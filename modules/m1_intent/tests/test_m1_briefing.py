"""M1-05 briefing and room rules, M1-06 briefing video (placeholder version, D-029/A-019), through the real app:
rules from the prepared session, confirmations, rooms open only on the organiser's send, a latecomer sees the
briefing first, the video slot, uploads limited by the contract, stored in the company plane only."""
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from m1_kit import BASE, ORGANISER_ROLES
from modules.m1_intent.domain import briefing as B
from modules.m1_intent.domain.contracts import DEFAULT_DIR
from test_m1_briefing_kit import make_world, seated, session_at, stage_of

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"x" * 64


def brief(c, sid):
    r = c.get(f"{BASE}/sessions/{sid}/briefing")
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def w(tmp_path, monkeypatch):
    real = B.load_settings  # these tests are about a session's own upload: the module's shared default video is tested in test_m1_critic4.py
    monkeypatch.setattr(B, "load_settings", lambda folder=None: replace(real(folder), default_video=None))
    return make_world(tmp_path)


# ---- M1-05: the rules text comes from the prepared session ----------------------------------------------------
def test_rules_come_from_the_prepared_session_and_follow_a_change(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "draft", purpose="Find our shared worries", outcome="A short list")
    b = brief(org, sid)
    texts = {r["id"]: r["text"] for r in b["rules"]}
    assert texts["purpose"] == "Find our shared worries" and texts["outcome"] == "A short list"
    assert b["company_name"] == "Co-A" and b["title"] == "Find our shared worries"
    assert "20 minutes" in texts["time"] and "anonymous" in texts["notes"]
    org.put(f"{BASE}/sessions/{sid}", json={"purpose": "A different purpose", "length_minutes": 30})
    b2 = brief(org, sid)
    assert {r["id"]: r["text"] for r in b2["rules"]}["purpose"] == "A different purpose"
    assert "30 minutes" in {r["id"]: r["text"] for r in b2["rules"]}["time"]


def test_labels_and_fixed_wording_come_from_the_contract_not_code(w, tmp_path):
    folder = tmp_path / "contracts"
    shutil.copytree(DEFAULT_DIR, folder)
    data = yaml.safe_load((folder / "briefing.yaml").read_text())
    data["rules"]["labels"]["purpose"] = "Why we are here"
    (folder / "briefing.yaml").write_text(yaml.safe_dump(data))
    w.app.state.m1_contracts_dir = folder
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "draft")
    assert brief(org, sid)["rules"][0]["label"] == "Why we are here"


def test_a_broken_contract_is_a_plain_error(w, tmp_path):
    folder = tmp_path / "contracts"
    shutil.copytree(DEFAULT_DIR, folder)
    (folder / "briefing.yaml").write_text("video: 3\n")
    w.app.state.m1_contracts_dir = folder
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "draft")
    r = org.get(f"{BASE}/sessions/{sid}/briefing")
    assert r.status_code == 500 and "briefing.yaml" not in r.text and "Traceback" not in r.text


