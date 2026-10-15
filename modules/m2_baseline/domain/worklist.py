"""The KPI work list (M2-01, M2-03, M2-04, M2-05): what a KPI record is, what state it is in, who may see it.
Pure functions over the shapes of contracts/SHARED.md (plus the additive fields listed in contracts/worklist.yaml)."""
import secrets
from functools import lru_cache

from modules.m2_baseline.domain.provenance import MARKS, prov, unknown
from modules.m2_baseline.domain.questionnaire import load_questionnaire, source_rows
from modules.m2_baseline.domain.triage import ROLES

PERSONAL = ("yes", "no", "not_sure")
STATES = ("not_started", "drafted", "questions_open", "signed")
MAX_NAME, MAX_TEXT, MAX_PEOPLE = 120, 2000, 50
RESTRICTED_NAME = "A restricted measure"  # all anyone not named for a measure may learn of it: not its name, not its definition
RESTRICTED_REFUSAL = "This measure is restricted to its named people."


class Invalid(ValueError):
    """A plain-words refusal of what was sent; the message is shown to the person."""


def text_of(value, what: str, limit: int) -> str:
    t = " ".join(str(value).split()) if isinstance(value, str) else ""
    if not t:
        raise Invalid(f"Please give {what}.")
    if len(t) > limit:
        raise Invalid(f"That is too long for {what}. Please shorten it.")
    return t


def new_id() -> str:
    return "kpi-" + secrets.token_hex(4)


def new_kpi(kid: str, name: str, problem_ids: list, priority, definition: dict | None = None,
            questions: list[str] | None = None) -> dict:
    """A KPI a person confirmed. Everything but the name starts as unknown, except what the pack drafted (a guess)."""
    return {"id": kid, "name": name, "problem_ids": list(problem_ids), "priority": priority,
            "definition": definition or unknown("Lens"),
            "owners": {r: unknown("Lens") for r in ROLES},
            "governance": {"personal": "not_sure", "sensitive": False, "may_see": []},
            "tracking": unknown("Lens"), "producer": unknown("Lens"), "gathered": unknown("Lens"),
            "questions": [{"id": secrets.token_hex(4), "question": q, "answer": unknown("Lens")} for q in questions or []],
            "definition_proposal": None}


def state_of(kpi: dict, baseline_state: str) -> str:
    """not started, drafted, questions open or signed (M2-01). A signed baseline signs every KPI in it."""
    if baseline_state == "signed":
        return "signed"
    if any(q["answer"]["mark"] == "unknown" for q in kpi["questions"]):
        return "questions_open"
    return "drafted" if kpi["definition"]["mark"] != "unknown" else "not_started"


@lru_cache(maxsize=1)
def _source_labels() -> dict:
    """The plain words of the questionnaire's source-row choices, read once."""
    return {r["key"]: {c["value"]: c["label"] for c in r.get("choices", [])} for r in load_questionnaire().fields["sources"]["row"]}


def _said(cell) -> str:
    return str(cell.get("value") or "").strip() if isinstance(cell, dict) and cell.get("mark") == "stated" else ""


def with_answers(kpi: dict, answers: list[dict]) -> dict:
    """R4 defect 4: "who produces the data" and "how it is gathered" still unknown on the work list are read from what the
    owners answered (the systems they named, how each arrives and how often): the same rows the catalogue is built from.
    Only what an owner stated; a value a person typed on the work list is never replaced."""
    rows = [(a, r) for a in answers for r in source_rows(a)]
    labels = _source_labels()

    def fill(field: str, texts) -> dict:
        cur = kpi.get(field) if isinstance(kpi.get(field), dict) else {"value": None, "mark": "unknown"}
        got = list(dict.fromkeys(t for t in texts if t))
        if cur["mark"] != "unknown" or not got:
            return {field: cur}
        by = ", ".join(dict.fromkeys(str(a.get("owner_name") or "") for a, r in rows if a.get("owner_name")))
        return {field: prov("; ".join(got), "stated", by, "the owners' answers")}
    way = lambda r: ", ".join(x for x in (labels["connection"].get(_said(r.get("connection")), ""), labels["frequency"].get(_said(r.get("frequency")), "")) if x)  # noqa: E731
    return {**kpi, **fill("producer", (_said(r["name"]) for _, r in rows)), **fill("gathered", (way(r) for _, r in rows))}


