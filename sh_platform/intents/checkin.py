"""The Weekly check-in (specs 38 and 39; the record key stays `pulse`): the series, its week files and the reporter's entry.

One intent record carries the series; each week is a file `intents/<id>/weeks/<week_key>.json` (rulings 3 and 17). A due week is
opened by `tick`, the first time the series is read after `series.next_week_opens`, under the intent lock (no scheduler exists).
Other cards import `read_week`, `list_weeks` and `tick`. The review routes (spec 40) live in `checkin_review.py` when it exists.
Anonymous items carry no author: the item holds `by: null`, and only the author's own file `profile/<account>/pulse_mine.json` points at it.
"""
import importlib
import importlib.util
import json
import logging
import secrets
import statistics
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.build import alerts as store_alerts
from sh_platform.build import ops
from sh_platform.consume import feeds
from sh_platform.intents import _plane, _viewer, events, lifecycle as L, not_yet, people, store as S
from sh_platform.jsonfile import read_json_strict, write_json_atomic
from sh_platform.profile import areas as parea, store as pstore, view as pview

log = logging.getLogger(__name__)
router = APIRouter()

DAYS = ("mon", "tue", "wed", "thu", "fri")
KINDS = ("ran", "broke", "thought")
SEVERITY = ("slowed", "stopped", "cost")
UNITS = ("times", "hours")
ORDER = ("collect", "review", "sort", "closing", "closed")
MIN_REPORTERS, TEXT_MAX, EXTRA_MAX, GAP_CAP = 2, 600, 240, 60  # spec 38 open question 2 (proposed values); spec 39 question 2 (60 seconds)
NOT_FOUND = "We could not find that."
PURPOSE = "Every week the people of one area say what ran, what broke and what is on their mind."


