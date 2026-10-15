"""M1-24 charter draft, M1-25 sign in the room, M1-27 versions, rule 7 (signed is read-only, a draft keeps a human edit).
Ported in spirit from the earlier product's tests/test_gates.py (per-part sign-off, the same person cannot sign twice,
a reject is recorded and the part stays open), reshaped to one charter with signers and the file stores."""
import pytest

from m1_kit import BASE
from modules.m1_intent.store.charter import CharterStore
from modules.m1_intent.store.room import RoomStore
from test_m1_charter_kit import stand_in_result  # noqa: F401  (autouse: the fixture together-result)
from test_m1_charter_kit import (CLUSTERS, approver_post, charter, draft, put_raw, put_result, ready, second_signer, send_up,
                                 to_together)
from test_m1_room_kit import guest, hdr, new_session, start_room


def test_draft_lists_ticked_problems_by_priority_and_the_footer(world):
    org, sid, _ = ready(world, taken=2)
    got = draft(org, sid)["charter"]
    assert [p["title"] for p in got["problems"]] == ["Capital calls arrive too late", "No single exposure view", "Nobody owns the manager fee list"]
    assert [p["priority_label"] for p in got["problems"]] == ["Must", "Should", None]  # no vote: no priority, never invented
    assert [p["note_count"] for p in got["problems"]] == [6, 5, 2]
    assert got["problems"][0]["so_that"] == "funding is planned, not found" and got["problems"][1]["so_that"] is None
    assert got["later"] == [{"id": "c4", "title": "Reporting is monthly only"}]
    f = got["footer"]
    assert (f["participants"], f["notes"], f["later"]) == (2, 14, 1)   # seats taken, all notes (also the unticked), left for later
    assert got["status"] == "draft" and got["version"] == 1 and got["signing"]["signed"] == 0 and got["signing"]["needed"] == 2
    assert org.get(f"{BASE}/sessions/{sid}").json()["state"] == "signing"


def test_the_short_template_shows_fewer_columns(world):
    org, sid, _ = ready(world, charter_template="short")
    t = draft(org, sid)["charter"]["template"]
    assert t["id"] == "short" and t["columns"] == ["problem", "priority"]


def test_no_result_yet_is_an_honest_state_not_an_invented_charter(world):
    org, sid, _ = ready(world, result=False)
    page = charter(org, sid)
    assert page["charter"] is None and page["can_draft"] is False and page["no_result"] is True
    r = org.post(f"{BASE}/sessions/{sid}/charter", json={"confirm": True})
    assert r.status_code == 409 and r.json()["error"] == "no_result"


@pytest.mark.parametrize("bad", [{"clusters": [{"id": "c1"}]}, {"clusters": "x"}, {"nope": 1},
                                 {"clusters": [{**CLUSTERS[0], "priority": "urgent"}]},
                                 {"clusters": [{**CLUSTERS[0], "note_count": -1}]},
                                 {"clusters": [CLUSTERS[0], CLUSTERS[0]]}])
def test_a_result_in_the_wrong_shape_is_refused_not_guessed(world, bad):
    org, sid, _ = ready(world, result=False)
    put_raw(world, "co-a", sid, bad)
    r = org.post(f"{BASE}/sessions/{sid}/charter", json={"confirm": True})
    assert r.status_code == 409 and r.json()["error"] == "no_result"
    assert org.get(f"{BASE}/sessions/{sid}").json()["state"] == "together"


def test_only_the_together_stage_drafts_and_only_once(world):
    org, sid, _ = ready(world)
    draft(org, sid)
    assert org.post(f"{BASE}/sessions/{sid}/charter", json={"confirm": True}).status_code == 409      # already has a draft
    early = new_session(org)                                                  # a draft session has not reached the room's result
    assert org.post(f"{BASE}/sessions/{early}/charter").status_code == 409


def test_only_the_organiser_drafts_edits_and_sends(world):
    org, sid, code = ready(world)
    other = second_signer(world, "co-a", code, "sponsor")
    assert other.post(f"{BASE}/sessions/{sid}/charter").status_code == 404
    draft(org, sid)
    assert other.put(f"{BASE}/sessions/{sid}/charter", json={"so_that": {"c2": "x"}}).status_code == 404
    assert other.post(f"{BASE}/sessions/{sid}/charter/send").status_code == 404
    assert other.get(f"{BASE}/sessions/{sid}/charter").status_code == 200   # a seated person may read it


def test_the_purpose_lines_can_be_edited_while_it_is_a_draft(world):
    org, sid, _ = ready(world)
    draft(org, sid)
    r = org.put(f"{BASE}/sessions/{sid}/charter", json={"so_that": {"c2": "concentration is seen early", "c1": ""}})
    assert r.status_code == 200
    p = {x["id"]: x for x in r.json()["charter"]["problems"]}
    assert p["c2"]["so_that"] == "So that concentration is seen early." and p["c2"]["so_that_edited"] is True
    assert p["c1"]["so_that"] is None
    assert org.put(f"{BASE}/sessions/{sid}/charter", json={"so_that": {"nope": "x"}}).status_code == 422
    assert org.put(f"{BASE}/sessions/{sid}/charter", json={"so_that": {"c2": "x" * 5000}}).status_code == 422
    assert org.put(f"{BASE}/sessions/{sid}/charter", json={"so_that": "x"}).status_code == 422
    assert org.put(f"{BASE}/sessions/{sid}/charter", json={"other": 1}).status_code == 400


