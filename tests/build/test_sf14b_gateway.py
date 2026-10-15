"""SF14b: every Span and Flow model call runs through the REAL egress gateway (structure check, rows check, vault, suppressed figures),
with only the network stubbed, and is sent, never refused. Lists of objects travel as text lines; the gateway's raw-rows rule is unchanged."""
import json

import pytest

from sh_platform.agents.loop import _figures
from sh_platform.agents.runs import RunRegistry
from sh_platform.build.agents import flow as F, read_tools as T, span_design as SD, span_model as SM, span_suggest as SS
from sh_platform.build.agents.runtime import Runtime
from sh_platform.egress.aggregates import SuppressedFigures
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import EgressGateway, _check_structure
from sh_platform.egress.model import EgressModelClient
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.rows import json_findings
from sh_platform.egress.vault import NameVault
from sh_platform.profile.view import Viewer
from tests.build.test_sf09_span_model import PLAN, plane as model_plane  # noqa: F401  (fixtures)
from tests.build.test_sf10_span_suggest import _plane as suggest_plane, no_owner  # noqa: F401  (no_owner: autouse fixture)
from tests.build.test_sf11_span_design import plane as design_plane  # noqa: F401  (fixture)
from tests.build.test_sf12_flow import _run, plane as flow_plane  # noqa: F401  (fixture)

HOST = "model.example.test"
TWO_ALTERNATIVES = ["option: Keep separate paths; why_not: two copies of the same logic",
                    "option: A transaction fact; why_not: the company records no events"]


class _Wire:
    """The network: records every body the gateway sent and plays scripted provider replies (the last one repeats)."""

    def __init__(self, *replies):
        self.replies, self.bodies = list(replies), []

    def __call__(self, url, body):
        self.bodies.append(body)
        return self.replies[min(len(self.bodies), len(self.replies)) - 1]


def _reply(text="Done.", calls=()):
    return json.dumps({"text": text, "tool_calls": [{"name": n, "arguments": a, "id": f"c{i}"} for i, (n, a) in enumerate(calls)]})


def _steps(batches, text: str) -> list[str]:
    """One tool per step (the loop runs six steps at most), then the closing text, for each run in turn."""
    return [r for b in batches for r in [*(_reply(calls=[c]) for c in b), _reply(text)]]


def _client(plane, wire) -> EgressModelClient:
    return EgressModelClient(EgressGateway(plane, NameVault(plane), EgressPolicy(plane), model_allowlist=[HOST], transport=wire,
                                           model_url=f"https://{HOST}/v1/messages"))


def _log(plane) -> list[dict]:
    p = plane.area("context") / "egress_log.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []


def _all_sent(plane, wire, at_least=1):
    log = _log(plane)
    blocked = [x["reason_code"] for x in log if x["decision"] == "blocked"]
    assert not blocked, f"the gateway refused: {blocked}"
    assert len(wire.bodies) >= at_least and sum(x["decision"] == "sent" for x in log) == len(wire.bodies)


# ---- the conversion itself -----------------------------------------------------------------------------------------------------------

def test_a_list_of_objects_is_refused_raw_and_sent_as_lines():
    ctx = {"rules": [{"rule": "the check on amount", "passed": False}, {"rule": "the check on day", "passed": True}],
           "facts": [{"label": "rows loaded", "value": 1180, "group_size": 1180}, {"label": "keys changed", "value": 214, "group_size": 1180}]}
    assert json_findings(json.dumps({"context": ctx}))[0] == "raw_rows"  # the gateway's rule, unchanged
    out = T.as_lines(ctx)
    assert out["rules"] == ["rule: the check on amount; passed: no", "rule: the check on day; passed: yes"]
    assert out["facts"] == ctx["facts"]  # the loop's number guard still reads the facts
    assert json_findings(json.dumps({"context": out}))[0] is None
    tables = {"model": {"facts": [{"name": "fact_a", "keys": ["a_key"]}, {"name": "fact_b", "keys": ["b_key"]}]}}
    assert T.as_lines(tables)["model"]["facts"] == ["name: fact_a; keys: a_key", "name: fact_b; keys: b_key"]  # only the top-level facts stay


def test_a_figure_keeps_its_group_and_a_figure_without_one_is_not_shown():
    ctx = {"x": [{"rule": "r1", "count": 12, "group_size": 1180}, {"rule": "r2", "count": 3}, {"label": "l", "value": 4}]}
    assert T.as_lines(ctx)["x"] == ["rule: r1; count: 12 (group of 1180)", "rule: r2; count: not shown", "label: l; value: not shown"]


