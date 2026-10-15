# V6-builder (designs H7, H8, H9): Span the builder in the Pipelines step

## Built
- `sh_platform/v1/b11_builder.py`: the builder. Store `build/<pid>/builder.json` (rounds, benchmark, thread, needs, settled). No model call anywhere.
  - **Connect** each source as the newest APPROVED pack says (`b6_plan`): connectors through `c5_connect` (test, dry run; default deny and egress log unchanged), uploads checked against landed files (`e0c_landing`), PDF sources against loaded statements (`e2_intake`) and the marked fields.
  - **Confirm against the intent** (`build/<pid>/systems.json`): a mismatch of file name, columns or host is raised once with the intent's value, the pack's value and what was seen beside it; `settle` writes the answer to the system map and the pack together (logged on the plan; the version does not change) and it is never raised again.
  - **Run on a copy** by itself, once per approved pack version, through `jobs.handlers.run_pipeline` (job queue when there is one, inline in simple mode). It runs that approved version, never a newer draft.
  - **Action items** only for a failed connection (to the head of data, else the data team) and a missing sample (to the source owner, else the raiser): `pulse_cards` registered as an `e5_pulse` source; they close when a re-check passes.
  - **Benchmark**: upload last month's report (read locally by `context_docs.reader`, original kept by `e0c_landing`) or pick a signed report version (`e1_reports.as_issued`, figures the person may not see are left out).
  - **Variance** line by line against the run: key figures (pack `key_figures`, by group too), the benchmark returns and each leg's weight from `b9_verify.comparison`. Each line is Matches, Explained (revisions that add up to the difference, with evidence and the a5 trail id) or Unexplained.
  - **Go live** (schedule from the pack, `run_pipeline` live) or **Send back**: an `agents/handoff` item (`builder` -> architect, kind `variance`) with the unexplained lines as facts; it shows in the data team's Action and on the project timeline. The architect **issues pack version N+1** (`issue_version`: changed tables' SQL, before and after kept; proposed through `b6_plan.new_version`, approved by the head of data). When it is approved the builder reruns by itself and says whether the variance is cleared.
- `sh_platform/v1/b11_routes.py` + `b11.permissions.yaml`: GET `/api/v1/build/p/{pid}/builder`, POST `start`, `recheck`, `settle`, `benchmark`, `go-live`, `send-back`, `pack`. Routes are picked up by the `*_routes.py` glob.
- UI `ui/src/v1/b11/` (BuilderPanel, api, css, test), shown at the top of the Pipelines step (`b8/PipelinesRoom.tsx` renders it; the old stage cards, controls and run log stay below). The screen starts the builder when it opens (no click), shows the thread of the two Span roles, the sources, the run, the benchmark ask, the variance tables, Go live / Send back, and for the architect the form that issues the next version.
- Shared fixes: `agents/handoff.py` (route `builder`), `jobs/handlers.py` (`run_pipeline(..., version=)`), `b9_verify.py` (`plain_name`, `label` on comparison rows, review form defaults from the pack), `b9verify/format.ts` (numbers, shared), `b9verify/VerifyPanel.tsx`, `b6/Steps.tsx`.
- **WALK 9**: the send-for-review form takes portfolio, benchmark code and month from the pack's `benchmark` block first (the data engineer cannot see portfolios, so it was empty), then the old defaults.
- **WALK 10**: control totals grouped (10,500,000); plan approval time as "11 Oct 2026, 04:35" (`when`).
- **Series keys**: `IDX:GLEQ:SYN` reads "Global equity index", the spread part "Global equity index plus a spread" (names from `k9_daily.SERIES`; the pack may rename legs in `benchmark.names`). The row `component` key is unchanged because the fix flow uses it.

## How to see it
Testing mode, simple mode, a project whose latest plan is approved: open `/centre/build/p/<pid>/pipelines` as the data engineer (analyst). Put the pack fields below in the approved plan to see every state. Tests: `tests/v1/test_b11_builder.py`, `ui/src/v1/b11/b11.test.tsx`.

