"""Cycle 1 triage, package P8 (Lumen, memory, Span): one test per ticket. Tmp plane, synthetic data, model off."""
import uuid

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import b6_span as S
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import e0a_catalogue as cat
from sh_platform.v1 import e1_write, mem_agent as M, p1_project, talk, wh

ADMIN = Viewer(name="Nitin", roles=frozenset({"company_admin"}), account_id="acc-admin")
ANA = Viewer(name="Leo", roles=frozenset({"analyst"}), account_id="acc-leo")
PART = Viewer(name="Sofia", roles=frozenset({"participant"}), account_id="acc-sofia")
GOLD = "gold_monthly_report_holdings_monthly"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    plane = PlaneStore(tmp_path / "data").create("acme")
    pid = p1_project.create_project(plane, "int-1", "Monthly report", "Nitin")["id"]
    with wh.connect(plane) as con:
        con.execute(f"create table {GOLD} (report_month date, entity varchar, net_worth_usd decimal(18,2), status varchar)")
        con.execute(f"insert into {GOLD} values ('2026-08-31','Fund A',100,'official'),('2026-08-31','Fund B',50,'estimated'),"
                    "('2026-09-30','Fund A',130,'official'),('2026-09-30','Fund B',45,'revised')")
    cat.register_gold(plane, pid, "monthly_report", "holdings_monthly", [{"name": "report_month", "type": "date"}])
    return plane, pid


def _accepted(plane, pid, did, sql, spec):
    t = D.add_proposal(plane, ADMIN, pid, did, {"title": "Net worth by entity", "kpi": "K01", "sql": sql, "spec": spec})
    D.decide(plane, ADMIN, pid, did, t["id"], True)
    return t


def _by_entity(plane, pid, did):
    return _accepted(plane, pid, did, f"select entity, sum(net_worth_usd) as net_worth_usd from {GOLD} where report_month = (select max(report_month) from {GOLD}) group by entity",
                     {"mark": "bar", "encoding": {"x": {"field": "entity", "type": "nominal"}, "y": {"field": "net_worth_usd", "type": "quantitative"}}})


# ---- a10.0: why did this move ----------------------------------------------------------------------------------------------------

def test_a10_0_entities_on_the_axis_are_not_periods(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "Board")
    t = _by_entity(plane, pid, d["id"])
    out = L.explain(plane, ADMIN, pid, d["id"], t["id"])
    # LQ-2: a one-date tile is explained against the date before, from its table; the entities stay splits, never periods
    assert " to " in out["answer"] and all(str(e.get("period", "20"))[:2] == "20" for e in out["evidence"])
    assert all("split" in e or "period" in e for e in out["evidence"]) and out["wording"] == "rules"


def test_a10_0_a_timed_tile_still_explains_with_whole_names(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "Board")
    t = L.ask(plane, ADMIN, pid, d["id"], "net worth usd by entity per month")["proposals"][0]
    out = L.explain(plane, ADMIN, pid, d["id"], t["id"])
    assert "150" in out["answer"] and "175" in out["answer"] and "Fund A" in out["answer"]
    assert out["caveats"][0] == L.NO_MODEL and "model is off" not in out["caveats"][0]  # a10.10


# ---- a10.4 and a4.8: figure questions --------------------------------------------------------------------------------------------

def test_a10_4_a_figure_question_gets_the_figure_not_table_names(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "Board")
    _by_entity(plane, pid, d["id"])
    reply = L.ask(plane, ADMIN, pid, d["id"], "What was total net worth at the end of September?")["reply"]
    assert "Net worth USD is 175 in total" in reply and "Fund A 130" in reply and "Fund B 45" in reply
    assert GOLD not in reply and "columns" not in reply and "Net worth by entity" in reply
    via_chat = talk.lumen_company(plane, ADMIN, "What was total net worth at the end of September?", pid)
    assert "175 in total" in via_chat and GOLD not in via_chat


def test_a10_4_a_question_about_tables_is_still_described(env):
    plane, pid = env
    d = D.create(plane, ADMIN, pid, "Board")
    _by_entity(plane, pid, d["id"])
    assert GOLD in L.ask(plane, ADMIN, pid, d["id"], "Which tables can I see?")["reply"]


def test_a4_8_a_benchmark_question_gets_the_benchmark_screen_figures(env, monkeypatch):
    plane, pid = env
    from sh_platform.v1 import k7_routes as K7
    org = e1_write.org_id(plane)
    with wh.connect(plane) as con:
        ent = str(uuid.uuid4())
        con.execute("insert into legal_entities (id, organization_id, entity_code, entity_name, base_currency) values (?,?,?,?,?)", [ent, org, "TR", "Trust", "USD"])
        for code, name in (("EG-LIQUID", "Evergreen Liquid portfolio"), ("EG-GROWTH", "Evergreen Growth portfolio")):
            con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values (?,?,?,?,?,'USD')",
                        [str(uuid.uuid4()), org, ent, code, name])
    monkeypatch.setattr(K7, "definitions", lambda p: {"definitions": [{"benchmark_code": "EG-OFFICE-BLEND", "benchmark_name": "Office blend", "version": 1, "status": "approved"}]})
    seen = {}

    def monthly(p, v, portfolio, code, start, end):
        seen.update(portfolio=portfolio, code=code, start=start)
        fig = lambda x: {"value": x, "pct": x}  # noqa: E731
        return {"version_used": {"version": 1, "name": "Office blend", "status": "approved"}, "months": [{
            "month": "2026-09", "portfolio": fig("4.1667"), "benchmark": fig("2.7072"), "difference": fig("1.4595"),
            "liquid_sleeve": {**fig("2.2602"), "difference": fig("1.9065")}, "certified": True, "problems": []}]}
    monkeypatch.setattr(K7, "monthly", monthly)
    raj = Viewer(name="Raj", roles=frozenset({"approver"}), account_id="acc-raj")
    reply = talk.lumen_company(plane, raj, "How did the Evergreen Liquid portfolio do against the office benchmark in September 2026, and is that figure certified?")
    assert seen == {"portfolio": "EG-LIQUID", "code": "EG-OFFICE-BLEND", "start": "2026-09"}
    assert "4.1667%" in reply and "2.7072%" in reply and "1.4595 points" in reply and "1.9065 points" in reply and "It is certified" in reply


