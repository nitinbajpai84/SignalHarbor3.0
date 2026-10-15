"""M1-08, M1-10, M1-13, M1-16: the private room's rules, with no web and no storage. Synthetic text only."""
import pytest

from modules.m1_intent.domain import private_room as R

PROBLEMS = [
    {"id": "P-1", "question": "Where are renewals slipping behind the plan each month?",
     "decision": "Where to point follow-up effort", "breakdowns": ["region", "month"],
     "typical_actions": {"label": "pack label", "items": ["Split the slip by region first", "Compare with last month"]}},
    {"id": "P-2", "question": "Which suppliers deliver late most often?", "typical_actions": {"items": []}},
    {"id": "P-3", "question": "Why do complaints rise after launches?", "typical_actions": {"items": ["Review the launch checklist"]}},
]


def test_notes_are_accepted_only_in_the_private_rooms_stage():
    R.check_stage("private_rooms")  # no error
    for state in ("draft", "lobby", "briefing", "board", "together", "signing", "closed", "paused"):
        with pytest.raises(R.RoomClosed) as e:
            R.check_stage(state)
        assert e.value.message and "private_rooms" not in e.value.message  # plain words, no state names


def test_message_text_is_checked():
    assert R.check_text("  our renewals slipped  ") == "our renewals slipped"
    for bad in ("", "   ", 5, None, "x" * (R.MAX_MESSAGE_CHARS + 1), "bad\x00char"):
        with pytest.raises(R.RoomError):
            R.check_text(bad)


def test_one_question_at_a_time_and_short():
    # ported guard (the earlier North's `_limit_to_one_question`): the first question stays, later ones become statements
    assert R.tidy_reply("Thanks. Who is affected? And how often? Also how big?") == "Thanks. Who is affected? And how often. Also how big."
    assert R.tidy_reply("No question here.") == "No question here."
    assert R.tidy_reply('Do you mean "is it big?" Who is affected?') == 'Do you mean "is it big?" Who is affected?'  # a quoted question is not counted
    assert len(R.tidy_reply("word " * 400)) <= R.MAX_REPLY_CHARS
    assert R.tidy_reply("   ") == ""


def test_every_suggestion_is_labelled_and_says_the_company_decides():
    assert R.tidy_reply("Industry practice: others track it weekly.") == \
        "Industry practice (suggestion): Industry practice: others track it weekly.\nYour company decides."
    got = R.tidy_reply("From your data: renewals are tracked monthly.\nWho owns it?")
    assert got.startswith("Industry practice (suggestion): renewals are tracked monthly.") and "From your data" not in got
    assert R.tidy_reply("Industry practice (suggestion): weekly. Your company decides.").count("Your company decides") == 1


def test_pack_wording_for_the_model_has_no_ids_but_keeps_its_figures():
    assert R.plain("Q7: Should free-look cancels count? The pilot reserve is 5 million.") ==         "Should free-look cancels count? The pilot reserve is 5 million."
    assert R.plain("First-year premium plus 10% of single premium.") == "First-year premium plus 10% of single premium."
    assert R.plain(None) == ""


def test_figures_in_the_text_shown_become_facts_and_number_words_map_to_digits():
    vals = {f["value"] for f in R.figures("plus 10% of single premium, at least six months", "about 1,200 or 3.5")}
    assert vals == {"10", "6", "1,200", "3.5"} and R.figures("no figure here", "") == []


def test_an_acronym_in_a_note_matches_a_kpi_named_with_it():
    kpis = [{"id": "K1", "name": "Annualised premium equivalent (APE)"}, {"id": "K2", "name": "Lapse rate"},
            {"id": "K3", "name": "Claims backlog"}, {"id": "K4", "name": "Funding headroom"}]
    assert [o["name"] for o in R.kpi_offers(kpis, {}, ["Is our APE falling?"])] == ["Annualised premium equivalent (APE)"]
    assert R.kpi_offers(kpis, {}, ["Is our ape falling?"]) == []  # lower case 3 letters is not an acronym


KPIS = [{"id": "K01", "name": "Funding headroom"}, {"id": "K02", "name": "Evidence coverage"},
        {"id": "K03", "name": "Pack preparation effort"}, {"id": "K04", "name": "Known obligations due"}]
DEFAULTS = {"K01": {"definition_variants": [{"variant": "This pack: SUM(x.y)"}, {"variant": "Industry practice: the lowest cash left after calls."}],
                    "cadence": "Weekly", "breakdowns": ["entity", "monthly_bucket"], "levers": ["lever:pace_commitments"],
                    "customer_decides": [{"question": "Q1: Which reserve applies?"}], "caveat": "Do not count a call twice."}}


def test_kpis_matching_what_the_person_said_come_from_the_kpi_tree_and_defaults():
    got = R.kpi_offers(KPIS, DEFAULTS, ["Can we fund the capital calls over six months?", "worried about headroom"])
    assert [o["name"] for o in got] == ["Funding headroom"]
    o = got[0]
    assert o["means"] == "the lowest cash left after calls." and o["usually_refreshed"] == "Weekly"  # not the data-shaped "This pack" variant
    assert o["usually_split_by"] == ["entity", "monthly bucket"] and o["usual_levers"] == ["pace commitments"]
    assert o["your_company_decides"] == ["Which reserve applies?"] and o["watch_out"] == "Do not count a call twice."
    assert R.kpi_offers(KPIS, DEFAULTS, ["the coffee is cold"]) == [] and R.kpi_offers([], {}, ["headroom"]) == []


