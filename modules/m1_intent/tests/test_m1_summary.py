"""The summary page: built from the board's and the charter's own views, never attributing an anonymous note, refusing
before the rooms close, strangers and other companies, working with notes that have no kind, and honouring the names rule."""
import json

from fastapi.testclient import TestClient

from modules.m1_intent.api import summary as S
from modules.m1_intent.store.notes import NoteStore
from modules.m1_intent.store.sessions import SessionStore
from test_m1_board_kit import NOTES, Board, GatherStub, grouped, together
from test_m1_kinds import put


def summary(b, who=None):
    return b.org_call("GET", "/summary") if who is None else who.call("GET", "/summary")


def vote_and_tick(b, hidden=True):
    late = b.cluster("Calls arrive too late")["id"]
    for who in b.guests:
        assert who.call("POST", f"/together/clusters/{late}/vote", json={"option": "must"}).status_code == 200
    assert b.org_call("POST", f"/together/clusters/{late}/tick", json={"ticked": True}).status_code == 200
    assert b.guests[0].call("POST", f"/together/clusters/{late}/comments", json={"text": "Named remark"}).status_code == 200
    if hidden:
        assert b.guests[1].call("POST", f"/together/clusters/{late}/comments", json={"text": "Hidden remark", "anonymous": True}).status_code == 200
    return late


ALL_NAMED = [(t, False) for t, _ in NOTES]


def test_it_refuses_before_the_rooms_close_with_a_plain_409(tmp_path):
    early = Board(tmp_path)
    r = summary(early)
    assert r.status_code == 409 and "private rooms have closed" in r.json()["message"]


def test_it_holds_the_sections_and_is_built_from_the_board_and_charter_views(tmp_path):
    b = together(tmp_path)
    vote_and_tick(b)
    assert b.org_call("POST", "/charter", json={"confirm": True}).status_code in (200, 201)
    d = summary(b).json()
    assert d["board"] == b.org_call("GET", "/board").json()  # the same view, so they cannot differ
    assert d["charter"] == b.org_call("GET", "/charter").json()["charter"]
    assert d["session"]["people_count"] >= 2 and {"name", "role"} <= set(d["session"]["people"][0])
    by = {g["id"]: [i["name"] for i in g["items"]] for g in d["intent"]}
    assert by["must"] == ["Calls arrive too late"] and "No single exposure view" in by["open"]
    assert [g["id"] for g in d["intent"]] == ["must", "should", "could", "not_this_time", "open"]
    assert d["pain_points"] == d["future_signals"] == d["levers"] == []  # only intent notes: empty, no failure
    assert d["can_download"] is False  # not signed


def test_a_guest_sees_the_same_page_and_strangers_and_other_companies_do_not(tmp_path):
    b = together(tmp_path)
    assert [c["name"] for c in summary(b, b.guests[0]).json()["board"]["clusters"]] == [c["name"] for c in summary(b).json()["board"]["clusters"]]
    other = b.w.login("other-co", "co-b", ["company_admin"])
    assert other.get(b.url("/summary")).status_code in (403, 404)
    assert TestClient(b.w.app).get(b.url("/summary")).status_code in (401, 403)
    same_company = b.w.login("outsider", "co-a", ["participant"])
    assert same_company.get(b.url("/summary")).status_code in (403, 404)


def test_choice_mode_never_attributes_an_anonymous_note_and_counts_it_apart(tmp_path):
    six = tuple(f"Guest Number{i}" for i in range(1, 7))  # six seated people: not a small group, so the rows are listed
    b = together(tmp_path, seats=8, names=six)
    vote_and_tick(b)
    r = summary(b)
    d = r.json()
    c = d["contributions"]
    assert c["mode"] == "choice" and "small_group" not in c
    assert c["anonymous"] == {"notes": 2, "comments": 1, "total": 3}
    named = {p["name"]: p for p in c["people"]}
    assert sum(p["notes"] for p in named.values()) == 4  # the four named notes only
    assert sum(p["comments"] for p in named.values()) == 1
    assert sum(p["votes"] for p in named.values()) == 6
    anon = [n for cl in d["board"]["clusters"] for n in cl["notes"] if n["anonymous"]] + [n for n in d["board"]["on_its_own"] if n["anonymous"]]
    assert anon and all("author_name" not in n for n in anon)


def test_a_small_group_with_anonymous_notes_lists_no_one_by_name(tmp_path):
    b = together(tmp_path)  # two seated guests and an organiser seat: well under six
    vote_and_tick(b)
    c = summary(b).json()["contributions"]
    assert c["small_group"] is True and c["people"] is None and c["anonymous"]["total"] == 3
    assert b.org_call("GET", "/summary").json()["session"]["people_count"] <= 5


def test_anonymous_mode_hides_a_name_even_on_a_stored_note_that_carries_one(tmp_path):
    b = together(tmp_path, prep={"names": "anonymous"})
    store = NoteStore(b.w.plane(b.company))
    from modules.m1_intent.store.files import read_json, write_json
    path = store._path("notes", b.sid)
    data = read_json(path)
    data["notes"] = [{**n, "anonymous": False, "author_name": "Ada Guest", "kind": "pain_point"} for n in data["notes"]]
    write_json(path, data)
    d = summary(b).json()
    text = json.dumps({k: v for k, v in d.items() if k not in ("session", "charter")})
    assert "Ada Guest" not in text and d["pain_points"] and all(x["anonymous"] for x in d["pain_points"])
    assert d["board"] == b.org_call("GET", "/board").json()


