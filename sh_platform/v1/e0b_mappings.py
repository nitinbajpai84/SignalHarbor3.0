"""E0b2 mapping records: how one kind of sheet maps column by column onto the data model.

One JSON file per version in `data/<company>/model/mappings/<id>.json`:
  {id, file_pattern, sheet, header_row, version, purpose, layout: [source column], columns: [{source, target_table, target_field, transform}],
   state: proposed|approved|rejected|retired, proposed_by: {kind: agent|person, name, account_id}, owner, approved_by, approved_at, ...}
A layout change (different columns for the same file pattern and sheet) saves as the next version; old batches keep the version they used.
Approve or reject: the sheet owner or the data engineer seat, never the proposer when the proposer is a person.
"""
from __future__ import annotations

import fnmatch
import re
import secrets
from datetime import datetime, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.seats import DATA_ENGINEER, REFUSAL, seat_of

STATES = ("proposed", "approved", "rejected", "retired")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dir(plane):
    d = plane.path("model", "mappings")
    d.mkdir(parents=True, exist_ok=True)
    return d


def pattern_of(file_name: str) -> str:
    """'pos_2026_09_custodian.xlsx' -> 'pos_*_*_custodian.xlsx': every run of digits becomes a star."""
    return re.sub(r"\d+", "*", str(file_name).strip())


def _sheet_key(name) -> str:
    """A CSV sheet is named after its file, so month digits are masked like in the file pattern: bank_2026-07 and bank_2026-08 are one sheet."""
    return re.sub(r"\d+", "*", col_key(name))


def col_key(name) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(name).lower()).split())


def _load(plane, path) -> dict:
    try:
        return read_json_strict(path, dict)
    except (OSError, ValueError):
        raise Refused(500, "A mapping could not be read. Please try again.") from None


def _all(plane) -> list[dict]:
    rows = []
    for p in sorted(_dir(plane).glob("*.json")):
        try:
            rows.append(read_json_strict(p, dict))
        except (OSError, ValueError):
            continue  # one unreadable file never hides the others
    return rows


def _same_sheet(m: dict, pattern: str, sheet: str) -> bool:
    return m.get("file_pattern") == pattern and _sheet_key(m.get("sheet")) == _sheet_key(sheet)


def listing(plane, state: str | None = None) -> list[dict]:
    rows = [m for m in _all(plane) if not state or m.get("state") == state]
    return sorted(rows, key=lambda m: (m.get("file_pattern", ""), m.get("sheet", ""), m.get("version", 0)))


def get(plane, mapping_id: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]{4,64}", str(mapping_id)):
        raise Refused(404, "We could not find that mapping.")
    p = _dir(plane) / f"{mapping_id}.json"
    if not p.is_file():
        raise Refused(404, "We could not find that mapping.")
    return _load(plane, p)


def get_approved(plane, file_name: str, sheet: str) -> dict | None:
    """The newest approved mapping whose file pattern matches this file name and whose sheet is this sheet."""
    hits = [m for m in _all(plane) if m.get("state") == "approved" and _sheet_key(m.get("sheet")) == _sheet_key(sheet)
            and fnmatch.fnmatch(str(file_name).lower(), str(m.get("file_pattern", "")).lower())]
    return max(hits, key=lambda m: m.get("version", 0), default=None)


def _write(plane, m: dict) -> None:
    write_json_atomic(_dir(plane) / f"{m['id']}.json", m)


def save_proposal(plane, mapping: dict) -> str:
    """Store a proposed mapping and return its id. `mapping`: file_name, sheet, header_row, columns [{source, target_table, target_field,
    transform}], purpose?, owner?, proposed_by? ({kind, name, account_id}; default the data agent). Invented targets are refused."""
    from sh_platform.v1 import e0a_catalogue
    file_name, sheet = str(mapping.get("file_name") or ""), str(mapping.get("sheet") or "")
    cols = [dict(c) for c in mapping.get("columns") or []]
    if not file_name or not sheet or not cols:
        raise Refused(400, "A mapping needs a file name, a sheet and columns.")
    bad = [f"{c.get('source')} -> {c.get('target_table')}.{c.get('target_field')}" for c in cols
           if c.get("target_table") and not e0a_catalogue.has_field(plane, c["target_table"], c.get("target_field", ""))]
    if bad:
        raise Refused(400, "These targets are not in the data model: " + "; ".join(bad) + ".")
    layout = [str(c["source"]) for c in cols]
    pat = mapping.get("file_pattern") or pattern_of(file_name)
    by = dict(mapping.get("proposed_by") or {"kind": "agent", "name": "Data agent", "account_id": None})
    with lock_for(_dir(plane) / "_lock"):
        older = [m for m in _all(plane) if _same_sheet(m, pat, sheet)]
        same = [m for m in older if [col_key(x) for x in m["layout"]] == [col_key(x) for x in layout]]
        waiting = next((m for m in same if m["state"] == "proposed"), None)
        if waiting:  # pressing Load again must not stack identical proposals (and must keep the engineer's edits on this one)
            return waiting["id"]
        version = 1 + max((m["version"] for m in older), default=0) if not same else max(m["version"] for m in same)
        mid = "map-" + secrets.token_hex(6)
        rec = {"id": mid, "file_pattern": pat, "example_file": file_name, "sheet": sheet, "header_row": mapping.get("header_row"),
               "version": version, "purpose": mapping.get("purpose", ""), "layout": layout, "columns": cols, "state": "proposed",
               "layout_change": bool(older) and not same, "proposed_by": by, "proposed_at": _now(), "owner": str(mapping.get("owner") or ""),
               "approved_by": None, "approved_at": None, "rejected_reason": None}
        _write(plane, rec)
    return mid


