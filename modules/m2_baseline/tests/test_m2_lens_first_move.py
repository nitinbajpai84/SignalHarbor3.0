"""M2-AGENTS Part 0 and 1: why Lens "was not working", and Lens doing the first move.

Part 0 reproduces the screen Nitin saw with the family office pack and the two charter problems "Managers ahead or
behind benchmarks" and "Bonuses and trusted numbers", a stub model and no company documents. The cause was not the
model: Lens only acted on a click (disabled until a measure was confirmed), only called the model when a document
matched, and then said nothing. These tests fail on that behaviour."""
import json

import pytest
from m2_kit import BASE, login
from test_m2_lens import REAL, Refused, Stub, with_doc
from test_m2_worklist import confirm, kpi_of, kpi_url, rich_packs, seed_charter, start  # noqa: F401  (rich_packs: autouse fixture)

from sh_platform.context_docs.store import DocStore

FO = [{"id": "p1", "title": "Managers ahead or behind benchmarks", "priority": "must", "so_that": None, "note_count": 2, "library_problem_id": None},
      {"id": "p2", "title": "Bonuses and trusted numbers", "priority": "should", "so_that": None, "note_count": 1, "library_problem_id": None}]


@pytest.fixture
def fo(world):
    """The real family office pack for a company of its own."""
    world.app.state.packs = REAL
    world.app.state.entitlements.create_company("co-fo", "Co Fo", "family_office", modules=["m1_intent", "m2_baseline"])
    return world


def lens_url(v, tail=""):
    return f"{BASE}/baselines/{v['baseline']['id']}/lens{tail}"


def model(world, stub):
    world.app.state.lens_model_factory = (lambda plane: stub) if stub else (lambda plane: None)


# ---- Part 0: the reproduction

def test_the_charter_problems_get_suggestions_with_a_pack_draft_each(fo):
    c = login(fo, "co-fo")
    v = start(c, seed_charter(fo, "co-fo", FO))
    assert {"p1", "p2"} == {pid for s in v["suggestions"] for pid in s["problem_ids"]}
    assert all(s["definition"]["by"] == "the pack" and s["definition"]["mark"] == "guessed" for s in v["suggestions"])  # a draft without a click


def test_a_measure_nothing_can_define_is_said_so_never_silent(fo):
    """The old route answered an empty 200: no outcome, no note, and the page said "Lens has drafted what it could"."""
    stub = Stub()
    model(fo, stub)
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Manager gap to benchmark", problem_ids=["p1"])
    kid = v["kpis"][0]["id"]
    v = c.post(lens_url(v, "/draft"), json={}).json()
    assert v["outcomes"][kid] == "nothing" and stub.sent == []
    assert "Manager gap to benchmark" in v["lens_note"] and "ask you" in v["lens_note"]
    assert kpi_of(v, kid)["definition"]["mark"] == "unknown"


def test_the_live_path_says_so_when_the_model_fails(fo):
    with_doc(fo, "co-fo")
    model(fo, Refused())
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Calls due, by date", problem_ids=["p1"])
    v = c.post(lens_url(v, "/draft"), json={}).json()
    assert v["lens_note"].startswith("Lens could not reach the model") and list(v["outcomes"].values()) == ["unreachable"]
    assert c.get(lens_url(v)).json()["failed"] == [v["kpis"][0]["id"]]  # and the block offers to try again


def test_documents_without_a_model_are_said_so(fo):
    with_doc(fo, "co-fo")
    model(fo, None)
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Calls due, by date", problem_ids=["p1"])
    v = c.post(lens_url(v, "/draft"), json={}).json()
    assert "no model is set up" in v["lens_note"] and list(v["outcomes"].values()) == ["no_model"]


# ---- Part 1: the first move

def test_lens_proposes_measures_and_drafts_for_each_without_a_click(fo):
    c = login(fo, "co-fo")
    v = start(c, seed_charter(fo, "co-fo", FO))
    s = c.get(lens_url(v)).json()
    ids = [s_["id"] for s_ in v["suggestions"]]
    assert s["pending"] == ids and [r["kind"] for r in s["refine"]] == ["suggestion"] * len(ids)
    assert "usually track" in s["refine"][0]["label"] and s["refine"][0]["problems"]
    assert str(len(ids)) in s["say"]["did"] and "2" in s["say"]["did"]


