"""FIXE1 (12 Oct): rights found by UC6/UC8. The owner and the signing sponsor hand a project over; the owner reads her benchmark sheet; the data team
runs the trade check; the run log names the person; a V1 intent's /charter link lands on its signing page."""
from datetime import date, timedelta
from pathlib import Path

import yaml

from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e1_access, e3b_routes, run_log, wh
from sh_platform.v1 import p1_project as P
from sh_platform.v1 import p2_assign as A
from sh_platform.v1.e1_write import org_id
import pytest

MEI = Viewer("Mei Chen", frozenset({"owner"}), False, "a-mei")
DANIEL = Viewer("Daniel Foo", frozenset({"sponsor"}), False, "a-daniel")
RAJ = Viewer("Raj Patel", frozenset({"approver"}), False, "a-raj")
LEO = Viewer("Leo Park", frozenset({"analyst"}), False, "a-leo")
ANITA = Viewer("Anita Rao", frozenset({"analyst", "head_of_data"}), False, "a-anita")
SOFIA = Viewer("Sofia Reyes", frozenset({"participant"}), False, "a-sofia")
DUE = (date.today() + timedelta(days=5)).isoformat()
V1 = Path(__file__).resolve().parents[2] / "sh_platform" / "v1"


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("acme")
    with wh.connect(plane) as con:
        for v in (MEI, DANIEL, RAJ, LEO):
            con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, is_active, created_at) values (?,?,?,?,?,?,?)",
                        [wh.new_id(), org_id(plane), v.account_id, v.name, v.account_id + "@example.test", True, wh.now()])
    return plane


def _signed_project(plane):
    pid = P.create_project(plane, "int-1", "Monthly view", "Mei Chen", "a-mei")["id"]
    write_json_atomic(plane.path("intents", "int-1", "sow.json"), {"state": "signed", "version": 1, "title": "x", "signature": {"name": "Daniel Foo", "role": "sponsor", "at": "2026-10-11T11:00:00+00:00"}})
    return pid


def test_the_owner_and_the_signing_sponsor_hand_over_and_the_approver_cannot(plane):
    pid = _signed_project(plane)
    assert A.handover(plane, MEI, pid, "Leo Park", "go", DUE)["event"] == "handover"          # the owner who raised it
    assert A.handover(plane, DANIEL, pid, "Leo Park", "go", DUE)["event"] == "handover"       # the sponsor who signed it
    with pytest.raises(A.Refused) as e:
        A.handover(plane, RAJ, pid, "Leo Park", "go", DUE)
    assert e.value.status == 403


def test_handover_route_roles():
    r = yaml.safe_load((V1 / "p2.permissions.yaml").read_text(encoding="utf-8"))["routes"]["POST /api/v1/projects/{pid}/handover"]["roles"]
    assert {"owner", "sponsor"} <= set(r) and "approver" not in r and "participant" not in r


def test_the_owner_reads_her_benchmark_sheet_but_does_not_sign_it():
    routes = yaml.safe_load((V1 / "g3.permissions.yaml").read_text(encoding="utf-8"))["routes"]
    for k, v in routes.items():
        assert ("owner" in v["roles"]) == (k.startswith("GET ")), k


def test_the_data_team_runs_the_trade_check_and_a_participant_cannot(monkeypatch):
    monkeypatch.setattr(e1_access, "visible_portfolios", lambda plane, v: {"p1"})
    monkeypatch.setattr(e1_access, "level", lambda *a, **k: "read")   # the Data team group is read-only on portfolios
    assert e3b_routes._may_run(None, ANITA) and e3b_routes._may_run(None, LEO)
    assert not e3b_routes._may_run(None, SOFIA)
    roles = yaml.safe_load((V1 / "e3b.permissions.yaml").read_text(encoding="utf-8"))["routes"]["POST /api/v1/recon/{code}/run"]["roles"]
    assert {"analyst", "head_of_data"} <= set(roles) and "participant" not in roles


def test_the_run_log_names_the_person_who_ran_the_check(plane, monkeypatch):
    from sh_platform.v1 import e3_recon as R
    monkeypatch.setattr(R, "_run_detail", lambda *a, **k: {"checked": 3, "breaks": [], "opened": []})
    R.run_detail(plane, "cash_by_entity", date(2026, 7, 31), who="Leo Park")
    R.run_detail(plane, "cash_by_entity", date(2026, 7, 31))
    assert [r["who"] for r in run_log.list_runs(plane, kind="recon")] == ["system", "Leo Park"]
    import inspect
    assert "who=v.name" in inspect.getsource(e3b_routes.run)
