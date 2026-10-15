"""B30: the affected person and the observer (file 47). A mini app signs people in by a name set per request."""
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.intents import affected, store
from sh_platform.intents.access import Me
from sh_platform.plane import PlaneStore

ID = "prb-" + "a" * 32
NAMES = {"a-janet": "Janet Shaw", "a-daniel": "Daniel Kerr", "a-aaron": "Aaron Lyle", "a-katie": "Katie", "a-harvey": "Harvey Rowley",
         "a-grace": "Grace Ward", "a-admin": "Admin Person"}


def person(acct):
    return {"account_id": acct, "name": NAMES[acct]}


def record(**over):
    rec = {"id": ID, "type": "problem", "title": "Slow packing list", "purpose": "Sign-off is the slow step", "created_by": "a-janet",
           "company": "ardmore", "areas": ["operations"], "state": "open", "affected_may_read": False,
           "people": {"organiser": person("a-janet"), "sponsor": person("a-daniel"), "decider": None, "owner": None, "reporter": None,
                      "participants": [person("a-aaron")], "advisers": [], "affected": [person("a-harvey"), person("a-grace")],
                      "observers": [person("a-katie")]},
           "time_box": {"starts": "2026-10-01T00:00:00+00:00", "ends": "2099-01-01T00:00:00+00:00", "extended_by": []},
           "stages": [], "outcome": {"kind": "problem"}, "closure": {"summary": "Done well", "cancel_reason": None, "closed_at": None},
           "ratings": [], "links": {"from": None, "to": [], "build": None}, "share": {"link": None, "who_may_open": []}, "history": []}
    rec.update(over)
    return rec


@pytest.fixture
def world(tmp_path):
    (tmp_path / "planes").mkdir()
    plane = PlaneStore(tmp_path / "planes").create("ardmore")
    store.create_intent(plane, record())
    app = FastAPI()
    app.include_router(affected.router)
    app.state.settings = SimpleNamespace(data_root=plane.root.parent)
    app.state.account_store = SimpleNamespace(get=lambda a: {"display_name": NAMES.get(a, a)}, in_company=lambda c: [])
    who = {"id": "a-harvey", "roles": ["participant"]}

    @app.middleware("http")
    async def sign_in(request, call_next):
        request.state.company_id, request.state.account_id, request.state.roles = "ardmore", who["id"], who["roles"]
        return await call_next(request)
    c = TestClient(app)
    c.as_ = lambda acct, *roles: who.update(id=acct, roles=list(roles) or ["participant"])
    c.plane = plane
    return c


def side(c):
    return json.loads(c.plane.path("intents", ID, "affected.json").read_text())


def notes(c):
    return c.get(f"/api/intents/{ID}/notes").json()


def test_switch_off_hides_content_and_on_opens_it(world):
    c = world
    c.as_("a-harvey")
    assert notes(c)["may_read"] is False
    shut = c.post(f"/api/intents/{ID}/feel", json={"item": "card-1"})  # a card: the wall is closed to them
    assert shut.status_code == 403 and "intent_content_closed" in shut.text and "You can see that this exists" in shut.text
    assert c.put(f"/api/intents/{ID}/affected-access", json={"read_content": True}).status_code == 403  # only the organiser
    c.as_("a-janet")
    assert c.put(f"/api/intents/{ID}/affected-access", json={"read_content": True}).json() == {"read_content": True}
    rec = store.read_intent(c.plane, ID)
    assert rec["affected_may_read"] is True and rec["history"][-1]["to"] == "affected read: on"
    c.as_("a-harvey")
    assert notes(c)["may_read"] is True
    assert c.post(f"/api/intents/{ID}/feel", json={"item": "card-1"}).status_code == 200


