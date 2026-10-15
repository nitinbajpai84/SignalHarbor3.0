"""The session's stages and the moves between them, in ONE table (M1-03 to M1-30, pause: M1-23).

Later packages add behaviour to these moves, never new states. Pure Python; no storage here.
Stage order follows the spec: draft, lobby, briefing, private rooms, board (only after the rooms close),
together, signing, closed. A paused session remembers where it stopped and resumes only there.
"""
STAGES = ("draft", "lobby", "briefing", "private_rooms", "board", "together", "signing")
STATES = (*STAGES, "paused", "closed")

_MOVES = {
    "draft": {"lobby"},                                    # starting the session is M1-P02
    "lobby": {"briefing", "paused"},
    "briefing": {"private_rooms", "paused"},
    "private_rooms": {"board", "paused"},
    "board": {"together", "paused"},
    "together": {"signing", "paused"},
    "signing": {"closed", "together", "paused"},           # the approver can send the charter back
    "paused": set(),                                       # only back to where it stopped: see can_move
    "closed": set(),
}
ALLOWED: dict[str, tuple[str, ...]] = {s: tuple(t for t in STATES if t in _MOVES[s]) for s in STATES}


class IllegalMove(ValueError):
    """The move is not allowed; the message is plain words for the screen."""


def can_move(state: str, to: str, paused_from: str | None = None) -> bool:
    if state == "paused":
        return paused_from is not None and to == paused_from
    return to in ALLOWED.get(state, ())


def move(session: dict, to: str) -> dict:
    """A copy of the session at its new state; raises IllegalMove. Only `state` and `paused_from` change."""
    state, paused_from = session["state"], session.get("paused_from")
    if not can_move(state, to, paused_from):
        raise IllegalMove("The session cannot move there from where it is now.")
    return {**session, "state": to, "paused_from": state if to == "paused" else None}
