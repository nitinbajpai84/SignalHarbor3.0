# Company model additions for the top 50 use cases

Owner: the model steward (one decision-maker, so eight builders do not each invent tables). Decided 17 Oct 2026. Every decision is logged in `docs/v3/ASSUMPTIONS.md` as A11 onward, so Nitin can reverse it.

## The rule

A table joins the core only if it is a **source fact** the office receives or records: something that arrives in a file, a statement or a minute, or that a person records, and that no existing table can hold. A **derived** thing (a balance by bank, mandate fit, renewals due, net worth after debt) is a figure: a recipe and a figure record, never a table. Items needed only by cards outside the top 50 wait (class d) so the core stays thin.

## The 86 items in the "new things needed" list

| Class | Items | What happens |
|---|---|---|
| (a) source-fact core table | 8 | 6 new tables (2 items merge into `bank_accounts`) |
| (b) derived figure | 39 | 38 recipe stubs (`twr_periods` merges into `time_weighted_return`) |
| (c) already covered | 14 | no new table; the existing table or recipe is named |
| (d) out of scope for now | 25 | 11 tables, 13 recipes that need them, 1 skill |
| **Total** | **86** | |

## New core tables (6), all additive

Every table has the same organisation and load columns as `fx_confirmations`: `id`, `organization_id`, `source_record_id`, `source_document_id`, `source_page`, `received_at`, `recorded_at`, `supersedes_<table>_id`. A change is a new row that supersedes the old one. Defined in `docs/v2/evidence-to-action-mvp.dbml` (group `office_records`) and `.duckdb.sql`.

| Table | Own columns |
|---|---|
| `bank_accounts` | holder_kind (office or payee), legal_entity_id, instrument_id, holder_name, account_purpose, bank_name, account_ref (masked), currency, cash_instrument_id, status, opened_on, closed_on, verified_on, verified_by |
| `credit_facilities` | facility_ref, legal_entity_id, lender, facility_type, currency, limit_amount, drawn_amount, interest_rate, rate_basis, maturity_date, collateral, as_at, status |
| `family_members` | member_name, relationship, legal_entity_id, user_id, allowance_amount, allowance_currency, allowance_frequency, allowance_from, allowance_to, paid_from_portfolio_id, active_from, active_to |
| `vendor_contracts` | vendor_name, service, contract_ref, legal_entity_id, owner_user_id, start_date, end_date, next_renewal_date, auto_renews, notice_days, annual_cost, currency, status |
| `deal_pipeline` | deal_name, manager_name, strategy, asset_class, instrument_id, target_commitment, currency, stage, stage_on, owner_user_id |
| `committee_decisions` | committee, decided_on, title, subject_type, subject_id, outcome, conditions, amount, currency, recorded_by |

Three columns are added to existing tables (A18): `cash_movements.bank_account_id`, `cash_movements.counterparty_portfolio_id`, `approvals.cash_movement_id`. New movement types `payment`, `transfer`, `allowance` are named in the column note. Existing offices get all of this on next start through `reload_core`; `tests/v1/test_v3_model_tables.py` drops the tables and columns from an old office and checks they come back with its data intact.

## `expected_statements` re-judged (A19)

Under the rule it is half a source fact. A schedule a person confirms, or one the fund terms state, is something the office records. A schedule inferred from the cadence of statements already received is derived. **It stays**: the code (`v3_expected`), the `missing_statements` recipe and the tests are built on it, the row says how it was decided (`source`), and a stored expectation answers "what did we expect, and when did we know". Narrowed rule: new generators must not write inferred rows beyond the cadence rule already there; any further expectation is a figure. Reverse it by moving the schedule into a recipe over `extracted_fields` (reporting_frequency, statement_due_days) and the statements received.

## Conventions the builders share

