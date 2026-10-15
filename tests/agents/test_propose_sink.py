"""SF01: the propose sink. A propose tool only checks arguments; the loop collects; nothing is written."""
import json

import pytest

from conftest import StubGate, StubModel
from sh_platform.agents.loop import run_agent
from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.agents.registry import ToolRefused, ToolRegistry
from sh_platform.build.agents.read_tools import check_proposal

GOOD = {"title": "Keep fund manager history", "what": "Slowly changing type 2 on the fund dimension.", "why": "Managers change.",
        "technique": "scd2", "subject": "fund dimension", "effort": "small",
        "evidence": {"counts": [{"label": "funds changed manager", "value": 214, "group_size": 1180}], "fields": ["manager"], "queries": []},
        "impact": {"contracts": ["build/pipelines/trades.json"], "marts": ["gold.k12"], "dashboards": []},
        "alternatives": [{"option": "Type 1", "why_not": "Loses the history."}], "cites": []}


def _reg():
    r = ToolRegistry(StubGate(("acme", "m4_build")))
    r.register("m4_build", "propose", lambda kind, args: check_proposal("span", kind, args), read_only=False, proposes=True,
               description="d", parameters={"kind": "string", "args": "object"})
    return r


def test_registry_still_refuses_write_tools():
    r = ToolRegistry(StubGate())
    with pytest.raises(ToolRefused):
        r.register("m", "write", lambda: None, read_only=False, description="d", parameters={})
    with pytest.raises(ToolRefused):
        r.register("m", "both", lambda: None, read_only=True, proposes=True, description="d", parameters={})
    with pytest.raises(ToolRefused):
        r.register("m", "out", lambda: None, read_only=False, proposes=True, outside=True, description="d", parameters={})


def test_valid_proposal_collected_and_nothing_written(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    m = StubModel(ModelReply("", [ToolCall("propose", {"kind": "model_change", "args": GOOD})]), ModelReply("Filed one.", []))
    res = run_agent(m, _reg(), "acme", "m4_build", "Span", "You draft.", {}, "Suggest.")
    assert res.status == "done" and len(res.proposals) == 1
    p = res.proposals[0]
    assert p["kind"] == "model_change" and p["args"]["subject"] == "fund dimension" and p["args"]["evidence"]["counts"][0]["value"] == 214
    assert "outside_seen" not in p
    assert json.loads(m.calls[1]["messages"][-1]["content"]) == {"filed": "waiting for a person"}
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("kind,args", [
    ("model_change", {**GOOD, "to": "Grace Ward"}),                          # unknown key: the addressee is never the agent's choice
    ("incident_note", GOOD),                                                 # not Span's kind
    ("delete_everything", GOOD),
    ("model_change", {**GOOD, "what": "x" * 2001}),
    ("model_change", {**GOOD, "evidence": {"counts": [{"label": "few", "value": 3, "group_size": 3}]}}),
    ("model_change", {**GOOD, "evidence": {"rows": [["a"]]}}),
    ("model_change", {**GOOD, "effort": "huge"}),
    ("model_change", {k: v for k, v in GOOD.items() if k != "why"}),
])
def test_bad_proposal_refused(kind, args):
    m = StubModel(ModelReply("", [ToolCall("propose", {"kind": kind, "args": args})]), ModelReply("Tried.", []))
    res = run_agent(m, _reg(), "acme", "m4_build", "Span", "You draft.", {}, "Suggest.")
    assert res.proposals == [] and res.refusals == ["propose"]
    last = m.calls[1]["messages"][-1]  # SF09b: one plain line back, never the refused call's arguments
    assert last["role"] == "user" and last["content"].startswith("Your call to propose was refused (") and "tool_calls" not in json.dumps(m.calls[1]["messages"])


def test_wrong_top_level_arguments_refused():
    with pytest.raises(ToolRefused):
        _reg().call("acme", "m4_build", "propose", {"kind": "model_change", "args": GOOD, "extra": 1})


def test_an_object_sent_as_json_text_is_read_back_and_still_checked():
    """SF14d safety net: a provider that sends `args` as JSON text gets it parsed before the tool's own check, which is not weakened."""
    assert _reg().call("acme", "m4_build", "propose", {"kind": "model_change", "args": json.dumps(GOOD)})["args"]["title"] == GOOD["title"]
    for bad in (json.dumps({**GOOD, "what": ""}), "{not json", json.dumps([GOOD]), "[" * 5000):
        with pytest.raises(ToolRefused):
            _reg().call("acme", "m4_build", "propose", {"kind": "model_change", "args": bad})
