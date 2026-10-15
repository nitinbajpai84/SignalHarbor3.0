"""SF08: cross-card checks over SF01 to SF07 (read-only review; new tests only). Synthetic data, tmp planes, no model, no server.
1. what the propose tool collects (SF01) is what proposals.file (SF02) accepts;
2. specs from SF05 render through SF06's render_plain with no script and no web address;
3. another company's proposal, design and sandbox are unreachable (planes);
4. a role without access is refused on the proposal and dialect routes, with the real permission table applied in the test app only."""
import hashlib
import json

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from sh_platform.auth.permissions import load_permissions
from sh_platform.build import archify_spec as S, architecture as A, design_doc as D, dialect as DI, model_build as MB, proposals as P
from sh_platform.build.agents.read_tools import check_proposal
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer

FACTS = [{"label": "fund rows", "value": 1180, "group_size": 1180}, {"label": "keys changed", "value": 214, "group_size": 1180}]
GRACE = Viewer("Grace Ward", frozenset({"approver"}))
JANET = Viewer("Janet Shaw", frozenset({"company_admin"}))
INTENT = "ini-" + "sf08" * 8


def _w(plane, rel, doc):
    p = plane.path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def _evidence():
    return {"counts": [{"label": "keys changed", "value": 214, "group_size": 1180}], "fields": ["manager"]}


@pytest.fixture
def plane(tmp_path, monkeypatch):
    pl = PlaneStore(tmp_path).create("sf08-co")
    _w(pl, "build/blueprint.json", {
        "version": 1, "state": "signed", "signed_by": [{"name": "Grace Ward", "role": "Head of department"}],
        "infra": {"warehouse": "plane", "runner": "builtin"},
        "lineage": [{"measure": "K12", "source": "Custodian file", "mart": "gold.k12.stale_share", "transform": "Stale over all"}],
        "access": [{"mart": "gold.k12", "may_see": None}],
        "model": {"facts": [{"name": "fact_fund", "grain": "One row per fund per month", "keys": [], "measures": ["K12"]}],
                  "dimensions": [{"name": "dim_fund", "keys": [], "attributes": [], "scd": 2}]}})
    _w(pl, "build/pipelines/custodian_file.json", {"source": "custodian_file", "title": "Custodian file", "marts": ["gold.k12"], "expected": "Daily"})
    _w(pl, "build/changes/C-0001.json", {"id": "C-0001", "title": "Valuation chase", "intent_id": None, "state": "with_architect", "sections": {
        "why": [{"text": "Handed to Build", "mark": "guessed", "from": "t", "by": "Span", "at": "2026-10-01T00:00:00+00:00"}],
        "what_changes": [], "decisions": [], "tests": [], "run_book": [], "risks": [], "build_steps": []}})
    intent = {"id": INTENT, "type": "initiative", "build_handoff": {"processes": [], "source_map": [
        {"id": "s1", "name": "Custodian file", "zone": "p1", "strategic": True, "restricted": False}]}}
    from sh_platform.intents import store as istore
    from sh_platform.profile import store as pstore
    monkeypatch.setattr(istore, "read_index", lambda p: [{"id": INTENT, "type": "initiative"}])
    monkeypatch.setattr(istore, "read_intent", lambda p, i: intent if i == INTENT else None)
    monkeypatch.setattr(pstore, "raw", lambda p: {"people": {}, "systems": {}, "areas": {}})
    A.regenerate(pl, "blueprint_signed", "build/blueprint.json", "Grace Ward", [])
    return pl


@pytest.fixture
def addressed(monkeypatch):
    """Grace owns K12 and signed the blueprint; Harvey is the contact on the one alert (what proposals.file reads)."""
    from sh_platform.consume import cards
    monkeypatch.setattr(cards, "data_owner", lambda p, code: "Grace Ward")


# ---- 1. the propose tool's output is what proposals.file accepts ------------------------------------------------------------------------

def test_an_incident_note_from_the_sink_is_filed(plane, addressed):
    _w(plane, "build/alerts.json", {"alerts": [{"id": "late:custodian_file", "kind": "late", "source": "custodian_file", "state": "open", "tell": "Harvey Rowley"}]})
    item = check_proposal("flow", "incident_note", {"title": "Late file", "what": "Ask the custodian for the file again", "why": "The file has not landed",
                                                    "alert_id": "late:custodian_file"})
    got = P.file(plane, "Flow", [item], {"run_id": "r1", "facts": []})
    assert [p["to"] for p in got] == ["Harvey Rowley"] and got[0]["kind"] == "incident_note"


