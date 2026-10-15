"""Process record: the two-way link between a module session and its outcome (D-026).

Starting a process creates, in ONE write, a session id and an outcome id side by
side, both "in progress". So a session never exists without its outcome record,
and the reverse. From an outcome you find the session it came from
(get_by_outcome); from a session, started or paused, you land on its current
state, or on the outcome once that is completed (landing_for).

Only ids, module id, kind, states, timestamps and the label are stored here. The
actual content lives elsewhere in the company plane. A
completed outcome is read-only. The store is bound to one CompanyPlane and takes
no company id anywhere; an unreadable file is never overwritten.

Limit: the lock covers threads in ONE process only (the same limit as the
accounts store). A second writer process sharing a plane needs a file lock first.
"""
import os
import re
import secrets
import unicodedata
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CrossCompanyError

SESSION_STATES = ("in_progress", "paused", "completed")  # extend here, not per module
OUTCOME_STATES = ("in_progress", "completed")
_MOVES = {("in_progress", "paused"), ("paused", "in_progress"),
          ("in_progress", "completed"), ("paused", "completed")}
_NAME = re.compile(r"[a-z0-9_]{1,40}")
_HEX = re.compile(r"[0-9a-f]{16,64}")
_BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Zl", "Zp")  # control, format (bidi, zero-width), surrogate, separators
_FIELDS = ("session_id", "outcome_id", "module_id", "kind", "label",
           "session_state", "outcome_state", "started_at", "updated_at")
_UNREADABLE = "The process records could not be read."


class ProcessRecordError(Exception):
    """Plain-words failure; never contains a path or an id."""


@dataclass(frozen=True)
class ProcessRecord:
    session_id: str
    outcome_id: str
    module_id: str
    kind: str
    label: str | None
    session_state: str
    outcome_state: str
    started_at: str
    updated_at: str


@dataclass(frozen=True)
class Landing:
    kind: str  # "outcome" or "session"
    outcome_id: str | None = None
    session_id: str | None = None
    state: str | None = None
    ready: bool | None = None


def _name_ok(v) -> bool:
    return type(v) is str and _NAME.fullmatch(v) is not None


def _label_ok(v) -> bool:
    return v is None or (type(v) is str and len(v) <= 120
                         and not any(unicodedata.category(c) in _BAD_CATEGORIES for c in v))


def _valid_row(row) -> bool:
    if type(row) is not dict or set(row) != set(_FIELDS):
        return False
    s = [row[k] for k in _FIELDS if k not in ("label", "module_id", "kind")]
    return (all(type(v) is str for v in s)
            and _HEX.fullmatch(row["session_id"]) is not None
            and _HEX.fullmatch(row["outcome_id"]) is not None
            and _name_ok(row["module_id"]) and _name_ok(row["kind"]) and _label_ok(row["label"])
            and row["session_state"] in SESSION_STATES and row["outcome_state"] in OUTCOME_STATES
            and (row["outcome_state"] != "completed" or row["session_state"] == "completed"))


def _find(rows: list[dict], key: str, value) -> int | None:
    if type(value) is not str or not _HEX.fullmatch(value):
        return None
    return next((i for i, r in enumerate(rows) if r[key] == value), None)


