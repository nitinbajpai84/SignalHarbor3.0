"""The time box and stage clock (spec 07). Working days are Monday to Friday, counted in UTC (ruling 22); the screen shows the
company's time zone from `profile.company.time_zone`, else UTC. Clock states are derived from the dates and never stored.

`working_days(start, days)` is the one sum other cards use: the end after `days` working days, at the start's time of day.
"""
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, _viewer
from sh_platform.intents import access, events, lifecycle, store
from sh_platform.profile import store as profile_store

router = APIRouter()

DAY = 86400
HALF, RISK = 50.0, 20.0          # percent left: amber at or below the first, red at or below the second (spec 07, open question 1)
HOURS_UNDER = 2 * DAY            # under two working days the clock speaks in hours
DAY_CHOICES = (1, 2, 3, 5)       # open question 2
REASON_MIN, REASON_MAX = 10, 300
STAGE_NAMES = {"wall": "Think unfiltered", "define": "Define strategically", "build_ready": "Build-ready"}
CLOSED = ("closed", "cancelled")


# ---- working-day arithmetic (pure) -------------------------------------------------------------------------------------------

def parse(text: str) -> datetime:
    d = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def working_days(start: datetime, days: int, tz=timezone.utc) -> datetime:
    """`start` plus `days` working days (Monday to Friday), at the same time of day. A start on a weekend counts from the next Monday.
    The count is lifecycle.add_working_days, so the time box and the clock never disagree."""
    return lifecycle.add_working_days(start, days, tz)


def working_seconds(a: datetime, b: datetime) -> float:
    """Working time (Monday to Friday, 24 hours a day) between a and b; zero when b is not after a."""
    if b <= a:
        return 0.0
    total, day = 0.0, a.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < b:
        nxt = day + timedelta(days=1)
        if day.weekday() < 5:
            total += (min(b, nxt) - max(a, day)).total_seconds()
        day = nxt
    return total


def working_days_between(a: datetime, b: datetime) -> float:
    return working_seconds(a, b) / DAY


def _n(n: int, one: str) -> str:
    return f"{n} {one}" if n == 1 else f"{n} {one}s"


def overdue_words(hours: int) -> str:
    """The one sentence for a clock that has run out, on every screen: "Overdue by 20 hours", "Overdue by 1 working day"."""
    return f"Overdue by {_n(hours // 24, 'working day')}" if hours >= 24 else f"Overdue by {_n(max(1, hours), 'hour')}"


def days_words(days: int) -> str:
    """Whole working days to the end (negative when over), for screens that count dates: "3 days left", "Overdue by 2 working days"."""
    return f"{_n(days, 'day')} left" if days > 0 else overdue_words(-days * 24)


def left_words(c: dict) -> str:
    """Words for one clock() part: "6 hours left", "3 days left" or overdue_words."""
    if c["state"] == "overdue":
        return overdue_words(-c["hours_left"])
    return f"{_n(c['hours_left'], 'hour')} left" if c["unit"] == "hours" else f"{_n(c['working_days_left'], 'day')} left"


def ends_words(when: str, over: bool) -> str:
    """"Closes Fri 17:00", and in the past tense once it is over: "Ended Tue 10:00"."""
    return f"{'Ended' if over else 'Closes'} {when}"


