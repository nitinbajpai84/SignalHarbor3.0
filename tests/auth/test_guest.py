"""The kernel's guest principal (M1-P02): a route may say `guest: true` and then a person with no account but a
valid X-Session-Token is let in as `participant` only. Every test names the check it guards and fails if that
check is removed. A fake module resolver stands in for module 1 (module 1's own tests use the real one).
Tokens here are fake strings, clearly marked."""
import logging

import pytest
import yaml
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from sh_platform.auth import guest as guest_mod
from sh_platform.auth import install_auth
from sh_platform.auth.guest import register_guest_resolver
from sh_platform.auth.permissions import DEFAULT_PATH, load_permissions
from sh_platform.auth.test_accounts import make_test_account
from sh_platform.modulegate import install_modulegate
from sh_platform.settings import Settings

SECRET = "fake-test-secret-not-real"
M = "/api/modules/m4_build"  # a catalogue module nothing else registers a resolver for
GOOD = "fake-token-good"
OTHER_CO = "fake-token-other-company"
OTHER_SESSION = "fake-token-other-session"
PART = ["participant", "analyst"]
TOKENS = {  # token -> (company, guest id, session id)
    GOOD: ("co-a", "guest-1", "s1"), OTHER_CO: ("co-b", "guest-2", "s2"), OTHER_SESSION: ("co-a", "guest-3", "s9"),
}
CALLS: list[str] = []


def fake_resolver(app, token):
    CALLS.append("resolver")
    return TOKENS.get(token)


class Kit:
    def __init__(self, tmp_path, rules=None):
        self.settings = Settings(mode="dev", data_root=str(tmp_path / "data"), session_secret=SECRET)
        data = yaml.safe_load(DEFAULT_PATH.read_text(encoding="utf-8"))
        data["routes"].update({
            f"GET {M}/g/{{sid}}": {"roles": PART, "guest": True},
            f"POST {M}/g/{{sid}}/write": {"roles": PART, "guest": True},
            f"POST {M}/entry": {"roles": PART, "guest": True, "entry": True},
            f"GET {M}/plain": {"roles": ["analyst"]},
            f"GET {M}/open": {"authenticated": True},
        })
        data["routes"].update(rules or {})
        perms = tmp_path / "perms.yaml"
        perms.write_text(yaml.safe_dump(data), encoding="utf-8")
        self.app = FastAPI()
        install_auth(self.app, self.settings, route_permissions=perms)
        install_modulegate(self.app, self.settings)
        self.store = self.app.state.entitlements
        for cid in ("co-a", "co-b"):
            self.store.create_company(cid, cid, "industry_x", modules=["m4_build"])

        def who(request: Request):
            s = request.state
            return {"company_id": s.company_id, "roles": s.roles, "account_id": s.account_id,
                    "guest_id": getattr(s, "guest_id", None), "m1_session_id": getattr(s, "m1_session_id", None)}

        @self.app.get(f"{M}/g/{{sid}}")
        def g_get(sid: str, request: Request):
            return {**who(request), "path_sid": sid}

        @self.app.post(f"{M}/g/{{sid}}/write")
        def g_write(sid: str, request: Request):
            return who(request)

        @self.app.post(f"{M}/entry")
        def entry(request: Request):
            return who(request)

        @self.app.get(f"{M}/plain")
        def plain(request: Request):
            return who(request)

        @self.app.get(f"{M}/open")
        def open_(request: Request):
            return who(request)

        self.app.get("/api/t/secret")(lambda: {"ok": True})
        self.app.get("/api/health")(lambda: {"status": "ok"})

    def login(self, name, company, roles):
        acct, pw = make_test_account(self.app.state.account_store, name, company, list(roles))
        c = TestClient(self.app)
        assert c.post("/api/auth/login", json={"email": acct["email"], "password": pw}).status_code == 200
        c.headers["x-csrf-token"] = c.cookies["sh_csrf"]
        return c


