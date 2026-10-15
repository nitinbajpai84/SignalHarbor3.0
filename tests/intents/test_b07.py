"""B07: the time box and stage clock. Pure sums and the extend and decide rules, on a plane in a temporary folder."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from sh_platform.intents import clock
from sh_platform.plane import PlaneStore

UTC = timezone.utc
D = lambda s: datetime.fromisoformat(s).replace(tzinfo=UTC)  # noqa: E731
IID = "ini-" + "0" * 32
FRI, MON = D("2026-10-09T17:00"), D("2026-10-12T17:00")


def test_working_days_skip_the_weekend():
    assert clock.working_days(FRI, 1) == MON
    assert clock.working_days(D("2026-10-05T09:00"), 10) == D("2026-10-19T09:00")  # Monday plus ten working days
    assert clock.working_days(D("2026-10-10T10:00"), 1) == D("2026-10-13T10:00")  # a Saturday start counts from Monday
    assert clock.working_days_between(FRI, MON) == 1.0
    assert clock.working_seconds(MON, FRI) == 0


def test_days_left_and_colours():
    s, e = D("2026-10-05T09:00"), D("2026-10-19T09:00")  # ten working days
    c = clock.clock(s, e, D("2026-10-07T09:00"))
    assert (c["working_days_total"], c["working_days_left"], c["state"], c["day_of"]) == (10, 8, "on_time", 3)
    assert clock.clock(s, e, D("2026-10-12T09:00"))["state"] == "at_half"   # 5 of 10 left: 50 percent
    assert clock.clock(s, e, D("2026-10-12T09:01"))["state"] == "at_half"
    assert clock.clock(s, e, D("2026-10-15T09:00"))["state"] == "at_risk"   # 2 of 10 left: 20 percent
    assert clock.clock(s, e, D("2026-10-14T09:00"))["state"] == "at_half"   # 3 of 10 left
    last = clock.clock(s, e, D("2026-10-19T03:00"))                          # six hours left: hours, not days
    assert (last["unit"], last["hours_left"]) == ("hours", 6)


def test_overdue():
    s, e = D("2026-10-05T09:00"), D("2026-10-09T09:00")
    c = clock.clock(s, e, D("2026-10-09T12:00"))
    assert c["state"] == "overdue" and c["working_days_left"] == 0 and c["hours_left"] == -3
    assert clock.clock(s, e, D("2026-10-13T09:00"))["hours_left"] == -48  # Friday to Tuesday is two working days past
    assert clock.clock(s, e, D("2026-10-04T09:00"))["state"] == "not_started"


class Req:
    def __init__(self, plane, account, name, roles=()):
        accts = {"a-org": {"email": "janet@x.test", "display_name": "Janet"}, "a-spon": {"email": "daniel@x.test", "display_name": "Daniel"}}
        self.app = SimpleNamespace(state=SimpleNamespace(account_store=SimpleNamespace(get=accts.get)))
        self.state = SimpleNamespace(account_id=account, roles=list(roles))
        self.name, self.account = name, account


@pytest.fixture
def world(tmp_path, monkeypatch):
    plane = PlaneStore(tmp_path).create("acme")
    monkeypatch.setattr(clock, "_plane", lambda r: plane)
    monkeypatch.setattr(clock, "_viewer", lambda r: SimpleNamespace(name=r.name))
    monkeypatch.setattr(clock, "_tier", lambda request, plane, rec: None if request.account == "a-other" else "card")
    rec = {"id": IID, "type": "initiative", "title": "T", "state": "open", "created_by": "a-org",
           "people": {"organiser": {"account_id": "a-org", "name": "Janet"}, "sponsor": {"account_id": "a-spon", "name": "Daniel"},
                      "participants": [{"account_id": "a-p", "name": "Pat"}], "observers": [], "affected": [{"account_id": "a-x", "name": "Xin"}]},
           "time_box": {"starts": "2026-10-05T09:00:00+00:00", "ends": "2026-10-19T09:00:00+00:00", "extended_by": []}, "version": 1, "event_count": 0,
           "stages": [{"key": "wall", "state": "done", "opened_at": "2026-10-05T09:00:00+00:00", "closed_at": "2026-10-08T09:00:00+00:00", "due": "2026-10-08T09:00:00+00:00"},
                      {"key": "define", "state": "open", "opened_at": "2026-10-08T09:00:00+00:00", "closed_at": None, "due": "2026-10-16T09:00:00+00:00"}]}
    path = plane.path("intents", IID, "intent.json")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(rec))
    return plane, path, Req(plane, "a-org", "Janet"), Req(plane, "a-spon", "Daniel"), Req(plane, "a-p", "Pat")


NOW = D("2026-10-07T10:00")
BODY = {"days": 2, "reason": "Waiting for the glossary from Finance", "scope": "intent"}


def test_extend_needs_a_reason_and_a_listed_day_count(world):
    _, _, org, *_ = world
    assert clock.extend(org, IID, {**BODY, "reason": ""}, NOW).status_code == 422
    assert clock.extend(org, IID, {**BODY, "reason": "short"}, NOW).status_code == 422
    assert clock.extend(org, IID, {**BODY, "days": 4}, NOW).status_code == 422


def test_first_extension_alone_second_needs_the_sponsor(world):
    plane, path, org, spon, pat = world
    assert clock.extend(pat, IID, BODY, NOW).status_code == 403
    r = clock.extend(org, IID, BODY, NOW)
    assert r["extended"] and r["clock"]["extensions"]["count"] == 1
    rec = json.loads(path.read_text())
    e = rec["time_box"]["extended_by"][0]
    assert (e["by"], e["status"], e["was"]) == ("Janet", "approved", "2026-10-19T09:00:00+00:00")
    assert rec["time_box"]["ends"].startswith("2026-10-21T09:00")
    assert rec["stages"][1]["due"].startswith("2026-10-20T09:00")  # moved with the box, never past its end
    assert rec["event_count"] == 1 and (plane.path("intents", IID, "events.jsonl").read_text().count('"kind":"extended"') == 1)
    r2 = clock.extend(org, IID, BODY, NOW)                      # the second one waits for Daniel
    assert r2["pending"] and not r2["extended"]
    assert json.loads(path.read_text())["time_box"]["ends"].startswith("2026-10-21")
    assert clock.extend(org, IID, BODY, NOW).status_code == 409   # one request at a time
    assert clock.decide(org, IID, 1, {"decision": "approve"}, NOW).status_code == 403
    d = clock.decide(spon, IID, 1, {"decision": "approve"}, NOW)
    assert d["clock"]["extensions"]["count"] == 2
    assert json.loads(path.read_text())["time_box"]["ends"].startswith("2026-10-23T09:00")


def test_decline_keeps_the_end_and_the_sponsor_extends_at_once(world):
    _, path, org, spon, _ = world
    clock.extend(org, IID, BODY, NOW)
    clock.extend(org, IID, BODY, NOW)
    clock.decide(spon, IID, 1, {"decision": "decline"}, NOW)
    tb = json.loads(path.read_text())["time_box"]
    assert tb["extended_by"][1]["status"] == "declined" and tb["ends"].startswith("2026-10-21")
    assert clock.extend(spon, IID, BODY, NOW)["extended"]


def test_reasons_hidden_from_a_viewer_who_may_not_read_and_closed_cannot_extend(world):
    plane, path, org, _, pat = world
    clock.extend(org, IID, BODY, NOW)
    rec = json.loads(path.read_text())
    area = Req(plane, "a-other", "Katie")
    assert clock.build(area, rec, plane, NOW)["extensions"]["latest"]["reason"] is None
    assert "glossary" in clock.build(pat, rec, plane, NOW)["extensions"]["latest"]["reason"]
    rec["state"] = "closed"
    path.write_text(json.dumps(rec))
    assert clock.extend(org, IID, BODY, NOW).status_code == 409


# ---- F18: the clock route admits everyone the matrix lets into the intent --------------------------------------------------------

def _clock_app(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sh_platform.intents import lifecycle as L, store as S
    from sh_platform.profile import store as profile_store
    accts = {"janet": ("Janet Shaw", ["company_admin"]), "harvey": ("Harvey Rowley", ["owner"]), "marcus": ("Marcus Todd", ["analyst"]),
             "zed": ("Zed Lee", ["participant"]), "lee": ("Lee Ann", ["participant"])}
    teams = {"janet": "Strategy", "harvey": "Operations", "marcus": "Data", "zed": "Treasury", "lee": "Legal"}
    plane = PlaneStore(tmp_path).create("ardmore").ensure()
    c = lambda v: {"value": v, "mark": "stated"}  # noqa: E731
    profile_store.mutate(plane, lambda d: d["people"].update(
        {a: {"name": c(n), "team": c(teams[a]), "areas": c([teams[a]]), "account_id": c(a)} for a, (n, _) in accts.items()}))
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = SimpleNamespace(get=lambda a: {"display_name": accts[a][0], "email": a + "@x.test"} if a in accts else None,
                                              in_company=lambda _: [{"account_id": a, "display_name": n, "roles": r} for a, (n, r) in accts.items()])
    app.include_router(clock.router)

    @app.middleware("http")
    async def sign_in(request, call_next):
        who = request.headers.get("x-who", "janet")
        request.state.account_id, request.state.company_id, request.state.roles = who, "ardmore", accts[who][1]
        return await call_next(request)
    rec = L.new_record("initiative", "ardmore", L.person("janet", "Janet Shaw"), "2026-10-05T09:00:00+00:00", title="Feed", areas=["Treasury"])
    rec["state"] = "open"
    rec["people"].update(owner=L.person("harvey", "Harvey Rowley"), advisers=[L.person("marcus", "Marcus Todd")])
    rec["time_box"].update(starts="2026-10-05T09:00:00+00:00", ends="2026-10-19T09:00:00+00:00")
    return TestClient(app), S.create_intent(plane, rec)["id"]


def test_clock_route_admits_named_owner_analyst_and_card_tier_stranger_404(tmp_path):
    api, iid = _clock_app(tmp_path)
    get = lambda who: api.get(f"/api/intents/{iid}/clock", headers={"x-who": who}).status_code  # noqa: E731
    assert (get("harvey"), get("marcus"), get("janet")) == (200, 200, 200)
    assert get("zed") == 200       # same area only: the card tier sees the stage bar and clock (spec 07), never an extension's reason
    assert api.get(f"/api/intents/{iid}/clock", headers={"x-who": "zed"}).json()["extensions"]["show_reason"] is False
    assert get("lee") == 404       # other area: hidden


def test_one_wording_for_left_and_overdue():
    assert clock.overdue_words(20) == "Overdue by 20 hours" and clock.overdue_words(1) == "Overdue by 1 hour"
    assert clock.overdue_words(24) == "Overdue by 1 working day" and clock.overdue_words(50) == "Overdue by 2 working days"
    assert clock.days_words(1) == "1 day left" and clock.days_words(3) == "3 days left" and clock.days_words(-1) == "Overdue by 1 working day"
    assert clock.ends_words("Tue 10:00", True) == "Ended Tue 10:00" and clock.ends_words("Fri 17:00", False) == "Closes Fri 17:00"
    s, e = D("2026-10-05T09:00"), D("2026-10-09T09:00")
    assert clock.clock(s, e, D("2026-10-13T09:00"))["words"] == "Overdue by 2 working days"
    assert clock.clock(s, e, D("2026-10-09T03:00"))["words"] == "6 hours left"


def test_time_card_for_organiser_and_sponsor_only_when_late(world):
    plane, path, org, spon, pat = world
    late = D("2026-10-21T10:00")  # two days past the end
    card = clock.build(org, json.loads(path.read_text()), plane, late)["time_card"]
    assert card["line"] == "Time is up. Overdue by 2 working days."
    assert card["who_picks"] == "Janet picks. If Janet does not pick by Thu 22 Oct, Daniel is asked."
    assert clock.build(spon, json.loads(path.read_text()), plane, late)["time_card"] is not None
    assert clock.build(pat, json.loads(path.read_text()), plane, late)["time_card"] is None
    assert clock.build(org, json.loads(path.read_text()), plane, NOW)["time_card"] is None  # plenty of time left


def test_a_closed_intent_reads_closed_with_no_days_left():
    rec = {"state": "closed", "closure": {"closed_at": "2099-10-09T08:00:00+00:00"}, "stages": []}
    tb = {"starts": "2026-10-01", "ends": "2026-10-10"}
    c = clock.ended_part(rec, tb, D("2026-10-07T09:00"), UTC)
    assert c["words"] == "Closed Wed 7 Oct" and c["working_days_left"] == 0 and c["state"] == "closed"  # never after now
    assert clock.ended_part({**rec, "state": "cancelled", "closure": {}, "stages": [{"closed_at": "2026-10-03T00:00:00+00:00"}]}, tb, D("2026-10-07T09:00"), UTC)["words"] == "Cancelled Sat 3 Oct"


def test_frame_panels_admit_a_person_named_only_on_a_charter_role(tmp_path):
    """FX3 (R1): clock, North and the note panel decide through the one tier, so a person named only in the intent's records (a charter
    role) reads them instead of a 404; North gives them a read-only seat and the note panel says they have no part there."""
    from sh_platform.intents import affected, north, store as S
    api, iid = _clock_app(tmp_path)
    plane = PlaneStore(tmp_path).plane_for("ardmore")
    rec = S.read_intent(plane, iid)
    rec.setdefault("refs", {})["wall_session_ids"] = ["s1"]
    plane.path("intents", iid, "intent.json").write_text(json.dumps(rec))
    roles = plane.path("intents", "m1_intent", "roles", "s1.json")
    roles.parent.mkdir(parents=True, exist_ok=True)
    roles.write_text(json.dumps({"roles": {"data_owner": "lee"}}))
    api.app.include_router(north.router)
    api.app.include_router(affected.router)
    api.app.state.north_model_factory = lambda _plane: None
    api.app.state.entitlements = SimpleNamespace()
    get = lambda path, who="lee": api.get(f"/api/intents/{iid}/{path}", headers={"x-who": who})  # noqa: E731
    assert get("clock").status_code == 200 and get("clock").json()["extensions"]["show_reason"] is True
    assert get("north").status_code == 200 and get("north").json()["seat"] == "observer"
    assert get("notes").status_code == 200 and get("notes").json()["mine"]["role"] is None
    assert get("north", "zed").json()["seat"] is None  # same area only: no panel, and no refusal for the page to show


def test_a_closing_intent_reads_closing_with_its_window_and_no_stage_clock(tmp_path):
    from sh_platform.intents import store as S
    api, iid = _clock_app(tmp_path)
    plane = PlaneStore(tmp_path).plane_for("ardmore")
    rec = S.read_intent(plane, iid)
    rec["state"] = "closing"
    plane.path("intents", iid, "intent.json").write_text(json.dumps(rec))
    v = api.get(f"/api/intents/{iid}/clock").json()
    assert v["stage"] is None and v["box"]["state"] == "closing" and v["box"]["words"].startswith("Closing, ")
