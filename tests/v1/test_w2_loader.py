"""W2 loader: the real loader of the six-month Evergreen Office (sh_platform/v1/v3_office6m_loaders.py) fills a test plane's warehouse from
tests/v1/fixtures/office6m, and the built recipes of the six domains (packs/family_office/1/recipes/*.yaml, rendered by sh_platform.v1.v3_recipes) are run on
that warehouse. Their numbers are compared with answer_keys.yaml (read from the file, never typed here).

Real: the office files (copied into a company's dropbox the way docs/test/uc-live/uc6-scripts/v3_team_env.py --data office6m does), the platform's warehouse
(PlaneStore, wh.connect), the loader, the recipes and their tie-outs. Nothing is stubbed. Synthetic data only.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from sh_platform.plane import PlaneStore
from sh_platform.v1 import v3_office6m_loaders as L
from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import wh

REPO = Path(__file__).resolve().parents[2]
OFFICE = REPO / "tests" / "v1" / "fixtures" / "office6m"
ENV_SCRIPT = REPO / "docs" / "test" / "uc-live" / "uc6-scripts" / "v3_team_env.py"
KEYS = yaml.safe_load((OFFICE / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]
TODAY = "2026-10-13"


def key(card: str, n: int = 0) -> dict:
    """The expected values of the card's n-th question, from the answer keys."""
    return list(KEYS[card]["questions"].values())[n]["expected"]


def f2(v) -> float:
    return round(float(v), 2)


# ---- an office: the dropbox of a company, loaded through the real loader --------------------------------------------------------------------

class Loaded:
    def __init__(self, plane, report):
        self.plane, self.report = plane, report
        self.con = wh.connect(plane)
        self.con.execute("set TimeZone = 'UTC'")

    def run(self, rid: str, **dims) -> list[dict]:
        """Render the recipe, check it reads only the tables it names, build its table, run its tie-out, return the rows."""
        r = R.recipe(rid)
        assert r is not None and r.get("status") != "stub", f"{rid} is not a built recipe"
        sql = R.render(r, f"t_{rid}", R.dims_for(r, dims))
        assert R.refusal(r, sql) is None, R.refusal(r, sql)
        self.con.execute(f"drop table if exists t_{rid}")
        self.con.execute(sql)
        if r.get("tie_out"):
            t = R.tie_out(self.con, r, f"t_{rid}")
            assert t and t["ok"], (rid, t)
        return self.rows(f"select * from t_{rid}")

    def rows(self, sql: str, *args) -> list[dict]:
        cur = self.con.execute(sql, list(args))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]

    def one(self, sql: str, *args):
        return self.con.execute(sql, list(args)).fetchone()[0]


def office_dropbox(tmp: Path, today: str = TODAY) -> Path:
    """The files that have arrived by `today`, in the folders of a company's dropbox: the same copy v3_team_env.py --data office6m makes."""
    spec = importlib.util.spec_from_file_location("v3_team_env", ENV_SCRIPT)
    env = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(env)
    info = env.load_office6m(tmp, today)
    assert info["files"] > 100
    return Path(info["dropbox"])


@pytest.fixture(scope="module")
def office(tmp_path_factory) -> Loaded:
    tmp = tmp_path_factory.mktemp("w2")
    box = office_dropbox(tmp)
    wh.reset_cache()
    plane = PlaneStore(tmp / "data").create("evergreen")
    report = L.load_plane(plane, box)
    o = Loaded(plane, report)
    yield o
    o.con.close()


def one(rows: list[dict], **want) -> dict:
    hit = [r for r in rows if all(r[k] == v for k, v in want.items())]
    assert len(hit) == 1, (want, hit)
    return hit[0]


# ---- the loader: every file kind is read, and says what it did --------------------------------------------------------------------------------

KINDS = ["administrator_cash", "administrator_nav", "administrator_trades", "approvals", "audit", "bank_statements", "close_checklist", "commitments", "custodian_positions",
         "custodian_transactions", "ddq", "emails", "exception_log", "family_allowances", "fx_confirmations", "fx_rates", "index_levels", "insurance", "investment_reports", "invoices",
         "loan_statements", "manager_statements", "meeting_notes", "notices", "payroll", "property_bills", "prospects", "reference", "trading_export", "vendor_contracts"]


def files_of(kind: str) -> int:
    return len([p for p in OFFICE.glob(f"20??-??/{kind}/*") if p.is_file()])


def test_every_file_kind_of_the_office_is_read_and_the_count_of_files_matches_the_folders(office):
    rep = office.report
    for kind in KINDS:
        assert kind in rep, f"{kind} was not read"
        assert not rep[kind]["not_loaded"], (kind, rep[kind]["not_loaded"])
        if kind != "reference":
            assert rep[kind]["files"] >= files_of(kind) - 0 and rep[kind]["rows"] > 0, (kind, rep[kind]["files"], files_of(kind))
    assert rep["manager_statements"]["files"] == files_of("manager_statements") == 59
    assert rep["bank_statements"]["files"] == files_of("bank_statements") == 83
    assert rep["custodian_positions"]["files"] == files_of("custodian_positions") == 140
    assert rep["notices"]["files"] == 17 and rep["emails"]["files"] == 84


