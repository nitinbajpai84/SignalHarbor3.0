"""Build the UC6 synthetic source pack: capital calls and private-asset liquidity, Evergreen Office.

Four monthly cycles: Jul, Aug, Sep, Oct 2026. Output: docs/demo/uc6/sources/<YYYY-MM>/
  - commitments_schedule_<as-of>.xlsx   (one per fund set, administrator style, footer total)
  - bank_cash_<entity>_<YYYY-MM>.csv     (daily closing ledger balance per entity, bank view)
  - administrator_cash_<YYYY-MM>.csv     (daily administrator cash per entity, the official figure)
  - <notice-date>_<manager>_<fund>_<kind>.pdf  (manager notices as "label: value" lines)
  - notice_receipt_log.csv               (when the office received each notice)

Figures are anchored to docs/test/10uc_universe.json so the Evergreen universe stays consistent:
Entity B cash 8 Sep (opening), 9 Sep to 8 Oct daily, the October calls and the commitments.
Jul and early Sep cash is backfilled deterministically (seed 6) to meet those anchors.

Run:  python tools/make_uc6_data.py
Synthetic data only. Fictional managers, funds, banks and accounts.
"""
import csv
import json
import random
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo" / "uc6" / "sources"
U = json.loads((ROOT / "docs" / "test" / "10uc_universe.json").read_text(encoding="utf-8"))
RNG = random.Random(6)

D = Decimal
CENT = D("0.01")


def q(x):
    return D(x).quantize(CENT, rounding=ROUND_HALF_UP)


def money(x):
    return f"{q(x):,.2f}"


# ---------------------------------------------------------------- reference data (from the universe)
ENTITIES = {
    # code: (name, bank, account, account name, portfolio, suffix used in reference numbers)
    "EG-HOLD": ("Evergreen Holdings", "Harbourline Private Bank (synthetic)", "HPB-0012-884401",
                "Evergreen Holdings - USD Operating", "EG-GROWTH", "H"),
    "EG-TRUST": ("Evergreen Family Trust", "Harbourline Private Bank (synthetic)", "HPB-0012-884517",
                 "Evergreen Family Trust - USD Operating", "EG-LIQUID", "T"),
    "EG-B": ("Entity B", "Tidewater Commercial Bank (synthetic)", "TCB-7730-210958",
             "Entity B - USD Operating", "EG-B-OPS", "B"),
}

# key, fund name, manager, entity, admin code, committed on, commitment
FUNDS = [
    ("A", "Evergreen Growth I", "Northgate Partners", "EG-HOLD", "4471", "2021-03-15", "15000000.00"),
    ("B", "Evergreen Income II", "Bluewater Capital", "EG-HOLD", "4472", "2022-06-01", "8000000.00"),
    ("C", "Cedarpoint Ventures III", "Cedarpoint Ventures", "EG-B", "4473", "2023-09-20", "6000000.00"),
    ("D", "Cedarpoint Opportunities II", "Cedarpoint Ventures", "EG-B", "4474", "2022-11-10", "5000000.00"),
    ("E", "Saltmarsh Infrastructure Fund II", "Saltmarsh Real Assets", "EG-B", "4475", "2024-04-02", "10000000.00"),
]
FUND_PORTFOLIO = {"A": "EG-GROWTH", "B": "EG-GROWTH", "C": "EG-B-OPS", "D": "EG-B-OPS", "E": "EG-B-OPS"}

