# Review: G1 project access, T2 ticket centre, L1 workbench (8 Oct)

**Summary.** G1's helper is sound and every `/api/v1/projects/...` read goes through it, but every intent-keyed route (`/intents/{iid}/...`, `/build/{iid}/...`, `/consume/...`) still reads the same artefacts with no project check, so a Restricted project's SOW, design, mapping sheet (and its .xlsx) and brief are open to any signed-in seat. T2 is well built (sequential numbers under one lock, append-only history, past assignees keep read, CSV scoped to one ticket) with two small leaks of a locked project's title and a Pulse card that can vanish after a delegation. L1 keeps every behaviour the four screens had; its only real gap is the layout key is per screen, not per person, and the UI suite is flaky under load (5 s timeout), not broken.

**Checks run.** `SH_MODEL_PROVIDER=off python -m pytest tests/v1 -q`: 111 passed. `npx tsc --noEmit -p .`: clean. `npx vitest run src/v1`: 4 of 62 fail with "timed out in 5000ms" (a1, i6, f1; `c4/ContextBox.test.tsx` races on a `findBy`); a second full run failed a different 2 (workbench, m1); every failing file passes on its own. Flaky, not red.

**Verdict.** Not ready. Fix B1 (one line per route) and B2 (the Internal decision) before this lands; the rest can follow in the fix round.

## Blockers

**B1. Project access is enforced only on `/api/v1/projects/...`; the intent-keyed routes read around it.** `may_see_project` is called by p1/p2/m1/g3/g1 routes and by the four agents' `chat()` (POST) only. Scenario: Priya makes a project Restricted; Leela (analyst, not on the team) gets 403 from `GET /api/v1/projects/{pid}/artefacts/intent` but 200 from every route below, and reads the same content.
- `sh_platform/v1/i2_routes.py:92` `GET /intents/{iid}/thread` returns thread + SOW. `i6_routes.py:61` `GET /intents/{iid}/chat` returns `C.view` (SOW, process map) and, for any decision-maker seat, runs `answer_pending` (a model call on someone else's thread); `i6_routes.py:73` uploads into another person's intent.
- `a1_routes.py:47` `GET /build/{iid}/chat` (design, data model, scan, mapping summary, questions). `f1_routes.py:35` `GET /build/{iid}/engineer` (mapping rows with SQL, open points), `:73` `flagged.md`. `c3_routes.py:30` `GET /consume/brief?iid=`.
- `b1_routes.py:18` design; `b2_routes.py:49` scan; `b3_routes.py:82` `mapping.xlsx` (also skips `G1.export_allowed`, the one export G1 says needs a role) and the other b3 GETs; `b4_routes.py:82` runs; `p4_routes.py:20` benchmarks; `g4_routes.py:34` deviations (before/after text) and `:40` POST; `c1_routes.py:16` consume views; `c4_routes.py:63,69` the conversation's ticks; `x5_routes.py:29` extract; `t1_routes.py:70` template; `g2_routes.py:39-56` run-book draft/edit/sign (`P1.read` with no G1 and no "live" check, so the ops seat edits any project's run book before go-live).
- `p3_routes.py:51` `GET /build/waiting` lists the title of every signed SOW, Restricted ones included, to any seat.
- Smallest fix: `G1.http_gate(plane, viewer, iid)` (already written, `g1_access.py:148`) as the first line of each handler above ("full" for the writes); in `p3_routes.waiting` drop rows whose `G1.level` is "none" and show title only for "preview". `test_g1.py` tests `check_agent` directly (line 128) and never a GET route, which is why this passed.

