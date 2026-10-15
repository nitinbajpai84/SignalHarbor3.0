"""M2-E4: the ready-to-build gate, what is signed (two documents and their fingerprints), the hand-off's new keys, "leave out", and the one download.
Synthetic family-office wording only. The gate is worked out over every measure and row, so it is the same for everyone."""
import io
import json
import zipfile

import pytest

from m2_kit import login
from modules.m2_baseline.domain import ambiguities as A
from modules.m2_baseline.domain import gate as GT
from modules.m2_baseline.domain import handoff as H
from modules.m2_baseline.domain import technical as T
from modules.m2_baseline.store import documents as DOC
from modules.m2_baseline.store.signoff import read_baseline_outcome
from test_m2_signoff_kit import BID, Team, confirm_all, kpi, me, seed, sign_both, standard_kpis

SECRET_NAME, SECRET_CALC = "Executive pay", "Restricted pay calculation"


def restricted_kpi(ready=True):
    k = kpi("K4", SECRET_NAME, ready=False)
    k["governance"] = {"personal": "yes", "sensitive": True, "may_see": [me("bea"), me("dan"), me("pia")]}
    if ready:
        for part, v in (("sources", ["S01"]), ("fields", ["F001"]), ("calculation", SECRET_CALC)):
            k = T.set_part(k, part, v, "stated", "Test Data Dan")
        k = T.confirm(k, "Test Data Dan")
    return k


def with_risk(k, status="accepted", kind="period", reason="We will use month end until the fund office says otherwise."):
    k = A.with_ambiguities(k, [A.make(kind, f"Which period does {k['name']} use?", "Month end or quarter end?", f"{k['name']}: period")])
    aid = k["ambiguities"][0]["id"]
    return A.accept(k, aid, reason, "Test Sponsor Sam") if status == "accepted" else k


def ready_team(world, kpis=None, company="co-a", **kw):
    seed(world, company, kpis=kpis if kpis is not None else standard_kpis(), **kw)
    return Team(world, company)


def ready_to_sign(team, ids=("K1", "K2")):
    confirm_all(team, ids)
    return team


def review(team, who="hana"):
    r = (team.analyst if who == "analyst" else team.c[who]).get(team.url("/review"))
    assert r.status_code == 200, r.text
    return r.json()


def zip_of(r):
    assert r.status_code == 200, r.text
    return zipfile.ZipFile(io.BytesIO(r.content))


def sheet_text(data: bytes) -> str:
    z = zipfile.ZipFile(io.BytesIO(data))
    return " ".join(z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("xl/worksheets/"))


# ---- the gate ---------------------------------------------------------------------------------------------------------------------------

def test_signing_passes_when_everything_holds_and_the_checklist_says_so(world):
    team = ready_to_sign(ready_team(world))
    g = review(team)["gate"]
    assert g["ok"] and g["measures"] == {**g["measures"], "ready": 3, "total": 3} and g["glossary"]["ok"] and g["governance"]["ok"] and g["open"]["n"] == 0
    assert g["fix"] == {"measures": "baselines", "glossary": "glossary", "governance": "governance", "open": "questions"} and g["refusal"] == ""
    a, b = sign_both(team)
    assert a.status_code == 200 and b.status_code == 200 and b.json()["status"] == "signed"


def test_the_gate_refuses_a_measure_that_is_not_ready_to_build(world):
    k2 = kpi("K2", "Exposure concentration", ready=False)
    team = ready_to_sign(ready_team(world, [kpi("K1", "Capital call timeliness"), k2]))
    r = team.c["sam"].post(team.url("/countersign"))
    assert r.status_code == 409 and r.json()["error"] == "not_ready_to_build"
    assert "1 of 2 measures are ready to build" in r.json()["message"]
    item = next(i for i in review(team)["gate"]["measures"]["items"] if i["kpi_id"] == "K2")
    assert not item["ready"] and any("technical definition" in x for x in item["reasons"])


