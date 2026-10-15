"""Round-3 fixes N-H, N9, N10, N8, N-I, P6 and the Lens wording for module 2: exposure and capital-call suggestions, definitions
without the pack's label, documents used per measure (a restricted one only for a restricted measure), the request email, paraphrased
steps merged, "waiting on" markers and name kinds. Model calls are stubs; family-office example content only, synthetic."""
from pathlib import Path

import pytest
import yaml
from story_answers import answer, hop

from modules.m2_baseline.agent import lens
from modules.m2_baseline.agent import pack_text as P
from modules.m2_baseline.domain import process_map as D
from modules.m2_baseline.domain import requests as R
from sh_platform.agents.protocols import ModelReply
from sh_platform.context_docs.store import DocStore
from sh_platform.packs import PackLoader

PACKS = Path(__file__).resolve().parents[3] / "packs"
LOADER = PackLoader(PACKS)
FO = PACKS / "family_office" / "1"


def fo_guidance():
    return P.Guidance(None, yaml.safe_load((FO / "kpi_tree.yaml").read_text(encoding="utf-8"))["kpis"],
                      problems=yaml.safe_load((FO / "problems.yaml").read_text(encoding="utf-8"))["problems"])


# ---- N-H: suggestions

def ids(g, title, notes=()):
    return [k["id"] for k in P.kpis_for_problem(g, {"title": title, "notes": list(notes), "library_problem_id": None})]


def test_the_exposure_problem_gets_the_exposure_measures_even_with_notes_that_wander():
    g = fo_guidance()
    notes = ["Exposure to one name across funds, co-investments and direct holdings takes a week to build by hand",
             "private funds are not in the weekly report"]
    for n in ([], notes):
        assert {"K02", "K09", "K10", "K11", "K12"} <= set(ids(g, "No single exposure view", n))


def test_the_capital_call_problem_also_gets_the_document_and_pack_effort_measures():
    g = fo_guidance()
    assert {"K01", "K04", "K05", "K06", "K14", "K03"} <= set(ids(g, "Capital calls arrive too late", ["Calls reach us by email"]))


def test_a_pack_problem_that_names_no_measure_wins_nothing_and_links_point_at_real_measures():
    g = fo_guidance()
    assert all(p["id"] != "INT-SCOPE" for p in P.matching_pack_problems(g, {"title": "No single exposure view", "notes": ["entities and holdings"]}))
    known = {k["id"] for k in g.kpis}
    assert all(set(P._kpi_ids_of(p)) <= known for p in g.problems)


@pytest.mark.parametrize("industry", sorted(LOADER.industries()))
def test_every_industry_suggests_only_its_own_measures_and_an_empty_company_nothing(industry):
    g = P.load_guidance(LOADER, industry)
    own = {k["id"] for k in g.kpis}
    for title in ("No single exposure view", "Capital calls arrive too late", "Renewals leak"):
        assert {i for i in ids(g, title, ["notes about holdings and calls"])} <= own
    empty = P.load_guidance(LOADER, "")
    assert P.propose_kpis(empty, [{"id": "p", "title": "No single exposure view", "library_problem_id": None}], set()) == []


# ---- Lens definitions

def test_the_label_is_taken_out_of_a_sentence_and_the_pack_definition_has_none():
    assert P.strip_label("Industry practice (suggestion). Counts unpaid notices. Industry practice (suggestion).") == "Counts unpaid notices."
    assert P.strip_label("The share of valuations older than the limit (Industry practice (suggestion)).") == "The share of valuations older than the limit"
    g = P.Guidance(None, [{"id": "K1", "name": "x", "definition": "Industry practice: Count of x."}])
    assert P.pack_definition(g, "K1") == "Count of x."


class Seq:
    """A stub that answers each call with the next reply and keeps what it was asked."""
    def __init__(self, *replies):
        self.replies, self.asked = list(replies), []

    def complete(self, module_id, messages, tools=None):
        self.asked.append(messages[-1]["content"])
        return ModelReply(self.replies.pop(0))


class Open:
    def is_enabled(self, company_id, module_id):
        return True


def draft(model):
    return lens.draft_definition(model, Open(), "co-a", company_name="Co", industry="Family office", kpi_name="Documents needing review",
                                 pack="p", documents="d")


