"""K2 Office view: holdings with status words and sources, USD/SGD switch, issued vs known now, NAV bridge (parts add up to the
difference, each with evidence), liquidity fallback and contract, access filtering, and the routes. Synthetic data only.
E1d (who sees what) is patched; everything else is real."""
import sys
import types
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e1_access, e1_reports, k4_office as O, wh

UTC = timezone.utc
D = lambda *a: datetime(*a, tzinfo=UTC)  # noqa: E731
U = lambda n: str(uuid.uuid5(uuid.NAMESPACE_DNS, "k4-" + n))  # noqa: E731
ORG = U("org")
E1, E2, PF1, PF2, PF3 = U("e1"), U("e2"), U("pf1"), U("pf2"), U("pf3")
A, B, LQ, X, OLD = U("A"), U("B"), U("LQ"), U("X"), U("OLD")
ALLOWED: set[str] = set()


def ins(con, table, **row):
    row.setdefault("organization_id", ORG)
    con.execute(f"insert into {table} ({', '.join(row)}) values ({', '.join('?' * len(row))})", list(row.values()))


def val(con, id, inst, pf, amount, vdate, rec, ccy="USD", vtype="manager_final", status="approved", sup=None, doc=None, fld=None):
    ins(con, "valuation_observations", id=id, instrument_id=inst, portfolio_id=pf, valuation_date=vdate, received_at=rec, recorded_at=rec,
        value_amount=amount, currency=ccy, valuation_type=vtype, approval_status=status, supersedes_valuation_id=sup,
        evidence_document_id=doc, extracted_field_id=fld)


def nav(con, id, pf, amount, period_end, rec, ccy="USD"):
    ins(con, "nav_snapshots", id=id, portfolio_id=pf, source_record_id=U("src"), nav_period_end=period_end, received_at=rec, recorded_at=rec,
        nav_amount=amount, currency=ccy, nav_status="official")


def fx(con, id, usd_sgd, on):
    ins(con, "market_observations", id=id, source_record_id=U("src"), series_key="FX:USDSGD:ECB", observation_type="fx", observed_at=on,
        received_at=on, recorded_at=on, value=usd_sgd, base_currency="USD", quote_currency="SGD", quality_status="official")


def base(p, entities=(("e1", "Evergreen Holdings"), ("e2", "Second Entity"))):
    with wh.connect(p) as con:
        ins(con, "source_systems", id=U("sys"), source_code="admin", source_name="Administrator export", source_type="file", is_active=True)
        ins(con, "source_batches", id=U("batch"), source_system_id=U("sys"), batch_reference="b", received_at=D(2026, 1, 1), validation_status="loaded")
        ins(con, "source_records", id=U("src"), source_batch_id=U("batch"), record_type="row", received_at=D(2026, 1, 1), recorded_at=D(2026, 1, 1),
            raw_payload_uri="x", content_hash="h", quality_status="ok")
        for k, name in entities:
            ins(con, "legal_entities", id=U(k), entity_code=k, entity_name=name, base_currency="USD")
        for i, n in ((A, "Evergreen Growth I"), (B, "Evergreen Growth II"), (LQ, "Liquid book"), (X, "Harbour Fund"), (OLD, "Old fund")):
            ins(con, "instruments", id=i, canonical_name=n, instrument_type="fund", asset_class="private_fund", created_at=D(2026, 1, 1))


def portfolio(con, pid, entity, name):
    ins(con, "portfolios", id=pid, legal_entity_id=entity, portfolio_code=name[:4], portfolio_name=name, base_currency="USD")


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    rules = types.ModuleType("sh_platform.v1.e3_rules")
    rules.current = lambda plane, code, on: {"rule_version_id": "r1", "parameters": {"fixing": "ECB"}} if code == "fx_fixing" else None
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e3_rules", rules)
    monkeypatch.setattr(sys.modules["sh_platform.v1"], "e3_rules", rules, raising=False)
    ALLOWED.clear()
    monkeypatch.setattr(e1_access, "visible_portfolios", lambda pl, v: set(ALLOWED))
    p = PlaneStore(tmp_path / "data").create("acme")
    base(p)
    return p


