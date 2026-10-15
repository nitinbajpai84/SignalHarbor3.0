"""Spec 14 layer 2 and 3, checked against sh_platform/intents/access.py: the "Per-intent role against action" table row by row,
the refusal codes, drafts, strangers, shares, closed intents, a role removed mid-session and the module gate prefix.
Synthetic Ardmore people only. Cases that need a route body still on a stub are skipped with the reason.
"""
from types import SimpleNamespace

import pytest

access = pytest.importorskip("sh_platform.intents.access", reason="B04 access.py not built yet")
A = access

ROLE = frozenset({"participant"})
ME = {
    "organiser": A.Me("a-org", "Janet Shaw", ROLE),
    "closer": A.Me("a-spon", "Daniel Kerr", ROLE),
    "participant": A.Me("a-part", "Aaron Lyle", ROLE),
    "affected": A.Me("a-aff", "Harvey Rowley", ROLE),
    "observer": A.Me("a-obs", "Grace Ward", ROLE),
    "area_member": A.Me("a-area", "Katie", ROLE, areas=frozenset({"finance"})),
    "company_admin": A.Me("a-admin", "Janet Admin", frozenset({"company_admin"})),
    "share_visitor": A.Me("a-share", "Ravi", ROLE),
}
COLS = tuple(ME)
STRANGER = A.Me("a-x", "Rahul", ROLE)
SUPER = A.Me("a-sa", "Platform", frozenset({"super_admin"}))


def intent(**over) -> dict:
    rec = {"id": "i1", "type": "initiative", "state": "open", "created_by": "a-org", "areas": ["Finance"], "affected_may_read": False,
           "people": {"organiser": {"account_id": "a-org", "name": "Janet Shaw"}, "sponsor": {"account_id": "a-spon", "name": "Daniel Kerr"},
                      "participants": [{"account_id": "a-part"}], "affected": [{"account_id": "a-aff"}], "observers": [{"account_id": "a-obs"}]},
           "share": {"who_may_open": [{"account_id": "a-share", "expires_at": "2999-01-01T00:00:00Z", "revoked_at": None}]}}
    rec.update(over)
    return rec


def req(method="GET"):
    return SimpleNamespace(method=method, url=SimpleNamespace(path="/api/intents/i1/x"), state=SimpleNamespace(account_id="a"))


def refuse(rec, who, allowed, method="GET", code=None):
    me = who if isinstance(who, A.Me) else ME[who]
    with pytest.raises(A.IntentRefused) as e:
        A.require_intent_role(req(method), rec, allowed, code=code, plane=object(), me=me)
    return e.value.status_code, e.value.detail


# One dict drives the table test: action -> (role set, marks in COLS order: organiser closer participant affected observer area company_admin share)
TABLE = {
    "exists": (A.EXISTENCE, "YYYYYYYY"),
    "clock and people": (A.CLOCK_AND_PEOPLE, "YYYYY---"),
    "open the content": (A.CONTENT, "YYY-Y--Y"),
    "contribute": (A.CONTRIBUTE, "Y-Y-----"),
    "feel": (A.FEEL, "--YY----"),
    "follow": (A.FOLLOW, "---YY---"),
    "ask to join": (A.JOIN_REQUEST, "---Y-Y--"),
    "edit": (A.EDIT, "Y-------"),
    "stage": (A.STAGE, "Y-------"),
    "extend": (A.EXTEND, "Y-------"),
    "cancel an Initiative": (A.cancel_roles(intent()), "-Y------"),
    "confirm closure": (A.CONFIRM_CLOSURE, "-Y------"),
    "rate": (A.RATE, "--Y-----"),
    "share": (A.SHARE, "Y-------"),
    "hand to Build": (A.HANDOFF, "-Y----Y-"),
}


@pytest.mark.parametrize("row", TABLE)
def test_per_intent_role_against_action(row):
    allowed, marks = TABLE[row]
    got = "".join("Y" if A.roles_of(intent(), ME[c]) & allowed else "-" for c in COLS)
    assert got == marks, row


def test_area_member_gets_existence_and_content_closed():
    rec = intent()
    assert A.roles_of(rec, ME["area_member"]) & A.EXISTENCE
    status, body = refuse(rec, "area_member", A.CONTENT)
    assert (status, body["error"]) == (403, "intent_content_closed")
    assert body["message"].endswith("Organiser: Janet Shaw.")


def test_affected_is_closed_until_the_switch_then_reads():
    assert refuse(intent(), "affected", A.CONTENT)[1]["error"] == "intent_content_closed"
    assert A.require_intent_role(req(), intent(affected_may_read=True), A.CONTENT, plane=object(), me=ME["affected"])


