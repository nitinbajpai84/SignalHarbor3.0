"""B06: people and roles in an intent. Invite, accept, decline with reason, role change, removal kept, affected told once, and what each viewer sees."""
import json
from types import SimpleNamespace

import pytest
from test_b12 import world  # noqa: F401  the wall fixture lives with the wall tests

from sh_platform.intents import events as EV
from sh_platform.intents import lifecycle as L
from sh_platform.intents import people as P
from sh_platform.intents import store as S
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile import store

ORG, AARON, KATIE, HARVEY, GRACE, ZED = "a-org", "a-aaron", "a-katie", "a-harvey", "a-grace", "a-zed"
NAMES = {ORG: "Janet Shaw", AARON: "Aaron Lyle", KATIE: "Katie Menon", HARVEY: "Harvey Rowley", GRACE: "Grace Ward", ZED: "Zed Ops"}
BOSS = ("company_admin",)


class Accounts:
    def in_company(self, _):
        return [{"account_id": k, "display_name": v, "roles": ["participant"], "disabled": False} for k, v in NAMES.items()]

    def get(self, aid):
        return {"display_name": NAMES.get(aid)}


def req(account, roles=("participant",), **q):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(account_store=Accounts())), query_params=q,
                           state=SimpleNamespace(company_id="fam", account_id=account, roles=list(roles)))


ID = {}


@pytest.fixture
def plane(tmp_path):
    pl = PlaneStore(tmp_path).create("fam").ensure()
    prof = store.empty()
    cell = lambda v: {"value": v, "mark": "stated"}  # noqa: E731
    prof["areas"] = {"ops": {"name": cell("Operations"), "kind": cell("operations_area")}}
    prof["people"] = {k: {"name": cell(n), "account_id": cell(a), "areas": cell(["ops"]), "team": cell("Operations")}
                      for k, n, a in (("z", "Zed Ops", ZED), ("g", "Grace Ward", GRACE))}
    write_json_atomic(pl.path("context", "profile", "profile.json"), prof)
    rec = L.new_record("brainstorm", "fam", L.person(ORG, NAMES[ORG]), "2026-10-01T00:00:00Z", title="Month-end", purpose="Cut it", areas=["ops"])
    rec.update(state="open", time_box={"starts": "", "ends": "2026-10-10T10:00:00Z", "extended_by": []})
    S.create_intent(pl, rec)
    ID["i"] = rec["id"]
    return pl


def intent(pl):
    return S.read_intent(pl, ID["i"])


def detail(pl):
    return P._detail(pl, ID["i"])


def events(pl):
    return EV.read_events(pl, ID["i"])


def invite(pl, body, who=ORG):
    return P._invite(pl, req(who, BOSS), ID["i"], body)


def entry(pl, pid):
    return P._entry(detail(pl), pid)


def joined(pl, pid):
    invite(pl, {"people": [{"person_id": pid}]})
    P._answer(pl, req(pid), ID["i"], pid, {"action": "accept"})


def test_invite_writes_invited_with_record_and_event(plane):
    out = invite(plane, {"people": [{"person_id": AARON}, {"person_id": KATIE, "role": "observer"}]})
    assert out == {"invited": [AARON, KATIE]}
    a = entry(plane, AARON)
    assert (a["role"], a["status"], a["via"], a["required"], a["invited_by"]) == ("participant", "invited", "picked", True, ORG)
    assert entry(plane, KATIE)["required"] is False
    i = intent(plane)
    assert [x["account_id"] for x in i["people"]["participants"]] == [AARON] and [x["account_id"] for x in i["people"]["observers"]] == [KATIE]
    assert i["people"]["organiser"]["account_id"] == ORG
    assert [p["person_id"] for p in i["people_detail"]] == [ORG, AARON, KATIE]  # the list lives on the record
    assert [e["kind"] for e in events(plane)] == ["person_invited"] * 2 and [h["kind"] for h in detail(plane)["history"]] == ["invited"] * 2


def test_invite_refuses_non_organiser_and_draft(plane):
    with pytest.raises(P.Refuse):
        invite(plane, {"people": [{"person_id": AARON}]}, who=AARON)
    S.update_intent(plane, ID["i"], intent(plane)["version"], lambda r: r.update(state="draft"))
    with pytest.raises(P.Refuse) as e:
        invite(plane, {"people": [{"person_id": AARON}]})
    assert e.value.status == 409