def test_the_gate_refuses_a_glossary_nobody_reviewed(world):
    team = ready_to_sign(ready_team(world, glossary=False))
    r = team.c["sam"].post(team.url("/countersign"))
    assert r.status_code == 409 and r.json()["error"] == "not_ready_to_build" and "glossary" in r.json()["message"]
    assert review(team)["gate"]["glossary"]["ok"] is False


def test_the_gate_refuses_governance_nobody_decided(world):
    cat = {"sources": [{"Source ID": {"value": "S01", "mark": "stated", "by": "x"}, "Source name": {"value": "Custodian portal", "mark": "stated", "by": "x"}}],
           "tables": [], "fields": [], "extractions": [], "kpis": []}
    team = ready_to_sign(ready_team(world, catalogue=cat))
    r = team.c["sam"].post(team.url("/countersign"))
    assert r.status_code == 409 and r.json()["error"] == "not_ready_to_build" and "governance is not decided" in r.json()["message"]
    assert review(team)["gate"]["governance"]["ok"] is False


def test_the_gate_refuses_while_a_question_is_open_and_lets_an_accepted_one_through(world):
    open_k = with_risk(kpi("K1", "Capital call timeliness"), status="open")
    team = ready_to_sign(ready_team(world, [open_k, kpi("K2", "Exposure concentration")]))
    r = team.c["sam"].post(team.url("/countersign"))
    assert r.status_code == 409 and r.json()["error"] == "not_ready_to_build" and "1 open question remains" in r.json()["message"]
    assert review(team)["gate"]["open"]["n"] == 1


def test_an_accepted_question_is_a_known_risk_in_the_hand_off(world):
    team = ready_to_sign(ready_team(world, [with_risk(kpi("K1", "Capital call timeliness")), kpi("K2", "Exposure concentration")]))
    a, b = sign_both(team)
    assert b.status_code == 200 and b.json()["status"] == "signed", (a.text, b.text)
    rec = team.c["hana"].get(team.url("/handoff")).json()
    (risk,) = rec["ambiguities"]
    assert risk["kpi_id"] == "K1" and risk["status"] == "accepted" and risk["by"] == "Test Sponsor Sam" and "month end" in risk["reason"]
    assert set(risk) >= {"kpi_id", "id", "kind", "text", "question", "where", "status", "reason", "by", "at"}
    assert not [a for a in rec["ambiguities"] if a["status"] == "open"]


def test_an_empty_baseline_cannot_be_signed_and_says_why(world):
    team = ready_team(world, [])
    g = review(team)["gate"]
    assert g["ok"] is False and "no measures" in g["refusal"]
    assert team.c["sam"].post(team.url("/countersign")).status_code == 409


def test_the_gate_is_the_same_for_everyone_and_a_hidden_measure_says_so_without_detail(world):
    team = ready_to_sign(ready_team(world, [*standard_kpis()[:2], restricted_kpi(ready=False)]), ("K1", "K2"))
    full, sam = review(team, "hana")["gate"], review(team, "sam")["gate"]
    assert full["ok"] is False and sam["ok"] is False and full["restricted"] is False and sam["restricted"] is True   # the same verdict, a different view of it
    assert {i["kpi_id"] for i in full["measures"]["items"]} == {"K1", "K2", "K4"} and {i["kpi_id"] for i in sam["measures"]["items"]} == {"K1", "K2"}
    assert sam["measures"]["ready"] == 2 and sam["measures"]["total"] == 2 and "something restricted is still open" in sam["refusal"]
    assert SECRET_NAME not in json.dumps(sam) and SECRET_CALC not in json.dumps(sam)
    analyst = review(team, "analyst")["gate"]
    assert analyst["ok"] is False and analyst["restricted"] is True and SECRET_NAME not in json.dumps(analyst)
    # the refusal a signature gets is the signer's own view of the same verdict
    confirm_all(team, ("K4",))
    r = team.c["sam"].post(team.url("/countersign"))
    assert r.status_code == 409 and r.json()["error"] == "not_ready_to_build" and "restricted" in r.json()["message"] and SECRET_NAME not in r.text
    assert "2 of 3 measures are ready to build" in team.c["hana"].post(team.url("/countersign")).json()["message"]


