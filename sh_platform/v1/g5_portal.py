"""G5 family portal: what one family member may see of their own share, read-only (docs/v3/PROGRAM-GAPS.md W5).

A person is a family member when their account's display name (or an entry in v3/settings.json "portal_members": {email: member name}) is a current
`family_members.member_name`. What they see of each entity is the signed rule `family_access_<member>_<entity>` (level full | summary | none, the
same rule the member_access recipe reads), capped by the entity scopes of their `family:<member>` access group when that group has any. Nothing is read for
another member: every query below takes the member's name and the levels worked out from it.

"My share" follows the ownership chain when the warehouse has an `entity_ownership` table (another builder adds it); it works out the member's
percentage of each entity they may see (member -> entity -> entity, with a cycle guard) and multiplies it by the entity's value. Without the table,
or without a column it understands, the view stays at entity level: the entities the member may see and their whole value, no percentage claimed.
The ask box answers only from the member's own share, documents and approvals (fixed rules, no model), so it cannot be led to anyone else's data.
Approvals addressed to a member are kept here (portal/approvals.json); staff raise them, only the addressed member decides.
ponytail: ownership column names are matched from a short list; a fixed schema once the entity_ownership table is final.
"""
from __future__ import annotations

import html
import logging
import os
import re
import threading
import time
import uuid
from datetime import date, datetime
from decimal import Decimal

import duckdb

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile.view import Viewer
from sh_platform.v1 import wh

log = logging.getLogger(__name__)
RANK = {"none": 0, "summary": 1, "full": 2}
GROUP_LEVEL = {"preview": "summary", "summary": "summary", "full": "full"}
STAFF = Viewer("Family portal", frozenset({"company_admin"}))  # reads whole-office figures; what is shown is cut down to the member's levels
NOT_SHARED = "Nothing is shared with you yet."
HELP = "I can answer about your own share, the entities you can see, your documents and approvals, and your morning note."
EMAIL_AT_ENV = "SH_MORNING_EMAIL_AT"  # "HH:MM" local time, default 07:00
_STOP = threading.Event()


def slug(text) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def norm(text) -> str:
    return " ".join(str(text).lower().split())


def money(v) -> str:
    from sh_platform.v1 import k10_note as N
    return N._millions(v) if v is not None and abs(Decimal(str(v))) >= 1000000 else N._money(v)


def _rows(con, sql: str, params: list | None = None) -> list[dict]:
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [{c: str(v) if isinstance(v, uuid.UUID) else v for c, v in zip(cols, r)} for r in cur.fetchall()]


def _read(plane, sql: str, params: list | None = None) -> list[dict]:
    """A read that answers nothing, never an error, when the table is not in this warehouse."""
    try:
        with wh.connect(plane, read_only=True) as con:
            return _rows(con, sql, params)
    except duckdb.Error:
        return []


# ---- who is a family member -----------------------------------------------------------------------------------------------------------

def members(plane) -> list[str]:
    rows = _read(plane, "select distinct m.member_name from family_members m where not exists (select 1 from family_members x where x.supersedes_family_member_id = m.id) order by 1")
    return [r["member_name"] for r in rows]


def member_of(plane, account: dict) -> str | None:
    """The family member name this account is, or None."""
    from sh_platform.v1 import v3_ops as O
    names = members(plane)
    mapped = (O.settings(plane).get("portal_members") or {}).get(str(account.get("email") or "").casefold())
    want = norm(mapped or account.get("display_name") or "")
    return next((n for n in names if norm(n) == want), None) if want else None


# ---- what they may see ----------------------------------------------------------------------------------------------------------------

def entities(plane) -> list[dict]:
    return _read(plane, "select id, entity_code, entity_name, base_currency from legal_entities order by entity_name")


