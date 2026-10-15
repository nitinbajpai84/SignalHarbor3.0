"""GET /api/company/graph: the viewer's gated graph over HTTP. Synthetic data; the graph document is written by path."""
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import load_settings

ROOT = Path(__file__).resolve().parents[2]
FAMILY, MUTUAL = "lakeside-family-office", "harbor-mutual"


def n(i, t, label, **kw):
    return {"id": i, "type": t, "label": label, "provenance": [], **kw}


def e(a, b, t):
    return {"from": a, "to": b, "type": t, "provenance": []}


DOC = {"version": 1, "built_at": "2026-10-06T00:00:00+00:00",
       "nodes": [n("m1", "Measure", "Single-issuer concentration"), n("m2", "Measure", "Loose measure"), n("s1", "Source", "Custody feed"),
                 n("p1", "Person", "Dan Data"), n("m3", "Measure", "Secret measure", restricted_to=["priya nair"]),
                 n("problem:c1", "Problem", "Late capital-call notices")],
       "edges": [e("m1", "s1", "fed_by"), e("s1", "p1", "owned_by"), e("m3", "s1", "fed_by"), e("problem:c1", "m1", "measured_by"),
                 e("problem:c1", "m3", "measured_by")]}
NOW = datetime.now(timezone.utc).isoformat()
WALL, DRAFT, CHARTER = "a" * 32, "b" * 32, "c" * 32


