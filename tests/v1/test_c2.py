"""C2 Offer card: offers come from the pack's feed list minus what the SOW already holds; "We have it" adds a source and an
unclear line (draft, version + 1) and posts to the room; an analyst may read but not answer."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
IID = "int_c2test"
SOW = {"id": "sow_c2test", "intent_id": IID, "title": "Monthly performance pack", "state": "signed", "version": 2,
       "kpis": [{"code": "K02", "name": "Reported-value evidence coverage", "status": "defined"}],
       "sources": [{"id": "custodian_positions", "name": "Custodian positions", "kind": "file", "holds": "monthly positions", "fields": []},
                   {"id": "bank_cash", "name": "Bank cash", "kind": "file", "holds": "daily cash balances", "fields": []}],
       "catalogue": [], "governance": [], "unclear": [], "signature": {"name": "Arjun Mehta", "role": "company_admin", "at": "2026-10-07"}}


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("c2") / "data"
    shutil.copytree(ROOT / "data", data)
    a = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    plane = PlaneStore(str(data)).plane_for("neera")
    plane.path("intents", IID).mkdir(parents=True, exist_ok=True)
    plane.path("intents", IID, "sow.json").write_text(json.dumps(SOW), encoding="utf-8")
    a.state.c2_plane = plane
    yield a
    mp.undo()


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_offer_then_we_have_it(app):
    c = client(app, "arjun.mehta.neera@example.test")
    doc = c.get("/api/v1/consume/offers").json()
    assert doc["intent_id"] == IID and doc["can_answer"]
    ids = [o["id"] for o in doc["offers"]]
    assert "fx_rates" in ids and "positions" not in ids and "cash_balances" not in ids  # the SOW already holds those two
    fx = next(o for o in doc["offers"] if o["id"] == "fx_rates")
    assert fx["kind"] == "FX rates" and {"code": "K02", "name": "Reported-value evidence coverage", "in_sow": True} in fx["unlocks"]
    assert {f["name"] for f in fx["must_contain"]} >= {"currency", "sgd_per_unit"}

    r = c.post("/api/v1/consume/offers/fx_rates/have", json={"intent_id": IID})
    assert r.status_code == 200, r.text
    sow = r.json()["sow"]
    assert sow["state"] == "draft" and sow["version"] == 3 and sow["signature"] is None
    assert sow["sources"][-1]["id"] == "src_fx_rates" and sow["unclear"][-1]["about"] == "src_fx_rates"
    assert "fx_rates" not in [o["id"] for o in c.get("/api/v1/consume/offers").json()["offers"]]
    assert c.post("/api/v1/consume/offers/fx_rates/have", json={}).status_code == 409
    assert not app.state.c2_plane.path("intents", IID, "room.json").exists()  # no rooms: nothing is written


def test_analyst_reads_but_may_not_answer(app):
    c = client(app, "leela.raman.neera@example.test")
    assert c.get("/api/v1/consume/offers").json()["can_answer"] is False
    assert c.post("/api/v1/consume/offers/commitments/have", json={}).status_code == 403


def test_fresh_company_does_not_break(app):
    doc = client(app, "nitin.fresh@example.test").get("/api/v1/consume/offers").json()
    assert doc["offers"] == [] and doc["line"]
