"""B25 (spec 43): the Decision intent. Synthetic Ardmore people; a small app with the record and decision routers only."""
import json
from types import SimpleNamespace

import pytest
from sh_platform.egress import rows
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.intents import decision, records
from sh_platform.plane import PlaneStore

CO = "ardmore"
ACCTS = {"janet": ("Janet Shaw", ["company_admin"]), "daniel": ("Daniel Kerr", ["sponsor"]), "aaron": ("Aaron Lyle", ["participant"]),
         "katie": ("Katie Rao", ["analyst"]), "harvey": ("Harvey Rowley", ["owner"]), "grace": ("Grace Ward", ["approver"])}


class Accounts:
    def get(self, aid):
        return {"display_name": ACCTS[aid][0]} if aid in ACCTS else None

    def in_company(self, company_id):
        return [{"account_id": a, "display_name": n, "roles": r, "disabled": False} for a, (n, r) in ACCTS.items()]


def P(aid):
    return {"account_id": aid, "name": ACCTS[aid][0]}


@pytest.fixture
def env(tmp_path):
    plane = PlaneStore(tmp_path).create(CO).ensure()
    plane.path("graph").mkdir(parents=True, exist_ok=True)
    plane.path("graph", "company.json").write_text(json.dumps({"version": 1, "built_at": None, "edges": [], "nodes": [
        {"id": "measure:nav-lag", "type": "Measure", "label": "NAV lag"},
        {"id": "process:close", "type": "Process", "label": "Month-end close", "restricted_to": ["Grace Ward"]}]}), encoding="utf-8")
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = Accounts()
    app.include_router(records.router)
    app.include_router(decision.router)

    @app.middleware("http")
    async def sign_in(request, call_next):
        who = request.headers.get("x-who", "janet")
        request.state.account_id, request.state.company_id, request.state.roles = who, CO, ACCTS[who][1]
        return await call_next(request)
    return SimpleNamespace(plane=plane, c=TestClient(app))


def call(env, who, path, body=None, method="POST"):
    return env.c.request(method, path, json=body or {}, headers={"x-who": who})


ANSWERS = {"question": "Which valuation date do we use for the fund report: month-end or quarter-end?", "decider": P("daniel"),
           "advisers": [P("katie"), P("aaron"), P("harvey")], "areas": ["Finance operations", "Investment"]}


def opened(env, answers=None, **create):
    r = call(env, "janet", "/api/intents", {"type": "decision", **create})
    assert r.status_code == 201, r.text
    iid = r.json()["id"]
    r = call(env, "janet", f"/api/intents/{iid}/decide", {"kind": "open", "answers": {**ANSWERS, **(answers or {})}})
    assert r.status_code == 200, r.text
    return iid, r.json()


def test_five_questions_fill_the_record(env):
    iid, rec = opened(env)
    assert rec["state"] == "open" and rec["title"] == ANSWERS["question"] == rec["outcome"]["question"]
    assert rec["time_box"]["ends"] and [s["key"] for s in rec["stages"]] == ["options", "decide"]
    assert rec["people"]["decider"]["account_id"] == "daniel" and rec["people"]["sponsor"]["account_id"] == "daniel"
    assert [a["account_id"] for a in rec["people"]["advisers"]] == ["katie", "aaron", "harvey"]
    assert rec["areas"] == ANSWERS["areas"] and rec["affected_may_read"] is False and isinstance(rec["outcome"], dict)


@pytest.mark.parametrize("bad,msg", [({"question": ""}, "what must be decided"), ({"decider": None}, "Name who decides"),
                                     ({"areas": []}, "Choose at least one area")])
def test_required_questions(env, bad, msg):
    iid = call(env, "janet", "/api/intents", {"type": "decision"}).json()["id"]
    r = call(env, "janet", f"/api/intents/{iid}/decide", {"kind": "open", "answers": {**ANSWERS, **bad}})
    assert r.status_code == 400 and msg in r.json()["detail"]


