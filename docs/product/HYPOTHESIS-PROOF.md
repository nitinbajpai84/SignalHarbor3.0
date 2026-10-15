# Hypothesis proof: the eight truths in the demo cycle

Illustrative, synthetic data (Ardmore family office demo, `packs/family_office/1/demo_cycle`). Every table below is the output of the SQL above it,
run against `warehouse/company.duckdb` after `tools/seed_demo_cycle.py` loaded the pack (gold measures in `gold.kNN`, every pack CSV in
`silver.<area>_<file>`). Regenerate with `python .sh-tmp/ic/data/d13_proof.py <company.duckdb>`. Measures run 2025-09 to 2026-09; daily rows
2026-07-01 to 2026-10-06. Document names are the context shelf file names the loader gives them (`<folder>_<file>`).

## T1 Idle cash (new revenue). Initiative: treasury sweep to money market funds, started 2026-05-04

Questions a reader asks: how much cash sits above the 2,000,000 SGD floor, in which entity, since when; what does it earn; was a sweep ever set up.

K20 idle cash above policy, per entity (E01 holdings company, E03 the trust):
```sql
select period, entity_id, value from gold.k20 where entity_id in ('E01', 'E03') and period in ('2025-09','2025-11','2026-02','2026-04','2026-05','2026-07','2026-09') order by period, entity_id
```

| period | entity_id | value |
|---|---|---|
| 2025-09 | E01 | 9,500,000.00 |
| 2025-09 | E03 | 10,000,000.00 |
| 2025-11 | E01 | 10,900,000.00 |
| 2025-11 | E03 | 11,200,000.00 |
| 2026-02 | E01 | 12,500,000.00 |
| 2026-02 | E03 | 12,800,000.00 |
| 2026-04 | E01 | 13,500,000.00 |
| 2026-04 | E03 | 13,700,000.00 |
| 2026-05 | E01 | 3,500,000.00 |
| 2026-05 | E03 | 3,800,000.00 |
| 2026-07 | E01 | 1,200,000.00 |
| 2026-07 | E03 | 1,100,000.00 |
| 2026-09 | E01 | 1,000,000.00 |
| 2026-09 | E03 | 1,000,000.00 |

K21 interest earned on cash, SGD per month:
```sql
select period, round(value, 2) as interest_sgd from gold.k21 order by period
```

| period | interest_sgd |
|---|---|
| 2025-09 | 3,572.37 |
| 2025-10 | 3,586.83 |
| 2025-11 | 3,623.95 |
| 2025-12 | 3,683.06 |
| 2026-01 | 3,747.49 |
| 2026-02 | 3,822.82 |
| 2026-03 | 3,917.11 |
| 2026-04 | 4,002.04 |
| 2026-05 | 25,928.89 |
| 2026-06 | 33,890.41 |
| 2026-07 | 38,165.95 |
| 2026-08 | 38,638.07 |
| 2026-09 | 37,554.81 |

Sweeps to money market funds (none before the initiative):
```sql
select transfer_type, counterparty, count(*) as transfers, min(value_date) as first, max(value_date) as last from silver.treasury_transfers where transfer_type = 'sweep_to_mmf' group by all order by counterparty
```

| transfer_type | counterparty | transfers | first | last |
|---|---|---|---|---|
| sweep_to_mmf | H037 | 5 | 2026-05-04 | 2026-07-06 |
| sweep_to_mmf | H039 | 4 | 2026-05-04 | 2026-07-06 |

**Before and after.** Before (2025-11 to 2026-04): E01 10.9m to 13.5m and E03 11.2m to 13.7m SGD above the floor; K21 about 3,600 to 4,000 SGD a month.
After the 2026-05-04 sweep: both entities 1.0m to 1.2m from July; K21 about 37,000 to 38,000 SGD a month. Verdict: **working**. Note: the sum over all three
operating entities is 2.8m in July (E02 holds 0.5m), so the "under 1.5 million" claim is per entity, which is why gold.k20 carries `entity_id`.

