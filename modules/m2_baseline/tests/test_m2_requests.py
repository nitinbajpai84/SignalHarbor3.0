"""M2-P02: requests to owners (M2-06), the answer link with no account (M2-07), the outstanding view and chasing (M2-29)."""
import json

from m2_kit import login
from test_m2_requests_kit import BASE, BID, KPIS, Clock, kpi, seed, send, token_of, visitor

from modules.m2_baseline.store.requests import RequestStore


def test_one_request_per_nominated_owner_listing_only_their_measures(world):
    seed(world)
    sent = send(login(world, "co-a"))
    assert set(sent) == {"Tom Reyes", "Arjun Rao", "Sara Lim", "Wei Chen"}
    assert [k["name"] for k in sent["Arjun Rao"]["kpis"]] == ["Funding capacity", "Capital call timing"]
    assert sent["Arjun Rao"]["role"] == "data owner" and sent["Tom Reyes"]["state"] == "sent"
    assert [k["name"] for k in sent["Wei Chen"]["kpis"]] == ["Distribution lag"]


def test_an_owner_nobody_named_is_not_asked(world):
    seed(world, kpis=[kpi("k1", "Funding capacity", business="Tom Reyes")])
    assert set(send(login(world, "co-a"))) == {"Tom Reyes"}


def test_the_link_is_shown_once_and_only_its_hash_is_stored(world):
    seed(world)
    org = login(world, "co-a")
    sent = send(org)
    token = token_of(sent["Tom Reyes"])
    assert token.startswith("ow-")
    files = [p.read_text() for p in world.plane("co-a").path("intents", "m2_baseline", BID).glob("*.json")]
    assert not any(token in text for text in files)
    assert token not in open(f"{world.settings.data_root}/_control/m2_answer_index.json").read()
    stored = json.loads(world.plane("co-a").path("intents", "m2_baseline", BID, "requests.json").read_text())
    assert all(len(r["token_hash"]) == 64 for r in stored)
    again = send(org)  # sending again keeps the same requests and shows no second link
    assert all(r["link_path"] is None for r in again.values())
    assert org.get(f"{BASE}/baselines/{BID}/requests").json()["summary"]["asked"] == 4


def test_the_email_text_has_names_and_questions_never_figures_or_definitions(world):
    seed(world)
    mail = send(login(world, "co-a"))["Tom Reyes"]["email"]
    assert mail["subject"].startswith("A few questions about 2 measures from ") and "Funding capacity" not in mail["subject"]  # the measures are in the body
    assert "- Funding capacity" in mail["body"] and "minute" not in mail["body"]
    assert "{link}" not in mail["body"] and "/answer/ow-" in mail["body"] and "You can answer here without signing in" in mail["body"]
    assert "A definition the owner never receives" not in json.dumps(mail)


def test_the_answer_page_shows_only_that_persons_names_and_questions(world):
    seed(world)
    sent = send(login(world, "co-a"))
    form = visitor(world, token_of(sent["Wei Chen"])).post(f"{BASE}/answer/form").json()
    assert [k["name"] for k in form["kpis"]] == ["Distribution lag"]
    text = json.dumps(form)
    assert "Funding capacity" not in text and "A definition the owner never receives" not in text
    assert "Arjun" not in text and "token" not in text


def test_the_token_works_only_in_the_header(world):
    seed(world)
    token = token_of(send(login(world, "co-a"))["Tom Reyes"])
    c = visitor(world)
    assert c.post(f"{BASE}/answer/form", json={"token": token}).status_code == 404
    assert c.post(f"{BASE}/answer/form?token={token}").status_code == 404
    assert c.post(f"{BASE}/answer/form/{token}").status_code in (401, 403, 404, 405)
    assert visitor(world, token).post(f"{BASE}/answer/form").status_code == 200


def test_every_refusal_before_the_hash_matches_gives_one_answer(world):
    seed(world)
    token = token_of(send(login(world, "co-a"))["Tom Reyes"])
    rid = token.split("-")[1]
    answers = []
    for bad in ("", "nonsense", f"ow-{'0' * 32}-{'a' * 43}", f"ow-{rid}-{'a' * 43}"):
        r = visitor(world, bad or None).post(f"{BASE}/answer/form")
        answers.append((r.status_code, r.json()))
    assert len({json.dumps(a) for a in answers}) == 1 and answers[0][0] == 404


