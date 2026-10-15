"""RUN1: every run gets one id; test and production are told apart; a sandbox pipeline run logs steps and its gold table carries the run_id."""
import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import b6_run as R, run_log, wh
from tests.v1.test_b6_run import plan, PID


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    return PlaneStore(tmp_path / "data").create("acme")


def test_run_log_roundtrip(plane):
    rid = run_log.start_run(plane, "recon", "production", "schedule", "Asha", job_id="j1")
    assert rid.startswith("run-")
    run_log.step(plane, rid, "cash", "check", "recon_runs", 5, 1, 0, 4, 1, batch_id="b1")
    run_log.finish(plane, rid, "ok")
    run_log.record(plane, "pipeline", "test", "manual", "Asha", [], "failed")
    assert [r["mode"] for r in run_log.list_runs(plane)] == ["test", "production"]
    assert [r["kind"] for r in run_log.list_runs(plane, mode="production")] == ["recon"]
    r = run_log.get_run(plane, rid)
    assert r["status"] == "ok" and r["job_id"] == "j1" and r["seconds"] is not None and r["steps"][0]["batch_id"] == "b1"
    assert run_log.get_run(plane, "nope") is None


def test_trial_run_is_a_test_run_with_steps_and_gold_run_id(plane):
    plan(plane)
    rec = R.run(plane, PID, "sandbox", by="Asha")
    run = run_log.get_run(plane, rec["run_id"])
    assert run["mode"] == "test" and run["kind"] == "pipeline" and run["who"] == "Asha" and run["status"] == "ok" and run["trigger"] == "manual"
    assert {s["target"] for s in run["steps"]} == {"gold_t_total", "bronze_t_raw", "bronze_t_file"}
    gold = next(s for s in run["steps"] if s["target"] == "gold_t_total")
    assert gold["layer"] == "gold" and gold["inserted"] == 1
    live = R.run(plane, PID, "live", by="Asha", trigger="schedule")  # production run: the gold table in the warehouse names the run
    assert run_log.get_run(plane, live["run_id"])["mode"] == "production" and run_log.get_run(plane, live["run_id"])["trigger"] == "schedule"
    with wh.connect(plane) as con:
        assert con.execute("select run_id, total from gold_t_total").fetchone() == (live["run_id"], 60)


def test_pipelines_read_their_own_production_run_and_next_slot(plane):
    plan(plane)
    assert [r["last_run"] for r in run_log.pipelines(plane)] == [None]  # approved, never run: "Not run yet"
    R.run(plane, PID, "sandbox", by="Asha")
    live = R.run(plane, PID, "live", by="Asha")
    [row] = run_log.pipelines(plane)
    assert row["source"] == PID and row["last_run"]["run_id"] == live["run_id"] and row["last_run"]["status"] == "ok"
    assert row["last_run"]["seconds"] is not None and row["last_run"]["rules"] and all(r["passed"] for r in row["last_run"]["rules"])
    assert row["next_run"]  # from the plan's schedule
