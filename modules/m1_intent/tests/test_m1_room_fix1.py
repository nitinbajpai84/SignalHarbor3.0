"""M1-P02 fix round 1 (security): live streams re-checked on every tick, join body limits, one seat per account under
concurrency, closed-session join, no secret in any response, a clean referrer on the join page. Each test fails if the
check it names is removed. Tokens and codes are made at run time."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from m1_kit import BASE
from modules.m1_intent.api import room as room_api
from modules.m1_intent.domain import room as R
from modules.m1_intent.store.room import RoomStore
from modules.m1_intent.store.sessions import SessionStore
from test_m1_room_kit import guest, hdr, join, lobby, new_session, seat_in, start_room
from test_m1_room_live import events, later, read_stream

LONG = ("briefing", "private_rooms", "board", "together", "signing", "closed")
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def slow(monkeypatch):
    """A stream that would live far longer than any test, checked fast."""
    monkeypatch.setattr(room_api, "TICK_SECONDS", 0.05)
    monkeypatch.setattr(room_api, "LIVE_SECONDS", 8.0)


# ---- B1: a stream is checked again on every tick ------------------------------------------------------------------
def test_a_guest_stream_ends_when_the_module_is_switched_off_mid_stream(world, slow):
    org = world.login("org", "co-a")
    sid = new_session(org)
    code = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), code, 1)
    later(0.4, lambda: world.store.set_module("co-a", "m1_intent", False))
    status, text, took = read_stream(guest(world), f"{BASE}/sessions/{sid}/live", hdr(t1))
    assert status == 200 and took < 3.0 and len(events(text)) == 1


def test_the_organisers_stream_ends_when_the_module_is_switched_off_mid_stream(world, slow):
    org = world.login("org", "co-a")
    sid = new_session(org)
    start_room(org, sid)
    later(0.4, lambda: world.store.set_module("co-a", "m1_intent", False))
    status, text, took = read_stream(org, f"{BASE}/sessions/{sid}/live")
    assert status == 200 and took < 3.0 and len(events(text)) == 1


def _twin(world, c: TestClient) -> TestClient:
    """The same browser (same cookies) as another client, so a second request can run while one streams."""
    t = TestClient(world.app)
    t.cookies.update(c.cookies)
    t.headers["x-csrf-token"] = c.headers["x-csrf-token"]
    return t


def test_the_organisers_stream_ends_at_logout(world, slow):
    org = world.login("org", "co-a")
    sid = new_session(org)
    start_room(org, sid)
    other_tab = _twin(world, org)
    later(0.4, lambda: other_tab.post("/api/auth/logout"))
    status, text, took = read_stream(org, f"{BASE}/sessions/{sid}/live")
    assert status == 200 and took < 3.0 and len(events(text)) == 1


def test_the_organisers_stream_ends_when_the_account_is_disabled(world, slow):
    org = world.login("org", "co-a")
    sid = new_session(org)
    start_room(org, sid)

    def disable():
        rows = world.accounts._read()
        world.accounts._write([{**a, "disabled": True} if a["account_id"] == org.account_id else a for a in rows])

    later(0.4, disable)
    status, text, took = read_stream(org, f"{BASE}/sessions/{sid}/live")
    assert status == 200 and took < 3.0 and len(events(text)) == 1


def test_a_stream_does_not_keep_an_idle_session_alive(world, slow, monkeypatch):
    """The stream's own checks must not refresh the idle timer (that would make a session immortal)."""
    org = world.login("org", "co-a")
    sid = new_session(org)
    start_room(org, sid)
    sessions, calls = world.app.state.sessions, []
    real = sessions.resolve
    monkeypatch.setattr(room_api, "LIVE_SECONDS", 1.0)  # about twenty ticks
    monkeypatch.setattr(sessions, "resolve", lambda cookie: calls.append(1) or real(cookie))
    read_stream(org, f"{BASE}/sessions/{sid}/live")
    assert len(calls) <= 4  # the request itself (a few layers), never once per tick


