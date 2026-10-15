"""LI-M1 item 4: stages close on time and the vote decides. The briefing, the rooms and the together stage advance by
themselves when the timer ends; "I'm done" from everyone closes a stage early; the groups the room backed with Must or
Should go into the charter by the rule in contracts/board.yaml, and the organiser only breaks ties or removes one."""
import time

import pytest

from m1_kit import BASE
from modules.m1_intent.domain import board as B
from modules.m1_intent.domain import together as T
from test_m1_board_kit import Board, GatherStub, grouped, together
from test_m1_briefing_kit import T0, make_world, session_at, stage_of
from test_m1_seat_wiring_kit import flow, new_world

LATE, EXPOSURE = "Calls arrive too late", "No single exposure view"


def jump(b: Board, seconds: float) -> None:
    """The server clock moves on (the board kit uses the real clock)."""
    b.w.app.state.m1_clock = lambda: time.time() + seconds


def vote(who, cid, option):
    r = who.call("POST", f"/together/clusters/{cid}/vote", json={"option": option})
    assert r.status_code == 200, r.text
    return r.json()


def cl(b, name):
    return next(c for c in b.org_call("GET", "/together").json()["clusters"] if c["name"] == name)


# ---- the rule, in the contract
def test_the_vote_rule_is_in_the_contract_and_ticks_the_leading_must_or_should():
    s = B.load_settings()
    assert tuple(s.auto_priorities) == ("must", "should") and s.auto_min_votes == 1
    z = {"must": 0, "should": 0, "could": 0, "not_this_time": 0}
    assert T.auto_decision(s, z) == "none"
    assert T.auto_decision(s, {**z, "must": 2, "could": 1}) == "tick"
    assert T.auto_decision(s, {**z, "should": 1}) == "tick"
    assert T.auto_decision(s, {**z, "could": 3, "must": 1}) == "none"
    assert T.auto_decision(s, {**z, "not_this_time": 2}) == "none"
    assert T.auto_decision(s, {**z, "must": 2, "should": 2}) == "tick"  # Must and Should count together
    assert T.auto_decision(s, {**z, "must": 1, "not_this_time": 1}) == "tie"
    assert T.auto_decision(s, {**z, "could": 2, "not_this_time": 2}) == "none"  # nobody backed it: nothing to break


def test_votes_tick_groups_into_the_charter_as_they_come(tmp_path):
    b = together(tmp_path)
    ada, ben = b.guests
    late, exp = cl(b, LATE)["id"], cl(b, EXPOSURE)["id"]
    vote(ada, late, "must")
    vote(ben, late, "should")  # one Must and one Should: both back it, Must and Should are not rivals
    vote(ada, exp, "could")
    v = {c["name"]: c for c in b.org_call("GET", "/together").json()["clusters"]}
    assert v[LATE]["ticked"] and v[LATE]["auto_ticked"] and not v[LATE]["tie"]
    assert not v[EXPOSURE]["ticked"] and not v[EXPOSURE]["auto_ticked"]


def test_a_tie_is_left_to_the_organiser_and_a_removal_is_not_undone_by_later_votes(tmp_path):
    b = together(tmp_path)
    ada, ben = b.guests
    late = cl(b, LATE)["id"]
    vote(ada, late, "must")
    vote(ben, late, "could")
    v = cl(b, LATE)
    assert v["ticked"] is False and v["tie"] is True and v["auto_ticked"] is False  # 1 Must against 1 Could: a tie
    assert b.org_call("POST", f"/together/clusters/{late}/tick", json={"ticked": True}).status_code == 200  # the organiser breaks it
    vote(ben, late, "must")
    assert cl(b, LATE)["ticked"] is True
    assert b.org_call("POST", f"/together/clusters/{late}/tick", json={"ticked": False}).status_code == 200  # and may remove it
    vote(ada, late, "must")
    assert cl(b, LATE)["ticked"] is False  # a later vote does not tick it again


# ---- the timer ends the stage
def test_the_together_stage_ends_by_itself_ticks_by_vote_and_drafts_the_charter(tmp_path):
    b = together(tmp_path)
    ada, ben = b.guests
    late, exp = cl(b, LATE)["id"], cl(b, EXPOSURE)["id"]
    vote(ada, late, "must")
    vote(ben, late, "must")
    vote(ada, exp, "not_this_time")
    assert b.org.get(f"{BASE}/sessions/{b.sid}").json()["state"] == "together"
    jump(b, 3600)
    t = b.org_call("GET", "/timer").json()
    assert t["stage"] == "signing"
    got = b.org_call("GET", "/charter").json()
    assert got["state"] == "signing" and [p["title"] for p in got["charter"]["problems"]] == [LATE]
    assert got["charter"]["problems"][0]["priority"] == "must"


def test_when_nothing_was_backed_the_together_stage_waits_for_the_organiser(tmp_path):
    b = together(tmp_path)
    jump(b, 3600)
    assert b.org_call("GET", "/timer").json()["stage"] == "together"
    assert b.org_call("GET", "/together").json()["held"] is False


def test_everyone_done_closes_the_together_stage_early(tmp_path):
    b = together(tmp_path)
    ada, ben = b.guests
    vote(ada, cl(b, LATE)["id"], "must")
    assert ada.call("POST", "/together/done", json={"done": True}).status_code == 200
    assert b.org.get(f"{BASE}/sessions/{b.sid}").json()["state"] == "together"  # one of two is not everyone
    assert ben.call("POST", "/together/done", json={"done": True}).status_code == 200
    assert b.org.get(f"{BASE}/sessions/{b.sid}").json()["state"] == "signing"


# ---- the briefing and the rooms
@pytest.fixture
def w(tmp_path):
    return make_world(tmp_path)


def test_the_briefing_sends_everyone_to_the_rooms_by_itself_when_time_is_up(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    assert org.get(f"{BASE}/sessions/{sid}/timer").json()["stage"] == "briefing"
    w.now[0] = T0 + 10_000
    t = org.get(f"{BASE}/sessions/{sid}/timer").json()
    assert t["stage"] == "private_rooms" and t["remaining_seconds"] == 8 * 60  # the rooms' own clock starts now
    assert stage_of(org, sid) == "private_rooms"


def test_everyone_clear_ends_the_briefing_early(tmp_path):
    w = new_world(tmp_path)
    org, sid, (ada, ben) = flow(w, "co-a", stage="briefing")
    url = f"{BASE}/sessions/{sid}"
    assert ada.call("POST", "/briefing/confirm", json={"answer": "clear"}).status_code == 200
    assert org.get(url).json()["state"] == "briefing"
    assert ben.call("POST", "/briefing/confirm", json={"answer": "clear"}).status_code == 200
    assert org.get(url).json()["state"] == "private_rooms"


def test_the_rooms_end_by_themselves_still(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "private_rooms")
    w.now[0] = T0 + 10_000
    assert org.get(f"{BASE}/sessions/{sid}/timer").json()["stage"] == "board"
