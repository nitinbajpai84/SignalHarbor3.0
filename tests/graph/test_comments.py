"""Node comments: anyone who sees the node adds; only the owner or steward decides; anonymous carries no name. Synthetic data."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import load_settings

ROOT = Path(__file__).resolve().parents[2]
FAMILY = "lakeside-family-office"


def n(i, t, label, **kw):
    return {"id": i, "type": t, "label": label, "provenance": [], **kw}


def e(a, b, t):
    return {"from": a, "to": b, "type": t, "provenance": []}


DOC = {"version": 1, "built_at": "2026-10-06T00:00:00+00:00",
       "nodes": [n("m1", "Measure", "Single-issuer concentration"), n("m2", "Measure", "Loose measure"), n("s1", "Source", "Custody feed"),
                 n("p1", "Person", "OWNER"), n("m3", "Measure", "Secret measure", restricted_to=["priya nair"])],
       "edges": [e("m1", "s1", "fed_by"), e("s1", "p1", "owned_by"), e("m1", "p1", "owned_by"), e("m3", "s1", "fed_by")]}


@pytest.fixture
def login(tmp_path_factory, tmp_path):
    root = tmp_path_factory.mktemp("cg_seeded") / "data"
    spec = importlib.util.spec_from_file_location("cg_tool_seed", ROOT / "tools" / "seed.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    result = mod.seed(root)
    pw = {l.split()[0]: l.split()[1] for l in result["path"].read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}
    shutil.copytree(root, tmp_path / "data")
    plane = PlaneStore(tmp_path / "data").plane_for(FAMILY)
    plane.path("graph", "company.json").write_text(json.dumps(DOC), encoding="utf-8")
    settings = load_settings({"SH_MODE": "dev", "SH_DATA_ROOT": str(tmp_path / "data"), "SH_SESSION_SECRET": "FAKE-graph-secret-0123456789-abcdefghij"}, env_file=tmp_path / "none.env")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<!doctype html>", encoding="utf-8")
    app = create_app(settings, dist_dir=tmp_path / "dist")

    def go(role: str) -> TestClient:
        email = f"{role}.{FAMILY}@example.test"
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        c.headers["x-csrf-token"] = c.cookies["sh_csrf"]
        return c
    owner = go("sponsor")
    name = owner.get("/api/auth/me").json()["display_name"]
    doc = json.loads(json.dumps(DOC).replace("OWNER", name))
    plane.path("graph", "company.json").write_text(json.dumps(doc), encoding="utf-8")
    plane.path("graph", "steward.json").write_text(json.dumps({"name": "Nobody Else", "account_id": None}), encoding="utf-8")
    return plane, go, name


URL = "/api/company/graph/node/m1/comments"


def test_anyone_who_sees_the_node_can_comment_and_a_silhouette_is_404(login):
    plane, go, _ = login
    r = go("analyst").post(URL, json={"kind": "ambiguity", "text": "Which custodian?", "anonymous": False})
    assert r.status_code == 200 and r.json()["state"] == "open", r.text
    assert go("company_admin").get(URL).json()["comments"][0]["text"] == "Which custodian?"
    assert go("sponsor").get("/api/company/graph/node/m3/comments").status_code == 404  # a node the viewer may not see
    assert go("analyst").post(URL, json={"kind": "bogus", "text": "x"}).status_code == 400


def test_only_the_owner_or_steward_decides(login):
    plane, go, owner = login
    cid = go("analyst").post(URL, json={"kind": "suggestion", "text": "Use net value"}).json()["id"]
    d = f"{URL}/{cid}/decide"
    assert go("analyst").post(d, json={"state": "accepted"}).status_code == 403
    assert go("sponsor").post(d, json={"state": "accepted"}).status_code == 200
    got = go("sponsor").get(URL).json()["comments"][0]
    assert got["state"] == "accepted" and got["decided_by"] == owner
    versions = json.loads(plane.path("graph", "versions.json").read_text(encoding="utf-8"))
    assert versions["m1"][0]["v"] == 1 and "Use net value" in versions["m1"][0]["what"]
    assert go("sponsor").post(d, json={"state": "answered"}).status_code == 400  # an answer needs words


def test_an_anonymous_comment_never_carries_a_name(login):
    plane, go, _ = login
    me = go("analyst").get("/api/auth/me").json()["display_name"]
    go("analyst").post(URL, json={"kind": "comment", "text": "Looks off", "anonymous": True})
    raw = plane.path("graph", "comments.json").read_text(encoding="utf-8")
    assert '"by": "Anonymous"' in raw and me not in raw
