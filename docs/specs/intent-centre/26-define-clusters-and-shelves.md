# 26. Define strategically: clusters and shelves

Part of: Intent Centre v2. Depends on: 01 (intent record, `refs`, stages), 02 (Initiative stage `define_strategically`), 06 (people and roles), 07 (stage clock), 08 (North runs the stage), 27 (process map tab), 28 (data sources tab), 29 and 30 (Lens's definition tab, governed fields). Feeds: 09 (closure and sign-off), 27, 28, 29, 30, 33 (build-ready check).

## Purpose (three sentences)

Define strategically is the second stage of an Initiative. In one ninety-minute session the committee turns the wall into ordered clusters on four shelves, with every cluster on Must or Should proven governed, and the session close writes the charter draft. This file specifies the clusters, the shelves, the vote, the governed ring, the right panel tabs and the session mode; the content of each tab is specified in 27, 28, 29 and 30.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | Runs the session: moves cards and clusters, shelves, ticks, breaks ties, closes the session | North opens `define_strategically` after the wall's together stage closes; Pulse line "Define is ready" |
| Sponsor (Daniel) | Watches the session, reads the shelves, sends a measure back with a note, signs the charter later (09) | Invitation to the session; Pulse line "Define session at 10:00" |
| Analyst (Katie) | Prepares before the session: checks Lens's drafts, fixes cluster names and card placement | North's prepare list, two days before the session |
| Participant (Aaron) | Votes, agrees, comments on a cluster | Session opens; join link |
| Owner (Harvey) | Business owner, data owner or source owner of a measure confirms "Mine" or "Not mine" in the Definition tab | Pulse line "Confirm your measures" |
| Observer | Reads what a participant reads; never votes, agrees, comments or moves anything | Named on the intent |
| Affected person | Sees existence, title, purpose, stage, clock, people and the outcome once closed. Opens the content only when the organiser switched on "affected people may read" at creation (default off) or when named on a share | Pulse line, intent list |
| Governance lead / approver (Grace) | Confirms classification and who may see; settles ambiguous terms | Lens question lines; the cap is three open questions per person across all of Define (A-045, shared with 27, 28, 29, 30) |
| Company admin | Sees that the stage exists and its outcome after close (shelf counts, charter draft reference); never the cards or anonymous notes | Intent home |
| Super admin | Sees existence only (title unless the company keeps titles private, type, state, areas, people count, dates, time box status), read through the kernel at `/centre/control/intents`; never content | Control list |

## Entry points (every route, link, Pulse line, button that leads here)

- Intent home (04), Initiative card, stage bar: "Define strategically" chip opens `/centre/intent/<id>/define`.
- Wall (stage bar, `StageLinks`): "Go to Define" once the together stage is closed.
- Pulse (06): organiser line "Define is ready: set the session time"; every invitee line "Define session on <date>"; owner line "Confirm your measures".
- The v1 route `/centre/intent/define/<session_id>` redirects to `/centre/intent/<id>/define` when the session belongs to an intent. With no intent record it opens the v1 screen unchanged (Open question 9).
- Charter screen `/centre/intent/<id>/charter` (`Back to Define`) and the build-ready check (33), "Open Define" on a gap that names a cluster.
- Share link (11): read-only variant of the same screen, no drag, no vote, no session mode.

## Screens, element by element

### Screen 1. Define (`/centre/intent/<id>/define`)

Layout at 1280: top bar (existing shell). Page head row: breadcrumb, title, counts, actions. Below, the stage clock strip. Then two columns: left (about 68 per cent) holds the shelves board; right (about 32 per cent) holds the tabbed panel. The governed block sits above the shelves, full width of the left column.

Layout at 390: one column. Order: head, clock, governed block, shelf selector (a segmented control replaces the four columns; one shelf is shown at a time), cluster list, then the tabbed panel opens as a full-screen sheet when a cluster is tapped. Drag is replaced by the "Move to" menu on each cluster. Session mode is not offered below 768.

#### Head, clock and counts

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Intent header | panel | Intent title, purpose line, type chip "Initiative", stage chip "Define strategically", organiser name | Title opens the intent home (04) | Participants, observers, sponsor, organiser, analyst; affected people only when "affected people may read" is on | Never empty |
| Stage clock | agent line (North) | "Day 5 of 6. 3 days left on the intent." read from the stage clock (07); turns amber and red per 07 (this file adds no threshold) | "Ask North what is late" opens North's drafted options (extend, close with what we have, cancel) per 07 | Participants, observers, sponsor, affected | "Not available yet: no time box on this intent." |
| Counts line | text | "<N> cards, <C> clusters, <M> measures, <P> people" from the board and together stores | None | Those who may open the content | "No clusters yet" (see empty board) |
| Back to wall | button | "Back to the wall" | Opens the wall; refused with "The wall is closed" once the stage is closed (kept read-only) | Organiser, sponsor | Hidden when no wall is referenced |
| Start session | button (primary) | "Start the ninety-minute session" | Moves intent `open` to `in_session` (01) and turns on session mode (Screen 3) | Organiser | Disabled with reason "Name a start time and invite the committee first" when `people.participants` is empty |
| Close the session | button (primary) | "Close the session and write the charter draft" | Opens the close dialog (Screen 4) | Organiser, only while in session or while stage is open | Hidden for everyone else |
| Reopen for a correction | button | "Reopen Define" on a closed stage | Asks for a reason (required, kept), sets the stage `open` until the sponsor signs; refused with "The charter is signed" after signing | Organiser | Hidden unless the stage is closed and unsigned |
| Topic filter | field (select) | Topics of the cards plus "All topics" (existing) | Narrows the shelves board to clusters of that topic | Those who may open the content | "No topics yet" (disabled) |

#### Governed block

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Four percentages | chip row | Owners named (business owner, data owner and source owner all named), Classification set, Who may see confirmed, Team assigned, each as "n of m measures" and a percentage from `governed_state.json` | Click a chip filters the cluster list to clusters missing that field | Those who may open the content | "Not available yet: no signed baseline, so no measures to count." |
| Sealed count | chip | "Sealed: n cards" counts only; never what is in them | None | Those who may open the content | Hidden at zero |

#### Shelves board

Four columns, left to right: **Must**, **Should**, **Good to have**, **Future**. A fifth strip above them, "Not placed yet", holds clusters with no shelf. Heading of each shelf carries the cluster count. A topic filter above the board (existing) narrows to one topic.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Shelf column (Must, Should, Good to have, Future) | list (drop target) | Clusters on that shelf, in the order placed | Drop target for a dragged cluster | Those who may open the content | "Nothing on Must yet. Drag a governed cluster here." (Future: "Nothing parked.") |
| Not placed yet strip | list (drop target) | Clusters with no shelf and no vote result | Dropping here removes a shelf (only before the vote closes; kept in moves) | Everyone | "Every cluster has a shelf." |
| Cluster tile | chip-card, draggable for organiser | Colour edge, name, card count "12 cards", lanes chips ("Think", "Fix", "Fear", "Dream" as the wall names them), measure codes, vote tally "Must 3, Should 2, Good 1, Future 0", tick mark, governed ring | Click selects it and loads the right panel; drag moves it to a shelf | Those who may open the content; drag only for organiser | n/a |
| Cluster colour | visual | A colour fixed at first grouping and kept when North regroups or when the cluster is renamed | None. Not editable | Everyone | n/a |
| Cluster name | button | North's name, renameable by the organiser | Click opens an inline field; Enter saves; Escape cancels; every rename is kept in moves | Name visible to all; rename organiser and analyst | Placeholder "Name this group" for a new cluster |
| Lanes chips | chips | Lane names the cluster's cards came from with counts, for example "Fix 5, Fear 4, Dream 3" | Click filters the card list in the panel to that lane | Everyone | Hidden if cards have no lane (older walls) |
| Card list (inside the selected cluster) | list | Cards: text, who (or "Anonymous"), lane. Sealed cards show "Sealed card" and no text | Drag a card to another cluster tile to move it; or "Move to" menu | Cards visible per v1 rules (D-013, seal); move organiser and analyst | "No cards in this group." |
| Move to menu | field (select) | Four shelves plus "Not placed yet" on every tile (keyboard and 390 route) | Same as a drop | Organiser | Hidden for others |
| Add group | button | "Add a group" | Creates an empty cluster with a new colour; name required | Organiser, analyst | n/a |
| Split group | button | "Split" on a selected cluster | Opens a card picker; chosen cards form a new cluster | Organiser, analyst | Disabled when the cluster has under two cards |
| Restore North's grouping | button | "Put back North's grouping" | Confirm dialog, then restores board grouping; shelves and votes are kept for clusters that survive; a cluster that disappears returns to "Not placed yet" with its move kept | Organiser | Disabled when nobody has changed anything |
| Cards on their own | tile | Cards that fit no cluster, count only | Click opens the list; drag a card into a cluster | Organiser, analyst | "Every card is in a group." |

#### The vote (existing together stage, reused)

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Vote buttons on a tile | buttons | "Must", "Should", "Good to have", "Future" (the four options) | Records the person's one vote per cluster; a second click changes it | Participants, sponsor, analyst, organiser (observers cannot vote; the organiser does not count towards "everyone done") | Disabled with "Voting is closed" when the room is held or signing |
| Tally | text | Counts per option; "Must plus Should: 5. The rest: 2." | None | Those who may open the content | "No votes yet" |
| Vote result mark | chip | "Backed" when Must plus Should beat the rest and at least the minimum votes; "Tied" on a tie; "Not backed" otherwise | None | Everyone | Hidden before the first vote |
| Tick | button | "Tick" or "Untick" | Organiser decides. A cluster the organiser has not touched follows the vote rule automatically | Organiser | Hidden for others |
| Tie banner | agent line (North) | "Group <name> is tied. The organiser decides." | Organiser ticks or unticks, or moves it to a shelf; the choice is the tie-break and is kept with name and time | Organiser (act), others (shown as context) | Hidden when no tie |
| Agree | button | "I agree with this group" | Toggles the person's agreement | Participants | n/a |
| Comment | field and button | Thread per cluster; "Comment" and an "Anonymous" toggle where the wall allows names to be hidden | Posts; anonymous author is never shown to organiser or admin | Participants (observers read, never post) | "No comments yet" |
| I am done | button | "I'm done voting" | Marks the person done; when everyone but the organiser is done North says so | Participants | Hidden once done |

The vote rule is the existing `auto_decision` rule: a cluster is ticked when Must plus Should votes are more than all the other votes together and reach the minimum vote count; equal counts are a tie and the organiser breaks it. The minimum count is the existing board setting (`auto_min_votes`); this spec does not change it.

#### Governed ring and refusal

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Governed ring | visual on tile | A solid ring when every measure the cluster maps to has all six fields confirmed (A-054); a dashed ring until then; no ring and the label "No measures yet" when the cluster maps to no measure | Hover or focus names the missing fields, for example "Missing: who may see, who resolves it" | Those who may open the content | "No measures yet" (not dashed: nothing to govern) |
| Ring key | text | "Solid: all six fields confirmed. Dashed: something is missing." under the board | None | Everyone | n/a |
| Refusal message | agent line (North), inline on the tile and read out to screen readers | On a drag or "Move to" to Must or Should of an ungoverned cluster: "Needs who may see and who resolves it before it can sit on Must." The tile snaps back. With no baseline or no measure: "Define the measures first." | Link "Open Lens's definition" selects the cluster and switches the panel to the definition tab | Organiser | Never shown for Good to have or Future |
| Refusal log | record | Each refusal is kept as a move with `result: refused` and the reason | None | Organiser | n/a |

The refusal applies to every route into Must or Should: drag, "Move to" menu, tie-break tick that would place a cluster on a shelf, and "Restore North's grouping".

#### Future shelf modal

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Park dialog | dialog | Title "Park <name> for later" | Opens on any move to Future | Organiser | n/a |
| Reason | field (required) | Free text, limit the existing reason length | The dialog will not close, and "Park it" stays disabled, until filled | Organiser | Error "Please say why this is parked for later." |
| Review date | field (date, required) | Defaults to today plus one quarter (proposed, Open question 12), in the company's time zone from the profile, else UTC; the organiser may change it to any later date | Saved with the move | Organiser | Error "Choose a date after today." |
| Park it | button | "Park it" | Saves shelf `future`, reason, review date; tile moves; the move is kept with name and time | Organiser | Disabled until both fields are valid |
| Cancel | button | "Cancel" | Closes; the tile returns where it was | Organiser | n/a |
| Parked marker | chip on tile | "Review 7 Jan 2027" and the reason on hover or tap | Click shows the reason | Those who may open the content | n/a |

Nothing is deleted. A cluster on Future keeps its cards, votes and comments. At the review date Nira adds a line to the organiser's Pulse: "Review parked group <name>". The organiser can move it, extend the date with a new reason, or leave it.

### Screen 2. Right panel (tabs)

Layout at 1280: sticky panel, tabs across the top, content below. At 390: bottom sheet with the tabs as a scrolling row. The panel always works on the selected cluster; with nothing selected it shows "Select a group to see its definition".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Tab: "Definition" | tab (default) | Lens's definition for the selected cluster's measures: the six governed fields as provenance cells, business and technical definition, and the business owner, data owner and source owner of each measure (content in 29, 30 and 31) | Opens 29 and 30 content here; "Mine", "Not mine", "Confirm the definition" and "Send back with a note" live in that content | Organiser, sponsor, owners, governance lead, analyst (confirm); participants and observers read | "No measures behind this group yet. Lens drafts them once a baseline exists." |
| Tab: "Process map" | tab (new) | The process map drawn for the selected cluster (content in 27) | Opens 27 content | Those who may open the content | "Not drawn yet. Lens drafts it from the cards and interviews." |
| Tab: "Data sources" | tab (new) | The sources behind the selected cluster's measures (content in 28) | Opens 28 content | Those who may open the content | "No sources named yet." |
| Tab status dot | chip | Green when that tab's content for the cluster is confirmed, amber when drafted, none when empty | None | Everyone | None |
| Cluster header (above tabs) | panel | Name, shelf, ring, measure codes, owner names with their kind (business, data, source) | None | Everyone | n/a |

A sealed cluster (every card sealed) shows its name and counts and the tabs show only what the measures say, never the card text.

### Screen 3. Session mode (ninety minutes)

Entered with "Start the ninety-minute session" by the organiser; ended by the close dialog or when the organiser leaves it. Route: the same as Screen 1, `/centre/intent/<id>/define`, in a different dress (Open question 10 asks whether the projector should use `/centre/intent/<id>/projector`).

Layout at 1280 (projector): the head collapses to a single bar; the shelves fill the screen with large tiles; the right panel opens as a drawer over the right third when a tile is tapped; the clock and counter sit in the bar. No avatars, no comment threads (counts only). At 390: not offered; the screen stays in normal mode and shows the clock.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Projector toggle | button | "Projector view" | Switches to large tiles, hides participant initials and comment text | Organiser | Hidden below 768 |
| Session clock | text | Counts down from 90:00 (mm:ss) from the moment of start; amber at 15:00 and red at 5:00 (proposed, Open question 2); keeps counting past zero as "+ 04:12 over" | None | Everyone in the session | Shows "90:00" before start |
| Decisions counter | text | "Decisions: 9 of 14" where a decision is one cluster with a shelf set and, if on Must or Should, ticked; 14 is the number of clusters | None | Everyone in the session | "Decisions: 0 of 0" with no clusters |
| Pause | button | "Hold the room" | Existing pause: stage and clock stop, voting is refused with "The room is held" | Organiser | Hidden when already held; "Carry on" appears |
| Time up banner | agent line (North) | At zero: "Ninety minutes are up. <n> of <c> decided. Close with what we have, or add time." | "Close the session" opens Screen 4; "Add 15 minutes" (length proposed, Open question 3) extends this session clock (reason asked, kept) | Organiser (act), others (context) | Hidden before zero |

### Screen 4. Close the session (dialog over Screen 1)

Route: none of its own; it opens over `/centre/intent/<id>/define`. Layout at 1280: a centred dialog, open items listed above the buttons. Layout at 390: a full-screen sheet, the list scrolls, the buttons stick to the bottom.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Open items list | list (North) | Counts read from the board and shelf store: clusters with no shelf, Must or Should clusters not ticked, measure fields not confirmed, parked clusters past their review date | Each line closes the dialog and filters the board to those clusters | Organiser | "Nothing is open. Every cluster has a shelf and every field is confirmed." |
| Extension reason | field (required) | Shown after "Add 15 minutes" on the time-up banner | "Add 15 minutes" stays disabled until filled; saved in `extensions` | Organiser | Error "Please say why more time is needed." |
| Confirm | button (primary) | "Close and write the charter draft" | stage `closed`, charter draft written, build-ready check run (33), intent stays in current state | Organiser | Disabled while the charter draft is being written |
| Keep going | button | "Keep going" | Closes the dialog, nothing written | Organiser | n/a |
| Result line | agent line (North) | "Charter draft written from <n> ticked groups. <g> gaps found." with n from the charter outcome and g from the build-ready check | "Open the charter" goes to `/centre/intent/<id>/charter` | Organiser | "Not available yet: the build-ready check has not run." |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Entry: Janet opens `/centre/intent/<id>/define` from the Pulse line "Define is ready: set the session time" or from the stage bar. North opens `define_strategically` when the wall's together stage closes. Before anyone arrives North has clustered the cards, named and coloured each cluster, and set lanes and counts (existing grouping).
2. Lens drafts, for each measure a cluster maps to, the six governed fields, the business and technical definitions (29 and 30), a first process map (27) and a first sources list (28). Lens also raises ambiguous terms as questions, within the shared cap of three open questions per person across Define (A-045).
3. Lens proposes a shelf per cluster from card count only and labels it "A suggestion". It never uses a vote prediction. It is not applied.
4. North sends Pulse lines: organiser "Set the session time", analyst "Check the drafts", invitees "Define session on <date>".
5. The analyst (Katie) opens Define, fixes cluster names and card placement, answers Lens's questions, and leaves.
6. Owners (Harvey, as business owner, data owner or source owner) open their cluster and click "Mine" or "Not mine, it is <name>" in the Definition tab.
7. At the session the organiser (Janet) projects the screen and clicks "Start the ninety-minute session". North starts the clock and the intent moves to `in_session`.
8. People vote on each cluster and comment. North watches the tally and, when everyone but the organiser is done, says so.
9. The organiser moves each cluster to a shelf. A move to Must or Should of an ungoverned cluster is refused with the missing fields; the organiser opens the Definition tab and the owner or governance lead confirms the missing field in the room. A move to Future opens the park dialog.
10. On a tie North names the cluster and the organiser breaks it with the tick or a shelf choice.
11. The governance lead settles each ambiguous term. A term accepted as ambiguous is recorded as a known risk (29).
12. The organiser clicks "Close the session and write the charter draft". North counts what is open (clusters with no shelf, Must or Should clusters not ticked, unconfirmed fields) and shows it in the dialog.
13. The organiser confirms. North writes the charter draft from the ticked clusters (existing charter draft), keeps the shelves as the priority, stamps the stage `closed_at`, and runs the build-ready check (33) to give a first list of gaps.
14. The sponsor (Daniel) gets a Pulse line "Charter draft ready to read and sign" (09). Nobody signs in Define.
15. Janet clicks "Open the charter" and leaves Define for `/centre/intent/<id>/charter`, or closes the tab. The intent moves to `closing` at charter signature (09).

## States and transitions (table: state, who moves it, to what, what is written)

| State | Who moves it | To what | What is written |
|---|---|---|---|
| Stage `define_strategically` not opened | North, when together stage closes | `open` | `stages[1].opened_at` |
| Stage `open`, intent `open` | Organiser, "Start the ninety-minute session" | Intent `in_session`, stage still `open` | `session.started_at` (New), intent state |
| In session | Organiser, "Hold the room" | `paused` (existing) | `paused_at`, `paused_from` |
| Paused | Organiser, "Carry on" | Back to `in_session` | clock resumes; paused time not counted against ninety minutes |
| Cluster no shelf | Organiser, drag or menu | Shelf `must`, `should`, `good_to_have` or `future` | shelf row and a move (who, when, from, to) |
| Cluster to Must or Should, ungoverned | Organiser | Refused, stays | a refused move with the reason |
| Cluster to Future | Organiser, park dialog | `future` with reason and review date | shelf row (reason, review date) and a move |
| Cluster ticked | Vote rule, or organiser | ticked / unticked | `ticked`, `touched` (organiser decisions are kept over the rule) |
| Session in progress | Organiser, close dialog | stage `closed`, intent stays in current state | `stages[1].closed_at`, charter draft ref in `refs.charter_outcome_id`, session close record |
| Closed stage | Nobody | Read-only: shelves, votes and moves are kept, nothing moves | None |
| Reopen for a correction | Organiser with a reason (kept) | `open` until the sponsor signs; refused after signing | `reopened: {by, at, reason}` (New) |

## Records read and written (file or route, fields; mark Existing or New)

In the table, `...` stands for `/api/modules/m1_intent/sessions/{id}`.

| Record | Fields | Read or write | Status |
|---|---|---|---|
| `GET .../together` | clusters (id, name, note_count, votes, tally, ticked, shelf, shelf_reason, review_date, measure_codes, governed, missing, colour), people_count, organiser, stage | read | Existing |
| `POST .../board/notes/{note_id}/move` | note to cluster or "on its own" | write | Existing |
| `POST .../board/clusters`, `.../rename`, `.../split`, `.../board/group`, `.../board/restore` | add, rename, split, regroup, restore | write | Existing |
| `POST .../together/clusters/{id}/vote`, `/agree`, `/comments`, `/done`, `/tick` | vote option, agree, comment, done, tick | write | Existing |
| `POST .../together/clusters/{id}/shelf` | shelf, reason | write | Existing; extended with `review_date` (New field in the body) |
| `POST .../pause`, `.../resume` | stage held and resumed | write | Existing |
| `intents/m1_intent/.../together_shelves` (ShelfStore) | shelves per cluster, moves list | read and write | Existing; moves gain `result` and `reason` for refusals (New) |
| `intents/m2_baseline/<baseline>/governed_state.json` | six fields per measure, `mark` stated or guessed | read | Existing |
| `POST .../charter` (draft_charter) | writes the charter draft from ticked clusters | write | Existing |
| `GET` and `POST /api/intents/{id}/define/session` | `{started_at, ended_at, over_seconds, extensions: [{by, at, minutes, reason}], decisions: {made, of}}` | read and write | New |
| `intents/<id>/intent.json` | `stages`, `state`, `refs`, `outcome` pointers and the `define.*` fields below | read and write via `sh_platform/jsonfile.py` | New (01) |
| `intents/<id>/events.jsonl` | one line per start, hold, move, refusal, tick, park, extension, reopen and close (16); the record holds counts only | write | New (16) |
| `GET /api/intents/{id}` | the record cut to the viewer's tier (01) | read | New (01) |
| Process map, data sources, definitions | per 27, 28, 29, 30 | read here, shown in tabs | New (those files) |

## Fields this feature adds to the intent record

- `define.session`: `{started_at, ended_at, planned_minutes: 90, extensions: [{by, at, minutes, reason}], decisions_made, decisions_of}`.
- `define.reopened`: `[{by, at, reason}]`.
- `define.shelf_counts`: `{must, should, good_to_have, future, not_placed}` written at close, copied from the shelf store for the Pulse and the closure draft (counts only, the store stays the source).
- `define.refusals`: count of refused moves, written at close.
- In each shelf move: `result: ok|refused` and `reason|null`.
- In each Future row: `review_date` set by the organiser (v1 set it by default only).

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** clusters, names and colours (existing); keeps the stage clock and the ninety-minute clock; says when a cluster is tied; names what is open at close; drafts the charter from the ticked clusters and the closure draft's Define section. North decides nothing on a shelf. The organiser moves, ticks and closes.
- **Lens** drafts the six governed fields, definitions, process map and sources; proposes a shelf per cluster from card count and labels it a suggestion; raises ambiguity questions within the shared cap of three open questions per person across Define (A-045). Lens never marks a field confirmed. A named person confirms in the Definition tab.
- **Nira** adds Pulse lines: session invitation, "confirm your measures", "review parked group <name>" on the review date. Nira states no figure that does not trace to a record.
- Person acts: organiser moves, ticks, parks, starts and closes; business, data and source owners confirm their measures; governance lead confirms classification and who may see, and settles ambiguities; sponsor signs the charter later (09).

## Rules (visibility, time box, who may do what)

- Only the organiser moves a cluster to a shelf, ticks, parks, starts and closes. The analyst may rename, add, split and move cards. Participants vote, agree, comment. Observers read only.
- Three owner kinds apply everywhere: business owner, data owner, source owner. The governed state's "process owner" is the business owner of the process (31).
- A person gets at most three open questions across Define (process map, glossary, catalogue and governed state together), A-045.
- Affected people read content only when "affected people may read" is on or when named on a share. A draft intent is visible only to the person who started it. Dates and clocks use the company's time zone from the profile, else UTC.
- Must and Should need a governed cluster (A-054). Good to have and Future never need one.
- Future needs a reason and a review date later than today. The default of one quarter is proposed (Open question 12).
- The vote rule: Must plus Should beat the rest and reach the minimum count; organiser breaks ties. The organiser's own tick overrides the rule and is kept.
- Every move is kept with the person, time, from and to. Nothing is deleted from the wall or a shelf.
- Anonymous and sealed cards keep the v1 rules (D-013, seal). Sealed card text is never shown in a tab, a tile, the projector view or the charter draft. The organiser and the company admin never see an anonymous author. The company admin never opens cards, comments or the refusal log.
- The ninety-minute clock is a session guide, not a gate. It never locks a screen. The stage clock (07) is the real time box.
- The stage is read-only once the charter is signed. A sponsor signature after Define closes cannot be undone from here.
- Share link (11): read-only, per intent, set by the organiser, for the people it names. Shows shelves, ring, tallies and the Definition tab content the viewer may see; no drag, vote, comment box or session mode. The visitor entry stays at `POST /api/modules/m1_intent/shared/view`.
- Super admin sees existence only (title, type, state, areas, people count, dates, time box status); never clusters, cards or definitions. A company switch "titles private to the company" removes the title.
- Copy rules: no game words, no vendor or model names; agents are North, Lens, Nira. British spelling. No em dashes.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Traces to |
|---|---|
| Cards, clusters, measures, people | `together` view: `note_count`, `clusters`, `measure_codes`, `people_count` |
| Clusters per shelf | ShelfStore shelves |
| Clusters ticked, clusters tied | `ticked`, `tie` in the together view |
| Moves made, moves refused | ShelfStore moves with `result` |
| Governed clusters of all clusters | `governed` per cluster |
| Four governed percentages | `governed_state.json` per measure |
| Parked clusters and the number past their review date | Future rows `review_date` against today |
| Decisions made of clusters | `define.session.decisions_made` and `decisions_of` |
| Session minutes used and over | `define.session.started_at`, `ended_at` |
| Cards confirmed, new, sealed (A-057) | existing lean counters |

Counts are exact. Any mean, median or per-person figure shows "Fewer than five" below five records; this feature shows none. If the baseline is missing, the percentages read "Not available yet: no signed baseline".

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

| Existing | Where | Use |
|---|---|---|
| Define screen: shelves, drag and drop, park dialog, topic filter, lock dialog, counts | `ui/src/modules/m1_intent/define/DefineScreen.tsx` (1 to 323; `Shelves` from 120, `ClusterCard` from 271) | Existing, reshaped: add route under an intent, tabs on the right, session mode, dated review field, governed block |
| Lens panel with six governed cells | `ui/src/modules/m1_intent/define/LensPanel.tsx` (1 to 159) | Existing, reshaped into the "Definition" tab (content 29, 30) |
| Board: grouping, cluster add, rename, split, restore, move note | `modules/m1_intent/api/board.py` (130 to 290) and `ui/src/modules/m1_intent/board/` (`BoardScreen.tsx`, `ClusterPanel.tsx`) | Existing, reused as is |
| Together: vote, agree, comment, done, tick, shelf, pause, resume | `modules/m1_intent/api/together.py` (28 to 225), `domain/together.py` (20 to 266: `SHELVES`, `auto_decision`, `apply_auto_ticks`, `may_shelve`, `move_to_shelf`, `governed_of`, `default_review_date`) | Existing, reused; `move_to_shelf` reshaped to accept a review date and to record refusals |
| Together UI: tiles, vote buttons, tally | `ui/src/modules/m1_intent/together/ClusterCard.tsx`, `TogetherScreen.tsx` | Existing, reused for vote controls on Define tiles |
| Shelf store | `modules/m1_intent/store/together_shelves.py` (1 to 25) | Existing, reused |
| Stage timer and pause | `StageTimer` (`ui/src/modules/m1_intent/timer/`), `together.py` 201 to 225 | Existing, reused; ninety-minute session clock is New and small, sits beside it |
| Projector view | `ui/src/modules/m1_intent/wall/WallScreen.tsx` (projector state, `ds-wall--projector` class) | Reshaped: copy the pattern to Define |
| Charter draft | `modules/m1_intent/api/charter.py` (`draft_charter` from 245), `makeCharterDraft` in `ui/src/modules/m1_intent/api.ts` (356) | Existing, reused for the session close |
| Governed state | `modules/m2_baseline` governed_state, read by path (`governed_of`, `domain/together.py` 237 to 249) | Existing, reused |
| Routes and roles | `modules/m1_intent/manifest.yaml` (78 to 85), `sh_platform/route_permissions.yaml` (103 to 110) | Existing; two new routes (define session) need declaring |
| Process map and sources tabs | none | New, content in 27 and 28 |
| Ninety-minute session clock, decisions counter | none (searched `ninety`, `decisions` under `ui/src/modules/m1_intent/timer`) | New |

Rejected: building a second Define or a second vote. The only builds are the tabs shell, the session record and the review-date field.

## Not in this feature

- The content of the Definition tab (29, 30), the process map (27) and the data sources (28).
- The build-ready check itself (33); Define only feeds it and calls it at close.
- The charter's signing, closure and next steps (09).
- The wall, private rooms and the together stage up to the vote (existing, other files).
- Gap analysis (first step of Build) and the Moment of truth screen.
- Define for Brainstorm, Pulse, Problem and Decision types.

## Open questions

1. Is the ninety-minute length fixed, or set per intent by the organiser? This spec fixes 90 and records `planned_minutes`.
2. The amber and red thresholds on the session clock (15 and 5 minutes) are proposed, not justified by a record. Should they be settings, or follow the stage clock rules in 07?
3. The "Add 15 minutes" length is proposed, not justified by a record. Does it need a second person to agree, or only the organiser with a reason?
4. May the organiser reopen Define after close but before signing, and does reopening clear ticks? Proposed: yes, with a reason, and ticks stay.
5. When the cluster has measures from more than one baseline, which baseline's governed state counts for the ring? Current code reads the latest signed one.
6. A Future review date earlier than the stage end: allowed? This spec only requires "after today".
7. Should a sponsor be able to vote, given the organiser is not counted? Current manifest lets the sponsor vote; confirm.
8. Is "Hold the room" the right wording for pause in session mode, or "Pause"? Existing screens say "held".
9. The v1 route `/centre/intent/define/<session_id>` is kept as a redirect. Brief section 10 lists other spellings as wrong; may it be retired once no intent-less sessions remain?
10. Should the projector view of session mode use `/centre/intent/<id>/projector` (listed in the brief's views) instead of a mode on the define route? This spec keeps one route.
11. Confirm no per-company setting is wanted for the existing minimum vote count (`auto_min_votes`).
12. The default review date of one quarter (three calendar months) is proposed, not given by the brief. Confirm or change it.
