"""M2-P04: the catalogue model, filling it from KPIs and answers, mapping, conflicts, governance and the routes.
Family-office example content only, synthetic. Nothing here reads a real value; the catalogue describes data and never contains it."""
import json

import pytest
from m2_kit import BASE, login

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain.provenance import prov, unknown
from modules.m2_baseline.store import catalogue as S

BID = "b" * 32
OUTCOME = "a" * 32
SRC = "answers.json"


def person(v, who="Sara"):
    # one fixed time: the coarse Windows clock made "latest answer wins" depend on timing (full-suite flake, 4 Oct)
    return prov(v, "stated", who, "the questionnaire", at="2026-10-03T10:00:00+00:00")


def kpis():
    return [
        {"id": "K01", "name": "Capital calls due, by date", "problem_ids": ["p1", "p2"], "priority": "Must",
         "definition": person("Cash the office must provide, by due date", "Mei"),
         "owners": {"business": person("Mei", "Mei"), "data": person("Sara"), "process": person("Sara")},
         "governance": {"personal": "no", "sensitive": False, "may_see": []}, "tracking": person("tracked_now")},
        {"id": "K02", "name": "Funding capacity", "problem_ids": ["p1"], "priority": "Must", "definition": person("Cash and committed lines", "Tom"),
         "owners": {"business": person("Tom", "Tom"), "data": person("Arjun", "Arjun"), "process": person("Sara")},
         "governance": {"personal": "no", "sensitive": False, "may_see": []}, "tracking": person("partly")},
        {"id": "K03", "name": "Exposure to one name", "problem_ids": ["p2"], "priority": "Should", "definition": unknown("Lens", "kpis.json"),
         "owners": {"business": unknown(), "data": unknown(), "process": unknown()},
         "governance": {"personal": "not_sure", "sensitive": True, "may_see": ["Test Mei Lim"]}, "tracking": unknown()},
    ]


def answers():
    def a(i, kpi, who, source, dt, arrival, sla, **extra):
        return {"id": i, "request_id": "r1", "owner_name": who, "kpi_id": kpi, "source": person(source, who), "data_type": person(dt, who),
                "arrival": person(arrival, who), "sla": person(sla, who), "tracked_today": unknown(), "could_track": unknown(), **extra}
    return [
        a("a1", "K02", "Arjun", "Bank portal", "structured", "daily", "By noon", tracked_today=person("yes", "Arjun")),
        a("a2", "K01", "Sara", "Call notices by email", "unstructured", "ad hoc", "No fixed time", could_track=person("yes")),
        a("a3", "K01", "Mei", "bank  portal", "structured", "weekly", "By noon"),  # disagrees with Arjun about how often it arrives
        a("a4", "K03", "Mei", "Custody statements", "structured", "monthly", "First of the month"),
    ]


def seed(world, company="co-a", state="mapping", kpi_rows=None, answer_rows=None):
    plane = world.plane(company)
    folder = plane.path("intents", "m2_baseline", BID)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "baseline.json").write_text(json.dumps({"id": BID, "charter_outcome_id": OUTCOME, "state": state, "created_at": "2026-10-03"}))
    (folder / "kpis.json").write_text(json.dumps(kpis() if kpi_rows is None else kpi_rows))
    (folder / "answers.json").write_text(json.dumps(answers() if answer_rows is None else answer_rows))
    out = plane.path("intents", "m1_intent", "outcomes")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{OUTCOME}.json").write_text(json.dumps({"problems": [{"id": "p1", "title": "Calls arrive too late"}, {"id": "p2", "title": "Headroom is a surprise"}]}))
    return plane


def by_id(rows, tab):
    return {C.row_id(tab, r): r for r in rows}


# ---- the model (M2-16) ------------------------------------------------------------------------------------------------------

def test_build_makes_stable_ids_and_one_row_per_kpi_linked_to_both_problems():
    cat, _ = C.build(None, kpis(), answers())
    assert [C.row_id("sources", s) for s in cat["sources"]] == ["S01", "S02", "S03"]
    k = by_id(cat["kpis"], "kpis")["K01"]
    assert C.value_of(k["Problem it serves"]) == ["p1", "p2"] and len(cat["kpis"]) == 3  # one row, both problems
    again, _ = C.build(cat, kpis(), answers())
    assert [C.row_id("sources", s) for s in again["sources"]] == ["S01", "S02", "S03"]  # ids never move


