"""Model transport reliability: transient failures (429, 5xx, timeouts, resets) are retried with backoff, a gateway
refusal never is, Retry-After is honoured within a cap, and calls share a small process-wide slot. MockTransport only."""
import json
import threading
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


@pytest.fixture
def waits(monkeypatch):
    out = []
    monkeypatch.setattr(G, "_sleep", out.append)
    G._breaker.clear()
    return out


def run(replies, final_check=None):
    seen, left = [], list(replies)

    def handler(req):
        seen.append(req)
        r = left.pop(0)
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, httpx.Response) else httpx.Response(200, json=r)
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    env = {"GOOGLE_API_KEY": KEY}
    return model_transport(select_provider(env), client=client, final_check=final_check, env=env), seen


def test_429_then_200_succeeds_after_one_backoff(waits):
    t, seen = run([httpx.Response(429), OK])
    assert json.loads(t(URL, BODY))["text"] == "hello"
    assert len(seen) == 2 and len(waits) == 1 and 1.0 <= waits[0] <= 1.25


def test_three_503s_fail_cleanly_with_backoff_and_no_body_in_the_log(waits, caplog):
    t, seen = run([httpx.Response(503, text=f"secret body {KEY}")] * 3)
    with pytest.raises(httpx.HTTPStatusError):
        t(URL, BODY)
    assert len(seen) == 3 and [round(w) for w in waits] == [1, 2]
    assert KEY not in caplog.text and "secret body" not in caplog.text and "http_503" in caplog.text  # the code only


@pytest.mark.parametrize("fail", [httpx.Response(500), httpx.Response(504), httpx.ReadTimeout("t"), httpx.ConnectError("reset")])
def test_other_transient_failures_are_retried(waits, fail):
    t, seen = run([fail, OK])
    assert json.loads(t(URL, BODY))["text"] == "hello" and len(seen) == 2


@pytest.mark.parametrize("fail", [httpx.Response(400), httpx.Response(401), httpx.Response(404)])
def test_a_client_error_is_not_retried(waits, fail):
    t, seen = run([fail, OK])
    with pytest.raises((httpx.HTTPStatusError, EgressBlocked)):  # 401 is now a key refusal (CB1)
        t(URL, BODY)
    assert len(seen) == 1 and waits == []


def test_a_gateway_refusal_is_never_retried(waits):
    t, seen = run([OK], final_check=lambda text: True)  # a protected name in the final body
    with pytest.raises(EgressBlocked) as e:
        t(URL, BODY)
    assert e.value.reason_code == "vault_name" and seen == [] and waits == []


def test_a_missing_credential_is_not_retried(waits):
    seen, env = [], {"GOOGLE_API_KEY": "k"}
    choice = select_provider(env)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: (seen.append(r), httpx.Response(200, json=OK))[1]))
    env["GOOGLE_API_KEY"] = ""  # the key is read at call time
    with pytest.raises(EgressBlocked) as e:
        model_transport(choice, client=client, env=env)(URL, BODY)
    assert e.value.reason_code == "no_credential" and seen == [] and waits == []


def test_retry_after_is_honoured_within_the_cap(waits):
    t, _ = run([httpx.Response(429, headers={"Retry-After": "3"}), OK])
    t(URL, BODY)
    assert waits == [3.0]
    waits.clear()
    t, _ = run([httpx.Response(429, headers={"Retry-After": "120"}), OK])
    t(URL, BODY)
    assert waits == [G.RETRY_AFTER_CAP] and G.RETRY_AFTER_CAP <= 8.0


def test_only_two_model_calls_run_at_once():
    now, peak, lock = [0], [0], threading.Lock()

    def handler(req):
        with lock:
            now[0] += 1
            peak[0] = max(peak[0], now[0])
        time.sleep(0.05)
        with lock:
            now[0] -= 1
        return httpx.Response(200, json=OK)
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    env = {"GOOGLE_API_KEY": KEY}
    t = model_transport(select_provider(env), client=client, env=env)
    threads = [threading.Thread(target=t, args=(URL, BODY)) for _ in range(6)]
    [x.start() for x in threads]
    [x.join() for x in threads]
    assert peak[0] == 2
