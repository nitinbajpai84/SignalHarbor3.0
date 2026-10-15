"""B03: areas, tags and the visibility matrix of file 05. The expected table is typed out here, apart from the code."""
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.intents import visibility as vis
from sh_platform.jsonfile import write_json_atomic
from sh_platform.packs import PackLoader
from sh_platform.plane import PlaneStore
from sh_platform.profile import areas, store
from sh_platform.profile.view import Viewer

COLS = ("existence", "title", "stage_clock", "people", "content", "sealed", "anonymous", "outcome", "closure", "ratings")
# persona -> the ten cells of file 05's table, in column order
EXPECTED = {
    "organiser":     ("Y", "Y", "Y", "all", "Y", "S", "A", "Y", "Y", "Y"),
    "sponsor":       ("Y", "Y", "Y", "all", "Y", "S", "A", "Y", "Y", "Y"),
    "participant":   ("Y", "Y", "Y", "all", "Y", "S", "A", "Y", "Y", "Y"),
    "observer":      ("Y", "Y", "Y", "all", "Y", "S", "A", "Y", "Y", "Y"),
    "affected_off":  ("Y", "Y", "Y", "all", "N", "N", "N", "closed", "came_next_closed", "N"),
    "same_area":     ("Y", "Y", "Y", "organiser", "N", "N", "N", "closed", "came_next_closed", "N"),
    "other_area":    None,
    "company_admin": ("Y", "Y", "Y", "organiser_counts", "N", "N", "N", "Y", "came_next", "count_avg3"),
    "super_admin":   ("Y", "unless_private", "state_dates_box", "count", "N", "N", "N", "N", "N", "N"),
    "share_visitor": ("Y", "Y", "Y", "speakers", "Y", "S", "A", "Y", "Y", "N"),
}
EXPECTED_AFFECTED_ON = ("Y", "Y", "Y", "all", "Y", "S", "A", "Y", "Y", "Y")


def person(acct, name):
    return {"account_id": acct, "name": name}


def viewers():
    v = lambda acct, name, *roles: Viewer(name, frozenset(roles), account_id=acct)
    return {
        "organiser": v("a-janet", "Janet Shaw"), "sponsor": v("a-daniel", "Daniel Kerr"), "participant": v("a-katie", "Katie"),
        "observer": v("a-obs", "Olive Observer"), "affected_off": v("a-harvey", "Harvey Rowley"), "same_area": v("a-fin", "Fiona Finance"),
        "other_area": v("a-grace", "Grace Ward"), "company_admin": v("a-admin", "Admin Person", "company_admin"),
        "super_admin": v("a-super", "Super", "super_admin"), "share_visitor": v("a-sally", "Sally Share"),
    }


def intent(**over):
    base = {"id": "i-1", "type": "brainstorm", "title": "Cash view", "purpose": "See cash early", "created_by": "a-janet", "areas": ["finance"],
            "state": "open", "affected_may_read": False,
            "people": {"organiser": person("a-janet", "Janet Shaw"), "sponsor": person("a-daniel", "Daniel Kerr"), "decider": None,
                       "owner": None, "reporter": None, "participants": [person("a-katie", "Katie")], "advisers": [],
                       "affected": [person("a-harvey", "Harvey Rowley")], "observers": [person("a-obs", "Olive Observer")]},
            "time_box": {"starts": "2026-10-01T00:00:00+00:00", "ends": "2099-01-01T00:00:00+00:00", "extended_by": []},
            "stages": [{"key": "wall", "state": "open", "opened_at": None, "closed_at": None}],
            "outcome": {"kind": "brainstorm", "statement": "x"},
            "closure": {"summary": "S", "why_it_happened": "W", "what_came_out": "Out", "next": [{"kind": "nothing", "ref": None, "reason": "r"}],
                        "cancel_reason": None},
            "ratings": [{"by": "a-katie", "score": 4, "note": "n"}], "rated_by": ["a-katie"], "refs": {"wall_session_ids": ["s1"]},
            "share": {"link": None, "who_may_open": [{"person_id": "p-sally", "label": "Sally", "token_hash": "h", "expires_at": "2099-01-01T00:00:00+00:00",
                                                      "revoked_at": None, "created_by": "a-janet"}]}}
    base.update(over)
    return base


