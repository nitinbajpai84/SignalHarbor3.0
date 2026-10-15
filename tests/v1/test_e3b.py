"""E3b reconciliation: the 12,400 cash break opens one case at a 5,000 tolerance; within tolerance opens none; a rerun does not duplicate;
no signed rule means no run; NAV against valuations; materiality from the signed rule. E3a and E4a are stubbed (cross-card contract)."""
import sys
import types
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e1_write as W
from sh_platform.v1 import e3_recon as R
from sh_platform.v1 import wh
from sh_platform.v1.i2_north import Refused
from tests.v1.e1_seed import seed

DAY = date(2026, 10, 8)
T = datetime(2026, 10, 8, 18, tzinfo=timezone.utc)
U = lambda n: str(uuid.uuid5(uuid.NAMESPACE_DNS, n))  # noqa: E731
RULES = {"cash_tolerance": {"rule_version_id": U("rv-tol"), "parameters": {"abs_amount": 5000, "currency": "USD"}},
         "cio_materiality": {"rule_version_id": U("rv-mat"), "parameters": {"abs_amount": 100000, "currency": "USD", "pct_of_fund": 0.5}}}


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    (tmp_path / "evergreen").mkdir()
    pl = PlaneStore(tmp_path).plane_for("evergreen")
    rules = types.SimpleNamespace(current=lambda plane, code, on: RULES.get(code) if code in rules_on else None)
    rules_on = set(RULES)
    cases = types.SimpleNamespace(opened=[])

    def open_case(plane, fields):
        cid = wh.new_id()
        cols = {"id": cid, "organization_id": W.org_id(plane), "status": "new", **fields}
        with wh.connect(plane) as con:
            con.execute(f"insert into exceptions ({', '.join(cols)}) values ({', '.join('?' * len(cols))})", list(cols.values()))
        cases.opened.append(fields)
        return cid

    cases.open = open_case
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e3_rules", rules)
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e4_cases", cases)
    with wh.connect(pl) as con:
        con.execute("insert into legal_entities (id, organization_id, entity_code, entity_name, base_currency) values (?,?,?,?,?)",
                    [U("eb"), W.org_id(pl), "B", "Entity B", "USD"])
        con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values (?,?,?,?,?,?)",
                    [U("pb"), W.org_id(pl), U("eb"), "PB", "Entity B portfolio", "USD"])
        for iid, name, typ in (("cash", "USD cash", "cash"), ("fa", "Fund A", "fund"), ("fb", "Fund B", "fund")):
            con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, created_at) values (?,?,?,?,?)",
                        [U(iid), W.org_id(pl), name, typ, T])
    seed(pl, sources=[U("sr")])
    return types.SimpleNamespace(company_id=W.org_id(pl), path=pl.path, rules_on=rules_on, cases=cases)


def cash(plane, view, amount):
    W.record(plane, "position_snapshots", {"source_record_id": U("sr"), "portfolio_id": U("pb"), "instrument_id": U("cash"), "position_date": DAY,
                                          "as_of_at": T, "received_at": T, "source_market_value": amount, "currency": "USD", "view_type": view,
                                          "data_status": "official"})


def test_the_12400_break_opens_one_case_and_a_rerun_adds_none(plane):
    cash(plane, "accounting", 5_000_000)
    cash(plane, "operational", 5_012_400)
    ids = R.run(plane, "cash_by_entity", DAY)
    assert len(ids) == 1
    f = plane.cases.opened[0]
    assert f["exception_type"] == "break" and f["candidate_impact_amount"] == 12_400 and f["impact_currency"] == "USD"
    assert f["materiality_status"] == "below_threshold" and f["materiality_rule_version_id"] == U("rv-mat") and "Entity B" in f["title"]
    assert R.run(plane, "cash_by_entity", DAY) == []                                  # an open case for the same subject and day exists
    assert len(plane.cases.opened) == 1
    last = R.last_runs(plane)
    assert [x["breaks"] for x in last] == [1, 1] and [len(x["opened"]) for x in last] == [0, 1]


