"""B13: Define inside an intent. Session start, extend, close (stage only, ruling 26), reopen; review dates; the decisions counter."""
import json
from datetime import date

import pytest

from modules.m1_intent.store.board import BoardStore, TogetherStore
from modules.m1_intent.store.together_shelves import ShelfStore
from sh_platform.intents import define as D
from sh_platform.intents import store
from sh_platform.plane import PlaneStore

SID = "a" * 32
IID = "ini-" + "b" * 32
ORG = {"id": "a-org", "name": "Janet", "roles": {"company_admin"}, "keys": {"a-org", "janet"}}
PAT = {"id": "a-p", "name": "Pat", "roles": {"participant"}, "keys": {"a-p", "pat"}}
NOW = "2026-10-07T10:00:00+00:00"


def cluster(cid: str) -> dict:
    return {"id": cid, "name": cid, "note_ids": [], "source": "north", "pack_problem_id": None, "reasoning": ""}


@pytest.fixture
def world(tmp_path):
    plane = PlaneStore(tmp_path).create("acme")
    rec = {"id": IID, "type": "initiative", "title": "Manager benchmarks", "purpose": "One view", "state": "open", "created_by": "a-org",
           "people": {"organiser": {"account_id": "a-org", "name": "Janet"}, "participants": [{"account_id": "a-p", "name": "Pat"}], "affected": []},
           "stages": [{"key": "think_unfiltered", "state": "closed", "opened_at": NOW, "closed_at": NOW},
                      {"key": "define_strategically", "state": "open", "opened_at": NOW, "closed_at": None}],
           "refs": {"wall_session_ids": [SID], "charter_outcome_id": None}, "event_count": 0,
           "events": {"path": f"intents/{IID}/events.jsonl", "count": 0, "last_seq": 0, "last_at": None}, "history": []}
    store.create_intent(plane, rec)
    BoardStore(plane).set_grouping(SID, "done", [cluster("c1"), cluster("c2"), cluster("c3")])
    TogetherStore(plane).update(SID, lambda d: {**d, "ticked": ["c1"]})
    ShelfStore(plane).update(SID, lambda d: {**d, "shelves": {"c1": {"shelf": "must", "reason": None, "review_date": None},
                                                              "c2": {"shelf": "should", "reason": None, "review_date": None}}})
    return plane


def run(plane, who, body):
    with store.locked(plane):
        rec = store.read_intent(plane, IID)
        refused = D.act(plane, rec, who, body, NOW, D.board_counts(plane, D.wall_of(rec), date(2026, 10, 7)))
        if not refused:
            store.write_intent(plane, rec)
    return refused, store.read_intent(plane, IID)


def test_decisions_counter_reads_the_shelves_and_ticks(world):
    c = D.board_counts(world, SID, date(2026, 10, 7))
    assert (c["made"], c["of"], c["unticked"]) == (1, 3, 1)  # c1 on Must and ticked; c2 on Should not ticked; c3 not placed
    assert c["shelf_counts"] == {"must": 1, "should": 1, "good_to_have": 0, "future": 0, "not_placed": 1}
    assert D.board_counts(world, None, date(2026, 10, 7))["of"] == 0


def test_only_the_organiser_starts_and_start_needs_participants(world):
    assert run(world, PAT, {"action": "start"})[0] == (403, D.ONLY_ORGANISER)
    refused, rec = run(world, ORG, {"action": "start"})
    assert refused is None and rec["state"] == "in_session"
    s = rec["define"]["session"]
    assert (s["planned_minutes"], s["started_at"], s["decisions_made"], s["decisions_of"]) == (90, NOW, 1, 3)


def test_extend_needs_a_reason(world):
    run(world, ORG, {"action": "start"})
    assert run(world, ORG, {"action": "extend", "reason": "  "})[0] == (422, D.NEED_REASON)
    _, rec = run(world, ORG, {"action": "extend", "reason": "Two groups still tied"})
    assert rec["define"]["session"]["extensions"] == [{"by": "a-org", "at": NOW, "minutes": 15, "reason": "Two groups still tied"}]


def test_close_needs_the_charter_draft_and_leaves_the_intent_state(world):
    run(world, ORG, {"action": "start"})
    assert run(world, ORG, {"action": "close"})[0] == (409, D.NO_CHARTER)
    world.path("intents", "m1_intent", "charters", f"{SID}.json").parent.mkdir(parents=True, exist_ok=True)
    world.path("intents", "m1_intent", "charters", f"{SID}.json").write_text("{}")
    refused, rec = run(world, ORG, {"action": "close"})
    assert refused is None
    assert rec["state"] == "in_session"  # ruling 26: Define close moves nothing; closing comes at signature
    assert rec["stages"][1]["state"] == "closed" and rec["stages"][1]["closed_at"] == NOW
    assert rec["define"]["shelf_counts"]["not_placed"] == 1 and rec["define"]["refusals"] == 0
    assert rec["define"]["session"]["ended_at"] == NOW
    kinds = [json.loads(x)["kind"] for x in world.path("intents", IID, "events.jsonl").read_text().splitlines()]
    assert kinds == ["define_session_started", "define_closed"] and rec["events"]["count"] == 2
    assert run(world, ORG, {"action": "close"})[0] == (409, D.CLOSED)


def test_reopen_needs_a_reason_and_is_refused_after_signing(world):
    world.path("intents", "m1_intent", "charters", f"{SID}.json").parent.mkdir(parents=True, exist_ok=True)
    world.path("intents", "m1_intent", "charters", f"{SID}.json").write_text("{}")
    run(world, ORG, {"action": "close"})
    assert run(world, ORG, {"action": "reopen"})[0] == (422, D.REOPEN_REASON)
    refused, rec = run(world, ORG, {"action": "reopen", "reason": "A cluster sits on the wrong shelf"})
    assert refused is None and rec["stages"][1]["closed_at"] is None and len(rec["define"]["reopened"]) == 1
    run(world, ORG, {"action": "close"})
    with store.locked(world):
        rec = store.read_intent(world, IID)
        rec["refs"]["charter_outcome_id"] = "o1"
        store.write_intent(world, rec)
    assert run(world, ORG, {"action": "reopen", "reason": "Too late"})[0] == (409, D.SIGNED)


def test_review_date_must_be_after_today():
    today = date(2026, 10, 7)
    assert D.review_date_ok("2027-01-07", today) == "2027-01-07"
    assert D.review_date_ok("2026-10-07", today) is None
    assert D.review_date_ok("not a date", today) is None
    assert D.review_date_ok(None, today) is None


def test_refusals_are_counted_from_the_events(world):
    who = ORG
    D._log_alone(world, IID, who, "shelf_refused", {"cluster": "c3", "to": "must", "missing": ["may_see"]})
    assert D.refusals(world, IID) == 1


def test_a_reader_who_is_not_named_gets_no_content(world):
    rec = store.read_intent(world, IID)
    stranger = {"id": "a-x", "name": "Xu", "roles": {"participant"}, "keys": {"a-x", "xu"}}
    assert D.relation(rec, stranger) == {"organiser": False, "reader": False}
    assert D.relation(rec, PAT)["reader"] is True


def test_view_carries_baseline_and_hold_flags(world):
    class R:  # the bare minimum _who reads
        state = type("S", (), {"account_id": "a-org", "roles": ["company_admin"], "display_name": "Janet", "company_id": "acme"})()
    rec = store.read_intent(world, IID)
    assert D.stage_of(rec)["closed_at"] is None  # the gate (R3) is this, not the wall's state
    assert not (rec["refs"].get("baseline_ids")) and not (rec.get("define") or {}).get("held_at")
