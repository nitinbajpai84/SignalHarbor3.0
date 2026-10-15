"""M1-17 the board appears when the rooms close, M1-18 North's clusters, M1-19 manual edits (domain and API), with the
anonymity rules of M1-P05. Stub North, synthetic family-office notes, no live call."""
import json
import random
from pathlib import Path

import pytest

from m1_kit import BASE
from modules.m1_intent.domain import board as B
from test_m1_board_kit import GROUPS, NOTES, Board, GatherStub, at_board, grouped
from test_m1_seat_wiring_kit import admin

S = B.load_settings()
ADA = "Ada Guest"


def ids(n):
    return [f"note{i}" for i in range(n)]


# ---- domain: North's groups made safe (ported from the earlier gather tests: every note in exactly one place)
def test_every_note_is_in_exactly_one_group_or_on_its_own():
    note_ids = ids(6)
    groups = [{"name": "A", "note_ids": ["note0", "note1"]}, {"name": "B", "note_ids": ["note1", "note2", "note9"]}]
    clusters = B.apply_grouping(S, note_ids, groups, set())
    placed = [n for c in clusters for n in c["note_ids"]]
    assert len(placed) == len(set(placed)) and set(placed) <= set(note_ids)  # no repeat, nothing invented
    assert [c["note_ids"] for c in clusters] == [["note0", "note1"]]          # B was left with one note: it dissolves
    view = B.view(clusters, [{"id": n, "text": n, "anonymous": False} for n in note_ids])
    assert sorted(x["id"] for x in view["on_its_own"]) == ["note2", "note3", "note4", "note5"]  # none dropped


def test_a_pack_problem_id_north_was_not_given_is_dropped_and_a_bad_name_gets_the_default():
    groups = [{"name": "A", "note_ids": ["note0", "note1"], "pack_problem_id": "P-9"},
              {"name": "   ", "note_ids": ["note2", "note3"], "pack_problem_id": "P-1"}]
    a, b = B.apply_grouping(S, ids(4), groups, {"P-1"})
    assert a["pack_problem_id"] is None and b["pack_problem_id"] == "P-1" and b["name"] == S.default_name


def test_no_note_is_ever_lost_whatever_the_edits():
    rng, note_ids = random.Random(7), ids(12)
    clusters = B.apply_grouping(S, note_ids, [{"name": f"G{i}", "note_ids": note_ids[i * 3:i * 3 + 3]} for i in range(3)], set())
    for _ in range(200):
        pick = rng.choice(["move", "own", "split"])
        c = rng.choice(clusters) if clusters else None
        try:
            if pick == "move" and clusters:
                clusters = B.move_note(clusters, note_ids, rng.choice(note_ids), rng.choice(clusters)["id"])
            elif pick == "own":
                clusters = B.move_note(clusters, note_ids, rng.choice(note_ids), None)
            elif c:
                clusters = B.split(S, clusters, c["id"], c["note_ids"][:1])
        except B.BoardError:
            pass
        view = B.view(clusters, [{"id": n, "text": n, "anonymous": False} for n in note_ids])
        seen = [n for c in view["clusters"] for n in c["note_ids"]] + [n["id"] for n in view["on_its_own"]]
        assert sorted(seen) == sorted(note_ids)


def test_rename_and_split_follow_the_rules():
    [c] = B.apply_grouping(S, ids(3), [{"name": "A", "note_ids": ids(3)}], set())
    assert B.rename(S, [c], c["id"], "  Calls   too late ")[0]["name"] == "Calls too late"
    for bad in ("", "x" * (S.name_chars + 1), 5, None):
        with pytest.raises(B.BoardError):
            B.rename(S, [c], c["id"], bad)
    out = B.split(S, [c], c["id"], ["note1"])
    assert [x["note_ids"] for x in out] == [["note0", "note2"], ["note1"]] and out[1]["name"].endswith(S.split_suffix)
    for bad in ([], ["note0", "note1", "note2"], ["nope"], "note1"):
        with pytest.raises(B.BoardError):
            B.split(S, [c], c["id"], bad)


# ---- API: nothing shows while the rooms are open; the organiser sees counts only (deck slide 14)
def test_while_the_rooms_are_open_the_board_is_refused_and_the_organiser_sees_counts_only(tmp_path):
    b = Board(tmp_path)
    for who in (b.org_call("GET", "/board"), b.guests[0].call("GET", "/board")):
        assert who.status_code == 409 and "close" in who.json()["message"]
    nid = b.guests[0].write("A draft that is not submitted yet")  # a draft: counted, never shown
    c = b.org_call("GET", "/board/counts")
    assert c.status_code == 200 and c.json() == {"stage": "private_rooms", "submitted": len(NOTES), "drafts": 1, "people_with_drafts": 1}
    assert not any(t in c.text for t, _ in NOTES) and nid not in c.text and "draft that" not in c.text
    assert b.guests[0].call("GET", "/board/counts").status_code in (401, 403, 404)  # the organiser's, not a guest's


