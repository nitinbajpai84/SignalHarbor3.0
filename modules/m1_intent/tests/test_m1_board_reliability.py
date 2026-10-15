"""CRITIC-M1 defects 2 and 8: when North cannot group, the board still has clusters (keywords, marked), the organiser can
regroup or make a cluster by hand, "together" with no clusters is refused, and prefill/save say what is wrong.
Stub North only, synthetic notes, no live call."""
import json

import pytest

from modules.m1_intent.agent import north
from modules.m1_intent.api import notes as notes_api
from modules.m1_intent.domain import board as B
from modules.m1_intent.domain import notes as N
from sh_platform.agents.protocols import ModelReply
from sh_platform.egress.aggregates import SuppressedFigures
from sh_platform.egress.gateway import _check_structure
from sh_platform.egress.model import encode_turn
from test_m1_board_kit import GatherStub, at_board, grouped
from test_m1_seat_wiring_kit import StubNorth, flow, new_world

S = B.load_settings()
MARK = "Grouped without North; please check."


def fake(i, text):
    return {"id": f"n{i}", "text": text}


def test_keyword_groups_share_a_word_from_the_notes_and_leave_the_rest_alone():
    notes = [fake(0, "Capital calls arrive late"), fake(1, "We miss capital call dates"), fake(2, "Exposure report is slow"),
             fake(3, "Exposure by name takes a week"), fake(4, "Fees differ by manager")]
    out = B.keyword_groups(S, notes)
    assert [(c["name"], c["note_ids"]) for c in out] == [("Capital", ["n0", "n1"]), ("Exposure", ["n2", "n3"])] \
        or {tuple(c["note_ids"]) for c in out} == {("n0", "n1"), ("n2", "n3")}
    assert all(c["source"] == "keywords" and c["reasoning"] == MARK for c in out)
    assert B.keyword_groups(S, [fake(0, "alpha beta"), fake(1, "gamma delta")]) == []  # nothing shared: nothing invented
    assert B.keyword_groups(S, []) == []


def test_a_word_in_most_notes_does_not_make_one_giant_group():
    notes = [fake(i, f"Managers report {w}") for i, w in enumerate(["alpha", "beta", "gamma", "delta", "alpha"])]
    out = B.keyword_groups(S, notes)
    assert [c["note_ids"] for c in out] == [["n0", "n4"]]


def test_a_cluster_made_by_hand_takes_notes_and_survives_a_later_move():
    clusters = [B.new_cluster("A", ["a", "b"], "north"), B.new_cluster("B", ["c", "d"], "north")]
    made = B.add_cluster(S, clusters, ["a", "b", "c", "d", "e"], "Mine", ["b", "e"])
    assert [c["note_ids"] for c in made] == [["a"], ["c", "d"], ["b", "e"]] and made[-1]["source"] == "person"
    empty = B.add_cluster(S, made, ["a", "b", "c", "d", "e"], "Empty")
    moved = B.move_note(empty, ["a", "b", "c", "d", "e"], "c", made[-1]["id"])
    assert [c["name"] for c in moved] == ["A", "B", "Mine", "Empty"]  # only a cluster the move emptied goes
    with pytest.raises(B.BoardError):
        B.add_cluster(S, clusters, ["a"], "  ")
    with pytest.raises(B.BoardError):
        B.add_cluster(S, clusters, ["a"], "X", ["zzz"])


def test_when_the_model_fails_the_board_still_has_marked_clusters_and_can_be_regrouped(tmp_path):
    b = at_board(tmp_path, model=GatherStub(fail=True))
    v = b.group()
    assert v["status"] == "done" and v["grouped_without_north"] is True and v["counts"]["clusters"] >= 1
    assert all(c["source"] == "keywords" and c["reasoning"] == MARK for c in v["clusters"])
    assert v["can_edit"] is True
    b.w.app.state.north_model_factory = lambda plane: GatherStub()  # North comes back
    again = b.group()
    assert again["grouped_without_north"] is False and {c["source"] for c in again["clusters"]} == {"north"}
    assert b.org_call("POST", "/board/group").status_code == 409  # North's own grouping is not redone over edits


def test_with_no_model_set_up_the_fallback_is_used_too(tmp_path):
    b = at_board(tmp_path, model=GatherStub())
    b.w.app.state.north_model_factory = lambda plane: None
    v = b.group()
    assert v["status"] == "done" and v["grouped_without_north"] is True and v["counts"]["clusters"] >= 1


