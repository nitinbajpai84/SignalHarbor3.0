"""Smoke: the egress rules end to end, with a stub transport (nothing leaves the machine).

The plane is the seeded company's own, in tmp_path.
"""
import json

import pytest

from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry
from sh_platform.agents.runs import RunRegistry
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import EgressGateway
from sh_platform.egress.minimiser import minimise
from sh_platform.egress.model import EgressModelClient
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.vault import NameVault
from smoke_helpers import CASES

B = CASES["B"]["id"]
MODEL_HOST, NET_HOST = "model.example.test", "public.example.test"


class Stub:
    """Stub transport: records every call, never touches the network."""

    def __init__(self, reply="ok"):
        self.calls, self.reply = [], reply

    def __call__(self, url, body):
        self.calls.append((url, body))
        return self.reply


@pytest.fixture
def rig(env):
    plane = env.planes.plane_for(B)
    model, net = Stub(), Stub("public page text")
    policy = EgressPolicy(plane, env.settings.egress_default)  # the company's real default: off
    policy.set_internet_hosts([NET_HOST])  # an allowlisted host, but the switch stays off
    vault = NameVault(plane)
    gw = EgressGateway(plane, vault, policy, model_allowlist=[MODEL_HOST], transport=model,
                       internet_transport=net, model_url=f"https://{MODEL_HOST}/v1/messages")
    return type("Rig", (), dict(plane=plane, gw=gw, vault=vault, policy=policy, model=model, net=net, env=env))


def log(plane):
    p = plane.area("context") / "egress_log.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []


def log_text(plane):
    """The log without its hash, time and attempt id (random hex that could hold any short digit run)."""
    return "\n".join(json.dumps({k: v for k, v in ln.items() if k not in ("sha256", "time", "attempt")})
                     for ln in log(plane))


def refused(rig, code, call, *args, **kw):
    """Refused with `code`: exactly one new log line, no transport call at all."""
    n, sent = len(log(rig.plane)), len(rig.model.calls) + len(rig.net.calls)
    with pytest.raises(EgressBlocked) as e:
        call(*args, **kw)
    assert e.value.reason_code == code
    assert len(rig.model.calls) + len(rig.net.calls) == sent
    lines = log(rig.plane)
    assert len(lines) == n + 1 and lines[-1]["decision"] == "blocked" and lines[-1]["reason_code"] == code


def test_internet_is_off_by_default_and_refusals_are_logged(rig):
    assert rig.policy.is_internet_allowed("m1_intent") is False  # never configured: off
    refused(rig, "internet_off", rig.gw.internet_query, "m1_intent", f"https://{NET_HOST}/q", "public market trends")
    assert "public market trends" not in log_text(rig.plane)
    rig.policy.set_internet("m1_intent", True)  # control: switched on for that module, it goes through
    reply = rig.gw.internet_query("m1_intent", f"https://{NET_HOST}/q", "public market trends")
    assert reply.outside is True and reply.text == "public page text" and len(rig.net.calls) == 1
    refused(rig, "internet_off", rig.gw.internet_query, "m2_baseline", f"https://{NET_HOST}/q", "public")  # per module
    refused(rig, "destination_not_allowed", rig.gw.internet_query, "m1_intent", "https://other.example.test/q", "x")


def test_internet_query_with_a_registered_name_is_refused(rig):
    rig.vault.register("company", "Zephyr Holdings")
    rig.policy.set_internet("m1_intent", True)
    refused(rig, "vault_name", rig.gw.internet_query, "m1_intent", f"https://{NET_HOST}/q", "news about Zephyr Holdings")
    assert "Zephyr" not in log_text(rig.plane)


def test_model_prompt_leaves_tokenised_never_in_clear(rig):
    rig.vault.register("company", "Zephyr Holdings")
    rig.vault.register("person", "Quentin Marlowe")
    rig.model.reply = "COMPANY_001 is on track, said PERSON_001."
    payload = {"question": "How is Zephyr Holdings doing, and what did Quentin Marlowe say about q.marlowe@example.test?"}
    r = rig.gw.send_model_prompt("m1_intent", payload)
    (url, body), = rig.model.calls
    text = body.decode("utf-8")
    assert "Zephyr" not in text and "Marlowe" not in text and "q.marlowe@example.test" not in text
    assert "COMPANY_001" in text and "PERSON_001" in text
    assert r.text == "Zephyr Holdings is on track, said Quentin Marlowe."  # mapped back inside the plane
    (line,) = log(rig.plane)
    assert line["decision"] == "sent" and line["host"] == MODEL_HOST and line["bytes"] == len(body)
    for w in ("Zephyr", "Marlowe", "COMPANY_001", "PERSON_001", "on track"):
        assert w not in log_text(rig.plane)


def test_name_that_cannot_be_swapped_is_blocked(rig):
    rig.vault.register("company", "Northwind Traders")
    refused(rig, "vault_name", rig.gw.send_model_prompt, "m1_intent", {"question": "see North-\nwindTraders9"})  # AQ1: glued forms are swapped