def test_accept_and_decline_with_reason(plane):
    invite(plane, {"people": [{"person_id": AARON}, {"person_id": KATIE}]})
    P._answer(plane, req(AARON), ID["i"], AARON, {"action": "accept"})
    assert entry(plane, AARON)["status"] == "joined" and entry(plane, AARON)["joined_at"]
    with pytest.raises(P.Refuse) as e:  # a participant must give a reason
        P._answer(plane, req(KATIE), ID["i"], KATIE, {"action": "decline"})
    assert e.value.status == 422
    P._answer(plane, req(KATIE), ID["i"], KATIE, {"action": "decline", "reason": "On leave until 14 Oct"})
    k = entry(plane, KATIE)
    assert k["status"] == "declined" and k["declined"]["reason"] == "On leave until 14 Oct"
    mine = {x["account_id"]: x.get("status") for x in intent(plane)["people"]["participants"]}  # the brainstorm reads the same words
    assert mine == {AARON: "Accepted", KATIE: "Declined"}
    with pytest.raises(P.Refuse):  # nobody answers for another person
        P._answer(plane, req(AARON), ID["i"], KATIE, {"action": "accept"})
    with pytest.raises(P.Refuse):  # no second answer
        P._answer(plane, req(AARON), ID["i"], AARON, {"action": "decline", "reason": "x"})


def test_role_change_needs_reason_and_is_kept(plane):
    joined(plane, HARVEY)
    org = req(ORG, BOSS)
    with pytest.raises(P.Refuse):
        P._role(plane, org, ID["i"], HARVEY, {"role": "observer"})
    P._role(plane, org, ID["i"], HARVEY, {"role": "observer", "reason": "Covering a deadline"})
    h = entry(plane, HARVEY)
    assert h["role"] == "observer" and h["required"] is False and h["role_history"][0]["reason"] == "Covering a deadline"
    assert [x["account_id"] for x in intent(plane)["people"]["observers"]] == [HARVEY] and detail(plane)["history"][-1]["kind"] == "role_changed"
    with pytest.raises(P.Refuse):  # a role the type does not use
        P._role(plane, org, ID["i"], HARVEY, {"role": "decider"})
    with pytest.raises(P.Refuse) as e:  # the organiser cannot demote themselves
        P._role(plane, org, ID["i"], ORG, {"role": "observer", "reason": "x"})
    assert e.value.status in (404, 409)


def test_removal_is_kept_with_reason_and_can_be_invited_again(plane):
    invite(plane, {"people": [{"person_id": AARON}]})
    joined(plane, KATIE)
    org = req(ORG, BOSS)
    with pytest.raises(P.Refuse):
        P._remove(plane, org, ID["i"], AARON, {})
    P._remove(plane, org, ID["i"], AARON, {"reason": "Wrong team"})
    a = entry(plane, AARON)
    assert a["status"] == "removed" and a["removed"]["reason"] == "Wrong team" and AARON not in [x["account_id"] for x in intent(plane)["people"]["participants"]]
    # a participant never sees the removed person; the organiser sees the person and the reason
    assert AARON not in [p["person_id"] for p in P._view(req(KATIE), plane, intent(plane), detail(plane))["people"]]
    v = P._view(org, plane, intent(plane), detail(plane))
    assert [p["removed"]["reason"] for p in v["people"] if p["person_id"] == AARON] == ["Wrong team"]
    invite(plane, {"people": [{"person_id": AARON}]})
    assert entry(plane, AARON)["status"] == "invited" and entry(plane, AARON)["removed"] is None
    assert [h["kind"] for h in detail(plane)["history"] if h["person"] == NAMES[AARON]] == ["invited", "removed", "invited"]


def test_affected_told_once_and_see_names_and_roles_only(plane):
    invite(plane, {"areas": ["ops"]})
    told = [p for p in detail(plane)["people_detail"] if p["role"] != "organiser"]  # the organiser is listed too, as Joined
    assert sorted(p["person_id"] for p in told) == [GRACE, ZED]
    assert all(p["role"] == "affected" and p["via"] == "area" and p["required"] is False for p in told)
    n = len(events(plane))
    invite(plane, {"areas": ["ops"], "people": [{"person_id": GRACE, "role": "affected"}]})  # again: nobody told twice
    assert len(events(plane)) == n and len(detail(plane)["people_detail"]) == 3
    v = P._view(req(GRACE), plane, intent(plane), detail(plane))
    assert v["level"] == "affected" and all(set(p) == {"person_id", "name", "role"} for p in v["people"])
    assert v["counts"]["not_answered"] == 0 and v["history"] == [] and "declined" not in v["counts"]
    with pytest.raises(P.Refuse) as e:  # an area that is not the intent's
        invite(plane, {"areas": ["Legal"]})
    assert e.value.status == 422


