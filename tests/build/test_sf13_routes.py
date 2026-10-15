"""SF13: the Span and Flow routes, the design sign in the approve act, the blueprint sign hook and the Pulse lines. Synthetic data only, the
b59 temporary plane, routes on a bare app with the person injected; no model (the factory returns None, so every agent falls back)."""
import json

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from sh_platform.auth.permissions import load_permissions
from sh_platform.build import architecture as A, blueprint as B, chain as C, design_doc, proposals as P
from sh_platform.build.agents import routes as RT, span_suggest
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from tests.build.test_b59 import WHO, _r, _w, world  # noqa: F401  (world is a fixture)

RUN = "a" * 32
ROUTES = [("get", "/api/company/build/span/target"), ("post", "/api/company/build/span/target"), ("get", "/api/company/build/span/model-draft"),
          ("post", "/api/company/build/span/model-draft"), ("post", "/api/company/build/span/model-draft/D1/file"), ("post", "/api/company/build/span/review"),
          ("get", "/api/company/build/design"), ("get", "/api/company/build/design/download"), ("get", "/api/company/build/design/spec"),
          ("put", "/api/company/build/design/spec"), ("put", "/api/company/build/design/lines"), ("post", "/api/company/build/design/redraft"),
          ("get", f"/api/company/build/flow/runs/{RUN}"), ("post", f"/api/company/build/flow/runs/{RUN}/explain"), ("get", "/api/company/build/flow/incidents")]
PLAN = {"GET /api/company/build/span/target": "all", "POST /api/company/build/span/target": "ca", "GET /api/company/build/span/model-draft": "ca",
        "POST /api/company/build/span/model-draft": "ca", "POST /api/company/build/span/model-draft/{draft_id}/file": "ca",
        "POST /api/company/build/span/review": "cao", "GET /api/company/build/design": "all", "GET /api/company/build/design/download": "all",
        "GET /api/company/build/design/spec": "all", "PUT /api/company/build/design/spec": "ca", "PUT /api/company/build/design/lines": "ca",
        "POST /api/company/build/design/redraft": "ca", "GET /api/company/build/flow/runs/{run_id}": "cao",
        "POST /api/company/build/flow/runs/{run_id}/explain": "ca", "GET /api/company/build/flow/incidents": "cao"}
ROLES = {"all": {"company_admin", "analyst", "sponsor", "owner", "approver", "participant"}, "ca": {"company_admin", "analyst"},
         "cao": {"company_admin", "analyst", "owner"}}


class Ent:
    def __init__(self):
        self.build_on, self.known = True, True

    def company(self, cid):
        return {"company_id": cid, "name": "Test Co", "industry": "family office"} if self.known else None

    def switches(self, cid):
        return {"modules": {}, "centres": {"build": self.build_on}}

    def is_enabled(self, cid, mid):
        return True


def _app(plane, me, monkeypatch, routers=()):
    app = FastAPI()
    C.install(app)
    app.include_router(RT.router)
    for r in routers:
        app.include_router(r)
    app.state.entitlements, app.state.build_model_factory = Ent(), (lambda p: None)

    @app.middleware("http")
    async def company(request: Request, call_next):
        request.state.company_id = plane.company_id
        return await call_next(request)
    for mod in (C, A, RT, B):
        monkeypatch.setattr(mod, "_plane", lambda r: plane)
        monkeypatch.setattr(mod, "_viewer", lambda r: me["v"])
    monkeypatch.setattr(B, "_name", lambda r: me["v"].name)
    monkeypatch.setattr(RT, "_spawn", lambda fn: fn())  # long drafts run inline in tests
    return app


@pytest.fixture
def app_(world, monkeypatch):  # noqa: F811
    plane, _ = world
    me = {"v": WHO["aaron"]}
    app = _app(plane, me, monkeypatch, [B.router])

    def as_(who):
        me["v"] = WHO[who]
        return TestClient(app)
    return plane, as_, app


