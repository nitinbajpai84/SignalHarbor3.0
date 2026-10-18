"""I6a North's conversation: a stubbed model drafts the SOW and the process map and says ready (the context passes the egress
row and size checks); a person's edit on the SOW page survives North's next patch; an intent started through I2 gets North's own
first reply; the model off asks the next goal, labelled; an analyst may read but not talk."""
import base64
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.agents.protocols import ModelReply
from sh_platform.app import create_app
from sh_platform.egress.rows import json_findings
from sh_platform.settings import Settings
from tests.v1.team import on_team
from sh_platform.v1.i6_chat import CLOSING
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
CREDS = SEED / "_control" / "seed_credentials.txt"
ARJUN, LEELA = "arjun.mehta.neera@example.test", "leela.raman.neera@example.test"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("i6a") / "data"
    shutil.copytree(SEED, data)
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


class Stub:
    def __init__(self, answer: dict):
        self.answer, self.seen = answer, []

    def complete(self, module_id, messages, tools=None):
        self.seen.append(messages)
        return ModelReply(text=json.dumps(self.answer))


READY = {
    "reply": CLOSING,
    "sow_patch": {
        "goal": {"why": "The committee needs returns after fees", "readers": ["the committee"]},
        "sources": [{"name": "Custodian statement", "kind": "system", "holds": "Monthly positions", "owner": "Leela Raman"}],
        "kpis": [{"name": "Time-weighted return", "definition": "Growth of the portfolio net of fees", "period": "monthly",
                  "sources": ["Custodian statement"]},
                 {"name": "Cash drag", "definition": "Return lost to idle cash", "pack_suggested": True}],
        "governance": [{"rule": "Only the committee sees client figures", "kind": "access", "applies_to": ["client figures"]}],
        "unclear": [{"question": "Who owns the benchmark choice?", "about": "benchmark", "who_can_settle": "Priya Nair"}],
    },
    "process_steps": [{"name": "Pull the custodian file", "who": "Leela Raman", "does": "Downloads positions", "system": "Custodian portal"},
                      {"name": "Check and sign the pack", "who": "Arjun Mehta", "does": "Reviews the figures"}],
    "covered": ["goal", "readers", "frequency", "process", "result", "kpis", "inputs", "strategic", "documents", "manual", "rules", "disputes", "success", "unclear", "nonsense"],
    "ready": True,
}


def test_model_drafts_sow_and_map_and_hands_over(app):
    c = client(app, ARJUN)
    stub = Stub(READY)
    app.state.build_model_factory = lambda plane: stub
    try:
        csv = b"date,account,value\n2026-09-30,A1,100\n"
        r = c.post("/api/v1/intents/chat", json={"text": "Monthly performance pack net of fees",
                                                  "files": [{"name": "i6_positions.csv", "data": base64.b64encode(csv).decode()}]})
        assert r.status_code == 200, r.text
        t0 = r.json()
        iid = t0["id"]
        assert c.get("/api/v1/intents/open").json()["id"] == iid
        # L2: North's patch waits for a yes; the SOW is untouched and the turn is not ready
        assert {p["document"] for p in t0["proposals"]["pending"]} == {"sow", "process_map"} and t0["state"] != "sow_ready"
        assert not t0["sow"]["kpis"] and not t0["process_map"]["steps"]
        for p in t0["proposals"]["pending"]:
            assert c.post(f"/api/v1/intents/{iid}/proposals/{p['id']}/accept").status_code == 200
        # the person edits a line on the SOW page; North's next patch must not overwrite it
        e = c.put(f"/api/v1/intents/{iid}/sow", json={"section": "goal", "field": "why", "value": "My own words"})
        assert e.status_code == 200, e.text
        stub.answer = {**READY, "sow_patch": {"goal": {"why": "North's rewording", "needed_by": "end of November"}}, "process_steps": None}
        t2 = c.post(f"/api/v1/intents/{iid}/chat", json={"text": "Needed by the end of November."}).json()
        for p in t2["proposals"]["pending"]:
            assert c.post(f"/api/v1/intents/{iid}/proposals/{p['id']}/accept").status_code == 200
        stub.answer = READY
        t = c.post(f"/api/v1/intents/{iid}/chat", json={"text": "That is all."}).json()  # nothing left to propose: North closes
    finally:
        del app.state.build_model_factory
    north = t["turns"][-1]
    assert north["by"] == "north" and north["name"] == "North" and north["text"].startswith("Here is what we are building")  # the product composes the closing summary
    assert t["turns"][0]["files"][0]["kind"] == "sample"
    assert t["state"] == "sow_ready" and "nonsense" not in t["needs_done"] and len(t["needs_done"]) == 14
    sow = t["sow"]
    assert sow["goal"]["line"] == "Monthly performance pack net of fees"
    tw = next(k for k in sow["kpis"] if k["name"] == "Time-weighted return")
    src = next(s for s in sow["sources"] if s["name"] == "Custodian statement")
    assert tw["status"] == "defined" and tw["source_ids"] == [src["id"]] and tw["code"].startswith("K")
    cd = next(k for k in sow["kpis"] if k["name"] == "Cash drag")
    assert cd["pack_suggested"] and cd["status"] == "unclear"
    assert [(s["n"], s["who"]) for s in t["process_map"]["steps"]] == [(1, "Leela Raman"), (2, "Arjun Mehta")]
    assert sow["governance"][0]["stated_by"] == "Arjun Mehta"
    assert any(u["question"] == "Who owns the benchmark choice?" and u["who_can_settle"] == "Priya Nair" for u in sow["unclear"])
    for messages in stub.seen:  # what went to the model passes the gateway's row and size checks
        for m in messages:
            assert json_findings(m["content"]) == (None, []), m["content"][:300]
    ctx = json.loads(stub.seen[0][1]["content"])["context"]
    assert ctx["files_now"] and "i6_positions" in json.dumps(ctx)

    assert t["sow"]["goal"]["why"] == "My own words" and t["sow"]["goal"]["needed_by"] == "end of November"


