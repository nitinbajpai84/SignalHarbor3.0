# Review E0 · Data foundation (E0a, E0b1, E0b2, E0c1, E0c2, E0c3, E0d, E0e)

Reviewed 9 Oct 2026 against `docs/plan/V2-CARDS.md` (facts, settled, recommendations 1-9) and `docs/plan/V2-BUILD.md`. Code read, not run live; no code edited, no servers, no live data.

## Verdict

**Not yet.** The pieces are sound on their own (append-only loads, control totals before any observation write, core model protected, proposer never approver, secrets only in the keys file), and the evaluation set passes at 100%. Three contract mismatches stop the demo: the intake screen cannot show a file, the seeded FX rule and series key do not meet, and the test files break each other when run together. One fix round.

## Tests run

- `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e0a.py test_e0b1.py test_e0b2.py test_e0c1.py test_e0c2.py test_e0d.py test_e0e.py -q`: **48 passed, 2 failed** (`test_e0c1.py::test_states`, `test_e0c1.py::test_routes_upload_scan_and_seats`). Both pass when `test_e0c1.py` runs alone; see blocker 3.
- `python tools/eval_data_agent.py evaltmp` on a tmp data root: PASS, mapping 100% in every trap, 0 invented targets, 3/3 in-progress, 1/1 totals mismatch. It needed `PYTHONPATH=.` and a company created first; see should-fix 7.

## Blockers

### 1. The intake file page cannot render a real record (E0c1 ↔ E0c3)
`sh_platform/v1/e0c_landing.py:139-148` (`listing`, `detail`) return the raw record; `ui/src/v1/e0c/api.ts:16-23` and `FilePage.tsx:24-83` expect a different shape.
- List: UI links on `files[].id` (`IntakePage.tsx:39-40`); the record has `file_id`. Every link goes to `/centre/data/intake/undefined`.
- Detail: UI reads `d.control_totals.length` (`FilePage.tsx:68`) which is absent, so the page throws after any profile; `d.mapping` is never served, so Accept / Not this and the "Load this file" button (needs `m.state === "approved"`) never appear; `profile.columns[].name` is served as plain strings; `load_result{state,message,held_back[]}` is served as `last_load{status,message,held_back[{row,reason}]}`; `can_act` and `can_decide` are absent so "Read this file" never shows.
- Scenario: Mei uploads `pos_2026_09_thousands.xlsx`, opens the list, clicks the file: blank page; even by URL, after "Read" the page crashes.
- Fix (one place, E0c1 since the mapping join must be server-side): in `detail` and `listing` add `id = file_id`; build `profile.columns` as `[{name, date_format}]` from `column_info`; join `mapping` = `e0b_mappings.get_approved(plane, name, sheet)` or the newest proposed record for the same pattern and sheet, with `can_decide` from `e0b_mappings._who_may_decide`; `control_totals` from `last_load.control_totals` renamed `expected -> in_file`; `load_result = {state: status, message, held_back: [f"row {r}: {reason}"]}`; `can_act = DATA_ENGINEER in seat_of(viewer)` (pass the viewer into `detail`). Then `api.ts` stays as it is.

### 2. The seeded FX rule and the FX series never meet (E0e ↔ settled rule keys ↔ E3d)
`tools/seed_evergreen.py:226-227` signs `fx_fixing` with `{"series_key": "FX:USDSGD", "fixing": "month_end"}` and `:238` writes `market_observations.series_key = "FX:USDSGD"`. Settled section: `fx_fixing {"fixing": "WMR_4PM"}` and series keys like `"FX:USDSGD:WMR_4PM"`. `sh_platform/v1/e3_calc.py:58-65` selects `series_key like '%' || fixing || '%'`, so with the seed it finds nothing and returns `None` with "cannot be converted".
- Scenario: CIO opens the September brief and switches to SGD: every line says it cannot be converted. E3d's Evergreen totals test in SGD cannot pass on the seed either.
- Fix: seed `fx_fixing` parameters as `{"fixing": "WMR_4PM"}` (keep `series_key` if wanted, as `"FX:USDSGD:WMR_4PM"`) and write both fixings with `series_key = "FX:USDSGD:WMR_4PM"`.

