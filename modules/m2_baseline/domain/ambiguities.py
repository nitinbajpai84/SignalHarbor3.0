"""M2-E1: the one place that knows what an ambiguity is (shared contract, docs/specs/M2-ENHANCEMENTS-PLAN.md). Pure functions, no files.

{id, kind, text, question, where, raised_by, status, resolution, by, at}; status open / settled / accepted. Added, optional: `refs`
(catalogue rows it names: [{tab, id}], so a viewer who may not see one never sees the item), `restricted` (drawn from a restricted
document: cleared when the measure is relaxed), `suggestion` (Lens's proposed answer, a suggestion until a person decides), `role` (whose
owner it goes to), `asked` ({owner, at} once it was added to an owner's request), `part` (what an answer changed), `reason` (accepted).

Moved here from domain/glossary.py (`new_ambiguity`, `with_ambiguities`) and domain/governance_view.py (`ambiguity`): glossary, governance
and the technical definition all build and list ambiguities through this file. One finding is one item: a second of the same kind and
place is never added, even once settled.
"""
import re
import secrets
from datetime import datetime, timezone

MAX_BASIS = 8
KINDS = ("definition", "period", "currency", "owner", "source", "calculation", "threshold", "governance", "conflict", "other")
STATUSES = ("open", "settled", "accepted")
LENS = "Lens"
MAX_TEXT = 2000
# the part of the definition a person's answer changes, by kind (a kind not here only records the answer)
ANSWER_PART = {"definition": "definition", "period": "period", "currency": "currency_basis", "calculation": "calculation", "threshold": "filters",
               "source": "notes"}
# words a question never holds: the template's own placeholders (a model echoing its instructions), and a request for catalogue ids (a missing link
# between a technical part and catalogue rows is Lens's job, never a question to a business person)
_TEMPLATE = ("what is unclear", "the question to ask", "what is not stated", "your proposed answer or nothing", "kind", "where", "unknown", "none")
_ASKS_IDS = re.compile(r"(?i)\bcatalogue\s+(?:ids?|identifiers?|rows?|fields?)\b|\bwhich\s+catalogue\s+(?:field|row|table)s?\b|\b(?:field|table|row)\s+ids?\b")  # asking a person for catalogue ids or rows; "which source ID is the system of record?" is a business question
_PART_TAG = re.compile(r"\((\w+)\)")
GROUPED = frozenset({"period", "currency", "source", "definition"})  # one decision per measure however Lens words it
GROUPED_PARTS = frozenset({"period", "currency_basis", "grain", "sources"})  # a conflict about one of these parts is one finding


class Refused(ValueError):
    """A plain-words refusal, shown to the person."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(text) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def make(kind: str, text: str, question: str, where: str, at: str | None = None, *, id: str | None = None, raised_by: str = LENS, **extra) -> dict:
    """One open ambiguity in the shared contract's shape. `id` is given for a derived one (governance), else random."""
    if kind not in KINDS:
        kind = "other"
    return {"id": id or "amb-" + secrets.token_hex(4), "kind": kind, "text": str(text)[:MAX_TEXT], "question": str(question)[:MAX_TEXT], "where": str(where)[:300],
            "raised_by": raised_by, "status": "open", "resolution": None, "by": None, "at": at or now(), **{k: v for k, v in extra.items() if v}}


def asks_for_ids(item: dict) -> bool:
    return bool(_ASKS_IDS.search(f"{item.get('question') or ''} {item.get('text') or ''}"))


def usable(item: dict) -> bool:
    """A question is stored only with real words of its own: not blank, not the template's placeholder, not a request for catalogue ids."""
    return all(_norm(item.get(f)) and _norm(item.get(f)) not in _TEMPLATE for f in ("text", "question")) and not asks_for_ids(item)


def _tag(item: dict) -> str:
    m = _PART_TAG.search(str(item.get("where") or ""))
    return m.group(1) if m else ""


def same(a: dict, b: dict) -> bool:
    """The same finding: the same kind about the same place, or (for the kinds with one decision per measure) the same part."""
    if a.get("kind") != b.get("kind"):
        return False
    if _norm(a.get("where")) == _norm(b.get("where")):
        return True
    t = _tag(a)
    return bool(t) and t == _tag(b) and (a.get("kind") in GROUPED or (a.get("kind") == "conflict" and t in GROUPED_PARTS))


def fresh(have: list[dict], items: list[dict]) -> list[dict]:
    """The items not already in `have` (settled and accepted ones count), and no two alike among themselves."""
    out: list[dict] = []
    for a in items:
        if usable(a) and not any(same(h, a) for h in [*have, *out]):
            out.append(a)
    return out


NOT_A_QUESTION = "Closed: not a question for a person"
REPEAT = "Closed: the same question is already open"


def tidy(items: list[dict]) -> list[dict]:
    """Open items that are blank, a template echo or a request for ids are closed visibly (never deleted), and so is an open item that repeats an
    earlier open one."""
    out: list[dict] = []
    for a in items:
        why = NOT_A_QUESTION if not usable(a) else REPEAT if any(h.get("status") == "open" and same(h, a) for h in out) else ""
        out.append({**a, "status": "settled", "resolution": why, "by": LENS, "at": now(), "auto": True} if a.get("status") == "open" and why else a)
    return out


