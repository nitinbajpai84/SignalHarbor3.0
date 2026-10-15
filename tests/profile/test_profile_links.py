"""LI-LINK: a profile person is linked to one enabled account of the same company, by the admin or by an exact email match."""
import base64

from pf_kit import FAMILY, OTHER, PEOPLE
from sh_platform.profile import reader, store, view
from sh_platform.profile.view import Viewer

ADMIN = Viewer("Mei Tan", frozenset({"company_admin"}))
SUE = Viewer("Sue Sponsor", frozenset({"sponsor"}))


def put(c, gid, name, data):
    return c.post(f"/api/profile/inputs/{gid}/upload", json={"filename": name, "data": base64.b64encode(data).decode()})


def link(c, pid, account_id):
    return c.put(f"/api/profile/people/{pid}/account", json={"account_id": account_id})


def make(env, email, name, company=FAMILY, roles=("participant",), disabled=False):
    return env.app.state.account_store.create(email, "FAKE-pw-1234", name, company, list(roles), disabled=disabled)["account_id"]


def setup_people(env):
    admin = env.login("company_admin")
    assert put(admin, 1, "people.csv", PEOPLE).status_code == 200
    return admin


def cellof(env, pid, company=FAMILY):
    from sh_platform.plane import PlaneStore
    plane = PlaneStore(env.app.state.settings.data_root).plane_for(company)
    return store.load(plane)["people"].get(pid, {}).get("account_id")


# ---- the admin's link ---------------------------------------------------------------------------------------------------

def test_admin_links_and_unlinks_with_a_persons_provenance(env):
    admin = setup_people(env)
    acc = make(env, "dan.d@example.test", "Dan D")
    r = link(admin, "dan-data", acc)
    assert r.status_code == 200
    c = cellof(env, "dan-data")
    assert c["value"] == acc and c["mark"] == "stated" and not c.get("agent") and c["from"].startswith("Linked by ")
    assert c["by"] and c["by"] in c["from"]
    r = link(admin, "dan-data", None)
    assert r.status_code == 200
    assert cellof(env, "dan-data")["value"] is None
    assert [p["account_id"] for p in admin.get("/api/profile/links").json()["people"] if p["id"] == "dan-data"] == [None]


def test_an_account_of_another_company_unknown_or_disabled_is_refused(env):
    admin = setup_people(env)
    foreign = make(env, "x@example.test", "Foreign Person", company=OTHER)
    off = make(env, "off@example.test", "Gone Person", disabled=True)
    for bad, word in ((foreign, "not available"), ("no-such-id", "not available"), (off, "switched off")):
        r = link(admin, "dan-data", bad)
        assert r.status_code == 422 and word in r.json()["message"], bad
        assert "account_id" not in r.json()["message"]
    assert cellof(env, "dan-data") is None


def test_one_account_one_person_and_unknown_person(env):
    admin = setup_people(env)
    acc = make(env, "shared@example.test", "Shared Seat")
    assert link(admin, "dan-data", acc).status_code == 200
    r = link(admin, "mei-tan", acc)
    assert r.status_code == 409 and "Dan Data" in r.json()["message"]
    assert cellof(env, "mei-tan") is None
    assert link(admin, "dan-data", acc).status_code == 200  # the same pair again is fine
    assert link(admin, "nobody-here", acc).status_code == 404


def test_the_body_must_name_an_account_or_null(env):
    admin = setup_people(env)
    assert admin.put("/api/profile/people/dan-data/account", json={}).status_code == 400
    assert admin.put("/api/profile/people/dan-data/account", json={"account_id": 5}).status_code == 400


def test_route_roles(env):
    setup_people(env)
    for role in ("sponsor", "analyst", "participant", "approver", "owner"):
        c = env.login(role)
        assert link(c, "dan-data", None).status_code == 403
        assert c.get("/api/profile/links").status_code == 403
    from fastapi.testclient import TestClient
    anon = TestClient(env.app)
    assert anon.put("/api/profile/people/dan-data/account", json={"account_id": None}).status_code == 401
    assert anon.get("/api/profile/links").status_code == 401


def test_other_company_admin_cannot_reach_this_profile(env):
    setup_people(env)
    b = env.login("company_admin", OTHER)
    assert link(b, "dan-data", None).status_code == 404
    assert b.get("/api/profile/links").json()["people"] == []


