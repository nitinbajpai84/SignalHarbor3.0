"""Score the top 50 use cases on the six-month Evergreen Office: one fast, deterministic run before the slow live runs.

    python tools/score50.py            -> docs/v3/SCORE50.md, totals printed, exit 0 always
    python tools/score50.py --all      -> docs/v3/SCORE100.md, all 100 cards (cards 51 to 100 have no priority; their order number is their card number)

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
OUT100 = REPO / "docs" / "v3" / "SCORE100.md"  # python tools/score50.py --all: all 100 cards
CLEAN_NOTES = False  # --all: also note each non-info signal firing on a row with no planted mess (notes only, the verdict is not changed)
TODAY = "2026-10-13"
HARBORLIGHT = "Harborlight Ventures IV"  # cards 34 and 41 screen this teaser; the pipeline csv (card 77) holds four other deals, one row each
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
        *[V(0, kf, "mandate_fit", col, deal_name=HARBORLIGHT) for kf, col in (("minimum_ticket", "ticket"), ("asset_class", "asset_class"), ("policy_limit_for_private_markets", "private_markets_limit_pct"),
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
        *[V(0, kf, "commit_check", col, deal_name=HARBORLIGHT) for kf, col in (("new_commitment", "new_commitment"), ("uncalled_after", "uncalled_after"), ("cash_usd_equivalent", "cash_usd"),
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
    "uc-041-commitappr": [({"budget_status": "not set"}, "key: no private-markets budget in the policy")],  # every deal under review: the policy signs no budget
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


# ---- cards 51 to 100 (--all) ------------------------------------------------------------------------------------------------------------------
# The mapping is the builders' own tests (tests/v1/test_w1b_*.py): each key value is the column the test compares it with. Recipes and columns
# are the ones the recipe really outputs. Where a test compares a key with a recipe through a rule, the rule is written here as a row selector.
# The planted mess is the MANIFEST's M-code (tests/v1/fixtures/office6m/MANIFEST.md) or the key's own flagged item, as in the top 50.

def FIRST(q, path, rid, col):
    """A column that repeats on every row of a recipe (a total, a flag of the run): its value on the first row."""
    return F(q, path, [rid], lambda x: x[rid][0][col] if x[rid] else None)


def FIRST_WHERE(q, path, rid, col, pred):
    return F(q, path, [rid], lambda x: next((r[col] for r in x[rid] if pred(r)), None))


def _pinnacle(r) -> bool:
    return str(r["feed"]).startswith("pinnacle")


def _by_fund(x) -> dict:
    rows, out = x["expected_distributions"], {}
    for r in rows:
        if r["row_kind"] == "fund_total":
            qs = sorted((q for q in rows if q["row_kind"] == "fund_quarter" and q["fund"] == r["fund"]), key=lambda q: str(q["quarter_end"]))
            out[r["fund"]] = {"latest_value": float(r["latest_value"]), "valuation_date": str(r["valuation_date"]), "total": float(r["amount"]),
                              "payout_pct": [round(float(q["payout_pct"]), 2) for q in qs], "amounts": [round(float(q["amount"]), 2) for q in qs]}
    return out


_ENT54 = ("Evergreen Holdings", "Evergreen Family Trust", "Entity B")
_WALK = ["investment_gains", "liquid_book_gain", "private_and_hedge_fund_gain", "spending", "closing", "capital_calls_paid", "distributions_received"]
_LOT = {"security": "security", "acquired": "acquired", "days_held": "days_held", "quantity": "quantity", "cost": "cost", "value": "value", "gain": "gain"}

CHECKS.update({
    "uc8-trades-vs-admin": [  # card 51, operate; test_w1b_operate.py test_card51_*
        L(0, "october_trade_breaks", "trade_breaks", {"trade": "trade"}, {"kind": "break_kind", "ours": "our_quantity", "administrator": "administrator_quantity",
                                                                          "difference_usd": "difference_amount", "amount": "difference_amount"}, breaks=True, exact=False),
        S(0, "trade_booked_twice_in_export", "trade_breaks", "trade", lambda r: r["break_kind"] == "booked twice"),
        V(0, "difference_sgd", "fx_confirmation_variance", "variance", trade_reference="FXF-2026-002"),
    ],
    "uc-052-insurance": [  # card 52, renewals_due; test_w1b_office.py test_card52_*
        L(0, "all_policies", "renewals_due", {"policy": "policy"}, {"name": "policy_name", "next_renewal": "next_renewal_date", "days_left": "days_left",
                                                                   "sum_insured": "sum_insured", "premium": "premium", "currency": "currency",
                                                                   "renewal_notice_received": "renewal_notice_received"}),
        L(0, "expiring_in_60_days", "renewals_due", {"policy": "policy"}, {"days_left": "days_left", "sum_insured": "sum_insured", "premium": "premium"}, due_in_60_days=True),
        N(0, "count", "renewals_due", lambda r: r["due_in_60_days"]),
    ],
    "uc-054-ladder": [  # card 54, liquidity_ladder (+ cash_by_entity for the cash lines); test_w1b_cash.py test_54_*
        *[V(0, f"by_entity.{e}.windows.{w}.{kf}", "liquidity_ladder", col, entity=e, window_days=w)
          for e in _ENT54 for w in (30, 60, 90) for kf, col in (("calls", "calls"), ("approved_and_scheduled_payments", "approved_and_scheduled_payments"),
                                                                 ("cash_after", "cash_after"), ("below_buffer", "below_buffer"))],
        *[V(0, f"by_entity.{e}.cash_usd_equivalent", "liquidity_ladder", "cash_usd_equivalent", entity=e, window_days=30) for e in _ENT54],
        *[V(0, f"by_entity.{e}.cash_usd", "cash_by_entity", "cash", entity=e, currency="USD", position_date=TODAY) for e in _ENT54],
        *[V(0, f"by_entity.{e}.cash_sgd", "cash_by_entity", "cash", entity=e, currency="SGD", position_date=TODAY) for e in _ENT54],
    ],
    "uc-070-idle": [  # card 70, idle_cash (window: signed ladder_window_days, A50); test_w1b_cash.py test_70_*
        *[V(0, f"by_entity.{e}.{kf}", "idle_cash", col, entity=e) for e in _ENT54
          for kf, col in (("cash_usd_equivalent", "cash_usd_equivalent"), ("outflow_90_days", "outflow"), ("buffer", "buffer"), ("idle", "idle"), ("short", "short"))],
        FIRST(0, "total_idle", "idle_cash", "total_idle"),
        FIRST(0, "total_short", "idle_cash", "total_short"),
    ],
    "uc-055-corpact": [  # card 55, actions_next_14d; test_w1b_hold.py test_55_*
        F(0, "window", ["actions_next_14d"], lambda x: [str(x["actions_next_14d"][0]["window_from"]), str(x["actions_next_14d"][0]["window_to"])]),
        L(0, "to_book", "actions_next_14d", {"security": "security"}, {"event": "event", "ex_date": "ex_date", "pay_date": "pay_date", "quantity": "quantity",
                                                                       "expected_cash": "expected_cash"}, bucket="book"),
        FIRST_WHERE(0, "cash_to_book", "actions_next_14d", "cash_to_book", lambda r: r["cash_to_book"] is not None),
        L(0, "to_decide", "actions_next_14d", {"security": "security"}, {"respond_by": "respond_by", "offer_price": "offer_price", "last_price": "last_price",
                                                                         "premium_pct": "premium_pct", "quantity_held": "quantity"}, bucket="decide"),
        L(0, "announced_outside_window", "actions_next_14d", {"security": "security"}, {"event": "event", "ex_date": "ex_date", "pay_date": "pay_date",
                                                                                       "quantity": "quantity", "expected_cash": "expected_cash"}, bucket="later"),
    ],
    "uc-056-custrecon": [  # card 56, position_break; test_w1b_operate.py test_card56_*
        N(0, "holdings_compared", "position_break", lambda r: r["administrator_quantity"] is not None and r["custodian_quantity"] is not None),
        L(0, "breaks", "position_break", {"security": "security"}, {"administrator_qty": "administrator_quantity", "custodian_qty": "custodian_quantity",
                                                                   "difference": "difference_quantity", "value_usd": "difference_value", "reason": "reason"}, breaks=True),
    ],
    "uc-058-settle": [  # card 58, unsettled_trades; test_w1b_operate.py test_card58_*
        N(0, "count", "unsettled_trades", lambda r: r["unsettled"]),
        L(0, "failed", "unsettled_trades", {"trade": "trade"}, {"security": "security", "side": "side", "quantity": "quantity", "amount": "amount",
                                                                "settle_date": "settle_date", "business_days_late": "business_days_late", "chase": "chase",
                                                                "reason": "reason", "cash_booked": "cash_booked"}, unsettled=True),
        F(0, "chase_counterparties", ["unsettled_trades"], lambda x: sorted({r["chase"] for r in x["unsettled_trades"] if r["unsettled"]})),
    ],
    "uc-059-breakage": [  # card 59, break_age; test_w1b_operate.py test_card59_*
        L(0, "all_open", "break_age", {"id": "break_id"}, {"type": "break_type", "entity": "entity", "subject": "subject", "detected": "detected",
                                                           "age_business_days": "age_business_days"}),
        L(0, "cash_breaks_over_5_days", "break_age", {"id": "break_id"}, {"type": "break_type"}, break_type="cash break", over_five_business_days=True),
        N(0, "open_cash_breaks", "break_age", lambda r: r["break_type"] == "cash break"),
    ],
    "uc-060-docinbox": [  # card 60, unrecognised_files; test_w1b_operate.py test_card60_*
        N(0, "files", "unrecognised_files"),
        L(0, "recognised", "unrecognised_files", {"file": "file"}, {"belongs_in": "belongs_in"}, recognition="recognised"),
        L(0, "unrecognised", "unrecognised_files", {"file": "file"}, {"belongs_in": "belongs_in"}, recognition="unrecognised"),
    ],
    "uc-061-dqscore": [  # card 61, source_quality; test_w1b_operate.py test_card61_*
        L(0, "by_source", "source_quality", {"source": "source"}, {"loads": "loads", "passed": "passed", "late_or_missing": "late_or_missing",
                                                                   "did_not_add_up": "did_not_add_up", "manual_fixes": "manual_fixes", "score_pct": "score_pct"}),
        FIRST_WHERE(0, "fix_first", "source_quality", "source", lambda r: r["fix_first"]),
    ],
    "uc-062-fxlife": [  # card 62, fx_mtm; test_w1b_operate.py test_card62_*
        L(0, "forwards", "fx_mtm", {"id": "trade"}, {"value_date": "value_date", "days_to_value": "days_to_value", "sell_usd": "sell_amount", "buy_sgd": "buy_amount",
                                                     "contract_rate": "contract_rate", "spot": "spot", "mtm_usd": "mtm_usd", "confirmation_status": "confirmation_status"}),
        F(0, "due_within_30_days", ["fx_mtm"], lambda x: [r["trade"] for r in x["fx_mtm"] if r["due_within_30_days"]]),
        F(0, "total_usd_to_deliver", ["fx_mtm"], lambda x: round(sum(float(r["usd_to_deliver"]) for r in x["fx_mtm"]), 2)),
        F(0, "next_value_date", ["fx_mtm"], lambda x: str(min(r["value_date"] for r in x["fx_mtm"]))),
        V(0, "trust_usd_cash", "cash_by_entity", "cash", entity="Evergreen Family Trust", currency="USD", position_date=TODAY),
        F(0, "trust_usd_shortfall", ["fx_mtm", "cash_by_entity"], lambda x: round(sum(float(r["usd_to_deliver"]) for r in x["fx_mtm"]) - sum(
            float(r["cash"]) for r in x["cash_by_entity"] if r["entity"] == "Evergreen Family Trust" and r["currency"] == "USD" and str(r["position_date"]) == TODAY), 2)),
    ],
    "uc-057-pricecheck": [  # card 57, price_gap_pct; test_w1b_operate.py test_card57_*
        FIRST_WHERE(0, "tolerance_pct", "price_gap_pct", "tolerance_pct", lambda r: r["tolerance_pct"] is not None),
        N(0, "prices_compared", "price_gap_pct", lambda r: r["our_price"] is not None),
        L(0, "over_tolerance", "price_gap_pct", {"security": "security", "date": "date"}, {"administrator_price": "our_price", "second_source_price": "second_source_price",
                                                                                           "gap_pct": "gap_pct"}, over_tolerance=1),
    ],
    "uc-063-cashcode": [  # card 63, uncoded_bank_lines; test_w1b_operate.py test_card63_*
        L(0, "uncoded", "uncoded_bank_lines", {"account": "account", "date": "date"}, {"amount": "amount", "description": "description"}),
        N(0, "count", "uncoded_bank_lines"),
        F(0, "net_amount", ["uncoded_bank_lines"], lambda x: tot(x["uncoded_bank_lines"], "amount")),
    ],
    "uc-064-fxexp": [  # card 64, currency_exposure; test_w1b_hold.py test_64_*
        V(0, "sgd_cash", "currency_exposure", "cash", currency="SGD"),
        V(0, "sgd_cash_usd_eq", "currency_exposure", "spot_usd_eq", currency="SGD"),
        V(0, "sgd_bought_forward", "currency_exposure", "fwd_bought", currency="SGD"),
        V(0, "sgd_forward_usd_eq", "currency_exposure", "fwd_bought_usd_eq", currency="SGD"),
        V(0, "net_sgd_exposure_usd_eq", "currency_exposure", "after_usd_eq", currency="SGD"),
        V(0, "share_of_family_pct", "currency_exposure", "share_after_pct", currency="SGD"),
        V(0, "usd_exposure_usd_eq", "currency_exposure", "spot_usd_eq", currency="USD"),
        V(0, "family_total_usd_eq", "currency_exposure", "family_total_usd_eq", currency="SGD"),
    ],
    "uc-065-realassets": [  # card 65, real_asset_value; test_w1b_hold.py test_65_*
        L(0, "assets", "real_asset_value", {"id": "asset_ref"}, {"name": "asset_name", "type": "asset_type", "entity": "entity", "latest_value": "latest_value",
                                                                 "currency": "currency", "value_usd": "value_usd", "appraised": "appraised_on",
                                                                 "title_holder": "title_holder"}),
        FIRST(0, "total_usd", "real_asset_value", "total_usd"),
        F(0, "by_type", ["real_asset_value"], lambda x: {r["asset_type"]: float(r["type_total_usd"]) for r in x["real_asset_value"]}),
        F(0, "by_entity", ["real_asset_value"], lambda x: {r["entity"]: float(r["entity_total_usd"]) for r in x["real_asset_value"]}),
        S(0, "title_not_in_entity_name", "real_asset_value", "asset_name", lambda r: r["title_differs"]),
    ],
    "uc-066-propreval": [  # card 66, appraisal_age; test_w1b_hold.py test_66_*
        L(0, "by_asset", "appraisal_age", {"id": "asset_ref"}, {"name": "asset_name", "appraised": "appraised_on", "age_days": "age_days", "due": "due"}),
        F(0, "order_new", ["appraisal_age"], lambda x: x["appraisal_age"][0]["due_names"].split(", ") if x["appraisal_age"] else []),
    ],
    "uc-067-unrl": [  # card 67, unrealised_gain; test_w1b_hold.py test_67_*
        FIRST(0, "lots", "unrealised_gain", "lots"),
        FIRST(0, "total_unrealised_gain", "unrealised_gain", "total_gain"),
        FIRST(0, "total_unrealised_loss", "unrealised_gain", "total_loss"),
        L(0, "loss_lots", "unrealised_gain", {"lot": "lot"}, _LOT, is_loss=True),
        L(0, "largest_gain_lots", "unrealised_gain", {"lot": "lot"}, _LOT, exact=False),
        L(0, "harborview_lots", "unrealised_gain", {"lot": "lot"}, _LOT, exact=False),
        F(0, "gain_by_security", ["unrealised_gain"], lambda x: {r["security"]: float(r["holding_gain"]) for r in x["unrealised_gain"]}),
    ],
    "uc-068-incomef": [  # card 68, income_forecast; test_w1b_hold.py test_68_*
        F(0, "period", ["income_forecast"], lambda x: [str(next(r for r in x["income_forecast"] if r["first_row"])["period_from"]),
                                                       str(next(r for r in x["income_forecast"] if r["first_row"])["period_to"])]),
        FIRST_WHERE(0, "total", "income_forecast", "total", lambda r: r["first_row"]),
        FIRST_WHERE(0, "coupons", "income_forecast", "coupons", lambda r: r["first_row"]),
        FIRST_WHERE(0, "dividends", "income_forecast", "dividends", lambda r: r["first_row"]),
        FIRST_WHERE(0, "events", "income_forecast", "events", lambda r: r["first_row"]),
        F(0, "by_quarter", ["income_forecast"], lambda x: {r["quarter"]: float(r["quarter_total"]) for r in x["income_forecast"]}),
    ],
    "uc-069-lookthru": [  # card 69, lookthrough_exposure; test_w1b_hold.py test_69_*
        L(0, "top_companies", "lookthrough_exposure", {"company": "company"}, {"through_funds": "through_funds", "funds": "funds", "share_of_family_pct": "share_of_family_pct"},
          rank=lambda r: r["rank"] <= 5),
        S(0, "companies_in_more_than_one_fund", "lookthrough_exposure", "company", lambda r: r["in_several_funds"]),
        F(0, "by_sector", ["lookthrough_exposure"], lambda x: {r["sector"]: float(r["sector_through_funds"]) for r in x["lookthrough_exposure"]}),
        V(0, "harborview_direct", "lookthrough_exposure", "direct_value", company="Harborview Semiconductor"),
        V(0, "harborview_through_funds", "lookthrough_exposure", "through_funds", company="Harborview Semiconductor"),
        V(0, "harborview_direct_pct_of_liquid_book", "lookthrough_exposure", "direct_pct_of_liquid_book", company="Harborview Semiconductor"),
        V(0, "harborview_with_funds_pct_of_liquid_book", "lookthrough_exposure", "with_funds_pct_of_liquid_book", company="Harborview Semiconductor"),
        FIRST(0, "family_investments", "lookthrough_exposure", "family_investments"),
    ],
    "uc-071-expdist": [  # card 71, expected_distributions; test_w1b_invest.py test_card71_*
        F(0, "by_quarter", ["expected_distributions"], lambda x: {str(r["quarter_end"]): float(r["amount"]) for r in x["expected_distributions"] if r["row_kind"] == "quarter_total"}),
        F(0, "total_next_4_quarters", ["expected_distributions"], lambda x: next(float(r["amount"]) for r in x["expected_distributions"] if r["row_kind"] == "total")),
        F(0, "by_fund", ["expected_distributions"], _by_fund),
    ],
    "uc-073-runway": [  # card 73, cash_runway; test_w1b_cash.py test_73_*
        F(0, "six_month_spend_by_category", ["cash_runway"], lambda x: {r["category"]: float(r["spend_usd"]) for r in x["cash_runway"]}),
        FIRST(0, "cash_usd_eq", "cash_runway", "cash_usd_eq"),
        FIRST(0, "average_monthly_spend", "cash_runway", "average_monthly_spend"),
        FIRST(0, "months_of_cash", "cash_runway", "months_of_cash"),
        FIRST(0, "months_of_cash_and_liquid_book", "cash_runway", "months_of_cash_and_liquid_book"),
        FIRST(0, "liquid_book", "cash_runway", "liquid_book"),
    ],
    "uc-074-boardpack": [  # card 74, board_summary; test_w1b_report.py test_card_74_*
        V(0, "net_worth_usd", "board_summary", "net_worth_usd"),
        V(0, "net_worth_sgd", "board_summary", "net_worth_sgd"),
        V(0, "net_worth_status", "board_summary", "estimate_note"),
        V(0, "liquid_book_q3_return_pct", "board_summary", "last_quarter_return_pct"),
        V(0, "benchmark_since_1_apr_pct", "board_summary", "since_start_benchmark_pct"),
        V(0, "cash_usd_eq", "board_summary", "cash_usd_eq"),
        V(0, "call_7_shortfall_usd", "board_summary", "call_shortfall_usd"),
        V(0, "uncalled_commitments", "board_summary", "uncalled_commitments_usd"),
        V(0, "statements_amended_after_last_report", "board_summary", "amendments_after_report"),
    ],
    "uc-075-yearwalk": [  # card 75, networth_walk; test_w1b_report.py test_card_75_*
        *[V(0, n, "networth_walk", n) for n in _WALK + ["opening", "income", "fx_and_other"]],
        F(0, "period", ["networth_walk"], lambda x: [str(x["networth_walk"][0]["period_from"]), str(x["networth_walk"][0]["period_to"])]),
    ],
    "uc-080-vintage": [  # card 80, vintage_split; test_w1b_invest.py test_card80_*
        F(0, "by_year", ["vintage_split"], lambda x: {str(r["vintage_year"]): {"commitment": float(r["commitment"]), "share_pct": float(r["share_pct"]),
                                                                              "funds": sorted(str(r["funds"]).split("; "))}
                                                      for r in x["vintage_split"] if not r["is_total"]}),
        V(0, "total", "vintage_split", "commitment", is_total=True),
        F(0, "largest_year", ["vintage_split"], lambda x: str(next(r["vintage_year"] for r in x["vintage_split"] if r["is_largest"]))),
        F(0, "largest_share_pct", ["vintage_split"], lambda x: float(next(r["share_pct"] for r in x["vintage_split"] if r["is_largest"]))),
    ],
    "uc-081-payroll": [  # card 81, payroll_total; test_w1b_office.py test_card81_*
        FIRST(0, "draft_net", "payroll_total", "run_net"),
        FIRST(0, "draft_employer_cpf", "payroll_total", "run_employer"),
        FIRST(0, "draft_total_cost", "payroll_total", "run_total_cost"),
        FIRST(0, "september_net", "payroll_total", "previous_net"),
        FIRST(0, "september_total_cost", "payroll_total", "previous_total_cost"),
        FIRST(0, "september_net_paid_per_bank", "payroll_total", "previous_net_paid_per_bank"),
        FIRST(0, "change_pct", "payroll_total", "change_pct"),
        FIRST(0, "release", "payroll_total", "release"),
        F(0, "flags", ["payroll_total"], lambda x: sorted(r["employee_name"] for r in x["payroll_total"] if r["flagged"]),
          kf=lambda e: sorted(f["employee"].split(" (")[0] for f in e)),
    ],
    "uc-082-covergap": [  # card 82, cover_gap; test_w1b_office.py test_card82_*
        L(0, "by_asset", "cover_gap", {"asset": "asset"}, {"appraised_usd": "appraised_usd", "insured_usd": "insured_usd", "gap_usd": "gap_usd", "status": "status"}),
        F(0, "total_gap_usd", ["cover_gap"], lambda x: round(sum(float(r["gap_usd"]) for r in x["cover_gap"]), 2)),
        S(0, "under_insured", "cover_gap", "asset", lambda r: r["under_insured"]),
        S(0, "no_policy", "cover_gap", "asset", lambda r: r["no_policy"]),
    ],
    "uc-091-jml": [  # card 91, access_review; test_w1b_office.py test_card91_*
        L(0, "granted_without_approver", "access_review", {"person": "person", "system": "system"}, {"permission": "permission"}, no_approver=True),
        F(0, "leaver", ["access_review"], lambda x: ", ".join(sorted({r["person"] for r in x["access_review"] if r["leaver"]}))),
        F(0, "leaver_access_to_remove", ["access_review"], lambda x: sorted(r["system"] for r in x["access_review"] if r["leaver"])),
        F(0, "joiner", ["access_review"], lambda x: ", ".join(sorted({r["person"] for r in x["access_review"] if r["joiner_not_requested"]}))),
        F(0, "joiner_access_not_requested", ["access_review"], lambda x: sorted(r["system"] for r in x["access_review"] if r["joiner_not_requested"])),
    ],
    "uc-092-accessrev": [  # card 92, access_review; test_w1b_office.py test_card92_*
        N(0, "grants_reviewed", "access_review"),
        L(0, "not_used_in_90_days", "access_review", {"person": "person", "system": "system"}, {"last_used": "last_used_on", "days_unused": "days_unused"}, unused_90=True),
        N(0, "count", "access_review", lambda r: r["unused_90"]),
    ],
    "uc-093-onbmgr": [  # card 93, onboarding_items; test_w1b_office.py test_card93_*
        FIRST(0, "items", "onboarding_items", "items"),
        FIRST(0, "complete", "onboarding_items", "complete_items"),
        FIRST(0, "ready", "onboarding_items", "ready"),
        S(0, "missing", "onboarding_items", "item", lambda r: not r["complete"]),
    ],
    "uc-095-sopreview": [  # card 95, sop_age; test_w1b_office.py test_card95_*
        L(0, "sops", "sop_age", {"sop": "sop"}, {"owner": "owner", "last_reviewed": "last_reviewed", "age_days": "age_days", "due": "due"}),
        F(0, "to_review", ["sop_age"], lambda x: [r["sop"] for r in sorted(x["sop_age"], key=lambda r: -r["age_days"]) if r["due"]]),
    ],
    "uc-097-kycrefresh": [  # card 97, kyc_expiry; test_w1b_office.py test_card97_*
        N(0, "documents", "kyc_expiry"),
        L(0, "expiring_in_90_days", "kyc_expiry", {"document": "document", "counterparty": "counterparty"},
          {"entity": "entity", "expires": "expires_on", "days_left": "days_left"}, expiring_90=True),
        L(0, "expired", "kyc_expiry", {"document": "document", "counterparty": "counterparty"},
          {"entity": "entity", "expires": "expires_on", "days_left": "days_left"}, expired=True),
    ],
    "uc-098-wordlist": [  # card 98, terms_proposed; test_w1b_office.py test_card98_*
        N(0, "distinct_terms", "terms_proposed"),
        S(0, "proposed", "terms_proposed", "term"),
        FIRST(0, "proposals_made", "terms_proposed", "proposals_made"),
        FIRST(0, "list_size", "terms_proposed", "list_size"),
        S(0, "already_in_list", "terms_proposed", "term", lambda r: r["in_list"]),
        S(0, "to_add", "terms_proposed", "term", lambda r: r["to_add"]),
    ],
    "uc-099-newfeed": [  # card 99, feed_mapping (the pinnacle feed); test_w1b_operate.py test_card99_*
        F(0, "columns", ["feed_mapping"], lambda x: next(r["columns"] for r in x["feed_mapping"] if _pinnacle(r))),
        FIRST_WHERE(0, "mapped_with_confidence", "feed_mapping", "mapped_with_confidence", _pinnacle),
        FIRST_WHERE(0, "share_mapped_pct", "feed_mapping", "share_mapped_pct", _pinnacle),
        FIRST_WHERE(0, "safe_to_go_live", "feed_mapping", "safe_to_go_live", _pinnacle),
        S(0, "in_doubt", "feed_mapping", "source_column", lambda r: bool(r["in_doubt"]) and _pinnacle(r)),
    ],
})

MESS.update({
    "uc8-trades-vs-admin": [({"trade": "T-20261002-003"}, "M16 buy quantity differs"), ({"trade": "T-20261006-005"}, "M16 sell missing at the administrator"),
                            ({"trade": "T-20260602-005"}, "M07 trade booked twice"), ({"trade_reference": "FXF-2026-002"}, "M16 forward confirmed at another rate")],
    "uc-052-insurance": [({"policy": "POL-CYB-04"}, "renewal notice not received (key)")],
    "uc-055-corpact": [({"security": "Tidewater Energy"}, "voluntary tender offer to decide before the deadline (key)")],
    "uc-056-custrecon": [({"security": "Bay Street Utilities"}, "M24 scrip dividend not advised to the administrator"),
                         ({"security": "Redwood Pharma"}, "M24 transfer-out not copied to the administrator")],
    "uc-058-settle": [({"trade": "BR2-20261002-001"}, "M23 settlement failed"), ({"trade": "BR2-20261007-002"}, "M23 settlement failed")],
    "uc-059-breakage": [({"break_id": b}, "M26 break left open in the register") for b in ("BRK-001", "BRK-002", "BRK-003", "BRK-004", "BRK-005", "BRK-006")],
    "uc-060-docinbox": [({"file": "IMG_2210.pdf"}, "M27 restaurant receipt, refuse"), ({"file": "data_export.xlsx"}, "M27 four-column sheet, hold and ask")],
    "uc-061-dqscore": [({"source": "administrator_cash"}, "M04 administrator cash did not add up"), ({"source": "bank_statements"}, "M02b bank statement never arrived"),
                       ({"source": "manager_statements"}, "M02 manager statement never arrived")],
    "uc-062-fxlife": [({"trade": "FXF-2026-002"}, "M16 forward confirmation differs")],
    "uc-057-pricecheck": [({"security": ["Kingfisher Telecom", "Kingfisher Telecom 4.6% 2030 bond"], "date": SEP30}, "second source differs above tolerance (key)")],
    "uc-063-cashcode": [({"reference": ["TT-7741XQ", "ACH-55201", "CHQ-000417"]}, "three bank lines with no purpose (key)")],
    "uc-064-fxexp": [({"currency": "SGD"}, "M16 forward confirmed at another rate")],
    "uc-065-realassets": [({"asset_ref": "RA-04"}, "M29 title in a personal name")],
    "uc-066-propreval": [({"asset_ref": "RA-03"}, "M28 appraisal older than a year"), ({"asset_ref": "RA-05"}, "M28 appraisal older than a year")],
    "uc-067-unrl": [({"security": "Harborview Semiconductor"}, "M31 same company in several funds"), ({"is_loss": lambda r: bool(r["is_loss"])}, "unrealised loss lots (key)")],
    "uc-069-lookthru": [({"company": "Harborview Semiconductor"}, "M31 same company in several funds (and held directly)"),
                        ({"in_several_funds": lambda r: bool(r["in_several_funds"])}, "companies in more than one fund (key)")],
    "uc-071-expdist": [({"fund": ["Cedarpoint Opportunities II", "Cedarpoint Ventures III", "Saltmarsh Renewables I"]}, "stale value, 31 Mar or 30 Jun (key)")],
    "uc-074-boardpack": [({"estimated_lines": lambda r: bool(r["estimated_lines"])}, "Evergreen Growth I estimate in the issued report (M03)"),
                         ({"amendments_after_report": lambda r: bool(r["amendments_after_report"])}, "M03 statements amended after the report")],
    "uc-075-yearwalk": [({"bank_months_missing": lambda r: bool(r["bank_months_missing"])}, "M02b bank statement never arrived")],
    "uc-081-payroll": [({"employee_name": "Grace Ong"}, "M32 gross 20 percent above September, no approval"),
                       ({"employee_name": "Jun Tan"}, "M32 contractor not on the staff register")],
    "uc-082-covergap": [({"no_policy": lambda r: bool(r["no_policy"])}, "M30 asset with no policy"),
                        ({"under_insured": lambda r: bool(r["under_insured"])}, "M30 insured below its appraisal")],
    "uc-091-jml": [({"no_approver": lambda r: bool(r["no_approver"])}, "access granted without an approver"),
                   ({"leaver": lambda r: bool(r["leaver"])}, "leaver's access still on"),
                   ({"joiner_not_requested": lambda r: bool(r["joiner_not_requested"])}, "joiner's access not requested")],
    "uc-092-accessrev": [({"unused_90": lambda r: bool(r["unused_90"])}, "access not used in 90 days")],
    "uc-093-onbmgr": [({"complete": False}, "onboarding item outstanding")],
    "uc-095-sopreview": [({"due": lambda r: bool(r["due"])}, "SOP not reviewed in a year")],
    "uc-097-kycrefresh": [({"expired": lambda r: bool(r["expired"])}, "KYC document expired"),
                          ({"expiring_90": lambda r: bool(r["expiring_90"])}, "KYC document expiring within 90 days")],
    "uc-098-wordlist": [({"to_add": lambda r: bool(r["to_add"])}, "term to add to the office list")],
    "uc-099-newfeed": [({"in_doubt": lambda r: bool(r["in_doubt"])}, "column in doubt (key)")],
})

# The cause of one key value where a recipe row carries several (card 75: the walk's opening, income and balancing item). Keyed (card, key path).
PATH_CAUSE: dict[tuple[str, str], str] = {}
PATH_CAUSE.update({
    ("uc-075-yearwalk", "opening"): "The 31 March USD/SGD fixing is in no file, so the opening is empty (the opening and balancing item wait for it)",
    ("uc-075-yearwalk", "income"): "Bank statement TCB-B-USD 2026-07 never arrived (M02b), so the income is 44.71 short",
    ("uc-075-yearwalk", "fx_and_other"): "The balancing item needs the opening, which needs the 31 March fixing (in no file), so it is empty",
})

BLOCKED.update({
    "uc-072-cashfc": ("the payment schedule file stops at 11 Jan 2027, and the key's expenses for January to September 2027 come from schedule items in no file; "
                      "recipe cash_forecast agrees with the key to December 2026 (test_w1b_cash.py test_72_*)"),
    "uc-084-taxest": ("the lots sold since 1 Apr are in no file (the lot register holds only the lots still open on 30 Sep), so the realised gains cannot be matched "
                      "first-in first-out; and the 2026 tax rates (tax_rate_<entity>) are proposed by the tax calendar reader, not signed (A20, A54)"),
    "uc-096-automation": ("the 45 minutes of rework are signed (A51), but which failures count against which SOP (late close steps, missing statements, unapproved "
                          "or changed-account calls, invoice problems) is in the key's method only: in no file and no signed rule"),
})

# ---- Office cards 83 to 100 (test_w1b_office.py; docs/v3/w1/build51-office.md) ----------------------------------------------------------------

CHECKS.update({
    "uc-083-taxcal": [  # card 83, tax_due
        L(0, "due_in_60_days", "tax_due", {"id": "id"}, {k: k for k in ("entity", "obligation", "due", "days", "prepared_by", "status")}, due_in_60_days=1),
        F(0, "count_by_entity", ["tax_due"], lambda x: dict(Counter(r["entity"] for r in x["tax_due"] if r["due_in_60_days"]))),
        L(0, "overdue", "tax_due", {"id": "id"}, {k: k for k in ("entity", "obligation", "due", "days_overdue", "prepared_by", "status")}, overdue=1),
    ],
    "uc-085-grants": [  # card 85, grants_used
        *[FIRST(0, k, "grants_used", k) for k in ("budget", "paid", "pledged", "used", "used_pct", "remaining", "paid_matches_bank")],
    ],
    "uc-086-grantappr": [  # card 86, grant_check
        *[FIRST(0, k, "grant_check", c) for k, c in (("request", "request"), ("amount", "amount"), ("remaining_budget", "remaining_budget"),
                                                    ("charity_registered_months", "charity_registered_months"), ("required_months", "required_months"),
                                                    ("holdings_usd_cash", "cash"), ("calls_due_30_days", "calls_due_30_days"),
                                                    ("cash_after_request_and_calls", "cash_after_request_and_calls"), ("checks.within_budget", "within_budget"),
                                                    ("checks.charity_old_enough", "charity_old_enough"), ("checks.cash_covers", "cash_covers"), ("pay", "pay"))],
    ],
    "uc-087-trustdist": [  # card 87, trust_distribution_room
        *[FIRST(0, k, "trust_distribution_room", k) for k in ("trust_year_start", "trust_income", "trust_expenses", "distributable_income", "payout_cap_pct", "distributable_cap")],
        D(0, "by_beneficiary", "trust_distribution_room", "beneficiary", {"share_pct": "share_pct", "room": "room", "paid": "paid", "left": "left_to_pay", "over": "over"}),
        S(0, "over_distributed", "trust_distribution_room", "beneficiary", lambda r: r["over"]),
    ],
    "uc-088-estateliq": [  # card 88, estate_cash_need
        *[FIRST(0, k, "estate_cash_need", c) for k, c in (("estate_value", "estate_value"), ("investments_30_sep", "investments"), ("cash", "cash"), ("real_assets", "real_assets"),
                                                         ("loan", "loan"), ("exemption", "exemption"), ("rate", "rate"), ("transfer_tax", "transfer_tax"),
                                                         ("liquid_assets_after_debt", "liquid_assets_after_debt"), ("cover", "cover"), ("can_meet", "can_meet"))],
    ],
    "uc-089-expapp": [  # card 89, approval_exceptions (the limits themselves are the signed rules: test_card89_*)
        N(0, "payments", "approval_exceptions"),
        L(0, "over_limit", "approval_exceptions", {"reference": "reference"}, {"payee": "payee", "usd": "usd", "approver": "approver", "limit": "limit_usd"}, over_limit=1),
        F(0, "approvals_by_person", ["approval_exceptions"], lambda x: dict(Counter(r["approver"] for r in x["approval_exceptions"]))),
    ],
    "uc-090-offcost": [  # card 90, office_cost
        D(0, "by_category", "office_cost", "category", {"actual": "actual", "budget_half_year": "budget_period", "variance": "variance", "over": "over"}),
        FIRST(0, "actual", "office_cost", "total_actual"),
        FIRST(0, "budget", "office_cost", "total_budget"),
        S(0, "over_budget", "office_cost", "category", lambda r: r["over"]),
        FIRST(0, "uncategorised", "office_cost", "uncategorised"),
    ],
    "uc-094-onbbank": [  # card 94, account_setup (the six checklist steps are in no file: not compared)
        F(0, "signatories", ["account_setup"], lambda x: str(x["account_setup"][0]["signatories"]).split(", ") if x["account_setup"] else None),
        FIRST(0, "required_head_of_finance", "account_setup", "required_person"),
        FIRST(0, "missing_signatory", "account_setup", "missing_signatory"),
        FIRST(0, "meets_signing_policy", "account_setup", "meets_signing_policy"),
        FIRST(0, "approved", "account_setup", "approved"),
    ],
    "uc-100-famaccess": [  # card 100, member_access
        F(0, "by_member", ["member_access"], lambda x: {m: {"allowed": {r["entity"]: r["allowed"] for r in x["member_access"] if r["member"] == m and r["allowed"] not in (None, "none")},
                                                             "granted": {r["entity"]: r["granted"] for r in x["member_access"] if r["member"] == m and r["granted"] != "none"},
                                                             "over_granted": {r["entity"]: {"granted": r["granted"], "allowed": r["allowed"]} for r in x["member_access"]
                                                                              if r["member"] == m and r["over_granted"]}}
                                                        for m in {r["member"] for r in x["member_access"]}}),
        F(0, "over_grants", ["member_access"], lambda x: sorted({r["member"] for r in x["member_access"] if r["over_granted"]})),
        F(0, "request", ["member_access"], lambda x: next(({"member": r["member"], "entity": r["entity"], "level": r["requested_level"], "allowed": r["request_allowed"]}
                                                           for r in x["member_access"] if r["has_request"]), None)),
    ],
})
MESS.update({
    "uc-083-taxcal": [({"id": "TX-04"}, "M33 overdue filing")],
    "uc-086-grantappr": [({"request": "REQ-2026-06"}, "M34 grant request fails the policy")],
    "uc-087-trustdist": [({"beneficiary": "Wen Chen"}, "M47 trust paid beyond its share")],
    "uc-089-expapp": [({"reference": ["BAL-2026-051", "LL-2026-0708"]}, "M35 approved above the approver's limit")],
    "uc-094-onbbank": [({"account_holder": "Evergreen Family Trust"}, "M38 signatory missing")],
    "uc-100-famaccess": [({"member": "Wen Chen", "entity_code": "EG-B"}, "M43 view over-granted")],
})


# ---- Invest cards 53, 76 to 79 (test_w1b_invest.py; docs/v3/w1/build51-invest.md) ---------------------------------------------------------------

_DATE = {"dealing_date": "dealing_date", "send_notice_by": "send_notice_by", "days_to_send": "days_to_send", "cash_date": "cash_date", "latest_value": "latest_value",
         "cash_at_payment": "cash_at_payment", "held_back_until_audit": "held_back_until_audit"}
CHECKS.update({
    "uc-053-watchlist": [  # card 53, watch_flags
        FIRST(0, "window_start", "watch_flags", "window_start"),
        D(0, "by_manager", "watch_flags", "manager", {k: k for k in ("late", "amended", "missing", "personnel_changes", "total")}),
        S(0, "on_watchlist", "watch_flags", "manager", lambda r: r["on_watchlist"]),
    ],
    "uc-076-scorecard": [  # card 76, manager_score
        D(0, "by_manager", "manager_score", "manager", {"return_pct_since_1_apr": "return_pct", "fee_drag_pct": "fee_drag_pct", "on_time_share": "on_time_share",
                                                        "watch_flags": "watch_flags", "score": "score", "verdict": "verdict"}),
        *[FIRST(0, f"weights.{k}", "manager_score", f"weight_{c}") for k, c in (("returns", "returns"), ("fees", "fees"), ("timeliness", "timeliness"), ("watch", "watch"))],
    ],
    "uc-077-deals": [  # card 77, deal_stage
        F(0, "by_stage", ["deal_stage"], lambda x: dict(Counter(r["stage"] for r in x["deal_stage"]))),
        L(0, "deals", "deal_stage", {"deal": "deal_name"}, {"stage": "stage", "days_in_stage": "days_in_stage", "ticket": "ticket", "stuck": "stuck"}),
        S(0, "stuck_over_60_days", "deal_stage", "deal_name", lambda r: r["stuck"]),
        FIRST(0, "total_ticket", "deal_stage", "total_ticket"),
    ],
    "uc-078-redemption": [  # card 78, redemption_dates
        D(0, "by_fund", "redemption_dates", "fund", _DATE),
    ],
    "uc-079-rebalance": [  # card 79, rebalance_trades
        FIRST(0, "book", "rebalance_trades", "book"),
        F(0, "targets_status", ["rebalance_trades"], lambda x: all("not signed" in str(r["targets_status"]) for r in x["rebalance_trades"] if r["target_pct"] is not None),
          kf=lambda e: "not signed" in e),
        D(0, "by_class", "rebalance_trades", "asset_class", {k: k for k in ("current", "current_pct", "target_pct", "target", "trade")}),
        F(0, "net_trade", ["rebalance_trades"], lambda x: tot(x["rebalance_trades"], "trade")),
    ],
})
MESS.update({
    "uc-053-watchlist": [({"manager": ["Saltmarsh Real Assets", "Northgate Partners"], "personnel_changes": lambda r: r["personnel_changes"] > 0}, "M44 manager personnel change"),
                         ({"manager": "Cedarpoint Ventures", "missing": lambda r: r["missing"] > 0}, "M02 statement missing (Cedarpoint Opportunities II, 30 Jun)")],
    "uc-076-scorecard": [({"verdict": "review or exit"}, "key: managers to review or exit (Cedarpoint, Kestrel, Saltmarsh)")],
    "uc-077-deals": [({"deal_name": ["Marlow Infrastructure Partners III", "Ashgrove Growth Equity V"]}, "M46 deals stuck in a stage")],
    "uc-078-redemption": [({"fund": "Kestrel Ridge Equity Long/Short Fund", "locked_up": 1}, "key: the long/short fund is locked up to 31 Dec")],
    "uc-079-rebalance": [({"targets_status": lambda r: "not signed" in str(r["targets_status"] or "")}, "key: targets proposed at the 8 Oct committee, not signed: a suggestion only")],
})

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
            elif CLEAN_NOTES and row and s.get("severity") != "info":  # --all: a note, not a verdict; the top 50 scorecard does not carry these notes
                notes.append(f"CLEAN {s['id']} fires on {subj}")
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


def score(all_cards: bool = False) -> dict:
    t0 = time.time()
    from sh_platform.v1 import v3_recipes as R, v3_signals as S
    S.PROVIDER = None  # the recipe rows of this run are the figures; no figure store, no live warehouse lookup
    S.same_fund = lambda plane, a, b, judged: S._norm_name(a) == S._norm_name(b)  # model-free: no judge in a deterministic score
    uc = yaml.safe_load((PACK / "use_cases_100.yaml").read_text(encoding="utf-8"))
    people = {p["id"]: p["person"] for p in uc["people"]}
    if all_cards:  # all 100 cards in their card order (the 50 with no priority carry an order number too)
        cards = sorted(uc["use_cases"], key=lambda u: u["order"])
    else:
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
    res = {"id": cid, "priority": c.get("priority") or c["order"], "title": c["title"], "domain": c["domain"], "person": people.get(c["owner"], c["owner"]), "checks": [],
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
                    res["causes"].append(("FAIL", PATH_CAUSE.get((cid, path)) or CAUSE.get(r, f"recipe {r} gives a wrong number"), r))
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
    w("# Score of the 100 use cases" if r.get("all") else "# Score of the top 50 use cases")
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
        other = [n for n in c.get("signal_notes") or [] if not n.startswith("CLEAN ")]
        clean = [n[len("CLEAN "):] for n in c.get("signal_notes") or [] if n.startswith("CLEAN ")]
        if other:
            w("")
            w("Signals that cannot run on the loaded data: " + "; ".join(other) + ".")
        if clean:
            w("")
            w("Non-info signals that fire on a row with no planted mess (a note, not a verdict): " + "; ".join(clean) + ".")
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
    global CLEAN_NOTES
    all_cards = "--all" in sys.argv[1:]
    CLEAN_NOTES = all_cards
    out = OUT100 if all_cards else OUT
    try:
        r = score(all_cards)
    except Exception:  # noqa: BLE001 - exit 0 always; say what broke
        log.exception("score50 could not run")
        print("score50: could not run (see the error above)")
        return 0
    r["all"] = all_cards
    out.write_text(write(r) + "\n", encoding="utf-8")
    t = Counter(c["result"] for c in r["cards"])
    print(f"PASS {t['PASS']}  FAIL {t['FAIL']}  SIGNAL {t['SIGNAL']}  BLOCKED {t['BLOCKED']}  of {len(r['cards'])} cards  "
          f"({r['total_s']:.0f} s)  -> {out.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
