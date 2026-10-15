"""Job queue. A job is a named handler plus a JSON payload; the handlers live in `sh_platform/jobs/handlers.py`.

- simple (`LocalQueue`): today's threads. `submit` runs the handler on the spot, so every route and loop behaves as it did.
  `enqueue` runs it on one background thread. Records are kept in memory.
- production (`RedisQueue`): jobs wait in Redis and `tools/worker.py` runs them. A failed job is retried with a doubling wait
  (backoff, backoff*2, ...) until `tries` is used up, then it lands on the failed list, where the admin page can send it again.
  `key` makes an enqueue a no-op while a job with the same key is still waiting or running (one tick per company per minute).

A handler returns a JSON-able result. A handler that raises is retried; one that must not be retried returns a result saying so.
Record: {id, name, payload, key, company_id, state queued|running|retrying|done|failed, tries, max_tries, error, result, queued_at, started_at, finished_at}.
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import queue as _q
import secrets
import threading
import time
from datetime import datetime, timezone

from sh_platform import events, mode as _mode

log = logging.getLogger(__name__)
HANDLERS: dict = {}
KEEP = 500
_SEQ = itertools.count()


def job(name: str):
    def reg(fn):
        HANDLERS[name] = fn
        return fn
    return reg


class JobFailed(Exception):
    """A job a caller waited for did not finish well."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new(name, payload, key, tries) -> dict:
    return {"id": secrets.token_hex(6), "name": name, "payload": payload, "key": key, "company_id": (payload or {}).get("company_id"),
            "state": "queued", "tries": 0, "max_tries": tries, "error": None, "result": None,
            "queued_at": _now(), "started_at": None, "finished_at": None, "seq": next(_SEQ)}


class _Base:
    backoff = 2.0

    def _event(self, rec: dict) -> None:
        events.publish("job." + rec["state"], {"job_id": rec["id"], "name": rec["name"], "state": rec["state"], "tries": rec["tries"],
                                               "company_id": rec["company_id"]})

    def _run(self, rec: dict):
        """Run one attempt. Returns the result; on failure sets retry or failed and returns None."""
        if rec["name"] not in HANDLERS:
            import sh_platform.jobs.handlers  # noqa: F401  (registers the handlers)
        rec["tries"] += 1
        rec.update(state="running", started_at=_now())
        self._save(rec)
        self._event(rec)
        try:
            out = HANDLERS[rec["name"]]({**(rec["payload"] or {}), "_job_id": rec["id"]})  # RUN1: a handler may log its job id
        except Exception as e:
            log.exception("job %s (%s) failed", rec["id"], rec["name"])
            self._attempt_failed(rec, f"{type(e).__name__}: {str(e)[:300]}")
            return None
        rec.update(state="done", result=out, error=None, finished_at=_now())
        self._save(rec)
        self._release(rec)
        self._event(rec)
        return out


    def _attempt_failed(self, rec: dict, error: str) -> None:
        """One attempt failed: retry after the backoff while tries are left, else the failed list."""
        rec["error"] = error
        if rec["tries"] < rec["max_tries"]:
            rec["state"] = "retrying"
            self._save(rec)
            self._event(rec)
            self._later(rec, self.backoff * 2 ** (rec["tries"] - 1))
        else:
            rec.update(state="failed", finished_at=_now())
            self._save(rec)
            self._failed(rec)
            self._release(rec)
            self._event(rec)


