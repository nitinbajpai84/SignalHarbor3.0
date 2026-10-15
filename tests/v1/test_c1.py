"""C1 KPI cards on a tmp copy of the Neera warehouse: values only for loaded periods, the scan's reason otherwise, a figure opens to its
run and rows; a period not loaded and a signed-out caller are refused."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
IID = "int-c1test"


def _put(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data", data)
    neera = data / "neera"
    _put(neera / "intents" / IID / "sow.json", {
        "id": "sow-1", "intent_id": IID, "title": "Monthly portfolio pack", "state": "signed", "version": 1,
        "kpis": [{"code": "K01", "name": "Total return", "unit": "%", "period": "month", "owner": "Arjun Mehta", "source_ids": ["custodian_C1"], "status": "defined"},
                 {"code": "K02", "name": "Fee ratio", "unit": "%", "period": "month", "owner": "Arjun Mehta", "source_ids": ["bank_B01"], "status": "defined"}],
        "catalogue": [{"table": "gold.k01", "layer": "gold", "feeds_kpis": ["K01"]}],
        "signature": {"name": "Arjun Mehta", "role": "company_admin", "at": "2026-10-01T09:00:00Z"}})
    _put(neera / "build" / "scan" / f"{IID}.json", {"intent_id": IID, "kpis": [
        {"code": "K01", "status": "available", "sources_used": ["custodian_C1"], "missing": []},
        {"code": "K02", "status": "partly", "sources_used": [], "missing": [{"what": "fee schedule", "where_expected": "landing/fees"}]}], "agreed": None})
    _put(neera / "build" / "ops" / "loaded.json", {"periods": [
        {"period": p, "source_id": "custodian_C1", "state": "loaded", "reason": None, "by": "Leela Raman", "at": "2026-10-02T09:00:00Z"} for p in ("2026-07", "2026-08")]
        + [{"period": "2026-09", "source_id": "custodian_C1", "state": "not_loaded", "reason": "file late", "by": "Leela Raman", "at": "2026-10-02T09:00:00Z"}]})
    import duckdb  # 1.0 starts with an empty warehouse: the test builds the one mart its KPI reads
    con = duckdb.connect(str(neera / "warehouse" / "company.duckdb"))
    con.execute("create schema if not exists gold")
    con.execute("create or replace table gold.k01 as select * from (values ('2026-07', 1.2), ('2026-08', 1.5), ('2026-09', 0.9)) t(period, value)")
    con.close()
    from sh_platform.warehouse import refresh_readonly_copy
    from sh_platform.plane import PlaneStore
    refresh_readonly_copy(PlaneStore(data).plane_for("neera"))
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    email = "dev.sharma.neera@example.test"  # a participant: the Consumer seat
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    return c


def test_cards_show_loaded_periods_only_and_open_to_run_and_rows(client):
    body = client.get("/api/v1/consume").json()
    [intent] = [i for i in body["intents"] if i["intent_id"] == IID]
    k01, k02 = intent["kpis"]
    assert [t["period"] for t in k01["trend"]] == ["2026-07", "2026-08"] and k01["latest"]["period"] == "2026-08"
    assert k02["latest"] is None and "fee schedule" in k02["reason"]
    fig = client.get(f"/api/v1/consume/{IID}/K01", params={"period": "2026-08"}).json()
    assert fig["value"] == k01["latest"]["value"] and fig["rows"] and fig["table"] == "gold.k01"
    assert fig["runs"][0]["source_id"] == "custodian_C1" and fig["runs"][0]["run"]["started"] >= "2026-08"


def test_refuses_a_period_not_loaded_and_a_signed_out_caller(client):
    assert client.get(f"/api/v1/consume/{IID}/K01", params={"period": "2026-09"}).status_code == 404
    assert TestClient(client.app).get("/api/v1/consume").status_code in (401, 403)
