"""F01: GET /api/intents, GET /api/intents/{id} read through file 05's matrix (visibility.py). The expected
table is typed out here, persona by persona, apart from the code; every check goes through the real routes."""
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.intents import admin, records, store as S, visibility
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile import store as profile_store

CO = "ardmore"
ACCTS = {  # id: (name, roles, area tags)
    "aaron": ("Aaron Lyle", ["participant"], []), "daniel": ("Daniel Kerr", ["sponsor"], []), "katie": ("Katie Rao", ["analyst"], []),
    "olive": ("Olive Ong", ["participant"], []), "harvey": ("Harvey Rowley", ["owner"], []), "fiona": ("Fiona Tay", ["participant"], ["finance"]),
    "grace": ("Grace Ward", ["approver"], ["compliance"]), "janet": ("Janet Shaw", ["company_admin"], ["compliance"]),
    "sally": ("Sally Chan", ["participant"], []), "zed": ("Zed Lee", ["participant"], []), "root": ("Platform", ["super_admin"], []),
}
# persona -> (status, tier, people keys or None for absent); file 05 rows: organiser, sponsor, participant, observer, affected (switch off),
# same-area, other-area, no area, company admin, super admin, share visitor, expired share
MATRIX = {
    "aaron":  (200, "content", "all"), "daniel": (200, "content", "all"), "katie": (200, "content", "all"), "olive": (200, "content", "all"),
    "harvey":  (200, "card", {"organiser", "sponsor", "decider", "owner", "reporter", "participants", "advisers", "affected", "observers"}),
    "fiona":  (200, "card", {"organiser"}), "grace": (404, None, None), "zed": (404, None, None),
    "janet":  (200, "exists", None), "root": (404, None, None), "sally": (200, "content", "all"),
}


class Accounts:
    def get(self, aid):
        return {"display_name": ACCTS[aid][0]} if aid in ACCTS else None

    def in_company(self, company_id):
        return [{"account_id": a, "display_name": n, "roles": r, "disabled": False} for a, (n, r, _t) in ACCTS.items() if a != "root"]


@pytest.fixture
def env(tmp_path):
    plane = PlaneStore(tmp_path).create(CO).ensure()
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = Accounts()
    app.state.entitlements = SimpleNamespace(company=lambda cid: {"name": "Ardmore"} if cid == CO else None)
    app.include_router(records.router)
    app.include_router(admin.router)
    app.include_router(visibility.router)

    @app.middleware("http")
    async def sign_in(request, call_next):
        who = request.headers.get("x-who", "aaron")
        request.state.account_id, request.state.company_id, request.state.roles = who, CO, ACCTS[who][1]
        return await call_next(request)

    c = lambda v: {"value": v, "mark": "stated"}  # noqa: E731
    profile_store.mutate(plane, lambda d: d["people"].update({
        f"p-{a}": {"name": c(n), "account_id": c(a), "team": c("Finance"), **({"areas": c(t)} if t else {})}
        for a, (n, _r, t) in ACCTS.items() if a != "root"}))  # everyone's team text says Finance: only the tag may count
    return SimpleNamespace(plane=plane, c=TestClient(app))


def call(env, who, method, path, body=None):
    return env.c.request(method, path, json=body or {}, headers={"x-who": who})


def P(aid):
    return {"account_id": aid, "name": ACCTS[aid][0]}


def opened(env, areas=("finance",), **people):
    r = call(env, "aaron", "POST", "/api/intents", {"type": "brainstorm", "title": "Cash view", "purpose": "See cash early", "areas": list(areas)})
    rec = r.json()
    if people:
        rec = call(env, "aaron", "PATCH", f"/api/intents/{rec['id']}", {"version": rec["version"], "people": people}).json()
    return call(env, "aaron", "PATCH", f"/api/intents/{rec['id']}/state", {"version": rec["version"], "to": "open"}).json()


def share(env, iid, rows):
    S.update_intent(env.plane, iid, S.read_intent(env.plane, iid)["version"], lambda r: r.update(share={"link": None, "who_may_open": rows}))


