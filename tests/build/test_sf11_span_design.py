"""SF11: Span's target architecture, change note decisions, citations and design sections. Stub model, synthetic data, tmp planes."""
import inspect
import json

import pytest

from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.build import architecture as A
from sh_platform.build import design_doc
from sh_platform.build.agents import span_arch
from sh_platform.build.agents import span_design as SD
from sh_platform.build.agents.runtime import MODULE_ID, Runtime
from sh_platform.egress.policy import EgressPolicy
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer

ADMIN = Viewer("Janet Shaw", frozenset({"company_admin"}))
# two industries, the same code: (company, title, source, measure name)
PROBLEMS = {"family office": ("fo-co", "Valuation chase protocol", "Custodian statements", "Stale private fund valuations"),
            "asset management": ("am-co", "Fee reconciliation", "Mandate trades", "Unreconciled fee share")}
PASSAGE = "Keep the full history of a changing attribute in a type two dimension so every past report can be reproduced."


class _Model:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def complete(self, module_id, messages, tools=None):
        self.calls.append({"messages": list(messages), "tools": [t["name"] for t in tools or []]})
        return self.replies.pop(0)


class _Broken:
    def complete(self, module_id, messages, tools=None):
        raise RuntimeError("no route to the model")


class _Gateway:
    def internet_query(self, module_id, destination, query):
        return type("R", (), {"text": PASSAGE})()


def _reply(obj) -> ModelReply:
    return ModelReply(json.dumps(obj), [])


@pytest.fixture(params=sorted(PROBLEMS))
def plane(request, tmp_path, monkeypatch):
    company, title, source, measure = PROBLEMS[request.param]
    pl = PlaneStore(tmp_path).create(company)
    write_json_atomic(pl.path("build", "blueprint.json"), {
        "version": 1, "state": "signed", "infra": {"warehouse": "plane", "runner": "builtin"},
        "model": {"facts": [{"name": "fact_k1", "grain": "one row per item per month", "keys": [], "measures": ["K1"]}], "dimensions": []},
        "lineage": [{"measure": "K1", "source": source, "fields": ["amount"], "mart": "gold.k1.share", "transform": "share of items"}],
        "rules": [], "access": [{"mart": "gold.k1", "may_see": None}]})
    write_json_atomic(pl.path("build", "pipelines", "p1.json"), {"source": "p1", "title": source, "marts": ["gold.k1"], "expected": "Daily"})
    intent = {"id": "i1", "type": "initiative", "title": title, "question": f"Why does {measure.lower()} rise?", "state": "open",
              "people": {"organiser": "Janet Shaw"}, "secret_note": "NOT-FOR-SPAN", "refs": {},
              "build_handoff": {"by": {"name": "Janet Shaw"}, "at": "2026-10-01",
                                "catalogue": [{"id": "K1", "name": measure, "priority": "must"}],
                                "processes": [{"id": "p1", "name": "Monthly chase", "owner": "Harvey Ali"}],
                                "source_map": [{"id": "s1", "name": source, "zone": "p1", "strategic": True}]}}
    write_json_atomic(pl.path("intents", "i1", "intent.json"), intent)
    from sh_platform.intents import store as istore
    from sh_platform.profile import store as pstore
    monkeypatch.setattr(istore, "read_index", lambda p: [{"id": "i1", "type": "initiative"}])
    monkeypatch.setattr(istore, "read_intent", lambda p, i: intent if i == "i1" else None)
    monkeypatch.setattr(pstore, "raw", lambda p: {"people": {}, "systems": {}, "areas": {}})
    A.regenerate(pl, "blueprint_signed", "build/blueprint.json", "Grace Ward", [])
    ln = lambda t, mark="guessed", **kw: {"text": t, "mark": mark, "from": "build/blueprint.json lineage", "by": "Span", "at": "2026-10-01", **kw}
    write_json_atomic(pl.path("build", "changes", "C-0001.json"), {
        "id": "C-0001", "intent_id": "i1", "title": title, "state": "with_architect", "measures": ["K1"],
        "components": {"added": ["gold:k1"], "changed": [], "retired": []},
        "sections": {"why": [ln("Handed to Build")], "what_changes": [ln("Add gold.k1 (gold)", component="gold:k1")],
                     "decisions": [ln("gold.k1: rule line", placement="gold.k1", options=["Main file", "Restricted file"], chosen="Main file"),
                                   ln("other: rule line", placement="other", options=["X", "Y"], chosen="X")],
                     "build_steps": [], "tests": [], "run_book": [], "risks": [ln("The person's own risk", mark="stated")]}})
    return pl


