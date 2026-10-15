"""A note submitted in the private room also becomes a card on the wall (profile `cards`), two companies kept apart."""
from modules.m1_intent.store.notes import _card
from sh_platform.profile import Viewer, read
from test_m1_seat_wiring_kit import StubNorth, flow, new_world

ADMIN = Viewer("Root", frozenset({"company_admin"}))


def cards(w, company):
    return read(w.plane(company), ADMIN)["cards"]


def test_a_submitted_note_writes_a_card_with_provenance(tmp_path):
    w = new_world(tmp_path, StubNorth({}))
    org, sid, (ada, _) = flow(w)
    nid = ada.write("Renewals slip every month")
    ada.save(nid, kind="pain_point")
    assert cards(w, "co-a") == {}  # a draft is not a card
    assert ada.submit(nid).status_code == 200
    c = cards(w, "co-a")[nid]
    assert c["lane"]["value"] == "missing" and c["q1"]["value"] == "Renewals slip every month" and c["q1"]["mark"] == "stated"
    assert c["anonymous"]["value"] is False and c["sealed"]["value"] is False and c["room"]["value"] == sid


def test_an_anonymous_note_is_an_anonymous_card_with_no_author_and_other_companies_see_none(tmp_path):
    w = new_world(tmp_path, StubNorth({}))
    org, sid, (ada, _) = flow(w)
    nid = ada.write("Nobody owns the exposure file")
    ada.save(nid, anonymous=True)
    ada.submit(nid)
    c = cards(w, "co-a")[nid]
    assert c["anonymous"]["value"] is True and "author" not in c and "Ada" not in str(c)
    assert c["q1"]["by"] == "anonymous"
    flow(w, company="co-b")
    assert cards(w, "co-b") == {}


def test_restricted_and_quarters_come_from_the_note():
    n = {"id": "ab12", "text": "x", "kind": "lever", "restricted": True, "anonymous": False, "author_name": "Ada Guest",
         "quarters": {"q1": "a", "q2": "b"}}
    c = _card(n, "s1")
    assert c["sealed"] is True and c["lane"] == "levers" and (c["q1"], c["q2"], c["q3"]) == ("a", "b", None) and c["author"] == "ada-guest"
