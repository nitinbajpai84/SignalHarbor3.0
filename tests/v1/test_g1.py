"""Card G1: one helper (`may_see_project`) decides who reads a project. Internal shows a lock and a preview, Restricted nothing, a
request goes to the owner and is answered from Pulse with an expiry, a person addressed by a comment can always read and answer
(S10), the map hides a restricted project's nodes, and the project folder holds exports and uploads."""
import base64
import secrets
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.settings import Settings
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import p1_project as P
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
WHO = ("priya.nair", "arjun.mehta", "leela.raman", "dev.sharma")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("g1") / "data"
    shutil.copytree(SEED / "_control", data / "_control")
    (data / "neera").mkdir()
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    from sh_platform.auth.accounts import AccountStore
    pw = {}
    for who in WHO:  # a test password in the tmp copy only
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


def plane_of(world):
    return PlaneStore(world[1]).plane_for("neera")


def account(world, name):
    from sh_platform.auth.accounts import AccountStore
    a = next(x for x in AccountStore(world[1]).in_company("neera") if x["display_name"] == name)
    return Viewer(name, frozenset(a["roles"]), False, a["account_id"])


def test_internal_lock_request_grant_and_restricted(world):
    priya, arjun, leela, dev = (client(world, w) for w in WHO)
    r = priya.post("/api/v1/intents/chat", json={"text": "A quarterly fee review for the committee"})
    assert r.status_code == 200, r.text
    iid = r.json()["id"]
    prj = priya.get(f"/api/v1/intents/{iid}/project").json()
    pid = prj["id"]
    assert prj["sensitivity"] == "internal" and prj["access"] == "full" and "Priya Nair" in [m["name"] for m in prj["team"]]

    # Internal: a participant who is not on the team sees the lock, a preview, and no artefact or export
    lock = dev.get(f"/api/v1/projects/{pid}").json()
    assert lock["locked"] and lock["access"] == "preview" and lock["owner"] == "Priya Nair" and lock["title"] and "artefacts" not in lock
    assert dev.get(f"/api/v1/projects/{pid}/artefacts/intent").status_code == 403
    assert dev.get(f"/api/v1/projects/{pid}/artefacts/intent/export?format=md").status_code == 403
    assert dev.post(f"/api/v1/projects/{pid}/comments", json={"artefact": "intent", "to": "raiser", "text": "hello"}).status_code == 403
    assert [p["id"] for p in dev.get("/api/v1/projects").json()["projects"]] == [pid] and dev.get("/api/v1/projects").json()["projects"][0]["locked"]
    assert leela.get(f"/api/v1/projects/{pid}/artefacts/intent").status_code == 403  # Internal is the team's alone, whatever the role
    assert arjun.get(f"/api/v1/projects/{pid}/artefacts/intent").status_code == 200  # the company admin sees every artefact

    # Request access: a K1 request to the owner, answered from Pulse
    asked = dev.post(f"/api/v1/projects/{pid}/access/request", json={"reason": "I run the fee desk"})
    assert asked.status_code == 200 and asked.json()["to"] == "Priya Nair", asked.text
    assert dev.post(f"/api/v1/projects/{pid}/access/request", json={}).json()["id"] == asked.json()["id"]  # one open request
    cards = [c for c in priya.get("/api/v1/pulse").json()["needs_you"]["cards"] if c["kind"] == "access"]
    assert cards and "Dev Sharma" in cards[0]["text"] and cards[0]["action"].startswith("Approve")
    assert dev.post(f"/api/v1/projects/{pid}/access/answer/{asked.json()['id']}", json={"approve": True}).status_code == 404  # not yours to answer
    done = priya.post(f"/api/v1/projects/{pid}/access/answer/{asked.json()['id']}", json={"approve": True, "days": 7, "note": "Welcome"})
    assert done.status_code == 200 and done.json()["state"] == "granted" and done.json()["expires"], done.text
    assert dev.get(f"/api/v1/projects/{pid}/artefacts/intent").status_code == 200  # read, not full
    assert dev.get(f"/api/v1/projects/{pid}").json()["access"] == "read"
    trail = P.comments(plane_of(world), pid)
    assert any(c["kind"] == "access" and c["state"] == "resolved" for c in trail)
    plane = plane_of(world)
    assert G1.may_see_project(plane, account(world, "Dev Sharma"), pid) == "read"
    assert priya.delete(f"/api/v1/projects/{pid}/access/grants/{account(world, 'Dev Sharma').account_id}").status_code == 200
    assert dev.get(f"/api/v1/projects/{pid}/artefacts/intent").status_code == 403  # taken back

    # Restricted: nothing but that the project exists; S10: a comment addressed to a person still lets them read and answer
    assert priya.put(f"/api/v1/projects/{pid}/access", json={"sensitivity": "restricted"}).json()["sensitivity"] == "restricted"
    assert dev.put(f"/api/v1/projects/{pid}/access", json={"sensitivity": "open"}).status_code == 403
    gone = dev.get(f"/api/v1/projects/{pid}").json()
    assert gone["locked"] and gone["access"] == "none" and "title" not in gone and "owner" not in gone
    assert dev.get("/api/v1/projects").json()["projects"] == []
    assert leela.get(f"/api/v1/projects/{pid}/artefacts/intent").status_code == 403  # a restricted project is the team's alone
    c = priya.post(f"/api/v1/projects/{pid}/comments", json={"artefact": "intent", "line_ref": "1.1", "to": "Dev Sharma", "text": "Which desk owns the fee file?"}).json()
    assert dev.get(f"/api/v1/projects/{pid}/artefacts/intent").status_code == 200
    ans = dev.post(f"/api/v1/projects/{pid}/comments/{c['id']}/answer", json={"text": "The fee desk"})
    assert ans.status_code == 200 and ans.json()["state"] == "answered"
    # Pulse: the restricted project is no line for an outsider, and the addressee's card opens it
    assert all(ln.get("pid") != pid for ln in leela.get("/api/v1/pulse").json()["projects"]["lines"])