def test_the_organiser_makes_a_cluster_by_hand_and_moves_notes_into_it(tmp_path):
    b = grouped(tmp_path)
    r = b.org_call("POST", "/board/clusters", json={"name": "Our own group"})
    assert r.status_code == 200, r.text
    mine = next(c for c in r.json()["clusters"] if c["name"] == "Our own group")
    assert mine["source"] == "person" and mine["notes"] == []
    lone = r.json()["on_its_own"][0]["id"]
    moved = b.org_call("POST", f"/board/notes/{lone}/move", json={"cluster_id": mine["id"]}).json()
    assert [n["id"] for c in moved["clusters"] if c["id"] == mine["id"] for n in c["notes"]] == [lone]
    with_notes = b.org_call("POST", "/board/clusters", json={"name": "Two", "note_ids": [b.note_ids[0]]}).json()
    assert next(c for c in with_notes["clusters"] if c["name"] == "Two")["note_ids"] == [b.note_ids[0]]


def test_making_a_cluster_is_the_organisers_and_checked_plainly(tmp_path):
    b = grouped(tmp_path)
    assert b.guests[0].call("POST", "/board/clusters", json={"name": "X"}).status_code in (401, 403, 404)
    assert b.org_call("POST", "/board/clusters", json={"nope": 1}).status_code == 400
    assert b.org_call("POST", "/board/clusters", json={"name": "   "}).status_code == 422
    assert b.org_call("POST", "/board/clusters", json={"name": "X", "note_ids": ["nothere"]}).status_code == 422
    assert b.org_call("POST", "/board/clusters", json={"name": "X"}).status_code == 200
    assert at_board(tmp_path / "b").org_call("POST", "/board/clusters", json={"name": "X"}).status_code == 409  # not grouped yet


def test_closing_the_wall_with_no_clusters_groups_the_notes_by_lane_never_a_dead_end(tmp_path):
    """F50 (spec 24, journey 50 step 5): Close the wall never stops at "Group the notes first"; the notes on their own form one group per lane."""
    b = grouped(tmp_path, model=GatherStub(groups={"zzz": "None"}))  # North finds no group
    assert b.board().json()["counts"]["clusters"] == 0
    assert b.org_call("POST", "/together").status_code == 200
    board = b.board().json()
    assert board["counts"]["clusters"] >= 1 and board["counts"]["on_its_own"] == 0


def test_closing_the_wall_before_anyone_grouped_lets_north_group_first(tmp_path):
    b = at_board(tmp_path)
    assert b.board().json()["status"] == "none"
    assert b.org_call("POST", "/together").status_code == 200
    board = b.board().json()
    assert board["status"] == "done" and board["counts"]["clusters"] >= 1  # North grouped them; a note it left alone stays on its own


def test_the_manifest_and_permissions_declare_the_new_route():
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    route = "/api/modules/m1_intent/sessions/{session_id}/board/clusters"
    manifest = yaml.safe_load((root / "modules/m1_intent/manifest.yaml").read_text(encoding="utf-8"))
    assert any(r["method"] == "POST" and r["path"] == route for r in manifest["routes"])
    assert f"POST {route}" in yaml.safe_load((root / "sh_platform/route_permissions.yaml").read_text(encoding="utf-8"))['routes']


# ---- defect 8: prefill and the 422 message
def test_saving_the_problem_inside_fields_says_which_field_is_wrong(tmp_path):
    w = new_world(tmp_path, StubNorth({}))
    org, sid, (ada, _) = flow(w)
    nid = ada.write()
    r = ada.save(nid, fields={"problem": "x"})
    assert r.status_code == 422 and '"problem"' in r.json()['message'] and 'text' in r.json()['message']
    r = ada.save(nid, fields={"colour": "red"})
    assert r.status_code == 422 and '"colour"' in r.json()['message']
    ok = ada.save(nid, text="Renewals slip", fields={"purpose": "Keep customers"})
    assert ok.status_code == 200, ok.text


class Checked:
    """A model that sends each step through the real gateway structure check, then proposes two fields."""
    def complete(self, module_id, messages, tools=None):
        _check_structure({"messages": [encode_turn(m) for m in messages]}, SuppressedFigures())
        return ModelReply(json.dumps({"purpose": "Keep customers", "affected": "Account managers", "belief": "40"}))


class Gate:
    def is_enabled(self, company_id, module_id):
        return True


def test_prefill_works_with_a_stub_model_and_its_message_passes_the_real_gateway_check():
    spec = N.load_fields()
    note = {"id": "x", "text": "Renewals slip every month", "fields": {}, "labels_suggested": [], "history": []}
    proposal = notes_api.prefill_fields(Checked(), Gate(), "co", spec, note)
    assert proposal == {"purpose": "Keep customers", "affected": "Account managers"}  # the belief number is never North's
    done = N.prefill(spec, note, proposal, "now")
    assert done["fields"]["purpose"] == "Keep customers" and "belief" not in done["fields"]
