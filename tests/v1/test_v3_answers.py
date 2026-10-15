"""Honest answers (c2): a question about the live project's figures is answered from rows or by one "Not available yet" line built from the thread's
own record, never by a reply that asks for records, guesses why or concludes without a figure. And two design checks behind the figures: SQL that
DuckDB cannot bind is refused before the run (b6_plan._bind), and a gold table that reads only tables nothing loads is refused (b6_span)."""
from types import SimpleNamespace

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import b6_span as S
from sh_platform.v1 import v3_board_routes as R
from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import wh
from sh_platform.v1.b6_plan import Refused
from tools import seed_evergreen as EG

KPIS = [{"name": "Net worth by portfolio", "definition": "Value of each portfolio"}, {"name": "Total mismatched amount", "definition": "Sum of differences"}]
TH = {"id": "t-1", "pid": "prj-1", "iid": "ini-1",
      "figures": [{"kpi": "Net worth by portfolio", "table": "gold_p_kpis", "rows": 4, "ok": False, "reason": "kpis has 4 rows but none holds a value for Net worth by portfolio."}],
      "exceptions": [{"title": "trading_export_20261005.csv did not load", "text": "Row 2: side 'sell usd / buy sgd' is not buy or sell."}]}


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    EG.company(tmp_path)
    p = PlaneStore(str(tmp_path)).plane_for("evergreen").ensure()
    wh.use(p)
    monkeypatch.setattr(F, "kpis_of", lambda plane, iid: KPIS)
    return p


def test_a_number_is_a_figure_but_a_date_a_year_or_a_file_name_is_not():
    assert R.has_figure("Entity B is off by 12,400 on 8 October.")
    assert R.has_figure("Concentration is 5.75% in Q3 2026.")
    assert not R.has_figure("There is no net worth figure for Evergreen Liquid on 30 September 2026.")
    assert not R.has_figure("The variance is minimal.")
    assert not R.has_figure("trading_export_20261005.csv did not load; trade T-20261005-004.")
    assert not R.has_figure("Net worth is $not available yet USD.")  # the number guard's mark: a blanked figure


def test_a_figure_question_is_told_from_a_how_to_or_a_greeting():
    for q in ("What was the Evergreen Liquid portfolio worth at 30 September 2026?", "How much does the FX forward confirmation differ from our record?",
              "What changed at Kestrel Ridge since the last meeting?", "Which holding is over its single-name limit?"):
        assert R.asks_figure(q, []), q
    for q in ("How do I add a file?", "hello", "What does net worth mean?"):
        assert not R.asks_figure(q, []), q


@pytest.mark.parametrize("reply", [
    "I don't have the records of previous meetings. Could you share the previous status so I can cross-reference them?",
    "I couldn't find any reference to an FX forward confirmation. Please share which one.",
    "There is no net worth figure recorded for 30 September 2026. The data for your entities may still be loading.",
    "The variance is minimal."])
def test_a_reply_with_no_figure_or_asking_for_records_becomes_the_honest_line(plane, reply):
    got = R.honest(plane, "What was the Evergreen Liquid portfolio worth at 30 September 2026?", TH, {"answer": reply, "trace": [], "used": ["x"]})
    assert got["answer"].startswith("Not available yet: Net worth by portfolio has no figure in the ready tables.")
    assert "kpis has 4 rows but none holds a value" in got["answer"] and "Not loaded: trading_export_20261005.csv" in got["answer"]
    assert got["figure"] is None and got["used"] == []


def test_a_figure_the_brief_does_not_name_lists_the_brief_figures_and_what_did_not_load(plane):
    got = R.honest(plane, "How much does the FX forward confirmation differ from our record?", TH, {"answer": "Please share which one.", "trace": []})
    assert got["answer"].startswith("Not available yet: no ready table of this project holds that figure (its figures are Net worth by portfolio, Total mismatched amount).")
    assert "Not loaded: trading_export_20261005.csv" in got["answer"]


def test_a_reply_with_a_figure_a_how_to_and_no_live_project_pass_unchanged(plane):
    with_figure = {"answer": "Entity B is off by 12,400 on 8 October.", "trace": []}
    assert R.honest(plane, "Which entity has a cash break on 8 October and by how much?", TH, with_figure) is with_figure
    how_to = {"answer": "Open Build and drop the file.", "trace": []}
    assert R.honest(plane, "How do I add a file?", TH, how_to) is how_to
    assert R.honest(plane, "What is our net worth?", None, how_to) is how_to


