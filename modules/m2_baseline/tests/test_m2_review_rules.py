"""Round 3 fixes N-A, N-D, N-E, N-F, N-G: the review reads the tracking status, confirming needs an answer, a signed baseline
is read-only on every write route, the hand-off lists gaps of real kinds only, the review's arrival line keeps every owner's
words. The real app over temporary folders (fixtures: test_m2_signoff_kit.py)."""
import json

import pytest

from m2_kit import BASE
from test_m2_signoff import by_id, get
from test_m2_signoff_kit import BID, Team, answer, confirm_all, kpi, me, seed, sign_both, standard_answers, standard_kpis, stated
from modules.m2_baseline.domain.provenance import prov, unknown

PM = "/process-map"
SIGNED = "This baseline is signed; it can no longer be changed."


def blank_tracking(k):
    return {**k, "tracking": unknown("Lens")}


# ---- N-A: tracking status reaches the review -----------------------------------------------------------------------
def test_the_owners_tracked_today_answer_reaches_the_review(world):
    seed(world, kpis=[blank_tracking(kpi("K1", "Capital calls")), blank_tracking(kpi("K2", "Exposure"))],
         answers=[answer("K1", tracked="tracked_now"), answer("K2", tracked="not_tracked")])
    team = Team(world)
    k = by_id(get(team))
    assert k["K1"]["tracking"]["today"] is True and k["K1"]["tracking"]["label"] == "Tracked today"
    assert not any("Tracking status" in u for u in k["K1"]["unknowns"]) and k["K1"]["review"] is None   # no next step is asked for
    assert k["K2"]["tracking"]["today"] is False and k["K2"]["review"] is not None
    assert team.c["sam"].post(team.url("/review/K1/accept")).status_code == 409                          # nothing to accept
    assert team.c["sam"].put(team.url("/review/K1"), json={"next_step": "x"}).status_code == 409
    assert [c["kpi_id"] for c in get(team)["coming"]] == ["K2"]


def test_the_status_set_on_the_process_map_reaches_the_review_and_wins(world):
    seed(world, kpis=[blank_tracking(kpi("K1", "Capital calls")), blank_tracking(kpi("K2", "Exposure"))],
         answers=[answer("K1", tracked="not_tracked"), answer("K2", tracked="not_tracked")])
    team = Team(world)
    assert by_id(get(team))["K1"]["tracking"]["today"] is False
    assert team.c["hana"].put(team.url(PM + "/K1/tracking"), json={"status": "tracked_now"}).status_code == 200
    k = by_id(get(team))
    assert k["K1"]["tracking"]["today"] is True and k["K1"]["review"] is None
    assert k["K2"]["tracking"]["today"] is False                                                         # untouched


def test_owners_who_disagree_on_tracking_leave_it_open_until_settled(world):
    other = {**answer("K1", tracked="partly", by=me("pia")), "id": "b"}
    seed(world, kpis=[blank_tracking(kpi("K1", "Capital calls"))], answers=[answer("K1", tracked="tracked_now"), other])
    k = by_id(get(Team(world)))["K1"]
    assert k["tracking"]["mark"] == "unknown" and k["tracking"]["today"] is False


def test_a_restricted_measure_confirmed_by_its_owners_never_blocks_the_checklist(world):
    hidden = {**kpi("K2", "Bonus pool", tracking="not_tracked"), "governance": {"personal": "yes", "sensitive": True, "may_see": [me("bea"), me("dan"), me("pia")]}}
    seed(world, kpis=[kpi("K1", "Capital calls"), hidden])
    team = Team(world)
    assert get(team, "hana")["items"][3]["met"] is False                                                 # nothing confirmed yet
    confirm_all(team, ("K1", "K2"))
    v = get(team, "hana")
    assert next(i for i in v["items"] if i["id"] == "next_steps")["met"] is True and v["can_countersign"] is True
    a, b = sign_both(team)
    assert a.status_code == 200 and b.status_code == 200 and b.json()["status"] == "signed"