def test_a_model_change_from_the_sink_is_filed(plane, addressed):
    item = check_proposal("span", "model_change", {"title": "Keep fund manager history", "what": "Type 2 history on the fund dimension",
                                                   "why": "214 of 1180 fund rows changed manager", "technique": "scd2", "subject": "fund dimension", "measure": "aum",
                                                   "evidence": _evidence(), "effort": "small"})
    assert len(P.file(plane, "Span", [item], {"run_id": "r1", "facts": FACTS})) == 1


def test_an_architecture_decision_from_the_sink_is_filed(plane, addressed, monkeypatch):
    item = check_proposal("span", "architecture_decision", {"title": "Where the mart sits", "what": "Keep it in the main file", "why": "No access list",
                                                            "change_id": "C-0001", "placement": "gold.k12", "options": ["main file", "own file"], "chosen": "main file"})
    _w(plane, "build/changes/C-0001.json", {"id": "C-0001", "intent_id": "m1_intent", "state": "draft"})
    monkeypatch.setattr(P.chain, "people_of", lambda pl, intent, note=None: {"architect": {"name": "Aaron Lyle"}})
    assert len(P.file(plane, "Span", [item], {"run_id": "r1", "facts": []})) == 1


def test_the_sink_cannot_name_the_addressee(plane, addressed):
    with pytest.raises(Exception):
        check_proposal("span", "model_change", {"title": "t", "what": "w", "why": "y", "to": "Grace Ward"})
    # and a hand-made item carrying one is dropped by file(), so the two cards agree on the one thing that matters for safety
    bad = {"kind": "model_change", "args": {"title": "t", "what": "w", "why": "y", "subject": "fund dimension", "to": "Grace Ward"}}
    assert P.file(plane, "Span", [bad], {"facts": FACTS}) == []


# ---- 2. specs render through render_plain with no script and no web address -------------------------------------------------------------

def _diagrams(pl, draft=None):
    return {k: S.svg_with_boundaries(S.current(pl, JANET) if k == "current" else getattr(S, k)(pl, JANET, draft)) for k in ("current", "target", "delta")}


def test_specs_validate_and_render_in_the_plain_document(plane):
    draft = {"placements": [{"id": "gold:k20", "kind": "gold", "label": "gold.k20 </text><script>alert(1)</script>", "interfaces": []}]}
    for k in ("current", "target", "delta"):
        sp = getattr(S, k)(plane, JANET) if k == "current" else getattr(S, k)(plane, JANET, draft)
        assert S.validate(sp, S.known_ids(plane, JANET, draft)) == [], k
    doc = D.draft(plane)
    html = D.render_plain(doc, _diagrams(plane, draft))
    assert html.count("<svg") == 3 and "<script" not in html.lower() and "http" not in html.lower()
    assert "javascript:" not in html.lower() and "onload" not in html.lower() and "onclick" not in html.lower()
    assert S.PLANE_LABEL in html and S.EGRESS_LABEL in html
    # the diagram sits in the section the template names
    for sec in D.template():
        if sec.get("diagram"):
            at = html.index(f"<h2>{sec['title']}")
            assert "<svg" in html[at:html.find("<h2>", at + 1)], sec["title"]


def test_a_hostile_diagram_string_is_cleaned_by_the_renderer(plane):
    doc = D.draft(plane)
    evil = '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><a xlink:href="https://evil.example/x"><text>t</text></a></svg>'
    html = D.render_plain(doc, {"current": evil})
    assert "<script" not in html.lower() and "http" not in html.lower()


# ---- 3. another company's proposal, design and sandbox are unreachable ------------------------------------------------------------------

