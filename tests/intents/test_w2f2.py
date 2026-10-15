"""W2F2: closed intents read as closed. On a temporary copy of the demo data: a seeded closed brainstorm (closed before the rating window was
written) offers the rating form to its participants and advisers until they rate or waive, an affected person cannot note, follow or tap a
closed intent, and the organiser's "Start the Initiative" (POST /next) writes the pre-filled draft. Synthetic Ardmore data only."""
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.intents import ratings
from sh_platform.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
B2 = "bra-bcc4ae29aab07293ba2015983f28126c"  # "Cut manual work on private fund capital calls", closed 2 Oct, no rating window
EMAIL = "{}.ardmore@example.test"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    if not CREDS.is_file() or not (ROOT / "data" / "ardmore" / "intents" / B2).is_dir():
        pytest.skip("no seeded demo data")
    data = tmp_path_factory.mktemp("w2f2") / "data"
    shutil.copytree(ROOT / "data", data, ignore=shutil.ignore_patterns("*.duckdb", "*.duckdb.wal"))
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    pw = {line.split()[0]: line.split()[1] for line in CREDS.read_text().splitlines() if line.strip() and not line.startswith("#")}

    def login(who: str) -> TestClient:
        c = TestClient(app, raise_server_exceptions=False)
        assert c.post("/api/auth/login", json={"email": EMAIL.format(who), "password": pw[EMAIL.format(who)]}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
        return c
    return login


def test_legacy_window_derived_from_closing_date():
    closed = datetime.now(timezone.utc) - timedelta(days=1)
    rec = {"type": "brainstorm", "state": "closed", "closure": {"closed_at": closed.isoformat()}}
    r = ratings.field(rec, "rating")
    assert r and r["rated"] == [] and datetime.fromisoformat(r["drop_at"]) == closed + timedelta(days=ratings.LEGACY_DAYS)
    assert ratings.window_open(rec, datetime.now(timezone.utc))
    assert ratings.field({**rec, "type": "pulse"}, "rating") is None and ratings.field({**rec, "state": "open"}, "rating") is None


def test_participant_and_adviser_rate_until_they_rate_or_waive(world):
    if datetime.now(timezone.utc) > datetime(2026, 10, 2, 5, tzinfo=timezone.utc) + timedelta(days=ratings.LEGACY_DAYS):
        pytest.skip("the seeded window has passed")
    siew, ben, priya, tomoko = (world(w) for w in ("siew.ling.ho", "benjamin.ho", "priya.raman", "tomoko.hayashi"))
    for c in (siew, ben, priya):
        r = c.get(f"/api/intents/{B2}/closure").json()["rating"]
        assert r and r["can_rate"] is True, r
    assert siew.post(f"/api/intents/{B2}/ratings", json={"score": 4, "note": "", "anonymous": True}).status_code == 200
    after = siew.get(f"/api/intents/{B2}/closure").json()["rating"]
    assert after["can_rate"] is False and after["mine"]["score"] == 4
    assert siew.post(f"/api/intents/{B2}/ratings", json={"score": 5, "anonymous": True}).status_code == 409
    assert ben.post(f"/api/intents/{B2}/rating/waive").status_code == 200
    w = ben.get(f"/api/intents/{B2}/closure").json()["rating"]
    assert w["waived"] is True and w["can_rate"] is False
    s = tomoko.get(f"/api/intents/{B2}/closure").json()["rating"]["summary"]  # five seeded anonymous ratings plus Siew Ling's
    assert s["count"] == 6 and s["rated"] == 6 and s["anonymous_count"] == 6 and s["signed"] == []


def test_affected_person_cannot_note_follow_or_tap_a_closed_intent(world):
    jia = world("jia.hao.lee")
    assert jia.get(f"/api/intents/{B2}/notes").json()["state"] == "closed"
    for path, body in (("notes", {"text": "W2F2 a note", "signed": True}), ("follow", {"follow": True})):
        r = jia.post(f"/api/intents/{B2}/{path}", json=body)
        assert r.status_code == 409, (path, r.text)
    assert jia.post(f"/api/intents/{B2}/join-requests", json={"asked_role": "participant", "reason": "W2F2"}).status_code == 409


def test_organiser_starts_the_initiative_from_the_chosen_idea(world):
    tomoko = world("tomoko.hayashi")
    c = tomoko.get(f"/api/intents/{B2}/closure").json()
    assert c["you"]["organiser"] and any(n["kind"] == "initiative" and not n.get("ref") for n in c["next"])
    r = tomoko.post(f"/api/intents/{B2}/next", json={})
    assert r.status_code == 200, r.text
    made = [x["target"] for x in r.json()["created"] if x["target"]["kind"] == "initiative"]
    assert len(made) == 1
    child = tomoko.get(f"/api/intents/{made[0]['id']}").json()
    assert child["state"] == "draft" and child["links"]["from"] == B2
    after = tomoko.get(f"/api/intents/{B2}/closure").json()
    assert next(n for n in after["next"] if n["kind"] == "initiative")["ref"] == made[0]["id"]  # a second press has nothing to start
