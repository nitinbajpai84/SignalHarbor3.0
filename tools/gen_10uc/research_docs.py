"""Deterministic generator: manager research documents (2 DDQs, 2 newsletters) as PDFs.
Every figure/name comes from docs/test/10uc_universe.json. Synthetic only."""
import json, pathlib, re
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from pypdf import PdfReader

ROOT = pathlib.Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
OUT = ROOT / "tests/v1/fixtures/10uc/research_docs"
OUT.mkdir(parents=True, exist_ok=True)
MG = {m["id"]: m for m in U["managers"]}
DOC = {d["id"]: d for d in U["documents"]}
FUND = {f["key"]: f for f in U["funds"]}
COMM = {c["fund"]: c for c in U["commitments"]}
ST = getSampleStyleSheet()
fmt = lambda s: f"{float(s):,.0f}"


def build(path, doc, flow):
    m = MG[doc["manager"]]

    def deco(c, d):
        c.saveState(); c.setFont("Helvetica", 8); c.setFillColor(colors.grey)
        c.drawString(40, 810, f"{m['name']}  |  {doc['title']}  |  Confidential  |  Synthetic test document")
        c.drawString(40, 28, f"{m['contact_email']}  |  Document date {doc['document_date']}")
        c.drawRightString(555, 28, f"Page {d.page}"); c.restoreState()
    SimpleDocTemplate(str(path), pagesize=A4, title=doc["title"], author=m["name"],
                      leftMargin=40, rightMargin=40, topMargin=50, bottomMargin=50,
                      invariant=1).build(flow, deco, deco)


def P(t, s="BodyText"): return Paragraph(t, ST[s])


def qa(rows):
    t = Table([["Ref", "Question", "Response"]] + [[a, P(b), P(c)] for a, b, c in rows], [35, 215, 265])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef0")),
                           ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def ddq_kestrel():
    d = DOC["doc-ddq-01"]; m = MG[d["manager"]]; h1, h2 = FUND["H1"], FUND["H2"]
    assets = re.search(r"([\d.]+) bn", d["key_facts"][0]).group(1)
    pms = re.search(r"managers: (.+)\.", d["key_facts"][1]).group(1)
    f = [P(d["title"], "Title"), P(f"Operational due diligence questionnaire. Completed for Evergreen Office, {d['document_date']}."),
         P(f"Respondent: {m['contact_name']}, Operations, {m['name']} ({m['contact_email']})."), Spacer(1, 10),
         P("1. Firm overview", "Heading2"),
         qa([("1.1", "Firm name and strategy", f"{m['name']}. {m['strategy']}."),
             ("1.2", "Total firm assets under management", f"USD {assets} bn (synthetic)."),
             ("1.3", "Funds offered to the investor", f"{h1['canonical_name']}; {h2['canonical_name']}.")]),
         Spacer(1, 8), P("2. Investment team", "Heading2"),
         qa([("2.1", "Portfolio managers of the Macro Fund", pms + "."),
             ("2.2", "Key person provisions", "Both portfolio managers are named as key persons in the fund documents."),
             ("2.3", "Changes to the investment team in the last 12 months", "None to report at the date of this questionnaire.")]),
         PageBreak(), P("3. Operations and valuation", "Heading2"),
         qa([("3.1", "Administrator and reporting frequency", "Independent administrator; monthly net asset value statements."),
             ("3.2", "Valuation policy", "Month-end valuations by the administrator; fee accruals reviewed monthly."),
             ("3.3", "Statement delivery", "Monthly statements by email to the contacts named by the investor."),
             ("3.4", "Business continuity", "Annual test; disaster recovery site in a separate region.")]),
         Spacer(1, 8), P("4. Attestation", "Heading2"),
         P(f"The undersigned confirms the responses are accurate at {d['document_date']}. Signed: {m['contact_name']}, {m['name']}.")]
    build(OUT / "kestrel_ridge_ddq_2026.pdf", d, f)
    return d


def ddq_cedarpoint():
    d = DOC["doc-ddq-02"]; m = MG[d["manager"]]
    days = re.search(r"within (\d+) days", d["key_facts"][0]).group(1)
    aud = re.search(r"effective (Q\d 2026)", d["key_facts"][1]).group(1)
    c, dd = FUND["C"], FUND["D"]
    f = [P(d["title"], "Title"), P(f"Operational due diligence questionnaire. Completed for Evergreen Office, {d['document_date']}."),
         P(f"Respondent: {m['contact_name']}, Investor Relations, {m['name']} ({m['contact_email']})."), Spacer(1, 10),
         P("1. Firm and funds", "Heading2"),
         qa([("1.1", "Firm name and strategy", f"{m['name']}. {m['strategy']}."),
             ("1.2", "Funds the investor holds", f"{c['canonical_name']} (commitment USD {fmt(COMM['C']['commitment_amount'])}); {dd['canonical_name']} (commitment USD {fmt(COMM['D']['commitment_amount'])}).")]),
         Spacer(1, 8), P("2. Reporting", "Heading2"),
         qa([("2.1", "Reporting frequency", "Quarterly."),
             ("2.2", "Timing of quarterly statements", f"Quarterly statements are delivered within {days} days of quarter end. Under its side letter, Evergreen Office receives them within 10 business days of quarter end."),
             ("2.3", "Capital call notice period", "Calls are noticed to investors in writing before the due date.")]),
         PageBreak(), P("3. Audit and governance", "Heading2"),
         qa([("3.1", "External auditor", f"Auditor change effective {aud}. The incoming auditor is appointed by the advisory committee."),
             ("3.2", "Impact of the auditor change on reporting", "Some year-end and interim reporting may take longer during the transition."),
             ("3.3", "Valuation policy", "Fair value by the manager, reviewed by the valuation committee each quarter.")]),
         Spacer(1, 8), P(f"Signed: {m['contact_name']}, {m['name']}, {d['document_date']}.")]
    build(OUT / "cedarpoint_ventures_ddq_2026.pdf", d, f)
    return d


