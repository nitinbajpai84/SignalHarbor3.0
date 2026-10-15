"""Card D: tools/seed_10uc.py on a temporary data root. Every planted fact of docs/test/10UC-ANSWER-KEY.md is asserted from the product's own
functions (never from the seed's tables alone). Synthetic data only; the live data root is never touched."""
import json
import os
from datetime import date
from decimal import Decimal

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import (c4_library, e1_reports, e2_match, e3_calc, e3_recon, e4_cases, e5_brief, k4_office as O, k5_managers as K5,
                            k6_liquidity as K6, k7_benchmark as K7, k8_sop, p1_project, wh)
from sh_platform.jsonfile import read_json_strict
from tools import seed_10uc as S

D = Decimal
U = S.U
as_of = date(2026, 10, 9)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    root = tmp_path_factory.mktemp("sh10uc")
    out = S.seed(root)
    plane = PlaneStore(root).plane_for("evergreen").ensure()
    ids, _ = S.EG.accounts(root)
    yield {"root": root, "plane": plane, "V": S.viewers(ids), "out": out}
    mp.undo()


def q(world, sql, *args):
    with wh.connect(world["plane"]) as con:
        return con.execute(sql, list(args)).fetchall()


def cases(world, kind=None):
    rows = e4_cases.listing(world["plane"], world["V"]["Grace Ong"])
    return [c for c in rows if kind in (None, c["exception_type"])]


def pf_id(world, code):
    return str(q(world, "select id from portfolios where portfolio_code = ?", code)[0][0])


# ---- the universe is whole and consistent ----------------------------------------------------------------------------------

def test_the_company_has_the_shape_the_card_asks_for(world):
    assert q(world, "select count(*) from legal_entities")[0][0] == 3
    assert q(world, "select count(*) from portfolios")[0][0] == 4
    assert q(world, "select count(distinct manager_name) from instruments where manager_name is not null")[0][0] == 6
    kinds = dict(q(world, "select instrument_type, count(*) from instruments group by 1"))
    assert (kinds["private_fund"], kinds["hedge_fund"], kinds["liquid_fund"]) == (5, 2, 2)
    assert q(world, "select count(*) from instruments where instrument_type in ('listed_equity','bond') or canonical_name like 'Pacific Rim%'")[0][0] == 20
    assert q(world, "select count(*) from instruments where instrument_type = 'fx_forward'")[0][0] == 2
    assert q(world, "select count(distinct valuation_date) from valuation_observations where valuation_date >= date '2025-10-31'")[0][0] >= 12
    assert q(world, "select count(*) from business_rules")[0][0] == 10
    assert q(world, "select count(*) from nav_snapshots")[0][0] == 48


def test_a_second_run_changes_nothing(world):
    tables = [r[0] for r in q(world, "select table_name from information_schema.tables where table_schema = 'main' and table_type = 'BASE TABLE'")]
    before = {t: q(world, f"select count(*) from {t}")[0][0] for t in tables}
    lib = len(c4_library._index(world["plane"]))
    again = S.seed(world["root"])
    assert (again["static"], again["history"], again["dashboard"]) == ("kept", "kept", "kept")
    assert {t: q(world, f"select count(*) from {t}")[0][0] for t in tables} == before
    assert len(c4_library._index(world["plane"])) == lib


def test_each_administrator_nav_equals_the_holdings_it_was_struck_on(world):
    """The administrator NAV is the sum of the holdings known when it was struck; the investment view known now is what the universe says."""
    plane, bad = world["plane"], []
    for n in U["administrator_nav_monthly"]:
        pid, end = pf_id(world, n["portfolio"]), date.fromisoformat(n["nav_period_end"])
        struck = q(world, "select recorded_at from nav_snapshots where portfolio_id = ? and nav_period_end = ?", pid, end)[0][0]
        if (e3_calc.portfolio_value(plane, pid, end, struck)["total"], e3_calc.portfolio_value(plane, pid, end, None)["total"]) != (
                D(n["nav_amount"]), D(n["investment_view_known_now"])):
            bad.append((n["portfolio"], n["nav_period_end"]))
    assert not bad


def test_liquid_book_lines_multiply_out_and_add_up(world):
    for month, book in U["liquid_book_month_end"].items():
        got = q(world, "select sum(value_amount) from valuation_observations v join portfolios p on p.id = v.portfolio_id "
                       "where p.portfolio_code = 'EG-LIQUID' and v.valuation_date = ?", date.fromisoformat(month))[0][0]
        assert got == D(book["total"])
        for p in book["positions"]:
            assert D(p["quantity"]) * D(p["price"]) == D(p["value"])
    assert q(world, "select count(*) from valuation_observations v join portfolios p on p.id = v.portfolio_id "
                    "where p.portfolio_code = 'EG-LIQUID' and v.valuation_date = date '2026-09-30' and v.value_amount <> 0")[0][0] == 20


def test_calls_never_exceed_commitments_and_match_the_register(world):
    ins = {str(r[0]): r[1] for r in q(world, "select id, canonical_name from instruments")}
    key = {f["canonical_name"]: f["key"] for f in U["funds"]}
    got = {key[ins[c["instrument_id"]]]: c for c in K6.commitments(world["plane"])}
    for c in U["commitments"]:
        g = got[c["fund"]]
        assert g["commitment_amount"] == D(c["commitment_amount"]) and g["called"] <= g["commitment_amount"]
        assert g["called"] + g["uncalled"] == g["commitment_amount"]
    # the register is to 30 Sep: A, B and E agree; C and D also count the October notices the product has confirmed (450,000 and 250,000)
    assert [(got[k]["called"], got[k]["uncalled"]) for k in "AB"] == [(D("11250000"), D("3750000")), (D("7200000"), D("800000"))]
    assert (got["E"]["called"], got["E"]["uncalled"]) == (D("4000000"), D("6000000"))
    assert (got["C"]["called"], got["C"]["uncalled"]) == (D("4050000"), D("1950000"))
    assert (got["D"]["called"], got["D"]["uncalled"]) == (D("4750000"), D("250000"))


# ---- UC1 -------------------------------------------------------------------------------------------------------------------

def test_uc1_issued_report_and_what_is_known_now(world):
    cio = world["V"]["Daniel Foo"]
    iv = O.issued_vs_known(world["plane"], cio)
    lines = {l["label"]: l for l in iv["lines"]}
    assert (lines["Total"]["issued"], lines["Total"]["known_now"]) == (D("57600000"), D("57780000"))
    assert (lines["Evergreen Growth I"]["issued"], lines["Evergreen Growth I"]["known_now"], lines["Evergreen Growth I"]["status"]) == (D("10000000"), D("10180000"), "revised")
    assert lines["Evergreen Income II"]["status"] == lines["Evergreen Liquid Book"]["status"] == "official"
    vid = iv["report"]["report_version_id"]
    assert iv["report"]["issued_at"].isoformat().startswith("2026-10-03T10:30") or str(iv["report"]["issued_at"]).startswith("2026-10-03")
    sgd = {l["label"]: l["issued"] for l in e5_brief.brief(world["plane"], cio, vid, "SGD")["lines"]}
    assert e3_calc.fx(world["plane"], "USD", "SGD", date(2026, 9, 30)) == D("1.3412") and sgd["Total"] == D("77253120.00")
    assert e3_calc.fx(world["plane"], "USD", "SGD", as_of) == D("1.3388")
    rev = [c for c in cases(world, "revision")]
    assert len(rev) == 1 and rev[0]["candidate_impact_amount"] == D("180000")
    assert D("180000") > D("100000") and D("180000") / D("10000000") * 100 == D("1.8")      # over cio_materiality (100,000 or 0.5%)


