# E3b Reconciliation engine

## What changed
Two checks in code, run on demand: `cash_by_entity` and `nav_vs_investment`. A break opens a case through E4a; the same break on the same day is never opened twice.

**Choice for cash_by_entity** (documented in the module docstring): both sides come from `position_snapshots` rows on instruments with `instrument_type = 'cash'`, summed per legal entity (via portfolios) and currency. `view_type = accounting` is the administrator, `operational` is the trading export. Positions, not `cash_movements`, because each source reports a balance. An entity with only one side is skipped and named in the run's `skipped` list.

**nav_vs_investment**: `nav_snapshots` for the day against the latest valuation per instrument on or before it, per portfolio. It uses the same `cash_tolerance` rule (phase 1 has one tolerance).

Rules (shape assumed from the DBML note on `rule_versions.parameters`): `cash_tolerance` `{abs_amount, currency}`; `cio_materiality` `{abs_amount, currency, pct?}` (pct is of the administrator or NAV figure). No signed tolerance: Refused 409 with a plain message, nothing runs. Different currencies are converted with `e3_calc.fx`; with no rate the subject is skipped and named.

Case fields passed to `e4_cases.open`: exception_type `break`, title (check, subject, day; used for de-duplication against open cases), description, detected_at, candidate_impact_amount, impact_currency, materiality_status, materiality_rule_version_id, portfolio_id (NAV check only).

## Files
`sh_platform/v1/e3_recon.py`, `e3b_routes.py`, `e3b.permissions.yaml`, `tests/v1/test_e3b.py` (6 tests; E3a and E4a stubbed). Runs are appended to `data/<company>/warehouse/recon_runs.jsonl`.

## Test on the demo
1. Seed evergreen (E0e) so Entity B cash differs by 12,400 on 8 Oct.
2. `POST /api/v1/recon/cash_by_entity/run` `{"as_of_date": "2026-10-08"}` as Mei (analyst).
3. Expect `opened` with one case id; open the Action Desk and see the Entity B break.
4. Run again: `opened` is empty, `breaks` still 1.
5. `GET /api/v1/recon/runs` lists both runs.

## Known limits
Needs E3a and E4a on disk to run for real. Run listing exposes counts and case ids only (case content is filtered by E4a/E1d). No scheduler; runs are triggered by a call.

## Wiring for the orchestrator
Router auto-installs from `e3b_routes.py`. Optionally call `e3_recon.run(plane, "cash_by_entity", date)` after each successful load (E0c2).
