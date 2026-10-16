"""Step 2, the judge (sh_platform/v1/v3_judge.py): two models of different families answer one small question; agreement is kept as an assumption,
disagreement becomes a Decision 2 question quoting both, a spent budget asks the person, the same input is never asked twice. Each of the five
worker judgements calls the judge. The models are stubbed; the office store, the hooks and the figure assumptions are real."""
import contextlib
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import v3_judge as J
from tests.v1 import test_v3_pdf as TP
from tests.v1.test_trade_intake import csv_file, env  # noqa: F401 - the trade fixture
from tests.v1.test_v3_pdf import office  # noqa: F401
from tests.v1.test_v3_recipes import BREAKS, plane as recipe_plane  # noqa: F401


class Model:
    def __init__(self, name, answer, why, calls):
        self.model_id, self.answer, self.why, self.calls = name, answer, why, calls

    def complete(self, module, messages, tools=None, suppressed=None):
        self.calls.append(messages)
        return SimpleNamespace(text=json.dumps({"answer": self.answer, "why": self.why}), usage={"tokens_in": 1000, "tokens_out": 100})


@pytest.fixture()
def plane(tmp_path):
    return PlaneStore(str(tmp_path)).create("acme")


@pytest.fixture()
def pair(monkeypatch):
    """Worker and checker stubs (qwen and openai families); the test sets box.a / box.b."""
    box = SimpleNamespace(calls=[], a="buy", b="buy")
    monkeypatch.setattr(J, "CLIENTS", lambda p: (Model("qwen/qwen3.7-flash", box.a, "worker", box.calls), Model("openai/gpt-oss-120b", box.b, "checker", box.calls)))
    return box


def ask(plane, side="bot", **k):
    return J.ask(plane, "trade_side", f"Is the side {side!r} a buy or a sell?", ["buy", "sell"], {"side": side}, "Buy when it means acquiring.", **k)


def test_two_models_that_agree_are_trusted_and_recorded_as_an_assumption(plane, pair):
    r = ask(plane, thread="t-1")
    assert r["agreed"] and r["answer"] == "buy" and [o["model"] for o in r["opinions"]] == ["qwen/qwen3.7-flash", "openai/gpt-oss-120b"] and r["cost"] > 0
    assert J.family("qwen/qwen3.7-flash") != J.family("openai/gpt-oss-120b") and "Evidence standard" in pair.calls[0][0]["content"]
    got = J.assumptions(plane, "t-1")
    assert got[0]["source"] == "Harbor (two models agreed)" and "worker" in got[0]["text"] and "checker" in got[0]["text"]  # quotes both opinions
    assert J.assumptions(plane, "t-2") == []


def test_two_models_that_disagree_raise_one_decision_2_question_with_both_opinions(plane, pair):
    pair.b = "sell"
    r = ask(plane, thread="t-1")
    assert not r["agreed"] and r["answer"] is None
    (q,) = J.pending(plane, "t-1")
    assert q["id"] == f"judge:{r['key']}" and len(q["options"]) == 3 and "buy: worker" in q["options"][0] and "sell: checker" in q["options"][1] and q["options"][2] == J.ELSE
    assert J.pending(plane, "t-2") == [] and J.assumptions(plane, "t-1") == []
    J.answer(plane, r["key"], q["options"][1])  # the person picks the checker's reading
    again = ask(plane, thread="t-1")
    assert again["agreed"] and again["answer"] == "sell" and again["by"] == "person" and J.pending(plane, "t-1") == []


def test_a_spent_budget_asks_the_person_and_never_guesses(plane, pair, monkeypatch):
    monkeypatch.setenv("SH_JUDGE_BUDGET_USD", "0.00001")
    assert ask(plane, thread="t-1")["agreed"]  # the first call fits, and costs more than the whole budget
    r = ask(plane, "sld", thread="t-1")
    assert r["stopped"] == "budget" and not r["agreed"] and r["answer"] is None and len(pair.calls) == 2  # no further model call
    (q,) = J.pending(plane, "t-1")
    assert "budget" in q["text"] and q["options"] == ["buy", "sell", J.ELSE]
    assert ask(plane, "sld", thread="t-2")["agreed"]  # another build has its own budget


def test_the_same_input_is_answered_from_the_cache(plane, pair):
    ask(plane)
    r = ask(plane)
    assert r["agreed"] and r["cached"] and r["cost"] == 0 and len(pair.calls) == 2
    pair.a = "sell"
    assert ask(plane)["answer"] == "buy" and len(pair.calls) == 2  # the first reply stands: the same call gives the same answer


def test_no_second_family_is_unavailable_without_a_question(plane):
    r = ask(plane)  # a test never reaches a live model
    assert r["agreed"] is False and r.get("unavailable") and J.pending(plane) == []


def test_judged_records_under_the_skill_and_returns_only_an_option(plane, pair):
    from sh_platform.v1 import v3_skills as S
    assert J.judged(plane, "trade_side", "Is the side 'bot' a buy or a sell?", ["buy", "sell"], {"side": "bot"}, "std", "t-9") == "buy"
    assert any(r["skill"] == "run.load-file" for r in S.runs(plane, "t-9"))


def test_agreed_judgements_reach_the_figure_assumptions(plane, pair):
    from sh_platform.v1 import v3_figstore as FS
    ask(plane, thread="t-1")
    assert [a["source"] for a in FS.assumptions([], None, {"id": "t-1"}, plane)] == ["Harbor (two models agreed)"] and FS.assumptions([], None, {"id": "t-1"}) == []


