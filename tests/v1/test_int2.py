"""INT2: chat-turn loop traces listed for Settings, trace ids carry a hashed person never a name, North/Span Design talks are scoped to the intent's project."""
import json

import pytest

from sh_platform.agents.protocols import ModelReply
from sh_platform.agents.runs import RunRegistry
from sh_platform.v1 import e6_trace as T
from sh_platform.v1 import i6_chat as C
from sh_platform.v1 import mem_agent as M
from sh_platform.v1 import mem_wire as W
from sh_platform.v1 import p1_project
from tests.v1.test_context_wiring import last_trace_steps
from tests.v1.test_north_loop import IID, ME, Script, sow
from tests.v1.test_north_loop import plane as north_plane  # noqa: F401


def test_loop_traces_listed_newest_first_with_counts(north_plane):  # noqa: F811
    plane = north_plane
    reg = RunRegistry(plane)
    reg.record_trace(trace_id="tr-a", run_id="r1", agent="Lumen", status="done", elapsed_ms=50,
                     steps=[{"kind": "model", "tokens_in": 10, "tokens_out": 5}, {"kind": "tool"}])
    reg.record_trace(trace_id="tr-b", run_id="r2", agent="Tally", status="error", elapsed_ms=7, steps=[])
    got = T.loop_traces(plane)
    assert [g["trace_id"] for g in got] == ["tr-b", "tr-a"]
    want = {"trace_id": "tr-a", "agent": "Lumen", "at": got[1]["at"], "steps": 2, "tokens": 15, "ms": 50, "outcome": "done"}
    assert {k: got[1][k] for k in want} == want and got[1]["at"]
    assert got[1]["worded_by"] == "model" and got[1]["cost_usd"] is None and got[1]["runs"] == 1  # AQ1 RC-10: cost and who worded it
    assert T.steps_for(plane, "tr-a")[0]["agent"] == "Lumen"


def test_trace_id_hashes_the_person_and_is_stable_per_company(north_plane):  # noqa: F811
    plane = north_plane
    a, b = T.turn_trace_id(plane, ME, "north"), T.turn_trace_id(plane, ME, "north")
    assert a != b and a.rsplit("-", 1)[0] == b.rsplit("-", 1)[0] and a.startswith("tr-north-")
    for part in (ME.name, ME.account_id or ""):
        assert part and part.lower() not in a.lower()


def test_a_north_turn_leaves_a_trace_without_the_name_and_is_listed(north_plane):  # noqa: F811
    plane = north_plane
    m = Script(ModelReply(text=json.dumps({"reply": "Done.", "sow_patch": {}, "covered": [], "ready": False})))
    thread = {"turns": [{"id": "t", "by": "person", "name": "Ann", "text": "hello", "at": "", "need": None, "files": []}]}
    assert C.ask(m, plane, IID, thread, sow("Monthly pack"), [], "hello", ["Ann"], [], None, ME)
    row = T.loop_traces(plane)[0]
    assert row["agent"] and row["trace_id"].startswith("tr-north-") and ME.name.lower() not in row["trace_id"].lower() and row["steps"] >= 1
    assert last_trace_steps(plane)


def test_intent_focus_names_the_project_or_stays_private(north_plane):  # noqa: F811
    plane = north_plane
    assert W.intent_focus(plane, "int-none") == {"intent": "int-none"}
    pid = p1_project.create_project(plane, IID, "Board pack", "Ann", "acc-ann")["id"]
    assert W.intent_focus(plane, IID) == {"intent": IID, "project": pid}


def test_the_route_is_admin_only(north_plane, monkeypatch):  # noqa: F811
    from fastapi import HTTPException
    from sh_platform.v1 import e6a_routes as R
    monkeypatch.setattr(R, "viewer_of", lambda request: ME)
    with pytest.raises(HTTPException) as e:
        R.loops(object())
    assert e.value.status_code == 403


def test_trace_id_format_for_all_four_agents(north_plane):  # noqa: F811
    """Verify tr-<agent>-<hash>-<random> format with no names for North, Lumen, Span Build, Tally."""
    plane = north_plane
    agents = ["north", "lumen", "span-build", "tally"]
    for agent in agents:
        id_a = T.turn_trace_id(plane, ME, agent)
        id_b = T.turn_trace_id(plane, ME, agent)
        # Format: tr-<agent>-<hash>-<random> where hash and random are 8 hex each
        # Split from right to handle agents with hyphens (span-build)
        parts = id_a.rsplit("-", 2)  # split off last two parts (hash and random)
        assert len(parts) == 3 and parts[0] == f"tr-{agent}", f"format error in {agent}: {id_a}"
        assert len(parts[1]) == 8 and len(parts[2]) == 8, f"hash/random not 8 hex in {agent}: {id_a}"
        # Hash is stable, random part differs
        assert id_a.rsplit("-", 1)[0] == id_b.rsplit("-", 1)[0], f"hash part unstable for {agent}"
        assert id_a.rsplit("-", 1)[1] != id_b.rsplit("-", 1)[1], f"random part same for {agent}"
        # No name in the trace id
        assert ME.name.lower() not in id_a.lower(), f"name {ME.name} found in {agent} trace id"
        assert (ME.account_id or "").lower() not in id_a.lower(), f"account_id {ME.account_id} found in {agent} trace id"


def test_person_tag_stable_and_hashed(north_plane):  # noqa: F811
    """Verify person_tag is stable per person per company and reveals no name."""
    plane = north_plane
    tag_a = T.person_tag(plane, ME)
    tag_b = T.person_tag(plane, ME)
    assert tag_a == tag_b and len(tag_a) == 8, f"tag unstable: {tag_a} vs {tag_b}"
    # Verify it's hex (all digits and a-f)
    assert all(c in "0123456789abcdef" for c in tag_a), f"tag not hex: {tag_a}"
    # No name in tag
    assert ME.name.lower() not in tag_a.lower(), f"name {ME.name} found in tag"
    assert (ME.account_id or "").lower() not in tag_a.lower(), f"account_id {ME.account_id} found in tag"
