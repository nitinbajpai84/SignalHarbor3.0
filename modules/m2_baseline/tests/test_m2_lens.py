"""Lens (M2-03, M2-P01): drafts from the company's own pack, pre-reads the company's documents, never invents a
formula, and only ever reaches the model through the egress gateway. The model is a stub; the structure test runs the
REAL gateway check, as modules/m1_intent/tests/test_m1_north_egress.py does for North."""
import json
from pathlib import Path

import pytest
from m2_kit import BASE, login
from test_m2_worklist import confirm, kpi_of, kpi_url, rich_packs, seed_charter, start  # noqa: F401  (rich_packs: autouse fixture)

from modules.m2_baseline.agent import lens
from modules.m2_baseline.agent import pack_text as P
from sh_platform.agents.protocols import ModelReply
from sh_platform.context_docs.store import DocStore
from sh_platform.egress.aggregates import SuppressedFigures
from sh_platform.egress.gateway import _check_structure
from sh_platform.egress.model import encode_turn
from sh_platform.packs import PackLoader

REAL = PackLoader(Path(__file__).resolve().parents[3] / "packs")
INDUSTRIES = REAL.industries()
COMPANY = "Illustrative Lakeside Family Office"
SEAT = "Arjun Rao"
DOC = (b"Calls due, by date. We count every capital call notice we have received that is not yet paid, "
       b"grouped by the date it falls due. The relationship manager is Margaret Ellery.")


class Gate:
    def is_enabled(self, company_id, module_id):
        return True


class Stub:
    """Remembers what it was sent and answers with `reply`."""
    def __init__(self, reply="Calls due, by date counts unpaid capital call notices grouped by due date."):
        self.reply, self.sent = reply, []

    def complete(self, module_id, messages, tools=None):
        self.sent.append(messages)
        return ModelReply(self.reply)


def with_doc(world, company="co-a", title="Funding calls note"):
    DocStore(world.plane(company)).upload("lens", "a", "calls.md", DOC, title=title)


def drafted(world, stub, company="co-a"):
    world.app.state.lens_model_factory = (lambda plane: stub) if stub else (lambda plane: None)
    c = login(world, company)
    v = confirm(c, start(c, seed_charter(world, company)), name="Calls due, by date", problem_ids=["p1"])
    return c, v


# ---- the pre-read of the company's documents

def test_a_matching_document_pre_fills_the_definition_as_guessed_from_its_title(world):
    with_doc(world)
    stub = Stub()
    c, v = drafted(world, stub)
    v = c.post(f"{BASE}/baselines/{v['baseline']['id']}/lens/draft", json={}).json()
    d = kpi_of(v, v["kpis"][0]["id"])["definition"]
    assert d["mark"] == "guessed" and d["by"] == "Lens" and d["from"] == "Funding calls note"
    assert d["value"].startswith("Calls due, by date counts")
    assert len(stub.sent) == 1


def test_nothing_goes_to_the_model_when_the_company_has_no_matching_document(world):
    stub = Stub()
    c, v = drafted(world, stub)
    v = c.post(f"{BASE}/baselines/{v['baseline']['id']}/lens/draft", json={}).json()
    assert stub.sent == [] and v["kpis"][0]["definition"]["mark"] == "unknown"  # no pack definition for a hand-added KPI either


class Refused:
    def complete(self, module_id, messages, tools=None):
        raise RuntimeError("the gateway refused")


def test_a_refused_model_call_is_told_to_the_person_never_a_silent_fallback(world):
    with_doc(world)
    c, v = drafted(world, Refused())
    v = c.post(f"{BASE}/baselines/{v['baseline']['id']}/lens/draft", json={}).json()
    assert v["lens_note"] == "Lens could not reach the model just now; these are the pack's suggestions."


def test_no_note_when_the_model_answered(world):
    with_doc(world)
    c, v = drafted(world, Stub())
    assert "lens_note" not in c.post(f"{BASE}/baselines/{v['baseline']['id']}/lens/draft", json={}).json()


