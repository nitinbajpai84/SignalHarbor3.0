"""The guest participant path through the real app: every check that lets a token holder in, or keeps one out.
Each test names the check it guards and fails if that check is removed (the report lists the mutations tried).
Codes and tokens are generated at run time; nothing here is a real secret."""
import json
import logging

import pytest

from m1_kit import BASE
from modules.m1_intent.store import room as store_room
from modules.m1_intent.store.room import resolve_token
from test_m1_room_kit import all_text, guest, hdr, join, lobby, new_session, seat_in, start_room

SIGNED_OUT = {"error": "session_expired", "message": "Your session has ended. Please sign in again.",
              "login_url": "/login"}


@pytest.fixture
def room(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    token, _ = seat_in(world, guest(world), code, 1, name="Ada", role="Planner")
    return world, org, sid, code, token


# ---- the guest principal -----------------------------------------------------------------------------------------
def test_a_token_and_no_cookie_reaches_the_lobby_as_a_participant_of_that_company_only(room):
    world, org, sid, code, token = room
    g = guest(world)
    assert not g.cookies  # no cookie at all
    r = lobby(g, sid, token)
    assert r.status_code == 200 and r.json()["me"]["name"] == "Ada" and r.json()["organiser"] is False


def test_every_way_a_token_can_be_wrong_looks_exactly_like_being_signed_out(room):
    world, org, sid, code, token = room
    g = guest(world)
    org.post(f"{BASE}/sessions/{sid}/seats/1/revoke")  # the good token is now revoked
    other, _ = seat_in(world, guest(world), code, 2)
    cases = [None, "", "garbage", token, other[:-2] + "zz", "x" * 5000, token + " "]  # none valid (first is revoked)
    for t in cases:
        r = g.get(f"{BASE}/sessions/{sid}/lobby", headers=hdr(t) if t is not None else {})
        assert (r.status_code, r.json()) == (401, SIGNED_OUT), repr(t)[:30]
    assert g.get(f"{BASE}/sessions/{sid}/lobby", headers=hdr(other)).status_code == 200  # the control


def test_the_token_is_taken_from_the_header_only_never_the_query_string_or_a_cookie(room):
    world, org, sid, code, token = room
    g = guest(world)
    for url in (f"{BASE}/sessions/{sid}/lobby?token={token}", f"{BASE}/sessions/{sid}/lobby?x-session-token={token}",
                f"{BASE}/sessions/{sid}/lobby?X-Session-Token={token}", f"{BASE}/sessions/{sid}/live?token={token}"):
        assert g.get(url).status_code == 401, url
    g.cookies.set("X-Session-Token", token)
    g.cookies.set("x_session_token", token)
    g.cookies.set("sh_session", token)
    assert g.get(f"{BASE}/sessions/{sid}/lobby").status_code == 401
    assert g.get(f"{BASE}/sessions/{sid}/lobby", headers=hdr(token)).status_code == 200  # the control


def test_a_token_reaches_no_organiser_route_and_no_other_module_route(room):
    world, org, sid, code, token = room
    g = guest(world)
    calls = [("post", f"/sessions/{sid}/start"), ("post", f"/sessions/{sid}/link"),
             ("post", f"/sessions/{sid}/seats/1/revoke"), ("post", f"/sessions/{sid}/briefing"),
             ("get", "/sessions"), ("post", "/sessions"), ("get", f"/sessions/{sid}"), ("put", f"/sessions/{sid}"),
             ("delete", f"/sessions/{sid}?confirm=yes"), ("get", "/lists"), ("get", "/templates"),
             ("post", "/templates"), ("get", f"/outcomes/{'a' * 32}")]
    for verb, path in calls:
        r = getattr(g, verb)(BASE + path, headers=hdr(token), **({"json": {}} if verb in ("post", "put") else {}))
        # refused, not "your session has ended": the guest's own room still works (CRITIC-M1 round 3)
        assert (r.status_code, r.json()["error"]) == (403, "forbidden"), (verb, path)
    assert lobby(g, sid, token).status_code == 200
    # and nothing changed
    assert org.get(f"{BASE}/sessions/{sid}").json()["state"] == "lobby"
    assert lobby(org, sid).json()["seats"][0]["state"] == "taken"


@pytest.mark.parametrize("path,verb", [("/api/modules", "get"), ("/api/company", "get"), ("/api/auth/me", "get"),
                                       ("/api/auth/logout", "post"),
                                       ("/api/admin/companies/co-a/modules/m1_intent", "put"),
                                       ("/api/modules/m2_baseline/anything", "get")])
def test_a_token_reaches_no_kernel_route_and_only_the_health_check_answers(room, path, verb):
    world, org, sid, code, token = room
    g = guest(world)
    r = getattr(g, verb)(path, headers=hdr(token))
    assert r.status_code in (401, 403, 404, 405)
    assert "Ada" not in r.text
    assert g.get("/api/health", headers=hdr(token)).json() == {"status": "ok"}


def test_the_path_session_must_be_the_tokens_own_session_even_inside_one_company(room):
    world, org, sid, code, token = room
    other_sid = new_session(org)
    start_room(org, other_sid)
    for path in (f"/sessions/{other_sid}/lobby", f"/sessions/{other_sid}/live", f"/sessions/{'0' * 32}/lobby",
                 "/sessions/not-an-id/lobby"):
        r = guest(world).get(BASE + path, headers=hdr(token))
        assert (r.status_code, r.json()["error"]) == (404, "not_found"), path
    assert "Ada" not in guest(world).get(f"{BASE}/sessions/{other_sid}/lobby", headers=hdr(token)).text


def test_another_companys_session_is_not_reachable_with_a_token_of_this_company(room):
    world, org, sid, code, token = room
    other_org = world.login("org-b", "co-b")
    b_sid = new_session(other_org)
    b_code = start_room(other_org, b_sid)
    b_token, _ = seat_in(world, guest(world), b_code, 1, name="Bea")
    g = guest(world)
    assert g.get(f"{BASE}/sessions/{b_sid}/lobby", headers=hdr(token)).status_code == 404
    assert g.get(f"{BASE}/sessions/{sid}/lobby", headers=hdr(b_token)).status_code == 404
    # the other company's organiser has no standing in this company's session either
    for verb, path in (("get", f"/sessions/{sid}/lobby"), ("post", f"/sessions/{sid}/briefing"),
                       ("post", f"/sessions/{sid}/seats/1/revoke"), ("post", f"/sessions/{sid}/link")):
        r = getattr(other_org, verb)(BASE + path)
        assert (r.status_code, r.json()["error"]) == (404, "not_found"), path
    assert lobby(guest(world), sid, token).json()["seats"][0]["state"] == "taken"


def test_the_company_is_never_taken_from_the_request(room):
    world, org, sid, code, token = room
    r = guest(world).get(f"{BASE}/sessions/{sid}/lobby?company_id=co-b&company=co-b",
                         headers={**hdr(token), "X-Company-Id": "co-b", "X-Company": "co-b", "Host": "co-b.test"})
    assert r.status_code == 200 and r.json()["session_id"] == sid


def test_a_token_whose_secret_belongs_to_another_session_is_refused_by_the_resolver(room):
    world, org, sid, code, token = room
    root = world.settings.data_root
    assert resolve_token(root, token)[0] == "co-a" and resolve_token(root, token)[2] == sid
    b_org = world.login("org-b", "co-b")
    b_sid = new_session(b_org)
    seat_in(world, guest(world), start_room(b_org, b_sid), 1)
    mixed = b_sid + "." + token.split(".", 1)[1]  # B's session id, A's secret
    for bad in (mixed, None, 5, b"x", "", token.replace(sid, "f" * 32)):
        assert resolve_token(root, bad) is None


def test_a_damaged_control_index_refuses_guests_instead_of_failing_open(room):
    world, org, sid, code, token = room
    path = world.settings.data_root + "/_control/m1_join_index.json"
    with open(path, "w", encoding="utf-8") as f:
        f.write("{not json")
    assert resolve_token(world.settings.data_root, token) is None
    assert lobby(guest(world), sid, token).status_code == 401
    r = join(guest(world), code)
    assert r.status_code == 500 and r.json()["error"] == "unreadable" and code not in r.text


def test_token_checks_use_a_constant_time_compare(room, monkeypatch):
    world, org, sid, code, token = room
    calls = []
    real = store_room.hmac.compare_digest
    monkeypatch.setattr(store_room.hmac, "compare_digest", lambda a, b: calls.append(1) or real(a, b))
    assert lobby(guest(world), sid, token).status_code == 200
    assert calls


def test_a_signed_in_organiser_keeps_their_rights_even_when_a_participants_token_is_also_sent(room):
    world, org, sid, code, token = room
    r = org.post(f"{BASE}/sessions/{sid}/briefing", headers=hdr(token))
    assert r.status_code == 200  # the cookie decides who this is; the token is ignored
    assert lobby(org, sid, token).json()["organiser"] is True


def test_a_signed_in_person_of_another_company_cannot_use_a_token_to_get_in(room):
    world, org, sid, code, token = room
    other = world.login("other", "co-b")
    r = other.get(f"{BASE}/sessions/{sid}/lobby", headers=hdr(token))
    assert r.status_code == 404  # signed in as co-b: the token is ignored and co-b has no such session
    assert "Ada" not in r.text


# ---- nothing secret is ever shown, stored in plain, or logged -----------------------------------------------------
def test_the_code_and_tokens_appear_nowhere_but_where_they_are_handed_over(world, caplog):
    caplog.set_level(logging.DEBUG)
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    bodies: list[str] = []

    def keep(r):
        bodies.append(r.text)
        return r

    start = keep(org.post(f"{BASE}/sessions/{sid}/start"))
    code = start.json()["join_path"].split("/")[-1]
    g = guest(world)
    first = keep(join(g, code, 1, name="Ada", role="Planner"))
    token = first.json()["token"]
    secret = token.split(".", 1)[1]
    for r in (join(guest(world), code), join(guest(world), code, 1), join(guest(world), code, 9),
              join(guest(world), code, 2, name="", role=""), join(guest(world), "wrong" * 5),
              lobby(guest(world), sid, token), lobby(guest(world), sid, "fake-wrong-token"),
              lobby(guest(world), sid), org.get(f"{BASE}/sessions/{sid}/lobby"),
              keep(org.post(f"{BASE}/sessions/{sid}/seats/1/revoke")), lobby(guest(world), sid, token),
              join(guest(world), code, token=token), org.post(f"{BASE}/sessions/{sid}/briefing")):
        keep(r)
    new_link = keep(org.post(f"{BASE}/sessions/{sid}/link"))
    advance_closed(world, sid)
    keep(join(guest(world), code))
    keep(lobby(guest(world), sid, token))
    keep(org.post(f"{BASE}/sessions/{sid}/link"))
    # the code is shown only to the organiser, in the start answer and in a new-link answer
    for text in bodies:
        if text in (start.text, new_link.text):
            continue
        assert code not in text, text[:80]
    # the token is shown once, in the answer to the join that made it
    for text in bodies:
        if text == first.text:
            continue
        assert token not in text and secret not in text
    assert code not in caplog.text and token not in caplog.text and secret not in caplog.text
    stored = all_text(world.settings.data_root)
    assert code not in stored and token not in stored and secret not in stored


def advance_closed(world, sid):
    from modules.m1_intent.store.sessions import SessionStore
    store = SessionStore(world.plane("co-a"))
    for s in ("private_rooms", "board", "together", "signing", "closed"):
        store.transition(sid, s)


def test_the_web_server_access_log_never_records_the_join_page_address():
    log = logging.getLogger("uvicorn.access")
    assert any(type(f).__name__ == "_HideJoinCode" for f in log.filters)
    secret_code = "AbCdEfGhIjKlMnOpQrStUv"
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "x", 1, '%s - "%s %s HTTP/%s" %d',
                            ("127.0.0.1:1", "GET", f"/join/{secret_code}", "1.1", 200), None)
    for f in log.filters:
        f.filter(rec)
    assert secret_code not in rec.getMessage() and "/join/<hidden>" in rec.getMessage()
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "x", 1, f"GET /join/{secret_code}?x=1 done", (), None)
    for f in log.filters:
        f.filter(rec)
    assert secret_code not in rec.getMessage()


