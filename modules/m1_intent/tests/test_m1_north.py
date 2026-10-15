"""M1-08, M1-10, M1-13: North on the kernel runtime, with a stub model. No live call. Synthetic text only."""
import json

import pytest
import yaml

from modules.m1_intent.agent import north
from modules.m1_intent.domain import private_room as R
from modules.m1_intent.tools.pack_tools import MODULE_ID, Guidance, load_guidance, load_problems
from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.packs import EmptyPack, PackLoader

PROBLEMS = [{"id": "P-1", "question": "Where are renewals slipping behind the plan each month?",
             "decision": "Where to point follow-up effort", "breakdowns": ["region", "month"],
             "typical_actions": {"items": ["Split the slip by region first"]}}]


class StubModel:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def complete(self, module_id, messages, tools=None):
        self.calls.append({"messages": list(messages), "tools": tools})
        r = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return r(messages) if callable(r) else r


def turns(*pairs):
    return [{"id": f"t{i}", "role": r, "text": t, "at": "n"} for i, (r, t) in enumerate(pairs)]


def guid(problems=PROBLEMS, **kw) -> Guidance:
    return Guidance(EmptyPack("x"), problems=problems, **kw)


def ask(world, model, text, company="co-a", practice=False, library=False, problems=PROBLEMS, history=(), guidance=None):
    t = turns(*history, ("person", text))
    return north.next_question(model, world.store, company, guidance or guid(problems), t, practice=practice, library=library)


# ---- instructions

def test_rules_are_industry_neutral_and_say_the_five_things():
    prompt = north.system_prompt(practice=True, library=True)
    for must in ("own words", "reads it back", "at most one question", "lead with a short recommended draft",
                 "Never propose which problems", "Never invent a problem, a figure", "Industry practice (suggestion)",
                 "the company decides", "own belief to be checked later", "Never state a target"):
        assert must.lower() in prompt.lower(), must
    assert "industry_practice" not in north.system_prompt(practice=False, library=False)
    assert "problem_library" not in north.system_prompt(practice=True, library=False)
    for bad in ("insur", "asset man", "policy" + "holder", "Priya", "APE"):  # words of the old script, built so this file stays clean
        assert bad.lower() not in prompt.lower()


def test_every_instruction_line_is_plain_text():
    """A line with a colon inside it once parsed as a mapping and was shown to the model as a Python dict."""
    r = north.load_rules()
    for key in ("rules", "advisor_rules", "practice_rules", "library_rules", "no_guidance_rules"):
        assert r[key] and all(isinstance(x, str) for x in r[key]), key
    assert isinstance(r["role"], str) and isinstance(r["example_rule"], str)
    assert "{" not in north.system_prompt(practice=True, library=True, north={"advisor_role": "x", "peers": "y",
                                                                               "typical_breakdowns": "z", "example_data_line": "w"})


# ---- behaviour with a stub model

def test_reply_is_one_short_question(world):
    m = StubModel(ModelReply("Thanks for that. Who is affected? And how often does it happen?"))
    text, answered = ask(world, m, "Renewals slipped")
    assert answered and text.count("?") == 1 and text.startswith("Thanks for that. Who is affected?")  # later questions become statements


def test_the_model_is_shown_the_persons_words_and_the_rules_and_only_the_matching_pack_content(world):
    m = StubModel(ModelReply("Who is affected?"))
    ask(world, m, "Renewals keep slipping behind plan in some regions", practice=True, problems=PROBLEMS)
    sent = json.dumps(m.calls[0]["messages"])
    assert "Renewals keep slipping" in sent and "own words" in m.calls[0]["messages"][0]["content"]
    assert "Split the slip by region first" in sent and "Industry practice (suggestion)" in sent  # grounded, labelled
    m = StubModel(ModelReply("Who is affected?"))
    ask(world, m, "Renewals keep slipping behind plan in some regions", practice=False, problems=PROBLEMS)
    assert "Split the slip" not in json.dumps(m.calls[0]["messages"])  # the organiser's switch is off: nothing from the pack


def test_no_pack_says_there_is_no_industry_guidance_yet_and_offers_nothing(world):
    m = StubModel(ModelReply("Who is affected?"))
    ask(world, m, "Renewals slipped", practice=True, guidance=guid([]))
    ctx = json.loads(m.calls[0]["messages"][1]["content"])["context"]
    assert ctx["industry_guidance"]["none_for_this_industry"] and "No industry guidance" in ctx["industry_guidance"]["note"]
    assert "no industry guidance" in m.calls[0]["messages"][0]["content"].lower()