def levels(plane, member: str) -> dict[str, str]:
    """{entity_code: level} the member may see (none is left out): the signed rule, capped by their access group's entity scopes when it has any."""
    ents = entities(plane)
    rules = {r["rule_code"]: r["level"] for r in _read(
        plane, "select r.rule_code, json_extract_string(v.parameters, '$.level') as level from business_rules r join rule_versions v on v.business_rule_id = r.id "
               "where starts_with(r.rule_code, 'family_access_') and v.approval_status = 'approved' "
               "qualify row_number() over (partition by r.rule_code order by v.version_number desc) = 1")}
    group = _read(plane, "select s.scope_value, s.access_level from access_groups g left join access_group_scopes s on s.access_group_id = g.id and s.scope_type = 'entity' "
                         "where g.group_name = ?", ["family:" + member])
    granted = {r["scope_value"]: GROUP_LEVEL.get(str(r["access_level"]), "none") for r in group if r["scope_value"]} or None  # no entity scope at all: the rule alone
    out = {}
    for e in ents:
        lv = rules.get(f"family_access_{slug(member)}_{slug(e['entity_code'])}") or "none"
        if lv not in RANK:
            lv = "none"
        if granted is not None and RANK[granted.get(e["entity_code"], "none")] < RANK[lv]:
            lv = granted.get(e["entity_code"], "none")
        if lv != "none":
            out[e["entity_code"]] = lv
    return out


# ---- ownership look-through -----------------------------------------------------------------------------------------------------------

def _col(cols: set, *cands):
    return next((c for c in cands if c in cols), None)


def ownership_edges(plane, member: str, on: date) -> list[dict] | None:
    """[{owner: ('member', name) | ('entity', code), owned: code, pct: Decimal fraction}] valid on the day, or None when the table or a column is missing."""
    cols = {r["column_name"] for r in _read(plane, "select column_name from information_schema.columns where table_name = 'entity_ownership'")}
    if not cols:
        return None
    o_ent, o_mem = _col(cols, "owner_entity_id", "owner_legal_entity_id"), _col(cols, "owner_member_name", "owner_name", "owner_family_member_id", "owner_member_id")
    owned, pct = _col(cols, "owned_entity_id", "owned_legal_entity_id", "legal_entity_id"), _col(cols, "ownership_pct", "percent", "pct", "ownership_percent")
    if not (owned and pct and (o_ent or o_mem)):
        return None
    a, b = _col(cols, "valid_from", "from_date", "effective_from", "active_from"), _col(cols, "valid_to", "to_date", "effective_to", "active_to")
    sel = ", ".join(c for c in (o_ent, o_mem, owned, pct, a, b) if c)
    ids = {e["id"]: e["entity_code"] for e in entities(plane)}
    mids = {r["id"]: r["member_name"] for r in _read(plane, "select id, member_name from family_members")}
    out = []
    for r in _read(plane, f"select {sel} from entity_ownership"):
        code = ids.get(r[owned], r[owned])
        if (a and r[a] and r[a] > on) or (b and r[b] and r[b] < on) or code not in ids.values():
            continue
        p = Decimal(str(r[pct])) / (Decimal(100) if re.search("pct|percent", pct) else Decimal(1))
        if o_ent and r[o_ent]:
            out.append({"owner": ("entity", ids.get(r[o_ent], r[o_ent])), "owned": code, "pct": p})
        elif o_mem and r[o_mem]:
            out.append({"owner": ("member", mids.get(r[o_mem], r[o_mem])), "owned": code, "pct": p})
    return out


def shares(edges: list[dict], member: str) -> dict[str, tuple[Decimal, list[str]]]:
    """{entity_code: (member's fraction of it, the chain)} following member -> entity -> entity. A cycle is cut where it closes."""
    got: dict[str, tuple[Decimal, list[str]]] = {}

    def walk(owner, frac: Decimal, path: list[str]) -> None:
        for e in edges:
            if e["owner"] == owner and e["owned"] not in path and len(path) < 8:
                f = frac * e["pct"]
                prev = got.get(e["owned"], (Decimal(0), []))
                got[e["owned"]] = (prev[0] + f, prev[1] + [" > ".join(path + [e["owned"]])])
                walk(("entity", e["owned"]), f, path + [e["owned"]])
    walk(("member", member), Decimal(1), [])
    return got


# ---- my share -------------------------------------------------------------------------------------------------------------------------

