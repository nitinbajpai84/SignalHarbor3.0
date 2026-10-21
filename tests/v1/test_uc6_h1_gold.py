"""UC6 H1: Span's drafted gold for capital calls runs unattended. The run guard reads SQL (a 'call' value or a capital_call name is data, a CALL
statement is not), the rules count due dates in day windows from each month end, a closing balance or a difference is listed rather than drafted
as a plain total, a figure named after commitments is placed on commitments, and a model design that fails the plan check gets one repair."""
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import duckdb

from sh_platform.v1.wh import _utc  # the same UTC session as the warehouse
import pytest

from sh_platform.v1 import b10_design as D
from sh_platform.v1 import b10_pack as K
from sh_platform.v1 import b6_run as R
from sh_platform.v1 import e1_write, k6_liquidity as K6, wh
from tests.v1.e1_seed import LE, seed
from tests.v1.test_fixc_span_pack import Script, draft, make, slug_of
from tests.v1.test_k6 import CASH, INST, PF, SRC_REC, world  # noqa: F401 - the fixture

KPIS = [
    {"code": "K01", "name": "Available cash by entity", "definition": "Administrator closing cash on the as-at date, by entity", "unit": "USD", "period": "monthly",
     "benchmark_by": ["entity"]},
    {"code": "K02", "name": "Calls due within 30 days", "definition": "Confirmed calls whose due date falls within 30 days of the as-at date", "unit": "USD",
     "period": "monthly", "benchmark_by": ["entity"]},
    {"code": "K03", "name": "Calls due in 31 to 60 days", "definition": "Confirmed calls whose due date falls 31 to 60 days after the as-at date", "unit": "USD",
     "period": "monthly", "benchmark_by": ["entity"]},
    {"code": "K04", "name": "Cash after calls by entity", "definition": "Administrator closing cash on the as-at date minus calls due within 30 days", "unit": "USD",
     "period": "monthly", "benchmark_by": ["entity"]},
    {"code": "K05", "name": "Uncalled commitment by fund", "definition": "Commitment minus confirmed called to date, by fund", "unit": "USD", "period": "monthly",
     "benchmark_by": ["fund"]},
    {"code": "K06", "name": "Calls not yet confirmed", "definition": "Calls noticed but not confirmed by the office", "unit": "USD", "period": "monthly",
     "benchmark_by": ["entity"]}]


@pytest.fixture()
def uc6(tmp_path, monkeypatch):
    return make(tmp_path, monkeypatch, {"title": "Can we meet the capital calls", "kpis": KPIS}, "h1")


@pytest.mark.parametrize("sql", [
    "create table g as select sum(amount) filter (where movement_type = 'call') as capital_call from cash_movements",
    "create table g as select 1 as call_count, 'load; copy' as note from cash_movements"])
def test_the_run_guard_lets_call_as_a_value_or_a_name_through(sql):
    assert R.build_statements({"name": "g", "sql": sql}, False)


@pytest.mark.parametrize("sql", ["call g()", "create table g as select 1; call x()", "create table g as select 1; drop table h", "drop table g",
                                 "insert into g select 1; delete from h"])
def test_the_run_guard_still_refuses_statements_that_are_not_one_create_or_insert(sql):
    with pytest.raises(ValueError):
        R.build_statements({"name": "g", "sql": sql, "columns": [{"name": "a"}]}, True)


def _gold(pack, kpi):
    return next(g for g in pack["target"]["gold"] if kpi in (g.get("kpis") or []))


