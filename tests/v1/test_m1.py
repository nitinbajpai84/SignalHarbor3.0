"""M1 The company map: nodes and edges from the demo company's records, a reopened intent of work supersedes, a KPI with no source shows a
stub that says why, a participant reads and comments, the note shows on the node; a participant may not mark a note seen."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
CREDS = SEED / "_control" / "seed_credentials.txt"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
IID = "m1-perf"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    if "m1_map" not in (ROOT / "sh_platform" / "graph" / "build.py").read_text(encoding="utf-8"):  # until the orchestrator adds the one line
        from sh_platform.v1 import i5_graph, m1_map
        orig = i5_graph.add_sow_nodes

        def both(g, plane, people=None):
            orig(g, plane, people)
            m1_map.add_company_map_nodes(g, plane, people)
        mp.setattr(i5_graph, "add_sow_nodes", both)
    data = tmp_path_factory.mktemp("m1") / "data"
    shutil.copytree(SEED, data)
    plane = PlaneStore(str(data)).plane_for("neera")

    def put(rel: str, obj) -> None:
        p = plane.path(*rel.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj), encoding="utf-8")

    sig = lambda v: {"name": "Arjun Mehta", "role": "company_admin", "at": f"2026-10-0{v}T09:00:00+00:00", "version": v}  # noqa: E731
    put(f"intents/{IID}/sow.json", {
        "id": f"sow-{IID}", "intent_id": IID, "title": "Monthly performance pack", "state": "draft", "version": 2,
        "goal": {"line": "Monthly performance pack", "why": "the committee decides on rebalancing", "readers": ["The investment committee"],
                 "decisions": ["rebalancing"], "needed_by": "the 8th working day"},
        "process": {"steps": [{"n": 1, "name": "Download custodian files", "who": "Kiran Iyer", "does": "downloads the positions", "inputs": [],
                               "outputs": ["positions"], "system": "Custodian positions"}], "handovers": []},
        "kpis": [{"code": "TWR", "name": "Time-weighted return", "definition": "Return net of flows", "formula": "", "unit": "%", "period": "monthly",
                  "owner": "Priya Nair", "source_ids": ["custodian"], "status": "defined", "pack_suggested": False},
                 {"code": "K01", "name": "Fee ratio", "definition": "Fees over assets", "formula": "", "unit": "%", "period": "monthly", "owner": "",
                  "source_ids": ["custodian"], "status": "defined", "pack_suggested": False},
                 {"code": "CD", "name": "Cash drag", "definition": "", "formula": "", "unit": "%", "period": "monthly", "owner": "",
                  "source_ids": [], "status": "unclear", "pack_suggested": False}],
        "sources": [{"id": "custodian", "name": "Custodian positions", "kind": "file", "holds": "positions", "sample_path": "landing/custodian/positions.csv",
                     "owner": "Kiran Iyer", "fields": [{"name": "market_value", "type": "number", "example": "100", "meaning": "value at month end"}]},
                    {"id": "ips", "name": "Investment policy statement", "kind": "document", "holds": "policy", "sample_path": "documents/ips.md", "owner": "",
                     "fields": [], "read": {"by": "North read it", "definitions": [{"term": "Time-weighted return", "file": "ips.md", "quote": "TWR is net of fees"}],
                                            "owners": [], "systems": [], "rules": []}}],
        "catalogue": [{"table": "gold_twr", "layer": "gold", "meaning": "TWR per month", "source_id": "custodian", "fields": [], "feeds_kpis": ["TWR"]}],
        "governance": [{"rule": "Only the committee sees returns", "kind": "access", "applies_to": ["TWR"], "stated_by": "Priya Nair"}],
        "unclear": [{"id": "u1", "question": "Gross or net of fees?", "about": "TWR", "who_can_settle": "Priya Nair", "settled": True, "answer": "Net"}],
        "signature": None, "signatures": [sig(1), sig(2)]})
    # a second intent whose K01 means something else (the seed has no intents of its own; the old live data happened to hold one)
    put("intents/m1-cash/sow.json", {"id": "sow-m1-cash", "intent_id": "m1-cash", "title": "Cash watch", "state": "draft", "version": 1,
                                     "goal": {"line": "Cash watch"}, "kpis": [{"code": "K01", "name": "Idle cash", "definition": "Cash above the buffer"}]})
    put(f"intents/{IID}/thread.json", {"intent_id": IID, "turns": [{"id": "t1", "by": "person", "name": "Arjun Mehta", "text": "Monthly pack",
                                                                     "at": "2026-10-01T09:00:00+00:00"}], "needs_done": [], "state": "sow_ready"})
    put(f"build/scan/{IID}.json", {"intent_id": IID, "kpis": [{"code": "CD", "status": "not", "sources_used": [],
                                                               "missing": [{"what": "daily cash balances", "where_expected": "bank file"}]}], "agreed": None})
    put(f"build/blueprint_conversation/{IID}.json", {"intent_id": IID, "turns": [], "state": "approved", "approved_by": "Leela Raman",
                                                     "approved_at": "2026-10-03T09:00:00+00:00"})
    put(f"consume/brief/{IID}.json", {"views": [{"name": "Committee page", "audience": "The investment committee", "kpis": ["TWR"],
                                                 "comparisons": [], "filters": [], "refresh": "monthly"}], "feeds_wanted": [], "levers": [],
                                      "existing_dashboards": [], "end_user_inputs": [], "notes": []})
    (plane.path("graph", "dirty")).parent.mkdir(parents=True, exist_ok=True)
    plane.path("graph", "dirty").write_text("1", encoding="utf-8")
    yield create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    mp.undo()


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_map_from_records(app):
    r = client(app, "arjun.mehta.neera@example.test").get("/api/v1/map")
    assert r.status_code == 200, r.text
    nodes = {n["id"]: n for n in r.json()["nodes"]}
    edges = {(e["from"], e["to"], e["type"]) for e in r.json()["edges"]}
    it, twr = nodes[f"intent:{IID}"], nodes["measure:TWR"]
    assert it["state"] == "designed" and it["from_record"] == f"intents/{IID}/sow.json"
    assert twr["definition"] == "Return net of flows" and IID in twr["intents"]
    assert ("source:custodian", twr["id"], "feeds") in edges and ("table:gold_twr", twr["id"], "feeds") in edges
    assert nodes["source:ips"]["type"] == "Document" and (twr["id"], "source:ips", "defined_in") in edges
    assert ("person:arjun-mehta", it["id"], "asked_for") in edges and (twr["id"], "view:m1-perf:committee-page", "shown_in") in edges
    assert (f"signed:{IID}:sow:v2", f"signed:{IID}:sow:v1", "supersedes") in edges  # a reopened intent of work: version 2 supersedes 1
    assert (f"signed:{IID}:design", "person:leela-raman", "signed_by") in edges
    gap = nodes[f"gap:{IID}:CD"]  # no source: a stub that says why, never a guess
    assert gap["stub"] and "daily cash balances" in gap["what"] and ("measure:CD", gap["id"], "derived_from") in edges
    assert nodes[f"measure:{IID}:K01"]["label"] == "Fee ratio" and "measure:K01" not in nodes  # K01 means two things in two intents: one node each
    assert any(n["type"] == "Decision" and n.get("answer") == "Net" for n in nodes.values())
    found = client(app, "arjun.mehta.neera@example.test").get("/api/v1/map/ask", params={"q": "Where does time-weighted return come from?"}).json()
    assert found["nodes"][0]["id"] == twr["id"]


def test_participant_reads_and_comments(app):
    dev = client(app, "dev.sharma.neera@example.test")  # participant: consumer seat only
    node = "measure:TWR"
    assert dev.get("/api/v1/map").status_code == 200
    r = dev.post(f"/api/v1/map/node/{node}/comments", json={"text": "This should be net of fees"})
    assert r.status_code == 200, r.text
    on = next(n for n in dev.get("/api/v1/map").json()["nodes"] if n["id"] == node)
    assert on["notes"][0]["by"] == "Dev Sharma" and on["notes"][0]["state"] == "open"
    cid = client(app, "arjun.mehta.neera@example.test").get("/api/v1/map/comments").json()["comments"][0]["id"]
    refused = dev.post(f"/api/v1/map/comments/{cid}/seen")
    assert refused.status_code == 403 and refused.json().get("error") != "csrf"  # refusal: only the decision maker marks a note seen
    assert dev.post("/api/v1/map/node/nobody:here/comments", json={"text": "x"}).status_code == 404
    assert client(app, "arjun.mehta.neera@example.test").post(f"/api/v1/map/comments/{cid}/seen").json()["state"] == "seen"
    assert client(app, "nitin.fresh@example.test").get("/api/v1/map").json()["nodes"] == []  # an empty company: an empty map, never a 500
