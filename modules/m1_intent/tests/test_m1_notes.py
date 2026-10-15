"""M1-11 the note form, M1-16 notes only in the rooms, submitting is the person's act. Stub North."""
import shutil

import pytest
import yaml

from m1_kit import BASE
from modules.m1_intent.domain.contracts import DEFAULT_DIR
from modules.m1_intent.store.notes import NoteStore
from test_m1_seat_wiring_kit import StubNorth, flow, new_world

PROPOSAL = {"purpose": "Keep customers", "affected": "Account managers", "size": "Monthly, about a tenth",
            "data_guess": "The billing spreadsheet", "labels": ["renewals", "billing"], "belief": "40"}


def world(tmp_path, proposal=None):
    return new_world(tmp_path, StubNorth(proposal if proposal is not None else PROPOSAL))


def test_the_form_comes_from_the_contract_and_follows_a_change_to_the_file(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, _) = flow(w)
    ids = [f["id"] for f in ada.room()["form"]]
    assert ids == ["problem", "purpose", "affected", "size", "belief", "data_guess", "labels"]
    folder = tmp_path / "contracts"
    shutil.copytree(DEFAULT_DIR, folder)
    data = yaml.safe_load((folder / "note_fields.yaml").read_text())
    data["fields"].append({"id": "owner", "label": "Who owns it", "kind": "text"})
    (folder / "note_fields.yaml").write_text(yaml.safe_dump(data))
    w.app.state.m1_contracts_dir = folder
    assert [f["id"] for f in ada.room()["form"]][-1] == "owner"
    nid = ada.write()
    assert ada.save(nid, fields={"owner": "Pat"}).json()["notes"][0]["fields"]["owner"] == "Pat"
    assert ada.save(nid, fields={"colour": "red"}).status_code == 422  # not in the contract: refused


def test_north_prefills_what_is_empty_asks_only_for_the_rest_and_never_proposes_the_belief_number(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, _) = flow(w)
    nid = ada.write()
    note = ada.call("POST", f"/room/notes/{nid}/prefill").json()["notes"][0]
    assert note["fields"]["purpose"] == "Keep customers" and note["fields"]["data_guess"] == "The billing spreadsheet"
    assert "belief" not in note["fields"] and note["missing"] == ["belief", "labels"]  # North asks only for these
    assert note["labels_suggested"] == ["renewals", "billing"] and "labels" not in note["fields"]


def test_a_person_value_is_never_replaced_by_a_prefill(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, _) = flow(w)
    nid = ada.write()
    ada.save(nid, fields={"purpose": "My own purpose"})
    note = ada.call("POST", f"/room/notes/{nid}/prefill").json()["notes"][0]
    assert note["fields"]["purpose"] == "My own purpose"


def test_the_belief_number_comes_only_from_the_person(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, _) = flow(w)
    nid = ada.write()
    ada.call("POST", f"/room/notes/{nid}/prefill")
    assert "belief" not in ada.room()["notes"][0]["fields"]
    assert ada.save(nid, fields={"belief": 35}).json()["notes"][0]["fields"]["belief"] == 35
    for bad in ("forty", True, [1]):
        assert ada.save(nid, fields={"belief": bad}).status_code in (422, 400)
    assert ada.room()["notes"][0]["fields"]["belief"] == 35


def test_labels_count_only_once_the_person_confirms_them(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, _) = flow(w)
    nid = ada.write()
    ada.call("POST", f"/room/notes/{nid}/prefill")
    assert ada.submit(nid).status_code == 200
    rec = NoteStore(w.plane("co-a")).board(sid)[0]
    assert "labels" not in rec["fields"]  # suggested, never confirmed
    nid2 = ada.write("Second")
    ada.call("POST", f"/room/notes/{nid2}/prefill")
    ada.save(nid2, fields={"labels": ["renewals"]})
    ada.submit(nid2)
    recs = {r["text"]: r for r in NoteStore(w.plane("co-a")).board(sid)}
    assert recs["Second"]["fields"]["labels"] == ["renewals"]


def test_where_the_data_might_be_is_stored_as_a_guess(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, _) = flow(w)
    form = {f["id"]: f for f in ada.room()["form"]}
    assert form["data_guess"]["guess"] is True and form["belief"]["person_only"] is True
    nid = ada.write()
    ada.save(nid, fields={"data_guess": "maybe the warehouse"})
    assert ada.room()["notes"][0]["fields"]["data_guess"] == "maybe the warehouse"


def test_an_unsubmitted_note_stays_private_and_submitting_is_the_persons_act(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, ben) = flow(w)
    nid = ada.write("private draft words")
    assert NoteStore(w.plane("co-a")).board(sid) == []  # a draft is nowhere shared
    assert "private draft" not in ben.room().__str__() and ben.submit(nid).status_code == 404  # not Ben's to submit
    assert NoteStore(w.plane("co-a")).board(sid) == []
    assert ada.submit(nid).status_code == 200
    assert [n["text"] for n in NoteStore(w.plane("co-a")).board(sid)] == ["private draft words"]


