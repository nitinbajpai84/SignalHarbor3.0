"""E0c1 landing zone and census: originals kept untouched, one record per file, and the state each file is in.

Layout in the company plane:
  landing/inbox/[source_code/]<file>          where people drop files (scanned, never modified or moved)
  landing/originals/<sha256>__<name>          the untouched copy (never rewritten)
  landing/records/<file_id>.json              {file_id, sha256, name, size, received_at, sender, source_code, sensitivity, state, ...}

States: new, profiled, waiting_for_mapping, loaded, rejected_totals, quarantined. The same bytes are one file (hash).
Profiling goes through `e0b_tools.profile_sheet`, loading through `e0c_load.load`; both are imported lazily (cards build in parallel).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from sh_platform.v1 import wh

log = logging.getLogger(__name__)

STATES = ("new", "profiled", "waiting_for_mapping", "loaded", "nothing_loaded", "rejected_totals", "quarantined")
SPREADSHEETS = {".xlsx", ".xlsm", ".csv"}  # .csv is profiled and loaded by e0b_tools / e0c_load as one sheet named after the file
MAX_BYTES = 25 * 1024 * 1024
POLL_SECONDS = 60
_LOCK = threading.RLock()


class Refused(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _now() -> str:
    return wh.now().isoformat()


def _dirs(plane) -> tuple[Path, Path, Path]:
    inbox, originals, records = (plane.path("landing", d) for d in ("inbox", "originals", "records"))
    for d in (inbox, originals, records):
        d.mkdir(parents=True, exist_ok=True)
    return inbox, originals, records


def _clean_name(name: str) -> str:
    base = re.split(r"[\\/]", str(name or ""))[-1].strip()
    base = re.sub(r"[^\w.\- ()]+", "_", base).strip(". ") or "file"
    return base[:120]


def _save(plane, rec: dict) -> dict:
    _, _, records = _dirs(plane)
    p = records / f"{rec['file_id']}.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    tmp.replace(p)
    return rec


def _all(plane) -> list[dict]:
    _, _, records = _dirs(plane)
    out = []
    for p in records.glob("*.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            log.warning("landing record unreadable: %s", p.name)
    return sorted(out, key=lambda r: r.get("received_at", ""), reverse=True)


def by_hash(plane, sha: str) -> dict | None:
    return next((r for r in _all(plane) if r["sha256"] == sha), None)


def get(plane, file_id: str) -> dict:
    if not re.fullmatch(r"[0-9a-f-]{36}", str(file_id)):
        raise Refused("We could not find that file.", 404)
    _, _, records = _dirs(plane)
    p = records / f"{file_id}.json"
    if not p.is_file():
        raise Refused("We could not find that file.", 404)
    return json.loads(p.read_text(encoding="utf-8"))


def original_path(plane, rec: dict) -> Path:
    return plane.path("landing", "originals", f"{rec['sha256']}__{rec['name']}")


def receive(plane, data: bytes, name: str, sender: str, source_code: str = "upload", sensitivity: str = "internal", received_on: str | None = None) -> dict:
    """Keep the bytes untouched and add a record. Returns the record plus `duplicate` (True when the same bytes were here already).
    `received_on` (UC5): when the file really arrived (an ISO date or time, not in the future), so a check "as received by" a past day sees it;
    the upload time is kept beside it as `uploaded_at`."""
    arrived = _arrival(received_on)
    if not data:
        raise Refused("That file is empty.")
    if len(data) > MAX_BYTES:
        raise Refused(f"That file is too large. The limit is {MAX_BYTES // 1_000_000} MB.", 413)
    sha = hashlib.sha256(data).hexdigest()
    with _LOCK:
        known = by_hash(plane, sha)
        if known:
            return {**known, "duplicate": True}
        _, originals, _ = _dirs(plane)
        clean = _clean_name(name)
        dest = plane.path("landing", "originals", f"{sha}__{clean}")
        if not dest.exists():
            dest.write_bytes(data)
        quarantine = Path(clean).suffix.lower() not in SPREADSHEETS
        rec = {"file_id": wh.new_id(), "sha256": sha, "name": clean, "size": len(data), "received_at": arrived or _now(), "uploaded_at": _now(),
               "sender": sender, "owner": sender, "source_code": _clean_name(source_code) or "upload",
               "sensitivity": sensitivity, "state": "quarantined" if quarantine else "new",
               "note": "This kind of file cannot be read yet. It is kept as received." if quarantine else "",
               "profile": None, "last_load": None, "last_load_at": None}
        return {**_save(plane, rec), "duplicate": False}


def _arrival(value) -> str | None:
    """An ISO date (taken as 00:00 UTC) or time, not later than now; None when not given."""
    if value in (None, ""):
        return None
    try:
        t = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        raise Refused("Give the day the file arrived as YYYY-MM-DD, or a date and time.") from None
    t = t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    if t > wh.now():
        raise Refused("The day the file arrived cannot be in the future.")
    return t.isoformat()


def scan_inbox(plane) -> list[dict]:
    """Register files in landing/inbox that are not known yet. Idempotent. A sub-folder name is the source code."""
    inbox, _, _ = _dirs(plane)
    new = []
    for p in sorted(inbox.rglob("*")):
        if not p.is_file() or p.name.startswith(("~$", ".")) or p.suffix.lower() in (".tmp", ".part", ".crdownload"):
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue  # still being written; the next poll picks it up
        rel = p.relative_to(inbox).parts
        r = receive(plane, data, p.name, "Inbox folder", rel[0] if len(rel) > 1 else "inbox")
        if not r["duplicate"]:
            new.append(r)
    return new


def listing(plane) -> dict:
    """{files: [...], by_source: {source_code: [file...]}} with the state and owner of each."""
    files = [{**{k: v for k, v in r.items() if k != "profile"}, "id": r["file_id"]} for r in _all(plane)]
    groups: dict[str, list] = {}
    for f in files:
        groups.setdefault(f["source_code"], []).append(f)
    return {"files": files, "by_source": groups, "states": list(STATES),
            "inbox_note": "Drop files in the inbox folder or upload here"}


def _transform_words(tr) -> str | None:
    if not tr:
        return None
    if isinstance(tr, str):
        return tr
    parts = []
    if tr.get("multiply"):
        parts.append(f"times {tr['multiply']:,}" if isinstance(tr["multiply"], int) else f"times {tr['multiply']}")
    if tr.get("date_format"):
        parts.append(f"dates read as {tr['date_format']}")
    if tr.get("decimal") == ",":
        parts.append("comma as the decimal mark")
    return ", ".join(parts) or None


def _mapping_for(plane, rec: dict, viewer) -> dict | None:
    """The mapping the screen shows: the newest proposed one if it is at least as new as the approved one, else the approved one."""
    prof = rec.get("profile") or {}
    if not prof.get("sheet"):
        return None
    try:
        from sh_platform.v1 import e0b_mappings as M
    except ImportError:
        return None
    pat = M.pattern_of(rec["name"])
    mine = [m for m in M.listing(plane) if M._same_sheet(m, pat, prof["sheet"])]
    appr = max((m for m in mine if m.get("state") == "approved"), key=lambda m: m.get("version", 0), default=None)
    prop = max((m for m in mine if m.get("state") == "proposed"), key=lambda m: (m.get("version", 0), m.get("proposed_at", "")), default=None)
    m = prop if prop and (not appr or prop.get("version", 0) >= appr.get("version", 0)) else appr
    if not m:
        return None
    can = edit = fix = False
    if viewer is not None and m.get("state") in ("proposed", "approved"):
        try:
            M._who_may_decide(viewer, m, proposer_check=False)
            fix = True
        except Exception:  # a refusal means this person may not set a fixed value
            pass
    if viewer is not None and m.get("state") == "proposed":
        try:
            M._who_may_decide(viewer, m, proposer_check=False)
            edit = True
            M._who_may_decide(viewer, m)
            can = True
        except Exception:  # a refusal means this person may not edit or decide
            pass
    tr = lambda c: c.get("transform") if isinstance(c.get("transform"), dict) else {}  # noqa: E731
    return {"id": m["id"], "version": m.get("version", 1), "state": m["state"], "can_decide": can, "can_edit": edit, "can_fix": fix, "fixed": m.get("fixed") or {},
            "columns": [{"source_column": c.get("source") or c.get("source_column"), "target_table": c.get("target_table") or "ignore",
                         "target_field": c.get("target_field") or "", "transform": _transform_words(c.get("transform")),
                         "date_format": tr(c).get("date_format"), "multiply": tr(c).get("multiply"), "decimal": tr(c).get("decimal")}
                        for c in m.get("columns") or []]}


def _needs_approval(plane, last: dict, viewer) -> dict:
    """Funds and portfolios the last load could not place, minus the fund matches a person has decided since; and who may approve."""
    needs = last.get("needs_approval") or {}
    try:
        from sh_platform.v1 import e2_match
        waiting = {p["id"] for p in e2_match.proposals(plane)}
    except Exception:  # noqa: BLE001 - the page still shows the load result without the live check
        log.warning("could not read the waiting fund matches")
        waiting = None
    funds = [f for f in needs.get("funds") or [] if waiting is None or not f.get("identifier_id") or f["identifier_id"] in waiting]
    can = False
    if viewer is not None:
        from sh_platform.v1.seats import DATA_ENGINEER, OPS_MANAGER, seat_of
        can = bool(seat_of(viewer) & {DATA_ENGINEER, OPS_MANAGER})
    return {"funds": funds, "portfolios": needs.get("portfolios") or [],
            "choose_portfolio": needs.get("choose_portfolio") or [], "can_approve": can}


def target_options(plane) -> list[str]:
    """Every 'table.field' a mapping line may point at (where a sheet column can land), for the edit list."""
    from sh_platform.v1 import e0a_catalogue, e0c_load
    skip = ("id", "organization_id", "source_record_id", "recorded_at", "received_at", "as_of_at")
    tables, side = getattr(e0c_load, "_TABLES", {}), getattr(e0c_load, "_SIDE", set())
    own = {f"{t}.{c}" for t in tables for c in e0a_catalogue.columns_of(plane, t) or []
           if c not in skip and not c.startswith("supersedes_") and not c.endswith("_id")}
    return ["ignore", *sorted(own | {f"{t}.{f}" for t, f in side})]


def detail(plane, file_id: str, viewer=None) -> dict:
    """The record shaped for the file page: id, profile columns as {name, date_format}, the mapping with can_decide,
    control totals as {measure, in_file, loaded, passed}, load_result {state, message, held_back[]} and can_act."""
    rec = get(plane, file_id)
    out = {**rec, "id": rec["file_id"]}
    prof = rec.get("profile")
    if prof:
        info = prof.get("column_info") or [{"name": n} for n in prof.get("columns") or []]
        out["profile"] = {**prof, "columns": [{"name": c["name"], "date_format": c.get("date_format"), "kind": c.get("kind")} for c in info]}
    out["mapping"] = _mapping_for(plane, rec, viewer)
    last = rec.get("last_load") or {}
    out["control_totals"] = [{"measure": t["measure"], "in_file": t.get("expected", ""), "loaded": t.get("loaded", ""), "passed": bool(t.get("passed"))}
                             for t in last.get("control_totals") or []]
    out["load_result"] = None if not last else {
        "state": out["state"], "message": last.get("message", ""),
        "held_back": [f"row {h['row']}: {h['reason']}" for h in last.get("held_back") or []]}
    out["needs_approval"] = _needs_approval(plane, last, viewer)
    out["target_options"] = target_options(plane)
    out["can_act"] = False
    if viewer is not None:
        from sh_platform.v1.seats import DATA_ENGINEER, seat_of
        out["can_act"] = DATA_ENGINEER in seat_of(viewer)
    return out


def set_state(plane, file_id: str, state: str, **extra) -> dict:
    if state not in STATES:
        raise ValueError(state)
    with _LOCK:
        rec = get(plane, file_id)
        rec.update(extra, state=state)
        return _save(plane, rec)


def profile(plane, file_id: str, sheet: str | None = None) -> dict:
    rec = get(plane, file_id)
    if rec["state"] == "quarantined":
        raise Refused("This file is quarantined and cannot be read yet.", 409)
    try:
        from sh_platform.v1 import e0b_tools
    except ImportError:
        log.warning("e0b_tools is not installed; cannot profile %s", file_id)
        raise Refused("The data agent's tools are not ready yet.", 503) from None
    try:
        prof = e0b_tools.profile_sheet(str(original_path(plane, rec)), sheet)
    except Exception as e:  # an unreadable workbook is quarantined, never lost
        log.warning("profile failed for %s: %s", rec["name"], type(e).__name__)
        set_state(plane, file_id, "quarantined", note="We could not read this file. It is kept as received.")
        raise Refused("We could not read this file. It is kept as received.", 422) from None
    # a file already loaded or waiting keeps that state; a new one becomes profiled
    state = rec["state"] if rec["state"] in ("waiting_for_mapping", "loaded", "rejected_totals") else "profiled"
    return set_state(plane, file_id, state, profile=prof)


def _is_trade_file(name: str, data: bytes) -> bool:
    """True when the file's header is one of the trade layouts (the trading export or the administrator's trade confirmations)."""
    import tempfile
    from sh_platform.v1 import e0b_tools, trade_intake
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / _clean_name(name)
        p.write_bytes(data)
        try:
            return trade_intake._layout(e0b_tools.read_grid(p)[1]) is not None
        except Exception:  # noqa: BLE001 - a file we cannot read is not a trade file; the normal path quarantines it
            return False


def _source_of(name: str) -> str:
    """A source code for a file dropped with a month of others: its name without the month digits (bank_cash_EG-B_2026-07.csv -> bank_cash_EG-B)."""
    return re.sub(r"[\d_\-.]+$", "", re.sub(r"\d{2,4}[-_.]\d{1,2}([-_.]\d{1,2})?", "", Path(_clean_name(name)).stem)).strip("_- ") or "upload"


def load_month(plane, files: list[tuple[str, bytes]], viewer, model=None, mode: str = "replace") -> dict:
    """Load a month of files in one action. Trade files go through trade_intake.load_folder (per business date, `mode` replace | append);
    every other file lands and loads the normal per-file way, and may stop at 'waiting for mapping' for a person. {files: {name: result}}."""
    import tempfile
    from sh_platform.v1 import trade_intake
    out: dict[str, dict] = {}
    trades = [(n, b) for n, b in files if _is_trade_file(n, b)]
    others = [(n, b) for n, b in files if (n, b) not in trades]
    for name, data in sorted(others, key=lambda x: x[0]):
        try:
            rec = receive(plane, data, name, getattr(viewer, "name", "month"), source_code=_source_of(name))
            rec = profile(plane, rec["file_id"]) if rec["state"] == "new" else rec
            rec = load(plane, rec["file_id"], viewer, model) if rec["state"] != "quarantined" else rec
            last = rec.get("last_load") or {}
            out[name] = {"file_id": rec["file_id"], "state": rec["state"], "message": last.get("message") or rec.get("note") or ""}
        except Refused as e:
            out[name] = {"file_id": None, "state": "refused", "message": e.message}
    if trades:
        with tempfile.TemporaryDirectory(dir=plane.path("landing")) as d:
            for name, data in trades:
                (Path(d) / _clean_name(name)).write_bytes(data)
            for name, res in trade_intake.load_folder(plane, d, viewer, mode=mode, sender=getattr(viewer, "name", "month")).items():
                out[name] = {"file_id": res.get("file_id"), "state": res.get("status"), "message": res.get("message") or ""}
    return {"files": dict(sorted(out.items())), "trade_files": len(trades), "other_files": len(others)}


_LOAD_STATES = {"loaded": "loaded", "already_loaded": "loaded", "waiting_for_mapping": "waiting_for_mapping", "rejected_totals": "rejected_totals",
                "quarantined": "quarantined", "layout_changed": "waiting_for_mapping", "nothing_loaded": "nothing_loaded"}


ALL_SHEETS = "*"
_STATUS_ORDER = ("quarantined", "rejected_totals", "waiting_for_mapping", "nothing_loaded", "loaded", "already_loaded")


def sheet_names(path: Path) -> list[str]:
    """The workbook's sheets, in order; a CSV or a file openpyxl cannot read is one unnamed sheet."""
    try:
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True)
        try:
            return list(wb.sheetnames)
        finally:
            wb.close()
    except Exception:  # noqa: BLE001 - not a workbook: the default sheet
        return [None]


