"""M1-03 room and join link, M1-04 lobby, M1-15 rejoin and late join through the real app.
Ported in spirit from the earlier product's join / seat / token / binding tests, reshaped to seats, one link and
the X-Session-Token header. Security cases (the guest principal, logs, cross-company) are in test_m1_room_guest.py,
live updates in test_m1_room_live.py."""
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from m1_kit import BASE, ORGANISER_ROLES
from modules.m1_intent.domain import room as R
from modules.m1_intent.store.room import JoinIndex, digest
from modules.m1_intent.store.sessions import SessionStore
from sh_platform.process_record import ProcessRecords
from test_m1_room_kit import (BOTH_ROUTES, ORGANISER_ROUTES, TOKEN, all_text, guest, hdr, join, lobby, new_session,
                              seat_in, start_room)

LINK_INVALID = {"error": "link_invalid", "message": "This link is not working. Please ask the organiser for a new one."}
ALL_STATES_AFTER_LOBBY = ("briefing", "private_rooms", "board", "together", "signing")


def advance(world, company, sid, *states):
    store = SessionStore(world.plane(company))
    for s in states:
        store.transition(sid, s)


# ---- M1-03: starting the room -----------------------------------------------------------------------------------
@pytest.mark.parametrize("role", ORGANISER_ROLES)
def test_every_organiser_role_can_start_the_room(world, role):
    c = world.login(f"o-{role}", "co-a", [role])
    sid = new_session(c)
    assert c.post(f"{BASE}/sessions/{sid}/start").status_code == 201


@pytest.mark.parametrize("role", ["participant", "approver", "owner"])
def test_other_roles_cannot_start_or_run_the_room(world, role):
    org = world.login("org", "co-a")
    sid = new_session(org)
    code = start_room(org, sid)
    c = world.login(f"x-{role}", "co-a", [role])
    for verb, path in ORGANISER_ROUTES:
        assert getattr(c, verb)(BASE + path.format(sid=sid)).status_code == 403, path
    assert SessionStore(world.plane("co-a")).get(sid)["state"] == "lobby"
    assert join(guest(world), code).status_code == 200  # the room is untouched


def test_starting_makes_seats_one_link_and_moves_the_session_to_the_lobby(world):
    c = world.login("org", "co-a")
    sid = new_session(c, seats=4)
    r = c.post(f"{BASE}/sessions/{sid}/start")
    assert r.status_code == 201 and r.json()["state"] == "lobby"
    got = c.get(f"{BASE}/sessions/{sid}").json()
    assert got["state"] == "lobby" and got["editable"] is False
    seats = c.get(f"{BASE}/sessions/{sid}/lobby").json()
    assert seats["seat_count"] == 4 and [s["state"] for s in seats["seats"]] == ["free"] * 4
    assert seats["organiser"] is True and seats["me"] is None


def test_the_move_out_of_draft_is_mirrored_in_the_process_record(world):
    c = world.login("org", "co-a")
    sid = new_session(c)
    start_room(c, sid)
    s = SessionStore(world.plane("co-a")).get(sid)
    rec = ProcessRecords(world.plane("co-a")).get_by_session(s["record_session_id"])
    assert rec.session_state == "in_progress" and rec.outcome_state == "in_progress"


def test_prepared_values_become_read_only_and_the_room_starts_only_once(world):
    c = world.login("org", "co-a")
    sid = new_session(c)
    start_room(c, sid)
    assert c.put(f"{BASE}/sessions/{sid}", json={"purpose": "Changed"}).status_code == 409
    again = c.post(f"{BASE}/sessions/{sid}/start")
    assert again.status_code == 409 and again.json()["error"] == "wrong_state"


def test_only_the_organiser_account_can_run_the_room_another_admin_gets_not_found(world):
    mine, other = world.login("mine", "co-a"), world.login("other", "co-a")
    sid = new_session(mine)
    for verb, path in ORGANISER_ROUTES:
        r = getattr(other, verb)(BASE + path.format(sid=sid))
        assert (r.status_code, r.json()["error"]) == (404, "not_found"), path
    assert SessionStore(world.plane("co-a")).get(sid)["state"] == "draft"


