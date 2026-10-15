"""Q3: the node route serves what the Desk-Node artboard shows: a sub-line per trail step, the definition's three lines, how many may see the figure.
Synthetic data."""
import json

from tests.graph.test_graph_route import FAMILY, e, login, n  # noqa: F401  (login is the fixture)
from sh_platform.plane import PlaneStore

AT = "2026-09-22T09:00:00+00:00"
BID, CID, SID = "b" * 32, "c" * 32, "d" * 32
DOC = {"version": 1, "built_at": AT, "nodes": [
    n("problem:p1", "Problem", "Late capital-call notices"), n("measure:k1", "Measure", "Trust NAV"), n("term:k1", "Term", "Trust NAV"),
    n("source:s1", "Source", "Custodian system"), n("field:f1", "Field", "nav_total"), n("field:f2", "Field", "as_of"),
    n("person:dan", "Person", "Dan Data"), n("person:harvey", "Person", "Harvey Rowley"), n("person:mei", "Person", "Mei Tan"),
    n("blueprint:v1", "Blueprint", "Blueprint v1"),
    n("pipeline:custodian-daily", "Pipeline", "custodian_daily", commits=[{"id": f"c{i}", "when": AT, "what": "x", "by": "Builder"} for i in (1, 2, 3)]),
    n("release:band-1-2026-09", "Release", "Release Band 1 2026-09")],
    "edges": [e("problem:p1", "measure:k1", "measured_by"), e("measure:k1", "term:k1", "defined_as"), e("measure:k1", "source:s1", "fed_by"),
              e("source:s1", "field:f1", "uses"), e("source:s1", "field:f2", "uses"), e("measure:k1", "person:dan", "owned_by"),
              e("measure:k1", "blueprint:v1", "designed_in"), e("blueprint:v1", "person:dan", "designed_by"),
              e("measure:k1", "pipeline:custodian-daily", "built_by"), e("measure:k1", "release:band-1-2026-09", "released_in"),
              e("release:band-1-2026-09", "person:harvey", "tested_by"), e("release:band-1-2026-09", "person:mei", "released_by")]}
BASE = {"kind": "baseline", "baseline_id": BID, "charter_outcome_id": CID, "signed_at": AT, "signatures": [{"name": "Mei Tan", "at": AT}],
        "glossary": [{"kpi_id": "k1", "term": {"value": "Trust NAV", "mark": "stated"},
                      "business_definition": {"value": "the total net asset value of the trust at month end", "mark": "stated"}}],
        "technical": {"k1": {"calculation": {"value": "sum of nav_total on the last business day", "mark": "stated"}}},
        "process_map": {"k1": {"steps": [{"id": "s2", "text": "reconciled by Olga on day 3", "order": 2},
                                         {"id": "s1", "text": "custodian export on day 2", "order": 1},
                                         {"id": "s3", "text": "an old step", "order": 3, "state": "removed"}]}}}
CHARTER = {"kind": "charter", "signed_at": AT, "session_id": SID, "problems": [{"id": "p1", "title": "Late capital-call notices", "note_count": 11}]}


def _put(plane, parts: tuple, doc: dict) -> None:
    p = plane.path(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def test_trail_sub_lines_definition_and_who_may_see(login):
    c = login("analyst")
    plane = PlaneStore(c.app.state.settings.data_root).plane_for(FAMILY).ensure()
    _put(plane, ("graph", "company.json"), DOC)
    _put(plane, ("intents", "m2_baseline", "outcomes", "b1.json"), BASE)
    _put(plane, ("intents", "m1_intent", "outcomes", f"{CID}.json"), CHARTER)
    _put(plane, ("intents", "m1_intent", "sessions", f"{SID}.json"), {"id": SID, "preparation": {"purpose": "Treasury wall"}})
    _put(plane, ("intents", "m2_baseline", BID, "governed_state.json"), {"k1": {"may_see": {"value": ["Olga Trustee", "Dan Data", "Mei Tan"], "mark": "stated"}}})
    r = c.get("/api/company/graph/node/measure:k1").json()
    steps = {t["step"]: t for t in r["trail"]}
    assert list(steps) == ["asked", "defined", "supplied", "built", "released"]
    assert (steps["asked"]["label"], steps["asked"]["detail"], steps["asked"]["ref"]) == ("Treasury wall", "Problem: Late capital-call notices · 11 cards", "problem:p1")
    assert steps["defined"]["detail"] == "Signed by Mei Tan · 22 Sep"
    assert (steps["supplied"]["label"], steps["supplied"]["detail"]) == ("Custodian system", "Fields: nav_total, as_of")
    assert (steps["built"]["label"], steps["built"]["detail"]) == ("Pipeline custodian_daily", "Design signed by Dan Data · 3 commits")
    assert (steps["released"]["detail"], steps["released"]["ref"]) == ("UAT: Harvey Rowley · release: Mei Tan", "release:band-1-2026-09")
    assert r["definition"] == {"term": "Trust NAV", "business": "the total net asset value of the trust at month end",
                               "technical": "sum of nav_total on the last business day", "process": "custodian export on day 2 · reconciled by Olga on day 3"}
    assert r["may_see_named"] == 3 and r["baseline_id"] == BID
