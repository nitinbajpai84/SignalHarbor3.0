"""A-017: provider adapters behind the egress gateway. httpx.MockTransport only: no live call, no real key."""
import json

import httpx
import pytest

from egress_helpers import log_lines
from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import EgressGateway
from sh_platform.egress.model import ToolCall, decode_turn, encode_turn
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.providers import (ADAPTERS, ProviderError, build_model_client, key_status, model_transport,
                                          select_provider)
from sh_platform.egress.providers.gemini import GeminiAdapter
from sh_platform.egress.providers.openrouter import OpenRouterAdapter
from sh_platform.egress.vault import NameVault

FAKE_KEY = "FAKE-KEY-FOR-TESTS-not-a-secret"  # clearly fake; never a real key
TOOLS = [{"name": "industry_practice", "description": "Practice for a topic", "parameters": ["topic"]},
         {"name": "problem_library", "description": "The library", "parameters": []}]
TURNS = [
    {"role": "system", "content": "Be brief."},
    {"role": "user", "content": "hello"},
    encode_turn({"role": "assistant", "content": "checking", "tool_calls": [
        {"name": "industry_practice", "arguments": {"topic": "churn"}, "id": "c1"}]}),
    encode_turn({"role": "tool", "name": "industry_practice", "tool_call_id": "c1", "content": '{"items": ["a"]}'}),
]


class Gate:
    def is_enabled(self, company_id, module_id):
        return True


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", FAKE_KEY)
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)


def mock_client(replies, seen):
    """An httpx client whose every request is answered from `replies` (the last repeats) and recorded."""
    replies = list(replies)

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        r = replies.pop(0) if len(replies) > 1 else replies[0]
        return r if isinstance(r, httpx.Response) else httpx.Response(200, json=r)
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


# ---- tool turns across the gateway envelope

def test_tool_turns_round_trip_through_the_envelope():
    a = decode_turn(TURNS[2])
    assert a["role"] == "assistant" and a["text"] == "checking"
    assert a["calls"] == [ToolCall("industry_practice", {"topic": "churn"}, "c1")]
    assert decode_turn(TURNS[3]) == {"role": "tool", "id": "c1", "name": "industry_practice", "content": '{"items": ["a"]}'}
    assert encode_turn({"role": "user", "content": "x"}) == {"role": "user", "content": "x"}  # plain unchanged
    assert decode_turn({"role": "tool", "content": "bare"})["id"] == ""  # old style tool message still reads
    # a hostile id or name cannot smuggle a header line
    e = encode_turn({"role": "assistant", "content": "", "tool_calls": [{"name": "x y\nz", "arguments": {}, "id": "a b"}]})
    assert "\nz" not in e["content"] and decode_turn(e)["calls"][0].id == "call_0"


# ---- wire formats

def test_gemini_request_and_reply():
    path, body = GeminiAdapter().format_request("gemini-test", TURNS, TOOLS)
    assert path == "/v1beta/models/gemini-test:generateContent"
    assert body["systemInstruction"] == {"parts": [{"text": "Be brief."}]}
    roles = [c["role"] for c in body["contents"]]
    assert roles == ["user", "model", "user"]
    assert body["contents"][1]["parts"][1] == {"functionCall": {"name": "industry_practice", "args": {"topic": "churn"}}}
    assert body["contents"][2]["parts"][0]["functionResponse"]["name"] == "industry_practice"
    decls = body["tools"][0]["functionDeclarations"]
    assert decls[0]["parameters"]["required"] == ["topic"] and "parameters" not in decls[1]
    assert FAKE_KEY not in json.dumps(body)
    reply = {"candidates": [{"content": {"parts": [{"text": "hidden", "thought": True}, {"text": "Hi. "},
                                                   {"text": "There."},
                                                   {"functionCall": {"name": "problem_library", "args": {}}}]}}]}
    text, calls = GeminiAdapter().parse_reply(json.dumps(reply))
    assert text == "Hi. There." and calls == [ToolCall("problem_library", {}, "call_0")]
    assert GeminiAdapter().parse_reply("not json") == ("", [])
    assert GeminiAdapter().parse_reply('{"candidates": []}') == ("", [])


