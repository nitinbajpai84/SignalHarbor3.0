"""M2-P01: start from a signed charter, the work list, triage, owners and governance (M2-01 to M2-05, M2-31).
Two industries with tiny packs, an industry with no pack, a company without module 2, and one person alone."""
import json
import secrets

import pytest
import yaml
from m2_kit import BASE, login

from modules.m2_baseline.domain.provenance import MARKS
from modules.m2_baseline.store.baseline import read_baseline
from modules.m2_baseline.store.kpis import read_kpis

PROBLEMS = [{"id": "p1", "title": "Calls arrive too late", "priority": "must", "so_that": "we can plan cash",
             "note_count": 3, "library_problem_id": "lib1"},
            {"id": "p2", "title": "Nobody trusts the numbers", "priority": "should", "so_that": None,
             "note_count": 1, "library_problem_id": None}]


@pytest.fixture(autouse=True)
def rich_packs(world):
    """The kit's packs only have a KPI tree; add a problem that lists KPIs and defaults with a question, per industry."""
    for industry in ("industry_a", "industry_b"):
        folder = world.packs / industry / "1"
        (folder / "problems.yaml").write_text(yaml.safe_dump({"problems": [
            {"id": "lib1", "question": "Late calls?", "kpi_ids": ["K0", "K1"]}]}))
        (folder / "industry_defaults.yaml").write_text(yaml.safe_dump({"defaults": [
            {"kpi_id": "K0", "definition_variants": [{"variant": f"{industry} usual definition 0"}],
             "customer_decides": [{"question": "Who approves the reserve?", "fields": []}]}]}))


def seed_charter(world, company="co-a", problems=PROBLEMS) -> str:
    oid = secrets.token_hex(16)
    folder = world.plane(company).path("intents", "m1_intent", "outcomes")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{oid}.json").write_text(json.dumps({
        "outcome_id": oid, "session_id": "s" * 32, "module": "m1_intent", "kind": "charter", "charter_version": 1,
        "signed_at": "2026-10-01T10:00:00+00:00", "signatures": [], "template": "t", "problems": problems, "later": [], "footer": {}}))
    return oid


def start(c, oid):
    r = c.post(f"{BASE}/baselines", json={"charter_outcome_id": oid})
    assert r.status_code in (200, 201), r.text
    return r.json()


def kpi_url(view, kid, tail=""):
    return f"{BASE}/baselines/{view['baseline']['id']}/kpis/{kid}{tail}"


