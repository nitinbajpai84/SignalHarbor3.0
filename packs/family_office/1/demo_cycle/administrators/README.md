# administrators: fund administrator statements (illustrative, synthetic)

Ids as in `master/`. Delivery months 2025-09 to 2026-09 (13). A statement covers the month ended before its delivery month and is expected on the 10th Singapore working day of the delivery month. No statement is shown after 2026-10-06.

## Administrator to fund
A1 Lattice: H027, H028, H036. A2 Pinecrest: H029, H034, H035. A3 Orchard: H030, H031, H032, H033.

## Files
| File | Grain | Columns |
|---|---|---|
| statements.csv | one row per fund per delivery month (130) | statement_id, admin_id, fund_id, period_end, delivery_month (YYYY-MM), expected_arrival, actual_arrival, working_days_late, late_flag (Y/N), valuation_date (the date the NAV is struck as at), valuation_age_days (period_end minus valuation_date), currency, nav (fund currency, 2 dp), capital_called_in_period, distributions_in_period, unfunded_commitment, corrected_flag, file_name |
| statement_corrections.csv | one row per re-issued statement (3) | correction_id, statement_id, admin_id, fund_id, period_end, reissued_on, reason, nav_before, nav_after, currency |

## Rules
- Monthly late count (statements with late_flag = Y, by delivery_month) is the count of late administrator statements for that month.
- Working days are Monday to Friday excluding Singapore public holidays.
- Quarterly-reporting funds strike the NAV at the latest quarter end; monthly funds at month end. Amounts are in the fund currency, not SGD.
