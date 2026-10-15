"""Regenerates the module 3 demo inputs (Illustrative Lakeside Family Office, September 2026). Synthetic: every value is invented.

Run: python make_demo_module3.py [output_folder]   (default: this folder). Deterministic: same bytes every run.
compute() is the answer key: the correct calculation over the sample files, used by tests/test_demo_module3.py.
Stdlib only; the .xlsx is written with zipfile + XML, like modules/m2_baseline/domain/xlsx_export.py.
"""
from __future__ import annotations

import csv
import io
import json
import random
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
TAG = "Illustrative, synthetic sample data. Not a real client."
PERIOD_END = "2026-09-30"
CUSTODY_LAST = date(2026, 9, 22)
PRIVATE = {"Private Equity", "Venture Capital"}


def bdays(a: date, b: date) -> list[date]:
    return [a + timedelta(d) for d in range((b - a).days + 1) if (a + timedelta(d)).weekday() < 5]


# ---- performance workbook ----------------------------------------------------------------------------------------------------------
PERF_HEAD = ["Fund / Manager", "Asset Cls", "Opening Value (SGD)", "Closing Value (SGD)", "Net Flows", "Fees Charged", "Period Return %"]


def performance_rows() -> list[list]:
    rng = random.Random(11)
    classes = (["Public Equity"] * 12 + ["Fixed Income"] * 8 + ["Private Equity"] * 7 + ["Venture Capital"] * 4 + ["Hedge Funds"] * 4
               + ["Real Assets"] * 3 + ["Cash"] * 2)
    words = ["Lakeside", "Harbour", "Cedar", "Summit", "Willow", "Granite", "Maple", "Orchard", "Falcon", "Meadow"]
    kinds = {"Public Equity": "Equity Fund", "Fixed Income": "Bond Mandate", "Private Equity": "Buyout Fund", "Venture Capital": "Venture Fund",
             "Hedge Funds": "Absolute Return Fund", "Real Assets": "Property Fund", "Cash": "Cash Account"}
    rows = []
    for i, ac in enumerate(classes):
        start = rng.randrange(8, 90) * 100000
        flows = rng.choice([0, 0, 0, 50000, -50000, 100000, -100000]) if ac != "Cash" else rng.choice([-200000, 0, 200000])
        chg = 0.0 if ac == "Cash" else rng.uniform(-0.025, 0.045)
        end = round(start * (1 + chg)) + flows
        fee = int(round(start * rng.uniform(0.0003, 0.0012), -1)) if i % 2 == 0 else None  # about half the fee cells stay empty
        ret = round((end - start - flows) / start * 100, 2)
        rows.append([f"{words[i % 10]} {kinds[ac]} {i // 10 + 1}", ac, start, end, flows, fee, ret])
    for i in (3, 14, 22, 31):  # asset class missing in four rows
        rows[i][1] = None
    return rows


def xlsx_bytes(sheet: str, banner: str, head: list[str], rows: list[list]) -> bytes:
    def cell(r, c, v):
        ref = f"{chr(65 + c)}{r}"
        if v is None or v == "":
            return ""
        if isinstance(v, (int, float)):
            return f'<c r="{ref}"><v>{v}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>'
    allrows = [[banner], [], head] + rows
    data = "".join(f'<row r="{n}">{"".join(cell(n, c, v) for c, v in enumerate(r))}</row>' for n, r in enumerate(allrows, 1))
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pk = "http://schemas.openxmlformats.org/package/2006/relationships"
    ov = "application/vnd.openxmlformats-officedocument.spreadsheetml"
    parts = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/xl/workbook.xml" ContentType="{ov}.sheet.main+xml"/>'
            f'<Override PartName="/xl/worksheets/sheet1.xml" ContentType="{ov}.worksheet+xml"/></Types>',
        "_rels/.rels": f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{pk}"><Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{ns}" xmlns:r="{rel}"><sheets><sheet name="{escape(sheet)}" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{pk}"><Relationship Id="rId1" Type="{rel}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{ns}"><sheetData>{data}</sheetData></worksheet>',
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, xml in parts.items():
            info = zipfile.ZipInfo(name, (2026, 10, 1, 0, 0, 0))  # fixed time: same bytes every run
            info.create_system = 0  # zipfile stamps the host OS (3 on Linux, 0 on Windows); fix it so every OS writes the same bytes
            z.writestr(info, xml, zipfile.ZIP_DEFLATED)
    return out.getvalue()