@pytest.fixture
def plane(tmp_path):
    (tmp_path / "planes").mkdir()
    pl = PlaneStore(tmp_path / "planes").create("ardmore")
    prov = {"mark": "stated", "by": "Admin", "from": "test"}

    def seed(doc):
        for pid, name, acct, tags in (("p-fin", "Fiona Finance", "a-fin", ["finance"]), ("p-grace", "Grace Ward", "a-grace", ["compliance"]),
                                      ("p-sally", "Sally Share", "a-sally", []), ("p-none", "No Area", None, [])):
            store.set_cell(doc, f"people.{pid}.name", name, prov)
            if acct:
                store.set_cell(doc, f"people.{pid}.account_id", acct, prov)
            if tags:
                store.set_cell(doc, f"people.{pid}.areas", tags, prov)
    store.mutate(pl, seed)
    return pl


@pytest.mark.parametrize("who", list(EXPECTED))
def test_matrix_cells(plane, who):
    got = vis.columns_for(plane, intent(), viewers()[who])
    assert (got and tuple(got[c] for c in COLS)) == (EXPECTED[who] or None)


def test_matrix_literal_in_code_matches_the_table():
    rows = {k: tuple(v[c] for c in COLS) for k, v in vis.MATRIX.items()}
    assert rows.pop("affected_on") == EXPECTED_AFFECTED_ON
    assert rows.pop("other_area") == ("N",) * 10
    assert rows == {k: v for k, v in EXPECTED.items() if v}


def test_affected_switch_on_opens_content(plane):
    got = vis.columns_for(plane, intent(affected_may_read=True), viewers()["affected_off"])
    assert tuple(got[c] for c in COLS) == EXPECTED_AFFECTED_ON
    assert vis.may_open_content(plane, intent(affected_may_read=True), viewers()["affected_off"])
    assert not vis.may_open_content(plane, intent(), viewers()["affected_off"])


def test_hidden_intent_is_absent_not_forbidden(plane):
    assert vis.read_intent(plane, intent(), viewers()["other_area"]) is None
    assert vis.read_intent(plane, intent(), Viewer("", frozenset())) is None  # no name, no account, no role
    app = FastAPI()
    app.include_router(vis.router)
    app.state.settings = SimpleNamespace(data_root=plane.root.parent)
    app.state.account_store = SimpleNamespace(get=lambda a: {"display_name": "Grace Ward"}, in_company=lambda c: [])
    write_json_atomic(plane.path("intents", "i-1", "intent.json"), intent())

    @app.middleware("http")
    async def sign_in(request, call_next):
        request.state.company_id, request.state.account_id, request.state.roles = "ardmore", "a-grace", ["participant"]
        return await call_next(request)
    c = TestClient(app)
    hidden, missing = c.get("/api/intents/i-1/content"), c.get("/api/intents/made-up/content")
    assert hidden.status_code == missing.status_code == 404 and hidden.json() == missing.json()


def test_draft_is_the_starters_alone(plane):
    d = intent(state="draft")
    assert vis.read_intent(plane, d, viewers()["organiser"])["title"] == "Cash view"
    for who in ("sponsor", "company_admin", "super_admin", "same_area", "participant", "share_visitor"):
        assert vis.read_intent(plane, d, viewers()[who]) is None


def test_union_of_relations(plane):
    both = Viewer("Fiona Finance", frozenset(), account_id="a-fin")
    i = intent(people={**intent()["people"], "participants": [person("a-fin", "Fiona Finance")]})
    assert vis.columns_for(plane, i, both)["content"] == "Y"  # same-area and participant: participant columns
    admin_in = Viewer("Katie", frozenset({"company_admin"}), account_id="a-katie")
    assert vis.columns_for(plane, intent(), admin_in)["content"] == "Y"


def test_outcome_closure_and_people_filters(plane):
    closed = intent(state="closed")
    fin = vis.read_intent(plane, closed, viewers()["same_area"])
    assert fin["outcome"] and fin["closure"] == {"what_came_out": "Out", "next": closed["closure"]["next"]}
    assert fin["people"] == {"organiser": {"name": "Janet Shaw"}} and "refs" not in fin and not fin["access"]["content"]
    assert "outcome" not in vis.read_intent(plane, intent(), viewers()["same_area"])  # not closed yet
    adm = vis.read_intent(plane, intent(), viewers()["company_admin"])
    assert adm["people"]["counts"] == {"participants": 1, "affected": 1, "observers": 1} and adm["ratings"] == {"count": 1, "average": None}
    sup = vis.read_intent(plane, intent(), viewers()["super_admin"])
    assert set(sup) == {"id", "type", "state", "areas", "title", "time_box", "time_box_status", "people_count", "access"}
    assert sup["time_box_status"] == "running"


