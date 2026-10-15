"""M2-E3: the governance view (measures, sources, fields), a field's own "who may see it", Lens's proposals, what is undecided, the
Governance sheet. Family-office-free synthetic wording; two industries and an empty company. Everyone is a throwaway test account."""
import json

import yaml
from m2_kit import BASE, login
from test_m2_catalogue_xlsx import read_book

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import governance_view as GV
from modules.m2_baseline.domain import handoff as H
from modules.m2_baseline.domain.provenance import prov
from modules.m2_baseline.store import governance as GS

BID = "d" * 32
AT = "2026-10-03T10:00:00+00:00"
PAT, ALAN, LENA, SAM = "Test Pat Owner", "Test Alan Analyst", "Test Lena Hr", "Test Sam Sponsor"
GOV = f"{BASE}/baselines/{BID}/governance"
CAT = f"{BASE}/baselines/{BID}/catalogue"
ADMIN = C.Viewer(PAT, frozenset({"company_admin"}))
SECRETS = ("Pay review", "HR system", "salary", "Lena")  # what only Lena (and the organiser) may ever see


def cell(v, by=PAT):
    return prov(v, "stated", by, "the questionnaire", at=AT)


def row(tab, rid, cells):
    r = C.new_row(tab, rid)
    r.update({h: cell(v) for h, v in cells.items()})
    return r


def kpis(personal_k3="not_sure"):
    return [
        {"id": "K01", "name": "Capital calls due", "problem_ids": [], "priority": "must", "governance": {"personal": "no", "sensitive": False, "may_see": []},
         "governance_decided": {"by": PAT, "at": AT}},
        {"id": "K02", "name": "Pay review", "problem_ids": [], "priority": "must", "governance": {"personal": "yes", "sensitive": True, "may_see": [LENA]},
         "governance_decided": {"by": PAT, "at": AT}},
        {"id": "K03", "name": "Exposure to one name", "problem_ids": [], "priority": "should", "governance": {"personal": personal_k3, "sensitive": False, "may_see": []}},
    ]


def catalogue():
    return {
        "sources": [row("sources", "S01", {"Source name": "Bank portal", "Contains personal data?": "No"}),
                    row("sources", "S02", {"Source name": "HR system", "Contains personal data?": "Yes", "Who may see it": LENA}),
                    row("sources", "S03", {"Source name": "Custody statements", "Contains personal data?": "Not sure"})],
        "tables": [row("tables", "T01", {"Source ID": "S01", "Name of table, file or document type": "balances", "Related KPIs": "K01"}),
                   row("tables", "T02", {"Source ID": "S02", "Name of table, file or document type": "staff", "Related KPIs": "K02"}),
                   row("tables", "T03", {"Source ID": "S03", "Name of table, file or document type": "custody", "Related KPIs": "K03"})],
        "fields": [row("fields", "F001", {"Item ID": "T01", "Field name as in the source": "closing_balance", "Feeds KPI": "K01", FIELD_CLASS: "Neither"}),
                   row("fields", "F002", {"Item ID": "T01", "Field name as in the source": "due_date", "Feeds KPI": "K01"}),
                   row("fields", "F003", {"Item ID": "T01", "Field name as in the source": "contact_email", "Feeds KPI": "K01"}),
                   row("fields", "F004", {"Item ID": "T02", "Field name as in the source": "salary", "Feeds KPI": "K02", FIELD_CLASS: "Personal data"}),
                   row("fields", "F005", {"Item ID": "T01", "Field name as in the source": "tax_ref", "Feeds KPI": "K01"})],
        "extractions": [], "kpis": [row("kpis", "K01", {}), row("kpis", "K02", {}), row("kpis", "K03", {})],
    }


FIELD_CLASS = "Personal data class"


def seed(world, company="co-a", state="mapping", kpi_rows=None, cat=None):
    plane = world.plane(company)
    folder = plane.path("intents", "m2_baseline", BID)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "baseline.json").write_text(json.dumps({"id": BID, "charter_outcome_id": None, "state": state, "created_at": "2026-10-03"}))
    (folder / "kpis.json").write_text(json.dumps(kpis() if kpi_rows is None else kpi_rows))
    (folder / "answers.json").write_text("[]")
    (folder / "catalogue.json").write_text(json.dumps(catalogue() if cat is None else cat))
    return plane


