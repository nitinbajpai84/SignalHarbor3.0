"""DS1: the dashboard studio. Lifecycle, approval, Consume lists published only, the grid, Lumen into a slot, refresh facts, default deny."""
import json
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.profile.view import Viewer
from sh_platform.v1 import b7_routes
from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1.p1_project import Refused
from tests.v1.test_cx import ADMIN, GOLD, _user, env  # noqa: F401 - env is a fixture

HEAD = Viewer(name="Head of data", roles=frozenset({"analyst"}), account_id="acc-head")
SPONSOR = Viewer(name="Sponsor", roles=frozenset({"sponsor"}), account_id="acc-sp")
READER = Viewer(name="Chia", roles=frozenset({"participant"}), account_id="acc-c")


def draft(plane, pid, viewer=ADMIN):
    d = S.create(plane, viewer, pid, "Board pack")
    S.add_widget(plane, viewer, pid, d["id"], {"kind": "line", "table": GOLD, "row": 0, "col": 0, "size": "wide"})
    return d


def publish(plane, pid, d, approver=HEAD):
    D.submit(plane, ADMIN, pid, d["id"])
    return D.decide_version(plane, approver, pid, d["id"], True)


def first_widget(plane, pid, d):
    return S.view(plane, ADMIN, pid, d["id"])["layout"]["items"][0]["id"]


def test_lifecycle_maker_cannot_approve_head_can(env):
    plane, pid = env
    d = draft(plane, pid)
    assert S.view(plane, ADMIN, pid, d["id"])["status"] == "draft"
    D.submit(plane, ADMIN, pid, d["id"])
    with pytest.raises(Refused) as e:
        D.decide_version(plane, ADMIN, pid, d["id"], True)  # the maker, even as company admin
    assert e.value.status == 403
    with pytest.raises(Refused):
        D.decide_version(plane, READER, pid, d["id"], True)
    assert S.view(plane, HEAD, pid, d["id"])["can"]["approve"] and not S.view(plane, ADMIN, pid, d["id"])["can"]["approve"]
    rec = D.decide_version(plane, HEAD, pid, d["id"], True)
    assert rec["lifecycle"]["status"] == "published" and rec["lifecycle"]["approved_by_name"] == "Head of data" and rec["lifecycle"]["published"]["version"] == 1


def test_the_approver_sees_what_lumen_checked_and_nobody_else_does(env):
    """V6 (design D3): the approver's panel has who built it and the checks, each from a record; a missing record is "not checked", never a pass."""
    plane, pid = env
    d = draft(plane, pid)
    D.submit(plane, ADMIN, pid, d["id"])
    assert S.view(plane, ADMIN, pid, d["id"])["review"] is None                      # the maker has no approval panel
    r = S.view(plane, HEAD, pid, d["id"])["review"]
    assert r["submitted_by"] and [c["title"] for c in r["checks"]] == ["The month's numbers", "Every tile names where it comes from",
                                                                         "The benchmark is the signed definition", "Readers are the people on the project"]
    by = {c["title"]: c for c in r["checks"]}
    assert by["The month's numbers"]["ok"] is None and by["The benchmark is the signed definition"]["ok"] is None   # no review in this world: not checked
    assert by["Every tile names where it comes from"]["ok"] is True and "Reads" in by["Every tile names where it comes from"]["detail"]


def test_sponsor_can_approve_and_send_back_needs_a_reason(env):
    plane, pid = env
    d = draft(plane, pid)
    D.submit(plane, ADMIN, pid, d["id"])
    with pytest.raises(Refused) as e:
        D.decide_version(plane, SPONSOR, pid, d["id"], False, "")
    assert e.value.status == 400
    back = D.decide_version(plane, SPONSOR, pid, d["id"], False, "Add cash by entity")
    assert back["lifecycle"]["status"] == "draft" and back["lifecycle"]["sent_back"]["reason"] == "Add cash by entity"
    with pytest.raises(Refused):  # nothing is waiting any more
        D.decide_version(plane, SPONSOR, pid, d["id"], True)


def test_empty_dashboard_cannot_be_submitted(env):
    plane, pid = env
    d = S.create(plane, ADMIN, pid, "Empty")
    with pytest.raises(Refused) as e:
        D.submit(plane, ADMIN, pid, d["id"])
    assert e.value.status == 400


def test_consume_lists_published_only(env):
    plane, pid = env
    d = draft(plane, pid)
    cio = _user(plane, "Chia", "acc-c", entity=True)
    D.set_audience(plane, ADMIN, pid, d["id"], [cio])
    assert D.list_for(plane, ADMIN, pid) == [] and D.shared_with(plane, READER) == []
    with pytest.raises(Refused) as e:
        D.get_published(plane, ADMIN, pid, d["id"])
    assert e.value.status == 404
    D.submit(plane, ADMIN, pid, d["id"])
    assert D.list_for(plane, ADMIN, pid) == [] and D.shared_with(plane, READER) == []  # waiting is not published
    D.decide_version(plane, HEAD, pid, d["id"], True)
    assert [x["title"] for x in D.list_for(plane, ADMIN, pid)] == ["Board pack"]
    assert [x["title"] for x in D.shared_with(plane, READER)] == ["Board pack"]
    assert D.get_published(plane, READER, pid, d["id"])["layout"]["items"][0]["kind"] == "line"


