# Wave 1, domain office: build notes

Cards of the domain "Run the office" and "Family and people" with priority 1 to 50: **9** (uc9-sop), **15** (uc-015-allowances), **30** (uc-030-vendors), **50** (uc-050-feeinv). Synthetic data only.

Files: `packs/family_office/1/recipes/office.yaml`, `signals/uc9-sop-*`, `uc-015-allowances-*`, `uc-030-vendors-*`, `uc-050-feeinv-*`, `builds/office.yaml`, `tests/v1/test_w1_office.py`.
Test run (wave 2): `pytest tests/v1/test_w1_office.py` gives **39 passed, 1 xfailed, 0 failed**. All 17 signals pass the engine's own `check()` with the roles of `role_builds.yaml` (run on main). Wave 2 fixes: see "Wave 2: the verifier's rows" at the end.

## Card 9, uc9-sop: Process map and SOP for the month-end report
- **Recipes:** none. No table holds a process; the figure (steps with owner, system and check) is read from the narrative document.
- **Signals:** `uc9-sop-steps-drawn` (hr_admin, approve), `uc9-sop-published` (hr_admin, approve, after the first), `uc9-sop-step-gap` (exception, hr_admin, call_back, holds `publish_sop`).
- **Build:** keeps `uc9-sop` in `role_builds.yaml` (not duplicated).
- **Test:** pass. The six steps of the narrative are parsed: 6 steps, owners equal the key (Mei Chen x3, Raj Patel x2, Daniel Foo), every step has an owner, a system and a control.

## Card 15, uc-015-allowances: Family allowances and distributions due
- **Recipe:** `allowance_due` (in `office.yaml`, ready), by member and month: scheduled, paid, owed, earlier. Tie-out: owed equals scheduled less every allowance paid in the same months.
- **Signals:** `-due` (principal, approve), `-approved` (cfo, release, only when cash covers it after the buffer), `-cash-short` (exception, cfo, holds `prepare_payment` for the entity), `-unpaid-earlier` (exception for the planted gap, principal, holds `prepare_payment` for the member).
- **Build:** `uc-015-allowances` under `principal`, with the October month-to-date Trust USD statements added to the key's inputs (wave 2, row 1). Expect: 8,000; 6,000; 5,000; 4,000; 213,895.52.
- **Test:** pass. Key scenario (September and October schedules, September Trust statement): due October Lin 8,000, Maya 6,000, Ethan 5,000, Wen 4,000; unpaid earlier Ethan Chen September 5,000; total owed 28,000. Over all history (April to October schedules, April to September statements) the only unpaid earlier line is Ethan's September. Trust USD cash 213,895.52 (HB 153,864.62 + TCB 60,030.90 at 13 Oct) is below the signed 250,000 buffer, so the cash-short signal fires.

## Card 30, uc-030-vendors: Vendors and contract renewals
- **Recipe:** `renewals_vendors` (stub filled, ready), by contract: annual cost, days to renewal, notice deadline, days to notice deadline, auto_renews, decision_open. Tie-out: rows equal contracts on file inside 90 days.
- **Signals:** `-renewing` (hr_admin, record), `-approved` (cfo, approve), `-notice-near` (exception, hr_admin, call_back, holds `renew_contract`).
- **Build:** `uc-030-vendors` under `hr_admin`. Expect: 35,400; 19,200; 79; 48.
- **Test:** pass. Two contracts renew inside 90 days of 13 Oct 2026: Orchard IT Services SGD 35,400, 2026-12-31, 79 days; Quill Research Subscriptions USD 19,200, 2026-11-30, 48 days. Marina and Summit are outside the window. Orchard's notice deadline is 2026-11-01 (60 days' notice), 19 days away.
- **One reading of the card:** the exception row says "auto-renewal date within 30 days". The signal counts the 30 days to the notice deadline (renewal date less notice days; the renewal date when no notice period is stated), because the deadline is when the decision must be made. For Orchard, a 30-day test on the renewal date would fire on 1 Dec, a month after the deadline. If the card is meant literally, change the condition to `doc.days_to_renewal <= 30`.

