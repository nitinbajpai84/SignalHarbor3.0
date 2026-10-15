"""Package L, wave 2: one regression test per Lumen ticket (NU-17, NU-19, NU-22, NU-27, DG-2, H1-07, SP-C1-04, LT-5, EVT-11, LQ-9).
Stub models replay the reply shapes recorded in docs/test-evidence/agents/ (new-uc, cycle-1). Synthetic data only."""
import json

import pytest

from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import e0a_catalogue as cat
from sh_platform.v1 import lumen_tools as LT
from sh_platform.v1 import mem_agent as M
from sh_platform.v1 import p1_project, wh

ADMIN = Viewer(name="Nitin", roles=frozenset({"company_admin"}), account_id="acc-admin")
STMT, LATE = "gold_mrt_statements_by_manager_month", "gold_mrt_late_days_by_manager_month"
MGRS = ("Bluewater Capital", "Cedarpoint Ventures", "Kestrel Ridge Advisors", "Meridian Index Managers", "Northgate Partners", "Saltmarsh Real Assets")
MONTHS = [f"{y}-{m:02d}-01" for y, m in [(2025, 9), (2025, 10), (2025, 11), (2025, 12)] + [(2026, k) for k in range(1, 10)]]


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
    """The new-uc A project, synthetic: six managers, 13 month-ends, statement counts and business days late."""
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    plane = PlaneStore(tmp_path / "data").create("acme")
    pid = p1_project.create_project(plane, "int-1", "Manager reporting", "Mei Chen")["id"]
    with wh.connect(plane) as con:
        con.execute(f"create table {STMT} (manager_name varchar, valuation_month date, statement_count integer, superseded_statement_count integer)")
        con.executemany(f"insert into {STMT} values (?,?,?,?)", [(g, m, 3 + j, j % 2) for i, m in enumerate(MONTHS) for j, g in enumerate(MGRS)])
        con.execute(f"create table {LATE} (manager_name varchar, valuation_month date, statement_count integer, business_days_late integer)")
        con.executemany(f"insert into {LATE} values (?,?,?,?)", [(g, m, 3 + j, (i + j) % 4) for i, m in enumerate(MONTHS) for j, g in enumerate(MGRS)])
    cat.register_gold(plane, pid, "mrt", "statements_by_manager_month", [{"name": "valuation_month", "type": "date"}])
    cat.register_gold(plane, pid, "mrt", "late_days_by_manager_month", [{"name": "valuation_month", "type": "date"}])
    did = D.create(plane, ADMIN, pid, "Scorecard")["id"]
    return plane, pid, did


def tables(plane, pid):
    return list(D.gold_tables(plane, pid))


HOLD, CASH = "gold_report_holdings", "gold_report_cash"
FUNDS = ("Fund A", "Fund B", "Fund C", "Fund D", "Fund E", "Fund F")


@pytest.fixture()
def hold(tmp_path, monkeypatch):
    """Month-end holdings in USD and SGD for six funds; daily cash in USD only (the DG-2 seed shape)."""
    wh.reset_cache()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "anthropic")
    plane = PlaneStore(tmp_path / "data").create("acme")
    pid = p1_project.create_project(plane, "int-1", "Monthly report", "Nitin")["id"]
    months = [f"2026-{m:02d}-01" for m in range(1, 10)]
    with wh.connect(plane) as con:
        con.execute(f"create table {HOLD} (report_month date, entity varchar, status varchar, net_worth_usd decimal(18,2), net_worth_sgd decimal(18,2))")
        con.executemany(f"insert into {HOLD} values (?,?,?,?,?)", [(mo, e, "official", 100 * (j + 1) + i, (100 * (j + 1) + i) * 1.3)
                                                                   for i, mo in enumerate(months) for j, e in enumerate(FUNDS)])
        con.execute(f"create table {CASH} (position_date date, entity varchar, cash_usd decimal(18,2))")
        con.executemany(f"insert into {CASH} values (?,?,?)", [("2026-10-08", "Fund A", 880400), ("2026-10-08", "Fund B", 5000)])
    cat.register_gold(plane, pid, "report", "holdings", [{"name": "report_month", "type": "date"}])
    cat.register_gold(plane, pid, "report", "cash", [{"name": "position_date", "type": "date"}])
    return plane, pid, D.create(plane, ADMIN, pid, "S")["id"]


def rows(plane, tile):
    return D.run_sql(plane, tile["sql"])[1]


