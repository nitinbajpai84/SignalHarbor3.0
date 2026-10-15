"""A2 the trail, on the Evergreen seed in a tmp root. Fund A valuation: six steps, Mei as checker; a statement step the viewer may not
read is "restricted" and empty; a portfolio the viewer cannot see is refused; the metric, case and tile kinds; routes are declared."""
import json
import uuid

import duckdb
import pytest

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import a5_trail as T
from sh_platform.v1 import wh
from tools import seed_evergreen as S


@pytest.fixture()
def world(tmp_path):
    wh.reset_cache()
    root = tmp_path / "data"
    S.seed(root)
    plane = PlaneStore(root).plane_for("evergreen")
    yield plane
    wh.reset_cache()


def q(plane, sql, *args):
    con = duckdb.connect(str(wh.path(plane)), read_only=True)
    try:
        return con.execute(sql, list(args)).fetchall()
    finally:
        con.close()


def viewer(plane, name, roles):
    ext = q(plane, "select external_identity_id from users where display_name = ?", name)[0][0]
    return Viewer(name, frozenset(roles), False, ext)


def fund_a_valuation(plane) -> str:
    return str(q(plane, "select v.id from valuation_observations v join instruments i on i.id = v.instrument_id where i.canonical_name = 'Evergreen Growth I'")[0][0])


def test_fund_a_valuation_has_six_steps_with_mei_as_checker(world):
    t = T.trail(world, viewer(world, "Daniel Foo", ["sponsor"]), "valuation", fund_a_valuation(world))
    assert [s["key"] for s in t["steps"]] == ["source", "file", "read", "checked", "stored", "used_by"]
    assert all(s["state"] == "done" for s in t["steps"])
    assert t["figure"]["value"].startswith("10000000") and t["figure"]["currency"] == "USD"
    by = {s["key"]: s for s in t["steps"]}
    assert by["checked"]["who"] == "Mei Chen" and "matched" in by["checked"]["what"]
    assert "Manager statements" in by["source"]["what"] and by["source"]["who"] == "Mei Chen"
    assert "September investment report" in by["used_by"]["what"]