def test_decline_reasons_reach_only_the_organiser(plane):
    invite(plane, {"people": [{"person_id": AARON}, {"person_id": KATIE}]})
    P._answer(plane, req(KATIE), ID["i"], KATIE, {"action": "decline", "reason": "private reason"})
    P._answer(plane, req(AARON), ID["i"], AARON, {"action": "accept"})
    for who, roles in ((AARON, ("participant",)), ("a-boss2", BOSS), (ZED, ("participant",))):
        assert "private reason" not in json.dumps(P._view(req(who, roles), plane, intent(plane), detail(plane)))
    assert "private reason" in json.dumps(P._view(req(ORG, BOSS), plane, intent(plane), detail(plane)))
    v = P._view(req(ZED), plane, intent(plane), detail(plane))  # tagged to the area, not named: the organiser and nothing else
    assert v["level"] == "area" and [p["role"] for p in v["people"]] == ["organiser"] and v["counts"] is None
    with pytest.raises(P.Refuse) as e:  # no part, no area, no admin role: the intent is not there for them
        P._view(req("a-outsider"), plane, intent(plane), detail(plane))
    assert e.value.status == 404


def test_remind_drafts_only_and_writes_reminder_entry(plane):
    invite(plane, {"people": [{"person_id": AARON}], "areas": ["ops"]})
    out = P._remind(plane, req(ORG, BOSS), ID["i"], [AARON, GRACE])
    assert [d["person_id"] for d in out] == [AARON]  # affected people are not reminded
    assert entry(plane, AARON)["reminders"][0]["sent_note"] is None and detail(plane)["history"][-1]["kind"] == "reminded"
    assert len(P._remind(plane, req(ORG, BOSS), ID["i"], [AARON])) == 1 and len(entry(plane, AARON)["reminders"]) == 1  # cooldown: draft again, record once


def test_people_the_record_names_are_adopted_and_closed_intents_refuse(plane):
    S.update_intent(plane, ID["i"], intent(plane)["version"], lambda r: r["people"]["participants"].append(L.person(AARON, NAMES[AARON])))
    v = P._view(req(ORG, BOSS), plane, *_fresh(plane))
    assert {p["person_id"]: p["status"] for p in v["people"]} == {ORG: "joined", AARON: "invited"}
    S.update_intent(plane, ID["i"], intent(plane)["version"], lambda r: r.update(state="cancelled"))
    with pytest.raises(P.Refuse) as e:
        invite(plane, {"people": [{"person_id": KATIE}]})
    assert e.value.message == "This intent has closed."


def _fresh(plane):
    rec, det = intent(plane), detail(plane)
    P._adopt(rec, det)
    return rec, det


def test_area_written_as_a_name_still_tells_the_people_in_it(plane):
    S.update_intent(plane, ID["i"], intent(plane)["version"], lambda r: r.update(areas=["Operations"]))
    invite(plane, {"areas": ["ops"]})
    assert sorted(p["person_id"] for p in detail(plane)["people_detail"] if p["role"] == "affected") == [GRACE, ZED]
    assert P._view(req(ORG, BOSS), plane, intent(plane), detail(plane))["intent"]["areas"] == [{"id": "ops", "name": "Operations"}]


def test_an_answer_given_on_the_record_reaches_the_list(plane):
    invite(plane, {"people": [{"person_id": AARON}, {"person_id": KATIE}]})
    def answer(r):
        for x in r["people"]["participants"]:
            x.update(status="Accepted" if x["account_id"] == AARON else "Declined", reason="On leave" if x["account_id"] == KATIE else None)
    S.update_intent(plane, ID["i"], intent(plane)["version"], answer)
    v = P._view(req(ORG, BOSS), plane, *_fresh(plane))
    assert {p["person_id"]: p["status"] for p in v["people"]} == {ORG: "joined", AARON: "joined", KATIE: "declined"}
    assert [p["declined"]["reason"] for p in v["people"] if p["person_id"] == KATIE] == ["On leave"]


