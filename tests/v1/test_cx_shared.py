"""SW1: GET /api/v1/consume/shared - dashboards others shared with the person, and the latest issued report."""
import uuid
from datetime import date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_routes, e1_reports, p1_project, wh
from tests.v1.test_cx import ADMIN, _user


@pytest.fixture()
def env(tmp_path, monkeypatch):
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("acme")
    pid = p1_project.create_project(plane, "int-1", "Monthly report", "Nitin")["id"]
    _user(plane, "Boss", "acc-admin")
    daniel = _user(plane, "Daniel", "acc-d", entity=True)
    sofia = _user(plane, "Sofia", "acc-s", entity=True)
    d = D.create(plane, ADMIN, pid, "Board pack")
    D.set_audience(plane, ADMIN, pid, d["id"], [daniel])
    cur = {}
    monkeypatch.setattr(cx_routes, "viewer_of", lambda request: cur["v"])
    monkeypatch.setattr(cx_routes, "_plane", lambda request: plane)
    app = FastAPI()
    app.include_router(cx_routes.router)
    return plane, d, TestClient(app), cur


def get(env, name, acc):
    _, _, c, cur = env
    cur["v"] = Viewer(name=name, roles=frozenset({"participant"}), account_id=acc)
    return c.get("/api/v1/consume/shared").json()


def test_audience_sees_it_others_and_the_maker_do_not(env):
    got = get(env, "Daniel", "acc-d")["dashboards"]
    assert [(x["id"], x["project_title"], x["shared_by"], x["tiles"], x["link"]) for x in got] == [(env[1]["id"], "Monthly report", "Boss", 0, f"/centre/consume/d/{env[1]['id']}")]
    assert get(env, "Sofia", "acc-s")["dashboards"] == []
    env[3]["v"] = ADMIN
    assert env[2].get("/api/v1/consume/shared").json()["dashboards"] == []  # own dashboards are in "Your projects"


def test_lost_access_sees_none(env):
    plane = env[0]
    with wh.connect(plane) as con:
        con.execute("delete from access_group_scopes")
    assert get(env, "Daniel", "acc-d")["dashboards"] == []


def test_brief_hidden_without_portfolio_access(env, monkeypatch):
    monkeypatch.setattr(e1_reports, "listing", lambda plane: [{"name": "Monthly report", "versions": [{"id": "rv-1", "status": "issued", "issued_at": datetime(2026, 10, 1)}]}])
    monkeypatch.setattr(D.access, "visible_portfolios", lambda plane, viewer: set())
    assert get(env, "Daniel", "acc-d")["brief"] is None


def test_brief_is_the_latest_issued_report_and_its_link_resolves(env, monkeypatch):
    assert get(env, "Daniel", "acc-d")["brief"] is None
    vs = [{"id": "rv-old", "status": "issued", "issued_at": datetime(2026, 9, 1)}, {"id": "rv-new", "status": "issued", "issued_at": datetime(2026, 10, 1)},
          {"id": "rv-draft", "status": "draft", "issued_at": datetime(2026, 10, 5)}]
    monkeypatch.setattr(e1_reports, "listing", lambda plane: [{"name": "Monthly report", "versions": vs}])
    monkeypatch.setattr(D.access, "visible_portfolios", lambda plane, viewer: {"pf-1"})  # Daniel sees a portfolio
    b = get(env, "Daniel", "acc-d")["brief"]
    assert b == {"report_version_id": "rv-new", "title": "Monthly report", "link": "/centre/consume/brief/rv-new"}
    from pathlib import Path  # the page the link opens is mounted in the UI routes
    assert 'path: "consume/brief/:reportVersionId"' in (Path(__file__).parents[2] / "ui/src/v1/k4/routes.tsx").read_text(encoding="utf-8")
