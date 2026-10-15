"""R1: build roles named at the charter. Synthetic family office."""
from m1_kit import BASE, draft
from sh_platform.profile import store


def put(plane, path, value):
    store.record(plane, path, value, {"mark": "stated", "by": "Hal", "from": "People list", "ref": {"kind": "document", "id": "d1"}})


def seed(world):
    plane = world.plane("co-a").ensure()
    for pid, name, role, flag in (("dan", "Dan Data", "Head of data", "is_head_of_data"), ("eli", "Eli Code", "Data engineer", None),
                                  ("oli", "Oli Ops", "Operations lead", None)):
        put(plane, f"people.{pid}.name", name)
        put(plane, f"people.{pid}.role", role)
        if flag:
            put(plane, f"people.{pid}.{flag}", True)
    return plane


def start(world, **over):
    org = world.login("org", "co-a", ["sponsor"])
    sid = org.post(f"{BASE}/sessions", json=draft(approver_name="Sue Sponsor", **over)).json()["id"]
    return org, sid


def test_roles_are_drafted_from_the_people_list_as_guesses(world):
    seed(world)
    org, sid = start(world)
    r = org.get(f"{BASE}/sessions/{sid}/roles").json()
    assert (r["roles"]["architect"], r["roles"]["developer"], r["roles"]["ops"], r["roles"]["sponsor"]) == ("Dan Data", "Eli Code", "Oli Ops", "Sue Sponsor")
    assert r["roles"]["tester"] is None and r["roles"]["informed"] == []
    assert r["provenance"]["architect"]["mark"] == "guessed" and "Dan Data" in r["provenance"]["architect"]["from"]
    assert r["can_edit"] is True


def test_the_organiser_sets_a_role_and_it_becomes_stated(world):
    seed(world)
    org, sid = start(world)
    r = org.put(f"{BASE}/sessions/{sid}/roles", json={"tester": "Tia Test", "informed": ["Ann"]})
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["roles"]["tester"] == "Tia Test" and got["roles"]["informed"] == ["Ann"]
    assert got["provenance"]["tester"]["mark"] == "stated" and got["provenance"]["architect"]["mark"] == "guessed"
    other = world.login("other", "co-a", ["analyst"])  # another organiser-capable person may read, not set
    assert other.get(f"{BASE}/sessions/{sid}/roles").json()["can_edit"] is False
    assert other.put(f"{BASE}/sessions/{sid}/roles", json={"tester": "X"}).status_code == 403
    assert org.put(f"{BASE}/sessions/{sid}/roles", json={"boss": "X"}).status_code == 422


def test_a_guess_never_overwrites_a_stated_role(world):
    plane = seed(world)
    org, sid = start(world)
    org.put(f"{BASE}/sessions/{sid}/roles", json={"architect": "Ann Architect"})
    put(plane, "people.zed.name", "Zed Zero")  # the profile now says someone else is head of data
    put(plane, "people.zed.is_head_of_data", True)
    r = org.get(f"{BASE}/sessions/{sid}/roles").json()
    assert r["roles"]["architect"] == "Ann Architect" and r["provenance"]["architect"]["mark"] == "stated"
