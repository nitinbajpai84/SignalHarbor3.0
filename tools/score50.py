"""Score the top 50 use cases on the six-month Evergreen Office: one fast, deterministic run before the slow live runs.

    python tools/score50.py            -> docs/v3/SCORE50.md, totals printed, exit 0 always

What it does, in order:
1. Loads tests/v1/fixtures/office6m once into a fresh test plane with the real loader (v3_office6m_loaders.load_plane), as of 13 Oct 2026.
2. Runs every built recipe of the pack once on that warehouse (render, tables check, build, tie-out), the way tests/v1/test_w2_loader.py does.
3. For each top-50 card (packs/family_office/1/use_cases_100.yaml, priority 1..50) reads the numbers its answer key expects
   (tests/v1/fixtures/office6m/answer_keys.yaml) from the recipe output at the row the key names. CHECKS below says which recipe and column answer each
   key field (the per-domain tests tests/v1/test_w1_*.py and test_w2_loader.py are the source of that mapping). No expected number is typed here:
   row selectors (a fund, a date, a call number) and column names only.
4. Runs the card's signals (packs/family_office/1/signals/<card>-*.yaml) once over the recipe rows with the signal engine's own resolve and condition
   (v3_signals), the model-free way: a fund name is matched by its normalised spelling, never by the judge. The planted mess of each card (MESS, from
   the fixture MANIFEST's "Mess planted on purpose" and the key's own flagged items) must be caught by a signal of the card; an exception signal (one
   with a hold) must not fire on any other row.
5. Gives each card PASS / FAIL (a number is wrong, a recipe errors or does not tie out) / SIGNAL (numbers right, a signal misbehaves) /
   BLOCKED (needs something that does not exist yet) and writes docs/v3/SCORE50.md.

Synthetic data only. Nothing is written to the repo but the scorecard; the test plane lives in a temporary folder.
"""
from __future__ import annotations

import logging
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

OFFICE = REPO / "tests" / "v1" / "fixtures" / "office6m"
PACK = REPO / "packs" / "family_office" / "1"
OUT = REPO / "docs" / "v3" / "SCORE50.md"
TODAY = "2026-10-13"
log = logging.getLogger("score50")


# ---- comparing a key value with a recipe value ---------------------------------------------------------------------------------------------

def _decimals(x: float) -> int:
    s = repr(float(x))
    return len(s.split(".")[1].rstrip("0")) if "." in s and "e" not in s else 0


def show(v) -> str:
    if isinstance(v, (date, datetime)):
        return v.isoformat()[:10]
    if isinstance(v, Decimal):
        v = float(v)
    if isinstance(v, float):
        return f"{v:,.6f}".rstrip("0").rstrip(".")
    if isinstance(v, dict):  # recipe rows come in no fixed order: show them sorted so two runs write the same scorecard
        return "{" + ", ".join(f"{k!r}: {show(x)}" for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))) + "}"
    if isinstance(v, list):
        return "[" + ", ".join(show(x) for x in v) + "]"
    return repr(v) if isinstance(v, str) else str(v)


def same(exp, got) -> bool:
    """A key value against a recipe value: a number to the decimals the key writes (at least cents), a date as ISO text, a list in any order."""
    if exp is None:
        return got is None or got == ""
    if isinstance(exp, bool):
        return got is not None and not isinstance(got, str) and bool(got) == exp
    if isinstance(exp, (int, float)):
        try:
            return abs(float(got) - float(exp)) <= 0.5 * 10 ** -max(_decimals(exp), 2) + 1e-12
        except (TypeError, ValueError):
            return False
    if isinstance(exp, list):
        if not isinstance(got, (list, tuple)) or len(got) != len(exp):
            return False
        if all(same(e, g) for e, g in zip(exp, got)):
            return True
        return all(same(e, g) for e, g in zip(sorted(exp, key=show), sorted(got, key=show)))
    if isinstance(exp, dict):
        return isinstance(got, dict) and set(map(str, exp)) == set(map(str, got)) and all(same(exp[k], got.get(k, got.get(str(k)))) for k in exp)
    return show(got).strip("'") == str(exp) if got is not None else False


# ---- the check specs ---------------------------------------------------------------------------------------------------------------------------

class K:
    """A value taken from the card's own key (a row selector such as the fund the key names)."""
    def __init__(self, path: str):
        self.path = path


def dig(d, path: str):
    for p in [x for x in path.split(".") if x]:
        if not isinstance(d, dict) or p not in d:
            raise KeyError(path)
        d = d[p]
    return d


def pick(rows: list[dict], where: dict, key: dict) -> list[dict]:
    out = []
    for r in rows:
        ok = True
        for c, w in where.items():
            w = dig(key, w.path) if isinstance(w, K) else w
            if callable(w):
                ok = bool(w(r))
            elif isinstance(w, (list, tuple, set)):
                ok = any(same(x, r.get(c)) for x in w)
            else:
                ok = same(w, r.get(c))
            if not ok:
                break
        if ok:
            out.append(r)
    return out


def _wh(where: dict, key: dict) -> str:
    return ", ".join(f"{c}={'<rule>' if callable(v) else show(dig(key, v.path) if isinstance(v, K) else v)}" for c, v in where.items())


def V(q, path, rid, col, fn=None, **where):
    """One key value = column `col` of the one row `where` selects (fn turns the row value into the key's form)."""
    def run(rows, key):
        hit = pick(rows[rid], where, key)
        if len(hit) != 1:
            return [(path, dig(key, path), f"{len(hit)} rows where {_wh(where, key)}", False)]
        got = hit[0].get(col)
        got = fn(got) if fn else got
        return [(path, dig(key, path), got, same(dig(key, path), got))]
    return {"q": q, "recipes": [rid], "run": run, "paths": [path]}


def D(q, path, rid, keycol, fields, alias=None, **where):
    """The key is {name: value} or {name: {field: value}}; each name is the row whose `keycol` is that name. fields: a column, or {key field: column}."""
    def run(rows, key):
        out, want = [], dig(key, path)
        for name, exp in want.items():
            hit = pick(rows[rid], {**where, keycol: (alias or {}).get(name, name)}, key)
            p = f"{path}.{name}" if path else str(name)
            if len(hit) != 1:
                out.append((p, exp, f"{len(hit)} rows where {keycol}={(alias or {}).get(name, name)}", False))
                continue
            for kf, col in (fields.items() if isinstance(fields, dict) else [(None, fields)]):
                if kf is not None and kf not in exp:
                    continue
                e = exp[kf] if kf is not None else exp
                c, fn = col if isinstance(col, tuple) else (col, None)
                g = fn(hit[0].get(c)) if fn else hit[0].get(c)
                out.append((f"{p}.{kf}" if kf else p, e, g, same(e, g)))
        return out
    return {"q": q, "recipes": [rid], "run": run, "paths": [path]}


def L(q, path, rid, match, fields, alias=None, exact=True, **where):
    """The key is a list of rows; each is found by `match` ({key field: column}) and its `fields` compared. exact: no other row is selected."""
    def run(rows, key):
        out, want, sel = [], dig(key, path), pick(rows[rid], where, key)
        used = set()
        for i, item in enumerate(want):
            m = {col: (alias or {}).get(item[kf], item[kf]) for kf, col in match.items()}
            hit = pick(sel, m, key)
            p = f"{path}[{', '.join(str(item[k]) for k in match)}]"
            if len(hit) != 1:
                out.append((p, "1 row", f"{len(hit)} rows", False))
                continue
            used.add(id(hit[0]))
            for kf, col in fields.items():
                if kf in item:
                    c, fn = col if isinstance(col, tuple) else (col, None)
                    g = fn(hit[0].get(c)) if fn else hit[0].get(c)
                    out.append((f"{p}.{kf}", item[kf], g, same(item[kf], g)))
        extra = [r for r in sel if id(r) not in used]
        if exact and extra:
            out.append((f"{path} (rows)", len(want), f"{len(sel)} rows; also {', '.join(show(r.get(c)) for r in extra[:4] for c in list(match.values())[:1])}", False))
        return out
    return {"q": q, "recipes": [rid], "run": run, "paths": [path]}


def S(q, path, rid, col, pred=None, **where):
    """The key is a list of names: column `col` of the rows `pred` keeps, in any order."""
    def run(rows, key):
        got = sorted((r.get(col) for r in pick(rows[rid], where, key) if pred is None or pred(r)), key=show)
        return [(path, dig(key, path), got, same(dig(key, path), got))]
    return {"q": q, "recipes": [rid], "run": run, "paths": [path]}


