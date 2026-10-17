# W1b build: Report and govern, cards 51 to 100

Domain "Report and govern", cards with no priority: `uc-074-boardpack` (74) and `uc-075-yearwalk` (75). Synthetic Evergreen office only.

Files: `packs/family_office/1/recipes/report.yaml` (recipes `board_summary` and `networth_walk` added), `packs/family_office/1/signals/uc-074-boardpack-*.yaml` (3) and `uc-075-yearwalk-*.yaml` (3), `packs/family_office/1/builds/report-51.yaml`, `tests/v1/test_w1b_report.py`, `tests/v1/test_w1_report.py` (two lines), this page.

**Test result:** `pytest tests/v1/test_w1b_report.py tests/v1/test_w1_report.py` gives 54 passed, 0 failed (about 43 seconds). With `test_v3_recipes`, `test_v3_roles`, `test_v3_figstore`, `test_v3_regressions`: 53 passed.

## Built: card 74, family board pack

| Item | State |
|---|---|
| Recipe `board_summary` | ready. One row for the liquid book that has a signed benchmark link |
| Signals | `uc-074-boardpack-headline` (info, principal), `-estimate` (needs, cio), `-amended` (problem, cio, **holds `issue_board_pack`**) |
| Build | `uc-074-boardpack` under role `principal`; files are the key's `input_files` with `office6m:`; `check.expect` copied from the key |

Numbers the recipe gives (all equal the key): net worth USD 57,600,000 and SGD 77,253,120 at 1.3412; "Evergreen Growth I is an estimate in the issued report"; liquid book 3.5148 percent for 2026Q3 (benchmark 5.0052) and 3.821 over every month loaded against 5.7563 for the benchmark; cash USD 6,156,041.41 at 13 Oct; call shortfall 270,000; uncalled commitments 14,600,000; 1 statement amended after the last issued report.

How it is made: the card's figure is a headline over five other figures (report total, return, cash, call shortfall, uncalled, amendments). A recipe may read tables only (A8), never another recipe's ready table, so `board_summary` holds the SQL of `report_total_fx`, `time_weighted_return`, `cash_by_bank`, `cash_after_calls`, `called_to_date` and `amendments_open` as common table expressions, taken from their recipes by a script and changed in no line. `test_the_board_figures_equal_the_recipes_that_own_them` runs each of the six beside it and asserts the same values, so a sibling changed without the board fails the test.

Honest edges, all from the data and no rule invented:
- The cash shortfall is the sum over entities that have a call due. With no signed `cash_buffer` it is empty, not zero, and `call_entities_unmeasured` counts entities with a call but no shortfall (tested by removing the rule).
- Cash is empty when one bank account has no rate to USD. Uncalled counts USD commitments only; `uncalled_other_currency` counts the rest.
- With no signed `benchmark_link` the return columns are empty and the other figures stay (tested).
- "Since 1 April" is "every month loaded": `performance_from` and `performance_to` show the dates, so the label cannot drift silently. The last complete quarter is read from the data (2026Q3), not typed.
- The signals' exception is an amendment received after the last issued report, which is the one open item in the key. The estimate signal has no hold: the report total is still stated, with the estimate named beside it.

## Built: card 75, what happened to our worth (with two figures the files cannot give)

| Item | State |
|---|---|
| Recipe `networth_walk` | ready. One row for the period from the day after the last month end before the first office bank balance (31 March) to the last month end on or before the last balance (30 September) |
| Signals | `uc-075-yearwalk-headline` (info, principal), `-estimate` (needs, cio), `-incomplete` (problem, cfo, **holds `present_networth_walk`**) |
| Build | `uc-075-yearwalk` under role `principal`; files are the key's `input_files` with `office6m:`; `check.expect` holds the seven figures below, written as the key has them |

The expense ledger now has a reader (`v3_pack_readers_controls`, table `office_expenses`), which was the reason card 75 was not built before.

**Figures the recipe gives and the key has, to the cent:** investment gains 540,967 (liquid book 1,514,870, funds and hedge funds -973,903), spending 1,263,862.76, closing net worth 114,394,995.51, capital calls paid 5,950,000, distributions received 767,500. These seven are in `check.expect`.