def clock(starts: datetime, ends: datetime, now: datetime, extensions: int = 0) -> dict:
    """One clock: the whole box or one stage. `percent_left` is of the current box (extensions included, open question 8)."""
    total = working_seconds(starts, ends)
    left = working_seconds(max(now, starts), ends) if now < ends else -working_seconds(ends, now)
    pct = max(0.0, min(100.0, left / total * 100)) if total else 0.0
    state = "not_started" if now < starts else "overdue" if left <= 0 else "at_risk" if pct <= RISK else "at_half" if pct <= HALF else "on_time"
    days_total = round(total / DAY)
    out = {
        "starts": starts.isoformat(), "ends": ends.isoformat(), "working_days_total": days_total,
        "working_days_left": max(0, math.ceil(left / DAY)), "hours_left": math.ceil(left / 3600) if left > 0 else -max(1, math.ceil(-left / 3600)),
        "percent_left": round(pct, 1), "state": state, "extensions": extensions,
        "day_of": min(days_total, int(working_seconds(starts, max(now, starts)) // DAY) + 1) if days_total else 0,
        "unit": "hours" if 0 < left < HOURS_UNDER else "days",
    }
    out["words"] = left_words(out)
    return out


# ---- the record ----------------------------------------------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _intent_path(plane, intent_id: str):
    if not intent_id.isalnum():
        raise LookupError
    return plane.path("intents", intent_id, "intent.json")


def _tz(plane) -> str:
    try:
        name = ((profile_store.load(plane).get("company") or {}).get("time_zone") or {}).get("value")
        ZoneInfo(str(name))
        return str(name)
    except (OSError, ValueError, KeyError, TypeError):
        return "UTC"


def _is(ref, who: dict) -> bool:
    """Whether a people slot names this viewer: an account id, email or name, or the record's {account_id, name}."""
    if isinstance(ref, dict):
        return ref.get("account_id") == who["id"] if ref.get("account_id") else _is(ref.get("name"), who)
    return isinstance(ref, str) and ref.strip().lower() in who["keys"]


def _who(request: Request) -> dict:
    st, v = request.app.state, _viewer(request)
    acct = st.account_store.get(request.state.account_id) or {}
    return {"id": request.state.account_id, "name": v.name, "roles": set(request.state.roles or []),
            "keys": {k for k in (request.state.account_id, str(acct.get("email") or "").lower(), v.name.strip().lower()) if k}}


def _name_of(request: Request, ref) -> str:
    if isinstance(ref, dict):
        return str(ref.get("name") or "")
    acct = request.app.state.account_store.get(ref) if isinstance(ref, str) else None
    return str((acct or {}).get("display_name") or ref or "")


def _relation(rec: dict, who: dict) -> dict:
    p = rec.get("people") or {}
    is_org, is_spon = _is(p.get("organiser"), who), _is(p.get("sponsor"), who)
    readers = [*(p.get("participants") or []), *(p.get("observers") or [])]
    return {"organiser": is_org, "sponsor": is_spon, "reader": is_org or is_spon or any(_is(r, who) for r in readers),
            "affected": any(_is(r, who) for r in p.get("affected") or [])}


def _due(rec: dict, s: dict) -> datetime | None:
    """The stage's due: the written one, else the catalogue's default days from when it opened, never past the box end."""
    if rec.get("type") == "decision" and (rec.get("time_box") or {}).get("ends"):  # a Decision has one deadline: the box end, on every screen
        return parse(rec["time_box"]["ends"])
    if s.get("due"):
        return parse(s["due"])
    try:
        days = next(x["default_days"] for x in lifecycle.type_def(rec["type"])["stages"] if x["key"] == s.get("key"))
        return min(working_days(parse(s["opened_at"]), int(days)), parse(rec["time_box"]["ends"]))
    except (KeyError, StopIteration, TypeError, ValueError):
        return None


def _stage_rows(rec: dict, now: datetime) -> tuple[list[dict], dict | None]:
    stages, current = [], None
    for s in rec.get("stages") or []:
        status = "done" if s.get("closed_at") else "current" if s.get("opened_at") and current is None else "later"
        row = {"key": s.get("key"), "name": STAGE_NAMES.get(s.get("key"), str(s.get("key") or "").replace("_", " ").capitalize()),
               "status": status, "due": (lambda d: d.isoformat() if d else None)(_due(rec, s)) if s.get("opened_at") else s.get("due")}
        d = _due(rec, s) if s.get("opened_at") else None
        row["days"] = round(working_days_between(parse(s["opened_at"]), d)) if d else None  # the wall card's "(n working days)" comes from the dates
        stages.append(row)
        current = current or (s if status == "current" else None)
    return stages, current


def ended_part(rec: dict, tb: dict, now: datetime, zone) -> dict:
    """The clock of a closed or cancelled intent (spec 07: the state is derived, closed is done): "Closed Fri 9 Oct", no days left.
    The date is the closure's, never after now; else the last stage closed; else the box end."""
    stamps = [(rec.get("closure") or {}).get("closed_at"), *[s.get("closed_at") for s in reversed(rec.get("stages") or [])], tb.get("ends")]
    day = parse(next(x for x in stamps if x))
    day = min(day, now).astimezone(zone)
    total = round(working_seconds(parse(tb["starts"]), parse(tb["ends"])) / DAY)
    state = rec["state"]
    return {"starts": tb["starts"], "ends": day.isoformat(), "working_days_total": total, "working_days_left": 0, "hours_left": 0, "percent_left": 0.0,
            "state": state, "extensions": 0, "day_of": total, "unit": "days", "words": f"{state.capitalize()} {day:%a} {day.day} {day:%b}"}


def _extensions(rec: dict) -> list[dict]:
    return (rec.get("time_box") or {}).get("extended_by") or []


def _st(e: dict) -> str:
    return e.get("status") or "approved"  # an entry written before this card had no status and took effect at once


class _Names:
    """A legacy extension entry holds an account id in `by`; show the person's name."""
    def __init__(self, request: Request):
        self.request = request

    def get(self, ref, default=None):
        return _name_of(self.request, ref) if isinstance(ref, str) else default


def _view_ext(e: dict, n: int, show_reason: bool, names: "_Names | None" = None) -> dict:
    out = {k: e.get(k) for k in ("by", "at", "days", "scope", "was", "decided_by", "decided_at")}
    out["by"] = (names or {}).get(out["by"], out["by"])
    return {"n": n, **out, "status": _st(e), "reason": e.get("reason") if show_reason else None}


def _time_card(request: Request, rec: dict, plane, box: dict | None, now: datetime, may_act: bool) -> dict | None:
    """North's time card (spec 07, screen C): once the box is at risk or over, for the organiser and sponsor. One sentence, read
    from the clock; who picks; when the sponsor (else the company admin) is asked, one working day after the end."""
    if not box or not may_act or box["state"] not in ("at_risk", "overdue") or rec.get("state") in (*CLOSED, "draft"):
        return None
    people = rec.get("people") or {}
    org, spon = _name_of(request, people.get("organiser")) or "The organiser", people.get("sponsor")
    zone = _zone(plane)
    ask = working_days(max(parse(box["ends"]), now), 1, zone).astimezone(zone)
    line = ("Time is up. " if box["state"] == "overdue" else f"Day {box['day_of']} of {box['working_days_total']}. ") + box["words"] + "."
    return {"line": line, "organiser": org,
            "who_picks": f"{org} picks. If {org} does not pick by {ask:%a} {ask.day} {ask:%b}, {_name_of(request, spon) if spon else 'the company admin'} is asked."}


def _zone(plane):
    try:
        return ZoneInfo(_tz(plane))
    except ValueError:
        return timezone.utc


def build(request: Request, rec: dict, plane, now: datetime | None = None) -> dict:
    now, who = now or _now(), _who(request)
    names = _Names(request)
    rel, tb = _relation(rec, who), rec.get("time_box") or {}
    approved = [e for e in _extensions(rec) if _st(e) == "approved"]
    stages, current = _stage_rows(rec, now)
    box = clock(parse(tb["starts"]), parse(tb["ends"]), now, len(approved)) if tb.get("starts") and tb.get("ends") else None
    stage = None
    due = _due(rec, current) if box and current else None
    if due:
        stage = clock(parse(current["opened_at"]), min(due, parse(tb["ends"])), now, 0)  # a stage never ends after the box
    if rec.get("state") == "closing" and box:  # spec 09: a closing intent reads "Closing" with its window, no stage clock, never "Not started"
        end = parse(box["ends"]).astimezone(_zone(plane))
        box, stage = {**box, "state": "closing", "words": f"Closing, {'ended' if box['state'] == 'overdue' else 'ends'} {end:%a} {end.day} {end:%b}"}, None
    if rec.get("state") in CLOSED and tb.get("starts") and (tb.get("ends") or tb.get("starts")):
        box, stage = ended_part(rec, {**tb, "ends": tb.get("ends") or tb["starts"]}, now, _zone(plane)), None
    show = rel["reader"] or (rel["affected"] and bool(rec.get("affected_may_read"))) or _tier(request, plane, rec) == "content"
    sponsor = (rec.get("people") or {}).get("sponsor")
    open_ = rec.get("state") not in (*CLOSED, "draft")
    needs = bool(approved or any(_st(e) == "pending" for e in _extensions(rec)))
    approver_ok = rel["sponsor"] or (not sponsor and "company_admin" in who["roles"])
    pend = next((_view_ext(e, n, show, names) for n, e in enumerate(_extensions(rec)) if _st(e) == "pending"), None)
    can_extend = open_ and (rel["organiser"] or rel["sponsor"]) and pend is None
    return {
        "id": rec.get("id"), "state": rec.get("state"), "tz": _tz(plane), "started": bool(box), "box": box, "stage": stage, "stages": stages,
        "extensions": {"count": len(approved), "show_reason": show, "list": [_view_ext(e, n, show, names) for n, e in enumerate(_extensions(rec))
                                                                                if _st(e) != "pending"],
                       "latest": next((_view_ext(e, n, show, names) for n, e in reversed(list(enumerate(_extensions(rec)))) if _st(e) == "approved"), None)},
        "pending": pend, "can_extend": can_extend, "may_act": rel["organiser"] or rel["sponsor"], "is_organiser": rel["organiser"], "can_decide": bool(pend and approver_ok and open_),
        "approval": {"needed": needs and not rel["sponsor"],
                     "approver": (_name_of(request, sponsor) + " (sponsor)") if sponsor else "the company admin"},
        "time_card": _time_card(request, rec, plane, box, now, rel["organiser"] or rel["sponsor"]),
        "single_stage": len(stages) <= 1, "day_choices": list(DAY_CHOICES), "reason_min": REASON_MIN, "reason_max": REASON_MAX,
    }


def _tier(request: Request, plane, rec: dict) -> str | None:
    """R1: the one decider (north.tier: visibility's matrix with people named in the intent's records and share rows). Spec 07: everyone
    who may know the intent exists sees its stage bar and clock (area members included); only the reasons for extensions need the content.
    The super admin never (R6)."""
    viewer = _viewer(request)
    if "super_admin" in (getattr(viewer, "roles", None) or ()):
        return None
    from sh_platform.intents import north
    t = north.tier(plane, rec, viewer)
    if t is None and (access.roles_of(rec, access.Me.of(request, plane)) or north.seat_of(plane, rec, viewer) is not None):
        return "card"
    return t


def _load(request: Request, intent_id: str):
    """The plane and the record; None when there is none or the viewer may not see it."""
    plane = _plane(request)
    try:
        rec = store.read_intent(plane, intent_id)
    except store.Unreadable:
        rec = None
    return plane, (rec if rec is not None and _tier(request, plane, rec) is not None else None)


def _log(plane, intent_id: str, rec: dict, who: dict, kind: str, detail: dict, stage: str | None = None) -> None:
    """One line in events.jsonl through the one writer; the caller writes `rec` after, so the counter is copied into it (define.py, brainstorm.py)."""
    person = {"account": who["id"], "name": who["name"], "role": "organiser"}
    events.point_rec(rec, events.try_append(plane, intent_id, kind, person, None, detail, "act", stage=stage))


def _fail(status: int, message: str) -> JSONResponse:
    return JSONResponse({"message": message}, status_code=status)


NOT_FOUND = "We could not find that intent."


def _apply(rec: dict, e: dict) -> None:
    """An approved extension moves the dates: the whole box (and the current stage with it, never past the new end) or the stage alone."""
    tb = rec["time_box"]
    cur = next((s for s in rec.get("stages") or [] if s.get("opened_at") and not s.get("closed_at") and _due(rec, s)), None)
    e["was"] = tb["ends"]
    if e["scope"] == "intent":
        tb["ends"] = working_days(parse(tb["ends"]), e["days"]).isoformat()
    if cur:
        cur["due"] = min(working_days(_due(rec, cur), e["days"]), parse(tb["ends"])).isoformat()


def extend(request: Request, intent_id: str, body: dict, now: datetime | None = None):
    """The organiser extends once alone; a later extension waits for the sponsor (the company admin when there is none)."""
    now = now or _now()
    plane, rec = _load(request, intent_id)
    if rec is None:
        return _fail(404, NOT_FOUND)
    who = _who(request)
    rel = _relation(rec, who)
    if not (rel["organiser"] or rel["sponsor"]):
        return JSONResponse({"message": "Only the organiser or the sponsor can extend."}, status_code=403)
    if rec.get("state") in (*CLOSED, "draft") or not (rec.get("time_box") or {}).get("ends"):
        return _fail(409, "Nothing to extend. The intent is closed.")
    days, reason, scope = body.get("days"), str(body.get("reason") or "").strip(), body.get("scope") or "intent"
    if days not in DAY_CHOICES or isinstance(days, bool):
        return _fail(422, "Choose 1, 2, 3 or 5 working days.")
    if not REASON_MIN <= len(reason) <= REASON_MAX:
        return _fail(422, "A reason is needed." if not reason else f"The reason needs {REASON_MIN} to {REASON_MAX} characters.")
    if scope not in ("stage", "intent"):
        return _fail(422, "Choose this stage only or the whole intent.")
    out = {}

    def change(r: dict) -> None:
        exts = r["time_box"].setdefault("extended_by", [])
        if any(_st(x) == "pending" for x in exts):
            raise ValueError("An extension is already waiting for approval.")
        if scope == "stage":
            _, cur = _stage_rows(r, now)
            if not cur or not _due(r, cur):
                raise ValueError("This intent has no stage clock to extend.")
            if working_days(_due(r, cur), days) > parse(r["time_box"]["ends"]):
                raise ValueError("The stage would end after the intent. Extend the whole intent.")
        direct = not any(_st(x) == "approved" for x in exts) or rel["sponsor"]
        e = {"by": who["name"], "at": now.isoformat(), "reason": reason, "days": days, "scope": scope, "was": r["time_box"]["ends"],
             "status": "approved" if direct else "pending", "decided_by": who["name"] if direct else None, "decided_at": now.isoformat() if direct else None}
        exts.append(e)
        if direct:
            _apply(r, e)
        out.update(e=e, n=len(exts) - 1, direct=direct, end=r["time_box"]["ends"])

    try:
        rec = store.update_intent(plane, intent_id, rec["version"], change)
    except store.VersionConflict:
        return _fail(409, store.CONFLICT)
    except ValueError as err:
        return _fail(409 if "waiting" in str(err) else 422, str(err))
    if out["direct"]:
        events.try_append(plane, intent_id, "extended", {"account": who["id"], "name": who["name"], "role": ""}, {"store": "time_box", "id": str(out["n"])},
                          {"old_end": out["e"]["was"][:10], "new_end": out["end"][:10]}, "act")
    return {"extended": out["direct"], "pending": not out["direct"], "clock": build(request, rec, plane, now)}


def decide(request: Request, intent_id: str, n: int, body: dict, now: datetime | None = None):
    now = now or _now()
    plane, rec = _load(request, intent_id)
    if rec is None:
        return _fail(404, NOT_FOUND)
    who, decision = _who(request), body.get("decision")
    sponsor = (rec.get("people") or {}).get("sponsor")
    if not (_is(sponsor, who) or (not sponsor and "company_admin" in who["roles"])):
        return JSONResponse({"message": "Only the approver can decide this."}, status_code=403)
    if decision not in ("approve", "decline"):
        return _fail(422, "Choose approve or decline.")
    out = {}

    def change(r: dict) -> None:
        exts = (r.get("time_box") or {}).get("extended_by") or []
        if not 0 <= n < len(exts) or _st(exts[n]) != "pending" or r.get("state") in CLOSED:
            raise ValueError("That request is no longer waiting.")
        e = exts[n]
        e.update(status="approved" if decision == "approve" else "declined", decided_by=who["name"], decided_at=now.isoformat())
        if decision == "approve":
            _apply(r, e)
        out.update(e=e, end=r["time_box"]["ends"])

    try:
        rec = store.update_intent(plane, intent_id, rec["version"], change)
    except store.VersionConflict:
        return _fail(409, store.CONFLICT)
    except ValueError as err:
        return _fail(409, str(err))
    if decision == "approve":
        events.try_append(plane, intent_id, "extended", {"account": who["id"], "name": who["name"], "role": ""}, {"store": "time_box", "id": str(n)},
                          {"old_end": out["e"]["was"][:10], "new_end": out["end"][:10]}, "act")
    return {"decided": decision, "clock": build(request, rec, plane, now)}


# ---- routes --------------------------------------------------------------------------------------------------------------------

@router.get("/api/intents/{intent_id}/clock")
def get_clock(intent_id: str, request: Request):
    plane, rec = _load(request, intent_id)
    if rec is None:
        return _fail(404, NOT_FOUND)
    return build(request, rec, plane)


@router.post("/api/intents/{intent_id}/time-box/extend")
def post_extend(intent_id: str, body: dict, request: Request):
    return extend(request, intent_id, body)


@router.post("/api/intents/{intent_id}/extend/{n}/decide")
def post_decide(intent_id: str, n: int, body: dict, request: Request):
    return decide(request, intent_id, n, body)
