# W1 build: Hold and maintain (key `hold`)

Six cards of priority 1 to 50 have the domain "Hold and maintain": 13, 17, 21, 31, 38, 43. All six are done. Synthetic data only (Evergreen Office, `tests/v1/fixtures/office6m`).

Files written: `packs/family_office/1/recipes/hold.yaml`, 18 files `packs/family_office/1/signals/uc-0NN-<card>-*.yaml`, `packs/family_office/1/builds/hold.yaml`, `tests/v1/test_w1_hold.py`, this page.

Test run: `pytest tests/v1/test_w1_hold.py` gives **15 passed, 0 failed** (data tests for the 7 recipes, 6 signal-format checks, 1 builds check, 1 facility check).
How the tests load: a small DuckDB with the model's tables (`docs/v2/evidence-to-action-mvp.duckdb.sql`); the office6m files are read by small readers in the test (xlsx, csv, pdf text) and written to the tables; the recipe SQL comes from `v3_recipes.render`, is checked with `refusal` / `tables_read` (only `may_read` tables) and `tie_out`, then compared with `answer_keys.yaml`.

## Recipes (all `status: ready`)

| Recipe | Card | Reads | Tie-out | Added columns for signals |
|---|---|---|---|---|
| `identifier_gaps` | 13 | instruments, instrument_identifiers, position_snapshots | values add up to the position snapshots at each instrument's latest date | gap_count, gap_value_total, net_worth, gap_pct_of_net_worth, first_row |
| `net_worth_after_debt` | 17 | position_snapshots, credit_facilities, portfolios, legal_entities, instruments | after-debt = positions less debt shown | family_* totals, is_latest |
| `facility_headroom` (new, card 17 exception) | 17 | credit_facilities, legal_entities | none | first_row |
| `value_age_days` | 21 | valuation_observations, position_snapshots, instruments | one row per instrument with a valuation | stale_count, stale_names, stalest_fund, first_row |
| `allocation` | 31 | position_snapshots, instruments, portfolios, legal_entities | parts add up to the position snapshots | total_value, unclassified_value, positions_total, first_row |
| `nav_rollforward` | 38 | valuation_observations, cash_movements, instruments, extracted_fields | prior + calls - distributions + implied gain = closing | latest |
| `liquid_pnl_mtd` | 43 | position_snapshots, transactions, instruments, portfolios | value today = listed positions at the latest date | first_row |
| `liquid_price_move` (new, card 43 exception) | 43 | position_snapshots, instruments, portfolios | none | top_move |

`net_worth` (not mine) is unchanged. `currency_exposure` (64) and `income_forecast` (68) stay stubs: priority above 50.
Rules used, none invented: stale after 90 days (card 21 and the stub), the 1 percent of net worth (card 13), 10 percent in a day (card 43), a cent for the roll-forward (card 38). The single-name limit and the covenant line are read from signed rules at run time, not written into a recipe.

## Per card

### Card 13, `uc-013-secgaps`, owner head_of_data
- Recipe: `identifier_gaps`.
- Signals: `uc-013-secgaps-found` (normal), `-completed` (normal, nobody acts), `-over-one-percent` (exception, problem, holds `publish_limits`).
- Build: `uc-013-secgaps` under role `head_of_data`. Expect: Pacific Rim Convertible 2029 note, 1,122,000.
- Test: PASS. 1 instrument with a gap, value 1,122,000.00 (key: count 1, 1,122,000); net worth 108,230,000.00; 1.0367 percent of net worth, so the exception row fires.

### Card 17, `uc-017-liab`, owner principal
- Recipes: `net_worth_after_debt`, `facility_headroom`.
- Signals: `uc-017-liab-owed`, `-drawdown` (normal), `-headroom` (exception, problem, routed to cfo, holds `new_drawdown`).
- Build: `uc-017-liab` under role `principal`. Expect: 2,800,000, 105,430,000.
- Test: PASS. At 30 Sep net worth 108,230,000, debt 2,800,000, after debt 105,430,000 (Entity B 14,595,000); debt by month-end Apr to Sep 3,000,000 / 3,000,000 / 2,900,000 / 2,900,000 / 2,900,000 / 2,800,000 (all match the key); the issued report lines (Growth I, Income II, liquid book) 57,600,000 less debt 54,800,000. Headroom is empty: the loan agreement states a principal, not a limit.

### Card 21, `uc-021-stale`, owner risk_officer
- Recipe: `value_age_days`.
- Signals: `uc-021-stale-found`, `-fresh` (normal), `-breach-on-stale` (exception, needs, holds `confirm_breach`).
- Build: `uc-021-stale` under role `risk_officer`. Expect: the three fund names, 196, 105.
- Test: PASS. All ten funds match the key for valuation date, age and flag at 13 Oct; stale set = Cedarpoint Ventures III (105), Cedarpoint Opportunities II (196), Saltmarsh Renewables I (105).

### Card 31, `uc-031-alloc`, owner fund_accountant
- Recipe: `allocation`.
- Signals: `uc-031-alloc-ready`, `-unclassified` (normal), `-not-adding-up` (exception, problem, holds `publish_allocation`).
- Build: `uc-031-alloc` under role `fund_accountant`. Expect: 108,230,000, 36.37, 58.9, 1.04.
- Test: PASS. Total 108,230,000; all eight class values and percents (bond 10,967,500 / 10.13 ... unclassified 1,122,000 / 1.04) and the three entity percents (58.9, 25.03, 16.07) match, to 0.02 for rounding.

