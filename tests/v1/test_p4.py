"""P4 Benchmarks: North copies the benchmark from the person's words (never the model's) and accepts "I don't have one"; Span's design
carries one per KPI (proposed where the SOW has none); Flow's load checks each gold figure, writes build/verify/<iid>.json and raises
every miss as a comment to the raiser and the sponsor; the build pack is refused until a comment on each miss is answered."""
import json
import shutil
import types
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.agents.protocols import ModelReply
from sh_platform.app import create_app
from sh_platform.settings import Settings
from sh_platform.v1 import p1_project as P1
from sh_platform.v1 import p4_benchmarks as P4

ROOT = Path(__file__).resolve().parents[2]
PW = "p4-test-only-password"  # set on the tmp copy's accounts; the seeded passwords are never read
IID = "p4test"


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data", data)
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    for who in ("arjun.mehta", "leela.raman", "priya.nair"):
        app.state.account_store.set_password(f"{who}.neera@example.test", PW)
    return app, data / "neera"


def _client(app, who):
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": f"{who}.neera@example.test", "password": PW}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


class Stub:
    def __init__(self, answer):
        self.answer = answer

    def complete(self, module_id, messages, tools=None):
        return ModelReply(text=json.dumps(self.answer))


def test_parse_and_design_list():
    b = P4.parse("for September we reported 4.2 %; after the load the figure should read 4.3 % within 0.1", "Arjun Mehta", date(2026, 10, 8))
    assert b == {"period": "2026-09", "reported": 4.2, "expected": 4.3, "tolerance": 0.1, "source": "said by Arjun Mehta"}
    sow = {"kpis": [{"code": "K01", "name": "Fee ratio"}, {"code": "K02", "name": "Cash drag"}]}
    P4.from_talk(sow, None, "I don't have one.", "Arjun Mehta", asked=True)  # North (rules only) asked; no KPI named
    assert [k["benchmark"] for k in sow["kpis"]] == [None, None]
    d = P4.for_design(sow, date(2026, 10, 8))
    assert [(x["code"], x["proposed"], x["period"], x["expected"]) for x in d] == [("K01", True, "2026-09", None), ("K02", True, "2026-09", None)]


def test_north_copies_the_figures_from_the_persons_words(world):
    app, _ = world
    c = _client(app, "arjun.mehta")
    stub = Stub({"reply": "Noted. Which systems hold the fees?", "covered": ["goal", "kpis", "benchmarks"], "ready": False, "process_steps": None,
                 "sow_patch": {"kpis": [{"name": "Fee ratio", "definition": "Fees over assets", "benchmark": "given"},
                                        {"name": "Cash drag", "definition": "Return lost to idle cash"}]}})
    app.state.build_model_factory = lambda plane: stub
    try:
        t = c.post("/api/v1/intents/chat", json={"text": "Fee ratio: for September 2026 we reported 4.2 %; after the load it should read 4.2 % within 0.1"}).json()
        for p in t["proposals"]["pending"]:  # L2: North's KPIs wait for a yes; accepting copies the figures from the person's words
            assert c.post(f"/api/v1/intents/{t['id']}/proposals/{p['id']}/accept").status_code == 200
        stub.answer = {**stub.answer, "sow_patch": {"kpis": [{"name": "Cash drag", "benchmark": "none"}]}}
        t = c.post(f"/api/v1/intents/{t['id']}/chat", json={"text": "For cash drag I don't have one."}).json()
    finally:
        del app.state.build_model_factory
    k = {x["name"]: x for x in t["sow"]["kpis"]}
    b = k["Fee ratio"]["benchmark"]  # G3: the old field points at the sheet's rows and carries the first row's figures
    assert b["sheet"] is True and len(b["rows"]) == 1
    assert {x: b[x] for x in ("period", "reported", "expected", "tolerance", "source")} == {"period": "2026-09", "reported": 4.2, "expected": 4.2, "tolerance": 0.1, "source": "said by Arjun Mehta"}
    assert k["Cash drag"]["benchmark"] is None and "benchmarks" in t["needs_done"]


