"""IC-2a: the four wall questions on a card (A-055) and North's suggestion cards (A-056). Model stubbed; synthetic words only."""
import pytest

from modules.m1_intent.domain import notes_quarters as Q
from modules.m1_intent.domain.private_room import RoomError
from m1_kit import BASE as API
from modules.m1_intent.store.notes import SuggestionStore
from sh_platform.context_docs.store import DocStore
from sh_platform.profile import store as profile
from test_m1_briefing_kit import make_world, seated, session_at
from test_m1_lean_room import MEI, interview, room, tie
from test_m1_seat_wiring_kit import StubNorth, flow, new_world

SPEC = Q.load()
BASE = {"id": "n1", "text": "Late reports", "state": "draft", "history": [], "fields": {}}


def test_the_four_questions_come_in_order_from_the_contract():
    assert [q["id"] for q in SPEC.questions] == ["q1", "q2", "q3", "q4"]
    note = Q.start(BASE)
    assert Q.next_open(note) == "q1"
    note = Q.answer(SPEC, note, {"q1": {"text": "Reports arrive late"}})
    assert Q.next_open(note) == "q2"
    assert Q.lead(SPEC, note, "q2") == SPEC.get("q2")["lead"]


def test_a_draft_from_the_interview_shows_its_source_and_keep_accepts_it():
    note = Q.start(BASE, {"q2": {"text": "Finance, monthly", "from": "Interview with Ada", "source": "interview"}})
    assert "Interview with Ada" in Q.lead(SPEC, note, "q2") and "Finance, monthly" in Q.lead(SPEC, note, "q2")
    kept = Q.answer(SPEC, note, {"q2": {"keep": True}})
    assert kept["quarters"]["q2"] == {"text": "Finance, monthly", "mark": "stated", "from": "Interview with Ada"}
    assert "q2" not in kept["quarter_drafts"]


def test_change_replaces_the_draft_with_what_the_person_typed():
    note = Q.start(BASE, {"q2": {"text": "Finance, monthly", "from": "Interview with Ada", "source": "interview"}})
    out = Q.answer(SPEC, note, {"q2": {"text": "Everyone, weekly"}})
    assert out["quarters"]["q2"] == {"text": "Everyone, weekly", "mark": "stated", "from": "you"}
    assert out["quarter_drafts"] == {}


def test_a_quarter_kept_from_a_document_is_guessed_and_names_the_document():
    note = Q.start(BASE, {"q3": {"text": "The monthly pack", "from": "Reporting guide", "source": "document"}})
    kept = Q.answer(SPEC, note, {"q3": {"keep": True}})
    assert kept["quarters"]["q3"]["mark"] == "guessed" and kept["quarters"]["q3"]["from"] == "Reporting guide"
    assert kept["quarters"]["q4"]["mark"] == "unknown"
    with pytest.raises(RoomError):
        Q.answer(SPEC, kept, {"q1": {"keep": True}})  # no draft waiting


def test_i_dont_know_is_accepted_on_questions_two_to_four_but_not_the_first():
    note = Q.answer(SPEC, Q.start(BASE), {"q4": {"text": "I don't know"}})
    assert note["quarters"]["q4"]["mark"] == "unknown" and Q.next_open(note) == "q1"
    assert Q.answered(note) == 0
    assert Q.answer(SPEC, Q.start(BASE), {"q2": {"text": "I don't know"}, "q3": {"text": "no idea"}})["quarters"]["q3"]["mark"] == "unknown"
    with pytest.raises(RoomError):
        Q.answer(SPEC, Q.start(BASE), {"q1": {"text": "I don't know"}})  # the first question must be answered


def test_two_answered_quarters_may_be_placed_and_one_is_refused():
    note = Q.answer(SPEC, Q.start(BASE), {"q1": {"text": "Late reports"}})
    with pytest.raises(RoomError, match="at least 2 of the four"):
        Q.check_placeable(SPEC, note)
    note = Q.answer(SPEC, note, {"q2": {"text": "Finance, monthly"}})
    Q.check_placeable(SPEC, note)
    Q.check_placeable(SPEC, BASE)  # an older note has no quarters: not checked


