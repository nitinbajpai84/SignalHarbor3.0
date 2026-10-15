"""IC v2 (26): Define strategically inside an Initiative.

Module 1's together stage stays the board, the vote, the shelves and the charter draft (reused, not rebuilt). This file adds:
  GET  /api/intents/{id}/define/session   the session record, the decisions counter and the open items for the close dialog
  POST /api/intents/{id}/define/session   {action: start|extend|close|reopen}; close moves the stage only (ruling 26)
  POST /api/intents/{id}/define/shelf     a shelf move with the organiser's review date for Future; a refused move is logged
Session fields live in the intent record under `define` (file 26, "Fields this feature adds"); each act is one events line.
"""
import json
import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from modules.m1_intent.api import deps
from modules.m1_intent.api.board import route, settings
from modules.m1_intent.api.briefing import Open
from modules.m1_intent.domain import board as B
from modules.m1_intent.domain import together as T
from modules.m1_intent.store.board import BoardStore, TogetherStore
from modules.m1_intent.store.files import StoreError
from modules.m1_intent.store.together_shelves import ShelfStore
from sh_platform.intents import _plane, store
from sh_platform.intents.clock import _is, _log, _tz, _who
from sh_platform.profile import view as PV

log = logging.getLogger(__name__)
router = APIRouter()

# ruling 28: the record accepts every key a feature file adds; file 26 adds `define`. Drop this line once store.KEYS lists it.
store.KEYS = store.KEYS | {"define"}

STAGE_KEYS = ("define_strategically", "define")
PLANNED, EXTRA, REASON_MAX = 90, 15, 300
SLOTS, LISTS = ("organiser", "sponsor", "decider", "owner", "reporter"), ("participants", "advisers", "observers")
NOT_FOUND = "We could not find that intent."
ONLY_ORGANISER = "Only the organiser can do this."
NO_PEOPLE = "Name a start time and invite the committee first."
NEED_REASON = "Please say why more time is needed."
PARK_REASON = "Please say why this is parked for later."
PARK_DATE = "Choose a date after today."
CLOSED = "Define is closed. Reopen it for a correction first."
NO_CHARTER = "Write the charter draft first."
SIGNED = "The charter is signed."
REOPEN_REASON = "Please say why Define is reopened."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fail(status: int, message: str) -> JSONResponse:
    return JSONResponse({"message": message}, status_code=status)


def _me(ref, who: dict) -> bool:
    """A people slot names this viewer: the ruling 21 object ({account_id, name}) or a plain account id, email or name."""
    if isinstance(ref, dict):
        ref = ref.get("account_id") or ref.get("email") or ref.get("name")
    return _is(ref, who)


def _name(ref) -> str:
    return str(ref.get("name") or "") if isinstance(ref, dict) else str(ref or "")


def relation(rec: dict, who: dict, plane=None) -> dict:
    """With a plane, a person the intent's records name as a source owner or confirmer reads as a participant (store.named_in_records)."""
    p = rec.get("people") or {}
    reader = any(_me(p.get(s), who) for s in SLOTS) or any(_me(x, who) for k in LISTS for x in p.get(k) or [])
    if not reader and plane is not None and rec.get("state") != "draft" and who.get("id"):
        try:
            reader = store.named_in_records(plane, rec, PV.Viewer(who.get("name") or "", frozenset(who.get("roles") or ()), account_id=who["id"]))
        except Exception:  # noqa: BLE001 - a records read that fails leaves the person as the people list says
            log.warning("named_in_records failed for %s", rec.get("id"), exc_info=True)
    affected = any(_me(x, who) for x in p.get("affected") or []) and bool(rec.get("affected_may_read"))
    return {"organiser": _me(p.get("organiser"), who), "reader": reader or affected}


def stage_of(rec: dict) -> dict | None:
    return next((s for s in rec.get("stages") or [] if s.get("key") in STAGE_KEYS), None)


def wall_of(rec: dict) -> str | None:
    ids = (rec.get("refs") or {}).get("wall_session_ids") or []
    return ids[-1] if ids else None


