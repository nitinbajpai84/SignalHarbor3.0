# 20. Linking intents: from one intent to the next, and to Build

Part of: Intent Centre v2. Depends on: 01 (record, state table, `links` block), 02 (type catalogue: `can_become`, `can_create`, `can_come_from`), 03 (chooser frame, `?from=`), the per-type start questions (22, 35, 38, 41, 43), 06 (people), 09 (closure and the next list), 16 (events), 21 (backlog). Feeds: 04 (home: linked chips, counters), 11 (share link view), the company graph, Build hand-off (gap analysis, room 0 of Build).

## Purpose (three sentences)

Intents rarely end alone: a brainstorm becomes an initiative, a weekly check-in item becomes a problem, a problem that is bigger than a fix becomes an initiative, a decision can lead to any other type, and a build-ready initiative goes to Build. This feature lets a person turn an intent, or one item inside it, into the next intent in one step, with North proposing the kind and pre-filling the new intent's start questions from the source. Every link is kept in both records and on the company graph, so anyone who may see the intent can walk the chain from the first idea to the thing that was built, and a cancelled link says why.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | Closing her intent, or reading an item mid-session and seeing it needs its own intent | "Turn this into..." on an item, or a row in the closure next list |
| Sponsor (Daniel) | Same, on intents he sponsors; hands an Initiative to Build | Same control; "Hand to Build" on a closed build-ready Initiative |
| Reviewer of a Weekly check-in (its organiser) | Review: giving each item one fate | The fate buttons "Ops problem" and "Backlog item" on a check-in item are this control with the kind fixed |
| Organiser of a Problem (Janet; Harvey as owner only if he is also organiser or sponsor, open question 10) | The fix is bigger than a fix | "Turn this into..." on the problem statement |
| Organiser or sponsor of a Decision (Janet, Daniel; Grace as decider only if she is also one of them, open question 10) | A decision needs carrying out | "Turn this into..." on the chosen option |
| Person who created the draft (it is visible to them alone, ruling 14) | Opening a draft that came from another intent | The "Came from" card on the draft; Nira line "A draft is waiting for you" |
| Participant, observer, affected person, area member | Reading where an intent came from or went | Chain view and linked chips, at their own visibility tier (observers read what a participant reads; affected people read existence, title, purpose, stage, clock, people and the outcome once closed, ruling 4) |
| Company admin | Checking the chain of any intent; cancelling a stuck one | Chain view (existence and outcome only) |
| Super admin | Nothing here. Sees that an intent exists (read through the kernel, ruling 5), never its links | `/centre/control/intents` only |
| North (agent) | Proposes the kind, drafts the pre-fill, writes both sides of the link, repairs half-written links | After the person presses "Create draft" or "Close intent" |

## Entry points (every route, link, Pulse line, button that leads here)

- **"Turn this into..." button** on any item inside a session or stage: wall card, brainstorm idea, weekly check-in item, problem statement or cause, decision option, and the Initiative's open choices found while defining.
- **"Turn this into..." button** on the intent page header, for the intent as a whole (used when no single item is the source).
- **Closure screen next list (09)**: each row of kind Initiative, Problem, Backlog, and (ruling 7, widened in 02) Decision and Brainstorm, is created through this feature once the closer presses "Close intent". The row's "Edit start answers" link opens the same panel before closing.
- **Weekly check-in review (`/centre/intent/<id>/week`, 40)**: the fates `problem` (button "Ops problem") and `backlog` (button "Backlog item") call this feature with the item as source. The fates `handled` and `nothing` write no link.
- **"Hand to Build" button** on a closed Initiative whose `outcome.build_ready` is true (09 shows "Open in Build" for the same state; this button writes the link first, then opens `/centre/build/gap-analysis?from=<id>`, room 0 of the Build centre, ruling 10).
- **Query `/centre/intent/new?type=<type>&from=<intent id>&item=<item id>`** (the chooser reads `type` and `from`; `item` is added here, open question 11). It opens the start questions of that type (22, 35, 38, 41 or 43) with the answers pre-filled as below. The chooser (03) is the frame only.
- **Chain view** `/centre/intent/past/<id>/chain` (ruling 1): from the "Linked intents" panel (09), a linked chip on any card in 04 or 12, and the intent's node page on the map.
- **Pulse lines from Nira** ("Pulse" is the daily page): "A draft came from <title>. Finish it" (to the person who created the draft), "A linked intent was cancelled" (to the source organiser), "<title> came out of your intent and is now closed" (to the source organiser).
- **Share link view**: shows "Came from" and "Led to" chips, read-only, for intents the viewer may open.

## Screens, element by element

### Screen A. "Turn this into..." menu and panel

