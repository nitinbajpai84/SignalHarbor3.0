# W1 verify: Hold and maintain (cards 13, 17, 21, 31, 38, 43)

Adversarial review of the builder's output (docs/v3/w1/build-hold.md). Read-only except this file.

Test run: `pytest tests/v1/test_w1_hold.py -q -p no:cacheprovider --basetemp=D:/Temp/pyt-w1v-hold` gives **15 passed, 0 failed**. The counts pass, but several checks are weaker than the summary says (see rows marked missing).

Severity: wrong figure = a number shown is wrong or can be wrong on other data; unsafe = a person can be told a thing is fine when it is not, or an exception can be silently skipped; missing = a check, signal or test that should exist does not, or cannot fail; cosmetic = wording or formatting only.

Answer-key check: every check.expect number for the six cards exists in answer_keys.yaml. No builder-typed expected number was found that is absent from the key, except the test-only figures noted in row 21.

| card | issue | severity | evidence |
|---|---|---|---|
| 13 | Holdings with no position rows (exited, or in the master only) count as gaps at zero value, so gap_count and gap_pct inflate on other months. The fixture has 32 instruments, all with positions, so the test does not catch it. | wrong figure | recipes/hold.yaml:48 `from instruments left join held`; gap_count window counts has_gap regardless of market value |
| 13 | Each instrument is carried at its own last position date. A holding that drops out of the latest file keeps its old value in gap_value_total, net_worth and gap_pct, so the totals mix dates. | wrong figure | recipes/hold.yaml:30-48 (`last` CTE per instrument); build-hold.md item 7 admits the 1,119,900 vs 1,122,000 effect |
| 13 | Signal title says "Unclassified holdings above 1 percent", but the metric also counts no-identifier holdings (card row: "no class or identifier"). The completed signal says "Allocation and limits recompute", which nothing does. | cosmetic | signals/uc-013-secgaps-over-one-percent.yaml line 2; uc-013-secgaps-completed.yaml message |
| 17 | Debt is summed as stored with no sign guard. The recipe text says "always the positive amount owed", but only the test loader applies abs(). If a loader stores the statement's negative balance, net worth after debt rises by 5.6m (2 x 2.8m). | wrong figure | recipes/hold.yaml:278 `sum(drawn_amount) as debt`; tests/v1/test_w1_hold.py:178 abs() in load_loans only |
| 17 | Closed facilities still count in debt. The debt CTE does not filter status; facility_headroom does. | wrong figure | recipes/hold.yaml:278 vs :315 `f.status <> 'closed'` |
| 17 | Covenant check reads only first_row, the latest-dated facility. Another facility under its line is never flagged. Headroom is also mixed across currencies. | unsafe | recipes/hold.yaml:300-315 `first_row`; signals/uc-017-liab-headroom.yaml `by: {first_row: true}` |
| 17 | The covenant signal can never fire on current data: no limit in the facility rows (headroom is null), and facility_headroom_line is not signed. The exception is dead, not just waiting. | missing | test line 260-268 asserts headroom None; build-hold.md item 5 |
| 17 | "A drawdown is recorded" does not detect a drawdown. It fires on every loan statement while debt > 0, and the message says only "a loan statement was recorded". | missing | signals/uc-017-liab-drawdown.yaml condition `nwd.family_debt > 0` |
| 17 | The headroom message calls `line - headroom` the "margin". It is the shortfall. | cosmetic | signals/uc-017-liab-headroom.yaml `let: {margin: line.amount - fac.headroom}` |
| 21 | Estimates count as valuations. Two Kestrel Ridge funds have only a 30 Sep 2026 estimate, which the recipe takes as the latest value, so they show 13 days old and fresh. Nothing filters approval_status. The key accepts this (answer_keys 660-664), so the key itself needs an owner decision. | unsafe | recipes/hold.yaml:69-88 no approval filter; tests/.../test_w1_hold.py:148 loads status "estimate" as a valuation; manager_statements/2026-10/kestrel_*_2026-09-30_estimate.pdf |
| 21 | The stale-found message says the stale funds "are marked stale in the limits and report notes". Nothing marks them. The signal has no hold, while the card says "so we do not lean on them". | unsafe | signals/uc-021-stale-found.yaml line 20; no hold block in the file |
| 21 | The breach-on-stale signal checks only the stalest fund (`by: issuer: age.stalest_fund`). A limit breach on another stale fund (Cedarpoint Ventures III, Saltmarsh Renewables I) is never raised. The limit rule is also unverified (`limit.value`). | unsafe | signals/uc-021-stale-breach-on-stale.yaml `by: {issuer: age.stalest_fund}`; build-hold.md item 6 |
| 21 | Age is measured against the latest position date loaded, not the calendar date. If the October custodian file is missing, the as-of date falls back and staleness is understated. | wrong figure | recipes/hold.yaml:83 `coalesce(max(position_date), ...)` |
| 21 | The fresh signal fires for every fresh statement and says the fund "leaves the stale list", even when it was never on it. | cosmetic | signals/uc-021-stale-fresh.yaml message; condition `not age.stale` |
| 31 | No defect found. Allocation adds to positions_total, shares sum to 100, and the unclassified value and percents match the key (1.04). | none | recipes/hold.yaml:102-140; key 958-992 |
| 38 | If the gain line cannot be read, reported_gain and unexplained are null, so both the ties and the unexplained signals stay silent. Nothing flags an unreadable statement. | unsafe | recipes/hold.yaml:173 left join; signals/uc-038-navroll-unexplained.yaml `abs(rf.unexplained) > 0.01` (null is not > 0.01) |
| 38 | Estimates are not filtered in the roll-forward. A quarter closing on an estimate with no amended or final statement rolls forward on that estimate. Not triggered by the current private funds, which all have final or amended Sep values. | unsafe | recipes/hold.yaml:159-173 `obs` filters supersedes only |
| 38 | The tie-out cannot fail. implied_gain is defined as closing - prior - calls + distributions, so prior + calls - distributions + implied_gain = closing always. | missing | recipes/hold.yaml:186-188 tie_out sql; build-hold.md tie-out column |
| 38 | The gain lookup (`left join extracted_fields`) is not de-duplicated. A document with two net_gain_loss rows (a re-extraction) duplicates the quarter row. | wrong figure | recipes/hold.yaml:173 |
| 38 | Check expect "875,000" drops the sign. The key says implied_gain -875000 (Cedarpoint Ventures III Q2). A sign flip would still pass. | missing | answer_keys.yaml 1183; builds/hold.yaml uc-038-navroll expect; test line 413 compares with commas stripped and no sign |
| 38 | The four "unexplained" figures in build-hold.md (Growth I Q2 108,181 and Q3 396,980; Income II Q2 229,452 and Q3 182,582) are not in the answer key. The test asserts only 108,181 and -210,957 (reported gain). The reported gain matches the June statement; the key has no such number. | missing | tests/v1/test_w1_hold.py:336; answer_keys has no reported-gain figure for uc-038 |
| 38 | The statement message prints "+ gain" but never shows the gain, so a reader cannot check the sum. | cosmetic | signals/uc-038-navroll-statement.yaml message |
| 43 | The liquid figure is the largest book only (first_row). The signal says "The liquid book is ...". A second listed portfolio, or a portfolio with no month-end snapshot (dropped by the inner join on the month-end date), is silently left out. | wrong figure | recipes/hold.yaml:214 `join tot as t0`; signals/uc-043-liquidpnl-daily.yaml message |
| 43 | The month-start signal fires on every scheduled run with the text "A new month". Its only condition is value_month_end > 0. | missing | signals/uc-043-liquidpnl-month-start.yaml trigger schedule, condition `pnl.value_month_end > 0` |
| 43 | The price-jump signal checks only the largest move of the latest date. A jump over 10 percent on an earlier date, or a second one on the same day, is never signalled. The "held for review" wording has no review step behind it. | unsafe | recipes/hold.yaml:237-258 `top_move` is one row over the whole table; signals/uc-043-liquidpnl-price-jump.yaml |
| 43 | Test precedence bug: `assert A and B or C` makes the top-move check always true. | missing | tests/v1/test_w1_hold.py:368 |
| 43 | Check expect "11,100" drops the sign. The key says gain_loss_mtd -11100 and the builder's own output is -11,100. | missing | answer_keys.yaml 1363; test line 355 asserts the sign, but the build check does not |
| all | The build check (`test_builds_carry_the_exact_answer_keys`) searches the whole answer-key file, not the card's own block. Short expects match anything: "196", "105" (inside 105430000), "36.37". | missing | tests/v1/test_w1_hold.py:412-413 |
| all | No test shows that any exception signal fires on the key data. The tests check only file format and recipe numbers. | missing | tests/v1/test_w1_hold.py:376-414 |
| all | Subject lines print raw decimals, for example "identifier gaps closed at 108230000.00", "allocation difference ...: -1122000.00", raw prices like 0.986500. Not plain words. | cosmetic | signals/uc-013-secgaps-completed.yaml subject; uc-031-alloc-not-adding-up.yaml; uc-043-liquidpnl-price-jump.yaml message |

## Counts by severity

- wrong figure: 7 (rows 1, 2, 4, 5, 13, 19, 23 of the table; several are latent on other data)
- unsafe: 7
- missing: 10
- cosmetic: 5
- none: 1 (card 31, reported as no defect)
- Total rows: 29 issues plus one clean card

## Five worst issues

1. Card 21: estimates are treated as valuations, so the two Kestrel Ridge funds read as fresh (13 days) on a Sep estimate. The answer key agrees with this, so the rule is wrong in the key too, and someone with authority must decide.
2. Card 21: the stale message says stale values are "marked" in limits and reports, but nothing is marked and no hold stops anyone leaning on them.
3. Card 21: the breach-on-stale signal checks only the stalest fund, so a breach on another stale fund is never raised.
4. Card 38: an unreadable manager gain makes both exception signals silent, so an unexplained roll-forward can pass unnoticed.
5. Card 17: net worth after debt has no sign guard in the recipe. A loader that stores the statement's negative balance overstates net worth after debt by 5.6m.

Not yet reviewed in depth: the rules file reads (single_name_limit_pct as limit.value) and the signal engine's `by` semantics, which the builder says are assumed. Neither was checked against the engine branch.
