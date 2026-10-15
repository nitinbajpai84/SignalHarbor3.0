"""Sessions and templates in the company plane's `intents` area (M1-29 skeleton).

intents/m1_intent/sessions/<id>.json   one file per session
intents/m1_intent/index.json           a small list of my sessions (id, owner, state, label)
intents/m1_intent/templates.json       reusable preparation values
Every path comes from the plane and every id is checked before it is used in a path. Nothing about people's
notes is stored here yet. The process record (D-026) is created at the first save and mirrors the state.
"""
import logging
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from modules.m1_intent.domain.preparation import KEYS, with_defaults
from modules.m1_intent.domain.timer import window_minutes
from modules.m1_intent.domain.states import STAGES, STATES, IllegalMove, move
from modules.m1_intent.store.files import UNREADABLE, StoreError, WrongState, lock_for, read_json, write_json
from sh_platform.process_record import ProcessRecordError, ProcessRecords

log = logging.getLogger(__name__)
_HEX = re.compile(r"[0-9a-f]{32}")
_SESSION_KEYS = {"id", "organiser_account_id", "state", "paused_from", "preparation", "record_session_id",
                 "outcome_id", "created_at", "updated_at", "inputs"}
NO_INPUTS = {"actions": 0, "free_text": 0, "cards_confirmed": 0, "cards_new": 0, "cards_sealed": 0}  # LI-M1: how many things people did and typed in this session, never what
_INDEX_KEYS = {"id", "organiser_account_id", "state", "label", "seats", "outcome_id", "updated_at"}  # and "topic" (an older index has none)
_OPEN = ("lobby", "briefing", "private_rooms", "board", "together", "signing", "paused")  # a wall that is running: not a draft, not closed
_TEMPLATE_KEYS = {"id", "name", "preparation", "created_at"}
_MIRROR = {"paused": "paused", "closed": "completed"}  # every other stage is "in progress"
_STARTED = "This session has already started, so its preparation can no longer be changed."


def _hex(v) -> bool:
    return isinstance(v, str) and _HEX.fullmatch(v) is not None


def _label(prep: dict) -> str:
    return " ".join(prep["purpose"].split())[:120]