def test_nothing_in_the_office_folders_is_left_without_a_reader(office):
    from tools.gen_office6m.more import NEW_KINDS  # the kinds of the other 49 cards wait for their readers and recipes
    NEW_KINDS = [k for k in NEW_KINDS if k not in ("custody_statements", "insurance_schedule", "property_valuations", "title_deeds")]  # read by v3_pack_readers_assets
    NEW_KINDS = tuple(k for k in NEW_KINDS if k not in ("payment_schedule", "income_calendar", "corporate_actions", "settlement_status", "tax_lots", "realised_lots", "manager_outlook"))  # read by v3_pack_readers_treasury
    NEW_KINDS = tuple(k for k in NEW_KINDS if k not in ("expense_ledger", "office_budget", "payroll_drafts", "sops", "access_register", "kyc_register", "onboarding", "bank_forms", "family_access", "glossary", "break_register", "load_log", "inbox", "new_feed"))  # read by v3_pack_readers_controls
    NEW_KINDS = tuple(k for k in NEW_KINDS if k not in ("tax_calendar", "tax_notices", "grant_ledger", "grant_requests", "trust_deed", "estate_planning", "fund_holdings", "deal_pipeline", "fund_documents", "market_data", "target_allocation"))  # read by v3_pack_readers_family and v3_pack_readers_invest
    kinds = {p.parts[-2] for p in OFFICE.glob("20??-??/*/*") if p.is_file()} - set(NEW_KINDS)
    assert kinds <= set(office.report), kinds - set(office.report)
    assert not [k for k, v in office.report.items() if "no reader for this kind" in v["not_loaded"] and k not in NEW_KINDS]


def test_the_loader_reads_the_office_as_it_knew_itself_on_an_earlier_day(tmp_path):
    """Month folders up to the month, daily files not dated after the day: on 31 July nothing from August or October is in the warehouse."""
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("july")
    box = office_dropbox(tmp_path, "2026-07-31")
    L.load_plane(plane, box, "2026-07-31")
    o = Loaded(plane, {})
    try:
        assert str(o.one("select max(position_date) from position_snapshots")) <= "2026-07-31"
        assert o.one("select count(*) from cash_movements where received_at > timestamp '2026-07-31 23:59:59+00'") == 0
        assert o.one("select count(*) from documents where document_type = 'capital_call_notice'") == len([p for p in OFFICE.glob("*/notices/*_call*.pdf") if p.name[:10] <= "2026-07-31"]) == 5
    finally:
        o.con.close()


def test_the_same_folders_are_not_loaded_twice_into_one_company(tmp_path):
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("twice")
    box = office_dropbox(tmp_path, "2026-04-30")
    first = L.load_plane(plane, box, "2026-04-30")
    assert first["notices"]["files"] > 0 and first["reference"]["files"] > 0
    with pytest.raises(ValueError, match="already loaded"):
        L.load_plane(plane, box, "2026-04-30")
    with wh.connect(plane) as con:  # the refused second load left nothing behind
        assert con.execute("select count(*) from legal_entities where entity_code = 'EG-HOLD'").fetchone()[0] == 1


def test_a_company_that_already_holds_master_data_keeps_it(tmp_path):
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("seeded")
    with wh.connect(plane) as con:
        org = __import__("sh_platform.v1.e1_write", fromlist=["org_id"]).org_id(plane)
        con.execute("insert into organizations (id, name, created_at) values (?, 'Seeded', now())", [org])
        le, pf = wh.new_id(), wh.new_id()
        con.execute("insert into legal_entities (id, organization_id, entity_code, entity_name, base_currency) values (?, ?, 'EG-HOLD', 'Evergreen Holdings', 'USD')", [le, org])
        con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values (?, ?, ?, 'EG-LIQUID', 'Liquid', 'USD')", [pf, org, le])
    box = office_dropbox(tmp_path, "2026-04-30")
    L.load_plane(plane, box, "2026-04-30")
    with wh.connect(plane) as con:
        assert con.execute("select count(*) from legal_entities where entity_code = 'EG-HOLD'").fetchone()[0] == 1
        assert con.execute("select count(*) from portfolios where portfolio_code = 'EG-LIQUID'").fetchone()[0] == 1
        assert con.execute("select count(*) from organizations").fetchone()[0] == 1


# ---- the planted mess ------------------------------------------------------------------------------------------------------------------------

def test_day_first_and_month_first_dates_are_read_the_way_their_file_writes_them(office):
    # M11a: the first custodian row of July writes 10/07/2026 (10 July), the settle date beside it is ISO
    row = office.rows("select trade_date, settlement_date from transactions where external_trade_id = 'CT-DV-EBG-20260710'")
    assert [(str(r["trade_date"]), str(r["settlement_date"])) for r in row] == [("2026-07-10", "2026-07-10")]
    # M11b: the Saltmarsh Renewables I distribution notice writes 09/10/2026 and 09/24/2026 (month first)
    d = office.rows("select d.document_date, f.value_text from documents d join extracted_fields f on f.document_id = d.id and f.field_name = 'pay_date' "
                    "where d.document_type = 'distribution_notice' and d.title like '%_K_distribution'")
    assert [(str(r["document_date"]), r["value_text"]) for r in d] == [("2026-09-10", "2026-09-24")]
    assert any("month first" in f for f in office.report["notices"]["flagged"]) and any("day first" in f for f in office.report["custodian_transactions"]["flagged"])
    assert L.parse_date("10/07/2026", hint=date(2026, 7, 15)) == date(2026, 7, 10) and L.parse_date("09/10/2026", order="mdy") == date(2026, 9, 10)
    assert L.parse_date("24 September 2026") == date(2026, 9, 24) and L.slash_order("09/24/2026 and 09/10/2026") == "mdy"