def test_within_tolerance_opens_none(plane):
    cash(plane, "accounting", 1_000_000)
    cash(plane, "operational", 1_004_999)
    assert R.run(plane, "cash_by_entity", DAY) == [] and plane.cases.opened == []


def test_a_big_break_is_material_and_one_sided_cash_is_skipped(plane):
    cash(plane, "accounting", 1_000_000)
    cash(plane, "operational", 1_150_000)
    R.run(plane, "cash_by_entity", DAY)
    assert plane.cases.opened[0]["materiality_status"] == "material"
    d = R.run_detail(plane, "cash_by_entity", date(2026, 10, 9))                     # nothing reported that day
    assert d["checked"] == 0 and d["opened"] == []


def test_no_signed_tolerance_means_no_run(plane):
    plane.rules_on.discard("cash_tolerance")
    cash(plane, "accounting", 1)
    with pytest.raises(Refused) as e:
        R.run(plane, "cash_by_entity", DAY)
    assert "No signed cash tolerance" in e.value.message and R.last_runs(plane) == []
    with pytest.raises(Refused):
        R.run(plane, "nope", DAY)


def test_a_revised_cash_row_is_read_as_known(plane):
    cash(plane, "accounting", 1_000_000)
    cash(plane, "operational", 1_012_400)
    with wh.connect(plane, read_only=True) as con:
        old = con.execute("select id from position_snapshots where view_type = 'operational'").fetchone()[0]
    W.record(plane, "position_snapshots", {"source_record_id": U("sr"), "portfolio_id": U("pb"), "instrument_id": U("cash"), "position_date": DAY,
                                          "as_of_at": T, "received_at": T, "source_market_value": 1_001_000, "currency": "USD",
                                          "view_type": "operational", "data_status": "official"}, supersedes_id=str(old))
    assert R.run(plane, "cash_by_entity", DAY) == []                                  # now within tolerance
    assert len(R.run(plane, "cash_by_entity", DAY, cutoff=datetime(2026, 1, 1, tzinfo=timezone.utc))) == 0   # nothing was known then


def test_nav_against_investment_valuations(plane):
    W.record(plane, "nav_snapshots", {"portfolio_id": U("pb"), "source_record_id": U("sr"), "nav_period_end": DAY, "received_at": T,
                                      "nav_amount": 16_400_000, "currency": "USD", "nav_status": "approved_official"})
    for inst, amt in (("fa", 10_000_000), ("fb", 6_300_000)):
        W.record(plane, "valuation_observations", {"instrument_id": U(inst), "portfolio_id": U("pb"), "valuation_date": date(2026, 9, 30), "received_at": T,
                                                    "value_amount": amt, "currency": "USD", "valuation_type": "manager_estimate", "approval_status": "draft"})
    ids = R.run(plane, "nav_vs_investment", DAY)
    assert len(ids) == 1 and plane.cases.opened[0]["candidate_impact_amount"] == 100_000
    assert R.run(plane, "nav_vs_investment", DAY) == []


def test_materiality_percent_of_fund_fires(plane):
    cash(plane, "accounting", 100_000)
    cash(plane, "operational", 112_400)  # over the 5,000 tolerance, under 100,000, but 12.4% of the figure
    R.run(plane, "cash_by_entity", DAY)
    assert plane.cases.opened[0]["materiality_status"] == "material"


# ---- K6: limits (UC5) --------------------------------------------------------------------------------------------------------------

LIMIT = {"rule_version_id": U("rv-lim"), "parameters": {"dimension": "asset_class", "bucket": "private equity", "min_pct": 0, "max_pct": 30}}


