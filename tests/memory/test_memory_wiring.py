"""MEM-2 wiring: the agents write and read memory at the ends of conversations. Stub model, synthetic names."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "modules" / "m1_intent" / "tests"), str(ROOT / "tests" / "interview")]

import iv_kit  # noqa: E402
from m1_kit import BASE  # noqa: E402
from sh_platform.interview import api as interview_api, engine  # noqa: E402
from sh_platform.agents.protocols import ModelReply  # noqa: E402
from sh_platform.memory import for_prompt, summarise  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.profile import record  # noqa: E402
from test_m1_seat_wiring_kit import flow, new_world  # noqa: E402

LINE = "fact: Prefers a short weekly report"
LENS = {"mark": "stated", "by": "Test", "from": "A list"}


class Stub:
    """One question for a conversation turn; one memory line for the summary call."""

    def complete(self, module_id, messages, tools=None):
        return ModelReply(LINE if "long-term memory" in messages[0]["content"] else "Who is affected?")


def people_files(plane, agent="north"):
    folder = plane.path("context", "memory", agent, "people")
    return sorted(p.stem for p in folder.glob("*.json")) if folder.is_dir() else []


def seated_rooms(tmp_path, link: bool):
    w = new_world(tmp_path, Stub())
    org, sid, (ada, _) = flow(w)
    plane = w.plane("co-a")
    if link:
        record(plane, "people.p-org.account_id", org.account_id, {**LENS, "at": "2026-10-01T09:00"})
    assert org.post(f"{BASE}/sessions/{sid}/room/messages", json={"text": "Reports arrive late", "kind": "note"}).status_code == 200
    assert ada.write("Nobody owns exposure") and True
    return w, org, sid, plane


def test_closing_the_rooms_writes_memory_for_a_linked_seat_only(tmp_path):
    w, org, sid, plane = seated_rooms(tmp_path, link=True)
    assert org.post(f"{BASE}/sessions/{sid}/rooms/close").json() == {"state": "board"}
    assert people_files(plane) == ["p-org"]  # the guest has no account, so no link, so nothing
    assert "short weekly report" in json.dumps(for_prompt(plane, "north", "p-org", budget=1200))


def test_an_unlinked_account_writes_nothing_and_a_memory_error_does_not_break_the_close(tmp_path, monkeypatch):
    w, org, sid, plane = seated_rooms(tmp_path, link=False)
    assert org.post(f"{BASE}/sessions/{sid}/rooms/close").status_code == 200
    assert people_files(plane) == []
    w2, org2, sid2, plane2 = seated_rooms(tmp_path / "two", link=True)

    def boom(*a, **k):
        raise RuntimeError("memory store down")
    monkeypatch.setattr(summarise, "summarise_and_remember", boom)
    assert org2.post(f"{BASE}/sessions/{sid2}/rooms/close").json() == {"state": "board"}
    assert people_files(plane2) == []


def test_finishing_the_interview_writes_memory(tmp_path):
    plane = PlaneStore(tmp_path).create(iv_kit.FAMILY)
    iv_kit.seed(plane)
    person = engine.find(plane, "aaron-lyle", [])
    engine.start(plane, person)
    state = SimpleNamespace(company_id=iv_kit.FAMILY)
    app = SimpleNamespace(state=SimpleNamespace(interview_model_factory=lambda p: Stub(), model_env={},
                                                entitlements=SimpleNamespace(is_enabled=lambda c, m: True)))
    engine.finish(plane, person["id"])
    interview_api._remember(SimpleNamespace(app=app, state=state), plane, person, False, iv_kit.FAMILY)
    assert "short weekly report" in json.dumps(for_prompt(plane, "north", "aaron-lyle", budget=1200))
