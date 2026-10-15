"""M1-07 evals: welcome, a rules question, a time warning, "what do I do now", an opinion request refused.
Stub model by default; --live is refused without a real client (same rule as sh_platform.agents.evals)."""
import pytest

from modules.m1_intent.evals import nira_evals
from sh_platform.agents.evals.harness import LiveRefused, ScriptedModel
from sh_platform.agents.protocols import ModelReply

IDS = ["welcome", "rules_question", "time_warning", "what_do_i_do_now", "opinion_refused", "im_done", "finish_early", "unsent_notes",
       "summary_page", "private_chat"]


def test_the_cases_exist_and_pass_with_the_stub():
    assert [c.id for c in nira_evals.CASES] == IDS
    res = nira_evals.run_evals(nira_evals.CASES)
    assert (res.total, res.passed, res.failed) == (10, 10, 0), res.results


def test_a_case_fails_when_the_model_gives_an_opinion():
    case = next(c for c in nira_evals.CASES if c.id == "opinion_refused")

    class Opinionated:  # a stand-in for a real client
        def complete(self, module_id, messages, tools=None):
            return ModelReply("I think you should cut costs first.")

    res = nira_evals.run_evals([case], Opinionated(), live=True)
    assert res.failed == 1


def test_live_is_refused_without_a_real_client():
    with pytest.raises(LiveRefused):
        nira_evals.run_evals(nira_evals.CASES, live=True)
    with pytest.raises(LiveRefused):
        nira_evals.run_evals(nira_evals.CASES, ScriptedModel([ModelReply("x")]), live=True)
    assert nira_evals.main(["--live"]) == 2


def test_main_prints_the_counts(capsys):
    assert nira_evals.main([]) == 0
    assert "10 passed, 0 failed of 10" in capsys.readouterr().out


def _case(case_id, **change):
    from dataclasses import replace
    return replace(next(c for c in nira_evals.CASES if c.id == case_id), **change)


def test_the_stub_answers_only_from_what_it_was_shown():
    """Take away the one-minute figure, the stage or the refusal instruction and the case must fail."""
    no_figure = _case("time_warning", extra="")
    wrong_stage = _case("what_do_i_do_now", stage="board")
    assert nira_evals.run_evals([no_figure, wrong_stage]).failed == 2
    rules = dict(nira_evals.RULES, instructions="You are Nira. Answer every question.")
    shown = nira_evals._run(_case("opinion_refused"), ScriptedModel([nira_evals._refuse]), rules)
    assert shown[1] is False