def test_five_wrong_tries_lock_the_caller_out(world):
    seed(world)
    token = token_of(send(login(world, "co-a"))["Tom Reyes"])
    c = visitor(world, f"ow-{'0' * 32}-{'a' * 43}")
    codes = [c.post(f"{BASE}/answer/form").status_code for _ in range(6)]
    assert codes[:5] == [404] * 5 and codes[5] == 429
    assert visitor(world, token).post(f"{BASE}/answer/form").status_code == 429  # same address, still waiting


def test_opening_the_link_marks_it_opened(world):
    seed(world)
    org = login(world, "co-a")
    token = token_of(send(org)["Tom Reyes"])
    visitor(world, token).post(f"{BASE}/answer/form")
    row = next(r for r in org.get(f"{BASE}/baselines/{BID}/requests").json()["requests"] if r["owner_name"] == "Tom Reyes")
    assert row["state"] == "opened" and row["opened_at"]


def test_an_expired_link_is_refused_with_its_reason(world):
    seed(world)
    clock = Clock(world)
    token = token_of(send(login(world, "co-a"))["Tom Reyes"])
    assert visitor(world, token).post(f"{BASE}/answer/form").status_code == 200
    clock.days(15)
    r = visitor(world, token).post(f"{BASE}/answer/form")
    assert r.status_code == 409 and "expired" in r.json()["message"]


def test_a_withdrawn_link_stops_and_a_new_one_replaces_it(world):
    seed(world)
    org = login(world, "co-a")
    sent = send(org)["Tom Reyes"]
    token = token_of(sent)
    out = org.post(f"{BASE}/baselines/{BID}/requests/{sent['id']}/revoke").json()
    assert out["request"]["link"] == "revoked"
    r = visitor(world, token).post(f"{BASE}/answer/form")
    assert r.status_code == 409 and "withdrawn" in r.json()["message"]
    fresh = org.post(f"{BASE}/baselines/{BID}/requests/{sent['id']}/relink").json()
    new_token = fresh["link_path"].removeprefix("/answer/")
    assert new_token != token and new_token in fresh["email"]["body"] and "{link}" not in fresh["email"]["body"]
    assert visitor(world, new_token).post(f"{BASE}/answer/form").status_code == 200
    assert visitor(world, token).post(f"{BASE}/answer/form").status_code == 404  # the old secret no longer matches


def test_chasing_at_three_and_seven_days_and_the_organiser_is_told(world):
    seed(world)
    clock = Clock(world)
    org = login(world, "co-a")
    sent = send(org)
    visitor(world, token_of(sent["Tom Reyes"])).post(f"{BASE}/answer/form")  # Tom opens it; Wei never does
    view = lambda: org.get(f"{BASE}/baselines/{BID}/requests").json()  # noqa: E731
    row = lambda v, n: next(r for r in v["requests"] if r["owner_name"] == n)  # noqa: E731
    clock.days(2)
    assert row(view(), "Wei Chen")["state"] == "sent" and not row(view(), "Wei Chen")["remind_due"]
    clock.days(1)
    v = view()
    assert row(v, "Wei Chen")["state"] == "no_reply" and row(v, "Wei Chen")["remind_due"] and row(v, "Wei Chen")["days_waiting"] == 3
    assert row(v, "Tom Reyes")["state"] == "opened"  # opened, not answered
    assert "has not replied in 3 days" in row(v, "Wei Chen")["nira"] and v["alerts"] == []
    wei = row(v, "Wei Chen")["id"]
    marked = org.post(f"{BASE}/baselines/{BID}/requests/{wei}/remind").json()
    assert len(marked["request"]["reminders"]) == 1 and not marked["request"]["remind_due"]
    assert "Reminder" in marked["email"]["subject"] and "earlier message" in marked["email"]["body"]
    clock.days(4)
    v = view()
    assert row(v, "Wei Chen")["remind_due"] and row(v, "Wei Chen")["organiser_told"]
    assert len(v["alerts"]) == 4  # nobody has answered: all four are outstanding at seven days
    assert {w["kpi_name"] for w in v["waiting_on"]} == {"Funding capacity", "Capital call timing", "Distribution lag"}
    assert next(w for w in v["waiting_on"] if w["kpi_id"] == "k1")["waiting_on"] == ["Tom Reyes", "Arjun Rao", "Sara Lim"]
    assert v["summary"] == {"asked": 4, "answered": 0, "outstanding": 4, "in_meeting": 0}


