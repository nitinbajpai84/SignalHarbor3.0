"""F1 The data engineer's conversation with Flow: open points from an unclear mapping row, a formula the runner could not build and a failed
check; a stubbed model reads an answer into a row patch (the context passes the gateway's checks); with the model off, pasted SQL is kept
on the row as the engineer's, a point is flagged and exported, and the last answer hands over to ops. A sponsor reads but may not answer."""
import json
import shutil
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.agents.protocols import ModelReply
from sh_platform.app import create_app
from sh_platform.egress.rows import json_findings
from sh_platform.settings import Settings
from tests.v1.team import on_team

ROOT = Path(__file__).resolve().parents[2]
PW = "f1-test-only-password"  # set on the tmp copy's accounts; the seeded passwords are never read
IID = "f1test"
ROWS = [  # the mapping sheet contract (docs/plan/V1-BUILD.md); a tiny synthetic fixture of this card's own
    {"n": 1, "layer": "silver", "target_table": "silver.positions", "target_field": "market_value", "source_id": "custody_positions",
     "source_table": "positions", "source_field": "market_value", "transformation": "as is", "rule": "", "test": "not empty", "status": "mapped"},
    {"n": 2, "layer": "silver", "target_table": "silver.positions", "target_field": "issuer", "source_id": "custody_positions",
     "source_table": "positions", "source_field": "", "transformation": "Not available yet: no source field is named.", "rule": "",
     "test": "", "status": "unclear"},
    {"n": 3, "layer": "gold", "target_table": "gold.concentration", "target_field": "value", "source_id": "custody_positions",
     "source_table": "positions", "source_field": "market_value", "transformation": "Largest issuer over the total.", "op": "formula",
     "rule": "Flow could not write the SQL (no model answer).", "test": "", "status": "unclear"},
]
RUN = {"id": "run-f1-a", "source": "v1_custody_positions", "status": "failed", "rows": 40, "started": "2026-10-01T08:00:00+00:00",
       "rules": [{"rule": "market_value:not empty", "passed": False, "count": 12}, {"rule": "account_id:not empty", "passed": True, "count": 0}]}


class Stub:
    def __init__(self, answer: dict):
        self.answer, self.seen = answer, []

    def complete(self, module_id, messages, tools=None):
        self.seen.append(messages)
        return ModelReply(text=json.dumps(self.answer))


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data", data)
    co = data / "neera"
    (co / "build" / "mapping").mkdir(parents=True, exist_ok=True)
    (co / "build" / "mapping" / f"{IID}.json").write_text(json.dumps({"intent_id": IID, "version": 1, "rows": ROWS}), encoding="utf-8")
    (co / "intents" / IID).mkdir(parents=True, exist_ok=True)
    (co / "intents" / IID / "sow.json").write_text(json.dumps({
        "sources": [{"id": "custody_positions", "name": "Custodian positions", "owner": "Leela Raman"}],
        "kpis": [{"code": "K01", "name": "Concentration", "source_ids": ["custody_positions"]}],
        "catalogue": [{"table": "concentration", "layer": "gold", "source_id": "custody_positions", "feeds_kpis": ["K01"]}]}), encoding="utf-8")
    runs = co / "warehouse" / "runs.json"
    old = json.loads(runs.read_text(encoding="utf-8"))["runs"] if runs.exists() else []
    runs.write_text(json.dumps({"runs": old + [RUN]}), encoding="utf-8")
    (co / "extractions").mkdir(exist_ok=True)  # X5's record: a statement whose closing value did not parse waits for review
    (co / "extractions" / "docf1.json").write_text(json.dumps({"doc_id": "docf1", "file": "documents/statement_sep.txt", "intent_id": IID,
        "status": "review", "at": "2026-10-02T08:00:00+00:00", "checks": [{"field": "closing_value", "kind": "parses", "ok": False,
                                                                             "why": "not a number"}]}), encoding="utf-8")
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    for who in ("leela.raman", "priya.nair"):
        app.state.account_store.set_password(f"{who}.neera@example.test", PW)
    return app, co


