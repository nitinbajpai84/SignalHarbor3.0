"""North drafts the "So that ..." line of each ticked problem from its notes (M1-24), on the kernel agent runtime.

The call goes through the egress runtime like the grouping does (agent/gather.py): the problems and their notes go in as
plain text lines, the reply is plain text lines ("p1: ..."), labels are short (p1, p2...) so the model never sees an id.
The model sees the notes' words only (no author, time or position); names inside the words are tokenised by the
gateway. A draft is only text for a person to check: the caller labels it a draft and never lets it replace a human edit.
With no model, or a reply that cannot be read, nothing is drafted: the line stays blank and the organiser is asked.
"""
import logging
import re
from pathlib import Path

import yaml

from modules.m1_intent.domain import charter as C
from modules.m1_intent.domain import private_room as R
from modules.m1_intent.tools.pack_tools import MODULE_ID
from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry

log = logging.getLogger(__name__)
AGENT_NAME = "North"
RULES_FILE = Path(__file__).with_name("charter_lines_rules.yaml")
NOTES_PER_PROBLEM = 8   # chosen: enough to show the pattern, small enough to stay one short call
NOTE_CHARS = 300
# live Gemini wrote `p1': 'text'` (4 October): the label may carry a quote or asterisks, the text a quote or trailing comma
_LINE = re.compile(r"^\s*(?:[-*]\s*)?\**(p\d+)\**['\"]?\s*[:=]\s*(.+?)[,;]?\s*$", re.IGNORECASE)


def load_rules() -> dict:
    return yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))


def system_prompt(north: dict | None = None) -> str:
    rules = load_rules()
    role = str((north or {}).get("advisor_role") or "").strip() or "the industry expert"
    return "\n\n".join([rules["role"].strip().format(advisor_role=role), "Rules:\n" + "\n".join(f"- {r}" for r in rules["rules"])])


def build_question(problems: list[dict]) -> tuple[str, dict[str, str]]:
    """(the plain-text instruction, label -> problem id). `problems` are {id, title, notes: [text]}."""
    labels, lines = {}, ["Problems and the notes about them (label: problem):"]
    for p in problems:
        labels[f"p{len(labels) + 1}"] = p["id"]
        lines.append(f"- p{len(labels)}: {' '.join(p['title'].split())}")
        lines += [f"  - note: {' '.join(t.split())[:NOTE_CHARS]}" for t in p["notes"][:NOTES_PER_PROBLEM]]
    return "\n".join(lines), labels


def parse(text: str, labels: dict[str, str], limit: int) -> dict[str, str]:
    """problem id -> "So that ..." sentence, for each readable line; the prefix is added when North left it out, and
    a line over `limit` (prefix included) is left out."""
    out = {}
    for ln in (text or "").splitlines():
        m = _LINE.match(ln)
        if m and m.group(1).lower() in labels:
            raw = m.group(2)
            if raw[0] in "'\"" and (len(raw) < 2 or raw[-1] != raw[0]):
                continue  # a quote opened and never closed: the reply was cut off in this line
            if raw[0] in "'\"":
                raw = raw[1:-1]
            line = C.with_so_that(raw)
            if line and len(line) <= limit:
                out[labels[m.group(1).lower()]] = line
    return out


def draft_lines(model, gate, recorder, company_id: str, problems: list[dict], limit: int, north: dict | None = None) -> dict[str, str]:
    """One call per problem, so a line is drafted from that problem's own notes only (the model never sees the others, as
    with prefill). {} when there is nothing to draft, no model, or no reply can be used; a failed call skips its problem."""
    out: dict[str, str] = {}
    for p in problems if model is not None else []:
        question, labels = build_question([p])
        ctx = {"stage": "charter", "facts": R.figures(*p["notes"])}
        res = run_agent(model, ToolRegistry(gate), company_id, MODULE_ID, AGENT_NAME, system_prompt(north), ctx, question, recorder=recorder)
        if res.status != "done":
            log.warning("North's charter lines could not be used (%s)", res.status)
            continue
        out.update(parse(res.text, labels, limit))
    return out
