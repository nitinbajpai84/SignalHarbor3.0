"""The `cards` section: one write path, a sealed card is a silhouette to an outsider, an anonymous card has no author for anyone."""
import pytest

from sh_platform.profile import Viewer, cards_summary, read, record, record_card
from sh_platform.profile.store import load

LENS = {"mark": "stated", "by": "Lens", "agent": "lens", "from": "Policy sheet"}
ADMIN = Viewer("Mei Tan", frozenset({"company_admin"}))
TOM = Viewer("Tom Ng", frozenset({"analyst"}))
OUT = Viewer("Lena Ho", frozenset({"analyst"}))


def card(cid="c1", **kw):
    return {"id": cid, "lane": "missing", "sealed": False, "anonymous": False, "author": "mei-tan", "q1": "Pay bands are unclear", **kw}


def hr_area(plane):
    record(plane, "governance.restricted_areas.hr.area", "Pay", LENS)
    record(plane, "governance.restricted_areas.hr.may_see", ["Tom Ng"], LENS)


def test_a_card_is_written_with_provenance(plane):
    record_card(plane, card(from_interview="q3", room="abc"), by="Mei Tan", source="Interview with Mei Tan")
    c = read(plane, ADMIN)["cards"]["c1"]
    assert c["lane"]["value"] == "missing" and c["author"]["value"] == "mei-tan" and c["from_interview"]["value"] == "q3"
    assert c["q1"]["value"] == "Pay bands are unclear" and c["q1"]["mark"] == "stated" and c["q1"]["by"] == "Mei Tan"
    assert c["q1"]["from"] == "Interview with Mei Tan" and "cluster" not in c


def test_a_sealed_card_is_a_silhouette_to_an_outsider_and_whole_to_a_named_viewer(plane):
    hr_area(plane)
    record_card(plane, card(sealed=True, q1="Pay for the finance team is not tracked"))
    assert read(plane, OUT)["cards"]["c1"] == {"id": "c1", "lane": "missing", "sealed": True, "silhouette": "A sealed card"}
    assert read(plane, TOM)["cards"]["c1"]["q1"]["value"].startswith("Pay for")
    assert cards_summary(plane, OUT) == {"lanes": {"tracking": 0, "missing": 1, "watch": 0, "levers": 0}, "total": 1}


def test_an_anonymous_card_has_no_author_for_anyone_including_the_admin(plane):
    record_card(plane, {**card("c2", anonymous=True), "author": None, "anon_key": "anon-9f2c"})
    for v in (ADMIN, TOM, OUT):
        c = read(plane, v)["cards"]["c2"]
        assert "author" not in c and "anon-9f2c" not in str(c)
    assert "anonymous" not in str(load(plane)["cards"]["c2"]["q1"]["by"]).replace("anonymous", "", 1)  # provenance names nobody


@pytest.mark.parametrize("bad", [
    {"lane": "wishes"},
    {"anon_key": "anon-1"},  # author and key together
    {"author": None},  # named, nobody
    {"anonymous": True, "author": None},  # anonymous, no key
    {"anonymous": True, "author": "mei-tan", "anon_key": None},  # anonymous with a person
    {"sealed": "yes"},
    {"id": "Bad Id"},
])
def test_a_bad_card_is_refused_and_nothing_is_written(plane, bad):
    with pytest.raises(ValueError):
        record_card(plane, {**card(), **bad})
    assert read(plane, ADMIN)["cards"] == {}


def test_an_empty_company_has_no_cards_and_two_industries_stay_apart(plane, other_plane):
    assert read(plane, ADMIN)["cards"] == {} and cards_summary(plane, ADMIN)["total"] == 0
    record_card(plane, card())
    assert set(read(plane, ADMIN)["cards"]) == {"c1"} and read(other_plane, ADMIN)["cards"] == {}
    assert cards_summary(other_plane, ADMIN) == {"lanes": {"tracking": 0, "missing": 0, "watch": 0, "levers": 0}, "total": 0}
