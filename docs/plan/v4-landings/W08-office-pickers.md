# W08: portfolio and month pickers (Office "Why did this move", Benchmark)

## What changed
- `ui/src/v1/k4/api.ts`: `getPortfolios()` lists the portfolios the person may see (read from the existing holdings route, which omits hidden ones); `getWhyMoved` takes an optional `portfolioId` (sends `portfolio_id`, no `book`).
- `ui/src/v1/k4/OfficePage.tsx`: "Why did this move" now has a Portfolio picker (default "The liquid book", then each visible portfolio) and a Month picker. The month gives the range (last day of the month before to last day of the chosen month); the range is shown beside it.
- `ui/src/v1/k7/BenchmarkPage.tsx`: the typed portfolio code is a picker of visible portfolios (value = portfolio id, which the comparison route accepts). If the list cannot be read, or a code arrives in the link, the typed box / that code stays. The From/To month pickers already existed.

## How to see it
Consume > Office view > Why did this move: choose a portfolio and a month. Consume > Benchmark: choose a portfolio, then Show.

## Tests
- `npx vitest run src/v1/k4 src/v1/k7`: 15 passed (new: why-moved asks for the chosen portfolio and month; benchmark picker sends the portfolio id). `npx tsc --noEmit` clean.
- Backups: `.sh-tmp/*.bak-W08`.

## Notes
- The old From/To date inputs in the Why panel are replaced by one month (a custom date span is no longer possible there).
- Portfolio list comes from holdings in USD; it fetches holdings once more per page.

## Review
Verdict: pass. Re-ran `npx vitest run src/v1/k4 src/v1/k7`: 15 passed. Scope: only k4/k7 files plus the landing note changed. The why-moved route accepts `portfolio_id` and `book`, so the request shape is correct. Wording is plain, no jargon. No fixes needed.
Open items: neither picker has been looked at on screen; the Why panel can no longer take a custom date span; one extra holdings call per page.
