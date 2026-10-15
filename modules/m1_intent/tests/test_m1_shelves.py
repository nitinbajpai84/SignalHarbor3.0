"""IC-3b, the four shelves (A-058): must, should, good_to_have, future. Synthetic family-office notes, stub North."""
import json

import pytest

from modules.m1_intent.domain import board as B
from modules.m1_intent.domain import charter_export as X
from modules.m1_intent.domain import together as T
from modules.m1_intent.store.sessions import SessionStore
from modules.m1_intent.store.together_shelves import ShelfStore
from test_m1_board_kit import Board, together

S = B.load_settings()
NOW = 1_790_000_000.0  # 2026-09-21 in UTC



def ids(b) -> dict:
    return {c["name"]: c["id"] for c in b.org_call("GET", "/together").json()["clusters"]}


# ---- domain
def test_could_reads_as_good_to_have_and_an_old_vote_still_counts():
    assert T.shelf_id("could") == "good_to_have" and T.shelf_id("must") == "must" and "could" not in T.SHELVES
    assert T.SHELVES == ("must", "should", "good_to_have", "future")
    z = {o: 0 for o in S.option_ids}
    d = T.vote(S, {"votes": {}, "agrees": {}, "comments": {}, "ticked": []}, "c1", "a", "could")
    assert T.shelf_id(T.priority(S, T.tally(S, d, "c1"))) == "good_to_have" and T.priority(S, z) is None


def test_the_default_review_date_is_one_quarter_on_from_the_clock():
    assert T.default_review_date(NOW) == "2026-12-21"
    assert T.default_review_date(1_772_000_000.0) == "2026-05-25"  # 2026-02-25
    assert T.default_review_date(1_788_000_000.0) == "2026-11-29"  # 2026-08-29; month-end cut: 2026-11-30 exists
    from datetime import datetime, timezone
    assert T.default_review_date(datetime(2026, 11, 30, tzinfo=timezone.utc).timestamp()) == "2027-02-28"


def test_future_needs_a_reason_and_gets_a_review_date_and_every_move_is_kept():
    c, empty = {"id": "c1"}, {"shelves": {}, "moves": []}
    for bad in (None, "", "   ", 5):
        with pytest.raises(B.BoardError):
            T.move_to_shelf(empty, c, "future", bad, "Ada", NOW, 300)
    with pytest.raises(B.BoardError):
        T.move_to_shelf(empty, c, "maybe", None, "Ada", NOW, 300)
    with pytest.raises(B.BoardError):
        T.move_to_shelf(empty, c, "future", "x" * 301, "Ada", NOW, 300)
    one = T.move_to_shelf(empty, c, "could", None, "Ada", NOW, 300)  # the old name is written as the new one
    assert one["shelves"]["c1"] == {"shelf": "good_to_have", "reason": None, "review_date": None}
    two = T.move_to_shelf(one, c, "future", "  Wait for   the new   custodian ", "Ben", NOW, 300)
    assert two["shelves"]["c1"] == {"shelf": "future", "reason": "Wait for the new custodian", "review_date": "2026-12-21"}
    assert [(m["by"], m["from"], m["to"]) for m in two["moves"]] == [("Ada", None, "good_to_have"), ("Ben", "good_to_have", "future")]
    assert all(m["at"].startswith("2026-09-21") and m["cluster"] == "c1" for m in two["moves"])


def test_may_shelve_lets_must_and_should_through_only_when_governed():
    ok = {"id": "c1", "governed": True, "missing": []}
    bad = {"id": "c1", "governed": False, "missing": ["owners", "may_see"]}
    assert T.may_shelve(ok, "must") == (True, "") and T.may_shelve(bad, "good_to_have") == (True, "") and T.may_shelve(bad, "future") == (True, "")
    assert T.may_shelve(bad, "must") == (False, "Needs an owner and who may see before it can sit on Must.")
    assert T.may_shelve({**bad, "missing": ["owners", "may_see", "review_date"]}, "should")[1] == "Needs an owner, who may see and a review date before it can sit on Should."
    assert T.may_shelve({"id": "c1"}, "must") == (False, "Define the measures first.")  # no baseline, or no measures: nothing served