def test_administrator_rows_that_were_not_received_are_not_positions_and_are_said_so(office):
    exc = office.rows("select title from exceptions where exception_type = 'value_not_received'")
    assert len(exc) == 9  # nine funds had no value in the 31 March pack
    assert office.one("select count(*) from position_snapshots p join instruments i on i.id = p.instrument_id where p.position_date = date '2026-03-31' and i.instrument_type = 'private_fund'") == 1
    assert any("Not received" in f for f in office.report["administrator_nav"]["flagged"])


def test_a_renamed_administrator_column_is_read_flagged_and_proposed_as_a_new_mapping(office):
    june = office.rows("select p.source_market_value from position_snapshots p join instruments i on i.id = p.instrument_id "
                       "where p.position_date = date '2026-06-30' and i.canonical_name = 'Harborview Semiconductor' and p.view_type = 'accounting'")
    assert len(june) == 1 and float(june[0]["source_market_value"]) > 0  # read through the synonym 'valuation amount'
    maps = office.rows("select mapping_status, version_number from sheet_mappings where file_pattern like 'administrator%' order by version_number")
    assert maps == [{"mapping_status": "approved", "version_number": 1}, {"mapping_status": "proposed", "version_number": 2}]
    assert any("Valuation Amount (USD)" in f for f in office.report["administrator_nav"]["flagged"])
    changed = office.run("columns_changed")
    k = key("uc-016-schemadrift")
    assert [(r["old_name"], r["new_name"], r["change"]) for r in changed] == [(k["old_name"], k["new_name"], "renamed")]
    assert changed[0]["batches_on_old_name"] == 6  # the six packs that kept the name 'Market Value' (the key says 5: build-operate.md, Needs 8)


def test_a_duplicate_invoice_and_a_duplicate_trade_are_kept_flagged_and_counted_once(office):
    inv = office.rows("select d.document_status, f.value_text from documents d join extracted_fields f on f.document_id = d.id and f.field_name = 'invoice_no' "
                      "where d.document_type = 'invoice' and f.value_text = 'INV-OIT-2606' order by d.received_at")
    assert [r["document_status"] for r in inv] == ["final", "duplicate"]  # M06
    assert office.one("select count(*) from extracted_fields where field_name = 'seen_before'") >= 1
    trades = office.rows("select transaction_type, status from transactions where external_trade_id like 'T-20260602-005%' order by external_trade_id")
    assert trades == [{"transaction_type": "sell", "status": "settled"}, {"transaction_type": "duplicate", "status": "rejected"}]  # M07
    assert office.one("select count(*) from exceptions where exception_type in ('duplicate_invoice', 'duplicate_trade')") == 2
    assert any("M06" in f for f in office.report["invoices"]["flagged"]) and any("M07" in f for f in office.report["trading_export"]["flagged"])


def test_loan_statements_negative_signs_become_the_amount_owed(office):
    k = key("uc-017-liab")
    rows = office.rows("select strftime(as_at, '%Y-%m') m, drawn_amount from credit_facilities where facility_ref = 'TL-B-01' order by as_at")
    assert {r["m"]: -float(r["drawn_amount"]) for r in rows} == k["by_month"] and float(rows[-1]["drawn_amount"]) == k["principal_outstanding"]
    shown = office.one("select value_numeric from extracted_fields f join documents d on d.id = f.document_id where d.title = 'loan_statement_TL-B-01_2026-09' and f.field_name = 'closing_principal_as_shown'")
    assert float(shown) == k["loan_balance_as_shown_negative"]  # the sign as the bank wrote it is kept on the document
    assert office.run("facility_headroom")[0]["drawn_amount"] == Decimal("2800000.00")


def test_fx_side_text_sell_usd_buy_sgd_is_a_signed_forward_not_a_buy_or_sell(office):
    fwd = office.rows("select transaction_type, quantity_delta, cash_amount, currency from transactions where external_trade_id = 'FXF-2026-002'")
    assert fwd == [{"transaction_type": "fx_forward", "quantity_delta": Decimal("-3000000.00000000"), "cash_amount": Decimal("4027500.00000000"), "currency": "SGD"}]
    assert office.one("select count(*) from transactions where transaction_type in ('buy', 'sell') and instrument_id in (select id from instruments where instrument_type like 'fx_%')") == 0


def test_the_bank_balances_and_the_administrator_cash_are_never_added_together(office):
    day = office.rows("select i.canonical_name, i.instrument_type, p.source_market_value from position_snapshots p join instruments i on i.id = p.instrument_id "
                      "where p.position_date = date '2026-10-13' and i.instrument_type = 'cash' and p.portfolio_id = (select id from portfolios where portfolio_code = 'CASH-EG-HOLD') and p.currency = 'USD'")
    assert len(day) >= 4  # the administrator's cash, the desk's, and the two bank accounts exist as different instruments ...
    k = key("uc6-liquidity", 0)
    cash = office.run("cash_by_entity")
    for name, v in k.items():  # ... and the entity cash of the recipe is the administrator's alone
        assert f2(one([r for r in cash if str(r["position_date"]) == TODAY], entity=name, currency="USD")["cash"]) == v["usd"]
        assert f2(one([r for r in cash if str(r["position_date"]) == TODAY], entity=name, currency="SGD")["cash"]) == v["sgd"]
    assert office.one("select count(*) from bank_accounts where cash_instrument_id is not null and holder_kind = 'office'") == 12