def test_uc1_the_nav_bridge_at_30_sep(world):
    got = {p["portfolio_name"]: p for p in O.nav_bridge(world["plane"], world["V"]["Daniel Foo"], "USD", date(2026, 9, 30))["portfolios"]}
    want = {"Evergreen Growth portfolio": ("16580000", "16400000", "revisions", "180000"), "Evergreen Liquid portfolio": ("41200000", "41200000", None, "0"),
            "Entity B operating portfolio": ("22875000", "22525000", "revisions", "350000"), "Evergreen Funds portfolio": ("22750000", "22550000", "revisions", "200000")}
    for name, (inv, nav, part, amount) in want.items():
        g = got[name]
        assert (g["investment_total"], g["administrator_nav"]) == (D(inv), D(nav))
        parts = {x["code"]: x["amount"] for x in g["parts"]}
        assert sum(parts.values()) == g["difference"] and parts["unexplained"] == parts["fx"] == parts["timing"] == 0
        assert part is None or parts[part] == D(amount)
    assert {e["label"].split(":")[0] for e in got["Evergreen Funds portfolio"]["parts"][0]["evidence"]} == {
        "Kestrel Ridge Macro Fund", "Kestrel Ridge Equity Long/Short Fund"}


def test_uc1_holdings_status_words(world):
    h = O.holdings(world["plane"], world["V"]["Daniel Foo"], "USD", as_of)
    lines = {l["name"]: l for e in h["entities"] for p in e["portfolios"] for l in p["lines"]}
    status = {n: lines[n]["status"] for n in ("Evergreen Growth I", "Evergreen Income II", "Cedarpoint Ventures III", "Cedarpoint Opportunities II",
                                              "Saltmarsh Infrastructure Fund II", "Kestrel Ridge Macro Fund", "Kestrel Ridge Equity Long/Short Fund",
                                              "Global Equity Index Fund (synthetic)", "Global Bond Index Fund (synthetic)", "Pacific Rim Convertible 2029 note")}
    assert status == {"Evergreen Growth I": "revised", "Evergreen Income II": "official", "Cedarpoint Ventures III": "stale",
                      "Cedarpoint Opportunities II": "stale", "Saltmarsh Infrastructure Fund II": "unverified", "Kestrel Ridge Macro Fund": "estimated",
                      "Kestrel Ridge Equity Long/Short Fund": "estimated", "Global Equity Index Fund (synthetic)": "official",
                      "Global Bond Index Fund (synthetic)": "official", "Pacific Rim Convertible 2029 note": "Needs a class"}
    assert lines["Cedarpoint Ventures III"]["value"] == D("8275000") and lines["Saltmarsh Infrastructure Fund II"]["value"] == D("9950000")
    assert lines.get("Evergreen Liquid Book", {"value": 0})["value"] == 0    # the roll-up carries nothing (P1 hides its zero line): its 20 securities are the lines


def test_uc1_why_the_liquid_book_moved(world):
    pf = pf_id(world, "EG-LIQUID")
    aug, sep = (e3_calc.portfolio_value(world["plane"], pf, d, None)["total"] for d in (date(2026, 8, 31), date(2026, 9, 30)))
    assert (aug, sep) == (D("39552000"), D("41200000")) and sep - aug == D("1648000")
    r = e3_calc.portfolio_return(world["plane"], pf, date(2026, 8, 31), date(2026, 9, 30))
    assert r["value"].quantize(D("0.000001")) == D("0.041667") and r["flows"] == 0
    move = q(world, "select i.canonical_name, v.value_amount - a.value_amount from valuation_observations v join valuation_observations a on a.instrument_id = v.instrument_id "
                    "and a.portfolio_id = v.portfolio_id and a.valuation_date = date '2026-08-31' join instruments i on i.id = v.instrument_id "
                    "where v.valuation_date = date '2026-09-30' and v.portfolio_id = ? order by 2 desc limit 2", pf)
    assert move == [("Northwind Logistics", D("132000")), ("Silverpine Software", D("130400"))]


# ---- UC2 -------------------------------------------------------------------------------------------------------------------

def test_uc2_entity_b_cash_break_and_no_case_for_the_trust(world):
    run = next(r for r in e3_recon.last_runs(world["plane"]) if r["recon_code"] == "cash_by_entity")
    assert (run["as_of_date"], run["checked"], run["breaks"]) == ("2026-10-08", 3, 1)
    cash = [c for c in cases(world, "break") if c["title"].startswith("Cash differs")]
    assert len(cash) == 1 and "Entity B" in cash[0]["title"] and cash[0]["candidate_impact_amount"] == D("12400")
    liq = O.liquidity(world["plane"], world["V"]["Daniel Foo"], "USD", as_of)
    cash_by = {e["entity_code"]: e["available_cash"] for e in liq["entities"]}
    assert cash_by == {"EG-B": D("880400"), "EG-HOLD": D("2300000"), "EG-TRUST": D("1150000")}
    ops = q(world, "select e.entity_code, p.view_type, sum(p.source_market_value) from position_snapshots p join portfolios f on f.id = p.portfolio_id "
                   "join legal_entities e on e.id = f.legal_entity_id join instruments i on i.id = p.instrument_id "
                   "where i.instrument_type = 'cash' and p.position_date = date '2026-10-08' group by 1, 2 order by 1, 2")
    assert ops == [("EG-B", "accounting", D("880400")), ("EG-B", "operational", D("868000")), ("EG-HOLD", "accounting", D("2300000")),
                   ("EG-HOLD", "operational", D("2300000")), ("EG-TRUST", "accounting", D("1150000")), ("EG-TRUST", "operational", D("1148200"))]


