"""W3 two modes: the adapter layer in simple mode (real), the Redis side against a small fake Redis, and the Postgres/Redis side against
real servers when TEST_DATABASE_URL and TEST_REDIS_URL are set (the Redis database named there is flushed; use a throw-away one)."""
import fnmatch
import json
import os
import threading
import time
import types
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform import events, jobs, mode
from sh_platform.plane import PlaneStore
from sh_platform.state import Conflict, FileStore, kv, update
from sh_platform.v1 import w3_jobs_routes as R

REAL = bool(os.environ.get("TEST_DATABASE_URL") and os.environ.get("TEST_REDIS_URL"))
needs_real = pytest.mark.skipif(not REAL, reason="set TEST_DATABASE_URL and TEST_REDIS_URL to run the production-mode tests")


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("DATABASE_URL", "REDIS_URL"):
        monkeypatch.delenv(k, raising=False)
    events.reset()
    jobs.reset()
    kv._CLIENT = None
    yield
    events.reset()
    jobs.reset()
    kv._CLIENT = None


class FakeRedis:
    """Just the commands the code uses. Times to live are honoured by a clock the test can move."""

    def __init__(self):
        self.d, self.exp, self.now = {}, {}, time.time

    def _live(self, k):
        if k in self.exp and self.exp[k] <= self.now():
            self.d.pop(k, None)
            self.exp.pop(k, None)
        return k in self.d

    def set(self, k, v, nx=False, ex=None, px=None):
        if nx and self._live(k):
            return None
        self.d[k] = v
        if ex or px:
            self.exp[k] = self.now() + (ex or px / 1000)
        return True

    def get(self, k):
        return self.d[k] if self._live(k) and not isinstance(self.d[k], (list, dict)) else None

    def pttl(self, k):
        return int((self.exp[k] - self.now()) * 1000) if self._live(k) and k in self.exp else -1

    def delete(self, *ks):
        for k in ks:
            self.d.pop(k, None)
            self.exp.pop(k, None)

    def expire(self, k, s):
        self.exp[k] = self.now() + s

    def incr(self, k):
        self.d[k] = int(self.d.get(k, 0)) + 1
        return self.d[k]

    def scan_iter(self, pattern, count=None):
        return iter([k for k in list(self.d) if self._live(k) and fnmatch.fnmatch(k, pattern)])

    def rpush(self, k, v):
        self.d.setdefault(k, []).append(v)

    def lpush(self, k, v):
        self.d.setdefault(k, []).insert(0, v)

    def lpop(self, k):
        return self.d[k].pop(0) if self.d.get(k) else None

    def blpop(self, k, timeout=0):
        v = self.lpop(k)
        return (k, v) if v is not None else None

    def ltrim(self, k, a, b):
        self.d[k] = self.d.get(k, [])[a:b + 1]

    def lrange(self, k, a, b):
        return self.d.get(k, [])[a:None if b == -1 else b + 1]

    def lrem(self, k, n, v):
        old = self.d.get(k, [])
        self.d[k] = [x for x in old if x != v]
        return len(old) - len(self.d[k])

    def zadd(self, k, m, nx=False):
        z = self.d.setdefault(k, {})
        for member, score in m.items():
            if not (nx and member in z):
                z[member] = score

    def zrangebyscore(self, k, lo, hi):
        return [m for m, s in sorted(self.d.get(k, {}).items(), key=lambda i: i[1]) if lo <= s <= hi]

    def zrem(self, k, m):
        return 1 if self.d.get(k, {}).pop(m, None) is not None else 0

    def zrevrange(self, k, a, b):
        return [m for m, _ in sorted(self.d.get(k, {}).items(), key=lambda i: -i[1])][a:b + 1]

    def zcard(self, k):
        return len(self.d.get(k, {}))

    def zremrangebyscore(self, k, lo, hi):
        z = self.d.get(k, {})
        for m in [m for m, s in z.items() if lo <= s <= hi]:
            del z[m]


# ---- mode ---------------------------------------------------------------------------------------------------------------------------

def test_mode_is_simple_by_default_and_production_only_with_both(monkeypatch):
    assert mode.mode() == "simple" and not mode.production()
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    with pytest.raises(mode.ModeError, match="REDIS_URL"):
        mode.check()
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    with pytest.raises(mode.ModeError, match="DATABASE_URL"):
        mode.check()
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    assert mode.mode() == "production"
    monkeypatch.setenv("REDIS_URL", "  ")
    with pytest.raises(mode.ModeError):
        mode.check()


