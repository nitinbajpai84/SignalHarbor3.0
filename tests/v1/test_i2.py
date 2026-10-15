"""I2 North's thread: the decision maker starts an intent and answers North to a ready SOW (model off, labelled); a model reply
drafts through the runtime; an analyst may read the thread but not write to it."""
import base64
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.agents.protocols import ModelReply
from sh_platform.app import create_app
from sh_platform.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("i2") / "data"
    shutil.copytree(ROOT / "data", data)
    a = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    a.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    yield a
    mp.undo()


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_thread_to_ready_sow_with_the_model_off(app):
    c = client(app, "arjun.mehta.neera@example.test")
    r = c.post("/api/v1/intents", json={"line": "Monthly performance pack net of fees"})
    assert r.status_code == 200, r.text
    iid = r.json()["id"]
    t = c.get(f"/api/v1/intents/{iid}/thread").json()
    assert t["turns"][-1]["by"] == "north" and t["turns"][-1]["need"] == "goal" and t["turns"][-1]["name"] == "North (rules only)"
    assert t["sow"]["goal"]["line"] == "Monthly performance pack net of fees" and t["sow"]["state"] == "draft"

    csv = b"date,account,value\n2026-09-30,A1,100\n"
    f = c.post(f"/api/v1/intents/{iid}/thread/files", json={"name": "positions.csv", "data": base64.b64encode(csv).decode(), "kind": "sample"})
    assert f.status_code == 200, f.text
    assert f.json() == {"name": "positions.csv", "path": "landing/positions/positions.csv", "kind": "sample"}
    assert (Path(app.state.settings.data_root) / "neera" / "landing" / "positions" / "positions.csv").is_file()

    said = [
        ("Why: the committee needs returns after fees\nReaders: Priya Nair, the committee\nNeeded by: 2026-11-30", []),
        ("Leela pulls the custodian file. Arjun checks the figures and signs the pack.", []),
        ("", [f.json()]),                                               # a dropped file answers the inputs need
        ("Time-weighted return: growth of the portfolio net of fees; Concentration", []),
        ("Only the committee may see client figures. Keep statements seven years.", []),
        ("Who owns the benchmark choice is not settled", []),
    ]
    for text, files in said:
        r = c.post(f"/api/v1/intents/{iid}/thread", json={"text": text, "files": files})
        assert r.status_code == 200, r.text
    t = r.json()
    assert t["state"] == "sow_ready" and t["needs_done"] == ["goal", "process", "inputs", "kpis", "rules", "unclear"]
    sow = t["sow"]
    assert sow["goal"]["readers"] == ["Priya Nair", "the committee"] and sow["goal"]["needed_by"] == "2026-11-30"
    assert [s["who"] for s in sow["process"]["steps"]] == ["Leela", "Arjun"]
    tw = next(k for k in sow["kpis"] if k["name"] == "Time-weighted return")
    assert tw["status"] == "defined" and not tw["pack_suggested"]
    assert next(k for k in sow["kpis"] if k["name"] == "Concentration")["status"] == "unclear"  # no definition given: never guessed
    assert any(k["pack_suggested"] and k["status"] == "unclear" for k in sow["kpis"])  # the pack's concentration KPI, as a suggestion
    assert {g["kind"] for g in sow["governance"]} == {"access", "retention"} and sow["governance"][0]["stated_by"] == "Arjun Mehta"
    assert any(u["question"].startswith("Who owns the benchmark") for u in sow["unclear"])
    assert t["turns"][-1]["text"].startswith("The intent of work is ready")
    assert [f["kind"] for x in t["turns"] for f in x["files"]] == ["sample"] and t["turns"][-8]["need"] == "inputs"


class Stub:
    def complete(self, module_id, messages, tools=None):
        return ModelReply(text=json.dumps({"section": {"why": "The committee asked for it", "readers": ["Priya Nair"]},
                                           "met": True, "unclear": [], "follow_up": "", "next_question": "How is it done today?"}))


def test_model_drafts_through_the_runtime(app):
    c = client(app, "arjun.mehta.neera@example.test")
    iid = c.post("/api/v1/intents", json={"line": "Fee ratio by client"}).json()["id"]
    app.state.build_model_factory = lambda plane: Stub()
    try:
        t = c.post(f"/api/v1/intents/{iid}/thread", json={"text": "The committee asked for it, Priya reads it."}).json()
    finally:
        del app.state.build_model_factory
    assert t["turns"][-1]["name"] == "North" and t["turns"][-1]["text"] == "How is it done today?" and t["turns"][-1]["need"] == "process"
    assert t["sow"]["goal"]["why"] == "The committee asked for it" and t["needs_done"] == ["goal"]


def test_analyst_starts_but_is_off_someone_elses_team(app):
    iid = client(app, "arjun.mehta.neera@example.test").post("/api/v1/intents", json={"line": "Cash drag"}).json()["id"]
    leela = client(app, "leela.raman.neera@example.test")
    assert leela.get(f"/api/v1/intents/{iid}/thread").status_code == 403  # G1: not on the team
    assert leela.post(f"/api/v1/intents/{iid}/thread", json={"text": "hello"}).status_code == 403
    assert leela.post("/api/v1/intents", json={"line": "x"}).status_code == 200  # anyone may start