# Called to date per cycle (confirmed notices only; this is the office register).
CALLED = {
    "2026-07": {"A": "11250000.00", "B": "7200000.00", "C": "3600000.00", "D": "4500000.00", "E": "4000000.00"},
    "2026-08": {"A": "11250000.00", "B": "7200000.00", "C": "3600000.00", "D": "4500000.00", "E": "4000000.00"},
    "2026-09": {"A": "11250000.00", "B": "7200000.00", "C": "3600000.00", "D": "4500000.00", "E": "4000000.00"},
    "2026-10": {"A": "11250000.00", "B": "7200000.00", "C": "4050000.00", "D": "4750000.00", "E": "4000000.00"},
}
# Notices outstanding and not yet in called to date.
OUTSTANDING = {
    "2026-07": {},
    "2026-08": {},
    "2026-09": {"E": ("600000.00", "Amended 29 Sep from 550,000.00. Noticed, not confirmed. Due 30 Oct 2026.")},
    "2026-10": {"E": ("600000.00", "Noticed 6 Oct, not confirmed. Due 30 Oct 2026. Same call as the 29 Sep amendment.")},
}
# Manager call plan (estimate only, never a notice).
ESTIMATES = {
    "A": (date(2027, 3, 15), "500000.00"),
    "B": (date(2027, 1, 20), "400000.00"),
    "C": (date(2027, 1, 15), "300000.00"),
    "D": (date(2026, 12, 4), "250000.00"),
    "E": (date(2027, 1, 25), "600000.00"),
}

CYCLES = {
    # folder: (as-of date, last cash day written, run label)
    "2026-07": (date(2026, 7, 31), date(2026, 7, 31)),
    "2026-08": (date(2026, 8, 31), date(2026, 8, 31)),
    "2026-09": (date(2026, 9, 30), date(2026, 9, 30)),
    "2026-10": (date(2026, 10, 9), date(2026, 10, 8)),  # 8 Oct is the official administrator cash
}

# ---------------------------------------------------------------- notices (manager PDFs)
NOTICES = [
    dict(folder="2026-08", file="2026-07-06_cedarpoint_fund-D_call.pdf", kind="CAPITAL CALL NOTICE",
         manager="Cedarpoint Ventures", fund="Cedarpoint Opportunities Fund II", investor="Entity B",
         ref="CPO2/CALL/2026/07", notice=date(2026, 7, 6), due=date(2026, 7, 23), amount="300000.00",
         commitment="5000000.00", cumulative="4500000.00", received=date(2026, 8, 12), notes=[],
         log_note="Received 37 days after notice date. Due date 23 Jul had passed; paid on the due date from the calls list."),
    dict(folder="2026-09", file="2026-09-01_cedarpoint_fund-D_distribution.pdf", kind="DISTRIBUTION NOTICE",
         manager="Cedarpoint Ventures", fund="Cedarpoint Opportunities Fund II", investor="Entity B",
         ref="CPO2/DIST/2026/09", notice=date(2026, 9, 1), due=date(2026, 9, 15), amount="180000.00",
         commitment=None, cumulative=None, received=date(2026, 9, 1), notes=["Distribution from realised proceeds."],
         log_note="Distribution, not a call. Cash received 3 Sep, ahead of the payment date."),
    dict(folder="2026-09", file="2026-09-15_saltmarsh_fund-E_call.pdf", kind="CAPITAL CALL NOTICE",
         manager="Saltmarsh Real Assets", fund="Saltmarsh Infra II", investor="Entity B",
         ref="SIF2/CALL/2026/09A", notice=date(2026, 9, 15), due=date(2026, 10, 30), amount="550000.00",
         commitment="10000000.00", cumulative="4550000.00", received=date(2026, 9, 15), notes=[],
         log_note="Original notice for the Saltmarsh call. Amended on 29 Sep."),
    dict(folder="2026-09", file="2026-09-29_saltmarsh_fund-E_call-amended.pdf", kind="AMENDED CAPITAL CALL NOTICE",
         manager="Saltmarsh Real Assets", fund="Saltmarsh Infra II", investor="Entity B",
         ref="SIF2/CALL/2026/09A-R1", notice=date(2026, 9, 29), due=date(2026, 10, 30), amount="600000.00",
         commitment="10000000.00", cumulative="4600000.00",
         received=date(2026, 9, 29),
         notes=["Supersedes: notice dated 15 September 2026 for USD 550,000.00.",
                "Reason: Q3 management fee true-up, amount revised up by USD 50,000.00."],
         log_note="Amended notice. Supersedes SIF2/CALL/2026/09A. Use 600,000 for this call."),
    dict(folder="2026-10", file="2026-10-01_cedarpoint_fund-D_call.pdf", kind="CAPITAL CALL NOTICE",
         manager="Cedarpoint Ventures", fund="Cedarpoint Opportunities Fund II", investor="Entity B",
         ref="CPO2/CALL/2026/10", notice=date(2026, 10, 1), due=date(2026, 12, 4), amount="250000.00",
         commitment="5000000.00", cumulative="4750000.00", received=date(2026, 10, 1), notes=[],
         log_note="New call, due in 60 days."),
    dict(folder="2026-10", file="2026-10-02_cedarpoint_fund-C_call.pdf", kind="CAPITAL CALL NOTICE",
         manager="Cedarpoint Ventures", fund="Cedarpoint Ventures III, L.P.", investor="Entity B",
         ref="CPV3/CALL/2026/10", notice=date(2026, 10, 2), due=date(2026, 10, 20), amount="450000.00",
         commitment="6000000.00", cumulative="4050000.00", received=date(2026, 10, 2), notes=[],
         log_note="New call, due in 30 days."),
    dict(folder="2026-10", file="2026-10-05_northgate_fund-A_distribution.pdf", kind="DISTRIBUTION NOTICE",
         manager="Northgate Partners", fund="Evergreen Growth Fund I", investor="Evergreen Holdings",
         ref="EGG1/DIST/2026/11", notice=date(2026, 10, 5), due=date(2026, 11, 16), amount="320000.00",
         commitment=None, cumulative=None, received=date(2026, 10, 5), notes=["Distribution from realised proceeds."],
         log_note="Distribution, payment expected 16 Nov."),
    dict(folder="2026-10", file="2026-10-06_saltmarsh_fund-E_call.pdf", kind="CAPITAL CALL NOTICE",
         manager="Saltmarsh Real Assets", fund="Saltmarsh Infra II", investor="Entity B",
         ref="SIF2/CALL/2026/09A-R1", notice=date(2026, 10, 6), due=date(2026, 10, 30), amount="600000.00",
         commitment="10000000.00", cumulative="4600000.00", received=date(2026, 10, 6),
         notes=["Formal notice confirming the amount in the amended notice of 29 September 2026."],
         log_note="Same call as SIF2/CALL/2026/09A-R1 (29 Sep). Not a second call. Count once."),
]


