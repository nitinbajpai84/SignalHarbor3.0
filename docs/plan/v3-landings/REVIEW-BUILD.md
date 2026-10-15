# Review · Build group (B1, B2, B3, B4, D1) · 9 Oct 2026

Reviewer: Fable. Scope: cards B1–B4 and D1 against `docs/plan/V3-CENTRES-CARDS.md`, the UI paths versus the real routes, and the head-of-data journey. Repo code untouched; servers untouched; live data untouched.

## Verdict

**Not ready for the fix round to be skipped.** The backend journey B2 → B4 works end to end at library level (propose → approve with model change → sandbox → live → schedule → runs → Airflow), the SQL gate is solid, the swap keeps the previous gold, and D1 registers gold and bronze on approval. But the screen cannot drive it: the four B4 routes the Pipeline step calls do not exist, the Build page crashes on a project that has no plan yet (so Span can never be asked to propose from the UI), Span's source codes never match the intake source codes (so `on_arrival` and intake bronze registration can never line up), and the X1 demo plan is invisible to Consume and refuses a schedule change. Four blockers, each a small fix.

## How it was checked

- `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_b6.py tests/v1/test_b6_run.py tests/v1/test_b6_diagram.py tests/v1/test_d1.py tests/v1/test_e0a.py -q` → **32 passed** (28 s).
- `cd ui && npx vitest run src/v1/b6 src/v1/b6diagram` → **2 files, 6 tests passed**.
- `.sh-tmp/review_build.py` (throwaway): temporary data root, `tools/seed_evergreen.seed`, `tools/seed_v3_demo.intent` (signed intent, project id, Leo Park builder, Anita Rao head of data), one approved E0b mapping (administrator export → `valuation_observations`), then the journey over HTTP with `TestClient` on `create_app` (login + CSRF header) as Anita (head of data), Leo (engineer) and Daniel (CIO); library calls where a route is missing. A second temporary root ran `tools/seed_v3_demo.seed` to check D1 and the demo plan.

## Journey step results

