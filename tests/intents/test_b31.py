"""B31: admin views (spec 48). Fake requests on a plane in a temporary folder; no server."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from sh_platform.intents import admin, store
from sh_platform.plane import PlaneStore

NOW = datetime.now(timezone.utc)
SECRET = ["SECRET-NOTE", "acct-rater", "SEALED-TEXT", "TOKEN-HASH", "ANON-NAME"]


def iso(days: float) -> str:
    return (NOW + timedelta(days=days)).isoformat()


def person(name: str, acct: str | None = None) -> dict:
    return {"account_id": acct or f"a-{name.lower()}", "name": name}


def rec(n: int, type_="problem", state="open", ends=5, areas=("ops",), ratings=None, closure=None, sponsor=None, title=None, extended=0):
    return {
        "id": f"{store.PREFIX[type_]}-{n:032x}", "type": type_, "title": title or f"Intent {n}", "purpose": f"Purpose {n}", "created_by": "a-janet",
        "created_at": iso(-20), "company": "acme", "areas": list(areas),
        "people": {"organiser": person("Janet"), "sponsor": sponsor, "decider": None, "owner": None, "reporter": None,
                   "participants": [person("Aaron")], "advisers": [], "affected": [], "observers": []},
        "state": state, "time_box": {"starts": iso(-10), "ends": iso(ends), "extended_by": [{"by": "a-janet", "at": iso(-3), "reason": "SECRET-NOTE"}] * extended},
        "stages": [{"key": "wall", "state": "open", "opened_at": iso(-10), "closed_at": None}],
        "outcome": {"kind": type_, "what": "SEALED-TEXT"}, "closure": closure or {}, "ratings": ratings or [], "links": {"from": None, "to": [], "build": None},
        "share": {"link": None, "who_may_open": [{"person_id": "p1", "token_hash": "TOKEN-HASH", "revoked_at": None}]},
        "start_answers": {"q": "SEALED-TEXT"}, "history": [], "event_count": 0,
    }


def closed(n, ratings=None, type_="decision", late=False, **kw):
    cl = {"closed_by": "a-janet", "closed_at": iso(-1 if late else -4), "summary": "=cmd|' /C calc'!A0", "what_came_out": "Chose the second option\nmore text",
          "next": [{"kind": "backlog", "ref": None, "reason": "later"}]}
    return rec(n, type_, "closed", ends=-2, closure=cl, ratings=ratings, **kw)


@pytest.fixture
def world(tmp_path):
    plane = PlaneStore(tmp_path).create("acme")
    accounts = {"a-janet": {"display_name": "Janet Shaw"}}
    ent = SimpleNamespace(company=lambda c: {"name": "Acme"} if c == "acme" else None, switches=lambda c: {"centres": {"intent": True}},
                          list_companies=lambda: [{"company_id": "acme"}])

    def req(roles=("company_admin",), **q):
        return SimpleNamespace(query_params=q, app=SimpleNamespace(state=SimpleNamespace(
            account_store=SimpleNamespace(get=accounts.get), entitlements=ent, settings=SimpleNamespace(data_root=tmp_path))),
            state=SimpleNamespace(account_id="a-admin", company_id="acme", roles=list(roles)))
    return plane, req


def put(plane, *recs):
    for r in recs:
        store.create_intent(plane, r)


def call(fn, request, plane=None):
    return fn(request, plane or admin.vis._plane(request))


def test_table_filters_counts_and_overdue(world):
    plane, req = world
    draft = rec(9, state="draft")
    put(plane, rec(1), rec(2, "initiative", ends=-3, extended=1, areas=()), rec(3, ends=-14), closed(4), draft,
        rec(5, state="cancelled", closure={"closed_at": iso(-1), "cancel_reason": "gone", "cancelled_by_role": "company_admin"}))
    out = call(admin._list, req())
    assert out["counts"] == {"open": 1, "overdue": 2, "closed": 1, "cancelled": 1, "total": 5}  # no draft
    assert {i["id"] for i in out["items"]}.isdisjoint({draft["id"]})
    assert call(admin._list, req(type="initiative"))["counts"]["total"] == 1
    assert call(admin._list, req(area="none"))["items"][0]["title"] == "Intent 2"
    assert call(admin._list, req(q="intent 3"))["counts"]["total"] == 1
    assert call(admin._list, req(state="cancelled"))["items"][0]["cancelled_by_admin"] is True
    assert call(admin._list, req(organiser="Janet"))["counts"]["total"] == 5
    over = call(admin._list, req(overdue="1"))
    assert [i["title"] for i in over["items"]] == ["Intent 3", "Intent 2"]  # most overdue first
    assert over["items"][0]["clock"]["text"].startswith("Overdue by") and "extended once" in over["north"]
    assert over["tabs"]["overdue"] == 2


def test_unrated_list_and_ratings_rule(world):
    plane, req = world
    rated = [{"by": "acct-rater", "score": s, "note": "SECRET-NOTE"} for s in (5, 4, 3)]
    put(plane, closed(1), closed(2, ratings=[{"by": "anonymous", "score": 2}]), closed(3, ratings=rated), closed(4, type_="pulse"))
    out = call(admin._list, req(unrated="1"))
    assert [i["title"] for i in out["items"]] == ["Intent 1"]  # an anonymous rating counts; a check-in is never rated
    assert out["reminder_note"] == "No reminder was sent."
    rows = {i["title"]: i["rating"] for i in call(admin._list, req())["items"]}
    assert rows["Intent 3"]["mean"] == 4.0 and rows["Intent 2"]["mean"] is None and rows["Intent 2"]["count"] == 1
    assert rows["Intent 4"]["by_design"] is True


def test_csv_register_has_no_secret_and_protects_formulas(world):
    plane, req = world
    put(plane, closed(1, ratings=[{"by": "acct-rater", "score": 5, "note": "SECRET-NOTE"}], title="=HYPERLINK(1)", sponsor=person("Daniel")),
        rec(2, state="cancelled", closure={"closed_at": iso(-1), "cancel_reason": "+gone", "cancelled_by_role": "company_admin"}), rec(3))
    out = call(admin._register, req())
    assert out["columns"][0] == "id" and len(out["rows"]) == 2  # closed and cancelled only
    text = json.dumps(out)
    assert not [s for s in SECRET if s in text]
    row = next(r for r in out["rows"] if r["state"] == "closed")
    assert row["title"].startswith("'=") and row["summary"].startswith("'=") and row["sponsor"] == "Daniel"
    assert row["rating_count"] == "1" and row["rating_mean"] == "" and row["next"] == "backlog" and row["closed_in_time"] == "yes"
    assert next(r for r in out["rows"] if r["state"] == "cancelled")["cancel_reason"] == "'+gone"
    assert list(row) == admin.CSV_COLUMNS


def test_nothing_secret_in_any_admin_or_control_answer(world):
    plane, req = world
    put(plane, closed(1, ratings=[{"by": "acct-rater", "score": 5, "note": "SECRET-NOTE"}]), rec(2, extended=1))
    for out in (call(admin._list, req()), call(admin._counters, req()), {"rows": admin._existence(plane, NOW)}):
        assert not [s for s in SECRET if s in json.dumps(out)], out


def test_cancel_logs_reason_and_refuses_closed(world):
    plane, req = world
    a, b = rec(1), closed(2)
    put(plane, a, b)
    assert admin.admin_cancel(req(), plane, a["id"], "   ").status_code == 400
    assert admin.admin_cancel(req(), plane, b["id"], "why").status_code == 409
    assert admin.admin_cancel(req(), plane, "ini-" + "0" * 32, "why").status_code == 404
    assert admin.admin_cancel(req(), plane, a["id"], "  Organiser has left  ") == {"id": a["id"], "state": "cancelled"}
    saved = store.read_intent(plane, a["id"])
    cl = saved["state"], saved["closure"]
    assert cl[0] == "cancelled" and cl[1]["cancel_reason"] == "Organiser has left" and cl[1]["cancelled_by_role"] == "company_admin"
    assert cl[1]["closed_by"] == "a-admin" and "summary" not in cl[1]
    events = [json.loads(x) for x in plane.path("intents", a["id"], "events.jsonl").read_text().splitlines()]
    assert events[0]["kind"] == "cancelled_by_admin" and "Organiser has left" not in json.dumps(events)
    assert admin.admin_cancel(req(), plane, a["id"], "again").status_code == 409
    assert admin._rows(req(), plane)[0] is not None


def test_non_admin_is_refused(world):
    plane, req = world
    for roles in (("participant",), ("sponsor",), ("super_admin",)):
        assert admin.get_admin_list(req(roles)).status_code == 403
        assert admin.get_intents_settings(req(roles)).status_code == 403


def test_super_admin_sees_existence_only_and_titles_private(world):
    plane, req = world
    put(plane, rec(1, title="Quiet title", ends=-3), closed(2, ratings=[{"by": "acct-rater", "score": 5, "note": "SECRET-NOTE"}]), rec(3, state="draft"))
    sa = req(("super_admin",), company_id="acme")
    sa.state.company_id = "other"
    rows = admin.get_control_companies_by_company_id_intents("acme", sa)["rows"]
    assert len(rows) == 2 and {r["title"] for r in rows} == {"Quiet title", "Intent 2"}
    assert set(rows[0]) == {"id", "title", "title_private", "type", "state", "areas", "people_count", "opened", "ends", "clock", "bucket"}
    text = json.dumps(rows)
    assert not [s for s in SECRET + ["Janet", "Purpose", "Chose the second", "Aaron"] if s in text]
    summary = admin.get_control_intents_summary(sa)
    assert summary["overdue"] == 1 and summary["by_type"]["problem"]["open"] == 1 and summary["by_type"]["decision"]["closed"] == 1
    assert summary["titles_private"] is False and summary["total"] == 2
    # the company admin turns titles private on; the super admin then gets no title in the answer at all
    admin._save_settings(plane, {"titles_private": True}, "Janet")
    hidden = admin.get_control_companies_by_company_id_intents("acme", sa)["rows"]
    assert all(r["title"] is None and r["title_private"] for r in hidden) and "Quiet title" not in json.dumps(hidden)
    s2 = admin.get_control_intents_summary(sa)
    assert s2["titles_private"] is True and s2["centre_use"]["scope"] == "counts" and len(s2["centre_use"]["months"]) == 6
    assert not [s for s in SECRET + ["Quiet title", "Intent 2", "Janet", "Purpose"] if s in json.dumps(s2)]
    assert admin.get_control_companies_by_company_id_intents("acme", req(("company_admin",))).status_code == 404
    assert admin.get_control_intents_summary(req(("company_admin",))).status_code == 403
    assert admin.get_control_companies_by_company_id_intents("nope", sa).status_code == 404


def test_settings_read_and_write(world):
    plane, req = world
    s = admin.read_settings(plane)
    assert s["time_box_days"]["initiative"] == 10 and s["time_box_overrides"] == {} and s["titles_private"] is False
    assert s["affected_default"] is False and s["opportunity"] == {**{k: None for k in admin.OPPORTUNITY_KEYS}, "scan": None, "min_confidence_to_show": None}
    admin._save_settings(plane, {"time_boxes": {"initiative": 6}, "titles_private": True, "affected_default": True, "opportunity": {"window_days": 14}}, "Janet")
    s = admin.read_settings(plane)
    assert s["time_box_days"]["initiative"] == 6 and s["time_box_days"]["problem"] == 5 and s["titles_private"] is True
    assert s["affected_default"] is True and s["opportunity"]["window_days"] == 14 and s["opportunity"]["drift_periods"] is None
    view = admin._settings_view(plane)["time_boxes"]["initiative"]
    assert view == {"title": "Initiative", "days": 6, "catalogue": 10, "changed": True, "stages_total": 10}
    admin._save_settings(plane, {"time_boxes": {"initiative": None}}, "Janet")  # back to the catalogue
    assert admin.read_settings(plane)["time_box_overrides"] == {}
    for bad in ({"time_boxes": {"initiative": 0}}, {"time_boxes": {"pulse": 3}}, {"time_boxes": {"problem": True}}, {"titles_private": "yes"},
                {"opportunity": {"nope": 1}}):
        with pytest.raises(ValueError):
            admin._save_settings(plane, bad, "Janet")
    put_resp = admin.put_intents_settings({"time_boxes": {"decision": 3}}, req())
    assert put_resp["time_boxes"]["decision"]["days"] == 3
    assert admin.put_intents_settings({"time_boxes": {"decision": 0}}, req()).status_code == 400


def test_counters(world):
    plane, req = world
    put(plane, rec(1), rec(2, ends=-3), rec(3, areas=()), closed(4, areas=("ops", "tax")))
    out = call(admin._counters, req())
    cell = {r["area"]: r["types"] for r in out["rows"]}
    assert cell["ops"]["problem"] == {"open": 1, "overdue": 1, "closed": 0, "cancelled": 0}
    assert cell["ops"]["decision"]["closed"] == 1 and cell["tax"]["decision"]["closed"] == 1 and cell["none"]["problem"]["open"] == 1
    assert out["totals"]["decision"]["total"] == 1 and out["no_area"] == 1 and out["untagged"] is None


def test_a_seed_intent_with_no_title_reads_type_and_date_never_blank(world):
    plane, req = world
    r = rec(7)
    r["title"] = ""
    put(plane, r)
    row = call(admin._list, req(), plane)["items"][0]
    assert row["title"].startswith("Problem, started ") and row["title"] != "Problem, started "
    sa = req(("super_admin",), company_id="acme")
    seen = admin.get_control_companies_by_company_id_intents("acme", sa)["rows"][0]
    assert seen["id"] == r["id"] and seen["title"].startswith("Problem, started ")
    admin._save_settings(plane, {"titles_private": True}, "Janet")  # private stays private: no fallback leaks a title
    assert admin.get_control_companies_by_company_id_intents("acme", sa)["rows"][0]["title"] is None