def test_the_server_refuses_to_start_with_only_one_set(monkeypatch, tmp_path):
    from sh_platform.app import create_app
    monkeypatch.setenv("REDIS_URL", "redis://x")
    with pytest.raises(mode.ModeError):
        create_app()


# ---- state (simple mode: the files stay as they are) ------------------------------------------------------------------------------------

def test_file_store_keeps_plain_json_and_compare_and_set(tmp_path):
    s = FileStore(tmp_path)
    assert s.get("intents", "acme/a/x.json") == (None, "0")
    v1 = s.put("intents", "acme/a/x.json", {"n": 1}, expected="0")
    assert json.loads((tmp_path / "acme" / "intents" / "a" / "x.json").read_text()) == {"n": 1}  # same shape on disk as before
    assert s.get("intents", "acme/a/x.json") == ({"n": 1}, v1)
    with pytest.raises(Conflict):
        s.put("intents", "acme/a/x.json", {"n": 2}, expected="0")  # must not exist
    v2 = s.put("intents", "acme/a/x.json", {"n": 2}, expected=v1)
    assert v2 != v1
    with pytest.raises(Conflict):
        s.put("intents", "acme/a/x.json", {"n": 3}, expected=v1)  # stale
    assert update(s, "intents", "acme/a/x.json", lambda d: {"n": d["n"] + 1}) == {"n": 3}
    assert s.keys("intents", "acme/a") == ["acme/a/x.json"]
    s.delete("intents", "acme/a/x.json")
    assert s.get("intents", "acme/a/x.json")[0] is None


def test_file_store_refuses_a_key_that_escapes(tmp_path):
    s = FileStore(tmp_path)
    for bad in ("../x.json", "acme/../../x.json", "/abs.json", "acme", "a\\b/c.json"):
        with pytest.raises(ValueError):
            s.put("intents", bad, {})
    with pytest.raises(ValueError):
        s.put("In Tents", "acme/x.json", {})


