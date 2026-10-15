"""Nira, the guide, in module 2 (M2-AGENTS). The shared part is sh_platform/agents/guide.py (moved there from module 1's
nira.py when module 2 became the second user); this file holds module 2's own: her instructions (nira_rules.yaml), her
fixed messages and her session facts. The facts are built here from the baseline's own state, in code, so what she
says matches what is recorded; the model only words an answer to a question. She is shown no pack content."""
from pathlib import Path

from sh_platform.agents import guide

MODULE_ID = "m2_baseline"
RULES_FILE = Path(__file__).with_name("nira_rules.yaml")
KINDS = ("welcome", "ask", "now")
STEPS = ("baselines", "requests", "process-map", "catalogue", "signoff")
LABELS = {"baselines": "the work list", "requests": "requests to the owners", "process-map": "the process map",
          "catalogue": "the data catalogue", "signoff": "review and sign-off"}


def load_rules() -> dict:
    return guide.load_yaml(RULES_FILE, guide.ANSWER_KEYS + ("screens",))


def lines(s: dict, cfg: dict) -> str:
    """The session facts as plain sentences, from the state `s`: {step, signed, measures, owners_complete, definitions,
    open_questions, requests, answered, waiting [names], mapped}. Every number is a count of what is recorded."""
    n = STEPS.index(s["step"]) + 1
    out = [f"The baseline has five steps: {', '.join(f'{i} {LABELS[x]}' for i, x in enumerate(STEPS, 1))}.",
           f"The person is on step {n}: {LABELS[s['step']]}. Help for this screen: {cfg['screens'][s['step']]}",
           f"{s['measures']} measures are on the work list; {s['owners_complete']} have all three owners named; {s['definitions']} have a definition; "
           f"{s['open_questions']} questions to the business are still open.",
           f"{s['requests']} requests to owners have been sent; {s['answered']} are answered.",
           f"{s['mapped']} measures have a process map."]
    if s.get("held"):
        out.append(f"{s['held']} uploaded document(s) wait for the organiser to decide whether they hold personal data; Lens cannot use them until then.")
    out.append("Still waiting for an answer from: " + ", ".join(s["waiting"]) + "." if s["waiting"] else "Nobody is waited on for an answer.")
    out.append("The baseline is signed and read-only." if s["signed"] else "The baseline is not signed yet. Each owner signs their own part and the sponsor countersigns.")
    return " ".join(out)


def next_key(s: dict) -> str:
    if s["signed"]:
        return "signed"
    if not s["measures"]:
        return "no_measures"
    if s["owners_complete"] < s["measures"]:
        return "owners"
    if not s["requests"]:
        return "requests"
    if s["waiting"]:
        return "waiting"
    return "map" if s["mapped"] < s["measures"] else "review"


def say(kind: str, s: dict, cfg: dict) -> str:
    """The fixed messages (where you are, what is next): no model, so they work with no key and say the same thing every time."""
    m = cfg["messages"]
    if kind == "now":
        return m["now"][next_key(s)]
    progress = m["signed"] if s["signed"] else m["now"][next_key(s)]
    if s["waiting"] and not s["signed"]:
        progress = m["waiting"].format(names=", ".join(s["waiting"])).strip() + " " + progress
    held = m["held"].format(n=s["held"], docs="document waits" if s["held"] == 1 else "documents wait") + " " if s.get("held") else ""
    return m["welcome"].format(n=STEPS.index(s["step"]) + 1, label=LABELS[s["step"]], progress=held + progress)


def ask_nira(model, gate, recorder, company_id: str, company_name: str, industry: str, *, state: dict, question: str,
             cfg: dict | None = None, reply_max: int = 500) -> str:
    cfg = cfg or load_rules()
    facts = lines(state, cfg)
    asked = " ".join(p for p in (cfg["tasks"]["ask"], question.strip(), guide.figures_note(facts)) if p)
    ctx = {**guide.quiet_context(company_name, industry, asked), "session_facts": facts}
    return guide.ask_guide(model, gate, recorder, company_id, MODULE_ID, cfg, ctx, asked, reply_max)
