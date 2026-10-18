# Score of the 100 use cases

Written by `python tools/score50.py` on 2026-10-18 08:21. Office: tests/v1/fixtures/office6m as of 2026-10-13, loaded once with the real loader (v3_office6m_loaders.load_plane); 108 built recipes run once; keys from answer_keys.yaml; signals from packs/family_office/1/signals. Deterministic: no model is called. Load 13 s, whole run 27 s.

PASS: every key value matches and the signals behave. FAIL: a number is wrong, or a recipe the card needs does not run or tie out. SIGNAL: the numbers are right but the planted mess is not caught, or an exception signal fires on a clean row. BLOCKED: needs something that does not exist yet.

## Totals

| PASS | FAIL | SIGNAL | BLOCKED | Cards |
|---|---|---|---|---|
| 99 | 1 | 0 | 0 | 100 |

Key values compared: 1847, matching: 1843.

## By domain

| Domain | PASS | FAIL | SIGNAL | BLOCKED | Cards |
|---|---|---|---|---|---|
| Cash and treasury | 15 | 0 | 0 | 0 | 15 |
| Hold and maintain | 13 | 0 | 0 | 0 | 13 |
| Invest | 15 | 0 | 0 | 0 | 15 |
| Operate and control | 18 | 0 | 0 | 0 | 18 |
| Report and govern | 15 | 0 | 0 | 0 | 15 |
| Run the office | 13 | 0 | 0 | 0 | 13 |
| Family and people | 10 | 1 | 0 | 0 | 11 |

## By person (card owner)

| Person | PASS | FAIL | SIGNAL | BLOCKED | Cards |
|---|---|---|---|---|---|
| Anita Rao | 8 | 0 | 0 | 0 | 8 |
| Grace Ong | 11 | 0 | 0 | 0 | 11 |
| Helen Foo | 12 | 0 | 0 | 0 | 12 |
| Mei Chen | 11 | 0 | 0 | 0 | 11 |
| Priya Nair | 10 | 0 | 0 | 0 | 10 |
| Raj Patel | 10 | 0 | 0 | 0 | 10 |
| Sam Lee | 8 | 0 | 0 | 0 | 8 |
| Sofia Reyes | 10 | 0 | 0 | 0 | 10 |
| Tom Hale | 9 | 0 | 0 | 0 | 9 |
| Daniel Foo | 10 | 1 | 0 | 0 | 11 |

## Failures by root cause, worst first

A card can sit under more than one cause. The cause is what the expected-against-got numbers of the card detail point to.

1. **Bank statement TCB-B-USD 2026-07 never arrived (M02b), so Entity B's income is 44.71 short; the key of card 84 still counts that interest (A58)**. FAIL, 1 card(s): 84. Recipes: tax_estimate.

## Every card

