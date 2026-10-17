# W1b build: Invest domain, cards 51 to 100 (53, 71, 76, 77, 78, 79, 80)

Files: `packs/family_office/1/recipes/invest.yaml` (recipes `vintage_split`, `expected_distributions`, `watch_flags`, `manager_score`, `deal_stage`, `redemption_dates`, `rebalance_trades`; `commit_check` now one row per deal), `packs/family_office/1/signals/uc-053-*`, `uc-071-*`, `uc-076-*`, `uc-077-*`, `uc-078-*`, `uc-079-*`, `uc-080-*` (2 each), `packs/family_office/1/builds/invest-51.yaml` (7 builds), `tests/v1/test_w1b_invest.py`, the `manager_news` reader in `sh_platform/v1/v3_pack_readers_invest.py`, the signed rule `deal_stage_limit_days` (A55) in `reference/office_rules.csv` and `tools/gen_office6m/more.py`, and the card 34, 41 and 53 to 79 entries of `tools/score50.py`.

Test: `pytest tests/v1/test_w1b_invest.py` gives **31 passed** (about 30 s). With `test_w1_invest`, `test_w2_readers_invest`, `test_gen_office6m`, `test_w2_loader`, `test_w3_intake`, `test_v3_recipes` and `test_v3_signals`: 220 passed.
Score: `python tools/score50.py --all` gives PASS for all seven Invest cards 51 to 100, and for 34 and 41; `python tools/score50.py` stays 50/50.
The test loads the six-month office through the real pack readers (`v3_pack_readers.load_plane`), renders and ties out each recipe with `v3_recipes`, runs the signals with the engine's own resolve and calc, and reads every expected number from `answer_keys.yaml`.

## Built

| Card | Recipe | Signals (exception in bold) | Build id (role) | Result |
|---|---|---|---|---|
| 80 `uc-080-vintage` | `vintage_split` | `vintage-split`, **`vintage-bunched`** (skipped until a limit is signed) | `uc-080-vintage` (risk_officer) | pass, 2021 15,000,000 (27.35) ... total 54,850,000 |
| 71 `uc-071-expdist` | `expected_distributions` | `expdist-fund`, **`expdist-stale-value`** | `uc-071-expdist` (investment_analyst) | pass, total 2,660,810 |
| 53 `uc-053-watchlist` | `watch_flags` | `watchlist-flagged`, **`watchlist-missing`** (holds `put_manager_off_watchlist`) | `uc-053-watchlist` (investment_analyst) | pass 32/32: window from 15 Jul; Cedarpoint 2 (amended 1, missing 1), Kestrel 2, Northgate 2 (personnel 1), Saltmarsh 3 (late 2, personnel 1), Bluewater and Meridian 0 |
| 76 `uc-076-scorecard` | `manager_score` | `scorecard-score`, **`scorecard-review`** (no hold: signs none) | `uc-076-scorecard` (cio) | pass 34/34: Bluewater 98.3 add, Northgate 86.8 add, Kestrel 45.4, Cedarpoint 20, Saltmarsh 13 review or exit |
| 77 `uc-077-deals` | `deal_stage` | `deals-stage`, **`deals-stuck`** (holds `advance_deal`) | `uc-077-deals` (investment_analyst) | pass 23/23: five deals, 13,000,000; Marlow (77 days) and Ashgrove (120) stuck |
| 78 `uc-078-redemption` | `redemption_dates` | `redemption-notice`, **`redemption-locked`** | `uc-078-redemption` (ops_lead) | pass 14/14: Macro deal 30 Nov, notice by 16 Oct, cash 14 Dec 6,954,000 (366,000 held back); Long/Short deal 31 Dec, notice by 30 Oct, cash 1 Feb 2027 4,921,000 (259,000) |
| 79 `uc-079-rebalance` | `rebalance_trades` | `rebalance-proposal`, **`rebalance-unsigned`** (holds `execute_rebalance`) | `uc-079-rebalance` (cio) | pass 18/18: book 42,273,700; sell 5,811,695 listed equity, buy 4,817,910 bond and 993,785 convertible; net 0; targets proposed, not signed |