def add_pack_files(world):
    """industry_a's pack knows a feed field and flags it personal; industry_b's pack says nothing about it."""
    a = world.packs / "industry_a" / "1"
    (a / "feeds.yaml").write_text(yaml.safe_dump({"feeds": {"positions": {"fields": [
        {"id": "closing_balance", "type": "decimal", "required_for": ["K01"], "pii": False},
        {"id": "tax_ref", "type": "string", "required_for": [], "pii": True}]}}}))


def team(world, company="co-a"):
    return {"admin": login(world, company, "Pat Owner", ("company_admin",)), "analyst": login(world, company, "Alan Analyst", ("analyst",)),
            "lena": login(world, company, "Lena Hr", ("analyst",)), "sponsor": login(world, company, "Sam Sponsor", ("sponsor",))}


def flat(view):
    return [m for m in view["measures"]]


def names_in(view, key="fields"):
    return [f["name"] for m in view["measures"] if not m.get("hidden") for f in m[key]]


def ids_in(view):
    return [f["id"] for m in view["measures"] if not m.get("hidden") for f in m["fields"]]


# ---- the view equals what is stored -------------------------------------------------------------------------------------------------

def test_the_view_equals_the_stored_governance(world):
    seed(world)
    v = team(world)["admin"].get(GOV).json()
    by_id = {m["id"]: m for m in v["measures"]}
    k1, k2, k3 = by_id["K01"], by_id["K02"], by_id["K03"]
    assert (k1["personal"], k1["sensitive"], k1["visible_to"]["mode"]) == ("no", False, "everyone")
    assert k1["visible_to"]["text"] == GV.EVERYONE and k1["decided"] == {"by": PAT, "at": AT}  # who decided it and when
    assert (k2["personal"], k2["sensitive"], k2["visible_to"]["names"]) == ("yes", True, [LENA]) and k2["restricted"] is True
    assert k3["personal"] == "not_sure" and k3["decided"] is None and "personal data is not decided" in k3["undecided"]
    assert [s["name"] for s in k1["sources"]] == ["Bank portal"] and [f["name"] for f in k1["fields"]] == ["closing_balance", "due_date", "contact_email", "tax_ref"]
    f1 = k1["fields"][0]
    assert f1["personal"] == "Neither" and f1["decided"] == {"by": PAT, "at": AT} and f1["table"] == "balances" and f1["source"] == "Bank portal"
    assert f1["feeds"] == [{"id": "K01", "name": "Capital calls due"}] and f1["visible_to"]["mode"] == "everyone"
    salary = by_id["K02"]["fields"][0]
    assert salary["personal"] == "Personal data" and salary["sensitive"] is True and salary["visible_to"]["text"] == "Follows the measure “Pay review”"
    assert by_id["K02"]["sources"][0]["visible_to"]["text"] == LENA and by_id["K03"]["sources"][0]["personal"] == "Not sure"
    s = v["summary"]
    assert s["measures"] == {"total": 3, "decided": 2, "undecided": 1, "restricted": 2}  # K02 (personal, sensitive) and K03 (not sure counts as personal)
    assert s["fields"]["total"] == 5 and s["fields"]["undecided"] == 3 and s["fields"]["decided"] == 2
    assert "3 fields have no personal-data decision" in s["lines"] and "1 measure has no personal-data decision" in s["lines"]
    assert v["can_change"] is True and v["signed"] is False


def test_the_view_is_derived_never_a_second_store(world):
    plane = seed(world)
    before = {n: (plane.path("intents", "m2_baseline", BID) / n).read_bytes() for n in ("kpis.json", "catalogue.json")}
    team(world)["admin"].get(GOV)
    assert before == {n: (plane.path("intents", "m2_baseline", BID) / n).read_bytes() for n in before}
    assert not [p.name for p in plane.path("intents", "m2_baseline", BID).iterdir() if "govern" in p.name]


# ---- a field restricted alone ---------------------------------------------------------------------------------------------------------