def test_every_cell_is_a_provenance_value_and_unknowns_stay_visible():
    cat, _ = C.build(None, kpis(), answers())
    for tab in C.TABS:
        for row in cat[tab]:
            assert list(row) == [h for h in C.headers(tab) if h in row]
            for cell in row.values():
                assert {"value", "mark", "by", "at", "from"} <= set(cell)
                assert cell["mark"] != "unknown" or cell["value"] is None
    k3 = by_id(cat["kpis"], "kpis")["K03"]
    assert k3["Data owner"]["mark"] == "unknown" and C.is_blank(k3["Tracking status"])  # shown as unknown, never filled in


def test_sources_are_filled_from_the_answers_and_governance():
    cat, _ = C.build(None, kpis(), answers())
    bank = next(s for s in cat["sources"] if C.text_of(s["Source name"]).lower().startswith("bank"))
    assert C.text_of(bank["Structured or unstructured"]) == "Structured" and bank["Availability"]["mark"] == "unknown"  # nobody said it (r4-3)
    assert C.text_of(bank["Data owner"]) == "Arjun" and C.text_of(bank["Contains personal data?"]) == "No"
    mail = next(s for s in cat["sources"] if "email" in C.text_of(s["Source name"]))
    assert C.text_of(mail["Structured or unstructured"]) == "Unstructured" and mail["Availability"]["mark"] == "unknown"
    custody = next(s for s in cat["sources"] if "Custody" in C.text_of(s["Source name"]))
    assert C.text_of(custody["Contains personal data?"]) == "Not sure"  # not sure stays personal until someone confirms
    assert C.text_of(custody["Who may see it"]) == "Test Mei Lim"


def test_tracking_status_uses_the_templates_words():
    cat, _ = C.build(None, kpis(), answers())
    k = by_id(cat["kpis"], "kpis")
    assert [C.text_of(k[i]["Tracking status"]) for i in ("K01", "K02", "K03")] == ["Tracked today", "Will be tracked in future", ""]


def test_a_person_edit_survives_a_rebuild_and_is_attributed():
    cat, conflicts = C.build(None, kpis(), answers())
    C.edit_cells(cat, conflicts, "kpis", "K02", {"Tracking status": "Can be tracked now"}, "Tom")
    again, _ = C.build(cat, kpis(), answers(), conflicts)
    cell = by_id(again["kpis"], "kpis")["K02"]["Tracking status"]
    assert (cell["value"], cell["by"], cell["from"]) == ("Can be tracked now", "Tom", "edited in the catalogue")


# ---- mapping (M2-17) ------------------------------------------------------------------------------------------------------------

def mapped(cat, conflicts):
    s = by_id(cat["sources"], "sources")
    C.add_row(cat, conflicts, "tables", {"Source ID": "S01", "Kind": "file", "Name of table, file or document type": "statement.csv", "Related KPIs": "K01, K02"}, "Arjun")
    C.add_row(cat, conflicts, "fields", {"Item ID": "T01", "Field name as in the source": "closing_balance", "Feeds KPI": "K02"}, "Arjun")
    C.add_row(cat, conflicts, "extractions", {"Item ID (document type)": "T01", "What to extract": "Due date", "Feeds KPI": "K01"}, "Sara", "guessed")
    return s


def test_a_table_relates_to_several_kpis_and_counts_per_kpi_are_shown():
    cat, conflicts = C.build(None, kpis(), answers())
    mapped(cat, conflicts)
    full = by_id(C.with_derived(cat)["kpis"], "kpis")
    counts = {k: [C.value_of(full[k][h]) for h in ("Tables mapped", "Fields mapped", "Extractions mapped")] for k in full}
    assert counts == {"K01": [1, 0, 1], "K02": [1, 1, 0], "K03": [0, 0, 0]}
    assert "nothing_mapped" in C.kpi_findings(cat)["K03"] and "nothing_mapped" not in C.kpi_findings(cat)["K01"]  # nothing mapped stays visible


