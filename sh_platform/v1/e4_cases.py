"""E4a Exceptions and cases: the Action Desk's records (tables exceptions, exception_events, approvals, exception_impacts).

States: new, assigned, investigating, waiting_check, resolved, rejected (a dismissed case is rejected). Every change writes an exception_events row.
Maker-checker: the maker is whoever submits the explanation; the checker approves or sends back and is never the maker or the case owner.
A material case can only close through a check; `resolve` is the direct path for cases below threshold.
Numbers: CASE-0001 style, sequential per company, never reused. The model has no number column, so the number is the note of the `opened` event
and a counter file `cases/counter.json` keeps it from ever being reused (open point: a `case_number` column through E0b `propose_model_change`).
Event types written: opened, assigned, taken, explanation_proposed (by E4b), submitted, explanation_confirmed, sent_back, resolved, dismissed,
accounting_affected, finance_requested, comment.
Reads of rows for a person go through E1d (`e1_access`); it fails closed.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone

from sh_platform.v1.scope_memo import memo
from sh_platform.v1 import wh

log = logging.getLogger(__name__)
STATES = ("new", "assigned", "investigating", "waiting_check", "resolved", "rejected")
OPEN_STATES = ("new", "assigned", "investigating", "waiting_check")
RANK = {"material": 0, "unknown": 1, "below_threshold": 2}
_LOCK = threading.Lock()
_NUM = re.compile(r"^CASE-(\d{4,})$")
POLICY_TYPE = "policy_question"  # k7_benchmark opens these; they have no portfolio
POLICY_ROLES = frozenset({"approver", "analyst", "sponsor"})


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


# ---- people and numbers --------------------------------------------------------------------------------------------------------

def _org(plane) -> str:
    from sh_platform.v1.e1_write import org_id  # the uuid every card derives from the company id
    return org_id(plane)


def _col(con, sql: str, args: list) -> list:
    return [str(r[0]) for r in con.execute(sql, args).fetchall()]


def _uid(con, plane, who, required: bool = False) -> str | None:
    """Warehouse users.id for a Viewer, a name or a user id. None when the person has no users row; `required` refuses instead (maker-checker
    needs a real identity, so it fails closed)."""
    uid = None
    if who:
        try:
            uid = str(uuid.UUID(str(who)))
        except ValueError:
            r = []
            if getattr(who, "account_id", None):
                r = _col(con, "select id from users where external_identity_id = ? and is_active", [who.account_id])
            if len(r) != 1 and not getattr(who, "shared_name", False):
                r = _col(con, "select id from users where display_name = ? and is_active", [getattr(who, "name", str(who))])
            uid = r[0] if len(r) == 1 else None
    if uid is None and required:
        raise Refused(403, "That person is not set up as a user of this company's data yet.")
    return uid


def _name(con, plane, uid) -> str | None:
    if not uid:
        return None
    return _first(con, "select display_name from users where id = ?", [uid]) or str(uid)


def _admin(viewer) -> bool:
    return "company_admin" in set(getattr(viewer, "roles", ()) or ())


ACT_ROLES = frozenset({"company_admin", "sponsor", "analyst", "owner", "approver"})
NO_ACT = "A participant can see this case and ask Tally about it, but cannot act on it."
READ_ONLY = "Your access to this portfolio is read-only: you can see this case and ask Tally about it, but cannot act on it."


def _read_only(plane, actor, row: dict | None) -> bool:
    """analyst-uc2-02, uc8-02: a person whose access groups give only read on the case's portfolio sees it but never acts (E1d level, not the role)."""
    if plane is None or not row or not row.get("portfolio_id") or getattr(actor, "roles", None) is None or _admin(actor):
        return False
    from sh_platform.v1 import e1_access
    return e1_access.level(plane, actor, portfolio_id=row["portfolio_id"]) != "full"


def _may_act(actor, plane=None, row: dict | None = None) -> bool:
    """A11 least privilege (TD-01): a person whose only role is participant asks, never takes, submits, approves, sends back, resolves,
    dismisses or assigns; nor does a person with read-only access to the case's portfolio. An actor given by name or id (an internal call)
    carries no roles and is checked by the route's permissions."""
    roles = getattr(actor, "roles", None)
    return roles is None or (bool(ACT_ROLES & set(roles)) and not _read_only(plane, actor, row))


