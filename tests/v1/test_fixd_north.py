"""FIXD: North's claims match what landed, result and success are filled from the person's words, figures already given are never asked
again, KPIs and sources are not drafted twice, and a money KPI gets a currency. Fake model only; synthetic data (UC6 and UC8 wording)."""
import json

import pytest

from sh_platform.agents.protocols import ModelReply
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import g1_access
from sh_platform.v1 import g3_sheet as G3
from sh_platform.v1 import i2_north as N
from sh_platform.v1 import i6_chat as C
from sh_platform.v1 import l2_proposals as L2
from sh_platform.v1 import north_tools as NT

MEI = Viewer("Mei Chen", frozenset({"analyst"}), False, "acc-mei")


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    monkeypatch.setattr(g1_access, "check_agent", lambda *a, **k: None)
    (tmp_path / "co").mkdir()
    return PlaneStore(tmp_path).plane_for("co")


class Model:
    def __init__(self, *answers):
        self.answers = list(answers)

    def complete(self, module_id, messages, tools=None, **kw):
        if "Write the memory of this conversation." in json.dumps(messages):
            return ModelReply(text="{}")
        a = self.answers.pop(0)
        return ModelReply(text=a if isinstance(a, str) else json.dumps(a))


def _sow(plane, iid, **rows):
    sow = N.read_sow(plane, iid)
    sow.update(rows)
    write_json_atomic(plane.path("intents", iid, "sow.json"), sow)


def _accept_all(plane, iid):
    for p in L2.pending(plane, iid, ("sow", "process_map")):
        L2.accept(plane, iid, p["id"], "Mei Chen")
    return N.read_sow(plane, iid)


def _paths(v):
    return [c["path"] for p in v["proposals"]["pending"] for c in p["changes"]]


def test_a_claim_with_no_matching_change_is_left_out(plane):
    iid = C.create(plane, MEI, "A monthly capital call view")
    m = Model({"reply": "Got it. I have removed the six-month headroom KPI. I have added the result description and success criteria. "
                        "Who approves the 30-day view?",
               "sow_patch": {"kpis": [{"name": "Calls due within 30 days", "definition": "confirmed calls due within 30 days"}]}})
    text = C.chat(plane, iid, MEI, "Calls due within 30 days is the sum of confirmed calls due in the next 30 days.", model=m)["turns"][-1]["text"]
    assert "removed" not in text and "success criteria" not in text
    assert "Who approves the 30-day view?" in text and "KPI Calls due within 30 days" in text


def test_a_claim_that_matches_the_change_stays():
    got = C.true_claims("I have added the result description. Who signs?", [{"op": "add", "path": "template_fields/result"}], [], [])
    assert got == "I have added the result description. Who signs?"


def test_result_and_success_are_filled_from_the_persons_words(plane):
    iid = C.create(plane, MEI, "A monthly capital call view")
    m = Model({"reply": "Thanks, noted. Who may see it?", "sow_patch": {}})
    said = ("To finish: the result looks like one page per month with a card per entity. We will know it worked when the figures match "
            "my hand spreadsheet for July to September.")
    v = C.chat(plane, iid, MEI, said, model=m)
    assert {"template_fields/result", "template_fields/success"} <= set(_paths(v))
    tf = _accept_all(plane, iid)["template_fields"]
    assert tf["result"].startswith("One page per month") and tf["success"].startswith("The figures match my hand spreadsheet")


def test_the_propose_tool_drafts_result_and_success(plane):
    iid = C.create(plane, MEI, "A monthly capital call view")
    t = NT.NorthTools(plane, MEI, iid)
    assert t.propose_intent_section("success", {"text": "Raj approves October without the spreadsheet."})["sow_patch"] == \
        {"template_fields": {"success": "Raj approves October without the spreadsheet."}}
    assert t.propose_intent_section("template_fields", {"result": "One page a month."})["sow_patch"]["template_fields"] == {"result": "One page a month."}


def test_last_months_figures_already_given_are_not_asked_again(plane):
    iid = C.create(plane, MEI, "A monthly trade check")
    _sow(plane, iid, kpis=[{"code": "K01", "name": "Trades compared", "definition": "trades in both files", "status": "defined", "source_ids": []}])
    G3.upsert(plane, iid, [{"code": "K01", "kpi": "Trades compared", "dims": {"period": "2026-07", "entity": ""}, "reported": None,
                            "expected": None, "tolerance": None, "source": "", "stated_by": "Mei Chen"},
                           {"code": "K01", "kpi": "Trades compared", "dims": {"period": "2026-07"}, "reported": 4.0, "expected": 4.0,
                            "tolerance": 0.0, "source": "said by Mei Chen", "stated_by": "Mei Chen"}])
    ask = "Could you give me last month's figures for each KPI?"
    m = Model({"reply": f"Thanks. {ask}", "asked": "benchmarks", "sow_patch": {}, "covered": ["benchmarks"]})
    text = C.chat(plane, iid, MEI, "The extraction specs are right.", model=m)["turns"][-1]["text"]
    assert ask not in text and "not the figures yet" not in text
    assert not C.open_gaps(plane, iid, N.read_sow(plane, iid))  # the row with no figure is superseded by the one given


