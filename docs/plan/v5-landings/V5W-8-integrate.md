# V5W-8 Integration

## Mounted (all seven packages)
- Routers: every `*_routes.py` is auto-installed by `sh_platform/v1/__init__.install` (b9, d1, k10, k3, p2 included), and their `*.permissions.yaml` merge. No router lines were needed.
- `sh_platform/app.py`: `ChatStreamMiddleware` (V5W-7) added outermost; the delivery thread (`d1_delivery.start/stop`, V5W-4) starts and stops with the build scheduler. Backup `.sh-tmp/app.py.bak-v5`.
- UI: routes auto-globbed by `v1/index.tsx`; shell (Action landing, bar Action/Build/Consume/Map) was already in place from package 2.
- `PipelinesRoom` now renders `VerifyPanel` (V5W-3); `DashboardsRoom` has a Delivery button (V5W-4); Settings has a "Delivery channels" section linking `/centre/build/delivery-settings`; `look.test.tsx` stylesheet list updated; `reportlab` added to requirements.txt.
- Delivery stays part of step 4 (as in the D4 design), so no fifth step was added to `b9/steps.ts`.

## Conflicts and breaks found and fixed
1. **Pulse dropped**: V5W-1's `p2_routes.py` and `p2.permissions.yaml` overwrote the existing P2 Pulse files (`GET /api/v1/pulse` returned 404; test_p2 and test_g1 failed). The Pulse route is merged back into the same files.
2. **Action landing 500**: card ids are UUIDs, not JSON serialisable. `p2_routes._run` now uses `jsonable_encoder`.
3. **Route shadowing**: `GET /api/v1/consume/morning-note/delivery-lines` was caught by C1's `/api/v1/consume/{iid}/{code}` (422). Moved to `/api/v1/morning-note/delivery-lines` (d1 routes, d1 yaml, k10 api and test).
4. **Delivery approvers locked out**: Delivery pages took the Build gate, so sponsor and approver (who approve channels) were bounced to Action. The gate now also admits Intent-only roles; the server still decides.
5. **No Action card for channels waiting approval**: `p2_assign._waiting` now lists submitted delivery channels the viewer can approve ("Delivery channel from X on Y", links to the delivery page). UI type and label added.
6. **Test conflicts**: `test_na7` and `test_out_of_credit_everywhere` sent "hi"/"hello", which V5W-7 answers with a fixed reply; both pass `fast={"off": True}`. `test_b10::no_file_writes_events_jsonl_by_hand` flagged `p2_assign.py`; its log is now `assignments/log.jsonl`.
7. **Layout**: the Build stepper's link line and Action greeting were flush to the left edge; 40px gutters added (b9.css, ActionLanding).
Backups: `.sh-tmp/*.bak-v5`, `*.bak-v5b`, `*.bak-v5c`.

## Test counts
- `tsc --noEmit`: clean for this work; two errors in `src/v1/k12/PainPointDemo.tsx` (another package, not touched).
- Full vitest: 1696 tests; 3 to 5 failed in two runs, a different set each time (m1_intent private_room, voice, m2 signoff). They pass alone (100/100) with one worker, so they are timeouts while the backend suite ran. Changed dirs (a5 p2 d1 k10 b8 b9 b9verify s1 look shell): 157 passed.
- `vite build`: ok.
- Full backend suite (`-n 6`, 42 min): 3901 passed, 68 skipped, 42 failed, 3 errors. I re-ran the 45 on a clean checkout of HEAD: 33 fail there too (not from this work): evals YAML parse error (`tests/evals/shared_c2.yaml` line 101, 17 tests), north_w2 nu01/nu06/h106, rc2_2, e4b, e0b1, v3_g1 skills, p7_cycle1, span_loop, t1, tally x3, smoke egress, `test_g1_gate` (FastAPI 0.142 wraps included routers, so `app.routes` no longer lists `{iid}` paths), voice and x5 errors. The rest were mine and are fixed (items 1, 6 above). Still unclear: `north_w2::nu02` fails here and passed on HEAD, with the same scripted-model-exhausted signature as nu01; `test_b10::every_kind_written` now fails on proving/report/review kinds from work in progress, not these packages.
- After fixes: test_p2, test_g1, test_p2_assign, test_d1_delivery, test_b10 (other than the proving kinds), test_s_cycle2, test_s_wave2: pass.

