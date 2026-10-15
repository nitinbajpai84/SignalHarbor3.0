"""B01 (spec 01): the intent record, lifecycle, index and the core routes. Synthetic people; a small app with only this router."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.intents import lifecycle as L
from sh_platform.intents import admin, records, store as S
from sh_platform.plane import PlaneStore
from sh_platform.profile import store as profile_store

CO = "ardmore"
ACCTS = {  # id: (name, roles)
    "janet": ("Janet Shaw", ["company_admin"]), "daniel": ("Daniel Kerr", ["sponsor"]), "aaron": ("Aaron Lyle", ["participant"]),
    "katie": ("Katie Rao", ["analyst"]), "harvey": ("Harvey Rowley", ["owner"]), "grace": ("Grace Ward", ["approver"]),
    "zed": ("Zed Lee", ["participant"]), "root": ("Platform", ["super_admin"]),
}


class Accounts:
    def get(self, aid):
        return {"display_name": ACCTS[aid][0]} if aid in ACCTS else None

    def in_company(self, company_id):
        return [{"account_id": a, "display_name": n, "roles": r, "disabled": False} for a, (n, r) in ACCTS.items() if a != "root"]


@pytest.fixture
def env(tmp_path):
    plane = PlaneStore(tmp_path).create(CO).ensure()
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = Accounts()
    app.state.entitlements = SimpleNamespace(company=lambda cid: {"name": "Ardmore"} if cid == CO else None)
    app.include_router(records.router)
    app.include_router(admin.router)

    @app.middleware("http")
    async def sign_in(request, call_next):
        who = request.headers.get("x-who", "janet")
        request.state.account_id, request.state.company_id, request.state.roles = who, CO, ACCTS[who][1]
        return await call_next(request)

    def person(aid, team):
        c = lambda v: {"value": v, "mark": "stated"}  # noqa: E731
        return {"name": c(ACCTS[aid][0]), "team": c(team), "areas": c([team]), "account_id": c(aid)}  # the tag decides, not the team

    profile_store.mutate(plane, lambda d: d["people"].update({"p1": person("katie", "Finance"), "p2": person("zed", "Legal")}))
    return SimpleNamespace(plane=plane, c=TestClient(app))


def call(env, who, method, path, body=None):
    return env.c.request(method, path, json=body or {}, headers={"x-who": who})


def make(env, type_="decision", **extra):
    r = call(env, "janet", "POST", "/api/intents", {"type": type_, "title": "Pick a custodian", "purpose": "Reduce fees",
                                                    "areas": ["Finance"], **extra})
    assert r.status_code == 201, r.text
    return r.json()


def go(env, rec, to, who="janet"):
    r = call(env, who, "PATCH", f"/api/intents/{rec['id']}/state", {"version": rec["version"], "to": to})
    return r


def people(env, rec, patch):
    r = call(env, "janet", "PATCH", f"/api/intents/{rec['id']}", {"version": rec["version"], "people": patch})
    assert r.status_code == 200, r.text
    return r.json()


def P(aid):
    return {"account_id": aid, "name": ACCTS[aid][0]}


def test_create_writes_ruled_record_and_index_row(env):
    rec = make(env)
    assert rec["state"] == "draft" and rec["version"] == 1 and rec["tier"] == "content"
    assert rec["people"]["organiser"] == P("janet") and rec["company"] == CO and rec["outcome"] == {"kind": "decision", "question": "", "options": [],
                                                                                                    "chosen": None, "why": ""}
    on_disk = json.loads(env.plane.path("intents", rec["id"], "intent.json").read_text())
    assert set(on_disk) <= S.KEYS and on_disk["record"] == f"intents/{rec['id']}/intent.json"
    rows = json.loads(env.plane.path("intents", "_index.json").read_text())["rows"]
    assert [r["id"] for r in rows] == [rec["id"]] and rows[0]["state"] == "draft"
    assert call(env, "janet", "POST", "/api/intents", {"type": "game"}).status_code == 400
    assert call(env, "janet", "POST", "/api/intents", {"type": "problem", "links": {"from": "ini-" + "0" * 32}}).status_code == 400
    assert call(env, "janet", "POST", "/api/intents", {"type": "problem", "extra": 1, "title": "x"}).status_code == 201  # unknown body keys never reach the file


def test_read_as_each_tier(env):
    rec = make(env, "initiative")
    # a draft: its organiser only, not even the company admin or a super admin
    assert call(env, "daniel", "GET", f"/api/intents/{rec['id']}").status_code == 404
    rec = people(env, rec, {"sponsor": P("daniel"), "participants": [P("aaron")], "affected": [P("harvey")]})
    assert go(env, rec, "open").status_code == 200
    one = lambda who: call(env, who, "GET", f"/api/intents/{rec['id']}")  # noqa: E731
    assert one("janet").json()["tier"] == "content" and one("daniel").json()["tier"] == "content" and one("aaron").json()["tier"] == "content"
    card = one("katie").json()  # tagged to the area Finance
    assert card["tier"] == "card" and "closure" not in card and "ratings" not in card and "refs" not in card
    assert card["people"] == {"organiser": {"name": "Janet Shaw"}} and "account_id" not in json.dumps(card) and card["stages"][0]["state"] == "open"
    assert one("harvey").json()["tier"] == "card"  # named affected, content switch off
    assert one("zed").status_code == 404  # no overlap, not named, not the admin
    # a company admin who is not in the intent sees that it exists, nothing more
    other = make(env, "problem")  # janet is organiser here too: use a draft opened by her, read as grace (no area) and root
    assert call(env, "grace", "GET", f"/api/intents/{other['id']}").status_code == 404
    # affected people read the content once the organiser switches it on
    r = call(env, "janet", "PATCH", f"/api/intents/{rec['id']}", {"version": 3, "affected_may_read": True})
    assert r.status_code == 200 and one("harvey").json()["tier"] == "content"
    names = {i["id"] for i in call(env, "zed", "GET", "/api/intents").json()}
    assert rec["id"] not in names and other["id"] not in names


def test_admin_sees_existence_only(env, tmp_path):
    rec = make(env, "brainstorm", areas=["Legal"])
    people(env, rec, {"participants": [P("aaron")]})
    # make the admin a non-organiser: Aaron starts one, Janet only has the admin role
    r = call(env, "aaron", "POST", "/api/intents", {"type": "problem", "title": "Wire delays", "purpose": "Late wires", "areas": ["Ops"]})
    mine = r.json()
    call(env, "aaron", "PATCH", f"/api/intents/{mine['id']}/state", {"version": 1, "to": "open"})
    seen = call(env, "janet", "GET", f"/api/intents/{mine['id']}").json()
    assert seen["tier"] == "exists" and "stages" in seen and "closure" not in seen and "people" not in seen and seen["title"] == "Wire delays"


@pytest.mark.parametrize("type_,slots", [("initiative", ["sponsor"]), ("brainstorm", []), ("pulse", []), ("decision", ["decider"])])
def test_transitions_and_the_per_type_closer(env, type_, slots):
    rec = make(env, type_)
    assert call(env, "aaron", "GET", f"/api/intents/{rec['id']}").status_code == 404
    assert go(env, rec, "closing").status_code == 409  # not listed from draft
    rec = people(env, rec, {s: P(a) for s, a in zip(slots, ["daniel"])} | {"participants": [P("aaron")]})
    rec = go(env, rec, "open").json()
    assert rec["state"] == "open" and rec["stages"][0]["state"] == "open" and rec["time_box"]["ends"] > rec["time_box"]["starts"]
    assert all(set(s) == {"key", "state", "opened_at", "closed_at"} for s in rec["stages"])  # names stay in the contract
    assert next(r for r in S.read_index(env.plane) if r["id"] == rec["id"])["stage_name"]
    assert go(env, rec, "open").status_code == 409 and go(env, rec, "open", "aaron").status_code in (403, 409)
    assert go(env, rec, "closed").status_code == 409  # closing through state is refused: close signs
    assert call(env, "aaron", "PATCH", f"/api/intents/{rec['id']}/state", {"version": rec["version"], "to": "in_session"}).status_code == 403
    rec = go(env, rec, "in_session").json()
    rec = go(env, rec, "closing").json()
    assert rec["closure"]["draft_by"] == "janet" and rec["closure"]["signed"] is False
    body = {"summary": "Done", "why_it_happened": "Fees", "what_came_out": "Pick A", "next": [{"kind": "nothing", "reason": "Handled"}]}
    close = lambda who="janet", **kw: call(env, who, "POST", f"/api/intents/{rec['id']}/close",  # noqa: E731
                                          {"version": cur()["version"], **(body | kw)})
    cur = lambda: call(env, "janet", "GET", f"/api/intents/{rec['id']}").json()  # noqa: E731
    assert close("aaron").status_code == 403  # only the organiser closes
    assert close(summary=" ").status_code == 400
    for slot, who in zip(slots, ["daniel"]):  # the confirmers sign first, in order
        assert close().status_code == 409
        assert call(env, who, "POST", f"/api/intents/{rec['id']}/closure/confirm", {"version": cur()["version"]}).status_code == 200
    done = close()
    assert done.status_code == 200, done.text
    out = done.json()
    assert out["state"] == "closed" and out["closure"]["signed"] and out["closure"]["closed_by"] == "janet"
    assert all(s["state"] == "closed" for s in out["stages"])
    assert call(env, "janet", "PATCH", f"/api/intents/{rec['id']}", {"version": out["version"], "title": "x"}).status_code == 409
    assert call(env, "janet", "POST", f"/api/intents/{rec['id']}/cancel", {"version": out["version"], "cancel_reason": "x"}).status_code == 409


def test_problem_owner_then_reporter(env):
    rec = make(env, "problem")
    rec = people(env, rec, {"owner": P("harvey"), "reporter": P("grace")})
    rec = go(env, rec, "open").json()
    rec = go(env, rec, "closing").json()
    conf = lambda who: call(env, who, "POST", f"/api/intents/{rec['id']}/closure/confirm",  # noqa: E731
                            {"version": call(env, "janet", "GET", f"/api/intents/{rec['id']}").json()["version"]})
    shut = lambda: call(env, "janet", "POST", f"/api/intents/{rec['id']}/close",  # noqa: E731
                        {"version": call(env, "janet", "GET", f"/api/intents/{rec['id']}").json()["version"], "summary": "Fixed"})
    assert conf("grace").status_code == 403  # the reporter waits for the owner
    assert conf("harvey").status_code == 200 and shut().status_code == 409
    assert conf("grace").status_code == 200
    assert shut().json()["state"] == "closed"


def test_send_back_keeps_the_closure_draft(env):
    rec = go(env, make(env, "brainstorm"), "open").json()
    rec = go(env, rec, "closing").json()
    rec["closure"]["summary"] = "x"
    back = go(env, rec, "open").json()
    assert back["state"] == "open" and back["closure"]["draft_by"] == "janet"
    assert [h["to"] for h in back["history"]] == ["draft", "open", "closing", "open"]


def test_cancel_needs_a_reason_and_is_final(env):
    rec = make(env, "brainstorm")
    url = f"/api/intents/{rec['id']}/cancel"
    assert call(env, "janet", "POST", url, {"version": 1, "cancel_reason": "  "}).status_code == 400
    assert call(env, "aaron", "POST", url, {"version": 1, "cancel_reason": "no"}).status_code == 404  # not even seen
    r = call(env, "janet", "POST", url, {"version": 1, "cancel_reason": "Merged into another"})
    out = r.json()
    assert r.status_code == 200 and out["state"] == "cancelled" and out["closure"]["cancel_reason"] == "Merged into another"
    assert out["closure"]["closed_by"] == "janet" and out["closure"]["closed_at"] and out["title"] == "Pick a custodian"  # content is kept
    assert call(env, "janet", "PATCH", f"/api/intents/{rec['id']}/state", {"version": out["version"], "to": "open"}).status_code == 409
    assert call(env, "janet", "GET", "/api/intents?view=past").json()[0]["state"] == "cancelled"
    assert call(env, "janet", "GET", "/api/intents?view=running").json() == []


def test_north_never_signs_or_cancels():
    rec = L.new_record("brainstorm", CO, P("janet"), "2026-10-05T09:00:00+00:00")
    L.move(rec, "open", "janet", "2026-10-05T09:00:00+00:00")
    L.move(rec, "closing", "north", "2026-10-06T09:00:00+00:00")
    assert rec["closure"]["draft_by"] == "north" and rec["history"][-1]["by"] == "north"
    for fn in (lambda: L.close(rec, "north", {"summary": "x"}, "t"), lambda: L.cancel(rec, "north", "x", "t"),
               lambda: L.move(rec, "closed", "north", "t"), lambda: L.move(rec, "open", "north", "t")):
        with pytest.raises(L.Refused):
            fn()


def test_version_conflict_writes_nothing(env):
    rec = make(env)
    ok = call(env, "janet", "PATCH", f"/api/intents/{rec['id']}", {"version": 1, "title": "First"})
    assert ok.status_code == 200 and ok.json()["version"] == 2
    stale = call(env, "janet", "PATCH", f"/api/intents/{rec['id']}", {"version": 1, "title": "Second"})
    assert stale.status_code == 409 and "reload" in stale.json()["detail"]
    assert call(env, "janet", "PATCH", f"/api/intents/{rec['id']}/state", {"version": 1, "to": "open"}).status_code == 409
    assert call(env, "janet", "PATCH", f"/api/intents/{rec['id']}", {"title": "no version"}).status_code == 400
    disk = json.loads(env.plane.path("intents", rec["id"], "intent.json").read_text())
    assert disk["title"] == "First" and disk["version"] == 2
    assert call(env, "aaron", "PATCH", f"/api/intents/{rec['id']}", {"version": 2, "title": "x"}).status_code == 404


def test_edit_rules(env):
    rec = make(env)
    bad = lambda **kw: call(env, "janet", "PATCH", f"/api/intents/{rec['id']}", {"version": 1, **kw}).status_code  # noqa: E731
    assert bad(state="closed") == 400 and bad(people={"organiser": P("daniel")}) == 400 and bad(people={"sponsor": {"account_id": "nobody", "name": "N"}}) == 400
    assert bad(title="x" * 201) == 400 and bad(areas="Finance") == 400
    assert call(env, "janet", "PATCH", f"/api/intents/{rec['id']}", {"version": 1, "areas": ["Finance", "Finance", " Ops "]}).json()["areas"] == ["Finance", "Ops"]


def test_extend_is_not_answered_here(env):
    rec = go(env, make(env, "decision"), "open").json()  # clock.py's /time-box/extend owns extending (B07's approval rule)
    end = datetime.fromisoformat(rec["time_box"]["ends"])
    r = call(env, "janet", "POST", f"/api/intents/{rec['id']}/extend", {"version": rec["version"], "to": end.replace(year=end.year + 1).isoformat(), "reason": "x"})
    assert r.status_code in (404, 405)


def test_working_days_skip_weekends():
    fri = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)
    assert L.add_working_days(fri, 2).date().isoformat() == "2026-10-06"  # Friday + 2 working days = Tuesday
    assert L.add_working_days(fri, 10).date().isoformat() == "2026-10-16"
    from sh_platform.intents import clock
    sat = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)
    assert L.add_working_days(sat, 1) == clock.working_days(sat, 1) == datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)  # one count


def test_stage_routes(env):
    rec = go(env, make(env, "problem"), "open").json()
    k = [s["key"] for s in rec["stages"]]
    r = call(env, "janet", "POST", f"/api/intents/{rec['id']}/stages/{k[0]}/close", {"version": rec["version"]})
    assert r.json()["stages"][0]["closed_at"]
    r = call(env, "janet", "POST", f"/api/intents/{rec['id']}/stages/{k[1]}/open", {"version": r.json()["version"]})
    assert r.json()["stages"][1]["state"] == "open"
    assert call(env, "janet", "POST", f"/api/intents/{rec['id']}/stages/nope/open", {"version": r.json()["version"]}).status_code == 404


def test_index_upsert_rebuild_and_list_filters(env):
    a, b = make(env, "decision"), make(env, "brainstorm", areas=["Legal"])
    idx = lambda: json.loads(env.plane.path("intents", "_index.json").read_text())["rows"]  # noqa: E731
    call(env, "janet", "PATCH", f"/api/intents/{a['id']}", {"version": 1, "title": "Renamed"})
    rows = {r["id"]: r for r in idx()}
    assert len(rows) == 2 and rows[a["id"]]["title"] == "Renamed" and rows[a["id"]]["rev"] == "2"  # upsert, not append
    go(env, a | {"version": 2}, "open")
    assert {r["id"]: r for r in idx()}[a["id"]]["state"] == "open" and {r["id"]: r for r in idx()}[a["id"]]["stage_key"] == "options"
    # damaged index: rebuilt from the files on the next list; a damaged record drops out and is never overwritten
    env.plane.path("intents", "_index.json").write_text("{not json")
    assert {i["id"] for i in call(env, "janet", "GET", "/api/intents").json()} == {a["id"], b["id"]}
    env.plane.path("intents", b["id"], "intent.json").write_text('{"id": "%s", "oops": 1}' % b["id"])
    S.rebuild_index(env.plane, "test")
    assert [i["id"] for i in call(env, "janet", "GET", "/api/intents").json()] == [a["id"]]
    assert call(env, "janet", "GET", f"/api/intents/{b['id']}").status_code == 500
    assert "oops" in env.plane.path("intents", b["id"], "intent.json").read_text()
    assert [i["id"] for i in call(env, "janet", "GET", "/api/intents?type=brainstorm").json()] == []
    assert call(env, "janet", "GET", "/api/intents?mine=1&state=open").json()[0]["id"] == a["id"]
    assert call(env, "janet", "GET", "/api/intents/not-an-id").status_code == 404


def test_store_functions_for_other_cards(env):
    rec = L.new_record("pulse", CO, P("janet"), S.now_iso())
    S.create_intent(env.plane, rec)
    with pytest.raises(S.VersionConflict):
        S.create_intent(env.plane, rec)  # an id is never reused
    got = S.read_intent(env.plane, rec["id"])
    got["event_count"] = 4
    out = S.write_intent(env.plane, got)
    assert out["version"] == 2
    with pytest.raises(S.VersionConflict):
        S.write_intent(env.plane, got | {"version": 1})
    with pytest.raises(ValueError):
        S.write_intent(env.plane, got | {"surprise": 1})
    assert S.update_intent(env.plane, rec["id"], 2, lambda r: r.update(purpose="p"))["version"] == 3
    assert [r["id"] for r in S.read_index(env.plane)] == [rec["id"]]


def test_super_admin_never_reads_intents(env):
    rec = go(env, make(env), "open").json()
    assert call(env, "root", "GET", f"/api/intents/{rec['id']}").status_code == 404  # R6: existence comes from /api/control (B31)
    assert call(env, "root", "GET", f"/api/intents/control?company_id={CO}").status_code == 404  # the old projection is gone
    assert rec["id"] not in json.dumps(call(env, "root", "GET", "/api/intents").json())
    rows = call(env, "root", "GET", f"/api/control/companies/{CO}/intents").json()["rows"]  # existence through the control route
    assert [r["id"] for r in rows] == [rec["id"]]
    assert set(rows[0]) <= {"id", "title", "title_private", "type", "state", "areas", "people_count", "opened", "ends", "clock", "bucket"}
    assert not {"purpose", "organiser", "outcome", "closure", "people"} & set(rows[0])
