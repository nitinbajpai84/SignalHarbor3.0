"""The room, its seats and the join link (M1-03, M1-04, M1-15).

intents/m1_intent/rooms/<session id>.json     seats of one session, in that company's own plane
<data root>/_control/m1_join_index.json       join code HASH -> company id, session id, created, closed; and
                                              session id -> company id. Ids only: no company data, no names.

The join code (128-bit, URL-safe) and the participant token (256-bit) are shown once and only their SHA-256
hashes are stored. A token is "<session id>.<secret>": the session id lets the control index find the company
without scanning planes; the secret alone is what is checked, against the hash on the seat, in constant time.
Nothing here logs or raises a code or a token. Locks cover threads in one process only (A-015).
"""
import hashlib
import hmac
import logging
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from modules.m1_intent.domain import room as R
from modules.m1_intent.store.files import UNREADABLE, StoreError, WrongState, lock_for, read_json, write_json
from modules.m1_intent.store.sessions import SessionStore
from sh_platform.plane import CrossCompanyError, PlaneStore

log = logging.getLogger(__name__)
_HEX32 = re.compile(r"[0-9a-f]{32}")
_TOKEN = re.compile(r"([0-9a-f]{32})\.([A-Za-z0-9_-]{43})")
_CODE = re.compile(r"[A-Za-z0-9_-]{22}")
_ROOM_KEYS = {"session_id", "seats"}
_SEAT_KEYS = {"n", "state", "participant_id", "name", "role", "account_id", "token_hash", "late", "joined_at"}
_ENTRY_KEYS = {"company_id", "session_id", "created", "closed"}
NO_ROOM = "This session has no room yet."


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class JoinIndex:
    """The control index. One small file; every change under its own lock."""

    def __init__(self, data_root, clock=time.time):
        self._path = Path(data_root).resolve() / "_control" / "m1_join_index.json"
        self._clock = clock

    def _read(self) -> dict:
        data = read_json(self._path)
        if data is None:
            return {"codes": {}, "sessions": {}}
        if not (isinstance(data, dict) and set(data) == {"codes", "sessions"} and isinstance(data["codes"], dict)
                and isinstance(data["sessions"], dict)
                and all(isinstance(e, dict) and set(e) == _ENTRY_KEYS and isinstance(e["closed"], bool)
                        for e in data["codes"].values())):
            raise StoreError(UNREADABLE)
        return data

    def add(self, code: str, company_id: str, session_id: str) -> None:
        """The session's one code: a new code replaces the old one, which stops working."""
        with lock_for(self._path):
            data = self._read()
            data["codes"] = {h: e for h, e in data["codes"].items() if e["session_id"] != session_id}
            data["codes"][digest(code)] = {"company_id": company_id, "session_id": session_id,
                                           "created": datetime.fromtimestamp(self._clock(), timezone.utc).isoformat(),
                                           "closed": False}
            data["sessions"][session_id] = company_id
            write_json(self._path, data)

    def lookup(self, code) -> dict | None:
        """{company_id, session_id, closed} for a live code, else None. A malformed code is just unknown."""
        if not isinstance(code, str) or not _CODE.fullmatch(code):
            return None
        with lock_for(self._path):
            entry = self._read()["codes"].get(digest(code))
        return None if entry is None else dict(entry)

    def company_of(self, session_id: str) -> str | None:
        with lock_for(self._path):
            found = self._read()["sessions"].get(session_id)
        return found if isinstance(found, str) else None

    def mark_closed(self, session_id: str) -> None:
        """Flags the session's link as closed. The session's own state stays the truth: a later package that
        closes a session may call this, and the checks below do not depend on it."""
        with lock_for(self._path):
            data = self._read()
            hit = [e for e in data["codes"].values() if e["session_id"] == session_id and not e["closed"]]
            for e in hit:
                e["closed"] = True
            if hit:
                write_json(self._path, data)


