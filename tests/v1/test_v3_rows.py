"""r9 (sh_platform/v1/v3_rows.py, v3_judge wording, the persona's own files): Sofia was stuck at "12 mapping rows still need a person" because the
ready table Span designed after the rows were settled had 12 columns with no definition. Now clear columns settle through two agreeing models
(each an assumption), unclear ones become one Decision 2 question to the raiser, and the pack is always sent. Models are stubbed."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_judge as J
from sh_platform.v1 import v3_rows as R
from sh_platform.v1 import wh
from tools import seed_evergreen as EG

ROOT = Path(__file__).resolve().parents[2]
T = "gold_p_kpis"
SQL = f"create table {T} as select c.commitment_amount, c.currency from commitments c"


class Model:
    def __init__(self, name, answer, calls):
        self.model_id, self.answer, self.calls = name, answer, calls

    def complete(self, module, messages, tools=None, suppressed=None):
        self.calls.append(messages)
        return SimpleNamespace(text=json.dumps({"answer": self.answer, "why": "stub"}), usage={"tokens_in": 10, "tokens_out": 5})


@pytest.fixture()
def plane(tmp_path):
    EG.company(tmp_path)
    p = PlaneStore(str(tmp_path)).plane_for("evergreen").ensure()
    wh.use(p)
    return p


def pair(monkeypatch, a, b):
    box = SimpleNamespace(calls=[])
    monkeypatch.setattr(J, "CLIENTS", lambda p: (Model("qwen/qwen3.7-flash", a, box.calls), Model("openai/gpt-oss-120b", b, box.calls)))
    return box


def _x(plane):
    calls = []
    gold = [{"name": T, "purpose": "Monthly KPI values", "sql": SQL, "depends_on": ["commitments"], "grain": "", "keys": [], "kpis": [],
             "columns": [{"name": "commitment_amount", "type": "DECIMAL(18,2)", "definition": "Needs a definition"},
                         {"name": "currency", "type": "VARCHAR", "definition": "Needs a definition"}]}]
    rows = [{"id": "m-amt", "kind": "derived", "gold": f"{T}.commitment_amount", "needs_person": f"Define commitment_amount of {T}.", "resolved": False},
            {"id": "m-ccy", "kind": "derived", "gold": f"{T}.currency", "needs_person": f"Define currency of {T}.", "resolved": False},
            {"id": "m-src", "kind": "source", "gold": "commitments.id", "needs_person": "Map this sample to the model before the builder can use it.", "resolved": False}]

    def api(who, method, path, body=None, **kw):
        calls.append((who, method, path.split("/architecture")[-1], body))
        if method == "GET" and path.endswith("/pack"):
            return {"pack": {"state": "draft", "target": {"gold": gold}, "mapping": rows}, "versions": [{"version": 1}]}
        return {}
    th = {"id": "t-1", "pid": "prj-1", "iid": "ini-1", "started_by": "Sofia Reyes", "figures": [{"kpi": "Time-weighted return", "table": T}]}
    return SimpleNamespace(plane=plane, th=th, api=api, app=None, account_id=None), calls


def edits(calls, section=None):
    return [b for w, m, p, b in calls if m == "PUT" and (section is None or b["section"] == section)]


def test_clear_columns_settle_through_two_agreeing_models_and_each_is_an_assumption(plane, monkeypatch):
    box = pair(monkeypatch, "A", "yes")  # one names the letter, the other the option: the same pick
    x, calls = _x(plane)
    R.send(x)
    defs = {b["key"]: b["changes"]["definition"] for b in edits(calls, "gold_column")}
    assert defs[f"{T}.commitment_amount"] == "The commitment amount of the commitments row it comes from (commitments.commitment_amount), unchanged."
    resolved = {b["key"]: b for b in edits(calls, "mapping")}
    assert set(resolved) == {"m-amt", "m-ccy", "m-src"} and "two models" in resolved["m-amt"]["note"]  # the sample row is settled at intake, as before
    assert edits(calls, "gold_remove") == [] and R.questions(x) == []
    assert [(w, m, p) for w, m, p, _ in calls if m == "POST"] == [("leo", "POST", "/pack/submit"), ("anita", "POST", "/pack/approve")]
    assert len(J.assumptions(plane, "t-1")) == 2  # each settled column is recorded as an assumption
    assert box.calls[0] == box.calls[1]  # the checker sees the very same system text and evidence as the worker


def test_unclear_columns_become_one_decision_2_question_to_the_raiser_and_the_pack_still_goes(plane, monkeypatch):
    pair(monkeypatch, "yes", "no")
    x, calls = _x(plane)
    R.send(x)
    assert [b["key"] for b in edits(calls, "gold_remove")] == [T]  # held out, so the rest is sent: never a dead end
    assert ("anita", "POST", "/pack/approve") in [(w, m, p) for w, m, p, _ in calls]
    (q,) = R.questions(x)
    assert q["id"] == R.QID and q["text"].startswith("For Sofia Reyes") and "commitment_amount" in q["text"] and "currency" in q["text"]
    assert q["options"] == [R.USE, R.LEAVE] and J.pending(plane, "t-1") == []  # one question, not one per column
    assert "Time-weighted return" in x.th["figure_notes"] and "Sofia Reyes" in x.th["figure_notes"]["Time-weighted return"]
    calls.clear()
    R.answer(x, R.USE)
    (back,) = edits(calls, "gold_add")
    assert back["key"] == T and set(back["changes"]["definitions"]) == {"commitment_amount", "currency"} and back["changes"]["sql"] == SQL
    assert ("anita", "POST", "/pack/approve") in [(w, m, p) for w, m, p, _ in calls] and R.questions(x) == []
    assert "Time-weighted return" not in x.th["figure_notes"]


def test_leaving_the_tables_out_says_why_and_they_are_not_designed_again(plane, monkeypatch):
    pair(monkeypatch, "cannot tell", "cannot tell")  # both abstain: no answer, the person decides
    x, calls = _x(plane)
    R.send(x)
    R.answer(x, R.LEAVE)
    assert R.questions(x) == [] and "Left out at Decision 2" in x.th["figure_notes"]["Time-weighted return"]
    monkeypatch.setattr(F, "kpis_of", lambda plane, iid: [{"name": "Time-weighted return", "definition": "TWR"}])
    monkeypatch.setattr(F, "design", lambda *a: pytest.fail("a table the person left out is not designed again"))
    monkeypatch.setattr(F, "table_rows", lambda plane, copy=False: {})
    x.api = lambda who, method, path, body=None, **kw: {"pack": {"state": "approved", "target": {"gold": []}}}
    F.cover(x, "loaded")


def test_a_fixed_number_is_a_placeholder_not_a_figure():
    assert F.null_columns("create table g as select c.*, 12 as time_weighted_return, 100 as allocation_drift from commitments c") == {"time_weighted_return", "allocation_drift"}


def test_options_are_lettered_in_plain_words_with_the_kinds_standard_and_worked_examples(plane, monkeypatch):
    box = pair(monkeypatch, "B", "b")
    r = J.ask_kind(plane, "recipe", {"figure": "Unmatched FX", "definition": "Sum of variances", "formula": "sum"}, ["fx_confirmation_variance", "none"], {"x": 1},
                   thread="t-1", describe={"none": "No recipe here computes this figure"})
    assert r["agreed"] and r["answer"] == "none"
    system, user = box.calls[0][0]["content"], json.loads(box.calls[0][1]["content"])
    assert "Worked examples" in system and "background only" in system and user["options"] == {"A": "fx_confirmation_variance", "B": "No recipe here computes this figure"}
    assert user["question"].startswith("Which recipe computes the figure 'Unmatched FX'")


def test_the_held_out_set_spans_the_five_kinds_and_its_cases_are_not_the_worked_examples():
    data = json.loads((ROOT / "tests" / "v1" / "fixtures" / "judge_heldout.json").read_text(encoding="utf-8"))
    kinds = {c["kind"] for c in data["cases"]}
    assert 10 <= len(data["cases"]) <= 20 and kinds == {"file", "amount_line", "fund_match", "trade_side", "recipe"}
    examples = " ".join(c for g in J.GUIDES.values() for c, _, _ in g["examples"]).lower()
    for c in data["cases"]:
        for v in c["subject"].values():
            assert len(str(v)) < 12 or str(v).lower() not in examples, c["id"]


def test_the_persona_keeps_its_state_and_report_where_the_run_says(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("v3_persona", ROOT / "docs" / "test" / "uc-live" / "uc6-scripts" / "v3_persona.py")
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)
    monkeypatch.delenv("UC6_STATE", raising=False)
    monkeypatch.delenv("UC6_REPORT", raising=False)
    assert P.paths("ops_clerk") == (Path("D:/Temp/sh3-team-ops_clerk.json"), Path("D:/Temp/sh3-team/ops_clerk.json"))  # today's defaults
    monkeypatch.setenv("UC6_STATE", str(tmp_path / "s.json"))
    monkeypatch.setenv("UC6_REPORT", str(tmp_path / "r.json"))
    assert P.paths("ops_clerk") == (tmp_path / "s.json", tmp_path / "r.json")