def test_rules_count_30_and_60_day_windows_from_the_month_end_and_list_balances(uc6):
    plane, pid = uc6
    pack = draft(plane, pid)
    due = _gold(pack, "Calls due within 30 days")  # A7, live r3b/r5: both call windows are bound by meaning to the pack's calls_due recipe
    assert due is _gold(pack, "Calls due in 31 to 60 days") and due["purpose"].startswith("Recipe calls_due:") and "commitments" not in due["depends_on"]
    # The rules still draft the windows for an office whose pack has no calls recipe: ask them directly, as design() does after the recipes.
    calls = [k for k in KPIS if k["name"] in ("Calls due within 30 days", "Calls due in 31 to 60 days")]
    g = next(x for x in D._rules_design(plane, slug_of(plane, pid), calls, K._grain({"kpis": KPIS})[0], [])["gold"]
             if "Calls due within 30 days" in x["kpis"])
    assert "Calls due in 31 to 60 days" in g["kpis"]
    assert "f.due_date between a.as_at + 0 and a.as_at + 30" in g["sql"] and "f.due_date between a.as_at + 31 and a.as_at + 60" in g["sql"]
    assert "not exists (select 1 from cash_movements as s where s.supersedes_cash_movement_id = f.id)" in g["sql"]  # a confirmed notice counts once
    n = _gold(pack, "Calls not yet confirmed")["sql"]
    assert "confirmation_status = 'noticed'" in n and "'confirmed'" not in n  # "not confirmed" leaves confirmed out
    placed = {k for x in pack["target"]["gold"] for k in x.get("kpis") or []}
    after = _gold(pack, "Cash after calls by entity")  # the pack's cash_after_calls recipe: a balance on positions, never a sum of movements under a cash name
    assert after["purpose"].startswith("Recipe cash_after_calls:") and "position_snapshots" in after["depends_on"]
    cash = _gold(pack, "Available cash by entity")  # c6 (A7): the closing balance is built from the pack's cash_by_entity recipe, on positions, never movements
    assert cash["purpose"].startswith("Recipe cash_by_entity:") and "cash_movements" not in cash["depends_on"]
    assert "Uncalled commitment by fund" in placed  # UC6 G: commitments now hold called_to_date, so the rules draft it
    rows = " ".join(m["needs_person"] for m in K.open_rows(pack))
    assert "Define Cash after calls by entity" not in rows and "Define Uncalled commitment by fund" not in rows  # both placed: nothing left to define

    con = _utc(duckdb.connect())
    con.execute("create table legal_entities (id varchar, entity_code varchar)")
    con.execute("create table portfolios (id varchar, legal_entity_id varchar)")
    con.execute("create table cash_movements (id varchar, portfolio_id varchar, movement_type varchar, notice_kind varchar, confirmation_status varchar, "
                "effective_date date, due_date date, amount decimal(18,2), supersedes_cash_movement_id varchar)")
    con.execute("insert into legal_entities values ('le-b', 'EG-B')")
    con.execute("insert into portfolios values ('pf-b', 'le-b')")
    for row in [("c1", "confirmed", "2026-09-20", "2026-10-20", 450000, None),   # 20 days after 30 Sep
                ("n2", "noticed", "2026-09-15", "2026-10-25", 600000, None),     # noticed, then confirmed by c2: counted once
                ("c2", "confirmed", "2026-09-29", "2026-10-25", 600000, "n2"),
                ("c3", "confirmed", "2026-09-29", "2026-11-15", 250000, None),   # 46 days: the 31 to 60 day window
                ("n4", "noticed", "2026-09-28", "2026-10-10", 100000, None)]:    # not confirmed: no confirmed window
        con.execute("insert into cash_movements values (?, 'pf-b', 'call', 'call', ?, ?, ?, ?, ?)", list(row[:1]) + list(row[1:]))
    for s in R.build_statements(g, False):
        con.execute(s)
    got = con.execute(f"select calls_due_within_30_days, calls_due_in_31_to_60_days from {g['name']}__next where month = date '2026-09-01' and entity = 'EG-B'").fetchone()
    assert [float(x) for x in got] == [1050000.0, 250000.0]