def test_edit_keeps_published_visible_until_the_new_version_is_approved(env):
    plane, pid = env
    d = draft(plane, pid)
    publish(plane, pid, d)
    S.set_layout(plane, ADMIN, pid, d["id"], {"rows": 3, "title": "Board pack v2", "items": [{"id": first_widget(plane, pid, d), "row": 1, "col": 3, "size": "medium"}]})
    v = S.view(plane, ADMIN, pid, d["id"])
    assert v["status"] == "draft" and v["version"] == 2 and v["published_version"] == 1 and v["title"] == "Board pack v2"
    pub = D.get_published(plane, ADMIN, pid, d["id"])
    assert pub["title"] == "Board pack" and (pub["layout"]["items"][0]["row"], pub["layout"]["items"][0]["col"]) == (0, 0)
    assert D.list_for(plane, ADMIN, pid)[0]["title"] == "Board pack"
    publish(plane, pid, d)
    assert D.get_published(plane, ADMIN, pid, d["id"])["title"] == "Board pack v2" and D._load(plane, pid, d["id"])["lifecycle"]["published"]["version"] == 2


def test_submitted_dashboard_cannot_be_changed_until_sent_back(env):
    plane, pid = env
    d = draft(plane, pid)
    D.submit(plane, ADMIN, pid, d["id"])
    with pytest.raises(Refused) as e:
        S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "note", "text": "x", "row": 1, "col": 0})
    assert e.value.status == 409


def test_legacy_dashboard_counts_as_published_and_edits_into_a_new_version(env):
    plane, pid = env
    old = D.create(plane, ADMIN, pid, "Old one")
    assert "lifecycle" not in old and D.status_of(old) == "published"
    assert [x["id"] for x in D.list_for(plane, ADMIN, pid)] == [old["id"]] and D.get_published(plane, ADMIN, pid, old["id"])["title"] == "Old one"
    S.add_widget(plane, ADMIN, pid, old["id"], {"kind": "note", "text": "Hello", "row": 0, "col": 0})
    v = S.view(plane, ADMIN, pid, old["id"])
    assert v["status"] == "draft" and v["version"] == 2
    assert D.get_published(plane, ADMIN, pid, old["id"])["layout"] is None  # the old dashboard is untouched for readers


def test_two_editors_on_one_copy_the_second_save_is_refused_not_lost(env):
    plane, pid = env
    d = draft(plane, pid)
    seen = S.view(plane, ADMIN, pid, d["id"])  # both editors open the same copy
    wid = seen["layout"]["items"][0]["id"]
    S.set_layout(plane, ADMIN, pid, d["id"], {"rev": seen["rev"], "items": [{"id": wid, "row": 1, "col": 0, "size": "wide"}]})
    with pytest.raises(Refused) as e:
        S.set_layout(plane, ADMIN, pid, d["id"], {"rev": seen["rev"], "items": [{"id": wid, "row": 0, "col": 6, "size": "medium"}]})
    assert e.value.status == 409 and S.view(plane, ADMIN, pid, d["id"])["layout"]["items"][0]["row"] == 1  # the first change stands
    now = S.view(plane, ADMIN, pid, d["id"])
    S.set_layout(plane, ADMIN, pid, d["id"], {"rev": now["rev"], "items": [{"id": wid, "row": 0, "col": 6, "size": "medium"}]})  # after a reload it goes in
    S.set_layout(plane, ADMIN, pid, d["id"], {"items": [{"id": wid, "row": 0, "col": 0, "size": "medium"}]})  # no rev: as before, no check


def test_slots_move_and_resize_are_persisted_and_checked(env):
    plane, pid = env
    d = S.create(plane, ADMIN, pid, "Grid")
    a = S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "bar", "table": GOLD, "row": 0, "col": 0, "size": "medium"})
    b = S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "figure", "table": GOLD, "row": 0, "col": 6, "size": "full"})
    assert b["size"] == "medium"  # a full widget does not fit in half a row: it takes the largest size that does
    with pytest.raises(Refused):  # taken slot
        S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "note", "text": "x", "row": 0, "col": 2})
    with pytest.raises(Refused):  # off the grid
        S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "note", "text": "x", "row": 5, "col": 0})
    S.set_layout(plane, ADMIN, pid, d["id"], {"rows": 4, "items": [{"id": a["id"], "row": 2, "col": 3, "size": "wide"}, {"id": b["id"], "row": 0, "col": 0, "size": "full"}]})
    items = {i["id"]: i for i in S.view(plane, ADMIN, pid, d["id"])["layout"]["items"]}
    assert (items[a["id"]]["row"], items[a["id"]]["col"], items[a["id"]]["size"]) == (2, 3, "wide") and items[b["id"]]["size"] == "full"
    assert S.view(plane, ADMIN, pid, d["id"])["layout"]["rows"] == 4
    for bad in ([{"id": a["id"], "row": 0, "col": 6, "size": "wide"}],  # runs past column 12
                [{"id": a["id"], "row": 0, "col": 0, "size": "full"}, {"id": b["id"], "row": 0, "col": 0, "size": "small"}],  # overlap
                [{"id": "w-nope", "row": 0, "col": 0, "size": "small"}]):
        with pytest.raises(Refused):
            S.set_layout(plane, ADMIN, pid, d["id"], {"items": bad})
    S.set_layout(plane, ADMIN, pid, d["id"], {"rows": 4, "items": [{"id": b["id"], "row": 0, "col": 0, "size": "full"}]})  # leaving one out takes it off the grid
    assert len(S.view(plane, ADMIN, pid, d["id"])["layout"]["items"]) == 1


@pytest.mark.parametrize("kind,view", [("figure", "figure"), ("table", "table"), ("status", "status"), ("line", None), ("bar", None), ("area", None)])
def test_each_widget_reads_a_gold_table_and_runs(env, kind, view):
    plane, pid = env
    d = S.create(plane, ADMIN, pid, "Kinds")
    w = S.add_widget(plane, ADMIN, pid, d["id"], {"kind": kind, "table": GOLD, "row": 0, "col": 0, "size": "wide"})
    v = S.view(plane, ADMIN, pid, d["id"])
    assert v["layout"]["items"][0]["reads"] == ["monthly report holdings"]
    got = S.tile_data(plane, ADMIN, pid, d["id"], w["tile"])
    assert got["rows"] and got["data_used"]["tables"] == [GOLD]
    if view:
        assert got["spec"]["usermeta"]["view"] == view


