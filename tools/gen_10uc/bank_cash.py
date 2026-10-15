"""Bank cash statements (xlsx) from docs/test/10uc_universe.json. Deterministic, no randomness."""
import json
from decimal import Decimal
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tests/v1/fixtures/10uc/bank_cash"
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text())
# Fictional bank per entity: (bank, account no., account name, branch)
BANKS = {
    "EG-HOLD": ("Harbourline Private Bank (synthetic)", "HPB-0012-884401", "Evergreen Holdings - USD Operating"),
    "EG-TRUST": ("Harbourline Private Bank (synthetic)", "HPB-0012-884517", "Evergreen Family Trust - USD Operating"),
    "EG-B": ("Tidewater Commercial Bank (synthetic)", "TCB-7730-210958", "Entity B - USD Operating"),
}
ENT = {e["entity_code"]: e["entity_name"] for e in U["legal_entities"]}
# Bank closing = administrator cash, except Entity B on 8 Oct where the bank agrees with the trading export (planted 12,400).
B_BREAK = {r["date"] for r in U["cash_daily"] if r["entity"] == "EG-B" and r["difference"] != "0.00"}


def bank_close(r):
    return Decimal(r["trading_export"] if (r["entity"] == "EG-B" and r["date"] in B_BREAK) else r["administrator"])


TX_HDR = ["Value date", "Reference", "Type", "Description", "Counterparty", "Amount", "Currency"]


def bank_items(ent):
    return sorted((t for t in U["cash_activity"] if t["entity"] == ent and t["bank_date"]), key=lambda t: (t["bank_date"], t["reference"]))


def build():
    rows = {}
    for r in U["cash_daily"]:
        rows.setdefault(r["entity"], []).append(r)
    files = {}
    for ent, rs in rows.items():
        rs.sort(key=lambda r: r["date"])
        bank, acct, name = BANKS[ent]
        wb = Workbook(); ws = wb.active; ws.title = "Daily balances"
        ws["A1"] = bank; ws["A1"].font = Font(bold=True, size=14)
        ws["A2"] = "Account statement - daily ledger balances (SYNTHETIC TEST DATA)"
        ws["A3"] = f"Account name: {name}"; ws["A4"] = f"Account number: {acct}"
        ws["A5"] = "Currency: USD"
        ws["A6"] = f"Period: {rs[0]['date']} to {rs[-1]['date']}"
        ws["A7"] = f"Generated: {U['meta']['as_of']} 06:00 UTC"
        hdr = ["Value date", "Account number", "Currency", "Opening balance", "Net movement", "Closing ledger balance"]
        for c, h in enumerate(hdr, 1):
            x = ws.cell(9, c, h); x.font = Font(bold=True, color="FFFFFF"); x.fill = PatternFill("solid", fgColor="1F3A5F")
        prev = None
        for i, r in enumerate(rs):
            close = bank_close(r)
            opening = prev if prev is not None else None
            ws.cell(10 + i, 1, r["date"]); ws.cell(10 + i, 2, acct); ws.cell(10 + i, 3, "USD")
            if opening is not None:
                ws.cell(10 + i, 4, float(opening)); ws.cell(10 + i, 5, float(close - opening))
            ws.cell(10 + i, 6, float(close))
            prev = close
            for c in (4, 5, 6):
                ws.cell(10 + i, c).number_format = "#,##0.00;[Red]-#,##0.00"
        end = 10 + len(rs)
        ws.cell(end + 1, 1, "Closing balance at period end:").font = Font(bold=True)
        ws.cell(end + 1, 6, float(prev)).number_format = "#,##0.00"
        ws.cell(end + 3, 1, "First day opening balance not shown: statement starts at first value date in period.")
        ws.cell(end + 4, 1, f"{bank} - synthetic document for testing. Page 1 of 1")
        for col, w in zip("ABCDEF", (14, 20, 10, 18, 16, 22)): ws.column_dimensions[col].width = w
        ws.freeze_panes = "A10"
        # the items behind each day's net movement (P08b: the bank pays WIRE-20261008-B01 on 8 Oct, like the trading export)
        tx = wb.create_sheet("Transactions")
        for c, h in enumerate(TX_HDR, 1):
            x = tx.cell(1, c, h); x.font = Font(bold=True, color="FFFFFF"); x.fill = PatternFill("solid", fgColor="1F3A5F")
        for i, t in enumerate(bank_items(ent), 2):
            for c, v in enumerate((t["bank_date"], t["reference"], t["movement_type"], t["description"], t["counterparty"], float(Decimal(t["amount"])), t["currency"]), 1):
                tx.cell(i, c, v)
            tx.cell(i, 6).number_format = "#,##0.00;[Red]-#,##0.00"
        for col, w in zip("ABCDEFG", (12, 20, 14, 46, 40, 14, 9)): tx.column_dimensions[col].width = w
        f = OUT / f"{ent.lower().replace('-', '_')}_bank_statement_2026-09-09_to_2026-10-08.xlsx"
        wb.save(f); files[f.name] = (ent, acct, rs)
    return files


