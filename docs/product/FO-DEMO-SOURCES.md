# Demo family office: structured sources

Synthetic files for the demo family office (second 1.0 company), built by `python tools/make_samples_fo_demo.py [company_id] [company_name]`. They land in `data/<company>/landing/<folder>/` with a restorable copy in `local/samples/<company>/`. Period 1 September 2025 to 30 September 2026; base currency SGD; all names and providers are fictional. Planted exceptions and their exact values: `FO-DEMO-ANSWER-KEY.md` (outside the product).

Use cases refer to the PRD (`FAMILY-OFFICE-PRD.md`, section 9): P1-1 ingestion, P1-2 security master and ledger, P1-3 positions, cash, valuation and net worth, P1-4 reconciliation and exceptions, P1-5 TWR, MWR and benchmark, P1-6 drill-through; P2-1 private investments, P2-2 allocation drift, P2-3 attribution, P2-4 risk and concentration, P2-5 liquidity, P2-6 fees, income and tax lots. Phase 0 items: P0-1 inventory, P0-2 benchmark policy, P0-3 treatment of fees and missing prices, P0-4 access roles.

## Shape

- Entities: E1 family trust (accounts NC-001, NC-002, HB-SGD-01, HB-USD-01), E2 holding company owned by E1 (NC-003, LG-SGD-01, LG-HKD-01).
- One custodian, Northgate Custody, three accounts; two banks, Harbour Bank (HB) and Lion Gate Bank (LG), four accounts.
- 45 listed securities SEC001 to SEC045 (20 equities, 12 bonds, 8 funds, 5 money market funds) in SGD, USD, EUR, HKD; four private funds PF01 to PF04; three indices STR50, CWE, AGB; one blended benchmark for portfolio PF-MAIN.
- Every security is held in one account. The accounts were onboarded on 1 September 2025 by in-kind `transfer` rows (holdings) and cash `transfer` rows, so position quantity = sum of buy, sell and transfer quantities in the ledger, and custodian cash = sum of settled `net_amount`.
- Conventions: bond quantities are units of 100 nominal (quantity x price = market value for every row); FX `rate` is SGD per one unit of `base_currency`; benchmark levels are in SGD; amounts in the account currency unless the column says base.

## Folders

