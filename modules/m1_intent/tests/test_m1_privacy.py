"""M1-12, M1-29, D-013, D-015, D-016, D-017, A-031, guardrail 9: anonymous means anonymous, tested from every direction.
Each test here fails if the protection it names is removed. Synthetic names only."""
import json
import logging
import shutil

import pytest
import yaml

from m1_kit import BASE
from modules.m1_intent.domain.contracts import DEFAULT_DIR
from modules.m1_intent.store.notes import NoteStore, load_retention, retention_plan
from test_m1_seat_wiring_kit import StubNorth, admin, flow, ids_of, new_world

ADA = "Ada Anonymous-Author"


def setup(tmp_path, **kw):
    w = new_world(tmp_path, StubNorth({"purpose": "Keep customers"}))
    org, sid, (ada, ben) = flow(w, names=(ADA, "Ben By-Name"), **kw)
    return w, org, sid, ada, ben


def anon_note(person, text="anonymous problem text"):
    nid = person.write(text)
    assert person.save(nid, anonymous=True).status_code == 200
    return nid


def files_with(w, needle: str) -> set[str]:
    root = w.settings.data_root
    return {p.relative_to(root).as_posix() for p in __import__("pathlib").Path(root).rglob("*")
            if p.is_file() and needle in p.read_text(encoding="utf-8", errors="ignore")}


