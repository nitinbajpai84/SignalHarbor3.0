"""Regressions of test cycle 2 (passed in cycle 1, failed in cycle 2). Synthetic data only.

1. hr_admin: a process ask went down the data path, because North's gap-fill drafts (accepted before Decision 1 since the sign-off fix) put
   formula figures in the brief that the model had not marked as suggestions.
2. head_of_data: a ready table with a row per portfolio and a NULL figure in each counted as "has rows", so the figure was never redesigned on the
   loaded positions and the answer fell to Lumen.
3. cio, fund_accountant: an .eml sent as message/rfc822 arrived at intake as an empty file ("That file is empty.").
"""
import hashlib
import json
from contextlib import contextmanager
from types import SimpleNamespace

import duckdb
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from sh_platform.plane import PlaneStore
from sh_platform.v1 import l2_proposals as L2
from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_harbor as H
from sh_platform.v1 import v3_process as P
from sh_platform.v1.e0c_routes import _multipart

EML = (b"From: Example Manager <ir@example.test>\nTo: Ops <ops@example.test>\nSubject: Revision notice\nContent-Type: text/plain; charset=\"utf-8\"\n"
       b"MIME-Version: 1.0\n\nThe amended statement replaces the estimate.\n  Amended: USD 10,180,000\n")


# ---- 3. an email file keeps its bytes through the form upload --------------------------------------------------------------------

def test_an_eml_sent_as_message_rfc822_keeps_its_exact_bytes():
    app = FastAPI()

    @app.post("/up")
    async def up(request: Request):
        form = await _multipart(request)
        return {"name": form["filename"], "sha": hashlib.sha256(form["data"]).hexdigest(), "source_code": form.get("source_code"), "n": len(form["files"])}

    c = TestClient(app)
    for ctype in ("message/rfc822", "application/octet-stream", "text/csv"):
        got = c.post("/up", files={"file": ("04_revision_notice.eml", EML, ctype)}, data={"source_code": "fund_a"}).json()
        assert got == {"name": "04_revision_notice.eml", "sha": hashlib.sha256(EML).hexdigest(), "source_code": "fund_a", "n": 1}, ctype
    binary = bytes(range(256)) * 4 + b"\r\n--not-the-boundary\r\n"  # a body with CRLFs and dashes of its own is cut only at the real boundary
    got = c.post("/up", files={"file": ("book.xlsx", binary)}).json()
    assert got["sha"] == hashlib.sha256(binary).hexdigest()


# ---- 1. a process ask stays process-only when the figures are North's own fill -----------------------------------------------

ASK = "I want the steps written down properly: who does what, in which system, and a procedure document I can hand a new joiner."
FILLED = {"name": "Net worth", "formula": "Sum of asset values - sum of liabilities", "pack_suggested": False, "status": "defined"}


def _office(tmp_path):
    plane = PlaneStore(tmp_path / "data").create("acme")
    plane.path("v3").mkdir(parents=True, exist_ok=True)
    plane.path("v3", "files.json").write_text(json.dumps([{"name": "month_end_process_narrative.md", "status": "recognised", "thread": "t-1", "source": ""},
                                                          {"name": "handover_email.txt", "status": "waiting", "thread": None, "source": ""}]))
    return plane


def _propose(plane, text, kpis):
    L2.propose(plane, "ini-1", "sow", None, [{"op": "add", "path": f"kpis/{k['name']}", "after": k["name"]} for k in kpis],
               payload={"sow_patch": {"kpis": kpis}, "process_steps": None, "text": text, "who": "Priya Nair"})


def test_figures_north_filled_with_the_usual_practice_do_not_make_a_process_ask_a_data_build(tmp_path):
    plane = _office(tmp_path)
    sow = {"intent_id": "ini-1", "title": "Month-end investment report", "goal": {"line": ASK}, "kpis": [FILLED]}
    _propose(plane, H.FILL + "The figures, and how you work each one out today", [FILLED])
    assert P.is_process(plane, {"id": "t-1", "iid": "ini-1"}, sow)
    _propose(plane, "We also report net worth each month as assets less liabilities.", [FILLED])  # the person's own words name it: it counts
    assert not P.is_process(plane, {"id": "t-1", "iid": "ini-1"}, sow)


def test_a_figure_with_no_proposal_behind_it_still_counts(tmp_path):
    plane = _office(tmp_path)
    assert not P.is_process(plane, {"id": "t-1", "iid": "ini-1"}, {"intent_id": "ini-1", "title": "x", "goal": {"line": ASK}, "kpis": [FILLED]})


# ---- 2. a ready table whose figure column is all NULL is not a filled table -------------------------------------------------------

def _copy_with(tmp_path, value):
    (tmp_path / "warehouse").mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(tmp_path / "warehouse" / "sandbox.duckdb"))
    con.execute("create table gold_kpis (portfolio_id varchar, net_worth decimal(38, 8))")
    con.execute("insert into gold_kpis values ('p1', ?), ('p2', ?)", [value, value])
    con.close()
    return SimpleNamespace(path=lambda *p: tmp_path.joinpath(*p))


KPI = {"name": "Net worth by portfolio"}
GOLD = [{"name": "gold_kpis", "columns": [{"name": "portfolio_id", "type": "VARCHAR"}, {"name": "net_worth", "type": "DECIMAL(38,8)"}]}]


def test_rows_with_no_value_for_the_figure_are_not_a_filled_ready_table(tmp_path):
    assert not F.valued(_copy_with(tmp_path / "a", None), KPI, GOLD)
    assert F.valued(_copy_with(tmp_path / "b", 41200000), KPI, GOLD)


