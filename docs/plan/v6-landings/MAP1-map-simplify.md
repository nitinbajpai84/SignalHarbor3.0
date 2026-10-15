# MAP1: Map simplified, Operations split out

## What changed
- `/centre/map` is one page, "The office's ontology", with a three-way switch: Ontology (default, the existing whole-company graph, same style), Process map, Business glossary (the old Definitions tab). Subtitle: "People, projects and data, and how each number is made."
- Graph uses the full page width. Find box, One project select, State select, Show chips (People, Projects, Sources, Tables, Dashboards and reports, Definitions, Cases, Decisions; counts) and the lens chips sit compactly above it. The selected-item card is a slim overlay that opens on selection and closes with Close.
- Agents are filtered out in the view (nodes, edges, Show chips, counts). Data and API unchanged.
- No "Waiting for you" bar on the Map. Map review items now show in Action under "Waiting for my approval" ("Map review · N new items ... Review N") linking to `/centre/map/review` (head of data only, same rule as the queue). The review route is unchanged.
- New `/centre/operations`, "Operations: is everything arriving and running?" (data team only; same server refusal as the old Health tab). Four tiles, Sources table (all old Health columns), Live pipelines table. Build sub-navigation "Projects | Operations" (`b6/BuildNav.tsx`, shown to the data team) on Projects and Operations. Add Deliveries as another `<section>` in `k3/OperationsPage.tsx`.
- Old URLs: `/centre/map?tab=health` -> `/centre/operations`; `?tab=flow|conversations` -> `/centre/map` (keeps `?focus=`); `/centre/map/company` -> `/centre/map` (keeps query). `?tab=processes|definitions` still work.
- Repointed: `MAP_HEALTH` in `sh_platform/v1/b7_studio.py` and the RefreshLine default link now `/centre/operations` (text "See the source health in Operations"); Trail panel "Open in the map" now `/centre/map?focus=<id>`; Review queue links `/centre/map?project=`.
- Removed code: `FlowTab.tsx`, `ConversationsTab.tsx` (+test), `HealthTab.tsx` (now `SourcesTable.tsx`). Backups in `.sh-tmp/*.bak-map1`. Backend endpoints (`/centre-map/flow`, `/memory/graph`) untouched.

## How to test
Sign in as a data-team user (analyst). Open Map: three views, graph full width, click a node for the card, pick a project (growth steps), toggle Show chips. Open Build then Operations. Visit `/centre/map?tab=health`, `?tab=flow`, `/centre/map/company`. As head of data with items waiting, see the Map review line in Action.
Tests: `npx vitest run src/v1/k3 src/v1/a5 src/v1/a5trail src/v1/b7 src/v1/b6/b6.test.tsx --maxWorkers=2` (81 + new Action test = 82 pass); `npx tsc --noEmit` clean; `pytest tests/v1/test_b7_studio.py` 42 pass.
Screenshots (seeded Testing env, port 8731 under `.sh-tmp/testenv/map1`): `map1-map.png`, `map1-operations.png`.

## Audit, old vs new
Kept: whole-company graph, lenses (Data flow, Process, Definitions, People and decisions, Health), kind filter (as Show chips), State filter (now a select), One project at a time with growth steps and replay, find, node card with owner/state/neighbours, Process maps, Definitions (renamed Business glossary), Review queue page, "Company map" link to the Intent graph (now top right), relation legend (now one line under the graph), Health data (all columns, now Operations).
Removed on Nitin's word: Data flow tab, Conversations tab, Show as a list, duplicate Whole company chip, Waiting bar on the Map (moved to Action), Agents column.
Also gone (side effects, listed so none is silent): the "Also: ..." link row, the Review queue chip on Map (reachable from Action), the "Whole company" chip (lens chips now toggle off to return to all), the "Back to the whole company" button (the One project select's "All projects"), Agents Show filter.

## Departures from the artboards
- Graph kept in today's style per Nitin's later instruction, not the card grid; no definitions band; no side columns; no "Waiting" bar.
- Operations tiles: "Pipelines ran at 06:00" is "Pipelines whose last run was healthy" (no run-time target in the API). Live pipelines has no "Next run" column (no schedule data) and Checks counts passed rules of the last run. The seeded test env has no live pipelines, so its screenshot shows "No pipeline is live yet".
- Sources table keeps the old Health columns instead of the design's Expected/To do columns.
- Show chip "Dashboards, reports" keeps its existing label; Show and Lens rows wrap on narrow screens.
- Title/switch use the wording from Nitin's later message ("The office's ontology", Ontology / Process map / Business glossary), not the artboard's.
