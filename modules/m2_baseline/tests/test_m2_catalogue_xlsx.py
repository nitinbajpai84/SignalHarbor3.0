"""M2-18: the Excel export opens (well-formed zip and XML) and matches the template's tabs, headers, lists, formulas and dropdowns.
Reads the template with the stdlib only (no openpyxl). Synthetic family-office content."""
import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from m2_kit import login
from test_m2_catalogue import CAT, answers, kpis, seed

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain.xlsx_export import build_xlsx

TEMPLATE = Path(__file__).resolve().parents[3] / "docs" / "specs" / "signal-harbor-data-catalogue-template.xlsx"
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
SHEETS = ["Read me", "1 Sources", "2 Tables", "3 Fields", "4 Extractions", "5 KPIs", "Lists"]


def read_book(data: bytes) -> dict[str, dict]:
    """sheet name -> {'cells': {ref: text}, 'formulas': {ref: text}, 'validations': {sqref: formula}}"""
    z = zipfile.ZipFile(io.BytesIO(data))
    assert z.testzip() is None
    for name in z.namelist():
        if name.endswith((".xml", ".rels")):
            ET.fromstring(z.read(name))  # every part is well-formed XML
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    names = [s.get("name") for s in wb.iter(M + "sheet")]
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        shared = ["".join(t.text or "" for t in si.iter(M + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(M + "si")]
    out = {}
    for i, name in enumerate(names, 1):
        root = ET.fromstring(z.read(f"xl/worksheets/sheet{i}.xml"))
        cells, formulas = {}, {}
        for c in root.iter(M + "c"):
            f = c.find(M + "f")
            if f is not None:
                formulas[c.get("r")] = f.text
            elif c.get("t") == "inlineStr":
                cells[c.get("r")] = "".join(t.text or "" for t in c.iter(M + "t"))
            elif c.get("t") == "s":
                cells[c.get("r")] = shared[int(c.find(M + "v").text)]
        dvs = {d.get("sqref"): d.find(M + "formula1").text.lstrip("=") for d in root.iter(M + "dataValidation")}
        out[name] = {"cells": cells, "formulas": formulas, "validations": dvs}
    return out


def populated():
    fixed = {"a1": "2026-10-03T09:00:00+00:00", "a3": "2026-10-04T09:00:00+00:00"}  # a1 (Arjun) is earlier than a3 (Mei)
    rows = [{**a, **{k: {**v, "at": fixed.get(a["id"], "2026-10-03T09:00:00+00:00")} for k, v in a.items() if isinstance(v, dict) and "mark" in v}}
            for a in answers()]
    cat, conflicts = C.build(None, kpis(), rows)
    C.add_row(cat, conflicts, "tables", {"Source ID": "S01", "Kind": "File", "Name of table, file or document type": "statement.csv", "Related KPIs": "K02"}, "Arjun")
    C.add_row(cat, conflicts, "tables", {"Source ID": "S02", "Related KPIs": "Unknown"}, "Sara")
    C.add_row(cat, conflicts, "fields", {"Item ID": "T01", "Field name as in the source": "closing_balance", "Feeds KPI": "K02"}, "Arjun")
    return C.with_derived(cat)


def test_the_tabs_and_headers_equal_the_templates():
    tpl, mine = read_book(TEMPLATE.read_bytes()), read_book(build_xlsx(populated()))
    assert list(tpl) == list(mine) == SHEETS
    for name in SHEETS[1:6]:
        for ref in [r for r in tpl[name]["cells"] if re.fullmatch(r"[A-Z]+[1-4]", r)]:
            want = tpl[name]["cells"][ref]
            if isinstance(want, str):  # two guidance lines were reworded to stay neutral (fix round 1)
                want = want.replace("env:BANK_KEY", "env:PORTAL_KEY").replace("bank holidays", "public holidays")
            assert mine[name]["cells"].get(ref) == want, (name, ref)  # title, blurb, guidance and header rows
        # IC-0d adds one column after the template's last one on the KPIs tab: the proposed quality rules
        assert [r for r in mine[name]["cells"] if re.fullmatch(r"[A-Z]+4", r) and r != "V4"] == [r for r in tpl[name]["cells"] if re.fullmatch(r"[A-Z]+4", r)]


def test_read_me_and_lists_equal_the_templates_apart_from_the_example_rows_line():
    tpl, mine = read_book(TEMPLATE.read_bytes()), read_book(build_xlsx(populated()))
    assert mine["Lists"]["cells"] == tpl["Lists"]["cells"]  # every dropdown word, in the same cells
    diff = {r for r in tpl["Read me"]["cells"] if mine["Read me"]["cells"].get(r) != tpl["Read me"]["cells"][r]}
    assert diff == {"B14"} and set(mine["Read me"]["cells"]) == set(tpl["Read me"]["cells"])


def test_formulas_and_dropdowns_are_the_templates():
    tpl, mine = read_book(TEMPLATE.read_bytes()), read_book(build_xlsx(populated()))
    for name in SHEETS[1:6]:
        assert mine[name]["formulas"] == tpl[name]["formulas"], name  # Complete? and Ready? and the counts, row 5 to row 204
        assert mine[name]["validations"] == tpl[name]["validations"], name


def test_no_example_rows_and_the_rows_are_this_baselines():
    mine = read_book(build_xlsx(populated()))
    assert "EXAMPLE ROW" not in str(mine)
    assert [mine["1 Sources"]["cells"][f"A{n}"] for n in (5, 6, 7)] == ["S01", "S02", "S03"] and "A8" not in mine["1 Sources"]["cells"]
    assert [mine["5 KPIs"]["cells"][f"A{n}"] for n in (5, 6, 7)] == ["K01", "K02", "K03"]
    assert mine["2 Tables"]["cells"]["E6"] == "Unknown"  # a named person said they do not know; the template says to write Unknown
    assert mine["1 Sources"]["cells"]["B7"] == "Custody statements"


def test_how_sure_confirmed_by_and_date_are_filled_from_provenance():
    s = read_book(build_xlsx(populated()))["1 Sources"]["cells"]
    assert s["Q5"] == "Guessed" and (s["R5"], s["S5"]) == ("Mei, Arjun", "2026-10-04")  # an old one-line source is a guessed name; both owners named it, the later (a3, Mei) first, and the date is the later one
    assert s["Q7"] == "Guessed"


def test_an_unknown_stays_blank_and_never_looks_known():
    s = read_book(build_xlsx(populated()))["5 KPIs"]["cells"]
    assert "F7" not in s and "G7" not in s and "I7" not in s  # K03 has no owners and no tracking status: blank cells, not "Unknown"


def test_a_list_cell_holds_the_problems_of_one_kpi_row_together():
    k = read_book(build_xlsx(populated()))["5 KPIs"]["cells"]
    assert k["E5"] == "p1; p2" and k["B5"] == "Capital calls due, by date"


def test_text_is_escaped_and_control_characters_are_dropped():
    cat, conflicts = C.build(None, kpis(), answers())
    C.edit_cells(cat, conflicts, "sources", "S01", {"Connection details (no passwords)": "a < b & \"c\"\x07"}, "Arjun")
    assert read_book(build_xlsx(C.with_derived(cat)))["1 Sources"]["cells"]["H5"] == 'a < b & "c"'


def test_an_empty_catalogue_still_opens_with_every_tab():
    book = read_book(build_xlsx(C.with_derived(C.empty_catalogue())))
    assert list(book) == SHEETS and book["1 Sources"]["cells"]["B4"] == "Source name" and "A5" not in book["1 Sources"]["cells"]


def test_more_than_the_templates_204_rows_still_work():
    cat = C.empty_catalogue()
    for i in range(210):
        cat["sources"].append(C.new_row("sources", f"S{i + 1:02d}"))
    book = read_book(build_xlsx(C.with_derived(cat)))["1 Sources"]
    assert book["cells"]["A214"] == "S210" and "T214" in book["formulas"] and "T215" not in book["formulas"]
    assert book["validations"]["C5:C214"] == "Lists!$A$2:$A$10"


def test_the_route_returns_a_workbook_that_opens(world):
    seed(world)
    c = login(world, "co-a", "Pat Owner", ("company_admin",))
    c.post(CAT + "/refresh")
    r = c.get(CAT + "/export")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert "attachment" in r.headers["content-disposition"]
    assert list(read_book(r.content)) == [*SHEETS[:-1], "Governance", "Technical definitions", "Lists"]  # M2-E3 and M2-E1: their sheets come before the lists


def test_rows_a_person_may_not_see_are_not_in_the_file(world):
    seed(world)
    login(world, "co-a", "Pat Owner", ("company_admin",)).post(CAT + "/refresh")
    plain = read_book(login(world, "co-a", "Tom Hale", ("analyst",)).get(CAT + "/export").content)["5 KPIs"]["cells"]
    assert [plain[f"A{n}"] for n in (5, 6)] == ["K01", "K02"] and "A7" not in plain
    named = read_book(login(world, "co-a", "Mei Lim", ("analyst",)).get(CAT + "/export").content)["5 KPIs"]["cells"]
    assert named["A7"] == "K03"


def test_text_that_starts_like_a_formula_gets_a_quote_prefix_style():
    import re
    import zipfile
    from io import BytesIO
    cat, conflicts = C.build(None, [], [])
    C.add_row(cat, conflicts, "sources", {"Source name": "=HYPERLINK(\"x\")"}, "Sara")
    z = zipfile.ZipFile(BytesIO(build_xlsx(C.with_derived(cat))))
    sheet = z.read("xl/worksheets/sheet2.xml").decode()
    assert re.search(r'<c r="B5" s="12" t="inlineStr"><is><t xml:space="preserve">=HYPERLINK', sheet)
    assert 'quotePrefix="1"' in z.read("xl/styles.xml").decode()
