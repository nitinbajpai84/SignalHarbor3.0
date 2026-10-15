# Ardmore 1.0 demo workspace: data for the PRD use cases (7 October 2026, late)

Nitin's product requirements document for a family office data platform (uploaded 7 Oct; copy at `docs/product/FAMILY-OFFICE-PRD.md`) lists the sources, the canonical model and the phase 1 and 2 use cases. A second 1.0 company, **Ardmore** (`ardmore-1`), gets synthetic data that lets every phase 0/1 use case and the phase 2 reports be walked in the product as a demo. Neera stays the functional test company.

Rules: synthetic data only; the company name appears only inside `data/` and `local/` (both gitignored), never in `tools/` or `docs/` file names or code; British spelling; no vendor or model names (custodians, banks, index providers are fictional: "Northgate Custody", "Harbour Bank", "Straits 50 index"); pronouns they/them unless the roster states otherwise; no Claude attribution anywhere.

## Cards

### D3 Structured sources (the PRD's section 7, P0 rows plus the P1 private portal)
Generator `tools/make_samples_fo_demo.py` (company id and name are arguments; defaults `ardmore-1`, "Ardmore"), idempotent, writing to `data/<company>/landing/<source>/` and a restorable copy to `local/samples/<company>/` (gitignored). Period: 1 September 2025 to 30 September 2026, **daily** where the PRD says daily. One folder per source, file names dated, CSV (one XLSX where the PRD mentions spreadsheets):

| Folder | Files | Columns (at least) |
|---|---|---|
| `custodian_positions` | one per month-end plus every trading day of the last two months | as_of, account_id, security_id, isin, quantity, price_local, currency, market_value_local, market_value_base, cost_basis_base |
| `custodian_transactions` | monthly | trade_date, settle_date, account_id, security_id, type (buy/sell/dividend/interest/fee/transfer/call/distribution), quantity, price, gross_amount, net_amount, currency, reference |
| `custodian_cash` | monthly | as_of, account_id, currency, balance, available |
| `custodian_income` | monthly | pay_date, account_id, security_id, kind (dividend/interest/coupon), gross, withholding, net, currency |
| `custodian_fees` | monthly invoices | invoice_date, account_id, fee_type (custody/management/performance/transaction), amount, currency, period_from, period_to |
| `custodian_tax_lots` | quarterly | as_of, account_id, security_id, lot_id, open_date, quantity, cost_base, cost_local, currency |
| `custodian_corporate_actions` | one file | ex_date, security_id, action (split/dividend/merger/name_change), ratio_or_amount, note |
| `bank_balances` | daily, one file per month | as_of, bank_account_id, entity_id, currency, balance |
| `bank_transfers` | monthly | value_date, bank_account_id, direction, counterparty, amount, currency, memo |
| `market_prices` | daily, one file per month | price_date, security_id, isin, close_local, currency, source_code |
| `fx_rates` | daily, one file per month | rate_date, base_currency, quote_currency, rate |
| `security_master` | one file | security_id, isin, name, asset_class, sub_class, sector, geography, currency, manager, listed (yes/no) |
| `benchmark_levels` | daily, one file per month | level_date, index_code, level, total_return_index |
| `benchmark_blend` | one file | portfolio_id, index_code, weight, effective_from |
| `target_allocation` | one file | portfolio_id, asset_class, target_weight, min_weight, max_weight, effective_from |
| `manual_adjustments` | one XLSX, sheets `adjustments`, `approvals` | adjustment_id, as_of, account_id, security_id, field, old_value, new_value, reason_code, requested_by / approved_by, approved_at, status |
| `private_portal` | quarterly | fund_id, name, commitment, called_to_date, distributed_to_date, nav, nav_date, currency, ownership_pct |
| `entities` | one file | entity_id, name, kind (trust/holding/individual), beneficial_owners, custodian_accounts, bank_accounts |

