"""W1b hold: the recipes of the "Hold and maintain" cards of 51 to 100 (55, 64, 65, 66, 67, 68), run on the real loader's warehouse and compared with
answer_keys.yaml. Card 69 is unbuilt: the fund holdings lists have no reader yet (docs/v3/w1/build51-hold.md, Needs).

Real: the office6m files copied into a company's dropbox, the platform's warehouse and the real loader (as tests/v1/test_w2_loader.py), the recipe and its tie-out,
the signal yaml run through the engine's own parser. Nothing is stubbed. No expected number is typed here: they come from the key. The cases that change the data
(a confirmation that agrees, a forward with no confirmation) edit the warehouse inside a transaction that is rolled back. Synthetic data only.
"""
from __future__ import annotations

import glob
from pathlib import Path

import pytest
import yaml

from sh_platform.plane import PlaneStore
from sh_platform.v1 import v3_office6m_loaders as L
from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import wh
from tests.v1 import test_w2_loader as W
from tests.v1.test_w1_hold import ROLES, fire, leaves

REPO = Path(__file__).resolve().parents[2]
OFFICE = W.OFFICE
PACK = REPO / "packs" / "family_office" / "1"
KEYS = W.KEYS
CARD = "uc-064-fxexp"
BUILT = [CARD, "uc-055-corpact", "uc-065-realassets", "uc-066-propreval", "uc-067-unrl", "uc-068-incomef"]
UNBUILT = ["uc-069-lookthru"]
# cards whose story has an exception (a signal that is not info); 68 has none
EXCEPTION = {CARD, "uc-055-corpact", "uc-065-realassets", "uc-066-propreval", "uc-067-unrl"}


@pytest.fixture(scope="module")
def office(tmp_path_factory) -> W.Loaded:
    tmp = tmp_path_factory.mktemp("w1b")
    box = W.office_dropbox(tmp)
    wh.reset_cache()
    plane = PlaneStore(tmp / "data").create("evergreen")
    o = W.Loaded(plane, L.load_plane(plane, box))
    yield o
    o.con.close()


def key(card=CARD, n=0) -> dict:
    return W.key(card, n)


def by_ccy(rows):
    return {r["currency"]: r for r in rows}


def f2(v) -> float:
    return round(float(v), 2)


# ---- card 64: currency exposure --------------------------------------------------------------------------------------------------------------

def test_64_the_recipe_is_built_and_its_tie_out_holds(office):
    r = R.recipe("currency_exposure")
    assert r["status"] == "ready" and r["cards"] == [64] and r["tie_out"]
    rows = office.run("currency_exposure")  # also renders, checks the tables read and runs the tie-out
    assert sorted(x["currency"] for x in rows) == ["SGD", "USD"]


def test_64_the_exposure_equals_the_key(office):
    k = key()
    t = by_ccy(office.run("currency_exposure"))
    sgd, usd = t["SGD"], t["USD"]
    assert f2(sgd["cash"]) == k["sgd_cash"]
    assert f2(sgd["spot_usd_eq"]) == k["sgd_cash_usd_eq"]
    assert f2(sgd["fwd_bought"]) == k["sgd_bought_forward"]
    assert f2(sgd["fwd_bought_usd_eq"]) == k["sgd_forward_usd_eq"]
    assert f2(sgd["after_usd_eq"]) == k["net_sgd_exposure_usd_eq"]
    assert f2(sgd["share_after_pct"]) == k["share_of_family_pct"]
    assert f2(usd["spot_usd_eq"]) == k["usd_exposure_usd_eq"]
    assert f2(sgd["family_total_usd_eq"]) == f2(usd["family_total_usd_eq"]) == k["family_total_usd_eq"]
    assert f2(sgd["spot_usd_eq"]) + f2(usd["spot_usd_eq"]) == pytest.approx(k["family_total_usd_eq"], abs=0.005)
    assert str(sgd["as_of"]) == "2026-10-13" and str(sgd["month_end"]) == "2026-09-30" and f2(sgd["rate"]) == 1.34
    assert sgd["non_base"] and not usd["non_base"] and sgd["unplaced_forwards"] == 0 and not sgd["no_rate"]


