"""Live run 5, answer group (docs/v3/LIVE-R5-ANALYSIS.md): the answer sentences and the readers' sentence, not the binding or the SQL.

Regressions first: every case that passed in run 4 must still pass, so each r4 answer template that the answer changes could touch is pinned here
with the live question's own figure names and synthetic values (the run 4 sentence reproduced, word for word where the run 4 check read it).
The pins call figures.say() on the pack's own answer lines, so a template edit that drops a checked number fails here, not in a live run.

Fixed here: avg_numbers keeps the SQL as written (uc3 and uc-094 read it; the sqlglot round trip rewrote to_char), the plain read names a table's own
period ("2026Q3", uc-044), and the memo keeps the fee part of the latest call (uc-040). Synthetic data only; no live model is called."""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
import yaml

from sh_platform.v1 import v3_figures as F

RECIPES = Path(__file__).resolve().parents[2] / "packs" / "family_office" / "1" / "recipes"


def recipe(file: str, rid: str) -> dict:
    for r in yaml.safe_load((RECIPES / file).read_text(encoding="utf-8"))["recipes"]:
        if r["id"] == rid:
            return r
    raise KeyError(rid)


# ---- the fixes ------------------------------------------------------------------------------------------------------------------

def test_avg_keeps_the_sql_as_written_and_casts_only_the_avg_argument():
    keep = "create table t as select date_trunc('month', d) as m, to_char(d, 'YYYY-MM') as k, avg(x) as a from s group by all"
    out = F.avg_numbers(keep)
    assert "to_char(d, 'YYYY-MM')" in out  # the round trip through sqlglot wrote this as CAST(d AS TEXT)
    assert "avg(CAST(x AS DOUBLE))" in out and out.startswith("create table t as select date_trunc('month', d) as m, to_char(d, 'YYYY-MM') as k, avg(")
    assert F.avg_numbers("select avg(cast(x as double)) from s") == "select avg(cast(x as double)) from s"  # already a cast: unchanged
    assert F.avg_numbers("select avg(distinct x) from s") == "select avg(DISTINCT CAST(x AS DOUBLE)) from s"
    assert F.avg_numbers("select avg(x) over (partition by a) from s") == "select avg(CAST(x AS DOUBLE)) over (partition by a) from s"
    assert F.avg_numbers("select avg(x) from s where to_char(d, 'YYYY') = '2026'") == "select avg(CAST(x AS DOUBLE)) from s where to_char(d, 'YYYY') = '2026'"
    assert F.avg_numbers("not sql at all (") == "not sql at all ("
    assert F.avg_numbers("select sum(x) from s") == "select sum(x) from s"


def test_avg_of_a_yes_no_column_still_builds_in_duckdb():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("create table b (o varchar, d date, ok boolean)")
    con.execute("insert into b values ('o', date '2026-10-02', true), ('o', date '2026-10-05', false)")
    sql = "create table g as select o, strftime(d, '%Y-%m') as month, avg(ok) * 100 as rate from b group by o, strftime(d, '%Y-%m')"  # plain duckdb: strftime, not the warehouse's to_char
    con.execute(F.avg_numbers(sql))
    assert con.execute("select month, rate from g").fetchall() == [("2026-10", 50.0)]


def test_period_said_by_the_table_own_period_not_its_date_month():
    # uc-044: "...quarter · 2026Q3 in June 2026" said the quarter by its as-at month; the table names the period itself
    assert F._period_said(date(2026, 6, 30), False, "June 2026", {"2026Q3"}) == "2026Q3"
    assert F._period_said(date(2026, 6, 30), False, "June 2026", {"2026Q3", "2026Q2"}) == "June 2026"  # more than one name: the month, as before
    assert F._period_said(date(2026, 6, 30), False, "June 2026", set()) == "June 2026"
    assert F._period_said(date(2026, 6, 30), True, "30 June 2026", {"2026Q3"}) == "30 June 2026"  # a day is said by its date
    assert F._period_said(None, False, "", {"2026Q3"}) == ""  # no as-at date: no period


def test_memo_keeps_the_fee_part_of_the_latest_call():
    # uc-040: the 350,000 fee of the latest call was lost from the memo (run 5); the memo's own line now says it
    memo = recipe("invest.yaml", "memo_support")
    rows = [
        {"fund": "Cedarpoint Ventures III", "figure": "fee_in_call", "figure_label": "fee in the latest call", "value": D("350000.00"), "currency": "USD",
         "traced": 1, "source": "call notice record 7"},
        {"fund": "Cedarpoint Ventures III", "figure": "commitment", "figure_label": "commitment", "value": D("10000000.00"), "currency": "USD",
         "traced": 1, "source": "register record 1"},
        {"fund": "Evergreen Credit III", "figure": "unfunded", "figure_label": "unfunded", "value": D("300000.00"), "currency": "USD", "traced": 0,
         "source": ""},
    ]
    said = F.say(memo, rows)
    assert "Fee in the latest call: Cedarpoint Ventures III 350,000 USD." in said
    assert "Not traced: Evergreen Credit III unfunded 300,000." in said
    assert "3 memo figures, 2 traced to a source." in said


