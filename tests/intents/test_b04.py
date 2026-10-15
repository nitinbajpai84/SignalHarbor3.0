"""B04: the per-intent check of spec 14 (layer 2 and 3) and the module gate prefix. Synthetic Ardmore people only."""
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from sh_platform.intents import access as A
from sh_platform.jsonfile import write_json_atomic
from sh_platform.modulegate import _module_segments
from sh_platform.plane import CompanyPlane
from sh_platform.profile import store

ROLE = frozenset({"participant"})
ME = {
    "organiser": A.Me("a-org", "Janet Shaw", ROLE),
    "closer": A.Me("a-spon", "Daniel Kerr", ROLE),
    "participant": A.Me("a-part", "Aaron Lyle", ROLE),
    "affected": A.Me("a-aff", "Harvey Rowley", ROLE),
    "observer": A.Me("a-obs", "Grace Ward", ROLE),
    "area_member": A.Me("a-area", "Mei Ling", ROLE, areas=frozenset({"finance"})),
    "company_admin": A.Me("a-admin", "Admin", frozenset({"company_admin"})),
    "share_visitor": A.Me("a-share", "Ravi", ROLE),
}
STRANGER = A.Me("a-x", "Rahul", ROLE)
SUPER = A.Me("a-sa", "Platform", frozenset({"super_admin"}))


def intent(**over) -> dict:
    rec = {"id": "i1", "type": "initiative", "state": "open", "created_by": "a-org", "areas": ["Finance"], "affected_may_read": False,
           "people": {"organiser": {"account_id": "a-org", "name": "Janet Shaw"}, "sponsor": {"account_id": "a-spon", "name": "Daniel Kerr"},
                      "participants": [{"account_id": "a-part", "name": "Aaron Lyle"}], "affected": [{"account_id": "a-aff"}],
                      "observers": [{"account_id": "a-obs"}]},
           "share": {"who_may_open": [{"account_id": "a-share", "expires_at": "2999-01-01T00:00:00Z", "revoked_at": None}]}}
    rec.update(over)
    return rec


def may(action: frozenset, who: str, rec: dict | None = None) -> bool:
    return bool(A.roles_of(rec or intent(), ME[who]) & action)


# File 14, "Per-intent role against action", row by row. Columns in table order; Y = allowed through layer 2 on an open Initiative.
COLS = ("organiser", "closer", "participant", "affected", "observer", "area_member", "company_admin", "share_visitor")
TABLE = {
    "see that it exists": (A.EXISTENCE, "YYYYYYYY"),
    "see the clock and the people": (A.CLOCK_AND_PEOPLE, "YYYYY---"),
    "see the outcome once closed": (A.OUTCOME, "YYYYYYYY"),
    "open the content (switch off)": (A.CONTENT, "YYY-Y--Y"),
    "add a card, idea, answer, evidence": (A.CONTRIBUTE, "Y-Y-----"),
    "feel": (A.FEEL, "--YY----"),
    "note": (A.NOTE, "---Y----"),
    "ask to join": (A.JOIN_REQUEST, "---Y-Y--"),
    "follow": (A.FOLLOW, "---YY---"),
    "edit title, purpose, areas, people, affected may read": (A.EDIT, "Y-------"),
    "open or close a stage": (A.STAGE, "Y-------"),
    "close the build_ready stage": (A.STAGE_BUILD_READY, "YY------"),
    "extend the time box": (A.EXTEND, "Y-------"),
    "decide a second extension": (A.EXTEND_DECIDE, "-Y------"),
    "cancel (Initiative)": (A.cancel_roles(intent()), "-Y------"),
    "confirm the closure": (A.CONFIRM_CLOSURE, "-Y------"),
    "rate": (A.RATE, "--Y-----"),
    "share, revoke": (A.SHARE, "Y-------"),
    "start a linked intent": (A.LINK, "YY------"),
    "hand to Build": (A.HANDOFF, "-Y----Y-"),
}
# Not layer 2: "See anonymous notes" is the v1 rule in the notes handler; "Set titles_private" is the guard's company-admin-only line.


@pytest.mark.parametrize("row", TABLE)
def test_per_intent_table(row):
    action, marks = TABLE[row]
    got = "".join("Y" if may(action, c) else "-" for c in COLS)
    assert got == marks, row


