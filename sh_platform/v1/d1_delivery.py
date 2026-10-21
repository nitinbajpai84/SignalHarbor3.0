"""V5 D1: step 5 of a project, Delivery. How people receive a published dashboard (docs/plan/V5-REDESIGN-PLAN.md section 6).

Channels: consume (the published dashboard), morning_note (a line in the Morning Note), slack, teams, email (digest), alert (a threshold, sent
by email / slack / teams / webhook) and webhook (outgoing). Each channel is a draft made by one person and approved by another, like a dashboard.
Messages are built from the published dashboard's own rows (a figure is printed as the record holds it, never worked out). Everything that
leaves goes through sh_platform/egress (send_email, send_webhook): the host must be on the company's list, names are masked, each attempt
is logged. A channel that is not set up, or a send that is refused, lands in the outbox with its preview and a plain reason: never silent.
Slack / Teams / webhook addresses are SECRETS BY NAME: an admin saves the name of an environment variable and the host; the address is read at
send time and never stored, shown or logged.

ponytail: one message per channel built from the first row of up to six tiles; a richer layout per channel when a customer asks.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import threading

from sh_platform.state import kv
from contextlib import suppress
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sh_platform.egress import email as mail
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.policy import _HOST, EgressPolicy
from sh_platform.jsonfile import read_json_strict, write_json_atomic
from sh_platform.v1 import b6_schedule as SCH
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import p1_project
from sh_platform.v1.p1_project import Refused
from sh_platform.v1.seats import ARCHITECT, seat_of

log = logging.getLogger(__name__)
KINDS = {"consume": "Consume", "morning_note": "Morning Note section", "slack": "Slack channel", "teams": "Microsoft Teams channel",
         "email": "Email digest", "alert": "Threshold alert", "webhook": "Outgoing webhook"}
HOOKS = ("slack", "teams", "webhook")  # kinds whose address is a secret by name
VIA = ("email", "slack", "teams", "webhook")
FREQ = ("daily", "weekly", "monthly", "on_change")
OPS = {"lt": "falls below", "gt": "goes above"}
# review: SH_ prefix and a hook suffix, so an admin cannot point a channel at any other environment variable (an API key, the session secret)
SECRET_NAME = re.compile(r"^SH_[A-Z0-9_]{1,50}_(?:HOOK|WEBHOOK|WEBHOOK_URL)$")
CID = re.compile(r"^ch-[0-9a-f]{6}$")
MAX_TILES, OUTBOX_CAP = 6, 200
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _who(viewer) -> str:
    return D.who(viewer)


def _name(viewer) -> str:
    return getattr(viewer, "name", "") or _who(viewer)


def _roles(viewer) -> set:
    return set(getattr(viewer, "roles", ()) or ())


def is_maker(viewer) -> bool:
    return bool({"company_admin", "analyst"} & _roles(viewer))


def is_admin(viewer) -> bool:
    return "company_admin" in _roles(viewer)


def can_approve(viewer, ch: dict) -> bool:
    """Someone other than the maker (or whoever submitted it): the head of data, the sponsor, the approver, or the company admin."""
    return (ch.get("status") == "submitted" and _who(viewer) not in (ch["made_by"], ch.get("submitted_by"))
            and bool({"company_admin", "sponsor", "approver"} & _roles(viewer) or ARCHITECT in seat_of(viewer)))


# ---- Settings: the channels an admin has set up (secrets by name) --------------------------------------------------------------------

def _cfg_path(plane):
    return plane.area("context") / "delivery_config.json"


def _cfg(plane) -> dict:
    try:
        got = read_json_strict(_cfg_path(plane), dict)
    except (OSError, ValueError):
        got = None
    return got or {}


def set_config(plane, viewer, kind: str, secret: str, host: str) -> dict:
    """An admin saves where a kind of channel sends: the NAME of the secret (an environment variable) and the host. Empty secret removes it.
    The host goes on the company's egress list for webhooks, one entry per configured host."""
    if not is_admin(viewer):
        raise Refused(403, "Only an administrator can set up delivery channels.")
    if kind not in HOOKS:
        raise Refused(400, "Choose Slack, Microsoft Teams or an outgoing webhook.")
    secret, host = str(secret or "").strip(), str(host or "").strip().lower()
    cfg = _cfg(plane)
    if not secret:
        cfg.pop(kind, None)
    else:
        if not SECRET_NAME.match(secret):
            raise Refused(400, "The secret name starts with SH_, ends with _WEBHOOK and uses capital letters, digits and underscores, for example SH_SLACK_WEBHOOK.")
        if not _HOST.fullmatch(host) or host.rsplit(".", 1)[-1].isdigit():  # review: a host name, never an IP address
            raise Refused(400, "Give the host only, for example hooks.slack.com, with no https:// and no path.")
        cfg[kind] = {"secret": secret, "host": host}
    write_json_atomic(_cfg_path(plane), cfg)
    EgressPolicy(plane).set_webhook_hosts({c["host"] for c in cfg.values()})
    return config_view(plane)


