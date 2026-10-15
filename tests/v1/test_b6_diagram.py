"""B3 plan diagram: nodes by layer, edges from lineage and source names, new items marked, newest plan wins, missing plan is 404."""
import json
from types import SimpleNamespace

from sh_platform.v1 import b6_diagram as D

PLAN = {"project_id": "EV-0003", "version": 1, "state": "proposed",
        "sources": [{"code": "admin", "kind": "structured", "files": [], "owner": "Mei"}],
        "tables": [{"name": "bronze_admin_positions", "layer": "bronze", "purpose": "raw"},
                   {"name": "positions", "layer": "silver", "purpose": "core"},
                   {"name": "gold_ev_holdings_monthly", "layer": "gold", "purpose": "kpi"}],
        "lineage": [{"from": "bronze_admin_positions", "to": "positions"}, {"from": "positions", "to": "gold_ev_holdings_monthly"}]}


def test_diagram_layers_edges_and_new():
    d = D.diagram(PLAN)
    layer = {n["id"]: n["layer"] for n in d["nodes"]}
    assert layer["source:admin"] == "source" and layer["consumers"] == "consumer"
    new = {n["id"] for n in d["nodes"] if n["new"]}
    assert new == {"table:bronze_admin_positions", "table:gold_ev_holdings_monthly"}
    assert "table:positions" not in new
    pairs = {(e["from"], e["to"]) for e in d["edges"]}
    assert ("source:admin", "table:bronze_admin_positions") in pairs
    assert ("table:positions", "table:gold_ev_holdings_monthly") in pairs
    assert ("table:gold_ev_holdings_monthly", "consumers") in pairs
    assert d["state"] == "proposed"


def test_latest_plan_and_missing(tmp_path):
    plane = SimpleNamespace(path=lambda *p: tmp_path.joinpath(*p))
    try:
        D.latest_plan(plane, "EV-0003")
        raise AssertionError("expected Missing")
    except D.Missing:
        pass
    f = tmp_path / "build" / "EV-0003"
    f.mkdir(parents=True)
    (f / "plan-v2.json").write_text(json.dumps({**PLAN, "version": 2}), encoding="utf-8")
    (f / "plan-v10.json").write_text(json.dumps({**PLAN, "version": 10}), encoding="utf-8")
    (f / "plan-v1.json").write_text(json.dumps(PLAN), encoding="utf-8")
    assert D.latest_plan(plane, "EV-0003")["version"] == 10
    try:
        D.latest_plan(plane, "../x")
        raise AssertionError("expected Missing")
    except D.Missing:
        pass


def test_w2_core_silver_tables_the_plan_reads_are_drawn_between_bronze_and_gold():
    """Seeded and Span plans read core silver tables they do not rebuild: the Silver column must not be empty."""
    plan = {"project_id": "EV-0003", "version": 1, "state": "live", "sources": [{"code": "admin", "kind": "structured", "files": [], "owner": "Mei"}],
            "tables": [{"name": "bronze_admin_positions", "layer": "bronze", "depends_on": []},
                       {"name": "gold_ev_cash", "layer": "gold", "depends_on": ["position_snapshots", "portfolios"]}],
            "lineage": [{"from": "bronze_admin_positions", "to": "position_snapshots"}]}
    d = D.diagram(plan)
    layer = {n["id"]: n["layer"] for n in d["nodes"]}
    assert layer["table:position_snapshots"] == layer["table:portfolios"] == "silver"
    assert not next(n for n in d["nodes"] if n["id"] == "table:position_snapshots")["new"]
    pairs = {(e["from"], e["to"]) for e in d["edges"]}
    assert {("table:bronze_admin_positions", "table:position_snapshots"), ("table:position_snapshots", "table:gold_ev_cash"),
            ("table:portfolios", "table:gold_ev_cash")} <= pairs
    assert len(pairs) == len(d["edges"])  # no edge drawn twice
