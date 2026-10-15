# 39. Weekly check-in entry (record key `pulse`)

Part of: Intent Centre v2. Depends on: 00-BRIEF, 01 (intent record), 02 (intent types catalogue), 05 (areas and visibility), 07 (time box and stage clock), 13 (Pulse lines), 16 (events), 24 (card model), 27 (process map), 38 (check-in setup, owns the week file). Feeds: the Weekly check-in review and triage screens (the reader), 09 (closure), 19 (centre counters), 21 (backlog).

Naming (brief section 10, ruling 3): on screen the type is "Weekly check-in". "Pulse" alone always means the daily page. The record key and the API stay `pulse`.

## Purpose (three sentences)

This is the one screen where a person says, once a week and in about two minutes, what ran, what broke and what is on their mind in their ops area. Each answer becomes a small item card with a kind (`ran`, `broke`, `thought`), and a `broke` item can carry how bad it was and a count or amount when the person knows one. North prefills "what ran" from the ops run log and the alerts the person owns, marked guessed, so the person confirms or edits rather than types; this is the screen most people will use, and it is built for a phone first.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Participant of the area (Aaron, Harvey, Katie) | Once a week while the `collect` stage is open; edits until the week closes | Their daily Pulse line "Your week for <area>" (13, row 13), or the intent page button "Answer the week" |
| Owner of a source or alert (Harvey) | Same, with North's prefill filled from the runs and alerts he owns | Same |
| Organiser and reader (Janet) | Reads the record while it fills; may also answer as a participant | "See this week's items" on the intent page |
| Sponsor (Daniel), company admin (Grace) | Read the closed week record, never anonymous authorship (D-013) | Intent page after close |
| Affected person, not a participant | Sees existence, title, purpose, stage, clock, people and the outcome once closed. Opens the week content only if the organiser switched on "affected people may read" at creation (default off) or a share names them (ruling 4) | Intent page |
| Observer | Reads what a participant reads; never writes or votes (ruling 4) | Intent page |
| North (agent) | Drafts the prefill, keeps the minutes counter honest, nudges | Entry opens; stage `collect` clock |

## Entry points (every route, link, Pulse line, button that leads here)

- Daily Pulse line (13, row 13, kind `request`): title "Your week for <area>", action "Answer three questions", href `/centre/intent/<id>/week` (replaces the `#stage` anchor for this type). A person who has started but not submitted gets the line "Finish your week" with the same href (new wording, see Open questions).
- Pulse strip nudge: Nira shows the line on the person's nudge day (open question 10).
- Intent page (`/centre/intent/<id>`, spec 04) for a Weekly check-in in `collect`: primary button "Answer the week" (participant) or "Edit my week" (after submitting).
- Phone: the same link from the Pulse line message drafted in 13 opens the entry directly, after sign-in (no extra step).
- The route always opens the current week. An earlier week opens read-only at `/centre/intent/<id>/week?week=<week_key>`. Screens C and D are views of the same route: `?view=mine` and `?view=record` (ruling 18 allows query parameters on views; no sub-route is added).
- Route family (New): `GET /api/intents/{id}/pulse/entry`, `PUT /api/intents/{id}/pulse/entry`, `POST /api/intents/{id}/pulse/entry/submit`, `GET /api/intents/{id}/pulse/prefill`, `GET /api/intents/{id}/pulse/mine`, `GET /api/intents/{id}/pulse/record`. Each takes `?week=<week_key>` (default: the current week), is declared in the module manifest and in `route_permissions.yaml` (default deny).

## Screens, element by element

### Screen A: the entry, "Weekly check-in"

