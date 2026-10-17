"""Trade intake: the trading-system export (daily CSV) and the administrator's trade confirmations (monthly Excel) into silver `transactions`.

`e0c_load` hands a landed file here when its header row is one of the two trade layouts (`dispatch`); everything else goes the
normal spreadsheet way. The same intake tables are written as for any file: a source system (type OMS for the trading export,
administrator for the administrator file, which is what the trade check `e3_recon.trade_vs_admin` reads), one source_batch per
file with its control totals, one source_record per file row (sheet, row, cell range), and the `transactions` rows through
`e1_write.record_many`, each pointing at its source_record. file -> batch -> record -> silver row.

Per business date, `mode` (set on the landing record as `trade_mode`, default "replace"):
- replace: a trade id that is already there from this source is superseded by the new row; a trade of a date the file covers
  (the dates in its rows, the date in a daily file's name, the stated period of the administrator file) that the file no longer
  lists is superseded by a row with status "cancelled".
- append: only new trade ids are added; ids already there are kept and counted as `kept`.
An administrator "Amendment" row supersedes the latest row of that trade id and changes quantity, price and amount only.
Rows whose instrument or portfolio is not approved are held back (source_record quality "held_back"), the rest load.
Signs follow the seed: buy = +quantity, -cash; sell = -quantity, +cash; FX forward = -sold amount, +bought amount.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl.utils import get_column_letter

from sh_platform.v1 import wh

log = logging.getLogger(__name__)

# layout -> (source_code, source_type, header word that tells the layout, {file column (lower case): field})
_LAYOUTS = {
    "trading": ("trading_export", "OMS", "external_trade_id", {
        "external_trade_id": "tid", "trade_date": "trade_date", "settle_date": "settle", "portfolio": "portfolio", "side": "side",
        "instrument_code": "code", "isin": "isin", "instrument_name": "name", "quantity": "qty", "price": "price", "amount": "amount",
        "currency": "ccy", "status": "status"}),
    "administrator": ("administrator", "administrator", "client reference", {
        "client reference": "tid", "row type": "kind", "trade date": "trade_date", "settle date": "settle", "portfolio": "portfolio",
        "administrator code": "code", "security": "name", "buy/sell": "side", "quantity": "qty", "price": "price", "gross amount": "amount",
        "currency": "ccy", "status": "status"}),
}
_LABELS = {"trading": ("code", "isin", "name"), "administrator": ("code", "name")}
_KEEP = ("external_trade_id", "portfolio_id", "instrument_id", "transaction_type", "currency")


def _mod(name: str):
    return importlib.import_module(f"sh_platform.v1.{name}")


def _text(v) -> str:
    return "" if v is None else str(v).strip()


def _dec(v) -> Decimal | None:
    try:
        return Decimal(_text(v).replace(",", "")) if _text(v) else None
    except InvalidOperation:
        raise ValueError(f"{v!r} is not a number") from None


def _day(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(_text(v)[:10]) if _text(v) else None


# ---- reading the file --------------------------------------------------------------------------------------------------

def _layout(grid: list[list]) -> tuple[str, int] | None:
    """(layout, header row index) when one of the first ten rows is a trade header, else None."""
    for i, row in enumerate(grid[:10]):
        cells = {_text(c).lower() for c in row}
        for name, (_, _, word, _) in _LAYOUTS.items():
            if word in cells and {"currency", "quantity"} <= cells:
                return name, i
    return None


def _parse(grid: list[list], layout: str, hdr: int) -> dict:
    """Rows up to the first blank row, the stated footers {label: value} below it, and the period line (start, end) or None."""
    cols = _LAYOUTS[layout][3]
    head = {i: _text(c).lower() for i, c in enumerate(grid[hdr])}
    idx = {cols[h]: i for i, h in head.items() if h in cols}
    rows, i = [], hdr + 1
    while i < len(grid) and any(c not in (None, "") for c in grid[i]):
        g = grid[i]
        rows.append({"r": i + 1, "raw": {head[j]: g[j] for j in head if j < len(g) and head[j]}, "kind": "Trade",
                     **{f: (g[j] if j < len(g) else None) for f, j in idx.items()}})
        i += 1
    footers = {}
    for g in grid[i:]:
        vals = [c for c in g if c not in (None, "")]
        if len(vals) >= 2 and isinstance(vals[0], str):
            footers[vals[0].strip().lower()] = vals[-1]
    period = None
    for g in grid[:hdr]:
        m = re.search(r"period:\s*(\d{1,2} \w+ \d{4}) to (\d{1,2} \w+ \d{4})", _text(g[0] if g else ""), re.I)
        if m:
            period = tuple(datetime.strptime(x, "%d %B %Y").date() for x in m.groups())
    return {"rows": rows, "footers": footers, "period": period, "heads": [h for h in head.values() if h],
            "first_col": min(idx.values()) + 1, "last_col": max(idx.values()) + 1}


def dispatch(plane, rec: dict, path: Path, viewer) -> dict | None:
    """The hook in e0c_load: the load result when the file is a trade file, None when it is not (the normal path then runs)."""
    if path.suffix.lower() not in (".csv", ".xlsx", ".xlsm"):
        return None
    try:
        sheet, grid = _mod("e0b_tools").read_grid(path, None)
    except Exception:  # noqa: BLE001 - an unreadable file is not ours; the normal path reports it
        return None
    lay = _layout(grid)
    return _load(plane, rec, path, sheet, grid, *lay) if lay else None


# ---- the load ----------------------------------------------------------------------------------------------------------

def _system(con, org: str, layout: str) -> str:
    """The company's source system of this layout's type (trading export: OMS or trading), made when there is none."""
    code, typ, _, _ = _LAYOUTS[layout]
    r = con.execute("select id from source_systems where organization_id = ? and source_type in (?, ?) order by (source_code = ?) desc, source_code limit 1",
                    [org, typ, "trading" if typ == "OMS" else typ, code]).fetchone()
    if r:
        return r[0]
    sid = wh.new_id()
    con.execute("insert into source_systems (id, organization_id, source_code, source_name, source_type, connection_method, is_active) values (?,?,?,?,?,'file drop',true)",
                [sid, org, code, code.replace("_", " ").capitalize(), typ])
    return sid


def _scope(rec: dict, parsed: dict, trades: list[dict]) -> set[date]:
    """Business dates this file speaks for: its rows' dates, the date in a daily file's name, the stated period."""
    days = {r["_date"] for r in trades if r["_date"]}
    m = re.search(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)", rec["name"])
    if m:
        try:
            days.add(date(*map(int, m.groups())))
        except ValueError:
            pass
    if parsed["period"]:
        a, b = parsed["period"]
        days |= {a + timedelta(n) for n in range((b - a).days + 1)}
    return days


def _signed(itype: str | None, side: str, q: Decimal, amt: Decimal) -> tuple[Decimal, Decimal] | None:
    if itype == "fx_forward":
        return -q, amt
    fx = re.fullmatch(r"(buy|sell)\s+[a-z]{3}\s*/\s*(buy|sell)\s+[a-z]{3}", side)  # "sell usd / buy sgd": a currency trade, quantity = the first leg, amount = the second
    if fx and fx[1] != fx[2]:
        return (-q, amt) if fx[1] == "sell" else (q, -amt)
    s = {"buy": 1, "sell": -1}.get(side)
    return None if s is None else (s * q, -s * amt)


def _load(plane, rec: dict, path: Path, sheet: str, grid: list[list], layout: str, hdr: int) -> dict:
    fid, sha, mode = rec["file_id"], rec["sha256"], rec.get("trade_mode") or "replace"
    if mode not in ("replace", "append"):
        return {"status": "quarantined", "file_id": fid, "message": f"Unknown trade load mode {mode!r}: use replace or append. Nothing was loaded."}
    e1w, match = _mod("e1_write"), _mod("e2_match")
    org, received = e1w.org_id(plane), rec.get("received_at") or wh.now()
    if isinstance(received, str):
        received = datetime.fromisoformat(received)
    parsed = _parse(grid, layout, hdr)
    rows = parsed["rows"]
    try:
        for r in rows:
            r["_date"], r["_settle"] = _day(r.get("trade_date")), _day(r.get("settle"))
            r["_qty"], r["_price"], r["_amt"] = _dec(r.get("qty")), _dec(r.get("price")), _dec(r.get("amount"))
            r["kind"], r["_tid"] = _text(r.get("kind") or "Trade").title(), _text(r.get("tid"))
    except ValueError as e:
        return {"status": "quarantined", "file_id": fid, "message": f"A cell could not be read: {e}. Nothing was loaded."}
    trades = [r for r in rows if r["kind"] == "Trade"]

    # control totals: the administrator file states a trade count and a gross total per currency; the trading export states nothing
    measures = [{"measure": "Row count", "expected": Decimal(len(rows)), "loaded": Decimal(len(rows))}] if layout == "trading" else []
    for label, v in parsed["footers"].items():
        if label == "trade rows":
            measures.append({"measure": "Trade rows", "expected": _dec(v), "loaded": Decimal(len(trades))})
        elif (m := re.fullmatch(r"total gross amount, (\w+) trades", label)):
            ccy = m.group(1).upper()
            measures.append({"measure": f"Total gross amount, {ccy} trades", "expected": _dec(v),
                             "loaded": sum((r["_amt"] or 0 for r in trades if _text(r["ccy"]).upper() == ccy), Decimal(0))})
    for m in measures:
        m["tolerance"], m["passed"] = Decimal("0.01"), abs(m["expected"] - m["loaded"]) <= Decimal("0.01")
    bad = [m for m in measures if not m["passed"]]

    ref, now = f"{sha[:16]}:{sheet}", wh.now()
    with wh.connect(plane) as con:
        sid = _system(con, org, layout)
        if con.execute("select 1 from source_batches where source_system_id = ? and (batch_reference = ? or batch_reference like ?) and validation_status = 'loaded'",
                       [sid, ref, ref + "#%"]).fetchone():
            return {"status": "already_loaded", "file_id": fid, "message": "This file was already loaded."}
        tries = con.execute("select count(*) from source_batches where source_system_id = ? and (batch_reference = ? or batch_reference like ?)", [sid, ref, ref + "#%"]).fetchone()[0]
        ref = f"{ref}#{tries + 1}" if tries else ref
        batch = wh.new_id()
        summary = json.dumps({"layout": layout, "mode": mode, "message": "Row count and totals match the file."})
        if bad:
            m = bad[0]
            summary = f"{m['measure']}: the file says {m['expected']:,} but the rows add up to {m['loaded']:,}. Nothing was loaded."
        con.execute("insert into source_batches (id, organization_id, source_system_id, sheet_mapping_id, batch_reference, received_at, loaded_at, "
                    "content_hash, storage_uri, validation_status, validation_summary) values (?,?,?,?,?,?,?,?,?,?,?)",
                    [batch, org, sid, None, ref, received, None if bad else now, sha, path.as_uri(), "rejected_totals" if bad else "loaded", summary])
        for m in measures:
            con.execute("insert into batch_control_totals (id, organization_id, source_batch_id, measure_name, expected_value, loaded_value, tolerance, passed) "
                        "values (?,?,?,?,?,?,?,?)", [wh.new_id(), org, batch, m["measure"], m["expected"], m["loaded"], m["tolerance"], m["passed"]])
        result = {"file_id": fid, "batch_id": batch, "control_totals": [{"measure": m["measure"], "expected": str(m["expected"]), "loaded": str(m["loaded"]),
                                                                          "passed": m["passed"]} for m in measures]}
        if bad:
            return {**result, "status": "rejected_totals", "message": summary, "rows_loaded": 0, "held_back": []}

        pf = {r[0].strip().lower(): r[1] for r in con.execute("select portfolio_code, id from portfolios where organization_id = ?", [org]).fetchall()}
        itype = {r[0]: r[1] for r in con.execute("select id, instrument_type from instruments where organization_id = ?", [org]).fetchall()}
        names = ["id", "external_trade_id", "trade_date", "status", "portfolio_id", "instrument_id", "transaction_type", "quantity_delta", "cash_amount",
                 "currency", "settlement_date", "effective_date"]
        live = "not exists (select 1 from transactions s where s.supersedes_transaction_id = t.id)"
        join = "from transactions t join source_records r on r.id = t.source_record_id join source_batches b on b.id = r.source_batch_id"
        cur = {r[1]: dict(zip(names, r)) for r in con.execute(  # the current row of each trade id from this source
            f"select {', '.join('t.' + n for n in names)} {join} where b.source_system_id = ? and {live}", [sid]).fetchall()}
        elsewhere = dict(con.execute(  # instrument of the same trade id from another source (FX rows carry no code in the administrator file)
            f"select t.external_trade_id, t.instrument_id {join} where b.source_system_id <> ? and {live}", [sid]).fetchall())

        out, sups, held, waiting, kept, ports_wait, used = [], [], [], {}, 0, set(), set()

        def record(r: int | None, ext: str, eff, raw: dict, reason: str | None, cells: str | None = None) -> str:
            rid = wh.new_id()
            con.execute("insert into source_records (id, organization_id, source_batch_id, external_record_id, record_type, effective_at, received_at, recorded_at, "
                        "sheet_name, row_number, cell_range, raw_payload_uri, content_hash, quality_status) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [rid, org, batch, ext, "transactions", eff, received, now, sheet, r, cells, path.as_uri(),
                         hashlib.sha256(json.dumps(raw, default=str, sort_keys=True).encode()).hexdigest(), "held_back" if reason else "loaded"])
            return rid

        for r in rows:
            ext = f"{sheet}!{r['r']}"
            cells = f"{get_column_letter(parsed['first_col'])}{r['r']}:{get_column_letter(parsed['last_col'])}{r['r']}"
            tid, old, reason, row = r["_tid"], cur.get(r["_tid"]), None, {}
            if not tid:
                reason = "no trade id in the row"
            elif tid in used:
                reason = f"{tid}: the trade id is in the file twice"
            elif r["kind"] == "Amendment":
                if old is None:
                    reason = f"{tid}: no earlier trade to amend"
                elif r["_qty"] is None or r["_amt"] is None:
                    reason = f"{tid}: the amendment has no quantity or amount"
                else:
                    sq, sc = (1 if old["quantity_delta"] >= 0 else -1), (1 if old["cash_amount"] >= 0 else -1)
                    row = {k: old[k] for k in _KEEP} | dict(
                        trade_date=old["trade_date"], effective_date=old["effective_date"], settlement_date=old["settlement_date"],
                        quantity_delta=sq * abs(r["_qty"]), cash_amount=sc * abs(r["_amt"]), status="amended")
                    if _text(r.get("ccy")):
                        row["currency"] = _text(r["ccy"]).upper()
            elif old is not None and mode == "append":
                kept += 1
                used.add(tid)
                record(r["r"], ext, r["_date"], r["raw"], None, cells)
                continue
            else:
                iid, labels = None, [_text(r.get(k)) for k in _LABELS[layout] if _text(r.get(k)) and _text(r.get(k)).upper() != "FX"]
                for label in labels:
                    res = match.resolve(plane, label, sid)
                    if res.get("status") == "approved" and res.get("instrument_id"):
                        iid = res["instrument_id"]
                        break
                    waiting.setdefault(label, {"name": label, "identifier_id": res.get("identifier_id"), "status": res.get("status", "unknown"),
                                               "candidates": [c["name"] for c in res.get("candidates") or []][:3]})
                iid = iid or elsewhere.get(tid)
                if iid:
                    waiting = {k: v for k, v in waiting.items() if k not in labels}
                code, side = _text(r.get("portfolio")).lower(), _text(r.get("side")).lower()
                signed = _signed(itype.get(iid), side, abs(r["_qty"] or 0), abs(r["_amt"] or 0)) if iid else None
                if signed is None and iid and side and r["_qty"] is not None and r["_amt"] is not None:  # an unusual side ("bot", "SLD", "purchase"): two models read it
                    from sh_platform.v1 import v3_judge as J
                    said = J.judged(plane, "trade_side", J.question("trade_side", side=side), ["buy", "sell"], {"side": side},  # the word alone, so every row with it shares one answer
                                    J.standard("trade_side"))
                    if said:
                        side = said
                        signed = _signed(itype.get(iid), side, abs(r["_qty"] or 0), abs(r["_amt"] or 0))
                if r["_date"] is None or r["_qty"] is None or r["_amt"] is None or not _text(r.get("ccy")):
                    reason = f"{tid}: the row has no trade date, quantity, amount or currency"
                elif not iid:
                    reason = f"{_text(r.get('code')) or _text(r.get('name')) or 'no instrument'}: instrument not approved yet"
                elif code not in pf:
                    ports_wait.add(_text(r.get("portfolio")))
                    reason = f"{_text(r.get('portfolio')) or 'no portfolio'}: portfolio not approved yet (not in the company's master data)"
                elif signed is None:
                    reason = f"{tid}: side {side!r} is not buy or sell"
                else:
                    src_status = _text(r.get("status")).lower()
                    row = dict(portfolio_id=pf[code], instrument_id=iid, external_trade_id=tid,
                               transaction_type="fx_forward" if itype.get(iid) == "fx_forward" or "/" in side else side, trade_date=r["_date"], effective_date=r["_date"],
                               settlement_date=r["_settle"], quantity_delta=signed[0], cash_amount=signed[1], currency=_text(r["ccy"]).upper(),
                               status="booked" if src_status in ("executed", "booked", "") else src_status)
            rid = record(r["r"], ext, r["_date"], r["raw"], reason, cells)
            if reason:
                held.append({"row": r["r"], "reason": reason})
                continue
            used.add(tid)
            out.append(row | {"source_record_id": rid})
            sups.append(old["id"] if old else None)

        gone = 0
        if mode == "replace":  # a trade of a covered date that the file no longer lists is withdrawn
            scope = _scope(rec, parsed, trades)
            for tid, old in cur.items():
                if tid not in used and tid not in {r["_tid"] for r in rows} and old["status"] != "cancelled" and old["trade_date"] in scope:
                    rid = record(None, f"cancelled:{tid}", old["trade_date"], {"cancelled": tid, "file": rec["name"]}, None)
                    out.append({k: old[k] for k in names if k != "id"} | {"status": "cancelled", "source_record_id": rid})
                    sups.append(old["id"])
                    gone += 1

    needs = {"funds": sorted(waiting.values(), key=lambda x: x["name"]), "portfolios": sorted(ports_wait)}
    try:
        ids = e1w.record_many(plane, "transactions", out, sups) if out else []
    except Exception as e:  # noqa: BLE001 - the batch must not stay marked loaded
        log.exception("trade intake: writing transactions failed for %s", fid)
        with wh.connect(plane) as con:
            con.execute("update source_batches set validation_status = 'quarantined', validation_summary = ? where id = ?", [f"Writing failed: {e}", batch])
            con.execute("update source_records set quality_status = 'quarantined' where source_batch_id = ?", [batch])
        return {**result, "status": "quarantined", "message": f"Writing the rows failed ({e}). Nothing was loaded.", "rows_loaded": 0, "held_back": held}
    ok, nothing = len(ids) == len(out), not ids and bool(held)
    with wh.connect(plane) as con:
        con.execute("insert into batch_control_totals (id, organization_id, source_batch_id, measure_name, expected_value, loaded_value, tolerance, passed) values (?,?,?,?,?,?,?,?)",
                    [wh.new_id(), org, batch, "Rows written", Decimal(len(out)), Decimal(len(ids)), Decimal(0), ok])
        if nothing:  # every row held back: the file may be loaded again once the names are approved
            con.execute("update source_batches set validation_status = 'nothing_loaded', loaded_at = null where id = ?", [batch])
    result["control_totals"].append({"measure": "Rows written", "expected": str(len(out)), "loaded": str(len(ids)), "passed": ok})
    replaced = sum(1 for s in sups if s) - gone
    counts = {"written": len(ids) - gone - replaced, "replaced": replaced, "cancelled": gone, "kept": kept}
    base = {**result, "needs_approval": needs, "held_back": held, "observation_table": "transactions", "rows_loaded": len(ids), "mode": mode, "counts": counts}
    if nothing:
        return {**base, "status": "nothing_loaded", "message": f"Nothing was loaded. All {len(held)} rows are held back: "
                f"{len(needs['funds'])} instrument name(s) and {len(needs['portfolios'])} portfolio code(s) need approval."}
    msg = (f"Loaded {counts['written']} new trade(s), replaced {replaced}, cancelled {gone}, kept {kept} already there." if rows or gone else "The file has no trades.")
    _mod("e0c_load")._after_load(plane, _LAYOUTS[layout][0], sheet, parsed["heads"])
    return {**base, "status": "loaded", "message": msg + (f" {len(held)} held back: instrument or portfolio not approved yet." if held else "")}


# ---- a month in one action ---------------------------------------------------------------------------------------------

def load_folder(plane, folder, viewer, mode: str = "replace", sender: str = "trade-intake") -> dict:
    """Land every CSV / Excel file in `folder` (not its sub-folders) and load them in name order. Returns {file name: load result}.
    mode: replace | append (see the module doc). Files that are not trade files go the normal way and may wait for a mapping."""
    landing = _mod("e0c_landing")
    out = {}
    for p in sorted(Path(folder).iterdir()):
        if not p.is_file() or p.suffix.lower() not in (".csv", ".xlsx", ".xlsm"):
            continue
        rec = landing.receive(plane, p.read_bytes(), p.name, sender, source_code="trading_export" if p.suffix.lower() == ".csv" else "administrator")
        landing.set_state(plane, rec["file_id"], rec["state"], trade_mode=mode)
        out[p.name] = landing.load(plane, rec["file_id"], viewer).get("last_load") or {}
    return out
