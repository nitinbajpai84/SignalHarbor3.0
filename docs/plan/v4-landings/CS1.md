# CS1: daily key numbers at the top of Consume

Six large figures with a small change line, a status word and "Where is this from?", readable at 390px, with a USD/SGD switch. Every figure comes from a stored record through an existing function (k4_office, k6_liquidity, k7_benchmark, e3_calc); nothing is worked out by a model.

## What landed

| File | What |
|---|---|
| `sh_platform/v1/k9_daily.py` | `daily(plane, viewer, currency, as_of)`: nav, issued, returns, levers, markets, liquidity. A trail id and a `where` block on every figure; a section that fails says "Not available yet." and the others still show |
| `sh_platform/v1/k9_routes.py` | `GET /api/v1/consume/daily?currency=USD\|SGD[&as_of=YYYY-MM-DD]` (picked up by the `*_routes.py` glob; no mount line needed) |
| `sh_platform/v1/k9.permissions.yaml` | all six roles; every figure is filtered by entity access inside k4_office / k6_liquidity (fail closed) |
| `ui/src/v1/k9/` | `DailyNumbers.tsx` (default export, no props), `api.ts`, `daily.fixture.json`, `k9.test.tsx` |
| `tests/v1/test_k9_daily.py` | answer-key checks (below) |

## The six figures

| Card | Big figure | Change line | Answer key |
|---|---|---|---|
| Total value | company value at the as-of date, entities listed beneath | entity count, or "Only the entities you can see" | P03, P04 |
| Known now against the issued report | known now | difference since the issue date, issued figure, open case banner, link to the CIO Brief | P01, P02, P16 |
| Return this month | liquid book return | benchmark and difference in points; year to date beneath | P14 |
| What moved the liquid book | percent move | biggest mover; revisions, timing, exchange rates, unexplained, top three movers beneath | P03 to P06 |
| Markets this month | equity index month change | USD/SGD level and last-day move; every series beneath | P14, P16 |
| Cash after confirmed calls | firm cash after confirmed calls | calls due in 30 days; per entity beneath | P21, P22 |

## Mount lines for the orchestrator (ui/src/v1/cxui/ProjectList.tsx)

```tsx
// with the other imports
import DailyNumbers from "../k9/DailyNumbers";
```

```tsx
// inside <PageFrame title="Consume" ...>, as its first child, above <section aria-label="Shared with you">
<DailyNumbers />
```

No backend mount is needed. The band loads on its own and keeps its own USD/SGD switch.

## Decisions and limits

- Month = the issued report's period (Aug-end to Sep-end); with no issued report, the last month end. Year to date opens at 31 Dec of the year before.
- The benchmark is compared with the portfolio whose name contains "liquid" (P14); the warehouse has no portfolio-to-benchmark link yet (marked `ponytail:` in k9_daily.py).
- A monthly index has no last-day move; it reads "no last-day move", never zero.
- SGD year to date reads "No signed fx_fixing rule applies on 2025-12-31 ..." because the seed has no signed rate that early; the band shows the reason, not a guess.
- Total value is the company's holdings view (103,405,000 USD); the issued report total (57,600,000) is its own card, as the key defines it.

## How to test

```
PYTHONPATH=. SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_k9_daily.py -q     # 11 tests, about 3 minutes (seeds the universe)
cd ui && npx vitest run src/v1/k9                                                     # 5 tests
```

## Review (10 Oct)

Verdict: pass after two fixes.

- Access: route declared for all six roles like the K2 office routes; every money figure comes through k4_office/k6 (E1d, fail closed); the benchmark portfolio is picked from the viewer's own portfolios; market levels are company-wide and hold no entity data. One-entity test confirms no Entity B figure leaks.
- History: read only; market levels use the live (not superseded) rows up to the day asked. Nothing is written.
- Figures: P01-P06, P14, P16, P21-P22 asserted; P07 tightened so the total's status word must be "Stale" (the weakest holding).
- Fixed: the band crashed the whole page when the nav, levers or markets section came back "Not available yet" (`n.by_entity.length`, `l.parts.map`, `m.series.map` on a missing list). Now guarded; a new vitest covers it.
- Fixed: the SGD year to date showed the raw rule text ("No signed fx_fixing rule ..."). Each return period now carries a plain `message` ("Not available yet: there is no signed exchange rate for 31 Dec 2025."); the UI shows that, the raw `problems` stay in the payload for the trail.
- Tests: pytest tests/v1/test_k9_daily.py 11 passed; vitest src/v1/k9 6 passed; tsc shows no errors in src/v1/k9 (9 errors elsewhere, not ours).
- Not done: no 390px screenshot; open question whether the year starts on 31 Dec of the prior year (builder's assumption).
