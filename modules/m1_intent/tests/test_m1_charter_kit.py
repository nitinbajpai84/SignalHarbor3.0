"""Helpers for the M1-P09 tests (no tests here): a session taken to the together stage with a fixture result in the
shape contracts/charter.yaml describes. Family-office wording only as example text. Every token is made at run time."""
import itertools
import json

import pytest
import yaml

from m1_kit import BASE
from modules.m1_intent.store.room import RoomStore
from modules.m1_intent.store.sessions import SessionStore
from sh_platform.plane import PlaneStore
from test_m1_room_kit import join, new_session, start_room

CLUSTERS = [
    {"id": "c1", "title": "Capital calls arrive too late", "priority": "must", "note_count": 6, "agree_count": 4, "ticked": True,
     "so_that": "funding is planned, not found", "library_problem_id": "P-0"},
    {"id": "c2", "title": "No single exposure view", "priority": "should", "note_count": 5, "agree_count": 3, "ticked": True,
     "so_that": None, "library_problem_id": "P-1"},
    {"id": "c3", "title": "Nobody owns the manager fee list", "priority": None, "note_count": 2, "agree_count": 1, "ticked": True,
     "so_that": None, "library_problem_id": None},
    {"id": "c4", "title": "Reporting is monthly only", "priority": "could", "note_count": 1, "agree_count": 0, "ticked": False,
     "so_that": None, "library_problem_id": None},
]
APPROVER = "Test Approver Person"
_COUNT = itertools.count(1)


def give_pack_measures(world, industry="industry_a"):
    """Adds measures to a test pack and links two of its problems to them (one id is not in the pack on purpose)."""
    folder = world.packs / industry / "1"
    (folder / "kpi_tree.yaml").write_text(yaml.safe_dump({"kpis": [{"id": "K1", "name": "Six-month funding headroom"},
                                                                     {"id": "K2", "name": "Exposure coverage"},
                                                                     {"id": "K3", "name": "Manager fee drag"}]}))
    rows = yaml.safe_load((folder / "problems.yaml").read_text())["problems"]
    rows[0]["kpi_ids"] = ["K1", "K9"]          # K9 is not a measure of this pack: must never be drawn
    rows[1]["kpi_ids"] = ["K2"]
    (folder / "problems.yaml").write_text(yaml.safe_dump({"problems": rows}))


def put_raw(world, company, sid, obj):
    plane = PlaneStore(world.settings.data_root).plane_for(company).ensure()
    path = plane.path("intents", "m1_intent", "together", f"{sid}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def put_result(world, company, sid, clusters=None):
    put_raw(world, company, sid, {"clusters": CLUSTERS if clusters is None else clusters})


def to_together(world, company, sid):
    store = SessionStore(world.plane(company))
    for s in ("briefing", "private_rooms", "board", "together"):
        store.transition(sid, s)


def ready(world, company="co-a", seats=3, approver=APPROVER, result=True, taken=0, signers=2, **over):  # two signers: the older flow, now a Prepare choice (LI-M1)
    """(organiser client, session id, join code) with the session at the together stage."""
    org = world.login(f"org-{next(_COUNT)}", company, ["company_admin"])
    sid = new_session(org, seats=seats, approver_name=approver, signers=signers, **over)
    code = start_room(org, sid)
    for n in range(1, taken + 1):  # people who sat down in the lobby, by token like a guest
        RoomStore(world.plane(company)).take(sid, n, f"Person {n}", "Planning lead", None)
    to_together(world, company, sid)
    if result:
        put_result(world, company, sid)
    return org, sid, code


def draft(org, sid):
    r = org.post(f"{BASE}/sessions/{sid}/charter", json={"confirm": True})
    assert r.status_code == 201, r.text
    return r.json()


def charter(c, sid) -> dict:
    r = c.get(f"{BASE}/sessions/{sid}/charter")
    assert r.status_code == 200, r.text
    return r.json()


def second_signer(world, company, code, role="sponsor"):
    """A second person of the company who takes a seat with their account, so they can sign in the room."""
    c = world.login(f"signer-{role}", company, [role])
    assert join(c, code, 2, name="Second Signer", role="Sponsor").status_code == 200
    return c


def send_up(org, sid) -> str:
    r = org.post(f"{BASE}/sessions/{sid}/charter/send")
    assert r.status_code == 200, r.text
    return r.json()["link_path"].removeprefix("/approve/")


def approver_post(world, token, what="charter", body=None):
    """The approver's browser: no account, no cookie; the token only in the header."""
    from fastapi.testclient import TestClient
    c = TestClient(world.app)
    return c.post(f"{BASE}/approver/{what}", json=body, headers={"X-Session-Token": token})


def _read_stand_in(plane, session_id):
    path = plane.path("intents", "m1_intent", "together", f"{session_id}.json")
    return json.loads(path.read_text()) if path.is_file() else None


@pytest.fixture(autouse=True)
def stand_in_result(monkeypatch):
    """The charter tests feed a fixture together-result; the real board-to-charter path is tested in
    test_m1_charter_from_board.py. Imported by each charter test file so it applies there only."""
    from modules.m1_intent.api import charter as api_charter
    monkeypatch.setattr(api_charter, "together_result", _read_stand_in)
