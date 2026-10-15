"""The story check for module 2 (demo story 12_owner_answers_example.md, as row-shaped answers in story_answers.py): the catalogue has one
source per system with its type and connection, tables, fields and extractions are filled, a real disagreement is a conflict, and the
process map has team lanes in step order with the missing step drawn dashed and the person to ask named. Synthetic data only."""
import pytest
from story_answers import BLUEWATER, INDEX, MAILBOX, NORTHGATE, PAY, VENDOR, WORKBOOK, answer, answers, kpis, row

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import process_map as D
from modules.m2_baseline.domain.catalogue import text_of as t


@pytest.fixture(scope="module")
def built():
    return C.build(None, kpis(), answers())


def by_name(rows):
    return {t(r["Source name"]): r for r in rows}


def test_the_story_gives_one_source_per_system_not_one_per_sentence(built):
    cat, _ = built
    assert sorted(by_name(cat["sources"])) == sorted([WORKBOOK, MAILBOX, VENDOR, INDEX, NORTHGATE, BLUEWATER, PAY])


def test_each_source_has_its_type_structure_connection_owner_and_arrival(built):
    s = by_name(built[0]["sources"])
    got = {n: (t(r["Source type"]), t(r["Structured or unstructured"]), t(r["Connection method"])) for n, r in s.items()}
    assert got[WORKBOOK] == ("Manual workbook (Excel)", "Structured", "Typed in by hand")  # the owner's words: not in the dropdown, so not replaced
    assert got[MAILBOX] == ("Email with attachment", "Unstructured", "Email forwarded to us")
    assert got[VENDOR][0] == got[INDEX][0] == "Third-party portal or API" and got[VENDOR][1:] == ("Structured", "I download it")
    assert got[NORTHGATE] == ("File drop: CSV or Excel", "Structured", "Scheduled file drop")
    assert got[BLUEWATER][0] == "Third-party portal or API"
    assert t(s[NORTHGATE]["How often it arrives"]) == "Daily" and t(s[BLUEWATER]["Data owner"]) == "Arjun Rao"
    assert t(s[MAILBOX]["Data owner"]) == "Sara Lim" and t(s[MAILBOX]["Where it lands or lives"]) == "capital-calls mailbox"


def test_only_the_pay_workbook_is_personal_and_not_sure_stays_personal(built):
    s = by_name(built[0]["sources"])
    assert t(s[PAY]["Contains personal data?"]) == "Yes" and t(s[PAY]["Who may see it"]) == "Lina Ho, Mei Tan"
    assert t(s[NORTHGATE]["Contains personal data?"]) == "Not sure"
    assert {t(s[n]["Contains personal data?"]) for n in (WORKBOOK, VENDOR, INDEX, BLUEWATER, MAILBOX)} == {"No"}


def test_an_unknown_a_person_gave_stays_unknown_and_visible(built):
    vendor = by_name(built[0]["sources"])[VENDOR]
    assert vendor["Expected arrival time or SLA"]["mark"] == "unknown" and C.is_blank(vendor["Expected arrival time or SLA"])


def test_tables_are_filled_from_the_listed_tables_files_and_document_types_with_their_kpis(built):
    cat, _ = built
    sid = {t(r["Source name"]): C.row_id("sources", r) for r in cat["sources"]}
    tables = {t(r["Name of table, file or document type"]): r for r in cat["tables"]}
    assert set(tables) == {"NGC_Statement CSV", "NAV report", "Capital call notices", "Manager statements", "Fund returns", "Benchmark levels",
                           "Index levels", "S&P 500 levels", "MSCI World levels", "Pay review"}
    assert t(tables["NGC_Statement CSV"]["Source ID"]) == sid[NORTHGATE] and t(tables["NGC_Statement CSV"]["Kind"]) == "File"
    assert t(tables["Capital call notices"]["Kind"]) == "Email type" and t(tables["Capital call notices"]["Related KPIs"]) == "K04"
    assert t(tables["Manager statements"]["Source ID"]) == sid[MAILBOX] == t(tables["Capital call notices"]["Source ID"])
    assert t(tables["Fund returns"]["Related KPIs"]) == "K15" and t(tables["Pay review"]["Related KPIs"]) == "K18"
    assert t(tables["NGC_Statement CSV"]["How often it arrives"]) == "Daily"


def test_fields_come_from_the_key_fields_each_tied_to_its_table_and_kpi(built):
    cat, _ = built
    tid = {t(r["Name of table, file or document type"]): C.row_id("tables", r) for r in cat["tables"]}
    fields = {(t(r["Field name as in the source"]), t(r["Feeds KPI"])): t(r["Item ID"]) for r in cat["fields"]}
    assert fields[("cash_balance", "K01")] == tid["NGC_Statement CSV"] and fields[("valuation_date", "K12")] == tid["NAV report"]
    assert fields[("period_return", "K15")] == tid["Fund returns"]
    assert fields[("index_level", "K15")] in {tid["Index levels"], tid["Benchmark levels"]}
    assert fields[("salary_band", "K18")] == tid["Pay review"]
    assert len({(t(r["Item ID"]), t(r["Field name as in the source"]), t(r["Feeds KPI"])) for r in cat["fields"]}) == len(cat["fields"])  # none twice


