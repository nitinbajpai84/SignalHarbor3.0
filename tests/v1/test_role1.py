"""ROLE1 (12 Oct): who holds which seat in the Evergreen story. Mei is the business owner, Leo the data engineer and ops manager, Anita the head of data."""
import pytest

from sh_platform.auth.permissions import load_permissions
from sh_platform.v1 import seats as S
from tools import seed_evergreen as EG

MEI = {"owner"}
LEO = {"analyst"}
ANITA = {"analyst", "head_of_data"}


def roles_of(name: str) -> set[str]:
    role = {n: r for n, _, r in EG.PEOPLE}[name]
    return {role, *EG.EXTRA_ROLES.get(name, [])}


def test_the_seeded_people_hold_the_agreed_roles():
    assert roles_of("Daniel Foo") == {"sponsor"} and roles_of("Mei Chen") == MEI and roles_of("Raj Patel") == {"approver"}
    assert roles_of("Anita Rao") == ANITA and roles_of("Leo Park") == LEO
    assert roles_of("Grace Ong") == {"company_admin"} and roles_of("Sofia Reyes") == {"participant"}


def test_mei_holds_no_data_team_seat_but_can_read():
    assert S.seat_of(MEI) == {S.CONSUMER}


def test_leo_is_engineer_and_ops_but_cannot_approve_and_anita_can():
    assert {S.ARCHITECT, S.DATA_ENGINEER, S.OPS_MANAGER} <= S.seat_of(LEO) and S.HEAD_OF_DATA not in S.seat_of(LEO)
    assert S.HEAD_OF_DATA in S.seat_of(ANITA)


def test_leo_cannot_approve_a_design_pack_a_build_plan_or_a_model_change_but_anita_can():
    from sh_platform.v1 import b10_pack, b6_plan, e0a_catalogue
    from sh_platform.profile.view import Viewer
    leo, anita = Viewer("Leo Park", frozenset(LEO), False, "a-leo"), Viewer("Anita Rao", frozenset(ANITA), False, "a-anita")
    for approve in (lambda v: b6_plan.approve(None, v, "p"), lambda v: b10_pack.approve(None, v, "p"), lambda v: e0a_catalogue.approve(None, v, 2)):
        with pytest.raises(Exception) as e:
            approve(leo)
        assert getattr(e.value, "status", None) == 403, e.value
        try:
            approve(anita)  # past the seat check she meets the missing plane, never a 403 about her seat
        except Exception as e2:  # noqa: BLE001
            assert getattr(e2, "status", None) != 403 or "head of data" not in str(getattr(e2, "message", e2)).lower(), e2


OWNER_JOURNEY = [  # what Mei does: talk to North, read Action, read Consume and ask Lumen, read the map
    "POST /api/v1/intents/chat", "GET /api/v1/intents/open", "GET /api/v1/intents/{iid}/chat", "POST /api/v1/intents/{iid}/chat", "POST /api/v1/intents/{iid}/send-to-build",
    "GET /api/v1/trail", "GET /api/v1/consume/p/{pid}/dashboards", "GET /api/v1/consume/dashboards/{did}/view", "POST /api/v1/consume/chat",
    "POST /api/v1/consume/p/{pid}/dashboards/{did}/ask", "GET /api/company/graph", "GET /api/company/register", "GET /api/company/feeds",
]
DATA_TEAM_ONLY = ["GET /api/v1/ops", "GET /api/v1/connectors", "GET /api/v1/jobs", "GET /api/v1/instruments", "GET /api/company/build/pipelines", "GET /api/v1/ops/pipelines", "GET /api/v1/ops/runs", "GET /api/v1/ops/runs/{run_id}", "POST /api/v1/build/p/{pid}/studio"]


def test_server_lets_the_owner_do_her_journey_and_not_the_data_teams_tools():
    perms = load_permissions().routes
    for key in OWNER_JOURNEY:
        assert key in perms, key
        assert "owner" in perms[key].roles, key
    for key in DATA_TEAM_ONLY:
        assert key in perms, key
        assert "owner" not in perms[key].roles, key
