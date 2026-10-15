"""D6: the organiser can free a taken seat before the rooms open (revoke with reopen=1); the person rejoins with the link."""
import json

from m1_kit import BASE
from modules.m1_intent.store.sessions import SessionStore
from test_m1_room_kit import guest, join, lobby, new_session, seat_in, start_room


def test_freeing_a_seat_stops_the_old_token_and_lets_the_person_rejoin_with_the_link(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), code, 1, name="Ada")
    r = org.post(f"{BASE}/sessions/{sid}/seats/1/revoke?reopen=1")
    assert r.status_code == 200 and r.json()["seats"][0]["state"] == "free" and r.json()["arrived"] == 0
    assert "Ada" not in json.dumps(lobby(org, sid).json())
    assert lobby(guest(world), sid, t1).status_code == 401  # the old token is dead at once
    back = join(guest(world), code, 1, name="Ada")  # same name, same seat, new browser
    assert back.status_code == 200 and back.json()["me"]["seat"] == 1


def test_a_seat_can_no_longer_be_freed_once_the_rooms_are_open(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=2)
    code = start_room(org, sid)
    seat_in(world, guest(world), code, 1, name="Ada")
    store = SessionStore(world.plane("co-a"))
    for s in ("briefing", "private_rooms"):
        store.transition(sid, s)
    r = org.post(f"{BASE}/sessions/{sid}/seats/1/revoke?reopen=1")
    assert r.status_code == 409
    assert org.get(f"{BASE}/sessions/{sid}/lobby").json()["seats"][0]["state"] == "taken"
