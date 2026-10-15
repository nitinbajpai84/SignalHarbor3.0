"""M1-14 timer, warning and extension. Pure rules first, then the routes with an injected clock.
Ported ideas from the earlier product's session tests: a clock only ever extends, a late joiner gets the time that
is left (not a fresh clock), an organiser-only extend, a stage that ends moves on by itself (tests/test_intent_sessions.py).
The default session is 20 minutes split 4 / 8 / 8; the warning is 60 seconds (contracts/intent_session.yaml)."""
import pytest

from m1_kit import BASE
from modules.m1_intent.domain import timer
from test_m1_briefing_kit import T0, make_world, seated, session_at, stage_of

SPLIT = {"briefing": 4, "individual": 8, "together": 8}


# ---- pure rules ---------------------------------------------------------------------------------------------
def test_stage_time_comes_from_the_split_and_extensions_add_to_it():
    assert timer.ends_at("briefing", SPLIT, 1000.0, []) == 1000.0 + 240
    assert timer.ends_at("private_rooms", SPLIT, 1000.0, [{"minutes": 2}, {"minutes": 5}]) == 1000.0 + 60 * 15
    assert timer.ends_at("together", {"briefing": 1, "individual": 1, "together": 3}, 0.0, []) == 180.0
    with pytest.raises(KeyError):
        timer.ends_at("lobby", SPLIT, 0.0, [])


def test_extending_a_stage_that_is_over_gives_that_many_minutes_from_then_and_never_shortens():
    late = {"at": timer.iso(5000.0), "minutes": 2}  # made long after the stage ended at 1240
    assert timer.ends_at("briefing", SPLIT, 1000.0, [late]) == 5000.0 + 120
    early = {"at": timer.iso(1100.0), "minutes": 2}
    assert timer.ends_at("briefing", SPLIT, 1000.0, [early]) == 1240.0 + 120


def test_which_stages_are_timed():
    assert [s for s in ("lobby", "briefing", "private_rooms", "board", "together", "signing", "paused", "closed")
            if timer.is_timed(s)] == ["briefing", "private_rooms", "together"]


@pytest.mark.parametrize("now,expected", [(0, "running"), (139.9, "running"), (140, "warning"), (199.9, "warning"),
                                           (200, "over"), (500, "over")])
def test_warning_is_the_last_warning_seconds_and_then_over(now, expected):
    assert timer.status(now, 200.0, 60) == expected
    assert timer.status(now, 200.0, 30) == ("warning" if 170 <= now < 200 else "over" if now >= 200 else "running")


def test_times_round_trip_as_utc_text():
    assert timer.parse(timer.iso(1_800_000_000.0)) == 1_800_000_000.0 and timer.iso(0).endswith("+00:00")


# ---- the routes ---------------------------------------------------------------------------------------------
@pytest.fixture
def w(tmp_path):
    return make_world(tmp_path)


def tm(c, sid):
    r = c.get(f"{BASE}/sessions/{sid}/timer")
    assert r.status_code == 200, r.text
    return r.json()