def _acting(actor, plane=None, row: dict | None = None) -> None:
    roles = getattr(actor, "roles", None)
    if roles is not None and not ACT_ROLES & set(roles):
        raise Refused(403, NO_ACT)
    if _read_only(plane, actor, row):
        raise Refused(403, READ_ONLY)


def _next_number(con, plane) -> str:
    f = plane.path("cases", "counter.json")
    with _LOCK:
        last = 0
        if f.is_file():
            last = int(json.loads(f.read_text(encoding="utf-8")).get("last", 0))
        for (n,) in con.execute("select event_note from exception_events where event_type = 'opened' and organization_id = ?", [_org(plane)]).fetchall():
            m = _NUM.match(n or "")
            last = max(last, int(m.group(1)) if m else 0)
        last += 1
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"last": last}), encoding="utf-8")
    return f"CASE-{last:04d}"


def _dicts(cur) -> list[dict]:
    """Cursor rows as dicts; uuid values as plain strings."""
    cols = [d[0] for d in cur.description]
    return [{c: (str(v) if isinstance(v, uuid.UUID) else v) for c, v in zip(cols, r)} for r in cur.fetchall()]


def _first(con, sql: str, args: list):
    r = con.execute(sql, args).fetchone()
    return None if r is None or r[0] is None else (str(r[0]) if isinstance(r[0], uuid.UUID) else r[0])


# ---- rows ----------------------------------------------------------------------------------------------------------------------

def _event(con, plane, exception_id: str, by, event_type: str, note: str = "", agent_run_id=None, source_record_id=None, evidence_document_id=None) -> str:
    eid = wh.new_id()
    at = wh.now()
    last = con.execute("select max(occurred_at) from exception_events where exception_id = ?", [exception_id]).fetchone()[0]
    if last is not None and at <= last:  # a coarse clock (Windows) must not reorder two events written together
        at = last + timedelta(microseconds=1)
    con.execute(
        "insert into exception_events (id, organization_id, exception_id, performed_by_user_id, agent_run_id, event_type, event_note, occurred_at,"
        " source_record_id, evidence_document_id) values (?,?,?,?,?,?,?,?,?,?)",
        [eid, _org(plane), exception_id, by, agent_run_id, event_type, note or None, at, source_record_id, evidence_document_id])
    return eid


def _row(con, exception_id: str) -> dict:
    try:
        uuid.UUID(str(exception_id))
    except ValueError:  # an unknown number or a made-up id is "not found", never a database error (ev.24)
        raise Refused(404, "That case does not exist.") from None
    rows = _dicts(con.execute("select * from exceptions where id = ?", [exception_id]))
    if not rows:
        raise Refused(404, "That case does not exist.")
    return rows[0]


def _resolve_ref(con, plane, ref: str) -> str:
    """A case id, or its number CASE-0001."""
    if _NUM.match(ref or ""):
        r = _first(con, "select exception_id from exception_events where event_type = 'opened' and event_note = ? and organization_id = ?", [ref, _org(plane)])
        if r:
            return r
    return ref


def _number(con, exception_id: str) -> str | None:
    return _first(con, "select event_note from exception_events where exception_id = ? and event_type = 'opened' order by occurred_at limit 1", [exception_id])


def _maker(con, exception_id: str) -> str | None:
    """Whoever last submitted an explanation for check."""
    return _first(con, "select performed_by_user_id from exception_events where exception_id = ? and event_type = 'submitted' order by occurred_at desc limit 1", [exception_id])


def _checker_requested(con, exception_id: str) -> str | None:
    return _first(con, "select requested_from_user_id from approvals where exception_id = ? and status = 'requested' order by requested_at desc limit 1", [exception_id])


def _set(con, exception_id: str, **cols) -> None:
    con.execute(f"update exceptions set {', '.join(k + ' = ?' for k in cols)} where id = ?", [*cols.values(), exception_id])


# ---- access (E1d) --------------------------------------------------------------------------------------------------------------

