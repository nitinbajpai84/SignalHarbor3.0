"""Shared set-up for the M1-P03 tests (no tests here). A session is brought to a stage by the real store, a seated
person is a real signed-in account bound to a real seat of the room (made the first time the person asks about a
session), the clock is a list the test moves, and Nira's model is the evals harness stub."""
import re

from m1_kit import BASE, World, draft
from modules.m1_intent.domain import room as R
from modules.m1_intent.store.room import RoomStore
from modules.m1_intent.store.sessions import SessionStore
from sh_platform.agents.evals.harness import ScriptedModel
from sh_platform.agents.protocols import ModelReply

PATH = ("lobby", "briefing", "private_rooms", "board", "together", "signing")
T0 = 1_800_000_000.0


def make_world(tmp_path, reply="Here is the answer from the rules.") -> World:
    w = World(tmp_path)
    w.now = [T0]
    w.app.state.m1_clock = lambda: w.now[0]
    w.app.state.model_env = {}  # the real .env holds keys: a test must never pick it up
    use_model(w, ScriptedModel([ModelReply(reply)]))
    return w


def use_model(w: World, model):
    """Plug Nira's model in the way the module allows (`app.state.nira_model_factory`); None means no model."""
    w.app.state.nira_model_factory = lambda plane: model
    return model


def seated(w: World, company: str, name: str, seat: str = "", roles=("participant",)):
    """A signed-in person (default: a participant account) who holds the next free seat of whichever session they
    first ask about. `seat` is only a label for the reader."""
    c = w.login(name, company, list(roles))
    real, done = c.request, set()

    def request(method, url, *a, **k):
        m = re.search(r"/sessions/([0-9a-f]{32})", str(url))
        if m and m.group(1) not in done:
            done.add(m.group(1))
            sit(w, company, m.group(1), c.account_id, name)
        return real(method, url, *a, **k)
    c.request = request
    return c


def sit(w: World, company: str, sid: str, account_id: str, name: str) -> None:
    """Binds the account to the next free seat of the session's room (the room is made if the test put the session
    straight into a stage)."""
    rooms = RoomStore(w.plane(company).ensure())
    if rooms.get(sid) is None:
        rooms._save({"session_id": sid, "seats": R.new_seats(rooms.sessions.get(sid)["preparation"]["seats"])})
    free = next(x["n"] for x in rooms.get(sid)["seats"] if x["state"] == "free")
    rooms.take(sid, free, name, "Planning lead", account_id)


def session_at(w: World, organiser, company: str, stage: str = "briefing", **prep) -> str:
    r = organiser.post(f"{BASE}/sessions", json=draft(**prep))
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    store = SessionStore(w.plane(company).ensure(), clock=lambda: w.now[0])
    for s in PATH[:PATH.index(stage) + 1] if stage != "draft" else ():
        store.transition(sid, s)
    return sid


def stage_of(organiser, sid: str) -> str:
    return organiser.get(f"{BASE}/sessions/{sid}").json()["state"]
