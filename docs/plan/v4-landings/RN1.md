# RN1 - "Try it on a copy" answered 403 on a long-running server

## Root cause
In server mode (`wh.serve()`, used by `tools/serve_test.py` and the real server) the process keeps one read-write DuckDB
connection open on `warehouse/evidence.duckdb` for its whole life. `b6_run._sandbox_con` made the sandbox with
`shutil.copyfile(evidence.duckdb, sandbox.duckdb)`. On Windows DuckDB holds the file without read sharing, so the copy raises
`PermissionError: [Errno 13] Permission denied: ...evidence.duckdb` (the same reason `cp` said "Device or resource busy").
`b6_routes._run` caught every `PermissionError` as "no company space" and answered 403 "Your company space could not be opened".
A fresh TestClient never calls `wh.serve()`, so the file was closed and the copy worked; that is why it passed there.

## Fix
- `sh_platform/v1/b6_run.py`: the sandbox is filled through DuckDB itself (`ATTACH sandbox.duckdb` on the shared connection,
  `COPY FROM DATABASE`, `DETACH`), so no OS copy of an open file. One retry after 1 s on an OS/IO error. Sandbox runs take turns
  on a module lock (one `sandbox.duckdb` per company; another project unlinking it mid-run was the second way to hit the error).
- `sh_platform/v1/b6_routes.py`: only the errno-less `PermissionError` from `_plane` keeps the access message (403). Any OS error,
  `wh.Busy` or DuckDB IO error is logged and answered 503 "The run could not start because a data file is busy. Try again in a minute."
- `wh.py` unchanged.

## Test
- New `tests/v1/test_b6_run_lock.py`: a sandbox run (twice) while `wh.serve()` holds the warehouse open succeeds, the live
  warehouse is untouched and the copy has the live tables; the route maps an OS `PermissionError` to 503 and the no-company one to 403.
  Failed before the fix with the exact `PermissionError` above.
- `test_b6*`, `test_wh_lock`, `test_x1`, new test: 40 passed.
- Live: `make_test_env rn1`, `serve_test --port 8699 --scheduler`, Mei signed in, `POST .../run?mode=sandbox` twice: 200 (1.0 s, 0.4 s),
  run status ok. Server stopped. 8502 / Nitin's data not touched.

## How to test
On 8502 after a restart (the running server still has the old code): Build > Pipelines > "Try it on a copy" as Mei.

Backups: `.sh-tmp/{b6_run,b6_routes,wh}.py.bak-rn1`.
