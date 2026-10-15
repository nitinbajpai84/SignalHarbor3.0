"""Harbor 3.0 role suggestions: a job per person, the pack's actions and builds, and which builds are already started."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.auth.accounts import AccountStore  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_harbor as H, v3_model as M  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

PW = "test-password-not-real"
SAY = "I want to know every morning whether each entity can meet its capital calls."
DOC = {"roles": [
    {"id": "cfo", "title": "Head of Finance", "actions": ["Approve funding for a capital call"],
     "builds": [{"id": "uc6", "title": "Capital calls", "say": SAY, "dashboard": "Consume: cash by entity", "skills": ["intent.restate-ask"]}]},
    {"id": "ops_clerk", "title": "Operations Clerk", "actions": [], "builds": []}]}


class FakePack:
    def section(self, name):
        if name != "role_builds":
            raise KeyError(name)
        return DOC


def login(app, email, pw=PW) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    monkeypatch.setattr(M, "pack_of", lambda plane: FakePack())
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    st = AccountStore(data)
    st.create("sam@evergreen.example.test", PW, "Sam Lee", "evergreen", ["participant"])
    st.create("boss@evergreen.example.test", PW, "Bo Boss", "evergreen", ["company_admin"])
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    return app, data, login(app, "sam@evergreen.example.test"), login(app, "boss@evergreen.example.test")


def test_no_job_is_an_honest_empty(env):
    _, _, sam, _ = env
    r = sam.get("/api/v3/me/role").json()
    assert r["role"] is None and r["actions"] == [] and r["builds"] == []
    assert [x["id"] for x in r["roles"]] == ["cfo", "ops_clerk"]


def test_set_own_job_and_started(env):
    _, data, sam, _ = env
    assert sam.post("/api/v3/people/job", json={"email": "sam@evergreen.example.test", "role": "cfo"}).status_code == 200
    r = sam.get("/api/v3/me/role").json()
    assert r["role"] == {"id": "cfo", "title": "Head of Finance"}
    assert r["actions"] == ["Approve funding for a capital call"]
    assert r["builds"][0]["started"] is None and r["builds"][0]["dashboard"] == "Consume: cash by entity"
    plane = PlaneStore(data).plane_for("evergreen")
    H.save(plane, {"id": "t1", "title": "x", "stage": "drafting", "created": "2026-10-01T00:00:00Z", "events": [{"kind": "person", "text": SAY}]})
    assert sam.get("/api/v3/me/role").json()["builds"][0]["started"] == "t1"
    H.save(plane, {"id": "t1", "title": "x", "stage": "discarded", "created": "2026-10-01T00:00:00Z", "events": [{"kind": "person", "text": SAY}]})
    assert sam.get("/api/v3/me/role").json()["builds"][0]["started"] is None


def test_plain_person_cannot_set_another_but_admin_can(env):
    _, _, sam, boss = env
    assert sam.post("/api/v3/people/job", json={"email": "boss@evergreen.example.test", "role": "cfo"}).status_code == 403
    assert boss.post("/api/v3/people/job", json={"email": "sam@evergreen.example.test", "role": "ops_clerk"}).status_code == 200
    assert sam.get("/api/v3/me/role").json()["role"]["id"] == "ops_clerk"
    assert sam.post("/api/v3/people/job", json={"email": "sam@evergreen.example.test", "role": "nope"}).status_code == 400
    assert [p["email"] for p in sam.get("/api/v3/people/jobs").json()["people"]] == ["sam@evergreen.example.test"]
    assert len(boss.get("/api/v3/people/jobs").json()["people"]) > 2
