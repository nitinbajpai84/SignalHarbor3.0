# Live run 3: analysis of the failing checks

**Status: partial.** 38 of 97 use cases have finished (23 pass, 15 fail). uc-038-navroll is still working. 58 use cases have not reported yet. No case is stuck. Re-run this analysis when run 3 completes.

Read-only analysis. Evidence: reports in `D:/Temp/sh3-live/r3/<uc>.json`; thread files copied from each office's `evergreen/v3/threads/`; warehouse copies (`evidence.duckdb` plus `.wal`) queried with DuckDB, with the copies deleted afterwards; the r2 reports in `D:/Temp/sh3-live/r2/`; git history of `packs/family_office/1/recipes/` and `sh_platform/v1/`. No code, office or server was changed.

Method for the key check: for each missing key, the office's gold tables were searched for the number (tolerance 0.006). A key found in a bound table means the answer path dropped it (c). A key found only in an unbound table means binding (a). A key found in no table means the table or its input is wrong (b or f).

## Counts per class (15 FAIL cases)

| Class | Meaning | Count | Cases |
|---|---|---|---|
| (a) | Not bound to the recipe that answers the key | 1 | uc-015 |
| (b) | Bound, but the ready table is empty or missing | 1 | uc3 |
| (c) | The answer omits key numbers that the bound table holds | 5 | uc-008, uc-026, uc-033, uc-040, uc5 |
| (d) | Persona check too strict | 0 | none (see note) |
| (e) | Stuck | 0 | none |
| (f) | Other | 8 | uc-002, uc-004, uc-006, uc-007, uc-018, uc-034, uc-039, uc6-uncalled |
| | Total | 15 | |

Note on (d): the check is not the cause. uc-002, uc-004, uc-006, uc-018 and uc6-uncalled passed in r2 with the same expected keys and the same ask. Their r3 answers changed (see the regressions below), so the check did not change.

## Per-case evidence and fix

| Case | r2 | Class | Evidence (one line) | Fix |
|---|---|---|---|---|
| uc-002-callrecord | pass | f (regression) | Call 7 notice (-1,250,000, due 23 Oct) is a noticed movement on stub commitment `fffd0e38` (6,000,000, under Entity B, no source record). The called-to-date recipe skips shadow rows, so noticed_not_recorded is 0 for Cedarpoint Ventures III. 7,250,000 and 2,750,000 are in no table. Answer gives 4,550,000 before and after. | Post the notice to the commitment of the entity it names (Evergreen Holdings, CV III, 10,000,000). Stop the shadow filter from silently dropping noticed movements. |
| uc-004-callcheck | pass | f (regression) | cash_after_calls sums open calls to 4,850,000 = 3,600,000 overdue noticed calls + 1,250,000 (23 Oct). Keys 270,000 and 361,800 need the 23 Oct call alone. r2 answered 270,000 and 361,800. | Show the 23 Oct call apart from the overdue calls and give cover for the named call. Confirm why the 3.6M is open in r3 (seed or recipe). |
| uc-006-fxneed | pass | f (regression) | fx_required sizes the conversion on the total shortfall of 3,870,000 (5,185,800 SGD), not the 270,000 for the 23 Oct call. 361,800 is absent. | As uc-004. |
| uc-007-pacing | fail (c) in r2 | f | Unfunded 15,850,000 before and after. 14,600,000 needs call 7 applied (CV III unfunded 2,750,000 after it). The notice is dropped, as in uc-002. | As uc-002. |
| uc-008-payrun | pass | c (regression) | 5,400 is Summit Tax Advisory, state ready, due 14 Oct, in the bound batch table. Answer lists five release rows then "and 14 more", so 5,400 is cut. r2 listed it first. | List every release row, or sort by due date and state the count. Do not truncate set answers. |
| uc-015-allowances | fail (a) | a (repeat) | "Cash availability" is bound to cash_movements_monthly_by_entity (scheduled flows), not the cash balance. 213,895.52 (Family Trust cash) is in no bound table. funding_headroom has 0 rows. Answer gives September, not October, and no amounts (8,000 / 6,000 / 5,000 / 4,000 absent). | Bind cash availability to the cash-by-entity balance. Answer the current month with the scheduled amounts. |
| uc-018-fundplan | pass | f (regression) | funding_plan measures cover against all open calls (Holdings -3,870,000; Entity B -1,731,656.04). 270,000 and 618,343.96 (Entity B spare after buffer, before its own call) are absent. r2 answered both. | As uc-004. Show per-call and total cover. |
| uc-026-stmtadmin | fail (a) | c (repeat) | Bound table holds both sides (statement 10,180,000 vs administrator 10,000,000, and so on). Answer gives the differences only. | Give both values and the difference for each fund. |
| uc-033-breachesc | fail (b) | c (repeat) | Bound single_name_breach row holds cost_to_cure 324,210.53 and portfolio_total 41,200,000. Answer gives only exposure 2,368,000. Side issue: "Required sell amount" is bound to commitments_monthly_by_entity (rows dated 2021 to 2025, unrelated). | Print cost_to_cure for a cost-to-cure question. Fix the sell-amount binding. |
| uc-034-prospect | fail (a) | f (repeat) | Binding is now right (mandate_fit, called_to_date). Uncalled is 15,850,000, not 14,600,000, because the notice is dropped (as uc-002). "Existing exposure link" has no recipe and 0 rows. | As uc-002. Bind the exposure link. |
| uc-039-irr | fail (e) | f (repeat) | 5 of 8 funds are irr_status incomplete (history gaps 0.5M to 1.2M). Sources list has no bank_balances_feed or manual_adjustments. Answer fell back to "Rules-only reply". | Load the missing history inputs. Answer with the incomplete flag, not the rules-only fallback. |
| uc-040-icmemo | fail (a) | c (repeat) | Bound tables hold 10,000,000 (commitment) and 8,275,000 (amended value). Answer fell back to "Rules-only reply". 350,000 (fee on call 7) is in no bound table. 7,250,000 and 2,750,000 are dropped, as in uc-002. "amended" status is in no bound table. | Answer from the bound tables. Bind the fee check to the memo. Fix the notice. |
| uc3-statements-inbox | fail (a) | b (repeat) | "Statement receipt timeliness" is bound with 0 rows. Answer gave 65 as a plain weekday count and called it business days. 63 needs a holiday calendar. days_overdue is blank for most rows. | Build statement_timeliness with a business-day calendar. |
| uc5-limits | fail (b) | c (repeat) | Bound single_name_breach row: Harborview 5.75% against a 5% limit, "real breach", cost to cure 324,210.53. Answer says no holding is over its limit and quotes 4.21% from the 13 Oct concentration table. This is a wrong answer. | Answer breaches from the breach table. Use the concentration table only for the largest-share question. |
| uc6-uncalled | pass | f (regression) | Same as uc-002: 15,850,000 before and after. 14,600,000 is absent. | As uc-002. |