def test_relation_admits_a_person_named_only_as_a_process_owner(plane):
    from sh_platform.intents import define as D
    write_json_atomic(plane.path("intents", ID["i"], "processes.json"), {"processes": [{"owner": NAMES[ZED]}]})
    who = {"id": ZED, "name": NAMES[ZED], "roles": {"participant"}, "keys": {ZED, NAMES[ZED].lower()}}
    assert D.relation(intent(plane), who)["reader"] is False
    assert D.relation(intent(plane), who, plane)["reader"] is True


def test_no_line_says_for_your_information_and_the_people_hooks_run(plane):
    invite(plane, {"people": [{"person_id": AARON}, {"person_id": ZED, "role": "affected"}]})
    text = json.dumps(P._drafts(intent(plane), detail(plane), None, "http://x")) + json.dumps(P.pulse_people(plane, SimpleNamespace(account_id=ZED), None))
    assert "For your information" not in text and "Nothing is asked of you" in text
    P.record_join(plane, ID["i"], AARON, NAMES[AARON], "s1", 2)
    assert entry(plane, AARON)["status"] == "joined"
    P.mark_contributed(plane, ID["i"], AARON)
    assert entry(plane, AARON)["status"] == "contributed"
    P.mark_confirmed(plane, ID["i"], AARON, "define")
    assert entry(plane, AARON)["status"] == "confirmed"


def test_confirming_in_a_baseline_marks_the_person_on_its_intent(plane):
    S.update_intent(plane, ID["i"], intent(plane)["version"], lambda r: r["refs"].update(baseline_ids=["b1"]))
    joined(plane, AARON)
    P.confirmed_in_baseline(plane, "b1", NAMES[AARON], Accounts().in_company(None))
    assert entry(plane, AARON)["status"] == "confirmed"


def test_quarters_on_the_organiser_wall(world):  # noqa: F811
    from test_b12 import card, get, intent as wall_intent  # noqa: PLC0415
    wall_intent(world)
    card(world, "c1")  # q1 only
    store.record(world.plane, "cards.c1.q2", "Every Monday", {"mark": "stated", "by": "Test", "from": "A note"})
    assert get(world, "janet", "company_admin").json()["quarters"] == {"c1": 2}
    assert get(world, "aaron").json()["quarters"] is None


def test_people_count_includes_people_named_without_an_account(plane):
    invite(plane, {"people": [{"person_id": AARON}]})
    S.update_intent(plane, ID["i"], intent(plane)["version"],
                    lambda r: r["people"].setdefault("participants", []).extend([{"name": "Marcus Todd"}, {"name": "aaron lyle"}]))
    c = P._counts(detail(plane), "organiser", intent(plane))
    assert c["people"] == 3 and c["named"] == 2  # Janet, Aaron and Marcus; Aaron is not counted twice
    assert P._counts(detail(plane), "organiser")["people"] == 2  # the list alone, as before


# ---- F43 (SEC0 #4, #5): the list shows person ids, never another person's account id; a hidden intent answers like a missing one

def test_people_list_shows_person_ids_and_takes_them_back(plane):
    invite(plane, {"areas": ["ops"]})  # Grace (g) and Zed (z) are linked profile people
    org = req(ORG, BOSS)
    out = P._masked(org, plane, P._view(org, plane, intent(plane), detail(plane)))
    text = json.dumps(out)
    assert GRACE not in text and ZED not in text
    assert {p["person_id"] for p in out["people"]} == {ORG, "g", "z"}  # the organiser keeps her own account id
    assert P._acct(org, plane, "g") == GRACE and P._acct(org, plane, ORG) == ORG and P._acct(org, plane, "guest-x") == "guest-x"
    hashed = S.public_ref("f" * 32, {})
    assert hashed.startswith("acct-") and "f" * 32 not in hashed and S.account_for(hashed, {}, ["f" * 32]) == "f" * 32


def test_answer_on_a_hidden_intent_is_the_same_404_as_a_missing_one(plane):
    for iid in (ID["i"], "bra-" + "0" * 32):
        with pytest.raises(P.Refuse) as e:
            P._answer(plane, req("a-outsider"), iid, "a-outsider", {"action": "accept"})
        assert (e.value.status, e.value.message) == (404, P.NOT_FOUND), iid


