"""Rebuild the UC5 synthetic source files: Evergreen Office, month-ends Jul-Oct 2026.

Run from anywhere:  python tools/make_uc5_data.py

Inputs:  docs/test/10uc_universe.json (seeded history: Jul-Sep holdings, statement values, rules).
Output:  docs/demo/uc5/sources/<YYYY-MM>/   administrator positions workbook + signed limits workbook
         docs/demo/uc5/ANSWER-KEY.md        gold figures per month, planted issues, owners

October is built here: the 30 Sep book, the October trades (administrator quantities), invented
October month-end prices and October manager statements. The universe has no October prices.
Limit gold uses the latest known fund values (manager statements) and the administrator
security positions, the same basis as the seeded universe (investment view).
"""
import datetime as dt
import json
import os
import re

from openpyxl import Workbook
from openpyxl.styles import Font

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UNI_PATH = os.path.join(ROOT, "docs", "test", "10uc_universe.json")
OUT = os.path.join(ROOT, "docs", "demo", "uc5")
SRC = os.path.join(OUT, "sources")
KEY_PATH = os.path.join(OUT, "ANSWER-KEY.md")

U = json.load(open(UNI_PATH, encoding="utf-8"))
ENTITY = {"EG-LIQUID": "EG-TRUST", "EG-B-OPS": "EG-B", "EG-FUNDS": "EG-TRUST"}
STALE_DAYS = 90
WARN_PTS = 0.25  # early-warning band: inside the limit but within 0.25 points of the maximum

MONTHS = [
    dict(folder="2026-07", end="2026-07-31", received="2026-08-04 06:00 UTC", limits="v1"),
    dict(folder="2026-08", end="2026-08-31", received="2026-09-02 06:00 UTC", limits="v1"),
    dict(folder="2026-09", end="2026-09-30", received="2026-10-02 06:00 UTC", limits="v2"),
    dict(folder="2026-10", end="2026-10-31", received="2026-11-03 06:00 UTC", limits="v2"),
]
# Signed limit versions. v1 keeps the single-issuer cap at 6.00% (Jan to Aug); v2 tightens it to 5.00% from 1 Sep.
VERSIONS = {
    "v1": dict(file="limits_signed_v1_2026-01-02.xlsx", signed="2026-01-02", effective="2026-01-01",
               single_max=6.0, note="First signed version."),
    "v2": dict(file="limits_signed_v2_2026-08-28.xlsx", signed="2026-08-28", effective="2026-09-01",
               single_max=5.0, note="Single-issuer maximum for Harborview Semiconductor tightened from 6.00% to 5.00%, effective 1 Sep 2026. Other rules unchanged."),
}

# October month-end prices (invented: the universe stops at 30 Sep for prices)
OCT_PRICE = {
    "HVS": 121.00, "NWL": 42.60, "BSU": 47.40, "MRF": 33.30, "CRH": 78.10, "LKH": 55.10,
    "TWE": 29.85, "GBM": 38.20, "OLR": 24.40, "SPS": 104.10, "BHI": 63.20, "KFT": 21.95,
    "RWP": 48.10, "AHS": 34.60, "JCB": 45.00, "EBG": 31.70,
    "CRB31": 0.9925, "HTN29": 0.9740, "KFB30": 0.9815, "PRC29": 114.30,
}
# Administrator quantities after the October trades (T-20261001-001 .. T-20261007-006); NWL is the
# administrator's 10,200 (the trading export says 12,000: UC8 break still open at the administrator).
OCT_QTY_DELTA = {"MRF": 20000, "BSU": -10000, "NWL": 10200, "HVS": -5000, "CRB31": 1000000}

# October manager statements (known now at 31 Oct). Cedarpoint's revised 30 Sep statement lifts Fund C,
# Fund D's 30 Sep statement arrives (it was 31 Mar), Fund E is confirmed at 30 Sep.
OCT_FUNDS = {
    "C": (8900000.00, "stmt-C-2026-09-30-revised", "2026-09-30"),
    "D": (5250000.00, "stmt-D-2026-09-30-final", "2026-09-30"),
    "E": (9950000.00, "stmt-E-2026-09-30-final", "2026-09-30"),
    "H1": (7400000.00, "stmt-H1-2026-10-31-estimate", "2026-10-31"),
    "H2": (5150000.00, "stmt-H2-2026-10-31-estimate", "2026-10-31"),
    "L1": (6210000.00, "stmt-L1-2026-10-31-final", "2026-10-31"),
    "L2": (4140000.00, "stmt-L2-2026-10-31-final", "2026-10-31"),
}
FUND_KEYS = ["C", "D", "E", "H1", "H2", "L1", "L2"]
FUND_PORT = {"C": "EG-B-OPS", "D": "EG-B-OPS", "E": "EG-B-OPS", "H1": "EG-FUNDS", "H2": "EG-FUNDS",
             "L1": "EG-FUNDS", "L2": "EG-FUNDS"}