**Figures it cannot give, and why (each is in the data, none is a rule):**
- **Opening net worth 114,568,027.06 and the balancing item (`fx_and_other`, 94,195.23, 0.082 percent): empty.** The opening cash of the three Singapore dollar account groups needs the USD/SGD fixing of 31 March. The first fixing in any file is 1 April (`fx_rates` starts that day; there is no March investment report). The recipe does not borrow 1 April or any other day: `opening_fixing_missing` says 3 and `opening`, `opening_cash_usd_eq`, `fx_and_other`, `adds_up` are empty. The parts that need no fixing are shown (`opening_funds`, `opening_book`, `opening_loan`). Proved: with the generator's own 31 March fixing put in the warehouse for one test (rolled back), the opening equals the key to the cent and the walk adds up (`test_card_75_with_the_31_march_fixing_loaded...`).
- **Income 455,624.27 against the key's 455,668.98 (44.71 short).** The July statement of the Tidewater USD account of Entity B never arrived (M02b, expected 6 August). Its 44.71 of interest is in the key and in no file. The recipe counts the gap (`bank_months_missing` = 1) and the signal `-incomplete` says so. With the fixing loaded, the balancing item is then exactly 44.71 above the key's, which is the same gap. Income is therefore not in `check.expect`.

How it is made: net worth at a date is the funds (every instrument with a manager valuation, the latest period on or before the date, amended over final over estimate, as known on the last day loaded; the two index funds are funds here, as the key has them) + the liquid book (positions of instruments that are not funds and not cash) + the office banks' cash (SGD at the latest fixing on or before the balance date) less the loan statement's amount owed. The opening cash is the first balances less the confirmed movements since the month end; the opening loan is the first statement's interest over the facility rate / 12. Gains are as the key's `how` says: the book less the net settled buys and sells, the funds less calls plus distributions. Spending is the ledger without the debt service lines (the loan interest comes from the loan statements instead) plus that interest. A figure that needs a fixing the files do not have is empty, never a partial sum (tested: with every fixing removed, the closing, income, spending and balancing item are empty and the liquid book gain stands).

Honest edges:
- The tie-out is the closing liquid book against the position snapshots of its date. A tie-out of the bank balances against the movements fails by 3.33 on this office because of the missing July statement (interest 44.71 less a bank fee of 48.04), so it is not used; the missing month is a column instead.
- Two fund values at 30 September are manager estimates (`closing_estimated_funds` = 2, signal `-estimate`).
- The key has six months of data, not twelve; the period comes from the first balance on file, not from "this year".
- The fund list is not typed: "has a manager valuation" is the test, so a fund added later enters the walk by itself.

## Rescore, 17 Oct (after the rules A48-A52 and the last readers)

| Card | Before | After | Why |
|---|---|---|---|
| 74 board pack | FAIL (9/9 values right, figure bound to `net_worth`) | **PASS** 9/9 | The figure's name "Net worth, return, liquidity, decisions" matched `net_worth` by its name "net worth". `board_summary` now answers to that full name, which outscores the short one. Proved by `test_card_74_figure_binds_to_board_summary_not_net_worth` (plain "Net worth" still binds to `net_worth`). |
| 75 year walk | FAIL 8/11 | FAIL 8/11 (unchanged, reasons named) | Checked again: no file has the 31 March USD/SGD fixing. `fx_rates` starts 1 April, the first investment report is April's (1.3298 at 30 April), and the bank statements carry no rate. The opening and balancing item stay empty and the income stays 44.71 short (M02b). No rate is borrowed. |

`--all`: 76 PASS, 3 FAIL, 21 BLOCKED (was 75/4/21). The top 50 is 48/50; the two fails are 34 and 41 (Invest, from the five-deal csv reader), not this domain. Tests: `test_w1b_report.py`, `test_w1_report.py`, `test_v3_recipes.py` give 69 passed.

## Needs

1. **The USD/SGD fixing of 31 March** (a `fx_rates` file for that day, or a March investment report, which states the WMR rate). With it the opening and the balancing item fill in with no change to the recipe.
2. **The July statement of the Tidewater USD account of Entity B** (M02b), for the 44.71 of interest. Until it arrives the income is short and the signal `-incomplete` stays on.
3. **Signal inputs:** the three signals read the recipe's own columns, so no extra input is needed from a watcher. Trigger is `figure_changed` on `networth_walk`.
4. **Board recipe size (card 74)** is about 20 KB of SQL because it repeats its siblings. If the recipe format later allows reading another recipe's ready table, replace the copies with reads. The `never_read` of `board_summary` is `deal_pipeline` and `committee_decisions`; the walk's is the same.
5. **Tests outside my files:** `tests/v1/test_w1_report.py::test_every_recipe_is_built_reads_only_what_it_may_and_ties_out` is changed in two lines: it builds and checks the 13 top-50 recipes as before and states that the only other ready recipes are `board_summary` and `networth_walk` (proved in `test_w1b_report.py`, which loads the real office).
