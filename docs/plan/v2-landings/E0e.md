# E0e Evergreen demo company seed

## What changed
`tools/seed_evergreen.py` creates company `evergreen` (Evergreen Office): 7 accounts (CIO sponsor, Mei analyst, Raj approver, Sofia participant, Anita and Leo analyst, Grace company_admin; passwords only in `_control/seed_credentials.txt`), their `users` rows, 3 legal entities and portfolios, 4 instruments, approved identifiers ("EG Growth Fund I", administrator code 4471), 2 access groups with scopes, 5 signed rules (cash_tolerance, cio_materiality, estimate_use, statement_due, plus fx_fixing for E3d), source batches/records/control totals, Fund A/B valuations, liquid book position, NAV, USD/SGD fixings, cash on 8 Oct in two views (Entity B differs 12,400; Trust 1,800 inside tolerance), and the September report issued 3 Oct (10.00m, 6.40m, 41.20m, total 57.60m). The amended 10.18m statement is not loaded. Idempotent; `--reset` clears only the evergreen warehouse.
Files: `tools/seed_evergreen.py`, `tests/v1/test_e0e.py`, `docs/guides/EVERGREEN-DEMO.md`.

## How to test on the demo
1. `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e0e.py -q` (5 tests, tmp data root).
2. Orchestrator only: `python tools/seed_evergreen.py` (live data folder).
3. Sign in as `daniel.foo.evergreen@example.test` (password in the keys file).

## Known limits and decisions
- Facts are written by SQL with an explicit back-dated `recorded_at`: `e1_write` stamps now, so it cannot build history before the 3 Oct cutoff. Report goes through `e1_reports.ensure_report`/`issue` when installed (line shape: E1c's `sources=[{table,row_id}]`, statuses estimated/official); otherwise a SQL fallback writes the same rows (tested).
- Cash recon choice for E3b: `position_snapshots` on the Cash instrument, `accounting` (administrator) vs `operational` (trading export), position_date 2026-10-08.
- Rule parameter keys: `abs_amount`, `currency`, `pct_of_fund`, `allowed`, `business_days`, `series_key`/`fixing`.
- organization_id: E0a's DDL types it UUID, so the seed uses uuid5 of "<slug>.signal-harbor" (same as `e1_write.org_id`); the card text "organization_id = plane.company_id" cannot hold with UUID columns.
- Not seeded: documents, extracted fields, exceptions, pulse items (their cards own them).

## Wiring for the orchestrator
None. Run the seed once on the live data root; then `python tools/seed_e0_demo.py evergreen` for the inbox files.
