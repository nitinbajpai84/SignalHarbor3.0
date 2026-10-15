"""M1-29 skeleton: where sessions live in the company plane, strict reads, atomic writes, process record link."""
import json

import pytest

from m1_kit import World
from modules.m1_intent.domain import contracts as C
from modules.m1_intent.domain.preparation import Offers, clean, default_preparation
from modules.m1_intent.store.sessions import SessionStore, StoreError, WrongState
from sh_platform.plane import CrossCompanyError
from sh_platform.process_record import ProcessRecords

S, T = C.load_session_settings(), C.load_charter_templates()


def prep(purpose="Find out why renewals slip", **over):
    return clean({"purpose": purpose, **over}, default_preparation(S, T), S, T, Offers(False, False))


def store_for(world: World, company="co-a") -> SessionStore:
    return SessionStore(world.plane(company).ensure())


def test_files_live_under_the_intents_area_of_the_plane(world):
    st = store_for(world)
    s = st.create("acct-1", prep())
    base = world.plane("co-a").area("intents")
    files = sorted(p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file())
    assert files == ["m1_intent/index.json", f"m1_intent/sessions/{s['id']}.json"]
    assert not list(base.rglob("*.tmp"))  # atomic writes leave nothing behind


def test_create_gives_a_draft_and_starts_the_process_record_with_both_ids(world):  # D-026, A-026
    st = store_for(world)
    s = st.create("acct-1", prep("Renewals"))
    assert s["state"] == "draft" and s["outcome_id"] and s["record_session_id"]
    rec = ProcessRecords(world.plane("co-a")).get_by_session(s["record_session_id"])
    assert rec.outcome_id == s["outcome_id"] and rec.module_id == "m1_intent" and rec.kind == "charter"
    assert (rec.session_state, rec.outcome_state) == ("in_progress", "in_progress")
    assert rec.label == "Renewals"


def test_reopen_finds_the_outcome_and_the_outcome_opens_its_session(world):
    st = store_for(world)
    s = st.create("acct-1", prep())
    again = st.get(s["id"])
    assert again["outcome_id"] == s["outcome_id"]
    assert st.get_by_outcome(s["outcome_id"])["id"] == s["id"]
    assert st.get_by_outcome("f" * 32) is None
    landing = ProcessRecords(world.plane("co-a")).landing_for(s["record_session_id"])
    assert (landing.kind, landing.state) == ("session", "in_progress")


def test_state_changes_mirror_into_the_process_record(world):
    st = store_for(world)
    recs = ProcessRecords(world.plane("co-a"))
    s = st.create("acct-1", prep())
    st.transition(s["id"], "lobby")
    st.transition(s["id"], "briefing")
    st.transition(s["id"], "paused")
    assert recs.get_by_session(s["record_session_id"]).session_state == "paused"
    assert st.get(s["id"])["paused_from"] == "briefing"
    st.transition(s["id"], "briefing")
    assert recs.get_by_session(s["record_session_id"]).session_state == "in_progress"
    with pytest.raises(WrongState):
        st.transition(s["id"], "board")


def test_update_only_a_draft_and_only_by_the_organiser(world):
    st = store_for(world)
    s = st.create("acct-1", prep())
    assert st.update_draft(s["id"], "acct-1", prep("New purpose"))["preparation"]["purpose"] == "New purpose"
    assert st.update_draft(s["id"], "acct-2", prep("Hijack")) is None  # someone else's draft: not found
    st.transition(s["id"], "lobby")
    with pytest.raises(WrongState) as e:
        st.update_draft(s["id"], "acct-1", prep("Too late"))
    assert "started" in str(e.value)
    assert st.get(s["id"])["preparation"]["purpose"] == "New purpose"


def test_list_is_only_my_sessions_newest_first(world):
    st = store_for(world)
    a = st.create("acct-1", prep("one"))
    b = st.create("acct-1", prep("two"))
    st.create("acct-2", prep("not mine"))
    assert [x["id"] for x in st.list_for("acct-1")] == [b["id"], a["id"]]
    assert st.list_for("nobody") == []


