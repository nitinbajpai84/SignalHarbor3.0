"""B20 (35, 36): the Brainstorm start and the live session. Synthetic people; a small app with only the records and brainstorm routers."""
import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sh_platform.egress import rows
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.intents import brainstorm as B
from sh_platform.intents import records, store as S
from sh_platform.plane import PlaneStore
from sh_platform.profile import store as profile_store

CO = "ardmore"
ACCTS = {"janet": "Janet Shaw", "aaron": "Aaron Lyle", "harvey": "Harvey Rowley", "marcus": "Marcus Todd", "grace": "Grace Ward", "daniel": "Daniel Kerr",
         "obs": "Olivia Observer", "zed": "Zed Lee", "root": "Platform"}
TEAMS = {"janet": "Strategy", "aaron": "Risk", "harvey": "Operations", "marcus": "Data", "grace": "Council", "daniel": "Investments", "obs": "Risk", "zed": "Legal"}
INVITED = ["aaron", "harvey", "marcus", "grace", "daniel"]


class Accounts:
    def get(self, aid):
        return {"display_name": ACCTS[aid]} if aid in ACCTS else None

    def in_company(self, company_id):
        return [{"account_id": a, "display_name": n, "disabled": False} for a, n in ACCTS.items() if a != "root"]


@pytest.fixture
def env(tmp_path):
    plane = PlaneStore(tmp_path).create(CO).ensure()
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = Accounts()
    app.include_router(records.router)
    app.include_router(B.router)

    @app.middleware("http")
    async def sign_in(request, call_next):
        who = request.headers.get("x-who", "janet")
        request.state.account_id, request.state.company_id = who, CO
        request.state.roles = ["company_admin"] if who == "janet" else ["super_admin"] if who == "root" else ["participant"]
        return await call_next(request)

    c = lambda v: {"value": v, "mark": "stated"}  # noqa: E731
    profile_store.mutate(plane, lambda d: d["people"].update(
        {f"p-{a}": {"name": c(ACCTS[a]), "team": c(t), "role": c("Staff"), "account_id": c(a)} for a, t in TEAMS.items()}))
    return SimpleNamespace(plane=plane, c=TestClient(app))


def call(env, who, method, path, body=None):
    return env.c.request(method, path, json=body if body is not None else {}, headers={"x-who": who})


def tomorrow() -> date:
    return B.next_workday(datetime.now(timezone.utc).date())


def answers(**over):
    a = {"statement": "Performance reviews take two weeks and nobody trusts the scores", "good_outcome": "One idea to test, with an owner",
         "people": [f"p-{x}" for x in INVITED], "areas": ["Risk"], "session_date": tomorrow().isoformat(), "session_time": "10:00", "session_minutes": 60,
         "anonymous_ideas": True}
    return {**a, **over}


def draft(env, **over):
    r = call(env, "janet", "POST", "/api/intents", {"type": "brainstorm"})
    assert r.status_code == 201, r.text
    iid = r.json()["id"]
    r = call(env, "janet", "POST", f"/api/intents/{iid}/session/draft", {"answers": answers(**over)})
    assert r.status_code == 200, r.text
    return iid


def launch(env, **over):
    iid = draft(env, **over)
    r = call(env, "janet", "POST", f"/api/intents/{iid}/session/launch", {})
    return iid, r


def opened(env, accept=INVITED, **over):
    iid, r = launch(env, **over)
    assert r.status_code == 200, r.text
    began = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()  # the box starts at 09:00 the day before: move it back so the tests do not depend on the hour
    S.update_intent(env.plane, iid, S.read_intent(env.plane, iid)["version"], lambda rec: rec["time_box"].update(starts=began))
    for a in accept:
        assert call(env, a, "POST", f"/api/intents/{iid}/session/answer", {"answer": "accept"}).status_code == 200
    return iid


def view(env, who, iid, q=""):
    return call(env, who, "GET", f"/api/intents/{iid}/session{q}")


def act(env, who, iid, name, body=None):
    return call(env, who, "POST", f"/api/intents/{iid}/session/{name}", body or {})


