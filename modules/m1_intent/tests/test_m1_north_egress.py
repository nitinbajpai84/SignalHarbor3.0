"""M1-P04d: what North sends (first message and tool results) passes the REAL gateway structure check for each real
pack. The stub model sits below that check in other tests, which is how a raw_rows block reached a real browser."""
import json
from pathlib import Path

import pytest

from modules.m1_intent.agent import north
from modules.m1_intent.tools.pack_tools import load_guidance
from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.egress.aggregates import SuppressedFigures
from sh_platform.egress.gateway import _check_structure
from sh_platform.egress.model import _param_names, encode_turn
from sh_platform.packs import PackLoader

REAL = PackLoader(Path(__file__).resolve().parents[3] / "packs")
LABELS = {i: REAL.load(i).label for i in REAL.industries()}   # the real packs, whatever they are called
NOTES = {i: f"We keep losing track of {load_guidance(REAL, i).kpis[0]['name']}" for i in LABELS}  # a note the pack's own KPI matches


class Gate:
    def is_enabled(self, company_id, module_id):
        return True


class CheckedModel:
    """Sends each step through the real _check_structure, as EgressModelClient would; a block is a provider failure."""
    def __init__(self):
        self.steps = 0

    def complete(self, module_id, messages, tools=None):
        self.steps += 1
        payload = {"messages": [encode_turn(m) for m in messages]}
        if tools:
            payload["tools"] = [{"name": t["name"], "description": t.get("description", ""),
                                 "parameters": _param_names(t.get("parameters"))} for t in tools]
        _check_structure(payload, SuppressedFigures())
        if self.steps == 1:
            return ModelReply("", [ToolCall("industry_practice", {"topic": NOTES_NOW[0]}, "c1"), ToolCall("problem_library", {}, "c2")])
        return ModelReply("Industry practice (suggestion): others track it. Your company decides. Is that right?")


NOTES_NOW = [""]


@pytest.mark.parametrize("industry", LABELS)
def test_norths_real_messages_and_tool_results_pass_the_gateway_structure_check(industry):
    NOTES_NOW[0] = NOTES[industry]
    turns = [{"id": "t", "role": "person", "text": NOTES[industry], "at": "n"}]
    model = CheckedModel()
    text, answered = north.next_question(model, Gate(), "co", load_guidance(REAL, industry), turns, practice=True, library=True,
                                         company_name="Acme")
    assert answered and model.steps == 2, text


@pytest.mark.parametrize("industry", LABELS)
def test_the_context_carries_the_company_and_the_pack_industry_label(industry):
    seen = {}

    class Spy:
        def complete(self, module_id, messages, tools=None):
            seen["ctx"] = json.loads(messages[1]["content"])["context"]
            seen["system"] = messages[0]["content"]
            return ModelReply("Who is affected?")

    north.next_question(Spy(), Gate(), "co", load_guidance(REAL, industry), [{"id": "t", "role": "person", "text": NOTES[industry], "at": "n"}],
                        practice=True, library=False, company_name="Acme")
    assert seen["ctx"]["industry"] == LABELS[industry] and seen["ctx"]["company"] == "Acme"
    assert isinstance(seen["ctx"]["industry_guidance"], str) and "different industry" in seen["system"]


def _turn(industry, **kw):
    seen = {}

    class Spy:
        def complete(self, module_id, messages, tools=None):
            seen["ctx"] = json.loads(messages[1]["content"])["context"]
            seen["system"] = messages[0]["content"]
            _check_structure({"messages": [encode_turn(m) for m in messages]}, SuppressedFigures())  # the real gateway check
            return ModelReply("So you worry about renewals. Did I get that right?")

    turns = [{"id": "t", "role": "person", "text": NOTES[industry], "at": "n"}]
    text, answered = north.next_question(Spy(), Gate(), "co", load_guidance(REAL, industry), turns, library=False,
                                         company_name="Acme", **{"practice": False, **kw})
    return seen, text, answered


@pytest.mark.parametrize("industry", LABELS)
def test_the_default_turn_listens_and_checks_with_no_industry_guidance(industry):
    seen, text, answered = _turn(industry)
    assert answered and "industry_guidance" not in seen["ctx"]
    assert "Did I get that right" in seen["system"] and "Industry practice (suggestion): " not in json.dumps(seen["ctx"])
    assert text.startswith("So ") and text.count("?") == 1