def test_intent_started_through_i2_gets_norths_own_first_reply(app):
    c = client(app, ARJUN)
    iid = c.post("/api/v1/intents", json={"line": "Fee ratio by client"}).json()["id"]
    stub = Stub({"reply": "Who reads the fee ratio, and what decision does it support?",
                 "sow_patch": {"goal": {"why": "Fees look high"}}, "process_steps": None, "covered": ["goal"], "ready": False})
    app.state.build_model_factory = lambda plane: stub
    try:
        t = c.get(f"/api/v1/intents/{iid}/chat").json()
        again = c.get(f"/api/v1/intents/{iid}/chat").json()
    finally:
        del app.state.build_model_factory
    assert [(x["by"], x["name"]) for x in t["turns"]] == [("person", "Arjun Mehta"), ("north", "North")]
    assert t["turns"][1]["text"].startswith("Who reads the fee ratio") and t["needs_done"] == ["goal"]
    assert len(stub.seen) == 1 and len(again["turns"]) == 2  # answered once


def test_model_off_asks_the_next_goal_labelled(app):
    c = client(app, ARJUN)
    t = c.post("/api/v1/intents/chat", json={"text": "A cash drag report for the committee"}).json()
    assert t["turns"][-1]["name"] == "North (rules only)" and t["needs_done"] == ["goal"]
    assert t["turns"][-1]["text"].startswith("Who should be able to see this work")  # G1: asked once, second
    t = c.post(f"/api/v1/intents/{t['id']}/chat", json={"text": "Only the people I name."}).json()
    assert t["turns"][-1]["text"].startswith("Who reads it, and what do they decide")
    t = c.post(f"/api/v1/intents/{t['id']}/chat", json={"text": "The committee reads it and decides on rebalancing."}).json()
    t = c.post(f"/api/v1/intents/{t['id']}/chat", json={"text": "Monthly, by the eighth working day."}).json()
    assert t["needs_done"] == ["goal", "access", "readers", "frequency"] and t["turns"][-1]["text"].startswith("How is this produced today")
    t = c.post(f"/api/v1/intents/{t['id']}/chat", json={"text": "Leela pulls the custodian file. Arjun checks the figures."}).json()
    assert [s["who"] for s in t["process_map"]["steps"]] == ["Leela", "Arjun"] and t["needs_done"] == ["goal", "access", "readers", "frequency", "process"]


def test_analyst_talks_only_on_a_team_intent(app):
    iid = client(app, ARJUN).post("/api/v1/intents/chat", json={"text": "Concentration by asset class"}).json()["id"]
    leela = client(app, LEELA)
    assert leela.get(f"/api/v1/intents/{iid}/chat").status_code == 403  # G1: Internal is the team's alone
    assert leela.post(f"/api/v1/intents/{iid}/chat", json={"text": "hello"}).status_code == 403  # off the team: still refused
    on_team(app, iid, "Leela Raman")
    assert leela.get(f"/api/v1/intents/{iid}/chat").status_code == 200
    assert leela.post(f"/api/v1/intents/{iid}/chat", json={"text": "hello"}).status_code == 200
