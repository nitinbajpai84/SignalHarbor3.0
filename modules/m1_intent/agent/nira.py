"""Nira, the guide (M1-07). She runs only through the kernel agent runtime (`sh_platform.agents.run_agent`) and the
`ModelClient` protocol: this file makes no model call, no network call and holds no provider. Her instructions are
in nira_rules.yaml. What she is shown: the company's name, the stage and the rules of the prepared session, nothing
else (no pack content, no facts, no documents). Every run goes to the run registry, which keeps no content.
"""
import re
from pathlib import Path

import yaml

from sh_platform.agents import guide  # the part module 2's Nira shares (moved to the kernel when module 2 needed it)
from sh_platform.agents.protocols import ModelClient

MODULE_ID = "m1_intent"
RULES_FILE = Path(__file__).with_name("nira_rules.yaml")
KINDS = ("welcome", "ask", "now", "warning")
FIXED = ("welcome", "now", "warning")  # not model turns: the state machine's own messages (see nira_rules.yaml)
_KEYS = ("name", "role", "instructions", "tasks", "messages", "refusal_note", "avoid_terms", "fallback", "unavailable")


def load_rules(path=None) -> dict:
    data = yaml.safe_load(Path(path or RULES_FILE).read_text(encoding="utf-8"))
    ok = isinstance(data, dict) and all(k in data for k in _KEYS) and "ask" in data["tasks"]
    ok = ok and isinstance(data["messages"], dict) and set(FIXED) <= set(data["messages"])
    ok = ok and {"now", "wrap_up"} <= set(data["messages"]) and "default" in data["messages"]["wrap_up"]
    if not ok:
        raise ValueError("Nira's instructions are not complete.")
    return data


def _ended(sentence: str) -> str:
    """The organiser's own words rarely end with a full stop; the next sentence must not run on."""
    return sentence if sentence.rstrip().endswith((".", "!", "?")) else sentence.rstrip() + "."


def say(cfg: dict, kind: str, stage: str, rules: list[dict], extra: str = "", nearly_up: bool = True) -> str:
    """The fixed message for welcome, what to do now and the time warning: chosen by the stage, filled with the
    prepared session's own words. No model, so it works with no key and says the same thing every time."""
    m, said = cfg["messages"], {r["id"]: r["text"] for r in rules}
    if kind == "welcome":
        text = _ended(m["welcome"].format(purpose=said.get("purpose", "to agree what we want to know")))
        if said.get("outcome"):
            text += _ended(m["welcome_outcome"].format(outcome=said["outcome"]))
        return text + m["welcome_close"]
    if kind == "now":
        return m["now"].get(stage, m["now"]["draft"])
    wrap = m["wrap_up"].get(stage, m["wrap_up"]["default"])
    # "nearly up" only inside the warning threshold; before it she just says how long is left
    if not nearly_up:
        return " ".join(p for p in (extra[:1].upper() + extra[1:], wrap) if p)
    return " ".join(p for p in (m["warning"].format(wrap_up=wrap), extra) if p)


def build_pack(company_name: str, industry: str, stage: str, rules: list[dict], question: str, privacy: str = "",
               session_facts: str = "") -> dict:
    """The kernel's context pack with no pack content, plus the stage and the session's rules."""
    ctx = guide.quiet_context(company_name, industry, question)
    # one object, not a list of objects: the egress gateway reads a list of records as rows and would refuse it
    return {**ctx, "stage": stage, "rules": {r["id"]: r["text"] for r in rules}, "privacy": privacy,
            "session_facts": session_facts}


def _figures(rules: list[dict], extra: str) -> str:
    """The figures the session itself states, so she may repeat them (the kernel guard replaces any other figure)."""
    return guide.figures_note(" ".join(r["text"] for r in rules), extra)


_cut, _plain = guide.cut, guide.plain


def minutes_not_seconds(text: str) -> str:
    """"332 seconds are left" reads "about 5 minutes are left": a person thinks in minutes, not seconds."""
    def say_it(m: re.Match) -> str:
        mins = int(m.group(1)) // 60
        return "less than a minute" if mins < 1 else "about 1 minute" if mins == 1 else f"about {mins} minutes"
    return re.sub(r"\b(\d+) seconds?\b", say_it, text)


def ask_nira(model: ModelClient, gate, recorder, company_id: str, company_name: str, industry: str, *,
             stage: str, rules: list[dict], kind: str, question: str = "", extra: str = "",
             reply_max: int = 600, instructions: dict | None = None, nearly_up: bool = True) -> str:
    """Nira's reply as plain text. `gate` is the entitlement gate; `recorder` is the company's run registry.
    Welcome, now and warning are fixed messages (no model call); only "ask" goes to the model."""
    cfg = instructions or load_rules()
    extra = minutes_not_seconds(extra)
    if kind in FIXED:
        return _cut(say(cfg, kind, stage, rules, extra, nearly_up), reply_max)
    task = cfg["tasks"][kind]
    asked = " ".join(p for p in (task, question.strip(), extra, _figures(rules, extra)) if p)
    ctx = build_pack(company_name, industry, stage, rules, asked, " ".join(cfg.get("privacy_facts", [])),
                    " ".join(cfg.get("session_facts", [])))
    return guide.ask_guide(model, gate, recorder, company_id, MODULE_ID, cfg, ctx, asked, reply_max)
