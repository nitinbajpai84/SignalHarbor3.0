# Score of the top 50 use cases

Written by `python tools/score50.py` on 2026-10-17 16:25. Office: tests/v1/fixtures/office6m as of 2026-10-13, loaded once with the real loader (v3_office6m_loaders.load_plane); 58 built recipes run once; keys from answer_keys.yaml; signals from packs/family_office/1/signals. Deterministic: no model is called. Load 33 s, whole run 78 s.

PASS: every key value matches and the signals behave. FAIL: a number is wrong, or a recipe the card needs does not run or tie out. SIGNAL: the numbers are right but the planted mess is not caught, or an exception signal fires on a clean row. BLOCKED: needs something that does not exist yet.

## Totals

| PASS | FAIL | SIGNAL | BLOCKED | Cards |
|---|---|---|---|---|
| 39 | 8 | 2 | 1 | 50 |

Key values compared: 560, matching: 541.

## By domain

| Domain | PASS | FAIL | SIGNAL | BLOCKED | Cards |
|---|---|---|---|---|---|
| Cash and treasury | 10 | 1 | 0 | 0 | 11 |
| Invest | 7 | 0 | 1 | 0 | 8 |
| Operate and control | 7 | 1 | 0 | 0 | 8 |
| Hold and maintain | 5 | 0 | 1 | 0 | 6 |
| Run the office | 2 | 0 | 0 | 1 | 3 |
| Report and govern | 8 | 5 | 0 | 0 | 13 |
| Family and people | 0 | 1 | 0 | 0 | 1 |

## By person (card owner)

| Person | PASS | FAIL | SIGNAL | BLOCKED | Cards |
|---|---|---|---|---|---|
| Daniel Foo | 5 | 0 | 0 | 0 | 5 |
| Sam Lee | 2 | 0 | 0 | 0 | 2 |
| Sofia Reyes | 6 | 0 | 0 | 0 | 6 |
| Grace Ong | 5 | 1 | 0 | 0 | 6 |
| Anita Rao | 3 | 1 | 0 | 0 | 4 |
| Helen Foo | 6 | 0 | 2 | 0 | 8 |
| Mei Chen | 2 | 1 | 0 | 0 | 3 |
| Tom Hale | 4 | 2 | 0 | 0 | 6 |
| Raj Patel | 5 | 3 | 0 | 0 | 8 |
| Priya Nair | 1 | 0 | 0 | 1 | 2 |

## Failures by root cause, worst first

A card can sit under more than one cause. The cause is what the expected-against-got numbers of the card detail point to.

