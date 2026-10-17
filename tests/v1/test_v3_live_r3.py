"""Live run 3 regressions (docs/v3/LIVE-R3-ANALYSIS.md): uc-002, uc-004, uc-006, uc-007, uc-008, uc-018, uc-034, uc6-uncalled.

Cause: one unreadable inbox file failed the intake batch, which was then read kind by kind. The notices were read apart from the commitments
registers and bank statements they are matched with: call notices were posted to the clean office's stub commitments (replaced later by the
register rows) and no bank payment confirmed them, so 3.6M of paid calls stayed open as past due. Each case is that warehouse, recreated on the
office6m files loaded through the real readers (test_w2_loader.py's `office`) inside a transaction that is rolled back, asked its live question.
Synthetic data only."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_pack_readers as PK
from sh_platform.v1 import v3_recipes as R


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


W2 = _load("w2_loader_tests_r3", "test_w2_loader.py")
W3 = _load("w3_intake_tests_r3", "test_w3_intake.py")
office = W2.office

# the r3 warehouse: every call notice on the oldest row of its commitment's chain, and no bank confirmation read with it
R3_NOTICES = ("update cash_movements set commitment_id = (with recursive up(id) as (select cash_movements.commitment_id union all select c.supersedes_commitment_id "
              "from up join commitments as c on c.id = up.id where c.supersedes_commitment_id is not null) select id from up where not exists "
              "(select 1 from commitments as c where c.id = up.id and c.supersedes_commitment_id is not null)) where notice_kind = 'capital_call' and commitment_id is not null")
R3_UNPAID = "delete from cash_movements where notice_kind = 'capital_call' and confirmation_status = 'confirmed' and supersedes_cash_movement_id is not null"


def _r3(o, rids: list[str]) -> dict[str, tuple[list[dict], str]]:
    """Each recipe's rows and answer on the r3 warehouse."""
    o.con.execute("begin")
    try:
        assert o.one("select count(*) from cash_movements where notice_kind = 'capital_call' and confirmation_status = 'confirmed'") > 0
        o.con.execute(R3_NOTICES)
        o.con.execute(R3_UNPAID)
        out = {}
        for rid in rids:
            rows = o.run(rid)
            out[rid] = (rows, F.say(R.recipe(rid), rows) or "")
    finally:
        o.con.execute("rollback")
    return out


def _has(text: str, *keys: str) -> None:
    for k in keys:
        assert k in text, (k, text)


# ---- uc-002, uc6-uncalled, uc-007, uc-034: a notice posted to a replaced commitment row counts for the row that replaced it --------------------

def test_uc002_does_call_7_fit_cedarpoint_ventures_iii(office):
    ask = "Does call 7 fit what we committed to Cedarpoint Ventures III, and what is left after it?"
    rows, said = _r3(office, ["called_to_date"])["called_to_date"]
    cv = next(r for r in rows if r["fund"] == "Cedarpoint Ventures III")
    assert cv["investor"] == "Evergreen Holdings" and float(cv["noticed_not_recorded"]) == 1250000  # r3: 0, the notice was on a stub of Entity B
    _has(said, "10,000,000", "6,000,000", "7,250,000", "2,750,000")
    assert ask


def test_uc6_uncalled_and_uc007_unfunded_across_all_funds(office):
    out = _r3(office, ["called_to_date", "commitments_by_fund"])
    rows, said = out["called_to_date"]
    # uc6: "How much is uncalled across all commitments?" r3 said 15,850,000 before and after; r2 said the call and its rows held the totals
    assert (sum(float(r["unfunded_after_notice"]) for r in rows), sum(float(r["unfunded_before_notice"]) for r in rows)) == (14600000, 15850000)
    _has(said, "7,250,000", "2,750,000")
    rows, said = out["commitments_by_fund"]
    total = next(r for r in rows if r["is_total"])
    assert float(total["unfunded"]) == 14600000  # uc-007: "What's our unfunded commitment across all funds?"
    _has(said, "14,600,000")
    assert float(next(r for r in rows if r["fund"] == "Cedarpoint Ventures III")["unfunded"]) == 2750000


def test_uc034_harborlight_ticket_against_what_is_uncalled(office):
    rows, _ = _r3(office, ["mandate_fit"])["mandate_fit"]  # "Does the Harborlight fund fit our mandate, and what is its ticket against what we still have uncalled?"
    h = next(r for r in rows if r["deal_name"] == "Harborlight Ventures IV")
    assert (float(h["ticket"]), float(h["uncalled_before"]), float(h["uncalled_after"]), float(h["ticket_pct_of_uncalled"])) == (2000000, 14600000, 16600000, 13.7)


