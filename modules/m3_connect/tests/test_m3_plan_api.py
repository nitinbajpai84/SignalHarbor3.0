"""M3-P04 through the real app: the plan drafted on first view, accepting risks, signing in order, the outcome for module 4, read-only after signing
(also for another package's route), restricted items hidden, Nira's sentence. P01's sources.json and P03's findings.json are fixtures."""
import json

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from m3_kit import BASE, copy_baseline, person, restrict, signed_baseline
from modules.m3_connect.api.signed_guard import GuardedRouter, SignedGuard, refuse_when_signed
from modules.m3_connect.domain import accept as X
from modules.m3_connect.domain import steps as S

SOURCES = {"sources": [
    {"id": "S1", "name": "Custodian portal", "kind": "system", "effort": "small", "impact": {"score": 0.6, "reasons": []}, "marks": [],
     "owners": [{"name": "Dana Reyes", "role": "data owner", "team": "Investment Operations"}]},
    {"id": "S2", "name": "Exposure workbook", "kind": "spreadsheet", "effort": "large", "impact": {"score": 0.4, "reasons": []}, "marks": ["no_sample"],
     "owners": [{"name": "Omar Lee", "role": "data owner", "team": "Custody Operations"}]}]}
FINDINGS = {"findings": [
    {"measure_id": "K1", "group": "ready", "reasons": ["The figure matches the pack."], "pain_points": ["p1"], "levers": [], "sources": ["S1"]},
    {"measure_id": "K2", "group": "unclear", "reasons": ["The data stops on 22 Sep."], "pain_points": ["p1"], "levers": [], "sources": ["S2"]},
    {"measure_id": "K3", "group": "unknown", "reasons": ["No source is known."], "pain_points": [], "levers": [], "sources": []}],
    "risks": [{"id": "R1", "kind": "ambiguity", "text": "Is the period end 30 Sep?", "measures": ["K2"], "pain_points": ["p1"], "decision": None},
              {"id": "R2", "kind": "unknown", "text": "Measure three has no source.", "measures": ["K3"], "pain_points": [], "decision": None},
              {"id": "R3", "kind": "risk", "text": "Late packs may repeat.", "measures": ["K1"], "pain_points": ["p1"], "decision": None}]}


class Stub:
    def __init__(self, reply="I1 = Ready to build in days."):
        self.reply, self.sent = reply, []

    def complete(self, module_id, messages, tools=None):
        from sh_platform.egress.model import ModelReply
        self.sent.append(messages)
        return ModelReply(self.reply)


@pytest.fixture(autouse=True)
def registry():
    S._registry.clear()
    S.register("plan", X.step_state)
    yield
    S._registry.clear()


def start(world, company="m3-a", findings=FINDINGS, view=True):
    c = person(world, company, "Lens Lee")
    a = c.post(f"{BASE}/assessments").json()["assessment"]
    d = world.plane(company).path("intents", "m3_connect", "assessments", a["id"])
    if findings is not None:
        (d / "findings.json").write_text(json.dumps(findings))
        (d / "sources.json").write_text(json.dumps(SOURCES))
        if view:
            assert c.get(f"{BASE}/assessments/{a['id']}/plan").status_code == 200  # opening the screen drafts the plan
    return c, a["id"], d


def team(world, company="m3-a"):
    return person(world, company, "Sam Sponsor", ("sponsor",)), person(world, company, "Hana Head", ("company_admin",))


def url(aid, tail):
    return f"{BASE}/assessments/{aid}{tail}"


def names(band):
    return [m["name"] for i in band for m in i["measures"]]


@pytest.fixture
def ready(world):
    signed_baseline(world)
    return start(world)