def test_update_is_safe_with_two_writers(tmp_path):
    s = FileStore(tmp_path)
    s.put("build", "acme/count.json", {"n": 0})

    def bump():
        for _ in range(25):
            update(s, "build", "acme/count.json", lambda d: {"n": d["n"] + 1}, tries=200)
    ts = [threading.Thread(target=bump) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert s.get("build", "acme/count.json")[0] == {"n": 100}


# ---- jobs (simple mode) ---------------------------------------------------------------------------------------------------------------

@pytest.fixture()
def handlers(monkeypatch):
    seen = []
    monkeypatch.setitem(jobs.HANDLERS, "t.ok", lambda p: seen.append(p) or {"ok": p["n"]})
    monkeypatch.setitem(jobs.HANDLERS, "t.boom", lambda p: (_ for _ in ()).throw(OSError("disk full")))
    return seen


def test_submit_runs_here_and_keeps_the_original_error(handlers):
    q = jobs.LocalQueue()
    assert q.submit("t.ok", {"n": 3, "company_id": "acme"}) == {"ok": 3} and handlers == [{"n": 3, "company_id": "acme"}]
    with pytest.raises(OSError):
        q.submit("t.boom", {})
    assert [r["state"] for r in q.recent()] == ["failed", "done"]


def test_enqueue_retries_with_backoff_then_lands_on_the_failed_list_and_can_be_sent_again(handlers, monkeypatch):
    q = jobs.LocalQueue(backoff=0.0)
    jid = q.enqueue("t.boom", {"company_id": "acme"}, tries=3)
    assert q.drain(10)
    r = q.get(jid)
    assert r["state"] == "failed" and r["tries"] == 3 and "disk full" in r["error"] and [x["id"] for x in q.failed()] == [jid]
    monkeypatch.setitem(jobs.HANDLERS, "t.boom", lambda p: "fine now")
    assert q.retry(jid) and q.drain(10) and q.get(jid)["state"] == "done" and q.failed() == []
    assert not q.retry(jid)  # only a failed job goes again


def test_a_key_blocks_a_second_enqueue_while_the_first_waits(handlers):
    q = jobs.LocalQueue()
    gate = threading.Event()
    jobs.HANDLERS["t.slow"] = lambda p: gate.wait(5)
    try:
        a = q.enqueue("t.slow", {}, key="k")
        assert a and q.enqueue("t.slow", {}, key="k") is None
        gate.set()
        assert q.drain(10) and q.enqueue("t.ok", {"n": 1}, key="k")  # free again once finished
    finally:
        jobs.HANDLERS.pop("t.slow", None)
        gate.set()


def test_job_events_reach_the_bus(handlers):
    got = []
    events.bus().subscribe("t", "job.", got.append)
    jobs.LocalQueue(backoff=0).enqueue("t.ok", {"n": 1, "company_id": "acme"})
    jobs.queue()  # (the singleton is separate; the queue above published through the shared bus)
    time.sleep(0.3)
    assert [e["topic"] for e in got][:2] == ["job.queued", "job.running"] and got[-1]["topic"] == "job.done"
    assert got[0]["payload"]["company_id"] == "acme"


def test_the_scheduler_and_pipeline_run_go_through_the_queue_and_behave_as_before(tmp_path):
    from sh_platform.jobs import handlers as H
    from sh_platform.v1 import b6_run, b6_schedule
    plane = PlaneStore(tmp_path / "data").create("acme")
    assert jobs.queue().submit("b6.tick", H.payload_of(plane)) == b6_schedule.tick(plane) == []
    with pytest.raises(b6_run.Refused) as e:  # the same words and status as a direct run
        H.run_pipeline(plane, "nope", "sandbox", "Mei")
    direct = pytest.raises(b6_run.Refused)
    with direct as d:
        b6_run.run(plane, "nope", "sandbox", by="Mei")
    assert (e.value.message, e.value.status) == (d.value.message, d.value.status)
    names = [r["name"] for r in jobs.queue().recent()]
    assert "b6.tick" in names and "b6.run" in names


def test_graph_rebuild_stays_a_thread_in_simple_mode(tmp_path):
    from sh_platform.graph import hooks
    plane = PlaneStore(tmp_path / "data").create("acme")
    hooks.mark_dirty(plane)
    hooks.rebuild_if_dirty(plane, wait=False)
    assert jobs.queue().recent() == []  # nothing went to the queue


# ---- events (simple mode) -------------------------------------------------------------------------------------------------------------

def test_memory_bus_dispatches_at_once_and_a_failing_consumer_hurts_nobody():
    b, got = events.MemoryBus(), []
    b.subscribe("bad", "badge.", lambda e: 1 / 0)
    b.subscribe("good", "badge.", got.append)
    b.subscribe("other", "job.", got.append)
    i = b.publish("badge.action", {"company_id": "acme"})
    assert [e["id"] for e in got] == [i] and b.since(0)[0]["topic"] == "badge.action" and b.latest() == i and b.since(i) == []


def test_assigning_work_moves_the_action_badge(tmp_path):
    from sh_platform.v1 import p2_assign
    plane = PlaneStore(tmp_path / "data").create("acme")
    p2_assign._append(plane, {"event": "assign", "to": "Mei"})  # the shape _write appends
    ev = events.bus().since(0)[-1]
    assert ev["topic"] == "badge.action" and ev["payload"]["company_id"] == "acme" and ev["payload"]["to"] == "Mei" and ev["payload"]["change"] == "assign"


# ---- routes -----------------------------------------------------------------------------------------------------------------------------

@pytest.fixture()
def api(monkeypatch):
    app = FastAPI()
    app.include_router(R.router)
    role = {"v": "analyst"}

    @app.middleware("http")
    async def who(request, call_next):
        request.state.company_id = "acme"
        return await call_next(request)

    def seat(request, s):
        if role["v"] == "consumer" and s == "data_engineer":
            from fastapi import HTTPException
            raise HTTPException(403, {"error": "not_allowed", "message": "no"})
    monkeypatch.setattr(R, "require_seat", seat)
    return TestClient(app), role


def test_admin_page_lists_only_this_companys_jobs_and_sends_a_failed_one_again(api, handlers):
    c, role = api
    q = jobs.queue()
    q.backoff = 0
    mine = q.enqueue("t.boom", {"company_id": "acme", "data_root": "SECRET-PATH"}, tries=1)
    other = q.enqueue("t.boom", {"company_id": "rival"}, tries=1)
    assert q.drain(10)
    got = c.get("/api/v1/jobs").json()
    assert got["mode"] == "simple" and [j["id"] for j in got["failed"]] == [mine] and other not in json.dumps(got) and "SECRET-PATH" not in json.dumps(got)
    assert got["stats"]["failed"] == 1 and all(e["payload"]["company_id"] == "acme" for e in got["events"])
    assert c.post(f"/api/v1/jobs/{other}/retry").status_code == 404  # not this company's
    jobs.HANDLERS["t.boom"] = lambda p: "ok"
    assert c.post(f"/api/v1/jobs/{mine}/retry").json() == {"retried": mine}
    assert q.drain(10) and c.get("/api/v1/jobs").json()["failed"] == []
    role["v"] = "consumer"
    assert c.get("/api/v1/jobs").status_code == 403


def test_admin_page_lists_the_pipeline_runs_that_happen_inside_the_server(api, monkeypatch, tmp_path):
    """V6 (walk gap 14): in simple mode a run is not on the queue, so the page said "No jobs yet" after pipelines ran; the runs come from the projects' run logs."""
    from sh_platform.plane import PlaneStore
    from sh_platform.v1 import b6_run, p1_project
    c, _ = api
    plane = PlaneStore(tmp_path / "data").create("acme")
    pid = p1_project.create_project(plane, "int-1", "Monthly performance", "Mei Chen")["id"]
    b6_run._log(plane, pid, {"run_id": "r1", "plan_version": 1, "started": "2026-10-11T04:40:00+00:00", "finished": "2026-10-11T04:40:02+00:00", "status": "ok", "mode": "sandbox", "steps": []})
    b6_run._log(plane, pid, {"run_id": "r2", "plan_version": 1, "started": "2026-10-11T05:10:00+00:00", "finished": "2026-10-11T05:10:03+00:00", "status": "ok", "mode": "live", "steps": []})
    import sh_platform.profile.api as profile_api
    monkeypatch.setattr(profile_api, "_plane", lambda request: plane)
    got = c.get("/api/v1/jobs").json()
    assert [(r["run_id"], r["mode"], r["status"], r["title"]) for r in got["runs"]] == [("r2", "live", "ok", "Monthly performance"), ("r1", "sandbox", "ok", "Monthly performance")]
    assert got["jobs"] == [] and got["mode"] == "simple"


def test_event_stream_sends_this_companys_events_only(api, monkeypatch):
    c, _ = api
    events.publish("badge.action", {"company_id": "rival"})
    events.publish("badge.action", {"company_id": "acme", "to": "Mei"})
    with c.stream("GET", "/api/v1/events/stream?after=0") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())
    data = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    assert [d["payload"].get("to") for d in data] == ["Mei"] and "rival" not in body
    monkeypatch.setattr(R, "STREAM_S", 0.0)
    with c.stream("GET", "/api/v1/events/stream?after=99999") as r:  # an id from before a restart: starts from now, does not wait forever
        assert "data: " not in "".join(r.iter_text())