def limit_setup(plane, pe_date=date(2026, 9, 30), pe_status="confirmed"):
    RULES["limit_pe"] = LIMIT
    plane.rules_on.add("limit_pe")
    with wh.connect(plane) as con:
        con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, is_active, created_at) values (?,?,?,?,?,?,?)",
                    [U("owner"), plane.company_id, "o", "Owner", "", True, T])
        con.execute("insert into business_rules (id, organization_id, rule_code, rule_type, owner_user_id) values (?,?,?,?,?)",
                    [U("br"), plane.company_id, "limit_pe", "limit", U("owner")])
        con.execute("update instruments set asset_class = 'Private Equity' where id = ?", [U("fa")])
        con.execute("update instruments set asset_class = 'listed equity' where id = ?", [U("fb")])
    for inst, amt, d, st in (("fa", 4_000_000, pe_date, pe_status), ("fb", 6_000_000, date(2026, 9, 30), "confirmed")):
        W.record(plane, "valuation_observations", {"instrument_id": U(inst), "portfolio_id": U("pb"), "valuation_date": d, "received_at": T,
                                                    "value_amount": amt, "currency": "USD", "valuation_type": "manager_final", "approval_status": st})


@pytest.fixture(autouse=True)
def _clean_rules():
    yield
    RULES.pop("limit_pe", None)


def test_a_real_limit_breach_opens_a_typed_case_once(plane):
    limit_setup(plane)
    d = R.run_detail(plane, "limits", DAY)
    f = plane.cases.opened[0]
    assert d["breaks"] == 1 and len(d["opened"]) == 1 and f["exception_type"] == "limit_breach"
    assert d["causes"][0]["cause"] == "real breach" and "Cause: real breach" in f["description"] and "40.00%" in f["description"]
    assert f["candidate_impact_amount"] == 1_000_000 and "Entity B portfolio" in f["title"] and "Limit breached · Private Equity ·" in f["title"]
    assert d["rule_words"] == ["The private equity share of each portfolio must be at most 30%."]          # a5.7: a minimum of 0 is no minimum
    assert d["results"] == [{"rule_code": "limit_pe", "portfolio": "Entity B portfolio", "bucket": "private equity", "exposure_pct": "40.00", "breached": True, "max_pct": "30", "headroom_pts": "-10.00",
                             "words": "Private Equity, Entity B portfolio: 4,000,000 USD = 40.00% against a maximum of 30%.", "case_id": d["opened"][0],
                             "cause": "real breach", "over_by": "1000000.00"}]                                  # UC5-C2-01: why and by how much
    assert f["title"].endswith(" · 8 Oct 2026") and "above the signed maximum of 30%" in f["description"]      # UC5-C2-08, UC5-C2-10
    assert R.run(plane, "limits", DAY) == [] and len(plane.cases.opened) == 1


def test_an_old_valuation_makes_it_a_stale_data_breach(plane):
    limit_setup(plane, pe_date=date(2026, 5, 1))
    assert R.run_detail(plane, "limits", DAY)["causes"][0]["cause"] == "stale data"
    assert "Cause: stale data" in plane.cases.opened[0]["description"]


def test_an_unverified_valuation_is_stale_data_too(plane):
    limit_setup(plane, pe_status="proposed")
    assert R.run_detail(plane, "limits", DAY)["causes"][0]["cause"] == "stale data"


def test_a_pending_valuation_is_stale_data_too(plane):
    limit_setup(plane, pe_status="pending")
    assert R.run_detail(plane, "limits", DAY)["causes"][0]["cause"] == "stale data"


def test_a_holding_without_a_class_is_a_question_and_opens_no_case(plane):
    limit_setup(plane)
    RULES["limit_pe"] = dict(LIMIT, parameters={**LIMIT["parameters"], "max_pct": 45})
    with wh.connect(plane) as con:
        con.execute("update instruments set asset_class = null where id = ?", [U("fb")])
    d = R.run_detail(plane, "limits", DAY)
    assert d["breaks"] == 0 and plane.cases.opened == [] and d["causes"] == []
    assert d["questions"][0]["status"] == "Needs a class" and d["questions"][0]["instrument"] == "Fund B" and d["questions"][0]["exposure_pct"] == "60.00"