def test_permission_lines_match_the_plan_and_a_role_outside_them_is_refused(app_):
    _, _, app = app_
    table = load_permissions()
    for key, group in PLAN.items():
        assert table.routes[key].roles == ROLES[group], key
    gated = FastAPI()
    gated.include_router(RT.router)

    @gated.middleware("http")
    async def gate(request: Request, call_next):  # the real table, default deny
        hit = next((r for r in RT.router.routes if request.method in r.methods and r.path_regex.fullmatch(request.url.path)), None)
        rule = table.rule_for(request.method, hit.path_format) if hit else None
        role = request.headers.get("X-Role")
        if rule is None or not (role and role in rule.roles):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        return JSONResponse({"ok": True})
    c = TestClient(gated)
    for method, path in ROUTES:
        hit = next(r for r in RT.router.routes if method.upper() in r.methods and r.path_regex.fullmatch(path))
        allowed = table.rule_for(method.upper(), hit.path_format).roles
        for role in ("super_admin", "company_admin", "analyst", "sponsor", "owner", "approver", "participant"):
            assert (getattr(c, method)(path, headers={"X-Role": role}).status_code == 200) == (role in allowed), (method, path, role)


def test_a_switched_off_company_is_refused_on_every_route(app_):
    _, as_, app = app_
    for flag in ("build_on", "known"):
        setattr(app.state.entitlements, flag, False)
        for method, path in ROUTES:
            r = getattr(as_("janet"), method)(path)
            assert r.status_code == 403 and r.json()["error"] == "build_off", (flag, method, path)
        setattr(app.state.entitlements, flag, True)


def test_only_the_architect_asks_span(app_):
    _, as_, _ = app_
    as_("aaron").get("/api/company/build/changes")  # the note opens and names Aaron as its architect
    for method, path in [("post", "/api/company/build/span/target"), ("post", "/api/company/build/span/model-draft"),
                         ("put", "/api/company/build/design/spec"), ("put", "/api/company/build/design/lines"), ("post", "/api/company/build/design/redraft")]:
        r = getattr(as_("katie"), method)(path, json={})
        assert r.status_code == 403 and r.json()["message"] == RT.NOT_ARCHITECT, path
    r = as_("aaron").post("/api/company/build/span/model-draft", json={"changes": "keep fund history"})
    assert r.status_code == 409 and r.json()["error"] == "nothing_to_draft"  # SF09b: nothing landed yet, a plain refusal
    got = as_("katie").get("/api/company/build/span/model-draft").json()  # analysts read it
    assert got["state"] == "none" and "fallback" in got
    assert as_("aaron").post("/api/company/build/span/model-draft/D-nope/file").status_code == 404
    assert as_("aaron").post("/api/company/build/span/target", json={"intent_id": "../x"}).status_code == 422


def test_approving_the_change_signs_the_design_and_the_signed_version_stays(app_):
    plane, as_, _ = app_
    assert as_("aaron").get("/api/company/build/changes").status_code == 200  # the note opens
    assert design_doc.draft(plane, fallback=True)["state"] == "draft"
    d = as_("mei").get("/api/company/build/design").json()
    assert d["fallback"] is True and d["message"] == design_doc.SPAN_SENTENCE and d["doc"]["state"] == "draft" and set(d["diagrams"]) <= set(RT.KINDS)
    assert as_("aaron").post("/api/company/build/changes/C-0001/send").json()["step"] == 2
    as_("grace").put("/api/company/build/architecture/components/gold:k12", json={"owner": "harvey-rowley"})
    assert as_("grace").post("/api/company/build/changes/C-0001/approve").json()["state"] == "building"
    doc = design_doc.read(plane)
    assert doc["state"] == "signed" and doc["signed_by"][0]["name"] == "Grace Ward" and _r(plane, "build/blueprint.json")["state"] == "signed"
    v1 = plane.path("build", "design", "design.v1.json").read_text(encoding="utf-8")
    r = as_("aaron").put("/api/company/build/design/lines", json={"section": "context", "index": 0, "text": "Aaron's wording"})
    assert r.status_code == 200 and r.json()["doc"]["version"] == 2 and r.json()["doc"]["state"] == "draft"
    assert plane.path("build", "design", "design.v1.json").read_text(encoding="utf-8") == v1  # the signed version is untouched
    assert as_("aaron").put("/api/company/build/design/lines", json={"section": "context", "index": 99, "text": "x"}).status_code == 404