POOLS = {"industry_a": {"pain_point": ["a1", "a2", "a3", "a4", "a5"], "lever": ["l1"], "intent": [], "future_signal": []},
         "industry_b": {"pain_point": ["b1"], "lever": [], "intent": ["i1", "i2", "i3", "i4"], "future_signal": []},
         "empty": {}}


@pytest.mark.parametrize("name,expect", [("industry_a", {"pain_point": 3, "lever": 1}), ("industry_b", {"pain_point": 1, "intent": 3}), ("empty", {})])
def test_at_most_three_suggestions_per_lane_for_two_industries_and_an_empty_company(name, expect):
    got = Q.suggest(SPEC, Q.from_pack(POOLS[name], f"the {name} pack"))
    counts = {}
    for s in got:
        counts[s["kind"]] = counts.get(s["kind"], 0) + 1
        assert s["suggested"] is True and s["from"] == f"the {name} pack"
    assert counts == expect


def test_documents_add_to_the_same_cap_and_a_suggestion_becomes_a_card_only_when_picked_up():
    docs = [{"kind": "lever", "text": "Close earlier", "from": "Board paper"}] * 2 + [{"kind": "lever", "text": "Pay faster", "from": "Board paper"}]
    got = Q.suggest(SPEC, Q.from_pack({"lever": ["l1", "l2"]}, "the pack") + docs, taken=[{"text": "L1"}])
    assert [s["text"] for s in got] == ["l2", "Close earlier", "Pay faster"]  # l1 already a card; repeat dropped; cap of three
    card = Q.pick_up(got[1], BASE)
    assert card["source"] == {"kind": "suggestion", "from": "Board paper"} and card["confirmed"] is False
    assert Q.answer(SPEC, card, {"q1": {"keep": True}})["quarters"]["q1"]["mark"] == "guessed"


def test_untouched_suggestions_are_dropped_when_the_room_closes_and_never_count():
    room = {"notes": [BASE], "suggestions": Q.suggest(SPEC, Q.from_pack(POOLS["industry_a"], "p"))}
    assert Q.drop_untouched(room) == {"notes": [BASE]}


def test_one_person_alone_through_the_door(tmp_path):
    w = new_world(tmp_path, StubNorth())
    org, sid, (ada, _) = flow(w)
    nid = ada.write("Late reports")
    assert ada.submit(nid).status_code == 200  # an older card without quarters is unchanged
    nid = ada.write("Slow month end")
    r = ada.save(nid, quarters={"q1": {"text": "Slow month end"}})
    assert r.status_code == 200, r.text
    note = next(n for n in r.json()["notes"] if n["id"] == nid)
    assert note["quarters"]["q1"]["mark"] == "stated" and note["quarters"]["q2"]["mark"] == "unknown"
    refused = ada.submit(nid)
    assert refused.status_code == 422 and "at least 2" in refused.text
    ada.save(nid, quarters={"q3": {"text": "A spreadsheet"}})
    assert ada.submit(nid).status_code == 200


# ---- the wiring: interview and documents prefill, suggestions at open, dropped at close
def world_with_mei(tmp_path, findings=True, company="co-a"):
    w = make_world(tmp_path)
    interview(w, company)
    plane = w.plane(company).ensure()
    if findings:
        rows = [{"kind": "pain", "text": f"Pain number {i}", "who": "", "how_often": "", "from": f'Board paper: "x{i}"'} for i in range(5)]
        rows.append({"kind": "signal", "text": "Rate moves", "who": "", "how_often": "", "from": 'Board paper: "r"'})
        profile.record(plane, "inputs.g1.findings", rows, {"mark": "guessed", "by": "lens", "agent": "lens", "from": "Board paper"})
    org = w.login("org", company, ["sponsor"])
    sid = session_at(w, org, company, "private_rooms", seats=3)
    mei = seated(w, company, "Mei Tan")
    tie(w, "mei-tan", mei.account_id, company)
    return w, org, sid, mei