def test_the_code_and_every_token_are_stored_only_as_hashes(world):
    c = world.login("org", "co-a")
    sid = new_session(c)
    code = start_room(c, sid)
    token, _ = seat_in(world, guest(world), code, 1)
    secret = token.split(".", 1)[1]
    text = all_text(world.settings.data_root)
    assert code not in text and token not in text and secret not in text
    index = json.loads((Path(world.settings.data_root) / "_control" / "m1_join_index.json").read_text(encoding="utf-8"))
    assert list(index["codes"]) == [digest(code)]
    assert set(index["codes"][digest(code)]) == {"company_id", "session_id", "created", "closed"}
    assert index["sessions"] == {sid: "co-a"}
    assert "name" not in json.dumps(index) and "Ada" not in json.dumps(index)  # ids only


def test_codes_and_tokens_are_long_random_and_never_repeat(world):
    c = world.login("org", "co-a")
    codes = {start_room(c, new_session(c)) for _ in range(5)}
    assert len(codes) == 5 and all(len(x) == 22 for x in codes)  # 128 bits, url-safe
    tokens = set()
    sid = new_session(c, seats=5)
    code = start_room(c, sid)
    for n in range(1, 6):
        t, _ = seat_in(world, guest(world), code, n)
        assert TOKEN.match(t)  # session id, then a 256-bit secret
        tokens.add(t)
    assert len(tokens) == 5


# ---- M1-03: joining with the link and no account ----------------------------------------------------------------
def test_a_person_joins_with_no_account_and_gets_a_token_once(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    g = guest(world)
    look = join(g, code)
    assert look.status_code == 200 and look.json()["token"] is None and look.json()["me"] is None
    assert [s["state"] for s in look.json()["seats"]] == ["free"] * 3
    r = join(g, code, 2, name="  Ada   Example ", role="Head of planning")
    body = r.json()
    assert r.status_code == 200 and TOKEN.match(body["token"])
    assert body["me"] == {"seat": 2, "name": "Ada Example", "role": "Head of planning", "late": False,
                          "see_briefing_first": False}
    got = lobby(g, sid, body["token"])
    assert got.status_code == 200 and got.json()["me"]["seat"] == 2 and "token" not in got.text


@pytest.mark.parametrize("seat", [0, 4, -1, 99, "2", 2.0, None, True, [1], {"n": 1}])
def test_a_seat_that_is_not_one_of_the_seats_is_refused(world, seat):
    org = world.login("org", "co-a")
    code = start_room(org, new_session(org, seats=3))
    body = {"code": code, "seat": seat, "name": "Ada", "role": "Lead"}
    r = guest(world).post(f"{BASE}/join", json=body)
    if seat is None:
        assert r.status_code == 200 and r.json()["me"] is None  # no seat = just looking
    else:
        assert r.status_code == 422 and r.json()["field"] == "seat"


@pytest.mark.parametrize("name,role,field", [
    ("", "Lead", "name"), ("   ", "Lead", "name"), (None, "Lead", "name"), (5, "Lead", "name"),
    ("A" * 61, "Lead", "name"), ("Ada\x00", "Lead", "name"), ("Ada‮", "Lead", "name"),
    ("Ada\x07", "Lead", "name"), ("Ada", "", "role"), ("Ada", None, "role"), ("Ada", "L" * 81, "role"),
    ("Ada", "Le\x1bad", "role"), ("Ada", ["Lead"], "role")])
def test_name_and_role_are_plain_limited_text(world, name, role, field):
    org = world.login("org", "co-a")
    code = start_room(org, new_session(org))
    r = guest(world).post(f"{BASE}/join", json={"code": code, "seat": 1, "name": name, "role": role})
    assert r.status_code == 422 and r.json()["field"] == field
    assert "Traceback" not in r.text and code not in r.text
    assert all(s["state"] == "free" for s in join(guest(world), code).json()["seats"])  # nothing was taken


def test_a_name_with_line_breaks_is_folded_to_one_line_and_markup_is_kept_as_text(world):
    org = world.login("org", "co-a")
    sid = new_session(org)
    code = start_room(org, sid)
    token, body = seat_in(world, guest(world), code, 1, name="Ada\n<b>Example</b>", role="Lead\t&co")
    assert body["me"]["name"] == "Ada <b>Example</b>" and body["me"]["role"] == "Lead &co"


def test_two_joins_for_one_seat_exactly_one_wins(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=2)
    code = start_room(org, sid)
    gate = Barrier(8)

    def go(i):
        c = guest(world)
        gate.wait()
        return join(c, code, 1, name=f"Person {i}").status_code

    with ThreadPoolExecutor(8) as pool:
        codes = sorted(pool.map(go, range(8)))
    assert codes == [200] + [409] * 7
    room = org.get(f"{BASE}/sessions/{sid}/lobby").json()
    assert [s["state"] for s in room["seats"]] == ["taken", "free"] and room["arrived"] == 1


def test_a_taken_seat_cannot_be_taken_by_another_and_keeps_its_owner(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=2)
    code = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), code, 1, name="First")
    r = join(guest(world), code, 1, name="Second")
    assert (r.status_code, r.json()["error"]) == (409, "seat_taken")
    assert lobby(guest(world), sid, t1).json()["me"]["name"] == "First"
    # the owner holding a token and asking for another seat is simply returned to their own seat
    again = join(guest(world), code, 2, name="Greedy", token=t1)
    assert again.json()["me"]["seat"] == 1 and again.json()["token"] is None
    assert [s["state"] for s in org.get(f"{BASE}/sessions/{sid}/lobby").json()["seats"]] == ["taken", "free"]


