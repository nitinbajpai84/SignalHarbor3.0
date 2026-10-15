"""Harbor 3.0 process-only builds (UC9): documents in, process map and SOP out, no data load. The 2.0 engine and the model are stubbed
(as in test_v3_harbor); the document reading, the map, the SOP, the cards, the routes, Ask and Knowledge are real."""
import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_harbor as H  # noqa: E402
from sh_platform.v1 import v3_process as P  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

FIX = ROOT / "tests" / "v1" / "fixtures" / "10uc" / "process_narrative"
NARRATIVE, EMAIL = (FIX / "month_end_process_narrative.md").read_text(encoding="utf-8"), (FIX / "handover_email_mei_to_raj.txt").read_text(encoding="utf-8")
ASK = "We do the month-end investment report from memory. I want the steps written down: who does what, and a procedure document for a new joiner."
SOW = {"id": "sow-ini-1", "intent_id": "ini-1", "title": "We do the month-end investment report", "state": "signed", "version": 1,
       "signature": {"name": "Priya Nair", "role": "raiser", "at": "2026-10-15T04:18:40+00:00"},
       "goal": {"line": ASK, "why": "", "readers": ["Finance team"], "decisions": ["Sign off the report"], "needed_by": "Monthly"},
       "kpis": [{"code": "K01", "name": "Net worth", "formula": "Sum of positions + cash", "pack_suggested": True, "status": "defined"}],
       "process": {"steps": [{"n": 1, "name": "A guess", "who": "Operations"}], "handovers": []},
       "governance": [{"kind": "access", "rule": "Only the Finance team may see the pack"}], "sources": []}


def steps_of(text):
    return P._structured(text)


def test_the_narrative_gives_six_steps_and_the_email_only_fills_blanks():
    a, b = steps_of(NARRATIVE), P._numbered(EMAIL)
    assert [s["n"] for s in a] == [1, 2, 3, 4, 5, 6] and [s["n"] for s in b] == [1, 2, 3]
    assert a[1]["who"] == "Mei Chen" and a[1]["system"] == "Excel" and a[1]["manual"] is True and "5,000 USD" in a[1]["control"] and "break case" in a[1]["exception"]
    assert a[4]["manual"] is False and a[4]["who"] == "Raj Patel" and b[1]["who"] == "Mei Chen"  # the email's "I" is its sender
    steps, seen = P.merge([("email.txt", b), ("narrative.md", a)])  # the longer document is the base, whatever the order
    assert len(steps) == 6 and seen[2] == ["narrative.md", "email.txt"] and seen[5] == ["narrative.md"]
    assert steps[1]["control"] == a[1]["control"]  # the email never overwrites the narrative


def test_handovers_lanes_decisions_and_purpose():
    hand = P.handovers_of(NARRATIVE)
    assert [(h["from_step"], h["to_step"]) for h in hand] == [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6)] and "no log" in hand[2]["what"]
    steps = steps_of(NARRATIVE)
    assert [(la["name"], la["steps"]) for la in P.lanes_of(steps)] == [("Mei Chen", [1, 2, 3]), ("Raj Patel", [4, 5]), ("Daniel Foo", [6])]
    d = {x["step"]: x for x in P.decisions_of(steps)}
    assert len(d) == 6 and d[2]["owner"] == "Mei Chen" and d[2]["told"] == "Raj" and d[1]["told"] == ""
    assert P._section(NARRATIVE, "Purpose").startswith("This note describes, step by step")


def _plane(tmp_path, files):
    (tmp_path / "v3").mkdir(exist_ok=True)
    (tmp_path / "v3" / "files.json").write_text(json.dumps(files))
    return SimpleNamespace(path=lambda *p: tmp_path.joinpath(*p))


def _file(name, status="waiting", thread=None):
    return {"name": name, "status": status, "source": "", "thread": thread, "arrived_at": "2026-10-15T00:00:00Z"}