def test_every_route_is_declared_default_deny():
    decl = yaml.safe_load((Path(R.__file__).parent / "w3_jobs.permissions.yaml").read_text())["routes"]
    assert {f"{m} {r.path}" for r in R.router.routes for m in r.methods} == set(decl)


# ---- the Redis side, against a fake Redis ---------------------------------------------------------------------------------------------

def test_redis_queue_retries_with_backoff_then_fails_and_can_be_sent_again(monkeypatch, handlers):
    monkeypatch.setattr(events, "publish", lambda *a, **k: None)
    fake = FakeRedis()
    q = jobs.RedisQueue(backoff=100, client=fake)
    jid = q.enqueue("t.boom", {"company_id": "acme"}, tries=3, key="k1")
    assert q.enqueue("t.boom", {}, key="k1") is None  # same key still waiting
    assert q.work_once(0) and q.get(jid)["state"] == "retrying" and not q.work_once(0)  # waits for the backoff
    t0 = time.time()
    fake.zadd("sh:jobs:delayed", {jid: t0 - 1})  # the wait is over
    assert q.work_once(0) and q.get(jid)["tries"] == 2
    fake.zadd("sh:jobs:delayed", {jid: t0 - 1})
    assert q.work_once(0)
    r = q.get(jid)
    assert r["state"] == "failed" and r["tries"] == 3 and [x["id"] for x in q.failed()] == [jid]
    assert q.enqueue("t.ok", {"n": 1}, key="k1") and q.work_once(0)  # the key is free again once the job ended
    monkeypatch.setitem(jobs.HANDLERS, "t.boom", lambda p: "fine")
    assert q.retry(jid) and not q.retry(jid)  # a second click does not queue it twice
    assert q.work_once(0) is True and q.get(jid)["state"] == "done" and q.failed() == [] and not q.work_once(0)


