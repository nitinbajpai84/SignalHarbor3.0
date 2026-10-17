"""W1b cash (cards 51 to 100 of the Cash and treasury domain: 54, 70, 72, 73), proved on the real pack readers.

Built: 54 (liquidity_ladder, on the payment schedule's stages, A34) and 73 (cash_runway, on office_expenses, A33). Not built: 70 and 72, which lean on rules nobody
has signed (ladder_window_days, forecast_call_assumption, forecast_floor; A34). The office6m files go through the real loader (test_w2_loader.py's `office` fixture);
recipes run with their table check and tie-out; signals run through the engine's own parser (test_w1_hold.fire). Expected numbers come from answer_keys.yaml.
Cases that change the data edit the warehouse inside a transaction that is rolled back. Synthetic data only."""
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
BUILT, UNBUILT = ["uc-054-ladder", "uc-073-runway"], ["uc-070-idle", "uc-072-cashfc"]
UNSIGNED = ["ladder_window_days", "forecast_call_assumption", "forecast_floor"]


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


# ---- the signals, the builds and the two unbuilt cards ------------------------------------------------------------------------------------------

def test_the_signals_are_well_formed():
    mine = sorted(p for c in BUILT for p in (PACK / "signals").glob(c + "-*.yaml"))
    docs = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in mine]
    assert len(docs) == 3
    assert any(s["severity"] != "info" and s.get("hold") for s in docs), "an exception signal with a hold (card 54)"
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


def test_70_and_72_stay_unbuilt_because_their_rules_are_not_signed(office):
    """A34: idle cash needs the 90 day window and the forecast needs the call assumption and the floor as signed rules. None is on file."""
    assert office.one("select count(*) from business_rules where rule_code in (select unnest(?))", UNSIGNED) == 0
    stub = next(r for r in R.stubs() if r["id"] == "cash_forecast")
    assert stub["sql"] is None and R.recipe("cash_forecast") is None and R.recipe("idle_cash") is None
    built = {x["id"] for p in (PACK / "builds").glob("*.yaml") for r in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("roles", []) for x in r.get("builds", [])}
    assert not built & set(UNBUILT)
