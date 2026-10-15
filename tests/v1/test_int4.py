"""Card INT4 (Wave 3, offline): the admin line on Lumen's model-failure reply, M.clear_convo, the Tally quick flag, the landing question over the route."""
import pytest

from sh_platform.agents.protocols import ModelReply
from sh_platform.v1 import e6_trace
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import mem_agent as M
from tests.v1.test_lumen_w2 import ADMIN, hold  # noqa: F401 - fixture
from tests.v1.test_tally_w2 import cid, fresh_wording, loop_says, world  # noqa: F401 - fixtures
from tests.v1.test_anyone_may_start import app  # noqa: F401 - fixture
from tests.v1.test_i6a import CREDS, LEELA, client

LINE = "Note for the administrator: the OpenRouter model account is out of credit."


class Down:
    def complete(self, *a, **k):
        raise RuntimeError("no_credit")


def test_lumen_failure_reply_carries_the_admin_line_only_for_the_admin(hold, monkeypatch):  # noqa: F811
    plane, pid, did = hold
    monkeypatch.setattr(e6_trace, "model_trouble_note", lambda plane, viewer: LINE if "company_admin" in viewer.roles else None)
    out = L.ask(plane, ADMIN, pid, did, "Show me net worth per month.", model=Down())
    assert out["worded_by"] == "rules" and out["reply"].endswith(LINE)
    monkeypatch.setattr(e6_trace, "model_trouble_note", lambda plane, viewer: None)
    assert LINE not in L.ask(plane, ADMIN, pid, did, "Show me net worth per month.", model=Down())["reply"]


def test_clear_convo_empties_the_thread_and_keeps_memory(hold):  # noqa: F811
    plane, pid, did = hold
    M.learn(plane, ADMIN, "lumen", "I prefer blue lines.", f"{pid}:{did}")
    M.note(plane, ADMIN, "lumen", "c1", "person", "hello")
    assert M.convo(plane, ADMIN, "lumen", "c1")["turns"]
    M.clear_convo(plane, ADMIN, "lumen", "c1")
    assert M.convo(plane, ADMIN, "lumen", "c1")["turns"] == [] and M.focus(plane, ADMIN, "lumen", "c1") is None
    assert M.preferences(plane, ADMIN).get("lumen.color")


def test_tally_quick_gives_the_rules_analysis_without_a_model_call_then_the_model_follows(world, monkeypatch):  # noqa: F811
    monkeypatch.setenv("SH_MODEL_PROVIDER", "anthropic")
    seen: list = []
    loop_says(monkeypatch, "{timing_line} The break is on the case.", seen=seen)
    case = cid(world, "Cash differs", "Entity B")
    q = T.explain(world["plane"], world["V"]["Mei Chen"], case, quick=True)
    assert seen == [] and q["worded_by"] == "rules" and q["pending_model"] is True and q["summary"]
    full = T.explain(world["plane"], world["V"]["Mei Chen"], case)
    assert seen and full["pending_model"] is False
    assert T.explain(world["plane"], world["V"]["Mei Chen"], case, quick=True)["pending_model"] is False  # the kept wording is shown at once


def test_tally_route_passes_the_quick_flag(world, monkeypatch):  # noqa: F811
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sh_platform.v1 import e4a_routes as R
    got = []
    monkeypatch.setattr(T, "explain", lambda p, v, c, q=None, record=False, quick=False: got.append(quick) or {"ok": 1})
    monkeypatch.setattr(R, "_plane", lambda req: world["plane"])
    monkeypatch.setattr(R, "viewer_of", lambda req: world["V"]["Mei Chen"])
    a = FastAPI()
    a.include_router(R.router)
    c, case = TestClient(a), cid(world, "Cash differs", "Entity B")
    c.get(f"/api/v1/cases/{case}/tally?quick=1")
    c.get(f"/api/v1/cases/{case}/tally")
    assert got == [True, False]


@pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
def test_a_landing_question_over_the_route_is_marked_and_has_no_project(app):  # noqa: F811
    c = client(app, LEELA)
    v = c.post("/api/v1/intents/chat", json={"text": "Which intents do we have?"}).json()
    assert v["landing"] is True and v["project_id"] is None
    assert c.get("/api/v1/intents/open").json()["id"] != v["id"]
    v2 = c.post(f"/api/v1/intents/{v['id']}/chat", json={"text": "We need a monthly manager scorecard."}).json()
    assert not v2.get("landing") and v2["project_id"]


from sh_platform.v1 import n1_tally as T  # noqa: E402