## T2 Late Pinecrest statements drive pack effort (process cost). Initiative: standard template and auto-ingest, started 2026-06-15

Questions: why does the committee pack take 50 hours; which administrator is late; where does the rework go.

K03 pack hours and K25 late statements:
```sql
select k3.period, k3.value as pack_hours, k25.value as late_statements from gold.k03 k3 join gold.k25 k25 using (period) order by period
```

| period | pack_hours | late_statements |
|---|---|---|
| 2025-09 | 48.75 | 5.00 |
| 2025-10 | 50.00 | 7.00 |
| 2025-11 | 50.75 | 6.00 |
| 2025-12 | 51.50 | 7.00 |
| 2026-01 | 48.50 | 5.00 |
| 2026-02 | 52.00 | 6.00 |
| 2026-03 | 55.50 | 6.00 |
| 2026-04 | 55.00 | 5.00 |
| 2026-05 | 53.00 | 7.00 |
| 2026-06 | 40.75 | 7.00 |
| 2026-07 | 31.00 | 3.00 |
| 2026-08 | 30.00 | 3.00 |
| 2026-09 | 32.75 | 3.00 |

Late statements by administrator, before and after the template:
```sql
select admin_id, sum(case when delivery_month < '2026-07' then 1 else 0 end) as late_to_jun, sum(case when delivery_month >= '2026-07' then 1 else 0 end) as late_jul_sep, round(avg(working_days_late) filter (where late_flag = 'Y'), 1) as avg_days_late from silver.administrators_statements where late_flag = 'Y' group by admin_id order by admin_id
```

| admin_id | late_to_jun | late_jul_sep | avg_days_late |
|---|---|---|---|
| A1 | 12 | 0 | 1.90 |
| A2 | 30 | 9 | 8.30 |
| A3 | 19 | 0 | 1.90 |

Rework hours that the effort log itself attributes to A2:
```sql
select period, sum(hours) filter (where cause = 'late_statement_A2') as a2_rework_hours, sum(hours) as all_hours from silver.reporting_effort_log_monthly group by period order by period
```

| period | a2_rework_hours | all_hours |
|---|---|---|
| 2025-09 | 14.50 | 48.75 |
| 2025-10 | 15.50 | 50.00 |
| 2025-11 | 17.00 | 50.75 |
| 2025-12 | 16.00 | 51.50 |
| 2026-01 | 13.00 | 48.50 |
| 2026-02 | 15.50 | 52.00 |
| 2026-03 | 18.50 | 55.50 |
| 2026-04 | 20.50 | 55.00 |
| 2026-05 | 16.00 | 53.00 |
| 2026-06 | 10.00 | 40.75 |
| 2026-07 | 2.00 | 31.00 |
| 2026-08 | 1.75 | 30.00 |
| 2026-09 | 2.00 | 32.75 |

Daily file window: late files by source (A2 still late, ingest absorbs it):
```sql
select source_type || '_' || source_id as source, count(*) filter (where late_flag = 'Y') as late, count(*) filter (where schema_ok = 'N') as schema_failed from silver.landing_file_arrival_log group by all having late + schema_failed > 0 order by late desc
```

| source | late | schema_failed |
|---|---|---|
| administrator_A2 | 13 | 0 |
| custodian_C1 | 1 | 0 |
| bank_B04 | 1 | 0 |
| custodian_C3 | 0 | 1 |

**Before and after.** Before (2025-09 to 2026-05): K03 48.5 to 55.5 hours, K25 5 to 7 a month. After the template (from 2026-07): K03 30.0 to 32.75 hours, K25 3 a month,
A2's own rework hours falling from 10 to 20 a month to about 2. Verdict: **working**. The daily K03 check groups `effort_log_daily` by `date`, not `pack_period`
(by pack_period July is 21.67 hours, which is not what the monthly table records).

## T3 Family report opens fall (retention). Initiative: one-page personal summary, started 2026-07-15

Questions: who stopped reading, where they stop, what they ask.

K23 opens and K24 questions:
```sql
select o.period, o.value as opens, q.value as questions from gold.k23 o join gold.k24 q using (period) order by period
```