1. **No benchmark is linked to the liquid book; 'since 1 April' runs to 13 Oct**. FAIL, 2 card(s): 42, 44. Recipes: time_weighted_return.
2. **The sovereign note counts as a single name (no signed exemption), so every month breaches**. FAIL, 2 card(s): 47, 48. Recipes: limit_changes, pack_items.
3. **no recipe reads the process narrative into steps and owners (figure process_steps; signals need doc.process_name, steps, steps_without_owner)**. BLOCKED, 1 card(s): 9.
4. **An invoice above its fee schedule is not held in the payment run**. FAIL, 1 card(s): 8. Recipes: payment_batch.
5. **Reads the latest day (13 Oct), not the 30 Sep month end the key reads**. FAIL, 1 card(s): 12. Recipes: single_name_breach.
6. **The renamed-column count is of batches, not months**. FAIL, 1 card(s): 16. Recipes: columns_changed.
7. **recipe allowance_due gives a wrong number**. FAIL, 1 card(s): 15. Recipes: allowance_due.
8. **exception signal fires on a clean row: uc-038-navroll-unexplained**. SIGNAL, 1 card(s): 38.
9. **exception signal fires on a clean row: uc-049-feedrag-above-terms**. SIGNAL, 1 card(s): 49.

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
| 8 | uc-008-payrun: Weekly payment run with two approvals | Cash and treasury | Grace Ong | **FAIL** | 15/17 | items[Anchorage Custody (synthetic)].state: expected 'hold: invoice above fee schedule', got 'ready' (payment_batch); states: expected {'hold: invoice above fee schedule': 1, 'ready': 2, 'waiting for approval': 1}, got {'ready': 3, 'waiting for approval': 1} (payment_batch) |
| 9 | uc9-sop: Process map and SOP for the month-end report | Run the office | Priya Nair | **BLOCKED** | 0/0 | no recipe reads the process narrative into steps and owners (figure process_steps; signals need doc.process_name, steps, steps_without_owner) |
| 10 | uc-010-bankexp: Cash held at each bank against the bank limit | Cash and treasury | Tom Hale | **PASS** | 5/5 | all key values match; signals behave |
| 11 | uc10-pipeline: A monthly pipeline and insight from the administrator and trading files | Operate and control | Anita Rao | **PASS** | 6/6 | all key values match; signals behave |
| 12 | uc5-limits: Allocation and limit monitoring | Report and govern | Tom Hale | **FAIL** | 9/10 | holding: expected 'Harborview Semiconductor', got "8 rows where portfolio='Evergreen Liquid Book', position_date='2026-09-30', status='real breach'" (single_name_breach) |
| 13 | uc-013-secgaps: Securities with no asset class or identifier | Hold and maintain | Anita Rao | **PASS** | 3/3 | all key values match; signals behave |
| 14 | morning-networth-note: A morning note on what we are worth | Report and govern | Mei Chen | **PASS** | 7/7 | all key values match; signals behave |
| 15 | uc-015-allowances: Family member allowances and distributions due | Family and people | Mei Chen | **FAIL** | 0/4 | due_october.Lin Chen: expected 8000, got 0 (allowance_due); due_october.Maya Chen: expected 6000, got 0 (allowance_due); due_october.Ethan Chen: expected 5000, got 0 (allowance_due); due_october.Wen Chen: expected 4000, got 0 (allowance_due) |
| 16 | uc-016-schemadrift: A source file arrives with a new or renamed column | Operate and control | Anita Rao | **FAIL** | 2/3 | months_with_old_name: expected 5, got 6 (columns_changed) |
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
| 38 | uc-038-navroll: Private fund value roll-forward | Hold and maintain | Helen Foo | **SIGNAL** | 1/1 | uc-038-navroll-unexplained fires on a clean row (Evergreen Growth I unexplained -12,500 at 2026-09-30) |
| 39 | uc-039-irr: Return of each private fund since we invested | Invest | Sofia Reyes | **PASS** | 40/40 | all key values match; signals behave |
| 40 | uc-040-icmemo: Investment committee memo for a new commitment | Invest | Sofia Reyes | **PASS** | 8/8 | all key values match; signals behave |
| 41 | uc-041-commitappr: Approve a new commitment within policy | Invest | Raj Patel | **PASS** | 4/4 | all key values match; signals behave |
| 42 | uc4-vs-benchmark: How did the portfolio do against its benchmark? | Report and govern | Raj Patel | **FAIL** | 3/5 | benchmark_return_pct: expected 2.7072, got None (time_weighted_return); active_pct: expected 1.4595, got None (time_weighted_return) |
| 43 | uc-043-liquidpnl: Liquid book gain or loss so far this month | Hold and maintain | Raj Patel | **PASS** | 5/5 | all key values match; signals behave |
| 44 | uc-044-twr: Return for the year against the benchmark | Report and govern | Raj Patel | **FAIL** | 4/5 | benchmark_since_1_apr_pct: expected 5.7563, got None (time_weighted_return) |
| 45 | uc-045-reportpack: Monthly investment report: assemble and sign | Report and govern | Raj Patel | **PASS** | 4/4 | all key values match; signals behave |
| 46 | uc-046-attrib: Where did the return come from | Report and govern | Sofia Reyes | **PASS** | 14/14 | all key values match; signals behave |
| 47 | uc-047-icpack: Investment committee pack | Report and govern | Raj Patel | **FAIL** | 6/7 | real_breaches: expected 1, got 8 (pack_items) |
| 48 | uc-048-policyupd: Update the allocation policy and its limits | Report and govern | Tom Hale | **FAIL** | 2/9 | max_single_name_pct_by_month_end.2026-04-30: expected 6.13, got 7.17 (limit_changes); max_single_name_pct_by_month_end.2026-05-31: expected 5.89, got 7.3 (limit_changes); max_single_name_pct_by_month_end.2026-06-30: expected 5.74, got 7.34 (limit_changes); max_single_name_pct_by_month_end.2026-07-31: expected 5.71, got 7.28 (limit_changes); max_single_name_pct_by_month_end.2026-08-31: expected 5.71, got 7.35 (limit_changes); max_single_name_pct_by_month_end.2026-09-30: expected 5.75, got 7.08 (limit_changes); and 1 more |
| 49 | uc-049-feedrag: Fees paid to each manager | Invest | Helen Foo | **SIGNAL** | 16/16 | uc-049-feedrag-above-terms fires on a clean row (Bluewater Capital) |
| 50 | uc-050-feeinv: Administrator and custodian invoices against the fee schedule | Run the office | Grace Ong | **PASS** | 17/17 | all key values match; signals behave |

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

