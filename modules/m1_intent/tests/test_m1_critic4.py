"""Customer critic round 4 (module 1): an empty charter cannot be signed or sent, finishing early is confirmed through the
API as well as the screen, the email carries a full link and names who has no address, the briefing video reaches a guest
(and a new session has a default one), prefill reads only the note it fills, and unsent notes go anonymously where each
person chooses (A-045). Synthetic wording only; stub models."""
import datetime
import json
from dataclasses import replace

from m1_kit import BASE
from modules.m1_intent.domain import briefing as B
from modules.m1_intent.store.notes import NoteStore
from test_m1_board_kit import Board
from test_m1_charter_export import signed
from test_m1_charter_kit import CLUSTERS, draft, put_result, ready, send_up  # noqa: F401
from test_m1_charter_kit import stand_in_result  # noqa: F401  (the autouse fixture)
from test_m1_seat_wiring_kit import StubNorth, flow, new_world

UNTICKED = [{**c, "ticked": False} for c in CLUSTERS]


# ---- 4. an empty charter, and finishing early through the API
def test_a_charter_with_no_problem_cannot_be_signed_or_sent(world):
    org, sid, _ = ready(world, result=False)
    put_result(world, "co-a", sid, UNTICKED)
    assert org.post(f"{BASE}/sessions/{sid}/charter", json={"confirm": True}).status_code == 201
    r = org.post(f"{BASE}/sessions/{sid}/charter/sign")
    assert r.status_code == 409 and r.json()["message"] == "Tick at least one problem before signing."
    r = org.post(f"{BASE}/sessions/{sid}/charter/send")
    assert r.status_code == 409 and "Tick at least one problem" in r.json()["message"]
    assert org.get(f"{BASE}/sessions/{sid}/charter").json()["charter"]["signing"]["signed"] == 0


def test_finishing_with_groups_open_needs_confirm_through_the_api(world):
    org, sid, _ = ready(world)  # one of the four groups is not ticked
    r = org.post(f"{BASE}/sessions/{sid}/charter")
    assert r.status_code == 409 and "still open" in r.json()["message"] and "confirm" in r.json()["message"]
    assert org.get(f"{BASE}/sessions/{sid}/charter").json()["charter"] is None  # nothing was drafted, the stage did not move
    assert org.post(f"{BASE}/sessions/{sid}/charter", json={"confirm": "yes"}).status_code == 400
    assert org.post(f"{BASE}/sessions/{sid}/charter", json={"confirm": True}).status_code == 201


def test_finishing_with_nothing_open_needs_no_confirm(world):
    org, sid, _ = ready(world, result=False)
    put_result(world, "co-a", sid, [{**c, "ticked": True} for c in CLUSTERS])
    assert org.post(f"{BASE}/sessions/{sid}/charter").status_code == 201


def test_the_footer_date_is_the_organisers_own_day(world):
    org, sid, _ = ready(world)
    today = datetime.datetime.now(datetime.timezone.utc).date()
    day = today + datetime.timedelta(days=1)
    assert org.post(f"{BASE}/sessions/{sid}/charter", json={"confirm": True, "date": "2020-01-01"}).status_code == 400  # not believed
    r = org.post(f"{BASE}/sessions/{sid}/charter", json={"confirm": True, "date": day.isoformat()})
    assert r.status_code == 201 and r.json()["charter"]["footer"]["date"] == day.isoformat()


# ---- 5. the email
def test_the_email_has_a_full_link_from_the_configured_base_and_lists_who_has_no_address(world, monkeypatch):
    monkeypatch.setenv("SH_PUBLIC_BASE_URL", "https://harbor.example.test/")
    org, sid, _, _, _ = signed(world, guest_seat=1)
    e = org.get(f"{BASE}/sessions/{sid}/charter/email", headers={"origin": "https://evil.example"}).json()
    link = f"https://harbor.example.test/modules/m1_intent/sessions/{sid}/charter"
    assert e["link"] == link and link in e["body"] and "evil.example" not in json.dumps(e)
    assert e["no_address"] == ["Sara Guest"]
    assert {p["name"] for p in e["people"] if p["email"]} == {"Second Signer"}