def test_interview_drafts_start_with_the_interview_as_q1_and_keep_makes_it_stated(tmp_path):
    w, org, sid, mei = world_with_mei(tmp_path, findings=False)
    note = next(n for n in room(mei, sid)["notes"] if n["text"] == MEI["q2"])
    assert note["quarters"]["q1"]["mark"] == "unknown" and note["quarter_drafts"]["q1"]["from"] == "Interview with Mei Tan"
    r = mei.post(f"{API}/sessions/{sid}/room/notes/{note['id']}", json={"quarters": {"q1": {"keep": True}}}).json()
    got = next(n for n in r["notes"] if n["id"] == note["id"])
    assert got["quarters"]["q1"] == {"text": MEI["q2"], "mark": "stated", "from": "Interview with Mei Tan"}


def test_a_shelf_passage_that_fits_is_a_guessed_draft_naming_the_document(tmp_path):
    w, org, sid, mei = world_with_mei(tmp_path, findings=False)
    DocStore(w.plane("co-a").ensure()).upload("north", "pat", "c.md", b"Capital calls reach the cash team too late each week because notices go by email.",
                                              title="Capital call process", visibility="shared_full")
    note = next(n for n in room(mei, sid)["notes"] if n["text"] == MEI["q2"])
    r = mei.post(f"{API}/sessions/{sid}/room/notes/{note['id']}", json={"quarters": {}}).json()  # opening the card
    d = next(n for n in r["notes"] if n["id"] == note["id"])["quarter_drafts"]
    assert d["q2"]["from"] == "Capital call process" and d["q2"]["source"] == "document"
    k = mei.post(f"{API}/sessions/{sid}/room/notes/{note['id']}", json={"quarters": {"q2": {"keep": True}}}).json()
    assert next(n for n in k["notes"] if n["id"] == note["id"])["quarters"]["q2"]["mark"] == "guessed"


def test_suggestions_are_capped_picked_up_and_dropped_when_the_rooms_close(tmp_path):
    w, org, sid, mei = world_with_mei(tmp_path)
    v = room(mei, sid)
    sug = v["suggestions"]
    assert sorted(s["kind"] for s in sug) == ["future_signal", "pain_point", "pain_point", "pain_point"]  # five pains, three kept
    assert all(s["suggested"] and s["from"] == "Board paper" for s in sug)
    assert len(v["notes"]) == len(MEI)  # suggestions are not notes
    got = mei.post(f"{API}/sessions/{sid}/room/notes", json={"from_suggestion": sug[0]["id"]}).json()
    assert len(got["notes"]) == len(MEI) + 1 and len(got["suggestions"]) == 3
    assert mei.post(f"{API}/sessions/{sid}/room/notes", json={"from_suggestion": sug[0]["id"]}).status_code == 422  # already taken
    assert org.post(f"{API}/sessions/{sid}/rooms/close").status_code == 200
    assert SuggestionStore(w.plane("co-a"))._all(sid) == {}
    assert NoteStore_board(w, sid) == []  # nothing untouched or unconfirmed reached the wall


def NoteStore_board(w, sid):
    from modules.m1_intent.store.notes import NoteStore
    return NoteStore(w.plane("co-a")).board(sid)


def test_no_findings_and_no_pack_examples_means_no_suggestions(tmp_path):
    w, org, sid, mei = world_with_mei(tmp_path, findings=False)
    assert room(mei, sid)["suggestions"] == []


# ---- fix round 1: the shelf draft reads only what the person may read; an anonymous card keeps no name
CALLS = b"Capital calls reach the cash team too late each week because notices go by email."


def _open(mei, sid, note_id):
    r = mei.post(f"{API}/sessions/{sid}/room/notes/{note_id}", json={"quarters": {}}).json()
    return next(n for n in r["notes"] if n["id"] == note_id)


