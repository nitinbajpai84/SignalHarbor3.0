"""The baseline record and the signed charter it starts from (M2-01). Files in the company plane, contracts/SHARED.md:

intents/m2_baseline/<baseline id>/baseline.json   {id, charter_outcome_id, state, created_at}   one per signed charter
intents/m1_intent/outcomes/<outcome id>.json      the signed charter (module 1's output; read only, as a file: a module
                                                  never imports another module)

`read_baseline(plane, baseline_id)` is what the other module 2 packages call.
"""
import logging
import re
import secrets
from datetime import datetime, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
_HEX32 = re.compile(r"[0-9a-f]{32}")
STATES = ("draft", "requests", "mapping", "review", "signed")
UNREADABLE = "These records could not be read, so nothing was changed. Please ask your administrator."
NOT_SAVED = "That could not be saved. Please try again."
LOCKED = "This baseline is signed; it can no longer be changed."


class StoreError(Exception):
    """A plain-words failure; never contains a path or an id."""


class Locked(StoreError):
    """The baseline is signed: signed content is read-only."""


def is_id(value) -> bool:
    return isinstance(value, str) and _HEX32.fullmatch(value) is not None


def root(plane):
    return plane.path("intents", "m2_baseline")


def read_file(path, kind: type):
    try:
        return read_json_strict(path, kind)
    except (OSError, ValueError):
        log.warning("a baseline file could not be read")
        raise StoreError(UNREADABLE) from None


def write_file(path, data) -> None:
    try:
        write_json_atomic(path, data)
    except OSError:
        raise StoreError(NOT_SAVED) from None


def read_baseline(plane, baseline_id) -> dict | None:
    """{id, charter_outcome_id, state, created_at}, or None when there is no such baseline."""
    if not is_id(baseline_id):
        return None
    return read_file(root(plane) / baseline_id / "baseline.json", dict)


def set_state(plane, baseline_id: str, state: str) -> None:
    """Signing moves the baseline to "signed"; a new version moves it back to "review". Every working-copy route reads this one
    state (api/signed_guard.py, store/kpis.py, store/catalogue.py, the process map), so it is set in one place."""
    if state not in STATES:
        raise ValueError("unknown state")
    with lock_for(root(plane) / baseline_id / "baseline.json"):
        base = read_baseline(plane, baseline_id)
        if base is None:
            raise LookupError("no baseline")
        write_file(root(plane) / baseline_id / "baseline.json", {**base, "state": state})


def _listed(doc: dict, key: str) -> list[dict]:
    return [p for p in doc.get(key) or [] if isinstance(p, dict) and p.get("id") and str(p.get("title") or "").strip()]


def read_charter(plane, outcome_id) -> dict | None:
    """The signed charter's outcome record, or None. Read from module 1's file; its shape is contracts/outcome.yaml.
    Module 1 hands four lists: `problems` (intents only), `pain_points`, `future_signals`, `levers`. Here `problems` holds the
    intents and the pain points (each tagged `kind`), so everything that matches measures to problems treats a pain point the
    same way; future signals and levers stay as they are, context and never problems. An older charter has only `problems`."""
    if not is_id(outcome_id):
        return None
    doc = read_file(plane.path("intents", "m1_intent", "outcomes", f"{outcome_id}.json"), dict)
    if not (doc and doc.get("kind") == "charter" and isinstance(doc.get("problems"), list)):
        return None
    problems = [{**p, "kind": "problem"} for p in doc["problems"] if isinstance(p, dict)]
    seen = {p.get("id") for p in problems}
    pain = [{**p, "kind": "pain_point"} for p in _listed(doc, "pain_points") if p["id"] not in seen]
    return {**doc, "problems": problems + pain, "future_signals": _listed(doc, "future_signals"), "levers": _listed(doc, "levers")}


def charter_title(doc: dict) -> str:
    """What the charter is called on screen: the charter has no title of its own, so its first problem, and how many more."""
    titles = [str(p.get("title") or "").strip() for p in doc["problems"] if isinstance(p, dict) and str(p.get("title") or "").strip()]
    return (titles[0] + (f" and {len(titles) - 1} more" if len(titles) > 1 else "")) if titles else ""


def charters(plane) -> list[dict]:
    """The signed charters this company can start from, newest first."""
    folder = plane.path("intents", "m1_intent", "outcomes")
    out = []
    for f in folder.glob("*.json") if folder.is_dir() else []:
        doc = read_charter(plane, f.stem)
        if doc:
            out.append({"outcome_id": f.stem, "signed_at": str(doc.get("signed_at") or ""), "problem_count": len(doc["problems"]) + len(doc["future_signals"]) + len(doc["levers"]),  # module 1 hands on all four lists
                        
                        "title": charter_title(doc)})
    return sorted(out, key=lambda c: c["signed_at"], reverse=True)


def baselines(plane) -> list[dict]:
    folder = root(plane)
    found = [read_baseline(plane, p.name) for p in folder.iterdir() if p.is_dir()] if folder.is_dir() else []
    return sorted((b for b in found if b), key=lambda b: b["created_at"], reverse=True)


def start(plane, charter_outcome_id: str | None) -> tuple[dict, bool]:
    """(baseline, created). One baseline per signed charter: a second start returns the first. With no charter (module 1
    not bought, or a company starting from nothing) the baseline starts empty and KPIs are added by hand. Raises
    LookupError for a charter that is not signed here."""
    if charter_outcome_id is not None and read_charter(plane, charter_outcome_id) is None:
        raise LookupError("no signed charter")
    with lock_for(root(plane)):
        if charter_outcome_id is not None:
            for b in baselines(plane):
                if b["charter_outcome_id"] == charter_outcome_id:
                    return b, False
        b = {"id": secrets.token_hex(16), "charter_outcome_id": charter_outcome_id, "state": "draft",
             "created_at": datetime.now(timezone.utc).isoformat()}
        write_file(root(plane) / b["id"] / "baseline.json", b)
        return b, True
