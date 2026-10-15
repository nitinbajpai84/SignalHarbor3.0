"""B09: closure, sign-off and ratings. Records on a plane in a temporary folder, the real routes behind a small test app; the person
is chosen by a header. Covers the per-type confirmer then the organiser, close with what we have, cancel with a reason, anonymous
ratings, the aggregate from three, no per-person figure, the Weekly check-in series never rated, and the approver link."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.intents import closure, lifecycle as L, ratings, records, store as S
from sh_platform.plane import PlaneStore

PEOPLE = {"a-org": "Janet", "a-spon": "Daniel", "a-own": "Harvey", "a-rep": "Katie", "a-p1": "Aaron", "a-p2": "Mei Ling", "a-p3": "Ravi",
          "a-out": "Rahul"}


@pytest.fixture
def world(tmp_path, monkeypatch):
    plane = PlaneStore(tmp_path).create("acme")
    PLANE[:] = [plane]
    monkeypatch.setattr(records, "_plane", lambda r: plane)
    monkeypatch.setattr(records, "_viewer", lambda r: SimpleNamespace(
        name=PEOPLE[r.headers["x-as"]], roles=frozenset(), account_id=r.headers["x-as"], shared_name=False))
    app = FastAPI()
    app.state.account_store = SimpleNamespace(get=lambda a: {"display_name": PEOPLE[a]} if a in PEOPLE else None)
    app.include_router(closure.router)
    return plane, TestClient(app)


def person(a):
    return L.person(a, PEOPLE[a])


def make(plane, type_="problem", state="closing", **people):
    rec = L.new_record(type_, "acme", person("a-org"), S.now_iso(), title="Late sweeps", purpose="Cash sweeps run late every Friday")
    rec["people"].update({k: person(v) if isinstance(v, str) else [person(x) for x in v] for k, v in people.items()})
    rec["state"] = state
    if state == "closing":
        rec["closure"]["draft_by"] = "a-org"
    S.create_intent(plane, rec)
    return rec["id"]


def put(c, who, iid, **body):
    if "version" not in body:  # every closure write names the version it read (spec 01)
        body["version"] = S.read_intent(PLANE[0], iid)["version"]
    return c.put(f"/api/intents/{iid}/closure", json=body, headers={"x-as": who})


PLANE = []


def problem(plane, **kw):
    iid = make(plane, owner="a-own", reporter="a-rep", participants=["a-p1", "a-p2", "a-p3"], **kw)
    S.update_intent(plane, iid, 1, lambda r: r["outcome"].update(root_cause="A late file", fix="Move the cut-off"))
    return iid


NEXT = {"action": "edit", "next": [{"kind": "nothing", "title": "", "reason": "Fixed, nothing follows"}],
        "summary_sentences": [{"slot": "s1", "text": "The cut-off moved.", "sources": [{"label": "Outcome", "ref": "outcome"}]}]}


def test_owner_then_reporter_then_organiser_close(world, monkeypatch):
    plane, c = world
    from sh_platform.intents import memory_close
    called = []
    monkeypatch.setattr(memory_close, "write_closure_memory", lambda p, r: called.append(r["id"]))
    from sh_platform.graph import hooks
    from sh_platform.intents import problem as prob
    monkeypatch.setattr(prob, "write_back", lambda p, r, q=None: called.append("write_back") or {})
    monkeypatch.setattr(hooks, "mark_dirty", lambda p: called.append("map"))
    iid = problem(plane)
    put(c, "a-org", iid, **NEXT)
    r = put(c, "a-org", iid, action="close")
    assert r.status_code == 409 and "Waiting for the owner, Harvey" in r.json()["detail"]
    assert put(c, "a-rep", iid, action="sign").status_code == 403          # the reporter cannot go first
    assert put(c, "a-p1", iid, action="sign").status_code == 403
    assert put(c, "a-own", iid, action="sign").status_code == 200
    assert "Waiting for the reporter, Katie" in put(c, "a-org", iid, action="close").json()["detail"]
    assert put(c, "a-rep", iid, action="sign").status_code == 200
    assert put(c, "a-own", iid, action="close").status_code == 403         # only the organiser closes
    r = put(c, "a-org", iid, action="close")
    assert r.status_code == 200 and r.json()["state"] == "closed"
    rec = S.read_intent(plane, iid)
    assert [x["role"] for x in rec["closure"]["confirmed"]] == ["owner", "reporter"] and rec["closure"]["closed_by"] == "a-org"
    assert rec["rating"]["rated"] == [] and rec["outcome_used"]["ask_at"] > rec["closure"]["closed_at"]
    assert rec["closing_started_at"] and called[-3:] == ["write_back", iid, "map"] and called.count("map") >= 1  # R11: write-back, memory, map at close; the map also learns the closing start (FX5)
    assert rec["outcome"]["writeback"] == {}
    assert "Signed by Harvey" in r.json()["strip"]


def test_close_with_what_we_have_and_edit_clears_signature(world):
    plane, c = world
    iid = make(plane, "decision", decider="a-spon")                           # no decision, no why recorded
    put(c, "a-org", iid, **NEXT)
    r = put(c, "a-org", iid, action="close")
    assert r.status_code == 409 and "outcome is missing" in r.json()["detail"]
    assert put(c, "a-org", iid, action="close_incomplete").status_code == 400   # a reason is needed
    put(c, "a-spon", iid, action="sign")
    put(c, "a-org", iid, action="edit", why_it_happened="Changed after signing")
    assert S.read_intent(plane, iid)["closure"]["confirmed"] == []            # an edit after signing asks again
    put(c, "a-spon", iid, action="sign")
    r = put(c, "a-org", iid, action="close_incomplete", reason="The decider was away")
    assert r.status_code == 200
    cl = S.read_intent(plane, iid)["closure"]
    assert cl["incomplete"] and "Decision" in cl["missing"] and cl["incomplete_reason"] == "The decider was away"
    assert r.json()["strip"].startswith("Closed with what we have")


def test_cancel_needs_a_reason_and_keeps_it_in_one_place(world):
    plane, c = world
    iid = problem(plane)
    app = c.app
    app.include_router(records.router)
    assert c.post(f"/api/intents/{iid}/cancel", json={"version": 2}, headers={"x-as": "a-org"}).status_code == 400
    r = c.post(f"/api/intents/{iid}/cancel", json={"version": 2, "cancel_reason": "Merged into another problem"}, headers={"x-as": "a-org"})
    assert r.status_code == 200
    rec = S.read_intent(plane, iid)
    assert rec["state"] == "cancelled" and rec["closure"]["cancel_reason"] == "Merged into another problem"
    v = c.get(f"/api/intents/{iid}/closure", headers={"x-as": "a-p1"}).json()
    assert v["cancelled"] and v["cancel"]["reason"] == "Merged into another problem" and v["you"]["can_close"] is False


def closed_problem(plane, c):
    iid = problem(plane)
    put(c, "a-org", iid, **NEXT)
    put(c, "a-own", iid, action="sign")
    put(c, "a-rep", iid, action="sign")
    assert put(c, "a-org", iid, action="close").status_code == 200
    return iid


def rate(c, who, iid, **body):
    return c.post(f"/api/intents/{iid}/ratings", json=body, headers={"x-as": who})


def test_ratings_anonymous_by_default_aggregate_from_three(world):
    plane, c = world
    iid = closed_problem(plane, c)
    assert rate(c, "a-out", iid, score=3).status_code == 404                  # sees nothing of it
    S.update_intent(plane, iid, S.read_intent(plane, iid)["version"], lambda r: r["people"].update(observers=[person("a-out")]))
    assert rate(c, "a-out", iid, score=3).status_code == 403                  # an observer is not asked
    assert rate(c, "a-p1", iid, score=0).status_code == 400
    assert rate(c, "a-p1", iid, score=4, note="Good people, too few numbers").status_code == 200
    assert rate(c, "a-p1", iid, score=5).status_code == 409                   # one per person, no edits
    rec = S.read_intent(plane, iid)
    assert rec["ratings"] == [{"by": None, "anonymous": True, "score": 4, "note": "", "at": rec["ratings"][0]["at"]}]
    assert "a-p1" not in json.dumps(rec["ratings"]) and rec["rating"]["rated"] == ["a-p1"]
    own = c.get(f"/api/intents/{iid}/ratings", headers={"x-as": "a-p1"}).json()["mine"]     # the person's own file keeps the link
    assert own["score"] == 4 and own["note"].startswith("Good people") and own["anonymous"] is True
    org = c.get(f"/api/intents/{iid}/ratings", headers={"x-as": "a-org"}).json()["summary"]
    assert org["rated"] == 1 and org["mean"] is None and org["bar"] is None and org["anonymous_count"] == 1
    rate(c, "a-p2", iid, score=5, note="Clear", anonymous=False)
    org = c.get(f"/api/intents/{iid}/ratings", headers={"x-as": "a-org"}).json()["summary"]
    assert org["mean"] is None and "Not shown until three" in org["hidden"]
    assert org["signed"] == [{"name": "Mei Ling", "score": 5, "note": "Clear"}]
    rate(c, "a-own", iid, score=4)
    org = c.get(f"/api/intents/{iid}/ratings", headers={"x-as": "a-org"}).json()["summary"]
    assert org["mean"] == 4.3 and org["bar"] == {"1": 0, "2": 0, "3": 0, "4": 2, "5": 1} and org["count"] == 3
    assert "Good people" not in json.dumps(org)                              # an anonymous note never reaches the organiser
    other = c.get(f"/api/intents/{iid}/ratings", headers={"x-as": "a-p3"}).json()
    assert other["summary"] is None                                          # a participant sees nothing of others'


def test_no_per_person_figure_and_the_waive(world):
    plane, c = world
    iid = closed_problem(plane, c)
    for q in ("by=a-p1", "person=a-p1", "per_person=1"):
        assert c.get(f"/api/intents/{iid}/ratings?{q}", headers={"x-as": "a-org"}).status_code == 400
    assert c.post(f"/api/intents/{iid}/rating/waive", headers={"x-as": "a-p3"}).status_code == 200
    assert c.get(f"/api/intents/{iid}/ratings", headers={"x-as": "a-p3"}).json()["waived"] is True
    assert ratings.mean([{"score": 5}, {"score": 4}]) is None and ratings.mean([{"score": 5}, {"score": 4}, {"score": 4}]) == 4.3


def test_the_weekly_series_is_never_rated(world):
    plane, c = world
    iid = make(plane, "pulse", participants=["a-p1", "a-p2"])
    put(c, "a-org", iid, **NEXT)
    r = put(c, "a-org", iid, action="close")
    assert r.status_code == 200
    rec = S.read_intent(plane, iid)
    assert not rec.get("rating") and not rec.get("outcome_used") and "rating" not in rec["closure"]
    assert r.json()["rating"] is None and r.json()["rated"] is False
    assert rate(c, "a-p1", iid, score=5).status_code == 409
    assert ratings.window_open(rec, datetime.now(timezone.utc)) is False


def test_anonymous_contributions_are_only_a_count_and_small_counts_are_hidden(world):
    plane, c = world
    iid = problem(plane)
    lines = [{"kind": "card_added", "by": {"account": "a-p1"}, "anonymous": False, "sealed": False}] * 2 \
        + [{"kind": "card_added", "by": {"account": "a-p2"}, "anonymous": True, "sealed": False}] * 3 \
        + [{"kind": "card_added", "by": {"account": "a-p3"}, "anonymous": False, "sealed": True}]
    plane.path("intents", iid, "events.jsonl").write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    v = c.get(f"/api/intents/{iid}/closure", headers={"x-as": "a-org"}).json()
    assert v["anonymous_count"] == 3
    rows = {r["name"]: r for r in v["people"]}
    assert rows["Aaron"]["label"] == "Fewer than five" and rows["Aaron"]["count"] is None
    assert "Mei Ling" in rows and rows["Mei Ling"]["label"] == "Fewer than five"
    assert rows["Ravi"]["label"] == "Fewer than five"                        # the sealed line is not counted at all
    outsider = c.get(f"/api/intents/{iid}/closure", headers={"x-as": "a-out"})
    assert outsider.status_code == 404


def test_the_approver_link_signs_once_and_a_send_back_clears_it(world):
    plane, c = world
    iid = make(plane, "decision", decider="a-spon")
    S.update_intent(plane, iid, 1, lambda r: r["outcome"].update(chosen="Sweep on Thursday", why="Banks cut off at four"))
    put(c, "a-org", iid, **NEXT)
    assert put(c, "a-spon", iid, action="send").status_code == 403           # only the organiser sends a link
    sent = put(c, "a-org", iid, action="send").json()["sent"]
    token = sent["link"].removeprefix("/approve/")
    assert "hash" not in json.dumps(S.read_intent(plane, iid)["closure"]["links"][0].get("token", ""))
    assert closure.TOKEN.fullmatch(token)
    page = closure.approver_read(plane, token)
    assert page["title"] == "Late sweeps" and "id" not in page and page["role"] == "decider"
    with pytest.raises(closure.LinkGone):
        closure.approver_decide(plane, token, "decline", "  ")               # a send-back needs a comment
    closure.approver_decide(plane, token, "decline", "Say which bank")
    assert S.read_intent(plane, iid)["closure"]["send_back"]["comment"] == "Say which bank"
    with pytest.raises(closure.LinkGone):
        closure.approver_read(plane, token)                                   # one use
    token2 = put(c, "a-org", iid, action="send").json()["sent"]["link"].removeprefix("/approve/")
    assert put(c, "a-org", iid, action="withdraw").status_code == 200
    with pytest.raises(closure.LinkGone):
        closure.approver_decide(plane, token2, "approve", "")                 # withdrawn
    token3 = put(c, "a-org", iid, action="send").json()["sent"]["link"].removeprefix("/approve/")
    closure.approver_decide(plane, token3, "approve", "")
    cl = S.read_intent(plane, iid)["closure"]
    assert cl["signature"]["how"] == "approver" and cl["signature"]["name"] == "Daniel" and cl["send_back"] is None
    assert put(c, "a-org", iid, action="close").status_code == 200


def test_children_are_written_from_the_next_list_after_closure(world):
    plane, c = world
    iid = problem(plane)
    put(c, "a-org", iid, action="edit", next=[{"kind": "backlog", "title": "Look at the cut-off", "reason": "Not urgent"},
                                              {"kind": "initiative", "title": "Automate sweeps", "reason": "Bigger than a fix"}])
    put(c, "a-org", iid, action="draft")
    put(c, "a-own", iid, action="sign")
    put(c, "a-rep", iid, action="sign")
    assert put(c, "a-org", iid, action="close").status_code == 200
    rec = S.read_intent(plane, iid)
    refs = [n["ref"] for n in rec["closure"]["next"]]
    assert refs[0].startswith("bk-") and refs[1] in rec["links"]["to"]
    child = S.read_intent(plane, refs[1])
    assert child["state"] == "draft" and child["links"]["from"] == iid and child["type"] == "initiative"
    assert json.loads(plane.path("intents", "backlog.json").read_text())["items"][0]["source"]["intent_id"] == iid


def test_close_needs_the_version_and_a_summary(world):
    plane, c = world
    iid = problem(plane)
    put(c, "a-org", iid, action="edit", next=NEXT["next"])
    put(c, "a-own", iid, action="sign")
    put(c, "a-rep", iid, action="sign")
    r = c.put(f"/api/intents/{iid}/closure", json={"action": "close"}, headers={"x-as": "a-org"})
    assert r.status_code == 400 and "version" in r.json()["detail"]
    assert put(c, "a-org", iid, action="close", version=1).status_code == 409   # an old version is refused
    r = put(c, "a-org", iid, action="close")
    assert r.status_code == 400 and "summary" in r.json()["detail"]             # no summary sentence: refused, no stand-in text
    put(c, "a-org", iid, action="draft")
    assert put(c, "a-org", iid, action="close").status_code == 200


def test_initiative_sponsor_confirms_through_the_charter_and_cancel_by_action(world):
    plane, c = world
    iid = make(plane, "initiative", sponsor="a-spon", participants=["a-p1"])
    S.update_intent(plane, iid, 1, lambda r: (r["outcome"].update(signed_at=S.now_iso(), signed_by="Daniel"),
                                              r.update(build_needed=False, build_needed_reason="Reporting only")))
    put(c, "a-org", iid, **NEXT)
    v = c.get(f"/api/intents/{iid}/closure", headers={"x-as": "a-org"}).json()
    assert v["signature"][0]["state"] == "signed" and v["signature"][0]["how"] == "charter"
    assert "Signed charter" in v["outcome"]["missing"]            # no charter outcome file in this plane, so close with what we have
    r = put(c, "a-org", iid, action="close_incomplete", reason="Charter file kept in the old store")
    assert r.status_code == 200 and S.read_intent(plane, iid)["closure"]["confirmed"][0]["how"] == "charter"
    other = make(plane, "brainstorm", state="open")
    assert put(c, "a-org", other, action="cancel").status_code == 400
    assert put(c, "a-org", other, action="cancel", cancel_reason="Merged with the treasury one").status_code == 200
    assert S.read_intent(plane, other)["closure"]["cancel_reason"] == "Merged with the treasury one"


def test_brainstorm_what_next_initiative_is_prefilled_and_linked_both_ways(world):
    plane, c = world
    iid = make(plane, "brainstorm", participants=["a-p1"])
    S.update_intent(plane, iid, 1, lambda r: (r.update(areas=["Treasury"]),
                                              r["outcome"].update(chosen={"idea": "Sweep from the noon file", "why": "The file is ready by noon", "ref": "c1"})))
    put(c, "a-org", iid, action="edit", next=[{"kind": "initiative", "title": "", "reason": "Bigger than a fix",
                                               "answers": {"i1": {"goal_line": "Sweep every day from the noon file"}}}])
    put(c, "a-org", iid, action="draft")
    assert put(c, "a-org", iid, action="close").status_code == 200
    rec = S.read_intent(plane, iid)
    ref = rec["closure"]["next"][0]["ref"]
    assert ref and ref in rec["links"]["to"] and rec["outcome"]["next"] == {"kind": "initiative", "title": "", "reason": "Bigger than a fix"}
    child = S.read_intent(plane, ref)
    assert child["links"]["from"] == iid and child["title"] == "Sweep from the noon file" and child["state"] == "draft"
    goal = child["start_answers"]["goal"]
    assert goal["mark"] == "guessed" and goal["prefilled_from"]["intent_id"] == iid
    assert goal["value"] == {"line": "Sweep every day from the noon file", "why": "The file is ready by noon"}
    assert any(r["dir"] == "from" for r in child.get("link_log") or []) and any(r["dir"] == "to" for r in rec.get("link_log") or [])


def test_initiative_close_view_has_the_build_strip_and_close_without_hand_off_needs_a_reason(world):
    plane, c = world
    iid = make(plane, "initiative", sponsor="a-spon", participants=["a-p1"])
    S.update_intent(plane, iid, 1, lambda r: (r["outcome"].update(signed_at=S.now_iso(), signed_by="Daniel"), r.update(build_needed=True)))
    put(c, "a-org", iid, **NEXT)
    v = c.get(f"/api/intents/{iid}/closure", headers={"x-as": "a-org"}).json()
    assert v["build_ready"]["text"] == "Not checked yet." and v["build_ready"]["can_skip"] and v["build_ready"]["href"].endswith("/build-ready")
    assert c.get(f"/api/intents/{iid}/closure", headers={"x-as": "a-p1"}).json()["build_ready"]["can_skip"] is False
    assert put(c, "a-org", iid, action="close_incomplete", no_handoff=True).status_code == 400
    assert put(c, "a-org", iid, action="close_incomplete", no_handoff=True, reason="Charter only, no build").status_code == 200
    assert S.read_intent(plane, iid)["closure"]["no_handoff_reason"] == "Charter only, no build"
    other = make(plane, "problem")
    assert c.get(f"/api/intents/{other}/closure", headers={"x-as": "a-org"}).json()["build_ready"] is None


def test_a_refusal_carries_a_message_and_the_view_lists_what_closing_needs(world):
    plane, c = world
    iid = make(plane, "initiative", sponsor="a-spon", participants=["a-p1"])
    r = put(c, "a-org", iid, action="close", no_handoff=True, reason="Charter only")
    assert r.status_code == 409 and r.json()["message"] == r.json()["detail"] and r.json()["message"]
    reqs = {x["key"]: x for x in c.get(f"/api/intents/{iid}/closure", headers={"x-as": "a-org"}).json()["build_ready"]["requirements"]}
    assert list(reqs) == ["build", "summary", "next", "sponsor"]
    assert not reqs["build"]["done"] and not reqs["summary"]["done"] and reqs["build"]["href"].endswith("/build-ready")
    put(c, "a-org", iid, **NEXT)
    reqs = {x["key"]: x for x in c.get(f"/api/intents/{iid}/closure", headers={"x-as": "a-org"}).json()["build_ready"]["requirements"]}
    assert reqs["summary"]["done"] and reqs["next"]["done"]


def test_people_roles_read_in_full_and_the_panel_is_the_one_people_source(world):
    plane, c = world
    iid = make(plane, "problem", affected=["a-p1"], participants=["a-p2"], advisers=["a-p3"])
    v = c.get(f"/api/intents/{iid}/closure", headers={"x-as": "a-org"}).json()
    roles = {r["role"] for r in v["people"]}
    assert {"affected", "participant", "adviser"} <= roles and "affecte" not in roles
    S.update_intent(plane, iid, S.read_intent(plane, iid)["version"], lambda r: None)
    assert [r["role"] for r in closure.people_rows(plane, S.read_intent(plane, iid))["rows"]] == [r["role"] for r in v["people"]]


def test_decision_closure_reads_the_option_name_and_asks_the_decider_again_after_an_edit(world):
    """FX1: the decider's choice already confirmed; the summary it wrote shows before North drafts; the draft proposes a next row
    with its reason; an edit that changes nothing keeps the signature; a real edit clears it and asks the decider again."""
    plane, c = world
    iid = make(plane, "decision", decider="a-spon")

    def decided(r):
        r["outcome"].update(options=[{"id": "opt-1", "name": "Use month-end"}, {"id": "opt-2", "name": "Use quarter-end"}],
                            chosen="opt-1", why="It matches the fund admin cut-off.")
        r["closure"].update(summary="Decided: Use month-end. By Daniel.", confirmed=[{"role": "decider", "by": "a-spon", "at": S.now_iso()}])
    S.update_intent(plane, iid, 1, decided)
    v = c.get(f"/api/intents/{iid}/closure", headers={"x-as": "a-spon"}).json()
    assert v["outcome"]["lines"][0] == {"label": "Decision", "value": "Use month-end"}
    assert [s["text"] for s in v["sentences"]] == ["Decided: Use month-end. By Daniel."] and not v["you"]["can_sign"]
    r = put(c, "a-org", iid, action="draft").json()
    assert r["next"][0]["reason"].startswith("The decision itself is the outcome: Use month-end")
    assert r["signature"][0]["state"] == "signed"                           # North's draft is not an edit
    same = put(c, "a-org", iid, action="edit", next=r["next"]).json()
    assert same["signature"][0]["state"] == "signed" and same["asked_again"] is None
    rows = [{**s, "text": "We settled the valuation date."} if i == 0 else s for i, s in enumerate(r["sentences"])]
    put(c, "a-org", iid, action="edit", summary_sentences=rows)
    v = c.get(f"/api/intents/{iid}/closure", headers={"x-as": "a-spon"}).json()
    assert v["signature"][0]["state"] == "waiting" and v["you"]["can_sign"] and v["asked_again"]["by"] == "Janet"
    assert "Waiting for the decider, Daniel" in put(c, "a-org", iid, action="close").json()["detail"]
    v = put(c, "a-spon", iid, action="sign").json()
    assert v["signature"][0]["state"] == "signed" and v["asked_again"] is None
    assert put(c, "a-org", iid, action="close").json()["state"] == "closed"