| # | Step | Result | Note |
|---|---|---|---|
| 1 | Head of data opens Build, sees the project sent from Intent | PASS | `GET /api/v1/build/projects` lists it: stage `build`, `intent_signed: true`, `plan_state: null` |
| 2 | Opens the project before any plan exists | **FAIL (UI)** | Server answers `{plan: null, state: null, can, ...}` with no `sources`/`tables`; `BuildPage.tsx:52` does `plan.sources.filter` → TypeError, blank page. No "Propose a plan" button exists for this state (the Approval step only shows it for `draft`/`rejected`) |
| 3 | Span proposes from the signed intent | PASS (API) | `POST .../plan/propose` as Leo → v1 `proposed`: 3 bronze, 1 silver (`valuation_observations` insert), 2 gold (`..._valuation_monthly`, `..._valuation_daily`); unplaced items named in `notes`, never guessed |
| 4 | Model changes, tables with SQL, diagram render from the real plan file | PASS | `GET .../plan` carries `model_diff`, `is_new`, every non-bronze table has SQL; `GET .../diagram` → 10 nodes, 8 edges, every plan table a node, state in the corner |
| 5 | Proposer cannot approve | PASS | 403 "You proposed this plan, so someone else needs to approve it." (`can.approve` false for Leo, true for Anita) |
| 6 | Head of data approves; model change approved in the same step | PASS | v2 proposed with `add_column instruments.risk_class` → one `POST .../plan/approve` → plan `approved`, E0a proposal 2 `approved`, logged |
| 7 | D1: gold and bronze registered on approval | PASS | `tables_for_project` → 2 gold, 3 bronze |
| 8 | Run in sandbox (button) | **FAIL (route)** | `POST .../run?mode=sandbox` → 405. Library `b6_run.run(..., "sandbox")` works: first run fails cleanly at silver (bronze not landed) and gold reads "not run"; after a bronze landing all steps `ok`, plan → `built`, live warehouse untouched, `warehouse/sandbox.duckdb` written |
| 9 | Go live (button) | **FAIL (route)** | `POST .../run?mode=live` → 405. Library: `ok`, 4 silver rows, 1 + 1 gold rows, plan → `live`. Project stage stays `signed` (see should-fix 3) |
| 10 | Schedule set | **FAIL (route)** | `PUT .../schedule` → 405. Library `b6_plan.set_schedule` → `{weekly, 07:00, mon}`, logged |
| 11 | Runs listed | **FAIL (route)** | `GET .../runs` → 404. Library `b6_run.runs` → 3 runs, newest first, rows per table |
| 12 | Airflow DAG downloadable | **FAIL (route)** | `GET .../airflow` → 404. Library `airflow_dag` → 6 `PythonOperator` tasks (one per table), `CRON = '0 7 * * 1'`, dependencies as `a >> b` |
| 13 | Failed live step keeps the previous gold | PASS | Bad gold SQL → run `failed`, row counts unchanged, no `__next` left behind |
| 14 | Consume finds the project's gold after go live | PASS | `GET /api/v1/consume/p/{pid}/tables` as the CIO → both gold tables with columns and rows |
| 15 | Chat change → new version → back to the head of data | PASS (API) | "add a monthly gold table by currency" → pending change; "yes" → v3 `proposed`. The UI never shows the pending change (should-fix 5) |
| 16 | X1 demo project in Consume | **FAIL** | `tools/seed_v3_demo.seed` registers nothing: `tables_for_project` → `gold: [] bronze: []`, so `/consume/p/{pid}/tables` is empty for the demo |
| 17 | X1 demo project: save the schedule / ask Span | **FAIL** | `set_schedule` → "position_snapshots has no SQL" (validate refuses the demo plan's silver tables with empty SQL); chat cannot add a table because the demo plan's silver tables list no columns |

## Blockers

1. **The Pipeline step has no backend.** `sh_platform/v1/b6_routes.py` (ends at line 178) and `b6.permissions.yaml` declare no `POST .../run`, `GET .../runs`, `PUT .../schedule`, `GET .../airflow`; `ui/src/v1/b6/api.ts:31-34` calls all four. Scenario: head of data clicks "Run in the sandbox" → 405 → "That did not go through." Nothing after approval can be done from the screen. Fix (b6_routes.py, ~25 lines): four routes under `BASE` through `_run`, each `_gate(plane, v, pid, "full")` then `b6_run.run(plane, pid, mode, by=v.name)` (catch `b6_run.Refused` too; map to the same JSON), `{"runs": b6_run.runs(plane, pid)}`, `B.set_schedule(plane, pid, body, v.name)` returning `_view`, and `PlainTextResponse(b6_schedule.airflow_dag(plane, pid), media_type="text/x-python", headers={"Content-Disposition": "attachment; filename=<slug>.py"})`; add the four lines to `b6.permissions.yaml` (`company_admin, analyst`; `GET runs`/`airflow` also `sponsor, owner, approver, participant`). Seat: `go_live` is ARCHITECT, `run_sandbox`/`schedule` DATA_ENGINEER, as `_can` already says.

2. **Build page crashes on a project with no plan; no way to ask Span to propose.** `ui/src/v1/b6/BuildPage.tsx:52` (`plan.sources.filter`) and `:56-57` read `sources`/`tables` of the `plan: null` answer from `b6_routes.py:81-82`. Scenario: the very first open of a project sent from Intent. Fix (BuildPage.tsx, 3 lines): after `if (!plan)` add `if (plan.state === null || !plan.tables) return <PageFrame ...><p>Span has not proposed a plan yet.</p><Button disabled={!plan.can?.propose} onClick={() => void act(() => api.propose(projectId))}>Ask Span to propose a plan</Button></PageFrame>` (keep the chat if you like); and in `api.ts:18` add `propose?: boolean` to `can`. Add the vitest for this state.

3. **Span's source codes never match the intake source codes.** `sh_platform/v1/b6_span.py:72` makes the code from the source *name* (`slug(s["name"], 24)` → `fund_administrator_expor`, `manager_statements_by_em`) and ignores the `code` the intent carries (`administrator`, `trading_export`, `manager_email`; X1 and I1 write it). Consequences: `b6_schedule.on_arrival` (`:90`, matches `s["code"] == source_code`) never fires for a real load; intake's bronze would be `bronze_administrator_<layout>` while the plan's is `bronze_fund_administrator_expor_valuations`, so the silver insert reads a table no load ever fills; names are truncated mid-word on screen. Fix (one line): `code = slug(s.get("code") or s["name"], 24)`; and `_bronze_and_silver` should name the layout after the mapping's `sheet` only when the mapping carries no `layout` word of its own (fine to leave).

4. **X1 demo plan is invisible to Consume and refuses a schedule change.** `tools/seed_v3_demo.py:241` writes `plan-v1.json` and runs but never registers in the catalogue (`e0a_catalogue.tables_for_project` → empty; `cx_dash._gold_names:60` relies on it). And `:182` writes four silver tables with `sql: ""`, which `b6_plan.validate:219-220` refuses, so `set_schedule` (and any chat change) on the demo project fails with "position_snapshots has no SQL". Fix (seed_v3_demo.py): drop the four empty silver rows from `tables` (keep them in `depends_on` and `lineage`; `validate` accepts core tables as dependencies), add `"project_slug": SLUG` to the plan, and after writing it call `b6_plan._register(plane, plan)` (gold) plus `e0a_catalogue.register_bronze(plane, "administrator", "positions", cols, [pid])` and the trading one (or give the two bronze rows `source`/`layout` keys so `_register` does both). Re-run `tests/v1/test_x1.py` and `test_cx.py`.

## Should-fixes

1. **Scheduler not started, `on_arrival` not wired, bronze never registered by loads.** No file outside `b6_schedule.py` imports it; `e0c_landing.py:254-255` (after the load status) calls neither `b6_schedule.on_arrival(plane, source_code)` nor `e0a_catalogue.register_bronze` (the D1 comment at `e0a_catalogue.py:588` says E0c does; it does not). Orchestrator items, as the landings say: `app.py` after `v1_cards.install(app)` start the thread with the PlaneStore accessor and stop it on shutdown; E0c after `status == "loaded"` call both. Until then the bronze layer of the Settings page only ever shows what approvals registered.

2. **The runner and scheduler pick the newest version regardless of its state.** `b6_run.latest_plan:52` and `b6_schedule.tick:73` / `on_arrival:88` take the highest `plan-v<n>`. Scenario (reproduced): a live v2, the engineer accepts a chat change → v3 `proposed` → `is_due` false and "Go live" refused until v3 is approved; a pending proposal silences a live schedule. Fix: in `latest_plan` prefer the newest version whose state is in `LIVE_OK` for live/scheduled runs (`run(..., mode="sandbox")` may keep the newest).

3. **Plan state moves bypass B2 and the project stage never moves.** `b6_run._set_state:76-81` rewrites the file instead of calling `b6_plan.set_state` (so no "plan is now live" line in `log.jsonl`, no NEXT check), and nothing sets `p1_project.set_stage(plane, pid, "built"|"live")`, so the Build landing shows "In build" for a live project. Also `b6_plan.approve:272-275` sets stage `designed`, which `p1_project._sync:153-155` recomputes from artefacts on the next read (stays `signed`); harmless but dead code. Fix in `b6_run.run` after a good run: `B.set_state(plane, pid, state, by or "runner")` and `P1.set_stage(plane, pid, "live" if mode == "live" else "built")`.

4. **Diagram route has no project access gate.** `b6_diagram_routes.py:14-17` checks the seat only (`viewer_of`), not `g1_access.require(plane, viewer, pid, "read")` as every other project read does. A participant with no access to an Internal project can read its table names and purposes. Fix: one `G1.require(...)` line (catch `Refused` → 403 JSON).

5. **Pending changes from the chat are invisible in the UI.** `b6_routes.py:147` returns `{turns, pending}`; `api.ts:23` types `Chat {turns}` and `BuildPage` ignores `pending`, so Accept / Not this exist only as the words "yes" / "not this" in the chat and the `/plan/changes/{cid}/accept|reject` routes are unused. Fix: type `pending`, render each with two buttons on the accept/reject routes (the L2 pattern).

6. **Model-change state label.** `BuildPage.tsx:56` labels step 2 "Proposed" whenever `model_changes` is set, even after approval; use `plan.model_diff?.state`. `api.ts:16` types `model_changes` as `string | null`; the server sends an integer (works, wrong type).

7. **B4's regex gate.** `b6_run.py:24` is a second line of defence only (B2's sqlglot gate runs before a plan is saved; verified: DROP, DELETE, UPDATE, two statements, `--` comments, unlisted tables, invented columns all refused). B4 alone lets `read_csv('/etc/passwd')` through and refuses harmless identifiers that contain `load`, `copy`, `call` as whole words. Fine while plans only come from B2 and X1; worth one `B.validate` call before a run once X1's plan passes it (blocker 4).

