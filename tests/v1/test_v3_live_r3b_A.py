"""Live run 3, part B, fixer A (docs/v3/LIVE-R3B-ANALYSIS.md): the cash and hold recipes of cards 51 to 100 and the wrong definition binds.

uc-053, 054, 055, 064, 065, 066, 067, 068, 069, 070, 073, 085. Causes: the recipes did not answer to the live question or to the figures North wrote in the brief
(liquidity_ladder, idle_cash, actions_next_14d, appraisal_age, unrealised_gain, income_forecast, lookthrough_exposure, cash_runway), so the answer was another
recipe's rows; none of the cash and hold recipes of these cards had an `answer`, so the rows were read as one line ("over 10 rows", "RA-04 only"); a definition that
leads with a count, or that only mentions "bank statements", bound a figure to missing_statements. The question and the figures below are as North wrote them in
those threads; the answers are each recipe run on the office6m warehouse (test_w2_loader.py's `office`). Synthetic data only."""
from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest

from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_recipes as R


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


office = _load("w2_loader_tests_r3b_a", "test_w2_loader.py").office


def _has(text: str, *keys: str) -> None:
    for k in keys:
        assert k in text, (k, text)


def _said(office, rid: str) -> str:
    return F.say(R.recipe(rid), office.run(rid)) or ""


def _figs(*pairs):
    return [{"name": n, "definition": d, "formula": "", "unit": "", "period": "monthly", "owner": "x", "status": "defined"} for n, d in pairs]


# ---- the live question names the recipe (kpi_by_recipe reads the question as a figure's name) -------------------------------------------------

QUESTIONS = [
    ("uc-054-ladder", "How much cash do we have against calls and payments in the next 30, 60 and 90 days?", "liquidity_ladder"),
    ("uc-055-corpact", "Which actions need a decision or a booking?", "actions_next_14d"),
    ("uc-064-fxexp", "Whether to hedge a currency exposure?", "currency_exposure"),
    ("uc-065-realassets", "What real assets we own, their values and who holds them?", "real_asset_value"),
    ("uc-066-propreval", "Whether to order a new appraisal?", "appraisal_age"),
    ("uc-067-unrl", "Which lots to sell for a tax or rebalance reason?", "unrealised_gain"),
    ("uc-068-incomef", "How much income to plan for next year?", "income_forecast"),
    ("uc-069-lookthru", "Whether the family is over-exposed to one company or sector through funds?", "lookthrough_exposure"),
    ("uc-070-idle", "How much cash is sitting idle above what we need for 90 days?", "idle_cash"),
    ("uc-073-runway", "Whether spending is sustainable", "cash_runway"),
]


@pytest.mark.parametrize("uc,question,want", QUESTIONS, ids=[q[0] for q in QUESTIONS])
def test_the_live_question_is_the_recipe_it_asks_for(uc, question, want):
    assert (R.match({"name": question}, strict=False) or {}).get("id") == want  # r3b: another recipe's rows (calls due, balances, unfunded commitments) answered


def test_the_recipes_other_phrases_do_not_take_other_questions():
    # the phrases added for cards 54 and 70 are not the questions of the capital-call story
    for q, other in [("Can Holdings pay the Cedarpoint call on the 23rd?", "cash_after_calls"), ("What are the calls due in the next 30 days?", "calls_due"),
                     ("How much SGD do we convert for the call?", "fx_required")]:
        assert (R.match({"name": q}, strict=False) or {}).get("id") in (other, None), q


# ---- the figures North wrote in the briefs are bound to them ------------------------------------------------------------------------------

def _bound(goal: str, *pairs) -> dict[str, str]:
    ks = _figs(*pairs)
    R.bind(None, None, ks, goal)
    return {k["name"]: k.get("built_from") for k in ks}


