"""IC v2 (23, 24, 25): the wall inside an intent. The wall itself stays the m1_intent session; this module resolves the intent to its
session, says what the viewer may do, adds the intent fields to the profile cards, and keeps North's suggestions per person.

Routes: GET /api/intents/{id}/wall, POST /api/intents/{id}/suggestions/{sid}/hide|unhide, POST /api/intents/{id}/suggestions/refresh.
Records: reads `intents/<id>/intent.json`; writes `cards.<id>.<field>` cells in the profile and `intents/<id>/suggestions.json`
(hidden rows per seat and counts; the rows themselves stay in the session's own suggestion store).
"""
import logging
import re
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, _viewer
from sh_platform.intents.access import Me, roles_of
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import store as profile_store
from sh_platform.profile import view as profile_view

router = APIRouter()
log = logging.getLogger(__name__)
_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
LANE_OF_CARD = {"tracking": "intent", "missing": "pain_point", "watch": "future_signal", "levers": "lever"}  # notes.py LANE_OF, reversed
STAGE_NAMES = {"think_unfiltered": "Think unfiltered", "define_strategically": "Define strategically", "build_ready": "Build-ready"}
CARD_FIELDS = (("intent_id", None), ("session_kind", None), ("withdrawn", None), ("edits", []), ("moves", []))
NOT_FOUND = "We could not find that."
_cannot_read = "You do not have access to this wall. Ask the organiser to add you."


def _plain(status: int, message: str) -> JSONResponse:
    """The house error body: the client shows `message` for these statuses (403 only under `not_allowed`)."""
    return JSONResponse({"error": {403: "not_allowed", 404: "not_found", 409: "conflict"}.get(status, "failed"), "message": message}, status_code=status)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _val(c: dict, field: str):
    cell = c.get(field)
    return cell.get("value") if isinstance(cell, dict) else None


# ---- the intent, its session and the viewer's part in it

def read_intent(plane, intent_id: str) -> dict | None:
    return read_json_strict(plane.path("intents", intent_id, "intent.json"), dict) if _ID.fullmatch(intent_id) else None


def session_ids(intent: dict) -> list[str]:
    """The wall session ids: `refs.wall_session_ids`, else the `wall_session` ref on a stage (file 22 writes either; Open question 5)."""
    ids = [i for i in (intent.get("refs") or {}).get("wall_session_ids") or [] if isinstance(i, str)]
    for st in intent.get("stages") or []:
        ref = st.get("ref") if isinstance(st, dict) else None
        if isinstance(ref, dict) and ref.get("kind") == "wall_session" and isinstance(ref.get("id"), str) and ref["id"] not in ids:
            ids.append(ref["id"])
    return ids


def role_of(roles: frozenset, seated: bool = False) -> str | None:
    """The wall's role from the intent role set (access.roles_of): organiser, sponsor (the named closer), participant, observer, affected or None."""
    if "organiser" in roles:
        return "organiser"
    if "closer" in roles:
        return "sponsor"
    if "participant" in roles or seated:
        return "participant"
    if "observer" in roles:
        return "observer"
    return "affected" if "affected" in roles else None


def _people_count(p: dict) -> int:
    """Invited people: participants and observers, as entries ({account_id, name}) or ids, each counted once."""
    key = lambda e: (e.get("account_id") or e.get("person_id") or str(e.get("name") or "").lower()) if isinstance(e, dict) else e  # noqa: E731
    return len({key(e) for k in ("participants", "observers") for e in p.get(k) or [] if e})


def initials(slug: str) -> str:
    return "".join(w[0] for w in [w for w in re.split(r"[^a-z0-9]+", slug.lower()) if w][:2]).upper()


def _open(request: Request, intent_id: str):
    """(plane, intent, role, session id), or the answer to send. 404 for what the viewer may not know exists."""
    from modules.m1_intent.store.room import RoomStore
    plane = _plane(request)
    intent, acct = read_intent(plane, intent_id), request.state.account_id
    if intent is None or (intent.get("state") == "draft" and intent.get("created_by") != acct):
        return _plain(404, NOT_FOUND)
    sids = session_ids(intent)
    seated = False
    if sids and acct:
        try:
            seated = RoomStore(plane).seat_of_account(sids[0], acct) is not None
        except (OSError, ValueError, LookupError):
            seated = False
    role = role_of(roles_of(intent, Me.of(request, plane)), seated)
    if role is None:
        return _plain(403, _cannot_read) if "company_admin" in (request.state.roles or []) else _plain(404, NOT_FOUND)
    if role == "affected" and not intent.get("affected_may_read"):
        return _plain(403, _cannot_read)
    return plane, intent, role, (sids[0] if sids else None)


