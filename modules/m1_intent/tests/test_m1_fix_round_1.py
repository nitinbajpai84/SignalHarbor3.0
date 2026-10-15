"""LI-M1 fix round 1: B1 (an interview belongs to the account it is tied to, never to a name typed at the door), North card text
checked like a typed note, Prepare drafted only from the sponsor's answers, and the rooms close early when everyone says "I'm done"."""
import json

from fastapi.testclient import TestClient

from m1_kit import BASE
from modules.m1_intent.domain import private_room as R
from sh_platform.profile import store as profile
from test_m1_briefing_kit import make_world, seated, session_at, sit, stage_of
from test_m1_lean_room import MEI, StubNorth, interview, room, talk, tie
from test_m1_room_kit import join, new_session, start_room, guest
from test_m1_seat_wiring_kit import flow, new_world


def named(w, name, company="co-a", roles=("participant",)):
    """A signed-in account whose own display name is exactly `name`."""
    pw = "Fake-test-pass-1234"
    acct = w.accounts.create(f"{name.lower().replace(' ', '-')}@test.invalid", pw, name, company, list(roles))
    c = TestClient(w.app)
    assert c.post("/api/auth/login", json={"email": acct["email"], "password": pw}).status_code == 200
    c.headers["x-csrf-token"] = c.cookies["sh_csrf"]
    c.account_id = acct["account_id"]
    return c


# ---- B1
def test_a_signed_in_person_who_types_another_persons_name_gets_zero_drafts(tmp_path):
    w = make_world(tmp_path)
    interview(w)
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=3)
    eve = w.login("Eve Park", "co-a", ["participant"])
    sit(w, "co-a", sid, eve.account_id, "Mei Tan")  # Eve typed Mei's name at the door
    got = room(eve, sid)
    assert got["notes"] == [] and "Capital calls" not in json.dumps(got)


def test_a_person_whose_profile_entry_is_tied_to_their_account_gets_their_own_interview(tmp_path):
    w = make_world(tmp_path)
    interview(w)
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=3)
    mei = w.login("M. Tan", "co-a", ["participant"])  # a display name that is not the profile's name
    tie(w, "mei-tan", mei.account_id)
    sit(w, "co-a", sid, mei.account_id, "M. Tan")
    assert {n["text"] for n in room(mei, sid)["notes"]} == set(MEI.values())


def test_an_account_whose_own_display_name_is_the_profile_persons_gets_nothing_without_a_link(tmp_path):
    w = make_world(tmp_path)
    interview(w)
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=3)
    mei = named(w, "Mei Tan")
    sit(w, "co-a", sid, mei.account_id, "Whatever Was Typed")
    assert room(mei, sid)["notes"] == []  # a name is never enough (A-043)


def test_a_link_to_another_account_never_gives_the_caller_drafts(tmp_path):
    w = make_world(tmp_path)
    interview(w)
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=3)
    real = w.login("Mei Real", "co-a", ["participant"])
    tie(w, "mei-tan", real.account_id)
    namesake = named(w, "Mei Tan")  # same display name, a different account
    sit(w, "co-a", sid, namesake.account_id, "Mei Tan")
    assert room(namesake, sid)["notes"] == []


def test_the_door_refuses_a_name_of_a_profile_person_tied_to_a_different_account(tmp_path):
    w = new_world(tmp_path)
    interview(w)
    org = w.login("org", "co-a", ["sponsor"])
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    real = w.login("Mei Real", "co-a", ["participant"])
    tie(w, "mei-tan", real.account_id)
    profile.record(w.plane("co-a").ensure(), "people.mei-tan.name", "Mei Tan",
                   {"mark": "stated", "by": "org", "from": "People list", "ref": {"kind": "document", "id": "p1"}})
    eve = w.login("Eve Park", "co-a", ["participant"])
    for who in (eve, guest(w)):
        r = join(who, code, 1, name="Mei Tan")
        assert r.status_code in (409, 422), r.text
        assert r.json()["error"] == "name_bound" and "someone else" in r.json()["message"]
        assert "mei-tan" not in r.text and real.account_id not in r.text
    assert join(real, code, 1, name="Mei Tan").status_code == 200  # the tied account itself may use it
    assert join(guest(w), code, 2, name="Eve Park").status_code == 200  # an untied name is untouched