8. **Duplicate "refreshed" cards, later.** `b6_run.notify:237` writes "Data refreshed · <project>" to every dashboard audience after a live run; `cx_share.notify("refreshed")` (C3) has no caller yet. When the orchestrator wires C3, pick one (the landing says the same).

9. **Names on screen.** Gold tables are `gold_monthly_investment_report_in_u_...` because `e0a_catalogue.slug_of` cuts the title at 30 characters mid-word. Not wrong, but a `project_slug` chosen once per project (and editable) would read better than a title slug; X1 uses `investment_report`.

## What is right

- SQL gate (B2): one statement, CREATE TABLE AS / INSERT ... SELECT only, every read table in the catalogue or earlier in the plan and listed in `depends_on`, every column resolved by sqlglot `qualify`; gold columns and lineage derived by the program.
- Approval (B2): architect seat, never the proposer (by account id), model change approved through `e0a.approve` in the same step, every step logged; sending back needs a reason and turns the model change down.
- Runner (B4): dependency order, `<t>__next` built and swapped in one transaction, failure stops the run and leaves the previous table and no leftovers; sandbox is a fresh copy and never touches the live file; live needs approved/built/live; no overlap per project; Airflow text has one task per table with the plan's dependencies and cron.
- D1: `layer_of`, `tables_for_project`, `register_bronze`/`register_gold` idempotent and name-checked; silver is the current catalogue.
- B3: nodes/edges from the real plan, "new" for bronze/gold/uncatalogued silver, consumers box only with gold; UI layout has no library.
- Plan-state and run-status words agree across B1/B2/B4/C1 (`draft|proposed|approved|rejected|built|live`; run `ok|failed`; `cx_dash._last_refresh` accepts `ok`).