def person_value(body, name: str, by: str, source: str = "") -> dict:
    """A value a person gave: {"text", "mark"}. The mark is theirs to choose (stated or guessed); unknown clears it."""
    mark = body.get("mark") if isinstance(body, dict) else None
    if mark not in MARKS:
        raise Invalid("Please say whether this is stated, guessed or unknown.")
    if mark == "unknown":
        return unknown(by, source)
    return prov(text_of(body.get("text"), name, MAX_TEXT), mark, by, source)


def nominee(body, by: str, account_id: str | None = None) -> dict:
    """One owner nomination: {"name", "has_account"}; an empty name takes the nomination away. Records who nominated."""
    if not isinstance(body, dict):
        raise Invalid("Please give a name.")
    if not str(body.get("name") or "").strip():
        return unknown(by, "nomination withdrawn")
    who = text_of(body["name"], "a name", MAX_NAME)
    p = prov(who, "stated", by, "nominated, with an account" if body.get("has_account") else "nominated, no account yet")
    return {**p, "account_id": account_id}  # the nominee's account (null without one): who may decline or confirm their part


def declined(owner: dict) -> dict:
    """The nominated person says no: the question goes back to the organiser, and the earlier answer stays on record."""
    if owner["mark"] == "unknown":
        raise Invalid("Nobody is nominated for this role.")
    return unknown(owner["value"], f"declined by {owner['value']}")


def governance(current: dict, body, account_ids=lambda name: []) -> dict:
    """personal (yes, no, not sure), sensitive, and the names who may see it. Not sure is kept as given and treated as
    personal. `account_ids(name)` gives the accounts a name belongs to now; they are kept beside the name
    (may_see_accounts, only for names that have one) so a later rename cannot let someone else in."""
    if not isinstance(body, dict):
        raise Invalid("Those details could not be read.")
    g = dict(current)
    if "personal" in body:
        if body["personal"] not in PERSONAL:
            raise Invalid("Please answer yes, no or not sure.")
        g["personal"] = body["personal"]
    if "sensitive" in body:
        if not isinstance(body["sensitive"], bool):
            raise Invalid("Please answer yes or no for sensitive to the business.")
        g["sensitive"] = body["sensitive"]
    if "may_see" in body:
        names = body["may_see"]
        if not isinstance(names, list) or len(names) > MAX_PEOPLE or not all(isinstance(n, str) for n in names):
            raise Invalid("Please give the names of the people who may see it.")
        g["may_see"] = list(dict.fromkeys(text_of(n, "a name", MAX_NAME) for n in names if n.strip()))
        bound = {n.casefold(): ids for n in g["may_see"] if (ids := account_ids(n))}
        g.pop("may_see_accounts", None)
        if bound:
            g["may_see_accounts"] = bound
    return g


def rank(gov: dict) -> int:
    """How closed a measure is: sensitive and personal each add one, "not sure" counts as personal but is below yes. Lower is less restricted."""
    return {"yes": 3, "not_sure": 2, "no": 0}[gov["personal"]] + bool(gov["sensitive"])


def treated_as_personal(gov: dict) -> bool:
    return gov["personal"] in ("yes", "not_sure")


def may_see(kpi: dict, viewer: str, account_id: str | None, organiser: bool) -> bool:
    """Server-side: a personal, not-sure or sensitive KPI is seen by the company admin and the people named in may_see,
    and by nobody else until people are named (slide 5); everyone else sees that it exists (slide 12). A name that
    belonged to an account when it was named is matched on that account's id; only a name with no account is matched
    on the display name."""
    g = kpi["governance"]
    if not (g["sensitive"] or treated_as_personal(g)) or organiser:
        return True
    bound = g.get("may_see_accounts", {})
    me = viewer.strip().casefold()
    return any(account_id in bound[k] if k in bound else k == me for k in (n.casefold() for n in g["may_see"]))


def visible_ids(kpis: list[dict], viewer: str, account_id: str | None, organiser: bool) -> set[str]:
    """The ids of the KPIs this viewer may see, by the one rule above (may_see). Every route that lists answers, steps or
    requests keeps only these: a KPI not in the set is dropped entirely, counts included."""
    return {k["id"] for k in kpis if may_see(k, viewer, account_id, organiser)}


def hidden(kpi: dict, baseline_state: str = "") -> dict:
    """What a person not named sees of a restricted KPI: that it exists, and nothing of what is in it."""
    return {"id": kpi["id"], "name": RESTRICTED_NAME, "restricted": True, "state": "not_started"}  # the same for every stub: a state would show whether the measure has a definition
