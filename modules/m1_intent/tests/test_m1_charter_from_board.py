"""The real path from the board to the charter (M1-P07 into M1-P09): notes grouped on the board, voted and ticked in the
room, then drafted as the charter. No fixture together-result here: the charter reads the board's own result."""
from test_m1_board_kit import together


def test_the_charter_is_drafted_from_the_rooms_ticked_clusters_and_their_vote(tmp_path):
    b = together(tmp_path)
    late, view = b.cluster("Calls arrive too late")["id"], b.cluster("No single exposure view")["id"]
    for who in b.guests:
        assert who.call("POST", f"/together/clusters/{late}/vote", json={"option": "must"}).status_code == 200
    assert b.org_call("POST", f"/together/clusters/{late}/tick", json={"ticked": True}).status_code == 200

    r = b.org_call("POST", "/charter", json={"confirm": True})
    assert r.status_code in (200, 201), r.text
    rows = r.json()["charter"]["problems"]
    assert [(p["title"], p["priority"]) for p in rows] == [("Calls arrive too late", "must")]
    left = r.json()["charter"]["footer"]
    assert left["later"] == 1, left  # the unticked exposure cluster is carried, not lost
    assert view not in {p.get("id") for p in rows}