def test_figure_reads_the_newest_two_periods_and_a_note_needs_text(env):
    plane, pid = env
    d = S.create(plane, ADMIN, pid, "F")
    w = S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "figure", "table": GOLD, "row": 0, "col": 0})
    rows = S.tile_data(plane, ADMIN, pid, d["id"], w["tile"])["rows"]
    assert [r["value"] for r in rows] == [175.0, 150.0]  # September then August
    with pytest.raises(Refused):
        S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "note", "text": " ", "row": 1, "col": 0})
    with pytest.raises(Refused):  # a table of another project
        S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "table", "table": "gold_other_x", "row": 1, "col": 0})


SQL = f"select entity, sum(net_worth) as net_worth from {GOLD} group by 1"


def _proposal(plane, viewer, pid, did, title="Net worth by entity", **extra):
    return D.add_proposal(plane, viewer, pid, did, {"title": title, "kpi": "net_worth", "sql": SQL, "spec": {"mark": "bar", "encoding": {"x": {"field": "entity", "type": "nominal"}, "y": {"field": "net_worth", "type": "quantitative"}}}, **extra})


def test_studio_conversation_proposes_then_accept_places_in_the_chosen_slot(env, monkeypatch):
    plane, pid = env
    d = S.create(plane, ADMIN, pid, "Ask")
    seen = {}

    def fake(plane_, viewer, pid_, did, text, *a, **k):
        seen.update(did=did, text=text)
        return {"reply": "I have proposed one tile. It is waiting for you.", "proposals": [_proposal(plane_, viewer, pid_, did)], "dashboard_id": did, "worded_by": "model"}
    monkeypatch.setattr(L, "ask", fake)
    out = S.ask_lumen(plane, ADMIN, pid, d["id"], {"text": "add net worth by entity as bars"})
    assert seen == {"did": d["id"], "text": "add net worth by entity as bars"} and out["worded_by"] == "model" and "waiting for you" in out["reply"]
    v = S.view(plane, ADMIN, pid, d["id"])
    assert v["layout"]["items"] == [] and [t["state"] for t in v["tiles"]] == ["proposed"]  # a proposal is a preview, not a widget
    tid = out["proposals"][0]["id"]
    it = S.accept_tile(plane, ADMIN, pid, d["id"], tid, {"row": 1, "col": 3, "size": "wide"})
    assert (it["row"], it["col"], it["size"]) == (1, 3, "wide")
    v = S.view(plane, ADMIN, pid, d["id"])
    assert v["layout"]["items"][0]["title"] == "Net worth by entity" and v["layout"]["items"][0]["reads"] == ["monthly report holdings"]
    assert [t["state"] for t in v["tiles"]] == ["accepted"]
    with pytest.raises(Refused) as e:  # accepted once only
        S.accept_tile(plane, ADMIN, pid, d["id"], tid, {})
    assert e.value.status == 409


def test_studio_follow_up_on_a_placed_widget_replaces_it_in_place(env, monkeypatch):
    plane, pid = env
    d = S.create(plane, ADMIN, pid, "Ask")
    mid = _proposal(plane, ADMIN, pid, d["id"])
    wid = S.accept_tile(plane, ADMIN, pid, d["id"], mid["id"], {"row": 1, "col": 2})["id"]
    focus = {}

    def follow(plane_, viewer, pid_, did, text, *a, **k):
        focus.update(L.M.focus(plane_, viewer, "lumen", L._convo(pid_, did)) or {})  # the selected widget's tile is the one in focus
        t = _proposal(plane_, viewer, pid_, did, "Net worth by entity, dots", replaces=mid["id"])
        return {"reply": "Changed.", "proposals": [t], "dashboard_id": did, "edited": True}
    monkeypatch.setattr(L, "ask", follow)
    out = S.ask_lumen(plane, ADMIN, pid, d["id"], {"text": "as dots", "widget": wid})
    assert focus["tile"] == mid["id"] and out["edited"] is True
    S.accept_tile(plane, ADMIN, pid, d["id"], out["proposals"][0]["id"], {"row": 0, "col": 0})  # a slot is chosen, but the widget stays where it stood
    v = S.view(plane, ADMIN, pid, d["id"])
    assert len(v["layout"]["items"]) == 1 and v["layout"]["items"][0]["id"] == wid and (v["layout"]["items"][0]["row"], v["layout"]["items"][0]["col"]) == (1, 2)
    assert v["layout"]["items"][0]["title"].endswith("dots") and [t["id"] for t in v["tiles"]] == [out["proposals"][0]["id"]]


def test_not_this_drops_the_proposal_and_a_taken_slot_is_refused_before_accepting(env):
    plane, pid = env
    d = draft(plane, pid)  # a wide line at row 0, col 0
    t = _proposal(plane, ADMIN, pid, d["id"])
    with pytest.raises(Refused):
        S.accept_tile(plane, ADMIN, pid, d["id"], t["id"], {"row": 0, "col": 4})
    assert [x["state"] for x in D._load(plane, pid, d["id"])["tiles"] if x["id"] == t["id"]] == ["proposed"]  # still waiting
    assert S.reject_tile(plane, ADMIN, pid, d["id"], t["id"])["state"] == "rejected"
    assert t["id"] not in [x["id"] for x in D._load(plane, pid, d["id"])["tiles"]]


def test_accept_without_a_slot_takes_the_first_free_one_and_adds_a_row_when_full(env):
    plane, pid = env
    d = S.create(plane, ADMIN, pid, "Fill")
    S.set_layout(plane, ADMIN, pid, d["id"], {"items": [], "rows": 1})
    got = [S.accept_tile(plane, ADMIN, pid, d["id"], _proposal(plane, ADMIN, pid, d["id"], f"T{i}")["id"], {}) for i in range(3)]
    assert [(g["row"], g["col"]) for g in got] == [(0, 0), (0, 6), (1, 0)]
    assert S.view(plane, ADMIN, pid, d["id"])["layout"]["rows"] == 2


