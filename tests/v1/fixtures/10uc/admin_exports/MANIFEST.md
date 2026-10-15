# admin_exports (synthetic)

Generator: `tools/gen_10uc/admin_exports.py` (deterministic; figures read from `docs/test/10uc_universe.json`; the script re-opens every file and asserts the figures).
Administrator: "Harbourline Fund Services (synthetic)". 12 files, one per month end, 2025-10 to 2026-09 (the universe holds 12 month ends, not 13). 348 position rows in total.

Each file `administrator_export_YYYY-MM.xlsx` has two sheets:
- `Positions`: title block rows 1-4, header row 6 (Portfolio, Admin Code, Instrument, Quantity, Price, Market Value, Currency, Valuation Status, Valuation Date), one row per holding per portfolio, footer note. 20 EG-LIQUID securities (quantity x price = value) plus the private/hedge/liquid fund holdings of EG-GROWTH, EG-B-OPS, EG-FUNDS (quantity 1, price = reported holding value).
- `Approved NAV`: approved NAV per portfolio for the month (approved_official), with approval timestamp (2nd business day, 06:00 UTC).

Valuation Status words: Priced (liquid book), Final, Estimate, Amended, Carried forward (older statement carried), Not received (blank quantity, price, value).
Valuation Date is the period end of the statement the value came from (`administrator_from` in the universe), so a carried value shows the older date (Fund D 2026-03-31 in the Sep file); liquid book lines carry the month end.

## Planted facts carried
| Fact | Where |
|---|---|
| Renamed column: `Market Value` becomes `Valuation Amount (USD)` | `administrator_export_2026-03.xlsx` only (generator choice; the universe lists no such fact) |
| P03 / P04 / P05 administrator NAV 30 Sep: EG-GROWTH 16,400,000; EG-B-OPS 22,525,000; EG-FUNDS 22,550,000; EG-LIQUID 41,200,000 (bridge differences are against the investment view, not in this file) | `2026-09`, sheet Approved NAV and Positions |
| P01 Fund A at 10,000,000 as Estimate; Fund B 6,400,000 Final | `2026-09` |
| P07 / P18 stale values: Fund D 4,650,000 carried from the 31 Mar statement; Fund C 8,275,000 from the 30 Jun amended statement; Fund E 9,600,000 carried (the Q3 statement arrived after the NAV) | `2026-09` (Fund D carried in 2026-04 to 2026-09) |
| P17 Harborview Semiconductor 20,000 x 118.40 = 2,368,000 (5.75% of 41,200,000) | `2026-09` |
| P29 the 6 Oct sale of 5,000 HVS is not booked: quantity stays 20,000 | `2026-09` |
| P13 Fund B / H1 shown under canonical names with admin codes 4472 / 4481 | all files |
| Oct 2025 edge cases: EG-GROWTH has no administrator values, NAV 0.00; EG-FUNDS NAV 10,444,500 | `2025-10` |
