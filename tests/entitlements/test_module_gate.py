"""The module gate against every kind of route. Each test fails if the check it names is removed."""
import json

import pytest
from starlette.websockets import WebSocketDisconnect

from gate_kit import MODS, REFUSED

# co-a: m1,m3,m4 on; m2,m5 switched off; m6 never owned.
HTTP_KINDS = [
    ("GET", "ping"), ("POST", "write"), ("GET", "analyst-only"), ("GET", "items/7"),
    ("GET", "files/a/b.txt"), ("GET", "static/anything/at/all"), ("GET", "undeclared"),
    ("GET", ""), ("GET", "nope/deeper"),
]


def snapshot(r):
    return (r.status_code, r.content, tuple(sorted(r.headers.items())))


def go(c, method, mod, tail):
    return c.request(method, f"/api/modules/{mod}/{tail}")


@pytest.fixture
def gate(world):
    s = world.store
    s.set_module("co-a", "m2_baseline", False)  # switched off (was owned)
    s.set_module("co-a", "m4_build", True)
    s.set_module("co-a", "m5_foresight", False)
    return world


def test_owned_module_is_served_on_every_route_kind(gate):
    c = gate.login("a-analyst", "co-a", ["analyst"])
    assert c.get("/api/modules/m1_intent/ping").json() == {"served": "ping"}
    assert c.post("/api/modules/m1_intent/write").json() == {"served": "write"}
    assert c.get("/api/modules/m1_intent/analyst-only").json() == {"served": "analyst"}
    assert c.get("/api/modules/m1_intent/items/7").json() == {"served": "item", "n": "7"}
    assert c.get("/api/modules/m1_intent/files/a/b.txt").json()["served"] == "files"
    assert c.get("/api/modules/m1_intent/static/x/y").json() == {"served": "mount", "rest": "x/y"}
    with c.websocket_connect("/api/modules/m1_intent/ws") as ws:
        assert ws.receive_text() == "served"
    assert c.get("/api/modules/m4_build/ping").json() == {"served": "ping"}


@pytest.mark.parametrize("method,tail", HTTP_KINDS)
def test_off_never_owned_and_unknown_are_refused_identically(gate, method, tail):
    c = gate.login("a-analyst", "co-a", ["analyst"])
    off = go(c, method, "m2_baseline", tail)          # owned, then switched off
    never = go(c, method, "m6_ops", tail)         # in the catalogue, never owned
    unknown = go(c, method, "ghost", tail)            # not in the catalogue at all
    nonsense = go(c, method, "M1_INTENT", tail)       # wrong case of an owned id
    for r in (off, never, unknown, nonsense):
        assert r.status_code == 403 and r.json() == REFUSED
    assert snapshot(off) == snapshot(never) == snapshot(unknown) == snapshot(nonsense)


def test_refusal_never_mentions_the_path_or_module(gate):
    c = gate.login("a-analyst", "co-a", ["analyst"])
    for mod in ("m5_foresight", "m6_ops", "ghost", "m2_baseline"):
        r = c.get(f"/api/modules/{mod}/secret-thing?x=1")
        text = r.text + json.dumps(dict(r.headers))
        assert mod not in text and "secret-thing" not in text
        assert r.json() == REFUSED


def test_refusal_hides_whether_the_route_exists_or_would_be_role_refused(gate):
    # a participant is not allowed on analyst-only routes; in a module they do not own they must NOT learn
    # that the route exists (a role refusal would say "forbidden", a missing route would say 404)
    c = gate.login("a-part", "co-a", ["participant"])
    served_unowned = c.get("/api/modules/ghost/analyst-only")          # exists + declared + role refused
    undeclared_unowned = c.get("/api/modules/ghost/undeclared")        # exists but undeclared
    missing_unowned = c.get("/api/modules/ghost/never-existed")        # does not exist
    assert snapshot(served_unowned) == snapshot(undeclared_unowned) == snapshot(missing_unowned)
    assert served_unowned.json() == REFUSED
    # in an owned module the ordinary role refusal still applies
    assert c.get("/api/modules/m1_intent/analyst-only").json()["error"] == "forbidden"


