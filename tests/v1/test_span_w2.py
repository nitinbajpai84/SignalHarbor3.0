"""Wave 2 (offline) fixes for Span and the talk box, package SP of docs/test/AGENT-TRIAGE.md. Stub models replay the recorded replies and
failure shapes of docs/test-evidence/agents/new-uc (RA, B transcripts) and the 10 Oct demo guide; the live 3-of-3 runs are owed."""
import json
import uuid

import pytest

from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.agents.registry import ToolRefused
from sh_platform.profile.view import Viewer
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import b6_span as S
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import p1_project as P
from sh_platform.v1 import span_tools as ST
from sh_platform.v1 import talk as T
from sh_platform.v1 import wh
from sh_platform.v1.skill_loader import LIMIT, load_skill, skill_files
from tests.v1.test_talk_to_all import ENG, SOFIA, Script, dash, world  # noqa: F401 - the Evergreen plane with a proposed plan

PFX = "gold_monthly_investment_report_"
# NU-14: ch-eb7c061c as recorded in B-transcript.json (QUALIFY before GROUP BY), given a name approval can register
NU14_SQL = ("create table {n} as SELECT i.manager_name, p.portfolio_code, le.entity_name, SUM(lv.value_amount) AS total_exposure, "
            "SUM(SUM(lv.value_amount)) OVER (PARTITION BY p.portfolio_code, le.entity_name) AS portfolio_entity_total_exposure "
            "FROM valuation_observations lv JOIN instruments i ON lv.instrument_id = i.id JOIN portfolios p ON lv.portfolio_id = p.id "
            "JOIN legal_entities le ON p.legal_entity_id = le.id WHERE lv.valuation_date <= '2026-09-30' QUALIFY ROW_NUMBER() OVER "
            "(PARTITION BY lv.instrument_id, lv.portfolio_id ORDER BY lv.valuation_date DESC, lv.received_at DESC) = 1 "
            "GROUP BY i.manager_name, p.portfolio_code, le.entity_name")
BY_MANAGER = (f"create table {PFX}statements_monthly_by_manager as select date_trunc('month', v.valuation_date) as month, i.manager_name, "
              "count(*) as statements_received from valuation_observations as v join instruments as i on v.instrument_id = i.id "
              "where i.manager_name is not null group by 1, 2")


def propose(name, sql, deps=("valuation_observations", "instruments"), replaces=""):
    return ToolCall("propose_plan_change", {"name": name, "purpose": "Statements per manager and month.", "sql": sql, "depends_on": list(deps),
                                            "replaces": replaces})


@pytest.fixture(autouse=True)
def model_on(world, monkeypatch):  # noqa: F811
    monkeypatch.setenv("SH_MODEL_PROVIDER", "stub")


def tools(plane, pid, text="add the statements per manager and month"):
    return ST.SpanTools(plane, ENG, pid, request=text)


# ---- TAQ-SP1 ---------------------------------------------------------------------------------------------------------------------

def test_taq_sp1_span_skill_is_whole_under_the_cap_and_teaches_the_new_rules():
    full = "\n\n".join(p.read_text(encoding="utf-8").strip() for p in skill_files("span").values())
    assert len(full) < LIMIT and load_skill("investigation") == full  # nothing cut (test_e4b loads it by its old name)
    low = full.lower()
    for s in ("never write a digit", "manager-reported valuation difference", "instruments.manager_name", "replaces", "revision"):
        assert s in low


# ---- NU-24, NU-14, NU-11/13 (catalogue columns), NU-13, NU-09 --------------------------------------------------------------------