def test_mapping_refuses_a_kpi_or_parent_that_does_not_exist_and_a_kpi_cannot_be_added_by_hand():
    cat, conflicts = C.build(None, kpis(), answers())
    for tab, cells in [("tables", {"Source ID": "S99"}), ("tables", {"Source ID": "S01", "Related KPIs": "K99"}), ("fields", {"Item ID": "T01"}),
                       ("fields", {"Feeds KPI": "K01"}), ("kpis", {})]:
        with pytest.raises(C.CatalogueError):
            C.add_row(cat, conflicts, tab, cells, "Arjun")
    assert cat["tables"] == [] and cat["fields"] == []  # a refused add leaves nothing behind


def test_complete_and_ready_follow_the_templates_formulas():
    cat, conflicts = C.build(None, kpis(), answers())
    mapped(cat, conflicts)
    full = C.with_derived(cat)
    k = by_id(full["kpis"], "kpis")
    assert C.text_of(k["K01"]["Ready for module 3?"]) == "Not ready"  # signed dates are not there yet (M2-P05)
    assert C.text_of(by_id(full["tables"], "tables")["T01"]["Complete?"]).startswith("Missing")  # no update pattern needed, but arrival is
    f = by_id(full["fields"], "fields")["F001"]
    assert C.text_of(f["Complete?"]) == "Missing 3 required"  # type, personal data class and the meaning are blank
    C.edit_cells(cat, conflicts, "fields", "F001", {"Business meaning": "Cash at end of day", "Data type": "number", "Personal data class": "Neither"}, "Arjun")
    assert C.text_of(by_id(C.with_derived(cat)["fields"], "fields")["F001"]["Complete?"]) == "Complete"
    assert by_id(C.with_derived(cat)["fields"], "fields")["F001"]["Data type"]["value"] == "Number"  # the dropdown's own word


def test_how_sure_confirmed_by_and_date_come_from_provenance():
    cat, conflicts = C.build(None, kpis(), answers())
    row = by_id(C.with_derived(cat)["sources"], "sources")["S01"]
    assert C.text_of(row["How sure are we"]) == "Guessed" and C.text_of(row["Confirmed by"]) == "Arjun"  # an old one-line source is a guessed name
    assert len(C.text_of(row["Date confirmed"])) == 10
    C.edit_cells(cat, conflicts, "sources", "S01", {"Connection method": "API"}, "Tom", "guessed")
    assert C.text_of(by_id(C.with_derived(cat)["sources"], "sources")["S01"]["How sure are we"]) == "Guessed"


# ---- conflicts (M2-24) ----------------------------------------------------------------------------------------------------------

def test_two_owners_answering_differently_give_a_conflict_with_both_versions_and_who_said_each():
    cat, conflicts = C.build(None, kpis(), answers())
    assert len(conflicts) == 1
    c = conflicts[0]
    assert (c["tab"], c["column"], c["state"]) == ("sources", "How often it arrives", "open")
    assert {(v["value"].lower(), v["by"]) for v in c["versions"]} == {("daily", "Arjun"), ("weekly", "Mei")}  # both versions, who said each
    cell = by_id(cat["sources"], "sources")[c["row_id"]]["How often it arrives"]
    assert cell["mark"] == "unknown" and cell["value"] is None  # Lens never picks


def test_only_a_named_person_settles_and_both_versions_stay_in_the_history():
    cat, conflicts = C.build(None, kpis(), answers())
    cid = conflicts[0]["id"]
    for bad in ("Lens", "", "Signal Harbor"):
        with pytest.raises(C.CatalogueError):
            C.settle(cat, conflicts, cid, "Daily", bad)
    with pytest.raises(C.CatalogueError):
        C.settle(cat, conflicts, cid, "  ", "Tom")
    C.settle(cat, conflicts, cid, "Daily", "Tom", "Arjun runs the download")
    rec = conflicts[0]
    assert (rec["state"], rec["settled_by"], len(rec["versions"])) == ("settled", "Tom", 2) and rec["history"][-1]["event"] == "settled"
    cell = by_id(cat["sources"], "sources")[rec["row_id"]]["How often it arrives"]
    assert (cell["value"], cell["by"], cell["mark"]) == ("Daily", "Tom", "stated")
    with pytest.raises(C.CatalogueError):
        C.settle(cat, conflicts, cid, "Weekly", "Tom")  # already settled


