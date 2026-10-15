"""V5W-1 assignments: the owner assigns steps or hands a project over; the assignee and the owner are told on Today; events keep history;
only the owner (or an admin) may assign; the Action landing lists what is assigned. Routes are declared."""
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e5_pulse, wh
from sh_platform.v1 import p1_project as P
from sh_platform.v1 import p2_assign as A
from sh_platform.v1.e1_write import org_id

MEI = Viewer("Mei Chen", frozenset({"analyst"}), False, "a-mei")
LEO = Viewer("Leo Park", frozenset({"analyst"}), False, "a-leo")
ANITA = Viewer("Anita Rao", frozenset({"analyst", "head_of_data"}), False, "a-anita")   # V6: the head of data approves plans
RINA = Viewer("Rina Rao", frozenset({"participant"}), False, "a-rina")
ADMIN = Viewer("Arjun Mehta", frozenset({"company_admin"}), False, "a-arjun")
TODAY = date(2026, 10, 12)
DUE = (date.today() + timedelta(days=5)).isoformat()


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("acme")
    with wh.connect(plane) as con:
        for v in (MEI, LEO, RINA, ADMIN):
            con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, is_active, created_at) values (?,?,?,?,?,?,?)",
                        [wh.new_id(), org_id(plane), v.account_id, v.name, v.account_id + "@example.test", True, wh.now()])
    return plane


@pytest.fixture()
def pid(plane):
    return P.create_project(plane, "int-1", "Monthly performance vs benchmark", "Mei Chen", "a-mei")["id"]


def cards(plane, viewer):
    return [i for i in e5_pulse.items(plane, viewer, TODAY) if i["kind"] == "assignment"]


def test_assign_notifies_both_and_keeps_history(plane, pid):
    A.assign(plane, MEI, pid, ["architecture", "pipelines"], "Leo Park", "Please use the administrator file.", DUE)
    assert [c["urgency"] for c in cards(plane, LEO)] == ["needs_me"]
    assert "Mei Chen assigned you" in cards(plane, LEO)[0]["headline"]
    assert [c["urgency"] for c in cards(plane, MEI)] == ["worth_a_look"]
    h = A.history(plane, MEI, pid)
    assert h["open"][0]["steps"] == ["Architecture", "Pipelines"] and h["open"][0]["to"] == "Leo Park"
    assert P.read(plane, pid)["people"]["builder"] == "Leo Park" and P.read(plane, pid)["people"]["raiser"] == "Mei Chen"
    assert A.history(plane, LEO, pid)["project"]["owner"] == "Mei Chen"  # the assignee can now read the project


def test_handover_then_reassign_replaces_and_done_closes(plane, pid):
    A.handover(plane, MEI, pid, "Leo Park", "Over to you", DUE)
    assert A.history(plane, MEI, pid)["open"][0]["steps"] == ["Architecture", "Pipelines", "Dashboards and delivery"]
    A.assign(plane, MEI, pid, ["dashboards"], "Arjun Mehta")
    open_ = {tuple(o["steps"]): o["to"] for o in A.history(plane, MEI, pid)["open"]}
    assert open_ == {("Architecture", "Pipelines"): "Leo Park", ("Dashboards and delivery",): "Arjun Mehta"}
    first = A.history(plane, MEI, pid)["open"][0]["id"]
    with pytest.raises(A.Refused) as e:
        A.finish(plane, MEI, first)  # not the assignee
    assert e.value.status == 403
    A.finish(plane, LEO, first)
    assert [o["to"] for o in A.history(plane, MEI, pid)["open"]] == ["Arjun Mehta"]
    assert len(A.history(plane, MEI, pid)["history"]) == 3  # handover, assign, done: nothing rewritten


def test_refusals(plane, pid):
    for who, steps, to, due, status in [(LEO, ["pipelines"], "Mei Chen", None, 403), (RINA, ["pipelines"], "Leo Park", None, 403),
                                        (MEI, [], "Leo Park", None, 400), (MEI, ["pipelines"], "Nobody Here", None, 400),
                                        (MEI, ["pipelines"], "Leo Park", "2020-01-01", 400), (MEI, ["pipelines"], "Leo Park", "soon", 400)]:
        with pytest.raises(A.Refused) as e:
            A.assign(plane, who, pid, steps, to, "", due)
        assert e.value.status == status
    assert A.events(plane) == []
    A.assign(plane, ADMIN, pid, ["pipelines"], "Leo Park")  # a company admin may assign any project
    with pytest.raises(A.Refused):
        A.history(plane, RINA, "prj-deadbeef")


def test_withdraw_by_assigner_only(plane, pid):
    aid = A.assign(plane, MEI, pid, ["pipelines"], "Leo Park")["id"]
    with pytest.raises(A.Refused):
        A.finish(plane, LEO, aid, "withdraw")
    assert cards(plane, LEO) and cards(plane, MEI)
    A.finish(plane, MEI, aid, "withdraw")
    assert A.history(plane, MEI, pid)["open"] == []
    assert cards(plane, LEO) == [] and cards(plane, MEI) == []  # review: a closed assignment leaves Today