def test_without_a_configured_base_the_email_uses_the_servers_own_address(world, monkeypatch):
    monkeypatch.delenv("SH_PUBLIC_BASE_URL", raising=False)
    org, sid, _, _, _ = signed(world)
    assert org.get(f"{BASE}/sessions/{sid}/charter/email").json()["link"] == f"http://testserver/modules/m1_intent/sessions/{sid}/charter"


# ---- 2. the briefing video
def test_a_new_session_has_the_default_video_and_a_guest_can_fetch_it_with_the_token(tmp_path):
    w = new_world(tmp_path)
    org, sid, (ada, _) = flow(w, "co-a", stage="briefing")
    assert ada.call("GET", "/briefing").json()["video"] == {"mode": "file", "content_type": "video/mp4"}
    got = ada.call("GET", "/briefing/video")
    assert got.status_code == 200 and got.headers["content-type"] == "video/mp4" and got.content[4:8] == b"ftyp"
    assert org.get(f"{BASE}/sessions/{sid}/briefing/video").status_code == 200
    assert ada.c.get(f"{BASE}/sessions/{sid}/briefing/video").status_code in (401, 403, 404)  # no token, no video: still default deny


def test_the_none_option_and_a_missing_default_keep_the_placeholder_and_none(tmp_path, monkeypatch):
    w = new_world(tmp_path)
    org, sid, (ada, _) = flow(w, "co-a", stage="briefing", prep={"briefing_video": "none"})
    assert ada.call("GET", "/briefing").json()["video"] == {"mode": "none"}
    assert ada.call("GET", "/briefing/video").status_code == 404
    real = B.load_settings
    monkeypatch.setattr(B, "load_settings", lambda folder=None: replace(real(folder), default_video=None))
    org2, sid2, (bea, _) = flow(w, "co-a", org_name="second organiser", stage="briefing")
    assert bea.call("GET", "/briefing").json()["video"] == {"mode": "placeholder"}


# ---- 6. prefill
def test_prefill_sends_only_the_note_it_fills_and_says_to_use_only_it(tmp_path):
    stub = StubNorth({"affected": "Account managers"})
    w = new_world(tmp_path, stub)
    org, sid, (ada, _) = flow(w, "co-a")
    ada.write("Lina and Mei rebuild the pay workbook by hand every month")
    nid = ada.write("Renewals slip every month")
    note = ada.call("POST", f"/room/notes/{nid}/prefill")
    assert note.status_code == 200
    call = next(m for m in reversed(stub.calls) if "ONLY one JSON object" in m[0]["content"])
    sent = json.dumps(call)
    assert "Renewals slip every month" in sent and "Lina" not in sent and "workbook" not in sent
    assert "Use only what is in this note" in call[0]["content"]


# ---- 1. unsent notes (A-045)
def test_an_unsent_note_with_by_name_chosen_goes_anonymously_where_each_person_chooses(tmp_path):
    b = Board(tmp_path, notes=())
    ada, ben = b.guests
    n = ada.write("Calls arrive too late")
    assert ada.save(n, anonymous=False).status_code == 200
    ben.submit(ben.write("Sent by name"))
    b.close_rooms()
    rows = {r["text"]: r for r in NoteStore(b.w.plane(b.company)).board(b.sid)}
    assert rows["Calls arrive too late"]["anonymous"] is True and "author_name" not in rows["Calls arrive too late"]
    assert rows["Sent by name"]["author_name"] == "Ben Guest"



# ---- a revoked seat keeps its name, so nobody new can be credited with its notes
def test_a_new_person_cannot_take_a_revoked_persons_name(world):
    from test_m1_room_kit import guest, join, new_session, start_room
    org = world.login("org revoke", "co-a", ["sponsor"])
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    assert join(guest(world), code, 1, name="Ada Guest").status_code == 200
    assert org.post(f"{BASE}/sessions/{sid}/seats/1/revoke").status_code == 200
    r = join(guest(world), code, 2, name="Ada Guest")
    assert r.status_code == 409 and r.json()["error"] == "name_taken"