def test_64_the_sold_leg_is_taken_off_the_usd_side(office):
    """The card's formula adds the bought leg and takes the sold leg off; the key's USD figure is the figure before the forwards."""
    usd = by_ccy(office.run("currency_exposure"))["USD"]
    assert f2(usd["fwd_sold"]) == 5000000.0 and f2(usd["after_usd_eq"]) == f2(usd["spot_usd_eq"]) - 5000000.0


def test_64_the_bank_confirms_more_than_was_booked_by_the_amount_the_other_key_states(office):
    """FXF-2026-002 is booked at 1.3425 and confirmed at 1.3452 (M16): the SGD forward is 8,100 higher on the confirmation. The figure uses the booking (the key's
    6,707,500); the gap is shown, never absorbed."""
    sgd = by_ccy(office.run("currency_exposure"))["SGD"]
    diff = key("uc8-trades-vs-admin")["difference_sgd"]
    assert f2(sgd["fwd_gap"]) == float(diff)
    assert f2(sgd["fwd_net_confirmed"]) == key()["sgd_bought_forward"] + float(diff)


def test_64_a_confirmation_that_agrees_leaves_no_gap_and_a_missing_one_is_never_guessed(office):
    con = office.con
    con.execute("begin")
    try:
        con.execute("update fx_confirmations set amount_bought = 4027500, rate = 1.3425 where trade_reference = 'FXF-2026-002'")
        assert by_ccy(office.run("currency_exposure"))["SGD"]["fwd_gap"] == 0
        con.execute("delete from fx_confirmations where trade_reference = 'FXF-2026-002'")
        t = by_ccy(office.run("currency_exposure"))
        assert t["SGD"]["unplaced_forwards"] == 1 and f2(t["SGD"]["fwd_bought"]) == key()["sgd_bought_forward"]  # the bought leg stands
        assert f2(t["USD"]["fwd_sold"]) == 2000000.0  # the USD sold leg of the other forward only: the unplaced one is not guessed onto a currency
    finally:
        con.execute("rollback")
    assert f2(by_ccy(office.run("currency_exposure"))["SGD"]["fwd_gap"]) == 8100.0  # rolled back


def test_64_a_forward_that_has_settled_is_no_longer_open(office):
    con = office.con
    con.execute("begin")
    try:
        con.execute("update transactions set settlement_date = date '2026-10-12' where external_trade_id = 'FXF-2026-001'")
        con.execute("update fx_confirmations set value_date = date '2026-10-12' where trade_reference = 'FXF-2026-001'")
        t = by_ccy(office.run("currency_exposure"))
        assert f2(t["SGD"]["fwd_bought"]) == 4027500.0 and f2(t["USD"]["fwd_sold"]) == 3000000.0
    finally:
        con.execute("rollback")


# ---- the signals ---------------------------------------------------------------------------------------------------------------------------

def tables(office):
    return {"currency_exposure": office.run("currency_exposure")}


def test_64_the_exposure_signal_fires_on_the_key_data(office):
    k = key()
    msg = fire("uc-064-fxexp-exposure", tables(office))
    assert msg and f"{k['net_sgd_exposure_usd_eq']:,.0f}" in msg and f"{k['share_of_family_pct']:.2f}" in msg


def test_64_the_forward_difference_fires_with_the_gap_and_the_booked_figure(office):
    msg = fire("uc-064-fxexp-forward-differs", tables(office))
    diff = key("uc8-trades-vs-admin")["difference_sgd"]
    assert msg and f"{diff:,.0f}" in msg and f"{key()['sgd_bought_forward']:,.0f}" in msg
    con = office.con
    con.execute("begin")
    try:
        con.execute("update fx_confirmations set amount_bought = 4027500, rate = 1.3425 where trade_reference = 'FXF-2026-002'")
        assert fire("uc-064-fxexp-forward-differs", tables(office)) is False
    finally:
        con.execute("rollback")


