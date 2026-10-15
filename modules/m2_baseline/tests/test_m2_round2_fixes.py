"""CRITIC-M2 round 2 fixes: N1 (hand-off leak), N2 (an honest "I don't know" counts), N3 (sponsor signs with a hidden measure),
N4 (account owners confirm), N5 and P3 (field and "not sure" visibility), P4 (the organiser is told). Synthetic data."""
import json

import pytest

from m2_kit import BASE, login
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import readiness as R
from modules.m2_baseline.domain import signoff as S
from modules.m2_baseline.domain.provenance import prov
from modules.m2_baseline.domain.questionnaire import BLANK, clean_answers, load_questionnaire, with_blanks
from test_m2_signoff_kit import BID, Team, answer, kpi, me, seed, standard_answers, standard_kpis
from test_m2_worklist import confirm as confirm_kpi, seed_charter, start

SECRET = ("SECRETNAME", "SECRETSRC", "salary_band", "SECRETSTEP")
OWNERS = [me("bea"), me("dan"), me("pia")]


def cell(v, by="Test Data Dan"):
    return prov(v, "stated", by, "meeting")


def pay_catalogue():
    return {"sources": [
        {"Source ID": cell("S01"), "Source name": cell("SECRETSRC"), "Contains personal data?": cell("Yes"), "Who may see it": cell(", ".join(OWNERS))},
        {"Source ID": cell("S02"), "Source name": cell("Open ledger"), "Contains personal data?": cell("No")}],
        "tables": [{"Item ID": cell("T01"), "Source ID": cell("S01"), "Related KPIs": cell("K1")},
                   {"Item ID": cell("T02"), "Source ID": cell("S02"), "Related KPIs": cell("K2")}],
        "fields": [{"Item ID": cell("T01"), "Field ID": cell("F001"), "Field name": cell("salary_band"), "Feeds KPI": cell("K1"), "Personal data class": cell("Personal data")},
                   {"Item ID": cell("T02"), "Field ID": cell("F002"), "Field name": cell("ledger_date"), "Feeds KPI": cell("K2"), "Personal data class": cell("Neither")}],
        "extractions": [], "kpis": []}


def signed_world(world):
    """K1 is restricted to its three owners (the sponsor is not named); everything is confirmed; the sponsor then the admin sign."""
    kpis = standard_kpis()
    kpis[0] = {**kpis[0], "name": "Bonus pool SECRETNAME", "governance": {"personal": "yes", "sensitive": True, "may_see": OWNERS}}
    pmap = {"K1": {"lanes": ["Pay"], "steps": [{"id": "s1", "lane": "Pay", "text": "SECRETSTEP", "order": 1, "manual": True,
                                                  "confirmed": True, "from": "x", "state": "validated", "by": OWNERS[2]}]}}
    seed(world, kpis=kpis, catalogue=pay_catalogue(), process_map=pmap)
    t = Team(world)
    t.c["sam"].put(t.url("/review/K2"), json={"next_step": "Ask the custodian", "project": "Hub", "tentative_date": "2027-03-31"})
    assert t.c["sam"].post(t.url("/review/K2/accept")).status_code == 200
    for k in ("K1", "K2"):
        for who, part in (("bea", "definition"), ("dan", "source"), ("pia", "process")):
            assert t.c[who].post(t.url("/confirm"), json={"kpi_id": k, "part": part}).status_code == 200
    return t


def leaks(text: str) -> bool:
    return any(s in text for s in SECRET)


# ---- N3: the sponsor signs for what they can see; the admin signs second -------------------------------------------------
def test_sponsor_signs_with_a_hidden_measure_and_the_admin_signs_second(world):
    t = signed_world(world)
    review = t.c["sam"].get(t.url("/review")).json()
    assert review["all_visible"] is False and review["restricted_count"] == 1 and review["can_countersign"] is True and not leaks(json.dumps(review))
    a = t.c["sam"].post(t.url("/countersign"))
    assert a.status_code == 200 and not leaks(a.text)
    first = a.json()["signatures"][0]
    assert first["slot"] == "sponsor" and first["restricted_covered"] == 1
    assert first["note"] == "covers 1 restricted measure confirmed by their named owners"
    b = t.c["hana"].post(t.url("/countersign"))
    assert b.status_code == 200 and b.json()["status"] == "signed"
    sigs = t.c["hana"].get(t.url("/handoff")).json()["signatures"]
    assert [(s["slot"], s["restricted_covered"]) for s in sigs] == [("sponsor", 1), ("head_of_data", 0)]