### 5. uc-005-benefcheck: PASS

Figures bound: bank_details_changed -> bank_details_changed; payments_on_hold -> bank_details_changed. Answered from: bank_details_changed.

Signals fired: uc-005-benefcheck-hold x1.

### 6. uc-006-fxneed: PASS

Figures bound: fx_plan_match -> fx_confirmation_variance; call_paid_match -> call_payment_status. Answered from: call_payment_status, fx_confirmation_variance, fx_rate_check, fx_required.

Signals fired: uc-006-fxneed-no-confirmation x1; uc-006-fxneed-release x1.

Signals that cannot run on the loaded data: uc-006-fxneed-confirmation-off cannot run: no reader gives doc.trade_reference, doc.rate.

### 7. uc-007-pacing: PASS

Figures bound: commitments_by_fund -> commitments_by_fund; budget_headroom -> private_markets_budget. Answered from: commitments_by_fund, private_markets_budget.

Signals fired: uc-007-pacing-unfunded x1.

Signals that cannot run on the loaded data: uc-007-pacing-over-budget cannot run: doc.budget_room_after on every row.

### 8. uc-008-payrun: FAIL

Figures bound: payment_batch -> payment_batch. Answered from: payment_batch.

| Key value | Expected | Got | Recipe |
|---|---|---|---|
| q1 items[Anchorage Custody (synthetic)].state | 'hold: invoice above fee schedule' | 'ready' | payment_batch |
| q1 states | {'hold: invoice above fee schedule': 1, 'ready': 2, 'waiting for approval': 1} | {'ready': 3, 'waiting for approval': 1} | payment_batch |

Signals fired: uc-008-payrun-changed-account x1; uc-008-payrun-waiting x1.

Signal problems: planted mess not caught by any signal: M15 invoice above schedule.

### 9. uc9-sop: BLOCKED

Figures bound: -. Answered from: -.

Blocked: no recipe reads the process narrative into steps and owners (figure process_steps; signals need doc.process_name, steps, steps_without_owner)

Signals that cannot run on the loaded data: uc9-sop-published cannot run: no reader gives doc.process_name, doc.steps; uc9-sop-step-gap cannot run: no reader gives doc.process_name, doc.steps, doc.steps_without_check, doc.steps_without_owner; uc9-sop-steps-drawn cannot run: no reader gives doc.manual_steps, doc.process_name, doc.steps, doc.steps_without_check, doc.steps_without_owner.

### 10. uc-010-bankexp: PASS

Figures bound: cash_by_bank -> cash_by_bank. Answered from: cash_by_bank.

Signals fired: none.

Signals that cannot run on the loaded data: uc-010-bankexp-over-limit cannot run: figure cash_by_bank for {'worst': 1} on every row.

### 11. uc10-pipeline: PASS

Figures bound: net_worth -> net_worth. Answered from: net_worth.

Signals fired: uc10-pipeline-column-held x1; uc10-pipeline-net-worth-shown x168.

Signals that cannot run on the loaded data: uc10-pipeline-files-ready cannot run: no reader gives doc.file_rows, doc.loaded_rows, doc.mapping_status.

### 12. uc5-limits: FAIL

Figures bound: single_name_concentration -> concentration. Answered from: concentration, drift_vs_target, single_name_breach.

| Key value | Expected | Got | Recipe |
|---|---|---|---|
| q1 holding | 'Harborview Semiconductor' | "8 rows where portfolio='Evergreen Liquid Book', position_date='2026-09-30', status='real breach'" | single_name_breach |

Signals fired: uc5-limits-breach x8; uc5-limits-no-class x1.