def focus_on(plane, pid, did, words, monkeypatch):
    """A first tile made by the rules (the model off for that turn), the one the follow-ups are about."""
    with monkeypatch.context() as m:
        m.setenv("SH_MODEL_PROVIDER", "off")
        return L.ask(plane, ADMIN, pid, did, words)["proposals"][0]


# ---- NU-17 / NU-27: a filter and a split per manager are kept --------------------------------------------------------------------

def test_nu17_rules_keep_only_the_two_managers_split_by_manager_along_the_months(env):
    plane, pid, did = env
    out = L.ask(plane, ADMIN, pid, did, "Not that one. As bars of business days late per month, one bar colour per manager, only Cedarpoint "
                                        "Ventures and Kestrel Ridge Advisors.")
    t = out["proposals"][0]
    got = rows(plane, t)
    assert t["recipe"]["split"] == "manager_name" and t["recipe"]["over_time"] and t["spec"]["encoding"]["x"]["type"] == "temporal"
    assert {r["manager_name"] for r in got} == {"Cedarpoint Ventures", "Kestrel Ridge Advisors"} and len(got) == 2 * len(MONTHS)
    assert "Cedarpoint Ventures and Kestrel Ridge Advisors only" in t["title"]


def test_nu17_a_follow_up_only_x_and_y_edits_the_tile_in_focus(env):
    plane, pid, did = env
    first = L.ask(plane, ADMIN, pid, did, "statement count by manager name per month as bars")["proposals"][0]
    out = L.ask(plane, ADMIN, pid, did, "As bars, only Cedarpoint and Kestrel.")
    new = out["proposals"][0]
    assert out["edited"] and [x["id"] for x in D.get(plane, ADMIN, pid, did)["tiles"]] == [new["id"]] and first["id"] != new["id"]  # a new version
    assert {r["manager_name"] for r in rows(plane, new)} == {"Cedarpoint Ventures", "Kestrel Ridge Advisors"}
    back = L.ask(plane, ADMIN, pid, did, "show them all again")["proposals"][0]
    assert len({r["manager_name"] for r in rows(plane, back)}) == len(MGRS)


def test_nu17_replay_the_model_drops_the_filter_and_the_program_keeps_it(env, monkeypatch):
    """Recorded shape (tr-29801e034e0940af, tr-3e2dcc20c9324b24): the model edits the mark and leaves 'only Cedarpoint and Kestrel' out."""
    plane, pid, did = env
    first = focus_on(plane, pid, did, "statement count by manager name per month as a line", monkeypatch)
    monkeypatch.setenv("SH_MODEL_PROVIDER", "anthropic")
    stub = Stub(calls(("get_focus_tile", {})), calls(("propose_tile_edit", {"tile_id": first["id"], "mark": "bars"})), ModelReply("Done."))
    out = L.ask(plane, ADMIN, pid, did, "As bars, only Cedarpoint and Kestrel.", model=stub)
    new = out["proposals"][0]
    assert out["worded_by"] == "model" and new["spec"]["mark"]["type"] == "bar"
    assert {r["manager_name"] for r in rows(plane, new)} == {"Cedarpoint Ventures", "Kestrel Ridge Advisors"}
    assert "filters for 'only X and Y'" in stub.seen[0]  # the loop is told which argument carries it


def test_nu17_the_model_may_name_a_manager_by_its_first_word(env):
    plane, pid, did = env
    reg = LT.lumen_registry(plane, ADMIN, pid, did)
    t = reg.call("acme", "consume", "propose_tile", {"table": STMT, "figure": "statement_count", "kind": "bar", "group_by": "manager_name",
                                                     "period": "month", "filters": ["manager_name=Cedarpoint", "manager_name=kestrel ridge"]})
    assert {r["manager_name"] for r in rows(plane, t)} == {"Cedarpoint Ventures", "Kestrel Ridge Advisors"}
    with pytest.raises(Exception, match="not in the table; use one of: Bluewater Capital"):
        reg.call("acme", "consume", "propose_tile", {"table": STMT, "figure": "statement_count", "kind": "bar", "filters": ["manager_name=Acme"]})


def test_nu27_names_with_underscores_work_with_a_tile_in_focus(env):
    plane, pid, did = env
    L.ask(plane, ADMIN, pid, did, "Show the scorecard per manager and month, statements received, as a table.")
    for words in ("statement_count by manager_name as bars", "Yes, show it: statement_count by manager_name per month as stacked bars."):
        out = L.ask(plane, ADMIN, pid, did, words)
        assert out["proposals"] and out["proposals"][0]["recipe"]["split"] == "manager_name", (words, out["reply"])
    assert out["proposals"][0]["recipe"]["over_time"]  # "per month" bars run along the months, not the latest date


