# Fix B · Benchmark read path (UC4, P14/P15)

No existing file was edited, so there are no `.bak-fixcp` backups. All files are new.

## What changed
- `sh_platform/v1/k7_routes.py` (auto-installed) and `sh_platform/v1/k7.permissions.yaml` (sponsor, approver, analyst, company_admin, participant; handler also needs the consumer seat).
  - `GET /api/v1/benchmarks`: every signed definition and version with status and components. A non-approved one carries `notice` "In progress: not used for certified figures." and `policy_question` (the question plus the open case, if one exists). Read only: asking never opens a case (the case is opened by `k7_benchmark.certified_return`, as before).
  - `GET /api/v1/benchmarks/comparison?portfolio=<id or code>&code=<benchmark code>&start=YYYY-MM&end=YYYY-MM` (months default to the last full month; max 36). Per month: portfolio, benchmark (blend), difference, each component (weight, index, spread, total return), `certified`, `problems`, and `version_used` (version, status, name). Figures are Decimal strings: `value` (fraction) and `pct` (4 places). A portfolio the person may not see (E1d) is a 404.
  - All figures come from `k7_benchmark.comparison` -> `e3_calc`. The only arithmetic here is the "liquid sleeve" line, see below.
- `ui/src/v1/k7/` (`routes.tsx`, `BenchmarkPage.tsx`, `api.ts`, fixture, `k7.test.tsx`): page `/centre/consume/benchmark`.
- `tests/v1/test_k7_routes.py`.

## Decision to check: which "difference" is 1.9065
The universe says 1.9065 = EG-LIQUID 4.1667 minus the 60/40 liquid sleeve 2.2602, not minus the blend 2.7072 (that would be 1.4595). No signed definition holds a 60/40 benchmark, so the route returns `difference` against the blend (what `comparison` gives) and also `liquid_sleeve: {value, pct, difference}`: the unspread components of the signed definition with weights renormalised (0.42/0.28 -> 0.6/0.4), Decimal, in `_liquid`. That is the one small second calculation; it is derived only from the components `e3_calc` returns. If you would rather sign a 60/40 benchmark in the seed and compare against it through `comparison`, delete `_liquid`.
Also: with the seed's private sleeve at equity + 300 bps over 30 days, e3 gives a spread of 0.2466%, so 3.7502% needs the seed to use the spread that yields 0.25 (e.g. 304 bps) or the checker to tolerate it. Not checked here (seed is another agent's).

## How to see it
Open `/centre/consume/benchmark?portfolio=EG-LIQUID&code=EG-OFFICE-BLEND&start=2026-09&end=2026-09` (or type the portfolio code and press Show). In-progress version 2 shows a card above the form with the notice and the policy question; the table row for 2026-09 shows 4.1667%, the blend 2.7072% with its three components (3.5002 / 0.4002 / 3.7502), "+1.4595 pts", "Against the liquid sleeve: +1.9065 pts", and Certified.
"Where is this from?": skipped. `a5_trail.KINDS` has no kind for a benchmark return, and I may not edit it.

## Tests run
- `pytest tests/v1/test_k7_routes.py tests/v1/test_k7.py -q`: 20 passed (8 new, 12 existing K7).
- `npx tsc --noEmit`: no errors in `src/v1/k7`.
- `npx vitest run src/v1/k7`: 3 passed.
Not tested: the HTTP layer through TestClient (handlers are the same `_run` pattern as `k5_routes`; a test checks the router paths equal the permissions file).

## Wiring for the orchestrator
- Link the page from nothing yet: suggest a "Benchmark" link in the Consume centre navigation or the Office page (`/centre/consume/benchmark?portfolio=<code>&code=EG-OFFICE-BLEND`).
- The page asks for a portfolio code by typing; a portfolio picker needs a list endpoint (the Office holdings response has the portfolios).
- Add `benchmark` to `a5_trail.KINDS` if "Where is this from?" is wanted on this table.
- For P14/P15 the checker must call `/api/v1/benchmarks` and `/api/v1/benchmarks/comparison?portfolio=EG-LIQUID&code=EG-OFFICE-BLEND&start=2026-09&end=2026-09` as the approver; the seed must have run `k7_benchmark.certified_return` (it does) for the policy-question case to show in the definitions response.
- Fixture `ui/src/v1/k7/benchmark.fixture.json` is hand-built from the expected figures, not a captured response.

## Review
Verdict: accepted, one small change made.

- Diff: all seven files are new (`k7_routes.py`, `k7.permissions.yaml`, `tests/v1/test_k7_routes.py`, four files under `ui/src/v1/k7/`); no existing file touched, so no `.bak-fixcp` was needed. The other files changed this afternoon belong to fixes L, M, O and the UX1 landings, not to B.
- Money and returns: every figure is a Decimal from `e3_calc` via `k7_benchmark.comparison`, serialised with `str`; `pct` is `quantize(0.0001, ROUND_HALF_UP)`. No floats, no model arithmetic. `_liquid` is a weighted mean of Decimals the calculation already returned; it stays, flagged in the note as the one derived line.
- Permissions: both routes declared with the five roles only; nothing else in the file, so default-deny holds. The handler also requires the consumer seat, and an unseen portfolio is a 404 (E1d), same as a missing one.
- Screen copy: plain. Missing figures read "Not available yet", errors are one sentence, the in-progress notice is the agreed wording. Series keys (`IDX.EQ`) and the e3 problem sentences do appear in the table; they are the names of the market series, which is what a reader would need to chase a missing level. Left as is.
- Changed: `version_used` was fetched by a second `e3_calc.benchmark_definition` call at the end of the last month, while the calculation itself picks the definition in force at each month's opening day. With a version boundary inside the last month the screen would have named a version the figures were not worked out with. It now takes the definition the last month's `comparison` actually used; the `e3_calc` import went with it.
- Tests after the change: `pytest tests/v1/test_k7_routes.py tests/v1/test_k7.py -q` 20 passed; `npx vitest run src/v1/k7` 3 passed; `npx tsc --noEmit` no errors in `src/v1/k7`.

Open items for the orchestrator (unchanged from above, plus one): the spread question. 300 bps over the 30 days from 31 Aug to 30 Sep is 0.2466%, so the private sleeve reads 3.7466%, not the universe's 3.7502%, unless the seed uses about 304 bps or the checker tolerates it. Decide in the seed or the universe, not here. Also decide whether 1.9065 is to be read off `liquid_sleeve.difference` (as built) or whether a signed 60/40 benchmark goes into the seed, in which case `_liquid` can be deleted.