def _client(world, who):
    c = TestClient(world[0])
    assert c.post("/api/auth/login", json={"email": f"{who}.neera@example.test", "password": PW}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def _rows(co):
    return {r["n"]: r for r in json.loads((co / "build" / "mapping" / f"{IID}.json").read_text(encoding="utf-8"))["rows"]}


def test_flow_walks_the_open_points_and_hands_over(world):
    app, co = world
    on_team(app, IID, "Leela Raman")  # G1: Internal is the team's alone
    c = _client(world, "leela.raman")
    v = c.get(f"/api/v1/build/{IID}/engineer").json()
    assert [p["kind"] for p in v["points"]] == ["mapping", "formula", "check", "document"]
    row2, formula, check, doc = v["points"]
    assert "closing_value" in doc["question"] and doc["about"] == "statement_sep.txt"
    assert v["current"] == row2["id"] and "4 open points" in v["opening"] and row2["question"].startswith("Row 2:")
    assert formula["about"] == "Concentration" and "could not write the SQL" in formula["why"]
    assert "12 rows" in check["question"] and v["context"]["mapping_rows"] == 3 and v["context"]["skill"]

    # the model reads the answer into a row patch
    stub = Stub({"reply": "I will read the issuer column.", "decision": "change", "source_field": "issuer_name",
                 "transformation": "Trim spaces from issuer_name.", "rule": "", "sql": None})
    app.state.build_model_factory = lambda plane: stub
    try:
        v = c.post(f"/api/v1/build/{IID}/engineer", json={"text": "Use the issuer name column, trimmed."}).json()
    finally:
        del app.state.build_model_factory
    assert [t["by"] for t in v["turns"]] == ["flow", "person", "flow"] and v["turns"][-1]["name"] == "Span"
    assert v["turns"][-1]["text"].startswith("I will read the issuer column. I have proposed 2 things")  # L2: the row waits for a yes
    assert _rows(co)[2]["status"] == "unclear"
    pr = v["proposals"]["pending"][0]
    assert c.post(f"/api/v1/intents/{IID}/proposals/{pr['id']}/accept").status_code == 200
    r = _rows(co)[2]
    assert (r["source_field"], r["status"]) == ("issuer_name", "mapped")
    meta = json.loads((co / "build" / "mapping" / f"{IID}.meta.json").read_text(encoding="utf-8"))
    assert "silver.positions.issuer" in meta["edited"]  # B3's edit protection: a redraft keeps it
    for messages in stub.seen:  # what went to the model passes the gateway's row and size checks
        for m in messages:
            assert json_findings(m["content"]) == (None, []), m["content"][:300]

    # model off: pasted SQL is kept on the row as the engineer's
    sql = 'select period, max(mv) / sum(mv) as value from silver."v1_custody_positions" group by period'
    v = c.post(f"/api/v1/build/{IID}/engineer", json={"text": sql}).json()
    r = _rows(co)[3]
    assert (r["sql"], r["sql_by"], r["status"]) == (sql, "engineer", "mapped")
    assert [p["kind"] for p in v["points"]] == ["check", "document"]

    # flag the check for a real engineer: it stays open and exports
    v = c.post(f"/api/v1/build/{IID}/engineer/flag", json={"point": check["id"], "note": "Ask the custodian"}).json()
    assert v["points"][0]["flagged"]["note"] == "Ask the custodian"
    md = c.get(f"/api/v1/build/{IID}/engineer/flagged.md")
    assert md.status_code == 200 and "Ask the custodian" in md.text and "Custodian positions" in md.text

    assert v["current"] == doc["id"]  # the walk skips a flagged point while another is open
    v = c.post(f"/api/v1/build/{IID}/engineer", json={"text": "I am not sure yet."}).json()
    assert len(v["points"]) == 2 and v["turns"][-1]["name"] == "Span (rules only)"  # a don't-know never closes a point
    v = c.post(f"/api/v1/build/{IID}/engineer", json={"text": "The closing value is on the next line."}).json()
    assert [p["kind"] for p in v["points"]] == ["check"] and "review page" in v["turns"][-1]["text"]
    v = c.post(f"/api/v1/build/{IID}/engineer", json={"text": "The file is wrong; the custodian resends it."}).json()
    assert v["points"] == [] and v["handed_over"] and "last open point" in v["turns"][-1]["text"]


def test_sponsor_reads_but_may_not_answer(world):
    c = _client(world, "priya.nair")
    assert c.get(f"/api/v1/build/{IID}/engineer").status_code == 200
    assert c.post(f"/api/v1/build/{IID}/engineer", json={"text": "yes"}).status_code == 403
    assert c.post(f"/api/v1/build/{IID}/engineer/flag", json={"point": "x"}).status_code == 403
    assert _client(world, "leela.raman").get("/api/v1/build/nosheet/engineer").status_code == 404
