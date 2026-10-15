"""DEMO1: tools/seed_demo_ready.py on a temporary data root with a stubbed market API. Every step does its thing and a second run changes nothing.
Synthetic data only; the repo's data/ is never touched."""
import json

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import b6_plan, cx_dash, d1_delivery, e0a_catalogue as E, k3_map, wh, x5_extract
from tools import seed_10uc as S
from tools import seed_demo_ready as R


def fake_http(url, headers):  # Frankfurter / MAS shaped answers; any other call is a 404
    if "frankfurter" in url:
        return 200, json.dumps({"rates": {"2026-10-09": {"SGD": 1.28, "USD": 1.12}}}).encode()
    return 404, b""


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    root = tmp_path_factory.mktemp("demoready")
    S.seed(root)
    F = {"api_http": fake_http}
    first = R.seed(root, strict=True, F=F)
    plane = PlaneStore(root).plane_for("evergreen").ensure()
    before = snapshot(plane)
    second = R.seed(root, strict=True, F=F)
    yield {"plane": plane, "root": root, "first": first, "second": second, "before": before, "after": snapshot(plane), "V": S.viewers(S.EG.accounts(root)[0])}
    mp.undo()


def snapshot(plane) -> dict:
    n = lambda p: len(list(plane.path(*p).glob("*"))) if plane.path(*p).is_dir() else 0  # noqa: E731
    with wh.connect(plane) as con:
        q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
        db = {"market": q("select count(*) from market_observations"), "silver": q(f"select count(*) from {R.SILVER}")}
    runs = (plane.path("ops", "runs.jsonl").read_text(encoding="utf-8").count("\n"))
    pid = R._project(plane, R.V3.TITLE)["id"]
    return {**db, "runs": runs, "plans": len(b6_plan.versions(plane, pid)), "models": len(E.proposals(plane)), "outbox": len(d1_delivery.outbox(plane, pid)),
            "extractions": n(("extractions",)), "projects": len(R.P1.all_projects(plane)), "documents": n(("documents",))}


def test_second_run_changes_nothing(world):
    assert world["before"] == world["after"]
    assert all(v == "kept" for k, v in world["second"].items() if k != "markets")
    assert "0 new" in world["second"]["markets"]


def test_silver_is_in_the_flow_and_loaded(world):
    plane, V = world["plane"], world["V"]
    stages = {n["stage"] for n in k3_map.flow(plane, V["Anita Rao"])["nodes"]}
    assert {"bronze", "silver", "gold"} <= stages and world["after"]["silver"] > 0


def test_test_and_production_runs_with_steps(world):
    from sh_platform.v1 import run_log
    rs = [r for r in run_log._read(world["plane"], "runs.jsonl") if r.get("kind") == "pipeline"]
    assert {"test", "production"} <= {r["mode"] for r in rs}
    assert any(s["run_id"] == rs[0]["run_id"] for s in run_log._read(world["plane"], "run_steps.jsonl"))


def test_markets_are_live_rows(world):
    from sh_platform.v1.c5_connect import api
    assert any("LIVE API" in m["marker"] for m in api.markers(world["plane"]))


def test_action_items_pending_extension_and_dashboards(world):
    plane, V = world["plane"], world["V"]
    assert x5_extraction_waiting(plane)
    assert [m["state"] for m in E.proposals(plane) if "manager_fee_schedule" in m["summary"]] == ["proposed"]
    pid = R._project(plane, R.V3.TITLE)["id"]
    assert b6_plan.get(plane, pid)["state"] == "proposed"
    states = {cx_dash.status_of(cx_dash._load(plane, pid, f.stem)) for f in cx_dash._dir(plane, pid).glob("dash-*.json")}
    assert {"submitted", "published"} <= states
    assert world["after"]["outbox"] >= 2


def test_uc4_project_is_live_with_an_approved_dashboard(world):
    plane = world["plane"]
    p = R._project(plane, R.UC4_TITLE)
    assert p["stage"] == "live" and cx_dash.status_of(R.b7_studio._starter_of(plane, p["id"])) == "published"


def x5_extraction_waiting(plane) -> bool:
    return x5_extraction_queue(plane)["count"] >= 1


def x5_extraction_queue(plane):
    return x5_extract.queue(plane)


def test_production_mode_queue_is_not_needed_and_is_left_alone(tmp_path, monkeypatch):
    """Production mode sends b6 runs to a Redis queue no worker serves during the seed: the seed runs them inline and restores the queue."""
    from sh_platform import jobs

    class NoRedis:
        def __init__(self, *a, **k):
            raise AssertionError("the seed must not use the Redis queue")
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setattr(jobs._mode, "production", lambda: True)
    monkeypatch.setattr(jobs, "RedisQueue", NoRedis)
    jobs.reset()
    wh.reset_cache()
    S.seed(tmp_path)
    plane = PlaneStore(tmp_path).plane_for("evergreen").ensure()
    V = S.viewers(S.EG.accounts(tmp_path)[0])
    assert R._inline(lambda: R.uc4(plane, V, None)) == "made"
    assert R._inline(lambda: R.uc4(plane, V, None)) == "kept"
    assert jobs._Q is None  # the product's own queue was not replaced
    jobs.reset()


def test_reset_db_truncates_only_state_and_outbox_tables():
    from tools import seed_demo_boot as B
    sql = []

    class Conn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, q):
            sql.append(q)
            return type("C", (), {"fetchall": lambda s: [("sh_state_a",), ("sh_outbox",)]})()
    assert B.reset_db("x", lambda: Conn()) == ["sh_state_a", "sh_outbox"]
    assert [q for q in sql if q.startswith("TRUNCATE")] == ['TRUNCATE TABLE "sh_state_a" RESTART IDENTITY', 'TRUNCATE TABLE "sh_outbox" RESTART IDENTITY']
    assert not any("DROP" in q.upper() for q in sql)
