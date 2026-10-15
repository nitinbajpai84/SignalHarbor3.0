"""B24: the Problem (specs 41, 42). A small app carries the router with a stand-in for sign-in; the plane is a temp folder of synthetic records."""
import json

import pytest
from sh_platform.egress import rows
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.intents import lifecycle as L
from sh_platform.intents import problem
from sh_platform.intents import store as S
from sh_platform.plane import PlaneStore

PEOPLE = {"aaron": ("Aaron Lyle", "Risk", "a-aaron", ["participant"]), "harvey": ("Harvey Rowley", "Fund Operations", "a-harvey", ["owner"]),
          "grace": ("Grace Ward", "Family Council Office", "a-grace", ["approver"]), "janet": ("Janet Shaw", "Strategy and Operations", "a-janet", ["company_admin"]),
          "katie": ("Katie Menon", "Investments", "a-katie", ["analyst"]), "daniel": ("Daniel Kerr", "Investments", "a-daniel", ["sponsor"]),
          "mei": ("Mei Ling", "Risk", "a-mei", ["participant"])}
ACCOUNTS = {v[2]: {"account_id": v[2], "display_name": v[0], "email": f"{k}@example.test", "roles": v[3], "disabled": False} for k, v in PEOPLE.items()}


class Store:
    def get(self, i): return ACCOUNTS.get(i)
    def in_company(self, c): return list(ACCOUNTS.values())


def cell(v): return {"value": v, "mark": "stated", "by": "Test", "at": "2026-10-01T00:00:00+00:00", "from": "test"}


@pytest.fixture
def env(tmp_path):
    plane = PlaneStore(tmp_path).create("acme").ensure()
    prof = {"version": 1, "inputs": {}, "systems": {}, "reported_figures": {}, "samples": {}, "interviews": {}, "constraints": {}, "cards": {},
            "governance": {"restricted_areas": {}, "field_rules": {}},
            "people": {k: {"name": cell(v[0]), "team": cell(v[1]), **({"owns": cell(["K02 Evidence coverage (business owner)"])} if k == "daniel" else {})} for k, v in PEOPLE.items()}}
    plane.path("context", "profile").mkdir(parents=True, exist_ok=True)
    plane.path("context", "profile", "profile.json").write_text(json.dumps(prof), encoding="utf-8")
    plane.path("graph").mkdir(parents=True, exist_ok=True)
    plane.path("graph", "company.json").write_text(json.dumps({"version": 1, "built_at": "x", "nodes": [
        {"id": "measure:K02", "type": "Measure", "label": "Evidence coverage", "provenance": [], "restricted_to": None},
        {"id": "person:daniel", "type": "Person", "label": "Daniel Kerr", "provenance": [], "restricted_to": None},
        {"id": "person:harvey", "type": "Person", "label": "Harvey Rowley", "provenance": [], "restricted_to": None}],
        "edges": [{"from": "measure:K02", "to": "person:daniel", "type": "owned_by", "provenance": []},
                  {"from": "measure:K02", "to": "person:harvey", "type": "owned_by", "provenance": []}]}), encoding="utf-8")
    plane.path("build", "pipelines").mkdir(parents=True, exist_ok=True)
    plane.path("build", "pipelines", "custodian.json").write_text(json.dumps({"source": "custodian_daily_file", "title": "Custodian daily file", "owner": "Harvey Rowley",
                                                                              "marts": ["gold.k02"]}), encoding="utf-8")
    app = FastAPI()
    app.state.settings = type("S", (), {"data_root": tmp_path})()
    app.state.account_store = Store()

    @app.middleware("http")
    async def who(request, call_next):
        a = ACCOUNTS[request.headers["x-acct"]]
        request.state.company_id, request.state.account_id, request.state.roles = "acme", a["account_id"], a["roles"]
        return await call_next(request)
    app.include_router(problem.router)
    return plane, TestClient(app)


def go(c, who, method, path, body=None):
    r = c.request(method, path, json=body, headers={"x-acct": PEOPLE[who][2]})
    return r


