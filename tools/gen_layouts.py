"""W2: 20 synthetic layouts for each of the 5 private-fund document types (100 PDFs) and the answer key, all invented parties.

    python tools/gen_layouts.py            writes tests/v1/fixtures/layouts/<type>_<nn>.pdf and keys.yaml
    make(doc_type, idx, seed=0)            -> (pdf bytes, expected {field: text}, meta) : a layout is fixed by (doc_type, idx); the seed changes only
                                              the fund, the investor and the figures, so seed 1 is the next document of the same layout.
A layout varies: the administrator's look (font, title wording), the order of fields, each label's wording, how fields are laid out (label and
value in two columns, "Label: value" lines, a header row over a value row, label over value, prose sentences mixed with columns), one page or
two, the date format, the currency inside or beside the amounts, optional fields left out, and a decoy figure with a similar label. Layout 19
of every type is a scan: the page is rasterised and the PDF holds only a picture."""
from __future__ import annotations

import io
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SCHEMAS = ROOT / "packs" / "family_office" / "1" / "doc_schemas"
OUT = ROOT / "tests" / "v1" / "fixtures" / "layouts"
TYPES = ["capital_call", "distribution_notice", "quarterly_statement", "nav_statement", "subscription_confirmation"]
SCAN_IDX = 19
FUNDS = ["Bluewater Growth Partners II", "Kestrel Credit Opportunities III", "Harbourline Infrastructure Fund", "Alder Ridge Real Assets IV",
         "Northgate Venture Fund V", "Tidewater Income Fund", "Sable Point Private Equity VII", "Linden Court Secondary Fund"]
