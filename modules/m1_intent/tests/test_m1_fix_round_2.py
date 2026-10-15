"""LI-M1 fix round 2: two accounts with the same display name match no interview by name (B1-b); a seated sponsor, analyst or company
admin who is not the organiser can say "I'm done" for the rooms (N2); the door tells nothing about people in restricted areas (N1)."""
import json

from fastapi.testclient import TestClient

from m1_kit import BASE
from sh_platform.profile import store as profile
from test_m1_briefing_kit import make_world, session_at, sit, stage_of
from test_m1_lean_room import MEI, interview, room, tie
from test_m1_room_kit import guest, join, new_session, start_room
from test_m1_seat_wiring_kit import flow, new_world


def namesake(w, name, tag, company="co-a", roles=("participant",)):
    """A signed-in account whose display name is exactly `name` (another account may carry the same one)."""
    pw = "Fake-test-pass-1234"
    acct = w.accounts.create(f"{tag}@test.invalid", pw, name, company, list(roles))
    c = TestClient(w.app)
    assert c.post("/api/auth/login", json={"email": acct["email"], "password": pw}).status_code == 200
    c.headers["x-csrf-token"] = c.cookies["sh_csrf"]
    c.account_id = acct["account_id"]
    return c


# ---- A-043: an interview goes only to the account linked to that person; no name ever matches
def _sit_all(w, sid, accounts):
    for n, c in enumerate(accounts):
        sit(w, "co-a", sid, c.account_id, f"Seat Name {n}")  # a typed name proves nothing


def test_two_accounts_with_the_same_display_name_and_no_link_both_get_zero_drafts(tmp_path):
    w = make_world(tmp_path)
    interview(w)
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=4)
    a, b = namesake(w, "Mei Tan", "mei-a"), namesake(w, "mei  TAN", "mei-b")
    _sit_all(w, sid, [a, b])
    for c in (a, b):
        got = room(c, sid)
        assert got["notes"] == [] and "Capital calls" not in json.dumps(got)


def test_a_link_gives_drafts_to_that_account_only_even_when_the_name_is_shared(tmp_path):
    w = make_world(tmp_path)
    interview(w)
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=4)
    a, b = namesake(w, "Mei Tan", "mei-a"), namesake(w, "Mei Tan", "mei-b")
    tie(w, "mei-tan", a.account_id)
    _sit_all(w, sid, [a, b])
    assert {n["text"] for n in room(a, sid)["notes"]} == set(MEI.values())
    assert room(b, sid)["notes"] == []


def test_a_lone_account_with_the_exact_name_of_the_person_gets_nothing_without_a_link(tmp_path):
    w = make_world(tmp_path)
    interview(w)
    named_person(w, "mei-tan", "Mei Tan")
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=4)
    a = namesake(w, "Mei Tan", "mei-a")
    sit(w, "co-a", sid, a.account_id, "Mei Tan")
    assert room(a, sid)["notes"] == []


def test_a_new_hire_with_a_leavers_name_gets_the_leavers_interview_to_nobody(tmp_path):
    w = make_world(tmp_path)
    interview(w)
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=4)
    old = w.accounts.create("mei-old@test.invalid", "Fake-test-pass-1234", "Mei Tan", "co-a", ["participant"], disabled=True)
    tie(w, "mei-tan", old["account_id"])
    new = namesake(w, "Mei Tan", "mei-new")
    sit(w, "co-a", sid, new.account_id, "Mei Tan")
    assert room(new, sid)["notes"] == []


def test_an_interview_only_person_and_odd_names_get_nothing_unless_linked(tmp_path):
    """No name entry in the profile, punctuation, spacing, zero-width or non-Latin names: none of them finds an interview."""
    w = make_world(tmp_path)
    interview(w, people={"mei-tan": MEI, "item": {"q2": "Reports arrive late"}})
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=8)
    w.accounts.create("lei@test.invalid", "Fake-test-pass-1234", "\u674e\u96f7", "co-a", ["participant"], disabled=True)
    people = [namesake(w, n, f"p{k}") for k, n in enumerate(("\u738b\u82b3", "Mei-Tan", "Mei Tan\u200b", "MEI TAN", "Mei Tan", "item"))]
    _sit_all(w, sid, people)
    assert [room(c, sid)["notes"] for c in people] == [[]] * len(people)


def test_a_disabled_or_missing_link_target_gives_the_caller_nothing(tmp_path):
    w = make_world(tmp_path)
    interview(w)
    named_person(w, "mei-tan", "Mei Tan")
    tie(w, "mei-tan", "no-such-account")
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=4)
    a = namesake(w, "Mei Tan", "mei-a")
    sit(w, "co-a", sid, a.account_id, "Mei Tan")
    assert room(a, sid)["notes"] == []