@pytest.fixture
def login(tmp_path_factory, tmp_path):
    root = tmp_path_factory.mktemp("cg_seeded") / "data"
    spec = importlib.util.spec_from_file_location("cg_tool_seed", ROOT / "tools" / "seed.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    result = mod.seed(root)
    pw = {l.split()[0]: l.split()[1] for l in result["path"].read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}
    shutil.copytree(root, tmp_path / "data")
    plane = PlaneStore(tmp_path / "data").plane_for(FAMILY)
    plane.path("graph", "company.json").write_text(json.dumps(DOC), encoding="utf-8")
    plane.path("graph", "versions.json").write_text(json.dumps({"m2": [{"v": 1, "what": "new", "by": "the record", "at": NOW, "ref": ""}],
                                                                 "m3": [{"v": 1, "what": "new", "by": "the record", "at": NOW, "ref": ""}],
                                                                 "m1": [{"v": 1, "what": "new", "by": "the record", "at": "2020-01-01T00:00:00+00:00", "ref": ""},
                                                                        {"v": 2, "what": "Links changed", "by": "the record", "at": NOW, "ref": ""}]}), encoding="utf-8")
    sessions = plane.path("intents", "m1_intent", "sessions")
    sessions.mkdir(parents=True, exist_ok=True)
    (sessions / f"{WALL}.json").write_text(json.dumps({"id": WALL, "state": "closed", "preparation": {"topic": "Treasury", "purpose": "Why notices run late"}}), encoding="utf-8")
    (sessions / f"{DRAFT}.json").write_text(json.dumps({"id": DRAFT, "state": "draft", "preparation": {"topic": "Not held yet"}}), encoding="utf-8")
    outcomes = plane.path("intents", "m1_intent", "outcomes")
    outcomes.mkdir(parents=True, exist_ok=True)
    (outcomes / f"{CHARTER}.json").write_text(json.dumps({"outcome_id": CHARTER, "session_id": WALL, "kind": "charter", "signed_at": NOW, "problems": [{"id": "c1", "title": "Late"}]}),
                                             encoding="utf-8")
    settings = load_settings({"SH_MODE": "dev", "SH_DATA_ROOT": str(tmp_path / "data"), "SH_SESSION_SECRET": "FAKE-graph-secret-0123456789-abcdefghij"}, env_file=tmp_path / "none.env")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<!doctype html>", encoding="utf-8")
    app = create_app(settings, dist_dir=tmp_path / "dist")

    def go(role: str, company: str = FAMILY) -> TestClient:
        email = f"{role}.{company}@example.test"
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        return c
    go.plane = plane
    return go


def test_the_admin_sees_the_whole_map_and_an_outsider_sees_a_silhouette(login):
    admin = login("analyst").get("/api/company/graph").json()
    assert {x["label"] for x in admin["nodes"]} >= {"Secret measure", "Custody feed"}
    out = login("sponsor").get("/api/company/graph?view=map").json()
    assert "Secret measure" not in json.dumps(out) and any(x.get("restricted") and x["id"].startswith("restricted-") for x in out["nodes"])


def test_a_trace_runs_from_the_measure_to_its_owner(login):
    r = login("company_admin").get("/api/company/graph?view=trace&focus=m1").json()
    assert {x["id"] for x in r["nodes"]} == {"m1", "s1", "p1"} and len(r["edges"]) == 2


def test_holes_list_measures_with_no_source(login):
    r = login("sponsor").get("/api/company/graph?view=holes").json()
    assert [h["label"] for h in r["holes"]] == ["Loose measure"]


def test_another_company_cannot_trace_this_one_and_bad_input_is_refused(login):
    other = login("company_admin", MUTUAL)
    assert other.get("/api/company/graph?view=trace&focus=m1").status_code == 404
    assert other.get("/api/company/graph").json()["nodes"] == []
    assert login("company_admin").get("/api/company/graph?view=nope").status_code == 400
    assert login("participant").get("/api/company/graph").status_code == 200  # A-070: the map is open to everyone in the company


def test_the_map_serves_five_columns_and_what_each_wall_produced(login):
    r = login("participant").get("/api/company/graph").json()
    assert r["columns"]["walls"] == [{"id": f"wall:{WALL}", "label": "Treasury"}]  # a draft wall is not on the map
    assert r["columns"]["problems"] == ["problem:c1"] and set(r["columns"]["systems"]) == {"s1"}
    restricted = next(x["id"] for x in r["nodes"] if x.get("restricted"))
    assert set(r["columns"]["measures"]) == {"m1", "m2", restricted}
    assert r["by_wall"] == [{"wall": f"wall:{WALL}", "problems": ["problem:c1"], "measures": sorted(["m1", restricted])}]
    assert r["holes"] == ["m2"] and r["new_this_week"] == ["m1", "m2"] and sorted(r["new_detail"]) == ["m1", "m2"]  # m1 has old history but changed again; m3 is new too, but hidden from this viewer: never named, not even by id
    assert "Secret measure" not in json.dumps(r)


def test_the_summary_counts_things_and_links_and_the_gate_is_unchanged(login):
    r = login("company_admin").get("/api/company/graph").json()
    assert r["summary"] == {"things": 7, "links": 6, "walls": 1, "charters": 1, "baselines": 0}
    assert r["new_this_week"] == ["m1", "m2"]  # the admin is not on m3's list either (A-069)
    assert "summary" not in login("company_admin").get("/api/company/graph?view=holes").json()
    assert login("participant").get("/api/company/graph").status_code == 200
    assert login("company_admin", MUTUAL).get("/api/company/graph").json()["by_wall"] == []


def test_a_wall_without_a_signed_charter_is_named_only_to_its_organiser_and_seat_holders(login):
    SECRET = "d" * 32
    login.plane.path("intents", "m1_intent", "sessions", f"{SECRET}.json").write_text(json.dumps(
        {"id": SECRET, "state": "private_rooms", "organiser_account_id": "someone-else", "preparation": {"topic": "Pay review", "purpose": "Who is paid what"}}), encoding="utf-8")
    walls = login("participant").get("/api/company/graph").json()["columns"]["walls"]
    assert {"id": f"wall:{SECRET}", "label": "A wall"} in walls and "Pay review" not in json.dumps(walls) and "Who is paid" not in json.dumps(walls)
    assert {"id": f"wall:{WALL}", "label": "Treasury"} in walls  # a signed charter makes its wall public to the company
