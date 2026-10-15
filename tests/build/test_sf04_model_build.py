"""SF04: the sandbox model engine. Ported first from the earlier repo's tests/test_model_drafting.py (static checks name what
is wrong, surrogate key collisions, rationale references, a plan with no rationale) on a synthetic plan; then the SF04 card.
Synthetic data only; every plane is a tmp folder."""
import copy
import hashlib

import duckdb
import pytest

from sh_platform import warehouse as wh
from sh_platform.build import model_build as mb
from sh_platform.plane import CompanyPlane

VALUATIONS_1 = "fund_id,period_end,nav,manager\nF1,2026-07-31,100,Ann\nF2,2026-07-31,200,Ben\nF3,2026-08-31,50,Cat\n"
VALUATIONS_2 = "fund_id,period_end,nav,manager\nF1,2026-08-31,110,Dee\nF2,2026-08-31,210,Ben\n"
FUNDS_1 = "fund_id,fund_name,manager\nF1,Alpha,Ann\nF2,Beta,Ben\nF3,Gamma,Cat\n"
FUNDS_2 = "fund_id,fund_name,manager\nF1,Alpha,Dee\nF2,Beta,Ben\nF3,Gamma,Eve\n"
COLUMNS = {"valuations": ["fund_id", "period_end", "nav", "manager"], "funds": ["fund_id", "fund_name", "manager"]}
PLAN = {"silver_model": {"dimensions": [{"name": "dim_fund", "type": "scd2", "business_key": ["fund_id"], "source": ["funds"],
                                         "tracked_attributes": ["manager"]}],
                         "facts": [{"name": "fact_valuation", "grain": ["fund_id", "period_end"], "source": ["valuations"],
                                    "foreign_keys": [{"dimension": "dim_fund", "on": "fund_id"}]}]},
        "gold_contract": {"marts": [{"name": "mart_nav_total", "source_fact": "fact_valuation", "field": "nav", "op": "sum",
                                     "date": "period_end", "measure": "K12"},
                                    {"name": "mart_nav_latest", "source_fact": "fact_valuation", "field": "nav", "op": "latest",
                                     "date": "period_end"}]}}


def _plan():
    return copy.deepcopy(PLAN)


def _land(plane, source, name, text):
    plane.area("landing").mkdir(parents=True, exist_ok=True)
    plane.path("landing", name).write_text(text, encoding="utf-8")
    wh.load_bronze(plane, source, name)


@pytest.fixture
def plane(tmp_path):
    p = CompanyPlane("lakeside-family-office", tmp_path)
    _land(p, "valuations", "v1.csv", VALUATIONS_1)
    _land(p, "valuations", "v2.csv", VALUATIONS_2)
    _land(p, "funds", "f1.csv", FUNDS_1)
    _land(p, "funds", "f2.csv", FUNDS_2)
    return p


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- ported from tests/test_model_drafting.py

def test_a_valid_plan_passes_the_static_checks():
    model, gold = mb.normalise(_plan(), COLUMNS)
    assert mb.check(model, gold, COLUMNS) == []
    dim = model["dimensions"][0]
    assert dim["surrogate_key"] == "fund_key" and dim["current_flag"] == "row_is_current"


def test_static_checks_name_what_is_wrong():
    plan = _plan()
    plan["silver_model"]["dimensions"][0]["source"] = ["no_such_source"]
    plan["silver_model"]["facts"][0]["grain"] = ["fund_id", "ghost_col"]
    plan["gold_contract"]["marts"][0]["source_fact"] = "fact_nowhere"
    plan["gold_contract"]["marts"][1]["op"] = "median"
    model, gold = mb.normalise(plan, COLUMNS)
    errors = " | ".join(mb.check(model, gold, COLUMNS))
    assert "no_such_source" in errors and "ghost_col" in errors and "fact_nowhere" in errors and "op must be" in errors