Shape: two legal entities, three custodian accounts at one custodian, four bank accounts at two banks, about 45 listed securities across equities, bonds, funds and cash equivalents in SGD, USD, EUR, HKD, four private funds, three indices and one blended benchmark, target allocation with ranges. Base currency SGD. Numbers must be internally consistent (positions × prices ≈ market value; cash moves with transactions; income lands in cash; fees drawn from cash; NAV updates quarterly).

**Planted truths (the PRD's exception list), each with an exact answer in `docs/product/FO-DEMO-ANSWER-KEY.md` (outside the product):**
1. A reconciliation break: on 15 July 2026 the custodian position quantity of one security differs from the transaction ledger by exactly one trade that is missing from the transactions file.
2. A missing price: one security has no price on 3 and 4 August 2026.
3. An unknown security: the positions file of 30 June 2026 holds a security_id absent from the security master.
4. A duplicate transaction on 12 December 2025.
5. A stale file: `bank_balances` for one account stops on 20 September 2026.
6. An out-of-balance cash account on 31 March 2026 (custodian cash vs sum of transactions, by a known amount).
7. A stale private valuation: one fund's NAV date is 31 December 2025 while the others are 30 June 2026.
8. Allocation drift: equities exceed their max weight from May 2026 onwards.
9. A single-issuer concentration above 10 % from February 2026.
10. A performance fact: the portfolio's time-weighted return for Q2 2026 and its benchmark-relative figure, computed by the generator and written to the key so a reviewer can reproduce it.

Also `docs/product/FO-DEMO-SOURCES.md`: every folder, file pattern, columns, owner (from the roster below), update frequency, and the PRD use case it serves. Ingestion metadata the PRD asks for goes in a sidecar per folder `_manifest.json` {source_system, files: [{name, effective_date, received_at, version}]}.

### D4 Unstructured documents (the PRD's P1 document repository)
About 24 files under `data/<company>/documents/` (copy to `local/documents/<company>/`): monthly custodian statement summaries (text) for three months, two capital call notices, one distribution notice, two manager letters, three invoices (custody, management, performance fee), an investment policy statement with target allocation and limits, a reconciliation and exception policy with tolerances, a data access policy (who may see what: principal, analyst, operations, tax adviser, external adviser), a retention note, two committee minutes, three emails (a price query, a capital call reminder, a break investigation), a valuation policy for private assets (stale after 180 days), a benchmark policy naming the blend, a fee agreement, a systems inventory. Plant: definitions (TWR, MWR, net worth, drift, concentration, liquidity runway), owners, the tolerances the PRD mentions (reconciliation tolerance, 98 %), one contradiction (the concentration limit in the IPS vs the minutes), one unclear decision. Answer key: `docs/product/FO-DEMO-DOCS-KEY.md`.

### Roster (seeded by the orchestrator, `tools/seed_fo_demo.py`)
| Name | Role in the PRD | Company role | Sign-in |
|---|---|---|---|
| Meredith Shaw | Principal / CIO, decision maker | company_admin, sponsor | meredith.shaw.<company>@example.test |
| Daniel Kerr | Investment analyst, architect, data engineer | analyst | daniel.kerr.<company>@example.test |
| Grace Ward | Operations / finance, ops manager | analyst | grace.ward.<company>@example.test |
| Harvey Rowley | Tax adviser / accountant | owner | harvey.rowley.<company>@example.test |
| Aaron Lyle | External adviser (controlled access) | approver | aaron.lyle.<company>@example.test |
| Katie Kingsley | Family member, reader | participant | katie.kingsley.<company>@example.test |

### Demo script (orchestrator, after D3 and D4 land)
`docs/guides/FO-DEMO-SCRIPT.md`: the PRD use cases mapped to the 1.0 journey: which sentence Meredith says to North, which KPIs she names (net worth, TWR, MWR, benchmark-relative, drift, concentration, liquidity runway, fees), what the scan reports (the planted truths), what Flow builds, what Consume shows, and which phase 2 items become offers.
