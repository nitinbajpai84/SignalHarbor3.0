"""Smoke: sign-in, menu, industry isolation, solo user, module gate, company isolation, sessions, default deny.

Synthetic, illustrative data only. Every test runs on its own copy of the seeded data in tmp_path.
"""
import json
import re

import pytest
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from sh_platform.agents.context import build_context_pack
from sh_platform.agents.registry import ToolRefused, ToolRegistry
from sh_platform.auth import all_routes, route_keys
from sh_platform.auth.permissions import Rule, load_permissions
from sh_platform.plane import CrossCompanyError, require_same_company
from smoke_helpers import CASES, INDUSTRY, disable_account, post, user_of

A, B, EMPTY = (CASES[k]["id"] for k in ("A", "B", "empty"))
M4 = "m4_build"
NOT_AVAILABLE = {"error": "module_not_available", "message": "This module is not part of your plan."}


# ------------------------------------------------------------------ 1. sign-in and menu
def test_signin_me_and_menu_per_company(env, case):
    user = user_of(case["id"])
    c = env.login(user["email"])
    me = c.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["company_id"] == case["id"] and me.json()["roles"] == user["roles"]
    company = c.get("/api/company").json()
    assert company["company_id"] == case["id"] and company["industry"] == INDUSTRY[case["id"]]
    menu = c.get("/api/modules")
    assert menu.status_code == 200
    assert [m["id"] for m in menu.json()] == case["modules"]  # exactly the package; [] for the empty company


def test_wrong_password_is_refused(env):
    from fastapi.testclient import TestClient
    r = TestClient(env.app).post("/api/auth/login", json={"email": user_of(A)["email"], "password": "FAKE-wrong"})
    assert r.status_code == 401 and r.json()["error"] == "login_failed"


# ------------------------------------------------------------------ 2. industry isolation
def _context(env, packs, company_id):
    company = env.entitlements.company(company_id)
    pack = packs.load(company["industry"])
    ctx = build_context_pack({"name": company["name"], "industry": company["industry"]}, pack, [],
                             "What should we track?", max_facts=5)
    return pack, ctx


def test_suggestions_differ_by_industry_and_empty_gets_empty_state(env, packs):
    pa, ctx_a = _context(env, packs, A)
    pb, ctx_b = _context(env, packs, B)
    pe, ctx_e = _context(env, packs, EMPTY)
    assert not pa.empty and not pb.empty and pe.empty
    texts_a = {s["text"] for s in ctx_a["suggestions"]}
    texts_b = {s["text"] for s in ctx_b["suggestions"]}
    assert texts_a and texts_b and texts_a.isdisjoint(texts_b)
    assert all(s["label"] == pa.suggestion_label for s in ctx_a["suggestions"])  # labelled as suggestions
    assert ctx_e["suggestions"] == [] and ctx_e["empty_state"] == pe.message  # honest empty state
    assert not ({"problems", "glossary"} & set(pe.sections()))


def _words(texts):
    return {w for t in texts for w in re.findall(r"[a-z]{6,}", t.lower())}


def test_no_word_of_one_industry_leaks_into_the_other(env, packs):
    _, ctx_a = _context(env, packs, A)
    _, ctx_b = _context(env, packs, B)
    _, ctx_e = _context(env, packs, EMPTY)
    only_a = _words(s["text"] for s in ctx_a["suggestions"]) - _words(s["text"] for s in ctx_b["suggestions"])
    only_b = _words(s["text"] for s in ctx_b["suggestions"]) - _words(s["text"] for s in ctx_a["suggestions"])
    shared = _words(m.description + " " + m.name for m in env.entitlements.catalogue.modules)
    only_a, only_b = only_a - shared, only_b - shared  # words the menu itself uses are not an industry's
    assert only_a and only_b
    menu_b = json.dumps(env.login(user_of(B)["email"]).get("/api/modules").json()).lower()
    menu_a = json.dumps(env.login(user_of(A)["email"]).get("/api/modules").json()).lower()
    blob_b, blob_a = json.dumps(ctx_b).lower() + menu_b, json.dumps(ctx_a).lower() + menu_a
    assert not only_a & _words([blob_b])
    assert not only_b & _words([blob_a])
    blob_e = json.dumps(ctx_e).lower()
    assert not (only_a | only_b) & _words([blob_e])


def test_pack_never_falls_back_to_another_industry(packs):
    assert packs.load("unlisted").empty and packs.load("unlisted", 1).empty


# ------------------------------------------------------------------ 3. solo user
def test_solo_user_home_and_sign_out(env):
    user = user_of(EMPTY)
    assert user["roles"] == ["company_admin", "sponsor"]  # one person, two roles
    c = env.login(user["email"])
    assert c.get("/api/modules").json() == []  # empty-state home list
    assert c.get("/api/company").json()["company_id"] == EMPTY
    out = post(c, "/api/auth/logout")
    assert out.status_code == 200
    assert c.get("/api/auth/me").status_code == 401