def story(p):
    """PF1: the Evergreen revision story. Fund A estimated 10.00m then revised to 10.18m after the NAV was struck; NAV 57.60m."""
    ALLOWED.update({PF1})
    with wh.connect(p) as con:
        portfolio(con, PF1, E1, "Evergreen Growth")
        ins(con, "documents", id=U("d2"), source_system_id=U("sys"), access_group_id=U("g"), document_type="statement", title="Fund A amended statement",
            original_uri="u", content_hash="d2", valuation_date=date(2026, 9, 30), received_at=D(2026, 10, 9), recorded_at=D(2026, 10, 9),
            document_status="final", processing_status="done")
        ins(con, "extracted_fields", id=U("f2"), document_id=U("d2"), field_name="nav", page_number=2, line_number=14, confidence="high", review_status="confirmed")
        val(con, U("v1"), A, PF1, 10_000_000, date(2026, 9, 30), D(2026, 10, 2), vtype="manager_estimate")
        val(con, U("v2"), A, PF1, 10_180_000, date(2026, 9, 30), D(2026, 10, 9), sup=U("v1"), doc=U("d2"), fld=U("f2"))
        val(con, U("vb"), B, PF1, 6_400_000, date(2026, 9, 30), D(2026, 10, 2))
        ins(con, "position_snapshots", id=U("p1"), source_record_id=U("src"), portfolio_id=PF1, instrument_id=LQ, position_date=date(2026, 9, 30),
            as_of_at=D(2026, 9, 30), received_at=D(2026, 10, 1), recorded_at=D(2026, 10, 1), source_market_value=41_200_000, currency="USD",
            view_type="investment", data_status="official")
        nav(con, U("n1"), PF1, 57_600_000, date(2026, 9, 30), D(2026, 10, 3))


def test_cash_position_is_not_a_holding(plane):
    story(plane)
    with wh.connect(plane) as con:
        ins(con, "instruments", id=U("cash"), canonical_name="Cash", instrument_type="cash", asset_class="cash", created_at=D(2026, 1, 1))
        ins(con, "position_snapshots", id=U("pc"), source_record_id=U("src"), portfolio_id=PF1, instrument_id=U("cash"), position_date=date(2026, 10, 8),
            as_of_at=D(2026, 10, 8), received_at=D(2026, 10, 8), recorded_at=D(2026, 10, 8), source_market_value=5_000_000, currency="USD",
            view_type="investment", data_status="official")
    h = O.holdings(plane, None, "USD", "2026-10-09")
    assert h["total"] == Decimal(57_780_000)
    assert "Cash" not in {l["name"] for e in h["entities"] for p in e["portfolios"] for l in p["lines"]}
    (b,) = O.nav_bridge(plane, None, "USD", "2026-10-09")["portfolios"]
    assert b["investment_total"] == Decimal(57_780_000)


# ---- holdings ---------------------------------------------------------------------------------------------------------

def test_holdings_status_source_and_totals(plane):
    story(plane)
    h = O.holdings(plane, None, "USD", "2026-10-09")
    assert h["total"] == Decimal(57_780_000) and h["partial"] is False
    (ent,) = h["entities"]
    assert ent["entity_name"] == "Evergreen Holdings" and ent["total"] == Decimal(57_780_000)
    (pf,) = ent["portfolios"]
    by = {l["name"]: l for l in pf["lines"]}
    assert by["Evergreen Growth I"]["status"] == "revised" and by["Evergreen Growth I"]["value"] == Decimal(10_180_000)
    assert by["Evergreen Growth I"]["source"] == 'Manager valuation dated 30 Sep 2026, from the statement "Fund A amended statement", page 2, line 14'
    assert by["Evergreen Growth I"]["where"]["document_id"] == U("d2")
    assert by["Evergreen Growth II"]["status"] == "official"
    assert "Administrator export" in by["Liquid book"]["source"] and by["Liquid book"]["status"] == "official"


def test_old_value_reads_stale_and_unverified_stays(plane):
    ALLOWED.add(PF3)
    with wh.connect(plane) as con:
        portfolio(con, PF3, E2, "Legacy")
        val(con, U("vo"), OLD, PF3, 500_000, date(2026, 3, 31), D(2026, 4, 5))
        val(con, U("vu"), X, PF3, 120_000, date(2026, 9, 30), D(2026, 10, 5), status="proposed")
    pf = O.holdings(plane, None, "USD", "2026-10-09")["entities"][0]["portfolios"][0]
    st = {l["name"]: l["status"] for l in pf["lines"]}
    assert st == {"Old fund": "stale", "Harbour Fund": "unverified"}