def test_nu27_replay_the_model_asks_which_period_and_the_tile_is_still_made(env, monkeypatch):
    """Recorded shape (tr-lumen-80f57ce4-d4f2d16f, -1f5db7d6): 'What period do you want to see: month, quarter, or year?' twice."""
    plane, pid, did = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "anthropic")
    q = ModelReply("I can show the superseded statement count by manager name. What period do you want to see: month, quarter, or year?")
    out = L.ask(plane, ADMIN, pid, did, "superseded statement count by manager name as a table", model=Stub(q, q, q))
    assert out["proposals"] and out["proposals"][0]["recipe"]["fig"] == "superseded_statement_count" and "What period" not in out["reply"]


def test_nu27_a_range_of_13_months_keeps_13_months_whatever_the_model_passed(env, monkeypatch):
    """Recorded shape (tr-lumen-80f57ce4-a4c48bcc): 'September 2025 to September 2026' became since 12, the 13th month cut."""
    plane, pid, did = env
    first = focus_on(plane, pid, did, "statement count by manager name per month as bars", monkeypatch)
    assert L.range_since("September 2025 to September 2026, by month") == {"since": 13}
    monkeypatch.setenv("SH_MODEL_PROVIDER", "anthropic")
    stub = Stub(calls(("propose_tile_edit", {"tile_id": first["id"], "since": 12})), ModelReply("Done."))
    out = L.ask(plane, ADMIN, pid, did, "September 2025 to September 2026, by month", model=stub)
    new = out["proposals"][0]
    assert new["recipe"]["since"] == 13 and len({r["valuation_month"] for r in rows(plane, new)}) == 13


# ---- NU-19: one ask, several figures ---------------------------------------------------------------------------------------------

def test_nu19_a_table_ask_naming_two_figures_shows_both(env):
    plane, pid, did = env
    out = L.ask(plane, ADMIN, pid, did, "Show the manager reporting scorecard: per manager and month, statement count and business days late, as a table.")
    t = out["proposals"][0]
    cols = list(rows(plane, t)[0])
    assert "statement_count" in cols and "business_days_late" in cols and "manager_name" in cols
    assert t["title"].startswith("Statement count and business days late")


def test_nu19_charts_for_figures_in_two_tables_are_two_tiles(env):
    plane, pid, did = env
    out = L.ask(plane, ADMIN, pid, did, "show business days late and superseded statement count per month")
    assert sorted(p["recipe"]["fig"] for p in out["proposals"]) == ["business_days_late", "superseded_statement_count"]
    assert out["reply"].startswith("I have proposed 2 tiles")


def test_nu19_replay_the_model_proposes_two_tiles_and_both_are_kept(env, monkeypatch):
    plane, pid, did = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "anthropic")
    stub = Stub(calls(("propose_tile", {"table": LATE, "figure": "business_days_late", "kind": "table"}),
                      ("propose_tile", {"table": STMT, "figure": "superseded_statement_count", "kind": "table"})), ModelReply("Two tiles."))
    out = L.ask(plane, ADMIN, pid, did, "A table of business days late, and one of revised statements, per manager and month.", model=stub)
    assert len(out["proposals"]) == 2 and out["worded_by"] == "model" and "once per figure named" in stub.seen[0]


# ---- NU-22 and H1-07: the talk on the page, a fresh talk --------------------------------------------------------------------------

def test_nu22_the_talk_comes_back_in_full_for_its_person_only(env):
    plane, pid, did = env
    long_ask = ("statement count by manager name per month as bars " + "please " * 60).strip()
    L.ask(plane, ADMIN, pid, did, long_ask)
    got = L.talk(plane, ADMIN, pid, did)
    assert got[0] == {"by": "person", "text": long_ask} and got[1]["by"] == "lumen" and got[1]["text"].startswith("I have proposed")
    other = Viewer(name="Raj", roles=frozenset({"company_admin"}), account_id="acc-raj")
    assert L.talk(plane, other, pid, did) == []