### 13. uc-013-secgaps: PASS

Figures bound: unclassified_holdings -> identifier_gaps. Answered from: identifier_gaps.

Signals fired: uc-013-secgaps-found x1.

Signals that cannot run on the loaded data: uc-013-secgaps-completed cannot run: figure identifier_gaps for {'first_row': True} on every row; uc-013-secgaps-over-one-percent cannot run: figure identifier_gaps for {'first_row': True} on every row.

### 14. morning-networth-note: PASS

Figures bound: networth_usd_sgd -> report_total_fx. Answered from: report_ready, report_total_fx.

Signals fired: morning-networth-note-today x1.

Signals that cannot run on the loaded data: morning-networth-note-call-uncovered cannot run: recipe cash_after_calls has no column call_amount, due_in_days; morning-networth-note-report-old cannot run: no reader gives doc.days_since_issue.

### 15. uc-015-allowances: FAIL

Figures bound: allowance_due -> allowance_due. Answered from: allowance_due.

| Key value | Expected | Got | Recipe |
|---|---|---|---|
| q1 due_october.Lin Chen | 8000 | 0 | allowance_due |
| q1 due_october.Maya Chen | 6000 | 0 | allowance_due |
| q1 due_october.Ethan Chen | 5000 | 0 | allowance_due |
| q1 due_october.Wen Chen | 4000 | 0 | allowance_due |

Key values not compared (no column answers them yet): q1.unpaid_earlier, q1.total_owed, q1.trust_usd_cash.

Signals fired: uc-015-allowances-unpaid-earlier x1.

Signals that cannot run on the loaded data: uc-015-allowances-approved cannot run: figure cash_by_entity for {'entity': 'doc.entity', 'currency': 'doc.currency'} on every row; uc-015-allowances-cash-short cannot run: figure cash_by_entity for {'entity': 'doc.entity', 'currency': 'doc.currency'} on every row.

### 16. uc-016-schemadrift: FAIL

Figures bound: columns_changed -> columns_changed. Answered from: columns_changed.

| Key value | Expected | Got | Recipe |
|---|---|---|---|
| q1 months_with_old_name | 5 | 6 | columns_changed |

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

### 29. uc-029-closeck: PASS

Figures bound: close_items_done -> close_items_done. Answered from: close_items_done.

Signals fired: uc-029-closeck-item-late x2.

Signals that cannot run on the loaded data: uc-029-closeck-report-can-start cannot run: no reader gives doc.steps; uc-029-closeck-sign-close cannot run: no reader gives doc.steps.

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

Signals fired: uc-033-breachesc-cost-to-cure x8.

Signals that cannot run on the loaded data: uc-033-breachesc-waiver-expired cannot run: no reader gives doc.breach_open, doc.days_past_expiry, doc.expires_on; uc-033-breachesc-waiver-recorded cannot run: no reader gives doc.committee, doc.decided_on, doc.expires_on, doc.outcome, doc.subject_id, doc.title.

### 34. uc-034-prospect: PASS

Figures bound: mandate_fit -> mandate_fit. Answered from: mandate_fit.

Signals fired: uc-034-prospect-screened x1.

Signals that cannot run on the loaded data: uc-034-prospect-class-over cannot run: doc.class_limit_pct on every row.

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

### 38. uc-038-navroll: SIGNAL

Figures bound: nav_rollforward -> nav_rollforward. Answered from: nav_rollforward.

Signals fired: uc-038-navroll-statement x12; uc-038-navroll-ties x10; uc-038-navroll-unexplained x2.

Signal problems: uc-038-navroll-unexplained fires on a clean row (Evergreen Growth I unexplained -12,500 at 2026-09-30).

### 39. uc-039-irr: PASS

Figures bound: fund_irr_tvpi -> fund_irr_tvpi. Answered from: fund_irr_tvpi.

Signals fired: uc-039-irr-by-fund x8.

### 40. uc-040-icmemo: PASS

Figures bound: memo_support -> memo_support. Answered from: memo_support.

Signals fired: uc-040-icmemo-figure-source x2.

### 41. uc-041-commitappr: PASS

Figures bound: commit_check -> commit_check. Answered from: commit_check.

Signals fired: uc-041-commitappr-cash-short x1; uc-041-commitappr-test-not-on-record x1.