def test_seat_count_is_respected_when_the_room_is_full(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=2)
    code = start_room(org, sid)
    seat_in(world, guest(world), code, 1)
    seat_in(world, guest(world), code, 2)
    assert join(guest(world), code, 1).status_code == 409 and join(guest(world), code, 2).status_code == 409
    assert join(guest(world), code, 3).status_code == 422
    assert org.get(f"{BASE}/sessions/{sid}/lobby").json()["arrived"] == 2


def test_the_link_belongs_to_one_session_and_a_token_only_opens_its_own_session(world):
    org = world.login("org", "co-a")
    a, b = new_session(org), new_session(org)
    code_a, code_b = start_room(org, a), start_room(org, b)
    ta, body_a = seat_in(world, guest(world), code_a, 1)
    tb, body_b = seat_in(world, guest(world), code_b, 1)
    assert body_a["session_id"] == a and body_b["session_id"] == b
    assert lobby(guest(world), a, ta).status_code == 200 and lobby(guest(world), b, tb).status_code == 200
    r = lobby(guest(world), b, ta)  # session A's token on session B's path
    assert (r.status_code, r.json()["error"]) == (404, "not_found")
    assert lobby(guest(world), a, tb).status_code == 404


def test_a_new_link_stops_the_old_one_and_leaves_seated_people_alone(world):
    org = world.login("org", "co-a")
    sid = new_session(org)
    old = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), old, 1)
    r = org.post(f"{BASE}/sessions/{sid}/link")
    assert r.status_code == 200
    new = r.json()["join_path"].split("/")[-1]
    assert new != old
    assert (join(guest(world), old).status_code, join(guest(world), old).json()) == (404, LINK_INVALID)
    assert join(guest(world), new).status_code == 200
    assert lobby(guest(world), sid, t1).status_code == 200  # a token is not the link
    assert JoinIndex(world.settings.data_root).lookup(old) is None


def test_a_token_only_person_cannot_make_a_new_link_or_start_anything(world):
    org = world.login("org", "co-a")
    sid = new_session(org)
    code = start_room(org, sid)
    t, _ = seat_in(world, guest(world), code, 1)
    g = guest(world)
    for verb, path in ORGANISER_ROUTES:
        r = getattr(g, verb)(BASE + path.format(sid=sid), headers=hdr(t))
        assert r.status_code == 403, path  # a live token is refused, not signed out (FIX-GUEST403)
    assert join(guest(world), code).json()["seats"][0]["state"] == "taken"


# ---- unknown, closed and switched-off links ------------------------------------------------------------------------
@pytest.mark.parametrize("code", ["", "short", "a" * 22, "A" * 21 + "!", "../../etc", None, 12345, ["x"], "a" * 500])
def test_an_unknown_or_malformed_code_gets_one_plain_answer(world, code):
    r = guest(world).post(f"{BASE}/join", json={"code": code})
    assert (r.status_code, r.json()) == (404, LINK_INVALID) or r.status_code == 400
    assert "Traceback" not in r.text


def test_a_missing_or_unreadable_body_is_a_plain_bad_request(world):
    g = guest(world)
    assert g.post(f"{BASE}/join", content=b"not json", headers={"Content-Type": "application/json"}).status_code == 400
    assert g.post(f"{BASE}/join", json=[1]).status_code == 400
    assert g.post(f"{BASE}/join", json={}).status_code == 400