## Pack and intent contract (for the architect and North cards)
Optional keys; nothing is invented when absent. Source: `arrives {how: upload|sftp|mailbox|sharepoint|database, connector, file, columns, host}`, `fields [{name, page}]` (PDF), `landing_source`. Plan: `key_figures [{label, table, column, agg, by?, match?, unit?}]`, `benchmark {portfolio, code, month, names?, tolerance?}`. Intent system map: `build/<pid>/systems.json` `{source code: {name, file, columns, host, how, frequency, owner}}`. If the architect card stores them elsewhere, change `pack_of`/`systems_of` only.

## Tests
- Python: `tests/v1/test_b11_builder.py` 11 passed. With `test_b9_verify`, `test_handoff`, `test_b6`, `test_b6_run`, `test_b6_run_lock`, `test_w3_two_modes`, `test_g1_gate`: 92 passed, 4 skipped (production-mode tests).
- UI: `npx vitest run src/v1/b11 src/v1/b9verify src/v1/b8 src/v1/b6`: 38 passed. `tsc --noEmit`: clean for my files; one error in `src/v1/workbench/ChangeBar.tsx` (another card's file).
- Not run: vite build (integration), any live model or Real use.

## Mount lines
- `sh_platform/app.py`: none (`*_routes.py` and `*.permissions.yaml` are discovered).
- `ui/src/v1/router.tsx`: none (the existing `build/p/:projectId/pipelines` route renders `PipelinesRoom`, which now includes the builder).
- Optional, integration: after `b6_plan.approve` succeeds in `b6_routes.py`, call `b11_builder.on_approved(plane, pid)` so the run starts at the moment of approval even if nobody opens the page (it never raises; the screen also starts it on open).

## Difference for Nitin's approval
1. A connection correction edits the approved pack's source in place (logged on the plan, version unchanged) instead of making a new approved version, because it is a connection detail and the person who settles it is the data team.
2. PDF sources are "connected" when statements are loaded and fields are marked; the builder does not re-read them here (reading stays in the evidence queue).
3. A `database` source is reported as a connection failure ("not set up in this product yet"): there is no database connector in c5.
4. A benchmark upload is read as text lines "label then number or %"; scanned PDFs need the local picture reader.
5. The builder section sits above the existing Pipelines controls rather than replacing them (never drop a feature); the old "Try it on a copy / Go live" buttons remain.
6. The new-version form shows the table's SQL to edit (the architect's own agent card may fill it instead).

## Open items
- Explained variance covers revisions of valuations (sum or single match). Other explanations (timing, FX) are left unexplained until a rule exists.
- The head of data seat and the seed person are the V6-design-fixes card's.
- No per-source "next run" times in the connection rows (the pack schedule is shown at Go live).

## Review
Checked against BUILD-FLOW-V6 step 3 and "never ask twice", designs H7 to H9, maker-never-checker and access.
- **Fixed:** the start at approval (`on_approved`, no viewer) computed the variance with no viewer, so the portfolio and leg figures were refused or failed and the round was lost or the variance wrong. Now that run skips the benchmark check, and the next start by a person (the page opening) checks it once and posts the result in the thread. New test `test_on_approved_runs_without_a_viewer_and_the_page_checks_the_benchmark`. Builder, handoff and b9_verify tests: 37 passed.
- **Holds:** a mismatch is raised once (settled key) with the intent's value beside it; the fix writes both the system map and the pack. The architect's version 2 goes through `b6_plan.approve`, which refuses the proposer, and the test covers that. Go live anyway is in H8. The signed benchmark leaves out figures the viewer may not see. The GET route correctly leaves out `head_of_data`, which opens no route on its own.
- **For Nitin:** difference 1 changes an approved pack without the head of data, and the spec says "Approved means locked". The change is logged and limited to the file, columns and host. Accept it, or route connection corrections through a new version.
- **Not this card:** the failure in `test_role_matrix_intents` (head_of_data list) belongs to V6-design-fixes, and the error in `ChangeBar.tsx` belongs to the workbench card.
- Backups: `.sh-tmp/*.bak-v6-review`.
