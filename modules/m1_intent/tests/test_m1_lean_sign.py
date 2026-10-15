"""LI-M1 item 5: one signature closes the charter (the sponsor, or the approver by link); two signers stay a choice in Prepare."""
from m1_kit import BASE
from test_m1_charter_kit import *  # noqa: F401,F403  (the charter kit and its autouse stand-in)
from test_m1_charter_kit import charter, draft, ready, second_signer


def sign(c, sid):
    return c.post(f"{BASE}/sessions/{sid}/charter/sign")


def test_one_signature_closes_the_charter_by_default(world):
    org, sid, code = ready(world, signers=None)
    assert draft(org, sid)["charter"]["signing"]["needed"] == 1
    got = sign(org, sid).json()["charter"]
    assert got["status"] == "signed" and got["signing"]["signed"] == 1
    assert org.get(f"{BASE}/sessions/{sid}").json()["state"] == "closed"


def test_the_organiser_can_still_ask_for_two_signers_in_prepare(world):
    org, sid, code = ready(world, signers=2)
    assert org.get(f"{BASE}/sessions/{sid}").json()["preparation"]["signers"] == 2
    assert draft(org, sid)["charter"]["signing"]["needed"] == 2
    assert sign(org, sid).json()["charter"]["status"] == "draft"
    two = second_signer(world, "co-a", code)
    assert sign(two, sid).json()["charter"]["status"] == "signed"


def test_only_one_or_two_signers_can_be_chosen(world):
    org = world.login("org", "co-a", ["sponsor"])
    from m1_kit import draft as body
    for bad in (0, 3, "2", True):
        assert org.post(f"{BASE}/sessions", json=body(signers=bad)).status_code == 422


def test_a_solo_session_needs_one_even_if_two_were_chosen(world):
    org, sid, code = ready(world, seats=1, signers=2)
    assert draft(org, sid)["charter"]["signing"]["needed"] == 1


def test_the_approver_by_link_is_the_one_signature(world):
    from test_m1_charter_kit import approver_post, send_up
    org, sid, code = ready(world, signers=None)
    draft(org, sid)
    token = send_up(org, sid)
    r = approver_post(world, token, "decision", {"decision": "approve"})
    assert r.status_code == 200, r.text
    assert charter(org, sid)["charter"]["status"] == "signed"