def test_after_the_load_a_figure_with_only_null_values_gets_a_ready_table_designed(tmp_path, monkeypatch):
    plane = _copy_with(tmp_path, None)
    asked = []
    monkeypatch.setattr(F, "kpis_of", lambda plane, iid: [KPI])
    monkeypatch.setattr(F, "table_rows", lambda plane, copy=False: {"position_snapshots": 344, **({"gold_kpis": 2} if copy else {})})  # the table has rows
    monkeypatch.setattr(F, "fact_names", lambda: {"position_snapshots"})
    monkeypatch.setattr(F, "design", lambda x, todo, filled: (asked.extend(k["name"] for k in todo), ([], {}))[1])

    @contextmanager
    def record(*a, **k):
        yield {}
    from sh_platform.v1 import v3_skills
    monkeypatch.setattr(v3_skills, "record", record)
    x = SimpleNamespace(plane=plane, th={"id": "t-1", "iid": "ini-1", "pid": "prj-1"},
                        api=lambda who, m, path, body=None, soft=False: {"pack": {"target": {"gold": GOLD}, "state": "approved"}})
    F.cover(x, "loaded")
    assert asked == ["Net worth by portfolio"]


# ---- cycle 4: go-live with no starter dashboard; a window over an aggregate; which statement is missing -------------------------

def test_go_live_does_not_stop_when_there_is_no_starter_dashboard_yet():
    """c4 ops_lead, ops_clerk: no figure had a ready table, the studio answered 409 and the chain stopped at go-live with a question."""
    def api(who, method, path, body=None, soft=False):
        if path.endswith("/starter"):
            if not soft:
                raise H.Q("There are no figures to build a starter dashboard from yet. It appears when the pipeline has run.")
            return {}
        raise AssertionError(f"nothing else is called: {method} {path}")
    got = H.c_lumen(SimpleNamespace(th={"pid": "prj-1", "iid": "ini-1"}, api=api))
    assert got.startswith("no starter board yet")


def test_the_bind_check_refuses_a_window_over_an_aggregate():
    """c4 principal: 'Cannot mix aggregates with non-aggregated columns' was forgiven as a type clash and stopped the run on the copy."""
    import pytest
    import sqlglot
    from sh_platform.v1 import b6_plan as B
    from sh_platform.v1.i2_north import Refused
    schema = {"position_snapshots": {"as_of_date": "date", "portfolio_id": "integer", "balance_amount": "decimal(18,2)", "observation_type": "varchar"}}
    bad = ("select as_of_date as day, portfolio_id, sum(balance_amount) - lag(sum(balance_amount)) over (partition by portfolio_id order by as_of_date) as change "
           "from position_snapshots group by all")
    with pytest.raises(Refused, match="Cannot mix aggregates"):
        B._bind("gold_x", sqlglot.parse_one(bad, dialect="duckdb"), schema)
    with pytest.raises(Refused, match="GROUP BY"):  # a column whose name holds 'type' is not a type clash
        B._bind("gold_x", sqlglot.parse_one("select observation_type, sum(balance_amount) from position_snapshots", dialect="duckdb"), schema)
    B._bind("gold_x", sqlglot.parse_one("select as_of_date, sum(balance_amount) from position_snapshots group by 1", dialect="duckdb"), schema)


def test_which_statement_is_missing_names_the_fund_and_its_business_days_overdue(monkeypatch):
    """c4 fund_accountant answered 'Missing statements in September 2026: 6' (a count of statements received). The answer key's 63 is P11: Cedarpoint
    Opportunities II, 30 Jun 2026, due 14 Jul (10 business days), 63 business days overdue at 9 Oct. Its one March statement must not read as monthly."""
    from datetime import date as d
    from sh_platform.profile.view import Viewer
    from sh_platform.v1 import k5_managers as K5
    docs = {f: [{"valuation_date": v, "supersedes_document_id": None, "received_at": v}] for f, v in (("C", "2026-06-30"), ("D", "2026-03-31"))}
    monkeypatch.setattr(K5, "_statements", lambda plane: docs)
    due_n, as_of = 10, d(2026, 10, 9)
    funds = [K5._fund_row({"fund_id": f, "fund_name": n, "manager": "Cedarpoint Ventures", "first_valued": None}, docs[f], [], {}, as_of, due_n, None)
             for f, n in (("C", "Cedarpoint Ventures III"), ("D", "Cedarpoint Opportunities II"))]
    assert len(funds[1]["earlier_missing"]) == 5  # one statement date alone reads as monthly in the inbox
    monkeypatch.setattr(K5, "inbox", lambda plane, viewer, as_of=None: {"as_of": "2026-10-09", "due_rule_signed": True, "rule_note": None,
                                                                       "managers": [{"name": "Cedarpoint Ventures", "funds": funds}]})
    got = F.missing_statements(None, Viewer("Helen Foo", frozenset({"company_admin"})), "Which statement is missing and how overdue is it?")
    assert got["answer"] == "Missing statement at 9 Oct 2026: Cedarpoint Opportunities II, period 30 Jun 2026, due 14 Jul 2026, 63 business days overdue."
    assert F.missing_statements(None, None, "What is our net worth?") is None


