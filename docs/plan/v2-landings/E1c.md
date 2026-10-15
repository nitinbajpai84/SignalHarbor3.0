# E1c Reports and issued versions

## What changed
- `e1_reports.py`: `ensure_report`, `issue`, `as_issued`, `as_known_now`, `versions_using` (the contract), plus `listing` for the routes.
- `issue` writes one `calculation_runs` row (knowledge_cutoff_at = cutoff, code_version = E3d `CALC_VERSION`, else `e1c-1` with a warning), a `metric_values` row per line, `metric_evidence` per source row, and an `issued` `report_versions` row. The previous issued version for the same report and period becomes `superseded`; the new row's `supersedes_report_version_id` is the record. All in one transaction.
- `metric_definitions` `holding_value` and `portfolio_total` are seeded on first use (owner = fixed system id `00000000-0000-5000-8000-000000000e1c`).
- A line is `{metric_code, portfolio_id?, instrument_id?, value, currency, status, sources?: [{table, row_id}]}`. Evidence is stored as `metric_evidence.note = "<table>:<row id>"` (the table has no column for an observation row); `source_record_id` and `extracted_field_id` are filled from the row when it has them.
- `as_known_now` re-reads each source row's subject through E1a `latest(cutoff=now)`. Same row: status as issued. Newer row: new value, status `revised`, `issued_value` kept. No evidence, row gone, or currency changed: `unverified` (no FX here). A `portfolio_total` line with no sources is re-added from the holdings in scope (its portfolio, or all if none).
- `versions_using` returns versions with status `issued` only (a superseded version is no longer live).
- Routes (`e1c_routes.py`): `GET /api/v1/reports`, `GET /api/v1/reports/versions/{id}?view=issued|now`. Lines are filtered with E1d (`level`, `visible_portfolios`); if E1d is missing nothing is shown (fail closed). Values go out as strings.

## Files
`sh_platform/v1/e1_reports.py`, `e1c_routes.py`, `e1c.permissions.yaml`, `tests/v1/test_e1c.py`, this note.

## How to test
1. `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e1c.py -q` (6 tests).
2. On a demo company: `ensure_report`, record the Fund A estimate with E1b, `issue` the September report, then record the 10.18m revision superseding it.
3. `as_issued` still shows 10.00m, `as_known_now` shows 10.18m, status revised, total 16.58m on the test data; `versions_using("valuation_observations", old_id)` returns the version.

## Known limits
- No FX conversion in `as_known_now` (a currency change gives `unverified`); E3d can be wired in later.
- Report version status changes do not write an event row: the DBML has no event table for reports. The supersedes link records it.
- Only valuation_observations, position_snapshots and nav_snapshots are re-read.

## Wiring for the orchestrator
None beyond the auto-install of `e1c_routes.router`. E3c uses `versions_using`; E5b uses `as_issued` / `as_known_now`; E0e calls `ensure_report` and `issue`. Rows use `e1_write.org_id(plane)` as organization_id (same as E1b).