@pytest.mark.parametrize("company", ["m3-a", "m3-b"])
def test_the_plan_is_drafted_automatically_on_first_view_for_two_industries(world, company):
    signed_baseline(world, "m3-a")
    if company == "m3-b":
        copy_baseline(world, "m3-a", "m3-b")
    c, aid, d = start(world, company)
    got = c.get(url(aid, "/plan")).json()
    assert got["drafted"] and got["waiting"] is None and (d / "plan.json").exists()
    assert [b["label"] for b in got["bands_info"].values()] == ["Now", "Next", "Later"]
    assert names(got["bands"]["now"]) != [] and len(got["bands"]["now"]) == 1 and len(got["bands"]["next"]) == 1 and len(got["bands"]["later"]) == 1
    now = got["bands"]["now"][0]
    assert now["effort_label"] == "Days" and now["team"] == ["Investment Operations"] and now["pain_points"] == [{"id": "p1", "title": "Late packs"}]
    nxt, later = got["bands"]["next"][0], got["bands"]["later"][0]
    assert nxt["blocked_by"][:2] == ["No sample data has arrived yet", "Is the period end 30 Sep?"] and nxt["who_unblocks"] == ["Omar Lee (data owner)"]
    assert nxt["date_text"] is None and nxt["date"] is None and later["covered_text"] == "not planned yet" and later["why_descoped"]
    assert now["summary"] and "sources" not in now and "reasons" not in now and "auto" not in now  # nothing technical is sent to the screen


def test_no_findings_yet_says_what_it_waits_for_and_writes_nothing(world):
    signed_baseline(world)
    c, aid, d = start(world, findings=None)
    got = c.get(url(aid, "/plan")).json()
    assert got["drafted"] is False and "findings" in got["waiting"] and not (d / "plan.json").exists()
    assert c.post(url(aid, "/plan/draft")).status_code == 409
    assert c.get(url(aid, "/risks")).json()["risks"] == []


def test_lens_words_the_summaries_with_a_stubbed_model_and_sends_no_restricted_measure(world):
    signed_baseline(world)
    restrict(world, "m3-a", "K2", ["Test Reader Rae"])
    stub = Stub("I1 = Custodian reporting is ready to build in a few days.")
    world.app.state.lens_model_factory = lambda plane: stub
    c, aid, _ = start(world)
    got = person(world, "m3-a", "Reader Rae").get(url(aid, "/plan")).json()
    assert got["bands"]["now"][0]["summary"] == "Custodian reporting is ready to build in a few days."
    sent = json.dumps(stub.sent)
    assert "Exposure concentration" not in sent and "K2" not in sent and "Custody Operations" not in sent and "Omar" not in sent


def test_a_failing_model_still_gives_a_plan(world):
    signed_baseline(world)

    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("down")
    world.app.state.lens_model_factory = lambda plane: Boom()
    c, aid, _ = start(world)
    got = c.get(url(aid, "/plan")).json()
    assert got["bands"]["now"][0]["summary"].endswith("ready to build. Effort: days.")


def test_risks_are_listed_accepted_and_sent_back_with_name_and_time(world, ready):
    c, aid, d = ready
    before = (d / "findings.json").read_bytes()
    risks = c.get(url(aid, "/risks")).json()
    assert [r["id"] for r in risks["risks"]] == ["R1", "R2", "R3"] and risks["counts"]["open"] == 3
    r1 = next(r for r in risks["risks"] if r["id"] == "R1")
    assert r1["measures"] == [{"id": "K2", "name": "Exposure concentration"}] and r1["pain_points"][0]["title"] == "Late packs"
    bad = c.post(url(aid, "/risks/R3/decision"), json={"decision": "sent_back", "reason": " "})
    assert bad.status_code == 422 and "why" in bad.json()["message"]
    ok = c.post(url(aid, "/risks/R1/decision"), json={"decision": "accepted", "note": "We know"}).json()
    got = next(r for r in ok["risks"] if r["id"] == "R1")
    assert got["state"] == "accepted" and got["decision"]["by"] == "Test Lens Lee" and got["decision"]["note"] == "We know" and got["decision"]["at"]
    back = c.post(url(aid, "/risks/R3/decision"), json={"decision": "sent_back", "reason": "Count the late packs"}).json()
    assert next(r for r in back["risks"] if r["id"] == "R3")["state"] == "sent_back" and back["counts"] == {"open": 1, "sent_back": 1, "accepted": 1, "rechecked": 0}
    assert c.post(url(aid, "/risks/R1/decision"), json={"decision": "accepted"}).status_code == 409   # already accepted
    assert c.post(url(aid, "/risks/R9/decision"), json={"decision": "accepted"}).status_code == 404
    assert c.post(url(aid, "/risks/R2/decision"), json={"decision": "maybe"}).status_code == 422
    assert (d / "decisions.json").exists() and (d / "findings.json").read_bytes() == before            # P03's file is never written


