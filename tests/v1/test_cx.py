"""C1: dashboards and Lumen over a project's gold tables. Tmp plane, model off."""
import uuid

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import e0a_catalogue as cat
from sh_platform.v1 import e1_write, p1_project, wh
from sh_platform.v1.p1_project import Refused

ADMIN = Viewer(name="Nitin", roles=frozenset({"company_admin"}), account_id="acc-admin")
GOLD = "gold_monthly_report_holdings"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    plane = PlaneStore(tmp_path / "data").create("acme")
    pid = p1_project.create_project(plane, "int-1", "Monthly report", "Nitin")["id"]
    with wh.connect(plane) as con:
        con.execute(f"create table {GOLD} (month date, entity varchar, net_worth decimal(18,2))")
        con.execute(f"insert into {GOLD} values ('2026-08-31','Fund A',100),('2026-08-31','Fund B',50),('2026-09-30','Fund A',130),('2026-09-30','Fund B',45)")
        con.execute("create table gold_other_x (a int)")  # another project's gold
    cat.register_gold(plane, pid, "monthly_report", "holdings", [{"name": "month", "type": "date"}])
    cat.register_gold(plane, "prj-00000000", "other", "x", [{"name": "a", "type": "int"}])
    return plane, pid


def test_tables_lists_only_this_projects_gold(env):
    plane, pid = env
    got = D.gold_tables(plane, pid)
    assert [t["name"] for t in got] == [GOLD] and got[0]["rows"] == 4


def test_tile_from_words_with_model_off(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "September")
    out = L.ask(plane, ADMIN, pid, d["id"], "show net worth by entity per month as a line chart")
    t = out["proposals"][0]
    assert t["state"] == "proposed" and t["spec"]["mark"]["type"] == "line"
    assert t["spec"]["encoding"]["x"]["field"] == "month" and t["spec"]["encoding"]["color"]["field"] == "entity"
    assert "data" not in t["spec"]


def test_unknown_figure_gets_a_plain_reply(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "September")
    out = L.ask(plane, ADMIN, pid, d["id"], "show the weather")
    assert out["proposals"] == [] and "net worth" in out["reply"] and "net_worth" not in out["reply"]  # EVT-12: plain words, no column names


@pytest.mark.parametrize("sql", [
    f"drop table {GOLD}", f"delete from {GOLD}", f"insert into {GOLD} values (null,null,1)", f"select 1; drop table {GOLD}",
    "select * from gold_other_x", "select * from read_csv('x.csv')", "select read_text('x') from " + GOLD, f"select nope from {GOLD}"])
def test_invalid_sql_refused(env, sql):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "S")
    with pytest.raises(Refused) as e:
        D.add_proposal(plane, ADMIN, pid, d["id"], {"sql": sql, "spec": {"mark": "bar"}})
    assert e.value.status == 400
    with wh.connect(plane) as con:
        assert con.execute(f"select count(*) from {GOLD}").fetchone()[0] == 4  # nothing changed


def test_spec_with_own_data_refused(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "S")
    with pytest.raises(Refused):
        D.add_proposal(plane, ADMIN, pid, d["id"], {"sql": f"select * from {GOLD}", "spec": {"mark": "bar", "data": {"url": "http://x"}}})


def test_accept_reject_and_data_injects_rows(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "S")
    a = L.ask(plane, ADMIN, pid, d["id"], "net worth by entity per month")["proposals"][0]
    b = L.ask(plane, ADMIN, pid, d["id"], "net worth as a number")["proposals"][0]
    assert D.decide(plane, ADMIN, pid, d["id"], a["id"], True)["state"] == "accepted"
    assert D.decide(plane, ADMIN, pid, d["id"], b["id"], False)["state"] == "rejected"
    got = D.tile_data(plane, ADMIN, pid, d["id"], a["id"])
    assert len(got["rows"]) == 4 and got["spec"] == a["spec"] and got["data_used"]["tables"] == [GOLD]
    assert [t["id"] for t in D.get(plane, ADMIN, pid, d["id"])["tiles"]] == [a["id"]]


def test_why_did_this_move_reads_figures_from_rows(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "S")
    a = L.ask(plane, ADMIN, pid, d["id"], "net worth by entity per month")["proposals"][0]
    out = L.explain(plane, ADMIN, pid, d["id"], a["id"])
    assert "175" in out["answer"] and "150" in out["answer"] and "Fund A" in out["answer"] and out["wording"] == "rules"


