"""W1b Operate and control, cards 51 to 100 (docs/v3/w1/build51-operate.md), proved on the real pack readers.

Built (8): uc8-trades-vs-admin (trade_breaks, and fx_confirmation_variance from cash.yaml), uc-056-custrecon (position_break), uc-058-settle (unsettled_trades),
uc-059-breakage (break_age), uc-060-docinbox (unrecognised_files), uc-061-dqscore (source_quality), uc-062-fxlife (fx_mtm) and uc-099-newfeed (feed_mapping).
Their numbers come from the recipes' output on the office loaded by sh_platform/v1/v3_pack_readers (the `office` fixture of test_w2_loader.py) and are compared
with answer_keys.yaml, read from the file, never typed.
Not built (2): uc-057-pricecheck (no reader for market_data, no signed price tolerance) and uc-063-cashcode (no bank line carries a reference to match); the tests
below prove why and fail the day that changes.
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

BUILT = ["uc8-trades-vs-admin", "uc-056-custrecon", "uc-058-settle", "uc-059-breakage", "uc-060-docinbox", "uc-061-dqscore", "uc-062-fxlife", "uc-099-newfeed"]
NOT_BUILT = {  # card -> (the file kinds of its key that have no reader, recipe stub or None)
    "uc-057-pricecheck": ({"market_data"}, "price_gap_pct"),
    "uc-063-cashcode": (set(), None),  # every file is read; what is missing is a reference on the bank line (see the test)
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


def test_card51_a_failed_trade_of_the_settlement_report_is_not_a_desk_trade_break(office):
    """The settlement report adds Broker Two's two failed buys as transactions (A45); the administrator books no failed trade, so they are card 58's, not breaks."""
    rows = office.run("trade_breaks")
    assert not [r for r in rows if str(r["trade"]).startswith("BR2-")]


# ---- card 56: uc-056-custrecon ----------------------------------------------------------------------------------------------------------

def test_card56_the_statement_against_the_administrator_gives_the_two_breaks_of_the_key(office):
    exp = key("uc-056-custrecon")
    rows = office.run("position_break")
    assert len([r for r in rows if r["administrator_quantity"] is not None and r["custodian_quantity"] is not None]) == exp["holdings_compared"]
    breaks = [r for r in rows if r["breaks"]]
    assert sorted(r["security"] for r in breaks) == sorted(b["security"] for b in exp["breaks"])
    for b in exp["breaks"]:
        r = one(rows, security=b["security"])
        assert (r["administrator_quantity"], r["custodian_quantity"], r["difference_quantity"], f2(r["difference_value"]), r["reason"], r["break_kind"]) == (
            Decimal(b["administrator_qty"]), Decimal(b["custodian_qty"]), Decimal(b["difference"]), f2(b["value_usd"]), b["reason"], "quantity differs"), b["security"]
    assert {str(r["position_date"]) for r in rows} == {"2026-09-30"} and {r["currency"] for r in breaks} == {"USD"}


def test_card56_a_holding_the_custodian_does_not_list_is_missing_at_the_custodian(office):
    office.con.execute("create or replace temp table keep_f as select * from extracted_fields where field_name = 'custody_quantity' and value_text = 'Bay Street Utilities'")
    office.con.execute("delete from extracted_fields where field_name = 'custody_quantity' and value_text = 'Bay Street Utilities'")
    try:
        r = one([x for x in office.run("position_break") if x["security"] == "Bay Street Utilities"], security="Bay Street Utilities")
        assert r["break_kind"] == "missing at custodian" and r["breaks"] == 1 and r["custodian_quantity"] is None
    finally:
        office.con.execute("insert into extracted_fields select * from keep_f")


# ---- card 58: uc-058-settle -------------------------------------------------------------------------------------------------------------

def test_card58_the_failed_trades_late_amount_reason_and_broker_match_the_key(office):
    exp = key("uc-058-settle")
    rows = office.run("unsettled_trades")
    assert len(rows) == exp["count"] == 2
    for k in exp["failed"]:
        r = one(rows, trade=k["trade"])
        assert (r["security"], r["side"], r["quantity"], f2(r["amount"]), str(r["settle_date"]), r["business_days_late"], r["chase"], r["reason"], bool(r["cash_booked"])) == (
            k["security"], k["side"], Decimal(k["quantity"]), f2(k["amount"]), k["settle_date"], k["business_days_late"], k["chase"], k["reason"], k["cash_booked"]), k["trade"]
    assert sorted({r["chase"] for r in rows}) == exp["chase_counterparties"]
    settled = {r["external_trade_id"]: r["status"] for r in office.rows("select external_trade_id, status from transactions where external_trade_id in (" + ", ".join("?" * len(exp["settled_in_report"])) + ")", *exp["settled_in_report"])}
    assert settled == {t: "settled" for t in exp["settled_in_report"]} and not [r for r in rows if r["trade"] in settled]


# ---- card 59: uc-059-breakage -----------------------------------------------------------------------------------------------------------

def test_card59_every_open_break_its_age_and_the_cash_breaks_over_five_days_match_the_key(office):
    exp = key("uc-059-breakage")
    rows = office.run("break_age")
    assert sorted(r["break_id"] for r in rows) == sorted(b["id"] for b in exp["all_open"])
    for b in exp["all_open"]:
        r = one(rows, break_id=b["id"])
        assert (r["break_type"], r["entity"], r["subject"], str(r["detected"]), r["age_business_days"]) == (b["type"], b["entity"], b["subject"], b["detected"], b["age_business_days"]), b["id"]
    assert len([r for r in rows if r["break_type"] == "cash break"]) == exp["open_cash_breaks"]
    assert sorted(r["break_id"] for r in rows if r["break_type"] == "cash break" and r["over_five_business_days"]) == sorted(b["id"] for b in exp["cash_breaks_over_5_days"])


def test_card59_the_five_days_is_the_cards_question_not_a_signed_rule():
    r = R.recipe("break_age")
    assert "not a signed" in r["formula"] and "not a signed rule" in r["columns"]["over_five_business_days"]


# ---- card 60: uc-060-docinbox -----------------------------------------------------------------------------------------------------------

def test_card60_each_inbox_file_where_it_belongs_and_what_to_do_match_the_key(office):
    exp = key("uc-060-docinbox")
    rows = office.run("unrecognised_files")
    assert len(rows) == exp["files"]
    for k in exp["recognised"]:
        r = one(rows, file=k["file"])
        assert (r["recognition"], r["belongs_in"], r["status"]) == ("recognised", k["belongs_in"], "duplicate" if "duplicate" in k["action"] else "final"), k["file"]
        assert r["action"].split()[0].rstrip(",") == k["action"].split()[0].rstrip(","), k["file"]
    for k in exp["unrecognised"]:
        r = one(rows, file=k["file"])
        assert (r["recognition"], r["belongs_in"], r["unrecognised"], r["action"].split()[0]) == ("unrecognised", k["belongs_in"], 1, k["action"].split()[0]), k["file"]
    assert sum(r["unrecognised"] for r in rows) == len(exp["unrecognised"])


# ---- card 61: uc-061-dqscore ------------------------------------------------------------------------------------------------------------

def test_card61_the_score_of_every_source_and_the_one_to_fix_first_match_the_key(office):
    exp = key("uc-061-dqscore")
    rows = office.run("source_quality")
    assert sorted(r["source"] for r in rows) == sorted(s["source"] for s in exp["by_source"])
    for k in exp["by_source"]:
        r = one(rows, source=k["source"])
        assert (r["loads"], r["passed"], r["late_or_missing"], r["did_not_add_up"], r["manual_fixes"], float(r["score_pct"])) == (
            k["loads"], k["passed"], k["late_or_missing"], k["did_not_add_up"], k["manual_fixes"], float(k["score_pct"])), k["source"]
    assert [r["source"] for r in rows if r["fix_first"]] == [exp["fix_first"]]
    # a statement that never arrived has no batch: it is the expected statement still missing, one per source here
    assert {r["source"]: r["never_arrived"] for r in rows if r["never_arrived"]} == {"bank_statements": 1, "manager_statements": 1}


def test_card61_is_held_when_no_load_log_marked_a_batch(office):
    r = R.recipe("source_quality")
    assert R.needs(office.con, r) is None
    office.con.execute("create or replace temp table keep_b as select id, arrived_on_time from source_batches where arrived_on_time is not null")
    office.con.execute("update source_batches set arrived_on_time = null")
    try:
        assert R.needs(office.con, r)
    finally:
        office.con.execute("update source_batches set arrived_on_time = k.arrived_on_time from keep_b as k where k.id = source_batches.id")


# ---- card 99: uc-099-newfeed ------------------------------------------------------------------------------------------------------------

def test_card99_the_new_feed_columns_mapped_in_doubt_and_not_safe_match_the_key(office):
    exp = key("uc-099-newfeed")
    rows = [r for r in office.run("feed_mapping") if r["feed"].startswith("pinnacle")]
    assert len(rows) == exp["columns"]
    r0 = rows[0]
    assert (r0["columns"], r0["mapped_with_confidence"], r0["share_mapped_pct"], r0["rows_in_sample"], bool(r0["safe_to_go_live"])) == (
        exp["columns"], exp["mapped_with_confidence"], exp["share_mapped_pct"], exp["rows_in_sample"], exp["safe_to_go_live"])
    assert sorted(r["source_column"] for r in rows if r["in_doubt"]) == sorted(exp["in_doubt"])
    assert all(r["doubt_between"] for r in rows if r["in_doubt"])


# ---- the two cards that are not built: proof that the real readers cannot give them ------------------------------------------------------

def kinds_of(card: str) -> set[str]:
    return {m.group(1) for f in KEYS[card]["input_files"] if (m := re.match(r"(?:\*/)?([a-z_]+)/", f))}


@pytest.mark.parametrize("card", sorted(NOT_BUILT))
def test_every_unread_kind_of_an_unbuilt_card_is_still_unread(card, office):
    unread = {k for k in kinds_of(card) if k in office.report and "no reader for this kind" in office.report[k]["not_loaded"]}
    assert unread == NOT_BUILT[card][0], f"{card}: the kinds without a reader changed ({sorted(unread)}); build the card (docs/v3/w1/build51-operate.md)"
    assert office.one("select count(*) from source_batches where " + " or ".join(f"coalesce(storage_uri, '') like '%/{k}/%'" for k in sorted(unread) or ["__none__"])) == 0


@pytest.mark.parametrize("rid", ["price_gap_pct"])
def test_the_recipes_of_unbuilt_cards_stay_honest_stubs(rid):
    r = next((x for x in R.stubs() if x["id"] == rid), None)
    assert R.recipe(rid) is None and r is not None and r.get("status") == "stub" and not r.get("sql")


def test_card57_no_second_price_source_is_in_the_plane_and_no_tolerance_is_signed(office):
    assert {r["series_key"] for r in office.rows("select distinct series_key from market_observations")} == {"IDX:GLBD:SYN", "IDX:GLEQ:SYN", "USD/SGD", "FX:USDSGD:WMR4PM"}
    assert office.one("select count(*) from business_rules where rule_code like 'price%'") == 0  # price_tolerance_pct (A46) is named, not signed


def test_card63_the_three_unexplained_bank_lines_are_loaded_but_no_bank_line_carries_a_reference_to_match(office):
    """A45: an unexplained line is a bank line with no matching reference in the schedule, the ledger, the grants or a notice. The bank statement reader
    writes no reference and no payee on a bank line, so no line can be matched, and telling the three apart by their movement type would be an unsigned rule."""
    exp = key("uc-063-cashcode")
    for u in exp["uncoded"]:
        n = office.one("select count(*) from cash_movements where amount = ? and effective_date = ?", Decimal(str(u["amount"])), dt.date.fromisoformat(u["date"]))
        assert n >= 1, u
    assert office.one("select count(*) from cash_movements where confirmation_status = 'confirmed' and (reference is not null or payee_name is not null)") == 0
    assert office.one("select count(*) from business_rules where rule_code like '%purpose%' or rule_code like '%uncoded%'") == 0


# ---- recipes: shape ---------------------------------------------------------------------------------------------------------------------

OWN = ["trade_breaks", "fx_mtm", "position_break", "unsettled_trades", "break_age", "unrecognised_files", "source_quality", "feed_mapping"]


def test_every_recipe_of_the_slice_is_ready_and_reads_only_what_it_may():
    for rid in OWN:
        r = R.recipe(rid)
        assert r and r.get("status") != "stub" and r["sql"] and r["measure"] and r["grain"] and r["tie_out"] and r["cards"] and r["why"], rid
        assert R.refusal(r, R.render(r, "t")) is None, rid


def test_new_recipes_do_not_take_over_the_names_of_other_figures():
    for n in ["FX forward confirmation variance", "Cash break", "Net worth by portfolio", "Statements missing by fund", "Statement against administrator value", "Called to date",
              "Columns changed", "Statement timeliness", "Missing statements", "Notices open"]:
        assert (R.match({"name": n}) or {}).get("id") not in OWN, n
    for rid in OWN:
        assert (R.match({"name": R.recipe(rid)["label"]}) or {}).get("id") == rid, rid
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


EXPECTED = {  # id -> (figure, severity, hold, role)
    "uc8-trades-vs-admin-quantity-differs": ("trade_breaks", "problem", "accept_administrator_trades", "ops_clerk"),
    "uc8-trades-vs-admin-missing-at-administrator": ("trade_breaks", "problem", "accept_administrator_trades", "ops_clerk"),
    "uc8-trades-vs-admin-missing-at-desk": ("trade_breaks", "problem", "accept_administrator_trades", "ops_clerk"),
    "uc8-trades-vs-admin-booked-twice": ("trade_breaks", "needs", None, "ops_clerk"),
    "uc8-trades-vs-admin-fx-confirmation-differs": ("fx_confirmation_variance", "problem", "settle_forward", "ops_clerk"),
    "uc-056-custrecon-quantity-differs": ("position_break", "problem", "accept_administrator_positions", "ops_lead"),
    "uc-056-custrecon-missing-one-side": ("position_break", "problem", "accept_administrator_positions", "ops_lead"),
    "uc-058-settle-failed": ("unsettled_trades", "problem", "release_trade_cash", "ops_clerk"),
    "uc-058-settle-late": ("unsettled_trades", "needs", None, "ops_clerk"),
    "uc-059-breakage-to-finance": ("break_age", "problem", None, "ops_lead"),
    "uc-059-breakage-open": ("break_age", "info", None, "ops_lead"),
    "uc-060-docinbox-unrecognised": ("unrecognised_files", "problem", "load_inbox_file", "ops_clerk"),
    "uc-060-docinbox-duplicate": ("unrecognised_files", "info", None, "ops_clerk"),
    "uc-060-docinbox-new": ("unrecognised_files", "needs", None, "ops_clerk"),
    "uc-061-dqscore-fix-first": ("source_quality", "problem", None, "head_of_data"),
    "uc-061-dqscore-never-arrived": ("source_quality", "needs", None, "head_of_data"),
    "uc-062-fxlife-marked": ("fx_mtm", "info", None, "ops_clerk"),
    "uc-062-fxlife-due-soon": ("fx_mtm", "needs", None, "ops_clerk"),
    "uc-062-fxlife-confirmation-differs": ("fx_mtm", "problem", "settle_forward", "ops_clerk"),
    "uc-062-fxlife-no-confirmation": ("fx_mtm", "problem", "settle_forward", "ops_clerk"),
    "uc-099-newfeed-in-doubt": ("feed_mapping", "problem", "load_new_feed", "head_of_data"),
}
NO_HOLD = {"uc-059-breakage", "uc-061-dqscore"}  # the story is a hand-over (to Finance) or a score; nothing waits on it
ROW_ID = {"trade_breaks": "trade", "fx_mtm": "trade", "fx_confirmation_variance": "trade_reference", "position_break": "security", "unsettled_trades": "trade",
          "break_age": "break_id", "unrecognised_files": "file", "source_quality": "source", "feed_mapping": "source_column"}


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
    for sid, (fig, sev, hold, role) in EXPECTED.items():
        s = sigs[sid]
        assert s["_file"] == f"{sid}.yaml" and s["suggestion"] is True and s["subject"] and s["message"] and s["pain_points"]
        assert S.check(s, {r: r for r in roles}) is None, (sid, S.check(s, {r: r for r in roles}))
        assert s["trigger"] == {"on": "figure_changed", "figure": fig} and s["severity"] == sev and s["route_to"] == role, sid
        assert (s.get("hold") or {}).get("blocks") == hold and (not hold or (s["hold"]["scope"] and s["hold"]["until"])), sid
        assert not re.search(r"\b(Sam|Helen|Raj|Mei|Daniel|Grace|Sofia|Anita)\b", yaml.safe_dump(s)), sid  # a role, never a person
        tree = ast.parse(str(s["condition"]), mode="eval")
        assert all(n.func.id in {"abs", "min", "max", "round", "last4", "num", "same_fund"} for n in ast.walk(tree) if isinstance(n, ast.Call))
    for card in BUILT:
        assert any(sid.startswith(card + "-") and EXPECTED[sid][1] == "problem" and (EXPECTED[sid][2] or card in NO_HOLD) for sid in EXPECTED), card


def test_signal_fields_are_columns_of_the_figure_they_watch(office):
    for fig in ROW_ID:
        office.run(fig)
    for sid, s in signals().items():
        have = {r["column_name"] for r in office.rows(f"select column_name from information_schema.columns where table_name = 't_{s['trigger']['figure']}'")}
        want = {f for i in s["inputs"] if i["kind"] == "doc" for f in i["fields"]}
        assert want <= have, (sid, want - have)
        for name in re.findall(r"\{doc\.([a-z_]+)", s["message"] + s["subject"] + (s.get("hold") or {}).get("scope", "")):
            assert name in want, (sid, name)


def test_each_signal_fires_on_exactly_the_rows_of_the_key(office):
    sigs = signals()
    rows = {fig: office.run(fig) for fig in ROW_ID}

    def who(sid):
        fig = sigs[sid]["trigger"]["figure"]
        return sorted(r[ROW_ID[fig]] for r in rows[fig] if fires(sigs[sid], r))

    assert who("uc8-trades-vs-admin-quantity-differs") == ["T-20261002-003"]
    assert who("uc8-trades-vs-admin-missing-at-administrator") == ["T-20261006-005"]
    assert who("uc8-trades-vs-admin-missing-at-desk") == []
    assert who("uc8-trades-vs-admin-booked-twice") == ["T-20260602-005"]
    assert who("uc8-trades-vs-admin-fx-confirmation-differs") == ["FXF-2026-002"]
    assert who("uc-056-custrecon-quantity-differs") == sorted(b["security"] for b in key("uc-056-custrecon")["breaks"])
    assert who("uc-056-custrecon-missing-one-side") == []
    assert who("uc-058-settle-failed") == sorted(f["trade"] for f in key("uc-058-settle")["failed"])
    assert who("uc-058-settle-late") == []
    assert who("uc-059-breakage-to-finance") == sorted(b["id"] for b in key("uc-059-breakage")["cash_breaks_over_5_days"])
    assert who("uc-059-breakage-open") == sorted(b["id"] for b in key("uc-059-breakage")["all_open"])
    assert who("uc-060-docinbox-unrecognised") == sorted(f["file"] for f in key("uc-060-docinbox")["unrecognised"])
    assert who("uc-060-docinbox-duplicate") == sorted(f["file"] for f in key("uc-060-docinbox")["recognised"] if "duplicate" in f["action"])
    assert who("uc-060-docinbox-new") == sorted(f["file"] for f in key("uc-060-docinbox")["recognised"] if "duplicate" not in f["action"])
    assert who("uc-061-dqscore-fix-first") == [key("uc-061-dqscore")["fix_first"]]
    assert who("uc-061-dqscore-never-arrived") == ["bank_statements", "manager_statements"]
    assert who("uc-062-fxlife-marked") == ["FXF-2026-001", "FXF-2026-002"]
    assert who("uc-062-fxlife-due-soon") == []
    assert who("uc-062-fxlife-confirmation-differs") == ["FXF-2026-002"]
    assert who("uc-062-fxlife-no-confirmation") == []
    assert who("uc-099-newfeed-in-doubt") == sorted(key("uc-099-newfeed")["in_doubt"])


def _msg(sig: dict, row: dict) -> str:
    return S.render(sig["message"], {"doc": {k: (v if isinstance(v, (str, dt.date)) else S.num(v)) for k, v in row.items() if v is not None}})


def test_the_messages_carry_the_numbers_of_the_key(office):
    sigs = signals()
    rows = {r["trade"]: r for r in office.run("trade_breaks") if r["breaks"]}
    msg = _msg(sigs["uc8-trades-vs-admin-quantity-differs"], rows["T-20261002-003"])
    assert "12,000" in msg and "10,200" in msg and "75,870" in msg and "-1,800" in msg and "{" not in msg
    msg = _msg(sigs["uc-062-fxlife-marked"], one(office.run("fx_mtm"), trade="FXF-2026-002"))
    assert "5,597" in msg and "1.3400" in msg and "2027-01-05" in msg and "{" not in msg
    msg = _msg(sigs["uc-056-custrecon-quantity-differs"], one(office.run("position_break"), security="Bay Street Utilities"))
    assert "40,000" in msg and "41,250" in msg and "-60,062.50" in msg and "{" not in msg
    msg = _msg(sigs["uc-058-settle-failed"], one(office.run("unsettled_trades"), trade="BR2-20261002-001"))
    assert "281,150" in msg and "Synthetic Broker Two" in msg and "seller short delivery" in msg and "5 business days" in msg and "{" not in msg
    msg = _msg(sigs["uc-061-dqscore-fix-first"], one(office.run("source_quality"), source="administrator_cash"))
    assert "5 of 7" in msg and "71.4" in msg and "{" not in msg
    msg = _msg(sigs["uc-099-newfeed-in-doubt"], one(office.run("feed_mapping"), source_column="Dt"))
    assert "8 of 10" in msg and "Dt" in msg and "{" not in msg


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
