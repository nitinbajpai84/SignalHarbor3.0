"""Deterministic generator: manager capital account / NAV statements (PDF) for private and hedge funds.
Reads every figure from docs/test/10uc_universe.json. Synthetic data only.
Run: python tools/gen_10uc/manager_statements.py
"""
import json
import datetime as dt
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text())
OUT = ROOT / "tests/v1/fixtures/10uc/manager_statements"
FUNDS = {f["key"]: f for f in U["funds"]}
MGRS = {m["id"]: m for m in U["managers"]}
KEYS = ["A", "B", "C", "D", "E", "H1", "H2"]  # private and hedge funds (L1/L2 are index funds, other category)
# per-manager layout: colour, document title, value label, file slug, address (synthetic)
STYLE = {
    "MGR-NORTHGATE": ("#1f3a5f", "Capital Account Statement", "Closing capital account balance", "northgate", "Northgate Partners, 12 Quay Street, Harbor City"),
    "MGR-BLUEWATER": ("#0b6e75", "Partner Valuation Statement", "Net asset value of your interest", "bluewater", "Bluewater Capital, 40 Marina Road, Harbor City"),
    "MGR-CEDARPOINT": ("#5b3a7a", "Capital Account Statement", "Limited partner capital balance", "cedarpoint", "Cedarpoint Ventures, 7 Orchard Lane, Harbor City"),
    "MGR-SALTMARSH": ("#6b4e16", "Capital Account Statement", "Net capital account value", "saltmarsh", "Saltmarsh Real Assets, 3 Dockside Way, Harbor City"),
    "MGR-KESTREL": ("#8a1c2b", "Monthly NAV Statement", "Net asset value of holding", "kestrel", "Kestrel Ridge Advisors, 88 Ridge Avenue, Harbor City"),
}
DEFAULT_NAME = {"A": "Evergreen Growth I", "B": "Fund B - Evergreen Income II", "C": "Cedarpoint Ventures III, L.P.",
                "D": "Cedarpoint Opportunities Fund II", "E": "Saltmarsh Infrastructure Fund II",
                "H1": "Kestrel Ridge Macro Fund", "H2": "KR Equity Long Short Ltd"}


def money(v):
    return f"{float(v):,.2f}"


def dlong(d):
    d = dt.date.fromisoformat(d[:10])
    return f"{d.day} {d:%B %Y}"


