"""B4: tables run in dependency order; a failed step keeps the previous gold table; sandbox leaves the live warehouse alone and live needs approval;
schedules come due once; two runs of one project never overlap; the Airflow text has one task per table; cards reach people in Action."""
import ast
import json
from datetime import datetime

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import b6_run as R, b6_schedule as S, wh
from sh_platform.v1.e1_write import org_id

PID = "prj-0a0b0c01"
RAW = "create table bronze_t_raw as select * from (values (1, 10), (2, 20), (3, 30)) t(id, v)"
SUM = "create table gold_t_total as select sum(v) as total from bronze_t_raw"
MAKER, CIO = wh.new_id(), wh.new_id()
BAD = "create table gold_t_total as select sum(nope) as total from bronze_t_raw"


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    return PlaneStore(tmp_path / "data").create("acme")


def plan(plane, version=1, state="approved", gold=SUM, schedule=None, **kw):
    # gold is listed first on purpose: the runner must reorder by depends_on
    p = {"project_id": PID, "version": version, "sources": [{"code": "admin_export", "kind": "structured", "files": [], "owner": "Ops"}],
         "tables": [{"name": "gold_t_total", "layer": "gold", "sql": gold, "depends_on": ["bronze_t_raw"], "columns": []},
                    {"name": "bronze_t_raw", "layer": "bronze", "sql": RAW, "depends_on": [], "columns": []},
                    {"name": "bronze_t_file", "layer": "bronze", "sql": "", "depends_on": [], "columns": []}],
         "schedule": schedule or {"freq": "daily", "at": "06:00", "day": None}, "state": state, "proposed_by": "acc-maker", **kw}
    f = plane.path("build", PID, f"plan-v{version}.json")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(p), encoding="utf-8")
    return p


def total(plane):
    with wh.connect(plane) as con:
        return con.execute("select total from gold_t_total").fetchone()[0]


def test_order_and_live_run(plane):
    p = plan(plane)
    assert [t["name"] for t in R.order(p)] == ["bronze_t_raw", "bronze_t_file", "gold_t_total"] or \
        [t["name"] for t in R.order(p)].index("bronze_t_raw") < [t["name"] for t in R.order(p)].index("gold_t_total")
    rec = R.run(plane, PID, "live")
    assert rec["status"] == "ok" and total(plane) == 60
    steps = {s["table"]: s for s in rec["steps"]}
    assert steps["gold_t_total"]["rows"] == 1 and steps["bronze_t_raw"]["rows"] == 3 and steps["bronze_t_file"]["status"] == "filled by file loads"
    assert R.runs(plane, PID)[0]["run_id"] == rec["run_id"]
    assert R.latest_plan(plane, PID)["state"] == "live"


def test_loop_refused():
    with pytest.raises(R.Refused):
        R.order({"tables": [{"name": "a", "depends_on": ["b"]}, {"name": "b", "depends_on": ["a"]}]})


def test_failure_keeps_previous_gold(plane):
    plan(plane)
    R.run(plane, PID, "live")
    plan(plane, version=2, state="live", gold=BAD)
    rec = R.run(plane, PID, "live")
    assert rec["status"] == "failed"
    bad = [s for s in rec["steps"] if s["status"] == "failed"]
    assert len(bad) == 1 and bad[0]["table"] == "gold_t_total" and "could not be built" in bad[0]["error"]
    assert total(plane) == 60  # the last good run is untouched
    with wh.connect(plane) as con:
        assert not con.execute("select 1 from information_schema.tables where table_name like '%__next'").fetchone()


def test_sql_that_destroys_is_refused_per_step(plane):
    plan(plane, gold="create table gold_t_total as select 1; drop table users")
    rec = R.run(plane, PID, "live")
    assert rec["status"] == "failed"
    with wh.connect(plane) as con:
        assert con.execute("select count(*) from information_schema.tables where table_schema = 'main' and table_name = 'users'").fetchone()[0] == 1


def test_sandbox_leaves_live_alone_and_live_needs_approval(plane):
    plan(plane, state="proposed")
    with pytest.raises(R.Refused):
        R.run(plane, PID, "live")
    rec = R.run(plane, PID, "sandbox")
    assert rec["status"] == "ok" and plane.path("warehouse", "sandbox.duckdb").exists()
    with wh.connect(plane) as con:
        assert not con.execute("select 1 from information_schema.tables where table_name = 'gold_t_total'").fetchone()
    plan(plane, state="approved")
    R.run(plane, PID, "sandbox")
    assert R.latest_plan(plane, PID)["state"] == "built"


def test_no_overlap(plane):
    plan(plane)
    key = f"{plane.root}|{PID}"
    R._RUNNING.add(key)
    try:
        with pytest.raises(R.Refused, match="already running"):
            R.run(plane, PID, "live")
    finally:
        R._RUNNING.discard(key)


