"""P3 the Build Centre entry on a tmp copy of the data: a signed intent waits for a builder, the architect picks it up (recorded on
the P1 project record, made for an intent that has none), a second pick-up and a sponsor's pick-up are refused."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
LEELA, PRIYA = "leela.raman.neera@example.test", "priya.nair.neera@example.test"
A, B = "int-p3a", "int-p3b"


def _put(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data", data)
    neera = data / "neera"
    for iid in (A, B):
        _put(neera / "intents" / iid / "sow.json", {"id": f"sow-{iid}", "intent_id": iid, "title": f"Pack {iid}", "state": "signed", "version": 1,
                                                    "kpis": [], "signature": {"name": "Arjun Mehta", "role": "company_admin", "at": "2026-10-07T10:00:00Z"}})
    _put(neera / "projects" / "prj-0000beef.json", {"id": "prj-0000beef", "intent_id": B, "title": "Pack B", "stage": "signed", "artefacts": [],
                                                   "people": {"raiser": "Arjun Mehta", "builder": None}})
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}

    def client(email):
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
        return c
    return neera, client


def _ids(rows):
    return {r["intent_id"] for r in rows}


def test_pickup_moves_work_from_waiting_to_in_build(world):
    neera, client = world
    leela = client(LEELA)
    got = leela.get("/api/v1/build/waiting").json()
    assert {A, B} <= _ids(got["waiting"]) and not ({A, B} & _ids(got["in_build"]))
    got_a = leela.post(f"/api/v1/build/pickup/{A}").json()  # no project yet: P1 makes one for the older intent
    assert got_a["builder"] == "Leela Raman" and got_a["pid"].startswith("prj-")
    assert json.loads((neera / "projects" / f"{got_a['pid']}.json").read_text())["people"]["builder"] == "Leela Raman"
    assert leela.post(f"/api/v1/build/pickup/{B}").json()["pid"] == "prj-0000beef"
    assert json.loads((neera / "projects" / "prj-0000beef.json").read_text())["people"]["builder"] == "Leela Raman"
    assert not (neera / "build" / "pickup" / f"{B}.json").exists()
    got = leela.get("/api/v1/build/waiting").json()
    assert {A, B} <= _ids(got["in_build"]) and not ({A, B} & _ids(got["waiting"]))


def test_refuses_a_second_pickup_a_sponsor_and_an_unsigned_intent(world):
    _, client = world
    leela = client(LEELA)
    assert leela.post(f"/api/v1/build/pickup/{A}").status_code == 200
    assert leela.post(f"/api/v1/build/pickup/{A}").status_code == 409
    assert leela.post("/api/v1/build/pickup/int-nothere").status_code == 404
    assert client(PRIYA).post(f"/api/v1/build/pickup/{B}").status_code == 403
