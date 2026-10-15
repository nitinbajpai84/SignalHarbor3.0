"""M2-E4: the "ready to build" gate over the whole baseline, pure functions (reads nothing, writes nothing).

Signing needs: every measure ready to build (or left out by the organiser or sponsor, with a reason), the glossary reviewed, governance decided,
and no open question. `check` is worked out over EVERY measure (domain/readiness.ready_to_build with the all-seeing open count), so the gate is
the same for everyone; `for_viewer` then shows one person only the reasons about what they may see, plus one plain line when something they
may not see is still open. Reasons are counts and parts; they never name a field, source or another measure.
"""
from modules.m2_baseline.domain import readiness as R

RESTRICTED = R.OPEN_RESTRICTED
FIX = {"measures": "baselines", "glossary": "glossary", "governance": "governance", "open": "questions"}  # the step of the bar where each is fixed
LEFT_OUT_NEEDS = "Please say why this measure is left out."


def accepted_risks(kpis: list[dict], left_out: dict) -> list[dict]:
    """The questions accepted as known risks, with who accepted them and why. A measure left out carries none."""
    return [{"kpi_id": k["id"], "id": a["id"], "kind": a["kind"], "text": a["text"], "question": a.get("question", ""), "where": a.get("where", ""),
             "status": "accepted", "reason": a.get("reason") or a.get("resolution") or "", "by": a.get("by"), "at": a.get("at"),
             **({"refs": a["refs"]} if a.get("refs") else {})}
            for k in kpis if isinstance(k, dict) and k.get("id") and k["id"] not in left_out
            for a in k.get("ambiguities") or [] if a.get("status") == "accepted"]


def left_out_rows(kpis: list[dict], left_out: dict) -> list[dict]:
    names = {k["id"]: k.get("name") or k["id"] for k in kpis if isinstance(k, dict) and k.get("id")}
    return [{"kpi_id": kid, "name": names[kid], "reason": got["reason"], "by": got["by"], "at": got["at"]} for kid, got in left_out.items() if kid in names]


def refusal(not_ready: int, total: int, glossary_ok: bool, governance_ok: bool, open_n: int, restricted: bool = False) -> str:
    """The plain sentence a refused signature carries (and the screen shows above the checklist)."""
    bits = []
    if not total:
        bits.append("there are no measures in the baseline")
    elif not_ready:
        bits.append(f"{total - not_ready} of {total} measures are ready to build")
    if not glossary_ok:
        bits.append("the glossary has not been reviewed yet")
    if not governance_ok:
        bits.append("governance is not decided yet")
    if open_n:
        bits.append(f"{open_n} open {'question remains' if open_n == 1 else 'questions remain'}")
    if restricted:
        bits.append(RESTRICTED[:1].lower() + RESTRICTED[1:-1])
    return ("The baseline cannot be signed yet: " + "; ".join(bits) + ". Fix these, or leave a measure out of this baseline with a reason.") if bits else ""


def check(kpis: list[dict], derived: dict, left_out: dict, glossary: tuple[bool, list[str]], governance: tuple[bool, list[str]], open_n: int) -> dict:
    """The gate over every measure. `derived` is `store.ambiguities.derived_open_all`; `open_n` the open questions of the measures that count."""
    items = []
    for k in kpis:
        if not (isinstance(k, dict) and k.get("id")) or k["id"] in left_out:
            continue
        ok, why = R.ready_to_build(k, derived.get(k["id"], 0))
        items.append({"kpi_id": k["id"], "name": k.get("name") or k["id"], "ready": ok, "reasons": why, "open": R.open_total(k, derived.get(k["id"], 0))})
    bad = sum(1 for i in items if not i["ready"])
    gl, gv = {"ok": glossary[0], "reasons": glossary[1]}, {"ok": governance[0], "reasons": governance[1]}
    ok = bool(items) and not bad and gl["ok"] and gv["ok"] and not open_n
    return {"ok": ok, "measures": {"ready": len(items) - bad, "total": len(items), "items": items}, "glossary": gl, "governance": gv, "open": {"n": open_n},
            "left_out": left_out_rows(kpis, left_out), "restricted": False, "fix": FIX,
            "refusal": refusal(bad, len(items), gl["ok"], gv["ok"], open_n)}


def for_viewer(full: dict, seen: set[str], visible_open: dict[str, int], open_n: int, glossary: tuple[bool, list[str]], governance: tuple[bool, list[str]]) -> dict:
    """The gate as one person may see it. `ok` is the whole baseline's (the same for everyone). The counts, reasons and measures are theirs; when
    something they may not see is also open, `restricted` is set and the sentence says so, with no detail."""
    all_items = full["measures"]["items"]
    mine = [{**i, "reasons": R.reasons_for_viewer(i["reasons"], i["open"], visible_open.get(i["kpi_id"], 0))} for i in all_items if i["kpi_id"] in seen]
    bad = sum(1 for i in mine if not i["ready"])
    hidden_open = any(not i["ready"] for i in all_items if i["kpi_id"] not in seen)
    gl = {"ok": full["glossary"]["ok"], "reasons": glossary[1]}
    gv = {"ok": full["governance"]["ok"], "reasons": governance[1]}
    restricted = (hidden_open or (not gl["ok"] and not gl["reasons"]) or (not gv["ok"] and not gv["reasons"]) or full["open"]["n"] > open_n)
    mine_out = [r for r in full["left_out"] if r["kpi_id"] in seen]
    return {**full, "measures": {"ready": len(mine) - bad, "total": len(mine), "items": mine}, "glossary": gl, "governance": gv, "open": {"n": open_n},
            "left_out": mine_out, "restricted": restricted,
            "refusal": "" if full["ok"] else (refusal(bad, len(mine), gl["ok"] or not gl["reasons"], gv["ok"] or not gv["reasons"], open_n, restricted)
                                              or "The baseline cannot be signed yet. " + RESTRICTED)}