def test_a_job_whose_worker_died_is_retried_after_its_lease_runs_out(monkeypatch, handlers):
    monkeypatch.setattr(events, "publish", lambda *a, **k: None)
    fake = FakeRedis()
    q = jobs.RedisQueue(backoff=0, client=fake)
    jid = q.enqueue("t.ok", {"n": 3}, key="k9", tries=2)
    rec = q._next(0)  # a worker takes it, marks it running, then dies without finishing
    rec.update(state="running", tries=1)
    q._save(rec)
    fake.zadd("sh:jobs:running", {jid: time.time() + q.LEASE})
    assert q.sweep() == 0 and q.enqueue("t.ok", {}, key="k9") is None  # lease still live: nothing moves
    fake.zadd("sh:jobs:running", {jid: time.time() - 1})  # the heartbeat stopped
    assert q.work_once(0) and q.get(jid)["state"] == "done" and q.get(jid)["tries"] == 2 and fake.zcard("sh:jobs:running") == 0
    assert q.enqueue("t.ok", {}, key="k9")  # the key is free again
    jid2 = q.enqueue("t.ok", {}, tries=1)
    r2 = q.get(jid2)
    r2.update(state="running", tries=1)
    q._save(r2)
    fake.zadd("sh:jobs:running", {jid2: time.time() - 1})
    assert q.sweep() == 1 and q.get(jid2)["state"] == "failed" and q.get(jid2)["error"] == "the worker stopped during the job"


def test_a_long_job_keeps_its_lease_alive(monkeypatch, handlers):
    monkeypatch.setattr(events, "publish", lambda *a, **k: None)
    fake = FakeRedis()
    q = jobs.RedisQueue(client=fake)
    q.LEASE = 0.3
    seen = []
    monkeypatch.setitem(jobs.HANDLERS, "t.slow", lambda p: [time.sleep(0.15) or seen.append(q.sweep()) for _ in range(5)] and "ok")
    jid = q.enqueue("t.slow", {})
    assert q.work_once(0) and q.get(jid)["state"] == "done" and seen == [0] * 5 and fake.zcard("sh:jobs:running") == 0


def test_redis_queue_call_waits_for_the_worker(monkeypatch, handlers):
    monkeypatch.setattr(events, "publish", lambda *a, **k: None)
    q = jobs.RedisQueue(client=FakeRedis())
    t = threading.Thread(target=lambda: [q.work_once(0) or time.sleep(0.02) for _ in range(100)])
    t.start()
    assert q.call("t.ok", {"n": 7}, timeout=5, poll=0.02) == {"ok": 7}
    t.join()
    with pytest.raises(jobs.JobFailed):
        q.call("t.ok", {"n": 1}, timeout=0.1, poll=0.02)  # nobody is working: times out


def test_pipeline_refusal_is_a_result_not_a_failure_in_production(monkeypatch, tmp_path):
    from sh_platform.jobs import handlers as H
    from sh_platform.v1 import b6_run
    monkeypatch.setattr(events, "publish", lambda *a, **k: None)
    plane = PlaneStore(tmp_path / "data").create("acme")
    q = jobs.RedisQueue(client=FakeRedis())
    monkeypatch.setattr(jobs, "_Q", q)
    t = threading.Thread(target=lambda: [q.work_once(0) or time.sleep(0.02) for _ in range(150)])
    t.start()
    with pytest.raises(b6_run.Refused) as e:
        H.run_pipeline(plane, "nope", "sandbox", "Mei")
    t.join()
    assert e.value.status == 404 and q.recent()[0]["state"] == "done" and q.failed() == []


