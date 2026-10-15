"""The stage timer (M1-14). Pure: times are UTC epoch seconds, the clock is passed in, nothing is stored here.

Briefing, private rooms and together have a time from the session's split; other stages have no timer.
The server is the one source of truth for time: the screens only show what these functions return.
"""
import math
from datetime import datetime, timedelta, timezone

PART_OF_STAGE = {"briefing": "briefing", "private_rooms": "individual", "together": "together"}
AUTO_MOVE = {"briefing": "private_rooms", "private_rooms": "board", "together": "signing"}  # LI-M1: every timed stage ends by itself


def is_timed(stage: str) -> bool:
    return stage in PART_OF_STAGE


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def parse(text: str) -> float:
    return datetime.fromisoformat(text).timestamp()


def ends_at(stage: str, split: dict, started_at: float, extensions: list[dict]) -> float:
    """Start plus the stage's minutes, then each extension in turn adds its minutes to the later of the current end
    and the moment it was made (so extending a stage that is already over gives that many minutes from then).
    Never shortens. Raises KeyError for a stage with no timer."""
    end = started_at + 60 * split[PART_OF_STAGE[stage]]
    for e in extensions:
        end = max(end, parse(e["at"]) if "at" in e else end) + 60 * e["minutes"]
    return end


def window_minutes(start: float, working_days: int) -> int:
    """Minutes from `start` to the same time of day `working_days` working days later (Monday to Friday, no holidays; UTC)."""
    day, left = datetime.fromtimestamp(start, timezone.utc), working_days
    while left:
        day += timedelta(days=1)
        left -= day.weekday() < 5
    return math.ceil((day.timestamp() - start) / 60)


def status(now: float, end: float, warning_seconds: int) -> str:
    """running, warning (the last `warning_seconds`), or over."""
    left = end - now
    return "over" if left <= 0 else "warning" if left <= warning_seconds else "running"


def on_rooms_end(session: dict) -> None:
    """Called once when the private rooms end, before the stage moves on. The notes written so far are submitted
    by the caller just before this (store/notes.py submit_all, M1-P05); here the stage move is all that happens."""
