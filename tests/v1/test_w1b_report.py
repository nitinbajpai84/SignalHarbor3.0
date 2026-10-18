"""W1b report (cards 51 to 100 of the Report and govern domain: 74 and 75), proved on the real pack readers.

Result: card 74 (the board pack) is built: recipe `board_summary`, three signals, one build. Card 75 (the net worth walk) is built: recipe `networth_walk`, three
signals, one build; the opening net worth uses the 31 March USD/SGD fixing (filed with April), and its income is short by one bank statement that never
arrived (M02b), which the balancing item takes up. The office files are loaded through the
real loader (tests/v1/test_w2_loader.py); every expected number comes from tests/v1/fixtures/office6m/answer_keys.yaml, never typed here. Synthetic data only."""
from __future__ import annotations

import glob
import importlib.util
import re
from pathlib import Path

import pytest
import yaml

from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import v3_signals as SG

_SPEC = importlib.util.spec_from_file_location("w2_loader_tests", Path(__file__).with_name("test_w2_loader.py"))
W2 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(W2)
key, f2, OFFICE = W2.key, W2.f2, W2.OFFICE
office = W2.office  # the module fixture: the office files loaded through the real readers

PACK = Path(__file__).resolve().parents[2] / "packs" / "family_office" / "1"
CARDS = ["uc-074-boardpack", "uc-075-yearwalk"]
SIBLINGS = ["report_total_fx", "time_weighted_return", "cash_by_bank", "cash_after_calls", "called_to_date", "amendments_open"]


# ---- the recipe ------------------------------------------------------------------------------------------------------------------------------

def test_the_report_cards_after_the_top_50_are_74_and_75_and_both_are_built():
    cards = [c["id"] for c in yaml.safe_load((PACK / "use_cases_100.yaml").read_text(encoding="utf-8"))["use_cases"] if c["domain"] == "Report and govern" and not c.get("priority")]
    assert sorted(cards) == ["uc-074-boardpack", "uc-075-yearwalk"]
    assert R.recipe("board_summary") is not None and R.recipe("board_summary")["cards"] == [74]
    assert R.recipe("networth_walk") is not None and R.recipe("networth_walk")["cards"] == [75] and not any(r["id"] == "networth_walk" for r in R.stubs())


def test_card_74_the_headline_figures_are_the_key(office):
    k, rows = key("uc-074-boardpack"), office.run("board_summary")  # run() also checks the A8 tables and the tie-out
    assert len(rows) == 1
    r = rows[0]
    assert (f2(r["net_worth_usd"]), f2(r["net_worth_sgd"])) == (k["net_worth_usd"], k["net_worth_sgd"])
    assert r["estimate_note"] == k["net_worth_status"] and r["net_worth_status"] == "estimated" and r["estimated_lines"] == 1
    assert (float(r["last_quarter_return_pct"]), r["last_quarter"], r["portfolio"]) == (k["liquid_book_q3_return_pct"], "2026Q3", "Evergreen Liquid Book")
    assert float(r["since_start_benchmark_pct"]) == k["benchmark_since_1_apr_pct"] and str(r["performance_from"]) == "2026-03-31" and str(r["performance_to"]) == "2026-09-30"
    assert f2(r["cash_usd_eq"]) == k["cash_usd_eq"] and r["cash_unconverted_accounts"] == 0
    assert f2(r["call_shortfall_usd"]) == k["call_7_shortfall_usd"] and r["call_entities_unmeasured"] == 0
    assert f2(r["uncalled_commitments_usd"]) == k["uncalled_commitments"] and r["uncalled_other_currency"] == 0
    assert r["amendments_after_report"] == k["statements_amended_after_last_report"]


def test_card_74_figure_binds_to_board_summary_not_net_worth():
    """The card's figure is named "Net worth, return, liquidity, decisions"; by name alone it bound to net_worth (scored FAIL). It must bind to board_summary."""
    card = next(c for c in yaml.safe_load((PACK / "use_cases_100.yaml").read_text(encoding="utf-8"))["use_cases"] if c["id"] == "uc-074-boardpack")
    assert [(R.match(f) or {}).get("id") for f in card["figures"]] == ["board_summary"]
    assert (R.match({"name": "Net worth"}) or {}).get("id") == "net_worth"  # plain net worth still binds where it did


