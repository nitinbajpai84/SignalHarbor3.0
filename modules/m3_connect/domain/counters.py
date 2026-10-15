"""LI-M3: how many human inputs one assessment took, as two small counters for the outcomes page.

`inputs_count.json` in the assessment folder: {"actions": {<kind>: n}, "actions_total": n, "free_text": n}. A human action is one thing a person did
(uploaded a file, chose a source, mapped a figure, checked a rule, decided a risk, edited a plan item, signed). `free_text` counts the actions that
carried words a person typed (a reason, a note). Only counts are kept: no name, no text.
"""
import logging
from pathlib import Path

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
FILE = "inputs_count.json"


def read(folder: Path) -> dict:
    try:
        doc = read_json_strict(Path(folder) / FILE, dict)
    except (OSError, ValueError):
        doc = None
    return doc if doc else {"actions": {}, "actions_total": 0, "free_text": 0}


def bump(folder: Path, kind: str, free_text: bool = False) -> None:
    """Counts one human action of `kind`. A counter that cannot be written never fails the action itself."""
    path = Path(folder) / FILE
    try:
        with lock_for(path):
            doc = read(folder)
            doc["actions"][kind] = doc["actions"].get(kind, 0) + 1
            doc["actions_total"] = sum(doc["actions"].values())
            doc["free_text"] += 1 if free_text else 0
            write_json_atomic(path, doc)
    except (OSError, ValueError):
        log.warning("an input count could not be saved")  # a lost count is better than a lost upload