# ---- join: JSON only and a small body -------------------------------------------------------------------------------
def test_join_wants_json_and_refuses_another_content_type(world):
    org = world.login("org", "co-a")
    code = start_room(org, new_session(org))
    body = ('{"code": "%s"}' % code).encode()
    for ctype in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data"):
        r = guest(world).post(f"{BASE}/join", content=body, headers={"Content-Type": ctype})
        assert r.status_code == 415 and code not in r.text, ctype
    r = guest(world).post(f"{BASE}/join", content=body)  # no content type at all
    assert r.status_code == 415
    ok = guest(world).post(f"{BASE}/join", content=body, headers={"Content-Type": "application/json; charset=utf-8"})
    assert ok.status_code == 200


def test_join_refuses_a_body_over_the_limit_declared_or_streamed(world):
    org = world.login("org", "co-a")
    code = start_room(org, new_session(org))
    big = ('{"code": "%s", "name": "%s"}' % (code, "x" * 5000)).encode()
    head = {"Content-Type": "application/json"}
    declared = guest(world).post(f"{BASE}/join", content=big, headers=head)
    assert declared.status_code == 413 and code not in declared.text

    def chunks():  # no Content-Length: a chunked body
        for i in range(0, len(big), 500):
            yield big[i:i + 500]

    streamed = guest(world).post(f"{BASE}/join", content=chunks(), headers=head)
    assert streamed.status_code == 413
    just_ok = ('{"code": "%s", "pad": "%s"}' % (code, "x" * 3000)).encode()
    assert guest(world).post(f"{BASE}/join", content=just_ok, headers=head).status_code == 200


# ---- take: one seat per account, even under a race -----------------------------------------------------------------
def test_five_concurrent_joins_from_one_account_take_one_seat(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=5)
    start_room(org, sid)
    plane = world.plane("co-a")
    gate = Barrier(5)

    def go(n):
        gate.wait()
        return RoomStore(plane).take(sid, n, "Olive", "Owner", org.account_id)

    with ThreadPoolExecutor(5) as pool:
        results = list(pool.map(go, range(1, 6)))
    assert {seat["n"] for seat, _ in results} == {results[0][0]["n"]}  # everybody got the same seat
    assert all(token is None for _, token in results)
    room = RoomStore(plane).get(sid)
    assert [s["state"] for s in room["seats"]].count("taken") == 1


def test_the_api_returns_the_existing_seat_for_an_account_that_races_itself(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=5)
    code = start_room(org, sid)
    twins = [_twin(world, org) for _ in range(5)]
    gate = Barrier(5)

    def go(i):
        gate.wait()
        return join(twins[i], code, i + 1, name="Olive", role="Owner")

    with ThreadPoolExecutor(5) as pool:
        rs = list(pool.map(go, range(5)))
    assert all(r.status_code == 200 and r.json()["token"] is None for r in rs)
    assert len({r.json()["me"]["seat"] for r in rs}) == 1
    assert lobby(org, sid).json()["arrived"] == 1


# ---- take: closed session, directly and in a race ---------------------------------------------------------------------
def test_take_refuses_a_closed_session_itself(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=2)
    start_room(org, sid)
    for s in LONG:
        SessionStore(world.plane("co-a")).transition(sid, s)
    with pytest.raises(R.RoomError) as e:
        RoomStore(world.plane("co-a")).take(sid, 1, "Late", "Buyer", None)
    assert e.value.code == "link_closed"
    assert all(s["state"] == "free" for s in RoomStore(world.plane("co-a")).get(sid)["seats"])


