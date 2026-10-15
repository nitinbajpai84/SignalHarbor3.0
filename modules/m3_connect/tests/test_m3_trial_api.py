"""M3-P03 routes: compile, run, trial view, mark a rule checked, findings view; roles, restricted measures, two industries, an empty company."""
import json

import pytest

from m3_kit import BASE, copy_baseline, person, restrict, signed_baseline
from m3_trial_kit import Stub, write
from modules.m3_connect.domain import findings as F
from modules.m3_connect.domain import steps as S
from modules.m3_connect.domain import trial as T

RULE = json.dumps({"op": "sum", "column": "amount"})


def start(world, company="m3-a", name="Lens Lee", roles=("analyst",)):
    c = person(world, company, name, roles)
    r = c.post(f"{BASE}/assessments")
    assert r.status_code in (200, 201), r.text
    aid = r.json()["assessment"]["id"]
    adir = world.plane(company).path("intents", "m3_connect", "assessments", aid)
    write(adir, "intake/s1/rows.json", [{"amount": "10"}, {"amount": "20"}])
    write(adir, "sources.json", [{"id": "s1", "name": "Test source", "measures": ["K1", "K2"]}])
    write(adir, "benchmarks.json", [{"measure_id": "K1", "figure": 30, "unit": "SGD", "period_end": "2026-09-30", "source_note": "pack p1"},
                                    {"measure_id": "K2", "figure": 99, "unit": "SGD", "period_end": "2026-09-30", "source_note": "pack p2"}])
    return c, aid, adir


def url(aid, tail):
    return f"{BASE}/assessments/{aid}/{tail}"


def by_id(view):
    return {m["measure"]: m for m in view["measures"]}


def flow(world, company):
    world.app.state.lens_model_factory = lambda plane: Stub(RULE)
    c, aid, adir = start(world, company)
    assert c.post(url(aid, "trial/compile")).status_code == 200
    v = c.post(url(aid, "trial/run")).json()
    return c, aid, adir, v


@pytest.mark.parametrize("company", ["m3-a", "m3-b"])
def test_compile_run_view_check_and_findings_in_two_industries(world, company):
    signed_baseline(world)
    if company == "m3-b":
        copy_baseline(world, "m3-a", "m3-b")
    c, aid, adir, v = flow(world, company)
    S.register("trial", T.state)  # the scaffold test empties the step registry
    S.register("findings", F.state)
    m = by_id(v)
    assert m["K1"]["result"] == "matches" and m["K1"]["our_figure"] == 30 and m["K1"]["rule"]["words"] == "The sum of amount."
    assert m["K2"]["result"] == "gap" and m["K2"]["difference"] == -69 and m["K2"]["likely_reason"]
    assert m["K3"]["result"] == "cannot" and m["K3"]["their_figure"] is None and "no figure from you" in m["K3"]["missing"]  # never zero
    assert [s for s in S.steps_for(adir) if s["id"] in ("trial", "findings")] == [  # the trial is not done while the analyst has rules to check (D3); K1 matches, so Lens checked it itself (LI-M3)
        {"id": "trial", "label": "Trial", "state": "in_progress", "waiting_on": "Waiting for the data analyst to check 2 rules Lens wrote."},
        {"id": "findings", "label": "Findings", "state": "done", "waiting_on": ""}]
    f = c.get(url(aid, "findings")).json()
    assert {k: x["group"] for k, x in f["measures"].items()} == {"K1": "ready", "K2": "unclear", "K3": "unclear"}
    assert {r["id"] for r in f["risks"]} == {"risk-measure-K2", "risk-measure-K3"}
    r = c.post(url(aid, "trial/rules/K3/check"))
    assert r.status_code == 200 and by_id(r.json())["K3"]["rule"]["checked_by"] == "Test Lens Lee"
    assert c.get(url(aid, "findings")).json()["measures"]["K3"]["group"] == "ready"  # checked, and nothing to compare with
    again = c.post(url(aid, "trial/compile")).json()
    assert by_id(again)["K3"]["rule"]["state"] == "checked"  # a person's check is never overwritten by a new compile
    c.post(url(aid, "trial/rules/K2/check"))
    assert [s["state"] for s in S.steps_for(adir) if s["id"] == "trial"] == ["done"]


def test_roles_sponsor_reads_but_cannot_compile_run_or_check(world):
    signed_baseline(world)
    c, aid, _, _ = flow(world, "m3-a")
    s = person(world, "m3-a", "Sponsor Sue", ("sponsor",))
    assert s.get(url(aid, "trial")).status_code == 200 and s.get(url(aid, "findings")).status_code == 200
    for tail in ("trial/compile", "trial/run", "trial/rules/K1/check"):
        assert s.post(url(aid, tail)).status_code == 403
    admin = person(world, "m3-a", "Head Hugo", ("company_admin",))
    assert admin.post(url(aid, "trial/rules/K1/check")).status_code == 403  # checking a rule is the data analyst's


def test_restricted_measure_is_hidden_from_a_viewer_outside_may_see(world):
    signed_baseline(world)
    restrict(world, "m3-a", "K1", ["Someone Else"])
    c, aid, adir, v = flow(world, "m3-a")
    k1 = by_id(v)["K1"]
    assert k1 == {"measure": "K1", "name": "A restricted measure", "restricted": True}
    assert "K1" not in json.loads((adir / "rules.json").read_text()) and "K1" not in json.loads((adir / "trial.json").read_text())
    assert c.post(url(aid, "trial/rules/K1/check")).status_code == 404
    f = c.get(url(aid, "findings")).json()
    assert f["measures"]["K1"]["name"] == "A restricted measure" and f["measures"]["K1"]["reasons"] == []
    assert all("K1" not in r["measures"] or r["text"] == "A restricted measure has something open." for r in f["risks"])
    admin = person(world, "m3-a", "Head Hugo", ("company_admin",))
    assert admin.post(url(aid, "trial/compile")).status_code == 200
    assert by_id(admin.post(url(aid, "trial/run")).json())["K1"] == k1  # A-069: named, so the head of data is outside the list too
    assert by_id(c.get(url(aid, "trial")).json())["K1"] == k1  # still hidden from the analyst after the admin's run
    assert c.get(url(aid, "findings")).json()["measures"]["K1"]["name"] == "A restricted measure"


def test_no_model_and_no_hint_means_could_not_compile_in_plain_words(world):
    signed_baseline(world)
    world.app.state.lens_model_factory = lambda plane: None
    c, aid, adir = start(world)
    v = c.post(url(aid, "trial/compile")).json()
    k1 = by_id(v)["K1"]
    assert k1["rule"]["state"] == "could_not_compile" and "no model" in k1["rule"]["reason"] and k1["rule"]["words"] is None
    assert by_id(c.post(url(aid, "trial/run")).json())["K1"]["our_figure"] is None
    assert c.post(url(aid, "trial/rules/K1/check")).status_code == 409


def test_empty_company_other_company_and_module_off_are_refused(world):
    signed_baseline(world)
    _, aid, _ = start(world)
    empty = person(world, "m3-empty", "Empty Ed")
    assert empty.get(url(aid, "trial")).status_code == 404 and empty.get(url("a" * 32, "findings")).status_code == 404
    other = person(world, "m3-b", "Lens Bo")
    assert other.get(url(aid, "trial")).status_code == 404  # another company's assessment does not exist here
    off = person(world, "m3-off", "Off Ola")
    assert off.get(url(aid, "trial")).status_code in (403, 404)
