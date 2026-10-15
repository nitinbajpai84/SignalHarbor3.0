"""Wave 2, package N: one regression per ticket (NU-01..07, H1-04..06, N1-SOP-01, N1-A15-01/02, N1-INT-01, the admin trouble line).
Models are stubs that replay the reply shapes recorded in docs/test-evidence/agents/new-uc and cycle-1/H-aqf15. Synthetic data only."""
import json

import pytest

from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.agents.registry import ToolRefused
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import g1_access
from sh_platform.v1 import g3_sheet as G3
from sh_platform.v1 import i2_north as N
from sh_platform.v1 import i6_chat as C
from sh_platform.v1 import k8_sop as K8
from sh_platform.v1 import l2_proposals as L2
from sh_platform.v1 import north_tools as NT
from sh_platform.v1 import t1_templates as T1

MEI = Viewer("Mei Chen", frozenset({"analyst"}), False, "acc-mei")
# NU-05: use case B, turn 33, as Mei typed it
B33 = ("Success: the tile matches our sheet. Last month, 30 Sep 2026, we reported Cedarpoint Ventures at 56.50% of the Entity B portfolio "
       "EG-B-OPS (12,925,000 of 22,875,000), headroom -1.50 points; it should read the same after the load.")


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    monkeypatch.setattr(g1_access, "check_agent", lambda *a, **k: None)
    (tmp_path / "co").mkdir()
    return PlaneStore(tmp_path).plane_for("co")


class Model:
    """Replays answers in turn: a dict is a JSON answer, a str prose, a ToolCall (or a list of them) a tool step; none left: down."""
    def __init__(self, *answers):
        self.answers, self.seen = list(answers), []

    def complete(self, module_id, messages, tools=None, **kw):
        self.seen.append(json.dumps(messages))
        if "Write the memory of this conversation." in self.seen[-1]:  # the memory summary after a turn (H1-08) is not a North reply
            return ModelReply(text="{}")
        if not self.answers:
            raise RuntimeError("down")
        a = self.answers.pop(0)
        if isinstance(a, (ToolCall, list)):
            return ModelReply(tool_calls=a if isinstance(a, list) else [a])
        return ModelReply(text=a if isinstance(a, str) else json.dumps(a))


def _kpi_sow(plane, iid):
    sow = N.read_sow(plane, iid)
    sow["kpis"] = [{"code": "K01", "name": "Manager exposure headroom", "definition": "55 minus the share", "status": "defined", "source_ids": []}]
    write_json_atomic(plane.path("intents", iid, "sow.json"), sow)


# ---- NU-01 ----------------------------------------------------------------------------------------------------------------------

def test_nu01_a_copied_drafts_line_is_dropped_so_the_reply_carries_one(plane):
    iid = C.create(plane, MEI, "A manager reporting scorecard")
    m = Model({"reply": "I'll assume monthly. Who reads it? I have proposed 1 thing to change; say yes to accept, or tell me what is wrong.",
               "sow_patch": {"goal": {"readers": ["Daniel Foo"]}}, "covered": []})
    text = C.chat(plane, iid, MEI, "It is for Daniel Foo.", model=m)["turns"][-1]["text"]
    assert "proposed 1 thing" not in text and text.count("say yes to accept") == 1


def test_nu01_an_answered_question_is_not_asked_again(plane):
    iid = C.create(plane, MEI, "A manager reporting scorecard")
    q = "What decisions will Daniel make from it?"
    m = Model({"reply": q, "asked": "readers", "sow_patch": {"goal": {"readers": ["Daniel Foo"]}}, "covered": []},
              {"reply": f"Thanks. {q}", "asked": "readers", "sow_patch": {"goal": {"decisions": ["which managers to chase"]}}, "covered": []})
    C.chat(plane, iid, MEI, "A scorecard for Daniel Foo.", model=m)
    v = C.chat(plane, iid, MEI, "Daniel decides which managers to chase.", model=m)
    assert q not in v["turns"][-1]["text"] and v["asked"] not in (None, "readers")


def test_nu01_the_product_lines_never_reach_the_model_in_earlier_turns():
    assert C.own_words("Who reads it? I have drafted who reads it; say yes to accept, or tell me what is wrong.") == "Who reads it?"


# ---- NU-02 ----------------------------------------------------------------------------------------------------------------------