def test_a_single_mart_object_is_accepted_as_a_list_of_one():
    plan = _plan()
    plan["gold_contract"]["marts"] = plan["gold_contract"]["marts"][0]
    _, gold = mb.normalise(plan)
    assert isinstance(gold["marts"], list) and gold["marts"][0]["name"] == "mart_nav_total"


def test_a_surrogate_key_never_collides_with_a_source_column():
    plan = _plan()
    plan["silver_model"]["dimensions"][0]["surrogate_key"] = "fund_id"
    model, gold = mb.normalise(plan, COLUMNS)
    assert model["dimensions"][0]["surrogate_key"] == "fund_id_sk"
    assert mb.check(model, gold, COLUMNS) == []
    model["dimensions"][0]["surrogate_key"] = "fund_name"  # a collision that survives is refused before anything is built
    assert any("already a column of" in e for e in mb.check(model, gold, COLUMNS))


def test_the_silver_builder_refuses_a_colliding_surrogate_key():
    con = duckdb.connect()
    con.execute("attach ':memory:' as co")
    con.execute("create schema co.bronze; create schema silver")
    con.execute("create table co.bronze.funds (fund_key varchar, fund_name varchar, _load_id varchar, _loaded_at timestamp)")
    dim = {"name": "dim_fund", "type": "scd1", "business_key": ["fund_key"], "surrogate_key": "fund_key", "source": ["funds"]}
    with pytest.raises(ValueError, match="already a column of"):
        mb.build_scd1_dimension(con, dim)


def test_an_unknown_rationale_reference_is_refused():
    plan = _plan()
    plan["rationale"] = {"entities": {"dim_fund": {"because": "manager changes matter", "from": ["a_document_never_shared.md"]}}}
    refs = mb.known_refs(list(COLUMNS), ["K12"])
    model, gold = mb.normalise(plan, COLUMNS)
    assert any("a_document_never_shared.md" in e for e in mb.check(model, gold, COLUMNS, refs))
    plan["rationale"]["entities"]["dim_fund"]["from"] = ["funds"]
    model, gold = mb.normalise(plan, COLUMNS)
    assert mb.check(model, gold, COLUMNS, refs) == []
    assert model["dimensions"][0]["description"] == "manager changes matter" and model["dimensions"][0]["provenance"] == ["funds"]


def test_a_plan_with_no_rationale_still_normalises_and_checks_cleanly():
    model, gold = mb.normalise(_plan(), COLUMNS)
    assert all("provenance" not in d for d in model["dimensions"] + model["facts"])
    assert mb._normalise_rationale(_plan()) == {"entities": {}, "marts": {}}


# --------------------------------------------------------------------------- SF04 acceptance

def test_1_a_valid_draft_builds_facts_dimensions_and_marts_with_counts(plane):
    model, gold = mb.normalise(_plan(), COLUMNS)
    rep = mb.sandbox_build(plane, "d0001", model, gold)
    assert rep["errors"] == []
    assert rep["built"] == {"silver": ["dim_fund", "fact_valuation"], "gold": ["mart_nav_total", "mart_nav_latest"]}
    assert rep["counts"]["fact_valuation"] == 5 and rep["counts"]["mart_nav_total"] == 2  # periods 2026-07, 2026-08
    assert set(rep) == {"built", "counts", "errors"}


def test_2_a_non_unique_grain_names_the_table_and_columns_only(plane):
    plan = _plan()
    plan["silver_model"]["facts"][0]["grain"] = ["period_end"]
    model, gold = mb.normalise(plan, COLUMNS)
    rep = mb.sandbox_build(plane, "d0002", model, gold)
    assert rep["errors"] == ["silver fact_valuation: grain period_end is not unique (duplicates exist)"]
    assert rep["built"]["gold"] == []  # stops before gold, later tables read this one