Route: the menu opens in place on the item; the panel is the intent screen with a query, `/centre/intent/<id>?turn=<kind>&item=<item id>`, so it can be linked and reloaded (open question 11). Layout at 1280: the intent page stays on the left (840 wide); the panel opens on the right (440 wide), with the source item highlighted on the left. At 390: the panel is a full-screen sheet with a "Back" link; the source item sits in a collapsed "From this item" strip at the top.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| "Turn this into..." | button with menu | One row per kind this item may become, read from `can_become` and `can_create` of the source's type in `intent_types.yaml`. North's pick is first, marked "North suggests", with one line of why ("Three people raised this in two weeks") taken from records | Opens the panel for the chosen kind | Organiser, sponsor of the source. Hidden on a cancelled intent and on an item the viewer cannot read | Menu not offered when the catalogue lists no target for this type and item: nothing is shown, not a disabled button. A Decision always has targets (ruling 7) |
| Kind row | list item | Kind name (Initiative, Brainstorm, Problem, Decision, Backlog item, Build), a one-line reason it fits, and "Already linked" with the target title when this item already has a link of that kind | Already linked: opens the target. Otherwise opens the panel | As above | Not applicable |
| Source strip | panel (read-only) | Title and type of the source; the item text; the source `purpose`. Anonymous and sealed items show "A private item. Its words are not carried over." with no text | None | As above | Not applicable |
| New intent title | field | North's draft title, from the item text (first 80 characters, trimmed to a whole word) | Edit in place | Organiser, sponsor | Empty only if the item has no text: "Give the new intent a title." Create stays off |
| Start questions | list of fields | The target type's start questions in order (wording and field names from the per-type files: 22 Initiative six, 35 Brainstorm five, 38 Weekly check-in four, 41 Problem five, 43 Decision five). Pre-filled ones carry a chip "From <source title>" and a one-line "Why: copied from the chosen idea". Empty ones carry "North could not fill this from the source" | Edit, or "Keep" on a chip, or "Clear" to empty it. Required questions still empty do not block Create (they block Open later, as in the per-type file) | Organiser, sponsor | No pre-fill at all: the questions are shown empty with "Nothing to carry over from this item." |
| People carried over | chips (checkboxes) | Source organiser, sponsor, `owner`, `reporter`, `decider` and non-anonymous participants as "Suggested for the new intent", each unchecked by default except the person pressing the button | Check to add as a suggestion on the new draft's people list. Nobody is invited until the creator opens the intent | Organiser, sponsor | "No one is named on the source." |
| Areas carried over | chips | The source's `areas`, all checked | Uncheck to drop | Organiser, sponsor | "The source has no areas." Create stays off (at least one area is required to open, so it is asked here). Affected people are not carried over; the "affected people may read" switch (ruling 4) is asked in the new intent's start flow, default off |
| Time note | text | "The time box starts when the new intent is opened, not now." plus the new type's default | None | Organiser, sponsor | Not applicable |
| "Create draft" | button | Primary. Label for a Backlog item is "Add to backlog" (one reason field replaces the questions); for Build it is "Hand to Build" | Creates the target as a draft visible only to the person pressing it (or the backlog item in `intents/backlog.json`, or the Build hand-off), writes both link entries, closes the panel, shows "Draft created. Open it" with a link. Writes nothing when the call fails and says "Not created. Nothing was changed." | Organiser, sponsor | Disabled until title and areas are present |
| "Cancel" | link | "Cancel" | Closes the panel, writes nothing | As above | Not applicable |
| Open-draft link | link | "Open the draft" | `/centre/intent/new?type=<type>&from=<id>&item=<item id>&draft=<draft id>` (start questions of the type; `draft` is open question 11) | Organiser, sponsor | Not applicable |

### Screen B. Backlog item and Build hand-off variants of the panel

Same route, same layout. Backlog item: one field "Why this goes to the backlog" (required, one sentence), the item text as the title (editable), no start questions. It is stored as `why_it_matters.text` in 21 and the item is written to `intents/backlog.json` by the backlog spec's create function. Build (opens room 0, gap analysis, which is `modules/m3_connect` as built and moved; this feature only writes the hand-off and the link): read-only list of what is handed over (charter ref, glossaries, catalogue, process map, data sources map from `outcome`, as names with state, never copies) and the field "Anything Build must know" (optional). "Hand to Build" is offered only when `outcome.build_ready` is true. When false: "Build cannot pick this up yet. North lists what is missing." with `build_ready_gaps` as a list, and no button.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Backlog reason | field | Required one sentence | Edit | Organiser, sponsor | "Add the reason" in red; button stays off |
| Hand-over list | list | Each artefact: name, version, confirmed or draft | Opens the artefact read-only in a side panel | Organiser, sponsor, participants | "Nothing to hand over: the Initiative has no charter yet." Button hidden |
| Build gaps | list | `build_ready_gaps` | None | Organiser, sponsor, participants | Hidden when build-ready |
| Note for Build | field | Free text, max 500 characters | Edit | Organiser, sponsor | Optional, placeholder "Optional" |

### Screen C. Chain view

Route: `/centre/intent/past/<id>/chain` (ruling 1; also used for an open intent, open question 11). Layout at 1280: one horizontal line of cards (the chain, oldest at left), with the viewed intent outlined; under it a detail strip for the selected card. If the chain is longer than five cards the line scrolls sideways with the viewed intent kept in view. At 390: one vertical column, oldest at top, the viewed intent outlined; the detail strip opens as a sheet when a card is tapped.

