"""Q3: each comment carries the state line the Desk-Node artboard shows. Synthetic data."""
from tests.graph.test_comments import URL, login  # noqa: F401  (login is the fixture)


def test_state_lines_name_the_decider_and_the_version(login):
    plane, go, owner = login
    first = owner.split()[0]
    a = go("analyst")
    sug = a.post(URL, json={"kind": "suggestion", "text": "Add the FX check"}).json()["id"]
    amb = a.post(URL, json={"kind": "ambiguity", "text": "Dormant vehicles?", "anonymous": True}).json()["id"]
    com = a.post(URL, json={"kind": "comment", "text": "Tell the trustees"}).json()["id"]
    lines = {c["id"]: c["line"] for c in a.get(URL).json()["comments"]}
    assert lines[amb] == f"Open · {first} to decide"
    s = go("sponsor")
    assert s.post(f"{URL}/{sug}/decide", json={"state": "accepted"}).status_code == 200
    assert s.post(f"{URL}/{com}/decide", json={"state": "answered", "answer": "added to the September release note"}).status_code == 200
    lines = {c["id"]: c["line"] for c in a.get(URL).json()["comments"]}
    assert lines[sug] == f"Accepted by {first} (owner) · became version 1"
    assert lines[com] == "Answered: added to the September release note"
