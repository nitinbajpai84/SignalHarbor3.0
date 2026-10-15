"""The North evals run on a stub: label, no invented numbers, the no-pack case. No live call."""
import pytest

from modules.m1_intent.evals.north import __main__ as runner
from modules.m1_intent.evals.north.cases import CASES, NO_PACK, PACK, ScriptedModel, run_all, run_case
from sh_platform.agents.protocols import ModelReply


def test_all_stub_cases_pass():
    res = run_all()
    assert len(res) == len(CASES) == 17 and all(ok for _, ok, _ in res), res


def test_the_evals_catch_a_missing_label_an_invented_number_and_a_borrowed_card():
    base = {c.id: c for c in CASES}
    no_label = type(base["label_when_practice_is_used"])(**{**base["label_when_practice_is_used"].__dict__,
                                                          "script": [ModelReply("Others track the slip by region.")]})
    assert not run_case(no_label, ScriptedModel(no_label.script))[1]
    c = base["no_invented_number"]
    leaks = type(c)(**{**c.__dict__, "must_not_include": ["not available yet"]})  # the replacement must be there
    assert not run_case(leaks, ScriptedModel(leaks.script))[1]
    c = base["no_pack_says_no_guidance_and_offers_nothing"]
    borrowed = type(c)(**{**c.__dict__, "guidance": PACK, "card_expected": False})  # a pack where there should be none
    assert not run_case(borrowed, ScriptedModel(borrowed.script))[1]
    c = base["kpis_come_from_the_pack_labelled"]
    other = type(c)(**{**c.__dict__, "guidance": NO_PACK})  # without the pack's KPI tree there is nothing to offer
    assert not run_case(other, ScriptedModel(other.script))[1]
    c = base["adv_false_citation_is_relabelled"]
    assert run_case(c, ScriptedModel(c.script))[1]
    c = base["one_question_only"]
    assert run_case(c, ScriptedModel(c.script))[1]  # the room cuts the three questions to one


def test_live_run_needs_a_key_and_never_calls_out_here(monkeypatch, capsys):
    for k in ("GOOGLE_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert runner.main(["--live"]) == 2
    assert "GOOGLE_API_KEY" in capsys.readouterr().err  # names only
    assert runner.main([]) == 0
