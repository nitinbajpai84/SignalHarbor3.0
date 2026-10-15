"""V5W-7 fast chat: fixed replies, classifier, answer cache, figure answers, router hook, server-sent events. Stub models only; latency asserted."""
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from sh_platform.agents.loop import run_agent
from sh_platform.agents.protocols import ModelReply
from sh_platform.agents.registry import ToolRegistry
from sh_platform.v1 import chat_fastpath as FP
from sh_platform.v1 import router as R


class Gate:
    def __init__(self, on=True):
        self.on = on

    def is_enabled(self, company_id, module_id):
        return self.on


class Model:
    def __init__(self, text="The cash balance is held in the custody account."):
        self.calls, self.text = 0, text

    def complete(self, module_id, messages, tools=None):
        self.calls += 1
        return ModelReply(text=self.text)


class NoModel:
    def complete(self, *a, **k):
        raise AssertionError("a model was called")


def ask(model, q, *, on=True, system="You are North.", ctx=None, fast=None, agent="North"):
    return run_agent(model, ToolRegistry(Gate(on)), "acme", "m1_intent", agent, system, ctx or {}, q, fast=fast)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    FP.reset()
    monkeypatch.setattr(FP, "jev_key", lambda: "")
    yield
    FP.reset()


# ---- fixed replies ----
@pytest.mark.parametrize("agent", ["north", "span", "lumen", "flow", "tally"])
@pytest.mark.parametrize("q", ["Hi", "hello there!", "Good morning", "Thanks!", "thank you so much", "help", "What can you do?", "Who are you?"])
def test_fixed_reply_for_every_agent(agent, q):
    r = FP.fixed_reply(agent, q)
    assert r and not any(c.isdigit() for c in r)
    if q in ("Hi", "help", "Who are you?"):
        assert agent.capitalize() in r


def test_fixed_only_when_the_whole_message_is_small_talk():
    assert FP.fixed_reply("north", "thanks, now show me the nav") is None
    assert FP.fixed_reply("north", "hi what is the nav") is None
    assert FP.fixed_reply("unknown", "hi") is None


def test_fixed_reply_skips_the_model_and_is_fast():
    t = time.monotonic()
    res = ask(NoModel(), "Hello!")
    assert res.status == "done" and res.steps == 0 and "North" in res.text
    assert res.trace[0]["route"] == "fixed" and time.monotonic() - t < 0.2


def test_fixed_reply_in_json_mode_keeps_the_shape_callers_parse():
    res = ask(NoModel(), "thanks", system="Reply as JSON with a reply key.")
    assert json.loads(res.text)["reply"].startswith("You are welcome")


def test_nothing_is_served_when_the_module_is_off():
    res = ask(NoModel(), "hello", on=False, fast={"scope": "p"})
    assert res.status == "refused"


# ---- classifier ----
def test_classifier_rules_and_jev_only_for_the_unplaced():
    seen = []

    def jev(t):
        seen.append(t)
        return "fast"

    assert FP.classify("north", "hi").kind == "fixed"
    assert FP.classify("lumen", "why did returns fall last month?", jev=jev).kind == "strong"
    assert FP.classify("lumen", "which sources are late?", jev=jev).kind == "fast"
    assert seen == []
    r = FP.classify("lumen", "cash position tomorrow", jev=jev)
    assert r.kind == "fast" and r.by == "Jev" and seen == ["cash position tomorrow"]
    assert FP.classify("lumen", "cash position tomorrow", jev=lambda t: None).kind == "strong"


def test_classifier_orders_cache_and_figure_before_the_tier():
    facts = [{"label": "Open breaks", "value": 7, "group_size": 9}]
    assert FP.classify("tally", "how many open breaks?", facts=facts).kind == "figure"
    assert FP.classify("tally", "how many open breaks?", facts=facts, cached=True).kind == "cache"


def test_jev_is_off_without_a_key_and_sees_only_masked_text():
    assert FP.jev_tier("cash position tomorrow") is None
    assert FP._mask("mail ann@x.com about 1,200 USD") == "mail x about #,### USD"
    assert len(FP._mask("a" * 900)) == 200


def test_jev_answers_are_used_only_when_confident():
    class Pick:
        def __init__(self, choice, conf):
            self.choice, self.confidence = choice, conf

    class Res:
        def __init__(self, p):
            self.choices = {"tier": p}

    class Client:
        def __init__(self, p):
            self.p = p

        def system_one(self, state, questions):
            assert set(state) == {"question"}
            return Res(self.p)

    assert FP.jev_tier("cash position tomorrow", Client(Pick("fast", 0.9))) == "fast"
    FP.reset()
    assert FP.jev_tier("cash position tomorrow", Client(Pick("fast", 0.3))) is None
    FP.reset()
    assert FP.jev_tier("cash position tomorrow", Client(Pick("other", 0.9))) is None


def test_router_hook_sends_a_short_lookup_to_the_fast_tier():
    assert R.pick_tier("lumen", "answer", {"text": "which sources are late?"}) == "fast"
    assert R.pick_tier("lumen", "answer", {"text": "why did returns fall and what should we change?"}) == "specialist"
    assert R.pick_tier("lumen", "answer", {"text": "which sources are late?", "retry": True}) == "manager"
    assert R.pick_tier("span", "plan", {"text": "which sources are late?"}) == "specialist"
    assert R.pick_tier("lumen", "answer", {"text": "which sources are late?", "files": True}) == "specialist"


