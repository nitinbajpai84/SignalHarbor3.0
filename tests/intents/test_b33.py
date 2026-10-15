"""B33: centre measures (spec 19) from a fixture plane: each measure, the small-group rule, the Not available yet paths, super admin counts only."""
import json
from datetime import datetime, timezone

import pytest

from sh_platform.intents import measures as M
from sh_platform.intents.store import PREFIX
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer

NOW = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)
ADMIN = Viewer("Janet Shaw", frozenset({"company_admin"}), False, "acc-admin")
AARON = Viewer("Aaron Lyle", frozenset({"participant"}), False, "acc-aaron")
_n = 0


@pytest.fixture
def plane(tmp_path):
    return PlaneStore(tmp_path / "data").create("co-test")


def put(plane, type_="problem", state="closed", opened="2026-09-01T09:00:00Z", closed="2026-09-10T09:00:00Z", ends="2026-09-15T09:00:00Z",
        ext=0, ratings=(), outcome=None, nxt=(), links=None, stages=None, people=None, **extra):
    global _n
    _n += 1
    iid = f"{PREFIX[type_]}-{_n:032x}"
    rec = {"id": iid, "type": type_, "state": state, "title": "t", "purpose": "p", "areas": [], "created_by": "acc-x",
           "people": people or {"organiser": {"account_id": "acc-x", "name": "X"}},
           "time_box": {"starts": opened, "ends": ends, "extended_by": [{"by": "x", "at": opened, "reason": "r"}] * ext},
           "stages": stages or [{"key": "s1", "state": "closed", "opened_at": opened, "closed_at": closed}],
           "outcome": outcome or {"kind": type_}, "closure": {"closed_at": closed if state in ("closed", "cancelled") else None,
                                                             "next": list(nxt)},
           "ratings": [{"by": "anonymous", "score": s} for s in ratings], "links": links or {"from": None, "to": [], "build": None}, **extra}
    d = plane.path("intents", iid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "intent.json").write_text(json.dumps(rec), encoding="utf-8")
    return iid


def get(plane, mid, viewer=ADMIN, window="6m"):
    return next(m for m in M.compute(plane, viewer, window, now=NOW)["measures"] if m["id"] == mid)


def test_empty_plane_every_measure_not_available(plane):
    put(plane, state="draft")  # drafts are excluded everywhere
    ms = M.compute(plane, ADMIN, now=NOW)["measures"]
    assert [m["id"] for m in ms] == [f"M{i:02d}" for i in range(1, 16)]
    for m in ms:
        assert m["value"] is None and m["missing"].startswith("Not available yet."), m["id"]
    assert get(plane, "M01")["missing"] == "Not available yet. No intent has been opened."


def test_m01_counts_by_type_and_month_including_cancelled(plane):
    put(plane, "problem", opened="2026-09-01T09:00:00Z")
    put(plane, "decision", state="cancelled", opened="2026-10-01T09:00:00Z")
    put(plane, "problem", state="open", opened="2025-01-01T09:00:00Z")  # outside the window
    m = get(plane, "M01")
    assert m["value"] == 2 and m["by_type"] == {"problem": 1, "decision": 1} and len(m["ids"]) == 2
    assert {r["month"]: r["count"] for r in m["by_month"]}["2026-09"] == 1


def test_m02_m04_time_box_and_extensions(plane):
    put(plane, closed="2026-09-10T09:00:00Z", ends="2026-09-15T09:00:00Z")
    put(plane, closed="2026-09-20T09:00:00Z", ends="2026-09-15T09:00:00Z", ext=2)
    put(plane, "pulse")  # a check-in series is excluded from M02 to M04
    put(plane, state="cancelled")  # cancelled excluded
    m2, m4 = get(plane, "M02"), get(plane, "M04")
    assert (m2["numerator"], m2["denominator"]) == (1, 2)
    assert (m4["numerator"], m4["denominator"], m4["extensions"]) == (1, 2, 2)