def test_matrix_through_the_routes(env):
    rec = opened(env, sponsor=P("daniel"), participants=[P("katie")], observers=[P("olive")], affected=[P("harvey")])
    share(env, rec["id"], [{"person_id": "sally", "label": "Sally", "token_hash": "secret-hash", "expires_at": "2099-01-01T00:00:00+00:00", "revoked_at": None},
                           {"person_id": "zed", "label": "Zed", "token_hash": "", "expires_at": "2020-01-01T00:00:00+00:00", "revoked_at": None}])
    for who, (status, tier, ppl) in MATRIX.items():
        r = call(env, who, "GET", f"/api/intents/{rec['id']}")
        assert r.status_code == status, (who, r.text)
        listed = rec["id"] in json.dumps(call(env, who, "GET", "/api/intents").json()) if who != "root" else False
        assert listed == (status == 200 and who != "root"), who
        if status != 200:
            assert r.json() == call(env, who, "GET", "/api/intents/bra-" + "0" * 32).json()  # hidden reads like missing
            continue
        out = r.json()
        assert out["tier"] == tier, who
        blob = json.dumps(out)
        assert "secret-hash" not in blob, who
        if tier != "content":
            assert "account_id" not in blob and not {"refs", "start_answers", "closure", "history", "share"} & set(out), who
            assert "stages" in out and ("outcome" not in out) == (tier == "card"), who  # stage and clock Y; outcome: admin Y, else once closed
            assert out.get("ratings") == ({"count": 0, "average": None} if who == "janet" else None), who  # admin: count, average from three
            assert (set(out["people"]) if "people" in out else None) == ppl, who
    assert call(env, "sally", "GET", f"/api/intents/{rec['id']}").json()["share"] == {"shared_with_you": True}  # spec 11 rule 4: never the other shares


def test_closed_outcome_and_draft(env):
    draft = call(env, "aaron", "POST", "/api/intents", {"type": "problem", "title": "Wire delays", "purpose": "Late", "areas": ["finance"]}).json()
    for who in ("fiona", "janet", "daniel", "root"):
        assert call(env, who, "GET", f"/api/intents/{draft['id']}").status_code == 404, who  # starter only (ruling 14)
    assert call(env, "root", "GET", f"/api/intents/control?company_id={CO}").status_code == 404  # R6: the projection is gone
    rows = call(env, "root", "GET", f"/api/control/companies/{CO}/intents").json()["rows"]  # the super admin's route: no draft, no content
    assert draft["id"] not in json.dumps(rows) and "Wire delays" not in json.dumps(rows)
    rec = opened(env)
    rec = call(env, "aaron", "PATCH", f"/api/intents/{rec['id']}/state", {"version": rec["version"], "to": "closing"}).json()
    done = call(env, "aaron", "POST", f"/api/intents/{rec['id']}/close", {"version": rec["version"], "summary": "S", "what_came_out": "Out",
                                                                          "next": [{"kind": "nothing", "reason": "r"}]})
    assert done.status_code == 200, done.text
    seen = call(env, "fiona", "GET", f"/api/intents/{rec['id']}").json()
    assert seen["tier"] == "card" and "outcome" in seen and "closure" not in seen


def test_company_wide_missing_refs_and_index(env):
    rec = opened(env, areas=("company-wide",))
    for who in ("zed", "grace", "fiona"):
        assert call(env, who, "GET", f"/api/intents/{rec['id']}").json()["tier"] == "card", who  # in every area
    S.update_intent(env.plane, rec["id"], rec["version"], lambda r: r.pop("refs", None))
    assert call(env, "aaron", "GET", f"/api/intents/{rec['id']}").json()["refs_resolved"] == []  # no KeyError, no 404 for its own organiser
    row = next(r for r in S.read_index(env.plane) if r["id"] == rec["id"])
    assert row["created_at"] and json.loads(env.plane.path("intents", "_index.json").read_text())["schema"] == S.SCHEMA


def test_search_keys_use_the_index_query(env):
    rec = opened(env)
    found = call(env, "fiona", "GET", "/api/intents?q=cash").json()
    assert found["total"] == 1 and found["items"][0]["id"] == rec["id"] and not found["items"][0]["can_open"]
    assert call(env, "grace", "GET", "/api/intents?q=cash").json()["total"] == 0
    assert isinstance(call(env, "fiona", "GET", "/api/intents?view=running").json(), list)  # the plain list stays a list
    assert set(call(env, "fiona", "GET", "/api/intents?limit=5").json()) >= {"items", "total"}  # limit alone is a search key