def test_download_is_plain_html_as_an_attachment(app_):
    plane, as_, _ = app_
    as_("aaron").get("/api/company/build/changes")
    design_doc.draft(plane)
    r = as_("daniel").get("/api/company/build/design/download")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert r.headers["content-disposition"] == 'attachment; filename="design-document-v1.html"'
    assert "<h1>Design document, version 1</h1>" in r.text and "<script" not in r.text.lower()


def test_put_spec_refuses_an_invalid_spec_and_keeps_a_valid_one_as_stated(app_, monkeypatch):
    plane, as_, _ = app_
    as_("aaron").get("/api/company/build/changes")
    design_doc.draft(plane)
    bad = as_("aaron").put("/api/company/build/design/spec", json={"kind": "target", "spec": {"components": "nope"}})
    assert bad.status_code == 422 and bad.json()["message"].startswith("The diagram could not be drawn: ")
    good = as_("aaron").get("/api/company/build/design/spec?kind=target").json()
    assert good["stated"] is False
    spec = good["spec"]
    spec["components"][0]["label"] = "Aaron layout"
    r = as_("aaron").put("/api/company/build/design/spec", json={"kind": "target", "spec": spec})
    assert r.status_code == 200 and r.json()["stated"] is True, r.text
    monkeypatch.setattr(span_suggest, "review", lambda *a, **k: None)
    assert as_("aaron").post("/api/company/build/design/redraft").status_code == 202  # inline: no model, records only
    back = as_("mei").get("/api/company/build/design/spec?kind=target").json()
    assert back["stated"] is True and back["spec"]["components"][0]["label"] == "Aaron layout"


def test_flow_notes_fall_back_and_hide_what_is_not_there(app_):
    plane, as_, _ = app_
    _w(plane, "warehouse/runs.json", {"runs": [{"id": RUN, "source": "custodian_file", "status": "failed", "on_time": True, "schema_ok": True, "rows": 40,
                                                "rules": [{"rule": "K12:holding_id must not be empty", "passed": False, "count": 12}]}]})
    r = as_("janet").get(f"/api/company/build/flow/runs/{RUN}")
    assert r.status_code == 200 and r.json()["fallback"] is True and r.json()["sentence"].startswith("Flow could not reach the model")
    assert as_("janet").get(f"/api/company/build/flow/runs/{'b' * 32}").status_code == 404
    assert as_("janet").post(f"/api/company/build/flow/runs/{RUN}/explain").json()["fallback"] is True
    assert as_("janet").get("/api/company/build/flow/incidents").json() == {"incidents": [], "fallback": False}
    _w(plane, "build/alerts.json", {"alerts": [{"id": "al-1", "kind": "failed", "source": "custodian_file", "state": "open", "opened": "2026-10-07",
                                                "tell": "Katie Menon"}]})
    inc = as_("janet").get("/api/company/build/flow/incidents").json()["incidents"]
    assert len(inc) == 1 and inc[0]["alert_id"] == "al-1" and inc[0]["fallback"] is True
    assert as_("harvey").get("/api/company/build/flow/incidents").json()["incidents"] == []  # not the addressee


def test_blueprint_signature_starts_one_review(app_, monkeypatch):
    plane, as_, _ = app_
    seen = []
    monkeypatch.setattr(span_suggest, "review", lambda pl, rt, intent_id=None: seen.append(pl.company_id))
    r = as_("janet").post("/api/company/build/blueprint/sign")
    assert r.status_code == 200, r.text
    assert seen == [plane.company_id]