def test_who_has_not_acted_and_next_answer_a_hidden_intent_like_a_missing_one(plane, tmp_path):  # F43, SEC0 #5
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sh_platform.intents import links, nira
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = Accounts()
    app.include_router(nira.router)
    app.include_router(links.router)

    @app.middleware("http")
    async def who(request, call_next):
        request.state.company_id, request.state.account_id = "fam", request.headers["x-acct"]
        request.state.roles = request.headers.get("x-roles", "participant").split(",")
        return await call_next(request)
    c, missing = TestClient(app), "bra-" + "0" * 32
    for method, tail in (("GET", "who-has-not-acted"), ("POST", "next")):
        hidden = c.request(method, f"/api/intents/{ID['i']}/{tail}", headers={"x-acct": "a-outsider"})
        gone = c.request(method, f"/api/intents/{missing}/{tail}", headers={"x-acct": "a-outsider"})
        assert hidden.status_code == gone.status_code == 404 and hidden.json() == gone.json(), tail
    invite(plane, {"areas": ["ops"]})
    out = c.get(f"/api/intents/{ID['i']}/who-has-not-acted", headers={"x-acct": ORG, "x-roles": "company_admin"})
    assert out.status_code == 200 and GRACE not in out.text and ZED not in out.text


def test_company_list_carries_the_sponsor_flag_and_ref(plane):  # the Initiative start screen's sponsor guess (F46 follow-up)
    store.record(plane, "people.g.is_sponsor", True, {"mark": "stated", "by": "Test", "from": "Roster"})
    rows = {p["name"]: p for p in P._company_people(req(ORG, BOSS), plane)}
    assert rows["Grace Ward"]["is_sponsor"] is True and rows["Zed Ops"]["is_sponsor"] is False and rows["Aaron Lyle"]["is_sponsor"] is False


def test_type_own_action_hides_the_invitation_card_and_a_passer_leaves_the_list(plane):
    invite(plane, {"people": [{"person_id": AARON}]})
    S.update_intent(plane, ID["i"], intent(plane)["version"], lambda r: r["people"].update(sponsor=L.person(KATIE, NAMES[KATIE])))

    def card(pid):
        return P._view(req(pid), plane, *_fresh(plane))["invitation"]
    assert card(AARON) is not None
    e = {"person_id": KATIE, "name": NAMES[KATIE], "role": "sponsor", "status": "invited", "invited_by": ORG}
    rec = intent(plane)
    assert P._invitation(plane, rec, e, NAMES, None) is not None
    S.update_intent(plane, ID["i"], rec["version"], lambda r: r["outcome"].update(signed_by=NAMES[KATIE]))
    assert P._invitation(plane, intent(plane), e, NAMES, None) is None  # signed: no "asked to sponsor" card
    prob = {"type": "problem", "people": {"owner": None}, "passes": [{"from_id": GRACE}]}
    det = {"people_detail": [{"person_id": GRACE, "role": "participant", "status": "invited"}, {"person_id": ZED, "role": "participant", "status": "joined"}]}
    P._tidy_problem(prob, det)
    assert [x["person_id"] for x in det["people_detail"]] == [ZED]
    assert P._invitation(plane, {**prob, "state": "open", "type": "problem"}, {**e, "role": "owner"}, NAMES, None) is None  # the Problem's own Accept


def test_invitation_email_gives_the_stage_close_date_not_the_intent_end(plane):  # F51
    S.update_intent(plane, ID["i"], intent(plane)["version"], lambda r: r.update(
        stages=[{"key": "think_unfiltered", "state": "open", "opened_at": "2026-10-07T07:00:00+00:00", "closed_at": None, "due": "2026-10-12T07:00:00+00:00"}]))
    out = invite(plane, {"people": [{"person_id": AARON}]})
    assert out == {"invited": [AARON]}
    body = P._drafts(intent(plane), detail(plane), P._tz(plane), "")["invite"]["body"]
    assert "The wall closes 12 Oct." in body and "10 Oct" not in body


def test_inviting_gives_a_wall_seat_when_the_room_exists(plane, monkeypatch):  # F51
    taken = []

    class Room:
        def __init__(self, _plane): ...
        def get(self, sid): return {"seats": [{"n": 1, "state": "taken"}, {"n": 2, "state": "free"}, {"n": 3, "state": "free"}]}
        def seat_of_account(self, sid, who): return None
        def take(self, sid, n, name, role, account_id):
            taken.append((n, name, account_id)); return {"n": n}, None
    monkeypatch.setattr("modules.m1_intent.store.room.RoomStore", Room)
    sid = "a" * 32
    S.update_intent(plane, ID["i"], intent(plane)["version"], lambda r: r["refs"].update(wall_session_ids=[sid]))
    invite(plane, {"people": [{"person_id": AARON}]})
    assert taken and taken[0][1:] == ("Aaron Lyle", AARON)
    assert entry(plane, AARON)["status"] == "joined"
