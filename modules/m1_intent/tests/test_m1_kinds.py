"""The four kinds of note (intent, pain point, future signal, lever) from the private room to the board.
Synthetic wording only, written for a family office as example text. Stub North; no live model."""
import json
from pathlib import Path

import pytest
import yaml

from m1_kit import BASE
from modules.m1_intent.agent import north
from modules.m1_intent.domain import notes as N
from modules.m1_intent.store.notes import NoteStore
from modules.m1_intent.store.sessions import SessionStore
from modules.m1_intent.tools.pack_tools import Guidance, load_guidance
from sh_platform.packs import EmptyPack, PackLoader
from test_m1_board_kit import GatherStub
from test_m1_seat_wiring_kit import StubNorth, flow, new_world

REAL_PACKS = PackLoader(Path(__file__).resolve().parents[3] / "packs")
KINDS = ("intent", "pain_point", "future_signal", "lever")
# one note per kind: (text, the fields the kind may carry)
SAMPLES = {
    "intent": ("We will review the funding reserve every quarter", {}),
    "pain_point": ("Preparing the investment meeting pack takes two days", {"who": "The finance team", "how_often": "Every month", "kpi": "Pack preparation time"}),
    "future_signal": ("Interest rate moves could change our funding costs", {"source": "Central bank rate decisions"}),
    "lever": ("We can change how fast we commit to new investments", {"moves": "Funding headroom, Cash buffer"}),
}


def put(person, kind, text=None, fields=None, anonymous=None):
    """A note of `kind` written, filled and submitted by `person`; returns its id."""
    sample_text, sample_fields = SAMPLES[kind]
    nid = person.write(text or sample_text)
    body = {"kind": kind, "fields": sample_fields if fields is None else fields}
    if anonymous is not None:
        body["anonymous"] = anonymous
    r = person.save(nid, **body)
    assert r.status_code == 200, r.text
    assert person.submit(nid).status_code == 200
    return nid


def room(tmp_path, proposal=None, company="co-a"):
    return flow(new_world(tmp_path, StubNorth(proposal)), company)


# ---- an old note loads as an intent
def test_a_note_with_no_kind_is_an_intent():
    assert N.kind_of({"id": "x", "text": "old note"}) == "intent"
    assert N.kind_of({"kind": "lever"}) == "lever"


def test_an_old_stored_note_with_no_kind_reads_back_as_an_intent(tmp_path):
    w = new_world(tmp_path)
    org, sid, (ada, _) = flow(w)
    put(ada, "intent")
    path = w.plane("co-a").path("intents", "m1_intent", "notes", f"{sid}.json")
    data = json.loads(path.read_text())
    for rec in data["notes"]:
        rec.pop("kind", None)  # a note stored before kinds existed
    path.write_text(json.dumps(data))
    assert [n["kind"] for n in NoteStore(w.plane("co-a")).board(sid)] == ["intent"]
    # and a draft in a transcript with no kind shows as an intent in its author's room
    assert ada.room()["notes"][0]["kind"] == "intent"


def test_a_new_note_is_an_intent_until_the_person_says_otherwise(tmp_path):
    org, sid, (ada, _) = room(tmp_path)
    nid = ada.write()
    assert ada.room()["notes"][0]["kind"] == "intent"
    assert ada.save(nid, kind="lever").json()["notes"][0]["kind"] == "lever"


# ---- each kind is saved and shown
@pytest.mark.parametrize("kind", KINDS)
def test_each_kind_is_saved_shown_to_its_author_and_posted_with_its_kind(tmp_path, kind):
    org, sid, (ada, ben) = room(tmp_path)
    nid = ada.write(SAMPLES[kind][0])
    note = ada.save(nid, kind=kind, fields=SAMPLES[kind][1]).json()["notes"][0]
    assert note["kind"] == kind and note["fields"] == SAMPLES[kind][1]
    assert ada.submit(nid).status_code == 200
    # the room tells the screen which kinds exist and which extra details each carries
    kinds = {k["id"]: k for k in ada.room()["kinds"]}
    assert list(kinds) == list(KINDS)
    assert [f["id"] for f in kinds[kind]["fields"]] == list(SAMPLES[kind][1]) or kind == "intent"
    assert all(k["label"] and k["heading"] for k in kinds.values())


