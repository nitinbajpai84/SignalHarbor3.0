"""The company profile: one file per company plane, `context/profile/profile.json`, every value a provenance cell (LI-PROFILE).

A cell is `{value, mark: stated|guessed|unknown, by, at, from, ref?, agent?}`: module 2's shape. `from` is a plain human label
("Business glossary, page 3", "Interview with Mei Tan", "Sample file sept.xlsx"), never an id. `ref` is the machine pointer
`{kind: document|interview|sample|person, id, page?}`. `agent` ("lens", "nira", "north") is set only on a draft an agent wrote, so a
person who happens to be called Lens is still a person. Drafts and a person's answers stay apart by `agent`, `by` and `mark`.

Sections hold items keyed by id, and an item's fields are cells: `people.<id>.<field>`, `systems.<id>.<field>`,
`governance.restricted_areas.<id>.<field>`, `governance.field_rules.<id>.<field>`, `reported_figures.<id>.<field>`,
`samples.<id>.<field>`, `interviews.<id>.<field>`, `constraints.<id>.<field>`, `inputs.<group>.<field>`.
A draft by an agent never overwrites a cell a person wrote (rule 7). The file is written whole or not at all, under one lock.
"""
import copy
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.graph.hooks import mark_dirty
from sh_platform.plane import CompanyPlane

MARKS = ("stated", "guessed", "unknown")
KINDS = ("document", "interview", "sample", "person")
AGENTS = frozenset({"lens", "nira", "north"})  # the values of a cell's `agent` flag
DEPTH = {"inputs": 3, "people": 3, "systems": 3, "reported_figures": 3, "samples": 3, "interviews": 3, "constraints": 3, "cards": 3, "governance": 4}
GOVERNANCE = ("restricted_areas", "field_rules")
_SEG = re.compile(r"[a-z0-9_@-]{1,80}")


def empty() -> dict:
    return {"version": 1, "inputs": {}, "people": {}, "systems": {}, "reported_figures": {}, "samples": {}, "interviews": {},
            "constraints": {}, "cards": {}, "governance": {"restricted_areas": {}, "field_rules": {}}}


def _file(plane: CompanyPlane):
    return plane.path("context", "profile", "profile.json")


def is_agent(c: Any) -> bool:
    """True for a cell an agent drafted: decided by the explicit `agent` flag, never by the display name in `by`."""
    return isinstance(c, dict) and c.get("agent") in AGENTS


def cell(value: Any, provenance: Mapping[str, Any]) -> dict:
    """A provenance cell, checked. An unknown never carries a value."""
    mark, by, src, ref = provenance.get("mark"), str(provenance.get("by") or "").strip(), provenance.get("from"), provenance.get("ref")
    agent = provenance.get("agent")
    if mark not in MARKS:
        raise ValueError("mark must be stated, guessed or unknown")
    if not by:
        raise ValueError("a value needs the name of who said it")
    if not isinstance(src, str) or not src.strip():
        raise ValueError("from needs a plain label of where it came from")
    if agent is not None and agent not in AGENTS:
        raise ValueError("agent must be lens, nira or north")
    if ref is not None and (not isinstance(ref, Mapping) or ref.get("kind") not in KINDS or not str(ref.get("id") or "").strip()):
        raise ValueError("ref needs a kind (document, interview, sample or person) and an id")
    out = {"value": None if mark == "unknown" else value, "mark": mark, "by": by,
           "at": provenance.get("at") or datetime.now(timezone.utc).isoformat(), "from": src.strip()}
    if ref is not None:
        out["ref"] = {k: ref[k] for k in ("kind", "id", "page") if ref.get(k)}
    if agent:
        out["agent"] = agent
    return out


def _path(path: str) -> list[str]:
    parts = path.split(".") if isinstance(path, str) else []
    if len(parts) == 3 and parts[0] == "interviews":  # a question id is Q1..Q14 in the contract and q1..q14 in the store
        parts[2] = parts[2].lower()
    if not parts or parts[0] not in DEPTH or len(parts) != DEPTH[parts[0]] or not all(_SEG.fullmatch(p) for p in parts):
        raise ValueError("that is not a place in the profile")
    if parts[0] == "governance" and parts[1] not in GOVERNANCE:
        raise ValueError("that is not a place in the profile")
    return parts


def load(plane: CompanyPlane) -> dict:
    doc = read_json_strict(_file(plane), dict)
    return doc if doc is not None else empty()


def mutate(plane: CompanyPlane, change) -> Any:
    """Read, change and write the whole file under its lock. `change(doc)` returns what the caller wants back."""
    path = _file(plane)
    with lock_for(path):
        doc = load(plane)
        out = change(doc)
        write_json_atomic(path, doc)
    mark_dirty(plane)  # every profile write (record, drop_drafts, a reader's changes) goes through here: the company graph is rebuilt from it
    return out


def set_cell(doc: dict, path: str, value: Any, provenance: Mapping[str, Any]) -> dict | None:
    """Writes into `doc`; None when a person's cell is kept because an agent tried to replace it."""
    parts = _path(path)
    new = cell(value, provenance)
    if parts[0] == "people" and parts[2] == "account_id" and (is_agent(new) or new["mark"] == "guessed"):
        return None  # a link to a sign-in account is made by a person only: an agent's or a draft's write is refused (LI-LINK)
    node = doc
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    old = node.get(parts[-1])
    if isinstance(old, dict) and old.get("mark") != "unknown" and not is_agent(old) and is_agent(new):
        return None
    if isinstance(old, dict) and old.get("mark") == "stated" and new["mark"] == "guessed":
        return None  # marks decide, not authors: a guess never replaces a stated value, whoever stated it
    node[parts[-1]] = new
    return new


def record(plane: CompanyPlane, path: str, value: Any, provenance: Mapping[str, Any]) -> dict | None:
    """The one way to write the profile. `provenance` is {mark, by, from: {kind, ref, page?}, at?}. Returns the cell written, or None
    when a person's own cell was kept."""
    return mutate(plane, lambda doc: set_cell(doc, path, value, provenance))


def drop_drafts(doc: dict, source: str) -> None:
    """Removes every item whose cells were all drafted by an agent from the attachment `source` (from.att), ready for a re-read.
    An item a person has touched stays."""
    def mine(item) -> bool:
        cells = [c for c in item.values() if isinstance(c, dict) and "mark" in c]
        return bool(cells) and all(is_agent(c) and (c.get("ref") or {}).get("id") == source for c in cells)
    for section in ("people", "systems", "reported_figures", "samples", "constraints"):
        doc[section] = {k: v for k, v in doc[section].items() if not mine(v)}
    for part in GOVERNANCE:
        doc["governance"][part] = {k: v for k, v in doc["governance"][part].items() if not mine(v)}


def raw(plane: CompanyPlane) -> dict:
    """The whole profile, unfiltered: for the kernel's own readiness and asks. Never send it to a screen."""
    return copy.deepcopy(load(plane))