def test_an_answered_owner_is_no_longer_outstanding_and_cannot_be_reminded(world):
    seed(world)
    org = login(world, "co-a")
    sent = send(org)["Wei Chen"]
    c = visitor(world, token_of(sent))
    c.post(f"{BASE}/answer/save", json={"kpi_id": "k3", "answers": {"source": {"value": "Fund admin file", "mark": "stated"}}})
    assert c.post(f"{BASE}/answer/submit").json() == {"state": "answered"}
    v = org.get(f"{BASE}/baselines/{BID}/requests").json()
    assert v["summary"]["answered"] == 1 and v["summary"]["outstanding"] == 3
    assert all("Wei Chen" not in w["waiting_on"] for w in v["waiting_on"])
    assert org.post(f"{BASE}/baselines/{BID}/requests/{sent['id']}/remind").status_code == 409


def test_answer_in_a_meeting_instead_withdraws_the_link(world):
    seed(world)
    org = login(world, "co-a")
    sent = send(org)["Wei Chen"]
    out = org.post(f"{BASE}/baselines/{BID}/requests/{sent['id']}/meeting").json()["request"]
    assert out["state"] == "in_meeting" and out["meeting"]["by"] == "Test Pat Owner" and out["link"] == "revoked"
    assert visitor(world, token_of(sent)).post(f"{BASE}/answer/form").status_code == 409
    assert org.get(f"{BASE}/baselines/{BID}/requests").json()["summary"]["in_meeting"] == 1


def test_a_baseline_with_no_measures_is_not_found_and_an_empty_company_has_nothing(world):
    c = login(world, "co-none")
    assert c.get(f"{BASE}/baselines/{BID}/requests").json()["requests"] == []  # no kpis.json yet: nothing asked
    assert c.post(f"{BASE}/baselines/{BID}/requests").status_code == 404


def test_two_industries_and_one_person_alone(world):
    for company in ("co-a", "co-b", "co-solo"):
        seed(world, company)
        assert len(send(login(world, company, name=f"Org {company}"))) == 4


def test_another_companys_baseline_is_unreachable(world):
    seed(world, "co-a")
    other = login(world, "co-b")
    assert other.get(f"{BASE}/baselines/{BID}/requests").json()["requests"] == []  # co-b has no such baseline
    assert other.post(f"{BASE}/baselines/{BID}/requests").status_code == 404
    token = token_of(send(login(world, "co-a", name="Org a"))["Tom Reyes"])
    assert RequestStore(world.plane("co-b"), BID).all() == []
    assert visitor(world, token).post(f"{BASE}/answer/form").status_code == 200  # the link reaches co-a's plane only


def test_a_role_without_access_a_signed_out_caller_and_a_switched_off_module_are_refused(world):
    seed(world)
    assert login(world, "co-a", name="Plain participant", roles=("participant",)).get(f"{BASE}/baselines/{BID}/requests").status_code == 403
    assert visitor(world).get(f"{BASE}/baselines/{BID}/requests").status_code in (401, 403)
    assert visitor(world).post(f"{BASE}/baselines/{BID}/requests").status_code in (401, 403)
    assert login(world, "co-off").get(f"{BASE}/baselines/{BID}/requests").status_code == 403
    token = token_of(send(login(world, "co-a", name="Org a"))["Tom Reyes"])
    world.app.state.entitlements.set_module("co-a", "m2_baseline", False)
    assert visitor(world, token).post(f"{BASE}/answer/form").status_code in (403, 404)  # same refusal as anyone
    world.app.state.entitlements.set_module("co-a", "m2_baseline", True)


def test_a_traversal_baseline_id_finds_nothing(world):
    seed(world)
    c = login(world, "co-a")
    assert c.get(f"{BASE}/baselines/..%2F..%2Fother/requests").status_code in (404, 403)
    assert c.get(f"{BASE}/baselines/a.b/requests").status_code == 404