# ---- N-D: confirming needs an answer -------------------------------------------------------------------------------
def test_an_owner_who_never_answered_cannot_confirm_their_part(world):
    seed(world, silent=True)  # only Dan answered K1
    team = Team(world)
    r = team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K1", "part": "definition"})
    assert r.status_code == 409 and r.json()["message"] == "Answer the questions for this part first."
    assert team.c["dan"].post(team.url("/confirm"), json={"kpi_id": "K1", "part": "source"}).status_code == 200


def test_a_meeting_answer_in_their_name_lets_an_owner_confirm(world):
    seed(world)
    team = Team(world)
    meeting = {**answer("K1", by=me("bea")), "id": "m1"}          # the fixture's answers are meeting answers
    path = world.plane("co-a").path("intents", "m2_baseline", BID, "answers.json")
    path.write_text(json.dumps([*json.loads(path.read_text()), meeting]))
    assert team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K1", "part": "definition"}).status_code == 200


# ---- N-E: a signed baseline is read-only ---------------------------------------------------------------------------
@pytest.fixture
def signed(world):
    seed(world)
    team = Team(world)
    team.c["sam"].put(team.url("/review/K2"), json={"next_step": "Ask the custodian for a feed"})
    team.c["sam"].post(team.url("/review/K2/accept"))
    confirm_all(team)
    a, b = sign_both(team)
    assert b.json()["status"] == "signed"
    return team


WRITES = [("put", "/kpis/K1/owners", {"business": {"name": "Someone"}}), ("put", "/kpis/K1/governance", {"personal": "no"}),
          ("post", PM + "/draw", None), ("post", PM + "/K1/steps", {"lane": "Ops", "text": "A step"}),
          ("put", PM + "/K1/tracking", {"status": "partly"}), ("post", "/requests", None),
          ("put", "/meeting-answers", {"owner_name": "X", "kpi_id": "K1", "answers": {}}),
          ("post", "/confirm", {"kpi_id": "K1", "part": "definition"}),
          ("post", "/signoff/settle", {"kpi_id": "K1", "field": "tracked_today", "value": "yes"}),
          ("put", "/review/K2", {"next_step": "Changed"}), ("post", "/review/K2/accept", None),
          ("post", "/catalogue/sources/rows", {"cells": {}}), ("post", "/catalogue/refresh", None)]


@pytest.mark.parametrize("verb,tail,body", WRITES)
def test_every_write_on_a_signed_baseline_answers_409(signed, verb, tail, body):
    who = "hana" if "/review/K2/accept" not in tail else "sam"
    r = getattr(signed.c[who], verb)(signed.url(tail), **({"json": body} if body is not None else {}))
    assert r.status_code == 409 and r.json()["message"] == SIGNED, r.text


def test_the_work_list_says_signed_and_a_new_version_opens_the_working_copy_again(signed):
    path = signed.world.plane("co-a").path("intents", "m2_baseline", BID, "baseline.json")
    assert json.loads(path.read_text())["state"] == "signed"   # the work list derives each measure's "signed" from this (test_m2_worklist)
    assert signed.c["sam"].post(signed.url("/versions")).status_code == 200
    assert json.loads(path.read_text())["state"] == "review"
    assert signed.c["hana"].put(signed.url(PM + "/K1/tracking"), json={"status": "partly"}).status_code == 200


def test_the_answer_link_routes_are_closed_too(signed):
    from modules.m2_baseline.api.signed_guard import refuse_if_signed
    from modules.m2_baseline.store.baseline import Locked
    with pytest.raises(Locked):
        refuse_if_signed(signed.world.plane("co-a"), BID)