ANS = {"open": True, "what": "Monthly fee file arrives late", "saw": "The file came on the 5th, not the 2nd.", "bites": {"kind": "slowed", "count": 3},
       "about": {"id": "measure:K02"}, "owner": {"source": "source_owner", "name": "Harvey Rowley"}, "areas": ["Fund Operations"], "affected": ["Aaron Lyle", "Mei Ling"]}


def draft(plane, who="katie"):
    """A draft as the chooser leaves it (file 01), owned by `who`."""
    name, _, aid, _r = PEOPLE[who]
    rec = L.new_record("problem", "acme", L.person(aid, name), S.now_iso())
    S.create_intent(plane, rec)
    return rec["id"]


def opened(env, who="katie", **over):
    plane, c = env
    rid = draft(plane, who)
    r = go(c, who, "POST", f"/api/intents/{rid}/problem/start", {**ANS, **over})
    assert r.status_code == 200, r.text
    return rid


def accepted(env):
    rid = opened(env)
    assert go(env[1], "harvey", "POST", f"/api/intents/{rid}/triage/accept").status_code == 200
    return rid


def rec_of(plane, rid):
    return S.read_intent(plane, rid)


def closing_to_closed(plane, rid, katie="a-katie", harvey="a-harvey"):
    """What the closure screen (file 09) does: start closing, the owner then the reporter sign, the organiser closes."""
    now = S.now_iso()
    for fn in (lambda r: L.move(r, "closing", katie, now), lambda r: L.confirm(r, harvey, now), lambda r: L.confirm(r, katie, now),
               lambda r: L.close(r, katie, {"summary": "Done.", "next": [{"kind": "nothing", "reason": "Nothing more to do."}]}, now)):
        S.update_intent(plane, rid, rec_of(plane, rid)["version"], fn)


def test_questions_prefill_from_an_item_and_an_alert(env):
    plane, c = env
    wk = draft(plane, "mei")  # any intent id will do for the check-in item's folder
    plane.path("intents", wk, "weeks").mkdir(parents=True)
    plane.path("intents", wk, "weeks", "2026-w40.json").write_text(json.dumps({"items": [{"id": "i9", "text": "Statement file late again"}]}), encoding="utf-8")
    r = go(c, "aaron", "GET", f"/api/intents/problem/start?from={wk}&item=i9").json()
    assert r["prefill"]["what"] == "Statement file late again" and "Weekly check-in" in r["prefill"]["origin"]
    assert [x["id"] for x in r["catalogue"]] == ["measure:K02"] and {p["name"] for p in r["people"]} >= {"Aaron Lyle", "Harvey Rowley"}
    assert "Fund Operations" in r["areas"]
    chips = go(c, "aaron", "GET", "/api/intents/problem/start?about=measure:K02").json()["chips"]  # the order of spec 41: business, source, data
    assert [(x["source"], x["name"]) for x in chips] == [("business_owner", "Daniel Kerr"), ("source_owner", "Harvey Rowley"), ("data_owner", "Harvey Rowley")]
    assert go(c, "aaron", "GET", "/api/intents/problem/start?alert=nope").json()["prefill"]["alert_missing"] is True  # said, not guessed
    alert = go(c, "aaron", "GET", "/api/intents/problem/start?alert=custodian_daily_file:missing").json()["prefill"]
    assert alert["what"] == "Custodian daily file: the file has not arrived" and alert["owner_source"] == "source_owner"


def test_open_needs_the_answers_then_writes_the_ruled_record(env):
    plane, c = env
    rid = draft(plane)
    url = f"/api/intents/{rid}/problem/start"
    assert go(c, "katie", "POST", url, {**ANS, "bites": {}}).status_code == 422
    assert go(c, "katie", "POST", url, {**ANS, "affected": []}).status_code == 422
    assert go(c, "aaron", "POST", url, ANS).status_code == 404  # not their draft
    assert go(c, "katie", "POST", url, {**ANS, "open": False}).json()["saved"]  # a draft: only its creator reads it
    assert go(c, "katie", "GET", f"/api/intents/{rid}/problem").json()["state"] == "draft"
    assert go(c, "aaron", "GET", f"/api/intents/{rid}/problem").status_code == 404
    assert go(c, "katie", "POST", url, ANS).status_code == 200
    rec = rec_of(plane, rid)
    assert rec["state"] == "open" and rec["short_ref"] == "P-1" and rec["stages"][0]["key"] == "describe" and rec["people"]["owner"] is None
    assert rec["outcome"]["triage"] == "waiting" and rec["outcome"]["proposed_owner"]["name"] == "Harvey Rowley" and rec["people"]["reporter"]["account_id"] == "a-katie"
    assert rec["links"]["node"] == "measure:K02" and rec["triage_note"]["drafted_plainly"] is True and [p["name"] for p in rec["people"]["affected"]] == ["Aaron Lyle", "Mei Ling"]
    assert rec["time_box"]["ends"] and rec["title"] == "Monthly fee file arrives late" and rec["people"]["participants"][0]["name"] == "Harvey Rowley"  # the proposed owner can read it
    assert "opened" in plane.path("intents", rid, "events.jsonl").read_text(encoding="utf-8")
    assert go(c, "katie", "POST", url, ANS).status_code == 404  # opened already


