"""M1-26 the approver link: a security path. Hashed at rest, expiring, one session, read and decide only, nothing else
exposed, rate-limited like sign-in. Tokens here are made at run time; nothing is a real secret."""
import json
import re

import pytest

from m1_kit import BASE
from modules.m1_intent.store.charter import CharterStore, new_token
from sh_platform.auth.sessions import MAX_FAILURES
from test_m1_charter_kit import stand_in_result  # noqa: F401  (autouse: the fixture together-result)
from test_m1_charter_kit import APPROVER, approver_post, charter, draft, ready, send_up
from test_m1_room_kit import all_text, guest

TOKEN = re.compile(r"^ap-[0-9a-f]{32}-[A-Za-z0-9_-]{43}$")


def sent(world, **kw):
    org, sid, code = ready(world, **kw)
    draft(org, sid)
    return org, sid, send_up(org, sid)


def expire(world, sid, company="co-a"):
    """Moves the link's end into the past, in the file, as time passing would."""
    plane = world.plane(company)
    store = CharterStore(plane)
    doc = store.read(sid)
    doc["links"] = [{**l, "expires_at": "2000-01-01T00:00:00+00:00"} for l in doc["links"]]
    store._save(doc)


# ---- sending
def test_sending_needs_a_named_approver(world):
    org, sid, _ = ready(world, approver="")
    draft(org, sid)
    r = org.post(f"{BASE}/sessions/{sid}/charter/send")
    assert r.status_code == 409 and "approver" in r.json()["message"]


def test_a_charter_half_signed_in_the_room_cannot_be_sent_to_an_approver(world):
    # otherwise the approver's decision would replace the room's signatures (M1-P09 review)
    org, sid, _ = ready(world)
    draft(org, sid)
    assert org.post(f"{BASE}/sessions/{sid}/charter/sign").status_code == 200
    r = org.post(f"{BASE}/sessions/{sid}/charter/send")
    assert r.status_code == 409 and "being signed in the room" in r.json()["message"]
    assert charter(org, sid)["charter"]["signing"]["signed"] == 1


def test_the_link_is_unguessable_shown_once_and_stored_only_as_a_hash(world):
    org, sid, _ = ready(world)
    draft(org, sid)
    r = org.post(f"{BASE}/sessions/{sid}/charter/send")
    assert r.status_code == 200
    path = r.json()["link_path"]
    assert path.startswith("/approve/") and TOKEN.match(path.removeprefix("/approve/"))
    token = path.removeprefix("/approve/")
    secret = token[-43:]
    assert secret not in all_text(world.settings.data_root)           # only the hash is at rest
    assert secret not in json.dumps(charter(org, sid))                 # and the page cannot show it again
    page = charter(org, sid)["charter"]
    assert page["status"] == "awaiting_approver" and page["approver"]["link"] == "open" and page["approver"]["name"] == APPROVER
    assert page["editable"] is False                                   # the draft that went up does not move under the approver
    assert len({send_up_token(org, sid) for _ in range(3)}) == 3       # every link is new


def send_up_token(org, sid):
    org.post(f"{BASE}/sessions/{sid}/charter/withdraw")
    return send_up(org, sid)


def test_two_links_are_never_open_at_once_and_a_withdrawn_link_is_dead(world):
    org, sid, first = sent(world)
    second = send_up(org, sid) if org.post(f"{BASE}/sessions/{sid}/charter/withdraw").status_code == 200 else None
    assert approver_post(world, first).status_code == 409
    assert approver_post(world, second).status_code == 200
    assert org.post(f"{BASE}/sessions/{sid}/charter/withdraw").json()["charter"]["status"] == "draft"
    assert approver_post(world, second).status_code == 409
    assert "withdrawn" in approver_post(world, second).json()["message"]


# ---- reading
def test_the_approver_reads_the_draft_with_no_account_and_sees_nothing_else(world):
    org, sid, token = sent(world)
    r = approver_post(world, token)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"version", "template", "lists", "problems", "later", "footer", "approver_name", "expires_at"}
    assert [p["title"] for p in body["problems"]][0] == "Capital calls arrive too late"
    assert set(body["problems"][0]) == {"title", "kind", "details", "priority_label", "so_that", "note_count"}
    text = r.text
    plane_files = all_text(world.settings.data_root)
    for secret in (sid, "co-a", org.account_id, token):
        assert secret not in text, "the approver's page must not carry ids or the token back"
    assert "session_id" not in text and "outcome" not in text and "account" not in text
    assert "ap-" not in text and plane_files  # (the files exist; the answer holds none of their ids)
    # reading does not use the link up: a reload works
    assert approver_post(world, token).status_code == 200