def test_a_model_that_writes_the_label_into_the_definition_has_it_stripped():
    out = draft(Seq("Counts the call notices not yet paid, by due date. Industry practice (suggestion)."))
    assert out == "Counts the call notices not yet paid, by due date."


def test_a_one_line_definition_that_only_restates_the_name_gets_one_retry_and_no_more():
    m = Seq("Documents needing review.", "Counts the documents with an open question, by type.")
    assert draft(m) == "Counts the documents with an open question, by type." and len(m.asked) == 2
    assert "say what is counted and how" in m.asked[1]
    m = Seq("Notices and reports with unresolved questions.", "Reports with questions.")
    assert draft(m) == "Reports with questions." and len(m.asked) == 2  # never a third try
    m = Seq("Counts the call notices not yet paid, by due date.")
    draft(m)
    assert len(m.asked) == 1  # a definition that says what is counted is not retried


def test_the_retrieval_query_has_the_name_the_pack_keywords_and_the_problem_titles():
    g = fo_guidance()
    q = P.retrieval_query(g, "K18", "Compensation inputs reconciled", ["Bonuses and trusted numbers"])
    assert {"bonus", "compensation", "Bonuses"} <= set(q.split())
    assert "valuation" in P.retrieval_query(g, "K12", "Stale-valuation share", []).lower()


def test_a_restricted_document_is_read_only_for_a_restricted_measure(world):
    plane = world.plane("co-a")
    s = DocStore(plane)
    s.upload("lens", "a", "bonus.md", b"The bonus pool rewards excess return against the benchmark. The committee approves each bonus.",
             title="Bonus policy", restricted=True)
    s.upload("lens", "a", "policy.md", b"The committee reviews each benchmark once a year. The committee approves the benchmark.", title="Policy")
    q = "Compensation inputs reconciled bonus pay committee benchmark"
    _, titles = lens.preread(plane, q)
    assert titles == ["Policy"]  # an ordinary measure never reads the restricted document
    text, titles = lens.preread(plane, q, restricted_ok=True)
    assert "Bonus policy" in titles and "bonus pool" in text


def test_a_restricted_measure_is_drafted_from_the_bonus_policy_only_for_a_person_who_may_see_it(world):
    from m2_kit import BASE, login
    from test_m2_worklist import confirm, kpi_of, seed_charter, start
    DocStore(world.plane("co-a")).upload("lens", "a", "bonus.md", b"Calls due, by date: the bonus pool rewards calls due by date. The committee approves each bonus.",
                                         title="Bonus policy", restricted=True)
    stub = Seq("Counts the calls due, by date.", "Counts the calls due, by date.")
    world.app.state.lens_model_factory = lambda plane: stub
    c = login(world, "co-a")
    v = confirm(c, start(c, seed_charter(world, "co-a")), name="Calls due, by date", problem_ids=["p1"])
    bid, kid = v["baseline"]["id"], v["kpis"][0]["id"]
    v = c.post(f"{BASE}/baselines/{bid}/lens/draft", json={}).json()
    assert stub.asked == [] and kpi_of(v, kid)["definition"]["mark"] == "unknown"  # not marked personal: the restricted document stays shut
    c.put(f"{BASE}/baselines/{bid}/kpis/{kid}/governance", json={"personal": "yes"})
    v = c.post(f"{BASE}/baselines/{bid}/lens/draft", json={"retry": True}).json()  # a second call skips what was tried (two tabs); a person asking again retries
    assert kpi_of(v, kid)["definition"]["from"] == "Bonus policy" and len(stub.asked) == 1


# ---- N10: the request email

def test_the_email_has_no_time_estimate_and_says_no_account_is_needed_only_to_people_without_one():
    plain = R.email_text("Wei Chen", "Mei Tan", ["A", "B", "C"], "https://x/answer/t")
    assert "minute" not in plain["body"] and "You can answer here without signing in" in plain["body"] and "Answer here: https://x/answer/t" in plain["body"]
    mine = R.email_text("Mei Tan", "Arjun Rao", ["A"], "https://x/answer/t", has_account=True)
    assert "No account is needed" not in mine["body"] and "Sign in" not in mine["body"] and "You can answer here without signing in" in mine["body"]  # R4 N10: the link needs no sign-in for anyone
    assert "minute" not in R.reminder_text("Wei", "Mei", ["A"])["body"]