def test_nu02_sources_turned_down_in_words_leave_the_pending_proposal(plane):
    iid = C.create(plane, MEI, "A manager reporting scorecard")
    srcs = [{"name": "Excel tracker", "kind": "file"}, {"name": "Signal Harbor", "kind": "system"}, {"name": "Fund register", "kind": "file"}]
    m = Model({"reply": "Which rules apply?", "sow_patch": {"sources": srcs}, "covered": []},
              {"reply": "I have removed the Excel tracker and Signal Harbor from the sources. What does good look like?",
               "withdraw": ["Excel tracker", "Signal Harbor"], "covered": []})
    C.chat(plane, iid, MEI, "Sources: the Excel tracker, Signal Harbor and the fund register.", model=m)
    v = C.chat(plane, iid, MEI, "Not the Excel tracker and not 'Signal Harbor' as sources, please drop those two.", model=m)
    pend = [c["path"] for p in v["proposals"]["pending"] for c in p["changes"]]
    assert pend == ["sources/Fund register"] and C.NOTHING_DRAFTED not in v["turns"][-1]["text"]
    p = v["proposals"]["pending"][0]
    L2.accept(plane, iid, p["id"], "Mei Chen")
    assert [s["name"] for s in N.read_sow(plane, iid)["sources"]] == ["Fund register"]


def test_nu02_a_proposal_with_every_row_withdrawn_is_turned_down_with_the_reason(plane):
    iid = C.create(plane, MEI, "A manager reporting scorecard")
    m = Model({"reply": "Which rules apply?", "sow_patch": {"sources": [{"name": "Excel tracker"}]}, "covered": []},
              {"reply": "Removed. What does good look like?", "withdraw": ["excel tracker"], "covered": []})
    C.chat(plane, iid, MEI, "We keep an Excel tracker.", model=m)
    v = C.chat(plane, iid, MEI, "Not the Excel tracker, it is not a source.", model=m)
    assert not v["proposals"]["pending"] and v["proposals"]["recent"][-1]["status"] == "rejected"
    assert "not a source" in v["proposals"]["recent"][-1]["reason"]


# ---- NU-03 ----------------------------------------------------------------------------------------------------------------------

def test_nu03_the_sign_check_reads_the_benchmark_sheet_through_the_kpis():
    tpl = {"kind": "intent_of_work", "fields": [{"key": "benchmarks", "required": True, "label": "For each figure, what you reported"}]}
    k = {"code": "K01", "name": "Statements received"}
    assert T1.missing_required(tpl, {"kpis": [k]}) == ["For each figure, what you reported"]
    assert T1.missing_required(tpl, {"kpis": [{**k, "benchmark": {"sheet": True, "rows": ["br_1"], "reported": 7.0}}]}) == []
    assert T1.missing_required(tpl, {"kpis": [{**k, "benchmark": None}]}) == []  # "we have none" is an answer
    assert T1.missing_required(tpl, {"kpis": [{**k, "benchmark": {"sheet": True, "rows": ["br_1"], "reported": None}}]})  # needs figure
    assert "benchmarks" in T1._SOW["intent_of_work"]


# ---- NU-04, NU-05 -------------------------------------------------------------------------------------------------------------------

def test_nu04_nu05_benchmark_figures_land_from_the_persons_words_and_close_the_gap(plane):
    iid = C.create(plane, MEI, "Exposure by manager with limit headroom")
    _kpi_sow(plane, iid)
    G3.upsert(plane, iid, [{"code": "K01", "kpi": "Manager exposure headroom", "dims": {"period": "2026-09", "manager": ""}, "reported": None,
                            "expected": None, "tolerance": None, "source": "", "stated_by": "Mei Chen"}])
    rows = [{"kpi": "Manager exposure headroom", "period": "2026-09", "by": {"manager": "Cedarpoint Ventures", "portfolio": "EG-B-OPS"},
             "reported": "-1.50", "expected": "same"},
            {"kpi": "Manager exposure headroom", "period": "2026-09", "by": {"manager": "Kestrel Ridge"}, "reported": "-1.75"},  # invented
            {"kpi": "Manager exposure headroom", "period": "2026-09", "by": {"manager": "Cedarpoint Ventures"}, "reported": "1.50"}]  # sign lost
    m = Model({"reply": "Thank you for the benchmark figures. Which documents are involved?", "covered": ["benchmarks", "success"],
               "sow_patch": {"kpis": [{"name": "Manager exposure headroom", "benchmark": "given", "benchmark_by": ["manager"]}]},
               "benchmark_rows": rows})
    v = C.chat(plane, iid, MEI, B33, model=m)
    sheet = G3.read(plane, iid)
    live = [r for r in sheet["rows"] if not r.get("dropped")]
    assert [(r["reported"], r["expected"], r["dims"]) for r in live] == [
        (-1.5, -1.5, {"period": "2026-09", "manager": "Cedarpoint Ventures", "portfolio": "EG-B-OPS"})]
    assert not G3.missing(plane, iid) and "not the figures yet" not in v["turns"][-1]["text"]
    assert not any(r.get("reported") == 30 or r.get("expected") == 2026 for r in sheet["rows"])  # no sentence cut into rows
    tpl = {"kind": "intent_of_work", "fields": [{"key": "benchmarks", "required": True, "label": "B"}]}
    assert T1.missing_required(tpl, N.read_sow(plane, iid)) == []  # NU-03 end to end: the intent can be signed