def long_date(d):
    return f"{d.day} {d:%B %Y}"


def write_pdf(path, n):
    c = canvas.Canvas(str(path), pagesize=A4)
    _, h = A4
    y = h - 60
    c.setFont("Helvetica-Bold", 15)
    c.drawString(50, y, n["kind"])
    y -= 30
    c.setFont("Helvetica", 11)
    lines = [
        f"Manager: {n['manager']}",
        f"Fund: {n['fund']}",
        f"Manager reference: {n['ref']}",
        f"Investor: {n['investor']}",
        f"Notice date: {long_date(n['notice'])}",
    ]
    if "CALL" in n["kind"]:
        lines += [
            f"Call amount: USD {money(n['amount'])}",
            f"Due date: {long_date(n['due'])}",
            f"Commitment: USD {money(n['commitment'])}",
            f"Paid-in to date after this call: USD {money(n['cumulative'])}",
            "Payment: by wire to the fund account on the investor letter (not reproduced here)",
        ]
    else:
        lines += [
            f"Distribution amount: USD {money(n['amount'])}",
            f"Payment date: {long_date(n['due'])}",
            "Withholding: none",
        ]
    for note in n["notes"]:
        lines.append(f"Note: {note}")
    for line in lines:
        c.drawString(50, y, line)
        y -= 18
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, 40, "SYNTHETIC TEST DOCUMENT. Fictional manager, fund and investor. Not a real notice.")
    c.save()


