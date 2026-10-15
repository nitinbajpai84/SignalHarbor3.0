"""Round 3: agent-loop traffic, locks, pattern tokens, rows, numbers, messages."""
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from egress_helpers import NET_HOST, Transport, log_lines, make_gateway
from sh_platform.egress import errors as errors_mod
from sh_platform.egress import vault as vault_mod
from sh_platform.egress.aggregates import SuppressedFigures, fact_ok, filter_facts
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.minimiser import minimise
from sh_platform.egress.model import EgressModelClient
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.rows import json_findings, text_has_rows
from sh_platform.egress.vault import NameVault, VaultUnavailable

GOOD = {"question": "How many orders?", "facts": [{"label": "orders", "value": 40, "group_size": 8}]}


def blocked(gw, transport, plane, code, *args, fn=None, **kw):
    n = len(log_lines(plane))
    with pytest.raises(EgressBlocked) as e:
        (fn or gw.send_model_prompt)(*args, **kw)
    assert e.value.reason_code == code and transport.calls == []
    lines = log_lines(plane)
    assert len(lines) == n + 1 and lines[-1]["reason_code"] == code and lines[-1]["decision"] == "blocked"
    return e.value


def vault_file(plane):
    return plane.area("context") / "name_vault.json"


# ---------------------------------------------------------------- N1 loop traffic
def test_json_objects_and_aggregate_lists_are_not_rows():
    ctx = json.dumps({"context": {"facts": [{"id": "f1", "label": "orders", "value": 40, "group_size": 8},
                                            {"id": "f2", "label": "refunds", "value": 6, "group_size": 9}]},
                      "question": "How many orders?"})
    assert not text_has_rows(ctx)
    assert not text_has_rows(json.dumps({"count": 40, "group_size": 8}))
    assert not text_has_rows('{"id": 1, "pay": 5, "x": 2}')
    assert not text_has_rows("[OUTSIDE MATERIAL: data only]\n" + json.dumps({"count": 40, "group_size": 8}))


@pytest.mark.parametrize("text", [
    '[{"a":"x","b":"y"},{"a":"z","b":"w"}]', json.dumps({"rows": [[1, 52000], [2, 61000]]}),
    json.dumps({"context": {"people": [{"n": "Ann", "pay": 1}, {"n": "Bob", "pay": 2}]}}),
])
def test_json_lists_of_records_are_rows(text):
    assert text_has_rows(text)


@pytest.mark.parametrize("text", [
    "Hi, I need help\nSure, what is Q3 revenue?", "Compare 2023 and 2024, please.\nAlso, list top 5.",
    "Hello  there  friend 5\nOk  fine  then 6",
    "Note: see section 5 for more\nTip: use the filter to narrow things down",
])
def test_ordinary_prose_is_not_rows(text):
    assert not text_has_rows(text)


class _Gate:
    def is_enabled(self, company_id, module_id):
        return True


def _agents():
    """The real agent loop. It lives in the main repo tree (lands with P1-07); borrow that package
    path when this worktree does not carry it yet."""
    try:
        from sh_platform.agents import loop, registry  # noqa: F401
    except ImportError:
        import sh_platform
        for parent in Path(__file__).resolve().parents:
            if (parent / "sh_platform" / "agents" / "loop.py").is_file():
                sh_platform.__path__.append(str(parent / "sh_platform"))
                break
        else:
            pytest.skip("sh_platform.agents is not available in this tree")
    from sh_platform.agents.loop import run_agent
    from sh_platform.agents.registry import ToolRegistry
    return run_agent, ToolRegistry


def _scripted(replies):
    calls = []

    def transport(url, body):
        calls.append(body)
        return replies[min(len(calls), len(replies)) - 1]
    transport.calls = calls
    return transport