def test_only_a_process_ask_with_documents_and_no_formula_is_process_only(tmp_path):
    th = {"id": "t-1"}
    docs = _plane(tmp_path, [_file("narrative.md"), _file("mail.eml"), _file("old.docx", "loaded", "t-9")])
    assert P.is_process(docs, th, SOW)
    assert not P.is_process(docs, th, {**SOW, "goal": {"line": "Can we meet the capital calls?"}, "title": "Capital calls"})  # no process asked
    own = {**SOW, "kpis": [{"name": "Cash", "formula": "sum(cash)", "status": "defined"}]}
    assert not P.is_process(docs, th, own)  # a figure the person defined over data
    assert not P.is_process(_plane(tmp_path, [_file("narrative.md"), _file("cash.csv")]), th, SOW)  # a data table arrived
    assert P.is_process(_plane(tmp_path, [_file("cash.csv", "recognised", "t-2")]), th, SOW)  # another thread's table is not this one's


@pytest.fixture()
def office(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    monkeypatch.setattr(H, "SYNC", True)

    def fake_api(self, who, method, path, body=None, files=None, data=None, soft=False):
        if path == "/api/v1/intents/chat":
            return {"id": "ini-1", "turns": [{"by": "north", "text": "Here is what I understood."}], "sow": SOW}
        return SOW if path.endswith("/sow") else {}

    def sign(x):
        x.th["pid"], x.th["record"] = "prj-1", {"signed_by": "Priya Nair", "role": "raiser", "signed_at": "2026-10-15T04:18:40+00:00"}
        return "signed"
    monkeypatch.setattr(H.Ctx, "api", fake_api)
    monkeypatch.setitem(H.CHAINS, "PA", ([("North", "Signed the intent", sign), ("North", "Read the documents", P.p_read), ("North", "Drew the process map", P.p_map)], "decision2"))
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    (data / "evergreen" / "intents" / "ini-1").mkdir(parents=True)
    (data / "evergreen" / "intents" / "ini-1" / "sow.json").write_text(json.dumps(SOW))
    pw = {l.split()[0]: l.split()[1] for l in (data / "_control" / "seed_credentials.txt").read_text().splitlines() if l.strip()}
    c = TestClient(create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")))
    email = "anita.rao.evergreen@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c


def drop(c, name, text):
    return c.post("/api/v3/files", json={"name": name, "data": base64.b64encode(text.encode()).decode()})


def test_from_documents_to_a_live_procedure_with_no_data_load(office):
    c = office
    drop(c, "month_end_process_narrative.md", NARRATIVE)
    drop(c, "handover_email_mei_to_raj.txt", EMAIL)
    t = c.post("/api/v3/threads", json={"text": ASK}).json()
    tid = t["id"]
    assert t["stage"] == "decision1"
    t = c.post(f"/api/v3/threads/{tid}/decide", json={"n": 1, "answer": "confirm"}).json()  # Decision 1 as now
    assert t["stage"] == "decision2" and [s["agent"] for s in c.get(f"/api/v3/threads/{tid}/workbench").json()["steps"]] == ["North"] * 3
    d = t["decision"]
    assert d["n"] == 2 and d["title"] == "Is this the process?" and len(d["files"]) == 6 and d["questions"] == []
    assert d["files"][1]["read_as"] == "Mei Chen, Excel, by hand" and d["files"][2]["goes_to"].startswith("hands over to step 4:")
    assert "3 lanes" in d["summary"] and "Raj Patel: steps 4, 5" in d["summary"] and "5 hand-overs" in d["summary"]
    assert {f["status"] for f in c.get("/api/v3/files").json()["files"]} == {"loaded"}  # both documents were read; none was loaded as data

    t = c.post(f"/api/v3/threads/{tid}/decide", json={"n": 2, "answer": "carry_on", "answers": {}}).json()
    assert t["stage"] == "decision3" and t["decision"]["title"].startswith("Here is the procedure")
    sop = t["decision"]["sop"]
    assert sop["title"] == "Standard operating procedure: Monthly investment report in USD and SGD" and sop["manual_steps"] == [1, 2, 3, 4]
    assert any(x.startswith("Decision at step 2 (Mei Chen)") for x in sop["controls"]) and len(t["decision"]["checks"]) == 6
    assert all(ch["ok"] for ch in t["decision"]["checks"]) and any("input and output are not stated" in x for x in sop["open_points"])

    t = c.post(f"/api/v3/threads/{tid}/decide", json={"n": 3, "answer": "go_live"}).json()
    assert t["stage"] == "live" and "next_run" not in t and t["process"]["steps"] == 6  # a document deliverable: no schedule
    assert "6 steps, 4 flagged for automation" in c.get("/api/v3/desk").json()["note"]["text"]
    runs = [r["skill"] for r in __import__("sh_platform.v1.v3_skills", fromlist=["runs"]).runs(_plane_of(c), tid)]
    assert {"intent.read-company-doc", "intent.draw-process-lanes", "intent.draw-process-steps", "intent.map-decision-path", "intent.write-sop"} <= set(runs)

    r = c.get(f"/api/v3/threads/{tid}/sop?format=docx")
    assert r.status_code == 200 and r.content[:2] == b"PK" and "SOP-" in r.headers["content-disposition"]
    assert "## Steps" in c.get(f"/api/v3/threads/{tid}/sop?format=md").text and c.get(f"/api/v3/threads/{tid}/sop?format=pdf").status_code == 400

    a = c.post("/api/v3/ask", json={"text": "What are the steps of the month-end report process and who does each one?"}).json()
    assert a["answer"].count(";") == 5 and "1. Collect the exports (Mei Chen, File drop)" in a["answer"] and "6. Read the report (Daniel Foo, Report pack)" in a["answer"]
    assert a.get("figure") is None and a["trace"][0]["label"] == "Read the standard operating procedure"
    assert "Control: Difference per entity per day inside cash_tolerance (5,000 USD)" in c.post("/api/v3/ask", json={"text": "Tell me about step 2 of the process"}).json()["answer"]
    manual = c.post("/api/v3/ask", json={"text": "Which steps of the process are manual?"}).json()["answer"]
    assert manual.count(";") == 3 and "Read the report" not in manual

    k = c.get("/api/v3/knowledge").json()
    assert k["processes"][0]["lanes"] == ["Mei Chen", "Raj Patel", "Daniel Foo"] and len(k["processes"][0]["steps"]) == 6  # the map filled from the documents, not North's guess
    cons = c.get("/api/v3/consume").json()
    assert cons["reports"][0]["name"].startswith("Standard operating procedure") and any(g["q"].startswith("What are the steps of") for g in cons["golden"])


def _plane_of(c):
    from sh_platform.plane import PlaneStore
    return PlaneStore(c.app.state.settings.data_root).plane_for("evergreen")


def test_no_document_and_no_draft_is_a_question_and_a_draft_alone_stands(office, monkeypatch):
    c = office
    sow_no_steps = {**SOW, "process": {"steps": [], "handovers": []}}
    monkeypatch.setattr(H.Ctx, "api", lambda self, who, method, path, body=None, files=None, data=None, soft=False: (
        {"id": "ini-1", "turns": [], "sow": sow_no_steps} if path == "/api/v1/intents/chat" else sow_no_steps if path.endswith("/sow") else {}))
    tid = c.post("/api/v3/threads", json={"text": ASK}).json()["id"]
    t = c.post(f"/api/v3/threads/{tid}/decide", json={"n": 1, "answer": "confirm"}).json()
    assert t["stage"] == "question" and "no description of the process" in t["events"][-1]["text"]
    monkeypatch.setattr(H.Ctx, "api", lambda self, who, method, path, body=None, files=None, data=None, soft=False: (
        {"id": "ini-1", "turns": [], "sow": SOW} if path == "/api/v1/intents/chat" else SOW if path.endswith("/sow") else {}))
    t = c.post(f"/api/v3/threads/{tid}/say", json={"text": "retry"}).json()  # the signed brief's own draft stands, and says so
    assert t["stage"] == "decision2" and "North's draft" in t["decision"]["summary"] and t["decision"]["files"][0]["confidence"] == "medium"


def test_a_data_thread_is_untouched(office):
    c = office
    drop(c, "cash.csv", "entity,cash\nA,1\n")
    tid = c.post("/api/v3/threads", json={"text": ASK}).json()["id"]
    c.post(f"/api/v3/threads/{tid}/decide", json={"n": 1, "answer": "confirm"})
    assert H.load(_plane_of(c), tid)["mode"] == "data" and P.chain_name(None, H.load(_plane_of(c), tid), 2) == "B"
    assert c.post("/api/v3/ask", json={"text": "What are the steps of the process?"}).status_code in (200, 502)  # no live procedure: Lumen's path, no crash
