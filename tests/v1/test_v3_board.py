"""Harbor 3.0 board, ask and note: empty board, the live thread's published board, Lumen's answer with trace and Used lines, the note and its history.
Real routes, store and permissions; the 2.0 dashboard read and the model are stubbed (synthetic data only)."""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_board_routes as B  # noqa: E402
from sh_platform.v1 import v3_harbor as H  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

TILE = {"id": "t-000001", "title": "Cash by entity", "state": "accepted", "spec": {"mark": "bar"}, "kpi": "cash", "note": "", "sql": "select 1"}
LIVE = {"id": "th-live", "title": "Capital calls", "stage": "live", "created": "2026-10-01T00:00:00Z", "pid": "EV-0003", "events": [],
        "steps": [{"n": 1, "agent": "Flow", "action": "Ran on a copy", "ok": True, "run_id": "run-77", "detail": ""}],
        "note": {"text": "Capital calls is live. 1 figures are in the first note.", "figures": [{"label": "Cash", "value": "4.14m", "change": "-0.2m"}]}}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    pw = {l.split()[0]: l.split()[1] for l in (data / "_control" / "seed_credentials.txt").read_text().splitlines() if l.strip()}
    c = TestClient(create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")))
    email = "anita.rao.evergreen@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c, PlaneStore(data).plane_for("evergreen")


def go_live(plane):
    H.save(plane, LIVE)


def test_board_is_empty_with_no_live_thread(env):
    c, _ = env
    assert c.get("/api/v3/board").json() == {"title": "", "as_at": "", "figures": [], "tiles": [], "empty": True}


def test_board_is_the_published_dashboard_of_the_live_thread(env, monkeypatch):
    c, plane = env
    go_live(plane)
    monkeypatch.setattr(B.S, "adopt", lambda p, pid: None)
    monkeypatch.setattr(B.D, "list_for", lambda p, v, pid: [{"id": "dash-1", "accepted": 1}])
    monkeypatch.setattr(B.D, "get_published", lambda p, v, pid, did: {"id": did, "title": "Liquidity", "published_at": "2026-10-13", "tiles": [TILE, TILE | {"id": "t-2", "state": "proposed"}]})
    monkeypatch.setattr(B.D, "_last_refresh", lambda p, pid: None)
    monkeypatch.setattr(B.D, "tile_rows", lambda p, pid, rec, tid: {"rows": [{"cash": 4.1}]})
    b = c.get("/api/v3/board").json()
    assert b["empty"] is False and b["title"] == "Liquidity" and b["as_at"] == "2026-10-13"
    assert [t["id"] for t in b["tiles"]] == ["t-000001"] and b["tiles"][0]["project_id"] == "EV-0003" and b["tiles"][0]["dashboard_id"] == "dash-1"
    assert "sql" not in b["tiles"][0]
    assert b["figures"] == [{"label": "Cash", "value": "4.14m", "change": "-0.2m", "source": "Run run-77 of Capital calls"}]


def test_a_tile_with_no_figure_is_a_no_data_line_not_a_tile(env, monkeypatch):
    c, plane = env
    go_live(plane)
    monkeypatch.setattr(B.S, "adopt", lambda p, pid: None)
    monkeypatch.setattr(B.D, "list_for", lambda p, v, pid: [{"id": "dash-1", "accepted": 1}])
    monkeypatch.setattr(B.D, "get_published", lambda p, v, pid, did: {"id": did, "title": "Liquidity", "tiles": [TILE, TILE | {"id": "t-2", "title": "Calls due"}]})
    monkeypatch.setattr(B.D, "_last_refresh", lambda p, pid: None)
    monkeypatch.setattr(B.D, "tile_rows", lambda p, pid, rec, tid: {"rows": [{"cash": 4.1}] if tid == "t-000001" else [{"cash": float("nan")}, {"cash": None}]})
    b = c.get("/api/v3/board").json()
    assert [t["id"] for t in b["tiles"]] == ["t-000001"]
    assert b["lines"] == ["Calls due: no data yet"]


class _Ctx:
    """The chain's context with the 2.0 routes answered from a dict: what c_lumen reads and writes, nothing else."""
    def __init__(self, answers):
        self.th, self.answers, self.calls = {"pid": "EV-0003", "iid": "ini-1"}, answers, []

    def api(self, who, method, path, body=None, soft=False):
        self.calls.append((who, method, path, body))
        return self.answers(method, path)


def test_starter_drops_tiles_with_no_figure_and_adds_the_thread_kpis():
    dash = "/api/v1/build/p/EV-0003/studio/dash-1"
    view = {"id": "dash-1", "rev": 3, "tiles": [{"id": "t-empty", "starter": True}, {"id": "t-ok", "starter": True}],
            "layout": {"rows": 2, "items": [{"id": "w-e", "kind": "lumen", "tile": "t-empty", "row": 0, "col": 0, "size": "small"},
                                            {"id": "w-o", "kind": "lumen", "tile": "t-ok", "row": 1, "col": 0, "size": "wide"}]},
            "library": {"tables": [{"name": "cash_movements", "columns": [{"name": "entity", "type": "VARCHAR"}, {"name": "cash_balance", "type": "DOUBLE"},
                                                                          {"name": "uncalled_commitments", "type": "DOUBLE"}, {"name": "value_date", "type": "DATE"}]}]}}
    def answers(method, path):
        if path.endswith("/starter"):
            return {"id": "dash-1"}
        if path.endswith("/tiles/t-empty/data"):
            return {"rows": [{"cash_balance": None}, {"cash_balance": float("nan")}]}
        if path.endswith("/tiles/t-ok/data"):
            return {"rows": [{"cash_balance": 4.1}]}
        if "/intents/" in path:
            return {"sow": {"kpis": [{"name": "Cash by entity"}, {"name": "Uncalled commitments"}]}}
        if method == "GET" and path == dash:
            return view
        return {}

    x = _Ctx(answers)
    assert H.c_lumen(x) == "Lumen starter board accepted and published"
    put = next(b for _, m, p, b in x.calls if m == "PUT")
    assert [i["id"] for i in put["items"]] == ["w-o"] and put["rows"] == 4 and put["rev"] == 3
    adds = [b for _, m, p, b in x.calls if m == "POST" and p.endswith("/widgets")]
    assert [(a["kind"], a["measure"], a["split"], a["row"]) for a in adds] == [("bar", "cash_balance", "entity", 2), ("figure", "uncalled_commitments", None, 3)]
    assert any(p.endswith("/starter/accept") for _, m, p, _ in x.calls)


def test_a_live_thread_with_nothing_published_is_empty(env, monkeypatch):
    c, plane = env
    go_live(plane)
    monkeypatch.setattr(B.S, "adopt", lambda p, pid: None)
    monkeypatch.setattr(B.D, "list_for", lambda p, v, pid: [])
    assert c.get("/api/v3/board").json()["empty"] is True


def test_ask_returns_the_answer_with_trace_and_used_lines(env, monkeypatch):
    c, plane = env
    from sh_platform.agents.runs import RunRegistry
    RunRegistry(plane).record_trace(trace_id="tr-1", run_id=None, agent="Lumen", status="done", elapsed_ms=5,
                                    steps=[{"kind": "tool", "tool": "read_table"}, {"kind": "guard", "numbers_replaced": 1}, {"kind": "model"}])
    def fake(plane_, viewer, agent, text, pid=None, model=None):
        B.teach._scope.get().used.append({"id": "b1", "title": "Span playbook", "passage": 2, "line": "Used: Span playbook, passage 2"})
        return {"reply": "13.1m is uncalled.", "rules_only": False, "trace_id": "tr-1"}
    monkeypatch.setattr(B.T, "ask", fake)
    r = c.post("/api/v3/ask", json={"text": "What's our dry powder?"}).json()
    assert r["answer"] == "13.1m is uncalled." and r["used"] == ["Used: Span playbook, passage 2"]
    assert [s["kind"] for s in r["trace"]] == ["tool", "guard", "model"]
    assert r["trace"][1]["label"] == "Checked every number against the data; 1 could not be checked and was left out"
    assert c.post("/api/v3/ask", json={"text": "  "}).status_code == 400


def test_ask_with_the_model_off_still_answers_in_plain_words(env):
    c, _ = env
    r = c.post("/api/v3/ask", json={"text": "What is the net worth?"})
    assert r.status_code == 200 and r.json()["answer"] and r.json()["used"] == [] and isinstance(r.json()["trace"], list)


def test_note_falls_back_to_the_thread_note_and_keeps_history(env, monkeypatch):
    c, plane = env
    go_live(plane)
    monkeypatch.setattr(B, "_from_k10", lambda p, v: None)
    plane.path("v3", "note_log.json").write_text(json.dumps({"2026-10-12": "Cash steady", "2026-10-13": "Trade unmatched"}), encoding="utf-8")
    n = c.get("/api/v3/note").json()
    assert n["text"].startswith("Capital calls is live") and n["figures"][0]["source"] == "Run run-77 of Capital calls"
    assert [h["at"] for h in n["history"]] == ["2026-10-13", "2026-10-12"]
    assert c.get("/api/v3/note").json()["history"] == n["history"]  # reading twice adds nothing to the past


def test_note_with_nothing_yet_is_empty_not_an_error(env, monkeypatch):
    c, _ = env
    monkeypatch.setattr(B, "_from_k10", lambda p, v: None)
    n = c.get("/api/v3/note").json()
    assert n["text"] == "" and n["figures"] == [] and n["history"] == []
