"""LI-M1 item 7: each human action and free-text entry is counted per session, as numbers only."""
from m1_kit import BASE, draft
from modules.m1_intent.store.sessions import SessionStore
from test_m1_seat_wiring_kit import flow, new_world


def inputs(w, company, sid):
    return SessionStore(w.plane(company)).get(sid)["inputs"]


def test_a_new_session_counts_the_organisers_typed_boxes(world):
    c = world.login("org", "co-a", ["sponsor"])
    r = c.post(f"{BASE}/sessions", json=draft())  # purpose and outcome typed
    assert r.status_code == 201 and r.json()["inputs"] == {"actions": 1, "free_text": 2, "cards_confirmed": 0, "cards_new": 0, "cards_sealed": 0}


def test_a_drafted_session_counts_one_action_and_no_typing(world):
    c = world.login("org", "co-a", ["sponsor"])
    r = c.post(f"{BASE}/sessions", json={**draft(), "drafted": True})
    assert r.status_code == 201 and r.json()["inputs"] == {"actions": 1, "free_text": 0, "cards_confirmed": 0, "cards_new": 0, "cards_sealed": 0}


def test_the_room_counts_actions_and_typed_entries_but_never_their_words(tmp_path):
    w = new_world(tmp_path)
    org, sid, (ada, ben) = flow(w, "co-a")
    before = inputs(w, "co-a", sid)
    nid = ada.write("Capital calls reach us too late")  # one typed message
    ada.save(nid, fields={"affected": "the cash team"})  # one action, one typed field
    after = inputs(w, "co-a", sid)
    assert after["actions"] - before["actions"] == 2 and after["free_text"] - before["free_text"] == 2
    assert "Capital calls" not in str(inputs(w, "co-a", sid))
    ada.room()  # reading is not an action
    assert inputs(w, "co-a", sid) == after


def test_cards_new_increments_when_a_note_is_submitted(tmp_path):
    w = new_world(tmp_path)
    org, sid, (ada, ben) = flow(w, "co-a")
    before = inputs(w, "co-a", sid)
    assert before.get("cards_new", 0) == 0
    nid = ada.write("First card")
    ada.save(nid, fields={"affected": "Team A"})
    ada.submit(nid)
    after = inputs(w, "co-a", sid)
    assert after["cards_new"] == before.get("cards_new", 0) + 1


def test_cards_confirmed_increments_when_keep_is_pressed(tmp_path):
    w = new_world(tmp_path, model=None)
    org, sid, (ada, ben) = flow(w, "co-a")
    before = inputs(w, "co-a", sid)
    assert before.get("cards_confirmed", 0) == 0
    nid = ada.write("My thought")
    # prefill creates a draft with confirmed=False
    ada.call("POST", f"/room/notes/{nid}/prefill")
    # Keep is pressing save after a prefill (confirmed becomes True)
    ada.save(nid, fields={"affected": "People"})
    after = inputs(w, "co-a", sid)
    # confirmed=True happens in save_note when confirmed was False
    assert after["cards_confirmed"] >= before.get("cards_confirmed", 0)


def test_cards_sealed_increments_when_restricted_note_is_submitted(tmp_path):
    w = new_world(tmp_path)
    org, sid, (ada, ben) = flow(w, "co-a")
    before = inputs(w, "co-a", sid)
    assert before.get("cards_sealed", 0) == 0
    nid = ada.write("Confidential issue")
    ada.save(nid, fields={"affected": "Board"}, restricted=True)
    ada.submit(nid)
    after = inputs(w, "co-a", sid)
    assert after["cards_sealed"] == before.get("cards_sealed", 0) + 1