def _rt(model, **kw) -> Runtime:
    return Runtime(model, company_id="co", company_name="Synthetic Co", industry="test", viewer=ADMIN, **kw)


GOOD = {"placement": "gold.k1", "options": ["Main file", "Restricted file"], "chosen": "Main file",
        "why": "the blueprint gives this mart no access list", "follows": "Query tools read it from the read-only copy", "provenance": ["gold:k1"]}


def test_span_arch_exposes_the_agreed_names():
    assert list(inspect.signature(span_arch.draft_change_note).parameters) == ["plane", "note_id", "rt", "by"]
    assert list(inspect.signature(span_arch.draft_record).parameters) == ["plane", "rt", "by"]


def test_decision_with_one_option_is_dropped_and_stated_lines_kept(plane):
    one = {**GOOD, "placement": "other", "options": ["X"], "chosen": "X"}
    unknown_ref = {**GOOD, "placement": "third", "provenance": ["made-up-record"]}
    m = _Model(_reply({"decisions": [GOOD, one, unknown_ref], "risks": ["The source may arrive late"]}))
    out = SD.draft_change_note(plane, "C-0001", _rt(m), "Aaron Lyle")
    dec = out["note"]["sections"]["decisions"]
    assert out["fallback"] is False and out["dropped"] == 2
    assert all(len(d["options"]) >= 2 for d in dec)
    by_place = {d["placement"]: d for d in dec}
    assert "because the blueprint gives this mart no access list" in by_place["gold.k1"]["text"]
    assert by_place["other"]["text"] == "other: rule line" and "third" not in by_place  # the dropped one leaves the rule line
    risks = out["note"]["sections"]["risks"]
    assert risks[0]["text"] == "The person's own risk" and risks[0]["mark"] == "stated" and risks[-1]["by"] == "Span"
    assert json.loads(plane.path("build", "changes", "C-0001.json").read_text())["sections"]["decisions"][0]["text"] == "gold.k1: rule line"  # not saved


def test_citation_kept_only_when_the_passage_exists(plane):
    pol = EgressPolicy(plane)
    pol.set_internet(MODULE_ID, True)
    pol.set_internet_hosts(["guidance.example.org"])
    cites = [{"ref": "R-1", "quote": "every past report can be reproduced"}, {"ref": "R-1", "quote": "always copy every table to three regions"},
             {"ref": "R-7", "quote": "every past report can be reproduced"}]
    m = _Model(ModelReply("", [ToolCall("search_reference", {"query": "dimension history"})]), _reply({"decisions": [{**GOOD, "cites": cites}]}))
    out = SD.draft_change_note(plane, "C-0001", _rt(m, gateway=_Gateway()), "Aaron Lyle")
    assert "search_reference" in m.calls[0]["tools"]
    d = next(x for x in out["note"]["sections"]["decisions"] if x["placement"] == "gold.k1")
    assert d["cites"] == [{"source": "guidance.example.org", "passage_id": "R-1", "quote": "every past report can be reproduced"}]


def test_internet_off_lists_no_outside_tool_and_keeps_no_citation(plane):
    m = _Model(_reply({"decisions": [{**GOOD, "cites": [{"ref": "R-1", "quote": "every past report can be reproduced"}]}]}))
    out = SD.draft_change_note(plane, "C-0001", _rt(m), "Aaron Lyle")
    assert "search_reference" not in m.calls[0]["tools"]
    assert "R-1" not in m.calls[0]["messages"][0]["content"]  # the cite rule is not even in the prompt
    assert all(not x.get("cites") for x in out["note"]["sections"]["decisions"])


