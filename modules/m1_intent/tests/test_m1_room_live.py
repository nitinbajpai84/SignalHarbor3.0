"""Live updates (server-sent events) for the lobby. Copied in idea from the earlier product's live router and its
tests: refused before a byte streams, ends when the token stops working, never carries a token. The client uses
fetch with the X-Session-Token header (EventSource cannot send headers), so every guest stream here uses the header.

A stream has no natural end, so tests either hit routes that refuse before streaming, drive the generator directly
under a deadline, or shorten the stream's lifetime so the HTTP response completes (the lifetime is a module setting).
"""
import asyncio
import json
import threading
import time

import pytest

from m1_kit import BASE
from modules.m1_intent.api import room as room_api
from modules.m1_intent.store.sessions import SessionStore
from test_m1_room_kit import all_text, guest, hdr, join, new_session, seat_in, start_room

VIEW_KEYS = {"session_id", "state", "length_minutes", "is_solo", "organiser", "me", "seats", "arrived", "seat_count"}


@pytest.fixture
def quick(monkeypatch):
    monkeypatch.setattr(room_api, "TICK_SECONDS", 0.05)
    monkeypatch.setattr(room_api, "LIVE_SECONDS", 1.5)


def events(response_text: str) -> list[dict]:
    out = []
    for block in response_text.split("\n\n"):
        if block.startswith("data: "):
            out.append(json.loads(block[len("data: "):]))
    return out


def read_stream(client, url, headers=None) -> tuple[int, str, float]:
    t0 = time.time()
    with client.stream("GET", url, headers=headers or {}) as r:
        text = "".join(r.iter_text())
        return r.status_code, text, time.time() - t0


def later(seconds, fn):
    t = threading.Timer(seconds, fn)
    t.start()
    return t


# ---- refused before streaming ---------------------------------------------------------------------------------------
def test_a_stream_is_refused_before_a_byte_for_no_token_a_wrong_token_and_another_session(world):
    org = world.login("org", "co-a")
    sid, other = new_session(org), new_session(org)
    code = start_room(org, sid)
    start_room(org, other)
    t, _ = seat_in(world, guest(world), code, 1)
    url = f"{BASE}/sessions/{sid}/live"
    assert guest(world).get(url).status_code == 401
    assert guest(world).get(url, headers=hdr("fake-wrong")).status_code == 401
    assert guest(world).get(f"{url}?token={t}").status_code == 401
    assert guest(world).get(f"{BASE}/sessions/{other}/live", headers=hdr(t)).status_code == 404
    assert guest(world).get(f"{BASE}/sessions/{'a' * 32}/live", headers=hdr(t)).status_code == 404


# ---- what a stream carries -------------------------------------------------------------------------------------------
def test_an_arrival_reaches_the_organisers_stream(world, quick):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    later(0.4, lambda: seat_in(world, guest(world), code, 2, name="Late Arrival", role="Buyer"))
    status, text, _ = read_stream(org, f"{BASE}/sessions/{sid}/live")
    got = events(text)
    assert status == 200 and len(got) >= 2
    assert got[0]["arrived"] == 0 and got[-1]["arrived"] == 1
    assert got[-1]["seats"][1]["name"] == "Late Arrival" and got[-1]["organiser"] is True


def test_a_guest_stream_works_with_the_header_and_carries_nothing_secret(world, quick):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), code, 1, name="Ada", role="Planner")
    later(0.4, lambda: seat_in(world, guest(world), code, 2, name="Bo", role="Buyer"))
    later(0.8, lambda: org.post(f"{BASE}/sessions/{sid}/briefing"))
    status, text, _ = read_stream(guest(world), f"{BASE}/sessions/{sid}/live", hdr(t1))
    assert status == 200
    got = events(text)
    assert [e["arrived"] for e in got][0] == 1 and got[-1]["arrived"] == 2  # an arrival
    assert got[0]["state"] == "lobby" and got[-1]["state"] == "briefing"    # a stage change
    for e in got:
        assert set(e) == VIEW_KEYS and e["organiser"] is False and e["me"]["seat"] == 1
        assert all(set(s) <= {"n", "state", "mine", "name", "role"} for s in e["seats"])
    secret = t1.split(".", 1)[1]
    assert t1 not in text and secret not in text and code not in text
    for hidden in ("token", "hash", "account", "participant_id", "co-a"):
        assert hidden not in text, hidden