# ---- NU-06 ----------------------------------------------------------------------------------------------------------------------

def _tools(plane):
    iid = C.create(plane, MEI, "A manager reporting scorecard")
    return iid, NT.NorthTools(plane, MEI, iid)


def test_nu06_the_section_names_and_row_shapes_a_model_sends_are_taken(plane):
    _, t = _tools(plane)
    got = t.propose_intent_section("kpis", [{"name": "Manager value", "definition": "Sum of the latest statements", "benchmark": "given",
                                             "pack_suggested": False, "sources": "Manager statements"},
                                            {"name": "Manager share", "unit": "percent"}])
    assert [k["name"] for k in got["sow_patch"]["kpis"]] == ["Manager value", "Manager share"]
    assert got["sow_patch"]["kpis"][0]["sources"] == ["Manager statements"] and "pack_suggested" not in got["sow_patch"]["kpis"][0]
    assert t.propose_intent_section("Sources", {"name": "Fund register", "kind": "file"})["sow_patch"]["sources"][0]["kind"] == "file"
    assert t.propose_process_step("Collect", "Mei Chen", "", "File drop", "", "", True, "")["step"]["manual"] is True


def test_nu06_repeated_refusals_tell_the_model_to_stop_and_the_turn_ends_with_a_draft(plane):
    iid, _ = _tools(plane)
    bad = [ToolCall("propose_intent_section", {"section": f"figures_{i}", "content": {"name": "Headroom"}}) for i in range(4)]
    m = Model(bad,
              {"reply": "I put the three figures in the draft. Which sources hold them?",
               "sow_patch": {"kpis": [{"name": "Manager value"}, {"name": "Manager share"}, {"name": "Headroom"}]}, "covered": ["kpis"]})
    v = C.chat(plane, iid, MEI, "The figures: manager value, manager share and headroom.", model=m)
    assert "Stop calling this tool" in m.seen[1] and m.seen[1].count("Stop calling this tool") == 2  # from the third refusal on
    assert [c["path"] for p in v["proposals"]["pending"] for c in p["changes"] if c["op"] == "add"][:3] == [
        "kpis/Manager value", "kpis/Manager share", "kpis/Headroom"]


# ---- NU-07 ----------------------------------------------------------------------------------------------------------------------

def test_nu07_the_closing_names_the_controls_on_the_page(plane):
    sow = N.empty_sow("ini-x", "A scorecard")
    text = C.closing_summary("ini-x", sow)
    assert "Sign the intent of work" in text and "Send to Build" in text and "Hand to the architect" not in text
    assert "Daniel Foo can sign the intent of work" in C.closing_summary("ini-x", sow, None, "Daniel Foo")
    assert "architect" not in C.CLOSING


# ---- H1-04 ----------------------------------------------------------------------------------------------------------------------

def test_h104_a_question_about_what_exists_looks_with_a_tool_first(plane):
    q = "What does the office already have about the monthly investment report? Two or three lines, please."
    assert C._DATA_Q.search(q)
    m = Model("From your documents: a monthly report exists.", ToolCall("list_intents", {}), {"reply": "You have one draft intent.", "covered": []})
    C.start(plane, MEI, q, model=m)
    assert "check with a tool first" in m.seen[1]


# ---- H1-05, N1-SOP-01 ----------------------------------------------------------------------------------------------------------------

def test_h105_n1sop01_the_steps_manual_flag_wins_and_hand_work_words_count():
    sow = {"process": {"steps": [
        {"n": 1, "name": "Collect the exports", "does": "Downloads the files and saves them to the shared file drop", "system": "File drop"},
        {"n": 2, "name": "Review", "does": "Signs off", "system": "Report pack", "manual": True},
        {"n": 3, "name": "Convert", "does": "Converts in Excel", "system": "Excel", "manual": False},
        {"n": 4, "name": "Read", "does": "Reads the pack", "system": "Report pack"}]}}
    assert K8.build(sow)["manual_steps"] == [1, 2]


def test_h105_get_process_map_reports_the_flag(plane):
    iid, t = _tools(plane)
    sow = N.read_sow(plane, iid)
    sow["process"] = {"steps": [{"n": 1, "name": "Convert", "system": "Excel", "manual": False}], "handovers": []}
    write_json_atomic(plane.path("intents", iid, "sow.json"), sow)
    assert t.get_process_map("")["steps"][0].endswith("manual: no")


# ---- H1-06 ----------------------------------------------------------------------------------------------------------------------

