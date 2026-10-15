"""The company graph projection: nodes and edges with provenance, an empty company, two industries, anonymous cards, stale removal, the hook.
Synthetic records written where the modules write them (the kernel reads by path)."""
import json

import pytest

from sh_platform.graph.build import rebuild
from sh_platform.graph.hooks import mark_dirty, rebuild_if_dirty
from sh_platform.plane import PlaneStore
from sh_platform.profile import record, record_card

LENS = {"mark": "stated", "by": "Lens", "agent": "lens", "from": "People list"}
OID, BID, CID, AID = "a" * 32, "b" * 32, "c" * 32, "d" * 32


def cell(v, by="Mei Tan"):
    return {"value": v, "mark": "stated", "by": by, "at": "2026-10-01", "from": "Interview"}


def put(plane, parts, data):
    p = plane.path(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def seed(plane, measure="Single-issuer concentration", source="Custody feed", restricted=None):
    """Profile people and a card, a signed charter and baseline, and a module 3 assessment."""
    record(plane, "people.mei.name", "Mei Tan", LENS)
    record(plane, "people.mei.team", "Finance", LENS)
    record(plane, "people.dan.name", "Dan Data", LENS)
    record(plane, "systems.custody.name", source, LENS)
    for q, v in (("lane", "tracking"), ("q1", "Exposure file arrives late"), ("sealed", False), ("anonymous", False)):
        record(plane, f"cards.k1.{q}", v, LENS)
    record(plane, "cards.k1.author", "mei", LENS)
    for cid, lane, text in (("k2", "missing", "Manual rework"), ("k3", "levers", "Daily feed"), ("k4", "watch", "Rate move")):  # pains, levers and signals are cards
        record_card(plane, {"id": cid, "lane": lane, "sealed": False, "anonymous": False, "author": "dan", "q1": text}, by="Dan Data")
    put(plane, ("intents", "m1_intent", "outcomes", f"{CID}.json"),  # the real charter shape (contracts/outcome.yaml)
        {"kind": "charter", "outcome_id": CID, "signed_at": "2026-09-01", "signatures": [{"name": "Sue Sponsor", "at": "2026-09-01", "how": "room"}],
         "problems": [{"id": "p1", "title": "Concentration is reported late", "priority": "high"}], "later": [{"id": "p2", "title": "Later one"}]})
    gov = {"personal": "no"} if not restricted else {"personal": "yes", "may_see": restricted}
    put(plane, ("intents", "m2_baseline", BID, "kpis.json"), [{"id": "M1", "problem_ids": ["p1"], "governance": gov}])
    put(plane, ("intents", "m2_baseline", "outcomes", f"{OID}.json"),
        {"kind": "baseline", "outcome_id": OID, "baseline_id": BID, "charter_outcome_id": CID, "signed_at": "2026-09-20",
         "signatures": [{"name": "Mei Tan", "at": "2026-09-20", "slot": "organiser"}],
         "catalogue": {"kpis": [{"KPI ID": cell("M1"), "KPI name": cell(measure), "Business owner": cell("Mei Tan"), "Data owner": cell("Dan Data")}],
                       "sources": [{"Source ID": cell("S1"), "Source name": cell(source), "Data owner": cell("Dan Data"), "Contains personal data?": cell("No")},
                                   {"Source ID": cell("S2"), "Source name": cell("Loose file"), "Contains personal data?": cell("No")}],
                       "tables": [{"Item ID": cell("T1"), "Source ID": cell("S1"), "Related KPIs": cell("M1")}],
                       "fields": [{"Field ID": cell("F1"), "Field name as in the source": cell("Mkt Value"), "Item ID": cell("T1")}]},
         "glossary": [{"kpi_id": "M1", "term": "Concentration"}],
         "process_map": {"M1": {"lanes": ["Finance"], "steps": [{"id": "st1", "text": "Collect the file", "state": "open"}]}},
         "ambiguities": [{"id": "a1", "kpi_id": "M1", "status": "accepted", "by": "Mei Tan", "at": "2026-09-10", "text": "Before or after fees"}]})
    put(plane, ("intents", "m3_connect", "assessments", AID, "assessment.json"), {"created_at": "2026-10-02"})
    put(plane, ("intents", "m3_connect", "assessments", AID, "rules.json"), {"M1": {"rule": {"op": "ratio"}, "checked_by": "Mei Tan"}})
    put(plane, ("intents", "m3_connect", "assessments", AID, "findings.json"), {"risks": [{"id": "r1", "text": "File may be late", "measures": ["M1"]}]})
    put(plane, ("intents", "m3_connect", "assessments", AID, "plan.json"),
        {"items": [{"key": "g1", "band": "now", "sources": ["S1"]}], "signatures": [{"name": "Sue Sponsor", "at": "2026-10-03"}], "signed_at": "2026-10-03"})


@pytest.fixture
def plane(tmp_path):
    (tmp_path / "planes").mkdir()
    return PlaneStore(tmp_path / "planes").create("lakeside-family-office")


def by_type(g, t):
    return {n["id"] for n in g["nodes"] if n["type"] == t}


def _plan_id(g):
    return next(iter(by_type(g, "PlanItem")))


def edges(g, t):
    return {(e["from"], e["to"]) for e in g["edges"] if e["type"] == t}


def test_an_empty_company_is_an_empty_graph_not_an_error(plane):
    g = rebuild(plane)
    assert g["nodes"] == [] and g["edges"] == [] and g["version"] == 1 and g["built_at"]
    assert json.loads(plane.path("graph", "company.json").read_text(encoding="utf-8"))["nodes"] == []


def test_every_node_type_and_edge_type_is_projected_with_provenance(plane):
    seed(plane)
    g = rebuild(plane)
    for t in ("Problem", "Pain", "Signal", "Lever", "Measure", "Term", "Process", "Step", "System", "Source", "Field", "Person", "Team", "Rule", "Risk", "Decision", "PlanItem"):
        assert by_type(g, t), t
    assert {e["type"] for e in g["edges"]} == {"raised_by", "measured_by", "defined_as", "fed_by", "uses", "produced_by", "step_of", "owned_by", "governed_by",
                                                "at_risk", "decided_by", "planned_in", "member_of",
                                                "held_in", "produces", "defined_in", "led_to", "came_from"}  # spec 55's map edges; no record links a lever or signal to a measure: no moves/watches yet
    assert all(n["provenance"] and {"mark", "by", "from"} <= set(n["provenance"][0]) for n in g["nodes"])
    assert all(e["provenance"] for e in g["edges"])
    assert ("measure:M1", "source:S1") in edges(g, "fed_by") and ("source:S1", _plan_id(g)) in edges(g, "planned_in")
    assert ("card:k1", "person:mei-tan") in edges(g, "raised_by") or ("card:k1", "person:mei") in edges(g, "raised_by")
    assert ("problem:p1", "measure:M1") in edges(g, "measured_by")
    assert next(n for n in g["nodes"] if n["id"] == "measure:M1")["room"] == "define"


def test_two_industries_do_not_share_nodes(plane, tmp_path):
    other = PlaneStore(tmp_path / "planes").create("harbor-mutual")
    seed(plane)
    seed(other, measure="Claims ratio", source="Claims system")
    a, b = rebuild(plane), rebuild(other)
    assert "Claims ratio" not in json.dumps(a) and "Single-issuer" not in json.dumps(b)
    assert by_type(a, "Measure") == by_type(b, "Measure") == {"measure:M1"}


def test_an_anonymous_card_has_a_problem_node_and_no_person_edge_or_author(plane):
    record(plane, "people.ada.name", "Ada Guest", LENS)
    record_card(plane, {"id": "n9", "lane": "tracking", "sealed": False, "anonymous": True, "anon_key": "anon-n9", "q1": "Nobody owns the exposure file"},
                by="Ada Guest", source="A note")
    g = rebuild(plane)
    assert "card:n9" in by_type(g, "Problem")
    assert not [e for e in g["edges"] if e["from"] == "card:n9"]
    assert "Ada" not in json.dumps([n for n in g["nodes"] if n["id"] == "card:n9"]) and "anon-n9" not in json.dumps(g)


def test_rebuild_removes_stale_nodes_and_edges(plane):
    seed(plane)
    assert "source:S1" in {n["id"] for n in rebuild(plane)["nodes"]}
    plane.path("intents", "m2_baseline", "outcomes", f"{OID}.json").unlink()
    g = rebuild(plane)
    assert not by_type(g, "Source") and not by_type(g, "Measure") and not edges(g, "fed_by")
    assert "card:k1" in by_type(g, "Problem")  # the profile's own card stays


def test_an_unsigned_baseline_is_not_read(plane):
    seed(plane)
    p = plane.path("intents", "m2_baseline", "outcomes", f"{OID}.json")
    d = json.loads(p.read_text(encoding="utf-8"))
    d["signatures"] = []
    p.write_text(json.dumps(d), encoding="utf-8")
    assert not by_type(rebuild(plane), "Measure")


def test_a_record_write_marks_dirty_and_rebuild_if_dirty_rebuilds_once(plane):
    assert rebuild_if_dirty(plane) is True  # no graph yet
    assert rebuild_if_dirty(plane) is False
    record(plane, "people.mei.name", "Mei Tan", LENS)  # the profile store calls mark_dirty
    assert rebuild_if_dirty(plane) is True
    assert "person:mei-tan" in by_type(json.loads(plane.path("graph", "company.json").read_text(encoding="utf-8")), "Person")
    assert rebuild_if_dirty(plane) is False
    mark_dirty(plane)
    assert rebuild_if_dirty(plane) is True


def test_a_measure_named_like_a_restricted_field_rule_is_closed_with_its_process_and_decisions(plane):
    """The reviewer's probe: field rule "Pay" restricted to one person, a measure "Pay"."""
    from sh_platform.graph.read import graph_for
    from sh_platform.profile import Viewer
    seed(plane, measure="Pay")
    for f, v in (("field", "Pay"), ("personal", "yes"), ("sensitive", True), ("may_see", ["Lena Ho"])):
        record(plane, f"governance.field_rules.pay.{f}", v, LENS)
    rebuild(plane)
    tom, lena = Viewer("Tom Ng", frozenset({"analyst"})), Viewer("Lena Ho", frozenset({"analyst"}))
    seen = {n["type"] for n in graph_for(plane, tom)["nodes"] if n.get("restricted")}
    assert {"Measure", "Process", "Step", "Term", "Risk", "Decision", "Rule"} <= seen
    assert "Pay" not in json.dumps(graph_for(plane, tom)) and "M1" not in json.dumps(graph_for(plane, tom))
    assert "Pay" in json.dumps(graph_for(plane, lena))


def test_a_decision_and_a_plan_item_follow_their_risk_and_source_and_ids_say_nothing(plane):
    from sh_platform.graph.read import graph_for
    from sh_platform.profile import Viewer
    seed(plane, restricted=["Lena Ho"])
    put(plane, ("intents", "m3_connect", "assessments", AID, "decisions.json"), {"risks": {"r1": {"decision": "accepted", "by": "Mei Tan", "at": "2026-10-02"}}})
    put(plane, ("intents", "m3_connect", "assessments", AID, "plan.json"),
        {"items": [{"key": "g1-pay", "band": "now", "sources": ["S1"], "restricted": True}], "signatures": [], "signed_at": None})
    g = rebuild(plane)
    assert not any("M1" in n["id"] or "r1" in n["id"] or "g1" in n["id"] for n in g["nodes"] if n["type"] in ("Decision", "PlanItem"))
    out = graph_for(plane, Viewer("Tom Ng", frozenset({"analyst"})))
    assert {"Decision", "PlanItem", "Risk"} <= {n["type"] for n in out["nodes"] if n.get("restricted")}
    assert "g1-pay" not in json.dumps(out)


def test_an_account_bound_name_passes_by_account_not_by_display_name(plane):
    from sh_platform.graph.read import graph_for
    from sh_platform.profile import Viewer
    record(plane, "people.mei.name", "Mei Tan", LENS)
    record(plane, "people.mei.team", "HR", LENS)
    record(plane, "governance.restricted_areas.hr.area", "HR", LENS)
    record(plane, "governance.restricted_areas.hr.may_see", ["Lena Ho"], LENS)
    record(plane, "governance.restricted_areas.hr.may_see_accounts", {"Lena Ho": ["acct-1"]}, LENS)
    rebuild(plane)
    person = lambda v: next(n for n in graph_for(plane, v)["nodes"] if n["type"] == "Person")  # noqa: E731
    assert person(Viewer("Lena Ho", frozenset(), account_id="acct-1"))["label"] == "Mei Tan"
    assert person(Viewer("Lena Ho", frozenset(), account_id="acct-9")).get("restricted") is True
    assert person(Viewer("Lena Ho", frozenset()))["restricted"] is True  # a bound name never matches on the display name
    assert "restricted_bound" not in json.dumps(graph_for(plane, Viewer("Lena Ho", frozenset(), account_id="acct-1")))


def test_drop_drafts_and_every_store_write_mark_the_graph_dirty(plane):
    from sh_platform.profile import store
    rebuild_if_dirty(plane)
    assert rebuild_if_dirty(plane) is False
    store.mutate(plane, lambda doc: store.drop_drafts(doc, "att1"))
    assert rebuild_if_dirty(plane) is True


def test_profile_alone_yields_owned_by_edges_for_systems_and_measures(plane):
    """From profile: system owner and measure owner, all owned_by edges."""
    record(plane, "people.mei.name", "Mei Tan", LENS)
    record(plane, "people.dan.name", "Dan Data", LENS)
    record(plane, "systems.custody.name", "Custody feed", LENS)
    record(plane, "systems.custody.owner", "Mei Tan", LENS)
    record(plane, "reported_figures.concentration.figure", "Single-issuer", LENS)
    record(plane, "reported_figures.concentration.owner", "Dan Data", LENS)
    g = rebuild(plane)
    assert ("system:custody", "person:mei-tan") in edges(g, "owned_by")
    assert ("measure:concentration", "person:dan-data") in edges(g, "owned_by")


def test_profile_member_of_edges_for_people_on_teams(plane):
    """From profile: each person with a team gets a member_of edge to that team."""
    record(plane, "people.mei.name", "Mei Tan", LENS)
    record(plane, "people.mei.team", "Finance", LENS)
    record(plane, "people.dan.name", "Dan Data", LENS)
    record(plane, "people.dan.team", "Finance", LENS)
    g = rebuild(plane)
    assert ("person:mei-tan", "team:finance") in edges(g, "member_of")
    assert ("person:dan-data", "team:finance") in edges(g, "member_of")


def test_owned_by_edges_follow_restriction_rules_like_other_edges(plane):
    """Edges to restricted nodes are filtered per viewer like any other edge."""
    from sh_platform.graph.read import graph_for
    from sh_platform.profile import Viewer
    record(plane, "people.mei.name", "Mei Tan", LENS)
    record(plane, "people.lena.name", "Lena Ho", LENS)
    record(plane, "governance.restricted_areas.finance.area", "Finance", LENS)
    record(plane, "governance.restricted_areas.finance.may_see", ["Lena Ho"], LENS)
    record(plane, "systems.portfolio.name", "Portfolio", LENS)
    record(plane, "systems.portfolio.owner", "Lena Ho", LENS)
    record(plane, "systems.portfolio.area", "Finance", LENS)
    g = rebuild(plane)
    # Full graph has the edge from restricted system to restricted owner
    assert ("system:portfolio", "person:lena-ho") in edges(g, "owned_by")
    # Lena (with access) sees the edge
    graph_lena = graph_for(plane, Viewer("Lena Ho", frozenset({"analyst"})))
    assert ("system:portfolio", "person:lena-ho") in edges(graph_lena, "owned_by")
    # Tom (without access) does not see the edge
    graph_tom = graph_for(plane, Viewer("Tom Ng", frozenset({"analyst"})))
    assert ("system:portfolio", "person:lena-ho") not in edges(graph_tom, "owned_by")


def test_empty_company_is_still_empty(plane):
    """A plane with only profile (no module 2 or 3) still produces an empty graph with no edges."""
    record(plane, "people.mei.name", "Mei Tan", LENS)
    g = rebuild(plane)
    # Only person node, no edges yet (no systems or measures without module 2)
    assert by_type(g, "Person") == {"person:mei-tan"}
    assert g["edges"] == []