def test_a_refusing_may_shelve_stops_the_move(monkeypatch):
    monkeypatch.setattr(T, "may_shelve", lambda c, s: (False, "Not governed yet."))
    with pytest.raises(B.BoardError, match="Not governed yet."):
        T.move_to_shelf({"shelves": {}, "moves": []}, {"id": "c1"}, "must", None, "Ada", NOW, 300)


def test_the_result_leaves_a_future_cluster_out_of_the_charter_lists_and_parks_it():
    clusters = [{"id": "c1", "name": "Late calls", "note_ids": ["n1", "n2"]}, {"id": "c2", "name": "Old reports", "note_ids": ["n3"]},
                {"id": "c3", "name": "Fee lists", "note_ids": ["n4"]}]
    data = {"votes": {}, "agrees": {}, "comments": {}, "ticked": ["c1", "c2"]}
    shelves = {"c1": {"shelf": "good_to_have", "reason": None, "review_date": None},
               "c2": {"shelf": "future", "reason": "Next year", "review_date": "2026-12-21"}}
    r = T.result(S, data, clusters, "together", "s", 0, shelves)
    assert [c["id"] for c in r["ticked"]] == ["c1"] and r["ticked"][0]["priority"] == "could"  # the contract's id for the shelf
    assert [c["id"] for c in r["carried"]] == ["c3"]
    assert r["parked"] == [{"id": "c2", "name": "Old reports", "note_count": 1, "reason": "Next year", "review_date": "2026-12-21"}]
    assert "parked" not in T.result(S, data, clusters, "together", "s", 0)  # no shelves: the old shape


# ---- the charter export
def test_the_export_lists_parked_clusters_with_reason_and_review_date():
    view = {"footer": {"date": "2026-09-21", "participants": 2, "notes": 4, "later": 0}, "problems": [], "later": [],
            "signing": {"signers": [{"name": "Sam Sponsor", "at": "2026-09-21T10:00:00+00:00"}]},
            "parked": [{"title": "Old reports", "reason": "Next <year>", "review_date": "2026-12-21"}]}
    md, html = X.to_markdown(view, "Acme Office", "Session", False), X.to_html(view, "Acme Office", "Session", False)
    assert "## Parked for later" in md and "Old reports: Next" in md and "review by 2026-12-21" in md
    assert "<h2>Parked for later</h2>" in html and "Next &lt;year&gt;" in html
    assert "Parked for later" not in X.to_markdown({k: v for k, v in view.items() if k != "parked"}, "Acme Office", "Session", False)


# ---- the route
@pytest.mark.parametrize("company", ["co-a", "co-b"])  # two industries
def test_the_organiser_shelves_a_cluster_and_it_is_read_back_and_audited(tmp_path, company):
    b = together(tmp_path, company=company)
    cid = ids(b)["Calls arrive too late"]
    r = b.org_call("POST", f"/together/clusters/{cid}/shelf", json={"shelf": "could"})
    assert r.status_code == 200, r.text
    c = next(c for c in r.json()["clusters"] if c["id"] == cid)
    assert c["shelf"] == "good_to_have" and c["shelf_reason"] is None and c["review_date"] is None
    r = b.org_call("POST", f"/together/clusters/{cid}/shelf", json={"shelf": "future", "reason": "Wait for the custodian"})
    c = next(c for c in r.json()["clusters"] if c["id"] == cid)
    assert c["shelf"] == "future" and c["shelf_reason"] == "Wait for the custodian" and len(c["review_date"]) == 10
    moves = ShelfStore(b.w.plane(company)).get(b.sid)["moves"]
    assert [(m["from"], m["to"]) for m in moves] == [(None, "good_to_have"), ("good_to_have", "future")]
    assert all(m["by"] and m["at"] and m["cluster"] == cid for m in moves)
    assert any(x["id"] == cid for x in b.org_call("GET", "/board").json()["clusters"])  # nothing leaves the wall