def test_owner_accepts_and_only_the_proposed_owner_may(env):
    rid = opened(env)
    c = env[1]
    assert go(c, "aaron", "POST", f"/api/intents/{rid}/triage/accept").status_code == 403
    assert go(c, "janet", "POST", f"/api/intents/{rid}/triage/accept").status_code == 403
    v = go(c, "harvey", "POST", f"/api/intents/{rid}/triage/accept").json()
    assert v["triage"] == "accepted" and v["owner"] == "Harvey Rowley" and v["stage"] == "Find the cause"
    assert go(c, "harvey", "POST", f"/api/intents/{rid}/triage/accept").status_code == 403  # no longer proposed
    assert rec_of(env[0], rid)["outcome"]["accepted_by"] == "a-harvey"


def test_pass_needs_a_reason_and_two_passes_go_to_the_admin(env):
    rid = opened(env)
    c = env[1]
    p = f"/api/intents/{rid}/triage/pass"
    assert go(c, "harvey", "POST", p, {"to": "Grace Ward", "reason": "short"}).status_code == 422
    assert go(c, "harvey", "POST", p, {"to": "Katie Menon", "reason": "I am not on this one at all"}).status_code == 422  # the reporter
    assert go(c, "harvey", "POST", p, {"to": "Harvey Rowley", "reason": "I am not on this one at all"}).status_code == 422  # himself
    v = go(c, "harvey", "POST", p, {"to": "Grace Ward", "reason": "This is a Finance Ops file."}).json()
    assert v["waiting_for"] == "Grace Ward" and v["passes"][0]["reason"] == "This is a Finance Ops file."
    assert go(c, "harvey", "POST", f"/api/intents/{rid}/triage/accept").status_code == 403  # it is Grace's now
    v = go(c, "grace", "POST", p, {"to": "Daniel Kerr", "reason": "Daniel knows this feed better."}).json()
    assert v["triage"] == "escalated" and v["escalated"] and len(v["passes"]) == 2 and v["proposed_owner"] is None
    assert go(c, "grace", "POST", p, {"to": "Aaron Lyle", "reason": "A third pass is refused."}).status_code == 403
    assert go(c, "aaron", "POST", f"/api/intents/{rid}/triage/assign", {"to": "Daniel Kerr"}).status_code == 403
    v = go(c, "janet", "POST", f"/api/intents/{rid}/triage/assign", {"to": "Daniel Kerr"}).json()
    assert v["triage"] == "accepted" and v["owner"] == "Daniel Kerr"
    assert rec_of(env[0], rid)["outcome"]["assigned_by_admin"] is True