def test_64_the_limit_signal_is_skipped_with_no_signed_limit_and_works_when_one_is_given(office):
    """No currency limit is signed in the office files, so none is applied. The rule values below are synthetic, only to show the condition."""
    t = tables(office)
    assert fire("uc-064-fxexp-over-limit", t) is None
    assert fire("uc-064-fxexp-over-limit", t, rules={"currency_exposure_limit_pct": {"value": 5}}).startswith("SGD is 7.62 percent")
    assert fire("uc-064-fxexp-over-limit", t, rules={"currency_exposure_limit_pct": {"value": 10}}) is False


def test_64_with_two_non_base_currencies_the_signals_are_skipped_not_guessed(office):
    rows = office.run("currency_exposure")
    extra = dict(next(r for r in rows if r["currency"] == "SGD"), currency="EUR")
    assert fire("uc-064-fxexp-exposure", {"currency_exposure": rows + [extra]}) is None


@pytest.mark.parametrize("card", BUILT)
def test_signals_are_well_formed(card):
    mine = sorted((PACK / "signals").glob(card + "-*.yaml"))
    docs = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in mine]
    assert docs
    if card in EXCEPTION:
        assert any(s["severity"] != "info" for s in docs), "an exception signal"
    if card in (CARD, "uc-055-corpact", "uc-065-realassets"):
        assert any(s.get("hold") for s in docs), "the story's hold"
    for p, s in zip(mine, docs):
        assert s["id"] == p.stem and s["suggestion"] is True and s["route_to"] in ROLES
        assert s["severity"] in {"info", "needs", "problem"} and s["action"]["verb"] in {"log", "record", "approve", "call_back", "see"}
        for i in s["inputs"]:
            if i.get("recipe"):
                assert R.recipe(i["recipe"])


# ---- card 55: corporate actions in the next 14 days ----------------------------------------------------------------------------------------

def by_bucket(rows, bucket):
    return [r for r in rows if r["bucket"] == bucket]


def test_55_the_bookings_decisions_and_later_events_equal_the_key(office):
    k = key("uc-055-corpact")
    rows = office.run("actions_next_14d")
    assert [str(rows[0]["window_from"]), str(rows[0]["window_to"])] == k["window"]
    book = {r["security"]: r for r in by_bucket(rows, "book")}
    assert set(book) == {x["security"] for x in k["to_book"]}
    for x in k["to_book"]:
        r = book[x["security"]]
        assert (r["event"], str(r["ex_date"]), str(r["pay_date"])) == (x["event"], x["ex_date"], x["pay_date"])
        assert f2(r["quantity"]) == x["quantity"] and f2(r["expected_cash"]) == x["expected_cash"]
    assert f2(rows[0]["cash_to_book"]) == k["cash_to_book"] and rows[0]["book_count"] == len(k["to_book"])
    (d,) = by_bucket(rows, "decide")
    (x,) = k["to_decide"]
    assert (d["security"], str(d["respond_by"])) == (x["security"], x["respond_by"]) and x["event"].endswith(d["event"])  # the model's action type: "voluntary" is the election flag
    assert (f2(d["offer_price"]), f2(d["last_price"]), f2(d["premium_pct"]), f2(d["quantity"])) == (x["offer_price"], x["last_price"], x["premium_pct"], x["quantity_held"])
    assert d["expected_cash"] is None  # no cash until the office elects
    (o,) = by_bucket(rows, "later")
    (x,) = k["announced_outside_window"]
    assert (o["security"], o["event"], str(o["ex_date"]), str(o["pay_date"]), f2(o["quantity"]), f2(o["expected_cash"])) == \
        (x["security"], x["event"], x["ex_date"], x["pay_date"], x["quantity"], x["expected_cash"])


