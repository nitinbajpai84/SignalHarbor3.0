"""B36: data-backed opportunities (spec 56). The Watcher's patterns with thresholds set and unset, the record states, who may act, visibility,
and that no agent ever opens an intent. Synthetic data in a temporary company space; North's judgement is stubbed."""
import json
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.build import opportunity_watch as watch
from sh_platform.intents import opportunities as opp
from sh_platform.plane import PlaneStore
from sh_platform.profile import areas as areas_store

ACCTS = {"harvey": {"display_name": "Harvey Rowley"}, "katie": {"display_name": "Katie"}, "janet": {"display_name": "Janet Shaw"}, "mei": {"display_name": "Mei Ling"}}
ROLES = {"harvey": "owner", "katie": "analyst", "janet": "company_admin", "mei": "participant"}
YES = {"fits": True, "why": "It crosses a source, a process step and a measure.", "confidence": "fairly_sure", "at": "x",
       "start_answers": {"goal": {"value": "Stop late files", "mark": "guessed", "by": "North", "from": "opp-0001"}}}
NO = {"fits": False, "why": "This reads as a Problem.", "confidence": "not_sure", "start_answers": {}, "at": "x"}
UNSET = {"late_arrivals": None, "drift_periods": None, "checkin_weeks": None}


@pytest.fixture
def world(tmp_path, monkeypatch):
    plane = PlaneStore(tmp_path).create("acme")
    app = FastAPI()
    app.include_router(opp.router)
    pack = SimpleNamespace(section=lambda n: {"kpis": [{"id": "K12", "name": "Stale-valuation share"}]})
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = SimpleNamespace(get=ACCTS.get, in_company=lambda c: [])
    app.state.entitlements = SimpleNamespace(company=lambda c: {"industry": "x"})
    app.state.packs = SimpleNamespace(load=lambda i: pack)

    @app.middleware("http")
    async def who(request, call_next):
        acct = request.headers.get("x-acct", "harvey")
        request.state.account_id, request.state.roles, request.state.company_id = acct, [ROLES[acct]], "acme"
        return await call_next(request)

    monkeypatch.setattr(opp, "judge", lambda request, plane, rec: YES)
    monkeypatch.setattr(watch, "thresholds", lambda plane: dict(UNSET))
    return plane, TestClient(app)


def H(who):
    return {"x-acct": who}


RAISE = {"title": "Monday price file", "noticed": "The price file is late most Mondays.", "touches": {"measures": ["K12"], "sources": ["custodian_prices"]},
         "evidence": {"text": "Same manual override each Monday", "source": {"kind": "week_item", "ref": "ops/weeks/2026-W40#i2"}}}


def raised(c, who="harvey", **kw):
    r = c.post("/api/intents/opportunities", json={**RAISE, **kw}, headers=H(who))
    assert r.status_code == 201, r.text
    return r.json()


def seed_runs(plane, n=4):
    pipes = plane.path("build", "pipelines")
    pipes.mkdir(parents=True, exist_ok=True)
    (pipes / "custodian_prices.json").write_text(json.dumps({"source": "custodian_prices", "marts": ["gold.k12"], "owner": "Harvey"}))
    days = ["2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05"][:n]
    plane.path("warehouse").mkdir(parents=True, exist_ok=True)
    plane.path("warehouse", "runs.json").write_text(json.dumps({"runs": [{"source": "custodian_prices", "started": f"{d}T07:00:00+00:00", "status": "late", "on_time": False} for d in days]}))


def test_thresholds_unset_notice_nothing_and_say_so(world):
    plane, c = world
    seed_runs(plane)
    body = c.get("/api/intents/opportunities", headers=H("harvey")).json()
    assert body["opportunities"] == [] and body["thresholds"]["set"] is False and body["counters"] is None
    assert "Not available yet" in body["thresholds"]["message"]
    assert c.get("/api/intents/opportunities", headers=H("janet")).json()["counters"]["picked_up"] is None
    assert watch.detect(plane, date(2026, 10, 7), dict(UNSET)) == []


