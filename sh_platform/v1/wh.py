"""The company warehouse for Signal Harbor v2.0: one DuckDB file per company, schema = the v2 data model.

Every v2 card reads and writes the warehouse through `connect(plane)`; nobody opens the file another way.
The schema comes from `docs/v2/evidence-to-action-mvp.dbml`. Once card E0a lands, `e0a_catalogue.apply(plane)`
creates and migrates it (core plus approved company extensions); until then the generated
`docs/v2/evidence-to-action-mvp.duckdb.sql` is applied. Both are idempotent (CREATE TABLE IF NOT EXISTS / add-only).

Facts are append-only: a correction is a new row that points to the row it supersedes, with `recorded_at` set to now.
"""
from __future__ import annotations

import atexit
import contextlib
import contextvars
import logging
import os
import sys
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb

from sh_platform.jsonfile import read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
REPO = Path(__file__).resolve().parents[2]
STATIC_DDL = REPO / "docs" / "v2" / "evidence-to-action-mvp.duckdb.sql"
_READY: set[str] = set()
_LOCK = threading.Lock()
_SHARED: dict[str, duckdb.DuckDBPyConnection] = {}  # server mode: one read-write connection per company file, held open
_SERVING = False
_DAY: contextvars.ContextVar = contextvars.ContextVar("cycle_date", default=None)  # the cycle date of the company this request/thread works for (None = the real clock); per request, never shared between companies
_TRIES, _WAIT = 6, 0.5  # a busy file is tried again for about three seconds
_PROD_TRIES = 60  # production: the worker and the web processes take turns on the file, so wait up to 30 s for a turn
_USERS: dict[str, int] = {}  # production: open leases on each shared connection


class Busy(RuntimeError):
    """The warehouse file is held by another program (DuckDB allows one writing process per file)."""


def path(plane) -> Path:
    """data/<company>/warehouse/evidence.duckdb"""
    return plane.path("warehouse", "evidence.duckdb")


def _ensure_schema(plane, con: duckdb.DuckDBPyConnection) -> None:
    try:
        from sh_platform.v1 import e0a_catalogue  # E0a owns migrations once it exists
        if hasattr(e0a_catalogue, "apply"):
            e0a_catalogue.apply(plane)
            return
    except ImportError:
        pass
    con.execute(STATIC_DDL.read_text(encoding="utf-8"))


def _owner_file(key: str) -> Path:
    return Path(key + ".server")


def _busy(e: Exception) -> bool:
    m = str(e)
    return "being used by another process" in m or "process cannot access" in m or "Could not set lock" in m


def _utc(con):
    """Every warehouse session runs in UTC, so cast(max(received_at) as date) never lands a day late on a UTC+7 machine."""
    con.execute("set TimeZone = 'UTC'")
    return con


def _open(key: str) -> duckdb.DuckDBPyConnection:
    """duckdb.connect, a busy file tried again briefly; still busy, a plain Busy naming who holds it."""
    from sh_platform import mode
    tries = _PROD_TRIES if mode.production() else _TRIES
    for attempt in range(tries):
        try:
            return _utc(duckdb.connect(key))
        except duckdb.Error as e:
            if not _busy(e):
                raise
            if attempt < tries - 1:
                time.sleep(_WAIT)
    owner = _owner_file(key)
    who = owner.read_text(encoding="utf-8").strip() if owner.exists() else ""
    raise Busy(f"The company warehouse {key} is open in another program"
               + (f": {who}. Stop the server, or do this through the app, and try again." if who else
                  ", most likely the Signal Harbor server. Stop the server, or do this through the app, and try again.")) from None


def serve() -> None:
    """Server mode, called once at server start: the process keeps one read-write connection per company file and every
    `connect` is a cursor on it, so request threads, the scheduler and background jobs never open the file twice."""
    global _SERVING
    _SERVING = True


def release() -> None:
    """Close the shared connections (server stop, tests) and leave server mode."""
    global _SERVING
    with _LOCK:
        _SERVING = False
        for key, con in _SHARED.items():
            try:
                con.close()
            finally:
                _owner_file(key).unlink(missing_ok=True)
        _SHARED.clear()
        _USERS.clear()


atexit.register(release)


class _Lease:
    """Production mode (several web processes and the worker on one data volume): a cursor on the shared connection. When the last
    lease in this process closes, the file is closed too, so the worker and the other web processes can take their turn; DuckDB lets
    only one process hold the file. ponytail: turn-taking, not sharing; a long pipeline run makes readers wait (up to 30 s). A warehouse
    that many processes use at once needs a server database (Postgres or MotherDuck) instead of a DuckDB file."""

    def __init__(self, key: str, cur):
        self._key, self._cur = key, cur

    def __getattr__(self, name):
        return getattr(self.__dict__.get("_cur"), name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self) -> None:
        cur, self._cur = self.__dict__.get("_cur"), None
        if cur is None:
            return
        cur.close()
        with _LOCK:
            _USERS[self._key] = left = _USERS.get(self._key, 1) - 1
            if left <= 0 and self._key in _SHARED:
                try:
                    _SHARED.pop(self._key).close()
                finally:
                    _owner_file(self._key).unlink(missing_ok=True)

    def __del__(self):
        try:
            self.close()
        except Exception:  # noqa: BLE001 - interpreter shutdown
            pass