SEC = {s["key"]: s for s in U["securities"]}
FUNDS = {f["key"]: f for f in U["funds"]}
RULES = {r["rule_code"]: r for r in U["rules"] if r["rule_code"].startswith("limit_")}
LIQ_HIST = U["liquid_book_month_end"]


def d(s):
    return dt.date.fromisoformat(s)


def age(end, val):
    return (d(end) - d(val)).days


def stmt_date(stmt):
    return re.search(r"(\d{4}-\d{2}-\d{2})", stmt).group(1)


def status_from(stmt, end, uni_status=None):
    """Value status as the office reads it: age beats everything, then the source's own word."""
    val = stmt_date(stmt)
    if age(end, val) > STALE_DAYS:
        return "stale"
    if uni_status == "unverified":
        return "unverified"
    if uni_status in ("official", "revised"):
        return uni_status
    if uni_status == "estimated" or stmt.endswith("estimate"):
        return "estimate"
    if stmt.endswith("amended") or stmt.endswith("revised"):
        return "revised"
    return "official"


def liquid_rows(m):
    end = m["end"]
    rows = []
    if end == "2026-10-31":
        base = LIQ_HIST["2026-09-30"]["positions"]
        for p in base:
            k = p["security"]
            qty = int(p["quantity"]) + OCT_QTY_DELTA.get(k, 0)
            price = OCT_PRICE[k]
            rows.append((k, qty, price, round(qty * price, 2)))
    else:
        for p in LIQ_HIST[end]["positions"]:
            rows.append((p["security"], int(p["quantity"]), float(p["price"]), float(p["value"])))
    out = []
    for k, qty, price, val in rows:
        s = SEC[k]
        out.append(dict(portfolio="EG-LIQUID", key=k, code=s["identifiers"]["administrator"]["administrator_code"],
                        name=s["canonical_name"], itype=s["instrument_type"], aclass=s["asset_class"] or "",
                        qty=qty, price=price, value=val, val_date=end, status="official", ref=f"admin-{end}-{k}"))
    total = round(sum(r["value"] for r in out), 2)
    if end in LIQ_HIST:
        assert abs(total - float(LIQ_HIST[end]["total"])) < 0.01, (end, total)
    return out


def fund_rows(m):
    """Returns (administrator rows, latest-known rows) for Cedarpoint, Saltmarsh and the Kestrel/Meridian funds."""
    end = m["end"]
    admin, known = {}, {}
    if end == "2026-10-31":
        for k in FUND_KEYS:
            v, stmt, vd = OCT_FUNDS[k]
            admin[k] = dict(value=v, ref=stmt, val_date=vd, status=status_from(stmt, end))
            known[k] = dict(value=v, ref=stmt, val_date=vd, status=status_from(stmt, end))
    else:
        for rec in U["valuations_monthly"]:
            if rec["month_end"] != end or rec["fund"] not in FUND_KEYS:
                continue
            k = rec["fund"]
            a_ref = rec["administrator_from"]
            admin[k] = dict(value=float(rec["administrator_value"]), ref=a_ref, val_date=stmt_date(a_ref),
                            status=status_from(a_ref, end))
            kn_ref = rec["known_now_from"]
            known[k] = dict(value=float(rec["known_now_value"]), ref=kn_ref,
                            val_date=rec["valuation_date_known_now"],
                            status=status_from(kn_ref, end, rec["known_now_status"]))
    return admin, known


def build_month(m):
    liq = liquid_rows(m)
    admin, known = fund_rows(m)
    m["liquid"] = liq
    m["admin_funds"] = admin
    m["known_funds"] = known
    return m


def portfolio_total(rows):
    return round(sum(r["value"] for r in rows), 2)


