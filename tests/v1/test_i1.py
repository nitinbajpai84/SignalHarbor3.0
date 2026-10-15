"""I1 Company page: the decision maker edits all four sections and uploads a document; an analyst reads but may not write."""
import base64
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings
from sh_platform.v1 import i1_company

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("i1") / "data"
    shutil.copytree(ROOT / "data", data)
    yield create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    mp.undo()


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_decision_maker_edits_the_page(app):
    c = client(app, "arjun.mehta.neera@example.test")
    page = c.get("/api/v1/company").json()
    assert page["can_edit"] and page["who"]["name"]["value"] == "Neera Family Office"
    assert any(s["name"] == "Custodian daily files" for s in page["systems"])

    r = c.put("/api/v1/company", json={
        "who": {"about": "A single-family office in Singapore."},
        "systems": [{"id": "custodian-daily-files", "owner": "Leela Raman"}, {"name": "Board minutes drive", "kind": "drive"}],
        "policies": [{"kind": "retention", "text": "Keep statements seven years."}]})
    assert r.status_code == 200, r.text
    page = r.json()
    assert page["who"]["about"]["value"] == "A single-family office in Singapore." and page["who"]["about"]["by"] == "Arjun Mehta"
    systems = {s["id"]: s for s in page["systems"]}
    assert systems["custodian-daily-files"]["owner"] == "Leela Raman" and systems["board-minutes-drive"]["kind"] == "drive"
    assert page["policies"][0]["stated_by"] == "Arjun Mehta"

    up = c.post("/api/v1/company/documents", json={"filename": "policy.md", "data": base64.b64encode(b"# Policy\nNet of fees.").decode()})
    assert up.status_code == 200, up.text
    docs = {d["filename"] for d in c.get("/api/v1/company").json()["documents"]}
    assert "policy.md" in docs and "01-investment-policy-statement.md" in docs  # the page's upload and D2's files, one folder
    assert (Path(app.state.settings.data_root) / "neera" / "documents" / "policy.md").is_file()
    assert c.post("/api/v1/company/documents", json={"filename": "policy.md", "data": base64.b64encode(b"again").decode()}).status_code == 409

    plane = PlaneStore(app.state.settings.data_root).plane_for("neera")
    at = i1_company.mark_read(plane)
    assert c.get("/api/v1/company").json()["north_read_at"] == at
    assert i1_company.for_north(plane)["policies"][0]["text"] == "Keep statements seven years."


def test_analyst_reads_but_may_not_write(app):
    c = client(app, "leela.raman.neera@example.test")
    assert c.get("/api/v1/company").json()["can_edit"] is False
    assert c.put("/api/v1/company", json={"who": {"name": "X"}}).status_code == 403
    assert c.post("/api/v1/company/documents", json={}).status_code == 403


def test_fresh_company_and_bad_kind(app):
    c = client(app, "nitin.fresh@example.test")
    page = c.get("/api/v1/company").json()
    assert page["systems"] == [] and page["policies"] == [] and page["documents"] == []
    assert c.put("/api/v1/company", json={"policies": [{"kind": "mood", "text": "x"}]}).status_code == 422


# ---- I1 (9 Oct): the Intent centre -- sources captured, swim lane, project id, Send to Build -------------------------------
import json  # noqa: E402

from sh_platform.agents.protocols import ModelReply  # noqa: E402
from sh_platform.jsonfile import read_json_strict, write_json_atomic  # noqa: E402
from sh_platform.v1 import i2_north as N, i6_chat as C, p1_project as P1  # noqa: E402


class Stub:
    def __init__(self, answer):
        self.answer = answer

    def complete(self, module_id, messages, tools=None):
        return ModelReply(text=json.dumps(self.answer))


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("i1b") / "data"
    shutil.copytree(ROOT / "data", data)
    a = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    a.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    yield a
    mp.undo()


def test_sources_section_is_filled_from_talk(world):
    """Rules only (model off): 'monthly' in the person's words lands on the source as how often it arrives."""
    sow = N.empty_sow("x", "Monthly report")
    covered = list(C.GOALS)[:list(C.GOALS).index("inputs")]
    got = C.fallback(sow, covered, "The administrator export from Leela Raman arrives monthly", [])
    rows = got["sow_patch"].get("sources") or []
    assert rows and all(r.get("arrives") == "monthly" for r in rows)
    assert "how often" in C.GOALS["inputs"][1]


def test_model_fills_sources_swim_lane_and_project_id(world):
    c = client(world, "arjun.mehta.neera@example.test")
    answer = {"reply": "Which figures do you report today?", "ready": False, "covered": ["inputs"],
              "sow_patch": {"sources": [
                  {"name": "Administrator export", "kind": "file", "holds": "Holdings", "owner": "Leela Raman", "arrives": "monthly",
                   "samples": ["admin_sep.csv"]},
                  {"name": "Manager statements", "kind": "document", "structure": "unstructured", "holds": "Valuations", "owner": "Mei", "arrives": "quarterly"}]},
              "process_steps": [{"name": "Download the export", "who": "Leela Raman", "does": "Saves the file by hand", "system": "Spreadsheet"},
                                {"name": "Check the totals", "who": "Mei", "does": "Compares to statements"}]}
    world.state.build_model_factory = lambda plane: Stub(answer)
    try:
        t = c.post("/api/v1/intents/chat", json={"text": "Monthly investment report in USD and SGD"}).json()
        iid = t["id"]
        assert t["project_id"] and t["project_id"].startswith("prj-") and t["build"] is None  # the project exists from the first message
        for p in t["proposals"]["pending"]:
            assert c.post(f"/api/v1/intents/{iid}/proposals/{p['id']}/accept").status_code == 200
    finally:
        del world.state.build_model_factory
    got = c.get(f"/api/v1/intents/{iid}/chat").json()
    src = {s["name"]: s for s in got["sow"]["sources"]}
    assert src["Administrator export"]["structure"] == "structured" and src["Administrator export"]["arrives"] == "monthly"
    assert src["Administrator export"]["samples"] == ["admin_sep.csv"] and src["Administrator export"]["owner"] == "Leela Raman"
    assert src["Manager statements"]["structure"] == "unstructured"
    assert {s["who"] for s in got["process_map"]["steps"]} == {"Leela Raman", "Mei"}  # lanes by team


def test_send_to_build(world):
    c = client(world, "arjun.mehta.neera@example.test")
    iid = c.post("/api/v1/intents", json={"line": "Send me to build"}).json()["id"]
    url = f"/api/v1/intents/{iid}/send-to-build"
    assert c.post(url).status_code == 409  # still a draft
    plane = PlaneStore(world.state.settings.data_root).plane_for("neera")
    path = N._path(plane, iid, "sow.json")
    sow = read_json_strict(path, dict)
    write_json_atomic(path, {**sow, "state": "signed"})
    assert [x["state"] for x in c.get("/api/v1/intents/open").json()["recent"] if x["id"] == iid] == ["Signed, not sent to Build"]
    r = c.post(url)
    assert r.status_code == 200, r.text
    pid = P1.project_of(plane, iid)["id"]
    assert r.json()["project_id"] == pid and c.post(url).json()["at"] == r.json()["at"]  # once
    assert [x["state"] for x in c.get("/api/v1/intents/open").json()["recent"] if x["id"] == iid] == ["Sent to Build"]
    assert N._path(plane, iid, "send_to_build.json").is_file()  # the card in Action comes from e5_pulse's Build source (see test_e5a)
    assert c.get(f"/api/v1/intents/{iid}/chat").json()["build"]["project_id"] == pid
    assert client(world, "leela.raman.neera@example.test").post(url).status_code == 403
