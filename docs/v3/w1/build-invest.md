# W1 build: Invest domain (cards 7, 25, 34, 35, 39, 40, 41, 49)

Files: `packs/family_office/1/recipes/invest.yaml`, `packs/family_office/1/signals/<card id>-*.yaml` (19), `packs/family_office/1/builds/invest.yaml` (7 builds), `tests/v1/test_w1_invest.py`.
Test: `pytest tests/v1/test_w1_invest.py` gives **30 passed, 0 failed** (about 55 s). Every number a recipe is asserted against comes from `answer_keys.yaml`.

## How the test proves the recipes
The test builds a small DuckDB from the warehouse DDL (`docs/v2/evidence-to-action-mvp.duckdb.sql`) and loads the office6m files into it (xlsx with openpyxl, PDF text with pypdf).
It renders each recipe with `v3_recipes.render`, runs it, runs the recipe's `tie_out` and `needs`, and asserts the key. It also checks that each recipe reads only its `may_read` tables, and that
the signals pass the engine's own `v3_signals.check` and fire (or stay quiet) on the recipe rows. The production loaders for call notices, statements, questionnaires and teasers do not exist yet, so the
loader in the test stands in for them (see Needs 1). How the model holds the facts (the contract the recipes rely on):

- A call notice is a `call` row (the investment part) and a `fee` row (the fee part): `notice_kind` capital_call, `commitment_id`, `effective_date` = due date, `received_at` = notice date, money out negative (A5). `confirmation_status` is noticed until the bank debit is matched, then confirmed.
- A distribution is a positive `distribution` row, noticed, then a confirmed row (the bank credit, its own amount) that supersedes it. Notice 275,000 and credit 262,500 (M19) is one confirmed 262,500.
- A statement is a `valuation_observations` row (`evidence_document_id` = the statement document); a later row for the same period supersedes the earlier. An amended statement has `valuation_type` manager_amended. The statement's cumulative called is an `extracted_fields` row `cumulative_called`.
- A questionnaire is a `documents` row of type ddq with fields `manager_name` and `ddq: <question>`. A teaser is a `deal_pipeline` row. A meeting note has fields `counterparty` and `meeting_date`; a newsletter has `counterparty` and `team_change`. Fund terms are a `fund_terms` document with `management_fee_rate` (a fraction per billing, A21).

## Cards

| Card | Recipes | Signals | Build id | Result |
|---|---|---|---|---|
| 7 `uc-007-pacing` (cio) | `commitments_by_fund`, `private_markets_budget` | `uc-007-pacing-unfunded`, `uc-007-pacing-over-budget` (exception) | `uc-007-pacing` | pass: by fund 15,000,000/11,250,000/3,750,000 ... Cedarpoint III 10,000,000/7,250,000/2,750,000, total unfunded 14,600,000; budget not set, so the recipe returns no rows and `needs` holds it. With a test-only signed 60 percent rule the headroom is computed |
| 25 `uc7-manager-diligence` (investment_analyst) | `manager_timeline` | `uc7-manager-diligence-team-change`, `uc7-manager-diligence-restated` (exception) | keeps `uc7-manager-diligence` in role_builds.yaml | pass: 9 statement items since 12 June, newest first, with the 7,050,000 to 7,012,500 restatement; the Q3 newsletter team change is the tenth item |
| 34 `uc-034-prospect` (investment_analyst) | `mandate_fit` (uses the commitments logic) | `uc-034-prospect-screened`, `uc-034-prospect-known-manager`, `uc-034-prospect-class-over` (exception) | `uc-034-prospect` | pass: ticket 2,000,000, uncalled 14,600,000 to 16,600,000, 13.7 percent; budget and class limits read "not set". With test-only signed limits budget room and class room are computed and flagged over |
| 35 `uc-035-ddq` (investment_analyst) | `ddq_compare` | `uc-035-ddq-differences`, `uc-035-ddq-fee-answer`, `uc-035-ddq-open-item` (exception) | `uc-035-ddq` | pass: 5 changed answers (12 to 14, 820 to 910 million, key person, 2.0 to 2.25 percent, COO), 16 manager-topic rows, no gap; a deleted answer shows as a gap |
| 39 `uc-039-irr` (investment_analyst) | `fund_irr_tvpi` | `uc-039-irr-by-fund`, `uc-039-irr-incomplete` (exception) | `uc-039-irr` | pass: IRR (2 dp), TVPI and DPI of all 8 funds equal the key (for example Growth I 23.24, 0.9282, 0.0233; Cedarpoint III -40.54, 1.3792). A deleted call makes Growth I `incomplete` with a gap of 500,000 |
| 40 `uc-040-icmemo` (investment_analyst) | `memo_support` | `uc-040-icmemo-figure-source`, `uc-040-icmemo-untraced` (exception) | `uc-040-icmemo` | pass: commitment 10,000,000, called 7,250,000, unfunded 2,750,000, latest value 8,275,000 (amended, 30 June), fee in call 7 350,000, 5 questionnaire changes, each with its source; a figure with no source is `traced = 0` |
| 41 `uc-041-commitappr` (cio) | `commit_check` | `uc-041-commitappr-tests`, `uc-041-commitappr-cosign`, `uc-041-commitappr-cash-short` (exception) | `uc-041-commitappr` | pass: new commitment 2,000,000, uncalled after 16,600,000, cash 6,156,041.41 (12 accounts, 13 Oct fixing), cover 37.08 percent, status short, budget "not set" |
| 49 `uc-049-feedrag` (fund_accountant) | `fee_drag` | `uc-049-feedrag-share`, `uc-049-feedrag-above-terms` (exception) | `uc-049-feedrag` | pass: fees, net and gross gain and drag for the 4 managers equal the key (Bluewater 46,875 / 1,125,787 / 4.16 percent; Northgate 105,000 / 1,309,204 / 8.02 percent; the two with a loss have no drag). Fees above terms: Bluewater 9,375 (M08) |

