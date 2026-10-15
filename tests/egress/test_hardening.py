"""Second-round tests: vault safety, URL checks, log order, header leak, number and row guards."""
import json
import threading
import time

import httpx
import pytest

from egress_helpers import MODEL_HOST, NET_HOST, Transport, log_lines, make_gateway
from sh_platform.egress import vault as vault_mod
from sh_platform.egress.aggregates import SuppressedFigures, filter_facts
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import EgressGateway, make_httpx_transport
from sh_platform.egress.model import EgressModelClient, ToolCall, parse_reply
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.rows import json_findings, text_has_rows
from sh_platform.egress.vault import NameVault, VaultUnavailable

GOOD = {"question": "How many orders?", "facts": [{"label": "orders", "value": 40, "group_size": 8}]}


def blocked(gw, transport, plane, code, *args, fn=None, **kw):
    n = len(log_lines(plane))
    with pytest.raises(EgressBlocked) as e:
        (fn or gw.send_model_prompt)(*args, **kw)
    assert e.value.reason_code == code
    assert transport.calls == []
    lines = log_lines(plane)
    assert len(lines) == n + 1 and lines[-1]["reason_code"] == code and lines[-1]["decision"] == "blocked"
    return e.value


def vault_file(plane):
    return plane.area("context") / "name_vault.json"


# ---- B1: vault unreadable fails closed and is never overwritten
@pytest.mark.parametrize("content", [b"{not json", b"", b'{"entries": 5}', b'{"entries": {"X_001": {"kind": "planet", "name": "n"}}}'])
def test_unreadable_vault_refuses_and_is_untouched(plane, transport, content):
    vault_file(plane).write_bytes(content)
    gw, v, _ = make_gateway(plane, transport)
    blocked(gw, transport, plane, "vault_unavailable", "m1", GOOD)
    for call in (lambda: v.register("person", "Ann Lee"), lambda: v.tokenise("x"),
                 lambda: v.contains_name("x"), lambda: v.detokenise("x")):
        with pytest.raises(VaultUnavailable):
            call()
    assert vault_file(plane).read_bytes() == content


def test_vault_directory_in_place_of_file_refuses(plane, transport):
    vault_file(plane).mkdir()
    gw, _, _ = make_gateway(plane, transport)
    blocked(gw, transport, plane, "vault_unavailable", "m1", GOOD)


def test_missing_vault_is_empty_not_an_error(plane, transport):
    gw, v, _ = make_gateway(plane, transport)
    assert not vault_file(plane).exists() and v.contains_name("anything") is False
    gw.send_model_prompt("m1", GOOD)
    assert len(transport.calls) == 1


def test_vault_save_failure_refuses_with_right_reason(plane, transport, monkeypatch):
    gw, v, _ = make_gateway(plane, transport)

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(vault_mod, "write_json_atomic", boom)
    with pytest.raises(VaultUnavailable):
        v.register("person", "Ann Lee")
    assert not vault_file(plane).exists()
    # tokenising an e-mail needs no save any more: the token lives in memory only
    gw.send_model_prompt("m1", {"question": "mail a@b.example now"})
    assert b"a@b.example" not in transport.calls[0][1]


def test_stale_lock_held_too_long_refuses(plane, monkeypatch):
    v = NameVault(plane)
    monkeypatch.setattr(vault_mod, "_LOCK_WAIT", 0.05)
    v._lock.write_text("x")  # fresh lock held by someone else
    with pytest.raises(VaultUnavailable):
        v.register("person", "Ann Lee")


# ---- B2: two instances stay consistent
def test_two_instances_see_each_others_names(plane, transport):
    gw, va, _ = make_gateway(plane, transport)
    vb = NameVault(plane)
    assert va.contains_name("Zelda Quark") is False
    vb.register("person", "Zelda Quark")  # registered by another instance after A was built
    gw.send_model_prompt("m1", {"question": "about Zelda Quark"})
    assert b"Zelda" not in transport.calls[0][1] and b"PERSON_001" in transport.calls[0][1]


def test_two_instances_register_distinct_tokens_and_round_trip(plane):
    a, b = NameVault(plane), NameVault(plane)
    ta = a.register("person", "Ann Lee")
    tb = b.register("person", "Bob Ray")
    assert ta != tb and a.register("person", "Bob Ray") == tb
    assert a.detokenise(f"{ta} {tb}") == "Ann Lee Bob Ray" and b.detokenise(f"{ta} {tb}") == "Ann Lee Bob Ray"