| # | Card | Domain | Person | Result | Keys ok | Reason |
|---|---|---|---|---|---|---|
| 1 | uc-001-noticelog: Log an incoming capital call notice | Operate and control | Sam Lee | **PASS** | 9/9 | all key values match; signals behave |
| 2 | uc-002-callrecord: Record a capital call against the commitment | Cash and treasury | Helen Foo | **PASS** | 8/8 | all key values match; signals behave |
| 3 | uc6-liquidity: Can each entity meet its capital calls? | Cash and treasury | Daniel Foo | **PASS** | 12/12 | all key values match; signals behave |
| 4 | uc-004-callcheck: Check a call against cash and approve the payment | Cash and treasury | Daniel Foo | **PASS** | 10/10 | all key values match; signals behave |
| 5 | uc-005-benefcheck: Hold a payment when the bank details changed | Cash and treasury | Grace Ong | **PASS** | 7/7 | all key values match; signals behave |
| 6 | uc-006-fxneed: FX needed to pay a call in another currency | Cash and treasury | Grace Ong | **PASS** | 53/53 | all key values match; signals behave |
| 7 | uc-007-pacing: Commitment pacing: where we stand after the call | Invest | Raj Patel | **PASS** | 27/27 | all key values match; signals behave |
| 8 | uc-008-payrun: Weekly payment run with two approvals | Cash and treasury | Grace Ong | **PASS** | 17/17 | all key values match; signals behave |
| 9 | uc9-sop: Process map and SOP for the month-end report | Run the office | Priya Nair | **PASS** | 3/3 | all key values match; signals behave |
| 10 | uc-010-bankexp: Cash held at each bank against the bank limit | Cash and treasury | Tom Hale | **PASS** | 5/5 | all key values match; signals behave |
| 11 | uc10-pipeline: A monthly pipeline and insight from the administrator and trading files | Operate and control | Anita Rao | **PASS** | 6/6 | all key values match; signals behave |
| 12 | uc5-limits: Allocation and limit monitoring | Report and govern | Tom Hale | **PASS** | 11/11 | all key values match; signals behave |
| 13 | uc-013-secgaps: Securities with no asset class or identifier | Hold and maintain | Anita Rao | **PASS** | 3/3 | all key values match; signals behave |
| 14 | morning-networth-note: A morning note on what we are worth | Report and govern | Mei Chen | **PASS** | 7/7 | all key values match; signals behave |
| 15 | uc-015-allowances: Family member allowances and distributions due | Family and people | Mei Chen | **PASS** | 4/4 | all key values match; signals behave |
| 16 | uc-016-schemadrift: A source file arrives with a new or renamed column | Operate and control | Anita Rao | **PASS** | 3/3 | all key values match; signals behave |
| 17 | uc-017-liab: What we owe: loans and facilities, and net worth after debt | Hold and maintain | Mei Chen | **PASS** | 7/7 | all key values match; signals behave |
| 18 | uc-018-fundplan: Which entity pays this call and from where | Cash and treasury | Daniel Foo | **PASS** | 7/7 | all key values match; signals behave |
| 19 | uc3-statements-inbox: Manager statements: expected against received, and late | Operate and control | Helen Foo | **PASS** | 18/18 | all key values match; signals behave |
| 20 | uc1-why-nav-moved: Why did the NAV move since the issued report? | Report and govern | Raj Patel | **PASS** | 5/5 | all key values match; signals behave |
| 21 | uc-021-stale: Valuations that are stale | Hold and maintain | Tom Hale | **PASS** | 31/31 | all key values match; signals behave |
| 22 | uc-022-amendlog: Amended statements and what they replace | Operate and control | Helen Foo | **PASS** | 20/20 | all key values match; signals behave |
| 23 | uc-023-tieout: Does the issued report tie to the administrator | Report and govern | Helen Foo | **PASS** | 10/10 | all key values match; signals behave |
| 24 | uc-024-audit: Auditor sample: trace a figure to its file | Report and govern | Anita Rao | **PASS** | 6/6 | all key values match; signals behave |
| 25 | uc7-manager-diligence: What changed at Kestrel Ridge since we last met? | Invest | Sofia Reyes | **PASS** | 22/22 | all key values match; signals behave |
| 26 | uc-026-stmtadmin: Manager statement against the administrator value | Operate and control | Helen Foo | **PASS** | 30/30 | all key values match; signals behave |
| 27 | uc2-recon-break-desk: Daily cash reconciliation and break desk | Operate and control | Grace Ong | **PASS** | 10/10 | all key values match; signals behave |
| 28 | uc-028-interco: Move cash between entities | Cash and treasury | Daniel Foo | **PASS** | 7/7 | all key values match; signals behave |
| 29 | uc-029-closeck: Month-end close checklist | Operate and control | Grace Ong | **PASS** | 4/4 | all key values match; signals behave |
| 30 | uc-030-vendors: Vendors and contract renewals | Run the office | Priya Nair | **PASS** | 9/9 | all key values match; signals behave |
| 31 | uc-031-alloc: Where is the money: allocation by asset class and entity | Hold and maintain | Helen Foo | **PASS** | 4/4 | all key values match; signals behave |
| 32 | uc-032-driftrep: Allocation drift against the policy targets | Report and govern | Tom Hale | **PASS** | 2/2 | all key values match; signals behave |
| 33 | uc-033-breachesc: A real breach goes to the committee | Report and govern | Tom Hale | **PASS** | 4/4 | all key values match; signals behave |
| 34 | uc-034-prospect: Screen a new fund against the mandate | Invest | Sofia Reyes | **PASS** | 6/6 | all key values match; signals behave |
| 35 | uc-035-ddq: Compare manager questionnaires | Invest | Sofia Reyes | **PASS** | 11/11 | all key values match; signals behave |
| 36 | uc6-uncalled: How much of our commitments is still uncalled? | Cash and treasury | Daniel Foo | **PASS** | 10/10 | all key values match; signals behave |
| 37 | uc-037-distrack: Distributions expected against received | Cash and treasury | Sam Lee | **PASS** | 21/21 | all key values match; signals behave |
| 38 | uc-038-navroll: Private fund value roll-forward | Hold and maintain | Helen Foo | **PASS** | 1/1 | all key values match; signals behave |
| 39 | uc-039-irr: Return of each private fund since we invested | Invest | Sofia Reyes | **PASS** | 40/40 | all key values match; signals behave |
| 40 | uc-040-icmemo: Investment committee memo for a new commitment | Invest | Sofia Reyes | **PASS** | 8/8 | all key values match; signals behave |
| 41 | uc-041-commitappr: Approve a new commitment within policy | Invest | Raj Patel | **PASS** | 4/4 | all key values match; signals behave |
| 42 | uc4-vs-benchmark: How did the portfolio do against its benchmark? | Report and govern | Raj Patel | **PASS** | 5/5 | all key values match; signals behave |
| 43 | uc-043-liquidpnl: Liquid book gain or loss so far this month | Hold and maintain | Raj Patel | **PASS** | 5/5 | all key values match; signals behave |
| 44 | uc-044-twr: Return for the year against the benchmark | Report and govern | Raj Patel | **PASS** | 5/5 | all key values match; signals behave |
| 45 | uc-045-reportpack: Monthly investment report: assemble and sign | Report and govern | Raj Patel | **PASS** | 4/4 | all key values match; signals behave |
| 46 | uc-046-attrib: Where did the return come from | Report and govern | Sofia Reyes | **PASS** | 14/14 | all key values match; signals behave |
| 47 | uc-047-icpack: Investment committee pack | Report and govern | Raj Patel | **PASS** | 7/7 | all key values match; signals behave |
| 48 | uc-048-policyupd: Update the allocation policy and its limits | Report and govern | Tom Hale | **PASS** | 10/10 | all key values match; signals behave |
| 49 | uc-049-feedrag: Fees paid to each manager | Invest | Helen Foo | **PASS** | 16/16 | all key values match; signals behave |
| 50 | uc-050-feeinv: Administrator and custodian invoices against the fee schedule | Run the office | Grace Ong | **PASS** | 17/17 | all key values match; signals behave |
| 51 | uc8-trades-vs-admin: Trades and FX forwards against the administrator and the confirmations | Operate and control | Sam Lee | **PASS** | 8/8 | all key values match; signals behave |
| 52 | uc-052-insurance: Insurance policies and renewals | Family and people | Priya Nair | **PASS** | 35/35 | all key values match; signals behave |
| 53 | uc-053-watchlist: Manager watchlist: late, restated or changed | Invest | Sofia Reyes | **PASS** | 32/32 | all key values match; signals behave |
| 54 | uc-054-ladder: 30, 60, 90 day liquidity ladder | Cash and treasury | Daniel Foo | **PASS** | 45/45 | all key values match; signals behave |
| 55 | uc-055-corpact: Corporate actions and income calendar | Hold and maintain | Sam Lee | **PASS** | 62/62 | all key values match; signals behave |
| 56 | uc-056-custrecon: Custodian positions against administrator positions | Operate and control | Grace Ong | **PASS** | 11/11 | all key values match; signals behave |
| 57 | uc-057-pricecheck: Prices against a second source | Operate and control | Grace Ong | **PASS** | 8/8 | all key values match; signals behave |
| 58 | uc-058-settle: Trades not settled on time | Operate and control | Sam Lee | **PASS** | 20/20 | all key values match; signals behave |
| 59 | uc-059-breakage: Open breaks by age | Operate and control | Grace Ong | **PASS** | 33/33 | all key values match; signals behave |
| 60 | uc-060-docinbox: Documents the office could not recognise | Operate and control | Sam Lee | **PASS** | 6/6 | all key values match; signals behave |
| 61 | uc-061-dqscore: Data quality score for each source | Operate and control | Anita Rao | **PASS** | 73/73 | all key values match; signals behave |
| 62 | uc-062-fxlife: FX forwards: upcoming value dates and mark to market | Operate and control | Sam Lee | **PASS** | 21/21 | all key values match; signals behave |
| 63 | uc-063-cashcode: Unexplained bank lines | Operate and control | Sam Lee | **PASS** | 8/8 | all key values match; signals behave |
| 64 | uc-064-fxexp: Currency exposure of the family | Hold and maintain | Tom Hale | **PASS** | 8/8 | all key values match; signals behave |
| 65 | uc-065-realassets: Real assets register | Hold and maintain | Mei Chen | **PASS** | 52/52 | all key values match; signals behave |
| 66 | uc-066-propreval: Appraisal due on a real asset | Hold and maintain | Mei Chen | **PASS** | 25/25 | all key values match; signals behave |
| 67 | uc-067-unrl: Unrealised gain by lot | Hold and maintain | Helen Foo | **PASS** | 256/256 | all key values match; signals behave |
| 68 | uc-068-incomef: Dividend and coupon income forecast | Hold and maintain | Helen Foo | **PASS** | 6/6 | all key values match; signals behave |
| 69 | uc-069-lookthru: What the private funds really own | Hold and maintain | Sofia Reyes | **PASS** | 22/22 | all key values match; signals behave |
| 70 | uc-070-idle: Idle cash above what we need | Cash and treasury | Daniel Foo | **PASS** | 17/17 | all key values match; signals behave |
| 71 | uc-071-expdist: Distributions we expect in the next year | Invest | Sofia Reyes | **PASS** | 3/3 | all key values match; signals behave |
| 72 | uc-072-cashfc: 12 month cash forecast | Cash and treasury | Daniel Foo | **PASS** | 80/80 | all key values match; signals behave |
| 73 | uc-073-runway: How many months the family can spend | Cash and treasury | Mei Chen | **PASS** | 6/6 | all key values match; signals behave |
| 74 | uc-074-boardpack: Family board pack | Report and govern | Mei Chen | **PASS** | 9/9 | all key values match; signals behave |
| 75 | uc-075-yearwalk: What happened to our worth this year | Report and govern | Mei Chen | **PASS** | 11/11 | all key values match; signals behave |
| 76 | uc-076-scorecard: Manager scorecard | Invest | Raj Patel | **PASS** | 34/34 | all key values match; signals behave |
| 77 | uc-077-deals: Pipeline of deals under review | Invest | Sofia Reyes | **PASS** | 23/23 | all key values match; signals behave |
| 78 | uc-078-redemption: Redeem from a hedge fund within notice and lock-up | Invest | Grace Ong | **PASS** | 14/14 | all key values match; signals behave |
| 79 | uc-079-rebalance: Rebalancing proposal | Invest | Raj Patel | **PASS** | 18/18 | all key values match; signals behave |
| 80 | uc-080-vintage: Spread of private commitments by year | Invest | Tom Hale | **PASS** | 4/4 | all key values match; signals behave |
| 81 | uc-081-payroll: Household and office payroll | Family and people | Priya Nair | **PASS** | 9/9 | all key values match; signals behave |
| 82 | uc-082-covergap: Insurance cover against what we own | Family and people | Priya Nair | **PASS** | 27/27 | all key values match; signals behave |
| 83 | uc-083-taxcal: Tax calendar | Family and people | Helen Foo | **PASS** | 19/19 | all key values match; signals behave |
| 84 | uc-084-taxest: Estimated tax for the year | Family and people | Daniel Foo | **FAIL** | 18/22 | by_entity.Entity B.income: expected 89,709.31, got 89,664.6 (tax_estimate); by_entity.Entity B.tax_before_credits: expected 15,250.58, got 15,242.98 (tax_estimate); by_entity.Entity B.tax_to_set_aside: expected 15,250.58, got 15,242.98 (tax_estimate); total_to_set_aside: expected 159,164.11, got 159,156.51 (tax_estimate) |
| 85 | uc-085-grants: Philanthropy: budget used | Family and people | Mei Chen | **PASS** | 7/7 | all key values match; signals behave |
| 86 | uc-086-grantappr: Approve a grant payment | Family and people | Mei Chen | **PASS** | 12/12 | all key values match; signals behave |
| 87 | uc-087-trustdist: Trust distributions to beneficiaries | Family and people | Helen Foo | **PASS** | 27/27 | all key values match; signals behave |
| 88 | uc-088-estateliq: Cash for an estate or transfer tax | Family and people | Mei Chen | **PASS** | 11/11 | all key values match; signals behave |
| 89 | uc-089-expapp: Expense approval and sign-off rules | Run the office | Priya Nair | **PASS** | 10/10 | all key values match; signals behave |
| 90 | uc-090-offcost: What the office costs | Run the office | Daniel Foo | **PASS** | 56/56 | all key values match; signals behave |
| 91 | uc-091-jml: Joiner, mover, leaver access | Run the office | Priya Nair | **PASS** | 6/6 | all key values match; signals behave |
| 92 | uc-092-accessrev: Quarterly access review | Run the office | Priya Nair | **PASS** | 8/8 | all key values match; signals behave |
| 93 | uc-093-onbmgr: Onboard a new manager | Run the office | Grace Ong | **PASS** | 4/4 | all key values match; signals behave |
| 94 | uc-094-onbbank: Open or change a bank or custody account | Run the office | Daniel Foo | **PASS** | 5/5 | all key values match; signals behave |
| 95 | uc-095-sopreview: SOPs not reviewed in a year | Run the office | Priya Nair | **PASS** | 33/33 | all key values match; signals behave |
| 96 | uc-096-automation: Which processes to automate next | Run the office | Anita Rao | **PASS** | 49/49 | all key values match; signals behave |
| 97 | uc-097-kycrefresh: Know-your-client documents expiring | Run the office | Tom Hale | **PASS** | 13/13 | all key values match; signals behave |
| 98 | uc-098-wordlist: Keep the office words in step with the model | Run the office | Anita Rao | **PASS** | 6/6 | all key values match; signals behave |
| 99 | uc-099-newfeed: Bring in a new source file | Operate and control | Anita Rao | **PASS** | 5/5 | all key values match; signals behave |
| 100 | uc-100-famaccess: What each family member can see | Family and people | Priya Nair | **PASS** | 3/3 | all key values match; signals behave |

