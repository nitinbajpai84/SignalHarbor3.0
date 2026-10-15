"""Smoke: the process record (D-026) works for every seeded company and stays inside its own plane.

A session and its outcome are created together as "in progress", can be found from either side, and a
company's records are never visible from another company's plane. The store is module-agnostic: whether a
company may use a module is the caller's job (the module gate), not the store's.
"""
import pytest

from smoke_helpers import PEOPLE
from sh_platform.plane import CrossCompanyError
from sh_platform.process_record import ProcessRecords


def _store(env, company_id: str) -> ProcessRecords:
    return ProcessRecords(env.planes.plane_for(company_id))


def test_a_started_session_links_to_its_outcome_both_ways_for_every_company(env, case):
    store = _store(env, case["id"])
    rec = store.start("m1_intent", "charter", label="Illustrative session")
    assert rec.session_state == "in_progress" and rec.outcome_state == "in_progress"
    assert store.get_by_session(rec.session_id) == store.get_by_outcome(rec.outcome_id) == rec
    land = store.landing_for(rec.session_id)
    assert land.kind == "session" and land.state == "in_progress"  # a started session lands on its own state
    store.set_session_state(rec.session_id, "paused")
    assert store.landing_for(rec.session_id).state == "paused"  # a paused one too
    done = store.complete_outcome(rec.outcome_id)
    assert done.outcome_state == "completed" and done.session_state == "completed"
    land = store.landing_for(rec.session_id)
    assert land.kind == "outcome" and land.outcome_id == rec.outcome_id  # then it lands on the outcome
    assert [r.session_id for r in store.list(module_id="m1_intent")] == [rec.session_id]


def test_one_companys_records_are_not_visible_from_another_companys_plane(env):
    a, b = _store(env, "harbor-mutual"), _store(env, "tidewater-capital")
    rec = a.start("m2_baseline", "process_map")
    assert b.get_by_session(rec.session_id) is None and b.get_by_outcome(rec.outcome_id) is None
    assert b.list() == []
    assert b.landing_for(rec.session_id) is None
    own = b.start("m1_intent", "charter")
    assert a.get_by_session(own.session_id) is None
    assert {r.session_id for r in a.list()} == {rec.session_id}


def test_the_empty_company_can_keep_records_too_and_the_gate_is_the_callers_job(env):
    # The store does not know about entitlements: the empty company owns no module, but a record can exist
    # (for example one imported or started by an administrator); module routes stay refused by the gate.
    store = _store(env, "solo-studio")
    rec = store.start("m1_intent", "charter")
    assert store.get_by_outcome(rec.outcome_id) == rec
    assert env.entitlements.enabled_modules("solo-studio") == []
    solo = env.login(next(p for p in PEOPLE if p["company"] == "solo-studio")["email"])
    assert solo.get("/api/modules/m1_intent/anything").status_code == 403


def test_a_company_can_only_reach_its_own_records_file(env):
    plane = env.planes.plane_for("harbor-mutual")
    with pytest.raises(CrossCompanyError):
        plane.path("..", "tidewater-capital", "context", "process_records.json")