def test_solo_user_cannot_reach_any_module_route(env):
    c = env.login(user_of(EMPTY)["email"])
    for mid in env.entitlements.catalogue.ids:
        for path in (f"/api/modules/{mid}", f"/api/modules/{mid}/charter", f"/api/modules/{mid}/a/b"):
            r = c.get(path)
            assert r.status_code == 403 and r.json() == NOT_AVAILABLE, path
    assert env.entitlements.enabled_modules(EMPTY) == []


# ------------------------------------------------------------------ 4. switched-off module, three ways
def _probe_tool(env):
    """A test tool for m4 in a ToolRegistry wired to the real entitlement store (not module code)."""
    reg = ToolRegistry(env.entitlements)
    reg.register(M4, "probe", lambda: {"total": 12, "group_size": 9}, read_only=True,
                 description="Test tool.", parameters={})
    return reg


def _open_close_state(env, c, reg, company_id):
    """(menu has m4, route status for m4 and body, tools listed, call outcome)"""
    in_menu = M4 in [m["id"] for m in c.get("/api/modules").json()]
    r = c.get(f"/api/modules/{M4}/ping")
    listed = [t["name"] for t in reg.tools_for(company_id, M4)]
    try:
        called = reg.call(company_id, M4, "probe", {})
    except ToolRefused:
        called = "refused"
    return in_menu, r, listed, called


def _assert_closed(state):
    in_menu, r, listed, called = state
    assert not in_menu
    assert r.status_code == 403 and r.json() == NOT_AVAILABLE
    assert listed == [] and called == "refused"


def _assert_open(state):
    in_menu, r, listed, called = state
    assert in_menu
    assert r.status_code == 200 and r.json() == {"pong": True}  # passed the gate to a real route
    assert listed == ["probe"] and called == {"total": 12, "group_size": 9}


def _with_m4_route(env):
    env.add_route("get", f"/api/modules/{M4}/ping", lambda: {"pong": True}, Rule(authenticated=True))


@pytest.mark.parametrize("company_id,owns_at_start", [(A, False), (B, True)])
def test_module_off_is_refused_by_menu_route_and_tool_and_follows_the_switch(env, company_id, owns_at_start):
    _with_m4_route(env)
    reg, c = _probe_tool(env), env.login(user_of(company_id)["email"])
    st = lambda: _open_close_state(env, c, reg, company_id)  # noqa: E731
    (_assert_open if owns_at_start else _assert_closed)(st())
    env.entitlements.set_module(company_id, M4, True)
    _assert_open(st())
    env.entitlements.set_module(company_id, M4, False)  # off again: closed at once, same session
    _assert_closed(st())
    env.entitlements.set_module(company_id, M4, True)
    _assert_open(st())


def test_not_owned_module_looks_the_same_as_an_unknown_module(env):
    c = env.login(user_of(A)["email"])
    known_off = c.get(f"/api/modules/{M4}/ping")
    unknown = c.get("/api/modules/m99_nothing/ping")
    assert known_off.status_code == unknown.status_code == 403
    assert known_off.json() == unknown.json() == NOT_AVAILABLE
    assert known_off.headers.get("content-type") == unknown.headers.get("content-type")


def test_agent_tool_refused_for_other_company_even_if_one_company_owns_it(env):
    reg = _probe_tool(env)
    assert [t["name"] for t in reg.tools_for(B, M4)] == ["probe"]
    assert reg.tools_for(A, M4) == []
    with pytest.raises(ToolRefused):
        reg.call(A, M4, "probe", {})
    with pytest.raises(ToolRefused):
        reg.call(EMPTY, M4, "probe", {})


# ------------------------------------------------------------------ 5. cross-company read refused
@pytest.mark.parametrize("attacker,victim", [(B, A), (EMPTY, A), (A, B)],
                         ids=[f"{a}-reads-{v}" for a, v in [(B, A), (EMPTY, A), (A, B)]])