class RoomStore:
    def __init__(self, plane, clock=time.time):
        self._plane, self._clock = plane, clock
        self.sessions = SessionStore(plane, clock)

    # ---- files
    def _lock(self):
        return lock_for(self._plane.path("intents", "m1_intent"))  # the SessionStore's own lock: one at a time

    def _path(self, session_id: str) -> Path:
        return self._plane.path("intents", "m1_intent", "rooms", f"{session_id}.json")

    def _now(self) -> str:
        return datetime.fromtimestamp(self._clock(), timezone.utc).isoformat()

    def get(self, session_id) -> dict | None:
        if not isinstance(session_id, str) or not _HEX32.fullmatch(session_id):
            return None
        data = read_json(self._path(session_id))
        if data is None:
            return None
        seats = data.get("seats") if isinstance(data, dict) else None
        if not (isinstance(data, dict) and set(data) == _ROOM_KEYS and data["session_id"] == session_id
                and isinstance(seats, list) and seats and all(
                    isinstance(s, dict) and set(s) == _SEAT_KEYS and s["state"] in R.SEAT_STATES for s in seats)
                and [s["n"] for s in seats] == list(range(1, len(seats) + 1))):
            raise StoreError(UNREADABLE)
        return data

    def _save(self, room: dict) -> None:
        write_json(self._path(room["session_id"]), room)

    # ---- the organiser's moves
    def start(self, session_id: str, organiser_id: str, index: JoinIndex) -> str:
        """Draft to lobby: seats and the link are made; the new code is returned (shown once, never stored)."""
        with self._lock():
            s = self.sessions.get(session_id)
            if s is None or s["organiser_account_id"] != organiser_id:
                raise LookupError("no session")
            if s["state"] != "draft":
                raise WrongState("This session has already started.")
            self.sessions.check_wall_free(session_id)  # IC-2t: one open wall per topic; refused before seats and the link exist
            code = secrets.token_urlsafe(16)
            self._save({"session_id": session_id, "seats": R.new_seats(s["preparation"]["seats"])})
            index.add(code, self._plane.company_id, session_id)
            self.sessions.transition(session_id, "lobby")  # also mirrors "in progress" into the process record
            return code

    def new_code(self, session_id: str, organiser_id: str, index: JoinIndex) -> str:
        """A new link for a started session; the old one stops working. People already seated are not affected."""
        with self._lock():
            s = self.sessions.get(session_id)
            if s is None or s["organiser_account_id"] != organiser_id:
                raise LookupError("no session")
            if s["state"] == "draft" or self.get(session_id) is None:
                raise WrongState("This session has no room yet. Start the room first.")
            if s["state"] == "closed":
                raise WrongState("This session has closed, so it has no link any more.")
            code = secrets.token_urlsafe(16)
            index.add(code, self._plane.company_id, session_id)
            return code

    def revoke(self, session_id: str, organiser_id: str, n: int, reopen: bool = False) -> dict:
        with self._lock():
            s, room = self.sessions.get(session_id), self.get(session_id)
            if s is None or room is None or s["organiser_account_id"] != organiser_id:
                raise LookupError("no session")
            if s["state"] == "closed":
                raise WrongState("This session has closed.")
            if reopen and s["state"] not in ("lobby", "briefing"):
                raise WrongState("A seat can only be freed before the private rooms open.")
            seat = next((x for x in room["seats"] if x["n"] == n), None)
            if seat is not None and seat["account_id"] == organiser_id:
                raise R.RoomError("own_seat", "You cannot remove your own seat. The session needs you to run it.")
            room = {**room, "seats": R.revoke_seat(room["seats"], n, reopen)}
            self._save(room)
            return room

    def to_briefing(self, session_id: str, organiser_id: str) -> dict:
        """Lobby to briefing, with empty seats allowed. The briefing itself is another package's."""
        with self._lock():
            s = self.sessions.get(session_id)
            if s is None or s["organiser_account_id"] != organiser_id:
                raise LookupError("no session")
            return self.sessions.transition(session_id, "briefing")

    # ---- arrivals
    def take(self, session_id: str, n: int, name: str, role: str, account_id: str | None) -> tuple[dict, str | None]:
        """Takes a free seat for the person. A signed-in person is bound by account (no token); anyone else gets a
        new token, returned here once. One of two joins for the same seat wins; the other is refused."""
        with self._lock():
            s, room = self.sessions.get(session_id), self.get(session_id)
            if s is None or room is None:
                raise LookupError("no room")
            problem = R.join_problem(s["state"], new_person=True)
            if problem:
                raise problem
            if account_id is not None:  # one account, one seat: checked here, under the lock, so a race cannot
                held = next((x for x in room["seats"]  # seat the same person twice
                             if x["state"] == "taken" and x["account_id"] == account_id), None)
                if held is not None:
                    return held, None
            secret = None if account_id else f"{session_id}.{secrets.token_urlsafe(32)}"
            seats = R.take_seat(room["seats"], n, name=name, role=role, participant_id=secrets.token_hex(8),
                                account_id=account_id, token_hash=digest(secret) if secret else None,
                                state=s["state"], now=self._now())
            self._save({**room, "seats": seats})
            return next(x for x in seats if x["n"] == n), secret

    # ---- who is who
    def seat_of_account(self, session_id: str, account_id: str) -> dict | None:
        room = self.get(session_id)
        return next((s for s in room["seats"] if s["state"] == "taken" and s["account_id"] == account_id),
                    None) if room else None

    def seat_of_participant(self, session_id: str, participant_id) -> dict | None:
        room = self.get(session_id)
        return next((s for s in room["seats"] if s["state"] == "taken" and s["participant_id"] == participant_id),
                    None) if room else None

    def seat_of_token(self, session_id: str, token: str, allow_closed: bool = False) -> dict | None:
        """The taken seat this token belongs to, while the session is open (`allow_closed`: also after it closed, so
        a seated guest can still read the result). Constant-time compare of hashes."""
        m = _TOKEN.fullmatch(token)
        if not m or m.group(1) != session_id:
            return None
        s, room = self.sessions.get(session_id), self.get(session_id)
        if s is None or room is None or s["state"] == "draft" or (s["state"] == "closed" and not allow_closed):
            return None
        want = digest(token)
        for seat in room["seats"]:
            if seat["state"] == "taken" and seat["token_hash"] and hmac.compare_digest(seat["token_hash"], want):
                return seat
        return None


def resolve_token(data_root, token, allow_closed: bool = False) -> tuple[str, str, str] | None:
    """(company id, participant id, session id) for a token that is valid now, else None. Never raises.
    The company comes from the control index, never from the request."""
    if not isinstance(token, str):
        return None
    m = _TOKEN.fullmatch(token)
    if not m:
        return None
    session_id = m.group(1)
    try:
        company_id = JoinIndex(data_root).company_of(session_id)
        if company_id is None:
            return None
        seat = RoomStore(PlaneStore(data_root).plane_for(company_id)).seat_of_token(session_id, token, allow_closed)
    except (StoreError, LookupError, CrossCompanyError, ValueError, OSError):
        return None
    return (company_id, seat["participant_id"], session_id) if seat else None
