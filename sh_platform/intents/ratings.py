"""Spec 10: ratings and "was the outcome used". One score from 1 to 5 and one optional line per person per closed intent, anonymous unless
the person puts their name on it. Nobody sees an anonymous score or note; the organiser and sponsor see a mean and a bar from three
ratings. No per-person average exists, and a Weekly check-in is never rated. The window and the follow-up question are the record's own
`rating` and `outcome_used` (spec 10); an intent closed before they moved there keeps them inside `closure`, and both places are read.
"""
import calendar
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import lifecycle as L
from sh_platform.intents import store as S
from sh_platform.intents.records import _run
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

router = APIRouter()
MIN_GROUP = 3                    # ratings aggregate from three (ruling 8)
NOTE_MAX, LINE_MAX = 140, 200    # spec 10, open question 1: defaults pending Nitin
REMIND_DAYS, DROP_DAYS, CHANGE_DAYS = 2, 5, 7
NEVER_PER_PERSON = ("by", "person", "per_person", "who", "user")


def _month_after(d: datetime) -> datetime:
    y, m = divmod(d.month, 12)
    y, m = d.year + y, m + 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


LEGACY_DAYS = 7  # W2F2: the home card's rating window (pulse/intent_lines RATING_DAYS), for a record closed before the window was written


def field(rec: dict, key: str) -> dict | None:
    """`rating` or `outcome_used`, at the top of the record, or inside `closure` for an intent closed before the move. A closed record
    with neither (closed before ratings existed) gets the window the home card promises: from its closing date, LEGACY_DAYS long."""
    v = rec.get(key)
    v = v if isinstance(v, dict) else (rec.get("closure") or {}).get(key)
    at = (rec.get("closure") or {}).get("closed_at")
    if v is None and key == "rating" and rec.get("state") == "closed" and rec.get("type") != "pulse" and at:
        d = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        v = {"asked_at": d.isoformat(), "reminder_at": d.isoformat(), "drop_at": (d + timedelta(days=LEGACY_DAYS)).isoformat(),
             "dropped_at": None, "rated": [], "waived": [], "reminded": []}
    return v


def _anon(x: dict) -> bool:
    """A seeded rating may carry `by: "anonymous"` and no flag."""
    return bool(x.get("anonymous", x.get("by") in (None, "anonymous")))


def on_close(rec: dict, now: datetime, tz) -> None:
    """North opens the window and schedules the follow-up when the intent closes. A weekly check-in gets neither (ruling 3)."""
    if rec["type"] == "pulse":
        return
    rec["rating"] = {"asked_at": now.isoformat(), "reminder_at": L.add_working_days(now, REMIND_DAYS, tz).isoformat(),
                   "drop_at": L.add_working_days(now, DROP_DAYS, tz).isoformat(), "dropped_at": None, "rated": [], "waived": [], "reminded": []}
    rec["outcome_used"] = {"ask_at": _month_after(now).isoformat(), "asked_at": None, "deferred": 0, "answer": None, "note": None,
                         "answered_by": None, "answered_at": None, "dropped_at": None}


def _slot_ids(rec: dict) -> list[dict]:
    """People asked: everyone named except observers (ruling 4). Affected people are not asked until the test for "took part" is set."""
    p, out, seen = rec.get("people") or {}, [], set()
    for who in [p.get(s) for s in S.SLOTS] + (p.get("participants") or []) + (p.get("advisers") or []):
        key = isinstance(who, dict) and (who.get("account_id") or who.get("name"))
        if key and key not in seen:
            seen.add(key)
            out.append(who)
    return out


def _asked(rec: dict, viewer) -> bool:
    return any(S._named(w, viewer) for w in _slot_ids(rec))


def window_open(rec: dict, now: datetime) -> bool:
    r = field(rec, "rating")
    return bool(r) and not r.get("dropped_at") and now < datetime.fromisoformat(r["drop_at"])


def mean(ratings: list[dict]) -> float | None:
    """The mean over everyone's score, or None below three (ruling 8). Never a mean over one person's entries."""
    return round(sum(r["score"] for r in ratings) / len(ratings), 1) if len(ratings) >= MIN_GROUP else None


def _receipts(plane, account_id: str):
    return plane.path("people", account_id, "ratings.json")


