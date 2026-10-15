# DATA2 landing: the cause of the Entity B cash break is in the data

Tally (TALLY.md) found no candidate items for the Entity B break on 8 Oct 2026: the seeded cash files held balances only. Now 30 days of ordinary cash activity are seeded on both sides, and one wire is booked a day apart. Tally ranks that wire first as a timing item.

## What changed
- **`docs/test/make_10uc_universe.py`** has a new function, `cash_activity()`, with its own random stream, so `cash_daily` is unchanged. The universe gains `cash_activity` (232 items) and `cash_opening_8_sep` (the closing balance on 8 Sep, the same on both sides: Holdings 2,302,752.60, Trust 1,211,721.29, Entity B 851,099.16).
  - On a weekday there are 2 or 3 ordinary items (fee, coupon, USD/SGD FX settlement) and a sweep transfer that balances the day. A weekend day carries only a sweep, because `cash_daily` moves some balances on a Saturday.
  - Each item has its own `administrator_date`, `trading_export_date` and `bank_date`.
  - The generator asserts that the opening balance plus the items booked up to each day equals that day's balance on each side, for all 90 entity-days.
  - The 8 Oct balances are unchanged: 880,400 / 868,000, 1,150,000 / 1,148,200 and 2,300,000 / 2,300,000. The JSON diff contains additions only.
- **The planted items:**
  - `WIRE-20261008-B01`: Entity B, -12,400.00 USD, "Legal fees, Saltmarsh Infrastructure Fund II", paid to Lowmoor & Tasker LLP (synthetic). The trading export and the bank book it on 8 Oct; the administrator books it on 9 Oct.
  - `CHG-20261006-T01`: a -1,800.00 charge for the Trust, booked by the trading desk only. This is the Trust's existing 1,800 gap, which is inside tolerance.
- **Planted fact P08b** is in the universe, in 10UC-UNIVERSE.md and in the answer key. `plant()` now numbers only the plain ids, so P09 to P33 are unchanged.
- **Fixtures:**
  - `bank_cash.py`: each bank statement gains a `Transactions` sheet. Its items add up to every closing balance from the 8 Sep opening.
  - `trading_export.py`: writes `trading_export/cash_movements_trading_export_2026-09-09_to_2026-10-08.csv` (232 rows), and its self-check proves that the rows sum to the trading-export balances.
  - Both MANIFESTs are updated.
- **`check_10uc.py`:** 7 new checks. For each side in the universe, the movements sum to the balances. Only the wire and the Trust charge differ between the sides, and the wire has the right dates. For each entity, the bank transactions sum to the closing balances. The trading-export movements sum to the trading-export balances, and the wire appears once, on 8 Oct. The expected file count goes from 180 to 181. **All categories pass, 0 fail** (bank_cash: 197 pass).
- **`tools/seed_10uc.py`:** a new step, `_cash_activity`, with its own guard, so a data root seeded before this card gets the movements on its next run.
  - It writes one source batch per day and side (`cash movements <day> administrator` / `trading_export`), each under its own source system.
  - Each record has `record_type = 'cash_movement'`, and its `external_record_id` is the bank reference.
  - It writes one confirmed `cash_movements` row per item on the entity's cash portfolio, with explicit `recorded_at`.
  - It uses the direct writer, as the history does, because `e1_write` stamps the time as now. The intake mapping is a file-upload flow, so it is not used here.
  - The administrator's 9 Oct file is received at 06:00 UTC, before the 18:00 cutoff.
  - Movement types are fee, coupon, fx_settlement, transfer and wire. None of them is in `e3_calc._FLOW` or in k6's call/distribution filter, so NAV bridges, returns and liquidity are unchanged.
- **`sh_platform/v1/n1_tally.py`** (small edits; backup `.sh-tmp/n1_tally.py.bak-data2`):
  - Items dated up to 3 days after the case day are now read, but only to find where an item on one side was booked later. They are never candidates themselves.
  - An item that equals the difference and that the other side booked on a later day ranks first, with kind `timing` and score 105.
  - A cash movement shows its bank reference.
  - `_origins` also returns `external_record_id` and `record_type`.

## What Tally now says (Entity B, model off)
"... The best candidate: 12,400 USD cash movement wire WIRE-20261008-B01 dated 8 Oct 2026 at the trading export equals the difference and reached the administrator only on 9 Oct 2026: a timing difference that clears that day." The candidate's chips are the trading-export row (8 Oct) and the administrator row (9 Oct). The exact-match candidate follows in second place. The "balances only" missing note is gone.

## Deviation from the card (decided, not asked)
The card asked for the administrator to book the wire on 8 Oct and the trading desk on 9 Oct. That contradicts the balances it said to keep:
- On 8 Oct the administrator is 12,400 *higher* than the trading export.
- The bank fixture already agrees with the trading export, at 868,000.

So the outgoing wire has already left at the bank and at the trading desk, and the administrator has not booked it yet. The data plants it the other way round: trading desk and bank on 8 Oct, administrator on 9 Oct. The planted text is worded to match. This is recorded as item 7b of the answer key's differences.

## Tests
- `pytest tests/v1/test_seed_10uc.py tests/v1/test_n1_tally.py`: **45 passed** in 122 s.
- New test `test_uc2_p08b_cash_movements_add_up_and_tally_ranks_the_wire`: the movement count, opening plus movements equal each balance on each side for each day, the wire on both sides with its dates, and Tally's top candidate is WIRE-20261008-B01 as a timing difference for 12,400 USD.
- Updated tests in `test_n1_tally.py`:
  - The "balances only" assertion is inverted.
  - The injected `TX-12400` is removed, because the seeded wire is now the cause.
  - The test asserts that the wire ranks first, as a timing item and as the exact match, with chips for both sides' rows. The duplicate, foreign-currency and timing checks are kept.
- `python docs/test/make_10uc_universe.py`, `tools/gen_10uc/bank_cash.py` and `trading_export.py` were each rerun. Their self-checks pass.

## Open points
- The live data root was not touched. To see the movements live, run `python tools/seed_10uc.py` once. Its new guarded step adds them to an existing root; no reset is needed.
- `docs/test/10UC-DATA-CHECK.md` (the checker's written report) was not regenerated.
- Backups: `.sh-tmp/*.bak-data2`, plus the `bank_cash.bak-data2/` and `trading_export.bak-data2/` folders.

## Review
Verdict: accept. Reran check_10uc.py (all sections pass, 0 fail, planted 7/7) and test_seed_10uc.py + test_n1_tally.py (45 passed). The universe generator asserts movements sum to every daily balance on both sides; 8 Oct balances unchanged. Reversed wire direction (administrator books on 9 Oct) is justified by the existing balances and recorded in the answer key. Open: DATA-CHECK.md not regenerated; live root needs one `python tools/seed_10uc.py` run.
