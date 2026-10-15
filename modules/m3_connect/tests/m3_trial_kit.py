"""Kit for the M3-P03 tests: the demo inputs (packs/family_office/1/demo_module3) turned into the files P02 will write
(intake/<source>/rows.json, benchmarks.json) with small stdlib readers of our own, plus the sources file P01 writes, plus a model stub."""
import csv
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

from sh_platform.agents.protocols import ModelReply
from sh_platform.plane import PlaneStore

ROOT = Path(__file__).resolve().parents[3]
DEMO = ROOT / "packs" / "family_office" / "1" / "demo_module3"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NAMES = {"Fund / Manager": "manager", "Asset Cls": "asset_class", "Opening Value (SGD)": "opening_value", "Closing Value (SGD)": "closing_value",
         "Net Flows": "net_flows", "Fees Charged": "fees", "Period Return %": "period_return", "Val Date": "val_date", "Acct": "account",
         "Security": "security", "Mkt Value": "mkt_value", "Issuer": "issuer", "Exposure Value (SGD)": "exposure_value", "Date": "date", "Index": "index",
         "Level": "level", "amt": "amount", "due_dt": "due_date"}
SOURCES = {"s-perf": ("Performance workbook", ["K10", "K15", "K16"]), "s-custody": ("Northgate Custody daily file", ["K12"]),
           "s-calls": ("Capital-calls mailbox", ["K04"]), "s-index": ("Index provider feed", ["K16"]), "s-expo": ("Exposure workbook", ["K09"])}
BENCH_IDS = {"Known obligations due": "K04", "Single-issuer concentration": "K09", "Private-market allocation": "K10", "Stale-valuation share": "K12",
             "Manager performance versus benchmark": "K15", "Excess return versus benchmark (alpha)": "K16"}


def read_xlsx(path: Path) -> list[dict]:
    """Sheet 1, headers in row 3 (banner in row 1), inline strings: what the demo workbook has."""
    with zipfile.ZipFile(path) as z:
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows = []
    for r in sheet.iterfind(".//m:row", NS):
        cells = {re.match(r"[A-Z]+", c.get("r")).group(): ("".join(t.text or "" for t in c.iterfind(".//m:t", NS)) if c.get("t") == "inlineStr"
                                                              else (c.find("m:v", NS).text if c.find("m:v", NS) is not None else None)) for c in r.iterfind("m:c", NS)}
        rows.append([cells.get(chr(65 + i)) for i in range(max(map(ord, cells), default=64) - 64)] if cells else [])
    head, body = rows[2], rows[3:]
    return [{h: (r[i] if i < len(r) else None) for i, h in enumerate(head)} for r in body if any(r)]


def read_csv(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()[1:]  # the first line is the "illustrative" banner
    return list(csv.DictReader(lines))


def renamed(rows: list[dict]) -> list[dict]:
    return [{NAMES.get(k, k): (None if v in ("", None) else v) for k, v in r.items()} for r in rows]


def write(adir: Path, rel: str, data) -> None:
    p = adir / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def demo_files(adir: Path, skip: tuple = ()) -> None:
    """Writes the six demo sources' rows, the benchmarks and P01's sources file into an assessment folder."""
    adir.mkdir(parents=True, exist_ok=True)
    calls = json.loads((DEMO / "capital_calls_export.json").read_text(encoding="utf-8"))["notices"]
    data = {"s-perf": renamed(read_xlsx(DEMO / "performance_workbook.xlsx")), "s-custody": renamed(read_csv(DEMO / "custody_daily_positions.csv")),
            "s-calls": renamed(calls), "s-index": renamed(read_csv(DEMO / "index_levels.csv")), "s-expo": renamed(read_csv(DEMO / "exposure_workbook.csv"))}
    for sid, rows in data.items():
        if sid not in skip:
            write(adir, f"intake/{sid}/rows.json", rows)
    bench = [{"measure_id": BENCH_IDS[r["Measure"]], "figure": float(r["Figure"]), "unit": r["Unit"], "period_end": r["Period end"],
              "source_note": r["Where it came from"]} for r in read_csv(DEMO / "benchmarks_monthly_pack.csv")]
    write(adir, "benchmarks.json", bench)
    write(adir, "sources.json", [{"id": k, "name": n, "measures": m} for k, (n, m) in SOURCES.items()])


def pack_kpis() -> list[dict]:
    return yaml.safe_load((ROOT / "packs" / "family_office" / "1" / "kpi_tree.yaml").read_text(encoding="utf-8"))["kpis"]


def demo_inputs() -> dict:
    ks = {k["id"]: k for k in pack_kpis()}
    ms = [{"id": i, "name": ks[i]["name"], "restricted": False, "definition": ks[i]["definition"], "problem_ids": [], "owners": {}}
          for i in ("K04", "K09", "K10", "K12", "K15", "K16", "K18")]
    return {"measures": ms, "sources": [], "fields": [], "pain_points": [{"id": "p1", "title": "Late packs", "measures": ["K12"]}],
            "levers": [{"id": "l1", "title": "Faster feeds", "measures": ["K12", "K15"]}], "gaps": []}


class Gate:
    def is_enabled(self, company_id, module_id):
        return True


def plane(tmp_path):
    store = PlaneStore(tmp_path / "data")
    return (store.plane_for("co-test") if store.exists("co-test") else store.create("co-test")).ensure()


class Stub:
    """A model client: answers from a list (the last one repeats) and keeps every message it was sent."""

    def __init__(self, *answers):
        self.answers, self.sent = list(answers), []

    def complete(self, module_id, messages, tools=None):
        self.sent.append(messages)
        return ModelReply(text=self.answers[min(len(self.sent) - 1, len(self.answers) - 1)])

    @property
    def payload(self) -> str:
        return json.dumps(self.sent)