class LocalQueue(_Base):
    def __init__(self, backoff: float = 2.0):
        self.backoff, self.recs, self.keys = backoff, {}, set()
        self.q, self.lock, self.thread = _q.Queue(), threading.Lock(), None

    def _save(self, rec):
        with self.lock:
            self.recs[rec["id"]] = rec
            while len(self.recs) > KEEP:
                old = next((k for k, r in self.recs.items() if r["state"] in ("done", "failed")), None)
                if old is None:
                    break
                del self.recs[old]

    def _failed(self, rec):
        pass  # the failed list is every record in state failed

    def _release(self, rec):
        with self.lock:
            self.keys.discard(rec["key"])

    def _later(self, rec, wait):
        threading.Timer(wait, lambda: (self.q.put(rec["id"]), self._worker())).start()

    def _worker(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            self.thread = threading.Thread(target=self._loop, name="job-queue", daemon=True)
            self.thread.start()

    def _loop(self):
        while True:
            try:
                rid = self.q.get(timeout=1.0)
            except _q.Empty:
                return
            try:
                rec = self.recs.get(rid)
                if rec:
                    self._run(rec)
            finally:
                self.q.task_done()

    def enqueue(self, name, payload, *, key=None, tries=3, delay=0.0):
        rec = _new(name, payload, key, tries)
        with self.lock:
            if key and key in self.keys:
                return None
            if key:
                self.keys.add(key)
        self._save(rec)
        self._event(rec)
        if delay:
            self._later(rec, delay)
        else:
            self.q.put(rec["id"])
            self._worker()
        return rec["id"]

    def submit(self, name, payload, *, key=None, tries=1):
        """Simple mode: run it here and now, return the result; an exception goes to the caller as it always did."""
        if name not in HANDLERS:
            import sh_platform.jobs.handlers  # noqa: F401
        rec = _new(name, payload, key, tries)
        rec["tries"] = 1
        rec.update(state="running", started_at=_now())
        self._save(rec)
        try:
            out = HANDLERS[name](payload)
        except BaseException as e:
            rec.update(state="failed", error=f"{type(e).__name__}: {str(e)[:300]}", finished_at=_now())
            self._save(rec)
            raise
        rec.update(state="done", result=out, finished_at=_now())
        self._save(rec)
        return out

    call = submit

    def drain(self, timeout: float = 10.0) -> bool:
        """Wait until nothing is queued or waiting to retry (tests)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.q.unfinished_tasks == 0 and not any(r["state"] in ("queued", "retrying", "running") for r in list(self.recs.values())):
                return True
            time.sleep(0.02)
        return False

    def get(self, jid):
        return self.recs.get(jid)

    def recent(self, n=50):
        return sorted(self.recs.values(), key=lambda r: r["seq"], reverse=True)[:n]

    def failed(self, n=50):
        return [r for r in self.recent(KEEP) if r["state"] == "failed"][:n]

    def stats(self):
        s = {k: 0 for k in ("queued", "running", "retrying", "done", "failed")}
        for r in list(self.recs.values()):
            s[r["state"]] += 1
        return s

    def retry(self, jid):
        with self.lock:  # two clicks must not queue it twice
            rec = self.recs.get(jid)
            if not rec or rec["state"] != "failed":
                return False
            rec.update(state="queued", tries=0, error=None, finished_at=None)
            if rec["key"]:
                self.keys.add(rec["key"])
        self.q.put(jid)
        self._worker()
        return True


class RedisQueue(_Base):
    """Keys: sh:job:<id> (record), sh:jobs:ready (list), sh:jobs:delayed (zset by due time), sh:jobs:failed (list), sh:jobs:all (zset by
    queue time), sh:jobs:key:<key> (unique marker), sh:jobs:running (zset: job id -> lease end).
    A running job holds a lease that its worker renews every LEASE/3 s. A worker that dies stops renewing; the next worker to look for
    work finds the lease run out and counts it as a failed attempt (retry with backoff, or the failed list). ponytail: a worker killed
    between taking a job off the ready list and writing its lease (a few ms) loses that job; BLMOVE into a processing list if it matters."""
    TTL = 7 * 86400
    LEASE = 60.0

    def __init__(self, backoff: float = 2.0, client=None):
        self.backoff, self._c = backoff, client

    @property
    def r(self):
        if self._c is None:
            from sh_platform.state.kv import redis_client
            self._c = redis_client()
        return self._c

    def _save(self, rec):
        self.r.set(f"sh:job:{rec['id']}", json.dumps(rec), ex=self.TTL)
        self.r.zadd("sh:jobs:all", {rec["id"]: time.time()}, nx=True)

    def _failed(self, rec):
        self.r.lpush("sh:jobs:failed", rec["id"])
        self.r.ltrim("sh:jobs:failed", 0, KEEP - 1)

    def _release(self, rec):
        if rec["key"]:
            self.r.delete(f"sh:jobs:key:{rec['key']}")

    def _later(self, rec, wait):
        self.r.zadd("sh:jobs:delayed", {rec["id"]: time.time() + wait})

    def enqueue(self, name, payload, *, key=None, tries=3, delay=0.0):
        rec = _new(name, payload, key, tries)
        if key and not self.r.set(f"sh:jobs:key:{key}", rec["id"], nx=True, ex=3600):
            return None
        self._save(rec)
        self._event(rec)
        if delay:
            self._later(rec, delay)
        else:
            self.r.rpush("sh:jobs:ready", rec["id"])
        return rec["id"]

    def submit(self, name, payload, *, key=None, tries=3):
        """Production: a background job; returns the job id (None when the key is already queued)."""
        return self.enqueue(name, payload, key=key, tries=tries)

    def call(self, name, payload, *, key=None, tries=3, timeout=300.0, poll=0.25):
        """Enqueue and wait for the result. Raises JobFailed when it ends failed, or on timeout."""
        jid = self.enqueue(name, payload, key=key, tries=tries)
        if jid is None:
            raise JobFailed("the same job is already waiting")
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            rec = self.get(jid)
            if rec and rec["state"] == "done":
                return rec["result"]
            if rec and rec["state"] == "failed":
                raise JobFailed(rec["error"])
            time.sleep(poll)
        raise JobFailed("the job did not finish in time")

    def get(self, jid):
        raw = self.r.get(f"sh:job:{jid}")
        return json.loads(raw) if raw else None

    def _run(self, rec):
        jid, stop = rec["id"], threading.Event()
        self.r.zadd("sh:jobs:running", {jid: time.time() + self.LEASE})

        def beat():
            while not stop.wait(self.LEASE / 3):
                try:
                    self.r.zadd("sh:jobs:running", {jid: time.time() + self.LEASE})
                    if rec["key"]:
                        self.r.expire(f"sh:jobs:key:{rec['key']}", 3600)
                except Exception:
                    log.warning("job %s: lease renewal failed", jid)
        threading.Thread(target=beat, name=f"lease-{jid}", daemon=True).start()
        try:
            return super()._run(rec)
        finally:
            stop.set()
            self.r.zrem("sh:jobs:running", jid)

    def sweep(self) -> int:
        """Jobs whose lease ran out (their worker died): count the attempt as failed. Returns how many were found."""
        n = 0
        for jid in self.r.zrangebyscore("sh:jobs:running", 0, time.time()):
            if not self.r.zrem("sh:jobs:running", jid):
                continue  # another worker swept it first
            rec = self.get(jid)
            if rec and rec["state"] == "running":
                log.warning("job %s (%s): its worker stopped; counted as a failed attempt", jid, rec["name"])
                self._attempt_failed(rec, "the worker stopped during the job")
                n += 1
        return n

    def _next(self, wait: float = 1.0):
        """Sweep lapsed leases, move due retries to ready, then take the next job (None when nothing is ready)."""
        self.sweep()
        now = time.time()
        for jid in self.r.zrangebyscore("sh:jobs:delayed", 0, now):
            if self.r.zrem("sh:jobs:delayed", jid):
                self.r.rpush("sh:jobs:ready", jid)
        got = self.r.blpop("sh:jobs:ready", timeout=max(1, int(wait))) if wait else self.r.lpop("sh:jobs:ready")
        jid = got[1] if isinstance(got, (tuple, list)) else got
        return self.get(jid) if jid else None

    def work_once(self, wait: float = 1.0) -> bool:
        rec = self._next(wait)
        if rec:
            self._run(rec)
        return rec is not None

    def recent(self, n=50):
        return [r for r in (self.get(j) for j in self.r.zrevrange("sh:jobs:all", 0, n - 1)) if r]

    def failed(self, n=50):
        return [r for r in (self.get(j) for j in self.r.lrange("sh:jobs:failed", 0, n - 1)) if r and r["state"] == "failed"]

    def stats(self):
        s = {k: 0 for k in ("queued", "running", "retrying", "done", "failed")}
        for r in self.recent(KEEP):
            s[r["state"]] += 1
        return s

    def retry(self, jid):
        rec = self.get(jid)
        if not rec or rec["state"] != "failed" or not self.r.lrem("sh:jobs:failed", 0, jid):  # lrem is the claim: two clicks, one retry
            return False
        rec.update(state="queued", tries=0, error=None, finished_at=None)
        self._save(rec)
        self.r.rpush("sh:jobs:ready", jid)
        return True


_Q = None


def queue():
    global _Q
    if _Q is None:
        _Q = RedisQueue() if _mode.production() else LocalQueue()
    return _Q


def reset() -> None:
    """Tests: drop the queue so the next call builds the one for the mode then."""
    global _Q
    _Q = None


def run_worker(stop: threading.Event, q=None, poll: float = 1.0) -> None:
    """The worker loop (tools/worker.py): take jobs, and hand outbox events to their consumers."""
    q = q or queue()
    if not isinstance(q, RedisQueue):
        raise RuntimeError("the worker runs in production mode (DATABASE_URL and REDIS_URL)")
    import sh_platform.jobs.handlers  # noqa: F401
    while not stop.is_set():
        try:
            busy = q.work_once(poll)
            busy = bool(events.bus().dispatch_once()) or busy
        except Exception:
            log.exception("worker pass failed")
            time.sleep(poll)
            continue
        if not busy:
            time.sleep(0.05)
