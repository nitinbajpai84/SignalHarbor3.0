"""X1: the v3 demo project on Evergreen: signed intent with a swim lane, an approved live plan, gold tables with the right figures, three
accepted tiles whose SQL runs, and a second run that changes nothing. Temporary data root; no model."""
import json
import sys
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.v1 import p1_project, wh  # noqa: E402
from tools import seed_v3_demo as X  # noqa: E402


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    root = tmp_path_factory.mktemp("x1") / "data"
    first = X.seed(root)
    plane = PlaneStore(root).plane_for("evergreen")
    yield root, plane, first
    mp.undo()


def rows(plane, sql):
    with duckdb.connect(str(wh.path(plane))) as con:
        return con.execute(sql).fetchall()


def test_intent_signed_with_swim_lane_and_sources(seeded):
    _, plane, first = seeded
    sow = json.loads(plane.path("intents", first["intent_id"], "sow.json").read_text(encoding="utf-8"))
    assert sow["state"] == "signed" and sow["signature"]["name"] == X.CIO
    assert len({s["who"] for s in sow["process"]["steps"]}) >= 3
    assert {s["structure"] for s in sow["sources"]} == {"structured", "unstructured"}
    p = p1_project.read(plane, first["project_id"])
    assert p["stage"] == "live" and p["people"]["head_of_data"] == X.HEAD


def test_plan_approved_by_someone_else_and_live(seeded):
    _, plane, first = seeded
    plan = json.loads(plane.path("build", first["project_id"], "plan-v1.json").read_text(encoding="utf-8"))
    assert plan["state"] == "live" and plan["approved_by"] != plan["proposed_by"]
    assert {t["name"] for t in plan["tables"] if t["layer"] == "gold"} == {X.HOLDINGS, X.CASH, X.BENCH}
    assert {t["name"] for t in plan["tables"] if t["layer"] == "bronze"} == {X.BRONZE_ADMIN, X.BRONZE_TRADE}
    runs = [json.loads(x) for x in plane.path("build", first["project_id"], "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["mode"] for r in runs] == ["sandbox", "live"] and all(r["status"] == "ok" for r in runs)
    assert plane.path("warehouse", "sandbox.duckdb").is_file()


def test_gold_figures(seeded):
    _, plane, _ = seeded
    hold = {r[0]: r[1:] for r in rows(plane, f"select holding, net_worth_usd, net_worth_sgd, status from {X.HOLDINGS} where report_month = date '2026-09-01'")}
    assert hold["Evergreen Growth I"][0] == Decimal(10_000_000) and hold["Evergreen Growth I"][2] == "estimated"
    assert float(hold["Evergreen Growth I"][1]) == pytest.approx(13_412_000)  # 30 Sep fixing 1.3412
    assert sum(v[0] for v in hold.values()) == Decimal(57_600_000)
    cash = {(r[0], r[1]): r[2] for r in rows(plane, f"select entity, view_type, cash_usd from {X.CASH}")}
    # C1 fix: the gold cash view names its source (accounting -> administrator, operational -> trading export)
    assert cash[("Entity B", "administrator")] - cash[("Entity B", "trading export")] == Decimal(12_400)
    assert len(rows(plane, f"select distinct report_month from {X.HOLDINGS}")) == 2  # two report months, so "why did this move" has two periods
    assert len(rows(plane, f"select 1 from {X.BRONZE_ADMIN}")) and len(rows(plane, f"select 1 from {X.BRONZE_TRADE}"))


def test_dashboard_tiles_run_and_are_shared(seeded):
    _, plane, first = seeded
    d = json.loads(plane.path("consume", first["project_id"], "dashboards", f"{X.DASH_ID}.json").read_text(encoding="utf-8"))
    assert len(d["tiles"]) == 3 and {t["state"] for t in d["tiles"]} == {"accepted"} and len(d["audience"]) == 2
    for t in d["tiles"]:
        assert t["sql"].lower().startswith("select") and "data" not in t["spec"]
        assert rows(plane, t["sql"])


def test_second_run_changes_nothing(seeded):
    root, plane, first = seeded
    before = plane.path("build", first["project_id"], "runs.jsonl").read_text(encoding="utf-8")
    again = X.seed(root)
    assert again["project_id"] == first["project_id"] and again["build"] == "kept" and again["dashboard"] == "kept"
    assert plane.path("build", first["project_id"], "runs.jsonl").read_text(encoding="utf-8") == before
    assert len([p for p in p1_project.all_projects(plane) if p["title"] == X.TITLE]) == 1


def test_demo_dashboard_opens_in_consume_for_the_people_it_names(seeded):
    """C1's id rules, users.id audience, the maker's account id, gold in the catalogue, and the demo's own ask resolves."""
    from sh_platform.profile.view import Viewer
    from sh_platform.v1 import cx_dash as D, cx_lumen as L, cx_share, e0a_catalogue as cat
    _, plane, first = seeded
    pid = first["project_id"]
    ids, _n = X.EG.accounts(seeded[0])
    cio, fin = Viewer(X.CIO, frozenset({"sponsor"}), False, ids[X.CIO]), Viewer(X.FINANCE, frozenset({"approver"}), False, ids[X.FINANCE])
    eng = Viewer(X.ENGINEER, frozenset({"analyst"}), False, ids[X.ENGINEER])
    assert sorted(cat.tables_for_project(plane, pid)["gold"]) == sorted([X.HOLDINGS, X.CASH, X.BENCH]) and len(cat.tables_for_project(plane, pid)["bronze"]) == 2
    assert {t["name"]: t["rows"] for t in D.gold_tables(plane, pid)}[X.CASH] == 6
    assert [d["id"] for d in D.list_for(plane, cio, pid)] == [X.DASH_ID] and D.get(plane, fin, pid, X.DASH_ID)["id"] == X.DASH_ID
    for t in D.get(plane, eng, pid, X.DASH_ID)["tiles"]:
        assert D.tile_data(plane, fin, pid, X.DASH_ID, t["id"])["rows"]
    assert cx_share.notify(plane, pid, X.DASH_ID, "shared", token="x")["made"]
    d = D.create(plane, cio, pid, "Ask")
    out = L.ask(plane, cio, pid, d["id"], "show net worth by entity per month as a line chart")
    assert out["proposals"] and out["proposals"][0]["spec"]["encoding"]["x"]["field"] == "report_month"
    assert "decrease" not in out["reply"] and "only one period" not in L.explain(plane, cio, pid, d["id"], out["proposals"][0]["id"])["answer"]


def test_demo_plan_passes_the_plan_checker(seeded):
    """B2's validate accepts the demo plan (no empty silver rows), so a schedule change or a Span question on the demo works."""
    from sh_platform.v1 import b6_plan
    _, plane, first = seeded
    plan = json.loads(plane.path("build", first["project_id"], "plan-v1.json").read_text(encoding="utf-8"))
    assert plan["project_slug"] == X.SLUG and {t["layer"] for t in plan["tables"]} == {"bronze", "gold"}
    assert len(b6_plan.validate(plane, plan)["tables"]) == 5
