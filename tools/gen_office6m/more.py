"""The other 49 cards of packs/family_office/1/use_cases_100.yaml (the ones without priority 1 to 50): the data they need on top of the first 51, and the files that carry it.
build(w, R) makes every table once (X), generate3 writes the files from X, keys2.py computes the answer keys from the same X and the World. Nothing is typed twice:
a number in a key is a calculation on X or w. New files go in new kinds, so no file of the first 51 cards changes (the bank statements gain the planted lines of world.UNMATCHED and GRANTS).
Synthetic data only."""
import datetime as dt
import shutil
from decimal import Decimal as D
from types import SimpleNamespace as NS

from .files import OPS, RECV, dlong, mess, money, month_end, months, mgr, pname
from .world import ACCT, COMMIT_DATE, END, ENT, FAMILY, FUND, GRANT_BUDGET, MGR, PEOPLE, PRIVATE, TERMS, U, add_bd, bdays, d, is_bd, lastbd, next_bd, q2, rng
from .writers import write_csv, write_eml, write_pdf, write_xlsx

TODAY = END
# the file kinds of the other 49 cards: the loader (v3_pack_readers) has no reader for them yet, the cards that use them still need their tables and recipes
NEW_KINDS = ("access_register", "bank_forms", "break_register", "corporate_actions", "custody_statements", "deal_pipeline", "estate_planning", "expense_ledger", "family_access", "fund_documents", "fund_holdings", "glossary", "grant_ledger",
             "grant_requests", "inbox", "income_calendar", "insurance_schedule", "kyc_register", "load_log", "manager_news", "manager_outlook", "market_data", "new_feed", "office_budget", "onboarding", "payment_schedule", "payroll_drafts",
             "property_valuations", "settlement_status", "sops", "target_allocation", "tax_calendar", "tax_lots", "tax_notices", "title_deeds", "trust_deed")


def eq(w, amt, ccy): return D(amt) if ccy == "USD" else q2(D(amt) / w.fx[END])  # USD equivalent at the 13 Oct fixing


def bd_between(a, b): return len(bdays(a + dt.timedelta(days=1), b)) if b > a else 0


# ---------------------------------------------------------------------------------------------------- standing facts (inputs, not answers)
TAX = [("TX-01", "EG-HOLD", "Estimated chargeable income (ECI) filing", "2026-11-30", "Summit Tax Advisory", None, "SGD", "not started"),
       ("TX-02", "EG-HOLD", "Corporate income tax return and payment", "2026-11-30", "Summit Tax Advisory", 41200, "SGD", "draft with adviser"),
       ("TX-03", "EG-TRUST", "Trust income tax return and payment", "2026-12-15", "Summit Tax Advisory", 18400, "USD", "not started"),
       ("TX-04", "EG-B", "Corporate income tax return and payment", "2026-09-30", "Summit Tax Advisory", 22600, "USD", "not filed"),
       ("TX-05", "EG-HOLD", "Foreign tax credit claim for the Fund A withholding", "2027-01-15", "Helen Foo", None, "USD", "not started"),
       ("TX-06", "EG-HOLD", "W-8BEN-E renewal for the administrator", "2026-12-31", "Helen Foo", None, "USD", "not started")]
TAX_PAY_ON = {"TX-04": "2026-10-20"}  # the overdue one is paid as soon as filed
TAX_RATES = {"EG-HOLD": (D("0.17"), D("0")), "EG-TRUST": (D("0.12"), D("0.15")), "EG-B": (D("0.17"), D("0"))}  # income rate, realised-gain rate
# real assets: id, name, type, entity, currency, holder named on the title, [(appraisal date, value, appraiser)]
ASSETS = [("RA-01", "Bayview Residence", "residential property", "EG-HOLD", "SGD", "Evergreen Holdings", [("2024-11-20", 9100000, "Crestline Valuers"), ("2025-11-18", 9600000, "Crestline Valuers")]),
          ("RA-02", "Hillcrest House", "residential property", "EG-TRUST", "SGD", "Evergreen Family Trust", [("2026-03-02", 6400000, "Crestline Valuers")]),
          ("RA-03", "Fine art collection", "art", "EG-HOLD", "USD", "Evergreen Holdings", [("2024-08-20", 2400000, "Meridian Art Appraisals")]),
          ("RA-04", "Coastal Land Parcel Lot 14", "land", "EG-B", "USD", "Lin Chen", [("2026-06-10", 1800000, "Crestline Valuers")]),
          ("RA-05", "Wine cellar collection", "wine", "EG-TRUST", "USD", "Evergreen Family Trust", [("2025-09-30", 650000, "Meridian Art Appraisals")]),
          ("RA-06", "Motor yacht Evergreen Star", "vessel", "EG-HOLD", "USD", "Evergreen Holdings", [("2025-10-25", 1200000, "Harbour Marine Surveyors")])]
INSURED = {"POL-HOME-01": ("RA-01", 8500000), "POL-ART-02": ("RA-03", 2000000), "POL-LIAB-03": (None, 10000000), "POL-CYB-04": (None, 1000000)}  # policy: (asset, sum insured in its currency)
CUST_BREAKS = {"BSU": (1250, "Scrip dividend credited on 29 Sep, not yet advised to the administrator"), "RWP": (-400, "Transfer-out to a family brokerage account on 30 Sep, instruction not copied to the administrator")}
SECOND_NOISE = {"KFT": D("0.019"), "KFB30": D("-0.008")}  # second-source price above (+) or below (-) the administrator price: the planted gaps
PRICE_TOL = D("0.005")
FAILS = [("BR2-20261002-001", "2026-10-02", "2026-10-06", "LKH", "buy", 5000, "Synthetic Broker Two", "seller short delivery"),
         ("BR2-20261007-002", "2026-10-07", "2026-10-09", "EBG", "buy", 10000, "Synthetic Broker Two", "settlement instruction mismatch")]
BREAKS = [("BRK-001", "cash break", "EG-B", "Entity B USD 8 Oct, administrator 12,400 above the bank", "2026-10-08", "Grace Ong"), ("BRK-002", "cash break", "EG-TRUST", "Trust USD 8 Oct, desk 1,800 below the bank", "2026-10-08", "Grace Ong"),
          ("BRK-003", "cash break", "EG-TRUST", "Trust USD 17 Jun, administrator books the 6,200 fee a day late", "2026-06-17", "Helen Foo"),
          ("BRK-004", "cash break", "EG-B", "Entity B USD, Tidewater July statement never received, Tidewater leg cannot be reconciled", "2026-08-07", "Helen Foo"),
          ("BRK-005", "confirmation break", "EG-HOLD", "FX conversion FXS-20260602-HOLD has no bank confirmation", "2026-06-05", "Sam Lee"),
          ("BRK-006", "statement break", "EG-B", "Cedarpoint Opportunities II statement as at 30 Jun never received", "2026-07-15", "Grace Ong")]
HOLDINGS = {"A": [("Helix Cloud Systems", "Technology", 12), ("Harborview Semiconductor", "Technology", 7), ("Quarry Logistics", "Industrials", 9), ("Mistral Health Devices", "Health care", 8), ("Pennant Retail Group", "Consumer", 6), ("Other holdings", "Mixed", 58)],
            "B": [("Redstone Mortgage Trust", "Real estate credit", 14), ("Beacon Energy Credit", "Energy", 11), ("Alder Freight Loans", "Industrials", 9), ("Other holdings", "Mixed", 66)],
            "C": [("Helix Cloud Systems", "Technology", 15), ("Harborview Semiconductor", "Technology", 8), ("Lumen Genomics", "Health care", 10), ("Vantage Payments", "Financials", 9), ("Other holdings", "Mixed", 58)],
            "D": [("Pinecrest Foods", "Consumer", 13), ("Quarry Logistics", "Industrials", 10), ("Other holdings", "Mixed", 77)],
            "E": [("Saltmarsh Grid Holdings", "Utilities", 22), ("Tidal Pipeline Partners", "Energy", 14), ("Other holdings", "Mixed", 64)],
            "F": [("Helix Cloud Systems", "Technology", 9), ("Lumen Genomics", "Health care", 7), ("Pennant Retail Group", "Consumer", 6), ("Other holdings", "Mixed", 78)],
            "G": [("Alder Freight Loans", "Industrials", 12), ("Redstone Mortgage Trust", "Real estate credit", 8), ("Other holdings", "Mixed", 80)],
            "K": [("Saltmarsh Grid Holdings", "Utilities", 18), ("Solar Fields Ltd", "Energy", 16), ("Other holdings", "Mixed", 66)]}
PAYOUT = {"A": (3.0, 2.0, 2.5, 3.0), "B": (1.5, 1.5, 1.5, 1.5), "C": (0.0, 0.0, 1.0, 2.0), "D": (2.0, 0.0, 3.0, 0.0), "E": (1.0, 1.0, 1.5, 1.5), "F": (0.0, 1.0, 1.0, 1.0), "G": (1.2, 1.2, 1.2, 1.2), "K": (0.5, 0.5, 0.5, 0.5)}
PAYOUT_Q = ("2026-12-31", "2027-03-31", "2027-06-30", "2027-09-30")
# hedge fund terms: dealing (monthly or quarterly), notice calendar days, lock-up end, payout lag (days after dealing date), holdback percent until the audit
HF_TERMS = {"H1": dict(dealing="monthly", notice=45, lockup_end="2025-03-01", payout=14, holdback=5, subscribed="2024-03-01"), "H2": dict(dealing="quarterly", notice=60, lockup_end="2026-12-31", payout=30, holdback=5, subscribed="2025-12-31")}
TARGET_ALLOC = {"listed_equity": 65, "bond": 30, "convertible": 5}  # proposed interim targets of EG-LIQUID, % of the book
DEALS = [("DL-01", "Harborlight Ventures IV", "Harborlight Capital Partners", "venture", 2000000, "Teaser reviewed", "2026-09-22", "Sofia Reyes"), ("DL-02", "Marlow Infrastructure Partners III", "Marlow Capital", "infrastructure", 3000000, "Diligence", "2026-07-28", "Sofia Reyes"),
         ("DL-03", "Pelican Credit Opportunities II", "Pelican Credit", "private credit", 2500000, "Diligence", "2026-09-30", "Sofia Reyes"), ("DL-04", "Ashgrove Growth Equity V", "Ashgrove Partners", "private equity", 4000000, "Sourced", "2026-06-15", "Raj Patel"),
         ("DL-05", "Nimbus Secondaries I", "Nimbus Capital", "secondaries", 1500000, "Investment committee", "2026-10-08", "Raj Patel")]