def load(plane, file_id: str, viewer, model=None, sheet: str | None = None) -> dict:
    rec = get(plane, file_id)
    if rec["state"] == "quarantined":
        raise Refused("This file is quarantined and cannot be loaded.", 409)
    try:
        from sh_platform.v1 import e0c_load
    except ImportError:
        log.warning("e0c_load is not installed; cannot load %s", file_id)
        raise Refused("The load engine is not ready yet.", 503) from None
    if sheet == ALL_SHEETS:  # UC5: every sheet of the workbook in one step, each with its own mapping; the worst status is the file's
        per = {s: e0c_load.load(plane, file_id, viewer, model=model, sheet=s) for s in sheet_names(original_path(plane, rec))}
        worst = next((r for s in _STATUS_ORDER for r in per.values() if r.get("status") == s), next(iter(per.values()), {}))
        result = {**worst, "sheets": per, "message": " ".join(f"{s}: {r.get('message') or r.get('status')}" for s, r in per.items())}
    else:
        result = e0c_load.load(plane, file_id, viewer, model=model, sheet=sheet) if model is not None or sheet else e0c_load.load(plane, file_id, viewer)
    state = _LOAD_STATES.get(str((result or {}).get("status")), rec["state"])
    return set_state(plane, file_id, state, last_load=result, last_load_at=_now())


# --- light background poll: one daemon thread per started plane, every POLL_SECONDS while the server runs ----------------------

_POLLS: dict[str, threading.Event] = {}


def ensure_poll(plane, interval: float = POLL_SECONDS) -> None:
    key = str(plane.root)
    with _LOCK:
        if key in _POLLS and not _POLLS[key].is_set():
            return
        stop = _POLLS[key] = threading.Event()

    def run():
        while not stop.wait(interval):
            try:
                scan_inbox(plane)
            except Exception:  # the poll must never die
                log.exception("inbox scan failed")
            try:  # W2-connectors mount line 5: scheduled connectors fetch on the same poll
                from sh_platform.v1.c5_connect import ops as C5
                C5.run_due(plane)
            except Exception:  # the poll must never die
                log.exception("connector run failed")
    threading.Thread(target=run, name=f"landing-poll-{plane.company_id}", daemon=True).start()


def stop_polls() -> None:
    with _LOCK:
        for e in _POLLS.values():
            e.set()
        _POLLS.clear()
