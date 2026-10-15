"""M2-P03: what Lens sends to tidy the step wording passes the REAL gateway structure check and the real gateway, with
protected names, as in modules/m1_intent/tests/test_m1_north_egress.py (ported, reshaped for a plain-text reword)."""
import re
from pathlib import Path

import pytest
from test_m2_process_map import ANSWER, PACK_DEFAULT

from modules.m2_baseline.domain import process_map as D
from sh_platform.agents.protocols import ModelReply
from sh_platform.egress.aggregates import SuppressedFigures
from sh_platform.egress.gateway import EgressGateway, _check_structure
from sh_platform.egress.model import EgressModelClient, encode_turn
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.vault import NameVault
from sh_platform.packs import PackLoader
from sh_platform.plane import PlaneStore

REAL = PackLoader(Path(__file__).resolve().parents[3] / "packs")
INDUSTRIES = REAL.industries()


def steps_for(industry: str) -> list[dict]:
    """The steps Lens would reword: from the owners' answers, or from the real pack's own default map."""
    pack = REAL.load(industry)
    default = pack.section("process_map_default") if "process_map_default" in pack.sections() else PACK_DEFAULT
    return D.draw([ANSWER], None, "pack", None)["steps"] + D.draw([], default, "pack", None, kpi_id="K01")["steps"]


class CheckedModel:
    """Sends each call through the real _check_structure, as EgressModelClient would; a block is a provider failure."""
    def __init__(self, n):
        self.n, self.checked = n, 0

    def complete(self, module_id, messages, tools=None):
        _check_structure({"messages": [encode_turn(m) for m in messages]}, SuppressedFigures())
        self.checked += 1
        return ModelReply("\n".join(re.sub(r"^\d+\. ", "", ln) + " (tidied)" for ln in messages[-1]["content"].splitlines()))


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_the_tidy_request_passes_the_real_gateway_structure_check_for_each_real_pack(industry):
    texts = [s["text"] for s in steps_for(industry)]
    model = CheckedModel(len(texts))
    assert D.tidy_texts(model, texts) == [f"{t} (tidied)" for t in texts] and model.checked == 1


def real_client(tmp_path, reply, protected):
    (tmp_path / "data").mkdir()
    plane = PlaneStore(tmp_path / "data").create("lakeside-family-office")
    vault = NameVault(plane)
    for kind, name in protected:
        vault.register(kind, name)
    calls = []
    gw = EgressGateway(plane, vault, EgressPolicy(plane), model_allowlist=["model.example.test"],
                       model_url="https://model.example.test/v1", transport=lambda url, body: calls.append(body) or reply)
    return EgressModelClient(gw), calls


def test_the_tidy_request_through_the_real_gateway_carries_no_protected_name(tmp_path):
    texts = ["Sara adjusts the figure in the workbook", "Arjun Rao asks the bank for the statement"]
    model, calls = real_client(tmp_path, "Sara adjusts the figure in the workbook\nArjun Rao asks the bank for the statement",
                               [("person", "Sara"), ("person", "Arjun Rao"), ("person", "Arjun"), ("company", "Lakeside Holdings")])
    tidy = D.tidy_texts(model, texts)
    assert tidy == ["Sara adjusts the figure in the workbook", "Arjun Rao asks the bank for the statement"]
    assert calls and b"Sara" not in calls[0] and b"Arjun" not in calls[0]


def test_a_gateway_refusal_leaves_the_original_wording(tmp_path):
    model, calls = real_client(tmp_path, "unused", [("person", "Sara")])
    model.gateway.model_allowlist = []  # nothing may be sent: the gateway refuses
    steps = D.draw([ANSWER], None, "pack", None, model)["steps"]
    assert steps[0]["text"] == "Sends statement, daily" and not calls


def sara_answer():
    from test_m2_process_map import S
    return {**ANSWER, "in_between": S([{"who": S("Finance"), "step": S("Adjusts in Sara's tracker workbook"), "manual": S(True)},
                                       {"who": S("Finance"), "step": S("Downloads file"), "manual": S(False)}]),
            "upstream": S([]), "downstream": S([])}


def test_a_name_in_step_text_that_nobody_registered_is_never_sent_and_that_step_keeps_its_wording(tmp_path):
    """Sara is NOT registered here: the draw itself must keep her step off the wire."""
    model, calls = real_client(tmp_path, "Downloads the file", [("company", "Lakeside Holdings")])
    steps = D.draw([sara_answer()], None, "pack", None, model, frozenset())["steps"]
    assert [s["text"] for s in steps] == ["Adjusts in Sara's tracker workbook", "Downloads the file"]
    assert calls and all(b"Sara" not in c for c in calls)


def test_the_route_registers_people_with_each_part_and_teams_and_generic_words_not_at_all():
    from modules.m2_baseline.api.process_map import _names
    from sh_platform.egress.names import protected_names
    kpi = {"id": "k1", "owners": {"business": {"value": "Mira Das", "mark": "stated"}, "data": {"value": "Tom Ng", "mark": "stated"},
                                  "process": {"value": "Sara", "mark": "stated"}}}
    people, orgs = _names([ANSWER], [kpi])
    names = {n for _, n in protected_names("", people, orgs)}
    assert {"Mira Das", "Mira", "Das", "Tom Ng", "Tom", "Sara", "Arjun Rao", "Arjun", "Rao"} <= names
    assert not {"Finance", "Investments", "Committee", "Bank"} & names  # the `who` of an answer is a team or system