STAGE_LIMIT_DAYS = 60
DRAFT = dict(month="2026-10", pay_date="2026-10-23", raise_name="Grace Ong", raise_pct=20, extra=("Jun Tan (contractor)", "Contractor", 6500))
BUDGET = {"Staff": 1200000, "Premises": 180000, "Technology": 24000, "Professional fees": 85000, "Fund and custody fees": 60000, "Insurance": 80000, "Property running costs": 80000, "Research": 19200,
          "Banking": 6000, "Courier and other": 1500, "Debt service": 600000, "Family allowances": 276000, "Grants": 300000}  # annual budget in USD, set by the principal in April
APPROVERS = [("Priya Nair", 10000), ("Grace Ong", 50000), ("Daniel Foo", 500000), ("Raj Patel", 5000000)]  # person, limit in USD
APPROVER_PLANTED = {"LL-2026-0708": "Priya Nair", "BAL-2026-051": "Priya Nair"}
SPEND_TYPES = {"vendor_payment", "payroll", "payroll_tax", "property", "insurance", "allowance", "loan_service", "fee", "bank_fee", "grant"}
TRUST_DEED = dict(shares={"Lin Chen": 40, "Maya Chen": 25, "Ethan Chen": 27, "Wen Chen": 8}, payout_cap=70, successor="Mei Chen", year_start="2026-04-01")
ESTATE = dict(exemption=5000000, rate=D("0.15"), months_to_pay=6)
DEED_NOTE = "Allowances paid to beneficiaries count as distributions."
GRANT_POLICY = dict(min_registration_months=24)
GRANT_REQUEST = dict(id="REQ-2026-06", charity="Seabird Sanctuary Trust", amount=50000, registered="2025-03-01", purpose="Wetland wardens", contact="Anneke Lowe")
ROLE_ACCESS = {"Chief Investment Officer": [("OMS", "approve trades"), ("Administrator portal", "view"), ("Harbor", "reader")], "Head of Finance": [("Harbour Bank portal", "release payments"), ("Tidewater portal", "release payments"), ("Administrator portal", "view"), ("Harbor", "approver")],
               "Head of Data": [("Administrator portal", "view"), ("Custody portal", "view"), ("Shared drive", "edit"), ("Harbor", "admin")], "Principal": [("Harbor", "reader"), ("Harbour Bank portal", "view")],
               "Investment Analyst": [("OMS", "view"), ("Shared drive", "edit"), ("Harbor", "analyst")], "Operations Lead": [("Harbour Bank portal", "initiate payments"), ("Tidewater portal", "initiate payments"), ("Custody portal", "view"), ("OMS", "trade entry")],
               "Fund Accountant": [("Administrator portal", "view"), ("Custody portal", "view"), ("Shared drive", "edit")], "Risk and Compliance Officer": [("OMS", "view"), ("Harbor", "reader"), ("Shared drive", "view")],
               "Office and HR Manager": [("Shared drive", "edit"), ("Harbor", "reader")], "Operations Clerk": [("Harbour Bank portal", "initiate payments"), ("OMS", "trade entry"), ("Shared drive", "edit")]}
ACCESS_NO_APPROVER = [("Sam Lee", "OMS"), ("Wei Tan", "Harbour Bank portal")]  # planted: granted, nobody approved it
ACCESS_UNUSED = {("Sofia Reyes", "OMS"): "2026-05-20", ("Priya Nair", "Shared drive"): "2026-06-03", ("Anita Rao", "Custody portal"): "2026-04-28"}  # planted: last use more than 90 days ago
FAMILY_POLICY = {"Lin Chen": {"EG-HOLD": "full", "EG-TRUST": "full", "EG-B": "none"}, "Maya Chen": {"EG-HOLD": "none", "EG-TRUST": "summary", "EG-B": "none"},
                 "Ethan Chen": {"EG-HOLD": "none", "EG-TRUST": "summary", "EG-B": "none"}, "Wen Chen": {"EG-HOLD": "none", "EG-TRUST": "summary", "EG-B": "none"}}
FAMILY_GRANTED = {"Lin Chen": {"EG-HOLD": "full", "EG-TRUST": "full"}, "Maya Chen": {"EG-TRUST": "summary"}, "Ethan Chen": {"EG-TRUST": "summary"}, "Wen Chen": {"EG-TRUST": "summary", "EG-B": "full"}}  # planted: Wen Chen sees Entity B in full
FAMILY_REQUEST = dict(member="Maya Chen", entity="EG-HOLD", level="summary", date="2026-10-09")
ONBOARD = [("Contacts and relationship owner", "complete", "Harborlight IR contact and legal contact on file"), ("KYC pack (4 documents)", "complete", "certificate, licence, beneficial owners, sanctions screening"),
           ("Subscription document", "complete", "draft received, unsigned"), ("Bank details confirmed by call-back", "missing", "no standing instruction on file"), ("Statement schedule (frequency, due day, contact)", "missing", "not agreed")]
SIGNING = dict(min_signatories=2, must_include="Head of Finance", add_principal_over=500000)
ACCOUNT_FORM = dict(entity="EG-TRUST", bank="Tidewater Commercial Bank (synthetic)", currency="EUR", purpose="Euro receipts from Bluewater Capital", signatories=["Raj Patel (Chief Investment Officer)", "Grace Ong (Operations Lead)"])
ACCOUNT_STEPS = [("Opening form completed", True), ("KYC of the entity attached", True), ("Board and trustee resolution attached", True), ("Specimen signatures received", True), ("Signatories meet the signing policy", None), ("Head of Finance approval", False)]
KYC_DOCS = [("EG-HOLD", "Harbour Bank (synthetic)", "Director identity document, Raj Patel", "2021-11-15", "2026-11-14"), ("EG-HOLD", "Harbour Bank (synthetic)", "Certificate of incumbency", "2025-05-02", "2027-05-01"),
            ("EG-HOLD", "Tidewater Commercial Bank (synthetic)", "Certificate of incumbency", "2025-12-02", "2026-12-02"), ("EG-HOLD", "Cedarpoint Ventures", "Limited partner KYC refresh", "2025-01-05", "2027-01-05"),
            ("EG-HOLD", "Northgate Partners", "Limited partner KYC refresh", "2025-08-20", "2027-08-19"), ("EG-TRUST", "Harbour Bank (synthetic)", "Trust deed certified copy", "2024-06-30", "2027-06-29"),
            ("EG-TRUST", "Tidewater Commercial Bank (synthetic)", "Trustee identity document, Mei Chen", "2022-03-18", "2027-03-17"), ("EG-TRUST", "Kestrel Ridge Advisors", "Investor KYC refresh", "2025-11-10", "2027-11-09"),
            ("EG-B", "Harbour Bank (synthetic)", "Director identity document, Daniel Foo", "2021-09-13", "2026-09-12"), ("EG-B", "Tidewater Commercial Bank (synthetic)", "Certificate of good standing", "2026-04-20", "2027-04-19"),
            ("EG-B", "Saltmarsh Real Assets", "Limited partner KYC refresh", "2025-10-01", "2027-09-30"), ("EG-B", "Bluewater Capital", "Limited partner KYC refresh", "2026-01-12", "2028-01-11")]
SOPS = [("month-end-report", "Month-end investment report", "Mei Chen", "2026-03-12", 1, [("Collect the exports", "Mei Chen", 90, "yes"), ("Check cash against the administrator", "Mei Chen", 60, "yes"), ("Collect manager statements", "Mei Chen", 120, "yes"),
                                                                                  ("Convert to SGD", "Raj Patel", 30, "yes"), ("Review and approve the report", "Raj Patel", 45, "no"), ("Read the report", "Daniel Foo", 15, "no")]),
        ("capital-call-payment", "Capital call payment", "Helen Foo", "2025-11-04", 2, [("Log the notice", "Sam Lee", 20, "yes"), ("Check against the commitment", "Helen Foo", 25, "yes"), ("Call back on changed bank details", "Helen Foo", 30, "yes"), ("Approve over 500,000", "Daniel Foo", 10, "no"), ("Release payment", "Grace Ong", 15, "no")]),
        ("vendor-payment-run", "Vendor payment run", "Grace Ong", "2025-06-20", 2, [("Match invoices to contracts and the fee schedule", "Helen Foo", 60, "yes"), ("Check duplicates and changed bank details", "Helen Foo", 45, "yes"), ("Approve", "Daniel Foo", 15, "no"), ("Release", "Grace Ong", 20, "no")]),
        ("bank-statement-chase", "Bank statement chase", "Helen Foo", "2026-05-09", 4, [("List expected statements", "Sam Lee", 20, "yes"), ("Chase late or missing ones", "Helen Foo", 40, "yes"), ("Log the receipt", "Sam Lee", 10, "yes")]),
        ("payroll-release", "Payroll release", "Priya Nair", "2025-09-30", 1, [("Prepare pay file", "Priya Nair", 60, "yes"), ("Check against the staff register", "Priya Nair", 30, "yes"), ("Approve and release", "Daniel Foo", 15, "no")]),
        ("access-review", "Quarterly access review", "Priya Nair", "2026-07-14", 0.33, [("Export access list", "Anita Rao", 30, "yes"), ("Review unused and unapproved access", "Priya Nair", 90, "yes"), ("Remove access", "Anita Rao", 30, "yes")]),
        ("new-bank-account", "Open or change a bank account", "Daniel Foo", "2024-12-01", 0.1, [("Complete the bank form", "Grace Ong", 90, "yes"), ("Check signatories against the signing policy", "Daniel Foo", 30, "yes"), ("File the approval", "Helen Foo", 15, "yes")]),
        ("insurance-renewal", "Insurance renewal", "Priya Nair", "2026-02-03", 0.33, [("Read renewal notice", "Priya Nair", 20, "yes"), ("Compare with assets and last year", "Priya Nair", 60, "yes"), ("Approve premium", "Daniel Foo", 10, "no")])]
