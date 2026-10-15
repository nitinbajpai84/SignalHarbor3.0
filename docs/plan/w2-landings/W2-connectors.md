# W2-connectors: landing note

## Built
- `sh_platform/v1/c5_connect/`: `spec.py` (spec per connector: kind, host, schedule, credential variable NAMES, source code, params, file pattern; validated, stored in the company plane at `connectors/specs.json`), `kinds.py` (IMAP over TLS attachments only and read only, SFTP pull, Microsoft Graph for SharePoint/OneDrive), `ops.py` (test, dry run, fetch, health, map feed, run_due).
- `sh_platform/v1/c5_routes.py` + `c5.permissions.yaml` (data engineer seat: company_admin and analyst).
- `ui/src/v1/c5/` (`ConnectorsPage.tsx`, `api.ts`, `routes.tsx`, `c5.test.tsx`).
- Fetch lands through `e0c_landing.receive` (source_code = the connector's, sender `connector:<id>`), so profiling, mapping and loading run unchanged. Same bytes are never landed twice (hash), and a checkpoint (IMAP uid, or seen keys for SFTP/Graph) only moves after a clean run. Per-run state: `connectors/runs/<id>.json`.
- Egress: every connection is gated and logged in the existing egress log (module `c5_connect`, kind imap/sftp/graph, host, byte count, never a credential or file name). Default deny: the `c5_connect` internet switch must be on and the host on the company's internet list. Graph needs `graph.microsoft.com`, `login.microsoftonline.com` and the pre-signed download host.
- Secrets: only environment variable names in specs; values are read at the moment of use and never stored, logged or returned. Errors keep the exception type only.
- No edit to any existing file; no backups needed.

## How to see it
Set the company's internet list (Settings, Egress) to include the host and turn on `c5_connect`; set the named variables in the server environment; open Settings, Connectors (after mounting); Add, Test connection, Dry run, Fetch now. Landed files show in Data intake as New.

## Tests
`python -m pytest tests/v1/test_c5_connect.py` (10 passed): spec rules, default-deny egress and log, IMAP attachments/read only/idempotent/duplicate bytes, failure without secrets, SFTP idempotent, paramiko-missing report, Graph with download host rule, health/late/map feed, routes and permissions file coverage.
`npx vitest run src/v1/c5` (3 tests): list with state in words, empty state and dry run, save sends names not secrets.

## Mount lines (for the integration step)
1. `sh_platform/app.py`: `from sh_platform.v1 import c5_routes` and `app.include_router(c5_routes.router)` beside `e0c_routes`.
2. Permissions: add `sh_platform/v1/c5.permissions.yaml` to whatever list loads the other `*.permissions.yaml` files (same as `e0c.permissions.yaml`).
3. `ui/src/v1/router.tsx`: import `routes as c5Routes` from `./c5/routes` and spread it into the v1 routes (path `settings/connectors`); add a Settings link "Connectors" in `ui/src/shell/`.
4. Map health: in `k3_map.health`, after the per-source rows, merge `c5_connect.ops.map_feed(plane)` (`{source_code: {connector, is_late, failed, last_ok}}`) so a late or failed connector marks its source late.
5. Scheduler: call `c5_connect.ops.run_due(plane)` from the existing poll (same place as `e0c_landing.ensure_poll`), or leave connectors on "manual" and use Fetch now.

## Open items
- paramiko is not installed here; SFTP reports "unavailable" until it is added to requirements (unknown hosts are refused: the server needs the host in its known_hosts).
- Google Drive (optional in the card) not built.
- IMAP holds attachments in memory per run (25 MB cap per file in landing); stream if mailboxes grow.
- Graph uses client credentials (app registration) only; no per-user sign-in.
- SFTP/IMAP connections are logged per connection, not per command.

## Review (security, 11 Oct)

Verdict: pass after two fixes.

- Access: every route calls `require_seat(DATA_ENGINEER)` (company_admin, analyst) and matches `c5.permissions.yaml`; a test checks the two agree.
- Egress: each connection goes through `Gate` (c5_connect switch, default off, plus host allowlist) and is logged before it is made. Graph sends the bearer token only to graph.microsoft.com, follows nextLink only on the same host, and checks and logs the pre-signed download host. No redirects followed.
- Secrets: only variable names are stored. Values are read at use, and errors log the exception type only. **Fixed:** an analyst could name any server variable (for example `SH_JEV_API_KEY` or `SH_MCP_TOKEN`) as the IMAP user or Graph secret and send it to an allowlisted host. Credential variables must now start with `CONN_`. The tests and the screen placeholder are updated.
- Correctness: **fixed** CR/LF in params or file pattern (an IMAP command could be smuggled through the mailbox name, breaking read only). Control characters are now refused. Dedupe goes through the e0c_landing hash, and the checkpoint only moves on a clean run.
- Data locality: specs, runs and landed files live in the company plane, never in the repo.
- Tests: `tests/v1/test_c5_connect.py` 11 passed (one new test covers platform secrets and control characters). `npx vitest run src/v1/c5` 3 passed.
- Open (minor): the screen offers SFTP password only, not `key_file`, though the API takes it. The first IMAP run fetches the whole folder (UID 1:*) into memory. Setting up a deployment now needs `CONN_*` variable names.