# ---- leave out --------------------------------------------------------------------------------------------------------------------------

def unready_team(world):
    return ready_to_sign(ready_team(world, [kpi("K1", "Capital call timeliness"), kpi("K2", "Exposure concentration", ready=False)]), ("K1", "K2"))


def test_leave_out_needs_the_organiser_or_a_sponsor_and_a_reason(world):
    team = unready_team(world)
    url = team.url("/review/K2/leave-out")
    assert team.analyst.post(url, json={"reason": "Not needed."}).status_code == 403          # an analyst's role cannot
    assert team.c["bea"].post(url, json={"reason": "Not needed."}).status_code == 403          # nor an owner's
    assert team.c["sam"].post(url, json={"reason": "  "}).status_code == 422 and team.c["sam"].post(url, json={}).status_code == 422
    assert team.c["sam"].post(team.url("/review/NOPE/leave-out"), json={"reason": "x"}).status_code == 404
    assert team.c["sam"].post(team.url("/countersign")).status_code == 409                    # still refused
    r = team.c["sam"].post(url, json={"reason": "The fund office is replacing this report next year."})
    assert r.status_code == 200 and r.json()["gate"]["left_out"] == [{"kpi_id": "K2", "name": "Exposure concentration",
                                                                     "reason": "The fund office is replacing this report next year.", "by": me("sam"),
                                                                     "at": r.json()["gate"]["left_out"][0]["at"]}]
    assert r.json()["gate"]["ok"] and r.json()["gate"]["measures"]["total"] == 1


def test_a_left_out_measure_goes_to_the_hand_off_with_its_reason_and_signing_passes(world):
    team = unready_team(world)
    team.c["hana"].post(team.url("/review/K2/leave-out"), json={"reason": "Replaced next year."})
    a, b = sign_both(team)
    assert a.status_code == 200 and b.json()["status"] == "signed"
    rec = team.c["hana"].get(team.url("/handoff")).json()
    assert [(r["kpi_id"], r["reason"], r["by"]) for r in rec["left_out"]] == [("K2", "Replaced next year.", me("hana"))]
    assert "K2" not in rec["technical"] and all(e["kpi_id"] != "K2" for e in rec["glossary"])
    assert team.c["hana"].post(team.url("/review/K2/bring-back")).status_code == 409           # signed: read-only


def test_a_measure_can_be_brought_back_before_signing(world):
    team = unready_team(world)
    team.c["sam"].post(team.url("/review/K2/leave-out"), json={"reason": "Replaced next year."})
    r = team.c["sam"].post(team.url("/review/K2/bring-back"))
    assert r.status_code == 200 and r.json()["gate"]["left_out"] == [] and r.json()["gate"]["ok"] is False
    assert team.c["sam"].post(team.url("/review/K2/bring-back")).status_code == 409           # not left out any more


def test_nobody_leaves_out_a_measure_they_may_not_see(world):
    team = ready_team(world, [*standard_kpis()[:2], restricted_kpi()])
    r = team.c["sam"].post(team.url("/review/K4/leave-out"), json={"reason": "No."})          # the sponsor is not named for it
    assert r.status_code == 403 and SECRET_NAME not in r.text


# ---- what is signed: two documents, fingerprints ------------------------------------------------------------------------------------------

def signed_team(world, kpis=None, company="co-a", ids=("K1", "K2"), **kw):
    team = ready_to_sign(ready_team(world, kpis, company, **kw), ids)
    a, b = sign_both(team)
    assert b.status_code == 200 and b.json()["status"] == "signed", (a.text, b.text)
    return team