def test_staleness_is_judged_on_the_run_date_not_the_checked_day(plane):
    limit_setup(plane, pe_date=date(2026, 7, 1))   # 1 day old on the checked day, over 90 days old on the run date
    d = R.run_detail(plane, "limits", date(2026, 7, 2))
    assert d["stale_as_of"] == wh.now().date().isoformat() and d["causes"][0]["cause"] == "stale data"


def test_inside_the_limit_opens_nothing_and_a_missing_limit_refuses(plane):
    limit_setup(plane)
    RULES["limit_pe"] = dict(LIMIT, parameters={**LIMIT["parameters"], "max_pct": 45})
    d = R.run_detail(plane, "limits", DAY)
    assert d["breaks"] == 0 and d["checked"] == 1 and plane.cases.opened == []
    plane.rules_on.discard("limit_pe")
    with pytest.raises(Refused) as e:
        R.run(plane, "limits", DAY)
    assert "No signed limit" in e.value.message


def test_a_minimum_not_reached_is_a_breach(plane):
    limit_setup(plane)
    RULES["limit_pe"] = dict(LIMIT, parameters={"dimension": "asset_class", "bucket": "hedge fund", "min_pct": 5, "max_pct": 20})
    d = R.run_detail(plane, "limits", DAY)
    assert d["breaks"] == 1 and "below the signed minimum of 5%" in plane.cases.opened[0]["description"]


def test_a_single_name_limit_names_the_holding(plane):
    limit_setup(plane)
    RULES["limit_pe"] = dict(LIMIT, parameters={"dimension": "single_name", "bucket": "*", "max_pct": 50})
    d = R.run_detail(plane, "limits", DAY)
    assert d["breaks"] == 1 and "Fund B" in plane.cases.opened[0]["title"] and plane.cases.opened[0]["instrument_id"] == U("fb")


# ---- K6: trade_vs_admin (UC8) ------------------------------------------------------------------------------------------------------

def trade_setup(plane):
    with wh.connect(plane) as con:
        for tag, typ in (("oms", "OMS"), ("adm", "administrator")):
            con.execute("insert into source_systems (id, organization_id, source_code, source_name, source_type, is_active) values (?,?,?,?,?,?)",
                        [U("sys" + tag), plane.company_id, tag, tag, typ, True])
            con.execute("insert into source_batches (id, organization_id, source_system_id, batch_reference, received_at, validation_status) values (?,?,?,?,?,?)",
                        [U("bat" + tag), plane.company_id, U("sys" + tag), tag, T, "loaded"])
            con.execute("insert into source_records (id, organization_id, source_batch_id, record_type, received_at, recorded_at, raw_payload_uri, content_hash, quality_status)"
                        " values (?,?,?,?,?,?,?,?,?)", [U("rec" + tag), plane.company_id, U("bat" + tag), "trade", T, T, "x", "h", "ok"])


def trade(plane, side, trade_id, inst, amount, day=DAY, ccy="USD"):
    W.record(plane, "transactions", {"source_record_id": U("rec" + side), "portfolio_id": U("pb"), "instrument_id": U(inst), "external_trade_id": trade_id,
                                    "transaction_type": "buy", "trade_date": day, "effective_date": day, "cash_amount": amount, "currency": ccy, "status": "confirmed"})


