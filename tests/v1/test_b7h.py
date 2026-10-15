"""STUDIO2 card A: talk, history (undo, restore, compare, withdraw) and the inspector. The model is stubbed."""
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.v1 import b7_routes, b7h_routes
from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import b7h_history as H
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1.p1_project import Refused
from tests.v1.test_b7_studio import HEAD, READER, SPONSOR, _proposal, draft
from tests.v1.test_cx import ADMIN, GOLD, env  # noqa: F401 - env is a fixture


def stub_lumen(monkeypatch, titles):
    def fake(plane, viewer, pid, did, text, *a, **k):
        return {"reply": "Done.", "proposals": [_proposal(plane, viewer, pid, did, t) for t in titles], "dashboard_id": did}
    monkeypatch.setattr(L, "ask", fake)


def items(plane, pid, did):
    return S.view(plane, ADMIN, pid, did)["layout"]["items"]


def test_talk_places_every_proposal_and_records_a_step(env, monkeypatch):
    plane, pid = env
    d = S.create(plane, ADMIN, pid, "Talk")
    stub_lumen(monkeypatch, ["One", "Two"])
    out = H.talk(plane, ADMIN, pid, d["id"], {"text": "show two things"})
    v = S.view(plane, ADMIN, pid, d["id"])
    assert out["reply"] == "Done." and len(out["changed"]) == 2 and {i["id"] for i in v["layout"]["items"]} == set(out["changed"])
    assert all(t["state"] == "accepted" for t in v["tiles"])
    h = H.history(plane, ADMIN, pid, d["id"])
    assert h["now"] == out["step"] and h["steps"][-1]["said"] == "show two things" and h["steps"][0]["summary"] == "Started"


def test_talk_with_a_selected_widget_replaces_its_tile(env, monkeypatch):
    plane, pid = env
    d = draft(plane, pid)
    wid = items(plane, pid, d["id"])[0]["id"]
    stub_lumen(monkeypatch, ["Replacement"])
    out = H.talk(plane, ADMIN, pid, d["id"], {"text": "change it", "widget": wid})
    v = S.view(plane, ADMIN, pid, d["id"])
    assert out["changed"] == [wid] and len(v["layout"]["items"]) == 1 and v["layout"]["items"][0]["title"] == "Replacement" and len(v["tiles"]) == 1


def test_undo_restore_compare(env):
    plane, pid = env
    d = S.create(plane, ADMIN, pid, "Hist")
    a = S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "line", "table": GOLD, "row": 0, "col": 0, "size": "wide"})
    s1 = H.record_step(plane, ADMIN, pid, d["id"], "line", "Added line")
    b = S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "bar", "table": GOLD, "row": 0, "col": 9, "size": "small"})
    s2 = H.record_step(plane, ADMIN, pid, d["id"], "bar", "Added bar")
    assert H.compare(plane, ADMIN, pid, d["id"], s1) == {"added": [b["title"]], "removed": [], "changed": []}
    H.undo(plane, ADMIN, pid, d["id"])
    assert [i["id"] for i in items(plane, pid, d["id"])] == [a["id"]]
    H.undo(plane, ADMIN, pid, d["id"])  # undoing the undo brings the bar back
    assert {i["id"] for i in items(plane, pid, d["id"])} == {a["id"], b["id"]}
    H.restore(plane, ADMIN, pid, d["id"], s1)
    assert [i["id"] for i in items(plane, pid, d["id"])] == [a["id"]]
    H.restore(plane, ADMIN, pid, d["id"], s2)
    assert {i["id"] for i in items(plane, pid, d["id"])} == {a["id"], b["id"]}
    with pytest.raises(Refused) as e:
        H.restore(plane, ADMIN, pid, d["id"], 999)
    assert e.value.status == 404


def test_steps_are_capped_at_fifty(env):
    plane, pid = env
    d = S.create(plane, ADMIN, pid, "Cap")
    for k in range(60):
        H.record_step(plane, ADMIN, pid, d["id"], "", f"s{k}")
    h = H.history(plane, ADMIN, pid, d["id"])
    assert len(h["steps"]) == 50 and h["now"] == h["steps"][-1]["n"]


def test_withdraw_then_edit_and_published_stays(env):
    plane, pid = env
    d = draft(plane, pid)
    D.submit(plane, ADMIN, pid, d["id"])
    wid = items(plane, pid, d["id"])[0]["id"]
    with pytest.raises(Refused) as e:
        H.delete_widget(plane, ADMIN, pid, d["id"], wid)
    assert e.value.status == 409
    assert H.withdraw(plane, ADMIN, pid, d["id"])["status"] == "draft"
    with pytest.raises(Refused):
        H.withdraw(plane, ADMIN, pid, d["id"])
    D.submit(plane, ADMIN, pid, d["id"])
    D.decide_version(plane, HEAD, pid, d["id"], True)
    H.delete_widget(plane, ADMIN, pid, d["id"], wid)  # a published one becomes a new draft version; the published copy is untouched
    rec = D._load(plane, pid, d["id"])
    assert D.status_of(rec) == "draft" and rec["lifecycle"]["version"] == 2 and len(rec["lifecycle"]["published"]["layout"]["items"]) == 1
    assert D.published_view(rec)["layout"]["items"]


