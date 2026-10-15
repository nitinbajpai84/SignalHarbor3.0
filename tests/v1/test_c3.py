"""C3 Lumen's conversation: a stubbed model shapes the brief (KPIs and feeds go out by name and kind, come back as codes and ids; the
context passes the gateway's row and size checks), a dropped dashboard is kept, an end user's answer appends to the brief; with the model
off Lumen (rules only) asks the next goal; a participant may answer the short questions but not shape the page."""
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
from sh_platform.v1 import c3_chat

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
LEELA, DEV = "leela.raman.neera@example.test", "dev.sharma.neera@example.test"
IID = "int_c3test"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")

SOW = {"id": f"sow-{IID}", "intent_id": IID, "title": "Monthly performance pack", "state": "signed", "version": 1,
       "kpis": [{"code": "K01", "name": "Time-weighted return", "definition": "Growth net of fees", "unit": "%", "period": "monthly"},
                {"code": "K02", "name": "Cash drag", "definition": "Return lost to idle cash", "unit": "%", "period": "monthly"}],
       "sources": [], "catalogue": [], "governance": [], "unclear": [], "signature": {"name": "Arjun Mehta", "role": "company_admin", "at": "2026-10-01"}}


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("c3") / "data"
    shutil.copytree(ROOT / "data", data)
    d = data / "neera" / "intents" / IID
    d.mkdir(parents=True)
    (d / "sow.json").write_text(json.dumps(SOW))
    a = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    a.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    a.state.c3_data = data
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
    "reply": c3_chat.CLOSING,
    "brief_patch": {
        "views": [{"name": "Committee overview", "audience": "the investment committee", "kpis": ["Cash drag", "Time-weighted return", "Made up"],
                   "comparisons": ["policy benchmark", "previous quarter"], "filters": ["entity"], "refresh": "monthly"}],
        "feeds_wanted": ["FX rates"],
        "levers": [{"name": "Cash withdrawal", "affects": ["Cash drag"], "range": "small to large"}],
        "notes": ["Idle cash after a capital call pulls the return down"],
    },
    "covered": list(c3_chat.GOALS), "ready": True,
}


def test_model_shapes_the_brief_and_an_end_user_adds_to_it(app):
    c = client(app, LEELA)
    stub = Stub(READY)
    app.state.build_model_factory = lambda plane: stub
    try:
        dash = base64.b64encode(b"page,figure\nreturns,twr\nfees,fee ratio\n").decode()
        r = c.post(f"/api/v1/consume/brief/{IID}/chat", json={"text": "This is our quarterly pack.", "files": [{"name": "c3_pack.csv", "data": dash}]})
    finally:
        del app.state.build_model_factory
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["brief"]["views"] == [] and v["brief"]["existing_dashboards"][0]["name"] == "c3_pack.csv"  # L2: the dropped file is kept, the model's patch waits for a yes
    assert v["state"] == "open" and v["proposals"]["pending"][0]["document"] == "brief"
    assert c.post(f"/api/v1/intents/{IID}/proposals/{v['proposals']['pending'][0]['id']}/accept").status_code == 200
    app.state.build_model_factory = lambda plane: stub
    try:
        r = c.post(f"/api/v1/consume/brief/{IID}/chat", json={"text": "That is all."})  # nothing left to propose: Lumen closes
        assert r.status_code == 200, r.text
        v = r.json()
    finally:
        del app.state.build_model_factory
    b = v["brief"]
    assert b["views"][0]["kpis"] == ["K02", "K01"] and b["views"][0]["comparisons"] == ["policy benchmark", "previous quarter"]
    assert b["feeds_wanted"] == ["fx_rates"] and b["levers"] == [{"name": "Cash withdrawal", "affects": ["K02"], "range": "small to large"}]
    assert b["existing_dashboards"][0]["name"] == "c3_pack.csv"
    assert v["state"] == "ready" and v["turns"][-1]["name"] == "Lumen" and v["turns"][-1]["text"].startswith("Here is the brief")
    for messages in stub.seen:  # what went out passes the gateway's checks, and carries no KPI code or feed id
        for m in messages:
            assert json_findings(m["content"]) == (None, []), m["content"][:300]
    sent = json.dumps(stub.seen[0][1]["content"])
    assert "K01" not in sent and "fx_rates" not in sent and "FX rates" in sent and "c3_pack" in sent
    assert "Lumen" in stub.seen[0][0]["content"] and "Questions worth asking" in stub.seen[0][0]["content"]  # the skill is loaded
    assert c3_chat.kpi_order(_plane_of(app), IID) == ["K02", "K01"]

    dev = client(app, DEV)
    assert dev.get(f"/api/v1/consume/brief?iid={IID}").json()["ask_next"] == c3_chat.ASK_USERS[0]
    u = dev.post(f"/api/v1/consume/brief/{IID}/input", json={"text": "Return first; I decide on rebalancing."}).json()
    got = u["brief"]["end_user_inputs"][-1]
    assert (got["by"], got["question"]) == ("Dev Sharma", c3_chat.ASK_USERS[0]) and u["ask_next"] == c3_chat.ASK_USERS[1]


def _plane_of(app):
    class P:  # the tmp data plane for neera, enough for read_brief
        def path(self, *parts):
            return app.state.c3_data.joinpath("neera", *parts)
    return P()


def test_model_off_asks_the_next_goal_labelled(app):
    c = client(app, LEELA)
    iid = "int_c3off"
    d = app.state.c3_data / "neera" / "intents" / iid
    d.mkdir(parents=True)
    (d / "sow.json").write_text(json.dumps({**SOW, "id": f"sow-{iid}", "intent_id": iid}))
    v = c.post(f"/api/v1/consume/brief/{iid}/chat", json={"text": "No, nothing today."}).json()
    assert v["turns"][-1]["name"] == "Lumen (rules only)" and v["needs_done"] == ["existing"]
    assert v["turns"][-1]["text"] == c3_chat.GOALS["priority"][1]
    v = c.post(f"/api/v1/consume/brief/{iid}/chat", json={"text": "Cash drag first, then time-weighted return."}).json()
    assert v["brief"]["views"][0]["kpis"] == ["K02", "K01"] and v["turns"][-1]["text"] == c3_chat.GOALS["comparisons"][1]


def test_participant_answers_but_may_not_shape(app):
    dev = client(app, DEV)
    assert dev.post(f"/api/v1/consume/brief/{IID}/chat", json={"text": "hello"}).status_code == 200  # talking is open to all
    assert dev.post("/api/v1/consume/brief/int_nope/input", json={"text": "x"}).status_code == 404
