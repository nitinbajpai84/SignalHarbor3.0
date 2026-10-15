"""The intent lifecycle (spec 01): the one transition table, the per-type closer (ruling 25), time box, extend, close, cancel.

Pure functions over a record dict: the routes in records.py hold the lock and write. Pattern copied from modules/m1_intent/domain/states.py.
Type defaults (stages, days, confirmers, empty outcome) are read from the contract file modules/m1_intent/contracts/intent_types.yaml.
"""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import yaml

from sh_platform.intents import store as S

ILLEGAL = "This intent cannot move there from where it is now."
TYPES_FILE = Path(__file__).resolve().parents[2] / "modules" / "m1_intent" / "contracts" / "intent_types.yaml"
MOVES = {("draft", "open"), ("draft", "cancelled"), ("open", "in_session"), ("in_session", "open"), ("open", "closing"),
         ("in_session", "closing"), ("closing", "open"), ("closing", "closed"), ("open", "cancelled"), ("in_session", "cancelled"),
         ("closing", "cancelled")}
NORTH_MAY = {("in_session", "open"), ("open", "closing"), ("in_session", "closing")}  # North never moves to closed or cancelled
EXTENDABLE = ("open", "in_session", "closing")
LIST_FIELDS = {"options", "runners_up", "ideas_kept", "dropped", "weeks"}
NEXT_KINDS = ("initiative", "problem", "decision", "backlog", "handled", "nothing")


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


@lru_cache(maxsize=1)
def _types() -> dict:
    return yaml.safe_load(TYPES_FILE.read_text(encoding="utf-8"))["types"]


def type_def(type_: str) -> dict:
    return _types()[type_]


def confirmers(type_: str) -> list[str]:
    """People slots that sign before the organiser may close: sponsor (Initiative), decider (Decision), owner then reporter (Problem)."""
    c = type_def(type_)["closure"].get("closer_confirms")
    return [] if not c else [c] if isinstance(c, str) else list(c)


def can_move(frm: str, to: str, by: str) -> bool:
    return (frm, to) in MOVES and (by != "north" or (frm, to) in NORTH_MAY)


def blank_closure(draft_by: str | None = None) -> dict:
    return {"closed_by": None, "closed_at": None, "summary": "", "why_it_happened": "", "what_came_out": "", "next": [],
            "cancel_reason": None, "draft_by": draft_by, "signed": False, "confirmed": []}


def empty_outcome(type_: str) -> dict:
    o = type_def(type_)["outcome"]
    return {"kind": o["kind"], **{f: [] if f in LIST_FIELDS else None if f in ("build_ready", "chosen") else "" for f in o["fields"]}}


def person(account_id: str | None, name: str) -> dict:
    return {"account_id": account_id, "name": name}


def new_record(type_: str, company: str, creator: dict, now: str, *, title: str = "", purpose: str = "", areas: list | None = None,
               link_from: str | None = None) -> dict:
    iid = S.new_id(type_)
    return {"id": iid, "type": type_, "title": title, "purpose": purpose, "created_by": creator["account_id"], "created_at": now,
            "company": company, "areas": areas or [], "people": {**{s: None for s in S.SLOTS}, "organiser": creator,
                                                                 **{k: [] for k in S.LISTS}},
            "state": "draft", "time_box": {"starts": "", "ends": "", "extended_by": []}, "stages": [], "outcome": empty_outcome(type_),
            "closure": blank_closure(), "ratings": [], "links": {"from": link_from, "to": [], "build": None},
            "share": {"link": None, "who_may_open": []}, "record": f"intents/{iid}/intent.json", "version": 1, "updated_at": now,
            "history": [{"at": now, "by": creator["account_id"], "from": "", "to": "draft", "note": ""}], "affected_may_read": False,
            "refs": {"wall_session_ids": [], "charter_outcome_id": None, "baseline_ids": [], "assessment_ids": []}, "event_count": 0}


# ---- time -------------------------------------------------------------------------------------------------------------------

def zone(tz_name: str | None):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name) if tz_name else timezone.utc
    except Exception:  # unknown name or no tz database on this box: UTC (ruling 22)
        return timezone.utc