# ---- N-F: gaps of real kinds ----------------------------------------------------------------------------------------
def test_a_demo_sized_record_has_a_few_gaps_not_a_thousand(world):
    ks = [kpi(f"K{n:02d}", f"Measure {n}") for n in range(1, 17)]
    blank = {f"Column {c}": prov("", "guessed", "Lens") for c in range(12)}
    decided = {"Contains personal data?": prov("No", "stated", "x"), "Personal data class": prov("Neither", "stated", "x")}  # M2-E4: governance is decided before signing
    cat = {"sources": [{"Source ID": prov(f"S{n:02d}", "stated", "x"), **blank, "Contains personal data?": decided["Contains personal data?"]} for n in range(7)],
           "tables": [{"Item ID": prov(f"T{n:02d}", "stated", "x"), **blank} for n in range(16)],
           "fields": [{"Item ID": prov(f"F{n:03d}", "stated", "x"), **blank, "Personal data class": decided["Personal data class"]} for n in range(70)], "extractions": [], "kpis": []}
    seed(world, kpis=ks, answers=[answer(k["id"]) for k in ks], catalogue=cat)
    team = Team(world)
    confirm_all(team, [k["id"] for k in ks])
    sign_both(team)
    gaps = team.c["hana"].get(team.url("/handoff")).json()["gaps"]
    assert len(gaps) <= 3 and not [g for g in gaps if g["type"] in ("unknown", "empty")]


def test_gaps_are_of_real_kinds_with_plain_messages(world):
    seed(world, kpis=[kpi("K1", "Capital calls"), blank_tracking(kpi("K2", "Exposure")), kpi("K3", "Fees", owners=(None, "dan", "pia")),
                      kpi("K4", "Reports")],  # M2-E4: personal data is decided before signing, so a "personal data undecided" gap can no longer reach a signed record
         answers=[answer("K1"), answer("K2", tracked=None), answer("K4")])
    team = Team(world)
    team.c["sam"].put(team.url("/review/K2"), json={"tentative_date": "2027-03-31"})
    team.c["sam"].post(team.url("/review/K2/accept"))
    confirm_all(team, ("K1", "K2", "K4"))
    team.c["hana"].post(team.url("/confirm"), json={"kpi_id": "K3", "part": "source"})
    assert sign_both(team)[1].status_code == 200
    gaps = team.c["hana"].get(team.url("/handoff")).json()["gaps"]
    kinds = {g["type"] for g in gaps}
    assert kinds <= {"conflict", "no_owner", "personal_undecided", "tracking_unknown", "silent_accepted", "not_tracked"}
    assert {"no_owner"} <= kinds and "personal_undecided" not in kinds
    assert next(g for g in gaps if g["type"] == "no_owner")["where"] == "Fees: no business owner"
    assert all(g["why"] and g["action"] for g in gaps)


def test_an_owner_who_never_answered_and_was_accepted_is_a_gap(world):
    seed(world, kpis=[kpi("K2", "Exposure", tracking="not_tracked")], answers=[answer("K2", source=None, tracked="no", arrival=None)])
    team = Team(world)
    team.c["sam"].put(team.url("/review/K2"), json={"next_step": "Ask the custodian"})
    team.c["sam"].post(team.url("/review/K2/accept"))
    assert team.c["dan"].post(team.url("/confirm"), json={"kpi_id": "K2", "part": "source"}).status_code == 200
    assert sign_both(team)[1].status_code == 200
    gaps = team.c["hana"].get(team.url("/handoff")).json()["gaps"]
    silent = [g for g in gaps if g["type"] == "silent_accepted"]
    assert [g["where"] for g in silent] == [f"Exposure: {me('bea')} never answered", f"Exposure: {me('pia')} never answered"]
    assert silent[0]["accepted"]["by"] == me("sam")


# ---- N-G: the review keeps every owner's arrival --------------------------------------------------------------------
def rows_answer(kpi_id, by, frequency, sla):
    def f(v):
        return prov(v, "stated", by, "meeting")
    row = {"name": f("Custodian portal"), "frequency": f(frequency), "sla": f(sla), "structure": f("structured")}
    return {**answer(kpi_id, by=by), "id": f"r-{by}", "sources": f([row])}


def test_differing_arrival_answers_show_as_a_disagreement_in_the_review(world):
    seed(world, kpis=[kpi("K1", "Capital calls")], answers=[
        rows_answer("K1", "Test Sara", "daily", "Around 16:00"), rows_answer("K1", "Test Tom", "daily", "By 12:00"),
        rows_answer("K1", "Test Arjun", "daily", "By 12:00 on working days")])
    team = Team(world)
    k = by_id(get(team))["K1"]
    arrival = next(s for s in k["sensing"] if s["id"] == "arrival")
    assert arrival["differs"] is True
    for words in ("Test Sara: Daily, Around 16:00", "Test Tom: Daily, By 12:00", "Test Arjun: Daily, By 12:00 on working days"):
        assert words in arrival["value"]
    assert "When it arrives: owners gave different answers" in k["unknowns"]
    assert "Custodian portal" not in json.dumps(arrival)          # a system's name is never in the arrival line