def test_real_agent_loop_runs_through_egress_client(plane):
    run_agent, ToolRegistry = _agents()
    t = _scripted([json.dumps({"text": "", "tool_calls": [
                       {"name": "count_orders", "arguments": {"region": "north"}, "id": "c1"}]}),
                   "There were 40 orders."])
    gw, _, _ = make_gateway(plane, t)
    reg = ToolRegistry(_Gate())
    reg.register("m1", "count_orders", lambda region: {"count": 40, "group_size": 8}, read_only=True,
                 description="Count orders", parameters={"region": "a region name"})
    ctx = {"facts": [{"id": "f1", "label": "orders", "value": 40, "group_size": 8},
                     {"id": "f2", "label": "refunds", "value": 6, "group_size": 9}]}
    res = run_agent(EgressModelClient(gw), reg, "acme", "m1", "North", "You are helpful.", ctx, "How many orders?", fast={"off": True})
    assert res.status == "done" and "40" in res.text and res.tools_called == ["count_orders"]
    assert len(t.calls) == 2
    lines = log_lines(plane)
    assert [x["decision"] for x in lines] == ["sent", "sent"] and lines[0]["attempt"] != lines[1]["attempt"]
    assert b"count_orders" in t.calls[0] and b'\\"count\\": 40' in t.calls[1]


def test_real_agent_loop_blocks_raw_rows_in_a_tool_result(plane):
    run_agent, ToolRegistry = _agents()
    t = _scripted([json.dumps({"text": "", "tool_calls": [{"name": "list_names", "arguments": {}, "id": "c1"}]}),
                   "never reached"])
    gw, _, _ = make_gateway(plane, t)
    reg = ToolRegistry(_Gate())
    reg.register("m1", "list_names", lambda: [{"a": "x", "b": "y"}, {"a": "z", "b": "w"}], read_only=True,
                 description="Names", parameters={})
    res = run_agent(EgressModelClient(gw), reg, "acme", "m1", "North", "You are helpful.", {}, "List them")
    assert res.status == "error"
    assert len(t.calls) == 1  # the second model call never reached the transport
    last = log_lines(plane)[-1]
    assert last["decision"] == "blocked" and last["reason_code"] == "raw_rows"