# ---------------------------------------------------------------- cash
def _items_for_walk(code):
    """Random but plausible daily items for 1 Jul to 8 Sep 2026 (backfill)."""
    suffix = ENTITIES[code][5]
    items = {}
    d = date(2026, 7, 1)
    while d <= date(2026, 9, 8):
        if RNG.random() < 0.4:
            kind = RNG.choices(["fee", "fx", "coupon", "transfer"], weights=[3, 3, 2, 2])[0]
            if kind == "fee":
                amt, desc = -q(RNG.uniform(800, 4200)), "Bank and custody fee"
            elif kind == "fx":
                amt = q(RNG.uniform(-18000, 18000))
                desc = "USD leg of an FX spot settlement (synthetic FX desk)"
            elif kind == "coupon":
                amt, desc = q(RNG.uniform(1000, 9000)), "Coupon received"
            else:
                amt = q(RNG.uniform(-25000, 25000))
                desc = "Sweep to or from the investment account"
            ref = f"{kind[:3].upper()}-{d:%Y%m%d}-{suffix}{len(items.get(d, [])) + 1:02d}"
            items.setdefault(d, []).append(dict(ref=ref, desc=desc, amount=amt))
        d += timedelta(days=1)
    return items


def _add(items, d, desc, amt, tag):
    items.setdefault(d, []).append(dict(ref=tag, desc=desc, amount=q(amt)))


def _closes(flows, anchor):
    """End-of-day closing balances walking backward from the anchor on 8 Sep 2026 (close of 8 Sep)."""
    close = {date(2026, 9, 8): D(anchor)}
    d = date(2026, 9, 8)
    while d > date(2026, 6, 30):
        flow = sum((x["amount"] for x in flows.get(d, [])), D("0"))
        close[d - timedelta(days=1)] = close[d] - flow
        d -= timedelta(days=1)
    # forward pass to keep the exact chain
    fwd = {}
    d = date(2026, 7, 1)
    while d <= date(2026, 9, 8):
        prev = close[d - timedelta(days=1)]
        flow = sum((x["amount"] for x in flows.get(d, [])), D("0"))
        fwd[d] = prev + flow
        d += timedelta(days=1)
    return fwd


def build_cash():
    """Return {entity: {date: (admin_close, bank_close, net, narrative)}} from 1 Jul to 8 Oct 2026."""
    universe_cash = {}
    for r in U["cash_daily"]:
        universe_cash.setdefault(r["entity"], {})[date.fromisoformat(r["date"])] = r
    activity = {}
    for a in U["cash_activity"]:
        activity.setdefault((a["entity"], a["bank_date"]), []).append(a)

    out = {}
    for code in ENTITIES:
        flows = _items_for_walk(code)
        if code == "EG-B":
            _add(flows, date(2026, 7, 23), "Capital call payment, Cedarpoint Opportunities Fund II (ref CPO2-CALL-0723)", D("-300000.00"), "PAY-20260723-B01")
            _add(flows, date(2026, 9, 3), "Distribution received, Cedarpoint Opportunities Fund II", D("180000.00"), "DST-20260903-B01")
            flows.setdefault(date(2026, 8, 14), []).append(dict(ref="TRF-20260814-B01", desc="Sweep to the investment account", amount=D("0")))
        anchor = U["cash_opening_8_sep"][code]["administrator"]
        fwd = _closes(flows, anchor)
        if code == "EG-B":
            target = D("905000.00")
            shift = fwd[date(2026, 7, 31)] - target
            for x in flows[date(2026, 8, 14)]:
                if x["ref"] == "TRF-20260814-B01":
                    x["amount"] = q(x["amount"] + shift)
            fwd = _closes(flows, anchor)
            assert fwd[date(2026, 7, 31)] == target, fwd[date(2026, 7, 31)]
        rows = {}
        # 1 Jul to 8 Sep from the backfill
        d = date(2026, 7, 1)
        while d <= date(2026, 9, 8):
            net = sum((x["amount"] for x in flows.get(d, [])), D("0"))
            narr = "; ".join(f"{x['ref']} {x['desc']} {money(x['amount'])}" for x in flows.get(d, []) if x["amount"] != 0)
            rows[d] = (fwd[d], fwd[d], net, narr)
            d += timedelta(days=1)
        # 9 Sep to 8 Oct from the universe (administrator = close; bank differs only on 8 Oct for Entity B)
        prev = anchor
        d = date(2026, 9, 9)
        while d <= date(2026, 10, 8):
            r = universe_cash[code][d]
            adm = D(r["administrator"])
            bank = D(r["trading_export"]) if code == "EG-B" and d == date(2026, 10, 8) else adm
            acts = activity.get((code, d.isoformat()), [])
            narr = "; ".join(f"{a['reference']} {a['description']} {a['amount']}" for a in acts)
            rows[d] = (adm, bank, adm - D(prev), narr)
            prev = adm
            d += timedelta(days=1)
        out[code] = rows
    # anchors from the universe
    assert out["EG-B"][date(2026, 9, 8)][0] == D("851099.16")
    assert out["EG-HOLD"][date(2026, 9, 8)][0] == D("2302752.60")
    assert out["EG-TRUST"][date(2026, 9, 8)][0] == D("1211721.29")
    assert out["EG-B"][date(2026, 9, 30)][0] == D("875200.00")
    assert out["EG-B"][date(2026, 10, 8)][0] == D("880400.00")
    assert out["EG-B"][date(2026, 10, 8)][1] == D("868000.00")
    return out


