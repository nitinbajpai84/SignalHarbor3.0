"""B12 (files 23, 24, 25): the wall inside an intent: resolved from the intent, header fields, card fields, suggestions. Synthetic data only."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m1_intent.domain import notes_quarters as Q
from modules.m1_intent.store.notes import SuggestionStore
from sh_platform.intents import wall
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile import store as profile_store

CO, SID = "co-a", "a" * 32
SPEC = Q.load()


class Accounts:
    def get(self, account_id):
        return {"display_name": account_id}

    def in_company(self, company):
        return []


@pytest.fixture
def world(tmp_path):
    plane = PlaneStore(tmp_path).create(CO)
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = Accounts()
    app.include_router(wall.router)

    @app.middleware("http")
    async def who(request, call_next):
        account, roles = request.headers.get("x-account", "none"), request.headers.get("x-roles", "participant").split(",")
        request.state.company_id, request.state.account_id, request.state.roles = CO, account, roles
        return await call_next(request)

    return SimpleNamespace(plane=plane, client=TestClient(app))


def intent(world, iid="i1", **over):
    rec = {"id": iid, "type": "initiative", "title": "Cash by custodian", "purpose": "See cash before 9am", "created_by": "janet", "state": "open",
           "people": {"organiser": "janet", "sponsor": "daniel", "participants": ["aaron", "katie"], "observers": ["grace"], "affected": ["harvey"]},
           "time_box": {"ends": "2026-10-16T17:00:00+00:00"}, "affected_may_read": False,
           "stages": [{"key": "think_unfiltered", "state": "open", "wall": {"frozen_at": None}}, {"key": "define_strategically", "state": "pending"}],
           "refs": {"wall_session_ids": [SID]}, **over}
    write_json_atomic(world.plane.path("intents", iid, "intent.json"), rec)
    return rec


def get(world, who, roles="participant", iid="i1"):
    return world.client.get(f"/api/intents/{iid}/wall", headers={"x-account": who, "x-roles": roles})


def card(world, cid, lane="missing", author="aaron-lyle", anonymous=False, sealed=False, room=SID):
    prov = {"mark": "stated", "by": "Test", "from": "A note in the private room"}
    for f, v in (("lane", lane), ("room", room), ("author", author), ("anonymous", anonymous), ("sealed", sealed), ("q1", "Late cash report")):
        profile_store.record(world.plane, f"cards.{cid}.{f}", v, prov)


def test_the_wall_resolves_from_the_intent_and_carries_the_header_fields(world):
    intent(world)
    card(world, "c1", author="aaron-lyle")
    body = get(world, "janet", "company_admin").json()
    assert body["session_id"] == SID and body["role"] == "organiser" and body["can_add"] is True
    assert body["intent"] == {"title": "Cash by custodian", "purpose": "See cash before 9am", "type": "initiative", "state": "open", "ends": "2026-10-16T17:00:00+00:00"}
    assert [s["name"] for s in body["stages"]] == ["Think unfiltered", "Define strategically"]
    assert body["people"] == {"invited": 3, "joined": None, "initials": ["AL"]}  # no room file yet: joined is not known, never zero
    assert body["counts"] == {"total": 1, "per_lane": {"intent": 0, "pain_point": 1, "future_signal": 0, "lever": 0}, "withdrawn": 0}


def test_the_session_comes_from_a_stage_ref_when_refs_is_empty(world):
    intent(world, refs={"wall_session_ids": []}, stages=[{"key": "think_unfiltered", "state": "open", "ref": {"kind": "wall_session", "id": SID}}])
    assert get(world, "aaron").json()["session_id"] == SID
    intent(world, iid="i2", refs={}, stages=[])
    assert get(world, "janet", iid="i2").json()["session_id"] is None


@pytest.mark.parametrize("who,role,add", [("janet", "organiser", True), ("daniel", "sponsor", False), ("aaron", "participant", True), ("grace", "observer", False)])
def test_each_role_is_named_and_only_the_writers_may_add(world, who, role, add):
    intent(world)
    body = get(world, who).json()
    assert body["role"] == role and body["can_add"] is add


def test_who_may_open_it(world):
    intent(world)
    assert get(world, "stranger").status_code == 404  # may not know it exists
    assert get(world, "boss", "company_admin").status_code == 403  # sees it exists, never the wall
    assert get(world, "harvey").status_code == 403  # affected, reading switched off
    intent(world, affected_may_read=True)
    assert get(world, "harvey").json()["role"] == "affected" and get(world, "harvey").json()["can_add"] is False
    intent(world, state="draft")
    assert get(world, "aaron").status_code == 404 and get(world, "janet").status_code == 200  # a draft is the starter's alone
    assert get(world, "janet", iid="nope").status_code == 404 and get(world, "janet", iid="..").status_code == 404


def test_cards_gain_the_intent_fields_once_and_initials_never_leak_anonymous_or_sealed_authors(world):
    intent(world, type="brainstorm")
    card(world, "c1", author="aaron-lyle")
    card(world, "c2", author="katie-rao", anonymous=True)
    card(world, "c3", author="harvey-rowley", sealed=True)
    card(world, "c4", author="daniel-kerr", room="b" * 32)  # another wall: not this intent's
    body = get(world, "janet", "company_admin").json()
    assert body["people"]["initials"] == ["AL"] and body["counts"]["total"] == 3
    cards = profile_store.raw(world.plane)["cards"]
    for k in ("c1", "c2", "c3"):
        got = {f: cards[k][f]["value"] for f in ("intent_id", "session_kind", "withdrawn", "edits", "moves")}
        assert got == {"intent_id": "i1", "session_kind": "brainstorm", "withdrawn": None, "edits": [], "moves": []}
    assert "intent_id" not in cards["c4"]
    assert wall.stamp_cards(world.plane, "i1", "brainstorm", [SID]) == 0  # nothing left to stamp
    assert get(world, "grace").json()["counts"]["total"] == 3  # a reader does not write, and reads the same numbers


def test_a_withdrawn_card_is_kept_with_its_words_and_leaves_every_count(world):
    intent(world)
    card(world, "c1")
    card(world, "c2", lane="levers", author="katie-rao")
    wall.withdraw_card(world.plane, "c1", by="aaron-lyle", at="2026-10-08T09:00:00+00:00")
    kept = profile_store.raw(world.plane)["cards"]["c1"]
    assert kept["q1"]["value"] == "Late cash report" and kept["withdrawn"]["value"] == {"by": "aaron-lyle", "at": "2026-10-08T09:00:00+00:00"}
    body = get(world, "janet", "company_admin").json()
    assert body["counts"] == {"total": 1, "per_lane": {"intent": 0, "pain_point": 0, "future_signal": 0, "lever": 1}, "withdrawn": 1}
    assert body["people"]["initials"] == ["KR"]  # the withdrawn card's author shows nowhere
    with pytest.raises(ValueError):
        wall.withdraw_card(world.plane, "c1", by="aaron-lyle")  # never restored, never withdrawn twice
    with pytest.raises(LookupError):
        wall.withdraw_card(world.plane, "zz", by="aaron-lyle")


def row(kind, text):
    return Q.suggest(SPEC, [{"kind": kind, "text": text, "from": "the pack"}])[0]


def test_hide_and_unhide_move_one_row_for_one_seat_and_count_it(world):
    intent(world)
    a, b = row("lever", "Close earlier"), row("lever", "Pay faster")
    store = SuggestionStore(world.plane)
    store.put(SID, "seat1", [a, b])
    store.put(SID, "seat2", [a])
    assert wall.hide(world.plane, "i1", SID, "seat1", a["id"]) is True
    assert [r["id"] for r in store.get(SID, "seat1")] == [b["id"]] and [r["id"] for r in store.get(SID, "seat2")] == [a["id"]]
    assert wall.hide(world.plane, "i1", SID, "seat1", a["id"]) is False  # not there any more
    assert wall._read(world.plane, "i1")["counts"]["hidden"] == 1
    assert wall.unhide(world.plane, "i1", SID, "seat2", a["id"]) is False  # hidden by seat1, not seat2
    assert wall.unhide(world.plane, "i1", SID, "seat1", a["id"]) is True
    assert {r["id"] for r in store.get(SID, "seat1")} == {a["id"], b["id"]}
    assert wall._read(world.plane, "i1")["counts"]["hidden"] == 0


def test_top_up_keeps_three_per_lane_and_never_offers_a_hidden_or_held_text_again():
    pool = [{"kind": "pain_point", "text": f"Pain {i}", "from": "Board paper"} for i in range(6)] + [{"kind": "lever", "text": "Close earlier", "from": "p"}]
    fresh = Q.suggest(SPEC, pool)  # three pain points and the lever
    held, hidden = [row("pain_point", "Pain 0")], [row("pain_point", "Pain 1")]
    got = wall.top_up(3, False, held, hidden, [{"text": "close earlier"}], fresh)
    assert [r["text"] for r in got] == ["Pain 2"]  # Pain 0 held, Pain 1 hidden, the lever is already a card
    full = [row("pain_point", f"Own {i}") for i in range(3)]
    assert wall.top_up(3, False, full, [], [], fresh) == [r for r in fresh if r["kind"] == "lever"]  # a full lane gets nothing, another lane may
    assert len([r for r in wall.top_up(3, False, [], [], [], fresh) if r["kind"] == "pain_point"]) == 3


def test_a_brainstorm_has_three_suggestions_in_all():
    fresh = Q.suggest(SPEC, [{"kind": k, "text": f"{k} {i}", "from": "p"} for k in ("pain_point", "lever") for i in range(3)])
    assert len(wall.top_up(3, True, [], [], [], fresh)) == 3
    assert len(wall.top_up(3, True, [row("lever", "Mine")], [], [], fresh)) == 2
    assert wall.top_up(3, True, [row("lever", f"M{i}") for i in range(3)], [], [], fresh) == []


def test_a_real_record_names_people_as_entries_not_strings(world):
    """T12: Initiative records carry {account_id, name} entries, an unlinked person has account_id null."""
    p = {"organiser": {"account_id": "janet", "name": "Janet Shaw"}, "sponsor": {"account_id": None, "name": "Daniel Kerr"},
         "participants": [{"account_id": "aaron", "name": "Aaron Lyle"}, {"account_id": None, "name": "Harvey Rowley"}],
         "observers": [{"account_id": "grace", "name": "Grace Ward"}], "affected": []}
    intent(world, people=p)
    assert [get(world, w).json()["role"] for w in ("janet", "aaron", "grace")] == ["organiser", "participant", "observer"]
    assert get(world, "janet").json()["people"]["invited"] == 3
    assert get(world, "stranger").status_code == 404


def test_readers_get_lane_cards_with_initials_and_no_sealed_or_anonymous_words(world):
    """T12: the session routes serve only seat holders, so a reader's cards come from this route."""
    intent(world)
    card(world, "c1", author="aaron-lyle")
    card(world, "c2", author="katie-rao", anonymous=True)
    card(world, "c3", lane="levers", author="harvey-rowley", sealed=True)
    cards = get(world, "grace").json()["cards"]  # no session state on file: the rooms count as open, so only silhouettes
    assert sorted(c["lane"] for c in cards) == ["lever", "pain_point", "pain_point"] and all(c["text"] == "" for c in cards)
    assert get(world, "janet").json()["cards"] is None
    rows = wall.reader_cards([{"id": "x", "lane": {"value": "missing"}, "q1": {"value": "Late cash"}, "author": {"value": "aaron-lyle"}, "anonymous": {"value": False}}], False)
    assert rows[0]["text"] == "Late cash" and rows[0]["author"] == "AL" and rows[0]["lane"] == "pain_point"
    anon = wall.reader_cards([{"id": "y", "lane": {"value": "missing"}, "q1": {"value": "Worry"}, "anonymous": {"value": True}}], False)[0]
    assert anon["author"] is None and anon["anonymous"] is True


