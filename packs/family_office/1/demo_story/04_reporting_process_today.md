ILLUSTRATIVE: invented for demonstration

# 04 - How the monthly committee pack is produced today

This is the narrative the swimlane process map is drawn from. Lanes are teams: Bank, managers and data vendors (outside), Finance, Operations, Risk, Treasury, Investments, HR, Committee. Steps marked MANUAL are done by hand in Excel or by typing. Times are owner estimates, not logged. "C" is the committee day (third Thursday); "C-5" means five working days before it. The pack is issued at C-2.

## Overview

The committee pack takes about 38 person-hours and about eight working days elapsed. It is built in four workbooks and one document: the Northgate statement CSV, the Bluewater NAV report, Sara's Capital_Call_Tracker.xlsx, Arjun's Cash_NAV_Consolidation.xlsx and Wei's Exposure_Workbook.xlsx. Nothing is connected. Each hand-over is a copy and paste.

## Steps

**Step 1. Bank statement download (Finance, Arjun, MANUAL, about 1 hour, C-8).**
Northgate Custody posts a statement CSV on its online portal every working day by noon. Arjun logs in with his token, downloads the month-end file and the daily files for the month (cash balances and transactions) and saves them in the shared finance folder. He types the month-end USD to SGD rate from Northgate's FX page into the consolidation workbook. Pain point: the rate is typed by hand; one month it was keyed from the wrong date.

**Step 2. Call notices arrive (Bank and managers to Operations, any time).**
Managers email capital-call and distribution notices to the shared mailbox capital-calls@example.test. There is no fixed arrival time and no fixed format; some are PDFs, some are in the email body, some are corrections that replace an earlier notice. Pain point: the median notice reaches ILFO with about five working days left to the due date, although the agreements give ten business days.

**Step 3. Sara's capital-call tracker (Operations, Sara, MANUAL, about 3 hours a month plus daily checks).**
Sara reads the mailbox about 10:00 each working day. For each notice she types a row into Capital_Call_Tracker.xlsx (call reference, fund, amounts, due date, status) and marks superseded rows by hand. At C-8 she reconciles the tracker's "paid" rows to the bank transactions and updates called-to-date and unfunded per commitment. Pain points: the tracker is updated when she has time (median two working days after receipt); status words are not consistent; there is no deputy; it is not linked to the bank file.

**Step 4. Administrator NAV files (Finance, Arjun, MANUAL, about 30 minutes, C-7 to C-5).**
Bluewater Fund Services puts a monthly NAV report (xlsx) on its client file share by working day 8 after month-end. It covers the four funds it administers. Arjun downloads it. Private fund values in it are either quarterly finals or rolled forward from the last quarter and are labelled in a basis column. Pain points: the file slipped to working day 10 in five of the last twelve months; funds not administered by Bluewater (Seaglass, Ironbridge Logistics, Tidewater, Marlowe) arrive as PDFs or from the custody statement, so their values are typed in.

**Step 5. Manual adjustments and consolidation (Finance, Arjun, MANUAL, about 6 hours, C-6 to C-5).**
In Cash_NAV_Consolidation.xlsx Arjun pastes bank balances and NAV lines, converts USD to SGD, removes internal transfers between E01 and E02 so cash is counted once, types the PDF-sourced values, and pulls the unfunded totals from Sara's tracker (copy and paste of values). He adds Tom's expected-calls and stress inputs. Pain points: formulas are overwritten by hand in some cells; valuation dates sit in one tab and are not carried through; this step is repeated whenever a number changes.

**Step 6. Treasury input (Treasury, Tom, MANUAL, about 3 hours, C-6).**
Tom reviews cash, USD balances, money-market holdings and the notified calls, and enters the expected calls for the next six months and the stress multiplier in a tab of the consolidation workbook. He decides what to redeem or buy in FX. Pain point: expected calls come from managers' indicative schedules, which are rarely updated; the base case sees only calls already noticed.

**Step 7. Wei's exposure workbook (Risk, Wei, MANUAL, about 10 hours, C-5 to C-4).**
Wei copies positions and values from the consolidation workbook, adds look-through holdings typed from manager PDF reports, normalises issuer names by hand, and computes single-issuer concentration, private-market allocation and unhedged FX. Pain points: it takes about a week elapsed to produce exposure by name; private funds are not in the weekly report; only Wei can build it.

