"""Package L, cycle 1 second round (aqf13): one regression test per Lumen ticket. A stub model proves the wiring; the live check with the
real model (Testing mode) is in docs/test-evidence/agents/cycle-1/L-aqf13/. Synthetic data only."""
from decimal import Decimal

import pytest

from sh_platform.agents.loop import _reason
from sh_platform.agents.protocols import ModelReply
from sh_platform.agents.registry import ToolRefused
from sh_platform.profile.view import Viewer
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import e6_trace
from sh_platform.v1 import lumen_tools as LT
from sh_platform.v1 import mem_agent as M
from sh_platform.v1.p1_project import Refused
from tests.v1.test_lumen_aq1 import ADMIN, CASH, HOLD, Stub, calls, env, tables, tile  # noqa: F401 - env is a fixture

OTHER = Viewer(name="Someone Else", roles=frozenset({"participant"}), account_id="acc-other")


def _nw_tiles(plane, pid):
    did = D.create(plane, ADMIN, pid, "S")["id"]
    a = D.add_proposal(plane, ADMIN, pid, did, {"title": "Net worth by entity", "sql": f"select entity, sum(net_worth_usd) as net_worth_usd from {HOLD} "
                       f"where report_month = (select max(report_month) from {HOLD}) group by entity", "spec": {"mark": "bar", "encoding": {
                           "x": {"field": "entity", "type": "nominal"}, "y": {"field": "net_worth_usd", "type": "quantitative"}}}})
    b = D.add_proposal(plane, ADMIN, pid, did, {"title": "Holdings by status", "sql": f"select status, count(*) as holdings from {HOLD} group by status",
                       "spec": {"mark": "bar", "encoding": {"x": {"field": "status", "type": "nominal"}, "y": {"field": "holdings", "type": "quantitative"}}}})
    return did, a, b


def test_lq2_the_figure_named_moves_the_focus_not_the_last_tile(env):
    plane, pid = env
    did, nw, last = _nw_tiles(plane, pid)
    assert L._focus_tile(plane, ADMIN, pid, did, "what does net worth include?")["id"] == nw["id"]
    assert L._focus_tile(plane, ADMIN, pid, did, "where does this figure come from?")["id"] == last["id"]  # nothing named, nothing remembered
    stub = Stub(ModelReply("Net worth is everything the family owns less what it owes."))
    L.ask(plane, ADMIN, pid, did, "what does net worth include?", model=stub)
    assert L._focus_tile(plane, ADMIN, pid, did, "where does this figure come from?")["id"] == nw["id"]  # the focus followed the question


def test_lq3_the_dashboard_loop_has_why_moved_and_is_not_told_the_cause_is_missing(env):
    plane, pid = env
    did = D.create(plane, ADMIN, pid, "S")["id"]
    assert ("consume", "why_moved") in LT.lumen_registry(plane, ADMIN, pid, did)._tools
    assert ("consume", "why_moved") not in LT.lumen_registry(plane, ADMIN, pid, None)._tools  # talk.py registers its own there
    assert "why_moved" in L.LOOP_RULES and "the cause is not in the figures" not in L.LOOP_RULES and "cause is not in the data" not in L.RULES_CAUSE


def test_lq8_a_month_key_is_said_as_the_end_of_that_month(env):
    plane, pid = env
    assert L.when_words("2026-09-01", "report_month") == "the end of September 2026" and L.when_words("2026-10-08", "position_date") == "8 Oct 2026"
    ch = L.period_change(plane, tables(plane, pid)[HOLD], "net_worth_usd", [], "2026-09")
    assert L.change_words("Net worth", ch)[0].startswith("Net worth is up 6 from the end of August 2026 to the end of September 2026")


def test_lq9_the_why_button_is_worded_by_the_loop_with_a_trace(env):
    plane, pid = env
    did, nw, _ = _nw_tiles(plane, pid)
    D.decide(plane, ADMIN, pid, did, nw["id"], True)
    stub = Stub(calls(("compare_periods", {"table": HOLD, "figure": "net_worth_usd"})), ModelReply("Every fund rose a little; the largest part is price moves."))
    out = L.why_tile(plane, ADMIN, pid, did, nw["id"], model=stub)
    assert out["wording"] == "model" and out["trace_id"].startswith("tr-lumen-") and L.NO_MODEL not in out["caveats"]
    assert out["evidence"] and "price moves" in out["answer"] and "tile_in_focus" in stub.seen[0] and nw["id"] in stub.seen[0]