@pytest.fixture
def kit(tmp_path):
    CALLS.clear()
    register_guest_resolver("m4_build", fake_resolver)
    yield Kit(tmp_path)
    guest_mod.unregister_guest_resolver("m4_build")


def tok(t=GOOD):
    return {"X-Session-Token": t}


EXPIRED = {"error": "session_expired", "message": "Your session has ended. Please sign in again.",
           "login_url": "/login"}


def test_guest_route_is_served_with_a_valid_token_and_no_cookie(kit):
    r = TestClient(kit.app).get(f"{M}/g/s1", headers=tok())
    assert r.status_code == 200
    # the principal: company from the resolver, participant only, no account
    assert r.json() == {"company_id": "co-a", "roles": ["participant"], "account_id": None,
                        "guest_id": "guest-1", "m1_session_id": "s1", "path_sid": "s1"}


def test_guest_write_needs_no_csrf_because_the_token_is_a_header_not_a_cookie(kit):
    assert TestClient(kit.app).post(f"{M}/g/s1/write", headers=tok()).status_code == 200


@pytest.mark.parametrize("headers", [{}, tok("fake-wrong"), tok(""), {"X-Session-Token": "x" * 5000}])
def test_no_token_or_a_wrong_token_looks_exactly_like_signed_out(kit, headers):
    r = TestClient(kit.app).get(f"{M}/g/s1", headers=headers)
    assert (r.status_code, r.json()) == (401, EXPIRED)


def test_token_in_the_query_string_or_a_cookie_is_never_accepted(kit):
    c = TestClient(kit.app)
    assert c.get(f"{M}/g/s1?x_session_token={GOOD}&token={GOOD}").status_code == 401
    c.cookies.set("X-Session-Token", GOOD)
    c.cookies.set("sh_session", GOOD)
    assert c.get(f"{M}/g/s1").status_code == 401
    assert "resolver" not in CALLS  # the resolver was never even asked


def test_a_token_is_refused_on_a_route_that_is_not_marked_guest(kit):
    for path in (f"{M}/plain", f"{M}/open"):
        r = TestClient(kit.app).get(path, headers=tok())
        assert (r.status_code, r.json()["error"]) == (403, "forbidden"), path  # a live token is refused, not signed out


@pytest.mark.parametrize("path", ["/api/modules", "/api/company", "/api/auth/me", "/api/t/secret",
                                  "/api/admin/companies/co-a/modules/m4_build"])
def test_a_token_reaches_no_kernel_route_and_only_the_open_health_check_answers(kit, path):
    c = TestClient(kit.app)
    assert c.get(path, headers=tok()).status_code in (401, 403, 404, 405)
    assert c.get("/api/health", headers=tok()).json() == {"status": "ok"}


def test_a_module_with_no_registered_resolver_has_no_guests(kit):
    guest_mod.unregister_guest_resolver("m4_build")
    r = TestClient(kit.app).get(f"{M}/g/s1", headers=tok())
    assert (r.status_code, r.json()) == (401, EXPIRED)


def test_module_switched_off_for_the_tokens_company_refuses_the_guest(kit):
    kit.store.set_module("co-a", "m4_build", False)
    r = TestClient(kit.app).get(f"{M}/g/s1", headers=tok())
    assert (r.status_code, r.json()) == (403, {"error": "module_not_available",
                                                "message": "This module is not part of your plan."})
    # and it is the same answer a signed-in user of that company gets
    c = kit.login("an", "co-a", ["analyst"])
    assert c.get(f"{M}/plain").json() == r.json()


def test_a_company_that_never_owned_the_module_refuses_the_guest(kit):
    r = TestClient(kit.app).get(f"{M}/g/s9", headers=tok(OTHER_CO))
    assert r.status_code == 200  # co-b owns it in this kit...
    kit.store.set_module("co-b", "m4_build", False)
    assert TestClient(kit.app).get(f"{M}/g/s9", headers=tok(OTHER_CO)).status_code == 403