def test_accept_all_remaining_keeps_one_record_per_risk(world, ready):
    c, aid, d = ready
    c.post(url(aid, "/risks/R3/decision"), json={"decision": "sent_back", "reason": "Count them"})
    got = c.post(url(aid, "/risks/accept-all"), json={"note": "reviewed together"}).json()
    assert got["accepted"] == 2 and got["left_hidden"] == 0 and got["counts"]["open"] == 0 and got["counts"]["sent_back"] == 1
    rec = json.loads((d / "decisions.json").read_text())["risks"]
    assert set(rec) == {"R1", "R2", "R3"} and all(rec[r]["by"] == "Test Lens Lee" and rec[r]["at"] for r in ("R1", "R2")) and rec["R1"] is not rec["R2"]
    assert c.post(url(aid, "/risks/accept-all"), json={}).json()["accepted"] == 0


def test_signing_is_refused_in_plain_words_while_a_risk_is_open(world, ready):
    c, aid, d = ready
    sponsor, _ = team(world)
    r = sponsor.post(url(aid, "/plan/sign"))
    assert r.status_code == 409 and "3 risks still need a decision" in r.json()["message"] and "/" not in r.json()["message"]
    assert sponsor.get(url(aid, "/plan")).json()["can_sign"] is False and not (d.parent.parent / "outcomes").exists()


def test_sign_order_the_outcome_written_once_and_read_only_afterwards(world, ready):
    c, aid, d = ready
    sponsor, head = team(world)
    c.post(url(aid, "/risks/accept-all"), json={})
    for step in ("map", "request", "scan", "trial", "findings"):
        S.register(step, lambda p: {"state": "done"})
    assert c.get(url(aid, "/next")).json()["sentence"] == "The plan is ready to sign. The sponsor signs next."
    assert head.post(url(aid, "/plan/sign")).status_code == 409                              # the head of data cannot go first
    assert c.post(url(aid, "/plan/sign")).status_code == 409                                  # an analyst cannot sign
    first = sponsor.post(url(aid, "/plan/sign")).json()
    assert first["signed_at"] is None and [s["slot"] for s in first["signatures"]] == ["sponsor"] and first["waiting_for"] == ["Head of data"]
    assert c.get(url(aid, "/next")).json()["sentence"] == "Waiting for the head of data to sign."
    assert sponsor.post(url(aid, "/plan/sign")).status_code == 409                            # not twice
    assert c.put(url(aid, "/plan/item"), json={"key": "now:S1", "effort": "large", "reason": "x"}).status_code == 409   # the first signature locks the plan
    assert c.get(url(aid, "/outcome")).status_code == 404
    done = head.post(url(aid, "/plan/sign")).json()
    assert done["signed_at"] and done["outcome_id"] and [s["slot"] for s in done["signatures"]] == ["sponsor", "head_of_data"]
    outs = list((d.parent.parent / "outcomes").glob("*.json"))
    assert [f.stem for f in outs] == [done["outcome_id"]]
    rec = c.get(url(aid, "/outcome")).json()
    assert rec["kind"] == "plan" and rec["findings_summary"]["counts"] == {"ready": 1, "unclear": 1, "unknown": 1} and len(rec["accepted_risks"]) == 3
    assert [s["name"] for s in rec["signatures"]] == ["Test Sam Sponsor", "Test Hana Head"] and rec["assessment_id"] == aid
    assert rec["measure_names"]["K1"] and rec["plan"]["now"][0]["team"] == ["Investment Operations"]
    # read-only: every write on the assessment answers 409 in plain words
    for method, tail, body in (("post", "/risks/R1/decision", {"decision": "sent_back", "reason": "x"}), ("post", "/risks/accept-all", {}),
                               ("put", "/plan/item", {"key": "now:S1", "effort": "large", "reason": "x"}), ("post", "/plan/draft", None),
                               ("post", "/plan/sign", None)):
        r = getattr(c, method)(url(aid, tail), **({"json": body} if body is not None else {}))
        assert r.status_code == 409, tail
        assert r.json()["message"] and "/" not in r.json()["message"] or tail == "/plan/sign"
    assert c.get(url(aid, "/plan")).status_code == 200 and c.get(url(aid, "/risks")).status_code == 200  # reading stays open
    assert len(list((d.parent.parent / "outcomes").glob("*.json"))) == 1 and c.get(url(aid, "/next")).json()["sentence"] == "The plan is signed. Module 4 starts from it."


