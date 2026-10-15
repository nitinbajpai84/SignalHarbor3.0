# reporting

ILLUSTRATIVE: synthetic data for the Ardmore family office demo.

The monthly committee pack: who spent how long on it, and what had to be corrected after it went out.

## Files

### effort_log_daily.csv
Grain: one task row. Window: 2026-07-01 to 2026-10-06, working days only (no rows on 2026-08-10, National Day observed).

| Column | Meaning |
|---|---|
| task_id | EL0001 onwards |
| date | Day the work was done (ISO) |
| person | Who did it |
| pack_period | The committee month the work was for (third Thursday); work after a month's committee counts for the next month |
| task | What was done, in words |
| minutes | Minutes spent (multiples of 5) |
| cause | Why the time was needed: `late_statement_A1`, `late_statement_A2`, `late_statement_A3` (rework because that administrator's statement came late or was reissued), `reformat`, `reconcile`, `chase`, `review`, `layout` |

### effort_log_monthly.csv
Grain: calendar month x cause, 2025-09 to 2026-09 (13 months x 8 causes). Columns: period (YYYY-MM), cause, minutes, hours (minutes / 60, two decimals), source.
Aggregation: for 2026-07, 2026-08 and 2026-09 the rows are the sum of minutes in effort_log_daily.csv by calendar month of `date` and cause (source `daily_sum`). Earlier months come from the office's monthly log (source `monthly_log`); no daily rows exist for them. Monthly pack effort (K03, hours) is the sum of hours over causes.

### pack_versions.csv
Grain: one issued version of a month's pack. Columns: period, committee_date, version (v1 is the issue to the committee two working days before the meeting; v2 onwards are corrections), issued_date, issued_by, after_circulation (yes for corrections), change_note, pages, prep_hours_in_month (the month total from effort_log_monthly.csv).