def test_sgd_switch_uses_the_signed_fixing_and_says_when_missing(plane):
    story(plane)
    with wh.connect(plane) as con:
        fx(con, U("fx1"), "1.25", D(2026, 9, 30))
    h = O.holdings(plane, None, "SGD", "2026-10-09")
    assert h["total"] == Decimal(57_780_000) * Decimal("1.25") and h["currency"] == "SGD"
    line = h["entities"][0]["portfolios"][0]["lines"][0]
    assert line["currency"] == "SGD" and line["native"]["currency"] == "USD"
    h = O.holdings(plane, None, "EUR", "2026-10-09")  # no EUR rate
    msg = h["entities"][0]["portfolios"][0]["message"]
    assert h["total"] is None and ("cannot be converted" in msg or "No ECB rate" in msg)


def test_hidden_portfolio_is_left_out_and_totals_withheld(plane):
    story(plane)
    with wh.connect(plane) as con:
        portfolio(con, PF2, E2, "Second book")
        val(con, U("v9"), X, PF2, 1_000_000, date(2026, 9, 30), D(2026, 10, 2))
    h = O.holdings(plane, None, "USD", "2026-10-09")  # sees PF1 only
    assert h["partial"] is True and h["total"] is None
    assert [p["portfolio_name"] for e in h["entities"] for p in e["portfolios"]] == ["Evergreen Growth"]
    ALLOWED.clear()
    assert O.holdings(plane, None, "USD", "2026-10-09")["entities"] == []  # fail closed


# ---- issued vs known now ----------------------------------------------------------------------------------------------

def issue_report(p):
    e1_reports.ensure_report(p, "inv", "September investment report", "cio", ["USD"])
    by = str(uuid.uuid5(uuid.NAMESPACE_DNS, "k4-cio"))
    lines = [{"metric_code": "holding_value", "portfolio_id": PF1, "instrument_id": A, "value": 10_000_000, "currency": "USD", "status": "estimated",
              "sources": [{"table": "valuation_observations", "row_id": U("v1")}]},
             {"metric_code": "holding_value", "portfolio_id": PF1, "instrument_id": B, "value": 6_400_000, "currency": "USD", "status": "official",
              "sources": [{"table": "valuation_observations", "row_id": U("vb")}]}]
    return e1_reports.issue(p, "inv", date(2026, 9, 30), D(2026, 10, 3), by, lines, issued_at=D(2026, 10, 3))


def test_issued_beside_known_now_with_brief_link(plane):
    story(plane)
    rv = issue_report(plane)
    r = O.issued_vs_known(plane, None)
    assert r["report"]["report_version_id"] == rv and r["brief_link"] == f"/centre/consume/brief/{rv}"
    a = next(l for l in r["lines"] if l["instrument_id"] == A)
    assert (a["issued"], a["known_now"], a["difference"], a["status"]) == (Decimal(10_000_000), Decimal(10_180_000), Decimal(180_000), "revised")
    assert r["banner"] and "manager-reported valuation" in r["banner"]


def test_nothing_issued_says_so(plane):
    story(plane)
    r = O.issued_vs_known(plane, None)
    assert r["report"] is None and "No report has been issued" in r["message"]


# ---- NAV bridge -------------------------------------------------------------------------------------------------------

def parts(b):
    return {p["code"]: p for p in b["parts"]}


def test_bridge_revision_explains_the_whole_difference(plane):
    story(plane)
    b = O.nav_bridge(plane, None, "USD", "2026-09-30")["portfolios"][0]
    assert b["available"] and b["investment_total"] == Decimal(57_780_000) and b["administrator_nav"] == Decimal(57_600_000)
    assert b["difference"] == Decimal(180_000)
    p = parts(b)
    assert (p["revisions"]["amount"], p["timing"]["amount"], p["fx"]["amount"], p["unexplained"]["amount"]) == (Decimal(180_000), 0, 0, 0)
    ev = p["revisions"]["evidence"][0]
    assert ev["row_id"] == U("v2") and "page 2, line 14" in ev["text"] and "Evergreen Growth I" in ev["label"]
    assert p["unexplained"]["evidence"][0]["row_id"] == U("n1")


