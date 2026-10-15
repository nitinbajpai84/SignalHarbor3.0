"""The real path from four kinds of note to the charter: grouped within a kind on the board, ticked in the room, drafted as
four lists. No fixture result here (see test_m1_kinds_charter.py for the signed charter, its download and the hand-off)."""
from test_m1_board_kit import Board, GatherStub
from test_m1_kinds import KINDS, put


def test_notes_of_four_kinds_reach_the_charter_as_four_lists(tmp_path):
    b = Board(tmp_path, GatherStub({"pack": "Meeting pack", "rate": "Rate moves", "commit": "Commitment pace"}), notes=())
    ada, ben = b.guests
    put(ada, "intent", "Know our funding headroom every week")
    put(ada, "pain_point", "The meeting pack takes two days")
    put(ben, "pain_point", "The meeting pack is late for the council")
    put(ada, "future_signal", "Rate moves could change funding costs")
    put(ben, "future_signal", "Rate decisions change our cash returns")
    put(ada, "lever", "We can change how fast we commit")
    put(ben, "lever", "We can commit in smaller steps")
    b.close_rooms()
    b.group()
    b.to_together()
    clusters = b.org_call("GET", "/board").json()["clusters"]
    assert sorted(c["kind"] for c in clusters) == ["future_signal", "lever", "pain_point"]
    for c in clusters:
        assert b.org_call("POST", f"/together/clusters/{c['id']}/tick", json={"ticked": True}).status_code == 200
    r = b.org_call("POST", "/charter", json={"confirm": True})
    assert r.status_code == 201, r.text
    view = r.json()["charter"]
    lists = {l["kind"]: l for l in view["lists"]}
    by_id = {p["id"]: p for p in view["problems"]}
    assert [len(lists[k]["ids"]) for k in KINDS] == [0, 1, 1, 1]
    pain = by_id[lists["pain_point"]["ids"][0]]
    assert pain["details"] == [{"label": "Who is affected", "values": ["The finance team"]}, {"label": "How often", "values": ["Every month"]},
                               {"label": "KPI it shows up in", "values": ["Pack preparation time"]}]
    lever = by_id[lists["lever"]["ids"][0]]
    assert lever["details"] == [{"label": "KPIs it moves", "values": ["Funding headroom, Cash buffer"]}]
    assert view["footer"]["notes"] == 6 and view["alone"][0]["kind"] == "intent"  # the one intent note is on its own, left for later