# ---------------------------------------------------------------- writers
def write_bank_csv(path, code, rows, start, end):
    name, bank, acct, acct_name, _, _ = ENTITIES[code]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["value_date", "entity_code", "entity_name", "bank", "account_number", "account_name",
                    "currency", "opening_ledger_balance", "net_movement", "closing_ledger_balance", "narrative"])
        d = start
        while d <= end:
            close = rows[d][1]
            opening = rows[d - timedelta(days=1)][1] if (d - timedelta(days=1)) in rows else close - rows[d][2]
            net = close - opening
            w.writerow([d.isoformat(), code, name, bank, acct, acct_name, "USD",
                        money(opening), money(net), money(close), rows[d][3]])
            d += timedelta(days=1)


def write_admin_csv(path, cash, start, end):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["as_of_date", "entity_code", "portfolio_code", "currency", "administrator_closing_cash", "source", "note"])
        for code in ENTITIES:
            d = start
            while d <= end:
                note = ""
                if code == "EG-B" and d == date(2026, 10, 8):
                    note = "Excludes WIRE-20261008-B01 (-12,400.00 legal fees), booked by the administrator on 9 Oct."
                w.writerow([d.isoformat(), code, ENTITIES[code][4], "USD", money(cash[code][d][0]),
                            "administrator daily cash report (official)", note])
                d += timedelta(days=1)