def test_bridge_timing_and_unexplained_add_up(plane):
    ALLOWED.add(PF2)
    with wh.connect(plane) as con:
        portfolio(con, PF2, E2, "Second book")
        val(con, U("x1"), X, PF2, 900_000, date(2026, 6, 30), D(2026, 7, 5))
        val(con, U("x2"), X, PF2, 950_000, date(2026, 9, 30), D(2026, 10, 1))
        nav(con, U("n2"), PF2, 1_000_000, date(2026, 6, 30), D(2026, 7, 10))
    b = O.nav_bridge(plane, None, "USD", "2026-09-30")["portfolios"][0]
    p = parts(b)
    assert b["difference"] == Decimal(-50_000)
    assert (p["timing"]["amount"], p["unexplained"]["amount"], p["revisions"]["amount"], p["fx"]["amount"]) == (Decimal(50_000), Decimal(-100_000), 0, 0)
    assert p["timing"]["evidence"][0]["row_id"] == U("x2")
    assert sum(x["amount"] for x in b["parts"]) == b["difference"]


def test_bridge_fx_part(plane):
    ALLOWED.add(PF2)
    with wh.connect(plane) as con:
        portfolio(con, PF2, E2, "Second book")
        val(con, U("x1"), X, PF2, 1_300_000, date(2026, 6, 30), D(2026, 7, 5), ccy="SGD")
        nav(con, U("n2"), PF2, 1_000_000, date(2026, 6, 30), D(2026, 7, 10))
        fx(con, U("fa"), "1.30", D(2026, 6, 30))
        fx(con, U("fb"), "1.25", D(2026, 9, 30))
    b = O.nav_bridge(plane, None, "USD", "2026-09-30")["portfolios"][0]
    p = parts(b)
    assert b["difference"] == Decimal(40_000) and p["fx"]["amount"] == Decimal(40_000) and p["timing"]["amount"] == 0 and p["unexplained"]["amount"] == 0
    assert "ECB" in p["fx"]["evidence"][0]["text"]
    assert sum(x["amount"] for x in b["parts"]) == b["difference"]


def test_bridge_without_nav_or_rate_says_why(plane):
    ALLOWED.add(PF2)
    with wh.connect(plane) as con:
        portfolio(con, PF2, E2, "Second book")
        val(con, U("x1"), X, PF2, 900_000, date(2026, 6, 30), D(2026, 7, 5))
    assert "No administrator NAV" in O.nav_bridge(plane, None, "USD", "2026-09-30")["portfolios"][0]["message"]
    with wh.connect(plane) as con:
        nav(con, U("n2"), PF2, 1_000_000, date(2026, 6, 30), D(2026, 7, 10), ccy="EUR")
    b = O.nav_bridge(plane, None, "USD", "2026-09-30")["portfolios"][0]
    assert b["available"] is False and "EUR" in b["message"]


def test_bridge_respects_access(plane):
    story(plane)
    ALLOWED.clear()
    assert O.nav_bridge(plane, None, "USD", "2026-09-30")["portfolios"] == []


# ---- liquidity --------------------------------------------------------------------------------------------------------

def test_liquidity_says_so_until_commitments_exist(plane, monkeypatch):
    monkeypatch.setitem(sys.modules, "sh_platform.v1.k6_liquidity", None)  # an import of it now fails
    monkeypatch.delattr(sys.modules["sh_platform.v1"], "k6_liquidity", raising=False)  # the package attribute would otherwise win
    r = O.liquidity(plane, None, "USD", "2026-10-09")
    assert r["available"] is False and "not loaded" in r["message"]


def test_liquidity_passes_the_forecast_through(plane, monkeypatch):
    mod = types.ModuleType("sh_platform.v1.k6_liquidity")
    seen = {}
    mod.forecast = lambda pl, as_of, cutoff=None, viewer=None, currency=None: seen.update(as_of=as_of, currency=currency) or {
        "as_of": as_of.isoformat(), "entities": [{"entity_name": "Evergreen Holdings", "available_cash": Decimal(5), "buckets": []}]}
    monkeypatch.setitem(sys.modules, "sh_platform.v1.k6_liquidity", mod)
    monkeypatch.setattr(sys.modules["sh_platform.v1"], "k6_liquidity", mod, raising=False)
    r = O.liquidity(plane, None, "SGD", "2026-10-09")
    assert r["available"] and r["currency"] == "SGD" and r["entities"][0]["available_cash"] == 5
    assert seen == {"as_of": date(2026, 10, 9), "currency": "SGD"}