def test_the_pack_draft_is_a_guess_labelled_as_a_suggestion_and_needs_no_model(world):
    stub = Stub()
    world.app.state.lens_model_factory = lambda plane: stub
    c = login(world, "co-a")
    v = confirm(c, start(c, seed_charter(world)), suggestion_id="K0")
    c.put(kpi_url(v, "K0", "/triage"), json={"definition": {"mark": "unknown"}})
    v = c.post(f"{BASE}/baselines/{v['baseline']['id']}/lens/draft", json={"kpi_ids": ["K0"]}).json()
    d = kpi_of(v, "K0")["definition"]
    assert (d["mark"], d["by"], d["value"]) == ("guessed", "the pack", "industry_a usual definition 0")
    assert "suggestion" in d["from"] and stub.sent == []


def test_without_a_model_the_pack_draft_still_works_and_the_page_is_told(world):
    with_doc(world)
    c, v = drafted(world, None)
    assert v["lens_available"] is False
    v = c.post(f"{BASE}/baselines/{v['baseline']['id']}/lens/draft", json={}).json()
    assert v["kpis"][0]["definition"]["mark"] == "unknown"


def test_when_the_text_does_not_say_the_definition_stays_a_question(world):
    with_doc(world)
    c, v = drafted(world, Stub("NO DEFINITION"))
    v = c.post(f"{BASE}/baselines/{v['baseline']['id']}/lens/draft", json={}).json()
    k = v["kpis"][0]
    assert k["definition"]["mark"] == "unknown"
    assert [q["question"] for q in k["questions"]][0].startswith("What is the formula")  # never invented


def test_a_persons_stated_definition_keeps_lenss_draft_beside_it(world):
    with_doc(world)
    c, v = drafted(world, Stub())
    kid = v["kpis"][0]["id"]
    c.put(kpi_url(v, kid, "/triage"), json={"definition": {"text": "Our own words", "mark": "stated"}})
    v = c.post(f"{BASE}/baselines/{v['baseline']['id']}/lens/draft", json={}).json()
    k = kpi_of(v, kid)
    assert k["definition"]["value"] == "Our own words" and k["definition"]["mark"] == "stated"
    assert k["definition_proposal"]["mark"] == "guessed" and k["definition_proposal"]["from"] == "Funding calls note"
    v = c.put(kpi_url(v, kid, "/triage"), json={"definition": {"text": "Reworded", "mark": "stated"}}).json()
    assert kpi_of(v, kid)["definition_proposal"] is None  # settled by the person


def test_a_persons_guessed_definition_is_kept_too_and_the_draft_goes_beside_it(world):
    """B2: anything a person touched is protected, not only "stated"."""
    with_doc(world)
    c, v = drafted(world, Stub())
    kid = v["kpis"][0]["id"]
    c.put(kpi_url(v, kid, "/triage"), json={"definition": {"text": "Maybe unpaid notices", "mark": "guessed"}})
    v = c.post(f"{BASE}/baselines/{v['baseline']['id']}/lens/draft", json={}).json()
    k = kpi_of(v, kid)
    assert k["definition"]["value"] == "Maybe unpaid notices" and k["definition"]["by"] == "Test Pat Owner"
    assert k["definition_proposal"]["by"] == "Lens" and k["definition_proposal"]["value"].startswith("Calls due, by date counts")


def test_a_figure_only_in_a_document_is_replaced_and_never_saved_as_a_definition(world):
    """P1: the guard replaces 4500 (a document figure is not a recorded fact); its replacement text is not a definition."""
    DocStore(world.plane("co-a")).upload("lens", "a", "calls.md", DOC + b" The usual call is 4500.", title="Funding calls note")
    c, v = drafted(world, Stub("Calls due, by date counts notices where the call is 4500."))
    v = c.post(f"{BASE}/baselines/{v['baseline']['id']}/lens/draft", json={}).json()
    k = v["kpis"][0]
    assert k["definition"]["mark"] == "unknown" and "not available yet" not in json.dumps(k)
    assert k["questions"][0]["question"].startswith("What is the formula")  # still a question for the business


def test_the_model_is_sent_plain_text_marked_untrusted_never_a_list_of_objects(world):
    with_doc(world)
    stub = Stub()
    c, v = drafted(world, stub)
    c.post(f"{BASE}/baselines/{v['baseline']['id']}/lens/draft", json={})
    ctx = json.loads(stub.sent[0][1]["content"])["context"]
    assert isinstance(ctx["company_documents"], str) and "untrusted" in ctx["company_documents"]
    assert isinstance(ctx["industry_guidance"], str)
    assert all(isinstance(v, (str, list)) for v in ctx.values()) and "Never invent a formula" in stub.sent[0][0]["content"]