def test_the_triage_note_reaches_only_the_reporter_and_the_owner(env):
    rid = opened(env)
    c = env[1]
    kav, haf = go(c, "katie", "GET", f"/api/intents/{rid}/problem").json(), go(c, "harvey", "GET", f"/api/intents/{rid}/problem").json()
    assert "triage_note" in kav and "triage_note" in haf and kav["as_reported"]["what"] == "Monthly fee file arrives late"
    assert [a["id"] for a in haf["triage_note"]["alerts"]] == ["custodian_daily_file:missing"]  # Ops alerts for the measure's source
    adm = go(c, "janet", "GET", f"/api/intents/{rid}/problem").json()
    assert "triage_note" not in adm and adm["tier"] == "outcome"  # the admin reads the outcome, not the note
    aff = go(c, "aaron", "GET", f"/api/intents/{rid}/problem").json()
    assert aff["tier"] == "card" and "as_reported" not in aff and "triage_note" not in aff and aff["title"]  # existence only while the switch is off
    rid2 = opened(env, affected_may_read=True)
    aff2 = go(c, "aaron", "GET", f"/api/intents/{rid2}/problem").json()
    assert aff2["tier"] == "content" and "as_reported" in aff2 and "triage_note" not in aff2  # never the triage note
    assert go(c, "daniel", "GET", f"/api/intents/{rid}/problem").status_code == 404  # not tagged, not named, not an admin: not even a stub


def test_similar_past_problems_come_from_closed_ones_on_the_same_measure(env):
    plane, c = env
    old = L.new_record("problem", "acme", L.person("a-katie", "Katie Menon"), S.now_iso(), title="Fee file late in August", areas=["Fund Operations"])
    old["state"] = "closed"
    old["people"]["owner"] = L.person("a-harvey", "Harvey Rowley")
    old["outcome"] = {"kind": "problem", "about": {"id": "measure:K02"}, "what": "Fee file late", "root_cause": {"text": "The custodian changed its run time."},
                      "fix": {"text": "Moved our pull to 7am"}}
    S.create_intent(plane, old)
    rid = opened(env)
    sim = go(c, "katie", "GET", f"/api/intents/{rid}/problem").json()["triage_note"]["similar"]
    assert [s["id"] for s in sim] == [old["id"]] and sim[0]["why"] == "Same process or measure"
    assert sim[0]["root_cause"] == "The custodian changed its run time." and sim[0]["fix"] == "Moved our pull to 7am" and sim[0]["owner"] == "Harvey Rowley"
    harvey = go(c, "harvey", "GET", f"/api/intents/{rid}/problem").json()["triage_note"]["similar"]
    assert harvey[0]["can_open"] is True or "root_cause" not in harvey[0]  # a row the viewer may not open shows title, state and owner only


def test_resolution_then_closing_writes_back_once(env):
    plane, c = env
    rid = accepted(env)
    u = lambda tail: f"/api/intents/{rid}/{tail}"  # noqa: E731
    assert go(c, "harvey", "POST", u("problem/cause"), {"action": "draft"}).status_code == 422  # nothing to draft from yet
    assert go(c, "katie", "POST", u("problem/note"), {"text": "It started on the first of the month."}).status_code == 200
    assert go(c, "aaron", "POST", u("problem/note"), {"text": "Nobody told us."}).status_code == 403  # affected, switch off
    v = go(c, "harvey", "POST", u("problem/cause"), {"action": "draft"}).json()
    assert v["root_cause"]["drafted_by_north"] and not v["root_cause"]["confirmed_by"]
    assert go(c, "katie", "POST", u("problem/cause"), {"action": "confirm", "text": "x"}).status_code == 403
    v = go(c, "harvey", "POST", u("problem/cause"), {"action": "confirm", "text": "The custodian moved its run to after midnight."}).json()
    assert v["stage"] == "Fix" and v["root_cause"]["confirmed_by"] == "Harvey Rowley"
    bad = {"kind": "workaround", "what": "We pull the file by hand", "by": "Harvey Rowley", "done_at": "2026-10-07", "real_fix_by": "2026-01-01"}
    assert go(c, "harvey", "POST", u("problem/fix"), bad).status_code == 422  # a workaround needs a real-fix date after today
    v = go(c, "harvey", "POST", u("problem/fix"), {**bad, "real_fix_by": "2099-01-01"}).json()
    assert v["fix"]["kind"] == "workaround" and v["fix"]["real_fix_by"] == "2099-01-01" and v["stage"] == "Confirm"
    assert go(c, "katie", "POST", u("problem/confirm-tap"), {"state": "fixed"}).status_code == 403  # the reporter cannot tap for them
    assert go(c, "aaron", "POST", u("problem/confirm-tap"), {"state": "still"}).status_code == 422  # still needs a sentence
    aaron = go(c, "aaron", "GET", u("problem")).json()
    assert aaron["tier"] == "card" and "Harvey Rowley did: We pull the file by hand" in aaron["fix_line"] and [r["name"] for r in aaron["affected"]] == ["Aaron Lyle"]
    assert go(c, "aaron", "POST", u("problem/confirm-tap"), {"state": "fixed"}).status_code == 200
    go(c, "mei", "POST", u("problem/confirm-tap"), {"state": "still", "comment": "It was late again on the 9th."})
    owner = go(c, "harvey", "GET", u("problem")).json()
    assert owner["tally"] == {"fixed": 1, "still": 1, "affected": 2, "no_answer": 0} and any("still happening" in n["text"] for n in owner["notes"])
    assert owner["can_resolve"]["close"] is True and all(x["ok"] for x in owner["close_checks"])
    # the closure screen's flow (file 09) runs on the same record; the first read of the closed problem writes back
    closing_to_closed(plane, rid)
    assert go(c, "katie", "GET", u("problem")).json()["state"] == "closed"
    versions = json.loads(plane.path("graph", "versions.json").read_text(encoding="utf-8"))["measure:K02"]
    assert len(versions) == 1 and versions[0]["by"] == "Harvey Rowley" and versions[0]["ref"] == f"problem:{rid}" and "P-1 worked around" in versions[0]["what"]
    go(c, "harvey", "GET", u("problem"))
    problem.write_back(plane, rec_of(plane, rid))
    assert len(json.loads(plane.path("graph", "versions.json").read_text(encoding="utf-8"))["measure:K02"]) == 1  # idempotent


