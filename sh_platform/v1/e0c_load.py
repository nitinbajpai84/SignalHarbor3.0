"""E0c2: load a landed spreadsheet into the warehouse, only when it adds up.

`load(plane, file_id, viewer)` applies the approved mapping, writes source_batches, source_records (with sheet, row and
cell locators) and batch_control_totals, then the observation rows through `e1_write.record_many` (one transaction).
Control totals are checked on the parsed rows BEFORE any observation row is written, so a mismatch leaves the
observation tables untouched. Unknown fund names are held back (listed in the result), the rest of the file loads.

The batch row keeps the mapping it used as JSON in validation_summary ({mapping_id, mapping_version, message}) because the
warehouse sheet_mappings table is not written yet. A retry after a rejected attempt keeps the earlier batch and adds a new one (reference + '#n').
Returned `status`: loaded | waiting_for_mapping (reason: no_mapping | layout_changed) | rejected_totals | quarantined | already_loaded.
The caller (E0c1) turns the status into the census state; this module never touches the file record.

Other cards (imported lazily, see V2-CARDS.md fact 4): e0c_landing.get / original_path, e0b_mappings.get_approved / save_proposal,
e0b_tools.profile_sheet / propose_mapping, e2_match.resolve, e1_write.record_many.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from openpyxl.utils import get_column_letter

from sh_platform.v1 import wh

log = logging.getLogger(__name__)
TOLERANCE = Decimal("0.01")
GROUP_TOTALS, GROUP_COLUMN = "__group_totals__", "__group_column__"  # a totals block under the data: {group: {column: value}}

# observation table -> (subject key columns for supersession, supersedes column)
_TABLES = {
    "position_snapshots": (("portfolio_id", "instrument_id", "position_date", "view_type"), "supersedes_position_id"),
    "valuation_observations": (("instrument_id", "portfolio_id", "valuation_date"), "supersedes_valuation_id"),
    "cash_movements": ((), None),  # each movement is its own fact
    "nav_snapshots": (("portfolio_id", "nav_period_end"), "supersedes_nav_id"),
    "market_observations": (("series_key", "observed_at"), "supersedes_observation_id"),
    "commitments": (("legal_entity_id", "instrument_id"), "supersedes_commitment_id"),
    "fx_confirmations": (("trade_reference",), "supersedes_fx_confirmation_id"),  # v3 A1: a re-issued confirmation supersedes the one before
    "real_assets": (("asset_ref",), "supersedes_real_asset_id"),  # v3 A36: a newer appraisal of an asset supersedes the one before
}
_REQUIRED_DATE = {"position_snapshots": "position_date", "valuation_observations": "valuation_date", "cash_movements": "effective_date", "nav_snapshots": "nav_period_end", "fx_confirmations": "trade_date"}
_NEEDS_PORTFOLIO = {"position_snapshots", "cash_movements", "nav_snapshots"}
_NEEDS_INSTRUMENT = {"position_snapshots", "valuation_observations", "commitments"}
_DATE_FIELDS = {"position_date", "valuation_date", "effective_date", "nav_period_end", "committed_on", "trade_date", "value_date"}
_STAMP_FIELDS = {"observed_at", "as_of_at"}
_NUMERIC = {"quantity", "source_market_value", "value_amount", "amount", "nav_amount", "value", "commitment_amount", "debit", "credit", "amount_bought", "amount_sold", "rate"}
_SIDE = {("instruments", "canonical_name"), ("instrument_identifiers", "identifier_value"), ("portfolios", "portfolio_code"), ("legal_entities", "entity_code")}


def _mod(name: str):
    try:
        return importlib.import_module(f"sh_platform.v1.{name}")
    except ImportError:
        log.warning("E0c2 needs sh_platform.v1.%s, which is not available", name)
        raise


# ---- mapping and cell handling -------------------------------------------------------------------------------------

def _columns(mapping: dict) -> dict[str, dict]:
    """Normalise to {source column: {"table", "field", "transform"}}; accepts a list of records or {src: "t.f" | {target, transform}}."""
    cols = mapping.get("columns") or {}
    out: dict[str, dict] = {}
    items = cols.items() if isinstance(cols, dict) else [(c.get("source") or c.get("source_column"), c) for c in cols]
    for src, c in items:
        if isinstance(c, str):
            c = {"target": c}
        if "target" in c:
            tgt = c["target"]
            t, _, f = tgt.partition(".") if tgt != "ignore" else ("ignore", "", "")
        else:
            t, f = c.get("target_table") or "ignore", c.get("target_field") or ""
        out[str(src).strip()] = {"table": t, "field": f, "transform": c.get("transform") or c.get("transform_rule")}
    return out


def _num(v: Any, tr: Any = None) -> Decimal | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v))
    text = str(v).strip()
    if isinstance(tr, dict) and tr.get("decimal") == ",":
        text = text.replace(".", "").replace(" ", "").replace(",", ".")
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


def _factor(tr: Any) -> Decimal | None:
    if isinstance(tr, dict):
        return Decimal(str(tr["multiply"])) if tr.get("multiply") else None
    if isinstance(tr, str) and ("thousand" in tr.lower() or "multiply 1000" in tr.lower()):
        return Decimal(1000)
    return None


def _date_format(tr: Any) -> str | None:
    if isinstance(tr, dict):
        return tr.get("date_format")
    if isinstance(tr, str) and "date" in tr.lower():
        f = tr.lower().split("date", 1)[1].strip()
        return f if "%" in f else f.replace("yyyy", "%Y").replace("dd", "%d").replace("mm", "%m")
    return None


def _convert(v: Any, field: str, tr: Any) -> Any:
    if v is None or v == "":
        return None
    if field in _DATE_FIELDS or field in _STAMP_FIELDS:
        if isinstance(v, datetime):
            d = v
        elif isinstance(v, date):
            d = datetime(v.year, v.month, v.day)
        else:
            fmt = _date_format(tr)
            if not fmt:
                try:  # an ISO date (2026-07-31) is unambiguous and needs no format
                    d = datetime.fromisoformat(str(v).strip())
                except ValueError:
                    raise ValueError(f"text date {v!r} needs a date format in the mapping") from None
            else:
                d = datetime.strptime(str(v).strip(), fmt)
        return d if field in _STAMP_FIELDS else d.date()
    if field in _NUMERIC:
        n = _num(v, tr)
        if n is None:
            raise ValueError(f"{v!r} is not a number")
        f = _factor(tr)
        return n * f if f else n
    return str(v).strip()


def _read(path: Path, sheet: str | None, header_row: int, cols: dict[str, dict]):
    """-> (sheet name, file columns, data rows [(row number, {col: raw}, (first col idx, last col idx))], totals row {col: raw} | None).
    Excel and CSV go through the same reader as the profile (`e0b_tools.read_grid`)."""
    title, grid = _mod("e0b_tools").read_grid(path, sheet)
    cell = lambda r, i: (grid[r - 1][i - 1] if r <= len(grid) and i <= len(grid[r - 1]) else None)  # noqa: E731 - 1-based like Excel
    heads = {i: str(c).strip() for i, c in enumerate(grid[header_row - 1] if header_row <= len(grid) else [], 1) if c not in (None, "")}
    rows, totals, block, gap = [], None, None, False
    for r in range(header_row + 1, len(grid) + 1):
        vals = {h: cell(r, i) for i, h in heads.items()}
        if all(v in (None, "") for v in vals.values()):
            gap = bool(rows)
            continue
        first = next((v for v in (cell(r, i) for i in sorted(heads)) if v not in (None, "")), None)
        if gap and block is None and not (isinstance(first, str) and "total" in first.strip().lower()):
            break  # the table ends at its first blank row: the notes below it ("Rows: 29 ...", "Closing balance at period end") are not data (as the profile reads it)
        if block is not None:  # UC5: under a totals block every row is one group's stated total, never a data row
            if first not in (None, ""):
                block[str(first).strip()] = {h: v for h, v in vals.items() if v not in (None, "") and h != heads[min(heads)]}
            continue
        if isinstance(first, str) and "total" in first.strip().lower() and sum(v not in (None, "") for v in vals.values()) <= 1:
            block = {}  # "Portfolio totals (USD)" with no figures beside it: the data ended above it
            continue
        if isinstance(first, str) and first.strip().lower().startswith("total"):
            totals = vals
            continue
        rows.append((r, vals, (min(heads), max(heads))))
    if block:
        totals = {**(totals or {}), GROUP_TOTALS: block, GROUP_COLUMN: heads[min(heads)]}
    return title, list(heads.values()), rows, totals


# ---- warehouse helpers ---------------------------------------------------------------------------------------------

def _source_system(con, org: str, source_code: str) -> str:
    row = con.execute("select id from source_systems where organization_id = ? and source_code = ?", [org, source_code]).fetchone()
    if row:
        return row[0]
    sid = wh.new_id()
    con.execute(
        "insert into source_systems (id, organization_id, source_code, source_name, source_type, is_active) values (?, ?, ?, ?, 'spreadsheet', true)",
        [sid, org, source_code, source_code])
    return sid


def _previous(con, org: str, table: str, row: dict) -> str | None:
    keys, sup = _TABLES[table]
    if not keys:
        return None
    where = " and ".join(f"t.{k} is not distinct from ?" for k in keys)
    q = (f"select t.id from {table} t where t.organization_id = ? and {where} "
         f"and not exists (select 1 from {table} s where s.{sup} = t.id) order by t.recorded_at desc limit 1")
    r = con.execute(q, [org, *[row.get(k) for k in keys]]).fetchone()
    return r[0] if r else None


def _fmt(d: Decimal) -> str:
    return f"{d:,.2f}".rstrip("0").rstrip(".")


# ---- the load ------------------------------------------------------------------------------------------------------

def _file(plane, file_id: str) -> tuple[dict, Path]:
    landing = _mod("e0c_landing")
    rec = landing.get(plane, file_id)
    return rec, Path(landing.original_path(plane, rec))


def _ask_for_proposal(plane, viewer, rec: dict, profile: dict, reason: str, model=None) -> dict:
    """E0b2 versions the proposal itself: a different layout for a known pattern becomes the next version (layout_change)."""
    prop = _mod("e0b_tools").propose_mapping(plane, profile, viewer, model)
    pid = _mod("e0b_mappings").save_proposal(plane, {**prop["mapping"], "file_name": rec["name"], "owner": rec.get("owner")})
    msg = ("The columns in this file differ from the approved mapping. A new mapping has been proposed; nothing was loaded."
           if reason == "layout_changed" else "There is no approved mapping for this file yet. One has been proposed; nothing was loaded.")
    return {"status": "waiting_for_mapping", "reason": reason, "proposal_id": pid, "message": msg, "file_id": rec["file_id"]}


def _after_load(plane, source_code: str, sheet_name: str, file_cols: list[str]) -> None:
    """Tell the catalogue about the bronze table of this source layout (D1), then run the on-arrival plans that use the source (B4).
    The names follow Span's (b6_span): layout from the sheet, columns snake-cased. Never stops a load that has already succeeded."""
    try:
        from sh_platform.v1 import b6_schedule, b6_span, e0a_catalogue
        cols = [{"name": n, "type": "varchar"} for n in b6_span._snake(list(file_cols))]
        e0a_catalogue.register_bronze(plane, b6_span.slug(source_code, 24), b6_span.slug(sheet_name or "main", 24), cols, [])
        e0a_catalogue.refresh_aliases(plane)
        from sh_platform.jobs import handlers as H, queue  # W3: through the job queue (simple mode runs it here)
        queue().submit("b6.on_arrival", H.payload_of(plane, source_code=b6_span.slug(source_code, 24)))
    except Exception:  # noqa: BLE001 - the rows are in; the layer record and the schedule are conveniences
        log.exception("E0c2: bronze registration or on-arrival run failed for %s", source_code)


