"""M1-20 agree and discuss, M1-21 tick into the charter, M1-22 the tally as priority (D-020), M1-23 pause and resume, and
read_together_result for M1-P09. Stub North, synthetic family-office notes, no live call."""
import json
import time
from pathlib import Path

import pytest

from m1_kit import BASE
from modules.m1_intent.domain import board as B
from modules.m1_intent.domain import together as T
from modules.m1_intent.store.files import StoreError
from test_m1_board_kit import Board, grouped, together

S = B.load_settings()
OPTIONS = ["must", "should", "could", "not_this_time"]


def vote(who, cid, option):
    return who.call("POST", f"/together/clusters/{cid}/vote", json={"option": option})


def clusters(b, who=None) -> dict:
    r = b.org_call("GET", "/together") if who is None else who.call("GET", "/together")
    assert r.status_code == 200, r.text
    return {c["name"]: c for c in r.json()["clusters"]}


# ---- domain
def test_a_vote_replaces_the_same_persons_earlier_one_and_can_be_taken_back():
    d = {"votes": {}, "agrees": {}, "comments": {}, "ticked": [], "paused_at": None}
    d = T.vote(S, d, "c1", "seatA", "must")
    d = T.vote(S, d, "c1", "seatA", "could")
    d = T.vote(S, d, "c1", "seatB", "could")
    assert T.tally(S, d, "c1") == {"must": 0, "should": 0, "could": 2, "not_this_time": 0}
    assert T.vote(S, d, "c1", "seatB", None)["votes"]["c1"] == {"seatA": "could"}
    for bad in ("maybe", 3, ""):
        with pytest.raises(B.BoardError):
            T.vote(S, d, "c1", "seatA", bad)


def test_the_tally_is_the_priority_and_a_tie_or_no_vote_is_no_priority():
    z = {o: 0 for o in OPTIONS}
    assert T.priority(S, z) is None
    assert T.priority(S, {**z, "should": 2, "must": 1}) == "should"
    assert T.priority(S, {**z, "should": 2, "must": 2}) is None


def test_agree_is_one_mark_per_person_and_comments_are_limited():
    d = {"votes": {}, "agrees": {}, "comments": {}, "ticked": [], "paused_at": None}
    d = T.agree(T.agree(d, "c", "a", True), "c", "a", True)
    assert d["agrees"]["c"] == ["a"] and T.agree(d, "c", "a", False)["agrees"]["c"] == []
    with pytest.raises(B.BoardError):
        T.agree(d, "c", "a", "yes")
    for bad in ("", "   ", "x" * (S.comment_chars + 1), 5):
        with pytest.raises(B.BoardError):
            T.comment(S, d, "c", bad, False, "Ada")
    a = T.comment(S, d, "c", "  We   should talk  ", True, "Ada")["comments"]["c"][0]
    assert a == {"text": "We should talk", "anonymous": True}  # an anonymous comment holds nothing about its author


def test_the_options_come_from_the_contract():
    assert list(S.option_ids) == OPTIONS and [o["label"] for o in S.options] == ["Must", "Should", "Could", "Not this time"]


# ---- the stage and who may do what
def test_the_room_comes_back_together_from_the_board_only_by_the_organiser(tmp_path):
    b = grouped(tmp_path)
    assert b.guests[0].call("POST", "/together").status_code in (401, 403, 404)
    assert b.org_call("GET", "/together").status_code == 409  # not yet
    b.to_together()
    assert b.org_call("POST", "/together").status_code == 409
    v = b.org_call("GET", "/together").json()
    assert v["stage"] == "together" and v["can_vote"] and [o["id"] for o in v["options"]] == OPTIONS
    assert all(c["note_count"] == len(c["notes"]) for c in v["clusters"]) and v["on_its_own_count"] == 1


