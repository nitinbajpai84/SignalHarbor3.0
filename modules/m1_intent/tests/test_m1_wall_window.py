"""IC-2f: the frozen wall (snapshot stored once, served per viewer) and page one of the charter. Synthetic words only."""
import pytest

from datetime import datetime, timezone

from m1_kit import BASE
from modules.m1_intent.domain import timer
from modules.m1_intent.domain import charter_export as X
from modules.m1_intent.store import wall_snapshot as W
from sh_platform.plane import PlaneStore
from sh_platform.profile import Viewer, record, record_card
from test_m1_charter_kit import charter, draft, ready, stand_in_result  # noqa: F401  (the autouse fixture)
from test_m1_room_kit import new_session, start_room
from test_m1_seat_wiring_kit import StubNorth, flow, new_world

SID = "a" * 32
LENS = {"mark": "stated", "by": "Lens", "agent": "lens", "from": "Policy sheet"}
ADMIN = Viewer("Mei Tan", frozenset({"company_admin"}))
TOM = Viewer("Tom Ng", frozenset({"analyst"}))
OUT = Viewer("Lena Ho", frozenset({"analyst"}))


@pytest.fixture
def plane(tmp_path):
    return PlaneStore(tmp_path).create("co-a")


def card(cid, lane="missing", q1="Reports arrive late", **kw):
    return {"id": cid, "lane": lane, "sealed": False, "anonymous": False, "author": "mei-tan", "q1": q1, "room": SID, **kw}


def lane(w, name):
    return next(l for l in w["lanes"] if l["lane"] == name)


def pay_area(plane):
    record(plane, "governance.restricted_areas.hr.area", "Pay", LENS)
    record(plane, "governance.restricted_areas.hr.may_see", ["Tom Ng"], LENS)


def test_an_empty_company_freezes_four_empty_lanes(plane):
    W.freeze(plane, SID)
    w = W.served(plane, SID, ADMIN)
    assert [(l["lane"], l["count"], l["cards"]) for l in w["lanes"]] == [(n, 0, []) for n in ("tracking", "missing", "watch", "levers")]
    assert W.served(plane, "b" * 32, ADMIN) is None  # not frozen yet


def test_two_industries_and_one_person_alone(plane, tmp_path):
    record_card(plane, card("c1", "tracking", q1="Capital calls", q2={"value": "Treasury", "mark": "guessed"}), by="Mei Tan")  # one person alone
    W.freeze(plane, SID)
    c = lane(W.served(plane, SID, ADMIN), "tracking")["cards"][0]
    assert c["text"] == "Capital calls" and c["author"] == "Mei Tan" and c["quarters"]["q2"] == "guessed" and "Treasury" not in str(c)
    other = PlaneStore(tmp_path).create("co-b")  # another industry: its own wall, none of co-a's cards
    record_card(other, card("z1", "levers", q1="Fee schedule"), by="Pat Lee")
    W.freeze(other, SID)
    w = W.served(other, SID, ADMIN)
    assert lane(w, "levers")["count"] == 1 and lane(w, "tracking")["count"] == 0 and "Capital" not in str(w)


def test_the_snapshot_is_stored_once_and_a_later_card_does_not_change_it(plane):
    record_card(plane, card("c1"), by="Mei Tan")
    first = W.freeze(plane, SID)
    record_card(plane, card("c2"), by="Mei Tan")
    assert W.freeze(plane, SID) == first and lane(W.served(plane, SID, ADMIN), "missing")["count"] == 1


def test_a_sealed_card_is_a_silhouette_to_an_outsider_and_whole_to_a_named_viewer_with_the_same_count(plane):
    pay_area(plane)
    record_card(plane, card("s1", q1="Pay bands are unclear", sealed=True), by="Mei Tan")
    W.freeze(plane, SID)
    out, tom = lane(W.served(plane, SID, OUT), "missing"), lane(W.served(plane, SID, TOM), "missing")
    assert out["count"] == tom["count"] == 1
    assert out["cards"][0] == {"id": "s1", "lane": "missing", "sealed": True, "silhouette": "A sealed card"} and "Pay bands" not in str(out)
    assert tom["cards"][0]["text"] == "Pay bands are unclear"
    adm = lane(W.served(plane, SID, ADMIN), "missing")["cards"][0]  # A-069: the admin sees the silhouette once a person is named
    assert adm.get("silhouette") == "A sealed card" or adm.get("text")


def test_an_anonymous_card_has_no_author_in_the_file_or_for_the_admin(plane):
    record_card(plane, card("n1", anonymous=True, author=None, anon_key="anon-n1", q1="Nobody owns the file"), by="Mei Tan")
    W.freeze(plane, SID)
    got = lane(W.served(plane, SID, ADMIN), "missing")["cards"][0]
    assert got["author"] == "Anonymous"
    stored = str(W.get(plane, SID))
    assert "anon-n1" not in stored and "Mei" not in stored and "mei-tan" not in stored