def test_the_board_record_carries_the_kind_and_its_details(tmp_path):
    w = new_world(tmp_path)
    org, sid, (ada, ben) = flow(w)
    for kind in KINDS:
        put(ada, kind)
    recs = {n["kind"]: n for n in NoteStore(w.plane("co-a")).board(sid)}
    assert set(recs) == set(KINDS)
    assert recs["pain_point"]["fields"] == SAMPLES["pain_point"][1]
    assert recs["lever"]["fields"] == {"moves": "Funding headroom, Cash buffer"}
    assert recs["future_signal"]["fields"] == {"source": "Central bank rate decisions"}
    assert "who" not in recs["lever"]["fields"]


def test_a_detail_only_another_kind_has_is_refused_and_so_is_an_unknown_kind(tmp_path):
    org, sid, (ada, _) = room(tmp_path)
    nid = ada.write()
    assert ada.save(nid, kind="lever", fields={"who": "Finance"}).status_code == 422
    assert ada.save(nid, kind="pain_point", fields={"moves": "Cash"}).status_code == 422
    assert ada.save(nid, kind="wish").status_code == 422
    assert ada.save(nid, kind=3).status_code == 422
    assert ada.save(nid, kind="pain_point", fields={"who": "Finance"}).status_code == 200


def test_the_missing_details_follow_the_kind(tmp_path):
    org, sid, (ada, _) = room(tmp_path)
    nid = ada.write()
    assert "who" not in ada.room()["notes"][0]["missing"]
    note = ada.save(nid, kind="pain_point").json()["notes"][0]
    assert {"who", "how_often", "kpi"} <= set(note["missing"]) and "moves" not in note["missing"]


def test_north_suggests_a_kind_and_the_person_decides(tmp_path):
    org, sid, (ada, _) = room(tmp_path, proposal={"kind": "lever", "moves": "Cash buffer", "who": "nobody"})
    nid = ada.write("We can pace new commitments")
    note = ada.call("POST", f"/room/notes/{nid}/prefill").json()["notes"][0]
    assert note["kind"] == "intent" and note["kind_suggested"] == "lever"  # a suggestion, not a change
    assert note["fields"].get("moves") == "Cash buffer" and "who" not in note["fields"]
    ada.save(nid, kind="pain_point")  # the person chose
    again = ada.call("POST", f"/room/notes/{nid}/prefill").json()["notes"][0]
    assert again["kind"] == "pain_point" and again.get("kind_suggested") in (None, "pain_point")


def test_a_wrong_kind_from_north_is_ignored(tmp_path):
    org, sid, (ada, _) = room(tmp_path, proposal={"kind": "wish"})
    nid = ada.write()
    note = ada.call("POST", f"/room/notes/{nid}/prefill").json()["notes"][0]
    assert note["kind"] == "intent" and not note.get("kind_suggested")


def test_a_note_can_be_saved_with_its_kind_from_the_start(tmp_path):
    org, sid, (ada, _) = room(tmp_path)
    r = ada.call("POST", "/room/messages", json={"text": "Month end is painful", "kind": "note", "note_kind": "pain_point"})
    assert r.json()["notes"][-1]["kind"] == "pain_point"
    assert ada.call("POST", "/room/messages", json={"text": "x", "kind": "note", "note_kind": "wish"}).status_code == 422


# ---- the board groups within a kind
def test_the_board_groups_within_a_kind_and_never_mixes_kinds(tmp_path):
    w = new_world(tmp_path, GatherStub({"capital call": "Capital calls"}))
    org, sid, (ada, ben) = flow(w)
    put(ada, "pain_point", "Capital calls reach us too late to plan")
    put(ben, "pain_point", "We learn of capital calls by email days late")
    put(ada, "lever", "We can pace capital call funding differently")
    put(ben, "lever", "We can hold more cash ahead of a capital call")
    put(ada, "intent", "Know our capital call exposure for the year")
    assert org.post(f"{BASE}/sessions/{sid}/rooms/close").status_code == 200
    stub = w.app.state.north_model_factory(None)
    r = org.post(f"{BASE}/sessions/{sid}/board/group")
    assert r.status_code == 200, r.text
    view = org.get(f"{BASE}/sessions/{sid}/board").json()
    assert len([c for c in stub.calls if "Notes to group" in c[1]["content"]]) == 2  # one call for each kind that has two notes or more
    assert sorted(c["kind"] for c in view["clusters"]) == ["lever", "pain_point"]  # two groups with the same name, one for each kind
    for c in view["clusters"]:
        assert {n["kind"] for n in c["notes"]} == {c["kind"]}
    assert [n["kind"] for n in view["on_its_own"]] == ["intent"]
    assert view["by_kind"] == {"intent": 1, "pain_point": 2, "future_signal": 0, "lever": 2}


