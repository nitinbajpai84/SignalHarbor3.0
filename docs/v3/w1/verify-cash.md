# W1 adversarial check: cash and treasury (eleven cards: 2, 3, 4, 5, 6, 8, 10, 18, 28, 36, 37)

Reviewer: read-only check of the cash builder's output. Nothing else was edited or committed.

Test run: `tests/v1/test_w1_cash.py` gives **41 passed, 0 failed** (19.9 s).

Checked: (1) every `check.expect` number against `tests/v1/fixtures/office6m/answer_keys.yaml`; (2) each recipe's SQL, sources, sign, currency and date grain; (3) each signal's route, action, hold and condition; (4) the test run above; (5) plain words on screen.

Severity: **wrong figure** = a number a person would read is wrong or can be wrong on other months or entities. **unsafe** = a stop or hold the text claims is in force is not enforced, or a status contradicts a block. **missing** = a card rule or exception is not built, not checked, or can never fire. **cosmetic** = wording, duplicates or weak labels.

## Summary

| Severity | Count |
|---|---|
| wrong figure | 14 |
| unsafe | 2 |
| missing | 13 |
| cosmetic | 9 |
| **Total** | **38** |

## Issues

| Card | Issue | Severity | Evidence |
|---|---|---|---|
| 3 (uc6-liquidity) | The existing persona build in `role_builds.yaml` expects 2,305,906.48, 1,252,492.34 and 905,000. None of these is in the 13 Oct key (key: Holdings USD 1,230,000, SGD 1,600,000). Its files are `uc6:2026-07`, a July set. The builder did not report this. | wrong figure | `packs/family_office/1/role_builds.yaml` (uc6-liquidity check); `answer_keys.yaml` uc6-liquidity |
| 36 (uc6-uncalled) | The existing build expects 13,450,000. The key says 14,600,000. The builder reported it but left it as is. | wrong figure | `role_builds.yaml` (uc6-uncalled check); key `uncalled_after_call_7` 14,600,000 |
| 4, 3, 18 | `cash_after_calls`, `fx_required` and `funding_plan` take calls with `due_date >= latest cash date`. An unpaid call (status noticed or expected) that is already past due drops out of the shortfall and the conversion. | wrong figure | recipe SQL: `calls` CTE in `cash_after_calls`, `fx_required`, `funding_plan` |
| 3, 4 | Calls and the buffer use the latest cash date across all entities, but cash uses each entity's own latest date. Calls due between an entity's last date and the global maximum are dropped. Latent until entities report on different dates. | wrong figure | `cash_after_calls` (`lastc` vs `calls`) |
| 2 | `call_fee_check` compares the notice fee with the rate times the fund's commitment summed over all investors (`commit` groups by instrument). The notice names only the fund. Wrong when a fund has more than one investor (latent). | wrong figure | `call_fee_check`, `commit` CTE |
| 6 | `uc-006-fxneed-confirmation-off` compares each bank confirmation with the whole planned conversion (361,800) and never checks the rate against the fixing. The key lists eight other real conversions (1,000,000, 500,000, ...), so every one would be flagged once the tolerance is signed. The 0.1 percent rate test is not built. | wrong figure | `uc-006-fxneed-confirmation-off.yaml` condition; key `conversions` |
| 8 | `payment_batch` has no due-date window. The card asks for payments due in the next ten days, but every expected payment is listed and the totals by currency include later ones. | wrong figure | `payment_batch` `pay` CTE |
| 10 | `cash_by_bank`: an account in a currency with no USD rate gives a null USD value. `sum` drops it silently, so the total and the shares are understated. | wrong figure | `cash_by_bank` `usd` CTE |
| 4, 18, 28 | `funding_plan` is keyed on fund and `is_named`, with no call number. A fund with two open calls gives a list, or the other call's plan. Five signals use this key (uc-004-no-source, uc-018-plan, uc-018-under-buffer, uc-028-lender-short, uc-028-offer). | wrong figure | `funding_plan` columns (no call_no); signals `by:` |
| 28 | `balance_outstanding` takes the lender side's rows only when both sides exist. Repayments recorded only by the borrower are missed. | wrong figure | `intercompany_balance` `net` CTE |
| 37 | `distribution_gap` matches the credit only on the exact pay date. A credit one day late shows as "no credit" with the full notice as the gap, so the chase goes out for money that arrived. | wrong figure | `distribution_gap` `credit` join on `pay_date` |
| 37 | `credit` uses `abs(amount)`, so a reversal or refund counts as money received. | wrong figure | `distribution_gap` `credit` CTE |
| 4 | `uc-004-callcheck-approval` compares the call amount with the limit and ignores currency. An SGD call would be compared with a USD limit. | wrong figure | `uc-004-callcheck-approval.yaml` condition |
| 3, 4, 6 | `cash_by_entity` sums instruments of type cash. If the real loader types bank balances as cash too, every balance counts twice. The test uses `bank_balance` to avoid this, so the test does not catch it. | wrong figure | `cash_by_entity` `instrument_type = 'cash'`; build doc Need 2 |
| 2, 3, 4, 5, 6, 8, 10, 18, 28, 36, 37 | Eight of the eleven exception holds name holds nothing enforces: `record_call`, `close_fx_match`, `release_payment`, `move_cash_to_bank`, `offer_transfer`, `close_distribution`, `state_cash_as_current`, `report_uncalled`. Only `prepare_payment` is enforced. The messages still say the thing is stopped: "cannot be recorded" (card 2), "It is held" (card 8 changed account, the payment-run protection), "It is not offered" (card 28). | unsafe | the `hold:` block in each exception signal; build doc Need 6(d) |
| 8 | `payment_batch` state reads "ready" for a payment to a changed, unverified account when no hold or approval is open. The row's own `release_blocked` is true, so the batch shows a releasable payment that is blocked. | unsafe | `payment_batch` `state` case (ignores `account_changed_unverified`) |
| 2, 3, 6, 8, 10, 28, 36, 37 (all cards) | No loader is called. Every figure comes from the test's own readers, so the platform path and the table shapes are never run. | missing | build doc Need 1; test header ("Stubbed: the loader") |
| 6 | Parts two and three are not built: the bank's rate against the fixing (0.1 percent) for all eight conversions, and the call status after the bank statement. The test checks only 361,800 and 1.34. | missing | build doc Need 9; test `test_card_6_*` |
| 8 | The payment hold and the 1,030 variance are written by the test fixture, which computes the variance in Python and inserts the `payment_hold` row. No recipe or invoice check creates them. The "Pass" is therefore fixture-driven. | missing | `tests/v1/test_w1_cash.py` `payments()` fixture (lines about 255-282) |
| 28 | The reference IC-2026-08-01 and `approval_recorded` are not computed. The test asserts `k["approval_recorded"]` from the key, which is a tautology. | missing | test `test_card_28_the_trust_lent_*`; `intercompany_balance` has no reference column |
| 28 | No signal reads the one-sided transfer exception (`sides_agree` false, `unmatched_rows` 1). The two card 28 signals read `funding_plan`. | missing | `uc-028-interco-*.yaml` triggers and inputs |
| 36 | `uc6-uncalled-adds-up` cannot fire on its first clause. Unfunded is commitment minus called minus noticed, so called plus unfunded always equals the commitment. Only the negative-unfunded clause can fire. The test asserts the identity (line about 353). | missing | `uc6-uncalled-adds-up.yaml` condition; `called_to_date` |
| 3 | `uc6-liquidity-cash-file-late` needs a dated item that is not built, and the layout must name it. Without it the signal never fires. If the item never clears, it fires on every run. Its hold `state_cash_as_current` is not enforced. | missing | `uc6-liquidity-cash-file-late.yaml`; build doc Need 6(b) |
| 37 | A notice that arrives but is never recorded has no `distribution_gap` row, so the chase signal's figure is empty and it never fires. | missing | `distribution_gap` (rows come from recorded movements only) |
| 2, 37 | The test asserts 28,125, 18,750 and 9,375 (Credit III call 3), typed in the test. None is in the answer key. The build doc says test expectations are always read from the key, which is untrue here. | missing | `test_w1_cash.py` line about 346; key has no 28125 |
| 10 | With a signed limit and two banks over it, `worst: 1` returns one bank. The other is dropped silently. | missing | `uc-010-bankexp-over-limit.yaml` `by: worst: 1` |
| 18, 28 | `funding_plan` joins commitments with an inner join. A call with no `commitment_id` disappears from the plan with no warning. | missing | `funding_plan` `plan` CTE |
| 8 | The changed-account signal fires only on invoice arrival. A capital call payment to a changed account has no signal of its own; only uc-005 covers it, and only if the payment is prepared. | missing | `uc-008-payrun-changed-account.yaml` trigger `file_arrived` `invoice` |
| 37 | `uc-037-distrack-no-credit` relies on a layout date field with "due" in its name (unverified), and compares a string pay date with a date field. | missing | `uc-037-distrack-no-credit.yaml` |
| 8 | `batch_total_in_currency` adds held and waiting amounts together under a "total" label. Read as "to release" it overstates the releasable amount. | cosmetic | `payment_batch` `batch_total_in_currency` |
| 18, 28 | `uc-018-fundplan-under-buffer` and `uc-028-interco-offer` both fire for one call when the lender can cover it. | cosmetic | the two signal conditions |
| 18 | The card 18 key gives negatives (-270,000 and -36,104.48). The build expects positive magnitudes; the test accepts magnitudes. | cosmetic | `answer_keys.yaml` uc-018-fundplan; `role_builds`/cash build expects |
| 18 | The message uses "cover"; column names such as `best_other_spare`, `is_named` and `sides_agree` may reach the screen if the consume layer shows raw columns. | cosmetic | `uc-018-fundplan-plan.yaml` message; recipe columns |
| 28 | The tie-out's right-hand side is `0 * count(*)`. It checks netting only, not row pairing, so its label overstates it. | cosmetic | `intercompany_balance` tie_out |
| 37 | An overpayment (received above notice) shows the status "short". | cosmetic | `distribution_gap` `status` case |
| 5 | `uc-005-benefcheck-hold` fires on `uc01-cash-shortfall`, not on notice arrival, and overlaps `uc01-bank-changed`. | cosmetic | `uc-005-benefcheck-hold.yaml` trigger |
| 2 | The `called_to_date` tie-out sums amounts across currencies. | cosmetic | `called_to_date` tie_out |
| 6 | `fx_required` gives one row per quote currency if another FX pair is loaded, and its tie-out sums those rows across currencies. | cosmetic | `fx_required` join on `base_currency` only |

## Notes

- Route and action checks pass: each signal goes to a role that exists in the team, and each card has at least one exception signal with a hold.
- Signs match ASSUMPTIONS A5 (calls and payments are negative, distributions and credits positive); the recipes take absolute values where needed.
- All 25 expected numbers in the nine persona builds in `builds/cash.yaml` appear in the key for their card.
- Not run in this check: `test_v3_signals.py` and `test_v3_recipes.py` (the build doc says they now fail).