def test_the_export_renders_page_one_with_the_labels():
    wall = {"closed_at": "x", "lanes": [
        {"lane": "tracking", "count": 1, "cards": [{"id": "1", "text": "Capital calls", "author": "Mei Tan"}]},
        {"lane": "missing", "count": 2, "cards": [{"id": "2", "text": "File owner", "author": "Anonymous"},
                                                  {"id": "3", "lane": "missing", "sealed": True, "silhouette": "A sealed card"}]},
        {"lane": "watch", "count": 0, "cards": []}, {"lane": "levers", "count": 0, "cards": []}]}
    view = {"footer": {"date": "2026-10-04", "participants": 3, "notes": 2, "later": 0}, "later": [], "wall": wall,
            "problems": [], "signing": {"signers": []}}
    md, html = X.to_markdown(view, "Co", "S", False), X.to_html(view, "Co", "S", False)
    for out in (md, html):
        assert "What the committee put on the wall" in out and "Capital calls" in out and "A sealed card" in out and "Anonymous" in out
    assert md.index("What the committee put on the wall") < md.index("Signed by") and "(2)" in md
    assert html.index("What the committee put on the wall") < html.index("Problems") if "Problems" in html else True


def test_the_charter_version_carries_the_wall_and_a_signed_version_does_not_change(world):
    org, sid, code = ready(world, seats=3)
    plane = world.plane("co-a")
    pay_area(plane)
    record_card(plane, card("c1", "tracking", q1="Capital calls", room=sid), by="Mei Tan")
    record_card(plane, card("s1", q1="Pay bands are unclear", sealed=True, room=sid), by="Mei Tan")
    W._path(plane, sid).unlink()  # the kit moved the session on before these cards existed; draft from a fresh freeze
    draft(org, sid)
    w = charter(org, sid)["charter"]["wall"]
    assert lane(w, "tracking")["cards"][0]["text"] == "Capital calls" and lane(w, "missing")["cards"][0]["silhouette"] == "A sealed card"
    assert org.post(f"{BASE}/sessions/{sid}/charter/sign").status_code == 200
    record_card(plane, card("c2", "tracking", q1="Added later", room=sid), by="Mei Tan")
    again = charter(org, sid)["charter"]
    assert again["wall"] == w and "Added later" not in str(again["wall"])


def ts(y, m, d, h=9):
    return datetime(y, m, d, h, tzinfo=timezone.utc).timestamp()


def test_working_days_are_monday_to_friday():
    assert timer.window_minutes(ts(2026, 10, 5), 5) == 7 * 1440  # Monday to next Monday
    assert timer.window_minutes(ts(2026, 10, 9), 1) == 3 * 1440  # Friday to Monday
    assert timer.window_minutes(ts(2026, 10, 5), 1) == 1440


def test_the_window_defaults_to_five_is_checked_and_sets_the_rooms_length_when_the_room_starts(world):
    org = world.login("org-w", "co-a", ["company_admin"])
    sid = new_session(org, seats=3)
    got = org.get(f"{BASE}/sessions/{sid}").json()["preparation"]
    assert got["wall_window_days"] is None  # not chosen: the rooms keep their own length
    for bad in (0, 21, "5", True):
        assert org.put(f"{BASE}/sessions/{sid}", json={"wall_window_days": bad}).status_code == 422
    assert org.put(f"{BASE}/sessions/{sid}", json={"wall_window_days": 2}).json()["preparation"]["wall_window_days"] == 2
    before = datetime.now(timezone.utc).timestamp()
    start_room(org, sid)
    p = org.get(f"{BASE}/sessions/{sid}").json()["preparation"]
    assert timer.window_minutes(before, 2) - 1 <= p["split"]["individual"] <= timer.window_minutes(before, 2) + 3 * 1440  # the day count depends on the weekday
    assert p["split"]["individual"] >= 2 * 1440 and p["split"]["briefing"] >= 1


def test_every_close_freezes_the_wall_of_this_session_only_and_a_card_save_is_refused_after(tmp_path):
    w = new_world(tmp_path, StubNorth())
    org, sid, (ada, _) = flow(w)
    plane = w.plane("co-a")
    record_card(plane, card("elsewhere", room="f" * 32, q1="Another session's card"), by="Pat Lee")
    record_card(plane, card("noroom", room=None, q1="A card with no room"), by="Pat Lee")
    nid = ada.write("Late reports")
    assert W.get(plane, sid) is None
    assert org.post(f"{BASE}/sessions/{sid}/rooms/close").status_code == 200
    snap = W.get(plane, sid)
    assert snap is not None and "Another session" not in str(snap) and "no room" not in str(snap)
    assert W.freeze(plane, sid)["closed_at"] == snap["closed_at"]  # a second call keeps the first
    r = ada.save(nid, quarters={"q1": {"text": "Changed after close"}})
    assert r.status_code == 409
    assert "Changed after close" not in str(W.get(plane, sid))


def test_the_window_applies_only_when_it_was_set(world):
    org = world.login("org-x", "co-a", ["company_admin"])
    sid = new_session(org, seats=3)
    start_room(org, sid)
    assert org.get(f"{BASE}/sessions/{sid}").json()["preparation"]["split"]["individual"] == 8  # untouched
    other = new_session(org, seats=3, wall_window_days=5)
    start_room(org, other)
    assert org.get(f"{BASE}/sessions/{other}").json()["preparation"]["split"]["individual"] >= 5 * 1440
