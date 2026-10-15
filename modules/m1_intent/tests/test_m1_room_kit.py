"""Helpers for the M1-P02 room tests (no tests here). The real app over temporary folders, seeded companies from
m1_kit.World. NOTE: World switches module 1 on for every company it makes, including the empty one, because a new
company owns no modules by default; the tests that need it off switch it off themselves.
Every token, code and password here is made at run time or a fake string, never a real secret."""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from m1_kit import BASE, draft

CODE_PATH = re.compile(r"^/join/([A-Za-z0-9_-]{22})$")
TOKEN = re.compile(r"^[0-9a-f]{32}\.[A-Za-z0-9_-]{43}$")
ORGANISER_ROUTES = [
    ("post", "/sessions/{sid}/start"), ("post", "/sessions/{sid}/link"), ("post", "/sessions/{sid}/seats/1/revoke"),
    ("post", "/sessions/{sid}/briefing"),
]
BOTH_ROUTES = [("get", "/sessions/{sid}/lobby"), ("get", "/sessions/{sid}/live")]


def new_session(c, seats=3, **over) -> str:
    r = c.post(f"{BASE}/sessions", json=draft(seats=seats, **over))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def start_room(c, sid: str) -> str:
    """Starts the room; returns the join code taken from the link the organiser is shown."""
    r = c.post(f"{BASE}/sessions/{sid}/start")
    assert r.status_code == 201, r.text
    m = CODE_PATH.match(r.json()["join_path"])
    assert m, "the link is /join/<code>"
    return m.group(1)


def guest(world) -> TestClient:
    """A browser with no account and no cookie."""
    return TestClient(world.app)


def join(c, code: str, seat: int | None = None, name=None, role="Planning lead", token=None):  # no name: one per seat (a session refuses two people with one name)
    body: dict = {"code": code}
    if seat is not None:
        body.update(seat=seat, name=name or f"Ada Example {seat}", role=role)
    return c.post(f"{BASE}/join", json=body, headers={"X-Session-Token": token} if token else {})


def seat_in(world, c, code, n, **kw) -> tuple[str, dict]:
    """A guest takes seat n: (token, response body)."""
    r = join(c, code, n, **kw)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()


def hdr(token: str) -> dict:
    return {"X-Session-Token": token}


def lobby(c, sid: str, token: str | None = None):
    return c.get(f"{BASE}/sessions/{sid}/lobby", headers=hdr(token) if token else {})


def all_text(root) -> str:
    """Everything under the data root as text (so a test can prove a secret is not stored anywhere)."""
    return "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in Path(root).rglob("*") if p.is_file())