def test_uc054_the_cash_buffer_is_the_ladder_and_the_ladder_is_asked_for():
    goal = ("Every Monday, and after we record a call, I want each entity's cash in USD against the calls and the approved or scheduled payments falling in the next 30, "
            "60 and 90 days, and whether any of them drops under the 250,000 buffer. Leave out the held payments and the ones only expected.")
    got = _bound(goal, ("Cash buffer status", "USD cash balance per entity compared with the 250,000 USD buffer; breach flag if below."),
                 ("Calls due 30‑day", "Total call amount whose due date falls within the next 30 days."),
                 ("Scheduled payments 30‑day", "Total approved or scheduled payment amount due in the next 30 days."))
    assert got["Cash buffer status"] == "liquidity_ladder" and got["Calls due 30‑day"] == "calls_due"
    # one figure is the ladder, so the question's recipe has its one figure (v3_rule_checks.kpi_by_recipe reads exactly one)
    ks = _figs(("Calls due 60‑day", "Total call amount whose due date falls within the next 60 days."))
    R.bind(None, None, ks, goal)
    assert [k["built_from"] for k in ks if k.get("pack_suggested")] == ["liquidity_ladder"]


def test_uc067_and_uc069_a_recipe_the_goal_names_is_added_as_a_figure():
    goal = ("At quarter end I want the gain we are sitting on in each open lot of the liquid book: what it cost, what it is worth at the quarter-end price and the gain, "
            "with the lots at a loss first for tax and the lots of a holding above the single-name limit for a rebalance, and how much to sell to bring it back.")
    ks = _figs(("Net worth", "Total value of all assets incl. private‑fund positions"), ("Cash drag", "Cash holding as a proportion of total portfolio value"))
    R.bind(None, None, ks, goal)
    assert [k["built_from"] for k in ks if k.get("pack_suggested")].count("unrealised_gain") == 1 and ks[1]["built_from"] == ""
    goal = ("Each quarter I want to see through our private funds: what we own of each company and each sector through them, which companies sit in more than one fund, "
            "and Harborview Semiconductor with what we hold directly beside it, as the single-name limit measures it.")
    ks = _figs(("Unfunded commitments", "Opening unfunded + approved commitment changes – reductions from funded calls"))
    R.bind(None, None, ks, goal)
    assert [k["built_from"] for k in ks if k.get("pack_suggested")].count("lookthrough_exposure") == 1


def test_uc068_the_income_figure_is_the_income_forecast():
    got = _bound("At the start of the quarter I want the income the liquid book will pay us over the next 12 months: the coupons and the dividends the income calendar expects, by quarter.",
                 ("Quarterly liquid book income", "Sum of expected coupons and dividends for each quarter from the income calendar, adjusted for corporate actions, over the next 12 months."))
    assert got == {"Quarterly liquid book income": "income_forecast"}


def test_uc070_the_cash_headroom_is_the_idle_cash_and_a_cash_drag_is_not():
    got = _bound("At month end I want to know how much cash each entity holds above what it needs for the next 90 days, the calls and the approved or scheduled payments, and "
                 "above the 250,000 buffer, so I can propose to the CIO whether to invest, repay or hold it.",
                 ("Cash headroom", "Opening cash + approved inflows – known obligations – scenario‑only calls – proposed funding – reserve (buffer)."),
                 ("Cash drag", "Cash balance expressed as a percentage of total assets, indicating idle capital."))
    assert got["Cash headroom"] == "idle_cash" and not got["Cash drag"]


def test_uc073_the_cash_coverage_is_the_runway():
    got = _bound("At the quarter end I want to know how many months our cash covers at the way we have been spending.",
                 ("Cash coverage (cash only)", "Months of cash runway based on current cash balance divided by average monthly spend."))
    assert got["Cash coverage (cash only)"] == "cash_runway"


# ---- the wrong definition binds are stopped (uc-053, uc-085) and a words_all tie is not a crash --------------------------------------------

def test_uc053_a_count_of_managers_is_not_the_missing_statements_recipe():
    k = {"name": "Managers with statement issues", "definition": "Count of managers with at least one late, restated, missing statement or staff‑change email in the last 90 days, "
                                                                  "broken down by issue type and total per manager."}
    assert (R.match(k) or {}).get("id") != "missing_statements"  # r3b: a count of managers bound to the statements still missing (12 funds at 0)
    assert (R.match({"name": "Missing statements", "definition": "Late statements by fund and month"}) or {}).get("id") == "missing_statements"


