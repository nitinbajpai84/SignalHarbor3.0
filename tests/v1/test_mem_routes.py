"""Agent memory over HTTP and through North: a stubbed North remembers a lasting preference ("I will remember: ..."), the next turn's model
context carries it as strings, the person lists, corrects and forgets it, nobody else (same company, another company) sees it, and the
company's items are read by all and written only by the administrator and analysts."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.egress.rows import json_findings
from sh_platform.settings import Settings
from tests.v1.test_i6a import READY, Stub

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
ARJUN, LEELA, DEV = "arjun.mehta.neera@example.test", "leela.raman.neera@example.test", "dev.sharma.neera@example.test"
OTHER_CO = "company_admin.harbor-mutual@example.test"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("mem") / "data"
    shutil.copytree(ROOT / "data", data)
    a = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    a.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    yield a
    mp.undo()


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_north_remembers_and_the_person_lists_corrects_and_forgets(app):
    c = client(app, ARJUN)
    stub = Stub({**READY, "ready": False, "reply": "Who reads the pack?", "sow_patch": {}, "process_steps": None, "covered": []})
    app.state.build_model_factory = lambda plane: stub
    try:
        t = c.post("/api/v1/intents/chat", json={"text": "Always keep answers short. Monthly performance pack net of fees"}).json()
        said = t["turns"][-1]["text"]
        assert "you like short answers" in said and ("I will remember" in said or "Noted for next time" in said)
        mine = c.get("/api/v1/memory/me").json()["items"]
        assert len(mine) == 1 and mine[0]["agent_name"] == "North" and mine[0]["kind"] == "preference" and mine[0]["source"]["said"].startswith("Always keep")
        c.post(f"/api/v1/intents/{t['id']}/chat", json={"text": "The committee reads it."})
    finally:
        del app.state.build_model_factory
    ctx = json.loads(stub.seen[-1][1]["content"])["context"]
    assert any("short answers" in m for m in ctx["memory"])  # North reads recall() into its prompt, as strings
    for messages in stub.seen:
        for m in messages:
            assert json_findings(m["content"]) == (None, []), m["content"][:300]

    assert client(app, DEV).get("/api/v1/memory/me").json()["items"] == []  # same company, another person
    assert client(app, OTHER_CO).get("/api/v1/memory/me").json()["items"] == []  # another company

    fixed = c.patch(f"/api/v1/memory/me/{mine[0]['id']}", json={"text": "I like detailed answers"})
    assert fixed.status_code == 200 and fixed.json()["text"] == "I like detailed answers"
    assert [i["text"] for i in c.get("/api/v1/memory/me").json()["items"]] == ["I like detailed answers"]
    assert c.patch(f"/api/v1/memory/me/{mine[0]['id']}", json={"text": "x"}).status_code == 404  # the old version is gone
    assert client(app, DEV).delete(f"/api/v1/memory/me/{fixed.json()['id']}").status_code == 404  # not another person's to forget
    assert c.delete(f"/api/v1/memory/me/{fixed.json()['id']}").status_code == 200
    assert c.get("/api/v1/memory/me").json()["items"] == []
    assert c.patch("/api/v1/memory/me/m-00000000", json={"text": "x"}).json()["error"] == "not_found"


def test_company_items_are_read_by_all_and_written_by_admin_and_analyst(app):
    admin, analyst, dev = client(app, ARJUN), client(app, LEELA), client(app, DEV)
    assert dev.post("/api/v1/memory/company", json={"text": "Not mine to write"}).status_code == 403
    a = admin.post("/api/v1/memory/company", json={"text": "Report in USD unless asked"})
    assert a.status_code == 200, a.text
    b = analyst.post("/api/v1/memory/company", json={"term": "AUM", "concept_id": "concept:aum"})
    assert b.status_code == 200
    seen = dev.get("/api/v1/memory/company").json()
    assert {i["id"] for i in seen["items"]} == {a.json()["id"], b.json()["id"]} and seen["may_edit"] is False
    assert dev.delete(f"/api/v1/memory/company/{a.json()['id']}").status_code == 403
    assert client(app, OTHER_CO).get("/api/v1/memory/company").json()["items"] == []
    assert analyst.patch(f"/api/v1/memory/company/{a.json()['id']}", json={"text": "Report in SGD unless asked"}).status_code == 200
    assert admin.delete(f"/api/v1/memory/company/{b.json()['id']}").status_code == 200
    assert TestClient(app).get("/api/v1/memory/me").status_code in (401, 403)