def _can_see(plane, viewer, row: dict, con) -> bool:
    uid = _uid(con, plane, viewer)
    if _admin(viewer) or (uid and uid in (row["owner_user_id"], _maker(con, row["id"]))):
        return True
    if not row["portfolio_id"]:
        if row["exception_type"] == POLICY_TYPE:  # a policy question is for the people who agree policy, not only its owner (a4.1)
            return bool(POLICY_ROLES & set(getattr(viewer, "roles", ()) or ()))
        return False  # fail closed: a case about nothing in particular is for its people and the admin
    try:
        from sh_platform.v1 import e1_access
    except ImportError:
        log.warning("E1d e1_access is not installed; cases cannot be filtered")
        raise
    return e1_access.level(plane, viewer, portfolio_id=row["portfolio_id"]) != "none"


def _see(con, plane, actor, row: dict) -> None:
    """Every action starts here: a person who may not see the case may not act on it (an agent, actor None, is not a person)."""
    if actor is not None and not _can_see(plane, actor, row, con):
        raise Refused(403, "You do not have access to this case.")


# ---- the contract ---------------------------------------------------------------------------------------------------------------

def open(plane, fields: dict) -> str:  # noqa: A001  (name fixed by the cross-card contract)
    """Open a case and return its id. Needed: exception_type, title. Optional: description, portfolio_id, instrument_id, candidate_impact_amount,
    impact_currency, materiality_status, materiality_rule_version_id, owner_user_id, due_at, decision_intent_id, calculation_run_id,
    accounting_view_affected (true pulls Finance in), actor."""
    if not fields.get("exception_type") or not fields.get("title"):
        raise Refused(400, "A case needs a type and a title.")
    status = fields.get("materiality_status") or "unknown"
    if status not in RANK:
        raise Refused(400, "Materiality must be unknown, below_threshold or material.")
    cols = ("decision_intent_id", "calculation_run_id", "portfolio_id", "instrument_id", "exception_type", "title", "description",
            "candidate_impact_amount", "impact_currency", "materiality_rule_version_id", "owner_user_id", "due_at")
    eid = wh.new_id()
    with wh.connect(plane) as con:
        owner = _uid(con, plane, fields["owner_user_id"], True) if fields.get("owner_user_id") else None
        con.execute(
            f"insert into exceptions (id, organization_id, detected_at, materiality_status, status, {', '.join(cols)}) values (?,?,?,?,?,{', '.join('?' * len(cols))})",
            [eid, _org(plane), fields.get("detected_at") or wh.now(), status, "assigned" if owner else "new", *[owner if c == "owner_user_id" else fields.get(c) for c in cols]])
        by = _uid(con, plane, fields.get("actor"))
        _event(con, plane, eid, by, "opened", _next_number(con, plane))
        if fields.get("accounting_view_affected"):
            _event(con, plane, eid, by, "accounting_affected", "The accounting view is affected.")
        if owner:
            _event(con, plane, eid, by, "assigned", f"Assigned to {_name(con, plane, owner)}.")
    return eid


def assign(plane, exception_id: str, actor, to, note: str = "") -> dict:
    """Give the case to a person (a name or a user id). Not once it is closed."""
    with wh.connect(plane) as con:
        exception_id = _resolve_ref(con, plane, exception_id)
        row = _row(con, exception_id)
        _see(con, plane, actor, row)
        _acting(actor, plane, row)
        if row["status"] not in OPEN_STATES:
            raise Refused(409, "This case is closed.")
        if row["status"] == "waiting_check":
            raise Refused(409, "This case is waiting for a check. Send it back first.")
        owner = _uid(con, plane, to, True)
        _set(con, exception_id, owner_user_id=owner, status="assigned" if row["status"] == "new" else row["status"])
        _event(con, plane, exception_id, _uid(con, plane, actor), "assigned", note or f"Assigned to {_name(con, plane, owner)}.")
    return {"id": exception_id, "owner": owner}