# ---- custody ------------------------------------------------------------------------------------------------------------------------
CUSTODY_HEAD = ["Val Date", "Acct", "Security", "Qty", "Price", "Mkt Value", "Ccy"]
SECS = [("ACC-01", "Global Equity ETF A", "USD", 4200, 52.0), ("ACC-01", "SGD Govt Bond 2030", "SGD", 90000, 1.02), ("ACC-02", "Regional Bank Share", "SGD", 21000, 9.4),
        ("ACC-02", "Tech Leader Share", "USD", 800, 310.0), ("ACC-03", "Corporate Bond 2029", "USD", 60000, 0.99), ("ACC-03", "Global Equity ETF B", "USD", 5100, 41.5),
        ("ACC-04", "Utility Share", "SGD", 15000, 3.3), ("ACC-04", "Treasury Bill Dec", "SGD", 120000, 0.995), ("ACC-05", "Infrastructure Trust", "SGD", 33000, 1.85),
        ("ACC-05", "Healthcare Share", "USD", 1100, 142.0), ("ACC-06", "Property Trust Units", "SGD", 28000, 2.1), ("ACC-07", "Unlisted Note X", "SGD", 100, 5200.0),
        ("ACC-07", "Unlisted Note Y", "SGD", 80, 6100.0), ("ACC-07", "Private Placement Z", "USD", 60, 8400.0)]
STALE_AFTER = date(2026, 9, 11)  # the last three (illiquid) positions stop being priced here
STALE_DAYS = 5  # a position is stale when its last valuation is more than 5 business days before the file's last date


def custody_rows() -> list[list]:
    rng = random.Random(23)
    rows = []
    for k, (acc, sec, ccy, qty, p0) in enumerate(SECS):
        p = p0
        for d in bdays(date(2026, 8, 24), CUSTODY_LAST):
            if k >= 11 and d > STALE_AFTER:
                break
            p = round(p * (1 + rng.uniform(-0.01, 0.011)), 2)
            rows.append([d.isoformat(), acc, sec, qty, p, round(qty * p, 2), ccy])
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return rows


# ---- capital calls ------------------------------------------------------------------------------------------------------------------
def capital_calls() -> dict:
    funds = ["Cedar Buyout Fund II", "Summit Venture Fund III", "Granite Infrastructure Fund", "Willow Property Fund I", "Orchard Growth Fund"]
    amts = [250000, 400000, 180000, 320000, 150000, 500000, 275000, 210000, 360000, 120000, 440000, 190000, 300000, 260000, 380000]
    n = []
    for i, a in enumerate(amts):
        nd = date(2026, 8, 20) + timedelta(days=i * 3)
        due = nd + timedelta(days=12 + (i % 4) * 7)
        n.append({"notice_ref": f"CC-{i + 1:03d}", "fund": funds[i % 5], "notice_dt": nd.isoformat(), "due_dt": due.isoformat(), "amt": a, "ccy": "SGD",
                  "status": "paid" if due < date(2026, 9, 25) else "open", "replaces": None})
    n[6]["status"] = "open"
    # the amended notice: CC-014 replaces CC-007 (CC-007 asked for 275000, CC-014 asks for 290000, same fund)
    n[13].update(replaces="CC-007", amt=290000, notice_dt="2026-10-01", fund=n[6]["fund"], due_dt="2026-10-15", status="open")
    return {"illustrative_synthetic": TAG, "source": "Capital-calls mailbox export", "notices": n}


def open_calls(doc: dict) -> list[dict]:
    replaced = {x["replaces"] for x in doc["notices"] if x["replaces"]}
    return [x for x in doc["notices"] if x["status"] == "open" and x["notice_ref"] not in replaced]


# ---- index, exposure -----------------------------------------------------------------------------------------------------------------
def index_rows() -> list[list]:
    rng, rows = random.Random(5), []
    for name, lvl in (("Global Equity Index", 3150.0), ("SGD Bond Index", 218.0)):
        for d in bdays(date(2026, 8, 3), date(2026, 9, 22)):  # nothing after 22 Sep: the last week of September is missing
            lvl = round(lvl * (1 + rng.uniform(-0.008, 0.009)), 2)
            rows.append([d.isoformat(), name, lvl])
    return rows


EXPOSURE_HEAD = ["Issuer", "Country", "Sector", "Exposure Value (SGD)"]


def exposure_rows() -> list[list]:
    return [list(r) for r in [
        ("Alder Holdings", "Singapore", "Financials", 4100000), ("Birch Semiconductor", "United States", "Technology", 5200000),
        ("Cobalt Energy", "Norway", "Energy", 2300000), ("Dune Retail Group", "Australia", "Consumer", 1800000),
        ("Elm Healthcare", "United States", "Healthcare", 3300000), ("Fjord Shipping", "Norway", "Industrials", 1500000),
        ("Garnet Telecom", "Singapore", "Telecom", 2600000), ("Harbor REIT", "Singapore", "Real Estate", 2900000),
        ("Iris Utilities", "Japan", "Utilities", 1700000), ("Juniper Software", "United States", "Technology", 3900000),
        ("Kestrel Motors", "Germany", "Consumer", 2100000), ("Lotus Foods", "Thailand", "Consumer", 1200000),
        ("Maple Bank", "Canada", "Financials", 2800000), ("Nimbus Cloud", "United States", "Technology", 2400000),
        ("Onyx Mining", "Australia", "Materials", 1600000), ("Pine Logistics", "Singapore", "Industrials", 1400000),
        ("Quartz Pharma", "Switzerland", "Healthcare", 2200000), ("Reed Capital", "Singapore", "Financials", 1900000),
        ("Sable Networks", "United States", "Technology", 1300000), ("Tidal Power", "Denmark", "Utilities", 1100000),
        ("Umber Steel", "India", "Materials", 900000), ("Birch Semiconductor", "United States", "Technology", 1400000),
        ("Alder Holdings", "Singapore", "Financials", 700000), ("Vale Airlines", "Singapore", "Industrials", 800000)]]