def test_table_conditional_cells():
    assert may(A.CONTENT, "affected", intent(affected_may_read=True))  # only when switched on
    brainstorm = intent(type="brainstorm")
    assert A.cancel_roles(brainstorm) == A.ORGANISER and may(A.cancel_roles(brainstorm), "organiser", brainstorm)
    assert may(A.CONFIRM_CLOSURE, "organiser", brainstorm)  # organiser is closer when also closer
    both = intent(people={**intent()["people"], "participants": [{"account_id": "a-spon"}]})
    assert may(A.CONTRIBUTE, "closer", both) and may(A.RATE, "closer", both)  # closer if also participant
    problem = intent(type="problem", people={"organiser": "a-org", "owner": {"account_id": "a-aff"}, "reporter": {"account_id": "a-part"}})
    assert A.roles_of(problem, ME["affected"]) >= {"closer", "content"}
    assert "participant" in A.roles_of(problem, ME["participant"])  # a reporter counts as participant
    no_owner = intent(type="problem", people={"organiser": "a-org", "reporter": {"account_id": "a-part"}})
    assert "closer" in A.roles_of(no_owner, ME["participant"])  # owner, then reporter


def test_draft_is_creator_only():
    draft = intent(state="draft", created_by="a-org")
    assert {"creator", "organiser", "content"} <= A.roles_of(draft, ME["organiser"])
    named_not_creator = intent(state="draft", created_by="a-part")
    for who in COLS:
        if who != "participant":
            assert A.roles_of(named_not_creator, ME[who]) == frozenset(), who


def test_stranger_and_super_admin_have_no_role():
    assert A.roles_of(intent(), STRANGER) == frozenset()
    assert A.roles_of(intent(), SUPER) == frozenset()


def test_share_expired_revoked_or_bad_date_gives_nothing():
    for entry in ({"account_id": "a-share", "expires_at": "2000-01-01T00:00:00Z"}, {"account_id": "a-share", "revoked_at": "2026-01-01"},
                  {"account_id": "a-share", "expires_at": "soon"}):
        assert A.roles_of(intent(share={"who_may_open": [entry]}), ME["share_visitor"]) == frozenset()
    assert "content" in A.roles_of(intent(share={"who_may_open": [{"account_id": "a-aff"}]}), ME["affected"])  # named on a share opens it


def test_name_only_entry_needs_a_unique_name():
    rec = intent(people={"organiser": {"name": "Janet Shaw", "account_id": None}})
    assert "organiser" in A.roles_of(rec, A.Me("a-new", "janet  shaw", ROLE))
    assert A.roles_of(rec, A.Me("a-new", "Janet Shaw", ROLE, shared_name=True)) == frozenset()


# ---- require_intent_role: codes and words of file 14's Error copy


def req(method="GET"):
    return SimpleNamespace(method=method, url=SimpleNamespace(path="/api/intents/i1/x"), state=SimpleNamespace(account_id="a"))


def refuse(rec, who, allowed, method="GET", code=None):
    me = who if isinstance(who, A.Me) else ME[who]
    with pytest.raises(A.IntentRefused) as e:
        A.require_intent_role(req(method), rec, allowed, code=code, plane=object(), me=me)
    return e.value.status_code, e.value.detail


def test_no_role_is_404_same_as_missing(tmp_path):
    status, body = refuse(intent(), STRANGER, A.CONTENT)
    assert (status, body) == (404, {"error": "intent_not_found", "message": "We could not find that."})
    with pytest.raises(A.IntentRefused) as e:
        A.load_intent(CompanyPlane("ardmore", tmp_path), "nope")
    assert (e.value.status_code, e.value.detail) == (status, body)
    with pytest.raises(A.IntentRefused) as e:
        A.load_intent(CompanyPlane("ardmore", tmp_path), "..")
    assert e.value.status_code == 404


def test_content_closed_names_the_organiser():
    for who in ("area_member", "company_admin", "affected"):
        status, body = refuse(intent(), who, A.CONTENT)
        assert status == 403 and body["error"] == "intent_content_closed"
        assert body["message"] == ("You can see that this exists. You can open it if the organiser adds you. Organiser: Janet Shaw.")
    assert A.require_intent_role(req(), intent(affected_may_read=True), A.CONTENT, plane=object(), me=ME["affected"])


def test_observer_writes_are_read_only():
    status, body = refuse(intent(), "observer", A.CONTRIBUTE, "POST")
    assert (status, body) == (403, {"error": "intent_read_only", "message": "You can read this intent but not change it."})


def test_not_your_close():
    status, body = refuse(intent(), "organiser", A.CONFIRM_CLOSURE, "POST", code="intent_not_your_close")
    assert status == 403 and body == {"error": "intent_not_your_close",
                                      "message": "Only Daniel Kerr can close this. North has told them it is waiting."}


