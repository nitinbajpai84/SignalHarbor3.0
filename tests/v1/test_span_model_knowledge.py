"""SK1: Span knows the layers and the data model: describe_layers, describe_table (layer, keys, relationships, lineage) and get_lineage
answer from the catalogue, the plan and the dashboards, honour access, and leave the egress gateway nothing to refuse."""
import json

import pytest

from sh_platform.agents.loop import run_agent
from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.agents.registry import ToolRefused
from sh_platform.egress.rows import json_findings
from sh_platform.profile.view import Viewer
from sh_platform.v1 import agent_tools as AT
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import b6_span as S
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import p1_project as P
from sh_platform.v1 import span_tools as ST
from sh_platform.v1 import wh
from tests.v1.test_b6 import ENG, HEAD
from tests.v1.test_b6 import world as b6_world  # noqa: F401 - the Evergreen plane with a signed intent and an approved mapping

GOLD = "gold_monthly_investment_report_valuation_monthly"
OUTSIDER = Viewer("Bob", frozenset({"participant"}), False, "acc-bob")
MOD = "m3_connect"


@pytest.fixture()
def built(b6_world):  # noqa: F811
    """The plan is approved (gold registered), the gold table exists, and a dashboard tile reads it."""
    plane, pid = b6_world
    S.propose_plan(plane, ENG, pid)
    B.approve(plane, HEAD, pid)
    with wh.connect(plane) as con:
        con.execute(f"create table {GOLD} as select 1 as month_index")
    d = D.create(plane, ENG, pid, "Board view")
    D.add_proposal(plane, ENG, pid, d["id"], {"title": "Monthly", "sql": f"select * from {GOLD}",
                                              "spec": {"mark": "bar"}})
    return plane, pid


def tool(plane, viewer, pid, name, **a):
    return ST.span_registry(plane, viewer, pid, module_id=MOD).call(plane.company_id, MOD, name, a)


def clean(result):
    assert json_findings(json.dumps(result)) == (None, [])
    return result


def test_describe_layers_lists_real_silver_with_purpose_and_the_projects_gold(built):
    plane, pid = built
    got = clean(tool(plane, ENG, pid, "describe_layers", project=""))
    assert "shared company data model" in got["meaning"]
    silver = {l.split(":")[0]: l for l in got["silver"]}
    assert "valuation_observations" in silver and "instruments" in silver
    assert "rows" in silver["valuation_observations"]  # an aggregate, not a row
    assert any(l.startswith(GOLD + ":") and "not built yet" not in l for l in got["gold"])
    assert any(l.startswith("bronze_administrator_export_valuations:") for l in got["bronze"])


def test_describe_layers_for_one_project_and_a_project_nobody_gave_you(built):
    plane, pid = built
    assert any(GOLD in l for l in clean(tool(plane, ENG, pid, "describe_layers", project=pid))["gold"])
    with pytest.raises(ToolRefused):
        tool(plane, ENG, pid, "describe_layers", project="no-such-project")


def test_describe_table_shows_layer_relationships_and_lineage(built):
    plane, pid = built
    got = clean(tool(plane, ENG, pid, "describe_table", table="valuation_observations"))
    assert got["layer"] == "silver" and got["primary_key"] == "id"
    assert "points to instruments through instrument_id" in got["links"]  # SPM-C1-01: one list of links, both directions, in words
    assert any(l.startswith("is fed by ") for l in got["links"]) and any(l.startswith("feeds ") for l in got["links"]) and got["links_note"]
    assert "bronze_administrator_export_valuations" in got["fed_by"] and GOLD in got["feeds"]
    gold = clean(tool(plane, ENG, pid, "describe_table", table=GOLD))
    assert gold["layer"] == "gold" and "valuation_observations" in gold["fed_by"]


def test_get_lineage_of_the_gold_table_reaches_back_to_bronze_and_on_to_the_dashboard(built):
    plane, pid = built
    got = clean(tool(plane, ENG, pid, "get_lineage", table=GOLD))
    assert got["layer"] == "gold"
    assert f"bronze_administrator_export_valuations -> valuation_observations -> {GOLD}" in got["fed_by_paths"]
    assert f"{GOLD} -> dashboard Board view" in got["feeds_paths"]
    with pytest.raises(ToolRefused):
        tool(plane, ENG, pid, "get_lineage", table="no_such_table")


def test_someone_without_the_project_sees_none_of_its_gold(built):
    plane, pid = built
    P._update(plane, pid, lambda r: r.update(sensitivity="restricted", team=[]))
    got = clean(AT.AgentTools(plane, OUTSIDER, "lumen").describe_layers(project=""))
    assert not any(GOLD in l for l in got["gold"]) and "valuation_observations" in " ".join(got["silver"])
    with pytest.raises(ToolRefused):
        AT.AgentTools(plane, OUTSIDER, "lumen").describe_table(table=GOLD)
    with pytest.raises(ToolRefused):
        AT.AgentTools(plane, OUTSIDER, "lumen").describe_layers(project=pid)
    with pytest.raises(ToolRefused):
        tool(plane, OUTSIDER, pid, "get_lineage", table="valuation_observations")
    silver = AT.AgentTools(plane, OUTSIDER, "lumen").describe_table(table="valuation_observations")
    assert GOLD not in " ".join(silver["feeds"])  # the feed into a project they cannot see is not told either


def test_a_silver_question_makes_the_span_loop_call_describe_layers(built):
    plane, pid = built

    class Script:
        def __init__(self, *r):
            self.r, self.seen = list(r), []

        def complete(self, module_id, messages, tools=None, suppressed=None):
            self.seen.append(json.dumps(messages))
            return self.r.pop(0)

    model = Script(ModelReply("", [ToolCall("describe_layers", {"project": ""})]),
                   ModelReply("Silver is the shared company model; valuation_observations is one of its tables.", []))
    reg = ST.span_registry(plane, ENG, pid, module_id=MOD)
    res = run_agent(model, reg, plane.company_id, MOD, "Span", "You are Span. " + ST.PROMPT, {"facts": []}, "what is in the silver layer?")
    assert res.status == "done" and res.tools_called == ["describe_layers"] and res.refusals == []
    assert "valuation_observations" in model.seen[1]  # the answer was written after the model was shown the real tables
    assert "describe_layers" in ST.PROMPT
