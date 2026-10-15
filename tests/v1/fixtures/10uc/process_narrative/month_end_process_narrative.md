# Evergreen Office: how we produce the monthly investment report today

Document: OPS-PRC-014, version 3.2 (working copy)
Owner: Mei Chen, Operations analyst
Reviewed by: Anita Rao, Head of data
Last updated: 2026-10-05
Project: Monthly investment report in USD and SGD
Status: describes current practice, not a target design

## 1. Purpose

This note describes, step by step, how the Operations and Finance team at Evergreen Office assembles the monthly investment report in USD and SGD. The report is needed by the 3rd business day of each month and goes to Daniel Foo, the Chief Investment Officer. Leo Park (data engineer) and Anita Rao (Head of data) have asked for this to be written down so the process can be mapped and automated.

## 2. People and systems

| Person | Role | Part in the process |
|---|---|---|
| Mei Chen | Operations analyst | Steps 1 to 3 |
| Raj Patel | Finance | Steps 4 and 5 (also owns most rules) |
| Daniel Foo | Chief Investment Officer | Step 6, approves the issued report |
| Sofia Reyes | Risk | Receives the pack, owns the limits |
| Leo Park, Anita Rao | Data | Support the exports; builder and head of data of the project |

Systems: File drop (shared folder), Excel (recon workbook, statements tracker, SGD conversion file), Email (shared statements inbox), Report pack (the formatted pack template).

## 3. Steps today

There are 6 steps. Steps 1, 2, 3 and 4 are manual spreadsheet, file or email steps and take most of the time.

### Step 1. Collect the exports

- Who: Mei Chen
- System: File drop
- Manual spreadsheet or hand step: yes
- Control: Row count and file totals match the file (batch_control_totals).
- Known exception: A rejected file is re-requested the same day.

Each month-end Mei downloads the administrator positions export and the trading system positions export (CSV) from the portals and saves them to the shared file drop under /MonthEnd/<yyyy-mm>/raw. She opens each file, counts the rows and compares the row count and control total in the footer line with the file. If the batch control totals do not match she rejects it and asks the administrator or the desk for a new file the same day.

### Step 2. Check cash against the administrator

- Who: Mei Chen
- System: Excel
- Manual spreadsheet or hand step: yes
- Control: Difference per entity per day inside cash_tolerance (5,000 USD).
- Known exception: Over tolerance opens a break case (Entity B, 12,400 USD on 8 Oct 2026).

Mei opens the cash tab of her reconciliation workbook (Cash_Recon_<yyyy-mm>.xlsx) and pastes the administrator cash balances beside the trading export balances, one row per entity (EG-HOLD, EG-TRUST, EG-B) per day. A formula column shows the difference. The signed rule is that cash may differ by up to 5,000 USD per entity per day; anything over is highlighted by hand and a break case is opened in the tracker (tab 'Breaks'). Raj is told by email.

### Step 3. Collect manager statements

- Who: Mei Chen
- System: Email
- Manual spreadsheet or hand step: yes
- Control: Every expected statement received by statement_due (10 business days).
- Known exception: Late or missing: follow-up draft to the manager.

The managers send statements to the shared statements inbox. Mei saves the PDF to the manager folder, types the fund, period end, value and received date into the statements tracker (Excel), and checks the tracker against the expected list. A statement is due 10 business days after the period end. For anything late or missing she writes a follow-up email to the manager by hand. Quarterly funds (C, D, E) are carried forward in the months with no statement.

### Step 4. Convert to SGD

- Who: Raj Patel
- System: Excel
- Manual spreadsheet or hand step: yes
- Control: WMR 4pm fixing of the period end (fx_fixing).
- Known exception: No fixing: hold the report.

Raj takes the holdings values from the tracker and the cash from the recon workbook and converts them to SGD in a separate Excel file, looking up the WMR 4pm USD/SGD fixing for the period end in the market data file. For September 2026 the fixing used was 1.3412. If there is no fixing for the date he holds the report. The conversion is typed in, not linked, so a changed USD figure does not flow through.