## Card 50, uc-050-feeinv: Administrator and custodian invoices against the fee schedule
- **Recipe:** `invoice_variance` (new, ready), by invoice: billed, expected (fee base x schedule rate / billing periods, to the cent), variance, billed and schedule rate in percent. Tie-out: billed equals the amount due of every fee invoice read.
- **Signals:** `-arrives` (ops_lead, approve, variance 0), `-matches` (ops_lead, see, after approval), `-above-schedule` (exception, ops_lead, record "send the query", holds `prepare_payment` for the invoice).
- **Build:** `uc-050-feeinv` under `ops_lead`. Expect: 15,595.58; 4,940.14; 16,234.5; 6,180; 5,150; 1,030.
- **Test:** pass. Four invoices equal the key: Admin Q2 15,595.58 / 15,595.58, Cust Q2 4,940.14 / 4,940.14, Admin Q3 16,234.50 / 16,234.50, Cust Q3 billed 6,180 against 5,150, variance 1,030, billed at 0.06 percent against 0.05 on the schedule. Only FEE-CUST-Q3 is above. An invoice with no schedule rate stays in with no variance.

## Field conventions the recipes and signals rely on (mine, for the loader builders)
- Fee invoice: `documents.document_type = 'invoice'` with `extracted_fields` `invoice_no`, `vendor`, `fee_base`, `fee_rate` (fraction), `amount_due`. Fee schedule: a document of type `fee_schedule` with `service_fee_rate` (value_text the vendor, value_numeric the fraction) and `service_fee_periods` (value_text the vendor, 4 for quarterly). A21 names only fund-term fields, so these two are new names.
- Allowance: `family_members` one row per member per schedule month (allowance_from and allowance_to are the month, frequency `monthly`, received_at the schedule's due date); paid is `cash_movements` of type `allowance` (outflow, so `abs(amount)`).
- Signals on figures expect **one `figure_changed` event per row of the figure, the row passed as `doc`** (the engine's `by` picks one row and its conditions cannot aggregate).

## Needs (code, model or decisions I could not make inside my files)
1. **Remove the stub `allowance_due` from `recipes/family.yaml`.** The loader keeps the first recipe id by file name and `family.yaml` sorts before `office.yaml`, so the stub shadows the built recipe (`v3_recipes.recipes()` does not list it today). I put the recipe in `office.yaml` because that is the only recipe file I may edit.
2. **`legal_entities` added to `may_read` of `allowance_due`.** The stub allowed `family_members, cash_movements, portfolios`; the row needs the paying entity's name to match `cash_by_entity` in the signals. Revert if refused (the signals would then key on the portfolio).
3. **A member link on `cash_movements`** (a counterparty or member id). Today a payment is matched to a schedule line by paying portfolio, month and amount; equal amounts pair one to one, and a payment made in a later month than its line does not match. Needed for exactness; a new column is the model steward's decision.
4. **Loaders** (no code of mine): allowance schedule xlsx into `family_members`; Trust bank statement `allowance` lines into `cash_movements` (type allowance, with the movement's portfolio); vendor contract PDFs into `vendor_contracts` (renewal date, annual cost, notice days from "60 days' notice", auto_renews from "renews"); fee invoice and fee schedule PDFs into `documents` + `extracted_fields` with the field names above. The tests use small readers inside the test file.
5. **As-at date.** The recipes take it from the data (latest `recorded_at` of vendor contracts, latest `received_at` of family members), like `missing_statements`. In a live office whose contract rows were recorded long ago, "within 90 days" is counted from that day. A platform-provided as-of date would fix this; I did not add one.
6. **Answer key and the October statement.** The key for card 15 counts the October allowances as due and unpaid, which holds for the inputs it lists (September statement). The October month-to-date statement (`HB_TRUST_USD_2026-10_mtd.xlsx`) already shows all four paid on 1 October, so a build that also loads it will show October owed as 0 (and only Ethan's September unpaid). The persona build lists the key's inputs only.
7. **Status vocabulary.** `decision_open` is 1 until a contract's `status` is `Renewal approved`; the CFO approval action of `uc-030-vendors-approved` must set it (and set the next renewal date).
8. **Narrative reader fields** for card 9: the document reader must emit `process_name`, `steps`, `steps_without_owner`, `steps_without_check` for kind `process_narrative`.
9. **Invoice base is not independently checked.** `invoice_variance` trusts the fee base printed on the invoice; checking it against the administrator's NAV or the custodian's liquid book is a further figure, not built.
10. **Hold names** `publish_sop`, `renew_contract` are new; `prepare_payment` already exists. Whatever performs those actions must refuse while `held()` is not empty.

## Wave 2: the verifier's rows (docs/v3/w1/verify-office.md)

Signals added: `uc-030-vendors-notice-passed`, `uc-030-vendors-renewal-passed`, `uc-050-feeinv-below-schedule`, `uc-050-feeinv-not-checked` (17 in all). Recipe columns added: `allowance_due.month_name`, `allowance_due.entity_owed`, `invoice_variance.check_status`. The tests now run each signal's own condition with `v3_signals.calc` on rows the recipes produced.

| # | card | status | what was done, or why not |
|---|---|---|---|
| 1 | 15 | fixed | The build lists the October month-to-date Trust USD statements. With them October shows paid on 1 Oct (owed 0, no "due" card), and only Ethan Chen's September 5,000 is owed. Test `test_allowance_due_with_the_october_statement_shows_october_paid`. The key's `total_owed` 28,000 holds only without that statement, so 28,000 left the build's expect (the other expects are still key values). **Needs:** the key owner to restate `total_owed` for the build's inputs (5,000). |
| 2 | 15 | fixed | New column `entity_owed`: everything the paying entity owes in the currency. `-approved` and `-cash-short` test `entity_owed + buffer` against cash, so approvals one by one cannot together break the buffer. Test with cash 270,000: each line alone fits, none is released, all are held. |
| 3 | 15 | not fixed | Needs the owner of `recipes/family.yaml` to delete the `allowance_due` stub (outside my files). Renaming my recipe would leave the card's figure id behind a stub. Test `test_allowance_due_is_served_by_the_loader` is `xfail(strict=True)`: it turns red the day the stub goes, so the exception in `_recipe` gets removed. |
| 4 | 15 | fixed | Money out is negative (A5): a payment is an allowance movement below zero. A movement above zero is a reversal and cancels the latest payment of the same portfolio, currency, month and amount; one that cancels nothing shows as the tie-out difference. Test: a +5,000 refund leaves Ethan owed 5,000 (tie-out differs by 5,000), a +8,000 reversal makes Lin's September owed again. |
| 5 | 15 | not fixed | Needs the cash builder or the engine: `cash_by_entity` (recipes/cash.yaml) is by entity and position date, and the engine's `by` returns nothing when several dates match (the signal is skipped, not wrong). A latest-date row per entity in `cash_by_entity`, or a "latest" pick in `_pick`, fixes it. Also: that recipe reads the administrator's cash, while the key's 213,895.52 is the bank's daily balance. |
| 6 | 15 | fixed | Payments match lines of the same currency, and `entity_owed` is partitioned by entity and currency. Test: an SGD line is owed in SGD (16,000) and the USD total stays 28,000. |
| 7 | 15 | not fixed | Needs the model steward: a member link on `cash_movements`. Without it, two members with the same amount in one month cannot be told apart; nothing in the data says which was paid. |
| 8 | 15 | fixed | Same as row 1: the October statements that give 213,895.52 are in the build's files. |
| 9 | 30 | fixed | The window is on the notice deadline (renewal date when no notice is stated) up to 90 days. Test: renewal in 100 days with 90 days' notice is listed and fires notice-near. |
| 10 | 30 | fixed | notice-near needs `days_to_notice_deadline >= 0`; a passed deadline goes to the new `-notice-passed` exception (call the vendor, holds `renew_contract`). `-renewing` fires only while the deadline is ahead. Test: renewal in 20 days with 60 days' notice fires only notice-passed. |
| 11 | 30 | fixed | A still-active contract whose renewal date passed stays in the list (negative days) and fires the new `-renewal-passed` (record the next renewal date). Test: renewal 1 Oct 2026 fires only that. |
| 12 | 30 | not fixed | Spec choice for Nitin: the card says "auto-renewal date within 30 days"; the signal counts to the notice deadline (safer for Orchard). One-line change if the card is meant literally. |
| 13 | 30 | fixed | The approval message no longer claims the date is set; it says the next date is then entered from the renewed contract, and `-renewal-passed` catches it if nobody does. Setting the date as part of the approval action needs the platform's action code. |
| 14 | 30 | fixed | Expects are compared as numbers with the key's numeric values, not as substrings of its text. |
| 15 | 50 | fixed | New `check_status` column and `-not-checked` exception (holds `prepare_payment` for the invoice) when no schedule is on file, the schedule gives two rates, or the fee base is in another currency. Test: every invoice fires exactly one card-50 signal. |
| 16 | 50 | fixed | New `-below-schedule` (ops_lead approves payment as billed; the message says the vendor may bill the difference later). |
| 17 | 50 | fixed | The rate comes from the fee schedule in force on the invoice date: the latest schedule document not replaced, by its date (received date when undated), leaving out one dated after the invoice. Two different rates in that schedule give no expected fee and `check_status` says so. Test: an older 2025 schedule at 0.08 percent is ignored (5,150 stays); a second rate in the schedule in force gives "more than one rate". |
| 18 | 50 | fixed | The fee base currency is compared with the amount due currency; different gives no variance and the not-checked exception. |
| 19 | 50 | fixed | Messages no longer claim a drafted query or a payment run: above-schedule says "Held until the vendor answers a query"; matches says "approved for payment. Nothing to do." |
| 20 | 50 | not fixed | The engine needs a role on every signal, so "nobody" is an info card to ops_lead with verb `see` (said in the signal's header). Needs an engine "no route" option if a card with no reader is wanted. |
| 21 | 9 | partly fixed | The test reads the four hand steps (1 to 4) from the narrative and checks them against the key; `-steps-drawn` reads `manual_steps` and says how many are flagged. Producing it live needs the narrative reader (row 22). |
| 22 | 9 | not fixed | Needs the platform's narrative reader to emit `process_name`, `steps`, `steps_without_owner`, `steps_without_check`, `manual_steps` for kind `process_narrative` (code outside my files). |
| 23 | 9 | fixed | `-steps-drawn` and `-published` claim only what the counts show: steps read, each with an owner, a system and a check, and the hand steps. |
| 24 | all | fixed | `_recipe` reads through the live loader (`v3_recipes.recipe`) except `allowance_due` (row 3, xfail test). Every signal's condition is now run on recipe rows in tests (cards 9, 15, 30, 50), and all 17 pass `check()`. |
| 25 | all | not fixed, by design | The live loader also reads every recipe file, so a broken file elsewhere breaks these figures in production too; the test failing then is the right signal. |
| 26 | all | fixed | Dashboard labels lost "Consume:"; allowance messages use `month_name` (September 2026). Subjects keep the ISO month as the once-only key. |

## Wave 4: the stub is gone (score50, 17 Oct 2026)

- **Card 15, stub removed.** `recipes/family.yaml` now has `recipes: []` and a note; `allowance_due` from `office.yaml` is the one the loader serves (cards [15], built, no status). Needs 1 is done. `test_allowance_due_is_served_by_the_loader` is now a normal test (the strict xfail would have turned red).
- **Card 15 before → after:** BLOCKED (stub shadows the recipe) → FAIL, 0/4 key values. The recipe now runs and ties out. The remaining difference is the key's scope, not the recipe: `due_october` expects Lin 8,000, Maya 6,000, Ethan 5,000, Wen 4,000 as unpaid for October. The fixture's `HB_TRUST_USD_2026-10_mtd.xlsx` (1 Oct, four `allowance` lines, all paid) is loaded in score50, and the key's own `input_files` leave it out. With all inputs loaded the recipe gives October owed 0 and September owed 5,000 for Ethan Chen (earlier = 1, the planted gap). Tie-out ok (5,000 = 5,000).
- **To pass card 15 one of these must be decided by the key owner, not by this domain:** (a) restate `due_october` and `total_owed` (5,000) for the full data, as Needs 6 says; or (b) scope the key's inputs to the September statement. I did not change the key or the scorer.
- **Not touched (outside my files):** card 9 remains BLOCKED (narrative reader, Needs 22). Cards 30 and 50 still PASS.
- **Test:** `tests/v1/test_w1_office.py` 40 passed, 0 failed.
