"""EG1: what each agent really sends to the model passes the egress gateway's own row check after two turned-down proposals and some memory.
The gateway reads a list of two or more objects as raw rows and refuses the call (the agent then falls back to rules), so every context and
every tool result must be strings. Synthetic data only."""
import json

from sh_platform.agents.protocols import ModelReply
from sh_platform.egress.rows import json_findings
from sh_platform.v1 import l2_proposals as L2
from sh_platform.v1 import mem_agent as M
from tests.v1 import test_a1 as A1
from tests.v1.test_a1 import world as a1_world  # noqa: F401
from tests.v1.test_b6 import ENG
from tests.v1.test_b6 import world as b6_world  # noqa: F401
from tests.v1.test_lumen_loop import ADMIN
from tests.v1.test_lumen_loop import env as lumen_env  # noqa: F401
from tests.v1.test_north_loop import IID, ME, sow
from tests.v1.test_north_loop import plane as north_plane  # noqa: F401
from tests.v1.test_tally_loop import world as tally_world  # noqa: F401


class Cap:
    """A model that answers `text` and keeps every message list it was shown."""
    def __init__(self, text="ok"):
        self.text, self.seen = text, []

    def complete(self, module_id, messages, tools=None, suppressed=None):
        self.seen.append(messages)
        return ModelReply(self.text)


def allowed(model, needle: str | None = None):
    """The gateway's own row check on every message the model was shown: no raw_rows (or any other structural finding)."""
    msgs = [m for ms in model.seen for m in ms if needle is None or needle in json.dumps(ms)]
    assert msgs, "the model was never called"
    for m in msgs:
        assert json_findings(m["content"]) == (None, []), m["content"][:400]


def turn_down(plane, iid, document, who="Ann"):
    for n in ("one", "two", "three"):
        p = L2.propose(plane, iid, document, None, [{"op": "set", "path": f"{document}/kpis/{n}/name", "before": "", "after": n}])
        L2.reject(plane, iid, p["id"], who, f"not {n}, we count at cost")
    got = L2.facts(plane, iid, (document,))["turned_down_by_the_person"]
    assert len(got) == 3 and all(isinstance(x, str) for x in got)  # strings, one readable line each


def test_l2_facts_are_strings_only(north_plane):  # noqa: F811
    turn_down(north_plane, IID, "sow")
    assert json_findings(json.dumps(L2.facts(north_plane, IID, ("sow",)))) == (None, [])


def test_north(north_plane):  # noqa: F811
    from sh_platform.v1 import i6_chat as C
    turn_down(north_plane, IID, "sow")
    M.remember(north_plane, ME, "north", "fact", "Reports to the family council")
    m = Cap(json.dumps({"reply": "Done.", "sow_patch": {}, "covered": [], "ready": False}))
    thread = {"turns": [{"id": "t", "by": "person", "name": "Ann", "text": "committee returns", "at": "", "need": None, "files": []}]}
    assert C.ask(m, north_plane, IID, thread, sow("Monthly pack"), [], "committee returns", ["Ann"], [], None, ME)
    allowed(m)
    assert "turned_down_by_the_person" in json.dumps(m.seen)  # the reasons did reach the model


def test_span_design(a1_world, monkeypatch):  # noqa: F811
    from sh_platform.plane import PlaneStore
    app, data, _ = a1_world
    turn_down(PlaneStore(data).plane_for("neera"), "a1-model", "design")
    stub = A1.Stub({"reply": "Noted.", "run": [], "data_model": None, "questions": None, "scope": None, "ready": False})
    app.state.build_model_factory = lambda plane: stub
    try:
        r = A1.client(a1_world, A1.LEELA).post("/api/v1/build/a1-model/blueprint/chat", json={"text": "Draft the blueprint"})
        assert r.status_code == 200, r.text
    finally:
        del app.state.build_model_factory
    chat = [ms for ms in stub.seen if "LATEST MESSAGE FROM THE ARCHITECT" in json.dumps(ms)]
    assert chat and "turned_down_by_the_person" in json.dumps(chat)
    for ms in chat:
        for m in ms:
            assert json_findings(m["content"]) == (None, []), m["content"][:400]


def test_span_build(b6_world, monkeypatch):  # noqa: F811
    from sh_platform.v1 import b6_span as S
    from sh_platform.v1 import mem_wire as W
    plane, pid = b6_world
    monkeypatch.setenv("SH_MODEL_PROVIDER", "stub")
    M.remember(plane, ENG, "span", "fact", "Prefers short answers")
    m = Cap(json.dumps({"gold": []}))
    S.propose_plan(plane, ENG, pid)
    filled = {"valuation_observations": ["valuation_date", "value_amount"], "positions": ["quantity"]}
    schema = {t: {c: "varchar" for c in cols} for t, cols in filled.items()}
    S._ask_model(plane, m, "p", "add a table", filled, schema, viewer=ENG, pid=pid, wire=W.Wire(plane, "span", ENG, "add a table", {"project": pid}, None, pid))
    allowed(m)


