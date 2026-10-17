# Wave 1b, domain office, cards 51 to 100: build notes

Cards of "Run the office" and "Family and people" with no priority (use cases 51 to 100): **20**. **Built: 0. Not built: 20.** Synthetic data only.

Files touched: `packs/family_office/1/builds/office-51.yaml` (empty `roles`), `tests/v1/test_w1b_office.py`, this note. `recipes/office.yaml` and the signals are unchanged: a recipe or signal written now could not be proved on the real readers, and the rules forbid inventing a table or a rule.

## Why none is built
1. **No reader.** Every card reads at least one file kind that `sh_platform/v1/v3_pack_readers.py` does not read (the loader says "no reader for this kind"; the 36 kinds are `NEW_KINDS` in `tools/gen_office6m/more.py`). The warehouse holds none of their rows, so a recipe has nothing to run on and its key cannot be asserted from recipe output. Readers are code outside this builder's files.
2. **No table.** Many cards also need a table the model steward left for later (A23, `MODEL-ADDITIONS.md` class d). I did not invent them.
3. **No rule.** Several keys rest on a number that is in a document and in no signed rule (deed payout 70 percent and shares, transfer tax exemption and rate, tax rates, grant charity age of 24 months, SOP age of 365 days, access idle of 90 days, signing policy, approver limits). They need a reader or a signed `business_rules` row first (A20), not a number typed into a recipe.

`tests/v1/test_w1b_office.py` (21 passed) reads each card's input kinds from `answer_keys.yaml`, loads the office with the real loader and asserts at least one kind is still unread. When a card's files are all read it fails with "build the card": that is the signal to build it.

## Needs, by card
Key = `tests/v1/fixtures/office6m/answer_keys.yaml`. "Hold" = what the exception signal would hold once built.