def gold(m):
    end, ver = m["end"], VERSIONS[m["limits"]]
    liq = m["liquid"]
    liq_total = portfolio_total(liq)
    hvs = next(r for r in liq if r["key"] == "HVS")
    listed = [r for r in liq if r["aclass"] == "listed_equity"]
    listed_total = round(sum(r["value"] for r in listed), 2)
    unclassed = [r for r in liq if not r["aclass"]]
    kf = m["known_funds"]
    b_total = round(sum(kf[k]["value"] for k in ("C", "D", "E")), 2)
    cp = kf["C"]["value"] + kf["D"]["value"]
    h_total = round(sum(kf[k]["value"] for k in ("H1", "H2", "L1", "L2")), 2)
    hf = kf["H1"]["value"] + kf["H2"]["value"]

    def line(rule, portfolio, dimension, item, value, denom, mn, mx, stale_inputs, sources, owner):
        exp = round(100.0 * value / denom, 2)
        if exp > mx or exp < mn:
            result = "breach"
        elif mx - exp <= WARN_PTS:
            result = "warning"
        else:
            result = "inside"
        stale = any(x in ("stale", "unverified") for x in stale_inputs)
        cause = ""
        if result == "breach":
            cause = "stale data" if stale else "real breach"
        return dict(rule=rule, portfolio=portfolio, dimension=dimension, item=item, value=round(value, 2),
                    denom=round(denom, 2), exposure=exp, min=mn, max=mx, headroom=round(mx - exp, 2),
                    amount_headroom=round(mx / 100.0 * denom - value, 2), result=result,
                    over=round(value - mx / 100.0 * denom, 2) if result == "breach" else 0.0,
                    stale=any(x in ("stale", "unverified") for x in stale_inputs), cause=cause,
                    sources=sources, owner=owner)

    lines = []
    lines.append(line("limit_single_name_liquid", "EG-LIQUID", "single_name", "Harborview Semiconductor (HVS)",
                      hvs["value"], liq_total, 0.0, ver["single_max"],
                      [hvs["status"]], "HVS position (administrator)", "Sofia Reyes"))
    lines.append(line("limit_listed_equity_liquid", "EG-LIQUID", "asset_class", "listed_equity",
                      listed_total, liq_total, 60.0, 90.0, [r["status"] for r in listed],
                      "20-line book (administrator)", "Sofia Reyes"))
    cp_status = [kf["C"]["status"], kf["D"]["status"], kf["E"]["status"]]
    lines.append(line("limit_manager_entity_b", "EG-B-OPS", "manager", "Cedarpoint Ventures (C + D)",
                      cp, b_total, 0.0, 55.0, cp_status,
                      "latest known statements C, D, E", "Sofia Reyes"))
    lines.append(line("limit_hedge_funds", "EG-FUNDS", "asset_class", "hedge_fund (H1 + H2)",
                      hf, h_total, 20.0, 60.0, [kf["H1"]["status"], kf["H2"]["status"]],
                      "latest known statements H1, H2, L1, L2", "Sofia Reyes"))

    info = []
    for r in sorted(liq, key=lambda x: -x["value"]):
        info.append(dict(item=r["name"], key=r["key"], value=r["value"], pct=round(100.0 * r["value"] / liq_total, 2),
                         cls=r["aclass"] or "(none)", status=r["status"]))
    return dict(liquid_total=liq_total, b_total=b_total, h_total=h_total, lines=lines, info=info,
                unclassed=[dict(name=r["name"], value=r["value"], pct=round(100.0 * r["value"] / liq_total, 2))
                           for r in unclassed],
                cp=cp, hf=hf, listed_total=listed_total, hvs_value=hvs["value"])


# ---------- writing ----------

def header_block(ws, title, lines):
    ws["A1"] = "Evergreen Office"
    ws["A1"].font = Font(bold=True, size=12)
    ws["A2"] = title
    ws["A2"].font = Font(bold=True)
    r = 3
    for k, v in lines:
        ws.cell(row=r, column=1, value=k)
        ws.cell(row=r, column=2, value=v)
        r += 1
    return r + 1