def test_closing_the_rooms_puts_every_submitted_note_on_the_board_including_late_drafts(tmp_path):
    b = Board(tmp_path)
    b.guests[1].write("A late draft about manager fees that was never submitted")
    assert b.guests[0].call("POST", "/rooms/close").status_code in (401, 403, 404)  # only the organiser closes
    b.close_rooms()
    v = b.org_call("GET", "/board").json()
    assert v["stage"] == "board" and v["status"] == "none" and v["counts"]["notes"] == len(NOTES) + 1
    assert len(v["on_its_own"]) == len(NOTES) + 1 and v["clusters"] == []  # raw first, before North has grouped
    assert b.org_call("POST", "/rooms/close").status_code == 409  # not twice


def test_a_participant_reads_the_board_once_the_rooms_have_closed(tmp_path):
    b = grouped(tmp_path)
    r = b.guests[1].call("GET", "/board")
    assert r.status_code == 200 and r.json()["organiser"] is False and r.json()["can_edit"] is False
    assert {n["text"] for n in r.json()["on_its_own"]} | {n["text"] for c in r.json()["clusters"] for n in c["notes"]} == {t for t, _ in NOTES}


# ---- North's grouping (M1-18)
def test_north_groups_into_named_clusters_and_a_note_that_fits_nowhere_stays_on_its_own(tmp_path):
    b = at_board(tmp_path)
    v = b.group()
    assert v["status"] == "done" and sorted(c["name"] for c in v["clusters"]) == sorted(GROUPS.values())
    assert [len(c["notes"]) for c in sorted(v["clusters"], key=lambda c: c["name"])] == [2, 3]
    assert [n["text"] for n in v["on_its_own"]] == [t for t, _ in NOTES if "fee" in t.lower()]
    assert v["counts"] == {"notes": 6, "clusters": 2, "on_its_own": 1}
    seen = [n["id"] for c in v["clusters"] for n in c["notes"]] + [n["id"] for n in v["on_its_own"]]
    assert sorted(seen) == sorted(b.note_ids)  # every note exactly once


def test_a_failed_model_call_groups_by_keywords_marked_for_checking_and_can_be_tried_again(tmp_path):
    stub = GatherStub(fail=True)
    b = at_board(tmp_path, model=stub)
    v = b.group()
    assert v["status"] == "done" and v["grouped_without_north"] is True and v["clusters"]
    assert all(c["source"] == "keywords" for c in v["clusters"])
    stub.fail = False
    again = b.group()
    assert again["status"] == "done" and again["grouped_without_north"] is False


@pytest.mark.parametrize("reply", ["not json at all", '{"groups": "nope"}', "```json\n{broken\n```"])
def test_an_unreadable_reply_falls_back_to_keywords_not_a_crash(tmp_path, reply):
    b = at_board(tmp_path, model=GatherStub(reply=reply))
    v = b.group()
    assert v["status"] == "done" and v["grouped_without_north"] is True and v["clusters"]


def test_no_model_set_up_groups_by_keywords(tmp_path):
    b = at_board(tmp_path)
    b.w.app.state.north_model_factory = None
    b.w.app.state.model_env = {}
    v = b.group()
    assert v["status"] == "done" and v["grouped_without_north"] is True and v["clusters"]


def test_a_model_inventing_notes_and_repeating_one_changes_nothing_real(tmp_path):
    reply = json.dumps({"groups": [{"name": "Calls", "note_ids": ["n1", "n1", "n2", "n99", "x"]}]})
    b = at_board(tmp_path, model=GatherStub(reply="```json\n" + reply + "\n```"))
    v = b.group()
    assert len(v["clusters"]) == 1 and len(v["clusters"][0]["notes"]) == 2
    assert v["counts"]["on_its_own"] == len(NOTES) - 2


