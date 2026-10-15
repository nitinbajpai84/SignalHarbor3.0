# 32. Charter and signature

Part of: Intent Centre v2. Depends on: 01 (intent record), 06 (people and roles), 09 (closure), 27 (process map), 28 (data sources map), 30 (glossary and catalogue), 33 (build-ready check), 34 (who does what). Feeds: 09 (closure and sign-off), 33 (build-ready), Build hand-off, 11 (share link).

## Purpose (three sentences)

The charter is the one document an Initiative produces: what we intend to do, the problems we chose and why, how we will measure them, what is involved, who does what, whether a build is needed, and what we left for later. North drafts it from the records the Initiative already holds; the organiser edits the "so that" lines; the sponsor signs it, once. A signed charter is read-only and a change is a new version, so the company always knows exactly what was agreed.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | Define stage is done and the draft is ready | North says "The charter is drafted. Read it, fix the 'so that' lines, then ask Daniel to sign." |
| Sponsor (Daniel) | Charter is a complete draft | Nira "waiting for you": "<Title> charter is ready for your signature." |
| Analyst (Katie) | While the draft is open | Reads pages 4 to 8 as a participant. Edits nothing here: measures, processes and sources are edited in Define (27, 28, 30) and roles by the organiser only (34) |
| Participant (Aaron), observer | Any time after the draft exists | Participants read the charter; an observer reads what a participant reads and never writes |
| Affected people | Any time after the draft exists | See that the charter exists, its stage and, once signed, its outcome line. They read the content only when the organiser switched on "affected people may read" at creation (default off) or they are named on a share (brief ruling 4) |
| Approver (Grace) | Sponsor is away | Signs through the approver link (Existing route, see Reuse check) |
| North (agent) | Define stage closes | Drafts the charter, every blank "so that" line and the known risks; never signs |
| Lens (agent) | Drafting measures, processes, data sources, roles | Supplies the definitions, governed state, process list, source list and guessed roles the pages read |
| Company admin | Any time | Sees that the charter exists, its state and the signed outcome; never anonymous notes |
| Super admin | Any time | Sees that the intent exists (existence only); never the charter content |

## Entry points (every route, link, Pulse line, button that leads here)

- Intent page, Initiative, button "Open the charter" (shown once the Define stage is closed or a draft exists; spec 01 owns the page). Opens `/centre/intent/<id>/charter`.
- Wall screen, organiser stage bar, "Move to charter" (Existing StageBar, sends to the charter route).
- Old link `/centre/intent/charter/<session_id>` (Existing): redirects to `/centre/intent/<id>/charter` by looking the session up in the intent's `refs.wall_session_ids`, so old links keep working.
- Nira line for the sponsor: "<Title> charter is ready for your signature." Opens the charter at "Sign the charter".
- Nira line for the organiser: "<Title> charter has <n> 'so that' lines still to check."
- Pulse line when signed: "Daniel signed the <Title> charter, version <n>." Opens the signed charter.
- Approver link `/approve/<token>` (Existing; organiser creates it with "Send up for signing"; see Open question 7 on the route spelling).
- Share link (spec 11) opens the signed charter read-only.
- Build-ready check (33) and Define tabs (27, 28): the links "Open the charter" beside "Processes involved" and "Data sources".
- Build hand-off: the Build home links "Charter" on a handed-over Initiative.

## Screens, element by element

### A. Charter screen

Route: `/centre/intent/<id>/charter` (brief ruling 1). `<id>` is the intent id; the page resolves the Initiative's wall session through `refs.wall_session_ids` and calls the Existing session routes.

