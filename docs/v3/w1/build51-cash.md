# W1b build: cash and treasury, cards 51 to 100

Cards in this slice (Cash and treasury, no priority): 54 `uc-054-ladder`, 70 `uc-070-idle`, 72 `uc-072-cashfc`, 73 `uc-073-runway`. **None is built.** Each needs a source file the platform's readers do not load yet, and the rules forbid inventing a table or a status. No recipe, signal or persona build was written; the cards carry no `signals` rows, so no exception signal was due.

Files written: `tests/v1/test_w1b_cash.py`, `packs/family_office/1/builds/cash-51.yaml` (empty `roles`), this page. `recipes/cash.yaml` is unchanged: `liquidity_ladder` and `cash_forecast` stay stubs.

Test run: `python -m pytest tests/v1/test_w1b_cash.py -q -p no:cacheprovider --basetemp=D:/Temp/pyt-w1b-cash` gives **9 passed, 0 failed** (about 21 seconds), on the real pack readers (`v3_pack_readers.load_plane`) through the `office` fixture of `test_w2_loader.py`. The tests prove: (1) the loader says "no reader for this kind" for `payment_schedule`, `income_calendar`, `manager_outlook`, `expense_ledger`, and nothing of them is in the plane; (2) the two recipes are still stubs; (3) no expense rows, and none of the schedule's 19 references, are in the plane; (4) the legs the plane does give agree with the keys: cash by entity (USD and SGD, all three entities), calls due in 30 and 60 days, and the signed 250,000 buffer; (5) the plane's own expected payments (from invoices) for Holdings in 30 days are not the key's 131,654.02, so the gap is exactly the schedule's payment leg.

## Per card

| Card | Not built because | Needs |
|---|---|---|
| 54 ladder | The payment leg is the schedule file (`payment_schedule_2026-10-13.csv`: approved, scheduled, expected, held). Nothing reads it. The key counts approved and scheduled, leaves out held and expected; the model's expected payment has one status, so scheduled against expected cannot be told apart. Calls due also stops at 60 days; the ladder has a 90 day window. | A reader for `payment_schedule` and a decision on where the schedule status lives (a column on the expected payment, or a table). A 90 day window on `calls_due` (or the ladder reads calls itself). Then recipe `liquidity_ladder`: cash by entity (SGD at the day's fixing, 1.3400) less open calls and approved or scheduled payments inside 30, 60, 90 days, `below_buffer` against the signed `cash_buffer`. |
| 70 idle | Is the ladder's 90 day outflow less the buffer. Same missing payment leg. | Card 54. Then `idle = cash - outflow_90 - buffer`, `short` the negative part, per entity; buffer from the signed rule (already read by `cash_after_calls`). |
| 72 forecast | Needs the schedule (as 54), the income calendar (coupons and dividends), the managers' distribution outlooks (payout rates per quarter, read from PDFs), and future calls at an average of the last six months. No reader for the first three; the average-call assumption (991,666.67 a month) is a rule nobody has signed. | Readers for `income_calendar` and `manager_outlook`; a signed forecasting rule for future calls; the floor in the key is three buffers, also unsigned. |
| 73 runway | Needs office expenses: `expense_ledger_2026-04_to_2026-09.xlsx` has no reader and `office_expenses` is a table left for later (ASSUMPTIONS A23; `cash_runway` is in A24). | Decide the expense table (MODEL-ADDITIONS suggests cash movements of type expense) and a reader; then `cash_runway` = cash in USD equivalent over the average monthly spend of the last six months; the key also gives months of cash plus the liquid book. |

## Needs for the owner of the loader (not done here; the file is not on my list)

1. Readers for the four kinds above (`payment_schedule`, `income_calendar`, `manager_outlook`, `expense_ledger`). `test_w1b_cash.py` flips its first test the day one is added; change the expectation for that kind then.
2. A place for the schedule's status (approved, scheduled, expected, held) on a payment, without a new table if possible; `held` already has a home in `payment_hold` approvals.
3. Decide the three signed rules cards 70 and 72 lean on: the forecasting call assumption, the forecast floor, and the 90 day window of the ladder.