INVESTORS = ["Foo Family Holdings Pte Ltd", "Tan Heritage Trust", "Lim Ventures LLC", "Quill Estate Company", "Raman Family Office Ltd", "Ong Legacy Partners"]
ADMINS = ["Harbourline Fund Services", "Corvane Administration", "Meridew Partners Services", "Alta Quay Fund Admin", "Brightwater Trust Services", "Kellmoor Fiduciary"]
FONTS = {"Helvetica": "Helvetica-Bold", "Times-Roman": "Times-Bold", "Courier": "Courier-Bold"}
DATE_FMT = ["%d %B %Y", "%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y", "%d-%b-%Y"]
TITLES = {
    "capital_call": ["Capital Call Notice", "Drawdown Notice", "Notice of Capital Call", "Capital Request", "Call for Capital", "Contribution Notice", "Payment Request"],
    "distribution_notice": ["Distribution Notice", "Notice of Distribution", "Distribution Advice", "Proceeds Notice", "Payment of Distribution", "Return of Capital Advice"],
    "quarterly_statement": ["Quarterly Statement", "Capital Account Statement", "Partner Capital Statement", "Quarterly Report to Investors", "Investor Account Summary",
                            "Statement of Partner Capital"],
    "nav_statement": ["Net Asset Value Statement", "NAV Statement", "Valuation Statement", "Holding Valuation", "Net Asset Value Notice", "Unit Valuation Advice"],
    "subscription_confirmation": ["Subscription Confirmation", "Confirmation of Subscription", "Subscription Advice", "Subscription Accepted", "Investment Confirmation",
                                  "Units Issued Notice"],
}
LABELS = {
    "fund": ["Fund", "Fund name", "Partnership", "Name of fund", "Issuer"],
    "investor": ["Investor", "Limited partner", "Investor name", "Addressed to", "Unit holder"],
    "call_number": ["Call number", "Call no.", "Drawdown number", "Notice sequence"],
    "currency": ["Currency", "Ccy", "Payment currency", "Reporting currency"],
    "amount_due": ["Amount due", "Capital requested", "Total call amount", "Please pay", "Drawdown amount"],
    "investment_amount": ["For investments", "Investment portion", "Portfolio funding", "Capital for investments"],
    "fee_amount": ["For fees and expenses", "Management fee portion", "Fees", "Expenses and fees"],
    "due_date": ["Due date", "Payment due", "Funds required by", "Value date", "Settle by"],
    "notice_date": ["Notice date", "Date of notice", "Issued on", "Date"],
    "bank_account": ["Bank account", "Remit to account", "Beneficiary account", "Payment account"],
    "distribution_number": ["Distribution number", "Distribution no.", "Sequence"],
    "total_distribution": ["Total distribution", "Amount distributed", "Gross proceeds", "Total paid to you"],
    "recallable_amount": ["Recallable", "Return of capital (recallable)", "Recallable portion", "Capital returned, recallable"],
    "non_recallable_amount": ["Non-recallable", "Gains and income (non-recallable)", "Non-recallable portion", "Profit distribution"],
    "payment_date": ["Payment date", "Paid on", "Pay date", "Value date"],
    "record_date": ["Record date", "Entitlement date", "Holders of record on"],
    "period_end": ["Period end", "Statement date", "As at", "Quarter ended", "Reporting date"],
    "opening_balance": ["Opening balance", "Balance brought forward", "Capital account at start", "Beginning capital"],
    "contributions": ["Contributions", "Capital contributed", "Paid-in during period", "Additions"],
    "distributions": ["Distributions", "Capital returned", "Paid out during period", "Withdrawals"],
    "net_gain": ["Net gain (loss)", "Profit or loss for the period", "Net income allocated", "Investment result"],
    "closing_balance": ["Closing balance", "Ending capital account", "Capital account at end", "Balance carried forward"],
    "unfunded_commitment": ["Unfunded commitment", "Remaining commitment", "Undrawn commitment", "Still to be called"],
    "share_class": ["Share class", "Class", "Unit class", "Series"],
    "valuation_date": ["Valuation date", "NAV date", "Priced as at", "Struck on"],
    "units_held": ["Units held", "Number of units", "Your holding (units)", "Shares held"],
    "nav_per_unit": ["NAV per unit", "Net asset value per share", "Unit price (NAV)", "Price per unit at valuation"],
    "nav_total": ["Net asset value", "Value of your holding", "Total NAV", "Holding value"],
    "subscription_amount": ["Subscription amount", "Amount subscribed", "Total invested", "Your subscription"],
    "units_issued": ["Units issued", "Number of units allotted", "Shares allotted", "Units allocated"],
    "price_per_unit": ["Price per unit", "Issue price", "Dealing price", "Subscription price per share"],
    "trade_date": ["Trade date", "Dealing date", "Subscription date", "Accepted on"],
    "settlement_date": ["Settlement date", "Cash settles on", "Value date", "Paid on"],
}
DECOYS = {"capital_call": "Total commitment", "distribution_notice": "Cumulative distributions to date", "quarterly_statement": "Total commitment",
          "nav_statement": "Fund net assets", "subscription_confirmation": "Minimum initial subscription"}
PROSE = ["Our records show the {l} as {v}.", "The {l} is {v}.", "Please note that the {l} is {v}."]