class Refuse(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _run(fn):
    try:
        return fn()
    except Refuse as e:  # the client words a 403 only when it carries this code
        return JSONResponse({"message": e.message, **({"error": "not_allowed"} if e.status == 403 else {})}, status_code=e.status)
    except L.Refused as e:
        return JSONResponse({"message": e.message}, status_code=e.status)
    except S.VersionConflict:
        return JSONResponse({"message": S.CONFLICT}, status_code=409)
    except S.Unreadable:
        return JSONResponse({"message": S.UNREADABLE}, status_code=500)
    except PermissionError:
        return JSONResponse({"message": "Your company space could not be opened. Please ask your administrator."}, status_code=403)


# ---- dates: Monday to Friday, no holidays (ruling 22) ---------------------------------------------------------------------

def add_wd(d: date, n: int) -> date:
    step = 1 if n > 0 else -1
    while n:
        d += timedelta(days=step)
        if d.weekday() < 5:
            n -= step
    return d


def on_or_after(d: date) -> date:
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d


def _between(a: date, b: date) -> int:
    n = 0
    while a < b:
        a += timedelta(days=1)
        n += a.weekday() < 5
    return n


def week_dates(start: date, close_day: str) -> dict:
    """Opens on `start` (or the next Monday); closes on the first `close_day` at least two working days later. Answers close two working
    days before that, review is the day before it, sorting runs to the close day (the stage lengths of the catalogue: 3, 1, 1)."""
    opens, idx = on_or_after(start), DAYS.index(close_day)
    closes = opens
    while not (closes.weekday() == idx and _between(opens, closes) >= 2):
        closes += timedelta(days=1)
    answers = max(opens, add_wd(closes, -2))
    return {"opens": opens, "answers_close": answers, "review_day": max(answers, add_wd(closes, -1)), "closes": closes}


def week_key(opens: date) -> str:
    iso = opens.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _today(plane, now: datetime) -> date:
    return now.astimezone(L.company_zone(plane)).date()


def _stamp(d: date, end: bool, plane) -> str:
    return datetime.combine(d, time(23, 59, 59) if end else time(0), tzinfo=L.company_zone(plane)).isoformat()


def _state_on(w: dict, today: date) -> str:
    d = {k: date.fromisoformat(w[k]) for k in ("answers_close", "review_day", "closes")}
    return "closing" if today > d["closes"] else "sort" if today > d["review_day"] else "review" if today > d["answers_close"] else "collect"


# ---- week files -----------------------------------------------------------------------------------------------------------

def _wfile(plane, intent_id: str, key: str):
    return plane.path("intents", intent_id, "weeks", f"{key}.json")


def read_week(plane, intent_id: str, key: str) -> dict | None:
    """One week file, or None. A damaged file raises S.Unreadable and is never overwritten."""
    if not isinstance(key, str) or len(key) != 8 or key[4:6] != "-W":
        return None
    try:
        return read_json_strict(_wfile(plane, intent_id, key), dict)
    except (OSError, ValueError):
        raise S.Unreadable(key) from None


def write_week(plane, intent_id: str, w: dict) -> None:
    write_json_atomic(_wfile(plane, intent_id, w["week_key"]), w)


def list_weeks(plane, intent_id: str) -> list[dict]:
    """Every week file of the series, oldest first."""
    folder = plane.path("intents", intent_id, "weeks")
    keys = sorted(p.stem for p in folder.glob("*.json")) if folder.is_dir() else []
    return [w for k in keys if (w := read_week(plane, intent_id, k))]


def _event(plane, rec: dict, kind: str, by: dict | None, detail: dict | None = None) -> None:
    """One line in events.jsonl through the one writer (spec 16): keys, enums and numbers only, never words. No person means North's clock made it."""
    detail = detail or {}
    e = events.try_append(plane, rec["id"], kind, by or "north", None, detail if by else {**detail, "by_clock": True}, "act", stage="running")
    events.point_rec(rec, e)


def _who(v: pview.Viewer, role: str) -> dict:
    return {"account": v.account_id, "name": v.name, "role": role}


def _prompts(s: dict) -> list[dict]:
    base = [{"kind": p["kind"], "lead": p["lead"]} for p in L.type_def("pulse")["weekly_prompts"]]
    return base + ([{"kind": "thought", "lead": s["extra_prompt"], "extra": True}] if s.get("extra_prompt") else [])


def _open_week(plane, rec: dict, today: date) -> None:
    """Write the week due on `series.next_week_opens` (the latest due one if the series was not read for weeks), under the lock."""
    s = rec["series"]
    opens = date.fromisoformat(s["next_week_opens"])
    while True:
        d = week_dates(opens, s["close_day"])
        nxt = add_wd(d["closes"], 1)
        if nxt > today:
            break
        opens = nxt
    key = week_key(d["opens"])
    if read_week(plane, rec["id"], key) is None:
        write_week(plane, rec["id"], {
            "week_key": key, "opens": d["opens"].isoformat(), "closes": d["closes"].isoformat(), "answers_close": d["answers_close"].isoformat(),
            "review_day": d["review_day"].isoformat(), "state": "collect", "people": [dict(p) for p in rec["people"]["participants"]],
            "prompts": _prompts(s), "items": [], "submissions": [], "review": {}, "stage_closed_at": None, "closed_at": None})
        _event(plane, rec, "week_opened", None, {"week_key": key})
    if key not in s["weeks"]:
        s["weeks"].append(key)
    s.update(current_week=key, next_week_opens=nxt.isoformat())
    rec["time_box"].update(starts=_stamp(d["opens"], False, plane), ends=_stamp(d["closes"], True, plane))


def tick(plane, intent_id: str, now: datetime | None = None) -> dict | None:
    """The clock. Moves the last weeks forward by date, and opens the week due next. Returns the (fresh) record, or None."""
    now = now or datetime.now(timezone.utc)
    with S.locked(plane):
        rec = S.read_intent(plane, intent_id)
        s = rec and rec["type"] == "pulse" and rec["state"] in ("open", "closing") and rec.get("series")
        if not s:
            return rec
        today, changed = _today(plane, now), False
        for key in s["weeks"][-3:]:
            w = read_week(plane, intent_id, key)
            to = _state_on(w, today) if w else None
            if w and w["state"] != "closed" and ORDER.index(to) > ORDER.index(w["state"]):
                w.update(state=to, stage_closed_at=now.isoformat())
                write_week(plane, intent_id, w)
        if rec["state"] == "open" and s["status"] == "running" and s.get("next_week_opens") and today >= date.fromisoformat(s["next_week_opens"]):
            _open_week(plane, rec, today)  # ponytail: one week even after a long gap; a skipped week never existed
            changed = True
        return S.write_intent(plane, rec) if changed else rec


# ---- who is who -----------------------------------------------------------------------------------------------------------

def _me(v: pview.Viewer) -> dict:
    return {"account_id": v.account_id, "name": v.name}


def _is_org(rec: dict, v: pview.Viewer) -> bool:
    return bool(v.account_id) and (rec["people"].get("organiser") or {}).get("account_id") == v.account_id


def _is_reviewer(rec: dict, v: pview.Viewer) -> bool:
    return _is_org(rec, v) or (bool(v.account_id) and (rec.get("series") or {}).get("reviewer") == v.account_id)


def _ctx(request: Request, intent_id: str, *, content: bool = True):
    plane, v = _plane(request), _viewer(request)
    rec = S.read_intent(plane, intent_id)
    tier = rec and rec["type"] == "pulse" and S.tier_of(rec, v, S.areas_of(plane, v))
    if not tier:
        raise Refuse(404, NOT_FOUND)
    if content and tier != "content":
        raise Refuse(403, "You are not part of this check-in.")
    return plane, v, rec


def _need_week(plane, rec: dict, key: str | None) -> dict:
    key = key or (rec.get("series") or {}).get("current_week")
    w = read_week(plane, rec["id"], key) if key else None
    if w is None:
        raise Refuse(404, "No week is open yet." if not key else NOT_FOUND)
    return w


def _in_week(w: dict, v: pview.Viewer) -> bool:
    return bool(v.account_id) and any(p.get("account_id") == v.account_id for p in w["people"])


def _sub(w: dict, v: pview.Viewer) -> dict | None:
    return next((x for x in w["submissions"] if x["by"] == v.account_id), None)


def _can_edit(w: dict, now: datetime, plane) -> bool:
    return w["state"] == "collect" and _today(plane, now) >= date.fromisoformat(w["opens"])


# ---- the person's own pointer file (anonymous items) -------------------------------------------------------------------------

def _mine_file(plane, acct: str):
    return plane.path("profile", acct, "pulse_mine.json")


def _pointers(plane, acct: str) -> list[dict]:
    try:
        return list((read_json_strict(_mine_file(plane, acct), dict) or {}).get("items") or [])
    except (OSError, ValueError):
        return []


def _point(plane, acct: str, intent_id: str, key: str, item_id: str, present: bool) -> None:
    rows = [r for r in _pointers(plane, acct) if r.get("item_id") != item_id]
    write_json_atomic(_mine_file(plane, acct), {"items": rows + ([{"intent": intent_id, "week_key": key, "item_id": item_id}] if present else [])})


def _own_items(plane, rec: dict, w: dict, v: pview.Viewer) -> list[dict]:
    ids = {r["item_id"] for r in _pointers(plane, v.account_id) if r.get("intent") == rec["id"] and r.get("week_key") == w["week_key"]}
    return [i for i in w["items"] if i["id"] in ids or (not i["anonymous"] and i["by"] == v.account_id)]


# ---- North's prefill (spec 39): owned runs and alerts, marked guessed ---------------------------------------------------------

def _day(text) -> date | None:
    return ops._day(text)


def _span(a: date, b: date) -> str:
    one = lambda d: f"{d.day} {d.strftime('%b')}"  # noqa: E731
    return one(a) if a == b else f"{a.day} to {one(b)}" if (a.month, a.year) == (b.month, b.year) else f"{one(a)} to {one(b)}"


def _title(plane, source: str) -> str:
    t = (ops._load(plane.path("build", "pipelines", f"{source}.json"), {}) or {}).get("title")
    return str(t) if t else source.replace("_", " ").capitalize()


ALERT_WORDS = {"late": "arrived late", "failed": "failed its checks", "outside_range": "went outside its usual range"}


def drafts_for(plane, w: dict, v: pview.Viewer) -> list[dict]:
    """North's drafts for this person: counts and ids only, never rows. Matched by the owner's name (spec 39 open question 7)."""
    if v.shared_name:
        return []
    mine = lambda o: bool(o) and pview.norm(o) == pview.norm(v.name)  # noqa: E731
    runs = [r for r in ops._load(plane.path("warehouse", "runs.json"), {}).get("runs") or [] if mine(r.get("owner")) and _day(r.get("started"))]
    lo, hi = date.fromisoformat(w["opens"]), date.fromisoformat(w["closes"])
    inside = [r for r in runs if lo <= _day(r["started"]) <= hi]
    if not inside and runs:  # nothing in this week: the latest week the person has runs in, with its real dates on the evidence line
        hi = max(_day(r["started"]) for r in runs)
        lo = hi - timedelta(days=6)
        inside = [r for r in runs if lo <= _day(r["started"]) <= hi]
    out = []
    for src in dict.fromkeys(r["source"] for r in inside):
        rs = [r for r in inside if r["source"] == src]
        if not any(r.get("status") == "ok" for r in rs):
            continue
        days = [_day(r["started"]) for r in rs]
        out.append({"id": f"run:{src}", "kind": "ran", "text": f"{_title(plane, src)}: {sum(bool(r.get('on_time')) for r in rs)} of {len(rs)} {'load' if len(rs) == 1 else 'loads'} on time",
                    "evidence": f"From {len(rs)} {'run' if len(rs) == 1 else 'runs'}, {_span(min(days), max(days))}", "label": "Guessed by North, from this week's run log",
                    "from": [{"record": f"warehouse/runs.json#{r['id']}", "at": r["started"]} for r in rs]})
    for a in store_alerts._read(plane):
        at = _day(a.get("at")) if a.get("at") else None
        if not mine(a.get("owner")) or a.get("kind") not in ALERT_WORDS or (a.get("state") == "closed" and not (at and lo <= at <= hi)):
            continue
        tail = f", closed on {at.strftime('%A')}" if a.get("state") == "closed" and at else ""
        out.append({"id": f"alert:{a['id']}", "kind": "broke", "text": f"{_title(plane, a.get('source') or '')}: {ALERT_WORDS[a['kind']]}{tail}",
                    "evidence": f"Alert opened {a.get('opened') or 'on a day not recorded'}", "label": "Guessed by North, from your alerts",
                    "from": [{"record": f"build/alerts.json#{a['id']}", "at": a.get("opened")}]})
    return out


def _open_drafts(plane, w: dict, v: pview.Viewer, sub: dict | None) -> list[dict]:
    gone = set((sub or {}).get("kept", [])) | set((sub or {}).get("dropped", []))
    return [d for d in drafts_for(plane, w, v) if d["id"] not in gone]


# ---- item operations ------------------------------------------------------------------------------------------------------

def _text(body: dict, field: str = "text") -> str:
    t = " ".join(str(body.get(field) or "").split())
    if not t:
        raise Refuse(422, "Write a line first.")
    if len(t) > TEXT_MAX:
        raise Refuse(422, f"Keep it to {TEXT_MAX} characters.")
    return t


def _new_item(kind: str, text: str, v: pview.Viewer, *, anonymous=False, mark="stated", extra=False, prov=None) -> dict:
    return {"id": "it-" + secrets.token_hex(6), "by": None if anonymous else v.account_id, "by_name": None if anonymous else v.name,
            "anonymous": anonymous, "kind": kind, "extra": extra, "text": text, "state": "active", "mark": mark, "severity": None, "count": None,
            "unit": None, "amount": None, "ref": None, "edits": [], "unsent": False, "fate": None, "fate_reason": None, "decided_by": None,
            "provenance": prov or {"drafted_by": None, "from": [], "confirmed_by": None, "confirmed_at": None}}


def _item(w: dict, mine: list[dict], item_id) -> dict:
    it = next((i for i in mine if i["id"] == item_id and i["state"] == "active"), None)
    if it is None:
        raise Refuse(404, NOT_FOUND)
    return it


def _set_anonymous(plane, rec: dict, w: dict, it: dict, v: pview.Viewer, on: bool) -> None:
    if on == it["anonymous"]:
        return
    it.update(anonymous=on, by=None if on else v.account_id, by_name=None if on else v.name)
    if on:
        it["provenance"].update(**{"from": [], "confirmed_by": None, "confirmed_at": None})
        it["edits"] = [{"text": e["text"]} for e in it["edits"]]
    _point(plane, v.account_id, rec["id"], w["week_key"], it["id"], on)


def _fill(it: dict, body: dict, v: pview.Viewer, submitted: bool, now: datetime) -> None:
    """The card sheet's fields. Severity is the person's own call; a count or amount is only what was typed."""
    if "text" in body:
        text = _text(body)
        if text != it["text"]:
            if submitted:
                it["edits"].append({"text": it["text"], **({} if it["anonymous"] else {"at": now.isoformat()})})
            it["text"] = text
            if it["mark"] == "guessed":
                it["mark"] = "stated"
    if "severity" in body:
        sv = body["severity"]
        if sv is not None and (sv not in SEVERITY or it["kind"] != "broke"):
            raise Refuse(422, "Pick one of the three, on a line about something that broke.")
        it["severity"] = sv
    if "count" in body:
        c, u = body["count"], body.get("unit") or "times"
        if c is not None and (not isinstance(c, int) or isinstance(c, bool) or not 0 <= c <= 100000 or u not in UNITS or it["kind"] != "broke"):
            raise Refuse(422, "Give a whole number of times or hours, or leave it empty.")
        it.update(count=c, unit=u if c is not None else None)
    if "amount" in body:
        a = body["amount"]
        if a is not None:
            val, cur = (a or {}).get("value"), str((a or {}).get("currency") or "").strip().upper()
            if isinstance(val, bool) or not isinstance(val, (int, float)) or val < 0 or not 2 <= len(cur) <= 4 or it["kind"] != "broke":
                raise Refuse(422, "Give an amount and its currency, or leave it empty.")
            a = {"value": val, "currency": cur}
        it["amount"] = a
    if "ref" in body:
        r = body["ref"]
        if r is not None:
            if not isinstance(r, dict) or r.get("kind") not in ("measure", "process") or not r.get("id") or not r.get("label"):
                raise Refuse(422, "Pick a measure or a process, or clear the link.")
            r = {"kind": r["kind"], "id": str(r["id"])[:80], "label": str(r["label"])[:120], "intent": r.get("intent")}
        it["ref"] = r


def _apply(plane, rec: dict, w: dict, v: pview.Viewer, sub: dict, body: dict, now: datetime) -> None:
    op, mine, submitted = body.get("op"), _own_items(plane, rec, w, v), sub["state"] == "submitted"
    if op == "tick":  # active time: the gap since the last save, capped (spec 39 open question 2)
        sub["active_seconds"] += max(0, min(int(body.get("seconds") or 0), GAP_CAP))
    elif op == "add":
        line = body.get("kind")
        if line not in KINDS + ("extra",) or (line == "extra" and not rec["series"].get("extra_prompt") and not any(p.get("extra") for p in w["prompts"])):
            raise Refuse(422, "That line is not part of this check-in.")
        it = _new_item("thought" if line == "extra" else line, _text(body), v, anonymous=bool(body.get("anonymous")), extra=line == "extra")
        w["items"].append(it)
        sub["skipped"] = [k for k in sub["skipped"] if k != line]
        if it["anonymous"]:
            _point(plane, v.account_id, rec["id"], w["week_key"], it["id"], True)
    elif op == "update":
        it = _item(w, mine, body.get("id"))
        _fill(it, body, v, submitted, now)
        if "anonymous" in body:
            _set_anonymous(plane, rec, w, it, v, bool(body["anonymous"]))
        if "text" in body and not it["anonymous"] and it["provenance"]["drafted_by"]:
            it["provenance"].update(confirmed_by=v.name, confirmed_at=now.isoformat())
    elif op == "confirm":
        it = _item(w, mine, body.get("id"))
        it["mark"] = "stated"
        if not it["anonymous"]:
            it["provenance"].update(confirmed_by=v.name, confirmed_at=now.isoformat())
    elif op == "remove":
        it = _item(w, mine, body.get("id"))  # the words stay with the author only: the reader sees a count, never the text
        it["edits"].append({"text": it["text"]})
        it.update(state="withdrawn", text="")
    elif op in ("skip", "unskip"):
        k = body.get("kind")
        if k not in KINDS:
            raise Refuse(422, "That line is not part of this check-in.")
        sub["skipped"] = [x for x in sub["skipped"] if x != k] + ([k] if op == "skip" else [])
    elif op in ("keep_draft", "keep_all", "drop_draft"):
        open_ = _open_drafts(plane, w, v, sub)
        hit = [d for d in open_ if op == "keep_all" or d["id"] == body.get("draft_id")]
        if not hit:
            raise Refuse(404, NOT_FOUND)
        for d in hit:
            sub["dropped" if op == "drop_draft" else "kept"].append(d["id"])
            if op != "drop_draft":
                w["items"].append(_new_item(d["kind"], d["text"], v, mark="guessed", prov={"drafted_by": "north", "from": d["from"], "confirmed_by": None, "confirmed_at": None}))
                sub["skipped"] = [k for k in sub["skipped"] if k != d["kind"]]
    else:
        raise Refuse(422, "That change is not one this screen makes.")
    sub["last_saved_at"] = now.isoformat()


def _gate(plane, rec: dict, w: dict, v: pview.Viewer, now: datetime) -> dict:
    """The person's submission, made on first use. Only people on this week's list may answer, and only while answers are open."""
    if not _in_week(w, v):
        raise Refuse(403, "You are not on the list for this week's check-in.")
    if not _can_edit(w, now, plane):
        raise Refuse(409, "This week's answers have closed. Your answer can no longer be added.")
    sub = _sub(w, v)
    if sub is None:
        sub = {"by": v.account_id, "by_name": v.name, "state": "draft", "started_at": now.isoformat(), "submitted_at": None, "updated_at": None,
               "closed_at": None, "active_seconds": 0, "minutes": None, "skipped": [], "kept": [], "dropped": [], "last_saved_at": None}
        w["submissions"].append(sub)
    return sub


def _mine_view(it: dict) -> dict:
    return {k: it[k] for k in ("id", "kind", "extra", "text", "anonymous", "mark", "severity", "count", "unit", "amount", "ref", "fate", "fate_reason", "edits")}


def entry_view(plane, rec: dict, w: dict, v: pview.Viewer, now: datetime) -> dict:
    s, sub = rec["series"], _sub(w, v)
    mine = _own_items(plane, rec, w, v)
    live = [i for i in mine if i["state"] == "active"]
    can = _in_week(w, v) and _can_edit(w, now, plane)
    return {"week": {k: w[k] for k in ("week_key", "opens", "answers_close", "review_day", "closes", "state")}, "title": rec["title"],
            "area": (rec.get("areas") or [""])[0], "prompts": w["prompts"], "participant": _in_week(w, v), "can_edit": can,
            "status": (sub or {}).get("state", "none") if can or not sub else "closed", "submitted_at": (sub or {}).get("submitted_at"),
            "skipped": (sub or {}).get("skipped", []), "active_seconds": (sub or {}).get("active_seconds", 0), "minutes": (sub or {}).get("minutes"),
            "items": [_mine_view(i) | {"sent": bool((sub or {}).get("submitted_at"))} for i in live], "withdrawn": len(mine) - len(live),
            "guessed": sum(i["mark"] == "guessed" for i in live), "next_week_opens": s.get("next_week_opens"),
            "has_newer": s.get("current_week") not in (None, w["week_key"]), "series_status": s["status"]}


# ---- the entry routes (39) ------------------------------------------------------------------------------------------------

def _load_entry(request: Request, intent_id: str, week: str | None, now: datetime):
    plane, v, rec = _ctx(request, intent_id)
    rec = tick(plane, intent_id, now) or rec
    return plane, v, rec, _need_week(plane, rec, week)


@router.get("/api/intents/{intent_id}/pulse/entry")
def get_intents_by_intent_id_pulse_entry(intent_id: str, request: Request, week: str | None = None):
    def go():
        now = datetime.now(timezone.utc)
        plane, v, rec, w = _load_entry(request, intent_id, week, now)
        if not _in_week(w, v):
            raise Refuse(403, "You are not on the list for this week's check-in.")
        return {**entry_view(plane, rec, w, v, now), "measures": _measures(request, plane, v)}
    return _run(go)


def _measures(request: Request, plane, v: pview.Viewer) -> list[dict]:
    """The catalogue's measure names and codes for the link picker (spec 39), read through the feeds reader; never a value."""
    try:
        got = feeds.build(plane, v, feeds._pack_names(request))["measures"]
    except (OSError, ValueError, KeyError, LookupError, AttributeError):
        return []
    return [{"code": str(m["code"]), "name": str(m.get("name") or m["code"])} for m in got if isinstance(m, dict) and m.get("code")]


def _write_entry(request: Request, intent_id: str, week: str | None, ops_: list[dict], submit: bool, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    plane, v, rec = _ctx(request, intent_id)
    with S.locked(plane):
        rec = tick(plane, intent_id, now) or rec
        w = _need_week(plane, rec, week)
        sub = _gate(plane, rec, w, v, now)
        for body in ops_:
            _apply(plane, rec, w, v, sub, body, now)
        if submit:
            live = [i for i in _own_items(plane, rec, w, v) if i["state"] == "active"]
            if not live and not sub["skipped"]:
                raise Refuse(422, "Answer one of the three, or say nothing to add.")
            first = sub["submitted_at"] is None
            sub.update(state="submitted", submitted_at=sub["submitted_at"] or now.isoformat(), updated_at=now.isoformat(),
                       minutes=round(sub["active_seconds"] / 60, 2))
            _event(plane, rec, "entry_submitted" if first else "entry_updated", _who(v, "participant"), {"week_key": w["week_key"]})
            S.write_intent(plane, rec)
        write_week(plane, intent_id, w)
        out = entry_view(plane, rec, w, v, now)
    if submit and v.account_id:
        try:
            people.mark_contributed(plane, intent_id, v.account_id)  # the sender counts as contributed on the people view
        except Exception:  # noqa: BLE001 - the week is saved; the count catches up on the next send
            log.warning("contributed not marked on %s", intent_id, exc_info=True)
    return out


@router.put("/api/intents/{intent_id}/pulse/entry")
def put_intents_by_intent_id_pulse_entry(intent_id: str, body: dict, request: Request, week: str | None = None):
    return _run(lambda: _write_entry(request, intent_id, week, [body], False))


@router.post("/api/intents/{intent_id}/pulse/entry/submit")
def post_intents_by_intent_id_pulse_entry_submit(intent_id: str, request: Request, week: str | None = None):
    return _run(lambda: _write_entry(request, intent_id, week, [], True))


@router.post("/api/intents/{intent_id}/weeks/{week_key}/answers")
def post_intents_by_intent_id_weeks_by_week_key_answers(intent_id: str, week_key: str, body: dict, request: Request):
    """The short form of spec 38: one line per question, then send. `lines` maps ran, broke, thought, extra to text; `nothing` lists
    the kinds with nothing to say; `anonymous` lists the lines to keep the name off."""
    lines, nothing, anon = body.get("lines") or {}, body.get("nothing") or [], body.get("anonymous") or []
    steps = [{"op": "add", "kind": k, "text": t, "anonymous": k in anon} for k, t in lines.items() if str(t or "").strip()]
    steps += [{"op": "skip", "kind": k} for k in nothing if k not in lines or not str(lines[k] or "").strip()]
    return _run(lambda: _write_entry(request, intent_id, week_key, steps, True))


@router.get("/api/intents/{intent_id}/pulse/prefill")
def get_intents_by_intent_id_pulse_prefill(intent_id: str, request: Request, week: str | None = None):
    def go():
        plane, v, rec, w = _load_entry(request, intent_id, week, datetime.now(timezone.utc))
        if not _in_week(w, v):
            raise Refuse(403, "You are not on the list for this week's check-in.")
        drafts = _open_drafts(plane, w, v, _sub(w, v)) if w["state"] == "collect" else []
        return {"drafts": drafts, "count": len(drafts)}
    return _run(go)


def _week_row(w: dict, mine: list[dict]) -> dict:
    live = [i for i in mine if i["state"] == "active"]
    return {"week_key": w["week_key"], "opens": w["opens"], "closes": w["closes"], "state": w["state"],
            "counts": {k: sum(i["kind"] == k for i in live) for k in KINDS}, "became_problem": sum(i["fate"] == "problem" for i in live), "items": [
                {k: i[k] for k in ("id", "kind", "text", "anonymous", "severity", "count", "unit", "amount", "ref", "fate", "fate_reason")} for i in live]}


@router.get("/api/intents/{intent_id}/pulse/mine")
def get_intents_by_intent_id_pulse_mine(intent_id: str, request: Request):
    """Screen C: the person's own weeks of this series, their own words only."""
    def go():
        now = datetime.now(timezone.utc)
        plane, v, rec = _ctx(request, intent_id)
        rec = tick(plane, intent_id, now) or rec
        weeks = [w for w in list_weeks(plane, intent_id) if _in_week(w, v)]
        done = [w for w in weeks if (_sub(w, v) or {}).get("state") in ("submitted", "closed")]
        past = [w for w in weeks if w["state"] in ("closing", "closed")]
        mins = [m for w in reversed(done) if (m := (_sub(w, v) or {}).get("minutes")) is not None][:3]
        return {"weeks": [_week_row(w, _own_items(plane, rec, w, v)) | {"answered": w in done} for w in reversed(weeks) if _own_items(plane, rec, w, v) or w in done],
                "trend": {"answered": sum(w in done for w in weeks[-8:]), "of": len(weeks[-8:])} if len(past) >= 2 else None, "minutes": mins}
    return _run(go)


def _shown(it: dict) -> dict:
    """A week item as a reader sees it: an anonymous item carries no name and no source of a named person."""
    prov, anon = it["provenance"], it["anonymous"]
    if anon:
        how = "Stated, name hidden"
    elif it["mark"] == "guessed":
        how = "North drafted, not yet confirmed"
    elif prov["drafted_by"]:
        how = f"North drafted, {it['by_name']} {'edited' if it['edits'] else 'confirmed'}"
    else:
        how = f"Stated by {it['by_name']}"
    return {**{k: it[k] for k in ("id", "kind", "extra", "text", "mark", "severity", "count", "unit", "amount", "ref", "fate", "fate_reason")},
            "author": "Anonymous" if anon else it["by_name"], "provenance": how, "sources": [] if anon else [x["record"] for x in prov["from"]]}


@router.get("/api/intents/{intent_id}/pulse/record")
def get_intents_by_intent_id_pulse_record(intent_id: str, request: Request, week: str | None = None):
    """Screen D: the week's items with their provenance. While answers are open only the organiser and reviewer may read it."""
    def go():
        plane, v, rec, w = _load_entry(request, intent_id, week, datetime.now(timezone.utc))
        live = [i for i in w["items"] if i["state"] == "active" and not i["unsent"]]
        if w["state"] != "closed" and not _is_reviewer(rec, v):  # spec 39: until the reviewer has closed the week, a person reads only their own items
            own = {i["id"] for i in _own_items(plane, rec, w, v)}
            live = [i for i in live if i["id"] in own]
        done = [x for x in w["submissions"] if x["state"] in ("submitted", "closed")]
        mins = [x["minutes"] for x in done if x["minutes"] is not None]
        shut = w["state"] != "closed" and not _is_reviewer(rec, v)
        return {"week": {k: w[k] for k in ("week_key", "opens", "answers_close", "closes", "state")}, "answered": len(done), "of": len(w["people"]), "own_only": shut,
                "counts": {k: sum(i["kind"] == k for i in live) for k in KINDS}, "withdrawn": 0 if shut else sum(i["state"] == "withdrawn" for i in w["items"]),
                "guessed": sum(i["mark"] == "guessed" for i in live), "median_minutes": None if shut else (round(statistics.median(mins), 1) if len(mins) >= 5 else "Fewer than five") if mins else None,
                "items": [_shown(i) for i in live]}
    return _run(go)


# ---- the series: setup, settings, pause, resume, end (38) -------------------------------------------------------------------

def _vals(p: dict) -> dict:
    g = lambda k: pview._v(p, k)  # noqa: E731
    return {"id": g("account_id"), "name": g("name"), "role": g("role"), "team": g("team"), "areas": g("areas") or []}


def setup_options(plane, area: str | None) -> dict:
    """The pickers of Screen A: the company's active areas and the people of the profile, those tagged to the area first."""
    doc = pstore.load(plane)
    areas = [a for a in parea.listing(doc) if a["status"] == "active"]
    hit = next((a for a in areas if area and pview.norm(area) in (pview.norm(a["name"]), pview.norm(a["id"]))), None)
    tag = lambda p: bool(hit) and (hit["id"] in p["areas"] or pview.norm(p["team"] or "") == pview.norm(hit["name"]))  # noqa: E731
    people = sorted(({**{k: p[k] for k in ("id", "name", "role")}, "tagged": tag(p), "has_account": bool(p["id"])}
                     for p in map(_vals, (doc.get("people") or {}).values()) if p["name"]), key=lambda p: (not p["tagged"], p["name"]))
    return {"areas": areas, "people": people, "minimum": MIN_REPORTERS, "extra_max": EXTRA_MAX}


def preview(plane, close_day: str, now: datetime) -> dict:
    d = week_dates(_today(plane, now), close_day)
    return {**{k: v.isoformat() for k, v in d.items()}, "next_opens": add_wd(d["closes"], 1).isoformat(), "weekday": add_wd(d["closes"], 1).strftime("%A")}


def _series(rec: dict) -> dict:
    return rec.setdefault("series", {"status": "running", "close_day": "fri", "reviewer": (rec["people"].get("organiser") or {}).get("account_id"),
                                     "reviewer_name": (rec["people"].get("organiser") or {}).get("name"), "extra_prompt": None, "week_length_days": 5,
                                     "next_week_opens": None, "current_week": None, "weeks": [], "paused": None, "ended": None})


def _missing(rec: dict) -> str | None:
    if not rec.get("areas"):
        return "Pick the ops area first."
    if len(rec["people"]["participants"]) < MIN_REPORTERS:
        return f"Pick at least {MIN_REPORTERS} people who report."
    return None


def _apply_settings(plane, rec: dict, body: dict, v: pview.Viewer) -> list[str]:
    s, changed, draft = _series(rec), [], rec["state"] == "draft"
    if "area" in body:
        if not draft:
            raise Refuse(409, "To change the area, end this series and start a new one.")
        opts = setup_options(plane, body["area"])
        hit = next((a for a in opts["areas"] if pview.norm(str(body["area"])) in (pview.norm(a["name"]), pview.norm(a["id"]))), None)
        if hit is None:
            raise Refuse(422, "No ops areas are set up yet. Ask your company admin to add one." if not opts["areas"] else "Pick one of the company's areas.")
        rec.update(areas=[hit["name"]], title=f"Check-in: {hit['name']}", purpose=rec.get("purpose") or PURPOSE)
        changed.append("area")
    if "reporters" in body:
        opts = {p["id"]: p for p in setup_options(plane, None)["people"] if p["id"]}
        ids = list(dict.fromkeys(str(i) for i in body["reporters"] or []))
        if any(i not in opts for i in ids):
            raise Refuse(422, "Everyone who reports needs a sign-in. Pick from the list.")
        rec["people"]["participants"] = [{"account_id": i, "name": opts[i]["name"]} for i in ids]
        changed.append("reporters")
    if "close_day" in body:
        if body["close_day"] not in DAYS:
            raise Refuse(422, "Pick a day from Monday to Friday.")
        s["close_day"] = body["close_day"]
        changed.append("close_day")
    if "reviewer" in body:
        pick = next((p for p in setup_options(plane, None)["people"] if p["id"] and p["id"] == body["reviewer"]), None)
        if pick is None:
            raise Refuse(422, "The reviewer needs a sign-in. Pick from the list.")
        s.update(reviewer=pick["id"], reviewer_name=pick["name"])
        changed.append("reviewer")
    if "extra_prompt" in body:
        t = " ".join(str(body["extra_prompt"] or "").split()) or None
        if t and len(t) > EXTRA_MAX:
            raise Refuse(422, f"Keep your own question to {EXTRA_MAX} characters.")
        s["extra_prompt"] = t
        changed.append("extra_prompt")
    _answers(rec, changed)
    if not draft:
        for f in changed:
            _event(plane, rec, "series_changed", _who(v, "organiser"), {"field": f})
    return changed


def _answers(rec: dict, changed: list[str]) -> None:
    """The four start answers (p1 to p4 of the catalogue) in `start_answers`, the cells North reads to know what was asked."""
    sa, s = rec.setdefault("start_answers", {}), rec["series"]
    cell = lambda a: {"answer": a, "mark": "stated"}  # noqa: E731
    if "area" in changed:
        sa["p1"] = cell(rec["areas"][0])
    if "reporters" in changed:
        sa["p2"] = cell([p["name"] for p in rec["people"]["participants"]])
    if "close_day" in changed or "reviewer" in changed or "p3" not in sa:
        sa["p3"] = cell({"close_day": s["close_day"], "reviewer": s.get("reviewer_name")})
    if "extra_prompt" in changed and s["extra_prompt"]:
        sa["p4"] = cell(s["extra_prompt"])


def _organiser_rec(request: Request, intent_id: str):
    plane, v, rec = _ctx(request, intent_id)
    if not _is_org(rec, v):
        raise Refuse(403, "Only the organiser can do that.")
    return plane, v, rec


@router.put("/api/intents/{intent_id}/series")
def put_intents_by_intent_id_series(intent_id: str, body: dict, request: Request):
    def go():
        plane, v, rec = _organiser_rec(request, intent_id)
        with S.locked(plane):
            rec = S.read_intent(plane, intent_id)
            if rec["state"] not in ("draft", "open") or (rec.get("series") or {}).get("status") == "ended":
                raise Refuse(409, "This series has ended and cannot be changed.")
            if _apply_settings(plane, rec, body, v):
                S.write_intent(plane, rec)
        return {"series": rec["series"], "title": rec["title"], "areas": rec["areas"], "reporters": rec["people"]["participants"], "version": rec["version"]}
    return _run(go)


def _act(request: Request, intent_id: str, act: str, body: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    plane, v, rec = _organiser_rec(request, intent_id)
    reason = " ".join(str(body.get("reason") or "").split())[:300]
    with S.locked(plane):
        rec = S.read_intent(plane, intent_id)
        s, today, iso = _series(rec), _today(plane, now), now.isoformat()
        if act == "start":
            if rec["state"] != "draft":
                raise Refuse(409, "This check-in has already started.")
            if (why := _missing(rec)):
                raise Refuse(422, why)
            _answers(rec, [])  # the close day and reviewer default to Friday and the organiser, and still count as answered
            L.move(rec, "open", v.account_id, iso, tz=L.company_zone(plane))
            rec["stages"] = [{"key": "running", "name": "Running", "state": "open", "opened_at": iso, "closed_at": None}]
            rec["refs"]["weeks_dir"] = f"intents/{intent_id}/weeks"
            s.update(status="running", next_week_opens=on_or_after(today).isoformat())
            _open_week(plane, rec, today)
            _event(plane, rec, "series_started", _who(v, "organiser"))
        elif rec["state"] != "open" or s["status"] == "ended":
            raise Refuse(409, "This series has ended.")
        elif act == "pause" and s["status"] == "running":
            s.update(status="paused", paused={"by": v.account_id, "at": iso, "reason": reason})
            _event(plane, rec, "series_paused", _who(v, "organiser"))
        elif act == "resume" and s["status"] == "paused":
            s.update(status="running", paused=None, next_week_opens=max(s["next_week_opens"], add_wd(today, 1).isoformat()))
            _event(plane, rec, "series_resumed", _who(v, "organiser"))
        elif act == "end":
            if not reason:
                raise Refuse(422, "Give a reason to end the series.")
            L.move(rec, "closing", v.account_id, iso, note=reason)
            s.update(status="ended", ended={"by": v.account_id, "at": iso, "reason": reason}, next_week_opens=None)
            for key in s["weeks"][-3:]:  # the open week closes with what it has: it moves to closing and waits for the reviewer
                w = read_week(plane, intent_id, key)
                if w and ORDER.index(w["state"]) < ORDER.index("closing"):
                    w.update(state="closing", stage_closed_at=iso)
                    write_week(plane, intent_id, w)
            _event(plane, rec, "series_ended", _who(v, "organiser"))
        else:
            raise Refuse(409, "That is not possible from where the series is now.")
        S.write_intent(plane, rec)
        return {"series": rec["series"], "state": rec["state"]}


@router.post("/api/intents/{intent_id}/series/{act}")
def post_intents_by_intent_id_series_by_act(intent_id: str, act: str, request: Request, body: dict | None = None):
    if act not in ("start", "pause", "resume", "end"):
        return JSONResponse({"message": NOT_FOUND}, status_code=404)
    return _run(lambda: _act(request, intent_id, act, body or {}))


# ---- the list of weeks (38, series home) --------------------------------------------------------------------------------------

@router.get("/api/intents/{intent_id}/weeks")
def get_intents_by_intent_id_weeks(intent_id: str, request: Request, close_day: str | None = None, area: str | None = None):
    """Counts for everyone with content access; names of those who have not answered only for the organiser and reviewer. For the
    organiser it also carries the setup pickers and the date preview of Screen A."""
    def go():
        now = datetime.now(timezone.utc)
        plane, v, rec = _ctx(request, intent_id)
        rec = tick(plane, intent_id, now) or rec
        s, weeks = rec.get("series") or {}, list_weeks(plane, intent_id)
        reader = _is_reviewer(rec, v)
        rows = [{"week_key": w["week_key"], "opens": w.get("opens"), "closes": w.get("closes"), "state": w.get("state"),
                 "answered": sum(x.get("state") in ("submitted", "closed") for x in w.get("submissions") or []), "of": len(w.get("people") or []),
                 "items": sum(i.get("state") == "active" and not i.get("unsent") for i in w.get("items") or []),
                 "settled": sum(i.get("fate") in ("problem", "backlog") for i in w.get("items") or [])} for w in weeks]
        now_w = weeks[-1] if weeks and weeks[-1]["week_key"] == s.get("current_week") else None
        late = [p["name"] for p in now_w.get("people") or [] if not any(x["by"] == p["account_id"] and x["state"] != "draft" for x in now_w.get("submissions") or [])] if now_w and reader else None
        out = {"series": {k: s.get(k) for k in ("status", "close_day", "reviewer_name", "extra_prompt", "current_week", "next_week_opens")} if s else None,
               "state": rec["state"], "title": rec["title"], "weeks": rows, "not_answered": late, "organiser": _is_org(rec, v), "reviewer": reader,
               "participant": bool(now_w and _in_week(now_w, v))}
        if _is_org(rec, v):
            pick = area or (rec.get("areas") or [None])[0]
            out["setup"] = {**setup_options(plane, pick), "area": pick, "reporters": [p["account_id"] for p in rec["people"]["participants"]],
                            "close_day": (s or {}).get("close_day") or "fri", "reviewer": (s or {}).get("reviewer") or v.account_id,
                            "preview": preview(plane, close_day if close_day in DAYS else (s or {}).get("close_day") or "fri", now)}
        return out
    return _run(go)


# ---- the review routes (spec 40) belong to checkin_review.py; until it exists they stay stubs -----------------------------------

if importlib.util.find_spec("sh_platform.intents.checkin_review"):
    router.include_router(importlib.import_module("sh_platform.intents.checkin_review").router)
else:
    @router.get("/api/intents/{intent_id}/trends")
    def get_intents_by_intent_id_trends(request: Request):
        return not_yet("40")

    @router.get("/api/intents/{intent_id}/weeks/{week_key}")
    def get_intents_by_intent_id_weeks_by_week_key(request: Request):
        return not_yet("40")

    @router.get("/api/intents/{intent_id}/weeks/{week_key}/mine")
    def get_intents_by_intent_id_weeks_by_week_key_mine(request: Request):
        return not_yet("40")

    @router.post("/api/intents/{intent_id}/weeks/{week_key}/digest")
    def post_intents_by_intent_id_weeks_by_week_key_digest(request: Request):
        return not_yet("40")

    @router.post("/api/intents/{intent_id}/weeks/{week_key}/session")
    def post_intents_by_intent_id_weeks_by_week_key_session(request: Request):
        return not_yet("40")

    @router.post("/api/intents/{intent_id}/weeks/{week_key}/close")
    def post_intents_by_intent_id_weeks_by_week_key_close(request: Request):
        return not_yet("38")

    @router.post("/api/intents/{intent_id}/weeks/{week_key}/items/{item_id}/fate")
    def post_intents_by_intent_id_weeks_by_week_key_items_by_item_id_fate(request: Request):
        return not_yet("38")
