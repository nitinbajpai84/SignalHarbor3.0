"""B2 scan and agree: available / partly / not from landing headers, agree a scope, and the refusals."""
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.jsonfile import read_json_strict, write_json_atomic
from sh_platform.settings import Settings
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
ACCOUNTS = SEED / "_control" / "accounts.json"
pytestmark = pytest.mark.skipif(not ACCOUNTS.is_file(), reason="no seeded demo data")
PW = "b2-test-only-password"  # set on the tmp copy, never the real control plane
PEOPLE = ("arjun.mehta.neera@example.test", "leela.raman.neera@example.test")
IID = "int-b2"

SOW = {"id": "sow-b2", "intent_id": IID, "title": "Portfolio returns", "state": "signed", "version": 1,
       "kpis": [{"code": "TWR", "name": "Time-weighted return", "source_ids": ["custodian"]},
                {"code": "FEE", "name": "Fee ratio", "source_ids": ["custodian", "fees"]},
                {"code": "BMK", "name": "Benchmark relative", "source_ids": ["benchmark"]}],
       "sources": [{"id": "custodian", "name": "Custodian positions", "kind": "file", "fields": []},
                   {"id": "fees", "name": "Fee schedule", "kind": "file", "fields": []},
                   {"id": "benchmark", "name": "Benchmark prices", "kind": "file", "fields": []}],
       "catalogue": [
           {"table": "positions", "layer": "landing", "source_id": "custodian", "feeds_kpis": ["TWR", "FEE"],
            "fields": [{"name": "market_value", "source_field": "Market Value"}, {"name": "as_of", "source_field": "as_of"}]},
           {"table": "fees", "layer": "landing", "source_id": "fees", "feeds_kpis": ["FEE"],
            "fields": [{"name": "fee_bps", "source_field": "fee_bps"}]},
           {"table": "benchmark", "layer": "landing", "source_id": "benchmark", "feeds_kpis": ["BMK"],
            "fields": [{"name": "index_level", "source_field": "index_level"}]}],
       "unclear": [], "governance": [], "signature": {"name": "Arjun Mehta", "role": "company_admin", "at": "2026-10-07"}}


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(SEED / "_control", data / "_control")
    for c in ("neera", "fresh"):
        (data / c).mkdir()
    neera = data / "neera"
    write_json_atomic(neera / "intents" / IID / "sow.json", SOW)
    (neera / "landing" / "custodian").mkdir(parents=True)
    (neera / "landing" / "custodian" / "positions_2026-09.csv").write_text("as_of,Market Value\n2026-09-30,100\n", encoding="utf-8")
    from openpyxl import Workbook
    wb = Workbook()
    wb.active.title = "schedule"
    wb.active.append(["client", "fee_bps"]); wb.active.append(["c1", 50])
    wb.create_sheet("notes").append(["note"])
    (neera / "landing" / "fees").mkdir()
    wb.save(neera / "landing" / "fees" / "fees.xlsx")
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    for email in PEOPLE:
        app.state.account_store.set_password(email, PW)
    return app, neera


def _client(world, email):
    c = TestClient(world[0])
    assert c.post("/api/auth/login", json={"email": email, "password": PW}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_scan_then_agree(world):
    arjun = _client(world, "arjun.mehta.neera@example.test")
    r = arjun.post(f"/api/v1/build/{IID}/scan")
    assert r.status_code == 200, r.text
    st = {k["code"]: k for k in r.json()["scan"]["kpis"]}
    assert st["TWR"]["status"] == "available" and st["TWR"]["sources_used"] == ["custodian"]
    assert st["FEE"]["status"] == "available"
    assert st["BMK"]["status"] == "not" and "index_level" in st["BMK"]["missing"][0]["what"]
    a = arjun.post(f"/api/v1/build/{IID}/scan/agree", json={"scope": ["TWR", "FEE"]})
    assert a.status_code == 200, a.text
    rec = read_json_strict(world[1] / "build" / "scan" / f"{IID}.json")
    assert rec["agreed"]["scope"] == ["TWR", "FEE"] and rec["agreed"]["by"]


def test_partly_and_refusals(world):
    (world[1] / "landing" / "fees" / "fees.xlsx").unlink()
    arjun = _client(world, "arjun.mehta.neera@example.test")
    st = {k["code"]: k["status"] for k in arjun.post(f"/api/v1/build/{IID}/scan").json()["scan"]["kpis"]}
    assert st["FEE"] == "partly"
    assert arjun.post(f"/api/v1/build/{IID}/scan/agree", json={"scope": ["BMK"]}).status_code == 422
    leela = _client(world, "leela.raman.neera@example.test")  # analyst: may scan, may not agree
    assert leela.post(f"/api/v1/build/{IID}/scan/agree", json={"scope": ["TWR"]}).status_code == 403
    sow = dict(SOW, state="draft")
    write_json_atomic(world[1] / "intents" / IID / "sow.json", sow)
    assert leela.post(f"/api/v1/build/{IID}/scan").status_code == 409
