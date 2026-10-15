"""P2 Pulse: needs-you cards per person (seat waits, comments and tickets addressed to them), project lines gated by visibility,
worth-a-look gated by the facts' own routes; a damaged record never breaks it; the super admin is refused."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings
from sh_platform.v1 import p2_pulse

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
PID = "prj-0a1b2c3d"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("p2") / "data"
    shutil.copytree(ROOT / "data", data)
    from tools.reset_v1 import reset as _reset_v1
    _reset_v1(PlaneStore(data).plane_for("neera"))
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    plane = PlaneStore(str(data)).plane_for("neera")

    def put(rel: str, obj) -> None:
        p = plane.path(*rel.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")

    turn = {"id": "t1", "by": "person", "name": "Arjun Mehta", "text": "Monthly performance pack", "at": "2026-10-01T09:00:00+00:00"}
    put("intents/p2-talk/thread.json", {"intent_id": "p2-talk", "turns": [turn], "needs_done": ["goal"], "state": "open"})
    src = [{"id": "custodian", "name": "Custodian positions"}]
    put("intents/p2-built/sow.json", {"title": "Performance pack", "state": "signed", "sources": src})
    put("build/ops/loaded.json", {"periods": [{"period": "2026-09", "source_id": "custodian", "state": "loaded"}]})
    put(f"projects/{PID}.json", {"id": PID, "intent_id": "p2-built", "title": "Performance pack", "stage": "built", "artefacts": [],
                                 "people": {"raiser": "Arjun Mehta", "builder": "Leela Raman"}})
    put(f"projects/{PID}/comments.json", [
        {"id": "c1", "artefact": "design", "line_ref": "3.2", "by": "span", "to": "Arjun Mehta", "text": "Which custodian?", "state": "open",
         "at": "2026-10-03T08:00:00+00:00"},
        {"id": "c2", "artefact": "design", "line_ref": "4.1", "by": "span", "to": "Arjun Mehta", "text": "Month end?", "state": "open",
         "at": "2026-10-04T08:00:00+00:00"},
        {"id": "c3", "artefact": "build_pack", "line_ref": "7", "by": "watcher", "to": "Leela Raman", "text": "File late", "state": "open",
         "kind": "ticket", "at": "2026-10-05T08:00:00+00:00"},
        {"id": "c4", "artefact": "build_pack", "line_ref": "2", "by": "flow", "to": "Arjun Mehta", "text": "Done", "state": "resolved"},
        {"id": "c5", "artefact": "build_pack", "line_ref": None, "by": "Priya Nair", "to": "Leela Raman", "text": "Over to ops", "state": "open",
         "kind": "handover", "at": "2026-10-06T08:00:00+00:00"}])
    put("intents/p2-broken/sow.json", "{not json")
    put("signals/market.json", {"items": [{"kind": "market", "text": "Ten-year yield moved 30 basis points."}]})
    put("extractions/doc-statement-abc123.json", {"doc_id": "doc-statement-abc123", "status": "review", "file": "statement.md", "checks": []})
    p2_pulse._cache.clear()
    yield app
    mp.undo()


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    return c


def pulse(app, email):
    r = client(app, email).get("/api/v1/pulse")
    assert r.status_code == 200, r.text
    return r.json()


def test_each_person_sees_what_needs_them(app):
    a = pulse(app, "arjun.mehta.neera@example.test")
    assert all(a[b]["refreshed"] for b in ("needs_you", "projects", "worth_a_look"))
    kinds = {c["kind"] for c in a["needs_you"]["cards"]}
    assert {"thread", "comment"} <= kinds and "ticket" not in kinds  # X2's waits stay; Leela's ticket is not Arjun's
    c = next(c for c in a["needs_you"]["cards"] if c["kind"] == "comment")
    assert c["text"] == "2 comments on the system design need your answer." and c["href"].startswith(f"/centre/project/{PID}?artefact=design&line=3.2")
    line = next(l for l in a["projects"]["lines"] if l["intent_id"] == "p2-built")
    assert line["pid"] == PID and line["stage"] == "built" and line["open_comments"] == 2 and line["open_tickets"] == 1
    assert line["last_load"] == {"period": "2026-09", "state": "loaded", "reason": None}
    assert "p2-talk" in {l["intent_id"] for l in a["projects"]["lines"]}  # the decision maker reads projects still being talked through
    look = {i["kind"] for i in a["worth_a_look"]["items"]}
    assert {"market", "document"} <= look

    leela = pulse(app, "leela.raman.neera@example.test")  # analyst, builder on the project
    assert any(c["kind"] == "ticket" and "1 ticket on the build pack" in c["text"] for c in leela["needs_you"]["cards"])
    assert any(c["kind"] == "handover" and c["action"] == "Accept the hand-over" and c["href"] == "/centre/build/ops" for c in leela["needs_you"]["cards"])
    assert "p2-talk" not in {l["intent_id"] for l in leela["projects"]["lines"]}  # not signed, not hers


def test_a_participant_sees_only_what_their_routes_allow(app):
    dev = pulse(app, "dev.sharma.neera@example.test")  # consumer only
    assert {c["kind"] for c in dev["needs_you"]["cards"]} <= {"consume"}
    assert "p2-talk" not in {l["intent_id"] for l in dev["projects"]["lines"]}
    assert "document" not in {i["kind"] for i in dev["worth_a_look"]["items"]}  # the review queue is not a participant's


def test_fresh_is_empty_and_super_admin_is_refused(app):
    fresh = pulse(app, "nitin.fresh@example.test")
    assert fresh["needs_you"]["cards"] == [] and fresh["projects"]["lines"] == []
    assert client(app, "platform@example.test").get("/api/v1/pulse").status_code == 403