def test_the_board_figures_equal_the_recipes_that_own_them(office):
    """The board recipe holds a copy of each sibling's SQL (a recipe cannot read another recipe's table). If a sibling changes and the copy does not, this fails."""
    b = office.run("board_summary")[0]
    sib = {rid: office.run(rid) for rid in SIBLINGS}
    tot = sib["report_total_fx"][0]
    assert (b["net_worth_usd"], b["net_worth_sgd"], b["usd_sgd_fixing"], b["issued_on"]) == (tot["total_usd"], tot["total_sgd"], tot["usd_sgd_fixing"], tot["issued_on"])
    pick = lambda kind: next(x for x in sib["time_weighted_return"] if x["portfolio"] == b["portfolio"] and x["period_kind"] == kind and (kind == "all" or x["period_label"] == b["last_quarter"]))
    assert (b["last_quarter_return_pct"], b["last_quarter_benchmark_pct"]) == (pick("quarter")["portfolio_return_pct"], pick("quarter")["benchmark_return_pct"])
    assert (b["since_start_return_pct"], b["since_start_benchmark_pct"]) == (pick("all")["portfolio_return_pct"], pick("all")["benchmark_return_pct"])
    assert b["cash_usd_eq"] == sum(x["usd_equivalent"] for x in sib["cash_by_bank"])
    assert b["call_shortfall_usd"] == sum(x["shortfall"] for x in sib["cash_after_calls"] if x["calls_due"] > 0)
    assert b["uncalled_commitments_usd"] == sum(x["unfunded_after_notice"] for x in sib["called_to_date"] if x["currency"] == "USD")
    assert b["amendments_after_report"] == sum(x["open_amendments"] for x in sib["amendments_open"])


def test_without_a_signed_buffer_the_shortfall_is_empty_not_zero(office):
    con = office.con
    con.execute("begin")
    try:
        con.execute("delete from rule_versions where business_rule_id in (select id from business_rules where rule_code = 'cash_buffer')")
        r = office.run("board_summary")[0]
        assert r["call_shortfall_usd"] is None and r["call_entities_unmeasured"] >= 1
        assert f2(r["cash_usd_eq"]) == key("uc-074-boardpack")["cash_usd_eq"]  # the other figures stand
    finally:
        con.execute("rollback")
    assert f2(office.run("board_summary")[0]["call_shortfall_usd"]) == key("uc-074-boardpack")["call_7_shortfall_usd"]


def test_without_a_signed_benchmark_link_the_board_has_no_return_but_keeps_the_rest(office):
    con = office.con
    con.execute("begin")
    try:
        con.execute("delete from rule_versions where business_rule_id in (select id from business_rules where rule_code = 'benchmark_link')")
        r = office.run("board_summary")[0]
        assert r["last_quarter_return_pct"] is None and r["since_start_benchmark_pct"] is None and r["portfolio"] is None
        assert f2(r["net_worth_usd"]) == key("uc-074-boardpack")["net_worth_usd"]
    finally:
        con.execute("rollback")


# ---- the signals ------------------------------------------------------------------------------------------------------------------------------

def signals(card: str) -> dict[str, dict]:
    out = {}
    for p in sorted((PACK / "signals").glob(f"{card}-*.yaml")):
        s = yaml.safe_load(p.read_text(encoding="utf-8"))
        s["trigger"] = {("on" if k is True else k): v for k, v in s["trigger"].items()}  # YAML 1.1 reads a bare `on` as true
        out[s["id"]] = s
    return out


