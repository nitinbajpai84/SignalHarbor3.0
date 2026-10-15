import json

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.auth import all_routes, route_keys
from sh_platform.auth.permissions import load_permissions
from sh_platform.auth.test_accounts import make_test_account
from sh_platform.settings import load_settings

FIELDS = {"id", "number", "name", "description", "agent"}


def ids(c):
    return [m["id"] for m in c.get("/api/modules").json()]


def test_menu_shows_only_owned_modules_per_company(world):
    a = world.login("a", "co-a", ["analyst"])
    b = world.login("b", "co-b", ["sponsor"])
    n = world.login("n", "co-n", ["participant"])
    solo = world.login("s", "co-solo", ["analyst"])
    assert ids(a) == ["m1_intent", "m2_baseline", "m3_connect", "m4_build", "m5_foresight"]
    assert ids(b) == ["m1_intent", "m2_baseline", "m3_connect"]
    assert ids(n) == ["m1_intent"]
    assert ids(solo) == ["m2_baseline"]


def test_menu_entries_have_exactly_the_public_fields(world):
    for m in world.login("a", "co-a", ["analyst"]).get("/api/modules").json():
        assert FIELDS | {"centre"} <= set(m) <= FIELDS | {"centre", "centre_name", "centre_description"}
        assert isinstance(m["number"], int) and all(isinstance(m[k], str) and m[k] for k in FIELDS - {"number"})
    first = world.login("n", "co-n", ["analyst"]).get("/api/modules").json()[0]
    assert first["number"] == 1 and first["agent"] == "North"


def test_empty_company_sees_an_empty_menu_not_an_error(world):
    c = world.login("e", "co-empty", ["company_admin"])
    r = c.get("/api/modules")
    assert r.status_code == 200 and r.json() == []


def test_company_not_in_the_directory_sees_an_empty_menu(world):
    c = world.login("o", "co-ghost", ["analyst"])
    assert c.get("/api/modules").json() == []


def test_menu_changes_immediately_after_set_module(world):
    c = world.login("b", "co-b", ["analyst"])
    world.store.set_module("co-b", "m2_baseline", False)
    assert ids(c) == ["m1_intent", "m3_connect"]
    world.store.set_module("co-b", "m6_ops", True)
    assert ids(c) == ["m1_intent", "m3_connect", "m6_ops"]


def test_menu_ignores_a_company_named_in_the_request(world):
    c = world.login("n", "co-n", ["analyst"])
    for kw in ({"params": {"company_id": "co-a"}}, {"headers": {"x-company-id": "co-a"}}):
        assert ids(c) == ["m1_intent"]
        assert [m["id"] for m in c.get("/api/modules", **kw).json()] == ["m1_intent"]


def test_menu_and_company_need_a_company_account(world):
    root = world.login("root", None, ["super_admin"])
    assert root.get("/api/modules").status_code == 403
    assert root.get("/api/company").status_code == 403
    anon = TestClient(world.app)
    assert anon.get("/api/modules").status_code == 401
    assert anon.get("/api/company").status_code == 401


def test_company_route_returns_only_the_signed_in_company(world):
    a = world.login("a", "co-a", ["analyst"])
    assert a.get("/api/company").json() == {"company_id": "co-a", "name": "Company A", "industry": "industry_a"}
    n = world.login("n", "co-n", ["analyst"])
    assert n.get("/api/company", params={"company_id": "co-a"}).json() == {
        "company_id": "co-n", "name": "Company N", "industry": "none"}
    assert "package" not in n.get("/api/company").json()


def test_company_route_for_a_company_not_in_the_directory_is_a_plain_error(world):
    c = world.login("o", "co-ghost", ["analyst"])
    r = c.get("/api/company")
    assert r.status_code == 404 and set(r.json()) == {"error", "message"}
    assert "co-ghost" not in r.text


# ---- admin switch

def put(c, company, module, body):
    return c.put(f"/api/admin/companies/{company}/modules/{module}", json=body)


def test_super_admin_can_switch_a_module_and_it_takes_effect_at_once(world):
    root = world.login("root", None, ["super_admin"])
    co = world.login("b", "co-b", ["analyst"])
    assert co.get("/api/modules/m2_baseline/ping").status_code == 200
    r = put(root, "co-b", "m2_baseline", {"enabled": False})
    assert r.status_code == 200 and r.json() == {"company_id": "co-b", "module_id": "m2_baseline", "enabled": False}
    assert "m2_baseline" not in ids(co)
    assert co.get("/api/modules/m2_baseline/ping").status_code == 403
    assert put(root, "co-b", "m2_baseline", {"enabled": True}).status_code == 200
    assert co.get("/api/modules/m2_baseline/ping").status_code == 200
    assert put(root, "co-b", "m6_ops", {"enabled": True}).status_code == 200
    assert "m6_ops" in ids(co)


@pytest.mark.parametrize("role", ["company_admin", "sponsor", "analyst", "approver", "participant", "owner"])
def test_no_company_role_can_use_the_admin_route(world, role):
    c = world.login("r", "co-a", [role])
    for target in ("co-a", "co-b"):
        r = put(c, target, "m6_ops", {"enabled": True})
        assert r.status_code == 403 and r.json()["error"] == "forbidden"
    assert world.store.enabled_modules("co-a") == ["m1_intent", "m2_baseline", "m3_connect", "m4_build", "m5_foresight"]
    assert not world.store.is_enabled("co-b", "m6_ops")


