"""Live run 3, part B, fixer C (docs/v3/LIVE-R3B-ANALYSIS.md): uc8, uc-056, uc-058, uc-059, uc-060, uc-061, uc-063, uc-074, uc-075, uc-099.

Cause: the answer of these recipes was a fallback ("Rules-only reply", "one of N rows") because the recipe had no answer lines, or no words
for the question. The answer lines in operate.yaml and report.yaml now say each row the question asks for. Each case is asked its live question
on the office6m files loaded through the real readers (test_w2_loader.py's `office`), and the recipe's own answer lines are checked for the
numbers and names the question needs. Open in the table, not fixed here: uc-063's 42,120 is in no table; uc-075's income and FX lines differ
from the answer key by 44.71 each (the walk still adds up); uc-058 is held at Decision 3 in the live run (intake, not this file).
Synthetic data only."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_recipes as R


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


W2 = _load("w2_loader_tests_r3b_c", "test_w2_loader.py")
office = W2.office


def _said(office, rid: str) -> tuple[list[dict], str]:
    rows = office.run(rid)
    return rows, F.say(R.recipe(rid), rows) or ""


def _has(text: str, *keys: str) -> None:
    for k in keys:
        assert k in text, (k, text)


# ---- uc8: the October trades the administrator does not match ---------------------------------------------------------------------------

def test_uc8_trades_the_administrator_does_not_match_are_named_with_amounts(office):
    # "which October trades does the administrator not match?" r3 said "awaiting administrator file" and "breaks 0"
    rows, said = _said(office, "trade_breaks")
    breaks = [r for r in rows if r["breaks"]]
    assert {r["trade"] for r in breaks} >= {"T-20261006-005", "T-20261002-003"}
    _has(said, "T-20261006-005", "592,000", "T-20261002-003", "75,870", "missing at administrator", "quantity differs")
    assert re.search(r"and \d+ more", said) is None  # every break is said: no "and N more"


# ---- uc-056: which holdings differ between the custodian and the administrator, and why -------------------------------------------------

def test_uc056_every_holding_that_differs_is_said_with_its_value_and_reason(office):
    rows, said = _said(office, "position_break")  # r3 listed 2 of 2 rows with no values: "Quantity discrepancy value in September 2026"
    breaks = [r for r in rows if r["breaks"]]
    assert sorted(r["security"] for r in breaks) == ["Bay Street Utilities", "Redwood Pharma"]
    _has(said, "Bay Street Utilities", "60,062.50", "Scrip dividend credited on 29 Sep", "Redwood Pharma", "18,940", "Transfer-out to a family brokerage account")
    assert re.search(r"and \d+ more", said) is None


# ---- uc-058: which trades failed to settle and whom to chase ----------------------------------------------------------------------------

def test_uc058_failed_trades_are_said_with_amount_days_late_and_the_broker_to_chase(office):
    rows, said = _said(office, "unsettled_trades")  # the live answer was held at Decision 3 (intake); the recipe's lines say each trade
    assert sorted(r["trade"] for r in rows if r["unsettled"]) == ["BR2-20261002-001", "BR2-20261007-002"]
    _has(said, "BR2-20261002-001", "281,150", "5 business days late", "seller short delivery", "Synthetic Broker Two")
    assert re.search(r"and \d+ more", said) is None


# ---- uc-059: which breaks are older than five days ---------------------------------------------------------------------------------------

def test_uc059_breaks_older_than_five_business_days_are_said_first_with_their_age(office):
    rows, said = _said(office, "break_age")  # r3 stuck at the answer (500); the break_age recipe has no bindings and no answer lines before this
    old_cash = [r["break_id"] for r in rows if r["over_five_business_days"] and r["break_type"] == "cash break"]
    assert old_cash == ["BRK-003", "BRK-004"]
    assert said.index("Cash breaks older than five business days") < said.index("BRK-003") < said.index("BRK-004")
    _has(said, "84 business days old", "47 business days old", "Within five business days", "BRK-001", "BRK-002")


# ---- uc-060: where each unrecognised file belongs, or whether to refuse it ----------------------------------------------------------------

def test_uc060_each_inbox_file_is_said_with_where_it_belongs_or_refused(office):
    rows, said = _said(office, "unrecognised_files")  # r3: "unrecognised files has no rows"
    assert len(rows) == 5
    low = said.lower()  # the first word of a sentence is capitalised by the answer engine
    _has(low, "img_2210.pdf is not recognised", "refuse and return to the sender", "data_export.xlsx is not recognised", "hold and ask the sender",
         "scan_0412.pdf belongs in notices", "account_extract.xlsx belongs in bank_statements", "inv-oit-2610.pdf belongs in invoices")


# ---- uc-061: which source to fix first --------------------------------------------------------------------------------------------------

def test_uc061_the_source_to_fix_first_is_named_with_its_score(office):
    rows, said = _said(office, "source_quality")  # r3 said nothing: the recipe had no answer lines
    fix = [r for r in rows if r["fix_first"]]
    assert [r["source"] for r in fix] == ["administrator_cash"] and float(fix[0]["score_pct"]) == 71.4
    _has(said, "Fix first: administrator_cash", "71.4%", "5 of 7 loads", "Then, by score", "administrator_nav 85.7%", "bank_statements 97.6%")


# ---- uc-063: bank lines with no purpose -------------------------------------------------------------------------------------------------

def test_uc063_every_uncoded_bank_line_is_said_with_its_amount(office):
    rows, said = _said(office, "uncoded_bank_lines")  # r3 said one line (CHQ-000417)
    assert len([r for r in rows if r["uncoded"]]) == 3
    _has(said, "48,250 USD", "TT IN REF 7741XQ", "-3,980 USD", "ACH DEBIT MERCHANT 55201", "-2,150 USD", "CHEQUE 000417")
    assert re.search(r"and \d+ more", said) is None


# ---- uc-074: what to tell the board of the family -----------------------------------------------------------------------------------------

def test_uc074_the_board_headlines_are_all_said(office):
    rows, said = _said(office, "board_summary")
    assert len(rows) == 1 and float(rows[0]["cash_usd_eq"]) == 6156041.41  # r3 answered "Rules-only reply"
    _has(said, "57,600,000 USD", "77,253,120 SGD", "1.3412", "Evergreen Growth I is an estimate", "3.5148%", "5.7563%",
         "6,156,041.41 USD", "270,000 USD", "14,600,000 USD", "Statements amended after the report: 1")


# ---- uc-075: what to tell the family about the year -------------------------------------------------------------------------------------

def test_uc075_the_year_walk_is_said_from_opening_to_closing_and_adds_up(office):
    rows, said = _said(office, "networth_walk")  # r3 said the closing value only
    w = rows[0]
    assert w["adds_up"] is True
    _has(said, "114,568,027.06", "114,394,995.51", "540,967", "1,514,870", "-973,903", "1,263,862.76", "5,950,000", "767,500")
    # the walk adds up from opening to closing in the table itself (opening + gains + income - spending + fx and other = closing)
    assert round(float(w["opening"] + w["investment_gains"] + w["income"] - w["spending"] + w["fx_and_other"] - w["closing"]), 2) == 0


# ---- uc-099: is the new feed mapped and safe to go live -----------------------------------------------------------------------------------

def test_uc099_the_columns_in_doubt_are_named_and_the_feed_is_not_yet_safe(office):
    rows, said = _said(office, "feed_mapping")  # r3: "feed mapping has no rows"
    assert {r["source_column"] for r in rows if r["in_doubt"]} == {"Value", "Dt"}
    assert rows[0]["columns"] == 10 and rows[0]["mapped_with_confidence"] == 8 and rows[0]["share_mapped_pct"] == 80
    _has(said, "Value in pinnacle_custody_positions_*.csv is in doubt", "could be position_snapshots.source_market_value",
         "Dt in pinnacle_custody_positions_*.csv is in doubt", "8 of 10 columns", "80%", "not safe to go live yet")
    assert "safe to go live, the mapping is approved" not in said
