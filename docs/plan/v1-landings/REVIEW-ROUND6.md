# Review, Round 6 (P1 to P5): 8 October

Read: V1-BUILD.md Round 6, P1.md to P5.md, every file they name, every hook line in another card's file.
Ran (read-only): `SH_MODEL_PROVIDER=off python -m pytest tests/v1 -q` → 73 passed in 131 s. `cd ui && npx tsc --noEmit -p .` → clean.
No code was edited. Findings are ranked; each has file:line, the failing scenario, the smallest fix.

## Blockers

### B1. The signer can resolve an unanswered comment and sign around it
- `sh_platform/v1/p1_project.py:270-278` (`resolve`), used by `p4_benchmarks.py:210` (`done` counts `resolved`).
- Scenario: Flow raises a benchmark miss on the build pack to Arjun and Priya. Leela (builder, a build-pack signer) presses Resolve on both while they are still open; `sign_block` in P1 counts only `state == "open"` and P4 counts resolved as done, so `POST /build/{iid}/pack/sign` succeeds with the figure never confirmed. The same move lets the raiser resolve a comment addressed to himself and sign the intent of work.
- Fix (one guard in the shared function): in `resolve`, `if c["state"] == "open" and who != c.get("by"): raise Refused(409, "Answer it before it is resolved.")`. Then P4's `done` stays correct without change. Add the assertion to `tests/v1/test_p4.py` (builder's resolve → 409).

### B2. A project can be handed over and made live without a signed build pack
- `sh_platform/v1/p5_handover.py:92-103` (`offer`), `:119-135` (`accept`); UI `ui/src/v1/p5/HandoverCard.tsx:59` shows the button whenever the stage is not live.
- Scenario: any analyst opens an engineer page of a project still at `talking` or `designed`, presses Hand over to ops (P5 also writes them in as `people.builder`), then the same person (same roles) accepts on the ops page: the project is `live`, the build pack never signed, the benchmark gate of P4 skipped. `_set` writes `stage="live"` straight to the file, so P1's `_sync` keeps it.
- Fix: in `offer`, `if rec.get("stage") != "built": raise Refusal("Sign the build pack first; then hand the project over.")` and in `HandoverCard.tsx:59` show the button only when `p.stage === "built"`. Two names (offer ≠ accept) is not in the contract; leave as an open question.

## Should fix

### S1. The design and the build pack are readable by participants through the artefact view
- `sh_platform/v1/p1_routes.py:64-74` with `p1.permissions.yaml` (all six roles) versus `a1.permissions.yaml:4` and `b3.permissions.yaml:4,7` (company_admin, analyst, sponsor only).
- Scenario: Dev Sharma (participant) opens `/api/v1/projects/{pid}/artefacts/design` or `build_pack` (or `export?format=xlsx`) and reads Span's data model, the open questions and answers, the full mapping sheet with its rules and SQL, which b3 and a1 refuse him. No library item leaks (the SOW section is what I4 already shows to every role; P3 lists only `visibility === "company"` items; Pulse carries no document text).
- Fix: in `p1_project.document` (and so `export`), `if kind in ("design", "build_pack") and not roles & {"company_admin", "analyst", "sponsor"}: raise Refused(403, ...)`; pass `v.roles` from the route (one argument).

### S2. Agents' hand-over comments become "Accept the hand-over" cards for people who cannot accept
- `sh_platform/v1/p1_project.py:208-212` (`_person`: a part nobody holds falls back to the raiser), `p2_pulse.py:27-28,110` (every `handover` kind is a card with action "Accept the hand-over" opening the project page), `i6_chat.py:588`, `a1_chat.py:437`, `f1_chat.py:334,381`, `p5_handover.py:100`.
- Scenario: Flow's "no open points left" hand-over is addressed to `ops`; nobody holds ops yet, so it goes to the raiser. Priya (sponsor) sees "1 hand-over on the build pack waits for you to accept", the link opens the project page where there is nothing to accept, the accept route refuses her role, and only a build-pack signer can resolve it: the card never leaves her Pulse. P5's own offer has the same routing (its test fakes P1, so `to == "ops"` is asserted literally and the fallback is never exercised).
- Fix: in `p2_pulse._comment_cards`, a `handover` by an agent key (`by in p1_project.AGENTS`) is skipped (it tells; the seat wait already shows the act), and the P5 card's href is `/centre/build/ops`. In `p5_handover.offer`, address the comment to `people.ops` when held, else to the ops manager seat by name is impossible today: say so in the text and leave `to` unset.