def today_in(plane) -> date:
    """Today in the company's time zone from the profile, else UTC (also when this machine has no time zone data)."""
    try:
        return datetime.now(ZoneInfo(_tz(plane))).date()
    except (ZoneInfoNotFoundError, ValueError):
        return datetime.now(timezone.utc).date()


def review_date_ok(text, today: date) -> str | None:
    """The organiser's review date for Future: an ISO date later than today, else None."""
    try:
        d = date.fromisoformat(str(text))
    except ValueError:
        return None
    return d.isoformat() if d > today else None


def board_counts(plane, sid: str | None, today: date, governed: dict | None = None) -> dict:
    """Read from module 1's board, shelf and together stores. A decision is a cluster with a shelf and, on Must or Should, a tick."""
    zero = {"made": 0, "of": 0, "shelf_counts": {**{s: 0 for s in T.SHELVES}, "not_placed": 0}, "unticked": 0, "parked_late": 0, "ungoverned": None,
            "open_groups": []}  # not ticked into the charter: the groups the charter draft asks about ("1 group is still open")
    if not sid:
        return zero
    try:
        clusters = BoardStore(plane).get(sid)["clusters"]
        shelves = ShelfStore(plane).get(sid)["shelves"]
        together = TogetherStore(plane).get(sid)
    except StoreError:
        return zero
    ticked, s = set(together["ticked"]), B.load_settings(None)
    out = {**zero, "of": len(clusters), "shelf_counts": dict(zero["shelf_counts"]), "open_groups": open_groups(plane, sid)}
    for c in clusters:
        row = shelves.get(c["id"]) or {}
        # the organiser's shelf, else the tally's, exactly as the board shows it (together.cluster_view)
        shelf = T.shelf_id(row.get("shelf") or T.priority(s, T.tally(s, together, c["id"]))) or "not_placed"
        out["shelf_counts"][shelf if shelf in out["shelf_counts"] else "not_placed"] += 1
        on_top = shelf in ("must", "should")
        out["made"] += shelf != "not_placed" and (not on_top or c["id"] in ticked)
        out["unticked"] += on_top and c["id"] not in ticked
        out["parked_late"] += shelf == "future" and bool(row.get("review_date")) and row["review_date"] < today.isoformat()
    if governed is not None:
        out["ungoverned"] = sum(1 for c in clusters if governed.get(c["id"]) is False)
    return out


def open_groups(plane, sid: str) -> list[str]:
    """The groups not ticked into the charter, named exactly as the charter draft's "still open" question names them (one read, two screens)."""
    from modules.m1_intent.domain.charter import sentence_case
    from modules.m1_intent.store.charter import together_result
    try:
        rows = (together_result(plane, sid) or {}).get("clusters") or []
    except StoreError:
        return []
    return [sentence_case(str(c.get("title") or "")) for c in rows if not c.get("ticked")]


