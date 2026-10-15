"""M1-P05 seat wiring: guests (and bound accounts, and the organiser alone) reach their own briefing, room and notes,
and nobody else's. Real join links and tokens; North is a stub."""
import json

import pytest
from fastapi.testclient import TestClient

from m1_kit import BASE
from modules.m1_intent.store.room import RoomStore
from test_m1_room_kit import all_text, guest, join, new_session, start_room
from test_m1_seat_wiring_kit import Guest, admin, flow, ids_of, new_world

PARTICIPANT = [("GET", "/briefing"), ("GET", "/timer"), ("GET", "/room"), ("GET", "/room/library"),
               ("POST", "/briefing/confirm"), ("POST", "/room/messages"), ("POST", "/nira")]
ORGANISER_ONLY = [("POST", "/briefing/send"), ("POST", "/timer/extend"), ("POST", "/start"), ("POST", "/link"),
                  ("GET", "/join-link"), ("POST", "/seats/1/revoke"), ("POST", "/briefing"), ("GET", "")]


@pytest.fixture
def w(tmp_path):
    return new_world(tmp_path)


def test_a_guest_reaches_their_own_briefing_room_and_notes(w):
    org, sid, (ada, ben) = flow(w)
    assert ada.call("GET", "/briefing").status_code == 200
    assert ada.call("POST", "/briefing/confirm", json={"answer": "clear"}).json()["me"]["status"] == "clear"
    assert ada.call("GET", "/timer").json()["timed"] is True
    nid = ada.write("Renewals slip every month")
    assert [n["id"] for n in ada.room()["notes"]] == [nid]
    assert ben.room()["notes"] == [] and ben.call("GET", "/briefing").json()["me"]["status"] == "waiting"


def test_two_guests_never_see_each_others_room_or_clear_status(w):
    org, sid, (ada, ben) = flow(w)
    ada.write("ada private words")
    ada.call("POST", "/briefing/confirm", json={"answer": "clear"})
    assert "ada private" not in json.dumps(ben.room())
    assert "ada private" not in org.get(f"{BASE}/sessions/{sid}/room").text
    assert org.get(f"{BASE}/sessions/{sid}/briefing").json()["confirmed"] == 1  # a count only, never who


def test_a_token_works_only_for_its_own_session_and_company(w):
    org, sid, (ada, _) = flow(w)
    org2, sid2, (cy, _) = flow(w, org_name="org two", names=("Cy Guest", "Di Guest"))
    for method, path in PARTICIPANT:
        r = ada.c.request(method, f"{BASE}/sessions/{sid2}{path}", headers={"X-Session-Token": ada.token}, json={})
        assert r.status_code in (401, 403, 404), (method, path, r.status_code)
        assert "Cy" not in r.text
    other = w.login("other co", "co-b", ["company_admin"])
    assert other.get(f"{BASE}/sessions/{sid}/room").status_code == 404
    assert other.get(f"{BASE}/sessions/{sid}/briefing").status_code == 404


@pytest.mark.parametrize("method,path", ORGANISER_ONLY)
def test_a_guest_cannot_reach_any_organiser_route(w, method, path):
    org, sid, (ada, _) = flow(w)
    r = ada.c.request(method, f"{BASE}/sessions/{sid}{path}", headers={"X-Session-Token": ada.token}, json={"minutes": 2})
    assert r.status_code in (401, 403), r.status_code
    assert org.get(f"{BASE}/sessions/{sid}").json()["state"] == "private_rooms"


def test_a_guest_cannot_reach_the_admin_routes(w):
    org, sid, (ada, _) = flow(w)
    for method, path in (("GET", f"/sessions/{sid}/seats/2/transcript"), ("POST", "/retention/purge")):
        r = ada.c.request(method, BASE + path, headers={"X-Session-Token": ada.token}, json={})
        assert r.status_code in (401, 403)


def test_a_seat_in_the_body_header_or_query_is_never_used(w):
    org, sid, (ada, ben) = flow(w)
    ben.write("ben words")
    ids = ids_of(w, "co-a", sid, 2)
    r = ada.c.get(f"{BASE}/sessions/{sid}/room?seat_id={ids['seat']}", headers={"X-Session-Token": ada.token, "X-Seat-Id": ids["seat"]})
    assert "ben words" not in r.text