def test_delete_is_draft_only_organiser_only_and_closes_the_record(world):
    st = store_for(world)
    recs = ProcessRecords(world.plane("co-a"))
    s = st.create("acct-1", prep())
    assert st.delete_draft(s["id"], "acct-2") is False
    assert st.delete_draft(s["id"], "acct-1") is True
    assert st.get(s["id"]) is None and st.list_for("acct-1") == []
    assert recs.get_by_session(s["record_session_id"]).session_state == "completed"
    started = st.create("acct-1", prep())
    st.transition(started["id"], "lobby")
    with pytest.raises(WrongState):
        st.delete_draft(started["id"], "acct-1")


def test_corrupt_session_file_is_refused_and_left_untouched(world):
    st = store_for(world)
    s = st.create("acct-1", prep())
    path = world.plane("co-a").path("intents", "m1_intent", "sessions", f"{s['id']}.json")
    path.write_text("{ not json", encoding="utf-8")
    for call in (lambda: st.get(s["id"]), lambda: st.update_draft(s["id"], "acct-1", prep("x")),
                 lambda: st.transition(s["id"], "lobby")):
        with pytest.raises(StoreError) as e:
            call()
        assert str(path) not in str(e.value) and s["id"] not in str(e.value)
    assert path.read_text(encoding="utf-8") == "{ not json"


def test_a_session_file_with_the_wrong_shape_is_refused(world):
    st = store_for(world)
    s = st.create("acct-1", prep())
    path = world.plane("co-a").path("intents", "m1_intent", "sessions", f"{s['id']}.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["state"] = "not-a-state"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(StoreError):
        st.get(s["id"])


def test_an_unreadable_index_is_never_overwritten(world):
    st = store_for(world)
    st.create("acct-1", prep())
    index = world.plane("co-a").path("intents", "m1_intent", "index.json")
    index.write_text("[[[", encoding="utf-8")
    with pytest.raises(StoreError):
        st.list_for("acct-1")
    with pytest.raises(StoreError):
        st.create("acct-1", prep("second"))
    assert index.read_text(encoding="utf-8") == "[[["
    assert len(list(index.parent.joinpath("sessions").glob("*.json"))) == 1  # no half-made second session


def test_ids_from_a_request_never_reach_a_path(world):
    st = store_for(world)
    for bad in ("../../index", "..\\x", "a" * 31, "G" * 32, "", None, 5):
        assert st.get(bad) is None
        assert st.delete_draft(bad, "acct-1") is False


def test_a_plane_whose_folder_is_a_link_is_refused(world, tmp_path):
    plane = world.plane("co-a").ensure()
    store = SessionStore(plane)
    store.create("acct-1", prep())
    other = tmp_path / "elsewhere"
    other.mkdir()
    intents = plane.area("intents")
    for p in sorted(intents.rglob("*"), reverse=True):
        p.unlink() if p.is_file() else p.rmdir()
    intents.rmdir()
    try:
        intents.symlink_to(other, target_is_directory=True)
    except OSError:
        pytest.skip("links need extra rights on this machine")
    with pytest.raises(CrossCompanyError):
        store.list_for("acct-1")


def test_two_companies_are_isolated(world):
    a, b = store_for(world, "co-a"), store_for(world, "co-b")
    s = a.create("acct-1", prep("only in A"))
    assert b.get(s["id"]) is None and b.list_for("acct-1") == [] and b.get_by_outcome(s["outcome_id"]) is None
    assert ProcessRecords(world.plane("co-b")).get_by_session(s["record_session_id"]) is None
    assert b.templates() == []


def test_templates_keep_the_preparation_values_only(world):
    st = store_for(world)
    s = st.create("acct-1", prep(seats=4, approver_name="Chief Anybody"))
    t = st.save_template("Quarterly review", s["id"], "acct-1")
    assert t["name"] == "Quarterly review" and t["preparation"] == s["preparation"]
    assert set(t) == {"id", "name", "preparation", "created_at"}  # no session, no organiser, no notes
    assert [x["id"] for x in st.templates()] == [t["id"]]
    assert st.save_template("Nope", s["id"], "acct-2") is None


@pytest.mark.parametrize("content", [b"null", b"[]"])
def test_a_file_that_is_not_an_object_is_refused_and_left_alone(world, content):
    st = store_for(world)
    path = world.plane("co-a").area("intents") / "m1_intent" / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    with pytest.raises(StoreError):
        st.create("acct-1", prep())
    assert path.read_bytes() == content