# ---- M1-25: signing in the room
def test_signers_0_of_2_then_1_then_signed_and_the_same_person_cannot_sign_twice(world):
    org, sid, code = ready(world)
    assert draft(org, sid)["charter"]["signing"]["signed"] == 0
    first = org.post(f"{BASE}/sessions/{sid}/charter/sign").json()["charter"]
    assert first["status"] == "draft" and first["signing"]["signed"] == 1 and first["signing"]["i_signed"] is True
    again = org.post(f"{BASE}/sessions/{sid}/charter/sign")
    assert again.status_code == 409 and again.json()["error"] == "already_signed"
    assert org.get(f"{BASE}/sessions/{sid}").json()["state"] == "signing"
    two = second_signer(world, "co-a", code)
    done = two.post(f"{BASE}/sessions/{sid}/charter/sign").json()["charter"]
    assert done["status"] == "signed" and done["signing"]["signed"] == 2
    assert [x["how"] for x in done["signing"]["signers"]] == ["room", "room"]
    assert org.get(f"{BASE}/sessions/{sid}").json()["state"] == "closed"


def test_a_solo_session_is_signed_by_its_one_owner(world):
    org, sid, _ = ready(world, seats=1)
    assert draft(org, sid)["charter"]["signing"]["needed"] == 1
    done = org.post(f"{BASE}/sessions/{sid}/charter/sign").json()["charter"]
    assert done["status"] == "signed" and done["handed_on"] is True


@pytest.mark.parametrize("company", ["co-a", "co-b", "co-none"])
def test_the_whole_flow_works_for_two_industries_and_a_company_with_no_pack(world, company):
    org, sid, _ = ready(world, company=company, seats=1)
    draft(org, sid)
    assert org.post(f"{BASE}/sessions/{sid}/charter/sign").json()["charter"]["status"] == "signed"


def test_a_role_that_may_not_sign_is_refused(world):
    org, sid, code = ready(world)
    draft(org, sid)
    analyst = second_signer(world, "co-a", code, "analyst")
    assert analyst.post(f"{BASE}/sessions/{sid}/charter/sign").status_code == 403
    assert charter(org, sid)["charter"]["signing"]["signed"] == 0


def test_a_signer_of_the_company_needs_no_seat_to_read_or_sign(world):
    org, sid, _ = ready(world)
    draft(org, sid)
    sponsor = world.login("stranger", "co-a", ["sponsor"])      # no seat in the room
    page = sponsor.get(f"{BASE}/sessions/{sid}/charter")
    assert page.status_code == 200 and page.json()["charter"]["signing"]["can_sign"] is True
    assert sponsor.put(f"{BASE}/sessions/{sid}/charter", json={"so_that": {"c1": "x"}}).status_code == 404  # editing stays the organiser's
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    done = sponsor.post(f"{BASE}/sessions/{sid}/charter/sign").json()["charter"]
    assert done["status"] == "signed" and done["signing"]["signed"] == 2
    assert sponsor.post(f"{BASE}/sessions/{sid}/charter/sign").status_code == 404   # signed and handed on: the session is closed


def test_one_signature_per_person_even_without_a_seat(world):
    org, sid, _ = ready(world, seats=3)
    draft(org, sid)
    admin = world.login("admin2", "co-a", ["company_admin"])
    assert admin.post(f"{BASE}/sessions/{sid}/charter/sign").status_code == 200
    again = admin.post(f"{BASE}/sessions/{sid}/charter/sign")
    assert again.status_code == 409 and again.json()["error"] == "already_signed"
    assert charter(org, sid)["charter"]["signing"]["signed"] == 1


def test_a_revoked_seat_does_not_stop_a_signer_signing(world):
    org, sid, code = ready(world)
    sponsor = second_signer(world, "co-a", code, "sponsor")     # takes seat 2 with their account
    draft(org, sid)
    RoomStore(world.plane("co-a")).revoke(sid, org.account_id, 2)
    assert RoomStore(world.plane("co-a")).seat_of_account(sid, sponsor.account_id) is None
    r = sponsor.post(f"{BASE}/sessions/{sid}/charter/sign")
    assert r.status_code == 200 and r.json()["charter"]["signing"]["signed"] == 1


def test_a_person_without_a_signing_role_and_without_a_seat_still_reaches_nothing(world):
    org, sid, _ = ready(world)
    draft(org, sid)
    analyst = world.login("analyst", "co-a", ["analyst"])
    assert analyst.get(f"{BASE}/sessions/{sid}/charter").status_code == 404
    assert analyst.post(f"{BASE}/sessions/{sid}/charter/sign").status_code in (403, 404)