def news(doc_id, fname, body):
    d = DOC[doc_id]; m = MG[d["manager"]]
    build(OUT / fname, d, [P(d["title"], "Title"), P(f"{m['name']} | {d['document_date']} | For investors"), Spacer(1, 10)] + body(d, m))
    return d


def kestrel_news(d, m):
    kf = d["key_facts"][0]
    left = re.search(r"Team change: (.+?) left the firm on (.+?);", kf).groups()
    stays = re.search(r"; (.+?) is sole portfolio manager of the (.+?) from (.+)\.", kf).groups()
    h1, h2 = FUND["H1"], FUND["H2"]
    return [P("Team update", "Heading2"),
            P(f"{left[0]} left the firm on {left[1]}. {stays[0]} is sole portfolio manager of the {stays[1]} from {stays[2]}."),
            P("The investment process, risk framework and operations team of the fund are unchanged."), Spacer(1, 8),
            P("Funds", "Heading2"), P(f"This letter covers the {h1['canonical_name']} and the {h2['canonical_name']}."), Spacer(1, 8),
            P("Operations", "Heading2"), P("Monthly statements continue to be issued by the administrator. Contact the operations desk for any question."),
            Spacer(1, 8), P(f"Contact: {m['contact_name']}, {m['contact_email']}.")]


def northgate_news(d, m):
    return [P("Mid-year letter", "Heading2"), P(f"{FUND['A']['canonical_name']}: one exit signed, closing expected Q4 2026."),
            P("Portfolio companies continue to trade in line with plan. Detailed valuations follow in the monthly statements."), Spacer(1, 8),
            P("Investor relations", "Heading2"), P(f"Contact: {m['contact_name']}, {m['contact_email']}.")]


def verify():
    txt = lambda f: " ".join(" ".join(p.extract_text().split()) for p in PdfReader(OUT / f).pages)
    k = txt("kestrel_ridge_ddq_2026.pdf"); assert "USD 2.4 bn" in k and "Thomas Lindqvist, Priya Nair" in k
    c = txt("cedarpoint_ventures_ddq_2026.pdf"); assert "within 45 days" in c and "10 business days" in c and "effective Q2 2026" in c
    assert fmt(COMM["C"]["commitment_amount"]) in c and fmt(COMM["D"]["commitment_amount"]) in c
    n = txt("kestrel_ridge_q3_2026_newsletter.pdf")
    assert "Thomas Lindqvist left the firm on 30 September 2026" in n
    assert "Priya Nair is sole portfolio manager of the Macro Fund from 1 October 2026" in n
    g = txt("northgate_mid_year_letter_2026.pdf"); assert "closing expected Q4 2026" in g
    for t in (k, c, n, g): assert "Page 1" in t


if __name__ == "__main__":
    docs = [ddq_kestrel(), ddq_cedarpoint(), news("doc-news-01", "kestrel_ridge_q3_2026_newsletter.pdf", kestrel_news),
            news("doc-news-02", "northgate_mid_year_letter_2026.pdf", northgate_news)]
    verify()
    files = {"doc-ddq-01": "kestrel_ridge_ddq_2026.pdf", "doc-ddq-02": "cedarpoint_ventures_ddq_2026.pdf",
             "doc-news-01": "kestrel_ridge_q3_2026_newsletter.pdf", "doc-news-02": "northgate_mid_year_letter_2026.pdf"}
    planted = {"doc-news-01": "P25 and P26 (team change)", "doc-ddq-01": "P25 context (named portfolio managers)",
               "doc-ddq-02": "P27 (45 days, auditor change)", "doc-news-02": "none (context)"}
    lines = ["# research_docs manifest (synthetic)", "",
             "Generated by `tools/gen_10uc/research_docs.py` from `docs/test/10uc_universe.json`. PDFs with header, footer and page numbers.", "",
             "| File | Universe id | Date | Holds | Planted facts carried |", "|---|---|---|---|---|"]
    for d in docs:
        lines.append(f"| {files[d['id']]} | {d['id']} | {d['document_date']} | {d['title']}: {' '.join(d['key_facts'])} | {planted[d['id']]} |")
    (OUT / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("ok", len(docs))
