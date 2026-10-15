"""N6: the seeded company's signed records join up. A mart's node page reads its measure's signed baseline; the map backfills moments for
signed records that predate it, once; the architecture record is built from a signed blueprint when none exists; room 0's eligibility.
Synthetic data only."""
import json

from tests.graph.test_graph_route import FAMILY, e, login, n  # noqa: F401  (login is the fixture)
from tests.graph.test_node_trail_detail import AT, BASE, CHARTER, CID, DOC, SID, _put
from sh_platform.build import architecture
from sh_platform.build.gap_analysis import _eligible
from sh_platform.graph import knowledge_map as km
from sh_platform.plane import PlaneStore

MART = "mart:gold-k1"


def _plane(c):
    return PlaneStore(c.app.state.settings.data_root).plane_for(FAMILY).ensure()


def test_a_mart_reads_its_measures_signed_baseline(login):
    c = login("analyst")
    plane = _plane(c)
    doc = {**DOC, "nodes": [*DOC["nodes"], n(MART, "Mart", "gold.k1.trust_nav")],
           "edges": [*DOC["edges"], e("measure:k1", MART, "fed_by"), e(MART, "pipeline:custodian-daily", "built_by")]}
    _put(plane, ("graph", "company.json"), doc)
    _put(plane, ("graph", "updates.json"), [{"id": "x", "moment": "charter_signed", "ref": CID, "by": "Mei Tan", "at": AT}])  # recorded: no backfill
    _put(plane, ("intents", "m2_baseline", "outcomes", "b1.json"), BASE)
    _put(plane, ("intents", "m1_intent", "outcomes", f"{CID}.json"), CHARTER)
    _put(plane, ("intents", "m1_intent", "sessions", f"{SID}.json"), {"id": SID, "preparation": {"purpose": "Treasury wall"}})
    r = c.get(f"/api/company/graph/node/{MART}").json()
    steps = {t["step"]: t for t in r["trail"]}
    assert list(steps) == ["asked", "defined", "supplied", "built", "released"]
    assert steps["defined"]["label"] == "Baseline, version 1" and steps["supplied"]["label"] == "Custodian system"  # the source, not the mart itself
    assert r["definition"]["business"] == "the total net asset value of the trust at month end"


def test_backfill_writes_one_row_per_signed_record_once(login):
    c = login("analyst")
    plane = _plane(c)
    _put(plane, ("intents", "m2_baseline", "outcomes", "b1.json"), BASE)
    _put(plane, ("intents", "m1_intent", "outcomes", f"{CID}.json"), {**CHARTER, "signatures": [{"name": "Mei Tan", "at": AT}]})
    assert km.backfill(plane) == 1
    rows = km.read_updates(plane)
    assert [(r["moment"], r["ref"], r["at"], r["by"]) for r in rows] == [("charter_signed", CID, AT, "Mei Tan")]
    assert km.backfill(plane) == 0 and len(km.read_updates(plane)) == 1


def test_architecture_is_built_once_from_a_signed_blueprint(login):
    c = login("analyst")
    plane = _plane(c)
    assert architecture.ensure(plane) is False  # no blueprint: nothing invented
    _put(plane, ("build", "blueprint.json"), {"version": 1, "state": "signed", "signed_by": [{"name": "Mei Tan", "at": AT}],
                                              "lineage": [{"mart": "gold.k1.trust_nav", "measure": "k1", "source": "custodian_daily"}],
                                              "infra": {"warehouse": "plane", "runner": "builtin"}})
    _put(plane, ("build", "pipelines", "custodian_daily.json"), {"source": "custodian_daily", "marts": ["gold.k1"], "lands_at": "landing"})
    assert architecture.ensure(plane) is True and architecture.ensure(plane) is False
    rec = architecture.read(plane)
    assert rec["version"] == 1 and {"gold:k1", "source:custodian_daily", "infra:warehouse"} <= {x["id"] for x in rec["components"]}
    r = c.get("/api/company/build/architecture?view=data").json()
    assert r["version"] == 1 and r["diagram"]["connections"]


def test_room0_eligibility():
    assert _eligible({"type": "initiative", "state": "closed", "links": {"build": "build/blueprint.json"}})
    assert _eligible({"type": "initiative", "state": "open", "build_ready": {"state": "ready"}})
    assert not _eligible({"type": "initiative", "state": "open", "build_ready": {"state": "incomplete"}})
    assert not _eligible({"type": "initiative", "state": "closed", "links": {"build": None}})
    assert not _eligible({"type": "problem", "state": "open", "build_handoff": {"at": AT}})
