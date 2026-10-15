# PM1: production mode tested on this machine (11 Oct)

Postgres 16 and Redis 7 from `docker-compose.yml`, two web processes (8790, 8792) and `tools/worker.py` on one data root, against a simple-mode copy on 8791. Model calls off (`SH_MODEL_PROVIDER=off`): every chat answer is the rules or fast-path reply. Test data: `tools/make_test_env.py prod1` (scenarios) and `prod2` (final parity), migrated with `tools/migrate_to_postgres.py` (40 documents copied, 137 files kept on disk; a second run copied 0 and left 40 unchanged).

## Result in one line
All five scenarios pass and parity is equal, **after four fixes made here**. The biggest one: before the fix, a pipeline run on the worker failed whenever a web process had read the warehouse, and a second web process could not open a dashboard at all.

## Parity (10 use-case checkers, simple 8791 against production 8790)
- Final run (fresh `prod2` / `prod2s`, all fixes in): **10 checkers, 0 differences**. All 45 facts pass in both modes.
- The first run showed 7 differences (uc2 x3, uc5 x4). Every one was a clock time (`ran_at`, `cutoff`) of a recon the checker itself runs, including inside quoted response text. The figures, counts, case ids and wording were equal. Fix: `tools/parity_check.py` now ignores `ran_at` and `cutoff`, and clock times inside strings. Dates such as `as_of_date` still count (test added).

## Scenarios

| | Scenario | Result | Evidence |
|---|---|---|---|
| a | Two people edit the same dashboard | **Pass (fixed here)** | Leo (8790) and Grace (8792) open `dash-0ad2b1c7` at rev 2. Leo saves, so rev 3. Grace saves her copy and gets **409** "Someone else changed this dashboard since you opened it. Reload to see their change, then make yours again." Leo's change stands. Before the fix the layout save had no check, so the last writer silently won. |
| b | Kill the web process during a pipeline run | **Pass** | Anita starts a sandbox run on 8790. The web process is killed (`taskkill /F`) while job `18b913531f4b` (`b6.run`) is running. Anita's request drops (connection reset). The worker finishes the job anyway: `done`, 1 try, status `ok`, 3 gold tables built. The run is in the runs list afterwards. |
| b2 | Kill the **worker** mid-job (review open item) | **Pass (fixed here)** | Worker killed while job `abdfa75623fa` was running, and a new worker started. 60 s later (one lease) the new worker counted it as a failed attempt: `failed`, "the worker stopped during the job". The key marker was released and a new run straight after returned 200 `ok`. Before the fix the job stayed "running" and blocked a repeat for an hour. |
| c | Streamed answer over server-sent events | **Pass** | `POST /api/v1/consume/chat` with `Accept: text/event-stream` on 8792 as Sofia: 200 `text/event-stream`, `start` at 0.06 s, 10 `delta` pieces, then `done` with the full JSON (rules-only reply, no model). |
| d | Live Action badge after an assignment | **Pass (small fix)** | Mei holds `/api/v1/events/stream` open on 8792. Grace assigns her "dashboards" on 8790 at 1.88 s, and Mei's stream receives `badge.action {to: "Mei Chen", change: "assign"}` at 2.92 s, through Postgres and across processes. Fix: the badge event's `change` was always empty (it read `kind`; the record says `event`). |
| e | Rate limit across two web processes | **Pass** | `SH_CHAT_TURNS_PER_HOUR=4`. Raj alternates 8790 and 8792: turns 1 to 4 are 200, turns 5 (8790) and 6 (8792) are **429** "That is a lot of questions in an hour…". One Redis window counts for both processes. |

## Defects found and fixed (each with a test; backups in `.sh-tmp/<name>.bak-pm1`)
1. **The warehouse could only be used by one process** (`sh_platform/v1/wh.py`). The web server kept the DuckDB file open for its whole life, but DuckDB lets only one process hold a file. So in production the worker's pipeline runs failed with `Busy` (the screen showed a bare 500), and a second web process got 500 on any page that reads the warehouse.
   - Fix (production mode only; simple mode is unchanged): the web process gives the file back when its last open use closes, and in production a busy file is retried for up to 30 s instead of 3 s. Processes now take turns.
   - Re-tested: a web read, then a worker run (200, 1.9 s), then a read on the other web process (200).
   - Ceiling, marked `ponytail:` in the code: this is turn-taking, not sharing. A long run makes readers wait. Several busy replicas need a server warehouse (Postgres or MotherDuck), **a decision for Nitin**.
   - Tests: `test_production_web_gives_the_warehouse_file_back_when_idle`.