def test_company_is_never_taken_from_the_request(kit):
    r = TestClient(kit.app).get(f"{M}/g/s1?company_id=co-b", headers={**tok(), "X-Company-Id": "co-b",
                                                                      "X-Company": "co-b"})
    assert r.json()["company_id"] == "co-a"


def test_a_valid_cookie_session_wins_over_a_token_header(kit):
    c = kit.login("an", "co-b", ["analyst"])
    r = c.get(f"{M}/g/s1", headers=tok())  # signed in as co-b; the co-a token is ignored
    assert r.status_code == 200 and r.json()["account_id"] is not None and r.json()["guest_id"] is None
    assert r.json()["company_id"] == "co-b" and r.json()["roles"] == ["analyst"]


def test_a_signed_in_user_without_the_roles_is_refused_on_a_guest_route(kit):
    c = kit.login("ap", "co-a", ["approver"])
    assert c.get(f"{M}/g/s1").status_code == 403


def test_guest_state_is_reset_per_request(kit):
    c = TestClient(kit.app)
    assert c.get(f"{M}/g/s1", headers=tok()).json()["guest_id"] == "guest-1"
    assert c.get(f"{M}/g/s9", headers=tok(OTHER_SESSION)).json()["guest_id"] == "guest-3"
    assert c.get(f"{M}/g/s1").status_code == 401


def test_a_failing_resolver_means_refused_never_an_error_page_and_never_leaks_the_token(kit, caplog):
    def boom(app, token):
        raise RuntimeError(f"broken with {token}")

    register_guest_resolver("m4_build", boom)
    with caplog.at_level(logging.DEBUG):
        r = TestClient(kit.app).get(f"{M}/g/s1", headers=tok())
    assert (r.status_code, r.json()) == (401, EXPIRED)
    assert GOOD not in caplog.text and GOOD not in r.text


@pytest.mark.parametrize("bad", [None, ("co-a", "g"), ("co-a", "", "s1"), ("Not A Company!", "g", "s1"),
                                 ("co-a", "g", 5), "co-a"])
def test_a_resolver_answer_that_is_not_exactly_three_good_strings_is_refused(kit, bad):
    register_guest_resolver("m4_build", lambda app, token: bad)
    assert TestClient(kit.app).get(f"{M}/g/s1", headers=tok()).status_code == 401


def test_entry_route_is_reachable_with_no_session_and_no_token_and_the_handler_decides(kit):
    r = TestClient(kit.app).post(f"{M}/entry", json={})
    assert r.status_code == 200
    assert r.json() == {"company_id": None, "roles": [], "account_id": None, "guest_id": None,
                        "m1_session_id": None}


def test_entry_route_gives_a_valid_token_its_principal_and_ignores_a_stale_one(kit):
    c = TestClient(kit.app)
    assert c.post(f"{M}/entry", json={}, headers=tok()).json()["guest_id"] == "guest-1"
    stale = c.post(f"{M}/entry", json={}, headers=tok("fake-stale"))
    assert stale.status_code == 200 and stale.json()["guest_id"] is None and stale.json()["company_id"] is None


def test_entry_route_with_a_valid_token_of_a_company_without_the_module_is_refused(kit):
    kit.store.set_module("co-a", "m4_build", False)
    assert TestClient(kit.app).post(f"{M}/entry", json={}, headers=tok()).status_code == 403


def test_entry_route_binds_a_signed_in_account_and_enforces_csrf_for_it(kit):
    c = kit.login("an", "co-a", ["analyst"])
    r = c.post(f"{M}/entry", json={})
    assert r.json()["account_id"] is not None and r.json()["company_id"] == "co-a"
    c.headers["x-csrf-token"] = "wrong"
    assert c.post(f"{M}/entry", json={}).status_code == 403


def test_entry_route_refuses_a_signed_in_role_the_rule_does_not_list(kit):
    assert kit.login("ap", "co-a", ["approver"]).post(f"{M}/entry", json={}).status_code == 403


def test_entry_route_for_a_company_without_the_module_is_refused_when_signed_in(kit):
    kit.store.set_module("co-a", "m4_build", False)
    assert kit.login("an", "co-a", ["analyst"]).post(f"{M}/entry", json={}).status_code == 403