def test_both_documents_are_fingerprinted_at_signing_and_a_rebuild_gives_the_same_fingerprint(world):
    team = signed_team(world)
    doc = json.loads(world.plane("co-a").path("intents", "m2_baseline", BID, "signoff.json").read_text())
    docs = doc["versions"][-1]["documents"]
    assert set(docs) == {"business_glossary", "data_catalogue"} and all(len(d["sha256"]) == 64 and d["built_at"] for d in docs.values())
    again = DOC.fingerprints(world.plane("co-a"), BID, {}, "a later time")
    assert {k: v["sha256"] for k, v in again.items()} == {k: v["sha256"] for k, v in docs.items()}   # same content, same fingerprint
    rec = team.c["hana"].get(team.url("/handoff")).json()
    assert rec["documents"] == docs
    listed = review(team)["documents"]
    assert [d["name"] for d in listed] == ["Business glossary", "Data catalogue"] and all(d["unchanged"] for d in listed)


def test_a_later_change_to_either_document_is_detected(world):
    team = signed_team(world)
    plane = world.plane("co-a")
    path = plane.path("intents", "m2_baseline", BID, "glossary.json")
    g = json.loads(path.read_text())
    g["entries"][0]["business_definition"]["value"] = "Quietly reworded after signing."
    path.write_text(json.dumps(g))
    assert {d["id"]: d["unchanged"] for d in review(team)["documents"]} == {"business_glossary": False, "data_catalogue": True}
    kp = plane.path("intents", "m2_baseline", BID, "kpis.json")
    ks = json.loads(kp.read_text())
    ks[0]["technical"]["calculation"]["value"] = "1. Take something else."
    kp.write_text(json.dumps(ks))
    assert {d["id"]: d["unchanged"] for d in review(team)["documents"]} == {"business_glossary": False, "data_catalogue": False}


def test_fingerprints_cover_the_full_content_not_one_persons_view(world):
    team = signed_team(world, [*standard_kpis()[:2], restricted_kpi()], ids=("K1", "K2", "K4"))
    shown = {d["id"]: d["sha256"] for d in review(team, "analyst")["documents"]}
    assert shown == {d["id"]: d["sha256"] for d in review(team, "hana")["documents"]}          # one fingerprint per document, for everyone


def test_a_signed_baseline_refuses_writes(world):
    team = signed_team(world)
    assert team.c["sam"].post(team.url("/review/K1/leave-out"), json={"reason": "late"}).status_code == 409
    assert team.c["sam"].put(team.url("/review/K1"), json={"next_step": "x"}).status_code == 409


# ---- the hand-off's new keys --------------------------------------------------------------------------------------------------------------

def test_the_hand_off_carries_the_new_keys_in_the_agreed_shapes(world):
    team = signed_team(world, [with_risk(kpi("K1", "Capital call timeliness")), kpi("K2", "Exposure concentration")])
    rec = team.c["hana"].get(team.url("/handoff")).json()
    contract = H.load_outcome_contract()
    assert contract["added_keys"] == ["glossary", "technical", "ambiguities", "left_out", "documents"] and not set(contract["added_keys"]) & set(contract["required"])
    assert all(k in rec for k in contract["required"] + contract["added_keys"])
    assert [e["kpi_id"] for e in rec["glossary"]] == ["K1", "K2"] and rec["glossary"][0]["reviewed"]["by"]
    assert set(rec["technical"]) == {"K1", "K2"} and set(rec["technical"]["K1"]) == {*T.PARTS, "confirmed"}
    assert rec["technical"]["K1"]["sources"]["value"] == ["S01"] and rec["technical"]["K1"]["confirmed"]["by"] and rec["left_out"] == []
    assert read_baseline_outcome(world.plane("co-a"), rec["outcome_id"]) == rec