- **Fund terms** are `extracted_fields` rows with these field names: `reporting_frequency`, `statement_due_days`, `management_fee_rate`, `performance_fee_rate`, `hurdle_rate`, `fee_basis`, `notice_days`, `lockup_months`, `redemption_frequency`, `gate_pct`. Rates are fractions. A terms spreadsheet is read as a document, not a table.
- **Policy limits and office rules** are `business_rules` (rule_type `policy`, `tolerance` or `threshold`) with the numbers in `rule_versions.parameters`, signed through `approvals.rule_version_id`. Allocation targets use rule codes `allocation_<asset_class>` with `{"target_pct", "min_pct", "max_pct"}`; the private-markets budget is `allocation_private_markets`; a bank limit is `bank_limit_<bank>` with `{"limit", "currency"}`; the payment buffer and approval limits are `cash_buffer` and `payment_approval`.
- **A notice** is a `documents` row (type `capital_call_notice` or `distribution_notice`) with `extracted_fields` and a `cash_movements` row (`confirmation_status` noticed, then confirmed when recorded; `notice_kind`, `due_date`, `commitment_id`). "Notices logged and not recorded" = noticed rows.
- **A payment** is a `cash_movements` row of type `payment`, status `expected` until released; each approval is an `approvals` row with `cash_movement_id`.
- **A transfer between entities** is two `cash_movements` rows of type `transfer`, one per portfolio, each naming the other in `counterparty_portfolio_id`.
- **A balance by bank** is the position snapshots of the account's cash instrument (`bank_accounts.cash_instrument_id`).
- **A close checklist step** is an `exceptions` row of type `close_item` (owner, due_at, resolved_at) until a table is justified (A27).
- Recipe stubs: `recipes/<domain>.yaml`, `status: stub`, `sql: null`. The loader skips a stub; its owner fills in `sql`, `grain`, `measure`, `columns` and `tie_out` and removes `status: stub`.

## All 86 items

## (a) Source-fact core table (8)

| Item | Cards (top 50 in bold) | Becomes | Why |
|---|---|---|---|
| `table:bank_accounts` | **6**, **10**, 94 | bank_accounts (new) | A source fact: the account a bank statement, account opening or payee record names. One table for the office's own accounts and the payee accounts on file (holder_kind). |
| `table:committee_decisions` | **33**, **40**, **47** | committee_decisions (new) | What the committee decided is a fact the office records from the minutes; approvals hold one person's sign-off, not a committee outcome. |
| `table:counterparties` | **10** | merged into bank_accounts | A bank is a name on an account (bank_name); the per-bank limit is a signed rule, not a table. |
| `table:credit_facilities` | **17** | credit_facilities (new) | A loan agreement or lender statement is a source fact with terms (limit, rate, maturity) that no position or instrument column holds. |
| `table:deal_pipeline` | **34**, 77 | deal_pipeline (new) | The office's own record of funds under review and their stage; no other table holds a deal before it is an instrument. |
| `table:family_members` | **15**, 87, 100 | family_members (new) | The people the office pays or reports to, and their allowance schedule, arrive as a schedule file; nothing else holds a person who is not a user. |
| `table:standing_instructions` | **5** | merged into bank_accounts | The account on file for a payee is a payee row of bank_accounts; a change is a superseding row with the call-back in verified_on. |
| `table:vendor_contracts` | **30** | vendor_contracts (new) | A signed contract with renewal date, notice days and cost is a source fact from the contract; renewals due is a figure. |

## (b) Derived figure: a recipe, no table (39)

