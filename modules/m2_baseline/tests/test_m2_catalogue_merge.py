"""CRITIC-M2 round 3, N-B and N-C: a source whose personal-data answer is "not sure" is shown to the analyst (flagged) unless a restricted measure
is tied to it; fields and extractions are merged across measures; no blank rows; business meaning and connection details are honest.
Synthetic family-office content only."""
import io
import zipfile

from story_answers import MAILBOX, NORTHGATE, PAY, WORKBOOK, answer, answers, kpis, row

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain.catalogue import text_of as t
from modules.m2_baseline.domain.xlsx_export import build_xlsx

TOM = C.Viewer("Tom Ng", frozenset({"analyst"}))
ADMIN = C.Viewer("Mei Tan", frozenset({"company_admin"}))
NOTE = "rows are hidden until the organiser decides on personal data"


def gov(ks):
    return {k["id"]: k["governance"] for k in ks}


def seen_by(cat, ks, viewer, drop=True):
    return C.view_of(cat, C.guards(cat, gov(ks)), viewer, drop=drop)


def by_name(rows):
    return {t(r["Source name"]): r for r in rows if not r.get(C.HIDDEN)}


# ---- N-B: "not sure" ------------------------------------------------------------------------------------------------------------

def test_a_not_sure_source_is_shown_to_the_analyst_flagged_with_its_tables_and_conflict():
    cat, conflicts = C.build(None, kpis(), answers())
    shown, _ = seen_by(cat, kpis(), TOM, drop=False)
    north = by_name(shown["sources"])[NORTHGATE]
    assert t(north["Contains personal data?"]) == "Not sure" and north.get(C._UNDECIDED) is True and not north.get(C.HIDDEN)
    assert any(t(r.get("Name of table, file or document type")) == "NGC_Statement CSV" for r in shown["tables"])
    sid = C.row_id("sources", north)
    assert sid in {c["row_id"] for c in conflicts}  # the custodian's arrival-time conflict exists, on a row the analyst may now see


def test_a_not_sure_source_tied_to_a_restricted_kpi_stays_hidden_and_pay_still_is():
    ks = kpis()
    ks[-1] = {**ks[-1], "governance": {"personal": "no", "sensitive": True, "may_see": ["Lina Ho"]}}  # K18: sensitive counts as personal
    mine = answers()
    mine[-1] = answer("a6", "Lina Ho", "K18", sources=[row(PAY, "excel", "structured", "HR share", "Lina Ho", "email_forward", "quarterly", "",
                                                           "Pay review", "salary_band", personal="not_sure")])
    cat, _ = C.build(None, ks, mine)
    shown, _ = seen_by(cat, ks, TOM)
    dumped = str(shown)
    assert PAY not in dumped and "Pay review" not in dumped and "salary_band" not in dumped and "K18" not in dumped
    assert by_name(shown["sources"])[NORTHGATE]  # the open not-sure one is there


def test_a_not_sure_source_with_a_named_list_stays_hidden_even_with_no_table():
    cat, conflicts = C.build(None, kpis(), answers())
    C.edit_cells(cat, conflicts, "sources", "S01", {"Who may see it": "Arjun Rao"}, "Mei Tan")
    assert C.guards(cat, gov(kpis()))[("sources", "S01")]
    shown, _ = seen_by(cat, kpis(), TOM)
    assert NORTHGATE not in str(shown)
    assert NORTHGATE in str(seen_by(cat, kpis(), C.Viewer("Arjun Rao", frozenset({"analyst"})))[0])


def test_a_personal_looking_field_of_a_not_sure_source_stays_hidden():
    cat, conflicts = C.build(None, kpis(), answers())
    tid = next(C.row_id("tables", r) for r in cat["tables"] if t(r["Name of table, file or document type"]) == "NGC_Statement CSV")
    C.add_row(cat, conflicts, "fields", {"Item ID": tid, "Field name as in the source": "account_holder", "Feeds KPI": "K01", "Personal data class": "Personal data"}, "Mei Tan")
    shown, _ = seen_by(cat, kpis(), TOM)
    names = {t(r["Field name as in the source"]) for r in shown["fields"]}
    assert "cash_balance" in names and "account_holder" not in names


def test_extractions_follow_their_source_and_kpi_so_the_analyst_sees_the_non_pay_ones():
    cat, _ = C.build(None, kpis(), answers())
    shown, _ = seen_by(cat, kpis(), TOM)
    assert {t(r["What to extract"]) for r in shown["extractions"]} >= {"due date", "amount", "fund", "period return", "net asset value"}