### Card 38, `uc-038-navroll`, owner fund_accountant
- Recipe: `nav_rollforward`.
- Signals: `uc-038-navroll-statement`, `-ties` (normal), `-unexplained` (exception, problem, routed to fund_accountant, holds `report_fund`).
- Build: `uc-038-navroll` under role `fund_accountant`. Expect: 1,176,980, 875,000.
- Test: PASS. The 12 fund-quarters of the key and nothing else; prior, calls, distributions, new and implied gain equal the key on every row (for example Growth I Q3: 9,265,520 + 0 - 262,500 -> 10,180,000, gain 1,176,980; Cedarpoint III Q2: 8,150,000 + 1,000,000 -> 8,275,000, gain -875,000).
- The manager's own gain line leaves a difference in 4 of the 12 rows: Growth I Q2 108,181 and Q3 396,980, Income II Q2 229,452 and Q3 182,582. The exception signal would fire for those; the key does not cover this part.

### Card 43, `uc-043-liquidpnl`, owner cio
- Recipes: `liquid_pnl_mtd`, `liquid_price_move`.
- Signals: `uc-043-liquidpnl-daily`, `-month-start` (normal), `-price-jump` (exception, problem, routed to ops_clerk, holds `enter_price`).
- Build: `uc-043-liquidpnl` under role `cio`. Expect: 11,100, 42,273,700, 1,084,800.
- Test: PASS. 30 Sep 41,200,000; 13 Oct 42,273,700; net trades 1,084,800; gain -11,100; -0.0269 percent. Over the 140 custodian days the largest one-day price move is under 10 percent (2.34), so nothing is held.

## Needs (for the fixers and the steward; nothing here was changed outside my five paths)

1. **Real loader not called.** The tests read the files themselves. Whoever wires the loaders must write: statements into `valuation_observations` (period end as `valuation_date`, an amended statement as a row that `supersedes_valuation_id` the earlier one) with `evidence_document_id`, and the statement's "Net gain / (loss)" line into `extracted_fields` as `field_name = 'net_gain_loss'` (I added `extracted_fields` to `nav_rollforward.may_read`, the stub did not list it); capital calls and distributions into `cash_movements` as `call` / `distribution`, `confirmation_status = 'confirmed'`, with the amount that moved (see 4); loan statements into `credit_facilities` with `drawn_amount` positive (the statements show it negative, M12); the administrator column `Valuation Amount (USD)` read as market value (M18).
2. **The security master leaves out three funds**: Evergreen Growth II, Evergreen Credit III, Saltmarsh Renewables I. The test takes their class from `reference/master_data.json` and their identifier from the administrator code. A loader that creates them from the administrator file with no class would show them as gaps and change card 13 and card 31 (the unclassified amount would rise by 5,555,000). The administrator code 4491 is shared by Evergreen Credit III and the Global Equity Index Fund: identify by name, not by code.
3. **Model decision (steward): distribution amount.** The notice says 275,000 for Growth I (July); the bank credit is 262,500 (M19). The key uses 262,500. The `cash_movements` row must carry what arrived, or card 38 is out by 12,500.
4. **Stale threshold.** 90 days is written in the recipe (`stale_after_days`). To let an office sign its own, a `business_rules` code (for example `stale_valuation_days`) and a recipe that reads `business_rules` / `rule_versions` (not in `may_read`) are needed.
5. **Rules the signals read that are not signed yet.** `facility_headroom_line` (no covenant is stated in the data or the loan agreement, and no limit; the card 17 exception waits, it is skipped, never guessed). `single_name_limit_pct` (value 5 in `reference/office_rules.csv`): the signal reads `limit.value`, `facility_headroom_line` is read as `line.amount`; confirm these field names when the rules are loaded as `business_rules`.
6. **Signal engine fit** (engine is on the `sh3-signals` branch; the yaml follows its format): `by` must pick exactly one row, so the recipes carry one marked row (`first_row`, `is_latest`, `latest`, `top_move`) with the totals repeated on it. Consequences: the card 21 breach signal looks at the stalest fund only; the card 43 price-jump signal at the largest move of the latest day only; to fire once for each stale fund or each price move the engine needs to accept items on `figure_changed`. Triggers assumed to exist: `file_arrived` kinds `manager_statement` and `loan_statement` (document fields `fund`), `figure_changed` for the figure ids named, and `schedule` for the month start. The card 21 signal `-fresh` fires for any fresh statement, not only for a fund that was stale.
7. **Latest position date is the as-of.** `value_age_days` ages against the latest position date loaded, not the calendar date; `identifier_gaps` takes each instrument's own latest position (so on 13 Oct PRC29 would be 1,119,900, not the 1,122,000 of 30 Sep, if the October custodian files are loaded too; the test loads 30 Sep only, as the card's files do).
8. **Liquid book scope.** Listed means `instrument_type` in listed_equity, bond, convertible. Trades need `transaction_type` buy / sell, a status not cancelled / failed / rejected, `trade_date` and `settlement_date`; net trades count a trade made after the month start and settled by the as-of date (the key's "settled"). A duplicate OMS row (M07, June) is not handled here.
9. **Existing test file out of date, not mine:** `tests/v1/test_v3_recipes.py` has 4 failures (`test_a_figure_is_matched...`, `test_three_north_names...`, `test_a_recipe_the_question_names...`, `test_recipes_load_from_the_domain_folder...`). They assert that only seven recipes are built and that every recipe has `never_read`; they fail the same way with my recipes removed (checked), because other domains' recipes are also ready now and two (`renewals_vendors`, `invoice_variance`) have no `never_read`.
10. **Not done:** no run of the persona builds through the live API (`v3_persona.py`); only `--dry-run` showed the builds merge into the cio role (build 3). No commit made.
