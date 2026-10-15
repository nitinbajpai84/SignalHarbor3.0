"""H10: Lumen's starter dashboard. Rules only (no model), gold tables only, trails on every tile, accept / ask / send for approval."""
import json

import pytest
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import b6_run as R
from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import e0a_catalogue as cat
from sh_platform.v1 import p1_project, wh
from sh_platform.v1.p1_project import Refused

ADMIN = Viewer(name="Mei", roles=frozenset({"company_admin"}), account_id="acc-admin")
ANALYST = Viewer(name="Leo", roles=frozenset({"analyst"}), account_id="acc-leo")
SPONSOR = Viewer(name="Daniel", roles=frozenset({"sponsor"}), account_id="acc-sp")
READER = Viewer(name="Chia", roles=frozenset({"participant"}), account_id="acc-c")
T = "gold_perf_performance"
H = "gold_perf_holdings"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    plane = PlaneStore(tmp_path / "data").create("acme")
    pid = p1_project.create_project(plane, "int-1", "Monthly performance", "Nitin")["id"]
    with wh.connect(plane) as con:
        con.execute(f"create table {T} (month date, portfolio_return decimal(9,4), benchmark_return decimal(9,4))")
        con.execute(f"insert into {T} values ('2026-08-31',0.0210,0.0150),('2026-09-30',0.0417,0.0271)")
        con.execute(f"create table {H} (as_of date, fund varchar, entity varchar, holdings_usd decimal(18,2))")
        con.execute(f"insert into {H} values ('2026-09-30','Fund A',    'Trust', 10180000),('2026-09-30','Fund B','Trust', 6400000),('2026-09-30','Liquid','Holdings', 41200000)")
        con.execute("create table gold_other_x (a int)")
    cat.register_gold(plane, pid, "perf", "performance", [{"name": "month", "type": "date"}])
    cat.register_gold(plane, pid, "perf", "holdings", [{"name": "as_of", "type": "date"}])
    sow = {"goal": {"line": "Monthly performance against the benchmark", "decisions": ["keep or change the liquid allocation, by fund and by entity"]},
           "kpis": [{"code": "K1", "name": "Total holdings", "definition": "Holdings known now, by fund"},
                    {"code": "K2", "name": "Portfolio return"}, {"code": "K3", "name": "Benchmark return"}, {"code": "K9", "name": "Staff turnover"}]}
    f = plane.path("intents", "int-1", "sow.json")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(sow), encoding="utf-8")
    plan = plane.path("build", pid, "plan-v2.json")
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(json.dumps({"project_id": pid, "version": 2, "state": "live", "tables": [], "schedule": {}}), encoding="utf-8")
    R._log(plane, pid, {"run_id": "r1", "mode": "live", "status": "ok", "started": "2026-10-09T06:00:00+00:00", "finished": "2026-10-09T06:01:00+00:00",
                        "steps": [{"table": T, "status": "ok"}, {"table": H, "status": "ok"}]})
    return plane, pid


def test_proposal_is_deterministic_and_from_gold_with_trails(env):
    plane, pid = env
    a, b = L.propose_starter(plane, pid), L.propose_starter(plane, pid)
    assert [t["sql"] for t in a["tiles"]] == [t["sql"] for t in b["tiles"]] and a["from_intent"] and a["pack_version"] == 2
    titles = [t["title"] for t in a["tiles"]]
    assert any("against benchmark" in x.lower() for x in titles)          # the trend against the benchmark
    assert any("by fund" in x.lower() for x in titles) and any("by entity" in x.lower() for x in titles)  # the breakdowns the intent names
    assert not any("turnover" in x.lower() for x in titles)               # a KPI no table holds is not invented
    for t in a["tiles"]:
        D.check_sql(plane, pid, t["sql"])                                  # gold tables of this project only
        assert t["trail"]["pack_version"] == 2 and t["trail"]["reads"][0] in (T, H)
    assert "Pipeline version 2" in a["checks"] and "2 of 2 steps ok" in a["checks"]