def test_websocket_to_unowned_modules_is_closed_before_accept(gate):
    c = gate.login("a-analyst", "co-a", ["analyst"])
    for mod in ("m2_baseline", "m6_ops", "ghost"):
        with pytest.raises(WebSocketDisconnect) as e:
            with c.websocket_connect(f"/api/modules/{mod}/ws"):
                pass
        assert e.value.code == 1008


def test_mounted_app_and_router_routes_are_gated(gate):
    c = gate.login("a-analyst", "co-a", ["analyst"])
    assert c.get("/api/modules/m6_ops/static/x").status_code == 403   # MOUNT
    assert c.get("/api/modules/m6_ops/items/1").status_code == 403    # include_router
    assert c.get("/api/modules/m6_ops/files/x").status_code == 403    # path converter


def test_every_real_route_of_a_switched_off_module_is_refused(gate):
    """Walk the app's own route table: whatever is served under a switched-off module is refused."""
    from sh_platform.auth import all_routes, route_keys
    c = gate.login("a-analyst", "co-a", ["analyst"])
    n = 0
    for r in all_routes(gate.app):
        for key in route_keys(r):
            method, _, path = key.partition(" ")
            if not path.startswith("/api/modules/m2_baseline/") or method == "WEBSOCKET":
                continue
            n += 1
            url = path.replace("{path}", "x").replace("{n}", "1")
            assert c.request("GET" if method == "MOUNT" else method, url).json() == REFUSED, key
    assert n >= 6  # the walk really saw the fixture routes


@pytest.mark.parametrize("path", [
    "/api/modules/m1_intent/../m6_ops/ping",
    "/api/modules/m1_intent/files/../../m6_ops/ping",
    "/api/modules/m1_intent/./ping",
    "/api/modules/m1_intent//ping",
    "/api/modules//m1_intent/ping",
    "/api/modules/m1_intent/files/a\\..\\b",
    "/api/modules/m1_intent/files/a\x00b",
    "/api/modules/",
    "/api/modules/m2_baseline",
    "/api/modules/..",
])
def test_odd_paths_under_the_prefix_are_refused_the_same_way(gate, path):
    c = gate.login("a-analyst", "co-a", ["analyst"])
    out = gate.raw_get(c, path)
    assert out["status"] == 403 and json.loads(out["body"]) == REFUSED


def test_the_menu_route_is_not_swallowed_by_the_gate(gate):
    c = gate.login("a-analyst", "co-a", ["analyst"])
    assert c.get("/api/modules").status_code == 200


def test_company_comes_from_the_session_never_from_the_request(gate):
    a = gate.login("a-analyst", "co-a", ["analyst"])    # co-a: m2 OFF
    b = gate.login("b-analyst", "co-b", ["analyst"])    # co-b: m2 on, m4 not owned
    def naming(company):
        return ({"params": {"company_id": company}}, {"headers": {"x-company-id": company}},
                {"json": {"company_id": company}}, {"params": {"company": company, "module": "m2_baseline"}})

    for kw in naming("co-b"):
        assert a.post("/api/modules/m2_baseline/write", **kw).json() == REFUSED  # a: off, b: on
    for kw in naming("co-a"):
        assert b.post("/api/modules/m4_build/write", **kw).json() == REFUSED    # b: never owned, a: owns it
    assert b.post("/api/modules/m2_baseline/write").json() == {"served": "write"}


def test_cookie_or_header_naming_a_company_changes_nothing(gate):
    a = gate.login("a-analyst", "co-a", ["analyst"])
    a.cookies.set("company_id", "co-b")
    a.cookies.set("sh_company", "co-b")
    assert a.get("/api/modules/m2_baseline/ping").json() == REFUSED


def test_an_account_moved_to_another_company_follows_the_account_not_the_session(gate, tmp_path):
    c = gate.login("a-analyst", "co-a", ["analyst"])
    assert c.get("/api/modules/m4_build/ping").status_code == 200
    accts = tmp_path / "data" / "_control" / "accounts.json"
    data = json.loads(accts.read_text(encoding="utf-8"))
    for a in data:
        a["company_id"] = "co-b"  # co-b does not own m4
    accts.write_text(json.dumps(data), encoding="utf-8")
    assert c.get("/api/modules/m4_build/ping").json() == REFUSED


