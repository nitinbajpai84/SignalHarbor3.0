"""The guide's shared part (Nira, M1-07 and M2): moved out of modules/m1_intent/agent/nira.py when module 2 needed it
(rules/modules.md: shared code goes to sh_platform once a second module needs it). What stays in each module: its own
instructions file, its fixed messages and its session facts. Nothing here makes a network call: the guide runs only
through the kernel agent runtime (`run_agent`) and the `ModelClient` protocol, and what she is shown holds no pack content."""
import re
from pathlib import Path

import yaml

from sh_platform.agents.context import build_context_pack
from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry
from sh_platform.packs import EmptyPack

ANSWER_KEYS = ("name", "role", "instructions", "tasks", "messages", "avoid_terms", "fallback", "unavailable")


def load_yaml(path, keys=ANSWER_KEYS) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not (isinstance(data, dict) and all(k in data for k in keys)):
        raise ValueError("The guide's instructions are not complete.")
    return data


def cut(text: str, limit: int) -> str:
    """At most `limit` characters, ended at a whole sentence when there is one in the second half."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    end = max(head.rfind(". "), head.rfind("! "), head.rfind("? "))
    return head[:end + 1] if end > limit // 2 else head.rstrip()


def plain(text: str, rules: dict) -> str:
    bad = "|".join(re.escape(t) for t in rules["avoid_terms"])
    return rules["fallback"] if re.search(rf"\b(?:{bad})\b", text, re.IGNORECASE) else text


def figures_note(*texts: str) -> str:
    """The figures the guide's own facts state, so she may repeat them (the kernel guard replaces any other figure)."""
    nums = re.findall(r"\d+", " ".join(texts))
    return "Figures you may state: " + ", ".join(dict.fromkeys(nums)) + "." if nums else ""


def quiet_context(company_name: str, industry: str, question: str) -> dict:
    """The kernel's context pack with no pack content and no empty-state note: her context holds no industry knowledge."""
    ctx = build_context_pack({"name": company_name, "industry": industry}, EmptyPack(industry), [], question, max_facts=0)
    ctx.pop("empty_state", None)
    return ctx


def ask_guide(model, gate, recorder, company_id: str, module_id: str, cfg: dict, ctx: dict, asked: str, reply_max: int) -> str:
    """One model turn as the guide: plain text, cut, with a fallback for engineer words."""
    res = run_agent(model, ToolRegistry(gate), company_id, module_id, cfg["name"], cfg["instructions"], ctx, asked,
                    recorder=recorder)
    return cut(plain(res.text, cfg), reply_max) if res.status == "done" else res.text
