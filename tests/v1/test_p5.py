"""P5 Ops daily state and tickets on a live Neera project: the Watcher raises one ticket per late
source per day to the builder as a build-pack comment of kind ticket, ops raises one by hand; a participant is refused."""
import json
import shutil
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.settings import Settings
from sh_platform.v1 import p5_handover

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
PID = "prj-0000abcd"


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data" / "_control", data / "_control")
    shutil.copytree(ROOT / "data" / "neera", data / "neera")
    from tools.reset_v1 import reset as _reset_v1
    from sh_platform.plane import PlaneStore as _PS
    _reset_v1(_PS(data).plane_for("neera"))
    neera = data / "neera"
    (neera / "intents" / "i-test").mkdir(parents=True)
    (neera / "intents" / "i-test" / "sow.json").write_text(json.dumps({"id": "s", "intent_id": "i-test", "sources": [{"id": "administrator_A2"}]}), encoding="utf-8")
    (neera / "projects").mkdir(exist_ok=True)
    (neera / "projects" / f"{PID}.json").write_text(json.dumps({"id": PID, "intent_id": "i-test", "title": "Test", "stage": "built",
                                                              "artefacts": [], "people": {"raiser": "Priya Nair"}}), encoding="utf-8")
    comments = []
    p1 = types.SimpleNamespace()
    p1.comment = lambda plane, pid, artefact, line_ref, by, to, text, kind="comment": comments.append((pid, artefact, line_ref, by, to, kind)) or {"id": f"c{len(comments)}"}
    p1.comments = lambda plane, pid, artefact=None: [{"id": c, "state": "open"} for c in ("c1", "c2")]
    monkeypatch.setattr(p5_handover, "_p1", lambda: p1)  # P1's comments, faked here so the test reads only P5
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}

    def client(email):
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
        return c
    return client, comments, neera


def test_daily_state_and_tickets(world):
    client, comments, neera = world
    leela, arjun = client("leela.raman.neera@example.test"), client("arjun.mehta.neera@example.test")
    rec = json.loads((neera / "projects" / f"{PID}.json").read_text(encoding="utf-8"))
    rec.update(stage="live", people={"raiser": "Priya Nair", "builder": "Leela Raman"})  # went live through G2 (tested in test_g2)
    (neera / "projects" / f"{PID}.json").write_text(json.dumps(rec), encoding="utf-8")
    assert arjun.post(f"/api/v1/ops/handover/{PID}").status_code in (404, 405)  # no hand-over offer any more

    arjun.get("/api/v1/ops"); arjun.get("/api/v1/ops")  # the Watcher: one ticket per source per day, however many reads
    assert comments == [(PID, "build_pack", "administrator_A2", "watcher", "Leela Raman", "ticket")]
    daily = json.loads((neera / "build" / "ops" / "daily.json").read_text(encoding="utf-8"))
    assert daily["projects"][PID]["state"] == "late"

    r = arjun.post("/api/v1/ops/tickets", json={"pid": PID, "source_id": "administrator_A2", "text": "Rows look short for September."})
    assert r.status_code == 200 and r.json()["to"] == "Leela Raman" and r.json()["comment_id"] == "c2"
    board = leela.get("/api/v1/ops/live", params={"iid": "i-test"}).json()["projects"]
    assert board[0]["stage"] == "live" and len(board[0]["tickets"]) == 2
    assert arjun.post("/api/v1/ops/tickets", json={"pid": "prj-nothere", "source_id": "x", "text": "y"}).status_code == 400


def test_participant_refused(world):
    client, _, _ = world
    c = client("dev.sharma.neera@example.test")
    assert c.post("/api/v1/ops/tickets", json={"pid": PID, "source_id": "x", "text": "y"}).status_code == 403