| Card | Unread kinds | Also needs | What the recipe must give (from the key) | Exception signal and hold to write |
|---|---|---|---|---|
| 52 insurance | insurance_schedule (the 3 renewal notices are read but carry no sum insured, and none for POL-CYB-04) | table `insurance_policies` (or a kind column on `vendor_contracts`), recipe `renewals_due` | 2 in 60 days: POL-LIAB-03 19 days, POL-CYB-04 49 days; sums insured 10,000,000 and 1,000,000 | notice not received for POL-CYB-04, hr_admin, no hold. Data note: the liability notice shows premium SGD 9,800, the key USD 9,800 |
| 81 payroll | payroll_drafts (the six monthly registers are read) | table `staff_payroll` (personal pay, access decision first), recipe `payroll_total` | draft net 100,224; total cost 121,521.60; September 113,199; +7.35 percent; flags Grace Ong +20 percent, Jun Tan not on register | release held while a flag is open, cfo, holds `prepare_payment` for the pay file |
| 82 covergap | insurance_schedule, property_valuations | tables `insurance_policies`, `real_assets` (A23), recipes `renewals_due`, `real_asset_value`; USD at 1.3400 | total gap -9,647,014.92; under-insured Bayview, Fine art; no policy on 4 assets | no policy on an asset, hr_admin to principal, no hold |
| 83 taxcal | tax_calendar, tax_notices | table `tax_obligations`, recipe `tax_due` | TX-01 and TX-02 due 2026-11-30 (48 days); TX-04 overdue 13 days | overdue filing, cfo, no hold |
| 84 taxest | tax_calendar, tax_lots, tax_notices | recipe `tax_estimate`; rates 17, 12, 15 percent signed as rules; figures of cards 67, 68, 83 | total to set aside 159,164.11 (Holdings 29,054.88; Trust 114,858.65; Entity B 15,250.58) | none in the card |
| 85 grants | grant_ledger | table `grants`, recipe `grants_used`; budget 300,000 as a signed rule | paid 175,000; pledged 90,000; used 88.3 percent; remaining 35,000; paid agrees with the bank | used above a threshold, principal, no hold |
| 86 grantappr | grant_requests, grant_ledger | table `grants`; 24 months of registration as a rule; figure `liquidity_ladder` | request 50,000 against remaining 35,000; charity 19 of 24 months; cash after calls -70,000 | failed checks, principal, holds `prepare_payment` for the grant |
| 87 trustdist | trust_deed | table `succession_plan` (sensitive); deed shares and 70 percent payout as signed rules | Wen Chen over by 2,297.17; distributable 458,979.11; cap 321,285.38 | over-distribution, fund_accountant to principal, holds `prepare_payment` for Wen Chen |
| 88 estateliq | trust_deed, estate_planning, property_valuations | `real_assets`; exemption 5,000,000 and rate 15 percent as rules; recipe `estate_cash_need` | estate 131,306,339.91; tax 18,945,950.99; liquid after debt 55,879,741.41; cover 2.95 | none (cover above 1) |
| 89 expapp | expense_ledger (the approvals log is read, but only payments over 500,000) | recipe over the ledger; approver limits (10,000; 50,000; 500,000; 5,000,000) as signed rules | 151 payments; 2 over limit: BAL-2026-051 38,000 and LL-2026-0708 16,662.93, both approved by Priya Nair | over the approver's limit, hr_admin, holds `prepare_payment` for the payment |
| 90 offcost | expense_ledger, office_budget, payroll_drafts | table `office_expenses`, recipes `office_cost`, `payroll_total`, `renewals_vendors` | actual 1,463,862.76 against 1,455,850; over: Professional fees (+35,752.48), Grants (+25,000) | category over budget, cfo, no hold |
| 91 jml | access_register | `access_group_memberships` and `access_group_scopes` exist (they replace `access_grants`) but no reader fills them | 2 grants without approver (Sam Lee OMS, Wei Tan bank portal); leaver J. Ng holds OMS, Shared drive, Harbor | grant without approver, hr_admin to head_of_data, no hold |
| 92 accessrev | access_register | as 91; 90 idle days as a rule | 38 grants; 3 unused: Anita Rao 168 days, Sofia Reyes 146, Priya Nair 132 | idle grant, head_of_data, no hold |
| 93 onbmgr | onboarding | `kyc_records`; `expected_statements` rows for the new manager | 5 items, 3 complete; missing: bank details call-back, statement schedule | not ready, ops_lead, holds `prepare_payment` for the manager's first call |
| 94 onbbank | bank_forms | `kyc_records`; `bank_accounts` exists; signing policy (two or more, one the Head of Finance) as a rule | signatories Raj Patel, Grace Ong; missing Daniel Foo; not approved | signing policy not met, cfo, holds the account opening |
| 95 sopreview | sops | figure `sop_age` over SOP documents; 365 days as a rule | 3 to review: Open or change a bank account 681 days, Vendor payment run 480, Payroll release 378 | SOP over a year, hr_admin, no hold |
| 96 automation | sops, exception_log | recipe `automation_score` (step minutes, runs, failures); 45 minutes of rework per failure as a rule | automate next: Bank statement chase, score 2,040 | none in the card |
| 97 kycrefresh | kyc_register | `kyc_records` (personal identity data, access decision first) | 3 expiring in 90 days (32, 50, 84 days); 1 expired (Daniel Foo, -31 days) | expired or within 90 days, risk_officer, no hold |
| 98 wordlist | glossary | a glossary reader; the word list is the pack's `glossary.yaml` | proposed 4 distinct; already in the list 2; to add: side letter, stub period | none |
| 100 famaccess | family_access | `family_members` exists (allowances only); `access_group_*` filled; access levels none < summary < full as rules | over-grant: Wen Chen has Entity B full, allowed none; Maya Chen's request for Holdings denied | over-grant, principal, holds the report share |

## What would unlock most cards
1. Readers for `expense_ledger`, `office_budget`, `payroll_drafts`, `sops`, `access_register`, `kyc_register`, `family_access`, `grant_ledger`, `insurance_schedule`, `tax_calendar`. These ten kinds carry 17 of the 20 cards.
2. Signed rules (A20) for the limits listed above.
3. The model steward's decision on the class-d tables (A23): insurance_policies, grants, tax_obligations, staff_payroll, succession_plan, kyc_records, office_expenses, real_assets.
4. Cards 84, 88 and 90 reuse figures of other cards (tax_due, real_asset_value, payroll_total) and wait for them.

## Test
`pytest tests/v1/test_w1b_office.py`: **21 passed, 0 failed** (one count of the 20 cards, 20 "card waits for a reader" checks).