# ---- the card fields this feature adds (file 24)

def stamp_cards(plane, intent_id: str, kind: str, sids: list[str]) -> int:
    """Gives every wall card of these sessions the intent fields it lacks, as profile cells. Idempotent. Returns how many cards changed."""
    def todo(doc):
        return [k for k, c in doc["cards"].items() if _val(c, "room") in sids and "intent_id" not in c]
    if not todo(profile_store.raw(plane)):
        return 0
    prov = {"mark": "stated", "by": "Intent Centre", "from": "The wall of this intent"}

    def change(doc):
        keys = todo(doc)
        for k in keys:
            for f, v in CARD_FIELDS:
                if f in doc["cards"][k]:  # a card withdrawn before it was stamped keeps its mark
                    continue
                profile_store.set_cell(doc, f"cards.{k}.{f}", {"intent_id": intent_id, "session_kind": kind}.get(f, list(v) if isinstance(v, list) else v), prov)
        return len(keys)
    return profile_store.mutate(plane, change)


def withdraw_card(plane, card_id: str, by: str, at: str | None = None) -> None:
    """Marks a card withdrawn, keeping its words (file 24). `by` is the author's key: the caller passes the anon key for an anonymous card.
    The caller checks that the asker is the author and the wall is open."""
    def change(doc):
        c = doc["cards"].get(card_id)
        if c is None:
            raise LookupError(card_id)
        if _val(c, "withdrawn"):
            raise ValueError("already withdrawn")
        profile_store.set_cell(doc, f"cards.{card_id}.withdrawn", {"by": by, "at": at or _now()},
                               {"mark": "stated", "by": by, "from": "Withdrawn by its author"})
    profile_store.mutate(plane, change)


def counts(cards: list[dict]) -> dict:
    """Cards per wall lane, withdrawn ones out of every number and tallied apart."""
    live = [c for c in cards if not _val(c, "withdrawn")]
    lane = Counter(LANE_OF_CARD.get(_val(c, "lane"), "intent") for c in live)
    return {"total": len(live), "per_lane": {k: lane.get(k, 0) for k in LANE_OF_CARD.values()}, "withdrawn": len(cards) - len(live)}


def contributors(cards: list[dict]) -> list[str]:
    """Initials of named authors only. A sealed silhouette, an anonymous card and a withdrawn card give none."""
    return sorted({i for c in cards if "silhouette" not in c and not _val(c, "anonymous") and not _val(c, "withdrawn")
                   and (a := str(_val(c, "author") or "")) and a != "unnamed" and (i := initials(a))})


def reader_cards(shown: list[dict], rooms_open: bool) -> list[dict]:
    """The wall as a reader (sponsor, observer, affected) sees it, shaped as the wall's lane cards. The m1 board serves only seat holders and
    the organiser (Open question 3), so these come from the profile view, which already hides sealed words and anonymous authors.
    While the rooms are open a card is a silhouette: lane only. Authors show as initials, never a name."""
    out = []
    for c in shown:
        if _val(c, "withdrawn"):
            continue
        lane = LANE_OF_CARD.get(c["lane"] if "silhouette" in c else _val(c, "lane"), "intent")
        if "silhouette" in c:
            out.append({"id": c["id"], "lane": lane, "text": "", "anonymous": True, "mine": False, "quarters": None, "guessed": 0, "sealed": True})
        elif rooms_open:
            out.append({"id": f"other-{len(out)}", "lane": lane, "text": "", "anonymous": True, "mine": False, "quarters": None, "guessed": 0, "sealed": False, "other": True})
        else:
            anon = _val(c, "anonymous") is True
            ini = "" if anon else initials(str(_val(c, "author") or ""))
            out.append({"id": f"card-{len(out)}", "lane": lane, "text": str(_val(c, "q1") or ""), "anonymous": anon or not ini, "author": ini or None, "mine": False,
                        "quarters": sum(1 for q in ("q1", "q2", "q3", "q4") if _val(c, q)), "guessed": 0, "sealed": False})
    return out


