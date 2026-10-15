"""Owner confirmations, sponsor acceptance, countersign and the lock on signed work (M2-23, M2-25, M2-27).

Ported from the earlier product's emitters/baseline.py: get_signoff, sign_part, _signer_slot_for, sign_baseline,
_blocking_reason, locked_reason, _refuse_if_locked, BaselineLocked, _human_touched, _step_touched. Pure Python, no storage:
every function takes a version (see store/signoff.py) and returns a new one. Rules and wording: contracts/signoff.yaml.

Each owner confirms only their own part of a KPI (business owner the definition, data owner the source, process owner the
process). The sponsor and the head of data then sign the whole, as two different people. Signed content is read-only: a
change needs a new version and a new sign-off.
"""
import re
import unicodedata
from datetime import date

from modules.m2_baseline.domain.readiness import answered, best, choice_fields, conflict_options, owner_account, owner_of, tracked_today

_BAD = ("Cc", "Cf", "Cs", "Zl", "Zp")
DOC_NAMES = {"business_glossary": "business glossary", "data_catalogue": "data catalogue"}
LOCKED = "This baseline is signed. A change needs a new version and a new sign-off."


class SignoffError(Exception):
    """A plain-words refusal. `code` picks the status the route answers with."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class BaselineLocked(SignoffError):
    """A change or a re-draft was refused: the content is already signed or confirmed (M2-27)."""

    def __init__(self, message: str = LOCKED):
        super().__init__("locked", message)


def _norm(name) -> str:
    return " ".join(str(name).split()).casefold()


def clean_text(v, limit: int, what: str) -> str:
    if not isinstance(v, str) or any(unicodedata.category(c) in _BAD for c in v.replace("\n", " ")):
        raise SignoffError("invalid", f"Please check the {what}.")
    v = " ".join(v.split())
    if len(v) > limit:
        raise SignoffError("invalid", f"The {what} is too long: keep it under {limit} characters.")
    return v


# ---- the lock (old: locked_reason, _refuse_if_locked) ---------------------------------------------------------------
def _signers(version: dict, c: dict) -> str:
    label = {s["slot"]: s["label"] for s in c["countersign"]}
    return ", ".join(f"{s['name']} ({label.get(s['slot'], s['slot'])})" for s in version["countersign"])


def locked_reason(version: dict, c: dict, kpi_id: str | None = None, part: str | None = None, names: dict | None = None) -> str | None:
    """Plain words naming who signed the baseline or confirmed the part; None when a re-draft may run. A signature on the
    whole baseline locks every part. `kpi_id` / `part` narrow the question; None means any."""
    if version["countersign"] or version["status"] == "signed":
        return "the baseline is already signed by " + _signers(version, c)
    labels = {p["id"]: p["label"].lower() for p in c["parts"]}
    said = [f"the {labels.get(pid, pid)} of {(names or {}).get(kid, kid)} was confirmed by {got['by']}"
            for kid, got_parts in version["parts"].items() if kpi_id in (None, kid)
            for pid, got in got_parts.items() if part in (None, pid)]
    return "; ".join(said) or None


def refuse_if_locked(version: dict, c: dict, kpi_id=None, part=None, names=None) -> None:
    reason = locked_reason(version, c, kpi_id, part, names)
    if reason:
        raise BaselineLocked(f"{reason[:1].upper()}{reason[1:]} -- it cannot be re-drafted.")


def check_open(version: dict) -> None:
    if version["status"] == "signed" or version["countersign"]:
        raise BaselineLocked()


def human_touched(value) -> bool:
    """A value a person gave or changed: stated by a name that is not an agent or the pack. Re-drafts keep these.
    (Old: _human_touched.)"""
    return isinstance(value, dict) and value.get("mark") == "stated" and value.get("by") not in (None, "", "Lens")


def step_touched(step: dict) -> bool:
    """A person validated, edited or removed this process step. (Old: _step_touched, over this repo's step states.)"""
    return step.get("state") in ("validated", "edited", "removed")


# ---- confirmations (old: sign_part, _blocking_reason) ---------------------------------------------------------------
def _part(c: dict, part_id) -> dict:
    p = next((p for p in c["parts"] if p["id"] == part_id), None)
    if p is None:
        raise SignoffError("invalid", "That part of the baseline is not one that can be confirmed.")
    return p


def _kpi(kpis: list[dict], kpi_id) -> dict:
    k = next((k for k in kpis if isinstance(k, dict) and k.get("id") == kpi_id), None)
    if k is None:
        raise LookupError("no kpi")
    return k


def _same_name(people: list[dict], name) -> list[dict]:
    return [p for p in people if _norm(p["display_name"]) == _norm(name)]


def _is_owner(owner: str, owner_acct: str | None, acct_id: str, people: list[dict]) -> bool:
    """Identity is the account id. A name-only nomination matches only when exactly one account in the company has that name."""
    if owner_acct:
        return owner_acct == acct_id
    same = _same_name(people, owner)
    if len(same) > 1:
        raise SignoffError("ambiguous_name", f"More than one person in your company is called {owner}, so we cannot tell who the "
                           "owner is. Please ask your administrator.")
    return len(same) == 1 and same[0]["account_id"] == acct_id


NOT_ANSWERED = "Answer the questions for this part first."


def confirm(version: dict, c: dict, kpis: list[dict], kpi_id: str, part_id: str, who: str, acct_id: str, people: list[dict], now: str,
            answers: list[dict] = ()) -> dict:
    check_open(version)
    part, kpi = _part(c, part_id), _kpi(kpis, kpi_id)
    status, owner = owner_of(kpi, version["named"], part["owner"])
    if status != "named":  # old _blocking_reason: no owner blocks this KPI's sign-off until the sponsor names one
        raise SignoffError("no_owner", f"This part has no {part['owner_label']} yet, so it cannot be confirmed. The sponsor can name one.")
    if not _is_owner(owner, owner_account(kpi, version["named"], part["owner"]), acct_id, people):
        raise SignoffError("not_your_part", f"Only {owner}, the {part['owner_label']}, can confirm this part.")
    if not answered(answers, kpi_id, owner):  # N-D: a silent owner cannot confirm; a meeting answer in their name counts
        raise SignoffError("not_answered", NOT_ANSWERED)
    if (version["parts"].get(kpi_id) or {}).get(part_id):
        raise SignoffError("already_confirmed", "You have already confirmed this part.")
    return {**version, "parts": {**version["parts"], kpi_id: {**(version["parts"].get(kpi_id) or {}), part_id: {"by": who, "account_id": acct_id, "at": now}}}}


def name_owner(version: dict, c: dict, kpis: list[dict], kpi_id: str, part_id: str, name, who: str, role_ok: bool, now: str,
               people: list[dict] = ()) -> dict:
    """The sponsor names someone for a part that has no owner (slide 13). A name that is exactly one account in the company
    is stored with that account id; any other stays name-only."""
    check_open(version)
    if not role_ok:
        raise SignoffError("not_sponsor", "Only a sponsor can name an owner.")
    part, kpi = _part(c, part_id), _kpi(kpis, kpi_id)
    if owner_of(kpi, version["named"], part["owner"])[0] == "named":
        raise SignoffError("has_owner", f"This part already has a {part['owner_label']}.")
    name = clean_text(name, c["name_max_chars"], "name")
    if not name:
        raise SignoffError("invalid", "Please give the person's name.")
    row = {"name": name, "by": who, "at": now}
    same = _same_name(list(people), name)
    if len(same) == 1:
        row["account_id"] = same[0]["account_id"]
    return {**version, "named": {**version["named"], kpi_id: {**(version["named"].get(kpi_id) or {}), part["owner"]: row}}}


# ---- unknowns, next steps and acceptance (M2-23) --------------------------------------------------------------------
def _not_tracked(kpis, kpi_id) -> dict:
    kpi = _kpi(kpis, kpi_id)
    if tracked_today(kpi):
        raise SignoffError("tracked_today", "This measure is tracked today, so it needs no next step.")
    return kpi


def set_review(version: dict, c: dict, kpis: list[dict], kpi_id: str, fields: dict, who: str, now: str) -> dict:
    """Tentative date (optional), next step and project for a KPI not tracked today. A changed plan withdraws an
    acceptance that was given for the earlier one."""
    check_open(version)
    _not_tracked(kpis, kpi_id)
    old = version["review"].get(kpi_id) or {}
    row = {k: old.get(k) for k in ("tentative_date", "next_step", "project", "accepted")}
    if "tentative_date" in fields:
        d = fields["tentative_date"]
        try:
            row["tentative_date"] = date.fromisoformat(d).isoformat() if d not in (None, "") else None
        except (TypeError, ValueError):
            raise SignoffError("invalid", "Please give the date as year-month-day, or leave it empty.") from None
    if "next_step" in fields:
        row["next_step"] = clean_text(fields["next_step"] or "", c["next_step_max_chars"], "next step") or None
    if "project" in fields:
        row["project"] = clean_text(fields["project"] or "", c["project_max_chars"], "project") or None
    changed = {k: row[k] for k in ("tentative_date", "next_step", "project")} != {k: old.get(k) for k in ("tentative_date", "next_step", "project")}
    withdrawn = bool(changed and row["accepted"])
    if withdrawn:
        row["accepted"] = None
    said = dict(old.get("set") or {})  # who set each field and when, so one editor is never named for another's field
    said.update({k: {"by": who, "at": now} for k in ("tentative_date", "next_step", "project") if row[k] != old.get(k)})
    return {**version, "review": {**version["review"], kpi_id: {**row, "set": said, "updated_by": who, "updated_at": now}}}, withdrawn


def accept(version: dict, kpis: list[dict], kpi_id: str, who: str, role_ok: bool, now: str) -> dict:
    """The sponsor accepts a KPI as "unknown for now". Records who and when."""
    check_open(version)
    if not role_ok:
        raise SignoffError("not_sponsor", "Only a sponsor can accept a measure as unknown for now.")
    _not_tracked(kpis, kpi_id)
    old = version["review"].get(kpi_id) or {}
    if old.get("accepted"):
        raise SignoffError("already_accepted", "This measure is already accepted as unknown for now.")
    if not (old.get("next_step") or old.get("tentative_date")):
        raise SignoffError("needs_plan", "Please give a next step or a tentative date before accepting this measure as unknown for now.")
    return {**version, "review": {**version["review"], kpi_id: {**old, "accepted": {"by": who, "at": now}}}}


# ---- a real conflict between choices (M2-24) ------------------------------------------------------------------------
def settle(version: dict, c: dict, answers: list[dict], kpi_id: str, field, value, who: str, role_ok: bool, now: str) -> tuple[dict, dict]:
    """The sponsor or company admin picks one of the stated choices. Both answers stay in the answers file; the pick is
    kept here with who and when. Returns (version, audit detail)."""
    check_open(version)
    if not role_ok:
        raise SignoffError("not_sponsor", "Only a sponsor or the company admin can settle a conflict.")
    if field not in {f["id"] for f in c["readiness"]["sensing_fields"]} or field not in choice_fields():
        raise SignoffError("invalid", "Only a choice answer can be settled.")
    mine = [a[field] for a in answers if a.get("kpi_id") == kpi_id and field in a]
    if best(mine, True, ((version.get("settled") or {}).get(kpi_id) or {}).get(field))[0] != "conflict":
        raise SignoffError("no_conflict", "Nobody disagrees on this answer, so there is nothing to settle.")
    options = conflict_options(mine)
    if not any(o["value"] == value for o in options):
        raise SignoffError("invalid", "Please pick one of the answers people gave.")
    row = {"value": value, "by": who, "at": now, "options": options}
    nv = {**version, "settled": {**(version.get("settled") or {}), kpi_id: {**((version.get("settled") or {}).get(kpi_id) or {}), field: row}}}
    label = next(f["label"] for f in c["readiness"]["sensing_fields"] if f["id"] == field).lower()
    return nv, {"detail": f"settled {label}", "choice": value}  # the choice id only (a validated option value), never answer text


def confirm_by_link(version: dict, c: dict, kpis: list[dict], kpi_id: str, part_id: str, name: str, now: str, answers: list[dict] = ()) -> dict:
    """A nominee with no account confirms their own part through their answer link (the link was checked by the caller)."""
    check_open(version)
    part, kpi = _part(c, part_id), _kpi(kpis, kpi_id)
    status, owner = owner_of(kpi, version["named"], part["owner"])
    if status != "named" or _norm(owner) != _norm(name) or owner_account(kpi, version["named"], part["owner"]):
        raise SignoffError("not_your_part", "That part is not yours to confirm from this link. An owner with an account confirms signed in.")
    if not answered(answers, kpi_id, owner):
        raise SignoffError("not_answered", NOT_ANSWERED)
    if (version["parts"].get(kpi_id) or {}).get(part_id):
        raise SignoffError("already_confirmed", "You have already confirmed this part.")
    got = {"by": owner, "account_id": None, "at": now, "via": "answer link"}
    return {**version, "parts": {**version["parts"], kpi_id: {**(version["parts"].get(kpi_id) or {}), part_id: got}}}


# ---- countersign (old: _signer_slot_for, sign_baseline) -------------------------------------------------------------
def slot_for(c: dict, roles: set[str], filled: set[str]) -> str | None:
    """Only the next place in order is open: the sponsor signs first, then the head of data."""
    nxt = next((s for s in c["countersign"] if s["slot"] not in filled), None)
    return nxt["slot"] if nxt and roles & set(nxt["roles"]) else None


# ---- leaving a measure out of the baseline (M2-E4) ------------------------------------------------------------------------------------
def leave_out(version: dict, c: dict, kpis: list[dict], kpi_id: str, reason, who: str, roles: set[str], now: str) -> dict:
    """The organiser or a sponsor leaves a measure out of this baseline, with a reason. It goes to the hand-off as left out."""
    check_open(version)
    if not roles & set(c["leave_out_roles"]):
        raise SignoffError("not_sponsor", "Only the organiser or a sponsor can leave a measure out of this baseline.")
    _kpi(kpis, kpi_id)
    text = clean_text(reason if reason is not None else "", c["leave_out_reason_max_chars"], "reason")
    if not text:
        raise SignoffError("invalid", "Please say why this measure is left out.")
    return {**version, "left_out": {**(version.get("left_out") or {}), kpi_id: {"reason": text, "by": who, "at": now}}}


def bring_back(version: dict, c: dict, kpi_id: str, roles: set[str]) -> dict:
    check_open(version)
    if not roles & set(c["leave_out_roles"]):
        raise SignoffError("not_sponsor", "Only the organiser or a sponsor can bring a measure back into this baseline.")
    if kpi_id not in (version.get("left_out") or {}):
        raise SignoffError("not_left_out", "This measure is not left out.")
    return {**version, "left_out": {k: v for k, v in version["left_out"].items() if k != kpi_id}}


def countersign(version: dict, c: dict, view: dict, who: str, acct_id: str, roles: set[str], now: str, restricted: int, gate: dict,
                documents: dict) -> dict:
    """The sponsor, then the head of data, each once, as different people; only when every KPI is ready (M2-25, M2-26)."""
    if version["status"] == "signed":  # one signature locks edits (check_open) but the second may still be given
        raise BaselineLocked()
    if not view["ready"]:
        open_n = sum(len(i["missing"]) for i in view["items"] if i["required"] and not i["met"])
        raise SignoffError("not_ready", "The baseline is not ready for module 3 yet: " + (
            f"{open_n} items are open, some in measures you cannot see." if restricted else "; ".join(
                f"{i['label']} ({len(i['missing'])} open)" for i in view["items"] if i["required"] and not i["met"]) + "."))
    if not view["can_countersign"]:
        raise SignoffError("not_confirmed", "Every owner has to confirm their part before the baseline is signed.")
    if not gate["ok"]:  # M2-E4: ready to build, the same for everyone (the sentence is the asker's own view of it)
        raise SignoffError("not_ready_to_build", gate["refusal"])
    if any(s.get("account_id") == acct_id for s in version["countersign"]):
        raise SignoffError("already_signed", "You have already signed this baseline. The other signature has to come from someone else.")
    slot = slot_for(c, roles, {s["slot"] for s in version["countersign"]})
    if slot is None:
        raise SignoffError("no_slot", "Your role cannot sign the baseline now. The sponsor signs first, then the head of data.")
    if restricted and slot != "sponsor":  # A-044: the head of data signs for the whole, so must be able to see every measure
        raise SignoffError("not_visible", "Not everything is visible to you, so you cannot sign as the head of data.")
    note = f"covers {restricted} restricted measure{'s' if restricted != 1 else ''} confirmed by their named owners" if restricted else None
    first = version.get("documents")  # recorded at the first signature and never overwritten; a later signature must see the same documents
    if first:
        changed = [n for n, d in documents.items() if first.get(n, {}).get("sha256") != d["sha256"]]
        if changed:
            raise SignoffError("changed_since_signing", "The " + " and ".join(DOC_NAMES.get(n, n) for n in changed) + " changed after the first signature, "
                               "so this signature would cover something the first signer did not see. Undo the change, or ask the first signer to check it again.")
    sigs = [*version["countersign"], {"slot": slot, "name": who, "account_id": acct_id, "at": now, "restricted_covered": restricted, "note": note}]
    done = {s["slot"] for s in sigs} == {s["slot"] for s in c["countersign"]}
    return {**version, "countersign": sigs, "status": "signed" if done else "open", "signed_at": now if done else None,
            "documents": first or documents}