def test_wording_of_the_industry_comes_from_the_pack_north_file(world):
    north_cfg = {"advisor_role": "a cheese advisor", "peers": "cheesemakers", "typical_breakdowns": "wheel or month",
                 "example_data_line": "Ripening time is usually checked weekly", "rules": ["Never rank a rind."]}
    p = north.system_prompt(practice=True, library=False, north=north_cfg)
    for must in ("a cheese advisor", "cheesemakers", "wheel or month", "Ripening time is usually checked weekly", "Never rank a rind."):
        assert must in p
    assert "cheese" not in north.system_prompt(practice=True, library=False)  # no pack file: neutral defaults


def test_earlier_conversation_is_carried_so_it_continues_after_a_reconnect(world):
    m = StubModel(ModelReply("How often does it happen?"))
    ask(world, m, "About twice a month", history=[("person", "Renewals slipped"), ("north", "Who is affected?")])
    ctx = json.loads(m.calls[0]["messages"][1]["content"])["context"]
    assert ctx["background_earlier_north_replies"] == ["Who is affected?"]
    assert ctx["background_earlier_person_messages"] == ["Renewals slipped"]
    q = json.loads(m.calls[0]["messages"][1]["content"])["question"]
    assert q.startswith(north.LATEST) and q.endswith("About twice a month") and "Renewals slipped" not in q


def test_an_invented_figure_is_replaced_but_the_persons_own_figure_stays(world):
    m = StubModel(ModelReply("You said 40 customers. Is it really 99 percent of them?"))
    text, _ = ask(world, m, "We lost 40 customers last month")
    assert "40" in text and "99" not in text and "not available yet" in text


KPIS = [{"id": "K1", "name": "Annualised premium equivalent", "definition": "Premium measure."},
        {"id": "K2", "name": "Funding headroom"}, {"id": "K3", "name": "Lapse rate"}, {"id": "K4", "name": "Claims backlog"}]
DEFAULTS = {"K1": {"kpi_id": "K1", "definition_variants": [{"variant": "Industry practice: first-year regular premium plus 10% of single premium."}]},
            "K2": {"kpi_id": "K2", "definition_variants": [{"variant": "Industry practice: the cash left after calls, usually kept above six months of calls."}]}}


def test_a_figure_in_the_pack_text_survives_but_an_invented_one_is_replaced(world):
    g = guid([], kpis=KPIS, defaults=DEFAULTS)
    m = StubModel(ModelReply("Industry practice (suggestion): first-year regular premium plus 10% of single premium. Is it 37% for you?"))
    text, _ = ask(world, m, "How do we define annualised premium equivalent?", practice=True, guidance=g)
    assert "10%" in text and "37" not in text and "not available yet" in text
    assert "10%" in json.dumps(m.calls[0]["messages"])  # and the model was shown it, whole


def test_pack_number_words_and_digits_match_and_the_persons_number_stays_belief(world):
    g = guid([], kpis=KPIS, defaults=DEFAULTS)
    m = StubModel(ModelReply("Industry practice (suggestion): keep a minimum 6-month funding headroom. You said 40 calls, is that right?"))
    text, _ = ask(world, m, "Funding headroom worries me, we have 40 calls", practice=True, guidance=g)
    assert "6-month funding headroom" in text and "40 calls" in text and "not available" not in text


def test_a_figure_from_the_practice_tool_may_be_repeated(world):
    g = guid([], kpis=KPIS, defaults=DEFAULTS)
    m = StubModel(ModelReply("", [ToolCall("industry_practice", {"topic": "annualised premium equivalent"}, "c1")]),
                  ModelReply("Plus 10% of single premium, not 37%. Does that fit?"))
    text, _ = ask(world, m, "annualised premium equivalent", practice=True, guidance=g)
    assert "10%" in text and "37" not in text


def test_a_failing_model_gives_a_plain_message_not_a_trace(world):
    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("secret internal trace")
    text, answered = ask(world, Boom(), "Renewals slipped")
    assert not answered and "secret" not in text and "Traceback" not in text and text


# ---- tools

def reg(world, company="co-a", problems=PROBLEMS, practice=True, library=True):
    return north.build_registry(world.store, guid(problems), practice=practice, library=library)