def test_an_old_outcome_without_the_new_keys_still_loads(world):
    team = signed_team(world)
    plane, rec = world.plane("co-a"), team.c["hana"].get(team.url("/handoff")).json()
    old = {k: v for k, v in rec.items() if k not in H.load_outcome_contract()["added_keys"]}
    path = plane.path("intents", "m2_baseline", "outcomes", f"{rec['outcome_id']}.json")
    path.write_text(json.dumps(old))
    assert read_baseline_outcome(plane, rec["outcome_id"]) == old
    r = team.analyst.get(team.url("/handoff"))
    assert r.status_code == 200 and not set(H.load_outcome_contract()["added_keys"]) & set(r.json())   # nothing invented for an old record
    assert team.c["hana"].get(team.url("/handoff")).json() == old


def test_the_hand_off_hides_restricted_content_in_each_new_key(world):
    ks = [with_risk(kpi("K1", "Capital call timeliness")), kpi("K2", "Exposure concentration"), with_risk(restricted_kpi(), reason="Board knows.")]
    team = signed_team(world, ks, ids=("K1", "K2", "K4"))
    full = team.c["hana"].get(team.url("/handoff")).json()
    assert "K4" in full["technical"] and any(e["kpi_id"] == "K4" for e in full["glossary"]) and any(a["kpi_id"] == "K4" for a in full["ambiguities"])
    mine = team.analyst.get(team.url("/handoff")).json()
    assert set(mine["technical"]) == {"K1", "K2"} and all(e["kpi_id"] != "K4" for e in mine["glossary"]) and [a["kpi_id"] for a in mine["ambiguities"]] == ["K1"]
    assert SECRET_NAME not in json.dumps(mine) and SECRET_CALC not in json.dumps(mine)
    named = team.c["bea"].get(team.url("/handoff")).json()                                      # a person on the list does see it
    assert "K4" in named["technical"] and any(a["kpi_id"] == "K4" for a in named["ambiguities"])


def test_a_left_out_reason_that_names_something_hidden_is_withheld(world):
    kp = {"id": "K1"}
    rec = {"catalogue": {t: [] for t in ("sources", "tables", "fields", "extractions", "kpis")}, "process_map": {}, "confirmations": [], "gaps": [],
           "left_out": [{"kpi_id": "K1", "name": "Capital call timeliness", "reason": f"Same as {SECRET_NAME}.", "by": "x", "at": "y"}],
           "ambiguities": [], "glossary": [], "technical": {}, "documents": {}}
    out = H.for_viewer(rec, [{"id": "K1", "name": "Capital call timeliness", "governance": {}}, {"id": "K4", "name": SECRET_NAME, "governance": {}}], {"K1"},
                       H.C.Viewer("Al", frozenset({"analyst"})))
    assert out["left_out"][0]["reason"] == H.WITHHELD and SECRET_NAME not in json.dumps(out)


# ---- the one download ------------------------------------------------------------------------------------------------------------------------

def test_the_signed_bundle_has_the_right_files_and_says_what_was_signed(world):
    team = signed_team(world)
    r = team.c["hana"].get(team.url("/signoff/bundle"))
    assert r.headers["content-type"] == "application/zip" and "signed-baseline.zip" in r.headers["content-disposition"]
    z = zip_of(r)
    assert sorted(z.namelist()) == ["business-glossary.html", "business-glossary.xlsx", "data-catalogue.xlsx", "read-me-first.html"]
    page = z.read("read-me-first.html").decode()
    docs = json.loads(world.plane("co-a").path("intents", "m2_baseline", BID, "signoff.json").read_text())["versions"][-1]["documents"]
    assert "Signed: version 1" in page and me("sam") in page and me("hana") in page and all(d["sha256"] in page for d in docs.values())
    assert "Draft, not signed" not in page and "Business glossary" in page and "Data catalogue" in page
    assert "Known risks accepted" in page and "Left out of this baseline" in page
    assert "Signed: version 1" in z.read("business-glossary.html").decode() and "Signed: version 1" in sheet_text(z.read("business-glossary.xlsx"))
    book = zipfile.ZipFile(io.BytesIO(z.read("data-catalogue.xlsx")))
    names = book.read("xl/workbook.xml").decode()
    assert "Governance" in names and "Technical definitions" in names                          # all its sheets