def test_figures_asked_once_and_answered_are_not_asked_again():
    thread = {"turns": [{"by": "north", "text": "Give me last month's numbers for each figure?"},
                        {"by": "person", "text": "July: trades compared 4, breaks 0."}]}
    assert C.asked_figures_before(thread)


def test_a_kpi_and_a_source_under_a_near_name_are_not_drafted_twice(plane):
    iid = C.create(plane, MEI, "A monthly trade check")
    _sow(plane, iid, kpis=[{"code": "K01", "name": "Breaks above allowance", "definition": "count of breaks above the allowance",
                            "unit": "count", "status": "defined", "source_ids": []}],
         sources=[{"id": "src_a", "name": "Cash data (admin closing cash)", "kind": "file", "holds": "", "owner": "", "fields": []}])
    m = Model({"reply": "Which entity is it for?",
               "sow_patch": {"kpis": [{"name": "Breaks above 5,000 USD allowance", "owner": "Mei Chen"},
                                      {"name": "Net break (USD)"}, {"name": "Net break in USD"}],
                             "sources": [{"name": "Cash and call data", "owner": "Leo Park"}]}})
    C.chat(plane, iid, MEI, "Breaks above 5,000 USD allowance and net break in USD; Leo owns the cash and call data.", model=m)
    sow = _accept_all(plane, iid)
    assert [k["name"] for k in sow["kpis"]] == ["Breaks above allowance", "Net break (USD)"]
    assert [s["name"] for s in sow["sources"]] == ["Cash data (admin closing cash)"] and sow["sources"][0]["owner"] == "Leo Park"
    assert sow["kpis"][0]["unit"] == "count"  # a count with a threshold in money stays a count


def test_a_money_kpi_gets_the_currency_not_count(plane):
    iid = C.create(plane, MEI, "A monthly capital call view")
    m = Model({"reply": "Which entity first?", "sow_patch": {"kpis": [{"name": "Calls due within 30 days", "unit": "count",
                                                                      "definition": "confirmed calls due within 30 days of the as-at date"}]}})
    C.chat(plane, iid, MEI, "All figures are in USD. Calls due within 30 days are confirmed calls due within 30 days.", model=m)
    assert _accept_all(plane, iid)["kpis"][0]["unit"] == "USD"


def test_a_kpi_already_in_the_intent_is_proposed_for_removal_when_turned_down(plane):
    iid = C.create(plane, MEI, "A monthly capital call view")
    _sow(plane, iid, kpis=[{"code": "K01", "name": "Calls due within 30 days", "status": "defined", "source_ids": []},
                           {"code": "K02", "name": "Minimum six-month funding headroom", "status": "unclear", "source_ids": []}])
    m = Model({"reply": "I have removed the six-month funding headroom KPI. Who approves it?", "withdraw": ["Minimum six-month funding headroom"]})
    v = C.chat(plane, iid, MEI, "I did not ask for the six-month funding headroom; please remove it.", model=m)
    assert "kpis/Minimum six-month funding headroom" in _paths(v) and "removed the six-month" in v["turns"][-1]["text"]
    assert [k["name"] for k in _accept_all(plane, iid)["kpis"]] == ["Calls due within 30 days"]


def test_h3_a_figure_is_never_drafted_as_a_source(plane):
    iid = C.create(plane, MEI, "A monthly cash view")
    m = Model({"reply": "Who sends the bank file?",
               "sow_patch": {"kpis": [{"name": "Available cash by entity", "sources": ["Bank statements"]}],
                             "sources": [{"name": "Available cash by entity", "kind": "system"}, {"name": "Bank statements", "kind": "file", "owner": "Mei Chen"}]}})
    C.chat(plane, iid, MEI, "I want available cash by entity from the bank statements.", model=m)
    sow = _accept_all(plane, iid)
    assert [s["name"] for s in sow["sources"]] == ["Bank statements"] and sow["kpis"][0]["source_ids"] == [sow["sources"][0]["id"]]
