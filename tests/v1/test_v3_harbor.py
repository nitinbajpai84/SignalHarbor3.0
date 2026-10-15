"""Harbor 3.0: thread creation, decision 1, a stubbed chain reaching decision 2, a failing step becoming a question, a file drop
being recognised, and the desk shape. The 2.0 engine and the model are stubbed; routes, store and permissions are real."""
import base64
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_harbor as H  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

SOW = {"goal": {"line": "Can we meet the capital calls?", "readers": ["Anita"], "needed_by": "fifth business day", "decisions": ["fund a call"]},
       "sources": [{"name": "Administrator cash report"}, {"name": "Commitments schedule"}], "governance": [{"rule": "Cash is the administrator figure"}]}


def fake_api(self, who, method, path, body=None, files=None, data=None, soft=False):
    if path == "/api/v1/intents/chat":
        return {"id": "ini-1", "turns": [{"by": "north", "text": "Here is what I understood."}], "sow": SOW}
    return {}


def stub_a(x):
    x.th["maps"] = {"m1": {"name": "administrator_cash.csv", "tables": ["silver.cash"], "confidence": 0.95},
                    "m2": {"name": "commitments.xlsx", "tables": [], "confidence": 0.4}}
    x.th["span_q"] = [{"id": "span:q1", "text": "Is cash the administrator figure?", "assumed": "Yes"}]
    return "files read"


