# Wave 1b, domain office, cards 51 to 100: build notes

Cards of "Run the office" and "Family and people" with no priority (use cases 51 to 100): **20**. **Built: 9. Not built: 11.** Synthetic data only.

Files: `packs/family_office/1/recipes/office.yaml` (8 recipes added), `packs/family_office/1/signals/uc-0{52,81,82,91,92,93,95,97,98}-*.yaml` (14 signals),
`packs/family_office/1/builds/office-51.yaml` (9 builds), `tests/v1/test_w1b_office.py`, this note.

Every recipe runs on the office as the real pack readers load it (`v3_pack_readers`, the `office` fixture of `test_w2_loader.py`), and every number is compared with
`tests/v1/fixtures/office6m/answer_keys.yaml`, read from the file. No recipe reads a business rule. The windows in days (60, 90, 90, 365) are the ones the card's own
figure states in `use_cases_100.yaml`, as card 30's 90 days were (`build-office.md`); the as-at date is the latest day a file of the kind was received.

## Built

| Card | Recipe (reads) | Proved against the key | Signals (severity, route, hold) | Build (role) |
|---|---|---|---|---|
| 52 insurance | `renewals_due` (vendor_contracts of kind insurance, renewal notices) | all 4 policies: renewal, days left, sum insured, premium, notice received; due in 60 days POL-LIAB-03 (19) and POL-CYB-04 (49) | `-due` (needs, hr_admin), `-no-notice` (problem, hr_admin, fires on POL-CYB-04; no hold, the card only watches) | hr_admin |
| 81 payroll | `payroll_total` (staff_payroll, cash_movements) | draft net 100,224, employer 21,297.60, total 121,521.60; September 93,360 / 113,199, paid per bank 93,360; +7.35 percent; flags Grace Ong gross +20, Jun Tan not on the previous run; release 0 | `-flag` (problem, cfo, **holds `prepare_payment` for the pay file**) | hr_admin |
| 82 covergap | `cover_gap` (real_assets, vendor_contracts, market_observations) | 6 assets, appraised, insured, gap and status each; total -9,647,014.92; SGD at the 13 Oct fixing 1.3400 read from the plane | `-no-policy` (problem, hr_admin), `-under-insured` (needs, hr_admin); no hold | hr_admin |
| 91 jml | `access_review` (system_access_grants, the joiner/leaver mail fields) | no approver: Sam Lee OMS, Wei Tan Harbour Bank portal; leaver J. Ng: OMS, Shared drive, Harbor; joiner Wei Tan not requested: Harbour Bank portal | `-no-approver`, `-leaver` (problem, head_of_data), `-not-requested` (needs); no hold | hr_admin |
| 92 accessrev | `access_review` (same) | 38 grants; unused over 90 days: Anita Rao 168, Sofia Reyes 146, Priya Nair 132 | `-unused` (needs, head_of_data) | hr_admin |
| 93 onbmgr | `onboarding_items` (checklist document fields) | 5 items, 3 complete, missing the bank call-back and the statement schedule, not ready | `-missing` (problem, ops_lead, **holds `prepare_payment` for the manager's first call**) | ops_lead |
| 95 sopreview | `sop_age` (SOP document fields) | all 8 SOPs: owner, last review, age; due: Open or change a bank account 681, Vendor payment run 480, Payroll release 378 | `-due` (needs, hr_admin) | hr_admin |
| 97 kycrefresh | `kyc_expiry` (kyc_records, legal_entities) | 12 documents; expiring 32, 50, 84 days; expired Daniel Foo -31 (Entity B) | `-expired` (problem), `-expiring` (needs), risk_officer | risk_officer |
| 98 wordlist | `terms_proposed` (proposed_term fields, the office word list document) | 5 proposals, 4 distinct, 2 on the list (capital account, dry powder as an alias), to add side letter and stub period; list of 20 | `-to-add` (needs, head_of_data) | head_of_data |

Notes: "not in the staff register" (card 81) is a person not on the previous run, as the payroll draft reader flags it. The previous month's bank payment is matched by
pay date, currency and the run's exact net, as allowances are matched (card 15).


## Not built

| Card | Reason (proved in the test) | What unblocks it |
|---|---|---|
| 83 taxcal | no reader for `tax_calendar`, `tax_notices`; no `tax_obligations` table | readers; then recipe `tax_due` |
| 84 taxest | no reader for `tax_calendar`; the 17, 12 and 15 percent rates are signed nowhere; needs card 83 | reader, signed tax-rate rules, card 83 |
| 85 grants | no reader for `grant_ledger`; the 300,000 grant budget is only a proposed rule | reader and a signed budget |
| 86 grantappr | no reader for `grant_ledger`, `grant_requests`; 24 months of charity registration is in no rule | readers and a signed rule |
| 87 trustdist | no reader for `trust_deed`; deed shares and the 70 percent payout are not signed rules | reader and signed deed rules |
| 88 estateliq | no reader for `trust_deed`, `estate_planning`; exemption 5,000,000 and rate 15 percent are not signed | readers and signed rules |
| 89 expapp | every file is read, but the four approver limits (`approver_limit_*`) are **proposed**, not signed (A20) | the limits signed through approvals; then a recipe over `office_expenses` against the signed limits |
| 90 offcost | every file is read, but the 13 budget lines (`office_budget_*`) are **proposed**, not signed | the budget signed; then `office_cost` over `office_expenses` against half the annual budget |
| 94 onbbank | every file is read, but `signing_policy` (two signatories, one the Head of Finance) is **proposed** | the policy signed |
| 96 automation | the key's 45 minutes of rework per failure is in its method only, in no file and no rule; the failure counts draw on four other sources with no signed definition | a signed scoring rule (rework minutes, which failures count) |
| 100 famaccess | every file is read, but the 12 `family_access_*` levels are **proposed** | the family access policy signed; the grants are already in `access_group_scopes` |

The tests of the unbuilt cards pass while the reason holds and fail the day it changes (a reader appears, or a rule is signed): that is the signal to build the card.

## Test
`python -m pytest tests/v1/test_w1b_office.py -q -p no:cacheprovider --basetemp=D:/Temp/pyt-w1b-office`: **28 passed, 0 failed** (about 25 seconds).