def test_thresholds_set_draft_a_traced_record_once(world, monkeypatch):
    plane, c = world
    seed_runs(plane)
    monkeypatch.setattr(watch, "thresholds", lambda p: {**UNSET, "late_arrivals": 4})
    one = c.get("/api/intents/opportunities", headers=H("harvey")).json()["opportunities"]
    assert len(one) == 1 and one[0]["state"] == "noticed" and one[0]["noticed_by"] == "The operations monitor"
    n = one[0]["pattern"]["numbers"][0]
    assert n["value"] == 4 and n["trace"]["kind"] == "run"
    assert one[0]["touches"] == {"measures": [{"id": "K12", "name": "Stale-valuation share"}], "processes": [], "sources": ["custodian_prices"]}
    assert len(c.get("/api/intents/opportunities", headers=H("harvey")).json()["opportunities"]) == 1  # the same pattern is never opened twice
    assert watch.detect(plane, date(2026, 10, 7), {**UNSET, "late_arrivals": 6}) == []  # a higher threshold finds nothing


def test_checkin_pattern_ignores_anonymous_items(world):
    plane, _ = world
    d = plane.path("intents", "ops")
    (d / "weeks").mkdir(parents=True)
    (d / "intent.json").write_text(json.dumps({"id": "ops", "type": "pulse", "state": "open", "areas": []}))
    for wk in ("2026-W38", "2026-W39", "2026-W40"):
        items = [{"id": "i1", "by": "a-1", "kind": "broke", "text": "Monday price reconciliation redone"},
                 {"id": "i2", "by": "anonymous", "kind": "broke", "text": "Secret thing"}, {"id": "i3", "by": "anonymous", "kind": "broke", "text": "Secret thing"}]
        (d / "weeks" / f"{wk}.json").write_text(json.dumps({"week_key": wk, "items": items}))
    got = watch.detect(plane, date(2026, 10, 7), {**UNSET, "checkin_weeks": 3})
    assert len(got) == 1 and got[0]["pattern"]["numbers"][0]["value"] == 3 and "Secret" not in json.dumps(got)


def test_raise_needs_a_touch_and_a_role(world):
    _, c = world
    assert c.post("/api/intents/opportunities", json={**RAISE, "touches": {}}, headers=H("harvey")).status_code == 422
    assert c.post("/api/intents/opportunities", json={**RAISE, "title": ""}, headers=H("harvey")).json()["message"] == "A title is needed."
    assert c.post("/api/intents/opportunities", json=RAISE, headers=H("janet")).status_code == 403
    r = raised(c)  # evidence given and North says yes: proposed
    assert (r["state"], r["judgement"]["fits"], r["noticed_by"]) == ("proposed", True, "Harvey Rowley")
    assert [h["action"] for h in r["history"]][:3] == ["noticed", "evidence_supports", "under_review"]


def test_analyst_disputes_and_north_rejudges(world, monkeypatch):
    _, c = world
    r = raised(c)
    url = f"/api/intents/opportunities/{r['id']}/evidence"
    assert c.post(url, json={"text": "", "kind": "disputes"}, headers=H("katie")).json()["message"] == "Give a reason for the dispute."
    monkeypatch.setattr(opp, "judge", lambda request, plane, rec: NO)
    d = c.post(url, json={"text": "The late file is already fixed", "kind": "disputes"}, headers=H("katie")).json()
    assert d["state"] == "under_review" and d["judgement"]["fits"] is False and d["evidence"][-1]["kind"] == "disputes" and d["evidence"][-1]["by"] == "Katie"
    assert c.post(url, json={"text": "x", "kind": "supports"}, headers=H("janet")).status_code == 403


def test_owner_parks_dismisses_and_brings_back_with_reasons(world):
    _, c = world
    r = raised(c)
    url = f"/api/intents/opportunities/{r['id']}/state"
    assert c.post(url, json={"action": "park", "reason": "Wait"}, headers=H("harvey")).json()["message"] == "A review date is needed."
    assert c.post(url, json={"action": "park", "reason": "Wait", "review_date": "2026-13-40"}, headers=H("harvey")).status_code == 422
    assert c.post(url, json={"action": "dismiss", "reason": ""}, headers=H("harvey")).status_code == 422
    assert c.post(url, json={"action": "park", "reason": "Wait", "review_date": "2026-12-01"}, headers=H("katie")).status_code == 403
    p = c.post(url, json={"action": "park", "reason": "Wait for the renewal", "review_date": "2026-12-01"}, headers=H("harvey")).json()
    assert p["state"] == "parked" and p["parked"]["reason"] == "Wait for the renewal" and p["parked"]["by"] == "Harvey Rowley" and p["can"]["bring_back"]
    assert c.post(url, json={"action": "pick_up"}, headers=H("harvey")).status_code == 409
    assert c.post(url, json={"action": "bring_back"}, headers=H("harvey")).json()["state"] == "proposed"  # North says yes again
    dm = c.post(url, json={"action": "dismiss", "reason": "Not worth it"}, headers=H("harvey")).json()
    assert dm["state"] == "dismissed" and dm["dismissed"]["reason"] == "Not worth it" and not dm["can"]["add_evidence"]


