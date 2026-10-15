ILLUSTRATIVE: invented for demonstration

# 06 - Data dictionary

Aligned with tab 3 Fields of the data catalogue. One block per main file. Column "Feeds" uses the family_office pack KPI ids: K01 Minimum six-month funding headroom, K02 Reported-value evidence coverage, K04 Known obligations due, K05 Unfunded commitments, K06 Stress funding requirement, K09 Single-issuer concentration, K10 Private-market allocation, K11 Unhedged FX exposure, K12 Stale-valuation share, K14 Documents needing review, K15 Manager performance versus benchmark, K16 Excess return versus benchmark, K17 Benchmark coverage of holdings, K18 Compensation inputs reconciled, K19 Data definitions with a named owner. Account references are masked codes, not real numbers.

## 1. Bank statement CSV (Northgate Custody, T01 and T02)

### 1a. NGC_Statement_YYYYMMDD.csv (one row per account and currency per day)

| Field | Meaning | Type | Format or example | Feeds |
|---|---|---|---|---|
| statement_date | Day the balance is for | date | YYYY-MM-DD | K01 |
| entity_code | ILFO entity that owns the account | text | E01 or E02 | K01 |
| account_ref | Masked account code | text | E02-INV-USD | K01 |
| currency | Currency of the account | text | SGD, USD | K01, K11 |
| opening_balance | Balance at start of day | number | 1000000.00 (illustrative) | K01 |
| closing_balance | Balance at end of day | number | illustrative | K01, K11 |
| available_balance | Closing balance less holds | number | illustrative | K01 |

### 1b. NGC_Transactions_YYYYMMDD.csv (one row per cash movement)

| Field | Meaning | Type | Format | Feeds |
|---|---|---|---|---|
| trade_date | Date instructed | date | YYYY-MM-DD | K04 |
| value_date | Date cash moves | date | YYYY-MM-DD | K01, K04 |
| account_ref | Masked account code | text | E02-INV-USD | K01 |
| currency | Currency | text | USD | K04 |
| amount | Signed amount, debit negative | number | -1500000.00 (illustrative) | K01, K04 |
| narrative | Bank's free-text description (may name a manager or a family member) | text | free text | K04 |
| counterparty | Beneficiary or payer name | text | free text | K04 |
| internal_transfer_flag | Y when the movement is between E01 and E02 (set by Arjun, not by the bank) | text | Y or blank | K01 |

Exception: internal transfers are not marked by the bank. Arjun removes them by hand during consolidation. When the flag is wrong, cash is counted twice.

## 2. Administrator NAV report (Bluewater, BW_NAV_Report_YYYYMM.xlsx, T04)

One row per fund per holding entity at the month-end.

| Field | Meaning | Type | Format | Feeds |
|---|---|---|---|---|
| report_month_end | Month-end the report covers | date | YYYY-MM-DD | K12 |
| fund_code | ILFO code for the fund | text | HPE3, HPE4, KCF2, IBI1 | K02, K05, K10 |
| fund_name | Fund name | text | Harborview Private Equity Fund III | K02 |
| investor_entity_code | E01 or E02 | text | E02 | K10 |
| currency | Fund currency | text | USD | K11 |
| nav_local | ILFO's reported value in fund currency | number | illustrative | K02, K10, K12 |
| valuation_date | Date of the valuation behind the number | date | YYYY-MM-DD | K12 |
| valuation_basis | final_quarterly or rolled_forward | text | allowed values as listed | K02, K12 |
| commitment_local | Total commitment | number | illustrative | K05 |
| paid_in_to_date | Capital called and paid | number | illustrative | K05 |
| unfunded_local | Commitment less paid-in plus recallable returns | number | illustrative | K05 |
| recallable_amount | Distributions that may be called again | number | illustrative | K05 |
| report_status | draft or final | text | draft, final | K02 |

Exception: rolled_forward values are not final; Bluewater may restate them when the quarter is final. The administrator's unfunded figure may differ from Sara's tracker (timing).

## 3. Capital-call tracker (Sara, Capital_Call_Tracker.xlsx, T08)

### 3a. Tab Calls (one row per call notice)

| Field | Meaning | Type | Format | Feeds |
|---|---|---|---|---|
| call_ref | Sara's reference for the call | text | HPE4-C03 | K04, K14 |
| fund_code | Fund | text | HPE4 | K04, K05 |
| notice_date | Date printed on the notice | date | YYYY-MM-DD | K04 |
| received_date | Date the email reached the mailbox | date | YYYY-MM-DD | K04 |
| logged_date | Date Sara typed the row | date | YYYY-MM-DD | K04 |
| due_date | Date payment is due | date | YYYY-MM-DD | K01, K04 |
| currency | Call currency | text | USD | K04, K11 |
| call_amount | Total called | number | illustrative | K04 |
| fee_amount_in_call | Fee element of the call | number | illustrative | K05 |
| status | Received, Verified, Funded, Paid, Superseded | text | not enforced; free text in practice | K04, K14 |
| superseded_by | call_ref of the replacing notice | text | HPE4-C03A | K04, K14 |
| paid_date | Date the bank debit was seen | date | YYYY-MM-DD | K04 |
| notes | Free comments | text | free text | K14 |

Exception: corrected notices are logged as new rows and the earlier row is marked Superseded by hand. If the mark is missed the obligation is counted twice.

### 3b. Tab Commitments (one row per fund)