def test_tool_figures_inside_lines_still_count_as_facts_for_the_guard():
    out = T.tool_lines({"items": [{"run_id": "a" * 32, "loaded": {"row_count": 1180, "group_size": 1180},
                                   "rules": [{"rule": "r", "passed": False, "count": 12, "group_size": 1180}]},
                                  {"run_id": "b" * 32, "loaded": {"available": False}, "rules": []}], "truncated": False})
    assert out["items"][0] == f"run_id: {'a' * 32}; loaded: (row_count: 1180 (group of 1180)); rules: (rule: r; passed: no; count: 12 (group of 1180))"
    facts: list = []
    _figures("read_runs", out, facts)
    structured = [f for f in facts if f["label"] != "text"]  # AQ1 SPM-3: the figures written in the tool's own lines count too ("text")
    assert {f["value"] for f in structured} == {1180, 12} and all(f["group_size"] == 1180 for f in structured)
    assert {"1180", "12"} <= {f["value"] for f in facts if f["label"] == "text"}
    assert json_findings(json.dumps(out))[0] is None


def test_alternatives_and_cites_written_as_lines_are_accepted_by_the_propose_tool():
    args = {"title": "t", "what": "w", "why": "y", "subject": "fact_fund_month", "alternatives": TWO_ALTERNATIVES,
            "cites": ["source: pack; passage_id: scd-2"]}
    got = T.check_proposal("span", "model_change", args)["args"]
    assert got["alternatives"][0] == {"option": "Keep separate paths", "why_not": "two copies of the same logic"}
    assert got["cites"] == [{"source": "pack", "passage_id": "scd-2"}]
    with pytest.raises(T.ToolRefused):
        T.check_proposal("span", "model_change", {**args, "alternatives": ["just words"]})


# ---- Flow through the real gateway -------------------------------------------------------------------------------------------------

def test_flow_run_note_with_every_flow_tool_and_a_proposal_passes_the_gateway(flow_plane):
    run = _run(flow_plane)
    batches = [[("read_contracts", {}), ("read_runs", {"source": "trades"}), ("read_quarantine", {"source": "trades"}),
                ("read_alerts", {}), ("propose", {"kind": "model_change", "args": {
                    "title": "Grain", "what": "Redraft the grain", "why": "The check failed", "subject": "fact_trades",
                    "alternatives": TWO_ALTERNATIVES}})],
               [("read_dialect", {})]]
    wire = _Wire(*_steps(batches, "The run failed on its checks."))
    for _ in batches:
        note = F.explain_run(flow_plane, run["id"], Runtime(_client(flow_plane, wire), company_id=flow_plane.company_id), fresh=True)
        assert note["text"] == "The run failed on its checks." and not note["fallback"]
    _all_sent(flow_plane, wire, sum(len(b) + 1 for b in batches))
    sent = b"".join(wire.bodies).decode("utf-8")
    assert "read_runs" in sent and "(group of" in sent


def test_flow_incident_note_and_dialect_pass_the_gateway(flow_plane, monkeypatch):
    _run(flow_plane)
    flow_plane.path("build", "alerts.json").write_text(json.dumps({"alerts": [
        {"id": "trades:failed", "kind": "failed", "source": "trades", "state": "open", "tell": "Katie Menon", "opened": "2026-09-04"}]}),
        encoding="utf-8")
    wire = _Wire(_reply("The checks failed, so the file needs correcting."))
    rt = Runtime(_client(flow_plane, wire), company_id=flow_plane.company_id)
    assert F.incident_note(flow_plane, rt, "trades:failed")["fallback"] is False
    monkeypatch.setattr(T, "read_dialect", lambda pl, rt: {"state": "ready", "dialect": "snowflake", "message": "A draft.", "statements": [
        {"name": "silver.trades", "changed_constructs": ["strftime to to_char"]}, {"name": "gold.k1", "changed_constructs": ["date_trunc"]}]})
    assert F.explain_dialect(flow_plane, rt)["fallback"] is False
    _all_sent(flow_plane, wire, 2)


# ---- Span through the real gateway -------------------------------------------------------------------------------------------------

def test_span_review_with_every_span_tool_passes_the_gateway_and_files_the_run_id(tmp_path):
    pl = suggest_plane(tmp_path)
    sugg = {"subject": "fact_fund_month", "technique": "Periodic snapshot fact", "title": "Snapshot the fund month",
            "what": "Keep one snapshot row per fund per month.", "why": "590 funds are read at month end.",
            "evidence": {"counts": [{"label": "keys", "value": 590, "group_size": 590}], "fields": ["fund_id"]},
            "impact": {"contracts": ["fund_register"], "marts": ["gold.k12"]}, "alternatives": TWO_ALTERNATIVES, "effort": "medium"}
    batches = [[("read_model", {}), ("read_contracts", {}), ("read_queries", {}), ("read_architecture", {"view": "all"}),
                ("propose", {"kind": "model_change", "args": sugg})],
               [("read_profile", {"source": "fund_register"}), ("read_change_rate", {"source": "fund_register", "key": "fund_id"}),
                ("read_decisions", {"topic": "fund"}), ("read_pack", {"topic": "slowly changing history"}),
                ("read_handoff", {"intent_id": "i1"})]]
    wire = _Wire(*_steps(batches, "I filed my suggestions."))
    rt = Runtime(_client(pl, wire), company_id="acme", company_name="Acme Family Office", recorder=RunRegistry(pl))
    out = SS.review(pl, rt)
    run_id = json.loads(pl.area("context").joinpath("run_registry.jsonl").read_text(encoding="utf-8").splitlines()[-1])["run_id"]
    assert not out["fallback"] and not SS.review(pl, rt)["fallback"]
    _all_sent(pl, wire, sum(len(b) + 1 for b in batches))
    mine = [p for p in out["proposals"] if p["title"] == "Snapshot the fund month"]
    assert mine and mine[0]["run_id"] == run_id and len(mine[0]["alternatives"]) == 2  # plan 3.3 point 8


