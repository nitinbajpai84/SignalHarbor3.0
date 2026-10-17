"""More files for the Evergreen Office data set: allowances, administrator and custodian invoices, contracts, audit request, close checklist,
exception log, fund teaser, due-diligence questionnaires. Same conventions as files.py."""
import datetime as dt
from decimal import Decimal as D

from .files import MESS, RECV, dlong, money, month_end, months, mess, pname
from .world import DAYS, END, ENT, FAMILY, ADMIN_RATE, CUST_RATE, U, add_bd, bdays, d, lastbd, ym, q2
from .writers import write_csv, write_pdf, write_xlsx

AUDIT_ITEMS = [("2026-06", "Evergreen Liquid Book"), ("2026-08", "Evergreen Income II"), ("2026-09", "Evergreen Growth I"), ("2026-05", "Evergreen Liquid Book"),
               ("2026-07", "Evergreen Growth I"), ("2026-04", "Evergreen Income II"), ("2026-09", "Evergreen Liquid Book"), ("2026-07", "Evergreen Growth I (as sampled)")]
# deterministic close status per step for each month (done_on offsets in business days after month end; None = still open)
CLOSE_DONE = {"default": [2, 2, 3, 3, 3, 3]}
CLOSE_SEP = [2, 2, None, 3, 5, None]  # Sep: statements still open, review done 5 bd after month end (due 3), final read open


# vendor, currency, annual cost, renewal date, file
CONTRACTS = [("Orchard IT Services", "SGD", D(35400), d("2026-12-31"), "vendor_contract_orchard_it.pdf"), ("Quill Research Subscriptions", "USD", D(19200), d("2026-11-30"), "vendor_contract_quill_research.pdf"),
             ("Marina Office Suites", "SGD", D(222000), d("2027-03-31"), "vendor_contract_marina_lease.pdf"), ("Summit Tax Advisory", "SGD", D(12600), d("2027-01-31"), "vendor_contract_summit_tax.pdf")]


def register(w, asof):
    """Commitments register as the office keeps it: calls counted when the notice is recorded (notice date <= asof, and not the one that arrived on asof)."""
    from .world import PRIVATE, TERMS, FUND, MGR
    rows = []
    for f in PRIVATE:
        com, bef = D(TERMS[f][0]), D(TERMS[f][1])
        rec = sum((c["amount"] for c in w.calls if c["fund"] == f and c["notice"] < asof.isoformat()), D(0))
        pend = sum((c["amount"] for c in w.calls if c["fund"] == f and c["notice"] == asof.isoformat()), D(0))
        dist = sum((x["amount"] for x in w.dists if x["fund"] == f and x["pay"] <= asof.isoformat()), D(0))
        rows.append([ENT[FUND[f]["legal_entity"]], FUND[f]["legal_entity"], pname(f), f, MGR[FUND[f]["manager"]]["name"], float(com), "USD", float(bef + rec), float(com - bef - rec), float(pend), float(dist)])
    return rows


def cash_breaks(w):
    """Every entity-day where the administrator or the desk differs from the bank, per currency."""
    out = []
    for x in DAYS:
        for e in ENT:
            for c in ("USD", "SGD"):
                b = w.cash(e, c, x, "bank")
                for src in ("admin", "oms"):
                    v = w.cash(e, c, x, src)
                    if v != b: out.append(dict(date=x, ent=e, ccy=c, src=src, bank=b, other=v, diff=q2(v - b)))
    return out


def close_items(w):
    steps = U["process"]["steps"]; rows = []
    for m in months("2026-04", "2026-09"):
        me = month_end(m); due = add_bd(me, 3)
        offs = CLOSE_SEP if m == "2026-09" else CLOSE_DONE["default"]
        for st, off in zip(steps, offs):
            done = add_bd(me, off) if off is not None else None
            late = (done is None and due < END) or (done is not None and done > due)
            rows.append(dict(month=m, n=st["n"], step=st["name"], owner=st["who"], due=due, done=done, status="open" if done is None else "done", late=late))
    return rows