def test_named_in_records_reads_as_participant(env):
    rec = opened(env, areas=("treasury",))
    S.update_intent(env.plane, rec["id"], rec["version"], lambda r: r.update(refs={**(r.get("refs") or {}), "baseline_ids": ["b1"]}))
    assert call(env, "harvey", "GET", f"/api/intents/{rec['id']}").status_code == 404
    write_json_atomic(env.plane.path("intents", "m2_baseline", "b1", "data_sources.json"),
                      {"sources": {"S01": {"source_owner": {"value": "Harvey Rowley", "mark": "stated"}}}})
    seen = call(env, "harvey", "GET", f"/api/intents/{rec['id']}")
    assert seen.status_code == 200 and seen.json()["tier"] == "content"
    assert call(env, "zed", "GET", f"/api/intents/{rec['id']}").status_code == 404
    write_json_atomic(env.plane.path("intents", rec["id"], "processes.json"), {"processes": [{"owner": {"value": "p-zed", "mark": "stated"}}]})
    assert call(env, "zed", "GET", f"/api/intents/{rec['id']}").json()["tier"] == "content"  # a profile person id matches too
    assert call(env, "grace", "GET", f"/api/intents/{rec['id']}").status_code == 404
    write_json_atomic(env.plane.path("intents", rec["id"], "lens_questions.json"), {"questions": [{"to_person": "Grace Ward"}]})
    assert call(env, "grace", "GET", f"/api/intents/{rec['id']}").json()["tier"] == "content"  # a Lens question's person
    assert call(env, "olive", "GET", f"/api/intents/{rec['id']}").status_code == 404
    write_json_atomic(env.plane.path("intents", "m2_baseline", "b1", "governed_state.json"), {"K1": {"owners": {"value": ["Olive Ong"], "mark": "stated"}}})
    assert call(env, "olive", "GET", f"/api/intents/{rec['id']}").json()["tier"] == "content"  # a governed owner
    S.update_intent(env.plane, rec["id"], S.read_intent(env.plane, rec["id"])["version"], lambda r: r["refs"].update(wall_session_ids=["w1"]))
    write_json_atomic(env.plane.path("intents", "m1_intent", "roles", "w1.json"), {"roles": {"approver": {"value": "Sally Chan", "mark": "stated"}}})
    assert call(env, "sally", "GET", f"/api/intents/{rec['id']}").json()["tier"] == "content"  # a charter role
    assert call(env, "aaron", "GET", f"/api/intents/{rec['id']}").json()["refs_resolved"][0]["missing"] == "wall session not found"


def test_content_route_admits_who_the_record_route_admits(env):
    """F23: /content and the role=participant list filter use the record route's deciders."""
    path = lambda i: f"/api/intents/{i}/content"  # noqa: E731
    # (1) a source owner in another area
    rec = opened(env, areas=("treasury",))
    S.update_intent(env.plane, rec["id"], rec["version"], lambda r: r.update(refs={"baseline_ids": ["b1"]}))
    write_json_atomic(env.plane.path("intents", "m2_baseline", "b1", "data_sources.json"),
                      {"sources": {"S01": {"source_owner": {"value": "Harvey Rowley", "mark": "stated"}}}})
    assert call(env, "harvey", "GET", path(rec["id"])).json()["access"]["content"] is True
    assert call(env, "zed", "GET", path(rec["id"])).status_code == 404
    found = call(env, "harvey", "GET", "/api/intents?role=participant").json()
    assert rec["id"] in json.dumps(found) and rec["id"] not in json.dumps(call(env, "zed", "GET", "/api/intents?role=participant").json())
    # (2) every area reader of a company-wide intent
    wide = opened(env, areas=("company-wide",))
    for who in ("zed", "grace", "fiona", "daniel"):
        out = call(env, who, "GET", path(wide["id"]))
        assert out.status_code == 200 and out.json()["access"]["content"] is False, who
    # (3) a person named in a share
    sh = opened(env, areas=("finance",))
    assert call(env, "zed", "GET", path(sh["id"])).status_code == 404
    share(env, sh["id"], [{"person_id": "zed", "label": "Zed", "token_hash": "h", "expires_at": "2099-01-01T00:00:00+00:00", "revoked_at": None}])
    assert call(env, "zed", "GET", path(sh["id"])).json()["access"]["content"] is True
    assert call(env, "grace", "GET", path(sh["id"])).status_code == 404


def test_the_record_carries_person_ids_never_another_persons_account_id(env):  # F43, SEC0 #4
    rec = opened(env, sponsor=P("daniel"), participants=[P("katie")], observers=[P("olive")])
    for who in ("aaron", "daniel", "katie", "olive"):
        out = call(env, who, "GET", f"/api/intents/{rec['id']}").json()
        others = {"aaron", "daniel", "katie", "olive"} - {who}
        blob = json.dumps(out)
        assert not any(f'"{a}"' in blob for a in others), (who, blob)
        assert f'"p-{next(iter(others))}"' in blob  # shown by person id instead
        me = [x for x in [out["people"].get("organiser"), out["people"].get("sponsor"), *out["people"]["participants"], *out["people"]["observers"]]
              if x and x.get("is_me")]
        assert me and me[0]["account_id"] == who  # the viewer keeps their own, flagged
