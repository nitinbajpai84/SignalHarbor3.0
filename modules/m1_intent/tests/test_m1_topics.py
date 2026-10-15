"""IC-2t: a company runs several walls, one per topic or department. Synthetic family office."""
from m1_kit import BASE, draft
from sh_platform.profile import Viewer, read
from test_m1_seat_wiring_kit import StubNorth, flow, new_world

ADMIN = Viewer("Root", frozenset({"company_admin"}))


def make(c, **over):
    over.setdefault("topic", None)  # the shared draft() gives every test its own topic; this file tests the bare case too
    r = c.post(f"{BASE}/sessions", json=draft(**over))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_topic_is_checked_and_defaults_to_none(world):
    c = world.login("org", "co-a")
    assert c.get(f"{BASE}/sessions/{make(c)}").json()["preparation"]["topic"] is None
    sid = make(c, topic="  Treasury: capital calls ")
    assert c.get(f"{BASE}/sessions/{sid}").json()["preparation"]["topic"] == "Treasury: capital calls"
    r = c.post(f"{BASE}/sessions", json=draft(topic="x" * 61))
    assert r.status_code == 422 and r.json()["field"] == "topic"
    assert c.post(f"{BASE}/sessions", json=draft(topic=5)).status_code == 422
    assert c.get(f"{BASE}/sessions").json()[0]["topic"] in ("Treasury: capital calls", None)


def test_two_walls_open_at_once_each_with_a_topic(world):
    c = world.login("org", "co-a")
    a, b = make(c, topic="Treasury: capital calls"), make(c, topic="Investment committee: performance")
    assert c.post(f"{BASE}/sessions/{a}/start").status_code == 201
    assert c.post(f"{BASE}/sessions/{b}/start").status_code == 201
    topics = {x["topic"] for x in c.get(f"{BASE}/walls").json()["walls"]}
    assert topics == {"Treasury: capital calls", "Investment committee: performance"}


def test_a_second_wall_needs_a_topic_and_a_topic_cannot_open_twice(world):
    c = world.login("org", "co-a")
    first, bare, same = make(c), make(c), make(c, topic="Treasury")
    assert c.post(f"{BASE}/sessions/{first}/start").status_code == 201  # the only wall: no topic needed
    r = c.post(f"{BASE}/sessions/{bare}/start")
    assert r.status_code == 409 and "topic" in r.json()["message"]
    other = make(c, topic="treasury")
    assert c.post(f"{BASE}/sessions/{same}/start").status_code == 201
    r = c.post(f"{BASE}/sessions/{other}/start")
    assert r.status_code == 409 and "already open" in r.json()["message"]


def test_walls_list_counts_and_roles_and_company_walls(tmp_path):
    w = new_world(tmp_path, StubNorth({}))
    org, sid, (ada, ben) = flow(w, prep={"topic": "Treasury: capital calls"})
    for g, text in ((ada, "Calls arrive late"), (ada, "No owner for the cash file"), (ben, "Exposure is in three sheets")):
        nid = g.write(text)
        g.save(nid, kind="pain_point")
        assert g.submit(nid).status_code == 200
    row = org.get(f"{BASE}/walls").json()["walls"][0]
    assert (row["id"], row["topic"], row["state"], row["cards_count"], row["people_count"]) == (sid, "Treasury: capital calls", "private_rooms", 3, 2)
    assert row["purpose"]
    assert w.login("other-org", "co-a", ["analyst"]).get(f"{BASE}/walls").json()["walls"][0]["id"] == sid  # the company's, not one organiser's
    assert w.login("p", "co-a", ["participant"]).get(f"{BASE}/walls").status_code == 403
    assert w.login("b", "co-b", ["sponsor"]).get(f"{BASE}/walls").json() == {"walls": []}
    cards = read(w.plane("co-a"), ADMIN)["cards"]
    assert {c["topic"]["value"] for c in cards.values()} == {"Treasury: capital calls"} and len(cards) == 3


def test_an_anonymous_card_carries_the_topic_but_not_the_author(tmp_path):
    w = new_world(tmp_path, StubNorth({}))
    org, sid, (ada, _) = flow(w, prep={"topic": "Treasury"})
    nid = ada.write("Nobody owns it")
    ada.save(nid, anonymous=True)
    ada.submit(nid)
    c = read(w.plane("co-a"), ADMIN)["cards"][nid]
    assert c["topic"]["value"] == "Treasury" and "Ada" not in str(c)


def test_together_view_serves_the_topic(tmp_path):
    from test_m1_board_kit import together
    b = together(tmp_path, prep={"topic": "Treasury"})
    assert b.org_call("GET", "/together").json()["topic"] == "Treasury"
