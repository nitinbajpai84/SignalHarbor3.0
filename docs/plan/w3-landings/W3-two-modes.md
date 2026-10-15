# W3-two-modes: landing note

Reference: `docs/architecture/sh-local-vs-production.json` and `sh-detailed-architecture.json`. Simple mode behaves exactly as before (no route or screen changed). Production mode is on when `DATABASE_URL` and `REDIS_URL` are both set; only one set stops the server at start-up with a plain message (`sh_platform/mode.py`, checked in `create_app`).

## Built
- `sh_platform/mode.py`: `mode()`, `production()`, `check()` (raises `ModeError`).
- `sh_platform/state/__init__.py`: `StateStore` adapter. `FileStore` (simple: today's JSON files, atomic write, per-file lock, version = hash of the file, so files on disk keep their shape) and `PgStore` (production: psycopg, one table `sh_state_<kind>` per store kind, JSONB document, bigint version, `put(expected=...)` compare-and-set raising `Conflict`, optional caller transaction via `conn=`). `update()` is the read-change-write retry loop. kind = the company-folder area, key = `<company>/<path in the area>`.
- `sh_platform/state/kv.py`: Redis client, sliding-window rate limit, outage-breaker map, answer cache helpers.
- `sh_platform/jobs/`: `JobQueue` with `LocalQueue` (simple: `submit` runs the handler on the spot, `enqueue` uses one background thread) and `RedisQueue` (production: ready list, delayed set for retries with doubling backoff, failed list, unique `key`, `call()` waits for a result). `handlers.py`: `b6.tick`, `b6.on_arrival`, `b6.run`, `d1.tick`, `graph.rebuild`. `tools/worker.py` is the worker entry point (also dispatches outbox events).
- `sh_platform/events.py`: `EventBus`. `MemoryBus` (simple: in-process dispatch, last 500 events kept). `PgBus` (production: `sh_outbox` row written in the caller's own transaction via `publish(..., conn=)`; `dispatch_once()` with `FOR UPDATE SKIP LOCKED`; `sh_outbox_done (consumer, event_id)` makes each consumer run once per event; a failing consumer is retried on the next pass).
- Routed through the queue: scheduler loop (`b6_schedule.start` -> `b6.tick`), delivery loop (`d1_delivery.start` -> `d1.tick`), on-arrival runs (`e0c_load` -> `b6.on_arrival`), pipeline runs from the Pipeline step and from the Verify fix (`b6_routes.run_plan`, `b9_verify` -> `run_pipeline`), graph rebuild (`graph/hooks._background` -> `graph.rebuild` in production; still a thread in simple mode). In simple mode every one of these runs inline exactly as before (the queue only records it); in production the scheduler and delivery loops enqueue one tick per company per minute (the key de-duplicates across replicas) and a worker runs it, and a pipeline run waits for the worker's answer so the screen still gets the record. A rule refusal (`Refused`) comes back as a result, not a failure, so the screen shows the same words and nothing is retried.
- Shared state in Redis in production: answer cache and its data-version counter (`chat_fastpath`), chat turn limit (`demo_limits.TurnLimiter`), outage breaker (`egress/gateway._breaker`; a plain dict in simple mode, so the existing tests are untouched).
- Events: job states (`job.queued|running|retrying|done|failed`) and `badge.action` (published from `p2_assign._append`, never raises). `GET /api/v1/events/stream?after=` is server-sent events for the signed-in company (ends after about 25 s, the screen reconnects).
- Jobs and events admin page: `sh_platform/v1/w3_jobs_routes.py` + `w3_jobs.permissions.yaml` (auto-mounted by `v1.install`, data engineer seat; the stream is open to any signed-in seat but filtered to the company), `ui/src/v1/s1/jobs/` (`JobsPage.tsx`, `api.ts`, `routes.tsx`, `jobs.test.tsx`). Shows the mode, failed jobs with "Send again", recent jobs, latest events; refreshes when the stream says something moved.
- `docker-compose.yml` (postgres:16 on 5433, redis:7 on 6380, data under `D:/Docker/signal-harbor/`), `tools/migrate_to_postgres.py`, `tools/parity_check.py`, `requirements.txt` (+ `psycopg[binary]`, `redis`).

## How to run locally in production mode
1. `set SH_PG_PASSWORD=<pick one>` and `set SH_REDIS_PASSWORD=<pick another>` then `docker compose up -d` (needs Docker running). Redis now requires its password (PM1). Postgres keeps the password it was first started with; the local one from 11 Oct is in `.sh-tmp/pm1-local-db.env`.
2. `pip install -r requirements.txt`.
3. In every shell that runs the web server or the worker:
   `set DATABASE_URL=postgresql://sh:<your password>@127.0.0.1:5433/signal_harbor` and `set REDIS_URL=redis://:<your Redis password>@127.0.0.1:6380/0`.
4. Copy the existing data in (safe to repeat, the source is not touched): `python tools/migrate_to_postgres.py <data_root>` (add `--dry-run` first to see the counts).
5. Start the web server as usual (`python tools/serve_v1.py` or your port) and, in a second shell, `python tools/worker.py`. Open Settings, Jobs and events (after the mount lines below) to see jobs and events move.
6. Back to simple mode: remove the two variables and stop the worker. Nothing else changes.
7. Production tests: `set TEST_DATABASE_URL=...` (a separate database such as `signal_harbor_test`: the tests drop `sh_outbox`) and `set TEST_REDIS_URL=redis://:<pw>@127.0.0.1:6380/15` (that Redis database is flushed; use a throw-away one) then `python -m pytest tests/v1/test_w3_two_modes.py`.
8. Parity: start a simple-mode and a production-mode server on the same seed, then `python tools/parity_check.py --simple http://127.0.0.1:<p1> --production http://127.0.0.1:<p2> --creds <file> --out <dir>`.

## Difference for Nitin's approval
1. The jobs and events page has no artboard in `docs/plan/v5-designs/` (nothing there covers it). I built it from the existing design kit (`PageFrame`, `Pill`, `ds-table`) in the same shape as the Connectors page; it needs a design pass if you want it to match a canvas.
2. The queue is a small Redis queue written here, not arq or rq (neither is installed, and the card allowed either). Same behaviour asked for: retries with backoff, failed list, worker entry point. Swap to arq later if you want its extras.
3. The state adapter is built and tested but existing stores still read and write files in both modes (see Open items, first point).

## Mount lines (for the integration step)
1. `ui/src/v1/s1/routes.tsx`: `import { routes as jobsRoutes } from "./jobs/routes";` and add `...jobsRoutes` to its `routes` array (path `settings/jobs`; `s1/jobs/routes.tsx` is not picked up by the `./*/routes.tsx` glob because it is two levels down). Add a "Jobs and events" link in `SettingsPage.tsx`.
2. Server: nothing to mount (`w3_jobs_routes.py` and its permissions file are picked up by `sh_platform/v1/__init__.py`). Production start-up: run the worker (`tools/worker.py`) beside the web service on Railway; give both the same `DATABASE_URL`, `REDIS_URL` and data volume.

## Tests
- `python -m pytest tests/v1/test_w3_two_modes.py`: 24 passed, 3 skipped (the 3 need `TEST_DATABASE_URL` and `TEST_REDIS_URL`: Postgres store versions and CAS, outbox with once-only consumers, Redis queue with a real worker). The Redis logic is also tested against a small fake Redis in the same file (queue retries and failed list, call/wait, window, breaker, answer cache, data-version counter). Simple mode: mode rules, file store CAS and path escape, queue retry/backoff/unique key, event bus, assign moves the badge, scheduler and pipeline run through the queue with the same refusal words, admin routes (company filter, retry), event stream filter, permissions file coverage, migration idempotence, parity compare.
- `npx vitest run src/v1/s1/jobs`: 2 passed.
- Regression run in simple mode (tests/v1, egress, graph, auth, jsonfile): see the Regression line at the end of this note.

## Open items
- **Stores not moved yet.** About 350 call sites read and write JSON through `read_json_strict` / `write_json_atomic` and list folders with `iterdir`; they still use files in both modes. `StateStore` and the migration are ready, and Postgres holds a copy after `migrate_to_postgres.py`, but switching a store means going through `store_for(...)` and replacing its folder listings with `keys()`. Until then, production mode moves the jobs, events, cache, limits and breaker to Redis/Postgres, and the web service and worker must share the data volume (the diagram shows the volume on the worker; the web service also needs it today).
- Non-JSON data (DuckDB warehouse, uploads, `.jsonl` logs) stays on the volume by design.
- Fixed in PM1: a running job holds a 60 s lease its worker renews; a dead worker's job is counted as a failed attempt by the next worker (see PRODUCTION-TEST.md). The per-project "already running" guard in `b6_run` is per process; across workers the queue key (`b6.run:<company>:<project>`) stops a second waiting run, not a second one already started.
- Postgres connections are opened per call (no pool); the rate-limit count-then-add is not atomic across replicas. Both marked `ponytail:` where they live.
- Nothing was run against a real Postgres or Redis here (no servers on this machine); the production tests are ready to run once the compose file is up.

## Regression (simple mode, 11 Oct)
`pytest tests/v1 tests/egress tests/graph tests/auth tests/test_jsonfile.py`: 2102 passed, 22 skipped, 16 failed in 19 min. The 16 failures are in other cards' areas (skill text for Span/Lumen in test_e0b1 and test_v3_g1, North turn tests, Tally revision tests, `e6_trace` missing `turn_trace_id`/`new_trace_id`, g1 gate wording, seed and span-loop tests). Re-run on its own, none of their tracebacks touches a file of this card (no mention of jobs, events, state, mode, demo_limits, the gateway breaker, p2_assign, b6_schedule or graph hooks). Backups of every edited file: `.sh-tmp/<name>.bak-w3`.

## Review (security reviewer, 11 Oct)

Checked: mode switch and start-up refusal, company scoping of the jobs page, retry and event stream, permissions yaml (default deny, matches the router), Redis keys and TTLs, outbox once-only consumers, Postgres compare-and-set, docker-compose (ports bound to 127.0.0.1, password from the shell), simple-mode diffs of b6_schedule, b6_routes, d1_delivery, demo_limits, the gateway breaker, graph hooks and chat_fastpath (behaviour unchanged; the answer cache key carries the company). Design: the jobs page has no artboard (difference 1 stands for Nitin's approval).

Fixed in review:
1. **The event stream held a server thread for up to 25 s per open tab** (sync generator in the thread pool; about 40 open screens would stall every sync route). Now an async generator that polls the bus through the thread pool briefly and stops when the browser goes away.
2. **A stream that only saw other companies' events ended at once**, so the screen reconnected every 2 s and re-read the same rows. It now skips them and keeps waiting for its own company's events.
3. **An event id from before a restart** (`after` larger than the newest id) made the stream wait silently for ever; it now starts from the newest id.
4. **Double retry**: two clicks on Retry could queue a failed job twice (both queues). The Redis queue now claims the retry with `LREM` on the failed list; the local queue checks and flips the state under its lock.
5. **A poison outbox event was retried on every pass for ever** and enough of them would fill the 50-row batch. Dispatch now stops after 20 attempts per event (the row stays, attempts = 20, for a person to look at).
Tests added: double retry refused, restart id. `tests/v1/test_w3_two_modes.py` 24 passed, 3 skipped; jobs UI 2 passed.

Left as noted (not blocking, simple mode unaffected):
- Production breaker: the Redis key expires with the window, so after the window every caller tries the provider until one fails again (simple mode lets one trial through and re-arms). Same accepted herd as the existing ponytail note; store the "until" time with a longer TTL if it matters.
- A worker killed mid-job leaves the job "running" and its key marker blocks a repeat for up to an hour (builder's ponytail note: lease and sweeper).
- The Redis rate window is count-then-add (builder's ponytail note); a burst across replicas can pass the limit by a few turns.
- Redis in docker-compose has no password; it is bound to 127.0.0.1 only. Add `requirepass` before it runs anywhere else.
- None of the production side has run against a real Postgres or Redis. Run the three skipped tests with TEST_DATABASE_URL and TEST_REDIS_URL, and `tools/parity_check.py`, before calling production mode done.