def load(plane, file_id: str, viewer, model=None, sheet: str | None = None) -> dict:
    """`sheet`: load that sheet of the workbook (default: the first), e.g. a second sheet of latest statements (UC5)."""
    out = _load(plane, file_id, viewer, model, sheet=sheet)
    from sh_platform.v1 import run_log
    cts = out.get("control_totals") or []
    ok = out.get("status") == "loaded"
    run_log.record(plane, "intake_load", "production", "manual", getattr(viewer, "name", None), [dict(
        name=str(file_id), layer="bronze", target=out.get("observation_table"), rows_in=(out.get("rows_loaded") or 0) + len(out.get("held_back") or []),
        inserted=out.get("rows_loaded") or 0, rejected=len(out.get("held_back") or []), checks_passed=sum(1 for c in cts if c.get("passed")),
        checks_failed=sum(1 for c in cts if not c.get("passed")), error=None if ok else out.get("message"), batch_id=out.get("batch_id"), file_id=file_id)],
        "ok" if ok else "failed")
    return out


def _load(plane, file_id: str, viewer, model=None, sheet: str | None = None) -> dict:
    """`model`: the router-wrapped client for columns the synonym rules miss (None = rules only)."""
    rec, path = _file(plane, file_id)
    name, sha = rec["name"], rec["sha256"]
    org, received = _mod("e1_write").org_id(plane), rec.get("received_at") or wh.now()
    if isinstance(received, str):
        received = datetime.fromisoformat(received)
    tools = _mod("e0b_tools")
    profile = tools.profile_sheet(path, sheet)
    sheet = profile.get("sheet")

    mapping = _mod("e0b_mappings").get_approved(plane, name, sheet)
    if not mapping:
        return _ask_for_proposal(plane, viewer, rec, profile, "no_mapping", model)
    cols = _columns(mapping)
    header_row = mapping.get("header_row") or profile.get("header_row") or 1
    sheet_name, file_cols, rows, totals = _read(path, sheet or mapping.get("sheet"), int(header_row), cols)
    if {c.lower() for c in file_cols} != {c.lower() for c in cols}:
        return _ask_for_proposal(plane, viewer, rec, profile, "layout_changed", model)
    if profile.get("status") == "in_progress":
        return {"status": "quarantined", "file_id": file_id, "message": "This sheet is marked In Progress, so it was not loaded. Ask the sender for the final version."}

    obs = next((c["table"] for c in cols.values() if c["table"] in _TABLES), None)
    if not obs:
        return {"status": "quarantined", "file_id": file_id, "message": "No column in the approved mapping points at a table that holds observations."}
    final = profile.get("status", "final") == "final"
    ref = f"{sha[:16]}:{sheet_name}"
    mver = mapping.get("version") or mapping.get("version_number")

    # parse every row (conversion errors quarantine the file; nothing is written)
    parsed = []
    called_col = called_at = None
    if obs == "commitments":  # UC6 G: the file's "Called to date" and its "As at" line are kept on the commitment (the rules path reads them)
        e0b = _mod("e0b_tools")
        called_col = next((h for h in file_cols if e0b.norm_header(h) == "called to date"), None)
        called_at = next((d for d in (_mod("k6_liquidity")._as_at(c) for g in e0b.read_grid(path, sheet_name)[1][:int(header_row)] for c in g if c is not None) if d), None)
    try:
        for r, raw, span in rows:
            f: dict[str, Any] = {}
            side: dict[str, Any] = {}
            for src, c in cols.items():
                if c["table"] == obs:
                    f[c["field"]] = _convert(raw.get(src), c["field"], c["transform"])
                elif (c["table"], c["field"]) in _SIDE:
                    side[f"{c['table']}.{c['field']}"] = raw.get(src)
            if called_col and (n := _num(raw.get(called_col))) is not None:
                f["called_to_date"], f["called_as_at"] = n, called_at
            for key, val in (mapping.get("fixed") or {}).items():  # a value set on the mapping for every row that has none (e.g. the portfolio)
                tbl, _, fld = key.partition(".")
                if tbl == obs and f.get(fld) in (None, ""):
                    f[fld] = _convert(val, fld, None)
                elif tbl != obs and side.get(key) in (None, ""):
                    side[key] = val
            parsed.append((r, raw, span, f, side))
    except (ValueError, KeyError) as e:
        return {"status": "quarantined", "file_id": file_id, "message": f"A cell could not be read: {e}. Nothing was loaded."}

    # control totals: the file's own count and stated totals against what we parsed
    measures: list[dict] = []
    first = int(header_row) + 1
    n_expected = profile.get("row_count", len(parsed))
    measures.append({"measure": "Row count", "expected": Decimal(n_expected), "loaded": Decimal(len(parsed))})
    stated_in_file = (profile.get("totals") or {}).get("stated") or totals or {}
    if stated_in_file:
        for src, c in cols.items():
            if c["table"] == obs and c["field"] in _NUMERIC and (stated := _num(stated_in_file.get(src))) is not None:
                f_ = _factor(c["transform"])
                measures.append({"measure": f"Total of {src}", "expected": stated * f_ if f_ else stated,
                                 "loaded": sum((p[3].get(c["field"]) or Decimal(0) for p in parsed), Decimal(0))})
    groups, gcol = (totals or {}).get(GROUP_TOTALS) or {}, (totals or {}).get(GROUP_COLUMN)
    for group, stated_row in groups.items():  # UC5: each group's stated total (e.g. a portfolio's footer) against the rows of that group
        for src, c in cols.items():
            if c["table"] == obs and c["field"] in _NUMERIC and (stated := _num(stated_row.get(src))) is not None:
                f_ = _factor(c["transform"])
                mine = [p for p in parsed if str(p[1].get(gcol) or "").strip() == group]
                measures.append({"measure": f"Total of {src} for {group}", "expected": stated * f_ if f_ else stated,
                                 "loaded": sum((p[3].get(c["field"]) or Decimal(0) for p in mine), Decimal(0))})
    for m in measures:
        m["tolerance"] = TOLERANCE
        m["passed"] = abs(m["expected"] - m["loaded"]) <= TOLERANCE
    bad = [m for m in measures if not m["passed"]]

    with wh.connect(plane) as con:
        sid = _source_system(con, org, rec.get("source_code") or "spreadsheet")
        # idempotent: rows of this file that an earlier load already wrote stay as they are; a load again writes only the rest
        done = {int(x[0]) for x in con.execute(
            "select r.row_number from source_records r join source_batches b on b.id = r.source_batch_id where b.source_system_id = ? "
            "and (b.batch_reference = ? or b.batch_reference like ?) and r.quality_status = 'loaded'", [sid, ref, ref + "#%"]).fetchall()}
        done &= {p[0] for p in parsed}
        if parsed and len(done) == len(parsed):
            return {"status": "already_loaded", "file_id": file_id, "message": "This file was already loaded."}
        tries = con.execute("select count(*) from source_batches where source_system_id = ? and (batch_reference = ? or batch_reference like ?)",
                            [sid, ref, ref + "#%"]).fetchone()[0]
        if tries:  # a retry after a rejected or quarantined attempt keeps the earlier batch and its totals as history
            ref = f"{ref}#{tries + 1}"
        batch = wh.new_id()
        summary = json.dumps({"mapping_id": mapping.get("id"), "mapping_version": mver, "message": "Row count and totals match the file."})
        if bad:
            m = bad[0]
            summary = (f"{m['measure']}: the file says {_fmt(m['expected'])} but the rows add up to {_fmt(m['loaded'])}. Nothing was loaded.")
        con.execute("insert into source_batches (id, organization_id, source_system_id, sheet_mapping_id, batch_reference, received_at, loaded_at, "
                    "content_hash, storage_uri, validation_status, validation_summary) values (?,?,?,?,?,?,?,?,?,?,?)",
                    [batch, org, sid, None, ref, received, None if bad else wh.now(), sha, path.as_uri(),
                     "rejected_totals" if bad else "loaded", summary])
        for m in measures:
            con.execute("insert into batch_control_totals (id, organization_id, source_batch_id, measure_name, expected_value, loaded_value, tolerance, passed) "
                        "values (?,?,?,?,?,?,?,?)", [wh.new_id(), org, batch, m["measure"], m["expected"], m["loaded"], m["tolerance"], m["passed"]])
        result = {"file_id": file_id, "batch_id": batch, "mapping_id": mapping.get("id"), "mapping_version": mver,
                  "control_totals": [{"measure": m["measure"], "expected": str(m["expected"]), "loaded": str(m["loaded"]), "passed": m["passed"]} for m in measures]}
        if bad:
            return {**result, "status": "rejected_totals", "message": summary, "rows_loaded": 0, "held_back": []}

        # resolve instruments and portfolios, set locators, build the rows
        match = _mod("e2_match")
        pf = {r[0].strip().lower(): r[1] for r in con.execute("select portfolio_code, id from portfolios where organization_id = ?", [org]).fetchall()}
        ent = {r[0].strip().lower(): r[1] for r in con.execute("select entity_code, id from legal_entities where organization_id = ?", [org]).fetchall()}
        by_ent: dict[str, list] = {}
        codes_by_ent: dict[str, list] = {}
        for pid, eid, pcode in con.execute("select id, legal_entity_id, portfolio_code from portfolios where organization_id = ? order by portfolio_code", [org]).fetchall():
            by_ent.setdefault(str(eid), []).append(pid)
            codes_by_ent.setdefault(str(eid), []).append(pcode)
        choose: dict[str, list] = {}  # entity code -> its portfolio codes, when the file does not say which one
        cash_ids = con.execute("select id, currency from instruments where organization_id = ? and instrument_type = 'cash' order by canonical_name", [org]).fetchall()
        funds_wait: dict[str, dict] = {}  # fund names that need a person's approval (shown on the file page)
        ports_wait: set[str] = set()
        held, obs_rows, supers = [], [], []
        sheet_account = _heading_account(path, sheet_name)
        now = wh.now()
        for r, raw, (c0, c1), f, side in parsed:
            if r in done:
                continue
            rid = wh.new_id()
            reason = None
            row = dict(f)
            if obs == "cash_movements":
                dr, cr = row.pop("debit", None), row.pop("credit", None)
                if row.get("amount") is None and (dr is not None or cr is not None):  # Debit/Credit columns: the statement's signed convention, money in positive, out negative
                    row["amount"] = (cr or Decimal(0)) - (dr or Decimal(0))
            labels = [side[k] for k in ("instrument_identifiers.identifier_value", "instruments.canonical_name") if side.get(k) not in (None, "")]
            tried = []
            for label in labels:
                res = match.resolve(plane, str(label).strip(), sid)
                if res.get("status") == "approved" and res.get("instrument_id"):
                    row["instrument_id"], reason = res["instrument_id"], None
                    break
                reason = f"{label}: name not yet approved ({res.get('status', 'unknown')})"
                tried.append((str(label).strip(), res))
            if "instrument_id" not in row and not labels and obs == "position_snapshots" and cash_ids:  # a cash report names no fund: it is the cash instrument
                row["instrument_id"] = next((i for i, c in cash_ids if c == f.get("currency")), cash_ids[0][0])
            if "instrument_id" not in row:
                for label, res in [t for t in tried if t[1].get("identifier_id")] or tried:  # a code with no match is noise next to a name with one
                    funds_wait.setdefault(label, {"name": label, "identifier_id": res.get("identifier_id"), "status": res.get("status", "unknown"),
                                                  "candidates": [c["name"] for c in res.get("candidates") or []][:3]})
                if labels or obs in _NEEDS_INSTRUMENT:
                    reason = reason or "no fund name or code in the row"
            code, ecode = side.get("portfolios.portfolio_code"), side.get("legal_entities.entity_code")
            if obs == "commitments":
                if str(ecode or "").strip().lower() in ent:
                    row["legal_entity_id"] = ent[str(ecode).strip().lower()]
                else:
                    reason = reason or f"{ecode or 'no legal entity'}: legal entity not known"
            elif code not in (None, ""):
                if str(code).strip().lower() in pf:
                    row["portfolio_id"] = pf[str(code).strip().lower()]
                else:
                    ports_wait.add(str(code).strip())
                    reason = reason or f"{code}: portfolio not approved yet (not in the company's master data)"
            elif ecode not in (None, "") and len(by_ent.get(str(ent.get(str(ecode).strip().lower())), [])) == 1:
                row["portfolio_id"] = by_ent[str(ent[str(ecode).strip().lower()])][0]  # the entity's only portfolio
            elif obs in _NEEDS_PORTFOLIO and sheet_account in pf:
                row["portfolio_id"] = pf[sheet_account]  # the statement's own heading names the account ("Account number: X"), the rows do not
            elif obs in _NEEDS_PORTFOLIO:
                if ecode not in (None, "") and str(ecode).strip().lower() in ent:
                    choose[str(ecode).strip()] = codes_by_ent.get(str(ent[str(ecode).strip().lower()]), [])
                reason = reason or ("no portfolio in the row" if ecode in (None, "") else
                                    f"{ecode}: more than one portfolio. Choose one for the whole file on the file page")
            if (need := _REQUIRED_DATE.get(obs)) and row.get(need) in (None, "") and not reason:  # a row with no date (a value "not received") is held back and named, never the whole file
                reason = f"no {need.replace('_', ' ')} in the row"
            if obs == "cash_movements" and row.get("amount") is None and not reason:  # an opening-balance line carries no movement: held back, named
                reason = "no amount in the row (no debit, credit or amount value)"
            if obs == "valuation_observations":
                row.setdefault("valuation_type", "manager_estimate"); row.setdefault("approval_status", "unapproved")
            elif obs == "position_snapshots":
                row.setdefault("view_type", "operational"); row.setdefault("data_status", "official" if final else "estimated")
                row.setdefault("as_of_at", datetime.combine(row["position_date"], datetime.min.time()) if row.get("position_date") else None)
            elif obs == "cash_movements":
                row.setdefault("confirmation_status", "noticed"); row.setdefault("movement_type", "bank_movement")
            elif obs == "nav_snapshots":
                row.setdefault("nav_status", "approved_official" if final else "draft")
            elif obs == "market_observations":
                if (pair := re.fullmatch(r"([A-Z]{3})\s*/\s*([A-Z]{3})", str(row.get("series_key") or "").strip())):  # USD/SGD: an FX rate, base/quote from the pair
                    row.setdefault("observation_type", "fx"); row.setdefault("base_currency", pair[1]); row.setdefault("quote_currency", pair[2])
                row.setdefault("observation_type", "index_level"); row.setdefault("quality_status", "loaded")
            row["source_record_id"] = rid
            if obs != "commitments":
                row["received_at"] = received
            eff = next((v for k, v in f.items() if k in _DATE_FIELDS | {"observed_at"}), None)
            con.execute(
                "insert into source_records (id, organization_id, source_batch_id, external_record_id, record_type, effective_at, received_at, recorded_at, "
                "sheet_name, row_number, cell_range, raw_payload_uri, content_hash, quality_status) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [rid, org, batch, f"{sheet_name}!{r}", obs, eff, received, now, sheet_name, r,
                 f"{get_column_letter(c0)}{r}:{get_column_letter(c1)}{r}", path.as_uri(),
                 hashlib.sha256(json.dumps(raw, default=str, sort_keys=True).encode()).hexdigest(), "held_back" if reason else "loaded"])
            if reason:
                held.append({"row": r, "reason": reason})
            else:
                obs_rows.append(row)
                supers.append(_previous(con, org, obs, row))

    try:  # one transaction in e1_write; all or nothing
        ids = _mod("e1_write").record_many(plane, obs, obs_rows, supers) if obs_rows else []
    except Exception as e:  # noqa: BLE001 - the batch must not stay marked loaded
        log.exception("E0c2: writing observations failed for %s", file_id)
        with wh.connect(plane) as con:
            con.execute("update source_batches set validation_status = 'quarantined', validation_summary = ? where id = ?", [f"Writing failed: {e}", batch])
            con.execute("update source_records set quality_status = 'quarantined' where source_batch_id = ?", [batch])
        return {**result, "status": "quarantined", "message": f"Writing the rows failed ({e}). Nothing was loaded.", "rows_loaded": 0, "held_back": held}
    needs = {"funds": sorted(funds_wait.values(), key=lambda x: x["name"]), "portfolios": sorted(ports_wait),
             "choose_portfolio": [{"entity": e, "options": o} for e, o in sorted(choose.items())]}
    result["needs_approval"] = needs
    # honest result: what was written, not what was parsed. A file with no rows written is never "loaded".
    with wh.connect(plane) as con:
        todo = len(parsed) - len(done)
        ok = len(ids) == todo and bool(ids)
        con.execute("insert into batch_control_totals (id, organization_id, source_batch_id, measure_name, expected_value, loaded_value, tolerance, passed) "
                    "values (?,?,?,?,?,?,?,?)", [wh.new_id(), org, batch, "Rows written", Decimal(todo), Decimal(len(ids)), Decimal(0), ok])
        if not ids:
            con.execute("update source_batches set validation_status = 'nothing_loaded', loaded_at = null where id = ?", [batch])
    result["control_totals"].append({"measure": "Rows written", "expected": str(todo), "loaded": str(len(ids)), "passed": ok})
    if not ids:
        why = ("The file has no data rows." if not parsed else f"All {len(held)} rows are held back" + (
            f": {len(needs['funds'])} fund name(s) and {len(needs['portfolios'])} portfolio code(s) need approval." if needs["funds"] or needs["portfolios"] else "."))
        return {**result, "status": "nothing_loaded", "message": f"Nothing was loaded. {why}", "rows_loaded": 0, "held_back": held, "observation_table": obs}
    msg = (f"Loaded {len(ids)} of {todo} rows." + (f" {len(done)} were already in from an earlier load." if done else "")
           + (f" {len(held)} held back: fund or portfolio not approved yet." if held else ""))
    _after_load(plane, rec.get("source_code") or "spreadsheet", sheet_name, file_cols)
    return {**result, "status": "loaded", "message": msg, "rows_loaded": len(ids), "held_back": held, "observation_table": obs}