def test_the_organiser_may_still_mix_kinds_by_hand(tmp_path):
    w = new_world(tmp_path, GatherStub({"capital call": "Capital calls"}))
    org, sid, (ada, ben) = flow(w)
    put(ada, "pain_point", "Capital calls reach us too late")
    put(ben, "pain_point", "Capital calls come by email")
    lever = put(ada, "lever", "We can pace capital call funding")
    org.post(f"{BASE}/sessions/{sid}/rooms/close")
    org.post(f"{BASE}/sessions/{sid}/board/group")
    cid = org.get(f"{BASE}/sessions/{sid}/board").json()["clusters"][0]["id"]
    r = org.post(f"{BASE}/sessions/{sid}/board/notes/{lever}/move", json={"cluster_id": cid})
    assert r.status_code == 200, r.text
    assert r.json()["clusters"][0]["kind"] == "mixed"


def test_the_keyword_fallback_also_stays_within_a_kind(tmp_path):
    w = new_world(tmp_path, GatherStub(fail=True))
    org, sid, (ada, ben) = flow(w)
    put(ada, "pain_point", "Reporting packs take two days every month")
    put(ben, "lever", "Reporting packs could be built weekly")
    put(ada, "pain_point", "Reporting packs are late for the council")
    put(ben, "lever", "Reporting packs need a single owner")
    org.post(f"{BASE}/sessions/{sid}/rooms/close")
    view = org.post(f"{BASE}/sessions/{sid}/board/group").json()
    assert view["clusters"] and all({n["kind"] for n in c["notes"]} == {c["kind"]} for c in view["clusters"])


# ---- anonymity holds for every kind
@pytest.mark.parametrize("kind", KINDS)
def test_an_anonymous_note_of_any_kind_shows_no_author_anywhere(tmp_path, kind):
    w = new_world(tmp_path)
    org, sid, (ada, ben) = flow(w)
    put(ada, kind, anonymous=True)
    assert "Ada Guest" not in json.dumps(NoteStore(w.plane("co-a")).board(sid, viewer=None))
    assert ben.room()["notes"] == []  # another person never sees the draft or its details
    org.post(f"{BASE}/sessions/{sid}/rooms/close")
    org.post(f"{BASE}/sessions/{sid}/board/group")
    for who in (org, None):
        view = (org.get(f"{BASE}/sessions/{sid}/board") if who else ben.call("GET", "/board")).json()
        note = view["on_its_own"][0]
        assert note["anonymous"] is True and "author_name" not in note and note["kind"] == kind
        assert "Ada Guest" not in json.dumps(view)
    assert ada.call("GET", "/board").json()["on_its_own"][0]["mine"] is True  # the author still sees it as theirs


@pytest.mark.parametrize("kind", KINDS)
def test_a_note_of_any_kind_by_name_shows_the_author_name_when_names_are_open(tmp_path, kind):
    """In a session whose organiser chose open names, a note shows its author exactly when it is not anonymous."""
    w = new_world(tmp_path)
    org, sid, (ada, ben) = flow(w)
    store = SessionStore(w.plane("co-a"))
    s = store.get(sid)
    s["preparation"]["names"] = "named"
    store._save(s, store._read_index())
    assert ada.room()["names"] == "named"
    put(ada, kind)
    org.post(f"{BASE}/sessions/{sid}/rooms/close")
    note = ben.call("GET", "/board").json()["on_its_own"][0]
    assert note["author_name"] == "Ada Guest" and note["kind"] == kind and note["anonymous"] is False


# ---- North's rules, the pack, and a company with no pack
THEMES = ("pain_points", "future_signals", "levers")


def test_norths_rules_hold_the_three_themes_in_plain_words():
    rules = north.load_rules()
    themes = rules["themes"]
    assert set(themes) == set(THEMES)
    text = " ".join(str(v) for v in themes.values()).lower()
    for phrase in ("what hurts", "who is affected", "how often", "keep an eye on", "outside or market signals", "levers do you change", "kpis do you watch"):
        assert phrase in text, phrase
    for kind_words in ("hurts today", "to watch in future", "lever you change"):
        assert kind_words in " ".join(rules["kind_rules"]).lower()
    assert any("not all at once" in r.lower() or "in turn" in r.lower() for r in rules["themes_rules"])


