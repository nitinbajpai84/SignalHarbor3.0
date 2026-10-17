# W1 build: Hold and maintain (key `hold`)

Six cards of priority 1 to 50 have the domain "Hold and maintain": 13, 17, 21, 31, 38, 43. All six are done. Synthetic data only (Evergreen Office, `tests/v1/fixtures/office6m`).

Files: `packs/family_office/1/recipes/hold.yaml`, 21 files `packs/family_office/1/signals/uc-0NN-<card>-*.yaml`, `packs/family_office/1/builds/hold.yaml`, `tests/v1/test_w1_hold.py`, this page.

Test run (after the second pass, w2-fix-hold): `pytest tests/v1/test_w1_hold.py -q -p no:cacheprovider --basetemp=D:/Temp/pyt-w2-hold` gives **23 passed, 0 failed** (was 15).
How the tests load: a small DuckDB with the model's tables (`docs/v2/evidence-to-action-mvp.duckdb.sql`); the office6m files are read by small readers in the test (xlsx, csv, pdf text) and written to the tables; the recipe SQL comes from `v3_recipes.render`, is checked with `refusal` / `tables_read` (only `may_read` tables) and `tie_out`, then compared with `answer_keys.yaml`. No expected number is typed in the tests: they come from the key, or from the statement files read again (the manager's gain line). Signals are run in the tests through the engine's own parser (`v3_signals.calc` and `render`) over the recipe rows, with the engine's `by` rule (exactly one row, else skipped), so each exception signal is shown firing, not firing, or skipped on the data. Extra cases (an exited holding, a negative loan, a closed facility, a second facility, an unread gain line, an estimate, a second book, a jump on an earlier day) are built from synthetic rows added in the test; none drops rows from a recipe table to make it pass.

## Pass 2 (w4-fix-hold, 17 Oct 2026): the scorecard's hold cards

Scorecard: `tools/score50.py` (docs/v3/SCORE50.md). Cards 13, 17, 21, 31, 38, 43 before the pass: 13 FAIL, 17 FAIL, 21 PASS, 31 FAIL, 38 SIGNAL, 43 PASS. After: 13 PASS, 17 PASS, 21 PASS, 31 PASS, 38 SIGNAL, 43 PASS. Test: `tests/v1/test_w1_hold.py` 23 passed, 0 failed (4 tests moved to the corrected rules, one renamed; no test removed).