def _values(plane, cur: str) -> dict[str, dict]:
    """{entity_id: {total, portfolios:[{name,total}]}} for the whole office; the caller cuts it down."""
    try:
        from sh_platform.v1 import k4_office
        h = k4_office.holdings(plane, STAFF, cur)
    except Exception:  # noqa: BLE001 - a value that cannot be worked out is shown as not available, never a crash
        log.info("portal values unavailable", exc_info=True)
        return {}
    return {e["entity_id"]: {"total": e.get("total"), "portfolios": [{"name": p["portfolio_name"], "total": p["total"]} for p in e["portfolios"]]} for e in h["entities"]}


def my_share(plane, member: str, cur: str = "USD") -> dict:
    lv, ents, today = levels(plane, member), entities(plane), wh.now().date()
    vals = _values(plane, cur)
    edges = ownership_edges(plane, member, today)
    mine = shares(edges, member) if edges is not None else {}
    lines = []
    for e in ents:
        level = lv.get(e["entity_code"])
        if not level:
            continue
        v = vals.get(e["id"]) or {"total": None, "portfolios": []}
        frac, chain = mine.get(e["entity_code"], (None, []))
        line = {"entity": e["entity_name"], "code": e["entity_code"], "level": level, "value": v["total"], "your_pct": None if frac is None else frac * 100,
                "your_value": None if frac is None or v["total"] is None else v["total"] * frac, "via": chain}
        if level == "full":
            line["portfolios"] = [{"name": p["name"], "value": p["total"]} for p in v["portfolios"]]
        lines.append(line)
    hidden = sum(1 for c in mine if c not in lv)
    if edges is not None and mine:
        basis = "lookthrough"
        lines = [l for l in lines if l["your_pct"] is not None] or lines
        parts = [l["your_value"] for l in lines if l["your_value"] is not None]
        total = sum(parts, Decimal(0)) if parts and len(parts) == len(lines) else None
        note = "Your share follows the ownership chain: your percentage of each entity times its value." + (f" {hidden} more in the chain {'is' if hidden == 1 else 'are'} not shared with you." if hidden else "")
    else:
        basis, total = "entity", None
        note = ("The ownership chain is not recorded for you yet, so these are the whole values of the entities shared with you, not your percentage." if lines
                else NOT_SHARED)
    return {"member": member, "currency": cur, "as_of": today.isoformat(), "basis": basis, "total": total, "lines": lines, "note": note}


def _json(x):
    import json
    return json.loads(json.dumps(x, default=str))


# ---- documents ------------------------------------------------------------------------------------------------------------------------

def documents(plane, member: str) -> list[dict]:
    """Documents filed for the member's own group, `family:<member>`; nothing else is listed."""
    rows = _read(plane, "select d.id, d.title, d.document_type, d.document_date, d.received_at from documents d join access_groups g on g.id = d.access_group_id "
                        "where g.group_name = ? and not exists (select 1 from documents x where x.supersedes_document_id = d.id) order by d.received_at desc limit 50", ["family:" + member])
    return [{"id": r["id"], "title": r["title"], "kind": str(r["document_type"]).replace("_", " "), "date": str(r["document_date"] or r["received_at"])[:10]} for r in rows]


# ---- approvals addressed to a member --------------------------------------------------------------------------------------------------

def _af(plane):
    d = plane.path("portal")
    d.mkdir(parents=True, exist_ok=True)
    return d / "approvals.json"


def approvals_all(plane) -> list[dict]:
    try:
        return read_json_strict(_af(plane), list) or []
    except (OSError, ValueError):
        return []


def approvals_for(plane, member: str) -> list[dict]:
    return [a for a in approvals_all(plane) if a["member"] == member]