# ---- the wall's two times, written by the m1 routes that close the rooms and freeze the wall (file 23)

def mark_wall(plane, sid: str, field: str) -> None:
    """When the session belongs to an intent, writes `stages[think_unfiltered].wall.<field>` (`rooms_closed_at` or `frozen_at`) once.
    Never raises: the m1 move has already happened and must not fail on the intent's record."""
    from sh_platform.intents import store as S
    from sh_platform.intents.charter import intent_for_session
    for _ in range(2):  # one retry when the record moved between the read and the write
        try:
            rec = intent_for_session(plane, sid)
            st = next((x for x in (rec or {}).get("stages") or [] if x.get("key") == "think_unfiltered"), None)
            if st is None or (st.get("wall") or {}).get(field):
                return
            S.update_intent(plane, rec["id"], rec["version"],
                            lambda r: next(x for x in r["stages"] if x.get("key") == "think_unfiltered").setdefault("wall", {}).setdefault(field, _now()))
            return
        except S.VersionConflict:
            continue
        except Exception:  # noqa: BLE001
            log.warning("the wall time %s could not be written for session %s", field, sid, exc_info=True)
            return


def baseline_for(plane) -> str:
    """The module 2 baseline an Initiative's Define reads (refs.baseline_ids). Module 2 keeps one baseline per signed charter and the charter is
    written in Define, so the intent attaches the company's governed baseline (the newest signed one, the same one the clusters' rings read);
    else the newest baseline with measures; else module 2 starts an empty one, as it does for a company with no charter."""
    from modules.m1_intent.domain.together import latest_signed_baseline_id
    from modules.m2_baseline.store import baseline as MB
    bid = latest_signed_baseline_id(plane)
    if bid and MB.read_baseline(plane, bid):
        return bid
    with_kpis = [b for b in MB.baselines(plane) if plane.path("intents", "m2_baseline", b["id"], "kpis.json").is_file()]
    return (with_kpis[0] if with_kpis else MB.start(plane, None)[0])["id"]


def open_define(plane, intent_id: str, baseline_id: str | None, now: str | None = None) -> dict | None:
    """The wall froze: Think unfiltered closes, Define strategically opens, and the baseline is attached when the intent has none (spec 50
    step 5). Idempotent. Returns the record, or None when nothing changed. Leaves a stage line per move in events.jsonl."""
    from sh_platform.intents import events as E
    from sh_platform.intents import store as S
    now, moved = now or _now(), []

    def change(r):
        for st in r.get("stages") or []:
            if st.get("key") == "think_unfiltered" and st.get("state") == "open":
                st.update(state="closed", closed_at=now)
                moved.append(("stage_closed", st["key"]))
            elif st.get("key") == "define_strategically" and st.get("state") == "waiting":
                st.update(state="open", opened_at=now)
                moved.append(("stage_opened", st["key"]))
        refs = r.setdefault("refs", {})
        if baseline_id and not refs.get("baseline_ids"):
            refs["baseline_ids"] = [baseline_id]
            moved.append(("baseline", baseline_id))
    for _ in range(2):
        rec = S.read_intent(plane, intent_id)
        if rec is None or rec.get("state") not in ("open", "in_session"):
            return None
        try:
            rec = S.update_intent(plane, intent_id, rec["version"], change)
            break
        except S.VersionConflict:
            moved.clear()
    else:
        return None
    organiser = (rec.get("people") or {}).get("organiser") or {}
    who = {"account": organiser.get("account_id"), "name": organiser.get("name") or "", "role": "organiser"}
    for kind, key in moved:
        if kind != "baseline":
            E.try_append(plane, intent_id, kind, who, None, {"stage": key, **({"closed_by": "person"} if kind == "stage_closed" else {})}, "act", stage=key)
    return rec if moved else None


