"""W1b Operate and control, cards 51 to 100 (docs/v3/w1/build51-operate.md), proved on the real pack readers.

Built: uc8-trades-vs-admin (recipe trade_breaks, and fx_confirmation_variance from cash.yaml) and uc-062-fxlife (recipe fx_mtm). Their numbers come from the recipes' output on
the office loaded by sh_platform/v1/v3_pack_readers (the `office` fixture of test_w2_loader.py) and are compared with answer_keys.yaml, read from the file, never typed.
Not built (8): each reads a file kind the pack has no reader for, or a fact no table holds; the tests below prove why and fail the day a card's files are all read.
Synthetic data only."""
from __future__ import annotations

import ast
import datetime as dt
import glob
import importlib.util
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import v3_signals as S

_SPEC = importlib.util.spec_from_file_location("w2_loader_tests", Path(__file__).with_name("test_w2_loader.py"))
W2 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(W2)
key, f2, one, TODAY, KEYS, OFFICE = W2.key, W2.f2, W2.one, W2.TODAY, W2.KEYS, W2.OFFICE
office = W2.office  # the module fixture: the office files loaded through the real readers
PACK = W2.REPO / "packs" / "family_office" / "1"

BUILT = ["uc8-trades-vs-admin", "uc-062-fxlife"]
NOT_BUILT = {  # card -> (the file kinds of its key that have no reader, recipe stub or None)
    "uc-056-custrecon": ({"custody_statements"}, "position_break"),
    "uc-057-pricecheck": ({"market_data"}, "price_gap_pct"),
    "uc-058-settle": ({"settlement_status"}, "unsettled_trades"),
    "uc-059-breakage": ({"break_register"}, None),
    "uc-060-docinbox": ({"inbox"}, None),
    "uc-061-dqscore": ({"load_log"}, "source_quality"),
    "uc-063-cashcode": (set(), None),  # every file is read; what is missing is a purpose on the bank line (see the test)
    "uc-099-newfeed": ({"new_feed"}, None),
}


# ---- card 51: uc8-trades-vs-admin -------------------------------------------------------------------------------------------------------

def test_card51_trade_breaks_match_the_key(office):
    exp = key("uc8-trades-vs-admin")
    rows = office.run("trade_breaks")
    breaks = {(r["trade"], r["break_kind"]): r for r in rows if r["breaks"]}
    q = {b["trade"]: b for b in exp["october_trade_breaks"]}
    nwl = breaks[("T-20261002-003", "quantity differs")]
    k = q["T-20261002-003"]
    assert (nwl["our_quantity"], nwl["administrator_quantity"], nwl["difference_amount"], nwl["security"]) == (Decimal(k["ours"]), Decimal(k["administrator"]), Decimal(k["difference_usd"]), "Northwind Logistics")
    hvs = breaks[("T-20261006-005", "missing at administrator")]
    k = q["T-20261006-005"]
    assert (hvs["difference_amount"], hvs["currency"]) == (Decimal(k["amount"]), "USD") and hvs["administrator_quantity"] is None
    twice = [r["trade"] for r in rows if r["break_kind"] == "booked twice"]
    assert twice == exp["trade_booked_twice_in_export"]
    # nothing else is a break: the three of the key, over the whole six months
    assert sorted(breaks) == sorted([("T-20261002-003", "quantity differs"), ("T-20261006-005", "missing at administrator"), ("T-20260602-005", "booked twice")])
    assert not [r for r in rows if r["break_kind"] in ("missing at our desk", "awaiting administrator file")]
    assert sum(1 for r in rows if r["break_kind"] == "matches") == 21 - 2  # 21 buys and sells, two of them are breaks


def test_card51_the_fx_forward_confirmation_variance_is_the_key(office):
    exp = key("uc8-trades-vs-admin")
    rows = office.run("fx_confirmation_variance")
    r = one(rows, trade_reference=exp["fx_forward"])
    assert (r["variance"], r["currency"]) == (Decimal(exp["difference_sgd"]), "SGD")
    assert r["confirmed_amount"] - r["trade_amount"] == r["variance"]  # confirmed 3,000,000 x 1.3452 less booked 3,000,000 x 1.3425 (the key's two rates)
    assert (Decimal(exp["confirmed_rate"]) - Decimal(exp["booked_rate"])) * 3_000_000 == r["variance"]