def confirm(c, view, **body):
    r = c.post(f"{BASE}/baselines/{view['baseline']['id']}/kpis", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def kpi_of(view, kid):
    return next(k for k in view["kpis"] if k["id"] == kid)


# ---- M2-01: start from the signed charter; no KPI until a person confirms

def test_a_baseline_starts_from_a_signed_charter_once(world):
    c, oid = login(world, "co-a"), seed_charter(world)
    listed = c.get(f"{BASE}/baselines").json()
    assert [x["outcome_id"] for x in listed["charters"]] == [oid] and listed["charters"][0]["baseline_id"] is None
    r = c.post(f"{BASE}/baselines", json={"charter_outcome_id": oid})
    assert r.status_code == 201
    b = r.json()["baseline"]
    assert b["charter_outcome_id"] == oid and b["state"] == "draft" and len(b["id"]) == 32 and b["created_at"]
    again = c.post(f"{BASE}/baselines", json={"charter_outcome_id": oid})
    assert again.status_code == 200 and again.json()["baseline"]["id"] == b["id"]  # one baseline per signed charter
    assert c.get(f"{BASE}/baselines").json()["charters"][0]["baseline_id"] == b["id"]


def test_an_unknown_charter_is_refused_in_plain_words(world):
    c = login(world, "co-a")
    r = c.post(f"{BASE}/baselines", json={"charter_outcome_id": "f" * 32})
    assert r.status_code == 404 and "signed charter" in r.json()["message"]
    assert c.post(f"{BASE}/baselines", json={"charter_outcome_id": "../x"}).status_code == 404


def test_lens_suggests_but_no_kpi_exists_until_a_person_confirms(world):
    c, oid = login(world, "co-a"), seed_charter(world)
    v = start(c, oid)
    assert v["kpis"] == [] and read_kpis(world.plane("co-a"), v["baseline"]["id"]) == []
    assert [s["name"] for s in v["suggestions"]] == ["industry_a measure 0", "industry_a measure 1"]
    assert v["suggestions"][0]["problem_ids"] == ["p1"] and "suggestion" in v["suggestion_label"].lower()
    assert [p["has_kpi"] for p in v["problems"]] == [False, False]  # a charter problem with no KPI is shown as such
    v = confirm(c, v, suggestion_id="K0", problem_ids=["p1"])
    k = kpi_of(v, "K0")
    assert k["definition"]["mark"] == "guessed" and k["definition"]["by"] == "the pack" and "suggestion" in k["definition"]["from"]
    assert k["definition"]["value"] == "industry_a usual definition 0" and k["priority"] == "must"
    assert [p["has_kpi"] for p in v["problems"]] == [True, False]
    assert [s["id"] for s in v["suggestions"]] == ["K1"]  # a confirmed one is no longer suggested


def test_states_follow_the_kpi_from_not_started_to_signed(world):
    c, oid = login(world, "co-a"), seed_charter(world)
    v = confirm(c, start(c, oid), name="Calls received late")
    kid = v["kpis"][0]["id"]
    assert v["kpis"][0]["state"] == "questions_open"  # the formula is a question for the business, never invented
    q = v["kpis"][0]["questions"][0]
    v = c.put(kpi_url(v, kid, f"/questions/{q['id']}"), json={"answer": "Calls are priced at notice date."}).json()
    assert kpi_of(v, kid)["state"] == "not_started"  # a definition is still unknown
    v = c.put(kpi_url(v, kid, "/triage"), json={"definition": {"text": "Calls due, by date", "mark": "stated"}}).json()
    assert kpi_of(v, kid)["state"] == "drafted"
    base = world.plane("co-a").path("intents", "m2_baseline", v["baseline"]["id"], "baseline.json")
    base.write_text(json.dumps({**v["baseline"], "state": "signed"}))
    assert kpi_of(c.get(f"{BASE}/baselines/{v['baseline']['id']}").json(), kid)["state"] == "signed"


def test_the_list_can_be_added_to_and_removed_from(world):
    c, oid = login(world, "co-a"), seed_charter(world)
    v = confirm(c, start(c, oid), name="Funding headroom", problem_ids=["p2", "nope"])
    k = v["kpis"][0]
    assert k["problem_ids"] == ["p2"] and k["priority"] == "should" and k["id"].startswith("kpi-")
    assert c.post(f"{BASE}/baselines/{v['baseline']['id']}/kpis", json={"name": "  "}).status_code == 400
    v = c.delete(kpi_url(v, k["id"])).json()
    assert v["kpis"] == [] and c.delete(kpi_url(v, k["id"])).status_code == 404


# ---- the industry is a parameter; an empty company; one person alone (M2-31)

@pytest.mark.parametrize("company,industry", [("co-a", "industry_a"), ("co-b", "industry_b")])
def test_each_company_gets_its_own_industrys_suggestions(world, company, industry):
    c = login(world, company)
    v = start(c, seed_charter(world, company))
    assert all(s["name"].startswith(industry) for s in v["suggestions"]) and v["suggestions"]
    assert v["pack"] == {"available": True, "label": industry}


def test_a_company_with_no_pack_starts_empty_with_an_add_action(world):
    c = login(world, "co-none")
    v = start(c, seed_charter(world, "co-none"))
    assert v["suggestions"] == [] and v["pack"]["available"] is False and v["kpis"] == []
    assert [p["has_kpi"] for p in v["problems"]] == [False, False]
    v = confirm(c, v, name="Meeting-pack effort")
    assert v["kpis"][0]["definition"]["mark"] == "unknown" and v["kpis"][0]["definition"]["value"] is None


def test_one_person_without_module_1_starts_from_nothing_and_is_all_three_owners(world):
    c = login(world, "co-solo")
    assert c.get(f"{BASE}/baselines").json() == {"charters": [], "baselines": []}
    v = start(c, None)
    assert v["charter"] is None and v["problems"] == [] and v["baseline"]["charter_outcome_id"] is None
    v = confirm(c, v, name="Cash on hand")
    kid = v["kpis"][0]["id"]
    me = {"name": "Test Pat Owner", "has_account": True}
    v = c.put(kpi_url(v, kid, "/owners"), json={"business": me, "data": me, "process": me}).json()
    k = kpi_of(v, kid)
    assert k["missing_owners"] == [] and v["owners_complete"] == 1
    assert {o["value"] for o in k["owners"].values()} == {"Test Pat Owner"}


# ---- M2-02: triage, four things, each stated, guessed or unknown

def test_triage_shows_four_things_each_with_its_mark_and_who(world):
    c = login(world, "co-a")
    v = confirm(c, start(c, seed_charter(world)), suggestion_id="K0", problem_ids=["p1"])
    t = kpi_of(v, "K0")["triage"]
    assert set(t) == {"definition", "owner", "producer", "gathered", "unknown"}
    assert t["unknown"] == ["owner", "producer", "gathered"] and t["definition"]["mark"] == "guessed"
    assert all(t[f]["mark"] in MARKS and "by" in t[f] for f in ("definition", "owner", "producer", "gathered"))
    v = c.put(kpi_url(v, "K0", "/triage"), json={"gathered": {"text": "emails", "mark": "guessed"},
                                                  "producer": {"text": "The fund administrator", "mark": "stated"}}).json()
    t = kpi_of(v, "K0")["triage"]
    assert t["gathered"]["mark"] == "guessed" and t["gathered"]["by"] == "Test Pat Owner"
    assert t["producer"]["value"] == "The fund administrator" and t["unknown"] == ["owner"]
    v = c.put(kpi_url(v, "K0", "/triage"), json={"gathered": {"mark": "unknown"}}).json()
    assert kpi_of(v, "K0")["gathered"]["value"] is None and "gathered" in kpi_of(v, "K0")["triage"]["unknown"]


def test_triage_refuses_a_value_without_a_mark_or_text(world):
    c = login(world, "co-a")
    v = confirm(c, start(c, seed_charter(world)), suggestion_id="K0")
    for body in ({"producer": {"text": "x"}}, {"producer": {"text": "", "mark": "stated"}}, {}, {"producer": "x"}):
        assert c.put(kpi_url(v, "K0", "/triage"), json=body).status_code == 400


def test_a_stated_definition_is_never_replaced_by_a_new_draft(world):
    c = login(world, "co-a")
    v = confirm(c, start(c, seed_charter(world)), suggestion_id="K0")
    c.put(kpi_url(v, "K0", "/triage"), json={"definition": {"text": "Our own words", "mark": "stated"}})
    v = c.post(f"{BASE}/baselines/{v['baseline']['id']}/lens/draft", json={}).json()
    assert kpi_of(v, "K0")["definition"]["value"] == "Our own words"


# ---- M2-04: three owners by name, with or without an account; decline

def test_nominate_three_owners_records_who_and_when_and_account(world):
    c = login(world, "co-a")
    v = confirm(c, start(c, seed_charter(world)), suggestion_id="K0")
    v = c.put(kpi_url(v, "K0", "/owners"), json={"business": {"name": "Mei Tan", "has_account": True},
                                                 "data": {"name": "Arjun Rao"}}).json()
    k = kpi_of(v, "K0")
    assert k["owners"]["business"]["value"] == "Mei Tan" and k["owners"]["business"]["by"] == "Test Pat Owner"
    assert k["owners"]["business"]["at"] and "with an account" in k["owners"]["business"]["from"]
    assert "no account" in k["owners"]["data"]["from"]
    assert k["missing_owners"] == ["process"] and v["owners_complete"] == 0  # a missing owner shows as "no owner"
    assert k["triage"]["owner"]["value"] == "Mei Tan"


def test_declining_returns_the_nomination_to_the_organiser(world):
    c = login(world, "co-a")
    v = confirm(c, start(c, seed_charter(world)), suggestion_id="K0")
    v = c.put(kpi_url(v, "K0", "/owners"), json={"data": {"name": "Arjun Rao"}}).json()
    v = c.post(kpi_url(v, "K0", "/owners/data/decline")).json()
    o = kpi_of(v, "K0")["owners"]["data"]
    assert o["mark"] == "unknown" and o["value"] is None and o["from"] == "declined by Arjun Rao"
    assert c.post(kpi_url(v, "K0", "/owners/data/decline")).status_code == 400  # nobody left to decline
    assert c.post(kpi_url(v, "K0", "/owners/chief/decline")).status_code == 404


def test_withdrawing_or_a_bad_nomination(world):
    c = login(world, "co-a")
    v = confirm(c, start(c, seed_charter(world)), suggestion_id="K0")
    c.put(kpi_url(v, "K0", "/owners"), json={"process": {"name": "Sara"}})
    v = c.put(kpi_url(v, "K0", "/owners"), json={"process": {"name": ""}}).json()
    assert kpi_of(v, "K0")["owners"]["process"]["mark"] == "unknown"
    assert c.put(kpi_url(v, "K0", "/owners"), json={}).status_code == 400
    assert c.put(kpi_url(v, "K0", "/owners"), json={"business": {"name": "x" * 500}}).status_code == 400


# ---- M2-05: governance, enforced on the server

def test_not_sure_is_kept_and_treated_as_personal(world):
    c = login(world, "co-a")
    v = confirm(c, start(c, seed_charter(world)), suggestion_id="K0")
    k = kpi_of(v, "K0")
    assert k["governance"] == {"personal": "not_sure", "sensitive": False, "may_see": []} and k["treated_as_personal"] is True
    v = c.put(kpi_url(v, "K0", "/governance"), json={"personal": "no", "sensitive": True, "may_see": ["Mei", "Wei", "Mei"]}).json()
    k = kpi_of(v, "K0")
    assert k["governance"] == {"personal": "no", "sensitive": True, "may_see": ["Mei", "Wei"]} and k["treated_as_personal"] is False
    for bad in ({"personal": "maybe"}, {"sensitive": "yes"}, {"may_see": "Mei"}, {"may_see": [1]}):
        assert c.put(kpi_url(v, "K0", "/governance"), json=bad).status_code == 400


def test_people_not_named_see_that_it_exists_but_not_what_is_in_it(world):
    admin = login(world, "co-a", "Pat Owner", ("company_admin",))
    v = confirm(admin, start(admin, seed_charter(world)), suggestion_id="K0")
    admin.put(kpi_url(v, "K0", "/owners"), json={"business": {"name": "Mei Tan"}})
    admin.put(kpi_url(v, "K0", "/governance"), json={"personal": "yes", "may_see": ["Test Wei Lim"]})
    outsider, named = login(world, "co-a", "Sam Outsider", ("analyst",)), login(world, "co-a", "Wei Lim", ("analyst",))
    url = f"{BASE}/baselines/{v['baseline']['id']}"
    seen = outsider.get(url).json()["kpis"][0]
    assert seen == {"id": "K0", "name": "A restricted measure", "restricted": True, "state": "not_started"}  # R4 defect 5: no name
    assert "Mei Tan" not in outsider.get(url).text and "industry_a usual definition" not in outsider.get(url).text
    assert named.get(url).json()["kpis"][0]["restricted"] is False and admin.get(url).json()["kpis"][0]["restricted"] is False
    # and every write is refused for the person not named
    for call in (lambda: outsider.put(kpi_url(v, "K0", "/owners"), json={"data": {"name": "Zed"}}),
                 lambda: outsider.put(kpi_url(v, "K0", "/triage"), json={"producer": {"text": "x", "mark": "stated"}}),
                 lambda: outsider.put(kpi_url(v, "K0", "/governance"), json={"may_see": ["Sam"]}),
                 lambda: outsider.delete(kpi_url(v, "K0"))):
        assert call().status_code == 403
    assert named.put(kpi_url(v, "K0", "/owners"), json={"data": {"name": "Zed"}}).status_code == 200


def test_a_personal_or_not_sure_measure_is_for_the_admin_alone_until_people_are_named(world):
    """P2: not sure counts as personal, and with nobody named only the company admin sees what is in it."""
    admin = login(world, "co-a", "Pat Owner", ("company_admin",))
    v = confirm(admin, start(admin, seed_charter(world)), suggestion_id="K0", problem_ids=["p1"])
    other = login(world, "co-a", "Sam Outsider", ("analyst",))
    url = f"{BASE}/baselines/{v['baseline']['id']}"
    assert other.get(url).json()["kpis"][0]["restricted"] is True and admin.get(url).json()["kpis"][0]["restricted"] is False
    admin.put(kpi_url(v, "K0", "/governance"), json={"personal": "no"})  # a decision: not personal, not sensitive
    assert other.get(url).json()["kpis"][0]["restricted"] is False


def test_counts_never_include_a_measure_the_asker_cannot_see(world):
    """P4"""
    admin = login(world, "co-a", "Pat Owner", ("company_admin",))
    v = confirm(admin, start(admin, seed_charter(world)), suggestion_id="K0", problem_ids=["p1"])
    other = login(world, "co-a", "Sam Outsider", ("analyst",))
    url = f"{BASE}/baselines/{v['baseline']['id']}"
    for who, n in ((admin, 1), (other, 0)):
        seen = who.get(url).json()
        assert next(p for p in seen["problems"] if p["id"] == "p1")["kpi_ids"] == (["K0"] if n else [])
        assert who.get(f"{BASE}/baselines").json()["baselines"][0]["kpi_count"] == n


def test_only_the_admin_or_sponsor_changes_who_may_see(world):
    """P3: a named analyst can work on the measure but cannot widen or narrow the list."""
    admin = login(world, "co-a", "Pat Owner", ("company_admin",))
    v = confirm(admin, start(admin, seed_charter(world)), suggestion_id="K0")
    admin.put(kpi_url(v, "K0", "/governance"), json={"personal": "yes", "may_see": ["Test Wei Lim"]})
    named = login(world, "co-a", "Wei Lim", ("analyst",))
    r = named.put(kpi_url(v, "K0", "/governance"), json={"may_see": ["Test Wei Lim", "Test Sam Outsider"]})
    assert r.status_code == 403 and "company admin or the sponsor" in r.json()["message"]
    assert named.put(kpi_url(v, "K0", "/governance"), json={"sensitive": True}).status_code == 200  # other details stay open to them
    sponsor = login(world, "co-a", "Sue Sponsor", ("sponsor",))  # a sponsor is named like anyone, then may change the list
    admin.put(kpi_url(v, "K0", "/governance"), json={"may_see": ["Test Wei Lim", "Test Sue Sponsor"]})
    assert sponsor.put(kpi_url(v, "K0", "/governance"), json={"may_see": ["Test Wei Lim", "Test Sue Sponsor"]}).status_code == 200


def test_access_follows_the_account_not_a_name_taken_later(world):
    """P5: Wei has an account when named; another account renamed to "Test Wei Lim" is not let in."""
    admin = login(world, "co-a", "Pat Owner", ("company_admin",))
    v = confirm(admin, start(admin, seed_charter(world)), suggestion_id="K0")
    wei = login(world, "co-a", "Wei Lim", ("analyst",))
    admin.put(kpi_url(v, "K0", "/governance"), json={"personal": "yes", "may_see": ["Test Wei Lim", "No Account Yet"]})
    url = f"{BASE}/baselines/{v['baseline']['id']}"
    assert "may_see_accounts" not in admin.get(url).text  # account ids stay on the server
    sam = login(world, "co-a", "Sam Outsider", ("analyst",))
    sam_email = next(a["email"] for a in world.accounts._read() if a["display_name"] == "Test Sam Outsider")
    world.accounts.set_display_name(sam_email, "Test Wei Lim")
    assert wei.get(url).json()["kpis"][0]["restricted"] is False
    assert sam.get(url).json()["kpis"][0]["restricted"] is True
    late = login(world, "co-a", "No Account Yet", ("analyst",))  # no account when named: matched on the name
    world.accounts.set_display_name(next(a["email"] for a in world.accounts._read() if a["display_name"] == "Test No Account Yet"), "No Account Yet")
    assert late.get(url).json()["kpis"][0]["restricted"] is False


def test_only_the_nominee_or_the_organiser_declines(world):
    """P6"""
    admin = login(world, "co-a", "Pat Owner", ("company_admin",))
    v = confirm(admin, start(admin, seed_charter(world)), suggestion_id="K0")
    admin.put(kpi_url(v, "K0", "/governance"), json={"personal": "no"})  # visible to the team
    admin.put(kpi_url(v, "K0", "/owners"), json={"data": {"name": "Test Wei Lim", "has_account": True}, "process": {"name": "Test Wei Lim"}})
    sam, wei = login(world, "co-a", "Sam Outsider", ("analyst",)), login(world, "co-a", "Wei Lim", ("analyst",))
    admin.put(kpi_url(v, "K0", "/owners"), json={"data": {"name": "Test Wei Lim", "has_account": True}})  # now Wei has an account
    own = kpi_of(admin.get(f"{BASE}/baselines/{v['baseline']['id']}").json(), "K0")["owners"]
    assert len(own["data"]["account_id"]) == 32 and own["process"]["account_id"] is None  # kept for the sign-off to check
    r = sam.post(kpi_url(v, "K0", "/owners/data/decline"))
    assert r.status_code == 403 and "nominated" in r.json()["message"]
    assert wei.post(kpi_url(v, "K0", "/owners/data/decline")).status_code == 200
    assert admin.post(kpi_url(v, "K0", "/owners/process/decline")).status_code == 200  # the organiser may for them


# ---- signed content is read-only; security

def test_a_signed_baseline_refuses_every_change(world):
    c = login(world, "co-a")
    v = confirm(c, start(c, seed_charter(world)), suggestion_id="K0")
    path = world.plane("co-a").path("intents", "m2_baseline", v["baseline"]["id"], "baseline.json")
    path.write_text(json.dumps({**v["baseline"], "state": "signed"}))
    for call in (lambda: c.post(f"{BASE}/baselines/{v['baseline']['id']}/kpis", json={"name": "New"}),
                 lambda: c.delete(kpi_url(v, "K0")),
                 lambda: c.put(kpi_url(v, "K0", "/owners"), json={"data": {"name": "Zed"}}),
                 lambda: c.put(kpi_url(v, "K0", "/governance"), json={"personal": "no"}),
                 lambda: c.put(kpi_url(v, "K0", "/triage"), json={"producer": {"text": "x", "mark": "stated"}})):
        r = call()
        assert r.status_code == 409 and r.json()["error"] == "signed"


def test_another_companys_baseline_is_unreachable_and_roles_are_checked(world):
    a, b = login(world, "co-a"), login(world, "co-b", "Bea Other")
    v = start(a, seed_charter(world))
    assert b.get(f"{BASE}/baselines/{v['baseline']['id']}").status_code == 404
    assert b.get(f"{BASE}/baselines").json()["baselines"] == []
    assert b.post(f"{BASE}/baselines", json={"charter_outcome_id": v["baseline"]["charter_outcome_id"]}).status_code == 404
    assert login(world, "co-a", "Pia Participant", ("participant",)).get(f"{BASE}/baselines").status_code == 403
    assert login(world, "co-off", "Olly Off").get(f"{BASE}/baselines").status_code in (403, 404)


def test_the_files_have_the_shared_shape_and_the_read_functions_return_them(world):
    c = login(world, "co-a")
    v = confirm(c, start(c, seed_charter(world)), suggestion_id="K0", problem_ids=["p1"])
    plane, bid = world.plane("co-a"), v["baseline"]["id"]
    assert set(read_baseline(plane, bid)) == {"id", "charter_outcome_id", "state", "created_at"}
    (k,) = read_kpis(plane, bid)
    assert {"id", "name", "problem_ids", "priority", "definition", "owners", "governance", "tracking"} <= set(k)
    assert set(k["owners"]) == {"business", "data", "process"} and set(k["governance"]) == {"personal", "sensitive", "may_see"}
    for p in (k["definition"], k["tracking"], *k["owners"].values()):
        assert set(p) == {"value", "mark", "by", "from", "at"}
    assert read_baseline(plane, "nope") is None and read_kpis(plane, "nope") == [] and read_kpis(plane, "a" * 32) == []


def test_a_damaged_file_is_refused_not_overwritten(world):
    c = login(world, "co-a")
    v = confirm(c, start(c, seed_charter(world)), suggestion_id="K0")
    f = world.plane("co-a").path("intents", "m2_baseline", v["baseline"]["id"], "kpis.json")
    f.write_text("{not json")
    r = c.post(f"{BASE}/baselines/{v['baseline']['id']}/kpis", json={"name": "New"})
    assert r.status_code == 500 and "nothing was changed" in r.json()["message"] and f.read_text() == "{not json"


# ---- identity: pick an owner from the company's accounts, or type a free name

def test_owners_can_be_picked_from_the_companys_accounts_and_a_free_name_still_works(world):
    c = login(world, "co-a")
    login(world, "co-a", "Mei Tan", ("owner",))  # the account exists
    login(world, "co-b", "Sam Stranger", ("owner",))  # another company's account
    v = confirm(c, start(c, seed_charter(world)), suggestion_id="K0")
    people = {p["display_name"]: p["account_id"] for p in v["people"]}
    assert "Test Mei Tan" in people and "Test Sam Stranger" not in people
    assert all(set(p) == {"account_id", "display_name"} for p in v["people"])
    v = c.put(kpi_url(v, "K0", "/owners"), json={"business": {"account_id": people["Test Mei Tan"]},
                                                 "data": {"name": "Arjun Rao"}}).json()
    k = kpi_of(v, "K0")
    assert k["owners"]["business"]["value"] == "Test Mei Tan" and k["owners"]["business"]["account_id"] == people["Test Mei Tan"]
    assert "with an account" in k["owners"]["business"]["from"]
    assert k["owners"]["data"]["value"] == "Arjun Rao" and k["owners"]["data"]["account_id"] is None  # no account: a free name
    bad = c.put(kpi_url(v, "K0", "/owners"), json={"process": {"account_id": "not-an-account"}})
    assert bad.status_code == 400
    other = next(a["account_id"] for a in world.accounts.in_company("co-b"))
    assert c.put(kpi_url(v, "K0", "/owners"), json={"process": {"account_id": other}}).status_code == 400  # another company's account


# ---- suggestions for a charter problem with no library problem: matched by shared words, labelled, and linked on confirm

def test_a_custom_problem_is_matched_to_the_pack_problem_it_shares_words_with_and_confirming_links_it(world):
    folder = world.packs / "industry_a" / "1"
    (folder / "problems.yaml").write_text(yaml.safe_dump({"problems": [
        {"id": "lib1", "question": "Late calls?", "kpi_ids": ["K0"]},
        {"id": "lib2", "question": "Can we pay people on numbers we trust?", "decision": "performance figures behind bonuses", "kpi_ids": ["K1"]}]}))
    c = login(world, "co-a")
    custom = {"id": "p3", "title": "Bonuses and trusted numbers", "priority": "must", "so_that": None, "note_count": 2, "library_problem_id": None}
    v = start(c, seed_charter(world, problems=[custom]))
    assert [(s["id"], s["problem_ids"]) for s in v["suggestions"]] == [("K1", ["p3"])] and "suggestion" in v["suggestion_label"].lower()
    v = confirm(c, v, suggestion_id="K1")  # no problem_ids sent: the suggestion's own problem is linked
    assert kpi_of(v, "K1")["problem_ids"] == ["p3"] and next(p for p in v["problems"] if p["id"] == "p3")["has_kpi"] is True


def test_a_problem_that_shares_fewer_than_two_words_with_any_pack_problem_gets_no_suggestion(world):
    c = login(world, "co-a")
    odd = {"id": "p3", "title": "Parking", "priority": "could", "so_that": None, "note_count": 1, "library_problem_id": None}
    assert start(c, seed_charter(world, problems=[odd]))["suggestions"] == []


def test_the_family_office_pack_suggests_the_benchmark_and_pay_measures_for_the_story_problems():
    import pathlib

    from modules.m2_baseline.agent import pack_text as P
    pack = pathlib.Path(__file__).resolve().parents[3] / "packs" / "family_office" / "1"
    g = P.Guidance(None, [k for k in yaml.safe_load((pack / "kpi_tree.yaml").read_text(encoding="utf-8"))["kpis"]],
                   problems=yaml.safe_load((pack / "problems.yaml").read_text(encoding="utf-8"))["problems"])
    ids = lambda title: [k["id"] for k in P.kpis_for_problem(g, {"title": title, "library_problem_id": None})]  # noqa: E731
    assert ids("Managers ahead or behind benchmarks") == ["K15", "K16", "K17"]
    assert ids("Bonuses and trusted numbers") == ["K16", "K18"]
    assert ids("Performance and pay") and set(ids("Performance and pay")) <= {"K15", "K16", "K17", "K18", "K19"}