def test_observer_reads_and_every_write_is_read_only():
    assert A.require_intent_role(req(), intent(), A.CONTENT, plane=object(), me=ME["observer"])
    for allowed in (A.CONTRIBUTE, A.EDIT, A.STAGE, A.SHARE, A.RATE, A.CONFIRM_CLOSURE):
        status, body = refuse(intent(), "observer", allowed, "POST")
        assert (status, body["error"]) == (403, "intent_read_only"), allowed


def test_draft_is_the_creators_only():
    draft = intent(state="draft", created_by="a-part")
    assert "creator" in A.roles_of(draft, ME["participant"])
    for who in ("organiser", "company_admin", "closer", "observer", "area_member"):
        assert A.roles_of(draft, ME[who]) == frozenset(), who
        assert refuse(draft, who, A.CONTENT)[1]["error"] == "intent_not_found", who
    assert A.roles_of(draft, SUPER) == frozenset()


def test_stranger_gets_the_same_404_as_a_missing_id(tmp_path):
    from sh_platform.plane import CompanyPlane
    status, body = refuse(intent(), STRANGER, A.CONTENT)
    with pytest.raises(A.IntentRefused) as e:
        A.load_intent(CompanyPlane("ardmore", tmp_path), "no-such-intent")
    assert (status, body) == (e.value.status_code, e.value.detail) == (404, {"error": "intent_not_found", "message": "We could not find that."})
    assert refuse(intent(), SUPER, A.EXISTENCE)[0] == 404  # the super admin has no company role in an intent


def test_share_revoked_expired_unknown_all_give_nothing_and_stay_on_their_intent():
    dead = [{"account_id": "a-share", "revoked_at": "2026-01-01T00:00:00Z"},
            {"account_id": "a-share", "expires_at": "2000-01-01T00:00:00Z"},
            {"account_id": "a-other"}]
    bodies = {repr(refuse(intent(share={"who_may_open": [e]}), "share_visitor", A.CONTENT)) for e in dead}
    assert len(bodies) == 1, "all three causes must read the same"
    other = intent(id="i2", share={"who_may_open": [{"account_id": "a-someone-else"}]})
    assert A.roles_of(other, ME["share_visitor"]) == frozenset()  # a token for intent A opens nothing on intent B


def test_share_visitor_is_read_only():
    for allowed in (A.CONTRIBUTE, A.EDIT, A.RATE, A.SHARE):
        assert refuse(intent(), "share_visitor", allowed, "POST")[1]["error"] == "intent_read_only", allowed


@pytest.mark.parametrize("state", ["closed", "cancelled"])
def test_closed_intent_refuses_every_write_but_not_reads(state):
    rec = intent(state=state)
    for who, allowed in (("organiser", A.EDIT), ("organiser", A.STAGE), ("organiser", A.SHARE), ("participant", A.CONTRIBUTE),
                         ("participant", A.RATE), ("closer", A.CONFIRM_CLOSURE)):
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            status, body = refuse(rec, who, allowed, method)
            assert (status, body["error"]) == (409, "intent_closed"), (who, method)
    assert A.require_intent_role(req("GET"), rec, A.CONTENT, plane=object(), me=ME["organiser"])


def test_role_removed_mid_session_is_refused_on_the_next_call():
    rec = intent()
    assert A.require_intent_role(req("POST"), rec, A.CONTRIBUTE, plane=object(), me=ME["participant"])
    rec["people"]["participants"] = []
    assert refuse(rec, "participant", A.CONTRIBUTE, "POST")[0] == 404  # no other tie to the intent


def test_refusal_codes_are_never_the_guards():
    codes = {refuse(intent(), w, a, m)[1]["error"] for w, a, m in
             [("observer", A.EDIT, "POST"), ("area_member", A.CONTENT, "GET"), (STRANGER, A.CONTENT, "GET")]}
    assert not codes & {"forbidden", "module_not_available"}


def test_module_gate_judges_api_intents_as_module_one():
    from sh_platform.modulegate import _module_segments
    assert _module_segments("/api/intents/i1/content")[0] == "m1_intent"
    assert _module_segments("/api/intentsx") is None


# ---- cases that need route bodies still on stubs

@pytest.mark.skip(reason="needs GET /api/control/companies/{id}/intents and /api/control/intents/summary bodies (admin.py is a stub)")
def test_super_admin_projection_keys_and_titles_private():
    ...


@pytest.mark.skip(reason="needs GET /api/intents?view=past body (past.py is a stub)")
def test_cancelled_intent_appears_in_past_with_its_reason():
    ...


@pytest.mark.skip(reason="needs GET /api/intents/{id}/notes body (no notes module yet)")
def test_company_admin_never_gets_anonymous_notes():
    ...
