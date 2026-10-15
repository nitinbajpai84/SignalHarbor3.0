"""B05: the Intent Centre home (spec 04) and first run (spec 18), on build_home directly."""
from datetime import datetime, timezone

from sh_platform.intents import home, measures, visibility
from sh_platform.profile.view import Viewer

NOW = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)  # a Wednesday


def ctx(acct: str, areas=(), admin=False) -> dict:
    roles = frozenset({"company_admin"} if admin else {"participant"})
    return {"viewer": Viewer(acct, roles, False, acct), "vctx": visibility.Context(frozenset(areas)), "admin": admin,
            "areas": list(areas), "now": NOW, "today": NOW.date(), "tz": timezone.utc, "names": lambda p: (p or {}).get("name", ""),
            "area_name": lambda a: "Company-wide" if a == home.COMPANY_WIDE else a.capitalize()}


def rec(i: str, state="open", areas=("finance",), by="janet", **kw) -> dict:
    r = {"id": i, "type": "initiative", "title": f"Intent {i}", "state": state, "areas": list(areas), "created_by": by,
         "people": {"organiser": {"account_id": by, "name": by.capitalize()}, "participants": []},
         "time_box": {"starts": "2026-10-01T00:00:00Z", "ends": "2026-10-14T00:00:00Z", "extended_by": []},
         "stages": [{"key": "think_unfiltered", "state": "open" if state != "draft" else "waiting", "opened_at": "2026-10-01T00:00:00Z"}],
         "closure": {}, "ratings": [], "outcome": {}, "links": {}}
    r.update(kw)
    return r


def lane_ids(out: dict) -> dict:
    return {l["id"]: [c["id"] for c in l["cards"]] for l in out["lanes"]}


def test_lanes_follow_the_viewer_areas_then_company_wide():
    recs = [rec("a", areas=("finance",)), rec("b", areas=("operations",)), rec("c", areas=("finance", "operations"))]
    out = home.build_home(recs, ctx("aaron", areas=("finance",)))
    assert [l["id"] for l in out["lanes"]] == ["finance", "company-wide"]
    assert lane_ids(out)["finance"] == ["a", "c"]  # b is in an area Aaron is not tagged to: absent
    both = home.build_home(recs, ctx("katie", areas=("finance", "operations")))
    assert lane_ids(both) == {"finance": ["a", "c"], "operations": ["b", "c"], "company-wide": []}
    also = [c for c in both["lanes"][1]["cards"] if c["id"] == "c"][0]
    assert also["also_in"] == "Finance"  # the second card says where it already is
    assert both["cards"][0]["days"] == "5 days left" and both["cards"][0]["stage"] == "Think unfiltered"


def test_a_draft_reaches_only_its_starter_admin_included():
    recs = [rec("d", state="draft", by="janet"), rec("o")]
    starter = home.build_home(recs, ctx("janet", areas=("finance",)))
    assert lane_ids(starter)["drafts"] == ["d"] and "d" not in lane_ids(starter)["finance"]  # "Your drafts" once, not also in the area lane
    draft = [c for c in starter["cards"] if c["id"] == "d"][0]
    assert draft["stage"] == "Not started" and draft["days"] == "Time box starts when opened" and draft["your_role"] == "Organiser"
    for other in (ctx("grace", admin=True), ctx("aaron", areas=("finance",))):
        out = home.build_home(recs, other)
        assert all(c["id"] != "d" for c in out["cards"])


def hc(recs: list[dict]) -> dict:
    """B33's home counters over these records, as the route asks for them."""
    tz, closed = timezone.utc, [r for r in recs if r["state"] == "closed" and r["type"] != "pulse"]
    return {"M01": measures.m01(recs, measures.months("1m", tz, NOW), tz), "M02": measures.m02(closed, measures.months("1m", tz, NOW), tz),
            "M08": measures.m08(recs, measures.months("quarter", tz, NOW), tz), "M13": measures.m13(closed, measures.months("6m", tz, NOW), tz)}


def test_counters_never_read_zero_without_data():
    by = {c["key"]: c for c in home.counters(hc([rec("a")]), False)}
    assert by["M01"]["value"] == "1"  # opened this month: a real count
    for k in ("M02", "M13", "M08"):
        assert by[k]["value"] == "Not available yet" and by[k]["note"].startswith("Missing:")
    nothing = home.counters(None, False)  # the measures did not load
    assert {c["value"] for c in nothing} == {"Not available yet"} and nothing[0]["note"] == "Missing: the measures did not load"
    empty = home.build_home([], ctx("aaron", areas=("finance",)))
    assert empty["counters"] == [] and empty["screen"] == "first_run" and empty["subline"] == "No intents yet"


def test_counters_count_closed_and_ratings_from_three():
    closed = [rec(str(i), state="closed", closure={"closed_at": "2026-10-03T00:00:00Z"},
                  ratings=[{"by": "anonymous", "score": 4, "note": "secret"}]) for i in range(2)]
    late = rec("late", state="closed", closure={"closed_at": "2026-10-20T00:00:00Z"}, ratings=[{"score": 5}])
    by = {c["key"]: c for c in home.counters(hc(closed + [late]), False)}
    assert by["M02"]["value"] == "2 of 3"
    assert by["M13"]["value"] == "Initiative 4.3 from 3 ratings"  # per type (spec 19)
    two = {c["key"]: c for c in home.counters(hc(closed), False)}
    assert two["M13"]["value"] == "Fewer than three ratings" and two["M13"]["note"].startswith("2 ratings")
    page = home.build_home(closed + [late], {**ctx("aaron", areas=("finance",)), "measures": hc(closed + [late])})
    assert "secret" not in str(page)  # notes never reach the page


