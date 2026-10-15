"""What an agent never remembers (AGENT-MEMORY-PLAN): anonymous notes, restricted areas, figures, contact details."""
import re

from sh_platform.plane import CompanyPlane
from sh_platform.profile import store, view

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_NUMBER = re.compile(r"(?<![A-Za-z0-9])[$€£]?\d[\d,.]*")  # any standalone number, with or without a unit or currency; "Q3" is not one
_ACCOUNT = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{8,}\b")  # IBAN-like; long digit runs and phones are caught by _NUMBER
_QUOTE = re.compile(r"[\"“”]")
# a model reply that says nothing was given, or talks about "the user", is not a fact about the person; an anonymous note is never about a person
_JUNK = re.compile(r"^\s*(no|nothing)\b.*\b(provided|stored|available|mentioned|found|extract\w*|remember\w*)\b|^\s*(the )?user\b|\banonymous", re.I)


def restricted_terms(plane: CompanyPlane) -> set[str]:
    """Lower-case names of restricted areas, and of people the unrestricted profile hides (a person of a restricted team)."""
    doc = store.raw(plane)
    terms = {view.norm(x) for k, a in doc["governance"]["restricted_areas"].items() for x in (k, view._v(a, "area") or "") if x}
    open_people = set(view.read_unrestricted(plane)["people"])
    for k, p in doc["people"].items():
        if k not in open_people:
            terms |= {view.norm(x) for x in (k.replace("-", " "), view._v(p, "name") or "")}
    return {t for t in terms if len(t) >= 2}


def person_names(plane: CompanyPlane) -> set[str]:
    doc = store.raw(plane)
    return {str(x) for k, p in doc["people"].items() for x in (k.replace("-", " ").title(), view._v(p, "name")) if x}


def allowed(text: str, terms: set[str]) -> bool:
    low = view.norm(text)
    if _EMAIL.search(text) or _NUMBER.search(text) or _ACCOUNT.search(text):
        return False
    return not any(re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", low) for t in terms)


def junk(text: str) -> bool:
    return bool(_JUNK.search(text or ""))


def tidy(entries: list[dict]) -> list[dict]:
    """What a person is shown: no junk or repeated lines, "a initiative" mended, a plain fact or preference not headed "Open question"."""
    seen, out = set(), []
    for e in sorted(entries, key=lambda x: str(x.get("updated_at") or ""), reverse=True):
        text = re.sub(r"\ba (?=[aeiou])", "an ", str(e.get("text") or ""))
        key = view.norm(text)
        if junk(text) or key in seen:
            continue
        seen.add(key)
        kind = "fact" if e.get("kind") == "open" and text.startswith("Ran a") else "preference" if e.get("kind") == "open" and text.startswith("Prefers ") else e.get("kind")
        out.append({**e, "text": text, "kind": kind})
    return out


def clean(plane: CompanyPlane, entries: list[dict]) -> list[dict]:
    """Drop what must never be stored: anonymous notes, empty text, restricted-area content, figures, emails, phones, account numbers."""
    terms = restricted_terms(plane)
    return [e for e in entries
            if not e.get("anonymous") and str(e.get("text") or "").strip() and not junk(str(e["text"])) and allowed(str(e["text"]), terms)]


def depersonalise(text: str, names: set[str]) -> str | None:
    """Company wording: names replaced; None when the text is a quote."""
    if _QUOTE.search(text):
        return None
    for n in sorted(names, key=len, reverse=True):
        text = re.sub(rf"(?<![A-Za-z]){re.escape(n)}(?![A-Za-z])", "a colleague", text, flags=re.I)
    return text
