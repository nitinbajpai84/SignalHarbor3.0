"""M2-P02 fix round 1: the link is checked before any body is read, odd value types give a plain 422, the organiser routes
need the CSRF header, a submitted link is read-only, and samples per link are capped."""
import base64
import sys

import pytest
from m2_kit import login
from test_m2_answers import GOOD, save
from test_m2_requests_kit import BASE, BID, seed, send, token_of, visitor

from modules.m2_baseline.domain.questionnaire import load_questionnaire


@pytest.fixture
def tom(world):
    seed(world)
    org = login(world, "co-a")
    sent = send(org)["Tom Reyes"]
    return org, visitor(world, token_of(sent)), sent


def _api():
    return next(m for m in list(sys.modules.values()) if hasattr(m, "SAMPLE_AGENT") and hasattr(m, "_body"))


@pytest.mark.parametrize("path", ["/answer/save", "/answer/sample"])
def test_a_bad_token_is_refused_without_the_body_being_read(world, monkeypatch, path):
    seed(world)
    send(login(world, "co-a"))

    async def boom(*a, **k):
        raise AssertionError("the body was read")
    monkeypatch.setattr(_api(), "_body", boom)
    big = {"kpi_id": "k1", "filename": "a.txt", "data": base64.b64encode(b"x" * 500_000).decode()}
    bad = visitor(world, "ow-" + "0" * 32 + "-" + "a" * 43)
    r = bad.post(f"{BASE}{path}", json=big)
    assert r.status_code == 404
    assert visitor(world).post(f"{BASE}{path}", json=big).status_code == 404  # no token at all


@pytest.mark.parametrize("path", ["/answer/save", "/answer/sample"])
def test_a_locked_out_caller_is_refused_without_the_body_being_read(world, monkeypatch, path):
    seed(world)
    send(login(world, "co-a"))
    bad = visitor(world, "ow-" + "0" * 32 + "-" + "a" * 43)
    for _ in range(5):
        bad.post(f"{BASE}/answer/form")

    async def boom(*a, **k):
        raise AssertionError("the body was read")
    monkeypatch.setattr(_api(), "_body", boom)
    assert bad.post(f"{BASE}{path}", json={"kpi_id": "k1"}).status_code == 429


@pytest.mark.parametrize("value", [[1], {"a": 1}, 5, True])
def test_a_choice_answer_that_is_not_text_is_a_plain_422(tom, value):
    r = tom[1].post(f"{BASE}/answer/save", json={"kpi_id": "k1", "answers": {"tracked_today": {"value": value, "mark": "stated"}}})
    assert r.status_code == 422 and r.json()["message"] and r.json()["field"] == "tracked_today"


@pytest.mark.parametrize("kpi_id", [["k1"], {"a": 1}, 7, None])
def test_a_measure_that_is_not_text_is_a_plain_422_for_a_link_holder(tom, kpi_id):
    r = tom[1].post(f"{BASE}/answer/save", json={"kpi_id": kpi_id, "answers": GOOD})
    assert r.status_code == 422 and r.json()["field"] == "kpi_id"
    r = tom[1].post(f"{BASE}/answer/sample", json={"kpi_id": kpi_id, "filename": "a.txt", "data": "aGk="})
    assert r.status_code == 422


def test_odd_values_are_a_plain_422_for_an_organiser(world):
    seed(world)
    org = login(world, "co-a")
    put = lambda body: org.put(f"{BASE}/baselines/{BID}/meeting-answers", json=body)  # noqa: E731
    assert put({"owner_name": "Wei Chen", "kpi_id": ["a"], "answers": GOOD}).status_code == 422
    r = put({"owner_name": "Wei Chen", "kpi_id": "k3", "answers": {"could_track": {"value": [1], "mark": "stated"}}})
    assert r.status_code == 422 and r.json()["message"]
    assert org.post(f"{BASE}/baselines/{BID}/sample", json={"owner_name": "Wei Chen", "kpi_id": {"a": 1}, "filename": "a.txt", "data": "aGk="}).status_code == 422


def test_the_organiser_routes_refuse_a_request_with_no_csrf_header(world):
    seed(world)
    org = login(world, "co-a")
    rid = send(org)["Tom Reyes"]["id"]
    org.headers.pop("x-csrf-token")
    base = f"{BASE}/baselines/{BID}"
    data = base64.b64encode(b"hi").decode()
    calls = [("post", f"{base}/requests", {}), ("post", f"{base}/requests/{rid}/remind", {}),
             ("post", f"{base}/requests/{rid}/revoke", {}), ("post", f"{base}/requests/{rid}/relink", {}),
             ("post", f"{base}/requests/{rid}/meeting", {}),
             ("put", f"{base}/meeting-answers", {"owner_name": "Wei Chen", "kpi_id": "k3", "answers": GOOD}),
             ("post", f"{base}/sample", {"owner_name": "Wei Chen", "kpi_id": "k3", "filename": "a.txt", "data": data})]
    for method, url, body in calls:
        r = getattr(org, method)(url, json=body)
        assert r.status_code == 403, (url, r.status_code)
    org.headers["x-csrf-token"] = org.cookies["sh_csrf"]  # and with it the same call is accepted
    assert org.post(f"{base}/requests/{rid}/remind").status_code == 200


def test_a_submitted_link_is_read_only(tom):
    _, c, _ = tom
    save(c, "k1")
    save(c, "k2", {"source": {"value": None, "mark": "unknown"}})
    assert c.post(f"{BASE}/answer/submit").json() == {"state": "answered"}
    msg = "Your answers are in. Ask the organiser to reopen them if something changed."
    r = c.post(f"{BASE}/answer/save", json={"kpi_id": "k1", "answers": GOOD})
    assert r.status_code == 409 and r.json()["message"] == msg
    assert c.post(f"{BASE}/answer/sample", json={"kpi_id": "k1", "filename": "a.txt", "data": "aGk="}).status_code == 409
    assert c.post(f"{BASE}/answer/form").status_code == 200  # still readable


def test_samples_per_link_are_capped(tom):
    _, c, _ = tom
    cap = load_questionnaire().limits["samples_per_link"]
    for _ in range(cap):
        assert c.post(f"{BASE}/answer/sample", json={"kpi_id": "k1", "filename": "a.txt", "data": "aGk="}).status_code == 200
    r = c.post(f"{BASE}/answer/sample", json={"kpi_id": "k1", "filename": "a.txt", "data": "aGk="})
    assert r.status_code == 409 and str(cap) in r.json()["message"]
