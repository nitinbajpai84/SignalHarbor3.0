"""GET /api/company/graph/node/{id}, append_version and record_versions_from_build. Synthetic data."""
import copy
import json

import pytest

from sh_platform.graph.versions import append_version, record_versions_from_build, steward
from sh_platform.plane import PlaneStore
from tests.graph.test_graph_route import FAMILY, e, login, n  # noqa: F401  (login is the fixture)

SIGNED = "2026-10-01T09:00:00+00:00"
P = [{"mark": "stated", "by": "Will Wall", "at": "2026-09-01", "from": "A card"}]
DOC = {"version": 1, "built_at": SIGNED, "nodes": [
    n("problem:p1", "Problem", "Too much in one issuer", provenance=P), n("measure:k1", "Measure", "Concentration"), n("term:k1", "Term", "Concentration"),
    n("source:s1", "Source", "Custody feed"), n("field:f1", "Field", "Issuer id"), n("person:dan", "Person", "Dan Data"),
    n("pipeline:k1", "Pipeline", "Concentration load", provenance=P, commits=[{"id": "abc", "when": SIGNED, "what": "first load", "by": "Dan Data"}]),
    n("release:k1", "Release", "Release 1", provenance=P), n("measure:k2", "Measure", "Secret", restricted_to=["priya nair"])],
    "edges": [e("problem:p1", "measure:k1", "measured_by"), e("measure:k1", "term:k1", "defined_as"), e("measure:k1", "source:s1", "fed_by"),
              e("source:s1", "field:f1", "uses"), e("measure:k1", "person:dan", "owned_by"), e("measure:k1", "pipeline:k1", "built_by"),
              e("pipeline:k1", "release:k1", "released_by")]}
BASE = {"kind": "baseline", "signed_at": SIGNED, "signatures": [{"name": "Sam Sponsor", "at": SIGNED}],
        "glossary": [{"kpi_id": "k1", "term": "Concentration", "definition": "Largest issuer share"}]}


def seed(login):
    c = login("analyst")
    plane = PlaneStore(c.app.state.settings.data_root).plane_for(FAMILY).ensure()
    plane.path("graph", "company.json").write_text(json.dumps(DOC), encoding="utf-8")
    out = plane.path("intents", "m2_baseline", "outcomes")
    out.mkdir(parents=True, exist_ok=True)
    (out / "b1.json").write_text(json.dumps(BASE), encoding="utf-8")
    return c, plane


def test_trail_for_a_measure(login):
    c, plane = seed(login)
    append_version(plane, "measure:k1", "Name changed", "the record", "A card")
    r = c.get("/api/company/graph/node/measure:k1").json()
    steps = {t["step"]: t for t in r["trail"]}
    assert list(steps) == ["asked", "defined", "supplied", "built", "released"]
    assert steps["defined"]["by"] == "Sam Sponsor" and steps["supplied"]["label"] == "Custody feed" and steps["supplied"]["detail"] == "Fields: Issuer id" and steps["asked"]["by"] == "Will Wall"
    assert r["owner"] == "Dan Data" and r["definition"]["business"] == "Largest issuer share"
    assert r["commits"][0]["id"] == "abc" and r["versions"][0]["v"] == 1 and r["may_see_figure"] is True


def test_versions_appended_on_a_rebuild_diff(login):
    _, plane = seed(login)
    new = copy.deepcopy(DOC)
    new["nodes"][1]["label"] = "Concentration (renamed)"
    new["nodes"][3]["provenance"] = [{"from": "Baseline outcome b1"}]
    new["edges"] = [x for x in new["edges"] if x["type"] != "uses"]
    assert record_versions_from_build(plane, None, new) == 0
    assert record_versions_from_build(plane, DOC, new) == 3
    v = json.loads(plane.path("graph", "versions.json").read_text(encoding="utf-8"))
    assert v["measure:k1"][0]["what"] == "Renamed from Concentration to Concentration (renamed)" and v["measure:k1"][0]["by"] == "Signal Harbor"
    assert v["source:s1"][0]["ref"] == "Baseline outcome b1"
    assert record_versions_from_build(plane, new, new) == 0


def test_old_bare_rows_read_as_sentences_and_fold(login):
    c, plane = seed(login)
    for w in ("Links changed", "Links changed", "Name changed"):
        append_version(plane, "measure:k1", w, "the record", "kpis.json")
    rows = c.get("/api/company/graph/node/measure:k1").json()["versions"]
    assert [r["what"] for r in rows] == ["Linked to Custody feed and Concentration load", "Renamed"]
    assert all(r["by"] == "Signal Harbor" and "the record" not in r["what"] for r in rows)


def test_outsider_gets_the_same_404_for_a_silhouette_and_a_missing_id(login):
    seed(login)
    sponsor = login("sponsor")
    sil = next(x["id"] for x in sponsor.get("/api/company/graph").json()["nodes"] if x.get("restricted"))
    missing = sponsor.get("/api/company/graph/node/nope")
    for bad in (sil, "measure:k2"):  # the opaque id, and the real id of the hidden node
        r = sponsor.get(f"/api/company/graph/node/{bad}")
        assert (r.status_code, r.json()) == (404, missing.json()) and missing.status_code == 404


def test_steward_defaults(login):
    _, plane = seed(login)
    accts = [{"account_id": "a", "display_name": "Ann Admin", "roles": ["company_admin"], "disabled": False}]
    assert steward(plane, accts) == "Ann Admin"
    plane.path("graph", "steward.json").write_text(json.dumps({"name": "Sue Steward", "account_id": "x"}), encoding="utf-8")
    assert steward(plane, accts) == "Sue Steward"