def test_lumen(lumen_env, monkeypatch):  # noqa: F811
    from sh_platform.v1 import cx_dash as D
    from sh_platform.v1 import cx_lumen as L
    plane, pid = lumen_env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "stub")
    M.remember(plane, ADMIN, "lumen", "fact", "Net worth is reviewed by the family council")
    m = Cap()
    L.ask(plane, ADMIN, pid, D.create(plane, ADMIN, pid, "Board")["id"], "net worth per month", model=m)
    allowed(m)


def test_tally(tally_world, monkeypatch):  # noqa: F811
    import sh_platform.build.agents.runtime as rt
    from types import SimpleNamespace
    from sh_platform.v1 import e4_cases, n1_tally as T
    plane, viewer = tally_world["plane"], tally_world["V"]["Mei Chen"]
    cid = next(c["id"] for c in e4_cases.listing(plane, tally_world["V"]["Grace Ong"]) if c["title"].startswith("Cash differs"))
    M.remember(plane, viewer, "tally", "fact", "Wires from Entity B are timing differences")
    b = T.build(plane, T._exc(plane, cid))
    b["case_id"] = cid
    m = Cap('{"summary": "{entity} differs."}')
    monkeypatch.setattr(rt, "runtime_for_plane", lambda p: SimpleNamespace(model=m))
    T._model_text(plane, b, "explain", "", viewer)
    allowed(m)


# ---- EG2: every registered tool of every agent, on planes seeded with two or more of each item ---------------------------------------

def every_tool_passes(reg, company, module, args, may_refuse=()):
    """Call each registered tool the way the loop does (loop._run_tool, so the bytes are the ones the model sees) and run the gateway's
    row check on the result. Read tools must answer; `may_refuse` names the ones with nothing seeded to find (their refusal is checked too)."""
    from sh_platform.agents.loop import AgentResult, _run_tool
    from sh_platform.agents.protocols import ToolCall
    names = [t["name"] for t in reg.tools_for(company, module)]
    assert set(names) <= set(args), set(names) - set(args)  # a new tool must be added here
    res = AgentResult("", "")
    for n in names:
        out = _run_tool(reg, company, module, ToolCall(n, args[n]), res)
        assert json_findings(out) == (None, []), (n, out[:400])
        assert n not in res.refusals or n in may_refuse or reg.is_proposal(module, n), (n, out[:300])
    return res


SHARED = {"search_documents": {"query": "policy", "max": 4}, "recall_memory": {"topic": "net worth"}, "get_definition": {"term": "net worth"},
          "explain_figure_source": {"kind": "metric", "item_id": "m-1"}, "list_tables": {"layer": "all", "starts_with": ""}, "describe_layers": {"project": ""}}


def test_every_lumen_and_shared_tool_passes_with_two_projects_and_two_tables(lumen_env):  # noqa: F811
    from sh_platform.v1 import cx_dash as D
    from sh_platform.v1 import e0a_catalogue as cat
    from sh_platform.v1 import lumen_tools as LT
    from sh_platform.v1 import p1_project, wh
    from tests.v1.test_lumen_loop import GOLD, NEW, QUERY
    plane, pid = lumen_env
    p1_project.create_project(plane, "int-2", "Second report", "Nitin")
    cat.register_gold(plane, pid, "monthly_report", "flows", [{"name": "month", "type": "date"}, {"name": "amount", "type": "decimal"}])
    with wh.connect(plane) as con:
        con.execute("create table gold_monthly_report_flows (month date, entity varchar, amount decimal(18,2))")
    did = D.create(plane, ADMIN, pid, "Board")["id"]
    reg = LT.lumen_registry(plane, ADMIN, pid, did)
    assert len(reg.call("acme", LT.MODULE, "whoami_and_access", {})["projects"]) >= 2
    assert len(reg.call("acme", LT.MODULE, "list_gold_tables", {})["tables"]) >= 2
    by_entity = {**QUERY, "group_by": "entity"}  # two groups of three rows: both hidden, and they must not come back as two objects
    every_tool_passes(reg, "acme", LT.MODULE, {**SHARED, "describe_table": {"table": GOLD}, "whoami_and_access": {}, "list_gold_tables": {},
                      "query_figure": by_entity, "get_focus_tile": {}, "propose_tile": NEW,
                      "compare_periods": {"table": by_entity["table"], "figure": by_entity["figure"], "group_by": "entity"},
                      "propose_tile_edit": {"tile_id": "t-000000", "mark": "bar", "color": "", "period": "", "since": 0, "split": "", "currency": ""},
                      "why_moved": {"start": "2026-08-31", "end": "2026-09-30", "currency": "USD", "book": ""},  # LQ-3: on a dashboard registry
                      },
                      may_refuse=("explain_figure_source", "why_moved"))
    for q in (QUERY, {**QUERY, "period": "month"}):
        assert json_findings(json.dumps(reg.call("acme", LT.MODULE, "query_figure", q))) == (None, [])