## Regressions (passed in r2, fail in r3)

Six cases: uc-002, uc-004, uc-006, uc-008, uc-018, uc6-uncalled.

- **Notice dropped (uc-002, uc6-uncalled):** the notice sits on a stub commitment under Entity B. The recipe's shadow rule, in place since commit 9ca0091 (17 Oct, 19:47), then excludes it. r2 had the notice on the right commitment, so the cause is in how the r3 office loaded the notice.
- **Overdue calls counted (uc-004, uc-006, uc-018):** r3 counts 3.6M of noticed, overdue calls for Holdings. r2 did not. Whether the r3 seed has these calls, or the calls_due or funding recipe changed, is not yet confirmed.
- **Answer truncation (uc-008):** the answer format cut the list. r2 listed 5,400 first.

Context: r3 ran on commit 1f56bdc (00:26, 18 Oct), which changed figure binding and the held-table test in `v3_figures.py` and `v3_recipes.py`. It is a candidate for the answer-path changes, but I did not verify it per case. To split recipe from data: re-run the six regressions on a copy of 9ca0091 and on HEAD, with the same seed.

## Repeats (same use case failing again after the r2 fixes)

| Case | r2 class | r3 class | Status |
|---|---|---|---|
| uc-007-pacing | c | f | Still failing; cause changed to the notice drop |
| uc-015-allowances | a | a | Same: cash still bound to flows, not balance |
| uc-026-stmtadmin | a | c | Binding fixed; answer omits values |
| uc-033-breachesc | b | c | Table now holds data; answer omits cost to cure |
| uc-034-prospect | a | f | Binding fixed; notice drop |
| uc-039-irr | e | f | Same: incomplete history |
| uc-040-icmemo | a | c | Still on rules-only fallback |
| uc3-statements-inbox | a | b | Bound now, to a 0-row figure |
| uc5-limits | b | c | Table now present; answer picks the wrong figure |

r2 fixes that held (failed in r2, pass in r3): uc-013, uc-016, uc-017, uc-023, uc-024, uc-031, uc-032, uc-035 (8 cases).

## Top 5 fixes, ranked by cases fixed

1. **Answer path (5 cases: uc-008, uc-026, uc-033, uc-040, uc5).** Print every key column the bound table holds. Do not truncate set answers. Answer breaches from the breach table, not a snapshot. Do not fall back to "Rules-only reply" when the bound figures are present.
2. **Called-to-date notice (4 cases: uc-002, uc-007, uc6-uncalled, uc-034; partial for uc-040).** Post the noticed call to the commitment of the entity it names. Stop the shadow filter dropping noticed movements silently, or flag them.
3. **Calls-due scope (3 cases: uc-004, uc-006, uc-018).** Show the named call and the overdue calls as separate lines. Compute cover for the named call. Establish whether the 3.6M overdue noticed calls belong in the r3 seed.
4. **Ready tables empty or missing (2 cases: uc3, uc-039).** Build statement_timeliness on a business-day calendar. Load the missing history inputs for the IRR figures.
5. **Cash availability binding (1 case: uc-015).** Bind cash availability to the cash-by-entity balance, not the scheduled-flow table. This also clears funding_headroom (0 rows).

## Side findings

- uc-033: "Required sell amount" is bound to commitments_monthly_by_entity (unrelated rows, dated 2021 to 2025).
- uc-040: the 350,000 fee on call 7 is in call_fee_check, but no memo figure is bound to it.
- uc-034: "Existing exposure link" has no recipe and 0 rows.
- The answer field keeps only the sentence, and the check also scans the answer rows, which are not saved. A "missing" key here means absent from the whole answer. This is the r2 harness note, still open.

## Not yet covered

58 use cases have not reported, and uc-038 is still working. Their classes are unknown. Re-run after the run completes.