def test_a_signed_baseline_is_not_re_drafted(world):
    c, v = drafted(world, Stub())
    path = world.plane("co-a").path("intents", "m2_baseline", v["baseline"]["id"], "baseline.json")
    path.write_text(json.dumps({**v["baseline"], "state": "signed"}))
    with_doc(world)
    assert c.post(f"{BASE}/baselines/{v['baseline']['id']}/lens/draft", json={}).status_code == 409


# ---- the pack, per industry

@pytest.mark.parametrize("industry", ["industry_a", "industry_b", "none"])
def test_pack_text_is_the_companys_own_industry_or_empty(world, industry):
    g = P.load_guidance(world.app.state.packs, industry)
    mine = P.propose_kpis(g, [{"id": "p1", "title": "x", "library_problem_id": "lib1"}], set())
    assert g.has_content == (industry != "none")
    assert P.pack_text(g, "K0").startswith(P.LABEL)  # always labelled as a suggestion
    if g.has_content:
        assert industry in P.pack_text(g, "K0") and mine and all(industry in k["name"] for k in mine)
    else:
        assert mine == [] and P.pack_definition(g, "K0") == ""  # no pack: nothing, never another industry's content


# ---- the real gateway

class CheckedModel:
    """Sends each step through the real _check_structure, as EgressModelClient would; a block is a provider failure."""
    def __init__(self):
        self.steps = 0

    def complete(self, module_id, messages, tools=None):
        self.steps += 1
        payload = {"messages": [encode_turn(m) for m in messages]}
        _check_structure(payload, SuppressedFigures())
        return ModelReply("Capital calls still to be paid, grouped by the date they fall due.")


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_lenss_real_messages_pass_the_gateway_structure_check_for_each_real_pack(industry):
    g = P.load_guidance(REAL, industry)
    kpi = g.kpis[0]
    model = CheckedModel()
    text = lens.draft_definition(model, Gate(), "co", company_name="Acme", industry=g.label, kpi_name=kpi["name"],
                                 pack=P.pack_text(g, kpi["id"]),
                                 documents="\n\n".join([lens.INTRO, lens.wrap_untrusted("Calls are due by date.", "Note")]))
    assert text and model.steps == 1


def _real_client(tmp_path, reply):
    from sh_platform.egress.gateway import EgressGateway
    from sh_platform.egress.model import EgressModelClient
    from sh_platform.egress.policy import EgressPolicy
    from sh_platform.egress.vault import NameVault
    from sh_platform.plane import PlaneStore
    (tmp_path / "gw").mkdir()
    plane = PlaneStore(tmp_path / "gw").create("lakeside-family-office")
    calls = []
    gw = EgressGateway(plane, NameVault(plane), EgressPolicy(plane), model_allowlist=["model.example.test"],
                       model_url="https://model.example.test/v1", transport=lambda url, body: calls.append(body) or reply)
    return plane, EgressModelClient(gw), calls


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_the_real_gateway_never_sees_a_person_who_is_only_named_in_a_document(tmp_path, industry):
    """B1: "Margaret Ellery" is in the document and nowhere else; nobody registers her, as the endpoint does not."""
    plane, model, calls = _real_client(tmp_path, "Calls due, by date counts unpaid notices.")
    DocStore(plane).upload("lens", "a", "calls.md", DOC, title="Funding calls note")
    lens.register_names(plane, COMPANY, [SEAT])  # what the endpoint registers: the company and the people on the work list
    g = P.load_guidance(REAL, industry)
    passages, titles = lens.preread(plane, "Calls due, by date")
    text = lens.draft_definition(model, Gate(), "co", company_name=COMPANY, industry=g.label, kpi_name="Calls due, by date",
                                 pack=P.pack_text(g, g.kpis[0]["id"]), documents=passages)
    assert text and titles == ["Funding calls note"] and len(calls) == 1
    assert b"Lakeside" not in calls[0] and b"Margaret" not in calls[0] and b"Ellery" not in calls[0]
    assert b"[a name]" in calls[0] and b"untrusted" in calls[0]  # masked, and still quoted as untrusted
