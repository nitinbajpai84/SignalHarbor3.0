"""IC-3a: Stable colour per cluster (0-7 index). Tests for colour assignment and stability."""
import random
from pathlib import Path

import pytest

from modules.m1_intent.domain import board as B
from test_m1_board_kit import GROUPS, NOTES, Board, GatherStub, at_board, grouped

S = B.load_settings()


def ids(n):
    return [f"note{i}" for i in range(n)]


# ---- Domain tests: colour assignment and stability
def test_new_cluster_gets_lowest_unused_colour_index():
    """When a cluster is created, it gets the lowest unused colour index 0-7."""
    c1 = B.new_cluster("A", ids(2), "north")
    c2 = B.new_cluster("B", ids(2), "north")
    c3 = B.new_cluster("C", ids(2), "north")

    # Assign colours
    clusters = B.assign_colours([c1, c2, c3])

    assert clusters[0]["colour"] == 0
    assert clusters[1]["colour"] == 1
    assert clusters[2]["colour"] == 2


def test_colour_is_stable_across_note_moves():
    """Moving a note to another cluster does not change any cluster's colour."""
    clusters = B.apply_grouping(S, ids(6),
        [{"name": "A", "note_ids": ["note0", "note1"]},
         {"name": "B", "note_ids": ["note2", "note3"]}], set())
    clusters = B.assign_colours(clusters)

    colour_before = {c["id"]: c["colour"] for c in clusters}

    # Move a note
    clusters = B.move_note(clusters, ids(6), "note0", clusters[1]["id"])
    clusters = B.assign_colours(clusters)

    colour_after = {c["id"]: c["colour"] for c in clusters}
    assert colour_before == colour_after


def test_restored_cluster_keeps_old_colour():
    """When restoring North's grouping, clusters keep their original colours."""
    clusters = B.apply_grouping(S, ids(6),
        [{"name": "A", "note_ids": ["note0", "note1"]},
         {"name": "B", "note_ids": ["note2", "note3"]}], set())
    clusters = B.assign_colours(clusters)

    original_colours = {c["id"]: c["colour"] for c in clusters}
    original_ids = {c["id"] for c in clusters}

    # Modify by moving a note
    clusters = B.move_note(clusters, ids(6), "note0", clusters[1]["id"])
    clusters = B.assign_colours(clusters)

    # Simulate restore by creating fresh clusters with same IDs and names
    # In actual usage, the snapshot is restored
    snapshot_clusters = [
        B.new_cluster("A", ["note1"], "north"),
        B.new_cluster("B", ["note0", "note2", "note3"], "north")
    ]
    # Manually set IDs to match original
    for orig, snap in zip(sorted([c for c in clusters], key=lambda x: x["name"]),
                          sorted(snapshot_clusters, key=lambda x: x["name"])):
        snap["id"] = orig["id"]

    # In the restore flow, colours are preserved from previous state
    clusters = B.assign_colours(snapshot_clusters, preserve_ids=original_ids, previous_colours=original_colours)

    restored_colours = {c["id"]: c["colour"] for c in clusters}
    assert restored_colours == original_colours


def test_split_cluster_new_half_takes_lowest_unused_colour():
    """When splitting a cluster, the new half gets the lowest unused colour index."""
    clusters = B.apply_grouping(S, ids(6),
        [{"name": "A", "note_ids": ["note0", "note1", "note2"]},
         {"name": "B", "note_ids": ["note3", "note4"]}], set())
    clusters = B.assign_colours(clusters)

    colour_a = clusters[0]["colour"]
    colour_b = clusters[1]["colour"]

    # Preserve existing colours for split operation (simulates API behavior)
    existing_colours = {c["id"]: c["colour"] for c in clusters}
    existing_ids = {c["id"] for c in clusters}

    # Split cluster A
    clusters = B.split(S, clusters, clusters[0]["id"], ["note0"])
    # Preserve colours from existing clusters, assign new to new ones
    clusters = B.assign_colours(clusters, preserve_ids=existing_ids, previous_colours=existing_colours)

    # Original cluster A keeps colour 0
    cluster_a = next(c for c in clusters if "note1" in c["note_ids"])
    assert cluster_a["colour"] == colour_a

    # New cluster (split half) gets lowest unused (2)
    cluster_split = next(c for c in clusters if "note0" in c["note_ids"])
    assert cluster_split["colour"] == 2


def test_eight_clusters_then_ninth_reuses_lowest_freed_index():
    """With 8 clusters (indices 0-7), a 9th cluster reuses the lowest freed index."""
    # Create 8 clusters
    note_ids = ids(16)
    clusters = []
    for i in range(8):
        c = B.new_cluster(f"C{i}", note_ids[i*2:(i+1)*2], "north")
        clusters.append(c)

    clusters = B.assign_colours(clusters)
    colours = [c["colour"] for c in clusters]
    assert colours == [0, 1, 2, 3, 4, 5, 6, 7]

    # Preserve the original colours for tracking freed colours
    original_colours = {c["id"]: c["colour"] for c in clusters}
    original_ids = {c["id"] for c in clusters}

    # Remove cluster with colour 3 by moving its notes out
    clusters_3 = clusters[3]
    clusters = B.move_note(clusters, note_ids, note_ids[6], None)  # move from cluster 3
    clusters = B.move_note(clusters, note_ids, note_ids[7], None)  # move its second note

    # After moves, cluster 3 becomes empty and is removed
    clusters = [c for c in clusters if c["note_ids"]]

    # Add a 9th cluster
    c9 = B.new_cluster("C9", ["new_note_9"], "person")
    clusters.append(c9)

    # Preserve colours from original clusters (this is what the API does)
    clusters = B.assign_colours(clusters, preserve_ids=original_ids, previous_colours=original_colours)

    # The 9th should get colour 3 (lowest freed)
    cluster_9 = next(c for c in clusters if c["name"] == "C9")
    assert cluster_9["colour"] == 3


def test_all_clusters_have_colour_in_view():
    """The view output includes colour for every cluster."""
    clusters = B.apply_grouping(S, ids(4),
        [{"name": "A", "note_ids": ["note0", "note1"]},
         {"name": "B", "note_ids": ["note2", "note3"]}], set())
    clusters = B.assign_colours(clusters)

    notes = [{"id": n, "text": n, "anonymous": False} for n in ids(4)]
    view = B.view(clusters, notes)

    for cluster in view["clusters"]:
        assert "colour" in cluster
        assert 0 <= cluster["colour"] <= 7


# ---- API tests: colour in board response
def test_board_response_includes_colour_per_cluster(tmp_path):
    """The board API returns colour for each cluster."""
    b = grouped(tmp_path)
    resp = b.org_call("GET", "/board").json()

    for cluster in resp["clusters"]:
        assert "colour" in cluster
        assert isinstance(cluster["colour"], int)
        assert 0 <= cluster["colour"] <= 7