def test_uc2_p08b_cash_movements_add_up_and_tally_ranks_the_wire(world):
    from sh_platform.v1 import n1_tally
    rows = q(world, "select e.entity_code, s.source_code, m.effective_date, m.amount, r.external_record_id from cash_movements m "
                    "join source_records r on r.id = m.source_record_id join source_batches b on b.id = r.source_batch_id "
                    "join source_systems s on s.id = b.source_system_id join portfolios p on p.id = m.portfolio_id "
                    "join legal_entities e on e.id = p.legal_entity_id where r.record_type = 'cash_movement'")
    assert len(rows) == sum(1 for i in U["cash_activity"] for k in ("administrator_date", "trading_export_date") if i[k])
    for c in U["cash_daily"]:                                   # opening + movements to date = the balance, each side, each day
        for side in ("administrator", "trading_export"):
            got = D(U["cash_opening_8_sep"][c["entity"]][side]) + sum((r[3] for r in rows if r[0] == c["entity"] and r[1] == side and r[2].isoformat() <= c["date"]), D(0))
            assert got == D(c[side]), (c, side)
    assert sorted((r[1], r[2].isoformat(), r[3]) for r in rows if r[4] == "WIRE-20261008-B01") == [("administrator", "2026-10-09", D("-12400")), ("trading_export", "2026-10-08", D("-12400"))]
    case = next(c for c in cases(world, "break") if c["title"].startswith("Cash differs"))
    got = n1_tally.explain(world["plane"], world["V"]["Mei Chen"], case["id"])
    top = next(f for f in got["findings"] if f["key"] == "candidate")
    assert "WIRE-20261008-B01" in top["text"] and "timing difference" in top["text"] and top["figure"] == "12,400 USD"
    assert "WIRE-20261008-B01" in got["summary"] and not any("balances only" in m for m in got["missing"])


# ---- UC3 -------------------------------------------------------------------------------------------------------------------

def _first_and_last(world, fund, day):
    """The value a fund's chain of valuations for one date began with and the value it ends on (each row supersedes the one before)."""
    rows = {str(r[0]): (str(r[1]) if r[1] else None, r[2]) for r in q(
        world, "select v.id, v.supersedes_valuation_id, v.value_amount from valuation_observations v join instruments i on i.id = v.instrument_id "
               "where i.canonical_name = ? and v.valuation_date = ?", fund, date.fromisoformat(day))}
    tip = next(i for i in rows if i not in {s for s, _ in rows.values() if s})
    root = tip
    while rows[root][0]:
        root = rows[root][0]
    return rows[root][1], rows[tip][1]


def _funds(world, on):
    inbox = K5.inbox(world["plane"], world["V"]["Mei Chen"], on)
    return {f["fund_name"]: f for m in inbox["managers"] for f in m["funds"]}, inbox


def test_uc3_september_statements_expected_against_received(world):
    funds, inbox = _funds(world, as_of)
    assert inbox["due_rule_signed"] and len(funds) == 9 and len({m["name"] for m in inbox["managers"]}) == 6
    state = {n: f["state"] for n, f in funds.items()}
    assert {f["due"] for f in funds.values()} == {"2026-10-14"}
    for n in ("Cedarpoint Ventures III", "Cedarpoint Opportunities II"):
        assert state[n] == "not_due"
    assert [n for n, s in state.items() if s == "received"].__len__() == 7
    assert funds["Saltmarsh Infrastructure Fund II"]["last_value"]["status"] == "unverified"
    assert funds["Saltmarsh Infrastructure Fund II"]["last_value"]["amount"] == "9950000"
    assert funds["Kestrel Ridge Macro Fund"]["received_on"] == "2026-10-06" and funds["Kestrel Ridge Equity Long/Short Fund"]["received_on"] == "2026-10-07"
    assert funds["Evergreen Growth I"]["received_on"] == "2026-10-02" and funds["Evergreen Income II"]["received_on"] == "2026-10-01"


def test_uc3_late_statements_in_the_month_they_were_judged(world):
    h2, _ = _funds(world, date(2026, 9, 23))
    assert (h2["Kestrel Ridge Equity Long/Short Fund"]["state"], h2["Kestrel Ridge Equity Long/Short Fund"]["due"],
            h2["Kestrel Ridge Equity Long/Short Fund"]["days_late"]) == ("received_late", "2026-09-14", 6)
    e, _ = _funds(world, date(2026, 7, 25))
    assert (e["Saltmarsh Infrastructure Fund II"]["state"], e["Saltmarsh Infrastructure Fund II"]["days_late"]) == ("received_late", 8)
    d, _ = _funds(world, date(2026, 4, 22))
    assert (d["Cedarpoint Opportunities II"]["state"], d["Cedarpoint Opportunities II"]["days_late"]) == ("received_late", 5)


def test_uc3_the_missing_statement_and_the_follow_up_draft(world):
    funds, _ = _funds(world, as_of)
    miss = funds["Cedarpoint Opportunities II"]["earlier_missing"]
    assert miss == [{"period_end": "2026-06-30", "due": "2026-07-14", "days_late": 63}]
    mei = world["V"]["Mei Chen"]
    d = K5.draft_followup(world["plane"], mei, "cedarpoint-ventures", None, as_of)
    assert d["sent"] is False and "Cedarpoint Opportunities II" in d["draft"] and "30 Jun 2026" in d["draft"] and "14 Jul 2026" in d["draft"] and "63 business days overdue" in d["draft"]
    assert "Dear Hana Sato (Cedarpoint Ventures)," in d["body"]


def test_uc3_three_amended_statements_one_row_per_fund(world):
    funds, inbox = _funds(world, as_of)
    assert sum(f["revisions_total"] for f in funds.values()) == 3
    assert [n for n, f in funds.items() if f["revisions_total"]] == ["Cedarpoint Ventures III", "Kestrel Ridge Macro Fund", "Evergreen Growth I"] or \
        {n for n, f in funds.items() if f["revisions_total"]} == {"Cedarpoint Ventures III", "Kestrel Ridge Macro Fund", "Evergreen Growth I"}
    assert (_first_and_last(world, "Evergreen Growth I", "2026-09-30")) == (D("10000000"), D("10180000"))
    assert (_first_and_last(world, "Cedarpoint Ventures III", "2026-06-30")) == (D("8420000"), D("8275000"))
    assert (_first_and_last(world, "Kestrel Ridge Macro Fund", "2026-07-31")) == (D("7050000"), D("7012500"))
    sysid = q(world, "select id from source_systems where source_code = 'manager_email'")[0][0]
    ids = {n: e2_match.resolve(world["plane"], n, str(sysid))["instrument_id"] for n in
           ("KR Macro Fund Ltd - Class B USD", "Kestrel Ridge Macro Fund", "Fund B - Evergreen Liquid Book", "Evergreen Income II")}
    assert ids["KR Macro Fund Ltd - Class B USD"] == ids["Kestrel Ridge Macro Fund"] and ids["Fund B - Evergreen Liquid Book"] == ids["Evergreen Income II"]
    assert ids["Kestrel Ridge Macro Fund"] != ids["Evergreen Income II"] and sum(len(m["funds"]) for m in inbox["managers"]) == 9


# ---- UC4 -------------------------------------------------------------------------------------------------------------------