def test_a_rebuild_keeps_a_settlement_until_someone_answers_again():
    cat, conflicts = C.build(None, kpis(), answers())
    cid = conflicts[0]["id"]
    C.settle(cat, conflicts, cid, "Daily", "Tom")
    cat, conflicts = C.build(cat, kpis(), answers(), conflicts)
    assert conflicts[0]["state"] == "settled" and C.text_of(by_id(cat["sources"], "sources")[conflicts[0]["row_id"]]["How often it arrives"]) == "Daily"
    newer = answers() + [{**answers()[0], "id": "a5", "owner_name": "Mei", "arrival": prov("monthly", "stated", "Mei", "meeting", "2099-01-01T00:00:00+00:00")}]
    cat, conflicts = C.build(cat, kpis(), newer, conflicts)
    assert conflicts[0]["state"] == "open"  # Mei changed her answer to a third value: someone answered again, so it is open again
    assert [h["event"] for h in conflicts[0]["history"]] == ["settled", "reopened"] and conflicts[0]["history"][0]["by"] == "Tom"  # nothing is lost
    assert C.is_blank(by_id(cat["sources"], "sources")[conflicts[0]["row_id"]]["How often it arrives"])


def test_a_person_changing_their_own_answer_is_not_a_conflict():
    rows = answers()[:1] + [{**answers()[0], "id": "a9", "arrival": prov("weekly", "stated", "Arjun", "q", "2099-01-01T00:00:00+00:00")}]
    cat, conflicts = C.build(None, kpis(), rows)
    assert conflicts == [] and C.text_of(cat["sources"][0]["How often it arrives"]) == "Weekly"


def test_a_cell_in_open_conflict_cannot_be_edited_around():
    cat, conflicts = C.build(None, kpis(), answers())
    c = conflicts[0]
    with pytest.raises(C.CatalogueError) as e:
        C.edit_cells(cat, conflicts, "sources", c["row_id"], {"How often it arrives": "Daily"}, "Tom")
    assert e.value.code == "conflict"


# ---- governance (M2-05) -------------------------------------------------------------------------------------------------------------

def viewer(name, *roles):
    return C.Viewer(name, frozenset(roles))


def test_not_sure_is_treated_as_personal_and_unnamed_people_see_only_that_a_row_exists(world):
    seed(world)
    S.refresh(world.plane("co-a"), BID)
    plane = world.plane("co-a")
    mapped_cat, conflicts = S._raw(plane, BID)
    C.add_row(mapped_cat, conflicts, "tables", {"Source ID": "S03", "Related KPIs": "K03", "Name of table, file or document type": "custody.csv"}, "Mei")
    S._save(plane, BID, mapped_cat, conflicts)
    other = S.view(plane, BID, viewer("Tom", "analyst"))
    k3 = by_id(other["kpis"], "kpis")["K03"]
    assert k3 == {"KPI ID": k3["KPI ID"], C.HIDDEN: True}
    assert "Exposure" not in json.dumps(other) and "custody.csv" not in json.dumps(other)
    named = S.view(plane, BID, viewer("Test Mei Lim", "analyst"))
    assert C.text_of(by_id(named["kpis"], "kpis")["K03"]["KPI name"]) == "Exposure to one name"
    assert all(not r.get(C.HIDDEN) for r in named["tables"])


def test_where_nobody_is_named_yet_only_the_company_admin_sees_it():
    cat, _ = C.build(None, [{**kpis()[2], "governance": {"personal": "yes", "sensitive": False, "may_see": []}}], [])
    shown = C.with_derived(cat)
    g = C.guards(cat, {"K03": {"personal": "yes", "may_see": []}})
    assert C.apply_governance(shown, g, viewer("Pat", "analyst"))["kpis"][0].get(C.HIDDEN)
    assert not C.apply_governance(shown, g, viewer("Pat", "company_admin"))["kpis"][0].get(C.HIDDEN)