def test_reporter_reopens_once_then_starts_a_new_problem(env):
    plane, c = env
    rid = accepted(env)
    u = lambda tail: f"/api/intents/{rid}/{tail}"  # noqa: E731
    go(c, "katie", "POST", u("problem/note"), {"text": "Seen on the 1st."})
    go(c, "harvey", "POST", u("problem/cause"), {"action": "confirm", "text": "A changed run time."})
    go(c, "harvey", "POST", u("problem/fix"), {"kind": "fixed", "what": "Moved the pull", "by": "Harvey Rowley", "done_at": "2026-10-07"})
    now = S.now_iso()
    S.update_intent(plane, rid, rec_of(plane, rid)["version"], lambda r: L.move(r, "closing", "a-katie", now))
    assert go(c, "katie", "POST", u("problem/reopen"), {"reason": "", "stage": "fix"}).status_code == 422
    assert go(c, "harvey", "POST", u("problem/reopen"), {"reason": "No.", "stage": "fix"}).status_code == 403
    v = go(c, "katie", "POST", u("problem/reopen"), {"reason": "It was late again today.", "stage": "fix"}).json()
    assert v["state"] == "open" and v["stage"] == "Fix"
    go(c, "harvey", "POST", u("problem/fix"), {"kind": "fixed", "what": "Moved the pull again", "by": "Harvey Rowley", "done_at": "2026-10-07"})
    S.update_intent(plane, rid, rec_of(plane, rid)["version"], lambda r: L.move(r, "closing", "a-katie", now))
    r = go(c, "katie", "POST", u("problem/reopen"), {"reason": "Still late.", "stage": "fix"})
    assert r.status_code == 409 and "Start a new Problem" in r.json()["message"]


def test_anonymous_notes_never_reach_the_admin_and_extend_is_once(env):
    rid = accepted(env)
    c, u = env[1], (lambda tail: f"/api/intents/{rid}/{tail}")
    go(c, "katie", "POST", u("problem/note"), {"text": "A named note."})
    go(c, "katie", "POST", u("problem/note"), {"text": "Please do not name me.", "anonymous": True})
    assert "notes" not in go(c, "janet", "GET", u("problem")).json()  # outcome only
    notes = go(c, "harvey", "GET", u("problem")).json()["notes"]
    assert [n["by"] for n in notes] == ["Katie Menon", None] and notes[1]["anonymous"]
    assert go(c, "katie", "POST", u("problem/extend"), {"days": 2, "reason": "Waiting for the custodian."}).status_code == 403
    assert go(c, "harvey", "POST", u("problem/extend"), {"days": 2, "reason": "short"}).status_code == 422
    assert go(c, "harvey", "POST", u("problem/extend"), {"days": 2, "reason": "Waiting for the custodian."}).json()["extended"]["reason"]
    assert go(c, "harvey", "POST", u("problem/extend"), {"days": 1, "reason": "Another wait please."}).status_code == 409