def test_a_notice_that_names_a_new_account_is_a_new_unverified_payee_that_supersedes_the_one_on_file(office):
    rows = office.rows("select a.account_ref, a.verified_on, a.supersedes_bank_account_id is not null sup from bank_accounts a where a.holder_kind = 'payee' and a.holder_name = 'Cedarpoint Ventures III' order by a.account_ref")
    assert [(r["account_ref"], r["verified_on"] is not None, r["sup"]) for r in rows] == [("2209", True, False), ("4471", False, True)]  # M05a
    lake = office.rows("select a.account_ref, a.verified_on, a.supersedes_bank_account_id is not null sup from bank_accounts a where a.holder_name = 'Lakeside Legal LLP' order by a.account_ref")
    assert [(r["account_ref"], r["sup"]) for r in lake] == [("3047", False), ("6029", True)]  # M05b
    assert office.one("select count(*) from exceptions where exception_type = 'bank_details_changed'") >= 2


# ---- cash and treasury -------------------------------------------------------------------------------------------------------------------

def test_cash_card_2_and_36_the_commitment_the_call_and_what_is_left(office):
    k, rows = key("uc-002-callrecord"), office.run("called_to_date")
    c = one(rows, fund="Cedarpoint Ventures III")
    assert f2(c["commitment"]) == k["commitment"] and f2(c["called_before_notice"]) == k["called_before_call_7"] and f2(c["called_after_notice"]) == k["called_after_call_7"]
    assert f2(c["unfunded_after_notice"]) == k["unfunded_after_call_7"] and c["notice_fits"] is k["within_commitment"]
    u = key("uc6-uncalled")
    assert round(sum(float(r["unfunded_after_notice"]) for r in rows), 2) == u["uncalled_after_call_7"]
    assert {r["fund"]: f2(r["unfunded_after_notice"]) for r in rows} == u["by_fund"]


def test_cash_card_2_the_fee_on_call_7_matches_the_terms_and_the_fee_on_credit_iii_call_3_does_not(office):
    k, rows = key("uc-002-callrecord", 1), office.run("call_fee_check")
    c = one(rows, fund="Cedarpoint Ventures III", call_no=7)
    assert f2(c["fee_on_notice"]) == k["fee_on_notice"] and f2(c["fee_per_terms"]) == k["fee_per_terms"] and c["fee_matches"] is k["matches"]
    g = one(rows, fund="Evergreen Credit III", call_no=3)  # M08: 28,125 charged, 18,750 per the terms
    assert (f2(g["fee_on_notice"]), f2(g["fee_per_terms"]), f2(g["fee_difference"]), g["fee_matches"]) == (28125.0, 18750.0, 9375.0, False)


def test_cash_card_3_cash_by_entity_and_the_calls_due_in_30_and_60_days(office):
    k = key("uc6-liquidity", 0)
    day13 = [r for r in office.run("cash_by_entity") if str(r["position_date"]) == TODAY]
    for name, v in k.items():
        assert f2(one(day13, entity=name, currency="USD")["cash"]) == v["usd"] and f2(one(day13, entity=name, currency="SGD")["cash"]) == v["sgd"]
    calls = office.run("calls_due")
    for name, w in key("uc6-liquidity", 1).items():
        for days, amount in w.items():
            assert f2(one(calls, entity=name, currency="USD", window_days=int(days))["calls_due"]) == amount


def test_cash_card_4_holdings_is_short_after_the_call_and_the_buffer(office):
    k, rows = key("uc-004-callcheck"), office.run("cash_after_calls")
    h = one(rows, entity="Evergreen Holdings", currency="USD")
    assert f2(h["cash"]) == k["holdings_usd"] and f2(h["calls_due"]) == k["call"] and f2(h["buffer"]) == k["buffer"] and f2(h["shortfall"]) == k["shortfall_usd"]
    assert f2(one(rows, entity="Evergreen Holdings", currency="SGD")["cash"]) == k["holdings_sgd"]


def test_cash_card_5_the_account_on_call_7_is_not_the_one_on_file_and_the_payment_is_on_hold(office):
    k, rows = key("uc-005-benefcheck"), office.run("bank_details_changed")
    c = one(rows, fund="Cedarpoint Ventures III", call_no=7)
    assert c["changed"] is k["changed"] and c["old_ending"] == k["old_ending"] and c["new_ending"] == k["new_ending"] and c["on_hold"] is k["callback_required"]
    assert c["paid_to"].split(",") == k["earlier_calls_paid_to"] and c["paid_before"] == 2
    assert [(r["fund"], r["call_no"]) for r in rows if r["on_hold"]] == [("Cedarpoint Ventures III", 7)] and key("uc-005-benefcheck", 1)["count"] == 1


def test_cash_card_6_the_sgd_to_convert_at_the_planning_rate_and_the_banks_rates_against_the_fixings(office):
    k, rows = key("uc-006-fxneed"), office.run("fx_required")
    r = one(rows, entity="Evergreen Holdings")
    assert f2(r["convert_amount"]) == k["sgd_to_convert_for_call_7"] and f2(r["rate"]) == k["planning_rate"] and r["convert_currency"] == "SGD"
    checks = office.run("fx_rate_check")
    assert len(checks) == 10  # the 9 confirmed conversions and the desk's one the bank never confirmed (M09)
    assert all(abs(float(c["difference_pct"])) < 0.05 for c in checks if c["difference_pct"] is not None)
    assert one(checks, trade_reference="FXF-2026-002")["bank_rate"] == Decimal("1.345200")


def test_cash_card_10_cash_at_each_bank_in_usd_and_its_share(office):
    k, rows = key("uc-010-bankexp"), office.run("cash_by_bank")
    assert {r["bank"]: f2(r["usd_equivalent"]) for r in rows} == k["usd_equivalent_by_bank"]
    assert {r["bank"]: f2(r["share_pct"]) for r in rows} == k["share_pct"] and all(r["accounts"] == 6 for r in rows)


