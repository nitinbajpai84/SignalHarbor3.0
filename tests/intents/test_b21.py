"""B21: brainstorm converge (back up to three, counts never who, seat keys dropped, ties to the organiser), the outcome card and what next."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sh_platform.egress import rows
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.intents import access as A
from sh_platform.intents import converge as C
from sh_platform.intents import lifecycle as L
from sh_platform.intents import store as S
from sh_platform.plane import PlaneStore

ORG = {"account_id": "acct-janet", "name": "Janet Shaw"}
PEOPLE = [{"account_id": f"acct-p{i}", "name": f"Person {i}"} for i in range(1, 6)]
OBSERVER = {"account_id": "acct-obs", "name": "Olive Observer"}


def viewer(p) -> A.Me:
    return A.Me(p["account_id"], p["name"], frozenset(["participant"]))


@pytest.fixture
def world(tmp_path):
    plane = PlaneStore(tmp_path).create("lakeside-family-office")
    rec = L.new_record("brainstorm", "lakeside-family-office", ORG, S.now_iso(), title="Investor day ideas", purpose="Ideas", areas=["Finance"])
    rec["outcome"]["anonymous_ideas"] = True
    rec["people"]["participants"], rec["people"]["observers"] = PEOPLE, [OBSERVER]
    rec["state"] = "open"
    rec["stages"] = [{"key": "choose", "name": "Choose", "state": "open", "opened_at": S.now_iso(), "closed_at": None}]
    S.create_intent(plane, rec)
    ideas = [("Host a private talk", "g1", False), ("Invite the auditors", "g1", False), ("Open the vault", "g1", True),
             ("Share a reading list", None, False), ("Quarterly picnic", None, False), ("New lobby art", None, False)]
    doc = {"salt": "x", "ideas": [{"id": f"i{n}", "text": t, "anonymous": anon, "owner": f"owner-{n}", "author": None if anon else f"Person {n + 1}", "withdrawn": False,
                                    "replies": [], "moves": [], "edits": []} for n, (t, g, anon) in enumerate(ideas)],
           "groups": [{"id": "g1", "name": "Client events", "idea_ids": ["i0", "i1", "i2"], "by": "north"}]}
    plane.path("intents", rec["id"], "ideas.json").write_text(json.dumps(doc), encoding="utf-8")
    return SimpleNamespace(plane=plane, id=rec["id"])


def act(w, fn):
    rec, _ = C._mutate(w.plane, w.id, lambda r, ev: fn(r, ev))
    return rec


def opened(w):
    act(w, lambda r, ev: C.do_open(w.plane, r, {}, S.now_iso()))


def back(w, p, ref, on=True):
    C.do_back(w.plane, S.read_intent(w.plane, w.id), viewer(p), ref, on)


def close(w, picks=None):
    act(w, lambda r, ev: C.do_close(w.plane, r, {"account": ORG["account_id"], "name": ORG["name"], "role": "organiser"}, S.now_iso(), picks, ev))
    C.drop_votes(w.plane, w.id)


def view_for(w, p, rec=None):
    rec = rec or S.read_intent(w.plane, w.id)
    v = viewer(p)
    return C.build_view(w.plane, rec, v, C.relation(rec, v), lambda a: a)


def refs(w):
    return {c["text"]: c["ref"] for c in C.candidates(w.plane, S.read_intent(w.plane, w.id))}


def test_back_up_to_three_and_take_back(world):
    opened(world)
    r = refs(world)
    for t in ("Client events", "Share a reading list", "Quarterly picnic"):
        back(world, PEOPLE[0], r[t])
    with pytest.raises(L.Refused) as e:
        back(world, PEOPLE[0], r["New lobby art"])
    assert e.value.message == "You have used all three. Take one back first."
    back(world, PEOPLE[0], r["Quarterly picnic"], False)
    back(world, PEOPLE[0], r["New lobby art"])
    v = view_for(world, PEOPLE[0])
    assert v["converge"]["used"] == 3 and len(v["mine"]) == 3


def test_counts_never_who(world):
    opened(world)
    r = refs(world)
    back(world, PEOPLE[0], r["Client events"])
    back(world, PEOPLE[1], r["Client events"])
    back(world, PEOPLE[1], r["Quarterly picnic"])
    a, b = view_for(world, PEOPLE[0]), view_for(world, PEOPLE[2])
    row = lambda v: next(x for x in v["rows"] if x["ref"] == r["Client events"])  # noqa: E731
    assert row(a)["backed"] == row(b)["backed"] == 2 and row(a)["i_backed"] and not row(b)["i_backed"]
    assert a["have_backed"] == 2 and a["seated_count"] == 6 and a["north"] == "2 of 6 have backed."
    org_view = json.dumps(view_for(world, ORG))
    for p in PEOPLE:  # nothing in what the organiser reads names or keys a backer
        assert p["account_id"] not in org_view and C.seat_key(world.id, p["account_id"]) not in org_view
    assert view_for(world, ORG)["mine"] == []


def test_observer_and_closed_round_cannot_back(world):
    with pytest.raises(L.Refused) as e:
        back(world, PEOPLE[0], "c:i3")
    assert e.value.message == "The count has not opened."
    opened(world)
    assert C.relation(S.read_intent(world.plane, world.id), viewer(OBSERVER))["seated"] is False


def test_seat_keys_dropped_at_close(world):
    opened(world)
    r = refs(world)
    back(world, PEOPLE[0], r["Client events"])
    back(world, PEOPLE[1], r["Share a reading list"])
    key = C.seat_key(world.id, PEOPLE[0]["account_id"])
    assert key in C._votes_file(world.plane, world.id).read_text(encoding="utf-8")
    close(world)
    assert not C._votes_file(world.plane, world.id).exists()
    for f in world.plane.path("intents", world.id).rglob("*"):
        if f.is_file():
            body = f.read_text(encoding="utf-8")
            assert key not in body and "votes" not in body, f.name
    oc = S.read_intent(world.plane, world.id)["outcome"]
    assert oc["rounds"][0]["people_backed"] == 2 and oc["converge"]["state"] == "round_1_closed"
    assert {i["text"]: i["backed"]["round1"] for i in oc["ideas_kept"]}["Client events"] == 1


def test_plan_top_tie_goes_to_organiser():
    counts = {"a": 5, "b": 3, "c": 3, "d": 3, "e": 0}
    top, tie = C.plan_top(counts, list(counts), 3)
    assert top == ["a"] and tie == {"among": ["b", "c", "d"], "free": 2, "count": 3, "resolved": False, "picks": []}
    top, tie = C.plan_top(counts, list(counts), 3, ["b", "d"])
    assert top == ["a", "b", "d"] and tie["resolved"]
    assert C.plan_top({"a": 2, "b": 1, "c": 1, "d": 1}, ["a", "b", "c", "d"], 3)[1] is not None
    assert C.plan_top({"a": 4, "b": 3, "c": 2, "d": 1}, ["a", "b", "c", "d"], 3) == (["a", "b", "c"], None)


def test_tie_blocks_round_two_until_the_organiser_picks(world):
    opened(world)
    r = refs(world)
    for p in PEOPLE[:3]:
        back(world, p, r["Client events"])
    for p in PEOPLE[:2]:
        back(world, p, r["Share a reading list"])
        back(world, p, r["Quarterly picnic"])
    for p in PEOPLE[2:4]:
        back(world, p, r["New lobby art"])
    close(world)
    rec = S.read_intent(world.plane, world.id)
    tie = C.ranking(rec["outcome"], C.counts_now(world.plane, rec, C.candidates(world.plane, rec)))["tie"]
    assert tie["free"] == 2 and len(tie["among"]) == 3 and not tie["resolved"]
    assert view_for(world, ORG)["can"]["round2"] == "Pick which ideas go forward first."
    with pytest.raises(L.Refused):
        act(world, lambda rr, ev: C.do_round2(world.plane, rr, {}, S.now_iso()))
    with pytest.raises(L.Refused):  # exactly the free places
        close(world, tie["among"])
    close(world, tie["among"][:2])
    assert S.read_intent(world.plane, world.id)["outcome"]["rounds"][0]["tie_broken_by"] == ORG["account_id"]
    act(world, lambda rr, ev: C.do_round2(world.plane, rr, {}, S.now_iso()))
    oc = S.read_intent(world.plane, world.id)["outcome"]
    assert len(oc["rounds"]) == 2 and oc["rounds"][1]["candidates"] == [r["Client events"], *tie["among"][:2]]
    assert oc["converge"]["state"] == "round_2_open"
    back(world, PEOPLE[0], oc["rounds"][1]["candidates"][0])
    with pytest.raises(L.Refused) as e:
        back(world, PEOPLE[0], oc["rounds"][1]["candidates"][1])
    assert e.value.message == "You have used your one back. Take it back first."


def _confirmed(world):
    opened(world)
    r = refs(world)
    for p in PEOPLE[:3]:
        back(world, p, r["Client events"])
    back(world, PEOPLE[3], r["Quarterly picnic"])
    close(world)
    actor = {"account": ORG["account_id"], "name": ORG["name"], "role": "organiser"}
    act(world, lambda rr, ev: C.do_draft(world.plane, rr, actor, S.now_iso(), None, ev))
    return actor, r


def test_outcome_card_every_sentence_has_a_source_and_no_backer(world):
    actor, r = _confirmed(world)
    ch = S.read_intent(world.plane, world.id)["outcome"]["chosen"]
    assert ch["kind"] == "group" and ch["backed"] == 3 and ch["backed_of"] == 6
    assert ch["why_sources"] and all(s["source"].strip() for s in ch["why_sources"])
    assert " ".join(s["text"] for s in ch["why_sources"]) == ch["why"]
    assert ch["why_sources"][0] == {"text": "3 of 6 backed it.", "source": "3 of 6 backed"}
    assert [p["name"] for p in ch["proposed_by"]] == ["Person 1", "Person 2"] and ch["proposed_unnamed"] == 1  # the anonymous card is counted, not named
    assert all(t["source"] for t in ch["what_it_takes"]) and ch["what_it_takes"][-1]["source"] == "north_suggestion"
    assert json.dumps(ch).count("acct-") == 0
    with pytest.raises(L.Refused):  # a draft never replaces what is there
        act(world, lambda rr, ev: C.do_draft(world.plane, rr, actor, S.now_iso(), None, ev))
    act(world, lambda rr, ev: C.do_edit(world.plane, rr, actor, S.now_iso(), {"why": "3 of 6 backed it. It fits the investor day."}, ev))
    ch = S.read_intent(world.plane, world.id)["outcome"]["chosen"]
    assert [s["source"] for s in ch["why_sources"]] == ["3 of 6 backed", "Written by the organiser"] and ch["drafted_by"] is None


def test_override_needs_a_reason_and_confirm_opens_the_late_window(world):
    actor, r = _confirmed(world)
    with pytest.raises(L.Refused) as e:
        act(world, lambda rr, ev: C.do_edit(world.plane, rr, actor, S.now_iso(), {"ref": r["Quarterly picnic"]}, ev))
    assert e.value.message == "Why this one when another had more backs?"
    act(world, lambda rr, ev: C.do_edit(world.plane, rr, actor, S.now_iso(), {"what_it_takes": []}, ev))
    with pytest.raises(L.Refused) as e:
        act(world, lambda rr, ev: C.do_confirm(world.plane, rr, actor, S.now_iso(), ev))
    assert "what it would take" in e.value.message
    act(world, lambda rr, ev: C.do_edit(world.plane, rr, actor, S.now_iso(), {"what_it_takes": [{"text": "To be found out"}]}, ev))
    act(world, lambda rr, ev: C.do_confirm(world.plane, rr, actor, S.now_iso(), ev))
    rec = S.read_intent(world.plane, world.id)
    oc = rec["outcome"]
    assert rec["state"] == "closing" and oc["converge"]["state"] == "done" and oc["chosen"]["confirmed_by"]["name"] == "Janet Shaw"
    assert oc["late_window"]["closes_at"] > oc["late_window"]["opens_at"]
    events = [json.loads(x) for x in world.plane.path("intents", world.id, "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["kind"] for e in events] == ["count_closed", "outcome_drafted", "outcome_confirmed"]
    assert "acct-p1" not in json.dumps(events)


def test_late_thought_then_frozen(world):
    actor, r = _confirmed(world)
    act(world, lambda rr, ev: C.do_confirm(world.plane, rr, actor, S.now_iso(), ev))
    rec = S.read_intent(world.plane, world.id)
    ref = rec["outcome"]["chosen"]["ref"]
    act(world, lambda rr, ev: C.do_late(world.plane, rr, viewer(PEOPLE[0]), C._now(), {"text": "Add a dinner", "about": ref, "anonymous": True}, ev))
    th = S.read_intent(world.plane, world.id)["outcome"]["late_thoughts"][0]
    assert th["by"] is None and th["anonymous"]
    with pytest.raises(L.Refused):
        act(world, lambda rr, ev: C.do_late(world.plane, rr, viewer(PEOPLE[0]), C._now(), {"text": "x" * 301, "about": ref}, ev))
    shown = view_for(world, PEOPLE[1])["late"]
    assert shown["thoughts"][0]["name"] is None and shown["can_add"]
    assert not view_for(world, OBSERVER)["late"]["can_add"]
    late = lambda rr, ev: C.do_late(world.plane, rr, viewer(PEOPLE[0]), C._now() + timedelta(days=5), {"text": "Too late", "about": ref}, ev)  # noqa: E731
    with pytest.raises(L.Refused) as e:
        act(world, late)
    assert e.value.message == "This record is frozen."


def test_next_kinds_and_prefill(world):
    actor, r = _confirmed(world)
    v = view_for(world, ORG)
    assert v["next_kinds"] == ["initiative", "problem", "decision", "backlog", "handled", "nothing"]
    qs = {q["id"]: q for q in v["prefill"]["questions"]}
    assert len(qs) == 6 and len(qs["i1"]["answers"]["goal_line"]) <= 140 and qs["i1"]["from_brainstorm"]
    assert "Person 1" in qs["i2"]["answers"]["involve"] and "Person 2" in qs["i2"]["answers"]["involve"]
    assert qs["i5"]["answers"]["areas"] == ["Finance"]
    assert not any(qs[i]["from_brainstorm"] for i in ("i3", "i4", "i6"))
    assert v["backlog_preview"]["raised_by"] == "Person 1, Person 2" and v["backlog_preview"]["review_date"] is None


def test_routes_organiser_only_and_observer_read(world, monkeypatch):
    app = FastAPI()
    app.include_router(C.router)
    app.state.account_store = SimpleNamespace(get=lambda a: {"display_name": a})
    who = {"p": ORG}
    monkeypatch.setattr(C, "_plane", lambda request: world.plane)
    monkeypatch.setattr(A.Me, "of", staticmethod(lambda request, plane: viewer(who["p"])))
    c = TestClient(app)
    url = f"/api/intents/{world.id}/converge"
    who["p"] = PEOPLE[0]
    assert c.post(f"{url}/open").status_code == 403
    who["p"] = ORG
    assert c.post(f"{url}/open").json()["converge"]["state"] == "round_1_open"
    who["p"] = OBSERVER
    assert c.get(url).status_code == 200
    assert c.post(f"{url}/back", json={"candidate": "c:i3", "on": True}).status_code == 403
    who["p"] = PEOPLE[0]
    assert c.post(f"{url}/back", json={"candidate": "c:i3", "on": True}).json()["converge"]["used"] == 1
    who["p"] = {"account_id": "acct-stranger", "name": "Sam Stranger"}
    assert c.get(url).status_code == 404


def _req():
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(entitlements=object(), north_model_factory=lambda p: object())))


def test_outcome_drafted_through_the_runtime_falls_back_labelled_and_keeps_the_organisers_lines(world, monkeypatch):
    """F10, R14: the outcome card's wording comes from the runtime; a failed call keeps the counted sentences, marked so the screen says so;
    picking another idea keeps the organiser's own lines (rule 7)."""
    from sh_platform.intents import north as N
    sent = []

    def fake_call(plane_, model, gate, system, context, question):
        sent.append(json.dumps(context))
        assert rows.json_findings(json.dumps({"context": context, "question": question}))[0] is None  # the gateway would send it
        return json.dumps({"idea": "Client events for the investor day.", "why": [{"text": "3 of 6 backed it, 77 times.", "source": "3 of 6 backed"},
                                                                               {"text": "Invented.", "source": "nowhere"}]})
    monkeypatch.setattr(N, "_call", fake_call)
    opened(world)
    r = refs(world)
    for p in PEOPLE[:3]:
        back(world, p, r["Client events"])
    back(world, PEOPLE[3], r["Quarterly picnic"])
    close(world)
    actor = {"account": ORG["account_id"], "name": ORG["name"], "role": "organiser"}
    act(world, lambda rr, ev: C.do_draft(world.plane, rr, actor, S.now_iso(), None, ev, _req()))
    ch = S.read_intent(world.plane, world.id)["outcome"]["chosen"]
    assert sent and ch["fallback"] is False and ch["idea"] == "Client events for the investor day."
    assert ch["why_sources"] == [{"text": "3 of 6 backed it, times.", "source": "3 of 6 backed"}]  # untraced number and unsourced line dropped
    assert not any(x in blob for blob in sent for x in ("acct-", "owner-", "Person 1"))
    rec = S.read_intent(world.plane, world.id)
    assert C.outcome_view(rec, True, {"reader": True})["chosen"]["fallback"] is False  # the flag reaches the screen
    act(world, lambda rr, ev: C.do_edit(world.plane, rr, actor, S.now_iso(), {"what_it_takes": [{"text": "Book the room"}]}, ev))
    monkeypatch.setattr(N, "_call", lambda *a: None)  # the model cannot answer
    body = {"ref": r["Quarterly picnic"], "overridden_reason": "Cheaper"}
    act(world, lambda rr, ev: C.do_edit(world.plane, rr, actor, S.now_iso(), body, ev, _req()))
    rec = S.read_intent(world.plane, world.id)
    ch = rec["outcome"]["chosen"]
    assert ch["fallback"] is True and C.outcome_view(rec, True, {"reader": True})["chosen"]["fallback"] is True
    assert {"text": "Book the room", "source": "Added by the organiser"} in ch["what_it_takes"]


def test_w2f5_hand_typed_kept_line_without_ref_never_breaks_the_read(world):
    act(world, lambda r, ev: r["outcome"].update(ideas_kept=[{"text": "Typed by hand"}, "stray"], dropped=[{"text": "x", "reason": "y"}]))
    v = view_for(world, PEOPLE[0])
    assert v["id"] == world.id
    assert C.counts_now(world.plane, S.read_intent(world.plane, world.id), C.candidates(world.plane, S.read_intent(world.plane, world.id))) is not None