def take(plane, exception_id: str, actor) -> dict:
    """The person takes the case: they become the owner and start investigating."""
    with wh.connect(plane) as con:
        exception_id = _resolve_ref(con, plane, exception_id)
        row = _row(con, exception_id)
        _see(con, plane, actor, row)
        _acting(actor, plane, row)
        if row["status"] not in ("new", "assigned"):
            raise Refused(409, "This case cannot be taken now.")
        me = _uid(con, plane, actor, True)
        if row["owner_user_id"] and row["owner_user_id"] != me:
            raise Refused(403, "Another person owns this case.")
        _set(con, exception_id, owner_user_id=me, status="investigating")
        _event(con, plane, exception_id, me, "taken", "Took the case.")
    return {"id": exception_id, "status": "investigating"}


def add_event(plane, exception_id: str, actor, event_type: str, note: str = "", agent_run_id=None, source_record_id=None, evidence_document_id=None) -> str:
    """Write a history row (used by E4b for explanation_proposed, and for plain comments). actor may be None for an agent.
    A proposed explanation moves a new or assigned case to investigating."""
    with wh.connect(plane) as con:
        exception_id = _resolve_ref(con, plane, exception_id)
        row = _row(con, exception_id)
        eid = _event(con, plane, exception_id, _uid(con, plane, actor) if actor else None, event_type, note, agent_run_id, source_record_id, evidence_document_id)
        if event_type == "explanation_proposed" and row["status"] in ("new", "assigned"):
            _set(con, exception_id, status="investigating")
    return eid


def submit(plane, exception_id: str, actor, explanation: str, checker=None, code: str = "") -> dict:
    """The maker sends an explanation for check, with the reason it closes under (`code`, e.g. stale_data; kept when the checker approves).
    A named checker gets an approval request; the checker may not be the maker or the owner."""
    if not (explanation or "").strip():
        raise Refused(400, "Write the explanation to send for check.")
    with wh.connect(plane) as con:
        exception_id = _resolve_ref(con, plane, exception_id)
        row = _row(con, exception_id)
        _see(con, plane, actor, row)
        _acting(actor, plane, row)
        if row["status"] not in ("assigned", "investigating"):
            raise Refused(409, "Only a case being investigated can be sent for check.")
        me = _uid(con, plane, actor, True)
        if row["owner_user_id"] and me != row["owner_user_id"] and not _admin(actor):  # TD-02: the owner sends their own work for check
            raise Refused(403, "Only the person who owns this case, or a company administrator, can send it for check.")
        chk = _uid(con, plane, checker, True) if checker else None
        if chk and chk in (me, row["owner_user_id"]):
            raise Refused(403, "The checker must be someone other than the maker and the owner.")
        code = " ".join(str(code or "").split())[:60]
        _set(con, exception_id, status="waiting_check", resolution_code=code or None, **({} if row["owner_user_id"] else {"owner_user_id": me}))
        _event(con, plane, exception_id, me, "submitted", explanation.strip())
        if chk:
            con.execute("insert into approvals (id, organization_id, exception_id, approval_type, requested_from_user_id, status, requested_at)"
                        " values (?,?,?,?,?,?,?)", [wh.new_id(), _org(plane), exception_id, "case_explanation", chk, "requested", wh.now()])
    return {"id": exception_id, "status": "waiting_check"}


def _decide(plane, exception_id: str, actor, status: str, rationale: str, then) -> dict:
    """Shared checker path: the checks, the approvals row, then `then(con, eid, me)` for the state change, all in one connection."""
    with wh.connect(plane) as con:
        exception_id = _resolve_ref(con, plane, exception_id)
        row = _row(con, exception_id)
        _see(con, plane, actor, row)
        _acting(actor, plane, row)
        if row["status"] != "waiting_check":
            raise Refused(409, "This case is not waiting for a check.")
        me = _uid(con, plane, actor, True)
        if me in (row["owner_user_id"], _maker(con, exception_id)):
            raise Refused(403, "You cannot check your own work. Another person must decide.")
        asked = _checker_requested(con, exception_id)
        if asked and asked != me:
            raise Refused(403, f"This check was asked of {_name(con, plane, asked)}.")
        now = wh.now()
        r = _first(con, "select id from approvals where exception_id = ? and status = 'requested' order by requested_at desc limit 1", [exception_id])
        if r:
            con.execute("update approvals set status = ?, decision_by_user_id = ?, rationale = ?, decided_at = ? where id = ?", [status, me, rationale or None, now, r])
        else:  # nobody was named: the decision is its own approval row
            con.execute("insert into approvals (id, organization_id, exception_id, approval_type, requested_from_user_id, decision_by_user_id, status, rationale,"
                        " requested_at, decided_at) values (?,?,?,?,?,?,?,?,?,?)",
                        [wh.new_id(), _org(plane), exception_id, "case_explanation", me, me, status, rationale or None, now, now])
        return then(con, exception_id, me)