### S3. The P5 hook in b5 is only guarded against ImportError
- `sh_platform/v1/b5_ops.py:102`: `try: ... after_ops(plane, today, rows) except ImportError: pass`.
- Scenario: `after_ops` writes `build/ops/daily.json` and `tickets.json` on every `GET /api/v1/ops`; a locked or read-only file (OSError) or any P5 defect turns the whole ops page into a 500. Every other hook in this round uses `suppress(Exception)` or `except Exception`.
- Fix: `except Exception: log.warning("P5 after_ops failed", exc_info=True)`.

### S4. Pulse does not show P5's daily state per live project
- `sh_platform/v1/p2_pulse.py:242-246` builds the project line from `loaded.json` and runs; `p5_handover.daily(plane, pid)` is never read (P2 and P5 both list it as open).
- Scenario: a live project's source failed today; the ops page knows, Pulse's "your projects today" still says "loaded 2026-09".
- Fix: one guarded field on the line: `"daily": _guard("p5 daily", lambda: p5_handover.daily(plane, pid), None)`, and show it in `PulsePage.tsx` beside `last_load`.

### S5. A proposed benchmark is checked against calendar last month, not the loaded period
- `sh_platform/v1/p4_benchmarks.py:102-117` (`for_design`: `period = last full month`), `:185-198` (`verify` uses it).
- Scenario: the demo data runs to August; in October every KPI without a benchmark gets "The load reads no figure for 2026-09. Is that what you expect?", a comment to the raiser and the sponsor that cannot be confirmed truthfully, and the build pack stays blocked until someone answers nonsense.
- Fix: in `verify`, for `b["proposed"]` take `period` from the newest period `_full_trend` holds (fall back to `b["period"]` when there is none).

### S6. No screen can sign the build pack
- P4 lands `POST /api/v1/build/{iid}/pack/sign` and says so (P4.md "Shared edits needed"); `grep -rn "pack/sign" ui/src` finds nothing; `ArtefactView.tsx` has Download only.
- Scenario: in the demo the project cannot reach `built` except by curl, so B2's hand-over gate (once fixed) blocks every hand-over.
- Fix: one button on the build-pack tab of `ArtefactView.tsx` for `signers.includes(me)`: call the route, show the 409 sentence in a `role="alert"`.

### S7. Duplicate route paths: the old screens win today
- `ui/src/v1/i6/routes.tsx:5` (`intent`), `ui/src/v1/c1/routes.tsx:4` (`consume`), `ui/src/App.tsx:140` (`build` → Navigate home) against `ui/src/v1/p3/routes.tsx:21-25`. `v1Routes` is built by `import.meta.glob` (alphabetical: c1, i6 before p3) and React Router keeps the first of equal matches, so `/centre/intent` is still the bare conversation and `/centre/consume` the bare ConsumePage; React warns on duplicate keys.
- Fix (orchestrator): delete the two old entries and App.tsx:140. `home` is already resolved (X2 moved to `home/old`).

### S8. `tools/reset_v1.py` does not know Round 6's files
- `tools/reset_v1.py` removes intents, build, loaded.json and more, never `projects/`, `build/verify/`, `build/ops/{handovers,tickets,daily}.json`.
- Scenario: the orchestrator removes its test intents; orphan `prj-*` records keep showing in `GET /api/v1/projects`, on the P5 board (`p5_handover.board` lists every project) and as dead hand-overs. Pulse is safe (it walks `intents/`).
- Fix: add those paths to `reset`.

