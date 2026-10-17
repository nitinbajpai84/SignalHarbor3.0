# Live run 3, part B: use cases 51-100 and the stuck cases

**Status: complete.** Read-only. No code, office or server was changed. Run 4 was not touched.

Scope: the 50 use cases in `packs/family_office/1/use_cases_100.yaml` with no priority or priority above 50 (uc8, uc-052 to uc-100). uc-043 is priority 43, outside the scope, but it is one of the four stuck cases, so it is covered in the stuck rows.

Evidence and method:
- Reports: `D:/Temp/sh3-live/r3/<uc>.json` and `log-<uc>.txt`.
- Threads: copied from each office's `evergreen/v3/threads/` to `D:/Temp/r3b-scratch/threads/`. Read: `bindings`, `figures` (table, rows, ok, reason), `figure_notes`, `held_tables`.
- Warehouses: `evidence.duckdb` and `.wal` copied per office to `D:/Temp/r3b-scratch/wh/`, then queried read-only. Each expected key was searched in every table (numbers with tolerance 0.006, and x100 variants; names and dates as text).
- Location of each missing key: BOUND = found in a gold table that a figure in the thread is bound to. SOURCE = found only in a source table. ABSENT = found in no table. UNBOUND_GOLD was never seen: a gold table is built only for a bound figure.
- Recipe metadata: `packs/family_office/1/recipes/*.yaml`, read for names, words_all, answer and cards.
- Copies in `D:/Temp/r3b-scratch` are deleted after this report is written.

Classes: (a) not bound to the answering recipe; (b) bound, but the table is empty, missing or held at decision 3; (c) the answer omits key numbers that a bound table holds; (d) the check is too strict or loose; (e) stuck; (f) other.

## Counts

Scope: 50 use cases.

| Result | Count | Use cases |
|---|---|---|
| PASS | 2 | uc-057, uc-062 |
| FAIL | 42 | see table |
| STUCK (in scope) | 3 | uc-052, uc-059, uc-094 |
| NOT RUN (no report) | 3 | uc-072, uc-084, uc-096 |
| STUCK (outside scope) | 1 | uc-043 (priority 43) |

Classes for the 42 FAIL cases (one primary class each; the second class is in brackets in the table):

| Class | Meaning | Count |
|---|---|---|
| (a) | Not bound to the answering recipe | 13 |
| (b) | Bound, but empty, missing or held | 6 |
| (c) | Answer omits key numbers the bound table holds | 21 |
| (d) | Check too strict or loose | 0 (two weak checks noted, uc-061 and uc-099) |
| (e) | Stuck | 3 in scope, plus uc-043 outside scope |
| (f) | Other | 2 |
| | Total FAIL | 42 |

Answer patterns across the 42 failures:
- "one of N rows" or "and N more" truncation: 8 cases (uc8, uc-055, uc-061, uc-083, uc-089, uc-091, uc-093, uc-100). uc-057 and uc-062 pass with this pattern, so truncation is not always a failure.
- "Rules-only reply" fallback: 5 (uc-073, uc-074, uc-077, uc-082, uc-098). Each has a bound table with the key values.
- "Not available yet": 5 (uc-058, uc-060, uc-071, uc-095, uc-099).
- Answer about the wrong figure or wrong topic: uc-053, uc-054, uc-067, uc-068, uc-069, uc-070, uc-079, uc-085, uc-092, uc-097.

## Table: uc | class | evidence | fix

