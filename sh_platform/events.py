"""Event bus. A fact happened (a job changed state, an Action badge moved); consumers hear about it.

- simple: in-process. `publish` calls the matching subscribers at once and keeps the last 500 events for the stream.
- production: transactional outbox. `publish(..., conn=)` inserts a row in the caller's own Postgres transaction, so the fact and the
  event commit together or not at all. `dispatch_once()` (run by tools/worker.py) hands each row to every matching consumer once:
  a (consumer, event) row in sh_outbox_done is written in the same savepoint as the consumer runs, so a consumer that has finished
  an event is never called for it again. A consumer that raises is retried on the next pass,
  up to 20 passes; after that the row stays undispatched (attempts = 20) so one bad event cannot block the rest.

Event: {id, topic, payload, at}. Topics used: job.<state>, badge.action. A payload that belongs to a company carries company_id.
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone

from sh_platform import mode as _mode

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MemoryBus:
    def __init__(self):
        self.subs: list[tuple[str, str, object]] = []
        self.ring, self.seq, self.lock = deque(maxlen=500), itertools.count(1), threading.Lock()

    def subscribe(self, consumer: str, prefix: str, fn) -> None:
        self.subs.append((consumer, prefix, fn))

    def publish(self, topic: str, payload: dict, conn=None) -> int:
        with self.lock:
            ev = {"id": next(self.seq), "topic": topic, "payload": payload, "at": _now()}
            self.ring.append(ev)
        for _, prefix, fn in list(self.subs):
            if topic.startswith(prefix):
                try:
                    fn(ev)
                except Exception:
                    log.exception("event consumer failed for %s", topic)
        return ev["id"]

    def since(self, after: int = 0, limit: int = 100) -> list[dict]:
        with self.lock:
            return [e for e in self.ring if e["id"] > after][-limit:]

    def latest(self) -> int:
        with self.lock:
            return self.ring[-1]["id"] if self.ring else 0

    def dispatch_once(self, limit: int = 50) -> int:
        return 0  # simple mode dispatches inside publish


class PgBus:
    """Connections come from the shared pool (state.pg), so the web and the worker stay far under Postgres's max_connections."""

    def __init__(self, url: str):
        self.url, self.subs, self.ready = url, [], False

    def connect(self):
        from sh_platform.state import pg
        if not self.ready:
            with pg(self.url) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS sh_outbox (id bigserial PRIMARY KEY, topic text NOT NULL, payload jsonb NOT NULL, "
                             "created_at timestamptz NOT NULL DEFAULT now(), dispatched_at timestamptz, attempts int NOT NULL DEFAULT 0)")
                conn.execute("CREATE TABLE IF NOT EXISTS sh_outbox_done (consumer text NOT NULL, event_id bigint NOT NULL, "
                             "PRIMARY KEY (consumer, event_id))")
            self.ready = True
        return pg(self.url)

    def subscribe(self, consumer: str, prefix: str, fn) -> None:
        self.subs.append((consumer, prefix, fn))

    def publish(self, topic: str, payload: dict, conn=None) -> int:
        from psycopg.types.json import Jsonb
        sql = "INSERT INTO sh_outbox (topic, payload) VALUES (%s, %s) RETURNING id"
        if conn is not None:  # the caller's transaction: the caller commits
            return conn.execute(sql, (topic, Jsonb(payload))).fetchone()[0]
        with self.connect() as c:
            return c.execute(sql, (topic, Jsonb(payload))).fetchone()[0]

    def since(self, after: int = 0, limit: int = 100) -> list[dict]:
        with self.connect() as c:
            rows = c.execute("SELECT id, topic, payload, created_at FROM sh_outbox WHERE id > %s ORDER BY id LIMIT %s", (after, limit)).fetchall()
        return [{"id": r[0], "topic": r[1], "payload": r[2], "at": r[3].isoformat(timespec="seconds")} for r in rows]

    def latest(self) -> int:
        with self.connect() as c:
            return c.execute("SELECT coalesce(max(id), 0) FROM sh_outbox").fetchone()[0]

    def dispatch_once(self, limit: int = 50) -> int:
        """Hand pending events to the consumers. Returns how many events are now fully dispatched."""
        done = 0
        with self.connect() as c:
            rows = c.execute("SELECT id, topic, payload, created_at FROM sh_outbox WHERE dispatched_at IS NULL AND attempts < 20 ORDER BY id "
                             "FOR UPDATE SKIP LOCKED LIMIT %s", (limit,)).fetchall()
            for id_, topic, payload, at in rows:
                ev, ok = {"id": id_, "topic": topic, "payload": payload, "at": at.isoformat(timespec="seconds")}, True
                for consumer, prefix, fn in self.subs:
                    if not topic.startswith(prefix):
                        continue
                    try:
                        with c.transaction():  # a savepoint: a failing consumer undoes only its own done row
                            first = c.execute("INSERT INTO sh_outbox_done (consumer, event_id) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING 1",
                                              (consumer, id_)).fetchone()
                            if first:
                                fn(ev)
                    except Exception:
                        log.exception("event consumer %s failed for %s", consumer, topic)
                        ok = False
                if ok:
                    c.execute("UPDATE sh_outbox SET dispatched_at = now() WHERE id = %s", (id_,))
                    done += 1
                else:
                    c.execute("UPDATE sh_outbox SET attempts = attempts + 1 WHERE id = %s", (id_,))
            c.execute("DELETE FROM sh_outbox WHERE dispatched_at < now() - interval '7 days'")
        return done


_BUS = None


def bus():
    global _BUS
    if _BUS is None:
        _BUS = PgBus(os.environ["DATABASE_URL"]) if _mode.production() else MemoryBus()
    return _BUS


def reset() -> None:
    """Tests: forget the bus so the next call builds the one for the mode then."""
    global _BUS
    _BUS = None


def publish(topic: str, payload: dict, conn=None) -> int | None:
    """Publish; never raises. A broken event path must not undo the work that was just done."""
    try:
        return bus().publish(topic, payload, conn)
    except Exception:
        log.exception("could not publish %s", topic)
        return None


def badge(company_id: str, kind: str = "action", **more) -> None:
    """Something changed that moves a badge (Action: a new assignment). The screen re-reads its count when it hears this."""
    publish("badge." + kind, {"company_id": company_id, **more})


def wait_for(after: int, timeout: float = 25.0, poll: float = 1.0) -> list[dict]:
    """New events after id `after`; waits up to `timeout` seconds for the first one."""
    end = time.monotonic() + timeout
    while True:
        got = bus().since(after)
        if got or time.monotonic() >= end:
            return got
        time.sleep(poll)
