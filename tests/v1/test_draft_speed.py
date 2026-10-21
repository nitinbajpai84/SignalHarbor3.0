"""draft-speed: Decision 1 drafts fast and in the open. The model is stubbed with delays: the parallel calls overlap, the brief's parts and
open questions are on the thread before the pass ends, and a message sent while a pass runs joins it instead of starting a second pass."""
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_harbor as H  # noqa: E402
from sh_platform.v1 import v3_judge as J  # noqa: E402
from sh_platform.v1 import v3_recipes as R  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

DELAY = 0.4


def _spans(log):
    return max(s for s, _ in log), min(e for _, e in log)


def test_the_binding_question_and_each_figures_judgement_run_at_once(monkeypatch):
    log = []

    def slow(*a, **k):
        t0 = time.monotonic()
        time.sleep(DELAY)
        log.append((t0, time.monotonic()))
        return None
    monkeypatch.setattr(R, "_ask", slow)
    monkeypatch.setattr(J, "judged", slow)
    kpis = [{"name": n, "definition": "made up for the test"} for n in ("Zorblat spread", "Quux carry", "Frob gap")]
    R.bind(SimpleNamespace(), object(), kpis)
    assert len(log) == 4  # the typed question and three judgements
    last_start, first_end = _spans(log)
    assert last_start < first_end, "the calls ran one after another"
    assert max(e for _, e in log) - min(s for s, _ in log) < 2 * DELAY  # four calls in about the time of one


def test_the_judges_two_models_are_asked_at_once(tmp_path, monkeypatch):
    log = []

    class Slow:
        def __init__(self, mid):
            self.model_id = mid

        def complete(self, module, messages):
            t0 = time.monotonic()
            time.sleep(DELAY)
            log.append((t0, time.monotonic()))
            return SimpleNamespace(text='{"answer": "A", "why": "it fits"}', usage=None)
    monkeypatch.setattr(J, "CLIENTS", lambda plane: (Slow("anthropic/x"), Slow("openai/y")))
    plane = PlaneStore(str(tmp_path)).create("acme")
    r = J.ask(plane, "recipe", "Which recipe?", ["net_worth", "none"], {"figure": "Net worth"}, "Pick the recipe.", "t-1", person=False)
    assert r["agreed"] and r["answer"] == "net_worth"
    last_start, first_end = _spans(log)
    assert len(log) == 2 and last_start < first_end


# ---- the draft pass, through the routes ------------------------------------------------------------------------------------------------

class Model:
    """The intent chat as Harbor calls it, with a gate on each North call so the test decides when a reply lands."""
    def __init__(self):
        self.calls, self.gates, self.lock, self.busy, self.most = [], {}, threading.Lock(), 0, 0
        self.sow = {"goal": {"line": "Can we meet the capital calls?"}}

    def gate(self, n):
        return self.gates.setdefault(n, threading.Event())

    def api(self, x, who, method, path, body=None, files=None, data=None, soft=False):
        if method == "GET" and path.endswith("/chat"):
            return {"sow": self.sow}
        if method != "POST" or not path.endswith("/chat"):
            return {}
        with self.lock:
            self.calls.append(dict(body or {}))
            n, self.busy = len(self.calls), self.busy + 1
            self.most = max(self.most, self.busy)
        try:
            assert self.gate(n).wait(10), f"call {n} was never let through"
            if n == 2:  # the fill
                self.sow = {"goal": {"line": "Can we meet the capital calls?", "readers": ["Anita"], "needed_by": "fifth business day"},
                            "sources": [{"name": "Administrator cash report"}]}
            return {"id": "ini-1", "turns": [{"by": "north", "text": f"Reply {n}."}], "sow": self.sow}
        finally:
            with self.lock:
                self.busy -= 1


@pytest.fixture()
def run(tmp_path, monkeypatch):
    m = Model()
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    monkeypatch.setattr(H, "SYNC", False)
    monkeypatch.setattr(H.Ctx, "api", lambda self, *a, **k: m.api(self, *a, **k))
    monkeypatch.setattr(H, "_gaps", lambda x, iid: [] if len(m.calls) >= 2 else ["Who reads the result", "When it is needed"])
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    pw = {ln.split()[0]: ln.split()[1] for ln in (data / "_control" / "seed_credentials.txt").read_text().splitlines() if ln.strip()}
    c = TestClient(create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")))
    email = "anita.rao.evergreen@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    yield c, m
    for e in list(m.gates.values()) + [m.gate(i) for i in range(1, 6)]:
        e.set()


def _until(cond, what):
    t0 = time.monotonic()
    while not cond():
        assert time.monotonic() - t0 < 10, f"timed out waiting for {what}"
        time.sleep(0.02)


def test_parts_and_questions_show_before_the_pass_ends_and_messages_join_the_running_pass(run):
    c, m = run
    t = c.post("/api/v3/threads", json={"text": "Can we meet the capital calls?"}).json()
    tid = t["id"]
    _until(lambda: len(m.calls) == 1, "the first North call")
    said = c.post(f"/api/v3/threads/{tid}/say", json={"text": "Anita reads it."}).json()  # while North reads the first message
    assert said["drafting"] and said["events"][-1]["text"].startswith("Got it. I am adding that")
    m.gate(1).set()
    _until(lambda: len(m.calls) == 2, "the fill")
    v = c.get(f"/api/v3/threads/{tid}").json()  # the fill is still running: the first draft and its questions are already there
    assert v["stage"] == "drafting" and v["drafting"]
    assert v["decision"]["gaps"] == ["Who reads the result", "When it is needed"]
    assert [ln["value"] for g in v["decision"]["brief"]["doc"] for ln in g["lines"] if ln["label"] == "The question"] == ["Can we meet the capital calls?"]
    assert "Anita reads it." in m.calls[1]["text"] and H.FILL in m.calls[1]["text"] # joined the fill: one call
    c.post(f"/api/v3/threads/{tid}/say", json={"text": "Monthly."})
    c.post(f"/api/v3/threads/{tid}/say", json={"text": "By the fifth."})
    m.gate(2).set()
    _until(lambda: len(m.calls) == 3, "the short redraft")
    v = c.get(f"/api/v3/threads/{tid}").json()
    assert any(ln["label"] == "Read by" and ln["value"] == "Anita" for g in v["decision"]["brief"]["doc"] for ln in g["lines"])  # the fill's parts, before the end
    m.gate(3).set()
    _until(lambda: tid not in H.PASSES, "the pass to close")
    assert m.calls[2]["text"] == "Monthly. By the fifth." and H.FILL not in m.calls[2]["text"]  # what came in during the fill: one short redraft, no fill
    assert len(m.calls) == 3 and m.most == 1  # never a second pass beside the first
    v = c.get(f"/api/v3/threads/{tid}").json()
    assert v["stage"] == "decision1" and not v["drafting"]
    assert [e["text"] for e in v["events"] if e["kind"] == "person"] == ["Can we meet the capital calls?", "Anita reads it.", "Monthly.", "By the fifth."]  # none lost