def test_the_hidden_count_is_stated_plainly_and_only_when_something_is_hidden():
    cat, conflicts = C.build(None, kpis(), answers())
    stubs, _ = seen_by(cat, kpis(), TOM, drop=False)
    assert sum(1 for tab in C.TABS for r in stubs[tab] if r.get(C.HIDDEN)) > 0  # pay is hidden...
    assert C.hidden_note(stubs, cat, gov(kpis())) is None  # ...but is never counted or hinted at: no "not sure" row is hidden
    tid = next(C.row_id("tables", r) for r in cat["tables"] if t(r["Name of table, file or document type"]) == "NGC_Statement CSV")
    C.add_row(cat, conflicts, "fields", {"Item ID": tid, "Field name as in the source": "account_holder", "Feeds KPI": "K01", "Personal data class": "Personal data"}, "Mei Tan")
    stubs, _ = seen_by(cat, kpis(), TOM, drop=False)
    assert C.hidden_note(stubs, cat, gov(kpis())) == "1 row is hidden until the organiser decides on personal data"  # only the personal-looking field of the not-sure source
    assert C.hidden_note(seen_by(cat, kpis(), ADMIN, drop=False)[0], cat, gov(kpis())) is None


def test_a_hidden_pay_row_is_not_counted_even_when_its_source_is_not_sure():
    ks = kpis()
    ks[-1] = {**ks[-1], "governance": {"personal": "no", "sensitive": True, "may_see": ["Lina Ho"]}}
    mine = answers()
    mine[-1] = answer("a6", "Lina Ho", "K18", sources=[row(PAY, "excel", "structured", "HR share", "Lina Ho", "email_forward", "quarterly", "",
                                                           "Pay review", "salary_band", personal="not_sure")])
    cat, _ = C.build(None, ks, mine)
    stubs, _ = seen_by(cat, ks, TOM, drop=False)
    assert C.hidden_note(stubs, cat, gov(ks)) is None


def test_the_admin_decides_on_the_source_and_it_opens():
    cat, conflicts = C.build(None, kpis(), answers())
    sid = C.row_id("sources", by_name(cat["sources"])[NORTHGATE])
    C.edit_cells(cat, conflicts, "sources", sid, {"Contains personal data?": "No"}, "Mei Tan")
    north = by_name(seen_by(cat, kpis(), TOM)[0]["sources"])[NORTHGATE]
    assert C._UNDECIDED not in north
    # and a rebuild keeps the decision
    again, _ = C.build(cat, kpis(), answers(), conflicts)
    assert t(by_name(again["sources"])[NORTHGATE]["Contains personal data?"]) == "No"


# ---- N-C: duplicates ------------------------------------------------------------------------------------------------------------

def many():
    ks = kpis()
    ks += [{**ks[1], "id": "K05", "name": "Notices on time"}, {**ks[1], "id": "K06", "name": "Notices amended"}]
    ks[-1] = {**ks[-1], "definition": {"value": None, "mark": "unknown", "by": "Lens", "from": "kpis.json", "at": None}}

    def mail(i, who, kpi, read):
        return answer(i, who, kpi, sources=[
            row(MAILBOX, "email", "unstructured", "capital-calls mailbox", who, "email_forward", "ad_hoc", "", "Capital call notices", "", read),
            row(WORKBOOK, "excel", "structured", "Investments share", "Tom Ng", "manual_entry", "quarterly", "", "Fund returns",
                "period_return, Period_Return, Fund Name")])
    mine = [mail("m1", "Sara Lim", "K04", "Capital call notices: due date, Capital call notices: amount"),
            mail("m2", "Sara Lim", "K05", "Capital call notices: Due Date, Capital call notices: amount"),
            mail("m3", "Mei Tan", "K06", "Capital call notices:  due date")]
    return ks, mine


def test_fields_and_extractions_merge_across_kpis_and_keep_every_kpi():
    ks, mine = many()
    cat, _ = C.build(None, ks, mine)
    ex = {t(r["What to extract"]): t(r["Feeds KPI"]) for r in cat["extractions"]}
    assert ex == {"due date": "K04, K05, K06", "amount": "K04, K05"}
    fields = {t(r["Field name as in the source"]).lower(): t(r["Feeds KPI"]) for r in cat["fields"]}
    assert fields == {"period_return": "K04, K05, K06", "fund name": "K04, K05, K06"}
    assert len(cat["fields"]) == 2 and len(cat["extractions"]) == 2
    again, _ = C.build(cat, ks, mine)  # a rebuild adds nothing and moves nothing
    assert [t(r["Feeds KPI"]) for r in again["extractions"]] == [t(r["Feeds KPI"]) for r in cat["extractions"]] and len(again["fields"]) == 2