def test_the_ask_route_guards_lumens_reply(plane, monkeypatch):
    monkeypatch.setattr(R.P, "answer", lambda plane, text: None)
    monkeypatch.setattr(R.C, "liquidity_answer", lambda *a: None)
    monkeypatch.setattr(F, "figure_answer", lambda *a: None)
    monkeypatch.setattr(R, "_live", lambda plane: TH)
    monkeypatch.setattr(R.T, "ask", lambda *a: {"reply": "Could you share the previous status?", "rules_only": False, "trace_id": None})
    got = R._ask(plane, SimpleNamespace(), "What was the Evergreen Liquid portfolio worth at 30 September 2026?", "prj-1")
    assert got["answer"].startswith("Not available yet: Net worth by portfolio")


SCHEMA = {"legal_entities": {"id": "uuid", "entity_name": "text"}, "cash_movements": {"portfolio_id": "uuid", "amount": "numeric(18,2)"},
          "portfolios": {"id": "uuid", "legal_entity_id": "uuid"}}


def _t(sql):
    return {"name": "gold_x", "depends_on": list(SCHEMA), "sql": f"create table gold_x as {sql}"}


def test_a_join_that_uses_a_table_named_later_in_the_from_is_refused_before_the_run():
    bad = ("select le.id, sum(cm.amount) as amount from legal_entities le left join cash_movements cm on cm.portfolio_id = p.id "
           "left join portfolios p on p.legal_entity_id = le.id group by le.id")  # c2 ops_lead: sqlglot's qualify passed it, DuckDB did not
    with pytest.raises(Refused, match="Referenced table \"p\" not found"):
        B._check_sql(_t(bad), SCHEMA, set(SCHEMA))
    good = ("select le.id, sum(cm.amount) as amount from legal_entities le left join portfolios p on p.legal_entity_id = le.id "
            "left join cash_movements cm on cm.portfolio_id = p.id group by le.id")
    assert B._check_sql(_t(good), SCHEMA, set(SCHEMA))[1] == set(SCHEMA)


def test_a_gold_table_on_tables_nothing_loads_and_that_hold_nothing_is_refused_with_the_loaded_tables_named(plane):
    with wh.connect(plane) as con:
        con.execute("create table x_metric_values (v decimal(18,2))")
    msg = S.reads_nothing_loaded(plane, {"tables": []}, "create table gold_x as select sum(v) as v from x_metric_values")
    assert msg.startswith("it reads only x_metric_values, which no file load fills") and "position_snapshots (" in msg
    assert S.reads_nothing_loaded(plane, {"tables": []}, "create table gold_x as select count(*) as n from position_snapshots") is None  # a load fills it
    assert S.reads_nothing_loaded(plane, {"tables": [{"name": "x_metric_values"}]}, "create table gold_x as select sum(v) as v from x_metric_values") is None
    assert S.reads_nothing_loaded(plane, {"tables": []}, "create table gold_y as select sum(v) as v from gold_x") is None  # an earlier gold table of the draft
    with wh.connect(plane) as con:
        con.execute("insert into x_metric_values values (1)")
    assert S.reads_nothing_loaded(plane, {"tables": []}, "create table gold_x as select sum(v) as v from x_metric_values") is None


def test_a_column_outside_the_group_by_is_refused_before_the_run():
    schema = {"cash_movements": {"entity_id": "uuid", "effective_date": "date", "amount": "numeric(18,2)", "likely_cause": "text"}}
    bad = ("select cm.entity_id, sum(cm.amount) as cash, case when sum(cm.amount) > 5000 then cm.likely_cause else null end as likely_cause "
           "from cash_movements as cm group by cm.entity_id")  # c2 ops_lead second run: stopped the run on the copy
    with pytest.raises(Refused, match="must appear in the GROUP BY"):
        B._check_sql({"name": "gold_x", "depends_on": ["cash_movements"], "sql": f"create table gold_x as {bad}"}, schema, set(schema))


def test_a_literal_that_cannot_be_cast_to_its_column_is_refused_before_the_run():
    schema = {"cash_movements": {"organization_id": "uuid", "effective_date": "date", "amount": "numeric(18,2)"}}
    bad = "select cm.effective_date, sum(cm.amount) as total from cash_movements as cm where cm.organization_id = 'Entity B' group by cm.effective_date"
    with pytest.raises(Refused, match="Could not convert string 'Entity B'"):  # c2 ops_lead third run
        B._check_sql({"name": "gold_x", "depends_on": ["cash_movements"], "sql": f"create table gold_x as {bad}"}, schema, set(schema))


