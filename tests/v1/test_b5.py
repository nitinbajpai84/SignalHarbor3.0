"""B5 Ops and Loaded: Leela (analyst) reads ops on Neera, Loaded is recorded; a participant is refused."""
import json
import shutil
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data" / "_control", data / "_control")
    shutil.copytree(ROOT / "data" / "neera", data / "neera")
    from tools.reset_v1 import reset as _reset_v1  # the live Neera may hold a walk's records; the test starts from the company's files
    from sh_platform.plane import PlaneStore as _PS
    _reset_v1(_PS(data).plane_for("neera"))
    sow = data / "neera" / "intents" / "i-test" / "sow.json"
    sow.parent.mkdir(parents=True)
    sow.write_text(json.dumps({"id": "s", "intent_id": "i-test", "sources": [{"id": "administrator_A2", "name": "Administrator A2"}]}), encoding="utf-8")
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}

    def client(email):
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
        return c
    return client, data


def test_ops_and_loaded(world):
    client, data = world
    c = client("leela.raman.neera@example.test")
    ops = c.get("/api/v1/ops").json()
    a2 = next(s for s in ops["sources"] if s["source_id"] == "administrator_A2")
    assert a2["state"] == "late" and a2["rows"] is not None
    assert any(a["id"] == "administrator_A2:late" for a in ops["alerts"])

    r = c.post("/api/v1/ops/loaded", json={"period": ops["period"], "source_id": "administrator_A2", "state": "loaded"})
    assert r.status_code == 200 and r.json()["by"] == "Leela Raman"
    c.post("/api/v1/ops/loaded", json={"period": ops["period"], "source_id": "administrator_A2", "state": "not_loaded", "reason": "file short"})
    saved = json.loads((data / "neera" / "build" / "ops" / "loaded.json").read_text(encoding="utf-8"))["periods"]
    assert [(p["state"], p["reason"]) for p in saved] == [("not_loaded", "file short")]  # one act per period and source
    assert c.post("/api/v1/ops/loaded", json={"period": "Sept", "source_id": "x", "state": "loaded"}).status_code == 400
    assert c.post("/api/v1/ops/loaded", json={"period": "2026-09", "source_id": "x", "state": "not_loaded"}).status_code == 400


def test_participant_refused(world):
    client, _ = world
    c = client("dev.sharma.neera@example.test")
    assert c.get("/api/v1/ops").status_code == 403
    r = c.post("/api/v1/ops/loaded", json={"period": "2026-09", "source_id": "x", "state": "loaded"})
    assert r.status_code == 403 and r.json().get("error") != "csrf"