def test_a_personal_field_is_limited_to_the_people_named_on_its_source():
    cat, conflicts = C.build(None, kpis(), answers())
    C.edit_cells(cat, conflicts, "sources", "S01", {"Who may see it": "Arjun, Sara"}, "Arjun")
    C.add_row(cat, conflicts, "tables", {"Source ID": "S01", "Related KPIs": "K02"}, "Arjun")
    C.add_row(cat, conflicts, "fields", {"Item ID": "T01", "Feeds KPI": "K02", "Personal data class": "Personal data"}, "Arjun")
    shown, gov = C.with_derived(cat), {k["id"]: k["governance"] for k in kpis()}
    assert C.apply_governance(shown, C.guards(cat, gov), viewer("Tom", "analyst"))["fields"][0].get(C.HIDDEN)
    assert not C.apply_governance(shown, C.guards(cat, gov), viewer("Sara", "analyst"))["fields"][0].get(C.HIDDEN)
    assert C.apply_governance(shown, C.guards(cat, gov), viewer("Tom", "analyst"), drop=True)["fields"] == []


# ---- matching columns to KPIs (names and types only) -----------------------------------------------------------------------------------

FEEDS = {"balances": {"fields": [
    {"id": "closing_balance", "type": "decimal", "required_for": ["K02", "K77"], "pii": False},
    {"id": "account_no", "type": "string", "required_for": ["K02"], "pii": True, "customer_decides": True},
    {"id": "unused", "type": "string", "required_for": []}]}}
SYN = {"balances": {"closing_balance": {"regex": "^(closing_balance|cl_bal)$"}, "account_no": {"regex": "^acct_no$"}}}


def test_matcher_suggests_with_reasons_and_never_above_medium_for_a_business_rule():
    got = C.match_columns([{"name": "CL_BAL", "type": "decimal"}, {"name": "acct_no", "type": "string"}, {"name": "memo", "type": "string"}],
                          FEEDS, SYN, {"K02"})
    by_col = {g["column"]: g for g in got}
    assert by_col["CL_BAL"]["confidence"] == "high" and by_col["CL_BAL"]["kpi_ids"] == ["K02"]  # K77 is not one of this baseline's KPIs
    assert by_col["acct_no"]["confidence"] == "medium" and by_col["acct_no"]["personal"]
    assert "memo" not in by_col


def test_matcher_downgrades_a_wrongly_typed_column_and_ignores_unknown_kpis():
    got = C.match_columns([{"name": "closing_balance", "type": "date"}], FEEDS, {}, {"K02"})
    assert got[0]["confidence"] == "low"
    assert C.match_columns([{"name": "closing_balance", "type": "decimal"}], FEEDS, SYN, set()) == []


# ---- the routes ----------------------------------------------------------------------------------------------------------------------------

CAT = f"{BASE}/baselines/{BID}/catalogue"


def test_refresh_then_read_through_the_route(world):
    seed(world)
    c = login(world, "co-a", "Pat Owner", ("company_admin",))
    assert c.post(CAT + "/refresh").json() == {"status": "ok"}
    got = c.get(CAT).json()
    assert [C.row_id("sources", s) for s in got["sources"]] == ["S01", "S02", "S03"] and len(got["conflicts"]) == 1
    assert got["schema"]["sources"]["sheet"] == "1 Sources" and "K01" in got["findings"] and "K03" not in got["findings"]  # K03 is personal and the admin is not named for it
    k1 = by_id(got["kpis"], "kpis")["K01"]
    assert C.value_of(k1["Problem it serves"]) == ["Calls arrive too late", "Headroom is a surprise"]  # names, from module 1's outcome record


def test_edit_add_and_settle_are_attributed_to_the_signed_in_person(world):
    seed(world)
    c = login(world, "co-a", "Tom Hale", ("company_admin",))
    c.post(CAT + "/refresh")
    r = c.post(CAT + "/tables/rows", json={"cells": {"Source ID": "S01", "Related KPIs": "K02", "Name of table, file or document type": "statement.csv"}})
    assert r.status_code == 200 and r.json() == {"id": "T01"}
    assert c.put(CAT + "/tables/rows/T01", json={"cells": {"How often it arrives": "Daily"}}).status_code == 200
    got = by_id(c.get(CAT).json()["tables"], "tables")["T01"]
    assert (got["How often it arrives"]["by"], got["Related KPIs"]["by"]) == ("Test Tom Hale", "Test Tom Hale")
    cid = c.get(CAT).json()["conflicts"][0]["id"]
    assert c.post(f"{CAT}/conflicts/{cid}/settle", json={"value": "Daily", "by": "Lens"}).json()["settled_by"] == "Test Tom Hale"  # the body cannot name someone else
    assert c.get(CAT).json()["conflicts"][0]["state"] == "settled"


