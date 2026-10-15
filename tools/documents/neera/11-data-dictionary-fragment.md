# Data dictionary (fragment)

Owner: Leela Raman (Head of Data). Draft.

## positions (source: Northgate monthly positions file)
| Field | Meaning |
|---|---|
| as_of_date | Last working day of the month |
| security_code | Custodian security identifier, for example GEQ-001 |
| quantity | Units held at close |
| price_local | Price in the security currency (called price before March 2026) |
| currency | Security currency; missing in the January 2026 file |
| market_value_sgd | Quantity times price converted to Singapore dollars |

## fee_schedule
| Field | Meaning |
|---|---|
| fee_type | custody, management or advisory |
| rate_bps | Annual rate in basis points of average assets |

## benchmark_prices
| Field | Meaning |
|---|---|
| index_code | GLOBAL_EQ or GLOBAL_BOND |
| close_sgd | Month-end index level in Singapore dollars |
