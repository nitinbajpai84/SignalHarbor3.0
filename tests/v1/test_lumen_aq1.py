"""Package L, cycle 1 (agent quality bar): one regression test per Lumen ticket. A stub model proves the wiring; the live check with the real
model is in docs/test-evidence/agents/cycle-1/L-aqf13/. Synthetic data only."""
import json

import pytest

from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.agents.registry import ToolRefused
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import e0a_catalogue as cat
from sh_platform.v1 import e6_trace
from sh_platform.v1 import lumen_tools as LT
from sh_platform.v1 import mem_agent as M
from sh_platform.v1 import p1_project, wh

ADMIN = Viewer(name="Nitin", roles=frozenset({"company_admin"}), account_id="acc-admin")
HOLD, CASH = "gold_report_holdings", "gold_report_cash"
ENTS = ("Fund A", "Fund B", "Fund C", "Fund D", "Fund E", "Fund F")


class Stub:
    def __init__(self, *replies):
        self.replies, self.seen = list(replies), []

    def complete(self, module_id, messages, tools=None, suppressed=None):
        self.seen.append(json.dumps(messages))
        return self.replies.pop(0) if self.replies else ModelReply("ok")


def calls(*pairs):
    return ModelReply("", [ToolCall(n, a) for n, a in pairs])


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """13 month-ends of holdings (the first holds Fund A only: a partial month), and daily cash in two views."""
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "anthropic")
    plane = PlaneStore(tmp_path / "data").create("acme")
    pid = p1_project.create_project(plane, "int-1", "Monthly report", "Nitin")["id"]
    months = ["2025-09-01"] + [f"{y}-{m:02d}-01" for y, m in [(2025, 10), (2025, 11), (2025, 12)] + [(2026, k) for k in range(1, 10)]]
    rows = [("2025-09-01", "Fund A", "official", 10)]
    for i, mo in enumerate(months[1:], 1):
        rows += [(mo, e, "official" if j % 2 else "estimated", 100 * (j + 1) + i) for j, e in enumerate(ENTS)]
    with wh.connect(plane) as con:
        con.execute(f"create table {HOLD} (report_month date, entity varchar, status varchar, net_worth_usd decimal(18,2), net_worth_sgd decimal(18,2))")
        con.executemany(f"insert into {HOLD} values (?,?,?,?,?)", [(m, e, s, v, v * 1.3) for m, e, s, v in rows])
        con.execute(f"create table {CASH} (position_date date, entity varchar, view_type varchar, cash_usd decimal(18,2))")
        con.executemany(f"insert into {CASH} values (?,?,?,?)", [(d, e, vt, v) for d in ("2026-10-07", "2026-10-08") for e, vt, v in
                                                                [("Fund A", "accounting", 880400), ("Fund A", "operational", 868000), ("Fund B", "accounting", 5000), ("Fund B", "operational", 5000)]])
    cat.register_gold(plane, pid, "report", "holdings", [{"name": "report_month", "type": "date"}])
    cat.register_gold(plane, pid, "report", "cash", [{"name": "position_date", "type": "date"}])
    return plane, pid


def tables(plane, pid):
    return {t["name"]: t for t in D.gold_tables(plane, pid)}


def rows(plane, sql):
    return D.run_sql(plane, sql)[1]


def tile(plane, pid, **r):
    t = tables(plane, pid)[r.pop("table", HOLD)]
    return t, L.build(t, {"fig": "net_worth_usd", "when": "report_month", "split": None, "kind": "line", **r})


def test_lt2_last_12_months_is_12_month_ends(env):
    plane, pid = env
    _, got = tile(plane, pid, since=12)
    assert len({r["report_month"] for r in rows(plane, got["sql"])}) == 12


def test_evt13_cash_keeps_the_two_views_apart(env):
    plane, pid = env
    t = tables(plane, pid)[CASH]
    got = L.build(t, {"fig": "cash_usd", "when": "position_date", "split": "entity", "kind": "line"})
    vals = {(r["entity"], r["view_type"]): r["cash_usd"] for r in rows(plane, got["sql"]) if r["position_date"].startswith("2026-10-08")}
    assert vals[("Fund A", "accounting")] == 880400 and vals[("Fund A", "operational")] == 868000 and 1748400 not in vals.values()
    assert got["spec"]["encoding"]["strokeDash"]["field"] == "view_type"