def test_observer_reads_but_every_write_is_refused(world):
    c = world
    c.as_("a-katie")
    assert notes(c)["mine"]["role"] == "observer"
    assert c.post(f"/api/intents/{ID}/feel", json={"item": "intent"}).status_code == 403
    assert c.request("DELETE", f"/api/intents/{ID}/feel", json={"item": "intent"}).status_code == 403
    assert c.post(f"/api/intents/{ID}/notes", json={"text": "hello"}).status_code == 403
    assert c.put(f"/api/intents/{ID}/affected-access", json={"read_content": True}).status_code == 403
    assert c.post(f"/api/intents/{ID}/join-requests", json={"asked_role": "participant", "reason": "I can help"}).status_code == 403  # follow only
    assert c.post(f"/api/intents/{ID}/follow", json={"follow": True}).json() == {"follow": True}


def test_feel_this_counts_without_names_unless_signed(world):
    c = world
    c.as_("a-harvey")
    assert c.post(f"/api/intents/{ID}/feel", json={"item": "intent", "signed": False}).status_code == 200
    assert c.post(f"/api/intents/{ID}/feel", json={"item": "intent"}).status_code == 409  # one tap each
    c.as_("a-grace")
    got = c.post(f"/api/intents/{ID}/feel", json={"item": "intent", "signed": True}).json()
    assert got["taps"] == []  # an affected person gets no counts, only their own state
    c.as_("a-aaron")  # a participant
    got = c.post(f"/api/intents/{ID}/feel", json={"item": "intent"}).json()["taps"][0]
    assert (got["total"], got["affected"], got["participant"], got["names"]) == (3, 2, 1, [])  # counts only
    raw = json.dumps(side(c))
    assert "a-harvey" not in raw and raw.count("anon-") == 2  # the unsigned taps name nobody
    c.as_("a-janet")
    assert notes(c)["panel"]["taps"][0]["names"] == ["Grace Ward"]  # the organiser sees the signed name only
    c.as_("a-harvey")
    assert notes(c)["mine"]["tapped"] == ["intent"]
    assert c.request("DELETE", f"/api/intents/{ID}/feel", json={"item": "intent"}).json()["tapped"] is False  # take it back
    assert len(side(c)["feel_taps"]) == 2


def test_note_to_the_organiser(world):
    c = world
    c.as_("a-harvey")
    assert c.post(f"/api/intents/{ID}/notes", json={"text": "  "}).status_code == 422
    assert c.post(f"/api/intents/{ID}/notes", json={"text": "x" * 501}).status_code == 422
    c.post(f"/api/intents/{ID}/notes", json={"text": "Packing-list sign-off is slow", "signed": True})
    c.as_("a-grace")
    c.post(f"/api/intents/{ID}/notes", json={"text": "Custody worries me", "signed": False})
    c.as_("a-aaron")
    assert "notes" not in notes(c)["panel"]  # a participant never reads a note
    c.as_("a-admin", "company_admin")
    assert "notes" not in notes(c)["panel"]  # the company admin sees counts only
    c.as_("a-daniel")
    assert "notes" in notes(c)["panel"]  # the sponsor reads
    assert c.post(f"/api/intents/{ID}/notes/x/reply", json={"text": "hi"}).status_code in (403, 404)  # and cannot answer
    c.as_("a-janet")
    rows = notes(c)["panel"]["notes"]
    assert {n["from"] for n in rows} == {"Harvey Rowley", None}
    signed, unsigned = next(n for n in rows if n["from"]), next(n for n in rows if not n["from"])
    assert c.post(f"/api/intents/{ID}/notes/{unsigned['id']}/reply", json={"text": "thanks"}).status_code == 422
    assert c.post(f"/api/intents/{ID}/notes/{signed['id']}/reply", json={"text": "Thanks Harvey"}).status_code == 200
    assert [n["seen_at"] is not None for n in notes(c)["panel"]["notes"]].count(True) == 1
    c.as_("a-harvey")
    assert [x["text"] for x in notes(c)["mine"]["replies"]] == ["Thanks Harvey"]


