"""F50: journey 50 through the routes, on a temporary copy of the demo data: an Initiative opens, the wall runs, Close the wall groups and
freezes it, Define opens with a baseline, the charter is drafted and signed, and the build-ready check reads the start answer.
Synthetic Ardmore data only; no model is called (the stubs answer None, so North groups by lanes and Lens drafts nothing)."""
import shutil
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
M1 = "/api/modules/m1_intent/sessions"
JANET, DANIEL, AARON = "company_admin.ardmore@example.test", "sponsor.ardmore@example.test", "participant.ardmore@example.test"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    if not CREDS.is_file():
        pytest.skip("no seeded demo data")
    data = tmp_path_factory.mktemp("f50") / "data"
    shutil.copytree(ROOT / "data", data, ignore=shutil.ignore_patterns("*.duckdb", "*.duckdb.wal"))
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.north_model_factory = lambda plane: None  # no model: North's grouping falls back, the charter keeps its own lines
    app.state.lens_model_factory = lambda plane: None
    pw = {line.split()[0]: line.split()[1] for line in CREDS.read_text().splitlines() if line.strip() and not line.startswith("#")}
    if JANET not in pw:
        pytest.skip("the seeded Ardmore role accounts are not loaded")
    people = {}
    for email in (JANET, DANIEL, AARON):
        c = TestClient(app, raise_server_exceptions=False)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
        people[email] = c
    return app, data, people


def cell(value, by="Janet Shaw"):
    return {"value": value, "mark": "stated", "by": by, "from": ""}


