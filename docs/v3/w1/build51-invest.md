# W1b build: Invest domain, cards 51 to 100 (53, 71, 76, 77, 78, 79, 80)

Files: `packs/family_office/1/recipes/invest.yaml` (recipes `vintage_split` and, wave 2, `expected_distributions`), `packs/family_office/1/signals/uc-080-*.yaml` (2) and `uc-071-*.yaml` (2), `packs/family_office/1/builds/invest-51.yaml` (2 builds), `tests/v1/test_w1b_invest.py`, and one stale assertion in `tests/v1/test_w1_invest.py` (Needs 4).
Test: `pytest tests/v1/test_w1b_invest.py` gives **20 passed, 0 failed** (about 20 s). With `test_w1_invest`, `test_v3_recipes` and `test_v3_signals` together: 84 passed.
The test loads the six-month office through the real pack readers (`v3_pack_readers.load_plane`, as `test_w2_loader.py` does), renders and ties out the recipe with `v3_recipes`, and reads every expected number from `answer_keys.yaml`.

Seven Invest cards have no priority (the other 8 Invest cards are in the top 50). Two are built (80, and 71 since the treasury group's `manager_outlook` reader landed in wave 2); five wait, each for a reader that does not exist or a rule nobody has signed.

## Built

| Card | Recipe | Signals | Build id | Result |
|---|---|---|---|---|
| 80 `uc-080-vintage` (risk_officer) | `vintage_split` | `uc-080-vintage-split` (info), `uc-080-vintage-bunched` (exception, skipped until a limit is signed) | `uc-080-vintage` (risk_officer) | pass: 2021 15,000,000 (27.35), 2022 13,000,000 (23.70, 2 funds), 2023 10,000,000 (18.23), 2024 12,500,000 (22.79, 2 funds), 2025 4,350,000 (7.93, 2 funds), total 54,850,000, largest year 2021 at 27.35 percent. Every number and fund list equals the key |
| 71 `uc-071-expdist` (investment_analyst) | `expected_distributions` | `uc-071-expdist-fund` (info), `uc-071-expdist-stale-value` (needs, the exception) | `uc-071-expdist` (investment_analyst) | pass: by quarter 628,215 / 464,215 / 787,115 / 781,265, total 2,660,810; all eight funds' latest value, valuation date, four payout rates, four amounts and total equal the key (Growth I 10,180,000, the amended 30 Sep statement, not the 10,000,000 estimate) |

Card 80, how it reads the model: commitments the register does not supersede (the monthly registers replace one another, so a commitment counts once), by the year of `committed_on`, fund names from `instruments`. Per currency: a second currency gets its own rows, shares and total, never added to USD (planted in a test). A corrected row that supersedes a commitment replaces it (tested: Growth I 15,000,000 to 14,000,000 moves the 2021 row). Tie-out: the total rows equal the register's commitments. `needs`: no commitment on the register holds the figure (tested).

Signals of card 80: the normal one fires for the five years and not on the total row. The exception reads a signed rule `limit_vintage_year` (`max_pct`, the naming of the `limit_*` rules). The policy signs no such limit, so on the office data every row is skipped with "missing rule limit_vintage_year", never guessed; with a test-only 25 percent it fires on 2021 alone (27.35), with 30 it fires on none. No hold: the card's story is read only (signs: none), so there is nothing to block.

Card 71, how it reads the model: the latest statement value of each fund (the `valuation_observations` row nothing supersedes with the latest valuation date) times each quarter's `projected_payout_rate` of the fund's latest `manager_distribution_outlook` document (the treasury reader, A45). Rows per fund and quarter, a total per fund, per quarter and for all funds, per currency. Tie-out: the total equals the values times the rates recomputed straight from the statements and outlooks (`arg_max`, not the recipe's window). `needs`: no outlook rate, or no statement value. Tested: a newer outlook for Income II at 2 percent replaces the 1.5 percent one (384,000 to 512,000); a fund whose latest value is in SGD gets its own SGD total, never added to USD; with the rates removed the figure is held.

Signals of card 71: the normal one fires on the eight fund totals, never on the All funds rows. The exception fires on a fund whose value is older than the newest statement date among the funds of its currency (`is_stale`): Cedarpoint Opportunities II (31 Mar, its June statement never came, BRK-006), Cedarpoint Ventures III and Saltmarsh Renewables I (30 Jun). It compares dates in the data, no day limit. Routed to the Investment Analyst ("chase the statement or tell the CFO"). No hold: the story is read only (signs: none).

## Not built, and why

| Card | Waits for |
|---|---|
| 53 `uc-053-watchlist` | A reader for `manager_news` (the 2 personnel mails: Saltmarsh 18 Aug, Northgate 9 Sep). See below: the other three counts reproduce. |
| 76 `uc-076-scorecard` | A signed scorecard rule (weights 0.4 / 0.2 / 0.2 / 0.2, caps 10 percent return, 50 percent fee drag, 4 flags, bands 75 and 50) and card 53. No such rule is in `business_rules`; the stub's own text says the weights come from a signed rule, never fixed in a recipe. |
| 77 `uc-077-deals` | A reader for `deal_pipeline` (the five-deal csv, two teasers and the follow-up mail; the warehouse holds one deal, Harborlight, from the teaser). The 60-day "stuck" limit is not signed either. |
| 78 `uc-078-redemption` | A reader for `fund_documents` (the Kestrel H1 and H2 redemption terms: dealing frequency, notice days, lock-up end, payment lag, holdback). No Kestrel questionnaire is loaded either. |
| 79 `uc-079-rebalance` | A reader for `target_allocation` (the interim targets). The key says they were proposed on 8 Oct, not signed, so the figure would be a suggestion; the policy sets bands, not targets. No rebalancing rule is signed. |

Card 53 in detail (`test_card53_...`): a draft over `valuation_observations`, `expected_statements` and `extracted_fields` gives, for all six managers, **late, amended and missing equal to the key**: Cedarpoint amended 1, missing 1; Kestrel late 1, amended 1; Northgate amended 1; Saltmarsh late 2; Bluewater and Meridian 0. The fourth count, personnel changes, cannot equal the key from the loaded files:
- Northgate 1 and Saltmarsh 1 in the key come from the `manager_news` mails, which no reader loads (the warehouse gives 0 and 0).
- The Kestrel Q3 newsletter (received 28 Sep, "Thomas Lindqvist left the firm on 30 September") is loaded and carries a `team_change` field, so the warehouse gives Kestrel 1 where the key has 0. The key leaves the newsletter out although it is in the files and in the card's own inputs ("newsletter pdf"). To decide: does the newsletter count as a personnel change (then Kestrel is 3 and the key must change), or not (then the recipe must say why it ignores a `team_change` field)?
The recipe `watch_flags` stays a stub, and `test_w1_invest.py` still asserts it is one. No signal is written for it, because a signal on a figure nobody builds watches nothing. The draft SQL is in the test (`STATEMENT_FLAGS`). When the mail reader arrives (and the newsletter question is answered), that test fails and the recipe can be written from it. The exception signal planned for it: a manager with a missing statement, routed to the Investment Analyst, holding `put_manager_off_watchlist` until the statement arrives or the CIO decides.

The tests of the unbuilt cards (`test_cards_71_77_78_79_wait_for_readers...`, `test_cards_76_and_79_also_wait_for_a_signed_rule`, `test_card53_...`) pass while the reader or rule is missing and fail the day it exists.

## Needs
1. **Readers** (pack readers, `v3_pack_readers.py`, none is in my files; still missing after wave 2, whose four reader groups read none of them): `manager_news` (mail: counterparty, date, subject, body; write a `team_change` field as the newsletter has), `deal_pipeline` (the csv into the `deal_pipeline` table with stage and the date it entered the stage; the teasers and the follow-up mail as documents), `fund_documents` (redemption terms fields), `target_allocation` (class, target percent, status proposed).
2. **Signed rules**, each one a `business_rules` row the office signs, not a recipe constant: `limit_vintage_year` (`max_pct`, card 80's exception), the manager scorecard (weights, caps, bands), the stuck-deal limit in days, allocation targets (card 79).
3. **Key question (card 53)**: the Kestrel newsletter's team change is in the files and not in the key (above). The orchestrator or the key owner decides.
4. **Stale assertion**: `tests/v1/test_w1_invest.py::test_the_invest_recipes_are_built_and_the_others_stay_stubs` listed `expected_distributions` as a stub; dropped now that 71 is built. Drop 53 or 76 from that set the day it is built.
5. **Loader note**: `v3_pack_readers` reports "no reader for this kind" for the four kinds above (`manager_outlook` is now read by `v3_pack_readers_treasury`); `tools/gen_office6m/more.py` `NEW_KINDS` lists them and the two loader tests skip them.

## Assumptions I took (none is a new business rule)
- Vintage year = the year of the register's commitment date (`committed_on`). The key says "fund terms" as the source; the register holds the same dates for all eight funds and the key's totals equal it.
- "Largest year" is marked per currency by the greatest commitment; ties would mark both.
- The share of a year is of that currency's total, because currencies are not added.
- Card 71: the year is the four quarter ends of the manager's latest outlook (the key's 31 Dec 2026 to 30 Sep 2027), taken as written, not cut by a date of mine. A fund with no outlook (the hedge and index funds) gets no rate and no row.
- Card 71's stale mark is a date comparison inside the figure (older than the newest statement of the currency), not a day limit; no limit is signed and none is applied.
- The window and flags of card 53 (90 days, late, amended, missing) are the card's own formula and the key's `how`; they are used only in the draft test.
