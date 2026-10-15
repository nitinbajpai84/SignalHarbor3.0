"""Smoke fixtures: the real app, in process, over the seeded synthetic companies, in temporary folders.

Never reads a developer's .env or data folder. No password is ever printed or put in an assertion message.
"""
import shutil
import socket
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.auth.permissions import Rule
from sh_platform.auth.sessions import IDLE_SECONDS, SessionManager
from sh_platform.entitlements import EntitlementStore
from sh_platform.packs import PackLoader
from sh_platform.plane import PlaneStore
from sh_platform.settings import load_settings

from smoke_helpers import (CASES, FAKE_SECRET, GROUP_OF_FILE, GROUPS, NOT_TIED, ROOT, render, seed,
                           snapshot, tally)


# ---------------------------------------------------------------- guards
@pytest.fixture(scope="session", autouse=True)
def repo_tree_untouched():
    before = snapshot(ROOT)
    yield
    assert snapshot(ROOT) == before, "the smoke run changed files in the repo tree"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any connection beyond this machine fails the test. (Loopback stays open: the event loop on Windows
    builds its wake-up socket pair that way.)"""
    local = {"127.0.0.1", "::1", "localhost"}
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex
    real_create, real_lookup = socket.create_connection, socket.getaddrinfo

    def guard(real):
        def inner(first, *a, **k):
            target = a[0] if a and isinstance(first, socket.socket) else first
            if not (isinstance(target, tuple) and target[0] in local):
                raise AssertionError("real network use in a test")
            return real(first, *a, **k)
        return inner

    monkeypatch.setattr(socket.socket, "connect", guard(real_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guard(real_connect_ex))
    monkeypatch.setattr(socket, "create_connection", guard(real_create))

    def lookup(host, *a, **k):
        if host not in local:
            raise AssertionError("real network use in a test")
        return real_lookup(host, *a, **k)
    monkeypatch.setattr(socket, "getaddrinfo", lookup)


# ---------------------------------------------------------------- seeded data
@pytest.fixture(scope="session")
def seeded(tmp_path_factory):
    root = tmp_path_factory.mktemp("seeded") / "data"
    result = seed.seed(root)
    passwords = {}
    for line in result["path"].read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            email, password = line.split()[:2]
            passwords[email] = password
    return root, passwords


class FakeClock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now

    def advance(self, seconds: float):
        self.now += seconds


@dataclass
class Env:
    app: object
    root: Path
    settings: object
    clock: FakeClock
    _passwords: dict = field(repr=False)

    @property
    def entitlements(self) -> EntitlementStore:
        return self.app.state.entitlements

    @property
    def planes(self) -> PlaneStore:
        return PlaneStore(self.root)

    def login(self, email: str) -> TestClient:
        c = TestClient(self.app)
        r = c.post("/api/auth/login", json={"email": email, "password": self._passwords[email]})
        assert r.status_code == 200, f"sign-in failed for {email}"
        return c

    def add_route(self, kind: str, path: str, handler, rule: Rule | None = None) -> None:
        """Register a test route AHEAD of the UI mount (the mount is last and would swallow it), and
        declare it in the real permission table when `rule` is given (otherwise it is left undeclared)."""
        getattr(self.app, kind)(path)(handler)
        routes = self.app.router.routes
        new = routes.pop()
        routes.insert(next(i for i, r in enumerate(routes) if type(r).__name__ == "Mount"), new)
        if rule is not None:
            self.declare(f"{'WEBSOCKET' if kind == 'websocket' else kind.upper()} {path}", rule)

    def declare(self, key: str, rule: Rule) -> None:
        """Declare a test route in the real permission table (an undeclared route is refused)."""
        for mw in self.app.user_middleware:
            perms = mw.kwargs.get("perms")
            if perms is not None:
                perms.routes[key] = rule
                return
        raise AssertionError("auth middleware not found")


@pytest.fixture
def env(seeded, tmp_path):
    root, passwords = seeded
    data = tmp_path / "data"
    shutil.copytree(root, data)  # each test mutates its own copy
    settings = load_settings({"SH_MODE": "dev", "SH_DATA_ROOT": str(data), "SH_SESSION_SECRET": FAKE_SECRET},
                             env_file=tmp_path / "none.env")
    dist = tmp_path / "dist"  # a stand-in for the built UI, so the run never depends on ui/dist
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>SMOKE-UI</title>", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("OUTSIDE-DIST-MARKER", encoding="utf-8")
    app = create_app(settings, dist_dir=dist)
    clock = FakeClock()
    app.state.sessions = SessionManager(FAKE_SECRET, IDLE_SECONDS, 8 * 60 * 60, clock)  # fake clock, same rules
    return Env(app, data, settings, clock, passwords)


@pytest.fixture(scope="session")
def packs() -> PackLoader:
    return PackLoader(ROOT / "packs")


@pytest.fixture(params=list(CASES.values()), ids=[c["id"] for c in CASES.values()])
def case(request):
    return request.param


# ---------------------------------------------------------------- real counts per company and per group
def pytest_terminal_summary(terminalreporter):
    results = []
    for outcome in ("passed", "failed", "error", "skipped"):
        for rep in terminalreporter.stats.get(outcome, []):
            nodeid = getattr(rep, "nodeid", "").replace("\\", "/")
            if "tests/smoke/" in nodeid and (outcome != "passed" or rep.when == "call"):
                results.append((nodeid, outcome))
    if not results:
        return
    by_company, by_group = tally(results)
    terminalreporter.section("smoke counts")
    terminalreporter.write_line("smoke by company: " + render(by_company, [c["id"] for c in CASES.values()] + [NOT_TIED]))
    terminalreporter.write_line("smoke by group: " + render(by_group, list(GROUPS) + list(GROUP_OF_FILE.values())))