Route: `/centre/intent/<id>/week`.
Layout at 1280: a single centred column 640 px wide (this form is short; a wide layout adds nothing). Header, then three question blocks stacked, then the minutes strip and the submit row. A right rail 280 px shows "Your last weeks" (a short history, Screen C) and the North panel. At 390: one column; the rail collapses below the form; each question block is a collapsed header "1 of 3: What ran well this week?" that expands when tapped, one open at a time; the submit row is pinned to the bottom, thumb height 48 px, and inputs use the phone keyboard with a "Next" key between blocks.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Header | Text | "Weekly check-in", the area name, "Week of <Monday date>", and the close line "Closes <day, date>" in the company time zone (profile, else UTC) | None | Participants | If the week is closed: "This week is closed" and the form is read-only |
| Minutes strip | Text | "About 2 minutes. You have used 0:40 so far." (live, see Counters) | None | The person | Starts at "0:00" |
| Question block 1 | Panel | "What ran well this week?" with the person's item cards of kind `ran` and an "Add" field | See "Add" below | Participant | "Nothing yet. North has drafts for you below" when a prefill exists, else "Nothing yet. One line is enough." |
| Question block 2 | Panel | "What broke or nearly broke?" with item cards of kind `broke` | See "Add" | Participant | "Nothing yet. If nothing broke, say so with 'Nothing to add here'." |
| Question block 3 | Panel | "What is on your mind?" with item cards of kind `thought` | See "Add" | Participant | "Nothing yet. A worry or an idea both fit here." |
| Add field | Text field with microphone button, placeholder "One line, in your words" | The text being typed | "Add" (or the keyboard Done key) saves one item card of the block's kind. A second item is a second line, one thought per card. The microphone turns speech into text on the device only | Author | Empty: "Add" is off |
| Item card | Card (shape of the wall card, 24 Screen B: edge bar replaced by a kind colour bar; no four quarters) | The words, a kind chip (Ran, Broke, Thought), the severity chip (`broke` only), the link chip if set, the mark chip (Stated or Guessed), and the "Anonymous" tag if set | Tap opens the card sheet (below) | Author | Not shown when none |
| Card sheet | Bottom sheet at 390, popover at 1280 | The item fields in the order: words, severity (`broke`), count or amount (`broke`), "Links to" picker, "Hide my name" tap | Each change saves at once; a "Done" button closes the sheet | Author | Fields empty as stated per row |
| Severity taps | Segmented control (3), `broke` cards only | "Slowed us", "Stopped us", "Cost money" (wording is open question 13) | Sets `severity`. Tapping the chosen one again clears it. Nothing is chosen by default; North never picks one | Author | None chosen: the card shows "How bad? (optional)" |
| Count or amount field | Number field, under the severity taps | After "Slowed us" or "Stopped us": "How many times or hours, if you know" with a unit pick (times, hours). After "Cost money": "How much, if you know" with an amount | Saves `count` (with `unit`) or `amount`. Blank stays `null`. The screen never fills a guess in here | Author | Blank and labelled "Leave empty if you do not know" |
| "Links to" picker | Search field with two tabs | Tab "Measure": the catalogue (the measures the person may see, via `/api/company/feeds`, by name and code). Tab "Process": the process map nodes the person may read (27, `GET /api/intents/{id}/processes`) | Picks one `ref`. A link is optional and one per item. Shows the chosen name as a chip with a remove "x" | Author | "Nothing linked". Tab empty: "No measures in the catalogue yet" or "No process map yet" (each with the missing thing named) |
| "Hide my name" tap | Toggle on each item, off by default | "Hide my name on this item". Under it: "Nobody can see who wrote this, not the reader, not an admin" (D-013) | Sets `anonymous` on that item only. Shown unless the area's names rule is fixed (then it shows the fixed value, disabled, with the reason) | Author | Off |
| Guessed chip | Chip on a North draft | "Guessed by North, from this week's run log" or "from your alerts" | "Yes, right" turns the mark to `stated`. Editing the words also does. "Drop" removes the draft | Author | Not shown |
| "Nothing to add here" | Button, per block | "Nothing to add here" | Writes an empty answer for the block (the kind goes into `skipped`, no item). Counts as answered for the nudge | Author | Off once the block has a card |
| Submit | Button, primary, pinned at 390 | "Send my week" first time; "Update my week" after | Writes `submitted_at` and shows "Sent. You can change it until <close day>." The person stays on the screen. If drafts are still guessed, asks once: "3 drafts are still guessed. Keep them as drafts, or confirm all?" | Participant | Off until at least one block has an item or "Nothing to add here". Line: "Answer one of the three, or say nothing to add." |
| Save as draft | Automatic | A quiet line "Saved on this device and here" after each change | Every change saves to the week record as `draft`; nothing is lost if the person leaves | Author | None |
| Error line | Text | "That did not save. Try again." and "Try again" | Repeats the save; the typed words stay on screen | Author | Not shown |
| Closed view | Panel | "This week closed on <date>. Your items are on the record." and a "See the record" button | Opens Screen D (`?view=record`) | Participant | Not shown while open |

