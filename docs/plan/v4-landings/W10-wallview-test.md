# W10: WallView test clock frozen

## What changed
`ui/src/intents/WallView.test.tsx`, first test only: `Date.now` is spied to a fixed `2026-10-07T12:00:00Z` (restored in `finally`), so the fixture end date (now + 3 days - 1s) and the component's "3 days left" no longer depend on the run date. Component untouched. Backup: `.sh-tmp/WallView.test.tsx.bak-W10`.

## How to see it
`npx vitest run src/intents/WallView.test.tsx` from `ui/`: 19 passed.

## Tests
19 passed, 0 failed (re-run at review).

## Review
Verdict: pass, with the builder's first write-up corrected. That write-up said the test stayed flaky with 11 failures from jsdom corruption. The file on disk and a fresh run show otherwise: the `vi.spyOn(Date, "now")` approach works, and the earlier failures came from `vi.useFakeTimers()`, which also fakes the timers `findBy`/`waitFor` rely on. Scope: only the card's file changed. Open items: none. Optional: the same freeze could move to a `beforeEach` if more tests start depending on the fixture date.
