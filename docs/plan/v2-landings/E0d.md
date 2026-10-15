# E0d Synthetic workbooks and the evaluation set

All data is invented (fictional "Evergreen Office", fictional funds). No real names.

## Files
- `tools/make_e0d_workbooks.py [out_dir]` writes 21 .xlsx to `tests/v1/fixtures/e0d/workbooks/` and one expected JSON each to `tests/v1/fixtures/e0d/expected/`. Fixed seed and fixed document properties; cell content is identical on every run (the .xlsx zip bytes are not, because openpyxl stamps zip entries; compare cells).
- `tools/eval_data_agent.py <company> [--baseline] [--bar 0.8]` scores the data agent. Exit 0 pass, 1 below bar, 2 agent module missing.
- `tools/seed_e0_demo.py <company>` copies the workbooks into `data/<company>/landing/inbox/`, never overwriting.
- `tests/v1/test_e0d.py` (6 tests).

## Run
    python tools/make_e0d_workbooks.py
    python tools/eval_data_agent.py evergreen --baseline     # runner self-test, about 15% mapping accuracy
    python tools/eval_data_agent.py evergreen                # needs E0b
    python tools/seed_e0_demo.py <demo-company>
    SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e0d.py -q

## Expected JSON
`sheet`, `header_row`, `first_data_row`, `last_data_row`, `exclude_rows` (totals row), `status` (final / in_progress), `traps`,
`columns` (source header -> `{target: "table.field" | "ignore", transform?: {multiply | date_format}}`) and `control_totals`
(`row_count`, `sums` after transforms, and for a stated totals row `stated_matches_rows`, `stated_difference`). Targets are checked against
`docs/v2/evidence-to-action-mvp.dbml`. Capital calls map to `cash_movements` (type call): the model has no capital-call table.

## Contract the runner expects from E0b (planned names)
`profile_sheet(path) -> {sheet, header_row, columns, status}`; `propose_mapping(plane, profile) -> {columns: {src: "table.field"|"ignore"|{target, transform}}, status, totals_match}`
(`totals_match: false` means the stated totals do not add up; `status: "in_progress"` for a draft sheet). `plane` is the company slug. Change the runner if E0b differs.

## Traps (workbook)
- same_fund_two_names: pos_2026_09_altnames, val_admin_in_progress (administrator short names vs canonical names)
- thousands: pos_2026_09_thousands, cash_2026_09_thousands (multiply 1000)
- day_month_swap: val_mgr_estimate_dmy (%d/%m/%Y), val_mgr_estimate_mdy (%m/%d/%Y); text dates
- merged_header: pos_2026_09_merged, calls_2026_q3_merged (header is the row below the merged band)
- totals_row: pos_2026_09_totals, cash_2026_09_thousands, cash_2026_09_bad_total, calls_2026_q3_merged, benchmark_blend_2026
- renamed_column: pos_2026_09_custodian (vs August), nav_admin_2026_09 (vs August)
- in_progress: val_admin_in_progress, nav_draft_in_progress, benchmark_in_progress (sheet name and a title line say so)
- totals_mismatch: cash_2026_09_bad_total (stated total 25,000 above the rows)
- clean: pos_2026_08_custodian, val_mgr_final_aug, cash_2026_08, nav_admin_2026_08, calls_2026_q3, market_index_levels_sep

Figures reconcile across files: August and September positions use the same six funds; NAV per portfolio equals the sum of its positions; valuations equal position values.

## Known limits
- Single-table, first-sheet-style layouts; no hidden rows, formulas or multi-table sheets.
- Fund names map to `instruments.canonical_name`; resolving an alias to one instrument is not scored (only the column target).
- Day/month swap: every date is a month end (30/09/2026, 08/31/2026), so the day is above 12 and the order is resolvable from the sheet itself; a sheet with only days up to 12 is not covered.
- Expected `sums` are after transforms; for the thousands file they are rounded.
- The pass bar (0.8 mapping accuracy, zero invented targets, every in-progress and mismatch caught) is a default pending agreement; `--bar` overrides.
- Baseline only exact-matches column names, so it scores low by design.