def test_company_admin_cannot_switch_their_own_module_off_either(world):
    c = world.login("ca", "co-a", ["company_admin"])
    assert put(c, "co-a", "m1_intent", {"enabled": False}).status_code == 403
    assert world.store.is_enabled("co-a", "m1_intent")


def test_signed_out_cannot_use_the_admin_route(world):
    r = put(TestClient(world.app), "co-a", "m1_intent", {"enabled": False})
    assert r.status_code == 401 and world.store.is_enabled("co-a", "m1_intent")


def test_csrf_is_enforced_on_the_admin_route(world):
    root = world.login("root", None, ["super_admin"])
    del root.headers["x-csrf-token"]
    r = put(root, "co-a", "m1_intent", {"enabled": False})
    assert r.status_code == 403 and r.json()["error"] == "csrf"
    root.headers["x-csrf-token"] = "wrong"
    assert put(root, "co-a", "m1_intent", {"enabled": False}).json()["error"] == "csrf"
    assert world.store.is_enabled("co-a", "m1_intent")


def test_admin_route_plain_errors_for_unknown_company_or_module(world):
    root = world.login("root", None, ["super_admin"])
    r1 = put(root, "co-zz", "m1_intent", {"enabled": False})
    r2 = put(root, "co-a", "m9_nope", {"enabled": False})
    r3 = put(root, "Bad%20Id", "m1_intent", {"enabled": False})
    for r in (r1, r2, r3):
        assert r.status_code == 404 and set(r.json()) == {"error", "message"}
        assert "Traceback" not in r.text and "/" not in r.json()["message"] and "_control" not in r.text
    assert r1.json() != r2.json()  # the operator is told which one is wrong
    assert not (world.store.company("co-zz"))
    assert world.store.is_enabled("co-a", "m1_intent")


@pytest.mark.parametrize("body", [{}, {"enabled": "false"}, {"enabled": 0}, {"enabled": 1}, {"enabled": None},
                                  {"enabled": "yes"}, [True], "true", 5, None, {"enabled": [True]}])
def test_admin_route_refuses_anything_but_a_real_boolean(world, body):
    root = world.login("root", None, ["super_admin"])
    r = put(root, "co-a", "m1_intent", body)
    assert r.status_code == 400 and set(r.json()) == {"error", "message"}
    assert world.store.is_enabled("co-a", "m1_intent")


def test_admin_route_refuses_a_non_json_body(world):
    root = world.login("root", None, ["super_admin"])
    r = root.put("/api/admin/companies/co-a/modules/m1_intent", content=b"enabled=false",
                 headers={"content-type": "text/plain"})
    assert r.status_code == 400
    assert world.store.is_enabled("co-a", "m1_intent")


def test_switching_off_deletes_nothing_in_the_plane(world, tmp_path):
    root = world.login("root", None, ["super_admin"])
    f = tmp_path / "data" / "co-a" / "baseline" / "note.txt"
    f.write_text("synthetic", encoding="utf-8")
    assert put(root, "co-a", "m2_baseline", {"enabled": False}).status_code == 200
    assert f.read_text(encoding="utf-8") == "synthetic"


def test_admin_path_cannot_reach_another_route_or_module_namespace(world):
    root = world.login("root", None, ["super_admin"])
    r = root.put("/api/admin/companies/co-a/modules/m1_intent/extra", json={"enabled": True})
    assert r.status_code in (404, 405)


# ---- the real app, real route table

def real_app(tmp_path):
    return create_app(load_settings({"SH_DATA_ROOT": str(tmp_path / "data")}, env_file=tmp_path / "none.env"))


def test_real_app_declares_every_route_including_the_new_ones(tmp_path):
    app = real_app(tmp_path)
    declared = load_permissions().routes
    keys = [k for r in all_routes(app) for k in route_keys(r)]
    assert [k for k in keys if k not in declared] == []
    for k in ("GET /api/modules", "GET /api/company", "PUT /api/admin/companies/{company_id}/modules/{module_id}"):
        assert k in keys and k in declared
    assert declared["PUT /api/admin/companies/{company_id}/modules/{module_id}"].roles == {"super_admin"}
    assert not declared["PUT /api/admin/companies/{company_id}/modules/{module_id}"].authenticated
    assert declared["GET /api/modules"].authenticated and declared["GET /api/company"].authenticated


def test_real_app_end_to_end(tmp_path):
    app = real_app(tmp_path)
    store = app.state.entitlements
    store.create_company("co-a", "Company A", "industry_a", package="discover")
    acct, pw = make_test_account(app.state.account_store, "user", "co-a", ["analyst"])
    c = TestClient(app)
    assert c.get("/api/modules").status_code == 401
    assert c.post("/api/auth/login", json={"email": acct["email"], "password": pw}).status_code == 200
    assert ids(c) == ["m1_intent", "m2_baseline", "m3_connect"]
    # nothing is served under /api/modules/<id>/ yet (no module is built): refused or unknown, never data
    r = c.get("/api/modules/m1_intent/anything")
    assert r.status_code in (403, 404)
    assert c.get("/api/modules/m6_ops/anything").json()["error"] == "module_not_available"



def test_admin_route_refuses_json_sent_as_the_wrong_content_type(world):
    root = world.login("root", None, ["super_admin"])
    r = root.put("/api/admin/companies/co-a/modules/m1_intent", content=json.dumps({"enabled": False}),
                 headers={"content-type": "text/plain"})
    assert r.status_code == 400
    assert world.store.is_enabled("co-a", "m1_intent")
