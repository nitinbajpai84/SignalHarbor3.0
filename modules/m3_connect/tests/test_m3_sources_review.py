"""M3-P01 review round: module 2's current source rule and personal-data field guard, the stricter pain-point link, the account id on an override.
Route-level where a viewer is involved: the catalogue in the signed outcome record is edited the way module 2 would have written it."""
import json

import pytest

from m3_kit import BASE, person, signed_baseline
from modules.m3_connect.domain import sources as S
from test_m3_sources import _map_step_registered, c, link_table, measure, scored, start  # noqa: F401


def edit_catalogue(world, edit, company="m3-a"):
    for f in world.plane(company).path("intents", "m2_baseline", "outcomes").glob("*.json"):
        d = json.loads(f.read_text())
        edit(d["catalogue"])
        f.write_text(json.dumps(d))


def names(client, aid):
    return [s["name"] for s in client.get(f"{BASE}/assessments/{aid}/sources").json()["sources"]]


def setup(world, edit):
    team = signed_baseline(world)
    link_table(world)
    edit_catalogue(world, edit)
    world.app.state.lens_model_factory = lambda plane: None
    return team


@pytest.mark.parametrize("personal,by", [("Yes", "Test Data Dan"), ("", "x"), ("Not sure", "the organiser")])
def test_a_source_with_personal_data_and_no_names_is_restricted_for_all_but_the_head_of_data(world, personal, by):
    def edit(cat):
        cat["sources"][0]["Contains personal data?"] = {"value": personal or None, "mark": "stated" if personal else "unknown", "by": by}
        cat["sources"][0].pop("Who may see it", None)
    team = setup(world, edit)
    out, aid = start(world)
    sid = team.c["hana"].get(f"{BASE}/assessments/{aid}/sources").json()["sources"][0]["id"]
    assert names(out, aid) == ["A restricted source"]
    panel = out.get(f"{BASE}/assessments/{aid}/sources/{sid}").json()
    assert panel["source"]["name"] == "A restricted source" and panel["tables"] == [] and panel["measures"] == []
    assert "Custodian" not in str(panel)
    assert names(team.c["hana"], aid) == ["Custodian portal export"]


def test_a_not_sure_source_with_a_named_list_is_for_the_named_and_the_sponsor_only(world):
    def edit(cat):
        cat["sources"][0]["Contains personal data?"] = {"value": "Not sure", "mark": "stated", "by": "Test Data Dan"}
        cat["sources"][0]["Who may see it"] = c("Test Lens Lee")
    team = setup(world, edit)
    named, aid = start(world)
    assert names(named, aid) == ["Custodian portal export"]
    assert names(person(world, "m3-a", "Other Olly"), aid) == ["A restricted source"]
    assert names(team.c["sam"], aid) == ["Custodian portal export"]


def _fields(world, edit_fields, viewer_names):
    def edit(cat):
        cat["sources"][0]["Who may see it"] = c("Test Lens Lee")
        cat["fields"] = edit_fields
    team = setup(world, edit)
    named, aid = start(world)
    sid = named.get(f"{BASE}/assessments/{aid}/sources").json()["sources"][0]["id"]

    def seen(cl):
        return [f["name"] for t in cl.get(f"{BASE}/assessments/{aid}/sources/{sid}").json()["tables"] for f in t["fields"]]
    return team, named, seen, [person(world, "m3-a", n) for n in viewer_names]


def field(fid, name, cls=None):
    row = {"Field ID": c(fid), "Item ID": c("T01"), "Field name as in the source": c(name), "Feeds KPI": c("K1")}
    if cls:
        row["Personal data class"] = c(cls)
    return row


def test_a_personal_data_field_is_hidden_unless_the_viewer_is_named_on_its_source(world):
    team, named, seen, (other,) = _fields(world, [field("F1", "Open", "Neither"), field("F2", "Client names", "Personal data"), field("F3", "Blank class")],
                                           ["Other Olly"])
    assert seen(named) == ["Open", "Client names", "Blank class"]
    assert seen(other) == ["Open", "Blank class"]
    assert seen(team.c["hana"]) == seen(team.c["sam"]) == ["Open", "Blank class"]  # module 2's class guard: a named list means named people only


def test_a_personal_field_with_nobody_named_is_for_the_head_of_data_only(world):
    team = setup(world, lambda cat: cat.update(fields=[field("F2", "Client names", "Sensitive to the business")]))
    other, aid = start(world)
    sid = other.get(f"{BASE}/assessments/{aid}/sources").json()["sources"][0]["id"]

    def seen(cl):
        return [f["name"] for t in cl.get(f"{BASE}/assessments/{aid}/sources/{sid}").json()["tables"] for f in t["fields"]]
    assert seen(other) == [] and seen(team.c["hana"]) == ["Client names"]


def test_one_shared_generic_word_does_not_link_but_two_words_do():
    ms = [measure("K1", "Must", "Report accuracy review")]

    def link(title, so_that=""):
        return S._linked([{"title": title, "so_that": so_that, "measures": []}], ms)
    assert link("Late report packs") == []
    assert link("Report accuracy gaps") != []
    assert link("Accuracy review", "so that the board trusts it") != []
    assert link("Quarterly bonus pool") == []
    assert link("Late data report") == []  # generic words are not meaningful


def test_the_link_reason_says_possible_and_names_the_problem():
    text = " ".join(r["text"] for r in scored()["A"]["impact"]["reasons"])
    assert "possible link through the problem Slow reporting" in text


def test_an_override_keeps_the_account_id_beside_the_name_but_the_screen_never_gets_it(world):
    setup(world, lambda cat: None)
    c_, aid = start(world)
    sid = c_.get(f"{BASE}/assessments/{aid}/sources").json()["sources"][0]["id"]
    r = c_.put(f"{BASE}/assessments/{aid}/sources/{sid}/override", json={"impact": 0.1, "reason": "Because"})
    assert r.status_code == 200 and "by_id" not in r.json()["source"]["override"]
    stored = json.loads(next(world.plane("m3-a").path("intents", "m3_connect", "assessments").glob("*/sources.json")).read_text())
    o = stored["sources"][0]["override"]
    assert o["by"] == "Test Lens Lee" and o["by_id"] and o["by_id"] != o["by"]