def test_a_user_cannot_steer_the_server_to_another_companys_plane(env, attacker, victim):
    env.planes.plane_for(victim).path("landing", "private.txt").write_text("VICTIM-ONLY-MARKER", encoding="utf-8")
    victim_name = env.entitlements.company(victim)["name"].split(" ", 1)[1]  # drop the "Illustrative" tag
    c = env.login(user_of(attacker)["email"])
    other = {"company_id": victim, "companyId": victim, "company": victim}
    attempts = [
        c.get("/api/company", params=other),
        c.get("/api/company", headers={"X-Company-Id": victim, "X-Company": victim}),
        c.get("/api/modules", params=other, headers={"X-Company-Id": victim}),
        c.request("GET", "/api/company", content=json.dumps(other), headers={"content-type": "application/json"}),
        c.get(f"/api/company/{victim}"),
        c.get(f"/{victim}/landing/private.txt"),
        c.get(f"/data/{victim}/landing/private.txt"),
        c.get(f"/api/modules/m1_intent/../../{victim}/landing/private.txt"),
        c.get(f"/api/modules/m1_intent/%2e%2e/%2e%2e/{victim}/landing/private.txt"),
    ]
    for r in attempts:
        assert "VICTIM-ONLY-MARKER" not in r.text
        assert victim not in r.text and victim_name not in r.text
        if r.status_code == 200 and isinstance(r.json(), dict):
            assert r.json().get("company_id", attacker) == attacker
    assert c.get("/api/company", params=other).json()["company_id"] == attacker


def test_a_company_user_cannot_use_the_admin_switch_on_another_company(env):
    c = env.login(user_of(A)["email"])
    before = env.entitlements.enabled_modules(B)
    r = c.put(f"/api/admin/companies/{B}/modules/{M4}", json={"enabled": False},
              headers={"x-csrf-token": c.cookies.get("sh_csrf")})
    assert r.status_code == 403
    assert env.entitlements.enabled_modules(B) == before
    assert env.entitlements.enabled_modules(A) == CASES["A"]["modules"]


def test_require_same_company_and_plane_paths_fail_closed(env):
    with pytest.raises(CrossCompanyError):
        require_same_company(A, B)
    with pytest.raises(CrossCompanyError):
        require_same_company(A, "../" + B)
    require_same_company(A, A)  # same company: allowed
    plane_a = env.planes.plane_for(A)
    for bad in (f"../{B}/landing/private.txt", f"..\\{B}", "../../_control/accounts.json"):
        with pytest.raises(CrossCompanyError):
            plane_a.path(bad)


def test_no_route_takes_a_company_id_except_the_super_admin_switch(env):
    perms = load_permissions()
    # /api/company/... routes take no id: they serve the signed-in company's own plane
    taking_company = [k for r in all_routes(env.app) for k in route_keys(r) if "{company_id}" in k]
    # only the super admin's switches name a company (IC-5a added the control-plane pair)
    assert sorted(taking_company) == sorted(["PUT /api/admin/companies/{company_id}/modules/{module_id}",
                                             "GET /api/control/companies/{company_id}/intents",  # the super admin's existence rows (intents/admin.py)
                                             "PUT /api/control/companies/{company_id}/centres/{centre_id}",
                                             "PUT /api/control/companies/{company_id}/modules/{module_id}"])
    for k in taking_company:
        assert perms.routes[k].roles == {"super_admin"}
    assert perms.routes["PUT /api/admin/companies/{company_id}/modules/{module_id}"].roles == {"super_admin"}
    assert not perms.routes["PUT /api/admin/companies/{company_id}/modules/{module_id}"].authenticated


# ------------------------------------------------------------------ 6. expired session
EXPIRED = {"error": "session_expired", "message": "Your session has ended. Please sign in again.",
           "login_url": "/login"}


def _with_page(env):
    env.add_route("get", "/app/home", lambda: {"page": "home"}, Rule(authenticated=True))


def test_idle_session_gets_401_with_the_briefed_shape(env):
    c = env.login(user_of(A)["email"])
    assert c.get("/api/auth/me").status_code == 200
    env.clock.advance(60 * 60)  # past the 30 minute idle limit
    r = c.get("/api/auth/me")
    assert r.status_code == 401 and r.json() == EXPIRED
    assert c.get("/api/modules").status_code == 401
    assert c.get(f"/api/modules/{M4}/x").status_code == 401  # the module gate says the same


def test_activity_keeps_a_session_alive_until_it_goes_idle(env):
    c = env.login(user_of(A)["email"])
    for _ in range(4):
        env.clock.advance(20 * 60)  # always inside the idle limit
        assert c.get("/api/auth/me").status_code == 200
    env.clock.advance(31 * 60)
    assert c.get("/api/auth/me").status_code == 401