def verify(files):
    for fn, (ent, acct, rs) in files.items():
        ws = load_workbook(OUT / fn).active
        got = {ws.cell(r, 1).value: Decimal(str(ws.cell(r, 6).value)) for r in range(10, 10 + len(rs))}
        assert len(got) == 30, fn
        for r in rs:
            exp = bank_close(r)
            assert got[r["date"]] == exp, (fn, r["date"])
            diff = Decimal(r["administrator"]) - got[r["date"]]
            assert diff == (Decimal("12400.00") if (ent == "EG-B" and r["date"] == "2026-10-08") else 0), (fn, r["date"])
        txs = list(load_workbook(OUT / fn)["Transactions"].iter_rows(min_row=2, values_only=True))
        prev = Decimal(U["cash_opening_8_sep"][ent]["administrator"])
        for r in rs:
            net = sum((Decimal(str(t[5])).quantize(Decimal("0.01")) for t in txs if t[0] == r["date"]), Decimal(0))
            assert prev + net == got[r["date"]], (fn, r["date"], prev, net)
            prev = got[r["date"]]
    print("verified", len(files), "files")


def manifest(files):
    L = ["# bank_cash fixtures (synthetic)", "", "Generated by `tools/gen_10uc/bank_cash.py` from `docs/test/10uc_universe.json`. Fictional banks, accounts and entities.", "",
         "| File | Holds | Planted facts |", "|---|---|---|"]
    for fn, (ent, acct, rs) in files.items():
        note = "P08: bank balance 868,000.00 on 2026-10-08 vs administrator 880,400.00 (12,400.00 over tolerance 5,000)" if ent == "EG-B" else \
            ("P08 (no case): bank equals administrator 1,150,000.00 on 8 Oct; the 1,800 gap exists only against the trading export" if ent == "EG-TRUST" else "P08: 2,300,000.00 on 8 Oct, equal in both views")
        L.append(f"| {fn} | {ENT[ent]}, account {acct}, 30 daily closing ledger balances 2026-09-09 to 2026-10-08 | {note} |")
    L += ["", "Bank closing balance = universe administrator cash, except Entity B on 2026-10-08 where it equals the trading export figure.",
          "Calendar days incl. weekends are included because the universe carries them. Net movement is closing minus previous closing.",
          "Sheet `Transactions`: the items behind each day's net movement, from universe `cash_activity` (bank_date), starting from the 8 Sep closing balance in `cash_opening_8_sep`.",
          "P08b: WIRE-20261008-B01, -12,400.00, legal fees, paid by the bank on 2026-10-08 (the administrator books it on 2026-10-09)."]
    (OUT / "MANIFEST.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fs = build(); verify(fs); manifest(fs)