### Screen A2: North's help (the prefill, inside Screen A)

Shown as a panel above question block 1 at 1280 (right rail) and as a one-line expandable bar at 390.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| North line | Agent line | "North drafted 3 lines from this week's runs and alerts. Keep, change, or drop each." (the number is the count of drafts from `GET .../pulse/prefill`) | None | The person | No run log or alerts for the person: "North has nothing to prefill from. Type one line, or press Nothing to add here." |
| Draft rows | List, one row per draft | The draft words, e.g. "Capital calls mailbox: 5 of 5 loads on time" or "Bank statement feed: failed its checks on Tuesday, closed Wednesday"; the evidence line "From 5 runs, 2 to 6 Oct" | "Keep" makes an item card with `mark: guessed` in the block of its kind. "Edit" opens the card sheet. "Drop" hides it for this week | The person | None |
| "Keep all" | Button | Label | Creates all drafts as guessed cards. The person still confirms each with "Yes, right"; "Send my week" keeps unconfirmed ones as guessed (see Rules) | The person | Hidden when fewer than two drafts |
| "Show North's sources" | Link | The run ids and alert ids used (never rows) | Opens a list of ids with source name and date | The person | Not shown without drafts |

### Screen B: edit before the week closes

The same Screen A. After submit the page reloads in "edit" mode: cards show "Sent" ticks, the submit button reads "Update my week", and each card has "Edit" and "Remove". A removed item is marked `withdrawn` and kept (nothing is deleted); the reader no longer sees its words, only the count of withdrawn items. After the close time the form is read-only.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| "Edit" on a card | Button | Opens the card sheet | As above. The earlier words are kept in `edits[]` and shown only to the author | Author | None |
| "Remove" on a card | Button | "Remove this item?" with "Keep" and "Remove" | "Remove" sets `state: withdrawn`; "Keep" closes the question | Author | None |
| Clock line | Text | "Closes in 2 days" (from the stage clock, 07) | None | Participants | "Closed" after close |

### Screen C: my history ("Your weeks")

Route: `/centre/intent/<id>/week?view=mine`, also the right rail on Screen A (last weeks; how many is open question 12).
Layout at 1280: a list of weeks, newest first, each expandable. At 390: one card per week, tap to expand.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Week row | List item | "Week of 29 Sep: 2 ran, 1 broke, 1 thought" and, if the reader has acted, "1 became a problem" | Expands the week's cards | The person only | "You have not answered a week yet. Your first one takes about two minutes." |
| History card | Card | The person's own words, kind, severity, link, and the fate once set ("Became a problem", "Added to the backlog", "Handled", "Nothing, because <reason>") | Fate chip opens the Problem or backlog item the person may already see (13 and 21 rules) | The person only | None |
| Anonymous items | Card tag | "Anonymous" with the words | Shown here only through the person's own pointer file (see Records); nobody else can reach the link | The person only | Not shown when none |
| Trend line | Text | "You have answered 6 of the last 8 weeks" (weeks counted from the week files) | None | The person only | "Not available yet: you need at least two past weeks" |
| Minutes line | Text | "Your last entries took 2:10, 1:50 and 3:05" | None | The person only | Hidden when none recorded |

