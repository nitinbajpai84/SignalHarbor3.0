"""Fixtures for the company context tests: a plane in a temporary folder, and the real app over the seeded synthetic
companies (a copy per test). Nothing here touches the repo tree or the network."""
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ctx_const import FAMILY
from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import load_settings

ROOT = Path(__file__).resolve().parents[2]
FAKE_SECRET = "FAKE-context-secret-0123456789-abcdefghijklmnop"  # fake, clearly marked


from ctx_seed import seed  # noqa: E402  (one copy of tools/seed.py, shared with the tests)


@pytest.fixture
def planes(tmp_path):
    (tmp_path / "planes").mkdir()
    return PlaneStore(tmp_path / "planes")


@pytest.fixture
def plane(planes):
    return planes.create("lakeside-family-office")


@pytest.fixture
def other_plane(planes):
    return planes.create("harbor-mutual")


@pytest.fixture(scope="session")
def seeded(tmp_path_factory):
    root = tmp_path_factory.mktemp("ctx_seeded") / "data"
    result = seed.seed(root)
    passwords = {}
    for line in result["path"].read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            email, password = line.split()[:2]
            passwords[email] = password
    return root, passwords


class Env:
    def __init__(self, app, passwords):
        self.app, self._passwords = app, passwords

    def login(self, role: str, company: str = FAMILY) -> TestClient:
        email = f"{role}.{company}@example.test"
        c = TestClient(self.app)
        r = c.post("/api/auth/login", json={"email": email, "password": self._passwords[email]})
        assert r.status_code == 200, f"sign-in failed for {role}"
        return c


@pytest.fixture
def env(seeded, tmp_path):
    """The app over the seeded companies, with the seeded demo documents taken out so a test starts from an empty list."""
    root, passwords = seeded
    data = tmp_path / "data"
    shutil.copytree(root, data)
    shutil.rmtree(PlaneStore(data).plane_for(FAMILY).path("context", "agent_docs"))
    return _env(data, passwords, tmp_path)


@pytest.fixture
def demo_env(seeded, tmp_path):
    """The app over the seeded companies exactly as `tools/seed.py` leaves them, demo documents included."""
    root, passwords = seeded
    data = tmp_path / "data"
    shutil.copytree(root, data)
    return _env(data, passwords, tmp_path)


def _env(data, passwords, tmp_path):
    settings = load_settings({"SH_MODE": "dev", "SH_DATA_ROOT": str(data), "SH_SESSION_SECRET": FAKE_SECRET},
                             env_file=tmp_path / "none.env")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>CTX-UI</title>", encoding="utf-8")
    return Env(create_app(settings, dist_dir=dist), passwords)