def idea(env, who, iid, text, **more):
    r = act(env, who, iid, "idea", {"text": text, **more})
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ---- the five questions ---------------------------------------------------------------------------------------------------------

def test_five_questions_each_named_when_missing():
    today = date(2026, 10, 7)  # a Wednesday
    ok = answers(session_date="2026-10-08")
    assert B.check_answers(ok, today) is None
    for key, words in [("statement", "idea or the problem"), ("good_outcome", "good outcome"), ("areas", "area"), ("session_minutes", "45 or 60")]:
        assert words in B.check_answers({**ok, key: "" if isinstance(ok[key], str) else None if key != "areas" else []}, today)
    assert "working day" in B.check_answers({**ok, "session_date": "2026-10-10"}, today)  # a Saturday
    assert "working day" in B.check_answers({**ok, "session_date": "2026-10-07"}, today)  # today: the day before must exist


def test_four_to_eight_people(env):
    today = datetime.now(timezone.utc).date()
    base = answers()
    assert "four to eight" in B.check_answers({**base, "people": ["a"] * 3}, today)
    assert "Take 1 off" in B.check_answers({**base, "people": [str(i) for i in range(9)]}, today)
    iid = draft(env, people=["p-aaron", "p-harvey", "p-marcus"])
    r = call(env, "janet", "POST", f"/api/intents/{iid}/session/launch", {})
    assert r.status_code == 422 and "four to eight" in r.json()["message"]
    iid = draft(env, people=["p-janet"] + [f"p-{x}" for x in INVITED[:3]])
    assert "organiser" in call(env, "janet", "POST", f"/api/intents/{iid}/session/launch", {}).json()["message"]
    assert call(env, "janet", "POST", f"/api/intents/{iid}/session/launch", {}).status_code == 422  # still a draft
    assert call(env, "janet", "GET", f"/api/intents/{iid}").json()["state"] == "draft"


def test_time_box_is_set_from_the_session_date(env):
    w = B.window(date(2026, 10, 15))  # a Thursday
    assert w == {"before": "2026-10-14", "session": "2026-10-15", "after": "2026-10-16"}
    assert B.window(date(2026, 10, 12))["before"] == "2026-10-09"  # Monday: the day before is the Friday
    assert B.window(date(2026, 10, 16))["after"] == "2026-10-19"  # Friday: the day after is the Monday
    iid, r = launch(env)
    assert r.status_code == 200, r.text
    rec = S.read_intent(env.plane, iid)
    assert rec["state"] == "open" and rec["time_box"]["starts"][:10] == B.window(tomorrow())["before"] and rec["time_box"]["ends"][:10] == B.window(tomorrow())["after"]
    assert rec["outcome"]["session_at"][:16] == f"{tomorrow().isoformat()}T10:00" and rec["session"]["phase"] == "not_opened"
    assert [p["status"] for p in rec["people"]["participants"]] == ["Invited"] * 5
    assert "Open it here" in r.json()["message"]["body"]  # the organiser copies it; nothing is sent


# ---- pre-thinking is private ----------------------------------------------------------------------------------------------------

def test_prethinking_is_private_until_the_session_opens(env):
    iid = opened(env)
    assert call(env, "zed", "GET", f"/api/intents/{iid}/session").status_code == 404  # not invited: not even a stub
    mine = idea(env, "aaron", iid, "Score reviews against agreed examples")
    idea(env, "harvey", iid, "Review once a quarter, not twice a year")
    assert [i["text"] for i in view(env, "aaron", iid).json()["ideas"]] == ["Score reviews against agreed examples"]
    assert view(env, "marcus", iid).json()["ideas"] == []
    org = view(env, "janet", iid).json()
    assert org["ideas"] == [] and org["prethink"] == {"authors": 2, "ideas": 2, "invited": 5}  # counts only, never content
    assert "Score reviews" not in json.dumps(org) and "quarter" not in json.dumps(org)
    assert act(env, "aaron", iid, "idea-edit", {"id": mine, "text": "Score reviews against examples"}).status_code == 200
    assert act(env, "harvey", iid, "idea-edit", {"id": mine, "text": "mine now"}).status_code == 403
    assert act(env, "janet", iid, "open").status_code == 200
    assert len(view(env, "marcus", iid).json()["ideas"]) == 2  # on the shared board now


