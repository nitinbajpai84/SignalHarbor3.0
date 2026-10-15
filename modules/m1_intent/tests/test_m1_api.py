"""M1-01, M1-02, M1-29 (skeleton), M1-31 through the real app: roles, draft rules, templates, process record
link, two industries, an empty company, a solo user, and a module that is switched off."""
import pytest

from m1_kit import BASE, ORGANISER_ROLES, draft
from sh_platform.process_record import ProcessRecords

NOT_THERE = {"error": "not_found", "message": "We could not find that session."}


def create(c, **over):
    r = c.post(f"{BASE}/sessions", json=draft(**over))
    assert r.status_code == 201, r.text
    return r.json()


# ---- access: roles, signed out, switched off (module 1 specifically) --------------------------------------
@pytest.mark.parametrize("role", ORGANISER_ROLES)
def test_organiser_roles_can_prepare(world, role):
    c = world.login(f"org-{role}", "co-a", [role])
    assert create(c)["state"] == "draft"


@pytest.mark.parametrize("role", ["participant", "approver", "owner"])
def test_other_roles_are_refused_everywhere(world, role):
    org = world.login("org", "co-a")
    sid = create(org)["id"]
    c = world.login(f"other-{role}", "co-a", [role])
    calls = [("get", "/sessions"), ("post", "/sessions"), ("get", f"/sessions/{sid}"), ("put", f"/sessions/{sid}"),
             ("delete", f"/sessions/{sid}"), ("get", "/templates"), ("post", "/templates"), ("get", "/lists"),
             ("get", f"/outcomes/{'a' * 32}")]
    for verb, path in calls:
        r = getattr(c, verb)(BASE + path, **({"json": draft()} if verb in ("post", "put") else {}))
        # the one read a participant may make is their own session; with no seat the handler says "not found"
        want = 404 if (role == "participant" and verb == "get" and path == f"/sessions/{sid}") else 403
        assert r.status_code == want, (verb, path)
    assert org.get(f"{BASE}/sessions/{sid}").json()["preparation"]["purpose"] == draft()["purpose"]


def test_a_seat_holder_reads_a_limited_view_of_their_own_session(world):
    from test_m1_briefing_kit import PATH, SessionStore, sit
    sid = create(world.login("org", "co-a"))["id"]
    store = SessionStore(world.plane("co-a").ensure())
    for stage in PATH[:PATH.index("briefing") + 1]:
        store.transition(sid, stage)
    c = world.login("seated", "co-a", ["participant"])
    sit(world, "co-a", sid, c.account_id, "Priya")
    got = c.get(f"{BASE}/sessions/{sid}")
    assert got.status_code == 200
    assert set(got.json()) == {"id", "label", "state", "preparation", "seat"}
    assert set(got.json()["preparation"]) == {"purpose", "topic"}


def test_signed_out_is_refused(world):
    from fastapi.testclient import TestClient
    r = TestClient(world.app).get(f"{BASE}/sessions")
    assert r.status_code == 401


def test_a_company_without_module_1_is_refused_on_every_route_and_has_no_menu_entry(world):
    c = world.login("off", "co-off", ["company_admin"])
    for verb, path in [("get", "/sessions"), ("post", "/sessions"), ("get", "/lists"), ("get", "/templates"),
                       ("get", f"/sessions/{'a' * 32}"), ("get", f"/outcomes/{'a' * 32}")]:
        r = getattr(c, verb)(BASE + path, **({"json": draft()} if verb == "post" else {}))
        assert (r.status_code, r.json()["error"]) == (403, "module_not_available"), path
    assert [m["id"] for m in c.get("/api/modules").json()] == ["m2_baseline"]
    assert world.plane("co-off").area("intents").exists() and not list(world.plane("co-off").area("intents").rglob("*.json"))


def test_switching_module_1_off_refuses_a_signed_in_organiser_at_once_and_websockets_too(world):
    from starlette.websockets import WebSocketDisconnect
    c = world.login("org", "co-a")
    assert c.get(f"{BASE}/sessions").status_code == 200
    world.store.set_module("co-a", "m1_intent", False)
    assert c.get(f"{BASE}/sessions").status_code == 403
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect(f"{BASE}/live"):
            pass
    assert "m1_intent" not in [m["id"] for m in c.get("/api/modules").json()]


def test_a_route_that_is_not_declared_is_refused_by_default(world):
    c = world.login("org", "co-a")
    r = c.get(f"{BASE}/sessions/{'a' * 32}/notes")
    assert r.status_code in (403, 404)
    assert c.patch(f"{BASE}/sessions/{'a' * 32}", json={}).status_code in (403, 405)