def test_openrouter_request_and_reply():
    path, body = OpenRouterAdapter().format_request("some/model", TURNS, TOOLS)
    assert path == "/api/v1/chat/completions" and body["model"] == "some/model"
    m = body["messages"]
    assert [x["role"] for x in m] == ["system", "user", "assistant", "tool"]
    assert m[2]["tool_calls"][0] == {"id": "c1", "type": "function", "function": {
        "name": "industry_practice", "arguments": '{"topic": "churn"}'}}
    assert m[3] == {"role": "tool", "tool_call_id": "c1", "content": '{"items": ["a"]}'}
    assert body["tools"][0]["function"]["parameters"]["properties"] == {"topic": {"type": "string"}}
    reply = {"choices": [{"message": {"content": "ok", "tool_calls": [
        {"id": "t9", "type": "function", "function": {"name": "industry_practice", "arguments": '{"topic": "x"}'}},
        {"id": "bad", "type": "function", "function": {"name": "industry_practice", "arguments": "{not json"}}]}}]}
    text, calls = OpenRouterAdapter().parse_reply(json.dumps(reply))  # the malformed call is dropped, never run
    assert text == "ok" and calls == [ToolCall("industry_practice", {"topic": "x"}, "t9")]
    assert OpenRouterAdapter().parse_reply("{}") == ("", [])


# ---- selection and key handling

def test_selection_from_settings():
    assert select_provider({}) is None
    both = {"GOOGLE_API_KEY": "x", "OPENROUTER_API_KEY": "y"}
    assert select_provider(both).adapter.name == "gemini"  # the default when both keys exist
    assert select_provider({"OPENROUTER_API_KEY": "y"}).adapter.name == "openrouter"
    c = select_provider({**both, "SH_MODEL_PROVIDER": "openrouter", "SH_MODEL_NAME": "a/b"})
    assert (c.adapter.name, c.model) == ("openrouter", "a/b")
    c = select_provider({**both, "SH_MODEL_NAME": "a-b", "SH_MODEL_FAST": "fast-one"}, tier="fast")
    assert c.model == "fast-one"  # the tier setting wins over the general name
    assert select_provider({"SH_MODEL_PROVIDER": "gemini"}) is None  # asked for, but no key: not available
    with pytest.raises(ProviderError):
        select_provider({"SH_MODEL_PROVIDER": "nope", "GOOGLE_API_KEY": "x"})
    with pytest.raises(ProviderError):
        select_provider({"GOOGLE_API_KEY": "x", "SH_MODEL_NAME": "../../etc"})  # goes into a URL path


def test_key_status_and_reprs_never_hold_a_value():
    env = {"GOOGLE_API_KEY": FAKE_KEY}
    st = key_status(env)
    assert st["provider"] == "gemini" and st["key_env"] == "GOOGLE_API_KEY" and FAKE_KEY not in json.dumps(st)
    assert FAKE_KEY not in repr(select_provider(env)) and FAKE_KEY not in repr(ADAPTERS)


# ---- the transport behind the gateway

def make(plane, client, **kw):
    choice = select_provider({"GOOGLE_API_KEY": "x", **kw})
    vault = NameVault(plane)
    gw = EgressGateway(plane, vault, EgressPolicy(plane), model_allowlist=[choice.adapter.host],
                       model_url=f"https://{choice.adapter.host}",
                       transport=model_transport(choice, client=client, final_check=vault.contains_name))
    return gw, vault


