"""K5: blended benchmark return (weights, spread, FX, effective dates, cutoff), portfolio return with flows, the certified gate for a benchmark
still in progress (refused once, one policy question), and Span's benchmark gold table."""
import sys
import types
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import b6_span as S
from sh_platform.v1 import e3_calc as C
from sh_platform.v1 import k7_benchmark as K
from sh_platform.v1 import wh
from sh_platform.v1.i2_north import Refused

D = lambda *a: datetime(*a, tzinfo=timezone.utc)
U = lambda n: f"00000000-0000-0000-0000-{n:012d}"
ORG, PF, A, SRC = U(1), U(2), U(3), U(4)
AUG, SEP, JUL = date(2026, 8, 31), date(2026, 9, 30), date(2026, 7, 31)
_n = [100]


def nid() -> str:
    _n[0] += 1
    return U(_n[0])


def near(a, b, tol="0.0000001"):
    return abs(Decimal(a) - Decimal(b)) <= Decimal(tol)


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    rules = types.ModuleType("sh_platform.v1.e3_rules")
    rules.current = lambda plane, code, on: {"rule_version_id": "r1", "parameters": {"fixing": "ECB"}} if code == "fx_fixing" else None
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e3_rules", rules)
    monkeypatch.setattr(sys.modules["sh_platform.v1"], "e3_rules", rules, raising=False)
    p = PlaneStore(tmp_path / "data").create("acme")
    with wh.connect(p) as con:
        def level(key, on, v, ccy="USD", rec=None, sup=None):
            rec = rec or D(on.year, on.month, on.day)
            i = nid()
            con.execute("insert into market_observations (id, organization_id, source_record_id, series_key, observation_type, observed_at, received_at,"
                        " recorded_at, value, base_currency, quality_status, supersedes_observation_id) values (?,?,?,?,'index_level',?,?,?,?,?,'official',?)",
                        [i, ORG, SRC, key, D(on.year, on.month, on.day), rec, rec, v, ccy, sup])
            return i

        def fxo(on, v):
            con.execute("insert into market_observations (id, organization_id, source_record_id, series_key, observation_type, observed_at, received_at,"
                        " recorded_at, value, base_currency, quote_currency, quality_status) values (?,?,?,'FX.ECB.USDSGD','fx',?,?,?,?,'USD','SGD','official')",
                        [nid(), ORG, SRC, D(on.year, on.month, on.day), D(on.year, on.month, on.day), D(on.year, on.month, on.day), v])

        def bench(code, status, comps, ccy="USD"):
            i = nid()
            con.execute("insert into benchmark_definitions (id, organization_id, benchmark_code, benchmark_name, version_number, reporting_currency,"
                        " effective_from, calculation_method, approval_status) values (?,?,?,?,1,?,?, 'blend', ?)",
                        [i, ORG, code, f"Benchmark {code}", ccy, date(2026, 1, 1), status])
            for key, w, bps, frm, to in comps:
                con.execute("insert into benchmark_components (id, organization_id, benchmark_definition_id, market_series_key, component_weight, spread_bps,"
                            " weight_effective_from, weight_effective_to) values (?,?,?,?,?,?,?,?)", [nid(), ORG, i, key, w, bps, frm, to])

        for key, a, b, c in (("IDX.EQ", 90, 100, 105), ("IDX.BOND", 198, 200, 202)):
            level(key, JUL, a); level(key, AUG, b); level(key, SEP, c)
        level("IDX.PE", AUG, 100); level("IDX.PE", SEP, 102)
        level("IDX.SGDBOND", AUG, 200, "SGD"); level("IDX.SGDBOND", SEP, 202, "SGD")
        fxo(AUG, 1.25); fxo(SEP, 1.30)
        new, start = date(2026, 8, 31), date(2026, 1, 1)
        bench("BLEND", "approved", [("IDX.EQ", "0.5", None, start, date(2026, 8, 30)), ("IDX.BOND", "0.5", None, start, date(2026, 8, 30)),
                                    ("IDX.EQ", "0.6", None, new, None), ("IDX.BOND", "0.4", None, new, None)])
        bench("PRIVATE", "in_progress", [("IDX.PE", "1", "300", start, None)])
        bench("SPREAD", "approved", [("IDX.PE", "1", "300", start, None)])
        bench("SGDMIX", "approved", [("IDX.EQ", "0.5", None, start, None), ("IDX.SGDBOND", "0.5", None, start, None)])
        bench("BROKEN", "approved", [("IDX.EQ", "0.5", None, start, None)])
        bench("NOLEVEL", "approved", [("IDX.NONE", "1", None, start, None)])

        def val(on, amount, vtype="manager_final"):
            con.execute("insert into valuation_observations (id, organization_id, instrument_id, portfolio_id, valuation_date, received_at, recorded_at,"
                        " value_amount, currency, valuation_type, approval_status) values (?,?,?,?,?,?,?,?, 'USD', ?, 'approved')",
                        [nid(), ORG, A, PF, on, D(on.year, on.month, on.day), D(on.year, on.month, on.day), amount, vtype])
        val(AUG, 1_000_000); val(SEP, 1_150_000)

        def move(kind, on, amount, status="confirmed"):
            con.execute("insert into cash_movements (id, organization_id, source_record_id, portfolio_id, movement_type, effective_date, received_at,"
                        " recorded_at, amount, currency, confirmation_status) values (?,?,?,?,?,?,?,?,?, 'USD', ?)",
                        [nid(), ORG, SRC, PF, kind, on, D(on.year, on.month, on.day), D(on.year, on.month, on.day), amount, status])
        move("call", date(2026, 9, 15), 100_000)
        move("distribution", date(2026, 9, 20), 999_999, "expected")  # not confirmed: ignored
        move("dividend", date(2026, 9, 20), 5_000)                   # stays inside the portfolio: ignored
    return p


