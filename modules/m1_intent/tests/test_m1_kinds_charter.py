"""The charter, its download and the hand-off carry four separate lists: problems to solve now, pain points, what to
track for the future, levers for what-if. Synthetic family-office example text."""
from m1_kit import BASE
from modules.m1_intent.domain import charter as C
from modules.m1_intent.domain import charter_export as X
from modules.m1_intent.store.charter import read_outcome
from modules.m1_intent.store.sessions import SessionStore
from test_m1_charter_kit import CLUSTERS, draft, put_result, ready, second_signer, stand_in_result  # noqa: F401  (the autouse fixture)

HEADINGS = ["Problems to solve now", "Pain points", "What to track for the future", "Levers for what-if"]
DETAIL = lambda label, *values: {"label": label, "values": list(values)}  # noqa: E731
BY_KIND = [
    {"id": "c1", "kind": "intent", "title": "Know our funding headroom", "priority": "must", "note_count": 3, "agree_count": 2, "ticked": True,
     "so_that": None, "library_problem_id": None},
    {"id": "c2", "kind": "pain_point", "title": "The meeting pack takes two days", "priority": "should", "note_count": 2, "agree_count": 2,
     "ticked": True, "so_that": None, "library_problem_id": None,
     "details": [DETAIL("Who is affected", "The finance team"), DETAIL("How often", "Every month")]},
    {"id": "c3", "kind": "future_signal", "title": "Rate moves and funding cost", "priority": None, "note_count": 2, "agree_count": 1,
     "ticked": True, "so_that": None, "library_problem_id": None, "details": [DETAIL("Outside signal", "Central bank decisions")]},
    {"id": "c4", "kind": "lever", "title": "How fast we commit", "priority": "could", "note_count": 1, "agree_count": 1,
     "ticked": True, "so_that": None, "library_problem_id": None, "details": [DETAIL("KPIs it moves", "Funding headroom")]},
]


def signed(world, clusters):
    org, sid, code = ready(world, seats=3)
    put_result(world, "co-a", sid, clusters)
    draft(org, sid)
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    second_signer(world, "co-a", code).post(f"{BASE}/sessions/{sid}/charter/sign")
    return org, sid


def test_the_charter_view_has_the_four_lists_each_with_its_priority(world):
    org, sid, _ = ready(world)
    put_result(world, "co-a", sid, BY_KIND)
    view = draft(org, sid)["charter"]
    assert [(l["kind"], l["heading"]) for l in view["lists"]] == list(zip(["intent", "pain_point", "future_signal", "lever"], HEADINGS))
    by_id = {p["id"]: p for p in view["problems"]}
    assert [[by_id[i]["title"] for i in l["ids"]] for l in view["lists"]] == [[p["title"]] for p in BY_KIND]
    assert [by_id[i]["priority_label"] for i in ("c1", "c2", "c3", "c4")] == ["Must", "Should", None, "Could"]
    assert by_id["c2"]["details"] == BY_KIND[1]["details"] and by_id["c2"]["kind"] == "pain_point"


def test_an_empty_list_says_so_and_an_old_charter_is_all_problems_to_solve_now(world):
    org, sid, _ = ready(world)  # the old fixture clusters carry no kind
    view = draft(org, sid)["charter"]
    assert all(p["kind"] == "intent" and p["details"] == [] for p in view["problems"])
    assert [len(l["ids"]) for l in view["lists"]] == [3, 0, 0, 0]
    assert C.clean_together({"clusters": CLUSTERS}, C.load_charter_settings())[0]["kind"] == "intent"


def test_a_kind_the_charter_does_not_know_is_refused(world):
    org, sid, _ = ready(world, result=False)
    put_result(world, "co-a", sid, [{**BY_KIND[0], "kind": "wish"}])
    assert org.post(f"{BASE}/sessions/{sid}/charter", json={"confirm": True}).status_code in (409, 422)


def test_the_download_shows_the_four_lists_with_their_priorities(world):
    org, sid = signed(world, BY_KIND)
    files = {f["format"]: f["content"] for f in org.get(f"{BASE}/sessions/{sid}/charter/download").json()["files"]}
    for body in files.values():
        assert [body.index(h) for h in HEADINGS] == sorted(body.index(h) for h in HEADINGS)
        for p in BY_KIND:
            assert p["title"] in body
        assert "The finance team" in body and "Central bank decisions" in body and "Funding headroom" in body
    assert "Should" in files["markdown"] and "Could" in files["markdown"]


def test_the_download_of_a_charter_with_empty_lists_says_none_were_raised(world):
    org, sid = signed(world, CLUSTERS)
    html = {f["format"]: f["content"] for f in org.get(f"{BASE}/sessions/{sid}/charter/download").json()["files"]}["html"]
    assert all(h in html for h in HEADINGS) and html.count(X.NONE_RAISED) == 3


def test_the_hand_off_keeps_problems_and_adds_the_new_lists_as_extra_keys(world):
    org, sid = signed(world, BY_KIND)
    rec = read_outcome(world.plane("co-a"), SessionStore(world.plane("co-a")).get(sid)["outcome_id"])
    assert [p["title"] for p in rec["problems"]] == ["Know our funding headroom"]  # what module 2 reads as problems is unchanged
    assert [p["title"] for p in rec["pain_points"]] == ["The meeting pack takes two days"]
    assert [p["title"] for p in rec["future_signals"]] == ["Rate moves and funding cost"]
    assert [p["title"] for p in rec["levers"]] == ["How fast we commit"]
    assert rec["pain_points"][0]["details"] == BY_KIND[1]["details"] and rec["levers"][0]["priority"] == "could"
    assert not any("kind" in p for p in rec["problems"])


def test_an_old_signed_charter_still_hands_on_the_same_record(world):
    org, sid = signed(world, CLUSTERS)
    rec = read_outcome(world.plane("co-a"), SessionStore(world.plane("co-a")).get(sid)["outcome_id"])
    assert len(rec["problems"]) == 3 and rec["pain_points"] == rec["future_signals"] == rec["levers"] == []