def test_two_rows_with_different_person_edits_in_one_column_are_both_kept():
    ks, mine = many()
    cat, _ = C.build(None, ks, mine)
    src = cat["fields"][0]
    copy = C.new_row("fields", C.next_id("fields", cat["fields"]))
    copy.update({h: dict(src[h]) for h in ("Item ID", "Field name as in the source")})
    C.edit_cells(cat, [], "fields", C.row_id("fields", src), {"Notes": "first edit"}, "Mei Tan")
    cat["fields"].append(copy)
    C.edit_cells(cat, [], "fields", C.row_id("fields", copy), {"Notes": "second edit"}, "Sara Lim")
    fresh, _ = C.build(cat, ks, mine)
    assert {t(r["Notes"]) for r in fresh["fields"]} >= {"first edit", "second edit"}
    plain = C.new_row("fields", "F900")  # an edit on only one of two copies still merges, and the edit survives
    plain.update({h: dict(src[h]) for h in ("Item ID", "Field name as in the source")})
    merged = C.build({**cat, "fields": [src, plain]}, ks, mine)[0]["fields"]
    same = [r for r in merged if C.norm(t(r["Field name as in the source"])) == C.norm(t(src["Field name as in the source"]))]
    assert len(same) == 1 and t(same[0]["Notes"]) == "first edit"


def test_each_kpi_still_counts_its_merged_fields_and_extractions():
    ks, mine = many()
    cat, _ = C.build(None, ks, mine)
    full = {C.row_id("kpis", r): r for r in C.with_derived(cat)["kpis"]}
    assert [C.value_of(full["K05"][h]) for h in ("Fields mapped", "Extractions mapped")] == [2, 2]
    assert [C.value_of(full["K06"][h]) for h in ("Fields mapped", "Extractions mapped")] == [2, 1]


def test_old_duplicates_and_blank_extraction_rows_are_cleaned_on_the_next_fill():
    ks, mine = many()
    cat, _ = C.build(None, ks, mine)
    for k in ("K04", "K05"):  # what an earlier build left: one copy per measure, and rows with nothing in them
        for tab, item, what in (("fields", "Item ID", "Field name as in the source"), ("extractions", "Item ID (document type)", "What to extract")):
            src = cat[tab][0]
            copy = C.new_row(tab, C.next_id(tab, cat[tab]))
            copy[item], copy[what], copy["Feeds KPI"] = dict(src[item]), dict(src[what]), C.prov(k, "stated", "Lens", "answers.json")
            cat[tab].append(copy)
    cat["extractions"] += [C.new_row("extractions", "X900"), C.new_row("extractions", "X901")]
    fresh, _ = C.build(cat, ks, mine)
    assert len(fresh["fields"]) == 2 and len(fresh["extractions"]) == 2
    assert all(not C.is_blank(r["What to extract"]) or not C.is_blank(r["Item ID (document type)"]) for r in fresh["extractions"])


def test_no_extraction_row_is_blank_in_a_fresh_build():
    ks, mine = many()
    cat, _ = C.build(None, ks, mine + [answer("m9", "Sara Lim", "K05", sources=[row(MAILBOX, "email", "unstructured", "", "", "", "", "", "Capital call notices")])])
    assert all(not (C.is_blank(r["Item ID (document type)"]) and C.is_blank(r["What to extract"])) for r in cat["extractions"])


def test_business_meaning_is_never_the_measures_definition_and_says_not_available_yet():
    ks, mine = many()
    cat, _ = C.build(None, ks, mine)
    assert {t(r["Business meaning"]) for r in cat["fields"]} == {""}  # a field's meaning is its own description, never the measure's definition (critic round 5)
    assert all(r["Business meaning"]["mark"] == "unknown" and r["Business meaning"]["from"] == C.NOT_YET for r in cat["fields"])
    only_k06 = [m for m in mine if m["kpi_id"] == "K06"]
    cat6, _ = C.build(None, ks, only_k06)
    assert all(r["Business meaning"]["mark"] == "unknown" and r["Business meaning"]["from"] == C.NOT_YET for r in cat6["fields"])
    book = zipfile.ZipFile(io.BytesIO(build_xlsx(C.with_derived(cat6)))).read("xl/worksheets/sheet4.xml").decode()
    assert "Not available yet" in book


def test_connection_details_are_blank_unless_someone_gave_one():
    cat, _ = C.build(None, kpis(), answers())
    assert all(C.is_blank(s["Connection details (no passwords)"]) for s in cat["sources"])
    cat["sources"][0]["Connection details (no passwords)"] = C.prov(t(cat["sources"][0]["Where it lands or lives"]), "stated", "Lens", "answers.json")
    fresh, _ = C.build(cat, kpis(), answers())  # an old copy of the "lands" text is cleared
    assert C.is_blank(fresh["sources"][0]["Connection details (no passwords)"])
    C.edit_cells(fresh, [], "sources", "S01", {"Connection details (no passwords)": "sftp.example.test/in"}, "Mei Tan")
    assert t(C.build(fresh, kpis(), answers())[0]["sources"][0]["Connection details (no passwords)"]) == "sftp.example.test/in"  # a person's own words stay


def test_the_export_follows_the_same_rules():
    ks, mine = many()
    cat, _ = C.build(None, ks, mine)
    shown, _ = seen_by(cat, ks, ADMIN)
    sheet = zipfile.ZipFile(io.BytesIO(build_xlsx(shown))).read("xl/worksheets/sheet5.xml").decode()
    assert sheet.count("K04, K05, K06") == 1 and sheet.count(">due date<") == 1