**B2. Internal = team only (orchestrator's decision), built as "any analyst reads Internal".** `g1_access.py:88-89` returns "read" for any analyst unless Restricted. Scenario: Leela (analyst, off the team) reads an Internal project's intent of work; the owner was told only the people they name can. Every place that changes:
- `g1_access.py:88-89` delete the two lines; docstring `:5`; `G1.md` "The rules as built" and the first open question.
- Tests that encode the old rule: `tests/v1/test_g1.py:80` (`leela ... == 200` becomes 403), `tests/v1/test_g3g4.py:271` (`"read"` becomes `"preview"`).
- Pick-up adds the builder: already true. `p3_routes.py:48` `set_person("builder")` puts the name in `people`, and `team_of` (`g1_access.py:60-71`) reads `people` first. Nothing to add.
- Design submitted adds the head of data: no site today. `a1_chat.py:414` sets `state = "ready"`; add `P.set_person(pid, "head_of_data", <name>)` there. Note `a1_routes.py:25` defines the head of data as the `company_admin` role, who is already "full"; `p1_project.py:149-150` fills the part only after approval. Harmless until the head of data becomes a named seat.
- Go-live adds ops: `g1_access.py:86-87` already gives the ops seat "read" once `stage == live`; `p5_handover.go_live:133` never sets `people.ops`. Either keep the seat rule or `set_person("ops", by)` at the first run-book edit (`g2_routes.py:44`). Nothing blocks.
- The data engineer who is not the builder: `PEOPLE` (`p1_project.py:24`) has no engineer part and F1 raises "to builder" (`f1_chat.py:428`), so with B2 an engineer off the team is refused by `check_agent` (`f1_chat.py:368`). Add the engineer to `team` (role "data engineer") on their first Flow answer, or accept that the builder is the engineer. `ui/src/v1/f1/EngineerPage.tsx:110` shows the composer to any analyst; the 403 sentence then does the explaining.
- `p2_pulse.py:244-246` needs nothing (analysts get the lock line). `m1_map.restrict_nodes` hides Restricted nodes only (card wording); Internal nodes stay on the map for everyone. Say if that should follow the decision.

## Should fix

**S1. T2 shows a locked project's title to a ticket's assignee.** `t2_tickets.py:417-421,432` `row()` fills `project_title` from `P1.read` for every visible ticket; `ui/src/v1/t2/TicketPage.tsx:28` and `TicketsPage.tsx:60` print it. Scenario: Priya raises a ticket on a Restricted project to Dev (off the team); the list and the page show the project's title, which G1 says Dev may not see (links are correctly locked, `:369`). Fix: in `row()`, `_title` only when `G1_level(...) in ("full","read")`, else the words `lock_row` gives.

**S2. T2 Pulse card lost after a delegation.** `t2_tickets.py:514-524` `_covered` hides the Needs-you card when the linked comment is open, whatever that comment is addressed to. Scenario: the Watcher's ticket (comment to Leela) is delegated to Dev; Dev gets no card (the comment card goes to Leela) and no ticket card. Fix: `_covered` also requires `_me(c.get("to"), viewer)`.

**S3. Ticket numbers across processes.** `t2_tickets.py:139-148` serialises raises on `lock_for(d)`, a `threading.RLock` (`sh_platform/jsonfile.py:19`): correct for one process, not for two (the production build on 8200 and the watch script on the same data dir). Two raises at once can both compute `TCK-0004` and `write_json_atomic` replaces silently. Fix: claim the number with `os.open(path, O_CREAT|O_EXCL)` and retry on `FileExistsError`; mark it `# ponytail:`.

**S4. T2 open-ticket count on a lock line.** `t2_tickets.py:481-484` sets `open_tickets` on every Pulse line with a pid, including G1 lock rows (`p2_pulse.py:246` keeps `pid`). Fix: skip lines with `locked`.

**S5. L1 layout is per screen, not per person.** `ui/src/v1/workbench/Workbench.tsx:17` key `sh.workbench.<screen>`; the card says per person per screen. Two people on one browser share a layout. Fix: take the account id from `useSession` and put it in the key.

**S6. UI suite flaky under load.** `ui/vite.config.ts:11-15` has no `testTimeout`; 25 jsdom environments make 5 s too short (two full runs, two different sets of failures, all green alone). Fix: `testTimeout: 15000` in the `test` block.

**S7. A test that passes for the wrong reason.** `tests/v1/test_t2.py:95` `assert A or B` then `assert B`: the Needs-you card (A) is never actually checked and is in fact absent (the Watcher ticket is "covered" by its comment card, S2). Replace with an assertion on what is intended.

## Notes

- G1 S10 is wider than the card: a comment addressed to a person gives "read" on the whole project (`g1_access.py:90-92`), not the one line. Acceptable; say so in `G1.md`.
- `g1_access.defaults:175` puts every sponsor in the company on every new team; with two sponsors both see everything. Intended "the sponsor" (one).
- `_sync_rows:401-416` replaces a project file's `grants` wholesale, so a K1 grant given on the file itself is wiped by any project access change.
- `g1_routes.py:51-61` `GET .../access` returns `can_manage` and `requests` to a "read"-level viewer; fine (requests are filtered to the viewer's own).
- T2 `log_csv` (`t2_tickets.py:405`) does not neutralise notes starting with `=`, `+`, `-`, `@` (spreadsheet formula injection); prefix with `'`.
- T2 `say()` (`:229`) lets a past assignee comment, the card gives them "read". Harmless.
- T2 `migrate` runs only from `listing` (`:440`), so Pulse counts before anyone opens `/centre/tickets` come from P2's comment count; fine, documented.
- L1 behaviours checked and kept: Sign (`i4/SowPage.tsx:103`, untouched), Hand to the architect (`i6/ConversationPage.tsx:202`), Make it now (`g3/DeviationCards.tsx:37`; Flow links to it `f1/EngineerPage.tsx:47`), Approve (`a1/SpanPage.tsx:182`), Sign the build pack and Run the load (`f1/EngineerPage.tsx:83,86`), voice `Composer`/`SpeakButton`/`useReadAloud`, `ModeLine`, `ProjectTag` and the welcome bubble on all four screens.
- "Add context" never ticks from the library list; an upload made from it with an `iid` is ticked by the backend (`c4_library.py:182-183`), which is the person's own act. `L1.md` should say so rather than "nothing auto-ticked".
- localStorage failure: `Workbench.tsx:19-23,44-46` wrap every read and write; the test at `workbench.test.tsx:62` covers it. Esc is a window listener, so it also fires while typing in the composer; harmless.
- `workbench.css:13` uses `:has()` for the sticky pinned card; fine in current browsers, no fallback for old Safari.
- `G1.md` and `T2.md` match what is built except the two points above (S10 width, upload tick).

## Re-check after fixes (8 Oct)

`SH_MODEL_PROVIDER=off python -m pytest tests/v1 -q`: 114 passed. Read-only re-check of what FIX-G1T2L1.md changed.

### Closed
- B1 path/query intent routes: closed. `g1_access.py:159-172` `intent_gate` is on every router (`v1/__init__.py:30`); the walk in `test_g1_gate.py:19-41` asserts 403 (never 404) on every `{iid}` route and requires 40+ gate sentences; `?iid=` covered for `/consume/brief`, and the same code path serves `/ops/live?iid=` and `/router/costs?iid=`.
- The three exemptions hold on their own: `/intents/{iid}/project` → `G1.shown` lock row (`p1_routes.py:54-61`); `/build/pickup/{iid}` → 404 at level none (`p3_routes.py:64-66`); `/build/{iid}/engineer*` → `f1_routes._gate:39-45` calls `http_gate` on all four handlers.
- B2 Internal = team only: closed (`g1_access.level:82-93`, no analyst rule).
- S1, S2, S4: closed (`test_g1_gate.py:65-75`). S3 `O_CREAT|O_EXCL`, S5 account id in the layout key, S6, S7: as described, not re-run.

### Not closed / new findings (ranked)
1. **G1.join is self-service (read → full).** `f1_routes.py:43` joins any DATA_ENGINEER seat (= any analyst, `seats.py:18`) who holds an active ticket on the project; `t2_tickets.start:277-281` lets anyone with "read" raise a ticket *to themselves* (`to` defaults to `viewer.name`) and never checks who raised it. Scenario: Leela (analyst, "read" on an Open project, or via a comment/grant on an Internal one) posts `{"project": pid, "title": "x"}` to `/api/v1/tickets`, then GETs `/build/{iid}/engineer`: she is now "full" and can post designs, mappings, loads and signatures. Same through delegation (`reassign`). Fix: in `assigned_on` require the ticket's raiser to hold "full" on the project and to differ from the assignee, or join only from the owner's/builder's explicit assignment.
2. **Run-book join is the same hole for the ops seat.** `g2_routes._gate:24-27` joins any OPS_MANAGER seat (= any analyst) at "read" on a live project — Open projects give everyone "read" — on draft, edit *and* sign, before the body is validated. Fix: join only when the "read" came from the ops-seat rule and the project is not Open, or drop the join and keep the seat rule.
3. **`GET /api/v1/consume`** (`c1_routes.py:11-13`, `c1_cards.build:97-105`) has no viewer: every signed intent's title, KPIs and figures go to every company role, Restricted included. The per-figure route is gated; the list is not.
4. **`GET /api/v1/consume/offers?intent=`** (`c2_routes.py:26-28`) keys the intent as `intent`, not `iid`, so `intent_gate` never fires; it reads the SoW's KPIs and sources. `POST .../have` takes `intent_id` in the body, same gap (sponsor/admin only, so lower).
5. **X5 reads a project's documents with no G1.** `/extract/queue` (file names, intent ids) and `/extract/{doc_id}` (`x5_extract.detail:597-604` returns the document's lines) to any analyst (`x5_routes.py:95-104`).
6. `POST /api/v1/ops/tickets` (`p5_routes.py:26-28`, `p5_handover.raise_ticket:147-157`) raises on any `pid` without a G1 check; `GET /api/v1/ops/live` without `?iid=` lists every live project's title, builder and tickets to any analyst/sponsor.
7. Pick-up: `p3_routes.py:64-66` only refuses level none, so any architect seat picks up an Internal waiting project and becomes builder ("full"). Declared on purpose in the fix doc; say so in `G1.md`, since it is the one way an Internal project widens without its owner.
8. `_OPEN_PATHS` (`g1_access.py:156`) is a substring match (`"/project"`, `"/engineer"`): a future `/intents/{iid}/projections` would be exempt unnoticed. Match the route tail exactly.
9. `test_g1_gate.py` never walks query-keyed routes generically (only `/consume/brief`), nor `intent=`/body-keyed ones (findings 3-6 are exactly the shapes it misses). Add the same walk over routes whose handler takes `iid`/`intent` as a query or body field.
10. a1 join of the head of data (`a1_chat.py:420-421`) adds the first company admin by name; admins are already "full". Harmless; `defaults:214` still adds every sponsor.

### Verdict
Not ready. The gate itself holds (B1 closed), but `G1.join` lets a "read" person promote themselves to "full" through a self-raised ticket or a run-book edit (1, 2), and four non-iid routes still hand out a Restricted project's titles, figures, SoW and document lines (3-6). Fix 1-6 and extend the walk (9); 7-8 and 10 are notes.