def test_a_token_does_not_reach_a_websocket_even_on_a_module_path(kit):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with TestClient(kit.app).websocket_connect(f"{M}/g/s1", headers=tok()):
            pass


# ---- the rule table: what a `guest` rule may be --------------------------------------------------------------
@pytest.mark.parametrize("key,spec", [
    ("GET /api/modules/m4_build/x", {"roles": ["analyst"], "guest": True}),                 # no participant role
    ("GET /api/modules/m4_build/x", {"public": True, "guest": True}),                       # public
    ("GET /api/modules/m4_build/x", {"authenticated": True, "guest": True}),                # authenticated only
    ("GET /api/health", {"roles": ["participant"], "guest": True}),                         # a kernel route
    ("GET /api/modules/", {"roles": ["participant"], "guest": True}),                       # no module id
    ("WEBSOCKET /api/modules/m4_build/x", {"roles": ["participant"], "guest": True}),       # a websocket
    ("MOUNT /api/modules/m4_build/{path}", {"roles": ["participant"], "guest": True}),      # a mount
    ("GET /api/modules/m4_build/x", {"roles": ["participant"], "guest": True, "entry": True}),  # entry is POST only
    ("GET /api/modules/m4_build/x", {"roles": ["participant"], "entry": True}),             # entry needs guest
    ("GET /api/modules/m4_build/x", {"roles": ["participant"], "guest": "yes"}),            # not a real boolean
    ("GET /api/modules/m4_build/{rest:path}", {"roles": ["participant"], "guest": True}),   # a catch-all segment
    ("POST /api/modules/m4_build/a/{rest:path}", {"roles": ["participant"], "guest": True, "entry": True}),
    ("PUT /api/modules/m4_build/x", {"roles": ["participant"], "guest": True}),             # only GET and POST
    ("PATCH /api/modules/m4_build/x", {"roles": ["participant"], "guest": True}),
    ("DELETE /api/modules/m4_build/x", {"roles": ["participant"], "guest": True}),
])
def test_the_loader_refuses_a_guest_rule_that_is_too_wide(tmp_path, key, spec):
    path = tmp_path / "p.yaml"
    data = yaml.safe_load(DEFAULT_PATH.read_text(encoding="utf-8"))
    data["routes"][key] = spec
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_permissions(path)


def test_the_loader_accepts_the_two_good_shapes(tmp_path):
    path = tmp_path / "p.yaml"
    data = yaml.safe_load(DEFAULT_PATH.read_text(encoding="utf-8"))
    data["routes"]["GET /api/modules/m4_build/x"] = {"roles": ["participant"], "guest": True}
    data["routes"]["POST /api/modules/m4_build/y"] = {"roles": ["participant"], "guest": True, "entry": True}
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    rules = load_permissions(path).routes
    assert rules["GET /api/modules/m4_build/x"].guest and not rules["GET /api/modules/m4_build/x"].entry
    assert rules["POST /api/modules/m4_build/y"].entry


def test_the_shipped_table_marks_guest_only_on_known_link_routes():
    """Guests reach only: module 1's room, module 2's answer links, module 3's upload links and the interview links."""
    guests = {k for k, r in load_permissions().routes.items() if r.guest}
    allowed = ("/api/modules/m1_intent/", "/api/modules/m2_baseline/answer/", "/api/modules/m3_connect/intake/link/",
               "/api/modules/interview/guest/")
    assert all(k.split(" ", 1)[1].startswith(allowed) for k in guests), sorted(k for k in guests if not k.split(" ", 1)[1].startswith(allowed))


def test_a_module_manifest_cannot_declare_a_guest_route_by_itself(tmp_path):
    """The central table is the only place `guest` can come from: a manifest route merged by the module loader
    never carries it."""
    from sh_platform.manifest import _KEYS, _ROUTE_KEYS
    assert "guest" not in _ROUTE_KEYS and "guest" not in _KEYS


