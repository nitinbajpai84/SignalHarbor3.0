"""LI-M1 items 2 and 3: the interview feeds the private room as North-written note drafts the person keeps, changes or marks
anonymous; North writes note cards from the conversation. D-034 stays: a private room is read by its author only."""
import json

from m1_kit import BASE
from modules.m1_intent.store.notes import NoteStore
from modules.m1_intent.store.sessions import SessionStore
from sh_platform.agents.protocols import ModelReply
from sh_platform.profile import store as profile
from test_m1_briefing_kit import make_world, seated, session_at
from test_m1_seat_wiring_kit import StubNorth, flow, new_world

MEI = {"q1": "Which capital calls to fund each month", "q2": "Capital calls reach us too late, weekly, the cash team is hit",
       "q4": "Rate moves before they hit", "q5": "Move the call notice earlier"}
RAVI = {"q2": "Fee reports differ by manager"}
SPEC = {"mei-tan": MEI, "ravi-shah": RAVI}


def interview(w, company="co-a", people=SPEC, extra=None):
    plane = w.plane(company).ensure()
    for pid, answers in people.items():
        for q, text in answers.items():
            profile.record(plane, f"interviews.{pid}.{q}", {"answer": text, "followups": []},
                           {"mark": "stated", "by": pid, "from": f"Interview with {pid}", "ref": {"kind": "interview", "id": pid}})
    for path, value in (extra or {}).items():
        profile.record(plane, path, value, {"mark": "stated", "by": "x", "from": "test", "ref": {"kind": "interview", "id": "x"}})


def tie(w, pid, account_id, company="co-a"):
    """The profile says which account is this person (people.<pid>.account_id): the only thing besides the account's own display name
    that makes an interview someone's."""
    profile.record(w.plane(company).ensure(), f"people.{pid}.account_id", account_id,
                   {"mark": "stated", "by": "org", "from": "People list", "ref": {"kind": "document", "id": "p1"}})


def room(c, sid):
    r = c.get(f"{BASE}/sessions/{sid}/room")
    assert r.status_code == 200, r.text
    return r.json()


def world_with_two(tmp_path):
    w = make_world(tmp_path)
    interview(w)
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=3)
    mei, ravi = seated(w, "co-a", "Mei Tan"), seated(w, "co-a", "Ravi Shah")
    tie(w, "mei-tan", mei.account_id)
    tie(w, "ravi-shah", ravi.account_id)
    return w, org, sid, mei, ravi


def test_the_interview_answers_arrive_as_drafts_with_their_kinds_in_that_persons_room(tmp_path):
    w, org, sid, mei, ravi = world_with_two(tmp_path)
    notes = {n["text"]: n for n in room(mei, sid)["notes"]}
    assert set(notes) == set(MEI.values())
    assert [notes[MEI[q]]["kind"] for q in ("q1", "q2", "q4", "q5")] == ["intent", "pain_point", "future_signal", "lever"]
    n = notes[MEI["q2"]]
    assert n["state"] == "draft" and n["confirmed"] is False and n["source"]["kind"] == "interview"
    assert n["source"]["from"] == "Interview with Mei Tan"  # every draft names where it came from


def test_a_draft_never_reaches_another_persons_room_or_the_organiser(tmp_path):
    w, org, sid, mei, ravi = world_with_two(tmp_path)
    room(mei, sid)
    theirs = room(ravi, sid)
    assert [n["text"] for n in theirs["notes"]] == [RAVI["q2"]]
    assert "Capital calls" not in json.dumps(theirs)
    assert room(org, sid)["notes"] == []  # the organiser has no interview: no drafts, and cannot read Mei's room
    assert not any("Capital calls" in json.dumps(room(c, sid)) for c in (org, ravi))


def test_a_guest_who_types_a_name_gets_nobody_elses_interview(tmp_path):
    w = new_world(tmp_path)
    interview(w)
    org, sid, (guest,) = flow(w, "co-a", names=("Mei Tan",), seats=2)
    assert guest.room()["notes"] == []  # a name typed at the door proves nothing: only a signed-in person's own interview is used


def test_north_asks_only_about_the_gaps(tmp_path):
    w, org, sid, mei, ravi = world_with_two(tmp_path)
    got = room(mei, sid)
    assert got["interview"]["gaps"] == []  # an intent, a pain point, a future signal and a lever are all drafted
    assert not any(t["role"] == "north" and "Which levers" in t["text"] for t in got["turns"])
    theirs = room(ravi, sid)
    assert [g["kind"] for g in theirs["interview"]["gaps"]] == ["intent", "future_signal", "lever"]
    last = [t for t in theirs["turns"] if t["role"] == "north"][-1]["text"]
    assert "What do you intend to do now" in last and last.count("?") == 1  # one question, the first gap