def test_a_code_in_the_query_string_is_ignored(world):
    org = world.login("org", "co-a")
    code = start_room(org, new_session(org))
    r = guest(world).post(f"{BASE}/join?code={code}", json={"seat": 1})
    assert r.status_code == 400  # no code in the body, so nothing to look up


def test_closing_the_session_stops_the_link_and_every_token(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), code, 1)
    t2, _ = seat_in(world, guest(world), code, 2)
    advance(world, "co-a", sid, "briefing", "private_rooms", "board", "together", "signing", "closed")
    for t in (t1, t2):
        assert lobby(guest(world), sid, t).status_code == 404  # the token reads only the result (board, charter) after the close
    r = join(guest(world), code)
    assert (r.status_code, r.json()["error"]) == (409, "link_closed") and "closed" in r.json()["message"]
    assert join(guest(world), code, 3).status_code == 409
    assert join(guest(world), code, token=t1).status_code == 409  # not even the old token gets back in
    assert JoinIndex(world.settings.data_root)._read()["codes"][digest(code)]["closed"] is True
    assert org.post(f"{BASE}/sessions/{sid}/link").status_code == 409


def test_a_closed_session_is_judged_by_its_own_state_not_by_the_index_flag(world):
    org = world.login("org", "co-a")
    sid = new_session(org)
    code = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), code, 1)
    advance(world, "co-a", sid, "briefing", "private_rooms", "board", "together", "signing", "closed")
    assert JoinIndex(world.settings.data_root)._read()["codes"][digest(code)]["closed"] is False  # never flagged
    assert lobby(guest(world), sid, t1).status_code == 404
    assert join(guest(world), code, 1).status_code == 409


def test_a_company_without_the_module_gets_the_same_answer_as_an_unknown_link(world):
    org = world.login("org", "co-a")
    sid = new_session(org)
    code = start_room(org, sid)
    t, _ = seat_in(world, guest(world), code, 1)
    world.store.set_module("co-a", "m1_intent", False)
    r = join(guest(world), code)
    assert (r.status_code, r.json()) == (404, LINK_INVALID)
    assert join(guest(world), "x" * 22).json() == r.json()
    # a person who already holds a token is refused by the module gate, same as a signed-in user would be
    assert lobby(guest(world), sid, t).status_code == 403
    assert lobby(guest(world), sid, t).json()["error"] == "module_not_available"
    world.store.set_module("co-a", "m1_intent", True)
    assert lobby(guest(world), sid, t).status_code == 200  # switched back on: everything is as it was


