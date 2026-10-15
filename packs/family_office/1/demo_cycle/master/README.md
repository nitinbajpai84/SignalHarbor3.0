# master: Ardmore family office reference data (illustrative, synthetic)

Every other folder in demo_cycle uses these ids exactly. Reporting currency SGD. Position date 2025-09-30.

## Id lists
- Entities: E01 Ardmore Holdings Pte Ltd, E02 Ardmore Investments Pte Ltd, E03 Shaw Family Trust, E04 Kerr Next Generation Trust, E05 Ardmore Philanthropy Ltd.
- Custodians: C1 Harbourline Custody, C2 Meridian Trust Services, C3 Strait Custodial Bank.
- Administrators: A1 Lattice Fund Administration, A2 Pinecrest Fund Services, A3 Orchard Administration Partners.
- Bank accounts: B01 E01 SGD, B02 E01 USD, B03 E02 SGD, B04 E02 USD, B05 E03 SGD, B06 E04 SGD, B07 E05 SGD, B08 E02 EUR.
- Holdings H001 to H040: H001-H018 listed equities (daily price), H019-H026 bond funds (daily), H027-H036 private market funds (administrator valuation, quarterly or worse), H037-H040 money market funds (daily).
- Issuer groups G01 to G12 (G03 Kestrel Banking Group is the concentration issuer: about 131 million SGD of starting value, about 11 percent of assets).
- People P01 to P09 (staff), FR01 to FR04 (family readers).
- Currencies: SGD, USD, EUR, HKD.

## Files
| File | Grain | Columns |
|---|---|---|
| entities.csv | one row per entity | entity_id, name, type, jurisdiction |
| custodians.csv | one per custodian | custodian_id, name |
| administrators.csv | one per administrator | admin_id, name |
| accounts.csv | one per bank account | account_id, entity_id, currency, name |
| account_opening_balances.csv | one per account at 2025-09-30 | account_id, currency, balance_local (money, 2 dp), fx_sgd_per_unit, balance_sgd |
| issuer_groups.csv | one per issuer group | issuer_group_id, name |
| holdings.csv | one per instrument (40) | holding_id, name, asset_class, currency, custodian_id, administrator_id (private funds only), issuer_group_id, entity_id (owning entity) |
| positions_2025_09_30.csv | one per holding | holding_id, currency, quantity (units), unit_cost_local, book_cost_local, fx_sgd_per_unit, book_cost_sgd, unit_price_local (at 2025-09-30), market_value_local, market_value_sgd |
| people.csv | one per staff member | person_id, name, role, team, email, seed_display_name |
| family_readers.csv | one per family reader | reader_id, name, relation, generation, receives_report (yes/no) |

## Rules
- Money in the stated currency with two decimals; SGD per unit FX at 2025-09-30: USD 1.2800, EUR 1.5000, HKD 0.1650, SGD 1.
- Starting market value of holdings about 1,140 million SGD; bank cash about 48 million SGD; total about 1.19 billion SGD.
- Market value at the custodian at 2025-09-30: C1 about 474 million, C2 about 433 million, C3 about 233 million SGD.
- Quantities are the starting positions; later folders (valuations, custody) move them. Private fund market value is the last administrator valuation.
- Names are invented; email addresses use example.test.