| period | opens | questions |
|---|---|---|
| 2025-09 | 38.00 | 6.00 |
| 2025-10 | 38.00 | 6.00 |
| 2025-11 | 35.00 | 7.00 |
| 2025-12 | 31.00 | 9.00 |
| 2026-01 | 27.00 | 12.00 |
| 2026-02 | 23.00 | 14.00 |
| 2026-03 | 20.00 | 17.00 |
| 2026-04 | 17.00 | 19.00 |
| 2026-05 | 15.00 | 20.00 |
| 2026-06 | 14.00 | 21.00 |
| 2026-07 | 24.00 | 17.00 |
| 2026-08 | 26.00 | 13.00 |
| 2026-09 | 27.00 | 11.00 |

Opens by generation (master/family_readers):
```sql
select o.period, sum(report_opens) filter (where f.generation = 'next') as next_generation, sum(report_opens) filter (where f.generation = 'senior') as senior from silver.engagement_report_opens_monthly o join silver.master_family_readers f on f.name = o.reader group by o.period order by o.period
```

| period | next_generation | senior |
|---|---|---|
| 2025-09 | 16 | 22 |
| 2025-10 | 16 | 22 |
| 2025-11 | 15 | 20 |
| 2025-12 | 13 | 18 |
| 2026-01 | 11 | 16 |
| 2026-02 | 9 | 14 |
| 2026-03 | 7 | 13 |
| 2026-04 | 6 | 11 |
| 2026-05 | 5 | 10 |
| 2026-06 | 5 | 9 |
| 2026-07 | 15 | 9 |
| 2026-08 | 17 | 9 |
| 2026-09 | 18 | 9 |

Daily window: how far into a report each reader goes:
```sql
select reader, report_id like 'PS-%' as one_page_summary, count(*) as page_views, max(page) as deepest_page from silver.engagement_portal_events_daily group by all order by reader, one_page_summary
```

| reader | one_page_summary | page_views | deepest_page |
|---|---|---|---|
| Kerr Mei Xin | False | 9 | 1 |
| Kerr Mei Xin | True | 16 | 1 |
| Mr Shaw Kian Peng | False | 118 | 9 |
| Mrs Shaw Li Hua | False | 73 | 7 |
| Shaw Wei Jie | False | 10 | 1 |
| Shaw Wei Jie | True | 20 | 1 |

**Before and after.** Opens fell from 38 (2025-09) to 14 (2026-06) while questions rose from 6 to 21. After the one-page summary: opens 24 to 27,
questions down to 11. All of the recovery is next generation readers (5 to 18 a month); Mr and Mrs Shaw stay at 9. Verdict: **partly working**.

## T4 Stale private fund valuations (risk). Initiative: valuation chase protocol, started 2026-08-17

Questions: how much private fund value rests on a valuation older than 120 days; which administrator; is G03 concentration bought or grown.

K12 stale share and K09 G03 concentration:
```sql
select s.period, s.value as k12_stale_share, c.value as k09_g03_share from gold.k12 s join gold.k09 c using (period) order by period
```

| period | k12_stale_share | k09_g03_share |
|---|---|---|
| 2025-09 | 0.0000 | 0.1239 |
| 2025-10 | 0.0000 | 0.1228 |
| 2025-11 | 0.0000 | 0.1230 |
| 2025-12 | 0.0000 | 0.1242 |
| 2026-01 | 0.0000 | 0.1287 |
| 2026-02 | 0.0000 | 0.1325 |
| 2026-03 | 0.0000 | 0.1352 |
| 2026-04 | 0.0000 | 0.1391 |
| 2026-05 | 0.3327 | 0.1432 |
| 2026-06 | 0.3334 | 0.1469 |
| 2026-07 | 0.3349 | 0.1521 |
| 2026-08 | 0.3313 | 0.1567 |
| 2026-09 | 0.2681 | 0.1600 |

A3 Orchard funds, valuation age at month end:
```sql
select period, holding_id, valuation_date, valuation_age_days from silver.valuations_positions_monthly where holding_id in ('H030','H031','H032','H033') and period >= '2026-05' order by holding_id, period
```