def test_a_first_draft_from_a_document_is_kept_for_the_suggestion_and_goes_to_the_measure(fo):
    """The pre-read fill: Lens reads the company's document and the pack and fills the definition, who produces the data and how
    it is gathered as guesses with the document's title; the likely owner waits as a question to confirm. No measure exists yet."""
    c = login(fo, "co-fo")
    v = start(c, seed_charter(fo, "co-fo", FO))
    sid, name = v["suggestions"][0]["id"], v["suggestions"][0]["name"]
    DocStore(fo.plane("co-fo")).upload("lens", "a", "m.md", f"{name}: we track it every quarter from the administrator's statements.".encode(), title="Reporting note")
    stub = Stub("DEFINITION: The quarterly figure from the statements. OWNER: The finance team. PRODUCER: The fund administrator. GATHERED: Statements each quarter.")
    model(fo, stub)
    v = c.post(lens_url(v, "/draft"), json={"suggestion_ids": [sid]}).json()
    assert v["outcomes"][sid] == "documents" and v["kpis"] == []  # still no measure until a person confirms one
    assert "quarterly figure" in json.dumps(stub.sent) or "every quarter" in json.dumps(stub.sent)  # the stub saw the passage
    d = next(s for s in v["suggestions"] if s["id"] == sid)["definition"]
    assert (d["mark"], d["by"], d["from"]) == ("guessed", "Lens", "Reporting note")
    assert sid not in c.get(lens_url(v)).json()["pending"]
    v = confirm(c, v, suggestion_id=sid)
    k = kpi_of(v, sid)
    assert (k["definition"]["mark"], k["definition"]["from"]) == ("guessed", "Reporting note")
    assert (k["producer"]["value"].rstrip("."), k["producer"]["mark"], k["producer"]["from"]) == ("The fund administrator", "guessed", "Reporting note")
    assert k["gathered"]["mark"] == "guessed" and k["owners"]["business"]["mark"] == "unknown"  # a guessed owner is not a nomination
    ask = c.get(lens_url(v)).json()["asks"][0]
    assert ask["field"] == "owner" and ask["draft"]["value"].rstrip(".") == "The finance team" and ask["draft"]["from"] == "Reporting note"
    assert "I read 1 document" in c.get(lens_url(v)).json()["say"]["did"]


def test_the_fill_never_overwrites_a_persons_value(fo):
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Calls due, by date", problem_ids=["p1"])
    kid = v["kpis"][0]["id"]
    c.put(kpi_url(v, kid, "/triage"), json={"producer": {"text": "Our treasury desk", "mark": "stated"}, "definition": {"text": "Our own words", "mark": "stated"}})
    with_doc(fo, "co-fo")
    model(fo, Stub("DEFINITION: Unpaid notices by date. OWNER: Mei. PRODUCER: The administrator. GATHERED: By email."))
    v = c.post(lens_url(v, "/draft"), json={"kpi_ids": [kid]}).json()
    k = kpi_of(v, kid)
    assert (k["producer"]["value"], k["producer"]["mark"]) == ("Our treasury desk", "stated")
    assert k["definition"]["value"] == "Our own words" and k["definition_proposal"]["by"] == "Lens"
    assert k["gathered"]["mark"] == "guessed" and k["gathered"]["by"] == "Lens"  # only the gap is filled


def test_a_restricted_document_is_never_used_for_a_measure_not_marked_personal(fo):
    DocStore(fo.plane("co-fo")).upload("lens", "a", "pay.md", b"Secret pay gap: we compare pay bands across managers.", title="Pay bands", restricted=True)
    stub = Stub("It compares pay bands.")
    model(fo, stub)
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Secret pay gap", problem_ids=["p2"])
    kid = v["kpis"][0]["id"]
    c.put(kpi_url(v, kid, "/governance"), json={"personal": "no"})
    v = c.post(lens_url(v, "/draft"), json={"kpi_ids": [kid]}).json()
    assert stub.sent == [] and v["outcomes"][kid] == "nothing"


