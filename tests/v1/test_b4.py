"""B4 Flow loads: the mapping sheet's rows run through the runner, one run per source, logged in runs.json with Flow's note; a failed check
and a missing file go to the room. A sponsor may read the runs but not start a load."""
import json
import shutil
import sys
import types
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.settings import Settings
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
PW = "b4-test-only-password"  # set on the tmp copy's accounts; the seeded passwords are never read
IID = "b4test"
ROWS = [  # the mapping sheet contract (docs/plan/V1-BUILD.md); a tiny synthetic fixture of this card's own
    {"n": 1, "layer": "silver", "target_table": "silver.positions", "target_field": "account_id", "source_id": "custody_positions",
     "source_table": "positions", "source_field": "account_id", "transformation": "as is", "rule": "", "test": "not empty", "status": "mapped"},
    {"n": 2, "layer": "silver", "target_table": "silver.positions", "target_field": "market_value", "source_id": "custody_positions",
     "source_table": "positions", "source_field": "market_value", "transformation": "as is", "rule": "", "test": "not empty", "status": "mapped"},
    {"n": 3, "layer": "gold", "target_table": "gold.b4_aum", "target_field": "aum", "source_id": "custody_positions",
     "source_table": "positions", "source_field": "market_value", "transformation": "sum per month", "rule": "", "test": "", "status": "mapped"},
    {"n": 4, "layer": "silver", "target_table": "silver.fees", "target_field": "fee", "source_id": "fee_schedule",
     "source_table": "fees", "source_field": "fee", "transformation": "as is", "rule": "", "test": "not empty", "status": "mapped"},
    {"n": 5, "layer": "silver", "target_table": "silver.x", "target_field": "y", "source_id": "custody_positions",
     "source_table": "positions", "source_field": "y", "transformation": "", "rule": "", "test": "", "status": "unclear"},
]


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(SEED, data)
    co = data / "neera"
    (co / "build" / "mapping").mkdir(parents=True, exist_ok=True)
    (co / "build" / "mapping" / f"{IID}.json").write_text(json.dumps({"intent_id": IID, "version": 1, "rows": ROWS}), encoding="utf-8")
    (co / "intents" / IID).mkdir(parents=True, exist_ok=True)
    (co / "intents" / IID / "sow.json").write_text(json.dumps({"sources": [
        {"id": "custody_positions", "name": "Custodian positions", "owner": "Leela Raman"}]}), encoding="utf-8")
    land = co / "landing" / "custody_positions"
    land.mkdir(parents=True, exist_ok=True)
    (land / "positions_2026-08.csv").write_text("account_id,as_of,market_value\nA1,2026-08-31,100\nA2,2026-08-31,200\n", encoding="utf-8")
    # September: market_value renamed mid-year, so the check on market_value fails for these rows
    (land / "positions_2026-09.csv").write_text("account_id,as_of,mv\nA1,2026-09-30,110\nA2,2026-09-30,210\n", encoding="utf-8")
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    for who in ("leela.raman", "priya.nair"):
        app.state.account_store.set_password(f"{who}.neera@example.test", PW)
    return app, co


def _client(world, who):
    c = TestClient(world[0])
    assert c.post("/api/auth/login", json={"email": f"{who}.neera@example.test", "password": PW}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_load_runs_each_source(world):
    _, co = world
    c = _client(world, "leela.raman")
    r = c.post(f"/api/v1/build/{IID}/load")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_left_out"] == 1
    assert [m["source"] for m in body["missing"]] == ["v1_fee_schedule"]  # no file landed for fees
    (run,) = body["runs"]
    assert run["source"] == "v1_custody_positions" and run["rows"] == 4 and run["status"] == "failed"
    rules = {x["rule"]: x for x in run["rules"]}
    assert rules["account_id:not empty"]["passed"] and not rules["market_value:not empty"]["passed"]
    assert rules["market_value:not empty"]["count"] == 2
    assert run["note"]["fallback"] and run["note"]["lines"] and "no contract" not in " ".join(run["note"]["lines"])
    logged = json.loads((co / "warehouse" / "runs.json").read_text(encoding="utf-8"))["runs"]
    assert logged[-1]["id"] == run["id"] and logged[-1]["status"] == "failed"
    con = duckdb.connect(str(co / "warehouse" / "company.duckdb"), read_only=True)
    try:
        assert con.execute("select count(*) from silver.v1_custody_positions").fetchone()[0] == 4
        assert dict(con.execute("select period, value from gold.b4_aum").fetchall())["2026-08"] == 300
    finally:
        con.close()
    got = c.get(f"/api/v1/build/{IID}/runs").json()
    assert got["runs"][0]["id"] == run["id"] and got["runs"][0]["note"]["run_id"] == run["id"]
    assert {x["source"] for x in got["contracts"]} == {"v1_custody_positions", "v1_fee_schedule"}


def test_sponsor_reads_but_cannot_load(world):
    c = _client(world, "priya.nair")
    assert c.post(f"/api/v1/build/{IID}/load").status_code == 403
    assert c.get(f"/api/v1/build/{IID}/runs").status_code == 200
    assert _client(world, "leela.raman").get("/api/v1/build/nosheet/runs").status_code == 404