2. **A failed pipeline job surfaced as a 500** (`sh_platform/jobs/handlers.py`). Now it is a plain 503: "The pipeline run could not finish. Try again in a minute; the data team can see why under Jobs and events". "Already waiting" is a 409. The warehouse path and the error stay in the job record only. Test: `test_a_pipeline_run_that_fails_on_the_worker_is_a_plain_refusal_not_a_500`.
3. **Dashboard edits had no conflict check** (`b7_studio.set_layout`, `cx_dash._save`).
   - Every save now counts a `rev`, and the view returns it.
   - A layout save that sends an older `rev` is refused with 409. A save without `rev` behaves as before.
   - The studio screen sends `rev` (`ui/src/v1/b7/api.ts`, `StudioPage.tsx`).
   - Ceiling: the check-and-save lock is per process (marked `ponytail:`). Two processes saving in the same few ms can both pass until dashboards move to `StateStore`.
   - Tests: `test_two_editors_on_one_copy_the_second_save_is_refused_not_lost` and the b7 UI test (the PUT carries `rev`).
   - **`ui/dist` was not rebuilt.** Another agent is mid-edit in `ui/src/v1/t1`. Rebuild before the screen sends `rev`; the server check works without it.
4. **The Action badge event had an empty `change`** (`p2_assign._append`). Fixed, and the test now uses the real record shape.

## The two review items
- **Breaker herd: fixed** (`sh_platform/state/kv.py`, `egress/gateway.py`).
  - The Redis breaker now stores the code and the "until" time (wall clock), kept for a day after the window.
  - When the window ends, `take_trial` (`SET NX` on a trial key for one window) lets exactly one caller across all processes make the trial call. The others are refused with the same code until it clears or re-arms.
  - Simple mode is unchanged.
  - Tests: fake Redis with two processes and their own clocks, and real Redis.
- **Killed worker leaves a job "running": fixed** (`sh_platform/jobs/__init__.py`).
  - A running job holds a lease in `sh:jobs:running` (60 s). A heartbeat thread renews it every 20 s and also refreshes the key marker for jobs over an hour.
  - Each worker sweeps lapsed leases before taking work. A lapsed job counts as one failed attempt: it is retried with backoff, or goes to the failed list with its key released.
  - Ceiling (marked): a worker killed in the few ms between taking a job and writing its lease loses that job. BLMOVE would close that gap.
  - Tests: fake and real Redis, plus a long job that keeps its lease.

## Compose
Redis now requires a password: `--requirepass ${SH_REDIS_PASSWORD}`, required like `SH_PG_PASSWORD`, with `REDISCLI_AUTH` for the health check. `REDIS_URL` becomes `redis://:<password>@127.0.0.1:6380/0`. The run steps in `W3-two-modes.md` are updated. The passwords these volumes were first started with are in `.sh-tmp/pm1-local-db.env` (gitignored); Postgres keeps its first password. `docker compose down` was run and the data stays in `D:/Docker/signal-harbor`.

## Tests
- Production tests with `TEST_DATABASE_URL` (a separate database, `signal_harbor_test`, because the tests drop `sh_outbox`) and `TEST_REDIS_URL` (Redis db 15): `tests/v1/test_w3_two_modes.py` **32 passed, 0 skipped**. This includes the 3 that had never run against real servers, plus one new real-Redis test.
- Simple mode: `tests/v1/test_w3_two_modes.py tests/egress`: **298 passed, 4 skipped**. The 4 are the real-server tests.
- Touched areas: test_b6_run, b6_run_lock, p2, p2_assign, wh_clock, wh_lock and b7_studio gave 70 passed; test_cx with b7 gave 70 passed; `vitest src/v1/b7` gave 15 passed; `tsc --noEmit` is clean.

## Seen, not fixed
- **Postgres restarted itself three times** (07:26 to 07:29 UTC): "server process exited with exit code 2", then crash recovery with a 20 s+ "syncing data directory".
  - The worker logged failed passes during recovery and carried on. Nothing was lost, and there was no recurrence in the next 25 minutes.
  - The likely cause is the Windows bind mount (`D:/Docker/...`) under Postgres. If it recurs, use a Docker named volume (on the WSL disk) or a path inside WSL.
- The per-project "already running" guard in `b6_run` is per process (W3 open item, unchanged). The queue key still stops a second waiting run.
- Most stores still write JSON files in both modes (W3 open item 1, unchanged). Production still needs one shared data volume for the web processes and the worker.
- The Consume chat's rules reply to Sofia said "0 dashboards" while the project's published dashboard had a draft open. This is outside this card; worth a look by the Consume owner.
