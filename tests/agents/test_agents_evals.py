import pytest

from sh_platform.agents.evals.cases import CASES
from sh_platform.agents.evals import harness
from sh_platform.agents.evals.harness import LiveRefused, main, run_evals
from sh_platform.agents.protocols import ModelReply


def test_five_neutral_cases_pass_with_stub():
    assert len(CASES) == 6
    res = run_evals(CASES)
    assert (res.total, res.passed, res.failed) == (6, 6, 0), res.results


def test_a_failing_case_is_counted():
    bad = type(CASES[0])(**{**CASES[0].__dict__, "must_include": ["zzz never"]})
    res = run_evals([bad])
    assert (res.passed, res.failed) == (0, 1)


def test_live_refused_without_real_client():
    with pytest.raises(LiveRefused):
        run_evals(CASES, live=True)
    assert main(["--live"]) == 2


def test_live_runs_with_real_client_object():
    class Real:
        def complete(self, module_id, messages, tools=None):
            return ModelReply("Not available yet.", [])

    assert run_evals(CASES[:1], Real(), live=True).total == 1


def test_mutant_gate_always_true_is_caught(monkeypatch):
    case = next(c for c in CASES if c.id == "switched_off_tool_refused")
    assert run_evals([case]).passed == 1
    monkeypatch.setattr(harness._Gate, "is_enabled", lambda self, company_id, module_id: True)
    assert run_evals([case]).failed == 1


def test_mutant_registry_gate_ignored_is_caught(monkeypatch):
    from sh_platform.agents.registry import ToolRegistry
    case = next(c for c in CASES if c.id == "switched_off_between_steps")
    assert run_evals([case]).passed == 1
    monkeypatch.setattr(ToolRegistry, "call",
                        lambda self, c, m, n, a: self._tools[(m, n)]["func"](**a))
    assert run_evals([case]).failed == 1