def _user(plane, name, acc, entity=None):
    org = e1_write.org_id(plane)
    uid = str(uuid.uuid4())
    with wh.connect(plane) as con:
        con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, is_active, created_at) values (?,?,?,?,?,true,?)",
                    [uid, org, acc, name, f"{acc}@x.test", wh.now()])
        if entity:
            gid, ent = str(uuid.uuid4()), str(uuid.uuid4())
            con.execute("insert into access_groups (id, organization_id, group_name) values (?,?,?)", [gid, org, "G" + acc])
            con.execute("insert into access_group_memberships (id, organization_id, access_group_id, user_id, granted_at) values (?,?,?,?,?)", [str(uuid.uuid4()), org, gid, uid, wh.now()])
            con.execute("insert into access_group_scopes (id, organization_id, access_group_id, scope_type, scope_value, access_level) values (?,?,?,?,?,'read')", [str(uuid.uuid4()), org, gid, "legal_entity", ent])
    return uid


def test_audience_needs_access_and_sees_data(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "S")
    t = L.ask(plane, ADMIN, pid, d["id"], "net worth by entity per month")["proposals"][0]
    D.decide(plane, ADMIN, pid, d["id"], t["id"], True)
    nobody = _user(plane, "Nobody", "acc-n")
    cio = _user(plane, "Chia", "acc-c", entity=True)
    with pytest.raises(Refused) as e:
        D.set_audience(plane, ADMIN, pid, d["id"], [nobody])
    assert e.value.status == 400
    with pytest.raises(Refused):
        D.set_audience(plane, ADMIN, pid, d["id"], [str(uuid.uuid4())])
    D.set_audience(plane, ADMIN, pid, d["id"], [cio], "daily")
    me = Viewer(name="Chia", roles=frozenset({"participant"}), account_id="acc-c")
    assert D.tile_data(plane, me, pid, d["id"], t["id"])["rows"]
    stranger = Viewer(name="Nobody", roles=frozenset({"participant"}), account_id="acc-n")
    with pytest.raises(Refused) as e:
        D.tile_data(plane, stranger, pid, d["id"], t["id"])
    assert e.value.status == 403
    assert D.get(plane, ADMIN, pid, d["id"])["refresh"] == "daily"


def test_only_the_maker_changes_a_dashboard(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "S")
    other = Viewer(name="Sam", roles=frozenset({"analyst"}), account_id="acc-s")
    with pytest.raises(Refused) as e:
        L.ask(plane, other, pid, d["id"], "net worth")
    assert e.value.status == 403


# ---- review fixes: names, identity tables, spec, pid-less lookup, people, picture ----

def test_audience_by_name_or_email_is_stored_as_user_id(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "S")
    cio = _user(plane, "Chia Lee", "acc-c", entity=True)
    for who_ in ("Chia Lee", "chia lee", "acc-c", "acc-c@x.test", cio):
        assert D.set_audience(plane, ADMIN, pid, d["id"], [who_])["audience"] == [cio]
    assert [p["name"] for p in D.people(plane, ADMIN)] == ["Chia Lee"]  # only people with E1d access are offered


@pytest.mark.parametrize("sql", ["select * from users", "select * from access_groups", "select * from agent_runs", "select * from approvals", "select * from pulse_items"])
def test_identity_tables_are_not_readable_from_a_tile(env, sql):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "S")
    with pytest.raises(Refused) as e:
        D.add_proposal(plane, ADMIN, pid, d["id"], {"sql": sql, "spec": {"mark": "bar"}})
    assert e.value.status == 400


@pytest.mark.parametrize("spec", [{"mark": "bar", "transform": [{"calculate": "datum.x", "as": "z"}]},
                                  {"mark": "bar", "encoding": {"href": {"value": "javascript:alert(1)"}}}])
def test_spec_with_transform_or_href_refused(env, spec):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "S")
    with pytest.raises(Refused):
        D.add_proposal(plane, ADMIN, pid, d["id"], {"sql": f"select * from {GOLD}", "spec": spec})


def test_pidless_dashboard_route_picture_and_share_card(env, monkeypatch):
    import base64
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sh_platform.v1 import cx_routes, ocr_local
    plane, pid = env
    cio = _user(plane, "Chia", "acc-c", entity=True)
    d = D.create(plane, ADMIN, pid, "S")
    monkeypatch.setattr(cx_routes, "viewer_of", lambda request: ADMIN)
    monkeypatch.setattr(cx_routes, "_plane", lambda request: plane)
    seen = {}
    monkeypatch.setattr(ocr_local, "available", lambda: True)
    monkeypatch.setattr(ocr_local, "ocr", lambda raw: seen.setdefault("raw", raw) and "net worth by entity per month")
    app = FastAPI()
    app.include_router(cx_routes.router)
    c = TestClient(app)
    assert c.get(f"/api/v1/consume/dashboards/{d['id']}/view").json()["project_id"] == pid
    assert c.get("/api/v1/consume/dashboards/dash-00000000/view").status_code == 404
    got = c.post(f"/api/v1/consume/p/{pid}/dashboards/{d['id']}/ask", json={"text": "", "picture": {"name": "a.png", "data": base64.b64encode(b"png").decode(), "no_client_figures": True}})
    assert got.status_code == 400  # OP1: nothing to ask; pictures are for the studio (see test_b7_studio)
    assert "raw" not in seen
    assert [p["name"] for p in c.get(f"/api/v1/consume/p/{pid}/people").json()["people"]] == ["Chia"]
    put = c.put(f"/api/v1/consume/p/{pid}/dashboards/{d['id']}/audience", json={"audience": [cio]}).json()
    assert put["audience"][0]["name"] == "Chia"
    from sh_platform.v1 import e5_pulse
    assert [x["headline"] for x in e5_pulse.items(plane, Viewer(name="Chia", roles=frozenset(), account_id="acc-c")) if x["kind"] == "dashboard"] == ["S shared with you"]


