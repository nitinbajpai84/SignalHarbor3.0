# Wave 1, domain office: build notes

Cards of the domain "Run the office" and "Family and people" with priority 1 to 50: **9** (uc9-sop), **15** (uc-015-allowances), **30** (uc-030-vendors), **50** (uc-050-feeinv). Synthetic data only.

Files: `packs/family_office/1/recipes/office.yaml`, `signals/uc9-sop-*`, `uc-015-allowances-*`, `uc-030-vendors-*`, `uc-050-feeinv-*`, `builds/office.yaml`, `tests/v1/test_w1_office.py`.
Test run: `pytest tests/v1/test_w1_office.py` gives **27 passed, 0 failed**. All 13 signals also pass the engine's own `check()` (branch `sh3-signals`, with the roles of `role_builds.yaml`).

## Card 9, uc9-sop: Process map and SOP for the month-end report
- **Recipes:** none. No table holds a process; the figure (steps with owner, system and check) is read from the narrative document.
- **Signals:** `uc9-sop-steps-drawn` (hr_admin, approve), `uc9-sop-published` (hr_admin, approve, after the first), `uc9-sop-step-gap` (exception, hr_admin, call_back, holds `publish_sop`).
- **Build:** keeps `uc9-sop` in `role_builds.yaml` (not duplicated).
- **Test:** pass. The six steps of the narrative are parsed: 6 steps, owners equal the key (Mei Chen x3, Raj Patel x2, Daniel Foo), every step has an owner, a system and a control.

## Card 15, uc-015-allowances: Family allowances and distributions due
- **Recipe:** `allowance_due` (in `office.yaml`, ready), by member and month: scheduled, paid, owed, earlier. Tie-out: owed equals scheduled less every allowance paid in the same months.
- **Signals:** `-due` (principal, approve), `-approved` (cfo, release, only when cash covers it after the buffer), `-cash-short` (exception, cfo, holds `prepare_payment` for the entity), `-unpaid-earlier` (exception for the planted gap, principal, holds `prepare_payment` for the member).
- **Build:** `uc-015-allowances` under `principal`. Expect: 28,000; 8,000; 6,000; 5,000; 4,000; 213,895.52.
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
