"""FIXB2: the trade check on the UC8 answer-key months (Jul clean, Aug timing, Sep three breaks, Oct carried). Fixture rows, no loader, no model."""
from datetime import date
from decimal import Decimal

from sh_platform.v1 import e1_write as W
from sh_platform.v1 import e3_recon as R
from sh_platform.v1 import wh
from tests.v1.test_e3b import T, U, plane, trade_setup  # noqa: F401  (plane is the fixture)


def inst(plane, *names):
    with wh.connect(plane) as con:
        for n in names:
            con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, created_at) values (?,?,?,?,?)",
                        [U(n), plane.company_id, n, "fx_forward" if n.startswith("fxf") else "listed_equity", T])


def tx(plane, side, tid, name, qty, amount, day, ccy="USD", eff=None):
    W.record(plane, "transactions", {"source_record_id": U("rec" + side), "portfolio_id": U("pb"), "instrument_id": U(name), "external_trade_id": tid,
                                    "transaction_type": "sell" if qty < 0 else "buy", "trade_date": day, "effective_date": eff or day, "quantity_delta": qty,
                                    "cash_amount": amount, "currency": ccy, "status": "confirmed"})


def both(plane, tid, name, qty, amount, day, **kw):
    tx(plane, "oms", tid, name, qty, amount, day, **kw)
    tx(plane, "adm", tid, name, qty, amount, day, **kw)


def test_july_four_trades_all_match(plane):
    trade_setup(plane)
    inst(plane, "meridian", "bay", "rail", "bond")
    for tid, n, q, a, d in (("T-1", "meridian", 15000, -468000, 6), ("T-2", "bay", -5000, 228000, 14), ("T-3", "bond", 500000, -495750, 21), ("T-4", "rail", 3000, -216300, 28)):
        both(plane, tid, n, q, a, date(2026, 7, d))
    d = R.run_detail(plane, "trade_vs_admin", date(2026, 7, 31))
    assert (d["records"]["trading export"], d["matched"], d["breaks"], d["carried"]) == (4, 4, 0, 0)


def test_august_one_business_day_apart_is_timing_with_its_cause(plane):
    trade_setup(plane)
    inst(plane, "meridian", "bay")
    both(plane, "T-0804", "meridian", 8000, -248000, date(2026, 8, 4))
    tx(plane, "oms", "T-0827", "bay", -8000, 374640, date(2026, 8, 27))
    tx(plane, "adm", "T-0827", "bay", -8000, 374640, date(2026, 8, 28))        # Friday 28 Aug: one business day later
    d = R.run_detail(plane, "trade_vs_admin", date(2026, 8, 31))
    assert (d["records"]["trading export"], d["matched"], d["breaks"]) == (2, 1, 1)
    line = next(r for r in d["results"] if r["breached"])
    assert line["type"] == "timing" and "timing difference" in line["cause"] and "T-0827" in line["cause"]
    assert plane.cases.opened[0]["candidate_impact_amount"] == 0
    again = R.run_detail(plane, "trade_vs_admin", date(2026, 8, 31))      # the rerun finds the same case and keeps the cause
    assert again["opened"] == [] and any(r.get("cause") for r in again["results"])


def sep(plane, mp):
    trade_setup(plane)
    inst(plane, "meridian", "northwind", "fxf2", "harborview")
    both(plane, "T-0903", "meridian", 10000, -321000, date(2026, 9, 3))
    tx(plane, "oms", "T-0917", "northwind", 12000, -505800, date(2026, 9, 17))
    tx(plane, "adm", "T-0917", "northwind", 10200, -429930, date(2026, 9, 17))
    tx(plane, "oms", "F02", "fxf2", 3_000_000, 4_027_500, date(2026, 9, 29), ccy="SGD")
    tx(plane, "adm", "F02", "fxf2", 3_000_000, 4_035_600, date(2026, 9, 29), ccy="SGD")
    tx(plane, "oms", "T-0930", "harborview", -5000, 592000, date(2026, 9, 30))
    import sh_platform.v1.e3_calc as calc
    mp.setattr(calc, "fx", lambda plane, frm, to, on, cutoff: Decimal(1) / Decimal("1.3412") if (frm, to) == ("SGD", "USD") else None)
    return R.run_detail(plane, "trade_vs_admin", date(2026, 9, 30))