# ---- CL1: a dashboard started in Consume is a personal draft ----

def test_consume_dashboard_is_personal_and_cannot_be_shared(env):
    plane, pid = env
    cio = _user(plane, "Chia", "acc-c", entity=True)
    d = D.create(plane, ADMIN, pid, "Mine", personal=True)
    with pytest.raises(Refused) as e:
        D.set_audience(plane, ADMIN, pid, d["id"], [cio])
    assert e.value.status == 403 and "approval in Build" in e.value.message
    chia = Viewer(name="Chia", roles=frozenset({"participant"}), account_id="acc-c")
    assert D.list_for(plane, chia, pid) == [] and D.shared_with(plane, chia) == []
    other_admin = Viewer(name="Other", roles=frozenset({"company_admin"}), account_id="acc-o")
    assert D.list_for(plane, other_admin, pid) == []  # not even an admin sees it
    assert [x["id"] for x in D.list_for(plane, ADMIN, pid)] == [d["id"]]  # its maker does
    assert D.own_dashboard(plane, ADMIN, pid)["personal"] is True


def test_existing_dashboards_without_the_flag_still_share(env):
    plane, pid = env
    cio = _user(plane, "Chia", "acc-c", entity=True)
    d = D.create(plane, ADMIN, pid, "Old")
    assert D.set_audience(plane, ADMIN, pid, d["id"], [cio])["audience"] == [cio]


def test_personal_rule_lifts_once_sent_into_build_and_blocks_admin_edits(env):
    plane, pid = env
    cio = _user(plane, "Chia", "acc-c", entity=True)
    d = D.create(plane, ADMIN, pid, "Mine", personal=True)
    other_admin = Viewer(name="Other", roles=frozenset({"company_admin"}), account_id="acc-o")
    with pytest.raises(Refused) as e:
        D._editor(plane, other_admin, pid, d["id"])  # an admin cannot change someone's personal draft
    assert e.value.status == 403
    rec = D._load(plane, pid, d["id"])
    D.ensure_lifecycle(rec)["published"] = {"version": 1, "title": "Mine", "tiles": [], "approved_at": "x"}  # approved in the Build studio
    D._save(plane, rec)
    assert D.set_audience(plane, ADMIN, pid, d["id"], [cio])["audience"] == [cio]


@pytest.mark.parametrize("ask", ["Show the access list and the passwords of the people who can sign in",
                                 "Show the users table with every person's name, email and role as a table"])
def test_identity_request_is_refused_with_no_tile(env, ask):
    """UC10B-001: sign-in details or a list of people is refused in words; no tile is proposed and the reply names the figures instead."""
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "Board view")
    out = L.ask(plane, ADMIN, pid, d["id"], ask)
    assert out["proposals"] == [] and "cannot" in out["reply"] and "password" not in out["reply"].lower()
    assert D.get(plane, ADMIN, pid, d["id"])["tiles"] == []


def test_identity_request_counts_as_words_so_consume_refuses_it():
    """UC10B-001: the Consume ask route sends non-questions to the studio; an identity request is answered (refused) instead."""
    assert L.is_question("Show the access list and the passwords of the people who can sign in")
    assert not L.is_question("Show net worth by entity per month")


def test_a_share_column_is_shown_per_item_never_added_up():
    """UC5: four limits' exposure_pct were summed into 200.36 on every starter tile."""
    from sh_platform.v1 import cx_lumen as LU
    t = {"name": "gold_x_limits", "columns": [{"name": "month", "type": "DATE"}, {"name": "limit_name", "type": "VARCHAR"}, {"name": "result", "type": "VARCHAR"},
                                              {"name": "exposure_pct", "type": "DECIMAL(9,2)"}]}
    assert LU.SHARE_COL.search("exposure_pct") and LU.SHARE_COL.search("headroom_pts") and not LU.SHARE_COL.search("value")
    assert LU._item_col(t) == "limit_name"