## Per card detail

### 1. uc-001-noticelog: PASS

Figures bound: call_notice_amount -> call_notice_fields; notices_open -> notices_open. Answered from: call_notice_fields, notices_open.

Signals fired: none.

Signals that cannot run on the loaded data: uc-001-noticelog-fields-disagree cannot run: no reader gives doc.amount_in_table.

### 2. uc-002-callrecord: PASS

Figures bound: called_to_date -> called_to_date; unfunded_after_call -> called_to_date; fee_part_check -> call_fee_check. Answered from: call_fee_check, called_to_date.

Signals fired: uc-002-callrecord-fee-off x1; uc-002-callrecord-recorded x1.

### 3. uc6-liquidity: PASS

Figures bound: cash_by_entity -> cash_by_entity; calls_due -> calls_due. Answered from: calls_due, cash_by_entity.

Signals fired: uc6-liquidity-call-vs-cash x1.

### 4. uc-004-callcheck: PASS

Figures bound: cash_after_calls -> cash_after_calls; sgd_to_convert -> fx_required; call_vs_commitment_check -> called_to_date. Answered from: called_to_date, cash_after_calls, fx_required.

Key values not compared (no column answers them yet): q1.needs_approval_over_500000.

Signals fired: uc-004-callcheck-approval x1.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-004-callcheck-approval fires on Cedarpoint Ventures III call 7.