## The walk (own server on 8697, test env v5, 1440x900; shots in `docs/plan/v5-landings/walk/`)
01 Action landing (Mei), 01b (Daniel), 02 Build landing, 03 new project, 04 intent with North (rules/free-tier reply, Real use not switched on), 05 and 15 overview, 06 and 07 assign dialog and result (Mei to Leo), 08 Leo's Action (Assigned to me, Mark done), 09 architecture, 10 pipelines (with verify panel), 11 dashboards, 12 studio, 13 and 21 to 23 delivery (Grace adds Consume, sends; Daniel approves; Grace Go live), 14 complete, 16 Consume, 17 Map, 18 whole-company map, 19 review queue, 20 delivery settings, 22a Daniel's Action with the channel waiting.
Worked: sign-in lands on Action for every role; bar order; new project and North; assign and Leo's card; delivery approve and go live; project complete; Consume tabs; Map and review queue. No console or API errors after fixes.

## Gaps against the designs
- Intent could not be signed in the walk (needs a full North conversation); steps 2 to 4 were walked on the seeded live project, so the "opens when the intent is signed" gating, review and the real-send outbox were seen only as states (nothing is sent: no channel host is configured).
- Delivery is not its own rail step (kept under Dashboards, as D4). Rail copy differs slightly after the first view ("You are here").
- Project title is the first 120 characters of the sentence typed ("to show the inv"); the design names a short title.
- The Build film is missing on this machine (poster shown); the "What the page will show" box (A4) is not shown (needs a figure from records).
- Whole-company map: the layered graph is wider than its panel and clips at the right edge (scroll inside the panel).
- The pipelines run log lists every run (page height about 28,000px on the seed); needs paging.
- Only a company admin has Build and approval rights together, so the walk needed Grace plus Daniel; a data-team approver without admin rights cannot approve a channel on a project they are not on.
- Not done: PowerPoint export, Slack approval, fund return and alpha (listed in the package notes).

## Review (Opus, 11 Oct)
Looked at all 26 walk shots against A1, B1, B5, C1, D4, D5 and F1. Shell, bar order, Action landing per role, assign to Leo, delivery approve and go live match the flow. Shots before 09:53 (04, 13) still show the flush-left stepper; later shots carry the gutter fix.

**Fixed in review** (backups `.sh-tmp/*.bak-v5r`):
1. Project title cut mid-word ("to show the inv"): `i6_chat.opening` now cuts on a word with an ellipsis, at most 120 characters. Existing projects keep their stored title.
2. Go live stayed on the delivery page after going live (shot 23): `can.go_live` now needs an approved channel that is not live yet (`d1_delivery.py`).
3. Complete page copy: "1 dashboard(s)", "All 1 delivery channels", "channel(s)" now read in the singular when there is one; "Consume Consume" shows the title only when it differs from the label (`d1_delivery.summary`, `d1/CompletePage.tsx`).
4. Action landing: "Shared with you" ran edge to edge (shot 22a); it now has the 40px gutter. "Since 2026-10-11", "Due …" and "shared … on 2026-10-10" now read "11 Oct 2026" (`a5/ActionLanding.tsx`, `a5/ActionCentre.tsx`).

**Tests after the fixes:** test_d1_delivery, test_p2_assign, test_p2, test_north_aq1, test_north_c1r: pass (test_p7_cycle1 `ask_drops_a_step_planted…` fails, already on the HEAD list). Vitest a5, d1, p2: 37 passed; one unhandled error comes from `a5trail/trail.test.tsx` into `n2/Comments.tsx:73` (neither touched by V5). tsc: only the two `k12/PainPointDemo.tsx` errors, so `tsc --noEmit` is not clean overall and the K12 owner must fix them.

**Remaining gaps (not fixed here):**
- D5 Complete page is thin against the design: no four-step summary row, no "Added to the company knowledge map" section, and "What was verified" lacks the figure and benchmark lines (they need records; today only signatures, dashboards and channels feed it).
- Intent signing was never walked live; steps 2 to 4 were walked only on the seed. The next walk should take one project from North through sign-off.
- The whole-company map clips at the right edge (F1). The pipelines run log needs paging. There is no Build film.
- The architecture page shows a second "All projects · Plan and Span" crumb under the stepper links. Delivery shows a stopped channel above the live one with the same name.
- North_w2 nu02 has the same symptom as its siblings that fail on HEAD. b10 `every_kind_written` fails on the proving, report and review kinds from other work in progress. Their owners need to look at both.
