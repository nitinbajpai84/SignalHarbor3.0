"""Accepting the risks and signing the plan (M3-P04, the customer's actions 3 and 4). Also the files this package owns in the assessment
folder: plan.json (the plan, its edits and signatures) and decisions.json (risk decisions, keyed by risk id; P03's findings.json is never written,
the two are merged at read time).

The signing pattern is module 2's (modules/m2_baseline/domain/signoff.py `slot_for`, `countersign`, store/signoff.py `_hand_off`): the sponsor signs
first, then the head of data, as two different accounts; the second signature writes the read-only outcome record module 4 reads, once. A person who
may not see every restricted measure signs only as the sponsor, and the signature says it covers them (A-044).
"""
import logging
import secrets
from pathlib import Path

from modules.m3_connect.domain import plan as P
from modules.m3_connect.domain.plan import PlanError, contract
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
UNREADABLE = "The plan records could not be read, so nothing was changed. Please ask your administrator."
NOT_SAVED = "That could not be saved. Please try again."
SIGNED = "This plan is signed, so it can no longer be changed."
SIGNED_SENTENCE = "The plan is signed. Module 4 starts from it."


def _read(path: Path, kind=dict):
    try:
        return read_json_strict(path, kind)
    except (OSError, ValueError):
        raise PlanError("unreadable", UNREADABLE) from None


def _write(path: Path, doc) -> None:
    try:
        write_json_atomic(path, doc)
    except OSError:
        raise PlanError("unreadable", NOT_SAVED) from None


# ---- plan.json ----------------------------------------------------------------------------------------------------------------------------
def plan_path(d: Path) -> Path:
    return Path(d) / "plan.json"


def read_plan(d: Path) -> dict | None:
    doc = _read(plan_path(d))
    if doc is None:
        return None
    if not isinstance(doc.get("items"), list) or not isinstance(doc.get("signatures"), list):
        raise PlanError("unreadable", UNREADABLE)
    return doc


def save_plan(d: Path, doc: dict) -> None:
    _write(plan_path(d), doc)


def is_signed(d: Path) -> bool:
    doc = _read(plan_path(d))
    return bool(doc and doc.get("signed_at"))


def refuse_if_locked(plan: dict | None) -> None:
    """The first signature locks the plan (module 2's rule): no draft, no edit, no risk decision after it."""
    if plan and plan["signatures"]:
        names = ", ".join(f"{s['name']} ({s['label']})" for s in plan["signatures"])
        raise PlanError("locked", f"This plan is already signed by {names}, so it can no longer be changed.")


def change_plan(d: Path, apply, now: str) -> dict:
    """Read, refuse when locked, apply `apply(plan)` -> plan, save. One lock, so two edits never overwrite each other."""
    with lock_for(plan_path(d)):
        plan = read_plan(d)
        if plan is None:
            raise LookupError("no plan")
        refuse_if_locked(plan)
        plan = {**apply(plan), "updated_at": now}
        save_plan(d, plan)
        return plan


def draft_plan(d: Path, items: list[dict], now: str, assessment_id: str) -> dict:
    """Saves a freshly drafted item list, keeping every human edit (plan.merge)."""
    with lock_for(plan_path(d)):
        old = read_plan(d)
        refuse_if_locked(old)
        plan = {"assessment_id": assessment_id, "drafted_at": now, "updated_at": now, "signatures": [], "signed_at": None, "outcome_id": None,
                **{k: v for k, v in (old or {}).items() if k in ("signatures", "signed_at", "outcome_id")},
                "items": P.merge(items, (old or {}).get("items") or [])}
        save_plan(d, plan)
        return plan


# ---- decisions.json -----------------------------------------------------------------------------------------------------------------------
def decisions_path(d: Path) -> Path:
    return Path(d) / "decisions.json"


def read_decisions(d: Path) -> dict[str, dict]:
    doc = _read(decisions_path(d))
    got = (doc or {}).get("risks")
    return got if isinstance(got, dict) else {}


def with_decisions(risks: list[dict], decisions: dict[str, dict]) -> list[dict]:
    """Each risk with its decision (ours first, else the one P03 wrote) and its state."""
    out = []
    for r in risks:
        d = decisions.get(r["id"]) or r.get("decision")
        m2 = r.get("accepted_in_module_2")
        if not d and m2:  # accepted by a named person in module 2: decided already, until someone sends it back
            d = {"decision": "accepted", "note": m2.get("reason"), "by": m2.get("by"), "at": m2.get("at"), "from": "module_2"}
            out.append({**r, "decision": d, "state": "accepted"})
            continue
        out.append({**r, "decision": d, "state": P.risk_state(r, decisions.get(r["id"]))})
    return out