def test_the_sponsor_cannot_sign_while_a_hidden_measure_is_unconfirmed(world):
    t = signed_world(world)
    path = world.plane("co-a").path("intents", "m2_baseline", BID, "signoff.json")
    doc = json.loads(path.read_text())
    del doc["versions"][-1]["parts"]["K1"]["process"]
    path.write_text(json.dumps(doc))
    r = t.c["sam"].post(t.url("/countersign"))
    assert r.status_code == 409 and r.json()["error"] == "not_confirmed" and not leaks(r.text)


def test_the_head_of_data_slot_needs_to_see_every_measure():
    c = R.load_contract()
    v = {"version": 1, "status": "open", "countersign": [{"slot": "sponsor", "name": "S", "account_id": "a", "at": "t"}]}
    with pytest.raises(S.SignoffError) as e:
        S.countersign(v, c, {"ready": True, "can_countersign": True}, "H", "b", {"company_admin"}, "now", restricted=1, gate={"ok": True, "refusal": ""}, documents={})
    assert e.value.code == "not_visible"


# ---- N1: the hand-off route filters like every other route -------------------------------------------------------------
@pytest.mark.parametrize("who", ["analyst", "sponsor"])
def test_handoff_leaks_nothing_hidden_to_those_not_named(world, who):
    t = signed_world(world)
    assert t.c["sam"].post(t.url("/countersign")).status_code == 200 and t.c["hana"].post(t.url("/countersign")).status_code == 200
    r = (t.analyst if who == "analyst" else t.c["sam"]).get(t.url("/handoff"))
    assert r.status_code == 200 and not leaks(r.text) and '"K1"' not in r.text
    rec = r.json()
    assert {c["kpi_id"] for c in rec["confirmations"]} == {"K2"} and "K1" not in rec["process_map"]
    assert all(g["kpi_id"] != "K1" for g in rec["gaps"])
    full = t.c["hana"].get(t.url("/handoff")).json()
    assert "SECRETSRC" in json.dumps(full) and "K1" in full["process_map"]  # the admin, who signs for the whole, sees it all


def test_module_3_still_reads_the_full_record_through_the_store(world):
    from modules.m2_baseline.store.signoff import latest_baseline_outcome
    t = signed_world(world)
    t.c["sam"].post(t.url("/countersign"))
    t.c["hana"].post(t.url("/countersign"))
    assert "SECRETSRC" in json.dumps(latest_baseline_outcome(world.plane("co-a"), BID))


# ---- N5 / P3: fields follow their source; "not sure" sources show to the sponsor and admin -------------------------------
def test_analyst_sees_the_fields_of_an_open_source_but_not_of_a_personal_one(world):
    t = signed_world(world)
    cat = t.analyst.get(t.url("/catalogue")).json()
    shown = [f for f in cat["fields"] if not f.get(C.HIDDEN)]
    assert [C.row_id("fields", f) for f in shown] == ["F002"] and len(cat["fields"]) == 2 and "salary_band" not in json.dumps(cat)


def test_not_sure_sources_are_restricted_but_open_to_the_sponsor_and_admin():
    cat = {"sources": [{"Source ID": cell("S05"), "Source name": cell("Custodian"), "Contains personal data?": cell("Not sure"),
                        "Who may see it": cell("Mei Tan")}],  # named people: tied to a restricted list (an unnamed, untied "not sure" one is open: N-B)
           "tables": [], "fields": [], "extractions": [], "kpis": []}
    g = C.guards(cat, {})[("sources", "S05")]
    assert not all(C.allows(x, C.Viewer("Al", frozenset({"analyst"}))) for x in g)
    assert all(C.allows(x, C.Viewer("Sam", frozenset({"sponsor"}))) for x in g)
    assert all(C.allows(x, C.Viewer("Hana", frozenset({"company_admin"}))) for x in g)


