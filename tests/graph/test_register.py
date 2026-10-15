"""GET /api/company/register: rows from signed records, gated by the viewer's graph. Synthetic data."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import load_settings

ROOT = Path(__file__).resolve().parents[2]
FAMILY = "lakeside-family-office"
CID = "a" * 32


def n(i, t, label, **kw):
    return {"id": i, "type": t, "label": label, "provenance": [], **kw}


def e(a, b, t):
    return {"from": a, "to": b, "type": t, "provenance": []}


DOC = {"version": 1, "built_at": "2026-10-06T00:00:00+00:00",
       "nodes": [n("measure:kpi-1", "Measure", "Single-issuer concentration"), n("term:kpi-1", "Term", "Concentration"), n("person:dan", "Person", "Dan Data"),
                 n("problem:p1", "Problem", "Too concentrated"), n("measure:kpi-2", "Measure", "Secret measure", restricted_to=["priya nair"])],
       "edges": [e("measure:kpi-1", "person:dan", "owned_by"), e("problem:p1", "measure:kpi-1", "measured_by"), e("measure:kpi-2", "person:dan", "owned_by")]}
SIGN = {"signed_at": "2026-10-02T09:00:00+00:00", "signatures": [{"name": "Ann Sponsor", "at": "2026-10-02T09:00:00+00:00"}]}


@pytest.fixture
def login(tmp_path_factory, tmp_path):
    root = tmp_path_factory.mktemp("reg_seeded") / "data"
    spec = importlib.util.spec_from_file_location("reg_tool_seed", ROOT / "tools" / "seed.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    result = mod.seed(root)
    pw = {l.split()[0]: l.split()[1] for l in result["path"].read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}
    shutil.copytree(root, tmp_path / "data")
    plane = PlaneStore(tmp_path / "data").plane_for(FAMILY)

    def put(*parts, doc):
        p = plane.path(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc), encoding="utf-8")
    put("graph", "company.json", doc=DOC)
    put("intents", "m1_intent", "outcomes", f"{CID}.json", doc={"kind": "charter", **SIGN, "problems": [{"id": "p1"}]})
    put("intents", "m2_baseline", "outcomes", "b1.json", doc={"kind": "baseline", "charter_outcome_id": CID, **SIGN,
                                                              "catalogue": {"kpis": [{"KPI ID": "kpi-1"}, {"KPI ID": "kpi-2"}]}})
    put("build", "pipelines", "custody.json", doc={"source": "custody", "marts": ["gold.kpi-1"]})
    put("graph", "versions.json", doc={"measure:kpi-1": [{"v": 1}, {"v": 2}]})
    settings = load_settings({"SH_MODE": "dev", "SH_DATA_ROOT": str(tmp_path / "data"), "SH_SESSION_SECRET": "FAKE-register-secret-0123456789-abcdefghij"}, env_file=tmp_path / "none.env")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<!doctype html>", encoding="utf-8")
    app = create_app(settings, dist_dir=tmp_path / "dist")

    def go(role: str) -> TestClient:
        email = f"{role}.{FAMILY}@example.test"
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        return c
    return go


def test_rows_come_from_the_signed_charter_and_baseline(login):
    rows = {r["code"]: r for r in login("company_admin").get("/api/company/register").json()["rows"]}
    m = rows["kpi-1"]
    assert (m["kind"], m["owner"], m["pipeline"], m["version"], m["href"]) == ("measure", "Dan Data", "custody", 2, "/centre/intent/map/measure:kpi-1")
    assert m["signed"]["charter"]["by"] == "Ann Sponsor" and m["signed"]["baseline"]["at"] == SIGN["signed_at"] and m["signed"]["release"] is None
    assert rows["kpi-1"]["name"] == "Single-issuer concentration"
    assert m["source"] == {"name": "Too concentrated", "kind": "problem", "href": "/centre/intent/map/problem:p1"}


def test_a_silhouette_row_carries_no_owner_or_pipeline(login):
    body = login("sponsor").get("/api/company/register").json()
    hidden = [r for r in body["rows"] if r["name"] == "A restricted measure"]
    assert len(hidden) == 1 and hidden[0]["owner"] is None and hidden[0]["pipeline"] is None and hidden[0]["code"].startswith("restricted-")
    assert "Secret measure" not in json.dumps(body) and "kpi-2" not in json.dumps(body)


def test_the_payload_holds_no_figures(login):
    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                yield from walk(v)
        elif isinstance(x, list):
            for v in x:
                yield from walk(v)
        else:
            yield x
    rows = login("company_admin").get("/api/company/register").json()["rows"]
    assert all(isinstance(r.pop("version"), int) for r in rows)  # the version count is the only number
    assert not [v for v in walk(rows) if isinstance(v, (int, float)) and not isinstance(v, bool)]


def test_a_definition_stored_as_a_record_takes_its_measure_name():
    from sh_platform.graph.register import _name
    term = n("term:k", "Term", "{'value': 'Known obligations due', 'mark': 'stated'}")
    assert _name(term, {"measure:k": "Known obligations due"}, "k") == "Known obligations due"
    assert _name(n("term:k", "Term", "Concentration"), {"measure:k": "X"}, "k") == "Concentration"


def test_owner_is_the_business_owner_and_the_pipeline_column_lists_every_source(tmp_path, monkeypatch):
    from sh_platform.graph import register as R
    monkeypatch.setattr(R.B, "baselines", lambda p: [{"id": "b1", "state": "signed"}])
    monkeypatch.setattr(R.GS, "_read", lambda p, b: {"K02": {"owners": {"mark": "stated", "value": {"business": "Daniel Kerr", "data": "Harvey Rowley"}}}, "K03": {}})
    plane = PlaneStore(tmp_path / "planes").create(FAMILY)
    p = plane.path("build", "blueprint.json")
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"lineage": [{"measure": "K02", "source": "Custodian daily file"}, {"measure": "K02", "source": "Fund administrator statements"},
                                         {"measure": "K02", "source": "Custodian daily file"}]}), encoding="utf-8")
    assert R._business_owners(plane) == {"k02": "Daniel Kerr"}
    assert R._lineage(plane) == {"k02": "Custodian daily file, Fund administrator statements"}


def test_signed_intent_its_measures_rules_and_plans_are_listed(tmp_path):
    """PF2: a company that signed through Intent (the 10UC demo: one intent, four measures) no longer reads "Nothing has been signed yet"."""
    from sh_platform.graph import register as R
    from sh_platform.profile.view import Viewer
    from sh_platform.v1 import e3_rules, wh
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "planes").create(FAMILY)

    def put(*parts, doc):
        p = plane.path(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc), encoding="utf-8")
    at = "2026-10-03T01:00:00+00:00"
    kpis = [{"code": f"K0{i}", "name": f"Measure {i}"} for i in range(1, 5)]
    put("intents", "i-signed", "sow.json", doc={"state": "signed", "title": "Monthly report", "signature": {"name": "Daniel Foo", "at": at}, "kpis": kpis})
    put("intents", "i-draft", "sow.json", doc={"state": "draft", "title": "Not yet", "signature": None, "kpis": [{"code": "K9", "name": "Draft measure"}]})
    assert R._signed_rules(plane) == [] and not wh.path(plane).exists()  # reading never makes a warehouse
    put("projects", "prj-1.json", doc={"title": "Monthly report"})
    put("build", "prj-1", "plan-v1.json", doc={"state": "approved", "version": 1, "approved_by": "Harvey Rowley", "approved_at": at})
    put("build", "prj-1", "plan-v2.json", doc={"state": "proposed", "version": 2, "approved_by": None})
    put("build", "prj-2", "plan-v1.json", doc={"state": "rejected", "version": 1, "approved_by": None})
    mei, raj = Viewer("Mei Tan", frozenset({"analyst"}), False, "acc-mei"), Viewer("Raj Iyer", frozenset({"analyst"}), False, "acc-raj")
    v = e3_rules.propose(plane, mei, "cash_tolerance", "Cash may differ by 5,000 USD.", {"abs_amount": 5000, "currency": "USD"}, "2026-01-01", "tolerance")
    e3_rules.approve(plane, raj, v["rule_version_id"])
    e3_rules.propose(plane, mei, "limit_x", "A draft rule.", {}, "2026-01-01", "limit")

    got = R.register(plane, Viewer("Ann Admin", frozenset({"company_admin"}), False, "acc-ann"))["records"]
    by_kind = {k: [r for r in got if r["kind"] == k] for k in ("intent", "measure", "rule", "plan")}
    assert [(r["name"], r["by"], r["at"], r["href"]) for r in by_kind["intent"]] == [("Monthly report", "Daniel Foo", at, "/centre/intent/i-signed")]
    assert [r["name"] for r in by_kind["measure"]] == ["Measure 1", "Measure 2", "Measure 3", "Measure 4"]
    assert all(r["of"] == "Monthly report" and r["by"] == "Daniel Foo" for r in by_kind["measure"])
    assert [(r["name"], r["by"]) for r in by_kind["rule"]] == [("cash_tolerance, version 1", "Raj Iyer")]
    assert [(r["name"], r["by"], r["href"]) for r in by_kind["plan"]] == [("Build plan for Monthly report, version 1", "Harvey Rowley", "/centre/build/p/prj-1")]
    assert "Draft measure" not in json.dumps(got) and "Not yet" not in json.dumps(got)

    # ROLE1: the Activity trail also lists the run log; the data team sees everyone's, anyone else only their own
    from sh_platform.v1 import run_log
    run_log.record(plane, "pipeline", "test", "manual", "Leo Park", [], "ok")
    runs = [r for r in R.register(plane, Viewer("Ann Admin", frozenset({"company_admin"}), False, "acc-ann"))["records"] if r["kind"] == "run"]
    assert [(r["by"], r["name"]) for r in runs] == [("Leo Park", "Pipeline run, ok")]
    sponsor = lambda name: R.register(plane, Viewer(name, frozenset({"sponsor"}), False, "acc-s"))["records"]  # noqa: E731
    assert [r["name"] for r in sponsor("Daniel Foo")] == ["Monthly report", "Measure 1", "Measure 2", "Measure 3", "Measure 4"]
    assert sponsor("Mei Chen") == []
    # RSEC: a viewer whose name another account shares sees none of the name-only rows; names match case-insensitively
    assert R.register(plane, Viewer("Daniel Foo", frozenset({"sponsor"}), True, "acc-s"))["records"] == []
    assert [r["name"] for r in sponsor("daniel  foo")][:1] == ["Monthly report"]