def test_trades_match_by_id_or_by_instrument_date_and_amount(plane):
    trade_setup(plane)
    trade(plane, "oms", "T1", "fa", 100_000)
    trade(plane, "adm", "T1", "fa", 101_000)                      # same id, within the 5,000 tolerance
    trade(plane, "oms", "T2", "fb", 250_000)
    trade(plane, "adm", None, "fb", 252_500)                      # no id on the administrator side: matched on instrument, date and amount
    d = R.run_detail(plane, "trade_vs_admin", DAY)
    assert d["breaks"] == 0 and d["opened"] == [] and d["checked"] == 4 and d["matched"] == 2     # a8.0: records compared, not records left over
    assert d["rule_words"] and "5,000 USD" in d["rule_words"][0] and d["tolerance_rule_version_id"] == U("rv-tol")


def test_a_different_amount_and_unmatched_trades_open_break_cases_once(plane):
    trade_setup(plane)
    trade(plane, "oms", "T1", "fa", 100_000)
    trade(plane, "adm", "T1", "fa", 112_000)                      # 12,000 apart
    trade(plane, "oms", "T2", "fb", 50_000)                       # nobody at the administrator
    trade(plane, "adm", "T3", "fb", 70_000)                       # nobody in the trading export
    d = R.run_detail(plane, "trade_vs_admin", DAY)
    titles = sorted(f["title"] for f in plane.cases.opened)
    assert d["breaks"] == 3 and len(d["opened"]) == 3 and all(f["exception_type"] == "break" for f in plane.cases.opened)
    assert [t.split(" · ")[0] for t in titles] == ["Trade differs", "Trade not matched", "Trade not matched"]
    assert R.run(plane, "trade_vs_admin", DAY) == []


def test_old_trades_are_outside_the_window_and_no_tolerance_refuses(plane):
    trade_setup(plane)
    trade(plane, "oms", "OLD", "fa", 1, day=date(2026, 8, 1))
    assert R.run_detail(plane, "trade_vs_admin", DAY)["checked"] == 0
    plane.rules_on.discard("cash_tolerance")
    with pytest.raises(Refused):
        R.run(plane, "trade_vs_admin", DAY)


def test_a_limit_rule_can_name_one_portfolio(plane):
    limit_setup(plane)
    RULES["limit_pe"] = dict(LIMIT, parameters={**LIMIT["parameters"], "portfolio_code": "NO-SUCH"})
    assert R.run_detail(plane, "limits", DAY)["breaks"] == 0


# ---- cycle 1 fixes (P3) ------------------------------------------------------------------------------------------------------------

def test_a5_1_bucket_any_tests_every_holding(plane):
    limit_setup(plane)
    RULES["limit_pe"] = dict(LIMIT, parameters={"dimension": "single_name", "bucket": "any", "min_pct": 0, "max_pct": 50})
    d = R.run_detail(plane, "limits", DAY)
    assert {r["bucket"] for r in d["results"]} == {"fund a", "fund b"} and d["breaks"] == 1 and "Fund B" in plane.cases.opened[0]["title"]
    assert d["rule_words"] == ["Any single holding of each portfolio must be at most 50% of it."]


def test_a5_6_a5_7_limit_words_name_the_portfolio_and_read_plainly(plane):
    limit_setup(plane)
    RULES["limit_pe"] = dict(LIMIT, parameters={"dimension": "asset_class", "bucket": "listed_equity", "min_pct": 60, "max_pct": 90, "portfolio_code": "PB"})
    with wh.connect(plane) as con:
        con.execute("update instruments set asset_class = 'listed_equity' where id = ?", [U("fb")])
    d = R.run_detail(plane, "limits", DAY)
    assert d["rule_words"] == ["The listed equity share of the Entity B portfolio must be between 60% and 90%."]
    assert d["results"][0]["words"] == "Listed equity, Entity B portfolio: 6,000,000 USD = 60.00% against a maximum of 90%."


def test_a5_4_stale_cause_names_the_inputs(plane):
    limit_setup(plane, pe_date=date(2026, 5, 1))
    with wh.connect(plane) as con:
        con.execute("update valuation_observations set approval_status = 'proposed' where instrument_id = ?", [U("fb")])
    R.run_detail(plane, "limits", DAY)
    desc = plane.cases.opened[0]["description"]
    assert "2 input values are older than 90 days or not yet verified" in desc
    assert "Fund A valued 1 May 2026 (" in desc and "Fund B 6,000,000 USD not yet verified" in desc


