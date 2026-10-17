"""W1b cash (cards 51 to 100 of the Cash and treasury domain: 54, 70, 72, 73), proved on the real pack readers.

Built: 54 (liquidity_ladder, on the payment schedule's stages, A34), 70 (idle_cash, on the signed ladder_window_days and cash_buffer, A50) and 73 (cash_runway,
on office_expenses, A33). Card 72 has its recipe (cash_forecast, on the signed forecast_* rules, A50) but stays blocked: the payment schedule file stops at
11 Jan 2027, and the key's expenses after it come from schedule items that are in no file. The office6m files go through the real loader (test_w2_loader.py's
`office` fixture); recipes run with their table check and tie-out; signals run through the engine's own parser (test_w1_hold.fire). Expected numbers come from
answer_keys.yaml. Cases that change the data edit the warehouse inside a transaction that is rolled back. Synthetic data only."""
from __future__ import annotations

import glob
import importlib.util
from pathlib import Path

import pytest
import yaml

from sh_platform.v1 import v3_recipes as R
from tests.v1.test_w1_hold import ROLES, fire, leaves

_SPEC = importlib.util.spec_from_file_location("w2_loader_tests", Path(__file__).with_name("test_w2_loader.py"))
W2 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(W2)
key, f2, one, TODAY, KEYS = W2.key, W2.f2, W2.one, W2.TODAY, W2.KEYS
office = W2.office  # the module fixture: the office files loaded through the real readers
PACK = Path(__file__).resolve().parents[2] / "packs" / "family_office" / "1"
BUILT, UNBUILT = ["uc-054-ladder", "uc-070-idle", "uc-073-runway"], ["uc-072-cashfc"]
FORECAST_RULES = ["forecast_call_assumption", "forecast_floor", "forecast_horizon", "forecast_held_payments", "forecast_distribution_basis"]


def ladder(office) -> dict:
    return {(r["entity"], str(r["window_days"])): r for r in office.run("liquidity_ladder")}


# ---- card 54: the ladder -------------------------------------------------------------------------------------------------------------------------

def test_54_the_ladder_agrees_with_the_key_for_every_entity_and_window(office):
    k, lad = key("uc-054-ladder"), ladder(office)
    cash = [r for r in office.run("cash_by_entity") if str(r["position_date"]) == TODAY]
    assert len(lad) == 9
    for name, v in k["by_entity"].items():
        assert f2(one(cash, entity=name, currency="USD")["cash"]) == v["cash_usd"] and f2(one(cash, entity=name, currency="SGD")["cash"]) == v["cash_sgd"]
        for days, w in v["windows"].items():
            r = lad[(name, days)]
            assert str(r["as_of"]) == TODAY and r["unconverted"] == 0
            assert f2(r["cash_usd_equivalent"]) == v["cash_usd_equivalent"]
            assert (f2(r["calls"]), f2(r["approved_and_scheduled_payments"]), f2(r["cash_after"]), r["below_buffer"]) == (
                w["calls"], w["approved_and_scheduled_payments"], w["cash_after"], w["below_buffer"]), (name, days)


def test_54_held_and_expected_payments_are_left_out_until_approved(office):
    """FEE-CUST-Q3 (held, above its fee schedule) is not in the Trust's 30 days; approving it adds exactly its 6,180."""
    before = ladder(office)[("Evergreen Family Trust", "30")]["approved_and_scheduled_payments"]
    con = office.con
    con.execute("begin")
    try:
        con.execute("update cash_movements set payment_stage = 'approved' where reference = 'FEE-CUST-Q3'")
        after = ladder(office)[("Evergreen Family Trust", "30")]["approved_and_scheduled_payments"]
    finally:
        con.execute("rollback")
    assert f2(after - before) == 6180.0


def test_54_without_the_schedule_the_ladder_is_held_not_rosier(office):
    r = R.recipe("liquidity_ladder")
    assert office.one(r["needs"][0]["sql"]) > 0
    con = office.con
    con.execute("begin")
    try:
        con.execute("update cash_movements set payment_stage = null")
        assert office.one(r["needs"][0]["sql"]) == 0
    finally:
        con.execute("rollback")