def test_the_join_route_never_answers_with_a_stack_trace_or_the_input(world):
    org = world.login("org", "co-a")
    code = start_room(org, new_session(org))
    for body in ({"code": code, "seat": {"$gt": 1}, "name": "x", "role": "y"},
                 {"code": code, "seat": 1, "name": {"a": 1}, "role": "y"}, {"code": code, "seat": 10 ** 40}):
        r = guest(world).post(f"{BASE}/join", json=body)
        assert r.status_code == 422 and "Traceback" not in r.text and code not in r.text


def test_a_participant_token_is_a_random_secret_and_nothing_in_it_names_a_company_or_person(room):
    world, org, sid, code, token = room
    assert "co-a" not in token and "Ada" not in token
    assert token.split(".")[0] == sid  # the session id only, which the holder already knows from the path
    seat = json.loads(world.plane("co-a").path("intents", "m1_intent", "rooms", f"{sid}.json")
                      .read_text(encoding="utf-8"))["seats"][0]
    assert seat["token_hash"] and seat["token_hash"] not in token and token.split(".")[1] not in json.dumps(seat)


# ---- each layer on its own: the checks are repeated on purpose, so each needs a test that sees it alone ------------
def test_a_seat_that_is_revoked_in_the_file_refuses_its_token_even_if_the_hash_were_left_behind(room):
    world, org, sid, code, token = room
    path = world.plane("co-a").path("intents", "m1_intent", "rooms", f"{sid}.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["seats"][0]["state"] = "revoked"  # the hash is still there: only the state says no
    path.write_text(json.dumps(data), encoding="utf-8")
    assert resolve_token(world.settings.data_root, token) is None
    assert lobby(guest(world), sid, token).status_code == 401


def test_revoking_clears_the_token_hash_in_the_stored_seat(room):
    world, org, sid, code, token = room
    org.post(f"{BASE}/sessions/{sid}/seats/1/revoke")
    path = world.plane("co-a").path("intents", "m1_intent", "rooms", f"{sid}.json")
    seat = json.loads(path.read_text(encoding="utf-8"))["seats"][0]
    assert seat["state"] == "revoked" and seat["token_hash"] is None


def test_the_path_session_check_holds_even_if_two_seats_somehow_shared_an_identity(room):
    """Normally a seat of another session is simply not found. Force the worst case (the same participant id in
    two sessions of one company): the explicit session check must still refuse."""
    world, org, sid, code, token = room
    other = new_session(org)
    start_room(org, other)
    own = json.loads(world.plane("co-a").path("intents", "m1_intent", "rooms", f"{sid}.json").read_text(encoding="utf-8"))
    pid = own["seats"][0]["participant_id"]
    path = world.plane("co-a").path("intents", "m1_intent", "rooms", f"{other}.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["seats"][0].update(state="taken", participant_id=pid, name="Twin", role="Twin")
    path.write_text(json.dumps(data), encoding="utf-8")
    r = guest(world).get(f"{BASE}/sessions/{other}/lobby", headers=hdr(token))
    assert (r.status_code, r.json()["error"]) == (404, "not_found") and "Twin" not in r.text
