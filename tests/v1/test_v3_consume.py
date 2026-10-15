"""Harbor 3.0 Consume: the ask cache (miss, hit, version change), golden pre-compute, and the GET /api/v3/consume shape. Synthetic data only."""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_board_routes as B  # noqa: E402
from sh_platform.v1 import v3_consume as C  # noqa: E402
from sh_platform.v1 import v3_harbor as H  # noqa: E402
from sh_platform.v1 import v3_skills  # noqa: E402
from sh_platform.v1 import k6_liquidity as K  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

REAL_ASK = B._ask

LIVE = {"id": "th-live", "title": "Capital calls", "stage": "live", "created": "2026-10-01T00:00:00Z", "pid": "EV-0003", "events": [],
        "steps": [{"n": 1, "at": "2026-10-01T06:00:00Z", "agent": "Flow", "action": "Went live", "ok": True, "run_id": "run-77", "detail": ""}],
        "note": {"text": "Capital calls is live. 1 figures are in the first note.", "figures": [{"label": "Cash", "value": "4.14m", "change": "-0.2m"}]}}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    C.KEPT.clear()
    C.PRE.clear()
    calls = []
    monkeypatch.setattr(B, "_ask", lambda plane, viewer, text, pid: calls.append(text) or {"answer": "Cash is 4.14m.", "trace": [{"kind": "guard", "label": "Checked"}], "used": []})
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    pw = {l.split()[0]: l.split()[1] for l in (data / "_control" / "seed_credentials.txt").read_text().splitlines() if l.strip()}
    c = TestClient(create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")))
    email = "anita.rao.evergreen@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c, PlaneStore(data).plane_for("evergreen"), calls


def test_a_miss_then_a_hit_is_instant_and_marked_cached(env):
    c, plane, calls = env
    H.save(plane, LIVE)
    first = c.post("/api/v3/ask", json={"text": "What is our cash?"}).json()
    assert first["cached"] is False and first["answer"] == "Cash is 4.14m." and first["figure"]["value"] == "4.14m" and first["as_of"] == "2026-10-01T06:00:00Z"
    hit = c.post("/api/v3/ask", json={"text": "  what IS our cash??"}).json()  # same question once normalised
    assert hit["cached"] is True and hit["ms"] < 50 and hit["trace"] == first["trace"] and hit["answer"] == first["answer"]
    assert calls == ["What is our cash?"]


def test_a_new_live_run_invalidates_the_kept_answers(env):
    c, plane, calls = env
    H.save(plane, LIVE)
    c.post("/api/v3/ask", json={"text": "What is our cash?"})
    H.save(plane, LIVE | {"steps": LIVE["steps"] + [{"n": 2, "at": "2026-10-02T06:00:00Z", "agent": "Flow", "action": "Ran", "ok": True, "run_id": "run-78", "detail": ""}]})
    again = c.post("/api/v3/ask", json={"text": "What is our cash?"}).json()
    assert again["cached"] is False and len(calls) == 2 and again["as_of"] == "2026-10-02T06:00:00Z"


def test_precompute_answers_the_most_asked_once_per_version(env):
    c, plane, calls = env
    H.save(plane, LIVE)
    c.post("/api/v3/ask", json={"text": "Dry powder?"})
    C.KEPT.clear()
    calls.clear()
    viewer = type("V", (), {"account_id": None, "name": "x"})()  # a different viewer's keys are separate, so warm for the signed-in one below
    assert C.precompute(plane, viewer, lambda q: lambda: {"answer": "13.1m", "trace": [], "used": []}) == 5  # the asked one and the four golden
    assert C.precompute(plane, viewer, lambda q: lambda: {"answer": "13.1m", "trace": [], "used": []}) == 0


def _bucket(key, calls):
    return {"key": key, "calls": calls, "distributions": 0, "cash_after_calls": None, "items": []}


def _ent(code, name, cash, c30="0", c60="0", unc=0, dated="2026-07-31"):
    return {"entity_code": code, "entity_name": name, "available_cash": Decimal(cash), "uncalled": Decimal("44000000"), "unconfirmed": [{}] * unc,
            "cash_sources": [{"position_date": dated}], "buckets": [_bucket("overdue", 0), _bucket("30", Decimal(c30)), _bucket("60", Decimal(c60)), _bucket("90", 0)]}


JULY = [_ent("EG-HOLD", "Evergreen Holdings", "2305906.48"), _ent("EG-TRUST", "Evergreen Family Trust", "1252492.34", dated="2026-07-28"), _ent("EG-B", "Entity B", "905000.00")]


@pytest.fixture()
def july(env, monkeypatch):
    monkeypatch.setattr(C, "latest_day", lambda plane: date(2026, 7, 31))
    monkeypatch.setattr(K, "forecast", lambda plane, day, cutoff=None, viewer=None, currency=None: {"as_of": day.isoformat(), "entities": JULY})
    monkeypatch.setattr(B, "_ask", REAL_ASK)
    return env


def test_cash_by_entity_comes_from_the_tool_fast_with_the_july_figures(july):
    c, plane, _ = july
    H.save(plane, LIVE)
    got = c.post("/api/v3/ask", json={"text": "What is our cash by entity today?"}).json()
    assert got["ms"] < 1000 and got["figure"]["value"] == "4,463,398.82"
    assert [r["value"] for r in got["rows"]] == ["2,305,906.48", "1,252,492.34", "905,000.00"]
    assert got["source"] == "Bank statements and administrator, as at 31 Jul 2026 · run run-77" and "not tracked" not in got["answer"]
    assert "uncalled" not in got["answer"].lower()
    assert c.post("/api/v3/ask", json={"text": "what is our cash by entity today"}).json()["cached"] is True
    assert any(r["skill"] == "consume.answer-question" for r in v3_skills.runs(plane))


def test_other_liquidity_questions(july):
    c, plane, _ = july
    ask = lambda q: c.post("/api/v3/ask", json={"text": q}).json()  # noqa: E731
    assert ask("Which entity has the least cash?")["figure"]["value"] == "905,000.00"
    assert ask("How much cash does Entity B have?")["figure"]["value"] == "905,000.00"
    calls = ask("What calls are due in the next 30 days?")
    assert calls["figure"]["value"] == "None" and "No capital calls" in calls["answer"]
    assert "Yes" in ask("Can each entity meet its calls?")["answer"]


def test_a_question_that_is_not_liquidity_falls_back(july, monkeypatch):
    c, plane, _ = july
    monkeypatch.setattr(B, "_ask", lambda plane, viewer, text, pid: {"answer": "Lumen says 5.", "trace": [], "used": []} if C.liquidity_answer(plane, viewer, text) is None else {})
    assert C.liquidity_answer(plane, None, "What is the net worth?") is None
    assert c.post("/api/v3/ask", json={"text": "Tell me about the Harborview fund"}).json()["answer"] == "Lumen says 5."


def test_consume_on_an_empty_company(env):
    c, _, _ = env
    got = c.get("/api/v3/consume").json()
    assert got["as_of"] is None and got["figures"] == [] and got["watchlist"] == [] and got["boards"] == [] and got["note"] is None and got["reports"] == [] and got["answer"] is None
    assert set(got) == {"office", "as_of", "figures", "watchlist", "boards", "note", "reports", "golden", "answer"}


def test_consume_on_a_seeded_company(july):
    c, plane, _ = july
    H.save(plane, LIVE)
    got = c.get("/api/v3/consume").json()
    assert got["as_of"] == "2026-07-31"
    by = {f["label"]: f["value"] for f in got["figures"]}
    assert by["Total cash"] == "4,463,398.82" and by["Calls due in 30 days"] == "None" and by["Cash · Entity B"] == "905,000.00"
    assert [w["value"] for w in got["watchlist"]] == ["2,305,906.48", "1,252,492.34", "905,000.00"]
    assert [w["stale"] for w in got["watchlist"]] == [False, True, False]  # the trust's cash is dated 28 Jul, the rest 31 Jul
    assert "worth" not in got["note"]["headline"] and "4,463,398.82" in got["note"]["headline"] and got["reports"][0]["href"].startswith("/api/v1/projects/EV-0003/")
    assert got["golden"][0]["q"] == "What is our cash by entity today?" and got["answer"]["q"] == got["golden"][0]["q"] and got["answer"]["rows"]
    assert "uncalled" not in str(got).lower()