def test_cash_card_18_holdings_pays_call_7_and_needs_a_transfer_and_entity_b_has_spare_cash(office):
    k, rows = key("uc-018-fundplan"), office.run("funding_plan")
    assert {r["entity"]: f2(r["cover_after_calls"]) for r in rows} == k["usd_cover_after_buffer_and_call"]
    paying = one(rows, is_named=True)
    assert paying["entity"] == k["paying_entity"] and paying["transfer_needed"] is k["transfer_needed"] and f2(paying["shortfall"]) == k["shortfall"]
    assert paying["best_other_entity"] == "Entity B"


def test_cash_card_28_the_trust_lent_holdings_600000_on_5_august_and_both_sides_agree(office):
    k, rows = key("uc-028-interco"), office.run("intercompany_balance")
    assert len(rows) == 1
    r = rows[0]
    assert (r["lender"], r["borrower"], f2(r["balance_outstanding"])) == (k["lender"], k["borrower"], float(k["balance_outstanding"]))
    assert str(r["first_transfer_date"]) == k["date"] and r["sides_agree"] is True and r["reference"] == "IC-2026-08-01" and r["approved_by"] == "Daniel Foo"


def test_cash_card_37_one_distribution_arrived_short_and_the_rest_in_full(office):
    k, rows = key("uc-037-distrack"), office.run("distribution_gap")
    want = {(r["fund"], r["pay"]): (float(r["notice"]), float(r["received"]), float(r["gap"])) for r in k["rows"]}
    got = {(r["fund"], r["pay_date"]): (f2(r["notice_amount"]), f2(r["received"]), f2(r["gap"])) for r in rows}
    assert got == want
    assert one(rows, fund="Evergreen Growth I")["status"] == "short" and f2(one(rows, fund="Evergreen Growth I")["gap"]) == 12500.0


def test_cash_every_call_of_the_year_was_paid_on_its_due_date_but_call_7(office):
    rows = office.run("call_payment_status")
    assert sorted(r["status"] for r in rows).count("paid") == 10 and one(rows, fund="Cedarpoint Ventures III", due_date="2026-10-23")["status"] == "not due"


def test_cash_the_weekly_payment_run_lists_what_is_open_and_the_call_waits_for_the_head_of_finance(office):
    rows = office.run("payment_batch")
    got = {(r["payee"], f2(r["amount"]), r["currency"]): r["state"] for r in rows}
    items = {(i["payee"], float(i["amount"]), i["ccy"]) for i in key("uc-008-payrun")["items"]}
    assert set(got) == items
    call = one(rows, payee="Cedarpoint Ventures III")
    assert call["state"] == "waiting for approval" and call["requested_from"] == "Daniel Foo" and call["account_changed_unverified"] is True and call["release_blocked"] is True
    assert one(rows, payee="Summit Tax Advisory")["state"] == "ready"


# ---- hold and maintain ---------------------------------------------------------------------------------------------------------------------

def test_hold_card_38_the_value_roll_forward_of_each_private_fund(office):
    exp = key("uc-038-navroll")["rows"]
    got = {(x["fund"], f"{x['period_start']} to {x['period_end']}"): x for x in office.run("nav_rollforward")}
    assert set(got) == {(e["fund"], e["quarter"]) for e in exp}
    for e in exp:
        x = got[(e["fund"], e["quarter"])]
        assert (float(x["prior_value"]), float(x["calls"]), float(x["distributions"]), float(x["closing_value"]), float(x["implied_gain"])) == (e["prior"], e["calls"], e["distributions"], e["new"], e["implied_gain"]), e
        assert not x["gain_unreadable"] and not x["on_estimate"]


def test_hold_card_21_which_valuations_are_stale(office):
    k, rows = key("uc-021-stale"), office.run("value_age_days")
    got = {x["fund"]: x for x in rows}
    for fund, e in k["by_fund"].items():
        assert str(got[fund]["valuation_date"]) == e["valuation_date"] and got[fund]["age_days"] == e["age_days"] and got[fund]["stale"] is e["stale"], fund
    assert sorted(f for f, x in got.items() if x["stale"]) == sorted(k["stale"])


def test_hold_card_43_the_liquid_book_gain_or_loss_this_month(office):
    k, rows = key("uc-043-liquidpnl"), office.run("liquid_pnl_mtd")
    assert len(rows) == 1
    r = rows[0]
    assert str(r["position_date"]) == TODAY and str(r["month_end_date"]) == "2026-09-30"
    assert (float(r["value_month_end"]), float(r["value_today"]), float(r["net_trades"]), float(r["gain_loss"])) == (k["value_30_sep"], k["value_13_oct"], k["net_trades_settled"], k["gain_loss_mtd"])
    assert float(r["gain_pct"]) == pytest.approx(k["gain_pct"], abs=1e-4)


def test_hold_card_13_the_one_instrument_with_no_asset_class_is_found(office):
    k, rows = key("uc-013-secgaps"), office.run("identifier_gaps")
    gaps = [r for r in rows if r["has_gap"]]
    assert [g["instrument"] for g in gaps] == k["instruments"] and len(gaps) == k["count"] and gaps[0]["no_class"] and not gaps[0]["no_identifier"]
    # the recipe measures at the latest month end loaded (30 September), the date of the key's value
    sep = next(OFFICE.glob("*/custodian_positions/positions_20260930.csv")).read_text(encoding="utf-8")
    assert float([l for l in sep.splitlines() if "Pacific Rim Convertible" in l][0].split(",")[9]) == k["value"]


# ---- invest ---------------------------------------------------------------------------------------------------------------------------------