### 5. uc-005-benefcheck: PASS

Figures bound: bank_details_changed -> bank_details_changed; payments_on_hold -> bank_details_changed. Answered from: bank_details_changed.

Signals fired: uc-005-benefcheck-hold x1.

### 6. uc-006-fxneed: PASS

Figures bound: fx_plan_match -> fx_confirmation_variance; call_paid_match -> call_payment_status. Answered from: call_payment_status, fx_confirmation_variance, fx_rate_check, fx_required.

Signals fired: uc-006-fxneed-no-confirmation x1; uc-006-fxneed-release x1.

Signals that cannot run on the loaded data: uc-006-fxneed-confirmation-off cannot run: no reader gives doc.trade_reference, doc.rate.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-006-fxneed-release fires on Cedarpoint Ventures III call 7.

### 7. uc-007-pacing: PASS

Figures bound: commitments_by_fund -> commitments_by_fund; budget_headroom -> private_markets_budget. Answered from: commitments_by_fund, private_markets_budget.

Signals fired: uc-007-pacing-unfunded x1.

Signals that cannot run on the loaded data: uc-007-pacing-over-budget cannot run: doc.budget_room_after on every row.

### 8. uc-008-payrun: PASS

Figures bound: payment_batch -> payment_batch. Answered from: payment_batch.

Signals fired: uc-008-payrun-changed-account x1; uc-008-payrun-fee-hold x1; uc-008-payrun-waiting x1.

### 9. uc9-sop: PASS

Figures bound: process_steps -> process_steps. Answered from: process_steps.

Signals fired: uc9-sop-published x1; uc9-sop-steps-drawn x1.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc9-sop-published fires on Monthly investment report in USD and SGD SOP; uc9-sop-steps-drawn fires on Monthly investment report in USD and SGD.

### 10. uc-010-bankexp: PASS

Figures bound: cash_by_bank -> cash_by_bank. Answered from: cash_by_bank.

Signals fired: none.

Signals that cannot run on the loaded data: uc-010-bankexp-over-limit cannot run: figure cash_by_bank for {'worst': 1} on every row.

### 11. uc10-pipeline: PASS

Figures bound: net_worth -> net_worth. Answered from: net_worth.

Signals fired: uc10-pipeline-column-held x1; uc10-pipeline-net-worth-shown x168.

Signals that cannot run on the loaded data: uc10-pipeline-files-ready cannot run: no reader gives doc.file_rows, doc.loaded_rows.

### 12. uc5-limits: PASS

Figures bound: single_name_concentration -> concentration. Answered from: concentration, drift_vs_target, single_name_breach.

Signals fired: uc5-limits-breach x7; uc5-limits-no-class x1.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc5-limits-no-class fires on Evergreen Liquid Book Pacific Rim Convertible 2029 note no asset class.

### 13. uc-013-secgaps: PASS

Figures bound: unclassified_holdings -> identifier_gaps. Answered from: identifier_gaps.

Signals fired: uc-013-secgaps-found x1.

Signals that cannot run on the loaded data: uc-013-secgaps-completed cannot run: figure identifier_gaps for {'first_row': True} on every row; uc-013-secgaps-over-one-percent cannot run: figure identifier_gaps for {'first_row': True} on every row.

### 14. morning-networth-note: PASS

Figures bound: networth_usd_sgd -> report_total_fx. Answered from: report_ready, report_total_fx.

Signals fired: morning-networth-note-today x1.

Signals that cannot run on the loaded data: morning-networth-note-call-uncovered cannot run: recipe cash_after_calls has no column call_amount, due_in_days; morning-networth-note-report-old cannot run: no reader gives doc.days_since_issue.

### 15. uc-015-allowances: PASS

Figures bound: allowance_due -> allowance_due. Answered from: allowance_due.

Key values not compared (no column answers them yet): q1.unpaid_earlier, q1.total_owed, q1.trust_usd_cash.

Signals fired: uc-015-allowances-unpaid-earlier x1.

Signals that cannot run on the loaded data: uc-015-allowances-approved cannot run: figure cash_by_entity for {'entity': 'doc.entity', 'currency': 'doc.currency'} on every row; uc-015-allowances-cash-short cannot run: figure cash_by_entity for {'entity': 'doc.entity', 'currency': 'doc.currency'} on every row.

### 16. uc-016-schemadrift: PASS

Figures bound: columns_changed -> columns_changed. Answered from: columns_changed.