# ---------------------------------------------------------------- N2 locks, attempt id
def test_thirty_concurrent_registers_all_succeed(plane):
    names = [f"Concurrent Person {chr(97 + i // 26)}{chr(97 + i % 26)}x" for i in range(30)]
    errors, toks = [], {}

    def work(i):
        try:
            toks[i] = NameVault(plane).register("person", names[i])
        except Exception as e:  # noqa: BLE001 - the test reports any failure
            errors.append(repr(e))
    ts = [threading.Thread(target=work, args=(i,)) for i in range(30)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert errors == [] and len(set(toks.values())) == 30
    v = NameVault(plane)
    assert sorted(v.detokenise(t) for t in toks.values()) == sorted(names)
    assert not v._lock.exists()


def test_attempt_id_pairs_sent_and_failed_lines(plane):
    def bad(url, body):
        raise RuntimeError("x")
    gw, _, _ = make_gateway(plane, bad)
    for _ in range(2):
        with pytest.raises(EgressBlocked):
            gw.send_model_prompt("m1", GOOD)
    a, b, c, d = log_lines(plane)
    assert a["attempt"] == b["attempt"] and c["attempt"] == d["attempt"] and a["attempt"] != c["attempt"]
    assert re.fullmatch(r"[0-9a-f]{8}", a["attempt"])


# ---------------------------------------------------------------- SEC-N1 locks
def test_stale_garbage_lock_is_broken(plane, monkeypatch):
    v = NameVault(plane)
    v._lock.write_text("garbage")
    old = time.time() - 120
    os.utime(v._lock, (old, old))
    with pytest.raises(VaultUnavailable):  # unreadable owner: only the hard limit breaks it
        monkeypatch.setattr(vault_mod, "_LOCK_WAIT", 0.1)
        v.register("person", "Ann Lee")
    old = time.time() - 700
    os.utime(v._lock, (old, old))
    assert v.register("person", "Ann Lee") == "PERSON_001"
    assert not v._lock.exists()


def test_lock_of_dead_process_is_broken(plane):
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    v = NameVault(plane)
    v._lock.write_text(json.dumps({"pid": dead.pid, "token": "dead", "t": time.time() - 120}))
    assert v.register("person", "Ann Lee") == "PERSON_001"


def test_lock_of_live_process_is_never_stolen(plane, monkeypatch):
    monkeypatch.setattr(vault_mod, "_LOCK_WAIT", 0.2)
    v = NameVault(plane)
    mine = json.dumps({"pid": os.getpid(), "token": "live", "t": time.time() - 30})  # live and under 60 s
    v._lock.write_text(mine)
    with pytest.raises(VaultUnavailable):
        v.register("person", "Ann Lee")
    assert v._lock.read_text() == mine and not vault_file(plane).exists()


def test_lock_older_than_hard_limit_is_broken_even_if_owner_alive(plane):
    v = NameVault(plane)
    v._lock.write_text(json.dumps({"pid": os.getpid(), "token": "old", "t": time.time() - 601}))
    assert v.register("person", "Ann Lee") == "PERSON_001"


@pytest.mark.parametrize("content", ['{"pid": 1, "token": "x", "t": "soon"}', '{"pid": "x"}', "[1, 2]", "\x00\x01"])
def test_malformed_lock_is_breakable_only_after_hard_age(plane, monkeypatch, content):
    monkeypatch.setattr(vault_mod, "_LOCK_WAIT", 0.1)
    v = NameVault(plane)
    v._lock.write_text(content)
    with pytest.raises(VaultUnavailable):
        v.register("person", "Ann Lee")
    old = time.time() - 700
    os.utime(v._lock, (old, old))
    assert v.register("person", "Ann Lee") == "PERSON_001"


def test_owner_removes_only_its_own_lock(plane):
    v = NameVault(plane)
    with v._locked():
        v._lock.write_text(json.dumps({"pid": os.getpid(), "token": "someone-else", "t": time.time()}))
    assert v._lock.exists() and "someone-else" in v._lock.read_text()


def test_slow_holder_does_not_lose_the_waiters_entry(plane, transport, monkeypatch):
    holder, waiter = NameVault(plane), NameVault(plane)
    real_save = holder._save
    in_lock = threading.Event()

    def slow_save(entries):
        in_lock.set()
        time.sleep(0.5)
        real_save(entries)
    holder._save = slow_save
    t = threading.Thread(target=lambda: holder.register("person", "Holder Person"))
    t.start()
    in_lock.wait(2)
    waiter.register("person", "Waiter Person")
    t.join()
    final = NameVault(plane)
    assert final.contains_name("Holder Person") and final.contains_name("Waiter Person")
    assert len(json.loads(vault_file(plane).read_text())["entries"]) == 2
    gw, _, _ = make_gateway(plane, transport)
    gw.send_model_prompt("m1", {"question": "Holder Person met Waiter Person"})
    assert b"Holder" not in transport.calls[0][1] and b"Waiter" not in transport.calls[0][1]


def test_waiter_gives_up_safely_when_holder_is_slow(plane, monkeypatch):
    monkeypatch.setattr(vault_mod, "_LOCK_WAIT", 0.1)
    holder, waiter = NameVault(plane), NameVault(plane)
    real_save = holder._save
    in_lock = threading.Event()

    def slow_save(entries):
        in_lock.set()
        time.sleep(0.5)
        real_save(entries)
    holder._save = slow_save
    t = threading.Thread(target=lambda: holder.register("person", "Holder Person"))
    t.start()
    in_lock.wait(2)
    with pytest.raises(VaultUnavailable):
        waiter.register("person", "Waiter Person")
    t.join()
    assert list(json.loads(vault_file(plane).read_text())["entries"].values())[0]["name"] == "Holder Person"


def test_large_vault_is_fast_and_lock_held_briefly(plane, transport, monkeypatch):
    entries = {f"PERSON_{i:03d}": {"kind": "person", "name": f"Firstname{i} Surname{i}x"} for i in range(1, 3001)}
    vault_file(plane).write_text(json.dumps({"entries": entries}))
    held = []
    real = NameVault._locked

    def timed(self):
        import contextlib

        @contextlib.contextmanager
        def cm():
            with real(self):
                t0 = time.perf_counter()
                try:
                    yield
                finally:
                    held.append(time.perf_counter() - t0)
        return cm()
    monkeypatch.setattr(NameVault, "_locked", timed)
    gw, _, _ = make_gateway(plane, transport)
    filler = ("The quick brown fox jumps over the lazy dog while markets stay calm today. " * 300)[:19_000]
    msgs = [{"role": "user", "content": filler} for _ in range(9)]
    msgs.append({"role": "user", "content": filler[:18_000] + " ask Firstname2999 Surname2999x and firstname7 surname7x"})
    start = time.perf_counter()
    gw.send_model_prompt("m1", {"messages": msgs})
    took = time.perf_counter() - start
    body = transport.calls[0][1].decode()
    assert "Firstname2999" not in body and "PERSON_2999" in body and "PERSON_007" in body
    assert took < 60 and held and max(held) < 10.0  # wide headroom for a busy machine; the lock is held per write, not per scan


def test_pattern_values_are_not_written_to_the_vault(plane):
    v = NameVault(plane)
    out = v.tokenise("mail a@b.example call +44 20 7946 0958 acct 123456789012")
    assert "b.example" not in out and "123456789012" not in out
    assert not vault_file(plane).exists()
    assert v.detokenise(out) == "mail a@b.example call +44 20 7946 0958 acct 123456789012"
    assert NameVault(plane).detokenise(out) == out  # another object never had them


def test_vault_cap_and_name_length(plane, monkeypatch):
    monkeypatch.setattr(vault_mod, "MAX_ENTRIES", 2)
    v = NameVault(plane)
    v.register("person", "Ann Lee")
    v.register("person", "Bob Ray")
    assert v.register("person", "ann lee") == "PERSON_001"  # existing name: not a new entry
    with pytest.raises(ValueError):
        v.register("person", "Cy Dee")
    with pytest.raises(ValueError):
        NameVault(plane).register("company", "x" * 201)


def test_hyphen_newline_inside_a_short_name(plane):
    v = NameVault(plane)
    v.register("person", "Jo")
    assert v.tokenise("hi J-\no there") == "hi PERSON_001 there"
    assert v.contains_name("J-\no")


# ---------------------------------------------------------------- N3 / L numbers
def _sup(v):
    s = SuppressedFigures()
    s.add({"label": "x", "value": v, "group_size": 1})
    return s


def test_small_value_ignores_known_tokens_real_dates_and_decimal_parts():
    s = _sup(2)
    assert not s.appears_in("PERSON_002 met on 2026-10-02, total 1,234.2", tokens={"PERSON_002"})
    assert s.appears_in("PERSON_002 is here", tokens=())  # an unknown token is not stripped
    assert s.appears_in("we saw 2 cases")
    assert s.appears_in("on 2026-13-02 or 2026-02-30")  # not real dates: matched as numbers
    assert s.appears_in("at 2026-10-01T10:30:02Z") and s.appears_in("at 2026-10-01T10:30:00.2Z")
    assert s.appears_in("at 2026-10-01T10:30:00+02:00")
    assert not _sup(234).appears_in("1,234.5")  # a thousands group is not a number of its own
    assert _sup(234).appears_in("234 and PERSON_001")


def test_gateway_passes_vault_tokens_to_the_figure_check(plane, transport):
    gw, v, _ = make_gateway(plane, transport)
    v.register("person", "Ann Lee")
    _, sup = filter_facts([{"label": "a", "value": 1, "group_size": 1}])
    gw.send_model_prompt("m1", {"question": "Ann Lee asked"}, suppressed=sup)  # PERSON_001 is stripped
    transport.calls.clear()
    blocked(gw, transport, plane, "suppressed_figure", "m1", {"question": "PERSON_009 sees 1"}, suppressed=sup)


# ---------------------------------------------------------------- structural JSON checks (round 4)
def test_json_object_with_small_group_blocks_and_joins_suppressed(plane, transport):
    gw, _, _ = make_gateway(plane, transport)
    sup = SuppressedFigures()
    body = json.dumps({"context": {"facts": [{"id": "f", "label": "pay", "value": 52000, "group_size": 3}]},
                       "question": "q"})
    blocked(gw, transport, plane, "suppressed_figure", "m1",
            {"messages": [{"role": "user", "content": body}]}, suppressed=sup)
    assert sup.appears_in("it was 52,000") and not sup.appears_in("3 groups")
    # the same figure typed into free text on a later call is now blocked too
    blocked(gw, transport, plane, "suppressed_figure", "m1", {"question": "pay 52000"}, suppressed=sup)


@pytest.mark.parametrize("obj", [
    {"count": 4, "group_size": 4}, {"count": 4, "group_size": "9"}, {"count": 4, "group_size": 9.0},
    {"count": 4, "group_size": True}, {"count": 4, "group_size": None}, {"label": "x", "value": 3},
    {"a": {"b": [{"label": "x", "value": 3}]}},
])
def test_bad_group_size_or_fact_without_group_is_suppressed_figure(plane, transport, obj):
    gw, _, _ = make_gateway(plane, transport)
    for field in ("messages", "question"):
        text = json.dumps(obj)
        payload = {"messages": [{"role": "user", "content": text}]} if field == "messages" else {"question": text}
        blocked(gw, transport, plane, "suppressed_figure", "m1", payload)


def test_valid_aggregates_pass_everywhere(plane, transport):
    gw, _, _ = make_gateway(plane, transport)
    ok = json.dumps({"context": {"facts": [{"label": "a", "value": 1, "group_size": 5}]}, "count": 7})
    gw.send_model_prompt("m1", {"messages": [{"role": "user", "content": ok}]})
    assert len(transport.calls) == 1


def test_size_caps(plane, transport):
    gw, _, _ = make_gateway(plane, transport)
    blocked(gw, transport, plane, "payload_too_large", "m1", {"messages": [{"role": "user", "content": "w" * 20_001}]})
    blocked(gw, transport, plane, "payload_too_large", "m1", {"question": "w" * 20_001})
    blocked(gw, transport, plane, "payload_too_large", "m1",
            {"messages": [{"role": "user", "content": json.dumps({"k": "w" * 20_001})[:-1] + '"}'}]})
    blocked(gw, transport, plane, "summary_too_long", "m1", {"summary": "w" * 1201})
    gw.send_model_prompt("m1", {"messages": [{"role": "user", "content": "w" * 20_000}]})


def test_json_findings_priorities():
    assert json_findings('[{"a":1},{"a":2}]') == ("raw_rows", [])
    code, bad = json_findings('[{"label":"x","value":3},{"a":2}]')
    assert code == "suppressed_figure" and bad == [{"label": "x", "value": 3}]
    assert json_findings("[" * 300)[0] in (None, "raw_rows")


@pytest.mark.parametrize("quoted", ["1'234", "1’234", "1_234", "1٬234", "12​34", "0x4d2",
                                    "0b10011010010", "0o2322", "¹²³⁴", "1​,234"])
def test_more_number_spellings(quoted):
    assert _sup(1234).appears_in(f"it was {quoted} in total")


def test_suppressed_figure_in_internet_query(plane, transport):
    gw, _, _ = make_gateway(plane, transport, policy_on=("m1",))
    _, sup = filter_facts([{"label": "a", "value": 52000, "group_size": 2}])
    blocked(gw, transport, plane, "suppressed_figure", "m1", f"https://{NET_HOST}/", "salary 52,000 in the sector",
            fn=gw.internet_query, suppressed=sup)
    blocked(gw, transport, plane, "suppressed_figure", "m1", f"https://{NET_HOST}/s?n=52000", "public words",
            fn=gw.internet_query, suppressed=sup)
    assert gw.internet_query("m1", f"https://{NET_HOST}/", "salary 61,000", suppressed=sup).outside is True


# ---------------------------------------------------------------- N4 messages
def test_every_reason_code_has_a_one_sentence_message():
    src = "".join(p.read_text(encoding="utf-8") for p in Path(errors_mod.__file__).parent.glob("*.py"))
    codes = set(re.findall(r'EgressBlocked\(\s*"([a-z_]+)"', src)) | set(re.findall(r'else "([a-z_]+_failed)"', src))
    assert {"vault_unavailable", "bad_payload", "payload_too_large", "transport_failed"} <= codes
    for code in codes:
        msg = EgressBlocked(code).message
        assert code in errors_mod._MESSAGES, code
        assert msg.endswith(".") and msg.count(". ") == 0 and "_" not in msg and len(msg.split()) >= 8
    assert EgressBlocked("something_new").message.endswith(".")


# ---------------------------------------------------------------- N5 / N6
def test_nan_and_inf_facts_refused(plane, transport):
    for bad in (float("nan"), float("inf"), float("-inf")):
        assert not fact_ok({"label": "a", "value": bad, "group_size": 9})
    gw, _, _ = make_gateway(plane, transport)
    blocked(gw, transport, plane, "suppressed_figure", "m1",
            {"question": "q", "facts": [{"label": "a", "value": float("nan"), "group_size": 9}]})
    payload, sup = minimise("q", [{"label": "a", "value": float("inf"), "group_size": 9}], {"a"})
    assert payload["facts"] == [] and len(sup) == 1


def test_huge_integer_reaches_bad_payload_and_is_logged(plane, transport):
    gw, _, _ = make_gateway(plane, transport)
    blocked(gw, transport, plane, "bad_payload", "m1",
            {"question": "q", "facts": [{"label": "a", "value": 10 ** 5000, "group_size": 9}]})


def test_unexpected_exception_in_prepare_is_bad_payload(plane, transport, monkeypatch):
    gw, v, _ = make_gateway(plane, transport)

    def boom(text):
        raise RuntimeError("surprise")
    monkeypatch.setattr(v, "tokenise", boom)
    blocked(gw, transport, plane, "bad_payload", "m1", GOOD)


def test_hand_edited_policy_hosts_are_filtered(plane, transport):
    (plane.area("context") / "egress_policy.json").write_text(json.dumps({
        "internet": {"m1": True},
        "internet_hosts": ["https://a.example", "ok.example", "A.Example", 5, "b.example:8080", "u@c.example", "x"]}))
    assert EgressPolicy(plane).internet_hosts() == ["ok.example"]
    gw, _, _ = make_gateway(plane, transport)  # rewrites the file with valid hosts; edit it by hand again
    (plane.area("context") / "egress_policy.json").write_text(json.dumps({
        "internet": {"m1": True}, "internet_hosts": ["https://a.example", "A.example"]}))
    blocked(gw, transport, plane, "destination_not_allowed", "m1", "https://a.example/", "q", fn=gw.internet_query)


def test_gateway_detokenise_surfaces_vault_unavailable(plane):
    def corrupting(url, body):
        vault_file(plane).write_text("{broken")
        return "PERSON_001 ok"
    gw, v, _ = make_gateway(plane, corrupting)
    v.register("person", "Ann Lee")
    with pytest.raises(EgressBlocked) as e:
        gw.send_model_prompt("m1", {"question": "about Ann Lee"})
    assert e.value.reason_code == "vault_unavailable"
    assert [x["decision"] for x in log_lines(plane)] == ["sent"]
    with pytest.raises(VaultUnavailable):
        v.detokenise("PERSON_001")
