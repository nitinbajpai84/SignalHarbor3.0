"""The room's rules (M1-03, M1-04, M1-15), pure Python, no storage: seats, what a person gives on arrival, when a
link works, and who may add notes. The stage moves themselves stay in states.py.

Seat states: free, taken, revoked. A taken seat is never taken by anyone else; a revoked seat is never reused.
"""
import unicodedata

SEAT_STATES = ("free", "taken", "revoked")
# The stages in which the link still works for a new person: the lobby and every stage after it. A paused
# session lets people who already hold a seat back in, but takes nobody new; a closed one takes nobody.
JOINABLE = ("lobby", "briefing", "private_rooms", "board", "together", "signing")
NAME_MAX = 60   # chosen (M1-P02 choice 1): nothing in the spec; a person's name or nickname
ROLE_MAX = 80   # chosen (M1-P02 choice 1): their job role in the company, free text


class RoomError(Exception):
    """A plain-words refusal. `code` is for the screen, `field` names the value a form should mark."""

    def __init__(self, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.code, self.message, self.field = code, message, field


def new_seats(count: int) -> list[dict]:
    return [{"n": n, "state": "free", "participant_id": None, "name": None, "role": None, "account_id": None,
             "token_hash": None, "late": False, "joined_at": None} for n in range(1, count + 1)]


def _plain(value, what: str, limit: int, field: str) -> str:
    if not isinstance(value, str):
        raise RoomError("invalid", f"Please give your {what}.", field)
    text = " ".join(value.split())  # trims and folds any run of spaces, tabs and line breaks
    if not text:
        raise RoomError("invalid", f"Please give your {what}.", field)
    if len(text) > limit:
        raise RoomError("invalid", f"Your {what} can have at most {limit} characters.", field)
    if any(unicodedata.category(c).startswith("C") for c in text):  # control, format, unassigned: never shown
        raise RoomError("invalid", f"Your {what} can only have plain letters, numbers and punctuation.", field)
    return text


def clean_person(name, role) -> tuple[str, str]:
    """Name and job role as plain text: trimmed, limited, no control characters."""
    return _plain(name, "name", NAME_MAX, "name"), _plain(role, "role", ROLE_MAX, "role")


def seat_number(value, count: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= count:
        raise RoomError("invalid", "Please choose one of the seats shown.", "seat")
    return value


def join_problem(state: str, new_person: bool) -> RoomError | None:
    """Why the link cannot be used now, or None."""
    if state == "closed":
        return RoomError("link_closed", "This session has closed, so the link no longer works.")
    if state == "paused" and new_person:
        return RoomError("paused", "This session is paused. Please try again when the organiser resumes it.")
    if state not in JOINABLE and state != "paused":
        return RoomError("link_invalid", "This link is not working. Please ask the organiser for a new one.")
    return None


def take_seat(seats: list[dict], n: int, *, name: str, role: str, participant_id: str, account_id: str | None,
              token_hash: str | None, state: str, now: str) -> list[dict]:
    """The seats with seat n taken, or RoomError. A latecomer (the lobby is over) is flagged to see the briefing first."""
    seat = next((s for s in seats if s["n"] == n), None)
    if seat is None:
        raise RoomError("invalid", "Please choose one of the seats shown.", "seat")
    if seat["state"] == "taken":
        raise RoomError("seat_taken", "That seat has just been taken. Please choose another.", "seat")
    if seat["state"] == "revoked":
        raise RoomError("seat_revoked", "That seat is no longer available. Please choose another.", "seat")
    if any(s["state"] in ("taken", "revoked") and (s["name"] or "").casefold() == name.casefold() for s in seats):  # a revoked seat keeps its name
        raise RoomError("name_taken", "Someone in this session already uses that name. Please add your surname.", "name")
    taken = {**seat, "state": "taken", "participant_id": participant_id, "name": name, "role": role,
             "account_id": account_id, "token_hash": token_hash, "late": state != "lobby", "joined_at": now}
    return [taken if s["n"] == n else s for s in seats]


def revoke_seat(seats: list[dict], n: int, reopen: bool = False) -> list[dict]:
    """The seat becomes revoked and its token hash is gone, so the token stops working at once.
    With `reopen` the seat goes back to free instead, so the person can rejoin with the link."""
    seat = next((s for s in seats if s["n"] == n), None)
    if seat is None or seat["state"] != "taken":
        raise RoomError("not_taken", "Nobody has taken that seat.")
    fresh = new_seats(n)[n - 1]
    return [fresh if reopen and s["n"] == n else {**s, "state": "revoked", "token_hash": None} if s["n"] == n else s
            for s in seats]


def notes_allowed(state: str) -> bool:
    """Notes are accepted only while the private rooms are open: never in the lobby (M1-04)."""
    return state == "private_rooms"