def test_tools_are_listed_only_when_module_1_is_owned(world):
    r = reg(world)
    assert {t["name"] for t in r.tools_for("co-a", MODULE_ID)} == {"industry_practice", "problem_library"}
    assert r.tools_for("co-off", MODULE_ID) == []  # the company does not own module 1
    world.store.set_module("co-a", "m1_intent", False)
    assert r.tools_for("co-a", MODULE_ID) == []  # switched off: no tools, and a call is refused too
    with pytest.raises(Exception):
        r.call("co-a", MODULE_ID, "industry_practice", {"topic": "renewals slipping behind plan"})


def test_only_the_switched_on_tools_exist(world):
    assert [t["name"] for t in reg(world, practice=False, library=False).tools_for("co-a", MODULE_ID)] == []
    assert [t["name"] for t in reg(world, practice=True, library=False).tools_for("co-a", MODULE_ID)] == ["industry_practice"]
    assert [t["name"] for t in reg(world, practice=False, library=True).tools_for("co-a", MODULE_ID)] == ["problem_library"]


def test_industry_practice_tool_is_labelled_and_empty_when_nothing_matches(world):
    r = reg(world)
    got = r.call("co-a", MODULE_ID, "industry_practice", {"topic": "renewals keep slipping behind plan in regions"})
    assert got["label"] == "Industry practice (suggestion)" and "Your company decides." not in got["text"]  # tidy_reply adds it once, not the tool
    assert "Split the slip by region first" in got["text"] and isinstance(got["text"], str)
    nothing = {"nothing_matched": True}
    assert r.call("co-a", MODULE_ID, "industry_practice", {"topic": "the coffee is cold"}) == nothing
    assert [t["name"] for t in reg(world, problems=[]).tools_for("co-a", MODULE_ID)] == []  # no pack: no tools at all


def test_north_uses_the_tool_and_says_it_as_a_suggestion(world):
    m = StubModel(ModelReply("", [ToolCall("industry_practice", {"topic": "renewals slipping behind plan"}, "c1")]),
                  ModelReply("Others usually track the slip by region. Industry practice (suggestion): your company decides. Does that fit?"))
    text, answered = ask(world, m, "Renewals keep slipping behind plan", practice=True)
    assert answered and "Industry practice (suggestion)" in text
    tool_msg = [x for x in m.calls[1]["messages"] if x["role"] == "tool"][0]
    assert "Split the slip by region first" in tool_msg["content"]


def test_a_tool_that_is_off_cannot_be_called_by_the_model(world):
    m = StubModel(ModelReply("", [ToolCall("industry_practice", {"topic": "x"}, "c1")]), ModelReply("Who is affected?"))
    text, _ = ask(world, m, "Renewals slipped", practice=False)
    assert "could not use a tool" in text or text.startswith("Who")  # refused, then North carries on honestly
    tool_msg = [x for x in m.calls[1]["messages"] if x["role"] == "tool"][0]
    assert "not available" in tool_msg["content"]


def test_problem_library_tool_lists_pack_problems_only(world):
    got = reg(world).call("co-a", MODULE_ID, "problem_library", {})
    assert got["problems"] == [PROBLEMS[0]["question"]]


# ---- two industries and the empty company: content comes only from the company's own pack

@pytest.mark.parametrize("industry,other", [("industry_a", "industry_b"), ("industry_b", "industry_a")])
def test_each_industry_gets_only_its_own_pack(world, industry, other):
    pack, problems = load_problems(world.app.state.packs, industry)
    text = json.dumps(problems)
    assert industry in text and other not in text and len(problems) == (3 if industry == "industry_a" else 2)


def test_an_industry_with_no_pack_is_empty_not_borrowed(world):
    for name in ("none", "unlisted", "Not A Name!", ""):
        pack, problems = load_problems(world.app.state.packs, name)
        assert problems == [] and pack.empty
        assert R.match_practice(problems, "anything about renewals slipping behind plan") is None


def test_a_damaged_pack_file_is_an_empty_list_not_a_crash(tmp_path):
    folder = tmp_path / "x" / "1"
    folder.mkdir(parents=True)
    (folder / "pack.yaml").write_text(yaml.safe_dump({"industry": "x", "version": 1, "label": "x"}))
    (folder / "problems.yaml").write_text("problems: [unclosed")
    pack, problems = load_problems(PackLoader(tmp_path), "x")
    assert problems == []