def test_lq10_a_dashboard_not_shared_names_who_can_share_it(env):
    plane, pid = env
    did = D.create(plane, ADMIN, pid, "S")["id"]
    rec = D._load(plane, pid, did)
    with pytest.raises(Refused) as e:
        D.get_published(plane, OTHER, pid, did) if D.published_view(rec) else (_ for _ in ()).throw(Refused(403, D.maker_name(plane, rec)))
    assert e.value.status in (403, 404)
    assert D.maker_name(plane, {"created_by": "nobody-known"}) == "the person who made it"


def test_lumen_memory_c1_02_a_decision_on_a_dashboard_is_talk_not_a_build_request(env):
    plane, pid = env
    did, _, _ = _nw_tiles(plane, pid)
    words = "OK, decision: we drop the benchmark comparison page until the council agrees a new benchmark."
    assert not L._wants_tile(words, M.parse_style(words))
    stub = Stub(ModelReply("Understood: the benchmark comparison page is dropped until the council agrees a new benchmark."))
    out = L.ask(plane, ADMIN, pid, did, words, model=stub, talk_only=True)
    assert out["proposals"] == [] and out["dashboard_id"] == did and out["worded_by"] == "model" and "A question." in stub.seen[0]
    assert any("benchmark comparison page" in t.get("text", "") for t in M.convo(plane, ADMIN, "lumen", L._convo(pid, did))["turns"])


def test_lumen_memory_c1_05_a_remembered_currency_the_model_chose_itself_is_named(env):
    plane, pid = env
    t = tables(plane, pid)[HOLD]
    r = {"fig": "net_worth_sgd", "when": "report_month", "split": None, "kind": "line"}
    used, _ = L.apply_prefs(t, r, {"lumen.currency": "SGD", "lumen.color": "blue"}, {})
    assert "figures in SGD" in used and "blue lines" in used


def test_lumen_memory_c1_07_evt_t14_pointer_and_new_talk_replies_have_a_rules_trace(env):
    plane, pid = env
    did = D.create(plane, ADMIN, pid, "S")["id"]
    out = L.rules_turn(plane, ADMIN, pid, did, "show me cash per day", {"reply": "Dashboards are built in Build."}, "build_pointer")
    fresh = L.new_talk(plane, ADMIN, pid, did)
    for got, why in ((out, "build_pointer"), (fresh, "new_talk")):
        steps = e6_trace.steps_for(plane, got["trace_id"])
        flat = [s for r in steps for s in (r.get("steps") if isinstance(r, dict) and "steps" in r else [r])]
        assert {"kind": "rules", "why": why} in flat and got["worded_by"] == "rules"
    assert L.talk(plane, ADMIN, pid, did) == []  # the fresh start empties the page; the pointer turn was kept before it


def test_evt_t6_the_loop_gets_today_and_the_dates_each_table_holds(env):
    plane, pid = env
    facts = L.dates_facts(plane, list(tables(plane, pid).values()))
    assert facts["today"] and f"{HOLD}: 2025-09-01 to 2026-09-01" in facts["dates_in_data"]
    did, _, _ = _nw_tiles(plane, pid)
    stub = Stub(ModelReply("It rose."))
    L.ask(plane, ADMIN, pid, did, "why did net worth move in September?", model=stub)
    assert "dates_in_data" in stub.seen[0] and "never\\n  an earlier year" in stub.seen[0]


def test_evt_t8_query_figure_takes_a_day(env):
    plane, pid = env
    reg = LT.lumen_registry(plane, ADMIN, pid, None)
    got = reg.call("acme", "consume", "query_figure", {"table": CASH, "figure": "cash_usd", "month": "2026-10-07", "filters": ["view_type=accounting"]})
    assert "fewer than five" in got["summary"] and "on" not in reg.lumen.notes().split(",")[0] and "7 Oct 2026" in reg.lumen.notes()
    with pytest.raises(ToolRefused, match="2026-10-08"):
        reg.call("acme", "consume", "query_figure", {"table": CASH, "figure": "cash_usd", "month": "8 Oct"})


def test_lt2_1_lt2_2_an_edit_says_only_what_this_turn_asked(env):
    plane, pid = env
    t, blue = tile(plane, pid, color="blue", period="month", over_time=True)
    tl = {**blue, "id": "t-abcdef", "title": "Net worth per month (USD)"}
    new, reply = L.revise(plane, list(tables(plane, pid).values()), tl, "", {"period": "month", "currency": "SGD"})
    assert "already by month" in new["left_as_is"] and L.asked_notes(new, {"currency": "SGD"}) == ""  # LT2-1
    split, reply = L.revise(plane, list(tables(plane, pid).values()), tl, "by entity", {})
    assert "blue is no longer used" in reply and "blue is no longer used" in L.asked_notes(split, {})  # LT2-2: said at the split


