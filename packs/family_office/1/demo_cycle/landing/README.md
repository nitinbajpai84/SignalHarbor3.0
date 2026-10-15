# landing: daily file arrival log (illustrative, synthetic)

One row per expected file per business day, 2026-07-01 to 2026-10-06 (Monday to Friday; none on 2026-08-10, National Day observed). Times are Singapore time.

## Files
| File | Grain | Columns |
|---|---|---|
| file_arrival_log.csv | one row per file per business day (1,035) | arrival_date, source_type (custodian, administrator, bank, index_provider), source_id (C1 to C3, A1 to A3, B01 to B08, IDX), file_name, expected_at, arrived_at, minutes_late (0 when on time or early), rows, schema_ok (Y/N), schema_note, late_flag (Y when more than 30 minutes after expected) |

## Expected times
Custodian files: C1 07:30, C2 08:00, C3 07:45. Administrator flash files: A1 and A2 09:00, A3 09:30. Bank statements per account 08:30. Index provider 19:00.

## Notes
- File name patterns: custodian_daily_file_<id>_<yyyymmdd>.csv, administrator_daily_flash_<id>_<yyyymmdd>.csv, bank_statement_<account>_<yyyymmdd>.csv, index_provider_levels_<yyyymmdd>.csv.
- Rows are record counts in the file; schema_ok = N means the file did not match the expected header and its load was held.
- Monthly counts of late files for July, August and September 2026 are the sum of late_flag = Y rows by month of arrival_date.
