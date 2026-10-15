"""W14: the trace route gives a total per run: summed W01 step prices when present, else tokens only."""
from sh_platform.agents.runs import RunRegistry
from sh_platform.v1 import e6a_routes as R
from tests.v1.test_north_loop import plane as north_plane  # noqa: F401


def test_total_sums_prices_and_tokens():
    rows = [{"steps": [{"kind": "model", "tokens_in": 100, "tokens_out": 20, "cost_usd": 0.001},
                       {"kind": "tool"}, {"kind": "model", "tokens_in": 10, "tokens_out": 5, "cost_usd": None}]},
            {"steps": [{"kind": "model", "tokens_in": 1, "tokens_out": 1, "cost_usd": 0.0005}]}]
    got = R.total(rows)
    assert got["tokens"] == 137 and abs(got["cost_usd"] - 0.0015) < 1e-12


def test_total_without_prices_or_steps():
    assert R.total([{"steps": [{"kind": "model", "tokens_in": 3, "tokens_out": 2}]}]) == {"cost_usd": None, "tokens": 5}
    assert R.total([]) == {"cost_usd": None, "tokens": 0}


def test_trace_route_carries_steps_and_total(north_plane, monkeypatch):  # noqa: F811
    RunRegistry(north_plane).record_trace(trace_id="tr-w14", run_id="r1", agent="Span", status="done", elapsed_ms=9,
                                          steps=[{"kind": "model", "tokens_in": 10, "tokens_out": 5, "cost_usd": 0.002}])
    monkeypatch.setattr(R, "_admin", lambda request: north_plane)
    got = R.trace_runs(object(), "tr-w14")
    assert len(got["steps"]) == 1 and got["total"] == {"cost_usd": 0.002, "tokens": 15}
    assert R.trace_runs(object(), "tr-none")["total"] == {"cost_usd": None, "tokens": 0}