def test_decider_and_advisers_slots(env):
    iid = call(env, "janet", "/api/intents", {"type": "decision"}).json()["id"]
    six = [P(a) for a in ACCTS][:6]
    r = call(env, "janet", f"/api/intents/{iid}/decide", {"kind": "open", "answers": {**ANSWERS, "advisers": six}})
    assert r.status_code == 400 and "more advisers" in r.json()["detail"]
    assert call(env, "katie", f"/api/intents/{iid}/decide", {"kind": "open", "answers": ANSWERS}).status_code in (403, 404)


def test_options_drafted_and_marked_guessed(env):
    _, rec = opened(env)
    opts = rec["outcome"]["options"]
    assert [o["name"] for o in opts] == ["month-end", "quarter-end"]
    assert all(o["origin"] == "north" and o["by"] == "North" and o["needs"].startswith("Not known") for o in opts)
    assert rec["outcome"]["north"]["drafted"] == 2


def test_anonymous_adviser_option_and_note_keep_no_author(env):
    iid, rec = opened(env)
    r = call(env, "katie", f"/api/intents/{iid}/options", {"name": "Use month-end custodian price", "anonymous": True})
    assert r.status_code == 200
    first = rec["outcome"]["options"][0]["id"]
    assert call(env, "katie", f"/api/intents/{iid}/options/{first}/notes", {"text": "Custodian prices lag", "anonymous": True}).status_code == 200
    for who in ("janet", "daniel"):
        out = call(env, who, f"/api/intents/{iid}", method="GET").json()["outcome"]
        anon = [o for o in out["options"] if o["origin"] == "anonymous"][0]
        note = out["options"][0]["notes"][0]
        assert anon["by"] == note["by"] == "Anonymous" and "by_account" not in anon and "by_account" not in note
        assert "katie" not in json.dumps(out).lower()
    assert call(env, "grace", f"/api/intents/{iid}/options", {"name": "Not mine"}).status_code in (403, 404)  # not named: no write


def test_recommendation_rests_on_sources_and_untraced_numbers_drop(env):
    _, bare = opened(env)
    assert bare["outcome"]["recommendation"] is None  # no record behind any card
    src = call(env, "janet", "/api/intents", {"type": "problem", "title": "NAV report late", "areas": ["Finance operations"]}).json()["id"]
    iid, rec = opened(env, links={"from": src})
    r = rec["outcome"]["recommendation"]
    assert r["drafted_by"] == "North" and r["sources"] and r["sources"][0]["ref"] == src and r["option_id"]
    assert any("Missing: a quote or an estimate" in m for m in r["missing"])
    line, dropped = decision.drop_untraced("Option B saves 40 hours, per the 3 Oct note", "Measure: NAV lag, 3 Oct")
    assert dropped == ["40"] and "40" not in line and "3 Oct" in line


def test_decide_with_reason_records_and_waits_for_the_organiser(env):
    iid, rec = opened(env)
    opt = rec["outcome"]["options"][1]["id"]
    assert call(env, "janet", f"/api/intents/{iid}/decide", {"kind": "choose", "option_id": opt, "why": "x"}).status_code == 403
    assert call(env, "daniel", f"/api/intents/{iid}/decide", {"kind": "choose", "option_id": opt, "why": " "}).status_code == 400
    r = call(env, "daniel", f"/api/intents/{iid}/decide", {"kind": "choose", "option_id": opt, "why": "Matches the audit cycle"})
    out = r.json()
    assert r.status_code == 200 and out["state"] == "closing" and out["outcome"]["chosen"] == opt
    assert out["outcome"]["decided_by"] == "Daniel Kerr" and out["outcome"]["why"] == "Matches the audit cycle"
    assert out["outcome"]["why_drafted"] is False and len(out["outcome"]["considered_snapshot"]) == 2
    assert out["closure"]["confirmed"][0]["role"] == "decider" and out["closure"]["draft_by"] == "north"
    assert call(env, "katie", f"/api/intents/{iid}/options", {"name": "Late"}).status_code == 409  # recorded is read-only
    assert call(env, "daniel", f"/api/intents/{iid}/decide", {"kind": "none", "reason": "again"}).status_code == 409