### How each new figure reads the model
- **53 `watch_flags`**: per manager over the 90 days to the as-at date (the card's own window): late = statements received after their `expected_statements` due date (amended not counted), amended, missing (due, never received), personnel changes = `manager_news` mails with a `team_change`. The Kestrel Q3 newsletter carries a team change but is a newsletter, not a mail; the key's method counts mails, so Kestrel's count is 0 (tested). Tie-out: personnel changes = the mails in the window.
- **76 `manager_score`**: per manager and currency: return = (latest value - first value - calls paid + distributions) / first value; fee drag = fee parts of the confirmed call notices / gross gain, 100 when the gross gain is not positive, empty when no fee is on record (the hedge and index funds); on-time share over each non-amended statement received plus each due and never received; watch flags as card 53. Weights, caps and bands come from the signed `manager_score_weights` and `manager_score_bands` (A51). With the weights unsigned, score and verdict are empty and the recipe's `needs` holds it (tested). Meridian is scored too (50.0, keep); the key leaves the index manager out.
- **77 `deal_stage`**: deals nothing supersedes (the pipeline row of Harborlight supersedes the teaser's "Harborlight Ventures Iv"), not declined; days in stage to the as-at date; stuck against the signed `deal_stage_limit_days`. With no signed limit stuck is empty, never 60 by default (tested).
- **78 `redemption_dates`**: the fund's `redemption_terms` fields; dealing dates are the last business day of each month or quarter; the first one on or after the lock-up end whose notice deadline (back to a business day) is not before the as-at date; cash date = dealing date + payment lag, forward to a business day; holdback from the terms. A later lock-up moves the dealing date (tested).
- **79 `rebalance_trades`**: target rules `allocation_<class>` with a `target_pct` (approved first, else the latest proposed); book = the portfolio's latest positions per currency; trade = target - current. `targets_status` says "proposed, not signed: a suggestion only" (A52 keeps them proposed); a signed target shows "signed" (tested). The convertible note has no asset class on record and is counted under its instrument type (`class_from_type` = 1).

### Cards 34 and 41 (top 50) after the five-deal pipeline
Reading the pipeline csv put five deals in `deal_pipeline`. `mandate_fit` was already one row per deal; `commit_check` took the latest deal by stage date (now Nimbus, 1,500,000) and is now one row per deal too: the committee approves one deal at a time and tickets are not added. `score50.py` reads the Harborlight Ventures IV row for both cards (`HARBORLIGHT`), and the planted item of 41 is every deal with no private-markets budget (`budget_status` 'not set'), since the policy signs none for any deal.

## Not built
None. Every Invest card 51 to 100 passes.

## Assumptions I took
- A55 (logged): the 60-day stuck limit signed as `deal_stage_limit_days` (the generator's `STAGE_LIMIT_DAYS`, the key's and M46's value); Monday-to-Friday business days with no holiday calendar; the notice deadline moves back and the payment date forward to a business day; the 90-day watch window is the card's formula; personnel changes are counted from mails only; a statement with no due date on record yet counts as on time.
- The `manager_news` reader follows A43 (document plus `team_change` field); the manager is the part of the subject before ':', else the mail's last line.
- Kept from before: vintage year = the year of `committed_on`; shares per currency; card 71's stale mark is a date comparison, not a day limit.

## Needs
1. **Key question, now answered by the key's method (card 53)**: the Kestrel newsletter's team change is not counted, because the key counts mails. If the office wants newsletters counted, the key of 53 (and 76's watch flags) must change.
2. **Meridian (card 76)**: the key scores five managers and leaves the index manager out; the recipe scores all six. Say whether index managers are scored.
