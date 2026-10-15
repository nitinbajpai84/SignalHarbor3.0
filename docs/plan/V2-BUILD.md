# Signal Harbor v2.0 build plan (evidence to action)

Decided by Nitin, 9 Oct 2026: re-centre on evidence to action; version 1 becomes the build loop. Phase 1 cards E0 to E6; E0 added first because the client has no warehouse and most data lives in Excel. The architect and data engineer agents merge into one **data agent**. Decks: sponsor https://claude.ai/artifact/Tf4yd1c7LYsKXHFCRULSM2, working https://claude.ai/artifact/U8mCmsAJqZUsSeh5rxc4Bq. Data model: `docs/v2/evidence-to-action-mvp.dbml` (41 tables; diagram `Data Model/FO - Data model  v2.0.svg`).

Way of working: each card is built by a Sonnet builder, reviewed by Fable, one round of fixes, then rebuild and restart 8400. Cards live in `sh_platform/v1/e0<x>_*.py`, `e0<x>_routes.py`, `e0<x>.permissions.yaml`, `ui/src/v1/e0<x>/`, `tests/v1/test_e0<x>.py` (the v1 card pattern; routes auto-installed). Synthetic data only.

## E0 Data foundation (warehouse in a box, the data model as a governed catalogue, the data agent, spreadsheet intake)

### E0a The data model catalogue, its versions and the Admin "Data model" page
- **Source of truth** is DBML. The **core model** ships in the repo (`docs/v2/evidence-to-action-mvp.dbml`). A company may add an **extension** (DBML with new tables, or new columns on core tables); it may never drop or retype a core table or column.
- **Catalogue**: parse DBML with Python (`pydbml`, add to requirements) into `catalogue.json`: tables, columns (type, null, pk, default, note), indexes, refs, groups, table notes, and a `layer` (core or company). Stored per company under `data/<company>/model/versions/<n>/` with `model.dbml`, `catalogue.json`, `meta.json` (who proposed, who approved, when, state proposed|approved|rejected|superseded), and `data/<company>/model/current.json` pointing at the approved version. Version 1 is seeded from the core file.
- **Helpers** in `sh_platform/v1/e0a_catalogue.py` (the data agent and intake use these, nobody else parses DBML): `current(plane) -> dict`, `tables(plane) -> list[{name, group, note, layer}]`, `describe(plane, table) -> dict | None`, `has_field(plane, table, field) -> bool`, `version_of(plane) -> int`.
- **Warehouse in a box**: `ddl(catalogue, dialect="duckdb")` generates CREATE TABLE statements for DuckDB (uuid to UUID, timestamptz to TIMESTAMPTZ, jsonb to JSON, vector(n) to FLOAT[n], tsvector to VARCHAR, varchar(n) to VARCHAR) and `apply(plane)` creates or migrates the company warehouse at `data/<company>/warehouse/evidence.duckdb` (add tables and columns only).
- **Change proposal**: upload a DBML extension file, or a small form (add table; add column to a table). The program parses it, rejects an invalid script with the parser's line and message, and computes a **diff** in plain words (tables and columns added, changed, removed). Changes to core objects are refused ("core tables change only through a product release"). Removing or retyping an extension column that a sheet mapping uses (E0b records) is flagged as breaking.
- **Sandbox check** before approval: apply the proposed DDL to a copy of the warehouse file; report success or the error. 
- **Approval**: proposer holds the data engineer seat or is company_admin; approver holds the architect seat (head of data) and is never the proposer. Approve makes it current; reject keeps the reason. Agents and intake read only the approved current version. Every step is logged (who, when, what).
- **Routes** `/api/v1/model/...`: catalogue (tables, one table), versions, proposals (create, view diff, sandbox result, approve, reject). Read for any signed-in role; write per the seats above.
- **Screen** Admin "Data model" `/centre/admin/model`: version and status; tables by group with columns, types and notes (core marked, company extensions marked); a link to open the script; "Propose a change" (upload or form); proposal page with the plain diff, the sandbox result, Approve / Not this. Plain business English, no code on screen except column names.
- Tests: core seeds as version 1; describe/has_field; invalid DBML refused with line; core change refused; extension add creates a proposal with a correct diff; proposer cannot approve; approval switches current and creates the DuckDB tables; breaking change flagged.

