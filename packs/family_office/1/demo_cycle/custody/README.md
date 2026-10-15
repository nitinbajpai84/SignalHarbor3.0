# Custody

Synthetic, illustrative. Reporting currency SGD. Custodians C1 Harbourline Custody, C2 Meridian Trust Services, C3 Strait Custodial Bank.

| File | Grain | Columns and units |
|---|---|---|
| fee_schedule_C1_harbourline.eml, fee_schedule_C2_meridian.eml, fee_schedule_C3_strait.eml | one email per custodian, dated November 2024 | text |
| notes.md | office notes | text |
| assets_under_custody_monthly.csv | custodian x month, 2025-09 to 2026-09 (39 rows) | period YYYY-MM; custodian_id; assets_month_end_sgd (SGD, month-end value) |
| daily_fee_accruals.csv | custodian x calendar day, 2026-07-01 to 2026-10-06 (294 rows) | date; custodian_id; assets_under_custody_sgd (SGD, that day); rate_bp_annual (basis points a year applied); tier (flat, above 400m, below 400m); accrual_sgd (SGD = assets x rate / 10000 / 365, two decimals) |
| monthly_invoices.csv | custodian x month, 2025-09 to 2026-09 (39 rows) | invoice_no; custodian_id; period; issue_date; days; mean_assets_sgd; fee_sgd (sum of daily accruals for the month); other_charges_sgd (non-custody charges); invoice_total_sgd |
| k22_monthly.csv | custodian x month (39 rows) | k22_custody_fee_bp_annualised (K22: fee_sgd / mean assets x 365 / days x 10000) |

Aggregation: for 2026-07, 2026-08 and 2026-09, assets_month_end_sgd equals the last day's assets_under_custody_sgd in the daily file, and fee_sgd equals the sum of that month's accrual_sgd. Earlier months use the same method on daily values not shipped in the pack.