def test_54_signals_fire_on_the_key_and_the_exception_holds_when_an_entity_falls_under_the_buffer(office):
    k = key("uc-054-ladder")["by_entity"]["Evergreen Holdings"]["windows"]["90"]
    t = {"liquidity_ladder": office.run("liquidity_ladder")}
    msg = fire("uc-054-ladder-tightest", t)
    assert msg and msg.startswith("Evergreen Holdings") and f"{k['cash_after']:,.2f}" in msg and f"{k['approved_and_scheduled_payments']:,.2f}" in msg
    assert fire("uc-054-ladder-below-buffer", t) is False  # nobody is under the buffer in the key
    con = office.con
    con.execute("begin")
    try:  # an approved payment of 700,000 USD in 45 days takes Holdings under the buffer at 60 and 90 days
        con.execute("update cash_movements set amount = -700000, currency = 'USD', due_date = date '2026-11-27' where reference = 'INS-POL-LIAB-03'")
        t = {"liquidity_ladder": office.run("liquidity_ladder")}
        msg = fire("uc-054-ladder-below-buffer", t)
        assert msg and msg.startswith("Evergreen Holdings falls under the 250,000 buffer within 60 days") and fire("uc-054-ladder-tightest", t) is False
        con.execute("update rule_versions set approval_status = 'proposed' where business_rule_id in (select id from business_rules where rule_code = 'cash_buffer')")
        t = {"liquidity_ladder": office.run("liquidity_ladder")}
        assert all(r["buffer"] is None and r["below_buffer"] is None for r in t["liquidity_ladder"])
        assert fire("uc-054-ladder-below-buffer", t) is None  # no signed buffer: skipped, never guessed
    finally:
        con.execute("rollback")


# ---- card 73: the runway -------------------------------------------------------------------------------------------------------------------------

def test_73_the_runway_agrees_with_the_key(office):
    k, rows = key("uc-073-runway"), office.run("cash_runway")
    assert {r["category"]: f2(r["spend_usd"]) for r in rows} == k["six_month_spend_by_category"]
    r = rows[0]
    assert (r["months"], r["unconverted"], str(r["as_of"])) == (6, 0, TODAY)
    for c in ("cash_usd_eq", "average_monthly_spend", "months_of_cash", "months_of_cash_and_liquid_book", "liquid_book"):
        assert f2(r[c]) == k[c], c


def test_73_the_signal_says_the_months_and_the_largest_item(office):
    k = key("uc-073-runway")
    msg = fire("uc-073-runway-months", {"cash_runway": office.run("cash_runway")})
    assert msg and f"covers {k['months_of_cash']} months" in msg and f"{k['average_monthly_spend']:,.2f}" in msg and "Staff" in msg


# ---- card 70: idle cash ------------------------------------------------------------------------------------------------------------------------

def test_70_idle_cash_agrees_with_the_key(office):
    k, rows = key("uc-070-idle"), office.run("idle_cash")
    assert len(rows) == 3
    for name, v in k["by_entity"].items():
        r = one(rows, entity=name)
        assert (r["window_days"], str(r["as_of"]), r["unconverted"]) == (90, TODAY, 0)
        assert (f2(r["cash_usd_equivalent"]), f2(r["outflow"]), f2(r["buffer"]), f2(r["idle"]), f2(r["short"])) == (
            v["cash_usd_equivalent"], v["outflow_90_days"], v["buffer"], v["idle"], v["short"]), name
    assert (f2(rows[0]["total_idle"]), f2(rows[0]["total_short"])) == (k["total_idle"], k["total_short"])
    lad = ladder(office)  # the same outflow as card 54's 90 day rung
    assert all(f2(r["outflow"]) == f2(lad[(r["entity"], "90")]["calls"] + lad[(r["entity"], "90")]["approved_and_scheduled_payments"]) for r in rows)


