"""SF02: Span's and Flow's suggestions, the decide routes and the event kinds. Synthetic data, a temporary plane, the proposals routes on a bare
app with the signed-in person injected (the permission lines are the orchestrator's). chain.open_note is stubbed in the fixture; the last test runs the real one."""
import hashlib
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.build import chain as C, proposals as P
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer

WHO = {"grace": Viewer("Grace Ward", frozenset({"approver"})), "katie": Viewer("Katie Menon", frozenset({"analyst"})),
       "aaron": Viewer("Aaron Lyle", frozenset({"participant"})), "harvey": Viewer("Harvey Rowley", frozenset({"owner"})),
       "daniel": Viewer("Daniel Kerr", frozenset({"sponsor"}))}
FACTS = [{"label": "fund rows", "value": 1180, "group_size": 1180}, {"label": "keys changed", "value": 214, "group_size": 1180}]


def _w(plane, rel, doc):
    p = plane.path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def _mc(subject="fund dimension", measure="K12", **kw):
    return {"kind": "model_change", "args": {"title": "Keep fund manager history", "what": "Type 2 history on the fund dimension",
                                             "why": "214 of 1180 fund rows changed manager", "subject": subject, "measure": measure, "technique": "scd2",
                                             "evidence": {"counts": [{"label": "keys changed", "value": 214, "group_size": 1180}], "fields": ["manager"]},
                                             "impact": {"marts": ["gold.k12"]}, "effort": "small", **kw}}


@pytest.fixture
def world(tmp_path, monkeypatch):
    store = PlaneStore(tmp_path)
    plane, other = store.create("sf02-co"), store.create("sf02-other")
    _w(plane, "build/blueprint.json", {"version": 3, "state": "signed", "signed_by": [{"name": "Grace Ward", "role": "Head of department"}],
                                       "access": [{"mart": "gold.k12", "may_see": None}, {"mart": "gold.k06", "may_see": ["Daniel Kerr"]}]})
    _w(plane, "intents/m1_intent/roles/s1.json", {"roles": {}, "names": {"architect": "Aaron Lyle"}})
    _w(plane, "build/alerts.json", {"alerts": [{"id": "late:custodian_file", "kind": "late", "source": "custodian_file", "state": "open", "tell": "Harvey Rowley"}]})
    from sh_platform.consume import cards
    monkeypatch.setattr(cards, "data_owner", lambda p, code: {"K12": "Grace Ward", "K06": "Daniel Kerr"}.get(code))
    monkeypatch.setattr(C, "people_of", lambda p, i: {r: {"name": n, "mark": "stated"} for r, n in
                                                       {"architect": "Aaron Lyle", "head_of_department": "Grace Ward", "developer": "Katie Menon",
                                                        "tester": None, "ops": "Harvey Rowley"}.items()})
    opened = []

    def open_note(pl, title, sections, people, source, by):
        if any(o["source"] == source for o in opened):
            return {}
        note = {"id": f"C-{len(opened) + 1:04d}", "title": title, "sections": sections, "source": source, "by": by}
        opened.append(note)
        return note
    monkeypatch.setattr(C, "open_note", open_note, raising=False)
    app, me = FastAPI(), {"v": WHO["grace"]}
    app.include_router(P.router)
    monkeypatch.setattr(P, "_plane", lambda r: plane)
    monkeypatch.setattr(P, "_viewer", lambda r: me["v"])

    def as_(who):
        me["v"] = WHO[who]
        return TestClient(app)
    return plane, other, as_, opened


def test_file_validates_dedupes_caps_and_traces(world):
    plane, *_ = world
    bad_key = _mc(subject="a")
    bad_key["args"]["colour"] = "red"
    untraced = _mc(subject="b")
    untraced["args"]["why"] = "999 rows changed"
    small = _mc(subject="c")
    small["args"]["evidence"]["counts"][0]["group_size"] = 4
    items = [bad_key, untraced, small, _mc(), _mc(), _mc(subject="d", measure=None), _mc(subject="e"), _mc(subject="f"),
             {"kind": "incident_note", "args": {"title": "t", "what": "w", "why": "y", "alert_id": "late:custodian_file"}}]
    got = P.file(plane, "Span", items, {"run_id": "r1", "facts": FACTS})
    assert [p["subject"] for p in got] == ["fund dimension", "d", "e"]  # duplicates, refused, untraced, over three: dropped
    assert got[0]["to"] == "Grace Ward" and got[0]["to_role"] == "data owner" and got[1]["to_role"] == "blueprint signer"
    assert not any(k in json.dumps(got) for k in ('"rows"', '"records"'))
    assert P.file(plane, "Span", [_mc()], {"facts": FACTS}) == []  # one open proposal per kind and target
    assert P.file(plane, "Flow", [items[-1]], {"facts": FACTS})[0]["to"] == "Harvey Rowley"  # Flow may file an incident note