def test_the_guard_covers_another_packages_route_and_survives_mounting(world, ready):
    c, aid, d = ready
    mini = FastAPI()
    mini.state.settings = world.settings

    @mini.middleware("http")
    async def company(request, call_next):
        request.state.company_id = "m3-a"
        return await call_next(request)
    other = APIRouter()
    other.post("/assessments/{assessment_id}/intake/upload")(lambda assessment_id: {"saved": True})
    other.get("/assessments/{assessment_id}/intake")(lambda assessment_id: {"files": []})
    own = GuardedRouter()
    own.post("/assessments/{assessment_id}/own/save")(lambda assessment_id: {"saved": True})
    top = APIRouter(dependencies=[Depends(refuse_when_signed)])   # as api/__init__.py builds the module's router
    top.include_router(other)
    top.include_router(own)
    mini.include_router(top, prefix="/api")
    t = TestClient(mini)
    assert t.post(f"/api/assessments/{aid}/intake/upload").json() == {"saved": True}
    c.post(url(aid, "/risks/accept-all"), json={})
    sponsor, head = team(world)
    assert sponsor.post(url(aid, "/plan/sign")).status_code == 200
    assert head.post(url(aid, "/plan/sign")).json()["signed_at"]
    r = t.post(f"/api/assessments/{aid}/intake/upload")
    assert r.status_code == 409 and r.json()["detail"]["error"] == "signed" and "signed" in r.json()["detail"]["message"]   # a route that did nothing to get it
    own = t.post(f"/api/assessments/{aid}/own/save")
    assert own.status_code == 409 and own.json()["error"] == "signed" and "no longer be changed" in own.json()["message"]   # the screens' own shape
    assert t.get(f"/api/assessments/{aid}/intake").json() == {"files": []}
    from modules.m3_connect.api import plan as plan_api, router
    assert any(d.dependency is refuse_when_signed for d in router.dependencies)
    assert all(isinstance(rt, SignedGuard) for rt in plan_api.router.routes)


def test_an_edit_needs_a_reason_and_survives_a_redraft(world, ready):
    c, aid, d = ready
    key = c.get(url(aid, "/plan")).json()["bands"]["next"][0]["key"]
    assert c.put(url(aid, "/plan/item"), json={"key": key, "band": "later"}).status_code == 422
    got = c.put(url(aid, "/plan/item"), json={"key": key, "band": "later", "effort": "small", "team": "Vendor Office", "date": "2026-12-01",
                                              "covered_by": "Programme P-7", "reason": "Needs the vendor"}).json()
    assert [i["key"] for i in got["bands"]["later"]].count(key) == 1 and got["bands"]["next"] == []
    moved = next(i for i in got["bands"]["later"] if i["key"] == key)
    assert (moved["effort"], moved["team"], moved["date_text"], moved["covered_text"]) == ("small", ["Vendor Office"], "2026-12-01", "Programme P-7")
    assert moved["edits"]["band"]["by"] == "Test Lens Lee" and moved["edits"]["band"]["reason"] == "Needs the vendor"
    sources = json.loads((d / "sources.json").read_text())
    sources["sources"][1]["effort"] = "medium"
    (d / "sources.json").write_text(json.dumps(sources))
    again = c.post(url(aid, "/plan/draft")).json()
    kept = next(i for i in again["bands"]["later"] if i["key"] == key)
    assert (kept["effort"], kept["team"], kept["date_text"]) == ("small", ["Vendor Office"], "2026-12-01") and kept["proposals"] == {"effort": "medium"}
    assert c.put(url(aid, "/plan/item"), json={"key": "nope", "effort": "small", "reason": "x"}).status_code == 404


