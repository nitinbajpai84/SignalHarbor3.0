"""B1: Span drafts the three layers from a signed SOW into the blueprint and the architecture record; the model is off, so the
labelled rule-based lines stand. Refusals: a participant may not ask, and a draft SOW is not designed from."""
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
IID = "b1-fixture"
SOW = {
    "id": "sow-b1", "intent_id": IID, "title": "Monthly performance pack", "state": "signed", "version": 1,
    "goal": {"line": "See net returns monthly", "why": "Board pack", "readers": [], "decisions": [], "needed_by": "2026-11"},
    "process": {"steps": [], "handovers": []},
    "kpis": [{"code": "TWR", "name": "Time-weighted return", "definition": "Return net of flows", "formula": "chain-linked monthly returns",
              "unit": "%", "period": "month", "owner": "Arjun Mehta", "source_ids": ["custodian"], "status": "defined", "pack_suggested": False},
             {"code": "FEE", "name": "Fee ratio", "definition": "Fees over average assets", "formula": "fees / avg assets", "unit": "%",
              "period": "month", "owner": "Arjun Mehta", "source_ids": ["ledger"], "status": "unclear", "pack_suggested": True}],
    "sources": [{"id": "custodian", "name": "Custodian positions", "kind": "file", "holds": "Monthly positions", "sample_path": "landing/custodian/p.csv",
                 "owner": "Leela Raman", "fields": []},
                {"id": "ledger", "name": "General ledger", "kind": "file", "holds": "Trial balance", "sample_path": None, "owner": None, "fields": []}],
    "catalogue": [{"table": "custodian_positions", "layer": "landing", "meaning": "Positions as sent", "source_id": "custodian",
                   "fields": [{"name": "market_value", "type": "number", "meaning": "Value", "source_field": "MV"}], "feeds_kpis": []},
                  {"table": "positions", "layer": "silver", "meaning": "Positions typed", "source_id": "custodian",
                   "fields": [{"name": "market_value", "type": "number", "meaning": "Value", "source_field": "market_value"}], "feeds_kpis": ["TWR"]}],
    "governance": [], "unclear": [], "signature": {"name": "Arjun Mehta", "role": "company_admin", "at": "2026-10-07T10:00:00+00:00"},
}


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("b1") / "data"
    shutil.copytree(ROOT / "data", data)
    from tools.reset_v1 import reset as _reset_v1  # the live Neera may hold a walk's records; the test starts from the company's files
    from sh_platform.plane import PlaneStore as _PS
    _reset_v1(_PS(data).plane_for("neera"))
    for iid, state in ((IID, "signed"), ("b1-draft", "draft")):
        (data / "neera" / "intents" / iid).mkdir(parents=True, exist_ok=True)
        (data / "neera" / "intents" / iid / "sow.json").write_text(json.dumps({**SOW, "intent_id": iid, "state": state}), encoding="utf-8")
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    yield app, data, pw.get  # a bound method, so a failing assertion never prints the passwords
    mp.undo()


def _client(world, email):
    app, _, pw = world
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw(email)}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies["sh_csrf"]
    return c


def test_span_drafts_from_signed_sow(world):
    c = _client(world, "leela.raman.neera@example.test")
    r = c.post(f"/api/v1/build/{IID}/design")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["fallback"] is True and d["message"] and d["lines"]
    assert d["counts"] == {"source": 2, "bronze": 1, "silver": 1, "gold": 2}
    plane = world[1] / "neera" / "build"
    bp = json.loads((plane / "blueprint.json").read_text(encoding="utf-8"))
    assert {ln["measure"] for ln in bp["lineage"]} == {"TWR", "FEE"} and bp["state"] == "draft"
    rec = json.loads((plane / "architecture" / "record.json").read_text(encoding="utf-8"))
    comps = {x["id"]: x for x in rec["components"]}
    assert comps["silver:positions"]["interfaces"][0]["to"] == "gold:twr" and comps["silver:positions"]["state"] == "proposed"
    assert {"to": "bronze:custodian_positions", "kind": "feeds", "contract": None} in comps["source:custodian"]["interfaces"]
    a = c.get("/api/company/build/architecture?view=data").json()
    assert a["version"] == rec["version"] and a["diagram"]["components"]
    assert c.get(f"/api/v1/build/{IID}/design").json()["design"]["record_version"] == rec["version"]


def test_refusals(world):
    assert _client(world, "dev.sharma.neera@example.test").post(f"/api/v1/build/{IID}/design").status_code == 403
    r = _client(world, "arjun.mehta.neera@example.test").post("/api/v1/build/b1-draft/design")
    assert r.status_code == 409 and r.json()["error"] == "sow_not_signed"