def test_an_invited_person_must_accept_first(env):
    iid = opened(env, accept=["aaron"])
    v = view(env, "harvey", iid).json()
    assert v["mode"] == "invitation" and v["ideas"] == []
    assert act(env, "harvey", iid, "idea", {"text": "too early"}).status_code == 403
    assert act(env, "harvey", iid, "answer", {"answer": "decline"}).status_code == 422  # a decline needs a reason
    assert act(env, "harvey", iid, "answer", {"answer": "decline", "reason": "On leave"}).status_code == 200
    assert view(env, "harvey", iid).json()["mode"] == "declined"


# ---- phases, clock, controls ----------------------------------------------------------------------------------------------------

def test_phases_move_forward_by_the_organiser_only(env):
    iid = opened(env)
    assert act(env, "aaron", iid, "open").status_code == 403
    assert act(env, "janet", iid, "open").status_code == 200 and act(env, "janet", iid, "open").status_code == 409
    v = view(env, "aaron", iid).json()
    assert v["phase"] == "diverge" and v["remaining_seconds"] > 14 * 60 and "Do not judge" in v["prompts"]["diverge"]["text"]
    kept = idea(env, "aaron", iid, "Sweep cash each morning")
    assert act(env, "aaron", iid, "phase", {"to": "group"}).status_code == 403
    assert act(env, "janet", iid, "phase", {"to": "converge"}).status_code == 409  # no skipping
    assert act(env, "janet", iid, "phase", {"to": "group"}).status_code == 200
    assert act(env, "janet", iid, "phase", {"to": "converge"}).status_code == 200
    assert view(env, "aaron", iid).json()["phase"] == "converge" and act(env, "aaron", iid, "idea", {"text": "late"}).status_code == 409
    assert act(env, "aaron", iid, "idea-withdraw", {"id": kept}).status_code == 409  # the count's candidates stay put
    assert act(env, "janet", iid, "close").status_code == 200
    rec = S.read_intent(env.plane, iid)
    assert rec["session"]["phase"] == "closed" and rec["session"]["closed_early"] is False
    assert [s["state"] for s in rec["stages"]] == ["closed", "closed", "open"]  # the intent moves to Choose
    kinds = [json.loads(x)["kind"] for x in env.plane.path("intents", iid, "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert kinds == ["state_changed", "brainstorm_opened", "session_opened", "session_phase", "session_phase", "session_closed"]  # one line per act (ruling 12; the open also writes its state change)


def test_pause_stops_the_clock_and_adding(env):
    iid = opened(env)
    act(env, "janet", iid, "open")
    assert act(env, "janet", iid, "pause").status_code == 200
    a = view(env, "aaron", iid).json()
    assert a["paused"] and act(env, "aaron", iid, "idea", {"text": "during the pause"}).status_code == 409
    assert abs(view(env, "aaron", iid).json()["remaining_seconds"] - a["remaining_seconds"]) <= 1
    assert act(env, "janet", iid, "resume").status_code == 200
    assert act(env, "janet", iid, "add-time", {"minutes": 5, "reason": "Good flow"}).status_code == 200
    assert view(env, "aaron", iid).json()["remaining_seconds"] > 19 * 60
    s = {"phase": "diverge", "phase_started_at": "2026-10-07T10:00:00+00:00", "minutes": B.PHASE_MINUTES, "phase_paused_s": 60}
    assert B.remaining(s, datetime(2026, 10, 7, 10, 5, tzinfo=timezone.utc).timestamp()) == 15 * 60 - 4 * 60


# ---- North grouping, replies, anonymous ideas -----------------------------------------------------------------------------------

def test_north_groups_ideas_by_shared_words_and_regroups_on_request(env):
    iid = opened(env)
    act(env, "janet", iid, "open")
    assert act(env, "janet", iid, "group").status_code == 409  # fewer than two ideas: "Add ideas first"
    idea(env, "aaron", iid, "Pay custodians by a morning cash sweep")
    idea(env, "harvey", iid, "Sweep idle cash to the custodian each morning")
    idea(env, "marcus", iid, "Publish one dashboard of capital calls")
    v = view(env, "janet", iid).json()
    names = {g["name"]: g["count"] for g in v["groups"]}
    assert names.get("Custodian") == 2 or names.get("Sweep") == 2 or names.get("Cash") == 2, names
    assert v["grouped_by_words"] and v["ideas_count"] == 3
    grouped = {i["id"]: i["group_name"] for i in v["ideas"]}
    assert sum(1 for g in grouped.values() if g is None) == 1  # the dashboard idea is "not grouped yet"
    assert act(env, "janet", iid, "group").status_code == 200
    assert act(env, "aaron", iid, "group").status_code == 403  # Group again is the organiser's


def test_north_groups_through_the_runtime_and_falls_back_labelled(env, monkeypatch):
    """R14: the model groups; it sees idea ids and texts only, never an author or anonymous key; a failed call groups by words, labelled."""
    from sh_platform.intents import north as N
    env.c.app.state.entitlements, env.c.app.state.north_model_factory = object(), lambda p: object()
    sent = []

    def fake_call(plane_, model, gate, system, context, question):
        sent.append(json.dumps(context))
        assert rows.json_findings(json.dumps({"context": context, "question": question}))[0] is None  # the gateway would send it
        ids = list(context["ideas"])
        return json.dumps({"groups": [{"name": "Cash timing", "ids": ids[:2] + ["not-an-id"]}, {"name": "Lonely", "ids": ids[2:3]}]})
    monkeypatch.setattr(N, "_call", fake_call)
    monkeypatch.setattr(B, "_spawn", lambda fn: fn())  # the background grouping, inline
    iid = opened(env)
    act(env, "janet", iid, "open")
    idea(env, "aaron", iid, "Pay custodians by a morning cash sweep")
    idea(env, "marcus", iid, "Sweep idle cash each morning", anonymous=True)
    idea(env, "harvey", iid, "Publish one dashboard of capital calls")
    assert act(env, "janet", iid, "group").status_code == 200
    v = view(env, "janet", iid).json()
    assert [(g["name"], g["count"], g["fallback"]) for g in v["groups"]] == [("Cash timing", 2, False)] and not v["grouped_by_words"]
    assert sent and not any(x in blob for blob in sent for x in ("Aaron", "Marcus", "anon-", "owner", "author"))
    monkeypatch.setattr(N, "_call", lambda *a: None)  # the model cannot answer: shared words, and the screen says so
    assert act(env, "janet", iid, "group").status_code == 200
    v = view(env, "janet", iid).json()
    assert v["grouped_by_words"] and all(g["fallback"] for g in v["groups"])


def test_group_phase_people_move_cards_and_rename(env):
    iid = opened(env)
    act(env, "janet", iid, "open")
    a = idea(env, "aaron", iid, "Pay custodians by a morning cash sweep")
    idea(env, "harvey", iid, "Sweep idle cash to the custodian each morning")
    assert act(env, "aaron", iid, "move", {"id": a, "to": "new", "name": "Mine"}).status_code == 409  # diverge: no moves
    act(env, "janet", iid, "phase", {"to": "group"})
    assert act(env, "aaron", iid, "move", {"id": a, "to": "new", "name": "Mine"}).status_code == 200
    v = view(env, "marcus", iid).json()
    assert {g["name"] for g in v["groups"]} >= {"Mine"}
    gid = next(g["id"] for g in v["groups"] if g["name"] == "Mine")
    assert act(env, "marcus", iid, "rename", {"group_id": gid, "name": "Cash sweep"}).status_code == 200
    assert act(env, "obs", iid, "rename", {"group_id": gid, "name": "x"}).status_code == 404  # not in the intent
    assert act(env, "aaron", iid, "idea", {"text": "new ideas"}).status_code == 200  # the group phase still takes ideas


def test_replies_build_on_an_idea_and_are_not_ideas(env):
    iid = opened(env)
    i = idea(env, "aaron", iid, "Pay custodians by a morning cash sweep")
    r = call(env, "harvey", "POST", f"/api/intents/{iid}/cards/{i}/replies", {"text": "Only for balances over a set amount"})
    assert r.status_code == 409  # the session has not opened: no replies yet
    act(env, "janet", iid, "open")
    r = call(env, "harvey", "POST", f"/api/intents/{iid}/cards/{i}/replies", {"text": "Only for balances over a set amount"})
    assert r.status_code == 200, r.text
    v = view(env, "marcus", iid).json()
    card = v["ideas"][0]
    assert v["ideas_count"] == 1 and [x["text"] for x in card["replies"]] == ["Only for balances over a set amount"] and card["replies"][0]["author"] == "Harvey Rowley"
    assert call(env, "harvey", "POST", f"/api/intents/{iid}/cards/{i}/replies", {"text": " "}).status_code == 422


def test_anonymous_ideas_never_carry_a_name(env):
    iid = opened(env)
    act(env, "janet", iid, "open")
    secret = idea(env, "marcus", iid, "Ask Aaron Lyle to own the scoring", anonymous=True)
    idea(env, "aaron", iid, "A named idea")
    call(env, "harvey", "POST", f"/api/intents/{iid}/cards/{secret}/replies", {"text": "Agreed, hide me", "anonymous": True})
    for who in ("janet", "aaron", "harvey"):
        v = view(env, who, iid).json()
        card = next(i for i in v["ideas"] if i["anonymous"])
        assert card["author"] is None and "Aaron" not in card["text"] and "[name]" in card["text"]  # names are masked from the words too
        assert card["replies"][0]["author"] is None
        assert "Marcus" not in json.dumps(card)
    raw = (env.plane.path("intents", iid, "ideas.json")).read_text(encoding="utf-8")
    anon = next(i for i in json.loads(raw)["ideas"] if i["anonymous"])
    assert anon["author"] is None and anon["owner"].startswith("anon-") and "marcus" not in anon["owner"]
    idea(env, "marcus", iid, "Marcus would test this first", anonymous=True)  # the writer's own name never reaches the file
    assert "Marcus" not in env.plane.path("intents", iid, "ideas.json").read_text(encoding="utf-8")
    assert any(i["mine"] for i in view(env, "marcus", iid).json()["ideas"] if i["anonymous"])  # the author can still edit
    assert act(env, "marcus", iid, "idea-edit", {"id": secret, "text": "Still mine"}).status_code == 200
    assert act(env, "janet", iid, "idea-edit", {"id": secret, "text": "not mine"}).status_code == 403  # nobody else, the organiser included
    off = opened(env, anonymous_ideas=False)
    act(env, "janet", off, "open")
    assert act(env, "aaron", off, "idea", {"text": "hidden", "anonymous": True}).status_code == 422


def test_projector_and_observers_see_counts_not_words(env):
    iid = opened(env)
    act(env, "janet", iid, "open")
    idea(env, "aaron", iid, "Pay custodians by a morning cash sweep")
    idea(env, "harvey", iid, "Sweep idle cash to the custodian each morning")
    p = view(env, "janet", iid, "?display=projector").json()
    assert p["ideas_count"] == 2 and p["ideas"] == [] and "north_lines" not in p and "morning" not in json.dumps(p)
    assert p["statement"] and p["groups"]
    assert not any(n in json.dumps(p) for n in ("Aaron", "Harvey", "Marcus", "Grace", "Janet"))  # the room screen carries no names at all
    assert act(env, "obs", iid, "idea", {"text": "x"}).status_code == 404  # an observer must be named on the record
    rec = S.read_intent(env.plane, iid)
    rec["people"]["observers"] = [{"account_id": "obs", "person_id": "p-obs", "name": ACCTS["obs"]}]
    S.write_intent(env.plane, rec, expected_version=rec["version"])
    assert view(env, "obs", iid).json()["role"] == "observer"
    assert act(env, "obs", iid, "idea", {"text": "x"}).status_code == 403


def test_related_work_and_suggestions(env):
    first = opened(env, statement="Slow performance reviews")
    iid = draft(env, statement="Fix performance reviews")
    rel = call(env, "janet", "POST", f"/api/intents/{iid}/session/related", {"statement": "Performance reviews take two weeks"}).json()["related"]
    assert [r["ref"] for r in rel] == [first] and "review" in rel[0]["why"]
    assert call(env, "janet", "POST", f"/api/intents/{iid}/session/related", {"statement": "Zebra migration"}).json()["related"] == []
    s = call(env, "janet", "POST", f"/api/intents/{iid}/session/suggest-people", {"statement": "reviews", "areas": ["Risk"], "picked": []}).json()
    assert "p-janet" not in [p["id"] for p in s["people"]]  # the organiser is never offered
    risk = [p for p in s["people"] if p["team"] == "Risk"]
    assert risk and all(p["suggested"] and "Risk" in p["reason"] for p in risk)
    assert call(env, "aaron", "POST", f"/api/intents/{iid}/session/related", {"statement": "x"}).status_code == 404  # a draft is its organiser's alone


def test_group_again_keeps_the_groups_people_made_or_renamed(env, monkeypatch):
    """F10, rule 7: North's regroup (model or words) never overwrites a group people made or renamed; only the rest are grouped again."""
    from sh_platform.intents import north as N
    env.c.app.state.entitlements, env.c.app.state.north_model_factory = object(), lambda p: object()
    calls = []

    def fake_call(plane_, model, gate, system, context, question):
        ids = list(context["ideas"])
        from sh_platform.agents.guard import check_numbers
        assert check_numbers(" ".join(ids), [], question).text == " ".join(ids)  # the runtime's number guard leaves the idea ids whole
        calls.append(ids)
        return json.dumps({"groups": [{"name": "North pile", "ids": ids}]})
    monkeypatch.setattr(N, "_call", fake_call)
    monkeypatch.setattr(B, "_spawn", lambda fn: fn())  # the background grouping, inline
    iid = opened(env)
    act(env, "janet", iid, "open")
    a = idea(env, "aaron", iid, "Pay custodians by a morning cash sweep")
    b = idea(env, "harvey", iid, "Sweep idle cash each morning")
    idea(env, "marcus", iid, "Publish one dashboard of capital calls")
    idea(env, "grace", iid, "A dashboard for the council")
    act(env, "janet", iid, "phase", {"to": "group"})
    assert act(env, "aaron", iid, "move", {"id": a, "to": "new", "name": "Cash sweep"}).status_code == 200
    gid = next(g["id"] for g in view(env, "aaron", iid).json()["groups"] if g["name"] == "Cash sweep")
    assert act(env, "harvey", iid, "move", {"id": b, "to": gid}).status_code == 200
    assert act(env, "janet", iid, "group").status_code == 200
    v = view(env, "janet", iid).json()
    got = {g["name"]: g["count"] for g in v["groups"]}
    assert got == {"Cash sweep": 2, "North pile": 2} and a not in calls[-1] and b not in calls[-1]


# ---- F26: masking on read, withdraw guard once the count is open, seated count, the count's clock --------------------------------

def test_an_old_anonymous_card_is_masked_on_read_in_the_lane_and_in_converge(env):
    from sh_platform.intents import access as A
    from sh_platform.intents import converge as C
    iid = opened(env)
    act(env, "janet", iid, "open")
    secret = idea(env, "marcus", iid, "placeholder", anonymous=True)
    path = env.plane.path("intents", iid, "ideas.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    next(i for i in doc["ideas"] if i["id"] == secret)["text"] = "Zed Lee and Aaron would check the scores"  # written before the write-time mask
    path.write_text(json.dumps(doc), encoding="utf-8")
    for who in ("janet", "aaron", "harvey"):
        card = next(i for i in view(env, who, iid).json()["ideas"] if i["anonymous"])
        assert "Zed" not in card["text"] and "Aaron" not in card["text"]
    rec = A.load_intent(env.plane, iid)
    assert all("Zed" not in c["text"] and "Aaron" not in c["text"] for c in C.candidates(env.plane, rec))


def test_withdraw_is_refused_once_the_count_is_open(env):
    from sh_platform.intents import converge as C
    iid = opened(env)
    act(env, "janet", iid, "open")
    mine = idea(env, "aaron", iid, "One I might take back")
    C._mutate(env.plane, iid, lambda r, ev: C.ensure(r)["converge"].update(state="round_1_open"))
    r = act(env, "aaron", iid, "idea-withdraw", {"id": mine})
    assert r.status_code == 409 and "count has opened" in r.json()["message"]


def test_header_counts_seated_people_and_the_count_has_no_phase_clock(env):
    iid = opened(env, accept=["aaron", "harvey", "marcus"])
    act(env, "janet", iid, "open")
    assert view(env, "aaron", iid).json()["here"] == {"n": 4, "total": 6}  # organiser plus three accepted, of six on the list
    act(env, "janet", iid, "phase", {"to": "group"})
    act(env, "janet", iid, "phase", {"to": "converge"})
    v = view(env, "janet", iid).json()
    assert v["phase"] == "converge" and v["remaining_seconds"] is None and not any("clock is at zero" in x for x in v["north_lines"])
    assert v["ends"]


# ---- FX4: a bare-date time box, "Decided in", ideas in the group phase ---------------------------------------------------------

def test_view_survives_a_bare_date_start_and_lists_decisions_it_may_open(env):
    iid = opened(env)
    act(env, "janet", iid, "open")
    rec = S.read_intent(env.plane, iid)

    def seed(r):  # a seed record: a bare date for the start, and two links out
        r["time_box"]["starts"] = "2026-10-05"
        r["links"] = {"from": None, "to": ["dec-gone", "dec-here"], "build": None}
    S.update_intent(env.plane, iid, rec["version"], seed)
    dec = call(env, "janet", "POST", "/api/intents", {"type": "decision"}).json()["id"]
    r = S.read_intent(env.plane, dec)
    S.update_intent(env.plane, dec, r["version"], lambda x: x.update(title="Pick a custodian"))
    rec = S.read_intent(env.plane, iid)
    S.update_intent(env.plane, iid, rec["version"], lambda x: x["links"].update(to=["dec-gone", dec]))
    v = view(env, "janet", iid)
    assert v.status_code == 200, v.text
    assert v.json()["decided_in"] == [{"id": dec, "title": "Pick a custodian"}]  # the missing one is left out, no error


def test_ideas_can_be_added_in_the_group_phase(env):
    iid = opened(env)
    act(env, "janet", iid, "open")
    act(env, "janet", iid, "phase", {"to": "group"})
    assert view(env, "aaron", iid).json()["can_add"] is True
    assert act(env, "aaron", iid, "idea", {"text": "Add one in group"}).status_code == 200


def test_time_box_is_working_hours_in_the_company_zone():
    tz = timezone(timedelta(hours=8))
    box = B.time_box(date(2026, 10, 9), tz)
    assert box["starts"] == "2026-10-08T09:00:00+08:00" and box["ends"] == "2026-10-12T17:00:00+08:00"


def test_related_work_lists_each_piece_once(env):
    opened(env, statement="Slow performance reviews")
    opened(env, statement="Slow performance reviews")
    iid = draft(env, statement="Fix performance reviews")
    first = call(env, "janet", "POST", f"/api/intents/{iid}/session/related", {"statement": "Performance reviews take two weeks"}).json()["related"]
    titles = [(x["type"], x["title"].lower()) for x in first]
    assert first and len(titles) == len(set(titles)) and len({x["ref"] for x in first}) == len(first)