| Item | Cards (top 50 in bold) | Becomes | Why |
|---|---|---|---|
| `table:instrument_identifiers_gaps` | **13** | recipe identifier_gaps | A gap is an absence found by comparing instruments with instrument_identifiers: derived, not received. |
| `figure:private_markets_budget` | **7** | recipe private_markets_budget | Budget is the signed policy limit times net worth, less commitments: derived. |
| `recipe:allocation` | **31** | recipe stub in recipes/hold.yaml | Market value shares by class and entity: derived. |
| `recipe:allowance_due` | **15** | recipe stub in recipes/family.yaml | Schedule less paid: derived from family_members and cash movements. |
| `recipe:attribution` | **46** | recipe stub in recipes/report.yaml | Brinson parts: derived. |
| `recipe:bank_details_changed` | **5** | recipe stub in recipes/cash.yaml | A comparison of the notice with the payee account on file: derived. |
| `recipe:called_to_date` | **2** | recipe stub in recipes/cash.yaml | Calls to a date less nothing else: derived from confirmed call movements and the commitment. |
| `recipe:cash_after_calls` | **4** | recipe stub in recipes/cash.yaml | Cash by entity less calls due less the signed buffer: derived. |
| `recipe:cash_by_bank` | **10** | recipe stub in recipes/cash.yaml | Balances summed by bank, against a signed limit: derived. |
| `recipe:cash_forecast` | 72 | recipe stub in recipes/cash.yaml | Opening cash plus expected movements: derived. |
| `recipe:close_items_done` | **29** | recipe stub in recipes/operate.yaml | Counts of close steps, kept as exceptions of type close_item: derived. |
| `recipe:commitments_by_fund` | **7** | recipe stub in recipes/invest.yaml | Sums of commitments, calls and unfunded by fund: derived. |
| `recipe:currency_exposure` | 64 | recipe stub in recipes/hold.yaml | Value by currency, before and after forwards: derived. |
| `recipe:ddq_compare` | **35** | recipe stub in recipes/invest.yaml | Answers matched by topic from extracted fields: derived. |
| `recipe:distribution_gap` | **37** | recipe stub in recipes/cash.yaml | Notice less matching bank credit: derived. |
| `recipe:expected_distributions` | 71 | recipe stub in recipes/invest.yaml | Noticed distributions plus a labelled run rate: derived. |
| `recipe:fee_drag` | **49** | recipe stub in recipes/invest.yaml | Fees paid over gross gain: derived. |
| `recipe:fund_irr_tvpi` | **39** | recipe stub in recipes/invest.yaml | IRR and TVPI from dated flows and the latest value: derived. |
| `recipe:funding_plan` | **18** | recipe stub in recipes/cash.yaml | A choice of entity from cash cover: derived. |
| `recipe:fx_mtm` | 62 | recipe stub in recipes/operate.yaml | Mark of open forwards: derived. |
| `recipe:fx_required` | **6** | recipe stub in recipes/cash.yaml | Shortfall times the planning rate: derived. |
| `recipe:income_forecast` | 68 | recipe stub in recipes/hold.yaml | A trailing run rate on current holdings: derived. |
| `recipe:intercompany_balance` | **28** | recipe stub in recipes/cash.yaml | Transfers out less in per pair: derived. |
| `recipe:liquid_pnl_mtd` | **43** | recipe stub in recipes/hold.yaml | Value change less net trades: derived. |
| `recipe:liquidity_ladder` | 54 | recipe stub in recipes/cash.yaml | Value bucketed by days to cash: derived. |
| `recipe:manager_score` | 76 | recipe stub in recipes/invest.yaml | A weighted score of other figures: derived. |
| `recipe:nav_rollforward` | **38** | recipe stub in recipes/hold.yaml | Opening plus flows plus gain equals closing: derived. |
| `recipe:net_worth_after_debt` | **17** | recipe stub in recipes/hold.yaml | Net worth less drawn facilities: derived. |
| `recipe:networth_walk` | 75 | recipe stub in recipes/report.yaml | Start to now by cause: derived. |
| `recipe:payment_batch` | **8** | recipe stub in recipes/cash.yaml | Payments grouped by approval state: derived. |
| `recipe:position_break` | 56 | recipe stub in recipes/operate.yaml | Custodian against administrator: derived. |
| `recipe:price_gap_pct` | 57 | recipe stub in recipes/operate.yaml | Gap between two price series: derived. |
| `recipe:renewals_vendors` | **30** | recipe stub in recipes/office.yaml | Contracts inside the renewal window: derived from vendor_contracts. |
| `recipe:source_quality` | 61 | recipe stub in recipes/operate.yaml | Quality shares per source: derived. |
| `recipe:time_weighted_return` | **42** | recipe stub in recipes/report.yaml | Chain-linked returns and active return: derived. |
| `recipe:twr_periods` | **44** | merged into time_weighted_return | Duplicate of time_weighted_return (same chain-linked return over month, QTD, YTD, 1y); merged into it. |
| `recipe:unsettled_trades` | 58 | recipe stub in recipes/operate.yaml | Settlement date passed and not settled: derived. |
| `recipe:value_age_days` | **21** | recipe stub in recipes/hold.yaml | Date arithmetic on valuations: derived. |
| `recipe:watch_flags` | 53 | recipe stub in recipes/invest.yaml | Flags from late, restated or changed evidence: derived. |

