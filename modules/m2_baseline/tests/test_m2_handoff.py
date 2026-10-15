"""M2-28 hand-off to module 3 (the baseline outcome record, unknowns first) and D-026 (the two-way link with the module 2
process record)."""
import pytest

from m2_kit import BASE
from modules.m2_baseline.domain import handoff as H
from modules.m2_baseline.store.signoff import latest_baseline_outcome, read_baseline_outcome
from sh_platform.process_record import ProcessRecords
from test_m2_signoff_kit import BID, CATALOGUE, PROCESS_MAP, Team, confirm_all, me, seed, sign_both


@pytest.fixture
def signed(world):
    seed(world)
    team = Team(world)
    team.c["sam"].put(team.url("/review/K2"), json={"next_step": "Ask the custodian for a feed", "project": "Data hub", "tentative_date": "2027-03-31"})
    team.c["sam"].post(team.url("/review/K2/accept"))
    confirm_all(team)
    sign_both(team)
    return team


def outcome(team):
    r = team.c["hana"].get(team.url("/handoff"))
    assert r.status_code == 200, r.text
    return r.json()


def test_nothing_unsigned_leaves_module_2(world):
    seed(world)
    team = Team(world)
    assert team.c["sam"].get(team.url("/handoff")).status_code == 404
    confirm_all(team)
    team.c["sam"].post(team.url("/countersign"))                                         # one signature is not a signed baseline
    assert team.c["sam"].get(team.url("/handoff")).status_code == 404
    assert not list(world.plane("co-a").path("intents", "m2_baseline").glob("outcomes/*.json"))
    contract = H.load_outcome_contract()
    with pytest.raises(ValueError, match="only a signed baseline"):
        H.build_outcome(contract, outcome_id="o", session_id="s", baseline={"id": "b"}, version={"status": "open", "countersign": []},
                        view={"kpis": []}, process_map={}, catalogue={})


def test_signing_writes_the_record_module_3_reads(signed):
    rec = outcome(signed)
    contract = H.load_outcome_contract()
    assert all(k in rec for k in contract["required"])
    assert rec["module"] == "m2_baseline" and rec["kind"] == "baseline" and rec["baseline_id"] == BID and rec["baseline_version"] == 1
    assert rec["charter_outcome_id"] == "c" * 32 and rec["signed_at"]
    assert [s["slot"] for s in rec["signatures"]] == ["sponsor", "head_of_data"]
    assert {s["name"] for s in rec["signatures"]} == {me("sam"), me("hana")}
    assert len(rec["confirmations"]) == 6 and set(rec["confirmations"][0]) == set(contract["confirmation_fields"])
    assert rec["process_map"] == PROCESS_MAP                                             # the process map as signed
    assert set(rec["catalogue"]) == {"sources", "tables", "fields", "extractions", "kpis"} and rec["catalogue"]["sources"] == CATALOGUE["sources"]
    assert not any("account" in k for s in rec["signatures"] for k in s)                 # no account ids in the hand-off


def test_gaps_are_of_real_kinds_in_the_contracts_order_with_plain_messages(signed):
    gaps = outcome(signed)["gaps"]
    assert [g["id"] for g in gaps] == [f"G{n:03d}" for n in range(1, len(gaps) + 1)]
    assert all(set(g) == set(H.load_outcome_contract()["gap_fields"]) for g in gaps)
    order = [t["id"] for t in H.load_outcome_contract()["gap_types"]]
    types = [g["type"] for g in gaps]
    assert types == sorted(types, key=order.index) and set(types) <= set(order) and not {"unknown", "empty"} & set(types)
    assert [g["where"] for g in gaps if g["type"] == "no_owner"] == ["Manager fee reconciliation: no business owner"]
    assert any(g["type"] == "not_tracked" and g["kpi_id"] == "K2" for g in gaps)
    assert next(g for g in gaps if g["type"] == "not_tracked")["accepted"]["by"] == me("sam")   # the acceptance travels with the gap
    assert len(gaps) == 2 and all(g["severity"] in ("high", "medium") and g["why"] and g["action"] for g in gaps)  # a blank cell is not a gap


def test_the_process_record_links_both_ways(signed):
    plane = signed.world.plane("co-a")
    rec = outcome(signed)
    link = ProcessRecords(plane).get_by_outcome(rec["outcome_id"])
    assert link.module_id == "m2_baseline" and link.kind == "baseline" and link.session_id == rec["session_id"]
    assert link.outcome_state == "completed" and link.session_state == "completed"
    assert ProcessRecords(plane).get_by_session(rec["session_id"]).outcome_id == rec["outcome_id"]
    land = ProcessRecords(plane).landing_for(rec["session_id"])
    assert land.kind == "outcome" and land.outcome_id == rec["outcome_id"]
    assert read_baseline_outcome(plane, rec["outcome_id"]) == rec and latest_baseline_outcome(plane, BID) == rec
    assert signed.c["sam"].get(signed.url("/review")).json()["outcome_id"] == rec["outcome_id"]


def test_the_record_exists_in_progress_from_the_first_change(world):
    seed(world)
    team = Team(world)
    assert ProcessRecords(world.plane("co-a")).list(module_id="m2_baseline") == []
    team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K1", "part": "definition"})
    (rec,) = ProcessRecords(world.plane("co-a")).list(module_id="m2_baseline")
    assert rec.outcome_state == "in_progress" and rec.session_state == "in_progress"


def test_a_new_version_signed_again_is_a_new_record_and_the_old_one_stays(signed):
    first = outcome(signed)
    signed.c["sam"].post(signed.url("/versions"))
    confirm_all(signed)
    sign_both(signed)
    second = outcome(signed)
    assert second["baseline_version"] == 2 and second["outcome_id"] != first["outcome_id"] and second["session_id"] != first["session_id"]
    assert read_baseline_outcome(signed.world.plane("co-a"), first["outcome_id"]) == first   # signed content is never rewritten


def test_gaps_for_no_measures_and_for_a_catalogue_with_blank_cells_and_one_undecided_source():
    contract = H.load_outcome_contract()
    assert H.build_gaps(contract, [], {}) == [] and H.build_gaps(contract, [], CATALOGUE) == []   # an unknown or blank cell is not a gap
    cat = {**CATALOGUE, "sources": [{**CATALOGUE["sources"][0], "Contains personal data?": {"value": "Not sure", "mark": "stated"}}]}
    assert [(g["type"], g["where"]) for g in H.build_gaps(contract, [], cat)] == [("personal_undecided", "sources S01: Contains personal data?")]
