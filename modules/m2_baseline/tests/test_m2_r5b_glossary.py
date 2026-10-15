"""Round 5B: a heading-and-bullet glossary is read, matching is repeatable, governance reaches the signed glossary."""
from pathlib import Path

from m2_kit import BASE, login
from test_m2_glossary import entry, gurl, seed, upload

from modules.m2_baseline.domain import glossary as G
from modules.m2_baseline.store import glossary as S
from modules.m2_baseline.store import kpis as K

FILE16 = Path(__file__).parents[3] / "packs/family_office/1/demo_story/16_business_glossary_raw.md"
LABELS = {"meaning", "owner", "reported", "source", "last updated", "how often", "definition"}


def test_the_demo_glossary_in_headings_and_bullets_is_read_term_by_term():
    terms, _ = G.parse_provided(FILE16.read_text(encoding="utf-8"))
    names = [t["term"] for t in terms]
    assert len(terms) == 19 and not {G.key(n) for n in names} & LABELS
    cushion = terms[0]
    assert cushion["term"] == "Cash cushion" and cushion["aliases"] == ["six-month headroom"]
    assert cushion["owner"].startswith("Tom Ng") and cushion["frequency"].startswith("monthly") and "Cash_NAV" in cushion["source"]
    assert "worst of the next six months" in cushion["definition"]


def test_label_words_are_never_terms_in_plain_lines():
    terms, _ = G.parse_provided("- Meaning: what it is\n- Owner: Sam\nReal term: its wording")
    assert [t["term"] for t in terms] == ["Real term"]


def test_code_matches_prefix_containment_and_plurals_without_a_model():
    kpis = [{"id": "K1", "name": "Known obligations due"}, {"id": "K2", "name": "Capital call"}, {"id": "K3", "name": "Excess return versus benchmark (alpha)"}]
    terms = [{"term": "Alpha", "aliases": ["excess return"]}, {"term": "Capital calls", "aliases": []}, {"term": "Known obligations", "aliases": []}]
    assert G.code_matches(kpis, terms) == {"K1": 2, "K2": 1, "K3": 0}


MD = ("## Known obligations (also: \"what we owe\")\n- Meaning: payments we have committed to.\n- Owner: Tom Ng\n- Reported: monthly\n- Source: the tracker\n"
      "## Vendor rating\n- Meaning: how we score suppliers.\n")


def test_owner_frequency_and_source_come_over_as_provided_values(world):
    bid = seed(world, specs=[("Known obligations due", "", "no", [])])
    c = login(world, "co-a")
    e = entry(upload(c, bid, "g.md", MD.encode()).json(), "Known obligations due")
    assert e["match"] == "name" and e["frequency"]["value"] == "monthly" and e["frequency"]["mark"] == "stated"
    assert e["data_source"]["value"] == "the tracker" and e["text"]["data_source"] == "the tracker"
    assert "what we owe" in e["text"]["aliases"]


def _term(name):
    return {"term": name, "definition": "d", "aliases": [], "owner": "", "frequency": "", "source": ""}


def test_two_builds_match_the_same_and_the_model_is_asked_once(world):
    bid, plane = seed(world, specs=[("Cash cushion x", "d", "no", []), ("Pay y", "d", "no", [])]), world.plane("co-a")
    calls = []

    def matcher(terms, measures):
        calls.append((terms, measures))
        return {0: 0}

    doc = {"title": "g", "filename": "g.md", "by": "A", "at": "t", "truncated": False, "terms": [_term("Zeta"), _term("Alpha")]}
    first = S.build(plane, bid, lambda k: True, matcher, provided=doc)
    again = S.build(plane, bid, lambda k: True, matcher)
    S.build(plane, bid, lambda k: True, matcher, provided={**doc, "terms": [_term("Zeta")]})
    assert len(calls) == 2 and calls[0][0] == ["Alpha", "Zeta"]  # fixed order; the second build reused the stored answer; a changed file asks again
    assert first["matches"] and first["asked"] == again["asked"]
    assert [e.get("matched_term") for e in first["entries"]] == [e.get("matched_term") for e in again["entries"]]


def test_a_governance_change_reaches_the_glossary_at_once(world):
    bid, plane = seed(world, specs=[("Executive pay", "d", "no", [])]), world.plane("co-a")
    c = login(world, "co-a")
    c.post(gurl(bid, "/build"))
    kid = K.read_kpis(plane, bid)[0]["id"]
    assert c.put(f"{BASE}/baselines/{bid}/kpis/{kid}/governance", json={"personal": "yes", "may_see": []}).status_code == 200
    e = c.get(gurl(bid)).json()["entries"][0]
    assert e["personal"] == "yes" and e["text"]["who"] != G.OPEN_TO_ALL


def test_the_glossary_follows_governance_before_signing(world):
    bid, plane = seed(world, specs=[("Executive pay", "d", "no", [])]), world.plane("co-a")
    login(world, "co-a").post(gurl(bid, "/build"))
    kid = K.read_kpis(plane, bid)[0]["id"]
    K.change(plane, bid, kid, lambda k: {**k, "governance": {**k["governance"], "personal": "yes", "may_see": ["Test Pat Boss"]}})
    S.refresh_governance(plane, bid)
    e = S.read(plane, bid)["entries"][0]
    assert e["personal"] == "yes" and e["who_may_see"] == ["Test Pat Boss"]
