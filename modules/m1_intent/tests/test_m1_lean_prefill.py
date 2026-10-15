"""LI-M1 item 1: Prepare opens drafted from the company profile, every value with its source label. Synthetic family office."""
from m1_kit import BASE, draft
from sh_platform.profile import store

POLICY = "Investment policy statement, page 2"


def put(plane, path, value, by="Lens", frm=POLICY, agent="lens", kind="document", mark="stated"):
    store.record(plane, path, value, {"mark": mark, "by": by, "agent": agent, "from": frm, "ref": {"kind": kind, "id": "d1"}})


def seed(world, company="co-a"):
    plane = world.plane(company).ensure()
    for pid, name, role, sponsor in (("sue-sponsor", "Sue Sponsor", "Chair", True), ("aaron-lyle", "Aaron Lyle", "Head of exposure", False),
                                     ("dan-data", "Dan Data", "Head of data", False)):
        put(plane, f"people.{pid}.name", name, frm="People list", kind="document")
        put(plane, f"people.{pid}.role", role, frm="People list", kind="document")
        if sponsor:
            put(plane, f"people.{pid}.is_sponsor", True, frm="People list", kind="document")
    put(plane, "inputs.g2.summary", "Plan cash and exposure ahead of the family's capital calls", mark="guessed")
    put(plane, "interviews.aaron-lyle.q1", {"answer": "Which exposures to cut each month", "followups": []}, by="Aaron Lyle",
        frm="Interview with Aaron Lyle", agent=None, kind="interview", )
    put(plane, "interviews.sue-sponsor.q13", {"answer": "In three months calls are planned and exposure is one view. Aaron Lyle signs exposure, by 31 December",
                                              "followups": []}, by="Sue Sponsor", frm="Interview with Sue Sponsor", agent=None, kind="interview")
    return plane


def lists(c):
    r = c.get(f"{BASE}/lists")
    assert r.status_code == 200, r.text
    return r.json()


def test_prepare_opens_drafted_from_the_profile_with_source_labels(world):
    seed(world)
    d = lists(world.login("org", "co-a", ["sponsor"]))["profile_draft"]
    f = d["fields"]
    assert d["available"] is True
    assert f["purpose"] == {"value": "Plan cash and exposure ahead of the family's capital calls", "source": POLICY}
    assert f["outcome"]["value"].startswith("In three months calls are planned") and f["outcome"]["source"] == "Interview with Sue Sponsor"
    assert f["approver_name"] == {"value": "Aaron Lyle", "source": "Interview with Sue Sponsor"}  # the signer the sponsor named
    assert f["seats"] == {"value": 3, "source": "People list"}
    assert [(p["name"], p["role"]) for p in d["people"]] == [("Sue Sponsor", "Chair"), ("Aaron Lyle", "Head of exposure"), ("Dan Data", "Head of data")]
    assert f["names"]["value"] == "choice" and f["names"]["source"] and f["length_minutes"]["value"] == 20 and f["length_minutes"]["source"]
    assert all(v["source"] for v in f.values())  # every prefilled field names where it came from


def test_the_sponsor_is_the_approver_when_the_interview_names_nobody(world):
    plane = seed(world)
    put(plane, "interviews.sue-sponsor.q13", {"answer": "Calls are planned in three months", "followups": []}, by="Sue Sponsor",
        frm="Interview with Sue Sponsor", agent=None, kind="interview")
    f = lists(world.login("org", "co-a", ["sponsor"]))["profile_draft"]["fields"]
    assert f["approver_name"] == {"value": "Sue Sponsor", "source": "People list"}


def test_the_purpose_falls_back_to_the_sponsors_interview_when_no_strategy_was_brought(world):
    plane = seed(world)
    store.mutate(plane, lambda doc: doc["inputs"].pop("g2"))
    org = world.login("org", "co-a", ["sponsor"])
    f = lists(org)["profile_draft"]["fields"]
    assert "purpose" not in f  # Aaron Lyle's answer is not the sponsor's: it is not used
    put(plane, "interviews.sue-sponsor.q1", {"answer": "Plan the calls", "followups": []}, by="Sue Sponsor",
        frm="Interview with Sue Sponsor", agent=None, kind="interview")
    f = lists(org)["profile_draft"]["fields"]
    assert f["purpose"] == {"value": "Plan the calls", "source": "Interview with Sue Sponsor"}


def test_an_empty_company_gets_no_draft_and_today_s_wizard(world):
    d = lists(world.login("org", "co-empty", ["sponsor"]))["profile_draft"]
    assert d["available"] is False and d["fields"] == {}


def test_one_company_never_sees_anothers_profile(world):
    seed(world, "co-a")
    assert lists(world.login("org", "co-b", ["sponsor"]))["profile_draft"]["available"] is False


def test_a_draft_session_made_from_the_draft_is_an_ordinary_session(world):
    seed(world)
    c = world.login("org", "co-a", ["sponsor"])
    f = lists(c)["profile_draft"]["fields"]
    body = {k: f[k]["value"] for k in ("purpose", "outcome", "approver_name", "seats", "length_minutes", "names")}
    r = c.post(f"{BASE}/sessions", json={**body, "drafted": True})
    assert r.status_code == 201, r.text
    assert r.json()["preparation"]["approver_name"] == "Aaron Lyle" and r.json()["inputs"] == {"actions": 1, "free_text": 0, "cards_confirmed": 0, "cards_new": 0, "cards_sealed": 0}