| uc | class | evidence | fix |
|---|---|---|---|
| uc8-trades-vs-admin | b | "Mismatched trade amount" is bound to trade_breaks (43 rows) and reads 0; the thread says "awaiting administrator file". 75,870 is in no table; 592,000 is only in source tables (cash_movements, transactions). | Intake: load the administrator's October confirmations. Then bind the mismatch figure. |
| uc-053-watchlist | a | "Managers with statement issues" is bound to missing_statements by definition, not by name. watch_flags (cards 53, no words_all, no answer) is unbound and not built. Answer lists 12 funds at 0. | names and words_all for watch_flags (late, restated, personnel change, last 90 days); stop the definition bind to missing_statements; answer template for watch_flags. |
| uc-054-ladder | a | liquidity_ladder (cards 54) is unbound and not built. "Cash buffer status" is unbound (0 rows). Scheduled payments are bound to a cash_movements table, not the ladder. All 8 expected amounts are in no table. | names and words_all for "cash less calls in 30, 60, 90 days" on liquidity_ladder; bind cash buffer; answer template. |
| uc-055-corpact | c | actions_next_14d is bound (12 rows) and holds 31.5, 29.28, 7.58, 70,000 and 58,500. Answer gives the total only ("over 10 rows"). "Timeliness of election decisions" is unbound. | Answer template: each action with date and amount, never only the total. Bind the timeliness figure. |
| uc-056-custrecon | c [b] | position_break is bound (20 rows) and holds 18,940; answer lists 2 rows. 60,062.5 is in no table: custody_positions (needs_new) is absent from all 47 warehouses. | Answer template: all breaks for the month. Intake: load custodian positions. |
| uc-058-settle | b | unsettled_trades is held at decision 3: data_export.xlsx "All 4 rows are held back"; row 2 has no portfolio. statement_timeliness is bound to this question (wrong). settlements (needs_new) is absent. | Readers and intake: why data_export.xlsx rows are held back. Add settlements source. Fix the bad bind. |
| uc-060-docinbox | b | unrecognised_files is bound, with 0 rows. The three file names are in documents and source_batches, but not in the unrecognised table. | Readers and intake: unrecognised_files must list unmatched intake files. Add names, words_all and answer. |
| uc-061-dqscore | f [d] | source_quality is bound (6 rows) and gives manual-fix percentages. 71.4 is in no table: there is no composite score. "administrator_cash" is a column name, not a value, so the check is too strict. | Add the composite quality score to source_quality. Replace the check key with a value. |
| uc-063-cashcode | c | uncoded_bank_lines is bound (3 rows) and holds 48,250 and -3,980; answer gives one line (CHQ-000417). 42,120 is in no table. | Answer template: each bank line with its amount. Check whether 42,120 is a sum that is not stored. |
| uc-064-fxexp | c [b] | currency_exposure is bound and holds 6 of 7 expected values (including 112,272,239.48). Answer gives only the two net totals. The SGD forwards table has 0 rows. | Answer template: per currency, gross and forwards. Fix the sgd_forwards source. |
| uc-065-realassets | c | real_asset_value is bound (6 rows) and holds all 6 values; answer gives RA-04 only. | Answer template: one line per asset and a total. |
| uc-066-propreval | c | appraisal_age is bound (6 rows) and holds 784, 378, 353, 329 and 225; answer gives RA-04 only (125 days). | Answer template: each asset with days since appraisal; flag above 365. |
| uc-067-unrl | a | unrealised_gain (cards 67) is unbound and not built; tax_lots is present (66 rows). Answer prints per-fund values (a different figure). | names and words_all for "unrealised gain by lot"; bind; answer template. |
| uc-068-incomef | a | income_forecast (cards 68) is unbound. "Quarterly liquid book income" is bound to nothing and built from a 1-row table. Answer prints 2.0722 (a ratio). All 8 expected values are absent. | names and words_all for income_forecast; bind; answer template. |
| uc-069-lookthru | a | lookthrough_exposure (cards 69) is unbound and not built; fund_holdings is present (31 rows). Answer gives unfunded commitments (commitments_by_fund bound). | names and words_all for "look-through exposure by company"; bind; answer template. |
| uc-070-idle | a | idle_cash (cards 70) is unbound; "Cash headroom" is unbound; liquidity_ladder is not built. Answer prints balances. All 6 expected amounts are absent. | Bind idle_cash (after the ladder); names and words_all; answer template. |
| uc-071-expdist | b | expected_distributions is bound but not built (0 rows, ok false, reason blank). Its needs say no manager distribution outlook (projected_payout_rate) is loaded. | Intake: manager distribution outlook. Show needs[].why as the reason (it is blank now). |
| uc-073-runway | c | cash_runway is bound (13 rows) and holds all 6 expected values. Answer is the "Rules-only reply" fallback. cash_runway has no answer template. | Answer template for cash_runway. In v3_figures, no rules-only fallback when a bound table has rows. |
| uc-074-boardpack | c [a] | "Rules-only reply". board_summary (cards 74) has no answer and no words_all, and is not bound. 5.7563 is in the bound TWR table; 6,156,041.41 is cash_runway, which is unbound. | Answer template for board_summary; names and words_all; bind the runway figure. |
| uc-075-yearwalk | c | networth_walk is bound (1 row) and holds 1,514,870, 1,263,862.76 and 767,500. Answer gives the closing value only. | Answer template for networth_walk: opening, gains, income, spending, closing. |
| uc-076-scorecard | f | manager_score is built (6 rows); "score 50" matches Meridian's row (50.0). The expected 98.3, 86.8 and 45.4 are in no column. Its needs require signed scorecard weights, yet scores are written with weights 0.4/0.2/0.2/0.2. | Check whether manager_score_weights is approved for this office; if not, hold the score (enforce needs). Confirm the expected values with the generator. |
| uc-077-deals | c | deal_stage is bound (6 rows) and holds the deal names (Marlow, Ashgrove) and counts. Answer is the "Rules-only reply". 13,000,000 is in no table. | Answer template for deal_stage: name, stage, days in stage. |
| uc-078-redemption | b [a] | redemption_dates is bound but not built (dealing date None). fund_terms (needs_new) is absent from all warehouses. "Last notice date" is bound to vendor contracts (wrong table). Answer gives cash by entity. | Intake: fund terms. Fix the wrong bind. Answer template. |
| uc-079-rebalance | a | rebalance_trades (cards 79) is unbound and not built. Answer is "Time-weighted return: the figures are below" (wrong figure). 4 of 5 expected values are absent. | names and words_all for "amounts to trade to reach target"; bind; answer template. |
| uc-080-vintage | c | vintage_split is bound (6 rows) and holds all expected shares and years. Answer lists names and amounts, not the shares. | Answer template: amount and share by year. |
| uc-081-payroll | c | payroll_total is bound (10 rows) and holds 100,224, 21,297.6, 113,199 and 93,360. Answer gives per-person net pay only. "Total payroll amount" is unbound. | Answer template with totals; bind the total figure. |
| uc-082-covergap | c | cover_gap is bound (6 rows) and holds -820,895.52 and -4,776,119.4 and the asset names. Answer is the "Rules-only reply". cover_gap has no answer. | Answer template for cover_gap; no rules-only fallback when rows exist. |
| uc-083-taxcal | c [a] | tax_due is bound (6 rows) and holds TX-01, TX-02 and TX-04. Answer gives "items 1, one of 3 rows". "Payment due date" is bound to cash_movements (wrong table). | Answer template: every item. Fix the payment-date bind. |
| uc-085-grants | a | "Annual grant budget" is bound to missing_statements (185 rows), a wrong table. Answer gives one grant (300,000). grants_used (5 rows) holds 175,000, 90,000 and 265,000. | Bind the budget to the grants table; names and words_all; answer template. |
| uc-086-grantappr | a | "Budget remaining" is unbound. grant_check (1 row) holds only the cash buffer. 1,250,000 is in no bound table; -70,000 is in none. | Bind the budget to grants_used; names and words_all; answer template for grant_check. |
| uc-087-trustdist | c | trust_distribution_room is bound (4 rows) and holds 504,980.42, 46,001.31 and -2,297.17. Answer prints trust year income (the wrong column). | Answer template: distribution room per beneficiary. Choose the room column. |
| uc-088-estateliq | c | estate_cash_need is bound (1 row) and holds 131,306,339.91, 109,960,000, 55,879,741.41 and 2.95. Answer gives the transfer tax only. | Answer template for estate_cash_need. |
| uc-089-expapp | c | approval_exceptions is bound (151 rows) and holds all four expected keys. Answer: "payments 1, one of 151 rows". | Answer template: every over-limit payment; no truncation. |
| uc-090-offcost | c | office_cost is bound (13 rows) and holds 1,455,850 and 35,752.48. Answer gives overspend flags by category only. | Answer template: category, actual and budget, with totals. |
| uc-091-jml | c | access_review is bound (38 rows) and holds Sam Lee, Wei Tan and J. Ng. Answer: "grants 1, one of 38 rows". "Holding reconciliation accuracy" is unbound. | Answer template: each joiner, mover and leaver. |
| uc-092-accessrev | a | access_review is not bound for "Idle grants count"; the figure reads an unrelated table (grants by entity). Answer is about the user's own access. Expected names are in system_access_grants (source only). | names and words_all for "access not used in 90 days" on access_review; bind. |
| uc-093-onbmgr | c | onboarding_items is bound (5 rows) and holds "Statement schedule" and checklist state. Answer: "complete 1, one of 3 rows". "Onboarding completion time" is unbound. | Answer template: every item with its state. |
| uc-095-sopreview | a | sop_age (cards 95) is unbound. "Procedures overdue for review" has no binding and no table. Expected SOP titles and ages are in no table. | names and words_all for "SOPs by last review"; bind; answer template. |
| uc-097-kycrefresh | a | kyc_expiry (cards 97) is unbound. Answer is about the call-back account (bank_details_changed is bound). Expected dates are in no table. | names and words_all for "documents expiring in 90 days"; bind; answer template. |
| uc-098-wordlist | a | terms_proposed (cards 98) is unbound and not built. Answer is the "Rules-only reply". Expected words appear only in documents and extracted fields. | names and words_all; bind; answer template; build the proposed-terms table. |
| uc-099-newfeed | b [d] | feed_mapping is bound and has 0 rows ("feed mapping has no rows"). The expected "Value" is a column label that matches almost anything, so the check is weak. | Readers: produce feed mappings for the new file. Tighten the check to a value. |
| uc-100-famaccess | c | member_access is bound (12 rows) and holds Entity B and Evergreen Holdings. Answer: "pairs 1, one of 4 rows". | Answer template: each member and entity, with over-grants flagged. |

