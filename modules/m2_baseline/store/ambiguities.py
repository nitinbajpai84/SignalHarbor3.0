"""M2-E1: the open questions (ambiguities) of a baseline. Stored on each measure (kpis.json `ambiguities`, by domain/ambiguities.py); the
governance ones are worked out from the catalogue (store/governance.py `ambiguities`) and listed beside them, read-only here.

One list for one person: `listing` is the only way out of this file and it never returns an item that names, or links to, a measure, source,
table or field that person may not see (a restricted measure is skipped whole). The same rule as the technical definition and the governance view.
"""
from typing import Callable

from modules.m2_baseline.domain import ambiguities as A
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import technical as T
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.store import governance as G
from modules.m2_baseline.store import kpis as K
from modules.m2_baseline.store import technical as ST

NO_ITEM = "We could not find that question."
DERIVED = "This is decided in the governance view, where the missing decision is made."


def _owner(k: dict, kind: str, role: str | None = None) -> str:
    o = (k.get("owners") or {}).get(role or A.role_of(kind)) or {}
    return str(o.get("value") or "") if o.get("mark") != "unknown" else ""


def add(plane, baseline_id: str, kpi_id: str, items: list[dict]) -> int:
    """Add what Lens found to the measure; one already there (even settled) is not added again. How many were new."""
    before = len(next(k for k in K.read_kpis(plane, baseline_id) if k["id"] == kpi_id).get("ambiguities") or [])
    after = K.change(plane, baseline_id, kpi_id, lambda k: A.with_ambiguities(k, items))
    return len(after.get("ambiguities") or []) - before


def listing(plane, baseline_id: str, viewer: C.Viewer, sees: Callable[[dict], bool]) -> list[dict]:
    """Every question this person may see: [{kpi_id, kpi_name, owner, derived, ...the ambiguity}], the measures' order, derived (governance) last
    of each measure. `owner` is the person it would go to."""
    shown, _ = ST.catalogue_for(plane, baseline_id, viewer)
    names = set(T.row_names(shown))
    hidden = ST.hidden_terms(plane, baseline_id, viewer, sees)
    kpis = K.read_kpis(plane, baseline_id)
    derived = G.ambiguities(plane, baseline_id, viewer)
    out: list[dict] = []
    for k in kpis:
        if not sees(k):
            continue
        for a in k.get("ambiguities") or []:
            if any(r.get("id") not in names for r in a.get("refs") or []) or A.mentions(a, hidden):
                continue
            out.append({**a, "kpi_id": k["id"], "kpi_name": k["name"], "owner": _owner(k, a["kind"], a.get("role")), "derived": False,
                        "suggested_part": A.ANSWER_PART.get(a["kind"], "")})  # the part the screen preselects; a person may choose another or none
        out += [{**a, "kpi_id": k["id"], "kpi_name": k["name"], "owner": "", "derived": True} for a in derived.get(k["id"], [])]
    out += [{**a, "kpi_id": "", "kpi_name": "", "owner": "", "derived": True} for a in derived.get("", [])]
    return out


ALL_SEEING = C.Viewer("", frozenset({"company_admin"}))


def derived_open_all(plane, baseline_id: str) -> dict[str, int]:
    """{measure id: open governance questions} over EVERY row, as the organiser sees them: the number the ready-to-build gate uses, the same for
    everyone. Counts only; nothing here is shown to a person."""
    return {kid: len(items) for kid, items in G.ambiguities(plane, baseline_id, ALL_SEEING).items() if kid}


def counts(items: list[dict]) -> dict:
    return {"all": len(items), **{s: sum(1 for a in items if a["status"] == s) for s in A.STATUSES}}


def open_by_kpi(plane, baseline_id: str, viewer: C.Viewer, sees) -> dict[str, int]:
    out: dict[str, int] = {}
    for a in listing(plane, baseline_id, viewer, sees):
        if a["status"] == "open" and a["kpi_id"]:
            out[a["kpi_id"]] = out.get(a["kpi_id"], 0) + 1
    return out


def _find(plane, baseline_id: str, kpi_id: str, amb_id: str, viewer, sees) -> dict:
    item = next((a for a in listing(plane, baseline_id, viewer, sees) if a["id"] == amb_id and a["kpi_id"] == kpi_id), None)
    if item is None:
        raise LookupError(NO_ITEM)  # an item the person may not see answers like one that does not exist
    if item["derived"]:
        raise A.Refused(DERIVED)
    if item["status"] != "open":
        raise A.Refused("This question has already been dealt with.")
    return item


