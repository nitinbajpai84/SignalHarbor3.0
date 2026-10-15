"""E5a Role Pulse: cards for each person, made from events only (open cases, documents waiting for review, mapping
proposals, failed loads, missing statements, approvals asked). No model is needed; every word and figure is copied from rows.

Storage is the `pulse_items` table. It has no columns for status word, owner, due or link, so the card detail is kept as
JSON inside `summary`; `outcome` and `delivery_status` hold what the person did.
Cap: at most 7 open cards per person (approvals are never cut and do not count).
`items` makes the cards itself when the last run is older than five minutes, so no scheduler is needed."""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone

from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id

log = logging.getLogger(__name__)
CAP = 7
REFRESH_SECONDS = 30  # short for the live demo; a scheduler can take over later
_LAST: dict[str, float] = {}  # plane folder -> monotonic time of the last generate
VALUATION_TYPES = ("revision", "missing_document", "stale_data", "late_statement")  # cases about a valuation take its dates; a break or a call does not
_KEYWORDS = {"cio": ("cio", "chief investment", "decision"), "operations": ("operation", "ops"), "finance": ("financ",),
             "risk": ("risk",), "data": ("data", "architect", "engineer")}


# Extension point (V3): other cards add their own card sources here instead of writing pulse_items themselves.
# A source is `fn(plane, con, today) -> list[dict]` returning cards made with `card(...)`. A card goes to everyone who has its `role`
# (see `_KEYWORDS`), or to one person when it carries `recipient` (a users.id). Give each card a stable `key` ("build:<pid>",
# "dash:<id>:<refresh>"): a card already made for a person, or dismissed by them, is never made twice, and a changed one is reworded.
# Register once at import: `e5_pulse.register_source(my_fn)`. A source that raises is logged and skipped; it never stops the pulse.
SOURCES: list = []


def register_source(fn):
    """Add a card source (see SOURCES). Registering the same function again does nothing. Returns fn, so it can be a decorator."""
    if fn not in SOURCES:
        SOURCES.append(fn)
    return fn


class Refused(Exception):
    def __init__(self, message: str, status: int = 403):
        super().__init__(message)
        self.message, self.status = message, status


def roles_of(business_role: str | None) -> set[str]:
    text = (business_role or "").lower()
    return {r for r, words in _KEYWORDS.items() if any(w in text for w in words)}


def _user(con, plane, viewer) -> tuple[str, set[str]] | None:
    for col, val in (("external_identity_id", getattr(viewer, "account_id", None)), ("display_name", getattr(viewer, "name", None))):
        if val:
            r = con.execute(f"select id, business_role from users where organization_id = ? and is_active and {col} = ?", [org_id(plane), val]).fetchone()
            if r:
                return r[0], roles_of(r[1])
    return None


def _money(amount, ccy) -> str:
    return f"{ccy or ''} {abs(float(amount)):,.0f}".strip() if amount is not None else "not yet worked out"