def test_plain_refusals(world):
    seed(world)
    c = login(world, "co-a", "Pat Owner", ("company_admin",))
    assert c.get(f"{BASE}/baselines/{'z' * 32}/catalogue").status_code == 404
    assert c.get(f"{BASE}/baselines/..%2f..%2fx/catalogue").status_code in (403, 404, 422)
    assert c.post(CAT + "/tables/rows", json={"cells": {}}).status_code == 422
    assert c.post(CAT + "/kpis/rows", json={"cells": {}}).status_code == 422
    assert c.put(CAT + "/nonsense/rows/X1", json={"cells": {"a": "b"}}).status_code == 422
    assert c.post(CAT + "/tables/rows", data="not json", headers={"content-type": "application/json"}).status_code == 422
    body = c.post(CAT + "/tables/rows", json={"cells": {"Source ID": "S99"}}).json()
    assert body["message"] and "Traceback" not in json.dumps(body)


def test_a_signed_baseline_cannot_be_changed(world):
    seed(world, state="signed")
    c = login(world, "co-a", "Pat Owner", ("company_admin",))
    assert c.post(CAT + "/refresh").status_code == 409
    assert c.get(CAT).status_code == 200


def test_roles_company_isolation_and_a_switched_off_module(world):
    seed(world)
    seed(world, "co-b")
    assert login(world, "co-a", "Pat Owner", ("analyst",)).post(f"{CAT}/conflicts/c-x/settle", json={"value": "x"}).status_code == 403  # analysts do not settle
    assert login(world, "co-off", "Off Person", ("company_admin",)).get(CAT).status_code in (403, 404)
    other = login(world, "co-a", "Pat Two", ("company_admin",))
    other.post(CAT + "/refresh")
    assert login(world, "co-solo", "Solo Person", ("company_admin",)).get(CAT).status_code == 404  # no baseline in that company: nothing leaks
    b = login(world, "co-b", "Bea Owner", ("company_admin",))
    assert b.get(CAT).json()["sources"] == []  # industry B's own plane: nothing from A


def test_leak_tests_every_route_that_returns_catalogue_rows(world):
    seed(world)
    admin = login(world, "co-a", "Pat Owner", ("company_admin",))
    admin.post(CAT + "/refresh")
    plane = world.plane("co-a")
    cat, conflicts = S._raw(plane, BID)
    C.add_row(cat, conflicts, "tables", {"Source ID": "S03", "Related KPIs": "K03", "Name of table, file or document type": "vault_positions"}, "Mei")
    S._save(plane, BID, cat, conflicts)
    tom = login(world, "co-a", "Tom Hale", ("analyst",))
    for resp in (tom.get(CAT), tom.get(CAT + "/export"), tom.post(CAT + "/suggest-fields", json={"columns": [{"name": "x", "type": "string"}]})):
        assert resp.status_code == 200
        body = resp.content
        assert b"Exposure to one name" not in body and b"vault_positions" not in body
    assert tom.put(CAT + "/tables/rows/T01", json={"cells": {"Kind": "File"}}).status_code == 404  # cannot change what he cannot see
    assert b"vault_positions" in login(world, "co-a", "Mei Lim", ("analyst",)).get(CAT).content


def test_suggest_fields_route_takes_names_and_types_only(world):
    seed(world)
    c = login(world, "co-a", "Pat Owner", ("company_admin",))
    c.post(CAT + "/refresh")
    r = c.post(CAT + "/suggest-fields", json={"columns": [{"name": "closing_balance", "type": "decimal", "values": [1, 2, 3]}]})
    assert r.status_code == 200 and r.json()["suggestions"] == []  # industry A's pack has no feeds: an honest empty answer
    assert c.post(CAT + "/suggest-fields", json={"columns": "no"}).status_code == 422


