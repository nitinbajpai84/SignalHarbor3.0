"""T1 wiring, through the routes: a chat on a pinned template asks that template's goals, the intent of work will not sign while a
must-fill field of the pinned template is empty, and a company's own skill text reaches the agent's system prompt."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.agents.protocols import ModelReply
from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings
from sh_platform.v1 import a1_chat
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
CREDS = SEED / "_control" / "seed_credentials.txt"
ARJUN = "arjun.mehta.neera@example.test"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("t1w") / "data"
    shutil.copytree(SEED, data)
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": ARJUN, "password": pw[ARJUN]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    yield app, c, PlaneStore(data).plane_for("neera")
    mp.undo()


class Stub:
    def __init__(self):
        self.seen = []

    def complete(self, module_id, messages, tools=None):
        self.seen.append(messages)
        return ModelReply(text=json.dumps({"reply": "Noted.", "sow_patch": {}, "process_steps": None, "covered": [], "ready": False}))


def test_a_chat_on_a_pinned_template_asks_its_goals_and_signing_needs_its_must_fill_fields(world):
    _, c, plane = world
    fields = [{"key": "budget", "label": "Budget", "required": True, "ask": "What is the budget for this?"},
              {"key": "owner", "label": "Owner", "required": True, "ask": "Who owns it day to day?"},
              {"key": "notes", "label": "Notes", "required": False, "ask": "Any notes?"}]
    t = c.post("/api/v1/templates", json={"kind": "intent_of_work", "name": "Wiring pack"}).json()
    assert c.put(f"/api/v1/templates/{t['id']}", json={"fields": fields}).status_code == 200
    assert c.post(f"/api/v1/templates/{t['id']}/adopt", json={"standard": True}).status_code == 200

    r = c.post("/api/v1/intents/chat", json={"text": "A monthly pack for the board"})   # no template named: the company's standard
    assert r.status_code == 200, r.text
    thread = r.json()
    iid = thread["id"]
    assert thread["turns"][-1]["text"].startswith("Who should be able to see this work")   # G1: asked second, whatever the template
    assert thread["needs_done"] == ["budget"]
    thread = c.post(f"/api/v1/intents/{iid}/chat", json={"text": "Only the people I name."}).json()
    assert thread["turns"][-1]["text"] == "Who owns it day to day?"        # budget was the first goal; the next required one is asked
    assert thread["needs_done"] == ["budget", "access"]
    assert c.get(f"/api/v1/intents/{iid}/template").json()["template"]["id"] == t["id"]

    s = c.post(f"/api/v1/intents/{iid}/sow/sign", json={"confirm": True})
    assert s.status_code == 409 and "Owner" in json.dumps(s.json()) and "Budget" not in json.dumps(s.json())

    sow_path = plane.path("intents", iid, "sow.json")
    sow = json.loads(sow_path.read_text())
    assert sow["template_fields"] == {"budget": "A monthly pack for the board", "access": "Only the people I name."}   # N1: the answer is kept as a value
    sow["template_fields"] = {}                                             # the goal stays ticked, but there is no value
    sow_path.write_text(json.dumps(sow))
    thread = c.post(f"/api/v1/intents/{iid}/chat", json={"text": "The ops lead owns it."}).json()
    assert thread["needs_done"] == ["budget", "access", "owner"]
    s = c.post(f"/api/v1/intents/{iid}/sow/sign", json={"confirm": True})
    assert s.status_code == 409 and "Budget" in json.dumps(s.json()) and "Owner" not in json.dumps(s.json())   # N1: a tick is not a value
    got = c.get(f"/api/v1/intents/{iid}/sow").json()
    assert got["may"]["sign"] is False and "Budget" in got["sign_block"]    # N3: the button follows the same check
    assert c.put(f"/api/v1/intents/{iid}/sow", json={"section": "template_fields", "field": "budget", "value": "40,000 a year"}).status_code == 200
    s = c.post(f"/api/v1/intents/{iid}/sow/sign", json={"confirm": True})
    assert "Still to fill in" not in json.dumps(s.json())                   # the template no longer stops it (the SOW's own checks may)


def test_a_template_that_cannot_be_read_blocks_signing(world, monkeypatch):
    _, c, plane = world
    from sh_platform.v1 import i4_sow, t1_templates as T1
    def boom(*a, **k):
        raise OSError("gone")
    monkeypatch.setattr(T1, "sign_block", boom)
    assert "template could not be read" in i4_sow.t1_block(plane, "any")    # N4: fails closed, with a sentence


def test_a_company_skill_reaches_the_agents_system_prompt_and_governance_rules_reach_span(world):
    app, c, plane = world
    assert c.put("/api/v1/admin/skills/north/playbook.md", json={"text": "# Our North\nAlways ask about the family council first."}).status_code == 200
    assert c.put("/api/v1/admin/skills/span/playbook.md", json={"text": "# Our Span\nName every table after the council."}).status_code == 200
    assert c.put("/api/v1/admin/governance", json={"rules": [{"rule": "No figure leaves without a signature", "owner": "Arjun"}]}).status_code == 200
    stub = Stub()
    app.state.build_model_factory = lambda p: stub
    try:
        assert c.post("/api/v1/intents/chat", json={"text": "A quarterly fee review"}).status_code == 200
    finally:
        del app.state.build_model_factory
    system = stub.seen[0][0]["content"]
    assert "Always ask about the family council first" in system
    assert "Name every table after the council" in a1_chat._skill(plane)
    assert a1_chat._rules(plane) == ["No figure leaves without a signature (owner: Arjun)"]
