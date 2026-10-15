"""B35: the data knowledge map. Node kinds and edges from fixture records, versions at each update moment, scan results, restricted never shown,
the source owner's two answers. Synthetic records on a temporary plane."""
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from sh_platform.graph import knowledge_map as km
from sh_platform.graph.build import rebuild
from sh_platform.graph.versions import plain_versions
from sh_platform.intents import knowledge_map as api
from sh_platform.plane import PlaneStore
from sh_platform.profile import record
from sh_platform.profile.view import Viewer

LENS = {"mark": "stated", "by": "Lens", "agent": "lens", "from": "People list"}
OID, BID, CID, AID = "a" * 32, "b" * 32, "c" * 32, "d" * 32


def cell(v):
    return {"value": v, "mark": "stated", "by": "Mei Tan", "at": "2026-10-01", "from": "Interview"}


def put(plane, parts, data):
    p = plane.path(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def col(name, field_id=None, conf="high"):
    return {"name": name, "type": "string", **({"field_id": field_id, "match": {"confidence": conf}} if field_id else {})}


def seed(plane, shut=None):
    """Systems and people in the profile; a signed charter and baseline with two sources (S1 with three fields, S2 with one); an assessment where
    S1's file has `Mkt Value` and `Val Date` but not `Acct`, and S2's file carries a column called `Acct`."""
    for who in ("Mei Tan", "Dan Data"):
        record(plane, f"people.{who.split()[0].lower()}.name", who, LENS)
    record(plane, "systems.custody.name", "Custody feed", LENS)
    record(plane, "systems.loose.name", "Loose file", LENS)
    put(plane, ("intents", "m1_intent", "outcomes", f"{CID}.json"), {"kind": "charter", "outcome_id": CID, "signed_at": "2026-09-01",
        "signatures": [{"name": "Sue Sponsor", "at": "2026-09-01"}], "problems": [{"id": "p1", "title": "Concentration is reported late"}]})
    put(plane, ("intents", "m2_baseline", BID, "kpis.json"), [{"id": "M1", "problem_ids": ["p1"], "governance": {"personal": "no"}}])
    first = {"Source ID": cell("S1"), "Source name": cell("Custody feed"), "Data owner": cell("Dan Data"), "Availability": cell("Not available yet"),
             "Contains personal data?": cell("Yes" if shut else "No"), "Who may see it": cell(shut or "")}
    put(plane, ("intents", "m2_baseline", "outcomes", f"{OID}.json"), {"kind": "baseline", "outcome_id": OID, "baseline_id": BID, "charter_outcome_id": CID,
        "signed_at": "2026-09-20", "signatures": [{"name": "Mei Tan", "at": "2026-09-20", "slot": "organiser"}],
        "catalogue": {"kpis": [{"KPI ID": cell("M1"), "KPI name": cell("Concentration"), "Business owner": cell("Mei Tan"), "Data owner": cell("Dan Data")}],
                      "sources": [first, {"Source ID": cell("S2"), "Source name": cell("Loose file"), "Data owner": cell("Mei Tan"), "Contains personal data?": cell("No")}],
                      "tables": [{"Item ID": cell("T1"), "Source ID": cell("S1"), "Related KPIs": cell("M1")}, {"Item ID": cell("T2"), "Source ID": cell("S2"), "Related KPIs": cell("M1")}],
                      "fields": [{"Field ID": cell(f"F{i}"), "Field name as in the source": cell(n), "Item ID": cell("T1")} for i, n in ((1, "Mkt Value"), (2, "Val Date"), (3, "Acct"))]
                      + [{"Field ID": cell("F4"), "Field name as in the source": cell("Notes"), "Item ID": cell("T2")}]},
        "glossary": [{"kpi_id": "M1", "term": "Concentration"}]})
    put(plane, ("intents", "m3_connect", "assessments", AID, "assessment.json"), {"created_at": "2026-10-02"})
    put(plane, ("intents", "m3_connect", "assessments", AID, "intake", "S1", "profile.json"), {"files": [{"file": "81380322_custody.csv"}],
        "tables": [{"columns": [col("Mkt Value", "F1"), col("Val Date", "F2")]}]})
    put(plane, ("intents", "m3_connect", "assessments", AID, "intake", "S2", "profile.json"), {"tables": [{"columns": [col("Acct")]}]})


@pytest.fixture
def plane(tmp_path):
    pl = PlaneStore(tmp_path).create("acme")
    seed(pl)
    return pl


def types(doc):
    return {n["id"]: n["type"] for n in doc["nodes"]}


def edges(doc, t):
    return {(e["from"], e["to"]): e for e in doc["edges"] if e["type"] == t}


def test_kinds_and_edges_from_records(plane):
    put(plane, ("build", "blueprint.json"), {"version": 2, "state": "signed", "lineage": [{"measure": "M1", "source": "custody_feed", "mart": "gold.m1"}]})
    put(plane, ("build", "pipelines", "custody_feed.json"), {"source": "custody_feed", "title": "Custody feed", "lands_at": "landing", "marts": ["gold.m1"], "owner": "Dan Data"})
    put(plane, ("context", "agent_docs", "lens", "x1.json"), {"doc_id": "x1", "title": "How we read Concentration", "visibility": "shared", "restricted": False})
    put(plane, ("context", "agent_docs", "lens", "x2.json"), {"doc_id": "x2", "title": "Private note on Concentration", "visibility": "private"})
    put(plane, ("intents", "m3_connect", "assessments", AID, "plan.json"), {"signed_at": "2026-10-03", "signatures": [{"name": "Sue", "at": "2026-10-03"}]})
    t = types(rebuild(plane))
    assert {t[k] for k in ("charter:" + CID, "mart:gold-m1", "file:lens-x1", "system:landing-landing")} == {"Charter", "Mart", "File", "System"}
    assert any(v == "GapReport" for v in t.values()) and not any(k.startswith("file:lens-x2") for k in t)  # a private document is never a node
    doc = json.loads(plane.path("graph", "company.json").read_text(encoding="utf-8"))
    assert ("source:S1", "system:custody") in edges(doc, "held_in") and ("field:F1", "system:custody") in edges(doc, "held_in")
    assert ("pipeline:custody-feed", "system:landing-landing") in edges(doc, "lands_at")
    assert ("measure:M1", "mart:gold-m1") in edges(doc, "fed_by") and ("mart:gold-m1", "pipeline:custody-feed") in edges(doc, "built_by")
    assert ("measure:M1", "file:lens-x1") in edges(doc, "defined_in") and ("measure:M1", "blueprint:v2") in edges(doc, "defined_in")
    assert any(e["type"] == "led_to" for e in doc["edges"])
    owner = edges(doc, "owned_by")
    assert owner[("measure:M1", "person:mei-tan")]["owner_kind"] == ["business"] and owner[("source:S1", "person:dan-data")]["owner_kind"] == ["data"]
    assert owner[("field:F1", "person:dan-data")]["owner_kind"] == ["data"]  # a field has its source's owners


def scan_and_rebuild(plane):
    counts = km.scan_assessment(plane, AID, "Katie")
    rebuild(plane)
    return counts


def test_scan_results_and_verified_by_edges(plane):
    rebuild(plane)
    assert scan_and_rebuild(plane) == {"checked": 4, "available": 2, "missing": 1, "found_elsewhere": 1}
    rows = {r["node"]: r for r in km.verify_rows(plane, AID)}
    assert rows["field:F1"]["result"] == "available" and rows["field:F3"]["result"] == "found_elsewhere" and rows["field:F3"]["claimed"] == "missing"
    assert rows["field:F4"]["result"] == "missing" and rows["field:F3"]["found_in"] == "system:loose"
    doc = json.loads(plane.path("graph", "company.json").read_text(encoding="utf-8"))
    v = {e["from"]: e for e in doc["edges"] if e["type"] == "verified_by"}
    assert v["field:F3"]["result"] == "found_elsewhere" and v["field:F3"]["found_in"] == "system:loose" and v["field:F1"]["to"].startswith("gapreport:")
    ov = api.overview(plane, Viewer("Janet", frozenset({"company_admin"})))
    assert ov["checks"]["field:F3"]["found_in"]["label"] == "Loose file" and ov["checks"]["field:F1"]["word"] == "Available"
    km.scan_assessment(plane, AID, "Katie")  # a later scan keeps the older rows
    assert len(km.verify_rows(plane, AID)) == 8


def test_versions_and_updates_at_each_moment(plane):
    rebuild(plane)
    put(plane, ("build", "blueprint.json"), {"version": 1, "state": "signed", "lineage": [{"measure": "M1", "source": "custody_feed", "mart": "gold.m1"}]})
    row = km.record_moment(plane, "blueprint_signed", "blueprint-v1", "Sue Sponsor")
    assert row["added"].get("Mart") == 1 and row["added"].get("Blueprint") == 1 and row["line"].startswith("The map gained")
    assert "from the blueprint signed by Sue" in row["line"]
    versions = json.loads(plane.path("graph", "versions.json").read_text(encoding="utf-8"))
    mine = versions["mart:gold-m1"][0]
    assert mine["ref"] == "blueprint-v1" and mine["by"] == "Sue Sponsor" and "blueprint was signed" in mine["what"]
    assert plain_versions(versions["mart:gold-m1"], [])[0]["v"] == 1
    km.scan_assessment(plane, AID, "Katie")
    second = km.record_moment(plane, "scan_run", AID, "Katie")
    rows = km.read_updates(plane)
    assert [r["moment"] for r in rows] == ["blueprint_signed", "scan_run"] and rows[1]["id"] == second["id"] and second["added"].get("GapReport") is None
    versions = json.loads(plane.path("graph", "versions.json").read_text(encoding="utf-8"))
    assert versions["field:F3"][-1]["ref"] == AID and versions["field:F3"][-1]["what"] == "Checked by the scan: found in Loose file"
    assert second["changed"] >= 4  # each new scan result counts as a change
    km.scan_assessment(plane, AID, "Katie")
    n = len(json.loads(plane.path("graph", "versions.json").read_text(encoding="utf-8"))["field:F3"])
    km.record_moment(plane, "scan_run", AID, "Katie")  # the same result again adds no version line
    assert len(json.loads(plane.path("graph", "versions.json").read_text(encoding="utf-8"))["field:F3"]) == n
    with pytest.raises(ValueError):
        km.record_moment(plane, "someone_clicked", "x", "y")


def test_restricted_never_shown(tmp_path):
    pl = PlaneStore(tmp_path).create("acme")
    seed(pl, shut="Aaron Lyle")
    km.scan_assessment(pl, AID, "Katie")
    rebuild(pl)
    janet, aaron = Viewer("Janet Shaw", frozenset({"company_admin"})), Viewer("Aaron Lyle", frozenset({"participant"}), False, None)
    assert not [k for k in api.overview(pl, janet)["checks"] if k in ("field:F1", "field:F3")]  # S1 is shut: its fields are silhouettes to her
    assert "field:F1" not in api.overview(pl, janet)["owners"]
    assert "field:F1" in api.overview(pl, aaron)["checks"]
    out = api.systems_to_connect(pl, janet)
    assert [s["label"] for s in out["systems"]] == ["Loose file"]  # S1 is shut, so it adds nothing to any open system's counts
    with pytest.raises(HTTPException) as e:
        api.answer(pl, janet, "field:F3", None)
    assert e.value.status_code == 404  # a hidden node answers like an unknown one


def test_source_owner_confirms_or_rejects(plane):
    scan_and_rebuild(plane)
    owner, other = Viewer("Mei Tan", frozenset({"owner"})), Viewer("Dan Data", frozenset({"owner"}))  # S2 and F3's source S1: F3's owner is Dan Data
    assert api.overview(plane, other)["checks"]["field:F3"]["can_decide"] is True and api.overview(plane, owner)["checks"]["field:F3"]["can_decide"] is False
    with pytest.raises(HTTPException) as e:
        api.answer(plane, owner, "field:F3", None)
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        api.answer(plane, other, "field:F3", "  ")
    assert e.value.status_code == 422
    res = api.answer(plane, other, "field:F3", None)
    assert res["confirmed_by"] == "Dan Data" and res["result"] == "found_elsewhere"
    assert api.overview(plane, other)["checks"]["field:F3"]["confirmed_by"] == "Dan Data"
    with pytest.raises(HTTPException) as e:
        api.answer(plane, other, "field:F3", None)
    assert e.value.status_code == 409  # answered once
    km.scan_assessment(plane, AID, "Katie")  # a later scan is a new row, so it can be answered again, and a rejection makes it Missing
    rebuild(plane)
    assert api.answer(plane, other, "field:F3", "It is a different account list")["result"] == "missing"
    assert api.overview(plane, other)["checks"]["field:F3"]["word"] == "Missing"
    versions = json.loads(plane.path("graph", "versions.json").read_text(encoding="utf-8"))["field:F3"]
    assert any("confirmed by Dan Data" in v["what"] for v in versions) and any("Not the same" in v["what"] for v in versions)


def test_lines_for_the_pulse_and_the_super_admin(plane):
    rebuild(plane)
    put(plane, ("build", "blueprint.json"), {"version": 1, "state": "signed", "lineage": [{"measure": "M1", "source": "custody_feed", "mart": "gold.m1"}]})
    km.record_moment(plane, "blueprint_signed", "b1", "Sue Sponsor")
    km.scan_assessment(plane, AID, "Katie")
    km.record_moment(plane, "scan_run", AID, "Katie")
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    mine = api.pulse_lines(plane, Viewer("Dan Data", frozenset({"owner"})), now)
    assert {ln["kind"] for ln in mine} == {"inform", "decision"} and any(ln["href"] == "/centre/intent/map/field:F3" for ln in mine)
    assert [ln["kind"] for ln in api.pulse_lines(plane, Viewer("Mei Tan", frozenset({"owner"})), now)] == ["inform"]
    assert api.pulse_lines(plane, Viewer("Root", frozenset({"super_admin"})), now) == []


def test_systems_to_connect_line(plane, tmp_path):
    rebuild(plane)
    out = api.systems_to_connect(plane, Viewer("Janet", frozenset({"company_admin"})))
    assert out["line"].startswith("The charter's measures need data from 2 systems") and {s["label"] for s in out["systems"]} == {"Custody feed", "Loose file"}
    empty = PlaneStore(tmp_path / "x").create("empty")
    assert api.systems_to_connect(empty, Viewer("Janet", frozenset({"company_admin"})))["line"].startswith("The map does not yet say")


def test_a_signed_charter_appends_a_version(plane):
    f = plane.path("intents", "m1_intent", "outcomes", f"{CID}.json")
    text = f.read_text(encoding="utf-8")
    f.unlink()
    rebuild(plane)  # the map before the charter was signed
    f.write_text(text, encoding="utf-8")
    row = km.record_moment(plane, "charter_signed", f"charter:{CID}", "Sue Sponsor")
    assert row["added"].get("Charter") == 1 and row["line"] == "The map gained 1 charter from the charter signed by Sue"
    v = json.loads(plane.path("graph", "versions.json").read_text(encoding="utf-8"))[f"charter:{CID}"]
    assert v == [{**v[0], "v": 1, "what": "Added to the map when the charter was signed", "by": "Sue Sponsor", "ref": f"charter:{CID}"}]


def test_account_id_owner_shows_a_name_never_the_id(plane):
    from sh_platform.graph.build import _people, _person
    from sh_platform.graph.models import Graph
    acct = "02d340aa367a4e7eb600204cdab955d7"
    g = Graph()
    people = _people(g, {"people": {"kenneth-yap": {"name": cell("Kenneth Yap"), "account_id": cell(acct)}}}, SimpleNamespace(cells=lambda p: None))
    pid = _person(g, people, acct, [], "wall", from_key=True)
    assert g.nodes[pid]["label"] == "Kenneth Yap"
    assert _person(g, people, "f" * 32, [], "wall") is None  # an id with no person is no owner


def test_sign_moment_failure_never_raises(plane, monkeypatch):
    monkeypatch.setattr(km, "record_moment", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    km.try_moment(plane, "blueprint_signed", "v1", "Sue")
    monkeypatch.undo()
    assert km.record_moment(plane, "gap_report_signed", AID, "Sue")["moment"] == "gap_report_signed"


def test_lineage_view_keeps_the_focus_line_only(plane):
    doc = rebuild(plane)
    line = km.lineage(doc, "field:F1")
    ids = {n["id"] for n in line["nodes"]}
    assert {"field:F1", "source:S1", "measure:M1"} <= ids and "field:F2" not in ids and line["focus"] == "field:F1"
    assert all(e["from"] in ids and e["to"] in ids for e in line["edges"])
    assert km.lineage(doc, "field:nope") is None


def test_lineage_route(plane, monkeypatch):
    import sh_platform.graph.api as G
    rebuild(plane)
    monkeypatch.setattr(G, "_plane", lambda r: plane)
    monkeypatch.setattr(G, "_viewer", lambda r: Viewer("Janet", frozenset({"company_admin"})))
    req = SimpleNamespace(state=SimpleNamespace(account_id="x"))
    out = G.company_graph(req, view="lineage", focus="field:F1")
    assert out["view"] == "lineage" and "field:F2" not in {n["id"] for n in out["nodes"]}
    with pytest.raises(HTTPException):
        G.company_graph(req, view="lineage", focus="field:nope")


def test_same_moment_twice_writes_one_row(plane):
    rebuild(plane)
    km.record_moment(plane, "charter_signed", "ini-x", "Daniel Kerr")
    assert km.record_moment(plane, "charter_signed", "ini-x", "Daniel Kerr") == {}
    assert [r["ref"] for r in km.read_updates(plane)] == ["ini-x"]


def test_module_three_upload_runs_the_scan(plane):
    from modules.m3_connect.api import intake as m3
    assert m3._take._km_hooked
    rebuild(plane)
    km.scan_and_record(plane, AID, "Katie")
    assert km.read_updates(plane)[-1]["moment"] == "scan_run" and len(km.verify_rows(plane, AID)) == 4


def test_a_deleted_intent_leaves_the_map(plane):
    import shutil
    from sh_platform.intents import lifecycle as L
    from sh_platform.intents import store as S
    rec = L.new_record("brainstorm", "acme", L.person("a-org", "Mei Tan"), "2026-10-01T00:00:00Z", title="FX5 gone", purpose="Test")
    rec.update(state="open", time_box={"starts": "", "ends": "2026-10-10T10:00:00Z", "extended_by": []})
    S.create_intent(plane, rec)
    assert f"intent:{rec['id']}" in types(rebuild(plane))
    shutil.rmtree(plane.path("intents", rec["id"]))
    S.rebuild_index(plane)
    assert f"intent:{rec['id']}" not in types(rebuild(plane))