| Folder | File pattern | Columns | Owner | Frequency | Use cases |
|---|---|---|---|---|---|
| `custodian_positions` | `custodian_positions_YYYY-MM-DD.csv` (13 month-ends on the last trading day, every trading day of August and September 2026, plus a mid-month statement of 15 July 2026) | as_of, account_id, security_id, isin, quantity, price_local, currency, market_value_local, market_value_base, cost_basis_base | Grace Ward | daily (last two months), month-end | P1-1, P1-3, P1-4, P1-6 |
| `custodian_transactions` | `custodian_transactions_YYYY-MM.csv` | trade_date, settle_date, account_id, security_id, type (buy, sell, dividend, interest, fee, transfer, call, distribution), quantity, price, gross_amount, net_amount (signed, account currency), currency, reference | Grace Ward | monthly | P1-2, P1-4, P1-5, P2-1 |
| `custodian_cash` | `custodian_cash_YYYY-MM.csv` | as_of, account_id, currency, balance (settled), available (after pending settlements) | Grace Ward | monthly | P1-3, P1-4, P2-5 |
| `custodian_income` | `custodian_income_YYYY-MM.csv` | pay_date, account_id, security_id, kind (dividend, coupon, interest), gross, withholding, net, currency, reference (= ledger reference) | Grace Ward | monthly | P2-6, P1-5 |
| `custodian_fees` | `custodian_fees_YYYY-MM.csv` (invoice month) | invoice_date, invoice_id (= ledger reference of the fee row), account_id, fee_type (custody, management, performance, transaction), amount, currency, period_from, period_to | Grace Ward | monthly invoices | P2-6, P0-3 |
| `custodian_tax_lots` | `custodian_tax_lots_YYYY-MM-DD.csv` (quarter-ends) | as_of, account_id, security_id, lot_id, open_date, quantity, cost_base (lot total, SGD), cost_local (lot total), currency | Harvey Rowley | quarterly | P2-6 |
| `custodian_corporate_actions` | `custodian_corporate_actions_2026-09-30.csv` | ex_date, security_id, action (dividend, split, name_change), ratio_or_amount, note | Grace Ward | one file | P1-2, P2-6 |
| `bank_balances` | `bank_balances_YYYY-MM.csv` (calendar days) | as_of, bank_account_id, entity_id, currency, balance | Grace Ward | daily, one file per month | P1-3, P2-5 |
| `bank_transfers` | `bank_transfers_YYYY-MM.csv` | value_date, bank_account_id, direction (in, out), counterparty, amount, currency, memo | Grace Ward | monthly | P1-3, P2-5 |
| `market_prices` | `market_prices_YYYY-MM.csv` (trading days) | price_date, security_id, isin, close_local, currency, source_code (EXCH, EVAL, NAV) | Daniel Kerr | daily, one file per month | P1-1, P1-3, P1-4 |
| `fx_rates` | `fx_rates_YYYY-MM.csv` | rate_date, base_currency, quote_currency (SGD), rate | Daniel Kerr | daily, one file per month | P1-1, P1-3 |
| `security_master` | `security_master_2026-09-30.csv` | security_id, isin, name, asset_class (equity, fixed_income, fund, cash_equivalent, private), sub_class, sector, geography, currency, manager, issuer, listed (yes, no) | Daniel Kerr | one file | P1-2, P2-3, P2-4 |
| `benchmark_levels` | `benchmark_levels_YYYY-MM.csv` | level_date, index_code, level, total_return_index | Daniel Kerr | daily, one file per month | P1-5 |
| `benchmark_blend` | `benchmark_blend_2025-09-01.csv` | portfolio_id, index_code, weight, effective_from | Meredith Shaw | one file | P0-2, P1-5 |
| `target_allocation` | `target_allocation_2025-09-01.csv` | portfolio_id, asset_class, target_weight, min_weight, max_weight, effective_from | Meredith Shaw | one file | P2-2 |
| `manual_adjustments` | `manual_adjustments_2026-09-30.xlsx`, sheets `adjustments` (adjustment_id, as_of, account_id, security_id, field, old_value, new_value, reason_code, requested_by) and `approvals` (adjustment_id, approved_by, approved_at, status) | as named | Grace Ward (requests), Meredith Shaw (approves) | one workbook | P1-4, P1-6 |
| `private_portal` | `private_portal_YYYY-MM-DD.csv` (quarter-ends to 30 June 2026, downloaded about 45 days later) | fund_id, name, commitment, called_to_date, distributed_to_date, nav, nav_date, currency, ownership_pct | Daniel Kerr | quarterly | P2-1, P2-5 |
| `entities` | `entities_2026-09-30.csv` | entity_id, name, kind (trust, holding), beneficial_owners, custodian_accounts, bank_accounts (semicolon lists) | Harvey Rowley | one file | P0-1, P1-3 |

## Ingestion metadata

Each folder has `_manifest.json`: `{source_system, files: [{name, effective_date, received_at, version}]}`. Daily and monthly files arrive the next business day at 06:30 (+08:00); private portal files about 45 days after the quarter; policy files on their effective date. All versions are 1. Validation status is the platform's to record.

## How the numbers tie

- Positions: quantity x price_local = market_value_local; x the day's FX = market_value_base; cost_basis_base = sum of the open tax lots' cost_base.
- Cash: every dividend, coupon and interest row in `custodian_income` and every fee invoice in `custodian_fees` is one ledger row with the same reference; buys and sells settle T+2; transfers with a blank security_id mirror `bank_transfers` rows (counterparty "Northgate Custody <account>").
- Private funds: capital calls and distributions are ledger rows (security_id PF01 to PF04) paid from NC-001 (SGD) or NC-002 (USD, EUR); `called_to_date` and `distributed_to_date` in each portal file include them; NAV rolls forward quarterly.
- Corporate actions: the two-for-one split of SEC008 on 15 April 2026 is booked as a `transfer` of the bonus shares (reference CA-0001); SEC004 changed its name on 2 March 2026 (the master holds the new name).
- The ten planted exceptions are the only places these ties break on purpose.