def test_a_decision_moves_a_restricted_item_out_of_later_without_losing_an_edit(world):
    signed_baseline(world)
    restrict(world, "m3-a", "K1", ["Test Reader Rae"])
    c, aid, d = start(world)
    rae = person(world, "m3-a", "Reader Rae")
    plan = rae.get(url(aid, "/plan")).json()
    k1 = next(i for b in plan["bands"].values() for i in b if i["measures"] and i["measures"][0]["id"] == "K1")
    assert k1["band"] == "later"                                                              # restricted and its risk is not decided
    rae.post(url(aid, "/risks/R3/decision"), json={"decision": "accepted"})
    after = rae.get(url(aid, "/plan")).json()
    assert next(i for b in after["bands"].values() for i in b if i["measures"] and i["measures"][0]["id"] == "K1")["band"] == "now"


def test_a_restricted_measure_is_hidden_from_someone_not_named(world):
    signed_baseline(world)
    restrict(world, "m3-a", "K2", ["Test Reader Rae"])
    c, aid, d = start(world)
    outsider = person(world, "m3-a", "Other Olly")
    plan, risks = outsider.get(url(aid, "/plan")).json(), outsider.get(url(aid, "/risks")).json()
    text = json.dumps([plan, risks])
    assert "Exposure concentration" not in text and "Custody Operations" not in text and "Omar" not in text and "stops on 22 Sep" not in text
    stub = next(i for b in plan["bands"].values() for i in b if i.get("restricted"))
    assert stub["summary"] == "A restricted measure" and stub["measures"] == [] and stub["team"] == [] and stub["blocked_by"] == []
    r1 = next(r for r in risks["risks"] if r["id"] == "R1")
    assert r1["text"] == "A restricted measure" and r1["restricted"] and r1["measures"] == [] and plan["restricted_hidden"] == 1
    refused = outsider.post(url(aid, "/risks/R1/decision"), json={"decision": "accepted"})
    assert refused.status_code == 403 and "restricted" in refused.json()["message"]
    assert outsider.put(url(aid, "/plan/item"), json={"key": stub["key"], "effort": "small", "reason": "x"}).status_code == 403
    left = outsider.post(url(aid, "/risks/accept-all"), json={}).json()
    assert left["accepted"] == 2 and left["left_hidden"] == 1 and left["counts"]["open"] == 1
    named = person(world, "m3-a", "Reader Rae")
    seen = json.dumps([named.get(url(aid, "/plan")).json(), named.get(url(aid, "/risks")).json()])
    assert "Exposure concentration" in seen and named.post(url(aid, "/risks/R1/decision"), json={"decision": "accepted"}).status_code == 200
    head = person(world, "m3-a", "Hana Head", ("company_admin",))
    assert "Exposure concentration" not in json.dumps(head.get(url(aid, "/plan")).json())  # A-069: the admin is outside the named list


def test_the_sponsor_signs_for_what_they_see_and_the_outcome_keeps_the_measure_restricted(world):
    signed_baseline(world)
    restrict(world, "m3-a", "K2", ["Test Reader Rae"])
    c, aid, d = start(world)
    named = person(world, "m3-a", "Reader Rae")
    named.post(url(aid, "/risks/accept-all"), json={})
    sponsor, head = team(world)
    first = sponsor.post(url(aid, "/plan/sign")).json()
    assert first["signatures"][0]["restricted_covered"] == 1 and "covers 1 restricted measure" in first["signatures"][0]["note"]
    done = head.post(url(aid, "/plan/sign")).json()                                           # A-069: named, so the head of data is outside the list and cannot sign for what they cannot see
    rec = json.dumps(c.get(url(aid, "/outcome")).json())
    assert done["error"] == "not_visible" and "signed_at" not in done and "Exposure concentration" not in rec and "stops on 22 Sep" not in rec and "Is the period end" not in rec