def N(q, path, rid, pred=None, **where):
    """The key is a count of rows."""
    def run(rows, key):
        got = len([r for r in pick(rows[rid], where, key) if pred is None or pred(r)])
        return [(path, dig(key, path), got, same(dig(key, path), got))]
    return {"q": q, "recipes": [rid], "run": run, "paths": [path]}


def F(q, path, rids, fn, kf=None):
    """The key value worked out from recipe rows by a small function (a sum, a pivot); fn(rows) -> value. kf: the part of the key value a recipe can
    give (a file path in a key row is not a column)."""
    def run(rows, key):
        got, exp = fn(rows), dig(key, path)
        return [(path, exp, got, same(kf(exp) if kf else exp, got))]
    return {"q": q, "recipes": list(rids), "run": run, "paths": [path]}


def tot(rows, col, pred=lambda r: True):
    return round(sum(float(r[col] or 0) for r in rows if pred(r)), 2)


def by(rows, keycol, col, pred=lambda r: True):
    out: dict = defaultdict(float)
    for r in rows:
        if pred(r):
            out[r[keycol]] += float(r[col] or 0)
    return {k: round(v, 2) for k, v in out.items()}


def iso(v) -> str:
    return show(v)


def month_end(d) -> bool:
    return isinstance(d, date) and (d + timedelta(days=1)).day == 1


TODAY_ROW = {"position_date": TODAY}
SEP30 = "2026-09-30"
LIQUID = "Evergreen Liquid Book"
CV3 = "Cedarpoint Ventures III"
M03 = ["Evergreen Growth I", CV3, "Kestrel Ridge Macro Fund"]  # MANIFEST M03: the three amended statements