def test_read_catalogue_is_what_module_3_reads(world):
    plane = seed(world)
    S.refresh(plane, BID)
    cat = S.read_catalogue(plane, BID)
    assert list(cat) == list(C.TABS) and set(cat["kpis"][0]) == set(C.headers("kpis"))
    empty = S.read_catalogue(world.plane("co-b"), "c" * 32)
    assert empty == {t: [] for t in C.TABS}


# ---- fix round 1: nothing about a row the caller is not named for ----------------------------------------------------------------------------

def _with_hidden_table(world):
    seed(world)
    login(world, "co-a", "Pat Owner", ("company_admin",)).post(CAT + "/refresh")
    plane = world.plane("co-a")
    cat, conflicts = S._raw(plane, BID)
    C.add_row(cat, conflicts, "tables", {"Source ID": "S03", "Related KPIs": "K03", "Name of table, file or document type": "vault_positions"}, "Mei")
    S._save(plane, BID, cat, conflicts)
    return plane, conflicts


def test_findings_and_conflicts_of_a_hidden_kpi_do_not_leak(world):
    plane, _ = _with_hidden_table(world)
    tom = S.view(plane, BID, viewer("Tom", "analyst"))
    assert "K03" not in tom["findings"] and set(tom["findings"]) == {"K01", "K02"}
    mei = S.view(plane, BID, viewer("Test Mei Lim", "analyst"))
    assert "K03" in mei["findings"]
    # a conflict about a row the caller may not see is not mentioned, not even as a hidden stub
    cat, conflicts = S._raw(plane, BID)
    conflicts.append({"id": "c-hidden", "tab": "kpis", "row_id": "K03", "state": "open", "header": "Definition", "versions": []})
    S._save(plane, BID, cat, conflicts)
    assert all(c["id"] != "c-hidden" for c in S.view(plane, BID, viewer("Tom", "analyst"))["conflicts"])
    assert any(c["id"] == "c-hidden" for c in S.view(plane, BID, viewer("Test Mei Lim", "analyst"))["conflicts"])


def test_counts_for_a_visible_kpi_leave_out_hidden_rows(world):
    plane, _ = _with_hidden_table(world)
    cat, conflicts = S._raw(plane, BID)
    C.add_row(cat, conflicts, "tables", {"Source ID": "S03", "Related KPIs": "K01, K03", "Name of table, file or document type": "mixed"}, "Mei")
    S._save(plane, BID, cat, conflicts)  # a table tied to a hidden KPI is hidden from Tom, but still counts for Mei
    k1 = lambda who: by_id(S.view(plane, BID, who)["kpis"], "kpis")["K01"]["Tables mapped"]
    assert C.text_of(k1(viewer("Tom", "analyst"))) != C.text_of(k1(viewer("Test Mei Lim", "analyst")))


def test_blank_or_unknown_personal_answers_are_restricted():
    cat, conflicts = C.build(None, kpis()[:2], answers()[:2])
    C.edit_cells(cat, conflicts, "sources", "S01", {"Contains personal data?": ""}, "Arjun")
    g = C.guards(cat, {"K01": {"personal": "no"}, "K02": {"personal": "no"}})
    assert g[("sources", "S01")]  # blank counts as not sure
    C.edit_cells(cat, conflicts, "sources", "S01", {"Contains personal data?": "No"}, "Arjun")
    assert C.guards(cat, {"K01": {"personal": "no"}})[("sources", "S01")] == []
    C.add_row(cat, conflicts, "tables", {"Source ID": "S01", "Related KPIs": "K02"}, "Arjun")
    C.add_row(cat, conflicts, "fields", {"Item ID": "T01", "Feeds KPI": "K02"}, "Arjun")  # class left blank: the source's "No" applies (N5)
    assert C.guards(cat, {"K02": {"personal": "no"}})[("fields", "F001")] == []
    C.edit_cells(cat, conflicts, "sources", "S01", {"Contains personal data?": "Yes"}, "Arjun")
    assert C.guards(cat, {"K02": {"personal": "no"}})[("fields", "F001")]  # a "Yes" source keeps its fields restricted
    C.edit_cells(cat, conflicts, "fields", "F001", {"Personal data class": "Neither"}, "Arjun")
    assert C.guards(cat, {"K02": {"personal": "no"}})[("fields", "F001")] == C.guards(cat, {"K02": {"personal": "no"}})[("tables", "T01")]