# ---- N8, N-I: the process map

def mapped(*given, waiting=(), own=()):
    return D.draw(list(given), None, "pack", None, None, frozenset(), list(waiting), list(own))["steps"]


def test_two_owners_wording_of_one_step_is_one_step_with_both_owners():
    a = answer("a", "Sara Lim", "K01", in_between=[hop("Sara Lim", "Finance", "Review draft pack", 1), hop("Sara Lim", "Finance", "Tracker calls", 2)])
    b = answer("b", "Mei Tan", "K01", in_between=[hop("Mei Tan", "Finance", "Conduct review", 1), hop("Mei Tan", "Finance", "Calls", 2)])
    steps = mapped(a, b)
    assert [s["text"] for s in steps] == ["Review draft pack", "Tracker calls"]
    assert all(s["also_from"] == ["b"] for s in steps)
    pair = lambda x, y: D.paraphrased(x, y)  # noqa: E731
    assert pair("Pastes levels into the workbook", "Copies values into the exposure workbook")


def test_different_steps_and_other_lanes_stay_apart():
    assert not D.paraphrased("Review the draft pack", "Send the draft pack")
    assert not D.paraphrased("Pastes levels into the workbook", "Pastes levels into the portal")
    a = answer("a", "Sara Lim", "K01", in_between=[hop("Sara Lim", "Finance", "Review draft pack", 1)])
    b = answer("b", "Mei Tan", "K01", in_between=[hop("Mei Tan", "Investments", "Conduct review", 1)])
    assert len(mapped(a, b)) == 2


def test_an_owner_who_has_not_answered_gets_a_dashed_waiting_step_unless_a_step_already_asks_them():
    a = answer("a", "Mei Tan", "K09", in_between=[hop("Mei Tan", "Finance", "Builds the pack page", 1)])
    steps = mapped(a, waiting=["Wei Chen"], own=["Wei Chen"])
    wait = [s for s in steps if s.get("waiting")]
    assert [(s["text"], s["lane"], s["confirmed"], s["ask"]) for s in wait] == [("Waiting on Wei Chen", "Wei Chen", False, "Wei Chen")]
    assert D.mark_of(wait[0]) == "to_confirm"
    b = answer("b", "Mei Tan", "K09", in_between=[hop("Wei", "Finance", "Builds the exposure workbook", 1)])
    assert not [s for s in mapped(b, waiting=["Wei Chen"], own=["Wei Chen"]) if s.get("waiting")]  # the step is already dashed with "ask"
    assert not [s for s in mapped(a, waiting=["Wei Chen"]) if s.get("waiting")]  # an owner of another measure gets no marker here


def test_a_reword_may_not_add_a_verb():
    assert not D.keeps_words("Funding pack page", "Prepare funding pack page")
    assert not D.keeps_words("Due dates", "Extract due dates")
    assert D.keeps_words("Sends the funding pack page", "Sends funding pack page")


# ---- P6: name kinds

def test_organisations_are_companies_and_a_role_plus_the_company_word_is_nobody():
    people, orgs = lens.sort_names("Illustrative Lakeside Family Office",
                                   ["Wei Chen", "Wei", "Northgate Custody", "Bluewater Fund Services", "Sponsor Lakeside", "Company Admin (Lakeside Family Office)"])
    assert people == ["Wei Chen", "Wei"] and orgs == ["Northgate Custody", "Bluewater Fund Services"]


def test_the_vault_holds_organisations_as_company_and_never_sponsor_lakeside(world):
    from sh_platform.egress.vault import NameVault
    plane = world.plane("co-a")
    lens.register_names(plane, "Illustrative Lakeside Family Office", ["Wei Chen", "Northgate Custody", "Sponsor Lakeside"])
    held = {(e["kind"], e["name"]) for e in NameVault(plane)._state().entries.values()}
    assert ("company", "Northgate Custody") in held and ("person", "Wei Chen") in held
    assert not any(n.startswith("Sponsor") for k, n in held) and ("person", "Northgate Custody") not in held