def mine(plane, rec: dict, viewer) -> dict | None:
    if not viewer.account_id:
        return None
    rows = read_json_strict(_receipts(plane, viewer.account_id), list) or []
    return next((r for r in rows if r.get("intent_id") == rec["id"]), None)


def view(plane, rec: dict, viewer, roles: set, names, now: datetime) -> dict | None:
    """What this person may see about ratings. None for a Weekly check-in or an intent that is not closed."""
    r, used = field(rec, "rating"), field(rec, "outcome_used")
    if rec["type"] == "pulse" or rec["state"] != "closed" or not r:
        return None
    done = viewer.account_id in r["rated"] if viewer.account_id else False
    open_ = window_open(rec, now)
    out = {"window_open": open_, "drop_at": r["drop_at"][:10], "dropped": not open_,
           "can_rate": open_ and _asked(rec, viewer) and not done and viewer.account_id not in r["waived"],
           "rated_by_you": done, "waived": bool(viewer.account_id and viewer.account_id in r["waived"]), "mine": mine(plane, rec, viewer),
           "summary": None, "used": None}
    if roles & {"organiser", "sponsor"}:
        ratings, asked = rec.get("ratings") or [], len(_slot_ids(rec))
        m = mean(ratings)
        out["summary"] = {
            "asked": asked, "rated": max(len(r["rated"]), len(ratings)), "count": len(ratings), "mean": m,  # seeded ratings carry no "rated" list
            "bar": {str(i): sum(1 for x in ratings if x["score"] == i) for i in range(1, 6)} if m is not None else None,
            "signed": [{"name": names(x["by"]) or "A named person", "score": x["score"], "note": x.get("note") or ""} for x in ratings if not _anon(x)],
            "anonymous_count": sum(1 for x in ratings if _anon(x)),
            "empty": "No one has rated yet." if not ratings else None,
            "hidden": f"Not shown until three people have rated ({len(ratings)} so far)." if m is None and ratings else None}
    if used and (roles & {"organiser", "sponsor", "company_admin"}):
        due = now >= datetime.fromisoformat(used["ask_at"])
        out["used"] = {**{k: used[k] for k in ("answer", "note", "answered_at")}, "ask_on": used["ask_at"][:10], "due": due,
                       "can_answer": "organiser" in roles and due and (not used["answered_at"] or
                                                                    now - datetime.fromisoformat(used["answered_at"]) <= timedelta(days=CHANGE_DAYS)),
                       "suggest": {"text": "Open a Problem for what stopped it", "href": f"/centre/intent/new?type=problem&from={rec['id']}"}
                       if used["answer"] in ("no", "partly") else None}
    return out


# ---- writes (inside S.update_intent) ----------------------------------------------------------------------------------------

def _window(rec: dict, now: datetime) -> dict:
    if rec["type"] == "pulse":
        raise L.Refused(409, "A weekly check-in is not rated.")
    r = field(rec, "rating")
    if rec["state"] != "closed" or not r:
        raise L.Refused(409, "Ratings open when the intent closes.")
    if not window_open(rec, now):
        raise L.Refused(409, f"The rating window for this intent closed on {r['drop_at'][:10]}. Ratings are not taken after that.")
    if not isinstance(rec.get("rating"), dict) and not isinstance((rec.get("closure") or {}).get("rating"), dict):
        rec["rating"] = r  # the derived window is written with the first rating, so who rated is kept
    return r


def rate(rec: dict, viewer, b: dict, now: datetime) -> dict:
    r = _window(rec, now)
    if not _asked(rec, viewer) or not viewer.account_id:
        raise L.Refused(403, "You were not asked to rate this.")
    if viewer.account_id in r["rated"]:
        raise L.Refused(409, "You have already rated this. A rating cannot be changed.")
    score, note, anon = b.get("score"), str(b.get("note") or "").strip(), b.get("anonymous", True)
    if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5 or not isinstance(anon, bool) or len(note) > NOTE_MAX:
        raise L.Refused(400, f"Pick a rating from 1 to 5. A note is at most {NOTE_MAX} characters.")
    day = now.date().isoformat()  # a date, so a score cannot be matched to the moment someone pressed the button
    # an anonymous entry carries no account id and no note: the note stays with the person (their receipt), spec 10
    rec["ratings"] = sorted([*(rec.get("ratings") or []), {"by": None if anon else viewer.account_id, "anonymous": anon, "score": score,
                                                         "note": "" if anon else note, "at": day}], key=lambda x: (x["score"], x.get("by") or "", x.get("at") or ""))
    r["rated"] = sorted([*r["rated"], viewer.account_id])  # presence only, sorted so the order says nothing
    return {"intent_id": rec["id"], "title": rec["title"], "score": score, "note": note, "anonymous": anon, "at": day}


