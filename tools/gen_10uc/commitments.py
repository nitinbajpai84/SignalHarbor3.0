"""Commitments register (xlsx) for the Evergreen Office 10UC universe. Deterministic; synthetic data only."""
import json, pathlib
from decimal import Decimal as D
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

ROOT = pathlib.Path(__file__).resolve().parents[2]
U = json.load(open(ROOT / "docs/test/10uc_universe.json"))
OUT = ROOT / "tests/v1/fixtures/10uc/commitments"
FILE = OUT / "Evergreen_Commitments_Register_2026-10-09.xlsx"
ENT = {e["entity_code"]: e["entity_name"] for e in U["legal_entities"]}
FUND = {f["key"]: f for f in U["funds"]}
MGR = {m.get("key") or m.get("id") or m.get("code"): m for m in U["managers"]}
MOV = U["cash_movements"]
NAVY = PatternFill("solid", fgColor="1F3A5F")
HDR = Font(bold=True, color="FFFFFF")
MONEY = '#,##0.00;[Red]-#,##0.00'


def mname(f):
    m = MGR.get(FUND[f]["manager"], {})
    return m.get("name") or m.get("manager_name") or FUND[f]["manager"]


def sheet(ws, title, sub, head, rows, widths, money_cols, foot):
    ws["A1"], ws["A2"] = title, sub
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"].font = Font(italic=True, color="555555")
    for i, h in enumerate(head, 1):
        c = ws.cell(4, i, h); c.font, c.fill = HDR, NAVY
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for r, row in enumerate(rows, 5):
        for i, v in enumerate(row, 1):
            c = ws.cell(r, i, v)
            if i in money_cols: c.number_format = MONEY
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w
    ws.freeze_panes = "A5"
    ws.cell(len(rows) + 7, 1, foot).font = Font(italic=True, size=9, color="777777")


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active; ws.title = "Register"
    rows = []
    for c in U["commitments"]:
        f = c["fund"]
        rows.append([ENT[c["legal_entity"]], c["legal_entity"], FUND[f]["canonical_name"], f, mname(f),
                     float(c["commitment_amount"]), c["currency"], c["committed_on"],
                     float(c["called_to_date"]), float(c["uncalled"]),
                     float(c["calls_noticed_or_due_after_as_of"]), float(c["distributions_in_window"])])
    n = len(rows)
    rows.append(["Total", "", "", "", "", sum(r[5] for r in rows), "USD", "", sum(r[8] for r in rows),
                 sum(r[9] for r in rows), sum(r[10] for r in rows), sum(r[11] for r in rows)])
    sheet(ws, "Evergreen Office - Private Fund Commitments Register",
          "As of 9 Oct 2026. Prepared by Operations (Mei Chen), reviewed by Finance (Raj Patel). Illustrative synthetic data.",
          ["Entity", "Entity code", "Fund", "Fund key", "Manager", "Commitment", "Currency", "Commitment date",
           "Called to date", "Uncalled", "Noticed / due after as-of", "Distributions Aug 2025 - Sep 2026"],
          rows, [26, 11, 34, 9, 18, 16, 9, 16, 16, 16, 18, 20], {6, 9, 10, 11, 12},
          "Evergreen Office internal register | Synthetic data | Called to date = capital called per confirmed notices to 9 Oct 2026; uncalled = commitment - called. Page 1 of 1")
    for c in ws[len(rows) + 4]: c.font = Font(bold=True)
    ws2 = wb.create_sheet("Notices")
    mv = [[m["id"], ENT[m["legal_entity"]], FUND[m["fund"]]["canonical_name"], m["fund"], m["notice_kind"].title(),
           float(m["amount"]), m["currency"], m["notice_date"], m["due_date"], m["confirmation_status"]] for m in MOV]
    sheet(ws2, "Capital call and distribution notices (Aug 2025 - Dec 2026)",
          "Source: manager and administrator notices as logged by Operations. Status 'noticed' = not yet confirmed with the manager.",
          ["Notice id", "Entity", "Fund", "Fund key", "Kind", "Amount", "Currency", "Notice date", "Due date", "Status"],
          mv, [20, 26, 34, 9, 13, 16, 9, 12, 12, 12], {6},
          "Evergreen Office internal log | Synthetic data")
    wb.save(FILE)


def verify():
    wb = load_workbook(FILE, data_only=True)
    reg = {r[3]: r for r in wb["Register"].iter_rows(min_row=5, max_row=9, values_only=True)}
    for c in U["commitments"]:
        r = reg[c["fund"]]
        assert D(str(r[5])) == D(c["commitment_amount"]) and D(str(r[8])) == D(c["called_to_date"])
        assert D(str(r[9])) == D(c["uncalled"]) == D(c["commitment_amount"]) - D(c["called_to_date"])
        assert D(str(r[10])) == D(c["calls_noticed_or_due_after_as_of"]) and D(str(r[11])) == D(c["distributions_in_window"])
        assert r[7] == c["committed_on"] and r[6] == c["currency"] and D(str(r[8])) <= D(str(r[5]))
        # called = called_before + confirmed calls with notice in window up to as-of
        calls = sum(D(m["amount"]) for m in MOV if m["fund"] == c["fund"] and m["notice_kind"] == "call"
                    and m["notice_date"] <= "2026-09-30")
        assert D(c["called_before_2025_08"]) + calls == D(c["called_to_date"]), c["fund"]
        # distributions: confirmed ones in window
        dist = sum(D(m["amount"]) for m in MOV if m["fund"] == c["fund"] and m["notice_kind"] == "distribution"
                   and m["confirmation_status"] == "confirmed")
        assert dist == D(c["distributions_in_window"]), c["fund"]
        # noticed/due after as-of = calls with notice date after 30 Sep
        later = sum(D(m["amount"]) for m in MOV if m["fund"] == c["fund"] and m["notice_kind"] == "call"
                    and m["notice_date"] > "2026-09-30")
        assert later == D(c["calls_noticed_or_due_after_as_of"]), c["fund"]
    ids = [r[0] for r in wb["Notices"].iter_rows(min_row=5, max_row=4 + len(MOV), values_only=True)]
    assert ids == [m["id"] for m in MOV]
    print("verified OK")


if __name__ == "__main__":
    build(); verify()