def test_card51_a_trade_with_no_administrator_file_for_its_month_is_not_called_missing(office):
    """The October file lists 5 trades; a desk trade of a month with no administrator file would be 'awaiting', never 'missing'."""
    office.con.execute("create or replace temp table keep_docs as select * from documents where document_type = 'administrator_trades' and valuation_date >= date '2026-10-01'")
    office.con.execute("delete from documents where document_type = 'administrator_trades' and valuation_date >= date '2026-10-01'")
    try:
        rows = office.run("trade_breaks")
        oct6 = one(rows, trade="T-20261006-005")
        assert oct6["break_kind"] == "awaiting administrator file" and oct6["breaks"] == 0
    finally:
        office.con.execute("insert into documents select * from keep_docs")


# ---- card 62: uc-062-fxlife -------------------------------------------------------------------------------------------------------------

def test_card62_forwards_mark_to_market_match_the_key(office):
    exp = key("uc-062-fxlife")
    rows = office.run("fx_mtm")
    assert len(rows) == len(exp["forwards"]) == 2
    for k in exp["forwards"]:
        r = one(rows, trade=k["id"])
        assert (str(r["value_date"]), r["days_to_value"], r["buy_amount"], r["sell_amount"], float(r["contract_rate"]), float(r["spot"]), f2(r["mtm_usd"])) == (
            k["value_date"], k["days_to_value"], Decimal(k["buy_sgd"]), Decimal(k["sell_usd"]), k["contract_rate"], k["spot"], k["mtm_usd"]), k["id"]
        assert r["confirmation_status"] == k["confirmation_status"] and r["buy_currency"] == "SGD"
    assert [r["trade"] for r in rows if r["due_within_30_days"]] == [x["id"] for x in exp["due_within_30_days"]] == []
    assert sum(r["usd_to_deliver"] for r in rows) == Decimal(exp["total_usd_to_deliver"])
    assert str(min(r["value_date"] for r in rows)) == exp["next_value_date"]


def test_card62_the_trust_usd_cash_leg_gives_the_key_shortfall(office):
    """The recipe gives the USD to deliver; the Trust's USD cash is the cash_by_entity figure. Together they are the key's shortfall (the recipe does not join them)."""
    exp = key("uc-062-fxlife")
    deliver = sum(r["usd_to_deliver"] for r in office.run("fx_mtm"))
    cash = one([r for r in office.run("cash_by_entity") if str(r["position_date"]) == TODAY], entity="Evergreen Family Trust", currency="USD")["cash"]
    assert f2(cash) == exp["trust_usd_cash"] and f2(deliver - cash) == exp["trust_usd_shortfall"]


def test_card62_a_forward_without_a_rate_is_held_and_one_without_a_confirmation_says_none(office):
    r = R.recipe("fx_mtm")
    assert R.needs(office.con, r) is None
    office.con.execute("create or replace temp table keep_conf as select * from fx_confirmations where trade_reference = 'FXF-2026-001'")
    office.con.execute("delete from fx_confirmations where trade_reference = 'FXF-2026-001'")
    try:
        assert one(office.run("fx_mtm"), trade="FXF-2026-001")["confirmation_status"] == "none"
    finally:
        office.con.execute("insert into fx_confirmations select * from keep_conf")


# ---- the eight cards that are not built: proof that the real readers cannot give them ------------------------------------------------------

def kinds_of(card: str) -> set[str]:
    return {m.group(1) for f in KEYS[card]["input_files"] if (m := re.match(r"(?:\*/)?([a-z_]+)/", f))}


@pytest.mark.parametrize("card", sorted(NOT_BUILT))
def test_every_unread_kind_of_an_unbuilt_card_is_still_unread(card, office):
    unread = {k for k in kinds_of(card) if k in office.report and "no reader for this kind" in office.report[k]["not_loaded"]}
    assert unread == NOT_BUILT[card][0], f"{card}: the kinds without a reader changed ({sorted(unread)}); build the card (docs/v3/w1/build51-operate.md)"
    assert office.one("select count(*) from source_batches where " + " or ".join(f"coalesce(storage_uri, '') like '%/{k}/%'" for k in sorted(unread) or ["__none__"])) == 0


@pytest.mark.parametrize("rid", ["position_break", "price_gap_pct", "unsettled_trades", "source_quality"])
def test_the_recipes_of_unbuilt_cards_stay_honest_stubs(rid):
    r = next((x for x in R.stubs() if x["id"] == rid), None)
    assert R.recipe(rid) is None and r is not None and r.get("status") == "stub" and not r.get("sql")