def _decision(kind: str, text: str, who: str, acct: str, now: str) -> dict:
    lim = contract()["limits"]
    if kind == "sent_back":
        text = P._clean(text, lim["reason"], "reason", required=True)
        return {"decision": kind, "reason": text, "note": text, "by": who, "account_id": acct, "at": now}
    return {"decision": kind, "note": P._clean(text, lim["note"], "note") or None, "by": who, "account_id": acct, "at": now}


def _remember(old: dict | None, new: dict) -> dict:
    return {**new, "history": [*((old or {}).get("history") or []), *([{k: v for k, v in old.items() if k != "history"}] if old else [])]}


def decide(d: Path, risks: list[dict], risk_id: str, kind: str, text, who: str, acct: str, now: str, hidden: set[str]) -> dict:
    """Accept (note optional) or send back (reason required) one risk. Records who and when; a later decision replaces the earlier and keeps it in history."""
    if kind not in ("accepted", "sent_back"):
        raise PlanError("invalid", "Please accept the risk or send it back.")
    risk = next((r for r in risks if r["id"] == risk_id), None)
    if risk is None:
        raise LookupError("no risk")
    if set(risk["measures"]) & hidden:
        raise PlanError("restricted", "This risk is about a restricted measure that you may not see. Someone named on it has to decide.")
    new = _decision(kind, text, who, acct, now)
    with lock_for(decisions_path(d)):
        refuse_if_locked(read_plan(d))
        doc = read_decisions(d)
        old = doc.get(risk_id)
        if old and old.get("decision") == kind:
            raise PlanError("already_decided", "This risk is already " + ("accepted." if kind == "accepted" else "sent back."))
        _write(decisions_path(d), {"risks": {**doc, risk_id: _remember(old, new)}})
    return new


def decide_all(d: Path, risks: list[dict], note, who: str, acct: str, now: str, hidden: set[str]) -> dict:
    """"Accept all remaining": every risk nobody decided yet that this person may see, each with its own record.
    Returns {accepted, left_hidden, left, message}: how many were accepted, how many were left (about restricted measures this person may not see;
    the people who can see them decide them) and why, in one plain sentence."""
    new = _decision("accepted", note, who, acct, now)
    with lock_for(decisions_path(d)):
        refuse_if_locked(read_plan(d))
        doc = read_decisions(d)
        todo = [r for r in risks if r["id"] not in doc and not r.get("decision")]
        mine = [r for r in todo if not set(r["measures"]) & hidden]
        if mine:
            _write(decisions_path(d), {"risks": {**doc, **{r["id"]: dict(new) for r in mine}}})
    left = len(todo) - len(mine)
    back = len([r for r in risks if r.get("state") == "sent_back"])
    said = [f"Accepted {len(mine)} risk{'s' if len(mine) != 1 else ''}." if mine else "No risk was waiting for you to accept."]
    if left:
        said.append(f"Left {left}: {'it is' if left == 1 else 'they are'} about {'a measure' if left == 1 else 'measures'} only some people can see, which those people decide.")
    if back:
        said.append(f"{back} sent back {'is' if back == 1 else 'are'} with Lens for a re-check.")
    return {"accepted": len(mine), "left_hidden": left, "left": left, "message": " ".join(said)}


def restricted_note(n: int) -> str | None:
    """For a viewer who cannot see them: who decides the risks about restricted measures (None when there are none)."""
    return None if not n else (f"{n} risks are about measures only some people can see; they are decided by those people." if n != 1
                               else "1 risk is about a measure only some people can see; it is decided by those people.")


def known_notes(risks: list[dict]) -> list[dict]:
    """One line per person who accepted ambiguities in module 2 (D7): the risks carry it once here, not in every text."""
    by: dict[tuple[str, str], int] = {}
    for r in risks:
        got = r.get("accepted_in_module_2")
        if got:
            key = (str(got.get("by") or "a person"), str(got.get("at") or "")[:10])
            by[key] = by.get(key, 0) + 1
    return [{"kind": "accepted_in_module_2", "by": who, "at": day or None, "count": n,
             "text": f"{n} risk{'s were' if n != 1 else ' was'} accepted in module 2 by {who}{' on ' + day if day else ''}. They are known risks and need no new decision."}
            for (who, day), n in by.items()]