def test_nu24_a_gold_name_without_the_project_prefix_is_refused_and_never_filed(world):  # noqa: F811
    plane, pid = world
    with pytest.raises(ToolRefused, match=PFX):
        tools(plane, pid).propose_plan_change(**propose("gold_manager_reporting_scorecard", BY_MANAGER.replace(f"{PFX}statements_monthly_by_manager",
                                                                                                            "gold_manager_reporting_scorecard")).arguments)
    notes = []
    model_table = {"name": "gold_manager_reporting_scorecard", "layer": "gold", "columns": [], "depends_on": ["valuation_observations"],
                   "sql": "create table gold_manager_reporting_scorecard as select currency, count(*) as n from valuation_observations group by currency"}
    assert S.keep_valid(plane, B.get(plane, pid), [model_table], notes) == [] and PFX in notes[0]  # rules, model and chat share the rule


def test_nu11_a_silver_table_the_plan_fills_keeps_every_catalogue_column(world):  # noqa: F811
    plane, pid = world  # the plan maps only valuation_date, value_amount, currency into valuation_observations
    t = tools(plane, pid)
    assert {"instrument_id", "received_at", "supersedes_valuation_id"} <= set(t._tables()["valuation_observations"])
    got = t.propose_plan_change(**propose(f"{PFX}statements_monthly_by_manager", BY_MANAGER).arguments)  # RA: 'Unknown column: instrument_id'
    assert got["table"]["name"] == f"{PFX}statements_monthly_by_manager"


def test_nu14_the_replayed_qualify_before_group_by_sql_is_refused_before_approval(world):  # noqa: F811
    plane, pid = world
    sql = NU14_SQL.format(n=f"{PFX}exposure_by_manager_summary")
    with pytest.raises(ToolRefused, match="syntax error at or near"):
        tools(plane, pid).propose_plan_change(**propose(f"{PFX}exposure_by_manager_summary", sql,
                                                        ("valuation_observations", "instruments", "portfolios", "legal_entities")).arguments)
    assert ST.select_text(sql).startswith("SELECT i.manager_name") and "QUALIFY" in ST.select_text(sql)  # tried as written, not re-printed


def test_nu13_another_projects_gold_is_said_plainly(world):  # noqa: F811
    plane, pid = world
    sql = f"create table {PFX}holdings_copy as select month, sum(net_worth) as nw from gold_investment_report_holdings_monthly group by 1"
    with pytest.raises(ToolRefused, match="another project"):
        tools(plane, pid).propose_plan_change(**propose(f"{PFX}holdings_copy", sql, ("gold_investment_report_holdings_monthly",)).arguments)


def test_nu09_a_column_posing_as_the_funds_manager_is_refused(world):  # noqa: F811
    plane, pid = world
    sql = (f"create table {PFX}statements_by_manager as select o.name as manager_name, count(*) as n from valuation_observations as v "
           "join organizations as o on v.organization_id = o.id group by 1")  # ch-7816de54's shape: the company's name as the manager
    with pytest.raises(ToolRefused, match="instruments.manager_name"):
        tools(plane, pid).propose_plan_change(**propose(f"{PFX}statements_by_manager", sql, ("valuation_observations", "organizations")).arguments)


def test_sp_c1_02_a_layer_prefixed_table_gets_its_real_name_back(world):  # noqa: F811
    plane, pid = world
    with pytest.raises(ToolRefused, match="called valuation_observations"):
        tools(plane, pid).dry_run_sql(sql="select currency, count(*) as n from silver_valuation_observations group by currency")


def test_nu25_depends_on_written_as_text_is_read_as_the_list(world):  # noqa: F811
    plane, pid = world
    got = tools(plane, pid).propose_plan_change(**{**propose(f"{PFX}statements_monthly_by_manager", BY_MANAGER).arguments,
                                                   "depends_on": "valuation_observations, instruments"})
    assert got["table"]["depends_on"] == ["valuation_observations", "instruments"]


# ---- NU-25: no claimed draft without a filed change -------------------------------------------------------------------------------