def test_the_token_works_only_in_the_header(world):
    org, sid, token = sent(world)
    c = guest(world)
    for r in (c.post(f"{BASE}/approver/charter?token={token}"),
              c.post(f"{BASE}/approver/charter", json={"token": token}),
              c.post(f"{BASE}/approver/charter", headers={"Authorization": f"Bearer {token}"}),
              c.post(f"{BASE}/approver/charter", headers={"Cookie": f"sh_session={token}"})):
        assert r.status_code == 404 and r.json()["error"] == "link_invalid"


@pytest.mark.parametrize("token", ["", "x", "ap-", "ap-%s-%s" % ("0" * 32, "a" * 43), "ap-%s-%s" % ("g" * 32, "a" * 43), "ap.%s.%s" % ("0" * 32, "a" * 43),
                                   "a" * 300, "../" * 20, "ap-%s-%s" % ("0" * 32, "a" * 42)])
def test_malformed_and_unknown_tokens_get_the_same_plain_answer(world, token):
    ready(world)
    r = approver_post(world, token)
    assert r.status_code == 404 and r.json() == {"error": "link_invalid",
                                                 "message": "This link is not working. Please ask for a new one."}


def test_a_participant_style_token_is_not_an_approver_token(world):
    org, sid, code = ready(world)
    draft(org, sid)
    send_up(org, sid)
    from modules.m1_intent.store.room import RoomStore
    for t in (f"{sid}.{'a' * 43}", new_token(sid)):
        assert approver_post(world, t).status_code == 404


# ---- deciding
def test_the_approver_approves_and_the_charter_is_signed_with_their_name_and_time(world):
    org, sid, token = sent(world)
    r = approver_post(world, token, "decision", {"decision": "approve", "comment": "Go ahead"})
    assert r.status_code == 200 and r.json() == {"decision": "approve", "status": "signed"}
    got = charter(org, sid)["charter"]
    assert got["status"] == "signed" and got["handed_on"] is True
    sig = got["signing"]["signers"][0]
    assert sig["name"] == APPROVER and sig["how"] == "approver" and sig["at"]
    assert org.get(f"{BASE}/sessions/{sid}").json()["state"] == "closed"


def test_a_used_link_is_refused_for_reading_and_for_deciding(world):
    org, sid, token = sent(world)
    assert approver_post(world, token, "decision", {"decision": "approve"}).status_code == 200
    for what, body in (("charter", None), ("decision", {"decision": "approve"}), ("decision", {"decision": "decline", "comment": "no"})):
        r = approver_post(world, token, what, body)
        assert r.status_code == 409 and r.json()["error"] == "link_gone" and "already been used" in r.json()["message"]
    assert charter(org, sid)["charter"]["status"] == "signed"        # the second try changed nothing


def test_declining_needs_a_comment_reopens_together_and_keeps_the_draft_as_a_version(world):
    org, sid, token = sent(world)
    none = approver_post(world, token, "decision", {"decision": "decline"})
    assert none.status_code == 422 and none.json()["error"] == "comment_needed"
    assert approver_post(world, token, "decision", {"decision": "decline", "comment": "   "}).status_code == 422
    assert approver_post(world, token).status_code == 200            # a refused try did not use the link up
    r = approver_post(world, token, "decision", {"decision": "decline", "comment": "Not yet: name the owners"})
    assert r.status_code == 200 and r.json() == {"decision": "decline", "status": "returned"}
    page = charter(org, sid)
    assert page["state"] == "together" and page["charter"]["status"] == "returned" and page["can_draft"] is True
    assert page["charter"]["versions"][0]["comment"] == "Not yet: name the owners"
    assert approver_post(world, token).status_code == 409            # used up
    assert org.get(f"{BASE}/sessions/{sid}").json()["state"] == "together"
    new_v = draft(org, sid)["charter"]
    assert new_v["version"] == 2 and len(new_v["versions"]) == 2     # the first draft is still there, read-only
    assert approver_post(world, token).status_code == 409            # and the old link never reaches the new draft


def test_bad_decisions_are_refused_and_change_nothing(world):
    org, sid, token = sent(world)
    for body in ({}, {"decision": "maybe"}, {"decision": "approve", "extra": 1}, {"decision": "approve", "comment": "x" * 5000},
                 {"decision": "approve", "comment": 5}, [1], {"decision": ["approve"]}):
        r = approver_post(world, token, "decision", body)
        assert r.status_code in (400, 422), body
    c = guest(world)
    assert c.post(f"{BASE}/approver/decision", content=b"not json", headers={"X-Session-Token": token, "Content-Type": "application/json"}).status_code == 400
    assert c.post(f"{BASE}/approver/decision", content=b'{"decision":"approve"}', headers={"X-Session-Token": token}).status_code == 400  # JSON only
    assert c.post(f"{BASE}/approver/decision", content=b"x" * 40000, headers={"X-Session-Token": token, "Content-Type": "application/json"}).status_code == 400
    assert charter(org, sid)["charter"]["status"] == "awaiting_approver"


