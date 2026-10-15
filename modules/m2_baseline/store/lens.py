"""What Lens has tried, per measure or suggestion: intents/m2_baseline/<baseline id>/lens.json
{"attempts": {id: outcome}, "drafts": {id: {field: provenance value}}, "inputs": {kind: {"docs": [doc id], "none": bool}}}.
An attempt is recorded so the page never drafts the same measure again on every open (it stays a button: "Try again").
`drafts` holds what Lens filled that has no home yet: for a suggestion every field (definition, producer, gathered,
owner), for a confirmed measure only the likely owner (a guessed owner would count as nominated). `inputs` is the
pre-read checklist: which of the company's own uploaded documents a person tagged as which kind of input, or that they
have none. The documents themselves stay in the company context store. Not a contract file: no other package reads it."""
import time

from modules.m2_baseline.store import baseline as B
from sh_platform.jsonfile import lock_for


def _file(plane, baseline_id):
    return B.root(plane) / baseline_id / "lens.json"


def read(plane, baseline_id) -> dict:
    doc = (B.read_file(_file(plane, baseline_id), dict) if B.is_id(baseline_id) else None) or {}
    return {k: dict(doc.get(k) or {}) for k in ("attempts", "drafts", "inputs", "claimed")}


STALE_AFTER = 300  # seconds: a "working" claim older than this was never finished (the caller crashed or went away)


def is_stale(doc: dict, item_id: str) -> bool:
    return doc["attempts"].get(item_id) == "working" and time.time() - float(doc["claimed"].get(item_id) or 0) > STALE_AFTER


def _write(plane, baseline_id, change) -> None:
    with lock_for(_file(plane, baseline_id)):
        doc = read(plane, baseline_id)
        change(doc)
        B.write_file(_file(plane, baseline_id), doc)


def record(plane, baseline_id: str, item_id: str, outcome: str, draft: dict | None = None) -> None:
    """Note what happened to one measure or suggestion, and keep the fields Lens filled that have no home yet."""
    def change(doc):
        doc["attempts"][item_id] = outcome
        if draft:
            doc["drafts"][item_id] = {**doc["drafts"].get(item_id, {}), **draft}
    _write(plane, baseline_id, change)


def claim(plane, baseline_id: str, ids: list[str], retry: bool = False) -> list[str]:
    """The ids this caller may draft now: each is marked "working" under the lock BEFORE any model call, so a second tab or user
    opening at the same time skips it. `retry` takes them again (the "Try again" button)."""
    got: list[str] = []

    def change(doc):
        for i in ids:
            if retry or i not in doc["attempts"] or is_stale(doc, i):  # a claim nobody finished can be taken again
                doc["attempts"][i] = "working"
                doc["claimed"][i] = time.time()
                got.append(i)
    _write(plane, baseline_id, change)
    return got


def clear_restricted(plane, baseline_id: str, item_id: str, titles) -> None:
    """Drop what Lens kept for one item that it drew from a restricted document (flagged, or its title is in `titles`)."""
    def change(doc):
        kept = {f: v for f, v in (doc["drafts"].get(item_id) or {}).items()
                if not (v.get("restricted") or any(t in str(v.get("from") or "") for t in titles))}
        doc["drafts"].pop(item_id, None)
        if kept:
            doc["drafts"][item_id] = kept
    _write(plane, baseline_id, change)


def set_input(plane, baseline_id: str, kind: str, docs: list[str], none: bool) -> None:
    _write(plane, baseline_id, lambda doc: doc["inputs"].__setitem__(kind, {"docs": docs, "none": none}))


# ---- what the company's documents say about personal data: one file for the company (a document belongs to the company, not to a baseline)

def _scans_file(plane):
    return B.root(plane) / "document_scans.json"


def scans(plane) -> dict:
    """{doc id: {"words": [...], "state": "pending" | "clean" | "cleared"}}. Pending: the document mentions personal data and the organiser has not
    decided; Lens does not read it for a measure not marked personal. Cleared: the organiser said it is not personal data."""
    return dict(B.read_file(_scans_file(plane), dict) or {})


def set_scan(plane, doc_id: str, record: dict) -> None:
    with lock_for(_scans_file(plane)):
        B.write_file(_scans_file(plane), {**scans(plane), doc_id: record})
