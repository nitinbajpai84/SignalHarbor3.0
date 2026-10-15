# E0a landing: the data model catalogue, its versions and the Admin "Data model" page

## What changed
- The core DBML (`docs/v2/evidence-to-action-mvp.dbml`, 41 tables, 9 groups) is parsed with `pydbml` into a per-company catalogue. It parsed unchanged: `vector(384)`, `tsvector`, TableGroup and the indexes all work, so no workaround was needed. Only plain defaults (numbers, true/false, `now()`) are accepted in company extensions.
- Version 1 is written lazily on the first read of a company: `data/<company>/model/versions/1/{model.dbml, extension.json, catalogue.json, meta.json}` and `model/current.json`. Further versions are proposals (state proposed, approved, rejected, superseded). Every step goes to `model/log.json`.
- Proposals come from an uploaded DBML extension or a form (add table, add column). The parser's line and message are returned for a bad script. Any retype or change of a core column is refused ("Core tables change only through a product release"). A new column on an existing table must be optional or have a default (DuckDB cannot add a required column to a table that may hold rows). The diff is in plain words. Removing or retyping an extension column named in `model/mappings/*.json` (E0b records: `state`, `columns[].target_table`, `columns[].target_field`) is flagged under `breaking`.
- Sandbox: the proposed DDL is applied to a temp copy of the warehouse file (or an empty one) and the result stored. It is re-run at approval, and a failure blocks approval.
- Approval: needs the architect seat and a different account from the proposer; the warehouse is migrated first, then `current.json` switches. The old current version and other open proposals are marked superseded. Reject needs a reason, which is kept.
- Warehouse: `data/<company>/warehouse/evidence.duckdb`, add-only (create missing tables, add missing columns; no foreign keys or secondary indexes, primary keys and not null on creation only).

## Helpers (`sh_platform/v1/e0a_catalogue.py`)
`current(plane) -> dict` (`{version, tables, refs}`), `tables(plane) -> list[{name, group, note, layer}]`, `describe(plane, table) -> dict | None` (columns, indexes, refs), `has_field(plane, table, field) -> bool`, `version_of(plane) -> int`, `ddl(catalogue, dialect="duckdb") -> list[str]` (one create statement per table), `apply(plane) -> {created_tables, added_columns, path}`. Also `propose`, `approve`, `reject`, `proposals`, `versions`, `catalogue_view`, `script`. Refusals raise `sh_platform.v1.i2_north.Refused`.

## Files
New: `sh_platform/v1/e0a_catalogue.py`, `e0a_routes.py`, `e0a.permissions.yaml`, `ui/src/v1/e0a/{routes.tsx, api.ts, AdminModel.tsx}`, `tests/v1/test_e0a.py`, this note. Edited (backups in `.sh-tmp/*.bak-e0a`): `requirements.txt` (pydbml), `ui/src/v1/t1/AdminAgents.tsx` (a "Data model" link), `ui/src/shell/CentreShell.tsx` and `copy.ts` (menu link for admin and analyst).
Routes: `GET /api/v1/model/{catalogue, tables/{name}, script?version=, versions, proposals, proposals/{n}}`, `POST /api/v1/model/proposals`, `POST .../proposals/{n}/approve`, `.../reject`.

## Try it on the demo (after the server picks up the new code)
1. Sign in as Leela (analyst). Open Admin console, then "Data model" (`/centre/admin/model`): version 1, tables by group with columns.
2. "Propose a change": add a new table `office_notes` or a column on `users`. You land on the proposal page with the plain diff and "Works" from the trial on a copy.
3. Try Approve as Leela: refused (you proposed it).
4. Sign in as Arjun (company admin, architect seat) and open the same change: Approve. The page shows version 2 in use.
5. `data/neera/warehouse/evidence.duckdb` now holds the 41 core tables plus the new one.

## Tests
`SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e0a.py -q`: 8 passed. `cd ui && npx tsc --noEmit -p .`: clean; vitest `src/v1/t1 src/shell`: 18 passed.

## Known limits
- In an extension, a Table block named after a core table lists only the columns to add; a block for a company table lists all its columns (one left out is dropped from the catalogue, never from the warehouse). An upload overlays the current extension by table name, so a whole table cannot be removed through an upload.
- `model.dbml` for later versions is the core script plus the extension appended as text, so it is for reading, not for re-parsing as one file.
- Only the seats table decides who may act: the architect seat is analyst or company_admin, so one person can hold both seats; the proposer rule is by account.
- Version 1 for a live company is created on first read; the warehouse file appears at the first approval or a call to `apply(plane)`.
- The full v1 suite was run while E0c, E2 and E3 builders were mid-edit; failures seen there (supersession, fx, E0c states, one L2 chat test) are in their files and varied between runs.
