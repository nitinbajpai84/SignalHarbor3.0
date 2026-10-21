"""Shared small state: the answer cache, the chat rate limit and the outage breaker.

simple: process memory (what they were before). production: Redis, so two web replicas and the worker agree.
`redis_client()` is the one place a Redis connection is made; tests put a fake in `_CLIENT`.
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict, deque

from sh_platform import mode as _mode

_CLIENT = None


def redis_client():
    global _CLIENT
    if _CLIENT is None:
        import redis  # only production mode needs the package
        _CLIENT = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    return _CLIENT


# ---- sliding-window limit -------------------------------------------------------------------------------------------------------
class MemoryWindow:
    def __init__(self):
        self.hits, self.lock = defaultdict(deque), threading.Lock()

    def allow(self, key: str, limit: int, window: int, now: float) -> bool:
        with self.lock:
            q = self.hits[key]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


class RedisWindow:
    """A sorted set per key, scored by time. ponytail: count-then-add is not atomic; a burst across replicas can pass the limit by a
    few turns. A Lua script if the limit ever needs to be exact."""

    def allow(self, key: str, limit: int, window: int, now: float) -> bool:
        r, k = redis_client(), f"sh:rl:{key}"
        r.zremrangebyscore(k, 0, now - window)
        if r.zcard(k) >= limit:
            return False
        r.zadd(k, {f"{now}:{os.urandom(4).hex()}": now})
        r.expire(k, int(window) + 1)
        return True


def window():
    return RedisWindow() if _mode.production() else MemoryWindow()


# ---- the outage breaker: a dict of provider host -> (refusal code, when it may be tried again) ---------------------------------------
class RedisBreaker:
    """Dict-like (get, set, pop, clear, bool), plus take_trial. The value is "<code> <until as wall-clock time>", kept for a day after the
    window ends, so every process still sees the breaker after its window and only one caller (take_trial) gets the trial call."""
    KEEP = 86400

    def __init__(self, clock):
        self.clock = clock

    def get(self, host, default=None):
        raw = redis_client().get(f"sh:breaker:{host}")
        if not raw:
            return default
        code, _, until = raw.partition(" ")
        return code, self.clock() + (float(until) - time.time())

    def __setitem__(self, host, value):
        code, until = value
        wall = time.time() + (until - self.clock())
        redis_client().set(f"sh:breaker:{host}", f"{code} {wall}", ex=max(1, int(wall - time.time())) + self.KEEP)

    def take_trial(self, host, code, seconds) -> bool:
        """After the window: True for exactly one caller per window (it re-arms the window and makes the trial call)."""
        if not redis_client().set(f"sh:breaker:trial:{host}", "1", nx=True, px=max(1, int(seconds * 1000))):
            return False
        self[host] = (code, self.clock() + seconds)
        return True

    def pop(self, host, default=None):
        r = redis_client()
        k = f"sh:breaker:{host}"
        was = r.get(k)
        r.delete(k, f"sh:breaker:trial:{host}")
        return was.partition(" ")[0] if was else default

    def clear(self):
        r = redis_client()
        for k in r.scan_iter("sh:breaker:*"):
            r.delete(k)

    def __bool__(self):
        return next(iter(redis_client().scan_iter("sh:breaker:*", count=100)), None) is not None


def breaker_map(clock):
    return RedisBreaker(clock) if _mode.production() else {}


# ---- the answer cache -----------------------------------------------------------------------------------------------------------
def cache_get(key: str):
    v = redis_client().get(f"sh:answer:{key}")
    return json.loads(v) if v else None


def cache_put(key: str, text, ttl_s: float) -> None:
    redis_client().set(f"sh:answer:{key}", json.dumps(text), ex=max(1, int(ttl_s)))


def cache_clear() -> None:
    r = redis_client()
    for k in r.scan_iter("sh:answer:*"):
        r.delete(k)


# ---- the leader lease and short locks ---------------------------------------------------------------------------------------------
_ID = os.urandom(8).hex()  # this process; tests change it to stand in for a second web copy
LEASE_MS = 90_000  # three missed 30 s passes; a pass renews it
_HELD = threading.local()
_LOCKS: dict[str, threading.RLock] = defaultdict(threading.RLock)  # simple mode, per name


def lead(name: str = "loops", ttl_ms: int = LEASE_MS) -> bool:
    """True when this process holds the lease `name` (takes it, or renews it). Simple mode: the one process is always the leader.
    Call it every pass of a background loop; a lease that lapses is taken by whichever copy asks next."""
    if not _mode.production():
        return True
    r, k = redis_client(), f"sh:lead:{name}"
    if r.set(k, _ID, nx=True, px=ttl_ms):
        return True
    if r.get(k) == _ID:  # ponytail: get-then-pexpire is not atomic; a Lua script if two copies ever share an id
        r.pexpire(k, ttl_ms)
        return True
    return False


def unlead(name: str = "loops") -> None:
    """Give the lease up on shutdown so another copy takes over at once."""
    if _mode.production():
        r, k = redis_client(), f"sh:lead:{name}"
        if r.get(k) == _ID:
            r.delete(k)


class lock:
    """`with kv.lock("chain:t1") as got:` got is False when someone else holds it (skip the work). Re-entrant in the same thread.
    Production: a Redis key with a TTL (so a crashed holder frees it); simple: an in-process lock."""

    def __init__(self, name: str, ttl_s: float = 1800):
        self.name, self.ttl, self.got, self.nested = name, ttl_s, False, False

    def __enter__(self) -> bool:
        held = _HELD.__dict__.setdefault("names", set())
        if self.name in held:
            self.nested = self.got = True
            return True
        if _mode.production():
            self.got = bool(redis_client().set(f"sh:lock:{self.name}", _ID, nx=True, px=max(1, int(self.ttl * 1000))))
        else:
            self.got = _LOCKS[self.name].acquire(blocking=False)
        if self.got:
            held.add(self.name)
        return self.got

    def __exit__(self, *exc) -> None:
        if not self.got or self.nested:
            return
        _HELD.names.discard(self.name)
        if _mode.production():
            r, k = redis_client(), f"sh:lock:{self.name}"
            if r.get(k) == _ID:
                r.delete(k)
        else:
            _LOCKS[self.name].release()
