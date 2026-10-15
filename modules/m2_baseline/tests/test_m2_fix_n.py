"""M2-FIX-N: the owner form's payload shape (D3) and the answer refusal that names the step."""
import pytest
from test_m2_answers import GOOD, save, tom  # noqa: F401  (tom is a fixture)
from test_m2_worklist import rich_packs, start  # noqa: F401  (rich_packs gives the packs a problem that lists measures)

from modules.m2_baseline.domain.questionnaire import AnswerError, clean_answers, load_questionnaire


def test_the_payload_the_screen_builds_is_accepted_for_every_step_kind(tom):
    answers = {**GOOD,
               "upstream": {"value": [{"who": "Bank", "what": "Statement"}], "mark": "stated"},  # no manual upstream or downstream
               "in_between": {"value": [{"who": "Sara", "step": "Workbook", "manual": False}], "mark": "stated"},  # manual only here
               "downstream": {"value": [{"who": "Board", "what": "Pack", "team": "IC", "order": "3"}], "mark": "stated"}}
    rec = save(tom[1], answers=answers)["saved"]
    assert rec["in_between"]["value"][0]["manual"] is False


def test_a_manual_flag_on_an_upstream_step_is_refused_naming_the_step():
    bad = {"upstream": {"value": [{"who": "Bank", "what": "x"}, {"who": "A", "what": "y", "manual": False}], "mark": "stated"}}
    with pytest.raises(AnswerError) as e:
        clean_answers(load_questionnaire(), bad, by="T", source="s")
    assert "Step 2 in the upstream list" in str(e.value) and "manual" in str(e.value)


# ---- D8: all four charter lists reach module 2 ------------------------------------------------------------------------
def _four_lists(world, extra=True):
    import json

    from test_m2_worklist import PROBLEMS, seed_charter
    oid = seed_charter(world)
    if extra:
        f = world.plane("co-a").path("intents", "m1_intent", "outcomes", f"{oid}.json")
        doc = json.loads(f.read_text())
        doc.update(pain_points=[{"id": "pp1", "title": "Calls arrive too late, again", "priority": "must", "so_that": None, "note_count": 1, "details": [], "library_problem_id": "lib1"}],
                   future_signals=[{"id": "fs1", "title": "Interest rate moves", "priority": None, "note_count": 1}],
                   levers=[{"id": "lv1", "title": "Call notice period", "priority": None, "note_count": 1}])
        f.write_text(json.dumps(doc))
    return oid, len(PROBLEMS)


def test_pain_points_future_signals_and_levers_come_from_the_charter_and_add_up(world):
    from test_m2_worklist import rich_packs, start  # noqa: F401
    c = login(world, "co-a")
    oid, intents = _four_lists(world)
    assert c.get(f"/api/modules/m2_baseline/baselines").json()["charters"][0]["problem_count"] == intents + 3  # M1's "3 go on" counts all four
    view = start(c, oid)
    groups = {g["key"]: [i["title"] for i in g["items"]] for g in view["charter_groups"]}
    assert groups == {"problems": ["Calls arrive too late", "Nobody trusts the numbers"], "pain_points": ["Calls arrive too late, again"],
                      "future_signals": ["Interest rate moves"], "levers": ["Call notice period"]}
    assert sum(len(v) for v in groups.values()) == intents + 3
    pain = next(p for p in view["problems"] if p["id"] == "pp1")
    assert pain["kind"] == "pain_point" and [p["id"] for p in view["problems"]] == ["p1", "p2", "pp1"]  # future signals and levers are not problems
    assert any("pp1" in s["problem_ids"] for s in view["suggestions"])  # the same matcher gives a pain point its measures


def test_lens_is_given_future_signals_and_levers_as_facts(world):
    from modules.m2_baseline.domain.triage import charter_facts
    from modules.m2_baseline.store.baseline import read_charter
    charter = read_charter(world.plane("co-a"), _four_lists(world)[0])
    assert charter_facts(charter) == ["Charter: to track in future: Interest rate moves.", "Charter lever for what-if: Call notice period."]


def test_an_old_charter_without_the_new_lists_still_works(world):
    from test_m2_worklist import rich_packs, start  # noqa: F401
    c = login(world, "co-a")
    oid, intents = _four_lists(world, extra=False)
    view = start(c, oid)
    assert [g["key"] for g in view["charter_groups"] if g["items"]] == ["problems"] and len(view["problems"]) == intents
    assert c.get("/api/modules/m2_baseline/baselines").json()["charters"][0]["problem_count"] == intents


