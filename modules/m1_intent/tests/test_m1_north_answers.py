"""CRITIC-M1 defects 5 and 6: North answers the LATEST message, does not ask for what the person said does not exist,
gives the usual practice in words from the pack, and says "Your company decides." once. Stub model, synthetic text."""
import json
from pathlib import Path

from modules.m1_intent.agent import north
from modules.m1_intent.domain import private_room as R
from modules.m1_intent.tools.pack_tools import load_guidance
from sh_platform.agents.protocols import ModelReply
from sh_platform.packs import PackLoader
from test_m1_north import StubModel, ask, guid

PACKS = Path(__file__).resolve().parents[3] / "packs"


def seen(m):
    return json.loads(m.calls[0]["messages"][1]["content"])


def test_the_latest_message_is_the_question_and_earlier_turns_are_background(world):
    m = StubModel(ModelReply("One name is usually capped."))
    ask(world, m, "Is there a limit on a single name?", history=[("person", "Marlowe alpha looks weak"), ("north", "Alpha is excess return.")])
    body = seen(m)
    assert body["question"].startswith(north.LATEST) and body["question"].endswith("Is there a limit on a single name?")
    assert "Marlowe" not in body["question"] and body["context"]["background_earlier_person_messages"] == ["Marlowe alpha looks weak"]
    assert "latest" not in body["context"] and "earlier_replies" not in body["context"]


def test_the_rules_say_answer_first_never_ask_for_what_does_not_exist_and_decides_once():
    p = north.system_prompt(practice=True, library=False).lower()
    for must in ("latest message", "answer the question that was asked first", "has just said does not exist",
                 "who typically decides", "the room adds them once, after a labelled industry-practice suggestion", "do not paste a measure"):
        assert must in p, must
    assert "does not exist" in north.system_prompt(practice=False, library=False)  # also in listen mode


def test_a_person_asking_how_others_do_it_gets_the_pack_without_the_switch(world):
    m = StubModel(ModelReply("Usually the committee."))
    ask(world, m, "What do family offices usually use as a concentration limit?")
    assert "industry_guidance" in seen(m)["context"] and "Industry practice:" in m.calls[0]["messages"][0]["content"]
    m = StubModel(ModelReply("Noted."))
    ask(world, m, "Our renewals slipped last month")
    assert "industry_guidance" not in seen(m)["context"]


def test_company_decides_is_said_once_and_last():
    out = R.tidy_reply("Industry practice (suggestion): the committee approves it. Your company decides.\n"
                       "Industry practice (suggestion): reviewed yearly. Your company decides. Who signs it off here?")
    assert out.lower().count("company decides") == 1 and out.rstrip().endswith("Your company decides.")
    assert R.tidy_reply("Your company decides what limit it uses.") == "Your company decides what limit it uses."  # a real sentence stays
    assert "company decides" not in R.tidy_reply("Noted, you have no limit.").lower()


def test_the_family_office_pack_has_usual_practice_in_words_for_the_questions_customers_ask():
    g = load_guidance(PackLoader(PACKS), "family_office")
    for question, needles in (("Who approves a benchmark for a manager?", ("investment committee usually approves the benchmark",)),
                              ("What do family offices usually use as a single-name concentration limit?", ("single-name limit", "share of total assets")),
                              ("How is tracking error usually watched?", ("tracking error is usually watched quarterly",))):
        text = north.ground_text(g, [question])
        assert all(n.lower() in text.lower() for n in needles), (question, text)
    rows = [d for d in g.defaults.values() if d.get("usual_practice")]
    assert rows and all(r.get("status") == "proposal" for p in (x for d in rows for x in d["usual_practice"]) for r in [p])
    assert not any(c.isdigit() for d in rows for p in d["usual_practice"] for c in p["text"])  # no invented figure


def test_pack_practice_reaches_the_offers_and_a_pack_without_it_still_works():
    k = [{"id": "M-1", "name": "Approval of benchmarks"}]
    d = {"M-1": {"kpi_id": "M-1", "usual_practice": [{"text": "A committee usually signs it off once a year.", "status": "proposal"}]}}
    assert R.kpi_offers(k, d, ["who approves a benchmark"])[0]["usual_practice"] == ["A committee usually signs it off once a year."]
    assert R.kpi_offers(k, {}, ["approval of benchmarks"])[0]["usual_practice"] == []
    assert guid().has_content