SOP_FAIL_MIN = 45
GLOSSARY = [("capital call", "drawdown; call notice", "A manager's request that an investor pay part of its commitment"), ("uncalled commitment", "unfunded commitment; dry powder", "Commitment not yet called"), ("capital account", "capital account statement", "An investor's balance in a fund"),
            ("net asset value", "NAV", "Value of a fund or portfolio after liabilities"), ("distribution", "payout", "Cash returned by a fund"), ("management fee", "mgmt fee", "Fee a manager charges on commitment or value"), ("single name limit", "concentration limit", "Maximum share of one issuer"),
            ("cash buffer", "minimum cash", "Cash kept back per entity"), ("break", "cash break; reconciliation break", "A difference between two sources"), ("amended statement", "restated statement", "A statement that replaces an earlier one"),
            ("estimate", "estimated statement", "A manager's early value, to be replaced by the final"), ("fixing", "WMR fixing; WMR 4pm", "The reference exchange rate of the day"), ("administrator", "fund administrator", "Firm that keeps the official records"),
            ("custodian", "custody bank", "Firm that holds the securities"), ("call-back", "callback", "A phone check on a known number before paying changed details"), ("tolerance", "", "Largest difference accepted"),
            ("benchmark", "reference index", "The index a portfolio is measured against"), ("look-through", "", "Exposure seen through a fund to what it owns"), ("hedge", "", "A position that offsets a currency or market exposure"), ("lock-up", "gate", "Period in which money cannot be redeemed")]
GLOSSARY_PROPOSED = [("email 2026-10-06 (Grace Ong)", "dry powder"), ("email 2026-10-06 (Grace Ong)", "side letter"), ("meeting note 2026-10-08", "capital account"), ("meeting note 2026-10-08", "stub period"), ("meeting note 2026-10-08", "side letter")]
FEED = dict(name="Pinnacle Trust Company (synthetic)", date="2026-10-12", columns=[("Acct", "account", True), ("SecRef", "security_id", True), ("Description", "security_name", True), ("Qty", "quantity", True), ("Px", "price", True),
                                                                           ("Value", "market_value or book_value", False), ("Cost", "cost", True), ("Ccy", "currency", True), ("Dt", "valuation date or trade date or settle date", False), ("Status", "position status", True)])
LOAD_KINDS = ["bank_statements", "administrator_cash", "administrator_nav", "custodian_transactions", "custodian_positions", "manager_statements", "notices", "invoices", "trading_export", "fx_confirmations", "commitments", "investment_reports"]
LATE_TAGS, FIX_TAGS, ADD_TAGS = {"M01", "M02a"}, {"M18", "M11a", "M11b", "M07", "M06", "M05b"}, {"M04", "M16", "M15", "M19", "M08", "M13"}
PERSONNEL = [("MGR-SALTMARSH", "2026-08-18", "Head of Infrastructure resigns", "Priya Menon, our Head of Infrastructure, has resigned; her last day is 30 September."), ("MGR-NORTHGATE", "2026-09-09", "Second named key person added", "Marcus Hale joins Elena Marsh as a named key person from 1 October.")]


def months_iter(a, b):
    out, y, m = [], a.year, a.month
    while (y, m) <= (b.year, b.month):
        out.append((y, m)); y, m = y + (m == 12), m % 12 + 1
    return out


# ---------------------------------------------------------------------------------------------------- income and corporate actions
def income_events(w, start, end):
    """Coupons and dividends with a pay date in (start, end], on the quantity held on 13 Oct: the rule the World books with (world._events), carried forward."""
    cpn = {"CRB31": (D("0.051"), (3, 9), 15), "HTN29": (D("0.039"), (6, 12), 30), "KFB30": (D("0.046"), (1, 7), 20)}
    out = []
    for y in (2026, 2027, 2028):
        for i, (k, s) in enumerate(w.sec.items()):
            qty = w.qty[END][k]
            if k in cpn:
                for mth in cpn[k][1]:
                    x = next_bd(dt.date(y, mth, cpn[k][2]))
                    if start < x <= end: out.append(dict(pay=x, sec=k, kind="coupon", rate=cpn[k][0], per_unit=None, qty=qty, amount=q2(cpn[k][0] / 2 * qty)))
            elif k != "PRC29":
                for mth in (4, 7, 10):
                    x = next_bd(dt.date(y, mth, 10 + (i % 3) * 5)); dps = (w.px[k][END] * D("0.0045")).quantize(D("0.0001"))
                    if start < x <= end: out.append(dict(pay=x, sec=k, kind="dividend", rate=None, per_unit=dps, qty=qty, amount=q2(qty * dps)))
    return sorted(out, key=lambda e: (e["pay"], e["sec"]))


# ---------------------------------------------------------------------------------------------------- scheduled payments (the ladder, the idle cash, the forecast)
def pay_items(w, end):
    """Money the office will pay after 13 Oct and up to end: (ref, entity, payee, due, amount, currency, status, basis). Status: approved (a document is in hand), scheduled (a standing order), expected
    (the usual bill, not yet received), held (blocked by a rule). Calls are not here: they come from the notices."""
    out = []
    def add(ref, ent, payee, due, amt, ccy, status, basis):
        due = next_bd(due)
        if END < due <= end: out.append(dict(ref=ref, ent=ent, payee=payee, due=due, amount=D(amt), ccy=ccy, status=status, basis=basis))
    pr = w.payroll[-1]; bal = w.loan[-1]["close"]
    for y, m in months_iter(END, end):
        day = dt.date(y, m, 25)
        while not is_bd(day): day -= dt.timedelta(days=1)
        add(f"PAY-{y}{m:02d}", "EG-HOLD", "Evergreen Holdings payroll", day, pr["net"], "SGD", "scheduled", "net pay run, last month's run")
        add(f"CPF-{y}{m:02d}", "EG-HOLD", "Central Provident Fund (synthetic)", dt.date(y, m, 14), pr["cpf"], "SGD", "scheduled", "CPF of the month before")
        add(f"RENT-{y}{m:02d}", "EG-HOLD", "Marina Office Suites", dt.date(y, m, 1), D(18500), "SGD", "scheduled", "lease, 18,500 a month")
        add(f"IT-{y}{m:02d}", "EG-HOLD", "Orchard IT Services", dt.date(y, m, 3) + dt.timedelta(days=30), D(2950), "SGD", "expected", "contract, 2,950 a month, invoice on the 3rd, 30 days")
        add(f"ALW-{y}{m:02d}", "EG-TRUST", "Family allowances", dt.date(y, m, 1), sum((D(a) for n, r, a in FAMILY), D(0)), "USD", "scheduled", "four members, first business day")
        add(f"LOAN-{y}{m:02d}", "EG-B", "Harbour Bank (synthetic)", dt.date(y, m, 28), q2(bal * D("0.0610") / 12) + (D(100000) if m in (6, 9) else D(0)), "USD", "scheduled", "TL-B-01 interest and principal")
        if m in (6, 9) and y > 2026: bal -= D(100000)
    for pn, ent, ccy in (("Bayview Residence", "EG-HOLD", "SGD"), ("Hillcrest House", "EG-TRUST", "SGD")):
        mine = [p for p in w.props if p["prop"] == pn]; util = q2(sum((p["items"][1][1] for p in mine), D(0)) / len(mine)); mg = mine[0]["items"][0][1]; tx = next(i[1] for p in mine for i in p["items"] if i[0].startswith("Property tax"))
        for y, m in months_iter(END, end):
            st = "approved" if (y, m) == (2026, 10) else "expected"
            amt = next(p["total"] for p in mine if p["month"] == "2026-10") if (y, m) == (2026, 10) else mg + util + (tx if m in (1, 4, 7, 10) else D(0))
            add(f"PB-{pn.split()[0][:2].upper()}-{y}{m:02d}", ent, pn + " managing agent", dt.date(y, m, 26), amt, ccy, st, "monthly bill" + (" with the quarter's property tax" if m in (1, 4, 7, 10) else ""))
    for p in w.policies:
        nxt = p["renewal"] if p["renewal"] > END else p["renewal"].replace(year=p["renewal"].year + 1)
        add(f"INS-{p['id']}", "EG-HOLD", "SafeHarbour Insurance Brokers (synthetic)", nxt, p["premium"], p["ccy"], "approved" if p["notice"] <= END < p["renewal"] else "expected", "renewal premium" + (", notice in hand" if p["notice"] <= END < p["renewal"] else ""))
    for f in w.fee_invoices:
        if f["due"] > END: add(f["id"], "EG-TRUST", f["vendor"], f["due"], f["amount"], "USD", "held" if f["amount"] != f["expected"] else "approved", "invoice above its fee schedule" if f["amount"] != f["expected"] else "quarterly fee invoice")
    for y, m in [(2027, 1), (2027, 4), (2027, 7)]:
        for f in w.fee_invoices[-2:]:
            add(f"FEE-{f['who'].upper()}-{y}-{m:02d}", "EG-TRUST", f["vendor"], dt.date(y, m, 5) + dt.timedelta(days=14), f["expected"], "USD", "expected", "quarterly fee at the schedule rate")
    add("QRS-2026-RENEW", "EG-HOLD", "Quill Research Subscriptions", dt.date(2026, 11, 30), D(19200), "USD", "expected", "annual renewal of the research subscription")
    for t in TAX:
        if t[5]: add(f"TAXPAY-{t[0]}", t[1], "Tax authority (synthetic)", d(TAX_PAY_ON.get(t[0], t[3])), t[5], t[6], "scheduled", t[2])
    return sorted(out, key=lambda r: (r["due"], r["ref"]))


