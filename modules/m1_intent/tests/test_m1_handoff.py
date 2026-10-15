"""M1-30 the outcome record module 2 reads, and D-026 the two-way link between the session and its outcome."""
import json

import pytest

from m1_kit import BASE
from modules.m1_intent.domain import handoff as H
from modules.m1_intent.store.charter import CharterStore, read_outcome
from modules.m1_intent.store.sessions import SessionStore
from sh_platform.process_record import ProcessRecords
from test_m1_charter_kit import stand_in_result  # noqa: F401  (autouse: the fixture together-result)
from test_m1_charter_kit import APPROVER, approver_post, draft, ready, second_signer, send_up


def ids(world, org, sid, company="co-a"):
    s = SessionStore(world.plane(company)).get(sid)
    return s["outcome_id"], s["record_session_id"]


def test_the_outcome_record_exists_from_the_start_and_the_file_only_when_signed(world):
    org, sid, _ = ready(world, seats=1)
    outcome_id, record_sid = ids(world, org, sid)
    rec = ProcessRecords(world.plane("co-a")).get_by_outcome(outcome_id)
    assert rec.outcome_state == "in_progress" and rec.session_id == record_sid      # D-026: made up front
    draft(org, sid)
    assert read_outcome(world.plane("co-a"), outcome_id) is None                    # nothing leaves unsigned
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    assert read_outcome(world.plane("co-a"), outcome_id) is not None


def test_signing_in_the_room_writes_the_record_module_2_reads(world):
    org, sid, code = ready(world, taken=1)
    draft(org, sid)
    org.put(f"{BASE}/sessions/{sid}/charter", json={"so_that": {"c2": "concentration is seen early"}})
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    second_signer(world, "co-a", code).post(f"{BASE}/sessions/{sid}/charter/sign")
    outcome_id, _ = ids(world, org, sid)
    rec = read_outcome(world.plane("co-a"), outcome_id)
    contract = H.load_outcome_contract()
    assert all(k in rec for k in contract["required"])
    assert rec["outcome_id"] == outcome_id and rec["session_id"] == sid and rec["module"] == "m1_intent" and rec["kind"] == "charter"
    assert rec["charter_version"] == 1 and rec["template"] == "standard"
    assert [p["title"] for p in rec["problems"]] == ["Capital calls arrive too late", "No single exposure view", "Nobody owns the manager fee list"]
    assert [p["priority"] for p in rec["problems"]] == ["must", "should", None]
    assert rec["problems"][1]["so_that"] == "So that concentration is seen early."
    assert set(rec["problems"][0]) == set(contract["problem_fields"])
    assert rec["later"] == [{"id": "c4", "title": "Reporting is monthly only"}]
    assert rec["footer"]["participants"] == 1 and rec["footer"]["notes"] == 14 and rec["footer"]["later"] == 1
    assert [s["how"] for s in rec["signatures"]] == ["room", "room"] and all(s["name"] and s["at"] for s in rec["signatures"])
    assert not any("account" in k for s in rec["signatures"] for k in s)         # no account ids in the hand-off


def test_an_approval_writes_the_same_record_signed_by_the_approver(world):
    org, sid, _ = ready(world)
    draft(org, sid)
    approver_post(world, send_up(org, sid), "decision", {"decision": "approve"})
    outcome_id, _ = ids(world, org, sid)
    rec = read_outcome(world.plane("co-a"), outcome_id)
    assert rec["signatures"] == [{"name": APPROVER, "at": rec["signed_at"], "how": "approver"}]


def test_the_session_and_its_outcome_are_linked_both_ways(world):
    org, sid, _ = ready(world, seats=1)
    draft(org, sid)
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    outcome_id, record_sid = ids(world, org, sid)
    records = ProcessRecords(world.plane("co-a"))
    by_outcome, by_session = records.get_by_outcome(outcome_id), records.get_by_session(record_sid)
    assert by_outcome == by_session and by_outcome.outcome_state == "completed" and by_outcome.session_state == "completed"
    land = records.landing_for(record_sid)
    assert land.kind == "outcome" and land.outcome_id == outcome_id          # from the session you land on its outcome
    back = org.get(f"{BASE}/outcomes/{outcome_id}").json()                   # from the outcome you open its record and its session
    assert back["outcome_id"] == outcome_id and back["kind"] == "charter" and back["problems"] and back["signatures"]
    assert back["session"]["id"] == sid and back["session"]["state"] == "closed" and back["session"]["landing"]["kind"] == "outcome"
    assert {k: v for k, v in back.items() if k != "session"} == read_outcome(world.plane("co-a"), outcome_id)  # the record, unchanged
    assert org.get(f"{BASE}/sessions/{sid}").json()["outcome_id"] == outcome_id
    assert read_outcome(world.plane("co-a"), outcome_id)["session_id"] == sid


def test_a_declined_charter_hands_nothing_on_and_the_outcome_stays_in_progress(world):
    org, sid, _ = ready(world)
    draft(org, sid)
    approver_post(world, send_up(org, sid), "decision", {"decision": "decline", "comment": "Not yet"})
    outcome_id, record_sid = ids(world, org, sid)
    assert read_outcome(world.plane("co-a"), outcome_id) is None
    assert ProcessRecords(world.plane("co-a")).get_by_outcome(outcome_id).outcome_state == "in_progress"
    assert ProcessRecords(world.plane("co-a")).landing_for(record_sid).kind == "session"


def test_the_record_holds_no_note_text_no_author_and_no_company_id(world):
    org, sid, _ = ready(world, seats=1)
    draft(org, sid)
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    outcome_id, _ = ids(world, org, sid)
    text = json.dumps(read_outcome(world.plane("co-a"), outcome_id))
    assert "co-a" not in text and "agree_count" not in text and org.account_id not in text


def test_another_company_cannot_read_the_outcome_and_a_bad_id_is_none(world):
    org, sid, _ = ready(world, seats=1)
    draft(org, sid)
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    outcome_id, _ = ids(world, org, sid)
    assert read_outcome(world.plane("co-b").ensure(), outcome_id) is None        # each company has its own plane
    for bad in ("", "../x", None, 5, "g" * 32):
        assert read_outcome(world.plane("co-a"), bad) is None
    other = world.login("other", "co-b", ["company_admin"])
    assert other.get(f"{BASE}/outcomes/{outcome_id}").status_code == 404


def test_only_a_signed_version_can_be_built_into_a_record():
    contract = H.load_outcome_contract()
    unsigned = {"status": "draft", "signatures": [], "version": 1}
    with pytest.raises(ValueError):
        H.build_outcome(contract, outcome_id="a" * 32, session_id="b" * 32, version=unsigned)
    with pytest.raises(ValueError):
        H.build_outcome(contract, outcome_id="a" * 32, session_id="b" * 32, version={**unsigned, "status": "signed"})


def test_the_signed_version_in_the_store_matches_the_record(world):
    org, sid, _ = ready(world, seats=1)
    draft(org, sid)
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    outcome_id, _ = ids(world, org, sid)
    v = CharterStore(world.plane("co-a")).read(sid)["versions"][-1]
    rec = read_outcome(world.plane("co-a"), outcome_id)
    assert rec == H.build_outcome(H.load_outcome_contract(), outcome_id=outcome_id, session_id=sid, version=v)


def test_an_approved_charter_reads_one_of_one_signers(world):
    org, sid, _ = ready(world)
    draft(org, sid)
    approver_post(world, send_up(org, sid), "decision", {"decision": "approve"})
    s = org.get(f"{BASE}/sessions/{sid}/charter").json()["charter"]["signing"]
    assert (s["signed"], s["needed"]) == (1, 1)