def test_no_areas_and_first_run_copy():
    out = home.build_home([rec("a")], ctx("aaron"))
    assert out["screen"] == "no_areas" and out["cards"] == []
    rows = home._type_rows()
    assert [r["name"] for r in rows] == ["Initiative", "Brainstorm", "Weekly check-in", "Problem", "Decision"]
    assert rows[0]["chip"] == "10 working days" and rows[2]["chip"] == "One week, repeats"
    assert home._suggestions(None)["line"].startswith("No industry knowledge is available yet for this industry.")


def test_past_rows_newest_first_with_cancel_reason():
    recs = [rec("x", state="closed", closure={"closed_at": "2026-09-01T00:00:00Z", "one_liner": "Done"}),
            rec("y", state="cancelled", closure={"closed_at": "2026-10-02T00:00:00Z", "cancel_reason": "No longer needed"})]
    out = home.build_home(recs, ctx("aaron", areas=("finance",)))
    assert [(p["id"], p["one_liner"]) for p in out["past"]] == [("y", "Cancelled: No longer needed"), ("x", "Done")]
    assert out["cards"] == []


def test_company_wide_and_area_names_reach_the_viewer():
    c = {**ctx("aaron", areas=("finance",)), "area_id": lambda a: a.strip().lower()}
    recs = [rec("n", areas=("Finance",)), rec("w", areas=("company-wide",), by="janet"), rec("dw", state="draft", areas=("company-wide",)),
            rec("nd", state="draft", areas=(), by="aaron")]
    out = home.build_home(recs, c)
    ids = lane_ids(out)
    assert ids["finance"] == ["n"] and ids["company-wide"] == ["w"]  # a name-spelled area joins its lane; a draft is never company-wide
    assert ids["drafts"] == ["nd"]  # the starter's own area-less draft sits in "Your drafts"
    assert [l["id"] for l in out["lanes"]].count("drafts") == 1


def test_one_company_wide_lane_named_on_group_and_clamped_past():
    low = lambda a: a.strip().lower()  # noqa: E731  the live area_id also maps names to ids and company-wide in any case
    c = {**ctx("aaron", areas=("finance",)), "area_id": low}
    recs = [rec("a", areas=("Company-Wide",)), rec("b", areas=("company-wide",)), rec("c", areas=("reporting",), people={"organiser": {"account_id": "janet", "name": "Janet"}, "participants": [{"account_id": "aaron", "name": "Aaron"}]}),
            rec("f", state="closed", closure={"closed_at": "2026-10-09T00:00:00Z", "one_liner": "Future"}),
            rec("g", state="closed", closure={"closed_at": "2026-10-06T00:00:00Z", "one_liner": "Past"})]
    out = home.build_home(recs, c)
    names = [l["name"] for l in out["lanes"]]
    assert names.count("Company-wide") == 1 and "Named on" in names and "reporting" not in names
    assert lane_ids(out)["company-wide"] == ["a", "b"] and lane_ids(out)["named"] == ["c"]
    assert all(p["date"] <= "2026-10-07" for p in out["past"]) and out["past"][0]["id"] == "f"  # clamped to today, so it still sorts first


def test_card_days_come_from_the_stage_clock():
    from sh_platform.intents import clock
    r = rec("d", time_box={"starts": "2026-10-01T00:00:00Z", "ends": "2026-10-09T17:00:00Z", "extended_by": []})
    card = home.build_home([r], ctx("aaron", areas=("finance",)))["cards"][0]
    want = clock.clock(clock.parse(r["time_box"]["starts"]), clock.parse(r["time_box"]["ends"]), NOW)["words"]
    assert card["days"] == want == "3 days left"  # the old date count said 2
    late = rec("l", time_box={"starts": "2026-10-01T00:00:00Z", "ends": "2026-10-06T10:00:00Z", "extended_by": []}, type="pulse")
    assert home.build_home([late], ctx("aaron", areas=("finance",)))["cards"][0]["days"] == "Ended Tuesday"


def test_rating_tile_is_per_type_and_box_share_skips_no_end_date():
    mk = lambda i, t, n: rec(i, state="closed", type=t, closure={"closed_at": "2026-10-03T00:00:00Z"}, ratings=[{"score": 4}] * n)  # noqa: E731
    recs = [mk("a", "initiative", 3), mk("b", "problem", 2)]
    by = {c["key"]: c for c in home.counters(hc(recs), False)}
    assert by["M13"]["value"] == "Initiative 4.0 from 3 ratings"  # the Problem type has two: not averaged, not pooled
    only = {c["key"]: c for c in home.counters(hc([mk("c", "initiative", 1), mk("d", "problem", 2)]), False)}
    assert only["M13"]["value"] == "Fewer than three ratings"
    open_end = rec("n", state="closed", closure={"closed_at": "2026-10-03T00:00:00Z"}, time_box={"starts": "2026-10-01", "ends": None})
    ok = rec("o", state="closed", closure={"closed_at": "2026-10-03T00:00:00Z"})
    assert {c["key"]: c for c in home.counters(hc([open_end, ok]), False)}["M02"]["value"] == "1 of 1"
