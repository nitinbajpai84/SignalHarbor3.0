"""IC-3c: the governed state (A-054). Six provenance cells per measure, a draft from the stored sources (no model), a guess never over a
stated value, confirmation only by the person named, restricted filtering, the complete rule and the four percentages."""
import json
from datetime import date

import pytest
from m2_kit import BASE, login
from test_m2_governance import BID, LENA, PAT, SAM, kpis, seed

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import governed as G
from modules.m2_baseline.store import governed as S
from sh_platform.profile import store as profile_store

ADMIN = C.Viewer(PAT, frozenset({"company_admin"}))
SPONSOR = C.Viewer(SAM, frozenset({"sponsor"}))
LENA_V = C.Viewer(LENA, frozenset({"analyst"}))
APPROVER = C.Viewer("Test Ava Approver", frozenset({"approver"}))
OWNER = C.Viewer("Test Olga Owner", frozenset({"owner"}), account_id="acct-olga")
STRANGER = C.Viewer("Test Stan Stranger", frozenset({"analyst"}))
HEAD = C.Viewer("Test Hal Head", frozenset({"analyst"}))
TODAY = date(2026, 10, 6)


def own(name, account=None):
    return {"value": name, "mark": "stated", "by": PAT, "from": "nominated", "at": "2026-10-03T10:00:00+00:00", **({"account_id": account} if account else {})}


def rows():
    r = kpis()
    r[0]["owners"] = {"business": own("Test Olga Owner", "acct-olga"), "data": own("Test Dan Data"), "process": {"value": None, "mark": "unknown"}}
    return r


def profile(plane, path, value, mark="stated"):
    profile_store.record(plane, path, value, {"mark": mark, "by": "Test Pat Owner", "from": "a test file"})


def test_blank_has_six_cells_with_provenance(world):
    plane = seed(world, kpi_rows=rows())
    got = S.governed_for(plane, BID, ADMIN)["measures"][0]["state"]
    assert tuple(got) == G.FIELDS
    for c in got.values():
        assert c["mark"] == "unknown" and c["value"] is None and c["by"] and c["from"] and c["at"]


def test_draft_from_each_named_source(world):
    plane = seed(world, kpi_rows=rows())
    profile(plane, "people.olga.name", "Test Olga Owner")
    profile(plane, "people.olga.team", "Treasury")
    profile(plane, "constraints.deadline-1.kind", "deadline")
    profile(plane, "constraints.deadline-1.text", "Capital calls due is needed by week 12")
    profile(plane, "constraints.deadline-2.kind", "deadline")
    profile(plane, "constraints.deadline-2.text", "Treasury must close by week 8")
    profile(plane, "constraints.deadline-3.kind", "deadline")
    profile(plane, "constraints.deadline-3.text", "Unrelated team by week 2")
    profile(plane, "governance.field_rules.salary.field", "salary")
    profile(plane, "governance.field_rules.salary.sensitive", True)
    profile(plane, "governance.field_rules.salary.may_see", [LENA])
    profile(plane, "governance.restricted_areas.exposure.area", "Exposure")
    profile(plane, "governance.restricted_areas.exposure.may_see", ["Test Zed"])
    pack = [{"id": "P1", "name": "Capital calls due", "drives": [{"kpi": "P2"}]}, {"id": "P2", "name": "Funding headroom", "drives": []}]
    assert S.draft_all(plane, BID, ADMIN, pack, TODAY) == 3
    s = {m["id"]: m["state"] for m in S.governed_for(plane, BID, ADMIN)["measures"]}
    k1, k2, k3 = s["K01"], s["K02"], s["K03"]
    assert k1["owners"]["value"] == {"business": "Test Olga Owner", "data": "Test Dan Data", "process": None} and k1["owners"]["mark"] == "guessed"
    assert (k1["classification"]["value"], k1["may_see"]["value"]) == ("open", [])  # existing governance
    assert (k2["classification"]["value"], k2["may_see"]["value"]) == ("sensitive", [LENA])  # Pay review: its own answers and the salary rule
    assert (k3["classification"]["value"], k3["may_see"]["value"]) == ("restricted", ["Test Zed"])  # the restricted area "Exposure"
    assert k1["resolving"]["value"] == {"team": "Treasury", "target_week": 8} and k2["resolving"]["mark"] == "unknown"
    assert k1["affects"]["value"] == ["Funding headroom"] and k2["affects"]["mark"] == "unknown"
    assert (k1["review_date"]["value"], k1["review_date"]["mark"], k1["review_date"]["from"]) == ("2027-01-05", "guessed", "default")
    assert all(c["mark"] != "stated" for st in s.values() for c in st.values())