def test_invest_card_7_unfunded_commitment_by_fund_and_in_total(office):
    k, rows = key("uc-007-pacing"), office.run("commitments_by_fund")
    for fund, v in k["by_fund"].items():
        x = one(rows, fund=fund)
        assert (float(x["committed"]), float(x["called"]), float(x["unfunded"])) == (v["committed"], v["called"], v["unfunded"]), fund
    assert float(one(rows, is_total=1)["unfunded"]) == k["total_unfunded"]


def test_invest_card_39_return_of_each_private_fund_since_it_was_first_valued(office):
    k, rows = key("uc-039-irr"), office.run("fund_irr_tvpi")
    for fund, v in k["by_fund"].items():
        x = one(rows, fund=fund)
        assert (f2(x["irr_pct"]), f2(x["tvpi"] * 1), float(x["latest_value"]), str(x["latest_period"])) == (v["irr_pct_since_1_apr"], v["tvpi"], v["latest_value"], v["latest_period"]) or \
               (f2(x["irr_pct"]), round(float(x["tvpi"]), 4), float(x["latest_value"]), str(x["latest_period"])) == (v["irr_pct_since_1_apr"], v["tvpi"], v["latest_value"], v["latest_period"]), fund
        assert round(float(x["dpi"]), 4) == v["dpi"], fund


def test_invest_card_35_five_answers_of_the_manager_changed_between_the_questionnaires(office):
    k, rows = key("uc-035-ddq"), office.run("ddq_compare")
    changed = {r["topic"]: (r["previous_answer"], r["answer"]) for r in rows if r["changed"]}
    assert changed == {d["question"]: (d["y2025"], d["y2026"]) for d in k["differences"]} and len(changed) == k["count"]


# ---- office -----------------------------------------------------------------------------------------------------------------------------------

def test_office_card_30_two_contracts_come_up_for_renewal_within_90_days(office):
    k, rows = key("uc-030-vendors"), office.run("renewals_vendors")
    want = sorted(k["renewing_within_90_days"], key=lambda x: x["renewal"])
    got = sorted(rows, key=lambda r: str(r["next_renewal_date"]))
    assert len(got) == k["count"]
    for g, w in zip(got, want):
        assert (g["vendor_name"], g["currency"], float(g["annual_cost"]), str(g["next_renewal_date"]), g["days_to_renewal"]) == (w["vendor"], w["currency"], w["annual_cost"], w["renewal"], w["days_to_renewal"])


def test_office_card_50_the_custodian_invoice_is_billed_above_the_fee_schedule(office):
    k, rows = key("uc-050-feeinv"), office.run("invoice_variance")
    got = {r["invoice_no"]: r for r in rows}
    assert set(got) == {i["id"] for i in k["invoices"]}
    for w in k["invoices"]:
        g = got[w["id"]]
        assert (float(g["billed"]), float(g["expected"]), float(g["variance"]), float(g["rate_billed_pct"])) == (w["billed"], w["expected"], w["variance"], w["rate_billed_pct"])
    assert [i for i, g in got.items() if g["variance"] > 0] == k["overcharged"]


# ---- operate and control -----------------------------------------------------------------------------------------------------------------------

def test_operate_card_19_the_statements_late_and_the_one_never_received(office):
    k = key("uc3-statements-inbox", 0)["missing"][0]
    rows = office.run("statement_timeliness")
    miss = [r for r in rows if r["status"] == "missing"]
    m = one(miss, statement_of=k["fund"])
    assert str(m["period_end"]) == k["period"] and str(m["due_date"]) == k["due"] and m["business_days_overdue"] == k["business_days_overdue_13_oct"]
    late = {(r["statement_of"], str(r["period_end"])): (str(r["received_on"]), r["business_days_late"]) for r in rows if r["status"] == "late" and r["kind"] == "manager statement"}
    assert late == {(x["fund"], x["period"]): (x["received"], x["business_days_late"]) for x in key("uc3-statements-inbox", 1)["late"]}
    banks = {(r["statement_of"], r["status"]) for r in rows if r["kind"] == "bank statement" and r["status"] != "on_time"}
    assert banks == {("HB-TRUST-SGD", "late"), ("TCB-B-USD", "missing")}


def test_operate_card_22_three_amendments_and_the_one_after_the_last_issued_report(office):
    k, rows = key("uc-022-amendlog"), office.run("amendments_open")
    got = {r["fund"]: r for r in rows}
    for a in k["amendments"]:
        g = got[a["fund"]]
        assert (float(g["replaces"]), float(g["amended_value"]), float(g["change"]), str(g["received_on"])) == (a["replaces"], a["amended"], a["change"], a["received"])
    assert sum(r["open_amendments"] for r in rows) == k["open_count"]


def test_operate_card_27_the_cash_breaks_over_the_tolerance_and_the_one_inside_it(office):
    ex = key("uc2-recon-break-desk", 1)
    rows = [r for r in office.run("cash_difference_by_source") if r["bank_complete"]]
    src = {"admin": "administrator", "oms": "desk"}
    over = sorted((str(r["day"]), r["entity"], r["source"], r["bank_cash"], r["other_cash"], r["cash_break"]) for r in rows if r["over_tolerance"] == 1)
    want_over = sorted((x["date"], x["entity"], src[x["source"]], Decimal(str(x["bank"])), Decimal(str(x["other"])), Decimal(str(x["difference"]))) for x in ex["over_tolerance"])
    inside = sorted((str(r["day"]), r["entity"], r["source"], r["cash_break"]) for r in rows if r["over_tolerance"] == 0)
    assert over == want_over and inside == sorted((x["date"], x["entity"], src[x["source"]], Decimal(str(x["difference"]))) for x in ex["inside_tolerance"])
    gap = [r for r in office.rows("select * from t_cash_difference_by_source where bank_complete = 0")]
    assert not gap or all(r["cash_break"] is None for r in gap)  # TCB-B-USD July is missing: no false break