def test_h106_a_draft_that_did_not_land_is_not_claimed(plane):
    iid = C.create(plane, MEI, "A monthly investment report")
    m = Model({"reply": "Thanks, the note is clear and I have drafted the six steps, the hand-overs and the four manual steps. Who reads it?",
               "covered": []})
    text = C.chat(plane, iid, MEI, "Here is how we produce the report today.", model=m)["turns"][-1]["text"]
    assert "drafted the six steps" not in text and text.startswith(C.NOTHING_DRAFTED) and "Who reads it?" in text


# ---- N1-A15-01, N1-A15-02 ----------------------------------------------------------------------------------------------------------

def test_n1a1501_a_reply_is_held_to_three_sentences_with_its_question():
    long = ("You want the report monthly. It goes to Daniel Foo. It is due by the 3rd business day. Sofia owns the limits. "
            "Mei does steps 1 to 3. Who approves a change?")
    got = C.budget(long, 3)
    assert C.sentences(got) == ["You want the report monthly.", "It goes to Daniel Foo.", "Who approves a change?"]
    assert C.budget("One. Two?", 3) == "One. Two?" and len(C.sentences(C.budget(long, 2))) == 2
    assert len(C.sentences("Today: 1. Mei exports the file. 2. Raj checks it.")) == 2  # a list number is not a sentence


def test_n1a1502_a_drafted_steps_preview_shows_its_control_and_exception():
    step = {"name": "Check cash", "who": "Mei Chen", "does": "Opens the cash tab and pastes balances " * 12, "system": "Excel",
            "control": "Inside 5,000 USD per entity per day", "exception": "Over tolerance opens a break case", "manual": True}
    text = L2._row_text(step)
    assert "control: Inside 5,000 USD" in text and "exception: Over tolerance" in text and "manual: yes" in text
    assert text.index("does:") > text.index("exception:")


# ---- N1-INT-01 --------------------------------------------------------------------------------------------------------------------

def test_n1int01_a_landing_question_leaves_no_draft_until_a_goal_is_stated(plane):
    m = Model({"reply": "There is no intent for that yet. What would you like to build?", "covered": []},
              {"reply": "Who reads it?", "covered": ["goal"]})
    v = C.start(plane, MEI, "Which intents do we have?", model=m)
    iid = v["id"]
    from sh_platform.v1 import p1_project as P1
    assert C.open_intent(plane, MEI) is None and C.recent_intents(plane, MEI) == [] and P1.for_intent(plane, iid) is None and v["project_id"] is None
    C.chat(plane, iid, MEI, "We need a monthly manager scorecard for Daniel.", model=m)
    assert C.open_intent(plane, MEI) == iid and N.read_sow(plane, iid)["title"] == "New intent"  # NA-5: the title is proposed, never written
    assert "Monthly manager scorecard for Daniel" in json.dumps(C.view(plane, iid)["proposals"]["pending"])
    assert P1.for_intent(plane, iid) is not None


# ---- model trouble line --------------------------------------------------------------------------------------------------------

def test_the_model_failure_reply_carries_the_admin_line_when_s_gives_one(plane, monkeypatch):
    from sh_platform.v1 import e6_trace
    iid = C.create(plane, MEI, "A monthly report")
    monkeypatch.setattr(e6_trace, "model_offline_line", lambda plane, viewer: "The model account is out of credit (openrouter).", raising=False)
    text = C.chat(plane, iid, MEI, "Who should read it?", model=Model())["turns"][-1]["text"]  # NM1: the rules answer, led by the line
    assert text.startswith("The model account is out of credit (openrouter).")
    monkeypatch.setattr(e6_trace, "model_offline_line", lambda plane, viewer: e6_trace.OFFLINE_LINE, raising=False)
    assert C.chat(plane, iid, MEI, "Who should read it?", model=Model())["turns"][-1]["text"].startswith(C.OFFLINE)


def test_nu06_the_recorded_refused_shapes_now_draft_and_a_claim_in_words_is_backed(plane):
    """tr-north-52658793-*: section "kpis" and content sent as JSON text, repeated, then the model answers in words."""
    iid, _ = _tools(plane)
    shapes = [ToolCall("propose_intent_section", {"section": "kpis", "content": {"name": "Manager concentration", "unit": "percent"}}),
              ToolCall("propose_intent_section", {"section": "kpi", "content": json.dumps({"name": "Manager concentration", "unit": "percent"})})]
    m = Model(list(shapes), list(shapes), "I have drafted the three figures for you to check.")  # the repeat ends the tool steps
    v = C.chat(plane, iid, MEI, "The figure: share of the portfolio per manager in percent.", model=m)
    text = v["turns"][-1]["text"]
    assert "could not" not in text and "rules-only" not in text
    assert [c["path"] for p in v["proposals"]["pending"] for c in p["changes"] if c["path"].startswith("kpis/")] == ["kpis/Manager concentration"]