# ---- the lists the screens offer -----------------------------------------------------------------------------
def test_lists_come_from_the_contract_files(world):
    from modules.m1_intent.domain import contracts as C
    s, t = C.load_session_settings(), C.load_charter_templates()
    body = world.login("org", "co-a").get(f"{BASE}/lists").json()
    assert body["seats"] == {"min": s.seats_min, "max": s.seats_max}
    assert body["time_presets_minutes"] == list(s.time_presets)
    assert [x["id"] for x in body["charter_templates"]] == [x.id for x in t.templates]
    assert body["default_template"] == t.default_id
    assert sum(body["default_split"].values()) == body["default_length_minutes"]


def test_north_offers_follow_the_pack_of_the_company_industry(world):
    a = world.login("a", "co-a").get(f"{BASE}/lists").json()["north"]
    b = world.login("b", "co-b").get(f"{BASE}/lists").json()["north"]
    assert (a["problem_library_available"], a["industry_practice_available"]) == (True, True)
    assert a["problem_count"] == 3 and b["problem_count"] == 2  # each company sees only its own industry's pack
    n = world.login("n", "co-none").get(f"{BASE}/lists").json()["north"]
    assert (n["problem_library_available"], n["industry_practice_available"], n["problem_count"]) == (False, False, 0)
    assert "No industry knowledge" in n["message"]
    assert "industry_a" not in str(n) and "industry_b" not in str(n)


def test_north_offer_is_refused_for_an_industry_without_a_pack(world):
    c = world.login("n", "co-none")
    r = c.post(f"{BASE}/sessions", json=draft(north_problem_library=True))
    assert r.status_code == 422 and r.json()["field"] == "north_problem_library"
    ok = c.post(f"{BASE}/sessions", json=draft())
    assert ok.status_code == 201  # the empty pack never blocks preparing
    assert ok.json()["preparation"]["north_problem_library"] is False


# ---- M1-01: draft rules ---------------------------------------------------------------------------------------
def test_draft_save_close_reopen_edit_by_organiser(world):
    c = world.login("org", "co-a")
    s = create(c, seats=3, approver_name="Chief Anybody")
    assert s["state"] == "draft" and s["editable"] is True and s["is_solo"] is False
    got = c.get(f"{BASE}/sessions/{s['id']}").json()  # closed and reopened
    assert got["preparation"]["seats"] == 3 and got["preparation"]["approver_name"] == "Chief Anybody"
    r = c.put(f"{BASE}/sessions/{s['id']}", json={"purpose": "A better purpose", "seats": 5})
    assert r.status_code == 200 and r.json()["preparation"]["purpose"] == "A better purpose"
    again = c.get(f"{BASE}/sessions/{s['id']}").json()["preparation"]
    assert again["seats"] == 5 and again["outcome"] == "A signed charter"  # untouched values stay


def test_another_admin_of_the_same_company_cannot_see_edit_or_delete_my_draft(world):
    mine, other = world.login("mine", "co-a"), world.login("other", "co-a")
    sid = create(mine)["id"]
    for r in (other.get(f"{BASE}/sessions/{sid}"), other.put(f"{BASE}/sessions/{sid}", json={"purpose": "Hijack"}),
              other.delete(f"{BASE}/sessions/{sid}?confirm=yes"),
              other.post(f"{BASE}/templates", json={"name": "t", "session_id": sid})):
        assert (r.status_code, r.json()) == (404, NOT_THERE)
    assert other.get(f"{BASE}/sessions").json() == []
    assert mine.get(f"{BASE}/sessions/{sid}").json()["preparation"]["purpose"] == draft()["purpose"]


def test_started_session_preparation_is_read_only(world):
    c = world.login("org", "co-a")
    s = create(c)
    from modules.m1_intent.store.sessions import SessionStore
    SessionStore(world.plane("co-a")).transition(s["id"], "lobby")  # starting belongs to M1-P02
    got = c.get(f"{BASE}/sessions/{s['id']}").json()
    assert got["editable"] is False
    r = c.put(f"{BASE}/sessions/{s['id']}", json={"purpose": "Changed after the start"})
    assert r.status_code == 409 and "started" in r.json()["message"]
    assert c.get(f"{BASE}/sessions/{s['id']}").json()["preparation"]["purpose"] == draft()["purpose"]
    r = c.delete(f"{BASE}/sessions/{s['id']}?confirm=yes")
    assert r.status_code == 409