def test_the_alert_is_acknowledged_with_the_link_when_the_problem_closes(env):
    plane, c = env
    plane.path("build", "alerts.json").write_text(json.dumps({"alerts": [{"id": "custodian_daily_file:missing", "kind": "missing", "source": "custodian_daily_file",
                                                                         "measure": None, "owner": "Harvey Rowley", "opened": "2026-10-06", "state": "open", "by": None, "at": None, "note": None}]}), encoding="utf-8")
    rid = opened(env, alert="custodian_daily_file:missing")
    u = lambda tail: f"/api/intents/{rid}/{tail}"  # noqa: E731
    assert go(c, "katie", "GET", u("problem")).json()["alert_line"]["id"] == "custodian_daily_file:missing"
    go(c, "harvey", "POST", u("triage/accept"))
    go(c, "harvey", "POST", u("problem/cause"), {"action": "unknown", "reason": "The custodian has not said why."})
    go(c, "harvey", "POST", u("problem/fix"), {"kind": "accepted_no_fix", "reason": "We will watch it for a month.", "accepted_by": "Harvey Rowley"})
    closing_to_closed(plane, rid)
    go(c, "katie", "GET", u("problem"))
    alert = json.loads(plane.path("build", "alerts.json").read_text(encoding="utf-8"))["alerts"][0]
    assert alert["state"] == "acknowledged" and alert["by"] == "Harvey Rowley" and alert["note"] == "Problem P-1: /centre/intent/" + rid
    assert "closed without a fix" in json.loads(plane.path("graph", "versions.json").read_text(encoding="utf-8"))["measure:K02"][0]["what"]


def test_the_reporter_who_owns_it_skips_acceptance(env):
    rid = opened(env, who="harvey", owner={"source": "reporter", "name": "Harvey Rowley"})
    v = go(env[1], "harvey", "GET", f"/api/intents/{rid}/problem").json()
    assert v["triage"] == "accepted" and v["owner"] == "Harvey Rowley" and v["stage"] == "Find the cause"


def test_north_drafts_through_the_runtime_and_anonymous_notes_never_reach_it(env, monkeypatch):
    plane, c = env
    c.app.state.entitlements, c.app.state.north_model_factory = object(), lambda p: object()
    sent = []

    def fake_call(plane_, model, gate, system, context, question):
        sent.append(json.dumps(context))
        assert rows.json_findings(json.dumps({"context": context, "question": question}))[0] is None  # the gateway would send it
        if "root cause" in question:
            return '{"text": "The custodian run moved after midnight, 99 times.", "based_on": ["n1", "zz"], "questions": ["Since when?"]}'
        return '{"text": "The monthly fee file arrives late."}'
    monkeypatch.setattr(problem.N, "_call", fake_call)
    rid = opened(env)
    assert go(c, "harvey", "GET", f"/api/intents/{rid}/problem").json()["triage_note"]["summary"] == "The monthly fee file arrives late."
    assert rec_of(plane, rid)["triage_note"]["drafted_plainly"] is False
    go(c, "harvey", "POST", f"/api/intents/{rid}/triage/accept")
    go(c, "katie", "POST", f"/api/intents/{rid}/problem/note", {"text": "The run moved after midnight."})
    go(c, "katie", "POST", f"/api/intents/{rid}/problem/note", {"text": "SECRET-ANON line.", "anonymous": True})
    rc = go(c, "harvey", "POST", f"/api/intents/{rid}/problem/cause", {"action": "draft"}).json()["root_cause"]
    assert rc["fallback"] is False and "99" not in rc["text"] and rc["based_on"] == ["n1"] and rc["questions"] == ["Since when?"]
    assert not any("SECRET-ANON" in s for s in sent)
    monkeypatch.setattr(problem.N, "_call", lambda *a: None)  # the model cannot answer: the plain reading, labelled
    rc = go(c, "harvey", "POST", f"/api/intents/{rid}/problem/cause", {"action": "draft"}).json()["root_cause"]
    assert rc["fallback"] is True