The cards copy the `ds-trail` look used on the node page (see Reuse check). A chain is the viewed intent, every ancestor by `links.from`, and every descendant by `links.to`, plus the Build hand-off at the end. A backlog item on the way (source, backlog item, intent opened from it) is drawn as a card with caption "Backlog item" whose state is the item's `status` in 21. Dates use the company time zone from the profile, else UTC.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Chain card | card (link) | Caption (type: "Check-in item", "Brainstorm", "Problem", "Decision", "Initiative", "Backlog item", "Build"), title, state pill (open, closed, cancelled), date closed or days left, organiser name | Select shows the detail strip. "Open" inside the strip goes to the intent if the viewer may open it | Everyone who may see the intent exists (participants, observers, affected people, area members). A card the viewer may not see exists is not drawn (the line closes up and shows "1 step hidden") | See "Not linked" below |
| Link label | text between cards | "led to" with the date and who created it ("Janet, 3 Oct"). When North proposed it and the person accepted: "North proposed, Janet accepted" | None | Same as the card | Not applicable |
| Source item chip | chip on the right-hand card | The item it came from: "From check-in item: Statement file late again". Anonymous or sealed: "From a private item" | Opens the item in the source if the viewer may read it | Whoever may read that item | Hidden when the link came from the whole intent |
| Cancelled card | card variant | Dashed outline, state pill "Cancelled", the cancel reason in one line, "Cancelled by Daniel, 6 Oct" | Select shows the full reason | Everyone who may see the intent exists (reason is part of "cancelled intents say why", brief section 4) | Not applicable |
| Not linked | text | "Nothing came before this intent and nothing came out of it yet." | None | Anyone who may open the view | Is the empty state |
| Build card | card | "Build", the hand-off date, who handed it, the blueprint name once Build has made one, else "Waiting for Build" | Opens the Build page for the hand-off | Organiser, sponsor, participants, observers; others see "Build" and the date | Hidden when `links.build` is null |
| Chain sentence | text above the line | One plain sentence, for example "This began as a weekly check-in item on 3 Oct, became the problem 'Statement file late', then the initiative 'Fix the statement feed', and was handed to Build on 9 Oct." Built from the link entries (see Reuse check, GraphPage `trail`) | None | Same as the chain | "This intent has no links." |
| "Copy link to this chain" | button | Copies the route above | Clipboard | Anyone who may open the view | Not applicable |

### Screen D. "Came from" card and "Led to" list on an intent page

Region: right column of the intent page at 1280 (under the people panel); at 390 a collapsible section after the header, collapsed by default except on a draft that has `links.from`, where it is open.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| "Came from" card | panel | Source title, type, purpose, outcome one-liner, state, date closed or cancelled; the source's organiser, sponsor and participants by name (the `linked` tier, see Rules); the one source item text if not private | "Open the source" goes to the source if the viewer may open it; otherwise the card is all they get | Organiser, sponsor, participants and observers of the target; affected people and area members see title, purpose, stage and the outcome once closed only | "This intent did not come from another." |
| Source cancelled banner | agent line | "The source was cancelled on 6 Oct: <reason>. This intent keeps going. Check that it still makes sense." | "I have checked" (organiser) writes an event on the link and hides the banner for them | Organiser of the target | Not shown when the source is not cancelled |
| "Led to" list | list | One row per link out: kind chip, title, state, date; backlog rows show the backlog item title and its state | Row opens the target if the viewer may | As the intent page | "Nothing has come out of this intent yet." |
| Target cancelled row | list row variant | State pill "Cancelled", reason, who | None | As the intent page | Not applicable |
| "See the whole chain" | link | "See the whole chain" | Opens Screen C | As the intent page | Hidden when there are no links either way |
| North line on a draft | agent line | "North filled 3 of 8 questions from <source title>. Check each one." | Scrolls to the first pre-filled question | Organiser of the target | Not shown when nothing was pre-filled |

### Screen E. Intent node on the company map

