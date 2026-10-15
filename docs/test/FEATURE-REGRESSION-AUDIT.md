# Feature regression audit: before and after the four-centre rebuild (9 Oct 2026)

Rule (Nitin): every feature that existed before the rebuild still exists and is reachable by a normal user in at most two clicks from the new shell (bar, centre landing, Settings), unless Nitin removed it explicitly.

Before = `Backups/Repo 1.0 - 2026-10-09 before four centres`. Now = `Repo 1.0` as read on 9 Oct evening.

## What was explicitly removed (not restored)

| What | Where Nitin said so |
|---|---|
| Flow, Jev (as a persona), investigation and briefing agents as *names*; their code becomes Span's and Lumen's tools | `docs/plan/V3-CENTRES-CARDS.md:12` |
| Brainstorm, charter, check-in, problem and decision *entry points in menus* (code stays) | `docs/plan/V3-CENTRES-CARDS.md` card S1 |
| Settings (people, rules, sources and model, templates, signed register, agent runs, Testing/Real) behind the person's name, admin and head of data only | card S1 (same file) |

Everything else below was "redirected to its new home" by card S1. A redirect to a page that does not hold the feature is a loss, not a move, so it is restored.

## Findings after dedupe (43 auditor rows collapse to 24)

Click counts are from the new bar. "Restore" means the smallest edit that makes the old screen reachable again; no screen is rebuilt.

