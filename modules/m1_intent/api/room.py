"""M1-P02 routes: start the room (M1-03), join by link with no account, the lobby (M1-04), rejoin and late join
(M1-15), and the live updates the lobby uses. Declared in manifest.yaml AND marked in route_permissions.yaml.

Who is who (kernel: sh_platform/auth/guest.py):
- Organiser routes need the signed-in organiser account. A token holder never reaches them: the table does not
  mark them `guest`, so the kernel refuses a token there before this file runs.
- Lobby and live routes are `guest`: a signed-in person who joined with their account (the organiser running
  alone, or any colleague of the company), or a token holder. Whichever it is, the path's session id must be the
  session that person belongs to; anything else is the same "not found".
- POST /join is the `entry` route: it is reached with no session and no token. The company is the one the join
  code belongs to, found in the control index; nothing about the company is taken from the request.
The join code and tokens are never logged, echoed in an error, or put in a URL of an API call.
"""
import asyncio
import hmac
import json
import logging
import re
import secrets
import time
from datetime import datetime
from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from modules.m1_intent.api import deps
from modules.m1_intent.domain import contracts as C
from modules.m1_intent.domain import room as R
from modules.m1_intent.domain.seat_identity import name_is_tied_elsewhere, plane_key
from modules.m1_intent.store.files import StoreError, read_json, write_json
from modules.m1_intent.store.room import JoinIndex, RoomStore, resolve_token
from modules.m1_intent.store.sessions import SessionStore
from sh_platform.auth.guest import register_guest_resolver
from sh_platform.modulegate import may_use_module
from sh_platform.plane import PlaneStore

log = logging.getLogger(__name__)
router = APIRouter()
MODULE = "m1_intent"
TICK_SECONDS = 1.0      # how often a stream looks at the room (a plain file read)
LIVE_SECONDS = 600.0    # a stream ends after this long; the screen reconnects (and so is checked again)
JOIN_BODY_MAX = 4096    # a join is a code, a seat, a name and a role: well under 1 KB
_NAME_BOUND = "That name belongs to someone else in the company. Please use your own name."
_LINK_INVALID = ("link_invalid", "This link is not working. Please ask the organiser for a new one.")
_OTHER_COMPANY = ("other_company", "You are signed in to a different company, so you cannot join this session. "
                                   "Sign out, then open the link again.")


# ---- the kernel asks this module who a token belongs to
def _resolve_guest(app, token):
    # a closed session still knows its seated guests: they may read the board and the charter (every other route refuses
    # a guest of a closed session; the live stream and the lobby check the token again, strictly). The token stops
    # working `guest_read_days_after_close` days after the close (updated_at is the time of the close: nothing writes to a closed session).
    root = app.state.settings.data_root
    who = resolve_token(root, token, allow_closed=True)
    if who is None:
        return None
    try:
        s = SessionStore(PlaneStore(root).plane_for(who[0])).get(who[2])
        if s is not None and s["state"] == "closed":
            days = C._int(C._read(getattr(app.state, "m1_contracts_dir", None), "retention.yaml")["guest_read_days_after_close"], "guest days")
            if float(getattr(app.state, "m1_clock", time.time)()) > datetime.fromisoformat(s["updated_at"]).timestamp() + days * 86400:
                return None
    except (StoreError, LookupError, ValueError, KeyError, TypeError, OSError):
        return None  # cannot tell: no access
    return who


register_guest_resolver(MODULE, _resolve_guest)