def test_a_missing_figure_is_never_read_from_a_count_of_what_arrived():
    t = {"name": "gold_statements", "columns": [{"name": "month", "type": "date"}, {"name": "statements_received_on_time", "type": "bigint"}]}
    assert F._read(None, t, {"name": "Missing statements"}, "Which statement is missing?", {}) is None


# ---- round 5 (cycle 6 fixes) ------------------------------------------------------------------------------------------------------

def test_a_declared_column_name_that_differs_from_the_sql_alias_never_takes_a_guessed_formula():
    """c5 ops_clerk: the design named the column 'trade match rate', the SQL 'Trade match rate'; the pack took the design's 'from' (f.id, t.id) as the
    formula, the plan could not be drawn, and the run on a copy said only 'This project has no build plan yet.'."""
    from sh_platform.v1 import b10_pack as K
    sql = ("create table gold_m as select t.organization_id, 100.0 * count(distinct t.id) filter (where f.id is not null) as \"Trade match rate\", "
           "count(distinct t.id) as total_trades from transactions t left join fx_confirmations f on t.external_trade_id = f.trade_reference group by t.organization_id")
    t = {"layer": "gold", "name": "gold_m", "sql": sql, "depends_on": ["transactions"], "keys": ["organization_id"],
         "columns": [{"name": "organization_id", "type": "uuid"}, {"name": "trade match rate", "type": "varchar", "from": "f.id, t.id"}, {"name": "total_trades", "type": "bigint"}]}
    g = K._gold(None, {}, {"tables": [t]}, {}, "", [])[0]
    assert g["columns"][1]["expr"].startswith("100.0 * COUNT(DISTINCT t.id)")
    assert "f.id, t.id" not in K._build_sql("gold_m", g)
    t["columns"].append({"name": "not_in_the_sql", "type": "bigint", "from": "f.id, t.id"})
    g = K._gold(None, {}, {"tables": [t]}, {}, "", [])[0]
    assert g["base_sql"] is None and K._build_sql("gold_m", g) == sql  # a column the SQL does not name: the SQL as written


def test_no_build_plan_after_an_approved_pack_asks_naming_the_step_that_failed(monkeypatch):
    import pytest
    from sh_platform.v1 import b10_pack as K, b6_run, v3_plan_guard as PG
    why = "The formula for a column of gold_m cannot be read: Invalid expression / Unexpected token."
    monkeypatch.setattr(b6_run, "latest_plan", lambda plane, pid, live=False: None)
    monkeypatch.setattr(K, "latest_approved", lambda plane, pid: {"version": 1, "plan_error": why})
    calls = []

    def api(who, method, path, body=None, soft=False):
        calls.append(path)
        raise H.Q(why)
    with pytest.raises(H.Q) as e:
        PG.ensure_plan(SimpleNamespace(th={"pid": "prj-1"}, plane=None, api=api))
    assert calls == ["/api/v1/build/p/prj-1/architecture/pack/plan/approve"]  # the head of data's retry first
    assert "could not draw the build plan" in e.value.text and why in e.value.text and "no build plan yet" not in e.value.text


def _conc_rows():
    from datetime import date
    from decimal import Decimal
    return [{"portfolio": "Evergreen Liquid portfolio", "issuer": n, "position_date": date(2026, 9, 30), "currency": "USD", "concentration_pct": Decimal(v)}
            for n, v in (("Harborview Semiconductor", "5.75"), ("Northwind Logistics", "5.08"))]


def test_the_concentration_recipe_is_a_share_of_the_portfolio():
    """c5 risk_officer: the answer key is Harborview 2,368,000 of the EG-LIQUID portfolio's 41,200,000 = 5.75%; the recipe divided by everything held."""
    from decimal import Decimal
    from sh_platform.v1 import v3_recipes as R
    con = duckdb.connect()
    con.execute("create table portfolios (id int, portfolio_name varchar)")
    con.execute("create table instruments (id int, canonical_name varchar, instrument_type varchar)")
    con.execute("create table bank_accounts (id int, cash_instrument_id int)")  # cash counts once (the holdings snippet reads it)
    con.execute("create table position_snapshots (id int, portfolio_id int, instrument_id int, position_date date, currency varchar, data_status varchar, "
                "recorded_at timestamp, supersedes_position_id int, source_market_value decimal(18,2))")
    con.execute("insert into portfolios values (1, 'Liquid'), (2, 'Growth')")
    con.execute("insert into instruments values (1, 'Harborview Semiconductor', 'listed_equity'), (2, 'Rest', 'listed_equity'), (3, 'Fund', 'private_fund')")
    con.execute("insert into position_snapshots values (1, 1, 1, '2026-09-30', 'USD', 'official', now(), null, 2368000), "
                "(2, 1, 2, '2026-09-30', 'USD', 'official', now(), null, 38832000), (3, 2, 3, '2026-09-30', 'USD', 'official', now(), null, 26650000)")
    r = R.recipe("concentration")
    con.execute(R.render(r, "gold_c"))
    assert con.execute("select concentration_pct from gold_c where issuer = 'Harborview Semiconductor'").fetchone()[0] == Decimal("5.75")
    assert R.tie_out(con, r, "gold_c")["ok"]