def test_someone_elses_private_document_and_memories_never_become_a_draft(tmp_path):
    w, org, sid, mei = world_with_mei(tmp_path, findings=False)
    store = DocStore(w.plane("co-a").ensure())
    store.upload("north", "another-account", "c.md", CALLS, title="Private calls file")  # private by default
    note = next(n for n in room(mei, sid)["notes"] if n["text"] == MEI["q2"])
    assert "q2" not in _open(mei, sid, note["id"])["quarter_drafts"]
    store.upload("north", "another-account", "s.md", CALLS, title="Shared calls file", visibility="shared_full")
    mei.post(f"{API}/sessions/{sid}/room/notes/{note['id']}", json={"quarters": {}})
    again = next(n for n in room(mei, sid)["notes"] if n["id"] == note["id"])
    assert again["quarter_drafts"].get("q2") is None  # drafts are made once, when the card starts


def test_a_shared_document_is_drafted(tmp_path):
    w, org, sid, mei = world_with_mei(tmp_path, findings=False)
    store = DocStore(w.plane("co-a").ensure())
    store.upload("north", "another-account", "s.md", CALLS, title="Shared calls file", visibility="shared_full")
    note = next(n for n in room(mei, sid)["notes"] if n["text"] == MEI["q2"])
    assert _open(mei, sid, note["id"])["quarter_drafts"]["q2"]["from"] == "Shared calls file"


def test_a_link_guest_gets_no_shelf_drafts(tmp_path):
    w = new_world(tmp_path, StubNorth())
    org, sid, (ada, _) = flow(w)
    DocStore(w.plane("co-a").ensure()).upload("north", "x", "s.md", CALLS, title="Shared calls file", visibility="shared_full")
    nid = ada.write("Capital calls reach the cash team too late")
    r = ada.save(nid, quarters={})
    assert r.status_code == 200 and next(n for n in r.json()["notes"] if n["id"] == nid)["quarter_drafts"] == {}


def test_an_anonymous_card_that_keeps_a_system_draft_stores_no_name(tmp_path):
    w, org, sid, mei = world_with_mei(tmp_path, findings=False)
    plane = w.plane("co-a").ensure()
    meta = {"mark": "stated", "by": "x", "from": "test", "ref": {"kind": "document", "id": "d"}}
    profile.record(plane, "systems.ledger.name", "Ledger", meta)
    profile.record(plane, "systems.ledger.owner", "Mei Tan", meta)
    for order in ("anonymous_first", "keep_first"):
        text = MEI["q2"] if order == "anonymous_first" else MEI["q1"]
        note = next(n for n in room(mei, sid)["notes"] if n["text"] == text)
        assert "Mei Tan" in _open(mei, sid, note["id"])["quarter_drafts"]["q3"]["text"] or order == "keep_first"
        url = f"{API}/sessions/{sid}/room/notes/{note['id']}"
        steps = [{"anonymous": True}, {"quarters": {"q3": {"keep": True}}}]
        for body in (steps if order == "anonymous_first" else steps[::-1]):
            assert mei.post(url, json=body).status_code == 200
        got = next(n for n in room(mei, sid)["notes"] if n["id"] == note["id"])
        assert got["quarters"]["q3"]["text"] and "Mei" not in str(got["quarters"]) and "Tan" not in str(got["quarters"])
        assert "[a name]" in got["quarters"]["q3"]["text"]


def test_a_shared_document_gives_no_passage_to_a_draft_only_shared_full_does(tmp_path):
    w, org, sid, mei = world_with_mei(tmp_path, findings=False)
    DocStore(w.plane("co-a").ensure()).upload("north", "another-account", "s.md", CALLS, title="Summary only file", visibility="shared")
    note = next(n for n in room(mei, sid)["notes"] if n["text"] == MEI["q2"])
    assert "q2" not in _open(mei, sid, note["id"])["quarter_drafts"]  # no summary exists, so nothing