# ---- confirmations and the send -----------------------------------------------------------------------------
def test_confirm_counts_and_rooms_open_only_when_the_organiser_sends(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", seats=3)
    p1, p2 = seated(w, "co-a", "p1", "seat-1"), seated(w, "co-a", "p2", "seat-2")
    brief(p2, sid)  # the second person sits down (a seat is taken the first time a person asks); LI-M1: with everyone clear the briefing would close
    assert (brief(org, sid)["confirmed"], brief(org, sid)["seats"]) == (0, 3)
    assert p1.post(f"{BASE}/sessions/{sid}/briefing/confirm", json={"answer": "clear"}).json()["me"]["status"] == "clear"
    assert p1.post(f"{BASE}/sessions/{sid}/briefing/confirm", json={"answer": "clear"}).status_code == 200  # twice counts once
    assert brief(org, sid)["confirmed"] == 1
    org.post(f"{BASE}/sessions/{sid}/briefing/confirm", json={"answer": "clear"})
    assert brief(org, sid)["confirmed"] == 2
    assert stage_of(org, sid) == "briefing"  # everyone but one is clear and the rooms are still closed
    r = org.post(f"{BASE}/sessions/{sid}/briefing/send")
    assert r.status_code == 200 and stage_of(org, sid) == "private_rooms"
    assert p2.get(f"{BASE}/sessions/{sid}/briefing").status_code == 200


def test_a_participant_cannot_send_and_cannot_see_the_count(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", seats=2)
    p = seated(w, "co-a", "p", "seat-1")
    assert p.post(f"{BASE}/sessions/{sid}/briefing/send").status_code == 403
    assert stage_of(org, sid) == "briefing"
    b = brief(p, sid)
    assert "confirmed" not in b and b["can_send"] is False and b["me"]["role"] == "participant"
    assert brief(org, sid)["can_send"] is True


def test_confirm_answer_is_checked_and_only_in_the_briefing_or_after_rooms_open(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    assert org.post(f"{BASE}/sessions/{sid}/briefing/confirm", json={"answer": "maybe"}).status_code == 422
    assert org.post(f"{BASE}/sessions/{sid}/briefing/confirm", json=[1]).status_code == 400
    lobby = session_at(w, org, "co-a", "lobby")
    assert org.post(f"{BASE}/sessions/{lobby}/briefing/confirm", json={"answer": "clear"}).status_code == 409
    assert org.post(f"{BASE}/sessions/{lobby}/briefing/send").status_code == 409  # not in the briefing yet


def test_send_twice_is_refused_the_second_time(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    assert org.post(f"{BASE}/sessions/{sid}/briefing/send").status_code == 200
    assert org.post(f"{BASE}/sessions/{sid}/briefing/send").status_code == 409


def test_a_latecomer_sees_the_briefing_before_their_room(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", seats=2)
    org.post(f"{BASE}/sessions/{sid}/briefing/confirm", json={"answer": "clear"})
    org.post(f"{BASE}/sessions/{sid}/briefing/send")
    late = seated(w, "co-a", "late", "seat-late")
    b = brief(late, sid)
    assert b["stage"] == "private_rooms" and b["next"] == "briefing" and b["rules"]
    late.post(f"{BASE}/sessions/{sid}/briefing/confirm", json={"answer": "clear"})
    assert brief(late, sid)["next"] == "room"
    assert brief(org, sid)["next"] == "room"


def test_nobody_outside_the_room_can_use_the_briefing(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    other_admin = w.login("other", "co-a")  # same company, not the organiser of this session
    assert other_admin.get(f"{BASE}/sessions/{sid}/briefing").status_code == 404
    no_seat = w.login("noseat", "co-a", ["participant"])  # a participant account with no seat in this session
    assert no_seat.get(f"{BASE}/sessions/{sid}/briefing").status_code == 403
    foreign = w.login("foreign", "co-b")
    assert foreign.get(f"{BASE}/sessions/{sid}/briefing").status_code == 404
    assert foreign.post(f"{BASE}/sessions/{sid}/briefing/send").status_code == 404
    assert foreign.get(f"{BASE}/sessions/{sid}/briefing/video").status_code == 404


@pytest.mark.parametrize("role", ["approver", "owner"])
def test_other_roles_are_refused(w, role):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    c = w.login(f"r-{role}", "co-a", [role])
    for verb, path in [("get", "briefing"), ("post", "briefing/confirm"), ("post", "briefing/send"),
                       ("get", "briefing/video"), ("post", "nira"), ("get", "timer"), ("post", "timer/extend")]:
        assert getattr(c, verb)(f"{BASE}/sessions/{sid}/{path}").status_code == 403, path


def test_a_company_without_module_1_is_refused(w):
    c = w.login("off", "co-off")
    r = c.get(f"{BASE}/sessions/{'a' * 32}/briefing")
    assert (r.status_code, r.json()["error"]) == (403, "module_not_available")


# ---- two industries, an empty company, a solo run ---------------------------------------------------------------
@pytest.mark.parametrize("company", ["co-a", "co-b", "co-none"])
def test_works_for_any_industry_and_never_shows_industry_content(w, company):
    org = w.login("org", company)
    sid = session_at(w, org, company, "briefing")
    b = brief(org, sid)
    assert b["rules"] and "industry_a" not in str(b) and "industry_b" not in str(b)


def test_an_empty_company_has_nothing_to_brief(w):
    org = w.login("org", "co-empty")
    assert org.get(f"{BASE}/sessions/{'b' * 32}/briefing").status_code == 404


def test_a_solo_run_confirms_and_sends_alone(w):
    org = w.login("solo", "co-solo", ["company_admin", "sponsor"])
    sid = session_at(w, org, "co-solo", "briefing", seats=1)
    b = brief(org, sid)
    assert (b["seats"], b["confirmed"]) == (1, 0)
    org.post(f"{BASE}/sessions/{sid}/briefing/confirm", json={"answer": "clear"})
    assert brief(org, sid)["confirmed"] == 1
    assert org.post(f"{BASE}/sessions/{sid}/briefing/send").status_code == 200


@pytest.mark.parametrize("role", ORGANISER_ROLES)
def test_every_organiser_role_can_run_the_briefing(w, role):
    org = w.login(f"o-{role}", "co-a", [role])
    sid = session_at(w, org, "co-a", "briefing")
    assert org.post(f"{BASE}/sessions/{sid}/briefing/send").status_code == 200


# ---- M1-06: the video slot ------------------------------------------------------------------------------------
def test_without_a_file_there_is_a_placeholder_and_the_text_version(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    b = brief(org, sid)
    assert b["video"] == {"mode": "placeholder"} and b["rules"]  # the text version is always there
    assert org.get(f"{BASE}/sessions/{sid}/briefing/video").status_code == 404


def test_no_video_option_hides_the_slot_but_keeps_the_text(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", briefing_video="none")
    b = brief(org, sid)
    assert b["video"] == {"mode": "none"} and b["rules"]


def test_read_aloud_is_not_available_with_the_stub_and_says_so(w):
    org = w.login("org", "co-a")
    b = brief(org, session_at(w, org, "co-a", "briefing"))
    assert b["read_aloud"] == {"available": False, "message": "Reading aloud is not available yet."}


def upload(c, sid, body=MP4, ctype="video/mp4"):
    return c.put(f"{BASE}/sessions/{sid}/briefing/video", content=body, headers={"content-type": ctype})


def test_an_upload_inside_the_contract_is_stored_in_the_plane_and_shown(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    r = upload(org, sid)
    assert r.status_code == 200 and r.json()["video"] == {"mode": "file", "content_type": "video/mp4"}
    got = org.get(f"{BASE}/sessions/{sid}/briefing/video")
    assert got.status_code == 200 and got.content == MP4 and got.headers["content-type"] == "video/mp4"
    assert got.headers["x-content-type-options"] == "nosniff"
    assert brief(org, sid)["video"]["mode"] == "file"
    root = Path(w.settings.data_root)
    stored = [p for p in root.rglob("*") if p.is_file() and p.read_bytes() == MP4]
    assert len(stored) == 1 and stored[0].relative_to(root).parts[:2] == ("co-a", "context")


def test_a_participant_can_play_it_and_another_company_cannot(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", seats=2)
    upload(org, sid)
    p = seated(w, "co-a", "p", "seat-1")
    assert p.get(f"{BASE}/sessions/{sid}/briefing/video").content == MP4
    assert w.login("x", "co-b").get(f"{BASE}/sessions/{sid}/briefing/video").status_code == 404


@pytest.mark.parametrize("ctype", ["video/quicktime", "text/html", "application/octet-stream", "image/png"])
def test_a_type_outside_the_contract_is_refused(w, ctype):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    r = upload(org, sid, ctype=ctype)
    assert r.status_code == 415 and brief(org, sid)["video"]["mode"] == "placeholder"


def test_a_file_over_the_contract_size_is_refused_and_nothing_is_kept(w, tmp_path):
    folder = tmp_path / "contracts"
    shutil.copytree(DEFAULT_DIR, folder)
    data = yaml.safe_load((folder / "briefing.yaml").read_text())
    data["video"]["max_megabytes"] = 1
    (folder / "briefing.yaml").write_text(yaml.safe_dump(data))
    w.app.state.m1_contracts_dir = folder
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    assert upload(org, sid, body=b"x" * (1024 * 1024 + 1)).status_code == 413
    assert upload(org, sid, body=b"").status_code == 422
    assert brief(org, sid)["video"]["mode"] == "placeholder"
    assert upload(org, sid, body=b"x" * 1024 * 1024).status_code == 200


def test_only_the_organiser_uploads_and_only_before_the_rooms_open(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", seats=2)
    assert upload(seated(w, "co-a", "p", "seat-1"), sid).status_code == 403
    org.post(f"{BASE}/sessions/{sid}/briefing/send")
    assert upload(org, sid).status_code == 409


# ---- fix round: handler-level refusals, a seat is never taken from the request, chunked uploads, plain type error ---
def test_a_seated_company_admin_who_is_not_the_organiser_is_refused_by_the_handler(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "private_rooms", seats=2)
    other = seated(w, "co-a", "other-admin", roles=("company_admin",))  # seated, passes the route roles: the handler must still refuse
    for r in (other.post(f"{BASE}/sessions/{sid}/briefing/send"),
              other.post(f"{BASE}/sessions/{sid}/timer/extend", json={"minutes": 5}),
              upload(other, sid)):
        assert r.status_code == 403 and r.json()["error"] == "forbidden"
    assert stage_of(org, sid) == "private_rooms" and brief(org, sid)["video"]["mode"] == "placeholder"
    assert org.get(f"{BASE}/sessions/{sid}/timer").json()["extensions"] == []


def test_a_seat_sent_in_a_header_or_body_is_ignored(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", seats=3)
    nobody = w.login("nobody", "co-a", ["participant"])  # signed in, no seat from the guest principal
    nobody.headers["x-seat-id"] = "seat-1"
    nobody.headers["x-seat"] = "seat-1"
    assert nobody.get(f"{BASE}/sessions/{sid}/briefing?seat_id=seat-1").status_code == 403
    assert nobody.post(f"{BASE}/sessions/{sid}/briefing/confirm", json={"answer": "clear", "seat_id": "seat-1", "seat": "seat-1"}).status_code == 403
    # a seated person cannot confirm for somebody else either
    p = seated(w, "co-a", "p", "seat-1")
    p.post(f"{BASE}/sessions/{sid}/briefing/confirm", json={"answer": "clear", "seat_id": "seat-2"})
    assert brief(org, sid)["confirmed"] == 1
    assert brief(seated(w, "co-a", "q", "seat-2"), sid)["me"]["status"] == "waiting"


def test_a_chunked_upload_over_the_limit_is_refused_and_nothing_is_kept(w, tmp_path):
    folder = tmp_path / "contracts"
    shutil.copytree(DEFAULT_DIR, folder)
    data = yaml.safe_load((folder / "briefing.yaml").read_text())
    data["video"]["max_megabytes"] = 1
    (folder / "briefing.yaml").write_text(yaml.safe_dump(data))
    w.app.state.m1_contracts_dir = folder
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")

    def chunks(n):
        for _ in range(n):
            yield b"x" * 65536  # no content-length is sent: the body arrives in chunks
    r = org.put(f"{BASE}/sessions/{sid}/briefing/video", content=chunks(20), headers={"content-type": "video/mp4"})
    assert r.status_code == 413
    assert brief(org, sid)["video"]["mode"] == "placeholder"
    assert not [p for p in Path(w.settings.data_root).rglob("*") if p.is_file() and p.name.endswith(".bin")]
    assert org.put(f"{BASE}/sessions/{sid}/briefing/video", content=chunks(16), headers={"content-type": "video/mp4"}).status_code == 200


def test_the_file_type_error_is_in_plain_words(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    r = upload(org, sid, ctype="video/quicktime")
    assert r.status_code == 415 and "a standard video file (.mp4 or .webm)" in r.json()["message"]
