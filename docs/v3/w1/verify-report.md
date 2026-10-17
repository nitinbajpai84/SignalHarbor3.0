# Verify: report and govern (wave 1)

**Verification of w1 report wave: 31 tests pass, but the figures do not hold up.** I did not write `docs/v3/w1/verify-report.md`, because my instructions say not to write report .md files, so the full table is below.

**Pytest** (`tests/v1/test_w1_report.py`): 31 passed, 0 failed, in 12.85s.

**Counts by severity (24 rows):** wrong figure 10, unsafe 1, missing 8, cosmetic 5.

**5 worst issues:**
1. **uc-047 breaches:** the pack counts 7 real single-name breaches; the key says 1 (`answer_keys.yaml`, `real_breaches: 1`). The test at `test_w1_report.py:495` asserts 7.
2. **uc-048 limit months:** `limit_changes` includes the 2026-03-31 month end, giving 7 months and 7 breaches at 5 percent, and 2 at 6 percent. The key has 6 months, 6 breaches and 1 breach. The test drops March before asserting, so the table itself is wrong. The signal then tells the risk officer "breached in 2 of 7 month ends" (`test_w1_report.py:668`).
3. **Time-weighted return, other entities:** the recipe applies the blended benchmark to every portfolio with no link. EG-FUNDS shows 112.40 percent over all months and 114.81 percent for April. EG-FUNDS March has 2 positions against 4 in April, so that April figure is a start-value gap. EG-B-OPS and EG-PRIVATE show 0.0000 for months that are carried forward, and nothing flags them.
4. **Sovereign exemption:** any instrument with "sovereign" in its name is exempt from the single-name limit by a name match (`single_name_breach`, `limit_changes`, `pack_items`). This is not a signed rule. Unsafe.
5. **uc-047 proposals:** the section sums a noticed call (1,250,000) and a deal ticket (2,000,000) into 3,250,000. The key's 270,000 shortfall is never produced by a recipe; it only appears as a hand-typed dict at `test_w1_report.py:588`.

**Full table (card | issue | severity | evidence):**

| Card | Issue | Severity | Evidence |
|---|---|---|---|
| uc-047 | Breaches section shows 7 real breaches; key says 1 | wrong figure | answer_keys uc-047; test line 495 |
| uc-047 | Proposals adds call and deal ticket to 3,250,000; 270,000 never produced | wrong figure | pack_items; test lines 494, 588 |
| uc-047 | build-report.md says "Pass" and that every number is asserted against the key; breach count, 270,000 and 1,250,000 are not | missing | build-report.md per-card table |
| uc-048 | limit_changes has March (7 months); breaches 7 and 2 vs key 6 and 1 | wrong figure | probe; answer_keys uc-048; test lines 502-507 |
| uc-048 | Review signal says "2 of 7 month ends" at 6 percent | wrong figure | test line 668 |
| uc-048 | Signal subjects show internal rule codes | cosmetic | signals uc-048-policyupd-* |
| uc-044, uc4 | Blended benchmark applied to all portfolios; no link | wrong figure | time_weighted_return `bm` CTE; build-report Needs 8 |
| uc-044 | Carried-forward and estimated month-ends used as real; 0.0000 months | wrong figure | probe; positions dedupe in _shared.yaml |
| uc-044 | EG-FUNDS April 114.81 from start-value gap (2 vs 4 positions) | wrong figure | probe of position totals |
| uc-044 | Dividends and coupons left out of return; April income about 145k on about 40m, larger than April's -0.29 | wrong figure (method; key uses same method, decide) | formula text; transactions |
| uc-044 | No-link signal reads linked_return_pct, which no recipe outputs | missing | signals/uc-044-twr-no-link.yaml |
| uc-046 | Flow months (Apr to Jul) adds_up false, held by show_attribution; no flow version | missing | probe; signals/uc-046-attrib-does-not-add.yaml |
| uc-032 | Cedarpoint 26.73 (band 0-55) vs Oct note 56.50; no alert | missing | probe; build-report Needs 6 |
| uc-033, uc5, uc-047, uc-048 | Name-based sovereign exemption | unsafe | single_name_breach, limit_changes, pack_items |
| uc5, uc4, uc-044, uc-033 | Triggers name figures that are not recipe ids (single_name_concentration, active_return, twr_periods, cost_to_cure); tests bypass triggers, so live firing is unverified | missing | signals grep; v3_signals.py:305-331 |
| uc-033 | Waiver-expired signal needs expires_on, which no table holds | missing | build-report Needs 11 |
| uc-047 | Open-section reminder routes to cio regardless of owner | missing | signals/uc-047-icpack-open-late.yaml |
| uc5, uc-045, uc-047, morning note | Signals fire every run or many times (7 breach messages) | cosmetic | signal conditions; test line 576 |
| uc-033, uc-044, uc-047 | Shows IDX:GLBD:SYN, "linked return", internal figure_ref ids | cosmetic | test line 638; pack_items figure_ref |
| uc-024 | Trace matches exact line name; "(as sampled)" suffix would break a real trace | wrong figure (risk; correct on this sample by chance) | trace_coverage join; key item 8 |
| uc-045 | Missing WMR fixing reported as "does not tie"; same-date reports duplicate sections | cosmetic | report_ready `fx`, `rep` |
| uc-048 | breaches_in_period not partitioned by portfolio; latent merge | wrong figure (latent) | limit_changes final select |
| uc-032 | Drift tie-out only checks shares are 0 to 100 | missing | drift_vs_target tie_out |
| uc-023 | check.expect "4,581" vs recipe -4581; plain-text match risk | cosmetic | builds/report.yaml |

**Checks that passed:** the money sign follows A5 (buys are outflows); all 13 domain cards are covered; the tie-outs for the liquid book match the key (monthly returns, 3.821 since April, attribution 4.1667 / 2.2602 / 1.9065, cost to cure 324,210.53, trace 7 of 8, report sections 3 of 5 ready at 60 percent).

Files reviewed (read-only): `packs/family_office/1/recipes/report.yaml`, `packs/family_office/1/recipes/_shared.yaml`, `packs/family_office/1/builds/report.yaml`, `packs/family_office/1/signals/` (39 files), `tests/v1/test_w1_report.py`, `tests/v1/fixtures/office6m/answer_keys.yaml`, `docs/v3/w1/build-report.md`, `sh_platform/v1/v3_signals.py`. Probe scripts are in the session scratchpad.