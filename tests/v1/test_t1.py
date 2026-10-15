"""T1 templates: seeds, a required field blocks sign-off, North's goals follow the chosen template, a company skill overrides the
repo's, only the company admin changes things, a started document keeps its template version, requests reach the admin."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.settings import Settings
from sh_platform.v1 import i2_north as N
from sh_platform.v1 import skill_loader as SL
from sh_platform.v1 import t1_templates as T

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
ARJUN, LEELA = "arjun.mehta.neera@example.test", "leela.raman.neera@example.test"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("t1") / "data"
    shutil.copytree(ROOT / "data", data)
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    yield app, PlaneStore(data)
    mp.undo()


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_seeds_goals_and_the_sample_company_examples(world):
    _, store = world
    t = T.template_for(store.plane_for("neera"), "intent_of_work")
    must = T.required_keys(t)
    assert t["version"] == 1 and len(t["fields"]) == 16 and "benchmarks" in must and "strategic" not in must
    goals = T.goals_from(t)
    assert list(goals)[:len(must)] == must and list(goals)[-1] == T.FREE_KEY      # must-fill first, free text last
    assert len(goals["goal"]) == 4 and goals["goal"][2] == "goal"                  # i6_chat's GOALS shape
    for kind in T.KINDS:
        assert T.template_for(store.plane_for("neera"), kind)["fields"]
    try:  # the sample company is no longer in the live data (renamed in a local branded workspace); make it in the copy
        wh = store.plane_for(T.SAMPLE_COMPANY)
    except LookupError:
        wh = store.create(T.SAMPLE_COMPANY)
    ex = T.listing(wh, Viewer("A", frozenset({"analyst"}), False, "a"), "intent_of_work")[0]["examples"]
    assert [e["name"] for e in ex] == ["Monthly wealth and performance report", "Quarterly fee review"]
    assert T.example(wh, ex[0]["id"])["values"]["goal"]
    assert T.template_for(store.plane_for("fresh"), "intent_of_work")["examples"] == []


def test_required_field_blocks_sign_and_a_started_document_keeps_its_version(world):
    app, store = world
    plane = store.plane_for("neera")
    admin = Viewer("Arjun Mehta", frozenset({"company_admin"}), False, "acc-1")
    iid = N.create(plane, admin, "Monthly pack")["id"]
    pin = T.choose(plane, iid)
    assert pin["version"] == 1
    block = T.sign_block(plane, iid)
    assert "Who reads the result" in block and "signed" in block
    assert T.choose(plane, iid, "nobody-here-x") == pin                # the pin sticks
    # every required goal answered: nothing blocks
    sow = N.read_sow(plane, iid)   # a value, not a tick, fills a must-fill field
    sow["template_fields"] = {k: "answered" for k in T.required_keys(T.for_intent(plane, iid))}
    from sh_platform.jsonfile import write_json_atomic
    write_json_atomic(N._path(plane, iid, "sow.json"), sow)
    assert T.sign_block(plane, iid) is None
    # the admin changes and adopts the standard template (version 2): the started intent keeps version 1
    c = client(app, ARJUN)
    t = c.get("/api/v1/templates/standard-intent-of-work").json()
    fields = t["fields"] + [{"key": "budget", "label": "Budget", "required": True, "type": "text"}]
    assert c.put("/api/v1/templates/standard-intent-of-work", json={"fields": fields}).status_code == 200
    assert T.template_for(plane, "intent_of_work")["version"] == 1                 # not adopted yet: people still read version 1
    assert c.post("/api/v1/templates/standard-intent-of-work/adopt", json={}).json()["version"] == 2
    assert T.template_for(plane, "intent_of_work")["version"] == 2
    assert T.for_intent(plane, iid)["version"] == 1 and T.sign_block(plane, iid) is None
    new = N.create(plane, admin, "Another")["id"]
    assert T.choose(plane, new)["version"] == 2 and "Budget" in T.sign_block(plane, new)
    log = c.get("/api/v1/admin/log").json()
    assert [r["what"] for r in log[:2]] == ["adopted template", "edited template"]


def test_only_the_company_admin_changes_things_and_requests_reach_them(world):
    app, _ = world
    leela, arjun = client(app, LEELA), client(app, ARJUN)
    assert leela.get("/api/v1/templates").status_code == 200
    for r in (leela.post("/api/v1/templates/standard-intent-of-work/adopt", json={}), leela.put("/api/v1/admin/governance", json={"rules": []}),
              leela.get("/api/v1/admin/skills"), leela.get("/api/v1/admin/requests"), leela.get("/api/v1/templates?all=1")):
        assert r.status_code == 403
    assert leela.post("/api/v1/template-requests", json={"text": "We need a template for a quarterly fee review"}).json()["id"] == "REQ-0001"
    rows = arjun.get("/api/v1/admin/requests").json()
    assert rows[0]["by"] == "Leela Raman" and rows[0]["state"] == "open"
    assert arjun.post("/api/v1/admin/requests/REQ-0001", json={"state": "done", "note": "Added"}).json()["state"] == "done"
    assert arjun.put("/api/v1/admin/governance", json={"rules": [{"rule": "Nothing leaves the company without a signature", "owner": "Arjun"}]}).json()["version"] == 1
    plane = world[1].plane_for("neera")
    assert T.governance_rules(plane) == ["Nothing leaves the company without a signature (owner: Arjun)"]


def test_a_company_skill_overrides_the_default(world):
    app, store = world
    plane, other = store.plane_for("neera"), store.plane_for("fresh")
    repo = SL.load_skill("north")
    c = client(app, ARJUN)
    got = c.get("/api/v1/admin/skills").json()
    north = next(a for a in got if a["agent"] == "north")
    assert {f["source"] for f in north["files"]} == {"repo"}
    assert c.put("/api/v1/admin/skills/north/playbook.md", json={"text": "# Our North\nAlways ask about the family council first."}).status_code == 200
    assert "Always ask about the family council" in SL.load_skill("north", plane)
    assert SL.load_skill("north", other) == repo == SL.load_skill("north") and SL.skill_label("north", plane) == "Our North"
    assert "questions.md" in SL.skill_files("north", plane)                           # files not edited still come from the repo
    assert c.put("/api/v1/admin/skills/north/Bad%20name.txt", json={"text": "x"}).status_code == 422
    assert c.put("/api/v1/admin/skills/nobody/playbook.md", json={"text": "x"}).status_code == 404
    assert c.put("/api/v1/admin/skills/north/playbook.md", json={"text": "# Second"}).status_code == 200
    assert len(list((plane.path("skills", "north", "_versions")).glob("playbook__v*.md"))) == 2  # the repo text, then the first company copy
    assert c.delete("/api/v1/admin/skills/north/playbook.md").status_code == 200
    assert SL.load_skill("north", plane) == repo