def waive(rec: dict, viewer, b: dict, now: datetime) -> None:
    r = _window(rec, now)
    if not _asked(rec, viewer) or not viewer.account_id:
        raise L.Refused(403, "You were not asked to rate this.")
    if viewer.account_id not in r["rated"] and viewer.account_id not in r["waived"]:
        r["waived"] = sorted([*r["waived"], viewer.account_id])


def answer_used(rec: dict, viewer, b: dict, now: datetime) -> None:
    used = field(rec, "outcome_used")
    if rec["type"] == "pulse" or rec["state"] != "closed" or not used:
        raise L.Refused(409, "Only a closed intent can be asked this.")
    if not S._named((rec["people"] or {}).get("organiser"), viewer):
        raise L.Refused(403, "Only the organiser answers this.")
    if now < datetime.fromisoformat(used["ask_at"]):
        raise L.Refused(409, f"North asks about this on {used['ask_at'][:10]}. Please come back then.")
    if used["answered_at"] and now - datetime.fromisoformat(used["answered_at"]) > timedelta(days=CHANGE_DAYS):
        raise L.Refused(409, "This answer can no longer be changed.")
    note = str(b.get("note") or "").strip()
    if b.get("answer") not in ("yes", "partly", "no") or len(note) > LINE_MAX:
        raise L.Refused(400, f"Answer yes, partly or no. The line is at most {LINE_MAX} characters.")
    used.update(answer=b["answer"], note=note, answered_by=viewer.account_id, answered_at=now.isoformat(), asked_at=used["asked_at"] or now.isoformat())


# ---- routes -----------------------------------------------------------------------------------------------------------------

def _write(request: Request, intent_id: str, fn, receipt: bool = False):
    from sh_platform.intents import closure as K

    def go(plane, viewer, now):
        rec0 = S.read_intent(plane, intent_id)
        if rec0 is None or S.tier_of(rec0, viewer, S.areas_of(plane, viewer)) is None:
            raise LookupError(intent_id)
        when, got = datetime.fromisoformat(now), []
        rec = S.update_intent(plane, intent_id, rec0["version"], lambda r: got.append(fn(r, viewer, when)))
        if receipt:
            path = _receipts(plane, viewer.account_id)
            with lock_for(path):
                write_json_atomic(path, [*(read_json_strict(path, list) or []), got[0]])
        return K.view(plane, rec, viewer, K._names(request))
    return _run(request, go)


@router.post("/api/intents/{intent_id}/ratings")
def post_intents_by_intent_id_ratings(request: Request, intent_id: str, body: dict = Body(default={})):
    return _write(request, intent_id, lambda r, v, n: rate(r, v, body, n), receipt=True)


@router.post("/api/intents/{intent_id}/rating/waive")
def post_intents_by_intent_id_rating_waive(request: Request, intent_id: str):
    return _write(request, intent_id, lambda r, v, n: waive(r, v, {}, n))


@router.post("/api/intents/{intent_id}/outcome-used")
def post_intents_by_intent_id_outcome_used(request: Request, intent_id: str, body: dict = Body(default={})):
    return _write(request, intent_id, lambda r, v, n: answer_used(r, v, body, n))


@router.get("/api/intents/{intent_id}/ratings")
def get_intents_by_intent_id_ratings(request: Request, intent_id: str):
    from sh_platform.intents import closure as K
    if any(k in request.query_params for k in NEVER_PER_PERSON):
        return JSONResponse({"detail": "Ratings are never shown per person."}, status_code=400)

    def go(plane, viewer, now):
        rec = S.read_intent(plane, intent_id)
        if rec is None or S.tier_of(rec, viewer, S.areas_of(plane, viewer)) is None:
            raise LookupError(intent_id)
        return view(plane, rec, viewer, K.roles_of(rec, viewer), K._names(request), datetime.fromisoformat(now)) or {"rated": False}
    return _run(request, go)
