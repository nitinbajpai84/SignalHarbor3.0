"""Card P1: starting an intent makes a project; the analyst comments on a KPI line to the decision maker, which holds his signature
until he answers; the analyst may not answer a comment addressed to someone else; the intent of work exports as Markdown."""
import secrets
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.settings import Settings
from tests.v1.team import on_team
from sh_platform.v1 import p1_project as P
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("p1") / "data"
    shutil.copytree(SEED / "_control", data / "_control")
    (data / "neera").mkdir()
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    from sh_platform.auth.accounts import AccountStore
    pw = {}
    for who in ("arjun.mehta", "leela.raman"):  # a test password in the tmp copy only
        email = f"{who}.neera@example.test"
        pw[email] = secrets.token_urlsafe(16)
        AccountStore(data).set_password(email, pw[email])
    yield app, data, pw
    mp.undo()


def client(world, who):
    app, _, pw = world
    c = TestClient(app)
    email = f"{who}.neera@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_project_comment_holds_signature_until_answered(world):
    arjun, leela = client(world, "arjun.mehta"), client(world, "leela.raman")
    r = arjun.post("/api/v1/intents/chat", json={"text": "A monthly performance pack for the board"})
    assert r.status_code == 200, r.text
    iid = r.json()["id"]
    on_team(world[0], iid, "Leela Raman")  # G1: Internal is the team's alone
    prj = leela.get(f"/api/v1/intents/{iid}/project").json()
    pid = prj["id"]
    assert pid.startswith("prj-") and prj["stage"] == "talking" and prj["people"]["raiser"] == "Arjun Mehta"
    assert [a["kind"] for a in prj["artefacts"]] == list(P.KINDS)

    doc = leela.get(f"/api/v1/projects/{pid}/artefacts/intent").json()
    assert doc["sections"][0]["lines"][0]["ref"] == "1.1"
    c = leela.post(f"/api/v1/projects/{pid}/comments",
                   json={"artefact": "intent", "line_ref": "1.1", "to": "raiser", "text": "Which board meeting is this for?"}).json()
    assert c["to"] == "Arjun Mehta" and c["state"] == "open" and c["by"] == "Leela Raman"
    assert "waiting for your answer" in P.sign_block(world_plane(world), iid, "intent", "Arjun Mehta")
    signed = arjun.post(f"/api/v1/intents/{iid}/sow/sign", json={"confirm": True, "version": 1})
    assert signed.status_code == 409 and "waiting for your answer" in signed.text, signed.text

    refused = leela.post(f"/api/v1/projects/{pid}/comments/{c['id']}/answer", json={"text": "I will answer for him"})
    assert refused.status_code == 403 and "Arjun Mehta" in refused.json()["message"]

    assert arjun.post(f"/api/v1/projects/{pid}/comments/{c['id']}/answer", json={"text": "The November meeting"}).json()["state"] == "answered"
    assert P.sign_block(world_plane(world), iid, "intent", "Arjun Mehta") is None
    assert leela.post(f"/api/v1/projects/{pid}/comments/{c['id']}/resolve").json()["state"] == "resolved"

    md = leela.get(f"/api/v1/projects/{pid}/artefacts/intent/export?format=md")
    assert md.status_code == 200 and md.text.startswith("# Intent of work")
    assert leela.get(f"/api/v1/projects/{pid}/artefacts/intent/export?format=xlsx").status_code == 400


def world_plane(world):
    from sh_platform.plane import PlaneStore
    _, data, _ = world
    return PlaneStore(data).plane_for("neera")


def test_the_person_who_signs_the_intent_becomes_the_projects_sponsor(tmp_path):
    """V6 (walk gap 6): people.sponsor was left empty after the sponsor signed; the raiser's own signature does not fill it."""
    from sh_platform.jsonfile import write_json_atomic
    from sh_platform.plane import PlaneStore
    plane = PlaneStore(tmp_path / "data").create("acme")
    for iid, signer, want in (("int-a", "Daniel Foo", "Daniel Foo"), ("int-b", "Mei Chen", None)):
        (plane.path("intents") / iid).mkdir(parents=True)
        write_json_atomic(plane.path("intents", iid, "sow.json"), {"title": "Monthly report", "state": "signed", "version": 1,
                                                                    "signature": {"name": signer, "role": "sponsor", "at": "2026-10-11T08:00:00+00:00"}})
        rec = P.create_project(plane, iid, "Monthly report", "Mei Chen")
        assert P.read(plane, rec["id"])["people"]["sponsor"] == want
