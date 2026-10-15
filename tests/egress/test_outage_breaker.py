"""CB1: a provider that is out of credit is refused once, then at once for 5 minutes, then one trial. Rate limits still retry."""
import json
import time

import httpx
import pytest

from sh_platform.egress import gateway as G
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.providers import model_transport, select_provider

KEY = "FAKE-KEY-FOR-TESTS-not-a-secret"
OK = {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}
BODY = json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode()
URL = "https://generativelanguage.googleapis.com/x"


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    G._breaker.clear()
    now = [1000.0]
    monkeypatch.setattr(G, "_clock", lambda: now[0])
    waits = []
    monkeypatch.setattr(G, "_sleep", waits.append)
    yield now, waits
    G._breaker.clear()


def run(replies):
    seen, left = [], list(replies)

    def handler(req):
        seen.append(req)
        r = left.pop(0)
        return r if isinstance(r, httpx.Response) else httpx.Response(200, json=r)
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    env = {"GOOGLE_API_KEY": KEY}
    return model_transport(select_provider(env), client=client, env=env), seen


@pytest.mark.parametrize("status,code", [(402, "no_credit"), (401, "provider_key_refused"), (403, "provider_key_refused")])
def test_refusal_is_fast_unretried_then_breaker_skips_provider(fresh, status, code):
    now, waits = fresh
    t, seen = run([httpx.Response(status)])
    t0 = time.perf_counter()
    with pytest.raises(EgressBlocked) as e:
        t(URL, BODY)
    assert time.perf_counter() - t0 < 2 and e.value.reason_code == code and len(seen) == 1 and not waits
    now[0] += 299
    with pytest.raises(EgressBlocked) as e:
        t(URL, BODY)
    assert e.value.reason_code == code and len(seen) == 1  # never reached the provider


def test_after_the_window_one_trial_call(fresh):
    now, _ = fresh
    t, seen = run([httpx.Response(402), httpx.Response(402), OK])
    with pytest.raises(EgressBlocked):
        t(URL, BODY)
    now[0] += 301
    with pytest.raises(EgressBlocked):
        t(URL, BODY)
    assert len(seen) == 2  # the trial failed: window re-armed
    with pytest.raises(EgressBlocked):
        t(URL, BODY)
    assert len(seen) == 2
    now[0] += 301
    assert json.loads(t(URL, BODY))["text"] == "hello" and len(seen) == 3
    assert not G._breaker


def test_plain_429_is_still_retried(fresh):
    _, waits = fresh
    t, seen = run([httpx.Response(429, text="rate limit exceeded"), OK])
    assert json.loads(t(URL, BODY))["text"] == "hello" and len(seen) == 2 and len(waits) == 1 and not G._breaker


def test_429_with_exhausted_credit_opens_the_breaker(fresh):
    t, seen = run([httpx.Response(429, text="You have exhausted your credit balance")])
    with pytest.raises(EgressBlocked) as e:
        t(URL, BODY)
    assert e.value.reason_code == "no_credit" and len(seen) == 1


def test_gateway_logs_each_refused_call(fresh, plane):
    from egress_helpers import MODEL_HOST, log_lines, make_gateway
    calls = []
    client = httpx.Client(transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(402)), follow_redirects=False)
    send = G.make_httpx_transport(None, client=client, tries=3)
    gw, _, _ = make_gateway(plane, send)
    for _ in range(2):
        with pytest.raises(EgressBlocked) as e:
            gw.send_model_prompt("m1", {"question": "hi"})
        assert e.value.reason_code == "no_credit"
    assert len(calls) == 1  # the second call never left
    lines = log_lines(plane)
    assert [(x["decision"], x["reason_code"]) for x in lines] == [("sent", ""), ("failed", "no_credit")] * 2