def approve(plane, exception_id: str, checker, rationale: str = "") -> dict:
    """The checker accepts the explanation and the case is resolved. Never the maker or the owner."""
    def done(con, eid, me):
        code = _first(con, "select resolution_code from exceptions where id = ?", [eid]) or "explained"  # the maker's reason, else explained
        _set(con, eid, status="resolved", resolution_code=code, resolved_at=wh.now())
        _event(con, plane, eid, me, "explanation_confirmed", rationale or "Explanation accepted.")
        _event(con, plane, eid, me, "resolved", "Resolved after check.")
        return {"id": eid, "status": "resolved"}
    return _decide(plane, exception_id, checker, "approved", rationale, done)


def send_back(plane, exception_id: str, checker, reason: str) -> dict:
    """The checker returns the case to investigating with a reason."""
    if not (reason or "").strip():
        raise Refused(400, "Say why you are sending it back.")

    def done(con, eid, me):
        _set(con, eid, status="investigating")
        _event(con, plane, eid, me, "sent_back", reason.strip())
        return {"id": eid, "status": "investigating"}
    return _decide(plane, exception_id, checker, "rejected", reason, done)


def resolve(plane, exception_id: str, actor, resolution_code: str, note: str = "") -> dict:
    """Close a case directly. Only for a case below threshold; a material or unrated case needs a check (submit, approve)."""
    with wh.connect(plane) as con:
        exception_id = _resolve_ref(con, plane, exception_id)
        row = _row(con, exception_id)
        _see(con, plane, actor, row)
        _acting(actor, plane, row)
        if row["status"] not in ("assigned", "investigating"):
            raise Refused(409, "This case cannot be resolved now.")
        if row["materiality_status"] != "below_threshold":
            raise Refused(403, "This case needs a check before it can be closed.")
        _set(con, exception_id, status="resolved", resolution_code=resolution_code or "resolved", resolved_at=wh.now())
        _event(con, plane, exception_id, _uid(con, plane, actor), "resolved", note or resolution_code or "Resolved.")
    return {"id": exception_id, "status": "resolved"}


def dismiss(plane, exception_id: str, actor, reason: str) -> dict:
    """Close a case as not a problem. A reason is required."""
    if not (reason or "").strip():
        raise Refused(400, "Say why you are dismissing this case.")
    with wh.connect(plane) as con:
        exception_id = _resolve_ref(con, plane, exception_id)
        row = _row(con, exception_id)
        _see(con, plane, actor, row)
        _acting(actor, plane, row)
        if row["status"] not in OPEN_STATES:
            raise Refused(409, "This case is already closed.")
        me = _uid(con, plane, actor, row["materiality_status"] != "below_threshold")
        if row["materiality_status"] != "below_threshold" and me in (row["owner_user_id"], _maker(con, exception_id)):
            raise Refused(403, "A material or unrated case is closed through a check, or dismissed by another person than its owner and maker.")
        _set(con, exception_id, status="rejected", resolution_code="dismissed", resolved_at=wh.now())
        _event(con, plane, exception_id, me, "dismissed", reason.strip())
    return {"id": exception_id, "status": "rejected"}


def _finance_may_help(con, row: dict) -> bool:
    """The accounting view is affected, or (UC5) a limit breach, whose cure is a trade Finance approves."""
    return row.get("exception_type") == "limit_breach" or bool(con.execute(
        "select 1 from exception_events where exception_id = ? and event_type = 'accounting_affected' limit 1", [row["id"]]).fetchone())