def test_without_an_intent_it_says_so_and_uses_each_tables_first_figure(env):
    plane, pid = env
    plane.path("intents", "int-1", "sow.json").unlink()
    got = L.propose_starter(plane, pid)
    assert not got["from_intent"] and got["tiles"] and "first figure" in got["why"][0]


def test_start_makes_a_draft_once_and_consume_sees_nothing(env):
    plane, pid = env
    rec = S.start_starter(plane, pid)
    assert rec["lifecycle"]["status"] == "draft" and rec["starter"]["status"] == "proposed" and S.start_starter(plane, pid)["id"] == rec["id"]
    assert all(t["state"] == "proposed" and t["starter"] for t in rec["tiles"])
    assert D.list_for(plane, READER, pid) == []                            # nothing in Consume before an approval
    v = S.view(plane, ANALYST, pid, rec["id"])
    assert v["starter"]["why"] and v["can"]["edit"] and len(v["layout"]["items"]) >= 5
    assert all(i["reads"] for i in v["layout"]["items"] if i.get("tile"))


def test_accept_as_it_is_then_send_for_approval(env):
    plane, pid = env
    did = S.start_starter(plane, pid)["id"]
    v = S.accept_starter(plane, ANALYST, pid, did)
    assert v["starter"]["status"] == "accepted" and all(t["state"] == "accepted" for t in v["tiles"])
    with pytest.raises(Refused):
        S.accept_starter(plane, ANALYST, pid, did)                         # nothing left to accept
    D.submit(plane, ANALYST, pid, did)
    with pytest.raises(Refused):
        D.decide_version(plane, ANALYST, pid, did, True)                   # whoever accepted cannot approve
    assert D.decide_version(plane, SPONSOR, pid, did, True)["lifecycle"]["status"] == "published"
    assert [d for d in S.listing(plane, SPONSOR, pid) if d['id'] == did][0]['status'] == 'published'


def test_removed_widget_is_dropped_on_accept_and_asking_lumen_adds_to_it(env):
    plane, pid = env
    did = S.start_starter(plane, pid)["id"]
    v = S.view(plane, ANALYST, pid, did)
    gone = next(i for i in v["layout"]["items"] if i.get("tile"))
    S.set_layout(plane, ANALYST, pid, did, {"rev": v["rev"], "rows": v["layout"]["rows"], "items": [i for i in v["layout"]["items"] if i["id"] != gone["id"]]})
    out = S.ask_lumen(plane, ANALYST, pid, did, {"text": "show holdings by entity as bars"})   # add something specific
    assert out["proposals"]
    v = S.accept_starter(plane, ANALYST, pid, did)
    assert gone["tile"] not in [t["id"] for t in v["tiles"]]


def test_default_deny(env):
    plane, pid = env
    did = S.start_starter(plane, pid)["id"]
    with pytest.raises(Refused):
        S.accept_starter(plane, READER, pid, did)


def test_live_run_hook_proposes_it(env):
    plane, pid = env
    plan = R.latest_plan(plane, pid, live=True)
    plan["state"] = "approved"
    R._move(plane, pid, {**plan, "state": "live"}, "live", "runner")
    assert S._starter_of(plane, pid) is not None


def test_routes_start_accept_and_submit(env, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from sh_platform.v1 import b7_routes
    plane, pid = env
    cur = {"v": ANALYST}
    monkeypatch.setattr(b7_routes, "viewer_of", lambda request: cur["v"])
    monkeypatch.setattr(b7_routes, "_plane", lambda request: plane)
    app = FastAPI()
    app.include_router(b7_routes.router)
    c, base = TestClient(app), f"/api/v1/build/p/{pid}/studio"
    cur["v"] = READER
    assert c.post(base + "/starter").status_code == 403
    cur["v"] = ANALYST
    v = c.post(base + "/starter").json()
    assert v["starter"]["status"] == "proposed" and c.post(base + "/starter").json()["id"] == v["id"]
    assert c.post(f"{base}/{v['id']}/submit").json()["status"] == "submitted"   # send for approval accepts first
    rec = D._load(plane, pid, v["id"])
    assert rec["starter"]["status"] == "accepted" and all(t["state"] == "accepted" for t in rec["tiles"])