def test_studio_ask_is_for_the_dashboards_editor_and_never_makes_a_personal_dashboard(env):
    plane, pid = env
    d = draft(plane, pid)  # made by ADMIN
    other = Viewer(name="Mei", roles=frozenset({"analyst"}), account_id="acc-mei")
    with pytest.raises(Refused) as e:
        S.ask_lumen(plane, other, pid, d["id"], {"text": "show net worth by entity per month as a line chart"})
    assert e.value.status == 403
    assert [r["id"] for r in S.listing(plane, ADMIN, pid)] == [d["id"]]  # nothing else was made on the way


def test_studio_conversation_with_the_real_rules_proposes_accepts_and_edits_in_place(env):
    plane, pid = env
    d = S.create(plane, ADMIN, pid, "Real")
    out = S.ask_lumen(plane, ADMIN, pid, d["id"], {"text": "show net worth by entity per month as a line chart"})
    assert out["proposals"] and out["worded_by"] == "rules" and S.view(plane, ADMIN, pid, d["id"])["layout"]["items"] == []
    wid = S.accept_tile(plane, ADMIN, pid, d["id"], out["proposals"][0]["id"], {"row": 0, "col": 0, "size": "full"})["id"]
    again = S.ask_lumen(plane, ADMIN, pid, d["id"], {"text": "make it dots", "widget": wid})
    assert again["edited"] is True and again["proposals"][0]["replaces"] == out["proposals"][0]["id"]
    S.accept_tile(plane, ADMIN, pid, d["id"], again["proposals"][0]["id"], {})
    v = S.view(plane, ADMIN, pid, d["id"])
    assert [i["id"] for i in v["layout"]["items"]] == [wid] and v["layout"]["items"][0]["size"] == "full"
    assert [x["by"] for x in v["talk"]] == ["person", "lumen", "person", "lumen"]  # the thread is kept per dashboard
    assert S.ask_lumen(plane, ADMIN, pid, d["id"], {"new_talk": True})["proposals"] == [] and S.view(plane, ADMIN, pid, d["id"])["talk"] == []


def test_library_offers_lumen_tiles_not_yet_on_the_grid(env):
    plane, pid = env
    mine = D.create(plane, ADMIN, pid, "Scratch")
    t = L.ask(plane, ADMIN, pid, mine["id"], "net worth by entity per month")["proposals"][0]
    d = S.create(plane, ADMIN, pid, "Studio")
    lib = S.view(plane, ADMIN, pid, d["id"])["library"]
    assert [x["tile_id"] for x in lib["lumen"]] == [t["id"]] and lib["tables"][0]["label"] == "monthly report holdings"
    S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "lumen", "dashboard_id": mine["id"], "tile_id": t["id"], "row": 0, "col": 0})
    v = S.view(plane, ADMIN, pid, d["id"])
    assert v["layout"]["items"][0]["title"] == t["title"] and v["tiles"][0]["state"] == "accepted"


# ---- refresh facts ---------------------------------------------------------------------------------------------------------------

def _pipeline(plane, pid, runs, sched=None):
    b = plane.path("build", pid)
    b.mkdir(parents=True, exist_ok=True)
    (b / "plan-v1.json").write_text(json.dumps({"version": 1, "state": "live", "schedule": sched or {"freq": "daily", "at": "06:00", "day": None},
                                                 "sources": [{"code": "adm"}], "tables": []}), encoding="utf-8")
    (b / "runs.jsonl").write_text("\n".join(json.dumps(r) for r in runs), encoding="utf-8")


def _run(day, status="ok"):
    return {"run_id": f"r{day}", "mode": "live", "status": status, "started": f"2026-10-{day:02d}T06:00:30+00:00", "finished": f"2026-10-{day:02d}T06:02:10+00:00"}


def _health(late):
    return lambda *a, **k: {"sources": [{"code": c, "name": n, "is_late": x} for c, n, x in late]}


def test_refresh_header_facts_from_schedule_and_runs(env, monkeypatch):
    plane, pid = env
    monkeypatch.setattr(S.k3_map, "health", _health([("adm", "Administrator", False)]))
    _pipeline(plane, pid, [_run(9), _run(10)])
    r = S.refresh_status(plane, pid, datetime(2026, 10, 10, 12, 0))
    assert r["words"] == "Updated daily at 06:00 after the pipeline run" and r["last_refreshed"] == "2026-10-10T06:02:10+00:00"
    assert r["next"].startswith("2026-10-11T06:00") and r["warning"] is None and r["link"] is None
    w = S.refresh_status(plane, pid, datetime(2026, 10, 10, 3, 0))  # before today's run: the next one is today
    assert w["next"].startswith("2026-10-10T06:00")
    _pipeline(plane, pid, [_run(10)], {"freq": "weekly", "at": "07:30", "day": "mon"})
    assert S.refresh_status(plane, pid, datetime(2026, 10, 10, 12, 0))["words"] == "Updated every Monday at 07:30 after the pipeline run"


def test_refresh_warns_when_the_last_run_failed_or_a_source_is_late(env, monkeypatch):
    plane, pid = env
    monkeypatch.setattr(S.k3_map, "health", _health([("adm", "Administrator", False)]))
    _pipeline(plane, pid, [_run(9), _run(10, "failed")])
    r = S.refresh_status(plane, pid, datetime(2026, 10, 10, 12, 0))
    assert "failed on 10 Oct" in r["warning"] and "since 9 Oct" in r["warning"] and r["link"] == "/centre/operations" and r["last_run_failed"]
    monkeypatch.setattr(S.k3_map, "health", _health([("adm", "Administrator", True), ("other", "Other", True)]))
    _pipeline(plane, pid, [_run(9)])
    r = S.refresh_status(plane, pid, datetime(2026, 10, 10, 12, 0))
    assert r["warning"] == "Not refreshed since 9 Oct: the Administrator file is late" and r["late_sources"] == ["Administrator"]  # only sources this project reads


