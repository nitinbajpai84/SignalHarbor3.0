"""K3 v5 (V5W-6) The company map as one ontology: node types, labelled relations, verified vs in progress, growth, and the review queue."""
import pytest

from sh_platform.v1 import k3_onto as O
from sh_platform.v1 import p1_project as P

from tests.v1.test_k3 import ADMIN, HEAD, OUT, NOBODY, world  # noqa: F401  (the same small family office)


def by_id(o, nid):
    return next((n for n in o["nodes"] if n["id"] == nid), None)


def rels(o):
    return {(e["from"], e["to"], e["rel"]) for e in o["edges"]}


def test_one_graph_with_typed_nodes_and_labelled_relations(world):
    plane, w = world
    o = O.build(plane, ADMIN)
    types = {n["type"] for n in o["nodes"]}
    assert {"person", "agent", "project", "intent", "source", "table", "dashboard"} <= types
    assert {e["rel"] for e in o["edges"]} <= set(O.REL)
    pn = f"project:{w['pid']}"
    r = rels(o)
    assert ("source:administrator", "table:bronze_administrator_export_valuations", "feeds") in r
    assert ("table:gold_monthly_report_valuation_monthly", "dash:d1", "feeds") in r
    assert ("table:gold_monthly_report_valuation_monthly", pn, "built by") in r
    assert (pn, "intent:rep1", "raised from") in r
    assert ("person:Mei Tan", "dash:d1", "owns") not in r  # Mei is the audience, not the owner
    assert by_id(o, "table:gold_monthly_report_valuation_monthly")["layer"] == "gold"
    assert any(n["type"] == "case" for n in o["nodes"]) and ("agent:tally" in {e["to"] for e in o["edges"] if e["rel"] == "raised from"})


def test_state_follows_project_completion_and_the_head_of_datas_admission(world):
    plane, w = world
    gold, pid = "table:gold_monthly_report_valuation_monthly", w["pid"]
    o = O.build(plane, ADMIN)
    assert by_id(o, gold)["state"] == "in_progress" and not by_id(o, gold)["waiting"]  # project not complete: nothing waits yet
    assert by_id(o, "source:administrator")["state"] == "verified"  # baseline belongs to no project
    P.set_stage(plane, pid, "live")
    o = O.build(plane, ADMIN)
    assert by_id(o, gold)["waiting"] and o["waiting"] >= 3
    done = O.approve(plane, ADMIN, [gold])
    o = O.build(plane, ADMIN)
    n = by_id(o, gold)
    assert n["state"] == "verified" and n["verified_by"] == "Ada" and n["verified_at"] == done["at"]
    link = next(e for e in o["edges"] if e["from"] == gold and e["to"] == "dash:d1")
    assert link["state"] == "in_progress"  # the dashboard has not been admitted yet: the link stays dashed
    assert o["can_review"] is True


def test_review_queue_approve_reject_and_who_may(world):
    plane, w = world
    P.set_stage(plane, w["pid"], "live")
    q = O.review(plane, HEAD)
    assert q["allowed"] and not q["can_review"] and q["totals"]["waiting"] >= 3
    proj = q["projects"][0]
    assert proj["title"] == "Monthly investment report" and {i["status"] for i in proj["items"]} == {"waiting"}
    with pytest.raises(O.Refused) as e:
        O.approve(plane, HEAD, [proj["items"][0]["id"]])
    assert e.value.status == 403
    with pytest.raises(O.Refused):
        O.reject(plane, ADMIN, proj["items"][0]["id"], "   ")
    dash = next(i["id"] for i in proj["items"] if i["id"].startswith("dash:"))
    O.reject(plane, ADMIN, dash, "Audience is wrong")
    q = O.review(plane, ADMIN)
    d = next(i for i in q["projects"][0]["items"] if i["id"] == dash)
    assert d["status"] == "sent_back" and d["reason"] == "Audience is wrong" and d["by"] == "Ada"
    with pytest.raises(O.Refused) as e:
        O.approve(plane, ADMIN, ["table:not_there"])
    assert e.value.status == 409
    O.approve(plane, ADMIN, [dash])  # the head may change their mind
    d = next(i for i in O.review(plane, ADMIN)["projects"][0]["items"] if i["id"] == dash)
    assert d["status"] == "approved" and d["decided_at"]


def test_growth_steps_and_access(world):
    plane, w = world
    P.set_stage(plane, w["pid"], "live")
    o = O.build(plane, ADMIN)
    proj = o["projects"][0]
    assert [s["n"] for s in proj["steps"]] == [1, 2, 3, 4] and proj["complete"] and sum(s["added"] for s in proj["steps"]) > 3
    assert by_id(o, "dash:d1")["steps"][w["pid"]] == 4 and by_id(o, f"project:{w['pid']}")["steps"][w["pid"]] == 1
    assert by_id(o, "table:valuation_observations")["steps"][w["pid"]] == 2
    # a person with no team role never sees the data team's layers, nor the review queue, nor health colour
    out = O.build(plane, OUT)
    assert not {"source", "case"} & {n["type"] for n in out["nodes"]} and all(n["health"] is None for n in out["nodes"])
    assert O.review(plane, OUT)["allowed"] is False
    with pytest.raises(O.Refused):
        O.approve(plane, OUT, ["x"])


def test_health_colours_follow_the_source(world):
    plane, _ = world
    o = O.build(plane, ADMIN)
    assert by_id(o, "source:manager_email")["health"] == "attention" and by_id(o, "source:administrator")["health"] in ("ok", "attention")
    assert by_id(o, "table:bronze_manager_email_statement")["health"] == "affected"


def test_every_new_route_is_declared_and_writes_are_the_head_alone():
    from tests.v1.test_k3 import ROOT
    text = (ROOT / "sh_platform" / "v1" / "k3.permissions.yaml").read_text(encoding="utf-8")
    for line in ("GET /api/v1/centre-map/ontology:", "GET /api/v1/centre-map/review:", "POST /api/v1/centre-map/review/approve: {roles: [company_admin]}",
                 "POST /api/v1/centre-map/review/reject: {roles: [company_admin]}"):
        assert line in text


def test_maker_never_checker_the_builder_may_not_review_their_project(world):
    plane, w = world
    P.set_stage(plane, w["pid"], "live")
    P.set_person(plane, w["pid"], "builder", "Ada")
    q = O.review(plane, ADMIN)
    assert q["projects"][0]["mine"] is True
    item = q["projects"][0]["items"][0]["id"]
    for call in (lambda: O.approve(plane, ADMIN, [item]), lambda: O.reject(plane, ADMIN, item, "No")):
        with pytest.raises(O.Refused) as e:
            call()
        assert e.value.status == 403