def test_blend_with_effective_dated_weights(plane):
    r = C.benchmark_return(plane, "BLEND", AUG, SEP)
    assert r["problems"] == [] and r["definition"]["approval_status"] == "approved"
    assert near(r["value"], "0.034")                                     # 0.6 * 5% + 0.4 * 1%
    assert {c["series_key"]: c["weight"] for c in r["components"]} == {"IDX.EQ": Decimal("0.6"), "IDX.BOND": Decimal("0.4")}
    old = C.benchmark_return(plane, "BLEND", JUL, AUG)                   # the earlier weights were in force at the start
    assert near(old["value"], Decimal("0.5") * Decimal(10) / 90 + Decimal("0.5") * Decimal(2) / 198)


def test_spread_is_a_twelfth_a_month_between_month_ends(plane):
    r = C.benchmark_return(plane, "SPREAD", AUG, SEP)                    # 300 bps a year = 25 bps a month, as the signed definition says
    assert near(r["value"], Decimal("0.02") + Decimal("0.03") / 12)
    assert near(r["components"][0]["spread_return"], Decimal("0.03") / 12)


def test_index_in_another_currency_is_converted_by_the_signed_fixing(plane):
    r = C.benchmark_return(plane, "SGDMIX", AUG, SEP, currency="USD")
    sgd = (Decimal(202) / Decimal("1.30")) / (Decimal(200) / Decimal("1.25")) - 1
    assert near(r["value"], Decimal("0.5") * Decimal("0.05") + Decimal("0.5") * sgd)
    assert r["value"] < Decimal("0.025")                                 # the weaker Singapore dollar cost return


def test_known_by_cutoff_and_corrections(plane):
    with wh.connect(plane) as con:
        old = con.execute("select id from market_observations where series_key = 'IDX.EQ' and observed_at = ?", [D(2026, 9, 30)]).fetchone()[0]
        con.execute("insert into market_observations (id, organization_id, source_record_id, series_key, observation_type, observed_at, received_at, recorded_at,"
                    " value, base_currency, quality_status, supersedes_observation_id) values (?,?,?, 'IDX.EQ','index_level',?,?,?,?, 'USD','official',?)",
                    [nid(), ORG, SRC, D(2026, 9, 30), D(2026, 10, 5), D(2026, 10, 5), 110, old])
    then = C.benchmark_return(plane, "BLEND", AUG, SEP, cutoff=date(2026, 10, 3))
    now = C.benchmark_return(plane, "BLEND", AUG, SEP)
    assert near(then["value"], "0.034") and near(now["value"], Decimal("0.6") * Decimal("0.10") + Decimal("0.4") * Decimal("0.01"))