def test_the_picker_lists_only_this_companys_enabled_accounts_by_name(env):
    admin = setup_people(env)
    make(env, "ok@example.test", "Olive Okafor")
    make(env, "off@example.test", "Gone Person", disabled=True)
    make(env, "far@example.test", "Faraway Person", company=OTHER)
    out = admin.get("/api/profile/links").json()
    names = {a["display_name"] for a in out["accounts"]}
    assert "Olive Okafor" in names and "Gone Person" not in names and "Faraway Person" not in names
    assert all(set(a) == {"account_id", "display_name"} for a in out["accounts"])


# ---- visibility ---------------------------------------------------------------------------------------------------------

def test_only_the_admin_sees_the_link_in_the_profile(env):
    admin = setup_people(env)
    link(admin, "dan-data", make(env, "dan.d@example.test", "Dan D"))
    assert admin.get("/api/profile").json()["people"]["dan-data"]["account_id"]["value"]
    for role in ("sponsor", "analyst"):
        assert "account_id" not in env.login(role).get("/api/profile").json()["people"]["dan-data"]


# ---- the automatic match by email: a suggestion only, never a link -----------------------------------------------------------

def sugg(env, pid, company=FAMILY):
    from sh_platform.plane import PlaneStore
    plane = PlaneStore(env.app.state.settings.data_root).plane_for(company)
    return store.load(plane)["people"].get(pid, {}).get("account_suggestion")


def test_a_matching_email_is_a_suggestion_not_a_link(env):
    admin = env.login("company_admin")
    acc = make(env, "Dan@Example.test", "Dan D")
    assert put(admin, 1, "people.csv", PEOPLE).status_code == 200
    assert cellof(env, "dan-data") is None
    c = sugg(env, "dan-data")
    assert c["value"] == acc and c["mark"] == "guessed" and c["agent"] == "lens" and c["from"] == "Matched by email"
    assert c["ref"]["kind"] == "document" and c["ref"]["id"]
    assert sugg(env, "mei-tan") is None
    row = [p for p in admin.get("/api/profile/links").json()["people"] if p["id"] == "dan-data"][0]
    assert row["account_id"] is None and row["suggestion"]["account_id"] == acc and row["suggestion"]["file"] == "people.csv"


def test_a_non_admin_upload_never_makes_a_link_or_a_suggestion(env):
    """The reviewer's probe: an analyst's list carries the analyst's own email against another person."""
    me = make(env, "analyst.me@example.test", "Alma Analyst")
    for role in ("analyst", "sponsor"):
        c = env.login(role)
        data = b"Name,Role,Team,Email\nDan Data,Head of data,Data,analyst.me@example.test\nDecoy,Clerk,Ops,analyst.me@example.test\n"
        assert put(c, 1, "people.csv", data).status_code == 200
        assert cellof(env, "dan-data") is None and sugg(env, "dan-data") is None
        assert cellof(env, "decoy") is None and sugg(env, "decoy") is None
        assert c.post("/api/profile/read").status_code == 200
        assert cellof(env, "dan-data") is None and sugg(env, "dan-data") is None
    assert me


def test_decoy_row_cannot_take_the_account_from_the_real_person(env):
    admin = env.login("company_admin")
    acc = make(env, "dan@example.test", "Dan D")
    analyst = env.login("analyst")
    put(analyst, 1, "people.csv", b"Name,Role,Team,Email\nDecoy,Clerk,Ops,dan@example.test\n")
    assert cellof(env, "decoy") is None and sugg(env, "decoy") is None
    put(admin, 1, "people.csv", PEOPLE)
    assert link(admin, "dan-data", acc).status_code == 200


def test_only_the_admin_sees_the_suggestion(env):
    admin = env.login("company_admin")
    make(env, "dan@example.test", "Dan D")
    put(admin, 1, "people.csv", PEOPLE)
    assert admin.get("/api/profile").json()["people"]["dan-data"]["account_suggestion"]["value"]
    for role in ("sponsor", "analyst"):
        assert "account_suggestion" not in env.login(role).get("/api/profile").json()["people"]["dan-data"]


def test_confirm_turns_the_suggestion_into_a_stated_link(env):
    admin = env.login("company_admin")
    acc = make(env, "dan@example.test", "Dan D")
    put(admin, 1, "people.csv", PEOPLE)
    assert link(admin, "dan-data", acc).status_code == 200
    c = cellof(env, "dan-data")
    assert c["value"] == acc and c["mark"] == "stated" and not c.get("agent") and c["from"].startswith("Linked by ")
    assert sugg(env, "dan-data") is None
    row = [p for p in admin.get("/api/profile/links").json()["people"] if p["id"] == "dan-data"][0]
    assert row["account_id"] == acc and row["suggestion"] is None