def test_one_person_alone_cannot_sign_twice(world):
    signed_baseline(world, "m3-a")
    copy_baseline(world, "m3-a", "m3-solo", with_charter=False)
    c, aid, d = start(world, "m3-solo")
    solo = person(world, "m3-solo", "Solo Sam", ("sponsor", "company_admin"))
    solo.post(url(aid, "/risks/accept-all"), json={})
    assert solo.post(url(aid, "/plan/sign")).status_code == 200
    again = solo.post(url(aid, "/plan/sign"))
    assert again.status_code == 409 and "someone else" in again.json()["message"]


def test_nira_says_the_first_thing_waiting_and_on_whom(world, ready):
    c, aid, d = ready
    S.register("map", lambda p: {"state": "done"})
    S.register("request", lambda p: {"state": "in_progress", "waiting_on": "Waiting on the custody file from Operations."})
    assert c.get(url(aid, "/next")).json() == {"step": "request", "done": False, "sentence": "Waiting on the custody file from Operations."}
    for step in ("request", "scan", "trial", "findings"):
        S.register(step, lambda p: {"state": "done"})
    assert c.get(url(aid, "/next")).json() == {"step": "plan", "done": False, "sentence": "3 risks need a decision from the sponsor."}
    c.post(url(aid, "/risks/R1/decision"), json={"decision": "accepted"})
    c.post(url(aid, "/risks/R2/decision"), json={"decision": "accepted"})
    assert c.get(url(aid, "/next")).json()["sentence"] == "1 risk needs a decision from the sponsor."
    c.post(url(aid, "/risks/R3/decision"), json={"decision": "sent_back", "reason": "Count them"})
    assert c.get(url(aid, "/next")).json()["sentence"] == "Lens is re-checking 1 risk you sent back."
    got = c.get(url(aid, f"")).json()
    assert [s for s in got["steps"] if s["id"] == "plan"][0]["state"] == "in_progress"


def test_before_the_findings_the_plan_step_waits_and_nira_names_it(world):
    signed_baseline(world)
    c, aid, _ = start(world, findings=None)
    got = c.get(url(aid, "/next")).json()
    assert got["step"] == "map" and got["sentence"]


def test_access_company_role_and_module_switch(world):
    signed_baseline(world, "m3-a")
    copy_baseline(world, "m3-a", "m3-b")
    c, aid, _ = start(world)
    other = person(world, "m3-b", "Lens Bo")
    for method, tail in (("get", "/plan"), ("get", "/risks"), ("get", "/next"), ("get", "/outcome"), ("post", "/plan/draft"), ("post", "/risks/accept-all")):
        assert getattr(other, method)(url(aid, tail)).status_code == 404, tail            # another company's assessment is unreachable
    guest = person(world, "m3-a", "Guest Gus", ("participant",))
    for method, tail in (("get", "/plan"), ("post", "/plan/sign"), ("post", "/risks/accept-all"), ("put", "/plan/item")):
        assert getattr(guest, method)(url(aid, tail)).status_code == 403, tail
    off = person(world, "m3-off", "Off Olga")
    assert off.get(url(aid, "/plan")).status_code in (403, 404)
    assert c.get(f"{BASE}/assessments/{'0' * 32}/plan").status_code == 404


def test_a_get_never_drafts_into_a_signed_assessment_and_a_bad_edit_is_a_400(world, ready):
    c, aid, d = ready
    r = c.put(url(aid, "/plan/item"), json={"key": "now:S1", "band": [], "reason": "x"})
    assert r.status_code == 400 and r.json()["message"] and "/" not in r.json()["message"]
    (d / "plan.json").unlink()
    base = json.loads((d / "assessment.json").read_text())
    (d / "assessment.json").write_text(json.dumps({**base, "state": "signed"}))
    got = c.get(url(aid, "/plan")).json()
    assert got["drafted"] is False and not (d / "plan.json").exists()
