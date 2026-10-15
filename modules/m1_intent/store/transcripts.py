"""One private transcript per seat (M1-08, M1-29 skeleton), with the note drafts made from it.

intents/m1_intent/transcripts/<session_id>/<seat_id>.json in the company's own plane. Strict reads (a damaged
or foreign file is refused and never overwritten), atomic writes, one lock per file. Who may read a transcript
is decided by the API (the author; a company admin only when the author has no anonymous notes: D-016, A-031). Nothing here
names the person: the file holds the seat id only.
"""
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from modules.m1_intent.store.files import NOT_SAVED, UNREADABLE, StoreError, lock_for, read_json, write_json

_HEX = re.compile(r"[0-9a-f]{32}")
_KEYS = {"session_id", "seat_id", "turns", "notes", "updated_at"}


def _hex(v) -> bool:
    return isinstance(v, str) and _HEX.fullmatch(v) is not None


class TranscriptStore:
    def __init__(self, plane, clock=time.time):
        self._plane, self._clock = plane, clock

    def _path(self, session_id, seat_id) -> Path:
        if not (_hex(session_id) and _hex(seat_id)):
            raise StoreError(NOT_SAVED)
        return self._plane.path("intents", "m1_intent", "transcripts", session_id, f"{seat_id}.json")

    def _empty(self, session_id, seat_id) -> dict:
        return {"session_id": session_id, "seat_id": seat_id, "turns": [], "notes": [], "updated_at": None}

    def _read(self, path: Path, session_id, seat_id) -> dict:
        data = read_json(path)
        if data is None:
            return self._empty(session_id, seat_id)
        if not (isinstance(data, dict) and set(data) == _KEYS and data["session_id"] == session_id
                and data["seat_id"] == seat_id and isinstance(data["turns"], list) and isinstance(data["notes"], list)
                and all(isinstance(x, dict) and isinstance(x.get("id"), str) for x in (*data["turns"], *data["notes"]))):
            raise StoreError(UNREADABLE)
        return data

    def _lock(self):
        # ponytail: one lock per company plane (resolving a path while another thread replaces a file beside it
        # can fail on Windows); per-seat locks if posts ever need to run in parallel across seats.
        return lock_for(self._plane.root / ".m1_transcripts")

    def seats(self, session_id) -> list[str]:
        """The seat ids that have a transcript in this session (for the rooms-end submit and retention)."""
        folder = self._path(session_id, "0" * 32).parent
        return sorted(f.stem for f in folder.glob("*.json") if _hex(f.stem)) if folder.is_dir() else []

    def load(self, session_id, seat_id) -> dict:
        with self._lock():
            return self._read(self._path(session_id, seat_id), session_id, seat_id)

    def update(self, session_id, seat_id, change: Callable[[dict], None]) -> dict:
        """Read, let `change` edit the transcript in place, write. If `change` raises nothing is written."""
        with self._lock():
            path = self._path(session_id, seat_id)
            data = self._read(path, session_id, seat_id)
            change(data)
            data["updated_at"] = datetime.fromtimestamp(self._clock(), timezone.utc).isoformat()
            write_json(path, data)
            return data