def test_which_holding_is_over_its_single_name_limit_names_it_with_its_share(monkeypatch):
    from decimal import Decimal
    from sh_platform.v1 import cx_dash, v3_rule_checks as RC
    k = {"name": "Single-issuer concentration"}
    monkeypatch.setattr(RC, "_signed_limits", lambda plane, on: [{"words": "The Harborview Semiconductor share of the Evergreen Liquid portfolio must be at most 5%.",
                                                                  "max": Decimal(5), "bucket": "harborview semiconductor", "portfolio": "Evergreen Liquid portfolio"}])
    got = RC._over_limit(None, k, _conc_rows(), "Which holding is over its single-name limit?", {})
    assert got["answer"].startswith("Over the single-name limit: Harborview Semiconductor, Evergreen Liquid portfolio, 5.75% on 30 September 2026 against a maximum of 5%.")
    monkeypatch.setattr(RC, "_signed_limits", lambda plane, on: [])  # no signed rule: the limit the signed brief states, for every holding
    got = RC._over_limit(None, k, _conc_rows(), "Which holding is over its limit?", {"brief": {"question": "no single name over 5 percent, listed equity between 60 and 90"}})
    assert "Harborview Semiconductor" in got["answer"] and "Northwind Logistics" in got["answer"] and "signed brief" in got["answer"]
    got = RC._over_limit(None, k, _conc_rows(), "Which holding is over its limit?", {"brief": {"question": "test the liquid book"}})
    assert got["answer"].startswith("The single-name limit is not on record") and "5.75%" in got["answer"]  # never an invented limit
    t = {"name": "gold_c", "columns": [{"name": "issuer", "type": "varchar"}, {"name": "concentration_pct", "type": "decimal(9,2)"}]}  # 'which holding': the issuer
    monkeypatch.setattr(cx_dash, "run_sql", lambda plane, sql: ([], [{"issuer": "A", "concentration_pct": Decimal(1)}, {"issuer": "B", "concentration_pct": Decimal(2)}], False))
    monkeypatch.setattr(F, "coverage", lambda plane, vals: "")
    got = F._read(None, t, k, "Which holding has the largest concentration?", {})
    assert got and "no split by" not in got["answer"]


def test_a_cash_break_is_read_for_the_day_asked_against_the_signed_tolerance(monkeypatch):
    """c5 ops_lead: 'Cash break over not available yetk in October 2026: ... Evergreen Family Trust 1,800.00'. The label was blanked by the number guard,
    the day asked was said as the month, and the Trust's 1,800 (one custody charge, inside the 5,000 USD tolerance) was listed as a break."""
    from datetime import date
    from decimal import Decimal
    from sh_platform.agents.guard import check_numbers
    from sh_platform.v1 import e3_rules, v3_recipes as R, v3_rule_checks as RC
    assert check_numbers('{"name": "Cash break over 5k", "definition": "over 7"}', [], "Anything over 5,000").text == \
        '{"name": "Cash break over 5k", "definition": "over not available yet"}'  # the label stays; a stated figure is still checked
    rows = [{"entity": e, "day": date(2026, 10, d), "currency": "USD", "cash_break": Decimal(v)}
            for e, d, v in (("Entity B", 8, "12400"), ("Evergreen Family Trust", 8, "1800"), ("Evergreen Holdings", 8, "0"), ("Entity B", 7, "0"))]
    monkeypatch.setattr(e3_rules, "current", lambda plane, code, on: {"parameters": {"abs_amount": 5000, "currency": "USD", "per": "entity_day"}} if code == "cash_tolerance" else None)
    got = RC._breaks(None, R.recipe("cash_break"), rows, "Which entity has a cash break on 8 October and by how much?")
    assert got["answer"] == ("Cash break on 8 October 2026, over the signed cash tolerance of 5,000 USD per entity per day: Entity B 12,400.00 USD. "
                             "Within the tolerance, not a break: Evergreen Family Trust 1,800.00 USD. Agree: Evergreen Holdings.")
    monkeypatch.setattr(e3_rules, "current", lambda plane, code, on: None)
    assert RC._breaks(None, R.recipe("cash_break"), rows, "Which entity has a cash break?") is None  # no tolerance on record: the plain figures answer


def test_a_break_named_by_its_threshold_is_the_cash_break_and_the_question_finds_it():
    """c6 ops_lead: North called the break 'Variance over 5,000'; no recipe matched, no break table was built, and 'which entity has a cash break'
    was answered from Cash balance per entity."""
    from sh_platform.v1 import v3_recipes as R, v3_rule_checks as RC
    var = {"name": "Variance over 5,000", "definition": "Absolute difference between summed cash sources and expected cash, filtered for amounts > 5,000"}
    assert R.match({"name": "Cash break over 5k"})["id"] == R.match(var)["id"] == "cash_break"
    assert R.match({"name": "Number of breaks"}) is None and R.match({"name": "Timing-only variance", "definition": "Differences that resolve"}) is None
    kpis = [{"name": "Cash balance per entity", "definition": "Cash on hand"}, var]
    assert RC.kpi_by_recipe("Which entity has a cash break on 8 October and by how much?", kpis) is var
    assert RC.kpi_by_recipe("What is the weather?", kpis) is None
    assert RC._day("2026-10-08") == __import__("datetime").date(2026, 10, 8)