def test_missing_data_gives_no_value_and_a_reason(plane):
    for code, word in (("BROKEN", "add up"), ("NOLEVEL", "IDX.NONE"), ("MISSING", "No benchmark")):
        r = C.benchmark_return(plane, code, AUG, SEP)
        assert r["value"] is None and word in r["problems"][0]
    stale = C.benchmark_return(plane, "BLEND", date(2026, 12, 31), date(2027, 1, 31))
    assert stale["value"] is None
    late = C.benchmark_return(plane, "SPREAD", AUG, date(2026, 10, 20), cutoff=date(2026, 10, 21))   # the September level is 20 days old by then
    assert late["value"] is None and "too old" in late["problems"][0]


def test_portfolio_return_weights_the_call_by_days_held(plane):
    r = C.portfolio_return(plane, PF, AUG, SEP)
    assert r["problems"] == [] and r["flows"] == Decimal(100_000) and r["opening"] == Decimal(1_000_000)
    assert near(r["value"], Decimal(50_000) / Decimal(1_050_000))        # (1.15m - 1m - 0.1m) / (1m + 0.1m * 15/30)
    assert r["statuses"] == ["official"]


def test_portfolio_return_without_flows_and_without_opening_value(plane):
    flat = C.portfolio_return(plane, PF, date(2026, 8, 31), date(2026, 9, 14))
    assert flat["problems"] == [] and flat["value"] == Decimal(0)         # no new value and no flow before 15 Sep: nothing happened
    none = C.portfolio_return(plane, PF, date(2026, 7, 31), AUG)
    assert none["value"] is None and none["problems"]                    # nothing known at the start
    assert C.portfolio_return(plane, PF, SEP, AUG)["value"] is None


def test_in_progress_benchmark_is_refused_once_and_raised_as_a_policy_question(plane):
    for _ in range(2):
        with pytest.raises(Refused) as e:
            K.certified_return(plane, "PRIVATE", AUG, SEP)
        assert e.value.status == 409 and "cannot be used in a certified report" in e.value.message
    with wh.connect(plane) as con:
        rows = con.execute("select exception_type, title from exceptions").fetchall()
    assert rows == [("policy_question", "Agree the definition of benchmark PRIVATE")]
    assert near(K.certified_return(plane, "SPREAD", AUG, SEP)["value"], Decimal("0.02") + Decimal("0.03") / 12)
    with pytest.raises(Refused) as e:
        K.certified_return(plane, "MISSING", AUG, SEP)
    assert e.value.status == 404


def test_comparison_is_certified_only_with_an_approved_benchmark_and_settled_values(plane):
    c = K.comparison(plane, PF, "BLEND", AUG, SEP)
    assert near(c["difference"], Decimal(50_000) / Decimal(1_050_000) - Decimal("0.034")) and c["certified"] is True
    assert K.comparison(plane, PF, "PRIVATE", AUG, SEP)["certified"] is False
    assert K.comparison(plane, PF, "NOLEVEL", AUG, SEP)["difference"] is None
    with wh.connect(plane) as con:
        con.execute("update valuation_observations set valuation_type = 'manager_estimate' where valuation_date = ?", [SEP])
    est = K.comparison(plane, PF, "BLEND", AUG, SEP)
    assert est["certified"] is False and est["portfolio"]["statuses"] == ["estimated"]


def test_span_adds_the_benchmark_table_only_for_a_benchmark_kpi(plane):
    assert S.benchmark_table("evergreen", [{"name": "Net worth by month"}]) == []
    tabs = S.benchmark_table("evergreen", [{"name": "Net worth by month"}, {"name": "Portfolio vs benchmark", "definition": "difference to the blend"}])
    assert [t["name"] for t in tabs] == ["gold_evergreen_benchmark_monthly", "gold_evergreen_benchmark_weights"]   # V6B: the returns, and the weight of each leg
    done = B.validate(plane, {"tables": tabs, "schedule": {}})      # parsed and every column checked against the data model
    cols = [c["name"] for c in done["tables"][0]["columns"]]
    assert cols == ["portfolio_code", "benchmark_code", "month", "portfolio_return", "benchmark_return", "difference"]   # by portfolio, so one portfolio's return is never added to another's
    assert [c["type"] for c in done["tables"][0]["columns"]][2:] == ["date", "decimal(9,6)", "decimal(9,6)", "decimal(9,6)"]   # typed, not all varchar
    assert [c["name"] for c in done["tables"][1]["columns"]] == ["benchmark_code", "month", "component", "component_weight"]
    assert S.benchmark_table("x" * 60, [{"name": "benchmark"}]) == []   # name too long for a table


