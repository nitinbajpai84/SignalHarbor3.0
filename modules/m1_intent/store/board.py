"""The board and the together stage's marks, in the company's own plane (M1-17 to M1-23).

  intents/m1_intent/board/<session id>.json      clusters (note ids only), North's own grouping kept to restore, the
                                                 edit log (who and what, never a note's words), `status` of the grouping
  intents/m1_intent/together/<session id>.json   votes and agree marks by seat, comments, ticked clusters, paused_at
Neither file holds a note's words, an author or a time of a note: notes are read through NoteStore.board (the public
records only). Strict reads (a damaged file is refused and never overwritten), atomic writes, one lock per plane.
"""
import re
import time
from datetime import datetime, timezone

from modules.m1_intent.store.files import UNREADABLE, StoreError, lock_for, read_json, write_json
from modules.m1_intent.store.transcripts import TranscriptStore

_HEX = re.compile(r"[0-9a-f]{32}")
STATUSES = ("none", "done", "failed")
EMPTY = {"votes": {}, "agrees": {}, "comments": {}, "ticked": [], "paused_at": None, "done": [], "touched": []}
_CLUSTER_KEYS = {"id", "name", "note_ids", "source", "pack_problem_id", "reasoning", "colour"}


def _hex(v) -> bool:
    return isinstance(v, str) and _HEX.fullmatch(v) is not None


def _clusters_ok(rows) -> bool:
    return isinstance(rows, list) and all(
        isinstance(c, dict) and (set(c) == _CLUSTER_KEYS or set(c) == _CLUSTER_KEYS - {"colour"})
        and isinstance(c["id"], str) and isinstance(c["name"], str) and isinstance(c["note_ids"], list)
        for c in rows)


class _Files:
    folder = ""

    def __init__(self, plane, clock=time.time):
        self._plane, self._clock = plane, clock

    def _lock(self):
        return lock_for(self._plane.root / ".m1_board")

    def _path(self, sid):
        if not _hex(sid):
            raise StoreError(UNREADABLE)
        return self._plane.path("intents", "m1_intent", self.folder, f"{sid}.json")

    def _now(self) -> str:
        return datetime.fromtimestamp(self._clock(), timezone.utc).isoformat()

    def _save(self, data: dict) -> None:
        write_json(self._path(data["session_id"]), {**data, "updated_at": self._now()})

    def update(self, sid: str, change) -> dict:
        """Read, let `change(data)` return the new data (or raise: nothing is written), write it."""
        with self._lock():
            data = change(self.get(sid))
            self._save(data)
            return data


class BoardStore(_Files):
    folder = "board"

    def get(self, sid: str) -> dict:
        data = read_json(self._path(sid))
        if data is None:
            return {"session_id": sid, "status": "none", "clusters": [], "snapshot": None, "edits": [], "updated_at": None}
        if not (isinstance(data, dict) and data.get("session_id") == sid and data.get("status") in STATUSES
                and _clusters_ok(data.get("clusters")) and (data.get("snapshot") is None or _clusters_ok(data["snapshot"]))
                and isinstance(data.get("edits"), list)):
            raise StoreError(UNREADABLE)
        return data

    def edit(self, sid: str, clusters: list[dict], editor: str, kind: str, **detail) -> dict:
        """Saves edited clusters and records who made the edit and what kind (never a note's words)."""
        def change(d):
            return {**d, "clusters": clusters, "edits": [*d["edits"], {"by": editor, "kind": kind, **detail}]}
        return self.update(sid, change)

    def set_grouping(self, sid: str, status: str, clusters: list[dict], fallback: bool = False) -> dict:
        """North's grouping: kept as the board and, apart, as the one to restore. `fallback`: made without North."""
        def change(d):
            return {**d, "status": status, "fallback": fallback, "clusters": clusters,
                    "snapshot": clusters if status == "done" else d["snapshot"]}
        return self.update(sid, change)


class TogetherStore(_Files):
    folder = "together"

    def get(self, sid: str) -> dict:
        data = read_json(self._path(sid))
        if data is None:
            return {"session_id": sid, "updated_at": None, **{k: type(v)() for k, v in EMPTY.items()}}
        if isinstance(data, dict):
            data = {"done": [], "touched": [], **data}  # files written before "I'm done" and the vote rule have no such lists
        if not (isinstance(data, dict) and data.get("session_id") == sid and set(data) == {"session_id", "updated_at", *EMPTY}
                and isinstance(data["done"], list) and isinstance(data["touched"], list)
                and all(isinstance(data[k], dict) for k in ("votes", "agrees", "comments")) and isinstance(data["ticked"], list)):
            raise StoreError(UNREADABLE)
        return data


def counts(plane, sid: str, submitted: int) -> dict:
    """Counts only, for the organiser while the rooms are open: notes submitted, notes still drafts, people writing."""
    drafts = writing = 0
    transcripts = TranscriptStore(plane)
    for seat in transcripts.seats(sid):
        try:
            mine = sum(1 for n in transcripts.load(sid, seat)["notes"] if n.get("state") == "draft")
        except StoreError:  # one damaged transcript must not hide the counts of the others
            continue
        drafts += mine
        writing += mine > 0
    return {"submitted": submitted, "drafts": drafts, "people_with_drafts": writing}
