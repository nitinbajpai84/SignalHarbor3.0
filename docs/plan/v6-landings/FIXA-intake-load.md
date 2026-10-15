# FIXA: intake load (UC6 B1 to B3, honest result, pipeline upload names)

## Root causes and fixes

| Issue | Root cause | Fix |
|---|---|---|
| B1 500 `KeyError 'columns'` | `e0b_tools._model_targets` read `t["columns"]` from `e0a_catalogue.tables()`, which lists names only. Every caller of `tables()` was checked (b6_span, b10_pack, cx_dash, talk, e0b_tools registry): they read names/notes only. | `_model_targets` now reads `e0a_catalogue.columns_of()`. No change to `e0a_catalogue.py` (FIXC's file). Test: `test_model_targets_reads_the_columns_not_the_table_list`. |
| B2 rules drop money, ISO dates | Synonym lists had no closing cash, net movement, commitment columns, entity code, "as of date"; ISO dates carried no format. | `e0b_tools.DOMAINS`: closing cash/balance to `position_snapshots.source_market_value`, net movement to `cash_movements.amount`, entity code to `legal_entities.entity_code`, new `commitments` domain (commitment, committed on, currency, legal entity, administrator code). Called to date / uncalled stay ignored on purpose (worked out from confirmed calls). ISO dates get `%Y-%m-%d` in the proposal so the review shows it. |
| B2 no way to correct a line | Only approve or reject. | `e0b_mappings.edit` + `PUT /api/v1/model/mappings/{id}` (target, date format, multiply by, decimal mark). Same `sheet_mappings` records; approval stores the corrected lines. File page shows editable lines for the data engineer; Accept saves then approves. Remembered for the next file: `get_approved` now matches a sheet name with its month digits masked (a CSV sheet is named after its file, so July's mapping never matched August's). |
| B3 "fund or portfolio not approved yet" | It is the per-source fund-name match (`e2_match`, `instrument_identifiers.mapping_status`), approved by Operations or the data engineer; a portfolio code that is not in master data is held too. The result only said so in one sentence. | The load result carries `needs_approval {funds, portfolios}`; the file page lists each fund with an Approve action (`POST /api/v1/evidence/aliases/{id}/approve`) and each missing portfolio, then Load again. Commitments are now loadable (table `commitments`), so the commitments workbook proposes its funds. |
| m3 "loaded" with 0 rows | Control total counted parsed rows, not written rows. | New control total "Rows written". Zero written gives status/state `nothing_loaded` ("Nothing was loaded. ..."), batch `nothing_loaded`, never `loaded`. Message on success reads "Loaded n of m rows". |
| UC8 M7 overwrite | `runner.py` upload renamed every file to `<source>_<today>.csv`. | The sender's name is kept when the pipeline pattern accepts it, else wrapped as `<source>_<original stem>`. A different file with the same name gets `~2`; identical bytes are the same file. |

Also: cash reports name no fund, so a position row with no instrument takes the company's cash instrument; a row with an entity code and no portfolio uses the entity's only portfolio (else held back, saying why); cash rows default `movement_type = bank_movement` (NOT NULL). "Upload files" on the intake page takes several files at once (a month); each goes through the same file page. FIXB1's trade hook at the end of `e0c_load.py` was left alone; `trade_intake.load_folder` still has no route (pending, not needed for this path).

## Files

`sh_platform/v1/e0b_tools.py`, `e0b_mappings.py`, `e0b_routes.py`, `e0b.permissions.yaml`, `e0c_load.py`, `e0c_landing.py`, `sh_platform/build/runner.py`; `ui/src/v1/e0c/api.ts`, `FilePage.tsx`, `IntakePage.tsx`, `e0c.test.tsx`; tests `tests/v1/test_fixa_intake.py` (new), `test_e0c2.py` (3 control totals), `tests/build/test_runner.py` (kept names, no overwrite). Backups: `D:/Temp/bak-fixa/`.

## How to test

- `pytest tests/v1/test_fixa_intake.py tests/v1/test_e0b2.py tests/v1/test_e0c1.py tests/v1/test_e0c2.py tests/build/test_runner.py -n 4`
- `cd ui && npx vitest run src/v1/e0c && npx tsc --noEmit`
- By hand: Data > Intake, upload the July files together, open one, change a line, Accept, Load. A file with an unapproved fund shows "Waiting for approval" with an Approve button.

## UC6 July acceptance (fresh env D:/Temp/fixa-env, in-process through the same landing/mapping/load functions the routes call, model off, deleted afterwards)

See the final report for the numbers recorded; cash by entity at 31 Jul from the administrator file: EG-HOLD 2,305,906.48, EG-TRUST 1,252,492.34, EG-B 905,000.00, matching ANSWER-KEY 3.1.

## Not done / limits

- Uncalled still reads 44,000,000 in a clean company: called-to-date comes from confirmed calls, not the commitments file.
- EG-TRUST has two portfolios, so its bank file rows are held back ("more than one portfolio, needs a portfolio column"); the page says so.
- A partly loaded file cannot be loaded again (would double cash movements); approve funds before the first load.
- A fund with no instrument at all in master data cannot be proposed from the page (needs the master-data feature).
- The notice receipt log (header only) reads "Nothing loaded: no data rows".