def test_grouping_runs_once_then_restoring_north_grouping_undoes_edits(tmp_path):
    b = grouped(tmp_path)
    assert b.org_call("POST", "/board/group").status_code == 409  # already grouped: edits are not thrown away by accident
    calls = len(b.w.app.state.north_model_factory(None).calls)
    c = b.cluster("Calls arrive too late")
    assert b.org_call("GET", "/board").json()["edited"] is False
    b.org_call("POST", f"/board/clusters/{c['id']}/rename", json={"name": "Late capital calls"})
    assert b.cluster("Late capital calls") and b.org_call("GET", "/board").json()["edited"] is True
    v = b.org_call("POST", "/board/restore").json()
    assert sorted(x["name"] for x in v["clusters"]) == sorted(GROUPS.values()) and v["edited"] is False
    assert calls == len(b.w.app.state.north_model_factory(None).calls)  # restoring is not a new model call


def test_the_grouping_is_only_for_the_organiser_and_only_after_the_rooms_close(tmp_path):
    b = Board(tmp_path)
    assert b.org_call("POST", "/board/group").status_code == 409
    b.close_rooms()
    assert b.guests[0].call("POST", "/board/group").status_code in (401, 403, 404)
    assert b.org_call("POST", "/board/restore").status_code == 409  # nothing to restore yet


def test_an_empty_board_is_an_honest_empty_state_and_makes_no_model_call(tmp_path):
    stub = GatherStub()
    b = Board(tmp_path, model=stub, notes=[])
    b.close_rooms()
    v = b.group()
    assert v["status"] == "done" and v["counts"] == {"notes": 0, "clusters": 0, "on_its_own": 0}
    assert not any("Notes to group" in c[1]["content"] for c in stub.calls)


# ---- manual edits (M1-19)
def test_the_organiser_can_move_a_note_rename_a_cluster_and_split_one_and_every_edit_records_who(tmp_path):
    b = grouped(tmp_path)
    late, expo = b.cluster("Calls arrive too late"), b.cluster("No single exposure view")
    fee = next(n for n in b.org_call("GET", "/board").json()["on_its_own"])
    v = b.org_call("POST", f"/board/notes/{fee['id']}/move", json={"cluster_id": late["id"]}).json()
    assert v["counts"]["on_its_own"] == 0 and len(next(c for c in v["clusters"] if c["id"] == late["id"])["notes"]) == 3
    v = b.org_call("POST", f"/board/clusters/{expo['id']}/rename", json={"name": "Exposure in one view"}).json()
    assert [c["name"] for c in v["clusters"] if c["id"] == expo["id"]] == ["Exposure in one view"]
    two = [n["id"] for n in next(c for c in v["clusters"] if c["id"] == expo["id"])["notes"]][:2]
    v = b.org_call("POST", f"/board/clusters/{expo['id']}/split", json={"note_ids": two, "name": "Exposure by name"}).json()
    assert v["counts"]["clusters"] == 3 and sorted(len(c["notes"]) for c in v["clusters"]) == [1, 2, 3]
    v = b.org_call("POST", f"/board/notes/{fee['id']}/move", json={"cluster_id": None}).json()  # back on its own
    assert v["counts"]["on_its_own"] == 1
    log = json.loads(next(Path(b.w.settings.data_root).rglob("board/*.json")).read_text(encoding="utf-8"))["edits"]
    assert [e["kind"] for e in log] == ["move", "rename", "split", "move"] and all(e["by"] for e in log)


def test_edits_refuse_what_cannot_be_done_in_plain_words(tmp_path):
    b = grouped(tmp_path)
    c = b.cluster("Calls arrive too late")
    for path, body in [(f"/board/notes/{b.note_ids[0]}/move", {"cluster_id": "0" * 16}), (f"/board/notes/nope/move", {"cluster_id": None}),
                       (f"/board/clusters/{c['id']}/rename", {"name": ""}), (f"/board/clusters/{c['id']}/split", {"note_ids": []}),
                       (f"/board/clusters/{c['id']}/split", {"note_ids": [n["id"] for n in c["notes"]]})]:
        r = b.org_call("POST", path, json=body)
        assert r.status_code == 422 and r.json()["message"] and "Traceback" not in r.text, path
    assert b.org_call("POST", f"/board/clusters/{c['id']}/rename", json={"nom": "x"}).status_code == 400
    assert b.org_call("POST", f"/board/notes/{b.note_ids[0]}/move", json={}).status_code == 400


def test_a_guest_cannot_edit_the_board(tmp_path):
    b = grouped(tmp_path)
    c = b.cluster("Calls arrive too late")
    g = b.guests[0]
    for method, path, body in [("POST", f"/board/clusters/{c['id']}/rename", {"name": "x"}), ("POST", "/board/restore", None),
                               ("POST", f"/board/notes/{b.note_ids[0]}/move", {"cluster_id": None})]:
        assert g.call(method, path, **({"json": body} if body else {})).status_code in (401, 403, 404), path


