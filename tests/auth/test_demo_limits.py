"""Public-demo guards: the daily model cap at the router, the per-account chat rate limit, the super-admin switch. Stub models; no spend."""
import json
from datetime import datetime, timezone

import pytest

from sh_platform import demo_limits as D
from sh_platform.egress.errors import EgressBlocked
from sh_platform.v1 import router as R



def _row(usd, at=None):
    return json.dumps({"at": at or datetime.now(timezone.utc).isoformat(timespec="seconds"), "cost_usd": usd}) + "\n"


def test_cap_counts_only_today_and_is_off_in_dev(tmp_path, monkeypatch):
    log = tmp_path / "model_costs.jsonl"
    log.write_text(_row(0.9) + _row(0.9) + _row(50, "2020-01-01T00:00:00+00:00"), encoding="utf-8")
    monkeypatch.delenv("SH_MODE", raising=False)
    monkeypatch.delenv("SH_DAILY_MODEL_CAP_USD", raising=False)
    assert not D.over_cap(log)  # dev: no cap unless set
    monkeypatch.setenv("SH_DAILY_MODEL_CAP_USD", "2")
    assert not D.over_cap(log) and abs(D.spent_today(log) - 1.8) < 1e-9
    log.write_text(log.read_text() + _row(0.2), encoding="utf-8")
    assert D.over_cap(log)
    monkeypatch.setenv("SH_DAILY_MODEL_CAP_USD", "0")
    assert not D.over_cap(log)
    monkeypatch.delenv("SH_DAILY_MODEL_CAP_USD")
    monkeypatch.setenv("SH_MODE", "prod")
    assert D.daily_cap_usd() == 2.0  # the prod default


class _Plane:
    def __init__(self, folder):
        self.folder = folder

    def area(self, name):
        return self.folder


class _Base:
    route_env = {}


def test_router_refuses_over_cap_and_sends_nothing(tmp_path, monkeypatch):
    (tmp_path / R.COST_LOG).write_text(_row(3.0), encoding="utf-8")
    monkeypatch.setenv("SH_DAILY_MODEL_CAP_USD", "2")
    rm = R.RoutedModel(_Base(), _Plane(tmp_path), "north", "reply", "specialist", build=lambda *a: pytest.fail("a client was built"))
    with pytest.raises(EgressBlocked) as e:
        rm.complete("m1", [{"role": "user", "content": "hi"}])
    assert e.value.reason_code == "daily_cap" and "allowance" in e.value.message


def test_turn_limiter_window():
    now = [0.0]
    lim = D.TurnLimiter(lambda: now[0])
    assert all(lim.allow("a", 3) for _ in range(3)) and not lim.allow("a", 3)
    assert lim.allow("b", 3)  # per account
    now[0] = 3601
    assert lim.allow("a", 3)
    assert lim.allow("a", 0)  # 0 = off


def test_chat_route_pattern():
    ok = ["/api/intents/i1/north/turns", "/api/v1/intents/chat", "/api/v1/intents/i1/chat", "/api/v1/consume/chat", "/api/v1/build/chat",
          "/api/modules/m2_baseline/baselines/b1/lens/ask"]
    assert all(D.CHAT_ROUTE.match(p) for p in ok) and not D.CHAT_ROUTE.match("/api/intents/i1/notes")


def test_middleware_limits_chat_turns_per_account(kit, monkeypatch):
    monkeypatch.setenv("SH_CHAT_TURNS_PER_HOUR", "2")
    kit.app.router.add_api_route("/api/v1/consume/chat", lambda: {"ok": True}, methods=["POST"])
    kit.app.state.route_permissions.routes["POST /api/v1/consume/chat"] = type(kit.app.state.route_permissions.routes["POST /api/t/write"])(
        **kit.app.state.route_permissions.routes["POST /api/t/write"].__dict__)
    c, _, _ = kit.login("chatty")
    h = {"X-CSRF-Token": c.cookies["sh_csrf"]}
    assert [c.post("/api/v1/consume/chat", headers=h).status_code for _ in range(3)] == [200, 200, 429]


def test_superadmin_closed_in_prod_unless_enabled(monkeypatch):
    monkeypatch.setenv("SH_MODE", "prod")
    monkeypatch.delenv("SH_ENABLE_SUPERADMIN", raising=False)
    assert not D.superadmin_open() and not D.real_mode_allowed()
    monkeypatch.setenv("SH_ENABLE_SUPERADMIN", "1")
    assert D.superadmin_open()


def test_chat_route_pattern_covers_every_agent_room():
    more = ["/api/v1/consume/brief/i1/chat", "/api/v1/build/p/p1/chat", "/api/v1/build/i1/blueprint/chat", "/api/v1/cases/c1/ask_finance",
            "/api/company/build/proposals/p1/ask", "/api/modules/m1_intent/sessions/s1/room/messages", "/api/v1/intents/i1/chat/files"]
    assert all(D.CHAT_ROUTE.match(p) for p in more)


def test_gateway_caps_and_logs_unrouted_calls(tmp_path, monkeypatch):
    """A call that skips the router still counts toward the cap, and is refused once the cap is reached. Stub transport; no spend."""
    from sh_platform.egress.gateway import COST_LOG
    from sh_platform.plane import PlaneStore
    from tests.egress.egress_helpers import Transport, make_gateway

    plane = PlaneStore(tmp_path).create("acme-co")
    wire = Transport(json.dumps({"text": "hi", "model": "x/unlisted", "usage": {"tokens_in": 10**6, "tokens_out": 10**6}}))
    gw = make_gateway(plane, wire)[0]
    monkeypatch.setenv("SH_DAILY_MODEL_CAP_USD", "0.01")
    gw.send_model_prompt("m1", {"messages": [{"role": "user", "content": "hello"}]})
    rows = [json.loads(x) for x in (plane.area("context") / COST_LOG).read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["routed"] is False and rows[-1]["cost_usd"] > 0.01
    with pytest.raises(EgressBlocked) as e:
        gw.send_model_prompt("m1", {"messages": [{"role": "user", "content": "again"}]})
    assert e.value.reason_code == "daily_cap" and len(wire.calls) == 1


def test_signed_in_routes_stay_open_when_superadmin_is_off(monkeypatch):
    """Railway 12 Oct: `GET /api/auth/me` is {authenticated, roles: [super_admin]}; the public-demo gate must not close it."""
    from sh_platform.auth import AuthMiddleware
    from types import SimpleNamespace as NS
    monkeypatch.delenv("SH_ENABLE_SUPERADMIN", raising=False)
    mw = AuthMiddleware.__new__(AuthMiddleware)
    mw.owner = None
    mw.perms = NS(routes={"GET /api/auth/me": NS(roles={"super_admin"}, authenticated=True, public=False, guest=False)})
    import sh_platform.auth as auth
    monkeypatch.setattr(auth, "_key_for", lambda owner, scope: "GET /api/auth/me")
    monkeypatch.setattr(auth, "guest_for", lambda owner, scope: None)
    mw._session = lambda cookie: None
    scope = {"type": "http", "method": "GET", "path": "/api/auth/me", "headers": []}
    assert mw._check(scope, {}) == "expired"  # not signed in: told so, not refused
