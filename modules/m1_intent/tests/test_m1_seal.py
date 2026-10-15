"""The seal (D-013, A-053, A-069): a sealed note is a silhouette on the wall and the board unless the viewer is on the
matching restricted area's list; with no matching area it is a silhouette for everyone; an anonymous sealed note names nobody."""
import pytest

from modules.m1_intent.store.board import BoardStore
from modules.m1_intent.store.sessions import SessionStore

from test_m1_board_kit import Board
from sh_platform.profile import Viewer, read, record

LENS = {"mark": "stated", "by": "Lens", "agent": "lens", "from": "Policy sheet"}
SEALED = "A sealed card"
PAY = "Pay for the finance team is not tracked"


def setup(tmp_path, listed=("Test org co-a",), area="Pay"):
    b = Board(tmp_path, notes=())
    plane = b.w.plane("co-a")
    record(plane, "governance.restricted_areas.hr.area", area, LENS)
    record(plane, "governance.restricted_areas.hr.may_see", list(listed), LENS)
    return b, plane


def seal(b, text, **body):
    ada = b.guests[0]
    nid = ada.write(text)
    assert ada.save(nid, restricted=True, **body).status_code == 200
    assert ada.submit(nid).status_code == 200
    b.close_rooms()
    return nid


def notes_of(view):
    return {n["id"]: n for n in [*(x for c in view["clusters"] for x in c["notes"]), *view["on_its_own"]]}


def test_the_seal_is_saved_and_the_author_sees_it_in_the_room(tmp_path):
    b, _ = setup(tmp_path)
    ada = b.guests[0]
    nid = ada.write(PAY)
    assert ada.save(nid, restricted=True).json()["notes"][-1]["restricted"] is True
    assert ada.save(nid, restricted="yes").status_code == 422


def test_a_sealed_note_with_a_matching_area_is_a_silhouette_to_an_outsider_and_whole_to_a_listed_viewer(tmp_path):
    b, plane = setup(tmp_path)
    nid = seal(b, PAY)
    assert notes_of(b.board().json())[nid]["text"] == PAY  # the listed organiser
    out = notes_of(b.board(b.guests[1]).json())[nid]  # a seat holder outside the list
    assert out["text"] == SEALED and out["sealed"] is True and PAY not in str(out)
    assert read(plane, Viewer("Lena Ho", frozenset({"analyst"})))["cards"][nid]["silhouette"] == SEALED
    assert read(plane, Viewer("Test org co-a", frozenset()))["cards"][nid]["q1"]["value"] == PAY


def test_a_sealed_note_with_no_matching_area_is_a_silhouette_for_everyone(tmp_path):
    b, plane = setup(tmp_path, area="Litigation")
    nid = seal(b, PAY)
    for view in (b.board().json(), b.board(b.guests[1]).json(), b.board(b.guests[0]).json()):  # organiser, outsider, the author
        assert notes_of(view)[nid]["text"] == SEALED
    assert read(plane, Viewer("admin co-a", frozenset({"company_admin"})))["cards"][nid]["silhouette"] == SEALED


def test_the_admin_follows_a_069_once_a_person_is_named(tmp_path):
    b, plane = setup(tmp_path, listed=("Tom Ng",))
    nid = seal(b, PAY)
    assert read(plane, Viewer("admin co-a", frozenset({"company_admin"})))["cards"][nid]["silhouette"] == SEALED
    assert notes_of(b.board().json())[nid]["text"] == SEALED  # the organiser is not named either


def test_an_anonymous_sealed_note_returns_no_author_anywhere(tmp_path):
    b, plane = setup(tmp_path)
    nid = seal(b, PAY, anonymous=True)
    for view in (b.board().json(), b.board(b.guests[1]).json()):
        assert "Ada" not in str(view)
    wall = str(read(plane, Viewer("Test org co-a", frozenset({"company_admin"})))["cards"][nid])
    assert "Ada" not in wall and "author" not in wall.replace("anon_key", "")


# ---- every other reader of the board's notes: the words of a sealed note are closed in each
from test_m1_board_kit import GatherStub  # noqa: E402
from modules.m1_intent.domain import board as BD  # noqa: E402
from modules.m1_intent.store.charter import cluster_notes, notes_on_their_own, read_outcome, together_result  # noqa: E402

SEALED_NOTES = ["Capital calls reach us too late to plan the cash", "We learn of capital calls by email days after the due date"]
OPEN_NOTES = ["No single exposure view across the family holdings", "Exposure by name takes a week to put together"]