def raise_approval(plane, by: str, member: str, title: str, detail: str = "", amount=None, currency: str = "USD") -> dict:
    if member not in members(plane):
        raise ValueError("That is not a family member of this office.")
    title = " ".join(str(title).split())[:140]
    if not title:
        raise ValueError("Say what needs approving.")
    rec = {"id": "ap-" + wh.new_id()[:8], "member": member, "title": title, "detail": str(detail)[:600], "amount": None if amount in (None, "") else str(amount),
           "currency": str(currency)[:3].upper(), "status": "pending", "raised_by": by, "raised": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    f = _af(plane)
    with lock_for(f):
        write_json_atomic(f, approvals_all(plane) + [rec])
    return rec


def decide(plane, member: str, aid: str, approve: bool, note: str = "") -> dict:
    """Only the addressed member decides, and only once. ValueError carries the words for the screen."""
    f = _af(plane)
    with lock_for(f):
        rows = approvals_all(plane)
        rec = next((a for a in rows if a["id"] == aid and a["member"] == member), None)
        if rec is None:
            raise LookupError("I cannot find that approval.")
        if rec["status"] != "pending":
            raise ValueError(f"This was already {rec['status']}.")
        rec.update(status="approved" if approve else "declined", decided=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), note=str(note)[:300])
        write_json_atomic(f, rows)
    return rec


# ---- the morning note, the ask box ----------------------------------------------------------------------------------------------------

def morning_note(plane, member: str, share: dict | None = None) -> dict:
    s = share or my_share(plane, member)
    pend = [a for a in approvals_for(plane, member) if a["status"] == "pending"]
    cur = s["currency"]
    if not s["lines"]:
        head = NOT_SHARED
    elif s["basis"] == "lookthrough" and s["total"] is not None:
        head = f"Your share is worth {cur} {money(s['total'])}."
    else:
        head = f"{len(s['lines'])} {'entity is' if len(s['lines']) == 1 else 'entities are'} shared with you."
    lines = [head]
    lines += [f"{l['entity']}: " + (f"your {l['your_pct']:.1f}% is {cur} {money(l['your_value'])}" if l["your_value"] is not None else f"{cur} {money(l['value'])} in all") for l in s["lines"][:6]]
    if pend:
        lines.append(f"{len(pend)} {'approval is' if len(pend) == 1 else 'approvals are'} waiting for you.")
    lines.append(s["note"])
    return {"member": member, "as_of": s["as_of"], "headline": head, "lines": lines, "text": "\n".join(lines)}


def ask(plane, member: str, text: str) -> dict:
    """Answers from the member's own share, documents and approvals by fixed rules. Anything else gets what can be asked."""
    q, s = norm(text), my_share(plane, member)
    named = [l for l in s["lines"] if norm(l["entity"]) in q or norm(l["code"]) in q.split()]
    if re.search(r"\b(approv|pending|waiting|sign)\w*", q):
        pend = [a for a in approvals_for(plane, member) if a["status"] == "pending"]
        a = "; ".join(p["title"] for p in pend) if pend else "Nothing is waiting for you."
        return {"answer": a, "used": ["approvals"]}
    if re.search(r"\b(document|letter|statement|file|report|paper)s?\b", q):
        d = documents(plane, member)
        return {"answer": "; ".join(x["title"] for x in d[:8]) if d else "No documents are filed for you.", "used": ["documents"]}
    if re.search(r"\b(morning|note|today|new)\b", q):
        return {"answer": morning_note(plane, member, s)["text"], "used": ["morning note"]}
    if named or re.search(r"\b(share|worth|own|value|have|hold|entit|much|exposure|trust)\w*", q):
        if not s["lines"]:
            return {"answer": NOT_SHARED, "used": ["my share"]}
        rows = named or s["lines"]
        a = " ".join(f"{l['entity']}: " + (f"your {l['your_pct']:.1f}% is {s['currency']} {money(l['your_value'])}." if l["your_value"] is not None
                                           else f"{s['currency']} {money(l['value'])} in all." if l["value"] is not None else "value not available yet.") for l in rows)
        if s["basis"] == "lookthrough" and s["total"] is not None and not named:
            a = f"Your share is {s['currency']} {money(s['total'])}. " + a
        return {"answer": a, "used": ["my share"]}
    return {"answer": HELP, "used": []}


def portal(plane, member: str) -> dict:
    s = my_share(plane, member)
    return _json({"member": member, "share": s, "note": morning_note(plane, member, s), "documents": documents(plane, member), "approvals": approvals_for(plane, member)})