# ---- N2
def test_a_seated_sponsor_who_is_not_the_organiser_can_say_done_and_close_the_rooms(tmp_path):
    w = new_world(tmp_path)
    org, sid, (ada,) = flow(w, "co-a", seats=5, names=("Ada Guest",))
    for roles in (("sponsor",), ("analyst",), ("company_admin",)):
        sam = w.login(f"Sam {roles[0]}", "co-a", list(roles))
        sit(w, "co-a", sid, sam.account_id, f"Sam {roles[0]}")
        assert sam.post(f"{BASE}/sessions/{sid}/room/done", json={"done": True}).status_code == 200
        assert sam.post(f"{BASE}/sessions/{sid}/room/done", json={"done": False}).status_code == 200
        sam.post(f"{BASE}/sessions/{sid}/room/done", json={"done": True})
    assert stage_of(org, sid) == "private_rooms"  # Ada has not said it
    assert ada.call("POST", "/room/done", json={"done": True}).status_code == 200
    assert stage_of(org, sid) == "board"


def test_the_organiser_and_an_unseated_sponsor_stay_refused_for_done(tmp_path):
    w = new_world(tmp_path)
    org, sid, _ = flow(w, "co-a")
    assert org.post(f"{BASE}/sessions/{sid}/room/done", json={"done": True}).status_code == 403
    other = w.login("Other Sponsor", "co-a", ["sponsor"])  # same company, no seat
    assert other.post(f"{BASE}/sessions/{sid}/room/done", json={"done": True}).status_code in (403, 404)
    assert stage_of(org, sid) == "private_rooms"


def test_the_done_route_has_the_same_roles_as_the_briefings_confirm_route():
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    man = yaml.safe_load((root / "modules/m1_intent/manifest.yaml").read_text(encoding="utf-8"))
    perms = yaml.safe_load((root / "sh_platform/route_permissions.yaml").read_text(encoding="utf-8"))
    ends = ("/briefing/confirm", "/room/done")
    roles = {r["path"].rsplit("/", 2)[-2] + "/" + r["path"].rsplit("/", 1)[-1]: set(r["roles"]) for r in man["routes"] if r["path"].endswith(ends)}
    p = {k.rsplit("/", 2)[-2] + "/" + k.rsplit("/", 1)[-1]: set(v["roles"]) for k, v in perms["routes"].items() if k.endswith(ends)}
    assert roles["briefing/confirm"] == roles["room/done"] == p["briefing/confirm"] == p["room/done"]


# ---- N1
def test_a_restricted_area_persons_name_is_not_refused_differently_from_an_unknown_name(tmp_path):
    w = new_world(tmp_path)
    plane = w.plane("co-a").ensure()
    org = w.login("org", "co-a", ["sponsor"])
    sid = new_session(org, seats=4)
    code = start_room(org, sid)
    src = {"mark": "stated", "by": "org", "from": "People list", "ref": {"kind": "document", "id": "p1"}}
    hidden, open_ = w.login("Hidden Holder", "co-a", ["participant"]), w.login("Open Holder", "co-a", ["participant"])
    for path, value in (("governance.restricted_areas.hr.area", "HR"), ("governance.restricted_areas.hr.may_see", []),
                        ("people.ann-hr.name", "Ann Hr"), ("people.ann-hr.team", "HR"), ("people.ann-hr.account_id", hidden.account_id),
                        ("people.bob-fin.name", "Bob Fin"), ("people.bob-fin.team", "Finance"), ("people.bob-fin.account_id", open_.account_id)):
        profile.record(plane, path, value, src)
    assert join(guest(w), code, 1, name="Ann Hr").status_code == 200  # nothing to tell: it is taken like an unknown name
    assert join(guest(w), code, 2, name="Nobody Known").status_code == 200
    r = join(guest(w), code, 3, name="Bob Fin")  # an open person tied to someone else is still refused
    assert r.status_code in (409, 422) and r.json()["error"] == "name_bound"


# ---- helpers and the rest of the lean security tests
def named_person(w, pid, name, company="co-a"):
    """The profile's people list names this person."""
    profile.record(w.plane(company).ensure(), f"people.{pid}.name", name,
                   {"mark": "stated", "by": "org", "from": "People list", "ref": {"kind": "document", "id": "p1"}})