def test_names_leave_tokenised_and_the_key_stays_in_the_header(plane, key):
    seen = []
    gw, vault = make(plane, mock_client([{"candidates": [{"content": {"parts": [{"text": "Hello PERSON_001."}]}}]}], seen))
    vault.register("person", "Zelda Quark")
    from sh_platform.egress.model import EgressModelClient
    r = EgressModelClient(gw).complete("m1", [{"role": "system", "content": "s"},
                                              {"role": "user", "content": "I am Zelda Quark, mail zelda@example.test"}])
    assert r.text == "Hello Zelda Quark."  # replies are detokenised inside the plane
    req = seen[0]
    assert req.url.host == "generativelanguage.googleapis.com" and req.headers["x-goog-api-key"] == FAKE_KEY
    wire = req.content.decode()
    assert "Zelda" not in wire and "zelda@example.test" not in wire and "PERSON_001" in wire
    assert FAKE_KEY not in str(req.url) and FAKE_KEY not in wire
    log = (plane.area("context") / "egress_log.jsonl").read_text()
    assert FAKE_KEY not in log and "Zelda" not in log and log_lines(plane)[0]["host"] == "generativelanguage.googleapis.com"


def test_tool_call_round_trip_through_the_real_loop(plane, key):
    seen = []
    first = {"candidates": [{"content": {"parts": [{"functionCall": {"name": "industry_practice", "args": {"topic": "churn"}}}]}}]}
    second = {"candidates": [{"content": {"parts": [{"text": "Done."}]}}]}
    gw, _ = make(plane, mock_client([first, second], seen))
    from sh_platform.egress.model import EgressModelClient
    reg = ToolRegistry(Gate())
    reg.register("m1", "industry_practice", lambda topic: {"items": ["watch retention"]}, read_only=True,
                 description="d", parameters={"topic": "a topic"})
    res = run_agent(EgressModelClient(gw), reg, "acme-co", "m1", "North", "Be brief.", {}, "Say hello to the team")
    assert res.status == "done" and res.text == "Done." and res.tools_called == ["industry_practice"]
    assert len(seen) == 2
    second_body = json.loads(seen[1].content)
    parts = [p for c in second_body["contents"] for p in c["parts"]]
    assert {"functionCall": {"name": "industry_practice", "args": {"topic": "churn"}}} in parts  # the call turn is carried
    assert any("functionResponse" in p and p["functionResponse"]["name"] == "industry_practice" for p in parts)


def test_openrouter_path_and_bearer_key(plane, key):
    seen = []
    choice = select_provider({"OPENROUTER_API_KEY": "x"})
    t = model_transport(choice, client=mock_client([{"choices": [{"message": {"content": "ok"}}]}], seen))
    out = json.loads(t("https://openrouter.ai", json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode()))
    assert out == {"text": "ok", "model": choice.model, "tool_calls": []}  # the model id rides along for the gateway cost row
    assert str(seen[0].url) == "https://openrouter.ai/api/v1/chat/completions"
    assert seen[0].headers["authorization"] == f"Bearer {FAKE_KEY}"


def test_other_hosts_are_refused_and_never_get_the_key(plane, key):
    seen = []
    gw, _ = make(plane, mock_client([{}], seen))
    gw.model_allowlist.append("other.example.test")  # even if an operator allowlisted it, the adapter says no
    gw._model_url = "https://other.example.test"
    with pytest.raises(EgressBlocked) as e:
        gw.send_model_prompt("m1", {"messages": [{"role": "user", "content": "hi"}]})
    assert e.value.reason_code == "destination_not_allowed" and seen == []
    assert log_lines(plane)[-1]["decision"] == "failed"


def test_gateway_allowlist_is_the_provider_host_only(plane, key):
    client = build_model_client(plane, {"GOOGLE_API_KEY": "x"})
    assert client.gateway.model_allowlist == ["generativelanguage.googleapis.com"]
    assert build_model_client(plane, {}) is None  # no key: the caller degrades honestly


