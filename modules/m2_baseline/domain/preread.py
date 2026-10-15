"""The pre-read checklist (M2-AGENTS): what the business can give Lens before the work list. Each kind is optional; a document
is tagged with a kind or the person says "we do not have this". The documents live in the company context store (the
same ones the Company context page holds); this is a view over them, tagged by kind. Plain words, no industry named."""
import hashlib
import re

from modules.m2_baseline.agent import lens
from modules.m2_baseline.domain import governance_view as GV
from modules.m2_baseline.domain.worklist import Invalid
from modules.m2_baseline.store import lens as LS
from modules.m2_baseline.store.baseline import StoreError
from sh_platform.context_docs.retrieval import INTRO, retrieve, wrap_untrusted
from sh_platform.context_docs import documents_for
from sh_platform.context_docs.store import DocStore
from sh_platform.plane import CrossCompanyError

KINDS = (
    ("glossary", "Business glossary", "The words your company uses for its measures and what they mean."),
    ("definitions", "KPI or report definitions in use", "How your reports define each measure today."),
    ("figures", "Last period's reported figures or dashboards", "Only to see what is reported now; Lens never copies a figure into a definition."),
    ("procedures", "Process or procedure documents", "How the numbers are produced, step by step."),
    ("sources", "List of sources and who owns them", "The systems, files and the people responsible for them."),
    ("dictionaries", "Data dictionaries or sample files", "Table and column names help Lens; it never reads values from them."),
)
KEYS = tuple(k for k, _, _ in KINDS)


def view(inputs: dict, documents: list[dict]) -> list[dict]:
    """The checklist: each kind with the documents tagged to it (still on file) and whether the person said they have none."""
    titles = {d["doc_id"]: d["title"] for d in documents}
    out = []
    for key, label, help_ in KINDS:
        got = inputs.get(key) or {}
        out.append({"key": key, "label": label, "help": help_, "none": bool(got.get("none")),
                    "docs": [{"doc_id": i, "title": titles[i]} for i in got.get("docs") or [] if i in titles]})
    return out


def checked(kind: str, body, allowed: set[str]) -> tuple[list[str], bool]:
    """(document ids, none) from a person's tick: only documents this person may see; "none" and documents never both."""
    if kind not in KEYS:
        raise LookupError("no such kind")
    docs, none = (body.get("docs") if isinstance(body, dict) else None) or [], bool(isinstance(body, dict) and body.get("none"))
    if not isinstance(docs, list) or not all(isinstance(i, str) for i in docs):
        raise Invalid("Please choose documents from the list.")
    if any(i not in allowed for i in docs):
        raise Invalid("One of those documents is not on file. Please choose from the list.")
    return ([] if none else list(dict.fromkeys(docs))), none


# ---- documents that mention personal data wait for the organiser (round 5B) ---------------------------------------------------------
# A document uploaded on the Company context page is read here for the pack's personal-data words and the generic words of
# contracts/governance.yaml. A hit is "pending": the organiser is asked "Mark it restricted?" (the context documents' own restrict route) or says it is
# not personal data. Until then Lens does not read it for a measure not marked personal. Every retrieval of module 2 goes through `read`.
PENDING, CLEAN, CLEARED = "pending", "clean", "cleared"
_NOT_PERSONAL: set = set()  # (kind, words) pairs never flagged; the contract's document_kinds already leaves channel words out


def _phrases(parts: dict) -> list[str]:
    """What the industry pack calls personal data: a feed field flagged pii, by its id and every spelling the pack knows for it."""
    out = []
    for feed, body in (parts.get("feeds") or {}).items():
        for fld in (body or {}).get("fields") or []:
            if not fld.get("pii"):
                continue
            spellings = (((parts.get("synonyms") or {}).get(feed) or {}).get(fld.get("id")) or {}).get("spellings") or []
            out += [" ".join(re.findall(r"[a-z0-9]+", str(s).lower())) for s in [fld.get("id"), *(x.get("spelling") if isinstance(x, dict) else x for x in spellings)]]
    return [p for p in dict.fromkeys(out) if p]


