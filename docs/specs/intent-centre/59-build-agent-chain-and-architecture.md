# 59. Build centre agent chain and the company architecture record

Part of: Intent Centre v2 (the return cycle, `docs/plan/CYCLE-PLAN.md` section 1, stage Build). Depends on: 33 (build-ready check and hand-off), 34 (who does what, the charter roles block), 55 (data knowledge map), 57 (hypothesis record), `docs/specs/BUILD-CENTRE-SPEC.md` (rooms, blueprint, contracts, Prover, Watcher), `docs/plan/SHAPES.md` sections 2 to 6 and 10. Feeds: 55 (new map node kind Component), 56 and 57 (the Watcher's signals carry the change that built the thing), 58 (Proving starts from the signed release), 60 (the Architect drafts context cards from the change note), 13 (Pulse lines), 19 (counters).

## Purpose (three sentences)

An Initiative handed to Build (33) today meets four agents (Architect, Builder, Prover, Watcher) and two signatures (blueprint, release), but nobody owns the company's architecture as a whole, nothing tells the person who builds what exactly is changing and why, and the hand-overs between people are not visible. This feature makes Build one chain with a named person at every gate: the Architect agent places each new component in a company-wide architecture record (three views: data, infrastructure, enterprise solution) and drafts a change note and regenerated diagrams; the head of department approves; the data engineer builds against the change note; the tester verifies against the hypothesis and the catalogue; the ops manager accepts the running service and the Watcher feeds the radar. Agents draft, people sign: every step is drafted by an agent and closed only by the named person's signature, and the architecture record and its diagrams are regenerated on every signed blueprint and every signed release so the knowledge map always shows what the company runs today and which Initiative changed it.

## Who uses it and when (role, moment, trigger)

The five steps of the chain, each with the agent that drafts and the person who acts. Person slots come from the charter roles block (34, SHAPES section 12) plus one new slot, `head_of_department` (see Fields).

| Step | Agent drafts (v1 name kept) | Person acts (charter role) | Ardmore example | Moment and trigger |
|---|---|---|---|---|
| 1. Architect | Architect | Architect (`roles.architect`) reviews and sends for approval | Aaron | Hand-off written by 33 ("Hand to Build") and gap report signed in room 0; Pulse line "The Architect drafted the change for `<T>`. Check it." |
| 2. Approval | None (North checks the note is complete) | Head of department (`roles.head_of_department`) approves or sends back; IT signs the infrastructure part when that view changes | Grace | Architect presses "Send for approval"; Pulse line "Approve the design for `<T>`" |
| 3. Data engineer | Builder (code from contracts, existing) | Developer (`roles.developer`) | Katie | Approval signed; Pulse line "Build `<T>` from change note C-0003" |
| 4. Tester | Prover (existing) | Tester (`roles.tester`; fallback sponsor or company admin, existing in `uat.py`) | Mei Ling | Developer presses "Built, ready to test"; Pulse line "Test `<T>`" |
| 5. Ops manager | Watcher (existing) | Ops (`roles.ops`) | Harvey | Release signed by the sponsor (Daniel, existing `prove.py` release); Pulse line "Take over `<T>` from today" |

Other readers:

| Role | Moment | Trigger |
|---|---|---|
| Sponsor (Daniel) | Between steps 4 and 5 | Signs the release (existing, unchanged); reads the chain strip on Build home |
| Organiser (Janet) | Any time after hand-off | Follows "See the build" from the closed Initiative (58's Proving panel links here too) |
| Anyone who may open the map (Aaron, participants) | Any time | Opens the architecture record or a Component node on the map |
| Company admin | Setting who signs the infrastructure part | Admin Defaults, existing `admin` defaults page (Open question 4) |
| Super admin | Never | No route (control plane holds no company data) |

## Entry points (every route, link, Pulse line, button that leads here)

- Build centre home `/centre/build` (existing `ui/src/pages/BuildCentre.tsx`): new panel "The chain" with one row per open change note; the row opens Screen C.
- 33's "Hand to Build" lands on `/centre/build/gap-analysis?from=<id>` (unchanged). When the gap report is signed, the room 0 banner gains the link "See the change the Architect drafted" to Screen C.
- Blueprint page `/centre/build/blueprint` (existing): the chip "Draw the diagram" (today links to `/centre/intent/graph`, `BlueprintPage.tsx` L125) now opens Screen B at the data view; the new hand-over strip (Screen D) links to Screen C.
- Pipelines `/centre/build/pipelines`, Prove `/centre/build/prove`, Ops `/centre/build/ops` (existing): hand-over strip (Screen D) at the top of each.
- New tab "Architecture" in the Build centre tab row, to `/centre/build/architecture`.
- Map (55) `/centre/intent/graph`: kind chip "Work" gains Component; a Component node page `/centre/intent/map/component:<id>` has the button "Open in the architecture record".
- Pulse lines (13, written by Nira), one per gate, kind `signature` or `request`: "The Architect drafted the change for `<T>`. Check it." (architect), "Approve the design for `<T>`" (head of department), "Build `<T>` from change note `<C>`" (developer), "Test `<T>`" (tester), "Take over `<T>` from today" (ops), "`<T>` was sent back at `<step>`: `<reason>`" (the person one step earlier). Each href is Screen C with `?step=<n>`.
- Pulse line to everyone who may open the map, kind `brief`: "The architecture changed: `<n>` components added by `<T>`" after each regeneration, href Screen B `?v=<n>&focus=change`.
- The closed Initiative's stage view `/centre/intent/<id>`: record panel link "See the build" to Screen C for the Initiative's change note (from `links.build`).

## Screens, element by element

Four screens. A and D reshape existing pages; B and C are new pages in the Build centre. All use `PageFrame`, `Panel`, `SideCard`, `Signature`, `Pill`, `Chip` and `ScreenState` as the existing Build pages do (`ui/src/pages/BlueprintPage.tsx`, `OpsPage.tsx`).

### Screen A. Build centre home, panel "The chain"

Route: `/centre/build` (existing `BuildCentre.tsx`, `GET /api/company/build/home`). Layout at 1280: the existing three-room panel stays; "The chain" sits above it, full width, one row per change note not yet live, each row a horizontal strip of five steps (Architect, Approval, Data engineer, Tester, Ops manager) with the person's name under each step and the current step highlighted. At 390: each change note is one card; the five steps become a vertical list; only the current step is expanded, the others show name and a state pill.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Panel title "The chain" | panel | "Every change from an Initiative, step by step. Agents draft; the named person signs." | None | Build centre users (route gate `centre="build"`, `App.tsx` L137) | Never empty |
| Change row title | link | "C-0003 Valuation chase protocol" (change note `id`, intent `title`) | Opens Screen C | As above | Panel shows "Nothing is being built. A change starts when an Initiative is handed to Build." |
| Step cell (x5) | chip | Step name, person name from the charter roles block, state pill: Waiting, Drafting, With `<name>`, Signed `<date>`, Sent back | Opens Screen C at `?step=<n>` | As above | Person "Not named yet" (pill amber); hover "Name them in the charter: Who does what" links to 34 |
| Days at this step | label | "With Grace for 2 working days" from the step's `opened_at` to today, company time zone | None | As above | "Not started" |
| Sent back marker | chip | "Sent back by Mei Ling: K12 does not match for 2026-08" (latest `returns[]` row) | Opens Screen C at the step it went back to | As above | Hidden |
| Live changes count | label | "Live: 4 changes" (count of change notes in state `live`) | Opens Screen B with `?focus=change` | As above | "No change is live yet." |

### Screen B. Company architecture record

Route: `/centre/build/architecture?view=data|infrastructure|enterprise&v=<n>&focus=<component id>|change` (new page `ui/src/pages/ArchitecturePage.tsx`; route is Open question 1). Default view `data`, default `v` the newest regenerated version. Layout at 1280: page frame title "How the company is built"; view chips; main card the diagram drawn from the stored Archify spec; under it the component table; right aside: "Selected", "This version", "What changed", "Owners missing". At 390: no diagram (the same rule as the map, `GraphPage.tsx` L158); the component table becomes cards grouped by kind; the aside moves below; a line "Open the diagram on a larger screen" stays.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Title "How the company is built" | heading | Fixed | None | Everyone the map route allows (`RoleGate centre="map"`, `App.tsx` L156) | Always shown |
| Subline | label | "Version 7, regenerated when Daniel signed the release on 3 Oct 2026" from `build/architecture/record.json` `version` and `regenerated` | None | As above | "No architecture recorded yet. The Architect drafts it when the first blueprint is signed." |
| View chips "Data", "Infrastructure", "Enterprise solution" | chip group | One chip per view with its component count | Sets `view`; redraws | As above | A view with no components shows "None yet" greyed |
| Chip "This change only" | chip | Present when `focus=change` | Dims every component not added or changed by the selected change | As above | Hidden when no change is selected |
| Version picker | field (select) | "Version 7 (current)", older versions with their moment and date | Sets `v`; reads `build/architecture/diagrams/<view>.v<n>.json` | As above | Only "Version 1" |
| Diagram | panel (SVG) | The Archify spec of this view and version: components at their `pos`, connections with labels, the change's components outlined | Click a component: selects it, scrolls the table to its row and fills "Selected" | As above; a restricted component (one that serves a measure on a restricted access list) is a box labelled "Restricted" with no name | "Nothing drawn yet for this view." |
| Button "Download the diagram" | button | Fixed | Downloads `build/architecture/diagrams/<view>.v<n>.html` when it exists (Open question 2) | Architect role, head of department, company admin | Hidden when no HTML was rendered |
| Component table | list | Columns: name, kind, view, owner, version, state (proposed, approved, built, tested, live, retired), "Changed by" (Initiative title and change id) | Row click selects; "Changed by" opens Screen C for that change | As above; restricted rows read "Restricted" in the name column, as `BlueprintPage.tsx` `rows()` does | "No components yet." |
| Side card "Selected" | panel | Name, plain-words description (with its mark), owner, interfaces in and out (each with kind and contract link), versions list | "Open on the map" opens `/centre/intent/map/component:<id>`; an interface's contract link opens `/centre/build/pipelines` | As above | "Pick a component to see its interfaces and history." |
| Field "Owner" | field (people picker) | In "Selected": the component's owner from the company people list | Pick saves as stated with by and at; North rechecks the step 2 gate | Architect role, head of department | "No owner yet" |
| Button "Edit description" | button | In "Selected" | Inline text field; saves as stated with by and at; a later draft never overwrites it (CLAUDE.md rule 7) | The component's owner, the architect role | Hidden for others |
| Side card "This version" | panel | Moment that produced it (signed blueprint vN or signed release), by, at, counts added, changed, retired, from `regenerated` | "Compare with the previous version" sets `focus=change` with the previous `v` | As above | "First version." |
| Side card "What changed" | list | One line per change note in this version: "C-0003 added 3 components, changed 1 (Valuation chase protocol)" | Line opens Screen C | As above | "Nothing changed since the previous version." |
| Side card "Owners missing" | agent line (Architect) | "2 components have no owner: silver.custodian_statements, the read-only copy" | Row link selects it; button "Ask the head of department" writes a Pulse request line | Architect role, head of department, company admin | Hidden when every component has an owner |

### Screen C. Change note and the chain for one change

Route: `/centre/build/change/<change_id>?step=1..5` (new page `ui/src/pages/ChangeNotePage.tsx`; Open question 1). Layout at 1280: header (change id, Initiative title linking to `/centre/intent/<id>`, state pill); the five-step strip as in Screen A; two columns. Left, 8 of 12: the change note sections in order (Why, What changes, Decision and alternatives, Build steps, What to test, Run book additions, Risks). Right, 4 of 12: the current step's action card, "Signatures", "Sent back". At 390: one column; the action card is sticky at the bottom; each section folds under its heading, "Why" and "What changes" open by default.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Header | label | "C-0003 · Valuation chase protocol · With Katie, data engineer" | Title opens the Initiative | Build centre users; the Initiative's participants read only | Not applicable |
| Step strip | chip group | Five steps, person, state | Sets `?step=` and scrolls to that step's section | As above | "Not named yet" on a step without a person |
| Section "Why" | panel | The hypothesis frozen at charter signature (57): belief, measure, baseline, target, review date; line "Handed to Build by Janet on `<date>`" from `build_handoff` (33) | Measure name opens its node page | As above | "Not available yet: this Initiative has no hypothesis. The change is checked against the catalogue only." |
| Section "What changes" | list | Components added, changed, retired, grouped by view; old and new values for a change; interfaces added | A component opens Screen B with `focus=<id>`; link "See the diagrams" opens Screen B `focus=change` | As above | "The Architect found nothing to add: every measure is adopted from existing tables." (estate scan path "adopt") |
| Section "Decision and alternatives" | panel | Per placement: at least two options, the choice, why, and what follows | None | As above | "Not drafted yet." |
| Section "Build steps" | list | Per step: pipeline contract to write or change (`build/pipelines/<source>.json`), marts to build (`gold.<code>`), rules to add (blueprint `rules[]`), each Done or Not done, read from the contracts and the run log | Contract line opens `/centre/build/pipelines`; Done is read, never ticked by hand | As above | "No build steps: nothing to build for this change." |
| Section "What to test" | list | Per measure: catalogue check (reported figure per period, `build/prove.json`), hypothesis check (the baseline reproduces from gold for the baseline period), rules to pass | Measure opens `/centre/build/prove` | As above | "Nothing to test yet: the data engineer has not marked the build done." |
| Section "Run book additions" | list | Per new pipeline: expected arrival, SLA, source owner, who is told, drafted from the contract | Opens `/centre/build/ops` run book | As above | "No run book change." |
| Section "Risks" | list | Accepted risks from the signed gap report (m3_connect plan outcome) that touch this change | None | As above | "No accepted risk touches this change." |
| Edit pencil on a draft line | button | On guessed lines only | Inline edit, saved as stated with by and at | Architect role, at step 1 | Hidden once approved (signed content is read-only) |
| Action card, step 1 | panel + buttons | "The Architect drafted this change from blueprint v3 and the signed gap report." Buttons "Send for approval" and "Ask the Architect to redraft" (required note) | "Send for approval" moves to step 2 and writes the Pulse line to the head of department; redraft redrafts the guessed lines only | Architect role | "The Architect is drafting. This follows the signed gap report." |
| Action card, step 2 | panel + buttons | North's completeness line ("Every component has an owner; every measure has a test"), the blueprint version signed with it; buttons "Approve the design" and "Send back" (required reason); a second row "IT signs the infrastructure part" when the infrastructure view changes | "Approve the design" signs the change note and the blueprint version together (one act, the existing blueprint sign route reshaped); "Send back" returns to step 1 | Head of department; the IT person for the infrastructure row | Disabled with North's first gap named ("2 components have no owner") |
| Action card, step 3 | panel + buttons | "3 of 4 build steps done, read from the run log"; buttons "Built, ready to test" and "Send back to the Architect" (required reason) | "Built, ready to test" is enabled only when every build step is done and the last run of each new pipeline is `ok`; moves to step 4 | Developer role | Disabled with the first missing step named ("The custodian statements pipeline has not run yet") |
| Action card, step 4 | panel + buttons | Per measure: catalogue result and hypothesis check; existing "Sign UAT" and "Send back with a note" (`ProvePage.tsx` L106-L107) | All measures signed moves to "Waiting for release"; a send-back returns to step 3 with the note | Tester role (fallback sponsor or company admin, as `uat.py` today) | "Nothing to test yet." |
| Release row | label + link | "Release signed by Daniel on `<date>`" from `build/prove.json` `release` | Link "Open the release" opens `/centre/build/prove` | Everyone on the page; only the sponsor signs (existing) | "Waiting for the sponsor to sign the release" |
| Action card, step 5 | panel + buttons | Run book additions, who is told, the Watcher's first run result; buttons "I run this from today" and "Not ready to take over" (required reason) | "I run this from today" moves the change to `live`; from then the Watcher tells the ops person, not the developer, about these pipelines; "Not ready" writes a Pulse line to the developer and sponsor | Ops role | "Waiting for the release." |
| Button "Stop this change" | button | Footer of the page, with a required reason | Moves the change to `stopped` (States table); signed records stay | The Initiative's organiser only | Hidden once `live` or `stopped` |
| Side card "Signatures" | list | Each signature: step, name, role, date | None | As above | "Nobody has signed yet." |
| Side card "Sent back" | list | Each return: from step, to step, by, reason, date | None | As above | Hidden when none |

### Screen D. Hand-over strip on the four existing Build pages

Route: top of `/centre/build/blueprint`, `/centre/build/pipelines`, `/centre/build/prove`, `/centre/build/ops` (existing pages; reshaped, not rebuilt). Layout at 1280: one line under the page title. At 390: the line wraps; the link sits under it, full width.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Strip text | label | "Step 3 of 5, data engineer: Katie. Building against change note C-0003." | None | Build centre users | Hidden when no change note is open |
| Link "Open the change note" | link | Fixed | Opens Screen C at the step | As above | Hidden with the strip |
| Count chip | chip | "2 changes open" when more than one change note is open | Opens Screen A | As above | Hidden when one or none |
| Chip "Draw the diagram" (existing, `BlueprintPage.tsx` L125) | chip | Fixed | Now opens Screen B at the data view (today it opens the map) | As today | Always shown |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

Example: the Initiative "Valuation chase protocol" (Janet organiser, Daniel sponsor) changes how stale private fund valuations are measured (K12). Charter roles (34): Aaron architect, Grace head of department, Katie developer, Mei Ling tester, Harvey ops.

1. Janet presses "Hand to Build" (33). Build opens at room 0, the gap analysis, as built. Katie runs it and Daniel signs the gap report (existing m3_connect plan sign).
2. Between that signature and anyone's next step, the Architect (agent) drafts: blueprint v3 from the existing `blueprint_draft.draft`; then it reads the current architecture record and places each new or changed thing as a component in one or more views (data: `bronze.custodian_statements`, `silver.custodian_statements`, `gold.k12`; infrastructure: none changed; enterprise solution: the "Custodian statements" source system feeds the "Committee pack" consumer). It writes change note C-0003 with Why (the hypothesis, 57), What changes, Decision and alternatives, Build steps, What to test, Run book additions and Risks, every line marked guessed with its source. It regenerates a draft diagram per changed view. Nira writes Aaron's Pulse line.
3. Aaron opens Screen C at step 1. He edits one decision line ("Keep custodian statements in the main warehouse file; they are not restricted") and presses "Send for approval". The line is now stated, by Aaron.
4. North (agent) checks completeness: every component has an owner, every measure in the change has a test line, every build step names a contract. It finds `silver.custodian_statements` has no owner and writes "1 component has no owner" on the action card. Nira writes Grace's line "Approve the design for Valuation chase protocol".
5. Grace opens Screen C at step 2. The button "Approve the design" is disabled with North's gap. She sets the owner on Screen B ("Selected", owner field, Harvey) and returns. North rechecks; the button enables. Grace presses "Approve the design". Blueprint v3 and C-0003 are signed together; both are read-only.
6. On that signature the server regenerates the architecture record (version 7) and the three view diagrams, writes the map update moment (55's `record_moment`, moment `blueprint_signed`), and the Architect drafts the context card lines for `gold.k12` (60). Nira writes Katie's line "Build Valuation chase protocol from change note C-0003" and the map line to everyone.
7. Katie opens Screen C at step 3, then the Pipelines page (Screen D strip shows "Step 3 of 5"). The Builder (agent) derives the new pipeline contract from the signed blueprint (existing `contracts.ensure`). Katie drops the sample file and runs the pipeline (existing runner). The Build steps section reads Done for each step from the contracts and the run log. She presses "Built, ready to test".
8. The Prover (agent) recomputes K12 for every reported period and runs the hypothesis check (the baseline 0.33 for 2026-05 reproduces from `gold.k12`; DATA-BRIEF truth D06). Nira writes Mei Ling's line.
9. Mei Ling opens Screen C at step 4. K12 matches for every reported period. She presses "Sign UAT" on K12 (existing route). The change waits for release.
10. Daniel signs the release on the Prove page (existing). The server regenerates the architecture record again (version 8, moment `release_signed`), marks the change's components `tested` then `live` only after step 5, and writes the map moment. 58 starts Proving from this release. Nira writes Harvey's line.
11. Harvey opens Screen C at step 5, reads the run book additions (expected arrival D+2 09:00 from the contract, SLA WD8) and presses "I run this from today". The change is `live`; the components move to `live`; the Watcher (agent) already checks every contract in `build/pipelines/` (`opportunity_watch.py` `_pipes` L68-L69); from now its alerts on this pipeline go to Harvey instead of Katie and carry `change_id` C-0003, so a radar pattern (57) can say which Initiative built the thing that drifts.
12. Branch, sent back: at step 4 Mei Ling finds a gap for 2026-08 and presses "Send back with a note". The change returns to step 3; Katie's Pulse line reads "Valuation chase protocol was sent back at Tester: K12 does not match for 2026-08". If the fix needs a design change, Katie presses "Send back to the Architect", the change returns to step 1, and the signed blueprint stays beside a new draft version (existing versioning in `blueprint.py` PUT).
13. Each person leaves Screen C to Pulse after their button; the organiser leaves the Initiative's record panel through "See the build" back to the intent.

## States and transitions (table: state, who moves it, to what, what is written)

Per change note (`build/changes/<change_id>.json`):

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | Server, on a signed gap report for an Initiative with `links.build` | `drafting` | Change note created; `intent_id`, `opened_at` |
| `drafting` | Architect agent, when its draft is written | `with_architect` | `sections` (guessed lines), `components_proposed`, draft diagrams; step 1 `opened_at` |
| `with_architect` | Architect role, "Send for approval" | `with_approver` | step 1 `signed: {by, at}`; Pulse line |
| `with_approver` | Head of department, "Approve the design" (and IT where the infrastructure view changes) | `approved` then at once `building` | step 2 `signed`; blueprint `state: signed`, `signed_by` with the real role; record regenerated; map moment |
| `with_approver` | Head of department, "Send back" | `with_architect` | `returns[]` row with reason |
| `building` | Developer, "Built, ready to test" | `testing` | step 3 `signed`; build steps snapshot |
| `building` | Developer, "Send back to the Architect" | `with_architect` | `returns[]` row; next blueprint version opens as draft |
| `testing` | Tester, UAT signed on every measure in the change | `waiting_release` | step 4 `signed` (the UAT signatures stay in `build/prove.json`) |
| `testing` | Tester, "Send back with a note" | `building` | `returns[]` row; the UAT `sent_back` record (existing) |
| `waiting_release` | Sponsor signs the release (existing) | `with_ops` | `release_ref`; record regenerated; map moment |
| `with_ops` | Ops role, "I run this from today" | `live` | step 5 `signed`; components `live`; alert `tell` switches to the ops person |
| `with_ops` | Ops role, "Not ready to take over" | `with_ops` (stays) | `returns[]` row (no step change); Pulse line to developer and sponsor |
| any before `live` | Organiser of the Initiative, "Stop this change" (required reason) | `stopped` | `stopped: {by, at, reason}`; proposed components removed from the record draft; nothing signed is undone |

Per component: `proposed` (Architect draft) → `approved` (step 2) → `built` (step 3) → `tested` (step 4) → `live` (step 5) → `retired` (a later change note retires it, approved at its own step 2).

## Records read and written (file or route, fields; mark Existing or New)

| Record or route | Fields | Mark |
|---|---|---|
| `build/architecture/record.json` (plane, `sh_platform/jsonfile.py`) | `{version, regenerated: {moment: blueprint_signed\|release_signed, ref, by, at}, components: [COMPONENT], history: [{version, moment, ref, at, added: [id], changed: [id], retired: [id]}]}` | New |
| COMPONENT | `{id, view: data\|infrastructure\|enterprise, kind, label, description: {text, mark, by, at}, owner: person id\|null, version, state, interfaces: [{to, kind: feeds\|reads\|writes\|posts, contract: path\|null}], refs: {blueprint_version, pipeline: path\|null, mart: str\|null, graph_node: id}, made_by: change id, changed_by: [change id], restricted: bool}` | New |
| `build/architecture/diagrams/<view>.v<n>.json` | Archify spec, the same shape as `docs/architecture/sh-m4-build.json`: `schema_version`, `diagram_type: architecture`, `meta.title`, `meta.views` (one view "This change" focusing the change's components), `components` (`id`, `type`, `label`, `sublabel`, `pos`, `size`), `connections` (`id`, `from`, `to`, `label`), `cards` | New |
| `build/architecture/diagrams/<view>.v<n>.html` | Rendered page, when a renderer is available (Open question 2) | New |
| `build/changes/<change_id>.json` | `{id, intent_id, state, blueprint_version, gap_report_ref, sections: {why, what_changes, decisions: [{placement, options: [str], chosen, why, follows}], build_steps, tests, run_book, risks} (each line {text, mark, from, by, at}), components: {added, changed, retired}, steps: [{n, role, person_id, opened_at, signed: {by, role, at}\|null}], returns: [{from, to, by, reason, at}], release_ref, stopped}` | New |
| `build/blueprint.json` and `blueprint.v<n>.json` (SHAPES 2) | `state`, `signed_by` (now the real signer and role), `version` | Existing; sign route reshaped |
| `build/pipelines/<source>.json` (SHAPES 3) | read for build steps and run book | Existing |
| `warehouse/runs.json` (SHAPES 4) | read for build steps Done and the step 3 gate | Existing |
| `build/prove.json` (SHAPES 5) | `measures[].uat`, `release` read for steps 4 and 5 | Existing |
| `build/alerts.json` (`sh_platform/build/alerts.py` L12-L13) | each alert gains `change_id` and `tell` (developer before `live`, ops person after) | Existing, fields New |
| Charter roles file `intents/m1_intent/roles/<session id>.json` (34) | `roles.*` and `answers.*`; new key `head_of_department` | Existing; key New |
| `intents/<id>/intent.json` | `links.build`, `build_handoff` (33), `hypothesis` ref (57) | Existing, read only |
| `graph/updates.json` via `knowledge_map.record_moment` | moments `blueprint_signed`, `release_signed` | Existing function, moments already listed in 55 |
| `GET /api/company/build/architecture?view=&v=` | record filtered by viewer | New |
| `PUT /api/company/build/architecture/components/{id}` | `owner`, `description` | New |
| `GET /api/company/build/changes`, `GET /api/company/build/changes/{id}` | change notes filtered by viewer | New |
| `POST /api/company/build/changes/{id}/send` (step 1), `/approve` (step 2), `/built` (step 3), `/take-over` (step 5), `/send-back` (any, with `to` and `reason`), `/stop` | step signatures | New |
| `POST /api/company/build/blueprint/sign` | signs with the viewer's charter role; called by `/approve` | Existing, reshaped |
| `POST /api/company/build/uat/{measure}/sign`, `POST /api/company/build/release/sign` | unchanged; on success the server moves the change state | Existing |
| `GET /api/company/build/home` | gains `chain: [{change_id, title, state, steps}]` | Existing, field New |
| `GET /api/pulse` | lines of kind `signature` and `request` from change notes | Existing route, new source |

## Fields this feature adds to the intent record

None in `intents/<id>/intent.json`. The change note points at the intent through `intent_id`; the intent reaches the change through `links.build` (33 is its only writer). The charter roles block (34) gains one key, `head_of_department: person id | null`, with its `provenance` and `answers` entries as 34 defines for the other roles.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

### What exists in v1 and exactly what changes

| v1 agent | What it does today (code) | What changes in this feature | What stays |
|---|---|---|---|
| Architect | Drafts `build/blueprint.json` deterministically from the signed baseline, catalogue, scan rules, trials and environment (`blueprint_draft.py` `draft` L132-L142, `BY = "Architect"` L17); no model call | Also owns the architecture record: after drafting the blueprint it places each new or changed thing as a component in the data, infrastructure and enterprise views, drafts the change note (seven sections, each line guessed with `from`), drafts the three Archify specs, and lists components without an owner. On a send-back it redrafts guessed lines only. At blueprint signature it drafts context card lines (60) | The blueprint draft and its provenance marks; the agent signs nothing |
| Builder | Contracts derived from the signed blueprint (`contracts.py` `derive` L30, `ensure` L72); runs bronze, silver, gold (`runner.py` `run_pipeline` L113, `transforms.py`) | Works from the change note's build steps: derives the contracts the change names and reports each step Done from the contracts and the run log. On screen the step is "Data engineer"; the person is the developer role | Contract shape (SHAPES 3), runner, run log |
| Prover | Recomputes each measure against the reported figure (`prove.py` `_compute` L96); UAT per measure (`uat.py`); release signed by the sponsor (`prove.py` L237-L254) | Adds the hypothesis check per measure in the change: the hypothesis baseline (57) for its baseline period reproduces from gold, or the line says "Not available yet" and names what is missing. The tester gate is the existing UAT; the change moves when every measure in it is signed | The release-ready rule (A-068), the sponsor's release signature |
| Watcher | Freshness, drift, failed checks, range breaks, alerts (`ops.py` `build` L72, `alerts.py`); radar patterns (`opportunity_watch.py` `detect` L160-L171) | Alerts carry `change_id` and go to the developer before `live` and to the ops person after; radar evidence lines (57) can name the change and Initiative that built the drifting pipeline. Nothing new is detected | Thresholds stay company settings (56); the Watcher never reads text and never opens an intent (ruling 32) |

Agent names on screen stay Architect, Builder, Prover, Watcher (the code names); the step names are Architect, Approval, Data engineer, Tester, Ops manager. Renaming the agents is Open question 6.

### Each agent's moments

- **Architect** drafts at three moments: the gap report signed (first draft); "Ask the Architect to redraft" or a send-back to step 1 (guessed lines only); and every regeneration (blueprint signed, release signed), when it rebuilds the record and the three diagrams from the signed records. The record is a projection: components come from the blueprint (`model`, `lineage`, `access`, `schedule`, `infra`), the contracts, the environment record, the profile's systems list and the map's System and Process nodes (55). It never invents a component no record names; a placement with no source reads "Not available yet" and names the missing record. People act: the architect role sends, the head of department approves.
- **Builder** derives contracts and code when step 3 opens. The developer acts: runs, fixes, presses "Built, ready to test".
- **Prover** recomputes after every run and after "Built, ready to test". The tester acts: signs UAT or sends back. The sponsor signs the release.
- **Watcher** runs on the schedule. The ops person acts: takes over, acknowledges and closes alerts (existing Ops page).
- **North** keeps the chain moving: it computes the completeness line at step 2 (every component has an owner, every measure has a test line, every build step names a contract), names the first gap on the disabled button, and nudges the person whose step it is (timing is Open question 7). North never signs, never sends back and never stops a change.
- **Lens** drafts the plain-words description of each enterprise solution component from the business glossary (29) and the catalogue (30); the component owner or the architect role confirms or edits.
- **Nira** writes the Pulse lines listed in Entry points, one per gate, and the "The architecture changed" line after each regeneration, built from what the reader may see.

## Rules (visibility, time box, who may do what)

- **Agents draft, people sign.** Each gate closes only with the named person's button. No agent signs, approves, marks built, verifies or takes over.
- **Who acts at each step.** Step 1 the architect role; step 2 the head of department (and the IT person for the infrastructure part when that view changes, BUILD-CENTRE-SPEC section 6); step 3 the developer role; step 4 the tester role (fallback sponsor or company admin, as `uat.py` today); release the sponsor; step 5 the ops role. A step with nobody named shows "Not named yet" and its buttons are disabled with "Name them in the charter" (34). Whether one person may hold two consecutive gates is Open question 3.
- **Send back** is allowed from steps 2, 3 and 4 to the step before, and from step 3 straight to step 1; a reason is required. Step 5 "Not ready to take over" keeps the change at step 5.
- **Stop.** Only the Initiative's organiser stops a change, with a reason. Signed records stay; components never built are dropped from the draft record.
- **Signed is read-only** (CLAUDE.md rule 7). An approved change note is never edited; a change after approval is a new blueprint version and a new change note that names the earlier one.
- **Regeneration.** The record and all three diagrams are regenerated on every signed blueprint and every signed release, and only then. Each regeneration is a new version; old versions are kept.
- **Visibility.** The record and diagrams are visible to everyone the map route allows (55). A component that serves a restricted measure shows as "Restricted" with no name, owner or interfaces to anyone outside the measure's access list (blueprint `access`). Change notes are visible to Build centre users and, read only, to the Initiative's participants; affected people follow ruling 4. A super admin has no route. No figure appears on Screens B or C except the hypothesis baseline and target the reader may already see on the Initiative (57).
- **Time box.** The Initiative is already `closed` when Build runs (ruling 26). The chain has no time box of its own; days at each step are shown, not enforced.
- **Egress.** Diagrams and change notes stay in the plane. The Archify spec is generated on the machine; nothing in the record leaves through the gateway.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Source | Where shown | When it cannot be worked out |
|---|---|---|---|
| Changes by state | count of `build/changes/*.json` by `state` | Screen A | "Nothing is being built." |
| Working days at the current step | today minus `steps[n].opened_at`, company time zone, Monday to Friday (ruling 22) | Screens A, C | "Not started" |
| Median working days per step across live changes | `steps[n].opened_at` to `steps[n].signed.at` | Screen A footer | "Fewer than five" below five live changes (ruling 8) |
| Send-backs per step | count of `returns[]` by `from` | Screen C side card | Hidden when none |
| Build steps done, of total | change note `build_steps`, Done read from contracts and `warehouse/runs.json` | Screen C step 3 | "No build steps" |
| Components by view and state | `build/architecture/record.json` `components` | Screen B chips and table | "No components yet." |
| Components with no owner | `components[].owner` null | Screen B "Owners missing", step 2 gate | Hidden when zero |
| Components added, changed, retired per version | `history[]` | Screen B "This version" | "First version." |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: skeletons of `sh_platform/build/*.py`; grep for "archify" over `sh_platform`, `tools`, `ui/src`, `docs/plan`, `docs/specs` (only docs mention it); callers of `record_moment(`; `docs/reuse-inventory.md` module 4 rows; the earlier repo's `emitters/architecture.py` and `emitters/architecture_drafting.py`. Every path below was checked on 7 Oct 2026.

| Existing | Where | Decision |
|---|---|---|
| Blueprint draft | `sh_platform/build/blueprint_draft.py` `draft` L132-L142, `marks` L153 | Reused unchanged; the component placement reads its output |
| Blueprint routes and versioning | `sh_platform/build/blueprint.py` GET L148, PUT L160-L196 (a signed blueprint is kept as `blueprint.v<n>.json` and the next version opens), sign L199-L216 | Reshaped: sign checks the viewer is the head of department named in the charter (today any viewer may sign and the role is written as "Company admin", L213), is called by "Approve the design", then runs the regeneration and `record_moment` |
| Contracts and runner | `sh_platform/build/contracts.py` `derive` L30, `ensure` L72; `runner.py` `run_pipeline` L113, `read_runs` L49 | Reused; build steps read them |
| Prover, UAT, release | `sh_platform/build/prove.py` `_compute` L96, release sign L237-L254; `uat.py` `_role` L24-L41, sign L48 | Reused; release sign gains the regeneration call; `_role` is the pattern for reading `head_of_department` |
| Watcher and alerts | `sh_platform/build/ops.py` `build` L72; `alerts.py` `_path` L12, `sync` L25, `act` L40; `opportunity_watch.py` `_pipes` L68, `detect` L160 | Reshaped: alerts gain `change_id` and `tell`; detection unchanged |
| Build home | `sh_platform/build/home.py` `build` L42-L86; `ui/src/pages/BuildCentre.tsx` | Reshaped: gains `chain` and the panel |
| Build pages | `ui/src/pages/BlueprintPage.tsx` (diagram L60-L85, "Draw the diagram" L125), `PipelinesPage.tsx`, `ProvePage.tsx` (UAT buttons L106-L107), `OpsPage.tsx`; routes `ui/src/App.tsx` L134-L162 | Reshaped: hand-over strip only; the blueprint's own model diagram stays |
| Map build nodes | `sh_platform/graph/build_nodes.py` `_register` L19-L31, `add_build_nodes` L63 | Pattern copied: a `Component` node type with edges `changed_by` (Component to Intent) and `part_of` (Component to Blueprint), registered the same way |
| Map update moments | `sh_platform/graph/knowledge_map.py` `record_moment` L259; called today only for charter signed, intent closed and scan run (`sh_platform/intents/charter.py` L683, `closure.py` L548, `intents/knowledge_map.py` L158) | Reused; the blueprint and release signatures add their calls (55 already lists these moments) |
| Charter roles | `modules/m1_intent/domain/roles.py` `ROLES` L5; 34's roles file | Reshaped: `head_of_department` added |
| Archify spec shape | `docs/architecture/sh-m4-build.json`, `sh-three-centres.json` and their HTML; `.archify/architecture-sh-three-centres-20261006-113000/` (a development render run) | Shape copied for the generated specs. The renderer is a development tool outside the product; the in-product diagram is drawn from the spec JSON with an SVG view like `BlueprintPage.tsx` `Diagram` (Open question 2) |
| Earlier repo architecture record and decision draft | `<earlier repo>\emitters\architecture.py` (`capture_architecture` L53, `check_consistency` L125), `emitters\architecture_drafting.py` (decision with at least two alternatives, `normalise` L177, `check` L197) | Reshaped: the decision shape (options, choice, why, what follows) and the static check that every cited reference exists become the change note's "Decision and alternatives" and North's completeness check; the model call is not used (the v1 Architect is deterministic) |
| Earlier repo screens | `s/architecture.js` (inventory, name only) | Not used: the new screens follow the current design tokens and `PageFrame` |

Genuinely new: the architecture record and its versions, the change note and its routes, the five-step chain state, Screens B and C, the `Component` map node, `head_of_department` in the roles block, alert `change_id` and `tell`.

## Not in this feature

- Gap analysis (room 0, `modules/m3_connect`, as built) and the hand-off (33).
- Naming the people (34); this file reads the roles block and adds one key.
- Proving and the weekly uplift report (58); the radar and hypothesis record (57); context cards (60).
- Cloud push, the Airflow generator, the estate scanner (BUILD-CENTRE-SPEC BC-2, BC-8).
- Hand-drawn diagrams or free-text components: every component traces to a record.
- Retiring a component outside a change note.

## Open questions

1. Routes. Ruling 1 covers `/centre/intent/...` only. This file uses `/centre/build/architecture`, `/centre/build/change/<change_id>` and `/api/company/build/...` beside the existing Build routes. Confirm, and whether the record belongs in Build or on the map (`/centre/intent/graph?view=architecture`).
2. Diagram rendering. The Archify renderer is a development tool, not part of the product. Is an in-product SVG drawn from the spec enough, or should the product bundle a renderer so "Download the diagram" gives the same HTML as `docs/architecture/`? The download button stays hidden until settled.
3. Head of department. Not in SHAPES section 12 or 34's six roles. This file adds `head_of_department` to the roles block; Lens would draft it from the profile (the head of the department in the Initiative's areas, else the head of data), but the profile has no head of department field today. May the same person hold architect and head of department?
4. IT signature. BUILD-CENTRE-SPEC says IT signs the infrastructure part "where IT owns the infrastructure". Who names the IT person: a company setting or a charter role?
5. Sponsor in the chain. The card's chain has five steps; the sponsor's release signature (BUILD-CENTRE-SPEC 4.5) sits between tester and ops manager. This file keeps it as a row, not a sixth step. Confirm.
6. Agent names. Keep Architect, Builder, Prover, Watcher, or rename them to the step names? The brief's section 5 names only North, Lens and Nira; the Build agents need the same standing (60 asks the same, its question 8).
7. Nudge timing and any expected days per step: no figure is justified. Days are shown, not enforced.
8. Component kinds per view (source, system, bronze, silver, gold, restricted file, read-only copy, runner, webhook, process, consumer) are drafted from BUILD-CENTRE-SPEC and SHAPES; confirm before the Archify `type` mapping is fixed.
9. Change note numbering: `C-0001` per company in order, or tied to the Initiative id?
10. Two Initiatives in Build that touch the same component: does the second wait for the first to go live, or are both drafted against the same record version with a conflict line?
11. Decision requests for Nitin, numbered from the next free A-number (ruling 20): (a) the architecture record and change note as the Build chain's records; (b) `head_of_department` as a seventh charter role; (c) blueprint signature restricted to the named head of department.