def test_missing_key_and_provider_errors_never_echo_a_key(plane, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    seen = []
    gw, _ = make(plane, mock_client([{}], seen))
    with pytest.raises(EgressBlocked) as e:
        gw.send_model_prompt("m1", {"messages": [{"role": "user", "content": "hi"}]})
    assert e.value.reason_code == "no_credential" and seen == []
    monkeypatch.setenv("GOOGLE_API_KEY", FAKE_KEY)
    gw, _ = make(plane, mock_client([httpx.Response(500, text=f"boom {FAKE_KEY}")], seen))
    with pytest.raises(EgressBlocked) as e:
        gw.send_model_prompt("m1", {"messages": [{"role": "user", "content": "hi"}]})
    assert e.value.reason_code == "transport_failed" and FAKE_KEY not in str(e.value) + repr(e.value)
    assert FAKE_KEY not in (plane.area("context") / "egress_log.jsonl").read_text()


def test_a_name_added_by_the_adapter_stage_is_refused(plane, key):
    seen = []
    gw, vault = make(plane, mock_client([{}], seen))
    choice = select_provider({"GOOGLE_API_KEY": "x"})
    vault.register("person", "Zelda Quark")
    t = model_transport(choice, client=mock_client([{}], seen), final_check=vault.contains_name)
    with pytest.raises(EgressBlocked) as e:  # a name that reached the final wire body (skipping the gateway) is stopped
        t("https://generativelanguage.googleapis.com",
          json.dumps({"messages": [{"role": "user", "content": "hi Zelda Quark"}]}).encode())
    assert e.value.reason_code == "vault_name" and seen == []


def test_the_gateway_guards_still_run_before_the_adapter(plane, key):
    seen = []
    gw, _ = make(plane, mock_client([{}], seen))
    rows = json.dumps([{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    with pytest.raises(EgressBlocked) as e:
        gw.send_model_prompt("m1", {"messages": [{"role": "user", "content": rows}]})
    assert e.value.reason_code == "raw_rows" and seen == []
    with pytest.raises(EgressBlocked):
        gw.send_model_prompt("m1", {"question": "q", "other_key": 1})
    assert seen == []


# ---- SF14d: each parameter goes with its real JSON type, never as text by default

def test_a_tools_parameter_types_reach_both_adapters_through_the_real_gateway(plane, key):
    """propose's `args` is an object: it must be declared as one, so the model sends an object, not JSON text."""
    seen = []
    call = {"candidates": [{"content": {"parts": [{"functionCall": {"name": "propose",
                                                                    "args": {"kind": "model_change", "args": {"title": "History"}}}}]}}]}
    gw, _ = make(plane, mock_client([call, {"candidates": [{"content": {"parts": [{"text": "Filed."}]}}]}], seen))
    from sh_platform.egress.model import EgressModelClient
    reg = ToolRegistry(Gate())
    got = []
    reg.register("m1", "propose", lambda kind, args: got.append(args) or {"kind": kind, **args}, read_only=False, proposes=True,
                 description="d", parameters={"kind": "string", "args": "object"})
    reg.register("m1", "industry_practice", lambda topic: {"items": ["x"]}, read_only=True, description="d",
                 parameters={"topic": "the person's own words"})  # North's style: a description is text
    res = run_agent(EgressModelClient(gw), reg, "acme-co", "m1", "Span", "Be brief.", {}, "Say hello to the team")
    assert res.status == "done" and got == [{"title": "History"}]
    decl = {d["name"]: d for d in json.loads(seen[0].content)["tools"][0]["functionDeclarations"]}
    assert decl["propose"]["parametersJsonSchema"]["properties"] == {"kind": {"type": "string"}, "args": {"type": "object"}}
    assert decl["industry_practice"]["parameters"]["properties"] == {"topic": {"type": "string"}}
    tools = [{"name": "t", "description": "d", "parameters": ["kind", "args:object", "ids:array", "n:integer", "ok:boolean", "a:b"]}]
    props = OpenRouterAdapter().format_request("some/model", TURNS, tools)[1]["tools"][0]["function"]["parameters"]["properties"]
    assert props == {"kind": {"type": "string"}, "args": {"type": "object"}, "ids": {"type": "array", "items": {}},
                     "n": {"type": "integer"}, "ok": {"type": "boolean"}, "a:b": {"type": "string"}}