### S9. Room files are still written by everyone
- `i4_sow.py:179`, `i2_north.py:452` (via `i6_chat.py:589`), `a1_chat.py:441`, `b2_routes.py:70,88,106`, `b3_mapping.py:282`, `b4_routes.py` `_post`, `b5_ops.py:50-60,100,129`, `c2_offers.py:145`, `f1_chat.py:337`, `x5_extract.py:717`. P1 left them because `test_a1`, `test_b3`, `test_c2`, `test_i4`, `test_i6a` assert room posts.
- Scenario: the spec says "No rooms"; every agent act is now written twice (comment and room), and the stale room keeps a second, unreviewed record of the same facts.
- Fix (one change): make `room.post` a no-op that returns `{}` and drop those asserts in the same commit. UI leftovers: `ui/src/v1/home/HomePage.tsx:44` Room link (reachable at `/centre/home/old`), wording at `ui/src/v1/b4/RunsPage.tsx:80`, `ui/src/v1/b5/OpsPage.tsx:118,126`.

## Notes

- N1. Name-only identity. `p1_project.answer:257` and `resolve:275` compare display names; Pulse (`p2_pulse._is_me`) refuses a shared name, the API does not. Two accounts named alike can answer each other's comments. Fix later: store `to_account` when a person is picked; refuse answer/resolve when `viewer.shared_name`.
- N2. Signature after reopen. `p1_project._sync:128-130` reads `sow.signature`; C2 clears it on reopen and keeps `sow.signatures`. The project record then shows the intent as draft with no signer (history is still in the SOW, nothing is lost on disk). Fall back to `signatures[-1]` for `signed_by` if the page should keep saying who signed last.
- N3. Reads that write. `GET /api/v1/intents/{iid}/project` (`p1_routes.py:49-56`) and `GET /api/v1/build/waiting` (`p3_routes.py:28-31`) create project records for older intents; `GET /api/v1/ops` writes `daily.json`. Idempotent (locked re-check in `create_project:94-97`), but a participant's GET now creates records with `started_by` from the thread.
- N4. Benchmark figures and the reply guard: safe. The stored value comes from the person's words (`i6_chat.py:612`, `p4_benchmarks.parse`), `FIELDS["kpis"]` (`i6_chat.py:77`) does not carry `benchmark`, so the model's "given"/"none" never reaches the SOW, and `closing_summary` is built after `ask` returns (`i6_chat.py:625`), outside the guard. `_sow_view` turns the benchmark into words that `_facts` picks up, so North may restate them.
- N5. `parse` is digit-greedy (`p4_benchmarks.py:54-57`): "4.2 % last month, across our 12 funds" stores reported 4.2, expected 12. Acceptable while the person sees the stored line in the closing summary; worth a "did I read that right" turn later.
- N6. Periods and tolerance are right: `_got` compares `str(period)[:7]` (dates or months both match), `met` is `abs(got - expected) <= tolerance + 1e-9`, absolute in the unit said; a dedup on (line_ref, to, text) raises each miss once and again when the figure changes (`_post:175-180`). The check-then-write is outside the comments lock, so two loads racing could double-post; loads are long, low risk.
- N7. Any analyst or company_admin signs the build pack (`p4_routes.py:28-38`, yaml); the signer is not checked against the project's builder or head of data. Same as the yaml says; name it in the guide.
- N8. The Watcher asks once per source per day under the tickets lock (`p5_handover.py:163-170`) and `after_ops` only runs for `stage == live`; a project with no builder logs a warning on every ops read. The ledger entry's `state` stays `open` after the comment resolves (P5.md says so); `board` already reads the comment state.
- N9. `f1_chat.py:374` turns every settled check into a `note` comment to the raiser on the build pack. Notes make no card and never block, but the gutter fills with one line per engineer answer.
- N10. `x5_extract.py:714` asks the raiser "Shall I use the revised spec?" as a blocking comment; answering it changes nothing (the decision is `decide_revision`). Either make it kind `note` or act on a yes.
- N11. Pulse caches 60 s per viewer (`p2_pulse.py:274-281`); an answered comment's card stays up to a minute. The anomaly threshold is 20 % for every KPI (`JUMP`), declared.
- N12. `ProjectTag` exists (`ui/src/v1/p1/ProjectTag.tsx`) but is wired into none of the four conversation headers yet (orchestrator task from P1.md).
- N13. Tests. All pass for the right reasons except: `tests/v1/test_p5.py:37-41` replaces P1 wholesale, so the real `to="ops"` → raiser routing (S2) and `resolve` by the offerer are never run against P1; `tests/v1/test_p4.py` never tries the builder's Resolve (B1). `test_p2` asserts counts on a hand-written comments file, which is fine. No test asserts a wrong value.