def test_uc4_benchmark_computed_from_the_seeded_index_levels(world):
    plane, p = world["plane"], D("0.000001")
    pf = pf_id(world, "EG-LIQUID")
    b = e3_calc.benchmark_return(plane, "EG-OFFICE-BLEND", date(2026, 8, 31), date(2026, 9, 30))
    parts = {(c["series_key"], c["weight"]): c for c in b["components"]}
    eq, bd = parts[("IDX:GLEQ:SYN", D("0.42"))], parts[("IDX:GLBD:SYN", D("0.28"))]
    assert eq["index_return"].quantize(D("0.00001")) == D("0.03500") and bd["index_return"].quantize(D("0.00001")) == D("0.00400")
    assert eq["index_return"] == D("1074.56") / D("1038.22") - 1 and bd["index_return"] == D("1041.22") / D("1037.07") - 1
    sleeve = parts[("IDX:GLEQ:SYN", D("0.30"))]                                    # 300 bps a year, 25 bps for the month
    assert sleeve["spread_return"] == D("300") / 10000 / 12
    assert b["value"].quantize(p) == D("0.027072") and b["definition"]["version_number"] == 1 and b["definition"]["approval_status"] == "approved"
    assert sum(c["weight"] for c in b["components"]) == 1
    c = K7.comparison(plane, pf, "EG-OFFICE-BLEND", date(2026, 8, 31), date(2026, 9, 30))
    assert c["certified"] and c["problems"] == [] and c["portfolio"]["value"].quantize(p) == D("0.041667")
    assert c["difference"].quantize(p) == D("0.014595")
    sixty_forty = D("0.6") * (D("1074.56") / D("1038.22") - 1) + D("0.4") * (D("1041.22") / D("1037.07") - 1)
    assert sixty_forty.quantize(p) == D("0.022602") and (c["portfolio"]["value"] - sixty_forty).quantize(p) == D("0.019065")


def test_uc4_version_two_is_in_progress_and_refused_for_certified_output(world):
    from sh_platform.v1.i2_north import Refused
    v = q(world, "select version_number, approval_status from benchmark_definitions order by 1")
    assert v == [(1, "approved"), (2, "in_progress")]
    w = q(world, "select sum(component_weight) from benchmark_components c join benchmark_definitions d on d.id = c.benchmark_definition_id group by d.version_number order by d.version_number")
    assert [r[0] for r in w] == [D("1"), D("1")]
    with pytest.raises(Refused, match="still being defined"):
        K7.certified_return(world["plane"], "EG-OFFICE-BLEND", date(2026, 10, 1), date(2026, 10, 8))
    q_cases = [c for c in cases(world, "policy_question") if "EG-OFFICE-BLEND" in c["title"]]
    assert len(q_cases) == 1
    assert K7.certified_return(world["plane"], "EG-OFFICE-BLEND", date(2026, 8, 31), date(2026, 9, 30))["value"] is not None


def test_uc4_the_consume_route_reads_the_same_figures(world):
    from sh_platform.v1 import k7_routes
    m = k7_routes.monthly(world["plane"], world["V"]["Daniel Foo"], "EG-LIQUID", "EG-OFFICE-BLEND", "2026-09", "2026-09")
    sep = m["months"][0]
    assert (sep["portfolio"]["pct"], sep["benchmark"]["pct"], sep["difference"]["pct"]) == ("4.1667", "2.7072", "1.4595")
    assert (sep["liquid_sleeve"]["pct"], sep["liquid_sleeve"]["difference"]["pct"]) == ("2.2602", "1.9065") and sep["certified"] and m["version_used"]["version"] == 1
    assert {c["return"]["pct"] for c in sep["components"]} == {"0.4002", "3.5002", "3.7502"}
    v2 = k7_routes.definitions(world["plane"])["definitions"][1]
    assert v2["status"] == "in_progress" and v2["policy_question"]["case"]["title"] == "Agree the definition of benchmark EG-OFFICE-BLEND"


# ---- UC5 -------------------------------------------------------------------------------------------------------------------

def test_uc5_one_real_breach_one_caused_by_a_stale_valuation(world):
    run = next(r for r in e3_recon.last_runs(world["plane"]) if r["recon_code"] == "limits")
    assert (run["as_of_date"], run["breaks"]) == ("2026-10-09", 2)
    causes = {c["title"].split(" · ")[1].lower(): c["cause"] for c in run["causes"]}
    assert causes == {"harborview semiconductor": "real breach", "cedarpoint ventures": "stale data"}
    lim = {c["title"]: c for c in cases(world, "limit_breach")}
    assert len(lim) == 2
    real = next(c for t, c in lim.items() if "Harborview" in t)
    stale = next(c for t, c in lim.items() if "cedarpoint" in t.lower())
    full = {c["id"]: e4_cases.get(world["plane"], c["id"], world["V"]["Grace Ong"]) for c in (real, stale)}
    assert "It is 5.75%" in full[real["id"]]["description"] and "Cause: real breach" in full[real["id"]]["description"]
    assert "It is 56.50%" in full[stale["id"]]["description"] and "Cause: stale data" in full[stale["id"]]["description"]
    share = D("2368000") / D("41200000") * 100
    assert share.quantize(D("0.01")) == D("5.75") and (D("12925000") / D("22875000") * 100).quantize(D("0.01")) == D("56.50")
    assert q(world, "select sum(v.value_amount) from valuation_observations v join instruments i on i.id = v.instrument_id where v.valuation_date = date '2026-09-30' "
                    "and i.canonical_name = 'Harborview Semiconductor'")[0][0] == D("2368000")


def test_uc5_limits_inside_range_and_the_instrument_without_a_class(world):
    run = next(r for r in e3_recon.last_runs(world["plane"]) if r["recon_code"] == "limits")
    res = {(r["rule_code"], r["portfolio"]): r for r in run["results"]}
    eq, hf = res[("limit_listed_equity_liquid", "Evergreen Liquid portfolio")], res[("limit_hedge_funds", "Evergreen Funds portfolio")]
    assert (eq["exposure_pct"], eq["breached"], hf["exposure_pct"], hf["breached"]) == ("80.61", False, "54.95", False)
    assert [(r["rule_code"], r["exposure_pct"]) for r in res.values() if r["breached"]] == [("limit_manager_entity_b", "56.50"), ("limit_single_name_liquid", "5.75")]
    assert [(x["instrument"], x["status"], x["value"], x["exposure_pct"]) for x in run["questions"]] == [("Pacific Rim Convertible 2029 note", "Needs a class", "1122000.00", "2.72")]
    assert q(world, "select sum(v.value_amount) from valuation_observations v join instruments i on i.id = v.instrument_id where v.valuation_date = date '2026-09-30' "
                    "and i.asset_class = 'listed_equity' and v.portfolio_id = ?", pf_id(world, "EG-LIQUID"))[0][0] == D("33210500")
    assert q(world, "select asset_class from instruments where canonical_name like 'Pacific Rim%'") == [(None,)]
    titles = " ".join(c["title"] for c in cases(world, "limit_breach")).lower()
    assert "listed" not in titles and "hedge" not in titles and "pacific" not in titles
    words = " ".join(run["rule_words"])
    assert all(w in words for w in ("Harborview Semiconductor share of the Evergreen Liquid portfolio must be at most 5%", "at most 55%", "between 60% and 90%", "between 20% and 60%"))


# ---- UC6 -------------------------------------------------------------------------------------------------------------------