def test_a_field_restricted_alone_never_reaches_a_viewer_who_may_not_see_it(world):
    add_pack_files(world)
    seed(world)
    t = team(world)
    assert t["admin"].put(f"{GOV}/fields/F001", json={"may_see": [LENA]}).status_code == 200
    stored = json.loads((world.plane("co-a").path("intents", "m2_baseline", BID) / "catalogue.json").read_text())
    own = next(f for f in stored["fields"] if C.row_id("fields", f) == "F001")[C.FIELD_VISIBILITY]
    assert own["value"] == LENA and own["mark"] == "stated" and own["by"] == PAT and own["at"]  # the field's own cell, with who and when
    # the view
    assert "closing_balance" not in names_in(t["analyst"].get(GOV).json())
    assert "closing_balance" in names_in(t["lena"].get(GOV).json()) and "closing_balance" in names_in(t["admin"].get(GOV).json())
    mine = next(f for m in t["lena"].get(GOV).json()["measures"] if m["id"] == "K01" for f in m["fields"] if f["id"] == "F001")
    assert mine["visible_to"] == {"mode": "named", "text": LENA, "names": [LENA]}
    # the catalogue
    got = t["analyst"].get(CAT).json()
    f1 = next(f for f in got["fields"] if f.get("Field ID", {}).get("value") == "F001" or f.get("Field ID") is None)
    assert f1.get("_hidden") is True and "closing_balance" not in json.dumps(got)
    assert "closing_balance" in json.dumps(t["lena"].get(CAT).json())
    # the Excel file
    for who, shown in (("analyst", False), ("lena", True)):
        data = t[who].get(CAT + "/export").content
        text = json.dumps(read_book(data))
        assert ("closing_balance" in text) is shown, who
    # the hand-off
    rec = {"catalogue": H._own(json.loads((world.plane("co-a").path("intents", "m2_baseline", BID) / "catalogue.json").read_text()))}
    assert C.FIELD_VISIBILITY in next(f for f in rec["catalogue"]["fields"] if C.row_id("fields", f) == "F001")  # the limit travels with the record
    out = H.for_viewer(rec, kpis(), {"K01", "K02", "K03"}, C.Viewer(ALAN, frozenset({"analyst"})))
    assert "closing_balance" not in json.dumps(out)
    out = H.for_viewer(rec, kpis(), {"K01", "K02", "K03"}, C.Viewer(LENA, frozenset({"analyst"})))
    assert "closing_balance" in json.dumps(out)
    # the column matcher
    cols = {"columns": [{"name": "closing_balance", "type": "decimal"}]}
    assert t["lena"].post(CAT + "/suggest-fields", json=cols).json()["suggestions"]
    assert t["analyst"].post(CAT + "/suggest-fields", json=cols).json()["suggestions"] == []


def test_a_field_can_never_be_relaxed_below_its_measure(world):
    seed(world)
    admin = team(world)["admin"]
    wide = admin.put(f"{GOV}/fields/F004", json={"may_see": [ALAN]})  # F004 feeds the Pay review, which only Lena may see
    assert wide.status_code == 422 and "may not see its measure" in wide.json()["message"]
    assert admin.put(f"{GOV}/fields/F004", json={"may_see": [LENA]}).status_code == 200
    assert admin.put(f"{GOV}/fields/F004", json={"may_see": [LENA, ALAN]}).status_code == 422
    assert admin.put(f"{GOV}/fields/F001", json={"may_see": [ALAN]}).status_code == 200  # an open measure: any narrower list is fine
    assert admin.put(f"{GOV}/fields/F001", json={"may_see": []}).status_code == 200  # taking the limit away: it follows its measures again
    assert admin.put(f"{GOV}/fields/F001", json={"may_see": "everyone"}).status_code == 422
    assert admin.put(f"{GOV}/fields/F001", json={"may_see": ["a;b"]}).status_code == 422
    assert admin.put(f"{GOV}/fields/F999", json={"may_see": []}).status_code == 404


def test_only_the_organiser_or_sponsor_changes_who_may_see(world):
    seed(world)
    t = team(world)
    assert t["analyst"].put(f"{GOV}/fields/F001", json={"may_see": [ALAN]}).status_code == 403
    assert t["lena"].put(f"{GOV}/fields/F001", json={"may_see": [LENA]}).status_code == 403
    assert login(world, "co-a", "Olive Owner", ("owner",)).put(f"{GOV}/fields/F001", json={"may_see": []}).status_code == 403
    assert login(world, "co-a", "Pia Participant", ("participant",)).get(GOV).status_code == 403
    assert t["sponsor"].put(f"{GOV}/fields/F001", json={"may_see": [LENA]}).status_code == 200  # the sponsor may
    # the existing rule for a measure stays: an analyst cannot name who may see it
    r = t["analyst"].put(f"{BASE}/baselines/{BID}/kpis/K01/governance", json={"may_see": ["x"]})
    assert r.status_code == 403