def test_pulse_lines_go_to_the_addressee_and_survive_the_cap(app_):
    plane, as_, _ = app_
    from sh_platform.pulse import intent_lines as IL
    as_("aaron").get("/api/company/build/changes")
    design_doc.draft(plane)
    _w(plane, "build/blueprint.json", {**_r(plane, "build/blueprint.json"), "signed_by": [{"name": "Grace Ward", "role": "Head of department"}]})
    pid = P.file(plane, "Span", [{"kind": "model_change", "args": {"title": "t", "technique": "grain statement", "what": "w", "why": "y", "subject": "fund dimension", "measure": "K12"}}],
                 {"facts": []})[0]["id"]
    to = P.read(plane, pid)["to"]
    who = next(k for k, v in WHO.items() if v.name == to)
    mine = [ln for ln in IL.others(plane, WHO[who]).get("decide", []) if ln["id"] == f"proposal:{pid}"]
    assert len(mine) == 1 and mine[0]["kind"] == "decision"
    other = next(k for k in WHO if k != who and k != "janet")
    assert not [ln for ln in IL.others(plane, WHO[other]).get("decide", []) if ln["id"].startswith("proposal:")]
    assert [ln["title"] for ln in RT.agent_lines(plane, WHO["aaron"])["decide"]] == ["Span drafted the design document for B59a valuation chase. Check it."]
    assert RT.agent_lines(plane, WHO["grace"])["decide"] == []
    watch = [{"id": f"w{i}", "kind": "brief"} for i in range(10)]
    kept = dict(IL._protect([("watch", watch), ("decide", mine)], 3, lambda rows: rows))
    assert kept["decide"] == mine  # R10: a decision line is never cut by the cap


def test_empty_company_reads_the_empty_sentences(tmp_path, monkeypatch):
    plane = PlaneStore(tmp_path).create("empty-co")
    me = {"v": Viewer("Ann Example", frozenset({"company_admin"}))}
    c = TestClient(_app(plane, me, monkeypatch))
    assert c.get("/api/company/build/span/target").json() == {"draft": None, "fallback": False, "message": None, "empty": RT.EMPTY_TARGET}
    d = c.get("/api/company/build/design").json()
    assert d["doc"] is None and d["empty"] == design_doc.EMPTY and d["fallback"] is False
    m = c.get("/api/company/build/span/model-draft").json()
    assert m["state"] == "none" and m["fallback"] is False
    assert c.post("/api/company/build/design/redraft").status_code == 409
    assert c.put("/api/company/build/design/spec", json={"kind": "target", "spec": json.loads("{}")}).status_code == 422


def test_the_agent_gate_follows_the_build_centre_switch_not_m4_build(app_):
    from types import SimpleNamespace
    from sh_platform.agents.loop import run_agent
    from sh_platform.agents.registry import ToolRegistry
    plane, _, app = app_
    ent = app.state.entitlements
    ent.is_enabled = lambda cid, mid: False  # m4_build is off, as it is for every seeded company
    calls = []

    class Model:
        def complete(self, module_id, messages, tools):
            calls.append(module_id)
            return SimpleNamespace(text="Reviewed.", tool_calls=[])
    app.state.build_model_factory = lambda p: Model()
    req = SimpleNamespace(app=app, state=SimpleNamespace(company_id=plane.company_id))
    rt = RT.R.runtime_for_request(req, plane, Viewer("", frozenset()))
    assert run_agent(rt.model, ToolRegistry(rt.gate), rt.company_id, RT.R.MODULE_ID, "Span", "s", {}, "q").status == "done" and calls
    ent.build_on = False
    calls.clear()
    assert run_agent(rt.model, ToolRegistry(rt.gate), rt.company_id, RT.R.MODULE_ID, "Span", "s", {}, "q").status == "refused" and not calls
