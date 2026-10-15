"""X3: seats from roles, and require_seat letting the right seat in and refusing the wrong one."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from sh_platform.v1.seats import require_seat, seat_of


def test_seat_table():
    assert seat_of({"sponsor"}) == {"decision_maker", "consumer"}
    assert seat_of({"analyst"}) == {"architect", "data_engineer", "ops_manager", "consumer"}
    assert seat_of({"company_admin"}) == {"decision_maker", "architect", "data_engineer", "ops_manager", "head_of_data", "consumer"}  # V6: the admin keeps the head of data seat
    assert seat_of({"owner"}) == seat_of({"approver"}) == seat_of({"participant"}) == {"consumer"}
    assert seat_of(SimpleNamespace(roles=frozenset())) == set()
    assert seat_of({"super_admin"}) == set()  # the control plane holds no company seat


class _Accounts:
    def get(self, account_id):
        return {"display_name": account_id}

    def in_company(self, company_id):
        return [{"display_name": "a"}]


def _client(roles: list[str], company_id: str | None = "neera") -> TestClient:
    app = FastAPI()
    app.state.account_store = _Accounts()

    @app.middleware("http")
    async def signed_in(request: Request, call_next):
        request.state.company_id, request.state.account_id, request.state.roles = company_id, "a", roles
        return await call_next(request)

    @app.post("/sign")
    def sign(request: Request):
        return {"name": require_seat(request, "decision_maker").name}

    @app.post("/typo")
    def typo(request: Request):
        return require_seat(request, "decision maker")

    return TestClient(app, raise_server_exceptions=True)


def test_decision_maker_signs():
    r = _client(["sponsor"]).post("/sign")
    assert r.status_code == 200 and r.json() == {"name": "a"}


def test_analyst_refused_with_a_sentence():
    r = _client(["analyst"]).post("/sign")
    assert r.status_code == 403
    assert r.json()["detail"] == {"error": "not_allowed", "message": "Only the decision maker can do this."}


def test_no_company_and_unknown_seat():
    assert _client(["sponsor"], company_id=None).post("/sign").json()["detail"]["error"] == "forbidden"
    with pytest.raises(ValueError):
        _client(["sponsor"]).post("/typo")