def test_inspector_patch_rebuilds_filters_renames_and_styles(env):
    plane, pid = env
    d = draft(plane, pid)
    it = items(plane, pid, d["id"])[0]
    out = H.patch_tile(plane, ADMIN, pid, d["id"], it["tile"], {"kind": "bar", "only": {"column": "entity", "values": ["Fund A"]}})
    v = S.view(plane, ADMIN, pid, d["id"])
    new = v["layout"]["items"][0]
    assert out["ok"] and new["kind"] == "bar" and new["tile"] != it["tile"] and [t["id"] for t in v["tiles"]] == [new["tile"]]
    rows = D.tile_rows(plane, pid, D._load(plane, pid, d["id"]), new["tile"])["rows"]
    assert rows and all(r["entity"] == "Fund A" for r in rows)
    H.patch_tile(plane, ADMIN, pid, d["id"], new["tile"], {"title": "Fund A only", "scale_zero": False, "number_format": "currency", "size": "full"})
    got = S.view(plane, ADMIN, pid, d["id"])
    enc = next(t for t in got["tiles"] if t["id"] == new["tile"])["spec"]["encoding"]["y"]
    assert got["layout"]["items"][0]["title"] == "Fund A only" and got["layout"]["items"][0]["size"] == "full"
    assert enc["scale"]["zero"] is False and enc["format"] == "currency"
    for bad in ({}, {"only": {"column": "nope", "values": ["x"]}}, {"number_format": "weird"}, {"measure": "nope"}):
        with pytest.raises(Refused):
            H.patch_tile(plane, ADMIN, pid, d["id"], new["tile"], bad)
    H.undo(plane, ADMIN, pid, d["id"])  # back to before the rename and style
    assert items(plane, pid, d["id"])[0]["title"] != "Fund A only"


def test_resize_refused_when_the_neighbour_is_in_the_way(env):
    plane, pid = env
    d = draft(plane, pid)
    S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "figure", "table": GOLD, "row": 0, "col": 9, "size": "small"})
    tile = items(plane, pid, d["id"])[0]["tile"]
    with pytest.raises(Refused):
        H.patch_tile(plane, ADMIN, pid, d["id"], tile, {"size": "full"})
    assert H.patch_tile(plane, ADMIN, pid, d["id"], tile, {"size": "medium"})["ok"]


def test_duplicate_and_delete(env):
    plane, pid = env
    d = draft(plane, pid)
    wid = items(plane, pid, d["id"])[0]["id"]
    out = H.duplicate_widget(plane, ADMIN, pid, d["id"], wid)
    v = S.view(plane, ADMIN, pid, d["id"])
    assert len(v["layout"]["items"]) == 2 and out["widget"]["tile"] != v["layout"]["items"][0]["tile"] and len(v["tiles"]) == 2
    H.delete_widget(plane, ADMIN, pid, d["id"], out["widget"]["id"])
    assert len(items(plane, pid, d["id"])) == 1
    with pytest.raises(Refused):
        H.delete_widget(plane, ADMIN, pid, d["id"], "w-nope")


@pytest.fixture()
def api(env, monkeypatch):
    plane, pid = env
    cur = {"v": ADMIN}
    monkeypatch.setattr(b7_routes, "viewer_of", lambda request: cur["v"])
    monkeypatch.setattr(b7_routes, "_plane", lambda request: plane)
    app = FastAPI()
    app.include_router(b7_routes.router)
    app.include_router(b7h_routes.router)
    return plane, pid, TestClient(app), cur


def test_every_route_is_declared_and_makers_only():
    declared = yaml.safe_load(Path(H.__file__).with_name("b7h.permissions.yaml").read_text(encoding="utf-8"))["routes"]
    real = {f"{m} {r.path}" for r in b7h_routes.router.routes for m in r.methods}
    assert real == set(declared) and all(v["roles"] == ["company_admin", "analyst"] for v in declared.values())


def test_routes_end_to_end(api, monkeypatch):
    plane, pid, c, cur = api
    base = f"/api/v1/build/p/{pid}/studio"
    did = c.post(base, json={"title": "R"}).json()["id"]
    stub_lumen(monkeypatch, ["Routed"])
    out = c.post(f"{base}/{did}/talk", json={"text": "hi"}).json()
    assert len(out["changed"]) == 1 and out["step"] >= 1
    c.post(f"{base}/{did}/widgets", json={"kind": "line", "table": GOLD, "row": 1, "col": 0, "size": "full"})
    h = c.get(f"{base}/{did}/history").json()
    assert h["steps"][-1]["summary"].startswith("Added") and h["now"] == h["steps"][-1]["n"]
    assert c.post(f"{base}/{did}/undo").json()["ok"]
    assert len(c.get(f"{base}/{did}").json()["layout"]["items"]) == 1
    assert c.get(f"{base}/{did}/history/{h['steps'][-1]['n']}/compare").json()["added"] == []
    wid = out["changed"][0]
    assert c.post(f"{base}/{did}/widgets/{wid}/duplicate").json()["ok"]
    assert c.delete(f"{base}/{did}/widgets/{wid}").json()["ok"]
    tid = c.get(f"{base}/{did}").json()["layout"]["items"][0]["tile"]
    assert c.patch(f"{base}/{did}/tiles/{tid}", json={"title": "Renamed"}).json()["ok"]
    assert c.post(f"{base}/{did}/withdraw").status_code == 409
    cur["v"] = READER
    assert c.get(f"{base}/{did}/history").status_code == 403 and c.post(f"{base}/{did}/talk", json={"text": "x"}).status_code == 403
    cur["v"] = SPONSOR
    assert c.delete(f"{base}/{did}/widgets/{wid}").status_code == 403