def test_state_and_ownership_cannot_be_set_from_the_request(world):
    c = world.login("org", "co-a")
    for extra in ({"state": "closed"}, {"company_id": "co-b"}, {"organiser_account_id": "x"}, {"id": "a" * 32}):
        r = c.post(f"{BASE}/sessions", json=draft(**extra))
        assert r.status_code == 422, extra
    s = create(c)
    assert c.put(f"{BASE}/sessions/{s['id']}", json={"state": "board"}).status_code == 422


def test_bad_input_gets_plain_messages_not_technical_ones(world):
    c = world.login("org", "co-a")
    for body in (draft(seats=0), draft(seats=11), draft(length_minutes=30, split={"briefing": 1, "individual": 1, "together": 1}),
                 {"outcome": "no purpose"}):
        r = c.post(f"{BASE}/sessions", json=body)
        assert r.status_code == 422
        j = r.json()
        assert j["error"] == "invalid" and isinstance(j["message"], str) and "detail" not in j
        assert not any(w in j["message"].lower() for w in ("json", "field required", "traceback", "validation"))
    assert c.post(f"{BASE}/sessions", content=b"not json", headers={"content-type": "application/json"}).status_code == 400
    assert c.post(f"{BASE}/sessions", json=[1, 2]).status_code == 400
    assert c.get(f"{BASE}/sessions").json() == []  # nothing half-made


def test_company_comes_from_the_server_session_never_the_request(world):
    c = world.login("org", "co-a")
    r = c.post(f"{BASE}/sessions?company_id=co-b", json=draft())
    assert r.status_code == 201
    assert len(world.login("b", "co-b").get(f"{BASE}/sessions").json()) == 0
    assert len(list(world.plane("co-b").area("intents").rglob("*.json"))) == 0
    assert len(list(world.plane("co-a").area("intents").rglob("sessions/*.json"))) == 1


def test_a_malformed_session_id_is_not_found_not_an_error(world):
    c = world.login("org", "co-a")
    for bad in ("..", "nothex", "A" * 32, "a" * 33):
        assert c.get(f"{BASE}/sessions/{bad}").status_code == 404
    assert c.get(f"{BASE}/sessions/{'a' * 32}").json() == NOT_THERE


# ---- delete ----------------------------------------------------------------------------------------------------
def test_delete_a_draft_needs_an_explicit_confirmation(world):
    c = world.login("org", "co-a")
    sid = create(c)["id"]
    r = c.delete(f"{BASE}/sessions/{sid}")
    assert r.status_code == 400 and "confirm" in r.json()["message"].lower()
    assert c.get(f"{BASE}/sessions/{sid}").status_code == 200
    assert c.delete(f"{BASE}/sessions/{sid}?confirm=yes").status_code == 200
    assert c.get(f"{BASE}/sessions/{sid}").status_code == 404
    assert c.get(f"{BASE}/sessions").json() == []


# ---- templates -------------------------------------------------------------------------------------------------
def test_save_as_template_then_start_a_new_draft_from_it(world):
    c = world.login("org", "co-a")
    s = create(c, seats=4, length_minutes=30, split={"briefing": 5, "individual": 15, "together": 10},
               approver_name="Chief Anybody", charter_template="short")
    r = c.post(f"{BASE}/templates", json={"name": "Quarterly review", "session_id": s["id"]})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert [t["name"] for t in c.get(f"{BASE}/templates").json()] == ["Quarterly review"]
    new = c.post(f"{BASE}/sessions", json={"from_template": tid}).json()
    assert new["id"] != s["id"] and new["state"] == "draft"
    assert new["preparation"] == {**s["preparation"], "topic": None}  # the same values; the topic is chosen per wall, never inherited (IC-2t)
    over = c.post(f"{BASE}/sessions", json={"from_template": tid, "purpose": "Different purpose"}).json()
    assert over["preparation"]["purpose"] == "Different purpose" and over["preparation"]["seats"] == 4
    assert c.post(f"{BASE}/sessions", json={"from_template": "f" * 32}).status_code == 404


def test_templates_are_per_company(world):
    a, b = world.login("a", "co-a"), world.login("b", "co-b")
    sid = create(a)["id"]
    a.post(f"{BASE}/templates", json={"name": "Mine", "session_id": sid})
    assert b.get(f"{BASE}/templates").json() == []
    assert b.post(f"{BASE}/templates", json={"name": "x", "session_id": sid}).status_code == 404