def test_a7_a_number_or_bars_by_name_are_the_latest_date_never_the_months_added(env):
    plane, pid = env
    _, got = tile(plane, pid, kind="bar", split="entity", when="report_month")
    assert len(rows(plane, got["sql"])) == len(ENTS) and got["title"] == "Net worth by entity at the latest date (USD)"


def test_lt1_a_split_on_the_time_axis_is_no_split_so_blue_applies(env):
    plane, pid = env
    reg = LT.lumen_registry(plane, ADMIN, pid, None)
    got = reg.call("acme", "consume", "propose_tile", {"table": HOLD, "figure": "net_worth_usd", "kind": "line", "group_by": "report_month", "color": "blue"})
    assert got["recipe"]["split"] is None and got["spec"]["mark"]["color"] == M.COLORS["blue"] and "color" not in got["spec"]["encoding"]


def test_lt5_arguments_are_read_the_way_a_model_passes_them(env):
    plane, pid = env
    did = D.create(plane, ADMIN, pid, "S")["id"]
    first = D.add_proposal(plane, ADMIN, pid, did, tile(plane, pid)[1])
    reg = LT.lumen_registry(plane, ADMIN, pid, did)
    got = reg.call("acme", "consume", "propose_tile_edit", {"tile_id": first["id"], "mark": "dots", "period": "monthly"})  # the rest left out
    assert got["spec"]["mark"]["type"] == "point" and got["recipe"]["period"] == "month"
    with pytest.raises(ToolRefused, match="sql are not taken"):
        reg.call("acme", "consume", "propose_tile_edit", {"tile_id": first["id"], "sql": "drop table x"})


def test_lt6_titles_are_plain_and_the_note_says_who_proposed(env):
    plane, pid = env
    reg = LT.lumen_registry(plane, ADMIN, pid, None)
    got = reg.call("acme", "consume", "propose_tile", {"table": HOLD, "figure": "net_worth_usd", "kind": "line"})
    assert got["title"] == "Net worth per month (USD)" and got["note"] == "Proposed by Lumen from your words."
    assert "fixed rules" in L.propose_by_rules(list(tables(plane, pid).values()), "net worth per month")["note"]


def test_lt7_a_partial_first_month_is_said(env):
    plane, pid = env
    said = L.partial_periods(plane, tables(plane, pid)[HOLD], "month")
    assert said.startswith("Take care: September 2025 holds only Fund A") and "probably incomplete" in said


def test_lq2_lq9_the_change_between_months_is_worked_out_by_the_program(env):
    plane, pid = env
    reg = LT.lumen_registry(plane, ADMIN, pid, None)
    got = reg.call("acme", "consume", "compare_periods", {"table": HOLD, "figure": "net_worth_usd", "month": "2026-09"})
    assert got["from"] == "2026-08-01" and got["to"] == "2026-09-01" and got["change"] == 6.0  # six funds, each up 1
    split = LT.lumen_registry(plane, ADMIN, pid, None)
    out = split.call("acme", "consume", "compare_periods", {"table": HOLD, "figure": "net_worth_usd", "group_by": "entity"})
    assert out["groups"] == [] and "hidden" in out  # one row per fund: nothing the model could read as the whole
    assert "Fund A 111 to 112 (up 1)" in split.lumen.notes()  # the program writes every part for the person


def test_lq2_the_why_button_on_a_one_date_tile_compares_with_the_month_before(env):
    plane, pid = env
    did = D.create(plane, ADMIN, pid, "S")["id"]
    t = D.add_proposal(plane, ADMIN, pid, did, {"title": "Net worth by entity", "sql": f"select entity, sum(net_worth_usd) as net_worth_usd from {HOLD} "
                       f"where report_month = (select max(report_month) from {HOLD}) group by entity", "spec": {"mark": "bar", "encoding": {
                           "x": {"field": "entity", "type": "nominal"}, "y": {"field": "net_worth_usd", "type": "quantitative"}}}})
    D.decide(plane, ADMIN, pid, did, t["id"], True)
    out = L.explain(plane, ADMIN, pid, did, t["id"])
    # LQ-8: a month key is the end of that month; LQ-3: the rules name where the causes are, not "the cause is not in the data"
    assert out["answer"].startswith("Net worth by entity is up 6 from the end of August 2026 to the end of September 2026") and out["caveats"][1] == L.RULES_CAUSE