def test_concurrent_registers_never_share_a_token(plane):
    names = [f"Person Number{chr(97 + i)}x" for i in range(10)]
    vaults = [NameVault(plane) for _ in range(5)]
    toks = {}

    def work(i):
        toks[i] = vaults[i % 5].register("person", names[i])
    ts = [threading.Thread(target=work, args=(i,)) for i in range(10)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(set(toks.values())) == 10
    v = NameVault(plane)
    assert sorted(v.detokenise(t) for t in toks.values()) == sorted(names)


# ---- H3 / M5: folding
@pytest.mark.parametrize("text", [
    "North\nwind Traders", "North\twind\tTraders", "North\x0bwind  Traders", "North-\nwind Traders",
    "North​wind Tra​ders", "NORTHWIND   TRADERS", "Nоrthwind Traders",  # Cyrillic o
])
def test_names_split_by_whitespace_controls_zero_width_or_lookalikes(plane, transport, text):
    gw, v, _ = make_gateway(plane, transport)
    v.register("company", "Northwind Traders")
    try:
        gw.send_model_prompt("m1", {"question": f"about {text} today"})
    except EgressBlocked as e:  # a name split inside a word is refused rather than swapped
        assert e.reason_code == "vault_name" and transport.calls == []
        return
    body = transport.calls[0][1].decode()
    assert "COMPANY_001" in body and "orthwind" not in body and "raders" not in body


def test_json_escaped_whitespace_cannot_hide_a_name(plane, transport):
    gw, v, _ = make_gateway(plane, transport)
    v.register("person", "Jo Park")
    for s in ("Jo\nPark", "Jo\u000bPark", "Jo Park", "J​o Park"):
        gw.send_model_prompt("m1", {"question": s})
        assert b"Park" not in transport.calls[-1][1]


def test_diacritics_fold(plane):
    v = NameVault(plane)
    v.register("person", "Zoe Muller")
    assert v.tokenise("hi Zoë Müller!") == "hi PERSON_001!"
    assert v.contains_name("ZOË MÜLLER") is True
    w = NameVault(plane)
    w.register("person", "Zoë Müller")  # the accented spelling folds the same way
    assert w.tokenise("Zoe Muller") != "Zoe Muller"


def test_short_name_zero_width_and_whole_word(plane):
    v = NameVault(plane)
    v.register("person", "Jo")
    assert v.tokenise("hi J​o and Joan") == "hi PERSON_001 and Joan"
    assert v.contains_name("J​o") and not v.contains_name("Joan analysis")


def test_international_phone_and_at_dot_email_and_token_scrub(plane):
    v = NameVault(plane)
    out = v.tokenise("call +44 20 7946 0958 or mail ann at corp dot example")
    assert "7946" not in out and "corp" not in out and "PHONE_001" in out and "EMAIL_001" in out
    assert v.contains_name("ring +44 20 7946 0958") and v.contains_name("a@b.example")
    v.register("company", "Company")  # a name equal to a token prefix must not block tokens
    assert v.contains_name(v.tokenise("x Company y")) is False


def test_unregistered_token_blocks_internet_query(plane, transport):
    gw, v, _ = make_gateway(plane, transport, policy_on=("m1",))
    v.register("person", "Ann Lee")
    for q in ("who is PERSON_001", "who is PERSON_777", "Ann Lee"):
        blocked(gw, transport, plane, "vault_name", "m1", f"https://{NET_HOST}/", q, fn=gw.internet_query)


# ---- B6 / L3: policy-owned hosts, plane match
def test_internet_hosts_validated_atomic_default_empty(plane, store):
    p = EgressPolicy(plane)
    assert p.internet_hosts() == []
    for bad in ("https://a.example", "a.example:8080", "u@a.example", "A.Example", "a.example/x", "localhost", ""):
        with pytest.raises(ValueError):
            p.set_internet_hosts([bad])
    p.set_internet_hosts(["b.example", "a.example"])
    p.set_internet("m1", True)  # does not wipe the hosts
    assert EgressPolicy(plane).internet_hosts() == ["a.example", "b.example"]
    assert EgressPolicy(store.create("beta-co")).internet_hosts() == []
    (plane.area("context") / "egress_policy.json").write_text("{broken")
    assert EgressPolicy(plane).internet_hosts() == []


def test_gateway_uses_policy_hosts_at_call_time(plane, transport):
    gw, _, policy = make_gateway(plane, transport, internet_hosts=(), policy_on=("m1",))
    blocked(gw, transport, plane, "destination_not_allowed", "m1", f"https://{NET_HOST}/", "rates", fn=gw.internet_query)
    policy.set_internet_hosts([NET_HOST])
    assert gw.internet_query("m1", f"https://{NET_HOST}/", "rates").outside is True


def test_gateway_refuses_mixed_planes(plane, store, transport):
    other = store.create("beta-co")
    with pytest.raises(ValueError):
        EgressGateway(plane, NameVault(other), EgressPolicy(plane), model_allowlist=[MODEL_HOST], transport=transport)
    with pytest.raises(ValueError):
        EgressGateway(plane, NameVault(plane), EgressPolicy(other), model_allowlist=[MODEL_HOST], transport=transport)


# ---- B3: URL path, query, fragment
@pytest.mark.parametrize("suffix", [
    "/Northwind%20Traders", "/s?q=Northwind+Traders", "/s?q=Northwind%20Traders", "/s?q=Northwind%2520Traders",
    "/s?q=Northwind%252520Traders", "/NorthwindTraders", "/a/north%0Awind%20traders", "/s?q=a%40b.example",
    "/s?acct=123456789012", "/s?x=PERSON_001",
])
def test_names_in_url_path_or_query_blocked(plane, transport, suffix):
    gw, v, _ = make_gateway(plane, transport, policy_on=("m1",))
    v.register("company", "Northwind Traders")
    blocked(gw, transport, plane, "vault_name", "m1", f"https://{NET_HOST}{suffix}", "public words", fn=gw.internet_query)


def test_url_fragment_and_over_encoding_refused(plane, transport):
    gw, _, _ = make_gateway(plane, transport, policy_on=("m1",))
    blocked(gw, transport, plane, "destination_not_allowed", "m1", f"https://{NET_HOST}/x#frag", "q", fn=gw.internet_query)
    from urllib.parse import quote
    deep = "a b"
    for _ in range(12):
        deep = quote(deep, safe="")
    blocked(gw, transport, plane, "destination_not_allowed", "m1", f"https://{NET_HOST}/{deep}", "q", fn=gw.internet_query)


def test_public_url_with_query_passes_and_log_keeps_host_only(plane, transport):
    gw, _, _ = make_gateway(plane, transport, policy_on=("m1",))
    gw.internet_query("m1", f"https://{NET_HOST}/search?q=policy+rate", "policy rate")
    line = log_lines(plane)[-1]
    assert line["host"] == NET_HOST
    assert "search" not in json.dumps(line) and "policy" not in json.dumps(line)


def test_model_url_is_fixed_and_rechecked_for_new_names(plane, transport):
    gw, v, _ = make_gateway(plane, transport, model_url=f"https://{MODEL_HOST}/v1/Northwind")
    v.register("company", "Northwind")
    blocked(gw, transport, plane, "vault_name", "m1", GOOD)


# ---- B4: log before send
def test_log_line_exists_before_transport_runs(plane):
    seen = []

    def spy(url, body):
        seen.append(log_lines(plane))
        return "ok"
    gw, _, _ = make_gateway(plane, spy)
    gw.send_model_prompt("m1", GOOD)
    assert len(seen[0]) == 1 and seen[0][0]["decision"] == "sent" and len(log_lines(plane)) == 1


def test_log_write_failure_after_open_blocks_send(plane, transport, monkeypatch):
    gw, _, _ = make_gateway(plane, transport)

    def boom(fd):
        raise OSError("no space")
    monkeypatch.setattr("sh_platform.egress.gateway.os.fsync", boom)
    e = blocked_no_line(gw, transport)
    assert e.reason_code == "log_unavailable" and "nothing was sent" in e.message


def blocked_no_line(gw, transport):
    with pytest.raises(EgressBlocked) as e:
        gw.send_model_prompt("m1", GOOD)
    assert transport.calls == []
    return e.value


def test_log_fields_have_no_control_characters(plane, transport):
    gw, _, _ = make_gateway(plane, transport)
    gw.send_model_prompt("m1\nFAKE LINE\x00 ", GOOD)
    raw = (plane.area("context") / "egress_log.jsonl").read_text()
    assert len(raw.splitlines()) == 1 and "FAKE LINE" in raw and "\x00" not in raw and " " not in raw


def test_transport_reason_code_kept_in_log(plane):
    t = make_httpx_transport("SH_TEST_NO_SUCH_KEY", model_hosts=[MODEL_HOST])
    gw, _, _ = make_gateway(plane, t, internet_transport=Transport())
    with pytest.raises(EgressBlocked) as e:
        gw.send_model_prompt("m1", GOOD)
    assert e.value.reason_code == "no_credential"
    assert [x["reason_code"] for x in log_lines(plane)] == ["", "no_credential"]


# ---- P1: malformed payloads are logged
@pytest.mark.parametrize("payload", [None, "text", 5, {"question": 5}, {"facts": "x"}, {"messages": 5},
                                     {"tools": {}}, {"messages": [5]}, {"tools": [5]}])
def test_malformed_payload_is_logged_bad_payload(plane, transport, payload):
    gw, _, _ = make_gateway(plane, transport)
    blocked(gw, transport, plane, "bad_payload", "m1", payload)


def test_internet_query_not_a_string_is_bad_payload(plane, transport):
    gw, _, _ = make_gateway(plane, transport, policy_on=("m1",))
    blocked(gw, transport, plane, "bad_payload", "m1", f"https://{NET_HOST}/", 5, fn=gw.internet_query)


# ---- structure mutants
def test_structure_checks(plane, transport):
    gw, _, _ = make_gateway(plane, transport)
    blocked(gw, transport, plane, "raw_rows", "m1", {"messages": [{"role": "user", "content": "x", "extra": "y"}]})
    blocked(gw, transport, plane, "bad_payload", "m1", {"messages": [{"role": "user", "content": 5}]})
    blocked(gw, transport, plane, "raw_rows", "m1", {"tools": [{"name": "t", "description": "d", "parameters": [], "x": 1}]})
    blocked(gw, transport, plane, "bad_payload", "m1", {"tools": [{"name": 5, "description": "d", "parameters": []}]})
    blocked(gw, transport, plane, "bad_payload", "m1", {"tools": [{"name": "t", "description": "d", "parameters": [5]}]})
    blocked(gw, transport, plane, "suppressed_figure", "m1",
            {"question": "q", "facts": [{"label": "a", "value": 1, "group_size": True}]})
    blocked(gw, transport, plane, "suppressed_figure", "m1",
            {"question": "q", "facts": [{"label": "a", "value": "1", "group_size": 9}]})


def test_empty_allowlist_and_url_fallback(plane, transport):
    gw, _, _ = make_gateway(plane, transport, model_allowlist=(), model_url=None)
    blocked(gw, transport, plane, "destination_not_allowed", "m1", GOOD)
    gw2, _, _ = make_gateway(plane, transport, model_url=None)  # falls back to https://<first host>
    gw2.send_model_prompt("m1", GOOD)
    assert transport.calls[0][0] == f"https://{MODEL_HOST}"


def test_no_userinfo_no_fragment_internet(plane, transport):
    gw, _, _ = make_gateway(plane, transport, policy_on=("m1",))
    for d in (f"https://u@{NET_HOST}/", f"https://{NET_HOST}/#a", f"https://{NET_HOST}/\n"):
        blocked(gw, transport, plane, "destination_not_allowed", "m1", d, "q", fn=gw.internet_query)


# ---- H1: key header never goes to internet hosts
def test_internet_query_never_carries_authorization(plane, monkeypatch):
    monkeypatch.setenv("SH_TEST_FAKE_KEY", "FAKE-PLACEHOLDER-not-a-secret")
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, text="reply")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    model_t = make_httpx_transport("SH_TEST_FAKE_KEY", model_hosts=[MODEL_HOST], client=client)
    net_t = make_httpx_transport(None, client=client)
    gw, _, _ = make_gateway(plane, model_t, internet_transport=net_t, policy_on=("m1",))
    gw.internet_query("m1", f"https://{NET_HOST}/s", "rates")
    gw.send_model_prompt("m1", GOOD)
    assert "authorization" not in seen[0].headers and seen[1].headers["authorization"].startswith("Bearer ")
    # even the model transport refuses to add the key for a non-model host
    seen.clear()
    model_t(f"https://{NET_HOST}/s", b"{}")
    assert "authorization" not in seen[0].headers
    log = (plane.area("context") / "egress_log.jsonl").read_text()
    assert "FAKE-PLACEHOLDER" not in log and "FAKE-PLACEHOLDER" not in repr(gw) + repr(model_t)


