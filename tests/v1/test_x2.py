"""X2 Home: each seat sees only what waits for it, built from the 1.0 records; a damaged record is skipped; the super admin is refused."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("x2") / "data"
    shutil.copytree(ROOT / "data", data)
    from tools.reset_v1 import reset as _reset_v1  # the live Neera may hold a walk's records; the test starts from the company's files
    from sh_platform.plane import PlaneStore as _PS
    _reset_v1(_PS(data).plane_for("neera"))
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    plane = PlaneStore(str(data)).plane_for("neera")

    def put(rel: str, obj) -> None:
        p = plane.path(*rel.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")

    turn = {"id": "t1", "by": "person", "name": "Arjun Mehta", "text": "Monthly performance pack", "at": "2026-10-01T09:00:00+00:00"}
    put("intents/x2-talk/thread.json", {"intent_id": "x2-talk", "turns": [turn], "needs_done": ["goal", "kpis"], "state": "open"})
    put("intents/x2-ready/thread.json", {"intent_id": "x2-ready", "turns": [turn], "needs_done": [], "state": "sow_ready"})
    put("intents/x2-ready/sow.json", {"title": "Fee ratio", "state": "draft", "unclear": [{"id": "u1", "settled": False}]})
    src = [{"id": "custodian", "name": "Custodian positions"}, {"id": "gl", "name": "General ledger"}]
    put("intents/x2-built/sow.json", {"title": "Performance pack", "state": "signed", "sources": src})
    put("intents/x2-built/room_state.json", {"stage": "loads", "waiting_on": "Flow", "since": "2026-10-02T08:00:00+00:00"})
    put("build/scan/x2-built.json", {"intent_id": "x2-built", "kpis": [{"code": "TWR", "status": "available"}, {"code": "CD", "status": "not"}],
                                     "agreed": {"by": "Arjun Mehta", "at": "2026-10-02", "scope": ["TWR"]}})
    put("build/mapping/x2-built.json", {"rows": [{"n": 1, "status": "mapped"}, {"n": 2, "status": "unclear"}]})
    put("build/ops/loaded.json", {"periods": [{"period": "2026-09", "source_id": "custodian", "state": "loaded"}]})
    put("intents/x2-broken/sow.json", "{not json")
    yield app
    mp.undo()


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    return c


def kinds(home, iid):
    return {w["kind"] for w in home["waiting"] if w["intent_id"] == iid}


def test_each_seat_sees_its_own_waits(app):
    arjun = client(app, "arjun.mehta.neera@example.test").get("/api/v1/home")
    assert arjun.status_code == 200, arjun.text
    h = arjun.json()
    assert h["may_start"] and {s["id"] for s in h["seats"]} >= {"decision_maker", "architect", "ops_manager"}
    assert kinds(h, "x2-talk") == {"thread"} and kinds(h, "x2-ready") == {"sign"}
    assert "1 unclear point" in next(w["text"] for w in h["waiting"] if w["kind"] == "sign")
    assert kinds(h, "x2-built") == {"mapping", "loaded", "consume"}  # loads started (one period confirmed), so no "run the loads"
    assert "General ledger" in next(w["text"] for w in h["waiting"] if w["kind"] == "loaded")
    built = next(i for i in h["intents"] if i["id"] == "x2-built")
    assert built["stage"] == "Loaded" and built["nira"] == "Nira: waiting on Flow since 2 October 2026"
    assert "x2-broken" in {i["id"] for i in h["intents"]}  # a damaged record is a line with nothing waiting, never a 500

    leela = client(app, "leela.raman.neera@example.test").get("/api/v1/home").json()  # analyst: architect, engineer, ops, consumer
    assert leela["may_start"] and kinds(leela, "x2-ready") == set() and "mapping" in kinds(leela, "x2-built")

    dev = client(app, "dev.sharma.neera@example.test").get("/api/v1/home").json()  # participant: consumer only
    assert [s["id"] for s in dev["seats"]] == ["consumer"] and {w["kind"] for w in dev["waiting"]} == {"consume"}


def test_fresh_is_empty_and_super_admin_is_refused(app):
    fresh = client(app, "nitin.fresh@example.test").get("/api/v1/home")
    assert fresh.status_code == 200 and fresh.json()["waiting"] == []
    assert client(app, "platform@example.test").get("/api/v1/home").status_code == 403
