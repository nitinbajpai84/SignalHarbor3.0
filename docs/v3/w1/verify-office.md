# Wave 1, domain office: adversarial verification

Reviewer: w1-verify-office (read-only, except this file). Scope: cards 9, 15, 30, 50 (domains "Run the office" and "Family and people", priority 1 to 50; docs/v3/USE-CASES-100.md shows exactly these four in the top 50: Run the office 3, Family and people 1).

## Test run

Command: `"C:/Users/Nitin/Python Projects/Investment Doc Extraction/files/venv/Scripts/python.exe" -m pytest tests/v1/test_w1_office.py -q -p no:cacheprovider --basetemp=D:/Temp/pyt-w1v-office`

- Run 1: 7 failed, 20 passed. Cause: `packs/family_office/1/recipes/report.yaml` (another builder's uncommitted file) had a YAML error at line 374. `test_figure_inputs_name_a_recipe_that_exists` loads every recipe file, so this suite depends on other builders' files.
- Runs 2 and 3 (same command, `--basetemp` suffixed, `--tb=line`): **27 passed, 0 failed**.

## Checks

1. Expected numbers: all 16 `check.expect` values in `builds/office.yaml` appear in `answer_keys.yaml`. None typed or computed by the builder. Pass, with one weakness (row 14).
2. Recipes: formula and grain match the card definitions for the key data. The failures below are for other months, other entities, sign and currency.
3. Signals: each card has an exception signal with a hold. Routes are sensible (card 9 hr_admin; card 15 principal and cfo; card 30 hr_admin and cfo; card 50 ops_lead). Each signal has one action. Probes below confirm specific gaps.
4. Counts: see Test run.
5. Plain words: mostly plain. Row 26 covers the exceptions.

Probe script (not in the repo): `D:/Temp/claude/D--Projects-01-Project-Signal-Harbor/7fe02e29-00ec-496a-a5ad-5bbc0d58c219/scratchpad/probe_office.py`, which imports the test module's own loaders and runs the recipes on changed data.

## Issues

Severity: wrong figure / unsafe / missing / cosmetic.

| # | card | issue | severity | evidence |
|---|---|---|---|---|
| 1 | 15 | The October Trust statement (in the same office folder) shows all four October allowances paid on 1 Oct, and the 213,895.52 cash is measured after those payments. The build lists the key's inputs only, which omit that statement, so a live build shows October as unpaid and due. Repeat-payment risk. The test uses the statement for cash but excludes it for the due amounts. | unsafe | `2026-10/bank_statements/HB_TRUST_USD_2026-10_mtd.xlsx`, Transactions rows AL-Lin/Maya/Ethan/Wen-202610 dated 2026-10-01 (-8000, -6000, -5000, -4000). Daily balance at 13 Oct: HB 153,864.62 + TCB 60,030.90 = 213,895.52. `tests/v1/test_w1_office.py` lines 133 and 158. |
| 2 | 15 | Each allowance approval and the cash-short check test one payment against the same cash figure. Released payments are not deducted, so four approvals can each pass while together they breach the buffer. | unsafe | `uc-015-allowances-approved.yaml` condition `doc.owed + buffer.amount <= cash.cash`. Example: cash 270,000, buffer 250,000. Each 8,000 to 4,000 payment passes (for example 8,000 + 250,000 <= 270,000). Total 28,000 leaves 242,000, below the buffer. |
| 3 | 15 | `allowance_due` is shadowed. The stub in `recipes/family.yaml` has the same id and sorts first, so the loader keeps it and then drops it as a stub. The built recipe is absent from `v3_recipes.recipes()`, so the live card 15 figure does not exist. The tests read `office.yaml` directly and bypass the loader, so they still pass. | missing (blocker) | `v3_recipes.recipes()` returns no `allowance_due`; `v3_recipes._file()` loop with `seen`; `family.yaml` stub has `status: stub`. Builder Needs item 1 confirms the cause. |
| 4 | 15 | Paid is matched with `abs(amount)`, so a positive allowance movement (refund or reversal) counts as a payment. It hides the planted gap. | wrong figure | Probe 6: a +5,000 allowance movement dated 20 Sep makes Ethan Chen's September owed 0 (should be 5,000). |
| 5 | 15 | The `cash_by_entity` figure is grouped by entity, currency and position date, but the signals key on entity and currency only. The engine picks one row, so the cash used may come from an older snapshot. | wrong figure (latent) | `recipes/cash.yaml` grain "By entity and position date"; signals `by: {entity: doc.entity, currency: doc.currency}`. Not probed. |
| 6 | 15 | The total owed sums rows with no currency filter. A future SGD allowance would be added to USD figures. | wrong figure (latent) | `recipes/office.yaml` allowance_due: no currency grouping; the test sums `owed` across rows. |
| 7 | 15 | Payments are paired to schedule lines by paying portfolio, month and amount only. Two members with the same amount in one month can swap attribution. The tie-out checks totals, so a swap passes. | wrong figure (latent) | `q.amount = d.scheduled and q.rn = d.rn` join. Builder Needs item 3 agrees. Reasoned, not run. |
| 8 | 15 | The build's check expects 213,895.52, but its listed files do not include the October Trust statements that produce it. The expected figure is not derivable from the build's own inputs. | missing | `builds/office.yaml` uc-015 `files` list; `test_trust_cash_cannot_cover_the_allowances_after_the_buffer` reads `2026-10/.../_mtd.xlsx`. |
| 9 | 30 | The window uses the renewal date only (0 to 90 days). A contract whose notice deadline falls inside 30 days, but whose renewal is more than 90 days away, is not listed, so the notice exception never fires for it. | unsafe | Probe 1: renewal 100 days out with 90 days' notice (deadline 10 days away) gives no row. |
| 10 | 30 | The notice-near exception fires for a passed notice deadline (days <= 30 includes negatives). The message then says "-40 days are left to give notice" and asks for a call. | unsafe | Probe 3: renewal 20 days out, 60 days' notice, `days_to_notice_deadline` = -40, condition evaluates True. `uc-030-vendors-notice-near.yaml` message. |
| 11 | 30 | Contracts with a renewal date already past (still Active) drop out of the list silently. | missing | Probe 2: renewal 1 Oct 2026 gives no rows. |
| 12 | 30 | Exception reading: the card says "auto-renewal date within 30 days"; the signal uses the notice deadline. The builder disclosed this. The deadline reading is safer for Orchard (a literal 30-day test on the renewal date would fire on 1 Dec, after the 1 Nov notice deadline). Needs Nitin's decision. | missing (spec choice) | `USE-CASES-100.md` #30 signals; `uc-030-vendors-notice-near.yaml` header. |
| 13 | 30 | The "Renewal approved" signal promises the next renewal date is set on approval. No action sets it, and no test covers it. | missing | `uc-030-vendors-approved.yaml` message; builder Needs item 7. |
| 14 | 30 | The expects "79" and "48" are checked as substrings of the key text, so they pass if the digits appear anywhere. | cosmetic | `test_builds_exist_and_their_numbers_are_the_key`, line 291. |
| 15 | 50 | An invoice with no schedule rate produces no signal at all: variance is null, so neither "matches" (== 0) nor "above" (> 0) is true. A card-50 invoice vanishes unchecked. | missing | `invoice_variance` `expected` null; `uc-050-feeinv-arrives.yaml` and `-above-schedule.yaml` conditions. Test checks only the null variance, not a signal. |
| 16 | 50 | An invoice below the schedule (variance < 0) also fires no signal. | missing | Same conditions as row 15. |
| 17 | 50 | The schedule rate and periods are `max()` over every fee_schedule document, with no supersede or date filter. A higher or older schedule row inflates the expected fee. | wrong figure | Probe 4: an extra fee_schedule row at 8 percent gives FEE-CUST-Q3 expected 824,000 (should be 5,150). `recipes/office.yaml` invoice_variance `sch` CTE. |
| 18 | 50 | No check that the invoice currency matches the fee base currency. An SGD invoice against a USD fee base gives a wrong variance. | wrong figure (latent) | `billed` takes `amount_due` currency; `fee_base` currency is never compared. |
| 19 | 50 | Two messages state things that nothing does: "A query to the vendor is drafted" (above-schedule) and "is in the payment run" (matches). Nothing drafts a query or moves a payment. | unsafe | `uc-050-feeinv-above-schedule.yaml` and `uc-050-feeinv-matches.yaml` messages. |
| 20 | 50 | The matches signal routes to ops_lead. The card says "nobody: see it, no work". | cosmetic | `USE-CASES-100.md` #50 signals; `uc-050-feeinv-matches.yaml` route_to. |
| 21 | 9 | Manual steps flagged for automation (key: 1, 2, 3, 4) are produced by no recipe, signal or test. The test checks only the step count and owners. | missing | `answer_keys.yaml` uc9-sop `manual_steps_flagged_for_automation`; `tests/v1/test_w1_office.py` lines 221 to 227; narrative "Manual spreadsheet or hand step: yes" for steps 1 to 4. |
| 22 | 9 | The card's figure `process_steps` is not produced. Signals read fields (`process_name`, `steps`, `steps_without_owner`, `steps_without_check`) from a reader that does not exist. | missing | Builder Needs item 8; `uc9-sop-steps-drawn.yaml` inputs. |
| 23 | 9 | The steps-drawn and SOP-published messages claim lanes, hand-overs, input, output, exception and failure handling. The narrative reader supplies only counts, so approving publication rests on content not checked. | unsafe | `uc9-sop-steps-drawn.yaml` and `uc9-sop-published.yaml` messages. |
| 24 | all | The tests bypass the loader (`_recipe` reads `office.yaml` directly) and never run a signal condition. The "13 signals pass check()" claim is on branch `sh3-signals`, not verified here. | missing | `tests/v1/test_w1_office.py` `_recipe()`, lines 31 to 32; no test evaluates `condition`. |
| 25 | all | The office suite depends on other builders' files: `test_figure_inputs_name_a_recipe_that_exists` loads every recipe file, so a broken `report.yaml` fails it (run 1). | missing | Run 1 traceback: `packs/family_office/1/recipes/report.yaml` line 374. |
| 26 | all | Screen wording: dashboard labels begin "Consume:" (an internal centre name). Messages show raw ISO dates such as 2026-10-01 for `doc.month`. | cosmetic | `builds/office.yaml` `dashboard`; allowance messages in `uc-015-allowances-*.yaml`. |

## Counts by severity

- wrong figure: 6 (rows 4, 5, 6, 7, 17, 18; of which 4 are latent)
- unsafe: 6 (rows 1, 2, 9, 10, 19, 23)
- missing: 11 (rows 3, 8, 11, 12, 13, 15, 16, 21, 22, 24, 25)
- cosmetic: 3 (rows 14, 20, 26)

Total: 26.

## Five worst

1. Row 3: `allowance_due` is dropped by the live loader, so card 15 has no figure in production. The tests pass anyway.
2. Row 1: the October statement shows October allowances already paid on 1 Oct. Without it in the inputs the build would show them as due, risking a second payment.
3. Row 2: each approval is checked against the same cash, so four approvals can together breach the 250,000 buffer (cash 270,000 example).
4. Row 9: the notice window is on the renewal date, so a contract whose notice deadline falls in 30 days but renews in 95 days is never flagged.
5. Row 17: the fee schedule takes the maximum over all schedule rows, ignoring supersedes. An extra row inflates FEE-CUST-Q3's expected fee from 5,150 to 824,000 in the probe.

## Not done

- No file outside this report was edited. Nothing was committed.
- Items 5, 7, 16, 18 are reasoned from the SQL and not run.
