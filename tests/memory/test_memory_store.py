"""Agent memory store (MEM-1): filters, person edits, compaction, company digest. Synthetic data, a temporary plane."""
import pytest

from sh_platform import memory
from sh_platform.plane import PlaneStore
from sh_platform.profile import store

P = {"mark": "stated", "by": "Mei Tan", "from": "Access list"}


@pytest.fixture
def plane(tmp_path):
    (tmp_path / "planes").mkdir()
    pl = PlaneStore(tmp_path / "planes").create("family-a")
    store.record(pl, "governance.restricted_areas.hr.area", "HR", P)
    store.record(pl, "people.sue-sponsor.name", "Sue Sponsor", P)
    store.record(pl, "people.dan-data.name", "Dan Data", P)
    return pl


def e(text, kind="fact", conv="c1", **kw):
    return {"kind": kind, "text": text, "conversation": conv, "at": "2026-10-01", **kw}


def texts(doc):
    return [x["text"] for x in doc["entries"]]


def test_filters_drop_what_must_not_be_remembered(plane):
    doc = memory.remember(plane, "north", "p1", [
        e("Capital calls arrive by email", conv="c1"),
        e("Private note", anonymous=True),
        e("HR reviews are slow"),
        e("Fees were 2.5% last year"),
        e("Costs 1,200 USD"),
        e("Write to dan@example.org"),
        e("Call +65 6123 4567"),
        e("Account GB29NWBK60161331926819 is used"),
    ])
    assert texts(doc) == ["Capital calls arrive by email"]


def test_person_edit_survives_a_remember(plane):
    doc = memory.remember(plane, "north", "p1", [e("Prefers a weekly summary")])
    doc["entries"][0].update(text="Prefers a weekly summary on Monday", by="person")
    memory.save(plane, "north", "p1", doc)
    out = memory.remember(plane, "north", "p1", [e("Prefers a weekly summary on Monday!", conv="c2")])
    assert texts(out) == ["Prefers a weekly summary on Monday"] and out["entries"][0]["by"] == "person"
    # a changed fact replaces the old one with the date; a contradiction is kept as open
    memory.remember(plane, "lens", "p1", [e("The custody feed lands every day")])
    out = memory.remember(plane, "lens", "p1", [e("The custody feed lands every day.", conv="c2"), e("The custody feed lands every week")])
    assert [x["kind"] for x in out["entries"]] == ["fact", "open"] and len(out["entries"][0]["from"]) == 2


def test_compaction_keeps_newest_five_and_provenance(plane):
    for i in range(8):
        memory.remember(plane, "nira", "p1", [e(f"Topic {chr(97 + i) * 600} noted", conv=f"c{i}")])
    doc = memory.load(plane, "nira", "p1")
    kinds = [x["kind"] for x in doc["entries"]]
    assert kinds.count("digest") == 1 and len(kinds) == 6
    digest = next(x for x in doc["entries"] if x["kind"] == "digest")
    assert {f["conversation"] for f in digest["from"]} == {"c0", "c1", "c2"}
    assert sum(len(x["text"]) for x in doc["entries"]) <= memory.BUDGET


def test_company_digest_has_no_names_and_no_lone_self_statements(plane):
    memory.remember(plane, "north", "p1", [e("Sue Sponsor wants one shared calendar"), e("I prefer short emails", "preference"), e('He said "ship it"')])
    memory.remember(plane, "north", "p2", [e("Dan Data wants one shared calendar!", conv="c9")])
    doc = memory.company_digest(plane, "north")
    assert texts(doc) == ["a colleague wants one shared calendar"]
    assert "p1" not in str(doc) and "c9" not in str(doc)
    assert memory.for_prompt(plane, "north", "p1")["company"][0]["text"] == "a colleague wants one shared calendar"
