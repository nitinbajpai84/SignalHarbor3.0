"""B28 (spec 11): share link and visitor view. Synthetic people; a small app with the share router and the two visitor routes."""
import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m1_intent.api import shared
from sh_platform.intents import share, store as S
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile import store as profile_store

CO = "ardmore"
SID = "a" * 32
ACCTS = {"janet": ("Janet Shaw", ["company_admin"]), "harvey": ("Harvey Rowley", ["owner"]), "aaron": ("Aaron Lyle", ["participant"]),
         "ops1": ("Mei Ling", ["participant"]), "zed": ("Zed Lee", ["participant"]), "pat": ("Pat Tan", ["participant"])}
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


class Accounts:
    def get(self, aid):
        return {"display_name": ACCTS[aid][0]} if aid in ACCTS else None

    def in_company(self, company_id):
        return [{"account_id": a, "display_name": n, "roles": r, "disabled": False} for a, (n, r) in ACCTS.items()]


def person(aid, team):
    c = lambda v: {"value": v, "mark": "stated"}  # noqa: E731
    return {"name": c(ACCTS[aid][0]), "team": c(team), "role": c("Analyst"), "account_id": c(aid)}


def record(state="closed"):
    org = {"name": "Janet Shaw", "account_id": "janet"}
    return {"id": "ini-" + "b" * 32, "type": "initiative", "title": "Quarterly valuation review", "purpose": "Check the second valuation",
            "created_by": "janet", "created_at": "2026-10-01T00:00:00+00:00", "company": CO, "areas": ["Finance"],
            "people": {"organiser": org, "sponsor": None, "decider": None, "owner": None, "reporter": None,
                       "participants": [{"name": "Pat Tan", "account_id": "pat"}], "advisers": [], "affected": [], "observers": []},
            "state": state, "time_box": {"starts": "2026-10-01", "ends": "2026-10-10", "extended_by": []},
            "stages": [{"key": "think_unfiltered", "state": "closed", "opened_at": "2026-10-01", "closed_at": "2026-10-02"}],
            "outcome": {"kind": "initiative", "goal": "Faster valuations", "why": "The council waits", "build_needed": "", "definitions_exist": ""},
            "closure": {"closed_by": "janet", "closed_at": "2026-10-09T00:00:00+00:00", "summary": "Done in a week", "why_it_happened": "Clear owner",
                        "what_came_out": "One new check", "next": [{"kind": "nothing", "ref": None, "reason": "Complete"}],
                        "cancel_reason": None},
            "ratings": [{"by": "pat", "score": 5, "note": "secret rating note"}], "links": {"from": None, "to": [], "build": None},
            "share": {"link": None, "who_may_open": []}, "refs": {"wall_session_ids": [SID]}, "affected_may_read": False}


@pytest.fixture
def env(tmp_path):
    plane = PlaneStore(tmp_path).create(CO).ensure()
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = Accounts()
    app.state.entitlements = SimpleNamespace(company=lambda cid: {"name": "Ardmore Family Office"})
    app.include_router(share.router)
    app.include_router(shared.router, prefix="/api/modules/m1_intent")

    @app.middleware("http")
    async def sign_in(request, call_next):
        who = request.headers.get("x-who")
        request.state.account_id, request.state.company_id, request.state.roles = (who, CO, ACCTS[who][1]) if who else (None, None, [])
        return await call_next(request)

    profile_store.mutate(plane, lambda d: d["people"].update({"p1": person("harvey", "Operations"), "p2": person("ops1", "Operations"),
                                                              "p3": person("zed", "Legal")}))
    wall = {"session_id": SID, "closed_at": "x", "lanes": [{"lane": "tracking", "cards": [
        {"id": "c1", "text": "", "author": "Aaron Lyle", "sealed": False}, {"id": "c2", "text": "", "author": "Anonymous", "sealed": False},
        {"id": "c3", "text": "", "author": "Pat Tan", "sealed": True}]}]}
    notes = {"session_id": SID, "notes": [{"id": "c1", "text": "Named card text", "anonymous": False}, {"id": "c2", "text": "Anon card text", "anonymous": True},
                                          {"id": "c3", "text": "SEALED TOPIC", "anonymous": False}]}
    for kind, doc in (("wall", wall), ("notes", notes)):
        plane.path("intents", "m1_intent", kind).mkdir(parents=True, exist_ok=True)
        write_json_atomic(plane.path("intents", "m1_intent", kind, f"{SID}.json"), doc)
    S.create_intent(plane, record())
    return SimpleNamespace(plane=plane, c=TestClient(app), id=record()["id"])