def test_the_bundle_is_built_for_the_viewer_and_holds_nothing_restricted_for_an_analyst(world):
    ks = [kpi("K1", "Capital call timeliness"), kpi("K2", "Exposure concentration"), with_risk(restricted_kpi(), reason="Board knows.")]
    team = signed_team(world, ks, ids=("K1", "K2", "K4"))
    full = zip_of(team.c["hana"].get(team.url("/signoff/bundle")))
    assert SECRET_NAME in full.read("business-glossary.html").decode() and SECRET_CALC in sheet_text(full.read("data-catalogue.xlsx"))
    mine = zip_of(team.analyst.get(team.url("/signoff/bundle")))
    for name in mine.namelist():
        text = sheet_text(mine.read(name)) if name.endswith(".xlsx") else mine.read(name).decode()
        assert SECRET_NAME not in text and SECRET_CALC not in text and "Board knows" not in text, name
    assert "Your copy shows only what you may see" in mine.read("read-me-first.html").decode()


def test_a_draft_bundle_is_marked_on_every_document(world):
    team = ready_to_sign(ready_team(world, [kpi("K1", "Capital call timeliness"), kpi("K2", "Exposure concentration", ready=False)]))
    r = team.analyst.get(team.url("/signoff/bundle"))
    assert "draft-baseline.zip" in r.headers["content-disposition"]
    z = zip_of(r)
    assert sorted(z.namelist()) == ["business-glossary.html", "business-glossary.xlsx", "data-catalogue.xlsx", "read-me-first.html"]
    for name in z.namelist():
        text = sheet_text(z.read(name)) if name.endswith(".xlsx") else z.read(name).decode()
        assert "Draft, not signed" in text, name
    assert "This is a draft" in z.read("read-me-first.html").decode()


def test_the_bundle_for_a_role_without_access_is_refused(world):
    team = ready_to_sign(ready_team(world))
    assert team.c["bea"].get(team.url("/signoff/bundle")).status_code == 403                    # an owner's role does not download the bundle


def test_the_bundle_for_an_empty_company_is_a_marked_draft(world):
    team = ready_team(world, [], "co-none")
    z = zip_of(team.c["hana"].get(team.url("/signoff/bundle")))
    assert "Draft, not signed" in z.read("read-me-first.html").decode() and "no measures" in z.read("read-me-first.html").decode()


@pytest.mark.parametrize("company", ["co-a", "co-b"])
def test_two_industries_sign_and_download_the_same_way(world, company):
    team = signed_team(world, company=company)
    assert review(team)["status"] == "signed" and review(team)["gate"]["ok"]
    assert len(zip_of(team.c["hana"].get(team.url("/signoff/bundle"))).namelist()) == 4


def test_nobody_reads_another_companys_bundle(world):
    seed(world, "co-a", kpis=standard_kpis())
    other = login(world, "co-b", "Other Sam", ("sponsor",))
    assert other.get(f"/api/modules/m2_baseline/baselines/{BID}/signoff/bundle").status_code in (403, 404)


def test_the_gate_text_names_no_measure_in_its_refusal(world):
    assert "Capital" not in GT.refusal(1, 3, False, False, 2) and GT.refusal(0, 3, True, True, 0) == ""


# ---- review round: nothing changes between the two signatures ---------------------------------------------------------------------------