def test_not_sure_kpi_is_restricted_and_blank_governance_too():
    assert C._restricted_kpi({"personal": "not_sure"}) and C._restricted_kpi({}) and C._restricted_kpi(None)
    assert not C._restricted_kpi({"personal": "no", "sensitive": False})
    cat, _ = C.build(None, [{**kpis()[0], "governance": {"personal": "not_sure", "may_see": ["Sara"]}}], [])
    shown, _f = C.view_of(cat, C.guards(cat, {"K01": {"personal": "not_sure", "may_see": ["Sara"]}}), viewer("Tom", "analyst"))
    assert shown["kpis"][0].get(C.HIDDEN)


def test_suggest_fields_leaves_out_hidden_kpis(world, monkeypatch):
    from modules.m2_baseline.api import catalogue as api
    feeds = {"f": {"fields": [{"id": "closing_balance", "type": "decimal", "required_for": ["K02", "K03"]}]}}
    monkeypatch.setattr(api, "_pack_matching", lambda request: (feeds, {}, "x"))
    _with_hidden_table(world)
    tom = login(world, "co-a", "Tom Hale", ("analyst",))
    got = tom.post(CAT + "/suggest-fields", json={"columns": [{"name": "closing_balance", "type": "decimal"}]}).json()["suggestions"]
    assert got and got[0]["kpi_ids"] == ["K02"]
    mei = login(world, "co-a", "Mei Lim", ("analyst",))
    assert mei.post(CAT + "/suggest-fields", json={"columns": [{"name": "closing_balance", "type": "decimal"}]}).json()["suggestions"][0]["kpi_ids"] == ["K02", "K03"]


def test_two_accounts_with_one_display_name_do_not_share_access(world):
    plane, _ = _with_hidden_table(world)
    world.accounts.create("mei.two@test.invalid", "pw-not-real-1", "Test Mei Lim", "co-a", ["analyst"])  # the same display name as the login below
    mei = login(world, "co-a", "Mei Lim", ("analyst",))  # named on K03, but another account has her display name: not named for it
    assert b"Exposure to one name" not in mei.get(CAT).content
    assert S.view(plane, BID, C.Viewer("Test Mei Lim", frozenset({"analyst"})))["findings"].get("K03") is not None  # alone, the name works


def test_refresh_says_only_ok(world):
    seed(world)
    assert login(world, "co-a", "Pat Owner", ("company_admin",)).post(CAT + "/refresh").json() == {"status": "ok"}


ROUTES = [("get", ""), ("post", "/refresh"), ("post", "/tables/rows"), ("put", "/tables/rows/T01"), ("post", "/conflicts/c-x/settle"),
          ("post", "/suggest-fields"), ("get", "/export")]


@pytest.mark.parametrize("method,path", ROUTES)
def test_signed_out_is_401_and_a_write_without_csrf_is_403(world, method, path):
    from fastapi.testclient import TestClient
    seed(world)
    out = TestClient(world.app)
    assert getattr(out, method)(CAT + path).status_code == 401
    if method != "get":
        c = login(world, "co-a", "Pat Owner", ("company_admin",))
        c.headers.pop("x-csrf-token")
        assert getattr(c, method)(CAT + path, json={}).status_code == 403


def test_a_source_row_follows_the_list_of_every_measure_it_serves_at_once():
    cat, conflicts = C.build(None, kpis(), answers())
    C.edit_cells(cat, conflicts, "sources", "S01", {"Who may see it": "Tom, Test Mei Lim"}, "Arjun")
    C.add_row(cat, conflicts, "tables", {"Source ID": "S01", "Related KPIs": "K03"}, "Arjun")  # K03 is limited to Mei
    shown, gov = C.with_derived(cat), {k["id"]: k["governance"] for k in kpis()}
    s1 = lambda who: next(r for r in C.apply_governance(shown, C.guards(cat, gov), viewer(who, "analyst"))["sources"] if C.row_id("sources", r) == "S01")  # noqa: E731
    assert s1("Tom").get(C.HIDDEN) and not s1("Test Mei Lim").get(C.HIDDEN)  # on the source's own list but not on K03's: its name is hidden from Tom