def test_uc085_a_grants_check_that_mentions_bank_statements_is_not_the_missing_statements_recipe():
    k = {"name": "Reconciliation check (paid vs bank)", "definition": "Verification that total paid grants match the amounts received in bank statements",
         "formula": "Compare sum of paid grant transactions to sum of relevant bank payment entries"}
    assert (R.match(k) or {}).get("id") != "missing_statements"  # r3b: it was, so the grant budget question read 185 statement rows


def test_a_tie_of_two_recipes_by_their_word_sets_is_left_to_the_model_not_a_crash(monkeypatch):
    two = [{"id": "a", "label": "Alpha", "names": [], "words_all": [["red"], ["blue"]], "formula": "x"}, {"id": "b", "label": "Beta", "names": [], "words_all": [["red"], ["blue"]], "formula": "y"}]
    monkeypatch.setattr(R, "recipes", lambda: two)
    assert R.match({"name": "red blue thing"}) is None  # r3b: IndexError, the tie was re-scored by names that a words_all tie does not have
    assert R.match({"name": "red blue thing", "definition": "alpha"})["id"] == "a"  # the formula words lead


# ---- the answers: each recipe on the office6m warehouse says the numbers of its card ---------------------------------------------------------

def test_uc054_cash_against_the_calls_and_payments_in_30_60_and_90_days(office):
    said = _said(office, "liquidity_ladder")  # "How much cash do we have against calls and payments in the next 30, 60 and 90 days?"
    _has(said, "2,424,029.85", "131,654.02", "393,801.77", "780,228.08", "1,930,584.33", "1,822,351.67", "1,801,427.23", "1,736,127.24")
    assert said.index("within 30 days") < said.index("within 60 days") < said.index("within 90 days")  # shortest window first


def test_uc055_which_actions_need_a_decision_or_a_booking(office):
    said = _said(office, "actions_next_14d")
    _has(said, "Tidewater Energy tender offer", "31.5", "29.28", "7.58", "70,000", "58,500", "10 actions to book add up to 93,190.20")


def test_uc064_whether_to_hedge_a_currency_exposure(office):
    _has(_said(office, "currency_exposure"), "5,150,694.59", "3,843,801.93", "6,707,500", "5,005,597.01", "7.62", "112,272,239.48", "116,116,041.41")


def test_uc065_the_real_assets_their_values_and_who_holds_them(office):
    said = _said(office, "real_asset_value")
    _has(said, "17,990,298.5", "7,164,179.1", "4,776,119.4", "11,940,298.5", "10,764,179.1", "5,426,119.4", "title is held by Lin Chen")
    assert all(a in said for a in ("RA-01", "RA-02", "RA-03", "RA-04", "RA-05", "RA-06"))  # r3b: RA-04 only


def test_uc066_whether_to_order_a_new_appraisal(office):
    said = _said(office, "appraisal_age")
    _has(said, "784 days", "378 days", "353 days", "329 days", "225 days", "125 days")
    assert said.index("Fine art collection") < said.index("Not yet due") < said.index("Bayview Residence")  # the two past 365 days come first


def test_uc067_which_lots_to_sell_for_a_tax_or_rebalance_reason(office):
    rows = office.run("unrealised_gain")
    h = next(r for r in rows if r["security"] == "Harborview Semiconductor" and r["first_of_security"])
    assert (h["limit_pct"], h["sell_to_limit"]) == (Decimal("5.00"), Decimal("324210.53"))  # the signed single-name limit, the sale also leaving the book
    assert all(r["sell_to_limit"] is None for r in rows if r["limit_pct"] is not None and r["holding_pct"] <= r["limit_pct"])
    assert all(r["loss"] == -r["gain"] for r in rows if r["is_loss"]) and all(r["loss"] is None for r in rows if not r["is_loss"])
    said = F.say(R.recipe("unrealised_gain"), rows) or ""
    _has(said, "66 open lots", "4,030,570", "-1,454,950", "-159,480", "504,900", "621,340", "324,210.53")
    assert said.index("-159,480") < said.index("-144,650")  # the largest loss first