# card -> the checks of its key. The comments name the planted mess (MANIFEST) or the test the mapping comes from.
CHECKS: dict[str, list] = {
    "uc-001-noticelog": [
        *[V(0, kf, "call_notice_fields", col, call_no=7) for kf, col in (("fund", "fund"), ("investor", "investor"), ("amount_usd", "amount"), ("due", "due_date"),
                                                                       ("new_investments", "new_investments"), ("management_fee", "management_fee"), ("account_ending", "account_ending"))],
        N(1, "count", "notices_open"),
        F(1, "notices", ["notices_open"], lambda x: [str(r["call_no"]) for r in x["notices_open"]], kf=lambda e: [n.split("-")[-1] for n in e]),
    ],
    "uc-002-callrecord": [
        *[V(0, kf, "called_to_date", col, fund=CV3) for kf, col in (("commitment", "commitment"), ("called_before_call_7", "called_before_notice"),
                                                                    ("called_after_call_7", "called_after_notice"), ("unfunded_after_call_7", "unfunded_after_notice"),
                                                                    ("within_commitment", "notice_fits"))],
        *[V(1, kf, "call_fee_check", col, fund=CV3, call_no=7) for kf, col in (("fee_on_notice", "fee_on_notice"), ("fee_per_terms", "fee_per_terms"), ("matches", "fee_matches"))],
    ],
    "uc6-liquidity": [
        D(0, "", "cash_by_entity", "entity", {"usd": "cash"}, currency="USD", **TODAY_ROW),
        D(0, "", "cash_by_entity", "entity", {"sgd": "cash"}, currency="SGD", **TODAY_ROW),
        D(1, "", "calls_due", "entity", {"30": "calls_due"}, currency="USD", window_days=30),
        D(1, "", "calls_due", "entity", {"60": "calls_due"}, currency="USD", window_days=60),
    ],
    "uc-004-callcheck": [
        *[V(0, kf, "cash_after_calls", col, entity="Evergreen Holdings", currency="USD") for kf, col in (("holdings_usd", "cash"), ("call", "calls_due"), ("buffer", "buffer"),
                                                                                                       ("shortfall_usd", "shortfall"))],
        V(0, "pays_from_usd_alone", "cash_after_calls", "shortfall", lambda v: not (v and v > 0), entity="Evergreen Holdings", currency="USD"),
        V(0, "holdings_sgd", "cash_after_calls", "cash", entity="Evergreen Holdings", currency="SGD"),
        V(0, "sgd_to_convert", "fx_required", "convert_amount", entity="Evergreen Holdings"),
        F(0, "sgd_in_usd", ["fx_required"], lambda x: next((round(float(r["other_cash"]) / float(r["rate"]), 2) for r in x["fx_required"]
                                                            if r["entity"] == "Evergreen Holdings" and r["rate"]), None)),
        V(1, "fits", "called_to_date", "notice_fits", fund=CV3),
        V(1, "unfunded_before", "called_to_date", "unfunded_before_notice", fund=CV3),
    ],
    "uc-005-benefcheck": [
        *[V(0, kf, "bank_details_changed", col, fund=CV3, call_no=7) for kf, col in (("changed", "changed"), ("old_ending", "old_ending"), ("new_ending", "new_ending"),
                                                                                     ("callback_required", "on_hold"))],
        V(0, "earlier_calls_paid_to", "bank_details_changed", "paid_to", lambda v: str(v or "").split(","), fund=CV3, call_no=7),
        N(1, "count", "bank_details_changed", lambda r: r["on_hold"]),
        F(1, "payment", ["bank_details_changed"], lambda x: ",".join(str(r["call_no"]) for r in x["bank_details_changed"] if r["on_hold"]), kf=lambda e: e.split("-")[-1]),
    ],
    "uc-006-fxneed": [
        V(0, "sgd_to_convert_for_call_7", "fx_required", "convert_amount", entity="Evergreen Holdings"),
        V(0, "planning_rate", "fx_required", "rate", entity="Evergreen Holdings"),
        L(0, "conversions", "fx_rate_check", {"ref": "trade_reference"}, {"usd": "amount_bought", "rate": "bank_rate", "fixing": "fixing", "diff_pct": "difference_pct",
                                                                         "within_0_1_pct": ("difference_pct", lambda v: v is not None and abs(float(v)) <= 0.1)},
          trade_reference=lambda r: str(r["trade_reference"]).startswith("FXS-")),
        L(1, "calls_due_to_date", "call_payment_status", {"due": "due_date", "amount": "amount"}, {"paid": ("status", lambda s: s == "paid")},
          due_date=lambda r: str(r["due_date"]) <= TODAY),
        F(2, "refs", ["fx_rate_check", "fx_confirmation_variance"],
          lambda x: sorted({r["trade_reference"] for r in x["fx_rate_check"]} - {r["trade_reference"] for r in x["fx_confirmation_variance"]})),
    ],
    "uc-007-pacing": [
        D(0, "by_fund", "commitments_by_fund", "fund", {"committed": "committed", "called": "called", "unfunded": "unfunded"}, is_total=0),
        V(0, "total_unfunded", "commitments_by_fund", "unfunded", is_total=1),
        V(0, "cedarpoint_iii_unfunded", "commitments_by_fund", "unfunded", fund=CV3),
        F(1, "private_markets_budget", ["private_markets_budget"], lambda x: x["private_markets_budget"][0]["budget"] if x["private_markets_budget"] else None),
    ],
    "uc9-sop": [  # read by v3_process from the narrative and the hand-over email (READERS)
        V(0, "steps", "process_steps", "steps"),
        F(0, "owners", ["process_steps"], lambda x: x["process_steps"][0]["owners"] if x["process_steps"] else None),
        F(0, "manual_steps_flagged_for_automation", ["process_steps"], lambda x: x["process_steps"][0]["manual_step_numbers"] if x["process_steps"] else None),
    ],
    "uc-008-payrun": [
        L(0, "items", "payment_batch", {"payee": "payee"}, {"amount": "amount", "ccy": "currency", "due": "due_date", "state": "state"}),
        F(0, "states", ["payment_batch"], lambda x: dict(Counter(r["state"] for r in x["payment_batch"]))),
    ],
    "uc-010-bankexp": [
        D(0, "usd_equivalent_by_bank", "cash_by_bank", "bank", "usd_equivalent"),
        D(0, "share_pct", "cash_by_bank", "bank", "share_pct"),
        F(0, "total_usd_eq", ["cash_by_bank"], lambda x: tot(x["cash_by_bank"], "usd_equivalent")),
    ],
    "uc10-pipeline": [
        V(0, "evergreen_liquid", "net_worth", "net_worth", portfolio=LIQUID, position_date=SEP30, currency="USD"),
        D(0, "net_worth_by_portfolio", "net_worth", "portfolio", "net_worth", alias={"EG-LIQUID": LIQUID}, position_date=SEP30, currency="USD"),
    ],
    "uc5-limits": [
        F(0, "holding", ["single_name_breach"], lambda x: max((r for r in x["single_name_breach"] if r["portfolio"] == LIQUID and str(r["position_date"]) == SEP30
                                                               and r["status"] == "real breach"), key=lambda r: r["concentration_pct"], default={}).get("holding")),
        S(0, "over_limit", "single_name_breach", "holding", portfolio=LIQUID, position_date=SEP30, status="real breach"),
        V(0, "value", "concentration", "exposure", portfolio=LIQUID, position_date=SEP30, issuer=K("holding")),
        V(0, "pct_of_portfolio", "concentration", "concentration_pct", portfolio=LIQUID, position_date=SEP30, issuer=K("holding")),
        F(0, "limit_pct", ["single_name_breach"], lambda x: (lambda v: v[0] if len(v) == 1 else v)(sorted({float(r["limit_pct"]) for r in x["single_name_breach"] if r["limit_pct"] is not None}))),
        V(0, "breach", "single_name_breach", "over_limit", portfolio=LIQUID, position_date=SEP30, holding=K("holding")),
        V(1, "listed_equity_pct", "drift_vs_target", "allocation_pct", bucket="listed equity", position_date=SEP30),
        F(1, "listed_equity_band", ["drift_vs_target"], lambda x: next((f"{float(r['min_pct']):g}-{float(r['max_pct']):g}" for r in x["drift_vs_target"]
                                                                     if r["bucket"] == "listed equity" and str(r["position_date"]) == SEP30), "no row at 2026-09-30")),
        V(1, "hedge_funds_pct_of_eg_funds", "drift_vs_target", "allocation_pct", bucket="hedge fund", portfolio="EG-FUNDS"),
        V(1, "cedarpoint_pct_of_eg_b_ops", "drift_vs_target", "allocation_pct", portfolio="EG-B-OPS"),
        V(1, "cedarpoint_max", "drift_vs_target", "max_pct", portfolio="EG-B-OPS"),
    ],
    "uc-013-secgaps": [
        N(0, "count", "identifier_gaps", lambda r: r["has_gap"]),
        S(0, "instruments", "identifier_gaps", "instrument", lambda r: r["has_gap"]),
        V(0, "value", "identifier_gaps", "gap_value", has_gap=True),
    ],
    "morning-networth-note": [
        *[V(0, kf, "report_total_fx", col) for kf, col in (("total_usd", "total_usd"), ("total_sgd", "total_sgd"), ("fixing", "usd_sgd_fixing"), ("issued", "issued_on"))],
        D(0, "lines", "report_ready", "section", "report_value"),
    ],
    "uc-015-allowances": [
        D(0, "due_october", "allowance_due", "member_name", "scheduled", month=lambda r: str(r["month"])[:7] == TODAY[:7]),  # due for October = scheduled; it was paid on 1 Oct (the October statement), so owed is 0
    ],
    "uc-016-schemadrift": [
        V(0, "old_name", "columns_changed", "old_name"),
        V(0, "new_name", "columns_changed", "new_name"),
        V(0, "months_with_old_name", "columns_changed", "batches_on_old_name"),
    ],
    "uc-017-liab": [
        V(0, "principal_outstanding", "facility_headroom", "drawn_amount", facility_ref="TL-B-01"),
        V(0, "loan_balance_as_shown_negative", "facility_headroom", "drawn_amount", lambda v: -v if v is not None else None, facility_ref="TL-B-01"),
        F(0, "by_month", ["net_worth_after_debt"], lambda x: {str(r["position_date"])[:7]: -float(r["debt"]) for r in x["net_worth_after_debt"]
                                                             if r["entity"] == "Entity B" and r["currency"] == "USD" and month_end(r["position_date"]) and str(r["position_date"]) <= SEP30}),
        V(0, "report_total", "report_total_fx", "total_usd"),
        F(0, "report_less_debt", ["report_total_fx", "facility_headroom"],
          lambda x: float(x["report_total_fx"][0]["total_usd"]) - float(x["facility_headroom"][0]["drawn_amount"]) if x["report_total_fx"] and x["facility_headroom"] else None),
        V(0, "all_portfolios_nav", "net_worth_after_debt", "family_net_worth", entity="Entity B", currency="USD", position_date=SEP30),
        V(0, "all_portfolios_less_debt", "net_worth_after_debt", "family_net_worth_after_debt", entity="Entity B", currency="USD", position_date=SEP30),
    ],
    "uc-018-fundplan": [
        D(0, "usd_cover_after_buffer_and_call", "funding_plan", "entity", "cover_after_calls"),
        V(0, "paying_entity", "funding_plan", "entity", is_named=True),
        V(0, "transfer_needed", "funding_plan", "transfer_needed", is_named=True),
        V(0, "shortfall", "funding_plan", "shortfall", is_named=True),
        S(0, "entities_with_spare_usd", "funding_plan", "entity", lambda r: (r["cover_after_calls"] or 0) > 0),
    ],
    "uc3-statements-inbox": [
        L(0, "missing", "statement_timeliness", {"fund": "statement_of", "period": "period_end"}, {"due": "due_date", "business_days_overdue_13_oct": "business_days_overdue"},
          status="missing", kind="manager statement"),
        L(1, "late", "statement_timeliness", {"fund": "statement_of", "period": "period_end"}, {"due": "due_date", "received": "received_on", "business_days_late": "business_days_late"},
          status="late", kind="manager statement"),
        F(2, "rows", ["statement_timeliness"], lambda x: sorted((["bank_statement", str(r["period_end"])[:7], iso(r["due_date"]), iso(r["received_on"]) if r["received_on"] else "",
                                                                  "never received" if r["status"] == "missing" else r["status"]] for r in x["statement_timeliness"]
                                                                 if r["kind"] == "bank statement" and r["status"] != "on_time"), key=str),
          kf=lambda e: sorted((row[1:] for row in e), key=str)),
    ],
    "uc1-why-nav-moved": [
        V(0, "issued", "change_since_report", "original_value", fund="Evergreen Growth I"),
        V(0, "amended", "change_since_report", "amended_value", fund="Evergreen Growth I"),
        V(0, "change", "change_since_report", "change_since_report", fund="Evergreen Growth I"),
        F(0, "change_pct", ["change_since_report"], lambda x: next((round(float(r["change_since_report"]) * 100 / float(r["original_value"]), 2)
                                                                    for r in x["change_since_report"] if r["fund"] == "Evergreen Growth I"), None)),
        V(0, "received", "amendments_open", "received_on", fund="Evergreen Growth I"),
    ],
    "uc-021-stale": [
        D(0, "by_fund", "value_age_days", "fund", {"valuation_date": "valuation_date", "age_days": "age_days", "stale": "stale"}),
        S(0, "stale", "value_age_days", "fund", lambda r: r["stale"]),
    ],
    "uc-022-amendlog": [
        F(0, "last_issued_report", ["amendments_open"], lambda x: iso(x["amendments_open"][0]["last_issued_report"]) if x["amendments_open"] else None),
        L(0, "amendments", "amendments_open", {"fund": "fund"}, {"period": "valuation_date", "replaces": "replaces", "amended": "amended_value", "change": "change",
                                                                "received": "received_on", "after_last_issued_report": ("open_amendments", bool)}),
        F(0, "open_count", ["amendments_open"], lambda x: sum(int(r["open_amendments"]) for r in x["amendments_open"])),
    ],
    "uc-023-tieout": [
        L(0, "differences", "report_tie_out", {"month": "report_month", "line": "line"}, {"report": "report_value", "administrator": "administrator_value", "difference": "difference"},
          difference=lambda r: r["difference"] != 0),
        F(0, "months_checked", ["report_tie_out"], lambda x: len({r["report_month"] for r in x["report_tie_out"]})),
    ],
    "uc-024-audit": [
        N(0, "sampled", "trace_coverage"),
        N(0, "traced", "trace_coverage", lambda r: r["traced"]),
        F(0, "share_traced_pct", ["trace_coverage"], lambda x: x["trace_coverage"][0]["share_traced_pct"] if x["trace_coverage"] else None),
        L(0, "untraceable", "trace_coverage", {"item": "item"}, {"month": "report_month", "line": "line", "figure": "figure"}, traced=False),
    ],
    "uc7-manager-diligence": [
        N(0, "items_since_12_june", "manager_timeline", lambda r: r["item_kind"] == "statement" and str(r["item_date"]) > str(r["last_meeting"]), manager="Kestrel Ridge Advisors"),
        L(0, "newest_first", "manager_timeline", {"date": "item_date", "fund": "fund", "kind": "status_kind"}, {"period": "period", "value": "value"},
          manager="Kestrel Ridge Advisors", item_kind="statement", item_date=lambda r: str(r["item_date"]) > str(r["last_meeting"])),
        V(0, "h1_july_restated_from", "manager_timeline", "restated_from", fund="Kestrel Ridge Macro Fund", period="2026-07-31", status_kind="amended"),
        V(0, "h1_july_restated_to", "manager_timeline", "value", fund="Kestrel Ridge Macro Fund", period="2026-07-31", status_kind="amended"),
        V(0, "h1_latest_value", "manager_timeline", "value", fund="Kestrel Ridge Macro Fund", period=SEP30),
    ],
    "uc-026-stmtadmin": [
        D(0, "differences", "statement_vs_admin", "fund", {"statement": "statement_value", "administrator": "administrator_value", "difference": "difference",
                                                           "administrator_status": "administrator_status", "statement_kind": "statement_kind"}),
    ],
    "uc2-recon-break-desk": [
        *[V(0, kf, "cash_difference_by_source", col, entity=K("entity"), day=K("date"), source="administrator", currency="USD")
          for kf, col in (("bank", "bank_cash"), ("administrator", "other_cash"), ("difference", "cash_break"))],
        L(1, "over_tolerance", "cash_difference_by_source", {"date": "day", "entity": "entity", "source": "source"}, {"bank": "bank_cash", "other": "other_cash", "difference": "cash_break"},
          alias={"admin": "administrator", "oms": "desk"}, over_tolerance=1, bank_complete=lambda r: r["bank_complete"]),
        L(1, "inside_tolerance", "cash_difference_by_source", {"date": "day", "entity": "entity", "source": "source"}, {"difference": "cash_break"},
          alias={"admin": "administrator", "oms": "desk"}, over_tolerance=0, bank_complete=lambda r: r["bank_complete"]),
    ],
    "uc-028-interco": [
        *[V(0, kf, "intercompany_balance", col) for kf, col in (("lender", "lender"), ("borrower", "borrower"), ("amount", "balance_outstanding"), ("date", "first_transfer_date"),
                                                                ("reference", "reference"), ("balance_outstanding", "balance_outstanding"))],
        V(0, "approval_recorded", "intercompany_balance", "approvals_recorded", lambda v: bool(v)),
    ],
    "uc-029-closeck": [
        N(0, "steps", "close_items_done", close_month="2026-09"),
        N(0, "done", "close_items_done", lambda r: r["done"], close_month="2026-09"),
        S(0, "open", "close_items_done", "step_name", lambda r: r["open"], close_month="2026-09"),
        S(0, "late", "close_items_done", "step_name", lambda r: r["late"], close_month="2026-09"),
    ],
    "uc-030-vendors": [
        L(0, "renewing_within_90_days", "renewals_vendors", {"vendor": "vendor_name"}, {"currency": "currency", "annual_cost": "annual_cost", "renewal": "next_renewal_date",
                                                                                        "days_to_renewal": "days_to_renewal"}),
        N(0, "count", "renewals_vendors"),
    ],
    "uc-031-alloc": [
        F(0, "total", ["allocation"], lambda x: next((r["total_value"] for r in x["allocation"] if str(r["position_date"]) == SEP30 and r["currency"] == "USD"), None)),
        F(0, "by_class", ["allocation"], lambda x: by([r for r in x["allocation"] if str(r["position_date"]) == SEP30 and r["currency"] == "USD"], "asset_class", "market_value",
                                                      lambda r: r["asset_class"] != "cash")),
        F(0, "by_class_pct", ["allocation"], lambda x: by([r for r in x["allocation"] if str(r["position_date"]) == SEP30 and r["currency"] == "USD"], "asset_class", "share_pct",
                                                          lambda r: r["asset_class"] != "cash")),
        F(0, "by_entity_pct", ["allocation"], lambda x: by([r for r in x["allocation"] if str(r["position_date"]) == SEP30 and r["currency"] == "USD"], "entity", "share_pct")),
    ],
    "uc-032-driftrep": [
        F(0, "rows", ["drift_vs_target"], lambda x: [{"rule": f"{r['bucket'].replace(' ', '_')} ({'EG-LIQUID' if r['portfolio'] == LIQUID else r['portfolio']})",
                                                      "pct": float(r["allocation_pct"]), "band": f"{float(r['min_pct']):g}-{float(r['max_pct']):g}", "outside": bool(r["outside_band"])}
                                                     for r in x["drift_vs_target"] if r["dimension"] == "asset_class"]),
        S(0, "outside", "drift_vs_target", "bucket", lambda r: r["outside_band"]),
    ],
    "uc-033-breachesc": [
        *[V(0, kf, "single_name_breach", col, portfolio=LIQUID, position_date=SEP30, holding=K("holding"))
          for kf, col in (("exposure", "exposure"), ("total", "portfolio_total"), ("limit_pct", "limit_pct"), ("cost_to_cure", "cost_to_cure"))],
    ],
    "uc-034-prospect": [
        *[V(0, kf, "mandate_fit", col) for kf, col in (("minimum_ticket", "ticket"), ("asset_class", "asset_class"), ("policy_limit_for_private_markets", "private_markets_limit_pct"),
                                                       ("uncalled_before", "uncalled_before"), ("uncalled_after", "uncalled_after"), ("ticket_pct_of_current_uncalled", "ticket_pct_of_uncalled"))],
    ],
    "uc-035-ddq": [
        L(0, "differences", "ddq_compare", {"question": "topic"}, {"y2025": "previous_answer", "y2026": "answer"}, changed=1),
        N(0, "count", "ddq_compare", lambda r: r["changed"]),
    ],
    "uc6-uncalled": [
        F(0, "uncalled_after_call_7", ["called_to_date"], lambda x: tot(x["called_to_date"], "unfunded_after_notice")),
        F(0, "uncalled_register_13_oct_before_call_7_recorded", ["called_to_date"], lambda x: tot(x["called_to_date"], "unfunded_before_notice")),
        D(0, "by_fund", "called_to_date", "fund", "unfunded_after_notice"),
    ],
    "uc-037-distrack": [
        L(0, "rows", "distribution_gap", {"fund": "fund", "pay": "pay_date"}, {"notice": "notice_amount", "received": "received", "gap": "gap"}),
        L(0, "gaps", "distribution_gap", {"fund": "fund", "pay": "pay_date"}, {"notice": "notice_amount", "received": "received", "gap": "gap"}, gap=lambda r: (r["gap"] or 0) > 0),
    ],
    "uc-038-navroll": [
        F(0, "rows", ["nav_rollforward"], lambda x: [{"fund": r["fund"], "quarter": f"{r['period_start']} to {r['period_end']}", "prior": float(r["prior_value"]),
                                                      "calls": float(r["calls"]), "distributions": float(r["distributions"]), "new": float(r["closing_value"]),
                                                      "implied_gain": float(r["implied_gain"])} for r in x["nav_rollforward"]]),
    ],
    "uc-039-irr": [
        D(0, "by_fund", "fund_irr_tvpi", "fund", {"irr_pct_since_1_apr": "irr_pct", "tvpi": "tvpi", "dpi": "dpi", "latest_value": "latest_value", "latest_period": "latest_period"}),
    ],
    "uc-040-icmemo": [
        *[V(0, kf, "memo_support", "value", fund=CV3, figure=fig) for kf, fig in (("commitment", "commitment"), ("called_incl_call_7", "called"), ("unfunded", "unfunded"),
                                                                                 ("latest_value", "latest_value"), ("fee_in_call_7", "fee_in_call"), ("ddq_changes_2025_to_2026", "ddq_changes"))],
        V(0, "latest_period", "memo_support", "as_at", fund=CV3, figure="latest_value"),
        V(0, "statement_kind", "memo_support", "detail", fund=CV3, figure="latest_value"),
    ],
    "uc-041-commitappr": [
        *[V(0, kf, "commit_check", col) for kf, col in (("new_commitment", "new_commitment"), ("uncalled_after", "uncalled_after"), ("cash_usd_equivalent", "cash_usd"),
                                                        ("cash_cover_of_uncalled_after_pct", "cash_cover_pct"))],
    ],
    "uc4-vs-benchmark": [
        *[V(0, kf, "time_weighted_return", col, portfolio=LIQUID, period_kind="month", period_label="2026-09")
          for kf, col in (("portfolio_return_pct", "portfolio_return_pct"), ("benchmark_return_pct", "benchmark_return_pct"), ("active_pct", "active_pct"),
                          ("liquid_aug", "start_value"), ("liquid_sep", "end_value"))],
    ],
    "uc-043-liquidpnl": [
        *[V(0, kf, "liquid_pnl_mtd", col, portfolio=LIQUID) for kf, col in (("value_30_sep", "value_month_end"), ("value_13_oct", "value_today"), ("net_trades_settled", "net_trades"),
                                                                            ("gain_loss_mtd", "gain_loss"), ("gain_pct", "gain_pct"))],
    ],
    "uc-044-twr": [
        F(0, "monthly_pct", ["time_weighted_return"], lambda x: [round(float(r["portfolio_return_pct"]), 4) for r in sorted(x["time_weighted_return"], key=lambda r: r["period_label"])
                                                                 if r["portfolio"] == LIQUID and r["period_kind"] == "month" and r["period_label"] <= SEP30[:7]]),
        V(0, "q2_apr_jun_pct", "time_weighted_return", "portfolio_return_pct", portfolio=LIQUID, period_label="2026Q2"),
        V(0, "q3_jul_sep_pct", "time_weighted_return", "portfolio_return_pct", portfolio=LIQUID, period_label="2026Q3"),
        V(0, "since_1_apr_pct", "time_weighted_return", "portfolio_return_pct", portfolio=LIQUID, period_kind="ytd"),
        V(0, "benchmark_since_1_apr_pct", "time_weighted_return", "benchmark_return_pct", portfolio=LIQUID, period_kind="ytd"),
    ],
    "uc-045-reportpack": [
        N(0, "sections", "report_ready"),
        S(0, "ready", "report_ready", "section", lambda r: r["ready"]),
        S(0, "not_ready", "report_ready", "section", lambda r: not r["ready"]),
        F(0, "share_ready_pct", ["report_ready"], lambda x: x["report_ready"][0]["share_ready_pct"] if x["report_ready"] else None),
    ],
    "uc-046-attrib": [
        *[V(0, kf, "attribution", col, portfolio=LIQUID, month_end=SEP30, asset_class="listed_equity")
          for kf, col in (("portfolio_pct", "portfolio_return_pct"), ("liquid_benchmark_pct", "benchmark_return_pct"), ("active_pct", "active_pct"),
                          ("sum_of_effects_pct", "sum_of_effects_pct"), ("adds_up", "adds_up"))],
        D(0, "effects_pct", "attribution", "asset_class", {"allocation": "allocation_pct", "selection": "selection_pct", "interaction": "interaction_pct"},
          alias={"equity": "listed_equity"}, portfolio=LIQUID, month_end=SEP30),
    ],
    "uc-047-icpack": [
        L(0, "sections", "pack_items", {"section": "section"}, {"owner": ("owner_role", lambda v: PEOPLE.get(v, v))}),
        V(0, "real_breaches", "pack_items", "items", section="Breaches"),
        V(0, "amendments_open", "pack_items", "amendments_open", section="Report"),
    ],
    "uc-048-policyupd": [
        D(0, "max_single_name_pct_by_month_end", "limit_changes", "month_end", "largest_name_pct", is_opening=False, approval_status="approved"),
        *[F(0, f"breaches_at_{n}_pct", ["limit_changes"], lambda x, st=st: sum(1 for r in x["limit_changes"] if r["over_limit"] and not r["is_opening"] and r["approval_status"] == st
                                                                              and str(r["month_end"]) <= SEP30)) for n, st in ((5, "approved"), (6, "proposed"))],
        V(0, "current_limit", "limit_changes", "limit_pct", is_latest=1, approval_status="approved"),
        V(0, "proposed_limit", "limit_changes", "limit_pct", approval_status="proposed", is_latest=1),
    ],
    "uc-049-feedrag": [
        D(0, "by_manager", "fee_drag", "manager", {"fees_paid_via_calls": "fees_paid", "net_gain_since_1_apr": "net_gain", "gross_gain": "gross_gain", "fee_drag_pct": "fee_drag_pct"}),
    ],
    "uc-050-feeinv": [
        L(0, "invoices", "invoice_variance", {"id": "invoice_no"}, {"billed": "billed", "expected": "expected", "variance": "variance", "rate_billed_pct": "rate_billed_pct"}),
        S(0, "overcharged", "invoice_variance", "invoice_no", lambda r: (r["variance"] or 0) > 0),
    ],
}