| Field | Meaning | Type | Format | Feeds |
|---|---|---|---|---|
| fund_code | Fund | text | HPE4 | K05 |
| commitment_ccy | Commitment currency | text | USD | K05 |
| commitment_amount | Total commitment | number | illustrative | K05 |
| called_to_date | Sum of paid calls | number | illustrative | K05 |
| recalled_distributions | Recallable returns added back | number | illustrative | K05 |
| unfunded_computed | Commitment less called plus recalled | number | formula, sometimes overwritten | K05 |

## 4. Exposure workbook (Wei, Exposure_Workbook.xlsx, T10)

### 4a. Tab Holdings and look-through (one row per holding or underlying line)

| Field | Meaning | Type | Format | Feeds |
|---|---|---|---|---|
| holding_id | Wei's row id | text | H0007 | K09 |
| entity_code | E01 or E02 | text | E02 | K09 |
| vehicle_name | Fund or account holding it | text | Tidewater Co-Investment Vehicle 1 | K10 |
| asset_class | Public equity, fixed income, PE and VC, private credit, real assets, cash | text | list | K10 |
| issuer_name | Underlying company or issuer as typed | text | free text | K09 |
| issuer_group | Normalised issuer name, set by hand | text | Meridian Cold Chain Holdings | K09 |
| exposure_route | direct or look_through | text | direct, look_through | K09 |
| currency | Currency of the exposure | text | USD | K11 |
| value_local | Value in local currency | number | illustrative | K09, K11 |
| value_sgd | Value in SGD at the typed rate | number | formula | K09, K10 |
| valuation_date | Date of the underlying valuation | date | YYYY-MM-DD | K12 |
| hedge_cover_sgd | Hedge amount, if any | number | usually blank | K11 |

Exceptions: issuer names differ by manager report and are matched by hand; look-through percentages are typed from PDFs and are not tracked for staleness.

## 4b. Performance workbook (Arjun, Performance_Workbook.xlsx, T13)

One row per fund and period. Index levels come from the market data vendor and the index provider (T15, T16); private figures come from manager statements (T17).

| Field | Meaning | Type | Format | Feeds |
|---|---|---|---|---|
| fund_code | Fund | text | MGE, HPE3 | K15, K16 |
| period_start | First day of the period measured | date | YYYY-MM-DD | K16 |
| period_end | Last day of the period | date | YYYY-MM-DD | K16 |
| return_method | time_weighted, net_irr or value_change (three versions of "return", not interchangeable) | text | allowed values as listed | K15, K16, K19 |
| period_return | Net-of-fee return of the fund over the period, in fund currency | percentage | 12.0 (illustrative) | K15, K16 |
| benchmark_id | Which benchmark applies, for example SPX, MSCIW, PE_BENCH. Blank for five of eight funds. | text | list, not enforced | K16, K17 |
| benchmark_return | Return of that benchmark over the same period and currency | percentage | 10.5 (illustrative) | K15, K16 |
| excess_return | period_return minus benchmark_return; the "alpha" of the pack. Formula, sometimes overwritten. | percentage points | +1.5 (illustrative) | K16 |
| index_level_start | Index level at period start, pasted from the vendor or provider | number | illustrative | K16 |
| index_level_end | Index level at period end, pasted | number | illustrative | K16 |
| level_source_date | Date of the pasted index close (often missing) | date | YYYY-MM-DD | K16, K19 |
| statement_period_end | Quarter the manager statement covers (private funds) | date | YYYY-MM-DD | K16 |

Exceptions: index closes are pasted by hand and the date is not always kept; the benchmark id can be changed by anyone who opens the file; private figures run a quarter or more behind public ones.

## 4c. Pay review workbook (Lina, Pay_Review_Workbook.xlsx, T14)

PERSONAL DATA. Every field below is personal data except the performance fields, which are copied in from Finance. Only the HR Lead and the Head of Investments may see it.

| Field | Meaning | Type | Format | Personal data? | Feeds |
|---|---|---|---|---|---|
| employee_ref | HR's reference for the person | text | EMP-04 | Yes | K18 |
| employee_name | Name of the employee | text | free text | Yes | K18 |
| role | Job title | text | list | Yes | K18 |
| salary_band | Pay band | text | B3 | Yes | K18 |
| target_bonus | Target bonus for the year | number | illustrative | Yes | K18 |
| performance_score | Weighted performance figure copied from Finance's spreadsheet | percentage | illustrative | No (but it feeds a personal decision) | K18 |
| recommended_bonus | Bonus recommended for the period | number | illustrative | Yes | K18 |
| approved_by | Who approved (Mei Tan) | text | name | Yes | K18 |
| review_date | Date of the review | date | YYYY-MM-DD | Yes | K18 |

Exception: performance_score is typed from an emailed spreadsheet; if the performance workbook changes afterwards, no one is told.

## 4d. Market data and index levels (third-party APIs, T15 and T16)

Described, not copied. One record is one instrument or index on one day.

| Field | Meaning | Type | Format | Feeds |
|---|---|---|---|---|
| instrument_or_index_id | Identifier of the instrument or index | text | illustrative code | K16, K17 |
| price_date | Close date | date | YYYY-MM-DD | K16 |
| close_level | Close price or index level | number | illustrative | K16 |
| currency | Currency of the level | text | USD | K16 |
| vendor_flag | Vendor's quality flag (estimated, final) | text | not recorded today | K19 |

Not personal data.

## 5. Pack inputs derived from these

The consolidation workbook (Arjun) holds K01, K02, K06 and K12 as pasted values with a note of source; it is not a source file in its own right.

## Personal data

Bank narratives and counterparty names may name family members: personal class "not sure", treated as personal until Arjun confirms. Every field of the pay review workbook except the performance score is personal data (see 4c). All other fields: neither personal nor sensitive, except that every file is sensitive to the business.