def test_a_placeholder_commitment_row_is_said_never_dropped_silently(office):
    office.con.execute("begin")
    try:  # a row with no register line, no called figure and no call, beside the fund's register rows
        office.con.execute("create temp table s as select * from commitments as x where not exists (select 1 from commitments as y where y.supersedes_commitment_id = x.id) "
                           "and x.called_to_date is not null limit 1")
        office.con.execute("update s set id = uuid(), source_record_id = null, called_to_date = null, called_as_at = null, supersedes_commitment_id = null")
        office.con.execute("insert into commitments select * from s")
        rows = office.run("called_to_date")
    finally:
        office.con.execute("rollback")
    assert sum(r["placeholders_left_out"] for r in rows) == 1 and len(rows) == 8
    said = F.say(R.recipe("called_to_date"), [r for r in rows if not r["noticed_not_recorded"]])  # an uncalled question (a call question stops at the call)
    assert "Left out as placeholders" in said and "1 row of" in said


# ---- uc-004, uc-006, uc-018: the named call is said apart from calls past due ------------------------------------------------------------------

def test_uc004_can_holdings_pay_the_cedarpoint_call_on_the_23rd(office):
    rows, said = _r3(office, ["cash_after_calls"])["cash_after_calls"]  # "Can Holdings pay the Cedarpoint call on the 23rd?"
    h = next(r for r in rows if r["entity"] == "Evergreen Holdings" and r["currency"] == "USD")
    assert (float(h["calls_ahead"]), float(h["shortfall_ahead"]), float(h["overdue_calls"])) == (1250000, 270000, 3600000)
    _has(said, "1,230,000", "1,250,000", "250,000", "270,000")


def test_uc006_how_much_sgd_to_convert_for_the_call(office):
    rows, said = _r3(office, ["fx_required"])["fx_required"]  # "We hold SGD and need USD for the call. How much do we convert ...?"
    h = next(r for r in rows if r["entity"] == "Evergreen Holdings")
    assert (float(h["shortfall_ahead"]), float(h["convert_ahead"])) == (270000, 361800)
    _has(said, "361,800", "1.34")


def test_uc018_which_entity_pays_and_whether_a_transfer_is_needed(office):
    _, said = _r3(office, ["funding_plan"])["funding_plan"]  # "Which entity pays and whether a transfer is needed first"
    _has(said, "Cedarpoint Ventures III call of USD 1,250,000", "270,000", "618,343.96")


def test_without_calls_past_due_the_answers_are_as_in_r2(office):
    said = {rid: F.say(R.recipe(rid), office.run(rid)) for rid in ("cash_after_calls", "fx_required", "funding_plan")}
    assert "past due" not in " ".join(said.values())
    _has(said["fx_required"], "Converting SGD 361,800 of its 1,600,000")
    _has(said["funding_plan"], "Evergreen Holdings is short USD 270,000", "Entity B has 618,343.96 spare")


# ---- the cause: one bad file must not split a drop by kind (uc-008's open calls too) ------------------------------------------------------------

def test_a_bad_file_is_set_aside_and_the_rest_is_read_together(tmp_path):
    names = ["2026-07/notices/2026-07-07_C_call6.pdf", "2026-08/bank_statements/HB_HOLD_USD_2026-07.xlsx", "2026-08/commitments/commitments_register_2026-07-31.xlsx",
             "2026-10/inbox/scan_0412.pdf"]
    plane, x = W3.flat_thread(tmp_path, names)
    PK.intake(x)
    # r3: scan_0412.pdf was read as a notice and failed, which split the drop; since r3b it is read as an inbox file and loads
    assert x.th["pack"]["scan_0412.pdf"]["kind"] == "inbox"
    n, aside = PK.load(x)
    assert n == 4 and aside == []
    call = W3.rows(plane, "select m.confirmation_status, e.entity_name, c.source_record_id is not null from cash_movements as m join commitments as c on c.id = m.commitment_id "
                          "join legal_entities as e on e.id = c.legal_entity_id where m.notice_kind = 'capital_call' and m.movement_type = 'call' "
                          "and not exists (select 1 from cash_movements as z where z.supersedes_cash_movement_id = m.id)")
    assert call == [("confirmed", "Evergreen Holdings", True)]  # r3: noticed, past due, on a stub of Entity B
    assert W3.rows(plane, "select count(*) from cash_movements where movement_type = 'payment' and confirmation_status = 'expected' and commitment_id is not null") == [(0,)]
