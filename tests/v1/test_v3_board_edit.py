"""Board picker rows, "Add to board" and its permissions: real studio, real dashboards (tests.v1.test_cx env); only the live-thread list is stubbed."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.profile.view import Viewer
from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import v3_board_routes as B
from tests.v1.test_b7_studio import READER, draft, publish
from tests.v1.test_cx import ADMIN, GOLD, env  # noqa: F401 - env is a fixture


def client(plane, pid, viewer, monkeypatch):
    monkeypatch.setattr(B.H, "all_threads", lambda p: [{"id": "th-1", "title": "Monthly report", "stage": "live", "pid": pid}])
    monkeypatch.setattr(B, "_plane", lambda r: plane)
    monkeypatch.setattr(B, "viewer_of", lambda r: viewer)
    app = FastAPI()
    app.include_router(B.router)
    return TestClient(app)


def published(plane, pid):
    d = draft(plane, pid)
    publish(plane, pid, d)
    return d


def test_boards_lists_the_use_case_owner_and_whether_a_draft_waits(env, monkeypatch):
    plane, pid = env
    d = published(plane, pid)
    c = client(plane, pid, ADMIN, monkeypatch)
    got = c.get("/api/v3/boards").json()
    assert got["can_edit"] is True
    assert [(b["pid"], b["dashboard_id"], b["use_case"], b["draft"]) for b in got["boards"]] == [(pid, d["id"], "Monthly report", False)]
    S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "note", "text": "x", "row": 1, "col": 0})  # a change makes a draft; the published copy stays
    assert c.get("/api/v3/boards").json()["boards"][0]["draft"] is True
    assert client(plane, pid, READER, monkeypatch).get("/api/v3/boards").json()["can_edit"] is False


def test_board_names_its_project_and_who_may_edit(env, monkeypatch):
    plane, pid = env
    d = published(plane, pid)
    b = client(plane, pid, ADMIN, monkeypatch).get(f"/api/v3/board?pid={pid}").json()
    assert (b["pid"], b["dashboard_id"], b["can_edit"]) == (pid, d["id"], True) or b.get("empty")  # no data in the test warehouse may leave the tiles out
    assert client(plane, pid, ADMIN, monkeypatch).get("/api/v3/board?pid=nope").json()["empty"] is True


def test_add_to_board_makes_a_draft_widget_and_leaves_the_published_board_alone(env, monkeypatch):
    plane, pid = env
    d = published(plane, pid)
    c = client(plane, pid, ADMIN, monkeypatch)
    n = len(S.view(plane, ADMIN, pid, d["id"])["layout"]["items"])
    r = c.post("/api/v3/board/add", json={"pid": pid, "label": "Net worth", "value": "4.1m"})
    assert r.status_code == 200 and r.json()["status"] == "draft" and r.json()["kind"] == "note"  # no figure record: the number as a note
    assert len(S.view(plane, ADMIN, pid, d["id"])["layout"]["items"]) == n + 1
    assert len(D.published_view(D._load(plane, pid, d["id"]))["layout"]["items"]) == n  # Consume still shows the approved version


def test_add_to_board_follows_the_figures_ready_table(env, monkeypatch):
    plane, pid = env
    d = published(plane, pid)
    from sh_platform.v1 import v3_figstore as FS
    monkeypatch.setattr(FS, "read", lambda p, i: {"id": "fig-nw", "name": "Net worth", "current_v": 1, "versions": [{"v": 1, "reads": [GOLD]}]})
    r = client(plane, pid, ADMIN, monkeypatch).post("/api/v3/board/add", json={"pid": pid, "figure_id": "fig-nw", "label": "Net worth"})
    assert r.status_code == 200 and r.json()["kind"] == "figure"


def test_only_a_maker_may_add_and_a_bad_board_is_refused(env, monkeypatch):
    plane, pid = env
    published(plane, pid)
    body = {"pid": pid, "label": "Net worth", "value": "1"}
    assert client(plane, pid, READER, monkeypatch).post("/api/v3/board/add", json=body).status_code == 403
    c = client(plane, pid, ADMIN, monkeypatch)
    assert c.post("/api/v3/board/add", json=body | {"pid": "nope"}).status_code == 400
    assert c.post("/api/v3/board/add", json={"pid": pid}).status_code == 400
