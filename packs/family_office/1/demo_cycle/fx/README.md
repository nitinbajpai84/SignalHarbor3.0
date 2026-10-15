# fx (illustrative, synthetic)

Ardmore family office, reporting currency SGD. Rates are SGD per one unit of foreign currency, four decimals.

| File | Grain | Columns |
|---|---|---|
| `daily_rates.csv` | business day, 2026-07-01 to 2026-10-06 (69 rows; no 2026-08-10, Singapore public holiday) | `date`, `usd_sgd`, `eur_sgd`, `hkd_sgd` |
| `month_end_rates.csv` | month, 2025-09 to 2026-09 (13 rows) | `period` (YYYY-MM), `as_of_date` (last business day), `usd_sgd`, `eur_sgd`, `hkd_sgd` |
| `forwards_register.csv` | one row per forward contract | `forward_id`, `entity_id`, `sold_currency`, `bought_currency`, `direction`, `trade_date`, `maturity_date`, `notional_usd` (USD), `spot_sgd_per_usd_at_trade`, `forward_sgd_per_usd`, `counterparty`, `status` |
| `monthly_exposure.csv` | month x currency (USD, EUR, HKD), 39 rows | `period`, `currency`, `bank_balances_native`, `holdings_native`, `gross_exposure_native` (bank plus holdings), `hedge_cover_native` (forward notional running at month end), `unhedged_native` (gross less cover), `month_end_rate_sgd`, `unhedged_sgd` (unhedged_native x rate) |
| `monthly_fx_measures.csv` | month, 13 rows | `period`, `k11_unhedged_fx_exposure_sgd`, `k26_hedging_cost_sgd`, `k27_unhedged_fx_loss_sgd` |

Amounts in the stated currency, two decimals. Native amounts are in the currency named in the row. Holdings are the month-end local market values of that currency's rows in `valuations/positions_monthly.csv`; bank balances are the month-end balances of that currency's accounts in `treasury/monthly_cash_balances.csv` (USD: B02, B04; EUR: B08; HKD: none). Forwards cover about 80 percent of the prior month-end gross USD exposure, rounded to a million.

## Aggregation rules

- Month-end rate for 2026-07, 2026-08 and 2026-09 equals the `daily_rates.csv` row on the last business day of that month. Earlier month-end rates have no daily file.
- K11 at month end = sum over USD, EUR, HKD of `unhedged_sgd`, all long positions.
- K26 for a month = sum over forwards maturing in that month of notional x (spot less forward rate) plus a dealing charge of 0.003 per cent of notional.
- K27 for a month = per currency, the unhedged native amount at the prior month end x (month-end rate less prior month-end rate), counted only where negative (a fall in SGD value), shown as a positive loss, summed over currencies. Gains are not netted.