def company_zone(plane):
    from sh_platform.profile import store as pstore, view as pview
    node = (pstore.load(plane).get("company") or {}).get("time_zone")
    return zone(pview._v({"v": node}, "v") if isinstance(node, dict) else node)


def add_working_days(start: datetime, days: int, tz=timezone.utc) -> datetime:
    """The same time of day `days` working days later (Monday to Friday, no holidays), counted in the company's zone (else UTC). A start on
    a weekend counts from the next Monday. The one count: clock.working_days calls this."""
    day, left = start.astimezone(tz), days
    while day.weekday() >= 5:
        day += timedelta(days=1)
    while left > 0:
        day += timedelta(days=1)
        left -= day.weekday() < 5
    return day.astimezone(timezone.utc)


# ---- transitions ------------------------------------------------------------------------------------------------------------

def _hist(rec: dict, by: str, frm: str, to: str, now: str, note: str = "") -> None:
    rec["history"].append({"at": now, "by": by, "from": frm, "to": to, "note": note})


def _organiser(rec: dict, by: str) -> None:
    if by != "north" and (rec["people"].get("organiser") or {}).get("account_id") != by:
        raise Refused(403, "Only the organiser can do that.")


def move(rec: dict, to: str, by: str, now: str, *, note: str = "", tz=timezone.utc, ends: str | None = None) -> None:
    """One transition from the table, except to `closed` and `cancelled` (close() and cancel() sign). Raises Refused."""
    frm = rec["state"]
    if to in ("closed", "cancelled") or not can_move(frm, to, by):
        raise Refused(409, ILLEGAL)
    _organiser(rec, by)
    if (frm, to) == ("draft", "open"):
        _open(rec, now, tz, ends)
    elif (frm, to) == ("open", "in_session"):
        st = next((s for s in rec["stages"] if s["state"] == "open"), None)
        if st and not st["opened_at"]:
            st["opened_at"] = now
    elif (frm, to) == ("in_session", "open"):
        live = {s["key"] for s in type_def(rec["type"])["stages"] if s.get("live")}
        for s in rec["stages"]:
            if s["state"] == "open" and s["key"] in live:
                s.update(state="closed", closed_at=now)
    elif to == "closing":
        old = rec.get("closure") or {}
        rec["closure"] = old if old.get("draft_by") else blank_closure(by)  # a draft kept after "Send back to open" is not rewritten
        rec["closure"].update(closed_by=None, closed_at=None, cancel_reason=None, signed=False)
    rec["state"] = to
    _hist(rec, by, frm, to, now, note)


def _open(rec: dict, now: str, tz, ends: str | None) -> None:
    td, start = type_def(rec["type"]), datetime.fromisoformat(now)
    end = add_working_days(start, int(td["time_box_days"]), tz)
    if ends:  # the organiser may set a shorter end at Open
        try:
            want = datetime.fromisoformat(ends)
        except ValueError:
            raise Refused(400, "That end date is not a date.") from None
        if want.tzinfo is None:
            want = want.replace(tzinfo=timezone.utc)
        if not start < want <= end:
            raise Refused(400, "The end must be after now and no later than the type's default.")
        end = want
    rec["time_box"].update(starts=now, ends=end.isoformat())
    rec["stages"] = [{"key": s["key"], "state": "waiting", "opened_at": None, "closed_at": None} for s in td["stages"]]  # names stay in the contract
    rec["stages"][0].update(state="open", opened_at=now)


def set_stage(rec: dict, key: str, to: str, by: str, now: str) -> None:
    """Open (`waiting` to `open`) or close (`open` to `closed`) one stage. Organiser, while the intent is open or in session."""
    _organiser(rec, by)
    st = next((s for s in rec["stages"] if s["key"] == key), None)
    if st is None:
        raise Refused(404, S.NOT_FOUND)
    if rec["state"] not in ("open", "in_session") or (to, st["state"]) not in (("open", "waiting"), ("closed", "open")):
        raise Refused(409, ILLEGAL)
    st["state"] = to
    st["opened_at" if to == "open" else "closed_at"] = now
    _hist(rec, by, rec["state"], rec["state"], now, f"stage {key} {to}")


