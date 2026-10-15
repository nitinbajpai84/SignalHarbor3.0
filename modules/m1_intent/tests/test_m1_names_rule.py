"""The organiser decides how names show on notes (Prepare's `names`): named, choice (the default) or anonymous.
One rule, applied where a note's anonymity is set; the rooms' end and the briefing follow it."""
import json

import pytest

from m1_kit import BASE, draft
from modules.m1_intent.domain import notes as N
from modules.m1_intent.domain.preparation import PrepError
from modules.m1_intent.store.notes import NoteStore
from test_m1_briefing_kit import make_world, session_at, use_model
from test_m1_nira import Spy, ask
from test_m1_notes import world
from test_m1_preparation import make
from test_m1_room_kit import guest, hdr, new_session, seat_in, start_room
from test_m1_seat_wiring_kit import Guest


def room_with(w, names=None, seats=3, who="org co-a"):
    org = w.login(who, "co-a", ["sponsor"])
    sid = new_session(org, seats=seats, **({} if names is None else {"names": names}))
    code = start_room(org, sid)
    people = []
    for i, name in enumerate(("Ada Guest", "Ben Guest"), 1):
        token, _ = seat_in(w, guest(w), code, i, name=name)
        people.append(Guest(w, token, sid, name))
    assert org.post(f"{BASE}/sessions/{sid}/briefing").status_code == 200
    assert org.post(f"{BASE}/sessions/{sid}/briefing/send").status_code == 200
    return org, sid, people


# ---- the setting: validated, defaulted, locked
def test_names_defaults_to_choice_and_only_the_three_values_are_valid():
    assert make({"purpose": "x"})["names"] == "choice"
    for v in ("named", "choice", "anonymous"):
        assert make({"purpose": "x", "names": v})["names"] == v
    for bad in ("Named", "", None, True, "everyone"):
        with pytest.raises(PrepError) as e:
            make({"purpose": "x", "names": bad})
        assert e.value.field == "names"


def test_an_old_session_without_the_field_is_choice():
    assert N.names_rule({"purpose": "x"}) == "choice" and N.names_rule(None) == "choice"
    assert N.names_rule({"names": "bogus"}) == "choice"


def test_the_setting_is_saved_with_the_draft_and_locked_once_the_session_starts(tmp_path):
    w = world(tmp_path)
    org = w.login("org co-a", "co-a", ["sponsor"])
    sid = new_session(org, names="named")
    assert org.get(f"{BASE}/sessions/{sid}").json()["preparation"]["names"] == "named"
    assert org.put(f"{BASE}/sessions/{sid}", json={"names": "anonymous"}).json()["preparation"]["names"] == "anonymous"
    assert org.put(f"{BASE}/sessions/{sid}", json={"names": "nobody"}).status_code == 422
    start_room(org, sid)
    r = org.put(f"{BASE}/sessions/{sid}", json={"names": "named"})
    assert r.status_code == 409  # started: read-only
    assert org.get(f"{BASE}/sessions/{sid}").json()["preparation"]["names"] == "anonymous"


# ---- the notes route
def test_named_refuses_an_anonymous_note_and_shows_the_name(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, ben) = room_with(w, "named")
    nid = ada.write("Calls come late")
    assert ada.room()["names"] == "named" and ada.room()["notes"][0]["anonymous"] is False
    r = ada.save(nid, anonymous=True)
    assert r.status_code == 409 and "cannot be anonymous" in r.json()["message"]
    assert ada.save(nid, anonymous=False).status_code == 200
    assert ada.submit(nid).status_code == 200
    [rec] = NoteStore(w.plane("co-a")).board(sid)
    assert rec["anonymous"] is False and rec["author_name"] == "Ada Guest"


def test_anonymous_refuses_a_named_note_and_never_shows_a_name(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, ben) = room_with(w, "anonymous")
    nid = ada.write("Calls come late")
    assert ada.room()["notes"][0]["anonymous"] is True
    r = ada.save(nid, anonymous=False)
    assert r.status_code == 409 and "name cannot be shown" in r.json()["message"]
    ada.submit(nid)
    [rec] = NoteStore(w.plane("co-a")).board(sid)
    assert rec["anonymous"] is True and "author_name" not in json.dumps(rec) and "Ada" not in json.dumps(rec)


def test_choice_and_a_session_without_the_field_work_as_before(tmp_path):
    w = world(tmp_path)
    for names in ("choice", None):
        org, sid, (ada, _) = room_with(w, names, who=f"org {names}")
        nid = ada.write("Calls come late")
        assert ada.room()["names"] == "choice" and ada.save(nid, anonymous=True).status_code == 200
        assert ada.save(nid, anonymous=False).status_code == 200


# ---- the rooms' end and what the board, charter lines and public view show
@pytest.mark.parametrize("names,anon", [("named", False), ("anonymous", True), ("choice", True)])  # choice: never sent, never confirmed (A-045)
def test_the_close_follows_the_mode(tmp_path, names, anon):
    w = world(tmp_path)
    org, sid, (ada, ben) = room_with(w, names)
    ada.write("Calls come late")
    assert org.post(f"{BASE}/sessions/{sid}/rooms/close").status_code == 200
    [rec] = NoteStore(w.plane("co-a")).board(sid)
    assert rec["anonymous"] is anon
    shown = N.public_record(N.load_fields(None), {**rec, "fields": {}})
    assert ("author_name" in shown) is (not anon)
    from modules.m1_intent.domain.board import shown as board_note
    assert ("author_name" in board_note(rec)) is (not anon)


def test_a_legacy_draft_that_contradicts_the_rule_is_corrected_at_the_close(tmp_path):
    from modules.m1_intent.store.notes import submit_drafts
    from modules.m1_intent.store.transcripts import TranscriptStore
    from test_m1_seat_wiring_kit import ids_of
    w = world(tmp_path)
    org, sid, (ada, _) = room_with(w, "named")
    plane, seat = w.plane("co-a"), ids_of(w, "co-a", sid, 1)["seat"]
    ada.write("Old draft")
    TranscriptStore(plane).update(sid, seat, lambda t: t["notes"][0].update(anonymous=True))  # keeps its author's name
    submit_drafts(plane, sid, seat, rooms_end=True)
    [rec] = NoteStore(plane).board(sid)
    assert rec["anonymous"] is False and rec["author_name"] == "Ada Guest"


# ---- what people are told
@pytest.mark.parametrize("names,says,never", [
    ("named", "everyone's name is shown", "stays anonymous"),
    ("anonymous", "no name is ever shown", "your name is shown"),
    ("choice", "you choose whether your name is shown", "no name is ever shown"),
])
def test_the_briefing_and_nira_say_the_true_rule(tmp_path, names, says, never):
    w = make_world(tmp_path)
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", names=names)
    r = org.get(f"{BASE}/sessions/{sid}/briefing")
    assert says in r.text.lower() and never not in r.text.lower()
    spy = use_model(w, Spy())
    assert ask(org, sid, question="Will my notes be anonymous?").status_code == 200
    assert says in json.dumps(spy.context).lower()


def test_nira_s_standing_facts_never_promise_anonymity_unconditionally():
    from modules.m1_intent.agent import nira
    cfg = nira.load_rules()
    facts = " ".join(cfg["privacy_facts"] + cfg["session_facts"])
    assert "Never promise anonymity when notes are open" in facts
    assert "only when the organiser lets each person choose" in facts
