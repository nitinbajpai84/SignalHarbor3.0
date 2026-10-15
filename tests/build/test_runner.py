"""BC-5: contracts and the built-in runner. Synthetic CSV; planes written by path."""
import base64
import copy
import importlib.util
import json
import os
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from sh_platform import warehouse as wh
from sh_platform.app import create_app
from sh_platform.auth.permissions import Rule
from sh_platform.plane import PlaneStore
from sh_platform.settings import load_settings

ROOT = Path(__file__).resolve().parents[2]
FAMILY, MUTUAL = "lakeside-family-office", "harbor-mutual"
BP = {"version": 1, "state": "draft", "signed_by": [{"name": "Mei Tan", "role": "sponsor", "at": "2026-10-01T09:00:00+00:00"}],
      "model": {"facts": [{"name": "trades", "grain": "trade", "keys": ["id"], "measures": ["AUM"]}], "dimensions": []},
      "lineage": [{"measure": "AUM", "source": "trades", "fields": ["amount"], "transform": "sum of amount", "mart": "gold.aum.aum_total"},
                  {"measure": "SECRET", "source": "trades", "fields": ["amount"], "transform": "latest amount", "mart": "gold.secret_mart.latest_amount"},
                  {"measure": "RATIO", "source": "trades", "fields": ["amount"], "transform": "ratio of two things", "mart": "gold.ratio.r"}],
      "rules": [{"measure": "AUM", "rule": "amount is not empty", "severity": "block", "from": "scan"},
                {"measure": "AUM", "rule": "amount range 0 to 100", "severity": "block", "from": "scan"},
                {"measure": "AUM", "rule": "id is unique", "severity": "block", "from": "scan"}],
      "access": [{"mart": "gold.secret_mart", "may_see": ["Mei Tan"]}],
      "schedule": [{"source": "trades", "expected": "D+2 09:00", "sla": "WD8", "depends_on": []}]}