def test_the_failed_first_draft_is_recorded_and_not_retried_on_every_open(fo):
    with_doc(fo, "co-fo")
    model(fo, Refused())
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Calls due, by date", problem_ids=["p1"])
    kid = v["kpis"][0]["id"]
    assert kid in c.get(lens_url(v)).json()["pending"]
    c.post(lens_url(v, "/draft"), json={"kpi_ids": [kid]})
    s = c.get(lens_url(v)).json()
    assert kid not in s["pending"] and s["failed"] == [kid] and "could not reach" in s["say"]["need"]


# ---- Lens asks, one question at a time, and the answers go to the fields the table uses

def test_lens_asks_one_open_question_at_a_time_and_the_answer_lands_in_the_table_field(fo):
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), suggestion_id=start(c, seed_charter(fo, "co-fo", FO))["suggestions"][0]["id"])
    kid = v["kpis"][0]["id"]
    c.post(lens_url(v, "/draft"), json={"kpi_ids": [kid]})
    s = c.get(lens_url(v)).json()
    first = s["asks"][0]
    assert (first["kpi_id"], first["field"], first["role"]) == (kid, "owner", "business") and first["text"].endswith("?")
    assert s["say"]["need"] == first["text"]
    c.put(kpi_url(v, kid, "/owners"), json={"business": {"name": "Mei Tan"}})
    assert c.get(lens_url(v)).json()["asks"][0]["role"] == "data"  # the next one
    c.put(kpi_url(v, kid, "/triage"), json={"producer": {"text": "The fund administrator", "mark": "stated"}})
    k = kpi_of(c.get(f"{BASE}/baselines/{v['baseline']['id']}").json(), kid)
    assert k["producer"]["mark"] == "stated" and k["producer"]["by"].startswith("Test")  # stated by the person, not by Lens


# ---- redraft: "Tell Lens what to change"

def test_tell_lens_what_to_change_redrafts_one_measure(fo):
    with_doc(fo, "co-fo")
    stub = Stub("Calls due, by date counts net returns after fees.")
    model(fo, stub)
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Calls due, by date", problem_ids=["p1"])
    kid = v["kpis"][0]["id"]
    v = c.post(lens_url(v, "/redraft"), json={"kpi_id": kid, "instruction": "make it about net returns"}).json()
    d = kpi_of(v, kid)["definition"]
    assert d["by"] == "Lens" and d["mark"] == "guessed" and "net returns" in d["value"]
    assert "make it about net returns" in json.dumps(stub.sent[0]) and v["outcome"] == "redrafted"


def test_a_redraft_never_overwrites_a_persons_edit(fo):
    with_doc(fo, "co-fo")
    model(fo, Stub("Calls due, by date counts net returns."))
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Calls due, by date", problem_ids=["p1"])
    kid = v["kpis"][0]["id"]
    c.put(kpi_url(v, kid, "/triage"), json={"definition": {"text": "Our own words", "mark": "stated"}})
    v = c.post(lens_url(v, "/redraft"), json={"kpi_id": kid, "instruction": "net returns"}).json()
    k = kpi_of(v, kid)
    assert k["definition"]["value"] == "Our own words" and k["definition_proposal"]["by"] == "Lens" and v["outcome"] == "kept_yours"


def test_a_redraft_without_a_model_says_so(fo):
    model(fo, None)
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Calls due, by date", problem_ids=["p1"])
    v = c.post(lens_url(v, "/redraft"), json={"kpi_id": v["kpis"][0]["id"], "instruction": "shorter"}).json()
    assert "no model is set up" in v["lens_note"] and v["outcome"] == "no_model"


def test_a_suggestion_can_be_redrafted_too(fo):
    model(fo, Stub("A new wording of the measure."))
    c = login(fo, "co-fo")
    v = start(c, seed_charter(fo, "co-fo", FO))
    sid = v["suggestions"][0]["id"]
    v = c.post(lens_url(v, "/redraft"), json={"kpi_id": sid, "instruction": "plainer"}).json()
    assert next(s for s in v["suggestions"] if s["id"] == sid)["definition"]["value"] == "A new wording of the measure." and v["kpis"] == []


def test_a_redraft_asks_for_an_instruction_and_a_known_measure(fo):
    model(fo, Stub())
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Calls due, by date")
    assert c.post(lens_url(v, "/redraft"), json={"kpi_id": v["kpis"][0]["id"], "instruction": " "}).status_code == 400
    assert c.post(lens_url(v, "/redraft"), json={"kpi_id": "nope", "instruction": "x"}).status_code == 404