def test_a_rule_check_on_any_ready_table_comes_before_a_plain_read(monkeypatch):
    """c6 ops_lead: cash by entity and the cash break both had 24 rows; the plain read of cash by entity answered first with closing balances."""
    from sh_platform.v1 import b10_pack as P, cx_dash as CD, talk, v3_rule_checks as RC
    k = {"name": "Cash breaks > 5,000"}
    tabs = [{"name": "gold_cash_by_entity", "rows": 24, "columns": []}, {"name": "gold_cash_break", "rows": 24, "columns": []}]
    monkeypatch.setattr(F, "kpis_of", lambda plane, iid: [k])
    monkeypatch.setattr(talk, "reachable", lambda plane, viewer: ([{"id": "prj-1"}], None))
    monkeypatch.setattr(P, "latest_approved", lambda plane, pid: {"target": {"gold": [{"name": t["name"]} for t in tabs]}})
    monkeypatch.setattr(CD, "gold_tables", lambda plane, pid: tabs)
    monkeypatch.setattr(F, "covering", lambda k, gold: gold)
    monkeypatch.setattr(F, "aliases", lambda plane: {})
    monkeypatch.setattr(RC, "answer", lambda plane, k, t, text, th: {"answer": "break"} if t["name"] == "gold_cash_break" else None)
    monkeypatch.setattr(F, "_read", lambda plane, t, k, text, names, th=None, measure=None: {"answer": "balance"})
    assert F._answer(None, None, "Which entity has a cash break on 8 October?", "prj-1", {"iid": "ini-1"})["answer"] == "break"


# ---- c6 follow-ups: recipe column, a brief with no figures, a rate that never divides, recipe matching ------------------------------------

def test_a_recipe_built_figure_is_answered_from_its_recipe_table_and_measure_column(monkeypatch):
    """c6 ops_clerk: 'FX forward match status' answered 991,000.00 from another table; the recipe table held FXF-2026-002 with variance 8,100."""
    from sh_platform.v1 import b10_pack as PK, cx_dash as CD, talk
    con = duckdb.connect()
    con.execute("create table gold_fx (trade_reference varchar, trade_date date, counterparty varchar, currency varchar, confirmed_amount decimal(18,2), "
                "trade_amount decimal(18,2), variance decimal(18,2))")
    con.execute("insert into gold_fx values ('FXF-2026-001', '2026-09-15', 'Bank A', 'USD', 500000, 500000, 0), "
                "('FXF-2026-002', '2026-10-05', 'Bank A', 'USD', 991000, 982900, 8100)")
    con.execute("create table gold_stats (trade_date date, matched_trade_count bigint, mismatch_total_amount decimal(18,2))")
    con.execute("insert into gold_stats select date '2026-10-01' + cast(i as integer), i, 991000 from range(5) as t(i)")

    def cols(t):
        return [{"name": n, "type": str(ty)} for n, ty in con.execute(f"select column_name, data_type from information_schema.columns where table_name = '{t}'").fetchall()]
    k = {"name": "FX forward match status", "definition": "FX forward confirmations against the desk's trades; the difference in amount"}
    gold = [{"name": "gold_fx", "kpis": [k["name"]], "purpose": "Recipe fx_confirmation_variance: FX forward confirmation variance"},
            {"name": "gold_stats", "kpis": ["Matched trade count"], "purpose": "Daily statistics of how many desk trades matched (FX forward status)"}]
    monkeypatch.setattr(F, "kpis_of", lambda plane, iid: [k])
    monkeypatch.setattr(talk, "reachable", lambda plane, viewer: ([{"id": "prj-1"}], None))
    monkeypatch.setattr(PK, "latest_approved", lambda plane, pid: {"target": {"gold": gold}})
    monkeypatch.setattr(CD, "gold_tables", lambda plane, pid: [{"name": t, "rows": n, "columns": cols(t)} for t, n in (("gold_fx", 2), ("gold_stats", 5))])
    def run_sql(plane, sql):
        c = con.execute(sql)
        return None, [dict(zip([d[0] for d in c.description], r)) for r in c.fetchall()], None
    monkeypatch.setattr(CD, "run_sql", run_sql)
    monkeypatch.setattr(F, "covering", lambda k, gold: gold)
    monkeypatch.setattr(F, "aliases", lambda plane: {})
    monkeypatch.setattr(F, "coverage", lambda plane, members: "")
    monkeypatch.setattr(F, "report_total", lambda plane, text: None)
    monkeypatch.setattr(F, "missing_statements", lambda plane, viewer, text: None)
    assert F.recipe_measures(k, gold) == {"gold_fx": "variance"}
    got = F._answer(None, None, "How much does the FX forward confirmation differ from our record?", "prj-1", {"iid": "ini-1"})
    assert "8,100" in got["answer"] and "991,000" not in got["answer"] and got["source"].startswith("fx")


def test_a_data_brief_with_no_figures_is_a_gap_at_decision_1_and_a_process_brief_is_exempt(tmp_path, monkeypatch):
    from sh_platform.v1 import i4_sow as S, v3_plan_guard as PG
    plane = _office(tmp_path)
    briefs = {"ini-d": {"intent_id": "ini-d", "title": "Trades against the administrator", "goal": {"line": "Match our trades with the administrator"}, "kpis": []},
              "ini-k": {"intent_id": "ini-k", "title": "Trades", "goal": {"line": "Match our trades"}, "kpis": [{"name": "Breaks"}]},
              "ini-p": {"intent_id": "ini-p", "title": "Month-end", "goal": {"line": ASK}, "kpis": []}}
    monkeypatch.setattr(S, "read", lambda plane, iid: briefs[iid])
    th = {"id": "t-1"}
    assert PG.figures_gap(plane, th, "ini-d") == ["Which figures do you want?"]
    assert PG.figures_gap(plane, th, "ini-k") == [] and PG.figures_gap(plane, th, "ini-p") == [] and PG.figures_gap(plane, th, None) == []
    from sh_platform.v1 import i6_chat as I6, v3_signoff as SO
    monkeypatch.setattr(SO, "accept_drafts", lambda x, iid: None)
    monkeypatch.setattr(I6, "_sign_gaps", lambda plane, iid: "")
    assert H._gaps(SimpleNamespace(plane=plane, th=th), "ini-d") == ["Which figures do you want?"]  # shown on Decision 1, and filled by the usual practice