def test_default_internet_transport_has_no_key(plane, monkeypatch):
    monkeypatch.setenv("SH_TEST_FAKE_KEY", "FAKE-PLACEHOLDER-not-a-secret")
    gw = EgressGateway(plane, NameVault(plane), EgressPolicy(plane), model_allowlist=[MODEL_HOST],
                       transport=Transport())
    assert gw.internet_transport is not gw.transport


def test_redirects_are_not_followed(monkeypatch):
    hits = []

    def handler(req):
        hits.append(str(req.url))
        return httpx.Response(302, headers={"location": "https://evil.test/"})
    t = make_httpx_transport(None, client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(httpx.HTTPStatusError):
        t(f"https://{NET_HOST}/", b"{}")
    assert hits == [f"https://{NET_HOST}/"]


def test_httpx_client_made_by_transport_is_closed(monkeypatch):
    made = []
    real = httpx.Client

    class Spy(real):
        def __init__(self, *a, **k):
            super().__init__(*a, transport=httpx.MockTransport(lambda r: httpx.Response(200, text="r")), **k)
            made.append(self)
    monkeypatch.setattr(httpx, "Client", Spy)
    assert make_httpx_transport(None)(f"https://{NET_HOST}/", b"{}") == "r"
    assert made and made[0].is_closed


def test_outside_material_not_detokenised(plane, transport):
    gw, v, _ = make_gateway(plane, transport, policy_on=("m1",))
    v.register("person", "Ann Lee")
    transport.reply = "PERSON_001 says hi"
    r = gw.internet_query("m1", f"https://{NET_HOST}/", "rates")
    assert r.text == "PERSON_001 says hi" and r.outside is True


# ---- M2: structural rows only
@pytest.mark.parametrize("text", [
    '{"a":1}\n{"a":2}', "[[1,52000],[2,61000]]", '[{"a":1},{"a":2}]', 'see [{"a": 1}, {"a": 2}]',
])
def test_json_rows_detected(text):
    assert text_has_rows(text)


def test_table_shaped_text_is_not_detected_by_design():
    for t in ("E1,52000\nE2,61000", "Ann: 52000\nBob: 61000", "- id: 1\n  pay: 5", "id=1 pay=2\nid=2 pay=3"):
        assert not text_has_rows(t)


def test_rows_in_message_tool_and_label_json_are_seen(plane, transport):
    gw, _, _ = make_gateway(plane, transport)
    rows = '[{"a":"x"},{"a":"y"}]'
    blocked(gw, transport, plane, "raw_rows", "m1", {"messages": [{"role": "user", "content": rows}]})
    blocked(gw, transport, plane, "raw_rows", "m1", {"tools": [{"name": "t", "description": rows, "parameters": []}]})
    blocked(gw, transport, plane, "raw_rows", "m1", {"question": "see " + rows})
    blocked(gw, transport, plane, "raw_rows", "m1", {"summary": rows})


def test_payload_size_cap(plane, transport):
    gw, _, _ = make_gateway(plane, transport)
    blocked(gw, transport, plane, "payload_too_large", "m1", {"question": "w " * 100_001})


@pytest.mark.parametrize("text", ["[{}" * 8000, '{"a":' * 8000, "[" * 20000, "a," * 100000, "1" * 200000, "\n".join(["1,2"] * 50000)],
                         ids=["objs", "keys", "brackets", "commas", "digits", "lines"])
def test_row_and_number_checks_are_fast(text):
    sup = SuppressedFigures()
    sup.add({"label": "x", "value": 12345, "group_size": 1})
    start = time.perf_counter()
    text_has_rows(text)
    json_findings(text)
    sup.appears_in(text)
    assert time.perf_counter() - start < 30  # quadratic code takes minutes; wide headroom for a busy machine


# ---- H4: suppressed figures by value
@pytest.mark.parametrize("quoted", [
    "1234", "1234.0", "1234.00", "1,234", "1.234", "1 234", "1 234", "1 234", "１２３４",
    "1.234e3", "1.234E+3", "1,234.0", "down -1234", "fell by 1234 units", "1.234,00",
])
def test_suppressed_value_caught_in_any_format(quoted):
    sup = SuppressedFigures()
    sup.add({"label": "x", "value": 1234, "group_size": 2})
    assert sup.appears_in(f"result: {quoted} total")


def test_suppressed_decimal_negative_and_scaled():
    sup = SuppressedFigures()
    sup.add({"label": "x", "value": 1234.5, "group_size": 2})
    for q in ("1234.50", "1,234.5", "1.2345e3", "1 234,5", "1.234,5"):
        assert sup.appears_in(q)
    neg = SuppressedFigures()
    neg.add({"label": "x", "value": -50, "group_size": 2})
    assert neg.appears_in("down 50 points") and neg.appears_in("−50")
    big = SuppressedFigures()
    big.add({"label": "x", "value": 1234567, "group_size": 2})
    for q in ("1.23 million", "1.2 million", "1.234 million", "1 mn", "1,234.567 thousand", "1234 k", "1 234 567", "1.234.567"):
        assert big.appears_in(q), q
    assert not big.appears_in("2.5 million and 12 345 and 999")


def test_small_suppressed_value_blocks_standalone_digit_only():
    sup = SuppressedFigures()
    sup.add({"label": "x", "value": 3, "group_size": 1})
    assert sup.appears_in("we saw 3 cases") and not sup.appears_in("we saw 33 cases, 13, 2024")


def test_gateway_blocks_reworded_suppressed_figure(plane, transport):
    gw, _, _ = make_gateway(plane, transport)
    _, sup = filter_facts([{"label": "a", "value": 52000, "group_size": 2}])
    for q in ("pay is 52,000", "pay is 52000.00", "pay is 52 000", "pay is 5.2e4", "pay is ５２000"):
        blocked(gw, transport, plane, "suppressed_figure", "m1", {"question": q}, suppressed=sup)
    gw.send_model_prompt("m1", {"question": "pay is 61000"}, suppressed=sup)


def test_group_size_true_rejected_explicitly():
    allowed, sup = filter_facts([{"label": "a", "value": 1, "group_size": True}])
    assert allowed == [] and len(sup) == 1


# ---- B5: model client
def test_parse_reply():
    assert parse_reply("plain words") == ("plain words", [])
    assert parse_reply('{"text": "hi"}') == ("hi", [])
    t, calls = parse_reply(json.dumps({"text": "go", "tool_calls": [
        {"name": "count_x", "arguments": {"a": 1}, "id": "c1"},
        {"name": "no_args"}, {"arguments": {}}, {"name": "bad", "arguments": "{oops"}, "junk",
        {"name": "auto", "arguments": {}}]}))
    assert t == "go" and calls == [ToolCall("count_x", {"a": 1}, "c1"), ToolCall("auto", {}, "call_5")]
    assert parse_reply("{broken json") == ("{broken json", [])
    assert parse_reply('{"no_text": 1}') == ('{"no_text": 1}', [])
    assert parse_reply('["a"]') == ('["a"]', [])
    assert parse_reply('{"text": "x", "tool_calls": "no"}') == ("x", [])


def test_model_client_tools_and_reply_round_trip(plane, transport):
    gw, v, _ = make_gateway(plane, transport)
    v.register("person", "Zelda Quark")
    transport.reply = json.dumps({"text": "PERSON_001 ok", "tool_calls": [
        {"name": "lookup", "arguments": {"who": "PERSON_001"}, "id": "t1"}]})
    tools = [{"name": "lookup", "description": "Find Zelda Quark", "parameters": {"properties": {"who": {"type": "string"}, "n": {}}}},
             {"name": "plain"}]
    r = EgressModelClient(gw).complete("m1", [{"role": "user", "content": "hi"}], tools=tools)
    body = json.loads(transport.calls[0][1])
    assert body["tools"][0] == {"name": "lookup", "description": "Find PERSON_001", "parameters": ["who", "n"]}
    assert body["tools"][1] == {"name": "plain", "description": "", "parameters": []}
    assert r.text == "Zelda Quark ok" and r.outside is False
    assert r.tool_calls == [ToolCall("lookup", {"who": "Zelda Quark"}, "t1")]


def test_model_client_uses_per_call_suppressed(plane, transport):
    gw, _, _ = make_gateway(plane, transport)
    c = EgressModelClient(gw)
    _, sup = filter_facts([{"label": "a", "value": 777, "group_size": 1}])
    with pytest.raises(EgressBlocked):
        c.complete("m1", [{"role": "user", "content": "it is 777"}], suppressed=sup)
    assert transport.calls == []
    c.complete("m1", [{"role": "user", "content": "it is 777"}])  # a later call has its own (no) set
    assert len(transport.calls) == 1