def test_drafts_are_made_once_and_the_person_keeps_changes_or_marks_one_anonymous(tmp_path):
    w, org, sid, mei, ravi = world_with_two(tmp_path)
    ns = {n["text"]: n["id"] for n in room(mei, sid)["notes"]}
    assert len(room(mei, sid)["notes"]) == 4  # a second visit makes none again
    url = f"{BASE}/sessions/{sid}/room/notes/"
    assert mei.post(url + ns[MEI["q1"]], json={"keep": True}).status_code == 200
    assert mei.post(url + ns[MEI["q2"]], json={"text": "Calls reach the cash team too late"}).status_code == 200
    assert mei.post(url + ns[MEI["q5"]], json={"anonymous": True}).status_code == 200
    got = {n["id"]: n for n in room(mei, sid)["notes"]}
    assert [got[ns[MEI[q]]]["confirmed"] for q in ("q1", "q2", "q4", "q5")] == [True, True, False, True]
    assert got[ns[MEI["q5"]]]["anonymous"] is True and got[ns[MEI["q2"]]]["text"] == "Calls reach the cash team too late"


def test_only_confirmed_drafts_go_to_the_board_when_the_rooms_close(tmp_path):
    w, org, sid, mei, ravi = world_with_two(tmp_path)
    ns = {n["text"]: n["id"] for n in room(mei, sid)["notes"]}
    mei.post(f"{BASE}/sessions/{sid}/room/notes/{ns[MEI['q1']]}", json={"keep": True})
    assert org.post(f"{BASE}/sessions/{sid}/rooms/close").status_code == 200
    shared = [n["text"] for n in NoteStore(w.plane("co-a")).board(sid)]
    assert shared == [MEI["q1"]]  # North's other drafts were never confirmed, so they were never sent


def test_a_restricted_answer_is_not_turned_into_a_draft(tmp_path):
    w = make_world(tmp_path)
    interview(w, people={"mei-tan": {"q2": "Salary data is a mess"}}, extra={"interviews.mei-tan.q2": {"answer": "Salary data is a mess", "followups": [], "restricted": True}})
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=2)
    mei = seated(w, "co-a", "Mei Tan")
    tie(w, "mei-tan", mei.account_id)
    assert room(mei, sid)["notes"] == []


# ---- North writes note cards from the conversation
PROPOSAL = {"notes": [
    {"text": "Calls are paid late", "kind": "pain_point", "fields": {"who": "the cash team", "how_often": "every month", "kpi": "Days to fund"}},
    {"text": "Watch rate moves", "kind": "future_signal", "fields": {"source": "central bank notices"}},
]}


def talk(c, sid, text="Calls are paid late by the cash team every month, we watch days to fund"):
    r = c.post(f"{BASE}/sessions/{sid}/room/messages", json={"text": text, "kind": "answer"})
    assert r.status_code == 200, r.text


def test_north_turns_the_conversation_into_cards_for_the_person_to_confirm(tmp_path):
    w = make_world(tmp_path)
    w.app.state.north_model_factory = lambda plane: StubNorth(PROPOSAL)
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=2)
    c = seated(w, "co-a", "Mei Tan")
    talk(c, sid)
    r = c.post(f"{BASE}/sessions/{sid}/room/notes", json={"from_conversation": True})
    assert r.status_code == 200, r.text
    cards = {n["text"]: n for n in r.json()["notes"]}
    assert set(cards) == {"Calls are paid late", "Watch rate moves"}
    c1 = cards["Calls are paid late"]
    assert (c1["kind"], c1["confirmed"], c1["fields"]) == ("pain_point", False, PROPOSAL["notes"][0]["fields"])
    assert c1["source"]["kind"] == "north" and not {"who", "how_often", "kpi"} & set(c1["missing"])  # the details are filled: nothing to type
    again = c.post(f"{BASE}/sessions/{sid}/room/notes", json={"from_conversation": True}).json()["notes"]
    assert len(again) == 2  # asking again does not repeat a card
    assert c.post(f"{BASE}/sessions/{sid}/room/notes/{c1['id']}", json={"keep": True}).status_code == 200


def test_cards_are_drafts_only_in_the_askers_room_and_the_old_form_still_works(tmp_path):
    w = make_world(tmp_path)
    w.app.state.north_model_factory = lambda plane: StubNorth(PROPOSAL)
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=3)
    mei, ravi = seated(w, "co-a", "Mei Tan"), seated(w, "co-a", "Ravi Shah")
    talk(mei, sid)
    mei.post(f"{BASE}/sessions/{sid}/room/notes", json={"from_conversation": True})
    assert room(ravi, sid)["notes"] == []
    r = ravi.post(f"{BASE}/sessions/{sid}/room/messages", json={"text": "Write it myself", "kind": "note"})  # the old way
    assert r.status_code == 200 and r.json()["notes"][-1]["confirmed"] is None


def test_without_a_model_there_are_no_cards_and_a_plain_message(tmp_path):
    w = make_world(tmp_path)
    w.app.state.north_model_factory = None
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=2)
    c = seated(w, "co-a", "Mei Tan")
    r = c.post(f"{BASE}/sessions/{sid}/room/notes", json={"from_conversation": True})
    assert r.status_code == 200 and r.json()["notes"] == []
    assert "North is not available" in r.json()["cards_message"]


def test_changing_a_draft_in_the_chat_confirms_it(tmp_path):
    w, org, sid, mei, ravi = world_with_two(tmp_path)
    nid = next(n["id"] for n in room(mei, sid)["notes"] if n["text"] == MEI["q2"])
    r = mei.post(f"{BASE}/sessions/{sid}/room/messages", json={"text": "Calls reach cash too late", "kind": "correction", "note_id": nid})
    assert r.status_code == 200, r.text
    assert next(n for n in r.json()["notes"] if n["id"] == nid)["confirmed"] is True

