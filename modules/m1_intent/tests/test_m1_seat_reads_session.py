"""A seat holder who is not the organiser reads the session's name, purpose, stage and their own seat, nothing else."""
from m1_kit import BASE
from test_m1_room_kit import join, new_session, start_room


def test_a_seat_holder_reads_name_purpose_stage_and_own_seat_only(world):
    org = world.login("org", "co-a")
    sid = new_session(org, seats=3)
    code = start_room(org, sid)
    assert join(org, code, 1, name="Olive Organiser", role="Owner").status_code == 200
    seated, outsider = world.login("ana", "co-a", ["analyst"]), world.login("out", "co-a", ["analyst"])
    assert outsider.get(f"{BASE}/sessions/{sid}").status_code == 404
    assert join(seated, code, 2, name="Ana Seated", role="Analyst").status_code == 200
    got = seated.get(f"{BASE}/sessions/{sid}").json()
    assert set(got) == {"id", "label", "state", "preparation", "seat"} and set(got["preparation"]) == {"purpose", "topic"}
    assert got["seat"] == {"n": 2, "name": "Ana Seated", "role": "Analyst"} and "Olive Organiser" not in str(got)
    assert got["state"] == "lobby" and got["preparation"]["purpose"] == org.get(f"{BASE}/sessions/{sid}").json()["preparation"]["purpose"]
