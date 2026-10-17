"""Write the Evergreen Office 6-month data set.

    python -m tools.gen_office6m [--out tests/v1/fixtures/office6m]

Deterministic (string seeds, fixed zip dates, no clock). Output: <out>/<YYYY-MM>/<kind>/..., <out>/reference/, MANIFEST.md, answer_keys.yaml, received_log_all.csv.
Synthetic data only: every name, bank, fund and figure is invented.
"""
import argparse
import collections
import shutil
from pathlib import Path

import yaml

from .files import MESS, generate
from .keys import FILES, build_keys, top50_ids
from .world import ROOT

DEFAULT_OUT = ROOT / "tests/v1/fixtures/office6m"
MARK = ".office6m"

KIND_NOTE = {
    "bank_statements": "xlsx, one per account per month (Transactions + Daily balances); *_mtd = 1 to 13 Oct. Arrives 2 business days (Harbour Bank) or 4 (Tidewater) after month end.",
    "administrator_cash": "csv, the administrator's official daily cash per entity and currency, monthly, 2 business days after month end.",
    "administrator_nav": "xlsx monthly NAV pack as at the month end, released 06:00 UTC on the 2nd business day (Positions + NAV by portfolio).",
    "administrator_trades": "csv, trades as the administrator booked them (monthly).",
    "custodian_positions": "csv, one per business day, 20 positions of the Evergreen Liquid portfolio.",
    "custodian_transactions": "csv, monthly, trades, dividends, coupons and fees at the custodian.",
    "manager_statements": "pdf, capital account statements as received (monthly or quarterly; final, estimate or amended).",
    "notices": "pdf, capital call notices and distribution notices, by notice date.",
    "emails": "eml, deliveries (statement and notice PDFs attached), chasers, internal mail, a vendor bank-change mail.",
    "trading_export": "csv, one per trade day (OMS export) and monthly cash_movements (the desk's cash view).",
    "fx_rates": "csv, one per business day, USD/SGD WMR 4pm fixing.",
    "index_levels": "csv, daily levels of the two synthetic indices (monthly files).",
    "fx_confirmations": "pdf, bank confirmations of FX conversions and forwards.",
    "invoices": "pdf, vendor invoices and administrator/custodian fee invoices.",
    "payroll": "xlsx, monthly payroll of Evergreen Holdings.",
    "insurance": "pdf, insurance renewal notices.",
    "property_bills": "pdf, monthly property bills for two properties.",
    "meeting_notes": "md, meeting and investment committee notes (some reused from the 10-use-case set).",
    "investment_reports": "xlsx + pdf, the monthly investment report as issued.",
    "loan_statements": "xlsx, monthly statement of Entity B's term loan (amounts shown negative).",
    "approvals": "csv, approval log for payments over 500,000 USD.",
    "commitments": "xlsx, the commitments register as the office keeps it.",
    "family_allowances": "xlsx, monthly family allowance schedule.",
    "close_checklist": "csv, month-end close checklist (the six steps of the month-end process).",
    "exception_log": "csv, exceptions up to 13 Oct (cash breaks, missing statements).",
    "audit": "xlsx, the auditor's sample request.",
    "prospects": "pdf, a fund teaser.",
    "ddq": "pdf, two years of one manager's due diligence questionnaire.",
    "reference": "standing data and reused documents: standing instructions, fund terms, vendor master, accounts, office rules, policy, benchmark workbook, security master, process narrative, research documents.",
    "vendor_contracts": "pdf, vendor contracts with renewal dates.",
    "loan_agreement": "pdf, the term loan agreement.",
    "fee_schedule": "pdf, administrator, custodian and manager fee schedule.",
    "payment_schedule": "csv, treasury payment schedule as at 13 Oct: approved, scheduled, expected and held payments, 90 days.",
    "corporate_actions": "pdf, custodian corporate action notices (dividends, a coupon, a voluntary tender offer).",
    "income_calendar": "csv, coupon and dividend calendar of the liquid book, next 12 months.",
    "custody_statements": "pdf, the custodian's safekeeping statement as at 30 Sep.",
    "market_data": "csv, second-source prices for the 20 securities.",
    "settlement_status": "csv, custodian settlement report as at 13 Oct.",
    "break_register": "csv, register of open breaks with detection dates.",
    "inbox": "mixed pdf and xlsx, five unsorted files.",
    "load_log": "csv, load log of the source files: on time, adds up, manual fix.",
    "property_valuations": "pdf, appraisals of six real assets.",
    "title_deeds": "pdf, title deeds of two properties and a land parcel.",
    "insurance_schedule": "pdf, schedule of the four policies with sum insured.",
    "tax_lots": "xlsx, custodian tax lot register as at 30 Sep.",
    "fund_holdings": "xlsx, look-through holdings of the eight private funds.",
    "manager_outlook": "pdf, manager distribution outlook, four quarters.",
    "fund_documents": "pdf, redemption terms of the two hedge funds.",
    "target_allocation": "xlsx, proposed interim targets of the liquid book (not signed).",
    "payroll_drafts": "xlsx, draft October pay file, not released.",
    "tax_calendar": "xlsx, tax calendar 2026-27 with the rates.",
    "tax_notices": "pdf, tax notice (ECI).",
    "grant_ledger": "xlsx, philanthropy ledger and budget 2026.",
    "grant_requests": "pdf + eml, a grant request.",
    "trust_deed": "pdf, deed of the Evergreen Family Trust.",
    "estate_planning": "pdf, transfer tax memo.",
    "expense_ledger": "xlsx, expense ledger 1 Apr to 30 Sep with approver, plus approval limits.",
    "office_budget": "xlsx, office budget 2026 by category.",
    "access_register": "csv + eml, access grants of twelve people, joiner and leaver mail.",
    "family_access": "pdf + csv + eml, family access policy, views granted, an access request.",
    "deal_pipeline": "csv + pdf + eml, deals under review.",
    "manager_news": "eml, manager personnel-change mails.",
    "sops": "md, eight SOPs with last review date and step minutes.",
    "kyc_register": "csv + pdf, KYC documents with expiry dates.",
    "onboarding": "csv + pdf, onboarding checklist, KYC pack and draft subscription document of a new manager.",
    "bank_forms": "pdf, a bank account opening form and the signing policy.",
    "glossary": "csv + eml + md, the office word list and proposed words.",
    "new_feed": "csv + pdf, a new custodian feed and its cover note.",
}