# Key fields that no recipe is meant to answer: prose, or a value of another as-of (named, never silently dropped).
NOT_A_FIGURE = {
    "uc-007-pacing": ["note"], "uc-041-commitappr": ["budget"], "uc-039-irr": ["basis"], "uc-032-driftrep": ["targets"],
    "uc3-statements-inbox": ["missing.business_days_overdue_9_oct"], "uc2-recon-break-desk": ["cause", "entity", "date"], "uc5-limits": ["hedge_band"],
    "uc-005-benefcheck": [], "uc-033-breachesc": ["holding"], "uc-040-icmemo": ["fund"], "uc-028-interco": [],
}

# card -> what blocks it: a figure no recipe or reader answers yet.
BLOCKED: dict[str, str] = {}


def _process_steps() -> list[dict]:
    """Card 9: the process narrative and the hand-over email read into steps and owners by v3_process, the reader live Harbor uses for a process thread."""
    from sh_platform.v1 import v3_process as P
    names = ("month_end_process_narrative.md", "handover_email_mei_to_raj.txt")
    fig = P.figures([{"file": n, "text": (OFFICE / "reference" / n).read_text(encoding="utf-8")} for n in names])
    return [fig] if fig else []


# figure -> a reader (not a recipe) that answers it; its rows sit beside the recipe rows
READERS = {"process_steps": _process_steps}