# ---- M1-03: signed-in joiners and solo ----------------------------------------------------------------------------
def test_a_signed_in_person_of_the_company_joins_with_their_account_and_gets_no_token(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    r = join(org, code, 2, name="Olive Organiser", role="Programme owner")
    body = r.json()
    assert r.status_code == 200 and body["token"] is None and body["signed_in"] is True and body["me"]["seat"] == 2
    room_file = world.plane("co-a").path("intents", "m1_intent", "rooms", f"{sid}.json")
    seat = json.loads(room_file.read_text(encoding="utf-8"))["seats"][1]
    assert seat["account_id"] == org.account_id and seat["token_hash"] is None  # bound to the account
    got = org.get(f"{BASE}/sessions/{sid}/lobby").json()
    assert got["me"]["seat"] == 2 and got["organiser"] is True
    again = join(org, code)  # the same link again returns the same seat
    assert again.json()["me"]["seat"] == 2 and again.json()["token"] is None
    assert join(org, code, 3, name="Second try", role="x").json()["me"]["seat"] == 2  # one account, one seat


def test_a_colleague_with_any_company_role_joins_and_is_only_a_participant_in_the_room(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    for role in ("analyst", "participant", "sponsor"):
        c = world.login(f"c-{role}", "co-a", [role])
        r = join(c, code, {"analyst": 1, "participant": 2, "sponsor": 3}[role], name=role.title(), role="Colleague")
        assert r.status_code == 200 and r.json()["token"] is None, role
        me = c.get(f"{BASE}/sessions/{sid}/lobby").json()
        assert me["organiser"] is False and me["me"]["name"] == role.title()
    # being seated does not make them the organiser
    c = world.login("c-analyst2", "co-a", ["analyst"])
    assert c.post(f"{BASE}/sessions/{sid}/briefing").status_code == 404
    # owners and approvers may join a wall they are invited to (orchestrator, 7 Oct): the permission gate lets them through
    assert world.login("x", "co-a", ["approver"]).post(f"{BASE}/join", json={"code": code}).status_code != 403


def test_a_colleague_who_has_not_joined_gets_not_found_on_the_lobby(world):
    org = world.login("org", "co-a")
    sid = new_session(org)
    start_room(org, sid)
    other = world.login("other", "co-a", ["analyst"])
    r = other.get(f"{BASE}/sessions/{sid}/lobby")
    assert (r.status_code, r.json()["error"]) == (404, "not_found")
    assert other.get(f"{BASE}/sessions/{sid}/live").status_code == 404


def test_one_person_can_run_the_whole_session_alone(world):
    solo = world.login("solo", "co-solo", ["company_admin", "sponsor"])
    sid = new_session(solo, seats=1)
    code = start_room(solo, sid)
    r = join(solo, code, 1, name="Sam Solo", role="Founder")
    assert r.status_code == 200 and r.json()["me"]["seat"] == 1 and r.json()["token"] is None
    room = solo.get(f"{BASE}/sessions/{sid}/lobby").json()
    assert room["is_solo"] and room["arrived"] == 1 and room["organiser"] and room["me"]["name"] == "Sam Solo"
    assert join(guest(world), code, 1).status_code == 409  # nobody else can sit in the only seat
    assert solo.post(f"{BASE}/sessions/{sid}/briefing").json() == {"state": "briefing"}


def test_the_organiser_cannot_remove_their_own_seat(world):
    solo = world.login("solo", "co-solo", ["company_admin"])
    sid = new_session(solo, seats=1)
    code = start_room(solo, sid)
    join(solo, code, 1)
    r = solo.post(f"{BASE}/sessions/{sid}/seats/1/revoke")
    assert (r.status_code, r.json()["error"]) == (409, "own_seat")


def test_a_signed_in_person_of_another_company_is_refused_with_no_company_data(world):
    org = world.login("org", "co-a")
    code = start_room(org, new_session(org))
    other = world.login("other", "co-b")
    r = join(other, code, 1, name="Mallory", role="Spy")
    assert r.status_code == 403 and r.json()["error"] == "other_company"
    assert "co-a" not in r.text and "Co-A" not in r.text and "industry" not in r.text
    assert join(other, code).status_code == 403  # not even a look at the seats
    assert all(s["state"] == "free" for s in join(guest(world), code).json()["seats"])


# ---- M1-04: the lobby ---------------------------------------------------------------------------------------------
def test_the_lobby_lists_arrivals_against_seats_and_hides_everything_else(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), code, 1, name="Ada", role="Planner")
    seat_in(world, guest(world), code, 3, name="Cy", role="Buyer")
    for who, token in (("participant", t1), ("organiser", None)):
        c = guest(world) if token else org
        body = lobby(c, sid, token).json()
        assert [(s["n"], s["state"]) for s in body["seats"]] == [(1, "taken"), (2, "free"), (3, "taken")], who
        assert body["seats"][0]["name"] == "Ada" and body["seats"][2]["role"] == "Buyer"
        assert "name" not in body["seats"][1]
        assert body["arrived"] == 2 and body["seat_count"] == 3 and body["length_minutes"] == 20
        text = json.dumps(body)
        for hidden in ("token", "hash", "account", "participant_id", "co-a"):
            assert hidden not in text, (who, hidden)
    assert lobby(guest(world), sid, t1).json()["seats"][0]["mine"] is True
    assert "late" not in lobby(guest(world), sid, t1).json()["seats"][0]  # only the organiser sees that


def test_no_notes_in_the_lobby_notes_are_for_the_private_rooms_only():
    assert R.notes_allowed("private_rooms") is True
    for state in ("draft", "lobby", "briefing", "board", "together", "signing", "paused", "closed"):
        assert R.notes_allowed(state) is False, state


def test_the_organiser_starts_the_briefing_with_empty_seats(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=5)
    start_room(org, sid)
    assert org.post(f"{BASE}/sessions/{sid}/briefing").json() == {"state": "briefing"}
    assert org.get(f"{BASE}/sessions/{sid}").json()["state"] == "briefing"
    r = org.post(f"{BASE}/sessions/{sid}/briefing")  # not twice
    assert (r.status_code, r.json()["error"]) == (409, "wrong_state")


def test_the_briefing_cannot_start_from_a_draft(world):
    org = world.login("org", "co-a")
    sid = new_session(org)
    assert org.post(f"{BASE}/sessions/{sid}/briefing").status_code == 409
    assert org.post(f"{BASE}/sessions/{sid}/link").status_code == 409


def test_revoking_a_seat_stops_its_token_at_once_and_the_seat_is_never_reused(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    t1, _ = seat_in(world, guest(world), code, 1, name="Ada")
    t2, _ = seat_in(world, guest(world), code, 2, name="Bo")
    assert lobby(guest(world), sid, t1).status_code == 200
    r = org.post(f"{BASE}/sessions/{sid}/seats/1/revoke")
    assert r.status_code == 200
    seats = r.json()["seats"]
    # not even the organiser is sent a removed person's name or role: the seat reads only as removed
    assert seats[0] == {"n": 1, "state": "revoked", "mine": False, "late": False} and r.json()["arrived"] == 1
    assert "Ada" not in json.dumps(lobby(org, sid).json())
    assert lobby(guest(world), sid, t1).status_code == 401  # at once
    assert lobby(guest(world), sid, t2).status_code == 200  # the others are not touched
    seen = lobby(guest(world), sid, t2).json()["seats"][0]
    assert seen == {"n": 1, "state": "revoked", "mine": False}  # others see only that it is revoked
    r = join(guest(world), code, 1, name="Mallory")
    assert (r.status_code, r.json()["error"]) == (409, "seat_revoked") and "no longer available" in r.json()["message"]
    # the revoked person cannot come back with the old token, only take another free seat
    back = join(guest(world), code, token=t1)
    assert back.json()["me"] is None and back.json()["seats"][0]["state"] == "revoked"
    assert join(guest(world), code, 3, token=t1, name="Ada again").json()["me"]["seat"] == 3


def test_only_a_taken_seat_can_be_revoked_and_only_by_its_organiser(world):
    org, other = world.login("org", "co-a"), world.login("other", "co-a")
    sid = new_session(org, seats=2)
    code = start_room(org, sid)
    assert org.post(f"{BASE}/sessions/{sid}/seats/1/revoke").json()["error"] == "not_taken"
    seat_in(world, guest(world), code, 1)
    assert other.post(f"{BASE}/sessions/{sid}/seats/1/revoke").status_code == 404
    for bad in ("0", "3", "99", "abc", "-1", "001x"):
        assert org.post(f"{BASE}/sessions/{sid}/seats/{bad}/revoke").status_code in (404, 409), bad
    assert org.get(f"{BASE}/sessions/{sid}/lobby").json()["seats"][0]["state"] == "taken"


# ---- M1-15: rejoin and late join ----------------------------------------------------------------------------------
def test_the_same_link_and_token_return_a_person_to_the_same_seat(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    t, first = seat_in(world, guest(world), code, 2, name="Ada", role="Planner")
    again = join(guest(world), code, token=t)  # a reload: new browser object, same stored token
    assert again.status_code == 200 and again.json()["token"] is None
    assert again.json()["me"] == first["me"]
    assert lobby(guest(world), sid, t).json()["me"]["seat"] == 2
    advance(world, "co-a", sid, "briefing")
    assert join(guest(world), code, token=t).json()["me"]["seat"] == 2  # still, after the stage moved on


def test_losing_the_token_means_taking_a_free_seat_never_someone_elses(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=2)
    code = start_room(org, sid)
    seat_in(world, guest(world), code, 1, name="Ada")  # Ada's token is lost with her browser
    look = join(guest(world), code)
    assert look.json()["me"] is None and look.json()["seats"][0]["state"] == "taken"
    assert join(guest(world), code, 1, name="Ada").status_code == 409  # cannot reclaim it
    assert join(guest(world), code, 2, name="Ada Two").status_code == 200  # a free seat


def test_a_wrong_or_foreign_token_never_opens_a_seat(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=2)
    code = start_room(org, sid)
    t, _ = seat_in(world, guest(world), code, 1)
    secret = t.split(".", 1)[1]
    for bad in (sid + ".x" * 20, f"{sid}.{'A' * 43}", "0" * 32 + "." + secret, secret, t[:-1], t + "x", t.upper()):
        assert lobby(guest(world), sid, bad).status_code == 401, bad
        got = join(guest(world), code, token=bad)
        assert got.status_code == 200 and got.json()["me"] is None  # treated as a stranger, never as that seat


def test_a_latecomer_is_flagged_to_see_the_briefing_first(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    t1, early = seat_in(world, guest(world), code, 1, name="Early")
    advance(world, "co-a", sid, "briefing")
    t2, late = seat_in(world, guest(world), code, 2, name="Late")
    assert early["me"]["see_briefing_first"] is False
    assert late["me"]["late"] is True and late["me"]["see_briefing_first"] is True
    assert lobby(guest(world), sid, t2).json()["me"]["see_briefing_first"] is True
    assert lobby(guest(world), sid, t1).json()["state"] == "briefing"
    seats = org.get(f"{BASE}/sessions/{sid}/lobby").json()["seats"]
    assert (seats[0]["late"], seats[1]["late"]) == (False, True)  # the organiser sees who came late


@pytest.mark.parametrize("state", ALL_STATES_AFTER_LOBBY)
def test_a_latecomer_can_take_a_free_seat_in_every_stage_after_the_lobby(world, state):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=2)
    code = start_room(org, sid)
    advance(world, "co-a", sid, *ALL_STATES_AFTER_LOBBY[:ALL_STATES_AFTER_LOBBY.index(state) + 1])
    assert join(guest(world), code, 2, name="Late").json()["me"]["late"] is True


def test_a_paused_session_lets_seated_people_back_in_but_takes_nobody_new(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    t, _ = seat_in(world, guest(world), code, 1)
    advance(world, "co-a", sid, "paused")
    assert lobby(guest(world), sid, t).json()["state"] == "paused"
    assert join(guest(world), code, token=t).json()["me"]["seat"] == 1
    r = join(guest(world), code, 2, name="New")
    assert (r.status_code, r.json()["error"]) == (409, "paused")
    advance(world, "co-a", sid, "lobby")  # resumed where it stopped
    assert join(guest(world), code, 2, name="New").status_code == 200


def test_a_person_in_the_lobby_sees_the_stage_move_to_the_briefing(world):
    org = world.login("org", "co-a")
    sid = new_session(org)
    code = start_room(org, sid)
    t, _ = seat_in(world, guest(world), code, 1)
    assert lobby(guest(world), sid, t).json()["state"] == "lobby"
    org.post(f"{BASE}/sessions/{sid}/briefing")
    assert lobby(guest(world), sid, t).json()["state"] == "briefing"


# ---- the same checks for two industries, a company with no pack, an empty company and a solo company --------------
@pytest.mark.parametrize("company,seats", [("co-a", 3), ("co-b", 2), ("co-none", 4), ("co-empty", 2), ("co-solo", 1)])
def test_the_whole_room_flow_is_the_same_for_every_company(world, company, seats):
    org = world.login(f"org-{company}", company)
    sid = new_session(org, seats=seats)
    code = start_room(org, sid)
    tokens = [seat_in(world, guest(world), code, n, name=f"Guest {n}", role="Role")[0] for n in range(1, seats + 1)]
    room = org.get(f"{BASE}/sessions/{sid}/lobby").json()
    assert room["arrived"] == seats and room["is_solo"] == (seats == 1)
    assert join(guest(world), code, 1).status_code == 409  # full
    assert org.post(f"{BASE}/sessions/{sid}/seats/1/revoke").status_code == 200
    assert lobby(guest(world), sid, tokens[0]).status_code == 401
    assert org.post(f"{BASE}/sessions/{sid}/briefing").status_code == 200
    # what one company's people see never mentions another company
    assert all(c not in json.dumps(room) for c in ("co-a", "co-b", "co-none", "co-empty", "co-solo") if c != company)


def test_every_route_of_this_package_is_declared_and_default_deny_holds(world):
    from sh_platform.auth import all_routes, route_keys
    perms = world.app.state.route_permissions.routes
    mine = [k for r in all_routes(world.app) if getattr(r, "path_format", "").startswith("/api/modules/m1_intent/")
            for k in route_keys(r) if k.endswith(("/start", "/link", "/revoke", "/lobby", "/live", "/join"))
            or k == "POST /api/modules/m1_intent/sessions/{session_id}/briefing"]  # exactly this package's routes
    assert len(mine) == 7
    guests = sorted(k for k in mine if perms[k].guest)
    assert guests == sorted(k for k in mine if k.endswith(("/lobby", "/live", "/join")))
    assert all("participant" in perms[k].roles for k in guests)
    assert [k for k in mine if perms[k].entry] == ["POST /api/modules/m1_intent/join"]
