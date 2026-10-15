"""The hypothesis record (spec 57, C7, C39): one shape shared by the opportunity, the Brainstorm outcome, the Initiative and its charter.

`intents/hypotheses/<hyp id>.json` = {id, origin: {kind, ref}, state: draft|checked|rejected|carried, carried_into: [], versions: [...]}.
A version is never edited in place: every change appends a version (`add_version`). A version frozen by a charter signature never changes.
The hypothesis `evidence[]` is the one evidence list (C7); 56's opportunity reads it through `as_56_evidence`.
"""
import logging
import re
from datetime import datetime, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
LENSES = ("new_revenue", "process_cost", "retention", "risk")
STATES = ("draft", "checked", "rejected", "carried")
CONFIDENCE = ("fairly_sure", "not_sure", "unlikely")  # words, never a percentage
RECORD_KINDS = ("data", "document", "voice", "whatif")  # C39 adds whatif
BASES = ("gap_to_target", "stated", "earlier_initiative")  # C8: company history only; a pack figure is never a basis
_ID = re.compile(r"hyp-[a-z0-9][a-z0-9-]{0,80}")
_EMPTY = {"belief": "", "lens": None, "measure": None, "baseline": None, "target": None, "expected_uplift": None, "confidence": "not_sure",
          "review_date": None, "evidence": [], "counter_check": None, "theme": None, "frozen_by": None}


def _dir(plane):
    return plane.path("intents", "hypotheses")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get(plane, hyp_id: str) -> dict | None:
    if not isinstance(hyp_id, str) or not _ID.fullmatch(hyp_id):
        return None
    try:
        rec = read_json_strict(_dir(plane) / f"{hyp_id}.json", dict)
    except (OSError, ValueError) as e:
        log.warning("a hypothesis record is unreadable: %s", type(e).__name__)
        return None
    return rec if isinstance(rec, dict) and rec.get("id") == hyp_id and rec.get("versions") else None


def all_records(plane) -> list[dict]:
    return [r for f in sorted(_dir(plane).glob("hyp-*.json")) if (r := get(plane, f.stem))]


def latest(rec: dict | None) -> dict | None:
    return rec["versions"][-1] if rec and rec.get("versions") else None


def ref(rec: dict) -> dict:
    return {"id": rec["id"], "version": rec["versions"][-1]["v"]}


def create(plane, origin: dict, fields: dict, by: str, state: str = "draft") -> dict:
    """A new record with version 1. `fields` are version fields; anything missing takes the empty value."""
    with lock_for(_dir(plane) / ".lock"):
        n = 1 + max((int(m.group(1)) for f in _dir(plane).glob("hyp-*.json") if (m := re.fullmatch(r"hyp-(\d{4,})", f.stem))), default=0)
        rec = {"id": f"hyp-{n:04d}", "origin": origin, "state": state, "carried_into": [],
               "versions": [{**_EMPTY, **fields, "v": 1, "at": now(), "by": by}]}
        write_json_atomic(_dir(plane) / f"{rec['id']}.json", rec)
    return rec


def add_version(plane, hyp_id: str, changes: dict, by: str, state: str | None = None) -> dict | None:
    """Appends a version: the latest one with `changes` laid over it. The earlier versions (frozen ones included) stay as they were."""
    path = _dir(plane) / f"{hyp_id}.json"
    with lock_for(path):
        rec = get(plane, hyp_id)
        if rec is None:
            return None
        last = rec["versions"][-1]
        rec["versions"].append({**last, **changes, "v": last["v"] + 1, "at": now(), "by": by, "frozen_by": changes.get("frozen_by")})
        if state:
            rec["state"] = state
        write_json_atomic(path, rec)
    return rec


def set_state(plane, hyp_id: str, state: str) -> None:
    path = _dir(plane) / f"{hyp_id}.json"
    with lock_for(path):
        rec = get(plane, hyp_id)
        if rec and state in STATES:
            rec["state"] = state
            write_json_atomic(path, rec)


def evidence_line(n: int, record_kind: str, stance: str, text: str, trace: dict, by: str, voices: int | None = None) -> dict:
    return {"id": f"ev{n}", "record_kind": record_kind, "stance": stance, "text": text, "trace": trace, "voices": voices, "by": by, "line_ref": None}


def record_kind_of(source_kind: str | None) -> str:
    """56 source kinds to 57 record kinds."""
    if source_kind == "document":
        return "document"
    if source_kind in ("week_item", "wall", "brainstorm", "backlog"):
        return "voice"
    return "whatif" if source_kind == "whatif" else "data"


def add_evidence(plane, hyp_id: str, ev: dict, by: str) -> dict | None:
    """A person's evidence line (56 shape: text, kind supports|disputes, source) as a new version (C7)."""
    rec = get(plane, hyp_id)
    if rec is None:
        return None
    lines = list(latest(rec)["evidence"])
    src = ev.get("source") or {}
    lines.append(evidence_line(len(lines) + 1, record_kind_of(src.get("kind")), "counters" if ev["kind"] == "disputes" else "supports", ev["text"],
                               {"kind": src.get("kind") or "person", "ref": src.get("ref"), "at": now()}, by))
    return add_version(plane, hyp_id, {"evidence": lines}, by)


def as_56_evidence(rec: dict) -> list[dict]:
    """The shim 56 reads (C7): hypothesis lines in the opportunity's evidence shape, with record_kind and stance kept."""
    v = latest(rec) or {}
    return [{"id": e["id"], "text": e["text"], "kind": "disputes" if e["stance"] == "counters" else "supports",
             "source": {"kind": (e.get("trace") or {}).get("kind"), "ref": (e.get("trace") or {}).get("ref")}, "by": e["by"],
             "at": (e.get("trace") or {}).get("at") or v.get("at"), "record_kind": e["record_kind"], "stance": e["stance"], "voices": e.get("voices")}
            for e in v.get("evidence") or []]


def uplift_gap(baseline: dict | None, target: dict | None) -> dict | None:
    """Gap to target, the one uplift basis computed here: only from a traced single baseline value and a person's target."""
    if not baseline or not target or not isinstance(baseline.get("value"), (int, float)) or not isinstance(target.get("value"), (int, float)):
        return None
    return {"value": round(abs(baseline["value"] - target["value"]), 4), "unit": baseline.get("unit"), "per": None, "basis": "gap_to_target",
            "trace": baseline.get("trace")}


def missing_uplift(v: dict) -> str | None:
    """Why the uplift cannot be worked out, or None when it can."""
    if v.get("expected_uplift"):
        return None
    if not v.get("measure"):
        return "Not available yet: no measure for this theme"
    if not v.get("baseline"):
        return "Not available yet: no baseline"
    if not v.get("target"):
        return "Not available yet: no target"
    return "Not available yet: the baseline is split by group, so one gap cannot be worked out"
