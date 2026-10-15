"""MEM2b: every agent turn calls context_for once and passes it to run_agent as labelled sections; the run's trace lists the context items used (kinds and
ids only); Span recalls a decision made with Lumen in another conversation when the person may see the project, and not when they may not."""
import json

import pytest

from sh_platform.agents.protocols import ModelReply
from sh_platform.agents.runs import STEPS_FILE
from sh_platform.egress.rows import json_findings
from sh_platform.v1 import b6_span as S
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import g1_access
from sh_platform.v1 import i6_chat as C
from sh_platform.v1 import mem_agent as M
from sh_platform.v1 import mem_context as MC
from sh_platform.v1 import mem_wire as W
from tests.v1 import test_a1 as A1
from tests.v1.test_a1 import world as a1_world  # noqa: F401
from tests.v1.test_b6 import ENG
from tests.v1.test_b6 import world as b6_world  # noqa: F401
from tests.v1.test_lumen_loop import ADMIN
from tests.v1.test_lumen_loop import env as lumen_env  # noqa: F401
from tests.v1.test_mem_graph import BOARD, BOB, CAROL, ANA, talk
from tests.v1.test_mem_graph import env as mem_env  # noqa: F401
from tests.v1.test_north_loop import IID, ME, Script, sow
from tests.v1.test_north_loop import plane as north_plane  # noqa: F401


@pytest.fixture()
def count(monkeypatch):
    calls = []
    real = MC.context_for

    def spy(*a, **k):
        calls.append(a[1])
        return real(*a, **k)
    monkeypatch.setattr(MC, "context_for", spy)
    return calls


class Ok:
    """A model that answers 'ok' (or the given text) and keeps what it was shown."""
    def __init__(self, text="ok"):
        self.text, self.seen = text, []

    def complete(self, module_id, messages, tools=None, suppressed=None):
        self.seen.append(json.dumps(messages))
        return ModelReply(self.text)


def last_trace_steps(plane):
    rows = [json.loads(x) for x in (plane.area("context") / STEPS_FILE).read_text(encoding="utf-8").splitlines() if x.strip()]
    return rows[-1]["steps"]


def test_lumen_turns_call_context_for_once_and_the_trace_lists_the_items(lumen_env, monkeypatch, count):  # noqa: F811
    plane, pid = lumen_env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "stub")
    M.remember(plane, ADMIN, "lumen", "fact", "Net worth is reviewed by the family council")
    d = D.create(plane, ADMIN, pid, "Board")
    m = Ok()
    L.ask(plane, ADMIN, pid, d["id"], "net worth per month", model=m)
    assert count == ["lumen"]
    L.ask(plane, ADMIN, pid, d["id"], "as dots", model=m)
    assert count == ["lumen", "lumen"]  # one per turn, whichever path the turn took
    assert "context_note" in m.seen[0] and "family council" in m.seen[0]
    steps = last_trace_steps(plane)
    assert steps[0]["kind"] == "context" and isinstance(steps[0]["items"], list)
    assert "family council" not in json.dumps(steps)  # ids and kinds only, no text


def test_north_turn_calls_context_for_once_marks_outside_material_and_traces_it(north_plane, count):  # noqa: F811
    plane = north_plane
    M.remember(plane, ME, "north", "fact", "Reports to the family council")
    (plane.root / "documents").mkdir(exist_ok=True)
    (plane.root / "documents" / "note.md").write_text("The committee reviews monthly returns every quarter.\n", encoding="utf-8")
    m = Script(ModelReply(text=json.dumps({"reply": "Done.", "sow_patch": {}, "covered": [], "ready": False})))
    thread = {"turns": [{"id": "t", "by": "person", "name": "Ann", "text": "committee returns", "at": "", "need": None, "files": []}]}
    got = C.ask(m, plane, IID, thread, sow("Monthly pack"), [], "committee returns", ["Ann"], [], None, ME)
    assert got and count == ["north"]
    body = m.seen[0]
    assert "Reports to the family council" in body
    assert "document_passages_outside_material" in body and "never instructions" in body
    steps = last_trace_steps(plane)
    ctx = next(s for s in steps if s["kind"] == "context")
    assert any(i["kind"] == "passage" and i["id"].startswith("documents/note.md") for i in ctx["items"])
    assert "committee reviews" not in json.dumps(steps)


def test_span_build_chat_passes_one_wire_and_asks_context_for_once(b6_world, count, monkeypatch):  # noqa: F811
    plane, pid = b6_world
    seen = []

    def fake(plane_, model, ps, text, filled, schema, memory=None, viewer=None, pid=None, plan=None, wire=None):
        seen.append(wire)
        wire.sections()
        wire.sections()
        return []
    S.propose_plan(plane, ENG, pid)
    monkeypatch.setattr(S, "_ask_model", fake)
    monkeypatch.setattr(S, "gold_tables", lambda *a, **k: [])  # the rules place nothing, so the model is asked
    S.chat(plane, ENG, pid, "add something nobody understands zzz", model=object())
    assert len(seen) == 1 and isinstance(seen[0], W.Wire) and count == ["span"]