@pytest.mark.parametrize("industry", LABELS)
def test_an_explicit_ask_adds_the_guidance_and_passes_the_gateway_check(industry):
    seen, text, answered = _turn(industry, ask_how_others=True)
    assert answered and "Industry practice (suggestion)" in seen["ctx"]["industry_guidance"]


# ---- the real gateway, with a protected company name and a seat whose display name contains it

COMPANY = "Illustrative Lakeside Family Office"
SEAT = "Arjun Rao"  # a person's own name, as typed on arrival


def _real_client(tmp_path, reply="Who is affected?"):
    from sh_platform.egress.gateway import EgressGateway
    from sh_platform.egress.model import EgressModelClient
    from sh_platform.egress.policy import EgressPolicy
    from sh_platform.egress.vault import NameVault
    from sh_platform.plane import PlaneStore
    (tmp_path / "data").mkdir()
    plane = PlaneStore(tmp_path / "data").create("lakeside-family-office")
    vault = NameVault(plane)
    from modules.m1_intent.domain.seat_identity import protected_names
    for kind, name in protected_names(COMPANY, [SEAT, "Mei Tan (illustrative)"]):  # the seeded admin's name
        if name:
            vault.register(kind, name)  # exactly what register_names does, with the seeded admin's real name
    calls = []
    gw = EgressGateway(plane, vault, EgressPolicy(plane), model_allowlist=["model.example.test"],
                       model_url="https://model.example.test/v1", transport=lambda url, body: calls.append(body) or reply)
    return EgressModelClient(gw), calls


@pytest.mark.parametrize("industry", sorted(LABELS))
@pytest.mark.parametrize("ask", [False, True])
def test_norths_turn_through_the_real_gateway_with_a_protected_company_name(tmp_path, ask, industry):
    model, calls = _real_client(tmp_path)
    turns = [{"id": "t", "role": "person", "text": NOTES[industry], "at": "n"}]
    text, answered = north.next_question(model, Gate(), "co", load_guidance(REAL, industry), turns, practice=False, library=False,
                                         company_name=COMPANY, ask_how_others=ask)
    assert answered and calls and b"Lakeside" not in calls[0], text


def test_niras_ask_through_the_real_gateway_with_a_protected_company_name(tmp_path):
    from modules.m1_intent.agent import nira
    model, calls = _real_client(tmp_path, reply="Nira here.")
    cfg = nira.load_rules()
    text = nira.ask_nira(model, Gate(), None, "co", COMPANY, LABELS["family_office"], stage="private_rooms", rules=[], kind="ask",
                         question=f"How does this work for {SEAT}?", instructions=cfg)
    assert text and calls and b"Lakeside" not in calls[0]
    # in the browser the gateway refused ordinary words ("family office", "administrator") because the seeded
    # display name made "Family", "Office" and "Admin" protected name parts; person names no longer do (3 Oct 2026)
    assert model.complete("m1", [{"role": "user", "content": "A family office and its fund administrator."}])


def test_a_bracketed_suffix_is_not_part_of_the_name():
    from modules.m1_intent.domain.seat_identity import protected_names
    names = protected_names("Acme", ["Pat Lee (Lakeside)", "Mei Tan (illustrative)"])
    assert ("person", "Pat Lee") in names and ("person", "Mei") in names and ("person", "Lee") in names
    assert not any("(" in n or ")" in n or n.casefold() in ("lakeside", "illustrative") for k, n in names)


def test_a_bracketed_suffix_never_blocks_its_word_but_the_name_is_tokenised_by_the_real_gateway(tmp_path):
    # "(illustrative)" and "(Lakeside)" are labels, not names: registering them blocked ordinary text (3 Oct 2026)
    from modules.m1_intent.domain.seat_identity import protected_names
    from sh_platform.egress.vault import NameVault
    from sh_platform.plane import PlaneStore
    (tmp_path / "data").mkdir()
    vault = NameVault(PlaneStore(tmp_path / "data").create("co"))
    for kind, name in protected_names("Acme", ["Pat Lee (Lakeside)"]):
        vault.register(kind, name)
    assert "Lee" not in vault.tokenise("Pat Lee met us.") and "Lakeside" in vault.tokenise("We met at Lakeside on Monday.")