def test_lq6_evt12_answers_say_figures_in_words_not_table_names(env, monkeypatch):
    plane, pid = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    did = D.create(plane, ADMIN, pid, "S")["id"]
    for words in ("show the weather", "what figures do you have?"):
        reply = L.ask(plane, ADMIN, pid, did, words)["reply"]
        assert "gold_" not in reply and "net_worth_usd" not in reply and "net worth" in reply
    assert HOLD in L.describe(plane, ADMIN, pid, "which columns does it have?")  # asked for: given


def test_lq7_a_rules_answer_has_a_trace_with_its_context(env, monkeypatch):
    plane, pid = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    did = D.create(plane, ADMIN, pid, "S")["id"]
    out = L.ask(plane, ADMIN, pid, did, "why did net worth move in September?")
    assert out["trace_id"].startswith("tr-lumen-") and out["worded_by"] == "rules" and "up 6" in out["reply"]
    steps = e6_trace.steps_for(plane, out["trace_id"])
    kinds = [s["kind"] for r in steps for s in (r.get("steps") if isinstance(r, dict) and "steps" in r else [r])]
    assert "context" in kinds and "rules" in kinds


def test_lumen_memory_03_a_model_tile_uses_the_remembered_colour(env):
    plane, pid = env
    did = D.create(plane, ADMIN, pid, "S")["id"]
    M.learn(plane, ADMIN, "lumen", "From now on, always use blue for my chart lines.", f"{pid}:{did}")
    stub = Stub(calls(("propose_tile", {"table": HOLD, "figure": "net_worth_usd", "kind": "line", "group_by": "report_month", "period": "month"})), ModelReply("done"))
    out = L.ask(plane, ADMIN, pid, did, "Show me net worth per month.", model=stub)
    t = out["proposals"][0]
    assert t["spec"]["mark"]["color"] == M.COLORS["blue"] and "I used what I remember about you: blue lines" in out["reply"] and out["worded_by"] == "model"


def test_lt3_a_new_dashboard_does_not_inherit_the_last_ones_tile(env, monkeypatch):
    plane, pid = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    a = D.create(plane, ADMIN, pid, "A")["id"]
    L.ask(plane, ADMIN, pid, a, "show net worth by entity per month")
    b = D.create(plane, ADMIN, pid, "B")["id"]
    assert L._focus_tile(plane, ADMIN, pid, b) is None and M.convo(plane, ADMIN, "lumen", L._convo(pid, b))["turns"] == []


def test_lt4_by_entity_on_a_tile_already_split_says_so(env, monkeypatch):
    plane, pid = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    did = D.create(plane, ADMIN, pid, "S")["id"]
    L.ask(plane, ADMIN, pid, did, "show net worth by entity per month")
    out = L.ask(plane, ADMIN, pid, did, "by entity")
    assert out["reply"] == "The tile is already split by entity." and out["proposals"] == []


def test_evt11_bars_by_status_then_dots_then_blue_keeps_editing_one_tile(env, monkeypatch):
    plane, pid = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    did = D.create(plane, ADMIN, pid, "S")["id"]
    first = L.ask(plane, ADMIN, pid, did, "show net worth by status as bars")["proposals"][0]
    assert first["spec"]["encoding"]["x"]["field"] == "status"
    L.ask(plane, ADMIN, pid, did, "make it dots")
    last = L.ask(plane, ADMIN, pid, did, "in blue")["proposals"][0]
    assert last["spec"]["mark"]["type"] == "point" and last["spec"]["mark"]["color"] == M.COLORS["blue"] and len(D.get(plane, ADMIN, pid, did)["tiles"]) == 1