def test_h1_07_a_forgotten_colour_does_not_shape_the_next_tile(hold):
    """Recorded (LUM-07 after MEM-02): the memory item is forgotten, the thread still says 'I prefer blue lines', the model passes blue."""
    plane, pid, did = hold
    M.learn(plane, ADMIN, "lumen", "I prefer blue lines.", f"{pid}:{did}")
    M.note(plane, ADMIN, "lumen", f"{pid}:{did}", "person", "I prefer blue lines.")
    for item in M.mine(plane, ADMIN):
        M.forget(plane, ADMIN, item["id"])
    assert M.preferences(plane, ADMIN).get("lumen.color") is None
    stub = Stub(calls(("propose_tile", {"table": HOLD, "figure": "net_worth_usd", "kind": "line", "period": "month", "color": "blue"})), ModelReply("done"))
    t = L.ask(plane, ADMIN, pid, did, "total net worth by month", model=stub)["proposals"][0]
    assert "color" not in t["spec"]["mark"] and "color" not in t["recipe"]
    red = L.ask(plane, ADMIN, pid, did, "line in red", model=Stub(calls(("propose_tile_edit", {"tile_id": t["id"], "color": "red"})), ModelReply("ok")))
    assert red["proposals"][0]["spec"]["mark"]["color"] == M.COLORS["red"]
    L.new_talk(plane, ADMIN, pid, did)
    assert M.convo(plane, ADMIN, "lumen", L._convo(pid, did))["turns"] == [] and L.talk(plane, ADMIN, pid, did) == []


# ---- DG-2: SGD honoured -----------------------------------------------------------------------------------------------------------

def test_dg2_the_remembered_sgd_and_in_sgd_reach_the_models_tile(hold):
    plane, pid, did = hold
    stub = Stub(calls(("propose_tile", {"table": HOLD, "figure": "net_worth_usd", "kind": "line", "group_by": "entity", "period": "month"})), ModelReply("done"))
    t = L.ask(plane, ADMIN, pid, did, "Show net worth by entity per month in SGD.", model=stub)["proposals"][0]
    assert t["recipe"]["fig"] == "net_worth_sgd" and t["title"].endswith("(SGD)")
    M.learn(plane, ADMIN, "lumen", "From now on show SGD first.", f"{pid}:{did}")
    stub = Stub(calls(("propose_tile", {"table": HOLD, "figure": "net_worth_usd", "kind": "line", "period": "month"})), ModelReply("done"))
    t = L.ask(plane, ADMIN, pid, did, "Show me net worth per month.", model=stub)["proposals"][0]
    assert t["recipe"]["fig"] == "net_worth_sgd"


def test_dg2_cash_with_no_sgd_figure_says_so(hold, monkeypatch):
    plane, pid, did = hold
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    out = L.ask(plane, ADMIN, pid, did, "Now show cash by entity as bars in SGD")
    assert out["proposals"][0]["recipe"]["fig"] == "cash_usd" and "Cash is kept in USD only in this project" in out["reply"]


# ---- SP-C1-04, LQ-9: figures the model could not see are written by the program ---------------------------------------------------

def test_sp_c1_04_under_five_rows_in_all_is_written_for_the_person(hold):
    plane, pid, did = hold
    stub = Stub(calls(("query_figure", {"table": CASH, "figure": "cash_usd", "filters": ["entity=Fund A"]})),
                ModelReply("I cannot show that figure because there are fewer than five rows. The administrator would know why it moved."))
    out = L.ask(plane, ADMIN, pid, did, "What is the cash of Fund A?", model=stub)
    assert out["reply"].startswith("Cash (Fund A) for 8 Oct 2026, from the rows: 880,400.")  # EVT-T8: the filter is named and "fewer than five" not in out["reply"]


def test_lq9_replay_two_months_fetched_and_the_change_refused_is_stated_by_the_program(hold):
    """Recorded shape (tr-6cbf4828740c4e6b): query_figure for August and September, then 'not a figure I can state'."""
    plane, pid, did = hold
    stub = Stub(calls(("query_figure", {"table": HOLD, "figure": "net_worth_usd", "group_by": "entity", "month": "2026-08"}),
                      ("query_figure", {"table": HOLD, "figure": "net_worth_usd", "group_by": "entity", "month": "2026-09"})),
                ModelReply("It returns a September 2026 value with the August 2026 value just before it. I have not calculated the change: the "
                           "difference between those two months is not a figure I can state. The cause is not in the figures; the administrator would know."))
    out = L.ask(plane, ADMIN, pid, did, "Why did net worth move in September?", model=stub)
    assert "is up 6 from the end of August 2026 to the end of September 2026"  # LQ-8 in out["reply"] and "Fund A 107 to 108 (up 1)" in out["reply"]
    assert "not a figure I can state" not in out["reply"] and "administrator would know" in out["reply"]


# ---- LT-5 / EVT-11: follow-up edits made by the loop, replayed from the recorded failures ---------------------------------------------

