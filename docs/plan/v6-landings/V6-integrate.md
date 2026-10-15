# V6-integrate: mount lines applied, full suites, one new project walked

## Built (mount lines from the four landing notes)
- `ui/src/v1/b8/routes.tsx` (the router globs each `routes.tsx`; `sh_platform/app.py` needed nothing, routes and `*.permissions.yaml` are discovered): the Architecture step tab `build/p/:projectId/architecture` renders `b10/ArchitectureStep`; the old room stays at `.../architecture/model`, linked from the step ("Model view: the three layers and every table"). `.../architecture/pack` still works.
- `sh_platform/v1/b6_routes.py`: after `plan/approve`, `b11_builder.on_approved(plane, pid)` (builder's optional hook): the run starts at the approval.
- Fixes found in the walk: see `WALK.md` "Fixed" 1-8 (North prompt over the gateway limit, plan source `arrives`/`fields`, pack in the head of data's Action, schedule day text, nothing-compared variance, benchmark check on page open, "Lumen" as maker, complete page pipelines card).
- Files touched outside the four cards: `sh_platform/v1/{b6_schedule,p2_assign,d1_delivery,b7_studio,b10_pack,b11_builder,i6_chat}.py`, `skills/north/traps.md`, `ui/src/v1/{b10/ArchitectureStep,b11/BuilderPanel,b11/api,p2/api,a5/ActionLanding}.tsx|ts`, tests (`look.test.tsx`, `test_role_matrix_intents`, `test_x3`, `test_v6_b10_pack`, `test_b11_builder`). Backups `.sh-tmp/*.bak-v6int`.

## How to see it
Serve the walk data: `python tools/make_test_env.py v6 --seed` then `python tools/serve_test.py --port 8697 --data-root .sh-tmp/testenv/v6/data` (Testing mode). Screenshots and the step table: `walk/` and `WALK.md`.

## Tests
- UI: `npx tsc --noEmit` clean; full `npx vitest run` 210 files, 1748 passed; `npx vite build` built.
- Backend, full suite (`nm1_pytest.py tests -q -n 6`): first run 15 failed, 4049 passed (all 15 fixed or load flakes: role matrix, `test_x3`, North prompt tests now green, perf and speed tests pass alone). Second full run after the walk fixes: 4063 passed, 72 skipped, 2 failed (`test_proposal_speed` and `test_a_long_job_keeps_its_lease_alive`, load timing, both pass alone) and 1 collection error (my `tests/v1/test_b10.py` clashed with the existing `tests/intents/test_b10.py`; renamed `test_v6_b10_pack.py`, passes).
- New tests: pack in Action, plan carries `arrives`/`fields`, working-day schedule, nothing-compared variance.

## Differences for Nitin's approval
Those listed in the four landing notes stand (two-click approval, connection corrections edit an approved pack, builder above the old Pipelines controls, no drag box on the PDF, Lumen starter checks tile as text). Added here:
1. Because this box has no SFTP or mailbox connector, the walk corrected every source to "upload" (a pack version of its own). In production a missing connector goes to the head of data's Action as designed.
2. An unexplained variance now includes report lines the run has no figure for (before, they were listed as "not compared" and the variance read "cleared").

## Open items
1. The North system prompt has under 700 characters of room before the gateway limit; a size test on the prompt for the largest template would catch the next addition.
2. The pack gives the builder no benchmark block (portfolio, code, month); see `WALK.md` Remaining 1-2 (column types and definitions, only one gold table).
3. Remaining design differences: `WALK.md`.
