"""The map's data quality: one node per measure, charter problems by name, no unanswered person, plain source labels."""
from sh_platform.graph.build import rebuild
from sh_platform.profile import record
from test_graph_build import LENS, by_type, edges, plane, put, seed  # noqa: F401


def figure(plane, key, name, value, owner="Dan Data"):
    for f, v in (("measure", name), ("figure", value), ("owner", owner)):
        record(plane, f"reported_figures.{key}.{f}", v, LENS)


def test_a_reported_figure_merges_into_its_baseline_measure(plane):
    seed(plane)
    figure(plane, "a", " single-issuer CONCENTRATION ", 11.8)
    figure(plane, "b", "Unbaselined thing", 3)
    figure(plane, "c", "Empty thing", None)
    g = rebuild(plane)
    assert by_type(g, "Measure") == {"measure:M1", "measure:unbaselined-thing"}


def test_problems_are_the_charters_and_a_blank_wall_card_is_not_one(plane):
    seed(plane)
    record(plane, "cards.blank.lane", "tracking", LENS)
    g = rebuild(plane)
    assert {n["id"]: n["label"] for n in g["nodes"] if n["type"] == "Problem"} == {"problem:p1": "Concentration is reported late", "card:k1": "Exposure file arrives late"}


def test_no_unanswered_person_and_a_plain_pipeline_label(plane):
    seed(plane)
    put(plane, ("build", "pipelines", "custody_feed.json"), {"source": "custody_feed", "marts": [], "owner": "Not available yet"})
    put(plane, ("build", "pipelines", "loose_file.json"), {"source": "loose_file", "marts": [], "owner": "Dan Data"})
    g = rebuild(plane)
    assert "person:not-available-yet" not in by_type(g, "Person")
    assert {n["id"]: n["label"] for n in g["nodes"] if n["type"] == "Pipeline"} == {"pipeline:custody-feed": "Custody feed", "pipeline:loose-file": "Loose file"}
    assert ("pipeline:loose-file", "person:dan-data") in edges(g, "owned_by")


def test_a_sealed_card_keeps_no_words_in_the_projection(plane):
    seed(plane)
    record(plane, "cards.s1.lane", "tracking", LENS)
    record(plane, "cards.s1.q1", "Secret payout zebra", LENS)
    record(plane, "cards.s1.sealed", True, LENS)
    g = rebuild(plane)
    assert "zebra" not in str(g).lower()
    assert {n["label"] for n in g["nodes"] if n["id"] == "card:s1"} == {"Sealed card"}