class ProcessRecords:
    def __init__(self, plane, clock=time.time):
        self._plane = plane
        self._clock = clock

    def _path(self) -> Path:
        # resolved on every operation: a context folder swapped for a link later is refused
        path = self._plane.path("context", "process_records.json")
        want = self._plane.root.resolve() / "context" / "process_records.json"
        # the file itself must not be a link, and must sit exactly where expected
        if path.is_symlink() or os.path.normcase(str(path)) != os.path.normcase(str(want)):
            raise CrossCompanyError("path outside company plane")
        return path

    def _now(self) -> str:
        return datetime.fromtimestamp(self._clock(), timezone.utc).isoformat()

    def _read(self, path: Path) -> list[dict]:
        try:
            data = read_json_strict(path, dict)
            if data is None:
                return []
            rows = data["records"]
        except (OSError, ValueError, KeyError, TypeError):
            raise ProcessRecordError(_UNREADABLE) from None
        if type(rows) is not list or not all(_valid_row(r) for r in rows):
            raise ProcessRecordError(_UNREADABLE)
        ids = [r[k] for r in rows for k in ("session_id", "outcome_id")]
        if len(set(ids)) != len(ids):  # a duplicate id means the file is damaged
            raise ProcessRecordError(_UNREADABLE)
        return rows

    def _write(self, path: Path, rows: list[dict]) -> None:
        try:
            write_json_atomic(path, {"records": rows})
        except OSError:
            raise ProcessRecordError("The process records could not be saved.") from None

    def _locked(self):
        path = self._path()
        return path, lock_for(path)

    def start(self, module_id, kind, label=None) -> ProcessRecord:
        if not (_name_ok(module_id) and _name_ok(kind)):
            raise ProcessRecordError("The module or kind is not valid.")
        if not _label_ok(label):
            raise ProcessRecordError("The label is not valid.")
        now = self._now()
        row = dict(session_id=secrets.token_hex(16), outcome_id=secrets.token_hex(16),
                   module_id=module_id, kind=kind, label=label,
                   session_state="in_progress", outcome_state="in_progress",
                   started_at=now, updated_at=now)
        path, lock = self._locked()
        with lock:
            rows = self._read(path)
            self._write(path, rows + [row])
        return ProcessRecord(**row)

    def get_by_session(self, session_id) -> ProcessRecord | None:
        return self._get("session_id", session_id)

    def get_by_outcome(self, outcome_id) -> ProcessRecord | None:
        return self._get("outcome_id", outcome_id)

    def _get(self, key, value) -> ProcessRecord | None:
        path, lock = self._locked()
        with lock:
            rows = self._read(path)
        i = _find(rows, key, value)
        return None if i is None else ProcessRecord(**rows[i])

    def list(self, module_id=None, session_state=None, outcome_state=None) -> list[ProcessRecord]:
        path, lock = self._locked()
        with lock:
            rows = self._read(path)
        return [ProcessRecord(**r) for r in reversed(rows)
                if module_id in (None, r["module_id"])
                and session_state in (None, r["session_state"])
                and outcome_state in (None, r["outcome_state"])]

    def landing_for(self, session_id) -> Landing | None:
        r = self.get_by_session(session_id)
        if r is None:
            return None
        if r.outcome_state == "completed":
            return Landing("outcome", outcome_id=r.outcome_id, ready=True)
        return Landing("session", session_id=r.session_id, state=r.session_state)

    def set_session_state(self, session_id, state) -> ProcessRecord:
        path, lock = self._locked()
        with lock:
            rows = self._read(path)
            i = _find(rows, "session_id", session_id)
            if i is None:
                raise ProcessRecordError("That session was not found.")
            if (rows[i]["outcome_state"] == "completed" or type(state) is not str
                    or (rows[i]["session_state"], state) not in _MOVES):
                raise ProcessRecordError("That session cannot move to that state.")
            rows[i] = {**rows[i], "session_state": state, "updated_at": self._now()}
            self._write(path, rows)
            return ProcessRecord(**rows[i])

    def complete_outcome(self, outcome_id) -> ProcessRecord:
        path, lock = self._locked()
        with lock:
            rows = self._read(path)
            i = _find(rows, "outcome_id", outcome_id)
            if i is None:
                raise ProcessRecordError("That outcome was not found.")
            if rows[i]["outcome_state"] == "completed":
                raise ProcessRecordError("That outcome is already completed.")
            rows[i] = {**rows[i], "outcome_state": "completed",
                       "session_state": "completed", "updated_at": self._now()}
            self._write(path, rows)
            return ProcessRecord(**rows[i])