def test_refresh_without_a_pipeline_says_so(env):
    plane, pid = env
    r = S.refresh_status(plane, pid, datetime(2026, 10, 10, 12, 0))
    assert r["last_refreshed"] is None and r["next"] is None and r["words"].startswith("No pipeline yet")


# ---- routes: default deny, makers, approvers, Consume --------------------------------------------------------------------------------

@pytest.fixture()
def api(env, monkeypatch):
    plane, pid = env
    cur = {"v": ADMIN}
    monkeypatch.setattr(b7_routes, "viewer_of", lambda request: cur["v"])
    monkeypatch.setattr(b7_routes, "_plane", lambda request: plane)
    app = FastAPI()
    app.include_router(b7_routes.router)
    return plane, pid, TestClient(app), cur


def test_every_studio_route_is_declared_and_defaults_to_deny():
    declared = yaml.safe_load(Path(S.__file__).with_name("b7.permissions.yaml").read_text(encoding="utf-8"))["routes"]
    real = {f"{m} {r.path}" for r in b7_routes.router.routes for m in r.methods}
    assert real == set(declared)
    assert all(not ({"participant", "owner", "approver"} & set(v["roles"])) for v in declared.values())
    makers = [k for k in declared if not k.startswith("GET") and not k.endswith(("approve", "send-back"))]
    assert makers and all(declared[k]["roles"] == ["company_admin", "analyst"] for k in makers)


def test_routes_end_to_end_makers_build_approvers_publish(api):
    plane, pid, c, cur = api
    base = f"/api/v1/build/p/{pid}/studio"
    cur["v"] = READER
    assert c.post(base, json={"title": "x"}).status_code == 403  # a reader cannot make a dashboard
    cur["v"] = ADMIN
    did = c.post(base, json={"title": "Board pack"}).json()["id"]
    got = c.post(f"{base}/{did}/widgets", json={"kind": "line", "table": GOLD, "row": 0, "col": 0, "size": "full"}).json()
    assert got["placed"]["kind"] == "line" and got["dashboard"]["refresh"]["words"]
    assert c.get(f"{base}/{did}/tiles/{got['placed']['tile']}/data").json()["rows"]
    assert c.post(f"{base}/{did}/submit").json()["status"] == "submitted"
    assert c.post(f"{base}/{did}/approve").status_code == 403  # not their own
    cur["v"] = SPONSOR
    seen = c.get(f"{base}/{did}").json()
    assert seen["can"]["approve"] and seen["library"]["tables"] == []
    assert c.put(f"{base}/{did}/layout", json={"items": []}).status_code == 403  # a sponsor approves, never edits
    assert c.post(f"{base}/{did}/send-back", json={}).status_code == 400
    assert c.post(f"{base}/{did}/send-back", json={"reason": "Shorter title"}).json()["sent_back"]["reason"] == "Shorter title"
    cur["v"] = ADMIN
    c.post(f"{base}/{did}/submit")
    cur["v"] = HEAD
    assert c.get(base).json()["dashboards"][0]["waiting_for_you"] is True
    assert c.post(f"{base}/{did}/approve").json()["status"] == "published"
    assert c.post(f"{base}/{did}/approve").status_code == 409
    cur["v"] = ADMIN  # the maker may make it company-wide; a new draft appears, the published one stays
    v = c.put(f"{base}/{did}/layout", json={"items": [{"id": got["placed"]["id"], "row": 0, "col": 0, "size": "full"}], "company_wide": True}).json()
    assert v["status"] == "draft" and v["version"] == 2 and v["company_wide"] is True


def test_consume_routes_show_published_only_and_company_reports(api, monkeypatch):
    from sh_platform.v1 import cx_routes
    plane, pid, c, cur = api
    monkeypatch.setattr(cx_routes, "viewer_of", lambda request: cur["v"])
    monkeypatch.setattr(cx_routes, "_plane", lambda request: plane)
    app = FastAPI()
    app.include_router(cx_routes.router)
    cc = TestClient(app)
    d = draft(plane, pid)
    S.set_layout(plane, ADMIN, pid, d["id"], {"items": [{"id": first_widget(plane, pid, d), "row": 0, "col": 0, "size": "wide"}], "company_wide": True})
    _user(plane, "Chia", "acc-c", entity=True)
    cur["v"] = READER
    assert cc.get("/api/v1/consume/shared").json()["company"] == [] and cc.get(f"/api/v1/consume/dashboards/{d['id']}/view").status_code in (403, 404)
    publish(plane, pid, d)
    got = cc.get("/api/v1/consume/shared").json()["company"]
    assert [x["title"] for x in got] == ["Board pack"] and got[0]["link"] == f"/centre/consume/d/{d['id']}"
    view = cc.get(f"/api/v1/consume/dashboards/{d['id']}/view").json()
    assert view["layout"]["items"][0]["kind"] == "line" and view["tiles"][0]["state"] == "accepted"
    tid = view["tiles"][0]["id"]
    assert cc.get(f"/api/v1/consume/p/{pid}/dashboards/{d['id']}/tiles/{tid}/data").json()["rows"]
    # a tile only in the new draft is not readable in Consume
    S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "bar", "table": GOLD, "row": 1, "col": 0})
    new = [t["id"] for t in D._load(plane, pid, d["id"])["tiles"] if t["id"] != tid][0]
    assert cc.get(f"/api/v1/consume/p/{pid}/dashboards/{d['id']}/tiles/{new}/data").status_code == 404
    assert cc.get(f"/api/v1/consume/p/{pid}/dashboards/{d['id']}/tiles/{new}/why").status_code == 404