def test_55_the_notices_agree_with_the_income_calendar(office):
    """Two sources, one figure: the cash each booking's notice states equals the income calendar's expected line of the same security and pay date."""
    cal = {(r["security"], str(r["due_date"])): f2(r["amount"]) for r in office.rows(
        "select i.canonical_name as security, c.due_date, c.amount from cash_movements as c join instruments as i on i.id = c.instrument_id "
        "where c.confirmation_status = 'expected' and c.movement_type in ('dividend', 'coupon')")}
    for r in office.run("actions_next_14d"):
        if r["expected_cash"] is not None:
            assert cal[(r["security"], str(r["pay_date"]))] == f2(r["expected_cash"]), r["security"]


def test_55_an_election_past_its_deadline_is_missed_not_decided(office):
    con = office.con
    con.execute("begin")
    try:
        con.execute("update corporate_actions set election_deadline = date '2026-10-10' where action_type = 'tender_offer'")
        rows = office.run("actions_next_14d")
        assert not by_bucket(rows, "decide") and [r["security"] for r in by_bucket(rows, "missed")] == ["Tidewater Energy"]
        assert fire("uc-055-corpact-election", {"actions_next_14d": rows}) is None
    finally:
        con.execute("rollback")


def test_55_the_signals_fire_with_the_key_figures(office):
    k = key("uc-055-corpact")
    t = {"actions_next_14d": office.run("actions_next_14d")}
    msg = fire("uc-055-corpact-to-book", t)
    assert msg and f"{k['cash_to_book']:,.2f}" in msg and f"{len(k['to_book'])} corporate actions" in msg
    (x,) = k["to_decide"]
    msg = fire("uc-055-corpact-election", t)
    assert msg and x["security"] in msg and f"{x['premium_pct']:.2f}" in msg and x["respond_by"] in msg and f"{x['quantity_held']:,.0f}" in msg


# ---- card 65: the real assets register --------------------------------------------------------------------------------------------------

def test_65_the_register_equals_the_key(office):
    k = key("uc-065-realassets")
    rows = {r["asset_ref"]: r for r in office.run("real_asset_value")}
    assert set(rows) == {a["id"] for a in k["assets"]}
    for a in k["assets"]:
        r = rows[a["id"]]
        assert (r["asset_name"], r["asset_type"], r["entity"], r["currency"], str(r["appraised_on"]), r["title_holder"]) == \
            (a["name"], a["type"], a["entity"], a["currency"], a["appraised"], a["title_holder"])
        assert f2(r["latest_value"]) == a["latest_value"] and f2(r["value_usd"]) == a["value_usd"]
    one = next(iter(rows.values()))
    assert f2(one["total_usd"]) == k["total_usd"]
    assert {r["asset_type"]: f2(r["type_total_usd"]) for r in rows.values()} == k["by_type"]
    assert {r["entity"]: f2(r["entity_total_usd"]) for r in rows.values()} == k["by_entity"]
    assert [r["asset_name"] for r in rows.values() if r["title_differs"]] == k["title_not_in_entity_name"]


def test_65_the_title_exception_holds_the_register_and_clears_when_the_title_matches(office):
    k = key("uc-065-realassets")
    t = {"real_asset_value": office.run("real_asset_value")}
    msg = fire("uc-065-realassets-title", t)
    assert msg and k["title_not_in_entity_name"][0] in msg and "Lin Chen" in msg
    assert f"{k['total_usd']:,.2f}" in fire("uc-065-realassets-register", t)
    con = office.con
    con.execute("begin")
    try:
        con.execute("update real_assets set title_holder_name = 'Entity B' where asset_ref = 'RA-04'")
        assert fire("uc-065-realassets-title", {"real_asset_value": office.run("real_asset_value")}) is None
    finally:
        con.execute("rollback")