def test_a_model_design_that_fails_the_plan_check_is_repaired_once_before_the_rules(uc6, monkeypatch):
    plane, pid = uc6
    slug = slug_of(plane, pid)

    def reply(sql):
        return json.dumps({"gold": [{"name": f"gold_{slug}_calls", "purpose": "Calls by entity", "grain": "Month by entity", "keys": ["month"],
                                     "kpis": ["Calls due within 30 days"], "sql": sql, "depends_on": ["cash_movements"], "columns": []}], "silver": []})
    bad = reply(f"create table gold_{slug}_calls as select case when f.amount > 0 then 1 as month from cash_movements as f")
    good = reply(f"create table gold_{slug}_calls as select cast(date_trunc('month', f.due_date) as date) as month, "
                 f"cast(sum(f.amount) as decimal(18,2)) as calls_due_within_30_days from cash_movements as f group by all")
    pack = draft(plane, pid, Script(bad, good), monkeypatch)
    designed = [g["name"] for g in pack["target"]["gold"] if g["name"].startswith(f"gold_{slug}_") and not g["purpose"].startswith("Recipe ")]  # A7: recipe tables are placed before the model
    assert designed == [f"gold_{slug}_calls"]


def test_drafted_uncalled_commitment_matches_the_office_view(uc6, world, monkeypatch):  # UC6 G: same figures as k6_liquidity.commitments()
    g = _gold(draft(*uc6), "Uncalled commitment by fund")
    plane = world
    srcs = {k: str(uuid.uuid4()) for k in "CDEF"}
    seed(plane, sources=list(srcs.values()))
    amounts = {"C": ("6000000", "3600000", date(2026, 8, 31)), "D": ("5000000", "4500000", date(2026, 8, 31)),
               "E": ("10000000", "4000000", None), "F": ("1000000", None, None)}
    com = {}
    for k, (amt, called, at) in amounts.items():
        com[k] = K6.record_commitment(plane, {"legal_entity_id": LE, "instrument_id": INST, "commitment_amount": Decimal(amt), "currency": "USD",
                                              "committed_on": date(2025, 1, 15), "source_record_id": srcs[k], "called_to_date": called and Decimal(called),
                                              "called_as_at": at})

    def call(k, amount, received, status="confirmed"):
        e1_write.record(plane, "cash_movements", {"source_record_id": SRC_REC, "portfolio_id": PF, "instrument_id": INST, "movement_type": "call",
                                                  "effective_date": received.date(), "received_at": received, "amount": Decimal(amount), "currency": "USD",
                                                  "confirmation_status": status, "due_date": received.date(), "notice_kind": "call", "commitment_id": com[k]})
    call("D", "300000", datetime(2026, 8, 12, tzinfo=timezone.utc))   # received before the file's as-at: already in 4.5m
    call("C", "200000", datetime(2026, 9, 10, tzinfo=timezone.utc))   # after the as-at: adds
    call("E", "500000", datetime(2026, 9, 10, tzinfo=timezone.utc))   # figure without a date: the confirmed calls win
    call("F", "100000", datetime(2026, 9, 10, tzinfo=timezone.utc))   # no figure: the confirmed calls
    call("C", "999999", datetime(2026, 9, 11, tzinfo=timezone.utc), "noticed")  # not confirmed: not counted
    monkeypatch.setattr(K6, "_file_called", lambda con, sid, grids: next((((Decimal(c), "f.xlsx", at) for k, (_, c, at) in amounts.items() if c and srcs[k] == str(sid))), None))
    want = sum(c["uncalled"] for c in K6.commitments(plane))
    assert want == Decimal("1000000") - Decimal("100000") + Decimal("6000000") - Decimal("3800000") + Decimal("5000000") - Decimal("4500000") + Decimal("10000000") - Decimal("500000")
    with wh.connect(plane) as con:
        for st in R.build_statements(g, False):
            con.execute(st)
        got = con.execute(f"select sum(uncalled_commitment_by_fund) from {g['name']}__next").fetchone()[0]
    assert got == want