def test_schedule_due_once(plane):
    p = plan(plane)
    assert S.is_due(p, None, datetime(2026, 10, 9, 7, 0))
    assert S.is_due(p, None, datetime(2026, 10, 9, 5, 0))  # yesterday's slot passed and it never ran
    assert not S.is_due(p, datetime(2026, 10, 9, 6, 1), datetime(2026, 10, 9, 7, 0))
    assert S.is_due(p, datetime(2026, 10, 8, 6, 1), datetime(2026, 10, 9, 7, 0))
    assert not S.is_due({**p, "state": "proposed"}, None, datetime(2026, 10, 9, 7, 0))
    assert not S.is_due({**p, "schedule": {"freq": "on_arrival"}}, None, datetime(2026, 10, 9, 7, 0))
    weekly = {**p, "schedule": {"freq": "weekly", "at": "06:00", "day": "mon"}}  # 9 Oct 2026 is a Friday
    assert S.last_slot(weekly["schedule"], datetime(2026, 10, 9, 7, 0)) == datetime(2026, 10, 5, 6, 0)
    assert S.last_slot({"freq": "monthly", "at": "06:00", "day": 15}, datetime(2026, 10, 9, 7, 0)) == datetime(2026, 9, 15, 6, 0)
    first = S.tick(plane, datetime(2026, 10, 9, 7, 0))
    assert len(first) == 1 and first[0]["by"] == "scheduler" and total(plane) == 60
    assert S.tick(plane, datetime(2026, 10, 9, 7, 5)) == []


def test_on_arrival(plane):
    plan(plane, schedule={"freq": "on_arrival", "at": "06:00", "day": None})
    assert S.on_arrival(plane, "other_source") == []
    out = S.on_arrival(plane, "admin_export")
    assert len(out) == 1 and out[0]["by"] == "file arrival" and out[0]["status"] == "ok"


def test_airflow_one_task_per_table(plane):
    p = plan(plane, schedule={"freq": "weekly", "at": "06:30", "day": "mon"})
    text = S.airflow_dag(plane, PID)
    tree = ast.parse(text)
    assert text.count("PythonOperator(task_id=") == len(p["tables"])
    assert "bronze_t_raw >> gold_t_total" in text and "'30 6 * * 1'" in text and "create or replace table gold_t_total" in text
    assert tree
    f = S.export_airflow(plane, PID)
    assert f.endswith(".py") and plane.path("airflow").exists()


def test_cards_for_owner_and_c3_for_dashboards(plane, monkeypatch):
    wh.connect(plane).close()
    org = org_id(plane)
    with wh.connect(plane) as con:
        con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, business_role, is_active, created_at) "
                    "values (?,?,?,?,?,?,true,?)", [MAKER, org, "acc-maker", "acc-maker", "acc-maker@x.test", "Data", wh.now()])
    d = plane.path("consume", PID, "dashboards")
    d.mkdir(parents=True, exist_ok=True)
    (d / "d1.json").write_text(json.dumps({"id": "d1", "audience": ["acc-cio"], "tiles": [{"sql": "select total from gold_t_total"}, {"sql": "select 1"}]}), encoding="utf-8")
    calls = []
    from sh_platform.v1 import cx_share
    monkeypatch.setattr(cx_share, "notify", lambda *a, **k: calls.append((a[1:4], k)) or {"made": ["x"]})
    plan(plane)
    rec = R.run(plane, PID, "live")
    assert calls == [((PID, "d1", "refreshed"), {"token": rec["run_id"], "tiles_changed": 1})]  # C3 writes the card; B4 no longer does
    plan(plane, version=2, state="live", gold=BAD)
    R.run(plane, PID, "live")
    with wh.connect(plane) as con:
        rows = [(str(u), h) for u, h in con.execute("select recipient_user_id, headline from pulse_items").fetchall()]
    assert len(calls) == 1 and [u for u, _ in rows] == [MAKER] and rows[0][1].startswith("Pipeline failed")


def test_live_and_schedule_skip_a_proposed_version(plane):
    plan(plane, state="live")
    plan(plane, version=2, state="proposed")
    assert R.latest_plan(plane, PID)["version"] == 2 and R.latest_plan(plane, PID, live=True)["version"] == 1
    assert R.run(plane, PID, "live")["plan_version"] == 1
    due = S.tick(plane, datetime(2099, 1, 1, 12, 0))  # a later day: the daily slot is due again, and v2 (proposed) must not silence it
    assert [r["plan_version"] for r in due] == [1]


def test_state_moves_are_logged_and_the_project_stage_follows(plane):
    plan(plane)  # approved
    R.run(plane, PID, "sandbox", by="Leo")
    R.run(plane, PID, "live", by="Anita")
    from sh_platform.v1 import b6_plan as B
    words = [e["what"] for e in B.read_log(plane, PID)]
    assert "plan is now built" in words and "plan is now live" in words


def test_a_silver_step_fed_only_by_bronze_is_left_to_the_file_load(plane):
    """UC5: the approved sheet mapping writes silver rows when a file loads; the run must not insert them again from bronze."""
    p = plan(plane)
    p["tables"].append({"name": "portfolios", "layer": "silver", "sql": "insert into portfolios (id) select 1 from bronze_t_file", "depends_on": ["bronze_t_file"],
                        "columns": []})
    plane.path("build", PID, "plan-v1.json").write_text(json.dumps(p), encoding="utf-8")
    rec = R.run(plane, PID, "live")
    steps = {s["table"]: s for s in rec["steps"]}
    assert rec["status"] == "ok" and steps["portfolios"]["status"] == "filled by file loads"
