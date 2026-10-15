"""M1-07 Nira as coordinator: she runs only through the kernel agent runtime and the ModelClient protocol, answers
from the prepared rules only, refuses opinions on the substance, writes every run to the run registry with no
content, and her replies pass the plain-words check. The model is the evals harness stub."""
import json
import re
from pathlib import Path

import pytest

from m1_kit import BASE
from modules.m1_intent.agent import nira
from sh_platform.agents.protocols import ModelReply
from test_m1_briefing_kit import make_world, seated, session_at, use_model


class Spy:
    """A ModelClient that remembers what it was shown."""

    def __init__(self, text="Here is the answer from the rules."):
        self.text, self.seen = text, []

    def complete(self, module_id, messages, tools=None):
        self.seen.append({"module": module_id, "messages": messages, "tools": tools})
        return ModelReply(self.text)

    @property
    def system(self):
        return self.seen[-1]["messages"][0]["content"]

    @property
    def context(self):
        return json.loads(self.seen[-1]["messages"][1]["content"])["context"]

    @property
    def question(self):
        return json.loads(self.seen[-1]["messages"][1]["content"])["question"]


@pytest.fixture
def w(tmp_path):
    return make_world(tmp_path)


def ask(c, sid, kind="ask", question="Can I write more than one note?"):
    body = {"kind": kind, **({"question": question} if question is not None else {})}
    return c.post(f"{BASE}/sessions/{sid}/nira", json=body)


# ---- she answers from the rules only ----------------------------------------------------------------------------
def test_her_context_holds_the_rules_and_the_stage_and_nothing_else_of_the_company(w):
    org = w.login("org", "co-a")  # industry_a has a pack with problems: none of it may reach her
    sid = session_at(w, org, "co-a", "briefing", purpose="Find our shared worries")
    spy = use_model(w, Spy()
)
    r = ask(org, sid)
    assert r.status_code == 200, r.text
    ctx = spy.context
    assert ctx["company"] == {"name": "Co-A", "industry": "industry_a"}
    assert ctx["stage"] == "briefing" and ctx["suggestions"] == [] and ctx["facts"] == [] and ctx["documents"] == []
    assert "empty_state" not in ctx
    assert ctx["rules"]["purpose"] == "Find our shared worries"
    assert "industry_a question" not in json.dumps(spy.seen) and "industry_a action" not in json.dumps(spy.seen)
    assert spy.seen[0]["tools"] == [] and spy.seen[0]["module"] == "m1_intent"


def test_changing_the_session_changes_what_nira_is_shown(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "draft", purpose="First purpose")
    spy = use_model(w, Spy()
)
    ask(org, sid)
    assert spy.context["rules"]["purpose"] == "First purpose"
    org.put(f"{BASE}/sessions/{sid}", json={"purpose": "Second purpose"})
    ask(org, sid)
    assert spy.context["rules"]["purpose"] == "Second purpose"


