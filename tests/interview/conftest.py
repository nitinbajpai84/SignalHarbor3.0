"""Fixtures for the interview tests: a plane in a temporary folder with a small synthetic profile, a stub model, and the real app over the
seeded synthetic companies (a copy per test). Nothing here touches the repo tree or the network."""
import importlib.util
import shutil
import sys

import pytest
from fastapi.testclient import TestClient

from iv_kit import FAMILY, OTHER, ROOT, StubModel, seed
from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import load_settings

FAKE_SECRET = "FAKE-interview-secret-0123456789-abcdefghijk"  # fake, clearly marked


def _seed_tool():
    spec = importlib.util.spec_from_file_location("iv_tool_seed", ROOT / "tools" / "seed.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def planes(tmp_path):
    (tmp_path / "planes").mkdir()
    return PlaneStore(tmp_path / "planes")


@pytest.fixture
def plane(planes):
    p = planes.create(FAMILY)
    seed(p)
    return p


@pytest.fixture(scope="session")
def seeded(tmp_path_factory):
    root = tmp_path_factory.mktemp("iv_seeded") / "data"
    result = _seed_tool().seed(root)
    passwords = {}
    for line in result["path"].read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            email, password = line.split()[:2]
            passwords[email] = password
    return root, passwords


class Env:
    def __init__(self, app, passwords):
        self.app, self._passwords, self.stub = app, passwords, StubModel()
        app.state.interview_model_factory = lambda plane: self.stub

    def login(self, role: str, company: str = FAMILY) -> TestClient:
        email = f"{role}.{company}@example.test"
        c = TestClient(self.app)
        r = c.post("/api/auth/login", json={"email": email, "password": self._passwords[email]})
        assert r.status_code == 200, f"sign-in failed for {role}"
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
        return c

    def guest(self) -> TestClient:
        return TestClient(self.app)

    def plane(self, company: str = FAMILY):
        return PlaneStore(self.app.state.settings.data_root).plane_for(company).ensure()


@pytest.fixture
def env(seeded, tmp_path):
    root, passwords = seeded
    data = tmp_path / "data"
    shutil.copytree(root, data)
    settings = load_settings({"SH_MODE": "dev", "SH_DATA_ROOT": str(data), "SH_SESSION_SECRET": FAKE_SECRET}, env_file=tmp_path / "none.env")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>IV-UI</title>", encoding="utf-8")
    e = Env(create_app(settings, dist_dir=dist), passwords)
    seed(e.plane())
    return e