def build(s, orig):
    f = FUNDS[s["fund"]]
    m = MGRS[f["manager"]]
    col, doctitle, vlabel, slug, addr = STYLE[f["manager"]]
    fname = DEFAULT_NAME[s["fund"]]
    if s["title"]:  # fund name as printed on this statement's title
        for n in f["identifiers"]["manager_email"]["manager_fund_name"]:
            if n in s["title"]:
                fname = n
    amended = s["kind"] == "amended"
    label = "Final - Amended" if amended else ("Estimate" if s["kind"] == "estimate" else "Final")
    fn = OUT / f"{slug}_{s['fund']}_{s['period_end']}_{s['kind']}.pdf"
    c = canvas.Canvas(str(fn), pagesize=A4, invariant=1)
    c.setTitle(f"{fname} - {dlong(s['period_end'])} - {label}")
    c.setAuthor(m["name"])
    W, H = A4

    def frame(pg):
        c.setFillColor(colors.HexColor(col))
        c.rect(0, H - 60, W, 60, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, H - 38, m["name"])
        c.setFont("Helvetica", 9)
        c.drawRightString(W - 40, H - 38, doctitle)
        c.setFillColor(colors.grey)
        c.setFont("Helvetica", 8)
        c.line(40, 50, W - 40, 50)
        c.drawString(40, 38, f"{addr}  |  {m['contact_email']}  |  Synthetic test document")
        c.drawRightString(W - 40, 38, f"Page {pg} of 2  |  Ref {s['statement_id']}")
        c.setFillColor(colors.black)

    # page 1: cover letter
    frame(1)
    y = H - 100
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Date issued: {dlong(s['received_at'])}")
    y -= 30
    for l in ["Evergreen Office", "Attn: Mei Chen, Investment Operations", "Harbor City"]:
        c.drawString(40, y, l)
        y -= 14
    y -= 16
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, fname)
    y -= 18
    c.setFont("Helvetica", 11)
    per = "quarter" if f["statement_frequency"] == "quarterly" else "month"
    c.drawString(40, y, f"{doctitle} for the {per} ended {dlong(s['period_end'])}")
    y -= 30
    c.setFont("Helvetica", 10)
    lines = [f"Dear {'Shareholder' if f['manager'] == 'MGR-KESTREL' else 'Investor'},", "",
             f"Please find enclosed your {doctitle.lower()} for the period ended {dlong(s['period_end'])}.",
             "The valuation, units and status are set out on page 2.", f"Status of this statement: {label}.", ""]
    if amended:
        reason = (s["note"] or "").split("Not loaded")[0].strip() or "see page 2"
        lines += ["THIS STATEMENT AMENDS AND SUPERSEDES THE EARLIER STATEMENT FOR THE SAME PERIOD.",
                  f"Reason for amendment: {reason}", ""]
    if s["kind"] == "estimate":
        lines += ["This is an estimate. A final statement will follow once the administrator closes the period.", ""]
    lines += ["Please contact us with any questions.", "", "Yours sincerely,", m["contact_name"], m["name"]]
    for l in lines:
        c.drawString(40, y, l)
        y -= 14
    c.showPage()

    # page 2: valuation table, same layout for every statement of a manager
    frame(2)
    y = H - 100
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Valuation summary")
    y -= 26
    rows = [("Fund", fname), ("Administrator code", f["identifiers"]["administrator"]["administrator_code"]),
            ("Period end", dlong(s["period_end"])), (vlabel, f"USD {money(s['value'])}"),
            ("Currency", f["currency"]), ("Units", "n/a (no unitised holding)"), ("Statement status", label),
            ("Date issued", dlong(s["received_at"]))]
    if amended:
        rows += [("Previously reported", f"USD {money(orig['value'])}"),
                 ("Change", f"USD {float(s['value']) - float(orig['value']):+,.2f}")]
    c.setFont("Helvetica", 10)
    for k, v in rows:
        c.setFillColor(colors.HexColor("#eeeeee"))
        c.rect(40, y - 5, W - 80, 20, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.drawString(48, y, k)
        c.drawString(250, y, str(v))
        y -= 24
    y -= 10
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(40, y, "Values are unaudited unless stated. This document is fictional and for testing only.")
    c.showPage()
    c.save()
    return fn, label


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob("*.pdf"):
        p.unlink()
    S = [s for s in U["statements"] if s["fund"] in KEYS]
    finals = {(s["fund"], s["period_end"]): s for s in S if s["kind"] in ("final", "estimate")}
    man = []
    for s in S:
        if s["kind"] == "missing":
            man.append((s, None, None))
            continue
        fn, label = build(s, finals.get((s["fund"], s["period_end"])))
        man.append((s, fn, label))
    planted = {
        "stmt-A-2026-09-30-amended": "P02/P12 Fund A amended 10,000,000 -> 10,180,000",
        "stmt-C-2026-06-30-amended": "P12 Fund C amended 8,420,000 -> 8,275,000",
        "stmt-H1-2026-07-31-amended": "P12/P13 Fund H1 amended 7,050,000 -> 7,012,500, second fund name",
        "stmt-E-2026-06-30-final": "P10 received 8 business days late",
        "stmt-D-2026-03-31-final": "P10 received 5 business days late",
        "stmt-H2-2026-08-31-final": "P10 received 6 business days late",
        "stmt-E-2026-09-30-final": "P04/P07 received 8 Oct, after the NAV of 2 Oct",
        "stmt-B-2026-09-30-final": "P13 fund printed as 'Fund B - Evergreen Liquid Book'",
        "stmt-D-2026-06-30-missing": "P11 MISSING, no file",
    }
    L = ["# Manager statements (synthetic)", "",
         "Generated by tools/gen_10uc/manager_statements.py from docs/test/10uc_universe.json (no randomness).",
         "Private funds A-E and hedge funds H1, H2 only; L1/L2 index fund statements belong to another category. "
         "Page 1 is a cover letter, page 2 the valuation table (value, units, period, status).", "",
         f"Files: {sum(1 for x in man if x[1])}. Missing (no file): 1 (Fund D, 30 Jun 2026).", "",
         "| File | Fund | Period end | Value USD | Label | Issued | Planted facts |", "|---|---|---|---|---|---|---|"]
    for s, fn, label in man:
        L.append(f"| {fn.name if fn else '(none)'} | {s['fund']} | {s['period_end']} | {s['value'] or ''} | "
                 f"{label or 'missing'} | {(s['received_at'] or '')[:10]} | {planted.get(s['statement_id'], '')} |")
    (OUT / "MANIFEST.md").write_text("\n".join(L) + "\n")
    return man


def verify(man):
    from pypdf import PdfReader
    n = 0
    for s, fn, label in man:
        if not fn:
            assert s["kind"] == "missing" and not list(OUT.glob(f"*_{s['fund']}_{s['period_end']}_missing*"))
            continue
        r = PdfReader(str(fn))
        assert len(r.pages) == 2
        t2 = r.pages[1].extract_text()
        assert f"USD {money(s['value'])}" in t2 and label in t2 and dlong(s["period_end"]) in t2, fn.name
        n += 1
    assert sum(1 for s, fn, _ in man if s["kind"] == "amended") == 3
    print("verified", n, "pdfs")


if __name__ == "__main__":
    verify(main())