# ---- expiry, other sessions, other companies
def test_an_expired_link_is_refused(world):
    org, sid, token = sent(world)
    expire(world, sid)
    for what, body in (("charter", None), ("decision", {"decision": "approve"})):
        r = approver_post(world, token, what, body)
        assert r.status_code == 409 and "expired" in r.json()["message"]
    assert charter(org, sid)["charter"]["approver"]["link"] == "expired"
    assert charter(org, sid)["charter"]["status"] == "awaiting_approver"


def test_a_token_of_another_session_is_refused(world):
    org1, sid1, tok1 = sent(world)
    org2, sid2, tok2 = sent(world)
    secret1 = tok1[-43:]
    forged = f"ap-{sid2}-{secret1}"                  # session 1's secret under session 2's name
    assert approver_post(world, forged).status_code == 404
    assert approver_post(world, f"ap-{sid1}-{tok2[-43:]}").status_code == 404
    r = approver_post(world, tok2, "decision", {"decision": "approve"})
    assert r.status_code == 200
    assert charter(org1, sid1)["charter"]["status"] == "awaiting_approver"   # the other session did not move
    assert charter(org2, sid2)["charter"]["status"] == "signed"


def test_a_company_that_no_longer_owns_the_module_gives_the_same_plain_answer(world):
    org, sid, token = sent(world)
    world.store.set_module("co-a", "m1_intent", False)
    r = approver_post(world, token)
    assert r.status_code == 404 and r.json()["error"] == "link_invalid"


def test_the_link_of_one_company_cannot_reach_another_companys_session(world):
    orgb, sidb, tokb = sent(world, company="co-b")
    orga, sida, toka = sent(world, company="co-a")
    assert approver_post(world, tokb, "decision", {"decision": "approve"}).status_code == 200
    assert charter(orga, sida)["charter"]["status"] == "awaiting_approver"


def test_a_signed_in_person_of_another_company_has_no_extra_power_with_a_link(world):
    org, sid, token = sent(world)
    other = world.login("other", "co-b", ["company_admin"])
    r = other.post(f"{BASE}/approver/charter", headers={"X-Session-Token": token})
    assert r.status_code == 200                     # the link is the capability; the same view as anyone
    assert set(r.json()) == {"version", "template", "lists", "problems", "later", "footer", "approver_name", "expires_at"}
    assert other.get(f"{BASE}/sessions/{sid}/charter").status_code == 404   # and it opened nothing else


# ---- rate limit, like sign-in
def test_failed_tries_are_locked_out_like_a_login(world):
    org, sid, token = sent(world)
    for _ in range(MAX_FAILURES):
        assert approver_post(world, "ap-%s-%s" % ("0" * 32, "b" * 43)).status_code == 404
    locked = approver_post(world, token)             # even the right token waits
    assert locked.status_code == 429 and locked.json()["error"] == "too_many_tries"
    assert approver_post(world, token, "decision", {"decision": "approve"}).status_code == 429
    assert charter(org, sid)["charter"]["status"] == "awaiting_approver"


def test_a_good_link_does_not_clear_the_failures(world):
    org, sid, token = sent(world)
    for _ in range(MAX_FAILURES - 1):
        approver_post(world, "ap-%s-%s" % ("0" * 32, "b" * 43))
        assert approver_post(world, token).status_code == 200      # a valid read between guesses
    approver_post(world, "ap-%s-%s" % ("0" * 32, "b" * 43))
    assert approver_post(world, token).status_code == 429


def test_the_approver_routes_are_the_only_door_and_only_for_posts(world):
    org, sid, token = sent(world)
    c = guest(world)
    assert c.get(f"{BASE}/approver/charter", headers={"X-Session-Token": token}).status_code in (401, 403, 405)
    assert c.post(f"{BASE}/approver/other", headers={"X-Session-Token": token}).status_code in (401, 403, 404)
    for path in ("", "/sign", "/send", "/withdraw"):     # no organiser route opens to a token
        assert c.post(f"{BASE}/sessions/{sid}/charter{path}", headers={"X-Session-Token": token}).status_code in (401, 403)


def test_the_link_address_is_served_to_the_screen_not_taken_for_a_missing_file(world, tmp_path):
    """Found in the browser walk: an address whose last part has a dot is a 404 from the web server's file rule."""
    from fastapi.testclient import TestClient
    from sh_platform.app import create_app
    org, sid, token = sent(world)
    assert "." not in token
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>app</html>")
    page = TestClient(create_app(world.settings, dist_dir=dist, packs_root=world.packs)).get(f"/approve/{token}")
    assert page.status_code == 200 and "app" in page.text