def boom(x):
    raise RuntimeError("the model is down")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    monkeypatch.setattr(H, "SYNC", True)
    monkeypatch.setattr(H.Ctx, "api", fake_api)
    monkeypatch.setitem(H.CHAINS, "A", ([("Span", "Read the files", stub_a)], "decision2"))
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    pw = {l.split()[0]: l.split()[1] for l in (data / "_control" / "seed_credentials.txt").read_text().splitlines() if l.strip()}
    c = TestClient(create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")))
    email = "anita.rao.evergreen@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c


def test_thread_decision_one_and_chain_to_decision_two(client):
    t = client.post("/api/v3/threads", json={"text": "Can we meet the capital calls?"}).json()
    assert t["stage"] == "decision1" and t["decision"]["brief"]["files"] == ["Administrator cash report", "Commitments schedule"]
    assert [e["kind"] for e in t["events"]] == ["person", "harbor", "harbor"]  # "Reading your question", then the brief
    t = client.post(f"/api/v3/threads/{t['id']}/decide", json={"n": 1, "answer": "confirm"}).json()
    assert t["stage"] == "decision2" and t["harbor_steps"] == 1
    d = t["decision"]
    assert d["n"] == 2 and {f["confidence"] for f in d["files"]} == {"high", "low"}
    assert [q["id"] for q in d["questions"]] == ["span:q1", "map:m2"]  # Span's question + the low-confidence mapping
    assert any(e["kind"] == "chips" for e in t["events"]) and client.get(f"/api/v3/threads/{t['id']}/workbench").json()["steps"][0]["ok"]
    assert client.post(f"/api/v3/threads/{t['id']}/decide", json={"n": 1, "answer": "confirm"}).status_code == 409


def test_a_failing_step_becomes_a_question_not_a_crash(client, monkeypatch):
    monkeypatch.setitem(H.CHAINS, "A", ([("Span", "Read the files", boom)], "decision2"))
    t = client.post("/api/v3/threads", json={"text": "x"}).json()
    t = client.post(f"/api/v3/threads/{t['id']}/decide", json={"n": 1, "answer": "confirm"}).json()
    assert t["stage"] == "question" and t["events"][-1]["kind"] == "question" and "model is down" in t["events"][-1]["text"]
    assert client.get("/api/v3/desk").json()["needs"][0]["kind"] == "question"
    monkeypatch.setitem(H.CHAINS, "A", ([("Span", "Read the files", stub_a)], "decision2"))
    assert client.post(f"/api/v3/threads/{t['id']}/say", json={"text": "try again"}).json()["stage"] == "decision2"


def test_a_dropped_file_is_recognised_and_the_desk_shape(client):
    tid = client.post("/api/v3/threads", json={"text": "Can we meet the capital calls?"}).json()["id"]
    data = base64.b64encode(b"entity,cash\nEG-B,1\n").decode()
    got = client.post("/api/v3/files", json={"name": "administrator_cash_2026-07.csv", "data": data}).json()["files"]
    client.post("/api/v3/files", json={"name": "holiday_photos.zip", "data": data})
    by = {f["name"]: f for f in client.get("/api/v3/files").json()["files"]}
    assert got[0]["status"] == "recognised" and by["administrator_cash_2026-07.csv"]["thread"] == tid
    assert by["holiday_photos.zip"]["status"] == "waiting"
    desk = client.get("/api/v3/desk").json()
    assert set(desk) == {"needs", "note", "threads", "files"} and desk["files"] == {"arrived": 2, "recognised": 1, "waiting": 1}
    assert desk["needs"][0] == {"kind": "decision", "thread": tid, "title": "Is this what you want?", "text": "Can we meet the capital calls?",
                                "actions": [{"label": "Confirm", "answer": "confirm"}, {"label": "Not yet", "answer": "not_yet"}]}
    assert desk["threads"][0]["needs"] == 1 and client.get("/api/v3/threads").json()["threads"][0]["id"] == tid


def _fake_x(tmp_path, files, api_calls, title="Can we meet the capital calls?"):
    import json
    from types import SimpleNamespace
    (tmp_path / "v3").mkdir(exist_ok=True)
    (tmp_path / "v3" / "files.json").write_text(json.dumps(files))
    plane = SimpleNamespace(path=lambda *p: tmp_path.joinpath(*p))
    th = {"id": "t-1", "pid": "prj-1", "title": title, "rules": [], "events": []}
    return SimpleNamespace(plane=plane, th=th, api=lambda who, method, path, body=None, **kw: api_calls.append((who, method, path, body)) or {})


def test_compare_turns_the_administrator_csv_into_benchmark_lines_when_no_benchmark_was_dropped(tmp_path):
    (tmp_path / "dropbox").mkdir()
    (tmp_path / "dropbox" / "administrator_cash_2026-07.csv").write_text(
        "as_of_date,entity_code,portfolio_code,currency,administrator_closing_cash,source,note\n"
        '2026-07-30,EG-B,EG-B-OPS,USD,"900,000.00",admin,\n'
        '2026-07-31,EG-HOLD,EG-GROWTH,USD,"2,305,906.48",admin,\n'
        '2026-07-31,EG-B,EG-B-OPS,USD,"905,000.00",admin,\n', encoding="utf-8")
    files = [{"name": "administrator_cash_2026-07.csv", "status": "recognised", "source": "Administrator cash statement", "thread": "t-1"}]
    calls: list = []
    x = _fake_x(tmp_path, files, calls)
    assert H.b_compare(x) == "compared with administrator_cash_2026-07.csv, 2 figures"
    assert calls[0][:3] == ("leo", "POST", "/api/v1/build/p/prj-1/builder/benchmark")
    assert calls[0][3] == {"name": "administrator_cash_2026-07.txt", "text": "Available cash EG-B 905,000.00\nAvailable cash EG-HOLD 2,305,906.48"}

    # a file that shares no word with the thread and is not a statement is not used
    files[0]["source"] = "Bank balances"
    calls.clear()
    assert H.b_compare(_fake_x(tmp_path, files, calls)) == "no report to compare with"
    assert calls == []


def test_the_morning_note_reads_the_liquidity_route_when_there_are_no_variance_lines(tmp_path):
    from types import SimpleNamespace
    calls: list = []

    def api(who, method, path, body=None, **kw):
        calls.append(path)
        if "/builder" in path:
            return {"round": {"variance": None, "run": {"run_id": "r1"}}}
        return {"entities": [{"entity_code": "EG-HOLD", "available_cash": "2,305,906.48", "buckets": [{"key": "30", "calls": "0"}]},
                             {"entity_code": "EG-B", "available_cash": "905,000.00", "buckets": [{"key": "30", "calls": "12,000.00"}]}]}
    x = SimpleNamespace(th={"title": "Capital calls covered", "pid": "prj-1"}, api=api)
    H.c_note(x)
    assert any("/api/v1/office/liquidity?currency=USD&as_of=" in p for p in calls)
    assert x.th["note"]["text"] == "Capital calls covered is live. 4 figures in the first note."
    assert x.th["note"]["figures"][1] == {"label": "Calls due in 30 days EG-HOLD", "value": "0", "change": ""}


def test_a_discarded_thread_leaves_the_desk_but_stays_on_record(client):
    tid = client.post("/api/v3/threads", json={"text": "Can we meet the capital calls?"}).json()["id"]
    r = client.post(f"/api/v3/threads/{tid}/discard", json={"reason": "Not what I meant"}).json()
    assert r["stage"] == "discarded" and r["events"][-1]["text"] == "Discarded: Not what I meant"
    assert client.get("/api/v3/desk").json()["needs"] == [] and client.get("/api/v3/threads").json()["threads"] == []
    assert client.get(f"/api/v3/threads/{tid}").json()["stage"] == "discarded"  # kept for the record