## (c) Already covered (14)

| Item | Cards (top 50 in bold) | Becomes | Why |
|---|---|---|---|
| `table:access_grants` | 91, 92, 100 | access_group_memberships + access_group_scopes | Who may see what is a group membership (granted_at, granted_by, expires_at) over entity scopes; a leaver is an expired membership. |
| `table:audit_requests` | **24** | source_records + documents + metric_evidence | The auditor's request list is a loaded file (one source record per item); the trace to file and page is metric_evidence. |
| `table:custody_positions` | 56 | position_snapshots | A custodian position is a position snapshot from the custodian's source system; the break is a figure (position_break). |
| `table:expected_statements_schedule` | **19**, 93 | expected_statements | Same thing as the table already in the model (A2); onboarding a manager (93) adds rows to it. |
| `table:fee_charges` | **49** | cash_movements | A fee paid is a cash movement of type fee (and a transaction when the administrator books it); fees stated on a statement are extracted_fields. |
| `table:fee_schedules` | **49** | extracted_fields | The fee rates are fund terms, read from the fee schedule or the LPA (A21 field names). |
| `table:fund_notices` | **1**, **2**, **37** | documents + extracted_fields + cash_movements | A notice is a document; its fields are read with page and line; the call or distribution is a cash_movements row (noticed, then confirmed; notice_kind, due_date, commitment_id exist). |
| `table:fund_terms` | 78 | extracted_fields | Terms are read from the fund's documents with page and review status (A21 lists the field names); a table would copy them. |
| `table:intercompany` | **28** | cash_movements | A transfer between two entities is two cash_movements rows of type transfer naming each other (new counterparty_portfolio_id); the balance is a figure. |
| `table:office_rules` | **4** | business_rules + rule_versions | A signed office rule (the 250,000 cash buffer, the two-approval limit) is exactly what these hold, with its parameters. |
| `table:payments` | **4**, **8** | cash_movements + approvals | A payment is a cash_movements row of type payment (expected until released); its approvals are approvals rows via the new cash_movement_id; the payee account is the new bank_account_id. |
| `table:policy_limits` | **32**, **48** | business_rules + rule_versions | Allocation targets, bands and single-name limits are signed policy: one rule per limit, the numbers in rule_versions.parameters, signed through approvals (A20). |
| `table:prices_second_source` | 57 | market_observations | A second price is another series_key from another provider in market_observations. |
| `table:settlements` | 58 | transactions | transactions has settlement_date and status; unsettled trades is a figure. |

## (d) Out of scope for now (25)

