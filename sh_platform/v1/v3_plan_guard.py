"""A missing build plan is never a dead end (round 5, bug 1).

The design pack's approval also draws and approves the build plan (b10_pack._approve_plan_with). When drawing fails the pack stays approved and
keeps the reason in `plan_error`, and the run on a copy then only says "This project has no build plan yet.". Here Harbor retries the plan once
(the head of data's retry on the pack screen) and, when it still fails, asks a question that names the step and its reason.
"""
from __future__ import annotations

import re

from sh_platform.v1 import b10_pack as K
from sh_platform.v1 import b6_run


def ensure_plan(x) -> None:
    from sh_platform.v1.v3_harbor import Q
    pid = x.th["pid"]
    if (b6_run.latest_plan(x.plane, pid, live=True) or {}).get("state") in b6_run.LIVE_OK:  # c8: a plan only drawn (proposed) is no plan the builder runs
        return
    pack = K.latest_approved(x.plane, pid)
    if pack is None:
        raise Q("The design pack is not approved yet, so there is no build plan to run. Say retry once the head of data has approved it.")
    try:
        x.api("anita", "POST", f"/api/v1/build/p/{pid}/architecture/pack/plan/approve", {})
    except Q as e:
        why = (K.latest_approved(x.plane, pid) or pack).get("plan_error") or e.text
        raise Q(f"I could not draw the build plan from the approved design pack (version {pack['version']}): {why} "
                "The figure's design needs a fix before it can run. Say retry after it is changed.") from None
    if (b6_run.latest_plan(x.plane, pid, live=True) or {}).get("state") not in b6_run.LIVE_OK:
        raise Q(f"The design pack (version {pack['version']}) is approved but its build plan is not approved. Say retry to try again.")


# ---- Decision 1: a data build names its figures (c6 follow-up 2) ------------------------------------------------------------------------

FIGURES_GAP = "Which figures do you want?"


def figures_gap(plane, th: dict, iid: str | None) -> list[str]:
    """[FIGURES_GAP] when the brief names no figure and the build is not process-only (v3_process): a data build with no figures reaches Build
    as "The plan has no tables.", so Decision 1 shows it as a gap, filled by the usual practice or by asking. [] otherwise."""
    if not iid:
        return []
    from sh_platform.v1 import i4_sow as S, v3_process as P
    try:
        sow = S.read(plane, iid)
    except Exception:  # noqa: BLE001 - no brief to read: nothing to say about its figures
        return []
    if any(isinstance(k, dict) and k.get("name") for k in sow.get("kpis") or []) or P.is_process(plane, th, sow):
        return []
    return [FIGURES_GAP]


# ---- the plan check: a rate divides (c6 follow-up 3) ----------------------------------------------------------------------------------

RATE_WORDS = re.compile(r"\b(?:rates?|shares?|ratios?|percent(?:age)?s?|pct)\b", re.I)
DIVIDES = re.compile(r"/|\b(?:avg|mean|divide)\s*\(", re.I)
AGGREGATES = re.compile(r"\b(?:count|sum)\s*\(", re.I)


def rate_without_division(t: dict) -> str | None:
    """Why a ready table may not stand: a figure named rate, share, ratio or percent is counted or summed but never divided ("trade match rate" was
    100 x matched trades). A cheap SQL text check; a rate read as it is (no count or sum) is left alone. None when it passes."""
    sql = re.sub(r"--[^\n]*|'[^']*'", " ", str(t.get("sql") or ""))
    names = [str(k) for k in t.get("kpis") or []] + [c for c in t.get("col_defs") or {}]
    rates = [n for n in names if RATE_WORDS.search(n.replace("_", " "))]
    if not rates or DIVIDES.search(sql) or not AGGREGATES.search(sql):
        return None
    return (f"{rates[0]} is a rate, share, ratio or percent, but the SQL never divides: it counts or sums without dividing by the total. "
            "Divide the part by the whole (for example matched trades / all trades)")