Route: `/centre/intent/map/intent:<id>` (the existing `NodePage` route, `ui/src/App.tsx` line 131, `intent/map/:nodeId`; it is not in the ruling 1 list, so open question 12). The page shows the Intent node with its subline (type, state, organiser), the Chain component in place of the five-step Trail, the versions list and the comments, as for any node.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Subline | text | "Problem · Closed · organised by Harvey" | None | Anyone who may see the node | Not applicable |
| Chain | cards | The same cards as Screen C, from `GET .../graph/node/{id}` field `chain` | As Screen C | As the node's guard | "No links yet." |
| Edge groups (Topic view) | list | `led_to`, `came_from`, `built_by` and `owned_by` edges, each with provenance ("stated by Janet when closing") | Opens the other node | Anyone who may see both nodes; an edge to a silhouette node shows "restricted" (STRUCTURAL rule in `models.py`) | "No relationships recorded." |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet is reading the closed Weekly check-in record for Operations, week of 29 Sep (`/centre/intent/<id>/week`). Item 4, kind `broke`, says "Statement file late again". She presses **Turn this into...** on the item.
2. North has already read the item and the two earlier weeks. The menu shows "Problem" first, marked "North suggests: this came up in three weeks". Other rows: "Backlog item", "Brainstorm", "Decision". Janet chooses Problem.
3. The panel opens. North has filled Problem question 1 ("What is wrong?", field `what`, file 41) from the item text and question 5 (areas, "Operations"; and the item's author as a suggested person who feels it, if not anonymous). It leaves question 4 (owner) empty and says so. Janet edits question 1, presses "Keep" on the areas, and leaves the owner for triage.
4. Janet checks Harvey and Katie under "People carried over" (suggestions only). She presses **Create draft**.
5. North writes the new Problem as a draft, visible to Janet alone (ruling 14), with `links.from` set, writes the link entry on the source and on the target (the source first, under the lock), appends the `created` event to the `events.jsonl` of both, and marks the company graph dirty. The panel shows "Draft created. Open it". Nira tells Janet "A draft came from the Operations check-in. Finish it."
6. Janet opens the draft. The "Came from" card shows the check-in title, purpose, outcome and the one item. The pre-filled answers are marked. She answers the empty ones and opens the Problem (41). Harvey, the proposed owner, gets "A problem is waiting for you" from 41, not from this feature.
7. Weeks later the Problem closes with "no fix, accepted: too large". Janet, its organiser, presses **Turn this into...** on the problem statement and chooses Initiative; North pre-fills the Initiative questions from `outcome.what`, the owner (a suggested person) and `outcome.affected`.
8. Daniel, as sponsor of the new Initiative, closes it with a signed charter and build-ready true. He presses **Hand to Build**. North writes `links.build`, the link entry and the `created` event, marks the graph dirty, and opens `/centre/build/gap-analysis?from=<id>` (Build room 0; not part of this feature).
9. Anyone who may see the intents opens **See the whole chain** and sees: check-in item, Problem, Initiative, Build, each with its state and who linked it.
10. If the Problem had been cancelled, North would have written the cancel reason on the link, told the source organiser by a Pulse line, and left the Initiative standing with the banner of Screen D.

## States and transitions (table: state, who moves it, to what, what is written)

A link is not an intent. It has its own small state, kept as events in `intents/<id>/events.jsonl` (16), each carrying the `link_id`. The state of a link is its last event. The intent record holds counts only (ruling 12).

| Link state | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | Organiser or sponsor presses "Create draft", or the closer presses "Close intent" with a next row | `active` | `link_log` entry on source (dir `to`) and target (dir `from`), and event `created` in both `events.jsonl` files; target `links.from`; source `links.to` (or `closure.next[].ref`, or `links.build`); graph marked dirty |
| `active` | North, when the target is opened | `active` | Event `target_opened` with date. No state change |
| `active` | North, when the target is closed | `active` | Event `target_closed` with the target's `closure.what_came_out` first sentence reference. Nira line to the source organiser |
| `active` | Cancel of the source (01: organiser or sponsor, or company admin for a stuck intent) | `source_cancelled` | Event `source_cancelled` on every link out of it: `by`, `at`, `reason` copied from `cancel`. Target is not touched otherwise |
| `active` | Cancel of the target | `target_cancelled` | Event `target_cancelled` on the source's entry with `reason`. The source's `closure.next[].ref` is unchanged; if the source is still open, North asks its organiser whether to add a new next row |
| `active` | Organiser deletes a draft target before opening it (01) | `target_withdrawn` | Event `target_withdrawn` on the source's entry; `links.to` keeps the id; `closure.next[].ref` keeps the id and the row shows "Draft withdrawn" |
| `source_cancelled` | Organiser of target presses "I have checked" | `source_cancelled` | Event `source_checked` with by, at. Banner hidden for that person |
| any | North, on read, when only one side has the entry | `active` | Event `repaired` on the side that was missing; same `link_id`, so it is idempotent |

Rules of the table: the event stream is append-only. A closed or cancelled intent still accepts new link events (the only writable field after close besides ratings, share and `next[].ref`, see 09). An event never edits an earlier event.

## Records read and written (file or route, fields; mark Existing or New)

| What | Where | Status |
|---|---|---|
| The intent record, `links`, `closure.next`, `cancel` | `intents/<id>/intent.json` via `sh_platform/jsonfile.py` (`lock_for`, `write_json_atomic`) | New (01, folder layout per ruling 12); this feature writes `links`, `link_log`, `start_answers` |
| Link events | `intents/<id>/events.jsonl`, one per intent (16), appended and never edited | New (16); this feature appends the link events |
| Link service | `sh_platform/intents/links.py`: `propose`, `create`, `chain`, `record_event`, `repair` | New |
| Backlog item | `intents/backlog.json`, `items[]` as in 21 (`id`, `title`, `kind`, `area`, `areas`, `source: {intent_id, type, stage_ref, pulse_item_id}`, `raised_by`, `raised_at`, `why_it_matters`, `status`, `opened_intent`); this feature calls the backlog spec's create function with `{title, kind, areas, source, raised_by, why_it_matters.text}` and reads `status` for the chain | New, owned by 21; the function's module path is open question 3 |
| Build hand-off | The Build side route that makes the hand-off (gap analysis is room 0 of Build, ruling 10); this feature stores its returned ref in `links.build` | New, owned by Build |
| The company graph | `graph/company.json` via `sh_platform/graph/build.py rebuild`, `hooks.py mark_dirty` | Existing; new builder `sh_platform/graph/intent_nodes.py` |
| Source records of the item (card, idea, check-in item, option) | Wall session, week file `intents/<id>/weeks/<week_key>.json`, `outcome` of the source type, read by reference | Existing (wall) or New (outcomes in 02, weeks in 40) |
| Profile for areas and names | `sh_platform/profile/view.py`, `store.py` | Existing |

| Route | Does | Body | Answers |
|---|---|---|---|
| `POST /api/intents/{id}/links/proposal` | North proposes kinds and the pre-fill; writes nothing | `item?` | `{kinds: [{kind, why, suggested: bool}], draft: {title, start_answers: [{n, answer, from_item, why}], people: [], areas: []}}` |
| `POST /api/intents/{id}/links` | Creates the target draft (or backlog item, or Build hand-off) and both link entries | `version`, `to_kind`, `item?`, `title`, `start_answers[]` (field names of the target type's file), `carry: {people[], areas[]}`, `reason?`, `note?` | 201 `{link_id, target: {kind, id}}`. 409 on stale `version`; 403 if not organiser or sponsor; 422 for a kind not in the catalogue |
| `GET /api/intents/{id}/chain` | The chain at the viewer's tier, read from `link_log` and the link events | none | `{chain: [{id, type, title, state, date, organiser, link: {kind, by, at, proposed_by, item}}], hidden: n, build: {...}|null}` |
| `POST /api/intents/{id}/links/{link_id}/checked` | "I have checked" on the source-cancelled banner | none | the link entry |

Permissions (same style as 01, default deny): `POST .../links/proposal` and `POST .../links` roles `[company_admin, sponsor, analyst, approver, participant, owner]` with the organiser-or-sponsor check made on the record, not the role. `GET .../chain` includes `guest: true` for share-link readers. Super admin is refused on all four.

## Fields this feature adds to the intent record

Brief fields are kept as they are. `links.from`, `links.to` and `links.build` are written as the brief says (01 lists them as server-only). Added:

- `link_log`: `[{link_id, dir: "from"|"to", kind: initiative|brainstorm|pulse|problem|decision|backlog|build, other: {type, id|null, title_at_link}, source_item: {kind: card|idea|checkin_item|option|statement|choice, id, hidden: bool}|null, created_by, created_at, proposed_by: "north"|"person", reason|null}]`. There is no events list on the record: link events go to `intents/<id>/events.jsonl` (16), each with `link_id`, `event`, `at`, `by|null`, `note|null`, and the record keeps counts only (ruling 12). `title_at_link` is kept so a row still reads if the other record is hidden or gone. The item text is never stored here (it is read from the source on view), except the first 80 characters in the draft title.
- `start_answers[].prefilled_from`: `{intent_id, item_id|null, why}` or null, on each answer North pre-filled. It is removed when the organiser edits the answer, and `start_answers[].mark` stays `stated` or `unknown` as in 02.
- `links.suggested_people`: `[{name, from_intent}]` on a draft only, cleared when the intent opens (each is accepted into `people` or dropped by the organiser).

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

**North**
- Drafts the proposal: the order of the menu, the title, and the pre-fill. The pre-fill is a plain mapping from the source record, not a guess (table below). Where a question has no source field, North leaves it empty and says so. It does not make up an answer.
- Proposes a kind from records: a check-in item whose text matches items in two earlier weeks of the same area, or whose `kind` is `broke`, proposes Problem; an idea chosen in a brainstorm proposes Initiative; a Problem closed "no fix, accepted" proposes Initiative; a Decision closed proposes any type that carries it out (ruling 7); an Initiative open choice proposes Decision. Matching of "the same item" uses wording North reads from the records and names the weeks it used. Where North is not sure it says "North is not sure" and lists two kinds.
- Writes both sides of the link in one action, in the order source, target, graph mark. If the second write fails, it leaves the first and repairs on the next read (event `repaired`).
- At closure, creates the children from the confirmed next list, only after the person presses "Close intent" (09). It never creates a link on its own.
- Watches links: tells the source organiser when a target closes or is cancelled, tells the target organiser when a source is cancelled.
- Never signs, opens, closes or cancels an intent. It creates only drafts.

| Link | Target question (by number in 02) | Filled from |
|---|---|---|
| Brainstorm to Initiative (22) | 1 goal; 2 people; 5 areas | `outcome.chosen.idea`; source participants (suggested only); source `areas`. "Why now" has no question in 22, so it is not filled (open question 2) |
| Brainstorm to Decision (43) | 1 what must be decided; 5 areas | North's draft as a question from the unsettled choice; source `areas`; ideas kept that are not anonymous or sealed become starting options |
| Check-in item to Problem (41) | 1 what is wrong (`what`); 5 areas and who feels it | item `text`; week `area`, and the item's author if not anonymous |
| Check-in item to Backlog item (21) | title; why it matters | item `text`; the reason given at review |
| Problem to Initiative (22) | 1 goal; 2 people; 5 areas | `outcome.what` and the cost answer (Problem 3) if stated; `people.owner`, `people.reporter` and the people who feel it (suggested only); problem `areas` |
| Decision to any type | the target's first question; areas | `outcome.chosen_option` text; decision `areas`; `people.decider` (suggested only). First question: goal for an Initiative, `what` for a Problem, the idea statement for a Brainstorm, the question for a Decision, the area for a Weekly check-in |
| Any type to Decision (43) | 1 what must be decided; 5 areas | the item text (card, idea, option, statement, open choice); source `areas` |
| Initiative to Problem or Decision | 1 | the item text (card, ambiguity or open choice) |
| Initiative to Build | none | no questions: the hand-over list and the optional note |

**Lens**: not involved. Lens drafts definitions in the Initiative's own stages. When a Build hand-off is made, the hand-over list reads Lens-drafted artefacts as confirmed or draft; it does not change them.

**Nira**: writes the Pulse lines (the daily page) listed in Entry points (draft waiting, linked intent cancelled, linked intent closed). It drafts the line. The person acts by opening the draft or reading the event.

**The person acts at**: pressing "Create draft" or "Add to backlog" or "Hand to Build"; pressing "Close intent" with a next row; pressing "I have checked". Nothing else writes a link.

## Rules (visibility, time box, who may do what)

- **Who may link**: organiser or sponsor of the source. Whether a named `owner` (Problem) or `decider` (Decision) may link is open question 10. A closed intent can still be linked from (a follow-up is a new intent with `links.from`, per 01 and 09). A cancelled intent cannot be linked from: the menu is hidden and the route answers 409 "This intent was cancelled. Start a new one instead."
- **Allowed kinds** come only from `can_become`, `can_create` and `can_come_from` in `intent_types.yaml`; the route refuses anything else with 422. This file adds no kind of its own. Ruling 7 settles that a Decision may link to any type as source or target; 02 widens `can_become` and `can_create` to match, and this file reads them as they stand in 02 after that correction.
- **One item, one link per kind.** An item may lead to a Problem and a Backlog item, but not two Problems. A second request answers 409 "This item already led to <title>." with a link to it.
- **Linked context tier.** Whoever creates a link names the target's organiser. For the purpose of reading the source, the target's organiser, sponsor, participants and observers get a `linked` tier on the source: its title, type, `purpose`, state, `outcome` (one-liner and the per-type outcome fields), organiser, sponsor and participant names, and the single source item text. They get no other card, note, vote, rating, sealed or anonymous content, and no other item. The tier is read at view time from the source (not copied) and is not tied to any share link: it stays as long as the link entry exists. It never reaches a participant added to the target after the link unless the target's organiser names them; a person added later sees the tier cut to title, purpose and outcome one-liner.
- **Private items.** An anonymous or sealed item can be the source of a link only by someone who can read it. Its text is never pre-filled, never shown in `source_item`, never in the chain sentence, never on the graph. The link records `hidden: true`. The new organiser sees "From a private item".
- **Area visibility.** A link adds no new visibility. A person who may see an intent exists (participants, observers, affected people, area members; a draft only its creator, ruling 14) sees its chain card; a person who may not sees nothing and the chain closes up with "1 step hidden". The count of hidden steps is shown, never their number of people or titles.
- **Super admin**: sees neither the links nor the chain, only existence (ruling 5). **Company admin**: sees the chain at existence and outcome tier, never anonymous or sealed items.
- **Dates and numbers.** Dates and working days use the company time zone from the profile, else UTC. Counts are exact. A proportion or per-person figure over fewer than five records shows "Fewer than five" (ruling 8).
- **Outcome is an object from the start (ruling 6).** The `linked` tier reads the per-type `outcome` object; parts not yet filled read "Not recorded yet".
- **Share link**: the read-only view of an intent shows its "Came from" and "Led to" chips only for intents the link also names or whose existence the viewer may see; the chip never opens an intent the viewer may not open.
- **Time box**: a link starts no clock. The target's time box starts when it is opened (01), with the type's default. North may suggest a shorter box when the source already did part of the work; it only suggests, and the organiser picks.
- **Nothing is deleted.** Links, events and cancelled targets stay. The only removal is a draft deleted before opening (01), and its link entry stays with `target_withdrawn`.
- **Cancellation**: cancelling a source or a target never cancels the other end. North tells the person at the other end and the person decides. Cancel reasons are public to anyone who sees the intent exists (brief section 4).
- **Agents decide and draft; people act**: North drafts the link and the pre-fill; a named person presses the button; the entry stores who.
- **Concurrency**: both writes carry the intent `version` (01). A stale source version gives 409 "Someone changed this intent. Please reload." and nothing is written.
- **Industry**: no kind, question or wording is industry-specific. The family office pack supplies area names only.

### What is written when a linked intent is cancelled

| Cancelled | Written on the cancelled record | Written on the other record | Written on the graph | Told |
|---|---|---|---|---|
| Source with children | `cancel {by, at, reason}` (01) | On each child: event `source_cancelled` with the reason; child's "Came from" card shows the banner | Edge `led_to` and `came_from` kept; edge property `status: source_cancelled`; Intent node state `cancelled` | Nira to each child's organiser |
| Target (a child) | `cancel {by, at, reason}` | On the source: event `target_cancelled` with the reason; `closure.next[].ref` unchanged; "Led to" row shows "Cancelled" and the reason | Edge kept with `status: target_cancelled` | Nira to the source organiser; if the source is still open, North asks whether to add a new next row |
| Draft deleted before opening | file removed (01) | On the source: event `target_withdrawn` | Edge removed on the next rebuild (a draft has no node), `led_to` returns when the replacement is created | None |
| Backlog item dropped (21, reason required, nothing deleted) | the backlog spec (`status`) | On the source: event `target_withdrawn` with the drop reason as `note` | Backlog node kept with status `dropped` | None |
| Whole chain | Each cancelled intent keeps its own reason | Only direct neighbours get events; there is no cascade | Chain shows each cancelled card with its reason | Only direct neighbours |

## Counters and measures of this feature (numbers only, each traced to a record)

| Measure | Traced to |
|---|---|
| Links created, by kind and by month | `link_log` entries with event `created`, grouped by `kind` and `created_at` |
| Links proposed by North and accepted unchanged, versus accepted with a different kind | `proposed_by` and the final `kind`; "different kind" needs the proposal stored (open question 4), otherwise "Not available yet. The proposal is not kept." |
| Pre-filled answers kept as filled, edited, cleared | `start_answers[].prefilled_from` present, removed, or answer empty, on opened intents |
| Link drafts never opened after a set number of working days | Target state `draft` and `link_log.created_at`. The number is open question 8; until it is set the screen says "Not available yet. The stale period is not set." |
| Chains of three or more | Count of intents whose chain has at least three cards, from `links.from` and `links.to` |
| Initiatives handed to Build and how many came from a Problem, Brainstorm or Decision | `links.build` not null, joined to `links.from` type |
| Sources cancelled with open children, and children cancelled with open sources | Link entries with the events `source_cancelled` or `target_cancelled` where the other end is not closed or cancelled |
| Next-list rows with no `ref` after closing | `closure.next[].ref` null where `kind` is not `nothing` |
| Intent nodes and `led_to`, `came_from`, `built_by` edges on the graph | `graph/company.json` counts by type (CG Map view) |

A proportion over fewer than five links shows "Fewer than five" (ruling 8). Where a count has no records the screen says "Not available yet. No intent has been linked."

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

| Found | Where | Decision |
|---|---|---|
| Company graph spec: node types, edge types, projection not source of truth, four views, silhouette for `restricted_to` | `docs/specs/COMPANY-GRAPH-SPEC.md` lines 1 to 63 | Used as the rule. Intent becomes a node type and three edge types (below); nothing is edited on the graph |
| Node and edge vocabulary, endpoint rules, `Graph.node`, `Graph.edge`, `meet` | `sh_platform/graph/models.py` lines 10 to 85 | Reused. `node()` refuses a room not in `ROOMS`, so the new builder must add room `intent` to `ROOMS` first, as `build_nodes._register` does for types |
| A later builder that registers its own node types and edges and is called from `rebuild` | `sh_platform/graph/build_nodes.py` lines 20 to 33 (`_register`), 54 onwards (`add_build_nodes`), and `build.py` line 128 (the call) | Copied as the pattern for `sh_platform/graph/intent_nodes.py`: `_register()` (idempotent), `add_intent_nodes(g, plane, people)`, one call added in `rebuild` after `add_build_nodes` |
| `owned_by` list widened with `append` in `_register` | `build_nodes.py` lines 31 to 33 | Same trick: append `Intent` to the from list of `owned_by` (organiser) and of `built_by`, `Blueprint` to the to list of `built_by`. This also allows Measure to Blueprint through the same lists; harmless, listed in open question 5 |
| Rebuild hook: `mark_dirty(plane)` after a record write, `rebuild_if_dirty` on read | `sh_platform/graph/hooks.py` lines 20 to 73; wired by `profile/store.py` line 90 | Reused. The link service calls `mark_dirty` after both writes; also after any intent state change (cancel, close) |
| Rebuild reads records by path and never imports modules | `sh_platform/graph/build.py` lines 1 to 11, 113 to 137 | Followed. `intent_nodes.py` reads `intents/*/intent.json` by path and writes nothing |
| Per-viewer filter and name binding | `sh_platform/profile/view.py` lines 1 to 25 (`ROLE_PASS`, name matching) | Reused for the node's `restricted_to` (people in the intent's areas, its named people, company admin) |
| Anonymous card has no person edge; sealed is whole only to who may see it | `build.py` lines 190 to 211 (`_cards`) | Copied as the rule for private items: no text, no person, `hidden: true` |
| Trail of five steps; fixed order and captions; shows "Not yet" for a missing step | `ui/src/design/parts.tsx` lines 212 to 240 (`Trail`, `STEP_CAPTION`, `STEP_ORDER`) | Reshaped. The styling classes (`ds-trail`, `ds-trail__step`, `__cap`, `__detail`, `--link`, `--empty`) are copied; a new `Chain` component takes a list of cards in any order and has no fixed five. `Trail` itself is not changed |
| Trail sentence for a measure | `ui/src/pages/GraphPage.tsx` lines 93 to 104 (`trail`) | Reshaped into `chainSentence(chain)`: same join of short clauses; for an Intent node it replaces the "links" count line at line 95 |
| Node page: trail, definition, versions, comments, route | `ui/src/pages/NodePage.tsx` lines 18 to 192; route `ui/src/App.tsx` line 131 | Reused. One branch: when `d.type === "Intent"`, render `Chain` in place of `Trail`. Versions and comments unchanged |
| Node detail shape `trail: [{step, label, ref, by, at}]` | `docs/plan/SHAPES.md` section 10 (graft lines 37 to 43) | Extended compatibly: for an Intent node the response adds `chain: [...]` and leaves `trail` as `[]`; `GET /api/company/graph/node/{id}` keeps the same keys. No key renamed |
| Intent record `links`, `closure.next`, `cancel`, state table, routes and permission block | `01-intent-record-and-lifecycle.md` lines 44 to 59, 91 to 118, 160 to 185 | Reused, with the folder layout `intents/<id>/intent.json` (ruling 12; 01 is corrected there). This file adds `link_log` and `prefilled_from` only |
| Events stream; records hold counts only | `16-transcript-and-audit-trail.md` | Reused. Link events are appended there |
| Backlog record `intents/backlog.json`, `status`, `source`, `opened_intent` | `21-backlog.md` lines 153 to 167 | Reused. Items are created through 21 and `status` is read for the chain; no backlog field is added here |
| Gap analysis as room 0 of Build | `modules/m3_connect` (moved, not rebuilt, ruling 10); `docs/specs/BUILD-CENTRE-SPEC.md` (amendment is request A-075) | Not used here beyond the hand-off; Build owns it |
| Chooser frame reads `type`, `from` and sets `links.from`; draft resume | `03-create-intent-chooser.md` lines 14 to 24 | Reused as the frame; the per-type start questions (22, 35, 38, 41, 43) are canonical (ruling 2). `item` is added to the query |
| Closure next list, backlog write, child creation | `09-closure-and-signoff.md` lines 47, 105, 134 to 135, 162 | Reused. This file fills in how the children are written |
| `can_become`, `can_create`, `can_come_from` | `02-intent-types-catalogue.md` lines 286 to 412 | Reused as the only list of allowed links (widened for Decision, ruling 7). Question wording comes from the per-type files |
| Sealed and anonymous rules (D-013) | v1 spec `docs/specs/INTENT-CENTRE-SPEC.md`, and the graph rule at `COMPANY-GRAPH-SPEC.md` line 63 | Reused as they are |

Genuinely new: the link service and its four routes, the link log, the Intent node and three edge types, the `Chain` component, the "Turn this into..." control and panel. Searches run: graft for "links to", "closure next", "trail", "led_to", "came_from", "Intent node"; none found an earlier link feature. All paths in this table were checked to exist in this repo on 7 Oct 2026 (the graph, profile, jsonfile and UI files; the spec files in this folder).

### The graph: Intent nodes and edges

Builder `add_intent_nodes(g, plane, people)` reads every `intents/<id>/intent.json` (id pattern from 01) and adds:

| Part | Definition |
|---|---|
| Node | id `intent:<intent id>`; type `Intent`; label the title; room `intent`; provenance `{mark: "stated", by: organiser, src: "intents/<id>/intent.json", at: created_at}` |
| Node guard (`restricted_to`) | Names of people tagged to the intent's areas, its people block and the company admin. Anyone else sees a silhouette. A draft is added only for its creator's guard (ruling 14) |
| Node payload | `intent_type`, `state`, `areas`, organiser, outcome one-liner when closed, cancel reason when cancelled. Never cards, notes, ratings, anonymous or sealed content |
| `led_to` | `Intent` to `Intent`, from source to target, provenance "linked by <name> on <date>", property `status` from the last event |
| `came_from` | `Intent` to `Intent`, from target to source. Written with `led_to` so Topic view groups edges from either end |
| `built_by` | `Intent` (an Initiative with `links.build`) to the `Blueprint` node the Build ref names (`blueprint:v<n>`), provenance "handed to Build by <name>". If Build has made no blueprint yet, no edge, and the node payload says "Waiting for Build" |
| `owned_by` | `Intent` to `Person` for the organiser. Only edge to a person, so a Pulse item author never appears |
| Backlog item | Added as a node of type `Backlog` (new type, same builder) from `intents/backlog.json` (node id `backlog:<item id>`), so a `led_to` edge has an end. Open question 4 asks if it is wanted |
| Rebuild | Whole graph is replaced on rebuild (the projection rule), so a withdrawn draft's edge disappears and a cancelled link shows its `status` |

## Not in this feature

- The closure screen and its signatures (09); the Next list is used here, not redrawn.
- The type workflows, the chooser screens and the intent page (02, 03, 22, 35, 38, 41, 43).
- The backlog screen and the backlog file. This feature creates an item through the backlog spec's function only.
- Gap analysis and the Build screens. Gap analysis is room 0 of the Build centre at `/centre/build/gap-analysis?from=<id>`; it starts after the hand-off and is not rebuilt here.
- A "suggest a link" control for participants. Only organiser and sponsor link.
- Merging two intents, splitting an intent, and re-parenting a link. A wrong link is fixed by cancelling the target and creating another.
- Editing the graph directly; the new Company map views (CG-2, CG-3), apart from the Intent node page.
- Email or chat messages. Nira writes Pulse lines only.

## Open questions

1. Ruling 7 widens Decision links in 02. Please confirm 02's `next_kinds` also gains Decision and Brainstorm, so the closure list (09) can offer them. Until then 09 offers only Initiative, Backlog, Problem, Nothing.
2. Initiative start question 2 "why now" no longer exists in 22 (six questions: goal, people, build, definitions, areas, deadline). Brainstorm `outcome.chosen.why` therefore has nowhere to land. Does 22 take it as context for the goal?
3. Which module and function does 21 expose to create a backlog item? 21 names routes under `/api/intent/backlog`, which ruling 1 spells differently. This file calls "the backlog spec's create function" until 21 is corrected.
4. Is a Backlog node on the graph wanted? Without it a `led_to` edge to a backlog item cannot be drawn. Also: should the chain show source, backlog item, then the intent opened from it (21 sets `links.from` to the source and `backlog_ref` to the item)?
5. Widening `built_by` for `Intent` and `Blueprint` also allows Measure to Blueprint. Is an edge name such as `handed_to` better? The brief names `built_by`, so it is used here.
6. What is the shape of `links.build` (the Build ref) that gap analysis at `/centre/build/gap-analysis?from=<id>` returns or accepts? This file assumes an id from which a `blueprint:v<n>` node can be found.
7. Should participants of the source see the target's existence by default? This file says only through area visibility.
8. How long before a link draft counts as stale? Nothing in the records fixes it.
9. Should the `linked` tier show source participant names to the target's creator when those participants were not told? This file gives names and keeps content out. Confirm.
10. Should a named `owner` (Problem) or `decider` (Decision) be allowed to press "Turn this into..." when they are neither organiser nor sponsor? The brief and ruling 13 name the slots but not this right. This file allows organiser or sponsor only.
11. Routes outside the ruling 1 list that this file needs: the panel query `/centre/intent/<id>?turn=<kind>&item=<item id>`, the query parameters `item` and `draft` on `/centre/intent/new`, and the chain view `/centre/intent/past/<id>/chain` for an intent that is still open (the ruling names it under past). Confirm or give the right spelling.
12. The node page route `/centre/intent/map/intent:<id>` already exists in `ui/src/App.tsx` line 131 but is not in the ruling 1 list. Keep it, or move it?
13. A draft is visible only to the person who started it (ruling 14). A person who wants someone else to organise the new intent cannot hand the draft over. This file makes the creator the organiser and offers others only as suggested people. Is a hand-over of a draft wanted?