# ---- privacy: restricted measures, restricted documents, who may call

def _restricted(fo):
    admin = login(fo, "co-fo", "Pat Owner", ("company_admin",))
    v = confirm(admin, start(admin, seed_charter(fo, "co-fo", FO)), name="Secret pay gap", problem_ids=["p2"])
    kid = v["kpis"][0]["id"]
    admin.put(kpi_url(v, kid, "/governance"), json={"personal": "yes", "may_see": ["Test Wei Lim"]})
    return admin, v, kid


def test_a_restricted_measure_is_not_in_lenss_block_for_someone_not_named(fo):
    stub = Stub()
    model(fo, stub)
    admin, v, kid = _restricted(fo)
    outsider = login(fo, "co-fo", "Sam Outsider", ("analyst",))
    named = login(fo, "co-fo", "Wei Lim", ("analyst",))
    seen = outsider.get(lens_url(v))
    assert kid not in seen.text and "Secret pay gap" not in seen.text
    drafted = outsider.post(lens_url(v, "/draft"), json={"kpi_ids": [kid]}).json()
    assert drafted["outcomes"] == {} and "Secret pay gap" not in json.dumps(drafted)  # nothing drafted for, or said of, a measure not theirs
    assert outsider.post(lens_url(v, "/redraft"), json={"kpi_id": kid, "instruction": "x"}).status_code == 403
    r = outsider.post(lens_url(v, "/ask"), json={"question": "Which measures are on the list?"}).json()
    assert "Secret pay gap" not in json.dumps(stub.sent) and r["text"]
    assert "Secret pay gap" in named.get(lens_url(v)).text and "Secret pay gap" in admin.get(lens_url(v)).text


def test_a_restricted_document_is_read_only_for_a_measure_marked_personal(fo):
    from sh_platform.context_docs.store import DocStore
    DocStore(fo.plane("co-fo")).upload("lens", "a", "pay.md", b"Secret pay gap: we compare pay bands across managers.", title="Pay bands", restricted=True)
    stub = Stub("It compares pay bands.")
    model(fo, stub)
    admin, v, kid = _restricted(fo)
    admin.post(lens_url(v, "/draft"), json={"kpi_ids": [kid]})
    assert "pay bands" in json.dumps(stub.sent).lower()  # the admin may see this measure, so its document may be read
    stub.sent.clear()
    other = login(fo, "co-fo", "Rae Other", ("analyst",))
    other.post(lens_url(v, "/ask"), json={"question": "What does Secret pay gap compare?"})
    assert "pay bands" not in json.dumps(stub.sent).lower()


def test_the_lens_routes_refuse_a_participant_another_company_and_a_switched_off_module(fo):
    admin = login(fo, "co-fo")
    v = start(admin, seed_charter(fo, "co-fo", FO))
    calls = [("get", ""), ("post", "/draft"), ("post", "/redraft"), ("post", "/ask")]
    pia = login(fo, "co-fo", "Pia Participant", ("participant",))
    other = login(fo, "co-a", "Bea Other")
    off = login(fo, "co-off", "Olly Off")
    for who, ok in ((pia, (403,)), (other, (404,)), (off, (403, 404))):
        for verb, tail in calls:
            r = getattr(who, verb)(lens_url(v, tail), **({} if verb == "get" else {"json": {"question": "hi", "kpi_id": "x", "instruction": "y"}}))
            assert r.status_code in ok, (verb, tail, r.status_code)
    assert pia.post(f"{BASE}/baselines/{v['baseline']['id']}/nira", json={"kind": "welcome"}).status_code == 403
    assert other.post(f"{BASE}/baselines/{v['baseline']['id']}/nira", json={"kind": "welcome"}).status_code == 404


# ---- the conversation

def test_lens_answers_from_recorded_facts_and_the_model_sees_plain_text(fo):
    stub = Stub("Because the pack lists it for that problem.")
    model(fo, stub)
    c = login(fo, "co-fo")
    v = start(c, seed_charter(fo, "co-fo", FO))
    name = v["suggestions"][0]["name"]
    r = c.post(lens_url(v, "/ask"), json={"question": f"Why did you suggest {name}?"}).json()
    assert r["text"] == "Because the pack lists it for that problem." and r["name"] == "Lens" and r["changed"] is False
    ctx = json.loads(stub.sent[0][1]["content"])["context"]
    assert isinstance(ctx["baseline_facts"], str) and "Managers ahead or behind benchmarks" in ctx["baseline_facts"] and name in ctx["baseline_facts"]
    assert "usually track" in ctx["baseline_facts"]