### E0b The data agent (Span and Flow merged), its skill and tools
- New skill folder `skills/data/` (playbook, questions, traps, examples), merged from `skills/span/` and `skills/flow/` plus the v2 rules: three times on every fact (effective, received, recorded); never overwrite, a correction supersedes; estimates kept apart from the official NAV; an identifier alias is used only after a person approves it; a load is accepted only when its control totals match; a change to the model is a proposal to the head of data. The company admin can edit it (existing skill loader and Admin skills page).
- Tools (registered for the data agent; each enforces its rule in code): `list_tables`, `describe_table` (E0a catalogue), `profile_sheet(file)` (header row, data range, column names, units such as thousands, date formats, sheet purpose guess, no values leave the machine), `propose_mapping(sheet profile)` (every target table and field validated with `has_field`; an invented target is rejected and named), `similar_approved_mappings(profile)` (the closest approved mappings by column names and sheet purpose, used as examples), `propose_model_change(reason, dbml)` (creates an E0a proposal).
- Mapping records: `data/<company>/model/mappings/<id>.json` (file pattern, sheet, header row, version, columns: source column, target table, target field, transform; state proposed|approved|retired; proposed_by agent run, approved_by, approved_at). A new version when the layout changes; old batches keep theirs.
- Prompts go through the existing router and egress (column names and a few profiled examples with digits removed; never rows).
- Tests: invented target rejected; approved mapping retrieved as example; profile finds header row and thousands; model-change proposal created; company skill override wins.

### E0c Spreadsheet intake into the warehouse
- **Land**: every uploaded or dropped file is kept untouched under `data/<company>/landing/originals/` with sha256, received time and sender; a duplicate (same hash) is recognised.
- **Census** screen "Data intake" `/centre/data/intake`: files by source with state (new, profiled, waiting for mapping approval, loaded, rejected: totals differ, quarantined), owner and last load.
- **Load**: apply the approved mapping version; write `source_batches`, `source_records` (with sheet, row, cell locator and recorded_at) and the target observation rows into the E0a DuckDB warehouse; compute **control totals** (row count and the totals the sheet states, found by the profile) into `batch_control_totals`; a mismatch rejects the batch with a plain message and nothing reaches the observation tables.
- **Layout change**: a file matching a known pattern whose columns differ triggers a new mapping proposal from the data agent instead of a silent load.
- Mapping approval on the same screen: the proposed mapping shown column by column with Accept / Not this (reuse the L2 Accept pattern where it fits); only the sheet owner or a data engineer seat may approve.
- Tests: duplicate file recognised; load writes batches, records with locators and observations; totals mismatch rejects with nothing loaded; layout change creates a proposal; recorded_at set.

### E0d Synthetic workbooks and the evaluation set
- About twenty messy synthetic workbooks for the fictional "Evergreen Office" (positions, valuations, cash, NAV, capital calls, a benchmark sheet), with traps: the same fund under two names, values in thousands, day and month swapped, a merged header row, a totals row at the bottom, a renamed column between months, a sheet marked In Progress, one file whose totals do not add up.
- For each: the expected mapping (target table and field per column) and expected control totals, in `tests/v1/fixtures/e0d/expected/*.json`.
- `tools/eval_data_agent.py <company>` runs the data agent's profile and mapping over the set and prints a score per trap (mapping accuracy, invented targets, totals caught); exits non-zero below the agreed bar.
- Also copied into the demo company's landing folder by `tools/seed_e0_demo.py` for the walk-through.

### Order
Wave 1: E0a and E0d in parallel. Wave 2: E0b and E0c in parallel once E0a's catalogue helpers exist. Fable reviews each wave; one fix round; rebuild and restart 8400.