Stuck (e):

| uc | class | evidence | fix |
|---|---|---|---|
| uc-052-insurance | e | Stuck on the question "The plan has no tables". insurance_policies (needs_new) is absent from all warehouses. The insurance schedule PDF is in the dropbox but not read into a table. renewals_due is bound but nothing is built. | Reader for the insurance schedule PDF into insurance_policies. A plan with no tables should fail, not ask. |
| uc-059-breakage | e | Stuck at "POST .../architecture/pack/generate answered 500". break_age (cards 59) is unbound (no bindings at all). The shared server log shows slow pack/generate calls and a reader crash (bank_statements, doc_period None, v3_pack_readers.py:808). Neither is confirmed as the 500. | Find the 500 traceback for this run. Guard the reader. Bind break_age. |
| uc-094-onbbank | e | The build SQL for "Signatory-compliance rate" fails with DuckDB `avg(BOOLEAN)` on gold_no_account_opens_until_its_sig_signatory_metrics. The figure is bound to account_setup, which has no answer and no words_all. | In the build SQL check, cast booleans before avg. Add words_all and an answer to account_setup. |
| uc-043-liquidpnl (outside scope) | e | Playwright POST /decide timed out after 300 s at decision1. No trace for thread t-0d4e1fc3c5 in server.log, and no thread folder. | Find the slow decide call. Retry. Check state.json for resume. |