def define_opened(request: Request, plane, sid: str) -> None:
    """The m1 route froze the wall: when the session belongs to an Initiative, Define opens on its record and Lens starts drafting
    ("North starts it when Define opens", spec 44). Never raises: the wall has already frozen."""
    try:
        from sh_platform.intents.charter import intent_for_session
        rec = intent_for_session(plane, sid)
        if not rec or rec.get("type") != "initiative":
            return
        had = bool((rec.get("refs") or {}).get("baseline_ids"))
        new = open_define(plane, rec["id"], None if had else baseline_for(plane))
        if new is not None and (new.get("refs") or {}).get("baseline_ids"):
            from sh_platform.intents import lens
            lens.start_in_background(plane, rec["id"], lens.runtime_for_request(request, plane))
    except Exception:  # noqa: BLE001
        log.warning("Define could not be opened on the intent for session %s", sid, exc_info=True)


# ---- the people records: the m1 routes tell the intent that someone joined or put up a card (never fails the act)

def _seat_person(plane, sid: str, seat) -> dict | None:
    from modules.m1_intent.store.room import RoomStore
    from modules.m1_intent.domain.seat_identity import seat_id_of
    room = RoomStore(plane).get(sid)
    return next((x for x in (room or {}).get("seats") or []  # the notes store passes the keyed seat id; the join route passes n
                 if x.get("state") == "taken" and seat in (x.get("n"), x.get("participant_id"), seat_id_of(plane, sid, x))), None)


def person_joined(plane, sid: str, seat: dict) -> None:
    """The join route took a seat: the intent that owns this wall session lists the person as Joined, via link."""
    try:
        from sh_platform.intents import people
        from sh_platform.intents.charter import intent_for_session
        rec = intent_for_session(plane, sid)
        if rec:
            people.record_join(plane, rec["id"], seat.get("account_id"), seat.get("name") or "", sid, seat["n"])
    except Exception:  # noqa: BLE001 - the seat is taken; a people record that cannot be written never undoes it
        log.warning("the join could not be recorded on the intent for session %s", sid, exc_info=True)


def person_contributed(plane, sid: str, seat) -> None:
    """A person's cards went to the wall: Joined becomes Contributed (first one only; mark_contributed leaves the rest as they are)."""
    try:
        from sh_platform.intents import people
        from sh_platform.intents.charter import intent_for_session
        rec, who = intent_for_session(plane, sid), _seat_person(plane, sid, seat)
        if rec and who:
            people.mark_contributed(plane, rec["id"], who.get("account_id") or f"guest-{sid}-{who['n']}")
    except Exception:  # noqa: BLE001
        log.warning("the first card could not be recorded on the intent for session %s", sid, exc_info=True)


# ---- the wall read

@router.get("/api/intents/{intent_id}/wall")
def get_wall(request: Request, intent_id: str):
    try:
        got = _open(request, intent_id)
        if isinstance(got, JSONResponse):
            return got
        plane, intent, role, sid = got
        sids = session_ids(intent)
        kind = "brainstorm" if intent.get("type") == "brainstorm" else "wall"
        seen, tally, organiser_q = [], counts([]), {}
        if sids:
            if role in ("organiser", "participant"):  # the writers stamp; a reader never writes
                stamp_cards(plane, intent_id, kind, sids)
            raw = {k: c for k, c in profile_store.raw(plane)["cards"].items() if _val(c, "room") in sids}  # the room is on the raw card: a silhouette has none
            tally = counts(list(raw.values()))  # numbers only, so the raw cards are safe here
            shown = profile_view.read(plane, _viewer(request))["cards"]
            seen = [shown[k] for k in raw if k in shown]
            organiser_q = {k: sum(1 for q in ("q1", "q2", "q3", "q4") if _val(shown[k], q))
                           for k in raw if k in shown and "silhouette" not in shown[k] and not _val(shown[k], "withdrawn")}
        p = intent.get("people") or {}
        invited = _people_count(p)
        joined = _joined(plane, sid)
        stage = next((s for s in intent.get("stages") or [] if s.get("key") == "think_unfiltered"), {})
        cards = None
        if sid and role not in ("organiser", "participant"):
            from modules.m1_intent.store.sessions import SessionStore
            st = SessionStore(plane).get(sid)
            cards = reader_cards(seen, st is None or st["state"] in ("draft", "lobby", "briefing", "private_rooms"))
        return {
            "cards": cards,
            "intent_id": intent_id, "session_id": sid, "role": role, "can_add": role in ("organiser", "participant"),
            "intent": {"title": intent.get("title") or "", "purpose": intent.get("purpose") or "", "type": intent.get("type"),
                       "state": intent.get("state"), "ends": (intent.get("time_box") or {}).get("ends") or None},
            "stages": [{"key": s.get("key"), "name": STAGE_NAMES.get(s.get("key"), str(s.get("key") or "").replace("_", " ").capitalize()),
                        "state": s.get("state")} for s in intent.get("stages") or []],
            "wall": {"rooms_closed_at": (stage.get("wall") or {}).get("rooms_closed_at"), "frozen_at": (stage.get("wall") or {}).get("frozen_at")},
            "people": {"invited": invited, "joined": joined, "initials": contributors(seen)},
            "counts": tally,
            # the organiser's board foot: quarters answered per card (n / 4), on the cards this viewer may read; sealed and withdrawn have none
            "quarters": organiser_q if role == "organiser" else None,
        }
    except PermissionError:
        return _plain(403, "Your company space could not be opened. Please ask your administrator.")
    except (ValueError, OSError):
        return _plain(500, "The wall could not be read. Try again.")