def test_closing_and_joining_at_once_never_seats_anyone_in_a_closed_session(world, monkeypatch):
    org = world.login("org", "co-a")
    plane = world.plane("co-a")
    seen: list[str] = []
    real_save = RoomStore._save

    def watching(self, room):
        seen.append(self.sessions.get(room["session_id"])["state"])  # the state at the moment a seat is written
        real_save(self, room)

    monkeypatch.setattr(RoomStore, "_save", watching)
    for _ in range(25):  # many small races: one close against ten joins
        sid = new_session(org, seats=10)
        start_room(org, sid)
        seen.clear()
        gate = Barrier(11)

        def close():
            gate.wait()
            for s in LONG:
                SessionStore(plane).transition(sid, s)

        def take(n):
            gate.wait()
            try:
                RoomStore(plane).take(sid, n, f"P{n}", "Role", None)
            except R.RoomError:
                pass

        closer = threading.Thread(target=close)
        closer.start()
        with ThreadPoolExecutor(10) as pool:
            list(pool.map(take, range(1, 11)))
        closer.join()
        assert "closed" not in seen, "a seat was written after the session closed"

# ---- a token in a cookie is never a token (each cookie name on its own) ---------------------------------------------
@pytest.mark.parametrize("name", ["x-session-token", "X-Session-Token", "x_session_token", "sh_session", "token"])
def test_a_token_in_a_cookie_of_any_name_is_refused_on_its_own(world, name):
    org = world.login("org", "co-a")
    sid = new_session(org)
    t1, _ = seat_in(world, guest(world), start_room(org, sid), 1)
    g = guest(world)
    g.cookies.set(name, t1)
    for path in ("lobby", "live"):
        assert g.get(f"{BASE}/sessions/{sid}/{path}").status_code == 401, path
    assert g.get(f"{BASE}/sessions/{sid}/lobby", headers=hdr(t1)).status_code == 200  # the header is what counts


# ---- the answers carry only what the screen needs -------------------------------------------------------------------
JOIN_KEYS = {"session_id", "state", "signed_in", "length_minutes", "token", "me", "seats"}
ME_KEYS = {"seat", "name", "role", "late", "see_briefing_first"}
LOBBY_KEYS = {"session_id", "state", "length_minutes", "is_solo", "organiser", "me", "seats", "arrived", "seat_count"}


def test_no_answer_carries_a_hash_or_any_field_beyond_the_screens_own(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=4)
    code = start_room(org, sid)
    g = guest(world)
    look = join(g, code).json()
    mine = join(g, code, 1, name="Ada", role="Planner")
    t1 = mine.json()["token"]
    for body in (look, mine.json(), join(guest(world), code, token=t1).json(), join(org, code, 2, name="O", role="R").json()):
        assert set(body) == JOIN_KEYS
        assert body["me"] is None or set(body["me"]) == ME_KEYS
        assert all(set(s) == {"n", "state"} for s in body["seats"])
    org.post(f"{BASE}/sessions/{sid}/seats/1/revoke")
    seat_in(world, guest(world), code, 3, name="Cy", role="Buyer")
    t3 = join(guest(world), code, 3, name="x", role="y")  # taken: refused, nothing but the plain error
    assert set(t3.json()) <= {"error", "message", "field"}
    for view in (lobby(org, sid).json(), lobby(guest(world), sid, seat_in(world, guest(world), code, 4)[0]).json()):
        assert set(view) == LOBBY_KEYS
        assert view["me"] is None or set(view["me"]) == ME_KEYS
        for s in view["seats"]:
            assert set(s) <= {"n", "state", "mine", "name", "role", "late"}
            if s["state"] != "taken":  # a free or removed seat names nobody, for anyone
                assert not {"name", "role"} & set(s)


# ---- the join page sends no referrer ---------------------------------------------------------------------------------
def test_the_page_tells_the_browser_to_send_no_referrer():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    assert '<meta name="referrer" content="no-referrer"' in html


# ---- the stale module check for a draft after remove: nothing else here ----------------------------------------------
def test_unused_helper_is_gone():
    assert not hasattr(room_api, "_own")
