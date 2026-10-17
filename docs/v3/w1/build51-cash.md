# W1b build: cash and treasury, cards 51 to 100

Cards in this slice (Cash and treasury, no priority): 54 `uc-054-ladder`, 70 `uc-070-idle`, 72 `uc-072-cashfc`, 73 `uc-073-runway`.

**Built and passing: 54, 70 and 73.** **Card 72 has its recipe but stays BLOCKED.** The answer key needs expenses from January to September 2027, and those payments are in no file (see below).

Cards 70 and 72 rest on office rules that were signed in the synthetic office as logged assumptions (A50):
- `ladder_window_days` (90)
- `forecast_call_assumption` (991,666.67 a month, starting the month after the first)
- `forecast_floor` (750,000)
- `forecast_horizon` (30 Sep 2027)
- `forecast_distribution_basis` (latest value times payout rate)
- `forecast_held_payments` (leave held payments out)

The recipes read every one of these values from `business_rules` and `rule_versions`. No value is written into a recipe.

## Files

- `packs/family_office/1/recipes/cash.yaml`:
  - `liquidity_ladder` (card 54) and `cash_runway` (card 73), built earlier.
  - `idle_cash` (card 70) is new.
  - `cash_forecast` (card 72) is now built; it replaces the stub.
- `packs/family_office/1/signals/` holds eight signals for this slice:
  - Card 54: `uc-054-ladder-tightest` (info) and `uc-054-ladder-below-buffer` (exception, with a hold).
  - Card 70: `uc-070-idle-surplus` (info) and `uc-070-idle-short` (exception, with a hold on `new_commitment` for the short entity).
  - Card 72: `uc-072-cashfc-outlook` (info), `uc-072-cashfc-below-floor` (exception, with a hold on `new_commitment` for all entities) and `uc-072-cashfc-schedule-ends` (info: the schedule stops before the horizon).
  - Card 73: `uc-073-runway-months` (info).
- `packs/family_office/1/builds/cash-51.yaml` holds the builds for 54, 70 and 73. Each `check.expect` is copied exactly from `answer_keys.yaml`. Card 72 has no build, because its key cannot be met from the files.
- `packs/family_office/1/use_cases_100.yaml`: card 70's figure was renamed from "Cash above 90 day need" to "Idle cash above 90 day need". Under the old name, the threshold rule in `v3_recipes.match` cut "above 90 day need" away, so the figure bound to `cash_by_entity`. The new name binds to `idle_cash`. `docs/v3/USE-CASES-100.md` was updated to match.
- `tools/score50.py`:
  - New checks for `uc-070-idle`: 17 values, against `idle_cash`.
  - The BLOCKED entry for 70 is gone.
  - The BLOCKED reason for 72 now names the data gap.
- `tests/v1/test_w1b_cash.py`: new tests for cards 70 and 72.
- Two neighbouring tests asserted that `cash_forecast` was a stub, and both were updated:
  - `tests/v1/test_w1_cash.py` now checks that the four cash recipes after the top 50 are built.
  - `tests/v1/test_v3_recipes.py` now checks every stub that remains. None remains now, because other groups built theirs.

## Per card

| Card | Before | After | How |
|---|---|---|---|
| 54 ladder | PASS | PASS | Unchanged. |
| 70 idle | BLOCKED | **PASS** (17/17) | Recipe `idle_cash` gives one row per entity, at the window of the signed `ladder_window_days`, counted from the entity's latest cash date. The outflow is the same as on the ladder: open calls plus approved or scheduled payments, each line in USD at the fixing, rounded to the cent. The recipe repeats the ladder's SQL so it can stand alone, because recipes do not read one another. `idle` is cash less the outflow less the signed `cash_buffer`, when that is positive. A negative result is reported as `short`, never as idle. The totals are on every row. The tie-out checks that cash less outflow less buffer equals idle less short for every entity. Two `needs` checks hold the figure: one when the window rule is unsigned, one when no payment stage is loaded. **Signals:** the surplus (info, routed to the CFO, who proposes to the CIO). An entity that is short is an exception, with a hold on new commitments from that entity. Nobody is short in the key, so only the info signal fires. |
| 72 forecast | BLOCKED (stub, rules unsigned) | **BLOCKED** (recipe built; data gap) | Recipe `cash_forecast` runs month by month from October 2026 to the signed horizon. Opening cash is every entity's administrator cash in USD (6,156,041.41). Distributions are the latest statement value times the outlook payout rate, at each quarter end. Income is the expected coupons and dividends. Calls are the noticed call 7, plus the signed assumption from November. Expenses are the payment schedule, with held payments left out under the signed rule. The floor comes from the signed rule. Opening, distributions, income and calls agree with the key in **all 12 months**. Expenses and closings agree in **October to December 2026**. **Why it stays blocked:** the schedule file `payment_schedule_2026-10-13.csv` lists payments only up to 11 Jan 2027 (the generator writes `X.sched` only to that date). The key's expenses for January to September 2027 come from schedule items that are in no file: for example, the key has 187,402.08 for January against 39,007.46 in the file. Filling them with a run rate would be an invented assumption, so the recipe flags the gap instead: `expenses_complete` is false from January, and the `uc-072-cashfc-schedule-ends` signal says so. With the files as they are, the forecast is lowest in 2027-09 at -3,192,336.56 and cash to raise is 3,942,336.56; the key has 5,654,705.37. **To unblock:** either the schedule file runs to 30 Sep 2027, or someone signs a rule for expenses after the schedule ends. |
| 73 runway | PASS | PASS | Unchanged. |

## Tests

Command: `python -m pytest tests/v1/test_w1b_cash.py -q -p no:cacheprovider --basetemp=D:/Temp/pyt-w1b-cash`

Result: **15 passed** in about 20 seconds, on the real pack readers. The new tests prove the following:

1. **Card 70 agrees with the key.** That covers 3 entities (cash, outflow, buffer, idle and short) and both totals. Each entity's outflow equals the ladder's 90-day calls plus payments.
2. **Card 70's window is the signed rule.** If the rule is re-signed at 30 days, the outflow moves to the 30-day rung. If it is unsigned, the `needs` check is 0 and there are no rows.
3. **Card 70's signals behave.** The surplus message names the key's total. The exception does not fire on the key. A 2,500,000 payment leaves Holdings short, and then the exception fires.
4. **Card 72 agrees with the key while the schedule lasts.** Opening cash, call assumption and floor match. Distributions, income and calls match for all 12 months. Every line matches from October to December.
5. **Card 72 stays blocked for a stated reason.** Every month from January onward has incomplete expenses. The schedule ends on or before 11 Jan 2027. Every later month's expenses fall below the key's. No build exists for card 72.
6. **Card 72's assumptions are signed rules.** All five forecast rules are signed. When the floor is unsigned, the `needs` check holds the forecast. Approving the held `FEE-CUST-Q3` adds exactly 6,180 to October.
7. **Card 72's signals behave.** They name the lowest month, the cash to raise against the floor, and the month the schedule stops.
8. **Signals and builds are sound.** All 8 signals are well formed, three of them exceptions with holds. The builds carry only numbers from the keys.

Neighbouring tests also pass: `test_w1_cash.py`, `test_v3_recipes.py`, `test_v3_signals.py` and `test_w2_readers_treasury.py`.

Scores:
- `python tools/score50.py` is 50/50.
- `python tools/score50.py --all` is 80 PASS, 1 FAIL, 2 SIGNAL and 17 BLOCKED. Cash and treasury is now 14 PASS and 1 BLOCKED (card 72). The run includes other groups' work in progress.