def test_a5_5_a2_2_a_rerun_still_points_at_the_open_cases(plane):
    cash(plane, "accounting", 880_400)
    cash(plane, "operational", 868_000)
    first = R.run_detail(plane, "cash_by_entity", DAY)
    again = R.run_detail(plane, "cash_by_entity", DAY)
    assert again["opened"] == [] and again["results"] == [{"subject": "Cash differs · Entity B · 2026-10-08", "breached": True, "case_id": first["opened"][0],
        "words": "Entity B cash, administrator against trading export: 880,400 against 868,000 USD, a difference of 12,400 USD."}]
    limit_setup(plane)
    lim = R.run_detail(plane, "limits", DAY)
    assert R.run_detail(plane, "limits", DAY)["results"][0]["case_id"] == lim["opened"][0]


def test_a2_0_a_day_with_no_files_says_there_was_nothing_to_compare(plane):
    d = R.run_detail(plane, "cash_by_entity", date(2026, 10, 9))
    assert d["checked"] == 0 and d["skipped"] and "nothing to compare" in d["skipped"][0]


def test_a8_4_a8_6_a8_3_trade_words_lists_and_fx_size(plane):
    trade_setup(plane)
    W.record(plane, "transactions", {"source_record_id": U("recoms"), "portfolio_id": U("pb"), "instrument_id": U("fa"), "external_trade_id": "T1",
                                    "transaction_type": "buy", "trade_date": DAY, "effective_date": DAY, "quantity_delta": 12000, "cash_amount": -505_800,
                                    "currency": "USD", "status": "confirmed"})
    W.record(plane, "transactions", {"source_record_id": U("recadm"), "portfolio_id": U("pb"), "instrument_id": U("fa"), "external_trade_id": "T1",
                                    "transaction_type": "buy", "trade_date": DAY, "effective_date": DAY, "quantity_delta": 10200, "cash_amount": -429_930,
                                    "currency": "USD", "status": "confirmed"})
    trade(plane, "oms", "T2", "fb", 1_000)
    trade(plane, "adm", "T2", "fb", 1_000)
    d = R.run_detail(plane, "trade_vs_admin", DAY)
    text = plane.cases.opened[0]["description"]
    assert text == ("Trading export buy 12,000 at 42.15 = 505,800 USD; administrator buy 10,200 at 42.15 = 429,930 USD; "
                    "a difference of 75,870 USD, 1,800 in quantity.")
    assert [(r["breached"], bool(r.get("case_id"))) for r in d["results"]] == [(True, True), (False, False)] and "matched" in d["results"][1]["words"]
    assert d["checked"] == 4 and d["matched"] == 1


def test_a8_3_a_break_in_another_currency_shows_the_tolerance_currency(plane, monkeypatch):
    trade_setup(plane)
    trade(plane, "oms", "F1", "fa", 4_027_500, ccy="SGD")
    trade(plane, "adm", "F1", "fa", 4_035_600, ccy="SGD")
    import sh_platform.v1.e3_calc as calc
    monkeypatch.setattr(calc, "fx", lambda plane, frm, to, on, cutoff: Decimal("1") / Decimal("1.3388") if (frm, to) == ("SGD", "USD") else None)
    R.run_detail(plane, "trade_vs_admin", DAY)
    assert "8,100 SGD (6,050.19 USD at the signed rate, against the 5,000 USD allowance)" in plane.cases.opened[0]["description"]