def test_3_an_scd2_dimension_keeps_one_current_row_per_key(plane):
    model, _ = mb.normalise(_plan(), COLUMNS)
    dim = model["dimensions"][0]
    con = duckdb.connect()
    con.execute("attach '" + str(plane.path("warehouse", "company.duckdb")) + "' as co (read_only)")
    con.execute("create schema silver")
    total, current = mb.build_scd2_dimension(con, dim)
    assert (total, current) == (5, 3)  # F1 and F3 changed manager; F2 did not, so no spurious version
    per_key = con.execute("select fund_id, count(*) filter (where row_is_current), max(manager) filter (where row_is_current) "
                          "from silver.dim_fund group by 1 order by 1").fetchall()
    assert per_key == [("F1", 1, "Dee"), ("F2", 1, "Ben"), ("F3", 1, "Eve")]
    con.close()


def test_4_a_conversion_error_carrying_a_value_is_scrubbed(plane):
    _land(plane, "valuations", "v3.csv", "fund_id,period_end,nav,manager\nF9,2026-09-30,SECRET-VALUE-77,Zed\n")
    plan = _plan()
    plan["silver_model"]["facts"][0]["grain"] = ["fund_id", "period_end", "nav"]
    model, gold = mb.normalise(plan, COLUMNS)
    rep = mb.sandbox_build(plane, "d0004", model, gold)
    assert rep["errors"] and rep["errors"][0] == "mart mart_nav_total: column nav: values do not fit type double"
    assert not any("SECRET" in e or "77" in e or "Zed" in e for e in rep["errors"])


def test_scrub_keeps_table_column_and_kind_and_drops_values():
    assert mb.scrub("Conversion Error: Could not convert string 'go to market' to DOUBLE when casting from source column nav\n\nLINE 1: x") \
        == "column nav: values do not fit type double"
    assert mb.scrub('Conversion Error: date field value out of range: "2026-13-01" when casting from source column period_end') \
        == "column period_end: values do not fit type date"
    assert mb.scrub("Catalog Error: Table with name missing_t does not exist!\nDid you mean \"pg_settings\"?") \
        == "Catalog Error: Table with name missing_t does not exist!"
    out = mb.scrub("Constraint Error: Duplicate key 'fund_id: F1' at row 1234 value: Ann Lee")
    assert "F1" not in out and "1234" not in out and "Ann" not in out and out.startswith("Constraint Error: Duplicate key")
    assert mb.scrub('Binder Error: Referenced column "nope" not found in FROM clause!\nCandidate bindings: "nav"') \
        == 'Binder Error: Referenced column "nope" not found in FROM clause!'


def test_5_the_company_warehouse_is_unchanged_after_a_run(plane):
    company = plane.path("warehouse", "company.duckdb")
    before = _sha(company)
    model, gold = mb.normalise(_plan(), COLUMNS)
    assert mb.sandbox_build(plane, "d0005", model, gold)["errors"] == []
    assert _sha(company) == before
    con = wh.open_company(plane)
    try:
        assert con.execute("select count(*) from information_schema.tables where table_schema in ('silver', 'gold')").fetchone()[0] == 0
    finally:
        con.close()


def test_6_the_sandbox_file_is_removed_even_when_a_build_fails(plane):
    plan = _plan()
    plan["silver_model"]["facts"][0]["grain"] = ["period_end"]
    model, gold = mb.normalise(plan, COLUMNS)
    assert mb.sandbox_build(plane, "d0006", model, gold)["errors"]
    assert not mb.sandbox_path(plane, "d0006").exists()
    assert mb.sandbox_build(plane, "d0007", *mb.normalise(_plan(), COLUMNS))["errors"] == []
    assert list(plane.path("warehouse", "sandbox").iterdir()) == []


def test_a_bad_draft_id_and_an_empty_company_are_refused(tmp_path, plane):
    with pytest.raises(ValueError):
        mb.sandbox_path(plane, "../company")
    empty = CompanyPlane("harbor-mutual", tmp_path / "other")
    rep = mb.sandbox_build(empty, "d0008", *mb.normalise(_plan(), COLUMNS))
    assert rep["errors"] == ["no bronze tables yet: the company warehouse has no data"]
