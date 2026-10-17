"""W1b hold: the recipe of the one "Hold and maintain" card of 51 to 100 that could be built (64, currency exposure), run on the real loader's warehouse and compared
with answer_keys.yaml. The six others (55, 65, 66, 67, 68, 69) are unbuilt because their tables or readers do not exist yet (docs/v3/w1/build51-hold.md, Needs).

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
UNBUILT = ["uc-055-corpact", "uc-065-realassets", "uc-066-propreval", "uc-067-unrl", "uc-068-incomef", "uc-069-lookthru"]


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


def test_64_signals_are_well_formed():
    mine = sorted((PACK / "signals").glob(CARD + "-*.yaml"))
    docs = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in mine]
    assert len(docs) == 3
    assert any(s["severity"] != "info" and s.get("hold") for s in docs), "an exception signal with a hold"
    for p, s in zip(mine, docs):
        assert s["id"] == p.stem and s["suggestion"] is True and s["route_to"] in ROLES
        assert s["severity"] in {"info", "needs", "problem"} and s["action"]["verb"] in {"log", "record", "approve", "call_back", "see"}
        for i in s["inputs"]:
            if i.get("recipe"):
                assert R.recipe(i["recipe"])


# ---- the build and the unbuilt cards ------------------------------------------------------------------------------------------------------

def test_64_the_build_carries_the_exact_answer_keys():
    b = yaml.safe_load((PACK / "builds" / "hold-51.yaml").read_text(encoding="utf-8"))
    builds = {x["id"]: (r["id"], x) for r in b["roles"] for x in r["builds"]}
    assert set(builds) == {CARD}
    role, x = builds[CARD]
    assert role in ROLES and x["say"] and x["files"] and x["check"]["ask"] and x["check"]["expect"]
    assert all(f.startswith("office6m:") and glob.glob(str(OFFICE / f[9:])) for f in x["files"])
    have = list(leaves(KEYS[CARD]["questions"]))
    numbers = [float(v) for v in have if isinstance(v, (int, float)) and not isinstance(v, bool)]
    for e in x["check"]["expect"]:
        assert any(abs(float(e.replace(",", "")) - v) < 1e-9 for v in numbers), e


def test_the_other_six_cards_are_honestly_unbuilt():
    """No recipe claims them: each needs a table or a reader that is not there (build51-hold.md). The stub of the income forecast stays a stub."""
    stub = next(r for r in yaml.safe_load((PACK / "recipes" / "hold.yaml").read_text(encoding="utf-8"))["recipes"] if r["id"] == "income_forecast")
    assert stub["status"] == "stub" and stub["sql"] is None and R.recipe("income_forecast") is None
    built = {x["id"] for p in (PACK / "builds").glob("*.yaml") for r in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("roles", []) for x in r.get("builds", [])}
    assert not built & set(UNBUILT)
