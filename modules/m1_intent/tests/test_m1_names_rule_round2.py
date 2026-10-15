"""The organiser's names rule, second round: board comments, a named close, templates, the charter's own view."""
import json

import pytest

from m1_kit import BASE
from modules.m1_intent.store.notes import NoteStore
from test_m1_board_kit import NOTES, at_board, together
from test_m1_charter_kit import charter, draft, ready, stand_in_result  # noqa: F401  (the autouse fixture)
from test_m1_names_rule import room_with
from test_m1_notes import world
from test_m1_room_kit import new_session


def _comment(who, cid, anon):
    return who.call("POST", f"/together/clusters/{cid}/comments", json={"text": "Put this first", "anonymous": anon})


def _notes(names):
    return [(t, names == "anonymous") for t, _ in NOTES]


@pytest.mark.parametrize("names,ok,bad", [("anonymous", True, False), ("named", False, True)])
def test_a_comment_follows_the_names_rule(tmp_path, names, ok, bad):
    b = together(tmp_path, prep={"names": names}, notes=_notes(names))
    ada = b.guests[0]
    cid = b.cluster("Calls arrive too late")["id"]
    refused = _comment(ada, cid, bad)
    assert refused.status_code == 409 and refused.json()["error"] == "names_rule"
    assert _comment(ada, cid, ok).status_code == 200
    assert _comment(ada, cid, None).status_code == 200  # no choice follows the rule
    view = ada.call("GET", "/together").json()
    assert view["names"] == names
    rows = next(c for c in view["clusters"] if c["id"] == cid)["comments"]
    assert len(rows) == 2 and all(r["anonymous"] is (names == "anonymous") for r in rows)
    assert all(("author_name" in r) is (names == "named") for r in rows)  # never a name in anonymous mode


def test_a_choice_session_still_lets_each_comment_choose(tmp_path):
    b = together(tmp_path)
    cid = b.cluster("Calls arrive too late")["id"]
    assert _comment(b.guests[0], cid, True).status_code == 200 and _comment(b.guests[0], cid, False).status_code == 200
    assert b.guests[0].call("GET", "/together").json()["names"] == "choice"


@pytest.mark.parametrize("names", ["named", "anonymous"])
def test_the_board_shows_the_authors_in_named_mode_and_never_in_anonymous(tmp_path, names):
    b = at_board(tmp_path, prep={"names": names}, notes=_notes(names))
    text = b.board().text
    assert ("Ada Guest" in text) is (names == "named") and ("Ben Guest" in text) is (names == "named")


def test_a_draft_without_a_kept_name_is_never_given_one_at_a_named_close(tmp_path):
    from modules.m1_intent.store.notes import submit_drafts
    from modules.m1_intent.store.transcripts import TranscriptStore
    from test_m1_seat_wiring_kit import ids_of
    w = world(tmp_path)
    org, sid, (ada, _) = room_with(w, "named")
    plane, seat = w.plane("co-a"), ids_of(w, "co-a", sid, 1)["seat"]
    ada.write("Old draft")
    TranscriptStore(plane).update(sid, seat, lambda t: t["notes"][0].update(anonymous=True, author_name=None))
    submit_drafts(plane, sid, seat, rooms_end=True)
    [rec] = NoteStore(plane).board(sid)
    assert rec["anonymous"] is True and not rec.get("author_name")  # left anonymous rather than named with no name


def test_a_session_made_from_a_template_does_not_inherit_the_names_rule(tmp_path):
    w = world(tmp_path)
    org = w.login("org tpl", "co-a", ["sponsor"])
    sid = new_session(org, names="anonymous")
    made = org.post(f"{BASE}/templates", json={"name": "T", "session_id": sid})
    assert made.status_code == 201, made.text
    tid = made.json()["id"]
    r = org.post(f"{BASE}/sessions", json={"from_template": tid})
    assert r.status_code == 201 and r.json()["preparation"]["names"] == "choice"
    r = org.post(f"{BASE}/sessions", json={"from_template": tid, "names": "named"})
    assert r.json()["preparation"]["names"] == "named"


@pytest.mark.parametrize("names", ["named", "anonymous", "choice"])
def test_the_charter_view_carries_no_note_author_in_any_mode(world, names):
    org, sid, _ = ready(world, names=names)
    draft(org, sid)
    assert "author" not in json.dumps(charter(org, sid)).lower()
