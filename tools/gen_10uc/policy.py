"""Evergreen Office allocation policy PDF, all figures read from docs/test/10uc_universe.json. Synthetic."""
import json, re, sys
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tests/v1/fixtures/10uc/policy"
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
R = {r["rule_code"]: r for r in U["rules"]}
PF = {p["portfolio_code"]: p for p in U["portfolios"]}
EN = {e["entity_code"]: e["entity_name"] for e in U["legal_entities"]}
FILE = "Evergreen_Investment_Allocation_Policy_v2026.1.pdf"
pct = lambda x: f"{x:g}%"
usd = lambda x: f"{x:,.0f}"
S = getSampleStyleSheet()


def limit_rows():
    rows = [["Rule code", "Portfolio", "Entity", "Dimension", "Bucket", "Min", "Max"]]
    for c in ("limit_single_name_liquid", "limit_listed_equity_liquid", "limit_manager_entity_b", "limit_hedge_funds"):
        p = R[c]["parameters"]; pf = PF[p["portfolio_code"]]
        rows.append([c, p["portfolio_code"], EN[pf["legal_entity"]], p["dimension"].replace("_", " "),
                     "any single name" if p["bucket"] == "any" else p["bucket"].replace("_", " "),
                     pct(p["min_pct"]), pct(p["max_pct"])])
    return rows


def tbl(rows, widths):
    t = Table([[Paragraph(str(c), S["BodyText"]) for c in r] for r in rows], colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfe8e2")),
                           ("GRID", (0, 0), (-1, -1), .4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def page(c, d):
    c.saveState(); c.setFont("Helvetica", 8)
    c.drawString(20 * mm, 287 * mm, "Evergreen Office | Investment Allocation Policy | Version 2026.1 | SYNTHETIC TEST DOCUMENT")
    c.line(20 * mm, 285 * mm, 190 * mm, 285 * mm)
    c.drawString(20 * mm, 10 * mm, "Confidential - Evergreen Office - Issued by Risk (Sofia Reyes) - Approved by the CIO")
    c.drawRightString(190 * mm, 10 * mm, f"Page {d.page}")
    c.restoreState()


def build():
    P = lambda t, s="BodyText": Paragraph(t, S[s])
    ct, ma, eu, sd, fx, ca = (R[k] for k in ("cash_tolerance", "cio_materiality", "estimate_use", "statement_due", "fx_fixing", "cash_call_alert_days"))
    eff = R["limit_hedge_funds"]["effective_from"]
    cp = ma["parameters"]
    own = lambda r: f'{r["owner"]} (approved by {r["approved_by"]})'
    f = [P(f'{U["company"]["name"]}: Investment Allocation Policy', "Title"),
         P(f"Version 2026.1 | Effective {eff} | Document date {U['meta']['as_of']} | Policy owner: Sofia Reyes, Risk | Approved by: Daniel Foo, Chief Investment Officer"),
         Spacer(1, 6), P("1. Purpose and scope", "Heading2"),
         P(f"This policy sets the limits within which the investment portfolios of {U['company']['name']} are run: "
           "four portfolios across three legal entities (" + ", ".join(f"{k} {v}" for k, v in EN.items()) + "). "
           f"Base currency is {U['company']['base_currency']}; the office reports in {' and '.join(U['company']['reporting_currencies'])}."),
         P("2. Strategic allocation targets", "Heading2"),
         P("Strategic target weights per asset class are not set in this version. Until the Investment Committee issues them, "
           "the minimum and maximum limits in section 3 are the only allocation constraints in force."),
         P("3. Allocation limits (percent of the portfolio)", "Heading2"),
         tbl(limit_rows(), [44 * mm, 26 * mm, 26 * mm, 22 * mm, 24 * mm, 14 * mm, 14 * mm]),
         Spacer(1, 4),
         P("Each limit is measured on the portfolio value at the month end and owned by Risk. A breach opens a case and is reported to the CIO; "
           "a breach whose cause is an out-of-date manager valuation is recorded as such and not as a real breach."),
         P("4. Liquidity and capital calls", "Heading2"),
         P(f"{ca['definition_text']} Cash may differ from the administrator by up to {usd(ct['parameters']['abs_amount'])} "
           f"{ct['parameters']['currency']} per entity per day before it needs a case (owner {own(ct)})."),
         P("5. Single-manager and single-name limits", "Heading2"),
         P(f"Single name in EG-LIQUID: no more than {pct(R['limit_single_name_liquid']['parameters']['max_pct'])} of the portfolio. "
           f"Manager concentration in the Entity B operating portfolio (EG-B-OPS): no more than {pct(R['limit_manager_entity_b']['parameters']['max_pct'])} with Cedarpoint Ventures."),
         P("6. Approval line and reporting rules", "Heading2"),
         tbl([["Rule", "Wording", "Owner / approved by"]] +
             [[r["rule_code"], r["definition_text"], f'{r["owner"]} / {r["approved_by"]}'] for r in (ma, eu, sd, fx)],
             [34 * mm, 100 * mm, 36 * mm]),
         Spacer(1, 4),
         P(f"The CIO is told of any change over {usd(cp['abs_amount'])} {cp['currency']} or {cp['pct_of_fund']:g}% of a fund. "
           "Limits and rules are changed only by the owner and need the CIO's approval; the maker never checks their own work."),
         P("7. Approval", "Heading2"),
         tbl([["Role", "Name", "Date"], ["Policy owner (Risk)", "Sofia Reyes", eff], ["Approved (CIO)", "Daniel Foo", eff]], [60 * mm, 60 * mm, 50 * mm])]
    SimpleDocTemplate(str(OUT / FILE), pagesize=A4, pageCompression=0, invariant=1, title="Investment Allocation Policy 2026.1",
                      author="Evergreen Office (synthetic)", topMargin=25 * mm, bottomMargin=20 * mm).build(f, onFirstPage=page, onLaterPages=page)


def verify():
    from pypdf import PdfReader  # verification only
    rd = PdfReader(str(OUT / FILE)); raw = " " * rd.get_num_pages()
    txt = re.sub(r"\s+", " ", " ".join(pg.extract_text() for pg in rd.pages))
    flat = txt.replace(" ", "")
    for c in ("limit_single_name_liquid", "limit_listed_equity_liquid", "limit_manager_entity_b", "limit_hedge_funds"):
        p = R[c]["parameters"]
        assert c in flat
    for row in limit_rows()[1:]:
        assert row[5] in txt and row[6] in txt, row
    for r in (R["cash_tolerance"], R["cio_materiality"], R["estimate_use"], R["statement_due"], R["fx_fixing"], R["cash_call_alert_days"]):
        pass
    for s in (R[k]["definition_text"] for k in ("cio_materiality", "estimate_use", "statement_due", "fx_fixing", "cash_call_alert_days")):
        assert s in txt, s
    for n in ("5%", "0%", "60%", "90%", "55%", "20%", "5,000", "100,000", "0.5%"):
        assert n in txt, n
    print("verified", FILE, len(raw), "pages")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True); build(); verify()