def test_nu25_a_claimed_draft_is_taken_out_when_nothing_was_filed(world):  # noqa: F811
    plane, pid = world
    bad = propose("gold_manager_reporting_scorecard", BY_MANAGER.replace(f"{PFX}statements_monthly_by_manager", "gold_manager_reporting_scorecard"))
    said = ("I have drafted a gold table called gold_manager_reporting_scorecard with manager_name and month. The data team can accept this change.")
    model = Script(ModelReply("", [bad]), ModelReply(said, []), ModelReply("", [bad]), ModelReply(said, []), ModelReply(said, []))
    got = S.chat(plane, ENG, pid, "Add a gold table: count of statements by instruments.manager_name and month", model)
    reply = got["turns"][-1]["text"]
    assert got["pending"] == [] and "I have drafted" not in reply and "can accept" not in reply
    assert "no change was filed" in reply and PFX in reply  # the reason, with the name approval needs


def test_nu25_a_claim_with_no_propose_call_at_all_is_taken_out(world):  # noqa: F811
    plane, pid = world
    model = Script(ModelReply("", [ToolCall("get_plan", {})]), ModelReply("I have proposed the table. It is awaiting approval from the data team.", []),
                   ModelReply("", [ToolCall("get_plan", {})]), ModelReply("I have proposed the table. It is awaiting approval from the data team.", []),
                   ModelReply("I have proposed it.", []))
    reply = S.chat(plane, ENG, pid, "Add a gold table of the late statements per manager", model)["turns"][-1]["text"]
    assert "I have proposed" not in reply and "no change was filed" in reply


# ---- NU-15: the failed run is read, the failed table replaced; NU-24/26 a table removed -------------------------------------------

def test_nu15_the_last_failed_run_is_in_the_context_and_the_failed_table_is_replaced(world, monkeypatch):  # noqa: F811
    plane, pid = world
    old = next(t["name"] for t in B.get(plane, pid)["tables"] if t["layer"] == "gold")
    from sh_platform.v1 import b6_run as R
    monkeypatch.setattr(R, "runs", lambda plane, pid, n=5: [{"run_id": "r1", "plan_version": 1, "mode": "sandbox", "status": "failed",
                                                             "steps": [{"table": old, "status": "failed", "error": 'Parser Error: syntax error at or near "GROUP"'}]}])
    fixed = BY_MANAGER.replace(f"{PFX}statements_monthly_by_manager", old)
    model = Script(ModelReply("", [propose(old, fixed, replaces=old)]), ModelReply("I proposed the fixed table in place of the failed one.", []))
    got = S.chat(plane, ENG, pid, "The trial run failed, please fix that table", model)
    assert "last_run" in model.seen[0] and "syntax error at or near" in model.seen[0]  # the failed run, worded by the program
    ch = got["pending"][0]
    assert ch["drops"] == [old] and ch["summary"].startswith("Replace") and [t["name"] for t in ch["tables"]] == [old]
    new = S.accept_change(plane, ENG, pid, ch["id"])
    assert [t["sql"] for t in new["tables"] if t["name"] == old] == [fixed]  # one table of that name, the fixed one


def test_nu24_nu26_a_gold_table_can_be_removed_by_a_change(world):  # noqa: F811
    plane, pid = world
    old = next(t["name"] for t in B.get(plane, pid)["tables"] if t["layer"] == "gold")
    model = Script(ModelReply("", [propose("", "", (), replaces=old)]), ModelReply("I proposed removing it.", []))
    model.replies[0] = ModelReply("", [ToolCall("propose_plan_change", {"name": old, "purpose": "", "sql": "", "depends_on": [], "replaces": old})])
    ch = S.chat(plane, ENG, pid, "Please remove that gold table, it has the wrong name", model)["pending"][0]
    assert ch["summary"] == f"Remove {old}" and ch["tables"] == []
    assert old not in {t["name"] for t in S.accept_change(plane, ENG, pid, ch["id"])["tables"]}


# ---- SP-C1-02: the refusal goes back to the model; the rules draft when the model never passes -------------------------------------