def test_the_same_arrival_from_everyone_is_not_a_disagreement(world):
    seed(world, kpis=[kpi("K1", "Capital calls")], answers=[rows_answer("K1", "Test Sara", "daily", "By 12:00"), rows_answer("K1", "Test Tom", "daily", "By 12:00")])
    arrival = next(s for s in by_id(get(Team(world)))["K1"]["sensing"] if s["id"] == "arrival")
    assert arrival["differs"] is False and arrival["value"] == "Daily, By 12:00"


# ---- review round: empty meeting answer, guard hardening, the waiver policy ------------------------------------------------
def test_an_empty_meeting_answer_is_refused_and_does_not_let_a_silent_owner_confirm(world):
    seed(world, silent=True)
    team = Team(world)
    r = team.c["hana"].put(team.url("/meeting-answers"), json={"owner_name": me("bea"), "kpi_id": "K1", "answers": {}})
    assert r.status_code == 422 and "at least one question" in r.json()["message"]
    assert team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K1", "part": "definition"}).status_code == 409


def test_answered_needs_a_real_answer_field():
    from modules.m2_baseline.domain.readiness import answered
    blank = {"kpi_id": "K1", "owner_name": "Bea", "source": unknown("Bea", "not answered yet"), "sample_doc_id": None}
    idk = {"kpi_id": "K1", "owner_name": "Bea", "source": unknown("Bea", "answer link")}
    assert not answered([{"kpi_id": "K1", "owner_name": "Bea"}], "K1", "Bea") and not answered([blank], "K1", "Bea")
    assert answered([idk], "K1", "Bea")                                   # an explicit "I don't know" counts


def _baseline_file(team):
    return team.world.plane("co-a").path("intents", "m2_baseline", BID, "baseline.json")


def test_a_baseline_signed_before_the_state_was_kept_is_still_read_only(signed):
    path = _baseline_file(signed)
    path.write_text(json.dumps({**json.loads(path.read_text()), "state": "review"}))     # as signed baselines were written before
    r = signed.c["hana"].put(signed.url(PM + "/K1/tracking"), json={"status": "partly"})
    assert r.status_code == 409 and r.json()["message"] == SIGNED
    assert signed.c["sam"].post(signed.url("/versions")).status_code == 200              # a new version opens it again
    assert signed.c["hana"].put(signed.url(PM + "/K1/tracking"), json={"status": "partly"}).status_code == 200


def test_an_unreadable_state_fails_closed_but_a_missing_baseline_stays_the_routes_404(signed):
    _baseline_file(signed).write_text("{not json")
    assert signed.c["hana"].put(signed.url(PM + "/K1/tracking"), json={"status": "partly"}).status_code == 409
    gone = signed.c["hana"].put(signed.url(PM + "/K1/tracking", bid="d" * 32), json={"status": "partly"})
    assert gone.status_code in (403, 404)


def test_the_waiver_applies_only_to_a_restricted_measure_the_sponsor_cannot_see(world):
    names = [me("bea"), me("dan"), me("pia")]
    gov = lambda who: {"personal": "yes", "sensitive": True, "may_see": who}  # noqa: E731
    seed(world, kpis=[kpi("K1", "Capital calls"), {**kpi("K2", "Seen pay", tracking="not_tracked"), "governance": gov([*names, me("sam")])},
                      {**kpi("K3", "Hidden pay", tracking="not_tracked"), "governance": gov(names)}])
    team = Team(world)
    confirm_all(team, ("K1", "K2", "K3"))
    steps = next(i for i in get(team, "hana")["items"] if i["id"] == "next_steps")
    assert steps["met"] is False and len(steps["missing"]) == 1 and "Seen pay" in steps["missing"][0]   # only the one the sponsor can see