Key values not compared (no column answers them yet): q1.file.

Signals fired: uc-016-schemadrift-mapping-proposed x1; uc-016-schemadrift-mapping-used x1.

Signals that cannot run on the loaded data: uc-016-schemadrift-type-or-unit-changed cannot run: no reader gives doc.column, doc.type_new, doc.type_old, doc.unit_new, doc.unit_old.

### 17. uc-017-liab: PASS

Figures bound: net_worth_after_debt -> net_worth_after_debt. Answered from: facility_headroom, net_worth_after_debt, report_total_fx.

Signals fired: uc-017-liab-no-limit-on-record x1; uc-017-liab-owed x1.

Signals that cannot run on the loaded data: uc-017-liab-headroom cannot run: rule facility_headroom_line on every row.

### 18. uc-018-fundplan: PASS

Figures bound: funding_plan -> funding_plan. Answered from: funding_plan.

Signals fired: uc-018-fundplan-plan x1; uc-018-fundplan-under-buffer x1.

### 19. uc3-statements-inbox: PASS

Figures bound: missing_statements -> statement_timeliness. Answered from: statement_timeliness.

Signals fired: uc3-statements-inbox-matched x12; uc3-statements-inbox-missing x2.

Signals that cannot run on the loaded data: uc3-statements-inbox-unknown-fund cannot run: recipe statement_timeliness has no column fund_match.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc3-statements-inbox-missing fires on TCB-B-USD statement 2026-07-31.

### 20. uc1-why-nav-moved: PASS

Figures bound: change_since_report -> change_since_report. Answered from: amendments_open, change_since_report.

Key values not compared (no column answers them yet): q1.over_materiality.

Signals fired: uc1-why-nav-moved-amended x3; uc1-why-nav-moved-bridge x3; uc1-why-nav-moved-over-materiality x3.

### 21. uc-021-stale: PASS

Figures bound: value_age_days -> value_age_days. Answered from: value_age_days.

Signals fired: uc-021-stale-breach-on-stale x1; uc-021-stale-estimate-only x1; uc-021-stale-found x1; uc-021-stale-fresh x3.

### 22. uc-022-amendlog: PASS

Figures bound: amendments_open -> amendments_open. Answered from: amendments_open.

Signals fired: uc-022-amendlog-listed x4; uc-022-amendlog-replaces x2.

### 23. uc-023-tieout: PASS

Figures bound: report_tie_out -> report_tie_out. Answered from: report_tie_out.

Signals fired: uc-023-tieout-differs x3; uc-023-tieout-ties x9; uc-023-tieout-unexplained x3.

### 24. uc-024-audit: PASS

Figures bound: trace_coverage -> trace_coverage. Answered from: trace_coverage.

Signals fired: uc-024-audit-traced x7; uc-024-audit-untraced x1.

### 25. uc7-manager-diligence: PASS

Figures bound: manager_timeline -> manager_timeline. Answered from: manager_timeline.

Signals fired: uc7-manager-diligence-restated x2; uc7-manager-diligence-team-change x1.

### 26. uc-026-stmtadmin: PASS

Figures bound: statement_vs_admin -> statement_vs_admin. Answered from: statement_vs_admin.

Signals fired: uc-026-stmtadmin-ask-administrator x5; uc-026-stmtadmin-compared x6; uc-026-stmtadmin-explained x1.

### 27. uc2-recon-break-desk: PASS

Figures bound: cash_break -> cash_difference_by_source. Answered from: cash_difference_by_source.

Signals fired: uc2-recon-break-desk-inside-tolerance x1; uc2-recon-break-desk-over-tolerance x2.

### 28. uc-028-interco: PASS

Figures bound: intercompany_balance -> intercompany_balance. Answered from: intercompany_balance.

Signals fired: uc-028-interco-offer x1.

Signals that cannot run on the loaded data: uc-028-interco-one-sided cannot run: figure intercompany_balance for {'sides_agree': False} on every row.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-028-interco-offer fires on Cedarpoint Ventures III call 7.

### 29. uc-029-closeck: PASS

Figures bound: close_items_done -> close_items_done. Answered from: close_items_done.

Signals fired: uc-029-closeck-item-late x2.

Signals that cannot run on the loaded data: uc-029-closeck-report-can-start cannot run: no reader gives doc.close_month, doc.steps, doc.open; uc-029-closeck-sign-close cannot run: no reader gives doc.close_month, doc.steps, doc.done, doc.open, doc.late.

### 30. uc-030-vendors: PASS

Figures bound: renewals_vendors -> renewals_vendors. Answered from: renewals_vendors.

Signals fired: uc-030-vendors-approved x2; uc-030-vendors-notice-near x1; uc-030-vendors-renewing x2.

### 31. uc-031-alloc: PASS

Figures bound: allocation_pct -> allocation. Answered from: allocation.

Signals fired: uc-031-alloc-ready x1; uc-031-alloc-unclassified x1.

### 32. uc-032-driftrep: PASS

Figures bound: drift_vs_target -> drift_vs_target. Answered from: drift_vs_target.

Signals fired: none.

Signals that cannot run on the loaded data: uc-032-driftrep-back-inside cannot run: recipe drift_vs_target has no column was_outside.

### 33. uc-033-breachesc: PASS

Figures bound: cost_to_cure -> single_name_breach. Answered from: single_name_breach.

Signals fired: uc-033-breachesc-cost-to-cure x7.

Signals that cannot run on the loaded data: uc-033-breachesc-waiver-expired cannot run: no reader gives doc.breach_open, doc.days_past_expiry; uc-033-breachesc-waiver-recorded cannot run: no reader gives doc.committee, doc.decided_on, doc.outcome, doc.subject_id.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-033-breachesc-cost-to-cure fires on Evergreen Liquid Book Northwind Logistics cost to cure; uc-033-breachesc-cost-to-cure fires on Evergreen Liquid Book Juniper Consumer Brands cost to cure; uc-033-breachesc-cost-to-cure fires on Evergreen Liquid Book Coastal Rail Holdings cost to cure; uc-033-breachesc-cost-to-cure fires on Evergreen Liquid Book Evermore Banking Group cost to cure; uc-033-breachesc-cost-to-cure fires on Evergreen Liquid Book Larkspur Health cost to cure; uc-033-breachesc-cost-to-cure fires on Evergreen Liquid Book Atlas Harbour Shipping cost to cure.

