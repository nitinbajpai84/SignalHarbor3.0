# Wave 1b, domain office, cards 51 to 100: build notes

Cards of "Run the office" and "Family and people" with no priority (use cases 51 to 100): **20**. **Built: 18. Not built: 2.** Synthetic data only.

Files: `packs/family_office/1/recipes/office.yaml` (17 recipes added), `packs/family_office/1/signals/uc-0{52,81,82,83,86,87,89,90,91,92,93,94,95,97,98}-*.yaml` and
`uc-100-*.yaml` (22 signals), `packs/family_office/1/builds/office-51.yaml` (18 builds), `tests/v1/test_w1b_office.py`, this note. Scored by `python tools/score50.py --all`.

Every recipe runs on the office as the real pack readers load it (`v3_pack_readers`, the `office` fixture of `test_w2_loader.py`), and every number is compared with
`tests/v1/fixtures/office6m/answer_keys.yaml`, read from the file. A limit, budget, level or policy is a **signed** office rule read by its code (A48, A49, A54), never a number
in the SQL: with no signed rule the figure that needs it is empty, never zero. The windows in days (60, 90, 90, 365, 30) are the ones the card's own figure states in
`use_cases_100.yaml`; the as-at date is the latest day a file was received. USD is the day's fixing (or the latest before it), as `cash_runway` does.

## Built, first round (no rule)

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

## Built, second round (family and controls readers, signed rules)

| Card | Recipe (reads; signed rule) | Proved against the key | Signals (severity, route, hold) | Build (role) |
|---|---|---|---|---|
| 83 taxcal | `tax_due` (tax_obligations) | due in 60 days TX-01, TX-02 (Holdings, 30 Nov, 48 days, Summit Tax Advisory); Holdings 2; overdue TX-04 Entity B, 13 days, not filed (M33) | `-overdue` (problem), `-due` (needs), fund_accountant; no hold | fund_accountant |
| 85 grants | `grants_used` (grants, the bank's grant debits; `office_budget_grants`) | budget 300,000, paid 175,000, pledged 90,000, used 265,000 (88.3 percent), 35,000 left; the three paid grants match the bank | none: no planted exception | principal |
| 86 grantappr | `grant_check` (grants, administrator cash, open calls; `office_budget_grants`, `grant_min_charity_months`, `cash_buffer`) | REQ-2026-06 50,000 against 35,000 left; charity 19 months against 24; Holdings USD 1,230,000 less the 1,250,000 call less the request = -70,000 under the 250,000 buffer; every check false, do not pay (M34) | `-fails` (problem, principal, **holds `prepare_payment` for the grant**) | principal |
| 87 trustdist | `trust_distribution_room` (deed fields, the trust's bank lines, the allowance schedule) | trust year from 1 Apr; income 504,980.42, costs 46,001.31, distributable 458,979.11, 70 percent cap 321,285.38; room, paid and left per beneficiary; Wen Chen 28,000 paid against 25,702.83 (M47) | `-over` (problem, fund_accountant, **holds `prepare_payment` for Wen Chen's allowance**) | fund_accountant |
| 88 estateliq | `estate_cash_need` (fund statements, liquid book, administrator cash, appraisals, the loan; `estate_tax_exemption`, `estate_tax_rate`) | investments 109,960,000 (30 Sep), cash 6,156,041.41, real assets 17,990,298.50, loan 2,800,000: estate 131,306,339.91; tax 18,945,950.99; liquid after debt 55,879,741.41, cover 2.95, can meet | none: the family can meet the tax | principal |
| 89 expapp | `approval_exceptions` (office_expenses; `approver_limit_<person>`) | 151 payments; over the limit BAL-2026-051 38,000 and LL-2026-0708 16,662.93, both by Priya Nair (10,000) (M35); approvals Daniel Foo 22, Grace Ong 10, Priya Nair 119; the four limits are the signed rules | `-over-limit` (problem, cfo); no hold, the payments are made | hr_admin |
| 90 offcost | `office_cost` (office_expenses; `office_budget_<category>`) | 13 categories, actual against the annual budget x 6/12; total 1,463,862.76 against 1,455,850; over: Professional fees (+35,752.48) and Grants (+25,000); none uncategorised | `-over` (needs, cfo) | cfo |
| 94 onbbank | `account_setup` (pending bank account, signatory fields, users; `signing_policy`) | signatories Raj Patel, Grace Ong; the Head of Finance Daniel Foo is missing; does not meet the policy; not approved (M38) | `-signatory` (problem, cfo, **holds `open_bank_account`**) | cfo |
| 100 famaccess | `member_access` (family groups and scopes, the request mail fields; `family_access_<member>_<entity>`) | allowed and granted per member and entity; Wen Chen given full Entity B against none (M43); Maya's request for the Holdings summary is outside the policy | `-over-granted` (problem, hr_admin, **holds `send_family_report`**) | hr_admin |

Notes: card 85 reads the signed Grants line of the 2026 office budget, not the `grant_budget` the ledger reader writes as proposed. Card 87's trust is the legal entity whose name
the deed's title carries; allowances are matched to the schedule as `allowance_due` matches them. Card 94: the key's six checklist steps are in no file, so only the two the data
decides (signatories meet the policy, Head of Finance approval) are proved; the other four are not compared. Card 100: summary is stored as `preview` in the group scopes (A38).

Signed for this round (A54, logged in `docs/v3/ASSUMPTIONS.md`, written by `tools/gen_office6m/more.py` into `reference/office_rules.csv`): `grant_min_charity_months` 24
(in no file; the key and M34 state it) and v2 of `estate_tax_exemption` 5,000,000 and `estate_tax_rate` 0.15 (the memo's values, proposed v1 kept beside them).

## Not built

| Card | Reason (proved in the test) | What unblocks it |
|---|---|---|
| 84 taxest | the lots sold since 1 Apr are in no file (the lot register holds only the lots still open on 30 Sep), so realised gains cannot be matched first-in first-out; the 2026 rates `tax_rate_<entity>` are proposed, not signed | a lot register with the closed lots (or the trade file's cost), and the rates signed; then a recipe over income, realised gains and the withholding credit |
| 96 automation | the 45 minutes of rework are signed (A51), but which failures count against which SOP (late close steps, missing statements, unapproved or changed-account calls, invoice problems) is in the key's method only | a signed rule naming the failure sources of each SOP; then `automation_score` over the SOP fields |

The tests of the unbuilt cards pass while the reason holds and fail the day it changes: that is the signal to build the card.

## Score
`python tools/score50.py --all`: 96 PASS, 1 FAIL (card 75, not of this domain), 0 SIGNAL, 3 BLOCKED (72, 84, 96). `python tools/score50.py`: 50 of 50.

## Test
`python -m pytest tests/v1/test_w1b_office.py -q -p no:cacheprovider --basetemp=D:/Temp/pyt-w1b-office`: **28 passed, 0 failed** (about 30 seconds).