def test_no_deadline_names_it_means_null_week(world):
    plane = seed(world, kpi_rows=rows())
    profile(plane, "people.olga.name", "Test Olga Owner")
    profile(plane, "people.olga.team", "Treasury")
    S.draft_all(plane, BID, ADMIN, [], TODAY)
    assert S.governed_for(plane, BID, ADMIN)["measures"][0]["state"]["resolving"]["value"] == {"team": "Treasury", "target_week": None}


def test_guess_never_replaces_stated(world):
    plane = seed(world, kpi_rows=rows())
    S.confirm_field(plane, BID, "K01", "classification", "personal", APPROVER)
    S.draft_governed(plane, BID, "K01", {"classification": ("open", "the measure")})
    cell = S.governed_for(plane, BID, ADMIN)["measures"][0]["state"]["classification"]
    assert (cell["value"], cell["mark"], cell["by"]) == ("personal", "stated", APPROVER.name)
    S.confirm_field(plane, BID, "K01", "classification", "sensitive", APPROVER)  # a person may restate
    assert S._read(plane, BID)["K01"]["classification"]["value"] == "sensitive"


@pytest.mark.parametrize("field,value,who", [
    ("owners", {"business": "Test Olga Owner"}, OWNER), ("classification", "open", APPROVER), ("may_see", [], APPROVER),
    ("resolving", {"team": "Treasury", "target_week": 9}, SPONSOR), ("affects", ["A"], OWNER), ("review_date", "2027-01-01", SPONSOR)])
def test_the_right_person_confirms(world, field, value, who):
    plane = seed(world, kpi_rows=rows())
    entry = S.confirm_field(plane, BID, "K01", field, value, who)
    assert entry[field]["mark"] == "stated" and entry[field]["by"] == who.name


def test_head_of_data_from_the_profile_may_confirm_owners_and_classification(world):
    plane = seed(world, kpi_rows=rows())
    profile(plane, "people.hal.name", "Test Hal Head")
    profile(plane, "people.hal.is_head_of_data", True)
    S.confirm_field(plane, BID, "K01", "owners", {"business": "Test Hal Head"}, HEAD)
    S.confirm_field(plane, BID, "K01", "classification", "open", HEAD)


@pytest.mark.parametrize("field,value,who", [
    ("owners", {}, STRANGER), ("owners", {}, ADMIN), ("classification", "open", OWNER), ("classification", "open", ADMIN),
    ("may_see", [], SPONSOR), ("resolving", {"team": "T"}, ADMIN), ("resolving", {"team": "T"}, OWNER), ("affects", [], SPONSOR),
    ("affects", [], ADMIN), ("review_date", "2027-01-01", STRANGER)])
def test_everyone_else_is_refused_in_one_sentence(world, field, value, who):
    plane = seed(world, kpi_rows=rows())
    with pytest.raises(C.CatalogueError) as e:
        S.confirm_field(plane, BID, "K01", field, value, who)
    assert e.value.code == "forbidden" and e.value.message == G.REFUSED
    assert S._read(plane, BID) == {}


def test_a_named_owner_who_is_also_admin_may_confirm_only_as_the_owner(world):
    plane = seed(world, kpi_rows=rows())
    both = C.Viewer("Test Olga Owner", frozenset({"company_admin"}), account_id="acct-olga")
    S.confirm_field(plane, BID, "K01", "affects", [], both)
    with pytest.raises(C.CatalogueError):
        S.confirm_field(plane, BID, "K01", "classification", "open", both)


