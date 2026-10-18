"""L3b: the project-free library file viewer: numbered lines for a file the viewer may see; refusals for another person's private file."""
import base64
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.settings import Settings
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
CREDS = SEED / "_control" / "seed_credentials.txt"
ARJUN, LEELA = "arjun.mehta.neera@example.test", "leela.raman.neera@example.test"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    data = tmp_path_factory.mktemp("l3b") / "data"
    shutil.copytree(SEED, data)
    a = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    a.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    return a


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_view_numbered_lines_and_refusals(app):
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    body = base64.b64encode(b"First line\nSecond line\n").decode()
    item = arjun.post("/api/v1/library", json={"name": "private-notes.md", "data": body}).json()["item"]
    assert item["visibility"] == "private"
    got = arjun.get("/api/v1/library/view", params={"file": item["path"]})
    assert got.status_code == 200 and got.json()["lines"][:2] == [{"n": 1, "text": "First line"}, {"n": 2, "text": "Second line"}]
    assert leela.get("/api/v1/library/view", params={"file": item["path"]}).status_code == 404  # another person's private file
    assert arjun.get("/api/v1/library/view", params={"file": "../../etc/passwd"}).status_code == 404  # not a library path
    assert arjun.get("/api/v1/library/view").status_code == 404
    arjun.put(f"/api/v1/library/{item['id']}", json={"visibility": "company"})
    assert leela.get("/api/v1/library/view", params={"file": item["path"]}).json()["name"] == "private-notes.md"
    arjun.delete(f"/api/v1/library/{item['id']}")
    assert arjun.get("/api/v1/library/view", params={"file": item["path"]}).status_code == 404
    assert TestClient(app).get("/api/v1/library/view", params={"file": item["path"]}).status_code in (401, 403)
