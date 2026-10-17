"""Live run 3, part B, fixer B (docs/v3/LIVE-R3B-ANALYSIS.md): the invest and office recipes of use cases 51 to 100.

Cause: the recipes these cards need had no names, words_all or answer template, so the figures were bound to the wrong recipe (uc-053 and uc-085 to
missing_statements, uc-078 to vendor contracts) or answered with "one of N rows" and the "Rules-only reply" fallback. Each case here is the
office6m warehouse loaded through the real readers (test_w2_loader.py's `office`), the recipe bound by the figure's name, its rows and its answer
checked against the live question. The dates are said as people say them ("15 Jul 2026"). Synthetic data only.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_recipes as R


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


W2 = _load("w2_loader_tests_r3b", "test_w2_loader.py")
office = W2.office


def _said(o, rid: str) -> tuple[list[dict], str]:
    rows = o.run(rid)
    return rows, F.say(R.recipe(rid), rows) or ""


def _has(text: str, *keys: str) -> None:
    for k in keys:
        assert k in text, (k, text)


def _bound(name: str) -> str | None:
    r = R._match({"name": name})
    return r["id"] if r else None


# ---- uc-053: "Which managers have given us a late, restated or changed statement this quarter?" ----------------------------------------------

def test_uc053_the_watchlist_is_bound_to_watch_flags_not_missing_statements(office):
    assert _bound("Managers with statement issues") == "watch_flags"
    rows, said = _said(office, "watch_flags")
    on = {r["manager"] for r in rows if r["on_watchlist"]}
    assert on == {"Cedarpoint Ventures", "Kestrel Ridge Advisors", "Northgate Partners", "Saltmarsh Real Assets"}
    _has(said, "Statement watch since 15 Jul 2026", "Cedarpoint Ventures", "Kestrel Ridge Advisors", "Northgate Partners", "Saltmarsh Real Assets")


# ---- uc-071: "How much money should we expect back from the funds over the next year?" ------------------------------------------------------------

def test_uc071_expected_distributions_say_the_quarters_the_funds_and_the_total(office):
    assert _bound("Projected fund payout") == "expected_distributions"
    rows, said = _said(office, "expected_distributions")
    total = next(r for r in rows if r["row_kind"] == "total")
    assert float(total["amount"]) == 2660810
    _has(said, "2,660,810", "628,215", "464,215", "787,115", "781,265", "1,068,900", "10,180,000")


# ---- uc-076: "Which managers should we keep, add to, or exit?" -----------------------------------------------------------------------------------

def test_uc076_manager_score_says_each_score_with_its_return_and_timeliness(office):
    _, said = _said(office, "manager_score")
    _has(said, "Bluewater Capital 98.3 (add)", "Northgate Partners 86.8 (add)", "Kestrel Ridge Advisors 45.4", "Meridian Index Managers 50 (keep)",
         "Cedarpoint Ventures 20", "Saltmarsh Real Assets 13", "14.71%", "-19.10%", "on time 0.929")


# ---- uc-077: "Which deals should we move forward or drop?" -------------------------------------------------------------------------------------

def test_uc077_deal_stage_says_the_total_and_the_stuck_deals_with_their_days(office):
    rows, said = _said(office, "deal_stage")
    assert sum(float(r["ticket"]) for r in rows) == 13000000
    _has(said, "13,000,000", "Marlow Infrastructure Partners III (Marlow Capital) in Diligence for 77 days", "Ashgrove Growth Equity V",
         "for 120 days", "Harborlight Ventures IV in Teaser reviewed for 21 days")


# ---- uc-078: "By when must we send the redemption notice and when do we get the cash?" -----------------------------------------------------------

def test_uc078_last_notice_date_is_bound_to_redemption_dates_not_vendor_contracts(office):
    assert _bound("Last notice date") == "redemption_dates"
    rows, said = _said(office, "redemption_dates")
    _has(said, "send notice by 16 Oct 2026", "dealing on 30 Nov 2026", "send notice by 30 Oct 2026", "dealing on 31 Dec 2026",
         "cash 6,954,000", "cash 4,921,000", "366,000 held back", "259,000 held back")


# ---- uc-079: "Which holdings should we sell or buy, and how much?" ------------------------------------------------------------------------------

def test_uc079_rebalance_trades_say_each_trade_against_its_target(office):
    assert _bound("Sell or buy to reach target") == "rebalance_trades"
    _, said = _said(office, "rebalance_trades")
    _has(said, "42,273,700", "listed_equity: -5,811,695 (sell), from 78.75% to the 65% target", "4,817,910 (buy)", "993,785 (buy)")


# ---- uc-080: "Are our private commitments too bunched in one year?" ----------------------------------------------------------------------------

def test_uc080_vintage_split_says_each_year_with_its_share(office):
    _, said = _said(office, "vintage_split")
    _has(said, "54,850,000", "2021 15,000,000 (27.35% of the total", "2022 13,000,000 (23.70%", "2023 10,000,000 (18.23%",
         "2024 12,500,000 (22.79%", "2025 4,350,000 (7.93%")


# ---- uc-081: "Whether to release the pay file" -----------------------------------------------------------------------------------------------------

def test_uc081_payroll_total_says_the_run_against_last_month_and_the_held_lines(office):
    assert _bound("Total payroll amount") == "payroll_total"
    _, said = _said(office, "payroll_total")
    _has(said, "net pay 100,224", "employer contributions 21,297.60", "total cost 121,521.60", "the last run cost 113,199 (net 93,360)",
         "7.35%", "Jun Tan: not in the staff register", "Grace Ong: gross changed")


# ---- uc-082: "Whether to raise or lower cover" ----------------------------------------------------------------------------------------------------

def test_uc082_cover_gap_says_the_total_and_each_asset(office):
    _, said = _said(office, "cover_gap")
    _has(said, "-9,647,014.92", "Hillcrest House", "Coastal Land Parcel Lot 14", "Bayview Residence", "gap -820,895.52", "Fine art collection")


# ---- uc-083: "Which filings and payments are due and who prepares them" ------------------------------------------------------------------------

def test_uc083_tax_due_says_every_item_with_its_date_and_preparer(office):
    assert _bound("Payment due date") == "tax_due"
    _, said = _said(office, "tax_due")
    _has(said, "TX-04", "due 30 Sep 2026", "TX-01", "TX-02", "due 30 Nov 2026", "Summit Tax Advisory")


# ---- uc-085: "Whether to approve more grants this year" ---------------------------------------------------------------------------------------------

def test_uc085_annual_grant_budget_is_bound_to_grants_used_not_missing_statements(office):
    assert _bound("Annual grant budget") == "grants_used"
    _, said = _said(office, "grants_used")
    _has(said, "Grant budget 300,000", "paid 175,000", "pledged 90,000", "265,000 used (88.3%)", "35,000 remaining")


# ---- uc-086: "Whether to pay the grant" -------------------------------------------------------------------------------------------------------------

def test_uc086_grant_check_says_the_request_budget_cash_and_calls(office):
    _, said = _said(office, "grant_check")
    _has(said, "REQ-2026-06", "USD 50,000", "remaining budget 35,000", "cash 1,230,000", "1,250,000 of calls due in 30 days", "leaving -70,000")
    assert _bound("Budget remaining") == "grants_used"


# ---- uc-087: "Whether the trust pays what its deed allows" ---------------------------------------------------------------------------------------

def test_uc087_trust_room_says_the_trust_year_and_each_beneficiary_against_the_room(office):
    _, said = _said(office, "trust_distribution_room")
    _has(said, "income 504,980.42", "expenses 46,001.31", "cap 321,285.38", "Wen Chen: room 25,702.83, paid 28,000, left -2,297.17")


# ---- uc-088: "Whether the family could meet a transfer tax from liquid assets" -------------------------------------------------------------------

def test_uc088_estate_cash_need_says_the_estate_and_whether_the_tax_is_met(office):
    _, said = _said(office, "estate_cash_need")
    _has(said, "131,306,339.91", "investments 109,960,000", "transfer tax of 18,945,950.99", "55,879,741.41 after debt", "a cover of 2.95 times")


# ---- uc-089: "Which approval limits to set and who may approve" ----------------------------------------------------------------------------------

def test_uc089_approval_exceptions_say_every_payment_over_its_limit_and_no_truncation(office):
    rows, said = _said(office, "approval_exceptions")
    assert len(rows) == 151 and sum(int(r["over_limit"]) for r in rows) == 2
    _has(said, "BAL-2026-051", "38,000 USD, approved by Priya Nair", "LL-2026-0708", "16,662.93 USD", "limit of 10,000 USD")
    assert "one of 151" not in said and "more" not in said


# ---- uc-090: "Whether the office costs more than planned" ---------------------------------------------------------------------------------------------

def test_uc090_office_cost_says_the_total_and_each_category_over_budget(office):
    _, said = _said(office, "office_cost")
    _has(said, "1,463,862.76", "1,455,850", "Professional fees 78,252.48 against 42,500, over by 35,752.48", "Grants 175,000 against 150,000, over by 25,000")


# ---- uc-091 and uc-092: "Which access to give or remove" / "Which access to remove" -------------------------------------------------------------

def test_uc091_access_review_says_each_joiner_mover_and_leaver(office):
    rows, said = _said(office, "access_review")
    assert len(rows) == 38
    _has(said, "Leaver still holds access, to remove: J. Ng: view on OMS", "Joiner has access nobody requested: Wei Tan: initiate payments on Harbour Bank portal",
         "No approver recorded: Sam Lee: trade entry on OMS")


def test_uc092_access_not_used_in_90_days_is_bound_to_access_review_and_says_each_grant(office):
    assert _bound("Access not used in 90 days") == "access_review"
    _, said = _said(office, "access_review")
    _has(said, "Anita Rao: view on Custody portal, 168 days unused", "Sofia Reyes: view on OMS, 146 days unused", "Priya Nair: edit on Shared drive, 132 days unused")


# ---- uc-093: "Whether every document and feed is in place before the first call" ----------------------------------------------------------------

def test_uc093_onboarding_says_the_items_outstanding_and_the_count_complete(office):
    _, said = _said(office, "onboarding_items")
    _has(said, "Harborlight onboarding: 3 of 5 items complete", "Outstanding before the first call:", "Bank details confirmed by call-back (missing)",
         "Statement schedule", "Complete:", "Subscription document")  # the complete items are in row order, not a sorted list


# ---- uc-094: "The run on the copy stopped at the signatory compliance step" --------------------------------------------------------------------

def test_uc094_account_setup_says_the_signatories_and_the_missing_one(office):
    _, said = _said(office, "account_setup")
    _has(said, "Evergreen Family Trust", "2 of 2 signatories", "the policy needs Head of Finance Daniel Foo")


# ---- uc-095: "Which procedures to review" -----------------------------------------------------------------------------------------------------------

def test_uc095_sop_age_says_each_procedure_past_its_review_with_its_age(office):
    assert _bound("Procedures overdue for review") == "sop_age"
    _, said = _said(office, "sop_age")
    _has(said, "Open or change a bank account (Daniel Foo)", "681 days ago", "Vendor payment run (Grace Ong)", "480 days ago", "Payroll release (Priya Nair)", "378 days ago")


# ---- uc-097: "Which documents to refresh before the bank or manager freezes the account" --------------------------------------------------------

def test_uc097_kyc_expiry_says_the_expired_and_the_expiring_documents(office):
    _, said = _said(office, "kyc_expiry")
    _has(said, "Daniel Foo, Director identity document, Daniel Foo, expired 12 Sep 2026 (-31 days)", "Limited partner KYC refresh, expires 5 Jan 2027 (84 days)",
         "Certificate of incumbency, expires 2 Dec 2026", "expires 14 Nov 2026")


# ---- uc-098: "Whether to add a word to the language list" -----------------------------------------------------------------------------------------

def test_uc098_terms_proposed_says_which_words_to_add_and_which_are_listed(office):
    _, said = _said(office, "terms_proposed")
    _has(said, "To add to the language list: side letter", "stub period", "Already on the list: capital account; dry powder")


# ---- uc-100: "What each family member may see" -------------------------------------------------------------------------------------------------------

def test_uc100_member_access_says_each_over_grant_and_each_request(office):
    _, said = _said(office, "member_access")
    _has(said, "Granted more than allowed: Wen Chen on Entity B: granted full, allowed none", "Requests not allowed: Maya Chen on Evergreen Holdings: summary")


# ---- the recipes this file changes are built and bound by name, not by definition -------------------------------------------------------------

def test_the_names_added_here_bind_their_own_recipe_and_no_other():
    for name, rid in [("Managers with statement issues", "watch_flags"), ("Annual grant budget", "grants_used"), ("Budget remaining", "grants_used"),
                      ("Last notice date", "redemption_dates"), ("Total payroll amount", "payroll_total"), ("Payment due date", "tax_due"),
                      ("Procedures overdue for review", "sop_age"), ("Access not used in 90 days", "access_review"), ("Projected fund payout", "expected_distributions")]:
        assert _bound(name) == rid, name