def connect(plane, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """A connection to the company warehouse, schema ensured once per process. Close it when done
    (`with wh.connect(plane) as con:`). In the server it is a cursor on the one shared connection (closing it leaves
    the shared one open); elsewhere a connection of its own. A file held by another program raises Busy."""
    p = path(plane)
    key = str(p)
    use(plane)
    with _LOCK:
        if key not in _READY:
            p.parent.mkdir(parents=True, exist_ok=True)
            with _open(key) as con:
                _ensure_schema(plane, con)
            _READY.add(key)
        # A uvicorn process is a server even when the scheduler (which calls serve()) is off, as in tools/serve_test.py:
        # without the shared connection, parallel requests open the file twice and DuckDB refuses ("Unique file handle
        # conflict"). ponytail: keyed on uvicorn being imported; app startup calling serve() itself is the cleaner switch.
        if _SERVING or "uvicorn" in sys.modules:
            if key not in _SHARED:
                _SHARED[key] = _open(key)
                _owner_file(key).write_text(f"the Signal Harbor server (process {os.getpid()}, started {now():%Y-%m-%d %H:%M} UTC)",
                                            encoding="utf-8")
            # DuckDB refuses a read-only and a read-write connection to the same file in one process, so every
            # connection is read-write; `read_only` is kept for callers and ignored. Writers stay append-only by rule.
            from sh_platform import mode
            if mode.production():
                _USERS[key] = _USERS.get(key, 0) + 1
                return _Lease(key, _utc(_SHARED[key].cursor()))
            return _utc(_SHARED[key].cursor())
    return _open(key)


@contextlib.contextmanager
def held(plane):
    """Production: keep the company file open for a block that makes many `connect` calls. Each lease closes the file when the last one
    ends, so every query after it reopened the file (about 70 ms each, and a wait while the worker holds it). A lease held here keeps the
    shared connection open for the block. Simple mode and the scripts (no shared connection) do nothing."""
    from sh_platform import mode
    if not mode.production() or not (_SERVING or "uvicorn" in sys.modules):
        yield
        return
    lease = connect(plane)
    try:
        yield
    finally:
        lease.close()


def new_id() -> str:
    return str(uuid.uuid4())


def _demo_file(plane) -> Path:
    return plane.path("settings", "demo_today.json")


def demo_today(plane) -> date | None:
    """The company setting demo_today (settings/demo_today.json = {"demo_today": "YYYY-MM-DD"}), or None when unset or unreadable."""
    try:
        got = read_json_strict(_demo_file(plane), dict)
        return date.fromisoformat(got["demo_today"]) if got and got.get("demo_today") else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def set_demo_today(plane, day: date | None) -> None:
    """Pin the company's 'today' (None clears it). Demo data is dated; this keeps the story true on any real day."""
    write_json_atomic(_demo_file(plane), {"demo_today": day.isoformat() if day else None})
    _DAY.set(day)


def use(plane) -> None:
    """Make this plane's company the one whose cycle date `now()` and `today()` answer for, in this request or thread."""
    _DAY.set(demo_today(plane))


def today(plane=None) -> date:
    """The company's business day: its cycle date (the demo_today setting) when set, else the real UTC day. Every business date
    (as-of defaults, due-date checks, schedules) reads this; timestamps of when something happened use now()."""
    return now(plane).date()


def now(plane=None) -> datetime:
    """The current UTC time; with a demo_today setting, a clock that stays inside that day: 23:00 UTC on it plus the real
    time since the day began, slowed 1000 times (one real day moves it 86 s), so 'today' never flips and later writes
    still sort after earlier ones. Pass `plane` to read its setting; without it the company this request or thread
    last connected to applies (a context variable, so two companies never share a day). ponytail: after about 41 real
    days the clock holds at the day's end."""
    real = datetime.now(timezone.utc)
    day = demo_today(plane) if plane is not None else _DAY.get()
    if not day:
        return real
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    return min(start + timedelta(hours=23) + (real - start) / 1000, datetime.combine(day, datetime.max.time(), tzinfo=timezone.utc))


def reset_cache() -> None:
    """Tests: forget which warehouses were prepared (a tmp plane gets a fresh file)."""
    release()
    with _LOCK:
        _READY.clear()