def test_folder_map_and_north(world):
    priya, arjun, leela, dev = (client(world, w) for w in WHO)
    plane = plane_of(world)
    iid = priya.post("/api/v1/intents/chat", json={"text": "Monthly wealth report for the family council"}).json()["id"]
    pid = priya.get(f"/api/v1/intents/{iid}/project").json()["id"]
    # North's answer to the access question sets the project and names the team
    G1.note_answer(plane, iid, "Only you and Dev Sharma, no preview for others", G1.ASK, False)
    rec = P.read(plane, pid)
    assert rec["sensitivity"] == "restricted" and "Dev Sharma" in [m["name"] for m in G1.team_of(rec)]
    assert dev.get(f"/api/v1/projects/{pid}").json()["access"] == "full"
    # the project folder: an upload lands in projects/<pid>/files/ and the library row points at it
    up = priya.post(f"/api/v1/projects/{pid}/files", json={"name": "fees.csv", "data": base64.b64encode(b"a,b\n1,2\n").decode()})
    assert up.status_code == 200, up.text
    assert (plane.path("projects", pid, "files", "Statements and invoices") / "fees.csv").is_file()
    from sh_platform.v1 import c4_library as L
    assert any(i.get("project") == pid and i["name"] == "fees.csv" for i in L._index(plane))
    assert [f["name"] for f in priya.get(f"/api/v1/projects/{pid}/files").json()["files"]] == ["fees.csv"]
    assert [f["name"] for f in dev.get(f"/api/v1/projects/{pid}/files").json()["files"]] == ["fees.csv"]
    assert leela.get(f"/api/v1/projects/{pid}/files").status_code == 403
    assert not any(i.get("project") == pid for i in L.listing(plane, account(world, "Leela Raman")))  # not even a lock row for a restricted project's file
    # an export from the full level is kept in the folder
    assert priya.get(f"/api/v1/projects/{pid}/artefacts/intent/export?format=md").status_code == 200
    assert any(i["name"].endswith("-intent-of-work.md") or i["name"].endswith("-intent.md") for i in L._index(plane) if i.get("project") == pid)
    # the company map: a restricted project's own nodes are a silhouette to everyone off its team
    from sh_platform.graph import models
    from sh_platform.graph.read import _sees
    g = models.Graph()
    g.node("intent:" + iid, "Measure", "Fee total", [], "intent")
    g.nodes["intent:" + iid]["intents"] = [iid]
    G1.restrict_nodes(g, plane, iid)
    node = g.nodes["intent:" + iid]
    assert _sees(node, dev_viewer := account(world, "Dev Sharma")) and not _sees(node, account(world, "Leela Raman")) and dev_viewer
    # the agents: a person who may not see the project is not talked to about it
    with pytest.raises(ValueError):
        G1.check_agent(plane, iid, account(world, "Leela Raman"), ValueError)
    G1.check_agent(plane, iid, account(world, "Dev Sharma"), ValueError)


def test_template_field_and_goal_order():
    f = G1.template_field()
    assert f["key"] == "access" and not f["required"] and f["ask"] == G1.ASK
    goals = {"goal": ("a", "q", None, None), "readers": ("b", "q", None, None), "frequency": ("c", "q", None, None), "comments": ("d", "q", None, None)}
    assert list(G1.place(goals))[:2] == ["goal", "access"]  # a template seeded before G1 gets the question too