# ---- North's card text
def test_a_card_is_capped_and_checked_like_a_typed_note(tmp_path):
    w = make_world(tmp_path)
    long_text = "Calls are late " * 400
    bad = {"notes": [{"text": long_text, "kind": "pain_point"},
                     {"text": "Fine card", "kind": "lever"}]}
    w.app.state.north_model_factory = lambda plane: StubNorth(bad)
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=2)
    c = seated(w, "co-a", "Mei Tan")
    talk(c, sid)
    notes = c.post(f"{BASE}/sessions/{sid}/room/notes", json={"from_conversation": True}).json()["notes"]
    texts = [n["text"] for n in notes]
    assert "Fine card" in texts and not any("​" in t for t in texts)
    assert all(len(t) <= R.MAX_MESSAGE_CHARS for t in texts) and len(texts) == 2


# ---- Prepare: only the sponsor's own answers
def _seed_people(w, with_sponsor_answer):
    from test_m1_lean_prefill import put
    plane = w.plane("co-a").ensure()
    for pid, name, sponsor in (("sue-sponsor", "Sue Sponsor", True), ("aaron-lyle", "Aaron Lyle", False)):
        put(plane, f"people.{pid}.name", name, frm="People list", kind="document")
        if sponsor:
            put(plane, f"people.{pid}.is_sponsor", True, frm="People list", kind="document")
    put(plane, "interviews.aaron-lyle.q1", {"answer": "Which exposures to cut each month", "followups": []}, by="Aaron Lyle",
        frm="Interview with Aaron Lyle", agent=None, kind="interview")
    put(plane, "interviews.aaron-lyle.q13", {"answer": "Exposure is one view", "followups": []}, by="Aaron Lyle",
        frm="Interview with Aaron Lyle", agent=None, kind="interview")
    if with_sponsor_answer:
        put(plane, "interviews.sue-sponsor.q1", {"answer": "Plan the family's capital calls", "followups": []}, by="Sue Sponsor",
            frm="Interview with Sue Sponsor", agent=None, kind="interview")


def test_purpose_and_outcome_never_come_from_a_person_who_is_not_the_sponsor(world):
    _seed_people(world, with_sponsor_answer=False)
    f = world.login("org", "co-a", ["sponsor"]).get(f"{BASE}/lists").json()["profile_draft"]["fields"]
    assert "purpose" not in f and "outcome" not in f
    assert "Aaron" not in json.dumps({k: v for k, v in f.items() if k in ("purpose", "outcome")})


def test_the_purpose_comes_from_the_sponsors_answer_with_its_source(world):
    _seed_people(world, with_sponsor_answer=True)
    f = world.login("org", "co-a", ["sponsor"]).get(f"{BASE}/lists").json()["profile_draft"]["fields"]
    assert f["purpose"] == {"value": "Plan the family's capital calls", "source": "Interview with Sue Sponsor"}
    assert "outcome" not in f


# ---- the rooms close early when everyone is done
def test_everyone_done_closes_the_private_rooms_early(tmp_path):
    w = new_world(tmp_path)
    org, sid, (ada, ben) = flow(w, "co-a")
    assert ada.call("POST", "/room/done", json={"done": True}).status_code == 200
    assert stage_of(org, sid) == "private_rooms"  # one of two is not everyone
    r = ben.call("POST", "/room/done", json={"done": True})
    assert r.status_code == 200, r.text
    assert stage_of(org, sid) == "board"


def test_taking_done_back_and_the_organiser_closing_still_work(tmp_path):
    w = new_world(tmp_path)
    org, sid, (ada, ben) = flow(w, "co-a")
    ada.call("POST", "/room/done", json={"done": True})
    ada.call("POST", "/room/done", json={"done": False})
    ben.call("POST", "/room/done", json={"done": True})
    assert stage_of(org, sid) == "private_rooms"
    assert org.post(f"{BASE}/sessions/{sid}/rooms/close").status_code == 200
    assert stage_of(org, sid) == "board"


def test_room_done_is_for_seated_participants_in_the_rooms_stage_only(tmp_path):
    w = new_world(tmp_path)
    org, sid, (ada, ben) = flow(w, "co-a")
    assert ada.call("POST", "/room/done", json={"done": "yes"}).status_code == 400
    assert org.post(f"{BASE}/sessions/{sid}/room/done", json={"done": True}).status_code == 403  # the organiser decides, as in together
    stranger = guest(w)
    assert stranger.post(f"{BASE}/sessions/{sid}/room/done", json={"done": True}).status_code in (401, 403, 404)
    other = new_world(tmp_path / "other")
    lobby_org, lobby_sid, (late,) = flow(other, "co-a", names=("Ada Guest",), stage="lobby")
    assert late.call("POST", "/room/done", json={"done": True}).status_code == 409  # the rooms are not open