def test_sp_c1_02_the_retry_carries_the_refusal_and_the_rules_draft_files_the_change(world):  # noqa: F811
    plane, pid = world
    bad = propose(f"{PFX}valuations_by_currency", "create table " + PFX + "valuations_by_currency as select currency, count(*) as n "
                  "from silver_valuation_observations group by currency", ("silver_valuation_observations",))
    model = Script(ModelReply("", [bad]), ModelReply("Drafted.", []), ModelReply("", [bad]), ModelReply("Drafted.", []))
    got = S.chat(plane, ENG, pid, "add a count of valuations by currency", model)
    assert any("The plan check refused the last draft" in s and "called valuation_observations" in s for s in model.seen)  # told what to fix
    assert len(got["pending"]) == 1 and "drafted it by the rules" in got["turns"][-1]["text"]


# ---- NU-10: 'why that join?' ------------------------------------------------------------------------------------------------------

def test_nu10_why_that_join_is_answered_about_the_table_just_discussed(world):  # noqa: F811
    plane, pid = world
    t = {"name": f"{PFX}statements_monthly_by_manager", "layer": "gold", "columns": [], "depends_on": ["valuation_observations", "instruments"],
         "sql": BY_MANAGER, "purpose": "Statements per manager and month."}
    out = S.explain(plane, B.get(plane, pid), "Why that join?", f"Span: I drafted {t['name']}.", [t])
    assert "joins instruments on" in out and "v.instrument_id = i.id" in out and "version" not in out


# ---- NU-08, NU-26: the first plan sees the warehouse and keeps the grain ------------------------------------------------------------

def test_nu08_nu26_the_first_plan_reads_loaded_core_tables_and_drops_a_table_without_the_manager(world, monkeypatch):  # noqa: F811
    plane, pid = world
    with wh.connect(plane) as con:
        con.execute("insert into reports (id, organization_id, report_code, report_name) values (?,?,?,?)", [str(uuid.uuid4()), str(uuid.uuid4()), "r", "R"])
    kpis = [{"name": "Statements received", "definition": "Statements received per manager and month", "benchmark_by": []}]
    seen = {}

    def fake(plane_, model, ps, request, filled, schema, **k):
        seen["tables"] = set(filled)
        return [{"name": f"gold_{ps}_reports_count", "layer": "gold", "purpose": "", "columns": [], "depends_on": ["reports"],
                 "sql": f"create table gold_{ps}_reports_count as select count(*) as statements_received from reports"}]
    monkeypatch.setattr(S, "_ask_model", fake)
    import sh_platform.v1.b1_design as B1
    sow = B1.read_sow(plane, P.read(plane, pid)["intent_id"])
    monkeypatch.setattr(S, "signed_sow", lambda plane_, prj: {**sow, "kpis": kpis})
    plan = S.propose_plan(plane, ENG, pid, model=object())
    assert "reports" in seen["tables"]  # NU-08: a loaded core table is offered, not only the mapped ones
    assert not any(t["name"].endswith("reports_count") for t in plan["tables"])  # NU-26: no manager column, left out with a note
    assert any("one row per manager" in n for n in plan["notes"])


# ---- NU-16: the head of data who must approve can open ---------------------------------------------------------------------------

def test_nu16_the_approver_can_open_an_internal_project_while_a_plan_waits(world):  # noqa: F811
    plane, pid = world
    anita = Viewer("Anita Rao", frozenset({"analyst"}), False, "acc-anita")
    P._update(plane, pid, lambda r: r.update(sensitivity="internal", team=[{"name": "Priya Nair", "role": "owner"}]))
    assert B.get(plane, pid)["state"] == "proposed" and G1.may_see_project(plane, anita, pid) == "read"
    assert G1.may_see_project(plane, SOFIA, pid) == "preview"  # a consumer is not opened by it
    P._update(plane, pid, lambda r: r.update(sensitivity="restricted"))
    assert G1.may_see_project(plane, anita, pid) == "none"  # Restricted stays with the people named