def test_closed_and_cancelled_refuse_writes_not_reads():
    for state in ("closed", "cancelled"):
        status, body = refuse(intent(state=state), "organiser", A.EDIT, "PUT")
        assert (status, body["error"]) == (409, "intent_closed")
        assert body["message"] == "This intent is closed. It is kept as it was and cannot be changed."
        assert "organiser" in A.require_intent_role(req(), intent(state=state), A.CONTENT, plane=object(), me=ME["organiser"])


def test_refusal_codes_are_never_the_guards():
    codes = {refuse(intent(), w, a, m)[1]["error"] for w, a, m in
             [("observer", A.EDIT, "POST"), ("area_member", A.CONTENT, "GET"), (STRANGER, A.CONTENT, "GET")]}
    assert not codes & {"forbidden", "module_not_available"}


# ---- the dependency, the flat body, the profile link


def test_person_of_reads_the_linked_person_and_stated_areas(tmp_path):
    plane = CompanyPlane("ardmore", tmp_path)
    doc = store.empty()
    doc["people"] = {"p1": {"account_id": {"value": "a1", "mark": "stated"}, "areas": {"value": ["Finance"], "mark": "stated"}},
                     "p2": {"account_id": {"value": "a2", "mark": "stated"}, "areas": {"value": ["Ops"], "mark": "guessed", "agent": "lens"}}}
    write_json_atomic(plane.path("context", "profile", "profile.json"), doc)
    assert A.person_of(plane, "a1") == ("p1", frozenset({"finance"}))
    assert A.person_of(plane, "a2") == ("p2", frozenset())  # a Lens guess is not a tag
    assert A.person_of(plane, "a9") == (None, frozenset())
    assert "participant" in A.roles_of(intent(people={"participants": ["p1"]}), A.Me("a1", "", ROLE, person_id="p1"))


def test_intent_route_returns_the_flat_body():
    def deny():
        raise A.IntentRefused(403, "intent_read_only", A.READ_ONLY)
    router = APIRouter(route_class=A.IntentRoute)
    router.add_api_route("/x", lambda _=Depends(deny): {"ok": True})
    app = FastAPI()
    app.include_router(router)
    r = TestClient(app).get("/x")
    assert (r.status_code, r.json()) == (403, {"error": "intent_read_only", "message": A.READ_ONLY})


def test_module_gate_judges_api_intents_as_module_one():
    assert _module_segments("/api/intents") == ["m1_intent"]
    assert _module_segments("/api/intents/i1/content") == ["m1_intent", "i1", "content"]
    assert _module_segments("/api/intentsx") is None
    assert _module_segments("/api/modules/m2_baseline/x") == ["m2_baseline", "x"]


# ---- tester T04: what the spec forbids


def test_content_readers_who_may_not_write_never_write_through_content():
    for who, rec in (("observer", intent()), ("share_visitor", intent()), ("affected", intent(affected_may_read=True))):
        status, body = refuse(rec, who, A.CONTENT, "POST")
        assert (status, body["error"]) == (403, "intent_read_only"), who
    assert A.require_intent_role(req("POST"), intent(), A.CONTENT, plane=object(), me=ME["participant"])


def test_super_admin_has_no_role_even_when_named():
    rec = intent(people={"organiser": {"account_id": "a-sa"}}, created_by="a-sa")
    assert A.roles_of(rec, SUPER) == frozenset()
    assert A.roles_of({**rec, "state": "draft"}, SUPER) == frozenset()


def test_a_name_shared_with_a_person_without_an_account_matches_nobody(tmp_path):
    plane = CompanyPlane("ardmore", tmp_path)
    doc = store.empty()
    doc["people"] = {"p1": {"name": {"value": "Aaron Lyle", "mark": "stated"}, "account_id": {"value": "a-part", "mark": "stated"}},
                     "p9": {"name": {"value": "Aaron  Lyle", "mark": "stated"}}}  # same name, no account
    write_json_atomic(plane.path("context", "profile", "profile.json"), doc)
    assert A.name_twin(plane, "Aaron Lyle", "p1")
    assert not A.name_twin(plane, "Grace Ward", "p1")
    assert A.name_twin(plane, "Aaron Lyle", None)  # unlinked viewer, but p1 is linked to another account
    assert A.name_twin(plane, "Aaron Lyle", "p9")  # seen from p9, p1 is someone else
    me = A.Me("a-part", "Aaron Lyle", ROLE, shared_name=A.name_twin(plane, "Aaron Lyle", "p1"), person_id="p1")
    assert A.roles_of(intent(people={"participants": [{"name": "Aaron Lyle"}]}), me) == frozenset()
    assert "participant" in A.roles_of(intent(people={"participants": [{"person_id": "p1"}]}), me)
    assert A.roles_of(intent(people={"participants": [{"person_id": "p9"}]}), me) == frozenset()  # the person with no account