def call(env, who, method, path, body=None, token=None):
    h = {"x-who": who} if who else {}
    if token:
        h["x-session-token"] = token
    return env.c.request(method, path, json=body if body is not None else {}, headers=h)


def do_share(env, targets, day=TOMORROW):
    return call(env, "janet", "POST", f"/api/intents/{env.id}/share", {"targets": targets, "expires_at": day})


def view(env, who, token=None):
    return call(env, who, "POST", "/api/modules/m1_intent/shared/view", {} if token else {"intent_id": env.id}, token)


def rec_of(env):
    return S.read_intent(env.plane, env.id)


def plane_bytes(env, kind):
    return env.plane.path("intents", "m1_intent", kind, f"{SID}.json").read_bytes()


def token_of(body):
    return body["link"]["url"].rsplit("/", 1)[1]


def test_share_people_area_and_link(env):
    r = do_share(env, [{"kind": "person", "target": "harvey"}, {"kind": "area", "target": "Operations"}, {"kind": "link"}])
    assert r.status_code == 200, r.text
    body = r.json()
    assert "/centre/shared/t/sh-" + env.id + "-" in body["link"]["url"]
    assert (body["counts"]["people"], body["counts"]["areas"], body["counts"]["links"], body["counts"]["live"]) == (1, 1, 1, 3)
    assert {e["kind"] for e in body["entries"]} == {"person", "area", "link"} and all("hash" not in e for e in body["entries"])
    assert body["counts"]["of"] is None  # a link row: nobody can say how many could open it
    s = rec_of(env)["share"]
    assert [w["person_id"] for w in s["who_may_open"]] == ["harvey"] and s["link"]  # who_may_open feeds the intent store's named access
    assert next(e for e in s["entries"] if e["kind"] == "area")["head_count"] == 2
    assert "hash" in next(e for e in s["entries"] if e["kind"] == "link") and "sh-" + env.id not in json.dumps(s)  # fingerprint only


def test_share_refusals(env):
    assert do_share(env, [{"kind": "person", "target": "harvey"}], day="").status_code == 422  # expiry required
    assert do_share(env, [{"kind": "person", "target": "harvey"}], day="2020-01-01").status_code == 422
    assert do_share(env, []).status_code == 422
    assert do_share(env, [{"kind": "person", "target": "pat"}]).status_code == 422  # already in the intent
    assert do_share(env, [{"kind": "area", "target": "Nowhere"}]).status_code == 422
    assert call(env, "harvey", "GET", f"/api/intents/{env.id}/share").status_code == 404  # not even a card for him
    assert call(env, "pat", "GET", f"/api/intents/{env.id}/share").status_code == 403  # sees it, does not run it
    S.update_intent(env.plane, env.id, rec_of(env)["version"], lambda r: r.update(state="draft"))
    r = do_share(env, [{"kind": "link"}])
    assert r.status_code == 409 and "draft" in r.json()["message"]


def test_visitor_by_name_area_and_link_and_opens_logged(env):
    token = token_of(do_share(env, [{"kind": "person", "target": "harvey"}, {"kind": "area", "target": "Operations"}, {"kind": "link"}]).json())
    assert view(env, "harvey").status_code == 200
    assert view(env, "harvey").status_code == 200  # a refresh is one open
    v = view(env, "ops1")  # tagged to Operations
    assert v.status_code == 200
    assert view(env, "aaron").status_code == 404  # named nowhere
    assert view(env, "aaron", token).status_code == 200  # the link
    opens = call(env, "janet", "GET", f"/api/intents/{env.id}/share").json()
    assert opens["counts"]["opened"] == 3 and {o["name"]: o["times"] for o in opens["opens"]} == {"Harvey Rowley": 1, "Mei Ling": 1, "Aaron Lyle": 1}
    assert {o["through"] for o in opens["opens"]} == {"name", "area", "link"}
    assert v.json()["banner"]["organiser"] == "Janet Shaw" and v.json()["note_max"] == 1000


