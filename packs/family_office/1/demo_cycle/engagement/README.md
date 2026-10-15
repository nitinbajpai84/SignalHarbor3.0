# Engagement: family reports and questions

Synthetic, illustrative. Readers are the four family members who receive the office's reports. Names match `master/` readers. No date after 2026-10-06.

Report ids: `FR-YYYY-MM` is the monthly family report for that period (14 pages); `PS-YYYY-MM` is the one-page personal summary for that period.

| File | Grain | Columns |
|---|---|---|
| `portal_events_daily.csv` | one row per page view, 2026-07-01 to 2026-10-06 | `event_id`; `timestamp` (local Singapore time, `YYYY-MM-DD HH:MM:SS`); `reader`; `report_id`; `page` (1 is the first page); `seconds_on_page` (seconds); `device` (mobile, tablet, desktop) |
| `report_opens_monthly.csv` | reader x month, 2025-09 to 2026-09 (52 rows) | `period` (`YYYY-MM`); `reader`; `report_opens` (count) |
| `questions_log.csv` | one row per question to the office, 2025-09 to 2026-09 | `question_id`; `date`; `reader`; `channel` (email, phone, whatsapp, portal_message, in_person); `question_text`; `topic`; `answered_by` (staff name); `minutes_to_answer` (minutes) |
| `feedback_notes/` | one short dated note per conversation recorded by Janet Shaw or Daniel Kerr, 2025-10-09 to 2026-09-23 (23 notes) | header lines Date, Recorded by, Family member, then free text |

## Aggregation

- A report open is a page view with `page` = 1, any report id. Monthly opens for 2026-07, 2026-08 and 2026-09 equal the count of those rows per reader per calendar month in the daily file. Earlier months have no daily rows.
- Report questions per month (K24) is the count of rows in `questions_log.csv` by the month of `date`; all 13 months are present.
- Events dated 2026-10-01 to 2026-10-06 are outside the monthly window.
