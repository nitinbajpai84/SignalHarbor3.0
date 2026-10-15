"""Evals harness: scripted stub model by default; a live run needs a real ModelClient from the caller."""
import sys
from dataclasses import dataclass, field

from sh_platform.agents.context import build_context_pack
from sh_platform.agents.guard import check_numbers
from sh_platform.agents.loop import run_agent
from sh_platform.agents.protocols import ModelClient, ModelReply
from sh_platform.agents.registry import ToolRegistry
from sh_platform.packs import EmptyPack

COMPANY, MODULE = "eval_co", "eval_module"


class LiveRefused(RuntimeError):
    """A live eval was asked for without a real model client."""


@dataclass
class EvalCase:
    id: str
    question: str
    facts: list[dict]
    must_include: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)
    expected_numbers_traced: bool = True  # every number left in the shown answer traces to a fact
    script: list = field(default_factory=list)  # ModelReply or callable(messages) -> ModelReply
    tools: list[tuple] = field(default_factory=list)  # (module_id, name, func, outside)
    industry: str = "unlisted"
    switch_off_after_step: int | None = None  # the module goes off after this many model calls
    expect_status: str | None = None
    expect_tools_called: list[str] | None = None
    module_on: bool = True  # False: the gate switches the case's module off for the company


@dataclass
class EvalResult:
    results: list[tuple[str, bool, list[str]]]

    total = property(lambda self: len(self.results))
    passed = property(lambda self: sum(ok for _, ok, _ in self.results))
    failed = property(lambda self: self.total - self.passed)


class ScriptedModel:
    """The default stub: plays the case's script in order (the last step repeats)."""

    def __init__(self, script: list):
        self.script = list(script)

    def complete(self, module_id, messages, tools=None) -> ModelReply:
        step = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        return step(messages) if callable(step) else step


class _SwitchOff:
    """Wraps the case's model and switches the gate off once it has answered `after` times."""

    def __init__(self, model, gate, after: int):
        self.model, self.gate, self.after, self.n = model, gate, after, 0

    def complete(self, module_id, messages, tools=None):
        reply = self.model.complete(module_id, messages, tools)
        self.n += 1
        if self.n >= self.after:
            self.gate.module_on = False
        return reply


class _Gate:
    def __init__(self, module_on: bool = True):
        self.module_on = module_on

    def is_enabled(self, company_id: str, module_id: str) -> bool:
        return self.module_on and module_id == MODULE


def _run_case(case: EvalCase, model: ModelClient | None) -> tuple[str, bool, list[str]]:
    gate = _Gate(case.module_on)
    registry = ToolRegistry(gate)
    for module_id, name, func, outside in case.tools:
        registry.register(module_id, name, func, read_only=True, description=name,
                          parameters={}, outside=outside)
    ctx = build_context_pack({"name": "Eval Co", "industry": case.industry}, EmptyPack(case.industry),
                             case.facts, case.question, max_facts=20)
    model = model or ScriptedModel(case.script)
    if case.switch_off_after_step:
        model = _SwitchOff(model, gate, case.switch_off_after_step)
    out = run_agent(model, registry, COMPANY, MODULE, "Eval",
                    "You answer from the recorded facts.", ctx, case.question, fast={"off": True})  # evals test the model path and its guard
    why = [f"missing: {p}" for p in case.must_include if p.lower() not in out.text.lower()]
    why += [f"forbidden: {p}" for p in case.must_not_include if p.lower() in out.text.lower()]
    if case.expect_status and out.status != case.expect_status:
        why.append(f"status {out.status}")
    if case.expect_tools_called is not None and out.tools_called != case.expect_tools_called:
        why.append("unexpected tools called")
    if case.expected_numbers_traced and not check_numbers(out.text, case.facts, case.question).ok:
        why.append("an untraced number is still shown")
    return case.id, not why, why


def run_evals(cases: list[EvalCase], model: ModelClient | None = None, *, live: bool = False) -> EvalResult:
    if live and (model is None or isinstance(model, ScriptedModel)):
        raise LiveRefused("A live run needs a real model client from the caller.")
    return EvalResult([_run_case(c, model if live else None) for c in cases])


def main(argv: list[str] | None = None, client: ModelClient | None = None) -> int:
    from sh_platform.agents.evals.cases import CASES

    live = "--live" in (sys.argv[1:] if argv is None else argv)
    try:
        res = run_evals(CASES, client, live=live)
    except LiveRefused as e:
        sys.stderr.write(f"{e}\n")
        return 2
    sys.stdout.write(f"{res.passed} passed, {res.failed} failed of {res.total}\n")
    return 0 if res.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