def test_a_disabled_account_gets_nothing(gate, tmp_path):
    c = gate.login("a-analyst", "co-a", ["analyst"])
    accts = tmp_path / "data" / "_control" / "accounts.json"
    data = json.loads(accts.read_text(encoding="utf-8"))
    for a in data:
        a["disabled"] = True
    accts.write_text(json.dumps(data), encoding="utf-8")
    r = c.get("/api/modules/m1_intent/ping")
    assert r.status_code in (401, 403) and "served" not in r.text


def test_super_admin_has_no_company_and_is_refused_on_module_routes(gate):
    c = gate.login("root", None, ["super_admin"])
    for mod in ("m1_intent", "m6_ops", "ghost"):
        r = c.get(f"/api/modules/{mod}/ping")
        assert r.status_code == 403 and r.json() == REFUSED
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/api/modules/m1_intent/ws"):
            pass


def test_the_empty_company_and_unknown_company_are_refused_everywhere(gate):
    c = gate.login("e", "co-empty", ["company_admin"])
    for mod in MODS:
        for method, tail in HTTP_KINDS:
            assert go(c, method, mod, tail).json() == REFUSED, (mod, tail)
    orphan = gate.login("o", "co-not-in-directory", ["analyst"])  # account whose company has no entitlements
    for mod in MODS:
        assert orphan.get(f"/api/modules/{mod}/ping").json() == REFUSED


def test_solo_company_and_other_industries(gate):
    solo = gate.login("solo", "co-solo", ["analyst"])
    assert solo.get("/api/modules/m2_baseline/ping").status_code == 200
    assert solo.get("/api/modules/m1_intent/ping").json() == REFUSED
    n = gate.login("n", "co-n", ["analyst"])  # industry "none"
    assert n.get("/api/modules/m1_intent/ping").status_code == 200
    assert n.get("/api/modules/m2_baseline/ping").json() == REFUSED


def test_switch_off_refuses_at_once_and_switch_on_restores_it(gate):
    c = gate.login("a-analyst", "co-a", ["analyst"])
    assert c.get("/api/modules/m1_intent/ping").status_code == 200
    gate.store.set_module("co-a", "m1_intent", False)
    assert c.get("/api/modules/m1_intent/ping").json() == REFUSED
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/api/modules/m1_intent/ws"):
            pass
    gate.store.set_module("co-a", "m1_intent", True)
    assert c.get("/api/modules/m1_intent/ping").status_code == 200


def test_one_company_switching_off_does_not_affect_another(gate):
    a = gate.login("a-analyst", "co-a", ["analyst"])
    b = gate.login("b-analyst", "co-b", ["analyst"])
    gate.store.set_module("co-a", "m1_intent", False)
    assert a.get("/api/modules/m1_intent/ping").json() == REFUSED
    assert b.get("/api/modules/m1_intent/ping").status_code == 200


def test_signed_out_requests_to_module_paths_learn_nothing_about_which_paths_exist(gate):
    from fastapi.testclient import TestClient
    anon = TestClient(gate.app)
    snaps = {snapshot(anon.get(f"/api/modules/{m}/{t}")) for m in MODS + ["zzz"]
             for t in ("ping", "undeclared", "analyst-only", "never-existed")}
    assert len(snaps) == 1
    status, body, _ = next(iter(snaps))
    assert status == 401 and b"served" not in body
    with pytest.raises(WebSocketDisconnect):
        with anon.websocket_connect("/api/modules/m1_intent/ws"):
            pass


def test_forged_and_garbage_cookies_are_signed_out(gate):
    from fastapi.testclient import TestClient
    c = TestClient(gate.app)
    c.cookies.set("sh_session", "garbage.garbage")
    assert c.get("/api/modules/m1_intent/ping").status_code == 401


def test_gate_runs_before_the_route_permission_check(gate):
    names = [m.cls.__name__ for m in gate.app.user_middleware]
    assert names.index("ModuleGate") < names.index("AuthMiddleware")  # outermost first


def test_csrf_still_applies_inside_an_owned_module(gate):
    c = gate.login("a-analyst", "co-a", ["analyst"])
    del c.headers["x-csrf-token"]
    assert c.post("/api/modules/m1_intent/write").json()["error"] == "csrf"
    # but an unowned module is refused as such, before anything else is revealed
    assert c.post("/api/modules/m6_ops/write").json() == REFUSED