def _day(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def _add_business_days(d: date, n: int) -> date:
    while n > 0:
        d += timedelta(days=1)
        n -= d.weekday() < 5
    return d


def _visible_portfolios(plane, viewer) -> set[str]:
    try:
        from sh_platform.v1 import e1_access
    except ImportError:
        log.warning("e1_access is missing; the pulse cannot check who may see which portfolio")
        raise
    return {str(p) for p in e1_access.visible_portfolios(plane, viewer)}


def _card(role, key, kind, headline, text, *, status_word, urgency, action_type, action, as_of, received=None, effect=None,
          owner=None, due=None, link=None, exception_id=None, rank=5) -> dict:
    return {"role": role, "key": key, "kind": kind, "headline": headline[:250], "text": text, "status_word": status_word,
            "urgency": urgency, "action_type": action_type, "action": action, "as_of": as_of, "received": received, "effect": effect,
            "owner": owner, "due": due, "link": link, "exception_id": exception_id, "rank": rank}


card = _card  # public name for sources registered by other cards


def user_ids_with_roles(plane, con, roles: set[str]) -> list[str]:
    """users.id of every active person whose sign-in account holds one of these roles (e.g. {"analyst", "company_admin"})."""
    try:
        from sh_platform.auth.accounts import AccountStore
        accts = AccountStore(plane.root.parent).in_company(plane.company_id)
    except Exception:  # noqa: BLE001 - without the account list nobody is matched by role
        log.warning("accounts could not be read for the pulse", exc_info=True)
        return []
    ext = {a["account_id"] for a in accts if roles & set(a.get("roles") or []) and not a.get("disabled")}
    rows = con.execute("select id, external_identity_id from users where organization_id = ? and is_active", [org_id(plane)]).fetchall()
    return [r[0] for r in rows if r[1] in ext]


def _build_cards(plane, con, today: date) -> list[dict]:
    """I1: a signed intent of work sent to Build gives each head of data, analyst and admin a card that opens its Build project."""
    out = []
    people = user_ids_with_roles(plane, con, {"analyst", "company_admin"})
    for f in sorted(plane.path("intents").glob("*/send_to_build.json")) if plane.path("intents").is_dir() else []:
        try:
            sent = json.loads(f.read_text(encoding="utf-8"))
            sow = json.loads((f.parent / "sow.json").read_text(encoding="utf-8")) if (f.parent / "sow.json").is_file() else {}
        except (OSError, ValueError):
            continue
        pid = sent.get("project_id")
        if not pid:
            continue
        title = str(sow.get("title") or f.parent.name)
        when = str(sent.get("at") or today.isoformat())[:10]
        for uid in people:
            c = _card("*", f"build:{pid}", "build", f"{title} is ready for Build", f"{sent.get('by') or 'Someone'} signed the intent of work and sent it to Build.",
                      status_word="Signed", urgency="needs_me", action_type="open_build", action="Open in Build", as_of=when,
                      received=when, link=f"/centre/build/p/{pid}", rank=2)
            c["recipient"] = uid
            out.append(c)
    return out


def _name(con, uid):
    r = con.execute("select display_name from users where id = ?", [uid]).fetchone() if uid else None
    return r[0] if r else None


def _status_word(typ: str, val) -> str:
    """The card's status word from the newest valuation row's real state (val = valuation_type, approval_status, supersedes id)."""
    vtype, appr, sup = (val or (None, None, None))
    if typ == "revision" or sup:
        if appr in ("pending", "proposed"):
            return "Revised · unverified"
        if vtype == "manager_final":
            return "Revised · manager final"
        return "Revised · estimated" if "estimate" in (vtype or "") or typ == "revision" else "Revised"
    if typ == "break":
        return "Break"
    return "Stale" if typ == "stale_data" else "Estimated" if "estimate" in (vtype or "") else "Unverified"


def _exception_cards(con, today: date) -> list[dict]:
    rows = con.execute(
        "select e.id, e.exception_type, e.title, e.detected_at, e.candidate_impact_amount, e.impact_currency, e.materiality_status, "
        "e.owner_user_id, e.due_at, e.instrument_id, i.canonical_name from exceptions e "
        "left join instruments i on i.id = e.instrument_id where e.status not in ('resolved','rejected')").fetchall()
    out = []
    for (eid, typ, title, det, amt, ccy, mat, owner, due, iid, iname) in rows:
        eid = str(eid)
        val = con.execute("select valuation_date, received_at, valuation_type, supersedes_valuation_id, approval_status from valuation_observations "
                          "where instrument_id = ? order by recorded_at desc limit 1", [iid]).fetchone() if iid and typ in VALUATION_TYPES else None
        word = _status_word(typ, val and (val[2], val[4], val[3]))
        pending = word == "Revised · unverified"
        eff = _money(amt, ccy)
        text = f"{title}. Effect {eff}." + (f" Fund: {iname}." if iname else "")
        if pending:
            text = (f"Indicative, unverified: the manager-reported valuation of {iname or 'this fund'} differs by {eff} in an amended statement. "
                    "Operations is checking the figures.")
        common = dict(status_word=word, as_of=val[0].isoformat() if val else det.date().isoformat(), received=val[1].isoformat() if val else None,
                      effect=eff, owner=_name(con, owner), due=due.date().isoformat() if due else None, link=f"/centre/desk/{eid}",
                      exception_id=eid)

        def mk(role, urgency, rank):
            return _card(role, f"exc:{eid}:{role}", "exception", title, text, action_type="open_case", action="Open case",
                         urgency=urgency, rank=rank, **common)

        material = mat == "material"
        if material or (pending and typ == "revision"):  # an unverified change reaches the CIO as indicative, even before materiality is known
            out.append(mk("cio", "needs_me" if material else "worth_a_look", 1 if material else 3))
        if typ in ("revision", "missing_document"):
            out.append(mk("operations", "needs_me" if material or pending else "worth_a_look", 2 if material or pending else 4))
        if typ == "break":
            due_now = bool(due and due.date() <= today)  # Operations owns every break; a material or due one needs them now
            out.append(mk("operations", "needs_me" if material or due_now else "worth_a_look", 2 if material or due_now else 4))
            out.append(mk("finance", "needs_me" if material else "worth_a_look", 3 if material else 4))
        if typ in ("stale_data", "limit_breach"):
            out.append(mk("risk", "needs_me" if typ == "limit_breach" else "worth_a_look", 3))
        if typ == "capital_call":     # Finance funds the call; due within two weeks needs them now
            soon = bool(due and (due.date() - today).days <= 14)
            out.append(mk("finance", "needs_me" if material or soon else "worth_a_look", 2 if material or soon else 4))
        if typ == "late_statement":
            out.append(mk("operations", "worth_a_look", 4))
    return out


def _document_cards(con) -> list[dict]:
    rows = con.execute("select d.id, d.title, d.received_at, d.valuation_date, count(*) from extracted_fields f join documents d on d.id = f.document_id "
                       "where f.review_status = 'pending' group by 1, 2, 3, 4").fetchall()
    return [_card("operations", f"doc:{did}", "document", f"Check {title}", f"{n} figure{'s' if n != 1 else ''} read from {title} wait for your check.",
                  status_word="Unverified", urgency="needs_me", action_type="review_document", action="Check the figures",
                  as_of=(vd or rec.date()).isoformat(), received=rec.isoformat(), link=f"/centre/evidence/{did}", rank=3)
            for did, title, rec, vd, n in rows]


def _data_cards(con) -> list[dict]:
    out = []
    for bid, ref, rec, status, summ in con.execute(
            "select id, batch_reference, received_at, validation_status, validation_summary from source_batches "
            "where validation_status in ('rejected_totals','quarantined')").fetchall():
        out.append(_card("data", f"batch:{bid}", "load", f"Load failed: {ref}", summ or f"{ref} was not loaded ({status.replace('_', ' ')}).",
                         status_word="Unverified", urgency="needs_me", action_type="fix_load", action="See why", as_of=rec.date().isoformat(),
                         received=rec.isoformat(), link=f"/centre/data/intake?batch={bid}", rank=1))
    for mid, pat, sheet, ver in con.execute("select id, file_pattern, sheet_name, version_number from sheet_mappings where mapping_status = 'proposed'").fetchall():
        out.append(_card("data", f"map:{mid}", "mapping", f"Mapping to approve: {pat}",
                         f"A column mapping for {pat}{' / ' + sheet if sheet else ''} (version {ver}) waits for approval.",
                         status_word="Unverified", urgency="needs_me", action_type="review_mapping", action="Review mapping",
                         as_of=wh.now().date().isoformat(), link=f"/centre/data/intake?mapping={mid}", rank=2))
    return out


def _statement_cards(plane, con, today: date) -> list[dict]:
    try:
        from sh_platform.v1 import e3_rules
    except ImportError:
        log.warning("e3_rules is missing; missing-statement cards are not made")
        return []
    params = ((e3_rules.current(plane, "statement_due", today) or {}).get("parameters")) or {}
    n = params.get("business_days_after_month_end") or params.get("business_days") or params.get("days")
    if not n:
        return []
    month_end = today.replace(day=1) - timedelta(days=1)
    due = _add_business_days(month_end, int(n))
    if today <= due:
        return []
    out = []
    for iid, name in con.execute("select id, canonical_name from instruments where instrument_type = 'fund'").fetchall():
        if not con.execute("select 1 from valuation_observations where instrument_id = ? and valuation_date >= ?", [iid, month_end]).fetchone():
            out.append(_card("operations", f"stmt:{iid}:{month_end}", "statement", f"Statement missing: {name}",
                             f"No statement for {name} dated {_day(month_end)} has arrived. It was due {_day(due)}.", status_word="Stale",
                             urgency="needs_me", action_type="request_statement", action="Ask the manager", as_of=month_end.isoformat(),
                             due=due.isoformat(), link=None, rank=3))
    return out


def _approval_cards(con) -> list[dict]:
    out = []
    for aid, typ, uid, at, eid, title in con.execute(
            "select a.id, a.approval_type, a.requested_from_user_id, a.requested_at, a.exception_id, e.title from approvals a "
            "left join exceptions e on e.id = a.exception_id where a.status = 'requested'").fetchall():
        c = _card("*", f"appr:{aid}", "approval", f"Your approval: {title or typ.replace('_', ' ')}",
                  f"{typ.replace('_', ' ').capitalize()} waits for your decision.", status_word="Unverified", urgency="needs_me",
                  action_type="approve", action="Review and decide", as_of=at.date().isoformat(), received=at.isoformat(),
                  link=f"/centre/desk/{eid}" if eid else None, exception_id=str(eid) if eid else None, rank=0)
        c["recipient"] = uid
        out.append(c)
    return out


def generate(plane, today: date | None = None) -> int:
    """Make today's cards for everyone. Returns how many new cards were stored. Safe to run again: a card already
    made (or dismissed) for a person is not made twice; a waiting card whose words changed (unverified, then confirmed) is reworded."""
    today = today or wh.now().date()
    now = wh.now()
    made = 0
    try:
        from sh_platform.v1.e6_trace import current_trace_id
        trace_id = current_trace_id()
    except ImportError:
        trace_id = None
    _LAST[str(plane.root)] = time.monotonic()
    with wh.connect(plane) as con:
        people = [(u, roles_of(b)) for u, b in con.execute(
            "select id, business_role from users where organization_id = ? and is_active", [org_id(plane)]).fetchall()]
        cards = (_exception_cards(con, today) + _document_cards(con) + _data_cards(con) + _statement_cards(plane, con, today)
                 + _approval_cards(con))
        for source in SOURCES:
            try:
                cards += source(plane, con, today)
            except Exception:  # noqa: BLE001 - one card source failing never stops the pulse
                log.warning("pulse source %s failed", getattr(source, "__name__", source), exc_info=True)
        for uid, roles in people:
            mine = [c for c in cards if (c.get("recipient") is not None and str(c["recipient"]) == str(uid)) or ("recipient" not in c and c["role"] in roles)]
            have = {}
            for pid, s_, ds in con.execute("select id, summary, delivery_status from pulse_items where recipient_user_id = ?", [uid]).fetchall():
                have[json.loads(s_).get("key")] = (pid, ds, json.loads(s_))
            # open cards count toward the cap; acknowledged and dismissed ones free their place; approvals never count
            used = con.execute("select count(*) from pulse_items where recipient_user_id = ? and delivery_status = 'pending' and action_type <> 'approve'",
                               [uid]).fetchone()[0]
            room = max(CAP - used, 0)
            for c in sorted(mine, key=lambda c: (c["rank"], c["as_of"])):
                body = {k: v for k, v in c.items() if k != "recipient"}
                if c["key"] in have:
                    pid, ds, old = have[c["key"]]
                    if ds == "pending" and {k: old.get(k) for k in body} != body:
                        con.execute("update pulse_items set headline = ?, summary = ?, urgency = ? where id = ?",
                                    [c["headline"], json.dumps({**body, "trace_id": old.get("trace_id") or trace_id}), c["urgency"], pid])
                    continue
                if c["kind"] != "approval":
                    if room <= 0:
                        continue
                    room -= 1
                if trace_id:
                    body["trace_id"] = trace_id
                con.execute("insert into pulse_items (id, organization_id, recipient_user_id, exception_id, headline, summary, generated_at, as_of_at, "
                            "urgency, action_type, delivery_status) values (?,?,?,?,?,?,?,?,?,?,'pending')",
                            [wh.new_id(), org_id(plane), uid, c["exception_id"], c["headline"], json.dumps(body), now,
                             datetime.fromisoformat(c["as_of"]).replace(tzinfo=timezone.utc), c["urgency"], c["action_type"]])
                made += 1
    return made


def _stale(plane) -> bool:
    last = _LAST.get(str(plane.root))
    return last is None or time.monotonic() - last > REFRESH_SECONDS


def _role_of(plane, viewer, role: str | None) -> tuple[set[str], str | None]:
    """(the person's roles, the role being viewed). No role asked for: their first role, in name order."""
    with wh.connect(plane) as con:
        me = _user(con, plane, viewer)
    roles = me[1] if me else set()
    if role and role not in roles:
        raise Refused("You do not have that role.")
    return roles, role or (sorted(roles)[0] if roles else None)


def items(plane, viewer, on_date: date | None = None, role: str | None = None) -> list[dict]:
    """The viewer's cards for the day, plus older ones still waiting. Dismissed cards are left out. `role` shows only the
    cards made for that role (approvals asked of the person always show). The cards are made first when the last run is over five minutes old."""
    on_date = on_date or wh.now().date()
    _, role = _role_of(plane, viewer, role)
    if _stale(plane):
        generate(plane, on_date)
    with wh.connect(plane) as con:
        me = _user(con, plane, viewer)
        if not me:
            return []
        rows = con.execute("select id, exception_id, headline, summary, generated_at, urgency, action_type, delivery_status, acknowledged_at, outcome "
                           "from pulse_items where recipient_user_id = ? and delivery_status <> 'dismissed' and "
                           "(cast(generated_at as date) = ? or delivery_status = 'pending')", [me[0], on_date]).fetchall()
        visible, out = None, []
        for (pid, eid, head, summ, gen, urg, at, ds, ack, outc) in rows:
            card = json.loads(summ)
            if role and card.get("role") not in (role, "*"):
                continue
            ex = con.execute("select portfolio_id from exceptions where id = ?", [eid]).fetchone() if eid else None
            if ex and ex[0]:
                visible = _visible_portfolios(plane, viewer) if visible is None else visible
                if str(ex[0]) not in visible:
                    continue
            out.append({**card, "id": pid, "headline": head, "generated_at": gen.isoformat(), "urgency": urg, "action_type": at,
                        "delivery_status": ds, "acknowledged_at": ack.isoformat() if ack else None, "outcome": outc})
    return sorted(out, key=lambda c: (c["urgency"] != "needs_me", c["rank"], c["as_of"]))


def view(plane, viewer, on_date: date | None = None, role: str | None = None) -> dict:
    """What the Pulse screen needs: the role shown, the person's roles, and the cards."""
    roles, shown = _role_of(plane, viewer, role)
    return {"role": shown or "", "roles": sorted(roles), "items": items(plane, viewer, on_date, shown)}


def _mine(con, plane, viewer, item_id: str) -> None:
    me = _user(con, plane, viewer)
    row = con.execute("select recipient_user_id from pulse_items where id = ? and organization_id = ?", [item_id, org_id(plane)]).fetchone()
    if not me or not row or row[0] != me[0]:
        raise Refused("This card is not yours.")


def acknowledge(plane, viewer, item_id: str) -> dict:
    with wh.connect(plane) as con:
        _mine(con, plane, viewer, item_id)
        con.execute("update pulse_items set delivery_status = 'acknowledged', acknowledged_at = ?, outcome = 'acted' where id = ?", [wh.now(), item_id])
    return {"id": item_id, "delivery_status": "acknowledged", "outcome": "acted"}


def dismiss(plane, viewer, item_id: str, reason: str) -> dict:
    reason = (reason or "").strip()
    if not reason:
        raise Refused("Please say why you are dismissing this card.", 400)
    with wh.connect(plane) as con:
        _mine(con, plane, viewer, item_id)
        summ = json.loads(con.execute("select summary from pulse_items where id = ?", [item_id]).fetchone()[0])
        summ["dismiss_reason"] = reason
        con.execute("update pulse_items set delivery_status = 'dismissed', acknowledged_at = ?, outcome = 'dismissed_with_reason', summary = ? where id = ?",
                    [wh.now(), json.dumps(summ), item_id])
    return {"id": item_id, "delivery_status": "dismissed", "outcome": "dismissed_with_reason"}


register_source(_build_cards)