def ask_finance(plane, exception_id: str, actor, finance_user) -> dict:
    """Pull Finance in: only when the case says the accounting view is affected. Decision (Wave 2, A11): asking Finance to look is a request,
    not an act on the case, so a participant who can see the case may ask (no `_acting`); it changes no status, owner or figure, and the event
    records who asked."""
    with wh.connect(plane) as con:
        exception_id = _resolve_ref(con, plane, exception_id)
        row = _row(con, exception_id)
        _see(con, plane, actor, row)
        if not _finance_may_help(con, row):
            raise Refused(409, "Finance is asked only when the accounting view is affected or a limit breach needs a trade to cure it.")
        who = _uid(con, plane, finance_user, True)
        _event(con, plane, exception_id, _uid(con, plane, actor), "finance_requested", f"Asked {_name(con, plane, who)} in Finance to look.")
    return {"id": exception_id, "finance": who}


# ---- reading -------------------------------------------------------------------------------------------------------------------

def _may(con, plane, viewer, row: dict) -> dict:
    """Which buttons this person may press."""
    me, st = _uid(con, plane, viewer), row["status"]
    owner, maker = row["owner_user_id"], _maker(con, row["id"])
    asked = _checker_requested(con, row["id"])
    live = st in OPEN_STATES
    accounting = _finance_may_help(con, row)
    can_check = st == "waiting_check" and me not in (owner, maker) and (not asked or asked == me)
    mine = _admin(viewer) or (me is not None and (me == owner or not owner))
    other = me is not None and me not in (owner, maker)  # a material case is dismissed by someone else
    act = _may_act(viewer, plane, row)  # a participant or a read-only group asks, never acts (TD-01, analyst-uc2-02)
    return {"take": act and st in ("new", "assigned") and (not owner or owner == me),
            "assign": act and live and st != "waiting_check" and mine,
            "explain": st in ("new", "assigned", "investigating") and (_admin(viewer) or (me is not None and me == owner)),  # as the route gates it
            "submit": act and st in ("assigned", "investigating") and mine,
            "approve": act and can_check, "send_back": act and can_check,
            "resolve": act and st in ("assigned", "investigating") and row["materiality_status"] == "below_threshold" and mine,
            "dismiss": act and live and (mine if row["materiality_status"] == "below_threshold" else other), "ask_finance": live and accounting}


_LEVEL = {"material": "high", "unknown": "medium", "below_threshold": "low"}


def _view(row: dict) -> dict:
    """The names the screens use for the same facts (E4c): materiality high/medium/low, due, state, amount, currency."""
    return {"materiality": _LEVEL.get(row["materiality_status"], "medium"), "due": row["due_at"], "state": row["status"],
            "amount": row["candidate_impact_amount"], "currency": row["impact_currency"]}


def _proposal(history: list[dict]) -> dict | None:
    """The newest explanation_proposed note as {text, sources}: the note is 'text\nSources: a; b[\nfootnote]'."""
    notes = [h["event_note"] for h in history if h["event_type"] == "explanation_proposed" and h["event_note"]]
    if not notes:
        return None
    text, _, rest = notes[-1].partition("\nSources: ")
    src, *tail = rest.split("\n")
    return {"text": "\n".join([text, *tail]).strip(), "sources": [x for x in src.split("; ") if x and x != "none found"]}