# ---- review (DS1) ------------------------------------------------------------------------------------------------------------------
ADMIN2 = Viewer(name="Other admin", roles=frozenset({"company_admin"}), account_id="acc-a2")


def test_anyone_who_changed_the_version_cannot_approve_it(env):
    plane, pid = env
    d = draft(plane, pid)
    S.add_widget(plane, ADMIN2, pid, d["id"], {"kind": "note", "text": "Read me", "row": 1, "col": 0})  # an admin may edit another's dashboard
    D.submit(plane, ADMIN, pid, d["id"])
    with pytest.raises(Refused) as e:
        D.decide_version(plane, ADMIN2, pid, d["id"], True)
    assert e.value.status == 403 and not S.view(plane, ADMIN2, pid, d["id"])["can"]["approve"]
    publish_rec = D.decide_version(plane, HEAD, pid, d["id"], True)
    S.set_layout(plane, ADMIN, pid, d["id"], {"items": S.view(plane, ADMIN, pid, d["id"])["layout"]["items"], "rows": 3})  # a new version: editors start again
    assert publish_rec["lifecycle"]["status"] == "published" and D._load(plane, pid, d["id"])["lifecycle"]["editors"] == [D.who(ADMIN)]


def test_company_wide_takes_effect_only_when_approved(env):
    plane, pid = env
    d = draft(plane, pid)
    publish(plane, pid, d)
    S.set_layout(plane, ADMIN, pid, d["id"], {"items": S.view(plane, ADMIN, pid, d["id"])["layout"]["items"], "company_wide": True})
    assert D.company_reports(plane, ADMIN) == []  # the working copy says so; the published version does not
    publish(plane, pid, d)
    assert [x["id"] for x in D.company_reports(plane, ADMIN)] == [d["id"]]


def test_audience_of_a_never_published_draft_sees_nothing_and_gets_no_card(env):
    from sh_platform.v1 import cx_share
    plane, pid = env
    d = draft(plane, pid)
    D.set_audience(plane, ADMIN, pid, d["id"], [_user(plane, "Chia", "acc-c", entity=True)])
    with pytest.raises(Refused) as e:
        D.get(plane, READER, pid, d["id"])
    assert e.value.status == 403
    assert cx_share.notify(plane, pid, d["id"], "shared")["made"] == []


def test_consume_chat_never_writes_into_a_studio_dashboard(env):
    plane, pid = env
    d = draft(plane, pid)
    assert D.own_dashboard(plane, ADMIN, pid)["id"] != d["id"]


# ---- OP1: the studio is the only place to build; Consume reads and answers ----------------------------------------------------------

def _consume(api, monkeypatch):
    from sh_platform.v1 import cx_routes
    plane, pid, c, cur = api
    monkeypatch.setattr(cx_routes, "viewer_of", lambda request: cur["v"])
    monkeypatch.setattr(cx_routes, "_plane", lambda request: plane)
    app = FastAPI()
    app.include_router(cx_routes.router)
    return plane, pid, c, cur, TestClient(app)


def test_consume_build_routes_refuse_with_a_pointer_to_the_studio(api, monkeypatch):
    plane, pid, c, cur, cc = _consume(api, monkeypatch)
    d = draft(plane, pid)
    publish(plane, pid, d)
    t = D._load(plane, pid, d["id"])["tiles"][0]["id"]
    base = f"/api/v1/consume/p/{pid}/dashboards"
    for r in (cc.post(base, json={"title": "New"}), cc.post(f"{base}/{d['id']}/tiles/{t}/accept"), cc.post(f"{base}/{d['id']}/tiles/{t}/reject")):
        assert r.status_code == 409 and "Dashboards are built in Build \u203a Dashboard studio" in r.json()["message"] and r.json()["link"] == f"/centre/build/p/{pid}/studio"
    cur["v"] = READER
    r = cc.post(base, json={"title": "New"})
    assert r.status_code == 409 and r.json()["link"] is None and "ask the project's analyst" in r.json()["message"].lower()
    assert len(list(D._dir(plane, pid).glob("dash-*.json"))) == 1  # nothing was made


def test_consume_lumen_answers_questions_and_points_build_requests_to_the_studio(api, monkeypatch):
    plane, pid, c, cur, cc = _consume(api, monkeypatch)
    d = draft(plane, pid)
    publish(plane, pid, d)
    ask = f"/api/v1/consume/p/{pid}/dashboards/{d['id']}/ask"
    for text in ("make it dots", "show net worth by entity as bars", "add a line chart of cash"):
        out = cc.post(ask, json={"text": text}).json()
        assert out["proposals"] == [] and out["reply"].startswith("Dashboards are built in Build \u203a Dashboard studio") and out["link"] == f"/centre/build/p/{pid}/studio"
    pic = cc.post(ask, json={"text": "what is this?", "picture": {"name": "a.png", "data": "eA=="}}).json()  # a picture asks for a build too
    assert pic["proposals"] == [] and pic["link"]
    q = cc.post(ask, json={"text": "What does net worth show?"}).json()
    assert q["proposals"] == [] and not q["reply"].startswith("Dashboards are built in")
    assert len(D._load(plane, pid, d["id"])["tiles"]) == 1  # no tile was proposed in the published dashboard
    from sh_platform.v1 import cx_routes
    out = cx_routes.pointer(READER, pid)  # someone who may not build is sent to the analyst, with no link
    assert out["link"] is None and "Ask the project's analyst" in out["reply"] and cx_routes.pointer(ADMIN, pid)["link"]