def test_card56_the_custodian_daily_file_and_the_administrator_agree_the_two_breaks_are_only_in_the_statement_pdf(office):
    """The key's two breaks (Bay Street +1,250 units, Redwood Pharma -400) are on the custodian's safekeeping statement (a PDF kind with no reader); the daily
    custodian file the loader reads agrees with the administrator on 30 September, so a recipe over the plane would report no break at all."""
    exp = key("uc-056-custrecon")
    rows = office.rows("select i.canonical_name as n, c.quantity as cq, a.quantity as aq from position_snapshots as c join source_records as r on r.id = c.source_record_id "
                       "join source_batches as b on b.id = r.source_batch_id join source_systems as s on s.id = b.source_system_id join position_snapshots as a on a.instrument_id = c.instrument_id "
                       "and a.portfolio_id = c.portfolio_id and a.position_date = c.position_date join source_records as r2 on r2.id = a.source_record_id join source_batches as b2 on b2.id = r2.source_batch_id "
                       "join source_systems as s2 on s2.id = b2.source_system_id join instruments as i on i.id = c.instrument_id where s.source_type = 'custodian' and s2.source_type = 'administrator' "
                       "and c.position_date = date '2026-09-30' and c.view_type = 'operational' and a.view_type = 'accounting'")
    assert len(rows) == exp["holdings_compared"] == 20
    assert not [r for r in rows if r["cq"] != r["aq"]] and len(exp["breaks"]) == 2


def test_card57_no_second_price_source_is_in_the_plane(office):
    assert {r["series_key"] for r in office.rows("select distinct series_key from market_observations")} == {"IDX:GLBD:SYN", "IDX:GLEQ:SYN", "USD/SGD", "FX:USDSGD:WMR4PM"}
    assert office.one("select count(*) from business_rules where rule_code like 'price%'") == 0  # and no signed price tolerance (the 0.5 percent is in the card text only)


def test_card58_no_trade_has_failed_to_settle_in_the_plane(office):
    assert office.one("select count(*) from transactions where status not in ('settled', 'executed', 'rejected')") == 0
    assert office.one("select count(*) from transactions where external_trade_id like 'BR2-%'") == 0  # the key's two failed trades are Broker Two's, only in the settlement report
    assert len(key("uc-058-settle")["failed"]) == 2


def test_card59_the_plane_holds_three_of_the_six_open_breaks_of_the_register(office):
    assert office.one("select count(*) from exceptions where exception_type = 'cash_break' and status = 'open'") == 3
    assert len(key("uc-059-breakage")["all_open"]) == 6 and key("uc-059-breakage")["open_cash_breaks"] == 4
    assert office.one("select count(*) from business_rules where rule_code like '%break_age%'") == 0  # the five days is in the card text only


def test_card60_and_61_have_no_inbox_and_no_load_log_in_the_plane(office):
    assert office.one("select count(*) from documents where original_filename in ('IMG_2210.pdf', 'data_export.xlsx', 'scan_0412.pdf', 'account_extract.xlsx')") == 0
    assert office.one("select count(*) from source_batches where validation_status not in ('loaded', 'validated')") == 0  # no batch carries a late, failed or fixed-by-hand mark


def test_card63_the_three_unexplained_bank_lines_are_loaded_but_nothing_says_they_have_no_purpose(office):
    exp = key("uc-063-cashcode")
    for u in exp["uncoded"]:
        n = office.one("select count(*) from cash_movements where amount = ? and effective_date = ?", Decimal(str(u["amount"])), dt.date.fromisoformat(u["date"]))
        assert n >= 1, u
    assert office.one("select count(*) from business_rules where rule_code like '%purpose%' or rule_code like '%uncoded%'") == 0
    # the columns of a cash movement hold no purpose or counterparty name: telling these three lines from a coded one needs a rule nobody has signed
    cols = {r["column_name"] for r in office.rows("select column_name from information_schema.columns where table_name = 'cash_movements'")}
    assert not cols & {"purpose", "counterparty", "counterparty_name", "payee"}


def test_card99_the_new_feed_is_not_in_the_plane(office):
    assert office.one("select count(*) from sheet_mapping_columns where source_column in ('SecRef', 'Dt')") == 0
    assert key("uc-099-newfeed")["in_doubt"] == ["Value", "Dt"]


