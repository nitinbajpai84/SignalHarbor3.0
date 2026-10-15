# 55. Data knowledge map

Part of: Intent Centre v2. Depends on: 05, 13, 14, 20, 27, 28, 30, 32, 33. Feeds: 12, 13, 19, 45, 48, and Build room 0 (gap analysis, `modules/m3_connect`).

## Purpose (three sentences)

After every signed charter, signed gap report, signed blueprint, release and scan run, the company map learns where each data point lives: which system or file holds it, which measure it feeds, which process produces it and who owns it. Anyone in the company can open one connected picture of the organisation and follow any data point upstream to the process that makes it and downstream to the measure and release that use it. The gap analysis reads the same map to choose which systems to connect to, then writes back whether what people said is available really is, and whether what they said is missing is in fact somewhere else.

## Who uses it and when (role, moment, trigger)

| Role (Ardmore demo) | Moment | Trigger |
|---|---|---|
| Katie, analyst | Build room 0, before connecting | Opens the gap analysis from a build-ready charter; the "Systems to connect, from the map" panel lists them |
| Harvey, source owner | After a scan run | Pulse line "One field you own was found in another system"; confirms or rejects on the node page |
| Janet, organiser | After her charter is signed | Pulse line "What changed in the map"; opens the Map |
| Daniel, sponsor | Any time | Opens a measure on the Map and asks "where does this come from" |
| Aaron, participant | Any time | Browses the Map; sees only what his viewer rule allows |
| Grace, approver | Before signing a blueprint or release | Opens the lineage of a measure to see every field and system behind it |
| Super admin | Never | Has no route to the map (rule below) |

## Entry points (every route, link, Pulse line, button that leads here)