def test_the_viewers_shared_name_flag_keeps_a_namesake_out_of_a_restricted_area_even_with_a_link(tmp_path):
    """A link finds the person, but a restricted area that lists the person by name must not open for a name two accounts carry
    (sh_platform/profile/view.py allows)."""
    w = make_world(tmp_path)
    interview(w)
    src = {"mark": "stated", "by": "org", "from": "People list", "ref": {"kind": "document", "id": "p1"}}
    plane = w.plane("co-a").ensure()
    for path, value in (("governance.restricted_areas.hr.area", "HR"), ("governance.restricted_areas.hr.may_see", ["Mei Tan"]),
                        ("people.mei-tan.name", "Mei Tan"), ("people.mei-tan.team", "HR")):
        profile.record(plane, path, value, src)
    org = w.login("org", "co-a", ["sponsor"])
    sid = session_at(w, org, "co-a", "private_rooms", seats=4)
    a, b = namesake(w, "Mei Tan", "mei-a"), namesake(w, "Mei Tan", "mei-b")
    tie(w, "mei-tan", a.account_id)
    _sit_all(w, sid, [a, b])
    assert [room(c, sid)["notes"] for c in (a, b)] == [[], []]


def test_the_door_refuses_only_the_normalised_name_of_an_open_person_linked_to_another_enabled_account(tmp_path):
    w = new_world(tmp_path)
    plane = w.plane("co-a").ensure()
    org = w.login("org", "co-a", ["sponsor"])
    sid = new_session(org, seats=8)
    code = start_room(org, sid)
    src = {"mark": "stated", "by": "org", "from": "People list", "ref": {"kind": "document", "id": "p1"}}
    hidden, open_ = w.login("Hidden Holder", "co-a", ["participant"]), w.login("Open Holder", "co-a", ["participant"])
    gone = w.accounts.create("gone@test.invalid", "Fake-test-pass-1234", "Gone Holder", "co-a", ["participant"], disabled=True)
    for path, value in (("governance.restricted_areas.hr.area", "HR"), ("governance.restricted_areas.hr.may_see", []),
                        ("people.ann-hr.name", "Ann Hr"), ("people.ann-hr.team", "HR"), ("people.ann-hr.account_id", hidden.account_id),
                        ("people.bob-fin.name", "Bob Fin"), ("people.bob-fin.team", "Finance"), ("people.bob-fin.account_id", open_.account_id),
                        ("people.cy-gone.name", "Cy Gone"), ("people.cy-gone.account_id", gone["account_id"])):
        profile.record(plane, path, value, src)
    outcomes = [join(guest(w), code, n, name=name) for n, name in enumerate(("Ann Hr", "Ann-Hr", "Zed Nobody"), 1)]
    assert [r.status_code for r in outcomes] == [200] * 3  # restricted or unknown: the same answer
    assert join(guest(w), code, 4, name="BOB  fin").json()["error"] == "name_bound"
    assert join(guest(w), code, 5, name="Bob-Fin").status_code == 200  # a different name: no name match at all
    assert join(guest(w), code, 6, name="Cy Gone").status_code == 200  # linked only to a switched-off account
    assert join(open_, code, 7, name="Bob Fin").status_code == 200  # the linked account itself


# ---- B2: Prepare reads the profile with the shared-name flag
def test_prepare_shows_two_namesake_analysts_nothing_from_a_restricted_area_that_lists_their_name(tmp_path):
    from test_m1_lean_prefill import put
    w = make_world(tmp_path)
    plane = w.plane("co-a").ensure()
    for path, value in (("governance.restricted_areas.hr.area", "HR"), ("governance.restricted_areas.hr.may_see", ["Mei Tan"]),
                        ("people.sam-hr.name", "Sam Hr"), ("people.sam-hr.team", "HR"), ("people.sam-hr.is_sponsor", True)):
        put(plane, path, value, frm="People list", kind="document")
    put(plane, "interviews.sam-hr.q1", {"answer": "Restricted HR purpose", "followups": []}, by="Sam Hr", frm="Interview with Sam Hr",
        agent=None, kind="interview")
    put(plane, "interviews.sam-hr.q13", {"answer": "Restricted HR outcome", "followups": []}, by="Sam Hr", frm="Interview with Sam Hr",
        agent=None, kind="interview")
    twins = [namesake(w, "Mei Tan", f"mei-{tag}", roles=("analyst",)) for tag in ("a", "b")]
    for c in twins:
        d = c.get(f"{BASE}/lists")
        assert d.status_code == 200, d.text
        assert "Restricted HR" not in d.text and "Sam Hr" not in d.text