def test_uc6_calls_due_in_30_60_90_days_and_the_unconfirmed_one(world):
    f = K6.forecast(world["plane"], as_of, viewer=world["V"]["Daniel Foo"])
    ent = {e["entity_code"]: e for e in f["entities"]}
    b = {k["key"]: k for k in ent["EG-B"]["buckets"]}
    assert ent["EG-B"]["available_cash"] == D("880400")
    assert [(i["fund"], i["amount"], i["due_date"], i["status"]) for i in b["30"]["items"]] == [
        ("Cedarpoint Ventures III", D("450000"), "2026-10-20", "confirmed"), ("Saltmarsh Infrastructure Fund II", D("600000"), "2026-10-30", "noticed")]
    assert b["30"]["calls"] == D("1050000") and b["30"]["cash_after_calls"] == D("-169600")            # after both noticed calls
    assert D("880400") - D("450000") == D("430400")                                                   # after the confirmed call only
    assert [(i["fund"], i["amount"], i["due_date"]) for i in b["60"]["items"]] == [("Cedarpoint Opportunities II", D("250000"), "2026-12-04")]
    assert [(i["fund"], i["amount"]) for i in ent["EG-B"]["unconfirmed"]] == [("Saltmarsh Infrastructure Fund II", D("600000"))]
    dist = [i for k in ent["EG-HOLD"]["buckets"] for i in k["items"] if i["kind"] == "distribution"]
    assert [(i["fund"], i["amount"], i["due_date"], i["status"]) for i in dist] == [("Evergreen Growth I", D("320000"), "2026-11-16", "noticed")]
    assert all(not any(k["items"] for k in e["buckets"] if k["key"] in ("30", "60", "90")) for e in f["entities"] if e["entity_code"] == "EG-TRUST")


def test_uc6_the_finance_case_for_the_confirmed_call(world):
    fin = [c for c in cases(world, "capital_call")]
    assert any(c["candidate_impact_amount"] == D("450000") for c in fin) and all(c["title"].startswith("Fund the capital call") for c in fin)
    assert not any(c["candidate_impact_amount"] == D("600000") for c in fin)                         # a call not yet confirmed opens no case
    mv = q(world, "select count(*) from cash_movements where notice_kind = 'call' and confirmation_status = 'noticed'")[0][0]
    assert mv >= 1


# ---- UC7 -------------------------------------------------------------------------------------------------------------------

def test_uc7_what_changed_since_the_last_kestrel_meeting(world):
    sponsor = world["V"]["Daniel Foo"]
    ch = K5.changes(world["plane"], sponsor, "kestrel-ridge-advisors")
    assert ch["since"] == "2026-06-12" and ch["worded_by"] == "rules"
    text = " ".join(i["text"] for i in ch["items"])
    assert "Kestrel Ridge Macro Fund dated 31 Jul 2026 arrived" in text and "revised statement" in text.lower()
    assert "Kestrel Ridge Equity Long/Short Fund dated 31 Aug 2026 arrived" in text and "Q3 2026 newsletter" in text
    assert any(i["date"] == "2026-08-20" and i["kind"] == "statement" for i in ch["items"])           # the 20 Aug amended statement (7,050,000 to 7,012,500)
    assert any(i["date"] == "2026-09-22" and "31 Aug 2026" in i["text"] for i in ch["items"])          # the 22 Sep Aug statement of the L/S fund
    chip = ch["passages"][0]
    assert chip["file"] == "Kestrel Ridge Advisors Q3 2026 newsletter.pdf" and chip["date"] == "2026-09-28"
    assert "Thomas Lindqvist left the firm on 30 September 2026" in chip["text"] and "Priya Nair is sole portfolio manager" in chip["text"]
    assert not any(w in json.dumps(ch).lower() for w in ("good manager", "bad manager", "concern", "recommend"))


def test_uc7_the_cedarpoint_profile(world):
    p = K5.profile(world["plane"], world["V"]["Daniel Foo"], "cedarpoint-ventures", as_of)
    rows = {r["fund_id"]: r for r in p["commitments"]["rows"]}
    assert sorted((r["commitment"] for r in rows.values())) == ["5000000", "6000000"]
    fund_d = next(f for f in p["funds"] if f["fund_name"] == "Cedarpoint Opportunities II")
    assert fund_d["last_value"]["valuation_date"] == "2026-03-31" and fund_d["earlier_missing"][0]["period_end"] == "2026-06-30"
    assert [d["name"] for d in p["documents"]] == ["Cedarpoint Ventures LP update call.md", "Cedarpoint Ventures DDQ 2026.pdf"] or \
        {d["name"] for d in p["documents"]} == {"Cedarpoint Ventures LP update call.md", "Cedarpoint Ventures DDQ 2026.pdf"}
    assert [x["text"] for x in p["questions"]] == ["Cedarpoint Opportunities II's 30 June 2026 statement was due on 14 July 2026 and has not arrived. Ask Cedarpoint when to expect it."]
    assert p["last_meeting"] == "2026-05-19"
    lib = {i["name"]: i for i in c4_library._index(world["plane"])}
    assert lib["Cedarpoint Ventures DDQ 2026.pdf"]["at"].startswith("2026-03-05") and lib["Evergreen investment committee note_ September 2026.md"]["sensitivity"] == "internal"
    assert world["V"]["Raj Patel"].name and not c4_library.readable(lib["Evergreen investment committee note_ September 2026.md"], world["V"]["Raj Patel"])


# ---- UC8 -------------------------------------------------------------------------------------------------------------------

def test_uc8_three_trade_breaks_and_the_matches(world):
    run = next(r for r in e3_recon.last_runs(world["plane"]) if r["recon_code"] == "trade_vs_admin")
    assert (run["as_of_date"], run["breaks"]) == ("2026-10-09", 3) and run["checked"] >= 7   # P3 counts each side checked
    titles = {c["title"]: c for c in cases(world, "break") if c["title"].startswith("Trade")}
    assert len(titles) == 3
    nw = next(c for t, c in titles.items() if "Northwind" in t)
    hv = next(c for t, c in titles.items() if "Harborview" in t)
    fxc = next(c for t, c in titles.items() if "FXF-2026-002" in t)
    assert nw["candidate_impact_amount"] == D("75870") == D(1800) * D("42.15") and "T-20261002-003" in nw["title"]
    assert hv["candidate_impact_amount"] == D("592000") and hv["title"].startswith("Trade not matched") and "T-20261006-005" in hv["title"]
    assert fxc["candidate_impact_amount"] == D("8100") and D("4035600") - D("4027500") == D("8100")
    usd = D("8100") * e3_calc.fx(world["plane"], "SGD", "USD", as_of)
    assert usd.quantize(D("0.01")) == D("6050.19") and usd > D("5000")
    assert not any(i in t for t in titles for i in ("T-20261001-001", "T-20261002-002", "T-20261007-006", "FXF-2026-001", "T-20260915-F01"))
    rates = {r[0]: r[1] for r in q(world, "select external_trade_id, cash_amount from transactions where external_trade_id like 'T-2026100%'")}
    assert D(rates["T-20261001-001"]) == D("-662000")                                                  # a buy is cash out


# ---- UC9 -------------------------------------------------------------------------------------------------------------------