def test_uc067_without_a_signed_limit_no_sale_is_worked_out(office):
    office.con.execute("begin")
    try:
        office.con.execute("update rule_versions set approval_status = 'draft' where json_extract_string(parameters, '$.dimension') = 'single_name'")
        rows = office.run("unrealised_gain")
    finally:
        office.con.execute("rollback")
    assert all(r["limit_pct"] is None and r["sell_to_limit"] is None for r in rows)
    assert "single-name limit" not in (F.say(R.recipe("unrealised_gain"), rows) or "")  # never a guessed limit


def test_uc068_how_much_income_to_plan_for_next_year(office):
    _has(_said(office, "income_forecast"), "811,406.6", "362,000", "449,406.6", "151,690.2", "122,500", "208,302.2", "272,302.2", "56,612", "54 payments")


def test_uc069_whether_the_family_is_over_exposed_through_funds(office):
    _has(_said(office, "lookthrough_exposure"), "2,740,050", "2,378,900", "1,393,000", "1,381,200", "1,374,600", "4,114,650", "1,779,300", "4.21", "7.46", "111,033,700")


def test_uc070_how_much_cash_is_idle_above_the_90_day_need(office):
    _has(_said(office, "idle_cash"), "2,424,029.85", "1,643,801.77", "530,228.08", "1,572,351.67", "1,486,127.24", "3,588,706.99")


def test_uc073_whether_spending_is_sustainable(office):
    said = _said(office, "cash_runway")
    _has(said, "6,156,041.41", "243,977.13", "25.23", "198.5", "42,273,700", "580,620.95")
    assert said.index("Staff") < said.index("Debt service")  # what it is spent on, largest first


def test_cash_forecast_says_the_months_under_the_floor(office):
    said = _said(office, "cash_forecast")  # card 72
    _has(said, "6,156,041.41", "-4,904,705.37", "5,654,705.37", "Months under the 750,000 floor:", "2027-03 closes at 242,129.88")


# ---- the branches the office6m data does not reach ----------------------------------------------------------------------------------------------

def test_a_ladder_row_under_the_buffer_and_one_that_could_not_be_worked_out_are_said():
    rows = [{"entity": "A", "window_days": 30, "cash_usd_equivalent": Decimal("300000.00"), "calls": Decimal("100000.00"), "approved_and_scheduled_payments": Decimal("50000.00"),
             "cash_after": Decimal("150000.00"), "buffer": Decimal("250000.00"), "below_buffer": True, "unconverted": 0},
            {"entity": "B", "window_days": 30, "cash_usd_equivalent": None, "calls": None, "approved_and_scheduled_payments": None, "cash_after": None, "buffer": Decimal("250000.00"),
             "below_buffer": None, "unconverted": 1}]
    said = F.say(R.recipe("liquidity_ladder"), rows)
    _has(said, "A drops under the 250,000 buffer within 30 days", "leaves 150,000", "B 30 days: not worked out")


def test_an_entity_short_of_its_90_day_need_is_said_with_the_shortfall():
    rows = [{"entity": "A", "window_days": 90, "cash_usd_equivalent": Decimal("100000.00"), "outflow": Decimal("400000.00"), "buffer": Decimal("250000.00"),
             "idle": Decimal("0.00"), "short": Decimal("550000.00"), "total_idle": Decimal("0.00"), "total_short": Decimal("550000.00")}]
    _has(F.say(R.recipe("idle_cash"), rows), "A is short 550,000", "Shortfalls across the entities add up to 550,000")


def test_one_word_serves_one_word_group_only():
    groups = [["approval", "limits"], ["over", "limits"]]
    assert not R._covers({"limits"}, groups) and R._covers({"approval", "limits"}, groups) and R._covers({"limits", "over"}, groups) and R._covers(set(), [])
    # score50 card 34: "Fit against class, size, liquidity limits" is not the payments over their approval limit
    assert (R.match({"name": "Fit against class, size, liquidity limits", "formula": "Fund class and ticket size against policy limits and budget headroom"}) or {}).get("id") != "approval_exceptions"
    assert (R.match({"name": "Payments above limit (USD)"}) or {}).get("id") == "approval_exceptions"