Not run (no report): uc-072-cashfc, uc-084-taxest, uc-096-automation. Run these before counting them.

Pass (no action): uc-057-pricecheck, uc-062-fxlife.

## Recipes that need names, words_all or answer templates

Names and words_all (recipes with cards in scope and no words_all): access_review, account_setup, actions_next_14d, appraisal_age, approval_exceptions, automation_score, board_summary, cash_forecast, cover_gap, currency_exposure, deal_stage, estate_cash_need, expected_distributions, grant_check, grants_used, idle_cash, income_forecast, kyc_expiry, lookthrough_exposure, manager_score, member_access, networth_walk, office_cost, onboarding_items, payroll_total, price_gap_pct, real_asset_value, rebalance_trades, redemption_dates, renewals_due, sop_age, tax_due, terms_proposed, trust_distribution_room, unrealised_gain, vintage_split, watch_flags.

Unbound figure phrases that need a name (from the threads): "Cash buffer status", "Cash headroom", "Cash drag", "Fee ratio", "Liquidity runway", "Scheduled payments 30/60/90-day", "Quarterly liquid book income", "Budget remaining", "Annual grant budget", "Idle grants count", "Grants removed this quarter", "Procedures overdue for review", "Total payroll amount", "Payment due date", "Last notice date", "Timeliness of election decisions", "Onboarding completion time", "Data completeness %", "Stale-valuation share", "Duplicate holdings count", "Holding reconciliation accuracy".