OVER_LIMIT = next(iter(yaml.safe_load((OFFICE / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]["uc5-limits"]["questions"].values()))["expected"]["over_limit"]

# The planted mess each card is about: rows (a selector on any recipe row that has those columns) a signal of the card must catch.
# From the MANIFEST's "Mess planted on purpose" (M-codes) and the items the key itself flags.
MESS: dict[str, list[tuple[dict, str]]] = {
    "uc-002-callrecord": [({"fund": "Evergreen Credit III", "call_no": 3}, "M08 fee above terms")],
    "uc-005-benefcheck": [({"fund": CV3, "call_no": 7}, "M05a changed bank account")],
    "uc-006-fxneed": [({"trade_reference": "FXS-20260602-HOLD"}, "M09 conversion with no confirmation")],
    "uc-008-payrun": [({"payee": CV3}, "M05a changed account on call 7"), ({"payee": "Anchorage Custody (synthetic)"}, "M15 invoice above schedule")],
    "uc10-pipeline": [({"old_name": "Market Value"}, "M18 column renamed")],
    "uc5-limits": [({"holding": OVER_LIMIT, "position_date": SEP30}, "key: the names over the single-name limit at 30 Sep (Harborview the largest)")],
    "uc-013-secgaps": [({"instrument": "Pacific Rim Convertible 2029 note"}, "M17 missing class")],
    "uc-015-allowances": [({"member_name": "Ethan Chen"}, "M19b unpaid allowance")],
    "uc-016-schemadrift": [({"old_name": "Market Value"}, "M18 column renamed")],
    "uc-018-fundplan": [({"fund": CV3, "call_no": 7}, "key: call 7 needs a transfer first")],
    "uc3-statements-inbox": [({"fund": "Cedarpoint Opportunities II", "period_end": "2026-06-30"}, "M02 statement missing"),
                             ({"statement_of": "Cedarpoint Opportunities II", "period_end": "2026-06-30"}, "M02 statement missing")],
    "uc1-why-nav-moved": [({"fund": M03}, "M03 amended statements")],
    "uc-021-stale": [({"fund": ["Cedarpoint Ventures III", "Cedarpoint Opportunities II", "Saltmarsh Renewables I"]}, "key: stale values")],
    "uc-022-amendlog": [({"fund": M03}, "M03 amended statements")],
    "uc-023-tieout": [({"report_month": ["2026-04", "2026-05", "2026-06"], "line": ["Evergreen Income II", "Evergreen Growth I"]}, "key: report lines that differ")],
    "uc-024-audit": [({"item": 8}, "key: untraceable sample item")],
    "uc7-manager-diligence": [({"fund": M03}, "M03 amended statements (H1 July restated)"), ({"item_kind": "newsletter"}, "key: Kestrel team change")],
    "uc-026-stmtadmin": [({"fund": ["Evergreen Growth I", "Saltmarsh Infrastructure Fund II", "Kestrel Ridge Macro Fund", "Kestrel Ridge Equity Long/Short Fund",
                                    "Evergreen Growth II", "Evergreen Credit III"]}, "key: statement differs from the administrator")],
    "uc2-recon-break-desk": [({"entity": ["Entity B", "Evergreen Family Trust"], "day": ["2026-10-08", "2026-06-17"]}, "M04 cash break")],
    "uc-029-closeck": [({"step_name": ["Collect manager statements", "Review and approve the report", "Read the report"]}, "key: late close steps")],
    "uc-030-vendors": [({"vendor_name": ["Orchard IT Services", "Quill Research Subscriptions"]}, "key: contracts renewing within 90 days")],
    "uc-031-alloc": [({"asset_class": "unclassified"}, "M17 missing class")],
    "uc-033-breachesc": [({"holding": "Harborview Semiconductor", "position_date": SEP30}, "key: the Harborview breach goes to committee")],
    "uc-035-ddq": [({"topic": ["Number of investment professionals", "Assets under management (USD)", "Key person provision", "Management fee", "Chief operating officer"]},
                    "key: answers changed")],
    "uc-037-distrack": [({"fund": "Evergreen Growth I", "pay_date": "2026-07-16"}, "M19 short-paid distribution")],
    "uc-041-commitappr": [({"deal_name": "Harborlight Ventures Iv"}, "key: no private-markets budget in the policy")],
    "uc-050-feeinv": [({"invoice_no": "FEE-CUST-Q3"}, "M15 invoice above schedule")],
    "uc-038-navroll": [({"fund": "Evergreen Growth I"}, "M19 short-paid distribution (12,500 less, in its latest roll-forward, the quarter to 30 Sep)")],
    "uc-049-feedrag": [({"manager": "Bluewater Capital"}, "M08 fee above terms (Evergreen Credit III call 3)")],
}

# A signal whose document is a row of a recipe under other column names (the event the live loader would raise carries these fields).
DOCS = {
    "uc3-statements-inbox-": ("statement_timeliness", {"fund": "statement_of", "period_end": "period_end", "due_date": "due_date"}),
    "uc-022-amendlog-": ("manager_timeline", {"fund": "fund", "period_end": "period", "status": "status_kind"}),
}

# The root cause a failing recipe points to, as far as its expected-against-got numbers show. Failures are grouped by it; a recipe not named here
# is its own group ("recipe X gives a wrong number").
LATEST = "Reads the latest day (13 Oct), not the 30 Sep month end the key reads"
CASH_IN = "Totals count the cash portfolios; the key's 'all portfolios' leaves cash out"
SOVEREIGN = "The sovereign note counts as a single name (no signed exemption), so every month breaches"
NO_ROWS = "The recipe builds no rows, or does not run, on the loaded office"
FEES = "Management fees billed in call notices are not carried into fee figures"
CAUSE = {
    "single_name_breach": LATEST, "drift_vs_target": LATEST, "identifier_gaps": LATEST,
    "allocation": CASH_IN, "net_worth_after_debt": CASH_IN,
    "limit_changes": SOVEREIGN, "pack_items": SOVEREIGN,
    "notices_open": NO_ROWS, "statement_vs_admin": NO_ROWS, "missing_statements": NO_ROWS,
    "fee_drag": FEES, "memo_support": FEES,
    "time_weighted_return": "No benchmark is linked to the liquid book; 'since 1 April' runs to 13 Oct",
    "fx_rate_check": "A conversion with no confirmation drops out of the FX checks (they are built from confirmations)",
    "fx_confirmation_variance": "A conversion with no confirmation drops out of the FX checks (they are built from confirmations)",
    "payment_batch": "An invoice above its fee schedule is not held in the payment run",
    "commit_check": "Cash for the commitment test counts more than the 12 bank accounts at the 13 Oct fixing",
    "columns_changed": "The renamed-column count is of batches, not months",
    "amendments_open": "The last issued report is its period end, not the day it was issued",
}

FUNCS = {"abs": abs, "min": min, "max": max, "round": round}
PEOPLE = {p["id"]: p["person"] for p in yaml.safe_load((PACK / "use_cases_100.yaml").read_text(encoding="utf-8"))["people"]}


# ---- loading and running ---------------------------------------------------------------------------------------------------------------------

def load(tmp: Path):
    from sh_platform.plane import PlaneStore
    from sh_platform.v1 import v3_office6m_loaders as L, wh
    wh.reset_cache()
    plane = PlaneStore(tmp / "data").create("evergreen")
    report = L.load_plane(plane, OFFICE, TODAY)
    con = wh.connect(plane)
    con.execute("set TimeZone = 'UTC'")
    return plane, con, report


def run_recipes(con) -> tuple[dict, dict, dict]:
    """Every built recipe once: rows, errors (why it cannot be built) and failed tie-outs."""
    from sh_platform.v1 import v3_recipes as R
    rows, errors, ties = {}, {}, {}
    for r in R.recipes():
        rid, name = r["id"], f"t_{r['id']}"
        try:
            sql = R.render(r, name, R.dims_for(r, {}))
            if (why := R.refusal(r, sql)):
                errors[rid] = why
                continue
            con.execute(f"drop table if exists {name}")
            con.execute(sql)
            cur = con.execute(f"select * from {name}")
            cols = [d[0] for d in cur.description]
            rows[rid] = [dict(zip(cols, x)) for x in cur.fetchall()]
            t = R.tie_out(con, r, name)
            if t and not t["ok"]:
                ties[rid] = f"tie-out '{t['label']}' fails: {show(t['a'])} against {show(t['b'])}"
        except Exception as e:  # noqa: BLE001 - a recipe that does not run is a finding, the score goes on
            errors[rid] = str(e).splitlines()[0][:200]
    return rows, errors, ties


def bound(card: dict) -> dict[str, str | None]:
    """Each figure of the card -> the recipe live Harbor binds it to by meaning (v3_recipes.match). A figure the rules leave unbound keeps its own id
    when a recipe has it (the live model question settles those; ponytail: 12 such cards would FAIL on rules alone, w4 follow-up). A rules match wins
    over the id: a figure id can equal a recipe id and still be another figure (cash_break)."""
    from sh_platform.v1 import v3_recipes as R
    ids = {r["id"] for r in R._file()["recipes"]} | set(READERS)
    return {f["id"]: (R.match(f) or {}).get("id") or (f["id"] if f["id"] in ids else None) for f in card["figures"]}


# ---- signals -----------------------------------------------------------------------------------------------------------------------------------

def signals_of(card_id: str, lib: dict) -> list[dict]:
    return [s for i, s in sorted(lib.items()) if i.startswith(card_id + "-")]


def _matches(sel: dict, row: dict) -> bool:
    return all(c in row for c in sel) and bool(pick([row], sel, {}))


def run_signal(plane, sig: dict, card_recipes: list[str], rows: dict, stubs: set) -> dict:
    """Run one signal over every row that is its document. -> {fired: [(row, subject)], skipped: n, why: reason it cannot run or None}."""
    from sh_platform.v1 import v3_signals as S
    fields = [f for i in sig.get("inputs") or [] if i["kind"] == "doc" for f in i["fields"]]
    trig = sig["trigger"]
    rename: dict = {}
    src = None
    if fields:
        over = next((v for k, v in DOCS.items() if sig["id"].startswith(k)), None)
        computed = {"days_past"} if trig.get("on") == "date_passed" else set()
        if over:
            src, rename = over
        elif trig.get("on") == "figure_changed":
            src = trig["figure"]
        else:
            figs = [i["id"] for i in sig.get("inputs") or [] if i["kind"] in ("figure", "recipe")]
            for rid in [*card_recipes, *figs, *rows]:
                if rid in rows and rows[rid] and set(fields) - computed <= set(rows[rid][0]):
                    src = rid
                    break
            if src is None:
                have = set().union(*(set(r[0]) for r in rows.values() if r))
                return {"fired": [], "skipped": 0, "why": f"no reader gives doc.{', doc.'.join(sorted(set(fields) - computed - have)) or ', doc.'.join(fields)}"}
        if src in stubs or src not in rows:
            return {"fired": [], "skipped": 0, "why": f"its rows come from recipe {src}, which is {'a stub' if src in stubs else 'not built'}"}
        if rows[src] and (gone := sorted(set(fields) - computed - set(rename) - set(rows[src][0]))):
            return {"fired": [], "skipped": 0, "why": f"recipe {src} has no column {', '.join(gone)}"}
        docs = rows[src]
    else:
        docs = [{}]
    if trig.get("on") in ("file_arrived", "action_done") and docs and "due_date" in docs[0]:
        docs = [r for r in docs if str(r["due_date"] or "") >= TODAY]  # the event is a notice arriving now, not a replay of the paid ones of the year
    fired, skipped, whys = [], 0, Counter()
    for row in docs:
        doc = {f: row.get(rename.get(f, f)) for f in fields}
        if "days_past" in fields and doc.get("days_past") is None:
            d = next((str(row[c])[:10] for c in ("due_date", "pay_date", "due_on", "expires_on") if row.get(c)), None)
            doc["days_past"] = (date.fromisoformat(TODAY) - date.fromisoformat(d)).days if d else None
        ev = {"doc": doc, "today": TODAY, "facts": {"figures": rows}}
        try:
            ns, _ = S.resolve(plane, sig, ev, FUNCS, [])
            for name, e in (sig.get("let") or {}).items():
                ns[name] = S.calc(e, ns, FUNCS)
            hit = bool(S.calc(sig["condition"], ns, FUNCS))
        except S.Missing as m:
            skipped += 1
            whys[str(m)] += 1
            continue
        except Exception as e:  # noqa: BLE001 - a condition that cannot be worked out on a row is a finding
            skipped += 1
            whys[f"error: {e}"] += 1
            continue
        if hit:
            try:
                subj = S.render(sig.get("subject") or "", ns)
            except Exception:  # noqa: BLE001
                subj = ""
            fired.append((row, subj or sig["id"]))
    why = None
    if skipped == len(docs) and whys:
        w = whys.most_common(1)[0][0]
        why = f"{w} on every row" if not w.startswith("error") else w
        for name in [i.get("id") for i in sig.get("inputs") or [] if i["kind"] in ("figure", "recipe")]:
            if name and name not in rows:
                why = f"needs figure {name}, which {'is a stub recipe' if name in stubs else 'no recipe builds'}"
                break
    return {"fired": fired, "skipped": skipped, "why": why}


def judge_signals(card_id: str, sigs: list[dict], res: dict) -> tuple[list[str], list[str]]:
    """-> (problems, notes). Problems: the planted mess is not caught; an exception signal fires on a clean row."""
    mess = MESS.get(card_id, [])
    problems, notes = [], []
    caught = set()
    for s in sigs:
        r = res[s["id"]]
        exception = bool(s.get("hold"))
        if r["why"]:
            notes.append(f"{s['id']} cannot run: {r['why']}")
            continue
        for row, subj in r["fired"]:
            hits = [why for sel, why in mess if _matches(sel, row)] if row else ([why for _, why in mess] if s.get("severity") != "info" else [])
            if hits and s.get("severity") != "info":
                caught.update(hits)
            elif exception and not hits:
                problems.append(f"{s['id']} fires on a clean row ({subj})")
    for _, why in mess:
        if why not in caught:
            problems.append(f"planted mess not caught by any signal: {why}")
    return sorted(set(problems)), notes


# ---- scoring ----------------------------------------------------------------------------------------------------------------------------------------

def leaves(d, path=""):
    if isinstance(d, dict) and d:
        for k, v in d.items():
            yield from leaves(v, f"{path}.{k}" if path else str(k))
    else:
        yield path


def score() -> dict:
    t0 = time.time()
    from sh_platform.v1 import v3_recipes as R, v3_signals as S
    S.PROVIDER = None  # the recipe rows of this run are the figures; no figure store, no live warehouse lookup
    S.same_fund = lambda plane, a, b, judged: S._norm_name(a) == S._norm_name(b)  # model-free: no judge in a deterministic score
    uc = yaml.safe_load((PACK / "use_cases_100.yaml").read_text(encoding="utf-8"))
    people = {p["id"]: p["person"] for p in uc["people"]}
    cards = sorted((u for u in uc["use_cases"] if u.get("priority") and u["priority"] <= 50), key=lambda u: u["priority"])
    keys = yaml.safe_load((OFFICE / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]
    lib = S._read_dir(PACK / "signals", "pack")
    stubs = {r["id"] for r in R.stubs()}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        plane, con, report = load(Path(tmp))
        t_load = time.time() - t0
        rows, errors, ties = run_recipes(con)
        rows.update({fid: fn() for fid, fn in READERS.items()})
        out = []
        for c in cards:
            out.append(score_card(c, keys.get(c["id"]), rows, errors, ties, stubs, lib, plane, people))
        con.close()
    return {"cards": out, "load_s": t_load, "total_s": time.time() - t0, "recipes": len(rows), "recipe_errors": errors, "ties": ties,
            "not_loaded": {k: v["not_loaded"] for k, v in report.items() if v.get("not_loaded")}}


def score_card(c, key, rows, errors, ties, stubs, lib, plane, people) -> dict:
    cid = c["id"]
    srows = {rid: [{k: iso(v) if isinstance(v, (date, datetime)) else v for k, v in r.items()} for r in rs] for rid, rs in rows.items()}  # dates as the engine's text
    res = {"id": cid, "priority": c["priority"], "title": c["title"], "domain": c["domain"], "person": people.get(c["owner"], c["owner"]), "checks": [],
           "reasons": [], "causes": [], "signal_notes": [], "binding": bound(c)}
    questions = list((key or {}).get("questions", {}).values())
    specs = CHECKS.get(cid, [])
    used = sorted({r for s in specs for r in s["recipes"]})
    res["answered_from"] = used
    if cid in BLOCKED or not key:
        res["result"], res["reasons"] = "BLOCKED", [BLOCKED.get(cid, "no answer key")]
        res["causes"] = [("BLOCKED", BLOCKED.get(cid, "no answer key"), None)]
        sig_res = {s["id"]: run_signal(plane, s, used, srows, stubs) for s in signals_of(cid, lib)}
        res["signal_notes"] = judge_signals(cid, signals_of(cid, lib), sig_res)[1]
        return res
    blocked = [r for r in used if r in stubs or (r not in rows and r not in errors)]
    if blocked:
        res["result"] = "BLOCKED"
        res["reasons"] = [f"recipe {r} is {'a stub (status: stub, no SQL); ' + ('family.yaml shadows the built one in office.yaml' if r == 'allowance_due' else 'not built') if r in stubs else 'not in the pack'}"
                          for r in blocked]
        res["causes"] = [("BLOCKED", f"recipe {r} is a stub, not built", r) for r in blocked]
        return res
    for r in sorted(set(used) | {b for b in res["binding"].values() if b}):
        if r in errors:
            res["reasons"].append(f"recipe {r} does not run: {errors[r]}")
            res["causes"].append(("FAIL", CAUSE.get(r, f"recipe {r} does not run"), r))
        elif r in ties:
            res["reasons"].append(f"recipe {r}: {ties[r]}")
            res["causes"].append(("FAIL", f"recipe {r} does not tie out", r))
    checked = set()
    for s in specs:
        exp = questions[s["q"]]["expected"] if s["q"] < len(questions) else {}
        if any(r in errors for r in s["recipes"]):
            continue
        for path, e, g, ok in s["run"](rows, exp):
            res["checks"].append({"q": s["q"], "path": path, "exp": e, "got": g, "ok": ok, "recipes": s["recipes"]})
            if not ok:
                res["reasons"].append(f"{path}: expected {show(e)}, got {show(g)} ({'/'.join(s['recipes'])})")
                for r in s["recipes"]:
                    res["causes"].append(("FAIL", CAUSE.get(r, f"recipe {r} gives a wrong number"), r))
        checked |= {(s["q"], p) for p in s["paths"]}
    # key values nobody checked: named, so a gap in the mapping is visible
    skip = set(NOT_A_FIGURE.get(cid, []))
    left = [f"q{qi + 1}.{p}" for qi, q in enumerate(questions) for p in leaves(q["expected"])
            if p not in skip and not any(cq == qi and (cp == "" or p == cp or p.startswith(cp + ".") or p.startswith(cp + "[")) for cq, cp in checked)]
    res["unchecked"] = left
    sigs = signals_of(cid, lib)
    sig_res = {s["id"]: run_signal(plane, s, used, srows, stubs) for s in sigs}
    res["fired"] = {i: [subj for _, subj in r["fired"]] for i, r in sig_res.items()}
    problems, notes = judge_signals(cid, sigs, sig_res)
    res["signal_notes"] = notes
    res["binding_gap"] = [f for f, b in res["binding"].items() if b is None or b not in used] if used else []
    for f in res["binding_gap"]:  # live Harbor answers a figure from the recipe it is bound to, so an unbound or wrongly bound figure is a wrong answer
        b = res["binding"][f]
        res["reasons"].append(f"figure {f} is bound to {b or 'no recipe'}, not to a recipe that answers the key ({', '.join(used)})")
        res["causes"].append(("FAIL", f"figure {f} is {'bound to ' + b if b else 'bound to no recipe'}, not to the recipe that answers its key", b))
    nums_ok = not res["reasons"]
    if nums_ok and problems:
        res["result"], res["reasons"] = "SIGNAL", problems
        res["causes"] = [("SIGNAL", _sig_cause(p), None) for p in problems]
    else:
        res["result"] = "PASS" if nums_ok else "FAIL"
        res["signal_problems"] = problems
    bnd = [f"{f} -> {b or 'no recipe'}" for f, b in res["binding"].items()]
    res["binding_text"] = "; ".join(bnd)
    return res


def _sig_cause(p: str) -> str:
    if p.startswith("planted mess not caught"):
        return "planted mess not caught by a signal"
    return "exception signal fires on a clean row: " + p.split(" fires")[0]


# ---- the scorecard ----------------------------------------------------------------------------------------------------------------------------------

def _cell(v) -> str:
    return show(v).replace("|", "/")


def write(r: dict) -> str:
    cards = r["cards"]
    tot_ = Counter(c["result"] for c in cards)
    order = ["PASS", "FAIL", "SIGNAL", "BLOCKED"]
    L_: list[str] = []
    w = L_.append
    w("# Score of the top 50 use cases")
    w("")
    w(f"Written by `python tools/score50.py` on {datetime.now():%Y-%m-%d %H:%M}. Office: tests/v1/fixtures/office6m as of {TODAY}, loaded once with the real loader "
      f"(v3_office6m_loaders.load_plane); {r['recipes']} built recipes run once; keys from answer_keys.yaml; signals from packs/family_office/1/signals. "
      f"Deterministic: no model is called. Load {r['load_s']:.0f} s, whole run {r['total_s']:.0f} s.")
    w("")
    w("PASS: every key value matches and the signals behave. FAIL: a number is wrong, or a recipe the card needs does not run or tie out. "
      "SIGNAL: the numbers are right but the planted mess is not caught, or an exception signal fires on a clean row. BLOCKED: needs something that does not exist yet.")
    w("")
    w("## Totals")
    w("")
    w("| PASS | FAIL | SIGNAL | BLOCKED | Cards |")
    w("|---|---|---|---|---|")
    w(f"| {tot_['PASS']} | {tot_['FAIL']} | {tot_['SIGNAL']} | {tot_['BLOCKED']} | {len(cards)} |")
    nchk = sum(len(c.get("checks", [])) for c in cards)
    nok = sum(1 for c in cards for x in c.get("checks", []) if x["ok"])
    w("")
    w(f"Key values compared: {nchk}, matching: {nok}.")
    for title, field in (("By domain", "domain"), ("By person (card owner)", "person")):
        w("")
        w(f"## {title}")
        w("")
        w("| " + title.split(" ")[1].capitalize() + " | " + " | ".join(order) + " | Cards |")
        w("|---" * (len(order) + 2) + "|")
        groups = defaultdict(Counter)
        for c in cards:
            groups[c[field]][c["result"]] += 1
        for g in sorted(groups, key=lambda g: (-groups[g]["PASS"] / sum(groups[g].values()), g)):
            w(f"| {g} | " + " | ".join(str(groups[g][o]) for o in order) + f" | {sum(groups[g].values())} |")
    w("")
    w("## Failures by root cause, worst first")
    w("")
    w("A card can sit under more than one cause. The cause is what the expected-against-got numbers of the card detail point to.")
    w("")
    causes, recs = defaultdict(set), defaultdict(set)
    for c in cards:
        for kind, cause, rid in c["causes"]:
            causes[(kind, cause)].add(c["priority"])
            if rid:
                recs[(kind, cause)].add(rid)
    for i, ((kind, cause), ps) in enumerate(sorted(causes.items(), key=lambda kv: (-len(kv[1]), kv[0])), 1):
        rs = f" Recipes: {', '.join(sorted(recs[(kind, cause)]))}." if recs[(kind, cause)] else ""
        w(f"{i}. **{cause}**. {kind}, {len(ps)} card(s): {', '.join(str(p) for p in sorted(ps))}.{rs}")
    gaps = [c for c in cards if c.get("binding_gap")]
    if gaps:
        w("")
        w(f"Binding gaps (scored as FAIL): {len(gaps)} card(s) have a figure that is bound to no recipe, or to a recipe other than the one that answers the key "
          "(live Harbor would design a table for it, or answer from the other recipe): " + ", ".join(f"{c['priority']} ({', '.join(c['binding_gap'])})" for c in gaps) + ".")
    w("")
    w("## Every card")
    w("")
    w("| # | Card | Domain | Person | Result | Keys ok | Reason |")
    w("|---|---|---|---|---|---|---|")
    for c in cards:
        ck = c.get("checks", [])
        why = "; ".join(c["reasons"][:6]) + (f"; and {len(c['reasons']) - 6} more" if len(c["reasons"]) > 6 else "")
        w(f"| {c['priority']} | {c['id']}: {c['title']} | {c['domain']} | {c['person']} | **{c['result']}** | {sum(x['ok'] for x in ck)}/{len(ck)} | {why.replace('|', '/') or 'all key values match; signals behave'} |")
    w("")
    w("## Per card detail")
    w("")
    for c in cards:
        w(f"### {c['priority']}. {c['id']}: {c['result']}")
        w("")
        w(f"Figures bound: {c.get('binding_text') or '-'}. Answered from: {', '.join(c.get('answered_from') or []) or '-'}.")
        bad = [x for x in c.get("checks", []) if not x["ok"]]
        if bad:
            w("")
            w("| Key value | Expected | Got | Recipe |")
            w("|---|---|---|---|")
            for x in bad:
                w(f"| q{x['q'] + 1} {x['path']} | {_cell(x['exp'])} | {_cell(x['got'])} | {'/'.join(x['recipes'])} |")
        if c["result"] == "BLOCKED":
            w("")
            w("Blocked: " + "; ".join(c["reasons"]))
        if c.get("unchecked"):
            w("")
            w("Key values not compared (no column answers them yet): " + ", ".join(c["unchecked"]) + ".")
        if c.get("fired"):
            w("")
            w("Signals fired: " + ("; ".join(f"{i} x{len(v)}" for i, v in c["fired"].items() if v) or "none") + ".")
        probs = c.get("signal_problems") or ([x for x in c["reasons"]] if c["result"] == "SIGNAL" else [])
        if probs:
            w("")
            w("Signal problems: " + "; ".join(probs) + ".")
        if c.get("signal_notes"):
            w("")
            w("Signals that cannot run on the loaded data: " + "; ".join(c["signal_notes"]) + ".")
        w("")
    if r["recipe_errors"] or r["not_loaded"]:
        w("## The run itself")
        w("")
        for rid, e in sorted(r["recipe_errors"].items()):
            w(f"- Recipe {rid} does not run: {e}")
        for k, v in sorted(r["not_loaded"].items()):
            w(f"- Loader, {k}: {'; '.join(v[:3])}")
        w("")
    return "\n".join(L_)


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    for noisy in ("sh_platform", "duckdb"):
        logging.getLogger(noisy).setLevel(logging.ERROR)
    try:
        r = score()
    except Exception:  # noqa: BLE001 - exit 0 always; say what broke
        log.exception("score50 could not run")
        print("score50: could not run (see the error above)")
        return 0
    OUT.write_text(write(r) + "\n", encoding="utf-8")
    t = Counter(c["result"] for c in r["cards"])
    print(f"PASS {t['PASS']}  FAIL {t['FAIL']}  SIGNAL {t['SIGNAL']}  BLOCKED {t['BLOCKED']}  of {len(r['cards'])} cards  "
          f"({r['total_s']:.0f} s)  -> {OUT.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
