"""W1b cash (cards 51 to 100 of the Cash and treasury domain: 54, 70, 72, 73), proved on the real pack readers.

Result: none of the four is built. Each needs a source the loader has no reader for (payment schedule, income calendar, manager outlook, expense ledger),
so the recipes stay stubs. This file proves why, and proves the legs of the keys that the loaded plane does give (cash, calls, buffer), so the gap is exactly
the missing reader and nothing else. Expected numbers come from answer_keys.yaml. Synthetic data only."""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

from sh_platform.v1 import v3_recipes as R

_SPEC = importlib.util.spec_from_file_location("w2_loader_tests", Path(__file__).with_name("test_w2_loader.py"))
W2 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(W2)
key, f2, one, TODAY = W2.key, W2.f2, W2.one, W2.TODAY
office = W2.office  # the module fixture: the office files loaded through the real readers

MISSING = {"uc-054-ladder": "payment_schedule", "uc-070-idle": "payment_schedule", "uc-072-cashfc": "payment_schedule", "uc-073-runway": "expense_ledger"}
STUBS = {"liquidity_ladder": 54, "cash_forecast": 72}


@pytest.mark.parametrize("kind", ["payment_schedule", "income_calendar", "manager_outlook", "expense_ledger"])
def test_the_loader_has_no_reader_for_the_sources_of_the_four_cards(office, kind):
    assert "no reader for this kind" in office.report[kind]["not_loaded"], office.report.get(kind)
    assert office.one("select count(*) from source_batches where coalesce(storage_uri, '') like ?", f"%/{kind}/%") == 0


@pytest.mark.parametrize("rid", sorted(STUBS))
def test_the_ladder_and_forecast_recipes_stay_honest_stubs(rid):
    r = next((x for x in R.stubs() if x["id"] == rid), None)
    assert R.recipe(rid) is None
    assert r is not None and r.get("status") == "stub" and not r.get("sql") and STUBS[rid] in r["cards"]


def test_nothing_in_the_plane_is_an_expense_or_a_scheduled_payment_of_the_schedule_file(office):
    assert office.one("select count(*) from cash_movements where movement_type in ('expense', 'scheduled_payment')") == 0
    refs = [r["ref"] for r in csv.DictReader((W2.OFFICE / "2026-10" / "payment_schedule" / "payment_schedule_2026-10-13.csv").open(encoding="utf-8"))]
    assert refs and office.one("select count(*) from source_records where external_record_id in (select unnest(?))", refs) == 0


def test_the_legs_the_plane_does_give_agree_with_the_ladder_and_idle_keys(office):
    ladder, idle = key("uc-054-ladder"), key("uc-070-idle")
    cash = [r for r in office.run("cash_by_entity") if str(r["position_date"]) == TODAY]
    calls = office.run("calls_due")
    for name, v in ladder["by_entity"].items():
        assert f2(one(cash, entity=name, currency="USD")["cash"]) == v["cash_usd"] and f2(one(cash, entity=name, currency="SGD")["cash"]) == v["cash_sgd"]
        for days in ("30", "60"):
            assert f2(one(calls, entity=name, currency="USD", window_days=int(days))["calls_due"]) == v["windows"][days]["calls"]
    after = {r["entity"]: r for r in office.run("cash_after_calls") if r["currency"] == "USD"}
    assert all(f2(after[n]["buffer"]) == v["buffer"] for n, v in idle["by_entity"].items())


def test_what_is_missing_is_exactly_the_payment_leg(office):
    """The key's 30 day payments of Holdings come from the schedule file; the plane's own expected payments (invoices) are a different set."""
    k = key("uc-054-ladder")["by_entity"]["Evergreen Holdings"]["windows"]["30"]["approved_and_scheduled_payments"]
    plane = office.rows("select coalesce(sum(abs(m.amount)), 0) as t from cash_movements as m join portfolios as p on p.id = m.portfolio_id join legal_entities as e on e.id = p.legal_entity_id "
                        "where m.movement_type = 'payment' and m.confirmation_status = 'expected' and e.entity_name = 'Evergreen Holdings' and m.due_date <= date '2026-11-12'")
    assert f2(plane[0]["t"]) != k
