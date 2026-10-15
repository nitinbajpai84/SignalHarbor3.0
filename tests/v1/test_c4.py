"""C4 The context library: the one-time import, upload, a duplicate by hash, a similar-name question, private by default (another
person can neither list, read, change nor delete it), share and unshare, only ticked items the viewer may see reach the agents'
context and the catalogue scan (even with a hidden id in the list), suggestions never ticked, delete."""
import base64
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.settings import Settings
from sh_platform.v1 import c4_library as L
from sh_platform.v1 import catalogue_scan
from sh_platform.v1 import i2_north as N
from sh_platform.v1 import i6_chat

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
ARJUN, LEELA = "arjun.mehta.neera@example.test", "leela.raman.neera@example.test"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
CSV = b"as_of,portfolio,market_value\n2026-08-31,Core,100\n"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("c4") / "data"
    shutil.copytree(ROOT / "data", data)
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    accounts = json.loads((data / "_control" / "accounts.json").read_text(encoding="utf-8"))
    rows = accounts if isinstance(accounts, list) else accounts.get("accounts", accounts)
    rows = rows.values() if isinstance(rows, dict) else rows
    ids = {r.get("display_name"): r.get("account_id") or r.get("id") for r in rows if r.get("company_id") == "neera"}
    yield app, PlaneStore(data).plane_for("neera"), ids
    mp.undo()


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def up(c, name, data, **kw):
    return c.post("/api/v1/library", json={"name": name, "data": base64.b64encode(data).decode(), **kw})


def test_library_upload_visibility_and_agents_read_only_ticked_items(world):
    app, plane, ids = world
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    a_v = Viewer("Arjun Mehta", frozenset({"company_admin"}), False, ids["Arjun Mehta"])
    l_v = Viewer("Leela Raman", frozenset({"analyst"}), False, ids["Leela Raman"])

    seeded = arjun.get("/api/v1/library").json()  # the one-time import: documents and landing folders, shared, "Seeded"
    names = {i["name"]: i for i in seeded}
    assert "13-access-policy.md" in names and "custodian positions" in names
    assert all(i["visibility"] == "company" and i["uploaded_by"] == "Seeded" for i in seeded)
    assert len(L._index(plane)) == len(seeded)  # a second read imports nothing twice

    got = up(arjun, "performance-2026-08.csv", CSV, note="performance reporting file").json()["item"]
    assert got["visibility"] == "private" and got["kind"] == "sample" and got["mine"]
    assert up(arjun, "copy.csv", CSV).json()["duplicate"]["id"] == got["id"]  # same bytes: nothing stored
    assert "similar" in up(arjun, "Performance 2025 07.csv", CSV + b"2026-07-31,Core,90\n").json()
    assert up(arjun, "index-levels.md", b"Index levels by month", note="external file").json()["item"]["kind"] == "external"

    assert got["id"] not in {i["id"] for i in leela.get("/api/v1/library").json()}  # private by default
    assert leela.put(f"/api/v1/library/{got['id']}", json={"visibility": "company"}).status_code == 404
    assert leela.delete(f"/api/v1/library/{got['id']}").status_code == 404
    assert "item" in up(leela, "x.csv", CSV).json()  # Arjun's private copy is no duplicate for Leela: nothing leaks

    assert arjun.put(f"/api/v1/library/{got['id']}", json={"visibility": "company"}).json()["visibility"] == "company"
    assert got["id"] in {i["id"] for i in leela.get("/api/v1/library").json()}
    arjun.put(f"/api/v1/library/{got['id']}", json={"visibility": "private"})
    assert got["id"] not in {i["id"] for i in leela.get("/api/v1/library").json()}

    iid = i6_chat.create(plane, a_v, "Monthly performance for the custodian positions")
    sugg = arjun.get(f"/api/v1/intents/{iid}/context/suggestions").json()
    assert "custodian positions" in {i["name"] for i in sugg} and arjun.get(f"/api/v1/intents/{iid}/context").json()["library_ids"] == []
    access, positions = names["13-access-policy.md"]["id"], names["custodian positions"]["id"]
    ctx = arjun.put(f"/api/v1/intents/{iid}/context", json={"library_ids": [got["id"], access, positions]}).json()
    assert ctx["library_ids"] == [got["id"], access, positions]

    lines = " ".join(L.lines(plane, iid, a_v))
    assert "performance reporting file" in lines and "13-access-policy.md" in lines and "market_value" in lines
    assert "02-reporting-policy.md" not in lines  # not ticked: never read
    seen = " ".join(L.lines(plane, iid, l_v))  # Arjun's private item is in the list, but Leela may not see it
    assert "performance reporting file" not in seen and "13-access-policy.md" in seen
    assert got["id"] not in leela.get(f"/api/v1/intents/{iid}/context").json()["library_ids"]
    leela.put(f"/api/v1/intents/{iid}/context", json={"library_ids": [access]})  # Leela's edit keeps Arjun's hidden tick
    assert L._ids(plane, iid) == [got["id"], access]
    assert N._company_page(plane, iid, l_v)["document_passages"] == L.lines(plane, iid, l_v)

    arjun.put(f"/api/v1/intents/{iid}/context", json={"library_ids": [access, positions]})
    read = {r["file"] for r in catalogue_scan.scan(plane, iid)["read"]}
    assert read == {"documents/13-access-policy.md", "landing/custodian_positions"}  # only ticked items reach the scan

    assert arjun.delete(f"/api/v1/library/{got['id']}").json() == {"deleted": got["id"]}
    assert not plane.path(*got["path"].split("/")).exists()
    assert leela.delete(f"/api/v1/library/{access}").status_code == 403  # a seeded item: only a company admin may remove it
    assert plane.path("documents", "13-access-policy.md").is_file()