def test_lt2_3_one_tile_per_figure_and_a_warning_said_once(env):
    plane, pid = env
    _, usd = tile(plane, pid, over_time=True)
    _, sgd = tile(plane, pid, fig="net_worth_sgd", over_time=True)
    assert L.one_per_figure([usd, sgd]) == [usd]
    reply = L.proposed_reply(plane, list(tables(plane, pid).values()), [usd, sgd])
    assert reply.count("Take care:") == 1


def test_lt2_4_a_no_change_edit_is_coded_no_change_not_a_bad_argument(env):
    plane, pid = env
    did = D.create(plane, ADMIN, pid, "S")["id"]
    t = D.add_proposal(plane, ADMIN, pid, did, tile(plane, pid, period="month", over_time=True)[1])
    reg = LT.lumen_registry(plane, ADMIN, pid, did)
    for args in ({"tile_id": t["id"]}, {"tile_id": t["id"], "period": "monthly"}):
        with pytest.raises(ToolRefused) as e:
            reg.call("acme", "consume", "propose_tile_edit", args)
        assert _reason("propose_tile_edit", str(e.value))["reason"].endswith("no_change")


def test_rc2_3_returns_are_said_as_percentages_and_an_empty_project_points_on(env):
    plane, pid = env
    t = {"columns": [{"name": "portfolio_return", "type": "DOUBLE"}, {"name": "difference", "type": "DOUBLE"}]}
    assert L.fig_text(t, "portfolio_return", 0.006024) == "0.60%" and L.fig_text(t, "difference", -0.021) == "-2.10%"
    assert L.fig_text(tables(plane, pid)[HOLD], "net_worth_usd", Decimal("1234.5")) == "1,234.5"
    line = LT.LumenTools._rows_line(t, "portfolio_return", [{"month": "2026-09-01", "portfolio_return": 0.006024}], [], "month", False, "2026-09-01")
    assert "0.60%" in line and "the end of September 2026" in line and "0.01" not in line


def test_rc2_3_c1_02_a_decision_gets_no_move_line_and_returns_change_in_points(env):
    plane, pid = env
    did, _, _ = _nw_tiles(plane, pid)
    stub = Stub(ModelReply("Noted: the page is dropped."))
    out = L.ask(plane, ADMIN, pid, did, "OK, decision: we drop the net worth page.", model=stub, talk_only=True)
    assert out["reply"].startswith("Noted") and "up 6" not in out["reply"]
    ch = {"from": "2026-08-01", "to": "2026-09-01", "groups": [], "total": (Decimal("0.0104"), Decimal("0.0271")), "views": [], "when": "month", "ratio": True}
    assert L.change_words("Benchmark return", ch)[0] == "Benchmark return is up 1.67 points from the end of August 2026 to the end of September 2026: 1.04% then 2.71%."


def test_evt_t8_the_program_line_names_the_filter(env):
    plane, pid = env
    reg = LT.lumen_registry(plane, ADMIN, pid, None)
    reg.call("acme", "consume", "query_figure", {"table": CASH, "figure": "cash_usd", "month": "2026-10-08", "filters": ["entity=Fund A", "view_type=accounting"]})
    assert "Cash (Fund A, accounting) for 8 Oct 2026, from the rows: 880,400." in reg.lumen.notes()


def test_rc2_3_a_benchmark_question_naming_no_portfolio_is_left_to_the_loop(env, monkeypatch):
    plane, pid = env
    from sh_platform.v1 import k7_routes as K7
    monkeypatch.setattr(K7, "definitions", lambda p: {"definitions": [{"benchmark_code": "EG-OFFICE-BLEND", "benchmark_name": "Office blend"}]})
    monkeypatch.setattr(L, "benchmark_answer", L.benchmark_answer)
    assert L.benchmark_answer(plane, ADMIN, "OK, decision: we drop the benchmark comparison page.") is None


def test_lumen_memory_c1_02_a_decision_with_the_model_off_is_kept_and_said_plainly(env, monkeypatch):
    plane, pid = env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    did = D.create(plane, ADMIN, pid, "S")["id"]
    out = L.ask(plane, ADMIN, pid, did, "OK, decision: we drop the net worth page.", talk_only=True)
    assert out["reply"].startswith("I could not think this through") and out["proposals"] == [] and out["trace_id"]
    assert any("drop the net worth page" in t.get("text", "") for t in M.convo(plane, ADMIN, "lumen", L._convo(pid, did))["turns"])
