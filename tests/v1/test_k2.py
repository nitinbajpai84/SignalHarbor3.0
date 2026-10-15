"""K2 The live company map as active knowledge context: signing adds definitions under concepts; similar names make a merge proposal,
never a merge; the collision fact is program-filled; variants carry a difference line (digit-free prompt, stub with the model off);
a suggestion is addressed to the owner and accepting it versions the definition; a restricted project's definitions are the team's;
the owner of another variant hears of a new one in Pulse; creating a project and signing land on the map."""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sh_platform.graph import models
from sh_platform.jsonfile import read_json_strict, write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import k2_map as K
from sh_platform.v1 import m1_map
from sh_platform.v1 import p1_project as P

ROOT = Path(__file__).resolve().parents[2]
FIN = Viewer("Fiona", frozenset({"analyst"}), False, "acc-f")
PERF = Viewer("Pete", frozenset({"analyst"}), False, "acc-p")
OUT = Viewer("Olive", frozenset({"participant"}), False, "acc-o")
ADMIN = Viewer("Ada", frozenset({"company_admin"}), False, "acc-a")
AT1, AT5, AT6 = "2026-10-01T09:00:00+00:00", "2026-10-05T09:00:00+00:00", "2026-10-06T09:00:00+00:00"


def sow(iid, title, kpis, signed):
    return {"id": f"sow-{iid}", "intent_id": iid, "title": title, "state": "signed", "version": 1,
            "goal": {"line": title, "why": "", "readers": [], "decisions": [], "needed_by": ""}, "process": {"steps": [], "handovers": []},
            "kpis": [{"code": c, "name": n, "definition": d, "formula": "", "unit": "SGD", "period": "monthly", "owner": o, "source_ids": [],
                      "status": "defined", "pack_suggested": False} for c, n, d, o in kpis],
            "sources": [], "catalogue": [], "governance": [], "unclear": [], "signature": {"name": "Ada", "role": "company_admin", "at": signed},
            "signatures": [{"name": "Ada", "role": "company_admin", "at": signed, "version": 1}]}