def test_titles_private_hides_the_super_admin_title(plane):
    areas.set_titles_private(plane, True, "Admin")
    sup = vis.read_intent(plane, intent(), viewers()["super_admin"])
    assert "title" not in sup and "purpose" not in sup
    assert vis.read_intent(plane, intent(), viewers()["organiser"])["title"] == "Cash view"


def test_nobody_gets_account_ids_or_raters(plane):
    for who in EXPECTED:
        seen = vis.read_intent(plane, intent(), viewers()[who])
        text = str(seen)
        assert "rated_by" not in text and "token_hash" not in text
        if who != "organiser" and seen:
            assert "'by': 'a-katie'" not in text and "a-harvey" not in text and "'account_id'" not in text


def test_share_revoked_or_expired_gives_no_access(plane):
    i = intent()
    i["share"]["who_may_open"][0]["revoked_at"] = "2026-10-02T00:00:00+00:00"
    assert vis.read_intent(plane, i, viewers()["share_visitor"]) is None
    j = copy.deepcopy(intent())
    j["share"]["who_may_open"][0]["expires_at"] = "2020-01-01T00:00:00+00:00"
    assert vis.read_intent(plane, j, viewers()["share_visitor"]) is None


def test_tag_change_applies_at_once_and_retired_area_still_matches(plane):
    fiona = viewers()["same_area"]
    assert vis.read_intent(plane, intent(), fiona)
    store.mutate(plane, lambda d: store.set_cell(d, "people.p-fin.areas", [], {"mark": "stated", "by": "Admin", "from": "t"}))
    assert vis.read_intent(plane, intent(), fiona) is None


def test_record_written_by_area_name_still_matches_the_tag(plane):
    """Start flows write area names ("Finance"); a tag is an id ("finance"). Both name the same area, so the same-area row holds."""
    store.mutate(plane, lambda d: areas._add(d, "finance", "Finance", "department", "Admin", "test"))
    seen = vis.read_intent(plane, intent(areas=["Finance"]), viewers()["same_area"])
    assert seen and not seen["access"]["content"]
    assert vis.read_intent(plane, intent(areas=["Compliance team"]), viewers()["same_area"]) is None


def test_pack_suggestions_are_never_stored_until_accepted(plane):
    root = Path(__file__).resolve().parents[2]
    pack = PackLoader(root / "packs").load("family_office")
    assert [s["name"] for s in areas.suggestions(pack, store.load(plane))] == ["Finance", "Investments", "Operations", "Compliance"]
    assert areas.listing(store.load(plane)) == []
    areas.accept(plane, pack, ["finance", "operations"], "Admin")
    got = {a["id"]: a for a in areas.listing(store.load(plane))}
    assert set(got) == {"finance", "operations"} and got["finance"]["from"] == "Accepted from suggestions" and got["finance"]["status"] == "active"
    assert [s["id"] for s in areas.suggestions(pack, store.load(plane))] == ["investments", "compliance"]
    assert areas.suggestions(PackLoader(root / "packs").load("no_such_industry"), store.load(plane)) == []  # an empty pack gives none


def test_areas_admin_rules(plane):
    aid = areas.add(plane, "Treasury", "department", "Admin")
    with pytest.raises(areas.AreaRefusal):
        areas.add(plane, " treas ury ", "department", "Admin")  # same name, spaces and case ignored
    areas.rename(plane, aid, "Treasury and Cash", "Admin")
    assert aid == "treasury" and areas.listing(store.load(plane))[0]["name"] == "Treasury and Cash"
    areas.set_status(plane, aid, "retired", "Admin")
    assert areas.listing(store.load(plane))[0]["status"] == "retired"
    with pytest.raises(areas.AreaRefusal):
        areas.tag(plane, "p-fin", ["treasury"], "Admin")  # retired areas are not offered
    areas.set_status(plane, aid, "active", "Admin")
    areas.tag(plane, "p-fin", ["treasury"], "Admin")
    assert areas.areas_of_account(store.load(plane), "a-fin") == {"treasury"}
    assert areas.reach(store.load(plane), ["treasury"]) == {"count": 1, "missing": None}