## Fixes after review (Build fixer, 9 Oct 2026)

Backups: `.sh-tmp/<name>.bak-v3fixB` for every file touched.

- **Blocker 1 (no Pipeline backend)**: `b6_routes.py` now has `POST .../run?mode=sandbox|live` (live needs the architect seat, sandbox the data engineer seat; answers the refreshed plan view plus `runs`), `GET .../runs`, `PUT .../schedule`, `GET .../airflow` (attachment, `text/x-python`). `b6_run.Refused` is mapped to the same JSON. Four lines added to `b6.permissions.yaml`.
- **Blocker 2 (blank page without a plan)**: `BuildPage.tsx` shows "Span has not proposed a plan yet." with "Ask Span to propose a plan" (enabled by `can.propose`), the chat and the composer. `api.ts` types `NoPlan`, `can.propose`.
- **Blocker 3 (source codes)**: `b6_span._sources` uses the intent's `code` (name only as fallback). E0c now registers the bronze table of each load (`e0a_catalogue.register_bronze`, same names Span uses) and calls `b6_schedule.on_arrival` after a successful load (`e0c_load._after_load`, never fails a finished load).
- **Blocker 4**: not touched (demo seed, Consume fixer). The driver's X1 steps already pass with their change.
- **Should-fix 1**: E0c hook done; the scheduler thread start in `app.py` stays with the orchestrator.
- **Should-fix 2**: `b6_run.latest_plan(plane, pid, live=True)` returns the newest approved/built/live version; used by live runs, `tick`, `on_arrival` and the Airflow file. A proposed v3 no longer silences a live v2.
- **Should-fix 3**: after a good run `b6_plan.set_state` moves the plan (approved to built to live, one log line each) and `P1.set_stage` moves the project to built or live (P1 `_sync` keeps built/live). The old `_set_state` file rewrite is gone.
- **Should-fix 4**: diagram route calls `g1_access.require(..., "read")`, 403/404 JSON.
- **Should-fix 5**: Build page lists pending chat changes with Accept and Not this on B2's accept/reject routes.
- **Should-fix 6**: step 2 label comes from `model_diff.state` (Proposed, Approved, Sent back); `model_changes` typed `number | string | null`.
- **Should-fix 7**: left as it is (B2 gate runs before a plan is saved; B4 regex stays a second line). Not added: a `B.validate` call before each run, because X1's plan shape must be checked with its owner first.
- **Should-fix 8**: B4's own "refreshed" cards are gone; after a live run it calls `cx_share.notify(..., "refreshed", token=run_id, tiles_changed=n)` per dashboard of the project (n = tiles whose SQL reads a rebuilt table). Failed-run card for the plan owner stays in B4.
- **Should-fix 9**: not done (project slug choice belongs to D1/B2 design).
- **Hand-overs**: (a) `b6/routes.tsx` wraps both Build routes in the same role gate P3 used (`centresFor(roles).has("build")`, else back to the person's start page); the shell note had no "Needs another card" section, so the P3 logic is used as it stands. (e) pending changes, (f) diagram gate, (c) and (d) as above.
- Driver `.sh-tmp/review_build.py`: every PASS, no FAIL, including the four Pipeline routes over HTTP and the X1 catalogue step.
- Tests: pytest (b6, b6_run, b6_diagram, d1, e0c2) 36 passed; vitest b6 + b6diagram 8 passed; `tsc --noEmit` clean. New tests: intent source code, live/schedule skip a proposed version, state log lines, C3 call, E0c bronze registration, no-plan page, Accept / Not this.
