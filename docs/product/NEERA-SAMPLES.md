# Neera sample files (what a family office hands over)

Synthetic. Built from the Neera warehouse by `tools/make_samples_neera.py`; live copy in `data/neera/landing/<source>/`, restorable copy in `tools/samples/neera/`. Periods run September 2025 to September 2026 (13 month ends). Amounts in the file's own currency unless the column says `_sgd`.

| Source folder and file | Owner | What it is |
|---|---|---|
| `custodian_positions/positions_<YYYY-MM>.csv` (13 files) | Operations (custodian statements) | Month-end holdings across the three custodians, 40 rows a month |
| `custodian_transactions/transactions_2025-10_to_2026-09.csv` | Operations | Buys and sells, 120 rows |
| `custodian_fees/fee_schedule.csv` | Operations | Fee rate per custodian |
| `custodian_fees/invoices_2025-09_to_2026-09.csv` | Operations | One custody invoice per custodian per month |
| `bank_cash/cash_balances_2025-09_to_2026-09.csv` | Treasury | Month-end balance of each of the eight bank accounts |
| `ledger/trial_balance_2025-09_to_2026-09.xlsx` | Finance | Two sheets: `Trial balance`, `Chart of accounts` |
| `benchmark/benchmark_prices_2025-09_to_2026-09.csv` | Investment office | Month-end levels of three reference indices |
| `clients/client_list.csv` | Principals' office | The family members who read the report |

## Columns

**positions_YYYY-MM.csv**: `holding_id` (H001 to H040, ties to the holdings master), `holding_name`, `custodian_id` (C1 Harbourline Custody, C2 Meridian Trust Services, C3 Strait Custodial Bank), `quantity` (units held), `price_local` (price per unit in the holding's currency), `currency`, `market_value_local` (quantity times price, local currency), `valuation_date` (date of the price; private funds carry an older date, so the value is stale).

**transactions**: `trade_date`, `holding_id`, `custodian_id`, `side` (buy or sell), `units`, `price_local` (month-end price used for the trade), `currency`, `gross_amount_local` (units times price).

**fee_schedule**: `custodian_id`, `custodian_name`, `tier` (flat, or "below 400m": the rate that applies while assets under custody stay below the bound), `rate_bp_annual` (basis points a year on assets under custody), `assets_to_sgd` (upper bound of the tier, blank when flat), `effective_from`.

**invoices**: `invoice_no`, `custodian_id`, `period`, `issue_date`, `days` (days billed), `mean_assets_sgd` (average assets under custody), `fee_sgd`, `other_charges_sgd`, `invoice_total_sgd`.

**cash_balances**: `period`, `account_id` (B01 to B08), `entity_id` (E01 to E04), `currency`, `month_end_balance`, `basis` (`statement` from the bank; `daily` when taken from the daily balance file).

**trial_balance** (sheet `Trial balance`): `period`, `account_code`, `account_name`, `debit_sgd`, `credit_sgd`. Debits equal credits in every period; account 3900 is the balancing line. Sheet `Chart of accounts`: `account_code`, `account_name`, `type`, `reporting_use`.

**benchmark_prices**: `period`, `index_code` (NEERA-EQ equities, NEERA-BOND bonds, NEERA-CASH cash), `close_level` (September 2025 = 1000), `currency` (SGD).

**client_list**: `reader_id`, `name`, `relation`, `generation` (senior or next), `receives_report` (True or False).

## Quirks planted

1. **Renamed column mid-year**: from `positions_2026-02.csv` onwards `price_local` is called `unit_price`.
2. **Missing currency column**: `positions_2026-01.csv` has no `currency`; it must be taken from the holdings in the other months.
3. **Duplicate row**: `positions_2025-12.csv` lists H006 (Highgate Technology Ordinary) twice, identical.
4. **Cash basis changes**: `bank_cash` rows are `statement` up to 2026-06 and `daily` from 2026-07.
5. **Stale private-fund prices**: private market funds (H027 to H036) carry `valuation_date` older than the month end.
6. **Tiered fee**: only C2 has a tiered rate (9.5 bp while below 400 million); C1 and C3 are flat.
7. **Foreign currency ledger**: the trial balance is in SGD while positions and cash are in local currency; conversion needs the month-end rate, which is not in these files.
8. **Benchmark is not tied to holdings**: the three indices are reference levels only; weights are not supplied and must come from the investment policy.
