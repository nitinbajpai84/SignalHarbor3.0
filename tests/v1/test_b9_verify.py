"""V5W-3: control totals against the loaded files, verify with who and when, send for review, review against the signed benchmark (k7), flag,
fix through the rules register and run the copy again, accept. No model is called. Data comes from test_k7's plane."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml
from test_k7 import ORG, plane, wh, nid  # noqa: F401  (plane is the fixture)

from sh_platform.profile.view import Viewer
from sh_platform.v1 import b9_routes as RT
from sh_platform.v1 import b9_verify as V
from sh_platform.v1 import p1_project as P1
from sh_platform.v1.i2_north import Refused

PF = "00000000-0000-0000-0000-000000000002"
LEO = Viewer("Leo Park", frozenset({"analyst"}), False, "acc-leo")
ADMIN = Viewer("Raj Admin", frozenset({"company_admin"}), False, "acc-raj")
GUEST = Viewer("Gus", frozenset({"participant"}), False, "acc-gus")


@pytest.fixture()
def prj(plane):
    with wh.connect(plane) as con:
        con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values (?,?,?,?,?,?)",
                    [PF, ORG, nid(), "EG-LIQUID", "Liquid", "USD"])
        con.execute("create table bronze_pos (id integer, amount integer)")
        con.execute("insert into bronze_pos values (1, 10), (2, 20)")
    rec = P1.create_project(plane, "intent-1", "Monthly performance", "Mei Chen")
    write_plan(plane, rec["id"], [("IDX.EQ", "0.36"), ("IDX.BOND", "0.24"), ("IDX.PE", "0.40")])
    return rec["id"]


def write_plan(plane, pid, weights):
    vals = ", ".join(f"('{k}', {w})" for k, w in weights)
    plan = {"project_id": pid, "version": 1, "state": "approved", "sources": [], "schedule": {"freq": "daily", "at": "06:00", "day": None},
            "tables": [{"name": "gold_total", "layer": "gold", "sql": "create table gold_total as select sum(amount) as amount from bronze_pos", "depends_on": ["bronze_pos"]},
                       {"name": "gold_benchmark_weights", "layer": "gold", "depends_on": [],
                        "sql": f"create table gold_benchmark_weights as select * from (values {vals}) t(series_key, weight)"},
                       {"name": "bronze_pos", "layer": "bronze", "sql": "", "depends_on": []}]}
    f = plane.path("build", pid, "plan-v1.json")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(plan), encoding="utf-8")


def batch(plane, expected, loaded):
    with wh.connect(plane) as con:
        sid = con.execute("select id from source_systems limit 1").fetchone()
        sid = sid[0] if sid else None
        if sid is None:
            sid = nid()
            con.execute("insert into source_systems (id, organization_id, source_code, source_name, source_type) values (?,?,?,?,?)", [sid, ORG, "t", "T", "file"])
        b = nid()
        con.execute("insert into source_batches (id, organization_id, source_system_id, batch_reference, received_at, loaded_at, storage_uri, validation_status)"
                    " values (?,?,?,?,now(),now(),?, 'loaded')", [b, ORG, sid, "positions-sep", "file:///x/Positions Sep.xlsx"])
        con.execute("insert into batch_control_totals (id, organization_id, source_batch_id, measure_name, expected_value, loaded_value, tolerance, passed)"
                    " values (?,?,?,?,?,?,0,?)", [nid(), ORG, b, "market_value_total", expected, loaded, expected == loaded])


def test_verify_compares_files_with_the_run_and_records_who_and_when(plane, prj):
    batch(plane, "30", "30")
    V.R.run(plane, prj, "sandbox", by="Leo Park")
    figs = {f["figure"]: f for f in V.figures(plane, prj)}
    assert figs["Market value total"]["check"] == "Match" and "Positions Sep.xlsx" in figs["Market value total"]["traced_to"]
    assert figs["Total: total of amount"]["check"] == "Match" and figs["Total: total of amount"]["source"] == "30"
    assert figs["Benchmark weights: total of weight"]["check"] == "Not compared"
    with pytest.raises(Refused) as e:
        V.mark_verified(plane, GUEST, prj)
    assert e.value.status == 403
    got = V.mark_verified(plane, LEO, prj)
    assert got["by"] == "Leo Park" and got["at"] and V.load(plane, prj)["verified"]["by"] == "Leo Park"


def test_a_figure_that_differs_blocks_verification(plane, prj):
    batch(plane, "30", "31")
    V.R.run(plane, prj, "sandbox", by="Leo")
    with pytest.raises(Refused) as e:
        V.mark_verified(plane, LEO, prj)
    assert e.value.status == 409 and "Market value total" in e.value.message


def test_send_needs_verified_then_review_flag_fix_accept(plane, prj, monkeypatch):
    batch(plane, "30", "30")
    V.R.run(plane, prj, "sandbox", by="Leo")
    body = {"portfolio": PF, "code": "BLEND", "month": "2026-09"}
    with pytest.raises(Refused) as e:
        V.send_for_review(plane, LEO, prj, body)
    assert e.value.status == 409
    V.mark_verified(plane, LEO, prj)
    rv = V.send_for_review(plane, LEO, prj, body)
    assert rv["owner"] == "Mei Chen" and rv["state"] == "requested"
    assert any(c["to"] == "Mei Chen" for c in P1.comments(plane, prj))   # the event the owner sees

    c = V.comparison(plane, ADMIN, prj, V.load(plane, prj)["review"])     # the run used 36/24/40, the signed version has 60/40
    rows = {r["component"]: r for r in c["rows"]}
    assert c["signed_version"] == 1 and not c["same"]
    assert rows["IDX.EQ"]["signed_weight_pct"] == "60.0000" and rows["IDX.EQ"]["used_weight_pct"] == "36.0000" and rows["IDX.EQ"]["gap_pts"] == "-24.0000"
    assert rows["IDX.PE"]["signed_weight_pct"] == "0.0000" and rows["IDX.PE"]["differs"]
    with pytest.raises(Refused) as e:
        V.accept(plane, ADMIN, prj)                                      # figures still differ
    assert e.value.status == 409
    with pytest.raises(Refused) as e:
        V.flag(plane, LEO, prj, "no")                                    # the engineer is not the owner
    assert e.value.status == 403

    out = V.flag(plane, ADMIN, prj, "The private sleeve weight is not the signed one.")
    assert out["state"] == "flagged" and out["case_id"] and out["issues"][0]["text"].startswith("The private")

    spec = importlib.util.spec_from_file_location("real_e3_rules", Path(V.__file__).with_name("e3_rules.py"))  # test_k7 stubs the register; use the real one
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e3_rules", mod)
    monkeypatch.setattr(sys.modules["sh_platform.v1"], "e3_rules", mod, raising=False)
    fix = V.propose_fix(plane, LEO, prj)
    assert fix["run_status"] == "ok" and fix["rule_version_id"]
    write_plan(plane, prj, [("IDX.EQ", "0.6"), ("IDX.BOND", "0.4")])   # Span's plan change: the table reads the signed version
    V.R.run(plane, prj, "sandbox", by="Leo")
    assert V.comparison(plane, ADMIN, prj, V.load(plane, prj)["review"])["same"]
    with pytest.raises(Refused) as e:
        V.accept(plane, ADMIN, prj)                                      # the rerun is not verified yet
    assert e.value.status == 409 and "verifies the new run" in e.value.message
    assert V.view(plane, LEO, prj)["stale"]                               # W3 walk: the screen offers to verify the new run
    V.mark_verified(plane, LEO, prj)
    with pytest.raises(Refused) as e:
        V.accept(plane, Viewer("Leo Park", frozenset({"analyst", "company_admin"}), False, "acc-leo"), prj)  # maker never checker
    assert e.value.status == 403
    done = V.accept(plane, ADMIN, prj)
    assert done["state"] == "accepted" and done["accepted_by"] == "Raj Admin" and done["accepted_at"]
    assert V.view(plane, ADMIN, prj)["review"]["state"] == "accepted"


def test_every_route_is_declared():
    table = yaml.safe_load((Path(V.__file__).with_name("b9.permissions.yaml")).read_text())["routes"]
    assert {f"{m} {r.path}" for r in RT.router.routes for m in r.methods} == set(table)


def test_w3_form_defaults_lumen_note_and_council_lines(plane, prj):
    batch(plane, "30", "30")
    V.R.run(plane, prj, "sandbox", by="Leo")
    sg = V.suggest(plane, ADMIN, prj)
    assert sg["portfolio"] == "EG-LIQUID" and sg["code"] == "BLEND" and len(sg["month"]) == 7
    V.mark_verified(plane, LEO, prj)
    assert len(V.view(plane, LEO, prj)["suggest"]["month"]) == 7  # LEO sees no portfolio, so none is pre-filled
    assert V.figure_lines(plane, ADMIN, prj) is None          # no review yet: nothing is invented
    V.send_for_review(plane, LEO, prj, {"portfolio": PF, "code": "BLEND", "month": "2026-09"})
    c = V.comparison(plane, ADMIN, prj, V.load(plane, prj)["review"])
    assert "differ" in c["lumen_note"] and "IDX.EQ is 36.0000% in the run" in c["lumen_note"]
    assert V.view(plane, LEO, prj)["suggest"] is None          # once sent, the form is gone
    fl = V.figure_lines(plane, ADMIN, prj)
    assert fl is None or ("performance:" in fl["sentence"] and fl["email_subject"].startswith("September:"))


def test_w3_walk_a_run_without_a_weights_table_can_be_sent_back_but_not_accepted(plane, prj):
    plan = json.loads(plane.path("build", prj, "plan-v1.json").read_text(encoding="utf-8"))
    plan["tables"] = [t for t in plan["tables"] if t["name"] != "gold_benchmark_weights"]
    plane.path("build", prj, "plan-v1.json").write_text(json.dumps(plan), encoding="utf-8")
    batch(plane, "30", "30")
    V.R.run(plane, prj, "sandbox", by="Leo")
    V.mark_verified(plane, LEO, prj)
    V.send_for_review(plane, LEO, prj, {"portfolio": PF, "code": "BLEND", "month": "2026-09"})
    v = V.view(plane, ADMIN, prj)
    assert v["comparison"] is None and v["comparison_error"] and v["can"]["flag"] and not v["can"]["accept"]
    mei = Viewer("Mei Chen", frozenset({"analyst"}), False, "acc-mei")  # the owner herself, not an admin who sees every case
    with wh.connect(plane) as con:
        con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, is_active, created_at) values (?,?,?,?,?,true,now())",
                    [nid(), ORG, "acc-mei", "Mei Chen", "mei@x.test"])
    out = V.flag(plane, mei, prj, "There is no benchmark mix in the run.")
    assert out["state"] == "flagged" and out["first"] is None
    assert not V.view(plane, Viewer("Leo Park", frozenset({"analyst", "data_engineer"}), False, "acc-leo"), prj)["can"]["fix"]  # the fix is a plan change


def test_w3_walk_two_signed_parts_on_one_series_compare_as_their_total(plane, prj, monkeypatch):
    comps = [{"series_key": "IDX.EQ", "weight": "0.42", "return": {"value": "0.035", "pct": "3.50"}, "spread_return": {"value": "0"}},
             {"series_key": "IDX.EQ", "weight": "0.30", "return": {"value": "0.0375", "pct": "3.75"}, "spread_return": {"value": "0.0025"}},
             {"series_key": "IDX.BOND", "weight": "0.28", "return": {"value": "0.004", "pct": "0.40"}, "spread_return": {"value": "0"}}]
    month = {"components": comps, "benchmark": {"value": "0.0271"}, "portfolio": {"value": "0.0417"}, "problems": []}
    from sh_platform.v1 import k7_routes
    monkeypatch.setattr(k7_routes, "monthly", lambda *a: {"months": [month], "version_used": {"version": 1, "name": "Blend"}})
    monkeypatch.setattr(V, "_used_weights", lambda *a: ("gold_benchmark_weights", {"IDX.EQ": V._dec("0.72"), "IDX.BOND": V._dec("0.28")}))
    c = V.comparison(plane, ADMIN, prj, {"portfolio": PF, "code": "BLEND", "month": "2026-09"})
    assert c["same"] and [r["component"] for r in c["rows"]] == ["IDX.EQ", "IDX.EQ plus spread", "IDX.BOND"]
    assert c["benchmark_run_pct"] == V._pct(V._dec("0.42") * V._dec("0.035") + V._dec("0.30") * V._dec("0.0375") + V._dec("0.28") * V._dec("0.004"))
