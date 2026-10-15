# FIXE2 - per-company cycle date

## What it does
Each company has a cycle (as-of) date, stored in its own data plane (`settings/demo_today.json`, the existing demo-day setting, so the seeded 9 Oct 2026 stays as it is). Unset means the real UTC day. The administrator or the head of data sets it on screen: **Settings > Cycle date**. The header shows "Cycle: 31 Jul 2026" beside the Testing/Real switch only when the company's day differs from the real day.

`wh.today(plane=None)` is the one function that returns the company's business day. `wh.now()` (timestamps) already ran on the same pinned clock and keeps doing so.

## The global is gone
`wh._DAY` was a process-wide list set by whichever company connected last. It is now a `ContextVar`, set by `wh.connect(plane)`, `wh.use(plane)` (called from `profile.api._plane`, so every request resolves its own company) and `wh.set_demo_today`. Two companies in one process, or on two threads, no longer share a day. A thread that never touches a company's plane gets the real clock (its context starts empty).

## API
`GET /api/v1/cycle-date` (every company role) and `PUT /api/v1/cycle-date` `{cycle_date: "YYYY-MM-DD" | null}` (route roles company_admin, analyst; handler allows company_admin or head_of_data only). New files `sh_platform/v1/cy_routes.py`, `cy.permissions.yaml`.

## New / changed code (mine)
- `sh_platform/v1/wh.py`: `_DAY` to ContextVar, new `use`, `today`; `connect`, `set_demo_today`, `now` adjusted.
- `sh_platform/profile/api.py` `_plane`: `wh.use(plane)`.
- `sh_platform/v1/p2_assign.py`: hand-over due-date check uses `wh.today(plane)` (`_check` takes `plane`). Fixes "due date has already passed" at cycle 31 Jul.
- `sh_platform/v1/e3b_routes.py`: recon run with no `as_of_date` defaults to the cycle date.
- `sh_platform/v1/b5_routes.py`, `sh_platform/build/home.py`, `sh_platform/build/ops.py`: the "today" they hand to the Operations / Build home views is `wh.today(plane)`.
- `sh_platform/v1/k6_liquidity.py` (`alert_if_due`), `k7_routes.py` (`monthly` default month), `b9_verify.py` (`_latest_month` fallback), `e3_rules.py` (`listing`, rule in force today), `c5_connect/api.py` (`collect` pull date), `g3_sheet.py` (3 sites), `p4_benchmarks.py` (2 sites): `date.today()` / `datetime.now().date()` replaced by `wh.today(...)`.
- UI: `ui/src/v1/router/CycleDate.tsx` (hook, header badge, settings control) + `CycleDate.test.tsx`; `ui/src/shell/CentreShell.tsx` (badge), `ui/src/shell/roles.ts` (new setting key `cycle` for admin and head of data), `ui/src/v1/s1/SettingsPage.tsx` (section), `ui/src/v1/a5/ReconPage.tsx` (the "Check as at" default is the cycle date).

## Edits inside other fixes' files (call sites only; please check merges)
- FIXB e3_recon: `sh_platform/v1/e3_recon.py` `_day(None)` now returns `wh.today()` (3 lines at the top of `_day`; a None as-of had crashed).
- FIXC b10_pack: `sh_platform/v1/b10_pack.py` `_benchmark_block`: `date.today().replace(day=1)` to `wh.today(plane).replace(day=1)` (one line, `wh` already imported).
- FIXD i6_chat: `sh_platform/v1/i6_chat.py` `benchmark_rows`: local `from datetime import date` replaced by `from sh_platform.v1 import wh`; `today or date.today()` to `today or wh.today(plane)`.
- FIXE1 permissions: none (the new routes are in their own `cy.permissions.yaml`). `roles.ts` carries my one new key and one list entry.
- Not touched: e0c_load, e0b_tools, e0c_landing, b6_span, b6_plan, north_tools, i4_sow, trade_intake, n1_tally. They already read `wh.now()`, which follows the company's cycle date.

## Already on the cycle date (no edit needed)
Intake `received_at`, case dates (`e4_cases` due/aging), Pulse, Consume (`k4_office._day`, `k5_managers`, `k10_note`/`e1_asof` default cutoff) all call `wh.now()`; with the ContextVar they now follow the right company.

## Deliberately not changed
- Scheduler firing and "next run" (`b6_schedule`, `c5_connect.is_due`, `d1_delivery.tick`, `b7_studio.refresh_status`, `run_log.pipelines`, `build/runner`): they compare the schedule with real server time against run records stamped with the real clock (`b6_run._now`). Moving only one side would make a daily run never fire or fire every minute. A schedule has to fire in real time.
- Legacy 2.0 `sh_platform/intents/*` and `modules/m2_baseline/*` `date.today()` uses (separate clocks, not the 1.0 cycle).
- Other UI date inputs that default to the browser day (Office month-end picker, intent start forms). Only the recon page was in the walk; offer the same hook elsewhere on request.

## Tests
- `tests/v1/test_fixe2_cycle.py` (5): default and pin; intake, recon, Consume and a run's month default to 31 Jul; due 2026-08-07 accepted at cycle 31 Jul (and 30 Jul refused); two companies do not leak (also across threads); route set / clear / 400 / 403.
- `tests/v1/test_wh_clock.py`: the thread test now states the new rule (a thread sees the company it connected to); it asserted the process-wide day before.
- `ui/src/v1/router/CycleDate.test.tsx` (4). `tsc --noEmit` clean.

Backups of every file touched before the first edit: `D:/Temp/bak-fixe2/`.
