"""POST /api/company/whatif: path through two edges, a lever halves, an outsider gets no values, a listed viewer does. Synthetic data."""
import json

import duckdb
import pytest

from sh_platform.plane import PlaneStore
from tests.graph.test_graph_route import FAMILY, e, login, n  # noqa: F401  (login is a fixture)

DOC = {"version": 1, "built_at": "2026-10-06T00:00:00+00:00",
       "nodes": [n("field:f", "Field", "Fees Charged"), n("source:s", "Source", "Custody"), n("lever:a", "Lever", "Rebalance"), n("problem:p", "Problem", "Drift"), n("measure:m", "Measure", "Concentration")],
       "edges": [e("lever:a", "problem:p", "moves"), e("problem:p", "measure:m", "measured_by"),
                 e("source:s", "field:f", "uses"), e("measure:m", "source:s", "fed_by")]}


@pytest.fixture
def api(login, tmp_path):  # noqa: F811
    plane = PlaneStore(tmp_path / "data").plane_for(FAMILY)
    plane.path("graph", "company.json").write_text(json.dumps(DOC), encoding="utf-8")
    plane.path("build").mkdir(parents=True, exist_ok=True)
    plane.path("build", "blueprint.json").write_text(json.dumps({"access": [{"mart": "gold.m", "may_see": ["Nobody Named"]}]}), encoding="utf-8")
    plane.area("warehouse").mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(plane.path("warehouse", "company.readonly.duckdb")))
    con.execute("create schema gold; create table gold.m as select '2026-09' as period, 100.0 as value")
    con.close()
    return login


def post(c, driver="lever:a", pct=20):
    return c.post("/api/company/whatif", json={"driver": driver, "change_pct": pct}, headers={"X-CSRF-Token": c.cookies["sh_csrf"]})


def test_path_found_through_two_edges(api):
    r = post(api("analyst"))
    assert r.status_code == 200, r.text
    assert r.json()["moved"][0]["path"] == ["lever:a", "problem:p", "measure:m"]


def test_a_lever_halves_the_change(api):
    assert post(api("analyst"), pct=20).json()["moved"][0]["change_pct"] == 10


def test_the_from_value_is_the_feeds_value(api):
    # the same figure Feeds shows this viewer (no baseline: the gold mart, named M)
    feeds = {m["code"]: m for m in api("analyst").get("/api/company/feeds").json()["measures"]}
    m = post(api("analyst")).json()["moved"][0]
    assert m["latest"]["value"] == feeds["M"]["latest"]["value"] == 100.0 and m["latest"]["moved_value"] == 110.0


def test_an_unsigned_edge_is_assumed_same_way_and_says_so(api):
    r = post(api("analyst")).json()
    m = r["moved"][0]
    assert m["assumed_direction"] and m["text"].endswith("100 to 110 (assumed same way)") and "assumed to move the same way" in r["basis"].lower()
    assert "moves" not in r["basis"] and "edges" not in r["basis"]


def test_a_lowers_edge_moves_the_measure_the_other_way():
    from sh_platform.build.whatif import _reach
    g = {"nodes": [n("field:f", "Field", "Fees"), n("measure:m", "Measure", "Net")], "edges": [e("field:f", "measure:m", "lowers")]}
    (m,) = _reach(g, "field:f", 10)
    assert m["change_pct"] == -10 and not m["assumed_direction"]


def keep(c, note="n"):
    return c.post("/api/company/whatif/save", json={"driver": "lever:a", "change_pct": 20, "note": note}, headers={"X-CSRF-Token": c.cookies["sh_csrf"]})


def test_save_and_list_are_per_person(api):
    c = api("analyst")
    r = keep(c)
    assert r.status_code == 200, r.text
    got = c.get("/api/company/whatif/scenarios").json()["scenarios"]
    assert [x["id"] for x in got] == [r.json()["id"]] and got[0]["result"]["moved"][0]["change_pct"] == 10
    d = c.delete(f"/api/company/whatif/scenarios/{got[0]['id']}", headers={"X-CSRF-Token": c.cookies["sh_csrf"]})
    assert d.status_code == 200 and c.get("/api/company/whatif/scenarios").json()["scenarios"] == []


def test_a_scenario_is_never_served_to_another_account(api):
    mine = api("analyst")
    sid = keep(mine).json()["id"]
    other = api("sponsor")
    assert other.get("/api/company/whatif/scenarios").json()["scenarios"] == []
    assert other.delete(f"/api/company/whatif/scenarios/{sid}", headers={"X-CSRF-Token": other.cookies["sh_csrf"]}).status_code == 404


def test_a_kept_scenario_is_written_under_context_whatif(api, tmp_path):
    c = api("analyst")
    keep(c)
    plane = PlaneStore(tmp_path / "data").plane_for(FAMILY)
    (f,) = plane.path("context", "whatif").glob("*.json")
    item = json.loads(f.read_text(encoding="utf-8"))[0]
    assert item["driver"] == "lever:a" and item["change_pct"] == 20 and item["saved_at"] and item["result"]["moved"]


def test_a_field_reaches_the_measures_its_source_feeds(api):
    moved = post(api("analyst"), driver="field:f", pct=10).json()["moved"]
    assert [m["path"] for m in moved] == [["field:f", "source:s", "measure:m"]]
    assert moved[0]["change_pct"] == 10
