"""IC-0d: the quality rules module 3's scan proposed sit beside a measure's signed catalogue entry: shown on the KPI row, in the Excel
export under the measure, and not for a reader who may not see the source they came from. Synthetic rows only."""
import io
import zipfile

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain.xlsx_export import build_xlsx

HEAD = C.Viewer("Somebody Else", frozenset({"analyst"}))  # named on the restricted source's list
OUTSIDER = C.Viewer("Outsider Test", frozenset({"analyst"}))
RULE = {"id": "S01:fill_rate:Fees Charged", "source_id": "S01", "kind": "fill_rate", "column": "Fees Charged", "figure": {"fill": 0.5, "empty": 20, "of": 40},
        "text": "“Fees Charged” is only 50% full (20 empty of 40 rows).", "state": "proposal", "by": "Lens",
        "provenance": {"from": "the scan of custodian.csv", "at": "2026-10-06"}}
OPEN_RULE = {**RULE, "id": "S02:period_gap:As at", "source_id": "S02", "kind": "period_gap", "text": "The data stops on 22 September."}


def catalogue():
    cat = C.empty_catalogue()
    for sid, personal in (("S01", "Yes"), ("S02", "No")):
        row = C.new_row("sources", sid)
        row["Source name"] = C.prov(f"File {sid}", "stated", "Test Owner")
        row["Contains personal data?"] = C.prov(personal, "stated", "Test Owner")
        row["Who may see it"] = C.prov("Somebody Else", "stated", "Test Owner")
        cat["sources"].append(row)
    k = C.new_row("kpis", "K01")
    k["KPI name"] = C.prov("Net fees", "stated", "Test Owner")
    cat["kpis"].append(k)
    return C.with_quality_rules(cat, {"K01": [RULE, OPEN_RULE]})


def shown(viewer, drop=False):
    cat = catalogue()
    return C.view_of(cat, C.guards(cat, {"K01": {"personal": "no", "sensitive": False}}), viewer, drop)[0]


def test_the_rules_sit_on_the_measure_beside_its_signed_cells():
    row = shown(HEAD)["kpis"][0]
    cell = row[C.QUALITY_RULES]
    assert cell["by"] == "Lens" and cell["mark"] == "guessed" and cell["rules"] == [RULE, OPEN_RULE]
    assert "50% full" in C.text_of(cell) and "the scan of custodian.csv" in C.text_of(cell)
    assert row["KPI name"]["value"] == "Net fees"  # nothing signed was touched


def test_a_reader_outside_the_restricted_source_sees_only_the_open_rule():
    for drop in (False, True):  # the screen and the export
        cell = shown(OUTSIDER, drop)["kpis"][0][C.QUALITY_RULES]
        assert cell["rules"] == [OPEN_RULE] and "Fees Charged" not in C.text_of(cell)


def test_no_rules_leaves_the_cell_empty():
    cat = C.with_quality_rules(catalogue(), {})
    assert C.is_blank(cat["kpis"][0].get(C.QUALITY_RULES))


def test_the_export_lists_the_rules_under_the_measure():
    def sheet(v):
        z = zipfile.ZipFile(io.BytesIO(build_xlsx(shown(v, True))))
        return "".join(z.read(n).decode() for n in z.namelist() if n.startswith("xl/worksheets/"))
    assert "Quality rules" in sheet(HEAD) and "Fees Charged" in sheet(HEAD)
    assert "Fees Charged" not in sheet(OUTSIDER) and "22 September" in sheet(OUTSIDER)