_ACCOUNT_LINE = re.compile(r"^\s*(?:account\s*(?:number|no\.?|#)|acct\s*(?:no\.?|#)?)\s*[:\-]\s*(\S+)\s*$", re.I)


def _heading_account(path: Path, sheet: str | None) -> str | None:
    """The account a statement names above its table ("Account number: TCB-7730-210958"), lower-cased: on this sheet, else on a sibling sheet of the
    workbook (the transactions sheet of a bank statement has no heading; the balances sheet beside it does). None when none names one."""
    try:
        for name in [sheet, *[n for n in _mod("e0c_landing").sheet_names(path) if n != sheet]]:
            for row in _mod("e0b_tools").read_grid(path, name)[1][:15]:
                for c in row:
                    if isinstance(c, str) and (m := _ACCOUNT_LINE.match(c)):
                        return m[1].strip().lower()
    except Exception:  # noqa: BLE001 - no heading account: the rows are held back for a person, as before
        log.info("E0c2: could not read the heading of %s", path)
    return None


# ---- trade files (FIXB1): the trading export and the administrator's trade file go to trade_intake; every other file takes the path above ----
_load_sheet = _load


def _load(plane, file_id: str, viewer, model=None, sheet: str | None = None) -> dict:  # noqa: F811 - load() above resolves _load at call time
    rec, path = _file(plane, file_id)
    if (t := _mod("trade_intake").dispatch(plane, rec, path, viewer)):
        return t
    sheet, kept_out = _movement_sheet(plane, path, sheet)
    if kept_out:
        return {"status": "nothing_loaded", "file_id": file_id, "message": kept_out, "rows_loaded": 0, "held_back": []}
    return _load_sheet(plane, file_id, viewer, model, sheet=sheet)


def _movement_sheet(plane, path: Path, sheet: str | None) -> tuple[str | None, str | None]:
    """A workbook with a balances sheet and a transactions sheet (a bank statement): the movements come from the transactions. The default sheet
    becomes the transactions sheet; the balances sheet is kept out (loading its net movements too would count every movement twice) unless the
    model has a table for balances. -> (sheet to load, why a balances sheet is kept out | None)."""
    names = _mod("e0c_landing").sheet_names(path)
    trans = next((n for n in names if n and "transaction" in n.lower()), None)
    bal = [n for n in names if n and "balance" in n.lower()]
    if not trans or not bal or (sheet and sheet not in bal):
        return sheet, None
    if sheet is None:
        sheet = trans
    else:
        with wh.connect(plane, read_only=True) as con:
            home = [t for (t,) in con.execute("select table_name from information_schema.tables").fetchall() if "balance" in t and not t.startswith(("gold_", "silver_", "bronze_"))]
        if not home:
            return sheet, (f"The {sheet} sheet was not loaded: it holds balances, the data model has no table for balances yet (an open question for the data team), "
                           f"and the {trans} sheet already carries every movement.")
    return sheet, None
