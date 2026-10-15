"""A-073 matrix: every API route x every ardmore role (and the super admin) against the role table.

Runs the real app on a temporary copy of the real data root (so POSTs with empty bodies cannot touch the demo data).
"denied" = the route guard's own 403 body (a handler's 403 about a record or a named act means the guard let the role in).
A module switched off for the company ("module_not_available") says nothing about roles and is skipped. Skipped if the seed credentials are absent.
"""
import json
import os
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.auth import route_keys, all_routes
from sh_platform.auth.permissions import load_permissions
from sh_platform.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")

TABLE = json.loads(re.search(r"/\* role table \*/(.*?)/\* end role table \*/",
                             (ROOT / "ui/src/shell/roles.ts").read_text(encoding="utf-8"), re.S).group(1))
ROLES = ["participant", "owner", "approver", "sponsor", "analyst", "company_admin", "super_admin"]
ORGANISER = {"company_admin", "sponsor", "analyst"}  # A-025: the Intent routes' own capability
# Named acts that may reach outside their centre (QUALITY-PASS section 1; proofs also admit sponsor, owner, approver).
ACTS = {
    "POST /api/company/whatif/keep": {"company_admin", "sponsor", "analyst"},  # Q12: keeping a scenario is an act for those who steer
    "GET /api/company/whatif/kept": {"company_admin", "sponsor", "analyst"},
    "GET /api/company/build/prove": {"analyst", "approver", "company_admin", "owner", "sponsor"},
    "PUT /api/company/build/environment": {"company_admin"},
    "POST /api/company/build/blueprint/sign": {"company_admin"},
    "POST /api/company/build/prove/{measure}/accept": {"company_admin", "analyst", "owner"},
    "POST /api/company/build/release/sign": {"sponsor", "company_admin"},
    "POST /api/company/build/uat/{measure}/sign": {"sponsor", "approver", "owner", "company_admin", "analyst"},
    "POST /api/company/build/alerts/{alert_id}/ack": {"company_admin", "analyst", "owner"},
    "POST /api/company/build/alerts/{alert_id}/close": {"company_admin", "analyst", "owner"},
    "GET /api/pulse/messages": ORGANISER,
    "POST /api/pulse/messages/{message_id}/send": ORGANISER,
    "POST /api/company/market/briefs": {"company_admin"},
}
# 59: the build chain's named people (architect, head of department, tester, ops) sit outside the Build centre; the handlers check the person
CHAIN = {"company_admin", "analyst", "sponsor", "owner", "approver", "participant"}
ACTS.update({k: CHAIN for k in (
    "GET /api/company/build/gap-analysis", "POST /api/company/build/gap-analysis/{intent_id}/start",  # N6: room 0, the organiser or the Build team
    "GET /api/company/build/architecture", "GET /api/company/build/architecture/diagram", "PUT /api/company/build/architecture/components/{component_id}",
    "GET /api/company/build/changes", "GET /api/company/build/changes/{cid}", "PUT /api/company/build/changes/{cid}/lines",
    *(f"POST /api/company/build/changes/{{cid}}/{x}" for x in ("send", "redraft", "approve", "built", "take-over", "send-back", "stop")))})
ACTS.update({k: CHAIN for k in (  # SF13: Span and Flow routes and the wave-1 proposal routes; handlers filter to the addressee or the architect
    "GET /api/company/build/span/target", "GET /api/company/build/design", "GET /api/company/build/design/download", "GET /api/company/build/design/spec",
    "GET /api/company/build/proposals", "GET /api/company/build/proposals/{pid}",
    *(f"POST /api/company/build/proposals/{{pid}}/{x}" for x in ("accept", "decline", "ask")))})
ACTS.update({k: {"company_admin", "analyst", "owner"} for k in (
    "POST /api/company/build/span/review", "GET /api/company/build/flow/runs/{run_id}", "GET /api/company/build/flow/incidents")})

# Module acts that name people outside the organiser trio (the yaml's own roles, pinned here so a change shows up).
M2 = "/api/modules/m2_baseline/baselines/{baseline_id}"
SIGNERS = {"company_admin", "sponsor"}  # the sponsor signs and settles; the organiser may act for the company
ACTS.update({f"POST {k}": SIGNERS for k in (
    "/api/modules/m1_intent/sessions/{session_id}/charter/sign", M2 + "/catalogue/conflicts/{conflict_id}/settle",
    M2 + "/signoff/settle", M2 + "/countersign", M2 + "/versions", M2 + "/review/{kpi_id}/leave-out",
    M2 + "/review/{kpi_id}/bring-back", M2 + "/kpis/{kpi_id}/ambiguities/{amb_id}/accept")})