### Step 5. Review and approve the report

- Who: Raj Patel
- System: Report pack
- Manual spreadsheet or hand step: no
- Control: Maker never checker; estimates only in the investment report (estimate_use).
- Known exception: A revision over cio_materiality reopens the review.

Raj assembles the report pack from the converted figures and sends it for review. A manager estimate may be used in the investment report only. The maker of the figures is never the checker: Raj prepares, Daniel Foo approves. If a late statement revises a value by more than 100,000 USD or 0.5% of a fund, the review is reopened.

### Step 6. Read the report

- Who: Daniel Foo
- System: Report pack
- Manual spreadsheet or hand step: no
- Control: Issued version with cutoff shown.
- Known exception: Questions to managers logged as open questions.

Daniel reads the issued pack. The pack shows the version and the cutoff time. Questions for managers are logged as open questions and picked up by Mei in the next cycle.

## 4. Hand-overs

- Hand-over 1-2: Mei Chen (File drop) to Mei Chen (Excel). Same person, different tool: the file is re-saved and re-typed.
- Hand-over 2-3: Mei Chen (Excel) to Mei Chen (Email). Same person, different tool: the file is re-saved and re-typed.
- Hand-over 3-4: Mei Chen (Email) to Raj Patel (Excel). By email with the workbook attached; there is no log of what was sent.
- Hand-over 4-5: Raj Patel (Excel) to Raj Patel (Report pack). Same person, different tool: the file is re-saved and re-typed.
- Hand-over 5-6: Raj Patel (Report pack) to Daniel Foo (Report pack). By email with the workbook attached; there is no log of what was sent.

There is no single place that shows where a month stands; Mei and Raj ask each other by chat.

## 5. Controls summary

| Step | Control |
|---|---|
| 1 | Row count and file totals match the file (batch_control_totals). |
| 2 | Difference per entity per day inside cash_tolerance (5,000 USD). |
| 3 | Every expected statement received by statement_due (10 business days). |
| 4 | WMR 4pm fixing of the period end (fx_fixing). |
| 5 | Maker never checker; estimates only in the investment report (estimate_use). |
| 6 | Issued version with cutoff shown. |

## 6. Known exceptions seen recently

- Cash: on 8 Oct 2026 Entity B (EG-B) showed 880,400 at the administrator against 868,000 in the trading export, a difference of 12,400 USD, over the 5,000 USD tolerance, so one break case was opened. EG-TRUST differed by 1,800 USD and needed no case.
- Statements: Fund D (Cedarpoint Opportunities II) 30 June 2026 statement was due 2026-07-14 and never arrived. Fund H2 August 2026 arrived 2026-09-22, 6 business days late; Fund E June 2026 arrived 2026-07-24, 8 business days late.
- Revisions: Fund A September 2026 was reported at 10,000,000 USD (manager estimate) in the report issued 2026-10-03; the amended statement of 2026-10-07 shows 10,180,000 USD, +180,000, over the 100,000 USD materiality, so the review is reopened. Earlier revisions: Fund C June 2026 8,275,000 (was 8,420,000) and Fund H1 July 2026 7,012,500 (was 7,050,000).
- The same fund can arrive under different names (for example 'KR Macro Fund Ltd - Class B USD' and 'Kestrel Ridge Macro Fund'); Mei matches them by eye using the administrator code.

## 7. The September 2026 cycle in numbers

Issued 2026-10-03 10:30 UTC, cutoff 10:00 UTC. Values in USD: Evergreen Growth I 10,000,000 (estimated); Evergreen Income II 6,400,000 (official); Liquid book 41,200,000 (official); Total 57,600,000 (estimated). Total in SGD 77,253,120.00 at 1.3412.

## 8. What we would like North to produce

A swim lane across the three people and four systems above, with the four manual steps flagged, and a standard operating procedure (owner, system, input, output, control, exception for each step).