### 42. uc4-vs-benchmark: FAIL

Figures bound: active_return -> time_weighted_return. Answered from: time_weighted_return.

| Key value | Expected | Got | Recipe |
|---|---|---|---|
| q1 benchmark_return_pct | 2.7072 | None | time_weighted_return |
| q1 active_pct | 1.4595 | None | time_weighted_return |

Key values not compared (no column answers them yet): q1.equity_index_pct, q1.bond_index_pct.

Signals fired: none.

Signals that cannot run on the loaded data: uc4-vs-benchmark-definition-changed cannot run: no reader gives doc.effective_from, doc.previous_version; uc4-vs-benchmark-index-missing cannot run: doc.benchmark_gap on every row; uc4-vs-benchmark-month cannot run: doc.benchmark_code on every row.

### 43. uc-043-liquidpnl: PASS

Figures bound: liquid_pnl_mtd -> liquid_pnl_mtd. Answered from: liquid_pnl_mtd.

Signals fired: uc-043-liquidpnl-daily x1.

### 44. uc-044-twr: FAIL

Figures bound: twr_periods -> time_weighted_return. Answered from: time_weighted_return.

| Key value | Expected | Got | Recipe |
|---|---|---|---|
| q1 benchmark_since_1_apr_pct | 5.7563 | None | time_weighted_return |

Signals fired: uc-044-twr-flow-timing x5.

Signals that cannot run on the loaded data: uc-044-twr-no-link cannot run: recipe time_weighted_return has no column stated_return_pct; uc-044-twr-periods cannot run: doc.portfolio_return_pct on every row.

### 45. uc-045-reportpack: PASS

Figures bound: report_ready -> report_ready. Answered from: report_ready.

Signals fired: uc-045-reportpack-drafted x1.

### 46. uc-046-attrib: PASS

Figures bound: attribution -> attribution. Answered from: attribution.

Signals fired: uc-046-attrib-effects x21; uc-046-attrib-slide x21.

### 47. uc-047-icpack: FAIL

Figures bound: pack_items -> pack_items. Answered from: pack_items.

| Key value | Expected | Got | Recipe |
|---|---|---|---|
| q1 real_breaches | 1 | 8 | pack_items |

Signals fired: uc-047-icpack-assembled x1.

Signals that cannot run on the loaded data: uc-047-icpack-open-late cannot run: no reader gives doc.days_to_committee; uc-047-icpack-section-done cannot run: recipe pack_items has no column done.

### 48. uc-048-policyupd: FAIL

Figures bound: limit_changes -> limit_changes. Answered from: limit_changes.

| Key value | Expected | Got | Recipe |
|---|---|---|---|
| q1 max_single_name_pct_by_month_end.2026-04-30 | 6.13 | 7.17 | limit_changes |
| q1 max_single_name_pct_by_month_end.2026-05-31 | 5.89 | 7.3 | limit_changes |
| q1 max_single_name_pct_by_month_end.2026-06-30 | 5.74 | 7.34 | limit_changes |
| q1 max_single_name_pct_by_month_end.2026-07-31 | 5.71 | 7.28 | limit_changes |
| q1 max_single_name_pct_by_month_end.2026-08-31 | 5.71 | 7.35 | limit_changes |
| q1 max_single_name_pct_by_month_end.2026-09-30 | 5.75 | 7.08 | limit_changes |
| q1 proposed_limit | 6 | "0 rows where approval_status='proposed', is_latest=1" | limit_changes |

Key values not compared (no column answers them yet): q1.breaches_at_6_pct.

Signals fired: none.

Signals that cannot run on the loaded data: uc-048-policyupd-approved cannot run: no reader gives doc.decided_on, doc.effective_from, doc.outcome.

### 49. uc-049-feedrag: SIGNAL

Figures bound: fee_drag -> fee_drag. Answered from: fee_drag.

Signals fired: uc-049-feedrag-above-terms x1; uc-049-feedrag-share x4.

Signal problems: uc-049-feedrag-above-terms fires on a clean row (Bluewater Capital).

### 50. uc-050-feeinv: PASS

Figures bound: invoice_variance -> invoice_variance. Answered from: invoice_variance.

Signals fired: uc-050-feeinv-above-schedule x1; uc-050-feeinv-arrives x3; uc-050-feeinv-matches x4.

