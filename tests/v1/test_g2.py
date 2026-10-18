"""G2 Go live and the run book: the project owner (raiser or sponsor) goes live; refused while the build pack is unsigned or a comment is
open; on go live the stage is live and Flow drafts the run book; the ops manager edits and signs it, refused while a comment on it is
unresolved; a participant cannot draft it."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings
from sh_platform.v1 import p1_project as P1
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
CREDS = SEED / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
IID = "g2test"


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(SEED / "_control", data / "_control")
    shutil.copytree(SEED / "neera", data / "neera")
    from tools.reset_v1 import reset as _reset_v1
    plane = PlaneStore(data).plane_for("neera")
    _reset_v1(plane)
    co = data / "neera"
    (co / "intents" / IID).mkdir(parents=True)
    (co / "intents" / IID / "sow.json").write_text(json.dumps({"intent_id": IID, "state": "signed", "title": "G2", "kpis": [],
                                                              "sources": [{"id": "g2src", "name": "Positions", "owner": "Arjun Mehta"}]}), encoding="utf-8")
    (co / "build" / "mapping").mkdir(parents=True, exist_ok=True)
    (co / "build" / "mapping" / f"{IID}.json").write_text(json.dumps({"intent_id": IID, "version": 1, "rows": [
        {"n": 1, "layer": "silver", "target_table": "silver.positions", "target_field": "value", "source_id": "g2src", "source_table": "positions",
         "source_field": "value", "transformation": "as is", "rule": "", "test": "Not empty.", "status": "mapped"}]}), encoding="utf-8")
    pid = P1.create_project(plane, IID, "G2 project", "Arjun Mehta")["id"]
    P1.set_person(plane, pid, "sponsor", "Priya Nair")
    P1.set_person(plane, pid, "builder", "Leela Raman")
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}

    def client(who):
        c = TestClient(app)
        email = f"{who}.neera@example.test"
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
        return c
    return client, plane, pid, co


def test_go_live_and_run_book(world):
    client, plane, pid, co = world
    arjun, leela, dev = client("arjun.mehta"), client("leela.raman"), client("dev.sharma")
    go = f"/api/v1/projects/{pid}/go-live"
    r = leela.post(go)
    assert r.status_code == 409 and "Only Arjun Mehta or Priya Nair" in r.json()["message"]  # not the owner
    r = arjun.post(go)
    assert r.status_code == 409 and "build pack is not signed" in r.json()["message"]

    P1.signed(plane, pid, "build_pack", "Leela Raman")
    c = P1.comment(plane, pid, "build_pack", "1.1", "flow", "Arjun Mehta", "Which month is meant?")
    r = arjun.post(go)
    assert r.status_code == 409 and "still open" in r.json()["message"]
    assert arjun.post(f"/api/v1/projects/{pid}/comments/{c['id']}/answer", json={"text": "September"}).status_code == 200
    P1.resolve(plane, pid, c["id"], "flow")

    verify = co / "build" / "verify"
    verify.mkdir(parents=True, exist_ok=True)
    (verify / f"{IID}.json").write_text(json.dumps([{"code": "K01", "period": "2026-09", "expected": 10, "got": 7, "tolerance": 1, "met": False}]), encoding="utf-8")
    r = arjun.post(go)  # a benchmark miss nobody answered and resolved stops go live, even with the build pack signed
    assert r.status_code == 409 and "K01" in r.json()["message"]
    (verify / f"{IID}.json").write_text("[]", encoding="utf-8")

    r = arjun.post(go)
    assert r.status_code == 200, r.text
    assert P1.read(plane, pid)["stage"] == "live" and arjun.post(go).status_code == 409  # live once

    doc = leela.get(f"/api/v1/projects/{pid}/artefacts/run_book").json()
    assert doc["sections"][0]["heading"] == "1. Sources and arrival" and doc["state"] == "draft"
    assert any("Positions" in ln["text"] for ln in doc["sections"][0]["lines"]) and any("Leela Raman" in ln["text"] for ln in doc["sections"][3]["lines"])

    q = P1.comment(plane, pid, "run_book", "3.1", "Leela Raman", "builder", "What does Not empty mean for value?")
    r = leela.post(f"/api/v1/projects/{pid}/run-book/sign")
    assert r.status_code == 409 and "not resolved" in r.json()["message"]
    P1.answer(plane, pid, q["id"], "Leela Raman", "Every row has a value.")  # the builder is Leela in this fixture
    P1.resolve(plane, pid, q["id"], "Leela Raman")
    r = leela.put(f"/api/v1/projects/{pid}/run-book", json={"sections": [{"lines": ["Positions arrive by working day 5."]}, {"lines": []}, {"lines": []}, {"lines": ["Call Leela."]}]})
    assert r.status_code == 200 and r.json()["version"] == 1
    assert leela.post(f"/api/v1/projects/{pid}/run-book/sign").status_code == 200
    art = next(a for a in P1.read(plane, pid)["artefacts"] if a["kind"] == "run_book")
    assert art["state"] == "signed" and art["signed_by"] == "Leela Raman" and P1.read(plane, pid)["people"]["ops"] == "Leela Raman"
    assert leela.put(f"/api/v1/projects/{pid}/run-book", json={"sections": [{"lines": ["x"]}] * 4}).json()["state"] == "draft"  # an edit reopens it

    assert dev.post(f"/api/v1/projects/{pid}/run-book/draft").status_code == 403
    assert dev.post(f"/api/v1/ops/handover/{pid}/accept").status_code in (404, 405)  # no hand-over any more