def test_70_the_window_is_the_signed_rule_and_without_it_the_figure_is_held(office):
    r = R.recipe("idle_cash")
    con = office.con
    con.execute("begin")
    try:  # a signed 30 day window moves the outflow to the 30 day rung
        con.execute("""update rule_versions set parameters = '{"days": 30}' where business_rule_id in (select id from business_rules where rule_code = 'ladder_window_days')""")
        lad = ladder(office)
        assert all(x["window_days"] == 30 and f2(x["outflow"]) == f2(lad[(x["entity"], "30")]["calls"] + lad[(x["entity"], "30")]["approved_and_scheduled_payments"])
                   for x in office.run("idle_cash"))
        con.execute("update rule_versions set approval_status = 'proposed' where business_rule_id in (select id from business_rules where rule_code = 'ladder_window_days')")
        assert office.one(r["needs"][0]["sql"]) == 0 and office.run("idle_cash") == []
    finally:
        con.execute("rollback")


def test_70_signals_say_the_surplus_and_the_exception_holds_an_entity_that_is_short(office):
    k = key("uc-070-idle")
    msg = fire("uc-070-idle-surplus", {"idle_cash": office.run("idle_cash")})
    assert msg and f"{k['total_idle']:,.2f} is idle" in msg and "Evergreen Family Trust" in msg
    assert fire("uc-070-idle-short", {"idle_cash": office.run("idle_cash")}) is False  # nobody is short in the key
    con = office.con
    con.execute("begin")
    try:  # an approved 2,500,000 USD payment in 45 days leaves Holdings short of its 90 days
        con.execute("update cash_movements set amount = -2500000, currency = 'USD', due_date = date '2026-11-27' where reference = 'INS-POL-LIAB-03'")
        rows = office.run("idle_cash")
        h = one(rows, entity="Evergreen Holdings")
        assert h["idle"] == 0 and h["short"] > 0 and f2(rows[0]["total_short"]) == f2(h["short"])
        msg = fire("uc-070-idle-short", {"idle_cash": rows})
        assert msg and msg.startswith(f"Evergreen Holdings is {h['short']:,.2f} short")
    finally:
        con.execute("rollback")


# ---- card 72: the forecast (recipe built, card blocked by the schedule's end) ----------------------------------------------------------------

def test_72_the_forecast_agrees_with_the_key_while_the_schedule_lasts(office):
    k, rows = key("uc-072-cashfc"), office.run("cash_forecast")
    fc = {r["month"]: r for r in rows}
    assert list(fc) == sorted(k["by_month"]) and str(rows[0]["as_of"]) == TODAY and rows[0]["unconverted"] == 0
    assert (f2(rows[0]["opening_cash_usd_eq"]), f2(rows[0]["monthly_call_assumption"]), f2(rows[0]["floor"])) == (
        k["opening_cash_usd_eq"], k["monthly_call_assumption"], k["floor"])
    for m, v in k["by_month"].items():  # distributions, income and calls come from the files for every month
        assert (f2(fc[m]["distributions"]), f2(fc[m]["income"]), f2(fc[m]["calls"])) == (v["distributions"], v["income"], v["calls"]), m
    for m in ("2026-10", "2026-11", "2026-12"):  # the schedule covers these months to their end: every line agrees
        assert fc[m]["expenses_complete"] is True
        assert {c: f2(fc[m][c]) for c in k["by_month"][m]} == k["by_month"][m], m


def test_72_stays_blocked_because_the_keys_later_expenses_are_in_no_file(office):
    """The schedule csv ends on 11 Jan 2027; the key's expenses from January to September come from schedule items the file never had."""
    k, fc = key("uc-072-cashfc"), {r["month"]: r for r in office.run("cash_forecast")}
    late = [m for m in sorted(k["by_month"]) if not fc[m]["expenses_complete"]]
    assert late == [m for m in sorted(k["by_month"]) if m >= "2027-01"] and str(fc["2027-01"]["schedule_ends"]) <= "2027-01-11"
    assert all(f2(fc[m]["expenses"]) < k["by_month"][m]["expenses"] for m in late)
    assert not any(x["id"] == "uc-072-cashfc" for p in (PACK / "builds").glob("*.yaml") for r in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("roles", [])
                   for x in r.get("builds", []))