def test_lt5_replay_words_first_then_the_edit_after_the_nudge(hold, monkeypatch):
    """Recorded (run 3, 'make it dots'): the model answered in words with no tool; one nudge, then propose_tile_edit."""
    plane, pid, did = hold
    first = focus_on(plane, pid, did, "show net worth per month", monkeypatch)
    stub = Stub(ModelReply("Sure, dots would show each month clearly."), calls(("propose_tile_edit", {"tile_id": first["id"], "mark": "dots"})), ModelReply("Done."))
    out = L.ask(plane, ADMIN, pid, did, "make it dots", model=stub)
    assert out["worded_by"] == "model" and out["edited"] and out["proposals"][0]["spec"]["mark"]["type"] == "point"


def test_lt5_replay_a_whole_new_tile_on_an_edit_turn_is_the_new_version(hold, monkeypatch):
    """Recorded (run 2, 'monthly not daily'): the loop proposed a brand-new tile, which was thrown away and the rules edited."""
    plane, pid, did = hold
    first = focus_on(plane, pid, did, "show net worth by entity per day", monkeypatch)
    stub = Stub(calls(("propose_tile", {"table": HOLD, "figure": "net_worth_usd", "kind": "line", "group_by": "entity", "period": "month"})), ModelReply("Done."))
    out = L.ask(plane, ADMIN, pid, did, "monthly not daily", model=stub)
    new = out["proposals"][0]
    assert out["worded_by"] == "model" and out["edited"] and new["recipe"]["period"] == "month"
    assert [x["id"] for x in D.get(plane, ADMIN, pid, did)["tiles"]] == [new["id"]] and first["id"] != new["id"]  # the new version, not a second tile


def test_evt11_replay_refused_tile_then_the_chain_of_edits_by_the_loop(hold):
    """Recorded (L-aqf13 run 2): 'Show me holdings by status' - propose_tile refused on period; then 'make it dots' and 'in blue' by the loop."""
    plane, pid, did = hold
    stub = Stub(calls(("propose_tile", {"table": HOLD, "figure": "net_worth_usd", "kind": "bars", "group_by": "status", "period": "latest"})),
                ModelReply("I could not make that tile."))
    t = L.ask(plane, ADMIN, pid, did, "Show me holdings by status", model=stub)["proposals"][0]
    assert t["spec"]["encoding"]["x"]["field"] == "status"  # the rules made it after the refused call; the chain goes on from it
    dots = L.ask(plane, ADMIN, pid, did, "make it dots", model=Stub(calls(("propose_tile_edit", {"tile_id": t["id"], "mark": "dots"})), ModelReply("ok")))
    assert dots["worded_by"] == "model"
    tid = dots["proposals"][0]["id"]
    blue = L.ask(plane, ADMIN, pid, did, "in blue", model=Stub(calls(("get_focus_tile", {})), calls(("propose_tile_edit", {"tile_id": tid, "color": "blue"})), ModelReply("ok")))
    last = blue["proposals"][0]
    assert blue["worded_by"] == "model" and last["spec"]["mark"] == {"type": "point", "filled": True, "color": M.COLORS["blue"]}
    assert len(D.get(plane, ADMIN, pid, did)["tiles"]) == 1


def test_nu17_a_first_word_names_values_in_one_column_only(hold):
    """Seen in the offline eval: 'only Entity B and Evergreen' also caught holdings named Evergreen Growth I (a second column)."""
    plane, pid, _ = hold
    with wh.connect(plane) as con:
        con.execute("create table gold_x_pos (report_month date, entity varchar, holding varchar, value_usd decimal(18,2))")
        con.executemany("insert into gold_x_pos values (?,?,?,?)", [("2026-09-01", e, h, 1) for e in ("Entity B", "Evergreen Family Trust", "Evergreen Holdings")
                                                                   for h in ("Evergreen Growth I", "Harbour Bond")])
    t = {"name": "gold_x_pos", "columns": [{"name": n, "type": ty} for n, ty in (("report_month", "DATE"), ("entity", "VARCHAR"), ("holding", "VARCHAR"),
                                                                                ("value_usd", "DECIMAL(18,2)"))]}
    assert L.filters_in(plane, t, "only Entity B and Evergreen") == ["entity=Entity B", "entity=Evergreen Family Trust", "entity=Evergreen Holdings"]
    assert L.filters_in(plane, t, "only Entity B and Evergreen Family Trust") == ["entity=Entity B", "entity=Evergreen Family Trust"]
    assert L.filters_in(plane, t, "only Harbour") == ["holding=Harbour Bond"] and L.filters_in(plane, t, "by entity") is None
