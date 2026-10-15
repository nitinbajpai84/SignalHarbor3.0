"""M2 requests, answers and owner identity: a restricted measure never leaks through the requests or answers routes, the email
carries the real link and plain names, an answered request can be reopened or returns to open for a new measure, and a
nominee with no account confirms their own part through their answer link."""
import json

from m2_kit import login
from test_m2_requests_kit import BASE, BID, KPIS, kpi, seed, send, token_of, visitor

SECRET = {"source": {"value": "Bonus workbook on the HR share", "mark": "stated"}}
GOOD = {"tracked_today": {"value": "partly", "mark": "stated"}, "source": {"value": "Bank statement", "mark": "stated"}}


def restricted():
    return {**kpi("k3", "Bonus pool", data="Wei Chen"), "governance": {"personal": "yes", "sensitive": True, "may_see": []}}


def seed_with_secret(world):
    seed(world, kpis=[*KPIS[:2], restricted()])
    org = login(world, "co-a")
    send(org)
    r = org.put(f"{BASE}/baselines/{BID}/meeting-answers", json={"owner_name": "Wei Chen", "kpi_id": "k3", "answers": SECRET})
    assert r.status_code == 200, r.text
    return org


# ---- defect 2: nothing about a measure the asker may not see ----------------------------------------------------------
def test_the_requests_list_leaves_out_a_restricted_measure_and_the_people_asked_only_about_it(world):
    org = seed_with_secret(world)
    full = org.get(f"{BASE}/baselines/{BID}/requests").json()
    assert "Wei Chen" in json.dumps(full) and full["summary"]["asked"] == 4
    seen = login(world, "co-a", "Ann Analyst", ("analyst",)).get(f"{BASE}/baselines/{BID}/requests").json()
    text = json.dumps(seen)
    assert "Wei Chen" not in text and "Bonus pool" not in text and "k3" not in text
    assert seen["summary"]["asked"] == 3 and {r["owner_name"] for r in seen["requests"]} == {"Tom Reyes", "Arjun Rao", "Sara Lim"}
    assert all(w["kpi_id"] != "k3" for w in seen["waiting_on"])


def test_sending_as_the_analyst_shows_no_restricted_link_or_name(world):
    seed(world, kpis=[*KPIS[:2], restricted()])
    out = login(world, "co-a", "Ann Analyst", ("analyst",)).post(f"{BASE}/baselines/{BID}/requests").json()
    assert "Wei Chen" not in json.dumps(out) and "Bonus pool" not in json.dumps(out) and out["new"] == 3


def test_the_answers_list_leaves_out_a_restricted_measures_answers(world):
    org = seed_with_secret(world)
    assert "Bonus workbook" in json.dumps(org.get(f"{BASE}/baselines/{BID}/answers").json())
    out = login(world, "co-a", "Ann Analyst", ("analyst",)).get(f"{BASE}/baselines/{BID}/answers").json()
    assert "Bonus" not in json.dumps(out) and "k3" not in json.dumps(out) and "Wei Chen" not in json.dumps(out)
    assert [k["id"] for k in out["kpis"]] == ["k1", "k2"]


def test_a_person_named_in_governance_sees_it_and_the_analyst_cannot_act_on_it(world):
    folder = seed_with_secret(world)
    named = {**restricted(), "governance": {"personal": "yes", "sensitive": True, "may_see": ["Test Ann Analyst"]}}
    world.plane("co-a").path("intents", "m2_baseline", BID, "kpis.json").write_text(json.dumps([*KPIS[:2], named]))
    ann = login(world, "co-a", "Ann Analyst", ("analyst",))
    assert "Bonus workbook" in json.dumps(ann.get(f"{BASE}/baselines/{BID}/answers").json())
    nobody = login(world, "co-a", "Nick Nobody", ("analyst",))
    rid = next(r["id"] for r in folder.get(f"{BASE}/baselines/{BID}/requests").json()["requests"] if r["owner_name"] == "Wei Chen")
    assert nobody.post(f"{BASE}/baselines/{BID}/requests/{rid}/remind").status_code == 404
    assert nobody.put(f"{BASE}/baselines/{BID}/meeting-answers",
                      json={"owner_name": "Wei Chen", "kpi_id": "k3", "answers": SECRET}).status_code == 422


# ---- the email ------------------------------------------------------------------------------------------------------
def test_the_email_has_the_link_filled_in_and_no_illustrative_tag(world):
    seed(world, kpis=[kpi("k1", "Funding capacity", business="Mei Tan (illustrative)")])
    org = login(world, "co-a", "Pat Organiser (illustrative)")
    sent = send(org)["Mei Tan (illustrative)"]
    body = sent["email"]["body"]
    assert "{link}" not in body and token_of(sent) in body and "illustrative" not in body.lower()
    assert "Hello Mei Tan," in body
    assert "illustrative" not in sent["email"]["subject"].lower()


# ---- reopen, and a new measure -------------------------------------------------------------------------------------
def write_baseline(world):
    world.plane("co-a").path("intents", "m2_baseline", BID, "baseline.json").write_text(json.dumps(
        {"id": BID, "charter_outcome_id": "c" * 32, "state": "review", "created_at": "2026-10-03T10:00:00+00:00"}))


def answer_all(c, kpis=("k1", "k2")):
    for k in kpis:
        assert c.post(f"{BASE}/answer/save", json={"kpi_id": k, "answers": GOOD}).status_code == 200
    r = c.post(f"{BASE}/answer/submit")
    assert r.status_code == 200 and r.json()["state"] == "answered", r.text