## Orchestrator checklist after the fixes
1. B1, B2, S3 (three one-line guards), S2 Pulse filter, S5 period, S1 role check.
2. Delete `i6/routes.tsx` `intent`, `c1/routes.tsx` `consume`, `App.tsx:140`; wire `ProjectTag` into the four headers; add the build-pack sign button (S6).
3. `room.post` no-op and drop the room asserts; remove the Room link and wording (S9); extend `reset_v1.py` (S8).
4. Rebuild, restart, re-issue passwords, remove test intents, walk once as Arjun, Leela, Priya, Dev.

## Verdict
Ship to the demo company: **yes after fixes**. B1 and B2 are each a one-line guard; without them the sign-off, which is the one thing that carries weight in this product, can be walked around by the builder alone.

## Summary
1. 73 backend tests pass (131 s) and tsc is clean; the hooks in i6, i4, a1, f1, x5 and b4 are guarded; the b5 hook is not (S3).
2. Two blockers, both sign-around paths: a signer can resolve an open, unanswered comment (B1), and any analyst can hand over and make live a project whose build pack was never signed (B2).
3. Visibility is right everywhere except the design and build-pack documents, which the artefact view opens to participants against a1's and b3's own rules (S1); no library item leaks through artefacts or Pulse.
4. Benchmarks are computed from loaded figures with the right period and tolerance; the reply guard cannot touch them; proposed benchmarks point at calendar last month instead of the loaded period (S5) and there is no sign button (S6).
5. Leftovers for the orchestrator: duplicate intent/consume/build routes (old ones win today), room posts still written everywhere, reset tool unaware of projects, hand-over cards addressed to people who cannot act (S2).

## Re-check after FIX6 (8 October)

Ran (read-only): `SH_MODEL_PROVIDER=off python -m pytest tests/v1 -q` → 70 passed, 3 skipped (all three in `test_x1.py`; round 6 had 73 passed, so nothing else was lost). `cd ui && npx tsc --noEmit -p .` → clean. B2 is not re-raised (Go live button, V1-BUILD.md Round 9, G2).

