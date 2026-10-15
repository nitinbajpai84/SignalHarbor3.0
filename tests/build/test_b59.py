"""B59a: the Build chain and the architecture record (spec 59). Synthetic data only, a temporary plane, the chain routes on a bare app with the
signed-in person injected (the permission lines are the orchestrator's)."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.build import architecture as A, chain as C
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer

INTENT = "ini-" + "b59a" * 8
NAMES = {"architect": "Aaron Lyle", "head_of_department": "Grace Ward", "developer": "Katie Menon", "tester": "Mei Ling Chong", "ops": "Harvey Rowley"}
PEOPLE = {n.lower().replace(" ", "-"): {"name": {"value": n}, "role": {"value": "Analyst"}, "team": {"value": "Risk"}}
          for n in [*NAMES.values(), "Janet Shaw", "Daniel Kerr"]}
WHO = {"aaron": Viewer("Aaron Lyle", frozenset({"participant"})), "grace": Viewer("Grace Ward", frozenset({"approver"})),
       "katie": Viewer("Katie Menon", frozenset({"analyst"})), "mei": Viewer("Mei Ling Chong", frozenset({"owner"})),
       "harvey": Viewer("Harvey Rowley", frozenset({"owner"})), "janet": Viewer("Janet Shaw", frozenset({"company_admin"}), account_id="acct-janet"),
       "daniel": Viewer("Daniel Kerr", frozenset({"sponsor"}))}


def _w(plane, rel: str, doc) -> None:
    p = plane.path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def _r(plane, rel: str):
    return json.loads(plane.path(*rel.split("/")).read_text(encoding="utf-8"))


@pytest.fixture
def world(tmp_path, monkeypatch):
    plane = PlaneStore(tmp_path).create("b59a-co")
    _w(plane, "build/blueprint.json", {
        "version": 1, "state": "draft", "signed_by": [], "band": "now", "provenance": {}, "rules": [], "schedule": [], "model": {"facts": []},
        "infra": {"warehouse": "plane", "runner": "builtin"},
        "lineage": [{"measure": "K12", "source": "Custodian file", "mart": "gold.k12.stale_share", "transform": "Stale holdings over all holdings"},
                    {"measure": "K06", "source": "Payroll file", "mart": "gold.k06.pay", "transform": "Pay"}],
        "access": [{"mart": "gold.k12", "may_see": None}, {"mart": "gold.k06", "may_see": ["Daniel Kerr"]}]})
    _w(plane, "build/pipelines/custodian_file.json", {"source": "custodian_file", "title": "Custodian file", "marts": ["gold.k12"], "owner": "Harvey Rowley",
                                                      "expected": "Daily", "sla": "WD8", "lands_at": "landing", "pattern": "custodian*.csv"})
    _w(plane, "warehouse/runs.json", {"runs": [{"source": "custodian_file", "status": "ok"}]})
    _w(plane, "intents/m3_connect/outcomes/o1.json", {"outcome_id": "o1", "kind": "plan", "assessment_id": "a1", "signed_at": "2026-09-01T00:00:00+00:00",
                                                      "accepted_risks": [{"measures": ["K12"], "text": "Statements arrive late"}, {"measures": ["K01"], "text": "Other"}]})
    _w(plane, "intents/m1_intent/roles/s1.json", {"roles": {}, "names": NAMES})
    _w(plane, "intents/hypotheses/h1.json", {"id": "h1", "origin": {"kind": "initiative", "ref": INTENT}, "versions": [
        {"belief": "Chasing lowers the stale share", "measure": {"id": "K12", "name": "Stale valuation share"},
         "baseline": {"value": 0.33, "periods": ["2026-05"]}, "target": {"value": 0.1, "by": "2026-11-30"}, "review_date": "2026-11-30"}]})
    _w(plane, "build/prove.json", {"band": "now", "release": {"state": "draft"}, "measures": [
        {"code": "K12", "periods": [{"period": "2026-07", "result": "match"}], "uat": {"state": "signed", "by": "X", "at": "2026-09-05T00:00:00+00:00"}}]})
    intent = {"id": INTENT, "type": "initiative", "title": "B59a valuation chase", "areas": ["risk"], "refs": {"wall_session_ids": ["s1"]},
              "links": {"build": "build:a1"}, "build_handoff": {"by": {"name": "Janet Shaw"}, "at": "2026-09-02T00:00:00+00:00"},
              "people": {"organiser": {"account_id": "acct-janet", "name": "Janet Shaw"}}}
    from sh_platform.intents import store as istore
    from sh_platform.profile import store as pstore
    monkeypatch.setattr(istore, "read_index", lambda p: [{"id": INTENT, "type": "initiative"}])
    monkeypatch.setattr(istore, "read_intent", lambda p, i: intent if i == INTENT else None)
    monkeypatch.setattr(pstore, "raw", lambda p: {"people": PEOPLE, "systems": {}, "areas": {}})
    from sh_platform.build.agents import runtime as R, span_arch
    monkeypatch.setattr(span_arch, "draft_change_note", lambda *a, **k: None)  # no model call in tests; gate 1 tests below override this
    monkeypatch.setattr(R, "runtime_for_plane", lambda plane, viewer=None: object())
    app, me = FastAPI(), {"v": WHO["aaron"]}
    C.install(app)
    for mod in (C, A):
        monkeypatch.setattr(mod, "_plane", lambda r: plane)
        monkeypatch.setattr(mod, "_viewer", lambda r: me["v"])

    def as_(who):
        me["v"] = WHO[who]
        return TestClient(app)
    return plane, as_


def test_the_chain_end_to_end(world, monkeypatch):
    plane, as_ = world
    ch = as_("aaron").get("/api/company/build/changes").json()["changes"]
    assert [c["id"] for c in ch] == ["C-0001"] and ch[0]["step"] == 1 and ch[0]["steps"][0]["person"] == "Aaron Lyle"
    note = as_("aaron").get("/api/company/build/changes/C-0001").json()
    assert note["can_act"] and {"gold:k12", "source:custodian_file"} <= {ln.get("component") for ln in note["sections"]["what_changes"]}
    assert all(ln["mark"] == "guessed" and ln["from"] for k in C.SECTIONS for ln in note["sections"][k])
    assert [r["text"] for r in note["sections"]["risks"]] == ["Statements arrive late"]
    assert as_("grace").post("/api/company/build/changes/C-0001/send").status_code == 403
    assert as_("aaron").post("/api/company/build/changes/C-0001/send").json()["step"] == 2

    r = as_("grace").post("/api/company/build/changes/C-0001/approve")
    assert r.status_code == 409 and "no owner" in r.json()["message"] and "gold.k12" in r.json()["message"]  # North names the gap
    assert as_("grace").put("/api/company/build/architecture/components/gold:k12", json={"owner": "harvey-rowley"}).json()["owner"] == "Harvey Rowley"
    assert as_("aaron").post("/api/company/build/changes/C-0001/approve").status_code == 403  # only the head of department (C33)
    from sh_platform.build import design_doc
    signed = []
    monkeypatch.setattr(design_doc, "sign", lambda plane, by, role: signed.append((by, role)))
    assert as_("grace").post("/api/company/build/changes/C-0001/approve").json()["state"] == "building"
    assert signed == [("Grace Ward", "Head of department")]
    bp = _r(plane, "build/blueprint.json")
    assert bp["state"] == "signed" and bp["signed_by"][0] == {**bp["signed_by"][0], "name": "Grace Ward", "role": "Head of department"}
    rec = A.read(plane)
    assert rec["version"] == 1 and rec["regenerated"]["moment"] == "blueprint_signed"
    assert plane.path("build", "architecture", "diagrams", "data.v1.json").is_file() and plane.path("build", "architecture", "record.v1.json").is_file()
    assert {c["id"]: c["state"] for c in rec["components"]}["gold:k12"] == "approved"

    assert as_("katie").post("/api/company/build/changes/C-0001/built").json()["state"] == "testing"
    assert _r(plane, "build/prove.json")["measures"][0]["uat"]["state"] == "pending"  # a new build is tested again
    prove = _r(plane, "build/prove.json")
    prove["measures"][0]["uat"] = {"state": "sent_back", "by": "Mei Ling Chong", "at": datetime.now(timezone.utc).isoformat(), "note": "K12 differs for 2026-08"}
    _w(plane, "build/prove.json", prove)
    back = as_("katie").get("/api/company/build/changes/C-0001").json()
    assert back["state"] == "building" and back["returns"][-1]["reason"] == "K12 differs for 2026-08" and back["steps"][2]["state"] == "sent_back"
    assert as_("katie").post("/api/company/build/changes/C-0001/built").status_code == 200
    later = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
    prove = _r(plane, "build/prove.json")
    prove["measures"][0]["uat"] = {"state": "signed", "by": "Mei Ling Chong", "at": later, "note": ""}
    _w(plane, "build/prove.json", prove)
    assert as_("mei").get("/api/company/build/changes/C-0001").json()["state"] == "waiting_release"
    assert as_("harvey").post("/api/company/build/changes/C-0001/take-over").status_code == 409
    prove["release"] = {"state": "signed", "by": "Daniel Kerr", "at": later}
    _w(plane, "build/prove.json", prove)
    got = as_("harvey").get("/api/company/build/changes/C-0001").json()
    assert got["state"] == "with_ops" and got["release"]["by"] == "Daniel Kerr" and A.read(plane)["version"] == 2


def test_take_over_makes_it_live_and_alerts_go_to_ops(world):
    plane, as_ = world
    as_("aaron").post("/api/company/build/changes/C-0001/send")
    as_("grace").put("/api/company/build/architecture/components/gold:k12", json={"owner": "harvey-rowley"})
    as_("grace").post("/api/company/build/changes/C-0001/approve")
    assert C.alert_fields(plane, "custodian_file") == {"change_id": "C-0001", "tell": "Katie Menon"}
    note = _r(plane, "build/changes/C-0001.json")
    now = datetime.now(timezone.utc).isoformat()
    note.update(state="with_ops", release_ref={"by": "Daniel Kerr", "at": now})
    _w(plane, "build/changes/C-0001.json", note)
    assert as_("katie").post("/api/company/build/changes/C-0001/take-over").status_code == 403
    assert as_("harvey").post("/api/company/build/changes/C-0001/take-over").json()["state"] == "live"
    assert {c["id"]: c["state"] for c in A.read(plane)["components"]}["gold:k12"] == "live"
    assert C.alert_fields(plane, "custodian_file")["tell"] == "Harvey Rowley"


def test_send_back_stop_and_own_design(world):
    plane, as_ = world
    assert as_("aaron").post("/api/company/build/changes/C-0001/send-back", json={"to": 1, "reason": "x"}).status_code == 409
    as_("aaron").post("/api/company/build/changes/C-0001/send")
    assert as_("grace").post("/api/company/build/changes/C-0001/send-back", json={"to": 1}).status_code == 422
    r = as_("grace").post("/api/company/build/changes/C-0001/send-back", json={"to": 1, "reason": "Name the owners"}).json()
    assert r["step"] == 1 and r["last_return"]["reason"] == "Name the owners"
    assert as_("aaron").post("/api/company/build/changes/C-0001/stop", json={"reason": "No"}).status_code == 403
    s = as_("janet").post("/api/company/build/changes/C-0001/stop", json={"reason": "Priorities changed"}).json()
    assert s["state"] == "stopped" and not [c for c in A.read(plane)["components"] if c.get("made_by") == "C-0001"]


def test_restricted_component_is_a_silhouette(world):
    plane, as_ = world
    A.regenerate(plane, "blueprint_signed", "v1", "test", [])
    seen = {c["label"] for c in as_("katie").get("/api/company/build/architecture?view=data").json()["components"]}
    assert "gold.k06" not in seen and "Restricted" in seen
    hidden = next(c for c in as_("katie").get("/api/company/build/architecture?view=data").json()["components"] if c["label"] == "Restricted")
    assert hidden["owner"] is None and hidden["interfaces"] == [] and not hidden["id"].startswith("gold:")
    assert "gold.k06" in {c["label"] for c in as_("daniel").get("/api/company/build/architecture?view=data").json()["components"]}
    assert "gold.k06" not in json.dumps(as_("katie").get("/api/company/build/architecture?view=data").json()["diagram"])


def test_pulse_line_goes_to_the_person_whose_step_it_is(world):
    plane, as_ = world
    as_("aaron").get("/api/company/build/changes")
    assert C.pulse_lines(plane, WHO["aaron"])["decide"][0]["title"].startswith("Span drafted the change for B59a valuation chase")
    assert C.pulse_lines(plane, WHO["grace"])["decide"] == []


def test_open_note_and_agent_labels(world):
    plane, as_ = world
    n = C.open_note(plane, "Span proposal", {"why": ["Add a mart"], "risks": [{"text": "Late file"}]}, {"architect": "Aaron Lyle", "head_of_department": "Grace Ward"},
                    {"kind": "proposal", "id": "p1"}, "Span")
    assert n["source"] == {"kind": "proposal", "id": "p1"} and n["state"] == "with_architect"
    assert all(ln["mark"] == "guessed" and ln["by"] == "Span" for k in ("why", "risks") for ln in n["sections"][k])
    got = as_("aaron").get(f"/api/company/build/changes/{n['id']}").json()
    assert got["can_act"] and got["steps"][0]["person"] == "Aaron Lyle" and got["sections"]["why"][0]["text"] == "Add a mart"
    assert [s["name"] for s in got["steps"]][::2][:2] == ["Span, the architect", "Flow, the data engineer"]
    assert as_("aaron").post(f"/api/company/build/changes/{n['id']}/redraft", json={"note": "x"}).json()["sections"]["why"]  # kept
    assert C.open_note(plane, "Second", {}, {}, {"kind": "proposal", "id": "p2"}, "Span")["id"] == "C-0003"
    n2 = C.open_note(plane, "Third", {"why": ["Quoted why"], "tests": ["Quoted test"]}, {}, {"kind": "proposal", "id": "p3"}, "Span")
    again = C._draft(plane, n2, {}, None)["sections"]
    assert [x["text"] for x in again["why"]] == ["Quoted why"] and [x["text"] for x in again["tests"]] == ["Quoted test"]
    assert C.hypothesis(plane, {}) is None


def _span(monkeypatch, fallback, message=None):
    from sh_platform.build.agents import span_arch

    def fake(plane, note_id, rt, by):
        note = next(n for n in C.all_notes(plane) if n["id"] == note_id)
        secs = {k: list(v) for k, v in note["sections"].items()}
        if not fallback:
            secs["decisions"].append(C._ln("Span: put the mart in the warehouse", "span:test"))
        return {"note": {**note, "sections": secs}, "fallback": fallback, "message": message, "dropped": 0}
    monkeypatch.setattr(span_arch, "draft_change_note", fake)


def test_gate1_model_path_saves_spans_lines(world, monkeypatch):
    plane, as_ = world
    _span(monkeypatch, False)
    as_("aaron").get("/api/company/build/changes")  # ensure() opens C-0001 through the normal path
    got = as_("aaron").get("/api/company/build/changes/C-0001").json()
    assert "Span: put the mart in the warehouse" in [x["text"] for x in got["sections"]["decisions"]] and got["drafting_note"] is None
    r = as_("aaron").post("/api/company/build/changes/C-0001/redraft", json={"note": "again"}).json()
    assert [x["text"] for x in r["sections"]["decisions"]].count("Span: put the mart in the warehouse") >= 1


def test_gate1_fallback_keeps_rules_and_carries_message(world, monkeypatch):
    plane, as_ = world
    _span(monkeypatch, True, "Span could not reach the model, so these are the rule-based lines.")
    as_("aaron").get("/api/company/build/changes")
    got = as_("aaron").get("/api/company/build/changes/C-0001").json()
    assert got["drafting_note"].startswith("Span could not reach") and got["sections"]["what_changes"]
    assert as_("aaron").post("/api/company/build/changes/C-0001/redraft", json={"note": "again"}).json()["drafting_note"]


def test_gate1_missing_module_keeps_todays_behaviour(world, monkeypatch):
    plane, as_ = world
    import sys
    monkeypatch.setitem(sys.modules, "sh_platform.build.agents.span_arch", None)
    monkeypatch.delattr("sh_platform.build.agents.span_arch", raising=False)
    as_("aaron").get("/api/company/build/changes")
    got = as_("aaron").get("/api/company/build/changes/C-0001").json()
    assert got["drafting_note"] is None and got["sections"]["what_changes"]


def test_built_step_attaches_flows_run_notes(world, monkeypatch):
    plane, as_ = world
    from sh_platform.build.agents import flow
    _w(plane, "warehouse/runs.json", {"runs": [{"id": "a" * 32, "source": "custodian_file", "status": "ok"}]})
    seen = []
    monkeypatch.setattr(flow, "explain_run", lambda pl, rid, rt, **k: seen.append(rid) or {"run_id": rid, "text": "It ran.", "lines": ["It ran."]}, raising=False)
    as_("aaron").get("/api/company/build/changes")
    assert "run_notes" not in as_("aaron").get("/api/company/build/changes/C-0001").json()  # before gate 3 is pressed
    n = C._rd(C._path(plane, "C-0001"))
    n["state"] = "testing"
    C._save(plane, n)
    got = as_("mei").get("/api/company/build/changes/C-0001").json()
    assert got["run_notes"] == [{"source": "custodian_file", "run_id": "a" * 32, "note": {"run_id": "a" * 32, "text": "It ran.", "lines": ["It ran."]}}]
    assert seen == ["a" * 32]


def test_missing_flow_leaves_no_run_notes(world, monkeypatch):
    plane, as_ = world
    import sys
    monkeypatch.setitem(sys.modules, "sh_platform.build.agents.flow", None)
    monkeypatch.delattr("sh_platform.build.agents.flow", raising=False)
    as_("aaron").get("/api/company/build/changes")
    n = C._rd(C._path(plane, "C-0001"))
    n["state"] = "testing"
    C._save(plane, n)
    assert "run_notes" not in as_("mei").get("/api/company/build/changes/C-0001").json()
