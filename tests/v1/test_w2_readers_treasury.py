"""Readers of the treasury group (v3_pack_readers_treasury): payment schedule, income calendar, corporate action notices, settlement report, tax lots,
manager outlooks. Real readers on the six-month office; expected numbers come from answer_keys.yaml or from the files. Synthetic data only."""
from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path

from sh_platform.v1 import v3_pack_readers as PK

_SPEC = importlib.util.spec_from_file_location("w2_loader_tests", Path(__file__).with_name("test_w2_loader.py"))
W2 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(W2)
key, OFFICE = W2.key, W2.OFFICE
office = W2.office  # the module fixture: the office loaded through the real readers

KINDS = ["payment_schedule", "income_calendar", "corporate_actions", "settlement_status", "tax_lots", "manager_outlook"]
ONE = {"payment_schedule": "2026-10/payment_schedule/payment_schedule_2026-10-13.csv", "income_calendar": "2026-10/income_calendar/income_calendar_2026-10-13.csv",
       "corporate_actions": "2026-10/corporate_actions/2026-10-08_TWE_tender_offer.pdf", "settlement_status": "2026-10/settlement_status/settlement_report_2026-10-13.csv",
       "tax_lots": "2026-10/tax_lots/lot_register_2026-09-30.xlsx", "manager_outlook": "2026-10/manager_outlook/bluewater_distribution_outlook_2026-27.pdf"}


def test_each_kind_is_recognised_from_its_content_not_its_name():
    for kind, rel in ONE.items():
        assert PK.kind_of("renamed.pdf" if rel.endswith("pdf") else "renamed" + Path(rel).suffix, (OFFICE / rel).read_bytes())[0] == kind


def test_every_kind_is_read_and_says_what_it_did(office):
    for kind in KINDS:
        r = office.report[kind]
        assert not r["not_loaded"] and r["files"] == len(list(OFFICE.glob(f"20??-??/{kind}/*"))) and r["rows"] > 0, (kind, r)


def test_payment_schedule_gives_the_stage_and_counts_what_the_key_counts(office):
    rows = office.rows("select * from cash_movements where payment_stage is not null")
    assert len(rows) == 32 and {r["payment_stage"] for r in rows} == {"approved", "scheduled", "held", "expected"}
    assert all(r["amount"] < 0 and r["confirmation_status"] == "expected" and r["reference"] and r["payee_name"] for r in rows)
    # the key: Holdings, next 30 days, approved and scheduled only (SGD at 1.34), the held and expected leave out
    fx = Decimal("1.34")
    got = office.rows("""select m.amount, m.currency from cash_movements m join portfolios p on p.id = m.portfolio_id join legal_entities e on e.id = p.legal_entity_id
                         where e.entity_code = 'EG-HOLD' and m.payment_stage in ('approved', 'scheduled') and m.due_date <= date '2026-11-12'""")
    total = sum((-r["amount"] / (fx if r["currency"] == "SGD" else 1)) for r in got)
    want = key("uc-054-ladder")["by_entity"]["Evergreen Holdings"]["windows"]["30"]["approved_and_scheduled_payments"]
    assert abs(float(total) - want) < 0.02, (total, want)


def test_a_payment_an_invoice_already_expected_is_one_row_with_the_schedule_stage(office):
    held = office.rows("select * from cash_movements where reference = 'FEE-CUST-Q3'")
    assert len(held) == 1 and held[0]["payment_stage"] == "held"
    assert office.one("select count(*) from (select reference from cash_movements where reference is not null and payment_stage is not null group by reference having count(*) > 1)") == 0
    assert "held" in " ".join(office.report["payment_schedule"]["flagged"])