def test_benchmark_table_values_match_the_calculation(plane):
    sql = S.benchmark_table("evergreen", [{"name": "benchmark"}])[0]["sql"].split(" as ", 1)[1]
    with wh.connect(plane) as con:
        con.execute("insert into valuation_observations (id, organization_id, instrument_id, portfolio_id, valuation_date, received_at, recorded_at, value_amount,"
                    " currency, valuation_type, approval_status) values (?,?,?,?,?,?,?,?, 'USD', 'manager_estimate', 'approved')",
                    [nid(), ORG, A, PF, SEP, D(2026, 9, 30), D(2026, 9, 30), 5_000_000])   # an estimate: must not count
        rows = con.execute(sql).fetchall()
    cols = ["portfolio", "code", "month", "pr", "br", "diff"]
    got = {(r[1], r[2].month): dict(zip(cols, r)) for r in rows}
    assert "PRIVATE" not in {k[0] for k in got}                       # the in-progress definition never appears
    sep = got[("BLEND", 9)]
    assert near(sep["br"], C.benchmark_return(plane, "BLEND", AUG, SEP)["value"]) and near(sep["br"], "0.034")   # new weights only, no double counting
    assert near(sep["pr"], Decimal("0.15"))                          # 1.15m / 1.0m, the estimate left out
    assert near(got[("BLEND", 8)]["br"], Decimal("0.5") * Decimal(100) / 90 - Decimal("0.5") + Decimal("0.5") * Decimal(2) / 198)  # old 50/50 window in August


def test_comparison_uses_the_reporting_currency_and_reports_valuation_dates(plane):
    c = K.comparison(plane, PF, "SGDMIX", AUG, SEP)                   # SGDMIX reports in USD: same as asking for USD
    assert c["benchmark"]["value"] == C.benchmark_return(plane, "SGDMIX", AUG, SEP, currency="USD")["value"]
    assert c["portfolio"]["valuation_dates"] == [SEP]


OCT31 = date(2026, 10, 31)


def _v2_from_october(plane):
    with wh.connect(plane) as con:
        did = nid()
        con.execute("insert into benchmark_definitions (id, organization_id, benchmark_code, benchmark_name, version_number, reporting_currency,"
                    " effective_from, calculation_method, approval_status) values (?,?,'BLEND','Benchmark BLEND',2,'USD',?, 'blend', 'in_progress')",
                    [did, ORG, date(2026, 10, 1)])
        for key, w in (("IDX.EQ", "0.7"), ("IDX.BOND", "0.3")):
            con.execute("insert into benchmark_components (id, organization_id, benchmark_definition_id, market_series_key, component_weight,"
                        " weight_effective_from) values (?,?,?,?,?,?)", [nid(), ORG, did, key, w, date(2026, 10, 1)])


def test_october_is_governed_by_the_version_in_force_on_1_october_and_refused(plane):
    """a4.2: the October period opens on 30 Sep, but the month it covers starts on 1 Oct, so version 2 (in progress) governs it."""
    _v2_from_october(plane)
    late = date(2026, 11, 5)
    assert C.benchmark_return(plane, "BLEND", SEP, OCT31, cutoff=late)["definition"]["version_number"] == 2
    assert C.benchmark_return(plane, "BLEND", AUG, SEP)["definition"]["version_number"] == 1      # September still certifies on version 1
    c = K.comparison(plane, PF, "BLEND", SEP, OCT31, cutoff=late)
    assert c["benchmark"]["value"] is None and c["certified"] is False and c["difference"] is None
    assert any("still being defined" in x for x in c["problems"])
    assert K.comparison(plane, PF, "BLEND", AUG, SEP)["certified"] is True


def test_an_unfinished_month_has_no_return_rather_than_zero(plane):
    """a4.7: on 9 Oct, October has no closing value; the return is not available, never 0%."""
    p = C.portfolio_return(plane, PF, SEP, OCT31, cutoff=date(2026, 10, 9))
    assert p["value"] is None and p["problems"] == ["Not available yet: the period runs to 31 Oct 2026 and has not ended."]
    b = C.benchmark_return(plane, "SPREAD", SEP, OCT31, cutoff=date(2026, 10, 9))
    assert b["value"] is None and b["problems"][0].startswith("Not available yet") and not any("too old" in x for x in b["problems"])