def figures(doc_type: str, r: random.Random) -> dict:
    """Values of one document, consistent with the schema's checks."""
    base = date(2026, r.randint(1, 9), r.randint(1, 28))
    ccy = r.choice(["USD", "EUR", "SGD", "GBP"])
    v = {"fund": r.choice(FUNDS), "currency": ccy}
    m = lambda lo, hi, step: Decimal(r.randint(lo, hi) * step)  # noqa: E731
    if doc_type != "nav_statement":
        v["investor"] = r.choice(INVESTORS)
    if doc_type == "capital_call":
        inv, fee = m(4, 60, 25000), m(1, 24, 1250)
        v.update(call_number=r.randint(1, 9), amount_due=inv + fee, investment_amount=inv, fee_amount=fee, due_date=base + timedelta(days=14), notice_date=base,
                 bank_account=f"SG{r.randint(10, 99)} DBSS {r.randint(1000, 9999)} {r.randint(1000, 9999)} {r.randint(1000, 9999)}")
    elif doc_type == "distribution_notice":
        rec, non = m(2, 30, 10000), m(1, 40, 5000)
        v.update(distribution_number=r.randint(1, 12), total_distribution=rec + non, recallable_amount=rec, non_recallable_amount=non,
                 payment_date=base + timedelta(days=7), record_date=base)
    elif doc_type == "quarterly_statement":
        op, c, d, g = m(40, 400, 25000), m(1, 20, 25000), m(1, 12, 10000), Decimal(r.randint(-40, 80) * 1500)
        v.update(period_end=date(2026, r.choice([3, 6, 9]), 30), opening_balance=op, contributions=c, distributions=d, net_gain=g,
                 closing_balance=op + c - d + g, unfunded_commitment=m(10, 300, 25000))
    elif doc_type == "nav_statement":
        units, nav = Decimal(r.randint(1000, 90000)) + Decimal(r.randint(1, 999)) / 1000, Decimal(r.randint(900000, 1900000)) / 10000
        v.update(share_class=f"Class {r.choice('ABCI')} {ccy}", valuation_date=base, units_held=units, nav_per_unit=nav, nav_total=(units * nav).quantize(Decimal("0.01")))
    else:
        units, price = Decimal(r.randint(1000, 90000)), Decimal(r.choice(["100", "1000", "125.50", "98.75"]))
        v.update(share_class=f"Class {r.choice('ABCI')} {ccy}", subscription_amount=units * price, units_issued=units, price_per_unit=price, trade_date=base,
                 settlement_date=base + timedelta(days=3))
    return v


def key(vtype: str, v) -> str:
    if vtype == "money":
        return f"{v:.2f}"
    if vtype == "number":
        return format(Decimal(v).normalize(), "f")
    return v.isoformat() if isinstance(v, date) else str(v)


def spec(doc_type: str, idx: int) -> dict:
    r = random.Random(f"{doc_type}:{idx}")
    fields = yaml.safe_load((SCHEMAS / f"{doc_type}.yaml").read_text(encoding="utf-8"))["fields"]
    return {"font": r.choice(list(FONTS)), "size": r.choice([9, 10, 11]), "style": ["kv", "colon", "table", "stack", "mixed"][idx % 5], "two_pages": idx % 3 == 1,
            "date_fmt": r.choice(DATE_FMT), "bare_ccy": r.random() < 0.4, "paren_neg": r.random() < 0.5, "admin": r.choice(ADMINS), "title": r.choice(TITLES[doc_type]),
            "labels": {f["name"]: r.choice(LABELS[f["name"]]) for f in fields}, "order": r.sample([f["name"] for f in fields], len(fields)),
            "omit": [f["name"] for f in fields if not f.get("required") and r.random() < 0.2], "prose": r.choice(PROSE), "cut": r.randint(5, 8),
            "decoy_first": r.random() < 0.5, "fields": fields}


def _text(f: dict, v, s: dict, ccy: str | None) -> str:
    t = f["type"]
    if t == "date":
        return v.strftime(s["date_fmt"])
    if t == "money":
        body = f"({abs(v):,.2f})" if v < 0 and s["paren_neg"] else f"{v:,.2f}"
        return f"{ccy} {body}" if ccy else body
    if t == "number":
        return f"{v:,.4f}" if f["name"] == "nav_per_unit" else f"{v:,.3f}" if f["name"] == "units_held" else f"{v:,.2f}"
    return str(v)