### 34. uc-034-prospect: PASS

Figures bound: mandate_fit -> mandate_fit. Answered from: mandate_fit.

Signals fired: uc-034-prospect-screened x5.

Signals that cannot run on the loaded data: uc-034-prospect-class-over cannot run: doc.class_limit_pct on every row.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-034-prospect-screened fires on Harborlight Ventures IV; uc-034-prospect-screened fires on Marlow Infrastructure Partners III; uc-034-prospect-screened fires on Pelican Credit Opportunities II; uc-034-prospect-screened fires on Ashgrove Growth Equity V; uc-034-prospect-screened fires on Nimbus Secondaries I.

### 35. uc-035-ddq: PASS

Figures bound: ddq_compare -> ddq_compare. Answered from: ddq_compare.

Signals fired: uc-035-ddq-differences x5; uc-035-ddq-fee-answer x1.

### 36. uc6-uncalled: PASS

Figures bound: uncalled_total -> called_to_date. Answered from: called_to_date.

Signals fired: none.

### 37. uc-037-distrack: PASS

Figures bound: distribution_gap -> distribution_gap. Answered from: distribution_gap.

Signals fired: uc-037-distrack-no-credit x1.

Signals that cannot run on the loaded data: uc-037-distrack-logged cannot run: no reader gives doc.fund, doc.amount, doc.currency, doc.pay_date.

### 38. uc-038-navroll: PASS

Figures bound: nav_rollforward -> nav_rollforward. Answered from: nav_rollforward.

Signals fired: uc-038-navroll-statement x12; uc-038-navroll-ties x10; uc-038-navroll-unexplained x2.

### 39. uc-039-irr: PASS

Figures bound: fund_irr_tvpi -> fund_irr_tvpi. Answered from: fund_irr_tvpi.

Signals fired: uc-039-irr-by-fund x8.

### 40. uc-040-icmemo: PASS

Figures bound: memo_support -> memo_support. Answered from: memo_support.

Signals fired: uc-040-icmemo-figure-source x2.

### 41. uc-041-commitappr: PASS

Figures bound: commit_check -> commit_check. Answered from: commit_check.

Signals fired: uc-041-commitappr-cash-short x5; uc-041-commitappr-test-not-on-record x5.

### 42. uc4-vs-benchmark: PASS

Figures bound: active_return -> time_weighted_return. Answered from: time_weighted_return.

Key values not compared (no column answers them yet): q1.equity_index_pct, q1.bond_index_pct.

Signals fired: uc4-vs-benchmark-month x6.

Signals that cannot run on the loaded data: uc4-vs-benchmark-definition-changed cannot run: no reader gives doc.effective_from, doc.previous_version; uc4-vs-benchmark-index-missing cannot run: doc.benchmark_gap on every row.

### 43. uc-043-liquidpnl: PASS

Figures bound: liquid_pnl_mtd -> liquid_pnl_mtd. Answered from: liquid_pnl_mtd.

Signals fired: uc-043-liquidpnl-daily x1.

### 44. uc-044-twr: PASS

Figures bound: twr_periods -> time_weighted_return. Answered from: time_weighted_return.

Signals fired: uc-044-twr-flow-timing x5; uc-044-twr-periods x2.

Signals that cannot run on the loaded data: uc-044-twr-no-link cannot run: recipe time_weighted_return has no column stated_return_pct.

### 45. uc-045-reportpack: PASS

Figures bound: report_ready -> report_ready. Answered from: report_ready.

Signals fired: uc-045-reportpack-drafted x1.

### 46. uc-046-attrib: PASS

Figures bound: attribution -> attribution. Answered from: attribution.

Signals fired: uc-046-attrib-effects x21; uc-046-attrib-slide x21.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-046-attrib-slide fires on Evergreen Liquid Book 2026-09-30 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-09-30 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-09-30 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-06-30 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-06-30 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-06-30 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-07-31 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-07-31 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-07-31 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-08-31 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-08-31 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-08-31 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-10-13 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-10-13 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-10-13 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-05-31 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-05-31 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-05-31 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-04-30 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-04-30 slide; uc-046-attrib-slide fires on Evergreen Liquid Book 2026-04-30 slide.

### 47. uc-047-icpack: PASS

Figures bound: pack_items -> pack_items. Answered from: pack_items.

Signals fired: uc-047-icpack-assembled x1.

Signals that cannot run on the loaded data: uc-047-icpack-open-late cannot run: no reader gives doc.days_to_committee; uc-047-icpack-section-done cannot run: recipe pack_items has no column done.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-047-icpack-assembled fires on committee pack as at 2026-09-30.

### 48. uc-048-policyupd: PASS

Figures bound: limit_changes -> limit_changes. Answered from: limit_changes.

Signals fired: uc-048-policyupd-review x1.

Signals that cannot run on the loaded data: uc-048-policyupd-approved cannot run: no reader gives doc.decided_on, doc.effective_from, doc.outcome.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-048-policyupd-review fires on single-name limit version 2 for Evergreen Liquid Book.

### 49. uc-049-feedrag: PASS

Figures bound: fee_drag -> fee_drag. Answered from: fee_drag.

Signals fired: uc-049-feedrag-above-terms x1; uc-049-feedrag-share x4.

### 50. uc-050-feeinv: PASS

Figures bound: invoice_variance -> invoice_variance. Answered from: invoice_variance.

Signals fired: uc-050-feeinv-above-schedule x1; uc-050-feeinv-arrives x3; uc-050-feeinv-matches x4.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-050-feeinv-arrives fires on FEE-CUST-Q2; uc-050-feeinv-arrives fires on FEE-ADMIN-Q3; uc-050-feeinv-arrives fires on FEE-ADMIN-Q2.

### 51. uc8-trades-vs-admin: PASS

Figures bound: fx_confirmation_variance -> fx_confirmation_variance. Answered from: fx_confirmation_variance, trade_breaks.

Key values not compared (no column answers them yet): q1.fx_forward, q1.booked_rate, q1.confirmed_rate, q1.difference_usd_at_8_oct.