| # | Feature | Before | Now (verified) | Decision | Owner group |
|---|---|---|---|---|---|
| 1 | Company knowledge graph `/centre/intent/graph` (m1 MapPage: clusters per intent, search, node panel, "Something looks wrong", K2 suggest-a-change and merge proposals) | COMPANY MAP bar item for every company role (`backup shell/copy.ts:11`) | Route `v1/m1/routes.tsx:4` and backend intact, but `shell/redirects.ts:16` still sends it to `/centre/intent`; `shell.test.tsx:140` asserts that. Not restored, despite the brief. K2Panel is only imported by m1, so suggest/merge are unreachable too. Server hrefs still point here (`p2_pulse.py:123,202`, `k2_map.py:905,910`, `consume/cards.py:252`, `knowledge_map.py:219`). | Restore: delete redirect line 16 and test row; show it as a "Company map" tab on `/centre/map` and as a link on the Intent landing | G1 (redirect), G5 (tab and link) |
| 2 | Map bar entry for participant, owner, approver, sponsor | COMPANY MAP shown to every role with "map" (`roles.ts` table, all six roles) | `roles.ts:32` adds Map only when `canSettings`; backend `k3`/`m1` permissions still allow all roles | Restore: drop the `canSettings` condition (Health tab stays data-team only inside the page, `k3/MapPage.tsx:19`) | G1 |
| 3 | Node pages `/centre/intent/map/:nodeId` crumbs and lineage button | Crumb "map" went to `/centre/intent/graph` | Route and links intact; `pages/NodePage.tsx:109,112,131` crumbs now go to `/centre/map`, which cannot show the node; `WhereItLives.tsx:73` lineage link is swallowed by the redirect | Restore: crumbs back to `/centre/intent/graph` once the redirect is gone; lineage view stays as in the old build (only `pages/GraphPage.tsx` implements it, and m1 shadowed it before too) | G5 |
| 4 | Home / Pulse `/centre/home` (needs-you cards incl. project-access approve/decline, "Your projects today" with last load and moved KPI, "Worth a look", seats, "Start a project") | HOME bar item, `v1/pulse/routes.tsx:4`, GET `/api/v1/pulse` | `redirects.ts:9` sends `/centre/home` to `/centre/action`; Action Today is the v2 e5 feed, a different list. PulsePage, ProjectAccessCard and `/api/v1/pulse` have no caller. Stray links bounce (`k1/AccessPage.tsx:28`, `InterviewPage.tsx:204`, `CharterView.tsx:360`). | Restore: stop redirecting `home` (keep `today` and `pulse`); add Action tab "Projects today" linking `/centre/home` (1 click from Action) | G1 (redirect), G2 (tab) |
| 5 | Tickets list, raise a ticket, ticket detail | TICKETS bar item, `v1/t2/routes.tsx:6-7`, all company roles | `redirects.ts:13` sends every `/centre/tickets*` to `/centre/action/cases`; no link anywhere; `TicketPage.tsx:27` crumb and server hrefs (`t2_tickets.py:521-537`) land on Cases | Restore: delete redirect; add Action tab "Tickets" | G1, G2 |
| 6 | Evidence list (all manager statements, Current/stale) and "All statements" crumb | EVIDENCE bar item, `v1/e2/routes.tsx:6` | `redirects.ts:12` sends the bare path to Cases; `a5/routes.tsx` has only the per-document route; `ActionCentre.tsx:24` HOME rewrites `/centre/evidence` to Cases; EvidenceList is dead code | Restore: route `action/evidence` wrapping EvidenceList, Action tab "Evidence", redirect bare `/centre/evidence` there, HOME entry updated | G1, G2 |
| 7 | Extraction review queue `/centre/extract/review` and `/centre/intent/:iid/extraction` | Linked from Pulse "Worth a look" (`p2_pulse.py:279`) | Routes (`x5/routes.tsx:6-7`) and backend intact; only reachable through Pulse, which is redirected | Restore: comes back with #4; also a "Review queue" link under the Action tabs | G2 |
| 8 | CIO Brief | From Pulse/Today links | Reachable: Consume > Office view > Open the CIO Brief (2 clicks from Consume landing, 3 from bar) | Restore (cheap): "Office view and CIO Brief" link under the Action tabs | G2 |
| 9 | Build entry: signed intents waiting for a builder, pick up, Design and Pipeline links (the only door to the per-intent Span rooms) | `v1/p3/BuildEntry.tsx` mounted at `/centre/build` (`backup p3/routes.tsx:21`) | `p3/routes.tsx` registers only `intent`; `/centre/build` is b6 ProjectsPage; nothing in `ui/src` links `/centre/build/:iid`; server hrefs still do (`x2_home.py:78-92`, `p2_pulse.py:141`, `m1_map.py:322,331`) | Restore: emit `intent_id` from `b6_routes.projects()` and `_view()` (`p1_project.py:101` stores it), and put a Rooms link line on ProjectsPage rows and BuildPage header. Do not remount BuildEntry at `build` (clashes); if the pick-up step is wanted, mount at `build/work` | G3 |
| 10 | Span blueprint chat `/centre/build/:iid` (three documents, layers diagram, data model doc, approve and hand over, read aloud, ModeLine, doc tools via `a1_chat.py:271`) | Reached from BuildEntry | Code and route (`a1/routes.tsx:4`) unchanged, no link. New b6 Span chat (`b6_span.py:414`) is rule-based with no doc tools or skill | Restore via #9 ("Design with Span" link). Giving b6_span the a1 engine is a build decision for Nitin, not a regression fix | G3 |
| 11 | Scan `/build/:iid/scan`, mapping sheet with .xlsx download `/mapping`, engineer room `/engineer` (open points, flag for human, run the load), run log `/runs` (checks, Span note, set-aside), deviations `/deviations`, full DesignPage `/design` | Linked from SpanPage, EngineerPage, BuildEntry | Routes `b2`, `b3`, `f1`, `b4`, `g3`, `b1` intact; no entry from the new shell | Restore via #9: Rooms links Design · Scan · Mapping sheet · Pipeline room · Run log · Approval requests; "Full run log" link under Pipeline last runs in `b6/Steps.tsx` | G3 |
| 12 | Project page `/centre/project/:pid` (four artefacts, comments, who holds which part, access, DeviationCards) | From Pulse project lines and the ProjectTag chip | Route and ProjectTag intact (2 clicks from Intent); Build and Consume project pages do not link it, so an approver coming through Build cannot see deviations | Restore: "Project page: documents, run book, deviations" link next to "All projects" on BuildPage; project id on ProjectsPage links there too | G3 |
| 13 | Data intake and file landing (upload, files by source, profile, column mapping Accept/Not this, control totals) `/centre/data/intake(/:fileId)` | DATA INTAKE bar item, `e0c/routes.tsx:6-7` | `redirects.ts:14` has no `!c` guard, so both paths go to `/centre/build`; `b6/Steps.tsx:23` "Add files" therefore bounces; `ActionCentre.tsx:24` rewrites intake links too; Today cards (`e5_pulse.py:206,211`) link here. Sheet mappings approved on FilePage are what `b6_span.approved_mappings` reads. | Restore: delete redirect line 14 and the HOME intake pair; add "Data intake" link on ProjectsPage (1 click from Build) | G1, G2 (HOME pair), G3 (link) |
| 14 | Ops `/centre/build/ops` (per-source last run, alerts Acknowledge/Close, Loaded/Not loaded, live projects card) | Target of the BUILD CENTRE bar item (`backup copy.ts:8`) | `redirects.ts:15` sends it to `/centre/build`; nothing else mounts OpsPage or LiveCard; many links still point here (`ProblemTriage.tsx:80`, `OpportunitiesPanel.tsx:47,264`, `pulse/lines.py:297-466`, `proposals.py:409`, `chain.py:313`, `t2_tickets.py:358`) | Restore: delete redirect line 15; "Ops: loads and alerts" link on ProjectsPage | G1, G3 |
| 15 | Span chat extras in Build: attachments, read aloud, ModeLine | `a1/SpanPage.tsx:253,277,284` | `b6/BuildPage.tsx:50` clears files without sending them (`api.sendChat` takes text only; `post_chat` reads `body.text`); no ModeLine, no SpeakButton | Restore: ModeLine in the chat head; hide the attach control until the backend reads files (honest), or pass files through `sendChat` and save to project intake | G3 |
| 16 | Signed KPI cards with click-through to the run that loaded each figure, "What has been built for you", Offers section, "Shape what you see" | `/centre/consume` = `p3/ConsumeEntry` rendering `c1/ConsumePage` (KPI cards, FigurePanel, ShapeLink, OffersSection) | `p3/routes.tsx` has only `intent`; `c1/routes.tsx` is empty; `/centre/consume` is cxui ProjectList (Office, Managers, Benchmark links only). ConsumeEntry and ConsumePage are orphans. | Restore: route `consume/figures` -> ConsumeEntry in `p3/routes.tsx`; links "Signed KPIs and offers", "Shape what you see" (`/centre/consume/design`), "Offers" (`/centre/consume/offers`) in the ProjectList nav | G4 |
| 17 | Lumen brief designer `/centre/consume/design(/:iid)` and end-user Ask page | ShapeLink inside ConsumePage | Routes `c3/routes.tsx:6-8` and `c3_chat.py:276` intact; no link | Restore via #16 | G4 |
| 18 | Consume 2.0 rooms: feeds, measure, market, what-if, lens; ConsumeCentre hub | Routes `App.tsx:146-150`; ConsumeCentre imported but never routed, so already URL-only before | Same; FeedsPage empty state now points at `/centre/map` | Not a regression. Optional one-liner: route `consume/views` -> ConsumeCentre and a link in the ProjectList nav | G4 (optional) |
| 19 | ModeLine in the new Lumen chat | ModeLine in every agent chat head | `cxui/ProjectPage.tsx` and `talk/TalkBox.tsx` have none | Restore: ModeLine in ProjectPage chat head | G4 |
| 20 | Settings sections two clicks from the avatar (Templates, Data model, Rules were direct avatar items before) | `backup CentreShell.tsx:79-81` | One "Settings" item (`CentreShell.tsx:89`); Settings opens on People, so every other section is 3 clicks | Restore: list the Settings sections directly in the account menu (labels from `s1/SettingsPage.tsx` SECTIONS) | G1 |
| 21 | "What the agents remember about you" | Avatar item for anyone with Pulse | Non-admins 2 clicks; admin and analyst 3 clicks (inside Settings only, `CentreShell.tsx:90`) | Restore: show the memory link for everyone (falls out of #20) | G1 |
| 22 | Signed register `/centre/register` for sponsor, owner, approver, participant | Route open to all company roles by URL; no menu link | Redirected to Settings > Signed register, admin and analyst only (`SettingsPage.tsx:61,70`); other roles get "not open to you" | Keep as narrowed: card S1 lists the register among the admin/head-of-data Settings sections. Open question for Nitin: should sponsors read it? If yes, `open: true` on the register entry. Fix the empty-state link `RegisterPage.tsx:62` with #1. | G5 (link fix only) |
| 23 | Intent admin, areas and people admin, backlog, past, outcomes | Reached only from inside Intent pages, no bar entry before either | Routes intact (`App.tsx:123-131`); IntentWelcome links none of them; `IntentAdmin.tsx:226,295,310` link `/company/settings/areas`, a route that never existed (pre-existing dead link; real page is `/centre/intent/admin/areas`) | Restore: "Intent admin" Settings section linking `/centre/intent/admin`; fix the three dead links; "Backlog" and "Past intents" links on the Intent landing | G5 |
| 24 | Agent skills editor listing and company overrides for the retired skill names | `skill_loader.agents()` listed seven folders; company copies under `skills/flow` etc. applied | ALIASES (`skill_loader.py:18-22`) hide `data/flow/intake/investigation/briefing/consumer` and `_company_dir` rewrites the name, so a company override saved under an old name is silently ignored; repo `skills/flow`, `intake`, ... are orphan files | Keep three agents (explicit, cards line 12). Fix only the silent loss: read a company folder under the old name as a fallback. Folding the retired text into span/lumen is a content decision for Nitin. | G6 |

### Not regressions (no restore needed)

- `pages/GraphPage.tsx` (five-column classic graph): shadowed by the m1 route before and now.
- Backend routes with no UI caller before or now: v1 `evidence/asof`, `evidence/chain`, `access/groups`, `library/*`, `map/collision`, `map/comments`, `intake/scan`, `company/documents`, `home`, `context/suggestions`, `model/layers`; 2.0 `/api/company/build|consume|whatif` writes; `/api/intents/*` admin, glossary, knowledge-map, radar, charter and closure; module routes `m1_intent`, `m2_baseline`, `m3_connect` (most go through a BASE constant and are grep false negatives). Wire only if Nitin asks.
- Evergreen vector index thin (1 of 69 files embedded): the seeds never called `doc_index.ensure` before either. Optional: G6.
- `p3/BuildEntry.tsx`, `ConsumeEntry.tsx` and `p3.test.tsx`: orphans today, back in use after #9 and #16.

## Restore groups (file sets do not overlap)

| Group | Files | Items |
|---|---|---|
| G1 Shell | `ui/src/shell/redirects.ts`, `ui/src/shell/shell.test.tsx`, `ui/src/shell/roles.ts`, `ui/src/shell/CentreShell.tsx`, `ui/src/shell/copy.ts` | #1 #2 #4 #5 #6 #13 #14 redirect lines and test rows; Map for all roles; account menu lists the Settings sections and memory for everyone |
| G2 Action | `ui/src/v1/a5/ActionCentre.tsx`, `ui/src/v1/a5/routes.tsx` | Tabs Projects today (`/centre/home`), Tickets (`/centre/tickets`), Evidence (`action/evidence` wrapping EvidenceList); links Review queue and Office view and CIO Brief; HOME map: evidence -> `action/evidence`, drop the intake pair |
| G3 Build | `sh_platform/v1/b6_routes.py`, `ui/src/v1/b6/api.ts`, `ui/src/v1/b6/ProjectsPage.tsx`, `ui/src/v1/b6/BuildPage.tsx`, `ui/src/v1/b6/Steps.tsx`, `ui/src/v1/b6/links.test.tsx` (new) | `intent_id` on rows and view; Rooms links (design, scan, mapping, engineer, runs, deviations) on rows and header; Ops, Data intake, Project page links; Full run log under last runs; ModeLine; attach control hidden or wired; one vitest asserting the links so the next re-cut cannot drop them |
| G4 Consume | `ui/src/v1/p3/routes.tsx`, `ui/src/v1/cxui/ProjectList.tsx`, `ui/src/v1/cxui/ProjectPage.tsx`, `ui/src/App.tsx` | `consume/figures` -> ConsumeEntry; nav links Signed KPIs and offers, Shape what you see, Offers, (optional) Business views hub via `consume/views` -> ConsumeCentre; ModeLine in the Lumen chat head |
| G5 Map and Intent | `ui/src/v1/k3/MapPage.tsx`, `ui/src/v1/p3/IntentWelcome.tsx`, `ui/src/pages/NodePage.tsx`, `ui/src/pages/RegisterPage.tsx`, `ui/src/v1/s1/SettingsPage.tsx`, `ui/src/intents/IntentAdmin.tsx` | "Company map" tab on Map rendering m1 MapPage (or linking `/centre/intent/graph`); Company map, Backlog, Past intents links on the Intent landing; node crumbs back to the graph; register empty-state link; Intent admin Settings section; dead `/company/settings/areas` links fixed |
| G6 Skills and seeds (backend, optional) | `sh_platform/v1/skill_loader.py`, `tools/seed_evergreen.py`, `tools/seed_v3_demo.py` | Company override fallback under the retired skill names; `doc_index.ensure` per landed document |

Ordering: G1 first (nothing in G2-G5 is reachable while the redirects stand); the rest in parallel. Open questions for Nitin: signed register for sponsors (#22); b6 Span with the a1 engine (#10); fold retired skill text into span/lumen (#24).

## G2 Action (restored)
- ActionCentre.tsx: tabs Projects today (/centre/home), Tickets (/centre/tickets), Evidence (/centre/action/evidence); links under tabs: Review queue (/centre/extract/review), Office view and CIO Brief (/centre/consume/office). HOME map: evidence list links now stay in /centre/action/evidence; intake pair removed so Today cards reach /centre/data/intake. `Stay` is now exported.
- a5/routes.tsx: added action/evidence (full statements list via EvidenceList).
- Backups: .sh-tmp/ActionCentre.tsx.bak-restore, .sh-tmp/a5-routes.tsx.bak-restore.
- Checks: npx tsc --noEmit clean; vitest src/v1/a5 4 files, 12 tests pass. No new tests added.

### G4 Consume restore result

- `p3/routes.tsx`: `consume/figures` -> ConsumeEntry (#16).
- `cxui/ProjectList.tsx` nav: Signed KPIs and offers, Shape what you see, Offers (#16, #17), Business views, feeds, market, what-if (#18).
- `App.tsx`: `consume/views` -> ConsumeCentre inside the consume RoleGate (#18).
- `cxui/ProjectPage.tsx`: ModeLine in the Lumen chat head (#19).
- Backups in `.sh-tmp/*.bak-restore`. Checked: `npx tsc --noEmit` clean; vitest p3, cxui, c1 (3 files, 9 tests) pass.

## G5 Map and Intent (restored)
- k3/MapPage: "Company map" chip navigates to /centre/intent/graph (m1 map with K2 panel: suggest a change, merges, owner answers, notes). Not in TABS.
- IntentWelcome: "Around your intents" panel links Company map, Backlog, Past intents (1 click).
- NodePage crumbs/back link now /centre/intent/graph. RegisterPage already pointed to /centre/intent/graph; unchanged.
- SettingsPage: new "Intent admin" section linking /centre/intent/admin (2 clicks).
- IntentAdmin: dead /company/settings/areas(/people) links fixed to /centre/intent/admin/areas(/people).
- Open question for Nitin: should sponsors read the signed register (then open:true on its SECTIONS entry)?
- Tests: tsc --noEmit clean; vitest k3, p3, s1, intents, pages: 555 pass, 1 fail (intents/WallView.test.tsx "3 days left" vs "24 hours left", date-dependent, not touched by this change).
- Backups: .sh-tmp/*.bak-restore.

## G1 Shell: redirects, Map for all roles, account menu (restored)
- redirects.ts: removed redirects for /centre/home, /tickets, /data/intake, /build/ops, /intent/graph (old pages reachable again). Bare /centre/evidence now goes to /centre/action/evidence.
- roles.ts: Map is in the bar for every role that has it (Health tab stays data-team only).
- CentreShell.tsx + copy.ts: account menu lists the seven Settings sections directly (2 clicks) for the data team; the memory link shows for everyone with Action.
- shell.test.tsx updated (rows removed, evidence row added, bars now include Map). Backups in .sh-tmp/*.bak-restore.
- Run: vitest src/shell 27 passed; tsc --noEmit clean; pytest tests/auth/test_role_table.py (see summary).
- Open: sh_platform/route_permissions.yaml not checked/edited (outside G1 file list); confirm /centre/map is allowed for participant/owner/approver/sponsor on the server and in the UI RoleGate.

## G6 result (skills and seeds)

- Done: `skill_loader._company_dirs` now reads the company folder under every retired name that folds into the agent (flow/intake/investigation/data into span; briefing/consumer into lumen), then the agent's own folder last, so a pre-rename override still applies and a newer one wins. Three agents unchanged. Test: `tests/test_skill_loader_retired.py` (passes). Backups in `.sh-tmp/*.bak-restore`.
- Not done, no code to change: `seed_evergreen.py` and `seed_v3_demo.py` land no document files (only warehouse rows, intent/build/consume JSON), so there is no per-document place to call `doc_index.ensure`. The thin evergreen index comes from the seed that lands documents (`tools/seed_10uc.py` already calls it). Left as optional; needs a decision on which documents the evergreen seed should land.

## G3 Build: result (restored)

Items 9, 10, 11 (and 12-14 Ops, intake, project page, ModeLine, guard test) done. Backups in `.sh-tmp/*.bak-restore`.
- `b6_routes.py`: `intent_id` added to `projects()` rows and `_view()` base. `api.ts`: `intent_id` on ProjectRow, Plan, NoPlan.
- `ProjectsPage.tsx`: Rooms column (Design with Span, Scan, Mapping sheet, Pipeline room, Run log, Approval requests) via a shared `Rooms` in `Steps.tsx`; "Project page" link per row; page links "Ops: loads and alerts" and "Data intake".
- `BuildPage.tsx`: Rooms line, "Project page: documents, run book, deviations" next to "All projects", ModeLine in the chat head. Attach/drop disabled in the composer because `sendChat` sends no files (re-enable when post_chat reads them).
- `Steps.tsx` Pipeline: "Full run log" link; "Add files" kept (needs G1 to drop the intake redirect).
- BuildEntry not remounted at `build`; pick-up step still unmounted (mount at `build/work` if wanted).
- Guard: `ui/src/v1/b6/links.test.tsx`.
- Tests: vitest `src/v1/b6` 9 passed; `tsc --noEmit` clean; pytest `tests/build -k "b6 or plan or project"` 8 passed.
- Open for Nitin: give `b6_span.chat()` the a1 engine (doc tools, load_skill, library lines); not a regression fix.

## OP1 (10 Oct): Consume's dashboard building moved to the studio, nothing dropped

Nitin: "Lumen should act like how it is acting in Consume, and in Consume there should be only the ready dashboards." Where each feature lives now is in `docs/plan/v4-landings/OP1.md`. In short: Lumen's conversation (thread per dashboard, proposals with Accept and Not this, follow-ups, memory, fresh talk, picture, rules-only note) moved from Consume's project page to Build > Dashboard studio ("Talk to Lumen"); Consume keeps reading, tables drawer, share, "Why did this move", "Where is this from?", comments, and Lumen answers questions there.
