"""The assessment record (SHARED.md): one folder per assessment in the company plane.

intents/m3_connect/assessments/<assessment_id>/assessment.json   {id, baseline_outcome_id, charter_outcome_id, state, created_by, created_at}

Created from the newest signed module 2 outcome (read by path, never imported). One assessment per signed outcome: a second start returns
the first. Other packages write their own files in the same folder and read this one through `read_assessment` / `folder`.
"""
import logging
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
_HEX32 = re.compile(r"[0-9a-f]{32}")
UNREADABLE = "These records could not be read, so nothing was changed. Please ask your administrator."
NOT_SAVED = "That could not be saved. Please try again."
NO_BASELINE = "There is no signed baseline yet. Sign the baseline in module 2 first, then start the assessment."


class StoreError(Exception):
    """A plain-words failure; never contains a path or an id."""


class NoSignedBaseline(StoreError):
    pass


def is_id(value) -> bool:
    return isinstance(value, str) and _HEX32.fullmatch(value) is not None


def root(plane) -> Path:
    return plane.path("intents", "m3_connect", "assessments")


def folder(plane, assessment_id) -> Path | None:
    """The assessment's folder, or None for an id that is not one. Never built from anything but a 32-hex id."""
    return root(plane) / assessment_id if is_id(assessment_id) else None


def read_assessment(plane, assessment_id) -> dict | None:
    d = folder(plane, assessment_id)
    if d is None:
        return None
    try:
        return read_json_strict(d / "assessment.json", dict)
    except (OSError, ValueError):
        log.warning("an assessment file could not be read")
        raise StoreError(UNREADABLE) from None


def assessments(plane) -> list[dict]:
    found = [read_assessment(plane, p.name) for p in root(plane).iterdir() if p.is_dir()] if root(plane).is_dir() else []
    return sorted((a for a in found if a), key=lambda a: a["created_at"], reverse=True)


def create(plane, baseline_outcome: dict | None, by: str) -> tuple[dict, bool]:
    """(assessment, created). Raises NoSignedBaseline when there is no signed baseline to start from."""
    if not baseline_outcome:
        raise NoSignedBaseline(NO_BASELINE)
    with lock_for(root(plane)):
        for a in assessments(plane):
            if a["baseline_outcome_id"] == baseline_outcome["outcome_id"]:
                return a, False
        a = {"id": secrets.token_hex(16), "baseline_outcome_id": baseline_outcome["outcome_id"],
             "charter_outcome_id": baseline_outcome.get("charter_outcome_id"), "state": "draft",
             "created_by": by, "created_at": datetime.now(timezone.utc).isoformat()}
        try:
            write_json_atomic(root(plane) / a["id"] / "assessment.json", a)
        except OSError:
            raise StoreError(NOT_SAVED) from None
        return a, True