def test_the_timer_shows_the_stage_time_and_what_is_left_from_the_server_clock(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    t = tm(org, sid)
    assert (t["stage"], t["timed"], t["status"], t["remaining_seconds"], t["warning_seconds"]) == ("briefing", True, "running", 240, 60)
    w.now[0] = T0 + 100
    assert tm(org, sid)["remaining_seconds"] == 140
    assert tm(org, sid)["ends_at"].endswith("+00:00") and tm(org, sid)["now"].endswith("+00:00")


def test_the_warning_shows_at_the_contract_warning_time(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    w.now[0] = T0 + 179
    assert tm(org, sid)["status"] == "running"
    w.now[0] = T0 + 180
    assert (tm(org, sid)["status"], tm(org, sid)["remaining_seconds"]) == ("warning", 60)


def test_a_late_joiner_sees_the_time_that_is_left_not_a_fresh_clock(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", seats=2)
    w.now[0] = T0 + 200
    late = seated(w, "co-a", "late", "seat-9")
    assert tm(late, sid)["remaining_seconds"] == 40


def test_the_timer_is_shown_for_each_timed_stage_and_not_for_the_others(w):
    org = w.login("org", "co-a")
    lobby = session_at(w, org, "co-a", "lobby")
    assert tm(org, lobby) == {"stage": "lobby", "timed": False, "now": tm(org, lobby)["now"]}
    for stage in ("private_rooms", "together"):
        sid = session_at(w, org, "co-a", stage)
        assert (tm(org, sid)["timed"], tm(org, sid)["remaining_seconds"]) == (True, 480)


def test_the_rooms_end_moves_the_stage_on_and_runs_the_hook_once(w, monkeypatch):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "private_rooms")
    seen = []
    monkeypatch.setattr(timer, "on_rooms_end", lambda session: seen.append(session["id"]))
    w.now[0] = T0 + 479
    assert tm(org, sid)["stage"] == "private_rooms" and seen == []
    w.now[0] = T0 + 480
    assert tm(org, sid)["stage"] == "board"
    tm(org, sid)
    assert stage_of(org, sid) == "board" and seen == [sid]


def test_extending_keeps_the_rooms_open_for_longer(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "private_rooms")
    w.now[0] = T0 + 470
    r = org.post(f"{BASE}/sessions/{sid}/timer/extend", json={"minutes": 5})
    assert r.status_code == 200 and r.json()["remaining_seconds"] == 10 + 300
    w.now[0] = T0 + 480 + 100
    assert tm(org, sid)["stage"] == "private_rooms"
    w.now[0] = T0 + 480 + 300
    assert tm(org, sid)["stage"] == "board"


def test_a_stage_the_organiser_extends_in_time_does_not_end(w):
    """LI-M1: the briefing now ends by itself too (test_m1_lean_stages); an extension made before the end moves the end."""
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    w.now[0] = T0 + 200
    assert org.post(f"{BASE}/sessions/{sid}/timer/extend", json={"minutes": 2}).json()["remaining_seconds"] == 40 + 120
    w.now[0] = T0 + 300
    assert tm(org, sid)["stage"] == "briefing"


def test_only_the_organiser_extends_and_only_by_a_contract_amount(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "private_rooms", seats=2)
    p = seated(w, "co-a", "p", "seat-1")
    assert p.post(f"{BASE}/sessions/{sid}/timer/extend", json={"minutes": 5}).status_code == 403
    assert tm(p, sid)["may_extend"] is False and tm(org, sid)["may_extend"] is True
    assert tm(org, sid)["extension_minutes"] == [2, 5, 10]
    for bad in (0, -5, 3, 1.5, "5", None, True):
        assert org.post(f"{BASE}/sessions/{sid}/timer/extend", json={"minutes": bad}).status_code == 422, bad
    assert org.post(f"{BASE}/sessions/{sid}/timer/extend", json=[5]).status_code == 400
    assert tm(org, sid)["remaining_seconds"] == 480  # nothing changed
    assert [r["minutes"] for r in org.get(f"{BASE}/sessions/{sid}/timer").json()["extensions"]] == []


def test_extensions_are_recorded_with_their_time(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "private_rooms")
    w.now[0] = T0 + 60
    org.post(f"{BASE}/sessions/{sid}/timer/extend", json={"minutes": 2})
    org.post(f"{BASE}/sessions/{sid}/timer/extend", json={"minutes": 10})
    ext = tm(org, sid)["extensions"]
    assert [e["minutes"] for e in ext] == [2, 10] and ext[0]["at"].startswith("2027-")
    assert tm(org, sid)["remaining_seconds"] == 480 - 60 + 720


def test_extending_a_stage_with_no_timer_is_refused(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "board")
    assert org.post(f"{BASE}/sessions/{sid}/timer/extend", json={"minutes": 5}).status_code == 409


def test_sending_everyone_to_their_rooms_starts_the_rooms_clock_now(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    w.now[0] = T0 + 100
    org.post(f"{BASE}/sessions/{sid}/briefing/send")
    assert (tm(org, sid)["stage"], tm(org, sid)["remaining_seconds"]) == ("private_rooms", 480)


def test_the_split_of_the_session_is_what_is_timed(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", length_minutes=10, split={"briefing": 1, "individual": 5, "together": 4})
    assert tm(org, sid)["remaining_seconds"] == 60


@pytest.mark.parametrize("company", ["co-a", "co-b", "co-none"])
def test_every_industry_and_a_solo_session_have_a_timer(w, company):
    org = w.login("org", company)
    sid = session_at(w, org, company, "briefing", seats=1)
    assert tm(org, sid)["timed"] is True


def test_empty_company_and_another_company_have_no_such_session(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    assert w.login("e", "co-empty").get(f"{BASE}/sessions/{sid}/timer").status_code == 404
    assert w.login("b", "co-b").post(f"{BASE}/sessions/{sid}/timer/extend", json={"minutes": 2}).status_code == 404