# ---- card 66: appraisal due ---------------------------------------------------------------------------------------------------------------

def test_66_the_ages_equal_the_key(office):
    k = key("uc-066-propreval")
    rows = {r["asset_ref"]: r for r in office.run("appraisal_age")}
    for a in k["by_asset"]:
        r = rows[a["id"]]
        assert (r["asset_name"], str(r["appraised_on"]), r["age_days"], r["due"]) == (a["name"], a["appraised"], a["age_days"], a["due"])
    assert next(iter(rows.values()))["due_names"].split(", ") == k["order_new"]


def test_66_the_signal_names_the_assets_due_and_is_silent_after_new_appraisals(office):
    k = key("uc-066-propreval")
    msg = fire("uc-066-propreval-due", {"appraisal_age": office.run("appraisal_age")})
    assert msg and all(n in msg for n in k["order_new"]) and str(max(a["age_days"] for a in k["by_asset"])) in msg
    con = office.con
    con.execute("begin")
    try:
        con.execute("update real_assets set appraised_on = date '2026-10-01' where asset_ref in ('RA-03', 'RA-05')")
        assert fire("uc-066-propreval-due", {"appraisal_age": office.run("appraisal_age")}) is None
    finally:
        con.execute("rollback")


# ---- card 67: unrealised gain by lot -------------------------------------------------------------------------------------------------------

LOT_COLS = ("security", "acquired", "days_held", "quantity", "cost", "value", "gain")


def lot_view(r):
    return {"security": r["security"], "acquired": str(r["acquired"]), "days_held": r["days_held"],
            **{c: f2(r[c]) for c in ("quantity", "cost", "value", "gain")}}


def test_67_the_lots_equal_the_key(office):
    k = key("uc-067-unrl")
    rows = office.run("unrealised_gain")
    lots = {r["lot"]: r for r in rows}
    assert len(rows) == k["lots"] == rows[0]["lots"] and rows[0]["unpriced_lots"] == 0
    assert f2(rows[0]["total_gain"]) == k["total_unrealised_gain"] and f2(rows[0]["total_loss"]) == k["total_unrealised_loss"]
    assert [r["lot"] for r in sorted((r for r in rows if r["is_loss"]), key=lambda r: (r["gain"], r["lot"]))] == [x["lot"] for x in k["loss_lots"]]
    for x in k["loss_lots"] + k["largest_gain_lots"] + k["harborview_lots"]:
        assert lot_view(lots[x["lot"]]) == {c: x[c] for c in LOT_COLS}, x["lot"]
    assert [r["lot"] for r in sorted(rows, key=lambda r: -r["gain"])[:len(k["largest_gain_lots"])]] == [x["lot"] for x in k["largest_gain_lots"]]
    assert {r["security"]: f2(r["holding_gain"]) for r in rows} == k["gain_by_security"]


def office_rule(name: str) -> dict:
    """The office's own signed rule, read from its reference file (never typed here)."""
    import csv
    with open(OFFICE / "reference" / "office_rules.csv", encoding="utf-8") as f:
        row = next(r for r in csv.DictReader(f) if r["rule"] == name)
    return {"value": float(row["value"])}


def test_67_the_sale_to_the_single_name_limit_equals_the_key(office):
    k = key("uc-067-unrl")
    t = {"unrealised_gain": office.run("unrealised_gain")}
    assert fire("uc-067-unrl-over-limit", t) is None  # no signed limit given: skipped, never guessed
    msg = fire("uc-067-unrl-over-limit", t, rules={"single_name_limit_pct": office_rule("single_name_limit_pct")})
    assert msg and msg.startswith(k["harborview_lots"][0]["security"]) and f"{k['harborview_sale_to_reach_5_pct']:,.2f}" in msg
    assert fire("uc-067-unrl-over-limit", t, rules={"single_name_limit_pct": {"value": 10}}) is False  # synthetic limit, only to show the condition


