"""A-073: one role table (ui/src/shell/roles.ts) drives the top bar, the routes and the server permissions.

Reads the table from the file's text and checks route_permissions.yaml agrees with it. A route that is a named
act (a signature, an accept, an alert someone must answer) may differ from its centre; each is pinned here with why.
"""
import json
import re
from pathlib import Path

from sh_platform.auth.permissions import load_permissions

ROLES_TS = Path(__file__).resolve().parents[2] / "ui" / "src" / "shell" / "roles.ts"
PERMS = load_permissions()


def role_table() -> dict[str, dict]:
    text = ROLES_TS.read_text(encoding="utf-8")
    body = re.search(r"/\* role table \*/(.*?)/\* end role table \*/", text, re.S)
    assert body, "roles.ts must keep the table between the /* role table */ markers"
    return json.loads(body.group(1))


TABLE = role_table()


def seers(centre: str) -> frozenset[str]:
    return frozenset(r for r, row in TABLE.items() if centre in row["centres"])


def routes_under(*prefixes: str) -> dict[str, frozenset[str]]:
    out = {}
    for key, rule in PERMS.routes.items():
        path = key.split(" ", 1)[1]
        if any(path == p or path.startswith(p + "/") for p in prefixes):
            out[key] = rule.roles
    return out


# Act routes: one list, kept in test_role_matrix (ACTS); imported as a module so its tests are not collected twice.
import test_role_matrix as _matrix  # noqa: E402

ACTS = _matrix.ACTS

CENTRE_ROUTES = {
    "build": ("/api/company/build",),
    "pulse": ("/api/pulse", "/api/memory"),
    "map": ("/api/company/graph", "/api/company/register"),
    "consume": ("/api/company/feeds", "/api/company/market", "/api/company/whatif"),
}


def test_table_names_exactly_the_server_roles():
    assert set(TABLE) == set(PERMS.roles)


def test_bar_order_and_landing():
    order = ["pulse", "intent", "build", "consume", "tickets", "map", "control"]
    for role, row in TABLE.items():
        assert row["centres"] == sorted(row["centres"], key=order.index), role
        assert row["lands"] == ("/centre/control" if role == "super_admin" else "/centre/action"), role
    assert TABLE["super_admin"]["centres"] == ["control"]


def test_centre_routes_agree_with_the_table():
    wrong = {}
    for centre, prefixes in CENTRE_ROUTES.items():
        found = routes_under(*prefixes)
        assert found, f"no routes found for {centre}"
        for key, roles in found.items():
            want = ACTS.get(key, seers(centre))
            if roles != want:
                wrong[key] = (sorted(roles), sorted(want))
    assert not wrong, wrong


def test_act_routes_still_exist():
    assert set(ACTS) <= set(PERMS.routes)


def test_control_routes_stay_inside_the_control_roles():
    for key, roles in routes_under("/api/control", "/api/company/settings", "/api/company/egress-log").items():
        assert roles and roles <= seers("control"), key
    assert all(r == {"super_admin"} for r in routes_under("/api/control").values())


def test_super_admin_reads_no_company_centre():
    company = routes_under(*(p for ps in CENTRE_ROUTES.values() for p in ps))
    assert not [k for k, roles in company.items() if "super_admin" in roles]