def personal_words(text: str, parts: dict) -> list[str]:
    """The words in `text` that name personal data, in the order they appear: the pack's own personal fields, then the generic words (names,
    contact details, pay, identifiers). A guess to ask a person about, never a decision."""
    words = re.findall(r"[a-z0-9]+", str(text or "").lower())
    flat, found, taken = " ".join(words), [], set()
    for phrase in _phrases(parts):
        if re.search(rf"\b{re.escape(phrase)}\b", flat):
            found.append((flat.index(phrase), phrase))
    kinds = GV._words()["document_kinds"]
    for n in (1, 2, 3):
        for i in range(len(words) - n + 1):
            key = "_".join(words[i:i + n])
            if not taken & set(range(i, i + n)) and any(p.search(key) and (kind, key) not in _NOT_PERSONAL for kind, ps in kinds.items() for p in ps):
                taken |= set(range(i, i + n))
                found.append((len(" ".join(words[:i])), " ".join(words[i:i + n])))
    return [w for _, w in sorted(dict.fromkeys(found))]


class _Held(DocStore):
    """The company's documents for a measure not marked personal, without the ones waiting for the organiser: not their passages, not their
    shared summaries. (Passage-level filtering leaks: a pay table's rows carry no flagged word, and a pay word has many synonyms.)"""
    held: frozenset = frozenset()

    def own_chunks(self, agent: str) -> list[dict]:
        return [{"title": d["title"], "text": c["text"], "location": c.get("location"), "source": "own_document"}
                for d in documents_for(self.plane, agent) if d["doc_id"] not in self.held for c in d.get("chunks", [])]

    def shared_summaries(self, agent: str) -> list[dict]:
        return [{"title": d["title"], "text": d["shared_summary"], "location": None, "source": "shared_summary"}
                for d in documents_for(self.plane, agent)
                if d["doc_id"] not in self.held and d["agent"] != agent and d.get("visibility") == "shared"]


def review(plane, parts: dict) -> set[str]:
    """Reads every document not yet read for personal data (a new upload) and returns the ids held back: pending, not restricted."""
    try:
        docs = documents_for(plane, lens.DOCUMENT_AGENT)  # a restricted document is already closed to everyone
    except (OSError, ValueError, CrossCompanyError):
        return set()  # no document can be read either, so nothing is released
    try:
        seen = LS.scans(plane)
    except StoreError:
        return {d["doc_id"] for d in docs}  # fails closed: with no readable record every document waits, and the damaged file is left as it is
    held = set()
    for d in docs:
        try:
            if d["doc_id"] not in seen and (d.get("chunks") or d.get("shared_summary")):
                text = " ".join([*(str(c.get("text") or "") for c in d["chunks"]), str(d.get("shared_summary") or "")])  # the text and its published summary
                words = personal_words(text, parts)
                seen[d["doc_id"]] = {"words": words, "state": PENDING if words else CLEAN, "sha": text_hash(d)}
                LS.set_scan(plane, d["doc_id"], seen[d["doc_id"]])
        except (OSError, StoreError):
            held.add(d["doc_id"])  # could not be recorded: held back, not released
            continue
        if (seen.get(d["doc_id"]) or {}).get("state") == PENDING:
            held.add(d["doc_id"])
    return held


def text_hash(doc: dict) -> str:
    """A fingerprint of a document's text, so a rebuilt document with the same content keeps the organiser's decision."""
    return hashlib.sha256(" ".join(str(c.get("text") or "") for c in doc.get("chunks", [])).encode("utf-8")).hexdigest()


def clear(plane, doc_id: str) -> None:
    """The organiser says this document is not personal data: Lens may read it for every measure."""
    seen = LS.scans(plane)
    if doc_id not in seen:
        raise LookupError(doc_id)
    LS.set_scan(plane, doc_id, {**seen[doc_id], "state": CLEARED})


def read(plane, parts: dict, query: str, *, restricted_ok: bool = False) -> tuple[str, list[str]]:
    """Lens's retrieval for module 2: `lens.preread`, except that a document waiting for the organiser's decision is not read for a measure
    not marked personal (`restricted_ok` false). Same result: (quoted passages, their titles)."""
    held = review(plane, parts)
    if restricted_ok or not held:
        return lens.preread(plane, query, restricted_ok=restricted_ok)
    try:
        LS.scans(plane)
    except StoreError:
        return "", []  # no readable record of what each document says: nothing is released, not even an ordinary passage
    store = _Held(plane)
    store.held = frozenset(held)
    try:
        hits = [h for h in retrieve(store, lens.DOCUMENT_AGENT, query) if h.get("title") and h["text"]]
    except (OSError, ValueError, CrossCompanyError):
        return "", []
    if not hits:
        return "", []
    text = "\n\n".join([INTRO] + [wrap_untrusted(lens._plain(h["text"]), " ".join(str(h["title"]).split())[:80]) for h in hits])
    return text, list(dict.fromkeys(" ".join(str(h["title"]).split())[:80] for h in hits))