def test_a_typed_instruction_about_one_measure_redrafts_it(fo):
    with_doc(fo, "co-fo")
    stub = Stub("Calls due, by date counts net returns.")
    model(fo, stub)
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Calls due, by date", problem_ids=["p1"])
    r = c.post(lens_url(v, "/ask"), json={"question": "Make the definition of Calls due, by date about net returns"}).json()
    assert r["changed"] is True
    d = kpi_of(c.get(f"{BASE}/baselines/{v['baseline']['id']}").json(), v["kpis"][0]["id"])["definition"]
    assert "net returns" in d["value"] and d["by"] == "Lens"


def test_without_a_model_lens_says_what_it_can_and_cannot_do(fo):
    model(fo, None)
    c = login(fo, "co-fo")
    v = start(c, seed_charter(fo, "co-fo", FO))
    r = c.post(lens_url(v, "/ask"), json={"question": "Why?"}).json()
    assert r["available"] is False and "no model" in r["text"]
    assert c.post(lens_url(v, "/ask"), json={"question": " "}).status_code == 400


def test_a_signed_baseline_can_be_asked_but_not_redrafted(fo):
    model(fo, Stub())
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Calls due, by date")
    path = fo.plane("co-fo").path("intents", "m2_baseline", v["baseline"]["id"], "baseline.json")
    path.write_text(json.dumps({**v["baseline"], "state": "signed"}))
    assert c.post(lens_url(v, "/ask"), json={"question": "Why this measure?"}).status_code == 200
    r = c.post(lens_url(v, "/ask"), json={"question": "Make the definition of Calls due, by date shorter"}).json()
    assert r["changed"] is False and "signed" in r["text"]
    assert c.post(lens_url(v, "/redraft"), json={"kpi_id": v["kpis"][0]["id"], "instruction": "x"}).status_code == 409


# ---- two industries and an empty company

@pytest.mark.parametrize("company,industry", [("co-a", "industry_a"), ("co-b", "industry_b")])
def test_each_industry_gets_its_own_first_move(world, company, industry):
    c = login(world, company)
    v = start(c, seed_charter(world, company))
    s = c.get(lens_url(v)).json()
    assert s["refine"] and all(industry in r["name"] for r in s["refine"]) and s["pack"] == {"available": True, "label": industry}


def test_a_company_with_no_pack_gets_an_honest_empty_state(world):
    c = login(world, "co-none")
    v = start(c, seed_charter(world, "co-none"))
    s = c.get(lens_url(v)).json()
    assert s["refine"] == [] and s["pending"] == [] and s["pack"]["available"] is False
    assert "no industry knowledge" in s["say"]["did"]


def test_figure_lines_carry_latest_change_range_and_pipeline_only_for_measures_the_asker_may_see(monkeypatch):
    from types import SimpleNamespace

    from modules.m2_baseline.api import lens_chat as LC
    t = [{"period": "2026-08", "value": 90.0}, {"period": "2026-09", "value": 62.5}]
    feeds = [{"code": "K02", "name": "Coverage", "may_see": True, "trend": t, "range_break": True},
             {"code": "K09", "name": "Hidden", "may_see": False, "trend": [], "range_break": False}]
    graph = {"nodes": [{"id": "pipeline:K02", "label": "Custodian daily file"}], "edges": [{"from": "measure:K02", "to": "pipeline:K02", "type": "built_by"}]}
    monkeypatch.setattr(LC, "_viewer", lambda r: None)
    monkeypatch.setattr(LC, "graph_for", lambda p, v: graph)
    monkeypatch.setattr(LC, "feeds_build", lambda p, v: {"measures": feeds})
    out = LC._figure_lines(SimpleNamespace(request=None, plane=None))
    assert len(out) == 1 and "Hidden" not in out[0]
    assert all(x in out[0] for x in ("2026-09", "62.5", "90", "down by 27.5", "outside its usual range", "Custodian daily file"))