def test_extractions_are_for_unstructured_document_types_with_what_to_read_out(built):
    cat, _ = built
    tid = {t(r["Name of table, file or document type"]): C.row_id("tables", r) for r in cat["tables"]}
    got = {(t(r["Item ID (document type)"]), t(r["What to extract"]), t(r["Feeds KPI"])) for r in cat["extractions"]}
    assert (tid["Capital call notices"], "due date", "K04") in got and (tid["Capital call notices"], "fund", "K04") in got
    assert (tid["Manager statements"], "net asset value", "K15") in got
    assert not any(x[0] in {tid["Fund returns"], tid["NAV report"]} for x in got)  # structured tables are not read out of documents


def test_a_document_type_with_nothing_to_read_out_still_gets_a_row_so_the_gap_shows():
    rows = [r for r in answers() if r["id"] != "a3"]  # Sara's call notices, with the read-out list, are gone; the mailbox stays through Tom
    cat, _ = C.build(None, kpis(), rows)
    only = [r for r in cat["extractions"] if t(r["Feeds KPI"]) == "K15"]
    assert {t(r["What to extract"]) for r in only} == {"period return", "net asset value"}


def test_each_kpi_counts_what_is_mapped_to_it(built):
    full = {C.row_id("kpis", r): r for r in C.with_derived(built[0])["kpis"]}
    counts = {k: [C.value_of(full[k][h]) for h in ("Tables mapped", "Fields mapped", "Extractions mapped")] for k in full}
    assert counts["K04"][0] == 1 and counts["K04"][2] == 3 and counts["K15"][0] >= 5 and counts["K18"] == [1, 2, 0]
    assert "nothing_mapped" not in C.kpi_findings(built[0])["K15"]


def test_two_owners_giving_different_arrival_times_for_one_system_is_a_conflict_found_by_system(built):
    cat, conflicts = built
    (c,) = [c for c in conflicts if c["state"] == "open" and c["column"] != "Contains personal data?"]  # Arjun "Not sure" and Sara "no" is the personal-data conflict (r4-2)
    assert (c["tab"], c["column"]) == ("sources", "Expected arrival time or SLA")
    assert {(v["by"], v["value"]) for v in c["versions"]} == {("Arjun Rao", "by 12:00 on working days"), ("Sara Lim", "around 16:00")}
    row = by_name(cat["sources"])[NORTHGATE]
    assert row["Expected arrival time or SLA"]["mark"] == "unknown"  # Lens never picks
    assert t(row["How often it arrives"]) == "Daily"  # they agree about how often: no conflict there


def test_a_rebuild_changes_nothing_and_ids_stay(built):
    cat, conflicts = built
    again, again_conflicts = C.build(cat, kpis(), answers(), conflicts)
    assert [len(again[k]) for k in C.TABS] == [len(cat[k]) for k in C.TABS]
    assert [C.row_id("tables", r) for r in again["tables"]] == [C.row_id("tables", r) for r in cat["tables"]]
    assert [c["id"] for c in again_conflicts] == [c["id"] for c in conflicts]


def test_a_personal_row_and_its_tables_and_fields_are_hidden_from_someone_not_named(built):
    cat, _ = built
    gov = {k["id"]: k["governance"] for k in kpis()}
    shown, _ = C.view_of(cat, C.guards(cat, gov), C.Viewer("Tom Ng", frozenset({"analyst"})), drop=True)
    dumped = str(shown)
    assert PAY not in dumped and "Pay review" not in dumped and "salary_band" not in dumped
    assert NORTHGATE in dumped  # "not sure" and open to the analyst now, flagged (CRITIC-M2 N-B); pay stays hidden
    assert WORKBOOK in dumped and "Fund returns" in dumped


def _shared_with_a_restricted_kpi():
    """K01 (open) and K18 (sensitive, named people only) list the same system; K18's row carries values only Lina may see."""
    mine = [a for a in answers() if a["kpi_id"] != "K01"]
    mine.append(answer("b1", "Arjun Rao", "K01", sources=[row("Shared drive file", "excel", "structured", "Finance share", "Arjun Rao", "manual_entry",
                                                              "daily", "", "Open table", "open_field")]))
    mine.append(answer("b2", "Lina Ho", "K18", sources=[row("shared  DRIVE file", "excel", "structured", "HR share", "Lina Ho", "manual_entry",
                                                            "monthly", "SECRETSLA", "Secret table, Open table", "secret_field", personal="no")]))
    cat, conflicts = C.build(None, kpis(), mine)
    gov = {k["id"]: k["governance"] for k in kpis()}
    shown, _ = C.view_of(cat, C.guards(cat, gov), C.Viewer("Tom Ng", frozenset({"analyst"})), drop=True)
    return cat, conflicts, shown