def test_closing_the_rooms_and_freezing_write_the_wall_times_once(world):
    """T12/R7: the m1 routes call mark_wall; the intent's stage gets each time once, and a session with no intent changes nothing."""
    from sh_platform.intents import store as S
    iid = "ini-" + "c" * 32
    rec = {"id": iid, "type": "initiative", "state": "open", "version": 1, "stages": [{"key": "think_unfiltered", "state": "open"}], "refs": {"wall_session_ids": [SID]}}
    S.write_intent(world.plane, rec, create=True)
    wall.mark_wall(world.plane, "f" * 32, "frozen_at")  # not this intent's session
    wall.mark_wall(world.plane, SID, "rooms_closed_at")
    first = S.read_intent(world.plane, iid)["stages"][0]["wall"]["rooms_closed_at"]
    wall.mark_wall(world.plane, SID, "rooms_closed_at")
    wall.mark_wall(world.plane, SID, "frozen_at")
    w = S.read_intent(world.plane, iid)["stages"][0]["wall"]
    assert w["rooms_closed_at"] == first and w["frozen_at"]


def test_a_submitted_note_keeps_its_four_quarters_on_the_card(world):
    from modules.m1_intent.store.notes import _card, _write_cards
    cell = lambda t, m="stated": {"text": t, "mark": m, "from": "you"}  # noqa: E731
    note = {"id": "n" * 16, "text": "Late cash", "kind": "pain_point", "anonymous": False, "author_name": "Aaron Lyle",
            "quarters": {"q1": cell("Late cash"), "q2": cell("Every Monday", "guessed"), "q3": {"text": "", "mark": "unknown", "from": None}, "q4": cell("Ops")}}
    _write_cards([note], SID, world.plane)
    c = profile_store.raw(world.plane)["cards"]["n" * 16]
    assert [_val(c, q) for q in ("q1", "q2", "q3", "q4")] == ["Late cash", "Every Monday", None, "Ops"] and c["q2"]["mark"] == "guessed"
    assert _card(note, SID)["q3"] is None


def _val(c, f):
    return c[f]["value"] if f in c else None


def test_seat_person_finds_the_seat_by_the_keyed_seat_id(world, monkeypatch):
    """F45: the notes store hands the keyed seat id to person_contributed, so the seat must be found by it (not only by n or participant id)."""
    from modules.m1_intent.domain.seat_identity import seat_id_of
    from modules.m1_intent.store.room import RoomStore
    seat = {"n": 1, "state": "taken", "participant_id": "p1", "account_id": "acct-aaron", "name": "Aaron"}
    monkeypatch.setattr(RoomStore, "get", lambda self, sid: {"seats": [seat, {"n": 2, "state": "free"}]})
    keyed = seat_id_of(world.plane, SID, seat)
    assert wall._seat_person(world.plane, SID, keyed) is seat
    assert wall._seat_person(world.plane, SID, 1) is seat and wall._seat_person(world.plane, SID, "nobody") is None