def test_the_organiser_reopens_an_answered_request_with_a_new_link_and_the_old_answers_kept(world):
    seed(world)
    write_baseline(world)
    org = login(world, "co-a")
    tom = send(org)["Tom Reyes"]
    old = token_of(tom)
    answer_all(visitor(world, old))
    url = f"{BASE}/baselines/{BID}/requests/{tom['id']}"
    assert org.post(f"{url}/relink").status_code == 409                                    # relink still refuses an answered one
    out = org.post(f"{url}/reopen")
    assert out.status_code == 200, out.text
    out = out.json()
    new = out["link_path"].removeprefix("/answer/")
    assert out["request"]["state"] == "sent" and new != old and new in out["email"]["body"] and "{link}" not in out["email"]["body"]
    assert visitor(world, old).post(f"{BASE}/answer/form").status_code == 404
    form = visitor(world, new).post(f"{BASE}/answer/form").json()
    assert form["kpis"][0]["answers"]["source"]["value"] == "Bank statement"                 # the old answers are still there
    assert visitor(world, new).post(f"{BASE}/answer/save", json={"kpi_id": "k1", "answers": GOOD}).status_code == 200
    assert org.post(f"{url}/reopen").status_code == 409                                    # not answered any more
    log = org.get(f"{BASE}/baselines/{BID}/audit").json()
    assert log["intact"] and [e["action"] for e in log["entries"]] == ["reopen"] and "Tom Reyes" in log["entries"][0]["detail"]


def test_a_new_measure_for_someone_who_already_answered_puts_their_request_back_to_open(world):
    seed(world)
    org = login(world, "co-a")
    answer_all(visitor(world, token_of(send(org)["Tom Reyes"])))
    summary = lambda: org.get(f"{BASE}/baselines/{BID}/requests").json()  # noqa: E731
    assert next(r for r in summary()["requests"] if r["owner_name"] == "Tom Reyes")["state"] == "answered"
    seed(world, kpis=[*KPIS, kpi("k4", "Fee drag", business="Tom Reyes")])
    again = send(org)["Tom Reyes"]
    assert again["state"] == "opened" and [k["id"] for k in again["kpis"]] == ["k1", "k2", "k4"] and again["link_path"] is None
    assert summary()["summary"]["outstanding"] >= 1


# ---- identity: a nominee with no account confirms through the link ------------------------------------------------------
def test_a_nominee_without_an_account_confirms_only_their_own_part_through_the_link(world):
    seed(world)
    write_baseline(world)
    org = login(world, "co-a")
    sent = send(org)
    tom = visitor(world, token_of(sent["Tom Reyes"]))
    form = tom.post(f"{BASE}/answer/form").json()
    assert [(m["kpi_id"], m["part"], m["confirmed"]) for m in form["confirmable"]] == [("k1", "definition", False), ("k2", "definition", False)]
    assert tom.post(f"{BASE}/answer/confirm", json={"kpi_id": "k1", "part": "source"}).status_code == 422   # Arjun's part
    assert tom.post(f"{BASE}/answer/confirm", json={"kpi_id": "k3", "part": "definition"}).status_code == 422  # Wei's measure
    answer_all(tom)                                                                          # N-D: an owner confirms only after answering
    r = tom.post(f"{BASE}/answer/confirm", json={"kpi_id": "k1", "part": "definition"})
    assert r.status_code == 200 and [m["confirmed"] for m in r.json()["confirmable"]] == [True, False]
    again = tom.post(f"{BASE}/answer/confirm", json={"kpi_id": "k1", "part": "definition"})
    assert again.status_code == 409 and again.json()["error"] == "already_confirmed"
    review = org.get(f"{BASE}/baselines/{BID}/review").json()
    done = next(k for k in review["kpis"] if k["id"] == "k1")["parts"][0]["confirmed"]
    assert done["by"] == "Tom Reyes" and done["via"] == "answer link"
    log = org.get(f"{BASE}/baselines/{BID}/audit").json()
    assert log["intact"] and log["entries"][-1]["action"] == "confirm" and log["entries"][-1]["by"] == "Tom Reyes"
    # nobody else's link can confirm Tom's part, and a link that is not good confirms nothing
    assert visitor(world, token_of(sent["Arjun Rao"])).post(f"{BASE}/answer/confirm", json={"kpi_id": "k2", "part": "definition"}).status_code == 422
    assert visitor(world).post(f"{BASE}/answer/confirm", json={"kpi_id": "k1", "part": "definition"}).status_code == 404


def test_a_nominee_with_an_account_confirms_by_signing_in_not_by_link(world):
    owners = kpi("k1", "Funding capacity", business="Tom Reyes")
    owners["owners"]["business"]["account_id"] = "acct-tom"
    seed(world, kpis=[owners])
    write_baseline(world)
    link = visitor(world, token_of(send(login(world, "co-a"))["Tom Reyes"]))
    form = link.post(f"{BASE}/answer/form").json()
    assert form["confirmable"] == []  # an account owner confirms signed in (N4); the link only serves owners with no account
    assert [m["part"] for m in form["sign_in_parts"]] == ["definition"]  # the page tells them to sign in
    assert form["sign_in_path"].startswith("/modules/m2_baseline/signoff/")
    assert link.post(f"{BASE}/answer/confirm", json={"kpi_id": "k1", "part": "definition"}).status_code == 422