def test_span_model_draft_passes_the_gateway(model_plane):
    wire = _Wire(json.dumps(PLAN))
    rt = Runtime(_client(model_plane, wire), company_id="lakeside-family-office", viewer=Viewer("Aaron Lyle", frozenset({"analyst"})))
    rec = SM.start(model_plane, rt, "Aaron Lyle", background=False)
    _all_sent(model_plane, wire)
    assert rec["state"] == "ready", rec


def test_span_target_change_note_and_design_pass_the_gateway(design_plane):
    wire = _Wire(json.dumps({"placements": [], "lines": [], "purpose": ["This work answers the charter question."]}))
    rt = Runtime(_client(design_plane, wire), company_id="co", company_name="Synthetic Co", industry="test")
    SD.draft_target(design_plane, rt, "i1")
    SD.draft_change_note(design_plane, "C-0001", rt, "Aaron Lyle")
    assert SD.draft_design(design_plane, rt)["fallback"] is False
    _all_sent(design_plane, wire, 3)


def test_the_structure_check_still_refuses_raw_rows():
    """The gateway's rule is kept exactly: a list of two objects in a message is still refused."""
    with pytest.raises(EgressBlocked) as e:
        _check_structure({"messages": [{"role": "user", "content": json.dumps([{"a": "x"}, {"a": "y"}])}]}, SuppressedFigures())
    assert e.value.reason_code == "raw_rows"


def test_flow_takes_a_reply_with_two_tool_calls_in_one_step_through_the_gateway(flow_plane):
    calls = [("read_runs", {"source": "trades"}), ("read_quarantine", {"source": "trades"})]
    run = _run(flow_plane)
    wire = _Wire(_reply(calls=calls), _reply("The run failed on its checks."))
    note = F.explain_run(flow_plane, run["id"], Runtime(_client(flow_plane, wire), company_id=flow_plane.company_id), fresh=True)
    _all_sent(flow_plane, wire, 2)
    assert note["text"] == "The run failed on its checks." and len(wire.bodies) == 2  # both calls ran in one step
    assert b"read_quarantine" in wire.bodies[1]


def test_the_gateway_takes_a_step_with_two_tool_calls(flow_plane):
    from sh_platform.agents.loop import run_agent
    calls = [("read_runs", {"source": "trades"}), ("read_quarantine", {"source": "trades"})]
    _run(flow_plane)
    wire = _Wire(_reply(calls=calls), _reply("Done."))
    rt = Runtime(None, company_id=flow_plane.company_id)
    run_agent(_client(flow_plane, wire), T.flow_registry(flow_plane, rt), flow_plane.company_id, "m4_build", "Flow", "s", {}, "q")
    _all_sent(flow_plane, wire, 2)


def test_a_refused_tool_call_leaves_its_reason_code_in_the_run_log_and_no_argument_value(flow_plane):
    """SF14c: a call refused by the tool's own argument check says why in the run row: tool name and reason code only."""
    from sh_platform.agents.loop import run_agent
    secret = "Jade Wong owes 4711"
    bad = ("propose", {"kind": "model_change", "args": {"title": secret, "what": "", "why": secret}})
    wire = _Wire(_reply(calls=[bad, ("nope", {"x": secret}), ("Jade Wong 4711", {})]), _reply("Done."))
    rt = Runtime(None, company_id=flow_plane.company_id)
    res = run_agent(_client(flow_plane, wire), T.flow_registry(flow_plane, rt), flow_plane.company_id, "m4_build", "Flow", "s", {}, "q",
                    recorder=RunRegistry(flow_plane))
    row = json.loads((flow_plane.area("context") / "run_registry.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert row["run_id"] == res.run_id
    assert row["refusals"] == [{"tool": "propose", "reason": "argument_check:what"},
                               {"tool": "nope", "reason": "not_available"},
                               {"tool": "unreadable", "reason": "not_available"}]
    assert "Jade" not in json.dumps(row) and "4711" not in json.dumps(row)