def test_ask_to_join_accept_and_decline_with_reason(world):
    c = world
    c.as_("a-harvey")
    assert c.post(f"/api/intents/{ID}/join-requests", json={"reason": " "}).status_code == 422
    assert c.post(f"/api/intents/{ID}/join-requests", json={"reason": "I run the packing list"}).status_code == 200
    assert c.post(f"/api/intents/{ID}/join-requests", json={"reason": "again"}).status_code == 409  # one open request
    c.as_("a-grace")
    c.post(f"/api/intents/{ID}/join-requests", json={"reason": "Finance sees it too"})
    c.as_("a-daniel")
    assert notes(c)["panel"]["can_answer"] is False
    c.as_("a-janet")
    reqs = {r["name"]: r for r in notes(c)["panel"]["requests"]}

    def url(r):
        return f"/api/intents/{ID}/join-requests/{r['id']}/answer"
    assert c.post(url(reqs["Grace Ward"]), json={"action": "decline"}).status_code == 422  # a reason is required
    assert c.post(url(reqs["Grace Ward"]), json={"action": "decline", "reason": "Wall is full"}).status_code == 200
    assert c.post(url(reqs["Harvey Rowley"]), json={"action": "accept", "role": "participant"}).json() == {"state": "accepted"}
    rec = store.read_intent(c.plane, ID)
    assert [p["name"] for p in rec["people"]["participants"]] == ["Aaron Lyle", "Harvey Rowley"]
    assert [p["name"] for p in rec["people"]["affected"]] == ["Grace Ward"] and rec["history"][-1]["to"] == "participant"
    c.as_("a-grace")
    mine = notes(c)["mine"]["request"]
    assert (mine["state"], mine["decline_reason"]) == ("declined", "Wall is full")
    assert c.post(f"/api/intents/{ID}/join-requests", json={"reason": "please"}).status_code == 409  # not repeated after a decline


def test_pulse_lines_at_open_and_close_only(world):
    c = world

    def me(acct, *areas):
        return Me(acct, NAMES[acct], frozenset(), False, None, frozenset(areas))
    grace, katie, aaron = me("a-grace", "operations"), me("a-katie"), me("a-aaron")
    first = affected.watch_lines(c.plane, grace)
    assert [x["id"] for x in first] == [f"affected-open:{ID}"]
    assert first[0]["detail"] == "Janet Shaw opened a Problem that touches operations. Nothing is asked of you."
    assert affected.watch_lines(c.plane, katie) and not affected.watch_lines(c.plane, aaron)  # an observer gets it, a participant does not
    c.as_("a-grace")
    notes(c)  # she opens it: the line goes
    assert affected.watch_lines(c.plane, grace) == []

    def stage(rec):  # a stage change in between makes no line
        rec["stages"] = [{"key": "x", "state": "open"}]
    store.update_intent(c.plane, ID, store.read_intent(c.plane, ID)["version"], stage)

    def close(rec):
        rec["state"], rec["closure"] = "closed", {"summary": "Fixed it", "cancel_reason": None, "closed_at": "2026-10-09T00:00:00Z"}
    assert affected.watch_lines(c.plane, grace) == []
    store.update_intent(c.plane, ID, store.read_intent(c.plane, ID)["version"], close)
    assert [(x["id"], x["title"], x["detail"]) for x in affected.watch_lines(c.plane, grace)] == [
        (f"affected-close:{ID}", "What came out of Slow packing list", "Fixed it")]
    notes(c)  # the outcome is read: the line goes
    assert affected.watch_lines(c.plane, grace) == [] and side(c)["seen"]["a-grace"]["closed_seen_at"]
    assert c.post(f"/api/intents/{ID}/notes", json={"text": "late"}).status_code == 409  # closed


def test_open_request_is_withdrawn_when_the_intent_closes(world):
    c = world
    c.as_("a-harvey")
    c.post(f"/api/intents/{ID}/join-requests", json={"reason": "I run it"})
    store.update_intent(c.plane, ID, store.read_intent(c.plane, ID)["version"], lambda r: r.update(state="closed"))
    affected.close_sweep(c.plane, ID)
    assert (side(c)["join_requests"][0]["state"], side(c)["join_requests"][0]["decline_reason"]) == ("withdrawn", "Intent closed")
