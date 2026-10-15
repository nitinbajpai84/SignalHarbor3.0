# E3d Calculation library

## What changed
`sh_platform/v1/e3_calc.py`: `CALC_VERSION` (12-char hash of the module source), `fx`, `fx_explained` (rate plus plain reason), `portfolio_value`. Decimal only. No routes, no UI.

## Files
`sh_platform/v1/e3_calc.py`, `tests/v1/test_e3d.py` (4 tests), this note.

## How it works
- A row counts at a cutoff when `recorded_at <= cutoff` and no superseding row was recorded by then (E1a's rule, done in one local query so the card stands alone). A plain date cutoff means end of that day UTC; None means now.
- `fx`: needs a signed `fx_fixing` rule (`e3_rules.current`) whose parameters name the fixing, e.g. `{"fixing": "ECB"}`. Picks the latest `market_observations` row (`observation_type='fx'`, `series_key` contains the fixing, base/quote currencies match, or the inverse) observed on or before the date. No rule, no rate: returns None, `fx_explained` gives the reason.
- `portfolio_value`: per instrument the latest valuation on or before the date, else the latest non-accounting position (`source_market_value`, or quantity times latest price). Status: estimated (manager_estimate), official, revised (final that supersedes), unverified (not approved, or indicative position). Converted with `fx`. If any line cannot be converted, `total` is None and `problems` lists why. Result: `{total, lines:[{instrument_id, value, status, source_row_id}], calc_version, problems}`.

## Test on the demo
1. `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e3d.py -q`
2. In a Python shell on the Evergreen plane: `portfolio_value(plane, pf, date(2026,9,30), date(2026,10,3), "USD")["total"]` gives 57,600,000; with `cutoff=None` after the amended statement it gives 57,780,000.

## Known limits
- Assumed (not in the DBML): the `fx_fixing` rule parameter name `fixing` and that FX series keys contain the fixing name. E3a/E0e seed must match.
- No "stale" status yet (no signed threshold). The warehouse uses UUID columns, so ids must be UUIDs.
- Does not use E1a `snapshot` (not landed); swap `_live` for it later if wanted.
- Tests stub `e3_rules` via `sys.modules`.

## Wiring for the orchestrator
None. E1c should use `CALC_VERSION`; E3c should call `fx(...)`.