| period | holding_id | valuation_date | valuation_age_days |
|---|---|---|---|
| 2026-05 | H030 | 2025-12-31 | 149 |
| 2026-06 | H030 | 2025-12-31 | 181 |
| 2026-07 | H030 | 2026-03-31 | 122 |
| 2026-08 | H030 | 2026-03-31 | 153 |
| 2026-09 | H030 | 2026-03-31 | 183 |
| 2026-05 | H031 | 2025-12-31 | 149 |
| 2026-06 | H031 | 2025-12-31 | 181 |
| 2026-07 | H031 | 2026-03-31 | 122 |
| 2026-08 | H031 | 2026-03-31 | 153 |
| 2026-09 | H031 | 2026-03-31 | 183 |
| 2026-05 | H032 | 2025-12-31 | 149 |
| 2026-06 | H032 | 2025-12-31 | 181 |
| 2026-07 | H032 | 2026-03-31 | 122 |
| 2026-08 | H032 | 2026-03-31 | 153 |
| 2026-09 | H032 | 2026-03-31 | 183 |
| 2026-05 | H033 | 2025-12-31 | 149 |
| 2026-06 | H033 | 2025-12-31 | 181 |
| 2026-07 | H033 | 2026-03-31 | 122 |
| 2026-08 | H033 | 2026-03-31 | 153 |
| 2026-09 | H033 | 2026-06-30 | 92 |

G03 grows by price, not purchases:
```sql
select count(*) as g03_purchases from silver.valuations_trades_monthly t join silver.master_holdings h using (holding_id) where h.issuer_group_id = 'G03'
```

| g03_purchases |
|---|
| 0 |

