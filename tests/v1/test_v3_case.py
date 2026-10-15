"""Harbor 3.0 case: the addendum shape, act (note, timing, close with a required reason), and a drafted email that is never sent."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    data = tmp_path / "data"
    data.mkdir()
    EG.seed(data)
    pw = {l.split()[0]: l.split()[1] for l in (data / "_control" / "seed_credentials.txt").read_text().splitlines() if l.strip()}
    c = TestClient(create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")))
    email = "grace.ong.evergreen@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c


def new_case(c, title="Trade T-005 is not at the administrator"):
    r = c.post("/api/v1/cases", json={"exception_type": "trade_mismatch", "title": title, "materiality_status": "below_threshold",
                                      "candidate_impact_amount": 592000, "impact_currency": "USD"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_case_has_the_addendum_shape_and_an_unsent_draft(client):
    cid = new_case(client)
    c = client.get(f"/api/v3/cases/{cid}").json()
    for k in ("id", "title", "status", "owner", "due", "thread", "what", "evidence", "steps", "history"):
        assert k in c
    assert c["status"] == "open" and c["title"].startswith("Trade T-005") and c["history"][0]["text"].startswith("Case opened")
    assert [s["answer"] for s in c["steps"]] == ["ask", "timing", "note"]
    assert c["draft"]["sent"] is False and "592,000" in c["draft"]["body"]


def test_ask_only_records_the_draft_and_note_needs_text(client):
    cid = new_case(client)
    c = client.post(f"/api/v3/cases/{cid}/act", json={"answer": "ask"}).json()
    assert "Nothing was sent" in c["history"][-1]["text"] and c["draft"]["sent"] is False and c["status"] == "open"
    assert client.post(f"/api/v3/cases/{cid}/act", json={"answer": "note"}).status_code == 400
    c = client.post(f"/api/v3/cases/{cid}/act", json={"answer": "note", "reason": "Called the administrator."}).json()
    assert c["history"][-1]["text"] == "Called the administrator."


def test_closing_needs_a_reason_and_timing_closes_with_its_own(client):
    cid = new_case(client)
    assert client.post(f"/api/v3/cases/{cid}/act", json={"answer": "resolved"}).status_code == 400
    assert client.post(f"/api/v3/cases/{cid}/act", json={"answer": "bogus"}).status_code == 400
    r = client.post(f"/api/v3/cases/{cid}/act", json={"answer": "resolved", "reason": "Booked on the 3rd."})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["status"] == "closed" and c["steps"] == [] and c["draft"] is None and c["history"][-1]["text"] == "Booked on the 3rd."
    t = new_case(client, "Trade T-006")
    c = client.post(f"/api/v3/cases/{t}/act", json={"answer": "timing"}).json()
    assert c["status"] == "closed" and "timing difference" in c["history"][-1]["text"]


def test_unknown_case_is_a_plain_404(client):
    assert client.get("/api/v3/cases/nope").status_code in (403, 404)