def test_load_checks_benchmarks_comments_misses_and_blocks_signing(world):
    app, co = world
    (co / "build" / "mapping").mkdir(parents=True, exist_ok=True)
    (co / "build" / "mapping" / f"{IID}.json").write_text(json.dumps({"intent_id": IID, "version": 1, "rows": [
        {"n": 1, "layer": "silver", "target_table": "silver.positions", "target_field": "market_value", "source_id": "p4_positions",
         "source_table": "positions", "source_field": "market_value", "transformation": "as is", "rule": "", "test": "", "status": "mapped"},
        {"n": 2, "layer": "gold", "target_table": "gold.p4_aum", "target_field": "aum", "source_id": "p4_positions",
         "source_table": "positions", "source_field": "market_value", "transformation": "sum per month", "rule": "", "test": "", "status": "mapped"}]}))
    (co / "intents" / IID).mkdir(parents=True, exist_ok=True)
    (co / "intents" / IID / "sow.json").write_text(json.dumps({"intent_id": IID, "state": "signed",
        "sources": [{"id": "p4_positions", "name": "Positions"}],
        "kpis": [{"code": "K01", "name": "Assets", "source_ids": ["p4_positions"],
                  "benchmark": {"period": "2026-08", "reported": 300, "expected": 310, "tolerance": 1, "source": "said by Arjun Mehta"}},
                 {"code": "K02", "name": "Assets again", "source_ids": ["p4_positions"],
                  "benchmark": {"period": "2026-08", "reported": 300, "expected": 300, "tolerance": 0, "source": "said by Arjun Mehta"}}],
        "catalogue": [{"table": "gold.p4_aum", "layer": "gold", "feeds_kpis": ["K01", "K02"]}]}))
    land = co / "landing" / "p4_positions"
    land.mkdir(parents=True, exist_ok=True)
    (land / "positions_2026-08.csv").write_text("account_id,as_of,market_value\nA1,2026-08-31,100\nA2,2026-08-31,200\n", encoding="utf-8")
    plane = types.SimpleNamespace(path=lambda *p: co.joinpath(*p))
    pid = P1.create_project(plane, IID, "Assets", "Arjun Mehta")["id"]
    P1.set_person(plane, pid, "sponsor", "Priya Nair")
    P1.set_person(plane, pid, "builder", "Leela Raman")

    c = _client(app, "leela.raman")
    r = c.post(f"/api/v1/build/{IID}/load")
    assert r.status_code == 200, r.text
    rows = json.loads((co / "build" / "verify" / f"{IID}.json").read_text())
    assert rows == r.json()["benchmarks"]
    assert [(x["code"], x["got"], x["met"]) for x in rows] == [("K01", 300.0, False), ("K02", 300.0, True)]
    cs = P1.comments(plane, pid, "build_pack")
    assert [(x["line_ref"], x["to"], x["by"]) for x in cs] == [("benchmark:K01:2026-08", "Arjun Mehta", "flow"),
                                                                ("benchmark:K01:2026-08", "Priya Nair", "flow")]
    assert "reads 300" in cs[0]["text"] and "expects 310 within 1" in cs[0]["text"]

    refused = c.post(f"/api/v1/build/{IID}/pack/sign")  # nobody answered the miss yet
    assert refused.status_code == 409 and "K01" in refused.json()["detail"]
    assert c.post(f"/api/v1/projects/{pid}/comments/{cs[0]['id']}/resolve").status_code == 409  # B1: a signer cannot resolve around an unanswered miss
    assert c.post(f"/api/v1/build/{IID}/pack/sign").status_code == 409
    c.post(f"/api/v1/build/{IID}/load")  # a reload raises the same miss once only
    assert len(P1.comments(plane, pid, "build_pack")) == 2
    a = _client(app, "priya.nair").post(f"/api/v1/projects/{pid}/comments/{cs[1]['id']}/answer", json={"text": "310 included a late fee."})
    assert a.status_code == 200, a.text
    assert c.post(f"/api/v1/build/{IID}/pack/sign").status_code == 409  # S4: answered is not resolved
    assert c.post(f"/api/v1/projects/{pid}/comments/{cs[1]['id']}/resolve").status_code == 200  # the signer reads the answer and resolves
    got = c.get(f"/api/v1/build/{IID}/benchmarks").json()
    assert got["sign_block"] is None and got["verify"] == rows and got["benchmarks"][0]["proposed"] is False
    s = c.post(f"/api/v1/build/{IID}/pack/sign")
    assert s.status_code == 200, s.text
    pack = next(x for x in s.json()["project"]["artefacts"] if x["kind"] == "build_pack")
    assert pack["state"] == "signed" and pack["signed_by"] == "Leela Raman" and s.json()["project"]["stage"] == "built"