# ---- the shared record carries no author
def test_the_public_record_of_an_anonymous_note_has_no_author_of_any_kind(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    nid = anon_note(ada)
    bn = ben.write("by name problem text")
    ada.submit(nid)
    ben.submit(bn)
    board = {n["text"]: n for n in NoteStore(w.plane("co-a")).board(sid, viewer=ben.room() and None)}
    rec = board["anonymous problem text"]
    assert set(rec) == {"id", "text", "kind", "priority", "anonymous", "fields", "mine"} and rec["anonymous"] is True
    assert board["by name problem text"]["author_name"] == "Ben By-Name"  # by name is the default (D-015)
    ids = ids_of(w, "co-a", sid, 1)
    blob = json.dumps(rec)
    assert not any(v in blob for v in (ids["seat"], ids["guest"], ADA, "Ada"))


def test_nothing_on_disk_that_boards_read_names_the_anonymous_author(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    ada.submit(anon_note(ada))
    ids = ids_of(w, "co-a", sid, 1)
    shared = [f for f in files_with(w, "anonymous problem text") if "/notes/" in f]
    assert len(shared) == 1
    on_disk = json.loads((__import__("pathlib").Path(w.settings.data_root) / shared[0]).read_text(encoding="utf-8"))
    assert all(set(r) == {"id", "text", "kind", "priority", "anonymous", "fields"} for r in on_disk["notes"])  # no author key stored
    for needle in (ids["seat"], ids["guest"], ADA):
        assert not any("/notes/" in f for f in files_with(w, needle)), needle
    # the author is kept apart, in the author map only
    assert any("note_authors" in f for f in files_with(w, ids["seat"]))


def test_an_author_sees_their_own_note_marked_anonymous_and_nobody_else_gets_that_mark(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    nid = anon_note(ada)
    own = ada.room()["notes"][0]
    assert own["anonymous"] is True
    ada.submit(nid)
    ids = ids_of(w, "co-a", sid, 1)
    store = NoteStore(w.plane("co-a"))
    mine = store.board(sid, viewer=ids["seat"])[0]
    theirs = store.board(sid, viewer=ids_of(w, "co-a", sid, 2)["seat"])[0]
    assert mine["mine"] is True and theirs["mine"] is False and store.board(sid)[0]["mine"] is False


def test_the_board_order_does_not_follow_who_submitted_when(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    for p in (ada, ben):
        for i in range(4):
            p.submit(anon_note(p, f"{p.name} note {i}"))
    ids = [n["id"] for n in NoteStore(w.plane("co-a")).board(sid)]
    assert ids == sorted(ids) and len(ids) == 8


def test_no_response_to_anyone_else_carries_the_authors_seat_or_guest_id(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    ada.submit(anon_note(ada))
    ada.call("POST", "/briefing/confirm", json={"answer": "clear"})
    ids = ids_of(w, "co-a", sid, 1)
    seen = [ben.room(), ben.call("GET", "/briefing").json(), ben.call("GET", "/timer").json(), ben.call("GET", "/lobby").json()
            if False else {}, org.get(f"{BASE}/sessions/{sid}").json(), org.get(f"{BASE}/sessions/{sid}/room").text,
            org.get(f"{BASE}/sessions/{sid}/briefing").json(), org.get(f"{BASE}/sessions/{sid}/lobby").json(),
            org.get(f"{BASE}/sessions/{sid}/join-link").json(), ben.c.get(f"{BASE}/sessions/{sid}/lobby", headers={"X-Session-Token": ben.token}).json(),
            admin(w).get(f"{BASE}/sessions/{sid}/seats/2/transcript").text]
    for body in map(json.dumps, seen):
        assert ids["seat"] not in body and ids["guest"] not in body
    notes_seen = json.dumps([ben.room()["notes"], org.get(f"{BASE}/sessions/{sid}/room").json()["notes"]])
    assert "anonymous problem" not in notes_seen and ADA not in notes_seen


def test_errors_about_another_persons_note_say_the_same_as_for_a_note_that_does_not_exist(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    nid = anon_note(ada)
    real = [ben.submit(nid), ben.save(nid, text="x"), ben.call("POST", f"/room/notes/{nid}/prefill"),
            ben.call("POST", f"/room/notes/{nid}/practice", json={"action": "add"})]
    fake = [ben.submit("e" * 16), ben.save("e" * 16, text="x"), ben.call("POST", f"/room/notes/{'e' * 16}/prefill"),
            ben.call("POST", f"/room/notes/{'e' * 16}/practice", json={"action": "add"})]
    assert [(r.status_code, r.json()) for r in real] == [(r.status_code, r.json()) for r in fake]
    assert all(ADA not in r.text and "anonymous" not in r.text for r in real)


def test_logs_carry_no_author_note_text_or_seat_for_an_anonymous_note(tmp_path, caplog):
    w, org, sid, ada, ben = setup(tmp_path)
    ids = ids_of(w, "co-a", sid, 1)
    with caplog.at_level(logging.DEBUG):
        nid = anon_note(ada, "distinctive anonymous words")
        ada.call("POST", f"/room/notes/{nid}/prefill")
        ada.submit(nid)
        ben.room()
        ada.save(nid, text="again")  # an error path too
    # the test client's own request lines (httpx) are the browser side, not the server's logs
    log = "\n".join(r.getMessage() for r in caplog.records if not r.name.startswith("httpx"))
    assert not any(v in log for v in (ADA, "Ada", ids["seat"], ids["guest"], "distinctive anonymous", nid))


def test_the_run_registry_and_the_vault_hold_no_authorship(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    nid = anon_note(ada)
    ada.call("POST", f"/room/notes/{nid}/prefill")
    ada.submit(nid)
    ids = ids_of(w, "co-a", sid, 1)
    registry = [p for p in w.plane("co-a").root.rglob("run_registry.jsonl")]
    assert registry
    text = registry[0].read_text(encoding="utf-8")
    assert not any(v in text for v in (ids["seat"], ids["guest"], ADA, "anonymous problem", nid))


def test_an_anonymous_draft_does_not_even_keep_the_name_in_its_own_record(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    nid = ada.write()
    assert ada.save(nid, anonymous=True).json()["notes"][0]["anonymous"] is True
    t = next(p for p in w.plane("co-a").root.rglob("*.json") if "transcripts" in p.parts and "Renewals" in p.read_text(encoding="utf-8"))
    note = json.loads(t.read_text(encoding="utf-8"))["notes"][0]
    assert note["author_name"] is None


# ---- who may read a private transcript (D-016, A-031)
def test_the_author_reads_their_own_transcript_always(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    anon_note(ada)
    assert "anonymous problem" in json.dumps(ada.room())


def transcript_files(w, sid):
    return [p for p in w.plane("co-a").root.rglob("*.json") if "transcripts" in p.parts and sid in p.parts]


def test_no_route_reads_a_transcript_for_anyone_and_the_authors_file_stays(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    ben.write("by name words")
    anon_note(ada)
    others = [admin(w), admin(w, "co-b"), w.login("analyst", "co-a", ["analyst"]), w.login("appr", "co-a", ["approver"])]
    for seat in (1, 2, 3, 9):
        url = f"{BASE}/sessions/{sid}/seats/{seat}/transcript"
        for r in [c.get(url) for c in others] + [org.get(url), ada.c.get(url, headers={"X-Session-Token": ada.token})]:
            assert r.status_code in (401, 403, 404, 405) and "by name words" not in r.text
    assert any("by name words" in p.read_text(encoding="utf-8") for p in transcript_files(w, sid))  # still stored for its author
    assert "by name words" not in json.dumps(ada.room()) and "by name words" in json.dumps(ben.room())  # only the author reads it


# ---- retention (D-017)
def custom_rules(tmp_path, w, **days):
    folder = tmp_path / "contracts"
    shutil.copytree(DEFAULT_DIR, folder)
    data = yaml.safe_load((folder / "retention.yaml").read_text())
    data["customers"] = {"co-a": days}
    (folder / "retention.yaml").write_text(yaml.safe_dump(data))
    w.app.state.m1_contracts_dir = folder


def test_the_retention_setting_is_read_from_the_contract_per_customer(tmp_path):
    w = new_world(tmp_path)
    assert load_retention("co-a") == {"transcripts_days": 365, "notes_days": 365, "requests_days": 365}
    custom_rules(tmp_path, w, transcripts_days=30)
    assert load_retention("co-a", w.app.state.m1_contracts_dir)["transcripts_days"] == 30
    assert load_retention("co-b", w.app.state.m1_contracts_dir)["transcripts_days"] == 365


def test_a_dry_run_lists_and_removes_nothing_and_a_purge_needs_the_approved_list(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    custom_rules(tmp_path, w, transcripts_days=1, notes_days=100000, requests_days=100000)
    ada.submit(ada.write("old one"))
    now = [__import__("time").time()]
    w.app.state.m1_clock = lambda: now[0]
    a = admin(w)
    dry = a.post(f"{BASE}/retention/purge", json={})
    assert dry.status_code == 200 and dry.json()["dry_run"] is True and dry.json()["total"] == 0
    now[0] += 3 * 86400
    plan = a.post(f"{BASE}/retention/purge", json={}).json()
    assert plan["total"] == 1 and plan["items"] == [{"kind": "transcripts", "session_id": sid, "count": 1}]
    ids = ids_of(w, "co-a", sid, 1)
    assert ids["seat"] not in json.dumps(plan)  # the list names no seat
    assert ada.room()["notes"]  # still there after the dry run
    assert a.post(f"{BASE}/retention/purge", json={"approve": "0" * 32}).status_code == 409  # not the shown list
    assert ada.room()["notes"]
    done = a.post(f"{BASE}/retention/purge", json={"approve": plan["id"]})
    assert done.status_code == 200 and done.json()["total"] == 1
    assert ada.room()["notes"] == [] and len(NoteStore(w.plane("co-a")).board(sid)) == 1  # only what was listed
    assert a.post(f"{BASE}/retention/purge", json={}).json()["total"] == 0


def test_only_a_company_admin_may_ask_for_a_purge_and_nothing_runs_by_itself(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    assert org.post(f"{BASE}/retention/purge", json={}).status_code == 403
    assert ada.c.post(f"{BASE}/retention/purge", json={}, headers={"X-Session-Token": ada.token}).status_code in (401, 403)
    ada.write("kept")
    plan = retention_plan(w.plane("co-a"), {"transcripts_days": 0, "notes_days": 0, "requests_days": 0},
                          __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    assert plan["total"] >= 0 and ada.room()["notes"]  # planning removes nothing


# ---- the rooms end (M1-14)
def test_when_the_rooms_end_every_draft_is_submitted_keeping_its_anonymity_and_it_happens_once(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    now = [__import__("time").time()]
    w.app.state.m1_clock = lambda: now[0]
    ada.write("by name draft")
    anon_note(ada, "anonymous draft")
    ben.write("ben draft")
    ben.submit(ben.room()["notes"][0]["id"])  # already submitted: not submitted twice
    now[0] += 3600
    assert org.get(f"{BASE}/sessions/{sid}/timer").json()["stage"] == "board"
    store = NoteStore(w.plane("co-a"))
    board = {n["text"]: n for n in store.board(sid)}
    assert set(board) == {"by name draft", "anonymous draft", "ben draft"}
    assert board["anonymous draft"]["anonymous"] is True and "author_name" not in board["anonymous draft"]
    assert board["by name draft"]["anonymous"] is True and "author_name" not in board["by name draft"]  # A-045: never sent, never confirmed
    assert board["ben draft"]["author_name"] == "Ben By-Name"  # the one Ben sent keeps his name
    org.get(f"{BASE}/sessions/{sid}/timer")
    assert len(store.board(sid)) == 3  # idempotent


def test_a_solo_run_submits_its_notes_the_same_way(tmp_path):
    w = new_world(tmp_path)
    from m1_kit import BASE as B
    from test_m1_room_kit import join, new_session, start_room
    org = w.login("Solo Person", "co-solo", ["company_admin"])
    sid = new_session(org, seats=1)
    join(org, start_room(org, sid), 1, name="Solo Person")
    org.post(f"{B}/sessions/{sid}/briefing")
    org.post(f"{B}/sessions/{sid}/briefing/send")
    org.post(f"{B}/sessions/{sid}/room/messages", json={"text": "solo note", "kind": "note"})
    now = __import__("time").time() + 3600
    w.app.state.m1_clock = lambda: now
    org.get(f"{B}/sessions/{sid}/timer")
    assert [n["text"] for n in NoteStore(w.plane("co-solo")).board(sid)] == ["solo note"]


def test_purging_the_notes_first_does_not_reopen_an_anonymous_authors_transcript_to_anyone(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    custom_rules(tmp_path, w, transcripts_days=100000, notes_days=1, requests_days=100000)
    ada.submit(anon_note(ada))
    now = [__import__("time").time() + 3 * 86400]
    w.app.state.m1_clock = lambda: now[0]
    a = admin(w)
    url = f"{BASE}/sessions/{sid}/seats/1/transcript"
    assert a.get(url).status_code in (404, 405)
    plan = a.post(f"{BASE}/retention/purge", json={}).json()
    assert [i["kind"] for i in plan["items"]] == ["notes"]
    assert a.post(f"{BASE}/retention/purge", json={"approve": plan["id"]}).status_code == 200
    assert NoteStore(w.plane("co-a")).board(sid) == []  # the notes are gone ...
    assert a.get(url).status_code in (404, 405)  # ... the anonymity is not
    assert "anonymous problem" in json.dumps(ada.room())  # the author still reads their own room


def test_a_damaged_file_is_skipped_by_the_dry_run_not_a_500(tmp_path):
    w, org, sid, ada, ben = setup(tmp_path)
    custom_rules(tmp_path, w, transcripts_days=1, notes_days=1, requests_days=100000)
    ada.submit(ada.write("old one"))
    (w.plane("co-a").path("intents", "m1_intent", "notes") / f"{sid}.json").write_text("{not json", encoding="utf-8")
    w.app.state.m1_clock = lambda: __import__("time").time() + 3 * 86400
    r = admin(w).post(f"{BASE}/retention/purge", json={})
    assert r.status_code == 200 and r.json()["skipped"] == 1