def test_payload_with_raw_rows_is_blocked(rig):
    refused(rig, "raw_rows", rig.gw.send_model_prompt, "m1_intent",
            {"question": "Summarise", "rows": [{"customer": "a", "balance": 10}]})
    refused(rig, "raw_rows", rig.gw.send_model_prompt, "m1_intent",
            {"question": "Summarise", "facts": [{"label": "orders", "value": 9, "group_size": 9, "customer": "a"}]})
    refused(rig, "raw_rows", rig.gw.send_model_prompt, "m1_intent",
            {"question": 'Here: [{"customer": "a", "balance": 10}, {"customer": "b", "balance": 11}]'})
    assert "customer" not in log_text(rig.plane)


def test_group_of_four_is_blocked_and_group_of_five_passes(rig):
    four = {"question": "How many?", "facts": [{"label": "late orders", "value": 4242, "group_size": 4}]}
    refused(rig, "suppressed_figure", rig.gw.send_model_prompt, "m1_intent", four)
    five = {"question": "How many?", "facts": [{"label": "late orders", "value": 4242, "group_size": 5}]}
    rig.gw.send_model_prompt("m1_intent", five)
    assert len(rig.model.calls) == 1 and b"4242" in rig.model.calls[0][1]
    refused(rig, "suppressed_figure", rig.gw.send_model_prompt, "m1_intent",
            {"question": "x", "facts": [{"label": "late orders", "value": 7, "group_size": None}]})
    assert "4242" not in log_text(rig.plane)


def test_minimiser_holds_back_a_small_group_and_its_value_cannot_be_quoted(rig):
    facts = [{"label": "late orders", "value": 4242, "group_size": 4}, {"label": "orders", "value": 90, "group_size": 12}]
    payload, held = minimise("How are we doing?", facts, {"late orders", "orders"})
    assert payload["facts"] == [facts[1]] and len(held) == 1
    rig.gw.send_model_prompt("m1_intent", payload, held)  # the safe payload passes
    quote = {"question": "Why are there 4,242 late orders?"}
    refused(rig, "suppressed_figure", rig.gw.send_model_prompt, "m1_intent", quote, held)


def test_every_attempt_writes_exactly_one_line_and_never_payload_text(rig):
    rig.vault.register("person", "Quentin Marlowe")
    attempts = [
        ("m1_intent", {"question": "A clean question about backlog"}),
        ("m1_intent", {"question": "What does Quentin Marlowe think about backlog?"}),
        ("m1_intent", {"question": "backlog", "rows": [{"x": 1}]}),
        ("m1_intent", {"question": "backlog", "facts": [{"label": "backlog", "value": 31337, "group_size": 2}]}),
    ]
    outcomes = []
    for module, payload in attempts:
        try:
            rig.gw.send_model_prompt(module, payload)
            outcomes.append("sent")
        except EgressBlocked as e:
            outcomes.append(e.reason_code)
    assert outcomes == ["sent", "sent", "raw_rows", "suppressed_figure"]  # the name was tokenised, not refused
    lines = log(rig.plane)
    assert len(lines) == len(attempts)  # exactly one line per attempt
    assert [ln["decision"] for ln in lines] == ["sent", "sent", "blocked", "blocked"]
    assert len(rig.model.calls) == 2  # the transport never saw the blocked ones
    text = log_text(rig.plane)
    for w in ("backlog", "Quentin", "Marlowe", "31337", "PERSON_001"):
        assert w not in text
    for ln in lines:
        assert set(ln) - {"masked"} == {"attempt", "time", "module", "kind", "host", "decision", "reason_code", "bytes", "sha256"}
        assert isinstance(ln.get("masked", 0), int)  # TS1c-05: a count of names swapped for tokens, never the names


def test_agent_run_through_the_real_registry_and_egress_client(rig):
    env = rig.env
    registry = ToolRegistry(env.entitlements)
    registry.register("m1_intent", "open_count", lambda: {"total": 12, "group_size": 9}, read_only=True,
                      description="Open items.", parameters={})
    rig.model.reply = "You have 12 open items and 9,317 late ones."  # 9,317 is invented
    context = {"facts": [{"id": "f1", "label": "Open", "value": 12, "group_size": 9}]}
    runs = RunRegistry(rig.plane)
    out = run_agent(EgressModelClient(rig.gw), registry, B, "m1_intent", "North", "You help.", context,
                    "How many items are open?", recorder=runs, fast={"off": True})
    assert out.status == "done" and out.numbers_replaced == 1
    assert "9,317" not in out.text and "not available yet" in out.text and "12 open items" in out.text
    assert len(rig.model.calls) == 1  # one guarded model call
    rows = (rig.plane.area("context") / "run_registry.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row["status"] == "done" and row["agent"] == "North" and row["numbers_replaced"] == 1
    assert set(row) == {"run_id", "agent", "module_id", "started", "finished", "status", "steps",
                        "tools_called", "numbers_replaced"}
    blob = json.dumps({k: v for k, v in row.items() if k not in ("run_id", "started", "finished")})         + log_text(rig.plane)
    for w in ("open items", "late ones", "How many items", "9,317"):
        assert w not in blob
    assert len(log(rig.plane)) == 1


def test_agent_run_is_refused_for_a_company_that_does_not_own_the_module(rig):
    registry = ToolRegistry(rig.env.entitlements)
    out = run_agent(EgressModelClient(rig.gw), registry, CASES["A"]["id"], "m4_build", "Builder", "You help.",
                    {"facts": []}, "Anything?")
    assert out.status == "refused" and rig.model.calls == [] and log(rig.plane) == []