def test_a_restricted_kpi_sharing_a_system_with_an_open_one_adds_nothing_the_analyst_can_see():
    _, conflicts, shown = _shared_with_a_restricted_kpi()
    src = by_name(shown["sources"])["Shared drive file"]
    assert t(src["Where it lands or lives"]) == "Finance share" and t(src["Data owner"]) == "Arjun Rao" and t(src["How often it arrives"]) == "Daily"
    dumped = str(shown) + str([c for c in conflicts if c["row_id"] in {C.row_id("sources", r) for r in shown["sources"]}])
    for leak in ("Lina", "HR share", "K18", "SECRETSLA", "Secret table", "secret_field"):
        assert leak not in dumped
    assert conflicts == []  # a version only a hidden KPI holds is no disagreement anyone may see


def test_an_open_source_does_not_show_its_table_that_relates_to_a_restricted_kpi():
    cat, _, shown = _shared_with_a_restricted_kpi()
    names = {t(r["Name of table, file or document type"]) for r in cat["tables"]}
    assert {"Open table", "Secret table"} <= names
    open_row = next(r for r in cat["tables"] if t(r["Name of table, file or document type"]) == "Open table")
    assert "K18" in t(open_row["Related KPIs"]) and not any("Open table" in str(r) or "Secret table" in str(r) for r in shown["tables"])
    assert by_name(shown["sources"])["Shared drive file"]  # the source itself is still there


def test_a_system_only_a_restricted_kpi_uses_is_personal_and_named_people_only():
    cat, _, _ = _shared_with_a_restricted_kpi()
    pay = by_name(cat["sources"])[PAY]
    assert t(pay["Contains personal data?"]) == "Yes" and t(pay["Who may see it"]) == "Lina Ho, Mei Tan"


def test_who_may_see_a_system_two_restricted_kpis_use_is_the_narrowest_list():
    ks = kpis()
    ks[-2] = {**ks[0], "id": "K17", "governance": {"personal": "yes", "sensitive": False, "may_see": ["Lina Ho", "Sara Lim"]}}
    mine = [answer("c1", "Lina Ho", "K18", sources=[row("Joint file", "excel", "structured", "", "", "manual_entry", "daily", "", "", personal="yes")]),
            answer("c2", "Lina Ho", "K17", sources=[row("Joint file", "excel", "structured", "", "", "manual_entry", "daily", "", "", personal="yes")])]
    cat, _ = C.build(None, ks, mine)
    assert t(by_name(cat["sources"])["Joint file"]["Who may see it"]) == "Lina Ho"


# ---- the process map

def draw_k15(waiting=("Wei Chen",)):
    mine = [a for a in answers() if a["kpi_id"] == "K15"]
    return D.draw(mine, None, "pack", None, None, frozenset(), list(waiting))


def test_the_map_has_team_lanes_not_people_in_step_order_with_duplicate_teams_merged():
    m = draw_k15()
    assert m["lanes"] == ["Market data vendor API", "Custodian", "Operations", "Investments", "Risk", "HR"]  # "investments team" is Investments
    assert [(s["lane"], s["order"]) for s in m["steps"]][:3] == [("Market data vendor API", 1), ("Custodian", 2), ("Operations", 3)]
    assert [s["text"][:12] for s in m["steps"]] == ["Publishes in", "Sends the po", "Files the ma", "Pastes level", "Subtracts th",
                                                    "Works out ex", "Reads the co", "Takes the fi"]  # merged from Tom's and Mei's lists by step number
    assert [s["manual"] for s in m["steps"]] == [False, False, False, True, True, False, False, False]


def test_a_step_someone_else_described_for_an_owner_who_has_not_answered_is_dashed_with_that_person_to_ask():
    steps = {s["lane"]: s for s in draw_k15()["steps"]}
    wei = steps["Risk"]
    assert wei["confirmed"] is False and wei["ask"] == "Wei Chen" and D.mark_of(wei) == "to_confirm"
    assert all("ask" not in s and s["confirmed"] for lane, s in steps.items() if lane not in ("Risk",))
    assert "ask" not in draw_k15(waiting=())["steps"][5] and draw_k15(waiting=())["steps"][5]["confirmed"] is True  # nobody to ask: as said


def test_waiting_owners_are_the_nominated_owners_with_no_answer():
    k15 = next(k for k in kpis() if k["id"] == "K15")
    mine = [a for a in answers() if a["kpi_id"] == "K15"]
    assert D.waiting_owners(k15, mine) == ["Wei Chen", "Sara Lim"]  # the data owner and the process owner have not answered K15


def test_hops_without_a_step_number_still_run_upstream_then_in_between_then_downstream():
    a = {"id": "x", "owner_name": "A", "kpi_id": "k", "upstream": {"value": [{"who": "Up", "what": "gives"}], "mark": "stated"},
         "in_between": {"value": [{"who": "Mid", "step": "reshapes"}], "mark": "stated"},
         "downstream": {"value": [{"who": "Down", "what": "uses"}], "mark": "stated"}}
    b = {**a, "id": "y", "upstream": {"value": [{"who": "Up2", "what": "also gives"}], "mark": "stated"}}
    assert [s["lane"] for s in D.draw([a, b], None, "pack", None)["steps"]] == ["Up", "Up2", "Mid", "Down"]  # "reshapes" and "uses" said twice: drawn once