def test_the_board_cannot_be_edited_once_the_room_is_signing(tmp_path):
    b = grouped(tmp_path)
    c = b.cluster("Calls arrive too late")
    assert b.org.post(f"{BASE}/sessions/{b.sid}/together").status_code == 200
    assert b.org_call("POST", f"/board/clusters/{c['id']}/rename", json={"name": "Still allowed together"}).status_code == 200
    from modules.m1_intent.store.sessions import SessionStore
    SessionStore(b.w.plane("co-a")).transition(b.sid, "signing")
    r = b.org_call("POST", f"/board/clusters/{c['id']}/rename", json={"name": "Too late now"})
    assert r.status_code == 409


# ---- anonymity (D-016, M1-12): the board uses the public note record only
def test_an_anonymous_note_has_no_author_anywhere_on_the_board(tmp_path):
    b = grouped(tmp_path)
    anon = [t for t, a in NOTES if a]
    c = b.cluster("Calls arrive too late")
    a_note = next(n for n in c["notes"] if n["text"] in anon)
    b.org_call("POST", f"/board/notes/{a_note['id']}/move", json={"cluster_id": None})  # editing keeps it hidden too
    answers = [b.org_call("GET", "/board").text, b.guests[0].call("GET", "/board").text, b.guests[1].call("GET", "/board").text,
               b.org_call("GET", "/board/counts").text]
    people = ("Ada Guest", "Ben Guest", "Ada", "Ben")
    for text in answers[:3]:
        for note in [n for c in json.loads(text)["clusters"] for n in c["notes"]] + json.loads(text)["on_its_own"]:
            assert (note["anonymous"] is True) == (note["text"] in anon)
            if note["anonymous"]:
                assert set(note) <= {"id", "text", "kind", "anonymous", "mine"}  # no author key of any kind
    # nothing the board stores names a person or holds a note's words
    for f in Path(b.w.settings.data_root).rglob("board/*.json"):
        blob = f.read_text(encoding="utf-8")
        assert not any(p in blob for p in people) and not any(t in blob for t, _ in NOTES), f.name


def test_only_the_author_sees_their_own_anonymous_note_marked_mine(tmp_path):
    b = grouped(tmp_path)
    mine = {n["text"] for c in b.guests[0].call("GET", "/board").json()["clusters"] for n in c["notes"] if n["mine"]}
    theirs = {n["text"] for c in b.guests[1].call("GET", "/board").json()["clusters"] for n in c["notes"] if n["mine"]}
    assert mine and theirs and not mine & theirs
    assert not any(n["mine"] for c in b.org_call("GET", "/board").json()["clusters"] for n in c["notes"])


# ---- who may see what, and other companies
def test_another_session_or_company_gets_nothing(tmp_path):
    b = grouped(tmp_path)
    other = admin(b.w, "co-b")
    assert other.get(b.url("/board")).status_code in (403, 404)
    outsider = b.w.login("second organiser", "co-a", ["sponsor"])  # another organiser of the same company: not this session's
    assert outsider.get(b.url("/board")).status_code in (403, 404)
    assert outsider.post(b.url("/board/group")).status_code in (403, 404)


def test_a_company_without_the_module_is_refused(tmp_path):
    b = Board(tmp_path)
    off = b.w.login("off person", "co-off", ["company_admin"])
    assert off.get(f"{BASE}/sessions/{b.sid}/board").status_code in (403, 404)


# ---- two industries, an empty company and one person working alone
@pytest.mark.parametrize("company", ["co-a", "co-b", "co-none"])
def test_the_board_works_for_two_industries_and_a_company_with_no_pack(tmp_path, company):
    b = grouped(tmp_path, company=company)
    assert b.org_call("GET", "/board").json()["counts"]["clusters"] == 2


def test_an_empty_company_and_one_person_working_alone(tmp_path):
    b = Board(tmp_path, company="co-solo", seats=1, names=(), notes=[])
    org = b.org
    assert org.get(b.url("/board")).status_code == 409  # rooms still open
    nid = org.post(b.url("/room/messages"), json={"text": "Capital calls reach us too late", "kind": "note"}).json()["notes"][-1]["id"]
    assert org.post(b.url(f"/room/notes/{nid}/submit")).status_code == 200
    b.close_rooms()
    v = b.group()
    assert v["counts"] == {"notes": 1, "clusters": 0, "on_its_own": 1}  # a lone note is on its own, not a cluster of one
    assert b.org_call("GET", "/board/counts").json()["submitted"] == 1