- Tab bar "Map" (existing, `ui/src/pages/GraphPage.tsx` L134-L137) to `/centre/intent/graph`.
- Pulse line "What changed in the map" (new, kind `inform`, written by Nira after each update moment), link to `/centre/intent/graph?view=fresh`.
- Pulse line "One field you own was found in another system" (new, kind `decision`, to the source owner only), link to `/centre/intent/map/<field node id>`.
- Node page button "Show lineage" (new) to `/centre/intent/graph?view=lineage&focus=<node id>`.
- Existing Map side card "Open definition" (`GraphPage.tsx` L239) to `/centre/intent/map/<node id>`.
- Build room 0 panel "Systems to connect, from the map" (new) at `/centre/build/gap-analysis?from=<id>`; each row links to the System node page.
- Intent screen `/centre/intent/<id>` record panel: link "See this on the map" (new) to `/centre/intent/map/intent:<id>` (file 20's Intent node).

## Screens, element by element

### Screen A. How my organisation connects (the existing Map page, re-staged)

Route: `/centre/intent/graph` (existing route, `ui/src/App.tsx` L130). New query keys `view` and `focus` (open question 1).

Layout at 1280: page frame title "How my organisation connects"; chip row; main card with the columns (existing `MapColumns`); right aside with the selected-thing card, "New this week", "Last map update" (new) and "What is kept out". The whole view keeps the existing five columns and adds a sixth, "Where it lives" (Field, File, Mart). The lineage view replaces the columns with one left-to-right line of columns for the focus node only: Process and step, System, File or Source, Field, Pipeline and Mart, Measure, Charter and Release (the earlier product's rule: never more than one topic's relationships on screen).

Layout at 390: no whole map (existing rule, `GraphPage.tsx` L158). Chips wrap to two rows. Lineage shows as a vertical list of cards, one per column, upstream at the top. "Last map update" moves below the map card. The sixth column is dropped in the wall view, as the existing phone view drops "owners".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Title "How my organisation connects" | heading | Existing copy (`ui/src/pages/graphCopy.ts` L5) | None | Everyone the map route allows (`route_permissions.yaml` L297) | Always shown |
| Subline | text | Things and links counts from the route's `summary` | None | As above | Existing empty copy (`graphCopy.ts` L61) |
| Chip "Whole map" | chip | Existing | Shows all columns | As above | Always shown |
| Chip "By wall" | chip | Existing | Existing | As above | Hidden when no walls |
| Chip "Trace" | chip | Existing | Existing | As above | Hint card when nothing selected |
| Chip "Gaps (n)" | chip | Existing holes count | Existing | As above | "Gaps (0)" |
| Chip "New this week (n)" | chip | Existing `new_this_week` count | Existing | As above | Chip hidden |
| Chip "Lineage" | chip (new) | Lineage of the selected thing | Sets `view=lineage&focus=<id>`; draws the lineage columns | As above | Disabled with hint "Pick a thing on the map first" |
| Chip "Checked by the scan (n)" | chip (new) | Count of `verified_by` edges the viewer sees | Keeps only nodes with a scan result; colours: available, missing, found elsewhere (labels, not colour alone) | As above | Chip hidden until the first scan run |
| Kind chips "Data", "Processes", "People", "Work" | chip group (new) | Data = Field, File, Source, System, Mart; Processes = Process, Step; People = Person, Team; Work = Intent, Charter, Gap report, Blueprint, Pipeline, Release | Toggles those kinds in the current view | As above | A kind with no nodes shows its chip greyed, "None yet" |
| Column "Where it lives" | list (new) | Field, File and Mart nodes, names only | Selects the node; side card shows its trail | As above; silhouettes per `read.py` L64-L65 | "Nothing recorded yet. The map learns where data lives when a charter is signed." |
| Lineage columns | list (new) | Upstream and downstream nodes of the focus node, each card with kind and owner | Card click selects it; double click opens its node page | As above; a silhouette card reads "A restricted field" with no owner | "Nothing is linked to this yet." |
| Scan result tag on a card | chip (new) | "Available", "Missing" or "Found in <system>" and the scan date | Opens the node page at "Where it lives" | As above; "Found in" names the system only if the viewer sees it, else "Found in another system" | No tag |
| Side card "Selected" | panel | Existing trail sentence, plus "Lives in <system>" for data kinds | "Open definition" (existing) to the node page | As above | Existing hint |
| Side card "Last map update" | panel + agent line (new) | Nira's one-line summary of the latest update, the moment ("Charter signed by Daniel"), the date | "See what changed" sets `view=fresh` | As above; the line is built from what this viewer sees | "The map has not been updated yet." |
| Side card "What is kept out" | panel | Existing copy (`graphCopy.ts` L54) | None | As above | Always shown |

### Screen B. Node page, "Where it lives" panel

Route: `/centre/intent/map/<node id>` (existing route, `App.tsx` L131; open question 1). The panel sits in the main column of `NodePage.tsx` between "Where it came from" (L149-L151) and the definition card (L153). Shown for Field, File, Source, System, Mart and Measure nodes.

Layout at 1280: main column card with rows; aside unchanged (versions, commits, who may see). Layout at 390: the card stacks above the definition; each row becomes label over value.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Card title "Where it lives" | heading | Fixed | None | Anyone who may open the node (404 otherwise, `versions.py` L189-L190) | Always shown |
| Row "Held in" | list | System nodes on `held_in` edges | Opens the system's node page | As above; a hidden system reads "A restricted system" | "Not recorded yet: no system named for this" |
| Row "Lands at" | list | `lands_at` targets with the arrival pattern from the pipeline contract | Opens the node | As above | "Not recorded yet" |
| Row "Written down in" | list | File, Charter, Gap report or Blueprint on `defined_in` edges | Opens the node page; a File opens its shelf entry | As above; a File whose document is restricted is not listed | "Not written down in any document on the shelves" |
| Row "Feeds" | list | Measures reached downstream (`fed_by`, `built_by`) | Opens the measure | As above | "Feeds no measure yet" |
| Row "Produced by" | list | Process and step on `produces` edges | Opens the process | As above | "No process named yet" |
| Row "Owners" | list | Business owner, data owner, source owner (ruling 11), from `owned_by` edges with their kind | Opens the person node | As above; a person whose only links are hidden is dropped (`read.py` L66-L67) | "Not available yet: owner not named" per kind |
| Row "Last checked" | text | Scan result, date, and the gap report it belongs to | "Open the gap report" to `/centre/build/gap-analysis?from=<intent id>` | As above | "Not checked yet. The first scan in the gap analysis checks it." |
| Button "Show lineage" | button | Fixed | To `/centre/intent/graph?view=lineage&focus=<id>` | As above | Always shown |
| Button "Confirm it is the same" | button (new) | Only on a "Found elsewhere" result | Writes the source owner's confirmation into `verify.json`; map rebuilds | The source owner of the claimed field only | Hidden |
| Button "Not the same thing" | button (new) | Only on a "Found elsewhere" result | Writes the rejection with a required reason; the result becomes "Missing" | The source owner only | Hidden |
| Existing buttons "Suggest a change", "Flag an ambiguity", "Ask Lens" | button | Existing (`NodePage.tsx` L128-L130) | Existing | Existing | Existing |

### Screen C. Build room 0 panel "Systems to connect, from the map"

Route: `/centre/build/gap-analysis?from=<id>` (ruling 10; `modules/m3_connect` screens as built). One new card at the top of the connect step.

Layout at 1280: full-width card, a table of systems. Layout at 390: one card per system, rows stacked.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Card title "Systems to connect, from the map" | heading | Fixed | None | Build team of the intent (33's `build_team`) | Always shown |
| North line | agent line | "The charter's measures need data from 3 systems. Two were named by people, one was found by the last scan." Counts from the lineage traversal | None | As above | "The map does not yet say where these measures' data lives. Ask the source owners." |
| System row | list | System name, measures it feeds (count), fields people said are there (count), source owner | Opens the system node page | As above; a restricted system is one row "A restricted system" with counts only, "Fewer than five" where below five | None |
| Chip "Said available / Said missing" | chip | Claim counts per system from the data sources map (28) | Filters the row's fields | As above | "No claims recorded" |
| Button "Use this list" | button | Fixed | Copies the systems into the existing connect step's request list (`modules/m3_connect/domain/intake.py` `source_plan`, L85-L122) | Katie and the build team | Disabled when the list is empty |
| Button "Run the scan" | button | Existing scan action of module 3 | Existing; on finish the map updates (moment 5) | Existing | Existing |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Daniel signs the charter (32). The charter store writes its outcome; the update hook rebuilds the map now (not on next read) and records versions. Nira writes the "What changed in the map" line for everyone who may see the map.
2. Janet opens Pulse, reads "The map gained 4 fields and 2 systems from the charter signed by Daniel", clicks it, and lands on the Map with "New this week" on.
3. Janet clicks the field "called_to_date". The side card says "Lives in the capital calls sheet; feeds Uncalled commitment; owned by Harvey". She clicks "Open definition".
4. On the node page the "Where it lives" panel shows Held in, Feeds, Produced by, Owners and "Not checked yet". She clicks "Show lineage" and sees the line from the capital call process to the measure. She leaves.
5. Katie opens the gap analysis from the build-ready charter. Between her arrival and the panel drawing, North walks the map from each charter measure along `fed_by`, `uses` and `held_in` to the systems and drafts the North line.
6. Katie reads the list and clicks "Use this list". The systems join the existing request list. She clicks "Run the scan".
7. The scan (module 3, as built) profiles the files it received. For each claim from the data sources map (28) and catalogue, it matches the profiled columns to the claimed fields with the existing matcher. It writes `verify.json`: available, missing, or found elsewhere with the system where it was found.
8. The map rebuilds (moment 5); each checked node gains a `verified_by` edge to the gap report. Nira writes the Pulse line, and a decision line to Harvey for each "found elsewhere" field he owns.
9. Harvey opens his line, reads "Said missing; found in the custodian portal as `uncalled_amt`", and clicks "Confirm it is the same". The confirmation is written; the map rebuilds; the tag reads "Found in custodian portal, confirmed by Harvey".
10. Grace signs the gap report (33). The map adds the Gap report node with `led_to` from the charter and keeps the scan edges. Later the blueprint and the release each update the map the same way. Each person leaves from the page they opened.

## States and transitions (table: state, who moves it, to what, what is written)

| State | Who moves it | To what | What is written |
|---|---|---|---|
| Claim "said available" or "said missing" | a person confirming the data sources map (28) or catalogue (30) | Unchecked | Existing records; a `claimed` value on the field's source row |
| Unchecked | the scan run (started by Katie) | Available, Missing or Found elsewhere | `verify.json` row; on rebuild a `verified_by` edge |
| Found elsewhere | Harvey, source owner | Confirmed found | `verify.json` row `confirmed_by`, `confirmed_at` |
| Found elsewhere | Harvey, source owner | Missing | `verify.json` row `rejected_by`, `reason` |
| Any result | a later scan run | A new result | New `verify.json` row (older rows kept); new version line on the node |
| Map version n | an update moment | Map version n+1 | `graph/company.json` rewritten; `graph/versions.json` rows appended; `graph/updates.json` row |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Read or written | Mark |
|---|---|---|---|
| `graph/company.json` via `sh_platform/graph/build.py` `rebuild` L113-L137 | nodes `{id, type, label, provenance, restricted_to, restricted_bound, room}`, edges `{from, to, type, provenance}` plus new edge props `result`, `found_in`, `owner_kind` | Written by rebuild only | Existing file; new node types and edges |
| `graph/versions.json` via `versions.py` `append_version` L40-L49, `record_versions_from_build` L82-L107 | `{node id: [{v, what, by, at, ref}]}`; `ref` set to the update moment's record | Appended | Existing |
| `graph/updates.json` | `[{id, moment: charter_signed\|gap_report_signed\|blueprint_signed\|release\|scan_run, ref, by, at, added: {type: count}, changed, removed, line}]` | Written at each moment; read by Pulse and the Map side card | New |
| `intents/m3_connect/assessments/<aid>/verify.json` | `{rows: [{node, claimed: available\|missing\|unknown, claimed_by, result: available\|missing\|found_elsewhere, found_in: system id\|null, column, confidence, scanned_at, confirmed_by, confirmed_at, rejected_by, reason}]}` | Written by the scan step and the two owner buttons | New |
| Profile systems and people (`sh_platform/profile/store.py` `raw`; build.py `_profile` L163-L173, `_people` L150-L160) | systems, owner, people, team | Read | Existing |
| Baseline catalogue sources, tables, fields (build.py `_baseline` L271-L290) | Source ID, Where it lands or lives, Data owner, Field name, Feeds KPI | Read | Existing |
| `intents/m2_baseline/<baseline_id>/data_sources.json` (28) | `system_ref`, `source_owner`, `business_owner`, `used_in.steps` | Read for `held_in`, `owned_by`, `produces` | New (owned by 28) |
| `intents/<id>/processes.json` (27) | processes, steps, owner | Read for Process and Step and `produces`, `consumes` | New (owned by 27) |
| Charter outcome `intents/m1_intent/outcomes/<id>.json` | signatures, signed_at, problems | Read for the Charter node | Existing |
| `context/agent_docs/<agent>/<doc>.json` (`sh_platform/context_docs/store.py` L40-L43) | id, title, visibility | Read for File nodes (title only, never text) | Existing |
| `build/blueprint.json`, `build/pipelines/*.json`, `build/prove.json` (build_nodes.py L63-L125) | lineage `mart`, `measure`, `source`; pipeline `lands_at`, `marts`, `owner`; release | Read for Mart, `lands_at`, `built_by` | Existing |
| Module 3 intake profiles `intake/<source_id>/profile.json` (`intake.py` `scan_state` L310-L319) | columns, types | Read by the scan step | Existing |
| `GET /api/company/graph?view=lineage&focus=<id>` (`sh_platform/graph/api.py` L104-L120, VIEWS L23) | as the map view, upstream and downstream of the focus | Read | Existing route, new view |
| `GET /api/company/graph/node/{id}` (`versions.py` L180-L261) | new key `where: {held_in, lands_at, written_in, feeds, produced_by, owners, last_checked}` | Read | Existing route, new key |
| `POST /api/modules/m3_connect/assessments/{aid}/verify/{row}/confirm` and `.../reject` | `reason` on reject | Written | New (open question 2) |

## Fields this feature adds to the intent record

- `refs.map_update_ids: [update id]`: the `graph/updates.json` rows this intent's signatures caused. Counts on screen are read from `updates.json`, never stored here.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** (Build room 0): on opening the gap analysis, traverses the map from the charter's measures to systems and drafts the "Systems to connect" list and its line. Katie acts: "Use this list" and "Run the scan".
- **Lens**: drafts nothing new on the map. Lens already drafts the data sources map (28) and technical definitions (30); people confirm them, and those confirmations are the claims the scan checks. "Ask Lens" on the node page answers "where does this live" by traversal first (COMPANY-GRAPH-SPEC section 5).
- **Nira**: after each update moment, writes one "What changed in the map" line per viewer from the `updates.json` row, using the smallest model tier (`TIER_ORDER[0]` in `tools/route_task.py` L30) through the egress gateway with labels tokenised; if the call fails, a fixed template line from the counts. Writes the decision line to a source owner for each "found elsewhere" field. Harvey acts: confirm or reject.
- No agent writes the map. The map is rebuilt from records; agents never sign, confirm or reject.

## Rules (visibility, time box, who may do what)

- The map is a projection (COMPANY-GRAPH-SPEC section 1). Nothing is edited on it. A scan result is a record in `verify.json`; the `verified_by` edge is drawn from it on rebuild.
- One graph: `graph/company.json`, versions in `graph/versions.json`. No second store.
- Update moments, each a forced rebuild plus versions plus one `updates.json` row: signed charter (32), signed gap report (Build room 0, 33), signed blueprint, signed release, scan run in Moment of truth. Other record writes keep the existing lazy rebuild (`hooks.py` `mark_dirty` L20-L27).
- Viewer rule: `sh_platform/profile/view.py` through `graph/read.py` `graph_for` L29-L45. Restricted and sealed material never shows its label, owner, system or file; a sealed wall card produces no data node. Any count over people or fields below five reads "Fewer than five" (ruling 8).
- File nodes carry the document title only, and only for documents whose shelf visibility lets the viewer see them; the text never enters the map.
- The super admin never sees the map, its counts or its Pulse lines; `/centre/control/intents` shows none of it.
- Only the named source owner of a field may confirm or reject "found elsewhere".
- The scan checks names and types of columns, never row values; it reads files already in the company plane and nothing leaves (data locality rule).
- No time box of its own: the map follows the time boxes of the intents that update it.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Record | Empty |
|---|---|---|
| Things and links on the map | `graph/company.json` via `summary` (`read.py` L73-L85) | Existing empty copy |
| Things by kind (Data, Processes, People, Work) | `graph/company.json` node types, viewer-gated | "None yet" |
| Checked by the scan, and per result | `verified_by` edges, from `verify.json` | Chip hidden |
| Claims proven wrong (said available, missing; said missing, found) | `verify.json` `claimed` against `result` | "Not available yet: no scan run" |
| Fields with no system named | Field nodes with no `held_in` edge | "0" shown only when fields exist |
| Data points with no owner per owner kind | Field and Source nodes with no `owned_by` of that kind | As above |
| Map updates this week | `graph/updates.json` rows under seven days | "The map has not been updated yet." |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: in this repo `graft ask "company graph nodes edges build" --source`, `graft skeleton sh_platform/graph/build.py`, `graft ask "scan run findings source connect gap report signed"`; in the earlier repo `graft ask "data map lineage catalogue ontology source field" --source`; read `docs/reuse-inventory.md`.

This repo:

| File and lines | What it is | Use |
|---|---|---|
| `docs/specs/COMPANY-GRAPH-SPEC.md` sections 1 to 5 | Projection rule, node and edge vocabulary, trace and impact views | Reused as the frame; this file extends its vocabulary |
| `sh_platform/graph/models.py` L9-L31, L48-L85 | `NODE_TYPES`, `EDGE_TYPES` endpoint rules, `Graph.node` and `edge` | Reshaped: new types and edges registered the way `build_nodes._register` does; edge needs props |
| `sh_platform/graph/build.py` L113-L137, L163-L173, L239-L318, L321-L366 | `rebuild`, systems, baseline sources, tables, fields, assessment | Reused; one new builder call after `add_build_nodes` |
| `sh_platform/graph/build_nodes.py` L19-L31, L63-L125 | Registering types without editing models; Blueprint, Pipeline, Release | Copied pattern for a new `data_nodes.py`; Mart from the same lineage |
| `sh_platform/graph/hooks.py` L20-L73 | Dirty flag and rebuild | Reused; update moments call the rebuild directly |
| `sh_platform/graph/versions.py` L40-L107, L180-L261 | Versions, node page route | Reused; node route gains `where` |
| `sh_platform/graph/read.py` L18-L85 | Viewer gate, silhouettes, holes | Reused unchanged |
| `sh_platform/graph/api.py` L23-L36, L48-L120 | Map, trace, holes, new this week | Reshaped: `lineage` view is `_trace` in both directions |
| `sh_platform/graph/register.py` L81-L87 | Measure to source lineage from the blueprint | Reused for `fed_by` to Mart |
| `ui/src/pages/GraphPage.tsx` L54-L77, L113-L247 | Map page, `reach` up and down, chips, side cards | Reshaped: new chips, sixth column, lineage view |
| `ui/src/pages/NodePage.tsx` L51-L192 | Node page | Reshaped: one new card and two owner buttons |
| `modules/m3_connect/domain/intake_match.py` L70-L86 | `match_columns` columns to fields with confidence | Reused for the claim check; "found elsewhere" runs it against every connected system |
| `modules/m3_connect/domain/intake.py` L85-L122, L310-L319 | Source plan, scan state | Reused for "Use this list" and the scan |
| `sh_platform/profile/view.py` L60-L109 | Viewer rules | Reused unchanged |
| `sh_platform/pulse/lines.py` L71-L73, L206-L216 | Line shape, owned-node lines | Reused for both new lines |

Earlier repo (`<earlier repo>`):

| File and lines | What it is | Use |
|---|---|---|
| `sh_platform/context/models.py` L14-L35 | Node and relationship vocabulary incl. `Table`, `Column`, `Document`, `LANDS_IN`, `HAS_COLUMN`, `DERIVED_FROM`, `PRODUCED`, `VALIDATED` | Reshaped: the idea of `LANDS_IN` and `VALIDATED` became `lands_at` and `verified_by`; types named by the settled list |
| `sh_platform/context/store.py` L178-L185 | `lineage(kpi)`: KPI to definition to table to column, depth 3 | Not copied (DuckDB store); its walk is what the lineage view does over JSON |
| `sh_platform/context/projectors/contracts.py` L82-L95, L101-L182 | Source `LANDS_IN`, `HAS_COLUMN`, silver `DERIVED_FROM` from contracts | Reshaped into the pipeline-contract reads above |
| `sh_platform/context/projectors/warehouse_meta.py` L1-L22 | Run and DQ results as metadata, no rows | Not used: no warehouse runs here yet; its "metadata only" rule is kept |
| `webapp/backend/routers/context_layer.py` L53-L93 | Shelf, topic, trace, map reads | Not copied: this repo already ported the views (`api.py`) |
| `docs/signal-harbor/prototype/js/screens/knowledge-graph.js` L277-L334 | Trace screen: one path, columns, the rest faint | Reshaped into the lineage view's layout and empty copy |
| `emitters/column_matcher.py` L98-L244 | Earlier column matcher | Not used: already ported as `intake_match.py` |
| `dbt/models/` | Empty (`.gitkeep` only) | Nothing to reuse |
| `sh_data/` | Workspace data folders and registries | Not used: holds data, not code |

Genuinely new: File, Charter, Gap report and Mart node types; `produces`, `consumes`, `held_in`, `lands_at`, `defined_in`, `verified_by` edges; `verify.json`; `updates.json`; the "Where it lives" card; the Build room 0 panel.

New vocabulary, all inside the existing graph:

| Kind on screen | Graph type | From | Mark |
|---|---|---|---|
| measure, definition, source, field, system, process, process step, person, team | Measure, Term, Source, Field, System, Process, Step, Person, Team | as today | Existing |
| blueprint, pipeline, release | Blueprint, Pipeline, Release | `build_nodes.py` | Existing |
| intent | Intent | file 20 (`intent_nodes.py`, not built) | New (20) |
| file, charter, gap report, mart | File, Charter, GapReport, Mart | shelves, charter outcome, signed assessment, blueprint lineage | New |

| Edge | From | To | Mark |
|---|---|---|---|
| `held_in` | Field, Source, File | System | New |
| `lands_at` | Source, Pipeline | System | New |
| `produces`, `consumes` | Process, Step (`consumes` also Pipeline) | Field, Source, File | New |
| `defined_in` | Measure, Term, Field | File, Charter, GapReport, Blueprint | New |
| `verified_by` | Field, Source | GapReport, props `result`, `found_in` | New |
| `owned_by` | adds Field, File, Mart; prop `owner_kind` | Person | Existing, widened |
| `led_to`, `came_from` | Intent, Charter, GapReport, Blueprint, Release in work order | the next or previous | Existing in 20, widened |
| `built_by`, `measured_by`, `moves`, `designed_by`, `tested_by`, `released_by`, `fed_by`, `uses`, `step_of` | as today; `built_by` adds Mart to Pipeline; `fed_by` adds Field and Mart as targets | | Existing |

## Not in this feature

- Editing the map directly, or a graph database.
- Reading row values or figures in the scan; only column names and types.
- Connecting to systems that are not already delivering files into the company plane (connectors stay in module 3).
- Export of the map to an outside catalogue.
- Any super admin view.

## Open questions

1. `/centre/intent/graph`, `/centre/intent/map/<id>` and the `view` and `focus` query keys are not in ruling 1 or 18. They are existing routes; confirm they stay, or move under `/centre/intent/...` views.
2. The confirm and reject routes sit under `/api/modules/m3_connect/...`, not `/api/intents/...` (ruling 1), because the scan belongs to module 3. Confirm.
3. Ruling "restricted never shown" against today's silhouettes (`read.py` L64-L65 shows "A restricted field"). Keep silhouettes, or drop restricted data nodes entirely?
4. `produces` (Process to Field) overlaps the existing `produced_by` (Source to Process). Keep both, or retire `produced_by`?
5. Is a landing area (`lands_at: landing`, `inbox/bank`) a System node, or a property of the Source?
6. Charter node against the existing "Charter signed" Decision node (`build.py` L227-L236): replace, or keep both?
7. Edges are keyed by (from, to, type); one person who is both data and source owner needs `owner_kind` as a list. Confirm the shape.
8. Which match confidence counts as "available" or "found elsewhere"? `match_columns` drops below level 2; whether "medium" is enough is not given.
9. Must a "found elsewhere" result wait for the source owner, or count at once? This file waits for Harvey.
10. Which document shelves give File nodes: only agent shelves (`context/agent_docs`), or also module 3 uploads?
11. Version `ref` today comes from node provenance (`versions.py` L100); an update moment needs it to be the moment's record. Confirm the change.
12. Does Nira's Pulse line go to everyone who may see the map, or only to people tagged to the intent's areas (05)?
13. How long are older `verify.json` rows kept, and does the Map show only the newest result?