# ---- recipes: shape ---------------------------------------------------------------------------------------------------------------------

OWN = ["trade_breaks", "fx_mtm"]


def test_every_recipe_of_the_slice_is_ready_and_reads_only_what_it_may():
    for rid in OWN:
        r = R.recipe(rid)
        assert r and r.get("status") != "stub" and r["sql"] and r["measure"] and r["grain"] and r["tie_out"] and r["cards"] and r["why"], rid
        assert R.refusal(r, R.render(r, "t")) is None, rid


def test_new_recipes_do_not_take_over_the_names_of_other_figures():
    for n in ["FX forward confirmation variance", "Cash break", "Net worth by portfolio", "Statements missing by fund", "Statement against administrator value", "Called to date"]:
        assert (R.match({"name": n}) or {}).get("id") not in OWN, n
    assert (R.match({"name": "Trade breaks"}) or {}).get("id") == "trade_breaks"
    assert (R.match({"name": "FX forwards mark to market"}) or {}).get("id") == "fx_mtm"


# ---- signals and builds -----------------------------------------------------------------------------------------------------------------

def signals() -> dict[str, dict]:
    out = {}
    for card in BUILT:
        for p in sorted((PACK / "signals").glob(f"{card}-*.yaml")):
            s = yaml.safe_load(p.read_text(encoding="utf-8"))
            s["trigger"] = {("on" if k is True else k): v for k, v in s["trigger"].items()}  # YAML 1.1 reads a bare `on` as true; the engine does the same
            s["_file"] = p.name
            out[s["id"]] = s
    return out