def test_bigger_than_a_fix_closes_the_problem_and_writes_the_linked_initiative_draft(env):
    plane, c = env
    rid = accepted(env)
    assert go(c, "aaron", "POST", f"/api/intents/{rid}/problem/to-initiative", {"reason": "Three feeds are involved."}).status_code in (403, 404)
    assert go(c, "harvey", "POST", f"/api/intents/{rid}/problem/to-initiative", {"reason": "short"}).status_code == 422
    r = go(c, "harvey", "POST", f"/api/intents/{rid}/problem/to-initiative", {"reason": "Three feeds and two teams are involved."})
    assert r.status_code == 200, r.text
    rec = rec_of(plane, rid)
    assert rec["state"] == "closed" and rec["closure"]["kind"] == "bigger_than_fix"
    ref = rec["closure"]["next"][0]["ref"]
    assert rec["closure"]["next"][0]["kind"] == "initiative" and ref and ref in rec["links"]["to"]
    child = rec_of(plane, ref)
    assert child["type"] == "initiative" and child["state"] == "draft" and child["links"]["from"] == rid and child["created_by"] == "a-harvey"
    assert r.json()["url"] == f"/centre/intent/new?type=initiative&draft={ref}&from={rid}"
    assert not (rec["outcome"].get("writeback") or {}).get("node")  # nothing was fixed: no version note
    assert go(c, "harvey", "POST", f"/api/intents/{rid}/problem/to-initiative", {"reason": "Three feeds and two teams are involved."}).status_code == 409
    seen = go(c, "katie", "GET", f"/api/intents/{rid}/problem").json()  # the reporter is told in the thread and sees what it became
    assert "bigger than a fix" in seen["notes"][-1]["text"] and seen["became"]["id"] == ref and seen["became"]["may_open"] is False


def test_the_owners_cause_words_stand_over_norths_draft(env, monkeypatch):
    """F10, rule 7: the owner's own cause text is what is kept; North's draft is marked as North's only while untouched."""
    plane, c = env
    c.app.state.entitlements, c.app.state.north_model_factory = object(), lambda p: object()
    monkeypatch.setattr(problem.N, "_call", lambda *a: '{"text": "The run moved after midnight.", "based_on": ["n1"], "questions": []}')
    rid = opened(env)
    go(c, "harvey", "POST", f"/api/intents/{rid}/triage/accept")
    go(c, "katie", "POST", f"/api/intents/{rid}/problem/note", {"text": "The run moved after midnight."})
    assert go(c, "harvey", "POST", f"/api/intents/{rid}/problem/cause", {"action": "draft"}).json()["root_cause"]["drafted_by_north"] is True
    go(c, "harvey", "POST", f"/api/intents/{rid}/problem/cause", {"action": "confirm", "text": "The scheduler was moved by the vendor upgrade."})
    rc = rec_of(plane, rid)["outcome"]["root_cause"]
    assert rc["text"] == "The scheduler was moved by the vendor upgrade." and rc["drafted_by_north"] is False and rc["confirmed_by"] == "a-harvey"


def test_the_reporter_slot_survives_the_people_list_rebuild(env):
    plane, c = env
    rid = opened(env)
    S.update_intent(plane, rid, rec_of(plane, rid)["version"], lambda r: r["people"].update(reporter=None))  # what file 06's rebuild leaves
    assert go(c, "katie", "GET", f"/api/intents/{rid}/problem").json()["reporter"] == "Katie Menon"
    assert go(c, "harvey", "POST", f"/api/intents/{rid}/triage/accept").status_code == 200
    rec = rec_of(plane, rid)
    assert rec["people"]["reporter"]["name"] == "Katie Menon" and rec["people"]["owner"]["name"] == "Harvey Rowley"


# ---- F37: intent faults ------------------------------------------------------------------------------------------------------------------------------

def test_an_opened_problem_has_its_start_questions_answered_so_north_asks_none(env):
    from sh_platform.intents import north
    plane, _c = env
    rec = rec_of(plane, opened(env))
    st = {"asked": []}
    assert north.missing_start(rec, st) is None