def test_a_field_a_person_may_not_see_cannot_be_restricted_by_them(world):
    seed(world)
    r = team(world)["sponsor"].put(f"{GOV}/fields/F004", json={"may_see": []})  # the sponsor is not named for the Pay review
    assert r.status_code == 404 and "salary" not in r.text


# ---- Lens proposes ---------------------------------------------------------------------------------------------------------------------

def _view(world, company="co-a"):
    r = login(world, company, f"Pat {company}", ("company_admin",)).get(GOV)
    assert r.status_code == 200, r.text
    return r.json()


def _proposal(v, fid):
    return next(f for m in v["measures"] if not m.get("hidden") for f in m["fields"] if f["id"] == fid)["proposal"]


def test_proposals_are_guessed_with_a_reason_and_never_replace_a_decision(world):
    add_pack_files(world)
    seed(world)
    v = _view(world)
    mail, due, tax = _proposal(v, "F003"), _proposal(v, "F002"), _proposal(v, "F005")
    assert mail["class"] == "Personal data" and mail["kind"] == "contact" and mail["mark"] == "guessed" and "contact details" in mail["reason"]
    assert due["class"] == "Neither" and due["mark"] == "guessed" and "not personal" in due["reason"]
    assert tax["class"] == "Personal data" and "industry pack" in tax["reason"]  # industry_a's pack flags it
    assert _proposal(v, "F001") is None and _proposal(v, "F004") is None  # a person's decision gets no proposal


def test_the_proposal_follows_the_companys_industry_not_a_fixed_one(world):
    add_pack_files(world)
    seed(world)
    seed(world, "co-b")
    seed(world, "co-none")
    assert _proposal(_view(world, "co-a"), "F005")["class"] == "Personal data"
    for other in ("co-b", "co-none"):  # no pack content about it: the generic guess only, nothing from industry_a
        got = _proposal(_view(world, other), "F005")
        assert got["class"] == "Neither" and "industry pack" not in got["reason"]


def test_confirming_proposals_is_the_persons_decision_and_skips_what_is_decided(world):
    seed(world)
    t = team(world)
    out = t["analyst"].post(f"{GOV}/proposals/confirm", json={"only_not_personal": True}).json()
    assert sorted(out["confirmed"]) == ["F002", "F005"]  # the two guessed "Neither"; the email stays a question
    stored = {C.row_id("fields", f): f for f in json.loads((world.plane("co-a").path("intents", "m2_baseline", BID) / "catalogue.json").read_text())["fields"]}
    assert stored["F002"][FIELD_CLASS]["value"] == "Neither" and stored["F002"][FIELD_CLASS]["by"] == ALAN and stored["F002"][FIELD_CLASS]["mark"] == "stated"
    assert stored["F003"][FIELD_CLASS]["mark"] == "unknown" and stored["F001"][FIELD_CLASS]["by"] == PAT  # never replaced
    again = t["analyst"].post(f"{GOV}/proposals/confirm", json={"only_not_personal": True}).json()
    assert again["confirmed"] == []
    one = t["analyst"].post(f"{GOV}/proposals/confirm", json={"field_ids": ["F003", "F004"]}).json()
    assert one["confirmed"] == ["F003"] and one["skipped"] == 1  # F004 was already decided
    assert t["analyst"].post(f"{GOV}/proposals/confirm", json={}).status_code == 422


def test_a_proposal_never_relaxes_a_not_sure_for_a_non_governor(world):
    cat = catalogue()
    cat["fields"][1][FIELD_CLASS] = cell("Not sure")
    seed(world, cat=cat)
    t = team(world)
    assert t["analyst"].post(f"{GOV}/proposals/confirm", json={"field_ids": ["F002"]}).json()["confirmed"] == []
    assert t["admin"].post(f"{GOV}/proposals/confirm", json={"field_ids": ["F002"]}).json()["confirmed"] == ["F002"]


# ---- undecided items ----------------------------------------------------------------------------------------------------------------------