def test_everyone_votes_agrees_and_comments_and_sees_a_live_tally(tmp_path):
    b = together(tmp_path)
    ada, ben = b.guests
    late = clusters(b)["Calls arrive too late"]["id"]
    assert vote(ada, late, "must").status_code == 200 and vote(ben, late, "must").status_code == 200
    assert b.org_call("POST", f"/together/clusters/{late}/vote", json={"option": "should"}).status_code == 200  # the organiser votes too
    ada.call("POST", f"/together/clusters/{late}/agree", json={"agree": True})
    ben.call("POST", f"/together/clusters/{late}/agree", json={"agree": True})
    for who, text, anon in [(ada, "Calls reach the cash team last", False), (ben, "I would put this first", True)]:
        assert who.call("POST", f"/together/clusters/{late}/comments", json={"text": text, "anonymous": anon}).status_code == 200
    c = clusters(b, ada)["Calls arrive too late"]
    assert c["votes"] == {"must": 2, "should": 1, "could": 0, "not_this_time": 0} and c["vote_total"] == 3 and c["priority"] == "must"
    assert c["agree_count"] == 2 and c["comment_count"] == 2 and c["my_vote"] == "must" and c["my_agree"] is True
    assert clusters(b, ben)["Calls arrive too late"]["my_vote"] == "must"
    assert c["comments"] == [{"text": "Calls reach the cash team last", "anonymous": False, "author_name": "Ada Guest"},
                             {"text": "I would put this first", "anonymous": True}]
    vote(ada, late, "not_this_time")  # changeable
    assert clusters(b, ada)["Calls arrive too late"]["votes"]["must"] == 1


def test_voting_is_refused_outside_the_together_stage_and_while_held(tmp_path):
    b = grouped(tmp_path)
    late = b.cluster("Calls arrive too late")["id"]
    assert vote(b.guests[0], late, "must").status_code == 409  # still the board
    b.to_together()
    assert b.org_call("POST", "/pause").status_code == 200
    r = vote(b.guests[0], late, "must")
    assert r.status_code == 409 and "held" in r.json()["message"]
    assert b.org_call("GET", "/together").json()["held"] is True  # the room can still be read while held


def test_a_vote_for_a_group_that_does_not_exist_or_a_bad_body_is_refused_plainly(tmp_path):
    b = together(tmp_path)
    ada = b.guests[0]
    assert ada.call("POST", f"/together/clusters/{'0' * 16}/vote", json={"option": "must"}).status_code == 422
    late = clusters(b)["Calls arrive too late"]["id"]
    assert vote(ada, late, "maybe").status_code == 422
    assert ada.call("POST", f"/together/clusters/{late}/vote", json={"opt": "must"}).status_code == 400
    assert ada.call("POST", f"/together/clusters/{late}/comments", json={"text": ""}).status_code == 422
    assert ada.call("POST", f"/together/clusters/{late}/agree", json={"agree": "yes"}).status_code == 422


def test_only_the_organiser_ticks_pauses_and_resumes(tmp_path):
    b = together(tmp_path)
    late = clusters(b)["Calls arrive too late"]["id"]
    g = b.guests[0]
    for path, body in [(f"/together/clusters/{late}/tick", {"ticked": True}), ("/pause", None), ("/resume", None)]:
        assert g.call("POST", path, **({"json": body} if body else {})).status_code in (401, 403, 404), path


# ---- anonymity in the thread and the votes
def test_an_anonymous_comment_names_nobody_anywhere_and_votes_are_never_shown_by_person(tmp_path):
    b = together(tmp_path)
    ada, ben = b.guests
    late = clusters(b)["Calls arrive too late"]["id"]
    ben.call("POST", f"/together/clusters/{late}/comments", json={"text": "Quiet worry about the cash", "anonymous": True})
    vote(ben, late, "must")
    for who in (None, ada, ben):  # Ben appears only as the named author of his by-name notes, never beside the comment or a vote
        v = clusters(b, who)["Calls arrive too late"]
        assert v["comments"] == [{"text": "Quiet worry about the cash", "anonymous": True}] and "Ben" not in json.dumps(v["votes"])
    stored = next(Path(b.w.settings.data_root).rglob("together/*.json")).read_text(encoding="utf-8")
    assert "Quiet worry" in stored and "Ben" not in stored  # the comment is stored with no name; the vote by an opaque seat id only
    assert not any(p in stored for p in ("Ada", "Guest"))


