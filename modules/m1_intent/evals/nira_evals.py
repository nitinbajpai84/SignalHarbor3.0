"""Nira's five evals (M1-07): welcome, a rules question, a time warning, "what do I do now", an opinion refused.

Built on the kernel's evals pieces (`sh_platform.agents.evals.harness`): the scripted stub model is the default,
and a live run needs a real model client from the caller (refused otherwise). The stub is not a script of fixed
strings only: it reads the rules out of the context it is shown, so a case also proves the rules reached Nira.
Run: python -m modules.m1_intent.evals.nira_evals [--live]. Synthetic, neutral content.
"""
import json
import sys
from dataclasses import dataclass, field

from modules.m1_intent.agent import nira
from modules.m1_intent.domain import briefing as B
from sh_platform.agents.evals.harness import EvalResult, LiveRefused, ScriptedModel
from sh_platform.agents.protocols import ModelClient, ModelReply

COMPANY = "eval_co"
PREP = {"purpose": "Agree what we want to know about our customers", "outcome": "A short signed list",
        "length_minutes": 20, "split": {"briefing": 4, "individual": 8, "together": 8}}
RULES = nira.load_rules()


class _Gate:
    def is_enabled(self, company_id: str, module_id: str) -> bool:
        return True


@dataclass
class NiraCase:
    id: str
    kind: str
    script: object  # ModelReply or callable(messages) -> ModelReply
    question: str = ""
    extra: str = ""
    stage: str = "briefing"
    must_include: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)


def _context(messages: list[dict]) -> dict:
    return json.loads(messages[1]["content"])["context"]


def _rule(messages: list[dict], rule_id: str) -> str:
    return _context(messages)["rules"][rule_id]


def _welcome(m) -> ModelReply:
    return ModelReply(f"Welcome, everyone. We are here to {_rule(m, 'purpose')[0].lower()}{_rule(m, 'purpose')[1:]}. First we read the rules together.")


def _time_answer(m) -> ModelReply:
    return ModelReply(_rule(m, "time"))


def _refuse(m) -> ModelReply:
    return ModelReply(RULES["refusal_note"] if "opinion" in m[0]["content"].lower() else "I think it is cost.")


def _asked(messages: list[dict]) -> str:
    return json.loads(messages[1]["content"])["question"]


def _warning(m) -> ModelReply:
    """Warns only if the one-minute figure reached her."""
    if "one minute" in _asked(m).lower():
        return ModelReply("About one minute is left. Please finish the note you are writing.")
    return ModelReply("Time is passing.")


def _now(m) -> ModelReply:
    """Tells the person what to do at the briefing only if she was told the stage is the briefing."""
    if _context(m)["stage"] == "briefing":
        return ModelReply("Read the rules on this screen, then tell me you are clear or ask a question.")
    return ModelReply("Carry on.")


def _fact(marker: str):
    """Answers with the fact she was given that holds `marker`: so a case fails if the fact never reached her."""
    def reply(m) -> ModelReply:
        c = _context(m)
        text = " ".join([c.get("privacy", ""), c.get("session_facts", "")])
        i = text.find(marker)
        return ModelReply(text[i:i + 500] if i >= 0 else "I do not know.")
    return reply


CASES = [
    NiraCase("welcome", "welcome", _welcome, must_include=["Welcome", "Agree what we want to know"]),
    NiraCase("rules_question", "ask", _time_answer, question="How long do we have in total?",
             must_include=["20 minutes"]),
    NiraCase("time_warning", "warning", _warning,
             extra="One minute is left in this stage.", stage="private_rooms", must_include=["minute"]),
    NiraCase("what_do_i_do_now", "now", _now,
             must_include=["rules", "clear"]),
    NiraCase("opinion_refused", "ask", _refuse, question="What do you think is the biggest problem we have?",
             must_include=["not the expert", "North"], must_not_include=["I think", "I believe", "you should"]),
    NiraCase("im_done", "ask", _fact("I'm done is a button"), question="What does I'm done do?", stage="together",
             must_include=["ready", "ends nothing", "organiser sees how many"]),
    NiraCase("finish_early", "ask", _fact("finishes the room stage early"), question="How does the organiser finish early?", stage="together",
             must_include=["We're done, go to the charter", "Back in the room"]),
    NiraCase("unsent_notes", "ask", _fact("saved but never sent"), question="What happens to notes I did not send?", stage="private_rooms",
             must_include=["posted for the person", "anonymously", "never confirmed their name"]),
    NiraCase("summary_page", "ask", _fact("The summary is one"), question="What is the summary page?", stage="closed",
             must_include=["read-only page", "who contributed what"]),
    NiraCase("private_chat", "ask", _fact("private chat"), question="Does anyone in the company read my chat with North?", stage="private_rooms",
             must_include=["only by you"], must_not_include=["nobody in the company"]),
]


def _run(case: NiraCase, model: ModelClient, rules: dict = RULES) -> tuple[str, bool, list[str]]:
    text = nira.ask_nira(model, _Gate(), None, COMPANY, "Eval Co", "unlisted", stage=case.stage,
                         rules=B.build_rules(PREP, _settings()), kind=case.kind, question=case.question,
                         extra=case.extra, instructions=rules)
    low = text.lower()
    why = [f"missing: {p}" for p in case.must_include if p.lower() not in low]
    why += [f"forbidden: {p}" for p in case.must_not_include if p.lower() in low]
    return case.id, not why, why


def _settings() -> B.BriefingSettings:
    return B.load_settings()


def run_evals(cases: list[NiraCase], model: ModelClient | None = None, *, live: bool = False) -> EvalResult:
    if live and (model is None or isinstance(model, ScriptedModel)):
        raise LiveRefused("A live run needs a real model client from the caller.")
    return EvalResult([_run(c, model if live else ScriptedModel([c.script])) for c in cases])


def main(argv: list[str] | None = None, client: ModelClient | None = None) -> int:
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