def test_only_the_addressee_decides_and_decline_needs_a_reason(world):
    plane, _, as_, _ = world
    pid = P.file(plane, "Span", [_mc()], {"facts": FACTS})[0]["id"]
    assert as_("katie").get(f"/api/company/build/proposals/{pid}").json()["can_decide"] is False
    for act in ("accept", "decline", "ask"):
        assert as_("katie").post(f"/api/company/build/proposals/{pid}/{act}", json={"reason": "x", "text": "x"}).status_code == 403
    assert as_("aaron").post(f"/api/company/build/proposals/{pid}/accept").status_code == 404  # not visible to him at all
    assert as_("grace").post(f"/api/company/build/proposals/{pid}/decline", json={}).status_code == 422
    r = as_("grace").post(f"/api/company/build/proposals/{pid}/ask", json={"text": "How many marts read it?"}).json()
    assert r["state"] == "asked" and r["thread"][0]["by"] == "Grace Ward"
    r = as_("grace").post(f"/api/company/build/proposals/{pid}/decline", json={"reason": "Not this quarter"}).json()
    assert r["state"] == "declined" and r["decided"]["reason"] == "Not this quarter"


def test_accepting_a_model_change_opens_one_note_and_leaves_the_signed_blueprint(world, monkeypatch):
    plane, _, as_, opened = world
    pid = P.file(plane, "Span", [_mc()], {"facts": FACTS})[0]["id"]
    bp = plane.path("build", "blueprint.json")
    before = hashlib.sha256(bp.read_bytes()).hexdigest()
    monkeypatch.delattr(C, "open_note")
    r = as_("grace").post(f"/api/company/build/proposals/{pid}/accept")
    assert r.status_code == 409 and r.json()["message"].startswith("Not available yet") and P.read(plane, pid)["state"] == "proposed"
    monkeypatch.setattr(C, "open_note", lambda *a: opened.append(a[4]) or {"id": "C-0001"}, raising=False)
    r = as_("grace").post(f"/api/company/build/proposals/{pid}/accept")
    assert r.status_code == 200 and r.json()["result"] == {"change_id": "C-0001"} and opened == [{"kind": "proposal", "id": pid, "accepted_by": "Grace Ward"}]
    assert as_("grace").post(f"/api/company/build/proposals/{pid}/accept").status_code == 409
    assert len(opened) == 1 and hashlib.sha256(bp.read_bytes()).hexdigest() == before


def test_open_from_proposal_quotes_the_proposal(world):
    plane, _, _, opened = world
    p = P.file(plane, "Span", [_mc()], {"facts": FACTS})[0]
    note = P.open_from_proposal(plane, p, "Grace Ward")
    why = [ln["text"] for ln in note["sections"]["why"]]
    assert why[0] == f"From Span's suggestion {p['id']}: Keep fund manager history" and "Evidence: keys changed: 214" in why
    assert note["sections"]["tests"][0]["measure"] == "K12" and note["source"]["id"] == p["id"] and note["by"] == "Span"
    assert P.open_from_proposal(plane, p, "Grace Ward") == {}


def test_a_changed_model_makes_the_proposal_stale(world):
    plane, _, as_, _ = world
    pid = P.file(plane, "Span", [_mc()], {"facts": FACTS})[0]["id"]
    _w(plane, "build/blueprint.json", {"version": 4, "state": "draft", "signed_by": [], "access": []})
    assert as_("grace").post(f"/api/company/build/proposals/{pid}/accept").json()["error"] == "stale"


def test_restricted_measure_is_hidden_outside_its_list(world):
    plane, _, as_, _ = world
    pid = P.file(plane, "Span", [_mc(subject="pay", measure="K06")], {"facts": FACTS})[0]["id"]
    assert as_("katie").get(f"/api/company/build/proposals/{pid}").status_code == 404
    assert pid not in {p["id"] for p in as_("katie").get("/api/company/build/proposals").json()["proposals"]}
    assert as_("daniel").get(f"/api/company/build/proposals/{pid}").status_code == 200


def test_ids_and_planes_are_refused(world):
    plane, other, as_, _ = world
    P.file(other, "Span", [_mc(), _mc(subject="x")], {"facts": FACTS})
    for bad in ("..%2F..%2Fsecret", "P-0002", "P-1", "C-0001"):
        assert as_("katie").get(f"/api/company/build/proposals/{bad}").status_code == 404
    assert P.read(plane, "../P-0001") is None
    with pytest.raises(ValueError):
        P._path(plane, "../../P-0001")