Series and weeks are not rated (ruling 3); this screen has no rating control.

### Screen D: the record (week record items with provenance)

Route: `/centre/intent/<id>/week?view=record`. Read-only here; fates are set in triage (the reader's screen, a later spec).
Layout at 1280: a table with filters across the top. At 390: item cards, one per row, filters in a "Filter" sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Counts strip | Panel | "5 of 6 answered. 14 items: 6 ran, 5 broke, 3 thought." (example; numbers from the week file) | None | Participants, organiser, sponsor, observers; affected people only when "affected people may read" is on | "No one has answered yet. The week closes <date>." |
| Filters | Chips | Kind (Ran, Broke, Thought), Severity (3), "Linked only", "Guessed only" | Filter the list | Same | None |
| Item row | List item | Words, kind chip, severity chip, count or amount ("Not given" when blank), link chip, author name or "Anonymous", fate chip once set | Opens the item sheet | Per Rules | "Nothing in this filter." |
| Provenance chip | Chip on the row | "Stated by <name>", or "North drafted from runs 2 to 6 Oct, <name> confirmed", or "North drafted, <name> edited". Anonymous items show "Stated, name hidden" and never the run link of a named person | Opens the provenance sheet: mark, source record names (run ids, alert ids), who confirmed, when | Same | None |
| Withdrawn count | Text | "2 items withdrawn by their authors" (words hidden) | None | Reader, organiser | Hidden when 0 |
| "Open the linked measure or process" | Link | The linked catalogue entry or process node | Navigates (permission of the target applies; a process opens `/centre/intent/<initiative id>/define?tab=process-map&process=<pid>`, 27) | Same | Not shown when no link |
| Print and share | None | Not here; sharing is spec 11 | | | |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Harvey opens his phone on Friday. His Pulse shows "Your week for Fund Operations: three questions, about 2 minutes". He taps the line to `/centre/intent/<id>/week`. (Nira wrote the line from the intent record, 13.)
2. The entry opens and the minutes counter starts. North reads `warehouse/runs.json` and `build/alerts.json` for sources and alerts Harvey owns, for this week only, and puts three drafts in the North bar, each marked guessed.
3. Under "What ran well" Harvey taps "Keep" on "Capital calls mailbox: 5 of 5 loads on time". He edits "Bank statement feed" to add "after the Wednesday fix". He drops a third draft.
4. Under "What broke" he types "Custodian file came late twice", taps "Slowed us", enters 2 times, and links it to the process "Month-end reconciliation" (27).
5. Under "What is on your mind" he types a worry about a key-person risk and turns on "Hide my name" for that item only.
6. He taps "Send my week". The screen says "Sent. You can change it until Sunday." The counter shows 1:55. North updates the intent counters (answered, items) and appends an event to `intents/<id>/events.jsonl`.
7. On Saturday Harvey thinks of one more thing, reopens the line "Edit my week", adds it, taps "Update my week".
8. At the close time the stage moves to `review` (07) and the week file becomes read-only for items. Harvey leaves the screen. His "Your weeks" history shows the week; the reader's later triage shows the fate of each item on his history card. The next week opens by the clock on the next working day after the close day, even if the review is unfinished (ruling 3).

## States and transitions (table: state, who moves it, to what, what is written)

Per-person submission state (tracked in `submissions[]` per week, see Records):

| State | Who moves it | To what | What is written |
|---|---|---|---|
| `none` | The person opens the screen | `draft` | `started_at`, `opened_at` |
| `draft` | Each field change | `draft` | Item cards in `items[]`, `last_saved_at`, `active_seconds` |
| `draft` | The person taps "Send my week" | `submitted` | `submitted_at`, `minutes` (see Counters), items still marked `guessed` are kept with `mark: guessed` |
| `submitted` | The person taps "Update my week" | `submitted` | New `edits[]` in items, `updated_at` |
| `draft` or `submitted` | Stage `collect` ends (North, 07) | `closed` | `closed_at`. The form becomes read-only |
| `draft` at close | North | `closed` (counted as unsent) | Items kept but flagged `unsent: true`; see Open questions |

Item state: `active` (default), `withdrawn` (author action). Item mark: `stated` or `guessed`. A guessed item becomes `stated` when the person taps "Yes, right" or edits the words. No state is ever deleted.

Fates (`problem | backlog | handled | nothing`, each with a reason) are set in triage, not here. At the week's close, North writes `nothing` with reason "Not reviewed this week" on any `ran` or `thought` item still undecided; every `broke` item needs a fate before the week closes (ruling 3). Both are written by the review spec, not by this screen.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Use | Fields | Mark |
|---|---|---|---|
| `intents/<id>/intent.json` | Read the intent, area, stage clock, participants, `people`, share and names rule | Brief section 3 record (ruling 12: the record is `intent.json` inside the folder `intents/<id>/`) | New (spec 01); through `sh_platform/jsonfile.py` |
| `intents/<id>/weeks/<week_key>.json` (`week_key` like `2026-W42`) | Read and write the week: this feature adds `items[]` and `submissions[]` | See "Fields this feature adds" | New (file shape owned by 38) |
| `intents/<id>/events.jsonl` | Append "entry started", "entry submitted", "entry updated" (no words) | Per spec 16 | New (16) |
| `warehouse/runs.json` (live copy: `data/ardmore/warehouse/runs.json`) | Read for the prefill | `runs[].source, started, ended, on_time, rows, schema_ok, rules, owner, status` (SHAPES section 4). Counts only; row counts are quoted, rows never | Existing |
| `build/alerts.json` | Read for the prefill | `alerts[].id, kind, source, measure, owner, opened, state, at` (written by `sh_platform/build/alerts.py` `sync`) | Existing |
| `build/pipelines/<source>.json` | Read to find the sources a person owns | `source, title, owner` | Existing |
| `/api/company/feeds` | Read the catalogue for the link picker | `measures[].code, name, owner` | Existing |
| `intents/<initiative id>/processes.json` via `GET /api/intents/{id}/processes` | Read for the link picker | `processes[].id, name, status` (27); processes with `status: removed` are not offered | New (27) |
| `profile/<person>/pulse_mine.json` | The person's own pointer to their items, including anonymous ones | `{items: [{intent, week_key, item_id}]}`. Held in the person's own profile space, never in the intent record or week file | New |
| `sh_platform/profile/view.py` | Read and filter per viewer | Reused `_cards` and `SILHOUETTE` for anonymous items | Existing |

## Fields this feature adds to the intent record

On `intents/<id>/intent.json` (counts only, ruling 12; nothing here copies words):

```
pulse: {
  current: {week_key, answered: int, items: int},   # zero counts at open; read from the current week file
}
outcome (from 02, ruling 6, never null): this feature feeds items_count and responded_count at close
```

On the week file `intents/<id>/weeks/<week_key>.json`, field `items[]` (the week file's other fields are 38's):

```
items: [{
  id,
  by: name | null,                           # null when anonymous; always set at submit
  anonymous: bool,
  kind: ran|broke|thought,
  text,
  state: active|withdrawn,
  mark: stated|guessed,
  severity: slowed|stopped|cost|null,       # broke items only
  count: int|null, unit: times|hours|null,
  amount: {value: number, currency: str}|null,
  ref: {kind: measure|process, id, label, intent|null}|null,   # intent set for a process
  provenance: {drafted_by: north|null, from: [{record: "warehouse/runs.json#<run id>"|"build/alerts.json#<alert id>", at}], confirmed_by: name|null, confirmed_at|null},
  edits: [{at, text}],
  unsent: bool,
  fate: problem|backlog|handled|nothing|null, fate_reason|null, decided_by|null   # written by triage and close, not here
}]
```

Per-person submission state (new field `submissions[]` on the week file):

```
submissions: [{
  by: name,
  state: draft|submitted|closed,
  started_at, submitted_at|null, updated_at|null, closed_at|null,
  active_seconds: int, minutes: number|null,
  skipped: [ran|broke|thought]
}]
```

Anonymous items: each item carries a `by: name | null` field for provenance; the item carries no author link the reader or admin can resolve when `anonymous: true`. The mapping from person to anonymous item lives only in `profile/<person>/pulse_mine.json` (Open question 1). Counts of answered people use `submissions[].state`, never item authorship. No brief section 3 field is renamed.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** drafts the prefill when the person opens the entry for the first time in a week: runs for sources the person owns (status `ok`, grouped per source, with the on-time count) become `ran` drafts; owned alerts opened or closed in the week become `broke` drafts (kind `late`, `failed`, `outside_range`), marked guessed, with the evidence ids. North never fills severity, a count or an amount, and never writes a thought. North may group a repeat of the same wording from several people in review (not here). North keeps the clock and nudges only a person whose entry is `none` or `draft`; the nudge day is open question 10. The person acts at: Keep, Edit, Drop, Send my week.
- **Lens** is not used on this screen. When the person links to a measure or process, the picker reads the catalogue and the process map (27); Lens writes nothing here.
- **Nira** writes the Pulse line (13, row 13) while the person has no submitted entry and the stage is open, and the "Finish your week" line when the state is `draft`. When the entry is `submitted` the line is removed. Nira reads only the entry state, never the words.
- Agents never sign. The person sends the week; North never sends for them.

## Rules (visibility, time box, who may do what)

- Only a participant of the intent (the area's people, 06) may enter. The organiser who is also a participant enters as a participant. An affected person who is not a participant may not enter; they see the closed week outcome, and the week content only under ruling 4. An observer reads what a participant reads and never writes.
- A person sees and edits only their own submission. Others' submissions are not shown to a participant at all while `collect` is open (no counts of who has answered, only "5 of 6 answered" from the organiser view in Screen D). This matches the privacy of the v1 wall (private until the rooms close).
- Each item is anonymous or named on its own. Anonymous items hide authorship from the reader, organiser, sponsor, company admin and super admin (D-013). The area's names rule can fix it to "named" or "anonymous"; the item toggle then shows the fixed value.
- The super admin sees existence only (ruling 5), never entries. The company admin sees existence and outcome, never anonymous authorship.
- A draft intent is visible only to the person who started it (ruling 14).
- Severity is the person's own judgement and may be left empty. A count or amount is shown only if typed; North and the reader may not fill it. A missing count shows "Not given", never zero.
- A guessed item that the person leaves unconfirmed at "Send my week" is stored as `guessed` and shown to the reader with the guessed mark; the person is asked once. Agents never turn guessed into stated.
- Editing is allowed until `collect` closes. After that the entry is read-only. A person may not add an item after close (open question 4).
- The time box is the stage clock (07): `collect` is 3 working days by default (02); the screen shows the actual close time from the record, in the company time zone from the profile, else UTC. Extending is the organiser's act, not this screen's.
- Series and weeks are not rated (ruling 3). No per-person figure exists anywhere (ruling 15).
- Health and pay information: the card sheet has the seal tap of the wall card (24) only where the area allows sealed items; default off, open question 5.
- Sensitive text: the item text is never sent anywhere except through the egress gateway when North drafts, and then names are tokenised (D-007).
- No game words; British spelling; every number traces to a record or reads "Not available yet".

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Source | Where shown |
|---|---|---|
| Minutes per submission (target 2:00) | `submissions[].minutes` = `active_seconds` / 60 at `submitted_at`, from the week file. `active_seconds` is the sum of intervals between `opened_at` and each save in which the screen was in view, capped per gap (the cap is open question 2) | Minutes strip, history (own), Screen D counts strip (median only) |
| Median minutes this week | Median of `submissions[].minutes` across submissions with `state` in {submitted, closed}; "Fewer than five" below five (ruling 8) | Intent page, 19 |
| Submissions of participants | Count of `submissions[].state in {submitted, closed}` over `people.participants` (exact) | Screen D, Pulse line detail (13) |
| Items by kind | Count of `items[].kind` with `state: active` (exact) | Screen D |
| Broke items by severity | Count of `items[].severity` | Screen D |
| Broke items with a count or amount | Count where `count` or `amount` is not null | Screen D |
| Items linked to a measure or process | Count where `ref` is not null | Screen D, 19 |
| Guessed share | Items with `mark: guessed` over all items; "Not available yet" with no items | Screen D |
| Drafts kept, edited, dropped | Counts from `provenance` and `edits` | Screen D (organiser) |
| Weeks answered (own) | Count of the person's submissions with state `submitted` or `closed` in the window (open question 12) | Screen C |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `graft ask "ops run log reader runs.json" --source`, `graft ask "wall card form"`, plus reading `docs/plan/SHAPES.md` section 4 and specs 02, 13, 24, 27 and 38. Paths below were checked to exist in this repo on 7 Oct 2026.

| Existing file | What it gives | Decision |
|---|---|---|
| `ui/src/modules/m1_intent/wall/Card.tsx` (109 lines: `WallCard`, `Card`, left edge, draft and sealed variants), `wall.css` (127 lines), `copy.ts` (85 lines) | The card component, draft chip, seal silhouette, anonymous foot | Reshaped: reuse the card shell, draft and silhouette variants; replace the four-segment edge with a one-colour kind bar (an item has one answer, not four quarters); a copy file for this screen in the style of `copy.ts`. Not rebuilt. |
| `ui/src/modules/m1_intent/wall/NorthPanel.tsx` (144 lines) | North's side panel and its Keep/Edit pattern | Reshaped: same panel, new draft rows. |
| `ui/src/modules/m1_intent/wall/WallScreen.tsx` (184 lines), `Lane.tsx` (24 lines) | Wall layout and lane switcher at 390 | Reshaped only for the one-block-at-a-time pattern at 390; the lanes themselves are not used. |
| `sh_platform/build/ops.py` lines 72 to 122 (`build` at 72, `_build_open` at 77) | Reads runs, joins pipelines, owners, alerts and range breaks; cached per viewer and day | Reuse as reader: add a thin `owned_week(plane, person, week)` that filters `runs.json` by `owner` and week and reads owned alerts. Does not re-derive. |
| `sh_platform/build/alerts.py` (49 lines: `_read` at 16, `sync` at 25) | Stored alerts with `owner`, `state`, `opened`, `at` | Reused as reader; `at` gives the close time of an acknowledged or closed alert. |
| `data/ardmore/warehouse/runs.json` | Run log per SHAPES section 4 (a bare `warehouse/runs.json` does not exist at the repo root; the path is per company plane) | Read only; counts only. |
| `ui/src/pages/OpsPage.tsx` (190 lines; `nameOf` at 104, `ownerOf` at 105) | Plain-language names for sources, owner lookup by pipeline contract | Copy the two lookups for the prefill wording. |
| `sh_platform/jsonfile.py` (`lock_for` at 19, `read_json_strict` at 25, `write_json_atomic` at 41) | Safe file write | Reused unchanged. |
| `sh_platform/profile/view.py` (`SILHOUETTE` at 167, `_cards` at 171) | Anonymous and sealed rules | Reused unchanged; no second rule. |
| `/api/company/feeds` (`measures[].code, owner`) | Catalogue for the link picker | Reused unchanged. |
| `docs/plan/SHAPES.md` (55 lines) | Run log and alert shapes | Read only. |
| Spec 27 `intents/<id>/processes.json` and `GET /api/intents/{id}/processes` | Process nodes for the link picker | Reused as the reader; this screen writes nothing there. Spec 27's note on `sh_platform/process_record.py` applies: that file is a session outcome link, not the process map, and is not used here. |
| 13 (Pulse lines row 13), 07 (stage clock), 38 (week file) | Entry line, close time, week file shape | Reused; this spec only changes the href and adds `entries[]`. |
| Genuinely new | The entry form, the item record with severity, count or amount and ref, the minutes counter, the person's own history and pointer file | New, kept to one file of `modules/m1_intent` plus the screens. |

## Not in this feature

- The reader's review and triage of items, fates and reasons (a later Weekly check-in spec).
- Grouping repeats across people (North, review stage).
- Creating the recurring series and its start questions (38, 03).
- Sharing the week record (11) and the closure draft (09).
- Notifications by email or chat beyond the Pulse line (13).
- Any severity or amount that North estimates; any comparison of people; any rating of a series or a week.
- Free-form attachments, photos or voice files (the microphone only turns speech into text on the device).
- Scoring or ranking a person by answers or minutes.

## Open questions

1. How does a person edit an anonymous item without the system holding a name-to-item link? Proposed here: a pointer file in the person's own profile. That is a link the person's own account holds, which D-013 may not allow. Option: keep an unreadable per-item edit token on the person's device only, so a lost device means the item cannot be edited. Nitin to choose.
2. Minutes: what idle gap counts as break? Proposed 60 seconds per gap. Is the target "two minutes" a median or a limit for every entry? A slow person may feel judged; the screen shows minutes only to the person and a median to others (fewer than five entries shows "Fewer than five").
3. Week file shape: ruling 17 specifies flat `items[]` with `kind: ran|broke|thought`, which this spec now follows. Spec 38 should align with this structure.
4. A person who misses the close: can they add a late entry, and does the reader see it? Proposed none, plus the reader may add on a person's behalf only with their word. A missed week opens no empty entry (02, open question 5).
5. May an item be sealed, as on the wall (24)? Pulse items about people or pay are plausible. Proposed: seal is offered only if the area enables it; otherwise people use "Hide my name" and a plain wording.
6. Should the prefill also use closed alerts as a `ran` item ("fixed on Wednesday")? This spec puts runs under `ran` and owned alerts that were late, failed or outside range under `broke` drafts. Nitin to confirm.
7. How is a person tied to an owned source or alert? `owner` in `runs.json`, the pipeline contract and `alerts.json` is a name, not an id (for example "Harvey Rowley"). The match is by name today; a person id is needed once names collide.
8. Currency for the amount field. Proposed the company's base currency from the company profile; no conversion. The profile field must be named in 01.
9. The count unit (times, hours) is chosen here to avoid free text. Is "number of people affected" also wanted?
10. Nudge day: the start question gives the close day, not a nudge day. Proposed one day before close, one nudge only; not decided.
11. Unsent drafts at close (`unsent: true`): does the reader see them? Proposed no, but the count "2 drafts not sent" shows to the person only.
12. How many past weeks the rail and the trend line cover (this draft shows four and eight). No figure was given; Nitin to set.
13. The three severity names ("Slowed us", "Stopped us", "Cost money") are proposed wording, not from the brief or 02. Confirm or replace.
14. Process links across intents: the Weekly check-in is a different intent from the Initiative that owns a process map (27). Which initiatives' maps may the person pick from (all they may open, or only maps tagged to the same area)? Proposed: all they may open.
15. The 390 layout puts one question open at a time. A test with six real phone users is needed before the two-minute target is claimed; until then the screen says "About 2 minutes" as a target, not a measured fact.
16. Screens C and D are `?view=mine` and `?view=record` on `/centre/intent/<id>/week`, because ruling 1 lists `week` as the only view name for this type. If sub-routes are preferred, ruling 1 needs a request. 38 uses `/week/<week_key>` for the entry; this spec follows ruling 1 and uses `?week=<week_key>`.
