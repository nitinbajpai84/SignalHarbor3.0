"""Live run 7, the three cards stopped at "The run on the copy stopped at the step that builds gold_..." (synthetic data only).

uc-055-corpact: the number guard blanked the 14 of "interval '14' day" in Span's model design (the intent says "two weeks"), so the SQL read
"interval 'not available yet' day"; the plan check let it through and the run stopped on it. uc-075-yearwalk: the model aliased a CTE "is", a DuckDB
reserved word; the plan check swallowed DuckDB's parser error. uc-099-newfeed: the feed_mapping recipe was dropped because its mapping tables were
"filled by no load" (the mapping is proposed when the file is read, after the pack), and the model's stand-in compared the text confidence with 100;
the plan check forgave that as a guessed type. In all three the failing table was Span's model design from the pack, which the run did not hold
because only tables designed by v3_figures were known as the model's. Also: a figure name a design lists ("Calls due within 7 days") is a name, never
a number to blank."""
from __future__ import annotations

import json
import types

import pytest
import sqlglot

from sh_platform.agents.guard import NOT_AVAILABLE, check_numbers
from sh_platform.plane import PlaneStore
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import b6_span as S
from sh_platform.v1 import v3_harbor as H
from sh_platform.v1 import v3_plan_guard as PG
from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import wh
from sh_platform.v1.b6_plan import Refused
from tools import seed_evergreen as EG


# ---- the number guard: names and SQL code are not figures ---------------------------------------------------------------------------------

def _design(sql: str, kpis: list[str]) -> str:
    return json.dumps({"gold": [{"name": "gold_x_calls", "kpis": kpis, "purpose": "Calls due soon.", "sql": sql}]})


def test_a_figure_name_a_design_lists_is_never_rewritten():
    got = check_numbers(_design("create table gold_x_calls as select 1 as n from calls", ["Calls due within 7 days", "Top 5 holdings"]), [], "Design.")
    assert '"kpis": ["Calls due within 7 days", "Top 5 holdings"]' in got.text and got.replaced == 0  # was "Calls due within not available yet days"


def test_zero_one_and_an_alias_digit_in_the_sql_are_code_but_a_threshold_the_intent_does_not_state_is_still_blanked():
    sql = ("create table gold_x_calls as select coalesce(sum(ps2.v), 0) / nullif(count(*), 0) as r from position_snapshots ps2 "
           "where ps2.d <= current_date + interval '14' day limit 1")
    got = check_numbers(_design(sql, []), [], "Design.")
    assert "coalesce(sum(ps2.v), 0) / nullif(count(*), 0)" in got.text and "limit 1" in got.text  # were "not available yet" (uc-001, uc-008, uc-013)
    assert f"interval '{NOT_AVAILABLE}' day" in got.text and got.replaced == 1  # uc-055: still blanked, and the plan check refuses it below
    assert check_numbers("We hold 0 funds and 1 loan.", [], "q").replaced == 2  # outside a design's sql, 0 and 1 are checked as before


# ---- the plan check -------------------------------------------------------------------------------------------------------------------------

def test_uc055_sql_the_guard_blanked_is_refused_before_the_run():
    t = {"name": "gold_x_upcoming", "sql": f"create table gold_x_upcoming as select * from corporate_actions where pay_date <= current_date + interval '{NOT_AVAILABLE}' day"}
    assert "not available yet" in PG.guard_mark(t) and PG.guard_mark({"sql": "create table g as select 1"}) is None


def _sel(sql: str):
    return sqlglot.parse_one(sql, read="duckdb")


def test_uc075_a_reserved_word_alias_is_refused_before_the_run():
    sql = "select is.total_income as total_income from (select sum(cm.amount) as total_income from cash_movements as cm) as is"
    with pytest.raises(Refused, match="syntax error"):
        B._bind("gold_x_worth_summary", _sel(sql), {"cash_movements": {"amount": "decimal(18,2)"}})
    B._bind("gold_x_worth_summary", _sel(sql.replace(" is", " ism")), {"cash_movements": {"amount": "decimal(18,2)"}})


