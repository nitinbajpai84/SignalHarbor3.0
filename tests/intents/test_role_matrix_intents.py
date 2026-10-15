"""Spec 14: every /api/intents route against every role (and the super admin), plus the top bar per role.

Runs the real app on a temporary copy of the demo data root, so empty-body POSTs cannot touch it. A role the yaml lists must not meet
the route guard's own 403 (a stub's 501 or a handler's 404 or its own 403 code is fine); a role it does not list must.
Skipped if the seed credentials are absent.
"""
import json
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.auth import all_routes, route_keys
from sh_platform.auth.permissions import load_permissions
from sh_platform.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
ROLES = ["participant", "owner", "approver", "sponsor", "analyst", "company_admin", "super_admin"]
SIX = set(ROLES) - {"super_admin"}
TABLE0 = json.loads(re.search(r"/\* role table \*/(.*?)/\* end role table \*/",
                             (ROOT / "ui/src/shell/roles.ts").read_text(encoding="utf-8"), re.S).group(1))
TABLE = {r: v for r, v in TABLE0.items() if r in ROLES}  # V6: head_of_data is a seat held beside analyst, it has no centres of its own
PERMS = load_permissions()
INTENT_KEYS = sorted(k for k in PERMS.routes if k.split(" ", 1)[1] == "/api/intents" or k.split(" ", 1)[1].startswith("/api/intents/"))


def fill(path):
    return re.sub(r"\{[^}]+\}", "x", path)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    if not CREDS.is_file():
        pytest.skip("no seeded demo data")
    data = tmp_path_factory.mktemp("intent_matrix") / "data"
    shutil.copytree(ROOT / "data", data)
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    registered = sorted({k for r in all_routes(app) for k in route_keys(r)
                         if re.match(r"[A-Z]+ /api/intents(/|$)", k)})
    return app, pw, registered


@pytest.fixture(scope="module")
def grid(world):
    """role -> {route key: (status, guard_refused)}; one sign-in per role."""
    app, pw, registered = world
    out = {}
    for role in ROLES:
        email = "platform@example.test" if role == "super_admin" else f"{role}.harbor-mutual@example.test"
        c = TestClient(app, raise_server_exceptions=False)  # a handler crash (500) still means the guard let the role in
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200, email
        rows = {}
        for key in registered:
            method, path = key.split(" ", 1)
            r = c.request(method, fill(path), headers={"X-CSRF-Token": c.cookies.get("sh_csrf", "")},
                          **({} if method in ("GET", "DELETE") else {"json": {}}))
            body = r.json() if r.status_code == 403 and "json" in r.headers.get("content-type", "") else {}
            # refused = the guard's own body, or the module gate (which runs first and says nothing about roles); the
            # guard's refusal carries its own header (SP-C1-03: its words now name who can act) so a handler's own "forbidden" is not mistaken for it
            guard = (r.headers.get("x-refused-by") == "access" and body.get("error") == "forbidden") or body.get("error") == "module_not_available"
            rows[key] = (r.status_code, guard)
        out[role] = rows
    return out


def test_every_intents_route_is_declared(world):
    undeclared = [k for k in world[2] if k not in PERMS.routes]
    assert not undeclared, f"registered but not in route_permissions.yaml: {undeclared}"


def test_yaml_intents_block_is_only_company_roles_or_super_admin_control():
    assert INTENT_KEYS, "no /api/intents lines in the yaml"
    for key in INTENT_KEYS:
        roles = PERMS.routes[key].roles
        assert roles and roles <= SIX, f"{key}: {sorted(roles)} (the super admin never reaches /api/intents)"


@pytest.mark.parametrize("role", ROLES)
def test_every_intents_route_against_role(world, grid, role):
    wrong = []
    for key, (status, guard) in grid[role].items():
        if key not in PERMS.routes:
            continue  # reported by test_every_intents_route_is_declared
        allowed = role in PERMS.routes[key].roles
        if allowed and guard:
            wrong.append(f"{role} {key}: listed in the yaml but the guard refused it")
        if not allowed and not guard:
            wrong.append(f"{role} {key}: not listed but answered {status}, not the guard's 403")
    assert not wrong, "\n" + "\n".join(wrong)


def test_super_admin_is_refused_on_every_intents_route(grid):
    assert grid["super_admin"] and all(guard for _s, guard in grid["super_admin"].values())


def test_settings_routes_are_company_admin_only(grid):
    for key in ("GET /api/intents/settings", "PUT /api/intents/settings"):
        for role in ROLES:
            if key in grid[role]:
                assert grid[role][key][1] == (role != "company_admin"), (role, key)


def test_only_the_share_view_and_approver_routes_are_guest():
    guests = {k for k, rule in PERMS.routes.items() if rule.guest and ("intent" in k or "approver" in k)}
    assert "POST /api/modules/m1_intent/shared/view" in guests
    assert all("/api/intents" not in k for k in guests), guests


# ---- the top bar (ui/src/shell/roles.ts)

def test_every_company_role_sees_the_intent_centre():
    assert set(TABLE) == set(ROLES)
    assert {r for r, row in TABLE.items() if "intent" in row["centres"]} == SIX
    assert "intent" not in TABLE["super_admin"]["centres"]


@pytest.mark.parametrize("role,bar", [
    ("participant", ["pulse", "intent", "consume", "tickets", "map"]),  # PF2 (10 Oct): every role reads Consume
    ("owner", ["pulse", "intent", "consume", "tickets", "map"]),
    ("approver", ["pulse", "intent", "consume", "tickets", "map"]),
    ("sponsor", ["pulse", "intent", "consume", "tickets", "map"]),
    ("analyst", ["pulse", "intent", "build", "consume", "tickets", "map"]),
    ("company_admin", ["pulse", "intent", "build", "consume", "tickets", "map", "control"]),
    ("super_admin", ["control"]),
])
def test_top_bar_per_role(role, bar):
    assert TABLE[role]["centres"] == bar


def test_build_stays_with_the_data_team():
    assert {r for r, row in TABLE.items() if "build" in row["centres"]} == {"analyst", "company_admin"}