def test_expiry_and_withdraw(env):
    body = do_share(env, [{"kind": "person", "target": "harvey"}, {"kind": "link"}]).json()
    token = token_of(body)
    assert view(env, "aaron", token).status_code == 200
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()  # the clock: a row past its end opens nothing, with no write
    S.update_intent(env.plane, env.id, rec_of(env)["version"],
                    lambda r: [e.update(expires_at=past) for e in r["share"]["entries"] if e["kind"] == "person"])
    r = view(env, "harvey")
    assert r.status_code == 409 and r.json()["message"] == "This share has ended."
    entry = next(e for e in body["entries"] if e["kind"] == "link")
    assert call(env, "janet", "DELETE", f"/api/intents/{env.id}/share/{entry['id']}").status_code == 200  # the next open fails at once
    r = view(env, "aaron", token)
    assert r.status_code == 409 and r.json()["message"] == "This share has ended."
    assert rec_of(env)["share"]["link"] is None
    assert call(env, "janet", "POST", f"/api/intents/{env.id}/share/withdraw", {"entry_id": "all"}).status_code == 404  # nothing live is left


def test_reshare_replaces_and_withdraw_all(env):
    first = token_of(do_share(env, [{"kind": "link"}]).json())
    second = token_of(do_share(env, [{"kind": "link"}]).json())
    assert view(env, "aaron", first).json()["message"] == "This share has ended."
    assert view(env, "aaron", second).status_code == 200
    assert [e["replaced_by"] is not None for e in rec_of(env)["share"]["entries"]] == [True, False]
    assert call(env, "janet", "POST", f"/api/intents/{env.id}/share/withdraw", {"entry_id": "all"}).json()["counts"]["live"] == 0
    assert view(env, "aaron", second).status_code == 409


def test_bad_link_is_one_answer_and_locks(env):
    do_share(env, [{"kind": "link"}])
    bad = "sh-" + env.id + "-" + "A" * 43
    assert [view(env, "aaron", bad).status_code for _ in range(5)] == [404] * 5
    assert view(env, "aaron", "garbage").status_code == 429  # locked after the failures
    assert call(env, None, "POST", "/api/modules/m1_intent/shared/view", {"intent_id": env.id}).status_code == 401


def test_visitor_sees_the_state_cut(env):
    do_share(env, [{"kind": "person", "target": "harvey"}])
    v = view(env, "harvey").json()
    assert v["closure"]["summary"] == "Done in a week" and v["closure"]["next"] == [{"kind": "nothing", "reason": "Complete"}]
    assert [p["name"] for p in v["people"]] == ["Janet Shaw", "Pat Tan"]

    def to(state, **closure):
        S.update_intent(env.plane, env.id, rec_of(env)["version"], lambda r: (r.update(state=state), r["closure"].update(closure)))
        return view(env, "harvey")
    o = to("open").json()
    assert o["closure"] is None and o["wall"]["lanes"][0]["cards"] and o["cancelled"] is None
    c = to("cancelled", cancel_reason="Not needed").json()
    assert c["cancelled"]["reason"] == "Not needed" and c["wall"] is None and c["closure"] is None and c["cancelled"]["by"] == "Janet Shaw"
    assert to("draft").status_code == 404  # a stale share after a reversal


def test_never_sealed_anonymous_or_private(env):
    token = token_of(do_share(env, [{"kind": "person", "target": "harvey"}, {"kind": "link"}]).json())
    for r in (view(env, "harvey"), view(env, "aaron", token)):
        raw, v = r.text, r.json()
        cards = v["wall"]["lanes"][0]["cards"]
        assert v["sealed"] == 1 and "SEALED TOPIC" not in raw
        assert [c["author"] for c in cards] == ["Aaron Lyle", "Anonymous"] and '"c2"' not in raw and '"c1"' not in raw
        assert v["restricted"] == 0 and "measure" not in raw.lower()
        for secret in ("secret rating note", "hash", "token_hash", "created_by", "account_id", "who_may_open", "ratings", "sh-" + env.id):
            assert secret not in raw