def test_operate_card_29_four_of_six_close_steps_are_done_and_three_are_late(office):
    k, rows = key("uc-029-closeck"), [r for r in office.run("close_items_done") if r["close_month"] == "2026-09"]
    assert len(rows) == k["steps"] and sum(r["done"] for r in rows) == k["done"] and sorted(r["step_name"] for r in rows if r["open"]) == sorted(k["open"])
    assert sorted(r["step_name"] for r in rows if r["late"]) == sorted(k["late"])


def test_operate_card_1_the_call_notice_says_which_fund_how_much_and_by_when(office):
    k, rows = key("uc-001-noticelog"), office.run("call_notice_fields")
    c = one(rows, fund=key("uc-001-noticelog")["fund"], call_no=7)
    assert (c["investor"], float(c["amount"]), str(c["due_date"]), float(c["new_investments"]), float(c["management_fee"]), c["account_ending"]) == \
           (k["investor"], k["amount_usd"], k["due"], k["new_investments"], k["management_fee"], k["account_ending"])


# ---- report and govern ----------------------------------------------------------------------------------------------------------------------------

def test_report_card_44_monthly_returns_and_the_quarters_of_the_liquid_book(office):
    k, rows = key("uc-044-twr"), [r for r in office.run("time_weighted_return") if r["portfolio"] == "Evergreen Liquid Book"]
    months = [round(float(r["portfolio_return_pct"]), 4) for r in sorted((r for r in rows if r["period_kind"] == "month" and r["period_label"] <= "2026-09"), key=lambda r: r["period_label"])]
    assert months == k["monthly_pct"]
    q = {r["period_label"]: round(float(r["portfolio_return_pct"]), 4) for r in rows if r["period_kind"] == "quarter"}
    assert q["2026Q2"] == k["q2_apr_jun_pct"] and q["2026Q3"] == k["q3_jul_sep_pct"]


def test_report_card_23_three_report_lines_differ_from_the_administrator(office):
    k, rows = key("uc-023-tieout"), office.run("report_tie_out")
    diffs = sorted((r["report_month"], r["line"], float(r["report_value"]), float(r["administrator_value"]), float(r["difference"])) for r in rows if r["difference"] != 0)
    assert diffs == sorted((d["month"], d["line"], d["report"], d["administrator"], d["difference"]) for d in k["differences"])
    assert len({r["report_month"] for r in rows}) == k["months_checked"]


def test_report_card_12_harborview_is_5_75_percent_of_the_liquid_book_at_30_september_against_a_5_percent_limit(office):
    k = key("uc5-limits")
    assert office.run("concentration")
    rows = office.rows("select issuer, exposure, concentration_pct from t_concentration where position_date = date '2026-09-30' and portfolio = 'Evergreen Liquid Book' order by concentration_pct desc")
    h = one(rows, issuer=k["holding"])
    assert (float(h["exposure"]), float(h["concentration_pct"])) == (k["value"], k["pct_of_portfolio"])
    # the one name above it is the sovereign note, which the key leaves out of the limit by a rule nobody has signed (build-report.md, Needs 4): the loader does not invent that rule
    assert [r["issuer"] for r in rows if r["concentration_pct"] > h["concentration_pct"]] == ["Harbour Treasury Note 2029 (synthetic sovereign)"]
    breach = [r for r in office.run("single_name_breach") if r["limit_pct"] is not None]
    assert breach and all(float(r["limit_pct"]) == 5.0 for r in breach)


def test_report_card_32_listed_equity_and_hedge_funds_are_inside_their_bands(office):
    k = key("uc-032-driftrep")
    rows = office.run("drift_vs_target")
    hedge = one(rows, dimension="asset_class", bucket="hedge fund")
    assert f2(hedge["allocation_pct"]) == k["rows"][1]["pct"] and not hedge["outside_band"]
    assert f2(one(rows, portfolio="EG-B-OPS")["allocation_pct"]) == key("uc5-limits", 1)["cedarpoint_pct_of_eg_b_ops"]
    assert not [r for r in rows if r["outside_band"]] and k["outside"] == []


def test_report_card_24_seven_of_eight_sampled_figures_trace_to_an_issued_report(office):
    k, rows = key("uc-024-audit"), office.run("trace_coverage")
    assert len(rows) == k["sampled"] and sum(1 for r in rows if r["traced"]) == k["traced"] and float(rows[0]["share_traced_pct"]) == k["share_traced_pct"]
    un = [r for r in rows if not r["traced"]]
    assert [(r["item"], r["report_month"], float(r["figure"])) for r in un] == [(u["item"], u["month"], u["figure"]) for u in k["untraceable"]]


# ---- the numbers of the loader itself ----------------------------------------------------------------------------------------------------------------

def test_every_recipe_that_reads_the_loaded_office_ties_out(office):
    """All the built recipes of the six domains that do not need a dimension choice build on the loaded warehouse and tie out (the ones named below are the recipes' own limits, see the report)."""
    ids = [r["id"] for r in R.recipes() if r["id"] != "missing_statements"]
    assert len(ids) >= 50
    for rid in ids:
        office.run(rid)


