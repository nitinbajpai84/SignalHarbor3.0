"""Shared answer cache, leader lease and the per-thread chain lock, on a fake Redis (two 'processes' = two ids on one fake)."""
import fnmatch
import json
import threading
import types

import pytest

from sh_platform.state import kv
from sh_platform.v1 import v3_consume as C
from sh_platform.v1 import v3_harbor as H


class FakeRedis:
    def __init__(self):
        self.d, self.now = {}, 0.0  # key -> (value, expires_at)

    def _live(self, k):
        v = self.d.get(k)
        if v and v[1] is not None and v[1] <= self.now:
            del self.d[k]
            v = None
        return v

    def get(self, k):
        v = self._live(k)
        return v[0] if v else None

    def set(self, k, v, nx=False, px=None, ex=None):
        if nx and self._live(k):
            return None
        ms = px if px is not None else (ex * 1000 if ex else None)
        self.d[k] = (v, self.now + ms / 1000 if ms else None)
        return True

    def pexpire(self, k, ms):
        self.d[k] = (self.d[k][0], self.now + ms / 1000)

    def delete(self, *ks):
        for k in ks:
            self.d.pop(k, None)

    def scan_iter(self, pat, count=None):
        return [k for k in list(self.d) if self._live(k) and fnmatch.fnmatch(k, pat)]


@pytest.fixture()
def redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(kv, "_CLIENT", fake)
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    return fake


def as_process(monkeypatch, name):
    monkeypatch.setattr(kv, "_ID", name)


class P:  # a plane stand-in
    def path(self, *a):
        return "company-1/" + "/".join(a)


def test_cache_shared_between_processes_and_version_bump(redis, monkeypatch):
    ver = [("run-1", "t1")]
    monkeypatch.setattr(C, "version", lambda plane: ver[0])
    monkeypatch.setattr(C, "_count", lambda *a: None)
    viewer, runs = types.SimpleNamespace(account_id="a1"), []

    def compute():
        runs.append(1)
        return {"answer": "Cash is 4.14m.", "trace": []}
    as_process(monkeypatch, "web-1")
    assert C.answer(P(), viewer, "cash?", compute)["cached"] is False
    C.KEPT.clear()  # a restart / another copy has no memory of it
    as_process(monkeypatch, "web-2")
    assert C.answer(P(), viewer, "cash?", compute)["cached"] is True
    assert len(runs) == 1
    ttls = [v[1] for k, v in redis.d.items() if k.startswith("sh:answer:")]
    assert ttls and all(t is not None for t in ttls)
    ver[0] = ("run-2", "t2")  # a new live run
    assert C.answer(P(), viewer, "cash?", compute)["cached"] is False
    assert len(runs) == 2


def test_leader_election_takeover_and_non_leader_idle(redis, monkeypatch):
    as_process(monkeypatch, "web-1")
    assert kv.lead(ttl_ms=1000) is True
    as_process(monkeypatch, "web-2")
    assert kv.lead(ttl_ms=1000) is False
    as_process(monkeypatch, "web-1")
    redis.now = 0.8
    assert kv.lead(ttl_ms=1000) is True  # renewed
    redis.now = 1.5
    as_process(monkeypatch, "web-2")
    assert kv.lead(ttl_ms=1000) is False  # still within the renewed lease
    redis.now = 2.5  # lapsed
    assert kv.lead(ttl_ms=1000) is True
    as_process(monkeypatch, "web-1")
    assert kv.lead(ttl_ms=1000) is False
    as_process(monkeypatch, "web-2")
    kv.unlead()  # shutdown frees it at once
    as_process(monkeypatch, "web-1")
    assert kv.lead() is True


def test_simple_mode_is_always_leader(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert kv.lead() is True


def test_non_leader_scanner_does_not_tick(redis, monkeypatch, tmp_path):
    as_process(monkeypatch, "web-1")
    kv.lead()  # another copy leads
    as_process(monkeypatch, "web-2")
    from sh_platform.v1 import g5_portal
    ticks, stop = [], threading.Event()
    monkeypatch.setattr(g5_portal, "accounts_of", lambda p: ticks.append(1) or [])
    monkeypatch.setattr(g5_portal, "morning_due", lambda: False)
    monkeypatch.setattr(g5_portal, "_STOP", stop)
    t = g5_portal.start(lambda: [object()], interval=0.01)
    stop.wait(0.15)
    assert not ticks  # not the leader
    redis.now = 1000  # lease lapses; this copy takes over
    stop.wait(0.15)
    stop.set()
    t.join(1)
    assert ticks


def test_chain_lock_blocks_double_run(redis, monkeypatch):
    runs = []
    inner = []

    def fake_run(app, plane, tid, name, account_id, at=0):
        runs.append(tid)
        if not inner:  # while "web-1" is mid-chain, "web-2" asks for the same thread
            inner.append(1)
            as_process(monkeypatch, "web-2")  # another thread (re-entry in the same thread is allowed)
            t = threading.Thread(target=H.run_chain, args=(None, P(), tid, "A", None))
            t.start()
            t.join()
            as_process(monkeypatch, "web-1")
    monkeypatch.setattr(H, "_run_chain", fake_run)
    as_process(monkeypatch, "web-1")
    H.run_chain(None, P(), "t1", "A", None)
    assert runs == ["t1"]
    H.run_chain(None, P(), "t1", "A", None)  # released after the first: runs again
    assert runs == ["t1", "t1"]