def test_browser_request_without_a_session_is_sent_to_login(env):
    _with_page(env)
    c = env.login(user_of(A)["email"])
    ok = c.get("/app/home", headers={"accept": "text/html"}, follow_redirects=False)
    assert ok.status_code == 200
    env.clock.advance(2 * 60 * 60)
    r = c.get("/app/home", headers={"accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/login"
    api = c.get("/api/auth/me", headers={"accept": "text/html"}, follow_redirects=False)
    assert api.status_code == 401  # an API path never redirects


def test_logout_ends_the_old_cookie(env):
    _with_page(env)
    c = env.login(user_of(A)["email"])
    old = c.cookies.get("sh_session")
    assert post(c, "/api/auth/logout").status_code == 200
    from fastapi.testclient import TestClient
    replay = TestClient(env.app)
    replay.cookies.set("sh_session", old)
    r = replay.get("/api/auth/me")
    assert r.status_code == 401 and r.json() == EXPIRED
    page = replay.get("/app/home", headers={"accept": "text/html"}, follow_redirects=False)
    assert page.status_code == 302 and page.headers["location"] == "/login"


def test_a_disabled_account_loses_its_open_session(env):
    user = user_of(A)
    c = env.login(user["email"])
    assert c.get("/api/auth/me").status_code == 200
    disable_account(env.app.state.account_store, user["email"])
    r = c.get("/api/auth/me")
    assert r.status_code == 401 and r.json() == EXPIRED
    from fastapi.testclient import TestClient
    again = TestClient(env.app).post("/api/auth/login", json={"email": user["email"], "password": "x"})
    assert again.status_code == 401


# ------------------------------------------------------------------ 7. default deny
def test_every_route_of_the_real_app_is_declared(env):
    perms = load_permissions()
    keys = [k for r in all_routes(env.app) for k in route_keys(r)]  # raises for a route it cannot classify
    assert keys, "no routes found"
    undeclared = [k for k in keys if k not in perms.routes]
    assert undeclared == []
    mounts = [k for k in keys if k.startswith("MOUNT")]
    assert mounts == ["MOUNT /{path}"]  # the one reviewed mount: the built UI
    assert perms.routes["MOUNT /{path}"].public and not perms.routes["MOUNT /{path}"].roles
    assert keys[-1] == "MOUNT /{path}"  # last, so every API route is matched first


def test_ui_mount_serves_only_the_built_ui_and_never_the_api_or_outside_files(env):
    from fastapi.testclient import TestClient
    anon = TestClient(env.app)
    for path in ("/login", "/modules/m1_intent", "/"):  # deep links: the app shows its own screen
        r = anon.get(path, headers={"accept": "text/html"}, follow_redirects=False)
        assert r.status_code == 200 and "SMOKE-UI" in r.text, path
    for path in ("/api/nothing-here", "/api/modules", "/api/company"):  # the mount never answers for /api
        r = anon.get(path, headers={"accept": "text/html"}, follow_redirects=False)
        assert r.status_code in (401, 403, 404) and "SMOKE-UI" not in r.text, path
    assert anon.get("/missing.js").status_code == 404
    for path in ("/../outside.txt", "/%2e%2e/outside.txt", "/..%5coutside.txt", "/outside.txt"):
        assert "OUTSIDE-DIST-MARKER" not in anon.get(path).text, path
    assert anon.post("/anything").status_code in (403, 404, 405)  # the mount serves GET only
    c = env.login(user_of(A)["email"])  # a module path is still judged by the gate before the mount
    r = c.get(f"/api/modules/{M4}/x", headers={"accept": "text/html"})
    assert r.status_code == 403 and r.json() == NOT_AVAILABLE


def test_an_undeclared_route_is_refused(env):
    env.add_route("get", "/api/undeclared-probe", lambda: {"leak": True})
    c = env.login(user_of(A)["email"])
    r = c.get("/api/undeclared-probe")
    assert r.status_code == 403 and r.json()["error"] == "forbidden" and "leak" not in r.text
    from fastapi.testclient import TestClient
    assert TestClient(env.app).get("/api/undeclared-probe").status_code == 403  # also signed out


def test_an_undeclared_post_is_refused_even_with_a_valid_csrf(env):
    env.add_route("post", "/api/undeclared-write", lambda: {"done": True})
    c = env.login(user_of(B)["email"])
    assert post(c, "/api/undeclared-write").status_code == 403


def test_websocket_without_a_session_is_closed(env):
    async def echo(ws: WebSocket):
        await ws.accept()
        await ws.send_text("hello")

    env.add_route("websocket", "/ws/declared", echo, Rule(authenticated=True))
    env.add_route("websocket", "/ws/undeclared", echo)
    from fastapi.testclient import TestClient
    anon = TestClient(env.app)
    for path in ("/ws/declared", "/ws/undeclared", f"/api/modules/{M4}/ws"):
        with pytest.raises(WebSocketDisconnect) as e:
            with anon.websocket_connect(path) as ws:
                ws.receive_text()
        assert e.value.code == 1008, path
    signed_in = env.login(user_of(A)["email"])
    with signed_in.websocket_connect("/ws/declared") as ws:
        assert ws.receive_text() == "hello"  # control: the declared route works with a session
    with pytest.raises(WebSocketDisconnect) as e:
        with signed_in.websocket_connect("/ws/undeclared") as ws:
            ws.receive_text()
    assert e.value.code == 1008