def test_a_seat_change_reaches_the_guests_stream_and_a_revoked_seat_shows_no_name(world, quick):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), code, 1, name="Ada")
    seat_in(world, guest(world), code, 2, name="Bo")
    later(0.4, lambda: org.post(f"{BASE}/sessions/{sid}/seats/2/revoke"))
    _, text, _ = read_stream(guest(world), f"{BASE}/sessions/{sid}/live", hdr(t1))
    last = events(text)[-1]
    assert last["seats"][1] == {"n": 2, "state": "revoked", "mine": False} and last["arrived"] == 1


def test_a_stream_ends_the_moment_the_seat_is_revoked(world, monkeypatch):
    monkeypatch.setattr(room_api, "TICK_SECONDS", 0.05)
    monkeypatch.setattr(room_api, "LIVE_SECONDS", 6.0)  # far longer than the test may take
    org = world.login("org", "co-a")
    sid = new_session(org)
    code = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), code, 1)
    later(0.4, lambda: org.post(f"{BASE}/sessions/{sid}/seats/1/revoke"))
    status, text, took = read_stream(guest(world), f"{BASE}/sessions/{sid}/live", hdr(t1))
    assert status == 200 and took < 3.0 and len(events(text)) == 1  # one view, then it ended


def test_a_stream_ends_when_the_session_closes(world, monkeypatch):
    monkeypatch.setattr(room_api, "TICK_SECONDS", 0.05)
    monkeypatch.setattr(room_api, "LIVE_SECONDS", 6.0)
    org = world.login("org", "co-a")
    sid = new_session(org)
    code = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), code, 1)

    def close():
        store = SessionStore(world.plane("co-a"))
        for s in ("briefing", "private_rooms", "board", "together", "signing", "closed"):
            store.transition(sid, s)

    later(0.4, close)
    _, text, took = read_stream(guest(world), f"{BASE}/sessions/{sid}/live", hdr(t1))
    assert took < 3.0


def test_a_stream_ends_when_the_module_is_switched_off_for_new_requests_and_reconnect_is_refused(world, quick):
    org = world.login("org", "co-a")
    sid = new_session(org)
    code = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), code, 1)
    world.store.set_module("co-a", "m1_intent", False)
    r = guest(world).get(f"{BASE}/sessions/{sid}/live", headers=hdr(t1))
    assert r.status_code == 403 and r.json()["error"] == "module_not_available"


def test_a_stream_ends_by_itself_after_its_lifetime_so_the_screen_reconnects_and_is_checked_again(world, quick):
    org = world.login("org", "co-a")
    sid = new_session(org)
    start_room(org, sid)
    _, text, took = read_stream(org, f"{BASE}/sessions/{sid}/live")
    assert 1.3 < took < 4.0 and len(events(text)) == 1  # unchanged room: one event, then the stream ends


def test_an_unchanged_room_sends_nothing_new_and_a_change_sends_one_event(monkeypatch):
    monkeypatch.setattr(room_api, "TICK_SECONDS", 0.001)
    monkeypatch.setattr(room_api, "LIVE_SECONDS", 5.0)
    seen = iter([{"n": 1}, {"n": 1}, {"n": 1}, {"n": 2}, {"n": 2}, None])  # None: the viewer may no longer see it

    async def run():
        return [chunk async for chunk in room_api.event_stream(lambda: next(seen))]

    assert asyncio.run(asyncio.wait_for(run(), 10)) == ['data: {"n": 1}\n\n', 'data: {"n": 2}\n\n']


def test_streams_leave_no_secret_behind(world, quick):
    org = world.login("org", "co-a")
    sid = new_session(org)
    code = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), code, 1)
    read_stream(guest(world), f"{BASE}/sessions/{sid}/live", hdr(t1))
    assert t1 not in all_text(world.settings.data_root) and code not in all_text(world.settings.data_root)