def test_pick_up_hands_back_the_chooser_and_no_agent_opens_an_intent(world):
    plane, c = world
    r = raised(c)
    url = f"/api/intents/opportunities/{r['id']}/state"
    assert c.post(url, json={"action": "pick_up"}, headers=H("mei")).status_code == 403  # C3: a participant only taps "I feel this"
    assert c.get(f"/api/intents/opportunities/{r['id']}", headers=H("janet")).json()["can"]["pick_up"]  # C3: the admin, sponsor and analyst may pick up
    assert c.get(f"/api/intents/opportunities/{r['id']}", headers=H("katie")).json()["can"]["pick_up"]
    p = c.post(url, json={"action": "pick_up"}, headers=H("harvey")).json()
    assert p["state"] == "picked_up" and p["picked_up_by"] == "Harvey Rowley" and p["became"] is None
    assert p["start_href"] == f"/centre/intent/new?type=initiative&from={r['id']}"
    assert list(plane.path("intents").glob("*/intent.json")) == []  # nothing in the whole flow wrote an intent


def test_visibility_by_area_and_admin_sees_all(world):
    plane, c = world
    aid = areas_store.add(plane, "Operations", "operations_area", "t")
    r = raised(c, areas=[aid])  # Harvey is not tagged to the area, so it is absent for him, not a silhouette
    assert c.get(f"/api/intents/opportunities/{r['id']}", headers=H("harvey")).status_code == 404
    assert c.get(f"/api/intents/opportunities/{r['id']}", headers=H("janet")).status_code == 200
    assert c.get("/api/intents/opportunities", headers=H("harvey")).json()["opportunities"] == []
    assert len(c.get("/api/intents/opportunities", headers=H("janet")).json()["opportunities"]) == 1


def test_thresholds_come_from_the_admin_settings_shape(world, monkeypatch):
    plane, _ = world
    monkeypatch.undo()  # the real thresholds(), reading admin.read_settings()["opportunity"]
    assert watch.thresholds(plane) == UNSET
    f = plane.path("settings", "intent_centre.json")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"opportunity": {"late_same_weekday": 3, "drift_periods": 4, "checkin_items_same_step": None}}))
    assert watch.thresholds(plane) == {"late_arrivals": 3, "drift_periods": 4, "checkin_weeks": None}


def test_handler_refusals_never_use_the_guard_code(world):
    _, c = world
    r = c.post("/api/intents/opportunities", json=RAISE, headers=H("janet"))
    assert r.status_code == 403 and r.json()["error"] == "opportunity_not_your_role"


def test_watcher_titles_name_the_measure_not_its_code(world, monkeypatch):
    plane, c = world
    draft = {"title": "K12 keeps moving up", "areas": [], "touches": {"measures": ["K12"], "processes": [], "sources": ["custodian_prices"]},
             "pattern": {"text": "K12 moved up in each of the last 3 periods.", "periods": ["2026-07", "2026-08", "2026-09", "2026-10"],
                         "numbers": [{"label": "Periods moving the same way", "value": 3, "unit": "periods", "trace": {"kind": "feed", "ref": "gold.k12", "at": "2026-10"}}]}}
    monkeypatch.setattr(watch, "detect", lambda *a, **k: [draft])
    o = c.get("/api/intents/opportunities", headers=H("harvey")).json()["opportunities"][0]
    assert o["title"] == "Stale-valuation share keeps moving up" and o["pattern"]["text"].startswith("Stale-valuation share moved up")