def test_planes_do_not_leak(tmp_path, plane, addressed):
    other = PlaneStore(tmp_path).create("sf08-other")
    _w(other, "build/blueprint.json", {"version": 1, "state": "signed", "signed_by": [{"name": "Grace Ward"}], "access": []})
    P.file(other, "Span", [{"kind": "model_change", "args": {"title": "t", "technique": "grain statement", "what": "w", "why": "y", "subject": "other dim"}}], {"facts": []})
    assert P.all_proposals(other) and P.all_proposals(plane) == []
    assert P.read(plane, "P-0001") is None and P.read(plane, "../sf08-other/build/proposals/P-0001") is None
    # design: a draft in one plane is not read from the other
    D.draft(plane)
    assert D.read(plane) is not None and D.read(other) is None
    # sandbox: the path is inside the plane; an id that climbs out is refused; building in one plane leaves the other warehouse untouched
    assert MB.sandbox_path(plane, "d1").is_relative_to(plane.path("warehouse"))
    for bad in ("../x", "..\\x", "a/b", "", "x" * 65):
        with pytest.raises(ValueError):
            MB.sandbox_path(plane, bad)
    assert MB.sandbox_path(plane, "d1") != MB.sandbox_path(other, "d1")
    other_wh = other.path("warehouse", "company.duckdb")
    other_wh.parent.mkdir(parents=True, exist_ok=True)
    other_wh.write_bytes(b"not touched")
    before = hashlib.sha256(other_wh.read_bytes()).hexdigest()
    report = MB.sandbox_build(plane, "d1", {"dimensions": [], "facts": []}, {"marts": []})
    assert report["errors"] and hashlib.sha256(other_wh.read_bytes()).hexdigest() == before
    assert not list(plane.path("warehouse").glob("sandbox/*.duckdb"))


# ---- 4. a role without access is refused on the proposal and dialect routes -------------------------------------------------------------

@pytest.fixture
def secured(plane, addressed, monkeypatch):
    """The two routers on a bare app, behind a middleware that applies the REAL route_permissions.yaml (default deny). The role comes from
    the X-Role header; the person is injected as in test_sf02."""
    table = load_permissions()
    app = FastAPI()
    app.include_router(P.router)
    app.include_router(DI.router)

    routes = [r for rt in (P.router, DI.router) for r in rt.routes]

    @app.middleware("http")
    async def gate(request: Request, call_next):
        hit = next((r for r in routes if request.method in r.methods and r.path_regex.fullmatch(request.url.path)), None)
        rule = table.rule_for(request.method, hit.path_format) if hit else None
        role = request.headers.get("X-Role")
        if rule is None or not (role and role in rule.roles):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        return await call_next(request)

    monkeypatch.setattr(P, "_plane", lambda r: plane)
    monkeypatch.setattr(P, "_viewer", lambda r: GRACE)
    monkeypatch.setattr(DI, "_plane", lambda r: plane)
    pid = P.file(plane, "Span", [{"kind": "model_change", "args": {"title": "t", "technique": "grain statement", "what": "w", "why": "y", "subject": "fund dimension", "measure": "K12"}}],
                 {"facts": []})[0]["id"]
    return TestClient(app), pid


def test_a_role_without_access_is_refused(secured):
    c, pid = secured
    paths = [("get", "/api/company/build/proposals"), ("get", f"/api/company/build/proposals/{pid}"),
             ("post", f"/api/company/build/proposals/{pid}/accept"), ("post", f"/api/company/build/proposals/{pid}/decline"),
             ("post", f"/api/company/build/proposals/{pid}/ask"), ("get", "/api/company/build/dialect"), ("get", "/api/company/build/dialect/download")]
    for method, path in paths:
        assert getattr(c, method)(path).status_code == 403, f"{method} {path} with no role"
        assert getattr(c, method)(path, headers={"X-Role": "super_admin"}).status_code == 403, f"{method} {path} as super_admin"
    for method, path in paths[5:]:  # the dialect routes are for the company admin and the analyst only
        for role in ("participant", "sponsor", "owner", "approver"):
            assert getattr(c, method)(path, headers={"X-Role": role}).status_code == 403, f"{method} {path} as {role}"
        r = getattr(c, method)(path, headers={"X-Role": "analyst"})
        assert r.status_code != 403, r.text
    assert c.get("/api/company/build/proposals", headers={"X-Role": "approver"}).status_code == 200  # Grace sees her own


def test_permission_lines_match_the_plan():
    t = load_permissions()
    ids = ("company_admin", "analyst", "sponsor", "owner", "approver", "participant")
    for key in ("GET /api/company/build/proposals", "GET /api/company/build/proposals/{pid}", "POST /api/company/build/proposals/{pid}/accept",
                "POST /api/company/build/proposals/{pid}/decline", "POST /api/company/build/proposals/{pid}/ask"):
        assert set(ids) == set(t.routes[key].roles), key
    for key in ("GET /api/company/build/dialect", "GET /api/company/build/dialect/download"):
        assert t.routes[key].roles == {"company_admin", "analyst"}, key
