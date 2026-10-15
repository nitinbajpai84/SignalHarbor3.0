# Module 3 demo inputs: Illustrative Lakeside Family Office, September 2026

Illustrative, synthetic. No real client, company or person. These are data samples a customer would upload, not documents: `tools/seed.py` does not add them as context documents (it reads only `demo_documents/` and `demo_story/`).

Regenerate with `python make_demo_module3.py` (same bytes every run). The script's `compute()` is the answer key; `tests/test_demo_module3.py` checks it.
Every CSV starts with a banner row ("Illustrative, synthetic ...") and then the header row; the workbook has the banner in row 1 and the headers in row 3 of sheet "Sep 2026"; the JSON has a top-level `illustrative_synthetic` key.
There is deliberately no pay or bonus file: the restricted source stays unknown, so K18 stays unknown.

## Files

| File | Source | Columns (as the office names them) | Feeds |
|---|---|---|---|
| `performance_workbook.xlsx` | Performance workbook | Fund / Manager, Asset Cls, Opening Value (SGD), Closing Value (SGD), Net Flows, Fees Charged, Period Return % (40 rows) | K10, K15, K16 |
| `custody_daily_positions.csv` | Northgate Custody daily file | Val Date, Acct, Security, Qty, Price, Mkt Value, Ccy (287 rows, 22 business days, 24 Aug to 22 Sep, 14 positions) | K12 |
| `capital_calls_export.json` | Capital-calls mailbox | notice_ref, fund, notice_dt, due_dt, amt, ccy, status, replaces (15 notices, all SGD) | K04 |
| `index_levels.csv` | Index provider feed | Date, Index, Level (two indexes, 3 Aug to 22 Sep) | K16 |
| `exposure_workbook.csv` | Exposure workbook | Issuer, Country, Sector, Exposure Value (SGD) (24 rows) | K09 |
| `benchmarks_monthly_pack.csv` | The office's own pack | Measure, Figure, Unit, Period end, Where it came from | the comparison |

## Deliberate problems

1. Asset class is empty in 4 of the 40 performance rows (rows 4, 15, 23, 32 of the data).
2. Fees Charged is empty in 20 of the 40 performance rows (blank is read as zero; Lens should flag it).
3. Custody data stops at 22 September; the period ends 30 September. Three illiquid positions (ACC-07) stop being priced on 11 September.
4. Index levels stop at 22 September: the last week of September is missing.
5. Capital call CC-014 amends and replaces CC-007 (same fund; 290,000 instead of 275,000). Only CC-014 counts.
6. Benchmark gaps (below): different period end, fees excluded, and one figure that cannot be reproduced.

## Expected outcome per measure (the answer key)

Rules used: figures in per cent; empty fees count as zero; private market = Private Equity plus Venture Capital, with unclassified rows counted in the total only; stale = last valuation more than 5 business days before the file's last date.

| Measure | Pack figure | Calculation from the files | Outcome |
|---|---|---|---|
| K10 Private-market allocation | 20.86 % | 20.86 % | matches |
| K09 Single-issuer concentration | 12.92 % | 12.92 % (Birch Semiconductor, two rows added) | matches |
| K04 Known obligations due | 2,610,000 SGD | 2,610,000 SGD (open notices, CC-007 replaced by CC-014) | matches |
| K12 Stale-valuation share | 28.57 % (as at 30 Sep) | 21.43 % (3 of 14 positions, data to 22 Sep) | gap: the pack's period end is 30 Sep, the data stops at 22 Sep |
| K15 Manager performance (net of fees) | 0.67 % (before fees) | 0.63 % (net of 69,050 SGD fees) | gap: the pack leaves fees out (and half the fee cells are empty) |
| K16 Excess return versus benchmark | 1.2 percentage points | not computable | cannot be worked out: index levels missing from 23 to 30 Sep |

K18 Compensation inputs reconciled: unknown (no pay review file, restricted).