# ---- the five hooks: each calls the judge ------------------------------------------------------------------------------------------------

@pytest.fixture()
def calls(monkeypatch):
    def fake(plane, kind, question, options, evidence, standard, thread=None, person=True):
        fake.seen.append(SimpleNamespace(kind=kind, options=list(options), thread=thread, person=person))
        return fake.reply(options)
    fake.seen, fake.reply = [], (lambda options: None)
    monkeypatch.setattr(J, "judged", fake)
    return fake


def test_hook_1_file_recognition_tie_goes_to_the_judge(plane, calls):
    from sh_platform.v1 import v3_harbor as H
    th = {"id": "t-1", "stage": "working", "sources": ["Alpha ledger", "Beta ledger"]}
    assert H.recognise(plane, "ledger_2026-07.csv", [th])[0] == "question"  # both sources share the word "ledger": a tie, the judge could not settle it
    assert calls.seen[0].kind == "file" and calls.seen[0].options == ["Alpha ledger", "Beta ledger"] and calls.seen[0].thread == "t-1"
    calls.reply = lambda options: "Beta ledger"
    assert H.recognise(plane, "ledger_2026-07.csv", [th]) == ("recognised", "Beta ledger", "t-1")


def test_hook_2_the_pdf_amount_line_goes_to_the_judge_and_is_the_question_default(office, calls):
    calls.reply = lambda options: options[1]
    x, _ = TP.run_a(office, "t-2", ["FXF-2026-001_confirmation_2026-09-15.pdf"])
    assert calls.seen[0].kind == "amount_line" and calls.seen[0].person is False and len(calls.seen[0].options) == 2
    (q,) = [q for q in TP.V.questions(x) if q["id"].startswith("pdf:")]
    assert q["assumed"] == calls.seen[0].options[1]


def test_hook_3_a_fund_name_that_is_not_exact_goes_to_the_judge(office, calls, monkeypatch):
    from sh_platform.v1 import e2_intake as E, e2_match as M, wh
    from sh_platform.v1 import v3_harbor as H
    from sh_platform.v1 import v3_pdf as V
    _, plane, _ = office
    approved = []
    monkeypatch.undo()  # the office fixture stubs _prematch out; this test needs the real one (the judge stub is put back below)
    monkeypatch.setattr(J, "judged", calls)
    monkeypatch.setattr("sh_platform.v1.e1_write.org_id", lambda plane: "o")
    monkeypatch.setattr(E, "_source", lambda con, org, code: "s")
    monkeypatch.setattr(M, "resolve", lambda plane, name, sid: {"status": "proposed", "identifier_id": "i-1"})
    monkeypatch.setattr(M, "proposals", lambda plane: [{"id": "i-1", "name_in_file": "Evergreen Income Fund Two", "instrument_name": "Evergreen Income II"}])
    monkeypatch.setattr(wh, "connect", lambda plane: contextlib.nullcontext())
    monkeypatch.setattr(H, "_skill", lambda x, sid, text: contextlib.nullcontext({}))
    x = SimpleNamespace(plane=plane, th={"id": "t-3"}, api=lambda who, method, path, *a, **k: approved.append(path))
    calls.reply = lambda options: "same fund"
    V._prematch(x, [{"label": "Fund", "value": "Evergreen Income Fund Two"}])
    assert calls.seen[0].kind == "fund_match" and calls.seen[0].options == ["same fund", "different fund"]
    assert approved == ["/api/v1/evidence/aliases/i-1/approve"]  # agreed: approved like an exact match
    calls.reply, approved[:] = (lambda options: "different fund"), []
    V._prematch(x, [{"label": "Fund", "value": "Evergreen Income Fund Two"}])
    assert approved == []  # not agreed: stays proposed for a person


def test_hook_4_an_unusual_trade_side_goes_to_the_judge(env, calls):  # noqa: F811
    calls.reply = lambda options: "buy"
    r = env.load(csv_file(("T-1", "2026-07-06", "bot", "MRF", 100, 3000)), "trading_export_20260706.csv")
    assert calls.seen[0].kind == "trade_side" and calls.seen[0].options == ["buy", "sell"]
    assert r["rows_loaded"] == 1 and [(t["quantity_delta"], t["cash_amount"]) for t in env.rows()] == [(Decimal(100), Decimal(-3000))]
    calls.reply = lambda options: None  # no agreement: the row is held back with its reason, as before
    r = env.load(csv_file(("T-2", "2026-07-07", "sld", "MRF", 5, 10)), "trading_export_20260707.csv", "append")
    assert r["rows_loaded"] == 0


def test_hook_5_recipe_binding_by_meaning_goes_to_the_judge(recipe_plane, calls, monkeypatch):  # noqa: F811
    from sh_platform.v1 import v3_recipes as R
    monkeypatch.setattr(R, "_ask", lambda plane, model, ctx: None)
    kpis = [BREAKS[2]]  # the rules do not match it, only its meaning does
    calls.reply = lambda options: "cash_break"
    R.bind(recipe_plane, object(), kpis, "Every morning I check cash for each entity")
    assert calls.seen[0].kind == "recipe" and "cash_break" in calls.seen[0].options and "none" in calls.seen[0].options
    assert kpis[0]["built_from"] == "cash_break" and kpis[0]["built_from_by"] == R.SPAN