def test_undecided_items_become_open_ambiguities_and_block_readiness(world):
    plane = seed(world)
    cat = json.loads((plane.path("intents", "m2_baseline", BID) / "catalogue.json").read_text())
    got = GS.ambiguities(plane, BID, ADMIN)
    k1 = got["K01"]
    assert {a["kind"] for a in k1} == {"governance"} and {a["status"] for a in k1} == {"open"}
    assert all(set(a) == {"id", "kind", "text", "question", "where", "raised_by", "status", "resolution", "by", "at"} for a in k1)
    assert len({a["id"] for a in k1}) == len(k1) and [a["id"] for a in k1] == [a["id"] for a in GS.ambiguities(plane, BID, ADMIN)["K01"]]  # stable ids
    assert any("due_date" in a["text"] for a in k1) and any("Exposure to one name" in a["text"] for a in got["K03"])
    ready, reasons = GS.governance_ready(plane, BID)
    assert ready is False and "3 fields have no personal-data decision" in reasons
    for f in cat["fields"]:
        f[FIELD_CLASS] = cell("Neither")
    cat["sources"][2]["Contains personal data?"] = cell("No")
    (plane.path("intents", "m2_baseline", BID) / "catalogue.json").write_text(json.dumps(cat))
    (plane.path("intents", "m2_baseline", BID) / "kpis.json").write_text(json.dumps(kpis("no")))
    assert GS.governance_ready(plane, BID) == (True, [])
    assert GS.ambiguities(plane, BID, ADMIN) == {}


def test_a_restricted_measure_with_nobody_named_is_undecided_too(world):
    ks = kpis("no")
    ks[1]["governance"]["may_see"] = []
    plane = seed(world, kpi_rows=ks)
    assert any("nobody named" in r for r in GS.governance_ready(plane, BID)[1])


# ---- the sheet, per viewer --------------------------------------------------------------------------------------------------------------

def _sheet(data):
    s = read_book(data)["Governance"]["cells"]
    rows, n = [], 5
    while f"A{n}" in s:
        rows.append([s.get(f"{c}{n}", "") for c in "ABCDEFGHI"])
        n += 1
    return s, rows


def test_the_governance_sheet_matches_the_view_for_each_viewer(world):
    seed(world)
    t = team(world)
    t["admin"].put(f"{GOV}/fields/F001", json={"may_see": [LENA]})
    for who in ("admin", "analyst", "lena", "sponsor"):
        header, rows = _sheet(t[who].get(CAT + "/export").content)
        assert [header[f"{c}4"] for c in "ABCDEFGHI"] == list(GV.FIELD_COLUMNS)
        assert rows == GV.table(t[who].get(GOV).json()), who
    assert read_book(t["admin"].get(CAT + "/export").content).keys() >= {"Governance", "Lists", "1 Sources"}


# ---- restricted names never reach a viewer who may not see them ---------------------------------------------------------------------------

def test_restricted_names_never_appear_for_a_viewer_who_may_not_see_them(world):
    seed(world)
    t = team(world)
    for who in ("analyst", "sponsor"):  # the analyst is not on the Pay review's list; neither is the sponsor
        v = t[who].get(GOV)
        assert all(m["id"] != "K02" for m in v.json()["measures"]) and "K02" not in v.text  # no stub, no id
        assert v.json()["note"] == "Some measures are restricted to named people"  # plain, with no number
        assert not any(w in v.text for w in SECRETS), who
        assert not any(w in json.dumps(read_book(t[who].get(CAT + "/export").content)) for w in SECRETS), who
        assert not any(w in t[who].get(CAT).text for w in SECRETS), who
        assert v.json()["summary"]["measures"]["total"] == 1  # counts never include what they may not see
    assert t["lena"].get(GOV).json()["measures"][1]["visible_to"]["names"] == [LENA]
    for role in ("owner", "participant"):  # an owner's answer link or a participant's room are not the governance view
        assert login(world, "co-a", f"{role} person", (role,)).get(GOV).status_code == 403


def test_only_those_who_may_see_a_list_see_it(world):
    ks = kpis()
    ks[0]["governance"] = {"personal": "yes", "sensitive": False, "may_see": [ALAN, LENA]}
    seed(world, kpi_rows=ks)
    t = team(world)
    k1 = lambda who: next((m for m in t[who].get(GOV).json()["measures"] if m["id"] == "K01"), None)  # noqa: E731
    assert k1("admin")["visible_to"]["names"] == [ALAN, LENA] and k1("analyst")["visible_to"]["names"] == [ALAN, LENA]
    assert k1("sponsor") is None  # a sponsor not on the list does not see the measure, so not its names either


# ---- review round: ambiguities and readiness filtered per viewer; "and" in a name; the organiser line ------------------------------------