def test_a_removed_seat_loses_its_room(w):
    org, sid, (ada, _) = flow(w)
    ada.write("before")
    assert org.post(f"{BASE}/sessions/{sid}/seats/1/revoke").status_code == 200
    assert ada.call("GET", "/room").status_code in (401, 403, 404)


def test_a_signed_in_person_bound_to_a_seat_reaches_it_and_a_stranger_does_not(w):
    org = w.login("org", "co-a", ["sponsor"])
    sid = new_session(org, seats=2)
    code = start_room(org, sid)
    mine = w.login("Bound Person", "co-a", ["participant"])
    assert join(mine, code, 1, name="Bound Person").status_code == 200
    base = f"{BASE}/sessions/{sid}"
    assert org.post(f"{base}/briefing").status_code == 200 and org.post(f"{base}/briefing/send").status_code == 200
    assert mine.post(f"{base}/room/messages", json={"text": "bound words", "kind": "note"}).status_code == 200
    stranger = w.login("Stranger", "co-a", ["participant"])
    assert stranger.get(f"{base}/room").status_code == 404
    assert "bound words" not in json.dumps(org.get(f"{base}/room").json())


def test_the_organiser_running_a_session_alone_has_their_own_seat(w):
    org = w.login("Solo Person", "co-solo", ["company_admin"])
    sid = new_session(org, seats=1)
    code = start_room(org, sid)
    assert join(org, code, 1, name="Solo Person").status_code == 200
    base = f"{BASE}/sessions/{sid}"
    assert org.post(f"{base}/briefing").status_code == 200
    assert org.post(f"{base}/briefing/confirm", json={"answer": "clear"}).status_code == 200
    assert org.post(f"{base}/briefing/send").status_code == 200
    nid = org.post(f"{base}/room/messages", json={"text": "alone", "kind": "note"}).json()["notes"][0]["id"]
    assert org.post(f"{base}/room/notes/{nid}/submit").status_code == 200


@pytest.mark.parametrize("company,industry", [("co-a", "industry_a"), ("co-b", "industry_b"), ("co-empty", "industry_a")])
def test_the_flow_works_for_two_industries_and_the_empty_company(w, company, industry):
    org, sid, (ada, _) = flow(w, company=company)
    assert ada.call("GET", "/room").json()["open"] is True and ada.call("GET", "/briefing").status_code == 200


def test_a_guests_name_is_registered_with_the_egress_vault_before_north_is_asked(w):
    org, sid, (ada, _) = flow(w)
    ada.write("hello")
    vault = [p for p in w.plane("co-a").root.rglob("name_vault.json")]
    assert vault and "Ada Guest" in vault[0].read_text(encoding="utf-8")


def test_the_organiser_can_see_the_join_link_again_without_making_a_new_one(w):
    org = w.login("org", "co-a", ["sponsor"])
    sid = new_session(org, seats=2)
    code = start_room(org, sid)
    first = org.get(f"{BASE}/sessions/{sid}/join-link")
    assert first.status_code == 200 and first.json()["join_path"] == f"/join/{code}"
    assert join(guest(w), code).status_code == 200  # still works: seeing it did not replace it
    assert code not in all_text(w.settings.data_root)  # stored sealed, never as the plain code
    new = org.post(f"{BASE}/sessions/{sid}/link").json()["join_path"]
    assert new != f"/join/{code}" and org.get(f"{BASE}/sessions/{sid}/join-link").json()["join_path"] == new
    assert join(guest(w), code).status_code == 404  # the old one stopped
    assert w.login("p", "co-a", ["participant"]).get(f"{BASE}/sessions/{sid}/join-link").status_code == 403
    assert w.login("x", "co-a", ["sponsor"]).get(f"{BASE}/sessions/{sid}/join-link").status_code == 404


def test_a_guest_in_the_lobby_can_read_the_sessions_own_title_from_the_briefing_answer(w):
    org, sid, (ada, _) = flow(w, stage="lobby")  # the lobby answers stay as M1-P02 fixed them; the title comes from here
    assert ada.call("GET", "/briefing").json()["title"].startswith("Agree what we want to know")