**Before and after.** K12 was 0 to 2026-04, 0.33 from 2026-05 to 2026-08 (H030 to H033 carried December and then March valuations, 120 to 183 days old),
and 0.27 in 2026-09 after the protocol got H033's June valuation. K09 drifted from 0.12 to 0.16 with no G03 purchase. Verdict: **too early**: one cycle,
one fund refreshed, three still stale. (The brief's 0.18 to 0.31 path was superseded by the D06 ruling recorded in RESUME-CARDS.)

## T5 Custody fee tier lost at C2 (process cost, not yet acted)

Questions: why did custody fees go up; did assets at C2 cross a tier.
```sql
select a.period, a.assets_month_end_sgd as c2_assets_sgd, k.value as k22_c2_bp from silver.custody_assets_under_custody_monthly a join gold.k22 k on k.period = a.period and k.custodian_id = a.custodian_id where a.custodian_id = 'C2' order by a.period
```

| period | c2_assets_sgd | k22_c2_bp |
|---|---|---|
| 2025-09 | 452,000,000.00 | 6.00 |
| 2025-10 | 455,000,000.00 | 6.00 |
| 2025-11 | 458,000,000.00 | 6.00 |
| 2025-12 | 455,000,000.00 | 6.00 |
| 2026-01 | 454,000,000.00 | 6.00 |
| 2026-02 | 391,000,000.00 | 6.00 |
| 2026-03 | 387,000,000.00 | 9.50 |
| 2026-04 | 392,000,000.00 | 9.50 |
| 2026-05 | 388,000,000.00 | 9.50 |
| 2026-06 | 389,000,000.00 | 9.50 |
| 2026-07 | 395,000,000.00 | 9.50 |
| 2026-08 | 391,000,000.00 | 9.50 |
| 2026-09 | 394,000,000.00 | 9.50 |

Daily accruals name the tier:
```sql
select custodian_id, tier, rate_bp_annual, count(*) as days, round(sum(accrual_sgd), 2) as fees_sgd from silver.custody_daily_fee_accruals group by all order by custodian_id
```

| custodian_id | tier | rate_bp_annual | days | fees_sgd |
|---|---|---|---|---|
| C1 | flat | 5.50 | 98 | 105,312.96 |
| C2 | below 400m | 9.50 | 98 | 100,126.08 |
| C3 | flat | 8.00 | 98 | 66,848.23 |

**Reading.** C2 assets fell from 454m to 391m SGD after the 60m transfer to C1 on 2026-02-16, below the 400m tier; the rate stepped from 6.0 to 9.5 bp.
At about 390m, 3.5 bp is roughly 137,000 SGD a year: the radar should raise it (consolidate back above 400m or renegotiate).

## T6 Unhedged USD (risk, decision pending)

Questions: how much USD is unhedged; when did hedging stop; what did August cost.
```sql
select x.period, x.value as k11_unhedged_sgd, h.value as k26_hedge_cost_sgd, l.value as k27_fx_loss_sgd from gold.k11 x join gold.k26 h using (period) join gold.k27 l using (period) order by period
```

| period | k11_unhedged_sgd | k26_hedge_cost_sgd | k27_fx_loss_sgd |
|---|---|---|---|
| 2025-09 | 294,369,813.73 | 815,790.00 | 0.0000 |
| 2025-10 | 307,009,851.92 | 1,007,290.00 | 316,400.00 |
| 2025-11 | 304,829,816.94 | 950,130.00 | 0.0000 |
| 2025-12 | 304,563,442.28 | 801,850.00 | 0.0000 |
| 2026-01 | 308,962,962.95 | 885,310.00 | 113,240.45 |
| 2026-02 | 312,282,459.53 | 974,430.00 | 0.0000 |
| 2026-03 | 300,978,303.80 | 1,067,780.00 | 216,598.22 |
| 2026-04 | 316,459,328.71 | 984,150.00 | 546,458.43 |
| 2026-05 | 852,431,725.84 | 0.0000 | 0.0000 |
| 2026-06 | 853,243,491.79 | 0.0000 | 1,796,630.65 |
| 2026-07 | 867,710,015.57 | 0.0000 | 2,127,576.60 |
| 2026-08 | 821,960,235.62 | 0.0000 | 47,185,164.63 |
| 2026-09 | 820,315,513.82 | 0.0000 | 4,380,706.76 |

Last forward:
```sql
select max(maturity_date) as last_maturity, count(*) as forwards from silver.fx_forwards_register
```

| last_maturity | forwards |
|---|---|
| 2026-04-30 | 8 |

**Reading.** No forward after 2026-04; K11 climbs as cover runs off and the August SGD move gives the K27 spike. The open Decision
(`initiatives/dec-0001-usd-hedge.json`) has no choice made; the radar should link to it rather than open a new item.

## T7 One view of commitments and calls (wish, no measure)

No SQL: the voices are wall cards, check-in items and a brainstorm idea, each worded differently. Eight records: wall cards `tr-04` (Treasury),
`pf-04` (Performance), `ng-04` (Next generation); check-in items in 2026-W30, 2026-W32, 2026-W36 (`2026-W36-02`, Aaron) and 2026-W41 (`2026-W41-03`,
Mei Ling); brainstorm idea `bs-05`. Loaded as cards `dc-<id>` and week items `dc-<id>`. Voices count by distinct person (ruling, 7 Oct): **five voices**
(Mei Ling Chong 3 records, Harvey Rowley 2, Janet Shaw, Pooja Kapoor, Aaron Lyle). The radar should group all eight into one theme with five voices.

## T8 Volatility makes the pack harder (red herring, reject)

Question: does pack effort follow market volatility?
```sql
select k.period, k.value as pack_hours, v.market_volatility_index as volatility from gold.k03 k join silver.valuations_volatility_monthly v using (period) order by period
```

| period | pack_hours | volatility |
|---|---|---|
| 2025-09 | 48.75 | 17.20 |
| 2025-10 | 50.00 | 16.40 |
| 2025-11 | 50.75 | 15.80 |
| 2025-12 | 51.50 | 16.90 |
| 2026-01 | 48.50 | 18.30 |
| 2026-02 | 52.00 | 20.10 |
| 2026-03 | 55.50 | 31.80 |
| 2026-04 | 55.00 | 29.40 |
| 2026-05 | 53.00 | 21.20 |
| 2026-06 | 40.75 | 17.90 |
| 2026-07 | 31.00 | 17.60 |
| 2026-08 | 30.00 | 30.70 |
| 2026-09 | 32.75 | 19.40 |

Correlation up to July, and with August and September in:
```sql
select round(corr(k.value, v.market_volatility_index) filter (where period < '2026-08'), 2) as to_july, round(corr(k.value, v.market_volatility_index), 2) as all_months from gold.k03 k join silver.valuations_volatility_monthly v using (period)
```

| to_july | all_months |
|---|---|
| 0.4800 | 0.0400 |

What the hours were in the volatile spring:
```sql
select period, cause, hours from silver.reporting_effort_log_monthly where period in ('2026-03','2026-04','2026-08') and hours >= 5 order by period, hours desc
```

| period | cause | hours |
|---|---|---|
| 2026-03 | late_statement_A2 | 18.50 |
| 2026-03 | reconcile | 10.00 |
| 2026-03 | reformat | 9.00 |
| 2026-03 | review | 8.50 |
| 2026-04 | late_statement_A2 | 20.50 |
| 2026-04 | review | 9.50 |
| 2026-04 | reformat | 8.00 |
| 2026-04 | reconcile | 8.00 |
| 2026-08 | reconcile | 9.00 |
| 2026-08 | review | 8.50 |
| 2026-08 | layout | 6.00 |

**Why it breaks.** March and April 2026 are both high-volatility and high-effort, so the months to July correlate at about 0.48. August is as volatile
as March (30.7) with only 30 hours, and the correlation over all thirteen months falls to about 0.04. The effort log attributes the spring hours to
`late_statement_A2` rework, which is T2. The radar must reject T8 with that reason.

## Words: the documents that carry each truth (loaded onto North's shelf)

| Truth | Documents |
|---|---|
| T1 | `text/committee_minutes/2025-12-18_investment_committee_minutes.md`, `text/committee_minutes/2026-03-19_investment_committee_minutes.md`, `text/treasury_notes/2025-11-26_cash_position_note.md`, `text/treasury_notes/2026-03-10_paper_cash_above_floor.md` |
| T2 | `text/operations/2025-10-21_harvey_to_pinecrest_statement_dates.eml`, `text/operations/2025-10-24_pinecrest_reply_statement_dates.eml`, `text/operations/2026-01-22_harvey_call_note_pinecrest.txt`, `text/operations/2026-04-23_harvey_note_statement_template.txt`, `text/operations/2026-06-15_harvey_auto_ingest_live.eml`, `text/operations/2026-07-07_harvey_to_pinecrest_monday_file.eml` |
| T3 | `engagement/feedback_notes/2025-10-09_kerr_mei_xin.md`, `engagement/feedback_notes/2026-03-24_shaw_wei_jie.md`, `engagement/feedback_notes/2026-06-17_kerr_mei_xin.md`, `text/operations/2026-07-20_rahul_one_page_summary_feedback.eml` |
| T4 | `text/compliance/2026-04-28_quarterly_compliance_note.md`, `text/compliance/2026-07-22_quarterly_compliance_note.md`, `text/committee_minutes/2026-08-20_investment_committee_minutes.md`, `text/compliance/2026-09-29_orchard_chase_first_cycle.md` |
| T5 | `text/operations/2026-09-21_harvey_meridian_invoices.eml`, `text/committee_minutes/2026-09-17_investment_committee_minutes.md`, `text/committee_minutes/2026-02-19_investment_committee_minutes.md` |
| T6 | `text/compliance/2026-08-14_policy_exception_usd_hedge.md`, `text/market_briefs/2026-08_market_brief.md`, `text/committee_minutes/2026-04-16_investment_committee_minutes.md`, `text/treasury_notes/2026-10-05_third_quarter_treasury_note.md` |
| T7 | none (voices only, see T7) |
| T8 | `text/analyst/2026-05-11_aaron_note_pack_effort_and_market_conditions.md`, `text/committee_minutes/2026-08-20_investment_committee_minutes.md` |