def test_reassign_closes_the_earlier_card(plane, pid):
    A.assign(plane, MEI, pid, ["pipelines"], "Leo Park")
    assert cards(plane, LEO)
    A.assign(plane, MEI, pid, ["pipelines"], "Arjun Mehta")
    assert cards(plane, LEO) == [] and len(cards(plane, ADMIN)) == 1


def test_landing_sections(plane, pid):
    A.assign(plane, MEI, pid, ["architecture"], "Leo Park", "Check the blend", DUE)
    got = A.landing(plane, LEO, TODAY)
    assert [r["title"] for r in got["assigned_to_me"]] == ["Monthly performance vs benchmark"]
    assert got["assigned_to_me"][0]["assigned_by"] == "Mei Chen" and got["assigned_to_me"][0]["due"] == DUE
    assert got["counts"]["assigned_to_me"] == 1 and got["needs_me"] == []  # the assignment card is not repeated under Needs me
    mine = A.landing(plane, MEI, TODAY)
    assert mine["counts"]["assigned_to_me"] == 0 and len(mine["assigned_by_me"]) == 1


def test_landing_waiting_for_my_approval(plane, pid, monkeypatch):
    from sh_platform.v1 import b6_plan
    monkeypatch.setattr(b6_plan, "get", lambda plane, p: {"state": "proposed", "version": 2, "proposed_by": "Mei Chen", "proposed_by_id": "a-mei", "proposed_at": "2026-10-11"})
    from sh_platform.v1 import g1_access as G
    G.join(plane, pid, "Leo Park", "builder", "a-leo")
    G.join(plane, pid, "Anita Rao", "head_of_data", "a-anita")
    got = A.landing(plane, ANITA, TODAY)
    assert [(w["kind"], w["title"]) for w in got["waiting_approval"]] == [("plan", "Plan v2: Monthly performance vs benchmark")]
    assert A.landing(plane, MEI, TODAY)["waiting_approval"] == []  # not your own plan
    assert A.landing(plane, LEO, TODAY)["waiting_approval"] == []  # an analyst who is not the head of data does not approve plans


def test_an_intent_ready_to_sign_waits_in_the_sponsors_action(plane, pid):
    """V6 (walk gap 4): Daniel's Action listed nothing because nobody was named sponsor before the signature; it opens the dedicated sign page."""
    from sh_platform.jsonfile import write_json_atomic
    daniel = Viewer("Daniel Foo", frozenset({"sponsor"}), False, "a-daniel")
    iid = P.read(plane, pid)["intent_id"]
    (plane.path("intents") / iid).mkdir(parents=True, exist_ok=True)
    write_json_atomic(plane.path("intents", iid, "sow.json"), {"state": "draft", "title": "Monthly performance vs benchmark"})
    write_json_atomic(plane.path("intents", iid, "thread.json"), {"state": "sow_ready", "turns": [{"by": "person", "name": "Mei Chen", "at": "2026-10-11T10:28:00+00:00"},
                                                                                                    {"by": "north", "name": "North", "at": "2026-10-11T10:42:00+00:00"}]})
    got = A.landing(plane, daniel, TODAY)["waiting_approval"]
    assert [(w["kind"], w["from"], w["since"], w["link"]) for w in got] == [("intent", "Mei Chen", "2026-10-11", f"/centre/intent/{iid}/sign")]
    assert got[0]["title"].startswith("Sign the intent:")
    assert A.landing(plane, MEI, TODAY)["waiting_approval"] == [] and A.landing(plane, LEO, TODAY)["waiting_approval"] == []   # not the raiser, not a builder
    write_json_atomic(plane.path("intents", iid, "sow.json"), {"state": "signed", "title": "x"})
    assert A.landing(plane, daniel, TODAY)["waiting_approval"] == []


def test_routes_are_declared():
    from sh_platform.v1 import p2_routes
    declared = yaml.safe_load((Path(p2_routes.__file__).parent / "p2.permissions.yaml").read_text())["routes"]
    routes = {f"{m} {r.path}" for r in p2_routes.router.routes for m in r.methods}
    assert routes == set(declared)


def test_builds_dialog_contract(plane, pid):
    """Build's dialog (b9) sends the person's id, a `note`, and `handover: true`; it reads `assignments` (a row per step) and the candidates list."""
    from sh_platform.v1 import p2_routes
    cands = A.candidates(plane, MEI, pid)["people"]
    leo = next(c for c in cands if c["name"] == "Leo Park")
    assert set(leo) == {"id", "name", "role", "open_steps"} and leo["open_steps"] == 0
    A.handover(plane, MEI, pid, leo["id"], "Over to you", DUE)
    rows = A.history(plane, MEI, pid)["assignments"]
    assert [(r["step"], r["assignee_name"], r["note"], r["due"], r["by_name"]) for r in rows] == [
        (s, "Leo Park", "Over to you", DUE, "Mei Chen") for s in ("architecture", "pipelines", "dashboards")]
    assert next(c for c in A.candidates(plane, MEI, pid)["people"] if c["name"] == "Leo Park")["open_steps"] == 3
    assert "GET /api/v1/projects/{pid}/assign/candidates" in {f"{m} {r.path}" for r in p2_routes.router.routes for m in r.methods}
