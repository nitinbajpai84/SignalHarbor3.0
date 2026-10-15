# Worked examples

Time-weighted return per month (cleaned table with period, start value, end value, net flow):
select period, (end_value - net_flow - start_value) / start_value as value from silver."table a" order by period
(flows taken out at month end; no digit needed). Chaining months is done in the report, not in one month's SQL.

Drift: select period, sum(abs(weight - target_weight)) / count(*) as value from silver."table a" group by period order by period

Concentration (largest issuer over total): with t as (select period, issuer, sum(market_value) as mv from silver."table a" group by period, issuer)
select period, max(mv) / sum(mv) as value from t group by period order by period

Runway (months of cash): cash balance at period end over the average monthly outflow; ask which window the engineer wants.

An open point, well asked: "Row: concentration. I took the largest issuer over the total; confirm or tell me the rule."
An answer applied: the rule goes on the mapping row, the row is marked as the engineer's, and the next load uses it.
