"""Sign-off privacy (fix E): a restricted measure never shows in the review, the audit or any action for someone not named on
it; the email link comes from the configured base; reopen is for organisers only; sending skips owners of hidden measures.
One check per route, so removing any single filter fails a test. Synthetic data; throwaway test accounts."""
import json

import pytest

from m2_kit import login
from test_m2_requests_kit import BASE as RBASE, BID as RBID, KPIS, kpi, seed as seed_requests, send, token_of
from test_m2_requests_privacy import answer_all, visitor, write_baseline
from test_m2_signoff_kit import BID, Team, answer, seed, standard_answers, standard_kpis

SECRET = ("SECRETNAME", "SECRETSRC")
ADMIN = "hana"


def restricted_world(world):
    kpis = standard_kpis()
    kpis[0] = {**kpis[0], "name": "Bonus pool SECRETNAME", "governance": {"personal": "yes", "sensitive": True, "may_see": []}}
    other = {**answer("K1", tracked="no", by="Test Process Pia"), "id": "z"}
    seed(world, kpis=kpis, answers=[answer("K1", source="SECRETSRC"), other, *standard_answers()[1:]])
    t = Team(world)
    admin = t.c[ADMIN]  # the company admin sees everything: makes the audit entries about K1
    assert admin.post(t.url("/signoff/settle"), json={"kpi_id": "K1", "field": "tracked_today", "value": "no"}).status_code == 200
    return t


def viewers(t):
    return {"analyst": t.analyst, "sponsor": t.c["sam"], "owner": t.c["bea"]}


def leaks(text: str) -> bool:
    return any(s in text for s in SECRET) or '"K1"' in text


@pytest.mark.parametrize("who", ["analyst", "sponsor", "owner"])
def test_review_shows_nothing_of_a_hidden_measure_and_is_never_ready(world, who):
    t = restricted_world(world)
    r = viewers(t)[who].get(t.url("/review"))
    assert r.status_code == 200 and not leaks(r.text)
    v = r.json()
    assert [k["id"] for k in v["kpis"]] == ["K2", "K3"] and all(c["kpi_id"] != "K1" for c in v["coming"])
    assert v["all_visible"] is False and v["can_countersign"] is False and v["restricted_count"] == 1 and "restricted from you" in v["note"]
    assert t.c[ADMIN].get(t.url("/review")).json()["all_visible"] is True


@pytest.mark.parametrize("who", ["analyst", "sponsor", "owner"])
def test_the_audit_leaves_out_entries_about_a_hidden_measure(world, who):
    t = restricted_world(world)
    full = t.c[ADMIN].get(t.url("/audit")).json()
    assert any(e.get("kpi_id") == "K1" for e in full["entries"])
    r = viewers(t)[who].get(t.url("/audit"))
    assert r.status_code == 200 and not leaks(r.text) and r.json()["intact"] is True


ACTIONS = [("put", "/review/K1", {"next_step": "x"}), ("post", "/review/K1/accept", None), ("post", "/review/K1/owner", {"part": "business", "name": "x"}),
           ("post", "/signoff/settle", {"kpi_id": "K1", "field": "tracked_today", "value": "no"}),
           ("post", "/confirm", {"kpi_id": "K1", "part": "business"})]


@pytest.mark.parametrize("who", ["analyst", "sponsor", "owner"])
@pytest.mark.parametrize("verb,path,body", ACTIONS)
def test_every_action_on_a_hidden_measure_is_not_found(world, who, verb, path, body):
    t = restricted_world(world)
    before = t.c[ADMIN].get(t.url("/audit")).json()["entries"]
    r = getattr(viewers(t)[who], verb)(t.url(path), **({"json": body} if body is not None else {}))
    sponsor_only = path.endswith(("/accept", "/owner", "/settle")) and who != "sponsor"  # the route refuses these roles first
    assert r.status_code == 403 and not leaks(r.text) and (sponsor_only or r.json()["message"] == "This measure is restricted to its named people.")  # P3: plain, not a bare 404
    assert t.c[ADMIN].get(t.url("/audit")).json()["entries"] == before  # and nothing was recorded