def answer(plane, baseline_id: str, kpi_id: str, amb_id: str, resolution: str, by: str, viewer: C.Viewer, sees, part: str | None = None, wording: str | None = None) -> dict:
    """A person answers: the answer is recorded on the question, which is settled. It changes nothing else unless the person chose a part
    ("Which part does this answer change?"): then `wording` is their own new text for that part, stated by them, and what it said before stays in
    the part's history. A part is never replaced by the bare answer. Returns {kpi, part}."""
    _find(plane, baseline_id, kpi_id, amb_id, viewer, sees)
    text = A._words(resolution, "your answer")
    part = None if part in (None, "", "none") else part  # a name that is not a part is refused by with_wording, never ignored

    def go(k):
        if part:
            k = A.reopen_for_part(k, part, f"the {T.LABELS.get(part, part).lower()} was changed by {by} after this was settled")
        k = A.settle(k, amb_id, text, by)
        if part:
            k = A._replace(T.with_wording(k, part, wording, text, by), amb_id, lambda a: {**a, "part": part})
        return k
    return {"kpi": K.change(plane, baseline_id, kpi_id, go), "part": part}


def accept(plane, baseline_id: str, kpi_id: str, amb_id: str, reason: str, by: str, viewer: C.Viewer, sees) -> dict:
    """"Accept as a known risk": the caller has checked the person is the organiser or sponsor; a reason is required."""
    _find(plane, baseline_id, kpi_id, amb_id, viewer, sees)
    return K.change(plane, baseline_id, kpi_id, lambda k: A.accept(k, amb_id, reason, by))


def owner_view(plane, baseline_id: str, name: str, account_id: str | None = None) -> tuple[C.Viewer, Callable[[dict], bool]]:
    """An owner as the catalogue and the work list see them: by their name (and account id when they have one). They are an owner, nothing more."""
    return C.Viewer(name, frozenset({"owner"}), False, account_id), (lambda k: W.may_see(k, name, account_id, False))


GENERIC = "A question about {name} needs your answer."


def for_owner(plane, baseline_id: str, kpi: dict, item: dict, name: str, account_id: str | None = None) -> str | None:
    """The question as the OWNER may read it: None when they may not see the measure at all (a restricted measure's question is never sent to
    someone not on its list); the generic wording when the question would name a row or measure hidden from them; else the question itself."""
    viewer, sees = owner_view(plane, baseline_id, name, account_id)
    if not sees(kpi):
        return None
    shown, _ = ST.catalogue_for(plane, baseline_id, viewer)
    names = set(T.row_names(shown))
    hidden = ST.hidden_terms(plane, baseline_id, viewer, sees)
    if any(r.get("id") not in names for r in item.get("refs") or []) or A.mentions(item, hidden):
        return GENERIC.format(name=kpi["name"])
    return item["question"]


def prepare_ask(plane, baseline_id: str, kpi_id: str, amb_id: str, viewer: C.Viewer, sees, role: str | None = None) -> tuple[dict, str, str]:
    """(the item, the owner's name, the plain question) for "Ask the owner". Raises Refused when nobody is named for that role."""
    item = _find(plane, baseline_id, kpi_id, amb_id, viewer, sees)
    k = next(k for k in K.read_kpis(plane, baseline_id) if k["id"] == kpi_id)
    role = role if role in ("business", "data", "process") else A.role_of(item["kind"])
    owner = _owner(k, item["kind"], role)
    if not owner:
        raise A.Refused(f"Nobody is named as the {role} owner of this measure yet, so there is no one to ask. Name them on the work list first.")
    o = (k.get("owners") or {}).get(role) or {}
    text = for_owner(plane, baseline_id, k, next(a for a in k["ambiguities"] if a["id"] == amb_id), owner, o.get("account_id"))
    if text is None:
        raise A.Refused("That owner may not see this measure, so the question cannot be sent to them.")
    return item, owner, text


def answer_as_owner(plane, baseline_id: str, kpi_id: str, amb_id: str, resolution: str, owner: str) -> dict:
    """The owner's reply from their answer page: the same settle path, stated by them, as a person who may see only what they may see."""
    k = next((k for k in K.read_kpis(plane, baseline_id) if k["id"] == kpi_id), None)
    if k is None:
        raise LookupError(NO_ITEM)
    account = next((o.get("account_id") for o in (k.get("owners") or {}).values() if o.get("value") == owner and o.get("account_id")), None)
    viewer, sees = owner_view(plane, baseline_id, owner, account)
    return answer(plane, baseline_id, kpi_id, amb_id, resolution, owner, viewer, sees)


def mark_asked(plane, baseline_id: str, kpi_id: str, amb_id: str, owner: str, request_id: str) -> dict:
    return K.change(plane, baseline_id, kpi_id, lambda k: A._replace(k, amb_id, lambda a: {**a, "asked": {"owner": owner, "at": A.now(), "request_id": request_id}}))
