# gold: monthly measures K01 to K27 (illustrative, synthetic)

One CSV per measure, `kNN.csv`, 13 month-end periods `2025-09` to `2026-09` (K15 and K16 start at `2025-10`, because a return needs the month before). Every value is computed from the other demo_cycle folders; nothing here is typed in by hand. Money in SGD with two decimals, ratios as decimals with four, counts as whole numbers.

| File | Columns | Unit | How it is computed (source folder) |
|---|---|---|---|
| k01.csv | period, value | SGD | Month-end bank cash (treasury, converted at fx/month_end_rates) plus money market funds (valuations/positions_monthly), less capital calls paid in the next six months (treasury/transfers), less K06, less a reserve of 2,000,000 per entity (10,000,000) |
| k02.csv | period, value | ratio | Holdings plus cash, less private fund value whose administrator statement for the month arrived late (administrators/statements late_flag Y), over holdings plus cash |
| k03.csv | period, value | hours | Sum of `hours` in reporting/effort_log_monthly for the period |
| k04.csv | period, value | SGD | Capital calls paid in the month (treasury/transfers `capital_call_paid`), converted at month-end rate |
| k05.csv | period, vehicle, value | SGD | `unfunded_commitment` from the statement delivered in the month, per fund, converted at month-end rate |
| k06.csv | period, value | SGD | 25 percent of total unfunded commitments (K05) as scenario-only calls |
| k07.csv | period, value | count | Pack versions reissued after circulation in the month (reporting/pack_versions `after_circulation` yes) |
| k08.csv | period, value | count | Operating entities more than 1,000,000 SGD above the cash floor at month end (treasury/monthly_idle_cash), plus one for each month after the last FX forward matured (fx/forwards_register) |
| k09.csv | period, value | ratio | Largest issuer group share of holdings (valuations/concentration_monthly) |
| k10.csv | period, value | ratio | Private market fund value over total holdings (valuations/positions_monthly) |
| k11.csv | period, value | SGD | fx/monthly_fx_measures `k11_unhedged_fx_exposure_sgd` |
| k12.csv | period, value | ratio | valuations/stale_valuation_monthly `stale_valuation_share` |
| k13.csv | period, value | SGD | Holdings plus cash at month end less the same at the previous month end (2025-09 against master/positions_2025_09_30 and account_opening_balances) |
| k14.csv | period, value | count | Statements delivered in the month with a valuation older than 120 days or a correction, plus landing files that failed the schema check |
| k15.csv | period, manager, value | percent | Month-on-month price return of each bond fund (valuations/month_end_prices); `manager` is the fund name |
| k16.csv | period, manager, value | percentage points | K15 less the mean K15 of all bond funds in the month |
| k17.csv | period, value | ratio | Value of holdings with an agreed benchmark (all but private market funds) over total holdings |
| k18.csv | period, value | ratio | Pack versions in the month that needed no reissue after circulation over all pack versions |
| k19.csv | period, value | ratio | Glossary terms with exactly one named owner over all terms in the office glossary (demo_story/16_business_glossary_raw.md); the glossary is undated, so every month carries the same value |
| k20.csv | period, entity_id, value | SGD | `cash_above_floor` per operating entity (treasury/monthly_idle_cash); the floor applies per entity, so the measure is read per entity |
| k21.csv | period, value | SGD per month | Sum of `total_interest_sgd` (treasury/monthly_interest) |
| k22.csv | period, custodian_id, value | basis points, annualised | custody/k22_monthly |
| k23.csv | period, value | count | Sum of `report_opens` (engagement/report_opens_monthly) |
| k24.csv | period, value | count | Questions logged in the month (engagement/questions_log) |
| k25.csv | period, value | count | Statements with `late_flag` Y by `delivery_month` (administrators/statements) |
| k26.csv | period, value | SGD per month | fx/monthly_fx_measures `k26_hedging_cost_sgd` |
| k27.csv | period, value | SGD per month | fx/monthly_fx_measures `k27_unhedged_fx_loss_sgd` |

Aggregation: every file is monthly. Where a source is daily (cash, prices, effort, arrivals), its own folder already rolls it up to the month as that folder's README says, and gold reads the monthly table.