# ---- N2: "I don't know" is an answer ---------------------------------------------------------------------------------------
def test_an_unknown_sources_answer_makes_the_derived_answers_unknown_from_the_link():
    q = load_questionnaire()
    out = clean_answers(q, {"sources": {"value": None, "mark": "unknown"}}, "Wei Chen", "answer link")
    for k in ("source", "data_type", "arrival"):
        assert out[k]["mark"] == "unknown" and out[k]["from"] == "answer link"
    full = with_blanks({"owner_name": "Wei Chen", **out}, q)
    assert all(full[k]["from"] != BLANK for k in ("source", "data_type", "arrival"))
    assert R.best([full["source"]])[0] == "unknown"


def test_wei_is_silent_the_sponsor_accepts_with_a_next_step_and_readiness_passes(world):
    seed(world, answers=[answer("K1")])  # K2 (not tracked today) has no answers: its owner is silent
    t = Team(world)
    before = t.c["sam"].get(t.url("/review")).json()
    assert before["ready"] is False
    assert {i["id"] for i in before["items"] if i["required"] and not i["met"]} == {"source", "sensing"}
    t.c["sam"].put(t.url("/review/K2"), json={"next_step": "Call Wei about the exposure feed"})
    assert t.c["sam"].post(t.url("/review/K2/accept")).status_code == 200
    after = t.c["sam"].get(t.url("/review")).json()
    assert after["ready"] is True
    k2 = next(k for k in after["kpis"] if k["id"] == "K2")
    assert k2["source"]["status"] == "unknown" and "Source is unknown" in k2["unknowns"]  # still on the record, never dropped
    conf = next(i for i in after["items"] if i["id"] == "confirmations")["missing"]
    assert conf and all("Exposure" not in m for m in conf)  # an accepted measure needs no confirmation from its silent owner


# ---- N4: accounts with other roles confirm their own parts -----------------------------------------------------------------
@pytest.mark.parametrize("role,name", [("approver", "Tom Approver"), ("participant", "Wei Participant")])
def test_an_owner_whose_account_has_another_role_confirms_their_own_part(world, role, name):
    k = kpi("K1", "Capital call timeliness", owners=("bea", "dan", "pia"))
    k["owners"]["business"] = prov(f"Test {name}", "stated", "Test Business Bea", "meeting")
    seed(world, kpis=[k], answers=[answer("K1"), answer("K1", by=f"Test {name}")])
    c = login(world, "co-a", name, (role,))
    t = Team(world)
    r = c.post(t.url("/confirm"), json={"kpi_id": "K1", "part": "definition"})
    assert r.status_code == 200, r.text
    assert c.post(t.url("/confirm"), json={"kpi_id": "K1", "part": "definition"}).json()["error"] == "already_confirmed"
    assert c.post(t.url("/confirm"), json={"kpi_id": "K1", "part": "source"}).json()["error"] == "not_your_part"  # only their own part
    assert c.post(t.url("/countersign")).status_code == 403  # and nothing else opens up for the role


# ---- P4 ----------------------------------------------------------------------------------------------------------------------
def test_the_organiser_is_told_when_governance_is_not_set(world):
    admin = login(world, "co-a", "Org Admin", ("company_admin",))
    view = start(admin, seed_charter(world))
    for n in ("First measure", "Second measure"):
        view = confirm_kpi(admin, view, name=n)
    assert view["governance_note"] == "2 measures are visible only to you until you set who may see them."
    analyst = login(world, "co-a", "Analyst Al", ("analyst",))
    # R4 P4: the analyst gets the same plain note, worded for someone who is not the organiser, naming no measure
    note = analyst.get(f"{BASE}/baselines/{view['baseline']['id']}").json()["governance_note"]
    assert note == "2 measures are visible only to the organiser until they set who may see them." and "First measure" not in note
    k = view["kpis"][0]["id"]
    r = admin.put(f"{BASE}/baselines/{view['baseline']['id']}/kpis/{k}/governance", json={"may_see": ["Someone Else"]})
    assert r.status_code == 200 and r.json()["governance_note"] == "1 measure is visible only to you until you set who may see it."


# ---- fix round 1 (FIX-I1): link confirm only for owners with no account; hidden-row and gap filters; waiver; control chars -----
def test_the_answer_link_confirms_only_parts_whose_owner_has_no_account():
    c, ks = R.load_contract(), [kpi("K1", "Capital call timeliness")]
    v = {"named": {}, "parts": {}, "status": "open", "countersign": []}
    ks[0]["owners"]["business"]["account_id"] = "acct-bea"
    with pytest.raises(S.SignoffError) as e:
        S.confirm_by_link(v, c, ks, "K1", "definition", me("bea"), "now")
    assert e.value.code == "not_your_part"
    out = S.confirm_by_link(v, c, ks, "K1", "source", me("dan"), "now", [answer("K1")])  # data owner: name only, no account
    assert out["parts"]["K1"]["source"]["via"] == "answer link"