**Step 8. Mei's review (Investments, Mei, MANUAL, about 5 hours, C-3 to C-2).**
Mei reads the draft pack, challenges numbers, and writes the policy compliance and decisions pages. She usually sends back one or two comment rounds to Arjun and Wei. Pain point: rework is the least visible cost; it is not logged. Policy exceptions are listed from Mei's own notes.

**Step 9. Pack assembly and issue (Operations, Sara, MANUAL, about 3 hours, C-2).**
Sara assembles the PDF from workbook extracts and Mei's pages, adds the manager fee summary appendix (copied from an earlier pack) and emails the pack to the committee. Pain point: the fee appendix is one of three copies of the fee list and is not checked.

**Step 10. Committee (Committee, C).**
The committee reads the pack, decides, and Sara records minutes. Decisions on commitments are tested against the reserve rule using the pack's funding page.

**Step 11. Monthly performance versus benchmark (Finance, Arjun, MANUAL, about 8 hours a month, then Mei about 2 hours, working days 10 to 15 after month-end).**
This is a separate cycle from the pack. Arjun keeps Performance_Workbook.xlsx. For public holdings he takes prices and values from the custody positions file and for the global equity fund from the daily NAV. He pastes index levels (an S&P 500 index, an MSCI World index) from a market data vendor download (Bloomberg Data License, illustrative) and from an index provider's file, then works out the period return and the benchmark return and subtracts. For private funds he types net IRR and NAV from each manager's quarterly statement (PDF attached to an email, arriving 30 to 60 days after quarter-end), so private figures are always a quarter or more behind the public ones. The benchmark for each fund is picked from memory or from the manager's report. Mei reads the result and tells him whether she agrees. Pain points: benchmarks chosen inconsistently; three versions of "return"; index dates pasted by hand; nothing connected; five of eight holdings have no benchmark.

**Step 12. Quarterly bonus and manager review (Finance to HR to Investments, MANUAL, about 6 hours for Lina and about 3 for Arjun and Mei, 4 to 6 weeks after quarter-end).**
After the Q performance note (see 13), Arjun emails a spreadsheet extract to Lina Ho (HR Lead). Lina copies the figures into Pay_Review_Workbook.xlsx, applies the weights in the bonus policy (see 14), and sends recommended accruals to Mei. Mei approves by email. Manager reviews (watch list decisions) go to the committee as a page in the quarterly pack. Pain points: HR waits for the spreadsheet; nobody trusts the figure because it was typed; if a private fund's value is later restated, the bonus basis changes with no record; the pay workbook mixes personal data and performance figures and is visible to Finance.

## Timing summary

| When | Step | Who | Effort |
|---|---|---|---|
| C-8 | Bank download; tracker reconciliation | Arjun, Sara | 1 h, 3 h |
| C-7 to C-5 | Administrator NAV file | Arjun | 0.5 h |
| C-6 to C-5 | Consolidation; Treasury input | Arjun, Tom | 6 h, 3 h |
| C-5 to C-4 | Exposure workbook | Wei | 10 h |
| C-3 to C-2 | Review and rework | Mei, Arjun, Wei | 5 h plus rework (inside the 12 and 10) |
| C-2 | Assembly and issue | Sara | 3 h |
| C | Committee | all | meeting |
| Month-end plus 10 to 15 working days | Performance versus benchmark (monthly) | Arjun, Mei | 8 h, 2 h |
| Quarter-end plus 4 to 6 weeks | Bonus accrual and manager review (quarterly) | Arjun, Lina, Mei | 3 h, 6 h, 3 h |

## Known pain points, in one list

1. Capital-call notices arrive late and unscheduled; logging adds a further delay.
2. No single exposure view: exposure by name takes about a week and leaves private funds out.
3. Nobody owns the manager fee list; three copies disagree on three of eight holdings.
4. Every hand-over is a manual copy of values; formulas are overwritten.
5. Valuation dates are not carried through to the pack.
6. Preparation hours are not logged, so the effort cannot be measured.
7. One person each for the tracker (Sara), the exposure workbook (Wei) and the stress view (Tom).
8. Performance versus benchmark is built by hand in Excel, months late for the private funds, with benchmarks chosen inconsistently.
9. Pay and manager reviews depend on that number; HR waits for a spreadsheet and nobody trusts it.
10. Index levels and prices have no system source; personal data sits beside performance data.

## Not confirmed

Wei has not described step 7 himself; it is drawn from other people's accounts and is shown as "to confirm". Who else receives the consolidation workbook is unknown.