def config_view(plane) -> dict:
    """Which kinds are set up. Names the secret, never its value."""
    cfg = _cfg(plane)
    hooks = [{"kind": k, "label": KINDS[k], "secret": cfg.get(k, {}).get("secret", ""), "host": cfg.get(k, {}).get("host", ""),
              "configured": _hook_url(cfg, k) is not None} for k in HOOKS]
    return {"channels": hooks, "email": {"configured": mail.smtp_configured(), "domains": sorted(mail.allowed_domains(plane))}}


def _hook_url(cfg: dict, kind: str) -> str | None:
    c = cfg.get(kind) or {}
    url = (os.environ.get(c.get("secret", "")) or "").strip() if c.get("secret") else ""
    return url if url.lower().startswith("https://") else None


# ---- storage ------------------------------------------------------------------------------------------------------------------------

def _file(plane, pid: str):
    p1_project.read(plane, pid)  # 404 for an unknown project
    return plane.path("consume", pid, "delivery.json")


def _load(plane, pid: str) -> dict:
    try:
        got = read_json_strict(_file(plane, pid), dict)
    except (OSError, ValueError):
        raise Refused(500, "Delivery could not be read. Please ask your administrator.") from None
    return got or {"channels": [], "live_at": None}


def _save(plane, pid: str, rec: dict) -> dict:
    write_json_atomic(_file(plane, pid), rec)
    return rec


def _channel(rec: dict, cid: str) -> dict:
    ch = next((c for c in rec["channels"] if c["id"] == cid), None) if isinstance(cid, str) and CID.match(cid) else None
    if ch is None:
        raise Refused(404, "There is no such channel.")
    return ch


def outbox(plane, pid: str, limit: int = 30) -> list[dict]:
    _file(plane, pid)
    try:
        items = read_json_strict(plane.path("consume", pid, "delivery_outbox.json"), list) or []
    except (OSError, ValueError):
        items = []
    return items[-limit:][::-1]


def _log_out(plane, pid: str, ch: dict, status: str, reason: str, msg: dict, trigger: str) -> dict:
    row = {"id": "ob-" + secrets.token_hex(3), "channel_id": ch["id"], "kind": ch["kind"], "title": ch["title"], "at": _now(), "trigger": trigger,
           "status": status, "reason": reason, "subject": msg["subject"], "preview": msg["text"]}
    path = plane.path("consume", pid, "delivery_outbox.json")
    with _LOCK:
        items = (read_json_strict(path, list) or []) + [row]
        write_json_atomic(path, items[-OUTBOX_CAP:])
    return row


# ---- channels and their approval ------------------------------------------------------------------------------------------------------

def _published(plane, pid: str, did: str) -> dict:
    rec = D._load(plane, pid, did)
    view = D.published_view(rec)
    if view is None:
        raise Refused(409, "Only an approved dashboard can be delivered. Get the dashboard approved first.")
    return view


def _addresses(raw) -> list[str]:
    out = [a.strip() for a in (raw if isinstance(raw, list) else str(raw or "").replace(";", ",").split(",")) if str(a).strip()]
    if not out or not all(re.fullmatch(r"[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+", a) for a in out) or len(out) > 20:
        raise Refused(400, "Give one or more email addresses, for example daniel@example.com.")
    return out