def test_uc9_the_sop_from_the_signed_process_map(world):
    plane = world["plane"]
    pr = next(p for p in p1_project.all_projects(plane) if p["title"] == "Monthly investment report in USD and SGD")
    sow = read_json_strict(plane.path("intents", pr["intent_id"], "sow.json"))
    assert sow["state"] == "signed"
    sop = k8_sop.build(sow)
    assert len(sop["steps"]) == 6 and sop["manual_steps"] == [1, 2, 3, 4] and sop["open_points"] == []
    assert [(s["n"], s["who"], s["system"]) for s in sop["steps"]] == [(1, "Mei Chen", "File drop"), (2, "Mei Chen", "Excel"), (3, "Mei Chen", "Email"),
                                                                       (4, "Raj Patel", "Excel"), (5, "Raj Patel", "Report pack"), (6, "Daniel Foo", "Report pack")]
    assert "cash tolerance of 5,000 USD" in sop["steps"][1]["control"] and "12,400 USD on 8 Oct 2026" in sop["steps"][1]["exception"]
    assert [[h["to_step"] for h in s["handovers"]] for s in sop["steps"]] == [[2], [3], [4], [5], [6], []]
    md = k8_sop.to_markdown(sop)
    assert "Manual steps flagged for automation" in md and "Not stated yet" not in md


# ---- UC10 ------------------------------------------------------------------------------------------------------------------

def test_uc10_the_project_runs_through_build_and_consume_on_13_months(world):
    plane, pid = world["plane"], world["out"]["project_id"]
    plan = read_json_strict(plane.path("build", pid, "plan-v1.json"))
    assert plan["state"] == "live" and {t["name"] for t in plan["tables"] if t["layer"] == "bronze"} == {"bronze_administrator_positions", "bronze_trading_export_positions"}
    dash = read_json_strict(plane.path("consume", pid, "dashboards", "dash-0ad2b1c7.json"))
    assert [t["title"] for t in dash["tiles"]] == ["Net worth by entity", "Cash by entity", "Holdings by status"] and {t["state"] for t in dash["tiles"]} == {"accepted"}
    users = {str(r[0]): r[1] for r in q(world, "select id, display_name from users")}
    assert sorted(users[a] for a in dash["audience"]) == ["Daniel Foo", "Raj Patel"]
    with wh.connect(plane) as con:
        res = {t["id"]: con.execute(t["sql"]).fetchall() for t in dash["tiles"]}
        months = con.execute("select count(distinct report_month) from gold_investment_report_holdings_monthly").fetchone()[0]
    assert months == 13
    assert {r[0]: r[1] for r in res["t-000001"]} == {"Entity B": D("22875000"), "Evergreen Family Trust": D("63950000"), "Evergreen Holdings": D("16580000")}
    assert sum(r[1] for r in res["t-000001"]) == D("103405000") and sum(r[1] for r in res["t-000003"]) == D("103405000")
    assert {r[0]: r[1] for r in res["t-000003"]} == {"estimated": D("12500000"), "official": D("62500000"), "revised": D("18455000"), "unverified": D("9950000")}
    assert {(r[0], r[1]): r[2] for r in res["t-000002"]}[("Entity B", "administrator")] == D("880400") and len(res["t-000002"]) == 6


# ---- PF1: the Build rooms have content, and the demo day is pinned ------------------------------------------------------------

def test_pf1_every_build_room_of_the_demo_project_has_content(world):
    from sh_platform.build import runner
    from sh_platform.v1 import b1_design, b2_scan, b3_mapping, b4_load, b6_plan, b6_run, g4_deviations
    plane, pid = world["plane"], world["out"]["project_id"]
    iid = p1_project.read(plane, pid)["intent_id"]
    d = b1_design.read_design(plane, iid)
    assert d and d["counts"]["gold"] == 4 and d["counts"]["source"] == 3 and len(d["lines"]) >= 3                       # Design with Span
    sc = b2_scan.read_scan(plane, iid)
    assert [k["status"] for k in sc["kpis"]] == ["available"] * 4 and sc["agreed"]["by"] == "Anita Rao"                    # Scan
    sheet = b3_mapping.read(plane, iid)["sheet"]
    assert len(sheet["rows"]) == 14 and {r["status"] for r in sheet["rows"]} == {"mapped"}                                 # Mapping sheet
    assert [v for v in b6_plan.versions(plane, pid)] == [1] and b6_plan.get(plane, pid)["schedule"] == {"freq": "daily", "at": "06:00", "day": None}
    assert [(e["by"], e["what"]) for e in b6_plan.read_log(plane, pid)][:2] == [("Leo Park", "proposed a build plan"), ("Anita Rao", "approved the build plan")]
    modes = {r["mode"]: r for r in b6_run.runs(plane, pid)}
    assert set(modes) == {"sandbox", "live"} and all(r["status"] == "ok" for r in modes.values())                          # Pipeline room
    counts = {s["table"]: s["rows"] for s in modes["live"]["steps"] if s["rows"] is not None}
    assert counts["gold_investment_report_holdings_monthly"] > 0 and counts["gold_investment_report_cash_daily"] > 0
    logged = {r["source"]: r for r in runner.read_runs(plane)}
    assert {s for s in logged} == {"v1_administrator", "v1_trading_export", "v1_manager_email"} and all(r["rows"] for r in logged.values())  # Run log
    assert len(b4_load.contracts_for(plane, iid)[0]) == 3
    devs = g4_deviations.read(plane, iid)
    assert len(devs) == 1 and devs[0]["status"] == "pending" and devs[0]["asks"][0]["name"] == "Anita Rao"                # Approval requests


def test_pf1_the_demo_day_is_pinned_to_9_oct_and_the_checks_tell_the_9_oct_story(world):
    plane = world["plane"]
    assert wh.demo_today(plane) == date(2026, 10, 9) and wh.now(plane).date() == date(2026, 10, 9)
    q(world, "select 1")                                                                    # connecting sets the clock of this thread to the company's
    assert wh.now().date() == date(2026, 10, 9)
    stale = next(c for c in cases(world, "limit_breach") if "cedarpoint" in c["title"].lower())
    text = e4_cases.get(plane, stale["id"], world["V"]["Grace Ong"])["description"]
    assert "(192 days)" in text and "(101 days)" in text                                    # ages counted to 9 Oct, not to the day the demo runs
    funds, _ = _funds(world, wh.now(plane).date())
    assert {funds[n]["state"] for n in ("Cedarpoint Ventures III", "Cedarpoint Opportunities II")} == {"not_due"}   # Cedarpoint is not late
    calls = cases(world, "capital_call")
    assert len(calls) == 1 and calls[0]["candidate_impact_amount"] == D("450000")           # one Finance call case


def test_pf1_without_the_setting_the_real_clock_is_used(world):
    from datetime import datetime, timezone
    plane = world["plane"]
    wh.set_demo_today(plane, None)
    try:
        assert wh.demo_today(plane) is None and wh.now(plane).date() == datetime.now(timezone.utc).date() and wh.now().date() == wh.now(plane).date()
    finally:
        wh.set_demo_today(plane, S.V3.DEMO_TODAY)
    assert wh.now(plane).date() == date(2026, 10, 9)