def test_a_pipeline_run_that_fails_on_the_worker_is_a_plain_refusal_not_a_500(monkeypatch, tmp_path):
    from sh_platform.jobs import handlers as H
    from sh_platform.v1 import b6_run
    monkeypatch.setattr(events, "publish", lambda *a, **k: None)
    plane = PlaneStore(tmp_path / "data").create("acme")
    q = jobs.RedisQueue(client=FakeRedis())
    monkeypatch.setattr(jobs, "_Q", q)
    monkeypatch.setitem(jobs.HANDLERS, "b6.run", lambda p: (_ for _ in ()).throw(RuntimeError("warehouse busy")))
    t = threading.Thread(target=lambda: [q.work_once(0) or time.sleep(0.02) for _ in range(150)])
    t.start()
    with pytest.raises(b6_run.Refused) as e:
        H.run_pipeline(plane, "p1", "sandbox", "Mei")
    t.join()
    assert e.value.status == 503 and "warehouse" not in e.value.message and q.failed()[0]["error"] == "RuntimeError: warehouse busy"


def test_production_web_gives_the_warehouse_file_back_when_idle(monkeypatch, tmp_path):
    import duckdb
    from sh_platform.v1 import wh
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    plane = PlaneStore(tmp_path / "data").create("acme")
    key = str(wh.path(plane))
    wh.reset_cache()
    wh.serve()
    try:
        with wh.connect(plane) as a:
            with wh.connect(plane) as b:  # a second request in this process shares the one open file
                assert b.execute("select 1").fetchall() == [(1,)]
            assert key in wh._SHARED and a.execute("select 42").fetchall() == [(42,)]  # still held while `a` is open
        assert key not in wh._SHARED  # the last one closed: the file is free
        duckdb.connect(key).close()  # so another process (the worker, the other web replica) can open it
        monkeypatch.delenv("DATABASE_URL")
        monkeypatch.delenv("REDIS_URL")
        with wh.connect(plane):
            pass
        assert key in wh._SHARED  # simple mode: held for the life of the server, as before
    finally:
        wh.reset_cache()


def test_redis_window_breaker_and_answer_cache(monkeypatch):
    fake = FakeRedis()
    kv._CLIENT = fake
    w = kv.RedisWindow()
    assert [w.allow("a", 2, 60, 100.0 + i) for i in range(3)] == [True, True, False] and w.allow("a", 2, 60, 200.0) and w.allow("b", 2, 60, 100.0)
    clock, wall = {"t": 1000.0}, {"t": time.time()}
    monkeypatch.setattr(kv, "time", types.SimpleNamespace(time=lambda: wall["t"]))
    fake.now = lambda: wall["t"]
    b = kv.RedisBreaker(lambda: clock["t"])
    assert not b and b.get("h") is None
    b["h"] = ("no_credit", clock["t"] + 300)
    code, until = b.get("h")
    assert code == "no_credit" and 1299 < until <= 1300 and b
    clock["t"] += 301
    wall["t"] += 301  # the window passes: every process still sees it, and exactly one caller gets the trial
    code, until = b.get("h")
    assert code == "no_credit" and until <= clock["t"] and b
    b2 = kv.RedisBreaker(lambda: clock["t"] + 50)  # a second process with its own clock agrees
    assert [b.take_trial("h", "no_credit", 300), b2.take_trial("h", "no_credit", 300)] == [True, False]
    assert b2.get("h")[1] > clock["t"] + 50 + 290  # the trial re-armed the window for everyone
    b["h"] = ("x", clock["t"] + 5)
    assert b.pop("h") == "x" and b.pop("h") is None
    kv.cache_put("k", "an answer", 60)
    assert kv.cache_get("k") == "an answer"
    kv.cache_clear()
    assert kv.cache_get("k") is None


def test_the_gateway_breaker_and_the_turn_limit_switch_with_the_mode(monkeypatch):
    from sh_platform import demo_limits
    from sh_platform.egress import gateway
    assert isinstance(gateway._breaker, dict)  # simple mode: a plain dict, as before
    assert demo_limits.TurnLimiter().win is None
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    kv._CLIENT = FakeRedis()
    assert isinstance(kv.breaker_map(time.monotonic), kv.RedisBreaker)
    lim = demo_limits.TurnLimiter(clock=lambda: 500.0)
    assert [lim.allow("u1", 2) for _ in range(3)] == [True, True, False]


def test_answer_cache_and_data_version_use_redis_in_production(monkeypatch):
    from sh_platform.v1 import chat_fastpath as FP
    kv._CLIENT = FakeRedis()
    monkeypatch.setattr(mode, "production", lambda: True)
    FP._CACHE.clear()  # another file's simple-mode answers may still be in process memory
    FP._put("key1", "cached text")
    assert FP._get("key1") == "cached text" and FP._CACHE == {}
    before = FP.data_version("acme")
    FP.bump("acme")  # a worker's run in another process
    assert FP.data_version("acme") != before
    FP.reset()
    assert FP._get("key1") is None