def _who_may_decide(viewer, m: dict, proposer_check: bool = True) -> None:
    owner = str(m.get("owner") or "").strip().lower()
    if DATA_ENGINEER not in seat_of(viewer) and not (owner and owner == str(viewer.name).strip().lower()):
        raise Refused(403, REFUSAL[DATA_ENGINEER])
    by = m.get("proposed_by") or {}
    if proposer_check and by.get("kind") == "person" and (by.get("account_id") == getattr(viewer, "account_id", None) or by.get("name") == viewer.name):
        raise Refused(403, "You proposed this mapping, so someone else has to approve it.")


def _decide(plane, mapping_id: str, viewer, state: str, reason: str = "") -> dict:
    with lock_for(_dir(plane) / "_lock"):
        m = get(plane, mapping_id)
        _who_may_decide(viewer, m)
        if state == "rejected" and m["state"] == "approved":  # UC5: a wrong approved mapping steps aside; the next load proposes a new one
            m.update(state="retired", retired_at=_now(), retired_by=viewer.name, rejected_reason=reason)
            _write(plane, m)
            return m
        if m["state"] != "proposed":
            raise Refused(409, f"This mapping is already {m['state']}.")
        m.update(state=state, decided_by=viewer.name, decided_at=_now())
        if state == "approved":
            m.update(approved_by=viewer.name, approved_at=m["decided_at"])
            for o in _all(plane):  # the earlier approved version steps aside; its batches keep it
                if o["id"] != m["id"] and o["state"] == "approved" and _same_sheet(o, m["file_pattern"], m["sheet"]):
                    _write(plane, {**o, "state": "retired", "retired_at": m["decided_at"]})
        else:
            m["rejected_reason"] = reason
        _write(plane, m)
    return m


def edit(plane, mapping_id: str, viewer, lines: list[dict], fixed: dict | None = None) -> dict:
    """The data engineer corrects a proposed mapping before approval. Each line: {source, target: 'table.field' | 'ignore', date_format?,
    multiply?, decimal?}. Only the lines sent change. Approval stores the corrected mapping, so the next file of this pattern loads with it. `fixed` {"table.field": value} gives every row of the file a value it
    does not carry (the portfolio of a bank file, say); kept with the mapping, and settable on an approved mapping too; columns may not change then."""
    from sh_platform.v1 import e0a_catalogue
    with lock_for(_dir(plane) / "_lock"):
        m = get(plane, mapping_id)
        _who_may_decide(viewer, m, proposer_check=False)
        if m["state"] != ("proposed" if lines else m["state"]) or m["state"] not in ("proposed", "approved"):
            raise Refused(409, f"This mapping is already {m['state']}, so it cannot be edited. Turn it down and a new one is proposed.")
        for key, val in (fixed or {}).items():
            t, _, f = str(key).partition(".")
            if not e0a_catalogue.has_field(plane, t, f) or not str(val).strip() or len(str(val)) > 80:
                raise Refused(400, f"{key} cannot be fixed to that value.")
            m["fixed"] = {**(m.get("fixed") or {}), key: str(val).strip()}
        by_src = {str(c["source"]): c for c in m["columns"]}
        for ln in lines:
            c = by_src.get(str(ln.get("source")))
            if c is None:
                raise Refused(400, f"{ln.get('source')} is not a column of this sheet.")
            t, _, f = str(ln.get("target") or "ignore").partition(".")
            if t in ("", "ignore"):
                c.update(target_table="", target_field="")
            elif e0a_catalogue.has_field(plane, t, f):
                c.update(target_table=t, target_field=f)
            else:
                raise Refused(400, f"{t}.{f} is not in the data model.")
            tr = dict(c["transform"]) if isinstance(c.get("transform"), dict) else {}
            for key in ("date_format", "multiply", "decimal"):
                if key not in ln:
                    continue
                v = ln[key]
                if v in (None, "", 0):
                    tr.pop(key, None)
                elif key == "multiply" and not re.fullmatch(r"\d+(\.\d+)?", str(v)):
                    raise Refused(400, "Multiply by needs a number.")
                elif key == "decimal" and v not in (".", ","):
                    raise Refused(400, "The decimal mark is a point or a comma.")
                elif key == "date_format" and not re.fullmatch(r"[%A-Za-z0-9/.\- :]{2,30}", str(v)):
                    raise Refused(400, "That date format is not one we can read. Example: %Y-%m-%d or %d/%m/%Y.")
                else:
                    tr[key] = float(v) if key == "multiply" and "." in str(v) else int(v) if key == "multiply" else v
            c["transform"] = tr or None
        m.update(edited_by=viewer.name, edited_at=_now())
        _write(plane, m)
    return m


def approve(plane, mapping_id: str, viewer) -> dict:
    return _decide(plane, mapping_id, viewer, "approved")


def reject(plane, mapping_id: str, viewer, reason: str) -> dict:
    if not str(reason or "").strip():
        raise Refused(400, "Say why this mapping is not right.")
    return _decide(plane, mapping_id, viewer, "rejected", str(reason).strip()[:500])