The recipes of cards 53, 71 and 76 (`watch_flags`, `expected_distributions`, `manager_score`) are outside the top 50 and stay stubs. The new recipes `manager_timeline`, `mandate_fit`, `memo_support` and `commit_check` are the figures of cards 25, 34, 40 and 41 that had no stub.

Notes on how each answers the key:
- `commitments_by_fund` also writes one total row per currency (`is_total = 1`), so "all funds" is a row, not a sum made outside. Its tie-out: committed on the total rows equals the register.
- `fund_irr_tvpi` finds the rate by bisection inside the SQL (a recursive CTE, 60 steps), with the key's day count (actual days over 365) and flows (opening value on the first statement date, confirmed calls and fees out, confirmed distributions in, latest value in at the register date). Its tie-out: called equals the register's called figure.
- `fee_drag` expected fees are the commitment times the fund's `management_fee_rate` for each fee row; only fee rows above that are counted in `fees_above_terms`.

## Signal rows not written as signals (they are the build's output, or have no engine event)
- Card 7 row 2 (Raj asks): the build's `check.ask`.
- Card 25 row 1 (a meeting is booked, the page): the build; no event exists for a booked meeting.
- Card 39 row 2 (quarter-end league table): the build's dashboard; a `schedule` signal can be added when the engine takes a quarter-end date.
- Card 40 row 1 (memo draft): the build; the two memo rows are signals.
- Card 49 row 2 (year end, fee drag next to IRR): the build's dashboard.

## Assumptions I took (none is a new business rule; each can be reversed in the recipe)
- A call logged and not recorded counts as called in `commitments_by_fund` (card 7 says unfunded after call 7 is 2,750,000), but not in the paid figure `fund_irr_tvpi` uses (the key's TVPI divides by 6,000,000, call 7 excluded).
- IRR runs from the first value on file (31 March), not from inception: the data starts there, so "since first call" is "since 1 April".
- The 24-month cash need in `commit_check` is all uncalled commitments (the answer key's stated basis). No signed pacing rule exists; it is labelled in the `need_basis` column.
- `fee_drag` is empty (no drag) where the gross gain is not positive, as the key has it.

## Needs
1. **Loaders** (no production reader exists; the test has a stand-in). Needed: a capital-call notice reader writing the call and fee rows above (skill `read-capital-call-notice`, A25) and a distribution reader plus the bank-credit match; a manager-statement reader writing `valuation_observations` with supersession and `cumulative_called`; a questionnaire reader (`ddq: <question>` fields and `manager_name`); a teaser reader to `deal_pipeline` (the asset class "venture" is mapped by hand in the test; the teaser says "early-stage and growth venture"); meeting-note and newsletter fields (`counterparty`, `meeting_date`, `team_change`); fund terms from `fund_terms.csv` as `management_fee_rate` fractions; bank balances as cash `position_snapshots` and the WMR fixing as `market_observations` (`fx_fixing`, units per USD).
2. **Model note**: `cash_movements.movement_type`/`valuation_observations.valuation_type` need `manager_amended` named in the column note (add-only). The commitments column `called_to_date`/`called_as_at` is read as stated by the register.
3. **Convention to agree with the cash builder**: a call notice is two rows (call = investment part, fee = fee part), both counted as called. If the cash recipes (`called_to_date`, `cash_after_calls`) treat one `call` row as the whole notice, the fee part is missing there. One rule for both.
4. **ASSUMPTIONS.md**: add the 24-month pacing basis (all uncalled commitments, no pacing rule signed) if the office accepts it; and the rule parameter name `max_pct` for `allocation_private_markets` and `allocation_<asset_class>` (MODEL-ADDITIONS names `max_pct`).
5. **Signal wiring**: `figure_changed` events must pass each row of the figure as `doc` (the pattern the office builder's signals use). Signals skip, never guess, when a field is empty (for example the budget room with no signed limit).
6. **Distributions completeness** is not checked in `fund_irr_tvpi` (only calls, against the statements' cumulative called): the statements' per-period distributions are not loaded.
7. **Existing tests that fail because of other builders' work, not this domain** (they fail the same with the original invest.yaml): `tests/v1/test_v3_recipes.py` (4: `renewals_vendors` and `invoice_variance` lack `never_read`; the signal library and recipe-name tests assume the old small lists) and `tests/v1/test_v3_signals.py` (3: the library is now 130+ signals, not five).