def clean(out):
    if out.exists() and any(out.iterdir()):
        if not (out / MARK).exists():
            raise SystemExit(f"refusing to write into {out}: not empty and not an office6m folder")
        for c in out.iterdir():
            shutil.rmtree(c) if c.is_dir() else c.unlink()
    out.mkdir(parents=True, exist_ok=True)
    (out / MARK).write_text("generated by tools/gen_office6m; safe to delete and regenerate\n", encoding="utf-8", newline="\n")


def users(R):
    """use case id -> list of file paths its globs match."""
    allp = [Path(r["path"]) for r in R.rows] + [Path("received_log_all.csv")]
    out = {}
    for i, globs in FILES.items():
        hit = set()
        for g in globs:
            hit |= {p.as_posix() for p in R.out.glob(g)}
        out[i] = sorted(hit)
    return out


def manifest(w, R, keys, ucs):
    cat = top50_ids()[1]
    by_kind = collections.defaultdict(list)
    for r in R.rows: by_kind[r["kind"]].append(r)
    used = collections.defaultdict(list)
    for i, ps in ucs.items():
        for p in ps: used[p].append(i)
    L = ["# Evergreen Office, six months of daily life (synthetic)", "",
         "Generated by `python -m tools.gen_office6m` (code in `tools/gen_office6m/`). Deterministic: two runs give byte-identical output. **Synthetic data only**: every entity, bank, fund, manager, person and figure is invented.",
         "April to 13 October 2026. The last days run past September so that the capital call of 13 October (use case 1) can be tested against the cash of that day.", "",
         "## The world", "",
         "- **Entities:** Evergreen Holdings (`EG-HOLD`), Evergreen Family Trust (`EG-TRUST`), Entity B (`EG-B`). Each has USD and SGD accounts at Harbour Bank (synthetic) and at Tidewater Commercial Bank (synthetic): 12 accounts (`reference/accounts.csv`).",
         "- **Portfolios:** `EG-GROWTH` (funds A, B), `EG-PRIVATE` (C, F), `EG-B-OPS` (D, E, G, K), `EG-FUNDS` (hedge funds H1, H2 and index funds L1, L2), `EG-LIQUID` (20 securities at Anchorage Custody).",
         "- **Private funds (8, four managers):** A Evergreen Growth I and F Evergreen Growth II (Northgate); B Evergreen Income II and G Evergreen Credit III (Bluewater); C Cedarpoint Ventures III and D Cedarpoint Opportunities II (Cedarpoint); E Saltmarsh Infrastructure Fund II and K Saltmarsh Renewables I (Saltmarsh). Commitments and fee terms: `reference/fund_terms.csv`.",
         "- **Cedarpoint Ventures III:** commitment 10,000,000 for Holdings; calls 5 (April) and 6 (July) paid to the account ending 2209; 6,000,000 called before call 7 (13 October, 1,250,000, account ending 4471); unfunded 2,750,000 after it.",
         "- **People:** the ten people of `docs/v3/TEAM-OF-TEN.md` (payroll, approvals, emails, notes).",
         "- **Office rules (`reference/office_rules.csv`):** payments over 500,000 need the Head of Finance (Daniel Foo); changed bank details need a call-back; 250,000 cash buffer per entity; 5 percent single-name limit; 5,000 daily cash tolerance. Signed rules with their parameters (A28-A30): the sovereign note Harbour Treasury Note 2029 is exempt from the single-name limit; the liquid book is measured against EG-OFFICE-BLEND (benchmark_link); an invoice above its fee schedule is held from the payment run. Signed for cards 51 to 100 (A48 onward): approver limits, the 2026 office budget, the signing policy and the family access levels (each a signed version 2 beside the proposed version 1 the reader takes from its file), the 90 day idle-cash window, the 12 month forecast assumptions (call assumption, floor, horizon, distribution basis, held payments), the 0.5 percent price tolerance, the manager scorecard weights and bands, the bank-line purpose rule and 45 minutes of rework per failure. The interim allocation targets stay proposed.",
         "- **Added for the other 49 cards** (`tools/gen_office6m/more.py`; keys in `keys2.py`): new kinds of files in their own folders (payment schedule, corporate actions, real assets, tax lots, SOPs, access, ...). The bank statements gain three unexplained lines (card 63) and five grant payments from Holdings USD (card 85); nothing else of the first 51 cards moves.",
         "- **Reused from the 10-use-case set** (`tests/v1/fixtures/10uc`, `docs/test/10uc_universe.json`): securities and their month-end prices, the manager statements of funds A, B, C, D, E, H1, H2, L1, L2 (values, dates, late, missing and amended ones), the WMR fixings, the October trades, index levels, the policy, benchmark workbook, security master, process narrative, research documents and some meeting notes. Generated new: everything else.", "",
         "## Folders and names", "",
         "`<YYYY-MM>/<kind>/<file>`: the month is the month the file **arrives or is dated** (the April bank statement is in `2026-05`), so loading the folders up to a month gives the office as it knew itself that month. `reference/` holds standing data. `received_log_all.csv` lists every expected statement with its expected and received date.",
         "Answer keys: `answer_keys.yaml`, by use case id, then question, then expected values and how each was computed (from the same data that wrote the files).", "",
         "## Files by kind", "", "| Kind | Files | What | Example |", "|---|---|---|---|"]
    for k in sorted(by_kind): L.append(f"| `{k}` | {len(by_kind[k])} | {KIND_NOTE.get(k, '')} | `{by_kind[k][0]['path']}` |")
    L += ["", f"Total: {len(R.rows)} files.", "", "## Mess planted on purpose", "", "| Id | Kind | Where | What |", "|---|---|---|---|"]
    seen = set()
    for m in sorted(MESS, key=lambda m: (m["id"], m["where"])):
        if (m["id"], m["where"]) in seen: continue
        seen.add((m["id"], m["where"])); L.append(f"| {m['id']} | {m['kind']} | `{m['where']}` | {m['what']} |")
    L += ["", "## Use cases: input files and answer keys", "", "Use case ids are those of `packs/family_office/1/use_cases_100.yaml`: all 100 cards (priority 1 to 50 first, then the other 49) plus the role-build `uc8-trades-vs-admin`.", "",
          "| Priority | Use case | Title | Input files (count) | Keys |", "|---|---|---|---|---|"]
    ids = top50_ids()[0] + [i for i in FILES if i not in top50_ids()[0]]
    for i in ids:
        g = "; ".join(f"`{x}`" for x in FILES[i][:3]) + (" ..." if len(FILES[i]) > 3 else "")
        L.append(f"| {cat.get(i, {}).get('priority', '')} | `{i}` | {cat.get(i, {}).get('title', '')} | {len(ucs[i])} files: {g} | {len(keys[i]['questions'])} |")
    L += ["", "## Every file", "", "| File | What | Mess | Used by |", "|---|---|---|---|"]
    for r in sorted(R.rows, key=lambda r: r["path"]):
        L.append(f"| `{r['path']}` | {r['desc']} | {' '.join(sorted(set(r['mess'])))} | {' '.join(used.get(r['path'], []))} |")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args(argv)
    out = Path(a.out).resolve(); clean(out)
    w, R, mess = generate(out)
    keys = build_keys(w)
    ucs = users(R)
    (out / "answer_keys.yaml").write_text("# Computed from the generated data by tools/gen_office6m/keys.py. Never edit by hand.\n" + yaml.safe_dump(
        dict(office="Evergreen Office (synthetic)", as_of="2026-10-13", keys=keys), sort_keys=False, allow_unicode=True, width=160), encoding="utf-8", newline="\n")
    (out / "MANIFEST.md").write_text(manifest(w, R, keys, ucs), encoding="utf-8", newline="\n")
    c = collections.Counter(r["kind"] for r in R.rows)
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"{len(R.rows)} files, {size / 1e6:.1f} MB, {len(keys)} use cases keyed, {len({m['id'] for m in mess})} mess ids -> {out}")
    print(", ".join(f"{k} {n}" for k, n in sorted(c.items())))


if __name__ == "__main__":
    main()