# ---- figure answer ----
def test_figure_from_recorded_facts_without_a_model():
    facts = [{"label": "Open breaks", "value": 7, "group_size": 9}, {"label": "Closed breaks", "value": 40, "group_size": 9}]
    res = ask(NoModel(), "How many open breaks are there?", ctx={"facts": facts})
    assert res.text == "Open breaks: 7." and res.status == "done"


def test_figure_needs_one_certain_fact_with_a_big_enough_group():
    two = [{"label": "Open breaks", "value": 7, "group_size": 9}, {"label": "Open breaks", "value": 8, "group_size": 9}]
    small = [{"label": "Open breaks", "value": 7, "group_size": 3}]
    assert FP.figure_answer("How many open breaks?", two) is None
    assert FP.figure_answer("How many open breaks?", small) is None
    assert FP.figure_answer("How many open breaks?", [{"label": "text", "value": "7", "group_size": 9}]) is None


# ---- cache ----
def test_second_ask_is_a_cache_hit_and_fast():
    m, f = Model(), {"scope": "ann|analyst|p1"}
    first = ask(m, "What is held in the custody account?", fast=f)
    t = time.monotonic()
    again = ask(m, "what is held in the custody account", fast=f)
    assert m.calls == 1 and again.text == first.text and again.trace[0]["route"] == "cache" and time.monotonic() - t < 0.2


def test_cache_key_holds_scope_and_data_version():
    m = Model()
    q = "What is held in the custody account?"
    ask(m, q, fast={"scope": "ann"})
    ask(m, q, fast={"scope": "bob"})
    assert m.calls == 2  # another person's scope never reads ann's answer
    ask(m, q, fast={"scope": "ann"})
    assert m.calls == 2
    FP.bump("acme")  # a pipeline run or new data
    ask(m, q, fast={"scope": "ann"})
    assert m.calls == 3


def test_new_files_in_the_warehouse_move_the_data_version(tmp_path, monkeypatch):
    from sh_platform.settings import Settings
    monkeypatch.setattr("sh_platform.settings.load_settings", lambda *a, **k: Settings(data_root=str(tmp_path)))
    (tmp_path / "acme" / "warehouse").mkdir(parents=True)
    a = FP.data_version("acme")
    (tmp_path / "acme" / "warehouse" / "company.duckdb").write_bytes(b"x")
    assert FP.data_version("acme") != a


def test_no_scope_no_cache_and_follow_ups_never_cached():
    m = Model()
    ask(m, "What is held in the custody account?")
    ask(m, "What is held in the custody account?")
    assert m.calls == 2
    f = {"scope": "ann"}
    ask(m, "and what about last year then", fast=f)
    ask(m, "and what about last year then", fast=f)
    assert m.calls == 4


def test_guard_replaced_or_json_answers_are_not_cached():
    m = Model("The balance is 123456 USD.")  # a figure no record holds: the guard rewrites it
    f = {"scope": "ann"}
    ask(m, "What is held in the custody account?", fast=f)
    ask(m, "What is held in the custody account?", fast=f)
    assert m.calls == 2
    j = Model('{"reply": "ok"}')
    ask(j, "What is held in the custody account?", fast=f, system="Reply as JSON.")
    ask(j, "What is held in the custody account?", fast=f, system="Reply as JSON.")
    assert j.calls == 2


# ---- server-sent events ----
def _app(status=200, body=None):
    app = FastAPI()

    @app.post("/api/v1/consume/chat")
    def chat():
        return JSONResponse(body if body is not None else {"reply": "Open breaks are seven today and two are older than a week."}, status_code=status)

    @app.post("/api/v1/consume/other")
    def other():
        return {"reply": "x"}
    app.add_middleware(FP.ChatStreamMiddleware)
    return TestClient(app)


def _events(text):
    out = []
    for blk in text.strip().split("\n\n"):
        ev, data = blk.split("\n", 1)
        out.append((ev[7:], json.loads(data[6:])))
    return out


def test_stream_when_asked_with_the_same_json_at_the_end():
    r = _app().post("/api/v1/consume/chat", headers={"Accept": "text/event-stream"})
    ev = _events(r.text)
    assert r.headers["content-type"].startswith("text/event-stream")
    assert ev[0][0] == "start" and ev[-1][0] == "done"
    assert "".join(d["text"] for e, d in ev if e == "delta") == ev[-1][1]["reply"]


def test_plain_json_fallback_and_other_paths_untouched():
    c = _app()
    assert c.post("/api/v1/consume/chat").json()["reply"].startswith("Open breaks")
    assert c.post("/api/v1/consume/other", headers={"Accept": "text/event-stream"}).json() == {"reply": "x"}


def test_stream_carries_a_refusal_as_an_error_event():
    r = _app(403, {"error": "forbidden", "message": "No access."}).post("/api/v1/consume/chat", headers={"Accept": "text/event-stream"})
    assert _events(r.text)[-1] == ("error", {"status": 403, "error": "forbidden", "message": "No access."})


def test_stream_reads_the_last_agent_turn_of_a_thread():
    body = {"turns": [{"by": "person", "text": "hi"}, {"by": "span", "text": "Design is ready for your review."}]}
    ev = _events(_app(200, body).post("/api/v1/consume/chat", headers={"Accept": "text/event-stream"}).text)
    assert "Design" in ev[1][1]["text"] and ev[-1][1] == body


def test_router_hook_never_calls_jev_directly(monkeypatch):
    """Review: Jev is outside platform/egress, so the live router hook stays on the rules."""
    def boom(*a, **k):
        raise AssertionError("Jev called outside the egress gateway")
    monkeypatch.setattr(FP, "jev_tier", boom)
    assert FP.tier_for("cash position tomorrow") is None
    assert FP.tier_for("which sources are late?") == "fast"