def test_glossary_terms_the_person_used_are_offered():
    terms = [{"term": "Capital call", "definition": "A notice asking for part of a commitment.", "synonyms": ["drawdown"]},
             {"term": "Reserve", "definition": "A buffer."}]
    assert [t["term"] for t in R.term_offers(terms, ["We have a Drawdown next month"])] == ["Capital call"]
    assert R.term_offers(terms, ["nothing here"]) == []


def test_a_note_keeps_the_persons_own_words_and_corrections_keep_history():
    n = R.new_note("Renewals slipped, I think.", "2026-01-01T00:00:00+00:00", "n1")
    assert n["text"] == "Renewals slipped, I think." and n["state"] == "draft" and n["priority"] is None
    assert n["practice"] is None and n["history"] == []
    n2 = R.correct_note(n, "Renewals slipped in March.", "2026-01-01T00:01:00+00:00")
    assert n2["text"] == "Renewals slipped in March." and n2["history"][0]["text"] == "Renewals slipped, I think."
    assert n["text"] == "Renewals slipped, I think."  # the original is never changed in place


def test_priority_scale_is_the_one_in_the_spec():
    assert R.clean_priority(None) is None
    assert R.clean_priority("must") == "must" and R.clean_priority("not_this_time") == "not_this_time"
    with pytest.raises(R.RoomError):
        R.clean_priority("urgent")


def test_practice_card_only_when_the_pack_matches_and_only_pack_words():
    card = R.match_practice(PROBLEMS, "Our renewals keep slipping behind plan in some regions")
    assert card["problem_id"] == "P-1" and card["decision"] == "offered"
    assert card["items"] == ["Split the slip by region first", "Compare with last month"]
    assert card["label"] == R.PRACTICE_LABEL == "Industry practice (suggestion)"
    assert card["company_decides"] == "Your company decides."
    assert R.match_practice(PROBLEMS, "The canteen coffee is cold") is None  # no match: nothing, no error
    assert R.match_practice([], "Our renewals keep slipping behind plan") is None  # no pack
    assert R.match_practice(PROBLEMS, "Which suppliers deliver late most often") is None  # a match with no items


def test_practice_decision_is_recorded_and_final():
    note = R.new_note("x", "t", "n1")
    note = R.set_practice(note, {"problem_id": "P-1", "label": R.PRACTICE_LABEL, "company_decides": "c",
                                 "items": ["a"], "decision": "offered"})
    added = R.decide_practice(note, "add", "t2")
    assert added["practice"]["decision"] == "added" and added["practice"]["decided_at"] == "t2"
    assert added["practice_added"] == ["a"]
    assert R.decide_practice(note, "dismiss", "t2")["practice"]["decision"] == "dismissed"
    with pytest.raises(R.RoomError):
        R.decide_practice(added, "dismiss", "t3")  # already decided
    with pytest.raises(R.RoomError):
        R.decide_practice(R.new_note("x", "t", "n2"), "add", "t")  # no card on this note
    with pytest.raises(R.RoomError):
        R.decide_practice(note, "maybe", "t")


def test_a_decided_card_is_never_replaced_by_a_new_match():
    note = R.new_note("x", "t", "n1")
    card = {"problem_id": "P-1", "label": "l", "company_decides": "c", "items": ["a"], "decision": "offered"}
    note = R.decide_practice(R.set_practice(note, card), "dismiss", "t2")
    assert R.set_practice(note, {**card, "problem_id": "P-3"})["practice"]["problem_id"] == "P-1"


def test_library_list_uses_the_packs_questions_only():
    assert R.library_list(PROBLEMS) == [{"id": "P-1", "text": PROBLEMS[0]["question"]},
                                        {"id": "P-2", "text": PROBLEMS[1]["question"]},
                                        {"id": "P-3", "text": PROBLEMS[2]["question"]}]
    assert R.library_list([{"id": "", "question": "x"}, {"id": "A", "question": ""}, "junk"]) == []


def _pack(n, shared, own=lambda i: f"zz{i}x"):
    """n problems that all carry the `shared` words and one word of their own."""
    return [{"id": f"Q-{i}", "question": f"{' '.join(shared)} {own(i)}", "typical_actions": {"items": ["an item"]}}
            for i in range(n)]


def test_a_note_sharing_only_common_words_gets_no_card():
    # "frobnicate" and "gizmos" are in every problem of the pack: they say nothing about which one the note is about
    problems = _pack(6, ["frobnicate", "gizmos"])
    assert R.match_practice(problems, "We frobnicate our gizmos every week") is None
    assert R.match_practice(problems, "Our team across the company wants numbers each month") is None  # stop words


def test_rare_shared_words_still_match():
    problems = _pack(6, ["frobnicate"], own=lambda i: f"rareword{chr(97 + i)} otherword{chr(97 + i)}")
    card = R.match_practice(problems, "rarewordc and otherwordc are our worry, with frobnicate too")
    assert card and card["problem_id"] == "Q-2"
    assert R.match_practice(problems, "rarewordc alone is one word only") is None  # still two meaningful words needed
