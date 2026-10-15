# E3c Revision impact

## What changed
`e3_impact.on_new_valuation(plane, valuation_id) -> str | None`. When a new valuation supersedes one that an issued report used
(`e1_reports.versions_using`), it works out the change (new minus old, converted to each report line's currency with `e3_calc.fx`),
opens a `revision` exception through `e4_cases.open` (amount, currency, materiality from the signed `cio_materiality` rule, rule version id)
and writes one `exception_impacts` row per affected report line (issued value, draft value). It reads only; it never touches `nav_snapshots`.
No supersession or no report used it: returns None. A missing FX rate leaves that line's draft value empty and says so in the description.

## Files
`sh_platform/v1/e3_impact.py`, `tests/v1/test_e3c.py`, this note.

## Test on the demo
1. Seed Evergreen (E0e) and confirm the amended Fund A statement (E2b `confirm`).
2. Check the Action Desk for one revision case, impact 180,000 USD, affecting the September report.
3. `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e3c.py -q`

## Known limits
- The report line is found as the `metric_values` row of the report version's calculation run with the same instrument (the holding line).
- `cio_materiality` parameters assumed as `abs_amount` and `pct_of_fund` (percent of the old value); E3a/E0e must use these keys or tell me.
- `e4_cases.open` is passed the `exceptions` column names (`exception_type`, `title`, `description`, `instrument_id`, `portfolio_id`, `detected_at`, `candidate_impact_amount`, `impact_currency`, `materiality_status`, `materiality_rule_version_id`, `status`).
- Sibling modules are imported lazily; a missing one logs a warning and raises ImportError.

## Wiring for the orchestrator
None beyond E2b calling `on_new_valuation` after writing the superseding valuation.