def test_bad_values_are_refused(world):
    plane = seed(world, kpi_rows=rows())
    for field, value, who in (("classification", "secret", APPROVER), ("review_date", "soon", SPONSOR),
                              ("resolving", {"team": "T", "target_week": 0}, SPONSOR), ("may_see", "Pat", APPROVER)):
        with pytest.raises(C.CatalogueError) as e:
            S.confirm_field(plane, BID, "K01", field, value, who)
        assert e.value.code == "invalid"


def test_complete_needs_all_six_stated_and_percentages(world):
    plane = seed(world, kpi_rows=rows())
    S.draft_all(plane, BID, ADMIN, [], TODAY)
    assert not any(m["complete"] for m in S.governed_for(plane, BID, ADMIN)["measures"])  # all guessed
    S.confirm_field(plane, BID, "K01", "owners", {"business": "Test Olga Owner"}, OWNER)
    S.confirm_field(plane, BID, "K01", "classification", "personal", APPROVER)
    S.confirm_field(plane, BID, "K01", "may_see", [LENA], APPROVER)
    S.confirm_field(plane, BID, "K01", "resolving", {"team": "Treasury", "target_week": 8}, SPONSOR)
    S.confirm_field(plane, BID, "K01", "affects", [], OWNER)
    got = S.governed_for(plane, BID, ADMIN)
    assert not got["measures"][0]["complete"] and got["percentages"] == {"owned": 33, "classified": 33, "may_see_confirmed": 33, "sealed": 33}
    S.confirm_field(plane, BID, "K01", "review_date", "2027-01-05", OWNER)
    got = S.governed_for(plane, BID, ADMIN)
    assert got["measures"][0]["complete"] and [m["complete"] for m in got["measures"][1:]] == [False, False]


def test_restricted_state_only_to_its_list(world):
    plane = seed(world, kpi_rows=rows())
    S.draft_all(plane, BID, ADMIN, [], TODAY)
    assert [m["id"] for m in S.governed_for(plane, BID, LENA_V)["measures"]] == ["K01", "K02"]  # K02 lists Lena; K03 (not sure) lists nobody
    assert [m["id"] for m in S.governed_for(plane, BID, STRANGER)["measures"]] == ["K01"]
    assert "Pay review" not in json.dumps(S.governed_for(plane, BID, STRANGER))
    assert S.draft_all(plane, BID, STRANGER, [], TODAY) == 1  # a person drafts only what they may see
    with pytest.raises(C.CatalogueError) as e:
        S.confirm_field(plane, BID, "K02", "classification", "open", APPROVER)
    assert e.value.code == "not_found"


def test_empty_company_and_one_person_alone(world):
    plane = seed(world, company="co-solo", kpi_rows=[])
    got = S.governed_for(plane, BID, ADMIN)
    assert got == {"measures": [], "percentages": {"owned": 0, "classified": 0, "may_see_confirmed": 0, "sealed": 0}}
    assert S.draft_all(plane, BID, ADMIN, [], TODAY) == 0
    alone = seed(world, company="co-solo", kpi_rows=rows())
    S.draft_all(alone, BID, ADMIN, [], TODAY)
    assert len(S.governed_for(alone, BID, ADMIN)["measures"]) == 3


def test_two_industries_and_no_pack_use_their_own_tree(world):
    for company, industry in (("co-a", "industry_a"), ("co-b", "industry_b"), ("co-none", "none")):
        plane = seed(world, company=company, kpi_rows=rows())
        try:
            tree = world.app.state.packs.load(industry).section("kpi_tree")["kpis"]
        except KeyError:
            tree = []
        tree = [{**t, "name": "Capital calls due", "drives": [{"kpi": tree[-1]["id"]}]} if i == 0 else t for i, t in enumerate(tree)]
        S.draft_all(plane, BID, ADMIN, tree, TODAY)
        affects = S.governed_for(plane, BID, ADMIN)["measures"][0]["state"]["affects"]
        assert (affects["mark"], affects["value"]) == (("guessed", [f"{industry} measure {len(tree) - 1}"]) if tree else ("unknown", None))


