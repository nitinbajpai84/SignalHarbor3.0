# W1b build: Hold and maintain, cards 51 to 100 (key `hold`)

Seven cards of 51 to 100 have the domain "Hold and maintain": 55, 64, 65, 66, 67, 68, 69. **One is built (64); six are honestly unbuilt**, because each needs a table or a reader that does not exist yet. Synthetic data only (Evergreen Office, `tests/v1/fixtures/office6m`). Followed how the top 50 were built (`build-hold.md`).

Files: `packs/family_office/1/recipes/hold.yaml` (the `currency_exposure` stub is now ready), 3 signals `packs/family_office/1/signals/uc-064-fxexp-*.yaml`, `packs/family_office/1/builds/hold-51.yaml`, `tests/v1/test_w1b_hold.py`, this page.

Test run: `pytest tests/v1/test_w1b_hold.py -q -p no:cacheprovider --basetemp=D:/Temp/pyt-w1b` gives **13 passed, 0 failed**. With `test_w1_hold`, `test_w2_loader`, `test_w3_intake`: 93 passed. The tests load the office with the real loader (`v3_office6m_loaders.load_plane`, as `test_w2_loader.py`), run the recipe with its tie-out, and compare with `answer_keys.yaml` (no expected number is typed; the cases that change data run in a transaction that is rolled back).

## Built

| Card | Recipe | Reads | Tie-out | Signals |
|---|---|---|---|---|
| 64 Currency exposure of the family | `currency_exposure` | position_snapshots, valuation_observations, transactions, fx_confirmations, market_observations, instruments | forward legs bought equal the executed forward bookings that settle after the as-of date | `uc-064-fxexp-exposure` (info, see), `uc-064-fxexp-forward-differs` (problem, **holds `hedge_decision` for the currency**), `uc-064-fxexp-over-limit` (needs, skipped until a limit is signed) |

Key figures from the recipe output (13 Oct, SGD at the 1.34 fixing): SGD cash 5,150,694.59 (USD 3,843,801.93), SGD bought forward 6,707,500 (USD 5,005,597.01), net SGD exposure 8,849,398.94, 7.62 percent of the family, USD exposure 112,272,239.48, family total 116,116,041.41. All equal the key.

How it reads: investments are the latest value known of each fund (valuations on or before the latest month end, received by 13 Oct) plus the listed holdings at the month end; cash is the administrator's cash positions (the instruments named `Cash <currency>`); open forwards are the executed forward bookings that settle after the as-of date, the currency sold taken from the bank's confirmation of the same reference. The USD side has the sold leg taken off (the card's formula); the key's USD figure is before the forwards, and the recipe shows both (`spot_usd_eq`, `after_usd_eq`).

### Things the build found

- **The key is built on the booking, the bank says more.** FXF-2026-002 is booked at 1.3425 (SGD 4,027,500) and the confirmation reads 1.3452 (SGD 4,035,600), mess M16, 8,100 SGD. The key's 6,707,500 is the booked total. The recipe uses the booking so it equals the key, and shows the bank's side beside it (`fwd_net_confirmed` 6,715,600, `fwd_gap` 8,100). The exception signal fires on it and holds the hedge decision for SGD; the test ties the gap to the other key (`uc8-trades-vs-admin`, `difference_sgd`). If the office wants the confirmation to stand, the share goes from 7.62 to 7.63; that is the office's call, not made here.
- **A forward with no confirmation has no known sold currency.** The booking holds the SGD amount and the USD quantity but not the pair. The recipe takes the sold currency from the confirmation and counts a forward without one in `unplaced_forwards`; it never guesses (tested by deleting the confirmation).
- **Two non-USD currencies.** The signals pick the one non-USD row (`by: non_base`); with two they are skipped by the engine's rule (tested). Today the office has SGD only.
- `build-hold.md` is unchanged. The `hold-51.yaml` check leaves out the SGD payments of the next 90 days and the confirmed (6,715,600) figure.

## Not built, and why (Needs)

| Card | Needs | Why not built |
|---|---|---|
| 55 Corporate actions and income calendar | table `corporate_actions` and a reader for `corporate_actions` notices (PDF) | `MODEL-ADDITIONS.md` lists the table as "later". The loader has no reader for the kind (`NEW_KINDS` in `tools/gen_office6m/more.py`). Nothing to read the events from. |
| 65 Real assets register | table `real_assets`, readers for `property_valuations` and `title_deeds` | Table is "later"; no reader. |
| 66 Appraisal due on a real asset | the appraisal dates from `real_assets` (`property_valuations` PDFs) | Card lists no new table, but the dates exist only in the unread appraisal PDFs; the age and the 365-day line (card formula) need `real_assets` first. |
| 67 Unrealised gain by lot | table `tax_lots`, reader for `lot_register_*.xlsx` | Table is "later"; no reader. |
| 68 Dividend and coupon income forecast | readers for `income_calendar` and `corporate_actions`; the dividend per share per quarter, which only those files carry | The stub in `hold.yaml` (a trailing run rate of cash received) would give a different figure from the key and is not a forecast; it stays a stub. The key's 0.45 percent per quarter is the generator's rate, not a signed rule or a field of the master. |
| 69 What the private funds really own | table `fund_holdings`, reader for `fund_holdings_*.xlsx` | Table is "later"; no reader. |

Also needed for card 64, not blocking: a reader for `payment_schedule` (the key's SGD payments of the next 90 days, USD 388,599.93, is not built), and **a signed currency exposure limit** (`currency_exposure_limit_pct`; none exists in the office files, so `uc-064-fxexp-over-limit` is skipped and no number was invented). The cards 55, 65, 67, 68 and 69 have no exception signals yet; they can only be written once the tables exist.

## Edited

`recipes/hold.yaml` (only `currency_exposure`; the `income_forecast` stub is untouched), the three `uc-064` signals, `builds/hold-51.yaml`, `tests/v1/test_w1b_hold.py`, this page.