def test_the_answer_key_names_every_planted_fact():
    key = (S.ROOT / "docs" / "test" / "10UC-ANSWER-KEY.md").read_text(encoding="utf-8")
    missing = [p["id"] for p in U["planted"] if f"| {p['id']} " not in key and f"{p['id']}:" not in key and f"### {p['id']}" not in key]
    assert not missing, missing


# ---- triage cycle 1, package S: one test per ticket -----------------------------------------------------------------------

def _project(world):
    return next(p for p in p1_project.all_projects(world["plane"]) if p["title"] == "Monthly investment report in USD and SGD")


def test_c1_a1_11_and_a1_13_universe_names_the_book_and_calls_late_values_revisions():
    assert [l["label"] for l in U["report_issued"]["lines"]][2] == "Evergreen Liquid Book"
    bridge = {b["portfolio"]: b for b in U["nav_bridge_30_sep"]}
    assert (bridge["EG-B-OPS"]["revisions"], bridge["EG-B-OPS"]["timing"]) == ("350000.00", "0.00")
    assert (bridge["EG-FUNDS"]["revisions"], bridge["EG-FUNDS"]["timing"]) == ("200000.00", "0.00")
    assert {p["kind"] for b in bridge.values() for p in b["parts"]} == {"revision"}


def test_c1_a2_1_the_wire_points_at_its_row_in_the_landed_trading_file(world):
    import csv
    rel, sheet, row = q(world, "select r.raw_payload_uri, r.sheet_name, r.row_number from source_records r join source_batches b on b.id = r.source_batch_id "
                               "join source_systems s on s.id = b.source_system_id where r.external_record_id = 'WIRE-20261008-B01' and s.source_code = 'trading_export'")[0]
    lines = list(csv.DictReader(world["plane"].path(*rel.split("/")).read_text(encoding="utf-8").splitlines()))
    got = lines[row - 2]
    assert sheet.endswith(".csv") and got["reference"] == "WIRE-20261008-B01"
    assert (got["description"], got["counterparty"]) == ("Legal fees, Saltmarsh Infrastructure Fund II", "Lowmoor & Tasker LLP (synthetic)")


def test_c1_a3_2_the_amended_july_statement_carries_the_managers_name(world):
    assert q(world, "select count(*) from documents where title = 'KR Macro Fund Ltd - Class B USD - July 2026 - Amended NAV'")[0][0] == 1


def test_c1_a3_8_the_superseded_2_oct_estimate_keeps_its_page_and_value(world):
    vid, did, fid = q(world, "select v.id, v.evidence_document_id, v.extracted_field_id from valuation_observations v join instruments i on i.id = v.instrument_id "
                             "where i.canonical_name = 'Evergreen Growth I' and v.valuation_date = date '2026-09-30' and v.supersedes_valuation_id is null")[0]
    assert did and fid
    assert q(world, "select value_numeric, page_number from extracted_fields where id = ?", str(fid))[0][0] == D("10000000")
    assert q(world, "select count(*) from documents where supersedes_document_id = ?", str(did))[0][0] == 1   # the 7 Oct amendment replaces it


def test_c1_a3_9_fund_a_amended_value_is_recorded_on_7_oct(world):
    rows = q(world, "select v.approval_status, v.recorded_at from valuation_observations v join instruments i on i.id = v.instrument_id "
                    "where i.canonical_name = 'Evergreen Growth I' and v.valuation_date = date '2026-09-30' and v.value_amount = 10180000")
    assert rows and all(r[1].date() == date(2026, 10, 7) for r in rows)


def test_c1_a4_3_the_plan_builds_the_benchmark_gold_table(world):
    plane, pid = world["plane"], world["out"]["project_id"]
    plan = read_json_strict(plane.path("build", pid, "plan-v1.json"))
    assert "gold_investment_report_benchmark_monthly" in {t["name"] for t in plan["tables"] if t["layer"] == "gold"}
    sow = read_json_strict(plane.path("intents", _project(world)["intent_id"], "sow.json"))
    assert "K04" in {k["code"] for k in sow["kpis"]}
    sep = q(world, "select benchmark_code, benchmark_return from gold_investment_report_benchmark_monthly where month = date '2026-09-01' and portfolio_code = 'EG-LIQUID'")
    assert [(c, round(float(r) * 100, 4)) for c, r in sep] == [("EG-OFFICE-BLEND", 2.7072)]


def test_c1_a6_2_calls_funded_before_october_are_not_overdue(world):
    f = K6.forecast(world["plane"], as_of, viewer=world["V"]["Daniel Foo"])
    assert all(not k["items"] for e in f["entities"] for k in e["buckets"] if k["key"] == "overdue")


def test_c1_a7_7_meetings_and_the_question_are_mei_chens(world):
    for mid in ("kestrel-ridge-advisors", "cedarpoint-ventures"):
        assert {n["by"] for n in K5.notes(world["plane"], mid) if n["kind"] in ("meeting", "question")} == {"Mei Chen"}


def test_c1_a9_0_raj_and_sofia_read_the_signed_project(world):
    from sh_platform.v1 import g1_access
    pid = _project(world)["id"]
    for name in ("Raj Patel", "Sofia Reyes"):
        assert g1_access.may_see_project(world["plane"], world["V"][name], pid) in ("read", "full")


def test_c1_a9_2_and_a9_3_the_signed_intent_reads_finished_and_sent(world):
    from sh_platform.v1 import i6_chat, t1_templates as T1
    plane, iid = world["plane"], _project(world)["intent_id"]
    assert T1.missing_required(T1.for_intent(plane, iid), T1.record_for_intent(plane, iid)) == []
    thread = read_json_strict(plane.path("intents", iid, "thread.json"))
    assert thread["state"] == "sow_ready" and thread["turns"][-1]["by"] == "north" and not thread["turns"][-1]["need"]
    assert i6_chat.sent_to_build(plane, iid)["by"] == "Daniel Foo"


def test_c1_a9_5_the_sop_speaks_plain_words_and_names_the_materiality_amount(world):
    import re
    sow = read_json_strict(world["plane"].path("intents", _project(world)["intent_id"], "sow.json"))
    words = " ".join(s["control"] + " " + s["exception"] for s in sow["process"]["steps"])
    assert not re.search(r"\b[a-z]+_[a-z_]+\b", words) and "100,000 USD" in sow["process"]["steps"][4]["exception"]


def test_c1_a10_7_and_a10_8_tiles_trace_to_bronze_and_status_note_names_four(world):
    """Gold -> silver -> bronze through the plan's lineage (intake edges checked against the catalogue), not through depends_on."""
    plane, pid = world["plane"], world["out"]["project_id"]
    from sh_platform.v1 import b6_plan
    plan = read_json_strict(plane.path("build", pid, "plan-v1.json"))
    again = b6_plan.validate(plane, plan)  # what approval re-derives must keep the intake edges, not only depends_on
    bronze = {"bronze_administrator_positions", "bronze_trading_export_positions"}
    for p in (plan, again):
        for name in ("gold_investment_report_holdings_monthly", "gold_investment_report_cash_daily"):
            up = b6_plan.upstream(p, name)
            assert "position_snapshots" in up and bronze <= up, (name, sorted(up))
            assert not bronze & set(next(t for t in p["tables"] if t["name"] == name)["depends_on"])  # depends_on stays what the SQL reads
    dash = read_json_strict(plane.path("consume", pid, "dashboards", "dash-0ad2b1c7.json"))
    assert dash["tiles"][2]["note"] == "Official, revised, estimated or unverified."