def test_a_comment_by_name_carries_the_name_and_a_guest_cannot_post_into_another_session(tmp_path):
    b = together(tmp_path)
    other = Board(tmp_path / "second", company="co-b")
    other.close_rooms()
    other.group()
    other.to_together()
    late = clusters(b)["Calls arrive too late"]["id"]
    foreign = other.guests[0]
    r = foreign.c.post(f"{BASE}/sessions/{b.sid}/together/clusters/{late}/vote", json={"option": "must"}, headers={"X-Session-Token": foreign.token})
    assert r.status_code in (401, 403, 404)
    r = foreign.c.get(f"{BASE}/sessions/{b.sid}/together", headers={"X-Session-Token": foreign.token})
    assert r.status_code in (401, 403, 404)
    assert clusters(b)["Calls arrive too late"]["vote_total"] == 0


# ---- ticking and the result M1-P09 reads
def test_ticking_sends_a_cluster_to_the_charter_and_unticking_carries_it_to_a_later_session(tmp_path):
    b = together(tmp_path)
    cs = clusters(b)
    late, expo = cs["Calls arrive too late"]["id"], cs["No single exposure view"]["id"]
    assert b.org_call("POST", f"/together/clusters/{late}/tick", json={"ticked": True}).json()["ticked_count"] == 1
    v = b.org_call("POST", f"/together/clusters/{expo}/tick", json={"ticked": True}).json()
    assert v["ticked_count"] == 2 and v["open_count"] == 0
    v = b.org_call("POST", f"/together/clusters/{expo}/tick", json={"ticked": False}).json()
    assert v["ticked_count"] == 1 and v["open_count"] == 1
    assert b.org_call("POST", f"/together/clusters/{'0' * 16}/tick", json={"ticked": True}).status_code == 422
    assert "No single exposure view" in b.org_call("GET", "/board").text  # nothing is ever deleted


def test_read_together_result_has_the_ticked_clusters_tally_note_count_and_agree_count(tmp_path):
    b = together(tmp_path)
    ada, ben = b.guests
    cs = clusters(b)
    late, expo = cs["Calls arrive too late"]["id"], cs["No single exposure view"]["id"]
    for who in (ada, ben):
        vote(who, late, "must")
        who.call("POST", f"/together/clusters/{late}/agree", json={"agree": True})
        who.call("POST", f"/together/clusters/{late}/comments", json={"text": "Agreed", "anonymous": True})
    vote(ada, expo, "should")
    vote(ben, expo, "could")
    b.org_call("POST", f"/together/clusters/{late}/tick", json={"ticked": True})
    res = T.read_together_result(b.w.plane("co-a"), b.sid)
    assert set(res) == {"session_id", "stage", "ticked", "carried", "on_its_own_count"} and res["stage"] == "together"
    [t] = res["ticked"]
    assert set(t) == {"id", "name", "note_ids", "note_count", "agree_count", "comment_count", "votes", "vote_total", "priority"}
    assert (t["id"], t["name"], t["note_count"], t["agree_count"], t["comment_count"]) == (late, "Calls arrive too late", 2, 2, 2)
    assert t["votes"] == {"must": 2, "should": 0, "could": 0, "not_this_time": 0} and t["vote_total"] == 2 and t["priority"] == "must"
    assert len(t["note_ids"]) == 2 and set(t["note_ids"]) <= set(b.note_ids)
    assert res["carried"] == [{"id": expo, "name": "No single exposure view", "note_count": 3}] and res["on_its_own_count"] == 1
    blob = json.dumps(res)  # no seat, author or comment text in what the charter reads
    assert "Agreed" not in blob and "Guest" not in blob
    assert json.loads(json.dumps(res)) == res