class _HideJoinCode(logging.Filter):
    """The page address /join/<code> carries the code by design, and the web server's access log would record
    it. This keeps the code out of that log."""
    _CODE = re.compile(r"/join/[^\s/?#\"']+")

    def filter(self, record: logging.LogRecord) -> bool:
        def hide(v):
            return self._CODE.sub("/join/<hidden>", v) if isinstance(v, str) else v
        record.msg = hide(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(hide(a) for a in record.args)
        return True


logging.getLogger("uvicorn.access").addFilter(_HideJoinCode())


_ROOM_STATUS = {"seat_taken": 409, "seat_revoked": 409, "paused": 409, "link_closed": 409, "not_taken": 409,
                "own_seat": 409, "name_taken": 409, "name_bound": 409, "invalid": 422}
guarded = deps.guarded(
    (R.RoomError, lambda e: deps.plain(_ROOM_STATUS.get(e.code, 404), e.code, e.message,
                                       **({"field": e.field} if e.field else {}))),
    (LookupError, lambda e: deps.not_found()))


# ---- who is asking
@dataclass(frozen=True)
class Viewer:
    organiser: bool
    seat: dict | None


def _viewer(request: Request, rooms: RoomStore, session: dict) -> Viewer | None:
    """The viewer of this session, or None. For a token holder the path's session must be the token's session."""
    st, sid = request.state, session["id"]
    if st.account_id is not None:
        organiser = session["organiser_account_id"] == st.account_id
        seat = rooms.seat_of_account(sid, st.account_id)
        return Viewer(organiser, seat) if organiser or seat else None
    if st.guest_id is not None and st.m1_session_id == sid and session["state"] != "closed":  # after the close a guest reads only the charter and the board
        seat = rooms.seat_of_participant(sid, st.guest_id)
        return Viewer(False, seat) if seat else None
    return None


def _me(seat: dict | None) -> dict | None:
    return None if seat is None else {"seat": seat["n"], "name": seat["name"], "role": seat["role"],
                                      "late": seat["late"], "see_briefing_first": seat["late"]}


def _picture(room: dict, viewer: Viewer | None) -> list[dict]:
    """The seat picture. Names and roles of those who hold a seat; nothing else about a seat. A revoked seat shows
    only its state, to everyone including the organiser (the organiser also sees who came late)."""
    mine = viewer.seat["n"] if viewer and viewer.seat else None
    out = []
    for s in room["seats"]:
        row: dict = {"n": s["n"], "state": s["state"], "mine": s["n"] == mine}
        if s["state"] == "taken":
            row.update(name=s["name"], role=s["role"])
        if viewer is not None and viewer.organiser and s["state"] != "free":
            row["late"] = s["late"]
        out.append(row)
    return out


def _room_view(session: dict, room: dict, viewer: Viewer) -> dict:
    prep = session["preparation"]
    return {"session_id": session["id"], "state": session["state"], "length_minutes": _total(prep),
            "is_solo": prep["seats"] == 1, "organiser": viewer.organiser, "me": _me(viewer.seat),
            "seats": _picture(room, viewer), "arrived": sum(1 for s in room["seats"] if s["state"] == "taken"),
            "seat_count": len(room["seats"])}


def _link(code: str, state: str) -> dict:
    return {"join_path": f"/join/{code}", "state": state}


def _plane(request: Request):
    return PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()


def _stores(request: Request) -> tuple[SessionStore, RoomStore]:
    rooms = RoomStore(_plane(request))
    return rooms.sessions, rooms


# ---- the organiser's link, kept sealed so it can be shown again (the index keeps only its hash, as before)
def _pad(plane, nonce: bytes) -> bytes:
    """32 bytes from the plane's own key (the seat ids use it too).
    ponytail: the key sits in the same plane as the sealed code, so the seal keeps the code out of copies and logs of
    the link file; it is no protection against someone who can read the plane's files."""
    return hmac.new(plane_key(plane), nonce, "sha256").digest()


def _keep_link(plane, session_id: str, code: str) -> None:
    nonce = secrets.token_bytes(16)
    sealed = bytes(a ^ b for a, b in zip(code.encode(), _pad(plane, nonce)))
    write_json(plane.path("intents", "m1_intent", "join_links", f"{session_id}.json"),
               {"session_id": session_id, "sealed": nonce.hex() + sealed.hex()})


def _kept_link(plane, session_id: str) -> str | None:
    data = read_json(plane.path("intents", "m1_intent", "join_links", f"{session_id}.json"))
    try:
        raw = bytes.fromhex(data["sealed"])  # type: ignore[index]
        code = bytes(a ^ b for a, b in zip(raw[16:], _pad(plane, raw[:16]))).decode()
    except (TypeError, KeyError, ValueError):
        return None
    return code if re.fullmatch(r"[A-Za-z0-9_-]{22}", code) else None


def _total(prep: dict) -> int:
    """The whole session in minutes: the chosen length, or the split's sum when a wall window made it longer."""
    return max(int(prep["length_minutes"]), sum(int(v) for v in (prep.get("split") or {}).values()))


def _seat_invited(plane, session_id: str) -> None:
    """People already invited to the intent that owns this wall get their seats now that the room exists."""
    from sh_platform.intents import people
    from sh_platform.intents.charter import intent_for_session
    rec = intent_for_session(plane, session_id)
    if rec:
        people.seat_invited(plane, rec["id"])


# ---- the organiser
@router.post("/sessions/{session_id}/start", status_code=201)
@guarded
async def start_room(request: Request, session_id: str):
    _, rooms = _stores(request)
    index = JoinIndex(request.app.state.settings.data_root)
    code = await deps.blocking(rooms.start, session_id, request.state.account_id, index)
    await deps.blocking(_keep_link, _plane(request), session_id, code)
    await deps.blocking(_seat_invited, _plane(request), session_id)
    return _link(code, "lobby")


@router.post("/sessions/{session_id}/link")
@guarded
async def new_link(request: Request, session_id: str):
    _, rooms = _stores(request)
    index = JoinIndex(request.app.state.settings.data_root)
    code = await deps.blocking(rooms.new_code, session_id, request.state.account_id, index)
    await deps.blocking(_keep_link, _plane(request), session_id, code)
    return _link(code, "lobby")


@router.get("/sessions/{session_id}/join-link")
@guarded
async def current_link(request: Request, session_id: str):
    """The organiser's current join link, shown again without making a new one (a new one ends the old one)."""
    sessions, _ = _stores(request)

    def work():
        s = sessions.get(session_id)
        if s is None or s["organiser_account_id"] != request.state.account_id:
            raise LookupError("no session")
        code = _kept_link(_plane(request), session_id)
        return None if code is None or s["state"] == "closed" else _link(code, s["state"])

    return await deps.blocking(work) or deps.plain(404, "no_link", "This link was not saved. Make a new link to share it.")


@router.post("/sessions/{session_id}/seats/{seat}/revoke")
@guarded
async def revoke_seat(request: Request, session_id: str, seat: str):
    _, rooms = _stores(request)
    if not re.fullmatch(r"[0-9]{1,2}", seat):
        raise LookupError("no seat")

    def work():
        room = rooms.revoke(session_id, request.state.account_id, int(seat), request.query_params.get("reopen") == "1")
        return _room_view(rooms.sessions.get(session_id), room, Viewer(True, None))

    return await deps.blocking(work)


@router.post("/sessions/{session_id}/briefing")
@guarded
async def start_briefing(request: Request, session_id: str):
    _, rooms = _stores(request)
    s = await deps.blocking(rooms.to_briefing, session_id, request.state.account_id)
    return {"state": s["state"]}


# ---- organiser and participants
def _read_view(request: Request, session_id: str):
    """A function that gives this caller's current view, or None once they may no longer see it. Used by both the
    plain read and every tick of the stream; a token is checked again each time."""
    st = request.state
    root = request.app.state.settings.data_root
    token = request.headers.get("x-session-token") if st.account_id is None else None
    who = (st.company_id, st.guest_id, st.m1_session_id)
    app_state = request.app.state

    def read():
        # every tick, for everyone: the company still owns the module (a stream outlives the gate's one check)
        if not may_use_module(app_state.entitlements, st.company_id, MODULE):
            return None
        if token is not None and resolve_token(root, token) != who:  # revoked, closed or replaced since
            return None
        if st.account_id is not None:  # signed in: the server session and the account must still be good. is_live
            acct = app_state.account_store.get(st.account_id)  # does not touch the idle timer, resolve() would
            if not (app_state.sessions.is_live(st.sid) and acct and not acct["disabled"]
                    and acct["company_id"] == st.company_id):
                return None
        rooms = RoomStore(PlaneStore(root).plane_for(st.company_id))
        s, room = rooms.sessions.get(session_id), rooms.get(session_id)
        viewer = _viewer(request, rooms, s) if s and room else None
        return _room_view(s, room, viewer) if viewer else None

    return read


@router.get("/sessions/{session_id}/lobby")
@guarded
async def lobby(request: Request, session_id: str):
    view = await deps.blocking(_read_view(request, session_id))
    if view is None:
        raise LookupError("no session")
    return view


async def event_stream(read_view):
    """Server-sent events: the viewer's own view each time it changes. Nothing is queued, so every event is built
    for this viewer at that moment. ponytail: polls a small file once a second per stream; fine for ten people."""
    loop = asyncio.get_running_loop()
    end, last = loop.time() + LIVE_SECONDS, None
    while loop.time() < end:
        view = await deps.blocking(read_view)
        if view is None:
            return
        payload = json.dumps(view, sort_keys=True)
        if payload != last:
            last = payload
            yield f"data: {payload}\n\n"
        await asyncio.sleep(TICK_SECONDS)


@router.get("/sessions/{session_id}/live")
@guarded
async def live(request: Request, session_id: str):
    read = _read_view(request, session_id)
    if await deps.blocking(read) is None:  # refused before a byte streams
        raise LookupError("no session")
    return StreamingResponse(event_stream(read), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


# ---- joining
def _enabled_in(request: Request, company_id: str):
    """A test for "this account exists in this company and is switched on" (the door only refuses names linked to such an account)."""
    store = request.app.state.account_store

    def is_enabled(account_id: str) -> bool:
        acct = store.get(account_id)
        return bool(acct) and acct["company_id"] == company_id and not acct["disabled"]
    return is_enabled


def _join_view(session: dict, room: dict, seat: dict | None, token: str | None, signed_in: bool) -> dict:
    return {"session_id": session["id"], "state": session["state"], "signed_in": signed_in,
            "length_minutes": _total(session["preparation"]), "token": token, "me": _me(seat),
            "seats": [{"n": s["n"], "state": s["state"]} for s in room["seats"]]}


class _BodyProblem(Exception):
    def __init__(self, response):
        self.response = response


async def _join_body(request: Request) -> dict | None:
    """The join body: JSON only, at most JOIN_BODY_MAX bytes (counted as it arrives, so a missing or false
    Content-Length does not help). Anyone can reach this route, so nothing is read before it is checked."""
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise _BodyProblem(deps.plain(415, "bad_request", deps.BAD_BODY))
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > JOIN_BODY_MAX:
        raise _BodyProblem(deps.plain(413, "too_large", deps.BAD_BODY))
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > JOIN_BODY_MAX:
            raise _BodyProblem(deps.plain(413, "too_large", deps.BAD_BODY))
        chunks.append(chunk)
    try:
        body = json.loads(b"".join(chunks))
    except ValueError:  # includes bad UTF-8
        return None
    return body if isinstance(body, dict) else None


@router.post("/join")
@guarded
async def join(request: Request):
    try:
        raw = await _join_body(request)
    except _BodyProblem as e:
        return e.response
    if raw is None or not isinstance(raw.get("code"), str):
        return deps.plain(400, "bad_request", deps.BAD_BODY)
    st, root = request.state, request.app.state.settings.data_root
    entry = await deps.blocking(JoinIndex(root).lookup, raw["code"])
    # a company without the module looks exactly like a code nobody knows
    if entry is None or not may_use_module(request.app.state.entitlements, entry["company_id"], MODULE):
        return deps.plain(404, *_LINK_INVALID)
    if st.account_id is not None and st.company_id != entry["company_id"]:
        return deps.plain(403, *_OTHER_COMPANY)  # no company data in the answer
    plane = PlaneStore(root).plane_for(entry["company_id"]).ensure()
    rooms, sid = RoomStore(plane), entry["session_id"]

    def work():
        s, room = rooms.sessions.get(sid), rooms.get(sid)
        if s is None or room is None:
            raise R.RoomError(*_LINK_INVALID)
        known = (rooms.seat_of_account(sid, st.account_id) if st.account_id is not None else
                 rooms.seat_of_participant(sid, st.guest_id) if st.guest_id is not None and st.m1_session_id == sid
                 else None)
        problem = R.join_problem(s["state"], new_person=known is None)
        if problem:
            if problem.code == "link_closed":
                JoinIndex(root).mark_closed(sid)
            raise problem
        if known is not None:  # the same link returns a person to their own seat; no new token is made
            return _join_view(s, room, known, None, st.account_id is not None)
        if raw.get("seat") is None:  # just looking at the seats
            return _join_view(s, room, None, None, st.account_id is not None)
        n = R.seat_number(raw.get("seat"), len(room["seats"]))
        name, role = R.clean_person(raw.get("name"), raw.get("role"))
        if name_is_tied_elsewhere(plane, name, st.account_id, _enabled_in(request, entry["company_id"])):
            raise R.RoomError("name_bound", _NAME_BOUND, "name")
        seat, token = rooms.take(sid, n, name, role, st.account_id)
        from sh_platform.intents.wall import person_joined
        person_joined(plane, sid, seat)  # the intent's people list shows Joined, via link; never fails the join
        return _join_view(s, rooms.get(sid), seat, token, st.account_id is not None)

    return await deps.blocking(work)