def fire(sig: dict, doc: dict):
    """Evaluate a signal the way the engine does: every declared field must be there, then the condition, then the message (None = skipped, False = quiet)."""
    funcs = {"abs": abs, "min": min, "max": max, "round": round, "last4": SG.last4, "num": SG.num}
    declared = next(i["fields"] for i in sig["inputs"] if i["kind"] == "doc")
    ns = {"doc": {}}
    for f in declared:
        if doc.get(f) in (None, ""):
            return None
        ns["doc"][f] = SG._dec(doc[f])
    hit = bool(SG.calc(sig["condition"], ns, funcs))
    return SG.render(sig["message"], ns) if hit else False


def test_card_74_has_three_signals_one_exception_with_a_hold_and_roles_that_exist():
    role_ids = {r["id"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"]}
    sg = signals("uc-074-boardpack")
    assert len(sg) == 3
    for sid, s in sg.items():
        assert SG.check(s, {r: r for r in role_ids}) is None, (sid, SG.check(s, {r: r for r in role_ids}))
        assert s["id"].startswith("uc-074-boardpack-") and s.get("suggestion") is True and s["route_to"] in role_ids
        declared = set(next(i["fields"] for i in s["inputs"] if i["kind"] == "doc"))
        used = set(re.findall(r"doc\.([A-Za-z_]\w*)", " ".join([s["condition"], s["message"], s["subject"], str((s.get("hold") or {}).get("scope", ""))])))
        assert used == declared, (sid, used ^ declared)
    exc = [s for s in sg.values() if s["severity"] == "problem"]
    assert len(exc) == 1 and exc[0]["hold"]["blocks"] == "issue_board_pack" and exc[0]["hold"]["until"]
    assert all(not s.get("hold") for s in sg.values() if s is not exc[0])


def test_card_74_signals_fire_on_the_office_data(office):
    sg, row = signals("uc-074-boardpack"), office.run("board_summary")[0]
    head = fire(sg["uc-074-boardpack-headline"], row)
    assert "USD 57,600,000 (SGD 77,253,120)" in head and "3.5148 percent last quarter" in head and "5.7563 for the benchmark" in head and "USD 6,156,041.41" in head
    assert "Evergreen Growth I is an estimate in the issued report" in fire(sg["uc-074-boardpack-estimate"], row)
    held = fire(sg["uc-074-boardpack-amended"], row)
    assert "1 statement(s) were amended after the report of 2026-09-30 was issued on 2026-10-03" in held and "The board page is held" in held


def test_card_74_signals_stay_quiet_or_skip_when_they_should(office):
    sg, row = signals("uc-074-boardpack"), office.run("board_summary")[0]
    assert fire(sg["uc-074-boardpack-amended"], {**row, "amendments_after_report": 0}) is False
    assert fire(sg["uc-074-boardpack-estimate"], {**row, "estimated_lines": 0}) is False
    assert fire(sg["uc-074-boardpack-headline"], {**row, "cash_usd_eq": None}) is None  # a figure that is not there is skipped, never guessed


# ---- the build --------------------------------------------------------------------------------------------------------------------------------

def test_card_74_has_one_build_with_the_keys_files_and_numbers():
    base = {b["id"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"] for b in r["builds"]}
    mine = yaml.safe_load((PACK / "builds" / "report-51.yaml").read_text(encoding="utf-8"))["roles"]
    builds = {b["id"]: (r["id"], b) for r in mine for b in r["builds"]}
    assert set(builds) == set(CARDS) and not set(builds) & base
    keys = yaml.safe_load((OFFICE / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]
    owners = {c["id"]: c["owner"] for c in yaml.safe_load((PACK / "use_cases_100.yaml").read_text(encoding="utf-8"))["use_cases"]}
    role, b = builds["uc-074-boardpack"]
    assert role == owners["uc-074-boardpack"] == "principal" and b["say"].strip() and b["check"]["ask"].endswith("?") and b["skills"] and b["dashboard"]
    assert b["files"] == ["office6m:" + f for f in keys["uc-074-boardpack"]["input_files"]]
    assert all(glob.glob(str(OFFICE / f[len("office6m:"):])) for f in b["files"])
    k = key("uc-074-boardpack")
    want = {f"{k['net_worth_usd']:,}", f"{k['net_worth_sgd']:,}", str(k["liquid_book_q3_return_pct"]), str(k["benchmark_since_1_apr_pct"]), f"{k['cash_usd_eq']:,.2f}", f"{k['call_7_shortfall_usd']:,}", f"{k['uncalled_commitments']:,}"}
    assert set(b["check"]["expect"]) == want
    role, b = builds["uc-075-yearwalk"]
    assert role == owners["uc-075-yearwalk"] == "principal" and b["say"].strip() and b["check"]["ask"].endswith("?") and b["skills"] and b["dashboard"]
    assert b["files"] == ["office6m:" + f for f in keys["uc-075-yearwalk"]["input_files"]]
    assert all(glob.glob(str(OFFICE / f[len("office6m:"):])) for f in b["files"])
    k = key("uc-075-yearwalk")
    assert set(b["check"]["expect"]) == {f"{k[n]:,}" for n in WALK}  # only what the files carry; the opening, the income and the balancing item are not promised


# ---- card 75, what happened to our worth ------------------------------------------------------------------------------------------------------

WALK = ["investment_gains", "liquid_book_gain", "private_and_hedge_fund_gain", "spending", "closing", "capital_calls_paid", "distributions_received"]


def test_card_75_every_figure_the_files_carry_is_the_key(office):
    k, rows = key("uc-075-yearwalk"), office.run("networth_walk")  # run() also checks the A8 tables and the tie-out
    assert len(rows) == 1
    r = rows[0]
    assert (str(r["period_from"]), str(r["period_to"]), str(r["opening_date"])) == (k["period"][0], k["period"][1], "2026-03-31")
    for name in WALK:
        assert f2(r[name]) == k[name], name
    assert (r["closing_funds"], r["closing_book"], r["closing_loan"]) == (68760000, 41200000, 2800000) and f2(r["closing_cash_usd_eq"]) == 7234995.51
    assert r["closing_fixing_missing"] == 0 and r["flows_fixing_missing"] == 0 and r["other_currency_lines"] == 0 and r["closing_estimated_funds"] == 2


def test_card_75_the_31_march_fixing_is_on_file_so_the_opening_is_the_key_and_the_walk_adds_up(office):
    k, r = key("uc-075-yearwalk"), office.run("networth_walk")[0]
    assert office.one("select count(*) from market_observations where observation_type = 'fx' and cast(observed_at as date) = date '2026-03-31'") == 1
    assert f2(r["opening"]) == k["opening"] and r["opening_fixing_missing"] == 0 and r["adds_up"] is True
    assert (f2(r["opening_funds"]), f2(r["opening_book"]), f2(r["opening_loan"])) == (64551403.0, 39672360.0, 3000000.0)
    assert f2(r["opening"]) + f2(r["investment_gains"]) + f2(r["income"]) - f2(r["spending"]) + f2(r["fx_and_other"]) == pytest.approx(f2(r["closing"]), abs=0.01)
    # A56: the key counts only the statements that arrived, so income and the balancing item are the key's
    assert f2(r["income"]) == k["income"] and f2(r["fx_and_other"]) == pytest.approx(k["fx_and_other"], abs=0.01)


def test_card_75_the_income_is_short_by_the_statement_that_never_arrived(office):
    """M02b: the July statement of TCB-B-USD (expected 6 August) is not in the files. The key (A56) leaves its 44.71 interest out and names the statement. The recipe counts the missing month."""
    r, k = office.run("networth_walk")[0], key("uc-075-yearwalk")
    assert r["bank_months_missing"] == 1
    assert office.one("select count(*) from source_batches where coalesce(storage_uri, '') like '%TCB_B_USD_2026-07%'") == 0
    assert f2(r["income"]) == k["income"] and k["statements_missing"] == ["TCB-B-USD 2026-07"] and len(k["statements_missing"]) == r["bank_months_missing"]


def test_card_75_the_expense_ledger_is_read_and_the_loan_interest_comes_from_the_loan_statements(office):
    r = office.run("networth_walk")[0]
    ledger = office.one("select sum(case when currency = 'USD' then amount else round(amount / (select f.value from market_observations as f where f.observation_type = 'fx' and cast(f.observed_at as date) = e.spent_on), 2) end) "
                        "from office_expenses as e where category <> 'Debt service'")
    interest = office.one("select sum(abs(value_numeric)) from extracted_fields where field_name = 'interest_charged_as_shown'")
    assert f2(r["spending"]) == round(float(ledger) + float(interest), 2) == key("uc-075-yearwalk")["spending"]
    assert office.report["expense_ledger"]["rows"] == 151 and not office.report["expense_ledger"]["not_loaded"]


def test_card_75_a_figure_without_its_fixing_is_empty_never_partial(office):
    con = office.con
    con.execute("begin")
    try:
        con.execute("delete from market_observations where observation_type = 'fx'")
        r = office.run("networth_walk")[0]
        assert r["closing"] is None and r["closing_cash_usd_eq"] is None and r["closing_fixing_missing"] == 3 and r["adds_up"] is False
        assert r["income"] is None and r["spending"] is None and r["flows_fixing_missing"] > 0 and r["fx_and_other"] is None
        assert f2(r["liquid_book_gain"]) == key("uc-075-yearwalk")["liquid_book_gain"]  # the parts that need no fixing stand
    finally:
        con.execute("rollback")
    assert f2(office.run("networth_walk")[0]["closing"]) == key("uc-075-yearwalk")["closing"]


def test_card_75_has_three_signals_one_exception_with_a_hold_and_roles_that_exist():
    role_ids = {r["id"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"]}
    sg = signals("uc-075-yearwalk")
    assert len(sg) == 3
    for sid, s in sg.items():
        assert SG.check(s, {r: r for r in role_ids}) is None, (sid, SG.check(s, {r: r for r in role_ids}))
        assert s["id"].startswith("uc-075-yearwalk-") and s.get("suggestion") is True and s["route_to"] in role_ids and s["trigger"]["figure"] == "networth_walk"
        declared = set(next(i["fields"] for i in s["inputs"] if i["kind"] == "doc"))
        used = set(re.findall(r"doc\.([A-Za-z_]\w*)", " ".join([s["condition"], s["message"], s["subject"], str((s.get("hold") or {}).get("scope", ""))])))
        assert used == declared, (sid, used ^ declared)
    exc = [s for s in sg.values() if s["severity"] == "problem"]
    assert len(exc) == 1 and exc[0]["hold"]["blocks"] == "present_networth_walk" and exc[0]["hold"]["until"]
    assert all(not s.get("hold") for s in sg.values() if s is not exc[0])


def test_card_75_signals_fire_on_the_office_data_and_stay_quiet_when_they_should(office):
    sg, row = signals("uc-075-yearwalk"), office.run("networth_walk")[0]
    head = fire(sg["uc-075-yearwalk-headline"], row)
    assert "From 2026-04-01 to 2026-09-30" in head and "USD 540,967" in head and "liquid book 1,514,870" in head and "funds -973,903" in head and "USD 114,394,995.51" in head
    assert "2 fund value(s)" in fire(sg["uc-075-yearwalk-estimate"], row) and fire(sg["uc-075-yearwalk-estimate"], {**row, "closing_estimated_funds": 0}) is False
    held = fire(sg["uc-075-yearwalk-incomplete"], row)
    assert "0 Singapore dollar account(s) have no USD/SGD fixing on or before 2026-03-31" in held and "1 account month(s) have no bank statement" in held and "It is held." in held
    assert fire(sg["uc-075-yearwalk-incomplete"], {**row, "opening_fixing_missing": 0, "bank_months_missing": 0}) is False
    assert fire(sg["uc-075-yearwalk-headline"], {**row, "closing": None}) is None  # a figure that is not there is skipped, never guessed
