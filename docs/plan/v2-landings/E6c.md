# E6c Shadow-mode replay

## What changed
`tools/shadow_run.py` replays periods of files in received order into a separate plane `<company>_shadow` (never live unless `--live`). While it runs `wh.now()` is replaced by the file's receipt time plus real elapsed seconds, and always restored. After each file: impacts for new superseding valuations (E3c), recons `cash_by_entity` and `nav_vs_investment` at the receipt cutoff (E3b). Writes two CSVs: findings (receipt to finding seconds, case opened, blank `false_alert` for the reviewer) and a reproducibility table (figure fingerprint per period cutoff at period end vs after all periods, via E1a).

## Files
`tools/shadow_run.py`, `docs/guides/SHADOW-MODE.md`, `tests/v1/test_e6c.py` (3 tests, stub loader/recon/impact, uses E0d workbook file names).

## Test on the demo
1. Write a spec (format in the tool header) listing a period's files and receipt times.
2. `python tools/shadow_run.py evergreen spec.json --out shadow_report.csv`
3. Fill `false_alert` in the CSV; check every row of `shadow_report_reproducible.csv` says yes.
Tests: `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e6c.py -q`

## Known limits
- The default loader needs E0c (not on disk yet): it assumes `e0c_landing.scan(plane) -> [{id, file_name|name}]` and `e0c_load.load(plane, file_id, viewer) -> {status}`. Raises ImportError with a warning when missing. Adjust `default_loader` in one place if E0c differs.
- Recon and impact calls assume `e3_recon.run(plane, code, as_of, cutoff=)` and `e3_impact.on_new_valuation(plane, id)` per the contract.
- Receipt-to-finding is machine time only. Fingerprint covers valuations, positions and NAV snapshots.
- The viewer is a stub `shadow-replay` with the data_engineer seat; E0c seat checks may need a real user.

## Wiring for the orchestrator
None.