def test_a8_5_a_break_that_comes_back_names_the_resolved_case(plane):
    trade_setup(plane)
    trade(plane, "oms", "T2", "fb", 50_000)
    first = R.run_detail(plane, "trade_vs_admin", DAY)["opened"][0]
    with wh.connect(plane) as con:
        con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, is_active, created_at) values (?,?,?,?,?,?,?)",
                    [U("raj"), plane.company_id, "r", "Raj Patel", "", True, T])
        con.execute("update exceptions set status = 'resolved', resolved_at = ? where id = ?", [datetime(2026, 10, 8, 6, tzinfo=timezone.utc), first])
        for typ, note, by in (("opened", "CASE-0005", None), ("resolved", "ok", U("raj"))):
            con.execute("insert into exception_events (id, organization_id, exception_id, event_type, event_note, performed_by_user_id, occurred_at) values (?,?,?,?,?,?,?)",
                        [wh.new_id(), plane.company_id, first, typ, note, by, T])
        con.execute("update exceptions set candidate_impact_amount = 40000 where id = ?", [first])   # the earlier break was a different size
    R.run_detail(plane, "trade_vs_admin", DAY)
    assert "This follows CASE-0005, resolved on 8 Oct 2026 by Raj Patel" in plane.cases.opened[1]["description"]


def test_uc2_03_a_resolved_break_of_the_same_size_is_not_opened_again(plane):
    cash(plane, "accounting", 880_400)
    cash(plane, "operational", 868_000)
    first = R.run_detail(plane, "cash_by_entity", DAY)["opened"][0]
    with wh.connect(plane) as con:
        con.execute("update exceptions set status = 'resolved', resolved_at = ? where id = ?", [T, first])
    again = R.run_detail(plane, "cash_by_entity", DAY)
    assert again["opened"] == [] and again["results"][0]["case_id"] == first and len(plane.cases.opened) == 1


def test_uc2_02_a_read_only_group_cannot_run_a_check(monkeypatch):
    from sh_platform.profile.view import Viewer
    from sh_platform.v1 import e1_access, e3b_routes
    monkeypatch.setattr(e1_access, "visible_portfolios", lambda plane, v: {"p1", "p2"})
    monkeypatch.setattr(e1_access, "level", lambda plane, v, entity_id=None, portfolio_id=None: "full" if v.name == "Mei" and portfolio_id == "p2" else "read")
    assert e3b_routes._may_run(None, Viewer("Mei", frozenset({"analyst"}), False, "a-mei"))
    assert e3b_routes._may_run(None, Viewer("Anita", frozenset({"analyst"}), False, "a-anita"))  # FIXE1: the data team runs checks
    assert not e3b_routes._may_run(None, Viewer("Rina", frozenset({"owner"}), False, "a-rina"))  # a read-only person still cannot
    assert e3b_routes._may_run(None, Viewer("Grace", frozenset({"company_admin"}), False, "a-g"))


def test_limit_basis_positions_and_statements(plane):
    """UC5 G-2: the administrator's month-end positions count; on the same date a fund keeps its manager's statement, a security the
    administrator's value; a later date wins; an administrator estimate is flagged on the line."""
    limit_setup(plane)
    later = date(2026, 10, 31)
    W.record(plane, "position_snapshots", {"source_record_id": U("sr"), "portfolio_id": U("pb"), "instrument_id": U("fa"), "position_date": date(2026, 9, 30),
                                           "as_of_at": T, "received_at": T, "source_market_value": 9_000_000, "currency": "USD", "view_type": "operational",
                                           "data_status": "official"})
    d = R.run_detail(plane, "limits", DAY)
    assert d["results"][0]["exposure_pct"] == "40.00"     # same date as the statement: the fund keeps the statement (4,000,000)
    W.record(plane, "position_snapshots", {"source_record_id": U("sr"), "portfolio_id": U("pb"), "instrument_id": U("fb"), "position_date": later,
                                           "as_of_at": T, "received_at": T, "source_market_value": 16_000_000, "currency": "USD", "view_type": "operational",
                                           "data_status": "official"})
    W.record(plane, "position_snapshots", {"source_record_id": U("sr"), "portfolio_id": U("pb"), "instrument_id": U("fa"), "position_date": later,
                                           "as_of_at": T, "received_at": T, "source_market_value": 4_000_000, "currency": "USD", "view_type": "operational",
                                           "data_status": "estimate"})
    d = R.run_detail(plane, "limits", later)
    res = d["results"][0]
    assert res["exposure_pct"] == "20.00" and res["estimates"] and "Uses estimates" in res["words"]   # 4m of 20m, the later dated values