def test_another_company_and_a_company_without_the_module_reach_nothing(world):
    org, sid, _ = ready(world)
    draft(org, sid)
    other = world.login("other", "co-b", ["company_admin"])
    off = world.login("off", "co-off", ["company_admin"])
    for c in (other, off):
        for verb, path in [("get", ""), ("post", ""), ("post", "/sign"), ("post", "/send"), ("post", "/withdraw")]:
            assert getattr(c, verb)(f"{BASE}/sessions/{sid}/charter{path}").status_code in (403, 404), (verb, path)
    assert charter(org, sid)["charter"]["signing"]["signed"] == 0


def test_a_guest_with_only_a_join_token_reaches_none_of_it(world):
    org = world.login("org", "co-a", ["company_admin"])
    sid = new_session(org, seats=2, approver_name="Someone")
    start_room(org, sid)
    _, token = RoomStore(world.plane("co-a")).take(sid, 1, "Guest", "Planning lead", None)
    to_together(world, "co-a", sid)
    put_result(world, "co-a", sid)
    draft(org, sid)
    g = guest(world)
    seated = g.get(f"{BASE}/sessions/{sid}/charter", headers=hdr(token))  # a seated guest reads it, read-only
    assert seated.status_code == 200 and seated.json()["charter"]["signing"]["can_sign"] is False
    for verb, path in [("post", ""), ("post", "/sign"), ("post", "/send"), ("put", "")]:
        kw = {"json": {}} if verb == "put" else {}
        r = getattr(g, verb)(f"{BASE}/sessions/{sid}/charter{path}", headers=hdr(token), **kw)
        assert r.status_code in (401, 403), (verb, path, r.status_code)


# ---- rule 7: signed means read-only
def test_a_signed_charter_is_read_only(world):
    org, sid, _ = ready(world, seats=1)
    draft(org, sid)
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    assert org.put(f"{BASE}/sessions/{sid}/charter", json={"so_that": {"c2": "changed"}}).status_code in (404, 409)
    assert org.post(f"{BASE}/sessions/{sid}/charter/sign").status_code in (404, 409)
    assert org.post(f"{BASE}/sessions/{sid}/charter/send").status_code in (404, 409)
    assert org.post(f"{BASE}/sessions/{sid}/charter", json={"confirm": True}).status_code == 409
    got = charter(org, sid)["charter"]
    assert got["editable"] is False and got["status"] == "signed"
    assert got["problems"][1]["so_that"] is None            # nothing changed


def test_the_store_itself_refuses_to_change_a_signed_version(world):
    from modules.m1_intent.domain import charter as C
    org, sid, _ = ready(world, seats=1)
    draft(org, sid)
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    settings = C.load_charter_settings()
    signed = CharterStore(world.plane("co-a")).read(sid)["versions"][-1]
    with pytest.raises(C.CharterError):
        C.edit_purposes(signed, {"c2": "x"}, settings, "someone", "now")
    with pytest.raises(C.CharterError):
        C.sign_in_room(signed, {"name": "x", "account_id": "y"}, 2, "now")
    with pytest.raises(Exception):
        CharterStore(world.plane("co-a")).edit(sid, org.account_id, lambda v: C.edit_purposes(v, {"c2": "x"}, settings, "s", "n"))


def test_a_signature_in_the_room_locks_the_draft_against_edits(world):
    org, sid, _ = ready(world)
    draft(org, sid)
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    assert org.put(f"{BASE}/sessions/{sid}/charter", json={"so_that": {"c2": "late change"}}).status_code == 409


# ---- M1-27: versions, and a human edit survives a new draft
def test_a_returned_charter_keeps_its_draft_and_a_human_edit_is_never_overwritten(world):
    org, sid, _ = ready(world)
    draft(org, sid)
    org.put(f"{BASE}/sessions/{sid}/charter", json={"so_that": {"c1": "our own words win"}})
    token = send_up(org, sid)
    r = approver_post(world, token, "decision", {"decision": "decline", "comment": "Add the fee list owner"})
    assert r.status_code == 200
    page = charter(org, sid)
    assert page["state"] == "together" and page["can_draft"] is True and page["charter"]["status"] == "returned"
    assert page["charter"]["returned"]["comment"] == "Add the fee list owner"
    again = draft(org, sid)["charter"]
    assert again["version"] == 2 and again["status"] == "draft"
    c1 = again["problems"][0]
    assert c1["so_that"] == "So that our own words win." and c1["so_that_edited"] is True
    assert c1["so_that_proposal"] == "funding is planned, not found"   # the room's line sits beside it, not over it
    assert [(v["version"], v["status"]) for v in again["versions"]] == [(1, "returned"), (2, "draft")]
    assert again["versions"][0]["comment"] == "Add the fee list owner"