def test_m03_median_working_days_and_small_group(plane):
    for _ in range(4):  # Monday to the next Monday: five working days
        put(plane, opened="2026-09-07T09:00:00Z", closed="2026-09-14T09:00:00Z")
    m = get(plane, "M03")
    assert m["value"] is None and m["small_group"] is True and m["by_type"]["problem"]["small_group"] is True
    put(plane, opened="2026-09-07T09:00:00Z", closed="2026-09-14T09:00:00Z")
    m = get(plane, "M03")
    assert m["value"] == 5.0 and m["small_group"] is False and m["by_type"]["problem"] == {"count": 5, "median": 5.0, "small_group": False}


def test_m08_build_ready_handed_and_waiting(plane):
    st = [{"key": "build_ready", "state": "closed", "opened_at": "2026-10-01T09:00:00Z", "closed_at": "2026-10-02T09:00:00Z"}]
    put(plane, "initiative", state="closing", stages=st, outcome={"kind": "initiative", "build_ready": True}, links={"from": None, "to": [], "build": "rel-1"})
    put(plane, "initiative", state="closing", stages=st, outcome={"kind": "initiative", "build_ready": True})
    put(plane, "initiative", state="closing", stages=st, outcome={"kind": "initiative", "build_ready": False})
    m = get(plane, "M08")
    assert (m["value"], m["handed"], m["waiting"]) == (2, 1, 1)


def test_m09_m14_brainstorm_became_initiative(plane):
    bra = put(plane, "brainstorm", nxt=[{"kind": "initiative", "ref": None, "reason": "r"}])
    ini = put(plane, "initiative", state="open", links={"from": bra, "to": [], "build": None})
    p = plane.path("intents", bra, "intent.json")
    rec = json.loads(p.read_text())
    rec["closure"]["next"] = [{"kind": "initiative", "ref": ini, "reason": "r"}]
    p.write_text(json.dumps(rec))
    put(plane, "brainstorm", nxt=[{"kind": "initiative", "ref": "ini-missing", "reason": "r"}])  # in m, not in n
    m9, m14 = get(plane, "M09"), get(plane, "M14")
    assert (m9["numerator"], m9["denominator"]) == (1, 2)
    assert (m14["numerator"], m14["denominator"]) == (1, 2)


def test_m10_week_fates_unresolved_problem_counts_as_nothing(plane):
    prb = put(plane, "problem", state="open")
    pul = put(plane, "pulse", state="open")
    wk = plane.path("intents", pul, "weeks")
    wk.mkdir()
    items = [{"id": "i1", "fate": "problem", "fate_ref": prb}, {"id": "i2", "fate": "problem", "fate_ref": None},
             {"id": "i3", "fate": "backlog"}, {"id": "i4", "fate": "handled"}, {"id": "i5", "fate": "nothing"}]
    (wk / "2026-W38.json").write_text(json.dumps({"week_key": "2026-W38", "items": items, "closed_at": "2026-09-18T17:00:00Z"}))
    (wk / "2026-W39.json").write_text(json.dumps({"week_key": "2026-W39", "items": items, "closed_at": None}))  # open week ignored
    m = get(plane, "M10")
    assert m["fates"] == {"problem": 1, "backlog": 1, "handled": 1, "nothing": 2} and m["denominator"] == 5
    assert m["unresolved"] == ["2026-W38/i2"] and m["missing"] == "1 problem fate has no Problem intent behind it and is counted as nothing."


def test_m11_m12_problem_and_decision_outcomes(plane):
    put(plane, "problem", outcome={"kind": "problem", "root_cause": "stale feed", "fix": {"by": "Harvey"}})
    put(plane, "problem", outcome={"kind": "problem", "root_cause": {"unknown": True}, "fix": {"by": "Harvey"}})
    put(plane, "decision", outcome={"kind": "decision", "chosen": "A", "decided_by": "Daniel", "why": "cost"})
    put(plane, "decision", outcome={"kind": "decision", "no_decision_reason": "deferred"})
    m11, m12 = get(plane, "M11"), get(plane, "M12")
    assert (m11["numerator"], m11["denominator"]) == (1, 2)
    assert (m12["numerator"], m12["denominator"]) == (1, 2)


