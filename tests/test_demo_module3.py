"""Module 3 demo inputs (packs/family_office/1/demo_module3): they exist, parse, regenerate exactly, and the benchmark figures
that should match equal an independent calculation read back from the files."""
import csv
import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "packs" / "family_office" / "1" / "demo_module3"
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location("make_demo_module3", FOLDER / "make_demo_module3.py")
M = importlib.util.module_from_spec(_spec)
sys.modules["make_demo_module3"] = M  # dataclass-free module, but keeps tracebacks readable
_spec.loader.exec_module(M)

FILES = ["performance_workbook.xlsx", "custody_daily_positions.csv", "capital_calls_export.json", "index_levels.csv",
         "exposure_workbook.csv", "benchmarks_monthly_pack.csv"]


def read_csv(name):
    """First line is the 'Illustrative, synthetic' banner, then the header row."""
    lines = (FOLDER / name).read_text(encoding="utf-8").splitlines()
    assert "Illustrative, synthetic" in lines[0]
    return list(csv.DictReader(lines[1:]))


def read_xlsx():
    with zipfile.ZipFile(FOLDER / "performance_workbook.xlsx") as z:
        wb, sheet = z.read("xl/workbook.xml").decode(), z.read("xl/worksheets/sheet1.xml").decode()
    assert 'name="Sep 2026"' in wb and "Illustrative, synthetic" in sheet
    rows = []
    for r in re.findall(r"<row [^>]*>(.*?)</row>", sheet):
        cells = {}
        for ref, body in re.findall(r'<c r="([A-Z])\d+"[^>]*>(.*?)</c>', r):
            m = re.search(r"<t>(.*?)</t>", body) or re.search(r"<v>(.*?)</v>", body)
            cells[ref] = m.group(1)
        rows.append(cells)
    return [r for r in rows[3:]]  # banner, blank, header, then data


def test_workbook_is_valid_xml_with_the_real_namespace():
    from xml.etree import ElementTree as ET
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    with zipfile.ZipFile(FOLDER / "performance_workbook.xlsx") as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    assert wb.tag == f"{{{ns}}}workbook" and sheet.tag == f"{{{ns}}}worksheet"
    assert [s.get("name") for s in wb.iter(f"{{{ns}}}sheet")] == ["Sep 2026"]
    assert len(list(sheet.iter(f"{{{ns}}}row"))) - 3 == 40  # banner, blank, header, then 40 data rows


def test_files_exist_and_parse():
    for f in FILES + ["README.md"]:
        assert (FOLDER / f).is_file(), f
    assert len(read_xlsx()) == 40
    assert 250 <= len(read_csv("custody_daily_positions.csv")) <= 320
    doc = json.loads((FOLDER / "capital_calls_export.json").read_text(encoding="utf-8"))
    assert "Illustrative, synthetic" in doc["illustrative_synthetic"] and len(doc["notices"]) == 15
    assert len(read_csv("exposure_workbook.csv")) > 15
    assert not list(FOLDER.glob("*pay*")) and not list(FOLDER.glob("*bonus*"))  # the restricted file stays unknown


def test_script_reproduces_every_file_exactly(tmp_path):
    M.main(tmp_path)
    for f in FILES:
        assert (tmp_path / f).read_bytes() == (FOLDER / f).read_bytes(), f


def test_deliberate_problems_are_present():
    rows = read_xlsx()
    assert sum(1 for r in rows if "B" not in r) == 4  # asset class missing in some rows
    assert 15 <= sum(1 for r in rows if "F" in r) <= 25  # fees about half empty
    cust = read_csv("custody_daily_positions.csv")
    assert max(r["Val Date"] for r in cust) == "2026-09-22"
    assert min(r["Val Date"] for r in cust) < "2026-09-01"  # a few days of August
    assert len({r["Val Date"] for r in cust}) == 22
    assert max(r["Date"] for r in read_csv("index_levels.csv")) == "2026-09-22"  # last week of September missing
    assert [n["notice_ref"] for n in json.loads((FOLDER / "capital_calls_export.json").read_text())["notices"] if n["replaces"]] == ["CC-014"]


def test_matching_benchmarks_equal_the_calculation_from_the_files():
    bench = {r["Measure"]: r for r in read_csv("benchmarks_monthly_pack.csv")}
    perf = read_xlsx()
    f = lambda r, k: float(r.get(k, 0))
    # K10 private-market allocation
    private = sum(f(r, "D") for r in perf if r.get("B") in ("Private Equity", "Venture Capital"))
    assert float(bench["Private-market allocation"]["Figure"]) == round(private / sum(f(r, "D") for r in perf) * 100, 2)
    # K09 single-issuer concentration
    agg = {}
    for r in read_csv("exposure_workbook.csv"):
        agg[r["Issuer"]] = agg.get(r["Issuer"], 0) + float(r["Exposure Value (SGD)"])
    assert float(bench["Single-issuer concentration"]["Figure"]) == round(max(agg.values()) / sum(agg.values()) * 100, 2)
    # K04 known obligations due: open notices that no amendment replaces
    notices = json.loads((FOLDER / "capital_calls_export.json").read_text())["notices"]
    replaced = {n["replaces"] for n in notices}
    assert float(bench["Known obligations due"]["Figure"]) == sum(n["amt"] for n in notices if n["status"] == "open" and n["notice_ref"] not in replaced)
    # the pack's return is before fees: gap to the net-of-fee calculation is the fees
    start, gain, fees = sum(f(r, "C") for r in perf), sum(f(r, "D") - f(r, "C") - f(r, "E") for r in perf), sum(f(r, "F") for r in perf)
    assert float(bench["Manager performance versus benchmark"]["Figure"]) == round(gain / start * 100, 2)
    assert round((gain - fees) / start * 100, 2) != float(bench["Manager performance versus benchmark"]["Figure"])


def test_stale_share_differs_because_the_pack_is_as_at_30_sep():
    pack = float(next(r for r in read_csv("benchmarks_monthly_pack.csv") if r["Measure"] == "Stale-valuation share")["Figure"])
    assert M.compute()["K12"] != pack
    assert {r["Period end"] for r in read_csv("benchmarks_monthly_pack.csv")} == {"2026-09-30"}


def test_alpha_cannot_be_reproduced_without_index_levels():
    levels = [r["Date"] for r in read_csv("index_levels.csv")]
    assert not any(d > "2026-09-22" for d in levels) and "2026-09-30" not in levels


def test_seed_only_takes_the_two_document_folders():
    src = (ROOT / "tools" / "seed.py").read_text(encoding="utf-8")
    assert '"demo_documents"' in src and '"demo_story"' in src and "demo_module3" not in src