def test_the_settle_audit_holds_the_choice_id_only(world):
    t = restricted_world(world)
    e = next(e for e in t.c[ADMIN].get(t.url("/audit")).json()["entries"] if e["action"] == "settle")
    assert e["detail"] == "settled tracked today" and e["choice"] == "no"


def test_someone_who_cannot_see_everything_cannot_countersign(world):
    t = restricted_world(world)
    r = t.c["sam"].post(t.url("/countersign"))
    assert r.status_code == 409 and r.json()["error"] == "not_confirmed" and not leaks(r.text)  # A-044: not blocked for being hidden


def test_a_person_named_on_the_measure_sees_it(world):
    t = restricted_world(world)
    path = world.plane("co-a").path("intents", "m2_baseline", BID, "kpis.json")
    ks = json.loads(path.read_text())
    ks[0]["governance"]["may_see"] = ["Test Sponsor Sam"]
    path.write_text(json.dumps(ks))
    v = t.c["sam"].get(t.url("/review")).json()
    assert "K1" in [k["id"] for k in v["kpis"]] and v["all_visible"] is True


# ---- the email link -----------------------------------------------------------------------------------------------------
def test_the_email_link_uses_the_configured_base_and_ignores_a_spoofed_origin(world, monkeypatch):
    seed_requests(world)
    org = login(world, "co-a")
    monkeypatch.setenv("SH_PUBLIC_BASE_URL", "https://harbor.example.test/")
    out = org.post(f"{RBASE}/baselines/{RBID}/requests", headers={"origin": "https://evil.example"}).json()
    body = json.dumps(out)
    assert "evil.example" not in body and "https://harbor.example.test/answer/" in body
    rid = out["sent"][0]["id"]
    ok = org.post(f"{RBASE}/baselines/{RBID}/requests/{rid}/relink", headers={"origin": "https://harbor.example.test"}).json()
    assert "https://harbor.example.test/answer/" in json.dumps(ok)


def test_without_a_configured_base_the_servers_own_address_is_used_and_a_spoofed_origin_is_ignored(world, monkeypatch):
    monkeypatch.delenv("SH_PUBLIC_BASE_URL", raising=False)
    seed_requests(world)
    org = login(world, "co-a")
    body = json.dumps(org.post(f"{RBASE}/baselines/{RBID}/requests", headers={"origin": "https://evil.example"}).json())
    assert "evil.example" not in body and "http://testserver/answer/" in body


# ---- reopen: organiser roles only (the same as relink) -----------------------------------------------------------------
@pytest.mark.parametrize("role", ["participant", "owner"])
def test_a_participant_cannot_reopen(world, role):
    seed_requests(world)
    write_baseline(world)
    org = login(world, "co-a")
    tom = send(org)["Tom Reyes"]
    answer_all(visitor(world, token_of(tom)))
    r = login(world, "co-a", "Plain Person", (role,)).post(f"{RBASE}/baselines/{RBID}/requests/{tom['id']}/reopen")
    assert r.status_code == 403
    assert visitor(world).post(f"{RBASE}/baselines/{RBID}/requests/{tom['id']}/reopen").status_code in (401, 403)  # a guest
    assert org.post(f"{RBASE}/baselines/{RBID}/requests/{tom['id']}/reopen").status_code == 200


# ---- sending skips owners of measures the sender cannot see ------------------------------------------------------------
def test_sending_as_the_analyst_skips_owners_of_hidden_measures_and_says_so(world):
    hidden = {**kpi("k3", "Bonus pool", data="Wei Chen"), "governance": {"personal": "yes", "sensitive": True, "may_see": []}}
    seed_requests(world, kpis=[*KPIS[:2], hidden])
    ann = login(world, "co-a", "Ann Analyst", ("analyst",))
    out = ann.post(f"{RBASE}/baselines/{RBID}/requests").json()
    assert out["note"] == "Some requests can only be sent by someone who can see those measures." and "Wei Chen" not in json.dumps(out)
    org = login(world, "co-a")
    rows = org.get(f"{RBASE}/baselines/{RBID}/requests").json()
    assert "Wei Chen" in rows["not_yet_asked"] and rows["summary"]["asked"] == 3  # no link was made for the hidden owner
    assert org.post(f"{RBASE}/baselines/{RBID}/requests").json()["note"] is None
