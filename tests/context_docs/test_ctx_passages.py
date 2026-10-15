"""context_passages: what North's context gets, and that it passes the REAL egress gateway (D-032).

The 3 October lesson: text goes as plain text, never as JSON lists of objects. The payload built here has the shape of
the agent loop's own message, and is run through the gateway's real structure check and a real send with a stub transport."""
import json

import pytest

import ctx_files as F
from sh_platform.agents.guard import check_numbers
from sh_platform.context_docs import context_passages, retrieval
from sh_platform.context_docs.store import DocStore
from sh_platform.egress.aggregates import SuppressedFigures
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import EgressGateway, _check_structure
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.vault import NameVault

MODEL_HOST = "model.example.test"


class Transport:
    def __init__(self):
        self.calls = []

    def __call__(self, url, body):
        self.calls.append((url, body))
        return "ok"


def gateway(plane, transport):
    vault = NameVault(plane)
    gw = EgressGateway(plane, vault, EgressPolicy(plane), model_allowlist=[MODEL_HOST],
                       model_url=f"https://{MODEL_HOST}/v1", transport=transport)
    return gw, vault


def loop_payload(passages: str, question: str) -> dict:
    """The shape the agent loop sends: the context and the question as one JSON object inside a user message."""
    return {"messages": [{"role": "system", "content": "You are North."},
                         {"role": "user", "content": json.dumps({"context": {"company_documents": passages}, "question": question})}]}


def plain_payload(passages: str, question: str) -> dict:
    """The passages as the plain text of a message, with nothing around them."""
    return {"question": question, "messages": [{"role": "user", "content": passages}]}


def test_no_documents_means_an_empty_string(plane):
    assert context_passages(plane, "north", "What is our target allocation?") == ""
    DocStore(plane).upload("north", "a", "coffee.txt", F.COFFEE)
    assert context_passages(plane, "north", "What is our target allocation?") == ""  # nothing matches
    assert context_passages(plane, "north", "") == ""


def test_only_the_few_relevant_passages_go_and_never_the_whole_file(plane):
    s = DocStore(plane)
    paragraphs = [f"Section {i}. " + ("Rebalancing note about growth assets and drift. " * 20) + f"Marker{i:02d}." for i in range(30)]
    s.upload("north", "a", "long-policy.md", "\n\n".join(paragraphs).encode())
    assert len(s.own_chunks("north")) > 10
    out = context_passages(plane, "north", "rebalancing growth assets drift")
    assert out.count(retrieval._UNTRUSTED_BEGIN) == retrieval.TOP_PASSAGES
    assert len(out) < 5000
    assert "Marker29" not in out or "Marker00" not in out  # not the whole document


def test_the_passages_pass_the_real_gateway_with_names_masked(plane):
    s = DocStore(plane)
    s.upload("north", "a", "calls.md", F.CAPITAL_CALLS + b" The relationship manager is Margaret Ellery.", title="Capital calls")
    s.upload("north", "a", "rows.json", b'{"manager": "Evergreen Partners", "fund": "Fund A"}\n'
                                         b'{"manager": "Harbor Row", "fund": "Fund B"}\n'
                                         b'[1, 2, 3, 4]\n[5, 6, 7, 8]\n', title="Capital calls rows")
    question = "When does Evergreen Partners call capital and who is the manager?"
    passages = context_passages(plane, "north", question)
    assert "Margaret" not in passages and "Evergreen" not in passages  # masked before they leave, vault or no vault
    assert "{" not in passages.replace("> {", "")
    for payload in (loop_payload(passages, question), plain_payload(passages, question)):
        _check_structure(payload, SuppressedFigures())  # the gateway's real structure check

    transport = Transport()
    gw, vault = gateway(plane, transport)
    vault.register("fund", "Evergreen Partners")  # the question is the caller's own text: the vault tokenises it, as before
    for payload in (loop_payload(passages, question), plain_payload(passages, question)):
        gw.send_model_prompt("m1_intent", payload)
    assert len(transport.calls) == 2
    for _url, body in transport.calls:
        text = body.decode("utf-8")
        assert "Margaret" not in text and "Ellery" not in text and "Evergreen" not in text and "[a name]" in text
        assert retrieval._UNTRUSTED_BEGIN in text


def test_a_name_in_a_document_is_masked_without_anyone_registering_it(plane):
    """B1 of M2-P01: the same context_passages feeds North and Lens, so the mask is applied once, where they meet."""
    DocStore(plane).upload("north", "a", "calls.md", b"Capital calls are due by date. The relationship manager is Margaret Ellery. "
                                                      b"Ask Dr Hammond, or Mr Ng, about Monday notices at the Finance Committee.", title="Calls")
    out = context_passages(plane, "north", "capital calls relationship manager notices")
    assert out and "[a name]" in out and retrieval._UNTRUSTED_BEGIN in out  # the untrusted wrapper stays
    for gone in ("Margaret", "Ellery", "Hammond", "Ng,"):
        assert gone not in out
    assert "Monday" in out and "Finance Committee" in out  # ordinary business words stay


def test_a_json_file_cannot_make_the_payload_look_like_rows(plane):
    DocStore(plane).upload("north", "a", "rows.json", b'{"manager": "Evergreen", "note": "capital call in March"}\n'
                                                       b'{"manager": "Harbor Row", "note": "capital call in September"}\n')
    passages = context_passages(plane, "north", "capital call March September manager")
    assert passages
    _check_structure(plain_payload(passages, "capital calls"), SuppressedFigures())
    bare = "\n".join(ln.removeprefix("> ") for ln in passages.splitlines())  # what it would be without the quote marks
    with pytest.raises(EgressBlocked):
        _check_structure(plain_payload(bare, "capital calls"), SuppressedFigures())


def test_a_figure_in_a_document_is_not_a_recorded_fact(plane):
    DocStore(plane).upload("north", "a", "policy.md", b"The liquidity reserve is 4,250,000 and the target is 60 percent growth.")
    passages = context_passages(plane, "north", "liquidity reserve target growth")
    assert "4,250,000" not in passages  # a sentence with a figure the guard would replace is dropped from the quote ...
    guarded = check_numbers("Your liquidity reserve is 4,250,000.", facts=[], question="What is our liquidity reserve?")
    assert "4,250,000" not in guarded.text and guarded.replaced == 1  # ... never a source of a figure


def test_an_unreadable_store_never_stops_the_agent(plane, monkeypatch):
    DocStore(plane).upload("north", "a", "policy.md", F.POLICY)

    def boom(*a, **k):
        raise OSError("disk")
    monkeypatch.setattr(retrieval, "retrieve", boom)
    assert context_passages(plane, "north", "growth assets") == ""
