"""Span's company chat must not fall back to the rules when the model counts what it lists (the number guard's 'not available yet' mark)."""
from sh_platform.agents.guard import check_numbers, context_facts
from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.v1 import talk as T
from tests.v1.test_talk_to_all import SOFIA, world  # noqa: F401 - the Evergreen plane

ANSWER = ("The investment report uses four gold tables:\n"
          "1. gold_monthly_investment_report_holdings_monthly\n"
          "2. gold_monthly_investment_report_net_worth_entity_monthly\n"
          "3. gold_monthly_investment_report_benchmark_monthly\n"
          "4. gold_monthly_investment_report_benchmark_weights")


class ToolThenAnswer:
    """A fake model: calls list_tables once, then answers ANSWER every time."""
    def __init__(self):
        self.calls = 0

    def complete(self, module_id, messages, tools=None, suppressed=None):
        self.calls += 1
        if self.calls == 1:
            return ModelReply("", [ToolCall("list_tables", {"layer": "gold"})])
        return ModelReply(ANSWER, [])


def test_a_company_chat_count_of_the_tables_it_lists_is_not_left_out(world):  # noqa: F811
    plane, _ = world
    got = T.ask(plane, SOFIA, "span", "Which gold tables does the investment report use?", None, ToolThenAnswer())
    assert "not available yet" not in got["reply"] and not got["rules_only"]
    assert got["reply"].startswith("The investment report uses four gold tables")


def test_a_count_the_reply_does_not_list_is_still_left_out():
    text = "The investment report uses four gold tables:\n1. a\n2. b\n3. c\n4. d, and 43 more rows."
    r = check_numbers(text, [], "Which gold tables?", words={"gold", "table"})
    assert r.missing == ["43"]


def test_a_money_figure_no_tool_returned_is_left_out_even_when_it_matches_the_list_length():
    text = "The report shows USD 4 across:\n1. a\n2. b\n3. c\n4. d"
    assert check_numbers(text, [], "What is the value?").missing == ["4"]


def test_a_count_in_the_context_is_not_left_out():
    ctx = {"projects_you_can_read": ["Monthly investment report (id prj-84d783f2)"], "tables": ["43 shared tables are in the layer"]}
    text = "There are 43 shared tables that the report can read."
    assert check_numbers(text, context_facts(ctx), "What can the report read?").missing == []


def test_a_money_figure_in_the_context_is_still_left_out():
    ctx = {"note": "Net worth was USD 4,200,000 at month end."}
    assert check_numbers("Net worth was 4,200,000.", context_facts(ctx), "What is net worth?").missing == ["4,200,000"]


def test_a_number_from_earlier_talk_is_never_a_source():
    from sh_platform.agents.guard import context_facts
    got = context_facts({"earlier_in_this_chat": ["Span: there are 12 trades"], "projects_you_can_read": ["Report (4 tables)"]})
    assert [f["value"] for f in got] == ["4"]