def test_c1_a5_9_answer_key_p20_matches_one_line_per_rule():
    key = (S.ROOT / "docs" / "test" / "10UC-ANSWER-KEY.md").read_text(encoding="utf-8")
    p20 = next(l for l in key.splitlines() if l.startswith("| P20 "))
    assert "0.00%" not in p20 and "4 compared" in p20


# ---- a held-back amendment -------------------------------------------------------------------------------------------------

def test_hold_amended_a_leaves_the_estimate_standing(tmp_path):
    wh.reset_cache()
    out = S.seed(tmp_path, hold_amended_a=True)
    plane = PlaneStore(tmp_path).plane_for("evergreen").ensure()
    ids, _ = S.EG.accounts(tmp_path)
    iv = O.issued_vs_known(plane, S.viewers(ids)["Daniel Foo"])
    total = next(l for l in iv["lines"] if l["label"] == "Total")
    assert "statement_A" not in out["live"] and total["issued"] == total["known_now"] == D("57600000")
    assert not [c for c in e4_cases.listing(plane, S.viewers(ids)["Grace Ong"]) if c["exception_type"] == "revision"]
    wh.reset_cache()


def test_w2_seed_signs_the_intent_on_3_oct_not_at_run_time(world):
    from sh_platform.v1 import p1_project
    p = p1_project.read(world["plane"], world["out"]["project_id"])
    sow = read_json_strict(world["plane"].path("intents", p["intent_id"], "sow.json"))
    assert sow["signature"]["at"].startswith("2026-10-03") and all(s["at"].startswith("2026-10-03") for s in sow["signatures"])
    intent = next(a for a in p1_project.read(world["plane"], p["id"])["artefacts"] if a["kind"] == "intent")
    assert (intent.get("signed_at") or "").startswith("2026-10-03")


def test_w2_validate_drops_an_intake_edge_the_catalogue_does_not_back(world):
    from sh_platform.v1 import b6_plan
    plane, pid = world["plane"], world["out"]["project_id"]
    plan = read_json_strict(plane.path("build", pid, "plan-v1.json"))
    bad = {**plan, "lineage": plan["lineage"] + [{"from": "bronze_administrator_positions", "to": "no_such_table"},
                                                 {"from": "position_snapshots", "to": "portfolios"}]}
    got = b6_plan.validate(plane, bad)["lineage"]
    assert {"from": "bronze_administrator_positions", "to": "position_snapshots"} in got
    assert not [e for e in got if e["to"] in ("no_such_table", "portfolios")]


# ---- cycle 2, package P6 (docs/test/TRIAGE-cycle-2.md): trail wording and seed --------------------------------------------------------

def _trail(world, kind, item, who="Mei Chen"):
    from sh_platform.v1 import a5_trail
    t = a5_trail.trail(world["plane"], world["V"][who], kind, item)
    return t, {s["key"]: s for s in t["steps"]}


def _val(world, fund, day):
    return str(q(world, "select v.id from valuation_observations v join instruments i on i.id = v.instrument_id where i.canonical_name = ? and v.valuation_date = ?"
                        " order by v.recorded_at desc limit 1", fund, date.fromisoformat(day))[0][0])


def test_c2_uc1_06_jucb_002_the_revision_trail_names_the_estimate_it_replaced_in_order(world):
    import re
    cid = next(c["id"] for c in cases(world, "revision") if "Evergreen Growth I" in c["title"])
    t, by = _trail(world, "case", cid)
    assert "the earlier estimate of 10,000,000 USD recorded on 2 Oct 2026" in by["stored"]["what"] and "10,180,000" not in by["stored"]["what"]
    assert "valuation observations" not in by["stored"]["what"] and "net asset value" in by["read"]["what"] and "received 7 Oct 2026" in by["file"]["what"]
    assert by["read"]["when"][:10] == "2026-10-07" and by["read"]["when"] < by["checked"]["when"]      # read on arrival, before Mei checked it
    assert not any(re.search(r"\d\. ", s["what"]) for s in t["steps"])                                  # nothing in a step reads as a step number


def test_c2_auc3_06_uc7_06_07_used_by_names_the_limit_case_and_the_office_view(world):
    _, by = _trail(world, "valuation", _val(world, "Cedarpoint Opportunities II", "2026-03-31"), "Daniel Foo")
    assert "Limit breached" in by["used_by"]["what"] and "arrives quarterly" in by["source"]["what"] and "Stale" in by["stored"]["what"]
    _, by = _trail(world, "valuation", _val(world, "Kestrel Ridge Equity Long/Short Fund", "2026-09-30"), "Daniel Foo")
    assert by["used_by"]["state"] == "done" and "Office view" in by["used_by"]["what"] and "arrives monthly" in by["source"]["what"]


def test_c2_uc6_03_a_call_case_without_its_notice_never_shows_a_valuation(world, monkeypatch):
    from sh_platform.v1 import n1_tally
    cid = next(c["id"] for c in cases(world, "capital_call"))
    monkeypatch.setattr(n1_tally, "build", lambda plane, ex: {"raw": {"call_id": None}})
    t, by = _trail(world, "case", cid, "Raj Patel")
    assert t["figure"] is None and by["file"]["state"] == "missing" and "notice" in by["file"]["what"]


def test_c2_seed_titles_classes_notes_and_labels(world):
    titles = {r[0] for r in q(world, "select title from documents")}
    assert "Evergreen Income II statement 30 Sep 2026 (final)" in titles and not any("Evergreen Liquid Book" in t for t in titles)   # UC1-C2-11
    assert "Cedarpoint Ventures III capital call notice 2 Oct 2026" in titles                                                        # UC6-07
    assert {r[0] for r in q(world, "select asset_class from instruments where instrument_type = 'fx_forward'")} == {"fx_forward"}   # UC5-C2-11
    texts = " ".join(n["text"] for n in K5.notes(world["plane"], K5.slug("Cedarpoint Ventures")) + K5.notes(world["plane"], K5.slug("Kestrel Ridge Advisors")))
    assert "Fund C" not in texts and "Fund D" not in texts and "later restated" not in texts                                       # C2-UC7-03, 04
    assert q(world, "select count(*) from source_batches where batch_reference like 'cash movements%' and position('trading_export' in batch_reference) > 0")[0][0] == 0               # analyst-uc2-09


def test_c2_uc9_07_north_names_who_signed(world):
    thread = read_json_strict(world["plane"].path("intents", _project(world)["intent_id"], "thread.json"))
    assert thread["turns"][-1]["text"].startswith("The intent of work is ready. Daniel Foo signed it") and "You signed" not in thread["turns"][-1]["text"]
