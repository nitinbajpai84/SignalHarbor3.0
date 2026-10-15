"""E3d: Evergreen totals (57.60m then 57.78m as known at two cutoffs), SGD conversion, missing FX returns None with a reason, version stable."""
import sys
import types
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e3_calc as C, wh

D = lambda *a: datetime(*a, tzinfo=timezone.utc)
RULE = {"fixing": "ECB"}
U = lambda n: f"00000000-0000-0000-0000-{n:012d}"
ORG, PF, A, B, LQ = U(1), U(2), U(3), U(4), U(5)
A1, B1, A2, P1, M1, S = U(11), U(12), U(13), U(14), U(15), U(16)


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    wh.reset_cache()
    rules = types.ModuleType("sh_platform.v1.e3_rules")
    rules.current = lambda plane, code, on: {"rule_version_id": "r1", "parameters": RULE} if code == "fx_fixing" and RULE else None
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e3_rules", rules)
    monkeypatch.setattr(sys.modules["sh_platform.v1"], "e3_rules", rules, raising=False)
    p = PlaneStore(tmp_path / "data").create("acme")
    with wh.connect(p) as con:
        def val(id, inst, amount, vtype, rec, sup=None, approval="approved"):
            con.execute("insert into valuation_observations (id, organization_id, instrument_id, portfolio_id, valuation_date, received_at, recorded_at,"
                        " value_amount, currency, valuation_type, approval_status, supersedes_valuation_id) values (?,?,?,?,?,?,?,?,?,?,?,?)",
                        [id, ORG, inst, PF, date(2026, 9, 30), rec, rec, amount, "USD", vtype, approval, sup])
        val(A1, A, 10_000_000, "manager_estimate", D(2026, 10, 2))
        val(B1, B, 6_400_000, "manager_final", D(2026, 10, 2))
        val(A2, A, 10_180_000, "manager_final", D(2026, 10, 9), sup=A1)
        con.execute("insert into position_snapshots (id, organization_id, source_record_id, portfolio_id, instrument_id, position_date, as_of_at,"
                    " received_at, recorded_at, source_market_value, currency, view_type, data_status) values"
                    " (?,?,?,?,?,?,?,?,?,41200000,'USD','investment','official')",
                    [P1, ORG, S, PF, LQ, date(2026, 9, 30), D(2026, 9, 30), D(2026, 10, 1), D(2026, 10, 1)])
        con.execute("insert into market_observations (id, organization_id, source_record_id, series_key, observation_type, observed_at, received_at,"
                    " recorded_at, value, base_currency, quote_currency, quality_status) values"
                    " (?,?,?,'FX.ECB.USDSGD','fx',?,?,?,1.25,'USD','SGD','official')", [M1, ORG, S, D(2026, 9, 30), D(2026, 9, 30), D(2026, 9, 30)])
    return p


def test_totals_as_known_then_and_now(plane):
    then = C.portfolio_value(plane, PF, date(2026, 9, 30), date(2026, 10, 3), "USD")
    now = C.portfolio_value(plane, PF, date(2026, 9, 30), None, "USD")
    assert then["total"] == Decimal("57600000") and now["total"] == Decimal("57780000")
    st = {l["instrument_id"]: l["status"] for l in then["lines"]}
    assert st == {A: "estimated", B: "official", LQ: "official"}
    assert {l["instrument_id"]: l["status"] for l in now["lines"]}[A] == "revised"
    assert {l["instrument_id"]: l["source_row_id"] for l in now["lines"]}[A] == A2


def test_sgd_and_missing_fx(plane):
    assert C.fx(plane, "USD", "SGD", date(2026, 9, 30)) == Decimal("1.25")
    assert C.fx(plane, "SGD", "USD", date(2026, 9, 30)) == Decimal("0.8")
    assert C.portfolio_value(plane, PF, date(2026, 9, 30), None, "SGD")["total"] == Decimal("57780000") * Decimal("1.25")
    assert C.fx(plane, "USD", "SGD", date(2026, 9, 29)) is None  # nothing observed yet
    assert C.fx(plane, "USD", "EUR", date(2026, 9, 30)) is None
    rate, why = C.fx_explained(plane, "USD", "EUR", date(2026, 9, 30))
    assert rate is None and "EUR" in why
    out = C.portfolio_value(plane, PF, date(2026, 9, 30), None, "EUR")
    assert out["total"] is None and out["problems"]


def test_no_signed_rule_returns_none_with_reason(plane):
    RULE.clear()
    try:
        rate, why = C.fx_explained(plane, "USD", "SGD", date(2026, 9, 30))
    finally:
        RULE.update({"fixing": "ECB"})
    assert rate is None and "fx_fixing" in why


def test_version_is_stable():
    import importlib
    assert C.CALC_VERSION == importlib.reload(C).CALC_VERSION and len(C.CALC_VERSION) == 12