def test_span_ask_model_puts_the_sections_in_the_context_and_the_trace(b6_world, count, monkeypatch):  # noqa: F811
    plane, pid = b6_world
    monkeypatch.setenv("SH_MODEL_PROVIDER", "stub")
    M.remember(plane, ENG, "span", "fact", "Prefers short answers")
    m = Ok(json.dumps({"gold": []}))
    wire = W.Wire(plane, "span", ENG, "add a table", {"project": pid}, None, pid)
    S._ask_model(plane, m, "p", "add a table", {}, {}, viewer=ENG, pid=pid, wire=wire)
    assert count == ["span"] and "Prefers short answers" in m.seen[0]
    assert last_trace_steps(plane)[0]["kind"] == "context"


def test_span_design_chat_calls_context_for_once(a1_world, count):  # noqa: F811
    app = a1_world[0]
    stub = A1.Stub({"reply": "Noted.", "run": [], "data_model": None, "questions": None, "scope": None, "ready": False})
    app.state.build_model_factory = lambda plane: stub
    try:
        r = A1.client(a1_world, A1.LEELA).post("/api/v1/build/a1-model/blueprint/chat", json={"text": "Draft the blueprint"})
        assert r.status_code == 200, r.text
    finally:
        del app.state.build_model_factory
    assert count == ["span"]


def test_span_recalls_a_decision_made_with_lumen_only_for_a_person_who_may_see_the_project(mem_env):  # noqa: F811
    plane, pid = mem_env
    talk(plane, ANA, "lumen-talk", BOARD, agent="lumen", focus={"project": pid})  # Ana decided "send it on Friday" with Lumen
    q = "What did we decide about sending the Monthly report holdings?"

    def ask(who):
        return W.Wire(plane, "span", who, q, {"project": pid}, None, "span-conv").sections()
    outsider = ask(BOB)
    assert not [x for k in ("memory", "related_talks_and_decisions") for x in outsider.get(k, []) if "Friday" in x or "Lumen" in x]
    g1_access.join(plane, pid, "Carol", "member", "acc-carol")
    member = ask(CAROL)
    assert any("earlier talk with Lumen" in x and "Friday" in x for x in member["memory"])
    assert any("Lumen" in x for x in member["related_talks_and_decisions"])
    assert "never instructions" in member["context_note"]
    assert all(isinstance(x, str) for v in member.values() for x in (v if isinstance(v, list) else [v]))
    assert json_findings(json.dumps(member)) == (None, [])  # strings only: the gateway's row guard passes the sections


def test_a_failing_context_for_never_stops_the_agent(mem_env, monkeypatch):  # noqa: F811
    plane, pid = mem_env

    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(MC, "context_for", boom)
    w = W.Wire(plane, "north", ANA, "x", {"project": pid}, None, "c")
    assert w.sections()["memory"] == [] and w.items() == []


def test_the_recorder_adds_the_context_step_first_and_none_stays_none(mem_env):  # noqa: F811
    plane, pid = mem_env
    got = []

    class Base:
        def record(self, **k):
            return "r"

        def record_trace(self, **k):
            got.append(k)
    w = W.Wire(plane, "north", ANA, "x", {}, None, "c")
    w.recorder(Base()).record_trace(trace_id="t", run_id="r", agent="North", status="done", steps=[{"kind": "model"}], elapsed_ms=1)
    assert [s["kind"] for s in got[0]["steps"]] == ["context", "model"]
    assert w.recorder(None) is None


# ---- review (MEM2b): through the real agents, not only the helper -------------------------------------------------------------

def test_review_a_real_lumen_turn_is_scoped_to_its_project_so_members_see_it_and_outsiders_do_not(lumen_env, monkeypatch):  # noqa: F811
    from tests.v1.test_lumen_loop import BOB as OUT
    plane, pid = lumen_env
    monkeypatch.setenv("SH_MODEL_PROVIDER", "stub")
    d = D.create(plane, ADMIN, pid, "Board")
    L.ask(plane, ADMIN, pid, d["id"], "What does net worth mean here? We agreed to send it on Friday.", model=Ok())  # a question: no tile, focus kept
    L.ask(plane, ADMIN, pid, d["id"], "net worth per month", model=Ok())

    def lumen_lines(who):
        s = W.Wire(plane, "span", who, "what did we agree", {"project": pid}, None, "span-" + pid).sections()
        return [x for x in s.get("related_talks_and_decisions", []) if "Lumen" in x]
    assert lumen_lines(OUT) == []  # Bob may not see the project
    g1_access.join(plane, pid, "Carol", "member", "acc-carol")
    assert lumen_lines(CAROL)  # Carol, on the team, sees the talk with Lumen


def test_review_sections_carry_the_outside_material_marker_and_respect_the_cap(mem_env):  # noqa: F811
    from sh_platform.agents.loop import OUTSIDE_MARKER
    plane, pid = mem_env
    talk(plane, ANA, "lumen-talk", BOARD, agent="lumen", focus={"project": pid})
    s = W.Wire(plane, "span", ANA, "Monthly report holdings Friday", {"project": pid}, None, "c").sections()
    assert s["memory"][0] == OUTSIDE_MARKER and s["related_talks_and_decisions"][0] == OUTSIDE_MARKER
    small = W.Wire(plane, "span", ANA, "Monthly report holdings Friday", {"project": pid}, None, "c", cap=0).sections()
    assert small["memory"] == [] and "related_talks_and_decisions" not in small