def test_a_card_sealed_on_its_note_only_stays_sealed(env):
    p = env.plane.path("intents", "m1_intent", "notes", f"{SID}.json")
    doc = json.loads(p.read_text())
    doc["notes"][0]["restricted"] = True  # the wall copy of c1 says not sealed; the note itself is sealed
    write_json_atomic(p, doc)
    do_share(env, [{"kind": "person", "target": "harvey"}])
    r = view(env, "harvey")
    assert r.json()["sealed"] == 2 and "Named card text" not in r.text and "Aaron Lyle" not in json.dumps(r.json()["wall"])


def test_note_goes_to_the_record_not_the_session(env):
    do_share(env, [{"kind": "person", "target": "harvey"}])
    before = plane_bytes(env, "notes"), plane_bytes(env, "wall")
    r = call(env, "harvey", "POST", "/api/modules/m1_intent/shared/note", {"intent_id": env.id, "text": "Which fund did the second valuation use?"})
    assert r.status_code == 200 and r.json() == {"sent": True, "to": "Janet Shaw"}
    note = lambda who, text: call(env, who, "POST", "/api/modules/m1_intent/shared/note", {"intent_id": env.id, "text": text})  # noqa: E731
    assert note("harvey", "   ").status_code == 422 and note("harvey", "x" * 1001).status_code == 422
    assert note("aaron", "hello").status_code == 404
    assert (plane_bytes(env, "notes"), plane_bytes(env, "wall")) == before  # the session's files are untouched
    n = rec_of(env)["share"]["notes"]
    assert len(n) == 1 and n[0]["by"] == "harvey" and n[0]["read_at"] is None
    panel = call(env, "janet", "GET", f"/api/intents/{env.id}/share").json()
    assert panel["notes"][0]["name"] == "Harvey Rowley" and panel["counts"]["unread"] == 1
    done = call(env, "janet", "POST", f"/api/intents/{env.id}/share/notes/{n[0]['id']}/read").json()
    assert done["counts"]["unread"] == 0 and rec_of(env)["share"]["notes"][0]["read_by"] == "janet"
    assert "notes" not in view(env, "harvey").json()  # a visitor never reads notes back
    call(env, "janet", "DELETE", f"/api/intents/{env.id}/share/all")  # a withdrawn share takes no more notes
    assert note("harvey", "late").status_code == 409


def test_who_opened_it_names_every_route(env):  # F35
    token = token_of(do_share(env, [{"kind": "person", "target": "harvey"}, {"kind": "link"}]).json())
    assert view(env, "harvey").status_code == 200 and view(env, "harvey", token).status_code == 200
    opens = call(env, "janet", "GET", f"/api/intents/{env.id}/share").json()["opens"]
    assert [o["through"] for o in opens] == ["name and link"]


# ---- F43 (SEC0 #4, #6): the organiser's panel and record carry person ids, never another person's account id or a link hash

def test_share_panel_and_record_carry_person_ids_not_account_ids_or_hashes(env):
    panel = call(env, "janet", "GET", f"/api/intents/{env.id}/share").json()
    ids = {p["name"]: p["id"] for p in panel["people"]}
    assert ids["Harvey Rowley"] == "p1" and ids["Pat Tan"].startswith("acct-") and ids["Janet Shaw"] == "janet"  # the viewer keeps her own
    r = do_share(env, [{"kind": "person", "target": "p1"}, {"kind": "link"}])  # the screen picks by person id
    assert r.status_code == 200, r.text
    assert '"harvey"' not in r.text and '"pat"' not in r.text
    assert [w["person_id"] for w in rec_of(env)["share"]["who_may_open"]] == ["harvey"]  # the store keeps the account
    from sh_platform.profile.view import Viewer
    for who in ("janet",):
        out = S.cut(rec_of(env), "content", Viewer("Janet Shaw", frozenset({"company_admin"}), False, who),
                    S.context(env.plane, Viewer("Janet Shaw", frozenset({"company_admin"}), False, who)))
        assert all("hash" not in e for e in out["share"]["entries"]) and "token_hash" not in json.dumps(out)
        assert '"harvey"' not in json.dumps(out) and out["share"]["who_may_open"][0]["person_id"] == "p1"