def _joined(plane, sid: str | None) -> int | None:
    from modules.m1_intent.store.room import RoomStore
    try:
        room = RoomStore(plane).get(sid) if sid else None
    except (OSError, ValueError, LookupError):
        return None
    return None if room is None else sum(1 for s in room["seats"] if s["state"] == "taken")


# ---- North's suggestions: hide, unhide, top up (file 25)

def _path(plane, intent_id: str):
    return plane.path("intents", intent_id, "suggestions.json")


def _read(plane, intent_id: str) -> dict:
    d = read_json_strict(_path(plane, intent_id), dict) or {}
    return {"hidden": d.get("hidden") or {}, "counts": {"suggested": 0, "hidden": 0, **(d.get("counts") or {})}}


def hide(plane, intent_id: str, sid: str, seat: str, suggestion_id: str) -> bool:
    """Not this one: the row leaves the person's suggestions and is kept apart so it is never drafted again. False when it is not there."""
    from modules.m1_intent.store.notes import SuggestionStore
    with lock_for(_path(plane, intent_id)):
        row = SuggestionStore(plane).take(sid, seat, suggestion_id)
        if row is None:
            return False
        st = _read(plane, intent_id)
        st["hidden"].setdefault(seat, []).append(row)
        st["counts"]["hidden"] += 1
        write_json_atomic(_path(plane, intent_id), st)
    return True


def unhide(plane, intent_id: str, sid: str, seat: str, suggestion_id: str) -> bool:
    """Undo: the row comes back to the person's suggestions."""
    from modules.m1_intent.store.notes import SuggestionStore
    with lock_for(_path(plane, intent_id)):
        st = _read(plane, intent_id)
        rows = st["hidden"].get(seat) or []
        row = next((r for r in rows if r.get("id") == suggestion_id), None)
        if row is None:
            return False
        store = SuggestionStore(plane)
        store.put(sid, seat, (store.get(sid, seat) or []) + [row])
        st["hidden"][seat] = [r for r in rows if r is not row]
        st["counts"]["hidden"] = max(0, st["counts"]["hidden"] - 1)
        write_json_atomic(_path(plane, intent_id), st)
    return True


def top_up(limit: int, brainstorm: bool, rows: list[dict], hidden: list[dict], notes: list[dict], fresh: list[dict]) -> list[dict]:
    """The new rows to add to what the person already has: at most `limit` per lane (in a brainstorm, `limit` in all), never a text the
    person holds, hid or already turned into a card. `fresh` is the candidates already passed through `notes_quarters.suggest`."""
    have = {" ".join(str(r.get("text", "")).lower().split()) for r in rows + hidden + notes}
    used, out = Counter(r.get("kind") for r in rows), []
    for s in fresh:
        key = " ".join(s["text"].lower().split())
        if key in have or (len(rows) + len(out) >= limit if brainstorm else used[s["kind"]] >= limit):
            continue
        have.add(key)
        used[s["kind"]] += 1
        out.append(s)
    return out


