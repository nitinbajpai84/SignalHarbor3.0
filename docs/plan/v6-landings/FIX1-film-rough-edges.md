# FIX1: the film's rough edges

Four defects the launch film exposed. Each was fixed where every caller passes through. No model calls, no figures or names in code.

## 1. Action: the Entity B cash break offers "Close as timing" and counts in Done today
- **Root cause (a):** the cash check (`e3_recon._cash_by_entity`) wrote result lines with no `cause`. The timing reading already existed in Tally (`n1_tally._candidates`: an item equal to the difference that the other side booked a day later). It was only used on the case page, so the Action line never matched `/timing/` and offered only "Open the case".
- **Fix (a):** `n1_tally.timing_cause(plane, case_id)` returns that candidate's sentence. A new `clears` flag marks the item-equals-difference, booked-later reading, so a plain one-sided item never counts as timing. After the check, `_cash_by_entity` stores the sentence as each breached line's `cause`. The button still shows only when the server allows `dismiss`, and it performs the existing dismiss action.
- **Root cause (b):** Done today compared `resolved_at` with the viewer's calendar day (`new Date()`). The demo company is pinned to 9 Oct 2026 (`demo_today`), so no closed case ever counted. A close made on the page was also counted twice, once in the page-local list and once as a closed case.
- **Fix (b):** `e4_cases.listing` now returns `closed_today`, worked out on the company's day (`wh.now(plane)`). Done today counts those cases, so a case closed on this page or on its own case page counts the same way. The close no longer adds a separate page-local line.
- **Check by hand:** reseed, then open `/centre/action` as an analyst who may dismiss. Under Reconciliations, the Entity B line reads "…equals the difference and reached the administrator only on 9 Oct 2026: a timing difference…" with **Close as timing**. Press it, and Done today goes up by 1. Closing a case from its case page counts too.
- **Note for the film:** the cause is written when the check runs. The film's snapshot `.sh-tmp/testenv/vid7/data.snap` holds a run from before this fix, so rebuild the snapshot (let `fresh_server` reseed) before re-filming.

## 2. The schedule after Go live follows the pack's refresh rule
- **Finding:** the chain pack → plan → builder → go-live was traced on a fresh seed. A pack whose freshness is "06:00 daily" goes live "daily at 06:00", so the schedule does follow the pack. The film's project is different: its SOW (`tools/seed_walk_benchmark.py`) says `needed_by: "5th business day"`, so its pack says "06:00 monthly, by the 5th business day". "Every month" was therefore correct. The film's end card "Live at 06:00 / every morning" (`tools/video/film7.py` line 238) does not match that project.
- **Root cause of what was wrong in the product:** the builder (`BuilderPanel.schedule`) and the go-live message (`b11_builder.go_live`) dropped the pack's day. They said "every month at 06:00" where the pack says "06:00 monthly, by the 5th business day".
- **Fix:** both now add the pack's day for a monthly rule: "every month at 06:00, by the 5th business day". The schedule `day` type in `ui/src/v1/b11/api.ts` is now `string | number | null`, matching the data.
- **Check by hand:** on the Pipelines builder, after the variance clears, the text reads "Going live uses the schedule in the pack: every month at 06:00, by the 5th business day". After Go live, the thread says "(monthly at 06:00, by the 5th business day)". If the film wants "every morning", change the film story's `needed_by` (for example "06:00 daily") or the end card. The product follows whichever the pack says.

## 3. Build never says "Connecting the 0 sources"
- **Root cause:** the count comes from the plan's `sources`. The film's intent names no source systems (`sources: []`), so the count is 0, yet the busy line and the Connections card were always shown.
- **Fix:** the busy line reads "Connecting the N source(s) and running on a copy." only when N > 0, and otherwise "Running on a copy.". The Connections card shows only when the round has connections.
- **Check by hand:** open the builder of a pack with no sources. It shows no "Connecting the 0 sources" line and goes straight to the run card.

## 4. Figure tiles show thousands separators
- **Root cause:** `cxui/Chart.tsx` drew the studio's figure view through its own formatter, but Lumen's "number" tile is a Vega text mark (`cx_lumen`, `mark: {type: "text"}`). Vega printed the raw value, 103405000.
- **Fix:** in the one shared render path (`Chart`, used by `TileCard` in the studio, Canvas and Consume), any single-number text-mark tile (a text mark with no x or y) is drawn by the same `Figure` view, which reads its own field. Every figure tile now uses the same formatter: separators, rates as percentages, and the change on the period before.
- **Check by hand:** ask Lumen for a single number (for example net worth). The tile reads "103,405,000", in the studio and in Consume.

## Tests
- `tests/v1/test_fix1_cash_timing.py` (new, fix 1): the seeded cash run's Entity B break carries the timing cause, and after dismissing it the case is `closed_today`.
- `tests/v1/test_v6b_pack_and_benchmark.py::test_go_live_then_lumen…` (fix 2): the go-live message carries the pack's refresh rule with its day.
- `ui/src/v1/b11/b11.test.tsx` "FIX1: …" (fixes 2 and 3): no "Connecting the 0", and the monthly day is shown.
- `ui/src/v1/cxui/cxui.test.tsx` "FIX1: …" (fix 4): a Lumen text-mark tile and a studio figure both show separators.
- `ui/src/v1/a5/ActionToday.test.tsx`: Done today reads the server's `closed_today`. `ui/src/v1/e4/cases.real.json` gained the field.

Results: `pytest tests/v1/test_n1_tally.py test_e3b.py test_e4a.py test_e4d.py test_fix1_cash_timing.py test_v6b_pack_and_benchmark.py`: 155 passed (one e4a fixture failure fixed and re-run green). `vitest run src/v1/a5 b11 cxui b7 e4 c1`: 91 passed. `tsc --noEmit`: clean.