def test_future_without_a_reason_and_a_wrong_shelf_are_refused(tmp_path):
    b = together(tmp_path)
    cid = ids(b)["Calls arrive too late"]
    for body in ({"shelf": "future"}, {"shelf": "future", "reason": " "}, {"shelf": "soon"}):
        assert b.org_call("POST", f"/together/clusters/{cid}/shelf", json=body).status_code == 422
    assert b.org_call("POST", f"/together/clusters/{cid}/shelf", json={}).status_code == 400
    assert b.org_call("POST", f"/together/clusters/{'0' * 16}/shelf", json={"shelf": "must"}).status_code == 422
    assert ShelfStore(b.w.plane("co-a")).get(b.sid)["moves"] == []


def test_a_guest_cannot_shelve_and_a_signing_room_refuses(tmp_path):
    b = together(tmp_path)
    cid = ids(b)["Calls arrive too late"]
    assert b.guests[0].call("POST", f"/together/clusters/{cid}/shelf", json={"shelf": "must"}).status_code == 403
    assert ShelfStore(b.w.plane("co-a")).get(b.sid)["moves"] == []
    SessionStore(b.w.plane("co-a")).transition(b.sid, "signing")
    r = b.org_call("POST", f"/together/clusters/{cid}/shelf", json={"shelf": "must"})
    assert r.status_code == 409 and ShelfStore(b.w.plane("co-a")).get(b.sid)["moves"] == []


def test_the_charter_and_hand_off_never_see_a_future_cluster(tmp_path):
    b = together(tmp_path)
    cs = ids(b)
    late, expo = cs["Calls arrive too late"], cs["No single exposure view"]
    _governed_world(b, FIELDS)  # Should needs a governed cluster (A-054)
    for cid in (late, expo):
        assert b.org_call("POST", f"/together/clusters/{cid}/tick", json={"ticked": True}).status_code == 200
    assert b.org_call("POST", f"/together/clusters/{late}/shelf", json={"shelf": "should"}).status_code == 200
    assert b.org_call("POST", f"/together/clusters/{expo}/shelf", json={"shelf": "future", "reason": "Not this year"}).status_code == 200
    res = T.read_together_result(b.w.plane("co-a"), b.sid)
    assert [c["id"] for c in res["ticked"]] == [late] and res["ticked"][0]["priority"] == "should"
    assert expo not in {c["id"] for c in res["carried"]}
    [p] = res["parked"]
    assert (p["id"], p["reason"]) == (expo, "Not this year") and p["review_date"]
    assert "Guest" not in json.dumps(res)