| card | before | after | why |
|---|---|---|---|
| 13 | FAIL: value 1,119,900 against 1,122,000 | PASS | The figure read each instrument at its own latest date (13 Oct for the listed holdings). The key and the policy measure limits at the month end (policy section 3), so the figure is now at the latest month end loaded (30 Sep). The found signal fired on the first row of each currency, not on the gap instrument, so the planted missing class was never caught; it now fires once for each instrument with a gap (`by: has_gap`), naming it. |
| 17 | FAIL: family net worth 118,361,314 against 108,230,000 | PASS | The family totals counted the four cash portfolios (bank balances and the administrator's cash, instrument type cash). Policy section 1 scopes the figures to the investment portfolios, so cash is left out of `net_worth_after_debt`; the tie-out is adjusted to match. Debt is unchanged. |
| 21 | PASS | PASS | Unchanged. |
| 31 | FAIL: total 118,361,314 against 108,230,000; by-class share off on private equity (15.77 against 15.76) | PASS | Same cash rule: cash is left out of the allocation and of `positions_total`, so the not-adding-up check compares like with like. Shares are kept to four decimals: each row was rounded to two, and the sum of three rounded rows made 15.77. |
| 38 | SIGNAL: the unexplained signal fires on Growth I (396,980) and Income II (182,582) | SIGNAL: only Growth I, at -12,500 | The manager's gain line on a monthly statement covers that month only (the Sep statement reads opening 9,400,000 + 780,000 = 10,180,000), but the roll-forward compared a quarter with it. The quarter's gain is now the sum of the net gain lines of the statements dated in the quarter; a quarter with a statement missing is unreadable, not guessed. Income II and Growth I Q2 now tie to the cent. The -12,500 left is the planted short-paid distribution (M19: notice 275,000, bank 262,500); the statements' gains assume the gross notice amount, the roll uses the cash received. No signed rule says which to use, so the difference is left in and the signal keeps saying so. |
| 43 | PASS | PASS | Unchanged. |

Other changes in the pass:
- `identifier_gaps` tie-out and grain follow the month end; the CTE is `month_end` (`asof` is a DuckDB keyword).
- `nav_rollforward`: new CTEs `mobs`, `monthly`, `freq` (statements per quarter: 3 when the fund reports monthly, else 1), `qg`; `reported_gain` and `gain_unreadable` come from `qg`.
- Test changes: card 13 tests read the month end (a 13 Oct custodian file is loaded and does not move the figure); card 38 helper `quarter_gain`; the estimate test uses Growth II (quarterly), because a monthly fund needs its three months.
- Scorecard limit, not changed here (tools/score50.py is not this domain's file): card 38 has no planted-mess entry for M19, so the -12,500 is scored as "fires on a clean row". It is a real difference, so the scorecard's MESS list for uc-038 should add M19. Decision for the orchestrator.

Other tests run against the hold recipes: `tests/v1/test_v3_recipes.py` has 2 failures, both from files other domains are editing (`allowance_due` in `family.yaml` is still matched, and the stub-count check); not caused by this pass.

## Verifier rows (docs/v3/w1/verify-hold.md): fixed or not

| card | verifier row | status | what was done, or why not |
|---|---|---|---|
| 13 | Holdings with no position rows count as gaps at zero value | fixed | `identifier_gaps` now starts from what is held (a market value other than zero at the instrument's latest position date) and joins the master to it. A master-only or sold-out instrument has no row. Test `test_13_an_instrument_not_held_is_not_a_gap`. |
| 13 | Each instrument at its own last date, totals mix dates | fixed as far as the data allows | The rule stays (an instrument is carried at its latest position, because administrator files are monthly and custodian files daily), but the row now says it: `as_of_min`, `as_of_max`, `mixed_dates`. The found signal prints the date range. A holding that dropped out of the latest custodian file cannot be told from a monthly one without the platform's source calendar (needs the platform loader to say which file each position came from). Test `test_13_holdings_at_different_dates_are_said_to_be_so`. |
| 13 | Signal title says "unclassified" but counts no-identifier; completed message says "recompute" | fixed | Titles and messages say "no class or identifier"; the completed message says what is true (every instrument held has both). |
| 17 | Debt summed as stored, no sign guard | fixed | `debt` is `sum(abs(drawn_amount))` (A5: the statement shows the balance negative; the amount owed is positive). The test loads the loan negative as the file has it and gets the key. |
| 17 | Closed facilities still count in debt | fixed | The latest row of each facility is chosen first, then a closed one is dropped (so an older active row is not picked up by mistake). Test `test_17_closed_facility_owes_nothing...`. |
| 17 | Covenant check reads only the latest-dated facility; headroom mixed across currencies | fixed | `facility_headroom.first_row` is, per currency, the facility with the least headroom (a facility with a limit before one without), and the totals repeat on every row. Currencies are never compared. One limit remains: the engine's `by` must pick exactly one row, so with two currencies the signal is skipped with a reason and does not guess (needs the platform: `by` with a currency, or items on `figure_changed`). Also not fixed: a facility in a currency the entity holds no positions in is not netted in `net_worth_after_debt` (needs a rate the model does not hold); said in the recipe formula. |
| 17 | Covenant signal can never fire: no limit on record | not fixed, made visible | A limit or covenant line is not in the data or the loan agreement, and none may be invented. The headroom signal stays skipped until `facility_headroom_line` is signed. New signal `uc-017-liab-no-limit-on-record` (needs, cfo, record) fires on the current data and asks for the limit, so the gap is not silent. Needs a signed rule (owner decision). |
| 17 | "A drawdown is recorded" fires on every statement while debt > 0 | fixed | The drawdown signal now reads `drawdown_total` (drawn minus the previous statement's drawn, positive only) from `facility_headroom`; it does not fire when the balance fell (the key data: August to September). Test with a synthetic drawdown. |
| 17 | "margin" is the shortfall | fixed | Renamed `shortfall`, the message says "short of the line by". |
| 21 | Estimates count as valuations; two Kestrel Ridge funds read as fresh | not fixed on the figure, made visible | The key counts them (13 days), so the numbers stay. Whether an estimate may stand as the latest value is a business rule nobody has signed (owner decision, as the verifier says). The recipe now shows `value_basis`, `is_estimate`, `estimate_count`, `estimate_names`; an estimate is never preferred to a final or amended value of the same date; new signal `uc-021-stale-estimate-only` (needs, risk_officer) asks for the final. |
| 21 | Stale message says "marked" but nothing marks them, no hold | fixed | `uc-021-stale-found` is now `needs` with the action "Label them stale in the limits and report notes" and a hold `use_stale_values`. The scope is the list of stale names, so a consumer asks `held(plane, "use_stale_values")` without a scope or per list (a per-fund hold would need one card for each fund, which the engine cannot do from one figure). |
| 21 | Breach-on-stale checks only the stalest fund; the limit rule unverified | partly fixed | The signal now reads the stale fund that is the largest share of what is held (`stale_max_fund`, `stale_max_pct`, `stale_max_age`, computed in the recipe from the position snapshots), no longer the oldest, and no longer reads the `concentration` figure (which divides by one portfolio). The limit is still the signed `single_name_limit_pct` read as `limit.value`; the engine branch was not checked for that field name. Its text says "of the liquid portfolio", so whether it applies to funds is for the office to confirm (owner decision). Only the largest stale value is checked, because `by` picks one row. |
| 21 | Age against the latest position date, not the calendar | not fixed | The key itself uses 13 Oct, the latest position date, so the as-of cannot be the run date without breaking the key. Needs the platform to pass the run date to a recipe. Said in the formula. |
| 21 | Fresh signal fires for every fresh statement | fixed | New column `was_stale` (the previous value was more than 90 days old on the day the new one arrived); the signal needs `not age.stale and age.was_stale`. Note: with a 90-day rule a quarterly fund is past 90 days for a few days every quarter (30 Jun to a 2 Oct statement is 94 days), so this still fires for most quarterly funds each quarter. That is the rule working, not a bug; switch the signal off if it is noise. |
| 31 | No defect found | none | Unchanged. |
| 38 | Unreadable gain line makes both exception signals silent | fixed | New column `gain_unreadable` (no gain line, or two different figures on one statement) and new exception signal `uc-038-navroll-gain-unreadable` (problem, fund_accountant, holds `report_fund`). Ties and unexplained are skipped for it, with the reason. Test `test_38_an_unread_or_doubled_gain_line...`. |
| 38 | Estimates not filtered in the roll-forward | fixed | A final or amended value of the same date is preferred to an estimate; a quarter that still closes on an estimate has `on_estimate`, and the "ties" signal does not say it ties. Test with a synthetic Q4. A roll-forward on an estimate is allowed but marked provisional (not dropped: dropping would hide the fund). |
| 38 | Tie-out cannot fail | fixed | The tie-out compares the table's calls less distributions with the confirmed cash movements of the same funds in the same quarters. The test makes the table wrong and shows it fails. |
| 38 | Gain lookup not de-duplicated | fixed | One gain per document: the same figure twice is one; two different figures give null and `gain_unreadable`. Test adds a re-extraction. |
| 38 | Expect "875,000" drops the sign | fixed | `builds/hold.yaml` expects "-875,000"; the builds test compares the number with its sign. |
| 38 | Four "unexplained" figures not in the key | not fixed, the key lacks them | The key has no reported-gain figures. The test no longer types 108,181 or -210,957: it reads the manager's gain line from the statement PDF again and checks `reported_gain` and `unexplained` against that. The key owner should add the reported gain and the unexplained amount for the four rows (Growth I Q2 and Q3, Income II Q2 and Q3). |
| 38 | Statement message prints "+ gain" with no gain | fixed | Prints the gain and the status of the closing value. |
| 43 | Liquid figure is the largest book only; a book with no month-end snapshot dropped | fixed | `liquid_pnl_mtd` left-joins the month-end value: a book with none stays as a row with `no_month_start` and is counted in `books_without_start`, never in the gain. Totals for all books (`books`, `total_value_today`, `total_value_month_end`, `total_net_trades`, `total_gain_loss`, `total_gain_pct`, `mixed_dates`) repeat on every row; the daily signal reads the totals and says how many books are left out. Test with a second book. |
| 43 | Month-start signal fires on every scheduled run | fixed | Recipe column `new_month` (the latest position date is the first one on file in its month); the signal needs it. Test: false on 13 Oct, true on 1 Oct. |
| 43 | Price-jump checks only the largest move of the latest date; "held for review" has no review step | fixed | `top_move` is the largest move of any date; `jump_count` and `jump_names` list every move over 10 percent in the table; the signal fires when any exists and lists all. The 10 percent is the card's figure; no office rule for it is signed (stated in the recipe). Reworded: "Confirm or correct the price before it enters the liquid book figure". The hold is scoped to the largest instrument only; the others are named in the message. Test with a jump on an earlier day and one on the last day. |
| 43 | Test precedence bug (`A and B or C`) | fixed | Rewritten as plain asserts. |
| 43 | Expect "11,100" drops the sign | fixed | "-11,100" in `builds/hold.yaml`. |
| all | Build check searched the whole key file | fixed | It now reads the card's own block of the key, numbers by value and sign, names as whole names. |
| all | No test shows an exception signal firing on the key data | fixed | Every card's test runs its signals over its recipe rows (see above). Card 17's headroom signal is shown skipped on the key data (no limit) and firing on a synthetic facility with a limit. |
| all | Subject lines print raw decimals | fixed | Subjects and messages use `{x:,.0f}` / `{x:.2f}` / `{x:.4f}`. |

Counts: wrong figure 7 (all fixed; the second as far as the data allows), unsafe 7 (5 fixed; the estimate rule and the breach scope need an owner decision), missing 10 (9 fixed; the covenant line needs a signed rule, the four reported-gain numbers need the key), cosmetic 5 (all fixed).

## Recipes (all `status: ready`)

| Recipe | Card | Reads | Tie-out | Added columns for signals |
|---|---|---|---|---|
| `identifier_gaps` | 13 | instruments, instrument_identifiers, position_snapshots | values add up to the position snapshots at the latest month end (pass 2) | gap_count, gap_value_total, net_worth, gap_pct_of_net_worth, as_of_min, as_of_max, mixed_dates, first_row |
| `net_worth_after_debt` | 17 | position_snapshots, credit_facilities, portfolios, legal_entities, instruments | after-debt = positions less debt shown | family_* totals, is_latest |
| `facility_headroom` | 17 | credit_facilities, legal_entities | none | limit_missing, drawn_change, facilities, facilities_without_limit, no_limit_facilities, drawdown_total, drawdown_facilities, first_row |
| `value_age_days` | 21 | valuation_observations, position_snapshots, instruments | one row per instrument with a valuation | value_basis, is_estimate, was_stale, held_pct, stale_count, stale_names, stalest_fund, estimate_count, estimate_names, stale_max_*, first_row |
| `allocation` | 31 | position_snapshots, instruments, portfolios, legal_entities | parts add up to the position snapshots, cash left out (pass 2) | total_value, unclassified_value, positions_total, first_row |
| `nav_rollforward` | 38 | valuation_observations, cash_movements, instruments, extracted_fields | calls less distributions equal the confirmed cash movements of the same quarters | closing_status, on_estimate, gain_unreadable, latest |
| `liquid_pnl_mtd` | 43 | position_snapshots, transactions, instruments, portfolios | value today = listed positions at the latest date | no_month_start, new_month, books, books_without_start, total_*, mixed_dates, first_row |
| `liquid_price_move` | 43 | position_snapshots, instruments, portfolios | none | jump_count, jump_names, top_move |

`net_worth` (not mine) is unchanged. `currency_exposure` (64) and `income_forecast` (68) stay stubs: priority above 50.
Rules used, none invented: stale after 90 days (card 21 and the stub), the 1 percent of net worth (card 13), 10 percent in a day (card 43), a cent for the roll-forward (card 38). These come from the cards, not from a signed office rule; the figures say so. The single-name limit and the covenant line are read from signed rules at run time, not written into a recipe.

## Per card

### Card 13, `uc-013-secgaps`, owner head_of_data
- Recipe `identifier_gaps`. Signals: `-found` (needs), `-completed` (info), `-over-one-percent` (exception, problem, holds `publish_limits`).
- Expect: Pacific Rim Convertible 2029 note, 1,122,000, at 30 Sep. Test: 1 instrument with a gap, value 1,122,000 (key), a 13 Oct file does not move it, about 1.04 percent of what is held, so the exception fires and `completed` does not.

### Card 17, `uc-017-liab`, owner principal
- Recipes `net_worth_after_debt`, `facility_headroom`. Signals: `-owed`, `-drawdown` (info), `-no-limit-on-record` (needs, cfo), `-headroom` (exception, problem, cfo, holds `new_drawdown`; skipped until a signed line exists).
- Expect: 2,800,000, 105,430,000 (investment portfolios, cash left out). Test: debt 2,800,000 (Entity B only), after debt 105,430,000, by month Apr to Sep, issued report 57,600,000 less debt 54,800,000.

### Card 21, `uc-021-stale`, owner risk_officer
- Recipe `value_age_days`. Signals: `-found` (needs, holds `use_stale_values`), `-fresh`, `-estimate-only` (needs), `-breach-on-stale` (needs, holds `confirm_breach`).
- Expect: the three fund names, 196, 105. Test: all ten funds match the key for date, age, flag; the two Kestrel Ridge funds are shown as estimates (worked out from the statement files).

### Card 31, `uc-031-alloc`, owner fund_accountant
- Recipe `allocation`. Signals: `-ready`, `-unclassified` (needs), `-not-adding-up` (exception, problem, holds `publish_allocation`). Unchanged recipe; test now also shows the exception firing when a position loses its portfolio.

### Card 38, `uc-038-navroll`, owner fund_accountant
- Recipe `nav_rollforward`. Signals: `-statement`, `-ties` (info), `-unexplained` and `-gain-unreadable` (exceptions, problem, hold `report_fund`).
- Expect: 1,176,980, -875,000. Test: the 12 fund-quarters of the key, the quarter gain from the statement files (sum of the statements in the quarter), and for each fund's latest quarter exactly one of ties / unexplained fires. Growth I Q3 is left at -12,500 (M19, see pass 2).

### Card 43, `uc-043-liquidpnl`, owner cio
- Recipes `liquid_pnl_mtd`, `liquid_price_move`. Signals: `-daily`, `-month-start` (info), `-price-jump` (exception, problem, ops_clerk, holds `enter_price`).
- Expect: -11,100, 42,273,700, 1,084,800. Test: 30 Sep 41,200,000; 13 Oct 42,273,700; net trades 1,084,800; gain -11,100; the largest one-day move in the 140 custodian days is under 10 percent, so nothing is held.

## Needs (for the fixers and the steward)

1. **Real loader not called.** The tests read the files themselves. Whoever wires the loaders must write: statements into `valuation_observations` (period end as `valuation_date`, an amended statement as a row that `supersedes_valuation_id` the earlier one, `approval_status` final / estimate / amended) with `evidence_document_id`, and the statement's "Net gain / (loss)" line into `extracted_fields` as `field_name = 'net_gain_loss'`; capital calls and distributions into `cash_movements` as `call` / `distribution`, `confirmation_status = 'confirmed'`, with the amount that moved; loan statements into `credit_facilities` (the recipe takes the size of `drawn_amount`, so either sign is safe, and a limit goes in `limit_amount` when the agreement states one); the administrator column `Valuation Amount (USD)` read as market value (M18).
2. **The security master leaves out three funds**: Evergreen Growth II, Evergreen Credit III, Saltmarsh Renewables I. A loader that creates them with no class would show them as gaps and change cards 13 and 31 (unclassified would rise by 5,555,000). Identify by name, not by administrator code 4491 (shared).
3. **Model decision (steward): distribution amount.** The notice says 275,000 for Growth I (July); the bank credit is 262,500 (M19). The key uses 262,500 (card 38's roll uses it too). The manager's monthly gain lines assume 275,000, so the roll shows -12,500 for Growth I's latest quarter. Decide whether the roll uses the gross notice amount or the cash received, and add M19 to the uc-038 entries of the scorecard MESS list.
4. **Stale threshold.** 90 days is written in the recipe. To let an office sign its own, a `business_rules` code and a recipe that reads `business_rules` / `rule_versions` are needed.
5. **Rules not signed yet.** `facility_headroom_line` (no covenant in the data; owner decision). `single_name_limit_pct` (5, in `reference/office_rules.csv`, worded "of the liquid portfolio"): the signal reads `limit.value`; confirm the field name and that it applies to funds. The estimate rule (may an estimate stand as the latest value?) is for the owner; the key accepts it today.
6. **Signal engine fit** (engine on the `sh3-signals` branch): `by` must pick exactly one row, so recipes carry one marked row with the totals repeated on it. Consequences: the breach signal looks at the largest stale value only; the price-jump hold names the largest instrument only; with two currencies the `first_row` signals are skipped. To fire once for each item the engine needs items on `figure_changed`. Triggers assumed to exist: `file_arrived` kinds `manager_statement` and `loan_statement` (document field `fund`), `figure_changed` for the figure ids named, `schedule` for the month start. A condition that reads an empty value is skipped with a reason (engine `Missing`), which is why the recipes carry booleans such as `limit_missing` and `gain_unreadable` for the empty cases.
7. **Latest position date is the as-of** for `value_age_days` (not the calendar date).
8. **Liquid book scope.** Listed means `instrument_type` in listed_equity, bond, convertible. Net trades count a trade made after the month start and settled by the as-of date. A duplicate OMS row (M07, June) is not handled here.
9. **Existing test file out of date, not mine:** `tests/v1/test_v3_recipes.py` had 4 failures (they assert only seven recipes are built and that every recipe has `never_read`); they fail the same way without my recipes.
10. **Not done:** no run of the persona builds through the live API (`v3_persona.py`). No commit made.
