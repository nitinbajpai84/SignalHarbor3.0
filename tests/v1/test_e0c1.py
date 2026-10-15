"""E0c1: originals kept untouched, duplicates by hash, inbox scan (idempotent), census states, profile/load via stubs, routes and seats."""
import shutil
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings
from sh_platform.v1 import e0c_landing as L
from sh_platform.v1 import wh

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
CSV = b"fund,nav\nA,10\n"


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    return PlaneStore(tmp_path / "data").create("acme")


@pytest.fixture()
def stubs(monkeypatch):
    tools = types.ModuleType("sh_platform.v1.e0b_tools")
    tools.profile_sheet = lambda path, sheet=None: {"sheet": sheet or "S1", "header_row": 1, "columns": ["fund", "nav"], "path_seen": Path(path).name}
    load = types.ModuleType("sh_platform.v1.e0c_load")
    load.result = {"status": "loaded", "rows": 1}
    load.load = lambda plane, file_id, viewer: load.result
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e0b_tools", tools)
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e0c_load", load)
    import sh_platform.v1 as pkg  # "from sh_platform.v1 import x" prefers the package attribute, which a real import elsewhere may have set
    monkeypatch.setattr(pkg, "e0b_tools", tools, raising=False)
    monkeypatch.setattr(pkg, "e0c_load", load, raising=False)
    return load


def test_original_is_kept_untouched_with_a_record(plane):
    r = L.receive(plane, CSV, "..\\evil/Pos 1.csv", "Mei", "manager_email")
    assert not r["duplicate"] and r["state"] == "new" and r["name"] == "Pos 1.csv" and r["owner"] == "Mei" and r["source_code"] == "manager_email"
    assert L.original_path(plane, r).read_bytes() == CSV and L.original_path(plane, r).name == f"{r['sha256']}__Pos 1.csv"
    assert L.get(plane, r["file_id"])["sha256"] == r["sha256"] and r["received_at"] and r["sensitivity"]


def test_duplicate_by_hash_is_recognised(plane):
    a = L.receive(plane, CSV, "a.csv", "Mei")
    b = L.receive(plane, CSV, "renamed.csv", "Raj")
    assert b["duplicate"] and b["file_id"] == a["file_id"] and len(L.listing(plane)["files"]) == 1
    assert not L.receive(plane, CSV + b"B,2\n", "a.csv", "Mei")["duplicate"]


def test_inbox_scan_registers_once_and_uses_folder_as_source(plane):
    inbox = plane.path("landing", "inbox")
    (inbox / "admin").mkdir(parents=True, exist_ok=True)
    (inbox / "admin" / "nav.csv").write_bytes(CSV)
    (inbox / "loose.csv").write_bytes(b"x,y\n1,2\n")
    (inbox / "~$lock.xlsx").write_bytes(b"junk")
    assert {r["source_code"] for r in L.scan_inbox(plane)} == {"admin", "inbox"}
    assert L.scan_inbox(plane) == [] and len(L.listing(plane)["files"]) == 2
    assert (inbox / "admin" / "nav.csv").read_bytes() == CSV  # inbox left alone
    assert set(L.listing(plane)["by_source"]) == {"admin", "inbox"}


def test_states(plane, stubs):
    r = L.receive(plane, CSV, "a.csv", "Mei")
    p = L.profile(plane, r["file_id"])
    assert p["state"] == "profiled" and p["profile"]["path_seen"].endswith("a.csv")
    assert "profile" not in L.listing(plane)["files"][0]
    for status, state in [("waiting_for_mapping", "waiting_for_mapping"), ("rejected_totals", "rejected_totals"), ("loaded", "loaded")]:
        stubs.result = {"status": status}
        out = L.load(plane, r["file_id"], None)
        assert out["state"] == state and out["last_load"] == {"status": status} and out["last_load_at"]
    assert L.profile(plane, r["file_id"])["state"] == "loaded"  # re-profiling does not undo a load
    q = L.receive(plane, b"%PDF", "scan.pdf", "Mei")
    assert q["state"] == "quarantined"
    with pytest.raises(L.Refused):
        L.load(plane, q["file_id"], None)


def test_unreadable_file_is_quarantined(plane, stubs, monkeypatch):
    def boom(path, sheet=None):
        raise ValueError("bad zip")
    sys.modules["sh_platform.v1.e0b_tools"].profile_sheet = boom
    r = L.receive(plane, b"not really excel", "a.xlsx", "Mei")
    with pytest.raises(L.Refused):
        L.profile(plane, r["file_id"])
    assert L.get(plane, r["file_id"])["state"] == "quarantined" and L.original_path(plane, r).exists()


def test_bad_ids_and_empty_files_refused(plane):
    for bad in ("../x", "nope"):
        with pytest.raises(L.Refused) as e:
            L.get(plane, bad)
        assert e.value.status == 404
    with pytest.raises(L.Refused):
        L.receive(plane, b"", "a.csv", "Mei")


@pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
def test_routes_upload_scan_and_seats(tmp_path, monkeypatch, stubs):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data" / "_control", data / "_control")
    shutil.copytree(ROOT / "data" / "neera", data / "neera")
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}

    def client(email):
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
        return c

    leela, priya = client("leela.raman.neera@example.test"), client("priya.nair.neera@example.test")
    up = leela.post("/api/v1/intake/upload", files={"file": ("nav.csv", CSV, "text/csv")}, data={"source_code": "admin"})
    assert up.status_code == 200, up.text
    rec = up.json()
    assert rec["state"] == "new" and rec["source_code"] == "admin" and rec["duplicate"] is False
    assert leela.post("/api/v1/intake/upload", files={"file": ("again.csv", CSV, "text/csv")}).json()["duplicate"] is True
    assert leela.post(f"/api/v1/intake/files/{rec['file_id']}/profile").json()["state"] == "profiled"
    assert leela.post(f"/api/v1/intake/files/{rec['file_id']}/load").json()["state"] == "loaded"
    d = leela.get(f"/api/v1/intake/files/{rec['file_id']}").json()  # the shape the file page reads
    assert d["id"] == rec["file_id"] and [c["name"] for c in d["profile"]["columns"]] == ["fund", "nav"]
    assert d["can_act"] is True and d["mapping"] is None and d["control_totals"] == [] and d["load_result"]["state"] == "loaded"
    assert priya.get(f"/api/v1/intake/files/{rec['file_id']}").json()["can_act"] is False
    assert all(f["id"] == f["file_id"] for f in leela.get("/api/v1/intake/files").json()["files"])
    got = priya.get("/api/v1/intake/files").json()
    assert any(f["file_id"] == rec["file_id"] for f in got["by_source"]["admin"])
    assert priya.post("/api/v1/intake/upload", files={"file": ("x.csv", b"q\n1\n", "text/csv")}).status_code == 403
    assert priya.post(f"/api/v1/intake/files/{rec['file_id']}/load").status_code == 403
    L.stop_polls()


def test_quarantined_and_repeat_loads_move_the_state(plane, stubs):
    r = L.receive(plane, CSV, "a.csv", "Mei")
    L.profile(plane, r["file_id"])
    stubs.result = {"status": "quarantined", "message": "no"}
    assert L.load(plane, r["file_id"], None)["state"] == "quarantined"
    r2 = L.receive(plane, CSV + b"B,2" + bytes([10]), "b.csv", "Mei")
    L.profile(plane, r2["file_id"])
    stubs.result = {"status": "already_loaded", "message": "again"}
    assert L.load(plane, r2["file_id"], None)["state"] == "loaded"