def test_income_calendar_is_expected_dividends_and_coupons(office):
    rows = office.rows("select * from cash_movements where movement_type in ('dividend', 'coupon') and confirmation_status = 'expected'")
    assert len(rows) == key("uc-068-incomef")["events"] == 54
    total = sum(r["amount"] for r in rows)
    assert abs(float(total) - key("uc-068-incomef")["total"] - 0) < 600000  # the key forecasts next year on its own rule; the calendar is the dated part
    assert sum(1 for r in rows if r["movement_type"] == "coupon") == 6 and all(r["due_date"] > W2.date(2026, 10, 13) and r["amount"] > 0 for r in rows)


def test_corporate_actions_keep_the_dates_and_the_tender_offer_needs_a_decision(office):
    rows = office.rows("select a.*, i.canonical_name from corporate_actions a join instruments i on i.id = a.instrument_id")
    assert len(rows) == 12
    want = key("uc-055-corpact")["to_book"]
    for w in want:
        r = next(x for x in rows if x["canonical_name"] == w["security"] and x["action_type"] == w["event"])
        assert str(r["ex_date"]) == w["ex_date"] and str(r["pay_date"]) == w["pay_date"] and not r["election_required"]
        q = office.one("select value_numeric from extracted_fields where document_id = ? and field_name = 'quantity_held'", r["source_document_id"])
        assert float(q) == w["quantity"]
    tender = next(x for x in rows if x["action_type"] == "tender_offer")
    assert tender["election_required"] and str(tender["election_deadline"]) == "2026-10-22" and tender["status"] == "election_open" and tender["elected_option"] is None
    assert office.one("select count(*) from exceptions where exception_type = 'corporate_action_election'") == 1
    coupon = next(x for x in rows if x["action_type"] == "coupon")
    assert float(coupon["rate_per_unit"]) == 0.039


def test_settlement_report_makes_the_two_failed_trades_and_leaves_the_settled_ones_alone(office):
    failed = office.rows("select * from transactions where status = 'failed' order by external_trade_id")
    assert [r["external_trade_id"] for r in failed] == [f["trade"] for f in key("uc-058-settle")["failed"]]
    assert {r["counterparty_name"] for r in failed} == {"Synthetic Broker Two"} and failed[0]["status_reason"] == "seller short delivery"
    assert all(r["cash_amount"] is None for r in failed)
    for t in key("uc-058-settle")["settled_in_report"]:
        assert office.one("select count(*) from transactions where external_trade_id = ?", t) == 1  # the desk's row, not a second one


def test_tax_lots_are_one_row_per_lot_with_the_register_cost(office):
    k = key("uc-067-unrl")
    assert office.one("select count(*) from tax_lots") == k["lots"] == 66
    lot = office.rows("select * from tax_lots where lot_ref = 'LOT-AHS-2'")[0]
    assert float(lot["cost_amount"]) == 793080 and float(lot["quantity"]) == 18000 and str(lot["acquired_on"]) == "2022-02-15" and str(lot["as_at"]) == "2026-09-30"


def test_manager_outlooks_are_one_payout_rate_per_fund_and_quarter(office):
    rows = office.rows("""select i.canonical_name f, f.value_text q, f.value_numeric r from extracted_fields f join documents d on d.id = f.document_id join instruments i on i.id = d.instrument_id
                          where f.field_name = 'projected_payout_rate' order by 1, 2""")
    assert len(rows) == 32
    for fund, v in key("uc-071-expdist")["by_fund"].items():
        got = [float(r["r"]) * 100 for r in rows if r["f"] == fund]
        assert [round(g, 4) for g in got] == [float(x) for x in v["payout_pct"]], (fund, got)


def test_the_same_event_noticed_again_supersedes_the_first_in_the_run():
    from sh_platform.v1 import v3_pack_readers_treasury as T

    class O:
        rows = {"corporate_actions": [{"id": "a", "instrument_id": "i", "action_type": "dividend", "pay_date": 1}]}
        con = None  # nothing on record
    w = "instrument_id = ? and action_type = ? and pay_date = ?"
    assert T._prior(O, "corporate_actions", w, ["i", "dividend", 1]) == "a"
    assert T._prior(O, "corporate_actions", w, ["i", "dividend", 2]) is None