def test_decide_later_only_once(env):
    iid, rec = opened(env)
    ends = rec["time_box"]["ends"]
    from datetime import datetime, timedelta
    to = datetime.fromisoformat(ends) + timedelta(days=1)
    while to.weekday() >= 5:
        to += timedelta(days=1)
    r = call(env, "daniel", f"/api/intents/{iid}/decide", {"kind": "later", "to": to.isoformat(), "reason": "Waiting for the custodian"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["outcome"]["deferral"]["from"] == ends and out["time_box"]["extended_by"][-1]["kind"] == "decide_later"
    again = call(env, "daniel", f"/api/intents/{iid}/decide", {"kind": "later", "to": to.isoformat(), "reason": "More"})
    assert again.status_code == 409 and "Already extended once" in again.json()["detail"]


def test_no_decision_needs_a_reason(env):
    iid, _ = opened(env)
    assert call(env, "daniel", f"/api/intents/{iid}/decide", {"kind": "none", "reason": ""}).status_code == 400
    out = call(env, "daniel", f"/api/intents/{iid}/decide", {"kind": "none", "reason": "The fund report moved to next year"}).json()
    assert out["outcome"]["chosen"] is None and out["outcome"]["no_decision_reason"].startswith("The fund") and out["state"] == "closing"


def test_version_notes_on_named_measures_only_where_seen(env):
    iid, rec = opened(env)
    r = call(env, "janet", f"/api/intents/{iid}/decide", {"kind": "affects", "nodes": ["measure:nav-lag", "process:close"]})
    assert [a["node_id"] for a in r.json()["outcome"]["affects"]] == ["measure:nav-lag"]  # Janet cannot see the restricted process
    opt = rec["outcome"]["options"][0]["id"]
    out = call(env, "daniel", f"/api/intents/{iid}/decide", {"kind": "choose", "option_id": opt, "why": "Simplest"}).json()
    assert out["outcome"]["writes"] == [{"node_id": "measure:nav-lag", "version": 1, "ref": f"intent:{iid}"}]
    versions = json.loads(env.plane.path("graph", "versions.json").read_text(encoding="utf-8"))
    assert versions["measure:nav-lag"][0]["what"].startswith("Decision: month-end.") and versions["measure:nav-lag"][0]["by"] == "Daniel Kerr"


def test_link_back_on_the_source_intent(env):
    src = call(env, "janet", "/api/intents", {"type": "problem", "title": "NAV report late", "areas": ["Finance operations"]}).json()["id"]
    iid, rec = opened(env, links={"from": src})
    call(env, "daniel", f"/api/intents/{iid}/decide", {"kind": "choose", "option_id": rec["outcome"]["options"][0]["id"], "why": "Simplest"})
    assert iid in call(env, "janet", f"/api/intents/{src}", method="GET").json()["links"]["to"]


def test_north_never_decides_and_suggestions_need_the_owner(env):
    iid, rec = opened(env)
    out = rec["outcome"]
    assert out["chosen"] is None and out["why"] == "" and out["decided_by"] is None and rec["state"] == "open"
    events = [json.loads(x) for x in env.plane.path("intents", iid, "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(e["status"] == "draft" for e in events if e.get("agent") == "north") and not any(e["kind"] == "signed" for e in events)
    opt = out["options"][0]
    n = call(env, "aaron", f"/api/intents/{iid}/options/{opt['id']}/notes", {"kind": "suggestion", "text": "Say the cost is two weeks"}).json()
    note = n["outcome"]["options"][0]["notes"][0]["id"]
    refused = call(env, "katie", f"/api/intents/{iid}/notes/{note}/decide", {"state": "accepted"})
    assert refused.status_code == 403 and refused.json()["detail"] == decision.OWNER_ONLY
    ok = call(env, "janet", f"/api/intents/{iid}/notes/{note}/decide", {"state": "accepted"}).json()["outcome"]["options"][0]
    assert ok["notes"][0]["state"] == "accepted" and ok["accepted"][0]["text"] == "Say the cost is two weeks"


def test_open_drafts_a_purpose_so_the_decision_can_close(env):
    _, rec = opened(env)
    assert rec["purpose"] == "Daniel Kerr decides, with the advisers' notes."


def test_options_and_lean_through_the_runtime_fall_back_labelled_and_keep_human_edits(env, monkeypatch):
    """F10, R14: option cards and the lean come from the runtime; a failed call gives word-rule cards marked `fallback`;
    a redraft replaces only North's untouched cards (rule 7)."""
    env.c.app.state.entitlements, env.c.app.state.north_model_factory = object(), lambda p: object()
    sent = []
    src = call(env, "janet", "/api/intents", {"type": "problem", "title": "NAV report late", "areas": ["Finance operations"]}).json()["id"]

    def fake_call(plane_, model, gate, system, context, question):
        sent.append(json.dumps(context))
        assert rows.json_findings(json.dumps({"context": context, "question": question}))[0] is None  # the gateway would send it
        if "option_id" in question:
            return json.dumps({"option_id": next(iter(context["options"])), "because": "the report rests on it", "refs": [src]})
        return json.dumps({"options": [{"name": "Month-end", "means": "Use month-end prices.", "for": ["Matches the custodian"], "refs": [src]},
                                       {"name": "Quarter-end", "means": "Use quarter-end prices.", "against": ["Saves 40 hours"]}]})
    monkeypatch.setattr(decision.N, "_call", fake_call)
    iid, rec = opened(env, links={"from": src})
    opts = rec["outcome"]["options"]
    assert [o["name"] for o in opts] == ["Month-end", "Quarter-end"] and not any(o["fallback"] for o in opts)
    assert opts[1]["against"] == ["Saves hours"]  # a number not in the records is dropped
    r = rec["outcome"]["recommendation"]
    assert r["fallback"] is False and r["option_id"] == opts[0]["id"] and r["line"].startswith("North leans to Month-end")
    assert sent and not any(x in s for s in sent for x in ("katie", "daniel", "by_account"))  # names are tokenised by the gateway; account ids never go
    assert call(env, "janet", f"/api/intents/{iid}/options", {"action": "edit", "option_id": opts[0]["id"], "name": "Month-end, our words"}).status_code == 200
    monkeypatch.setattr(decision.N, "_call", lambda *a: None)  # the model cannot answer
    out = call(env, "janet", f"/api/intents/{iid}/options", {"action": "redraft"}).json()["outcome"]
    names = [o["name"] for o in out["options"]]
    assert "Month-end, our words" in names and "Quarter-end" not in names  # the human edit stays, North's untouched card is replaced
    assert all(o["fallback"] for o in out["options"] if o["origin"] == "north" and not o.get("edited_by"))
    assert out["recommendation"]["fallback"] is True


def test_the_records_numbers_ride_in_the_question_so_the_guard_keeps_them():
    """F10: the runtime's number guard replaces any figure not in the facts or the question; drafts name the records' own numbers there."""
    from sh_platform.agents.guard import check_numbers
    q = decision.with_numbers("Draft.", '{"saw": "The file came at 11:40, not 10:00."}')
    assert "11, 40, 10, 00" in q
    assert check_numbers("It came at 11:40.", [], q).text == "It came at 11:40." and "not available" in check_numbers("It came at 11:40.", [], "Draft.").text


def test_an_older_seeded_option_takes_a_note_and_reads_with_a_name(env):
    """W2F7: options seeded as {id, text, drafted_by, added_by} take an adviser's note (no 500) and come back in the spec 43 shape."""
    from sh_platform.intents import store as S
    iid, rec = opened(env)
    S.update_intent(env.plane, iid, rec["version"], lambda r: r["outcome"].update(options=[
        {"id": "o1", "text": "Adopt the governed measures from the baseline for every section", "drafted_by": "north", "added_by": None},
        {"id": "o2", "text": "Use a standing credit line", "drafted_by": None, "added_by": "adviser"}]))
    r = call(env, "katie", f"/api/intents/{iid}/options/o1/notes", {"text": "Start with the NAV measures", "kind": "comment"})
    assert r.status_code == 200, r.text
    o1, o2 = r.json()["outcome"]["options"]
    assert o1["name"].startswith("Adopt the governed") and o1["origin"] == "north" and o1["by"] == "North"
    assert o1["notes"][0]["by"] == "Katie Rao" and o2["origin"] == "adviser" and o2["by"] == "an adviser"
