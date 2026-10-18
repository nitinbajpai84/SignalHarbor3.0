"""A1 Span's conversation: with the model off, the rule-based Span drafts design, scan and mapping one message at a time (labelled),
the head of data approves (defaults stand, scope agreed, hand-over to Flow) and the talk closes; an analyst may not approve. With a
stubbed model, Span's patch runs the three steps, merges the data model by alias, and what went to the model passes the gateway."""
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
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
CREDS = SEED / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
ARJUN, LEELA = "arjun.mehta.neera@example.test", "leela.raman.neera@example.test"
SOW = {  # b1's fixture, with a landing file for the custodian so one measure scans as available
    "id": "sow-a1", "title": "Monthly performance pack", "state": "signed", "version": 1,
    "goal": {"line": "See net returns monthly", "why": "Board pack", "readers": [], "decisions": [], "needed_by": "2026-11"},
    "process": {"steps": [], "handovers": []},
    "kpis": [{"code": "TWR", "name": "Time-weighted return", "definition": "Return net of flows", "formula": "chain-linked monthly returns",
              "unit": "%", "period": "month", "owner": "Arjun Mehta", "source_ids": ["custodian"], "status": "defined", "pack_suggested": False},
             {"code": "FEE", "name": "Fee ratio", "definition": "Fees over average assets", "formula": "fees / avg assets", "unit": "%",
              "period": "month", "owner": "Arjun Mehta", "source_ids": ["ledger"], "status": "unclear", "pack_suggested": True}],
    "sources": [{"id": "custodian", "name": "Custodian positions", "kind": "file", "holds": "Monthly positions", "sample_path": "landing/custodian/a1.csv",
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
    data = tmp_path_factory.mktemp("a1") / "data"
    shutil.copytree(SEED, data)
    from sh_platform.plane import PlaneStore
    from tools.reset_v1 import reset
    reset(PlaneStore(data).plane_for("neera"))
    (data / "neera" / "landing" / "custodian").mkdir(parents=True, exist_ok=True)
    (data / "neera" / "landing" / "custodian" / "a1.csv").write_text("MV,market_value\n100,100\n", encoding="utf-8")
    for iid in ("a1-off", "a1-model"):
        (data / "neera" / "intents" / iid).mkdir(parents=True, exist_ok=True)
        (data / "neera" / "intents" / iid / "sow.json").write_text(json.dumps({**SOW, "intent_id": iid}), encoding="utf-8")
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    yield app, data, pw.get  # a bound method, so a failing assertion never prints the passwords
    mp.undo()


def client(world, email):
    app, _, pw = world
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw(email)}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_rules_only_span_drafts_then_head_of_data_approves(world):
    leela, arjun = client(world, LEELA), client(world, ARJUN)
    on_team(world[0], "a1-off", "Leela Raman")  # G1: she picked the work up
    base = "/api/v1/build/a1-off/blueprint"
    v = leela.get(f"{base}/chat").json()
    assert v["greeting"].startswith("Hello Leela. I am Span") and v["can_talk"] and not v["can_approve"]
    names = []
    for text in ("Please start.", "Go on.", "And the mapping."):
        r = leela.post(f"{base}/chat", json={"text": text})
        assert r.status_code == 200, r.text
        v = r.json()
        names.append(v["turns"][-1]["name"])
    assert names == ["Span (rules only)"] * 3
    assert [t["did"][0].split(":")[0] for t in v["turns"] if t["by"] == "span"] == ["Design drafted", "Scan", "Mapping sheet version 1"]
    assert v["state"] == "ready" and v["design"] and v["mapping"]["rows"] and v["scope"] == ["TWR"]
    assert [c["title"] for c in v["layers"]["columns"]] == ["Sources", "Landing", "Cleaned", "Report"] and v["layers"]["links"]
    assert v["data_model"] and any(q["default"] for q in v["questions"])  # questions from skills/span/questions.md

    assert leela.post(f"{base}/approve").status_code == 403  # the architect drafts; the head of data approves
    r = arjun.post(f"{base}/approve")
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["state"] == "approved" and v["approved_by"] == "Arjun Mehta" and all(q["settled"] for q in v["questions"])
    assert v["scan"]["agreed"]["scope"] == ["TWR"] and not v["can_approve"]
    sheet = json.loads((world[1] / "neera" / "build" / "mapping" / "a1-off.json").read_text(encoding="utf-8"))
    assert sheet["version"] == 2  # redrafted to the agreed scope on approval
    assert leela.post(f"{base}/chat", json={"text": "One more change"}).status_code == 409
    saved = json.loads((world[1] / "neera" / "build" / "blueprint_conversation" / "a1-off.json").read_text(encoding="utf-8"))
    assert saved["state"] == "approved" and len(saved["turns"]) == 6


class Stub:
    def __init__(self, answer: dict):
        self.answer, self.seen = answer, []

    def complete(self, module_id, messages, tools=None):
        self.seen.append(messages)
        if "LATEST MESSAGE FROM THE ARCHITECT" in json.dumps(messages):
            return ModelReply(text=json.dumps(self.answer))
        return ModelReply(text="no")  # b1's and b3's own calls: their labelled rule-based drafts stand


def test_model_patch_runs_the_steps_and_merges_by_alias(world):
    app = world[0]
    stub = Stub({"reply": "I drafted the layers, scanned and mapped. One question for the head of data.", "run": ["design", "scan", "mapping"],
                 "data_model": [{"table": "fact_returns", "kind": "fact", "grain": "one row per account per month", "keys": ["account_key"],
                                 "relationships": ["joins dim_account on account_key"], "measures": ["a"]}],
                 "questions": [{"question": "Restate a closed month on a late correction?", "default": "Restate", "why": "Past packs"}],
                 "scope": ["a", "b"], "ready": True})
    app.state.build_model_factory = lambda plane: stub
    try:
        leela = client(world, LEELA)
        v = leela.post("/api/v1/build/a1-model/blueprint/chat", json={"text": "Draft the blueprint"}).json()
        # L2: the steps ran, but the data model, questions and scope wait for a yes
        assert v["turns"][-1]["name"] == "Span" and len(v["turns"][-1]["did"]) == 3 and v["state"] == "open", v["turns"][-1]
        assert not v["questions"] and v["proposals"]["pending"][0]["document"] == "design"
        assert leela.post(f"/api/v1/intents/a1-model/proposals/{v['proposals']['pending'][0]['id']}/accept").status_code == 200
        v = leela.get("/api/v1/build/a1-model/blueprint/chat").json()
    finally:
        del app.state.build_model_factory
    assert v["data_model"][0]["measures"] == ["Time-weighted return"] and v["questions"][0]["default"] == "Restate"
    assert v["scope"] == ["TWR", "FEE"]  # proposed; the approval keeps only what the scan can build
    chat = [m for m in stub.seen if "LATEST MESSAGE FROM THE ARCHITECT" in json.dumps(m)]
    assert len(chat) == 1
    for m in chat[0]:
        assert json_findings(m["content"]) == (None, []), m["content"][:300]
    ctx = json.loads(chat[0][1]["content"])["context"]
    assert "TWR" not in json.dumps(ctx) and "ref: a" in json.dumps(ctx)  # measures go by letter alias