def test_72_every_assumption_is_a_signed_rule_and_without_one_the_forecast_is_held(office):
    r = R.recipe("cash_forecast")
    assert office.one("select count(distinct rule_code) from business_rules where rule_code in (select unnest(?))", FORECAST_RULES) == 5
    assert office.one(r["needs"][0]["sql"]) == 1
    con = office.con
    con.execute("begin")
    try:
        con.execute("update rule_versions set approval_status = 'proposed' where business_rule_id in (select id from business_rules where rule_code = 'forecast_floor')")
        assert office.one(r["needs"][0]["sql"]) == 0
    finally:
        con.execute("rollback")
    con.execute("begin")
    try:  # the held FEE-CUST-Q3 is left out by the signed rule; approving it adds its 6,180 to October
        before = one(office.run("cash_forecast"), month="2026-10")["expenses"]
        con.execute("update cash_movements set payment_stage = 'approved' where reference = 'FEE-CUST-Q3'")
        assert f2(one(office.run("cash_forecast"), month="2026-10")["expenses"] - before) == 6180.0
    finally:
        con.execute("rollback")


def test_72_signals_name_the_low_month_the_floor_and_the_schedule_gap(office):
    t = {"cash_forecast": office.run("cash_forecast")}
    low = one(t["cash_forecast"], is_lowest=True)
    msg = fire("uc-072-cashfc-outlook", t)
    assert msg and f"lowest in {low['month']} at {low['closing']:,.2f}" in msg and "991,666.67" in msg
    msg = fire("uc-072-cashfc-below-floor", t)
    assert msg and "750,000 floor" in msg and f"{low['cash_to_raise']:,.2f} must be raised" in msg
    msg = fire("uc-072-cashfc-schedule-ends", t)
    assert msg and "from 2027-01 to 2027-09-30" in msg


# ---- the signals and the builds -----------------------------------------------------------------------------------------------------------------

def test_the_signals_are_well_formed():
    mine = sorted(p for c in BUILT + UNBUILT for p in (PACK / "signals").glob(c + "-*.yaml"))
    docs = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in mine]
    assert len(docs) == 8
    assert sum(1 for s in docs if s["severity"] != "info" and s.get("hold")) == 3, "an exception signal with a hold for cards 54, 70 and 72"
    for p, s in zip(mine, docs):
        assert s["id"] == p.stem and s["suggestion"] is True and s["route_to"] in ROLES
        assert s["severity"] in {"info", "needs", "problem"} and s["action"]["verb"] in {"log", "record", "approve", "call_back", "see"}
        for i in s["inputs"]:
            r = R.recipe(i["recipe"])
            assert r and set(i["by"]) <= set(r["columns"]) | {"entity", "window_days", "category"}


def test_the_builds_carry_the_exact_answer_keys():
    b = yaml.safe_load((PACK / "builds" / "cash-51.yaml").read_text(encoding="utf-8"))
    builds = {x["id"]: (r["id"], x) for r in b["roles"] for x in r["builds"]}
    assert set(builds) == set(BUILT)
    for card, (role, x) in builds.items():
        assert role in ROLES and x["say"] and x["files"] and x["check"]["ask"] and x["check"]["expect"]
        assert all(f.startswith("office6m:") and glob.glob(str(W2.OFFICE / f[9:])) for f in x["files"])
        numbers = [float(v) for v in leaves(KEYS[card]["questions"]) if isinstance(v, (int, float)) and not isinstance(v, bool)]
        for e in x["check"]["expect"]:
            assert any(abs(float(str(e).replace(",", "")) - v) < 1e-9 for v in numbers), (card, e)
