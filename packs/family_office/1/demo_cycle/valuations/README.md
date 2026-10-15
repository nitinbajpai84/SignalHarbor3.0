# valuations: prices, private fund valuations, positions, concentration (illustrative, synthetic)

Reporting currency SGD. Windows: monthly 2025-09 to 2026-09 (13 periods, value at month end); daily 2026-07-01 to 2026-10-06, business days only (no 2026-08-10). Ids from master/. FX from fx/month_end_rates.csv (positions) and fx/daily_rates.csv.

| File | Grain | Columns |
|---|---|---|
| daily_prices.csv | business day x listed, bond or money market holding (H001-H026, H037-H040; 69 days) | date, holding_id, currency, close_price_local (4 dp) |
| month_end_prices.csv | period x same 30 holdings (13 periods) | period, as_of_date, holding_id, currency, close_price_local |
| private_fund_valuations.csv | one row per administrator valuation (valuation_date) per private fund H027-H036 | holding_id, administrator_id, valuation_date, received_date (first statement carrying it), currency, statement_nav_local (as on administrators/statements.csv), position_scale, market_value_local (statement_nav_local x position_scale) |
| positions_monthly.csv | period x holding (40) | period, holding_id, currency, quantity, price_local, valuation_date, valuation_age_days (month end less valuation_date), fx_sgd_per_unit, market_value_local, market_value_sgd |
| trades_monthly.csv | month-end purchases of USD holdings (not G03) | period, trade_date, holding_id, side, units |
| concentration_monthly.csv | period x issuer group G01-G12 | period, issuer_group_id, market_value_sgd, share_of_holdings (of all holdings; K09 is the G03 row) |
| stale_valuation_monthly.csv | period | period, stale_value_sgd, private_fund_value_sgd, stale_valuation_share (K12), age_threshold_days |
| volatility_daily.csv | business day | date, market_volatility_index |
| volatility_monthly.csv | period | period, market_volatility_index |

## Rules
- Private fund price in positions_monthly for period P is the administrator valuation in the statement delivered in month P (valuation_date and nav from administrators/statements.csv); quantity is constant, nav is scaled by position_scale so the 2025-09 value equals the master position.
- Listed, bond and money market positions use month_end_prices; G03 equity prices move the issuer share (quantities of G03 holdings never change, so its share rises by price, not purchases). USD holdings other than G03 grow by month-end purchases (trades_monthly).
- K09 = share_of_holdings for G03. K12 = stale_value_sgd / private_fund_value_sgd, a private fund being stale when valuation_age_days is above age_threshold_days (120).
- Month-end July, August, September 2026 in month_end_prices equals the last daily close of the month; volatility_monthly for those months equals the mean of the daily rows. Earlier months have no daily rows.
- Money two decimals, ratios as decimals.