def render(doc_type: str, idx: int, vals: dict) -> tuple[bytes, dict]:
    from reportlab.pdfgen import canvas
    s, buf = spec(doc_type, idx), io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    types = {f["name"]: f for f in s["fields"]}
    names = [n for n in s["order"] if n in vals and n not in s["omit"] and not (n == "currency" and not s["bare_ccy"])]
    ccy = None if s["bare_ccy"] else vals["currency"]
    pages = [names[:s["cut"]], names[s["cut"]:]] if s["two_pages"] and len(names) > s["cut"] + 1 else [names]
    for pno, chunk in enumerate(pages, 1):
        y = 800
        c.setFont(FONTS[s["font"]], s["size"] + 6)
        c.drawString(50, y, s["admin"] if pno == 1 else f"{s['admin']} (continued)")
        y -= 28
        c.setFont(s["font"], s["size"] + 3)
        c.drawString(50, y, s["title"])
        y -= 34
        c.setFont(s["font"], s["size"])
        items = [(s["labels"][n], _text(types[n], vals[n], s, ccy if types[n]["type"] == "money" else None)) for n in chunk]
        if pno == 1:
            items.insert(0 if s["decoy_first"] else len(items), (DECOYS[doc_type], f"{ccy + ' ' if ccy else ''}{vals['_decoy']:,.2f}"))
        if s["style"] == "table":
            for k in range(0, len(items), 3):
                for j, (lab, val) in enumerate(items[k:k + 3]):
                    c.drawString(50 + j * 180, y, lab)
                    c.drawString(50 + j * 180, y - 16, val)
                y -= 46
        else:
            for k, (lab, val) in enumerate(items):
                st = ("prose" if k % 2 else "kv") if s["style"] == "mixed" else s["style"]
                if st == "kv":
                    c.drawString(50, y, lab)
                    c.drawString(270, y, val)
                    y -= 20
                elif st == "colon":
                    c.drawString(50, y, f"{lab}: {val}")
                    y -= 20
                elif st == "stack":
                    c.setFont(s["font"], s["size"] - 1)
                    c.drawString(50, y, lab)
                    c.setFont(s["font"], s["size"] + 1)
                    c.drawString(50, y - 15, val)
                    c.setFont(s["font"], s["size"])
                    y -= 38
                else:
                    c.drawString(50, y, s["prose"].format(l=lab.lower(), v=val))
                    y -= 20
        c.setFont(s["font"], s["size"] - 2)
        c.drawString(50, 60, f"Page {pno} of {len(pages)}.  Synthetic document: every party and figure is invented.")
        c.showPage()
    c.save()
    return buf.getvalue(), {"style": s["style"], "pages": len(pages)}


def scan(pdf: bytes) -> bytes:
    import fitz
    out = fitz.open()
    with fitz.open(stream=pdf, filetype="pdf") as src:
        for pg in src:
            png = pg.get_pixmap(dpi=200, colorspace=fitz.csGRAY).tobytes("png")
            page = out.new_page(width=pg.rect.width, height=pg.rect.height)
            page.insert_image(page.rect, stream=png)
    data = out.tobytes(deflate=True)
    out.close()
    return data


def make(doc_type: str, idx: int, seed: int = 0) -> tuple[bytes, dict, dict]:
    vals = figures(doc_type, random.Random(f"{doc_type}:{idx}:{seed}:v"))
    vals["_decoy"] = Decimal(random.Random(f"{seed}{idx}").randint(100, 900) * 10000)
    pdf, meta = render(doc_type, idx, vals)
    sp = spec(doc_type, idx)
    types = {f["name"]: f["type"] for f in sp["fields"]}
    expected = {n: key(types[n], vals[n]) for n in types if n in vals and n not in sp["omit"]}
    meta.update(doc_type=doc_type, layout=idx, scanned=idx == SCAN_IDX, absent=sorted(n for n in types if n not in expected))
    return (scan(pdf) if idx == SCAN_IDX else pdf), expected, meta


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    keys = {}
    for t in TYPES:
        for i in range(20):
            pdf, exp, meta = make(t, i)
            name = f"{t}_{i:02d}.pdf"
            (OUT / name).write_bytes(pdf)
            keys[name] = {"doc_type": t, "layout": i, "style": meta["style"], "scanned": meta["scanned"], "pages": meta["pages"], "absent": meta["absent"], "fields": exp}
    (OUT / "keys.yaml").write_text(yaml.safe_dump(keys, sort_keys=True, allow_unicode=True), encoding="utf-8")
    print(f"{len(keys)} files in {OUT}")


if __name__ == "__main__":
    main()