# ---- DG-1, DG-3: the talk box ------------------------------------------------------------------------------------------------------

def test_dg1_a_reply_with_an_untraced_figure_falls_to_the_rules(world):  # noqa: F811
    plane, _ = world
    model = Script(ModelReply("", [ToolCall("whoami_and_access", {})]), ModelReply("Entity B's cash is $not available yet USD after the call.", []))
    got = T.ask(plane, SOFIA, "lumen", "What is Entity B's cash?", None, model)
    assert "not available yet" not in got["reply"] and got["rules_only"]


def test_dg1_lumen_on_the_landing_has_the_manager_and_status_tools(world):  # noqa: F811
    plane, _ = world
    reg = T._registry(plane, ENG, "lumen", "What changed at Kestrel?")
    names = {n for _, n in reg._tools}
    assert {"manager_statements", "holdings_status"} <= names
    with pytest.raises(ToolRefused, match="manager"):
        reg._tools[("consume", "manager_statements")]["func"](manager="Nobody Such")


def test_dg1_a_figure_question_answered_without_a_figure_gets_the_tiles(dash, monkeypatch):  # noqa: F811
    plane, pid, did, admin = dash
    monkeypatch.setattr(T.L, "answer_figure", lambda plane_, v, p, text: "Net worth is 130 in total. From the tile 'Holdings'.")
    model = Script(ModelReply("", [ToolCall("list_gold_tables", {"project": pid})]),
                   ModelReply("I cannot answer that question, but I can tell you about the definition of terms.", []))
    got = T.ask(plane, admin, "lumen", "What is the net worth?", None, model)
    assert got["reply"].startswith("About ") and "130" in got["reply"]


def test_dg3_where_a_gold_table_comes_from_by_rules_and_by_tool(world):  # noqa: F811
    plane, pid = world
    out = T.span_company(plane, ENG, "Where does the valuation monthly table come from?")
    assert "built from valuation_observations" in out
    reg = T._registry(plane, ENG, "span")
    gold = next(t["name"] for t in B.get(plane, pid)["tables"] if t["layer"] == "gold")
    got = reg._tools[("m4_build", "get_lineage")]["func"](project=pid, table=gold)
    assert "valuation_observations" in json.dumps(got)
    with pytest.raises(ToolRefused):  # G1 on the project argument
        reg._tools[("m4_build", "get_plan")]["func"](project="prj-nope")


def test_s_contract_the_admin_hears_the_model_trouble_on_a_rules_reply(world, monkeypatch):  # noqa: F811
    plane, pid = world
    from sh_platform.v1 import e6_trace
    admin = Viewer("Mei Chen", frozenset({"company_admin"}), False, "acc-mei")
    monkeypatch.setattr(e6_trace, "model_trouble", lambda plane_: {"code": "no_credit", "providers": ["OpenRouter"]})
    down = Script()  # every call fails, as an account out of credit does
    assert "out of credit" in T.ask(plane, admin, "span", "Which gold tables are there?", None, down)["reply"]
    assert "out of credit" in S.chat(plane, admin, pid, "Which gold tables are there?", down)["turns"][-1]["text"]
    assert "out of credit" not in T.ask(plane, SOFIA, "span", "Which gold tables are there?", None, down)["reply"]


def test_review_preview_level_reads_no_plan(world):  # noqa: F811
    plane, pid = world
    P._update(plane, pid, lambda r: r.update(sensitivity="internal", team=[{"name": "Priya Nair", "role": "owner"}]))
    assert G1.may_see_project(plane, SOFIA, pid) == "preview"
    with pytest.raises(ToolRefused):
        T._registry(plane, SOFIA, "span").call("span", "get_plan", project=pid) if False else T._SpanAnywhere(plane, SOFIA).delegate("get_plan")(project=pid)