| Item | Cards (top 50 in bold) | Becomes | Why |
|---|---|---|---|
| `table:corporate_actions` | 55 | later: corporate_actions | A real source fact (custodian notices) but only card 55 needs it, outside the top 50. income_forecast runs on cash received until then. |
| `table:fund_holdings` | 69 | later: fund_holdings | What a fund owns is received (manager look-through reports), but only card 69 needs it, outside the top 50. |
| `table:grants` | 85, 86 | later: grants | Philanthropy is outside the top 50 (cards 85, 86). A grant paid is a cash movement; the award and budget are the part a table would add. |
| `table:insurance_policies` | 52 | later: vendor_contracts or its own table | Card 52 only, outside the top 50. A policy is a contract with a renewal, so vendor_contracts may take it with a kind column. |
| `table:kyc_records` | 93, 94, 97 | later: kyc_records | Cards 93, 94, 97 only, outside the top 50. Holds personal-identity documents, so it needs an access decision first. |
| `table:office_expenses` | 73, 90 | later: cash_movements of the office entity | Cards 73, 90 only, outside the top 50. Expenses are probably cash movements of type expense; decide when built. |
| `table:real_assets` | 65 | later: real_assets | Card 65 only, outside the top 50. |
| `table:staff_payroll` | 81 | later: staff_payroll | Card 81 only, outside the top 50; personal pay data, so it needs an access decision first. |
| `table:succession_plan` | 87 | later: succession_plan | Card 87 only, outside the top 50; sensitive family data. |
| `table:tax_lots` | 67 | later: tax_lots | Card 67 only, outside the top 50. Lots come from custodian statements. |
| `table:tax_obligations` | 83 | later: tax_obligations | Card 83 only, outside the top 50. |
| `recipe:actions_next_14d` | 55 | later | Needs corporate_actions (not built), card 55 outside the top 50. |
| `recipe:automation_score` | 96 | later | Needs step durations and failures per process step, which the model does not hold; card 96 outside the top 50. |
| `recipe:cash_runway` | 73 | later | Needs office expenses (not built); card 73 outside the top 50. |
| `recipe:estate_cash_need` | 88 | later | Needs succession and tax data (not built); card 88 outside the top 50. |
| `recipe:grants_used` | 85 | later | Needs grants (not built); card 85 outside the top 50. |
| `recipe:lookthrough_exposure` | 69 | later | Needs fund_holdings (not built); card 69 outside the top 50. |
| `recipe:office_cost` | 90 | later | Needs office expenses (not built); card 90 outside the top 50. |
| `recipe:payroll_total` | 81 | later | Needs staff_payroll (not built); card 81 outside the top 50. |
| `recipe:real_asset_value` | 65 | later | Needs real_assets (not built); card 65 outside the top 50. |
| `recipe:renewals_due` | 52 | later | Needs insurance policies (not built); card 52 outside the top 50. |
| `recipe:tax_due` | 83 | later | Needs tax_obligations (not built); card 83 outside the top 50. |
| `recipe:tax_estimate` | 84 | later | Needs tax data (not built); card 84 outside the top 50. |
| `recipe:unrealised_gain` | 67 | later | Needs tax_lots (not built); card 67 outside the top 50. |
| `skill:read-capital-call-notice` | **1** | skills catalogue, not the model | A reader for one PDF layout; not a model item. The builder of card 1 writes it like the FX confirmation layout in v3_pdf. |

## Not on the list, noticed on the way

The cards also use figures that nobody listed as new and that no recipe covers yet: `calls_due`, `drift_vs_target`, `cost_to_cure`, `mandate_fit`, `networth_usd_sgd`, `memo_support`, `pack_items`. Their builders add a recipe to their own domain file when the card needs one; the list names no table for them.

## Top 50 cards and what they now have

Every top-50 card has a home for each thing it needs. Four things to know, two of them shortcuts Nitin may not want:

- **Card 1** needs only `fund_notices` (covered) and the PDF reader skill (not a model item). Nothing in the model is missing; the reader is the builder's work.
- **Card 29 (close checklist)** has no table: its steps are `exceptions` of type `close_item` (A27). If Nitin wants a checklist template with steps that repeat each month, that is a new source-fact table.
- **Card 24 (auditor sample)** keeps the auditor's request list as source records of the loaded file and traces with `metric_evidence`; no request table (A22).
- **Cards 4 and 8 (payments)** write `cash_movements`, whose `source_record_id` and `portfolio_id` are required; a payment made in Harbor needs a source record for the act of recording it, as the FX confirmations do.
