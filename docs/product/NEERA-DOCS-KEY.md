# Neera documents: answer key

Not shown in the product. For checking what the catalogue scan (I5) captured from `data/neera/documents/` (20 files, all synthetic). Roster: Priya Nair, Arjun Mehta, Leela Raman, Dev Sharma, Kiran Iyer, Meera Pillai, Rohan Das, Anita Bose, Sameer Khan, Nisha Rao.

## KPI definitions planted

| KPI | Definition as written | Where | Owner named |
|---|---|---|---|
| Time-weighted return, net of fees | Compounded monthly sub-period returns, after custody, management and advisory fees | 01 IPS s2; 02 reporting policy; 12 fee agreement | Sameer Khan (10 minutes) |
| Benchmark relative return | Portfolio TWR (net) minus 60/40 benchmark return, percentage points | 01 IPS s3; 15 benchmark note | Sameer Khan (10 minutes); Dev Sharma prepares |
| Cash drag | Cash weight times benchmark return for the period | 01 IPS s4; 16 cash guideline | Sameer Khan (10 minutes); Rohan Das reports cash weight |
| Fee ratio | Total fees paid / average portfolio value, annualised, % of assets | 02 reporting policy; 08 email | Rohan Das (inputs) |
| Concentration | Largest single issuer as % of portfolio market value at month end | 01 IPS s4; 02; 19 FAQ | Meera Pillai (10 minutes) |

## Source systems planted
Northgate Custody portal (positions, transactions, statements; Kiran Iyer), Pier Bank portal (cash; Rohan Das), accounting system (trial balance, posted about working day 6; Arjun Mehta), benchmark price file (Dev Sharma), fee schedule spreadsheet (Arjun Mehta), client list (Meera Pillai; restricted). Files 03, 05, 11, 20.

## Rules planted
- Access (13): Principal and Head of Operations see all; Investments staff not the ledger or client personal details; Reporting and Treasury read-only on source files; client personal details to Compliance and the Principal; changes need Meera Pillai's written approval; six-monthly review.
- Retention (14, 05): source files and statements 7 years; published reports 10 years; investment email 7 years; minutes life of office; working spreadsheets 2 years after the report; client personal details deleted within 1 year after relationship ends.
- Approval (02, 03, 10): a figure is published only for a period Operations (Arjun Mehta) has confirmed as loaded.
- Reconciliation (18): break above SGD 1,000 keeps the month not loaded.

## Quirks that match the samples (D1)
Price column renamed `price` to `price_local` from March 2026 (06, 11); currency missing in the January 2026 file (11); duplicate rows removed before reconciliation (18); July positions break on GBD-004 (06).

## The contradiction
Concentration limit: **10 per cent** in the Investment Policy Statement (01, version 3, effective 1 January 2026, and repeated in 19) versus **12 per cent** agreed by the investment committee on 18 June 2026 (09), with the IPS not reissued. A catalogue must flag this, not pick one. Related: 04 reports a largest issuer of 9.1 per cent, under both.

A minor second inconsistency a careful reader may flag: 02 says the monthly report is due working day 8 and the fee ratio needs the trial balance (working day 6 at the earliest, 03), so it is tight but not contradictory. Not planted as a contradiction.

## The unclear point
Who decides the benchmark blend when the investment committee and the Principal disagree: raised in 07 (Dev Sharma to Priya Nair) and left open in 10 item 3. Nobody is named; the catalogue must record it as unclear, not assign an owner.

## Other traps
- 12 is the only place the three fee rates appear (custody 0.80 per cent a year, management 0.45, advisory 0.20).
- 04 is a cover note: figures in it (2.4 per cent, 2.1, +0.3, 0.2, 0.78, 9.1) are Q2 2026 illustrative values, not definitions.
- No .docx: python-docx is not installed here.