def test_the_themes_reach_the_prompt_for_every_industry_and_for_a_company_with_no_pack():
    for guidance in (None, {"advisor_role": "a family office advisor", "peers": "family offices"}):
        for practice in (False, True):
            p = north.system_prompt(practice=practice, library=False, north=guidance, has_pack=guidance is not None).lower()
            assert "what hurts" in p and "keep an eye on" in p and "levers do you change" in p
            assert "is this something that hurts today, something to watch in future, or a lever you change" in p
    plain_default = north.system_prompt(practice=False, library=False, north=None, has_pack=False)
    assert "listen and check" in plain_default.lower()  # listening stays the default


def test_every_real_pack_that_carries_theme_suggestions_carries_all_three_themes_and_one_has_them():
    carrying = [i for i in REAL_PACKS.industries() if "pain_point_examples" in REAL_PACKS.load(i).section("intent_examples")]
    assert "family_office" in carrying and len(carrying) >= 2  # two industries, so a second one proves the words live in the pack
    for industry in carrying:
        _check_pack_themes(REAL_PACKS.load(industry))


def _check_pack_themes(pack):
    examples = pack.section("intent_examples")
    for key in ("pain_point_examples", "future_signal_examples", "lever_examples"):
        assert examples[key] and all(isinstance(x, str) and x for x in examples[key]), key
    north_file = pack.section("north")
    for key in ("example_pain_line", "example_signal_line", "example_lever_line"):
        assert north_file[key].strip(), key


def test_the_form_offers_the_packs_suggestions_labelled_and_a_company_with_no_pack_gets_an_honest_empty_state(tmp_path):
    w = new_world(tmp_path)
    org, sid, (ada, _) = flow(w, "co-a")
    assert set(ada.room()["north"]["suggestions"]) == {"pain_point", "future_signal", "lever"}
    w2 = new_world(tmp_path / "none")
    org2, sid2, (cy, _) = flow(w2, "co-none")
    r = cy.room()
    assert r["north"]["suggestions"] == {"pain_point": [], "future_signal": [], "lever": []}
    assert r["north"]["suggestions_label"] is None and r["north"]["suggestions_empty"]  # says there is nothing yet, offers nothing
    nid = cy.write("Month end is slow")
    assert cy.save(nid, kind="pain_point", fields={"who": "Finance"}).status_code == 200  # the module still works
    assert cy.submit(nid).status_code == 200


def test_a_pack_with_suggestions_shows_them_with_the_suggestion_label(tmp_path):
    w = new_world(tmp_path)
    folder = w.packs / "industry_a" / "1"
    (folder / "intent_examples.yaml").write_text(yaml.safe_dump({
        "pain_point_examples": ["Reports arrive late"], "future_signal_examples": ["Rate decisions"], "lever_examples": ["Commitment pacing"]}))
    org, sid, (ada, _) = flow(w, "co-a")
    n = ada.room()["north"]
    assert n["suggestions"]["pain_point"] == ["Reports arrive late"] and n["suggestions"]["lever"] == ["Commitment pacing"]
    assert "suggestion" in n["suggestions_label"].lower()


def test_guidance_has_no_theme_wording_of_its_own_in_code():
    g = Guidance(EmptyPack("none"))
    assert not g.has_content and load_guidance(REAL_PACKS, "retail").north == {}


def test_the_briefing_tells_people_what_to_write_about_in_plain_words_and_nira_knows_the_kinds():
    from modules.m1_intent.agent import nira
    from modules.m1_intent.domain import briefing as B
    from modules.m1_intent.evals.nira_evals import PREP
    rules = {r["id"]: r for r in B.build_rules(PREP, B.load_settings())}
    text = rules["kinds"]["text"].lower()
    assert rules["kinds"]["label"] == "What to write about"
    for phrase in ("what hurts today", "who is affected", "how often", "keep an eye on", "outside or market signals", "levers do you change", "kpis do you watch"):
        assert phrase in text, phrase
    assert list(rules) == ["purpose", "outcome", "time", "kinds", "notes"]
    facts = " ".join(nira.load_rules()["session_facts"])
    assert "four kinds" in facts and "four lists" in facts and "North groups the notes of one kind at a time" in facts
