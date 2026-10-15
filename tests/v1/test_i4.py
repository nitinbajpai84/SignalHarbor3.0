"""Card I4: the decision maker settles the last unclear point, signs once, and the SOW is frozen, the KPI definitions are company
terms, the catalogue rows sit in a signed module 2 baseline, the room has a hand-over to Span; the analyst may not sign."""
import secrets
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.jsonfile import read_json_strict, write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings
from tests.v1.team import on_team
from sh_platform.v1 import i4_sow

ROOT = Path(__file__).resolve().parents[2]
IID = "i4test01"

SOW = {
    "id": "sow-i4test01", "intent_id": IID, "title": "Monthly performance pack", "state": "draft", "version": 1,
    "goal": {"line": "See net returns per client each month", "why": "The board asks", "readers": ["Board"], "decisions": ["Rebalance"], "needed_by": "2026-11-30"},
    "process": {"steps": [{"n": 1, "name": "Month end", "who": "Operations", "does": "Collects statements", "inputs": ["Custodian file"], "outputs": ["Positions"], "system": "Custodian portal"}],
                "handovers": []},
    "kpis": [{"code": "TWR", "name": "Time-weighted return (test)", "definition": "Return that removes the effect of client flows", "formula": "product(1+r) - 1",
              "unit": "%", "period": "month", "owner": "Priya Nair", "source_ids": ["S1"], "status": "defined", "pack_suggested": False}],
    "sources": [{"id": "S1", "name": "Custodian positions", "kind": "file", "holds": "Monthly positions", "sample_path": "landing/custodian/positions.csv",
                 "owner": "Operations", "fields": [{"name": "market_value", "type": "decimal", "example": "1000", "meaning": "Value at month end"}]}],
    "catalogue": [{"table": "positions", "layer": "landing", "meaning": "One holding per month", "source_id": "S1",
                   "fields": [{"name": "market_value", "type": "decimal", "meaning": "Value at month end", "source_field": "market_value"}], "feeds_kpis": ["TWR"]},
                  {"table": "returns_monthly", "layer": "gold", "meaning": "One return per client per month", "source_id": None, "fields": [], "feeds_kpis": ["TWR"]}],
    "governance": [{"rule": "Only the family may see client returns", "kind": "access", "applies_to": ["returns_monthly"], "stated_by": "Priya Nair"}],
    "unclear": [{"id": "u1", "question": "Are fees taken monthly or quarterly?", "about": "TWR", "who_can_settle": "Priya Nair", "settled": False, "answer": None}],
    "signature": None,
}


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("i4") / "data"
    shutil.copytree(ROOT / "data" / "_control", data / "_control")
    (data / "neera").mkdir()
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    from sh_platform.auth.accounts import AccountStore
    pw = {}
    for who in ("arjun.mehta", "leela.raman"):  # a test password in the tmp copy only: never reads the shared credentials file
        email = f"{who}.neera@example.test"
        pw[email] = secrets.token_urlsafe(16)
        AccountStore(data).set_password(email, pw[email])
    yield app, data, pw
    mp.undo()


def client(world, who):
    app, _, pw = world
    c = TestClient(app)
    email = f"{who}.neera@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_sign_writes_glossary_catalogue_and_room(world):
    arjun, leela = client(world, "arjun.mehta"), client(world, "leela.raman")
    me = arjun.get("/api/auth/me").json()
    plane = PlaneStore(world[1]).plane_for(me.get("company_id") or me["company"]["id"]).ensure()
    write_json_atomic(plane.path("intents", IID, "sow.json"), SOW)
    on_team(world[0], IID, "Leela Raman")  # G1: Internal is the team's alone
    url = f"/api/v1/intents/{IID}/sow"

    got = leela.get(url).json()
    assert got["title"] == SOW["title"] and got["may"]["sign"] is False and not got["sign_block"]  # the analyst reads; nothing blocks the decision maker
    assert arjun.get(url).json()["may"]["sign"] is True  # an open unclear point does not block: it travels to the architect
    assert leela.post(url + "/sign", json={"confirm": True, "version": 1}).status_code == 403  # the analyst is not the decision maker

    r = arjun.put(url, json={"section": "unclear", "index": 0, "field": "answer", "value": "Quarterly", "version": 1})
    assert r.status_code == 200 and r.json()["unclear"][0]["settled"] is True and r.json()["may"]["sign"] is True
    assert arjun.post(url + "/sign", json={"version": 1}).status_code == 422  # no confirm sentence answered

    write_json_atomic(plane.path("intents", IID, "thread.json"), {"state": "sow_ready", "turns": [  # V6 (design B3): "Before this" comes from the thread's own turns
        {"by": "person", "name": "Leela Raman", "at": "2026-10-11T10:28:00+00:00"}, {"by": "north", "name": "North", "at": "2026-10-11T10:42:00+00:00"}]})
    assert arjun.get(url).json()["before"] == {"by": "Leela Raman", "at": "2026-10-11T10:42:00+00:00", "minutes": 14}
    r = arjun.post(url + "/sign", json={"confirm": True, "version": 1, "note": "Good. Please show the SGD view as well."})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["signature"]["note"] == "Good. Please show the SGD view as well."   # the signer's note travels with the signature
    assert body["state"] == "signed" and body["signature"]["name"] and body["written"]["catalogue"]["tables"] >= 2  # the company's landing folders add theirs
    assert arjun.put(url, json={"section": "title", "value": "Changed", "version": 1}).status_code == 409  # frozen

    terms = read_json_strict(plane.path("glossary", "company-terms.json"), dict)["terms"]
    assert any(t["term"] == "Time-weighted return (test)" and t["state"] == "confirmed" for t in terms)
    bid = i4_sow.baseline_id_of(IID)
    from modules.m2_baseline.store import baseline as B
    assert B.read_baseline(plane, bid)["state"] == "signed"
    cat = read_json_strict(B.root(plane) / bid / "catalogue.json", dict)
    assert len(cat["sources"]) >= 2 and len(cat["tables"]) >= 2 and len(cat["fields"]) >= 1  # the landing folders add theirs
    assert not plane.path("intents", IID, "room.json").exists()  # no rooms: nothing is written

    # C2 reopens the record at version 2; the next signature adds only the new source and keeps the first signature
    again = read_json_strict(plane.path("intents", IID, "sow.json"), dict)
    again.update(state="draft", version=2, signature=None)
    again["sources"].append({"id": "S2", "name": "Market data feed", "kind": "system", "holds": "Benchmark prices", "sample_path": None, "owner": "Operations", "fields": []})
    write_json_atomic(plane.path("intents", IID, "sow.json"), again)
    r = arjun.post(url + "/sign", json={"confirm": True, "version": 2})
    assert r.status_code == 200 and r.json()["written"]["catalogue"] == {"baseline_id": bid, "sources": 1, "tables": 0, "fields": 0}
    assert [s["version"] for s in r.json()["signatures"]] == [1, 2]
    assert B.read_baseline(plane, bid)["state"] == "signed"

    md = leela.get(url + "/download?format=md")
    assert md.status_code == 200 and "## 8. Signature" in md.text and "attachment" in md.headers["content-disposition"]