# ---- signing ------------------------------------------------------------------------------------------------------------------------------
def slot_for(roles: set[str], filled: set[str]) -> str | None:
    """Only the next place in order is open: the sponsor signs first, then the head of data."""
    nxt = next((s for s in contract()["countersign"] if s["slot"] not in filled), None)
    return nxt["slot"] if nxt and roles & set(nxt["roles"]) else None


def sign(d: Path, who: str, acct: str, roles: set[str], now: str, hidden_count: int, facts: dict) -> dict:
    """The sponsor, then the head of data. Refused while any risk is undecided. The second signature writes the outcome record once.
    `facts`: names, titles and the restricted ids for the record (see build_outcome)."""
    c = contract()
    with lock_for(plan_path(d)):
        plan = read_plan(d)
        if plan is None:
            raise PlanError("no_plan", "There is no plan to sign yet. Lens drafts it once the findings are in.")
        if plan["signed_at"]:
            raise PlanError("signed", SIGNED)
        inputs = P.inputs_for_plan(d)  # read under the lock: what is signed is what is read now
        risks = with_decisions(inputs["risks"], read_decisions(d))
        waiting = [r for r in risks if not P.is_decided(r["state"])]
        if waiting:
            raise PlanError("risks_open", _open_words(waiting))
        if any(s.get("account_id") == acct for s in plan["signatures"]):
            raise PlanError("already_signed", "You have already signed this plan. The other signature has to come from someone else.")
        slot = slot_for(roles, {s["slot"] for s in plan["signatures"]})
        if slot is None:
            raise PlanError("no_slot", "Your role cannot sign the plan now. The sponsor signs first, then the head of data.")
        if hidden_count and slot != "sponsor":  # A-044: the head of data signs for the whole, so must be able to see every measure
            raise PlanError("not_visible", "Not everything is visible to you, so you cannot sign as the head of data.")
        label = {s["slot"]: s["label"] for s in c["countersign"]}[slot]
        note = f"covers {hidden_count} restricted measure{'s' if hidden_count != 1 else ''} decided by the people named on them" if hidden_count else None
        sigs = [*plan["signatures"], {"slot": slot, "label": label, "name": who, "account_id": acct, "at": now, "restricted_covered": hidden_count, "note": note}]
        done = {s["slot"] for s in sigs} == {s["slot"] for s in c["countersign"]}
        oid = plan.get("outcome_id") or secrets.token_hex(16)
        plan = {**plan, "signatures": sigs, "outcome_id": oid, "signed_at": now if done else None, "updated_at": now}
        if done:  # the record is written before the plan says "signed", so a signed plan always has one
            write_outcome(d, oid, plan, risks, inputs, facts)
        save_plan(d, plan)
        return plan


def _open_words(waiting: list[dict]) -> str:
    n = len([r for r in waiting if r["state"] == "open"])
    back = len(waiting) - n
    bits = ([f"{n} risk{'s' if n != 1 else ''} still need{'' if n != 1 else 's'} a decision"] if n else []) + (
        [f"{back} sent back risk{'s are' if back != 1 else ' is'} still being re-checked by Lens"] if back else [])
    return "The plan cannot be signed yet: " + " and ".join(bits) + "."


# ---- the outcome record module 4 reads --------------------------------------------------------------------------------------------------------
def outcomes_dir(d: Path) -> Path:
    return Path(d).parents[1] / "outcomes"  # intents/m3_connect/outcomes, beside assessments/