def test_ambiguities_name_nothing_the_viewer_may_not_see(world):
    plane = seed(world)
    team(world)["admin"].put(f"{GOV}/fields/F005", json={"may_see": [LENA]})  # tax_ref, on the open measure K01, restricted on its own
    got = GS.ambiguities(plane, BID, C.Viewer(ALAN, frozenset({"analyst"})))
    text = json.dumps(got)
    assert "tax_ref" not in text and "K02" not in got and "Pay review" not in text and "salary" not in text and "due_date" in text
    assert "tax_ref" in json.dumps(GS.ambiguities(plane, BID, C.Viewer(LENA, frozenset({"analyst"}))))
    assert "tax_ref" in json.dumps(GS.ambiguities(plane, BID, C.Viewer(PAT, frozenset({"company_admin"}))))


def test_readiness_counts_are_full_only_for_a_governor(world):
    plane = seed(world)
    team(world)["admin"].put(f"{GOV}/fields/F002", json={"may_see": [LENA]})
    assert "3 fields have no personal-data decision" in GS.governance_ready(plane, BID, C.Viewer(SAM, frozenset({"sponsor"})))[1]
    assert "2 fields have no personal-data decision" in GS.governance_ready(plane, BID, C.Viewer(ALAN, frozenset({"analyst"})))[1]
    assert GS.governance_ready(plane, BID)[0] is False  # the sign-off gate's own call counts everything


def test_a_name_with_and_in_it_cannot_grant_two_people(world):
    seed(world)
    r = team(world)["admin"].put(f"{GOV}/fields/F001", json={"may_see": ["Tom and Jerry"]})
    assert r.status_code == 422 and "one name" in r.json()["message"]


def test_the_organiser_is_told_they_see_every_row(world):
    seed(world)
    t = team(world)
    assert t["admin"].get(GOV).json()["organiser"] is True and t["analyst"].get(GOV).json()["organiser"] is False


# ---- signed, other companies, industries, empty -----------------------------------------------------------------------------------------------

def test_a_signed_baseline_refuses_writes_but_can_be_read(world):
    seed(world, state="signed")
    admin = team(world)["admin"]
    assert admin.get(GOV).json()["signed"] is True
    assert admin.put(f"{GOV}/fields/F001", json={"may_see": [LENA]}).status_code == 409
    assert admin.post(f"{GOV}/proposals/confirm", json={"only_not_personal": True}).status_code == 409


def test_other_companies_and_a_switched_off_module_are_refused(world):
    seed(world)
    assert login(world, "co-off", "Off Person", ("company_admin",)).get(GOV).status_code in (403, 404)
    assert login(world, "co-solo", "Solo Person", ("company_admin",)).get(GOV).status_code == 404  # no such baseline in that company
    assert login(world, "co-b", "Bea Owner", ("company_admin",)).put(f"{GOV}/fields/F001", json={"may_see": []}).status_code == 404
    assert world.app is not None and (world.plane("co-b").path("intents", "m2_baseline") / BID).exists() is False


def test_an_empty_baseline_and_an_industry_with_no_pack(world):
    for company in ("co-b", "co-none"):
        seed(world, company, kpi_rows=[], cat={t: [] for t in C.TABS})
        v = _view(world, company)
        assert v["measures"] == [] and v["summary"]["measures"] == {"total": 0, "decided": 0, "undecided": 0, "restricted": 0}
        assert v["summary"]["lines"] == [] and isinstance(v["pack_label"], str)


def test_the_pack_parts_and_proposal_have_no_fixed_industry(world):
    add_pack_files(world)
    parts = GV.pack_parts(world.app.state.packs, "industry_a")
    assert "positions" in parts["feeds"] and GV.pack_parts(world.app.state.packs, "industry_b")["feeds"] == {}
    assert GV.pack_parts(world.app.state.packs, "no_such")["feeds"] == {}
    m = {"personal": "no", "sensitive": False}
    assert GV.propose("tax_ref", [m], parts)["class"] == "Personal data" and GV.propose("tax_ref", [m], {})["class"] == "Neither"
    assert GV.propose("employee_name", [m], {})["kind"] == "name" and GV.propose("home_address", [m], {})["kind"] == "contact"
    assert GV.propose("monthly_pay", [m], {})["kind"] == "pay" and GV.propose("passport_no", [m], {})["kind"] == "identifier"
    assert GV.propose("portfolio_name", [m], {})["class"] == "Neither"  # a plain "name" is not a person's name
    assert GV.propose("mystery", [{"personal": "not_sure", "sensitive": False}], {}) is None