def test_journey_50_wall_to_build_ready(world):
    app, data, p = world
    j, d = p[JANET], p[DANIEL]
    who = {x["name"].split()[0]: x for x in j.get("/api/intents/people").json()["people"]}
    import json
    busy = {json.loads(f.read_text(encoding="utf-8"))["preparation"].get("topic") for f in (data / "ardmore" / "intents" / "m1_intent" / "sessions").glob("*.json")
            if json.loads(f.read_text(encoding="utf-8")).get("state") not in ("draft", "closed")}
    areas = [a for a in j.get("/api/intents/areas").json()["areas"] if a["name"] not in busy]  # one open wall per topic

    # step 1 and 2: the draft and the six answers
    rec = j.post("/api/intents", json={"type": "initiative"}).json()
    iid = rec["id"]
    deadline = date.fromisoformat(rec["created_at"][:10])
    from sh_platform.intents.initiative import add_working_days
    answers = {"goal": {"line": "F50 Cut the days to produce the quarterly client report", "why": "The family council waits two weeks for the pack."},
               "people": {"sponsor": {"account_id": who["Daniel"].get("account_id"), "name": who["Daniel"]["name"]},
                          "participants": [{"account_id": who["Aaron"].get("account_id"), "name": who["Aaron"]["name"]}], "affected": [], "just_me": False},
               "build": "yes", "definitions": "some", "areas": [areas[0]["id"]], "deadline": add_working_days(deadline, 10).isoformat()}
    for k, v in answers.items():
        r = j.put(f"/api/intents/{iid}/start", json={"version": rec["version"], "key": k, "cell": cell(v)})
        assert r.status_code == 200, (k, r.text)
        rec = r.json()
    r = j.post(f"/api/intents/{iid}/start/open", json={"version": rec["version"], "title": answers["goal"]["line"], "summary": {"text": "As I understood it.", "mark": "stated"}})
    assert r.status_code == 200, r.text
    rec = j.get(f"/api/intents/{iid}").json()
    assert rec["state"] == "open" and rec["build_needed"] is True  # step 2 writes the record's own answer (build-ready line 7)
    sid = rec["refs"]["wall_session_ids"][0]

    # step 3 and 4: the rooms open, the organiser puts two cards up from the pack's problem library
    r = j.post(f"{M1}/{sid}/start")
    assert r.status_code == 201, r.text
    assert j.post(f"{M1}/{sid}/briefing").status_code == 200
    assert j.post(f"{M1}/{sid}/briefing/send").status_code == 200, "rooms"
    for text in ("Three people rebuild the client pack by hand every quarter", "Custodian statements arrive late and in different layouts"):
        r = j.post(f"{M1}/{sid}/room/messages", json={"text": text, "kind": "note", "note_kind": "pain_point"})
        assert r.status_code == 200, r.text
    assert j.post(f"{M1}/{sid}/rooms/close").status_code == 200

    # step 5: Close the wall with nothing grouped: North groups first, the wall freezes, Define opens with a baseline
    r = j.post(f"{M1}/{sid}/together")
    assert r.status_code == 200, r.text
    rec = j.get(f"/api/intents/{iid}").json()
    stages = {s["key"]: s for s in rec["stages"]}
    assert stages["think_unfiltered"]["state"] == "closed" and stages["think_unfiltered"]["closed_at"]
    assert stages["define_strategically"]["state"] == "open"
    assert rec["refs"]["baseline_ids"], "Define opens with the company's baseline"
    lines = [json.loads(x) for x in (data / "ardmore" / "intents" / iid / "events.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert {("stage_closed", "think_unfiltered"), ("stage_opened", "define_strategically")} <= {(e["kind"], (e.get("detail") or {}).get("stage")) for e in lines}
    board = j.get(f"{M1}/{sid}/board").json()
    assert board["clusters"] and all(c["note_ids"] for c in board["clusters"])

    # step 6: a move to Must with no measure behind the group is refused in words
    cid = board["clusters"][0]["id"]
    r = j.post(f"/api/intents/{iid}/define/shelf", json={"cluster_id": cid, "shelf": "must"})
    assert r.status_code == 409 and r.json()["message"]

    # step 10 (dialog): the close dialog and the charter draft name the same open groups
    v = j.get(f"/api/intents/{iid}/define/session").json()
    names = v["open_items"]["open_groups"]
    assert len(names) == len(board["clusters"])
    r = j.post(f"{M1}/{sid}/charter", json={})
    assert r.status_code == 409 and all(n in r.json()["message"] for n in names)
    assert j.post(f"{M1}/{sid}/together/clusters/{cid}/tick", json={"ticked": True}).status_code == 200
    assert len(j.get(f"/api/intents/{iid}/define/session").json()["open_items"]["open_groups"]) == len(names) - 1
    r = j.post(f"{M1}/{sid}/charter", json={"confirm": True})
    assert r.status_code == 201, r.text
    r = j.post(f"/api/intents/{iid}/define/session", json={"action": "close"})
    assert r.status_code == 200, r.text

    # step 12: the build-ready check reads the start answer on line 7
    br = j.get(f"/api/intents/{iid}/build-ready").json()
    line7 = next(ln for ln in br["lines"] if ln["n"] == 7)
    assert line7["ok"] is True and line7["answer"] is True

    # step 10: the sponsor signs; steps 7, 9, 11: a process, the source owners and the build team (on the signed company baseline the owner
    # cells still save, so a source whose owner has no sign-in can be renamed and confirmed)
    j.put(f"/api/intents/{iid}/charter", json={"confirm_so_that": [p["id"] for p in (j.get(f"{M1}/{sid}/charter").json().get("charter") or {}).get("problems", [])]})
    c = d.get(f"/api/intents/{iid}/charter").json()
    c = c.get("charter") or c
    r = d.post(f"/api/intents/{iid}/charter/sign", json={"confirm_sponsor": True, "version": c.get("version"), "edited_at": c.get("edited_at")})
    assert r.status_code == 200, r.text
    m = j.get(f"/api/intents/{iid}/processes").json()
    pr = j.post(f"/api/intents/{iid}/processes", json={"version": m["version"], "name": "Produce the quarterly client report", "owner": "janet-shaw"}).json()
    m = j.get(f"/api/intents/{iid}/processes").json()
    assert j.post(f"/api/intents/{iid}/processes/{pr['process']['id']}/confirm", json={"version": m["version"]}).status_code == 200
    for s in j.get(f"/api/intents/{iid}/data-sources").json()["sources"]:
        r = j.put(f"/api/intents/{iid}/data-sources/{s['id']}", json={"cells": {"source_owner": "Janet Shaw"}})
        assert r.status_code == 200, r.text
        assert j.post(f"/api/intents/{iid}/data-sources/{s['id']}/confirm", json={}).status_code == 200
    for slot, pid in (("architect", "aaron-lyle"), ("developer", "katie-kingsley"), ("tester", "mei-ling-chong")):
        assert j.put(f"/api/intents/{iid}/roles", json={slot: pid}).status_code == 200
    br = j.post(f"/api/intents/{iid}/build-ready/check").json()
    assert br["verdict"] == "ready", br.get("stops")
    assert "aaron" not in next(ln for ln in br["lines"] if ln["n"] == 6)["slots"]["architect"]  # shown by name, not the profile id

    # step 13: hand to Build; room 0 receives the catalogue itself (R16)
    r = j.post(f"/api/intents/{iid}/handoff")
    assert r.status_code == 200, r.text
    h = r.json()["handoff"]
    assert h["catalogue"] and h["baseline_id"] == rec["refs"]["baseline_ids"][0] and h["processes"] and h["source_map"]


def test_the_sponsor_reads_the_shelves_without_a_seat(world):
    """Spec 50 step 6: Daniel reads Define's shelves though he never took a seat on the wall."""
    app, data, p = world
    import json
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in (data / "ardmore" / "intents").glob("ini-*/intent.json")]
    rec = next(r for r in rows if r["title"].startswith("F50 ") and r["refs"].get("wall_session_ids"))
    sid = rec["refs"]["wall_session_ids"][0]
    r = p[DANIEL].get(f"{M1}/{sid}/together")
    assert r.status_code == 200, r.text
    assert r.json()["clusters"] and r.json()["organiser"] is False