# ---- the migration (copy is idempotent) -----------------------------------------------------------------------------------------------

def test_migration_copies_json_once_and_leaves_the_rest(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("mig", Path(__file__).resolve().parents[2] / "tools" / "migrate_to_postgres.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    src = tmp_path / "src"
    (src / "acme" / "intents" / "i1").mkdir(parents=True)
    (src / "acme" / "intents" / "i1" / "a.json").write_text('{"a": 1}')
    (src / "acme" / "build").mkdir()
    (src / "acme" / "build" / "bad.json").write_text("{nope")
    (src / "acme" / "build" / "log.jsonl").write_text("{}\n")
    (src / "acme" / "warehouse").mkdir()
    (src / "acme" / "warehouse" / "w.duckdb").write_bytes(b"x")
    dst = FileStore(tmp_path / "dst")
    first = m.migrate(src, dst)
    assert (first["copied"], first["unchanged"], first["kept_on_disk"]) == (1, 0, 2) and first["unreadable"] == ["acme/build/bad.json"]
    assert dst.get("intents", "acme/i1/a.json")[0] == {"a": 1}
    again = m.migrate(src, dst)
    assert (again["copied"], again["unchanged"]) == (0, 1)
    (src / "acme" / "intents" / "i1" / "a.json").write_text('{"a": 2}')
    assert m.migrate(src, dst)["copied"] == 0 and dst.get("intents", "acme/i1/a.json")[0] == {"a": 1}  # the store holds the live copy: never overwritten
    assert m.migrate(src, dst, dry_run=True, refresh=True)["copied"] == 1 and dst.get("intents", "acme/i1/a.json")[0] == {"a": 1}  # dry run writes nothing
    assert m.migrate(src, dst, refresh=True)["copied"] == 1 and dst.get("intents", "acme/i1/a.json")[0] == {"a": 2}


def test_parity_check_compares_modes_and_ignores_times():
    import importlib.util
    spec = importlib.util.spec_from_file_location("par", Path(__file__).resolve().parents[2] / "tools" / "parity_check.py")
    p = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p)
    same = {uc: {"exit": 0, "facts": {"f.json": p.scrub({"v": "1.0", "at": "now"})}} for uc in p.UCS}
    other = {uc: {"exit": 0, "facts": {"f.json": p.scrub({"v": "1.0", "at": "later"})}} for uc in p.UCS}
    assert p.compare(same, other) == []
    a = p.scrub({"ran_at": "x", "e": '{"cutoff": "2026-10-09T23:03:19.555795+00:00", "as_of_date": "2026-10-09", "breaks": 1}'})
    b = p.scrub({"ran_at": "y", "e": '{"cutoff": "2026-10-09T23:03:19.604859+00:00", "as_of_date": "2026-10-09", "breaks": 1}'})
    assert a == b and p.scrub({"e": '"as_of_date": "2026-10-08"'}) != p.scrub({"e": '"as_of_date": "2026-10-09"'})  # dates are figures
    other["uc3"]["facts"]["f.json"] = {"v": "2.0"}
    other["uc4"]["exit"] = 1
    assert p.compare(same, other) == ["uc3/f.json: the facts differ between modes", "uc4: the checker failed in production mode (exit 1)"]


# ---- real Postgres and Redis (skipped unless TEST_DATABASE_URL and TEST_REDIS_URL are set) --------------------------------------------

@pytest.fixture()
def real(monkeypatch):
    import psycopg
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("REDIS_URL", os.environ["TEST_REDIS_URL"])
    kv._CLIENT = None
    kv.redis_client().flushdb()
    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as c:
        for t in ("sh_state_w3test", "sh_outbox", "sh_outbox_done"):
            c.execute(f"DROP TABLE IF EXISTS {t}")
    events.reset()
    jobs.reset()
    yield
    kv.redis_client().flushdb()


@needs_real
def test_postgres_store_versions_and_compare_and_set(real):
    from sh_platform.state import PgStore, store_for
    s = store_for("ignored")
    assert isinstance(s, PgStore)
    assert s.get("w3test", "acme/a.json") == (None, "0")
    v1 = s.put("w3test", "acme/a.json", {"n": 1}, expected="0")
    assert s.get("w3test", "acme/a.json") == ({"n": 1}, v1)
    with pytest.raises(Conflict):
        s.put("w3test", "acme/a.json", {"n": 2}, expected="0")
    v2 = s.put("w3test", "acme/a.json", {"n": 2}, expected=v1)
    with pytest.raises(Conflict):
        s.put("w3test", "acme/a.json", {"n": 3}, expected=v1)
    assert int(v2) == int(v1) + 1 and update(s, "w3test", "acme/a.json", lambda d: {"n": d["n"] + 1}) == {"n": 3}
    assert s.keys("w3test", "acme/") == ["acme/a.json"] and s.keys("w3test", "acme_") == []  # '_' is literal
    with s.connect() as c:  # a rolled-back transaction leaves nothing
        s.put("w3test", "acme/b.json", {"x": 1}, conn=c)
        c.rollback()
    assert s.get("w3test", "acme/b.json")[0] is None
    s.delete("w3test", "acme/a.json")
    assert s.get("w3test", "acme/a.json")[0] is None


@needs_real
def test_outbox_is_written_with_the_transaction_and_consumers_run_once(real):
    bus = events.bus()
    assert isinstance(bus, events.PgBus)
    calls, flaky = [], {"n": 0}
    bus.subscribe("mail", "badge.", lambda e: calls.append(("mail", e["id"])))

    def fussy(e):
        flaky["n"] += 1
        if flaky["n"] == 1:
            raise RuntimeError("first time fails")
        calls.append(("fussy", e["id"]))
    bus.subscribe("fussy", "badge.", fussy)
    with bus.connect() as c:
        bus.publish("badge.action", {"company_id": "acme"}, conn=c)
        c.rollback()  # the business write failed: no event
    assert bus.since(0) == []
    first = bus.publish("badge.action", {"company_id": "acme"})
    assert bus.dispatch_once() == 0  # fussy failed: event stays pending
    assert bus.dispatch_once() == 1  # next pass: mail is NOT called again, fussy succeeds
    assert sorted(calls) == [("fussy", first), ("mail", first)] and bus.dispatch_once() == 0 and bus.latest() == first


@needs_real
def test_redis_queue_end_to_end_with_a_worker(real):
    q = jobs.queue()
    assert isinstance(q, jobs.RedisQueue)
    jobs.HANDLERS["t.real"] = lambda p: {"got": p["n"]}
    try:
        stop = threading.Event()
        t = threading.Thread(target=jobs.run_worker, args=(stop, q, 1.0))
        t.start()
        assert q.call("t.real", {"n": 5, "company_id": "acme"}, timeout=20) == {"got": 5}
        time.sleep(1.2)  # the worker also hands the job events to their consumers
        assert {e["topic"] for e in events.bus().since(0)} >= {"job.queued", "job.running", "job.done"}
    finally:
        stop.set()
        t.join(10)
        jobs.HANDLERS.pop("t.real", None)


@needs_real
def test_real_redis_one_breaker_trial_and_a_lapsed_lease_is_swept(real):
    b1, b2 = kv.RedisBreaker(time.monotonic), kv.RedisBreaker(time.monotonic)
    b1["h"] = ("no_credit", time.monotonic() - 1)  # a window that has already ended
    assert b2.get("h")[0] == "no_credit" and [b1.take_trial("h", "no_credit", 60), b2.take_trial("h", "no_credit", 60)] == [True, False]
    assert b2.get("h")[1] > time.monotonic() + 50 and b1.pop("h") == "no_credit" and not b2
    q = jobs.queue()
    q.backoff = 0  # the swept attempt is retried at once
    jobs.HANDLERS["t.real"] = lambda p: "ok"
    try:
        jid = q.enqueue("t.real", {"company_id": "acme"}, key="real-k", tries=2)
        rec = q._next(1)
        rec.update(state="running", tries=1)
        q._save(rec)
        q.r.zadd("sh:jobs:running", {jid: time.time() - 1})  # its worker died: the lease ran out
        assert q.work_once(1) and q.get(jid)["state"] == "done" and q.get(jid)["tries"] == 2 and not q.r.exists("sh:jobs:key:real-k")
    finally:
        jobs.HANDLERS.pop("t.real", None)