def role_ids() -> set[str]:
    ids = {r["id"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"]}
    for p in (PACK / "builds").glob("*.yaml"):
        ids |= {r["id"] for r in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("roles") or []}
    return ids


EXPECTED = {  # id -> (figure, severity, hold)
    "uc8-trades-vs-admin-quantity-differs": ("trade_breaks", "problem", "accept_administrator_trades"),
    "uc8-trades-vs-admin-missing-at-administrator": ("trade_breaks", "problem", "accept_administrator_trades"),
    "uc8-trades-vs-admin-missing-at-desk": ("trade_breaks", "problem", "accept_administrator_trades"),
    "uc8-trades-vs-admin-booked-twice": ("trade_breaks", "needs", None),
    "uc8-trades-vs-admin-fx-confirmation-differs": ("fx_confirmation_variance", "problem", "settle_forward"),
    "uc-062-fxlife-marked": ("fx_mtm", "info", None),
    "uc-062-fxlife-due-soon": ("fx_mtm", "needs", None),
    "uc-062-fxlife-confirmation-differs": ("fx_mtm", "problem", "settle_forward"),
    "uc-062-fxlife-no-confirmation": ("fx_mtm", "problem", "settle_forward"),
}


def fires(sig: dict, row: dict) -> bool:
    """The condition on one row of the figure the signal watches, as the engine reads it (a missing field skips the signal)."""
    need = [f for i in sig["inputs"] if i["kind"] == "doc" for f in i["fields"]]
    if any(row.get(f) in (None, "") for f in need):
        return False
    funcs = {"abs": abs, "min": min, "max": max, "round": round, "last4": S.last4, "num": S.num}
    ns = {"doc": {f: row[f] if isinstance(row[f], (dt.date, Decimal, str)) else S._dec(row[f]) for f in need}}
    return bool(S.calc(sig["condition"], ns, funcs))


def test_signals_follow_the_engine_format_have_a_role_and_an_exception_with_a_hold():
    sigs = signals()
    assert set(sigs) == set(EXPECTED)
    roles = role_ids()
    for sid, (fig, sev, hold) in EXPECTED.items():
        s = sigs[sid]
        assert s["_file"] == f"{sid}.yaml" and s["suggestion"] is True and s["subject"] and s["message"] and s["pain_points"]
        assert S.check(s, {r: r for r in roles}) is None, (sid, S.check(s, {r: r for r in roles}))
        assert s["trigger"] == {"on": "figure_changed", "figure": fig} and s["severity"] == sev and s["route_to"] == "ops_clerk", sid
        assert (s.get("hold") or {}).get("blocks") == hold and (not hold or (s["hold"]["scope"] and s["hold"]["until"])), sid
        assert not re.search(r"\b(Sam|Helen|Raj|Mei|Daniel|Grace|Sofia)\b", yaml.safe_dump(s)), sid  # a role, never a person
        tree = ast.parse(str(s["condition"]), mode="eval")
        assert all(n.func.id in {"abs", "min", "max", "round", "last4", "num", "same_fund"} for n in ast.walk(tree) if isinstance(n, ast.Call))
    for card in BUILT:
        assert any(sid.startswith(card + "-") and EXPECTED[sid][1] == "problem" and EXPECTED[sid][2] for sid in EXPECTED), card


def test_signal_fields_are_columns_of_the_figure_they_watch(office):
    for fig in ("trade_breaks", "fx_mtm", "fx_confirmation_variance"):
        office.run(fig)
    for sid, s in signals().items():
        have = {r["column_name"] for r in office.rows(f"select column_name from information_schema.columns where table_name = 't_{s['trigger']['figure']}'")}
        want = {f for i in s["inputs"] if i["kind"] == "doc" for f in i["fields"]}
        assert want <= have, (sid, want - have)
        for name in re.findall(r"\{doc\.([a-z_]+)", s["message"] + s["subject"] + (s.get("hold") or {}).get("scope", "")):
            assert name in want, (sid, name)


def test_each_signal_fires_on_exactly_the_rows_of_the_key(office):
    sigs = signals()
    rows = {fig: office.run(fig) for fig in ("trade_breaks", "fx_mtm", "fx_confirmation_variance")}

    def who(sid):
        s = sigs[sid]
        return sorted(r.get("trade") or r.get("trade_reference") for r in rows[s["trigger"]["figure"]] if fires(s, r))

    assert who("uc8-trades-vs-admin-quantity-differs") == ["T-20261002-003"]
    assert who("uc8-trades-vs-admin-missing-at-administrator") == ["T-20261006-005"]
    assert who("uc8-trades-vs-admin-missing-at-desk") == []
    assert who("uc8-trades-vs-admin-booked-twice") == ["T-20260602-005"]
    assert who("uc8-trades-vs-admin-fx-confirmation-differs") == ["FXF-2026-002"]
    assert who("uc-062-fxlife-marked") == ["FXF-2026-001", "FXF-2026-002"]
    assert who("uc-062-fxlife-due-soon") == []
    assert who("uc-062-fxlife-confirmation-differs") == ["FXF-2026-002"]
    assert who("uc-062-fxlife-no-confirmation") == []


def test_the_messages_carry_the_numbers_of_the_key(office):
    sigs = signals()
    rows = {r["trade"]: r for r in office.run("trade_breaks") if r["breaks"]}
    ns = {"doc": {k: (v if isinstance(v, (str, dt.date)) else S.num(v)) for k, v in rows["T-20261002-003"].items() if v is not None}}
    msg = S.render(sigs["uc8-trades-vs-admin-quantity-differs"]["message"], ns)
    assert "12,000" in msg and "10,200" in msg and "75,870" in msg and "-1,800" in msg and "{" not in msg
    fx = one(office.run("fx_mtm"), trade="FXF-2026-002")
    msg = S.render(sigs["uc-062-fxlife-marked"]["message"], {"doc": {k: (v if isinstance(v, (str, dt.date)) else S.num(v)) for k, v in fx.items() if v is not None}})
    assert "5,597" in msg and "1.3400" in msg and "2027-01-05" in msg and "{" not in msg


def test_builds_are_the_built_cards_only_and_expect_numbers_from_the_key():
    builds = yaml.safe_load((PACK / "builds" / "operate-51.yaml").read_text(encoding="utf-8"))
    ids = []
    for role in builds["roles"]:
        assert role["id"] in role_ids()
        for b in role["builds"]:
            ids.append(b["id"])
            assert b["say"] and b["files"] and all(f.startswith("office6m:") for f in b["files"]) and b["check"]["ask"] and b["check"]["expect"]
            assert all(glob.glob(str(OFFICE / f[len("office6m:"):])) for f in b["files"]), b["id"]
            blob = json.dumps(KEYS[b["id"]]["questions"], default=str).replace(",", "")
            for e in b["check"]["expect"]:
                assert e.replace(",", "") in blob, (b["id"], e)
                assert len(e.replace(",", "")) > 2, (b["id"], e)
    assert sorted(ids) == sorted(BUILT)