def refusals(plane, intent_id: str) -> int:
    try:
        lines = plane.path("intents", intent_id, "events.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    n = 0
    for line in lines:
        try:
            n += json.loads(line).get("kind") == "shelf_refused"
        except (ValueError, AttributeError):
            continue
    return n


# ---- the session record (pure on a record; the caller holds the lock and writes) -------------------------------------------

def act(plane, rec: dict, who: dict, body: dict, now: str, counts: dict) -> tuple[int, str] | None:
    """Apply one session action to `rec`. Returns (status, message) when refused, else None (rec changed, events logged)."""
    if not relation(rec, who)["organiser"]:
        return 403, ONLY_ORGANISER
    stage, action = stage_of(rec), body.get("action")
    if stage is None:
        return 409, NOT_FOUND
    d = rec.setdefault("define", {})
    session = d.get("session")
    reason = " ".join(str(body.get("reason") or "").split())
    if action == "start":
        if stage.get("closed_at"):
            return 409, CLOSED
        if rec.get("state") != "open":
            return 409, "The session can start only while the intent is open."
        if not (rec.get("people") or {}).get("participants"):
            return 409, NO_PEOPLE
        d["session"] = {"started_at": now, "ended_at": None, "planned_minutes": PLANNED, "extensions": [],
                        "decisions_made": counts["made"], "decisions_of": counts["of"]}
        rec.setdefault("history", []).append({"at": now, "by": who["id"], "from": "open", "to": "in_session", "note": "Define session started"})
        rec["state"] = "in_session"
        _log(plane, rec["id"], rec, who, "define_session_started", {"planned_minutes": PLANNED}, "define_strategically")
    elif action == "extend":
        if not session or not session.get("started_at") or session.get("ended_at"):
            return 409, "The session has not started."
        if not reason or len(reason) > REASON_MAX:
            return 422, NEED_REASON
        session["extensions"].append({"by": who["id"], "at": now, "minutes": EXTRA, "reason": reason})
        _log(plane, rec["id"], rec, who, "define_extended", {"minutes": EXTRA}, "define_strategically")
    elif action == "close":
        if stage.get("closed_at"):
            return 409, CLOSED
        if not plane.path("intents", "m1_intent", "charters", f"{wall_of(rec)}.json").is_file():
            return 409, NO_CHARTER
        session = d["session"] = session or {"started_at": None, "ended_at": None, "planned_minutes": PLANNED, "extensions": []}
        session.update({"ended_at": now, "decisions_made": counts["made"], "decisions_of": counts["of"]})
        stage.update({"state": "closed", "closed_at": now})
        d["shelf_counts"] = counts["shelf_counts"]
        d["refusals"] = refusals(plane, rec["id"])  # the intent state is left as it is: closing comes at charter signature (ruling 26)
        _log(plane, rec["id"], rec, who, "define_closed", {"decisions_made": counts["made"], "decisions_of": counts["of"]}, "define_strategically")
    elif action == "reopen":
        if not stage.get("closed_at"):
            return 409, "Define is open."
        if (rec.get("refs") or {}).get("charter_outcome_id"):
            return 409, SIGNED
        if not reason or len(reason) > REASON_MAX:
            return 422, REOPEN_REASON
        stage.update({"state": "open", "closed_at": None})
        d.setdefault("reopened", []).append({"by": who["id"], "at": now, "reason": reason})
        _log(plane, rec["id"], rec, who, "define_reopened", {}, "define_strategically")
    else:
        return 400, "Please choose start, extend, close or reopen."
    return None


def _load(request: Request, intent_id: str):
    plane = _plane(request)
    try:
        rec = store.read_intent(plane, intent_id)
    except store.Unreadable:
        rec = None
    return plane, rec


def _governed(request: Request, plane, sid: str | None) -> dict:
    """cluster id -> governed (True/False), absent with no baseline or no measure; module 1's own read."""
    if not sid:
        return {}
    from modules.m1_intent.api.charter import _pack_rows
    try:
        problems, kpis, _ = _pack_rows(request)
        baseline = T.latest_signed_baseline_id(plane)
        out = {}
        for c in BoardStore(plane).get(sid)["clusters"]:
            g = T.governed_of(plane, baseline, T.measure_codes(c.get("pack_problem_id"), problems, kpis))
            if g:
                out[c["id"]] = g["governed"]
        return out
    except (StoreError, AttributeError):
        return {}


def view(request: Request, plane, rec: dict) -> dict:
    who = _who(request)
    rel, stage, sid = relation(rec, who, plane), stage_of(rec) or {}, wall_of(rec)
    p, d = rec.get("people") or {}, rec.get("define") or {}
    head = {"id": rec["id"], "type": rec["type"], "title": rec.get("title", ""), "purpose": rec.get("purpose", ""), "state": rec["state"],
            "organiser_name": _name(p.get("organiser"))}
    stage_out = {"state": stage.get("state"), "opened_at": stage.get("opened_at"), "closed_at": stage.get("closed_at")}
    if not rel["reader"]:  # the company admin: existence and the outcome after close, never the board (file 26, who uses it)
        return {"intent": head, "stage": stage_out, "tier": "exists", "shelf_counts": d.get("shelf_counts") if stage.get("closed_at") else None}
    counts = board_counts(plane, sid, today_in(plane), _governed(request, plane, sid))
    return {"intent": head, "stage": stage_out, "tier": "content", "wall_session_id": sid, "organiser": rel["organiser"],
            "start_blocked": None if p.get("participants") else NO_PEOPLE, "session": d.get("session"),
            "decisions": {"made": counts["made"], "of": counts["of"]}, "open_items": counts, "refusals": refusals(plane, rec["id"]),
            "has_baseline": bool((rec.get("refs") or {}).get("baseline_ids")), "held": bool(d.get("held_at")),
            "signed": bool((rec.get("refs") or {}).get("charter_outcome_id")), "today": today_in(plane).isoformat(), "now": _now()}


def _visible(request: Request, rec: dict | None) -> bool:
    if rec is None:
        return False
    who = _who(request)
    if rec["state"] == "draft":
        return relation(rec, who)["organiser"]
    return relation(rec, who, _plane(request))["reader"] or "company_admin" in who["roles"]


@router.get("/api/intents/{intent_id}/define/session")
def get_define_session(intent_id: str, request: Request):
    plane, rec = _load(request, intent_id)
    if not _visible(request, rec):
        return _fail(404, NOT_FOUND)
    return view(request, plane, rec)


@router.post("/api/intents/{intent_id}/define/session")
def post_define_session(intent_id: str, body: dict, request: Request):
    plane, rec = _load(request, intent_id)
    if not _visible(request, rec):
        return _fail(404, NOT_FOUND)
    who = _who(request)
    with store.locked(plane):
        rec = store.read_intent(plane, intent_id)
        counts = board_counts(plane, wall_of(rec), today_in(plane))
        refused = act(plane, rec, who, body, _now(), counts)
        if refused:
            return _fail(*refused)
        store.write_intent(plane, rec)
    return view(request, plane, rec)


def _log_alone(plane, intent_id: str, who: dict, kind: str, detail: dict) -> None:
    """One events line for an act that changes nothing else in the record; the record's counts follow."""
    with store.locked(plane):
        rec = store.read_intent(plane, intent_id)
        if rec is None:
            return
        _log(plane, intent_id, rec, who, kind, detail, "define_strategically")
        store.write_intent(plane, rec)


@router.post("/api/intents/{intent_id}/define/shelf")
@route
async def post_define_shelf(intent_id: str, request: Request):
    """The organiser puts a cluster on a shelf. Must and Should need a governed cluster (A-054): a refusal is kept as an event and
    answered 409 with the missing fields. Future needs a reason and a review date later than today (company time zone)."""
    raw = await deps.body_object(request)
    if raw is None or not {"cluster_id", "shelf"} <= set(raw) <= {"cluster_id", "shelf", "reason", "review_date"}:
        return deps.plain(400, "bad_request", deps.BAD_BODY)

    def work():
        plane, rec = _load(request, intent_id)
        if not _visible(request, rec):
            return _fail(404, NOT_FOUND)
        who = _who(request)
        if not relation(rec, who)["organiser"]:
            return _fail(403, ONLY_ORGANISER)
        if (stage_of(rec) or {}).get("closed_at"):
            return _fail(409, CLOSED)
        sid, shelf, cid = wall_of(rec), T.shelf_id(raw["shelf"]), raw["cluster_id"]
        if not sid:
            return _fail(409, "No wall is linked to this intent yet.")
        review = None
        if shelf == "future":
            if not " ".join(str(raw.get("reason") or "").split()):
                return _fail(422, PARK_REASON)
            review = review_date_ok(raw.get("review_date"), today_in(plane))
            if review is None:
                return _fail(422, PARK_DATE)
        o, s = Open(request, sid), settings(request)  # R3: the Define stage being open is the gate; the wall's own state is not asked
        cluster = next((c for c in BoardStore(o.plane).get(sid)["clusters"] if c["id"] == cid), None)
        if cluster is None:
            return _fail(404, "We could not find that group.")
        from modules.m1_intent.api.charter import _pack_rows
        from modules.m1_intent.api.together import together_view
        from modules.m1_intent.domain.seat_identity import person_name
        problems, kpis, _ = _pack_rows(request)
        cluster = {**cluster, **T.governed_of(o.plane, T.latest_signed_baseline_id(o.plane), T.measure_codes(cluster.get("pack_problem_id"), problems, kpis))}
        ok, why = T.may_shelve(cluster, shelf)
        if not ok:
            _log_alone(plane, intent_id, who, "shelf_refused", {"cluster": cid, "to": shelf, "missing": ",".join(cluster.get("missing", []))[:80]})
            return JSONResponse({"message": why, "refused": True, "cluster_id": cid}, status_code=409)
        by = person_name(request, o.s, o.plane) or "Organiser"

        def change(data: dict) -> dict:
            data = T.move_to_shelf(data, cluster, shelf, raw.get("reason"), by, o.now, s.comment_chars, request.state.account_id)
            if review:
                data["shelves"][cid] = {**data["shelves"][cid], "review_date": review}
            return data
        ShelfStore(o.plane, clock=lambda: o.now).update(sid, change)
        _log_alone(plane, intent_id, who, "cluster_parked" if shelf == "future" else "shelf_moved", {"cluster": cid, "to": shelf})
        return together_view(o, s, request)
    return await deps.blocking(work)


@router.post("/api/intents/{intent_id}/define/hold")
@route
async def post_define_hold(intent_id: str, request: Request):
    """Hold the room or carry on (R3): kept on the intent record, the m1 wall is not touched. Body {held: bool}."""
    raw = await deps.body_object(request)
    if raw is None or set(raw) != {"held"} or not isinstance(raw["held"], bool):
        return deps.plain(400, "bad_request", deps.BAD_BODY)

    def work():
        plane, rec = _load(request, intent_id)
        if not _visible(request, rec):
            return _fail(404, NOT_FOUND)
        who = _who(request)
        if not relation(rec, who)["organiser"]:
            return _fail(403, ONLY_ORGANISER)
        if (stage_of(rec) or {}).get("closed_at"):
            return _fail(409, CLOSED)
        with store.locked(plane):
            rec = store.read_intent(plane, intent_id)
            rec.setdefault("define", {})["held_at"] = _now() if raw["held"] else None
            _log(plane, intent_id, rec, who, "define_held" if raw["held"] else "define_resumed", {}, "define_strategically")
            store.write_intent(plane, rec)
        return view(request, plane, rec)
    return await deps.blocking(work)


@router.post("/api/intents/{intent_id}/define/vote")
@route
async def post_define_vote(intent_id: str, request: Request):
    """A seat's vote on a cluster while Define is open (R3), whatever state the wall is in. Body {cluster_id, option}."""
    raw = await deps.body_object(request)
    if raw is None or set(raw) != {"cluster_id", "option"}:
        return deps.plain(400, "bad_request", deps.BAD_BODY)

    def work():
        plane, rec = _load(request, intent_id)
        if not _visible(request, rec) or not wall_of(rec):
            return _fail(404, NOT_FOUND)
        if (stage_of(rec) or {}).get("closed_at"):
            return _fail(409, CLOSED)
        if (rec.get("define") or {}).get("held_at"):
            return _fail(409, T.CLOSED_VOTING["paused"])
        sid, cid = wall_of(rec), raw["cluster_id"]
        o, s = Open(request, sid), settings(request)
        if not any(c["id"] == cid for c in BoardStore(plane).get(sid)["clusters"]):
            return _fail(404, "We could not find that group.")
        clusters = BoardStore(plane).get(sid)["clusters"]
        TogetherStore(plane).update(sid, lambda d: T.apply_auto_ticks(s, T.vote(s, d, cid, o.seat, raw["option"]), clusters))
        return {"ok": True}
    return await deps.blocking(work)