def test_routes_read_confirm_refuse_and_isolate(world):
    seed(world, kpi_rows=rows())
    admin, spons = login(world, "co-a", PAT, ("company_admin",)), login(world, "co-a", SAM, ("sponsor",))
    url = f"{BASE}/baselines/{BID}/governed"
    assert admin.get(url).json()["measures"][0]["id"] == "K01"
    r = spons.post(f"{url}/K01/confirm", json={"field": "resolving", "value": {"team": "Treasury", "target_week": 6}})
    assert r.status_code == 200 and r.json()["state"]["resolving"]["mark"] == "stated" and r.json()["complete"] is False
    r = admin.post(f"{url}/K01/confirm", json={"field": "classification", "value": "open"})
    assert r.status_code == 403 and r.json()["message"] == G.REFUSED
    assert admin.post(f"{url}/K01/confirm", json={"value": 1}).status_code == 422
    assert login(world, "co-b", "Test Other", ("company_admin",)).get(url).status_code == 404  # another company has no such baseline
    assert login(world, "co-off", "Test Off", ("company_admin",)).get(url).status_code in (403, 404)


def test_first_read_drafts_lazily_and_serves_governed_and_missing(world):
    plane = seed(world, kpi_rows=rows())
    admin = login(world, "co-a", PAT, ("company_admin",))
    url = f"{BASE}/baselines/{BID}/governed"
    assert not S.exists(plane, BID)
    first = admin.get(url).json()
    assert S.exists(plane, BID)
    k1 = first["measures"][0]
    assert k1["state"]["owners"]["mark"] == "guessed" and k1["governed"] is False and k1["missing"] == list(G.FIELDS)
    S.confirm_field(plane, BID, "K01", "classification", "personal", APPROVER)
    again = admin.get(url).json()["measures"][0]  # a second read drafts nothing over the stated cell
    assert again["state"]["classification"]["value"] == "personal" and "classification" not in again["missing"]


def test_the_lens_draft_route_also_drafts_the_governed_state(world):
    from modules.m2_baseline.domain import worklist as W
    full = [{**W.new_kpi(k["id"], k["name"], [], k["priority"]), "governance": k["governance"], "owners": k.get("owners", W.new_kpi(k["id"], "x", [], "must")["owners"])} for k in rows()]
    plane = seed(world, kpi_rows=full)
    admin = login(world, "co-a", PAT, ("company_admin",))
    S.confirm_field(plane, BID, "K01", "classification", "personal", APPROVER)
    r = admin.post(f"{BASE}/baselines/{BID}/lens/draft", json={})
    assert r.status_code == 200, r.text
    state = S._read(plane, BID)
    assert set(state) == {"K01", "K02", "K03"} and state["K01"]["classification"]["mark"] == "stated"
    assert state["K02"]["classification"]["mark"] == "guessed"


@pytest.mark.parametrize("field,value,who", [("owners", {}, OWNER), ("owners", {"data": "Test Dan Data"}, OWNER), ("resolving", {}, SPONSOR),
                                              ("resolving", {"target_week": 5}, SPONSOR)])
def test_an_empty_owners_or_resolving_is_not_a_confirmation(world, field, value, who):
    plane = seed(world, kpi_rows=rows())
    with pytest.raises(C.CatalogueError) as e:
        S.confirm_field(plane, BID, "K01", field, value, who)
    assert e.value.code == "invalid" and e.value.message.startswith("Please name")
    assert S._read(plane, BID) == {}


def test_an_unreadable_baseline_does_not_break_the_lens_draft(world, caplog):
    plane = seed(world, kpi_rows=rows())
    (plane.path("intents", "m2_baseline", BID) / "catalogue.json").write_text("{not json")
    admin = login(world, "co-a", PAT, ("company_admin",))
    with caplog.at_level("WARNING"):
        r = admin.get(f"{BASE}/baselines/{BID}/governed")
    assert r.status_code == 200
    assert any(BID in m and "skipped" in m for m in caplog.messages)