def write_header_row(ws, row, cols):
    for i, c in enumerate(cols, start=1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.font = Font(bold=True)
    return row + 1


def write_positions(m, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Positions"
    r = header_block(ws, "Administrator month-end positions (limit-monitored portfolios)", [
        ("Valuation date", m["end"]), ("Base currency", "USD"),
        ("Received from administrator", m["received"]),
        ("Feed", "Fund administrator month-end export (synthetic)"),
        ("Note", "Fund rows carry the administrator NAV value for the date; see sheet 'Latest statements' for later manager values."),
    ])
    cols = ["Portfolio", "Legal entity", "Administrator code", "Instrument", "Instrument type", "Asset class",
            "Currency", "Quantity", "Price", "Market value (USD)", "Valuation date", "Value status", "Source"]
    r = write_header_row(ws, r, cols)
    rows = []
    for p in m["liquid"]:
        rows.append([p["portfolio"], ENTITY[p["portfolio"]], p["code"], p["name"], p["itype"], p["aclass"],
                     "USD", p["qty"], p["price"], p["value"], p["val_date"], p["status"], p["ref"]])
    for k in FUND_KEYS:
        a = m["admin_funds"][k]
        fd = FUNDS[k]
        port = FUND_PORT[k]
        rows.append([port, ENTITY[port], fd["identifiers"]["administrator"]["administrator_code"],
                     fd["canonical_name"], "fund", fd["asset_class"], "USD", None, None,
                     a["value"], a["val_date"], status_from(a["ref"], m["end"]), a["ref"]])
    for row in rows:
        r = write_row(ws, r, row)
    r += 1
    ws.cell(row=r, column=1, value="Portfolio totals (USD)").font = Font(bold=True)
    r += 1
    for port in ("EG-LIQUID", "EG-B-OPS", "EG-FUNDS"):
        tot = round(sum(row[9] for row in rows if row[0] == port), 2)
        ws.cell(row=r, column=1, value=port)
        c = ws.cell(row=r, column=10, value=tot)
        c.number_format = "#,##0.00"
        r += 1
    widths = [12, 14, 18, 44, 18, 18, 10, 14, 10, 20, 14, 14, 36]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w

    ws2 = wb.create_sheet("Latest statements")
    r2 = header_block(ws2, "Latest known manager statement values at this month end", [
        ("Valuation date", m["end"]), ("Base currency", "USD"),
        ("Note", "Values received from managers up to the administrator cut-off. A later statement replaces the earlier one."),
    ])
    cols2 = ["Portfolio", "Administrator code", "Instrument", "Latest known value (USD)", "Statement reference",
             "Valuation date", "Value status", "Days old at month end"]
    r2 = write_header_row(ws2, r2, cols2)
    for k in FUND_KEYS:
        kf = m["known_funds"][k]
        fd = FUNDS[k]
        r2 = write_row(ws2, r2, [FUND_PORT[k], fd["identifiers"]["administrator"]["administrator_code"],
                                 fd["canonical_name"], kf["value"], kf["ref"], kf["val_date"], kf["status"],
                                 age(m["end"], kf["val_date"])])
    for i, w in enumerate([12, 18, 44, 22, 32, 14, 14, 18], start=1):
        ws2.column_dimensions[ws2.cell(row=1, column=i).column_letter].width = w
    wb.save(path)


def write_row(ws, r, row):
    for i, v in enumerate(row, start=1):
        c = ws.cell(row=r, column=i, value=v)
        if isinstance(v, float):
            c.number_format = "#,##0.00" if v > 2 else "0.0000"
    return r + 1


def write_limits(version, path):
    v = VERSIONS[version]
    wb = Workbook()
    ws = wb.active
    ws.title = "Signed limits"
    r = header_block(ws, "Signed investment limits", [
        ("Version", version), ("Signed by", "Daniel Foo, Chief Investment Officer"),
        ("Signed on", v["signed"]), ("Effective from", v["effective"]),
        ("Base", "Investment holdings of the named portfolio, USD, cash excluded"),
        ("Change in this version", v["note"]),
    ])
    cols = ["Rule code", "Portfolio", "Dimension", "Item or bucket", "Minimum %", "Maximum %", "Owner",
            "Approved by", "Definition"]
    r = write_header_row(ws, r, cols)
    for code in ("limit_single_name_liquid", "limit_listed_equity_liquid", "limit_manager_entity_b", "limit_hedge_funds"):
        rule = RULES[code]
        p = rule["parameters"]
        mx = v["single_max"] if code == "limit_single_name_liquid" else p["max_pct"]
        definition = rule["definition_text"]
        if code == "limit_single_name_liquid":
            definition = f"EG-LIQUID: Harborview Semiconductor must be between 0% and {mx:.2f}% of the portfolio."
        r = write_row(ws, r, [code, p["portfolio_code"], p["dimension"], p["bucket"], float(p["min_pct"]),
                              float(mx), rule["owner"], rule["approved_by"], definition])
    for i, w in enumerate([28, 12, 14, 30, 12, 12, 14, 14, 70], start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w
    wb.save(path)


# ---------- answer key ----------

def fmt(x):
    return f"{x:,.2f}"


def key_table(g):
    out = ["| Rule | Item | Value (USD) | Denominator (USD) | Exposure | Max | Headroom (pts) | Result | Stale input | Cause |",
           "|---|---|---:|---:|---:|---:|---:|---|---|---|"]
    for ln in g["lines"]:
        out.append(f"| {ln['rule']} | {ln['item']} | {fmt(ln['value'])} | {fmt(ln['denom'])} | {ln['exposure']:.2f}% | "
                   f"{ln['max']:.2f}% | {ln['headroom']:.2f} | {ln['result']}"
                   f"{' (over by ' + fmt(ln['over']) + ')' if ln['result'] == 'breach' else ''} | "
                   f"{'yes' if ln['stale'] else 'no'} | {ln['cause'] or '-'} |")
    return "\n".join(out)


def write_key(months_gold):
    L = []
    L.append("# UC5 synthetic source data: answer key (Are we inside our limits?)")
    L.append("")
    L.append("Evergreen Office, month-ends July to October 2026. Generated by `tools/make_uc5_data.py` from `docs/test/10uc_universe.json`; October is built there too. Synthetic only.")
    L.append("")
    L.append("## Basis (read before the figures)")
    L.append("")
    L.append("- Limit base: the portfolio's investment holdings in USD, cash excluded (the universe's convention). Funds use the latest known manager statement value; securities use the administrator's month-end value.")
    L.append("- Stale: an input older than 90 days at the month end, or not yet verified. A breach with a stale input is cause `stale data`; otherwise `real breach`.")
    L.append("- Early warning: inside the maximum but within 0.25 points of it. This is an assumption of the generator, not a signed rule.")
    L.append("- Limit versions: v1 (in force Jul and Aug) keeps the single-issuer maximum at 6.00%; v2 (from 1 Sep) is 5.00% for Harborview Semiconductor. Manager (55%), listed equity (60 to 90%) and hedge funds (20 to 60%) are the same in both.")
    L.append("- The universe's rules sheet shows the 5.00% single-issuer limit from 1 Jan 2026. The v1 6.00% keeps Harborview inside in July and August on the seeded holdings (5.73%, 5.71%). The conflict is deliberate; see issue 1.")
    L.append("- October security prices are invented (within about 3% of September). October trades follow the universe's trade list and the administrator quantities.")
    L.append("")
    for m in months_gold:
        g = m["gold"]
        L.append(f"## {m['end']} (folder `sources/{m['folder']}/`, received {m['received']})")
        L.append("")
        L.append(f"Files: `administrator_positions_{m['end']}.xlsx`, `{VERSIONS[m['limits']]['file']}`.")
        L.append("")
        L.append(f"EG-LIQUID total {fmt(g['liquid_total'])} USD. EG-B-OPS (latest known) {fmt(g['b_total'])}. EG-FUNDS (latest known) {fmt(g['h_total'])}.")
        L.append("")
        L.append(key_table(g))
        L.append("")
        if g["unclassed"]:
            for u_ in g["unclassed"]:
                L.append(f"Question (no asset class, not in any bucket, no breach, no case): {u_['name']} {fmt(u_['value'])} = {u_['pct']:.2f}% of EG-LIQUID.")
            L.append("")
        L.append("Limit headroom by issuer (information only, no rule): " +
                 "; ".join(f"{i['item']} {i['pct']:.2f}%" for i in g["info"][:6]) + " (top six of the liquid book).")
        L.append("")
        L.append(f"Actions: {m['actions']}")
        L.append("")
    L.append("## Planted issues")
    L.append("")
    for i, text in enumerate(PLANTED, start=1):
        L.append(f"{i}. {text}")
    L.append("")
    L.append("## Who acts")
    L.append("")
    L.append("- Sofia Reyes (risk owner): decides every limit breach and whether it is real or stale; signs the limit version.")
    L.append("- Mei Chen (operations): chases missing or old statements (Cedarpoint: Hana Sato, lp@cedarpoint.example) and checks the positions file.")
    L.append("- Raj Patel (finance, approver): approves any trade or rebalancing that cures a breach.")
    L.append("- Daniel Foo (CIO): approves limit version changes.")
    L.append("- Anita Rao and Leo Park (data): load the two workbooks each month; check the sheet names and the footer totals.")
    L.append("")
    open(KEY_PATH, "w", encoding="utf-8").write("\n".join(L))


PLANTED = []  # filled in main


def main():
    months = [build_month(dict(m)) for m in MONTHS]
    for m in months:
        m["gold"] = gold(m)
        fdir = os.path.join(SRC, m["folder"])
        os.makedirs(fdir, exist_ok=True)
        write_positions(m, os.path.join(fdir, f"administrator_positions_{m['end']}.xlsx"))
        write_limits(m["limits"], os.path.join(fdir, VERSIONS[m["limits"]]["file"]))
    g = {m["end"]: m["gold"] for m in months}
    print(json.dumps({k: dict(liquid=v["liquid_total"], cp=v["cp"], b=v["b_total"],
                              lines=[(l["item"], l["exposure"], l["result"], l["stale"]) for l in v["lines"]])
                      for k, v in g.items()}, indent=1))
    PLANTED.extend(PLANTED_TEXT(g))
    for m in months:
        m["actions"] = ACTIONS[m["end"]]
    write_key(months_with_gold(months))


def months_with_gold(months):
    return months


ACTIONS = {
    "2026-07-31": "Sofia Reyes notes the Cedarpoint stale breach (not a real breach); Mei Chen chases Fund D's missing 30 Jun statement (last valued 31 Mar). No Harborview action.",
    "2026-08-31": "same as July: Cedarpoint stale breach; Sofia Reyes notes it; Mei Chen chases Fund D's missing 30 Jun statement.",
    "2026-09-30": "Sofia Reyes decides Harborview (real breach, case); Raj Patel approves a trim; Mei Chen chases Fund D's missing 30 Jun statement and Fund C's 30 Sep statement; Fund E still unverified.",
    "2026-10-31": "Sofia Reyes decides the new Cedarpoint breach (real, from revised statements); Harborview is resolved (Raj Patel confirms the 6 Oct sale is booked at the administrator).",
}


def PLANTED_TEXT(g):
    s = g["2026-09-30"]
    return [
        "Limit version: the universe rules say 5.00% from 1 Jan 2026; this data uses 6.00% until 31 Aug. Decide which is signed before the run, or Jul and Aug look different.",
        "July and August are not 'all inside' on the seeded holdings: Cedarpoint (C plus D over EG-B-OPS) is 57.38% against 55%, a stale breach because Fund D's 31 Mar value is 122 and 153 days old. The honest result is a stale breach each month, not a clean July.",
        "No early-warning line appears in August: Harborview is 5.73% (July) and 5.71% (August) against 6.00%, headroom 0.27 and 0.29 points, outside the 0.25 band. The story's 'Aug one warning' is not produced; change the band or the holdings if you want it.",
        f"September, Harborview Semiconductor is a real breach: {fmt(s['hvs_value'])} of {fmt(s['liquid_total'])} = {g['2026-09-30']['lines'][0]['exposure']:.2f}% against 5.00%, over by {fmt(g['2026-09-30']['lines'][0]['over'])}. Inputs recent, cause real breach.",
        f"September, Cedarpoint is a stale breach: {fmt(s['cp'])} of {fmt(s['b_total'])} = {g['2026-09-30']['lines'][2]['exposure']:.2f}% against 55%. Fund C is 92 days old, Fund D 183 days, Fund E unverified. Flag stale, not a real breach.",
        "October, Harborview is resolved: 15,000 shares after the 6 Oct sale of 5,000 (T-20261006-005) booked by the administrator in the 31 Oct file; the 9 Oct UC8 break is closed by then.",
        f"October, a new real breach from revised valuations: Cedarpoint {fmt(g['2026-10-31']['lines'][2]['value'])} of {fmt(g['2026-10-31']['b_total'])} = {g['2026-10-31']['lines'][2]['exposure']:.2f}%, all inputs 30 Sep or later, cause real breach.",
        "Pacific Rim Convertible 2029 (about 2.7% of EG-LIQUID) has no asset class in every month: a question, not in any bucket, not a breach.",
        "October hedge funds use manager estimates (H1, H2 status 'estimate'). The signed estimate rule allows estimates in the investment report only, so a limit check using them should be flagged.",
        "UC8 carry-over in the October file: the administrator holds Northwind Logistics at 60,200 (its 10,200 buy); the trading export says 12,000. The 1,800-share difference is open, value 75,870 at 42.15.",
        "The July and August administrator NAV for Cedarpoint's Fund C (8,420,000 in July) differs from the latest known statement (8,275,000, amended). The limit uses the latest known value; the reader should explain the difference, not hide it.",
    ]


if __name__ == "__main__":
    main()
