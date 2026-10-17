"""Live run 2, classes (b) and (e) of docs/v3/LIVE-R2-ANALYSIS.md, plus uc-016. Each case is the live office's condition, recreated on the office6m files loaded
through the real readers (test_w2_loader.py's `office` fixture) inside a transaction that is rolled back. Synthetic data only."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_recipes as R

_SPEC = importlib.util.spec_from_file_location("w2_loader_tests_r2b", Path(__file__).with_name("test_w2_loader.py"))
W2 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(W2)
office = W2.office

LIMIT_DIMS = "('asset_class', 'manager', 'single_name')"


def _rows(o, rid):
    return sorted((tuple(str(v) for v in r.values()) for r in o.run(rid)))


def _as_limits(con, rename_bucket: str | None = None):
    """The live office: the signed limits are typed `limit` and name the portfolio as portfolio_code (seed and limits workbook, e3_rules.import_signed)."""
    ids = f"select r.id from business_rules as r join rule_versions as v on v.business_rule_id = r.id where json_extract_string(v.parameters, '$.dimension') in {LIMIT_DIMS}"
    con.execute(f"update business_rules set rule_type = 'limit' where id in ({ids})")
    con.execute(f"update rule_versions set parameters = replace(cast(parameters as varchar), '\"portfolio\"', '\"portfolio_code\"') "
                f"where json_extract_string(parameters, '$.dimension') in {LIMIT_DIMS}")
    if rename_bucket:
        con.execute(f"update rule_versions set parameters = json_merge_patch(parameters, '{{\"bucket\": \"{rename_bucket}\"}}') "
                    "where json_extract_string(parameters, '$.dimension') = 'single_name'")


# ---- uc-032, uc-033, uc-048: limits signed as type limit --------------------------------------------------------------------------------------

def test_uc032_033_048_limits_typed_limit_give_the_same_tables_as_policy_limits(office):
    ids = ["drift_vs_target", "single_name_breach", "limit_changes"]
    before = {rid: _rows(office, rid) for rid in ids}
    assert all(before.values())
    office.con.execute("begin")
    try:
        _as_limits(office.con)
        assert office.one("select count(*) from business_rules where rule_type = 'limit'") > 0
        after = {rid: _rows(office, rid) for rid in ids}
    finally:
        office.con.execute("rollback")
    assert after == before


def test_uc033_a_single_name_limit_whose_bucket_names_a_holding_tests_that_holding_only(office):
    office.con.execute("begin")
    try:
        _as_limits(office.con, rename_bucket="Harborview Semiconductor")
        rows = office.run("single_name_breach")
    finally:
        office.con.execute("rollback")
    assert rows and {r["holding"] for r in rows} == {"Harborview Semiconductor"}


# ---- uc4, uc5, uc-024, uc-035: a recipe's table holds its figure by its columns' meaning -----------------------------------------------------

def test_uc4_uc5_uc024_uc035_a_recipe_table_holds_the_figure_its_column_names_do_not_spell():
    for figure, rid in [("Time‑weighted return net of fees", "time_weighted_return"), ("Single-name breaches and cost to cure", "single_name_breach"),
                        ("Traceability coverage", "trace_coverage"), ("Controls", "ddq_compare")]:
        t = R._table("p", R.recipe(rid), {"name": figure})
        cols = [e.alias_or_name for e in F.projections(t["sql"])]
        assert not F.has_column(figure, cols), rid  # the live r2 drop: "its design had no column for it"
        assert F.holds(t, figure), rid
    model = {"sql": "create table g as select month, net_worth from x", "purpose": "a model design"}
    assert not F.holds(model, "Time-weighted return net of fees")  # a model's design still needs a column for the figure


def test_uc4_a_benchmark_loaded_twice_is_counted_once(office):
    before = _rows(office, "time_weighted_return")
    con = office.con
    con.execute("begin")
    try:  # the live office had the same approved benchmark definition twice (seed and pack): the benchmark return came out doubled
        con.execute("create temp table d0 as select * from benchmark_definitions where lower(approval_status) = 'approved'")
        con.execute("create temp table c0 as select c.* from benchmark_components as c join d0 on d0.id = c.benchmark_definition_id")
        con.execute("create temp table m as select id as old, uuid() as new from d0")
        con.execute("update d0 set id = (select new from m where old = d0.id)")
        con.execute("update c0 set id = uuid(), benchmark_definition_id = (select new from m where old = c0.benchmark_definition_id)")
        con.execute("insert into benchmark_definitions select * from d0")
        con.execute("insert into benchmark_components select * from c0")
        after = _rows(office, "time_weighted_return")
    finally:
        con.execute("rollback")
    assert after == before


# ---- uc-016: the person's words name the columns-changed recipe -------------------------------------------------------------------------------

def test_uc016_a_renamed_column_binds_columns_changed():
    said = "The administrator renamed a column in their June file. Hold the load until I decide."
    assert R.asks(said, R.recipe("columns_changed"))
    kpis = [{"name": "Net worth", "definition": "Total value of all family assets", "formula": "x", "period": "monthly", "owner": "x", "status": "defined"}]
    R.bind(None, None, kpis, said, [], said)
    assert [k["built_from"] for k in kpis if k.get("pack_suggested")] == ["columns_changed"]


def test_uc016_columns_changed_shows_old_and_new_name_and_batches_on_the_old_one(office):
    rows = office.run("columns_changed")
    assert any(r["old_name"] == "Market Value" and r["change"] == "renamed" and r["batches_on_old_name"] >= 1 for r in rows)


# ---- uc-039, uc-041 (class e): a shadow commitment row is left out, as commitments_by_fund leaves it out ---------------------------------------

def test_uc039_uc041_shadow_commitment_rows_do_not_add_funds_or_uncalled(office):
    before = {rid: _rows(office, rid) for rid in ("fund_irr_tvpi", "commit_check", "commitments_by_fund")}
    con = office.con
    con.execute("begin")
    try:  # the live office: one more register row per fund with no source, no called figure and no call (seed rows beside the pack's register)
        con.execute("create temp table s as select * from commitments as x where not exists (select 1 from commitments as y where y.supersedes_commitment_id = x.id) "
                    "and x.called_to_date is not null")
        con.execute("update s set id = uuid(), source_record_id = null, called_to_date = null, called_as_at = null, supersedes_commitment_id = null")
        con.execute("insert into commitments select * from s")
        after = {rid: _rows(office, rid) for rid in before}
    finally:
        con.execute("rollback")
    assert after == before
