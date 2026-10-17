# W1b build: cash and treasury, cards 51 to 100

Cards in this slice (Cash and treasury, no priority): 54 `uc-054-ladder`, 70 `uc-070-idle`, 72 `uc-072-cashfc`, 73 `uc-073-runway`.

**Built: 54 and 73.** **Not built: 70 and 72**, because the rules they rest on are not signed (A34).

The readers they needed now exist: `payment_schedule`, `income_calendar` and `manager_outlook` are in `v3_pack_readers_treasury.py`, and `expense_ledger` is in `v3_pack_readers_controls.py`. The tables are there too: `cash_movements.payment_stage` (A34) and `office_expenses` (A33).

## Files

- `packs/family_office/1/recipes/cash.yaml` has two changes:
  - `liquidity_ladder` is now built; it replaces the stub.
  - `cash_runway` is a new recipe.
  - `cash_forecast` stays a stub.
- `packs/family_office/1/signals/` has three new signals:
  - `uc-054-ladder-tightest` (info)
  - `uc-054-ladder-below-buffer` (exception, with a hold)
  - `uc-073-runway-months` (info)
- `packs/family_office/1/builds/cash-51.yaml` holds two builds:
  - `cfo` builds `uc-054-ladder`.
  - `principal` builds `uc-073-runway`.
  - In both, `check.expect` is copied from `answer_keys.yaml`.
- `tests/v1/test_w1b_cash.py` was rewritten.
- `tests/v1/test_w1_cash.py` changed by one line: its stub assertion no longer expects `liquidity_ladder` to be a stub.

## Per card

| Card | State | How |
|---|---|---|
| 54 ladder | Built | Recipe `liquidity_ladder`, one row per entity and window. The windows are 30, 60 and 90 days, as the question names them, counted from the entity's latest cash date. The ladder takes the administrator's cash in USD (SGD at the latest fixing on or before that date, 1.3400), less open calls due in the window (open as `calls_due` counts them), less expected payments with `payment_stage` approved or scheduled. Each line is converted to USD and rounded to the cent; the key's 131,654.02 depends on that rounding. Held payments (`FEE-CUST-Q3`) and payments only expected are left out. `below_buffer` compares the result with the signed `cash_buffer`, and is empty when no buffer is signed. A currency with no fixing empties the figures and is counted in `unconverted`. The tie-out checks that the 90-day payment lines equal the schedule's approved or scheduled payments in that window. A `needs` check holds the figure when no payment carries a stage. **Signals:** the tightest entity at 90 days (info), and an entity that falls under the buffer (needs). The second one puts a hold on `new_commitment` for that entity until the CFO decides how to raise the cash. |
| 73 runway | Built | Recipe `cash_runway`, one row per expense category, with the totals on every row. Cash is every entity's latest administrator cash in USD. Spend is every `office_expenses` line in USD at its day's fixing, rounded to the cent. The average is the total divided by the months the ledger spans (first and last month both counted; 6 here). The liquid book is the latest value of the listed instruments (42,273,700, the same figure as card 43). The tie-out checks that every ledger line is counted once. **Signal:** months of cash, plus the largest item (info). There is no exception row, because no runway threshold is signed. |
| 70 idle | Not built | A34 makes the 90-day window of idle cash a signed rule (`ladder_window_days`), "to be signed before cards 70 and 72 are built". No such rule is on file. Once it is signed, the idle figure per entity is `cash_usd_equivalent - (calls + approved_and_scheduled_payments)` at that window, less `cash_buffer`, with the negative part reported as `short`. Those are all columns of `liquidity_ladder`, so the recipe is short. |
| 72 forecast | Not built | Needs two signed rules, and neither is signed: `forecast_call_assumption` (the 991,666.67 a month average of 1 Apr to 30 Sep) and `forecast_floor` (three buffers, 750,000). It also needs the expected distributions (card 71's `projected_payout_rate` times the latest fund value). That recipe belongs to the invest group. `cash_forecast` stays a stub. |

## Tests

Command: `python -m pytest tests/v1/test_w1b_cash.py -q -p no:cacheprovider --basetemp=D:/Temp/pyt-w1b-cash`

Result: **9 passed** in about 23 seconds. The tests run on the real pack readers through the `office` fixture of `test_w2_loader.py`. They prove the following:

1. The ladder agrees with the key for 3 entities × 3 windows. That covers USD and SGD cash, USD equivalent, calls, payments, cash after and below buffer.
2. Approving the held `FEE-CUST-Q3` adds exactly 6,180 to the Trust's 30 days.
3. With no stages loaded, the `needs` check holds the ladder.
4. The signals:
   - The tightest-entity signal fires with the key's numbers.
   - The below-buffer signal is false on the key data.
   - A 700,000 payment makes the below-buffer signal fire for Holdings, under the buffer within 60 days.
   - With the buffer unsigned, the below-buffer signal is skipped.
5. The runway matches the key: 13 categories, cash, average, months, liquid book, and months with the liquid book. Its signal fires.
6. The signals are well formed.
7. The builds carry only numbers from the keys.
8. Cards 70 and 72 stay unbuilt, and none of their three rules is on file.

Neighbouring tests also pass: `test_w1_cash.py`, `test_v3_recipes.py`, `test_v3_signals.py` and `test_w2_readers_treasury.py` (99 passed, 1 xfailed). `test_fixc_span_pack.py` has two failures, and they fail the same way with or without these recipes, so this work did not cause them.

## Needs (for the owner of the office rules)

1. Sign `ladder_window_days` (90) to unblock card 70.
2. Sign `forecast_call_assumption` and `forecast_floor` to unblock card 72. That card also needs the invest group's expected-distributions recipe.