def test_the_result_for_a_session_with_no_board_is_empty_and_a_damaged_file_is_refused(tmp_path):
    b = Board(tmp_path)
    res = T.read_together_result(b.w.plane("co-a"), b.sid)
    assert res["ticked"] == [] and res["carried"] == [] and res["on_its_own_count"] == len(b.note_ids)
    path = b.w.plane("co-a").path("intents", "m1_intent", "together", f"{b.sid}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StoreError):
        T.read_together_result(b.w.plane("co-a"), b.sid)


# ---- pause and resume (M1-23)
def test_pause_keeps_everything_and_resume_returns_to_the_same_stage_with_the_held_time_given_back(tmp_path):
    clock = [time.time()]
    b = Board(tmp_path)
    b.w.app.state.m1_clock = lambda: clock[0]
    b.close_rooms()
    b.group()
    b.to_together()
    t0 = b.org_call("GET", "/timer").json()
    assert t0["stage"] == "together" and t0["timed"]
    late = clusters(b)["Calls arrive too late"]["id"]
    vote(b.guests[0], late, "must")
    clock[0] += 30
    r = b.org_call("POST", "/pause")
    assert r.json() == {"state": "paused", "paused_from": "together"}
    assert b.org_call("GET", "/timer").json()["timed"] is False  # the clock is stopped while held
    clock[0] += 400
    assert b.org_call("POST", "/resume").json() == {"state": "together"}
    t1 = b.org_call("GET", "/timer").json()
    assert t1["timed"] and abs(t1["remaining_seconds"] - (t0["remaining_seconds"] - 30)) <= 2  # the 400 held seconds were not used up
    assert clusters(b)["Calls arrive too late"]["votes"]["must"] == 1  # votes, seats and notes were kept
    assert b.org_call("POST", "/resume").status_code == 409  # not paused any more


def test_pause_works_from_the_private_rooms_and_a_paused_session_refuses_new_notes(tmp_path):
    b = Board(tmp_path)
    assert b.org_call("POST", "/pause").json()["paused_from"] == "private_rooms"
    r = b.guests[0].call("POST", "/room/messages", json={"text": "A note while held", "kind": "note"})
    assert r.status_code == 409
    assert b.org_call("POST", "/resume").json() == {"state": "private_rooms"}
    assert b.guests[0].call("POST", "/room/messages", json={"text": "A note after resume", "kind": "note"}).status_code == 200


def test_pause_is_refused_where_it_cannot_be_done(tmp_path):
    from m1_kit import World
    from test_m1_room_kit import new_session
    w = World(tmp_path)
    org = w.login("solo draft", "co-solo", ["sponsor"])
    sid = new_session(org, seats=1)
    assert org.post(f"{BASE}/sessions/{sid}/pause").status_code == 409  # a draft cannot be held


# ---- industries and one person alone
@pytest.mark.parametrize("company", ["co-a", "co-b", "co-none"])
def test_together_works_for_two_industries_and_a_company_with_no_pack(tmp_path, company):
    b = together(tmp_path, company=company)
    late = clusters(b)["Calls arrive too late"]["id"]
    assert vote(b.guests[0], late, "should").status_code == 200


def test_one_person_working_alone_runs_every_stage_and_an_empty_board_has_nothing_to_vote_on(tmp_path):
    b = Board(tmp_path, company="co-solo", seats=1, names=(), notes=[])
    b.close_rooms()
    b.group()
    b.to_together()
    v = b.org_call("GET", "/together").json()
    assert v["clusters"] == [] and v["ticked_count"] == 0 and v["on_its_own_count"] == 0
    res = T.read_together_result(b.w.plane("co-solo"), b.sid)
    assert res["ticked"] == [] and res["carried"] == []


# ---- IC-3t: the fields the Define screen reads on each cluster
def _signed_baseline(plane, oid, signed_at, signed=True):
    path = plane.path("intents", "m2_baseline", "outcomes", f"{oid}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"kind": "baseline", "signed_at": signed_at if signed else "", "signatures": [{"name": "x"}] if signed else []}))


def test_together_cluster_colour_is_the_boards_colour(tmp_path):
    b = together(tmp_path)
    on_board = {c["id"]: c["colour"] for c in b.org_call("GET", "/board").json()["clusters"]}
    here = {c["id"]: c["colour"] for c in clusters(b).values()}
    assert here == on_board and len(here) >= 2


def test_measure_codes_come_from_the_linked_library_problem_and_are_empty_without_one(tmp_path):
    from test_m1_charter_kit import give_pack_measures
    from modules.m1_intent.store.board import BoardStore
    b = together(tmp_path)
    give_pack_measures(b.w, "industry_a")  # P-0 -> K1 (K9 is not a pack measure), P-1 -> K2
    cs = clusters(b)
    late = cs["Calls arrive too late"]["id"]
    BoardStore(b.w.plane("co-a")).update(b.sid, lambda d: {**d, "clusters": [
        {**c, "pack_problem_id": "P-0"} if c["id"] == late else c for c in d["clusters"]]})
    cs = clusters(b)
    assert cs["Calls arrive too late"]["measure_codes"] == ["K1"]
    assert cs["No single exposure view"]["measure_codes"] == []


def test_baseline_id_is_the_latest_signed_baseline_else_null(tmp_path):
    b = together(tmp_path)
    assert all(c["baseline_id"] is None for c in clusters(b).values())
    plane = b.w.plane("co-a")
    _signed_baseline(plane, "a" * 32, "2026-01-01T00:00:00+00:00")
    _signed_baseline(plane, "b" * 32, "2026-02-01T00:00:00+00:00")
    _signed_baseline(plane, "c" * 32, "2026-03-01T00:00:00+00:00", signed=False)  # unsigned never counts
    assert {c["baseline_id"] for c in clusters(b).values()} == {"b" * 32}


def test_governed_and_missing_are_served_per_cluster_from_module_twos_state(tmp_path):
    from test_m1_charter_kit import give_pack_measures
    from modules.m1_intent.store.board import BoardStore
    b = together(tmp_path)
    give_pack_measures(b.w, "industry_a")
    plane = b.w.plane("co-a")
    late = clusters(b)["Calls arrive too late"]["id"]
    BoardStore(plane).update(b.sid, lambda d: {**d, "clusters": [{**c, "pack_problem_id": "P-0"} if c["id"] == late else c for c in d["clusters"]]})
    assert all("governed" not in c and "missing" not in c for c in clusters(b).values())  # no baseline: absent
    _signed_baseline(plane, "a" * 32, "2026-01-01T00:00:00+00:00")
    folder = plane.path("intents", "m2_baseline", "a" * 32)
    folder.mkdir(parents=True)
    fields = ("owners", "classification", "may_see", "resolving", "affects", "review_date")
    (folder / "governed_state.json").write_text(json.dumps({"K1": {f: {"mark": "guessed" if f == "owners" else "stated"} for f in fields}}))
    cs = clusters(b)
    assert cs["Calls arrive too late"]["governed"] is False and cs["Calls arrive too late"]["missing"] == ["owners"]
    assert "governed" not in cs["No single exposure view"]  # no measures behind it
    (folder / "governed_state.json").write_text(json.dumps({"K1": {f: {"mark": "stated"} for f in fields}}))
    assert clusters(b)["Calls arrive too late"]["governed"] is True and clusters(b)["Calls arrive too late"]["missing"] == []


def test_baseline_id_prefers_the_outcomes_own_baseline_id(tmp_path):
    b = together(tmp_path)
    plane = b.w.plane("co-a")
    path = plane.path("intents", "m2_baseline", "outcomes", "a" * 32 + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"kind": "baseline", "baseline_id": "d" * 32, "signed_at": "2026-01-01T00:00:00+00:00", "signatures": [{"name": "x"}]}))
    assert {c["baseline_id"] for c in clusters(b).values()} == {"d" * 32}
