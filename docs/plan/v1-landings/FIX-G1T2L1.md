# Fix round: G1, T2, L1 (8 Oct)

Checks: `SH_MODEL_PROVIDER=off python -m pytest tests/v1 -q` 114 passed; `npx tsc --noEmit -p .` clean; `npx vitest run src/v1 src/shell` 80 passed (jsdom suite now has `testTimeout: 15000`).

## B1 intent-keyed routes
One router-wide dependency, `G1.intent_gate` (`g1_access.py`), installed by `sh_platform/v1/__init__.py` `install()` on every v1 router. Any route that names an intent in its path or as `?iid=` runs `http_gate` first ("read" for GET and for `.../chat`, "full" for other writes). That covers thread, chat, files, blueprint, design, scan, mapping and mapping.xlsx, runs, load, benchmarks, deviations, consume figures and brief, extract, template, context and every other `/intents/{iid}` and `/build/{iid}` route, including ones not on the review's list. It fails soft if the session cannot be had, so each handler still gives its own answer.
- Exempt on purpose (they gate themselves): `/intents/{iid}/project` (returns the lock row), `/build/pickup/{iid}` (p3 refuses a project the person may not see at all, 404), and `/build/{iid}/engineer*` (f1 `_gate`: joins an engineer who holds a ticket, then gates).
- `p3_routes.waiting` drops projects whose level is "none"; Internal ones show title only.
- Run-book routes (keyed by project) now call `G1.require`; before go live only the team may touch the run book.
- Tests: `tests/v1/test_g1_gate.py` walks `app.routes`, calls every intent-keyed route (about forty handlers) as an off-team analyst on a Restricted project and expects 403; plus run-book, brief, pick-up and the waiting list.

## B2 Internal is the team's alone
- `g1_access.level`: the analyst-reads rule is gone; docstring and `G1.md` updated. Tests that encoded the old rule changed (`test_g1`, `test_g3g4`, `test_i6a`); other tests now put Leela on the team the way pick-up does (`tests/v1/team.py`).
- Joining the team (`G1.join`, idempotent, never fails the caller): pick-up (already via `people.builder`); a design submitted for approval adds the head of data (`a1_chat.chat`, first company admin by name); the first run-book edit adds ops when they are not already full; an engineer opening the engineer screen on a project they hold an active ticket on is added as "data engineer" (`T2.assigned_on`, f1 `_gate`).
- Not done: the map still hides only Restricted nodes (card wording); Internal nodes stay visible.

## T2
S1 `row()` shows "A restricted project" for a project the viewer has no level on (Internal preview keeps its title, as the lock row does); also the Pulse ticket card. S2 `_covered` requires the comment to be addressed to the viewer. S3 ticket numbers claimed with `O_CREAT|O_EXCL` and retry. S4 no `open_tickets` on lock lines. S7 the vacuous assert in `test_t2.py` replaced by two real ones (covered while hers; Dev gets the card after delegation). Tests in `test_g1_gate.py` and `test_t2.py`. Not done: CSV formula-injection note.

## L1
Layout key is `sh.workbench.<account id>.<screen>` (`/api/auth/me` now also returns `account_id`; `test_auth` updated). `testTimeout: 15000`. Pin, Enlarge and Close are small icon buttons (aria-label and title carry the name). The Composer's paper-clip is gone: "Add context for a more relevant conversation" is the only attach control (a file can still be dropped on the box; i6 and voice tests use a drop).

## Screens
- `ui/src/v1/g1/`: `LockedProject` (lock, title/stage/owner for Internal, only "exists" for Restricted, Request access, requested/denied states), `ProjectAccess` (header: Open/Internal/Restricted, the team, a select for the owner), `ProjectAccessCard` (K1's `AccessCard` given an `answer` prop; shown in Pulse for `access` cards). `ProjectPage` shows the lock for a locked project. Tests: `g1/g1.test.tsx`.
- North's "Open the benchmark sheet" goes to `/centre/project/<pid>?artefact=benchmarks`; Span's Benchmarks document lists the sheet's rows and links the same page.
- TICKETS in the top bar for every company role (`copy.ts`, `roles.ts`, `CentreShell`), after Consume centre; `shell.test.tsx` and `test_role_table.py` updated.

## Not run / pre-existing
`tests/auth`: `test_role_matrix` needs ardmore credentials that are not seeded here; `test_every_real_route_is_declared` lists `POST /api/v1/build/{iid}/deviations/{did}/make` (G4) as undeclared, and three more in `test_auth` fail for reasons outside this change. Say if you want them chased.

## Fixes 2 (8 Oct, after the re-check)
1. G1.join is no longer self-service. `T2.assigned_on` counts a ticket only when the one who gave it (last raised/assigned/delegated entry) is not the viewer and holds "full" on the project (team or company admin, `G1.named_full`) or is an agent. A ticket raised to oneself never joins anyone.
2. Run book: `g2_routes._gate` lets a non-full person in only if the project is live, they hold the ops seat and `assigned_on` is true (a ticket from someone with "full"); only then does ops join. Open projects' "read" no longer opens it.
3. `GET /consume` filters intents by `G1.can_read_intent` (new helper). 4. `GET /consume/offers?intent=` and `POST .../have` gate the intent (the newest intent when none is named). 5. `/extract/queue` filters by the document's intent; `/extract/{doc_id}` gates the document's intent. 6. `POST /ops/tickets` gates `pid` (403; a missing project still 400/404); `GET /ops/live` without `?iid=` drops projects the viewer cannot read.
Tests: `test_g1_gate.py` adds `test_nobody_joins_the_team_by_themselves` and `test_routes_keyed_by_query_or_body_refuse_or_filter` (403 or filtered, never 404); `test_x5.py` puts the engineer on the team before reading a document. Not done: review notes 7, 8, 10.
