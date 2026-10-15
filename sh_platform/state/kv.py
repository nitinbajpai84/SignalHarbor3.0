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


def cache_put(key: str, text: str, ttl_s: float) -> None:
    redis_client().set(f"sh:answer:{key}", json.dumps(text), ex=max(1, int(ttl_s)))


def cache_clear() -> None:
    r = redis_client()
    for k in r.scan_iter("sh:answer:*"):
        r.delete(k)