# ---- each layer on its own -------------------------------------------------------------------------------------------
def test_auth_alone_refuses_a_token_on_a_route_not_marked_guest(tmp_path):
    """No module gate installed: the sign-in layer must refuse on its own."""
    data = yaml.safe_load(DEFAULT_PATH.read_text(encoding="utf-8"))
    data["routes"].update({f"GET {M}/g/{{sid}}": {"roles": PART, "guest": True}, f"GET {M}/plain": {"roles": ["analyst"]}})
    perms = tmp_path / "p.yaml"
    perms.write_text(yaml.safe_dump(data), encoding="utf-8")
    app = FastAPI()
    install_auth(app, Settings(mode="dev", data_root=str(tmp_path / "d"), session_secret=SECRET), route_permissions=perms)
    app.get(f"{M}/g/{{sid}}")(lambda sid: {"ok": True})
    app.get(f"{M}/plain")(lambda: {"ok": True})
    register_guest_resolver("m4_build", fake_resolver)
    try:
        c = TestClient(app)
        assert c.get(f"{M}/g/s1", headers=tok()).status_code == 200
        assert c.get(f"{M}/plain", headers=tok()).status_code == 403  # a live guest is refused, not signed out
    finally:
        guest_mod.unregister_guest_resolver("m4_build")


def test_the_middleware_itself_refuses_a_guest_rule_without_the_participant_role(tmp_path):
    """Defence in depth (M09): the loader already refuses such a rule, so build one by hand, past the loader, and
    the middleware must still not let a token through on it."""
    from sh_platform.auth.permissions import Rule
    data = yaml.safe_load(DEFAULT_PATH.read_text(encoding="utf-8"))
    data["routes"][f"GET {M}/g/{{sid}}"] = {"roles": PART, "guest": True}
    perms = tmp_path / "p.yaml"
    perms.write_text(yaml.safe_dump(data), encoding="utf-8")
    app = FastAPI()
    install_auth(app, Settings(mode="dev", data_root=str(tmp_path / "d"), session_secret=SECRET), route_permissions=perms)
    app.get(f"{M}/g/{{sid}}")(lambda sid: {"ok": True})
    register_guest_resolver("m4_build", fake_resolver)
    try:
        c = TestClient(app)
        assert c.get(f"{M}/g/s1", headers=tok()).status_code == 200  # the control: a proper rule lets the token in
        app.state.route_permissions.routes[f"GET {M}/g/{{sid}}"] = Rule(roles=frozenset({"analyst"}), guest=True)
        assert c.get(f"{M}/g/s1", headers=tok()).status_code == 403  # refused: the token is live, the rule not theirs
    finally:
        guest_mod.unregister_guest_resolver("m4_build")


def test_the_gate_alone_refuses_a_token_on_a_route_not_marked_guest_and_one_of_a_company_without_the_module(kit):
    from sh_platform.modulegate import ModuleGate

    gate = ModuleGate(None, kit.app)

    def scope(path, method="GET", token=GOOD):
        return {"type": "http", "method": method, "path": path, "raw_path": path.encode(), "query_string": b"",
                "root_path": "", "headers": [(b"x-session-token", token.encode())], "server": ("t", 80),
                "client": ("c", 1), "scheme": "http", "http_version": "1.1"}

    segs = lambda p: p[len("/api/modules/"):].split("/")  # noqa: E731
    assert gate._verdict(scope(f"{M}/g/s1"), segs(f"{M}/g/s1")) is None
    assert gate._verdict(scope(f"{M}/plain"), segs(f"{M}/plain")) == "forbidden"
    assert gate._verdict(scope(f"{M}/g/s1", token="fake-wrong"), segs(f"{M}/g/s1")) == "expired"
    assert gate._verdict(scope(f"{M}/entry", "POST", "fake-wrong"), segs(f"{M}/entry")) is None
    kit.store.set_module("co-a", "m4_build", False)
    assert gate._verdict(scope(f"{M}/g/s1"), segs(f"{M}/g/s1")) == "refused"