ACTS.update({
    "PUT " + M2 + "/governance/fields/{field_id}": SIGNERS,
    "POST " + M2 + "/review/{kpi_id}/accept": {"sponsor"},  # only the sponsor accepts or reassigns a review line
    "POST " + M2 + "/review/{kpi_id}/owner": {"sponsor"},
    "POST /api/modules/m1_intent/retention/purge": {"company_admin"},
    # a seat holder gets a limited view of their own session; the handler gives anyone else "not found"
    "GET /api/modules/m1_intent/sessions/{session_id}": ORGANISER | {"participant", "owner", "approver"},
    "POST /api/modules/m1_intent/sessions/{session_id}/together/done": {"participant"},  # a seat's own "I am done"
    # the yaml lets all three in; trial.py decides in its handler (analyst or head of data run it, the analyst alone checks a rule)
    "POST /api/modules/m3_connect/assessments/{assessment_id}/trial/compile": {"analyst", "company_admin"},
    "POST /api/modules/m3_connect/assessments/{assessment_id}/trial/run": {"analyst", "company_admin"},
    "POST /api/modules/m3_connect/assessments/{assessment_id}/trial/rules/{measure_id}/check": {"analyst"},
    "GET " + M2 + "/governed": {"analyst", "approver", "company_admin", "owner", "sponsor"},
    "POST " + M2 + "/governed/{measure_id}/confirm": {"analyst", "approver", "company_admin", "owner", "sponsor", "participant"},  # a participant named as data owner confirms; the store checks the name
    "GET " + M2 + "/review": {"analyst", "company_admin", "owner", "sponsor"},  # the owner confirms their own definition
    "PUT " + M2 + "/review/{kpi_id}": {"analyst", "company_admin", "owner", "sponsor"},
    "GET " + M2 + "/audit": {"analyst", "company_admin", "owner", "sponsor"},
    "GET " + M2 + "/handoff": {"analyst", "company_admin", "owner", "sponsor"},
    "GET " + M2 + "/technical": {"analyst", "approver", "company_admin", "owner", "sponsor"},  # the technical owner and the governance lead read it
    "POST " + M2 + "/glossary/entries/{kpi_id}/review": {"analyst", "approver", "company_admin", "owner", "sponsor"},  # file 29: the term owner reviews
})
ACTS.update({f"{k.split(' ')[0]} {M2}{k.split(' ')[1]}": {"analyst", "approver", "company_admin", "owner", "participant", "sponsor"}
             for k in ("POST /confirm", "GET /my-parts", "GET /my-technical", "POST /kpis/{kpi_id}/technical/confirm",
                       "POST /measures/{kpi_id}/send-back")})  # each person confirms their own parts
ACTS.update({k: CHAIN for k in (  # the named tester may hold any company role; the handlers check the person (Q10, FX10, R2)
    "GET /api/company/build/prove", "POST /api/company/build/prove/recheck", "POST /api/company/build/uat/{measure}/sign")})
ACTS["GET /api/company/build/ops"] = {"company_admin", "analyst", "owner"}  # the owner reads the alerts they act on
SIX = {"participant", "owner", "company_admin", "sponsor", "analyst", "approver"}
ACTS.update({  # routes every seat reaches; the handlers limit the rows (manifest roles, mirrored in the yaml on 7 Oct)
    "POST /api/modules/m1_intent/shared/note": SIX,  # a note to the organiser from anyone affected
    "GET " + M2 + "/glossary": SIX,  # file 29: owners confirm, participants read
    "GET " + M2 + "/data-sources": SIX, "PUT " + M2 + "/data-sources/{source_id}": SIX,
    "POST " + M2 + "/data-sources/{source_id}/confirm": SIX, "POST " + M2 + "/data-sources/{source_id}/reassign": SIX,
    "POST " + M2 + "/data-sources/{source_id}/problems": SIX - {"approver"},
    "POST " + M2 + "/data-sources": {"company_admin", "sponsor", "analyst", "participant"},
    "POST " + M2 + "/data-sources/areas": {"company_admin", "sponsor", "analyst", "participant"},
    "PUT " + M2 + "/data-sources/areas/{area_id}": {"company_admin", "sponsor", "analyst", "participant"},
    "POST " + M2 + "/data-sources/draft": {"company_admin", "sponsor"}, "POST " + M2 + "/data-sources/done": {"company_admin"},
})
ACTS.update({f"POST /api/modules/interview/guest/{x}": set() for x in ("start", "answer", "finish")})  # a link token, never a signed-in role
CENTRES = {"build": ("/api/company/build",), "pulse": ("/api/pulse", "/api/memory", "/api/company/memory"),
           "map": ("/api/company/graph", "/api/company/register"),
           "consume": ("/api/company/feeds", "/api/company/market", "/api/company/whatif")}
