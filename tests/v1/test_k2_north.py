"""K2 wiring in North: the collision question goes into the context once, and the answer is stored by letter, never by a model id."""
from types import SimpleNamespace

from sh_platform.v1 import i6_chat as I6
from sh_platform.v1 import k2_map

FACT = {"concept": {"id": "c-nw", "name": "Net worth"}, "question": "Net worth already has two definitions in the company: Finance and Performance. Do you mean one of these, or is yours different?",
        "definitions": [{"id": "d-fin", "team": "Finance", "project": "P1", "definition": "all assets"},
                        {"id": "d-perf", "team": "Performance", "project": "P2", "definition": "liquid only"}]}
ME = SimpleNamespace(name="Leela")


def test_question_and_answer(monkeypatch):
    calls = []
    monkeypatch.setattr(k2_map, "collision_fact", lambda *a, **k: FACT)
    monkeypatch.setattr(k2_map, "record_choice", lambda plane, iid, kpi, ch: calls.append((kpi, ch)))
    sow = {"kpis": [{"name": "Net worth"}]}
    monkeypatch.setattr(I6, "register_names", lambda *a: None)
    ctx = I6._collision(None, "i1", sow, ME)["company_definitions_to_check"]
    assert isinstance(ctx, str) and "KPI Net worth" in ctx and "A: Finance" in ctx and "B: Performance" in ctx
    I6._record_collision(None, "i1", sow, ME, {"kpi": "Net worth", "answer": "different", "option": "b", "reason": "we exclude private funds"})
    assert calls == [("Net worth", {"choice": "variant_of", "variant_of": "d-perf", "reason": "we exclude private funds", "by": "Leela"})]
    I6._record_collision(None, "i1", sow, ME, {"kpi": "Net worth", "answer": "different", "option": "A"})  # no reason: nothing stored
    I6._record_collision(None, "i1", sow, ME, {"kpi": "Gross worth", "answer": "new"})  # not a KPI in the draft: nothing stored
    assert len(calls) == 1
    assert I6._collision(None, "i1", {"kpis": [{"name": "Net worth", "variant_of": "d-perf"}]}, ME) == {}  # placed: not asked again