# ---- c3: a wrong figure stated as fact, and a chatty reply that slipped the guard ------------------------------------------------------------------

def _report(plane, name, day, fields):
    from sh_platform.v1.e1_write import org_id
    with wh.connect(plane) as con:
        did = wh.new_id()
        con.execute("insert into documents (id, organization_id, source_system_id, access_group_id, document_type, title, original_filename, original_uri, content_hash, valuation_date, document_status, received_at, recorded_at, processing_status) "
                    "values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [did, org_id(plane), wh.new_id(), wh.new_id(), "reports_and_packs", name, name, name, name, day, "final", wh.now(), wh.now(), "needs_match"])
        for i, (label, v, ccy) in enumerate(fields):
            con.execute("insert into extracted_fields (id, organization_id, document_id, field_name, value_text, value_numeric, currency, page_number, line_number, confidence, review_status) "
                        "values (?,?,?,?,?,?,?,?,?,?,?)", [wh.new_id(), org_id(plane), did, label, str(v), v, ccy, 1, i, "high", "confirmed"])


def test_the_latest_report_total_is_read_from_the_stored_fields_of_the_latest_period(plane):
    from datetime import date
    _report(plane, "Report_2026-08.xlsx", date(2026, 8, 31), [("Total", 50000000, "USD")])
    _report(plane, "Report_2026-09.xlsx", date(2026, 9, 30), [("Evergreen Growth I", 10000000, "USD"), ("Total", 57600000, "USD"), ("Total (SGD)", 77253120, "SGD")])
    _report(plane, "Report_2026-09.pdf", date(2026, 9, 30), [("Total (USD)", 57600000, "USD")])
    got = F.report_total(plane, "What are we worth in the latest report?")
    assert "57,600,000" in got["answer"] and "30 September 2026" in got["answer"] and "Report_2026-09.pdf" in got["answer"] and "50,000,000" not in got["answer"]
    assert "USD 57,600,000" in F.report_total(plane, "What are we worth in the latest report in USD?")["answer"]
    assert "SGD" not in F.report_total(plane, "What are we worth in the latest report in USD?")["answer"]
    assert F.report_total(plane, "What are we worth?") is None  # no report named


def test_two_different_totals_in_one_currency_are_not_answered(plane):
    from datetime import date
    _report(plane, "R_a.xlsx", date(2026, 9, 30), [("Total", 1, "USD")])
    _report(plane, "R_b.pdf", date(2026, 9, 30), [("Total (USD)", 2, "USD")])
    assert F.report_total(plane, "What are we worth in the latest report?") is None


def test_a_currency_column_is_a_unit_not_a_name_and_the_part_is_said(plane, monkeypatch):
    from decimal import Decimal
    from datetime import date
    from sh_platform.v1 import cx_dash as CD
    t = {"name": "gold_nw", "columns": [{"name": n, "type": ty} for n, ty in (("date", "DATE"), ("currency", "VARCHAR"), ("portfolio", "VARCHAR"), ("net_worth", "DECIMAL(18,2)"))]}
    rows = [{"date": date(2026, 9, 30), "currency": "USD", "portfolio": "EG-GROWTH", "net_worth": Decimal("10")}, {"date": date(2026, 9, 30), "currency": "USD", "portfolio": "EG-LIQUID", "net_worth": Decimal("30")}]
    monkeypatch.setattr(CD, "run_sql", lambda plane, sql: (None, rows, None))
    monkeypatch.setattr(F, "aliases", lambda plane: {})
    monkeypatch.setattr(F, "masters", lambda plane: [("portfolio", [{"EG-GROWTH"}, {"EG-LIQUID"}, {"X3"}, {"X4"}, {"X5"}])])
    got = F._read(plane, t, {"name": "Net worth"}, "What are we worth?", {})
    assert got["answer"].startswith("Net worth across the 2 portfolios loaded (of 5) in September 2026:") and "for USD" not in got["answer"] and "USD" not in got["answer"].split(":")[0]
    assert "Total 40.00" in got["answer"] or "Total 40" in got["answer"]


def test_the_rules_reply_after_a_blanked_figure_becomes_the_honest_line(plane):
    reply = ("Rules-only reply: I could not check a figure in my answer against the data, so I left it out. About For every fund I want: This project has 1 set of "
             "figures ready for dashboards: Shows for each fund the lag in days. You can see 0 dashboards.")
    assert not R.has_figure(reply)
    got = R.honest(plane, "Which statement is missing and how overdue is it?", TH, {"answer": reply, "trace": [], "used": []})
    assert got["answer"].startswith("Not available yet:")


# ---- c3: the valuations answer "what changed" when no ready table does -------------------------------------------------------------------------------

def _val(plane, con, inst, day, amount, sup=None, doc=None, mgr="Northgate Partners"):
    from sh_platform.v1.e1_write import org_id
    vid = wh.new_id()
    con.execute("insert into valuation_observations (id, organization_id, instrument_id, valuation_date, received_at, recorded_at, value_amount, currency, valuation_type, approval_status, "
                "supersedes_valuation_id, evidence_document_id) values (?,?,?,?,?,?,?,?,?,?,?,?)", [vid, org_id(plane), inst, day, wh.now(), wh.now(), amount, "USD", "manager_estimate", "unapproved", sup, doc])
    return vid


def _inst(plane, con, name, mgr, ident=()):
    from sh_platform.v1.e1_write import org_id
    iid = wh.new_id()
    con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, manager_name, currency, created_at) values (?,?,?,?,?,?,?)", [iid, org_id(plane), name, "fund", mgr, "USD", wh.now()])
    for kind, v in ident:
        con.execute("insert into instrument_identifiers (id, organization_id, instrument_id, source_system_id, identifier_type, identifier_value, mapping_status) values (?,?,?,?,?,?,?)",
                    [wh.new_id(), org_id(plane), iid, wh.new_id(), kind, v, "approved"])
    return iid