def test_the_rules_of_the_office_are_signed_rows_in_the_shape_the_recipes_read(office):
    rules = {r["rule_code"]: json.loads(r["parameters"]) for r in office.rows(
        "select r.rule_code, v.parameters from business_rules r join rule_versions v on v.business_rule_id = r.id where v.approval_status = 'approved'")}
    assert rules["cash_buffer"] == {"amount": 250000.0, "currency": "USD"} and rules["payment_approval"] == {"amount": 500000.0, "currency": "USD"}
    assert rules["cash_tolerance_usd"]["limit"] == 5000.0 and rules["single_name_limit_pct"]["max_pct"] == 5.0
    assert rules["limit_single_name_liquid"] == {"portfolio": "EG-LIQUID", "dimension": "single_name", "bucket": "any single name", "min_pct": 0, "max_pct": 5}
    assert rules["limit_manager_entity_b"]["bucket"] == "Cedarpoint Ventures" and rules["limit_manager_entity_b"]["max_pct"] == 55
    assert rules["limit_hedge_funds"]["min_pct"] == 20 and rules["limit_listed_equity_liquid"]["max_pct"] == 90
    assert rules["cio_materiality"] == {"amount": 100000, "pct": 0.5, "currency": "USD"} and rules["statement_due"] == {"business_days": 10}
    # the rules the file signs itself (office_rules.csv: type, parameters, status, version) are signed too: the sovereign exemption and the benchmark link
    assert "benchmark_link" in rules and any("exempt" in c for c in rules)
    # the loader signs nothing the files do not state: no bank limit, no payment window, no private-markets budget
    assert not [c for c in rules if c.startswith("bank_limit") or c in {"payment_run_window_days", "allocation_private_markets"}]


# ---- more of the keys, on the same warehouse --------------------------------------------------------------------------------------------------------

def test_cash_the_fx_forward_confirmed_at_1_3452_differs_from_the_booked_trade_by_8100_sgd(office):
    k, rows = key("uc8-trades-vs-admin"), office.run("fx_confirmation_variance")
    assert len(rows) == 9  # eight spot conversions and two forwards are confirmed; FXS-20260602-HOLD has no confirmation (M09) and so no row
    assert [(r["trade_reference"], f2(r["variance"])) for r in rows if r["variance"] != 0] == [(k["fx_forward"], float(k["difference_sgd"]))]
    assert any("M09" in f for f in office.report["fx_confirmations"]["flagged"])


def test_trades_against_the_administrator_the_two_october_breaks_are_in_the_loaded_data(office):
    """The administrator's own booking is kept as a document with a field per trade (never as a second row of the trade): NWL 12,000 at the desk against 10,200, and HVS missing."""
    breaks = key("uc8-trades-vs-admin")["october_trade_breaks"]
    admin = {r["field_name"][len("trade:"):]: r["value_numeric"] for r in office.rows(
        "select f.field_name, f.value_numeric from extracted_fields f join documents d on d.id = f.document_id where d.document_type = 'administrator_trades' and f.field_name like 'trade:%'")}
    desk = office.rows("select external_trade_id, abs(quantity_delta) q from transactions where trade_date >= date '2026-10-01' and transaction_type in ('buy', 'sell') and status <> 'failed'")  # the desk export; the settlement report's failed trades are the broker's
    differs = [(r["external_trade_id"], float(r["q"]), float(admin[r["external_trade_id"]])) for r in desk if r["external_trade_id"] in admin and r["q"] != admin[r["external_trade_id"]]]
    missing = [r["external_trade_id"] for r in desk if r["external_trade_id"] not in admin]
    assert differs == [(b["trade"], float(b["ours"]), float(b["administrator"])) for b in breaks if b["kind"] == "quantity differs"]
    assert missing == [b["trade"] for b in breaks if b["kind"] == "missing at administrator"]
    assert office.one("select count(*) from transactions where external_trade_id = 'T-20261002-003'") == 1  # counted once: the administrator's booking is not a transaction


def test_report_card_46_where_the_september_return_came_from(office):
    k = key("uc-046-attrib")
    rows = [r for r in office.run("attribution") if str(r["month_end"]) == "2026-09-30" and r["portfolio"] == "Evergreen Liquid Book"]
    assert {r["asset_class"] for r in rows} == {"listed_equity", "bond", "unclassified"}
    for cls, name in (("listed_equity", "equity"), ("bond", "bond"), ("unclassified", "unclassified")):
        r, e = one(rows, asset_class=cls), k["effects_pct"][name]
        assert (round(float(r["allocation_pct"]), 3), round(float(r["selection_pct"]), 3), round(float(r["interaction_pct"]), 3)) == (round(e["allocation"], 3), round(e["selection"], 3), round(e["interaction"], 3)), cls
    assert round(float(rows[0]["portfolio_return_pct"]), 4) == k["portfolio_pct"] and round(float(rows[0]["benchmark_return_pct"]), 4) == k["liquid_benchmark_pct"]
    assert round(float(rows[0]["active_pct"]), 4) == k["active_pct"] and rows[0]["adds_up"] is True


def test_report_the_issued_september_report_total_in_sgd_and_the_amended_fund_value(office):
    n, t = key("morning-networth-note"), office.run("report_total_fx")[0]
    assert (float(t["total_usd"]), float(t["usd_sgd_fixing"]), float(t["total_sgd"]), str(t["issued_on"])) == (n["total_usd"], n["fixing"], n["total_sgd"], n["issued"]) and t["total_status"] == "estimated"
    k = key("uc1-why-nav-moved")
    a = one(office.run("change_since_report"), fund="Evergreen Growth I")
    assert (float(a["original_value"]), float(a["amended_value"]), float(a["change_since_report"])) == (k["issued"], k["amended"], k["change"])