def test_every_span_tool_passes_with_two_plan_tables_and_two_runs(b6_world):  # noqa: F811
    from sh_platform.v1 import b6_run as R
    from sh_platform.v1 import b6_span as S
    from sh_platform.v1 import span_tools as ST
    plane, pid = b6_world
    S.propose_plan(plane, ENG, pid)
    R.run(plane, pid, "sandbox")
    R.run(plane, pid, "sandbox")
    reg = ST.span_registry(plane, ENG, pid, module_id="m3_connect")
    assert len(reg.call(plane.company_id, "m3_connect", "get_plan", {})["tables"]) >= 2
    runs = reg.call(plane.company_id, "m3_connect", "get_run_log", {"limit": 5})["runs"]
    assert len(runs) >= 2 and all(isinstance(r, str) for r in runs)
    every_tool_passes(reg, plane.company_id, "m3_connect", {
        **SHARED, "describe_table": {"table": "valuation_observations"}, "whoami_and_access": {}, "get_plan": {}, "get_run_log": {"limit": 5},
        "profile_table": {"table": "valuation_observations"}, "get_lineage": {"table": "valuation_observations"}, "dry_run_sql": {"sql": "select currency, count(*) as n from valuation_observations group by currency"},
        "propose_plan_change": {"name": "gold_x", "purpose": "p", "sql": "create table gold_x as select 1 as a", "depends_on": []},
        "propose_model_change": {"table": "valuation_observations", "purpose": "keep the manager's statement reference", "looked_for": "a statement reference on valuations",
                                 "columns": [{"name": "statement_ref", "type": "varchar"}]}},
        may_refuse=("explain_figure_source",))


def test_every_north_tool_passes_with_two_intents_steps_and_sources(north_plane):  # noqa: F811
    from tests.v1.test_north_loop import registry
    reg = registry(north_plane)
    assert len(reg.call("co", "m1_intent", "get_process_map", {"intent_id": ""})["steps"]) >= 2
    idp = {"intent_id": ""}
    args = {**SHARED, "describe_table": {"table": "x"}, "whoami_and_access": {}, "list_intents": {}, "get_intent": idp, "get_process_map": idp,
            "list_sources": idp, "propose_intent_section": {"section": "kpi", "content": {"name": "Return"}},
            "propose_process_step": {"name": "Send", "who": "Ann", "does": "", "system": ""},
            "read_document": {"file": "note.md", "from_line": 1, "to_line": 3}}
    every_tool_passes(reg, "co", "m1_intent", args, may_refuse=("explain_figure_source", "describe_table"))


def test_every_tally_tool_passes(tally_world):  # noqa: F811
    from tests.v1.test_tally_loop import SIDES
    from tests.v1.test_tally_loop import registry as tally_registry
    from sh_platform.v1 import tally_tools as TT
    reg = tally_registry(tally_world)
    every_tool_passes(reg, tally_world["plane"].company_id, TT.MODULE, {
        **SHARED, "describe_table": {"table": "x"}, "whoami_and_access": {}, "get_recon_run": {}, "get_both_sides": SIDES,
        "find_matching_items": {"kind": "all"}, "get_valuation_chain": {"fund": "Fund A", "as_of": "2026-10-08"}, "get_limit_inputs": {},
        "get_trade_rows": {}, "get_statement_chain": {}, "get_call_notice": {}, "get_case_history": {},
        "propose_explanation": {"cause": "timing", "item_ref": "", "note": ""}, "propose_next_step": {"who": "Operations", "action": "wait_for_file", "note": ""}},
        may_refuse=("explain_figure_source", "describe_table", "get_valuation_chain"))


def test_plain_flattens_a_definition_with_two_variants():
    from sh_platform.v1 import agent_tools as AT
    out = AT._plain({"found": [{"concept": "Net worth", "variants": [{"team": "a", "unit": "USD"}, {"team": "b", "unit": "SGD"}]},
                               {"concept": "NAV", "variants": [{"team": "c"}, {"team": "d"}]}]})
    assert all(isinstance(x, str) for x in out["found"]) and json_findings(json.dumps(out)) == (None, [])