def get(plane, exception_id: str, viewer) -> dict:
    """The case with its number, people in words, impacts, history, approvals and the buttons this viewer may press."""
    with wh.connect(plane) as con:
        exception_id = _resolve_ref(con, plane, exception_id)
        row = _row(con, exception_id)
        if not _can_see(plane, viewer, row, con):
            raise Refused(403, "You do not have access to this case.")
        cur = con.execute("select event_type, event_note, occurred_at, performed_by_user_id, agent_run_id, source_record_id, evidence_document_id"
                          " from exception_events where exception_id = ? order by occurred_at, id", [exception_id])
        history = _dicts(cur)
        for h in history:
            h["by"] = _name(con, plane, h.pop("performed_by_user_id")) or ("Tally" if h["agent_run_id"] else None)
        cur = con.execute("select i.report_version_id, i.issued_value, i.draft_value, i.currency, r.report_name, v.issued_at from exception_impacts i"
                          " left join report_versions v on v.id = i.report_version_id left join reports r on r.id = v.report_id where i.exception_id = ?", [exception_id])
        impacts = _dicts(cur)
        for h in history:
            h["at"] = h["occurred_at"]
            h["text"] = f"Case opened as {h['event_note']}." if h["event_type"] == "opened" else h["event_note"] or h["event_type"].replace("_", " ").capitalize()
        cur = con.execute("select requested_from_user_id, decision_by_user_id, status, rationale, requested_at, decided_at from approvals where exception_id = ? order by requested_at", [exception_id])
        approvals = _dicts(cur)
        for a in approvals:
            a["requested_from"], a["decided_by"] = _name(con, plane, a.pop("requested_from_user_id")), _name(con, plane, a.pop("decision_by_user_id"))
        may = _may(con, plane, viewer, row)
        affects = [f"{i['report_name'] or 'A report'}, issued {i['issued_at'].day} {i['issued_at']:%b}" if i["issued_at"] else f"{i['report_name'] or 'A report'}, not yet issued"
                   for i in impacts]
        maker = _name(con, plane, _maker(con, exception_id))
        return {**row, **_view(row), "number": _number(con, exception_id), "owner": _name(con, plane, row["owner_user_id"]), "maker": maker, "maker_name": maker,
                "checker_name": next((a["requested_from"] for a in reversed(approvals) if a["requested_from"]), None), "proposal": _proposal(history),
                "affects": affects, "impacts": impacts, "history": history, "approvals": approvals, "may": may, "can": may,
                "is_owner": bool(row["owner_user_id"]) and _uid(con, plane, viewer) == row["owner_user_id"]}


@memo
def listing(plane, viewer, filters: dict | None = None) -> list[dict]:
    """Cases the viewer may see, material first, then the largest (in the materiality rule's currency), then earliest due (no due last), then oldest. Filters: status ('active' = not closed), owner ('me' ok),
    exception_type, materiality_status, portfolio_id."""
    f = filters or {}
    with wh.connect(plane) as con:
        where, args = ["organization_id = ?"], [_org(plane)]
        if f.get("status") == "active":
            where.append("status in (" + ",".join(f"'{s}'" for s in OPEN_STATES) + ")")
        elif f.get("status"):
            where.append("status = ?")
            args.append(f["status"])
        for k in ("exception_type", "materiality_status", "portfolio_id"):
            if f.get(k):
                where.append(f"{k} = ?")
                args.append(f[k])
        if f.get("owner"):
            where.append("owner_user_id = ?")
            args.append(_uid(con, plane, viewer if f["owner"] == "me" else f["owner"]))
        cur = con.execute(f"select * from exceptions where {' and '.join(where)}", args)
        out, today = [], wh.now(plane).date()     # the company's day (demo_today when set), not the viewer's calendar
        for r in _dicts(cur):
            if _can_see(plane, viewer, r, con):
                out.append({**r, **_view(r), "number": _number(con, r["id"]), "owner": _name(con, plane, r["owner_user_id"]),
                            "closed_today": r["status"] not in OPEN_STATES and _utc_day(r["resolved_at"]) == today})
    far = datetime.max.replace(tzinfo=None)
    size = _sizer(plane)
    out.sort(key=lambda r: (RANK.get(r["materiality_status"], 1), -size(r), (r["due_at"].replace(tzinfo=None) if r["due_at"] else far), r["detected_at"].replace(tzinfo=None)))
    return out


def _utc_day(x):
    """The UTC calendar day of a stored instant (naive means UTC), or None."""
    return None if not isinstance(x, datetime) else (x.astimezone(timezone.utc) if x.tzinfo else x).date()


def _sizer(plane):
    """analyst-uc8-03: a case's size for ranking within a band, in the signed materiality rule's currency at today's signed rate (as is when no rate)."""
    from decimal import Decimal
    from sh_platform.v1 import e3_calc, e3_rules
    today = wh.now().date()
    to = ((e3_rules.current(plane, "cio_materiality", today) or {}).get("parameters") or {}).get("currency")
    rates: dict[str, Decimal] = {}

    def size(r: dict) -> Decimal:
        amt, ccy = abs(Decimal(str(r["candidate_impact_amount"] or 0))), (r["impact_currency"] or "").upper()
        if to and ccy and ccy != to.upper():
            if ccy not in rates:
                rates[ccy] = e3_calc.fx(plane, ccy, to, today) or Decimal(1)
            amt *= rates[ccy]
        return amt
    return size