def sealed_board(tmp_path, sealed=SEALED_NOTES, open_=OPEN_NOTES, one_signer=False, group=True):
    """Two groups; the capital call notes are sealed and no restricted area exists, so they are closed for every reader."""
    b = Board(tmp_path, notes=(), prep={"signers": 1} if one_signer else None)
    for i, text in enumerate([*sealed, *open_]):
        who = b.guests[i % 2]
        nid = who.write(text)
        if text in sealed:
            assert who.save(nid, restricted=True).status_code == 200
        assert who.submit(nid).status_code == 200
    b.close_rooms()
    if group:
        b.group()
    return b


def vote_and_tick(b):
    b.to_together()
    for name in (BD.SEALED_CLUSTER, "No single exposure view"):
        cid = b.cluster(name)["id"]
        for who in b.guests:
            assert who.call("POST", f"/together/clusters/{cid}/vote", json={"option": "must"}).status_code == 200
        assert b.org_call("POST", f"/together/clusters/{cid}/tick", json={"ticked": True}).status_code == 200


def test_a_cluster_of_only_sealed_notes_is_named_a_sealed_cluster_and_a_mixed_one_keeps_its_name(tmp_path):
    b = sealed_board(tmp_path)
    names = {c["name"] for c in b.board().json()["clusters"]}
    assert names == {BD.SEALED_CLUSTER, "No single exposure view"}
    assert "capital" not in str(b.board().json()).lower()
    assert BD.cluster_name("Renewals", [{"sealed": True}, {}]) == "Renewals"


def test_the_together_screen_and_the_summary_close_the_sealed_words(tmp_path):
    b = sealed_board(tmp_path)
    b.to_together()
    assert "capital" not in str(b.org_call("GET", "/together").json()).lower()
    assert "capital" not in str(b.org_call("GET", "/summary").json()).lower()


def test_the_charter_is_drafted_without_the_sealed_words(tmp_path):
    b = sealed_board(tmp_path)
    vote_and_tick(b)
    plane = b.w.plane("co-a")
    assert "capital" not in str(cluster_notes(plane, b.sid)).lower() and "capital" not in str(together_result(plane, b.sid)).lower()
    r = b.org_call("POST", "/charter", json={"confirm": True})
    assert r.status_code == 201, r.text
    assert "capital" not in r.text.lower() and BD.SEALED_CLUSTER in r.text


def test_a_sealed_note_left_on_its_own_is_a_sealed_card_on_the_charter(tmp_path):
    b = sealed_board(tmp_path, sealed=["Capital calls reach us too late to plan the cash"], open_=[], group=False)
    alone = notes_on_their_own(b.w.plane("co-a"), b.sid)
    assert [n["text"] for n in alone] == [BD.SEALED] and "author_name" not in alone[0]


def test_the_export_and_the_hand_off_carry_no_sealed_words(tmp_path):
    b = sealed_board(tmp_path, one_signer=True)
    vote_and_tick(b)
    assert b.org_call("POST", "/charter", json={"confirm": True}).status_code == 201
    assert b.org_call("POST", "/charter/sign").status_code == 200
    files = b.org_call("GET", "/charter/download").json()["files"]
    assert files and all("capital" not in f["content"].lower() for f in files) and any(BD.SEALED_CLUSTER in f["content"] for f in files)
    outcome_id = SessionStore(b.w.plane("co-a")).get(b.sid)["outcome_id"]
    rec = read_outcome(b.w.plane("co-a"), outcome_id)
    assert rec is not None and "capital" not in str(rec).lower() and BD.SEALED_CLUSTER in str(rec)


def test_sealed_notes_never_reach_the_grouping_prompt_and_sit_in_one_sealed_cluster(tmp_path):
    stub = GatherStub()
    b = Board(tmp_path, model=stub, notes=())
    for i, text in enumerate([*SEALED_NOTES, *OPEN_NOTES]):
        who = b.guests[i % 2]
        nid = who.write(text)
        if text in SEALED_NOTES:
            who.save(nid, restricted=True)
        who.submit(nid)
    b.close_rooms()
    view = b.group()
    sent = str([c for c in stub.calls if "Notes to group" in c[1]["content"]]).lower()
    assert sent != "[]" and "exposure" in sent and "capital" not in sent and "email" not in sent
    stored = BoardStore(b.w.plane("co-a")).get(b.sid)["clusters"]
    sealed = [c for c in stored if c["name"] == BD.SEALED_GROUP]
    assert len(sealed) == 1 and len(sealed[0]["note_ids"]) == 2 and view  # the stored name carries no words