def test_uc099_text_compared_with_a_number_is_refused_on_the_model_types_and_forgiven_on_a_guessed_gold_type():
    sql = "select smc.source_column from sheet_mapping_columns as smc where smc.confidence < 100"
    with pytest.raises(Refused, match="Cannot compare"):
        B._bind("gold_x_mapping_exceptions", _sel(sql), {"sheet_mapping_columns": {"source_column": "varchar", "confidence": "varchar"}})
    B._bind("gold_x_y", _sel("select g.a from gold_x as g where g.a < 100"), {"gold_x": {"a": "varchar"}})  # a gold column's type is the check's guess


@pytest.fixture()
def plane(tmp_path):
    EG.company(tmp_path)
    p = PlaneStore(str(tmp_path)).plane_for("evergreen").ensure()
    wh.use(p)
    return p


def test_uc099_the_feed_mapping_recipe_is_not_dropped_before_the_file_is_read(plane):
    t = R._table("we_will_get_a_new_custodian_fi", R.recipe("feed_mapping"), {"name": "Mapping confidence"})
    with wh.connect(plane) as con:
        con.execute("delete from sheet_mapping_columns")
    assert S.reads_nothing_loaded(plane, {"tables": []}, t["sql"]) is None  # was: "reads only sheet_mapping_columns, ... which no file load fills"


# ---- the run on the copy: a pack table Span drew with the model is held, not a dead end ----------------------------------------------------

class _Api:
    def __init__(self, gold: list[dict]):
        self.gold, self.calls, self.failed = gold, [], True

    def __call__(self, who, method, path, body=None, files=None, data=None, soft=False):
        self.calls.append((method, path, body))
        if path.endswith("/pack"):
            return {"pack": {"state": "approved", "target": {"gold": self.gold}}}
        if path.endswith("/pack/edit") and body["section"] == "gold_remove":
            self.gold = [g for g in self.gold if g["name"] != body["key"]]
            self.failed = False
            return {}
        if path.endswith("/builder"):
            err = f"{self.gold[0]['name']} could not be built: Binder Error: Cannot compare values of type VARCHAR and type INTEGER_LITERAL" if self.failed else None
            return {"can": {}, "round": {"state": "ran", "run": {"run_id": "r1", "status": "failed" if self.failed else "ok", "error": err,
                                                                  "steps": [{"status": "failed", "label": "Columns in doubt."}] if self.failed else []}}}
        return {}


class _Plane:
    def __init__(self, root):
        self.root = root

    def path(self, *parts):
        return self.root.joinpath(*parts)


def _x(tmp_path, gold, cached: list[str]):
    d = tmp_path / "v3" / "design_cache"
    d.mkdir(parents=True)
    (d / "k.json").write_text(json.dumps({"gold": [{"name": n, "sql": "create table ..."} for n in cached]}), encoding="utf-8")
    api = _Api(gold)
    th = {"id": "t-r7", "pid": "prj-1", "figures": [{"kpi": "Mapping confidence", "table": gold[0]["name"]}]}
    return types.SimpleNamespace(th=th, api=api, plane=_Plane(tmp_path)), api


def test_a_pack_table_the_model_designed_that_fails_on_the_copy_is_held_and_the_run_goes_on(tmp_path, monkeypatch):
    from sh_platform.v1 import v3_rows
    monkeypatch.setattr(v3_rows, "send", lambda x: None)
    t = "gold_we_will_get_a_new_custodian_fi_mapping_exceptions"
    x, api = _x(tmp_path, [{"name": t, "kpis": [], "purpose": "Lists columns in doubt."}, {"name": "gold_x_other", "kpis": ["Other"]}], [t])
    assert H.b_run(x) == "ran on a copy"  # was: "The run on the copy stopped at the step that builds ..." and the card STUCK
    assert x.th["held_tables"][t]["kpis"] == ["Mapping confidence"] and [g["name"] for g in api.gold] == ["gold_x_other"]


def test_a_recipe_table_that_fails_is_still_a_question_even_when_a_design_reply_named_it(tmp_path, monkeypatch):
    from sh_platform.v1 import v3_rows
    monkeypatch.setattr(v3_rows, "send", lambda x: None)
    t = "gold_x_feed_mapping"
    x, api = _x(tmp_path, [{"name": t, "kpis": ["Mapping confidence"], "purpose": "Recipe feed_mapping: ..."}], [t])
    with pytest.raises(H.Q, match="Cannot compare"):
        H.b_run(x)
    assert len(api.gold) == 1