class SessionStore:
    def __init__(self, plane, clock=time.time):
        self._plane, self._clock = plane, clock

    # ---- paths and files
    def _dir(self) -> Path:
        return self._plane.path("intents", "m1_intent")

    def _session_path(self, session_id: str) -> Path:
        return self._plane.path("intents", "m1_intent", "sessions", f"{session_id}.json")

    def _now(self) -> str:
        return datetime.fromtimestamp(self._clock(), timezone.utc).isoformat()

    def _lock(self):
        return lock_for(self._dir())

    def _read_index(self) -> list[dict]:
        data = read_json(self._dir() / "index.json")
        if data is None:
            return []
        rows = data.get("sessions") if isinstance(data, dict) else None
        if not isinstance(rows, list) or not all(
                isinstance(r, dict) and set(r) - {"topic"} == _INDEX_KEYS and _hex(r["id"]) and _hex(r["outcome_id"])
                and r["state"] in STATES and isinstance(r["label"], str) and isinstance(r["organiser_account_id"], str)
                for r in rows):
            raise StoreError(UNREADABLE)
        return rows

    def _write_index(self, rows: list[dict]) -> None:
        write_json(self._dir() / "index.json", {"sessions": rows})

    @staticmethod
    def _entry(s: dict) -> dict:
        return {"id": s["id"], "organiser_account_id": s["organiser_account_id"], "state": s["state"],
                "label": _label(s["preparation"]), "topic": s["preparation"]["topic"], "seats": s["preparation"]["seats"],
                "outcome_id": s["outcome_id"], "updated_at": s["updated_at"]}

    def _read(self, session_id) -> dict | None:
        if not _hex(session_id):
            return None
        s = read_json(self._session_path(session_id))
        if s is None:
            return None
        if isinstance(s, dict):
            s = {**s, "inputs": {**NO_INPUTS, **(s.get("inputs") or {})}, "preparation": with_defaults(s.get("preparation"))}  # an older session has fewer counters
        if not (isinstance(s, dict) and set(s) == _SESSION_KEYS and s["id"] == session_id and s["state"] in STATES
                and (s["paused_from"] is None or s["paused_from"] in STAGES) and _hex(s["record_session_id"])
                and _hex(s["outcome_id"]) and isinstance(s["organiser_account_id"], str)
                and isinstance(s["preparation"], dict) and set(s["preparation"]) == set(KEYS)
                and isinstance(s["inputs"], dict) and set(s["inputs"]) == set(NO_INPUTS)
                and all(type(v) is int and v >= 0 for v in s["inputs"].values())):
            raise StoreError(UNREADABLE)
        return s

    def _save(self, s: dict, index: list[dict]) -> None:
        """The session file first, then the index entry."""
        write_json(self._session_path(s["id"]), s)
        entry = self._entry(s)
        self._write_index([entry if r["id"] == s["id"] else r for r in index]
                          if any(r["id"] == s["id"] for r in index) else [*index, entry])

    # ---- sessions
    def create(self, organiser_id: str, prep: dict) -> dict:
        with self._lock():
            index = self._read_index()  # a damaged index refuses the save before anything is made
            try:
                rec = ProcessRecords(self._plane, self._clock).start("m1_intent", "charter", _label(prep))
            except ProcessRecordError as e:
                raise StoreError(str(e)) from None
            now = self._now()
            s = {"id": secrets.token_hex(16), "organiser_account_id": organiser_id, "state": "draft",
                 "paused_from": None, "preparation": prep, "record_session_id": rec.session_id,
                 "outcome_id": rec.outcome_id, "created_at": now, "updated_at": now, "inputs": dict(NO_INPUTS)}
            try:
                self._save(s, index)
            except StoreError:
                self._close_record(s)  # do not leave an outcome with no session behind it
                raise
            return s

    def get(self, session_id) -> dict | None:
        with self._lock():
            return self._read(session_id)

    def count(self, session_id, actions: int = 0, free_text: int = 0, cards_confirmed: int = 0,
              cards_new: int = 0, cards_sealed: int = 0) -> None:
        """Adds to the session's input counters (LI-M1). Only numbers are kept. The session file alone is written: its
        update time is the stage clock's fallback start, so it must not move."""
        with self._lock():
            s = self._read(session_id)
            if s is not None:
                write_json(self._session_path(session_id), {**s, "inputs": {"actions": s["inputs"]["actions"] + actions,
                                                                           "free_text": s["inputs"]["free_text"] + free_text,
                                                                           "cards_confirmed": s["inputs"]["cards_confirmed"] + cards_confirmed,
                                                                           "cards_new": s["inputs"]["cards_new"] + cards_new,
                                                                           "cards_sealed": s["inputs"]["cards_sealed"] + cards_sealed}})

    def get_by_outcome(self, outcome_id) -> dict | None:
        if not _hex(outcome_id):
            return None
        with self._lock():
            hit = next((r for r in self._read_index() if r["outcome_id"] == outcome_id), None)
            return self._read(hit["id"]) if hit else None

    def list_for(self, organiser_id: str) -> list[dict]:
        with self._lock():
            rows = [r for r in self._read_index() if r["organiser_account_id"] == organiser_id]
        rows.sort(key=lambda r: r["updated_at"], reverse=True)
        return [{"topic": None, **{k: v for k, v in r.items() if k != "organiser_account_id"}} for r in rows]

    def walls(self) -> list[dict]:
        """Every session of the company that has started (any organiser): id, topic, purpose, state. Newest first."""
        with self._lock():
            rows = [r for r in self._read_index() if r["state"] != "draft"]
            sessions = [s for s in (self._read(r["id"]) for r in rows) if s]
        sessions.sort(key=lambda s: s["updated_at"], reverse=True)
        return [{"id": s["id"], "topic": s["preparation"]["topic"], "purpose": s["preparation"]["purpose"], "state": s["state"]} for s in sessions]

    def check_wall_free(self, session_id: str) -> None:
        """Refuse, in plain words, before anything is written when this draft may not open as a wall yet."""
        with self._lock():
            s = self._read(session_id)
            if s is not None:
                self._check_wall_free(s)

    def _check_wall_free(self, s: dict) -> None:
        """One open wall per topic; a topic is needed once another wall is open."""
        topic = s["preparation"]["topic"]
        others = [r for r in self._read_index() if r["id"] != s["id"] and r["state"] in _OPEN]
        if not others:
            return
        if topic is None:
            raise WrongState("Another wall is already open, so this one needs a topic or department. Please add one.")
        taken = {(o["preparation"]["topic"] or "").casefold() for o in (self._read(r["id"]) for r in others) if o}
        if topic.casefold() in taken:
            raise WrongState("A wall on that topic is already open. Open it, or choose another topic or department.")

    def _mine(self, session_id, organiser_id) -> dict | None:
        s = self._read(session_id)
        return s if s and s["organiser_account_id"] == organiser_id else None

    def update_draft(self, session_id, organiser_id: str, prep: dict) -> dict | None:
        """None when it is not found or not the organiser's. Only a draft can change (M1-01)."""
        with self._lock():
            index = self._read_index()
            s = self._mine(session_id, organiser_id)
            if s is None:
                return None
            if s["state"] != "draft":
                raise WrongState(_STARTED)
            s = {**s, "preparation": prep, "updated_at": self._now()}
            self._save(s, index)
            return s

    def delete_draft(self, session_id, organiser_id: str) -> bool:
        with self._lock():
            index = self._read_index()
            s = self._mine(session_id, organiser_id)
            if s is None:
                return False
            if s["state"] != "draft":
                raise WrongState("This session has already started, so it can no longer be deleted.")
            self._session_path(session_id).unlink(missing_ok=True)
            self._write_index([r for r in index if r["id"] != session_id])
            self._close_record(s)
            return True

    def transition(self, session_id, to: str) -> dict | None:
        """Move along the state table and mirror the new state into the process record."""
        with self._lock():
            index = self._read_index()
            s = self._read(session_id)
            if s is None:
                return None
            was = s["state"]
            if was == "draft" and to == "lobby":
                self._check_wall_free(s)
            try:
                s = {**move(s, to), "updated_at": self._now()}
            except IllegalMove as e:
                raise WrongState(str(e)) from None
            if was == "draft" and to == "lobby" and s["preparation"]["wall_window_days"] is not None:  # the rooms last the wall's window, on the existing timer's split
                p = s["preparation"]
                s = {**s, "preparation": {**p, "split": {**p["split"], "individual": window_minutes(self._clock(), p["wall_window_days"])}}}
            self._mirror(s)
            self._save(s, index)
            if was == "private_rooms" and to == "board":  # every close: timer, organiser, everyone done
                from modules.m1_intent.store.wall_snapshot import freeze
                freeze(self._plane, session_id, datetime.fromtimestamp(self._clock(), timezone.utc))
            return s

    # ---- process record
    def _mirror(self, s: dict) -> None:
        recs = ProcessRecords(self._plane, self._clock)
        try:
            rec = recs.get_by_session(s["record_session_id"])
            target = _MIRROR.get(s["state"], "in_progress")
            if rec is None:
                raise StoreError(UNREADABLE)
            if rec.session_state != target:
                recs.set_session_state(s["record_session_id"], target)
        except ProcessRecordError as e:
            raise StoreError(str(e)) from None

    def landing(self, s: dict) -> dict:
        """Where a person lands from this session: its outcome once that is complete, else its current state."""
        try:
            land = ProcessRecords(self._plane, self._clock).landing_for(s["record_session_id"])
        except ProcessRecordError as e:
            raise StoreError(str(e)) from None
        return {"kind": land.kind, "state": land.state} if land else {"kind": "session", "state": s["state"]}

    def _close_record(self, s: dict) -> None:
        """A withdrawn draft: the session side is completed; the outcome stays as it is (no charter exists)."""
        try:
            ProcessRecords(self._plane, self._clock).set_session_state(s["record_session_id"], "completed")
        except ProcessRecordError:
            log.warning("could not close the process record of a withdrawn draft")

    # ---- templates
    def templates(self) -> list[dict]:
        with self._lock():
            return self._read_templates()

    def _read_templates(self) -> list[dict]:
        data = read_json(self._dir() / "templates.json")
        if data is None:
            return []
        rows = data.get("templates") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise StoreError(UNREADABLE)
        good = []
        for r in rows:  # an old record gets defaults; one that cannot be read is skipped, never failing the list
            r = {**r, "preparation": with_defaults(r.get("preparation"))} if isinstance(r, dict) else r
            if (isinstance(r, dict) and set(r) == _TEMPLATE_KEYS and _hex(r["id"]) and isinstance(r["name"], str)
                    and isinstance(r["preparation"], dict) and set(r["preparation"]) == set(KEYS)):
                good.append(r)
            else:
                log.warning("a saved template could not be read and was skipped")
        return good

    def get_template(self, template_id) -> dict | None:
        return next((t for t in self.templates() if t["id"] == template_id), None)

    def save_template(self, name: str, session_id, organiser_id: str) -> dict | None:
        """Stores the preparation values only. None when the session is not found or not the organiser's."""
        with self._lock():
            rows = self._read_templates()
            s = self._mine(session_id, organiser_id)
            if s is None:
                return None
            t = {"id": secrets.token_hex(16), "name": name, "preparation": s["preparation"],
                 "created_at": self._now()}
            write_json(self._dir() / "templates.json", {"templates": [*rows, t]})
            return t