def test_consume_lists_published_only_and_old_personal_drafts_move_into_the_studio(api, monkeypatch):
    plane, pid, c, cur, cc = _consume(api, monkeypatch)
    mine = D.create(plane, ADMIN, pid, "Started in Consume", personal=True)  # CL1 made these
    rec = D._load(plane, pid, mine["id"])
    rec["tiles"] += [{"id": "t-aaaaaa", "title": "Kept", "kpi": "net_worth", "sql": SQL, "spec": {"mark": "bar"}, "note": "", "state": "accepted"},
                     {"id": "t-bbbbbb", "title": "Waiting", "kpi": "net_worth", "sql": SQL, "spec": {"mark": "bar"}, "note": "", "state": "proposed"}]
    D._save(plane, rec)
    old = D.create(plane, ADMIN, pid, "Shared before")  # made before the studio and not personal: it counts as published
    rec = D._load(plane, pid, old["id"])
    rec["tiles"].append({"id": "t-cccccc", "title": "Old tile", "kpi": "net_worth", "sql": SQL, "spec": {"mark": "bar"}, "note": "", "state": "accepted"})
    D._save(plane, rec)
    studio = D._load(plane, pid, draft(plane, pid)["id"])  # a studio draft is not published either
    got = cc.get(f"/api/v1/consume/p/{pid}/dashboards").json()["dashboards"]
    assert [x["title"] for x in got] == ["Shared before"]  # published only
    row = {r["title"]: r for r in S.listing(plane, ADMIN, pid)}
    assert row["Started in Consume"]["status"] == "draft" and row["Started in Consume"]["created_by"] == D.who(ADMIN)  # a draft of its maker
    assert row["Shared before"]["status"] == "published" and row[studio["title"]]["status"] == "draft"
    v = S.view(plane, ADMIN, pid, mine["id"])
    assert [i["title"] for i in v["layout"]["items"]] == ["Kept"] and [t["title"] for t in v["tiles"] if t["state"] == "proposed"] == ["Waiting"]  # nothing lost
    assert [i["title"] for i in S.view(plane, ADMIN, pid, old["id"])["layout"]["items"]] == ["Old tile"]
    assert cc.get(f"/api/v1/consume/p/{pid}/dashboards/{mine['id']}").status_code == 404  # not in Consume
    assert cc.get(f"/api/v1/consume/p/{pid}/dashboards/{old['id']}").json()["tiles"][0]["title"] == "Old tile"
    # a personal draft stays its maker's own in the studio, as it was in Consume: another maker or admin neither lists, opens nor changes it
    assert "Started in Consume" not in [r["title"] for r in S.listing(plane, HEAD, pid) + S.listing(plane, ADMIN2, pid)]
    for who in (HEAD, ADMIN2):
        with pytest.raises(Refused):
            S.view(plane, who, pid, mine["id"])
    with pytest.raises(Refused):
        S.ask_lumen(plane, ADMIN2, pid, mine["id"], {"text": "make it dots"})
    # the maker can send it for approval like any studio dashboard
    D.submit(plane, ADMIN, pid, mine["id"])
    assert D.status_of(D._load(plane, pid, mine["id"])) == "submitted"


def test_studio_ask_accept_and_reject_routes_are_for_makers(api, monkeypatch):
    plane, pid, c, cur = api
    base = f"/api/v1/build/p/{pid}/studio"
    did = c.post(base, json={"title": "Talk"}).json()["id"]
    out = c.post(f"{base}/{did}/ask", json={"text": "show net worth by entity per month as a line chart"}).json()
    tid = out["proposals"][0]["id"]
    assert out["dashboard"]["layout"]["items"] == [] and out["dashboard"]["talk"][0]["by"] == "person"
    got = c.post(f"{base}/{did}/tiles/{tid}/accept", json={"row": 0, "col": 0, "size": "full"}).json()
    assert got["placed"]["size"] == "full" and got["dashboard"]["layout"]["items"][0]["tile"] == tid
    other = c.post(f"{base}/{did}/ask", json={"text": "make it dots"}).json()["proposals"][0]["id"]
    cur["v"] = READER
    assert c.post(f"{base}/{did}/tiles/{other}/accept", json={}).status_code == 403
    assert c.post(f"{base}/{did}/tiles/{other}/reject").status_code == 403
    cur["v"] = ADMIN
    assert c.post(f"{base}/{did}/tiles/{other}/reject").json()["tiles"][0]["id"] == tid


def test_listing_names_the_maker_and_approver_and_an_adopted_dashboard_has_no_approver(env):
    """UC10-02, UC10-07: every maker sees the project's dashboards, each with the maker's name (never the account id); one published before
    approvals existed has no approver name, so the room can say so; one approved in the studio names its approver."""
    plane, pid = env
    _user(plane, "Nitin Admin", "acc-admin")
    old = D.create(plane, ADMIN, pid, "Old one")  # legacy: no lifecycle
    d = draft(plane, pid)
    publish(plane, pid, d)
    rows = {r["title"]: r for r in S.listing(plane, HEAD, pid)}  # HEAD made neither
    assert set(rows) == {"Old one", "Board pack"}
    assert rows["Old one"]["made_by"] == "Nitin Admin" and rows["Old one"]["approved_by"] is None and rows["Old one"]["status"] == "published"
    assert rows["Board pack"]["approved_by"] == "Head of data"


def test_w3_walk_the_sponsor_who_approved_sees_the_published_dashboard(env):
    plane, pid = env
    d = draft(plane, pid)
    assert not any(x["id"] == d["id"] for x in D.list_for(plane, SPONSOR, pid))
    publish(plane, pid, d, approver=SPONSOR)
    assert any(x["id"] == d["id"] for x in D.list_for(plane, SPONSOR, pid))  # the approver, not in the audience, still sees it
    assert not any(x["id"] == d["id"] for x in D.list_for(plane, READER, pid))


