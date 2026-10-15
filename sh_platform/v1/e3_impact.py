"""E3c: a new valuation that supersedes a value an issued report used opens a revision exception with the effect per report line.

Reads facts, writes only `exception_impacts` (through the case card's `open`); never touches nav_snapshots or any observation row.
Sibling cards are imported lazily: e1_reports, e3_calc, e3_rules, e4_cases.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from sh_platform.v1 import wh

log = logging.getLogger(__name__)


def _need(module: str):
    try:
        return __import__(f"sh_platform.v1.{module}", fromlist=["x"])
    except ImportError:
        log.warning("e3_impact needs %s, which is not installed", module)
        raise


def _row(con, table: str, row_id: str) -> dict | None:
    cur = con.execute(f"select * from {table} where id = ?", [row_id])
    r = cur.fetchone()
    return {d[0]: (str(v) if type(v).__name__ == "UUID" else v) for d, v in zip(cur.description, r)} if r else None


def _materiality(plane, amount: Decimal, currency: str, base: Decimal | None, on_date) -> tuple[str, str | None]:
    """(status, rule_version_id) from the signed cio_materiality rule; unknown when none is signed."""
    rule = _need("e3_rules").current(plane, "cio_materiality", on_date)
    if not rule:
        return "unknown", None
    p = rule.get("parameters") or {}
    limit = p.get("abs_amount")
    pct = p.get("pct_of_fund")
    over = (limit is not None and abs(amount) > Decimal(str(limit))) or (
        pct is not None and base and abs(amount) > base * Decimal(str(pct)) / 100)
    return ("material" if over else "below_threshold"), rule.get("rule_version_id")


def _used_row(con, plane, new: dict) -> tuple[dict | None, list[str]]:
    """Walk back from the new row to the earlier valuation an issued report used: (that row, the report versions). A confirmed
    row that supersedes a pending one reaches the original through the pending row."""
    reports = _need("e1_reports")
    cur, seen = new, set()
    while cur.get("supersedes_valuation_id") and cur["id"] not in seen:
        seen.add(cur["id"])
        cur = _row(con, "valuation_observations", cur["supersedes_valuation_id"])
        if cur is None:
            return None, []
        versions = reports.versions_using(plane, "valuation_observations", cur["id"])
        if versions:
            return cur, versions
    return None, []


def on_new_valuation(plane, valuation_id: str) -> str | None:
    """Exception id when the new valuation (pending or confirmed) supersedes a value an issued report used, else None.
    One revision case per subject (instrument and valuation date): a later row for the same subject returns the open case."""
    from sh_platform.v1.e1_write import org_id
    with wh.connect(plane, read_only=True) as con:
        new = _row(con, "valuation_observations", valuation_id)
        if not new or new.get("approval_status") == "rejected":
            return None
        old, versions = _used_row(con, plane, new)
    if not old:
        return None
    calc = _need("e3_calc")
    delta = Decimal(str(new["value_amount"])) - Decimal(str(old["value_amount"]))
    impacts, notes, total, report_ccy, line_pf = [], [], Decimal(0), None, None
    with wh.connect(plane, read_only=True) as con:
        for vid in versions:
            rv = _row(con, "report_versions", vid)
            mv = con.execute(
                "select id, numeric_value, currency, portfolio_id from metric_values where calculation_run_id = ? and instrument_id = ?",
                [rv["calculation_run_id"], old["instrument_id"]]).fetchone()
            if not mv:
                continue
            mv_id, issued, ccy = str(mv[0]), mv[1], mv[2]
            line_pf = line_pf or (str(mv[3]) if mv[3] else None)
            d = delta
            if new["currency"] != ccy:
                rate = calc.fx(plane, new["currency"], ccy, new["valuation_date"], wh.now())
                if rate is None:
                    notes.append(f"No exchange rate from {new['currency']} to {ccy}: effect on one report line not worked out.")
                    impacts.append((vid, mv_id, issued, None, ccy))
                    continue
                d = delta * Decimal(str(rate))
            report_ccy = report_ccy or ccy
            total += d
            impacts.append((vid, mv_id, issued, Decimal(str(issued)) + d, ccy))
        fund = (con.execute("select canonical_name from instruments where id = ?", [new["instrument_id"]]).fetchone() or ["the fund"])[0]
        same = con.execute(
            "select id from exceptions where exception_type = 'revision' and instrument_id = ? and status not in ('resolved', 'rejected')"
            " and description like ? order by detected_at limit 1", [new["instrument_id"], f"%valued {new['valuation_date']}%"]).fetchone()
        have = {(str(r[0]), str(r[1]), Decimal(str(r[2]))) for r in con.execute(
            "select report_version_id, metric_value_id, draft_value from exception_impacts where exception_id = ? and draft_value is not null",
            [same[0]]).fetchall()} if same else set()
    if not impacts:
        return None
    exc_id = str(same[0]) if same else None
    if not exc_id:
        ccy = report_ccy or new["currency"]
        status, rule_vid = _materiality(plane, total, ccy, Decimal(str(old["value_amount"])), new["valuation_date"])
        kind = (new.get("valuation_type") or "manager").replace("_", " ")
        state = "confirmed" if new.get("approval_status") in ("confirmed", "approved", "approved_official") else "not yet verified"
        desc = (f"A manager-reported valuation of {fund} (valued {new['valuation_date']}, {kind}, {state}) replaces an earlier one that an issued "
                f"report used. Difference in the manager-reported valuation: {total:,.2f} {ccy}. Official NAV is unchanged.") + "".join(" " + n for n in notes)
        exc_id = _need("e4_cases").open(plane, {
            "exception_type": "revision", "description": desc,
            "title": f"Investigate the {abs(total):,.0f} {ccy} manager-reported valuation difference for {fund}",
            "instrument_id": new["instrument_id"], "portfolio_id": new.get("portfolio_id") or line_pf, "detected_at": wh.now(),
            "candidate_impact_amount": total, "impact_currency": ccy, "materiality_status": status,
            "materiality_rule_version_id": rule_vid, "status": "new"})
    with wh.connect(plane) as con:
        for vid, mv_id, issued, draft, c in impacts:
            if draft is not None and (vid, mv_id, draft) in have:
                continue  # the same effect is already on the case
            con.execute(
                "insert into exception_impacts (id, organization_id, exception_id, report_version_id, metric_value_id, issued_value, draft_value, currency)"
                " values (?,?,?,?,?,?,?,?)",
                [wh.new_id(), org_id(plane), exc_id, vid, mv_id, issued, draft, c])
    return exc_id