def test_a_reviewed_statement_field_names_the_reviewer_and_the_agent(world):
    plane, org = world, str(q(world, "select id from organizations")[0][0])
    vid = fund_a_valuation(plane)
    inst, mei = q(plane, "select instrument_id from valuation_observations where id = ?", vid)[0][0], q(plane, "select id from users where display_name = 'Mei Chen'")[0][0]
    src, grp = q(plane, "select id from source_systems where source_code = 'manager_email'")[0][0], q(plane, "select id from access_groups limit 1")[0][0]
    doc, run, fld = wh.new_id(), wh.new_id(), wh.new_id()
    with wh.connect(plane) as con:
        con.execute("insert into documents (id, organization_id, source_system_id, access_group_id, instrument_id, document_type, title, original_filename, original_uri,"
                    " content_hash, received_at, recorded_at, document_status, processing_status) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [doc, org, src, grp, inst, "manager_statement", "Fund A amended statement", "a.pdf", "x", "h", wh.now(), wh.now(), "final", "read"])
        con.execute("insert into agent_runs (id, organization_id, agent_type, model_id, prompt_version, tool_policy_version, started_at, run_status)"
                    " values (?,?,?,?,?,?,?,?)", [run, org, "intake", "m", "p", "t", wh.now(), "finished"])
        con.execute("insert into extracted_fields (id, organization_id, document_id, field_name, value_numeric, currency, page_number, line_number, confidence,"
                    " extracted_by_agent_run_id, review_status, reviewed_by, reviewed_at) values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [fld, org, doc, "nav", 10180000, "USD", 2, 14, "high", run, "confirmed", mei, wh.now()])
        con.execute("update valuation_observations set evidence_document_id = ?, extracted_field_id = ? where id = ?", [doc, fld, vid])
    by = {s["key"]: s for s in T.trail(plane, viewer(plane, "Mei Chen", ["analyst"]), "valuation", vid)["steps"]}
    assert "page 2, line 14" in by["read"]["what"] and by["read"]["who"] == "intake agent"
    assert by["checked"]["who"] == "Mei Chen" and by["file"]["refs"][0]["label"] == "Fund A amended statement"


def test_a_statement_the_viewer_may_not_read_is_restricted(world):
    plane, org = world, str(q(world, "select id from organizations")[0][0])
    vid = fund_a_valuation(plane)
    inst = q(plane, "select instrument_id from valuation_observations where id = ?", vid)[0][0]
    src = q(plane, "select id from source_systems where source_code = 'manager_email'")[0][0]
    other = wh.new_id()
    doc = wh.new_id()
    with wh.connect(plane) as con:
        con.execute("insert into access_groups (id, organization_id, group_name) values (?,?,?)", [other, org, "Board only"])
        con.execute("insert into documents (id, organization_id, source_system_id, access_group_id, instrument_id, document_type, title, original_filename, original_uri,"
                    " content_hash, received_at, recorded_at, document_status, processing_status) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [doc, org, src, other, inst, "board_paper", "Board paper", "b.pdf", "x", "h", wh.now(), wh.now(), "final", "read"])
        con.execute("update valuation_observations set evidence_document_id = ? where id = ?", [doc, vid])
    cio = T.trail(plane, viewer(plane, "Daniel Foo", ["sponsor"]), "valuation", vid)
    file = next(s for s in cio["steps"] if s["key"] == "file")
    assert file["state"] == "restricted" and file["refs"] == [] and "Board paper" not in json.dumps(file)
    assert len(cio["steps"]) == 6
    mei = next(s for s in T.trail(plane, viewer(plane, "Mei Chen", ["analyst"]), "valuation", vid)["steps"] if s["key"] == "file")
    assert mei["state"] == "done" and "Board paper" in mei["what"]


def test_a_portfolio_the_viewer_cannot_see_is_refused(world):
    stranger = Viewer("Nobody", frozenset({"participant"}), False, "acc-x")
    with pytest.raises(PermissionError):
        T.trail(world, stranger, "valuation", fund_a_valuation(world))
    with pytest.raises(LookupError):
        T.trail(world, stranger, "valuation", str(uuid.uuid4()))
    with pytest.raises(LookupError):
        T.trail(world, stranger, "valuation", "not-an-id")
    with pytest.raises(ValueError):
        T.trail(world, stranger, "mood", "x")


def test_metric_line_follows_its_source_and_a_total_is_added_up(world):
    cio = viewer(world, "Daniel Foo", ["sponsor"])
    line = str(q(world, "select id from metric_values where numeric_value = 10000000")[0][0])
    t = T.trail(world, cio, "metric", line)
    by = {s["key"]: s for s in t["steps"]}
    assert by["checked"]["who"] == "Mei Chen" and "Calculated by" in by["stored"]["what"] and "September investment report" in by["used_by"]["what"]
    total = T.trail(world, viewer(world, "Grace Ong", ["company_admin"]), "metric", str(q(world, "select id from metric_values where numeric_value = 57600000")[0][0]))
    assert "Added up from 3 line(s)" in total["steps"][0]["what"] and total["steps"][1]["state"] == "missing"


def test_case_trail_ends_with_the_case(world):
    vid = fund_a_valuation(world)
    inst = q(world, "select instrument_id from valuation_observations where id = ?", vid)[0][0]
    org = str(q(world, "select id from organizations")[0][0])
    ex = wh.new_id()
    with wh.connect(world) as con:
        con.execute("insert into exceptions (id, organization_id, instrument_id, exception_type, title, detected_at, materiality_status, status)"
                    " values (?,?,?,?,?,?,?,?)", [ex, org, inst, "revision", "Investigate the valuation difference", wh.now(), "material", "new"])
    t = T.trail(world, viewer(world, "Mei Chen", ["analyst"]), "case", ex)
    assert [s["key"] for s in t["steps"]][-1] == "used_by" and "Investigate the valuation difference" in t["steps"][-1]["what"]
    assert t["steps"][0]["state"] == "done"


def test_tile_trail_reads_plan_run_and_dashboard(world):
    plane = world
    pid = "prj-00000001"
    (plane.path("build") / pid).mkdir(parents=True)
    (plane.path("consume") / pid / "dashboards").mkdir(parents=True)
    plan = {"project_id": pid, "version": 2, "state": "live", "proposed_by": "Span", "approved_by": "Anita Rao", "approved_at": "2026-10-08T09:00:00+00:00",
            "sources": [{"code": "administrator", "kind": "structured", "files": [], "owner": "Mei Chen"}],
            "tables": [{"name": "bronze_administrator_positions", "layer": "bronze", "depends_on": []}, {"name": "gold_evergreen_cash_daily", "layer": "gold", "depends_on": ["bronze_administrator_positions"]}]}
    (plane.path("build", pid) / "plan-v1.json").write_text("{}", encoding="utf-8")
    (plane.path("build", pid) / "plan-v2.json").write_text(json.dumps(plan), encoding="utf-8")
    (plane.path("build", pid) / "runs.jsonl").write_text(json.dumps({"run_id": "r1", "status": "ok", "finished": "2026-10-08T10:00:00+00:00",
                                                                     "steps": [{"table": "gold_evergreen_cash_daily", "rows": 31, "status": "ok"}]}) + "\n", encoding="utf-8")
    cio_uid = str(q(plane, "select id from users where display_name = 'Daniel Foo'")[0][0])
    dash = {"id": "d1", "title": "Cash", "project_id": pid, "audience": [cio_uid], "created_by": "Mei Chen",
            "tiles": [{"id": "t1", "title": "Cash by entity", "kpi": "cash", "sql": "select * from gold_evergreen_cash_daily", "state": "accepted"}]}
    (plane.path("consume", pid, "dashboards") / "d1.json").write_text(json.dumps(dash), encoding="utf-8")
    t = T.trail(plane, viewer(plane, "Daniel Foo", ["sponsor"]), "tile", "t1")
    by = {s["key"]: s for s in t["steps"]}
    assert all(s["state"] == "done" for s in t["steps"])
    assert "bronze_administrator_positions" in by["file"]["what"] and by["checked"]["who"] == "Anita Rao" and "31 rows" in by["stored"]["what"]
    with pytest.raises(PermissionError):
        T.trail(plane, Viewer("Other", frozenset({"participant"}), False, "acc-x"), "tile", "t1")
    # a member of an audience group (not named) also passes: the cx_dash rule
    gid = str(q(plane, "select id from access_groups limit 1")[0][0])
    d2 = {**dash, "audience": [gid]}
    (plane.path("consume", pid, "dashboards") / "d1.json").write_text(json.dumps(d2), encoding="utf-8")
    in_group = q(plane, "select u.display_name from access_group_memberships m join users u on u.id = m.user_id where m.access_group_id = ? limit 1", gid)
    if in_group:
        T.trail(plane, viewer(plane, in_group[0][0], ["sponsor"]), "tile", "t1")
    with pytest.raises(LookupError):
        T.trail(plane, Viewer("Mei", frozenset({"analyst"}), False, "m"), "tile", "nope")


def test_route_is_declared():
    from pathlib import Path
    import sh_platform.v1 as v1
    assert "GET /api/v1/trail" in (Path(v1.__file__).parent / "a5.permissions.yaml").read_text(encoding="utf-8")
    from sh_platform.v1.a5_routes import router
    assert any(r.path == "/api/v1/trail" for r in router.routes)
