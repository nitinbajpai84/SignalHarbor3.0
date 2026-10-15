# E1a As-known-then queries

## What changed
`e1_asof` answers "what did we know at time T" over the six observation tables (valuation_observations, position_snapshots, cash_movements, nav_snapshots, market_observations, transactions).
A row is current at T when `recorded_at <= T` and no row superseding it has `recorded_at <= T`. The supersede links define the subject, so one query serves every table.
- `latest(plane, table, where, cutoff)`, `snapshot(plane, table, where, cutoff)`, `chain(plane, table, row_id)` (whole chain, oldest first).
- `where` is equality on real columns only (unknown field refused with a plain message); `cutoff` is a datetime, ISO string, bare date (end of that day, UTC) or None (now).
- Route `GET /api/v1/evidence/asof?table=&cutoff=&latest=1&<field>=<value>` and `GET /api/v1/evidence/chain?table=&id=`, filtered by E1d `visible_portfolios` (rows with no portfolio need access to at least one; market data has no portfolio and is open to any signed-in user). If E1d is missing, the route answers 503 and shows nothing (fails closed).

## Files
`sh_platform/v1/e1_asof.py`, `e1a_routes.py`, `e1a.permissions.yaml`, `tests/v1/test_e1a.py` (5 tests).

## Test on the demo
1. Seed Evergreen (E0e): Fund A estimate 10.00m recorded 2 Oct, amended 10.18m recorded 9 Oct.
2. `GET /api/v1/evidence/asof?table=valuation_observations&instrument_id=<Fund A id>&cutoff=2026-10-03` returns the 10.00m row.
3. Same call with no cutoff returns 10.18m.
4. `GET /api/v1/evidence/chain?table=valuation_observations&id=<either id>` returns both rows, oldest first.

## Known limits
- No organization filter: the warehouse is one file per company, and `organization_id` is a UUID while `plane.company_id` is a name (conflicts with Facts item 3; E1b should decide the mapping).
- A subject with two branches of supersession shows both tips.
- The `where` filter cannot express ranges or lists.

## Wiring for the orchestrator
Include `e1a_routes.router` (auto-installed by the card pattern). Needs E1d `e1_access.visible_portfolios`.