def test_named_mode_opens_the_contributions_table_by_name(tmp_path):
    b = together(tmp_path, notes=ALL_NAMED, prep={"names": "named"})
    vote_and_tick(b, hidden=False)
    c = summary(b).json()["contributions"]
    assert c["mode"] == "named" and c["anonymous"] is None
    by = {p["name"]: p for p in c["people"]}
    assert by["Ada Guest"]["notes"] == 3 and by["Ben Guest"]["notes"] == 3 and by["Ada Guest"]["comments"] == 1


def test_anonymous_mode_shows_totals_and_no_author_name_anywhere(tmp_path):
    b = together(tmp_path, prep={"names": "anonymous"})
    vote_and_tick(b)
    d = summary(b).json()
    assert d["contributions"] == {"mode": "anonymous", "totals": {"notes": 6, "comments": 2, "votes": 2}, "people": None, "anonymous": None}
    text = json.dumps({k: v for k, v in d.items() if k not in ("session", "charter")})
    assert "author_name" not in text and "Ada Guest" not in text and "Ben Guest" not in text
    assert all(n["anonymous"] for cl in d["board"]["clusters"] for n in cl["notes"])


def test_it_reads_pain_points_future_signals_and_levers_from_real_notes(tmp_path):
    b = Board(tmp_path, GatherStub({}), notes=())
    ada, ben = b.guests
    put(ada, "pain_point", "The meeting pack takes two days")
    put(ben, "future_signal", "Rate moves could change funding costs", anonymous=True)
    put(ada, "lever", "We can change how fast we commit")
    put(ben, "intent", "Know our funding headroom every week")
    b.close_rooms()
    d = summary(b).json()
    pain = d["pain_points"][0]
    assert pain["text"] == "The meeting pack takes two days" and pain["author_name"] == "Ada Guest"
    assert pain["details"] == [{"label": "Who is affected", "values": ["The finance team"]}, {"label": "How often", "values": ["Every month"]},
                               {"label": "KPI it shows up in", "values": ["Pack preparation time"]}]
    sig = d["future_signals"][0]
    assert sig["anonymous"] is True and "author_name" not in sig and sig["details"][0]["values"] == ["Central bank rate decisions"]
    assert d["levers"][0]["details"] == [{"label": "KPIs it moves", "values": ["Funding headroom, Cash buffer"]}]
    assert [len(d[k]) for k in ("pain_points", "future_signals", "levers")] == [1, 1, 1]  # the intent note is not listed here


def test_the_summary_equals_the_standalone_board_and_charter_for_a_seat_and_a_guest(tmp_path):
    b = together(tmp_path)
    vote_and_tick(b)
    assert b.org_call("POST", "/charter", json={"confirm": True}).status_code in (200, 201)
    for who in (None, *b.guests):
        call = (lambda p: b.org_call("GET", p)) if who is None else (lambda p, w=who: w.call("GET", p))
        d = call("/summary").json()
        assert d["board"] == call("/board").json()
        assert d["charter"] == call("/charter").json()["charter"]


def test_a_guest_outside_the_thirty_day_window_is_refused(tmp_path):
    import time
    b = together(tmp_path)
    vote_and_tick(b)
    assert b.org_call("POST", "/charter", json={"confirm": True}).status_code == 201
    SessionStore(b.w.plane(b.company)).transition(b.sid, "closed")
    assert b.guests[0].call("GET", "/summary").status_code == 200
    b.w.app.state.m1_clock = lambda: time.time() + 31 * 86400
    assert b.guests[0].call("GET", "/summary").status_code == 401


def test_the_page_still_opens_after_the_session_closes(tmp_path):
    b = together(tmp_path)
    vote_and_tick(b)
    assert b.org_call("POST", "/charter", json={"confirm": True}).status_code in (200, 201)
    store = SessionStore(b.w.plane(b.company))
    for stage in ("closed",):
        store.transition(b.sid, stage)
    r = summary(b)
    assert r.status_code == 200 and r.json()["session"]["stage"] == "closed"
    assert S.NOT_YET


def test_two_people_cannot_take_seats_under_the_same_name(tmp_path):
    from m1_kit import BASE
    from test_m1_room_kit import guest, join, start_room
    from test_m1_seat_wiring_kit import new_world
    from test_m1_room_kit import new_session
    w = new_world(tmp_path)
    org = w.login("org co-a", "co-a", ["sponsor"])
    code = start_room(org, new_session(org, seats=3))
    assert join(guest(w), code, 1, name="Ada Guest").status_code == 200
    r = join(guest(w), code, 2, name="ada  guest")
    assert r.status_code == 409 and r.json()["message"] == "Someone in this session already uses that name. Please add your surname."
    assert join(guest(w), code, 2, name="Ada Guest-Lim").status_code == 200