def test_september_three_breaks_with_types_and_amounts(plane, monkeypatch):
    d = sep(plane, monkeypatch)
    assert (d["records"]["trading export"], d["matched"], d["breaks"]) == (4, 1, 3)
    by = {r["type"]: r for r in d["results"] if r["breached"]}
    assert set(by) == {"quantity", "price", "missing"}
    amounts = {c["title"].split(" · ")[3]: (c["candidate_impact_amount"], c["impact_currency"]) for c in plane.cases.opened}
    assert amounts == {"T-0917": (Decimal("75870"), "USD"), "F02": (Decimal("8100"), "SGD"), "T-0930": (Decimal("592000"), "USD")}
    assert "1.3425" in by["price"]["words"] and "1.3452" in by["price"]["words"] and "6,039.37 USD" in by["price"]["words"]
    assert "1,800 in quantity" in by["quantity"]["words"]


def test_october_carries_harborview_and_does_not_raise_it_twice(plane, monkeypatch):
    sep(plane, monkeypatch)
    assert len(plane.cases.opened) == 3
    # the administrator amends Northwind and the forward on 6 Oct (the trade keeps its September date); Harborview stays missing
    tx(plane, "adm", "T-0917", "northwind", 12000, -505800, date(2026, 9, 17), eff=date(2026, 10, 6))
    tx(plane, "adm", "F02", "fxf2", 3_000_000, 4_027_500, date(2026, 9, 29), ccy="SGD", eff=date(2026, 10, 6))
    inst(plane, "bay")
    both(plane, "T-1001", "meridian", 20000, -662000, date(2026, 10, 1))           # the 1st: inside the calendar month, outside 30 days of 31 Oct
    both(plane, "T-1002", "bay", -10000, 482000, date(2026, 10, 2))
    both(plane, "T-1007", "bay", 1000000, -991000, date(2026, 10, 7))
    for _ in range(2):
        d = R.run_detail(plane, "trade_vs_admin", date(2026, 10, 31))
        assert (d["records"]["trading export"], d["matched"], d["breaks"], d["opened"], d["carried"]) == (3, 3, 0, [], 1)
    carried = next(r for r in d["results"] if r.get("carried"))
    assert "T-0930" in carried["subject"] and "592,000" in carried["words"] and carried["case_id"]
    assert len(plane.cases.opened) == 3


def test_a_cancelled_trade_is_not_compared_and_the_latest_version_counts(plane):
    trade_setup(plane)
    inst(plane, "meridian", "bay")
    first = W.record(plane, "transactions", {"source_record_id": U("recoms"), "portfolio_id": U("pb"), "instrument_id": U("meridian"), "external_trade_id": "T-1",
                                            "transaction_type": "buy", "trade_date": date(2026, 10, 5), "effective_date": date(2026, 10, 5), "quantity_delta": 100,
                                            "cash_amount": -1000, "currency": "USD", "status": "confirmed"})             # withdrawn from the re-sent file: nobody else has it
    W.record(plane, "transactions", {"source_record_id": U("recoms"), "portfolio_id": U("pb"), "instrument_id": U("meridian"), "external_trade_id": "T-1",
                                    "transaction_type": "buy", "trade_date": date(2026, 10, 5), "effective_date": date(2026, 10, 5), "quantity_delta": 100,
                                    "cash_amount": -1000, "currency": "USD", "status": "cancelled"}, supersedes_id=first)
    both(plane, "T-2", "bay", 10, -50, date(2026, 10, 6))
    d = R.run_detail(plane, "trade_vs_admin", date(2026, 10, 8))
    assert d["breaks"] == 0 and d["opened"] == [] and d["matched"] == 1