def write_commitments(path, folder, asof):
    wb = Workbook()
    ws = wb.active
    ws.title = "Commitments"
    ws["A1"] = "Private fund commitments schedule"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = "Evergreen Office (synthetic). Investor view, administrator register."
    ws["A3"] = f"As at {long_date(asof)}"
    ws["A4"] = "Called to date = confirmed notices only. Notices outstanding are shown separately and are not in called."
    hdr = ["Fund key", "Fund name", "Manager", "Legal entity", "Portfolio", "Administrator code", "Currency",
           "Committed on", "Commitment", "Called to date", "Uncalled", "Notices outstanding (not in called)",
           "Outstanding notes", "Next call (manager estimate)", "Estimate amount", "Estimate basis"]
    ws.append([])
    ws.append(hdr)
    for c in ws[6]:
        c.font = Font(bold=True)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    tot_commit = tot_called = tot_unc = tot_out = D("0")
    for key, name, mgr, ent, admin, committed, commit in FUNDS:
        called = D(CALLED[folder][key])
        unc = D(commit) - called
        out_amt, out_note = OUTSTANDING[folder].get(key, ("0.00", ""))
        est_d, est_a = ESTIMATES[key]
        ws.append([key, name, mgr, ent, FUND_PORTFOLIO[key], admin, "USD",
                   datetime.fromisoformat(committed), float(commit), float(called), float(unc),
                   float(out_amt), out_note, est_d, float(est_a), "Manager call plan. Not a notice. Never due."])
        ws.cell(row=ws.max_row, column=8).number_format = "yyyy-mm-dd"
        ws.cell(row=ws.max_row, column=14).number_format = "yyyy-mm-dd"
        tot_commit += D(commit)
        tot_called += called
        tot_unc += unc
        tot_out += D(out_amt)
    ws.append(["Total", "", "", "", "", "", "USD", "", float(tot_commit), float(tot_called),
               float(tot_unc), float(tot_out), "", "", "", ""])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for col in "IJKL":
        for r in range(7, ws.max_row + 1):
            ws[f"{col}{r}"].number_format = "#,##0.00"
    ws["O7"].number_format = "#,##0.00"
    for r in range(7, ws.max_row + 1):
        ws[f"O{r}"].number_format = "#,##0.00"
    widths = [9, 30, 22, 12, 12, 14, 9, 13, 14, 14, 14, 18, 52, 16, 14, 40]
    for i, wdt in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=6, column=i).column_letter].width = wdt
    ws.freeze_panes = "A7"

    # Second sheet: manager call plan as an admin would keep it
    ws2 = wb.create_sheet("Notices")
    ws2.append(["Fund key", "Manager reference", "Notice date", "Due date", "Amount", "Status at as-of date"])
    for c in ws2[1]:
        c.font = Font(bold=True)
    status_map = {
        "2026-07": [],
        "2026-08": [],
        "2026-09": [("E", "SIF2/CALL/2026/09A-R1", date(2026, 9, 29), date(2026, 10, 30), "600000.00",
                     "Noticed (amended 29 Sep). Not confirmed.")],
        "2026-10": [("C", "CPV3/CALL/2026/10", date(2026, 10, 2), date(2026, 10, 20), "450000.00", "Confirmed. In called."),
                    ("D", "CPO2/CALL/2026/10", date(2026, 10, 1), date(2026, 12, 4), "250000.00", "Confirmed. In called."),
                    ("E", "SIF2/CALL/2026/09A-R1", date(2026, 10, 6), date(2026, 10, 30), "600000.00",
                     "Noticed. Not confirmed. Not in called.")],
    }
    for k, ref, nd, dd, amt, st in status_map[folder]:
        ws2.append([k, ref, datetime.combine(nd, datetime.min.time()), datetime.combine(dd, datetime.min.time()),
                    float(amt), st])
        ws2.cell(row=ws2.max_row, column=3).number_format = "yyyy-mm-dd"
        ws2.cell(row=ws2.max_row, column=4).number_format = "yyyy-mm-dd"
        ws2.cell(row=ws2.max_row, column=5).number_format = "#,##0.00"
    for i, wdt in enumerate([10, 24, 14, 14, 14, 44], start=1):
        ws2.column_dimensions[ws2.cell(row=1, column=i).column_letter].width = wdt
    wb.save(path)


def write_receipt_log(path, folder):
    rows = [n for n in NOTICES if n["folder"] == folder]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "notice_kind", "manager_reference", "fund", "amount_usd", "notice_date",
                    "due_or_payment_date", "received_on", "office_note"])
        for n in rows:
            w.writerow([n["file"], n["kind"].title(), n["ref"], n["fund"], money(n["amount"]),
                        n["notice"].isoformat(), n["due"].isoformat(), n["received"].isoformat(), n["log_note"]])


# ---------------------------------------------------------------- main
def main():
    cash = build_cash()
    for folder, (asof, last_cash_day) in CYCLES.items():
        out = OUT / folder
        out.mkdir(parents=True, exist_ok=True)
        month_start = date(int(folder[:4]), int(folder[5:7]), 1)
        write_commitments(out / f"commitments_schedule_{asof.isoformat()}.xlsx", folder, asof)
        for code in ENTITIES:
            write_bank_csv(out / f"bank_cash_{code}_{folder}.csv", code, cash[code], month_start, last_cash_day)
        write_admin_csv(out / f"administrator_cash_{folder}.csv", cash, month_start, last_cash_day)
        write_receipt_log(out / "notice_receipt_log.csv", folder)
        for n in NOTICES:
            if n["folder"] == folder:
                write_pdf(out / n["file"], n)
        print(folder, "written to", out)

    # Gold (printed for the answer key; the key is written by hand from this output)
    for folder, (asof, last_cash_day) in CYCLES.items():
        cs = {code: cash[code][last_cash_day][0] for code in ENTITIES}
        print(folder, "cash at", last_cash_day, {k: money(v) for k, v in cs.items()})


if __name__ == "__main__":
    main()
