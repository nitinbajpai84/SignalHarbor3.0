# RUN1: a run ID on every run

**What.** Every run, test or production, gets an id like `run-20261012-131500-ab12`, so operations and data governance can see what each run did.
Lineage: source -> file batch (`source_batches.id`) -> source record -> bronze (`_load_id`) -> silver -> gold (`run_id` column).

**Where it lives.** `sh_platform/v1/run_log.py` (`start_run`, `step`, `finish`, `record`, `list_runs`, `get_run`). Append-only JSONL per company:
`data/<company>/ops/runs.jsonl` (a start line, then a finish line) and `ops/run_steps.jsonl`. Works in simple and production modes; no migration.
`who` is the account display name only.

**Wired.**
- Pipeline runs: `b6_run.run` (sandbox = TEST, live = PRODUCTION). It uses the same id as its own `runs.jsonl` record. One step per table with rows and status.
  Triggers: manual (route and job), `schedule` (b6_schedule.tick), `file_arrived` (b6_schedule.on_arrival). The job id comes from the queue (`jobs/__init__.py` passes `_job_id`; `b6.run` handler logs it).
- Gold tables built by a run carry `run_id` (`select '<id>' as run_id, * from (...)` in `b6_run.build_statements`, gold layer, CREATE TABLE AS only).
- Intake loads: `e0c_load.load` (step carries `batch_id`, `file_id`, control-total checks).
- Connector pulls: `c5_connect/ops.fetch` (covers file and API connectors; trigger `connector`).
- Recon runs: `e3_recon.run_detail` (checks = items checked, failed = breaks).
- API: `GET /api/v1/ops/runs?mode=&kind=` (latest 100), `GET /api/v1/ops/runs/{run_id}` (with steps). Data team seat, declared in `v1/r1_runs.permissions.yaml`.
- UI: "Runs" section on Operations (`ui/src/v1/k3/RunsSection.tsx`), TEST/PRODUCTION badge, click a run for its steps.

**Test.** `pytest tests/v1/test_r1_run_log.py` (log round trip; sandbox run is a TEST run with steps; live run is PRODUCTION and the gold table has `run_id`).
`npx vitest run src/v1/k3/k3.test.tsx`. Manually: run a pipeline from Build, open Operations, see the row.

**Pending.**
- `run_id` on silver/core model tables (not changed now).
- `load_id` (bronze `_load_id`) in the intake step: the e0c2 observation load does not write a bronze `_load_id`; add when the two loaders meet.
- Job id for runs started by `b6.tick` / `b6.on_arrival` jobs (the schedule path calls `run` without the job payload).
- b9_verify checks are not yet recorded as run checks; pipeline steps record built ok / failed only.
- "rerun" trigger has no caller yet; recon `who` and trigger are system/manual (the recon function has no viewer).
- Move JSONL to a warehouse table when the list outgrows a file scan; no retention (never deleted).