def accounts_of(plane) -> list[dict]:
    """The company's accounts with their email (`in_company` leaves it out), without the password hash."""
    from sh_platform.auth.accounts import AccountStore
    st = AccountStore(plane.root.parent)
    return [{k: a[k] for k in ("account_id", "email", "display_name", "roles", "disabled")} for a in map(st.get, [x["account_id"] for x in st.in_company(plane.company_id)]) if a]


# ---- the morning note by email --------------------------------------------------------------------------------------------------------

def _sfile(plane):
    d = plane.path("portal")
    d.mkdir(parents=True, exist_ok=True)
    return d / "morning_email.json"


def render_member_email(note: dict, base_url: str = "") -> dict:
    e = html.escape
    subject = f"Your morning note, {note['as_of']}: {note['headline']}"
    body = "".join(f'<p style="margin:10px 0;font-size:14px;line-height:1.5">{e(l)}</p>' for l in note["lines"])
    page = (f'<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;color:#14262b"><div style="font-size:12px;color:#5b6b70">Signal Harbor</div>'
            f'<h1 style="font-size:20px">{e(note["headline"])}</h1>{body}<p><a href="{e(base_url)}/v3/portal">Open your portal</a></p></body></html>')
    return {"subject": subject, "text": note["text"] + "\n\nOpen your portal: /v3/portal", "html": page}


def send_morning(plane, accounts: list[dict], day: str | None = None, force: bool = False) -> dict:
    """Write today's note as an email for each family member with an account (their own note) and, for the sponsor and admins, the office note.
    Goes through the egress gateway: SMTP when SH_SMTP_URL is set (env var name only), else a file in the plane's outbox. Once per day unless forced."""
    from sh_platform.egress import gateway
    from sh_platform.egress.errors import EgressBlocked
    day, f = day or wh.now().date().isoformat(), _sfile(plane)
    with lock_for(f):
        state = read_json_strict(f, dict) or {}
        if state.get("last_day") == day and not force:
            return {"day": day, "skipped": "already sent today", "sent": []}
        write_json_atomic(f, {**state, "last_day": day})
    sent = []
    for a in accounts:
        if a.get("disabled") or not a.get("email"):
            continue
        member, mail = member_of(plane, a), None
        try:
            if member:
                mail = render_member_email(morning_note(plane, member))
            elif {"company_admin", "sponsor"} & set(a["roles"]):
                from sh_platform.v1 import k10_note as N
                mail = N.render_email(N.morning_note(plane, Viewer(a.get("display_name") or "", frozenset(a["roles"]), False, a["account_id"])))
        except Exception:  # noqa: BLE001 - one person's note failing must not stop the others
            log.info("morning note for %s could not be built", a.get("account_id"), exc_info=True)
            sent.append({"to": a["email"], "result": "not built"})
            continue
        if mail is None:
            continue
        try:
            sent.append({"to": a["email"], "result": gateway.send_email(plane, [a["email"]], mail["subject"], mail["text"])})
        except EgressBlocked as e:
            sent.append({"to": a["email"], "result": "blocked: " + str(getattr(e, "reason_code", "refused"))})
    return {"day": day, "sent": sent}


def morning_due(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    at = (os.environ.get(EMAIL_AT_ENV) or "07:00").strip()
    try:
        h, m = (int(x) for x in at.split(":"))
    except ValueError:
        h, m = 7, 0
    return (now.hour, now.minute) >= (h, m)


# ---- the loop: push for new cards and approvals, and the daily email ------------------------------------------------------------------

def start(planes, interval: float = 60.0) -> threading.Thread:
    _STOP.clear()

    def loop() -> None:
        from sh_platform.v1 import g5_push
        while not _STOP.wait(interval):
            try:
                for plane in planes():
                    accts = accounts_of(plane)
                    g5_push.tick(plane, accts)
                    if morning_due():
                        send_morning(plane, accts)
            except Exception:
                log.exception("portal pass failed")
    t = threading.Thread(target=loop, name="g5-portal", daemon=True)
    t.start()
    return t


def stop() -> None:
    _STOP.set()