def test_an_agent_or_a_draft_can_never_write_account_id(env):
    admin = setup_people(env)
    from sh_platform.plane import PlaneStore
    plane = PlaneStore(env.app.state.settings.data_root).plane_for(FAMILY)
    for prov in ({"mark": "guessed", "by": "Lens", "from": "x", "agent": "lens"},
                 {"mark": "stated", "by": "Lens", "from": "x", "agent": "nira"},
                 {"mark": "guessed", "by": "Someone", "from": "x"},
                 {"mark": "unknown", "by": "Lens", "from": "x", "agent": "lens"}):
        assert store.record(plane, "people.dan-data.account_id", "a1", prov) is None
        assert cellof(env, "dan-data") is None
    doc = store.empty()
    assert store.set_cell(doc, "people.dan-data.account_id", "a1", {"mark": "guessed", "by": "Lens", "from": "x", "agent": "lens"}) is None
    assert "dan-data" not in doc["people"] or "account_id" not in doc["people"]["dan-data"]
    assert admin


def test_a_stored_agent_link_from_before_is_not_a_link(env):
    from sh_platform.plane import PlaneStore
    setup_people(env)
    plane = PlaneStore(env.app.state.settings.data_root).plane_for(FAMILY)
    def change(doc):
        doc["people"]["dan-data"]["account_id"] = {"value": "old", "mark": "guessed", "by": "Lens", "agent": "lens", "from": "Matched by email", "at": "t"}
    store.mutate(plane, change)
    assert [p["account_id"] for p in env.login("company_admin").get("/api/profile/links").json()["people"] if p["id"] == "dan-data"] == [None]


def test_the_match_ignores_case_and_spaces_and_skips_disabled_other_company_and_ambiguous(env):
    admin = env.login("company_admin")
    make(env, "mei@example.test", "Mei M", disabled=True)
    make(env, "sue@example.test", "Sue Elsewhere", company=OTHER)
    assert put(admin, 1, "people.csv", PEOPLE.replace(b"dan@example.test", b"  DAN@example.test ")).status_code == 200
    assert sugg(env, "mei-tan") is None and sugg(env, "sue-sponsor") is None
    acc = make(env, "dan@example.test", "Dan D")
    admin.post("/api/profile/read")
    assert sugg(env, "dan-data")["value"] == acc and cellof(env, "dan-data") is None


def test_two_accounts_with_one_email_never_suggest():
    doc = store.empty()
    store.set_cell(doc, "people.dan-data.email", "dan@example.test", {"mark": "stated", "by": "Lens", "from": "f", "agent": "lens"})
    from sh_platform.profile import links
    both = [{"account_id": "a1", "display_name": "A"}, {"account_id": "a2", "display_name": "B"}]
    links.auto_link(doc, lambda email: both)
    assert "account_suggestion" not in doc["people"]["dan-data"]
    links.auto_link(doc, lambda email: both[:1])
    assert doc["people"]["dan-data"]["account_suggestion"]["value"] == "a1"
    assert "account_id" not in doc["people"]["dan-data"]


def test_a_person_made_link_is_kept_and_so_is_a_person_made_unlink(env):
    admin = env.login("company_admin")
    mine = make(env, "chosen@example.test", "Chosen Seat")
    auto = make(env, "dan@example.test", "Dan D")
    put(admin, 1, "people.csv", PEOPLE)
    assert sugg(env, "dan-data")["value"] == auto
    assert link(admin, "dan-data", mine).status_code == 200
    admin.post("/api/profile/read")
    assert cellof(env, "dan-data")["value"] == mine and cellof(env, "dan-data")["mark"] == "stated" and sugg(env, "dan-data") is None
    assert link(admin, "dan-data", None).status_code == 200
    admin.post("/api/profile/read")
    assert cellof(env, "dan-data")["value"] is None and sugg(env, "dan-data") is None  # unlinked: not suggested again


def test_an_account_already_linked_to_someone_else_is_not_suggested(env):
    admin = setup_people(env)
    acc = make(env, "dan@example.test", "Dan D")
    assert link(admin, "mei-tan", acc).status_code == 200
    admin.post("/api/profile/read")
    assert sugg(env, "dan-data") is None and cellof(env, "mei-tan")["value"] == acc


def test_an_empty_company_and_a_second_industry_just_work(env):
    other = env.login("company_admin", OTHER)
    assert other.get("/api/profile/links").json()["people"] == []
    assert other.post("/api/profile/read").status_code == 200
    make(env, "dan@example.test", "Dan D", company=OTHER)
    assert put(other, 1, "people.csv", PEOPLE).status_code == 200
    assert sugg(env, "dan-data", OTHER)["value"] and cellof(env, "dan-data", OTHER) is None
    assert sugg(env, "dan-data") is None