def test_incident_note_and_decision_apply(world):
    plane, _, as_, _ = world
    inc = P.file(plane, "Flow", [{"kind": "incident_note", "args": {"title": "Late file", "what": "Ask the custodian for the file again",
                                                                    "why": "The file has not landed", "alert_id": "late:custodian_file"}}], {"facts": []})[0]
    assert P.pulse_lines(plane, WHO["harvey"])["decide"][0]["title"] == "Span wrote a note on the custodian file alert. Check it."
    assert as_("harvey").post(f"/api/company/build/proposals/{inc['id']}/accept").status_code == 200
    a = json.loads(plane.path("build", "alerts.json").read_text())["alerts"][0]
    assert a["state"] == "acknowledged" and a["by"] == "Harvey Rowley" and a["note"].startswith("Ask the custodian")
    _w(plane, "build/changes/C-0001.json", {"id": "C-0001", "intent_id": None, "state": "with_architect", "sections": {"decisions": []}})
    dec = P.file(plane, "Span", [{"kind": "architecture_decision", "args": {
        "title": "Where the mart sits", "what": "Keep it in the main file", "why": "it has no access list", "change_id": "C-0001",
        "placement": "Stale share mart", "options": ["Main file", "Restricted file"], "chosen": "Main file"}}], {"facts": []})[0]
    assert dec["to"] == "Aaron Lyle"
    assert P.pulse_lines(plane, WHO["aaron"])["decide"][0]["title"] == "Span suggests a change to Stale share mart. Decide."
    as_("aaron").post(f"/api/company/build/proposals/{dec['id']}/accept")
    line = json.loads(plane.path("build", "changes", "C-0001.json").read_text())["sections"]["decisions"][0]
    assert line["mark"] == "stated" and line["by"] == "Aaron Lyle" and line["chosen"] == "Main file"


def test_event_kinds_for_span_and_flow(tmp_path):
    from sh_platform.intents import events as E
    plane = PlaneStore(tmp_path).create("sf02-ev")
    _w(plane, "intents/ini-sf02/intent.json", {"id": "ini-sf02", "state": "open", "stages": []})
    assert E.append_event(plane, "ini-sf02", "span_drafted", "span", {"store": "build.proposals", "id": "P-0001"}, {"what": "suggestion", "ref": "P-0001"}, "draft")["agent"] == "span"
    assert E.append_event(plane, "ini-sf02", "flow_drafted", "flow", None, {"what": "run_note"}, "draft")["agent"] == "flow"
    with pytest.raises(E.EventRefused):
        E.append_event(plane, "ini-sf02", "span_drafted", "flow", None, {"what": "x"}, "draft")
    e = E.append_event(plane, "ini-sf02", "proposal_decided", {"account": "a1", "name": "Grace Ward"}, None, {"pid": "P-0001", "decision": "accepted"}, "act")
    assert e["by"]["name"] == "Grace Ward"
    with pytest.raises(E.EventRefused):
        E.append_event(plane, "ini-sf02", "proposal_decided", "span", None, {"pid": "P-0001"}, "act")


def test_accept_opens_a_real_change_note(tmp_path, monkeypatch):
    """chain.open_note itself, on a temporary plane: the note opens at step 1, marked from the proposal, the people from the charter."""
    from sh_platform.consume import cards
    plane = PlaneStore(tmp_path).create("sf02-real")
    _w(plane, "build/blueprint.json", {"version": 1, "state": "signed", "signed_by": [{"name": "Grace Ward"}], "access": []})
    monkeypatch.setattr(cards, "data_owner", lambda p, code: None)
    monkeypatch.setattr(C, "people_of", lambda p, i: {r: {"name": n, "mark": "stated"} for r, n in
                                                       {"architect": "Aaron Lyle", "head_of_department": "Grace Ward", "developer": "Katie Menon",
                                                        "tester": None, "ops": "Harvey Rowley"}.items()})
    app = FastAPI()
    app.include_router(P.router)
    monkeypatch.setattr(P, "_plane", lambda r: plane)
    monkeypatch.setattr(P, "_viewer", lambda r: WHO["grace"])
    pid = P.file(plane, "Span", [_mc()], {"facts": FACTS})[0]["id"]
    r = TestClient(app).post(f"/api/company/build/proposals/{pid}/accept").json()
    note = json.loads(plane.path("build", "changes", f"{r['result']['change_id']}.json").read_text())
    assert note["id"] == "C-0001" and note["state"] == "with_architect" and note["source"]["id"] == pid and note["intent_id"] is None
    assert note["people"]["architect"] == "Aaron Lyle" and note["sections"]["why"][0]["text"].startswith(f"From Span's suggestion {pid}")
    assert all(ln["mark"] == "guessed" and ln["by"] == "Span" for ln in note["sections"]["why"])
    assert P.open_from_proposal(plane, P.read(plane, pid), "Grace Ward") == {}  # one note per proposal