def test_lumen_memory_06_talk_about_the_monthly_report_is_answered_not_a_tile_edit(env):
    plane, pid = env
    did = D.create(plane, ADMIN, pid, "S")["id"]
    D.add_proposal(plane, ADMIN, pid, did, tile(plane, pid)[1])
    stub = Stub(ModelReply("Happy to. Who reads it first, and in which currency?"))
    out = L.ask(plane, ADMIN, pid, did, "I want to talk about how we run the monthly report.", model=stub)
    assert out["reply"].startswith("Happy to.") and out["proposals"] == [] and "Talk, not a tile request" in stub.seen[0]


def test_lumen_memory_07_the_loop_is_told_to_answer_a_decision_from_the_talk(env):
    assert "risk of a decision" in L.LOOP_RULES and "search_documents\n  only when the person asks about documents" in L.LOOP_RULES


def test_trace_id_in_every_ask_response(env, monkeypatch):
    plane, pid = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    did = D.create(plane, ADMIN, pid, "S")["id"]
    out = L.ask(plane, ADMIN, pid, did, "show net worth per month")
    assert out["trace_id"] and e6_trace.steps_for(plane, out["trace_id"])  # the why route: live check, run-N.json "questions"


def test_lq6_the_models_words_are_put_into_plain_words(env):
    plane, pid = env
    said = L.plain_words(f"This comes from the gold table `{HOLD}` (net_worth_usd), built from bronze tables.", plane, pid, list(tables(plane, pid).values()))
    assert HOLD not in said and "net_worth_usd" not in said and "bronze" not in said and "net worth USD" in said


def test_lq9_a_sentence_denying_figures_the_program_showed_is_dropped():
    said = L._tidy("Fund A moved most. I cannot provide the figure for Fund A as there is no data for it.", "Net worth is up 1.")
    assert said == "Fund A moved most."


def test_lt1_a_split_the_person_did_not_ask_for_is_dropped_and_blue_left_as_is_is_said(env):
    plane, pid = env
    t, model_tile = tile(plane, pid, split="entity")
    out = L.with_prefs(t, model_tile, {}, {}, "Show me net worth by month")
    assert out["recipe"]["split"] is None and "color" not in out["spec"]["encoding"]
    split = tile(plane, pid, split="entity")[1]
    split["id"] = "t-abcdef"
    new, _ = L.revise(plane, list(tables(plane, pid).values()), split, "", {"mark": "point", "color": "blue"})
    assert "each series keeps its own colour" in new["left_as_is"]


def test_evt11_holdings_by_status_names_the_table_and_gets_its_figure(env, monkeypatch):
    plane, pid = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    did = D.create(plane, ADMIN, pid, "S")["id"]
    t = L.ask(plane, ADMIN, pid, did, "Show me holdings by status")["proposals"][0]
    assert t["recipe"]["fig"] == "net_worth_usd" and t["spec"]["encoding"]["x"]["field"] == "status"
    other = D.create(plane, ADMIN, pid, "T")["id"]
    assert L.ask(plane, ADMIN, pid, other, "monthly not daily")["reply"].startswith("There is no tile on this dashboard yet to change.")


def test_lt5_a_filter_passed_as_text_or_object_is_read(env):
    plane, pid = env
    reg = LT.lumen_registry(plane, ADMIN, pid, None)
    for f in ("entity=fund a", {"entity": "Fund A"}):
        got = reg.call("acme", "consume", "compare_periods", {"table": HOLD, "figure": "net_worth_usd", "filters": f})
        assert got["from"] == "2026-08-01" and "summary" in got and "111 then 112" in reg.lumen.notes()  # one row: shown to the person by the program, not to the model


def test_lumen_memory_06_the_model_does_not_promise_to_remember_the_program_says_it():
    assert L._tidy("I will remember that. From now on, blue lines.", "") == "From now on, blue lines."


def test_lumen_memory_06_a_decision_stated_with_the_model_off_makes_no_tile(env, monkeypatch):
    plane, pid = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    did = D.create(plane, ADMIN, pid, "S")["id"]
    out = L.ask(plane, ADMIN, pid, did, "We decided the family council gets the monthly report in both USD and SGD, with net worth by entity first.")
    assert out["proposals"] == [] and "model did not answer" in out["reply"]