Answer templates (recipes with cards in scope and no answer; the 48 in-scope recipes, of which 37 have no answer): liquidity_ladder, idle_cash, cash_runway, cash_forecast, currency_exposure, actions_next_14d, real_asset_value, appraisal_age, unrealised_gain, income_forecast, lookthrough_exposure, vintage_split, watch_flags, expected_distributions, manager_score, deal_stage, redemption_dates, rebalance_trades, renewals_due, cover_gap, payroll_total, access_review, onboarding_items, sop_age, automation_score, kyc_expiry, terms_proposed, tax_due, grants_used, grant_check, trust_distribution_room, approval_exceptions, office_cost, account_setup, member_access, estate_cash_need, position_break, price_gap_pct, unsettled_trades, source_quality, fx_mtm, trade_breaks, break_age, unrecognised_files, feed_mapping, uncoded_bank_lines, board_summary, networth_walk. Also missing_statements (used by uc-053 and uc-085; no answer).

## Ranked fix list

Ranked by cases. Each group names the files it owns, so up to four fixers can run in parallel without edits to the same file.

1. Answer path (class c, 21 cases; several of these also have a binding or input gap noted in the table). Fix in `sh_platform/v1/v3_figures.py`: no "Rules-only reply" fallback when a bound table has rows; no "one of N rows" truncation on set answers; print the key columns the figure holds. Cases: uc-055, 056, 063, 064, 065, 066, 073, 074, 075, 077, 080, 081, 082, 083, 087, 088, 089, 090, 091, 093, 100.
2. Binding (class a, 13 cases). Fix names and words_all on the recipes listed above, and stop the wrong definition binds (uc-053, uc-085, uc-078, uc-083 payment date). Cases: uc-053, 054, 067, 068, 069, 070, 079, 085, 086, 092, 095, 097, 098.
3. Readers and intake (class b, 6 cases, plus uc-056 and uc-052). Load the administrator confirmations (uc8), the data_export.xlsx hold-back cause (uc-058), the unrecognised-file list (uc-060), the manager distribution outlook (uc-071), fund terms (uc-078), the feed mapping (uc-099), the insurance schedule (uc-052), and custodian positions (uc-056).
4. Other and stuck causes: uc-061 and uc-076 (f); uc-043, uc-052, uc-059 and uc-094 (e).

File ownership for four parallel fixers (no shared files):

- **Fixer A (binding and answers, cash and hold):** `sh_platform/v1/v3_recipes.py` (binding logic and the definition-bind misfires), `packs/family_office/1/recipes/cash.yaml`, `packs/family_office/1/recipes/hold.yaml`. Covers uc-054, 055, 064, 065, 066, 067, 068, 069, 070, 073, plus the bind fix for uc-053 and uc-085.
- **Fixer B (binding and answers, invest and office):** `packs/family_office/1/recipes/invest.yaml`, `packs/family_office/1/recipes/office.yaml`. Covers uc-053, 071, 076, 077, 078, 079, 080, 081, 082, 083, 085, 086, 087, 088, 089, 090, 091, 092, 093, 095, 097, 098, 100, and the stuck account_setup (uc-094).
- **Fixer C (binding and answers, operate and report):** `packs/family_office/1/recipes/operate.yaml`, `packs/family_office/1/recipes/report.yaml`. Covers uc8 (trade_breaks), 056, 058, 059 (break_age), 060, 061, 063, 074, 075, 099.
- **Fixer D (answer logic and readers):** `sh_platform/v1/v3_figures.py` (fallbacks and truncation, class c logic), the readers and intake files (`sh_platform/v1/v3_pack_readers*.py`), and the stuck causes (uc-043 decide timeout, uc-052 insurance reader, uc-059 pack/generate 500, uc-094 build SQL boolean cast).

Note: Fixers A, B and C each edit recipe YAML only in their own files. The answer logic for recipes in a file that another fixer owns must go through the owner of that file.

## Notes and limits

- "Absent" keys are not proof of a missing table. Some expected values may be derived sums that are not stored. Check each one against the recipe formula before fixing it.
- The server log (`D:/Temp/server.log`, 10 MB) is shared across runs. The stuck links for uc-059 and uc-094 are therefore partial. The uc-094 failure is confirmed by the report's own error text.
- The uc-076 expected values (98.3, 86.8, 45.4) do not match the table. Either the check uses different inputs, or the score is computed differently. This is unresolved.
- Many class (c) cases need only an answer template in a recipe YAML, not a code change. The fastest first step is Fixer A and B writing templates for their files.
- No code, office or server was changed. Run 4 was not touched.