def build_outcome(oid: str, plan: dict, risks: list[dict], inputs: dict, facts: dict) -> dict:
    """The record for a signed plan. A restricted measure carries only its id and group: no name, reason, source, team or risk wording."""
    c = contract()
    hide = set(facts["restricted"]) | {m for it in plan["items"] if it.get("restricted") for m in it["measures"]}  # also those behind a restricted source
    names = facts["names"]
    name = lambda m: P.RESTRICTED_NAME if m in hide else names.get(m, m)  # noqa: E731
    bands = {b: [] for b in c["bands"]}
    for it in plan["items"]:
        r = bool(it.get("restricted")) or bool(set(it["measures"]) & hide)
        keep = ("key", "measures", "pain_points", "effort", "date") if r else ("key", "measures", "pain_points", "effort", "team", "blocked_by",
                                                                              "who_unblocks", "date", "why_descoped", "covered_by", "summary")
        bands[it["band"]].append({**{k: it.get(k) for k in keep}, "restricted": r, **({"summary": P.RESTRICTED_NAME} if r else {}),
                                  "edits": {} if r else {f: {k: e[k] for k in ("reason", "by", "at")} for f, e in it["edits"].items()}})
    groups = {g: sum(1 for f in inputs["findings"] if f["group"] == g) for g in ("ready", "unclear", "unknown")}
    return {"outcome_id": oid, "module": c["outcome"]["module"], "kind": c["outcome"]["kind"], "assessment_id": plan["assessment_id"],
            "baseline_outcome_id": facts.get("baseline_outcome_id"), "charter_outcome_id": facts.get("charter_outcome_id"), "signed_at": plan["signed_at"],
            "bands": c["bands"], "plan": bands, "measure_names": {m: name(m) for m in {f["measure_id"] for f in inputs["findings"]}},
            "left_out": [{"measure_id": x["measure_id"], "name": P.RESTRICTED_NAME if x["measure_id"] in hide or x.get("restricted") else x.get("name"),
                          "reason": None if x["measure_id"] in hide or x.get("restricted") else x.get("reason")} for x in inputs.get("left_out") or []],
            "findings_summary": {"counts": groups, "measures": [
                {"measure_id": f["measure_id"], "group": f["group"], "reasons": [] if f["measure_id"] in hide else f["reasons"]} for f in inputs["findings"]]},
            "accepted_risks": [{"id": r["id"], "kind": r["kind"], "measures": r["measures"], "pain_points": r["pain_points"], "state": r["state"],
                                "text": P.RESTRICTED_NAME if set(r["measures"]) & hide else r["text"],
                                "decision": {k: (r["decision"] or {}).get(k) for k in (("decision", "at") if set(r["measures"]) & hide
                                                                                         else ("decision", "note", "reason", "by", "at"))}} for r in risks],
            "signatures": [{k: s.get(k) for k in ("slot", "label", "name", "at", "restricted_covered", "note")} for s in plan["signatures"]]}


def write_outcome(d: Path, oid: str, plan: dict, risks: list[dict], inputs: dict, facts: dict) -> None:
    """Written once: an existing record of this id is left as it is (a retry after a failed save never writes a second)."""
    path = outcomes_dir(d) / f"{oid}.json"
    if _read(path) is None:
        _write(path, build_outcome(oid, plan, risks, inputs, facts))


# ---- Nira: the one sentence -------------------------------------------------------------------------------------------------------------------
def next_sentence(plan: dict | None, risks: list[dict]) -> str:
    """The first thing waiting on the plan step, and on whom, in plain words. The sponsor decides the risks; the people who may see a restricted
    measure decide the risks about it (D9)."""
    if plan and plan["signed_at"]:
        return SIGNED_SENTENCE
    open_s = len([r for r in risks if r["state"] == "open" and not r.get("restricted")])
    open_r = len([r for r in risks if r["state"] == "open" and r.get("restricted")])
    mine = f"{open_s} risk{'s need' if open_s != 1 else ' needs'} a decision from the sponsor"
    theirs = f"{open_r} risk{'s' if open_r != 1 else ''} about {'measures' if open_r != 1 else 'a measure'} only some people can see"
    if open_s and open_r:
        return f"{mine}, and {theirs} from those people."
    if open_s:
        return mine + "."
    if open_r:
        return f"{theirs} {'need' if open_r != 1 else 'needs'} a decision from the people who can see {'them' if open_r != 1 else 'it'}."
    back = len([r for r in risks if r["state"] == "sent_back"])
    if back:
        return f"Lens is re-checking {back} risk{'s' if back != 1 else ''} you sent back."
    if (plan or {}).get("signatures"):
        return "Waiting for the head of data to sign."
    return "The plan is ready to sign. The sponsor signs next."


def step_state(d: Path) -> dict:
    """The plan step for the steps registry (domain/steps.py)."""
    try:
        inputs, plan = P.inputs_for_plan(d), read_plan(d)
        if plan and plan["signed_at"]:
            return {"state": "done"}
        if not inputs["ready"]:
            return {"state": "not_started"}
        return {"state": "in_progress", "waiting_on": next_sentence(plan, with_decisions(inputs["risks"], read_decisions(d)))}
    except PlanError:
        return {"state": "not_started"}