def test_a_rate_that_never_divides_is_refused_with_the_reason_and_one_that_divides_passes():
    from sh_platform.v1 import v3_plan_guard as PG
    bad = {"kpis": ["Trade match rate"], "sql": "create table g as select trade_date, 100 * count(*) filter (where matched) as trade_match_rate from t group by all"}
    why = PG.rate_without_division(bad)
    assert why and "Trade match rate" in why and "never divides" in why
    ok = {"kpis": ["Trade match rate"], "sql": "create table g as select 100.0 * count(*) filter (where matched) / count(*) as trade_match_rate from t"}
    assert PG.rate_without_division(ok) is None
    assert PG.rate_without_division({"kpis": ["Match share"], "sql": "create table g as select avg(case when matched then 1 else 0 end) as s from t"}) is None
    assert PG.rate_without_division({"kpis": ["FX rate"], "sql": "create table g as select trade_reference, rate from fx_confirmations"}) is None  # read as it is
    assert PG.rate_without_division({"kpis": ["Net worth"], "sql": "create table g as select sum(v) as net_worth from p"}) is None
    from sh_platform.v1 import b6_span as SP
    notes = []
    assert SP.keep_valid(None, {"tables": [], "project_slug": "t"}, [{"name": "gold_t_rate", "layer": "gold", **bad}], notes) == [] and "never divides" in notes[0]


def test_a_one_word_recipe_name_is_the_figure_only_when_it_is_the_whole_name():
    """c6 fixc: 'Distributions incoming cash' and 'Cash after calls by entity' were built as the cash balance, 'Net break in USD' as the cash break."""
    from sh_platform.v1 import v3_recipes as R
    ids = {n: (R.match({"name": n}) or {}).get("id") for n in ["Distributions incoming cash", "Cash after calls by entity", "Net break in USD", "Cash",
                                                                "Cash by entity", "Available cash by entity", "NAV", "Cash balance per entity"]}
    assert ids == {"Distributions incoming cash": None, "Cash after calls by entity": "cash_after_calls", "Net break in USD": None, "Cash": "cash_by_entity",
                   "Cash by entity": "cash_by_entity", "Available cash by entity": "cash_by_entity", "NAV": "net_worth", "Cash balance per entity": "cash_by_entity"}
    assert R.match({"name": "How much cash does Entity B hold?"}, strict=False)["id"] == "cash_by_entity"  # a question's words still find it


# ---- cycle 8: "How you will know it worked" never filled; the run on a copy stuck with no reason ----------------------------------

def test_a_success_drafted_at_the_top_of_the_patch_lands_in_the_template_and_a_gap_list_is_not_a_statement():
    """c7 cfo, risk_officer: North drafted {"success": {"text": ...}} at the top of sow_patch, where merge never reads it, so the gap stayed open on
    every fill; and Harbor's own list of gaps was read as the person stating the result ("; How you will know it worked")."""
    from sh_platform.v1 import i6_chat as I6
    sp = {"result": {"text": "(suggested) A one-page daily pack."}, "success": {"text": "(suggested) The pack reaches Mei and Raj each morning."},
          "template_fields": {"result": "Kept as written"}}
    I6.template_at_top(sp)
    assert sp == {"template_fields": {"result": "Kept as written", "success": "(suggested) The pack reaches Mei and Raj each morning."}}
    assert I6.stated_fields(H.FILL + "What the result looks like; How you will know it worked") == {}
    assert I6.stated_fields(H.FILL + "How you will know it worked; What is still unclear, and who can settle it") == {}
    assert I6.stated_fields("We will know it worked when the pack ties to the custodian.")["success"] == "The pack ties to the custodian."


def test_success_still_empty_after_the_usual_practice_is_harbors_suggestion_from_the_figures_and_their_tie_outs(tmp_path, monkeypatch):
    from sh_platform.v1 import i4_sow as SW, t1_templates as T, v3_signoff as SO
    plane = _office(tmp_path)
    path = SW.path_of(plane, "ini-1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"intent_id": "ini-1", "state": "draft", "kpis": [{"name": "Net worth", "built_from": "net_worth"}, {"name": "Unmatched count"}],
                                "template_fields": {"result": "A page"}}))
    monkeypatch.setattr(T, "for_intent", lambda plane, iid, kind="intent_of_work": {"fields": [{"key": "success", "label": "How you will know it worked"}]})
    gaps = ["How you will know it worked", "What is still unclear, and who can settle it"]
    assert SO.success_fallback(plane, "ini-1", gaps) == ["What is still unclear, and who can settle it"]
    got = SW.read(plane, "ini-1")["template_fields"]
    assert got["result"] == "A page" and got["success"] == (
        "(suggested by Harbor) Each figure (Net worth, Unmatched count) is filled on the trial copy and ties out: "
        "Net worth equals the sum of the position snapshots for the same dates, cash counted once.")
    path.write_text(json.dumps({"intent_id": "ini-1", "state": "draft", "kpis": [], "template_fields": {"success": "The person's own words"}}))
    assert SO.success_fallback(plane, "ini-1", gaps) == gaps and SW.read(plane, "ini-1")["template_fields"]["success"] == "The person's own words"
    assert SO.success_fallback(plane, "ini-1", ["What is still unclear, and who can settle it"]) == ["What is still unclear, and who can settle it"]


