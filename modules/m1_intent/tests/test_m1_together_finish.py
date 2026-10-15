"""Finishing the together stage early: the organiser drafts the charter (the one way the room moves on); a participant
can only signal "I'm done", which the organiser sees as a count. Stub North, synthetic family-office notes."""
from test_m1_board_kit import together


def clusters(b, who=None) -> dict:
    r = b.org_call("GET", "/together") if who is None else who.call("GET", "/together")
    assert r.status_code == 200, r.text
    return {c["name"]: c for c in r.json()["clusters"]}


def tick_all(b):
    for c in clusters(b).values():
        assert b.org_call("POST", f"/together/clusters/{c['id']}/tick", json={"ticked": True}).status_code == 200


def test_the_organiser_ends_the_stage_early_and_the_votes_and_charter_are_intact(tmp_path):
    b = together(tmp_path)
    late = clusters(b)["Calls arrive too late"]["id"]
    b.guests[0].call("POST", f"/together/clusters/{late}/vote", json={"option": "must"})
    tick_all(b)
    before = clusters(b)["Calls arrive too late"]["votes"]
    r = b.org_call("POST", "/charter", json={"confirm": True})
    assert r.status_code == 201 and r.json()["state"] == "signing" and r.json()["charter"]["status"] == "draft"
    assert b.org_call("GET", "/together").json()["stage"] == "signing"
    assert clusters(b)["Calls arrive too late"]["votes"] == before  # the votes are kept
    assert b.guests[0].call("GET", "/together").json()["stage"] == "signing"  # everyone sees the room moved on


def test_a_participant_or_guest_cannot_end_the_stage_and_it_cannot_be_ended_twice(tmp_path):
    b = together(tmp_path)
    tick_all(b)
    for g in b.guests:
        assert g.call("POST", "/charter").status_code in (401, 403)
    assert b.org_call("GET", "/together").json()["stage"] == "together"
    assert b.org_call("POST", "/charter", json={"confirm": True}).status_code == 201
    assert b.org_call("POST", "/charter", json={"confirm": True}).status_code == 409  # already ended: nothing changes


def test_im_done_is_a_signal_the_organiser_counts_and_it_ends_nothing(tmp_path):
    b = together(tmp_path)
    ada, ben = b.guests
    v = b.org_call("GET", "/together").json()
    assert v["done_count"] == 0 and v["people_count"] >= 2
    r = ada.call("POST", "/together/done", json={"done": True})
    assert r.status_code == 200 and r.json()["i_done"] is True
    assert ada.call("POST", "/together/done", json={"done": True}).json()["done_count"] == 1  # one mark per person
    v = b.org_call("GET", "/together").json()
    assert v["done_count"] == 1 and v["i_done"] is False and v["stage"] == "together"
    assert ben.call("GET", "/together").json()["i_done"] is False
    assert ada.call("POST", "/together/done", json={"done": False}).json()["done_count"] == 0
    assert ada.call("POST", "/together/done", json={"done": "yes"}).status_code == 422
    assert ada.call("POST", "/together/done", json={}).status_code == 400
    assert b.org_call("POST", "/together/done", json={"done": True}).status_code in (401, 403)  # the organiser decides instead


def test_im_done_is_refused_once_the_room_has_moved_on(tmp_path):
    b = together(tmp_path)
    tick_all(b)
    b.org_call("POST", "/charter", json={"confirm": True})
    assert b.guests[0].call("POST", "/together/done", json={"done": True}).status_code == 409