def test_her_instructions_are_plain_neutral_and_refuse_opinions(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    spy = use_model(w, Spy()
)
    ask(org, sid, question="Do you think we should cut our costs?")
    s = spy.system.lower()
    assert "nira" in s and "opinion" in s and "north" in s and "only from the rules" in s
    assert "industry_a" not in s and "industry_b" not in s and "co-a" not in s  # nothing about a company or industry


def test_the_instruction_file_and_no_code_carry_the_words(w):
    rules = nira.load_rules()
    assert "ask" in rules["tasks"] and {"welcome", "now", "warning"} <= set(rules["messages"])
    assert rules["avoid_terms"] and rules["fallback"]
    for must in ("cannot change anything", "single point of contact", "never say that it is done", "not the expert"):
        assert must in " ".join(rules["instructions"].split()) or must in rules["refusal_note"], must  # the earlier guide skill's guardrails
    src = Path(nira.__file__).read_text()
    for forbidden in ("import requests", "import httpx", "import anthropic", "import openai", "urllib", "genai", "http://", "https://"):
        assert forbidden not in src


def test_each_kind_gets_its_own_task_and_a_bad_kind_is_refused(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    spy = use_model(w, Spy()
)
    for kind in ("welcome", "now", "warning"):
        assert ask(org, sid, kind, None).status_code == 200
    assert spy.seen == []  # welcome, now and warning are the state machine's own messages: no model is asked
    assert ask(org, sid, "ask", "Where is my room?").status_code == 200 and "Where is my room?" in spy.question
    assert nira.load_rules()["tasks"]["ask"] in spy.question
    assert ask(org, sid, "gossip", "hi").status_code == 422
    assert ask(org, sid, "ask", None).status_code == 422 and ask(org, sid, "ask", "   ").status_code == 422
    assert ask(org, sid, "ask", "x" * 301).status_code == 422
    assert ask(org, sid, "ask", 5).status_code == 422
    assert org.post(f"{BASE}/sessions/{sid}/nira", json=["ask"]).status_code == 400


def test_a_question_is_answered_in_her_name_and_marks_the_seat_as_asked_not_clear(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", seats=2)
    p = seated(w, "co-a", "p", "seat-1")
    r = ask(p, sid).json()
    assert r["available"] is True and r["name"] == "Nira" and r["role"] == "the guide" and r["text"]
    assert p.get(f"{BASE}/sessions/{sid}/briefing").json()["me"]["status"] == "asked"
    assert org.get(f"{BASE}/sessions/{sid}/briefing").json()["confirmed"] == 0
    p.post(f"{BASE}/sessions/{sid}/briefing/confirm", json={"answer": "clear"})
    ask(p, sid)
    assert p.get(f"{BASE}/sessions/{sid}/briefing").json()["me"]["status"] == "clear"  # asking never undoes "clear"


# ---- numbers, plain words, failure -------------------------------------------------------------------------------
def test_figures_from_the_session_may_be_stated_and_invented_ones_are_replaced(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    use_model(w, Spy("The session lasts 20 minutes and 7 people will join.")
)
    text = ask(org, sid).json()["text"]
    assert "20 minutes" in text and "7" not in text and "not available yet" in text


def test_a_reply_with_engineering_words_is_replaced_by_the_plain_fallback(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    use_model(w, Spy("The JSON payload from the endpoint says yes.")
)
    assert ask(org, sid).json()["text"] == nira.load_rules()["fallback"]


def test_a_long_reply_is_cut_to_the_contract_length(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    use_model(w, Spy("Word. " * 400)
)
    assert len(ask(org, sid).json()["text"]) <= 600


def test_without_a_model_she_says_she_is_not_available_and_the_rules_still_show(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    use_model(w, None
)
    r = ask(org, sid)
    assert r.status_code == 200 and r.json() == {"available": False, "name": "Nira", "role": "the guide",
                                                 "text": "Nira is not available yet. The rules on this screen are all you need to begin."}
    assert org.get(f"{BASE}/sessions/{sid}/briefing").json()["rules"]


def test_a_model_failure_is_a_plain_message_not_a_trace(w):
    class Broken:
        def complete(self, *a, **k):
            raise RuntimeError("secret internal detail")

    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    use_model(w, Broken()
)
    r = ask(org, sid)
    assert r.status_code == 200 and "secret internal detail" not in r.text and r.json()["text"]


# ---- the run registry --------------------------------------------------------------------------------------------
def test_every_run_is_recorded_without_any_content(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", purpose="A very particular purpose")
    use_model(w, Spy("The unmistakable answer text.")
)
    ask(org, sid)
    ask(org, sid, "ask", "A very private question about lunch")
    log = (w.plane("co-a").area("context") / "run_registry.jsonl").read_text()
    rows = [json.loads(line) for line in log.splitlines()]
    assert [(r["agent"], r["module_id"], r["status"]) for r in rows] == [("Nira", "m1_intent", "done")] * 2
    for secret in ("A very particular purpose", "unmistakable", "private question", "lunch", "Co-A"):
        assert secret not in log
    assert not (w.plane("co-b").area("context") / "run_registry.jsonl").exists()


def test_a_switched_off_module_gets_no_nira(w):
    c = w.login("off", "co-off")
    assert c.post(f"{BASE}/sessions/{'a' * 32}/nira", json={"kind": "welcome"}).status_code == 403


def test_outsiders_cannot_reach_her(w):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    assert ask(w.login("x", "co-b"), sid).status_code == 404
    assert ask(w.login("noseat", "co-a", ["participant"]), sid).status_code == 403
    assert not re.search(r"Co-A", ask(w.login("o2", "co-a"), sid).text)  # another organiser of the same company: not found


@pytest.mark.parametrize("company,name", [("co-a", "Co-A"), ("co-b", "Co-B"), ("co-none", "Co-None")])
def test_works_for_two_industries_an_industry_with_no_pack_and_a_solo_run(w, company, name):
    org = w.login("org", company)
    sid = session_at(w, org, company, "briefing", seats=1)
    spy = use_model(w, Spy()
)
    assert ask(org, sid).json()["available"] is True
    assert spy.context["company"]["name"] == name and spy.context["suggestions"] == []


# ---- a running app: Nira goes through the egress gateway (B1) ------------------------------------------------------
GEMINI_REPLY = {"candidates": [{"content": {"parts": [{"text": "Here is a plain answer."}]}}]}


def running(w, monkeypatch, key=True):
    """The app as it runs: no stub injected, the key only in the environment, a MockTransport instead of the network."""
    import functools

    import httpx

    from modules.m1_intent.api import briefing as api
    from sh_platform.egress.providers import build_model_client

    del w.app.state.nira_model_factory
    w.app.state.model_env = {"GOOGLE_API_KEY": "fake-test-key-not-real"} if key else {}
    sent = []

    def handler(req):
        sent.append((req.url.host, req.content.decode()))
        return httpx.Response(200, json=GEMINI_REPLY)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(api, "build_model_client", functools.partial(build_model_client, client=client))
    return sent


def test_a_running_app_sends_nira_through_the_egress_client_with_names_protected(w, monkeypatch):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", purpose="Find our shared worries")
    sent = running(w, monkeypatch)
    r = ask(org, sid)
    assert r.status_code == 200 and r.json() == {"available": True, "name": "Nira", "role": "the guide", "text": "Here is a plain answer."}
    assert len(sent) == 1 and sent[0][0] == "generativelanguage.googleapis.com"
    assert "Co-A" not in sent[0][1] and "Test org" not in sent[0][1] and "fake-test-key" not in sent[0][1]
    from sh_platform.egress.vault import NameVault
    vault = NameVault(w.plane("co-a"))
    assert vault.contains_name("Co-A") and vault.contains_name("Test org")  # both registered before the call
    rows = [json.loads(x) for x in (w.plane("co-a").area("context") / "run_registry.jsonl").read_text().splitlines()]
    assert [(x["agent"], x["status"]) for x in rows] == [("Nira", "done")]


def test_a_company_name_in_the_session_text_never_leaves(w, monkeypatch):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", purpose="Help Co-A with its worries")
    sent = running(w, monkeypatch)
    assert ask(org, sid).status_code == 200
    assert all("Co-A" not in body for _, body in sent)


def test_no_key_gives_the_plain_sentence_and_no_call(w, monkeypatch):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    sent = running(w, monkeypatch, key=False)
    r = ask(org, sid).json()
    assert r["available"] is False and r["text"] == nira.load_rules()["unavailable"] and sent == []


def test_a_wrong_provider_setting_also_gives_the_plain_sentence(w, monkeypatch):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    running(w, monkeypatch)
    w.app.state.model_env = {**w.app.state.model_env, "SH_MODEL_PROVIDER": "nonsense"}
    r = ask(org, sid).json()
    assert r["available"] is False and "nonsense" not in json.dumps(r)


def test_every_seated_persons_name_is_registered_before_the_call(w, monkeypatch):
    from modules.m1_intent.store.room import JoinIndex, RoomStore
    from modules.m1_intent.store.sessions import SessionStore
    from sh_platform.egress.vault import NameVault
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "draft", seats=2)
    plane = w.plane("co-a")
    RoomStore(plane).start(sid, org.account_id, JoinIndex(w.settings.data_root))
    RoomStore(plane).take(sid, 1, "Zelda Quill", "participant", None)
    SessionStore(plane).transition(sid, "briefing")
    sent = running(w, monkeypatch)
    assert ask(org, sid).status_code == 200 and len(sent) == 1
    vault = NameVault(plane)
    assert vault.contains_name("Zelda Quill") and vault.contains_name("Zelda")
    assert "Zelda" not in sent[0][1]


def test_the_model_env_override_is_what_the_client_is_built_from(w, monkeypatch):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing")
    sent = running(w, monkeypatch, key=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-process-key-not-real")  # the process environment is not consulted
    assert ask(org, sid).json()["available"] is False and sent == []
    w.app.state.model_env = {"GOOGLE_API_KEY": "fake-override-key-not-real"}
    assert ask(org, sid).json()["available"] is True and len(sent) == 1
    assert "fake-override-key" not in sent[0][1]


# ---- the fixed messages (M1-P04c): the earlier Nira was the state machine's messages, not a model ------------------
def test_welcome_now_and_warning_work_with_no_key_and_make_no_call(w, monkeypatch):
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", purpose="Find our shared worries")
    sent = running(w, monkeypatch, key=False)
    welcome = ask(org, sid, "welcome", None).json()
    assert welcome["available"] is True and welcome["name"] == "Nira"
    assert "Find our shared worries" in welcome["text"] and "read the rules together" in welcome["text"]
    now = ask(org, sid, "now", None).json()
    assert now["available"] is True and "rules" in now["text"] and "clear" in now["text"]
    warn = ask(org, sid, "warning", None).json()
    assert "nearly up" not in warn["text"] and "minutes are left" in warn["text"] and "seconds" not in warn["text"]  # far from the end: just the time left
    assert sent == []


def test_what_to_do_now_follows_the_stage_and_says_the_same_every_time(w):
    org = w.login("org", "co-a")
    texts = {}
    for stage in ("lobby", "briefing", "private_rooms"):
        sid = session_at(w, org, "co-a", stage)
        texts[stage] = ask(org, sid, "now", None).json()["text"]
        assert ask(org, sid, "now", None).json()["text"] == texts[stage]
    assert len(set(texts.values())) == 3 and "own private room" in texts["private_rooms"]


def test_fixed_messages_hold_no_opinion_and_no_industry(w):
    cfg = nira.load_rules()
    said = json.dumps(cfg["messages"]).lower()
    assert "north" in said and not any(x in said for x in ("i think", "you should", "industry_a"))
    assert nira.say(cfg, "now", "no_such_stage", []) == cfg["messages"]["now"]["draft"]  # an unknown stage is never an error


def test_the_welcome_ends_each_sentence_even_when_the_organisers_words_do_not():
    cfg = nira.load_rules()
    text = nira.say(cfg, "welcome", "lobby", [{"id": "purpose", "text": "find what we should track"},
                                               {"id": "outcome", "text": "a signed list"}])
    assert "track. We want to leave with: a signed list. First" in text