def test_a4_8_one_locked_project_is_said_in_good_grammar():
    assert talk._lock_line([{"title": "Report", "owner": "Daniel Foo"}]).startswith(" There is 1 more project you cannot open")


# ---- a10.1-3: memory ---------------------------------------------------------------------------------------------------------------

def test_a10_2_a_preference_told_to_one_agent_does_not_replace_another_agents(env):
    plane, _ = env
    assert M.learn(plane, ANA, "tally", "From now on always answer in bullets.") == ["you like bullets answers"]
    assert M.learn(plane, ANA, "span", "I prefer short answers.") == ["you like short answers"]
    kept = {(i["agent"], i["text"]) for i in M.mine(plane, ANA)}
    assert ("tally", "Prefers: bullets answers") in kept and ("span", "Prefers: short answers") in kept


def test_a10_2_the_same_agent_still_replaces_its_own(env):
    plane, _ = env
    M.learn(plane, ANA, "span", "I prefer short answers.")
    M.learn(plane, ANA, "span", "I prefer detailed answers.")
    assert [i["text"] for i in M.mine(plane, ANA) if i["agent"] == "span"] == ["Prefers: detailed answers"]


def test_a10_3_a_one_off_request_beside_from_now_on_is_not_kept(env):
    plane, pid = env
    shown = M.learn(plane, ANA, "lumen", "From now on always use green for my charts. Show cash by entity per day.")
    assert shown == ["you like green for chart lines"]
    assert M.preferences(plane, ANA) == {"lumen.color": "green"}


def test_a10_3_a_remembered_colour_skipped_on_a_split_tile_is_said(env):
    plane, pid = env
    M.learn(plane, ADMIN, "lumen", "From now on always use green for my charts.")
    d = D.create(plane, ADMIN, pid, "Board")
    out = L.ask(plane, ADMIN, pid, d["id"], "Show net worth usd by entity per month")
    assert out["proposals"] and "I did not use green" in out["reply"] and "split by entity" in out["reply"]


# ---- a10.5, ev.10, ev.11: Span -----------------------------------------------------------------------------------------------------

PLAN = {"version": 1, "state": "live", "project_slug": "monthly_report", "sources": [{"code": "administrator"}], "tables": [
    {"name": "bronze_administrator_positions", "layer": "bronze", "columns": [{"name": "position_date", "type": "date", "from": "position date"}], "depends_on": []},
    {"name": GOLD, "layer": "gold", "purpose": "Month-end holdings by entity.", "depends_on": ["valuation_observations"], "columns": [
        {"name": "report_month", "type": "date", "from": "valuation date"}, {"name": "entity", "type": "varchar", "from": "legal entity"},
        {"name": "net_worth_usd", "type": "decimal", "from": "value"}, {"name": "status", "type": "varchar", "from": "approval status"}]},
    {"name": "gold_monthly_report_cash_daily", "layer": "gold", "purpose": "Cash per entity per day.", "depends_on": [], "columns": [
        {"name": "position_date", "type": "date", "from": "position date"}, {"name": "status", "type": "varchar", "from": "data status"}]}]}


def test_a10_5_span_answers_the_question_asked(env):
    plane, _ = env
    got = S.explain(plane, PLAN, "Which gold tables feed the dashboard, and how many months does the holdings table hold?")
    assert "2 gold tables" in got and f"{GOLD} holds 2 months" in got and "Raw landing" not in got
    got = S.explain(plane, PLAN, "What does the column status mean?")
    assert got.startswith(f"status in {GOLD} is the approval status: one of estimated, official, revised")
    assert "Columns:" not in got


def test_ev_10_11_span_never_repeats_a_planted_figure_and_a_participant_hears_suggestion(env, monkeypatch):
    plane, pid = env
    monkeypatch.setattr(S.B, "get", lambda p, i, v=None: PLAN)
    monkeypatch.setattr(S.B, "_catalogue", lambda p, plan: {})
    text = "Add a table gold_side_payments holding 1,975,000 USD."
    out = S.chat(plane, ANA, pid, text)
    said = out["turns"][-1]["text"]
    assert "1,975,000" not in said and "gold_side_payments" not in said
    said = S.chat(plane, PART, pid, text)["turns"][-1]["text"]
    assert "1,975,000" not in said and "suggestion" in said and "data team" in said