def extend(rec: dict, by: str, new_end: str, reason: str, now: str) -> None:
    _organiser(rec, by)
    if rec["state"] not in EXTENDABLE:
        raise Refused(409, ILLEGAL)
    if not isinstance(reason, str) or not reason.strip():
        raise Refused(400, "Please say why the time box is extended.")
    try:
        end = datetime.fromisoformat(new_end)
        old = datetime.fromisoformat(rec["time_box"]["ends"])
    except (TypeError, ValueError):
        raise Refused(400, "That end date is not a date.") from None
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if end <= old:
        raise Refused(400, "The new end must be later than the current end.")
    rec["time_box"]["extended_by"].append({"by": by, "at": now, "reason": reason.strip()})
    rec["time_box"]["ends"] = end.isoformat()
    _hist(rec, by, rec["state"], rec["state"], now, f"extended from {old.isoformat()} to {end.isoformat()}: {reason.strip()}")


def confirm(rec: dict, by: str, now: str) -> str:
    """The per-type confirmer signs, in the order the type names (owner before reporter). Returns the role confirmed."""
    if rec["state"] != "closing":
        raise Refused(409, ILLEGAL)
    done = {c["role"] for c in rec["closure"].setdefault("confirmed", [])}
    todo = [r for r in confirmers(rec["type"]) if r not in done]
    if not todo:
        raise Refused(409, "Nothing is waiting for a confirmation.")
    if (rec["people"].get(todo[0]) or {}).get("account_id") != by:
        raise Refused(403, f"Waiting for the {todo[0]}.")
    rec["closure"]["confirmed"].append({"role": todo[0], "by": by, "at": now})
    _hist(rec, by, "closing", "closing", now, f"{todo[0]} confirmed")
    return todo[0]


def close(rec: dict, by: str, body: dict, now: str) -> None:
    """closing to closed. A named person, never North. The confirmer (where the type names one) has signed first."""
    if rec["state"] != "closing" or by == "north":
        raise Refused(409, ILLEGAL)
    _organiser(rec, by)
    summary = body.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise Refused(400, "Please write a summary before closing.")
    waiting = [r for r in confirmers(rec["type"]) if r not in {c["role"] for c in rec["closure"].get("confirmed") or []}]
    if waiting:
        raise Refused(409, f"Waiting for the {waiting[0]}.")
    nxt = body.get("next") or []
    if not isinstance(nxt, list) or any(not isinstance(n, dict) or n.get("kind") not in NEXT_KINDS or not str(n.get("reason") or "").strip()
                                        for n in nxt):
        raise Refused(400, "Every next step needs a kind and a reason.")
    text = {k: str(body.get(k) or "").strip() for k in ("why_it_happened", "what_came_out")}
    rec["closure"].update(closed_by=by, closed_at=now, summary=summary.strip(), **text, signed=True, draft_by=by, cancel_reason=None,
                          next=[{"kind": n["kind"], "ref": n.get("ref"), "reason": str(n["reason"]).strip()} for n in nxt])
    for s in rec["stages"]:
        if s["state"] != "closed":
            s.update(state="closed", closed_at=now)
    rec["state"] = "closed"
    _hist(rec, by, "closing", "closed", now)


def cancel(rec: dict, by: str, reason: str, now: str) -> None:
    """Any live state to cancelled, reason required, content kept. A person, never North."""
    if rec["state"] in ("closed", "cancelled") or by == "north":
        raise Refused(409, ILLEGAL)
    _organiser(rec, by)
    if not isinstance(reason, str) or not reason.strip():
        raise Refused(400, "Please say why this intent is cancelled.")
    frm = rec["state"]
    rec["closure"] = {**(rec.get("closure") or blank_closure()), "cancel_reason": reason.strip(), "closed_by": by, "closed_at": now,
                      "signed": False}
    rec["state"] = "cancelled"
    _hist(rec, by, frm, "cancelled", now, reason.strip())