def test_memo_fee_line_is_said_for_every_fund_with_a_fee():
    memo = recipe("invest.yaml", "memo_support")
    rows = [{"fund": "A Fund", "figure": "fee_in_call", "figure_label": "", "value": D("10000.00"), "currency": "USD", "traced": 1},
            {"fund": "B Fund", "figure": "fee_in_call", "figure_label": "", "value": D("20000.00"), "currency": "USD", "traced": 1}]
    assert "Fee in the latest call: A Fund 10,000 USD; B Fund 20,000 USD." in F.say(memo, rows)


# ---- run 4 passes: the sentences the r4 checks read, pinned against the templates --------------------------------------------

def test_r4_uc044_the_return_sentence_names_the_period_label():
    # run 4 uc-044 passed on "3.5148" for 2026Q3 (the recipe's own line, latest to_date)
    twr = recipe("report.yaml", "time_weighted_return")
    rows = [{"to_date": date(2026, 6, 30), "portfolio": "Evergreen Liquid portfolio", "period_label": "2026Q2", "portfolio_return_pct": D("1.1"),
             "benchmark_return_pct": D("2.2")},
            {"to_date": date(2026, 9, 30), "portfolio": "Evergreen Liquid portfolio", "period_label": "2026Q3", "portfolio_return_pct": D("3.5148"),
             "benchmark_return_pct": D("5.0052")}]
    assert F.say(twr, rows) == "Evergreen Liquid portfolio 3.5148% for 2026Q3 against 5.0052% for the benchmark."


def test_r4_uc034_the_mandate_line_says_ticket_uncalled_and_after():
    # run 4 uc-034 passed on "2,000,000", "14,600,000", "16,600,000" (the figure's own uncalled, before and after the ticket)
    mandate = recipe("invest.yaml", "mandate_fit")
    row = {"deal_name": "Harborlight Ventures IV", "currency": "USD", "ticket": D("2000000.00"), "uncalled_before": D("14600000.00"),
           "ticket_pct_of_uncalled": D("13.70"), "uncalled_after": D("16600000.00"), "budget_status": "not set"}
    said = F.say(mandate, [row])
    for number in ("2,000,000", "14,600,000", "16,600,000"):
        assert number in said
    assert said.endswith("budget not set.")


def test_r4_uc021_the_stale_lines_name_the_funds_and_their_ages():
    # run 4 uc-021 passed on the three stale funds with 196 and 105 days
    stale = recipe("hold.yaml", "value_age_days")
    rows = [{"fund": "Cedarpoint Opportunities II", "age_days": 196, "valuation_date": date(2026, 3, 31), "stale": True, "stale_after_days": 90},
            {"fund": "Cedarpoint Ventures III", "age_days": 105, "valuation_date": date(2026, 6, 30), "stale": True, "stale_after_days": 90},
            {"fund": "Evergreen Growth I", "age_days": 13, "valuation_date": date(2026, 10, 1), "stale": False, "stale_after_days": 90}]
    assert F.say(stale, rows) == ("Older than 90 days: Cedarpoint Opportunities II 196 days (31 Mar 2026); Cedarpoint Ventures III 105 days (30 Jun 2026).")


def test_r4_uc040_the_call_line_keeps_the_fee_split():
    # run 4 uc-040 passed on "350,000" in the call 7 line of the notice recipe
    call = recipe("operate.yaml", "call_notice_fields")
    row = {"fund": "Cedarpoint Ventures III", "call_no": 7, "currency": "USD", "amount": D("1250000.00"), "new_investments": D("900000.00"),
           "management_fee": D("350000.00"), "due_date": date(2026, 10, 23), "account_ending": "4471"}
    assert F.say(call, [row]) == ("Cedarpoint Ventures III call 7: USD 1,250,000 (900,000 for investments, 350,000 fee) due 23 Oct 2026, "
                                  "to the account ending 4471.")


def test_r4_uc017_the_board_line_says_the_net_worth_and_the_report_date():
    # run 4 uc-017 passed on the family net worth after debt; the board line template keeps its first sentence (the after-debt figures are the
    # binding's to bring, see the analysis, not this template's)
    board = recipe("report.yaml", "board_summary")
    row = {"net_worth_usd": D("57600000.00"), "net_worth_sgd": D("77253120.00"), "usd_sgd_fixing": D("1.3412"), "report_date": date(2026, 9, 30),
           "estimate_note": "Evergreen Growth I is an estimate in the issued report.", "last_quarter": "2026Q3", "last_quarter_return_pct": D("3.5148"),
           "last_quarter_benchmark_pct": D("5.0052"), "performance_from": date(2026, 3, 31), "since_start_return_pct": D("3.821"),
           "since_start_benchmark_pct": D("5.7563"), "cash_usd_eq": D("6156041.41"), "cash_as_of": date(2026, 10, 13),
           "call_shortfall_usd": D("270000.00"), "uncalled_commitments_usd": D("58600000.00"), "amendments_after_report": 1}
    said = F.say(board, [row])
    assert said.startswith("Net worth is 57,600,000 USD and 77,253,120 SGD at the fixing of 1.3412, from the issued report of 30 Sep 2026.")
    assert "Cash is 6,156,041.41 USD at 13 Oct 2026." in said