def test_an_empty_company_has_no_shelves_and_a_damaged_file_is_refused(tmp_path):
    b = Board(tmp_path, company="co-solo", seats=1, names=(), notes=[])
    b.close_rooms()
    b.group()
    b.to_together()
    assert "parked" not in T.read_together_result(b.w.plane("co-solo"), b.sid)
    assert ShelfStore(b.w.plane("co-solo")).get(b.sid) == {"session_id": b.sid, "updated_at": None, "shelves": {}, "moves": []}
    path = b.w.plane("co-solo").path("intents", "m1_intent", "together_shelves", f"{b.sid}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(Exception):
        T.read_together_result(b.w.plane("co-solo"), b.sid)


def test_the_drafted_charter_and_download_carry_parked_but_never_as_a_problem(tmp_path):
    b = together(tmp_path)
    cs = ids(b)
    late, expo = cs["Calls arrive too late"], cs["No single exposure view"]
    for cid in (late, expo):
        b.org_call("POST", f"/together/clusters/{cid}/tick", json={"ticked": True})
    b.org_call("POST", f"/together/clusters/{expo}/shelf", json={"shelf": "future", "reason": "Not this year"})
    r = b.org_call("POST", "/charter", json={"confirm": True})
    assert r.status_code == 201, r.text
    v = b.org_call("GET", "/charter").json()["charter"]
    assert [p["title"] for p in v["parked"]] == ["No single exposure view"] and v["parked"][0]["reason"] == "Not this year"
    assert v["parked"][0]["review_date"] and all(p["title"] != "No single exposure view" for p in v["problems"] + v["later"])


def test_a_damaged_shelf_file_stops_the_draft_and_saves_nothing(tmp_path):
    b = together(tmp_path)
    cid = ids(b)["Calls arrive too late"]
    b.org_call("POST", f"/together/clusters/{cid}/tick", json={"ticked": True})
    b.org_call("POST", f"/together/clusters/{cid}/shelf", json={"shelf": "future", "reason": "Later"})
    moves = ShelfStore(b.w.plane("co-a")).get(b.sid)["moves"]
    assert moves[0]["by_account"]  # the account is kept beside the name
    b.w.plane("co-a").path("intents", "m1_intent", "together_shelves", f"{b.sid}.json").write_text("{not json", encoding="utf-8")
    r = b.org_call("POST", "/charter", json={"confirm": True})
    assert r.status_code == 500 and r.json()["error"] == "unreadable"
    assert SessionStore(b.w.plane("co-a")).get(b.sid)["state"] == "together"  # nothing was drafted or saved


# ---- IC-3e: Must and Should only for a governed cluster (A-054)
FIELDS = ("owners", "classification", "may_see", "resolving", "affects", "review_date")


def _governed_world(b, stated, baseline=True):
    """Links the first cluster to pack measure K1 and, with `baseline`, gives module 2 a signed baseline whose governed state marks `stated` fields stated."""
    from test_m1_charter_kit import give_pack_measures
    from modules.m1_intent.store.board import BoardStore
    give_pack_measures(b.w, "industry_a")
    plane = b.w.plane("co-a")
    cid = ids(b)["Calls arrive too late"]
    BoardStore(plane).update(b.sid, lambda d: {**d, "clusters": [{**c, "pack_problem_id": "P-0"} if c["id"] == cid else c for c in d["clusters"]]})
    if baseline:
        out = plane.path("intents", "m2_baseline", "outcomes")
        out.mkdir(parents=True, exist_ok=True)
        (out / ("a" * 32 + ".json")).write_text(json.dumps({"kind": "baseline", "baseline_id": "b" * 32, "signed_at": "2026-01-01T00:00:00+00:00", "signatures": [{"name": "x"}]}))
        folder = plane.path("intents", "m2_baseline", "b" * 32)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "governed_state.json").write_text(json.dumps({"K1": {f: {"value": "x", "mark": "stated" if f in stated else "guessed"} for f in FIELDS}}))
    return cid


def test_a_governed_cluster_moves_to_must(tmp_path):
    b = together(tmp_path)
    cid = _governed_world(b, FIELDS)
    r = b.org_call("POST", f"/together/clusters/{cid}/shelf", json={"shelf": "must"})
    assert r.status_code == 200, r.text
    c = next(c for c in r.json()["clusters"] if c["id"] == cid)
    assert c["shelf"] == "must" and c["governed"] is True and c["missing"] == []


def test_an_ungoverned_cluster_is_refused_with_the_missing_fields_named(tmp_path):
    b = together(tmp_path)
    cid = _governed_world(b, ("classification", "resolving", "affects", "review_date"))
    r = b.org_call("POST", f"/together/clusters/{cid}/shelf", json={"shelf": "must"})
    assert r.status_code == 422 and "Needs an owner and who may see before it can sit on Must." in r.text
    assert ShelfStore(b.w.plane("co-a")).get(b.sid)["moves"] == []
    assert b.org_call("POST", f"/together/clusters/{cid}/shelf", json={"shelf": "good_to_have"}).status_code == 200  # the other shelves stay open


def test_no_baseline_means_define_the_measures_first(tmp_path):
    b = together(tmp_path)
    cid = _governed_world(b, (), baseline=False)
    r = b.org_call("POST", f"/together/clusters/{cid}/shelf", json={"shelf": "should"})
    assert r.status_code == 422 and "Define the measures first" in r.text


def test_every_served_cluster_carries_its_sessions_topic_and_none_when_it_has_none(tmp_path):
    b = together(tmp_path)
    topic = SessionStore(b.w.plane("co-a")).get(b.sid)["preparation"]["topic"]
    clusters = b.org_call("GET", "/together").json()["clusters"]
    assert clusters and all("topic" in c and c["topic"] == topic for c in clusters)