def test_m13_ratings_from_three(plane):
    put(plane, ratings=[5, 4])
    m = get(plane, "M13")
    assert m["value"] is None and m["small_group"] is True and m["ratings"] == 2
    put(plane, ratings=[3])
    m = get(plane, "M13")
    assert (m["value"], m["ratings"], m["small_group"]) == (4.0, 3, False)


def test_m15_outcome_used_counts(plane):
    put(plane, outcome_used={"asked_at": "2026-10-01T09:00:00Z", "answer": "yes"})
    put(plane, outcome_used={"asked_at": "2026-10-01T09:00:00Z", "answer": "partly"})
    put(plane, outcome_used={"asked_at": "2026-10-01T09:00:00Z", "answer": None})
    put(plane)  # not asked: not counted
    m = get(plane, "M15")
    assert m["answers"] == {"yes": 1, "partly": 1, "no": 0, "not_answered": 1} and m["denominator"] == 3


def test_visible_scope_four_measures_and_hidden_intents_not_counted(plane):
    put(plane, people={"organiser": {"account_id": "acc-aaron", "name": "Aaron Lyle"}})
    put(plane)  # Aaron is not on it and has no area: hidden
    out = M.compute(plane, AARON, now=NOW)
    assert out["scope"] == "visible" and [m["id"] for m in out["measures"]] == ["M01", "M02", "M08", "M13"]
    assert out["measures"][0]["value"] == 1
    assert get(plane, "M01")["value"] == 2  # the company admin counts every intent


def test_home_counters_single_source(plane):
    put(plane, opened="2026-10-01T09:00:00Z", closed="2026-10-02T09:00:00Z", ends="2026-10-05T09:00:00Z")
    put(plane, opened="2026-09-01T09:00:00Z")
    h = M.home_counters(plane, ADMIN, now=NOW)
    assert set(h) == {"scope", "M01", "M02", "M08", "M13"}
    assert h["M01"]["value"] == 1 and (h["M02"]["numerator"], h["M02"]["denominator"]) == (1, 1)


def test_quarter_and_time_zone_months():
    from datetime import timedelta
    assert M.months("quarter", timezone.utc, NOW) == ["2026-10"]
    assert M.months("3m", timezone.utc, NOW) == ["2026-08", "2026-09", "2026-10"]
    late = datetime(2026, 9, 30, 20, 0, tzinfo=timezone.utc)  # already October in Hong Kong
    assert M.months("1m", timezone(timedelta(hours=8)), late) == ["2026-10"]


def test_super_admin_counts_only(plane):
    put(plane, "problem", opened="2026-09-01T09:00:00Z", ratings=[5, 5, 5])
    put(plane, "decision", state="cancelled", opened="2026-09-02T09:00:00Z", closed="2026-09-03T09:00:00Z")
    use = M.centre_use(plane, now=NOW)
    sep = next(r for r in use["months"] if r["month"] == "2026-09")
    assert sep == {"month": "2026-09", "opened": {"initiative": 0, "brainstorm": 0, "pulse": 0, "problem": 1, "decision": 1},
                   "closed": 1, "cancelled": 1}
    text = json.dumps(use)
    assert "score" not in text and "title" not in text and use["scope"] == "counts"


def test_route_refuses_super_admin():
    from types import SimpleNamespace
    req = SimpleNamespace(state=SimpleNamespace(roles=["super_admin"]))
    r = M.get_intents_measures(req)
    assert r.status_code == 403 and json.loads(r.body)["message"] == "Super admin sees counts only"


def test_window_with_no_qualifying_record_is_not_available_not_zero(plane):
    put(plane, "problem", opened="2025-01-01T09:00:00Z", closed="2025-01-05T09:00:00Z", ends="2025-01-10T09:00:00Z", ratings=[5, 5, 5],
        outcome_used={"asked_at": "2025-02-05T09:00:00Z", "answer": "yes"})
    put(plane, "decision", state="open", opened="2026-10-01T09:00:00Z")
    for mid in ("M02", "M03", "M04", "M11", "M13", "M14", "M15"):
        m = get(plane, mid)
        assert m["value"] is None and m["missing"].startswith("Not available yet."), mid
        assert m["small_group"] is False, mid