def test_a_cell_with_a_nul_marker_does_not_open_a_source():
    assert "\0" not in C._check_text("Who may see it", "\0analyst, Bea") and C._check_text("x", "a\tb\nc") == "a\tb\nc"
    cat = pay_catalogue()
    cat["sources"][0]["Who may see it"] = cell(C._check_text("Who may see it", "\0analyst"))
    g = C.guards(cat, {})[("sources", "S01")]
    assert not all(C.allows(x, C.Viewer("Analyst Al", frozenset({"analyst"}))) for x in g)


def test_the_sponsors_acceptance_waives_only_a_silent_owner(world):
    k2 = kpi("K2", "Exposure concentration", owners=("bea", "dan", "pia"), tracking="not_tracked")
    seed(world, kpis=[k2], answers=[answer("K2", by=me("dan"))])  # Dan (data owner) answered; Bea and Pia are silent
    t = Team(world)
    t.c["sam"].put(t.url("/review/K2"), json={"next_step": "Ask the custodian"})
    assert t.c["sam"].post(t.url("/review/K2/accept")).status_code == 200
    conf = next(i for i in t.c["sam"].get(t.url("/review")).json()["items"] if i["id"] == "confirmations")["missing"]
    assert len(conf) == 1 and "source" in conf[0].lower()  # Dan's given answer still needs Dan's confirmation


def test_gaps_for_a_hidden_measure_and_a_hidden_row_are_cut_from_the_analysts_handoff():
    from modules.m2_baseline.domain import handoff as H
    cat = pay_catalogue()
    kp = [{**kpi("K1", "Bonus pool SECRETNAME"), "governance": {"personal": "yes", "sensitive": True, "may_see": OWNERS}}, kpi("K2", "Open")]
    gaps = [{"id": "G1", "kpi_id": "K1", "where": "x"}, {"id": "G2", "kpi_id": None, "where": "sources S01: Owner"},
            {"id": "G3", "kpi_id": None, "where": "fields F001: Notes"}, {"id": "G4", "kpi_id": None, "where": "sources S02: Owner"}]
    rec = {"catalogue": cat, "process_map": {}, "confirmations": [], "gaps": gaps}
    out = H.for_viewer(rec, kp, {"K2"}, C.Viewer("Analyst Al", frozenset({"analyst"})))
    assert [g["id"] for g in out["gaps"]] == ["G4"]


def test_kpi_rows_are_cut_to_the_seen_set_even_when_the_catalogue_would_show_them():
    from modules.m2_baseline.domain import handoff as H
    cat = {"sources": [], "tables": [], "fields": [], "extractions": [],
           "kpis": [{"KPI ID": cell("K1"), "KPI name": cell("Shown")}, {"KPI ID": cell("K2"), "KPI name": cell("Cut")}]}
    kp = [kpi("K1", "Shown"), kpi("K2", "Cut")]  # bound by account id with another display name: the name guard would not cut K2
    out = H.for_viewer({"catalogue": cat, "process_map": {}, "confirmations": [], "gaps": []}, kp, {"K1"}, C.Viewer("Al", frozenset({"analyst"})))
    assert [C.row_id("kpis", r) for r in out["catalogue"]["kpis"]] == ["K1"]


def test_ready_and_can_countersign_are_false_for_the_sponsor_when_a_hidden_measure_is_not_ready(world):
    t = signed_world(world)
    path = world.plane("co-a").path("intents", "m2_baseline", BID, "answers.json")
    answers = [a for a in json.loads(path.read_text()) if a.get("kpi_id") != "K1"]
    path.write_text(json.dumps(answers))  # K1 (hidden from the sponsor) now has no answers
    review = t.c["sam"].get(t.url("/review")).json()
    assert review["ready"] is False and review["can_countersign"] is False and not leaks(json.dumps(review))
    r = t.c["sam"].post(t.url("/countersign"))
    assert r.status_code == 409 and "some in measures you cannot see" in r.json()["message"] and not leaks(r.text)