def test_a_superseded_valuation_answers_original_amended_and_change_with_its_document(plane):
    from datetime import date
    from decimal import Decimal
    day = date(2026, 9, 30)
    with wh.connect(plane) as con:
        eg = _inst(plane, con, "Evergreen Growth I", "Northgate", [("manager_fund_name", "Fund A - Evergreen Growth I")])
        other = _inst(plane, con, "Cedar Credit II", "Cedar")
        old = _val(plane, con, eg, day, Decimal("10000000"))
        _val(plane, con, eg, day, Decimal("10180000"), sup=old)
        _val(plane, con, other, day, Decimal("5000000"))
        did = wh.new_id()
        con.execute("update valuation_observations set evidence_document_id = null")
        from sh_platform.v1.e1_write import org_id
        con.execute("insert into documents (id, organization_id, source_system_id, access_group_id, document_type, title, original_filename, original_uri, content_hash, valuation_date, document_status, received_at, recorded_at, processing_status) "
                    "values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [did, org_id(plane), wh.new_id(), wh.new_id(), "manager_statement", "x", "revision_notice_amended.eml", "x", "x", day, "final", wh.now(), wh.now(), "needs_match"])
        con.execute("update valuation_observations set evidence_document_id = ? where supersedes_valuation_id is not null", [did])
    want = "Evergreen Growth I at 30 September 2026: original 10,000,000, amended 10,180,000, change +180,000 (amended per revision_notice_amended.eml)"
    for q in ("Why did Fund A move since the issued September report?", "Why did Evergreen Growth I move since the issued September report?", "What changed since the issued report?"):
        assert F._revisions(plane, q, [])["answer"] == want + "."


def test_without_a_link_both_values_and_the_gap_are_said_and_a_later_valuation_is_listed_for_the_named_fund(plane):
    from datetime import date
    from decimal import Decimal
    with wh.connect(plane) as con:
        k = _inst(plane, con, "Kestrel Ridge Macro Fund", "Kestrel Ridge Advisors")
        _val(plane, con, k, date(2026, 7, 31), Decimal("7050000"))
        _val(plane, con, k, date(2026, 7, 31), Decimal("7012500"))
        _val(plane, con, k, date(2026, 8, 31), Decimal("7210000"))
    a = F._revisions(plane, "What changed at Kestrel Ridge since the last meeting?", [])["answer"]
    assert "7,012,500 and 7,050,000, which differ by 37,500 (the rows do not say which came later" in a and a.startswith("Kestrel Ridge Macro Fund at 31 August 2026: 7,210,000;")
    assert F._revisions(plane, "What changed at Cedar since the last meeting?", [])["answer"].startswith("Kestrel Ridge Macro Fund at 31 July")  # the one revision, named plainly
