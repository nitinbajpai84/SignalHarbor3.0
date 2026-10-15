"""Readiness with honest answers: free text from different owners is combined, only a real choice conflict blocks and a
person settles it (both versions kept, audit-logged); the review says who each measure waits on; accepting an unknown
needs a plan and is recorded once. The real app over temporary folders (fixtures: test_m2_signoff_kit.py)."""
import json

from test_m2_signoff import by_id, get
from test_m2_signoff_kit import BID, Team, answer, me, seed, standard_answers

from modules.m2_baseline.store.answers import read_answers

PIA = "Test Process Pia"
SETTLE = "/signoff/settle"


def second(kpi_id="K1", **kw):
    return {**answer(kpi_id, by=PIA, **kw), "id": f"b-{kpi_id}"}


def test_free_text_from_two_owners_is_shown_together_and_is_not_a_conflict(world):
    seed(world, answers=[answer("K1"), second(source="Sara's mailbox", arrival="Mid afternoon"), *standard_answers()[1:]])
    k1 = by_id(get(Team(world)))["K1"]
    assert k1["source"]["status"] == "stated"
    assert k1["source"]["value"] == "Test Data Dan: Custodian portal export; Test Process Pia: Sara's mailbox"
    arrival = next(s for s in k1["sensing"] if s["id"] == "arrival")
    assert arrival["status"] == "stated" and "Mid afternoon" in arrival["value"] and "Daily by noon" in arrival["value"]
    assert k1["missing"] == [] and k1["state"] == "ready"


def test_a_real_choice_conflict_blocks_until_the_sponsor_settles_it_and_both_versions_stay(world):
    seed(world, answers=[answer("K1"), second(tracked="no", dtype="both"), *standard_answers()[1:]])
    team = Team(world)
    k1 = by_id(get(team))["K1"]
    tracked = next(s for s in k1["sensing"] if s["id"] == "tracked_today")
    assert tracked["status"] == "conflict" and {o["value"] for o in tracked["options"]} == {"yes", "no"}
    assert {o["by"] for o in tracked["options"]} == {"Test Data Dan", PIA}
    assert k1["state"] == "not_ready" and get(team)["ready"] is False

    body = {"kpi_id": "K1", "field": "tracked_today", "value": "no"}
    assert team.c["bea"].post(team.url(SETTLE), json=body).status_code == 403            # the route refuses an owner
    assert team.analyst.post(team.url(SETTLE), json=body).status_code == 403
    assert team.c["sam"].post(team.url(SETTLE), json={**body, "value": "maybe"}).status_code == 422
    assert team.c["sam"].post(team.url(SETTLE), json={**body, "field": "arrival"}).status_code == 422  # free text cannot be settled
    r = team.c["sam"].post(team.url(SETTLE), json=body)
    assert r.status_code == 200, r.text
    after = next(s for s in by_id(r.json())["K1"]["sensing"] if s["id"] == "tracked_today")
    assert after["status"] == "stated" and after["value"] == "no" and after["settled"]["by"] == me("sam")
    assert {o["value"] for o in after["settled"]["options"]} == {"yes", "no"}              # both versions kept on the record
    assert [a["tracked_today"]["value"] for a in read_answers(world.plane("co-a"), BID) if a["kpi_id"] == "K1"] == ["yes", "no"]
    # data type was a conflict too ("structured" against "both"); the sponsor settles that one as well, and the head of data may too
    r = team.c["hana"].post(team.url(SETTLE), json={"kpi_id": "K1", "field": "data_type", "value": "structured"})
    assert r.status_code == 200 and by_id(r.json())["K1"]["state"] == "ready"
    assert team.c["sam"].post(team.url(SETTLE), json=body).status_code == 409             # nothing left to settle
    entries = team.c["sam"].get(team.url("/audit")).json()
    assert entries["intact"] and [e["action"] for e in entries["entries"]] == ["settle", "settle"]
    assert entries["entries"][0]["by"] == me("sam") and entries["entries"][0]["kpi_id"] == "K1"


def test_a_settled_choice_is_a_conflict_again_when_the_answers_change(world):
    seed(world, answers=[answer("K1"), second(tracked="no"), *standard_answers()[1:]])
    team = Team(world)
    team.c["sam"].post(team.url(SETTLE), json={"kpi_id": "K1", "field": "tracked_today", "value": "no"})
    folder = world.plane("co-a").path("intents", "m2_baseline", BID, "answers.json")
    rows = json.loads(folder.read_text())
    for r in rows:
        if r["id"] == "b-K1":
            r["tracked_today"]["value"] = "partly"
    folder.write_text(json.dumps(rows))
    tracked = next(s for s in by_id(get(team))["K1"]["sensing"] if s["id"] == "tracked_today")
    assert tracked["status"] == "conflict"


def test_the_review_says_who_each_measure_is_waiting_on(world):
    seed(world, silent=True)  # only Dan answered K1; Bea and Pia are named but have not
    k1 = by_id(get(Team(world)))["K1"]
    assert k1["waiting_on"] == [me("bea"), me("pia")]
    assert k1["waiting_note"] == f"waiting on {me('bea')}, {me('pia')}"


def test_accepting_an_unknown_needs_a_next_step_or_a_date_and_is_recorded_once(world):
    seed(world)
    team = Team(world)
    r = team.c["sam"].post(team.url("/review/K2/accept"))
    assert r.status_code == 409 and r.json()["error"] == "needs_plan"
    assert team.c["sam"].put(team.url("/review/K2"), json={"tentative_date": "2027-03-31"}).status_code == 200
    assert team.c["sam"].post(team.url("/review/K2/accept")).status_code == 200
    assert team.c["sam"].post(team.url("/review/K2/accept")).status_code == 409
    actions = [e["action"] for e in team.c["sam"].get(team.url("/audit")).json()["entries"]]
    assert actions.count("accept") == 1
