# PF1: seed fills the Build rooms, demo day pinned to 9 Oct

## Rooms and what they read (all written through the product's own writers, in tools/seed_v3_demo.py)
| Room | Reads | Seed does |
|---|---|---|
| Design with Span | build/design/<iid>.json | b1_design.design (rule-based lines, no model call) |
| Scan | build/scan/<iid>.json | landing/<source>/*.csv written from the warehouse; b2_scan.run_scan, then agree (K01-K04, by Anita Rao) |
| Mapping sheet | build/mapping/<iid>.json | b3_mapping.draft from the SOW catalogue (3 landing tables, 14 rows, all mapped) |
| Pipeline room | build/<pid>/plan-v*.json, log.jsonl, runs.jsonl | b6_plan.new_version (Leo Park) then approve (Anita Rao), b6_run sandbox then live (per-table counts), schedule daily 06:00 |
| Run log | warehouse/runs.json | b4_load.load per mapped source (v1_administrator, v1_trading_export, v1_manager_email) |
| Approval requests | build/deviations/<iid>.json | g4_deviations.propose: read the K04 benchmark month in UTC, pending with Anita Rao |

The signed SOW now carries a `catalogue` (landing tables with fields); a demo made earlier gets it patched in, and an old plan written straight to disk gets its history log back-filled. Each step runs only when its room is empty, so re-seeding the live demo is safe.

## Demo day
`wh.now(plane=None)`: with the company setting `demo_today` (settings/demo_today.json) it returns that date at the real time of day; otherwise the real clock. `wh.connect(plane)` sets a thread-local day so the many `wh.now()` callers (checks, pulse, Tally) follow the company they last connected to; pass `plane` for an exact read. `wh.set_demo_today(plane, date|None)` writes it. Both seeds set 2026-10-09 for Evergreen (seed_10uc before the history, so recorded stamps and checks agree).

## Notes
- Mapping approval has no separate record in the product: rows are `mapped`; Anita agreed the scan scope.
- The manager source's run shows "late" (runner SLA guess for month-end files); the mapping-sheet room post logs a warning ("the room post ... failed") as before, not caused here.
- Not touched: tests/v1/test_e5a.py::test_acknowledge_dismiss_and_ownership fails with or without this change (hard-coded date).
- Backups: .sh-tmp/*.bak-pf.

## Tests
tests/v1/test_seed_10uc.py: 45 passed (3 new: rooms have content; checks on the pinned day give the 9 Oct story: 192 and 101 days, Cedarpoint not due, one Finance call case; no setting = real clock). Also passed: test_wh_lock, b1-b4, e3a-d, e4a/b/d, e5b, e0a, e1a, e2a, e5a except the one pre-existing failure above (203 passed, 1 failed).

## Review
- Re-run found 41 seed errors: b6_plan (edited 10 Oct 02:37, not PF1) now refuses depends_on a table the SQL never reads; the seed listed the two bronze tables on both gold tables. Fixed in tools/seed_v3_demo.py (gold depends_on = silver/core tables read only; backup .sh-tmp/seed_v3_demo.py.bak-pf2). Seed passes again: 44 of 45.
- Open, not PF1: test_c1_a10_7 (tiles trace to bronze) fails because b6_plan derives lineage from depends_on only, so a gold table can no longer name bronze unless its SQL reads it. Owner of b6_plan must either allow bronze in depends_on or relax the test.