def _builder(answers):
    calls = []

    def api(who, method, path, body=None, soft=False):
        calls.append(f"{method} {path.rsplit('/builder', 1)[-1] or '/'}")
        return answers[calls[-1]].pop(0)
    return calls, api


RAN = {"state": "ran", "run": {"status": "ok", "run_id": "run-1"}, "connections": []}


def test_a_drawn_but_unapproved_plan_is_approved_and_the_builder_runs_its_round(monkeypatch):
    """c7 ops_clerk: the plan was only proposed, so the builder had no round; a bare sandbox run left none either: "stuck: " with no reason."""
    from sh_platform.v1 import v3_plan_guard as PG
    monkeypatch.setattr(PG, "ensure_plan", lambda x: x.api("anita", "POST", "/approve-plan"))
    calls, api = _builder({"GET /": [{"round": None, "can": {"start": False}}, {"round": None, "can": {"start": True}}], "POST /approve-plan": [{}],
                           "POST /start": [{"round": RAN, "can": {}}]})
    x = SimpleNamespace(th={"pid": "prj-1"}, api=api)
    assert H.b_run(x) == "ran on a copy" and x.th["run_id"] == "run-1"
    assert calls == ["GET /", "POST /approve-plan", "GET /", "POST /start"]


def test_ensure_plan_approves_a_plan_that_was_only_proposed(monkeypatch):
    from sh_platform.v1 import b10_pack as K, b6_run, v3_plan_guard as PG
    plans = [{"state": "proposed"}, {"state": "approved"}]
    monkeypatch.setattr(b6_run, "latest_plan", lambda plane, pid, live=False: plans[0])
    monkeypatch.setattr(K, "latest_approved", lambda plane, pid: {"version": 1})
    calls = []
    PG.ensure_plan(SimpleNamespace(th={"pid": "prj-1"}, plane=None, api=lambda *a, **k: (calls.append(a[2]), plans.pop(0))))
    assert calls == ["/api/v1/build/p/prj-1/architecture/pack/plan/approve"]


def test_a_run_that_met_another_run_is_tried_once_more_and_a_stuck_run_always_names_why(monkeypatch):
    import pytest
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    busy = {"state": "failed", "run": {"status": "failed", "error": "This project is already running. Please wait for it to finish."}, "connections": []}
    calls, api = _builder({"GET /": [{"round": busy, "can": {}}], "POST /recheck": [{"round": RAN, "can": {}}]})
    assert H.b_run(SimpleNamespace(th={"pid": "prj-1"}, api=api)) == "ran on a copy" and calls == ["GET /", "POST /recheck"]
    blocked = {"state": "blocked", "connections": [{"code": "bank", "name": "Bank feed", "status": "failed", "detail": "the address is not allowed"}]}
    _, api = _builder({"GET /": [{"round": blocked, "can": {}, "needs": []}]})
    with pytest.raises(H.Q) as e:
        H.b_run(SimpleNamespace(th={"pid": "prj-1"}, api=api))
    assert e.value.text == "The run on a copy is stuck: Bank feed: the address is not allowed"
    from sh_platform.v1 import v3_plan_guard as PG
    monkeypatch.setattr(PG, "ensure_plan", lambda x: None)
    _, api = _builder({"GET /": [{"round": None, "can": {}}, {"round": None, "can": {}, "waiting": None}]})
    with pytest.raises(H.Q) as e:
        H.b_run(SimpleNamespace(th={"pid": "prj-1"}, api=api))
    assert e.value.text.startswith("The run on a copy is stuck: ") and len(e.value.text) > len("The run on a copy is stuck: ") + 10


def test_a_thread_save_never_leaves_a_half_written_file_for_a_reader(tmp_path):
    """Round 9: a reader caught the thread file mid-write and the start route returned HTTP 500."""
    import threading
    from types import SimpleNamespace
    from sh_platform.v1 import v3_harbor as H
    plane = SimpleNamespace(path=lambda *a: tmp_path.joinpath(*a))
    th = {"id": "t-race", "created": "2026-10-17", "stage": "drafting", "events": ["x" * 2000] * 50}
    H.save(plane, th)
    bad = []

    def read():
        for _ in range(200):
            try:
                H.load(plane, "t-race")
            except Exception as e:  # noqa: BLE001 - any failure is the bug
                bad.append(e)

    t = threading.Thread(target=read)
    t.start()
    for i in range(200):
        th["n"] = i
        H.save(plane, th)
    t.join()
    assert not bad
    assert not list(tmp_path.rglob("*.tmp"))


def test_a_figure_question_with_nothing_live_answers_at_once_without_the_model(monkeypatch):
    """17 Oct, Nitin: 'What is our cash by entity today?' on an office with no live build took about 45 seconds and the watchlist showed 0.00s."""
    from sh_platform.v1 import v3_board_routes as B
    monkeypatch.setattr(B, "_live", lambda plane, text="": None)
    monkeypatch.setattr(B.P, "answer", lambda plane, text: None)
    monkeypatch.setattr(B.C, "liquidity_answer", lambda *a, **k: None)
    import sh_platform.v1.v3_figures as F
    monkeypatch.setattr(F, "figure_answer", lambda *a, **k: None)
    monkeypatch.setattr(B.T, "ask", lambda *a, **k: (_ for _ in ()).throw(AssertionError("the model was called")))
    out = B._ask(object(), None, "What is our cash by entity today?", None)
    assert out["answer"].startswith("Not available yet: no build is live")