def test_limit_lines_go_to_the_limit_results_table_when_the_model_has_it(plane, monkeypatch):
    """UC5 G-1: with an approved `limit_results` table, a limits run writes its lines there (a rerun for the day replaces them)."""
    limit_setup(plane)
    with wh.connect(plane) as con:
        con.execute("create table limit_results (id varchar, as_of_date date, portfolio varchar, rule_code varchar, exposure_pct decimal(9,2), result varchar, cause varchar)")
    from sh_platform.v1 import e0a_catalogue
    monkeypatch.setattr(e0a_catalogue, "columns_of", lambda plane, t: ["id", "as_of_date", "portfolio", "rule_code", "exposure_pct", "result", "cause"] if t == "limit_results" else None)
    R.run_detail(plane, "limits", DAY)
    R.run_detail(plane, "limits", DAY)
    with wh.connect(plane) as con:
        rows = con.execute("select rule_code, exposure_pct, result, cause from limit_results").fetchall()
    assert rows == [("limit_pe", Decimal("40.00"), "breach", "real breach")]


def test_a_standing_breach_keeps_one_case_with_each_month_in_its_history(plane):
    """UC5: the same stale breach opened a new case every month; while its case is open, a later month is written in that case."""
    limit_setup(plane)
    notes = []
    plane.cases._set = lambda con, cid, **cols: con.execute(f"update exceptions set {', '.join(k + ' = ?' for k in cols)} where id = ?", [*cols.values(), cid])
    plane.cases._event = lambda con, pl, cid, by, kind, text: notes.append((cid, kind, text))
    first = R.run_detail(plane, "limits", DAY)
    later = R.run_detail(plane, "limits", date(2026, 10, 31))
    assert len(first["opened"]) == 1 and later["opened"] == [] and len(plane.cases.opened) == 1
    assert later["results"][0]["case_id"] == first["opened"][0]
    assert notes and notes[-1][0] == first["opened"][0] and notes[-1][2].startswith("Still in breach at 31 Oct 2026: 40.00%")


def test_a_file_received_before_the_cutoff_counts_even_if_loaded_later(plane):
    """UC5: 'Files received by 2 Oct' must see a file that arrived on 2 Oct and was loaded on 9 Oct."""
    limit_setup(plane)
    arrived, cut = T, datetime(2026, 10, 8, 19, tzinfo=timezone.utc)   # arrived with the others; recorded only when this test runs, after the cutoff
    W.record(plane, "valuation_observations", {"instrument_id": U("fb"), "portfolio_id": U("pb"), "valuation_date": DAY, "received_at": arrived,
                                                "value_amount": 16_000_000, "currency": "USD", "valuation_type": "manager_final", "approval_status": "confirmed"})
    res = R.run_detail(plane, "limits", DAY, cut)["results"][0]
    assert res["exposure_pct"] == "20.00"      # 4m of 20m: the 16m value counts though it was recorded after the cutoff


def test_a_breach_never_joins_an_open_case_of_a_later_day(plane):
    """UC5: a September breach was added to an open case dated 9 Oct; only an earlier month's open case is continued."""
    limit_setup(plane)
    later = R.run_detail(plane, "limits", date(2026, 10, 31))
    earlier = R.run_detail(plane, "limits", DAY)
    assert len(later["opened"]) == 1 and len(earlier["opened"]) == 1 and earlier["opened"] != later["opened"]