### Findings, one by one
- **B1 closed.** `sh_platform/v1/p1_project.py:275-276`: an open comment is 409 for anyone but its author; the signer check at `:277` still follows. Walked the sign-around routes: Leela's Resolve on Flow's miss is 409 (`tests/v1/test_p4.py:117-118`); agent comments have `by="flow"`, so no person is their author; P4's `done` (`p4_benchmarks.py:219`) now only ever sees `answered` by the addressee or `resolved` after an answer; P1's `sign_block` (`:291-292`) counts open comments addressed to the signer, which the author (who may be the signer) can still resolve, but a comment to yourself from yourself blocks nothing worth protecting. P5's accept still resolves its own hand-over comment because `h["by"]` is the author (`p5_handover.py:127`). No new hole.
- **S1 closed, with one side effect (S10 below).** `p1_project.py:362-363` refuses design and build pack to any role outside company_admin, analyst, sponsor; both routes pass `v.roles` (`p1_routes.py:66,72`); `export` goes through `document` (`:373`). `roles=None` skips the check but the two routes are the only callers. Other routes: a1 and b3 keep their yaml; the M1 map (`m1_map.py:322-328`) puts the mapping's table names and layers on the map for every role but no rule, SQL or question text; Pulse carries comment text only. No participant route to the design or the mapping remains.
- **S2 closed.** `p2_pulse.py:109` skips an agent's hand-over; `:118` sends a person's hand-over card to `/centre/build/ops`. `p5_handover.py:98` addresses the comment to `people.ops` or leaves `to` unset; `_is_me` (`p2_pulse.py:47`) returns False for None, `answer` refuses everyone (nobody is `to`), the offerer resolves on accept. `test_p5.py:69` still fakes P1, so the real `to=None` path is only exercised by reading.
- **S3 closed.** `b5_ops.py:102-105`, `except Exception` with a warning.
- **S4 closed.** `p2_pulse.py:97-99,251` guarded `daily`; `ui/src/v1/pulse/PulsePage.tsx:49` shows "Today: state".
- **S5 closed.** `p4_benchmarks.py:198-199` takes a proposed benchmark's period from `_newest` (`:137-141`, the newest loaded period), falling back to calendar last month when nothing is loaded. The row's `period` is what `_post` dedups on, so one comment per proposed KPI and loaded period.
- **S6 closed.** `ui/src/v1/f1/EngineerPage.tsx:89-91`: the button shows for company_admin or analyst (`:117`, the same roles as the route's yaml, N7 stands), the 409 sentence lands in `role="alert"`.
- **S7 closed.** `i6/routes.tsx` keeps only `intent/:iid`; `c1/routes.tsx` is empty; `App.tsx:140` is now `build/gap-analysis`; P3 owns `intent`, `build`, `consume` (`p3/routes.tsx:20-22`).
- **S8 closed.** `tools/reset_v1.py:36-40` removes projects/, build/verify/ and the three P5 ledgers.
- **S9 closed; the room is now dead code, not removed code (N14).** `room.py:42` returns `{}` before anything is written. Dependents walked: `x1_nira.after_post` was only ever called from `room.post:77`, which is now unreachable, so `room_state.json` is never written again; its readers are `x1_routes.py:28` (the room view) and `x2_home.py:50` (Nira's waiting line on `/centre/home/old`), both off the demo path; `m1_map.py:119` reads `room.json` as a provenance source and simply finds none. Nothing on home, Pulse or the four conversations depends on a room file. The five room asserts now assert "nothing written"; HomePage's Room link is gone; RunsPage and OpsPage wording fixed.
- **test_x1 skip is honest, not a cover.** Its three tests (`test_x1.py:45,70,78`) exercise posting to the room, the participant refusal and Nira's fixed stage order; the first two are the retired feature, the third is pure logic nothing calls any more. No live code path lost a test.

### New findings
- **S10 (should fix). The intent raiser can be sent a build-pack comment he cannot open.** P4 addresses every miss to the raiser and the sponsor (`p4_benchmarks.py:175-180`, `test_p4.py:111-112`); the raiser is whoever started the intent (`p1_project.py:103`), usually an `owner`, and S1 now refuses `owner` on the build pack. His Pulse card opens `/centre/project/{pid}?artefact=build_pack&comment=…`, `ArtefactView.tsx:47` shows "refused", and the answer box is inside the view. Signing is not blocked (one answer from the sponsor is enough, `p4_benchmarks.py:211-212`), but the card never leaves his Pulse. Smallest fix: on 403, `ArtefactView` still calls `GET /projects/{pid}/comments` (every seat may, `p1_routes.py:77-79`) and renders the comments addressed to `me` with the answer box; the document stays refused.
- **N14 (note). Remove the room rather than stub it.** `x1_routes.py:35-54` still accepts `POST /api/v1/intents/{iid}/room` from a company_admin, sponsor or analyst and returns 200 with an empty room, a silent black hole; `ui/src/v1/room/routes.tsx:4` still routes `/centre/intent/:iid/room` to a RoomPage nobody links to; `room.py:43-60` is unreachable code after a `return`. One commit: delete `room.py`, `x1_nira.py`, `x1_routes.py`, `ui/src/v1/room/`, `test_x1.py`, the `room.post` lines named in S9 and `b5_ops._to_room`, and `x2_home.py:50`.
- **N15 (note).** `test_p5.py:41` still replaces P1, so the `to=None` hand-over comment and the offerer's resolve on accept are not run against the real P1 (N13 stands, narrower now).

### Verdict
Every round 6 finding except B2 (deferred by decision) is closed, and none of the fixes opens a sign-around or a read-around. One new should-fix (S10, a dead-end Pulse card for an owner raiser, no security or signature weight) and two notes. Ship to the demo company: **yes**; take S10 with the Go live card or as a one-screen fix in the same pass.