def test_invalid_target_is_not_saved_and_the_previous_stays(plane):
    good = {"placements": [{"id": "gold-history", "kind": "gold", "label": "History mart", "view": "data", "interfaces": [{"to": "gold:k1", "kind": "reads"}]}],
            "lines": ["One new mart beside the existing one."]}
    first = SD.draft_target(plane, _rt(_Model(_reply(good))), "i1")
    assert first["saved"] and SD.target_draft(plane)["placements"][0]["id"] == "gold-history"
    for bad in ({"placements": [{"id": "x", "kind": "spaceship", "label": "X"}]},
                {"placements": [{"id": "y", "kind": "gold", "label": "Y", "interfaces": [{"to": "nowhere"}]}]},
                {"placements": [{"id": "gold:k1", "kind": "gold", "label": "Clash"}]},
                {"placements": [{"id": "gold-k77", "kind": "gold", "label": "An untraceable digit the guard rewrites"}]}):
        r = SD.draft_target(plane, _rt(_Model(_reply(bad))), "i1")
        assert not r["saved"] and r["errors"] and r["message"].startswith("The diagram could not be drawn")
        assert SD.target_draft(plane)["placements"][0]["id"] == "gold-history"


def test_target_payload_carries_the_hand_off_and_nothing_else_from_the_intent(plane):
    m = _Model(_reply({"placements": [], "lines": []}))
    SD.draft_target(plane, _rt(m), "i1")
    payload = json.loads(m.calls[0]["messages"][1]["content"])["context"]
    assert payload["charters"][0]["title"] and payload["charters"][0]["question"].startswith("Why does")
    assert payload["measures"][0]["code"] == "K1" and payload["processes"] == [{"name": "Monthly chase"}]
    assert payload["sources"][0]["quadrant"] and payload["sources"][0]["strategic"] is True
    text = json.dumps(payload)
    assert "NOT-FOR-SPAN" not in text and "Harvey Ali" not in text and "organiser" not in text and "2026-10-01" not in text


def test_no_model_or_failed_call_gives_the_rule_based_draft(plane):
    for model in (None, _Broken()):
        t = SD.draft_target(plane, _rt(model), "i1")
        assert t["fallback"] and t["message"] == "Span could not reach the model. This is the rule-based draft." and "gold:k1" in t["projection"]
        n = SD.draft_change_note(plane, "C-0001", _rt(model), "Aaron Lyle")
        assert n["fallback"] and n["note"]["sections"]["decisions"][0]["text"] == "gold.k1: rule line"
        d = SD.draft_design(plane, _rt(model))
        assert d["fallback"] and d["message"] == design_doc.SPAN_SENTENCE and d["doc"]["drafted"]["fallback"] is True
    assert SD.draft_change_note(plane, "../C-0001", _rt(None), "x") is None and SD.draft_change_note(plane, "C-0099", _rt(None), "x") is None


def test_design_sections_filled_and_stated_lines_kept_on_redraft(plane):
    reply = {"purpose": ["This work answers the charter question."], "target": ["One mart per measure."], "model": ["A star with one fact."],
             "decisions": [GOOD, {**GOOD, "options": ["Only one"]}], "risks": ["Late files delay the mart."]}
    out = SD.draft_design(plane, _rt(_Model(_reply(reply))))
    doc = out["doc"]
    assert not out["fallback"] and doc["sections"]["purpose"][0]["text"] == "This work answers the charter question."
    assert [d["placement"] for d in doc["sections"]["decisions"]] == ["gold.k1"]
    assert set(doc["specs"]) == {"current", "target", "delta"} and out["spec_errors"] == []
    design_doc.edit_line(plane, "purpose", 0, "Aaron's own purpose", "Aaron Lyle")
    again = SD.draft_design(plane, _rt(_Model(_reply({**reply, "purpose": ["A new guess."]}))))["doc"]
    assert again["sections"]["purpose"][0] == {**again["sections"]["purpose"][0], "text": "Aaron's own purpose", "mark": "stated"}
    assert "A new guess." in [x["text"] for x in again["sections"]["purpose"]]


def test_design_waits_for_a_change_note(tmp_path):
    empty = PlaneStore(tmp_path).create("empty-co")
    out = SD.draft_design(empty, _rt(None))
    assert out["doc"] is None and out["message"] == design_doc.EMPTY
