"""D-022 the simple business-graph picture at sign-off: problems linked to the company's own pack measures, labelled as a
suggestion. Only pack measures are ever drawn; no pack, or no linked problem, means no picture."""
from m1_kit import BASE
from modules.m1_intent.domain import charter as C
from modules.m1_intent.domain.contracts import load_charter_templates
from test_m1_charter_kit import stand_in_result  # noqa: F401  (autouse: the fixture together-result)
from test_m1_charter_kit import draft, give_pack_measures, ready

LABEL = "What others in the industry usually track (a suggestion, not your company's own definition)"


def test_the_picture_links_problems_to_pack_measures_only_and_says_it_is_a_suggestion(world):
    give_pack_measures(world, "industry_a")
    org, sid, _ = ready(world, seats=1)
    g = draft(org, sid)["charter"]["graph"]
    assert g["label"] == LABEL
    assert {k["id"] for k in g["kpis"]} == {"K1", "K2"}                  # K9 is named by the problem but is not in the pack
    assert {k["name"] for k in g["kpis"]} == {"Six-month funding headroom", "Exposure coverage"}
    assert g["links"] == [{"problem": "c1", "kpi": "K1"}, {"problem": "c2", "kpi": "K2"}]
    assert [p["id"] for p in g["problems"]] == ["c1", "c2"]               # c3 names no pack problem: not linked, not invented
    assert "K3" not in str(g)                                              # a pack measure nobody linked is not drawn


def test_the_picture_stays_after_signing(world):
    give_pack_measures(world, "industry_a")
    org, sid, _ = ready(world, seats=1)
    draft(org, sid)
    done = org.post(f"{BASE}/sessions/{sid}/charter/sign").json()["charter"]
    assert done["graph"] is not None and done["graph"]["label"] == LABEL


def test_another_industry_with_no_measures_gets_no_picture(world):
    give_pack_measures(world, "industry_a")                               # industry_b has no kpi_tree: never borrows A's
    org, sid, _ = ready(world, company="co-b", seats=1)
    assert draft(org, sid)["charter"]["graph"] is None


def test_a_company_with_no_pack_gets_no_picture(world):
    give_pack_measures(world, "industry_a")
    org, sid, _ = ready(world, company="co-none", seats=1)
    assert draft(org, sid)["charter"]["graph"] is None


def test_a_problem_that_names_no_pack_problem_is_never_linked():
    problems = [{"id": "x", "title": "T", "library_problem_id": None}, {"id": "y", "title": "U", "library_problem_id": "NOPE"}]
    pack_problems = [{"id": "P1", "kpi_ids": ["K1"]}]
    assert C.build_graph(problems, pack_problems, [{"id": "K1", "name": "One"}], "label") is None


def test_the_template_columns_come_from_the_contract():
    t = load_charter_templates()
    assert t.get("standard").columns == ("problem", "purpose", "priority", "notes") and t.get("short").columns == ("problem", "priority")
