"""Helpers for the M2-P02 tests (no tests here): a baseline's kpis.json in exactly the contracts/SHARED.md shape, a moving
clock, and a visitor with no account who holds only a link. Synthetic family-office wording; no real client data."""
import json

from fastapi.testclient import TestClient

from modules.m2_baseline.domain.provenance import prov

BASE = "/api/modules/m2_baseline"
BID = "a" * 32  # a real baseline id is 32 hex characters (store.baseline.is_id)
DAY = 86400.0


def kpi(kid: str, name: str, business=None, data=None, process=None, definition="A definition the owner never receives") -> dict:
    def owner(n):
        return prov(n, "stated", "Mei Tan", "work list") if n else prov(None, "unknown", "Lens", "")
    return {"id": kid, "name": name, "problem_ids": ["p1"], "priority": "high", "definition": prov(definition, "stated", "Mei Tan"),
            "owners": {"business": owner(business), "data": owner(data), "process": owner(process)},
            "governance": {"personal": "no", "sensitive": False, "may_see": []},
            "tracking": prov("partly", "guessed", "Lens")}


KPIS = [kpi("k1", "Funding capacity", business="Tom Reyes", data="Arjun Rao", process="Sara Lim"),
        kpi("k2", "Capital call timing", business="Tom Reyes", data="Arjun Rao"),
        kpi("k3", "Distribution lag", data="Wei Chen")]


def seed(world, company="co-a", bid=BID, kpis=None) -> None:
    folder = world.plane(company).path("intents", "m2_baseline", bid)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "kpis.json").write_text(json.dumps(KPIS if kpis is None else kpis))


class Clock:
    def __init__(self, world, start=1_800_000_000.0):
        self.t = start
        world.app.state.m2_clock = lambda: self.t

    def days(self, n: float) -> None:
        self.t += n * DAY


def send(org: TestClient, bid=BID) -> dict:
    r = org.post(f"{BASE}/baselines/{bid}/requests")
    assert r.status_code == 200, r.text
    return {x["owner_name"]: x for x in r.json()["sent"]}


def token_of(sent_row: dict) -> str:
    return sent_row["link_path"].removeprefix("/answer/")


def visitor(world, token: str | None = None) -> TestClient:
    """A person with no account, holding only a link."""
    c = TestClient(world.app)
    if token:
        c.headers["x-session-token"] = token
    return c
