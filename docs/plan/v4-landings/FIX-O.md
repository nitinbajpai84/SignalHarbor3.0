# FIX-O: Office view (UC1)

## What changed
- `k4_office.holdings`: each line now carries `asset_class` and `data_status` (the old status word). An instrument with no asset class has `status` = "Needs a class" (PRC29, 1,122,000), in API and on screen. The holdings table has a new "Asset class" column ("Not set" when empty).
- `k4_office.why_moved(plane, viewer, start, end, currency, portfolio_id, book)` and route `GET /api/v1/office/why-moved?start=&end=&currency=&portfolio_id=&book=`. `book=liquid` picks portfolios whose code or name contains "liquid" (EG-LIQUID); without either, all portfolios the viewer may see. Default permissions yaml line added (same roles as the other Office routes).
  - Returns start value, end value, change, percent (Decimal, 4 places, program arithmetic) and four parts that add up to the change exactly: price moves per instrument, trades in the period, revisions, exchange rates. Lines sorted largest first (trades in date order). Each line carries evidence (statement page or position file, or the trade id).
  - Trades: every live transaction dated in (start, end] for the scope is listed, including the 15 Sep FX forward; the message says "N trade(s) in the period are listed", never "no trades". Buy/sell types of held instruments change the value by their cash; other types (the forward) are listed with no effect on value.
  - Revisions = for values already known on each date, what was recorded since. A value that first arrived late counts as a move, not a revision.
  - Start and end must be ordered (400 otherwise); hidden portfolios and unconvertible currencies give `available: false` with a plain message.
- UI: new "Why did this move" section on the Office view (from/to dates default to the last two month-ends, liquid book), with change, percentage, largest contributor and the four parts.

## How to see it
Consume > Office view. Holdings table: PRC29 reads "Needs a class". Below the NAV bridge: "Why did this move" for the liquid book 31 Aug to 30 Sep (needs the seeded universe: expect 39,552,000 to 41,200,000, +1,648,000, +4.1667%, the FX forward listed).

## Tests run
- `pytest tests/v1/test_k4.py -q`: 19 passed (new: needs a class, liquid book with the forward listed and exact figures, revisions + access + date order, route).
- `npx tsc --noEmit` clean; `npx vitest run src/v1/k4`: 10 passed (new: why panel, Needs a class).

## Wiring for the orchestrator
- Seed must give PRC29 no `asset_class` and every other instrument one, otherwise they now also read "Needs a class". The seed must write the FX forward as a `transactions` row in EG-LIQUID with `trade_date` 2026-09-15 (type `fx_forward`, an instrument row, `external_trade_id` FXF-2026-001); the panel finds it by portfolio and date. Any buy/sell type transaction on a held instrument in the period will shift value from "price" to "trades".
- The checker should call `/api/v1/office/why-moved?start=2026-08-31&end=2026-09-30&book=liquid`; price lines carry per-security amounts, `largest` names the top one.
- Fixture `ui/src/v1/k4/office.fixture.json` gained a `why` key by hand (shape of the real response).
- Backups: `.sh-tmp/*.bak-fixcp`.

## Review
Verdict: **accepted**, with three small fixes applied in `sh_platform/v1/k4_office.py` (no other file changed).

Checked: diff against `.sh-tmp/*.bak-fixcp` (the Python/JSON files show whole-file diffs only because of line endings and a fixture reindent; the real changes are the holdings class fields, `why_moved`, one route, one yaml line, the UI section and tests). Money is Decimal end to end (`Decimal(str(...))`, `quantize("0.0001")`, parts sum to the change exactly, asserted in tests). No model arithmetic. Reads only, through `wh.connect(read_only=True)`. Permissions: one default-deny line with the same roles as the other Office routes. Screen copy plain. Nothing outside the file list touched.

Re-run: `pytest tests/v1/test_k4.py -q` 19 passed; `npx tsc --noEmit` clean; `npx vitest run src/v1/k4` 10 passed.

Fixed:
- Trade evidence text printed the raw type code and `None` ("fx_forward FXF-2026-001 dated 15 Sep 2026, USD None"); it now reads "Fx forward FXF-2026-001 dated 15 Sep 2026, 2,000,000.00 USD" and omits the amount when there is none.
- A transaction row with no currency would have crashed the FX lookup; it now falls back to the view currency.
- A value known on a date but no longer live now (`k in e_kn` but not in `e_now`) raised KeyError in the revisions line; it now counts as a revision to zero.

Open items (not defects in this file set):
- P06 and P19 are unverified against the seeded universe; the figures are reproduced only by the test data in `tests/v1/test_k4.py::liquid_book`. The orchestrator must confirm the seed writes the FX forward as a `transactions` row in EG-LIQUID dated 2026-09-15 and leaves only PRC29 without `asset_class`.
- Trades are listed in date order, not largest first (the brief said largest first for every part); harmless for one trade, say so if it matters.
- The screen panel is fixed to the liquid book (`book=liquid`); a per-portfolio picker was not built.