def sign(plane, iid, title, kpis, at=AT1, sensitivity=None, team=()):
    path = plane.path("intents", iid, "sow.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, sow(iid, title, kpis, at))
    rec = P.create_project(plane, iid, title, "Ada")
    if sensitivity:
        rec.update(sensitivity=sensitivity, team=[{"name": n, "role": "member"} for n in team])
        write_json_atomic(P._ppath(plane, rec["id"]), rec)
    return rec["id"]


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setattr(K, "_model", lambda plane: None)
    monkeypatch.setattr(K, "_kick", lambda *a, **k: None)  # the background thread is started by hand in the tests that want it
    monkeypatch.setattr(K, "_groups", lambda plane: [])
    (tmp_path / "co").mkdir()
    return PlaneStore(tmp_path).plane_for("co")


def world(plane, sens=None):
    a = sign(plane, "fin1", "Finance monthly pack", [("NW", "Net worth", "Assets minus liabilities, private funds at last NAV", "Fiona")],
             sensitivity=sens)
    b = sign(plane, "perf1", "Performance review", [("NW", "Net worth", "Assets minus liabilities, private funds excluded", "Pete")], AT5,
             sensitivity=sens)
    return a, b


def alt(plane):
    sign(plane, "alt1", "Wealth view", [("TW", "Net worth after fees", "Net worth less fees", "Fiona")], AT6)


def test_signing_adds_definitions_under_one_concept_with_variants_and_a_difference(plane):
    world(plane)
    got = K.concepts(plane, ADMIN)
    assert [c["name"] for c in got] == ["Net worth"]
    v = got[0]["variants"]
    assert {x["team"] for x in v} == {"Fiona", "Pete"} and {x["project"] for x in v} == {"Finance monthly pack", "Performance review"}
    assert all(x["definition"] and x["signed_on"] for x in v)
    assert "private funds" in got[0]["difference"] and K.proposals(plane, ADMIN) == []  # same name: one concept, nothing to propose


def test_similar_names_make_a_proposal_not_a_merge_and_a_person_confirms(plane):
    world(plane)
    alt(plane)
    assert len(K.concepts(plane, ADMIN)) == 2  # nothing was merged by itself
    (p,) = K.proposals(plane, ADMIN)
    assert p["state"] == "open" and {p["from_name"], p["into_name"]} == {"Net worth", "Net worth after fees"}
    with pytest.raises(K.K2Refused) as e:  # a bystander cannot settle it
        K.decide_proposal(plane, OUT, p["id"], True)
    assert e.value.status == 403
    K.decide_proposal(plane, FIN, p["id"], True)  # Fiona owns a definition on one side
    merged = K.concepts(plane, ADMIN)
    assert len(merged) == 1 and len(merged[0]["variants"]) == 3 and K.proposals(plane, ADMIN) == []


def test_declined_proposal_is_not_proposed_again(plane):
    world(plane)
    alt(plane)
    K.decide_proposal(plane, ADMIN, K.proposals(plane, ADMIN)[0]["id"], False, "different measure")
    K.sync(plane, None)
    assert K.proposals(plane, ADMIN) == [] and len(K.concepts(plane, ADMIN)) == 2


def test_pack_synonym_is_a_proposal_and_the_model_can_say_they_differ(plane, monkeypatch):
    world(plane)
    monkeypatch.setattr(K, "_groups", lambda plane: [{"net worth", "total wealth"}])
    sign(plane, "alt2", "Wealth", [("TW", "Total wealth", "All we own less debts", "Pete")], AT6)
    (p,) = K.proposals(plane, ADMIN)
    assert p["by"] == "rules" and "industry pack" in p["reason"] and len(K.concepts(plane, ADMIN)) == 2
    # a near name the fast model says is a different measure is not proposed at all
    monkeypatch.setattr(K, "_ask_json", lambda *a, **k: {"same": False})
    sign(plane, "alt3", "Fees", [("NF", "Net worth fee drag", "Fees over net worth", "Pete")], "2026-10-07T09:00:00+00:00")
    K.sync(plane, object())
    assert len(K.proposals(plane, ADMIN)) == 1


def test_difference_prompt_has_no_digit_and_regenerates_when_a_definition_changes(plane, monkeypatch):
    seen = []

    def ask(model, plane, system, ctx, question, iid="", names=()):
        seen.append(ctx)
        return {"line": "Finance counts private funds at last NAV; Performance leaves them out."}
    monkeypatch.setattr(K, "_ask_json", ask)
    sign(plane, "fin1", "Finance monthly pack", [("NW", "Net worth", "Assets minus 2 liabilities, private funds at 90-day NAV", "Fiona")])
    sign(plane, "perf1", "Performance review", [("NW", "Net worth", "Assets minus liabilities, private funds excluded", "Pete")], AT5)
    K.sync(plane, object())
    assert seen and not any(ch.isdigit() for ch in json.dumps(seen[-1]))
    assert next(iter(read_json_strict(plane.path("graph", "k2.json"), dict)["diffs"].values()))["by"] == "model"
    n = len(seen)
    K.sync(plane, object())
    assert len(seen) == n  # unchanged definitions: not asked again
    sign(plane, "fin1", "Finance monthly pack", [("NW", "Net worth", "Assets minus liabilities, private funds at cost", "Fiona")])
    K.sync(plane, object())
    assert len(seen) == n + 1  # a changed definition: regenerated


def test_collision_fact_is_program_filled_and_choices_are_recorded(plane):
    a, b = world(plane)
    fact = K.collision_fact(plane, ADMIN, "net  WORTH")
    assert fact["concept"] == {"id": "concept:net-worth", "name": "Net worth"}
    assert {d["id"] for d in fact["definitions"]} == {"def:fin1:NW", "def:perf1:NW"} and {d["project_id"] for d in fact["definitions"]} == {a, b}
    assert fact["question"] == "Net worth already has two definitions in the company: Fiona and Pete. Do you mean one of these, or is yours different?"
    assert K.collision_fact(plane, ADMIN, "Gold price") is None
    assert K.collision_fact(plane, ADMIN, "Net worth", exclude_iid="fin1")["definitions"][0]["id"] == "def:perf1:NW"
    # a third intent says "different": a new variant under the same concept, with the reason
    sign(plane, "adv1", "Advisers", [("AW", "Adviser wealth", "Wealth as advisers quote it", "Olive")], "2026-10-09T09:00:00+00:00")
    K.record_choice(plane, "adv1", "AW", {"choice": "variant_of", "variant_of": "def:fin1:NW", "reason": "Advisers quote gross of tax"})
    v = next(c for c in K.concepts(plane, ADMIN) if c["id"] == "concept:net-worth")["variants"]
    assert len(v) == 3 and next(x for x in v if x["iid"] == "adv1")["why_different"] == "Advisers quote gross of tax"
    assert K.choice_for(plane, "adv1", "AW")["variant_of"] == "def:fin1:NW"
    # "new" makes its own concept even with the same name; a vague answer is refused
    sign(plane, "new1", "Another", [("NW", "Net worth", "Something else entirely", "Olive")], "2026-10-10T09:00:00+00:00")
    K.record_choice(plane, "new1", "NW", "new")
    assert len([c for c in K.concepts(plane, ADMIN) if c["name"] == "Net worth"]) == 2
    with pytest.raises(K.K2Refused):
        K.record_choice(plane, "new1", "NW", {"choice": "variant_of", "variant_of": "def:fin1:NW"})
    with pytest.raises(K.K2Refused):
        K.record_choice(plane, "new1", "NW", "maybe")


def test_a_suggestion_goes_to_the_owner_and_accepting_it_versions_the_definition(plane):
    a, _ = world(plane)
    s = K.suggest(plane, OUT, "def:fin1:NW", "change_definition", "Funds at cost is what the auditors use", value="Assets minus liabilities, funds at cost")
    c = next(c for c in P.comments(plane, a) if c["id"] == s["id"])
    assert c["kind"] == "suggestion" and c["to"] == "Fiona" and c["by"] == "Olive" and c["state"] == "open" and c["artefact"] == "intent"
    assert [x["id"] for x in K.suggestions(plane, FIN)] == [s["id"]] and K.suggestions(plane, PERF) == []
    with pytest.raises(K.K2Refused) as e:
        K.answer_suggestion(plane, PERF, s["id"], True)  # not the addressee
    assert e.value.status == 403
    with pytest.raises(K.K2Refused):
        K.answer_suggestion(plane, FIN, s["id"], False)  # a decline needs its reason
    K.answer_suggestion(plane, FIN, s["id"], True)
    d = next(v for v in K.concepts(plane, ADMIN)[0]["variants"] if v["id"] == "def:fin1:NW")
    assert d["definition"] == "Assets minus liabilities, funds at cost" and d["version"] == 2
    hist = read_json_strict(plane.path("graph", "k2.json"), dict)["edits"]["def:fin1:NW"]
    assert hist[0]["by"] == "Fiona" and hist[0]["suggested_by"] == "Olive" and hist[0]["suggestion"] == s["id"]
    assert "funds at cost" in K.concepts(plane, ADMIN)[0]["difference"]  # the difference line is regenerated for the new text
    # declining with a reason keeps the definition and says why
    s2 = K.suggest(plane, OUT, "def:perf1:NW", "change_owner", "Pete moved", value="Priya")
    K.answer_suggestion(plane, PERF, s2["id"], False, "Pete still owns it")
    assert next(x for x in K.suggestions(plane, OUT) if x["id"] == s2["id"])["state"] == "declined"
    assert next(v for v in K.concepts(plane, ADMIN)[0]["variants"] if v["id"] == "def:perf1:NW")["owner"] == "Pete"
    # add_synonym acts on the concept; the oldest definition's owner owns it
    s3 = K.suggest(plane, OUT, "concept:net-worth", "add_synonym", "Some say this", value="Total wealth")
    K.answer_suggestion(plane, FIN, s3["id"], True)
    assert "Total wealth" in K.concepts(plane, ADMIN)[0]["synonyms"] and K.collision_fact(plane, ADMIN, "total wealth")


def test_a_restricted_projects_definitions_are_the_teams_only(plane):
    sign(plane, "sec1", "Secret pack", [("NW", "Net worth", "Counts the trust assets", "Fiona")], sensitivity="restricted", team=("Fiona",))
    sign(plane, "pub1", "Open pack", [("NW", "Net worth", "Counts listed assets", "Pete")], AT5)
    seen_by_outsider = K.concepts(plane, OUT)
    assert [len(c["variants"]) for c in seen_by_outsider] == [1] and "trust" not in json.dumps(seen_by_outsider)
    assert "trust" not in json.dumps(K.answer(plane, OUT, "what does net worth mean?"))
    assert len(K.collision_fact(plane, OUT, "Net worth")["definitions"]) == 1
    assert len(K.concepts(plane, FIN)[0]["variants"]) == 2 and len(K.concepts(plane, ADMIN)[0]["variants"]) == 2
    with pytest.raises(K.K2Refused):
        K.suggest(plane, OUT, "def:sec1:NW", "other", "hmm")
    g = models.Graph()  # the map: the restricted definition is the team's node, the open one is everyone's
    m1_map.add_company_map_nodes(g, plane, {})
    assert g.nodes["def:sec1:NW"]["restricted_to"] is not None and g.nodes["def:pub1:NW"]["restricted_to"] is None
    assert ("def:pub1:NW", "concept:net-worth", "variant_of") in g.edges and g.nodes["concept:net-worth"]["type"] == "Concept"


def test_ask_answers_what_a_kpi_means_with_variants_and_owners(plane):
    world(plane, "open")
    (c,) = K.answer(plane, OUT, "What does net worth mean?")
    assert c["name"] == "Net worth" and {(v["team"], v["owner"]) for v in c["variants"]} == {("Fiona", "Fiona"), ("Pete", "Pete")} and c["difference"]
    assert K.answer(plane, OUT, "weather in Paris") == []


def test_the_owner_of_another_variant_hears_of_a_new_one_in_pulse(plane):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sign(plane, "fin1", "Finance monthly pack", [("NW", "Net worth", "Assets minus liabilities", "Fiona")], "2020-01-01T09:00:00+00:00")
    assert K.pulse_items(plane, FIN) == []  # one definition, no variant yet
    sign(plane, "perf1", "Performance review", [("NW", "Net worth", "Assets without funds", "Pete")], now)
    (item,) = K.pulse_items(plane, FIN)
    assert item["text"] == "Your Net worth definition now has a second variant: Pete's." and item["kind"] == "map_variant"
    assert K.pulse_items(plane, PERF) == [] and K.pulse_items(plane, OUT) == []


def test_project_creation_and_signing_land_on_the_map(plane):
    flag = plane.path("graph", "dirty")
    P.create_project(plane, "newone", "New work", "Ada")
    assert flag.is_file()
    flag.unlink()
    P.signed(plane, "newone", "build_pack", "Ada")
    assert flag.is_file()


def test_suggestion_shows_in_pulse_and_never_blocks_a_signature(plane):
    world(plane)
    s = K.suggest(plane, OUT, "def:fin1:NW", "other", "Check the wording")
    from sh_platform.v1 import p2_pulse
    p2_pulse._cache.clear()
    cards = p2_pulse.build(plane, FIN)["needs_you"]["cards"]
    assert any(c["kind"] == "suggestion" and c["href"].startswith("/centre/intent/graph?node=def:fin1:NW") for c in cards), cards
    assert P.sign_block(plane, "fin1", "intent", "Fiona") is None and s["to"] == "Fiona"


# ---- fixes after review --------------------------------------------------------------------------------------------------------------

def test_names_are_registered_with_the_vault_before_every_model_call(plane, monkeypatch):
    seen = []
    monkeypatch.setattr("sh_platform.build.agents.runtime.register_names", lambda pl, company, names: seen.append((company, list(names))))
    world(plane)
    K.enrich(plane, object())  # the real _ask_json: it registers, then the fake model fails to route and the stub stands
    names = {n for _, ns in seen for n in ns}
    assert {"Fiona", "Pete", "Finance monthly pack", "Performance review"} <= names and all(c == "" for c, _ in seen)
    seen.clear()
    K._ask_json(object(), plane, "system", {"first": "x"}, "q", names=["Priya", "", "Priya"])
    assert seen == [("", ["Priya"])]


def test_the_difference_line_is_rebuilt_by_the_model_after_an_accepted_edit(plane, monkeypatch):
    calls = []

    def ask(model, plane, system, ctx, question, iid="", names=()):
        calls.append(ctx)
        return {"line": "Finance " + ("counts funds at cost" if "at cost" in json.dumps(ctx) else "counts funds at last NAV") + "; Performance leaves them out."}
    monkeypatch.setattr(K, "_ask_json", ask)
    world(plane)
    K.sync(plane, object())
    assert "last NAV" in K.concepts(plane, ADMIN)[0]["difference"]
    s = K.suggest(plane, OUT, "def:fin1:NW", "change_definition", "Auditors use cost", value="Assets minus liabilities, funds at cost")
    n = len(calls)
    K.answer_suggestion(plane, FIN, s["id"], True)
    assert len(calls) == n  # the accept itself asks nobody
    now = K.concepts(plane, ADMIN)[0]["difference"]
    assert now.startswith("Worded differently") and "at cost" in now  # at once: the program's line, never the stale model line
    assert K.enrich(plane, object()) == 1  # the background job words it
    diff = next(iter(read_json_strict(plane.path("graph", "k2.json"), dict)["diffs"].values()))
    assert diff["by"] == "model" and "at cost" in K.concepts(plane, ADMIN)[0]["difference"]
    assert K.enrich(plane, object()) == 0  # and does not ask again for the same text


def test_no_model_call_in_a_rebuild_or_a_read_and_the_job_has_a_cap(plane, monkeypatch):
    calls = []
    monkeypatch.setattr(K, "_model", lambda plane: object())
    monkeypatch.setattr(K, "_ask_json", lambda *a, **k: calls.append(1) or {"line": "x", "same": True})
    world(plane)
    alt(plane)  # a word-overlap proposal too
    g = models.Graph()
    m1_map.add_company_map_nodes(g, plane, {})
    K.concepts(plane, ADMIN), K.concept(plane, ADMIN, "concept:net-worth"), K.proposals(plane, ADMIN), K.pulse_items(plane, FIN)
    K.collision_fact(plane, ADMIN, "Net worth"), K.answer(plane, ADMIN, "net worth"), K.sync(plane)
    pid = K.proposals(plane, ADMIN)[0]["id"]
    K.suggest(plane, OUT, "def:fin1:NW", "other", "hmm")
    K.decide_proposal(plane, ADMIN, pid, False, "no")
    assert calls == []
    # the job: three more concepts with two variants each; the cap of two stops it at two calls, the next run does the rest
    K.enrich(plane, object(), cap=50)
    calls.clear()
    for i in range(3):
        sign(plane, f"x{i}", f"X{i}", [("K", f"Kpi{i}", "One meaning", "Fiona")], AT1)
        sign(plane, f"y{i}", f"Y{i}", [("K", f"Kpi{i}", "Another meaning", "Pete")], AT5)
    assert K.enrich(plane, object(), cap=2) == 2 and len(calls) == 2
    assert K.enrich(plane, object(), cap=5) == 1 and len(calls) == 3  # the third pair; none twice
    assert K.enrich(plane, object()) == 0 and len(calls) == 3


def test_a_word_overlap_proposal_is_checked_by_the_model_in_the_background(plane, monkeypatch):
    world(plane)
    alt(plane)
    monkeypatch.setattr(K, "_ask_json", lambda *a, **k: {"same": False})
    assert len(K.proposals(plane, ADMIN)) == 1  # the rules' guess stands until the job has looked
    K.enrich(plane, object())
    assert K.proposals(plane, ADMIN) == [] and len(K.concepts(plane, ADMIN)) == 2


def test_an_internal_projects_definition_text_is_the_teams_not_a_strangers(plane):
    sign(plane, "in1", "Internal pack", [("NW", "Net worth", "Counts the trust assets", "Fiona")], sensitivity="internal", team=("Fiona",))
    sign(plane, "pub1", "Open pack", [("NW", "Net worth", "Counts listed assets", "Pete")], AT5, sensitivity="open")
    seen = K.concepts(plane, OUT)
    (c,) = seen
    mine = next(v for v in c["variants"] if v["iid"] == "in1")
    assert "trust" not in json.dumps(seen) + json.dumps(K.answer(plane, OUT, "net worth trust")) + json.dumps(K.collision_fact(plane, OUT, "Net worth"))
    assert mine["team"] == "Fiona" and mine["project"] == "Internal pack" and mine["hidden"] and mine["definition"] == "" and mine["owner"] is None
    assert c["name"] == "Net worth" and "trust" not in str(c["difference"])
    assert "trust" in json.dumps(K.concepts(plane, FIN)) and "trust" in json.dumps(K.concepts(plane, ADMIN))
    g = models.Graph()
    m1_map.add_company_map_nodes(g, plane, {})
    raw = {i: dict(n) for i, n in g.nodes.items()}
    for who, shown in ((OUT, False), (FIN, True)):
        nodes = [dict(n) for n in g.nodes.values()]
        K.gate_nodes(plane, who, nodes, raw)
        d, k = (next(n for n in nodes if n["id"] == i) for i in ("def:in1:NW", "concept:net-worth"))
        assert ("trust" in json.dumps(d)) is shown and bool(d.get("hidden")) is not shown
        assert d["label"] == "Net worth (Fiona)" and bool(k.get("hidden")) is not shown
        assert next(n for n in nodes if n["id"] == "def:pub1:NW")["definition"] == "Counts listed assets"


def test_a_suggestion_on_a_concept_whose_oldest_definition_is_hidden_goes_to_the_oldest_visible(plane):
    sign(plane, "sec1", "Secret pack", [("NW", "Net worth", "Counts the trust assets", "Fiona")], sensitivity="restricted", team=("Fiona",))
    sign(plane, "pub1", "Open pack", [("NW", "Net worth", "Counts listed assets", "Pete")], AT5, sensitivity="open")
    s = K.suggest(plane, OUT, "concept:net-worth", "add_synonym", "Another name", value="Wealth")
    assert s["to"] == "Pete" and s["def_id"] == "def:pub1:NW"
    assert K.suggest(plane, FIN, "concept:net-worth", "other", "hmm")["to"] == "Fiona"  # the team sees the oldest
    with pytest.raises(K.K2Refused):
        K.suggest(plane, OUT, "concept:gold", "other", "hmm")


def test_a_team_name_owner_falls_back_to_the_project_owner_then_an_admin(plane, monkeypatch):
    def people(*rows):
        monkeypatch.setattr(K.G1.K, "directory", lambda plane: {f"a{i}": {"name": n, "disabled": False, "roles": r} for i, (n, r) in enumerate(rows)})
    sign(plane, "fin1", "Finance pack", [("NW", "Net worth", "Assets minus liabilities", "Finance team")], sensitivity="open")  # raiser: Ada
    people(("Ada", ["company_admin"]), ("Pete", ["analyst"]))
    s = K.suggest(plane, OUT, "def:fin1:NW", "other", "Check this")
    assert s["to"] == "Ada"
    K.answer_suggestion(plane, ADMIN, s["id"], False, "Not now")  # and Ada can answer it
    people(("Zed", ["company_admin"]), ("Pete", ["analyst"]))  # the raiser has left: a company admin
    assert K.suggest(plane, OUT, "def:fin1:NW", "other", "Check again")["to"] == "Zed"
    people(("Fiona", ["analyst"]))
    sign(plane, "fin2", "Other pack", [("NW", "Net worth", "Assets", "Fiona")], AT5, sensitivity="open")
    assert K.suggest(plane, OUT, "def:fin2:NW", "other", "Hello")["to"] == "Fiona"  # a person with an account stays the answerer


def test_a_call_asks_g1_once_per_project_and_reads_the_projects_once(plane, monkeypatch):
    world(plane, "open")
    sign(plane, "z1", "Z", [("Q", "Quarterly view", "A view", "Fiona")], AT6, sensitivity="open")
    K.concepts(plane, OUT)
    seen = {"g1": 0, "prj": 0}
    real_g1, real_prj = K.G1.may_see_project, K.P.for_intent
    monkeypatch.setattr(K.G1, "may_see_project", lambda *a: seen.__setitem__("g1", seen["g1"] + 1) or real_g1(*a))
    monkeypatch.setattr(K.P, "for_intent", lambda *a: seen.__setitem__("prj", seen["prj"] + 1) or real_prj(*a))
    K.concepts(plane, OUT)
    assert seen == {"g1": 3, "prj": 0}  # one answer per project, and no scan of projects/ per intent
    seen["g1"] = 0
    K.pulse_items(plane, OUT)
    K.collision_fact(plane, OUT, "Net worth")
    assert seen["g1"] <= 6 and seen["prj"] == 0


def test_a_reopened_intent_keeps_showing_its_last_signed_text(plane):
    world(plane, "open")
    assert "last NAV" in json.dumps(K.concepts(plane, ADMIN))  # the map has seen it signed
    path = plane.path("intents", "fin1", "sow.json")
    sow = read_json_strict(path, dict)
    sow.update(state="draft", signature={})  # C2 reopens: the signature is cleared, the history stays
    sow["kpis"][0]["definition"] = "A draft the person is still typing"
    write_json_atomic(path, sow)
    got = json.dumps(K.concepts(plane, ADMIN))
    assert "last NAV" in got and "still typing" not in got
    sign(plane, "never1", "Never", [("Q", "Quarterly view", "Typed", "Fiona")], AT6)  # reopened before the map ever saw it signed: absent
    path = plane.path("intents", "never1", "sow.json")
    sow = read_json_strict(path, dict)
    sow.update(state="draft", signature={})
    write_json_atomic(path, sow)
    assert "Quarterly view" not in json.dumps(K.concepts(plane, ADMIN))


def test_a_choice_needs_a_real_intent_and_a_named_kpi(plane):
    world(plane)
    for iid in ("", "nosuch", "../x", None):
        with pytest.raises(K.K2Refused) as e:
            K.record_choice(plane, iid, "NW", "new")
        assert e.value.status == 404
    with pytest.raises(K.K2Refused) as e:
        K.record_choice(plane, "fin1", "  ", "new")
    assert e.value.status == 400
    assert "" not in K._load(plane)["choices"]
    K.record_choice(plane, "fin1", "NW" + "x" * 500, "new")
    assert all(len(k) <= 200 for k in read_json_strict(plane.path("graph", "k2.json"), dict)["choices"]["fin1"])


CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"


@pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
def test_routes_ask_suggest_and_answer_on_a_copy_of_the_demo(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from sh_platform.app import create_app
    from sh_platform.settings import Settings
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data", data)
    plane = PlaneStore(str(data)).plane_for("neera")
    sign(plane, "k2-a", "Finance pack", [("NW", "Net worth", "Assets minus liabilities", "Arjun Mehta")])
    sign(plane, "k2-b", "Performance pack", [("NW", "Net worth", "Assets minus liabilities, funds excluded", "Priya Nair")], AT5)
    plane.path("graph", "dirty").write_text("1", encoding="utf-8")
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    pw = {x.split()[0]: x.split()[1] for x in CREDS.read_text().splitlines() if x.strip() and not x.startswith("#")}

    def client(email):
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
        return c
    arjun, dev = client("arjun.mehta.neera@example.test"), client("dev.sharma.neera@example.test")
    got = dev.get("/api/v1/map/ask", params={"q": "what does net worth mean?"}).json()
    assert got["concepts"][0]["name"] == "Net worth" and len(got["concepts"][0]["variants"]) == 2
    assert any(n["type"] == "Definition" for n in dev.get("/api/v1/map").json()["nodes"])
    assert arjun.get("/api/v1/map/collision", params={"kpi": "Net worth"}).json()["fact"]["concept"]["id"] == "concept:net-worth"
    r = dev.post("/api/v1/map/suggestions", json={"node": "def:k2-a:NW", "kind": "change_definition", "text": "Auditors use cost", "value": "Assets minus liabilities at cost"})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert dev.post(f"/api/v1/map/suggestions/{cid}/accept").status_code == 403  # not the addressee
    assert arjun.post(f"/api/v1/map/suggestions/{cid}/decline", json={}).status_code == 400  # a reason is needed
    assert arjun.post(f"/api/v1/map/suggestions/{cid}/accept").status_code == 200
    v = next(x for x in arjun.get("/api/v1/map/concepts/concept:net-worth").json()["variants"] if x["id"] == "def:k2-a:NW")
    assert v["version"] == 2 and v["definition"] == "Assets minus liabilities at cost"
    # a choice: an empty or unknown intent is refused, and only the team of the project may write it (Ada raised both; Dev is not on them)
    assert arjun.post("/api/v1/map/choice", json={"iid": "", "kpi": "NW", "choice": "new"}).status_code == 404
    assert arjun.post("/api/v1/map/choice", json={"iid": "nosuch", "kpi": "NW", "choice": "new"}).status_code == 404
    assert dev.post("/api/v1/map/choice", json={"iid": "k2-a", "kpi": "NW", "choice": "new"}).status_code in (403, 404)