### 3. `test_e0c1.py` fails when run with the other E0 tests (E0c1 tests)
`tests/v1/test_e0c1.py:28-36` stubs `e0b_tools` with `monkeypatch.setitem(sys.modules, ...)`. `e0c_landing.profile` does `from sh_platform.v1 import e0b_tools`, which takes the attribute already set on the package when the real module was imported earlier (by `test_e0b2.py`), so the real `profile_sheet` runs on the test's `.csv` bytes, openpyxl raises `InvalidFileException`, the file is quarantined and both tests fail (`test_states` with Refused 422, `test_routes_upload_scan_and_seats` with `KeyError: 'state'`).
- Fix: also `monkeypatch.setattr(sh_platform.v1, "e0b_tools", tools, raising=False)` (same for `e0c_load`), or stub `e0c_landing.profile_sheet` through a module-level indirection. The same mismatch is a product gap too: see should-fix 1.

## Should-fixes

1. **CSV is accepted but cannot be read.** `e0c_landing.py:27` lists `.csv` as a spreadsheet and the upload control accepts it (`IntakePage.tsx:30`), but `e0b_tools.profile_sheet` (`e0b_tools.py:138`) is openpyxl-only, so every CSV is quarantined with "We could not read this file". Either drop `.csv` from `SPREADSHEETS` and the accept list, or read CSV in `profile_sheet` and `e0c_load._read` with the `csv` module.
2. **Rule parameter keys differ from the settled list.** `seed_evergreen.py:222-225`: `estimate_use {"allowed": [...]}` (settled: `allowed_in`), `statement_due {"business_days": 10}` (settled: `business_days_after_month_end`). `e5_pulse.py:149` currently reads `business_days` so Pulse works by luck; nobody reads `estimate_use` yet. Align the seed with the settled keys (and E5a's reader in its own review) so the next card does not pick a third spelling.
3. **Census state lies after a quarantined or repeated load.** `e0c_landing.py:180-181` `_LOAD_STATES` maps only four statuses; `e0c_load` also returns `quarantined` and `already_loaded`. An In Progress sheet, an unreadable cell, or a failed write leaves the file in its old state (for example `profiled`) while `last_load.message` says it was quarantined. Add `"quarantined": "quarantined", "already_loaded": "loaded"` (E0c2's note asks for this; nobody has done it).
4. **A rejected batch is deleted on retry, leaving orphans.** `e0c_load.py:255` `delete from source_batches ... validation_status <> 'loaded'` erases the earlier rejected batch but not its `batch_control_totals` rows, and it erases history (recommendation 5 spirit). Keep the old batch and insert a new one with a reference suffixed by attempt number, or by `wh.now()`.
5. **The batch never records which mapping version it used.** `e0c_load.py:263` writes `sheet_mapping_id = mapping.get("sheet_mapping_id")`, which no mapping record carries (`e0b_mappings` records have `id = "map-..."`, and the column is UUID), so it is always NULL and "old batches keep their version" survives only in free text (`validation_summary`). Either write a `sheet_mappings` row at approval (`e0b_mappings._decide`) with a UUID id and store it on the record, or document that the warehouse link is deferred and keep `mapping_id`/`version` in the batch summary as structured JSON.
6. **The sheet owner can never approve.** `e0c_load._ask_for_proposal` (`e0c_load.py:185`) saves the proposal without `owner`, so `e0b_mappings._who_may_decide` (`:116-119`) only ever lets the data engineer seat in; the "sheet owner" rule in the card is dead. Pass `"owner": rec.get("owner")`. Also `e0b_tools.propose_mapping:282` computes `by` from the viewer and then hard-codes the agent at `:285` (dead variable); decide which and delete the other.
7. **`tools/eval_data_agent.py` cannot import the agent when run as documented.** No `sys.path.insert(0, ROOT)` (unlike `seed_evergreen.py:28`), so `python tools/eval_data_agent.py <company>` from the repo root prints "data agent not built yet" and exits 2 even though `e0b_tools` exists. Also the company must already exist in the entitlement store (`e0b_tools._plane` -> `PlaneStore.plane_for` raises `LookupError: unknown company`), which the usage line does not say. Add the path insert, print the real ImportError, and say "company must exist" in the docstring.
8. **The model path is dead in the real intake flow.** `e0c_load._ask_for_proposal` calls `propose_mapping(plane, profile, viewer)` without `model`, so columns the synonym rules miss are always `ignore` in production, never sent to the router. Pass `get_model(state, plane)` as E0b2's note says callers do, or state in the landing note that intake is rules-only for phase 1.
9. **Report `issued_at` is "now", not 3 Oct.** `e1_reports.issue` stamps `issued_at = wh.now()` (`e1_reports.py:104,128`); the seed's `issued` (`seed_evergreen.py:283`) is only used by the SQL fallback. The brief's "Issued 3 Oct" column will show today's date on a real seed. E1c should accept an optional `issued_at`, or the seed should go through the fallback for the back-dated demo and say so.
10. **`e0a_catalogue._breaking` reads the wrong column key.** `e0a_catalogue.py:496` uses `c.get("source_column", f)`; E0b2 records store `source`, so the breaking-change message names the target field instead of the sheet column. Use `c.get("source") or c.get("source_column")`.

## Nits

- `seed_evergreen.py:152-156` re-implements `e1_write.org_id`; the settled section says reuse it. Replace `_org_id` with `e1_write.org_id(plane)`.
- `e0b.permissions.yaml` opens approve/reject to every role at the YAML layer (the code gate is what refuses). Narrow to `[company_admin, analyst]` plus whatever role a sheet owner can hold, so default-deny reads true.
- `seats.py` makes every analyst both architect and data engineer, so "head of data approves, data engineer proposes" is by account only (E0a landing note says so). Worth a line in the Evergreen guide so a demo driver does not expect Leo to be refused as approver.
- `e0c_load.py:329` updates `source_batches.validation_status` to `quarantined` after a failed observation write with no event row; `source_records` written in that attempt keep `quality_status = 'loaded'`. Mark them `quarantined` in the same statement.
- `e0c_routes.py:69-73` `GET /files` registers inbox files on every read, including by a sponsor; harmless (own plane) but the sender is "Inbox folder" and the owner becomes that string. Consider owner = source folder name.
- E0d expected JSON and E0b2 agree; the runner's docstring still says "Planned contract"; update to "Contract (E0b2 landed)".
- `e0c.permissions.yaml` header says "or ops manager seat" but the code only checks `DATA_ENGINEER` (`e0c_routes.py:35`); same roles today, so fine, but say one thing.

## Checked and fine

- Append-only: `e0c_load` writes observations only through `e1_write.record_many` with `supersedes` links and `recorded_at = now`; `source_records.recorded_at` set; nothing updates an observation. Control totals are computed on parsed rows before any observation write, and a mismatch writes only the batch and its totals rows (status `rejected_totals`) with a plain message naming the measure and both figures (`test_e0c2` covers it).
- Core model: `_merge` refuses a retype or null/pk change of a core column; core-table blocks can only add; extension columns must be optional or defaulted; sandbox on a copy; warehouse add-only. Proposer never approver, by account id. Reject needs a reason. Every step in `model/log.json`.
- Mappings: every target validated with `has_field` at proposal (`e0b_tools`) and again at save (`e0b_mappings.save_proposal`); invented targets named in `rejected`; layout change becomes the next version; approval retires the earlier approved version; reject needs a reason.
- Egress: `profile_sheet` reads locally; the model prompt (`_model_targets`) carries column names, kinds and `fit(...)`-minimised context only, no values, through `router.route`.
- Evergreen seed: `users.external_identity_id = account id`; one account per role, passwords only in `_control/seed_credentials.txt`, nothing printed; alias "EG Growth Fund I" and administrator code 4471 approved; cash in `position_snapshots` on the Cash instrument, `accounting` vs `operational`, 8 Oct, Entity B 12,400 apart and the Trust 1,800 inside tolerance, exactly as `e3_recon.cash_by_entity` reads them; Fund A 10,000,000 estimated, valued 30 Sep, received 2 Oct, recorded before the 3 Oct cutoff; NAV 16.4m untouched by estimates; September report issued through `e1_reports.issue` with lines 10.00m / 6.40m / 41.20m / 57.60m and one evidence pointer per line; the 10.18m statement is not loaded; `--reset` asserts the evergreen plane. Idempotent on `legal_entities` count.
- Tenant: every seeded and loaded row carries `org_id(plane)`; the warehouse file is per company.
- E0b1 skill under the loader cap with the six v2 rules and three worked mappings.

## Fixes after review (9 Oct)

Blockers
1. Intake file page: `e0c_landing.listing` adds `id`; `detail(plane, file_id, viewer)` now serves `id`, `profile.columns[{name, date_format}]`, `mapping` (newest proposed if at least as new as the approved one, columns as `source_column/target_table/target_field/transform` with the transform in words, `can_decide` from `_who_may_decide`), `control_totals{measure,in_file,loaded,passed}`, `load_result{state,message,held_back[]}` and `can_act` (data engineer seat). The route passes the viewer. `api.ts` unchanged.
2. FX: seed signs `fx_fixing {"fixing": "WMR_4PM", "series_key": "FX:USDSGD:WMR_4PM"}` and both fixings use series key `FX:USDSGD:WMR_4PM`.
3. `test_e0c1` stubs now also patch the package attributes, so the seven E0 files pass together.

Should-fixes
1. CSV is profiled and loaded: `e0b_tools.read_grid` (Excel or CSV, sheet named after the file) is used by `profile_sheet` and `e0c_load._read`. Tests added.
2. Seed keys now `allowed_in` and `business_days_after_month_end`. Note: `e5_pulse.py:149` reads `business_days` (E5 card; see below).
3. `_LOAD_STATES` maps `quarantined` and `already_loaded`.
4. A rejected or quarantined attempt is kept; the retry inserts a new batch with reference `...#n`; the already-loaded check covers retried references.
5. The warehouse `sheet_mappings` link is deferred: the batch keeps `{mapping_id, mapping_version, message}` as JSON in `validation_summary` (a rejected batch keeps its plain sentence). Always NULL `sheet_mapping_id` stays and is documented in the `e0c_load` docstring.
6. Proposals carry `owner` (the file's owner); dead `by` variable deleted in `propose_mapping`.
7. `eval_data_agent.py` inserts the repo root on `sys.path`, prints the real ImportError, docstring says the company must exist; "Planned contract" updated.
8. The model path is live: the load route passes `_model(request, plane)` through `e0c_landing.load` and `e0c_load.load(model=)` to `propose_mapping` (rules-only when None).
9. Report date: `e1_reports.issue` still stamps now, so the seed writes the same rows with `issued_at` 3 Oct through its own writer (no UPDATE). See "Needs another card".
10. `_breaking` reads `source` first.

Nits done: seed uses `e1_write.org_id`; `e0b` approve/reject YAML narrowed to `[company_admin, analyst]`; permission headers say data engineer seat; guide notes Leo is not refused as approver; failed observation write marks that batch's `source_records` `quarantined`. Not done: inbox owner naming; `scan_inbox` still uses "Inbox folder".

Extra (coordinator, from the E5/E6 review): seed approves manager_email identifiers "Fund A - Evergreen Growth I", "Evergreen Growth I", "Fund B - Evergreen Liquid Book" (the name printed on Fund B's PDF; mapped to the seed's Fund B, Evergreen Income II), "Fund B - Evergreen Income II", "Evergreen Income II"; test asserts `e2_match.resolve` returns approved.

Needs another card
- E1c (`e1_reports.issue`): accept an optional `issued_at` (and use it for run times), so the seed can use `issue` again.
- E5a (`e5_pulse.py:149`): read `business_days_after_month_end` (fall back to `business_days`).
- E2c/E3: Fund B's PDF header says "Evergreen Liquid Book" while the value belongs to Evergreen Income II; fix the fixture text or confirm the mapping.