def test_only_a_never_published_draft_can_be_deleted(env):
    plane, pid = env
    d = draft(plane, pid)
    S.delete_draft(plane, ADMIN, pid, d["id"])
    assert d["id"] not in [r["id"] for r in S.listing(plane, ADMIN, pid)]
    sub = draft(plane, pid)
    D.submit(plane, ADMIN, pid, sub["id"])
    with pytest.raises(Refused) as e:
        S.delete_draft(plane, ADMIN, pid, sub["id"])  # waiting for approval
    assert e.value.status == 409
    pub = draft(plane, pid)
    publish(plane, pid, pub)
    S.add_widget(plane, ADMIN, pid, pub["id"], {"kind": "note", "text": "next", "row": 1, "col": 0})  # next version: a draft of a published one
    with pytest.raises(Refused):
        S.delete_draft(plane, ADMIN, pid, pub["id"])


def test_old_never_published_drafts_are_archived_not_deleted(env):
    from datetime import timedelta, timezone
    plane, pid = env
    d, pub = draft(plane, pid), draft(plane, pid)
    publish(plane, pid, pub)
    old = (datetime.now(timezone.utc) - timedelta(days=S.ARCHIVE_DAYS + 1)).isoformat(timespec="seconds")
    for x in (d, pub):
        p = D._file(plane, pid, x["id"]); rec = json.loads(p.read_text()); rec["updated_at"] = old; p.write_text(json.dumps(rec))
    rows = {r["id"]: r["archived"] for r in S.listing(plane, ADMIN, pid)}
    assert rows[d["id"]] is True and rows[pub["id"]] is False  # the published one never leaves the strip


# ---- E: six more ways to show a family office (bullet, waterfall, small multiples, calendar, treemap, KPI strip) ----------------------------

def _kinds_env(env):
    plane, pid = env
    from sh_platform.v1 import wh
    with wh.connect(plane) as con:
        con.execute("create table gold_calls_x (day date, fund varchar, called decimal(18,2), target decimal(18,2), pnl decimal(18,2))")
        con.execute("insert into gold_calls_x values ('2026-09-01','Fund A',10,12,1),('2026-09-01','Fund B',5,4,-2),('2026-09-15','Fund A',20,12,3),('2026-09-15','Fund B',0,4,-1)")
    from sh_platform.v1 import e0a_catalogue as cat
    cat.register_gold(plane, pid, "calls", "x", [{"name": "day", "type": "date"}])
    return plane, pid


@pytest.mark.parametrize("kind,cols", [("bullet", ["name", "value", "target"]), ("waterfall", ["label", "value"]), ("small_multiples", ["x", "grp", "value"]),
                                       ("calendar", ["day", "value"]), ("treemap", ["label", "value"]), ("kpi_strip", ["period", "called", "target", "pnl"])])
def test_new_kinds_build_and_run(env, kind, cols):
    plane, pid = _kinds_env(env)
    t = S.build_tile(plane, pid, kind, "gold_calls_x", measure="called")
    assert t["spec"]["usermeta"]["view"] == kind and D.check_spec(t["spec"], cols) and kind in S.KINDS
    got, rows, _ = D.run_sql(plane, t["sql"])
    assert got == cols and rows


def test_new_kinds_refuse_missing_columns_in_plain_words(env):
    plane, pid = env   # the holdings table has no target column and no usable category beyond entity
    with pytest.raises(Refused) as e:
        S.build_tile(plane, pid, "bullet", GOLD, measure="net_worth")
    assert "target" in e.value.message if hasattr(e.value, "message") else "target" in str(e.value)


def test_a_balance_is_shown_at_the_latest_date_and_a_flow_is_summed_over_time():
    from sh_platform.v1 import b7_studio as S
    q = lambda c: '"' + c + '"'  # noqa: E731
    assert S._latest("gold_cash", "cash_usd", "position_date", q) == ' where "position_date" = (select max("position_date") from "gold_cash")'
    assert S._latest("gold_calls", "call_amount", "due_date", q) == ""  # a flow adds up over time
    assert S._latest("gold_cash", "cash_usd", None, q) == ""  # no date column: nothing to keep


def test_bars_of_a_table_with_two_views_of_the_same_money_are_side_by_side(tmp_path, monkeypatch):
    from sh_platform.v1 import b7_studio as S
    cols = [{"name": "position_date", "type": "DATE"}, {"name": "entity", "type": "VARCHAR"}, {"name": "view_type", "type": "VARCHAR"}, {"name": "cash_usd", "type": "DECIMAL(28,8)"}]
    monkeypatch.setattr(S.D, "gold_tables", lambda plane, pid: [{"name": "gold_cash", "columns": cols}])
    t = S.build_tile(None, "p", "bar", "gold_cash", "cash_usd", None, "entity")
    assert '"view_type"' in t["sql"] and t["spec"]["encoding"]["xOffset"] == {"field": "view_type"}
    assert 'where "position_date" = (select max("position_date")' in t["sql"]


def test_a_widget_can_be_several_rows_tall_and_others_cannot_overlap_it():
    from sh_platform.v1 import b7_studio as S
    tall = {"id": "a", "row": 0, "col": 0, "size": "medium", "h": 2}
    S._check_grid({"rows": 3, "items": [tall, {"id": "b", "row": 1, "col": 6, "size": "medium"}]})
    for bad in ({"rows": 3, "items": [tall, {"id": "b", "row": 1, "col": 3, "size": "medium"}]},  # overlaps the second row of a
                {"rows": 1, "items": [tall]},                                                     # taller than the grid
                {"rows": 6, "items": [dict(tall, h=5)]}):                                          # more than four rows
        with pytest.raises(S.Refused):
            S._check_grid(bad)
    assert S.free_width({"rows": 3, "items": [tall]}, 1, 0) == 0
