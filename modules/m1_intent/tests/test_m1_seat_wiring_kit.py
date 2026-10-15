"""Shared set-up for the M1-P05 tests (no tests here). The real app, real join links, real guests with tokens: a
session is made by the organiser, the room started, guests take seats by the link, the briefing started and everyone
sent to the private rooms through the API. North's model is a stub (no live call). Synthetic names only."""
import json

from fastapi.testclient import TestClient

from m1_kit import BASE, World
from modules.m1_intent.domain.seat_identity import seat_id_of
from modules.m1_intent.store.room import RoomStore
from sh_platform.agents.protocols import ModelReply
from test_m1_room_kit import guest, hdr, new_session, seat_in, start_room


class StubNorth:
    """One question for a conversation turn; the given proposal (as JSON) for a note pre-fill."""

    def __init__(self, proposal: dict | None = None):
        self.proposal, self.calls = proposal or {}, []

    def complete(self, module_id, messages, tools=None):
        self.calls.append(messages)
        if "ONLY one JSON object" in messages[0]["content"]:
            return ModelReply(json.dumps(self.proposal))
        return ModelReply("Who is affected?")


def new_world(tmp_path, model=None) -> World:
    w = World(tmp_path)
    w.app.state.model_env = {}  # the real .env holds keys: a test must never pick it up
    w.app.state.north_model_factory = lambda plane: model or StubNorth()
    return w


class Guest:
    """One person with no account: a browser and a token."""

    def __init__(self, world, token: str, sid: str, name: str):
        self.c, self.token, self.sid, self.name = guest(world), token, sid, name

    def call(self, method: str, path: str, **kw):
        return self.c.request(method, f"{BASE}/sessions/{self.sid}{path}", headers=hdr(self.token), **kw)

    def room(self) -> dict:
        return self.call("GET", "/room").json()

    def write(self, text="Renewals slip every month", kind="note") -> str:
        r = self.call("POST", "/room/messages", json={"text": text, "kind": kind})
        assert r.status_code == 200, r.text
        return r.json()["notes"][-1]["id"]

    def save(self, note_id: str, **body):
        return self.call("POST", f"/room/notes/{note_id}", json=body)

    def submit(self, note_id: str):
        return self.call("POST", f"/room/notes/{note_id}/submit")


def flow(world, company="co-a", org_name="", seats=3, names=("Ada Guest", "Ben Guest"), organiser_roles=("sponsor",), stage="private_rooms", prep=None):
    """(organiser client, session id, [Guest]) with the session in `stage` (lobby, briefing or private_rooms)."""
    org = world.login(org_name or f"org {company}", company, list(organiser_roles))
    sid = new_session(org, seats=seats, **(prep or {}))
    code = start_room(org, sid)
    people = []
    for i, name in enumerate(names, 1):
        token, _ = seat_in(world, guest(world), code, i, name=name)
        people.append(Guest(world, token, sid, name))
    if stage != "lobby":
        assert org.post(f"{BASE}/sessions/{sid}/briefing").status_code == 200
    if stage == "private_rooms":
        assert org.post(f"{BASE}/sessions/{sid}/briefing/send").status_code == 200
    return org, sid, people


def ids_of(world, company: str, sid: str, n: int) -> dict:
    """The seat id and the guest id of seat n, read straight from the room store (what must never leak)."""
    seat = next(s for s in RoomStore(world.plane(company)).get(sid)["seats"] if s["n"] == n)
    return {"seat": seat_id_of(world.plane(company), sid, seat), "guest": seat["participant_id"], "name": seat["name"]}


def admin(world, company="co-a") -> TestClient:
    return world.login(f"admin {company}", company, ["company_admin"])