def test_an_enhancement_is_steered_to_an_initiative_but_a_real_fault_is_not():
    from sh_platform.intents.types import classify_text
    got = classify_text("We want a new column added to the cash match report. No fees column, want one added as an improvement")
    assert got["type"] == "initiative"
    assert classify_text("The cash match report is missing a fee and keeps failing")["type"] == "problem"
    assert classify_text("The fee file is wrong and we want it fixed")["type"] == "problem"


def test_a_closed_problem_carries_its_closed_date_and_an_open_one_does_not(env):
    plane, c = env
    rid = opened(env)
    assert go(c, "katie", "GET", f"/api/intents/{rid}/problem").json()["closed_at"] is None

    def shut(r):
        r["state"] = "closed"
        r["closure"] = {**(r.get("closure") or {}), "closed_at": "2026-10-09T08:00:00+00:00"}
    S.update_intent(plane, rid, rec_of(plane, rid)["version"], shut)
    assert go(c, "katie", "GET", f"/api/intents/{rid}/problem").json()["closed_at"].startswith("2026-10-09")


def test_a_summary_the_figure_guard_ate_a_word_from_falls_back_to_the_plain_restatement(env, monkeypatch):
    plane, c = env
    c.app.state.entitlements, c.app.state.north_model_factory = object(), lambda p: object()
    monkeypatch.setattr(problem.N, "_call", lambda *a: '{"text": "The Tnot available yetb extract is late."}')
    rid = opened(env, what="T24b extract is late")
    note = rec_of(plane, rid)["triage_note"]
    assert note["drafted_plainly"] is True and "not available yet" not in json.dumps(note["summary"] or "")


def test_a_related_intent_the_viewer_cannot_open_shows_no_details(env):  # F43, SEC0 #3
    plane, c = env
    old = L.new_record("problem", "acme", L.person("a-katie", "Katie Menon"), S.now_iso(), title="Secret legal fee matter", areas=["Legal"])
    old["state"] = "closed"
    old["outcome"] = {"kind": "problem", "about": {"id": "measure:K02"}, "what": "Fee file late", "root_cause": {"text": "x"}, "fix": {"text": "y"}}
    S.create_intent(plane, old)
    rid = opened(env)
    mine = go(c, "katie", "GET", f"/api/intents/{rid}/problem").json()["triage_note"]["similar"]
    assert [s["id"] for s in mine] == [old["id"]]  # the organiser of both sees the row
    v = go(c, "harvey", "GET", f"/api/intents/{rid}/problem")
    sim = v.json()["triage_note"]["similar"]
    assert sim and sim[0]["title"] == problem.HIDDEN_ROW and sim[0]["can_open"] is False
    assert old["id"] not in v.text and "Secret legal" not in v.text and sim[0]["organiser"] is None and sim[0]["state"] is None


def test_an_older_record_with_plain_text_cause_and_fix_still_loads(env):  # F49: the seed may keep them as strings
    plane, c = env
    rid = accepted(env)

    def old(r):
        r["outcome"]["root_cause"] = "The custodian file arrives after the cut-off"
        r["outcome"]["fix"] = "Ask for the file at noon"
    S.update_intent(plane, rid, rec_of(plane, rid)["version"], old)
    for who in ("katie", "harvey"):
        r = go(c, who, "GET", f"/api/intents/{rid}/problem")
        assert r.status_code == 200, r.text
    v = go(c, "harvey", "GET", f"/api/intents/{rid}/problem").json()
    assert v["root_cause"]["text"] == "The custodian file arrives after the cut-off" and v["fix"]["what"] == "Ask for the file at noon"


def test_an_older_accepted_record_still_shows_the_work_to_the_reporter(env):
    plane, c = env
    rid = accepted(env)
    def old(rec):  # a record that kept only the acceptance date
        rec["outcome"].pop("triage"); rec["outcome"]["owner_accepted_at"] = "2026-10-02T03:00:00+00:00"
    S.update_intent(plane, rid, S.read_intent(plane, rid)["version"], old)
    v = go(c, "katie", "GET", f"/api/intents/{rid}/problem").json()  # katie is the reporter
    assert v["triage"] == "accepted" and v["reads"] and "what_we_know" in v and "notes" in v
