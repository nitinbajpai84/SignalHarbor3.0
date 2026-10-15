"""The graph per viewer: silhouettes for a restricted node, structural edges kept, counts and holes."""
import json

from sh_platform.graph.build import rebuild
from sh_platform.graph.read import graph_for, summary
from sh_platform.profile import Viewer, record
from test_graph_build import LENS, plane, seed  # noqa: F401  (the plane fixture and the records)

ADMIN = Viewer("Root", frozenset({"company_admin"}))
LENA = Viewer("Lena Ho", frozenset({"analyst"}))
TOM = Viewer("Tom Ng", frozenset({"analyst"}))


def shut(plane):
    seed(plane, restricted=["Lena Ho"])
    rebuild(plane)


def test_an_outsider_sees_a_silhouette_and_a_named_viewer_sees_the_node(plane):
    shut(plane)
    out = graph_for(plane, TOM)
    m = next(n for n in out["nodes"] if n["type"] == "Measure")
    assert m["id"].startswith("restricted-") and {k: v for k, v in m.items() if k != "id"} == {"type": "Measure", "restricted": True, "label": "A restricted measure"}
    assert "Single-issuer" not in json.dumps(out) and "measure:M1" not in json.dumps(out)
    assert next(n for n in graph_for(plane, LENA)["nodes"] if n["type"] == "Measure")["label"] == "Single-issuer concentration"
    # A-069: someone is named, so the company admin no longer passes
    assert next(n for n in graph_for(plane, ADMIN)["nodes"] if n["type"] == "Measure")["label"] == "A restricted measure"


def test_only_structural_edges_survive_a_silhouette_and_they_lose_provenance(plane):
    shut(plane)
    out = graph_for(plane, TOM)
    edges, m_id = out["edges"], next(n["id"] for n in out["nodes"] if n["type"] == "Measure")
    kinds = {e["type"] for e in edges}
    assert {"measured_by", "fed_by"} <= kinds
    assert not kinds & {"defined_as", "at_risk", "governed_by", "moves", "watches"}
    assert all("provenance" not in e and e["restricted"] for e in edges if m_id in (e["from"], e["to"]))
    assert {"owned_by", "at_risk"} <= {e["type"] for e in graph_for(plane, LENA)["edges"]}


def test_a_restricted_area_silhouettes_its_people_and_a_shared_name_does_not_pass(plane):
    record(plane, "people.mei.name", "Mei Tan", LENS)
    record(plane, "people.mei.team", "HR", LENS)
    record(plane, "governance.restricted_areas.hr.area", "HR", LENS)
    record(plane, "governance.restricted_areas.hr.may_see", ["Lena Ho"], LENS)
    rebuild(plane)
    assert [n["label"] for n in graph_for(plane, TOM)["nodes"] if n["type"] == "Person"] == ["A restricted person"]
    assert [n["label"] for n in graph_for(plane, LENA)["nodes"] if n["type"] == "Person"] == ["Mei Tan"]
    assert all(n["restricted"] for n in graph_for(plane, Viewer("Lena Ho", frozenset(), shared_name=True))["nodes"] if n["type"] == "Person")


def test_no_graph_is_an_empty_graph_for_every_viewer(plane):
    assert graph_for(plane, TOM)["nodes"] == [] and summary(plane, TOM)["holes"]["measure_no_source"] == []


def test_summary_counts_and_holes(plane):
    seed(plane)
    rebuild(plane)
    s = summary(plane, ADMIN)
    assert s["counts"]["Measure"] == 1 and s["counts"]["Source"] == 2 and s["nodes"] > 10
    assert [h["id"] for h in s["holes"]["source_no_owner"]] == ["source:S2"]
    assert s["holes"]["measure_no_source"] == []
    assert "card:k1" in [h["id"] for h in s["holes"]["problem_no_measure"]]


def test_a_measure_with_no_source_is_a_hole_and_a_silhouette_still_counts(plane):
    seed(plane, restricted=["Lena Ho"])
    record(plane, "reported_figures.f1.measure", "Fees paid", LENS)
    rebuild(plane)
    assert [h["label"] for h in summary(plane, TOM)["holes"]["measure_no_source"]] == ["Fees paid"]
    assert summary(plane, TOM)["counts"]["Measure"] == 2