# ---- live r1: decision1 loop (uc-013, uc-026), column alias (uc-001), persona runner --------------------------------------------------

def test_last_period_figures_never_block_decision_one():
    from sh_platform.v1 import t1_seeds as S
    from sh_platform.v1 import t1_templates as T
    fields = S.fields_from(S.reporting_sections())
    bench = next(f for f in fields if f["key"] == "benchmarks")
    assert not bench["required"]  # a confirm or the usual practice leaves nothing to re-ask
    assert not [g for g in T.missing_required({"fields": [bench]}, {}) if "reported last period" in g]


def test_a_column_alias_with_spaces_is_slugged_before_the_check():
    from sh_platform.v1 import b10_design as D
    from sh_platform.v1 import e0a_catalogue as E
    assert E.slug("unmatched count") == "unmatched_count" and E.slug("Allocation drift (%)") == "allocation_drift" and E.slug("ok_name") == "ok_name"
    cols = D.check_columns([{"name": "unmatched count", "type": "int"}, {"name": "Allocation Drift", "type": "text"}])
    assert [c["name"] for c in cols] == ["unmatched_count", "allocation_drift"]


def test_persona_runner_says_the_usual_practice_once_per_distinct_gap_set():
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[2].joinpath("docs/test/uc-live/uc6-scripts/v3_persona.py").read_text(encoding="utf-8")
    assert 'gk not in s["retried"]' in src and 'gaps_said' not in src and 's["confirms"] > 4' in src


def test_a_gap_that_comes_back_after_a_confirm_is_one_plain_question_never_another_confirm(tmp_path, monkeypatch):
    """r1 uc-013: Span's open question survived each Confirm (the fill could not answer it), so Decision 1 came back and the runner confirmed 4 times."""
    import pytest
    from sh_platform.v1 import v3_plan_guard as PG
    from sh_platform.v1 import v3_signoff as SO
    gap = "Master-data owner assignment: who owns each record"
    monkeypatch.setattr(SO, "blocking", lambda plane, iid: [gap])
    monkeypatch.setattr(PG, "figures_gap", lambda plane, th, iid: [])
    monkeypatch.setattr(SO, "fill", lambda x, gaps: gaps)  # the usual practice cannot answer it
    monkeypatch.setattr(H, "_no_earlier_figures", lambda *a: None)
    monkeypatch.setattr(H, "_gaps", lambda x, iid: [gap])
    monkeypatch.setattr(SO, "guard", lambda *a: None)
    monkeypatch.setattr(H, "start_chain", lambda *a, **k: (_ for _ in ()).throw(AssertionError("the sign step ran again")))
    plane = SimpleNamespace(path=lambda *a: tmp_path.joinpath(*a))
    app = SimpleNamespace(state=SimpleNamespace(account_store={"a1": {"display_name": "Anita"}}))
    th = {"id": "t-loop", "created": "2026-10-17", "stage": "decision1", "iid": "int-1", "started_by": "Anita", "events": [], "steps": [],
          "decision": {"n": 1, "title": "Is this what you want?", "brief": {}, "gaps": [gap]}}
    x = SimpleNamespace(app=app, plane=plane, th=th, account_id="a1")
    with pytest.raises(H.Q) as first:  # the first confirm: the sign step asks with the full sign-off wording and remembers the gap
        SO.before_sign(x)
    assert "confirm it again" in first.value.text and th["sign_gaps"] == [gap]
    with pytest.raises(H.Q) as again:  # a retry of the sign step with the same gap: the plain question, no "confirm it again"
        SO.before_sign(x)
    assert again.value.text == f"I still need {gap} before this can be signed."
    H.save(plane, th)
    out = H.decide(app, plane, "t-loop", 1, "confirm", {}, "a1")  # Decision 1 confirmed again with the same gap: asked, not signed
    assert out["stage"] == "question" and out["events"][-1] == {**out["events"][-1], "kind": "question", "text": f"I still need {gap} before this can be signed."}
    assert out["resume"]["chain"] == "A" and not any(e["kind"] == "decision_done" for e in out["events"])
    with pytest.raises(ValueError):  # no Confirm is offered while the question is open
        H.decide(app, plane, "t-loop", 1, "confirm", {}, "a1")
    monkeypatch.setattr(SO, "blocking", lambda plane, iid: ["Success: how you will know it worked"])  # a different gap: the normal Decision 1 again
    assert H.still_needs(plane, {**th, "stage": "decision1"}) is None


def test_a_resolved_path_in_the_extended_windows_form_is_still_inside_the_plane(tmp_path, monkeypatch):
    """test_v3_rows failed now and then with "path outside company plane": four judge threads made v3/judge at once and Path.resolve (3.11,
    Windows) returned the extended form (prefix \\\\?\\), which is_relative_to the plain root never accepts."""
    import pathlib
    import pytest
    from sh_platform.plane import CompanyPlane, CrossCompanyError
    plane = CompanyPlane("evergreen", tmp_path)
    real = pathlib.Path.resolve
    monkeypatch.setattr(pathlib.Path, "resolve", lambda self, strict=False: pathlib.Path("\\\\?\\" + str(real(self))))
    assert plane.path("v3", "judge") == tmp_path / "v3" / "judge"
    with pytest.raises(CrossCompanyError):  # the prefix is dropped, never the check
        plane.path("..", "other")
