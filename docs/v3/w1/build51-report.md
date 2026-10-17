# W1b build: Report and govern, cards 51 to 100

Domain "Report and govern", cards with no priority: `uc-074-boardpack` (74) and `uc-075-yearwalk` (75). Synthetic Evergreen office only.

Files: `packs/family_office/1/recipes/report.yaml` (recipe `board_summary` added; `networth_walk` stays a stub with a note), `packs/family_office/1/signals/uc-074-boardpack-*.yaml` (3), `packs/family_office/1/builds/report-51.yaml`, `tests/v1/test_w1b_report.py`, this page.

**Test result:** `pytest tests/v1/test_w1b_report.py` gives 11 passed, 0 failed (about 22 seconds). It loads the office through the real loader (`v3_office6m_loaders`, as `test_w2_loader.py` does), runs the recipe the way `v3_recipes` renders it (A8 tables check and tie-out included) and asserts every number against `answer_keys.yaml`.

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

## Not built: card 75, what happened to our worth this year

Reason: the walk's spending leg is the expense ledger (`expense_ledger_2026-04_to_2026-09.xlsx`). The loader has no reader for that kind (it is in `NEW_KINDS`; `test_card_75_...` proves `not_loaded` says "no reader for this kind" and no source batch exists), and the model has no home for it (A23 leaves `office_expenses` for later). The key's spending is the ledger without debt service plus loan interest; it cannot be rebuilt from bank statements without inventing a mapping. The recipe `networth_walk` stays `status: stub`, there are no signals and no build. The other legs (fund values as known, book, bank cash, loan, calls, distributions, income) do load; only spending and so the balancing item `fx_and_other` are missing.

## Needs

1. **Card 75:** a reader for `expense_ledger` and a place for its rows (add `office_expenses` under A11, or load them as `cash_movements` of type `payment` with a category), then fill `networth_walk`. The key has six months of data, not twelve.
2. **A test outside my files fails because of the new recipe:** `tests/v1/test_w1_report.py::test_every_recipe_is_built_reads_only_what_it_may_and_ties_out` asserts the set of ready recipes in `report.yaml` equals the 13 top-50 recipes (`MINE`). `board_summary` is a new ready recipe, so it needs `<=` (or `MINE` plus `board_summary`). Every other check in that test passes for it (A8, tie-out, one line, columns). I did not edit the file.
3. **`never_read` of `board_summary`** is `deal_pipeline` and `committee_decisions` because it legitimately reads commitments, cash movements and transactions. If a rule wants those three in every report recipe's `never_read`, the board recipe cannot satisfy it.
4. **Signal inputs:** the three signals read the recipe's own columns, so no extra input is needed from a watcher. Trigger is `figure_changed` on `board_summary`.
5. **Recipe size:** the board recipe is about 20 KB of SQL because it repeats its siblings. If the recipe format later allows reading another recipe's ready table, replace the copies with reads.