# ---- D5: one clear Lens state --------------------------------------------------------------------------------------------
def test_lens_never_says_filled_all_and_still_drafting_all_and_never_blames_the_model_after_a_good_draft(world):
    c = login(world, "co-a")
    view = start(c, _four_lists(world, extra=False)[0])
    state = c.get(f"/api/modules/m2_baseline/baselines/{view['baseline']['id']}/lens").json()
    did = state["say"]["did"]
    assert state["pending"]  # nothing is attempted yet, yet the pack's wording already fills every suggestion
    assert not ("I filled a definition" in did and "still drafting" in did), did
    assert "could not reach" not in did and "could not reach" not in state["say"]["need"]


def test_sentences_say_one_thing_about_progress():
    from modules.m2_baseline.domain.lens_view import sentences
    kw = dict(pack_available=True, label="x", problems=2, suggested=9, measures=0, failed=0, nothing=0, available=True, locked=False, asking=None)
    mid = sentences(drafted=9, pending=9, **kw)["did"]
    assert "still drafting" not in mid or "filled a definition" not in mid
    done = sentences(drafted=9, pending=0, **kw)["did"]
    assert "I filled a definition for 9 of 9." in done and "drafting" not in done


# ---- D11: the link shown and the link in the email text are one ------------------------------------------------------------
def test_the_shown_link_and_the_email_link_are_the_same_with_and_without_a_configured_base(world, monkeypatch):
    import json

    from test_m2_signoff_privacy import RBASE, RBID, seed_requests
    seed_requests(world)
    org = login(world, "co-a")
    monkeypatch.delenv("SH_PUBLIC_BASE_URL", raising=False)
    # dev: the API is on :8200 and the page that asked is the UI on :8201, both this machine
    out = org.post(f"{RBASE}/baselines/{RBID}/requests", headers={"origin": "http://127.0.0.1:8201", "host": "127.0.0.1:8200"}).json()["sent"][0]
    assert out["address"].startswith("http://127.0.0.1:8201/answer/") and out["address"] in json.dumps(out["email"])
    monkeypatch.setenv("SH_PUBLIC_BASE_URL", "https://harbor.example.test")
    again = org.post(f"{RBASE}/baselines/{RBID}/requests/{out['id']}/relink", headers={"origin": "http://127.0.0.1:8201"}).json()
    assert again["address"].startswith("https://harbor.example.test/answer/") and again["address"] in json.dumps(again["email"])


# ---- D4: a named owner of any role reads and confirms exactly their own parts ----------------------------------------
from m2_kit import login  # noqa: E402
from test_m2_signoff_kit import BID, PEOPLE, seed  # noqa: E402


@pytest.mark.parametrize("role,key,part", [("approver", "bea", "definition"), ("participant", "dan", "source")])
def test_an_approver_or_participant_owner_sees_and_confirms_only_their_own_part(world, role, key, part):
    seed(world)
    c = login(world, "co-a", PEOPLE[key], (role,))
    base = f"/api/modules/m2_baseline/baselines/{BID}"
    assert c.get(f"{base}/review").status_code == 403  # the full review stays closed to them
    mine = c.get(f"{base}/my-parts")
    assert mine.status_code == 200
    got = mine.json()["parts"]
    assert got and {p["part"] for p in got} == {part}
    assert set(mine.json()) == {"status", "parts"}  # nothing else leaves: no other owner, no other measure's content
    r = c.post(f"{base}/confirm", json={"kpi_id": "K1", "part": part})
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"status", "parts"}  # the answer to a confirm holds nothing but their own parts
    assert next(p for p in c.get(f"{base}/my-parts").json()["parts"] if p["kpi_id"] == "K1")["confirmed"] is True
    assert c.post(f"{base}/confirm", json={"kpi_id": "K1", "part": "process"}).status_code == 409  # not their part


def test_a_participant_who_owns_nothing_sees_no_parts(world):
    seed(world)
    c = login(world, "co-a", "Just Passing", ("participant",))
    assert c.get(f"/api/modules/m2_baseline/baselines/{BID}/my-parts").json()["parts"] == []