def with_ambiguities(kpi: dict, items: list[dict]) -> dict:
    """The measure with these ambiguities added to its `ambiguities` list; one already there (even settled) is never added twice."""
    was = list(kpi.get("ambiguities") or [])
    have = tidy(was)
    new = fresh(have, items)
    out = {**kpi, "ambiguities": have + new} if new or have != was else kpi
    for a in items:  # the same finding again, from a document it was not raised from: the facts behind a settled item changed
        old = next((h for h in have if same(h, a) and h.get("status") != "open"), None)
        extra = [d for d in a.get("basis") or [] if old is not None and old.get("basis") and d not in old["basis"]]
        if extra:
            out = reopen(out, old["id"], f"{', '.join(extra)} now says something about this")
    return out


def find(kpi: dict, amb_id: str) -> dict | None:
    return next((a for a in kpi.get("ambiguities") or [] if a.get("id") == amb_id), None)


def _replace(kpi: dict, amb_id: str, edit) -> dict:
    items = list(kpi.get("ambiguities") or [])
    i = next((n for n, a in enumerate(items) if a.get("id") == amb_id), None)
    if i is None:
        raise LookupError("no ambiguity")
    items[i] = edit(items[i])
    return {**kpi, "ambiguities": items}


def _words(text, what: str) -> str:
    t = " ".join(str(text or "").split())
    if not t:
        raise Refused(f"Please write {what}.")
    if len(t) > MAX_TEXT:
        raise Refused("That is too long. Please shorten it.")
    return t


def settle(kpi: dict, amb_id: str, resolution: str, by: str, part: str | None = None, at: str | None = None) -> dict:
    """A person's answer: the item is settled, with the words and who gave them. `part` records which part of the definition it changed."""
    text = _words(resolution, "your answer")
    return _replace(kpi, amb_id, lambda a: {**a, "status": "settled", "resolution": text, "by": by, "at": at or now(), **({"part": part} if part else {})})


def accept(kpi: dict, amb_id: str, reason: str, by: str, at: str | None = None) -> dict:
    """"Accept as a known risk": a reason is required; who may do it is the caller's rule (organiser or sponsor)."""
    text = _words(reason, "the reason you accept this as a known risk")
    return _replace(kpi, amb_id, lambda a: {**a, "status": "accepted", "resolution": text, "reason": text, "by": by, "at": at or now()})


def close(kpi: dict, amb_id: str, why: str, at: str | None = None) -> dict:
    """An open item whose cause is gone is closed by the code, visibly ("Closed: ..."); a person can still re-open it by changing the part."""
    return _replace(kpi, amb_id, lambda a: {**a, "status": "settled", "resolution": why, "by": LENS, "at": at or now(), "auto": True})


def asked(kpi: dict, amb_id: str, owner: str, at: str | None = None) -> dict:
    return _replace(kpi, amb_id, lambda a: {**a, "asked": {"owner": owner, "at": at or now()}})


def open_count(items: list[dict]) -> int:
    return sum(1 for a in items if a.get("status") == "open")


def role_of(kind: str) -> str:
    """Whose owner an ambiguity is asked of: the data owner for what concerns data, else the business owner."""
    return "data" if kind in ("source", "calculation", "currency") else "business"


def clear_restricted(kpi: dict) -> dict:
    """Open ambiguities drawn from a restricted document go when the measure is made less restricted."""
    keep = [a for a in kpi.get("ambiguities") or [] if not a.get("restricted")]
    return {**kpi, "ambiguities": keep} if len(keep) != len(kpi.get("ambiguities") or []) else kpi


def mentions(item: dict, terms) -> bool:
    """Does the item name any of these (names and ids of rows, and measures, the viewer may not see)? Compared on lower case and punctuation
    aside. A name of 2 or 3 characters must match as a whole word (else "id" would hide everything); a longer one also inside a word
    ("salaries" names "salary", "salary_band" names "salary")."""
    hay = _norm(" ".join(str(item.get(f) or "") for f in ("text", "question", "where", "resolution", "reason")) + " " + str((item.get("suggestion") or {}).get("value") or ""))
    padded = f" {hay} "
    for t in (_norm(x) for x in terms):
        if len(t) >= 4 and t in hay or len(t) >= 2 and f" {t} " in padded:
            return True
    return False


# ---- re-opening: never silently ------------------------------------------------------------------------------------------------------

def reopen(kpi: dict, amb_id: str, why: str, at: str | None = None) -> dict:
    """A settled or accepted item whose facts changed is open again, visibly ("Re-opened: <why>"), with what it was before kept in `history`."""
    def go(a):
        if a.get("status") == "open":
            return a
        before = {k: a.get(k) for k in ("status", "resolution", "by", "at", "reason", "part")}
        return {**{k: v for k, v in a.items() if k not in ("reason", "part", "auto")}, "status": "open", "resolution": None, "by": None, "at": at or now(),
                "reopened": f"Re-opened: {why}", "history": [*(a.get("history") or []), before]}
    return _replace(kpi, amb_id, go)


def reopen_for_part(kpi: dict, part: str, why: str) -> dict:
    """Items an answer settled by writing this part are re-opened when the part is later changed by someone else."""
    for a in list(kpi.get("ambiguities") or []):
        if a.get("status") == "settled" and a.get("part") == part:
            kpi = reopen(kpi, a["id"], why)
    return kpi