def test_nothing_can_change_between_the_two_signatures_and_the_first_fingerprints_stand(world):
    team = ready_to_sign(ready_team(world))
    assert team.c["sam"].post(team.url("/countersign")).status_code == 200
    plane = world.plane("co-a")
    path = plane.path("intents", "m2_baseline", BID, "signoff.json")
    first = json.loads(path.read_text())["versions"][-1]["documents"]
    r = team.c["hana"].put(team.url("/glossary/entries/K1"), json={"choice": "edited", "text": "Quietly reworded between the signatures."})
    assert r.status_code == 409 and "Signing has started" in r.json()["message"]
    assert team.c["hana"].put(team.url("/review/K1"), json={"next_step": "x"}).status_code == 409
    assert team.c["hana"].post(team.url("/review/K1/leave-out"), json={"reason": "late"}).status_code == 409
    assert team.c["hana"].post(team.url("/countersign")).json()["status"] == "signed"
    assert json.loads(path.read_text())["versions"][-1]["documents"] == first          # never overwritten


def test_a_change_that_got_past_the_guard_stops_the_second_signature(world):
    team = ready_to_sign(ready_team(world))
    team.c["sam"].post(team.url("/countersign"))
    gp = world.plane("co-a").path("intents", "m2_baseline", BID, "glossary.json")
    g = json.loads(gp.read_text())
    g["entries"][0]["business_definition"]["value"] = "Changed behind the guard."
    gp.write_text(json.dumps(g))
    r = team.c["hana"].post(team.url("/countersign"))
    assert r.status_code == 409 and r.json()["error"] == "changed_since_signing" and "business glossary" in r.json()["message"]


def test_the_answer_link_guard_also_refuses_once_signing_has_started(world):
    from modules.m2_baseline.api.signed_guard import refuse_if_signed
    from modules.m2_baseline.store.baseline import Locked
    team = ready_to_sign(ready_team(world))
    refuse_if_signed(world.plane("co-a"), BID)
    team.c["sam"].post(team.url("/countersign"))
    with pytest.raises(Locked, match="Signing has started"):
        refuse_if_signed(world.plane("co-a"), BID)


def _risky(k):  # a question about the catalogue's source S01
    return A.with_ambiguities(k, [A.make("source", "Is the portal feed complete?", "Which feed?", "Source: portal", refs=[{"tab": "sources", "id": "S01"}])])


def test_an_open_question_on_a_left_out_measure_still_blocks_when_its_row_is_used_by_a_measure_that_counts(world):
    team = ready_to_sign(ready_team(world, [kpi("K1", "Capital call timeliness"), _risky(kpi("K2", "Exposure concentration"))]))   # K1 uses S01
    team.c["sam"].post(team.url("/review/K2/leave-out"), json={"reason": "Replaced."})
    assert review(team)["gate"]["open"]["n"] == 1 and not review(team)["gate"]["ok"]


def test_an_open_question_on_a_left_out_measure_is_dropped_when_no_measure_that_counts_uses_its_row(world):
    elsewhere = T.confirm(T.set_part(kpi("K1", "Capital call timeliness"), "sources", ["S77"], "stated", "Test Data Dan"), "Test Data Dan")
    team = ready_to_sign(ready_team(world, [elsewhere, _risky(kpi("K2", "Exposure concentration"))]))
    team.c["sam"].post(team.url("/review/K2/leave-out"), json={"reason": "Replaced."})
    assert review(team)["gate"]["open"]["n"] == 0


def test_the_personal_data_gap_kind_is_still_built_by_the_gap_logic():
    contract = H.load_outcome_contract()
    view = {"id": "K1", "name": "Pay", "review": None, "source": {"status": "stated"}, "sensing": [], "parts": [],
            "tracking": {"mark": "stated", "today": True, "label": ""}}
    gaps = H.build_gaps(contract, [view], {t: [] for t in ("sources", "tables", "fields", "extractions", "kpis")}, {"K1": {"personal": "not_sure"}})
    assert [(g["type"], g["kpi_id"]) for g in gaps] == [("personal_undecided", "K1")]