def _alert(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    try:
        limit = str(Decimal(str(raw.get("limit"))))
    except (InvalidOperation, ValueError):
        raise Refused(400, "Give the limit as a number.") from None
    if raw.get("op") not in OPS or not str(raw.get("tile") or "").strip():
        raise Refused(400, "Choose the tile to watch and whether it falls below or goes above the limit.")
    return {"tile": str(raw["tile"]), "op": raw["op"], "limit": limit, "via": raw.get("via") if raw.get("via") in VIA else "email"}


def create_channel(plane, viewer, pid: str, body: dict) -> dict:
    if not is_maker(viewer):
        raise Refused(403, "Only the data team can set up delivery.")
    kind = body.get("kind")
    if kind not in KINDS:
        raise Refused(400, "Choose where it goes.")
    view = _published(plane, pid, body.get("dashboard_id"))
    D.get_published(plane, viewer, pid, body["dashboard_id"])  # review: only a dashboard the maker may open
    when = body.get("when") if body.get("when") in FREQ else "daily"
    ch = {"id": "ch-" + secrets.token_hex(3), "kind": kind, "title": str(body.get("title") or KINDS[kind])[:120], "dashboard_id": body["dashboard_id"],
          "when": {"freq": when, "at": str((body.get("at") or "07:00"))[:5]}, "status": "draft", "live": False, "made_by": _who(viewer),
          "made_by_name": _name(viewer), "made_at": _now(), "last_sent": None, "last_digest": None}
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", ch["when"]["at"]):
        raise Refused(400, "Give the time as hours and minutes, for example 07:00.")
    if kind == "alert":
        ch["alert"] = _alert(body.get("alert"))
        if ch["alert"]["tile"] not in {t["id"] for t in view["tiles"]}:
            raise Refused(400, "That tile is not on the approved dashboard.")
    if kind == "email" or (kind == "alert" and ch["alert"]["via"] == "email"):
        ch["addresses"] = _addresses(body.get("addresses"))
    with _LOCK:
        rec = _load(plane, pid)
        rec["channels"].append(ch)
        _save(plane, pid, rec)
    return ch


def _step(plane, viewer, pid: str, cid: str, fn) -> dict:
    with _LOCK:
        rec = _load(plane, pid)
        ch = _channel(rec, cid)
        fn(ch)
        _save(plane, pid, rec)
    return ch


def submit_channel(plane, viewer, pid: str, cid: str) -> dict:
    def go(ch):
        if not is_maker(viewer):
            raise Refused(403, "Only the data team can send a channel for approval.")
        if ch["status"] != "draft":
            raise Refused(409, "Only a draft can be sent for approval.")
        ch.update(status="submitted", submitted_by=_who(viewer), submitted_at=_now(), sent_back=None)
    return _step(plane, viewer, pid, cid, go)


def decide_channel(plane, viewer, pid: str, cid: str, approve: bool, reason: str = "") -> dict:
    def go(ch):
        if ch["status"] != "submitted":
            raise Refused(409, "This channel is not waiting for approval.")
        if _who(viewer) in (ch["made_by"], ch.get("submitted_by")):
            raise Refused(403, "You cannot approve a channel you set up. Another person has to.")
        if not can_approve(viewer, ch):
            raise Refused(403, "Only the head of data, the sponsor or an approver can approve a channel.")
        if approve:
            D.get_published(plane, viewer, pid, ch["dashboard_id"])  # review: nobody approves a message built from figures they may not see
            ch.update(status="approved", approved_by=_who(viewer), approved_by_name=_name(viewer), approved_at=_now(), sent_back=None)
        else:
            reason_ = str(reason or "").strip()[:500]
            if not reason_:
                raise Refused(400, "Say why you are sending it back, so the maker knows what to change.")
            ch.update(status="draft", sent_back={"reason": reason_, "by": _name(viewer), "at": _now()})
    return _step(plane, viewer, pid, cid, go)


def stop_channel(plane, viewer, pid: str, cid: str) -> dict:
    def go(ch):
        if not is_maker(viewer):
            raise Refused(403, "Only the data team can stop a channel.")
        ch.update(status="stopped", live=False)
    return _step(plane, viewer, pid, cid, go)


def go_live(plane, viewer, pid: str) -> dict:
    """Switch on every approved channel. Nothing is sent now: the first message goes at the channel's next time."""
    if not is_maker(viewer):
        raise Refused(403, "Only the data team can go live.")
    with _LOCK:
        rec = _load(plane, pid)
        ready = [c for c in rec["channels"] if c["status"] == "approved"]
        if not ready:
            raise Refused(409, "No channel is approved yet. Send a channel for approval first.")
        for c in ready:
            c["live"] = True
        rec["live_at"] = rec["live_at"] or _now()
        _save(plane, pid, rec)
    with suppress(Refused):  # V6: a project whose delivery is live is complete on the company map too (a plan can exist without a project record)
        p1_project.set_stage(plane, pid, "live")
    return {"live": [c["id"] for c in ready], "sent_now": 0}


# ---- messages, from records only ---------------------------------------------------------------------------------------------------------

def _fmt(v) -> str:
    if v is None:
        return "Not available yet"
    if isinstance(v, float):
        v = Decimal(str(v))
    if isinstance(v, Decimal) and v.is_finite() and v.as_tuple().exponent < -4:  # V6 review: a computed ratio printed 0.006024795840697594 in a subject line
        v = v.quantize(Decimal("0.0001") if abs(v) < 1 else Decimal("0.01"))
    if isinstance(v, (Decimal, int)) and not isinstance(v, bool):
        return f"{v:,}"
    return v.isoformat() if isinstance(v, (date, datetime)) else str(v)


def _reporting_month(plane, pid: str) -> str | None:
    """The month the business owner reviewed (like 2026-09), from the project's own review; None when there is none."""
    try:
        from sh_platform.v1 import b9_verify
        m = str((b9_verify.load(plane, pid).get("review") or {}).get("month") or "")
        return m if re.fullmatch(r"\d{4}-\d{2}", m) else None
    except Exception:  # noqa: BLE001 - without a review the first row stands
        return None


def _row_for(rows: list[dict], cols: list[str], month: str | None) -> dict:
    """The row of the reporting month when a month column says which row that is (V6: October's row must not stand in for September's report); else the first."""
    if month:
        for c in cols:
            if any(w in c.lower() for w in ("month", "period", "date")):
                hit = next((r for r in rows if str(r.get(c) or "")[:7] == month), None)
                if hit is not None:
                    return hit
    return rows[0]


def _figures(plane, pid: str, view: dict) -> list[dict]:
    """The reporting month's row of each of up to six tiles (the first row when no month column says which), as the rows hold it. A tile with no rows is left out; none is shown as zero."""
    out, month = [], _reporting_month(plane, pid)
    for t in view["tiles"]:
        if len(out) == MAX_TILES:
            break
        try:
            got = D.tile_rows(plane, pid, view, t["id"])
        except Exception:  # noqa: BLE001 - one tile failing must not stop the message
            log.warning("delivery: tile could not be read", exc_info=True)
            continue
        if got["rows"]:
            row, cols = _row_for(got["rows"], got["columns"], month), got["columns"]
            out.append({"tile": t["id"], "title": t["title"], "raw": [row[c] for c in cols[:3]],
                        "value": ", ".join(f"{c.replace('_', ' ')} {_fmt(row[c])}" for c in cols[:3])})
    return out


def build_message(plane, pid: str, ch: dict) -> dict:
    view = _published(plane, pid, ch["dashboard_id"])
    facts = _figures(plane, pid, view)
    lines = [f"{f['title']}: {f['value']}" for f in facts] or ["The figures are not available yet."]
    if ch["kind"] == "alert":
        a = ch["alert"]
        hit = breach(ch, facts)
        lines = [f"{hit['title']} {OPS[a['op']]} {_fmt(Decimal(a['limit']))}: now {hit['value']}."] if hit else lines
    subject = f"{view['title']}: {facts[0]['value']}"[:140] if facts else view["title"]
    text = "\n".join([view["title"], *lines, "Open the dashboard in Signal Harbor under Consume."])
    return {"subject": subject, "text": text, "facts": [{"title": f["title"], "value": f["value"], "tile": f["tile"]} for f in facts], "title": view["title"],
            "digest": hashlib.sha256("|".join(f"{f['tile']}={f['value']}" for f in facts).encode()).hexdigest()[:16]}


def breach(ch: dict, facts: list[dict]) -> dict | None:
    """The watched tile when its first number is past the limit (Decimal compare); None when it is fine or has no number."""
    a = ch["alert"]
    f = next((x for x in facts if x["tile"] == a["tile"]), None)
    for v in (f or {}).get("raw", []):
        if isinstance(v, bool) or not isinstance(v, (int, float, Decimal)):
            continue
        n, lim = Decimal(str(v)), Decimal(a["limit"])
        return f if (n < lim if a["op"] == "lt" else n > lim) else None
    return None


# ---- sending (through egress) -----------------------------------------------------------------------------------------------------------------

def deliver(plane, pid: str, ch: dict, trigger: str, *, senders: dict | None = None, at: datetime | None = None) -> dict:
    """Send one approved, live channel now. Returns the outbox row (status sent / held / blocked). `senders` = {"email": fn, "webhook": fn}
    replaces the egress exits (tests); the default ones are sh_platform.egress.gateway.send_email and send_webhook."""
    if ch["status"] != "approved" or not ch["live"]:
        raise Refused(409, "This channel is not live. It must be approved, then switched on with Go live.")
    from sh_platform.egress import gateway as G
    senders = senders or {}
    msg = build_message(plane, pid, ch)
    if ch["kind"] in ("consume", "morning_note"):  # inside the platform: Consume and the Morning Note read the channel list
        row = _log_out(plane, pid, ch, "sent", "Shown in Signal Harbor.", msg, trigger)
    else:
        via = ch["alert"]["via"] if ch["kind"] == "alert" else ch["kind"]
        if via == "email":
            if not mail.smtp_configured() and "email" not in senders:
                row = _log_out(plane, pid, ch, "held", "Email is not set up yet. Ask your administrator. The message is kept here.", msg, trigger)
            else:
                row = _try(plane, pid, ch, msg, trigger, lambda: (senders.get("email") or G.send_email)(plane, ch["addresses"], msg["subject"], msg["text"]))
        else:
            url = _hook_url(_cfg(plane), via)
            if url is None:
                row = _log_out(plane, pid, ch, "held", f"{KINDS[via]} is not set up yet. Ask your administrator. The message is kept here.", msg, trigger)
            else:
                body = {"text": msg["text"]} if via != "webhook" else {"title": msg["title"], "text": msg["text"], "facts": msg["facts"]}
                row = _try(plane, pid, ch, msg, trigger, lambda: (senders.get("webhook") or G.send_webhook)(plane, url, body))
    if row["status"] == "sent":
        with _LOCK:
            rec = _load(plane, pid)
            c = _channel(rec, ch["id"])
            c.update(last_sent=at.isoformat() if at else row["at"], last_digest=msg["digest"])
            _save(plane, pid, rec)
    return row


_WHY = {"destination_not_allowed": "The address is not on your company's list. Ask your administrator to add it.",
        "vault_name": "The message still held a protected name, so nothing was sent.",
        "log_unavailable": "The send log could not be written, so nothing was sent."}


def _try(plane, pid, ch, msg, trigger, send) -> dict:
    try:
        out = send()
    except EgressBlocked as e:
        code = getattr(e, "reason_code", "")
        return _log_out(plane, pid, ch, "blocked", _WHY.get(code, "It could not be sent. Nothing left your company. The message is kept here."), msg, trigger)
    except Exception:  # noqa: BLE001 - the reason text could echo the message
        log.warning("delivery send failed", exc_info=False)
        return _log_out(plane, pid, ch, "blocked", "It could not be sent. The message is kept here.", msg, trigger)
    if isinstance(out, str) and "outbox" in out:
        return _log_out(plane, pid, ch, "held", "Email is not set up yet. The message is kept here.", msg, trigger)
    return _log_out(plane, pid, ch, "sent", "Sent.", msg, trigger)


def retry(plane, viewer, pid: str, oid: str, *, senders: dict | None = None) -> dict:
    """Send a held or blocked outbox message again (after the channel is set up)."""
    if not is_maker(viewer):
        raise Refused(403, "Only the data team can send it again.")
    row = next((r for r in outbox(plane, pid, OUTBOX_CAP) if r["id"] == oid), None)
    if row is None or row["status"] == "sent":
        raise Refused(404, "There is no such waiting message.")
    return deliver(plane, pid, _channel(_load(plane, pid), row["channel_id"]), "retry", senders=senders)


# ---- the scheduler hook: daily 07:00 and on change ------------------------------------------------------------------------------------------

def is_due(ch: dict, msg: dict, now: datetime) -> bool:
    if ch["kind"] in ("consume", "morning_note", "alert") or ch["status"] != "approved" or not ch["live"]:
        return False  # alerts are judged in tick, at once
    last = datetime.fromisoformat(ch["last_sent"]).astimezone().replace(tzinfo=None) if ch["last_sent"] else None
    if ch["when"]["freq"] == "on_change":
        return ch["last_digest"] != msg["digest"]
    slot = SCH.last_slot({"freq": ch["when"]["freq"], "at": ch["when"]["at"], "day": 1}, now)
    return slot is not None and (last is None or last < slot)


def tick(plane, now: datetime | None = None, *, senders: dict | None = None) -> list[dict]:
    """One pass for a company: send every live channel that is due. Call each minute (start()). `now` is local server time."""
    now, out = now or datetime.now(), []
    b = plane.path("consume")
    for pid in sorted(p.name for p in b.iterdir() if (p / "delivery.json").exists()) if b.exists() else []:
        try:
            for ch in [c for c in _load(plane, pid)["channels"] if c["status"] == "approved" and c["live"] and c["kind"] not in ("consume", "morning_note")]:
                try:
                    msg = build_message(plane, pid, ch)
                    if ch["kind"] == "alert":
                        due = bool(breach(ch, _figures(plane, pid, _published(plane, pid, ch["dashboard_id"])))) and ch["last_digest"] != msg["digest"]
                    else:
                        due = is_due(ch, msg, now)
                    if due:
                        out.append(deliver(plane, pid, ch, "alert" if ch["kind"] == "alert" else ch["when"]["freq"], senders=senders, at=now))
                except Refused as e:
                    log.info("delivery %s skipped: %s", ch["id"], e.message)
        except Exception:
            log.exception("delivery pass for %s failed", pid)
    return out


def start(planes, interval: float = 60.0) -> threading.Thread:
    """Start the delivery thread (stdlib, like b6_schedule). `planes` returns the company planes. Stop with stop()."""
    _STOP.clear()

    def loop() -> None:
        while not _STOP.wait(interval):
            try:
                if not kv.lead():  # one copy per deployment runs this loop
                    continue
                for plane in planes():
                    from sh_platform.jobs import handlers as H, queue  # W3: through the job queue (a worker sends in production)
                    queue().submit("d1.tick", H.payload_of(plane), key=H.minute_key("d1.tick", plane))
            except Exception:
                log.exception("delivery pass failed")
    t = threading.Thread(target=loop, name="d1-delivery", daemon=True)
    t.start()
    return t


_STOP = threading.Event()


def stop() -> None:
    _STOP.set()


# ---- views --------------------------------------------------------------------------------------------------------------------------------------

def view(plane, viewer, pid: str) -> dict:
    rec = _load(plane, pid)
    cfg = config_view(plane)
    ready = {h["kind"]: h["configured"] for h in cfg["channels"]} | {"email": cfg["email"]["configured"]}
    dashboards = [{"id": x["id"], "title": x["title"]} for x in D.list_for(plane, viewer, pid)]
    seen = {x["id"] for x in dashboards}  # review: previews and outbox only for dashboards this person may open
    chans = []
    for c in rec["channels"]:
        via = c["alert"]["via"] if c["kind"] == "alert" else c["kind"]
        try:
            prev = build_message(plane, pid, c) if c["status"] != "stopped" and c["dashboard_id"] in seen else None
        except Refused:
            prev = None
        chans.append(c | {"label": KINDS[c["kind"]], "set_up": ready.get(via, True), "preview": prev and {"subject": prev["subject"], "text": prev["text"], "tile": (prev["facts"] or [{}])[0].get("tile")},
                          "can": {"submit": c["status"] == "draft" and is_maker(viewer), "approve": can_approve(viewer, c) and c["dashboard_id"] in seen,
                                  "stop": c["status"] != "stopped" and is_maker(viewer)}})
    of = {c["id"]: c["dashboard_id"] for c in rec["channels"]}
    return {"project_id": pid, "channels": chans, "kinds": [{"kind": k, "label": v} for k, v in KINDS.items()], "dashboards": dashboards,
            "live_at": rec["live_at"], "figures": _figure_lines(plane, viewer, pid) if dashboards else None, "settings": cfg, "outbox": [r for r in outbox(plane, pid) if of.get(r["channel_id"]) in seen],
            "can": {"make": is_maker(viewer), "go_live": is_maker(viewer) and any(c["status"] == "approved" and not c.get("live") for c in rec["channels"]), "settings": is_admin(viewer)}}


def morning_note_lines(plane, viewer) -> list[dict]:
    """For the Morning Note: one line per live, approved Morning Note channel, from the dashboard's own rows. A reader sees a line only for
    a dashboard they may open."""
    out, b = [], plane.path("consume")
    for pid in sorted(p.name for p in b.iterdir() if (p / "delivery.json").exists()) if b.exists() else []:
        try:
            chans = _load(plane, pid)["channels"]
        except Refused:  # review: one unreadable project must not hide every other line
            continue
        for c in chans:
            if c["kind"] == "morning_note" and c["status"] == "approved" and c["live"]:
                try:
                    D.get_published(plane, viewer, pid, c["dashboard_id"])
                    m = build_message(plane, pid, c)
                except Refused:
                    continue
                out.append({"project_id": pid, "dashboard_id": c["dashboard_id"], "title": m["title"], "lines": [f["title"] + ": " + f["value"] for f in m["facts"]]})
    return out


def _figure_lines(plane, viewer, pid: str) -> dict | None:
    from sh_platform.v1 import b9_verify
    try:
        return b9_verify.figure_lines(plane, viewer, pid)
    except Exception:  # noqa: BLE001 - a missing review or warehouse leaves the lines out; it never stops the page
        log.warning("delivery: figure lines unavailable", exc_info=True)
        return None


def _knowledge(plane, pid: str, proj: dict, dash: list[dict], fl: dict | None, signers: set[str]) -> list[dict]:
    """What the project put on the company map (design D5), from its own records. `verified` is true only when a record says so."""
    from sh_platform.v1 import b6_run, b9_verify
    plan = b6_run.latest_plan(plane, pid) or {}
    ran = bool(b9_verify.load(plane, pid).get("verified"))
    arts = {a["kind"]: a for a in proj.get("artefacts") or []}
    groups = [
        ("Sources", [(str(x.get("code") or x.get("name")), ran) for x in plan.get("sources") or [] if isinstance(x, dict)]),
        ("Tables", [(str(x["name"]), ran) for x in plan.get("tables") or [] if isinstance(x, dict) and x.get("layer") == "gold" and x.get("name")]),
        ("Definitions", [(f"{fl['name'] or 'Benchmark'}, version {fl['version']}", arts.get("benchmarks", {}).get("state") == "signed")] if fl and fl.get("version") else []),
        ("Dashboards", [(f"{x['title']}, {x['accepted']} tile{'s' if x['accepted'] != 1 else ''}", True) for x in dash]),
        ("People", [(f"{n}, {r}", n in signers) for r, n in (("owner", proj["people"].get("raiser")), ("sponsor", proj["people"].get("sponsor")),
                                                              ("builder", proj["people"].get("builder")), ("head of data", proj["people"].get("head_of_data")),
                                                              ("operations", proj["people"].get("ops"))) if n]),
    ]
    return [{"group": g, "items": [{"text": t, "verified": v} for t, v in items]} for g, items in groups if items]


def _approved_plan(plane, pid: str) -> dict:
    from sh_platform.v1 import b6_run
    try:
        return b6_run.latest_plan(plane, pid, live=True) or {}
    except (OSError, ValueError):
        return {}


def _builder_live(plane, pid: str) -> str | None:
    """V6: the builder (b11) took the pipeline live with no separate verification: say who pressed it and whether a variance was accepted."""
    try:
        from sh_platform.v1 import b11_builder
        rounds = b11_builder.load(plane, pid)["rounds"]
        out = next((r["outcome"] for r in reversed(rounds) if (r.get("outcome") or {}).get("kind") == "live"), None)
    except Exception:  # noqa: BLE001 - nothing recorded is shown as not recorded
        return None
    return out and f"Live, started by {out['by']}" + (" with a variance accepted" if out.get("anyway") else " after a clean check")


def summary(plane, viewer, pid: str) -> dict:
    """The project-complete page: what was verified, from the project's own records. A line appears only when its record says so."""
    from sh_platform.v1 import b9_verify
    proj, rec = p1_project.read(plane, pid), _load(plane, pid)
    chans = [c for c in rec["channels"] if c["status"] == "approved"]
    dash = [x for x in D.list_for(plane, viewer, pid)]
    arts = {a["kind"]: a for a in proj.get("artefacts") or []}
    fl, ver = _figure_lines(plane, viewer, pid), b9_verify.load(plane, pid)
    plan = _approved_plan(plane, pid)
    arch_by = (arts.get("design") or {}).get("signed_by") or plan.get("approved_by")  # V6: the head of data's plan approval is the architecture approval
    verified = []
    if fl:
        verified.append({"text": f"{fl['month_name']} figures match the certified report: portfolio {fl['portfolio_pct']}%, benchmark {fl['benchmark_pct']}%, {fl['difference_pts']} points", "by": fl.get("accepted_by") or ""})
    if ver.get("verified"):
        v = ver["verified"]
        verified.append({"text": f"Trial run on a copy matched the source files before the pipelines went live ({v['matched']} of {v['total']} figures)", "by": v["by"]})
    if fl and fl["mix"]:
        verified.append({"text": f"Benchmark uses approved version {fl['version']}: " + ", ".join(f"{m['component'].replace('_', ' ')} {Decimal(m['weight_pct']).normalize():f}%" for m in fl["mix"]), "by": ""})
    for kind, label in (("intent", "The intent was signed"), ("design", "The architecture was approved"), ("run_book", "The run book was signed"), ("benchmarks", "The benchmark was signed")):
        a = arts.get(kind) or {}
        by = arch_by if kind == "design" else a.get("signed_by") if a.get("state") == "signed" else None
        if by:
            verified.append({"text": label, "by": by})
    if dash:
        verified.append({"text": ("Dashboard approved by someone who did not build it" if len(dash) == 1 else f"{len(dash)} dashboards approved by someone who did not build them"), "by": ", ".join(sorted({str(x.get('approved_by') or '') for x in dash if x.get("approved_by")}))})
    if chans:
        verified.append({"text": ("Delivery channel approved by someone who did not set it up" if len(chans) == 1 else f"All {len(chans)} delivery channels approved by someone who did not set them up"),
                         "by": ", ".join(sorted({c["approved_by_name"] for c in chans}))})
    steps = [{"n": 1, "label": "Intent", "who": "North, the industry expert", "state": (arts.get("intent") or {}).get("signed_by") and f"Signed by {arts['intent']['signed_by']}"},
             {"n": 2, "label": "Architecture", "who": "Span maps it to your data", "state": arch_by and f"Approved by {arch_by}"},
             {"n": 3, "label": "Pipelines", "who": "Span tries it, then runs it", "state": (f"Verified by {ver['verified']['by']}" if ver.get("verified") else _builder_live(plane, pid))},
             {"n": 4, "label": "Dashboards and delivery", "who": "Lumen builds views and sends them", "state": f"Approved and delivered to {len(chans)} channel{'s' if len(chans) != 1 else ''}" if chans else None}]
    signers = {n.strip() for a in arts.values() for n in str(a.get("signed_by") or "").split(",") if n.strip()} | {c["approved_by_name"] for c in chans}
    signers |= {arch_by} if arch_by else set()
    signers |= {n for n in ((fl or {}).get("accepted_by"), (ver.get("verified") or {}).get("by")) if n}
    return {"project_id": pid, "title": proj.get("title"), "complete": bool(rec["live_at"]), "live_at": rec["live_at"], "verified": verified, "steps": steps,
            "knowledge": _knowledge(plane, pid, proj, dash, fl, signers), "figures": fl,
            "delivered_to": [{"id": c["id"], "kind": c["kind"], "label": KINDS[c["kind"]], "title": c["title"], "approved_by": c["approved_by_name"],
                              "approved_at": c["approved_at"], "live": c["live"]} for c in chans],
            "not_approved": [c["id"] for c in rec["channels"] if c["status"] in ("draft", "submitted")]}