Layout at 1280: header strip (title, state chip, version chip, Download menu) across the top; left column (about 760 px) holds the charter pages as one scrolling document with a sticky page index; right column (about 360 px) holds the side panels in this order: Signature, Build-ready, Who does what, Version history. At 390: one column; the page index becomes a collapsible "Pages" bar under the header; the side panels drop below the document in the same order; the sticky "Sign the charter" button sits at the bottom edge for the sponsor.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Title and purpose | field (read) | Intent title, one-line purpose | Read only here; edited on the intent page (spec 01) | Those who may open the content | Title is never empty; purpose empty shows "No purpose written. Add one on the intent page." |
| State chip | chip | Draft, Signed or Superseded | None | Those who may open the content | n/a |
| Version chip | chip | "Version 2 of 2" (count of `versions[]`) | Opens the Version history panel | Those who may open the content | "Version 1" |
| Download menu | button | Two items: "Download PDF", "Download Markdown" | Downloads the current version as shown (a signed version downloads signed, with the signature block) | Participants, observers, organiser, sponsor, analyst, and affected people with read access | Disabled with "Nothing to download until a draft exists" |
| Page index | list | The ten pages in order, with a tick when the page has content | Scrolls to the page | Same | Pages with no content are listed and marked "Empty" |
| Page 1, The intent | panel | Title, purpose, who opened it (name, role, date) and why, areas, time box (`time_box.starts`, `ends`) | None | Same | "Not written yet" per missing field |
| Page 2, The frozen wall | panel | The wall as frozen: lanes, counts, card text, who took part (names, or "anonymous" count). Anonymous and sealed notes show as counts only | Link "Open the wall" opens `/centre/intent/<id>/wall` read-only | Same | "The wall was not frozen. The Initiative has no wall." |
| Page 3, Problems | list | Four lists in order: problems to solve now, pain points, what to track for the future, levers. Each row: priority chip, title, "so that" line, shelf chip, note count | See "so that" row below | Same | "No problems were chosen." |
| "So that" line | field | The sentence "so that <benefit>" under each problem; a North draft is marked "Draft by North" | Organiser edits inline (typed, saved with "Save the 'so that' lines"); "Use this line" accepts North's draft | Edit: organiser only, draft only. Others read | Empty: "Not written. North will draft it." |
| Tied priority select | field | Shown only when two problems tie | Organiser picks which is first; saved at once | Organiser, draft only | Hidden when no tie |
| "Use this line" | button | Appears under a North draft | Marks the line as confirmed by the organiser | Organiser, draft only | Hidden when the line is confirmed |
| Save the "so that" lines | button | Enabled when any line changed | Writes the edit to the draft version (see States) | Organiser, draft only | Disabled when nothing changed |
| Page 4, Measures | list | Per problem: measure name, business definition, technical definition, governed state (Confirmed, Draft, Unconfirmed, with who confirmed and when; "Confirmed" only when all six governed fields are confirmed) | Link "Open in glossary" opens the term in the glossary tab; link "Open in catalogue" opens its catalogue row (spec 30 owns both) | Same | Per problem: "No measure yet. Lens drafts one when the problem is chosen." If the glossary or catalogue is missing: "Not available yet: the glossary has no measures." |
| Page 5, Processes involved | list | From the process map (27) via `GET /api/intents/<id>/processes/charter-page`: per process the name, the owner (business owner of the process), status chip (Guessed, Edited, "Confirmed by Harvey"), step count and breaks count. A confirmed process shows in full; a guessed or edited one shows with the label "Not yet confirmed by its owner". Removed processes are not listed but appear in the change note. Header line "3 of 7 confirmed" | Link "Open the process map" opens `/centre/intent/<id>/define?tab=process-map`; a process name opens that process | Same | "No process linked. Add one in the process map." If the map was never drafted: "Not available yet: the process map has not been drafted." |
| Page 6, Data sources | list | From the data sources map (28): per source the name, system, format, state pill (Drafted by Lens, Edited, Confirmed by source owner, Needs source owner), and three separate lines: source owner, data owner, business owner ("Not named yet" when blank, never merged into one "Owner"). Header line "9 named, 6 confirmed". Technical areas as chips | Link "Open the data sources map" opens `/centre/intent/<id>/define?tab=data-sources`; a source name opens its row | Same. A restricted source shows as "A restricted source" with no owners or fields and a line "1 restricted source" (28) | "No data source linked." If the map was never drafted: "Not available yet: the data sources map has not been drafted." |
| Page 7, Who does what | panel (read copy) | The six roles from 34: Architect, Developer, Tester, Sponsor, Operations, Kept informed, each with the person's name, mark chip (Guessed, Stated, Left open) and answer chip (Not asked yet, Waiting, Accepted, Declined, Seen). Decline reasons are not shown here | None (edit lives in the side panel) | Same; affected people with read access see names, not answers (34) | "Roles not named yet" |
| Page 8, Build needed | panel | "Build needed: Yes", "No" or "Not answered", with the reason, who answered and when (from the intent's `build_needed`, `build_needed_reason`, `build_needed_by`, `build_needed_at`, 33). Then the seven build-ready lines from 33, each pass or fail: charter signed, business definitions confirmed, technical definition and catalogue and governed state, process owners, source owners, team named, build needed answered. "Build-ready: n of 7" | Link "Open the build-ready check" opens `/centre/intent/<id>/build-ready`; on "Not answered" the button "Answer it" opens the 33 dialog "Do we need a build?" | Same. Answer: organiser, sponsor | "Not answered. Janet or Daniel answers this." If never checked: "Not checked yet. North checks when Define has a charter draft." |
| Page 9, Parked for later | list | Everything on the Future shelf plus notes left on their own, each with the reason it was parked. A source feeding a parked cluster is marked "Parked cluster" (28) | None | Same | "Nothing parked." |
| Page 10, Known risks | list | Open items North drafted: processes not confirmed (27), sources without a confirmed source owner or with a restricted class undecided (28), build-ready lines that fail (33), required roles not accepted (34). Each line says what is open and who accepted it. Draft shows "Open items" until accepted | Organiser ticks "Accept this risk" per line (draft only) | Same; accept: organiser | "No known risks." |
| "Accept this risk" | checkbox | Per risk line | Writes `accepted_by`, `accepted_at` on that line | Organiser, draft only | Hidden on a signed version |
| Who does what (side panel) | panel | The Existing `RolesPanel`, reshaped by 34: the six roles, person picker from the company people list, mark chip, answer chip. The sponsor row is set from `people.sponsor` and is not picked here | Organiser uses "Confirm", "Edit", "Clear", "Ask them", "Ask everyone named", "Name someone else" exactly as in 34; no Save button, each change saves at once. Everyone else reads | Edit: organiser, draft only. Read: those who may open the content | "Not named yet" per role; footer "No roles drafted: the people list is empty. Add people in the profile first." |
| Build-ready (side panel) | panel | Chip "Build-ready: n of 7" and the first three items of North's to-do with the named person (33 panel B). Neutral until 7 of 7, then green | Button "See every line" opens `/centre/intent/<id>/build-ready`; an item opens its "Fix it" target | Those who may open the content | "Not checked yet." |
| Signature panel | panel | "Needs one signature: the sponsor, Daniel Kerr." When signed: name, date and time, and how (in the charter, or by approver link) | None | Same | "Waiting for Daniel Kerr" with a dashed signature line |
| Sign the charter | button | Primary, label "Sign the charter" | Opens the modal "Are you the sponsor?" | Sponsor only, and only on a draft. Organiser and others do not see it | Disabled with a one-line reason: "Check the 'so that' lines first.", "Add at least one problem." or "Answer 'Is a build needed?' first." |
| Modal "Are you the sponsor?" | modal | Text: "You are signing as <name>, sponsor of <Title>. Once signed, this version cannot be changed. A change is a new version." Two buttons | "Yes, I am the sponsor. Sign" writes the signature; "No, go back" closes the modal | Sponsor | n/a |
| Send up for signing | button | Existing | Creates the approver link (Existing), valid for the configured hours | Organiser, draft, when an approver is named | Hidden when no approver is named; the line "No approver named. Only the sponsor can sign." shows |
| Withdraw the link | button | Existing | Revokes the approver link | Organiser | Hidden when no link is out |
| Copy the link | button | Existing | Copies the approver link | Organiser | Hidden when no link |
| Version history | list | One row per version: version number, state chip, created by and at, signed by and at, comment, "Open this version" | "Open this version" opens that version read-only; the current version is marked | Same | Draft only: "Version 1 (draft). No signed version yet." |
| "Start a new version" | button | In a signed charter header | Creates a draft copy of the signed version (see Rules) and moves the signed one to Superseded only when the new one is signed | Organiser | Hidden on a draft |
| "Discard this draft" | button | In the header of a draft that is version 2 or later; asks for a reason | Removes the draft from the live list and keeps it in history as discarded, with the reason | Organiser | Hidden on version 1 and on a signed version |
| Returned banner | agent line | If the approver returned the draft: "Grace returned it: <comment>." | None | Organiser | Hidden |
| North line | agent line | "North drafted 3 'so that' lines. Check them." or "All lines are checked. Ask Daniel to sign." | None | Organiser, sponsor | Hidden when nothing to say |

Where each number on the pages comes from: counts of cards, participants and notes on page 2 and 3 read the frozen wall record; "n of m confirmed" on pages 5 and 6 read `processes.json` and the catalogue `sources` tab with the extras file; role counts on page 7 read the roles file; "n of 7" on page 8 reads `build_ready.lines[].ok` on the intent. Any number whose record cannot be read shows "Not available yet" and names the record.

### B. Signed view (same route, state Signed)

Same layout. No edit controls anywhere.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Signed banner | agent line | "Signed by Daniel Kerr on <date>. Read only. A change is a new version." | None | Those who may open the content | n/a |
| Download menu | button | As screen A; defaults to the signed version | Downloads PDF or Markdown with the signature block | Same as screen A | n/a |
| Share | button | Opens the share panel of spec 11 | Opens the panel | Organiser | Hidden until the intent is closing or closed |
| Start a new version | button | As screen A | As screen A | Organiser | Hidden on a draft |
| Hand-off line | text | "Handed to Build on <date>: <n> measures, <n> sources", read from `build_handoff` (33). It appears only after the organiser pressed "Hand to Build", never at signing | None | Those who may open the content | Hidden when not handed over |
| Pages 1 to 10 | panels | The frozen copy: `pages_frozen` for pages 4 to 8 and 10, so later edits in Define never change a signed charter | As screen A, links only | Same | As screen A |

### C. Approver view

Route: `/approve/<token>` (Existing; see Open question 7). Layout at 1280 and 390: one column, no module chrome. Unchanged in v2 except it shows the ten pages.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Charter pages 1 to 10 | panels | Read-only draft with every page | Scroll only | The link holder, until the link expires or is withdrawn | "This link is no longer valid." (Existing copy) |
| Intro line | text | "<Approver> is asked to approve this charter" (Existing) | None | Same | n/a |
| Comment field | field | Free text; required to decline | Type | Same | Empty; help text says a decline needs a comment |
| Approve | button | Existing label | Writes the signature as "by approver link" | Same | n/a |
| Decline (returns the draft) | button | Existing label | Returns the draft to the organiser with the comment | Same | Disabled until a comment is typed |
| Expiry line | text | "Link valid until <time>" (Existing) | None | Same | n/a |

Approval counts as the sponsor's signature only when the approver is the named signer for the Initiative (see Open question 1).

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Between steps, North closes the Define substages and drafts the charter version 1 from the frozen wall, the clusters and shelves, the measures, the process map, the data sources map and the roles. It drafts every blank "so that" line (marked "Draft by North") and the known risks. Nira tells Janet: "The charter is drafted."
2. Janet opens the charter from the intent page ("Open the charter") or from the Nira line.
3. Janet reads pages 1 to 10. For each draft "so that" line she presses "Use this line" or types her own. Lens has already drafted the measures; Janet checks them against page 4 and opens the glossary where one is wrong.
4. Janet reads pages 5 and 6. A process or source not yet confirmed by its owner stays labelled; she does not confirm for the owner. She uses the links to the Define tabs if she wants to chase one. North nudges the owner.
5. Janet opens Who does what in the side panel, corrects one name, confirms. It saves at once. She presses "Ask everyone named" (34).
6. Janet reads page 8. If "Build needed" says "Not answered", she or Daniel presses "Answer it" and answers the 33 dialog.
7. Janet ticks "Accept this risk" on page 10 for the open items she is content to carry.
8. Between steps, North checks: no unchecked draft line, at least one problem, build needed answered. It says "Ask Daniel to sign." and Nira puts the item on Daniel's list.
9. Daniel opens the charter, reads it, presses "Sign the charter". The modal asks "Are you the sponsor?". He presses "Yes, I am the sponsor. Sign".
10. The server writes the signature, freezes the version and its pages, writes the outcome record, moves the intent to closing and raises the Pulse line.
11. Between steps, North drafts the closure (spec 09) and rechecks the build-ready line "Charter signed", which now passes. Lens drafts any definition a failing line still needs, for a person to confirm.
12. Janet or Daniel downloads the PDF or Markdown copy, then leaves the screen by the link back to the intent page. Later, if the scope changes, Janet presses "Start a new version" and the cycle repeats from step 3.

## States and transitions (table: state, who moves it, to what, what is written)

Charter version states. `awaiting_approver` and `returned` are Existing v1 states and stay as sub-states of draft.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | North, when Define closes | draft v1 | Charter record, version 1, drafts marked `so_that_draft: true` |
| draft | Organiser edits a line, tie, role or risk | draft (same version, edited_at, edited_by set) | The version's problems, roles or risks. A draft never overwrites a human edit (rule 7) |
| draft | Organiser, "Send up for signing" | draft, awaiting approver | Approver link hash, expiry |
| draft, awaiting approver | Approver "Decline" | draft, returned | Return comment, by, at |
| draft | Sponsor signs (or approver approves) | signed | Signature (name, account id, at, how), frozen copy of every page (`pages_frozen`), outcome record, intent state closing, graph nodes |
| signed | Organiser, "Start a new version" | new draft v(n+1); v(n) stays signed | Copy of v(n) as draft, `created_by`, comment |
| signed v(n) | Sponsor signs v(n+1) | v(n) superseded, v(n+1) signed | `superseded_by`, `superseded_at`; v(n+1) signature |
| draft (new version) | Organiser, "Discard this draft" | removed from the live list, kept in history as discarded | `discarded: {by, at, reason}` |

Intent state: the first signature moves the intent to `closing`. Build-ready and hand-off (spec 33) happen inside `closing`. The organiser presses Close (spec 09) after hand-off or when 'build needed: no', moving the intent to `closed`. A new version of a charter on a `closed` intent: see Open question 4.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Read or written | Fields | Existing or New |
|---|---|---|---|
| `intents/<id>/intent.json` (intent record, spec 01 and brief ruling 12) | Read, written | state, outcome, links, people, `refs.wall_session_ids`, `build_needed*`, `build_team`, `build_ready`, `build_handoff` (33) | Existing (spec 01); build fields New (33) |
| Charter document, `modules/m1_intent/store/charter.py` (`CharterStore`) | Read, written | `versions[]` (version, status, template, problems, later, parked, wall, alone, footer, signatures, returned), `links[]` | Existing |
| Charter routes `GET/POST/PUT /api/modules/m1_intent/sessions/{id}/charter`, `.../sign`, `.../send`, `.../withdraw`, `.../download`, `.../email` in `modules/m1_intent/api/charter.py` | Used | as above | Existing |
| `POST /api/intents/<id>/charter/versions`, `POST /api/intents/<id>/charter/versions/{n}/discard`, `PUT /api/intents/<id>/charter/risks` | Written | start a new version, discard a draft, accept a risk | New (declared in `sh_platform/route_permissions.yaml`, default deny; see Open question 8) |
| `intents/m1_intent/outcomes/<outcome id>.json` | Written on sign | signatures, problems, footer | Existing |
| Roles file `intents/m1_intent/roles/<session id>.json`; `GET/PUT /api/modules/m1_intent/sessions/{id}/roles`; `domain/roles.py` | Read, written | the six keys architect, developer, tester, sponsor, ops, informed; `provenance`; `answers`, `names` (34) | Existing; answers New (34) |
| Measures with business and technical definition, catalogue row and governed state | Read | measure id, name, business definition, technical definition, state, confirmed_by, confirmed_at | Existing (M2 glossary, catalogue, governed state; specs 30 and 33 read them) |
| `intents/<id>/processes.json` via `GET /api/intents/<id>/processes/charter-page` (27) | Read | process id, name, owner, status, `confirmed`, step and break counts, `removed` | New (27) |
| `intents/m2_baseline/<baseline_id>/catalogue.json` `sources` tab and `data_sources.json` via `GET /baselines/{id}/data-sources` (28) | Read | source name, system, format, source owner, data owner, business owner, state, personal class, areas | Existing catalogue; extras file New (28) |
| `GET /api/intents/<id>/build-ready` (33) | Read | `lines[{key, ok, count, of, missing, evidence}]`, `state` | New (33) |
| Charter version fields `superseded_by`, `superseded_at`, `risks[]`, `pages_frozen`, `discarded` | Written | see "Fields this feature adds" | New |
| Graph nodes: charter node, problem nodes, measure nodes, edges "chosen in", "measured by", "signed" | Written on sign | node id, kind, version, signed_by, signed_at | Existing (`C.build_graph`, graph store), extended |
| `sh_platform/profile/view.py` | Read | per-viewer filter | Existing |
| Charter PDF | Written on download | rendered from the HTML export | New (see Reuse check) |

## Fields this feature adds to the intent record

None to the intent record's fixed fields, and none of the brief's section 3 fields are renamed. The build fields (`build_needed`, `build_team`, `build_ready`, `build_handoff`) belong to spec 33 and are read here, never duplicated. This feature adds to the charter version (held in the charter document, referenced by `links.build` and `outcome`):

```
charter_version: {
  ..., (all Existing fields),
  risks: [{text, source: process|source|build_ready|role|other, accepted_by|null, accepted_at|null}],
  pages_frozen: {measures: [...], processes: [...], data_sources: [...], roles: {...},
                 build: {needed, reason, by, at, lines: [...]}} | null,   # set at signing, then read only
  superseded_by: version number | null, superseded_at: iso | null,
  discarded: {by, at, reason} | null
}
```

The `build` block in `pages_frozen` is a copy of the 33 check as it stood at signing. Line 1 "Charter signed" is recorded as passing by this signature. The live check stays on the intent record.

The intent's `outcome` for an Initiative is an object from the moment the intent opens, never null (brief ruling 6). Signing sets `{charter_version, signed_by, signed_at, problems, measures, build_needed}` (references only; the content stays in the charter document). Specs 27 and 28 add their own counts to `outcome` under their own keys.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** drafts the charter at Define close, drafts blank "so that" lines (marked "Draft by North"), drafts the known risks from open items on pages 5, 6, 7 and 8, says "Ask Daniel to sign" only when every check is clear, recomputes the build-ready check after signing, and drafts the closure. A person acts: the organiser accepts or edits each line and risk; the sponsor signs. North never signs and never overwrites a line the organiser edited.
- **Lens** drafts the business and technical definition for each problem's measure, proposes governed state, drafts the process list (27), the data sources (28) and the roles (34, guessed from the people list and the wall, shown as guessed). A person acts: the organiser confirms roles; the named owners confirm a process, a source or a definition in their own tabs. Lens asks at most three open questions per person across Define (A-045).
- **Nira** puts "ready for your signature" on the sponsor's list, "lines to check" on the organiser's, and writes the Pulse line when signed. A person acts: the sponsor opens the item.
- Agents never sign. The signature panel shows only a named person.

## Rules (visibility, time box, who may do what)

- Only the sponsor signs. The company admin role may sign in the Existing route; v2 narrows the screen so only the named sponsor sees "Sign the charter". The approver link is the one exception (the named approver, when the sponsor named them).
- One signature per charter version. A person cannot sign twice.
- A signed charter is read-only. No field, role, line or risk can be edited. A change is a new version (Start a new version), which becomes the current version only when signed; until then the signed version stays the one Build reads.
- Each signed version is kept. Nothing is deleted; a discarded draft is kept in history with its reason.
- "Sign the charter" is disabled while any "so that" line is a North draft the organiser has not used or edited, while Page 3 is empty, and while "Is a build needed?" is unanswered. It is not blocked by unconfirmed processes, sources or roles: those appear on page 10 as risks the organiser accepts.
- Edit rights: the organiser edits "so that" lines, tie choices, roles and risks, only on a draft with no signatures. The sponsor reads. A participant reads. Processes, sources and measures are edited only in their own Define tabs by their own owners (27, 28, 30); the charter reads and freezes them.
- Visibility follows the brief: participants and observers open the content; affected people open it only when the organiser switched on "affected people may read" or they are named on a share, otherwise they see existence, title, purpose, stage, clock, people and the outcome line once closed; the super admin sees existence only; anonymous and sealed notes show as counts. A restricted source shows as "A restricted source" on page 6.
- The frozen wall is page two of the evidence: its content is frozen from the moment the wall freezes and the charter reads it, never recomputes it.
- Time box: the charter must be signed inside the Initiative's time box (10 working days by default, brief section 2). North warns the organiser before the end if the charter is unsigned, and proposes extend, close with what we have (the charter stays an unsigned draft, recorded as such), or cancel; a named person picks. The warning lead time is Open question 3.
- Every number on the charter traces to a record (counts of participants, notes, problems, processes, sources, roles, build-ready lines) or says "Not available yet" and names what is missing.
- No game words; no model or vendor names in copy; British spelling.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Source |
|---|---|
| Charters in draft, awaiting signature, signed, superseded | Charter documents, `versions[].status` |
| Days from Define close to signature | `created_at` of v1 and the signature `at` |
| "So that" lines drafted by North vs edited by the organiser | `so_that_draft`, `so_that_edited` on problems |
| Versions per charter | `len(versions)` |
| Signed charters with build needed yes, and of those, build-ready | intent `build_needed`, `build_ready.state` (33) |
| Risks accepted per signed charter | `risks[].accepted_by` |

Each shows "Not available yet" with the missing record named when it cannot be worked out. Counts are exact. Any mean or median shows "Fewer than five" below five records (brief ruling 8).

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

All paths below were checked and exist in this repo.

| Existing | Where | Decision |
|---|---|---|
| Charter routes: read, draft, edit, sign, send, withdraw, download, email, approver | `modules/m1_intent/api/charter.py` (routes at lines 226 to 373; `charter_view` at 97) and `modules/m1_intent/manifest.yaml` lines 56 to 67 | Existing, reused as is. Sign route reshaped to refuse a non-sponsor and a signature on a second version while the first is current |
| Charter store: versions, signatures, approver links, `_keep` writes the outcome and closes the session | `modules/m1_intent/store/charter.py` (class at 103, `sign` at 172, `_keep` at 180) | Existing. Reshaped: on sign the intent goes to `closing` (spec 09 closes it), not to closed; adds `superseded_by`, `risks`, `pages_frozen`, `discarded` |
| Charter view builder (`charter_view`, lists, signing block, versions list, graph) | `modules/m1_intent/api/charter.py` lines 97 to 130; `modules/m1_intent/domain/charter.py` | Existing, reused. Reshaped: adds pages 4 to 10 and the version rows |
| Charter screen: lines, tied priority, Later strip, stat grid, graph, Signature strip, SignActions | `ui/src/pages/CharterView.tsx` (343 lines; Line at 243, SignActions at 290), route registered in `ui/src/App.tsx` line 139 | Existing, reshaped: new route, page index, ten pages, modal "Are you the sponsor?", version history. Not rebuilt |
| Who does what panel | `ui/src/modules/m1_intent/charter/RolesPanel.tsx`; `modules/m1_intent/api/roles.py` (routes at 38 and 47); `modules/m1_intent/domain/roles.py` | Existing, reused. Detail and rules in spec 34 |
| Roles on the charter record: architect, developer, tester, sponsor, ops, informed | `docs/plan/SHAPES.md` section 12 (line 47) | Existing, reused; the six role names on screen come from here and from 34 |
| Markdown and HTML export | `modules/m1_intent/domain/charter_export.py` (`to_markdown` line 62, `to_html` line 81, `safe_filename` line 111) | Existing, reshaped to print pages 4 to 10; PDF is rendered from `to_html` (see Open questions) |
| Outcome record and hand-off | `modules/m1_intent/domain/handoff.py` (`build_outcome` line 33) | Existing, reused |
| Approver route and page | `modules/m1_intent/api/approver.py`; `ui/src/pages/ApproverPage.tsx`; route in `ui/src/main.tsx` line 30; manifest lines 65 to 67 | Existing, reused unchanged except the ten pages |
| Per-viewer filter, JSON files | `sh_platform/profile/view.py`, `sh_platform/jsonfile.py` | Existing, reused |
| Modal "Are you the sponsor?" | Not found. The stage bar has an "Are you sure?" pattern (`ui/src/modules/m1_intent/wall/StageBar.tsx` lines 20 and 25) | New, copy that pattern |
| Version history on screen | The store keeps all versions and the view returns `versions`; the screen does not list them (`docs/guides/TESTING-INTENT-CENTRE.md` line 261 onward, section 7) | New screen element over Existing data |
| Parked for later on the charter | `later`, `parked`, `alone` fields exist in the view and strip exists | Existing; reason text per parked item is New |
| Pages 4 to 8 and 10 | Search of `ui/src/pages` and `modules/m1_intent/domain` found no existing page | New pages reading the M2 records and the outputs of specs 27, 28, 33, 34 |

## Not in this feature

- The closure screen and rating (09, 10).
- Editing the measures, processes, data sources or catalogue (27, 28, 30; this feature only reads and freezes them).
- The build-ready check itself and the "Do we need a build?" dialog (33) and gap analysis (Build room 0).
- The detail of the Who does what panel and the role request page (34).
- More than one signature, committee votes on signing, e-signature legal weight.
- Charters for Brainstorm, Weekly check-in, Problem and Decision (they have their own outcome records).

## Open questions

1. Who signs if the sponsor is absent: only the named approver, or any company admin? v1 allows the company admin role in the route; the screen narrows to the sponsor.
2. PDF method: render `to_html` through the browser print path, or a server-side renderer? Not decided; the 390 px "text not cut off" check needs a decision.
3. Warning lead time before the time box ends. Two working days is a placeholder only; North's other warnings (33 uses half time and one working day, 34 and 28 use two working days) are not aligned either.
4. Does a new version of a signed charter on a closed intent need the organiser to reopen the intent, or may a charter version be added to a closed intent without reopening? Spec 01 owns reopen.
5. May a signed v1 stay the live version for Build while v2 is a draft (this spec says yes)?
6. Should a participant who disagrees be able to record a dissent on a signed charter? Not specified; not built.
7. Route convention: the approver page `/approve/<token>` and the Existing module API under `/api/modules/m1_intent/sessions/{id}/charter` do not follow the `/centre/intent/...` and `/api/intents/...` convention. They are kept because guests have no sign-in and guest routes may only live under `/api/modules/<module>/` (brief ruling 1). Confirm.
8. The three new charter routes (new version, discard, accept risk) are written under `/api/intents/<id>/charter/...`. Should they instead extend the Existing module routes so the session and the intent share one API?
9. The full-width Who does what route in spec 34 (`/centre/intent/<id>/roles`) is not in the view list of brief ruling 1. This spec uses only the side panel on the charter.
10. Line 1 of the build-ready check ("Charter signed") can only pass after signing, so the frozen `build` block always records it as passing by the signature. Confirm that a charter may be signed before the other six lines pass.
11. Should unconfirmed processes, unconfirmed sources and unaccepted roles block signing, or stay as accepted risks on page 10 as written here? 27 and 28 say nothing is hidden at close; 33 holds only hand-off, not signing.
12. Should the sponsor, who is also the signer, be allowed to answer "Is a build needed?" on the Sign button's own screen, or only on the build-ready page (33)?