MODULES = ("/api/modules/m1_intent", "/api/modules/m2_baseline", "/api/modules/m3_connect")
GUARD_403 = {"error": "forbidden", "message": "You do not have access to this."}
NO_COMPANY_OK = ("/api/health", "/api/auth", "/api/control", "/api/admin")  # the super admin may reach these


def under(path, prefixes):
    return any(path == p or path.startswith(p + "/") for p in prefixes)


def expected(key, role, rule):
    """True = may reach, False = must be refused, None = the table says nothing."""
    method, path = key.split(" ", 1)
    if key in ACTS:
        return role in ACTS[key]
    if role == "super_admin":
        return under(path, NO_COMPANY_OK) or rule.public
    if rule.public or path.startswith("/api/auth"):
        return True
    if under(path, ("/api/control", "/api/admin")):
        return False
    if under(path, ("/api/company/settings", "/api/company/egress-log")):
        return role == "company_admin"
    for centre, prefixes in CENTRES.items():
        if under(path, prefixes):
            if path.startswith("/api/company/memory"):
                return role == "company_admin"
            return centre in TABLE[role]["centres"]
    if under(path, MODULES):
        if role in ORGANISER:
            return True
        return None if rule.guest else False  # an invite link opens the wall for anyone with a seat
    return True if role == "company_admin" else None


def fill(path):
    return re.sub(r"\{[^}]+\}", "x", path)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")  # the real .env holds keys: this test must never make a live model call
    data = tmp_path_factory.mktemp("matrix") / "data"
    shutil.copytree(ROOT / "data", data)
    settings = Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")
    app = create_app(settings)
    perms = load_permissions()
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    routes = []
    for r in all_routes(app):
        for k in route_keys(r):
            if k.startswith(("MOUNT", "WEBSOCKET")) or k.startswith("POST /api/auth") or k in routes:
                continue
            routes.append(k)
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    yield app, perms, pw, routes
    mp.undo()


def results_for(world, role):
    app, perms, pw, routes = world
    email = "platform@example.test" if role == "super_admin" else f"{role}.harbor-mutual@example.test"
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": pw[email]})
    assert r.status_code == 200, (email, r.status_code)
    out = {}
    for key in routes:
        method, path = key.split(" ", 1)
        resp = c.request(method, fill(path), headers={"X-CSRF-Token": c.cookies.get("sh_csrf", "")},
                         **({} if method in ("GET", "DELETE") else {"json": {}}))
        denied = resp.status_code == 403 and "json" in resp.headers.get("content-type", "") \
            and resp.json().get("error") in ("forbidden", "module_not_available")
        out[key] = (resp.status_code, denied)
    return out


@pytest.mark.parametrize("role", ROLES)
def test_matrix(world, role):
    perms = world[1]
    res = results_for(world, role)
    if os.environ.get("X1_DUMP"):  # full status grid for the report: X1_DUMP=path pytest ...
        Path(os.environ["X1_DUMP"] + f".{role}.json").write_text(json.dumps(res))
    wrong = []
    for key, (status, denied) in res.items():
        if key not in perms.routes:
            continue  # reported once by test_every_route_is_declared
        want = expected(key, role, perms.routes[key])
        if want is True and denied:
            wrong.append(f"{role} {key}: expected allowed, got {status}")
        if want is False and not denied:
            wrong.append(f"{role} {key}: expected 403, got {status}")
    assert not wrong, "\n" + "\n".join(wrong)


def test_every_route_is_declared(world):
    """Default deny: a registered route with no yaml line is refused for everyone, so a screen calling it is dead."""
    undeclared = [k for k in world[3] if k not in world[1].routes]
    assert not undeclared, f"registered but not in route_permissions.yaml: {undeclared}"