# ---------------------------------------------------------------------------------------------------- tax lots (FIFO) from the trades
def lot_state(w, x):
    """Open lots after every trade settled by x, and the realised gains: opening lots are generated for the position held on 31 Mar."""
    r = rng("lots"); lots, realised = {}, []
    for k, s in w.sec.items():
        q = w.qty[d("2026-03-31")][k]; p0 = w.px[k][d("2026-03-31")]; unit = D(1000) if q >= 10000 else D(100)
        a = (q * D("0.5") // unit) * unit; b = (q * D("0.3") // unit) * unit; parts = [a, b, q - a - b]
        ds = sorted(dt.date(2021 + r.randrange(5), r.randrange(1, 13), 15) for _ in parts)
        lots[k] = []
        for n, (qq, dd) in enumerate(zip(parts, ds), 1):
            if s["instrument_type"] == "bond": c = D(str(round(r.uniform(0.95, 1.04), 4)))
            else: c = (p0 * D(str(round(r.uniform(0.55, 1.25), 3)))).quantize(D("0.01"))
            lots[k].append(dict(id=f"LOT-{k}-{n}", sec=k, acq=dd, qty=qq, unit=c))
    for t in sorted(w.trades, key=lambda t: (t["trade"], t["id"])):
        if t["settle"] > x: continue
        L = lots[t["sec"]]
        if t["side"] == "buy": L.append(dict(id=f"LOT-{t['sec']}-{t['id'][2:]}", sec=t["sec"], acq=t["trade"], qty=t["qty"], unit=t["price"]))
        else:
            need = t["qty"]
            for l in L:
                if need <= 0: break
                take = min(l["qty"], need)
                if take: realised.append(dict(trade=t["id"], date=t["settle"], sec=t["sec"], lot=l["id"], qty=take, proceeds=q2(take * t["price"]), cost=q2(take * l["unit"]), gain=q2(take * (t["price"] - l["unit"])))); l["qty"] -= take; need -= take
            assert need <= 0, t["id"]
    return [l for k in lots for l in lots[k] if l["qty"] > 0], realised


# ---------------------------------------------------------------------------------------------------- build every table
def build(w, R):
    X = NS(); X.w = w
    X.sched = pay_items(w, dt.date(2027, 9, 30))
    X.tax = TAX
    X.income = income_events(w, END, dt.date(2027, 10, 13))
    dv = [e for e in X.income if e["kind"] == "dividend" and e["pay"] <= END + dt.timedelta(days=14)]
    X.tender = dict(sec="TWE", offer=D("31.50"), notice="2026-10-08", deadline="2026-10-22", pays="2026-11-05", qty_held=w.qty[END]["TWE"], px=w.px["TWE"][END])
    X.caction_notices = [dict(e, ex=add_bd(e["pay"], -5), notice=add_bd(e["pay"], -9)) for e in dv] + [dict(e, ex=add_bd(e["pay"], -5), notice=d("2026-10-02")) for e in X.income if e["sec"] == "HTN29" and e["pay"] > END][:1]
    # custody statement and second source
    sep = d("2026-09-30"); X.custody = {k: w.qty[sep][k] + (D(CUST_BREAKS[k][0]) if k in CUST_BREAKS else D(0)) for k in w.sec}
    r = rng("second"); X.second = {}
    for day in (sep, END):
        for k in w.sec:
            n = SECOND_NOISE[k] if (k in SECOND_NOISE and day == sep) else D(str(round(r.uniform(-0.001, 0.001) if w.sec[k]["instrument_type"] != "bond" else r.uniform(-0.0005, 0.0005), 5)))
            X.second[(day, k)] = (w.px[k][day] * (1 + n)).quantize(D(10) ** w.px[k][day].as_tuple().exponent)
    X.fails = [dict(id=i, trade=d(td), settle=d(sd), sec=k, side=sd_, qty=D(q), price=w.px[k][d(td)], amount=q2(D(q) * w.px[k][d(td)]), cpty=cp, reason=why) for i, td, sd, k, sd_, q, cp, why in FAILS]
    X.breaks = [dict(id=i, type=t, ent=e, subject=s, detected=d(dd), owner=o, amount=None) for i, t, e, s, dd, o in BREAKS]
    X.inbox = [("scan_0412.pdf", "a copy of the Saltmarsh Renewables I distribution notice of 10 Sep", "notices", "duplicate of a notice already loaded"), ("account_extract.xlsx", "Tidewater Trust USD bank statement, 1 to 13 Oct", "bank_statements", "duplicate of the statement already loaded"),
               ("INV-OIT-2610.pdf", "Orchard IT Services invoice for October, SGD 2,950.00", "invoices", "new, to the payment run"), ("IMG_2210.pdf", "a restaurant receipt, not office business", None, "refuse and return to the sender"),
               ("data_export.xlsx", "a sheet of four columns with no source, header or date", None, "hold and ask the sender what it is")]
    # real assets
    X.assets = [dict(id=a[0], name=a[1], type=a[2], ent=a[3], ccy=a[4], title=a[5], appraisals=[dict(date=d(x), value=D(v), by=b) for x, v, b in a[6]]) for a in ASSETS]
    for a in X.assets: a["latest"] = max(a["appraisals"], key=lambda z: z["date"])
    # lots
    X.lots30, _ = lot_state(w, sep); _, X.realised = lot_state(w, END)
    # fund documents
    X.deals = [dict(id=i, name=n, sponsor=s, cls=c, ticket=D(t), stage=g, entered=d(e), owner=o) for i, n, s, c, t, g, e, o in DEALS]
    X.staff = [(n, t, D(g)) for n, t, g in PEOPLE if g]
    X.draft = [(n, t, g * (1 + D(DRAFT["raise_pct"]) / 100) if n == DRAFT["raise_name"] else g) for n, t, g in X.staff] + [(DRAFT["extra"][0], DRAFT["extra"][1], D(DRAFT["extra"][2]))]
    # expense ledger from the bank lines
    led, vmap = [], {i["no"]: i for i in w.invoices}
    cat = {"rent": "Premises", "it": "Technology", "research": "Research", "legal": "Professional fees", "audit": "Professional fees", "tax": "Professional fees", "courier": "Courier and other"}
    for t in w.tx:
        if t["typ"] not in SPEND_TYPES or not (d("2026-04-01") <= t["date"] <= d("2026-09-30")): continue
        a = ACCT[t["acct"]]; usd = eq(w, -t["amt"], a["ccy"]) if a["ccy"] == "USD" else q2(-t["amt"] / w.fx[t["date"]])
        if t["typ"] == "vendor_payment":
            inv = next((i for i in w.invoices if t["ref"] == "VP-" + i["no"]), None); c = cat[inv["cat"]] if inv else "Fund and custody fees"; no = inv["no"] if inv else t["ref"][3:]
        else:
            c = {"payroll": "Staff", "payroll_tax": "Staff", "property": "Property running costs", "insurance": "Insurance", "allowance": "Family allowances", "loan_service": "Debt service", "fee": "Fund and custody fees", "bank_fee": "Banking", "grant": "Grants"}[t["typ"]]; no = t["ref"]
        if t["typ"] == "loan_service": usd = eq(w, -t["amt"], "USD")
        led.append(dict(date=t["date"], cat=c, payee=t["cpty"], ent=a["ent"], ccy=a["ccy"], amount=-t["amt"], usd=usd, ref=no, bank_ref=t["ref"]))
    for l in led:
        need = "Daniel Foo" if l["cat"] in ("Staff", "Debt service", "Fund and custody fees") else next((p for p, lim in APPROVERS if l["usd"] <= lim), APPROVERS[-1][0])
        l["approver"] = APPROVER_PLANTED.get(l["ref"], need)
    X.ledger = led
    # SOPs, glossary
    X.sops = [dict(id=i, name=n, owner=o, reviewed=d(rv), runs=D(str(runs)), steps=[dict(step=s, owner=ow, minutes=m, manual=man == "yes") for s, ow, m, man in st]) for i, n, o, rv, runs, st in SOPS]
    X.glossary = GLOSSARY
    # access
    people = [(n, t) for n, t, g in PEOPLE] + [("J. Ng", "Investment Analyst"), ("Wei Tan", "Investment Analyst")]
    ra = rng("access"); grants = []
    for n, t in people:
        for sys, perm in (ROLE_ACCESS[t] if n != "J. Ng" else [("OMS", "view"), ("Shared drive", "edit"), ("Harbor", "analyst")]) + ([("Harbour Bank portal", "initiate payments")] if n == "Wei Tan" else []):
            used = d(ACCESS_UNUSED[(n, sys)]) if (n, sys) in ACCESS_UNUSED else (d("2026-09-28") if n == "J. Ng" else d("2026-08-01") + dt.timedelta(days=ra.randrange(0, 72)))
            granted = d("2026-10-05") if n == "Wei Tan" else d("2024-01-15") + dt.timedelta(days=ra.randrange(0, 700))
            appr = "" if (n, sys) in ACCESS_NO_APPROVER else ("Daniel Foo" if "Bank" in sys or "Tidewater" in sys else "Grace Ong")
            if n == "Wei Tan": used = d("2026-10-12")
            grants.append(dict(id=f"AG-{len(grants) + 1:03d}", person=n, title=t, system=sys, permission=perm, granted=granted, approver=appr, last_used=used))
    X.access = grants
    X.leaver = dict(name="J. Ng", left="2026-09-30"); X.joiner = dict(name="Wei Tan", start="2026-10-05", requested=["Harbor", "OMS (view)", "Shared drive"])
    X.family_requests = FAMILY_REQUEST
    X.load_log = build_load_log(R)
    return X


def build_load_log(R):
    rows = []
    for r in R.rows:
        if r["kind"] not in LOAD_KINDS: continue
        tags = set(r["mess"]); rows.append(dict(source=r["kind"], file=r["path"], on_time=not (tags & LATE_TAGS), adds_up=not (tags & ADD_TAGS), manual_fix=bool(tags & FIX_TAGS)))
    for f, kind, period, exp, got, status in RECV:
        if status == "never received": rows.append(dict(source={"bank_statement": "bank_statements", "manager_statement": "manager_statements"}[kind], file=f, on_time=False, adds_up=False, manual_fix=False))
    return sorted(rows, key=lambda r: (r["source"], r["file"]))


# ---------------------------------------------------------------------------------------------------- write the files
def generate3(w, R):
    n0 = len(R.rows); X = build(w, R); w.X = X
    reg = lambda p, kind, month, desc, tags=(): R.add(p, kind, month, desc, tags)
    mess("M22", "unexplained bank lines", "bank_statements/HB_HOLD_USD_2026-08.xlsx, TCB_HOLD_USD_2026-09.xlsx, HB_B_USD_2026-10_mtd.xlsx", "Three bank lines match no invoice, notice, payroll, trade or transfer: a TT in of 48,250 (19 Aug), an ACH debit of 3,980 (23 Sep) and cheque 000417 of 2,150 (6 Oct)")
    # --- payment schedule (054, 070, 072, 064)
    p = R.path("2026-10", "payment_schedule", "payment_schedule_2026-10-13.csv")
    write_csv(p, ["ref", "entity", "payee", "due_date", "amount", "currency", "status", "basis"], [[i["ref"], i["ent"], i["payee"], i["due"].isoformat(), float(i["amount"]), i["ccy"], i["status"], i["basis"]] for i in X.sched if i["due"] <= d("2027-01-11")])
    reg(p, "payment_schedule", "2026-10", "Treasury payment schedule as at 13 Oct: approved, scheduled, expected and held payments for the next 90 days")
    # --- corporate actions and income calendar (055, 068)
    for n in X.caction_notices:
        s = w.sec[n["sec"]]; fn = f"{n['notice']}_{n['sec']}_{n['kind']}.pdf"; p = R.path("2026-10", "corporate_actions", fn)
        L = [("ANCHORAGE CUSTODY (SYNTHETIC) - CORPORATE ACTION NOTICE", 1, 13), "---", f"Security: {s['canonical_name']} ({s['identifiers']['internal']['security_id']})", f"Event: {'Cash dividend' if n['kind'] == 'dividend' else 'Coupon payment'} (mandatory, no election)",
             f"Ex-date: {dlong(n['ex'])}", f"Payment date: {dlong(n['pay'])}", (f"{'Dividend per share' if n['kind'] == 'dividend' else 'Coupon rate per year'}: " + (f"USD {n['per_unit']}" if n["kind"] == "dividend" else f"{n['rate'] * 100:.2f}%"), 1),
             f"Your holding: {n['qty']:,.0f}", f"Expected cash: USD {money(n['amount'])}", "---", "Synthetic document for test purposes only"]
        write_pdf(p, fn, L); reg(p, "corporate_actions", "2026-10", f"Corporate action notice: {s['canonical_name']} {n['kind']} paid {n['pay']}, USD {money(n['amount'])}")
    t = X.tender; s = w.sec[t["sec"]]; p = R.path("2026-10", "corporate_actions", f"{t['notice']}_{t['sec']}_tender_offer.pdf")
    write_pdf(p, p.name, [("ANCHORAGE CUSTODY (SYNTHETIC) - CORPORATE ACTION NOTICE", 1, 13), "---", f"Security: {s['canonical_name']} ({s['identifiers']['internal']['security_id']})", "Event: Voluntary tender offer by the issuer (an instruction is needed)",
                          f"Offer price: USD {t['offer']} per share (last price USD {t['px']})", f"Respond by: {dlong(t['deadline'])}   Payment date if accepted: {dlong(t['pays'])}", f"Your holding: {t['qty_held']:,.0f}", "Silence means no tender.", "---", "Synthetic document for test purposes only"])
    reg(p, "corporate_actions", "2026-10", f"Corporate action notice: voluntary tender offer on {s['canonical_name']}, respond by {t['deadline']}", ["M45"])
    mess("M45", "decision needed", f"corporate_actions/{p.name}", "A voluntary tender offer on Tidewater Energy needs an instruction by 22 Oct; the other notices are mandatory and only need booking")
    p = R.path("2026-10", "income_calendar", "income_calendar_2026-10-13.csv")
    write_csv(p, ["pay_date", "security_id", "security", "event", "rate_per_year", "per_share", "quantity", "expected_cash_usd"], [[e["pay"].isoformat(), "SEC-" + e["sec"], w.sec[e["sec"]]["canonical_name"], e["kind"], float(e["rate"]) if e["rate"] else "", float(e["per_unit"]) if e["per_unit"] else "", float(e["qty"]), float(e["amount"])] for e in X.income])
    reg(p, "income_calendar", "2026-10", "Coupon and dividend calendar of the liquid book for the next 12 months at the quantity held on 13 Oct")
    # --- custody statement (056)
    p = R.path("2026-10", "custody_statements", "custody_statement_2026-09-30.pdf")
    L = [("ANCHORAGE CUSTODY (SYNTHETIC) - SAFEKEEPING STATEMENT", 1, 13), "Portfolio EG-LIQUID   As at 30 September 2026   Issued 5 October 2026", "---"]
    L += [f"{w.sec[k]['canonical_name'][:34]:34s} {X.custody[k]:>12,.0f} {w.px[k][d('2026-09-30')]:>9} {q2(X.custody[k] * w.px[k][d('2026-09-30')]):>16,.2f}" for k in w.sec]
    L += ["---"] + [f"Note {k}: {CUST_BREAKS[k][1]} ({CUST_BREAKS[k][0]:+,} units)" for k in CUST_BREAKS] + ["Synthetic document for test purposes only"]
    write_pdf(p, p.name, L); reg(p, "custody_statements", "2026-10", "Custodian's safekeeping statement as at 30 Sep: 20 positions, two differ from the administrator pack", ["M24"])
    mess("M24", "custodian differs from administrator", "custody_statements/custody_statement_2026-09-30.pdf", "Bay Street Utilities +1,250 units and Redwood Pharma -400 units against the administrator pack of 30 Sep, each with the custodian's note")
    # --- second source prices (057)
    p = R.path("2026-10", "market_data", "second_source_prices_2026-09-30_and_2026-10-13.csv")
    write_csv(p, ["date", "security_id", "ticker", "price", "source"], [[day.isoformat(), "SEC-" + k, w.sec[k]["identifiers"]["trading_export"]["ticker"], str(X.second[(day, k)]), "Synthetic Pricing Service"] for day in (d("2026-09-30"), END) for k in w.sec])
    reg(p, "market_data", "2026-10", "Second-source prices for the 20 securities on 30 Sep and 13 Oct", ["M25"])
    mess("M25", "price gap to second source", "market_data/second_source_prices_2026-09-30_and_2026-10-13.csv", "Kingfisher Telecom (+1.9 percent) and Kingfisher Telecom 4.6% 2030 (-0.8 percent) differ from the administrator price on 30 Sep by more than the 0.5 percent tolerance")
    # --- settlement report (058)
    p = R.path("2026-10", "settlement_status", "settlement_report_2026-10-13.csv")
    rows = [[t["id"], "SEC-" + t["sec"], t["side"], float(t["qty"]), float(t["amt"]), t["trade"].isoformat(), t["settle"].isoformat(), "settled", "", "Synthetic Broker One", "yes"] for t in w.trades if d("2026-09-28") <= t["settle"] <= END]
    rows += [[f["id"], "SEC-" + f["sec"], f["side"], float(f["qty"]), float(f["amount"]), f["trade"].isoformat(), f["settle"].isoformat(), "failed", f["reason"], f["cpty"], "no"] for f in X.fails]
    write_csv(p, ["trade_ref", "security_id", "side", "quantity", "amount", "trade_date", "settle_date", "status", "reason", "counterparty", "cash_booked"], rows)
    reg(p, "settlement_status", "2026-10", "Custodian settlement report as at 13 Oct: trades settling from 28 Sep, two failed", ["M23"])
    mess("M23", "settlement fails", "settlement_status/settlement_report_2026-10-13.csv", "Two purchases through Synthetic Broker Two (Larkspur Health 5,000, Evermore Banking Group 10,000) are past their settlement date, not delivered, no cash booked; the desk export has no row for them")
    # --- break register (059)
    p = R.path("2026-10", "break_register", "break_register_2026-10-13.csv")
    write_csv(p, ["break_id", "type", "entity", "subject", "detected_on", "owner", "status"], [[b["id"], b["type"], b["ent"], b["subject"], b["detected"].isoformat(), b["owner"], "open"] for b in X.breaks])
    reg(p, "break_register", "2026-10", "Register of open breaks as at 13 Oct: six items, none closed by anyone", ["M26"])
    mess("M26", "breaks never closed", "break_register/break_register_2026-10-13.csv", "Six breaks stay open in the register; the 17 Jun Trust cash break cleared the next day and the 8 Oct Entity B break on 9 Oct, but nobody closed them; two cash breaks are older than five business days")
    # --- inbox (060)
    base = R.out
    for fn, what, dest, act in X.inbox:
        p = R.path("2026-10", "inbox", fn)
        if fn == "scan_0412.pdf": p.write_bytes((base / "2026-09/notices/2026-09-10_K_distribution.pdf").read_bytes())
        elif fn == "account_extract.xlsx": p.write_bytes((base / "2026-10/bank_statements/TCB_TRUST_USD_2026-10_mtd.xlsx").read_bytes())
        elif fn == "INV-OIT-2610.pdf":
            write_pdf(p, fn, [("ORCHARD IT SERVICES", 1, 16), "Synthetic vendor - for test purposes only", "---", ("INVOICE", 1, 14), "Invoice no: INV-OIT-2610", "Invoice date: 3 October 2026", "Due date: 2 November 2026", f"Bill to: {ENT['EG-HOLD']}", "---",
                              "Description: Managed IT and security, October 2026", ("Amount due: SGD 2,950.00", 1, 12), "---", "Pay to account ending 2290 at Harbour Bank (synthetic)"])
        elif fn == "IMG_2210.pdf": write_pdf(p, fn, [("MARINA BAY DINING (SYNTHETIC)", 1, 14), "Table 12   2 guests", "---", "Set menu x 2   SGD 168.00", "Service 10 percent   SGD 16.80", ("Total SGD 184.80", 1), "Thank you", "Synthetic document for test purposes only"])
        else: write_xlsx(p, {"Sheet1": [["Ref", "Amt1", "Amt2", "Flag"], ["A-1", 1200.5, 1180.0, "Y"], ["A-2", 88.0, 88.0, "N"], ["A-3", 5400.0, 5000.0, "Y"], ["A-4", 15.25, 15.25, "N"]]})
        reg(p, "inbox", "2026-10", f"Unsorted inbox file: {what}", ["M27"] if dest is None else [])
    mess("M27", "unrecognised files", "inbox/IMG_2210.pdf, inbox/data_export.xlsx", "Five files arrive in the inbox; three are known kinds (a duplicate notice, a duplicate bank statement, a new Orchard IT invoice); a restaurant receipt and a four-column sheet with no source are not")
    # --- load log (061)
    p = R.path("2026-10", "load_log", "load_log_2026-10-13.csv")
    write_csv(p, ["source", "file", "on_time", "adds_up", "manual_fix"], [[r["source"], r["file"], str(r["on_time"]).lower(), str(r["adds_up"]).lower(), str(r["manual_fix"]).lower()] for r in X.load_log])
    reg(p, "load_log", "2026-10", f"Load log of {len(X.load_log)} source files: on time, adds up, needed a manual fix")
    # --- real assets, title deeds, valuations, insurance schedule (065, 066, 082, 052)
    for a in X.assets:
        for ap in a["appraisals"]:
            mon = ap["date"].strftime("%Y-%m") if ap["date"] >= d("2026-04-01") else "2026-04"
            p = R.path(mon, "property_valuations", f"valuation_{a['id']}_{ap['date']}.pdf")
            write_pdf(p, p.name, [(ap["by"].upper() + " (SYNTHETIC)", 1, 14), "---", ("VALUATION REPORT", 1, 14), f"Asset: {a['name']} ({a['id']})   Type: {a['type']}", f"Owner of record: {ENT[a['ent']]}", f"Valuation date: {dlong(ap['date'])}",
                                  (f"Appraised value: {a['ccy']} {money(ap['value'])}", 1, 12), "Basis: market value, willing buyer and seller", "---", "Synthetic document for test purposes only"])
            reg(p, "property_valuations", mon, f"Valuation of {a['name']} at {ap['date']}: {a['ccy']} {money(ap['value'])}", ["M28"] if a["id"] in ("RA-03", "RA-05") else [])
        if a["type"] in ("residential property", "land"):
            p = R.path("2026-04", "title_deeds", f"title_deed_{a['id']}.pdf")
            write_pdf(p, p.name, [("LAND REGISTRY (SYNTHETIC)", 1, 14), "---", ("CERTIFICATE OF TITLE", 1, 14), f"Property: {a['name']} ({a['id']})", (f"Registered proprietor: {a['title']}", 1, 12), "Tenure: freehold", "---", "Synthetic document for test purposes only"])
            reg(p, "title_deeds", "2026-04", f"Title deed of {a['name']}, proprietor {a['title']}", ["M29"] if a["id"] == "RA-04" else [])
    mess("M28", "appraisal older than a year", "property_valuations/valuation_RA-03_2024-08-20.pdf, valuation_RA-05_2025-09-30.pdf", "The art collection was last appraised on 20 Aug 2024 and the wine collection on 30 Sep 2025: more than 365 days before 13 Oct 2026")
    mess("M29", "title in a personal name", "title_deeds/title_deed_RA-04.pdf", "The Coastal Land Parcel, held by Entity B, is registered to Lin Chen personally")
    p = R.path("2026-10", "insurance_schedule", "insurance_schedule_2026-10-01.pdf")
    L = [("SAFEHARBOUR INSURANCE BROKERS (SYNTHETIC)", 1, 14), "Schedule of policies as at 1 October 2026", "---"]
    for pol in w.policies:
        a_id, si = INSURED[pol["id"]]; nxt = pol["renewal"] if pol["renewal"] > END else pol["renewal"].replace(year=pol["renewal"].year + 1)
        L.append(f"{pol['id']} | {pol['name']} | asset {a_id or 'none'} | sum insured {pol['ccy']} {money(si)} | premium {pol['ccy']} {money(pol['premium'])} | next renewal {nxt}")
    L += ["---", "Synthetic document for test purposes only"]
    write_pdf(p, p.name, L); reg(p, "insurance_schedule", "2026-10", "Insurance schedule: four policies with sum insured, premium and next renewal", ["M30"])
    mess("M30", "cover below value", "insurance_schedule/insurance_schedule_2026-10-01.pdf", "The art collection and Bayview Residence are insured below their latest appraisal; Hillcrest House, the wine collection, the yacht and the land parcel have no policy")
    # --- tax lots (067)
    p = R.path("2026-10", "tax_lots", "lot_register_2026-09-30.xlsx")
    write_xlsx(p, {"Lots": [["Lot", "Security id", "Security", "Acquired", "Quantity", "Unit cost", "Cost", "As at"]] + [[l["id"], "SEC-" + l["sec"], w.sec[l["sec"]]["canonical_name"], l["acq"].isoformat(), float(l["qty"]), float(l["unit"]), float(q2(l["qty"] * l["unit"])), "2026-09-30"] for l in X.lots30]})
    reg(p, "tax_lots", "2026-10", f"Custodian tax lot register as at 30 Sep: {len(X.lots30)} open lots")
    # --- look-through (069)
    p = R.path("2026-10", "fund_holdings", "fund_holdings_2026-09-30.xlsx")
    write_xlsx(p, {"Holdings": [["Fund key", "Fund", "Company", "Sector", "Weight (% of fund)", "Source"]] + [[f, pname(f), c, sc, wt, "manager report as at 30 Sep 2026"] for f in PRIVATE for c, sc, wt in HOLDINGS[f]]})
    reg(p, "fund_holdings", "2026-10", "Look-through holdings of the eight private funds as reported by the managers at 30 Sep", ["M31"])
    mess("M31", "same company in several funds", "fund_holdings/fund_holdings_2026-09-30.xlsx", "Helix Cloud Systems sits in funds A, C and F; Harborview Semiconductor in funds A and C and also directly in the liquid book")
    # --- manager outlook (071)
    for m in sorted({FUND[f]["manager"] for f in PRIVATE}):
        fs = [f for f in PRIVATE if FUND[f]["manager"] == m]; p = R.path("2026-10", "manager_outlook", f"{MGR[m]['name'].split()[0].lower()}_distribution_outlook_2026-27.pdf")
        L = [(MGR[m]["name"].upper(), 1, 14), "Distribution outlook for investors, 4 quarters from 1 October 2026", "---"] + [f"{pname(f)}: payout as % of NAV at quarter end " + ", ".join(f"{q} {PAYOUT[f][i]}%" for i, q in enumerate(PAYOUT_Q)) for f in fs] + ["---", f"{MGR[m]['name']} - synthetic document for test purposes only"]
        write_pdf(p, p.name, L); reg(p, "manager_outlook", "2026-10", f"{MGR[m]['name']} distribution outlook for " + ", ".join(pname(f) for f in fs))
    # --- fund documents for the hedge funds (078)
    for f, t in HF_TERMS.items():
        p = R.path("2026-04", "fund_documents", f"kestrel_{f}_redemption_terms.pdf")
        write_pdf(p, p.name, [("KESTREL RIDGE ADVISORS", 1, 14), f"{pname(f)} - redemption terms", "---", f"Dealing: {t['dealing']}, on the last business day of the {'month' if t['dealing'] == 'monthly' else 'quarter'}", f"Notice: {t['notice']} calendar days before the dealing date",
                              f"Lock-up: no redemption before {dlong(t['lockup_end'])}" if f == "H2" else f"Lock-up: ended {dlong(t['lockup_end'])}", f"Payment: {t['payout']} days after the dealing date, {t['holdback']} percent held back until the audit", f"Subscribed: {dlong(t['subscribed'])}", "---", "Synthetic document for test purposes only"])
        reg(p, "fund_documents", "2026-04", f"Redemption terms of {pname(f)}: dealing {t['dealing']}, notice {t['notice']} days")
    # --- target allocation (079)
    p = R.path("2026-10", "target_allocation", "interim_targets_EG-LIQUID_2026-10-08.xlsx")
    write_xlsx(p, {"Targets": [["Portfolio", "Asset class", "Target % of the book", "Status"]] + [["EG-LIQUID", c, v, "proposed at the 8 Oct committee, not yet signed"] for c, v in TARGET_ALLOC.items()]})
    reg(p, "target_allocation", "2026-10", "Proposed interim targets of the liquid book (65 equity, 30 bond, 5 convertible), not yet signed")
    # --- payroll draft (081)
    p = R.path("2026-10", "payroll_drafts", "payroll_run_2026-10_draft.xlsx")
    write_xlsx(p, {"Draft": [["Employee", "Title", "Gross (SGD)", "Employee CPF (20%)", "Net pay (SGD)", "Employer CPF (17%)", "Pay date"]] +
                   [[n, t, float(g), float(q2(g * D("0.20"))), float(q2(g * D("0.80"))), float(q2(g * D("0.17"))), DRAFT["pay_date"]] for n, t, g in X.draft]})
    reg(p, "payroll_drafts", "2026-10", "Draft pay file for October 2026, not yet released", ["M32"])
    mess("M32", "payroll draft anomalies", "payroll_drafts/payroll_run_2026-10_draft.xlsx", "Grace Ong's gross is 20 percent above September with no approval, and a contractor (Jun Tan) who is not on the staff register is paid SGD 6,500")
    # --- tax calendar, tax notice (083, 084)
    p = R.path("2026-10", "tax_calendar", "tax_calendar_2026-27.xlsx")
    write_xlsx(p, {"Obligations": [["Id", "Entity", "Obligation", "Due", "Prepared by", "Estimated amount", "Currency", "Status"]] + [[t[0], t[1], t[2], t[3], t[4], t[5] or "", t[6], t[7]] for t in TAX],
                   "Rates": [["Entity", "Tax rate on income", "Tax rate on realised gains"]] + [[e, float(a), float(b)] for e, (a, b) in TAX_RATES.items()]})
    reg(p, "tax_calendar", "2026-10", "Tax calendar 2026-27 of the three entities and the 2026 rates", ["M33"])
    mess("M33", "overdue filing", "tax_calendar/tax_calendar_2026-27.xlsx", "Entity B's corporate income tax return was due 30 Sep 2026 and is still 'not filed'")
    p = R.path("2026-10", "tax_notices", "eci_notice_EG-HOLD_2026.pdf")
    write_pdf(p, p.name, [("INLAND REVENUE (SYNTHETIC)", 1, 14), "---", ("NOTICE TO FILE ESTIMATED CHARGEABLE INCOME", 1, 13), f"Taxpayer: {ENT['EG-HOLD']}", "Filing due: 30 November 2026", "Tax rate on income: 17 percent", "---", "Synthetic document for test purposes only"])
    reg(p, "tax_notices", "2026-10", "Notice to file the estimated chargeable income of Evergreen Holdings by 30 Nov 2026")
    # --- grants (085, 086)
    p = R.path("2026-10", "grant_ledger", "grant_ledger_2026.xlsx")
    write_xlsx(p, {"Grants": [["Grant", "Date", "Charity", "Amount (USD)", "Purpose", "Status", "Bank reference"]] + [[g["id"], g["date"].isoformat(), g["charity"], float(g["amount"]), g["purpose"], g["state"], g["id"] if g["state"] == "paid" else ""] for g in w.grants],
                   "Budget": [["Year", "Annual grant budget (USD)"], [2026, GRANT_BUDGET]]})
    reg(p, "grant_ledger", "2026-10", "Philanthropy ledger 2026: three grants paid, two pledged, budget USD 300,000")
    g = GRANT_REQUEST; p = R.path("2026-10", "grant_requests", f"grant_request_{g['id']}.pdf")
    write_pdf(p, p.name, [(g["charity"].upper(), 1, 14), "---", ("GRANT REQUEST", 1, 14), f"Request: {g['id']}", f"Amount requested: USD {money(g['amount'])}", f"Purpose: {g['purpose']}", f"Charity registered: {dlong(g['registered'])}", f"Contact: {g['contact']}", "---", "Synthetic document for test purposes only"])
    reg(p, "grant_requests", "2026-10", f"Grant request {g['id']} from {g['charity']}, USD {money(g['amount'])}", ["M34"])
    e = R.path("2026-10", "grant_requests", f"2026-10-09_{g['id']}.eml")
    write_eml(e, f"{g['contact']} <anneke@seabird.example.test>", f"Operations <{OPS}>", f"Grant request {g['id']}, wetland wardens", dt.datetime(2026, 10, 9, 8, 15), f"Dear Evergreen team,\n\nPlease find our request for USD {money(g['amount'])} attached.\n\nAnneke Lowe\n{g['charity']}", f"grant-{g['id']}", attach=(p.name, p.read_bytes()))
    reg(e, "grant_requests", "2026-10", f"Email delivering grant request {g['id']}", ["M34"])
    mess("M34", "grant request fails the policy", f"grant_requests/grant_request_{g['id']}.pdf", "Seabird Sanctuary Trust asks for USD 50,000: more than the USD 35,000 left in the 2026 budget, and the charity was registered 19 months ago (policy: 24)")
    # --- trust deed (087), estate memo (088)
    p = R.path("2026-04", "trust_deed", "evergreen_family_trust_deed.pdf")
    sh = TRUST_DEED["shares"]
    write_pdf(p, p.name, [("EVERGREEN FAMILY TRUST - DEED OF SETTLEMENT (SYNTHETIC)", 1, 13), "---", "Trust year: 1 April to 31 March", "Beneficiaries and shares of distributable income: " + ", ".join(f"{n} {v} percent" for n, v in sh.items()),
                          f"Distributable income is trust income less trust expenses. The trustees may distribute up to {TRUST_DEED['payout_cap']} percent of it in a trust year.", DEED_NOTE, f"Successor trustee: {TRUST_DEED['successor']}", "---", "Synthetic document for test purposes only"])
    reg(p, "trust_deed", "2026-04", "Deed of settlement of the Evergreen Family Trust: four beneficiaries, shares, payout cap", ["M47"])
    mess("M47", "trust paid beyond its share", "trust_deed/evergreen_family_trust_deed.pdf", "Wen Chen's 8 percent share of the distributable income is smaller than the allowances paid to Wen Chen since April")
    p = R.path("2026-10", "estate_planning", "transfer_tax_memo_2026.pdf")
    write_pdf(p, p.name, [("SUMMIT TAX ADVISORY (SYNTHETIC)", 1, 14), "---", ("TRANSFER TAX MEMO", 1, 13), f"Exemption: USD {money(ESTATE['exemption'])}", f"Rate above the exemption: {ESTATE['rate'] * 100:.0f} percent", f"Payable within {ESTATE['months_to_pay']} months of the transfer",
                          "Assets are valued at the latest appraisal or statement.", "---", "Synthetic document for test purposes only"])
    reg(p, "estate_planning", "2026-10", "Transfer tax memo: exemption, rate, payment term")
    # --- expense ledger, approval limits, budget (073, 089, 090)
    p = R.path("2026-10", "expense_ledger", "expense_ledger_2026-04_to_2026-09.xlsx")
    write_xlsx(p, {"Ledger": [["Date", "Category", "Payee", "Entity", "Currency", "Amount", "USD equivalent", "Reference", "Approver"]] + [[l["date"].isoformat(), l["cat"], l["payee"], l["ent"], l["ccy"], float(l["amount"]), float(l["usd"]), l["ref"], l["approver"]] for l in X.ledger],
                   "Approval limits": [["Approver", "Limit (USD)"]] + [[n, v] for n, v in APPROVERS]})
    reg(p, "expense_ledger", "2026-10", f"Expense ledger 1 Apr to 30 Sep 2026: {len(X.ledger)} payments with category and approver", ["M35"])
    mess("M35", "approved above the approver's limit", "expense_ledger/expense_ledger_2026-04_to_2026-09.xlsx", "Two legal and audit payments (LL-2026-0708, BAL-2026-051) are approved by Priya Nair, whose limit is USD 10,000")
    p = R.path("2026-04", "office_budget", "office_budget_2026.xlsx")
    write_xlsx(p, {"Budget": [["Category", "Annual budget (USD)"]] + [[c, v] for c, v in BUDGET.items()]}); reg(p, "office_budget", "2026-04", "Office budget 2026 by category, set in April")
    # --- access (091, 092), family access (100)
    p = R.path("2026-10", "access_register", "access_register_2026-10-13.csv")
    write_csv(p, ["grant_id", "person", "title", "system", "permission", "granted_on", "approved_by", "last_used"], [[g["id"], g["person"], g["title"], g["system"], g["permission"], g["granted"].isoformat(), g["approver"], g["last_used"].isoformat()] for g in X.access])
    reg(p, "access_register", "2026-10", f"Access register as at 13 Oct: {len(X.access)} grants of twelve people", ["M36"])
    e = R.path("2026-10", "access_register", "2026-10-02_joiner_leaver.eml")
    write_eml(e, "Priya Nair <priya.nair.evergreen@example.test>", "Anita Rao <anita.rao.evergreen@example.test>", "Joiner and leaver: Wei Tan, J. Ng", dt.datetime(2026, 10, 2, 9, 0),
              "Anita,\n\nJoiner: Wei Tan, Investment Analyst, starts 5 October. Please give Harbor, OMS (view) and the shared drive.\nLeaver: J. Ng, contract analyst, last day 30 September. Please remove all access.\n\nPriya", "jml-2026-10")
    reg(e, "access_register", "2026-10", "Email from the HR manager: one joiner, one leaver", ["M36"])
    mess("M36", "access not approved, left, unused", "access_register/access_register_2026-10-13.csv", "Two grants have no approver (Sam Lee OMS, Wei Tan Harbour Bank portal, which was not even requested); the leaver J. Ng still holds three grants; three grants were not used for more than 90 days")
    p = R.path("2026-10", "family_access", "family_access_policy_2026.pdf")
    write_pdf(p, p.name, [("EVERGREEN OFFICE - FAMILY ACCESS POLICY (SYNTHETIC)", 1, 13), "---", "Each family member sees the entities below, at the level shown (full report, summary or none):"] +
              [f"{m}: " + ", ".join(f"{ENT[e]} {FAMILY_POLICY[m][e]}" for e in ENT) for m in FAMILY_POLICY] + ["The principal approves any change.", "---", "Synthetic document for test purposes only"])
    reg(p, "family_access", "2026-10", "Family access policy: what each member may see")
    p = R.path("2026-10", "family_access", "family_view_grants_2026-10-13.csv")
    write_csv(p, ["member", "entity", "level", "granted_on"], [[m, e, lv, "2026-01-15"] for m in FAMILY_GRANTED for e, lv in FAMILY_GRANTED[m].items()])
    reg(p, "family_access", "2026-10", "Views granted to the four family members as at 13 Oct", ["M43"])
    e = R.path("2026-10", "family_access", "2026-10-09_access_request_maya.eml")
    write_eml(e, "Maya Chen <maya.chen.evergreen@example.test>", "Priya Nair <priya.nair.evergreen@example.test>", "Could I see the Holdings report?", dt.datetime(2026, 10, 9, 18, 20), "Hi Priya,\n\nCould I get the monthly report for Evergreen Holdings as well? Thanks, Maya", "famreq-maya")
    reg(e, "family_access", "2026-10", "Access request from Maya Chen for the Holdings report")
    mess("M43", "view over-granted", "family_access/family_view_grants_2026-10-13.csv", "Wen Chen is granted the full Entity B report; the policy gives Wen Chen the Trust summary only")
    # --- deals (077)
    p = R.path("2026-10", "deal_pipeline", "deal_pipeline_2026-10-13.csv")
    write_csv(p, ["deal", "name", "sponsor", "asset_class", "ticket_usd", "stage", "stage_entered", "owner"], [[x["id"], x["name"], x["sponsor"], x["cls"], float(x["ticket"]), x["stage"], x["entered"].isoformat(), x["owner"]] for x in X.deals])
    reg(p, "deal_pipeline", "2026-10", "Deal pipeline as at 13 Oct: five deals with stage and date entered", ["M46"])
    for dl in X.deals[1:4:2]:
        q = R.path("2026-09", "deal_pipeline", f"teaser_{dl['id']}.pdf")
        write_pdf(q, q.name, [(dl["sponsor"].upper() + " (SYNTHETIC)", 1, 14), f"{dl['name']} - fund teaser", "---", f"Strategy: {dl['cls']}", f"Minimum commitment: USD {money(dl['ticket'])}", "Synthetic document for test purposes only"])
        reg(q, "deal_pipeline", "2026-09", f"Fund teaser: {dl['name']}")
    e = R.path("2026-10", "deal_pipeline", "2026-10-05_harborlight_followup.eml")
    write_eml(e, "Harborlight IR <ir@harborlight.example.test>", "Sofia Reyes <sofia.reyes.evergreen@example.test>", "Harborlight Ventures IV - first close 30 November", dt.datetime(2026, 10, 5, 11, 0), "Sofia,\n\nA reminder that the first close of Harborlight Ventures IV is on 30 November. Happy to arrange a call.\n\nHarborlight IR", "deal-harborlight")
    reg(e, "deal_pipeline", "2026-10", "Email from Harborlight about the first close")
    mess("M46", "deals stuck in a stage", "deal_pipeline/deal_pipeline_2026-10-13.csv", "Marlow Infrastructure Partners III has been in Diligence since 28 Jul and Ashgrove Growth Equity V in Sourced since 15 Jun, both more than 60 days")
    # --- manager news (053)
    for m, day, subj, body in PERSONNEL:
        e = R.path(day[:7], "manager_news", f"{day}_{MGR[m]['name'].split()[0].lower()}_personnel.eml")
        write_eml(e, f"{MGR[m]['contact_name']} <{MGR[m]['contact_email']}>", f"Operations <{OPS}>", f"{MGR[m]['name']}: {subj}", dt.datetime.fromisoformat(day + "T10:00:00"), f"Dear investors,\n\n{body}\n\n{MGR[m]['contact_name']}\n{MGR[m]['name']}", f"news-{m}-{day}")
        reg(e, "manager_news", day[:7], f"{MGR[m]['name']}: {subj}", ["M44"])
    mess("M44", "manager personnel change", "manager_news/", "Saltmarsh Real Assets announces a resignation (18 Aug) and Northgate Partners adds a key person (9 Sep)")
    # --- SOPs (095, 096)
    for s in X.sops:
        p = R.path("2026-10", "sops", f"sop_{s['id']}.md")
        p.write_text(f"# SOP: {s['name']}\n\nOwner: {s['owner']}\nLast reviewed: {s['reviewed']}\nRuns per month: {s['runs']}\n\n| Step | Owner | Minutes per run | Manual |\n|---|---|---|---|\n" +
                     "\n".join(f"| {x['step']} | {x['owner']} | {x['minutes']} | {'yes' if x['manual'] else 'no'} |" for x in s["steps"]) + "\n", encoding="utf-8", newline="\n")
        reg(p, "sops", "2026-10", f"SOP {s['name']}, last reviewed {s['reviewed']}", ["M39"] if (END - s["reviewed"]).days > 365 else [])
    mess("M39", "SOP not reviewed in a year", "sops/", "Vendor payment run (20 Jun 2025), Payroll release (30 Sep 2025) and Open or change a bank account (1 Dec 2024) were last reviewed more than 365 days before 13 Oct 2026")
    # --- KYC (097), onboarding (093), bank account (094), glossary (098), new feed (099)
    p = R.path("2026-10", "kyc_register", "kyc_register_2026-10-13.csv")
    write_csv(p, ["entity", "counterparty", "document", "issued", "expires"], [list(k) for k in KYC_DOCS]); reg(p, "kyc_register", "2026-10", "Know-your-client register: 12 documents held for banks and managers", ["M40"])
    q = R.path("2026-10", "kyc_register", "kyc_pack_Evergreen_Holdings_2026.pdf")
    write_pdf(q, q.name, [("EVERGREEN HOLDINGS - KYC PACK (SYNTHETIC)", 1, 13), "---"] + [f"{k[2]} | {k[1]} | issued {k[3]} | expires {k[4]}" for k in KYC_DOCS if k[0] == "EG-HOLD"] + ["---", "Synthetic document for test purposes only"])
    reg(q, "kyc_register", "2026-10", "KYC pack of Evergreen Holdings", ["M40"])
    mess("M40", "KYC documents expiring", "kyc_register/", "Three documents expire within 90 days (a director's identity document 14 Nov, a certificate of incumbency 2 Dec, a manager refresh 5 Jan) and one expired on 12 Sep")
    p = R.path("2026-10", "onboarding", "onboarding_checklist_Harborlight.csv")
    write_csv(p, ["item", "status", "note"], [list(o) for o in ONBOARD]); reg(p, "onboarding", "2026-10", "Onboarding checklist of Harborlight Capital Partners: five items, two missing", ["M37"])
    q = R.path("2026-10", "onboarding", "kyc_pack_Harborlight_Capital_Partners.pdf")
    write_pdf(q, q.name, [("HARBORLIGHT CAPITAL PARTNERS - KYC PACK (SYNTHETIC)", 1, 13), "---", "1. Certificate of incorporation: provided", "2. Regulatory licence: provided", "3. Beneficial owner declaration: provided", "4. Sanctions screening report: provided", "---", "Synthetic document for test purposes only"])
    reg(q, "onboarding", "2026-10", "KYC pack of Harborlight Capital Partners, four documents")
    q = R.path("2026-10", "onboarding", "subscription_document_Harborlight_Ventures_IV_draft.pdf")
    write_pdf(q, q.name, [("HARBORLIGHT VENTURES IV - SUBSCRIPTION DOCUMENT (DRAFT)", 1, 13), "---", "Investor: Evergreen Holdings   Commitment: USD 2,000,000", "Signature: not yet signed", "Bank details for calls: to be advised", "---", "Synthetic document for test purposes only"])
    reg(q, "onboarding", "2026-10", "Draft subscription document, unsigned, bank details to be advised")
    mess("M37", "onboarding items missing", "onboarding/onboarding_checklist_Harborlight.csv", "Bank details were never confirmed by call-back and no statement schedule is agreed with Harborlight Capital Partners")
    a = ACCOUNT_FORM; p = R.path("2026-10", "bank_forms", "account_opening_form_TCB_TRUST_EUR.pdf")
    write_pdf(p, p.name, [("TIDEWATER COMMERCIAL BANK (SYNTHETIC) - ACCOUNT OPENING FORM", 1, 13), "---", f"Account holder: {ENT[a['entity']]}", f"Bank: {a['bank']}   Currency: {a['currency']}", f"Purpose: {a['purpose']}"] + [f"Signatory {i}: {s}" for i, s in enumerate(a["signatories"], 1)] + ["Mandate: any two signatories", "---", "Synthetic document for test purposes only"])
    reg(p, "bank_forms", "2026-10", "Opening form of a euro account of the Trust at Tidewater: two signatories", ["M38"])
    q = R.path("2026-10", "bank_forms", "signing_policy_2026.pdf")
    write_pdf(q, q.name, [("EVERGREEN OFFICE - SIGNING POLICY 2026 (SYNTHETIC)", 1, 13), "---", f"Every office account has at least {SIGNING['min_signatories']} signatories, one of whom is the {SIGNING['must_include']}.", f"The Principal is added for payments over {SIGNING['add_principal_over']:,} USD.", "---", "Synthetic document for test purposes only"])
    reg(q, "bank_forms", "2026-10", "Signing policy: two signatories, one the Head of Finance")
    mess("M38", "signatory missing", "bank_forms/account_opening_form_TCB_TRUST_EUR.pdf", "The Head of Finance (Daniel Foo) is not among the signatories the signing policy requires")
    p = R.path("2026-10", "glossary", "office_words_2026-10-01.csv")
    write_csv(p, ["term", "aliases", "definition"], [list(g) for g in GLOSSARY]); reg(p, "glossary", "2026-10", "The office word list: 19 terms with aliases", ["M41"])
    e = R.path("2026-10", "glossary", "2026-10-06_word_proposal.eml")
    write_eml(e, "Grace Ong <grace.ong.evergreen@example.test>", "Anita Rao <anita.rao.evergreen@example.test>", "Two words the managers keep using", dt.datetime(2026, 10, 6, 9, 30), "Anita,\n\nThe managers keep saying 'dry powder' and 'side letter'. Should they be on the list?\n\nGrace", "words-1")
    reg(e, "glossary", "2026-10", "Email proposing two words", ["M41"])
    q = R.path("2026-10", "glossary", "word_review_2026-10-08.md")
    q.write_text("# Word review, 8 October 2026\n\nProposed:\n- capital account\n- stub period\n- side letter\n", encoding="utf-8", newline="\n"); reg(q, "glossary", "2026-10", "Meeting note proposing three words", ["M41"])
    mess("M41", "words proposed", "glossary/", "Four different words are proposed (dry powder, side letter, capital account, stub period); two are already in the list (dry powder as an alias, capital account)")
    p = R.path("2026-10", "new_feed", "pinnacle_custody_positions_2026-10-12.csv")
    names = [c[0] for c in FEED["columns"]]
    write_csv(p, names, [["PTC-001", "PTC-SEC-1", "Granite Bay Materials", 50000, 38.4, 1921500, 1600000, "USD", "2026-10-12", "Settled"], ["PTC-001", "PTC-SEC-2", "Juniper Consumer Brands", 20000, 44.4, 888200, 910000, "USD", "2026-10-12", "Settled"],
                         ["PTC-001", "PTC-SEC-3", "Evermore Banking Group", 15000, 31.2, 468000, 440000, "USD", "2026-10-12", "Pending"]])
    reg(p, "new_feed", "2026-10", "A new custodian feed (Pinnacle Trust Company): 10 columns, 3 rows", ["M42"])
    q = R.path("2026-10", "new_feed", "pinnacle_cover_note.pdf")
    write_pdf(q, q.name, [("PINNACLE TRUST COMPANY (SYNTHETIC)", 1, 14), "---", "Cover note to the first position file", "The file lists positions of account PTC-001 in USD.", "Column definitions will follow.", "---", "Synthetic document for test purposes only"])
    reg(q, "new_feed", "2026-10", "Cover note of the new custodian feed")
    mess("M42", "ambiguous columns", "new_feed/pinnacle_custody_positions_2026-10-12.csv", "Two of ten columns cannot be mapped with confidence: Value (market or book) and Dt (valuation, trade or settle date)")
    assert {r["kind"] for r in R.rows[n0:]} == set(NEW_KINDS), {r["kind"] for r in R.rows[n0:]} ^ set(NEW_KINDS)
    return X
