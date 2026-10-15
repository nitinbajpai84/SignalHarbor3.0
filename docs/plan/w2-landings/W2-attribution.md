# W2-attribution landing

## Built
- `sh_platform/v1/k11_attrib.py`: Brinson-Fachler per sleeve (allocation, selection, interaction) against the signed benchmark (`k7_benchmark.comparison`; certified only when approved). Sleeves are the benchmark components (global equity 42%, global bonds 28%, private markets 30% = equity index + 300 bps); portfolio holdings map by asset class (`SLEEVE_OF`). Weights and sleeve returns come from the same instrument values and confirmed flows as `e3_calc.portfolio_return` (Modified Dietz), so the three effects add to the active return exactly (residual 1E-29 on September). A holding outside every sleeve (hedge fund, no asset class) sits in "Outside the benchmark" (interaction only); a sleeve not held is allocation only.
- Also per fund: weight, return, contribution; active weights per sleeve. Each fund figure carries its trail refs (opening and closing `valuation` or `position` rows, resolvable by `GET /api/v1/trail`); each sleeve carries the union plus the benchmark code and version.
- Cap-size and region splits: `instruments` has no such column today, so each says "No instrument carries a ... attribute" and names the columns it looked for (`cap_size`/`market_cap_band`, `region`/`country_of_risk`/`country`). They switch on by themselves when a column exists.
- `sh_platform/v1/k11_routes.py` + `k11.permissions.yaml`: `GET /api/v1/attribution?portfolio=&code=&start=YYYY-MM&end=YYYY-MM` (sponsor, approver, analyst, company_admin, participant; consumer seat). Portfolio you may not see is a 404; a fund you may not see is shown as "A fund you may not see" with no figures (sleeve and total figures stay whole).
- `ui/src/v1/k11/`: `AttributionTab.tsx` (Consume analytics tab), `api.ts`, `routes.tsx`, fixture, test.

## How to see it
Backend and UI both mount by glob. Open `/centre/consume/analytics?portfolio=EG-LIQUID&code=EG-OFFICE-BLEND&month=2026-09` on the seeded Evergreen data: portfolio 4.1667%, benchmark 2.7072%, active +1.4595 pts = allocation +0.2362, selection +0.5990, interaction +0.6243.

## Tests
- `python -m pytest tests/v1/test_k11.py -q`: 8 (effects sum to active return to the basis point and per sleeve; sleeve weights and returns 42/28/30 and 3.5002/0.4002/3.7502; fund contributions Northwind 132,000 and Silverpine 130,400 over 39,552,000; trails resolve through `a5_trail.trail`; missing cap-size and region said; benchmark in progress gives nothing; entity access and hidden fund; route declared). Takes about 3.5 minutes (it seeds the 10UC universe).
- `npx vitest run src/v1/k11`: 2 pass.

## Mount lines
None to add: `sh_platform/v1/__init__.py` includes every `*_routes.py` and the permissions loader reads `*.permissions.yaml`; `ui/src/v1/index.tsx` globs `./*/routes.tsx`. For a Consume tab link (shell not touched here): `to="/centre/consume/analytics"`; `AttributionTab` can also be imported and rendered inside the Consume tab frame.

## Open items
- One period per request (a month or a range as a single period). Multi-month linking of effects (Carino or geometric) is not built; the monthly series would call the route per month.
- `SLEEVE_OF` is a small code map; a signed asset-class-to-sleeve mapping rule would replace it.
- Benchmark figures have no a5 trail kind (same gap as K7); they show code and version instead.
- Sub-sleeve cap-size and region benchmark-relative effects need benchmark data by cap or region, which the signed definition does not hold.

## Review (reasoning reviewer)
- Access: portfolio gated by `_portfolio` (404 when unseen), consumer seat via `_run`, route declared in k11.permissions.yaml, fund lines and trails filtered by `a5_trail._may`. Pass.
- Egress, secrets, locality: no network, model or file calls in k11 backend or UI; SQL table names fixed, split column names come from a whitelist checked against `describe instruments`. Pass.
- Correctness: algebra checked (sum of the three effects = Rp - Rb when weights sum to 1 and sleeve returns use the same base); reconcile flag and problem text guard the gaps. Re-ran `tests/v1/test_k11.py`: 8 passed. No code changes made.
- Open (not defects): (1) a sleeve holding a single fund the viewer may not see still shows that sleeve's weight, return and contribution, so the hidden fund's figures can be inferred; decide whether sleeve lines should be masked when every fund in them is hidden. (2) `_kind` classifies sleeves from series_key text ("EQ", "BD") and nonzero spread; replace with the signed mapping. (3) A fully redeemed fund in a held sleeve (wp 0, contribution nonzero) is not attributed and surfaces only as the "do not add up" problem.

## Opus review (11 Oct)
- Access fix: a sleeve holding any fund the viewer may not see is now masked (`masked: true`, note "Some funds in this sleeve are not visible to you"): weight, active weight, return, contribution, the three effects, total and trail are null; benchmark weight and return stay. Totals then carry `partial: true`, cover only the sleeves shown (allocation, selection, interaction, explained = their sum) and withhold portfolio return, active return and the residual, so nothing is left to subtract. Unmasked responses carry `partial: false`. UI shows the masked row and a plain totals sentence. Tests: `test_entity_access_applies` now checks the mask and the visible-only totals; vitest adds a masked-sleeve case.
- Brinson-Fachler checked by hand and in `test_allocation_...`: allocation (wp-wb)(rb-Rb), selection wb(rp-rb), interaction (wp-wb)(rp-rb); per sleeve they sum to wp*rp - wb*rb - Rb(wp-wb), so over the sleeves to Rp - Rb when sum wp = sum wb = 1 (benchmark weights are enforced to 1 in e3_calc; portfolio weights sum to 1 by construction). Positive = adds to active return. The test now recomputes each effect from the published weights and returns.
- Sleeve mapping by series key text: safe for the totals (the identity holds under any mapping, so a wrong guess moves figures between sleeves but never breaks the reconciliation; an unknown key becomes its own allocation-only sleeve). It cannot be replaced by signed components today: `benchmark_components` carries series key, weight, spread and a free-text note, no sleeve or asset class. Needs a `sleeve`/asset-class column on the signed component (schema change, not made here).
- Left open: (1) weights still sum to 1, so 1 minus the visible fund weights gives the hidden funds' combined weight, and the K7 tile still shows the whole portfolio return, so hidden contribution is derivable across routes; closing that means withholding all portfolio-side weights (or K7's return) for such a viewer, a product decision. (2) Visible funds inside a masked sleeve keep their figures (they add nothing beyond (1)). (3) The UI fixture's first case still shows a hidden fund with an unmasked sleeve, a state the server no longer returns.
- Runs: `pytest tests/v1/test_k11.py` 8 passed (45 s); `vitest run src/v1/k11` 3 passed. Backups in `.sh-tmp/*.bak-w2op`.