def _seat_ctx(request: Request, intent_id: str):
    """(plane, intent, ctx, sid) for a person with a seat while the rooms are open, else the answer to send."""
    from modules.m1_intent.api import private_room as room
    from modules.m1_intent.domain import private_room as R
    got = _open(request, intent_id)
    if isinstance(got, JSONResponse):
        return got
    plane, intent, _, sid = got
    ctx = room.Ctx(request, sid) if sid else None
    if ctx is None or not ctx.ok:
        return _plain(404, NOT_FOUND)
    if ctx.s["state"] != R.ROOM_STAGE:
        return _plain(409, "The private rooms are not open, so there are no suggestions to change.")
    return plane, intent, ctx, sid


def _hide_route(request: Request, intent_id: str, suggestion_id: str, undo: bool):
    try:
        got = _seat_ctx(request, intent_id)
        if isinstance(got, JSONResponse):
            return got
        plane, _, ctx, sid = got
        ok = (unhide if undo else hide)(plane, intent_id, sid, ctx.seat, suggestion_id)
        return {"ok": True} if ok else _plain(404, "That suggestion is no longer there.")
    except PermissionError:
        return _plain(403, "Your company space could not be opened. Please ask your administrator.")
    except (ValueError, OSError):
        return _plain(500, "That did not work. Try again.")


@router.post("/api/intents/{intent_id}/suggestions/{suggestion_id}/hide")
def post_suggestion_hide(request: Request, intent_id: str, suggestion_id: str):
    return _hide_route(request, intent_id, suggestion_id, False)


@router.post("/api/intents/{intent_id}/suggestions/{suggestion_id}/unhide")
def post_suggestion_unhide(request: Request, intent_id: str, suggestion_id: str):
    return _hide_route(request, intent_id, suggestion_id, True)


@router.post("/api/intents/{intent_id}/suggestions/refresh")
def post_suggestions_refresh(request: Request, intent_id: str):
    """North tops up the person's suggestions from their documents and the pack, within the cap. Nothing happens until the room's own
    first seeding has run (the person has opened their room)."""
    from modules.m1_intent.api import private_room as room
    from modules.m1_intent.domain import notes_quarters as Q
    from modules.m1_intent.store.notes import SuggestionStore
    from modules.m1_intent.tools.pack_tools import kind_suggestions
    try:
        got = _seat_ctx(request, intent_id)
        if isinstance(got, JSONResponse):  # rooms not open (before or after): nothing to top up, which is not a fault (the wall calls this on every open)
            return {"added": 0, "sources": []} if got.status_code == 409 else got
        plane, intent, ctx, sid = got
        store = SuggestionStore(plane)
        rows = store.get(sid, ctx.seat)
        if rows is None or ctx.wall().max_suggestions == 0:
            return {"added": 0, "sources": []}
        found = []
        for g in room.read_profile(plane, room.profile_viewer(request))["inputs"].values():  # as the room's own first seeding reads them
            cell = g.get("findings") if isinstance(g, dict) else None
            for f in (cell or {}).get("value") or []:
                kind = room.FINDING_LANE.get(f.get("kind"))
                name = str(f.get("from") or "").split(":")[0].strip() or str((cell or {}).get("from") or "")
                if kind and f.get("text") and name:
                    found.append({"kind": kind, "text": f["text"], "from": name})
        label = f"{ctx.guidance.label} pack" if ctx.guidance.label else "the industry pack"
        notes = ctx.transcripts.load(sid, ctx.seat)["notes"]
        with lock_for(_path(plane, intent_id)):
            st = _read(plane, intent_id)
            fresh = Q.suggest(ctx.wall(), found + Q.from_pack(kind_suggestions(ctx.guidance), label))
            new = top_up(ctx.wall().max_suggestions, intent.get("type") == "brainstorm", rows, st["hidden"].get(ctx.seat) or [], notes, fresh)
            if new:
                store.put(sid, ctx.seat, rows + new)
                st["counts"]["suggested"] += len(new)
                write_json_atomic(_path(plane, intent_id), st)
        return {"added": len(new), "sources": sorted({r["from"] for r in new})}
    except PermissionError:
        return _plain(403, "Your company space could not be opened. Please ask your administrator.")
    except (ValueError, OSError):
        return _plain(500, "That did not work. Try again.")
