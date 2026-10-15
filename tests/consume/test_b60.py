"""Business views and context cards (spec 60): drafts, who may act, viewer-gated counts, card states. Synthetic data only."""
from sh_platform.consume import cards, feeds, lenses
from sh_platform.profile.view import Viewer
from tests.consume.test_feeds import BID, WEI, cell, make, put

MEI = Viewer("Mei Tan", frozenset({"participant"}))
OLA = Viewer("Ola Dim", frozenset({"participant"}))
NAMES = {"NAV": "Fees and effort hours", "CASH": "Cash held"}


def seeded(tmp_path):
    plane = make(tmp_path)
    put(plane, f"intents/m2_baseline/{BID}/kpis.json", [{"id": c, "name": n, "definition": cell(f"{n} means what it says.")} for c, n in NAMES.items()])
    put(plane, f"intents/m2_baseline/{BID}/governed_state.json", {
        k: {"owners": cell({"business": "Mei Tan", "data": "Ola Dim"}), "may_see": cell(["Mei Tan", "Ola Dim"])} for k in NAMES})
    put(plane, "build/blueprint.json", {"lineage": [{"measure": "NAV", "source": "Custody file", "fields": ["Value"], "mart": "gold.nav.fees_and_effort"}],
                                        "rules": [{"measure": "NAV", "rule": "Value is never negative.", "severity": "warn", "from": "scan"}]})
    return plane


def feed_of(plane, viewer):
    return feeds.build(plane, viewer)["measures"]


def doc_of(plane, viewer, only_mine=False):
    return lenses.compute(plane, viewer, feed_of(plane, viewer), [], [], frozenset(), lambda r: True, only_mine)


def test_lens_is_drafted_then_a_person_moves_it_and_the_draft_never_overwrites(tmp_path):
    plane = seeded(tmp_path)
    d = doc_of(plane, MEI)
    assert d["assigned"]["NAV"]["lens"] == "process_cost" and d["assigned"]["NAV"]["mark"] == "guessed" and "CASH" not in d["assigned"] and d["not_in_a_lens"] == 1
    assert lenses.assign(plane, OLA, "NAV", "risk", feed_of(plane, OLA))[0] == 403  # the data owner does not own the view
    assert lenses.assign(plane, MEI, "NAV", "risk", feed_of(plane, MEI))[0] == 200
    assert doc_of(plane, MEI)["assigned"]["NAV"] == {**lenses.read_rows(plane)["NAV"]} and lenses.lens_of(plane, "NAV")["key"] == "risk"
    assert lenses.read_rows(plane)["NAV"]["mark"] == "stated"


def test_counts_cover_only_measures_the_viewer_may_see(tmp_path):
    plane = seeded(tmp_path)
    mei = {x["key"]: x for x in doc_of(plane, MEI)["lenses"]}["process_cost"]
    wei = {x["key"]: x for x in doc_of(plane, WEI)["lenses"]}["process_cost"]
    assert mei["counts"]["measures"] == 1 and mei["counts"]["outside"] == 1  # the ten-period series breaks its range
    assert wei["counts"]["measures"] == 0 and wei["counts"]["outside"] == 0 and wei["empty"].startswith("Not available yet")


def test_line_of_work_is_owner_named_only(tmp_path):
    plane = seeded(tmp_path)
    assert doc_of(plane, MEI, True)["lenses"][1]["measures"] == ["NAV"]
    assert doc_of(plane, WEI, True)["has_line_of_work"] is False


def test_card_draft_confirm_edit_dispute_and_who_may(tmp_path):
    plane = seeded(tmp_path)
    s, c = cards.get_card(plane, MEI, feed_of(plane, MEI), "gold.nav")
    assert s == 200 and c["state"] == "draft" and c["lines"]["lineage"]["text"].startswith("Custody file") and c["lines"]["owner"]["text"] == "Ola Dim"
    assert c["lines"]["last_change"]["text"].startswith("Not available yet") and c["can"]["confirm"] is False
    assert cards.confirm(plane, MEI, feed_of(plane, MEI), "nav")[0] == 403
    assert cards.edit(plane, OLA, feed_of(plane, OLA), "nav", "meaning", "Plain words.", "")[0] == 422  # a why is required
    s, c = cards.edit(plane, OLA, feed_of(plane, OLA), "nav", "meaning", "Plain words.", "clearer")
    assert s == 200 and c["state"] == "draft" and c["lines"]["meaning"]["from"] == "edited by Ola Dim"
    s, c = cards.confirm(plane, OLA, feed_of(plane, OLA), "nav")
    assert c["state"] == "confirmed" and c["lines"]["meaning"]["mark"] == "stated" and c["lines"]["last_change"]["mark"] == "guessed"
    assert cards.facts_for(plane, "NAV")[0].startswith("What it means: Plain words.")
    s, c = cards.dispute(plane, OLA, feed_of(plane, OLA), "nav", "Wrong table")
    assert c["state"] == "disputed" and cards.confirm(plane, OLA, feed_of(plane, OLA), "nav")[0] == 422
    assert cards.facts_for(plane, "NAV")[0].startswith("(draft, not yet confirmed by Ola Dim)")
    r = cards.redraft(plane, "nav")
    assert r["state"] == "draft" and r["meaning"]["text"] == "Plain words." and any(h["action"] == "disputed" for h in r["history"])  # a person's edit is kept


def test_card_turns_changed_when_the_map_has_a_newer_version(tmp_path):
    plane = seeded(tmp_path)
    cards.get_card(plane, OLA, feed_of(plane, OLA), "nav")
    cards.confirm(plane, OLA, feed_of(plane, OLA), "nav")
    cards._write(plane, "nav", {**cards.read_card(plane, "nav"), "confirmed_at": "2000-01-01T00:00:00+00:00"})
    put(plane, "graph/versions.json", {"mart:gold-nav-fees": [{"v": 2, "what": "Source changed", "by": "Ola Dim", "at": "2001-01-01T00:00:00+00:00", "ref": "ini-" + "a" * 32}]})
    s, c = cards.get_card(plane, OLA, feed_of(plane, OLA), "nav")
    assert c["state"] == "changed" and c["stale_since"].startswith("2001") and c["lines"]["last_change"]["text"].startswith("Source changed")
    assert cards.confirm(plane, OLA, feed_of(plane, OLA), "nav")[1]["state"] == "confirmed"  # confirming again reads the change


def test_restricted_viewer_gets_name_and_owner_only_and_unknown_table_is_404(tmp_path):
    plane = seeded(tmp_path)
    s, c = cards.get_card(plane, WEI, feed_of(plane, WEI), "gold.nav")
    assert s == 200 and c["restricted"].startswith("Restricted") and "lines" not in c and c["owner"] == "Ola Dim"
    assert cards.get_card(plane, MEI, feed_of(plane, MEI), "gold.nope")[0] == 404
    assert cards.get_card(plane, MEI, feed_of(plane, MEI), "../x")[0] == 404