Signals fired: uc8-trades-vs-admin-booked-twice x1; uc8-trades-vs-admin-fx-confirmation-differs x1; uc8-trades-vs-admin-missing-at-administrator x1; uc8-trades-vs-admin-quantity-differs x1.

### 52. uc-052-insurance: PASS

Figures bound: renewals_due -> renewals_due. Answered from: renewals_due.

Signals fired: uc-052-insurance-due x1; uc-052-insurance-no-notice x1.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-052-insurance-due fires on POL-LIAB-03 renews 2026-11-01.

### 53. uc-053-watchlist: PASS

Figures bound: watch_flags -> watch_flags. Answered from: watch_flags.

Signals fired: uc-053-watchlist-flagged x4; uc-053-watchlist-missing x1.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-053-watchlist-flagged fires on Kestrel Ridge Advisors.

### 54. uc-054-ladder: PASS

Figures bound: liquidity_ladder -> liquidity_ladder. Answered from: cash_by_entity, liquidity_ladder.

Signals fired: uc-054-ladder-tightest x1.

### 55. uc-055-corpact: PASS

Figures bound: actions_next_14d -> actions_next_14d. Answered from: actions_next_14d.

Signals fired: uc-055-corpact-election x1; uc-055-corpact-to-book x1.

### 56. uc-056-custrecon: PASS

Figures bound: position_break -> position_break. Answered from: position_break.

Signals fired: uc-056-custrecon-quantity-differs x2.

### 57. uc-057-pricecheck: PASS

Figures bound: price_gap_pct -> price_gap_pct. Answered from: price_gap_pct.

Signals fired: uc-057-pricecheck-over-tolerance x2.

### 58. uc-058-settle: PASS

Figures bound: unsettled_trades -> unsettled_trades. Answered from: unsettled_trades.

Key values not compared (no column answers them yet): q1.settled_in_report.

Signals fired: uc-058-settle-failed x2.

### 59. uc-059-breakage: PASS

Figures bound: break_age -> break_age. Answered from: break_age.

Signals fired: uc-059-breakage-open x6; uc-059-breakage-to-finance x2.

### 60. uc-060-docinbox: PASS

Figures bound: unrecognised_files -> unrecognised_files. Answered from: unrecognised_files.

Signals fired: uc-060-docinbox-duplicate x2; uc-060-docinbox-new x1; uc-060-docinbox-unrecognised x2.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-060-docinbox-new fires on INV-OIT-2610.pdf to invoices.

### 61. uc-061-dqscore: PASS

Figures bound: source_quality -> source_quality. Answered from: source_quality.

Signals fired: uc-061-dqscore-fix-first x1; uc-061-dqscore-never-arrived x2.

### 62. uc-062-fxlife: PASS

Figures bound: fx_mtm -> fx_mtm. Answered from: cash_by_entity, fx_mtm.

Signals fired: uc-062-fxlife-confirmation-differs x1; uc-062-fxlife-marked x2.

### 63. uc-063-cashcode: PASS

Figures bound: uncoded_bank_lines -> uncoded_bank_lines. Answered from: uncoded_bank_lines.

Signals fired: uc-063-cashcode-uncoded x3.

### 64. uc-064-fxexp: PASS

Figures bound: currency_exposure -> currency_exposure. Answered from: currency_exposure.

Key values not compared (no column answers them yet): q1.sgd_payments_next_90_days_usd_eq.

Signals fired: uc-064-fxexp-exposure x1; uc-064-fxexp-forward-differs x1.

Signals that cannot run on the loaded data: uc-064-fxexp-over-limit cannot run: rule currency_exposure_limit_pct on every row.

### 65. uc-065-realassets: PASS

Figures bound: real_asset_value -> real_asset_value. Answered from: real_asset_value.

Signals fired: uc-065-realassets-register x1; uc-065-realassets-title x1.

### 66. uc-066-propreval: PASS

Figures bound: appraisal_age -> appraisal_age. Answered from: appraisal_age.

Signals fired: uc-066-propreval-due x1.

### 67. uc-067-unrl: PASS

Figures bound: unrealised_gain -> unrealised_gain. Answered from: unrealised_gain.

Key values not compared (no column answers them yet): q1.harborview_sale_to_reach_5_pct.

Signals fired: uc-067-unrl-losses x1; uc-067-unrl-over-limit x1.

### 68. uc-068-incomef: PASS

Figures bound: income_forecast -> income_forecast. Answered from: income_forecast.

Signals fired: uc-068-incomef-forecast x1.

### 69. uc-069-lookthru: PASS

Figures bound: lookthrough_exposure -> lookthrough_exposure. Answered from: lookthrough_exposure.

Signals fired: uc-069-lookthru-overlap x1; uc-069-lookthru-top x1.

### 70. uc-070-idle: PASS

Figures bound: idle_cash -> idle_cash. Answered from: idle_cash.

Signals fired: uc-070-idle-surplus x1.

### 71. uc-071-expdist: PASS

Figures bound: expected_distributions -> expected_distributions. Answered from: expected_distributions.

Signals fired: uc-071-expdist-fund x8; uc-071-expdist-stale-value x3.

### 72. uc-072-cashfc: PASS

Figures bound: cash_forecast -> cash_forecast. Answered from: cash_forecast.

Signals fired: uc-072-cashfc-below-floor x1; uc-072-cashfc-outlook x1; uc-072-cashfc-schedule-ends x1.

### 73. uc-073-runway: PASS

Figures bound: cash_runway -> cash_runway. Answered from: cash_runway.

Signals fired: uc-073-runway-months x1.

### 74. uc-074-boardpack: PASS

Figures bound: board_summary -> board_summary. Answered from: board_summary.

Key values not compared (no column answers them yet): q1.sources.

Signals fired: uc-074-boardpack-amended x1; uc-074-boardpack-estimate x1; uc-074-boardpack-headline x1.

### 75. uc-075-yearwalk: PASS

Figures bound: networth_walk -> networth_walk. Answered from: networth_walk.

Key values not compared (no column answers them yet): q1.adds_up, q1.fx_and_other_pct_of_closing, q1.statements_missing.