def test_template_name_is_required_and_capped(world):
    c = world.login("org", "co-a")
    sid = create(c)["id"]
    for name in ("", "  ", "n" * 81, None, 3):
        assert c.post(f"{BASE}/templates", json={"name": name, "session_id": sid}).status_code == 422


# ---- process record (D-026, A-026) ------------------------------------------------------------------------------
def test_first_save_creates_the_process_record_and_both_ways_work(world):
    c = world.login("org", "co-a")
    s = create(c)
    recs = ProcessRecords(world.plane("co-a")).list(module_id="m1_intent")
    assert len(recs) == 1 and recs[0].outcome_id == s["outcome_id"]
    assert (recs[0].session_state, recs[0].outcome_state) == ("in_progress", "in_progress")
    assert c.get(f"{BASE}/sessions/{s['id']}").json()["outcome_id"] == s["outcome_id"]  # draft finds its outcome
    back = c.get(f"{BASE}/outcomes/{s['outcome_id']}")  # outcome opens its session
    assert back.status_code == 200 and back.json()["session"]["id"] == s["id"] and back.json()["status"] == "in_progress"  # no record before sign-off
    c.put(f"{BASE}/sessions/{s['id']}", json={"purpose": "Edited"})
    assert len(ProcessRecords(world.plane("co-a")).list(module_id="m1_intent")) == 1  # an edit makes no new record


def test_a_second_company_cannot_open_it_either_way(world):
    a, b = world.login("a", "co-a"), world.login("b", "co-b")
    s = create(a)
    assert b.get(f"{BASE}/outcomes/{s['outcome_id']}").status_code == 404
    assert b.get(f"{BASE}/sessions/{s['id']}").status_code == 404
    assert ProcessRecords(world.plane("co-b")).list() == []


def test_the_outcome_route_is_organiser_only_too(world):
    s = create(world.login("a", "co-a"))
    other = world.login("other", "co-a")
    assert other.get(f"{BASE}/outcomes/{s['outcome_id']}").status_code == 404


def test_deleting_a_draft_marks_its_record_completed_not_deleted(world):
    c = world.login("org", "co-a")
    s = create(c)
    c.delete(f"{BASE}/sessions/{s['id']}?confirm=yes")
    rec = ProcessRecords(world.plane("co-a")).list(module_id="m1_intent")[0]
    assert rec.session_state == "completed" and rec.outcome_state == "in_progress"
    assert c.get(f"{BASE}/outcomes/{s['outcome_id']}").status_code == 404


# ---- M1-31: solo, empty company, two industries --------------------------------------------------------------
def test_empty_company_gets_honest_empty_answers(world):
    c = world.login("org", "co-empty")
    assert c.get(f"{BASE}/sessions").json() == []
    assert c.get(f"{BASE}/templates").json() == []
    assert c.get(f"{BASE}/lists").status_code == 200
    assert c.get(f"{BASE}/outcomes/{'a' * 32}").status_code == 404


def test_a_solo_user_prepares_a_one_seat_session_alone(world):
    c = world.login("solo", "co-solo", ["company_admin", "sponsor"])
    s = create(c, seats=1)
    assert s["is_solo"] is True and s["preparation"]["seats"] == 1
    assert c.put(f"{BASE}/sessions/{s['id']}", json={"seats": 1, "purpose": "Solo run"}).status_code == 200
    assert [x["id"] for x in c.get(f"{BASE}/sessions").json()] == [s["id"]]


@pytest.mark.parametrize("company", ["co-a", "co-b", "co-none", "co-empty", "co-solo"])
def test_the_same_assertions_hold_for_every_company(world, company):
    c = world.login("org", company)
    s = create(c)
    assert c.get(f"{BASE}/sessions/{s['id']}").json()["state"] == "draft"
    assert [x["state"] for x in c.get(f"{BASE}/sessions").json()] == ["draft"]
    assert c.put(f"{BASE}/sessions/{s['id']}", json={"seats": 11}).status_code == 422
    assert c.delete(f"{BASE}/sessions/{s['id']}?confirm=yes").status_code == 200


def test_list_shows_label_state_and_seats_but_no_ids_of_other_people(world):
    c = world.login("org", "co-a")
    s = create(c)
    row = c.get(f"{BASE}/sessions").json()[0]
    assert row["id"] == s["id"] and row["state"] == "draft" and row["label"] == draft()["purpose"]
    assert "organiser_account_id" not in row and "organiser_account_id" not in s
    assert world.login("x", "co-a").get(f"{BASE}/sessions").json() == []