# ---- review round: governance can only be lowered by the admin or sponsor; restricted text only for a pay measure

def pay_world(world):
    from m2_kit import BASE, login
    from test_m2_worklist import confirm, seed_charter, start
    DocStore(world.plane("co-a")).upload(
        "lens", "a", "bonus.md", b"Calls due, by date: the bonus pool rewards calls due by date. The committee approves each bonus. The pool is SGD 600 thousand.",
        title="Bonus policy", restricted=True)
    world.app.state.lens_model_factory = lambda plane: Seq("Counts the calls due, by date.", "Counts the calls due, by date.")
    admin = login(world, "co-a", "Pat Owner", ("company_admin",))
    v = confirm(admin, start(admin, seed_charter(world, "co-a")), name="Calls due, by date", problem_ids=["p1"])
    return admin, v["kpis"][0]["id"], f"{BASE}/baselines/{v['baseline']['id']}"


def test_only_the_admin_or_sponsor_can_lower_personal_or_sensitive(world):
    from m2_kit import login
    admin, kid, base = pay_world(world)
    admin.put(f"{base}/kpis/{kid}/governance", json={"personal": "yes", "sensitive": True, "may_see": ["Test Wei Lim"]})
    named = login(world, "co-a", "Wei Lim", ("analyst",))
    for body in ({"personal": "no"}, {"personal": "not_sure"}, {"sensitive": False}):
        assert named.put(f"{base}/kpis/{kid}/governance", json=body).status_code == 403
    assert named.put(f"{base}/kpis/{kid}/governance", json={"personal": "yes", "sensitive": True}).status_code == 200  # no change is no lowering
    assert admin.put(f"{base}/kpis/{kid}/governance", json={"sensitive": False}).status_code == 200


def test_relaxing_a_pay_measure_clears_a_definition_drawn_from_a_restricted_document(world):
    from test_m2_worklist import kpi_of
    admin, kid, base = pay_world(world)
    admin.put(f"{base}/kpis/{kid}/governance", json={"personal": "yes"})
    v = admin.post(f"{base}/lens/draft", json={}).json()
    assert kpi_of(v, kid)["definition"]["from"] == "Bonus policy"
    v = admin.put(f"{base}/kpis/{kid}/governance", json={"personal": "no"}).json()
    assert kpi_of(v, kid)["definition"]["mark"] == "unknown" and kpi_of(v, kid)["definition_proposal"] is None


def test_a_merely_sensitive_measure_never_reads_a_restricted_document_and_figures_are_cut(world):
    from test_m2_worklist import kpi_of
    admin, kid, base = pay_world(world)
    admin.put(f"{base}/kpis/{kid}/governance", json={"personal": "no", "sensitive": True})
    v = admin.post(f"{base}/lens/draft", json={}).json()
    assert kpi_of(v, kid)["definition"]["mark"] == "unknown"
    text, _ = lens.preread(world.plane("co-a"), "calls due by date bonus pool", restricted_ok=True)
    assert "600" not in text and "committee approves each bonus" in text.lower()  # a sentence with a figure never leaves


def test_a_name_with_a_job_title_registers_the_person_and_keeps_a_surname_after_a_title():
    people, orgs = lens.sort_names("Illustrative Lakeside Family Office",
                                   ["Mei Tan Chief Executive Officer", "Director Lee", "Northgate Custody", "Sponsor Lakeside"])
    assert people == ["Mei Tan", "Lee"] and orgs == ["Northgate Custody"]


def test_the_requests_email_looks_only_at_measures_the_caller_may_see():
    class Store:
        def kpi_names(self):
            return {"K1": "One", "K2": "Two"}

        def kpis(self):
            return [{"id": "K1", "owners": {"business": {"value": "Wei Chen", "account_id": None}}},
                    {"id": "K2", "owners": {"business": {"value": "Wei Chen", "account_id": "acct-9"}}}]
    from modules.m2_baseline.api import requests as api
    row = {"owner_name": "Wei Chen", "kpi_ids": ["K1", "K2"]}
    for only in ({"K1", "K2"}, {"K1"}):  # K2 is hidden from the caller in the second: the words are the same either way
        assert "You can answer here without signing in" in api._email(Store(), row, "Mei", link="https://x", only=only)["body"]