def generate2(w, R):
    for asof in [month_end(m) for m in months("2026-04", "2026-09")] + [END]:
        rows = register(w, asof if asof == END else asof + dt.timedelta(days=1))
        tot = ["Total", "", "", "", "", sum(r[5] for r in rows), "USD", sum(r[7] for r in rows), sum(r[8] for r in rows), sum(r[9] for r in rows), sum(r[10] for r in rows)]
        arr = add_bd(asof, 3) if asof != END else END
        p = R.path(ym(arr), "commitments", f"commitments_register_{asof}.xlsx")
        write_xlsx(p, {"Register": [["Entity", "Entity code", "Fund", "Fund key", "Manager", "Commitment", "Currency", "Called to date", "Uncalled", "Noticed, not yet recorded", "Distributions to date (since 1 Apr 2026)"]] + rows + [tot]})
        R.add(p, "commitments", ym(arr), f"Commitments register as at {asof}: 8 private funds; uncalled {sum(r[8] for r in rows):,.0f}" + (" (call 7 noticed, not yet recorded)" if asof == END else ""))
    for m in months("2026-04", "2026-10"):
        rows = [a for a in w.allow if a["month"] == m]
        p = R.path(m, "family_allowances", f"allowance_schedule_{m}.xlsx")
        write_xlsx(p, {"Allowances": [["Member", "Relationship", "Amount (USD)", "Due date", "Paying entity"]] + [[a["member"], a["rel"], float(a["amount"]), a["due"].isoformat(), ENT["EG-TRUST"]] for a in rows]})
        R.add(p, "family_allowances", m, f"Family allowance schedule for {m}: 4 members, USD {sum(a['amount'] for a in rows):,.0f}", ["M19b"] if m == "2026-09" else [])
    mess("M19b", "unpaid allowance", "family_allowances/allowance_schedule_2026-09.xlsx", "Ethan Chen's September allowance of USD 5,000 is on the schedule but no payment appears in the Trust bank statement")
    mess("M19", "short-paid distribution", "notices/2026-07-07_A_distribution.pdf", "Fund A distribution notice says USD 275,000.00; the bank credit on 16 July is 262,500.00 (net of withholding, 12,500.00 less)")
    for f in w.fee_invoices:
        L = [(f["vendor"].upper(), 1, 14), "Synthetic vendor - for test purposes only", "---", ("INVOICE", 1, 14), f"Invoice no: {f['id']}", f"Invoice date: {dlong(f['date'])}   Due: {dlong(f['due'])}",
             f"Bill to: {ENT['EG-TRUST']}", "---", f"Service: {'Fund administration' if f['who'] == 'admin' else 'Custody and safekeeping'}, quarter {f['quarter']} 2026",
             f"Fee base (USD): {money(f['base'])}", f"Fee rate per year: {f['rate'] * 100:.2f}%", (f"Amount due: USD {money(f['amount'])}", 1, 12)]
        p = R.path(ym(f["date"]), "invoices", f"{f['date']}_{f['who']}_{f['id']}.pdf"); write_pdf(p, p.name, L)
        R.add(p, "invoices", ym(f["date"]), f"{f['quarter']} {f['who']} fee invoice, USD {money(f['amount'])}", ["M15"] if f["amount"] != f["expected"] else [])
    mess("M15", "fee above schedule", "invoices/2026-10-05_cust_FEE-CUST-Q3.pdf", "Custodian Q3 invoice charges 0.06% a year; the fee schedule says 0.05% (USD 6,180.00 billed against 5,150.00)")
    ref = R.out / "reference"
    docs = {"vendor_contract_orchard_it.pdf": ("ORCHARD IT SERVICES", "Managed IT and security service agreement", "Term: 1 Jan 2026 to 31 Dec 2026, renews automatically for 12 months unless 60 days' notice", "Annual cost: SGD 35,400.00 (SGD 2,950.00 a month)", "2026-12-31"),
            "vendor_contract_quill_research.pdf": ("QUILL RESEARCH SUBSCRIPTIONS", "Research subscription terms", "Term: 1 Dec 2025 to 30 Nov 2026, renews annually", "Annual cost: USD 19,200.00 (USD 4,800.00 a quarter)", "2026-11-30"),
            "vendor_contract_marina_lease.pdf": ("MARINA OFFICE SUITES", "Office lease", "Term: 1 Apr 2024 to 31 Mar 2027", "Annual cost: SGD 222,000.00 (SGD 18,500.00 a month)", "2027-03-31"),
            "vendor_contract_summit_tax.pdf": ("SUMMIT TAX ADVISORY", "Tax advisory engagement letter", "Term: 1 Feb 2026 to 31 Jan 2027, renews annually", "Annual cost: SGD 12,600.00", "2027-01-31")}
    for fn, (v, t, term, cost, ren) in docs.items():
        write_pdf(ref / fn, fn, [(v, 1, 14), "Synthetic vendor - for test purposes only", "---", (t, 1, 13), term, cost, f"Renewal date: {ren}"])
        R.rows.append(dict(path=f"reference/{fn}", kind="vendor_contracts", month="reference", desc=f"Vendor contract: {v.title()}, renews {ren}", mess=[]))
    write_pdf(ref / "loan_agreement_TL-B-01.pdf", "loan", [("HARBOUR BANK (SYNTHETIC)", 1, 14), "---", ("TERM LOAN AGREEMENT TL-B-01", 1, 13), "Borrower: Entity B", "Principal: USD 3,000,000.00", "Interest: 6.10% a year, paid monthly on the 28th",
                                                        "Repayment: USD 100,000.00 on 30 June and 30 September each year, balance at maturity 31 Dec 2029", "Synthetic document for test purposes only"])
    R.rows.append(dict(path="reference/loan_agreement_TL-B-01.pdf", kind="loan_agreement", month="reference", desc="Term loan agreement TL-B-01, Entity B, USD 3,000,000", mess=[]))
    rows = ["---", ("FEE SCHEDULE", 1, 13), f"Fund administration (Harbourline Fund Services): {ADMIN_RATE * 100:.2f}% a year of administered NAV, billed quarterly in arrears",
            f"Custody (Anchorage Custody): {CUST_RATE * 100:.2f}% a year of the liquid book, billed quarterly in arrears"]
    from .world import TERMS, PRIVATE
    rows += [f"Manager {pname(f)}: management fee {TERMS[f][2]}% of commitment per billing, billed in months {' '.join(map(str, TERMS[f][3]))}" for f in PRIVATE]
    write_pdf(ref / "fee_schedule.pdf", "fee schedule", [("EVERGREEN OFFICE", 1, 14), "Fee schedule on file (synthetic)"] + rows)
    R.rows.append(dict(path="reference/fee_schedule.pdf", kind="fee_schedule", month="reference", desc="Fee schedule: administrator, custodian and manager fees", mess=[]))
    # audit request: eight sampled figures from the monthly reports; the last one does not match any report line (planted)
    from .files import report_lines
    items = []
    for i, (m, line) in enumerate(AUDIT_ITEMS, 1):
        issue, lines, tot, sgd = report_lines(w, m)
        val = next((b for a, b, c in lines if a == line), None)
        items.append([i, m, line, float(val) if val is not None else 9500000.0, "yes" if val is not None else "no"])
    p = R.path("2026-09", "audit", "audit_request_2026-09-22.xlsx")
    write_xlsx(p, {"Sample": [["Item", "Report month", "Line", "Figure to trace (USD)", "(generator: traceable)"]] + [r[:4] + [r[4]] for r in items]})
    R.add(p, "audit", "2026-09", "Auditor's sample of eight report figures to trace to source files", ["M20"])
    mess("M20", "untraceable figure", "audit/audit_request_2026-09-22.xlsx", "Item 8 asks for Evergreen Growth I at 9,500,000 for July; no issued report shows that figure (the July report shows the statement value)")
    for m in months("2026-04", "2026-09"):
        rows = [[c["month"], c["n"], c["step"], c["owner"], c["due"].isoformat(), c["done"].isoformat() if c["done"] else "", c["status"]] for c in close_items(w) if c["month"] == m]
        arr = add_bd(month_end(m), 3)
        p = R.path(ym(arr), "close_checklist", f"close_checklist_{m}.csv"); write_csv(p, ["month", "step", "name", "owner", "due_on", "done_on", "status"], rows)
        R.add(p, "close_checklist", ym(arr), f"Month-end report close checklist for {m} (steps of the month-end process)")
    ex = [[b["date"].isoformat(), "cash break", ENT[b["ent"]], b["src"], float(b["diff"]), "over tolerance" if abs(b["diff"]) > 5000 else "inside tolerance"] for b in cash_breaks(w) if b["ccy"] == "USD"]
    ex += [[s["due"], "statement missing", pname(s["fund"]), "manager", "", "never received"] for s in w.stmts if s["status"] == "missing"]
    p = R.path("2026-10", "exception_log", "exception_log_2026-10-13.csv"); write_csv(p, ["date", "kind", "subject", "source", "amount", "note"], sorted(ex))
    R.add(p, "exception_log", "2026-10", "Office exception log up to 13 Oct 2026: cash breaks and missing statements", ["M04"])
    L = [("HARBORLIGHT VENTURES IV - FUND TEASER", 1, 14), "Harborlight Capital Partners (synthetic)", "---", "Strategy: early-stage and growth venture, 25 to 30 companies", "Target fund size: USD 400,000,000", "Minimum commitment: USD 2,000,000",
         "Management fee: 2.0% of commitment; carried interest 20% over an 8% hurdle", "Term: 10 years plus two 1-year extensions", "Liquidity: none until distributions; no redemptions", "First close: 30 November 2026", "Synthetic document for test purposes only"]
    p = R.path("2026-09", "prospects", "fund_teaser_Harborlight_Ventures_IV.pdf"); write_pdf(p, p.name, L)
    R.add(p, "prospects", "2026-09", "Fund teaser: Harborlight Ventures IV, venture, minimum ticket USD 2,000,000")
    qa = [("Number of investment professionals", "12", "14"), ("Assets under management (USD)", "820 million", "910 million"), ("Key person provision", "Two named partners", "Three named partners"),
          ("Valuation frequency", "Quarterly", "Quarterly"), ("Independent administrator", "Harbourline Fund Services", "Harbourline Fund Services"), ("Management fee", "2.0% of commitment", "2.25% of commitment"),
          ("Audit firm", "Brightline Audit", "Brightline Audit"), ("Chief operating officer", "R. Okafor", "T. Lindqvist")]
    for yr, idx, mon in (("2025", 1, "2026-04"), ("2026", 2, "2026-05")):
        p = R.path(mon, "ddq", f"cedarpoint_ddq_{yr}.pdf")
        write_pdf(p, p.name, [("CEDARPOINT VENTURES - DUE DILIGENCE QUESTIONNAIRE " + yr, 1, 13), "Synthetic document for test purposes only", "---"] + [f"{i}. {t[0]}: {t[idx]}" for i, t in enumerate(qa, 1)] + [f"Questionnaire date: {yr}"])
        R.add(p, "ddq", mon, f"Cedarpoint Ventures due diligence questionnaire {yr} (eight answers; five differ between the two years)", ["M21"])
    mess("M21", "questionnaire differences", "ddq/cedarpoint_ddq_2025.pdf vs _2026.pdf", "Five answers differ between the 2025 and 2026 questionnaires: investment professionals (12 vs 14), AUM, key person provision, management fee, chief operating officer")