# ---- answer key ------------------------------------------------------------------------------------------------------------------
def compute(perf=None, custody=None, calls=None, exposure=None) -> dict:
    """The correct calculation over the sample files (figures in per cent, or SGD for K04). Empty fees count as zero."""
    perf = perf or performance_rows()
    custody = custody or custody_rows()
    calls = calls or capital_calls()
    exposure = exposure or exposure_rows()
    start, tot_end = sum(r[2] for r in perf), sum(r[3] for r in perf)
    gain = sum(r[3] - r[2] - r[4] for r in perf)
    fees = sum(r[5] or 0 for r in perf)
    by_issuer: dict[str, float] = {}
    for r in exposure:
        by_issuer[r[0]] = by_issuer.get(r[0], 0) + r[3]
    last: dict[tuple, str] = {}
    for r in custody:
        last[(r[1], r[2])] = max(last.get((r[1], r[2]), ""), r[0])
    top = max(r[0] for r in custody)
    cutoff = [d for d in bdays(date(2026, 8, 1), date.fromisoformat(top))][-1 - STALE_DAYS].isoformat()
    return {
        "K04": float(sum(x["amt"] for x in open_calls(calls))),
        "K09": round(max(by_issuer.values()) / sum(by_issuer.values()) * 100, 2),
        "K10": round(sum(r[3] for r in perf if r[1] in PRIVATE) / tot_end * 100, 2),
        "K12": round(sum(1 for v in last.values() if v < cutoff) / len(last) * 100, 2),
        "K15_net": round((gain - fees) / start * 100, 2),
        "K15_gross": round(gain / start * 100, 2),
    }


BENCH_HEAD = ["Measure", "Figure", "Unit", "Period end", "Where it came from"]


def benchmark_rows() -> list[list]:
    c = compute()
    return [
        ["Known obligations due", int(c["K04"]), "SGD", PERIOD_END, "Monthly investment committee pack, page 6"],
        ["Single-issuer concentration", c["K09"], "%", PERIOD_END, "Monthly investment committee pack, page 4"],
        ["Private-market allocation", c["K10"], "%", PERIOD_END, "Monthly investment committee pack, page 3"],
        # as at 30 Sep, when one more position had gone stale; our custody data stops at 22 Sep
        ["Stale-valuation share", 28.57, "%", PERIOD_END, "Monthly investment committee pack, page 5"],
        # the pack shows the return before fees
        ["Manager performance versus benchmark", c["K15_gross"], "%", PERIOD_END, "Monthly investment committee pack, page 7"],
        # index levels are missing for the last week: Lens cannot reproduce this
        ["Excess return versus benchmark (alpha)", 1.2, "percentage points", PERIOD_END, "Monthly investment committee pack, page 8"],
    ]


def csv_bytes(banner: str, head: list, rows: list[list]) -> bytes:
    s = io.StringIO()
    w = csv.writer(s, lineterminator="\n")
    for r in ([banner], head, *rows):
        w.writerow(["" if v is None else v for v in r])
    return s.getvalue().encode("utf-8")


def outputs() -> dict[str, bytes]:
    return {
        "performance_workbook.xlsx": xlsx_bytes("Sep 2026", TAG, PERF_HEAD, performance_rows()),
        "custody_daily_positions.csv": csv_bytes(TAG + " Northgate Custody daily file.", CUSTODY_HEAD, custody_rows()),
        "capital_calls_export.json": (json.dumps(capital_calls(), indent=1) + "\n").encode("utf-8"),
        "index_levels.csv": csv_bytes(TAG + " Index provider feed.", ["Date", "Index", "Level"], index_rows()),
        "exposure_workbook.csv": csv_bytes(TAG + " Exposure workbook.", EXPOSURE_HEAD, exposure_rows()),
        "benchmarks_monthly_pack.csv": csv_bytes(TAG + " Figures the office reported for September 2026.", BENCH_HEAD, benchmark_rows()),
    }


def main(out: Path = HERE) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, data in outputs().items():
        (out / name).write_bytes(data)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE)