def test_a_submitted_note_is_read_only_and_submitting_twice_is_harmless(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, _) = flow(w)
    nid = ada.write()
    ada.submit(nid)
    assert ada.submit(nid).status_code == 200 and len(NoteStore(w.plane("co-a")).board(sid)) == 1
    assert ada.save(nid, text="changed").status_code == 422
    assert ada.save(nid, anonymous=True).status_code == 422
    assert ada.call("POST", "/room/messages", json={"text": "fix", "kind": "correction", "note_id": nid}).status_code == 422


def test_notes_are_refused_outside_the_private_rooms(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, _) = flow(w, stage="private_rooms")
    nid = ada.write()
    sess = w.plane("co-a")
    from modules.m1_intent.store.sessions import SessionStore
    SessionStore(sess).transition(sid, "board")
    assert ada.submit(nid).status_code == 409 and ada.save(nid, text="late").status_code == 409
    org2, sid2, (ben, _) = flow(w, org_name="org two", stage="briefing")
    assert ben.call("POST", "/room/messages", json={"text": "early", "kind": "note"}).status_code == 409


def test_a_note_in_the_wrong_shape_is_refused_in_plain_words(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, _) = flow(w)
    nid = ada.write()
    for body in ({}, {"fields": []}, {"anonymous": "yes"}, {"fields": {"labels": "x"}}, {"fields": {"purpose": "x" * 500}},
                 {"fields": {"labels": [f"l{i}" for i in range(9)]}}, {"who": "me"}, {"restricted": "yes"}, {"restricted": 1}):
        r = ada.save(nid, **body)
        assert r.status_code in (400, 422) and "Traceback" not in r.text
    assert ada.save("e" * 16, text="x").status_code == 404


def test_a_model_that_cannot_answer_leaves_the_form_to_the_person(tmp_path):
    w = world(tmp_path)
    w.app.state.north_model_factory = lambda plane: None
    org, sid, (ada, _) = flow(w)
    nid = ada.write()
    r = ada.call("POST", f"/room/notes/{nid}/prefill")
    assert r.status_code == 200 and r.json()["notes"][0]["fields"] == {}


# ---- closing the rooms submits only real notes (defect 4 of the critic run)
def _close(org, sid):
    assert org.post(f"{BASE}/sessions/{sid}/rooms/close").status_code == 200


def test_closing_the_rooms_submits_every_note_once_including_one_phrased_as_a_question(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, ben) = flow(w)
    ada.write("Calls come late")
    ada.write("Can we trust the consolidated picture?")  # a real note phrased as a question (critic fix C review)
    ada.write("  calls  come LATE ")            # the same words again: a retried turn
    kept = ada.write("Fees are not compared")
    ada.save(kept, anonymous=True)               # its choice is kept
    ben.write("Calls come late")                 # another person's identical words are their own note
    _close(org, sid)
    board = NoteStore(w.plane("co-a")).board(sid)
    assert sorted((n["text"], n["anonymous"]) for n in board) == [
        ("Calls come late", True), ("Calls come late", True), ("Can we trust the consolidated picture?", True),
        ("Fees are not compared", True)]  # never sent, never confirmed: anonymous where each person chooses (A-045)
    assert all("author_name" not in n for n in board if n["anonymous"])


def test_a_note_the_person_submitted_is_not_submitted_again_by_a_repeat_at_close(tmp_path):
    w = world(tmp_path)
    org, sid, (ada, _) = flow(w)
    ada.submit(ada.write("Calls come late"))
    ada.write("Calls come late")
    _close(org, sid)
    assert [n["text"] for n in NoteStore(w.plane("co-a")).board(sid)] == ["Calls come late"]


def test_a_note_with_no_choice_follows_the_sessions_names_rule_and_a_choice_wins(tmp_path):
    from modules.m1_intent.store.notes import submit_drafts
    from modules.m1_intent.store.transcripts import TranscriptStore
    from test_m1_seat_wiring_kit import ids_of
    from test_m1_names_rule import room_with
    w = world(tmp_path)
    org, sid, (ada, _) = room_with(w, "anonymous")   # the organiser chose anonymous in Prepare
    plane, seat = w.plane("co-a"), ids_of(w, "co-a", sid, 1)["seat"]
    ada.write("No choice yet")
    # an older draft that carries a choice of its own is the session's rule's to correct at the rooms' end
    submit_drafts(plane, sid, seat, rooms_end=True)
    got = {n["text"]: n["anonymous"] for n in NoteStore(plane).board(sid)}
    assert got == {"No choice yet": True}
    assert TranscriptStore(plane).load(sid, seat)["notes"][0]["anonymous"] is True