# ---- routes -----------------------------------------------------------------------------------------------------------

def test_routes_serve_json_with_strings_for_money(plane, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from sh_platform.v1 import k4_routes as R
    story(plane)
    monkeypatch.setattr(R, "viewer_of", lambda request: None)
    monkeypatch.setattr(R, "_plane", lambda request: plane)
    app = FastAPI()
    app.include_router(R.router)
    c = TestClient(app)
    h = c.get("/api/v1/office/holdings", params={"currency": "USD", "as_of": "2026-10-09"}).json()
    assert h["total"] == "57780000.00000000" or Decimal(h["total"]) == Decimal(57_780_000)
    assert c.get("/api/v1/office/nav-bridge", params={"as_of": "2026-09-30"}).json()["portfolios"][0]["parts"][0]["code"] == "revisions"
    assert c.get("/api/v1/office/liquidity").json()["currency"] == "USD"
    assert c.get("/api/v1/office/holdings", params={"as_of": "not a date"}).status_code == 400


def test_liquidity_with_the_real_forecast(plane):
    """K4's k6_liquidity against a cash balance and one call: after-call cash and the unconfirmed flag reach the Office view."""
    from sh_platform.v1 import k6_liquidity as L
    story(plane)
    CASH, FUND = U("cash"), U("fund")
    with wh.connect(plane) as con:
        ins(con, "instruments", id=CASH, canonical_name="Operating cash", instrument_type="cash", created_at=D(2026, 1, 1))
        ins(con, "instruments", id=FUND, canonical_name="Harbour Private Equity", instrument_type="fund", created_at=D(2026, 1, 1))
        ins(con, "position_snapshots", id=U("pc"), source_record_id=U("src"), portfolio_id=PF1, instrument_id=CASH, position_date=date(2026, 10, 8),
            as_of_at=D(2026, 10, 8), received_at=D(2026, 10, 9), recorded_at=D(2026, 10, 9), source_market_value=2_000_000, currency="USD",
            view_type="accounting", data_status="official")
    cid = L.record_commitment(plane, {"legal_entity_id": E1, "instrument_id": FUND, "commitment_amount": 5_000_000, "currency": "USD", "committed_on": date(2025, 1, 1)})
    with wh.connect(plane) as con:
        ins(con, "cash_movements", id=U("call1"), source_record_id=U("src"), portfolio_id=PF1, instrument_id=FUND, movement_type="call",
            effective_date=date(2026, 10, 20), received_at=D(2026, 10, 5), recorded_at=D(2026, 10, 5), amount=750_000, currency="USD",
            confirmation_status="noticed", due_date=date(2026, 10, 20), notice_kind="call", commitment_id=cid)
    ALLOWED.add(E1)
    monkey = e1_access.visible_entities
    e1_access.visible_entities = lambda pl, v: {E1}
    try:
        r = O.liquidity(plane, object(), "USD", "2026-10-09")
    finally:
        e1_access.visible_entities = monkey
    assert r["available"] is True
    ent = next(e for e in r["entities"] if e["entity_id"] == E1)
    assert ent["available_cash"] == Decimal(2_000_000)
    b30 = next(b for b in ent["buckets"] if b["key"] == "30")
    assert (b30["calls"], b30["cash_after_calls"]) == (Decimal(750_000), Decimal(1_250_000))
    assert [i["fund"] for i in ent["unconfirmed"]] == ["Harbour Private Equity"] and ent["uncalled"] == Decimal(5_000_000)


def test_instrument_without_asset_class_needs_a_class(plane):
    PRC = U("prc")
    ALLOWED.add(PF3)
    with wh.connect(plane) as con:
        portfolio(con, PF3, E2, "Liquid")
        ins(con, "instruments", id=PRC, canonical_name="Pacific Rim Convertible 2029 note", instrument_type="bond", created_at=D(2026, 1, 1))
        ins(con, "position_snapshots", id=U("pp"), source_record_id=U("src"), portfolio_id=PF3, instrument_id=PRC, position_date=date(2026, 9, 30),
            as_of_at=D(2026, 9, 30), received_at=D(2026, 10, 1), recorded_at=D(2026, 10, 1), source_market_value=1_122_000, currency="USD",
            view_type="investment", data_status="official")
    (l,) = O.holdings(plane, None, "USD", "2026-10-09")["entities"][0]["portfolios"][0]["lines"]
    assert (l["status"], l["asset_class"], l["data_status"], l["value"]) == ("Needs a class", None, "official", Decimal(1_122_000))


def liquid_book(plane):
    ALLOWED.add(PF3)
    with wh.connect(plane) as con:
        portfolio(con, PF3, E2, "EG-LIQUID")
        for n, (inst, v0, v1) in enumerate(((A, 20_000_000, 21_000_000), (B, 19_552_000, 20_200_000))):
            for on, v in ((date(2026, 8, 31), v0), (date(2026, 9, 30), v1)):
                ins(con, "position_snapshots", id=U(f"lp{n}{on}"), source_record_id=U("src"), portfolio_id=PF3, instrument_id=inst, position_date=on,
                    as_of_at=D(on.year, on.month, on.day), received_at=D(on.year, on.month, on.day), recorded_at=D(on.year, on.month, on.day),
                    source_market_value=v, currency="USD", view_type="investment", data_status="official")
        ins(con, "instruments", id=U("fxf"), canonical_name="FX forward FXF-2026-001", instrument_type="fx_forward", created_at=D(2026, 1, 1))
        ins(con, "transactions", id=U("t1"), source_record_id=U("src"), portfolio_id=PF3, instrument_id=U("fxf"), external_trade_id="FXF-2026-001",
            transaction_type="fx_forward", trade_date=date(2026, 9, 15), effective_date=date(2026, 12, 15), cash_amount=2_000_000, currency="USD",
            recorded_at=D(2026, 9, 15), status="booked")


def test_why_moved_liquid_book_lists_the_fx_forward(plane):
    liquid_book(plane)
    r = O.why_moved(plane, None, "2026-08-31", "2026-09-30", "USD", book="liquid")
    assert (r["start_value"], r["end_value"], r["change"], r["percent"]) == (Decimal(39_552_000), Decimal(41_200_000), Decimal(1_648_000), Decimal("4.1667"))
    parts = {p["code"]: p for p in r["parts"]}
    assert sum(p["amount"] for p in r["parts"]) == r["change"]
    assert [l["label"] for l in parts["price"]["lines"]] == ["Evergreen Growth I", "Evergreen Growth II"] and r["largest"] == "Evergreen Growth I"
    assert parts["price"]["lines"][0]["evidence"][0]["text"] and parts["price"]["lines"][0]["amount"] == Decimal(1_000_000)
    (t,) = parts["trades"]["lines"]
    assert "FXF-2026-001" in t["evidence"][0]["text"] and t["amount"] == 0 and "no trades" not in r["message"].lower()


def test_why_moved_revision_and_access(plane):
    story(plane)
    with wh.connect(plane) as con:
        val(con, U("vb0"), B, PF1, 6_000_000, date(2026, 9, 30), D(2026, 9, 30))  # B was known at 6.0m on 30 Sep, then 6.4m arrived
    r = O.why_moved(plane, None, "2026-08-31", "2026-09-30", "USD")
    parts = {p["code"]: p for p in r["parts"]}
    # B: 6.0m first recorded for 30 Sep, then 6.4m for the same date; A: the 10.0m estimate replaced by the 10.18m amended statement
    assert parts["revisions"]["amount"] == Decimal(580_000) and sum(p["amount"] for p in r["parts"]) == r["change"] and r["percent"] is None
    assert O.why_moved(plane, None, "2026-08-31", "2026-09-30", "USD", portfolio_id=PF2)["available"] is False
    with pytest.raises(ValueError):
        O.why_moved(plane, None, "2026-09-30", "2026-08-31")


def test_why_moved_route(plane, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from sh_platform.v1 import k4_routes as R
    liquid_book(plane)
    monkeypatch.setattr(R, "viewer_of", lambda request: None)
    monkeypatch.setattr(R, "_plane", lambda request: plane)
    app = FastAPI()
    app.include_router(R.router)
    c = TestClient(app)
    j = c.get("/api/v1/office/why-moved", params={"start": "2026-08-31", "end": "2026-09-30", "book": "liquid"}).json()
    assert Decimal(j["change"]) == Decimal(1_648_000) and j["percent"] == "4.1667"
    assert c.get("/api/v1/office/why-moved", params={"start": "x", "end": "2026-09-30"}).status_code == 400


# ---- cycle 1 fixes (a1.0, a1.1, a1.8, a4.9, a4.10) -----------------------------------------------------------------------

def test_month_end_value_recorded_days_later_is_a_price_move_not_a_revision(plane):
    """a1.0/a4.10: month-end valuations arrive two days after the date; with one row per date there is no revision."""
    ALLOWED.add(PF3)
    with wh.connect(plane) as con:
        portfolio(con, PF3, E2, "EG-LIQUID")
        for inst, v0, v1 in ((A, 20_000_000, 21_000_000), (B, 19_552_000, 20_200_000)):
            for on, v in ((date(2026, 8, 31), v0), (date(2026, 9, 30), v1)):
                val(con, U(f"m{inst}{on}"), inst, PF3, v, on, D(on.year, on.month, on.day) + timedelta(days=2))
    r = O.why_moved(plane, None, "2026-08-31", "2026-09-30", "USD", book="liquid")
    parts = {p["code"]: p for p in r["parts"]}
    assert parts["revisions"]["amount"] == 0 and not parts["revisions"]["lines"]
    assert [(l["label"], l["amount"]) for l in parts["price"]["lines"]] == [("Evergreen Growth I", Decimal(1_000_000)), ("Evergreen Growth II", Decimal(648_000))]
    assert r["largest"] == "Evergreen Growth I" and sum(p["amount"] for p in r["parts"]) == r["change"] == Decimal(1_648_000)


def test_a_trade_loaded_from_two_sources_is_listed_once(plane):
    """a1.1: the trading export and the administrator both send FXF-2026-001; it is one trade."""
    liquid_book(plane)
    with wh.connect(plane) as con:
        ins(con, "transactions", id=U("t2"), source_record_id=U("src"), portfolio_id=PF3, instrument_id=U("fxf"), external_trade_id="FXF-2026-001",
            transaction_type="fx_forward", trade_date=date(2026, 9, 15), effective_date=date(2026, 12, 15), cash_amount=2_000_000, currency="USD",
            recorded_at=D(2026, 9, 16), status="booked")
    r = O.why_moved(plane, None, "2026-08-31", "2026-09-30", "USD", book="liquid")
    (t,) = {p["code"]: p for p in r["parts"]}["trades"]["lines"]
    assert "FXF-2026-001" in t["evidence"][0]["text"] and r["message"] == "1 trade(s) in the period are listed."


def test_the_liquid_book_container_line_at_zero_is_not_a_holding(plane):
    """a1.8: the roll-up instrument the issued report needs is not listed beside its securities at zero."""
    liquid_book(plane)
    with wh.connect(plane) as con:
        ins(con, "instruments", id=U("liq"), canonical_name="Evergreen Liquid Book", instrument_type="liquid_book", asset_class="listed", created_at=D(2026, 1, 1))
        for on in (date(2026, 8, 31), date(2026, 9, 30)):
            val(con, U(f"liq{on}"), U("liq"), PF3, 0, on, D(on.year, on.month, on.day))
    names = [l["name"] for e in O.holdings(plane, None, "USD", "2026-09-30")["entities"] for p in e["portfolios"] for l in p["lines"]]
    assert sorted(names) == ["Evergreen Growth I", "Evergreen Growth II"]
    r = O.why_moved(plane, None, "2026-08-31", "2026-09-30", "USD", book="liquid")
    assert all(l["label"] != "Evergreen Liquid Book" for p in r["parts"] for l in p["lines"])


def test_issued_where_names_the_rate_when_shown_in_another_currency(plane):
    """a4.9: in SGD the trail says which rate converted the report."""
    story(plane)
    with wh.connect(plane) as con:
        fx(con, U("fx1"), "1.3412", D(2026, 9, 30))
    e1_reports.ensure_report(plane, "inv", "September investment report", "cio", ["USD", "SGD"])
    issue_report(plane)
    r = O.issued_vs_known(plane, None, "SGD")
    assert r["currency"] == "SGD" and "Converted from USD to SGD at 1.3412 (ECB fixing observed 30 Sep 2026)" in r["where"]["text"]
    assert "Converted" not in O.issued_vs_known(plane, None, "USD")["where"]["text"]
