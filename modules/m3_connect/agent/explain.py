"""Lens words the likely reason of a gap (M3-P03). It is shown the reasons code already worked out (counts, dates, column names), nothing else:
no row, no figure of ours or theirs. If the model is missing, refuses, or changes a number, the deterministic reasons stand."""
from modules.m3_connect.agent.compile import AGENT_NAME, MODULE_ID, figures
from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry
from sh_platform.agents.runs import RunRegistry

SYSTEM = ("You are Lens, a business analyst. You are given the reasons, already worked out, why two figures for one measure differ. "
          "Say the same thing in at most two short plain sentences for a finance manager. Do not add a cause, a number or a name that is not given. "
          "Reply with the sentences only.")


def reword(model, gate, company_id: str, plane, name: str, reasons: list[str]) -> str | None:
    """One short wording of the reasons, or None (keep the deterministic text)."""
    if model is None or not reasons:
        return None
    text = " ".join(reasons)
    res = run_agent(model, ToolRegistry(gate), company_id, MODULE_ID, AGENT_NAME, SYSTEM,
                    {"measure": name, "reasons": reasons, "facts": figures(text)}, "Reword the reasons.", recorder=RunRegistry(plane))
    out = " ".join(res.text.split())
    return out if res.status == "done" and out and not res.numbers_replaced and not out.startswith("{") else None


def reword_all(model, gate, company_id: str, plane, trial: dict, names: dict) -> dict:
    for mid, t in trial.items():
        if t.get("result") == "gap" and t.get("reasons"):
            t["likely_reason_lens"] = reword(model, gate, company_id, plane, str(names.get(mid) or ""), t["reasons"])
    return trial
