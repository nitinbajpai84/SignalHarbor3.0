"""E6a: a run is recorded on success and on exception; one trace id follows nested work; cost comes from the router log when priced; admin only."""
import pytest
from fastapi import HTTPException

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e6_trace as T, router, wh
from sh_platform.v1.e6_trace import _user_uuid as _uuid

VIEWER = Viewer("Mei", frozenset({"analyst"}), False, "acc-mei")
EXC = "11111111-1111-1111-1111-111111111111"
SQL = "select run_status, tool_calls, cost_usd, trace_id, acting_for_user_id, finished_at, exception_id from agent_runs order by started_at"


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    return PlaneStore(tmp_path / "data").create("acme")


def rows(plane):
    with wh.connect(plane) as con:
        return con.execute(SQL).fetchall()


def test_success_is_recorded_with_tool_calls_and_cost(plane):
    with T.agent_run(plane, VIEWER, "investigation", "m1", "p1", "t1", exception_id=EXC) as run:
        run.tool_call()
        run.tool_call()
        router.log_cost(plane, {"at": wh.now().isoformat(), "agent": "investigation", "tokens_in": 10, "cost_usd": 0.0125})
        router.log_cost(plane, {"at": wh.now().isoformat(), "agent": "other", "cost_usd": 9})
        run.output = "case://1"
    (status, calls, cost, trace, user, finished, exc), = rows(plane)
    user, exc = str(user), str(exc)
    assert (status, calls, float(cost), user, exc) == ("succeeded", 2, 0.0125, _uuid(plane, "acc-mei"), EXC)
    assert finished and trace == run.trace_id


def test_exception_is_recorded_and_reraised(plane):
    with pytest.raises(RuntimeError):
        with T.agent_run(plane, VIEWER, "data", "m1", "p1", "t1"):
            raise RuntimeError("boom")
    (status, _, cost, _, _, finished, _), = rows(plane)
    assert status == "failed" and cost is None and finished


def test_one_trace_id_follows_the_work(plane):
    with T.trace() as tid:
        with T.agent_run(plane, VIEWER, "intake", "m", "p", "t"):
            pass
        with T.agent_run(plane, VIEWER, "investigation", "m", "p", "t"):
            assert T.current_trace_id() == tid
    with T.agent_run(plane, VIEWER, "data", "m", "p", "t"):
        pass
    assert len(T.by_trace(plane, tid)) == 2 and T.current_trace_id() is None


def test_summary_by_agent_and_day_and_admin_only(plane, monkeypatch):
    with T.agent_run(plane, VIEWER, "data", "m", "p", "t"):
        pass
    with pytest.raises(ValueError):
        with T.agent_run(plane, VIEWER, "data", "m", "p", "t"):
            raise ValueError
    s = T.summary(plane)
    assert [(g["agent_type"], g["runs"], g["failures"]) for g in s["by_agent_day"]] == [("span", 2, 1)] and len(s["runs"]) == 2
    assert T.summary(plane, agent_type="intake")["runs"] == []
    from sh_platform.v1 import e6a_routes as R
    monkeypatch.setattr(R, "viewer_of", lambda request: VIEWER)
    with pytest.raises(HTTPException) as e:
        R._admin(object())
    assert e.value.status_code == 403
