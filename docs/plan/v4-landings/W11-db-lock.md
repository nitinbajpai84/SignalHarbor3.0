# W11-db-lock: one warehouse connection per company in the server

## What changed
- `sh_platform/v1/wh.py`
  - **Server mode** (`wh.serve()`): the process keeps one read-write DuckDB connection per company file (`_SHARED`), and every `wh.connect(plane)` returns a cursor on it. Request handlers, the b6 scheduler thread and background doc jobs no longer open the file themselves. `with wh.connect(plane) as con:` still works: closing the cursor leaves the shared connection open. Creating the shared connection happens under the existing `_LOCK`.
  - **Busy open is retried**: every open (shared, schema setup, and the plain per-call open used outside the server) is tried 6 times, 0.5 s apart (about 3 s in total).
  - **Plain message for scripts**: while the server holds the file it writes `evidence.duckdb.server` ("the Signal Harbor server (process N, started ...)"). Once the retries run out, a script gets `wh.Busy`: "The company warehouse <path> is open in another program: the Signal Harbor server (process N, started ...). Stop the server, or do this through the app, and try again." With no marker file, the message says it is most likely the Signal Harbor server.
  - `wh.release()` closes the shared connections and removes the marker files. It runs at server stop, at process exit (`atexit`) and in `reset_cache()`.
- `sh_platform/v1/b6_schedule.py`: `start()` calls `wh.serve()` (it runs once at server start from `app._install_build_scheduler`), and `stop()` calls `wh.release()`.

## Where the company warehouse is opened (all checked)
- Almost every v1 module opens it through `wh.connect`, so they are all covered.
- `e0a_catalogue._migrate` opens it with a direct `duckdb.connect` on the same file, in the same process. DuckDB reuses the open database for that connection, so it is fine.
- `b6_run._sandbox_con` uses a separate `sandbox.duckdb` file.
- `sh_platform/warehouse/__init__.py` and `tools/reset_v1.py` use the 1.0 `company.duckdb`, a different file.
- **`tools/seed_v3_demo.py:275` and `tools/seed_evergreen.py`** open `evidence.duckdb` directly. While the server is running they still get DuckDB's raw error. Follow-up for their owner: open the file through `wh.connect`.

## Cause of the Tally error
Within one process, connections to one file already share the database. 8 threads opening and closing their own connections ran with no error on this machine (duckdb 1.5.5). So the "used by another process" error came from a **second process**: a second server on the same data root (a dev server and the 8200 production build), or a seed script or test run against `data/`. With this change the server never opens the file twice, and the second process now gets the plain message above, not a raw IOException.

## Follow-ups (files outside this card)
- `sh_platform/app.py` `_install_build_scheduler`: with `SH_SCHEDULER=off` the scheduler, and so server mode, does not start. Call `wh.serve()` in `_start` before the `SH_SCHEDULER` check so the server always uses the shared connection.
- `sh_platform/v1/n1_tally.py` `_save`: catch `wh.Busy` alongside the IOException check. Busy now arrives after `wh` has already retried for about 3 s, so the extra retry there can drop to one try.
- Two servers on one data root still fight over the file. Run one server per data root.

## How to see it
1. Start the server as usual, then open `data/<company>/warehouse/`. Expect `evidence.duckdb.server` naming the server's process.
2. While the server runs, run a script that writes through `wh.connect`. After about 3 s it stops with the plain message above.
3. Stop the server. The marker file is removed.

## Tests
- New file `tests/v1/test_wh_lock.py`, 3 passed:
  - 8 threads × 30 writes in server mode: 240 rows, no errors, one shared connection.
  - 4 threads × 20 writes outside server mode: 80 rows.
  - A second process while the server mode holds the file gets `wh.Busy` with the server named.
- Regression: `tests/v1/test_a5.py`, `test_e0e.py`, `test_b4.py`, `test_b6.py`, `test_b6_diagram.py` and `test_b6_run.py` all pass (39 passed).
- No TypeScript changed, so `tsc` was not run.
- Backups: `.sh-tmp/wh.py.bak-W11-db-lock` and `.sh-tmp/b6_schedule.py.bak-W11-db-lock`.

## Review
Verdict: pass, no code changes needed. Reran `test_wh_lock.py` and `test_b6.py`: 12 passed. Scope held to `wh.py`, `b6_schedule.py` and the new test. Wording of the Busy message is plain and names the server. No emoji or Claude attribution.
Open items (outside the card):
- `app.py`: call `wh.serve()` before the `SH_SCHEDULER=off` check, or server mode is skipped.
- `n1_tally._save`: catch `wh.Busy`.
- `tools/seed_v3_demo.py`, `tools/seed_evergreen.py`: go through `wh.connect`.
- The pipeline script text written by `b6_schedule.py` (line ~160) and `e0a_catalogue.py:245` open `evidence.duckdb` directly. In-process the latter is fine; the generated script run as a separate process while the server is up will still show DuckDB's raw error.
- Nitin's question (mod showing running subagents, tokens, approximate cost, task) was not built; it needs its own card.