Signals fired: uc-075-yearwalk-estimate x1; uc-075-yearwalk-headline x1; uc-075-yearwalk-incomplete x1.

### 76. uc-076-scorecard: PASS

Figures bound: manager_score -> manager_score. Answered from: manager_score.

Signals fired: uc-076-scorecard-review x3; uc-076-scorecard-score x6.

### 77. uc-077-deals: PASS

Figures bound: deal_stage -> deal_stage. Answered from: deal_stage.

Signals fired: uc-077-deals-stage x5; uc-077-deals-stuck x2.

### 78. uc-078-redemption: PASS

Figures bound: redemption_dates -> redemption_dates. Answered from: redemption_dates.

Signals fired: uc-078-redemption-locked x1; uc-078-redemption-notice x2.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-078-redemption-notice fires on Kestrel Ridge Macro Fund.

### 79. uc-079-rebalance: PASS

Figures bound: rebalance_trades -> rebalance_trades. Answered from: rebalance_trades.

Signals fired: uc-079-rebalance-proposal x3; uc-079-rebalance-unsigned x3.

### 80. uc-080-vintage: PASS

Figures bound: vintage_split -> vintage_split. Answered from: vintage_split.

Signals fired: uc-080-vintage-split x5.

Signals that cannot run on the loaded data: uc-080-vintage-bunched cannot run: rule limit_vintage_year on every row.

### 81. uc-081-payroll: PASS

Figures bound: payroll_total -> payroll_total. Answered from: payroll_total.

Signals fired: uc-081-payroll-flag x2.

### 82. uc-082-covergap: PASS

Figures bound: cover_gap -> cover_gap. Answered from: cover_gap.

Signals fired: uc-082-covergap-no-policy x4; uc-082-covergap-under-insured x2.

### 83. uc-083-taxcal: PASS

Figures bound: tax_due -> tax_due. Answered from: tax_due.

Signals fired: uc-083-taxcal-due x2; uc-083-taxcal-overdue x1.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-083-taxcal-due fires on TX-02 Evergreen Holdings due 2026-11-30; uc-083-taxcal-due fires on TX-01 Evergreen Holdings due 2026-11-30.

### 84. uc-084-taxest: FAIL

Figures bound: tax_estimate -> tax_estimate. Answered from: tax_estimate.

| Key value | Expected | Got | Recipe |
|---|---|---|---|
| q1 by_entity.Entity B.income | 89,709.31 | 89,664.6 | tax_estimate |
| q1 by_entity.Entity B.tax_before_credits | 15,250.58 | 15,242.98 | tax_estimate |
| q1 by_entity.Entity B.tax_to_set_aside | 15,250.58 | 15,242.98 | tax_estimate |
| q1 total_to_set_aside | 159,164.11 | 159,156.51 | tax_estimate |

Key values not compared (no column answers them yet): q1.period.

Signals fired: uc-084-taxest-income-gap x1; uc-084-taxest-set-aside x3.

### 85. uc-085-grants: PASS

Figures bound: grants_used -> grants_used. Answered from: grants_used.

### 86. uc-086-grantappr: PASS

Figures bound: grant_check -> grant_check. Answered from: grant_check.

Signals fired: uc-086-grantappr-fails x1.

### 87. uc-087-trustdist: PASS

Figures bound: trust_distribution_room -> trust_distribution_room. Answered from: trust_distribution_room.

Signals fired: uc-087-trustdist-over x1.

### 88. uc-088-estateliq: PASS

Figures bound: estate_cash_need -> estate_cash_need. Answered from: estate_cash_need.

### 89. uc-089-expapp: PASS

Figures bound: approval_exceptions -> approval_exceptions. Answered from: approval_exceptions.

Key values not compared (no column answers them yet): q1.limits.Priya Nair, q1.limits.Grace Ong, q1.limits.Daniel Foo, q1.limits.Raj Patel.

Signals fired: uc-089-expapp-over-limit x2.

### 90. uc-090-offcost: PASS

Figures bound: office_cost -> office_cost. Answered from: office_cost.

Signals fired: uc-090-offcost-over x2.

Non-info signals that fire on a row with no planted mess (a note, not a verdict): uc-090-offcost-over fires on Professional fees over budget; uc-090-offcost-over fires on Grants over budget.

### 91. uc-091-jml: PASS

Figures bound: access_open -> access_review. Answered from: access_review.

Signals fired: uc-091-jml-leaver x3; uc-091-jml-no-approver x2; uc-091-jml-not-requested x1.

### 92. uc-092-accessrev: PASS

Figures bound: stale_access -> access_review. Answered from: access_review.

Signals fired: uc-092-accessrev-unused x3.

### 93. uc-093-onbmgr: PASS

Figures bound: onboarding_items -> onboarding_items. Answered from: onboarding_items.

Signals fired: uc-093-onbmgr-missing x2.

### 94. uc-094-onbbank: PASS

Figures bound: account_setup -> account_setup. Answered from: account_setup.

Key values not compared (no column answers them yet): q1.steps, q1.outstanding.

Signals fired: uc-094-onbbank-signatory x1.

### 95. uc-095-sopreview: PASS

Figures bound: sop_age -> sop_age. Answered from: sop_age.

Signals fired: uc-095-sopreview-due x3.

### 96. uc-096-automation: PASS

Figures bound: automation_score -> automation_score. Answered from: automation_score.

### 97. uc-097-kycrefresh: PASS

Figures bound: kyc_expiry -> kyc_expiry. Answered from: kyc_expiry.

Signals fired: uc-097-kycrefresh-expired x1; uc-097-kycrefresh-expiring x3.

### 98. uc-098-wordlist: PASS

Figures bound: terms_proposed -> terms_proposed. Answered from: terms_proposed.

Signals fired: uc-098-wordlist-to-add x2.

### 99. uc-099-newfeed: PASS

Figures bound: feed_mapping -> feed_mapping. Answered from: feed_mapping.

Key values not compared (no column answers them yet): q1.rows_in_sample.

Signals fired: uc-099-newfeed-in-doubt x2.

### 100. uc-100-famaccess: PASS

Figures bound: member_access -> member_access. Answered from: member_access.

Signals fired: uc-100-famaccess-over-granted x1.