def test_67_the_signed_exemption_keeps_the_sovereign_note_out_of_the_ranking(office):
    rows = office.run("unrealised_gain")
    htn = [r for r in rows if r["exempt"]]
    assert htn and all(r["name_rank"] is None for r in htn) and max(r["holding_pct"] for r in htn) > max(r["holding_pct"] for r in rows if not r["exempt"])
    con = office.con
    con.execute("begin")
    try:
        con.execute("update rule_versions set approval_status = 'proposed' where parameters like '%single_name_exempt%'")
        top = next(r for r in office.run("unrealised_gain") if r["name_rank"] == 1)
        assert top["security"] == htn[0]["security"]  # without the signed exemption the note would be the largest name
    finally:
        con.execute("rollback")


def test_67_the_losses_signal(office):
    k = key("uc-067-unrl")
    msg = fire("uc-067-unrl-losses", {"unrealised_gain": office.run("unrealised_gain")})
    assert msg and f"{k['total_unrealised_gain']:,.0f}" in msg and f"{k['total_unrealised_loss']:,.0f}" in msg and k["loss_lots"][0]["lot"] in msg


# ---- card 68: income forecast --------------------------------------------------------------------------------------------------------------

def test_68_the_forecast_equals_the_key(office):
    k = key("uc-068-incomef")
    rows = office.run("income_forecast")
    one = rows[0]
    assert [str(one["period_from"]), str(one["period_to"])] == k["period"]
    assert (f2(one["total"]), f2(one["coupons"]), f2(one["dividends"]), one["events"]) == (k["total"], k["coupons"], k["dividends"], k["events"])
    assert {r["quarter"]: f2(r["quarter_total"]) for r in rows} == k["by_quarter"]
    msg = fire("uc-068-incomef-forecast", {"income_forecast": rows})
    assert msg and f"{k['total']:,.2f}" in msg


def test_68_cash_already_received_is_not_forecast(office):
    k = key("uc-068-incomef")
    con = office.con
    con.execute("begin")
    try:
        amt = con.execute("select amount from cash_movements where confirmation_status = 'expected' and movement_type = 'coupon' order by due_date limit 1").fetchone()[0]
        con.execute("update cash_movements set confirmation_status = 'confirmed' where id = (select id from cash_movements where confirmation_status = 'expected' "
                    "and movement_type = 'coupon' order by due_date limit 1)")
        assert f2(office.run("income_forecast")[0]["total"]) == pytest.approx(k["total"] - float(amt))
    finally:
        con.execute("rollback")


# ---- the build and the unbuilt cards ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("card", BUILT)
def test_the_build_carries_the_exact_answer_keys(card):
    b = yaml.safe_load((PACK / "builds" / "hold-51.yaml").read_text(encoding="utf-8"))
    builds = {x["id"]: (r["id"], x) for r in b["roles"] for x in r["builds"]}
    assert set(builds) == set(BUILT)
    role, x = builds[card]
    assert role in ROLES and x["say"] and x["files"] and x["check"]["ask"] and x["check"]["expect"]
    assert all(f.startswith("office6m:") and glob.glob(str(OFFICE / f[9:])) for f in x["files"])
    have = list(leaves(KEYS[card]["questions"]))
    numbers = [float(v) for v in have if isinstance(v, (int, float)) and not isinstance(v, bool)]
    for e in x["check"]["expect"]:
        assert any(abs(float(e.replace(",", "")) - v) < 1e-9 for v in numbers), e


def test_card_69_is_honestly_unbuilt():
    """No recipe claims it: the fund holdings lists have no reader, so the fund_holdings table is empty (build51-hold.md)."""
    assert R.recipe("lookthrough_exposure") is None
    assert not [r for r in R.recipes() if 69 in (r.get("cards") or [])]
    built = {x["id"] for p in (PACK / "builds").glob("*.yaml") for r in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("roles", []) for x in r.get("builds", [])}
    assert not built & set(UNBUILT)