GOOD = "id,day,amount\n1,2026-09-01,10\n2,2026-09-02,20\n3,2026-09-03,30\n3,2026-09-03,30\n"
BAD = "id,day,amount\n1,2026-09-01,10\n2,2026-09-02,500\n"


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    root = tmp_path_factory.mktemp("bc5") / "data"
    spec = importlib.util.spec_from_file_location("bc5_seed", ROOT / "tools" / "seed.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    result = mod.seed(root)
    pw = {}
    for line in result["path"].read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            email, password = line.split()[:2]
            pw[email] = password
    return root, pw


@pytest.fixture
def env(seeded, tmp_path):
    root, pw = seeded
    shutil.copytree(root, tmp_path / "data")
    settings = load_settings({"SH_MODE": "dev", "SH_DATA_ROOT": str(tmp_path / "data"), "SH_SESSION_SECRET": "FAKE-bc5-secret-0123456789-abcdefghijkl"},
                             env_file=tmp_path / "none.env")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<!doctype html>", encoding="utf-8")
    app = create_app(settings, dist_dir=tmp_path / "dist")
    for k in ("POST /api/company/build/pipelines/{source}/upload", "POST /api/company/build/pipelines/run-due", "GET /api/company/build/schedule"):
        app.state.route_permissions.routes[k] = Rule(roles=frozenset({"company_admin", "analyst"}))  # until route_permissions.yaml carries them

    def login(role: str, company: str = FAMILY) -> TestClient:
        email = f"{role}.{company}@example.test"
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies["sh_csrf"]
        return c
    return login, PlaneStore(tmp_path / "data")


def land(plane, text: str) -> None:
    bp = plane.path("build", "blueprint.json")
    bp.parent.mkdir(parents=True, exist_ok=True)
    bp.write_text(json.dumps(BP), encoding="utf-8")
    f = plane.area("landing") / "trades_2026-09.csv"
    f.write_text(text, encoding="utf-8")
    t = datetime(2026, 9, 4, 8, 0).timestamp()  # before D+2 09:00 of the latest date in the file (3 Sep)
    os.utime(f, (t, t))


def test_contract_run_lands_bronze_silver_gold_and_logs(env):
    login, planes = env
    plane = planes.plane_for(FAMILY)
    land(plane, GOOD)
    c = login("company_admin")
    p = c.get("/api/company/build/pipelines").json()["pipelines"]
    assert p[0]["source"] == "trades" and p[0]["expected"] == "D+2 09:00" and p[0]["last_run"] is None
    assert "gold.secret_mart" in p[0]["marts"] and plane.path("build", "pipelines", "trades.json").exists()
    r = c.post("/api/company/build/pipelines/trades/run")
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "ok" and run["on_time"] and run["schema_ok"] and run["rows"] == 3 and run["marts_ready"]
    assert len(run["rules"]) == 3 and all(x["passed"] and x["count"] == 0 for x in run["rules"])
    assert any("RATIO" in n and "Not available yet" in n for n in run["notes"])
    assert wh.counts_only(plane, "bronze.trades")["rows"] == 4 and wh.counts_only(plane, "silver.trades")["rows"] == 3
    assert wh.counts_only(plane, "gold.aum") == {"rows": 1, "columns": 2}
    with pytest.raises(LookupError):  # the restricted mart is not in the company file
        wh.counts_only(plane, "gold.secret_mart")
    rc = duckdb.connect(str(plane.path("warehouse", "restricted.duckdb")), read_only=True)
    assert rc.execute("select count(*) from gold.secret_mart").fetchone()[0] == 1
    rc.close()
    assert c.get("/api/company/build/runs").json()["runs"][-1]["id"] == run["id"]
    assert json.loads(plane.path("warehouse", "runs.json").read_text())["runs"][-1]["source"] == "trades"
    assert c.get("/api/company/build/pipelines").json()["pipelines"][0]["last_run"]["id"] == run["id"]
    ro = wh.open_readonly(plane)
    assert ro.execute("select count(*) from silver.trades").fetchone()[0] == 3
    ro.close()


def test_failing_rule_shows_counts_and_status_failed(env):
    login, planes = env
    plane = planes.plane_for(FAMILY)
    land(plane, BAD)
    r = login("company_admin").post("/api/company/build/pipelines/trades/run")
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "failed" and run["marts_ready"] is None and run["sla_met"] is None
    assert {x["rule"].split(":")[1]: (x["passed"], x["count"]) for x in run["rules"]}["amount range 0 to 100"] == (False, 1)
    assert "500" not in json.dumps([run["rules"], run["notes"]])  # not the timestamps, which can hold those digits


def test_no_blueprint_contract_is_guessed_and_unknown_source_is_404(env):
    login, planes = env
    c = login("company_admin")
    assert c.post("/api/company/build/pipelines/trades/run").status_code == 404
    assert all(p["mark"] == "guessed" for p in c.get("/api/company/build/pipelines").json()["pipelines"])


def test_another_company_gets_403(env):
    login, planes = env
    c = login("company_admin", MUTUAL)
    shutil.rmtree(planes.root / MUTUAL)  # that company's space cannot be opened
    for r in (c.get("/api/company/build/pipelines"), c.get("/api/company/build/runs"), c.post("/api/company/build/pipelines/trades/run")):
        assert r.status_code == 403


def blueprint(plane, schedule: list[dict]) -> None:
    bp = copy.deepcopy(BP)
    bp["schedule"] = schedule
    plane.path("build", "blueprint.json").parent.mkdir(parents=True, exist_ok=True)
    plane.path("build", "blueprint.json").write_text(json.dumps(bp), encoding="utf-8")


def drop(c, source: str, name: str = "x.csv", text: str = GOOD):
    return c.post(f"/api/company/build/pipelines/{source}/upload", json={"filename": name, "data": base64.b64encode(text.encode()).decode()})


def test_upload_lands_a_file_the_runner_finds(env):
    login, planes = env
    plane = planes.plane_for(FAMILY)
    blueprint(plane, [{"source": "trades", "expected": "D+0 00:00", "sla": "WD8", "depends_on": []}])
    c = login("company_admin")
    assert drop(c, "trades", "notes.txt").status_code == 422
    r = drop(c, "trades")
    assert r.status_code == 200 and r.json()["file"] == "trades_x.csv" and r.json()["rows"] == 4  # the sender's name is kept inside the pattern
    assert (plane.area("landing") / r.json()["file"]).read_text() == GOOD
    assert c.post("/api/company/build/pipelines/trades/run").json()["rows"] == 3


def test_two_daily_files_uploaded_on_one_day_do_not_overwrite_each_other(env):
    login, planes = env
    plane = planes.plane_for(FAMILY)
    blueprint(plane, [{"source": "trades", "expected": "D+0 00:00", "sla": "WD8", "depends_on": []}])
    c = login("company_admin")
    other = GOOD + "T9,x,y,1\n"
    a, b = drop(c, "trades", "trades_2026-10-01.csv").json()["file"], drop(c, "trades", "trades_2026-10-02.csv", other).json()["file"]
    same = drop(c, "trades", "trades_2026-10-01.csv", other).json()["file"]  # same name, different bytes: kept apart
    assert len({a, b, same}) == 3 and (plane.area("landing") / a).read_text() == GOOD and (plane.area("landing") / same).read_text() == other
    assert drop(c, "trades", "trades_2026-10-01.csv").json()["file"] == a  # same name, same bytes: the same file


def test_run_refuses_until_its_dependency_has_run_ok_today(env):
    login, planes = env
    plane = planes.plane_for(FAMILY)
    blueprint(plane, [{"source": "trades", "expected": "D+0 00:00", "sla": "WD8", "depends_on": []},
                      {"source": "fx", "expected": "D+0 00:00", "sla": "WD8", "depends_on": ["trades"]}])
    c = login("company_admin")
    assert drop(c, "trades").status_code == 200 and drop(c, "fx").status_code == 200
    r = c.post("/api/company/build/pipelines/fx/run")
    assert r.status_code == 409 and "trades" in r.text
    assert c.post("/api/company/build/pipelines/trades/run").json()["status"] in ("ok", "late")
    assert c.post("/api/company/build/pipelines/fx/run").status_code == 200


def test_run_due_runs_in_dependency_order_and_records_late(env):
    login, planes = env
    plane = planes.plane_for(FAMILY)
    blueprint(plane, [{"source": s, "expected": "D+0 00:00", "sla": "WD8", "depends_on": d} for s, d in
                      (("fx", ["trades"]), ("ghost", []), ("trades", []))])
    c = login("company_admin")
    drop(c, "trades"), drop(c, "fx")
    r = c.post("/api/company/build/pipelines/run-due").json()
    assert [x["source"] for x in r["ran"]] == ["trades", "fx"]
    assert [x["source"] for x in r["skipped"]] == ["ghost"] and "No file has landed" in r["skipped"][0]["reason"]
    late = [x for x in c.get("/api/company/build/runs").json()["runs"] if x["source"] == "ghost"]
    assert len(late) == 1 and late[0]["status"] == "late" and late[0]["rows"] == 0
    again = c.post("/api/company/build/pipelines/run-due").json()
    assert again["ran"] == [] and len([x for x in c.get("/api/company/build/runs").json()["runs"] if x["source"] == "ghost"]) == 1
    states = {x["source"]: x["state"] for x in c.get("/api/company/build/schedule").json()["plan"]}
    assert states["ghost"] == "late" and states["trades"] in ("ok", "late") and states["fx"] in ("ok", "late", "failed")


def test_run_upserts_its_period_and_keeps_the_other_months(env):
    login, planes = env
    plane = planes.plane_for(FAMILY)
    land(plane, GOOD)
    con = wh.open_company(plane)
    con.execute("create schema if not exists gold")
    con.execute("create table gold.aum as select '2026-0' || i as period, i * 100.0 as value from range(1, 10) t(i)")
    con.close()
    assert login("company_admin").post("/api/company/build/pipelines/trades/run").status_code == 200
    con = wh.open_company(plane)
    got = dict(con.execute("select period, value from gold.aum").fetchall())
    assert len(got) == 9 and got["2026-01"] == 100.0 and got["2026-09"] == 60.0  # September replaced by the run's sum (10+20+30)
    con.close()
    con = wh.open_company(plane)  # a file with no date cannot give a period: the table is left alone
    from sh_platform.build import transforms
    assert transforms.build_mart(con, "trades", "aum", [("aum_total", "amount", "sum")], [("amount", "bigint")]) is False
    assert con.execute("select count(*) from gold.aum").fetchone()[0] == 9
    con.close()


def test_ensure_removes_contract_and_commit_files_of_sources_no_longer_derived(env):
    from sh_platform.build import contracts
    _, planes = env
    plane = planes.plane_for(FAMILY)
    land(plane, GOOD)
    contracts.ensure(plane)
    d = plane.path("build", "pipelines")
    (d / "old_source.json").write_text("{}", encoding="utf-8")
    (d / "old-source.commits.json").write_text("{}", encoding="utf-8")
    (d / "trades.commits.json").write_text("{}", encoding="utf-8")
    contracts.ensure(plane)
    assert sorted(f.name for f in d.glob("*.json")) == ["trades.commits.json", "trades.json"]


def test_set_aside_for_a_restricted_measure_is_masked_for_a_viewer_outside_its_list(env):
    login, planes = env
    plane = planes.plane_for(FAMILY)
    land(plane, GOOD)
    held = [{"rule": "SECRET:amount is not empty", "field": "amount", "count": 7}, {"rule": "AUM:amount is not empty", "field": "amount", "count": 2}]
    run = {"id": "r1", "source": "trades", "started": "2026-09-04T08:00:00+00:00", "rows": 9, "rules": [], "status": "failed", "quarantined": held,
           "rules": [{"rule": "SECRET:amount is not empty", "passed": False, "count": 7}, {"rule": "AUM:amount is not empty", "passed": True, "count": 0},
                     {"rule": "gold.secret_mart: left as it was", "passed": False, "count": 0}],
           "not_run": ["SECRET:id is unique"], "notes": ["SECRET: not yet", "RATIO: not yet"]}
    (plane.path("warehouse") / "runs.json").parent.mkdir(parents=True, exist_ok=True)
    (plane.path("warehouse") / "runs.json").write_text(json.dumps({"runs": [run]}), encoding="utf-8")
    c = login("analyst")
    c.get("/api/company/build/pipelines")  # makes the contract
    for q in (c.get("/api/company/build/runs").json()["runs"][0]["quarantined"],
              c.get("/api/company/build/pipelines").json()["pipelines"][0]["last_run"]["quarantined"]):
        assert q[0] == {"rule": "", "field": "", "count": 7, "masked": True} and q[1] == held[1]
    for r in (c.get("/api/company/build/runs").json()["runs"][0], c.get("/api/company/build/pipelines").json()["pipelines"][0]["last_run"]):
        assert [x["rule"] for x in r["rules"]] == ["a check you cannot see", "AUM:amount is not empty", "a check you cannot see"]
        assert r["not_run"] == ["a check you cannot see"] and r["notes"] == ["a check you cannot see", "RATIO: not yet"]
    bp = json.loads(plane.path("build", "blueprint.json").read_text(encoding="utf-8"))
    me = next(x["display_name"] for x in c.app.state.account_store.in_company(FAMILY) if "analyst" in x.get("roles", []))
    bp["access"][0]["may_see"] = [me]
    plane.path("build", "blueprint.json").write_text(json.dumps(bp), encoding="utf-8")
    r = c.get("/api/company/build/runs").json()["runs"][0]
    assert r["quarantined"][0] == held[0] and r["rules"][0]["rule"] == "SECRET:amount is not empty" and r["not_run"] == ["SECRET:id is unique"]
    assert login("company_admin").get("/api/company/build/runs").json()["runs"][0]["quarantined"] == held
