# 21. Backlog

Part of: Intent Centre v2. Depends on: 00-BRIEF (intent record, visibility rule), 01 (intent record and lifecycle), 02 (intent types catalogue), 03 (create intent chooser, start questions), 04 (Intent Centre home), 09 (closure and sign-off, `closure.next[]`), the weekly check-in review stage in 02 and 38, and 05 (areas). Feeds: 04 (backlog count chip on the home page), 09 (target of "Add to backlog"), the daily Pulse page lines (review reminder), the Initiative, Brainstorm, Problem and Decision start flows (22, 35, 41, 43: pre-filled start questions).

## Purpose (three sentences)

The backlog is where an idea from a brainstorm or an item from a weekly check-in waits until someone opens an intent for it. It keeps each item with where it came from, who raised it, why it matters and when someone will look at it again, so nothing is lost and nothing is forgotten. A lead can open an intent from an item in one click, merge two items that say the same thing, park an item with a reason and a review date (set by the same rule as the Future shelf), or drop it with a reason; nothing is ever deleted.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Area lead (the person in `areas.<id>.lead` of the area record, see Open question 1) | Weekly, and when North reminds them on their Pulse | Pulse line "Two backlog items in Operations are due for review" |
| Organiser of the source intent (for example Janet, who ran the brainstorm) | After closing an intent whose next list said "Add to backlog" | Link on the closure screen "See it in the backlog" |
| Person in the area (for example Aaron, Katie, Harvey) | When they want to say "I feel this" about an item, or check what happened to something they raised | Pulse line, or the Backlog link on the Intent Centre home page |
| Company admin | Checking that nothing is stuck, resolving a missing lead | Opens `/centre/intent/backlog` and picks "Company-wide" |
| Super admin | Never opens content | Sees only the total item count per company, read through the kernel on request (00-BRIEF section 10, ruling 5) |

## Entry points (every route, link, Pulse line, button that leads here)

- Intent Centre home (04): the "Backlog" link in the top bar, showing the count of open items in the viewer's areas. Opens `/centre/intent/backlog`.
- Closure screen (09), next list: after "Add to backlog" is confirmed and the intent is closed, North writes the item and the row shows "In the backlog" linking to `/centre/intent/backlog?item=<id>`.
- Weekly check-in review (02, 38): the fate "backlog" on a check-in item creates the item when the week closes; the week record row links to it.
- Daily Pulse page (Nira line): "Backlog items due for review" links to `/centre/intent/backlog?area=<area>&due=1`.
- A source intent's page: the "Came from here" panel lists the backlog items it produced, each linking to `/centre/intent/backlog?item=<id>`.
- Deep link from a merged or opened item: `/centre/intent/backlog?item=<id>` opens the card drawer on top of the list.

## Screens, element by element

### Screen A. Backlog list

Route: `/centre/intent/backlog` (query: `area`, `kind`, `status`, `due`, `item`).

Layout at 1280: top bar (title, area switcher, kind chips, status chips, counters strip); left rail with the area list (one row per area the viewer may see, plus "Company-wide", each with its open count); main column with item cards in a single column sorted by review date, soonest first; the card drawer opens as a right-hand panel over the main column. Layout at 390: the left rail collapses into the area switcher (a dropdown); chips scroll sideways; cards stack full width; the drawer opens as a full-screen sheet with a Back button; the counters strip collapses to one line (for example "3 areas, 14 open, oldest 41 days", illustrative) with a "More" toggle.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Title "Backlog" | Heading | "Backlog" and one line: "Ideas and items waiting for someone to open an intent." | None | Everyone who may open the centre | Same |
| Area switcher / left rail row | List | Area name (profile areas section, file 05) and open count (items with `status = open` in that area). First row "Company-wide" (items with no single area) | Filters the list; writes `area` to the URL | Viewer sees only areas they are tagged to; company admin sees all | "You are not tagged to an area yet. Ask your company admin." |
| Kind chips | Chip group (multi-select) | Idea, Ops problem, Request, each with a count of items of that `kind` | Toggles the filter | Everyone | A kind with zero items is dimmed and still selectable |
| Status chips | Chip group (single select) | Open (default), Parked, Became an intent, Dropped, Merged | Filters; "Became an intent", "Dropped" and "Merged" are history views | Everyone | "Nothing here yet." |
| "Due for review" toggle | Toggle | Count of items with `review_date` today or earlier | Filters to due items | Lead of the area and company admin; others do not see the toggle | Off and dimmed with "None due" |
| Counters strip | Panel | Items per area, oldest age, items that became intents, each read as named under "Counters and measures" (from `items[].status`, `items[].area`, `items[].raised_at`) | "Open the numbers" scrolls to Screen C | Lead and company admin; people in the area see the items-per-area number only | "Not available yet: no backlog items recorded." |
| Item card | List item | Title, area chip, kind chip, source link ("From: Packing-list rethink, brainstorm"), raised by and date, North's "why it matters" line, "I feel this" count (from `items[].taps`), review date, status | Click anywhere except buttons opens Screen B | Anyone tagged to the item's area; company admin; the source's organiser | See Screen A empty state below |
| "I feel this" button on card | Button (toggle) | Hand icon, the word "I feel this", and the count | Adds or removes the viewer's tap; one per person per item | People tagged to the item's area. Not the person who raised it (their raise counts as the first) | Count shows 1 (the raiser) |
| Review date chip on card | Chip | "Review 14 Oct" or "Review overdue by 3 days" (warn colour with the words, never colour alone) | None | Everyone who sees the card | "No review date set" shown with warn colour (a parked or open item always has one, so this means a record fault) |
| "Open an intent" button on card | Button (primary) | Label "Open an intent" | Opens the Open dialog (Screen D) | Actors named in Rules | Hidden for others; they see "Ask <lead name>" as muted text |
| Empty list | Panel | "Nothing is waiting in <area>. Ideas from brainstorms and weekly check-in items land here." with a link "Start a brainstorm" to `/centre/intent/new?type=brainstorm` | Link | Everyone | This is the empty state |

### Screen B. Item card drawer

Route: `/centre/intent/backlog?item=<id>`.

Layout at 1280: right panel, 480 px wide, over the list. Header (title, chips), body (why it matters, source, thinking kept, history), footer (actions). Layout at 390: full-screen sheet; the footer actions become a sticky bar with the first action visible and the rest under "More".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Title | Field (text) | The item title, editable by the actors in Rules until the item is no longer open | Saves on blur; written to history | Anyone who sees the card; edit only by actors | Required; "A title is needed." |
| "Why it matters" | Agent line (North draft) | One line drafted by North from the source: for example "Harvey's team re-key the same custody list four times a month; ops sees it as the biggest time loss in the area." Tag "Drafted by North, edited by <name>" once changed | "Edit" turns it into a field; a person's edit is never overwritten by a later draft | Everyone who sees the card; edit by actors | "North could not draft this from the source. Write one line." |
| "Where it came from" | Link panel | Source intent title, type chip, date closed, and for a check-in item the week ("Week of 28 Sep, Operations"). Link opens the source intent (if the viewer may open it) | Click opens `/centre/intent/<id>` | Everyone sees the title and type; link opens only if the viewer may open the source content (00-BRIEF section 4) | "Source not available: <reason>" (for example the intent is sealed to participants) |
| Source quote | Text | The original words from the source, shown with the name of who said it, or "Anonymous" for anonymous material (never unmasked) | None | Only those who may open the source content | "The original words are in the source intent." |
| Raised by, when, area, kind | Text rows | Name (or "Anonymous" if the source was anonymous), date, area chips, kind | Area and kind editable by actors | Everyone who sees the card | None |
| "I feel this" list | List | Count and, to the lead and company admin only, names of the people who tapped | None | Count: everyone in the area. Names: lead, company admin, never for taps made anonymously | "No one has tapped yet." |
| Review date | Field (date) | The date North will remind the lead | Actor changes the date; written to history (whether a long move needs a reason is Open question 11) | Edit by actors | "Set a review date." (required to leave the field) |
| History | List | Every change: created, edited, merged, parked, dropped, opened, review reminders sent, who and when | None | Actors and company admin; people in the area see only status changes | "No changes yet." |
| Related items | List | Items merged into this one (each with its original title) and items it was merged into | Click opens that item | Everyone who sees the card | "Nothing merged." |
| "Open an intent" | Button (primary) | See Screen D | Opens Screen D | Actors | Hidden for others |
| "Merge with another item" | Button | Opens a picker of other open items in the same area (search by title) | Opens Screen E | Actors | Disabled with "No other open item in this area." |
| "Park" | Button | Opens the park form (Screen F, reuses the Future shelf park form) | Opens Screen F | Actors | Hidden if the item is already parked (the Review date field above changes the date) |
| "Drop" | Button (secondary, warn text) | Opens the drop form | Opens Screen F with the drop reason | Actors | Hidden if the item is dropped |
| "Bring back" | Button | On a parked or dropped item: sets status to open, keeps the history | Writes status `open`, history line | Actors | Only shown for parked and dropped items |
| Close drawer / Back | Button | Cross at 1280, Back at 390 | Closes the drawer, removes `item` from the URL | Everyone who sees the card | None |
| "I feel this" button in drawer | Button (toggle) | Same control and count as on the card | Same as on the card | People tagged to the area, not the raiser | Count shows 1 |
| "Looks like the same thing" strip | Agent line (North suggestion) | "Looks like the same thing as <title>." with buttons "Merge with <title>" and "Not the same" | "Merge with" opens Screen E with that item chosen; "Not the same" hides the strip for this pair and writes a history line | Actors | Hidden when North finds no close item |

### Screen D. Open an intent from an item (dialog)

Route: dialog over Screen A or B, `/centre/intent/backlog?item=<id>&open=1`.

Layout at 1280: centred 640 px dialog. At 390: full-screen sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Type picker | Chip group (single) | Initiative, Brainstorm, Problem, Decision. North's suggestion has the tag "North suggests". A weekly check-in is never offered (it is recurring, not made from an item) | Choosing a type re-fills the start questions | Actors | North suggests by kind: idea to Brainstorm, ops problem to Problem, request to Initiative. A person changes it freely |
| Pre-filled start questions | Field list | The start questions of the chosen type (per-type file: 22 Initiative, 35 Brainstorm, 41 Problem, 43 Decision), with the ones North can answer from the item already filled and marked "From the backlog item": title, purpose, areas, organiser (the person opening it), people (the raiser as participant, if they agree) | Editable; Next continues to the per-type start flow (22, 35, 41 or 43) at the first unanswered question | Actors | A question North cannot fill stays empty and is asked in the normal flow |
| "Raised by" notice | Text | "Janet raised this. She will be asked to join, not added." | None | Actors | None |
| "Open it" button | Button (primary) | Label "Open it" | Creates the intent in state `draft` (visible only to the person who opened it, ruling 14) with `links.from = source intent id` and `backlog_ref = item id`; item status becomes `became_intent`; opens `/centre/intent/<new id>`; the person continues the start questions at `/centre/intent/new?type=<type>&from=<source intent id>` (how `backlog_ref` travels is Open question 12) | Actors | Disabled until the required start questions for the type are answered |
| "Cancel" | Button | Label "Cancel" | Closes the dialog; the item is unchanged | Actors | None |

### Screen E. Merge two items (dialog)

Layout at 1280: 640 px dialog with two columns (this item, the other). At 390: stacked, this item above.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Other item picker | List with search | Open items in the same area (and Company-wide items), title and source | Choose one | Actors | "No other open item in this area." |
| Side by side | Panel | Both titles, both "why it matters" lines, both sources, both counts of "I feel this" | None | Actors | None |
| "Keep this title" / "Keep the other title" | Radio | Which item survives | Choose | Actors | One must be chosen |
| "Combined why it matters" | Agent line + field | North's draft combining both lines in one | Edit allowed | Actors | "North could not combine them. Write one line." |
| "Merge" button | Button (primary) | Label "Merge" | The merged item keeps both sources, adds the taps of both (one per person, no double counting), keeps the earlier review date; the other item becomes status `merged` pointing at the survivor | Actors | Disabled until a title is chosen |
| "Cancel" | Button | Label "Cancel" | Closes | Actors | None |

### Screen F. Park or drop form (dialog)

This is the Future shelf form from the Define screen, reused (see Reuse check). Layout at 1280: 480 px dialog. At 390: bottom sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Title | Heading | "Park <title>" or "Drop <title>" | None | Actors | None |
| Reason | Field (text, required) | "Why are you parking this?" or "Why are you dropping this?" | Required; length limit is the Define form's reason limit | Actors | "Please say why this is parked for later." (the Define form's message, with "dropped" for a drop) |
| Review date (park only) | Field (date) | Default today plus one quarter, shown as "North will remind <lead> on <date>" | Editable; any future date | Actors | Default is always filled |
| "Park it" / "Drop it" | Button (primary) | Labels as shown | Writes status, reason, review date, history; closes the dialog | Actors | Disabled until the reason is filled |
| "Cancel" | Button | Label "Cancel" | Closes | Actors | None |
| Footer line | Text | "Nothing is deleted. You can bring it back." | None | Actors | None |

### Screen C. Backlog numbers

Route: `/centre/intent/backlog#numbers`. Layout at 1280: three tiles in a row (items per area, age, became intents). At 390: tiles stack. Visible to the lead (own areas) and company admin (all).

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Items per area tile | Panel | Open, parked and due counts per area (from `items[].status`, `items[].area`, `items[].review_date`) | None; an area name sets the list filter | Lead (own areas), company admin | "Not available yet: no backlog items recorded." |
| Age tile | Panel | Oldest open item age in days; median only with five or more open items in the area, else "Fewer than five" (from `items[].raised_at`) | None | Lead, company admin | "Not available yet: no backlog items recorded." |
| Became intents tile | Panel | Count of items with `status = became_intent`; share and days-to-open follow the thresholds in "Counters" (from `items[].status`, `items[].opened_intent`) | A count opens the list with the "Became an intent" chip | Lead, company admin | "Not available yet: no backlog items recorded." |
| Back to list link | Link | "Back to the backlog" | Goes to `/centre/intent/backlog` | Lead, company admin | None |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet closes a brainstorm. In "What happens next" she picks "Add to backlog" for the idea "One custody checklist for all four funds" and gives the reason. (Person acts.)
2. North, after the close is written, drafts the item: title from the idea, kind Idea, area Operations from the intent's areas, "why it matters" from the thinking kept, review date default (one quarter ahead). North writes the item to `intents/backlog.json` (company plane). (Agent drafts, writes after closure.)
3. Nira adds a line to Harvey's Pulse (Harvey is the area lead, `areas.<operations>.lead`): "New in the backlog: One custody checklist. Raised by Janet." (Agent.)
4. Aaron opens `/centre/intent/backlog`, sees the card in Operations, taps "I feel this". The count becomes 2. (Person.)
5. Three weeks later a weekly check-in closes with an item "Custody list is re-keyed every month" (kind `broke`) given the fate "backlog" and a reason. North sees it matches the first item (same area, similar words) and shows a "Looks like the same thing" strip on the new card: "Merge with One custody checklist?" It never merges by itself. (Agent suggests.)
6. Harvey opens the new card, presses "Merge with another item", sees both side by side, keeps the first title, edits the combined line and presses "Merge". (Person acts.)
7. At the review date North puts a line on Harvey's Pulse: "Review: One custody checklist, 5 people feel this. Open an intent, park it again, or drop it." (Agent.)
8. Harvey opens the card and presses "Open an intent". North suggests Initiative, pre-fills title, purpose, area Operations, and Janet as a participant to invite. Harvey adds the sponsor (Daniel) and presses "Open it". (Person acts.)
9. The card now reads "Became an intent" with a link to the new initiative. The new initiative has `links.from` pointing at the brainstorm. Harvey leaves. (Agent writes links both ways.)

## States and transitions (table: state, who moves it, to what, what is written)

Item status is separate from the intent `state`. Statuses: `open`, `parked`, `became_intent`, `merged`, `dropped`.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | North, after the source intent closes (from `closure.next[]` kind `backlog` or a weekly check-in item fate `backlog`) | `open` | New item with `source`, `raised_by`, `raised_at`, `area`, `kind`, North's draft `why_it_matters`, `review_date` default, `taps: [raiser]`, history line "Created" |
| `open` | Actor presses "Open it" (Screen D) | `became_intent` | `opened_intent` (new intent id), `status`, history line; the new intent gets `links.from` and `backlog_ref` |
| `open` | Actor presses "Park it" with reason and review date | `parked` | `status`, `parked: {reason, by, at, review_date}`, history line |
| `open` | Actor presses "Drop it" with reason | `dropped` | `dropped: {reason, by, at}`, history line |
| `open` | Actor presses "Merge" (this item is the one that goes away) | `merged` | `merged_into` (surviving id), history line on both items; the survivor adds sources, taps and the combined line |
| `parked` | North, at the review date | `parked` (reminder sent) | `reminded_at` appended, history line "Reminder sent to <lead>" |
| `parked` | Actor presses "Bring back" | `open` | `status`, history line; `parked` block kept in history |
| `parked` | Actor presses "Open it" | `became_intent` | As above |
| `parked` | Actor presses "Drop it" | `dropped` | As above |
| `dropped` | Actor presses "Bring back" (company admin or lead only) | `open` | `status`, history line |
| `became_intent`, `merged` | None | Final | Read-only; the history stays |

If the new intent opened from an item is cancelled, North does not return the item to `open` by itself. It proposes "Bring the backlog item back?" on the lead's Pulse and a person picks.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Status |
|---|---|---|
| `intents/backlog.json` in the company plane (through `sh_platform/jsonfile.py`, filtered per viewer with `sh_platform/profile/view.py`) | `{items: [{id, title, kind: idea\|ops_problem\|request, area (area id from file 05, or null for Company-wide), source: {intent_id, type, stage_ref\|null, week_key\|null, week_item_id\|null}, raised_by (account id or "anonymous"), raised_at, why_it_matters: {text, drafted_by: "north", edited_by\|null, edited_at\|null}, source_quote, taps: [{by, at}], review_date, status, parked: {...}\|null, dropped: {...}\|null, merged_into\|null, merged_from: [ids], opened_intent\|null, reminded_at: [], history: [{at, by, action, note}]}]}` | New |
| `intents/<id>/intent.json` of a source intent (01, ruling 12) | Read: `closure.next[]` (kind `backlog`), people, areas, visibility | Existing record, shape from 01 |
| `intents/<id>/weeks/<week_key>.json` of a weekly check-in (38) | Read: items with fate `backlog`, with kind and reason | Existing from 38 |
| `intents/<id>/intent.json` of an intent opened from an item | Written: `links.from`, plus `backlog_ref` | Existing record, one field added (see below) |
| `context/profile/profile.json` areas section and `people.<pid>.areas` (05; `GET /api/company/areas`) | Read: area ids and names, who is tagged to which area, and `areas.<id>.lead` (a person id) | Areas and tags New in 05; the `lead` cell is New and not yet in 05 (Open question 1) |
| Start questions of a type (22, 35, 41, 43) | Read: question ids and field names to pre-fill | Existing from the per-type files |
| Nira Pulse lines (`sh_platform/pulse/lines.py`) | Written: review-due and new-item lines | Existing file, three new templates |
| Run log | Written: each North draft and each actor action | Existing |
| Route `GET /api/intents/backlog`, `GET /api/intents/backlog/<id>` | Read, filtered per viewer | New |
| Routes `POST /api/intents/backlog/<id>/open`, `/merge`, `/park`, `/drop`, `/bring-back`, `/tap`, `PATCH /api/intents/backlog/<id>` | Write, each declared in the manifest with its role rule (default deny) | New |

## Fields this feature adds to the intent record

| Field | Shape | Meaning |
|---|---|---|
| `backlog_ref` | `item id \| null` | The backlog item this intent was opened from. It is not one of the brief's section 3 fields, and none of those is renamed. Set at creation by Screen D. The item holds the reverse link in `opened_intent`. |

Nothing else is added. The intent record never copies the item; it points at it.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** drafts four things. (1) The item itself at the close of a source intent: title, kind, area, "why it matters" in one line from the source records, and a default review date. The organiser or lead edits; North never overwrites a person's edit. (2) A "looks like the same thing" suggestion when a new item sits close to an open one in the same area; North only suggests and a person merges. (3) A type suggestion and pre-filled start answers when an actor presses "Open an intent". (4) The review reminder at the review date (see below). North never opens, parks, drops, merges or deletes. A named person acts each time.
- **Lens** is not used in this feature.
- **Nira** writes the Pulse lines: "New in the backlog" to the area lead when an item arrives; "Review due" at the review date (all are daily Pulse lines); "Backlog item opened as an intent" to the raiser. Nira does not count taps into a score or rank.

**Review reminder.** At a set hour on the review date (company time zone from the profile, else UTC; the hour is Open question 2), North puts one line on the area lead's Pulse: "Review: <title>. <n> people feel this. Open an intent, park it again, or drop it." The line links to `/centre/intent/backlog?item=<id>`. If not acted on, North repeats it once a week and tells the company admin after four weeks without action. The hour, the repeat and the escalation are proposals (Open question 2). If `areas.<id>.lead` is empty, the line goes to the company admin with "No lead named for <area>."

## Rules (visibility, time box, who may do each)

**Who may act.** The "actors" are: the organiser of the source intent, the named lead of the item's area, and the company admin. Any actor may open an intent, merge, park, drop, bring back and edit. Company-wide items (no single area) are actioned by the source organiser or the company admin.

| Action | Organiser of the source | Area lead | Company admin | Person in the area | Super admin |
|---|---|---|---|---|---|
| See the card | Yes | Yes | Yes | Yes (their areas) | Counters only |
| "I feel this" | No (raise counts) | Yes | Yes | Yes | No |
| Edit title, kind, area, line | Yes | Yes | Yes | No | No |
| Open an intent | Yes | Yes | Yes | No | No |
| Merge | Yes | Yes | Yes | No | No |
| Park | Yes | Yes | Yes | No | No |
| Drop | Yes | Yes | Yes | No | No |
| Bring back | Yes | Yes | Yes | No | No |

- **No deletion.** There is no delete route. Dropped and merged items stay with their history and appear under the status chips.
- **Reasons are required** for park and drop. A reason is plain text, kept in the history, and visible to actors and the company admin. People in the area see the status and the reason line for dropped and parked items (so they know what happened to something they felt).
- **Anonymous material.** If the source was anonymous, the item shows "Anonymous" and the source quote is never unmasked, even to the company admin (00-BRIEF section 4, D-013). Taps from an anonymous source count but have no name.
- **Visibility.** A person sees an item if they are tagged to its area (`people.<pid>.areas`, 05), if they are the source organiser, or if they are the company admin. Opening the source content follows the source intent's own rules; the card never leaks sealed or participant-only text to someone who could not open the source. The card's quote is shown only to those who may open the source.
- **Tap rule.** One tap per person per item. A tap is a signal, never a vote that decides anything. The count has no threshold that triggers an action.
- **Review date.** An open or parked item always has one. The default is today plus one quarter, the same rule the Define screen uses for the Future shelf.
- **Time box.** The backlog has no time box of its own. Intents opened from it carry their own type's time box from the day they open.
- **Agents never decide.** North drafts and reminds; a named person acts.

## Counters and measures of this feature (numbers only, each traced to a record)

All counted from `intents/backlog.json` through the viewer's visibility filter. Where nothing is recorded the tile says "Not available yet: no backlog items recorded."

| Counter | Calculation | Source | Shown to |
|---|---|---|---|
| Open items per area | Count of items with `status = open` grouped by `area` (area id) | `items[].status`, `items[].area` | Lead (own areas), company admin (all), people in the area (own areas, count only) |
| Parked items per area | Count with `status = parked` by `area` | same | Lead, company admin |
| Age of the oldest open item | Today minus the earliest `raised_at` among open items, in days, per area | `items[].raised_at` | Lead, company admin |
| Median age of open items | Median of (today minus `raised_at`) for open items per area; shown only if there are five or more open items in the area, otherwise "Fewer than five" | `items[].raised_at` | Lead, company admin |
| Items due for review | Count with `review_date <= today` and status open or parked | `items[].review_date` | Lead, company admin |
| Items that became intents | Count with `status = became_intent`, and as a share of all items ever created in the area (shown when the area has five or more items, else "Fewer than five") | `items[].status`, `items[].opened_intent` | Lead, company admin |
| Days from raised to opened | For items that became intents: `opened_intent` creation date minus `raised_at`, median, shown when five or more such items exist, else "Fewer than five" | `items[].raised_at`, the opened intent's `created_at` | Company admin |
| Dropped and merged counts | Count with `status = dropped` or `merged` | `items[].status` | Company admin |

Super admin sees only the total count of items per company, read through the kernel (ruling 5), never titles or area names. Dates and ages use the company time zone from the profile, else UTC. No counter ranks people or teams.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `graft ask "future shelf reason review date"`, a grep for `A-058`, `Future shelf`, `parked`, `review_date`, and a look through `ui/src/modules/m1_intent/define/` and `modules/m1_intent/`. The Define screen, and so the Future shelf, lives at `ui/src/modules/m1_intent/define/` (confirmed). All paths below were checked and exist.

| What exists | Where | Decision |
|---|---|---|
| Park form: reason field (required), default review date "today plus three months", Save and Cancel, dialog with aria label, the message "Please give a reason" | `ui/src/modules/m1_intent/define/DefineScreen.tsx` (lines 15 to 16 for `reviewDate`, 166 for the reason check, 189 to 198 for the park form) and `define/copy.ts` (lines 57 to 62: `futureTitle`, `futureReason`, `futureReview`, `futureSave`, `futureCancel`, `futureNeed`) | Reuse as is. Screen F is this form with the title, the "need a reason" message and button labels as props. Extract the form to one shared component taking `{title, reasonLabel, showReview, saveLabel, needMessage}` and use it from both Define and the backlog. Do not build a second form. |
| Parked card note line "Reason: <reason>" (class `df-cluster__note`) and the shelf footer "Nothing is thrown away. Each keeps its reason and a review date." | `DefineScreen.tsx` line 311; `define/copy.ts` lines 54 and 56 | Reshape. Same note and footer on the backlog card, with backlog words ("Nothing is deleted. You can bring it back."). |
| Default review date rule (today plus three calendar months, day cut to month end) | `modules/m1_intent/domain/together.py` `default_review_date` (lines 201 to 206) | Reuse by import. The server sets the date; the screen shows it. |
| Shelf move with reason required for Future, audit of every move | `modules/m1_intent/domain/together.py` `move_to_shelf` (line 209); `modules/m1_intent/store/together_shelves.py` `ShelfStore` | Reshape. The backlog has its own record and history, but the "reason required, trimmed, audited" logic is copied from `move_to_shelf`, not re-derived. |
| Shelf rules in the contract: "Future keeps the reason and a review date; nothing is deleted" | `docs/specs/INTENT-CENTRE-SPEC.md` line 74, A-058 at line 172; `modules/m1_intent/contracts/board.yaml` lines 26 to 29 | Same pattern. The Future shelf stays in the Define screen for clusters of an Initiative; the backlog is for items between intents. No cluster is moved into the backlog by this feature. |
| JSON file store through the shared kernel | `sh_platform/jsonfile.py` | Reuse for `intents/backlog.json`. |
| Per-viewer filtering | `sh_platform/profile/view.py` | Reuse. |
| Pulse lines and templates | `sh_platform/pulse/lines.py`, `templates.py` | Reuse. Add three templates in `templates.py` and line builders in `lines.py`, no new engine. |
| Share link pattern | `sh_platform/public_link.py` | Not used; the backlog has no share link. |
| Start questions | Per-type files 22, 35, 41, 43 (02 is the catalogue only) | Reuse to pre-fill; no second question list. |

Genuinely new: the backlog record, the item card, merge, drop, the "I feel this" tap, the review reminder, the counters.

## Not in this feature

- Choosing what to work on by score or rank (no priority scoring, no auto-ordering by taps).
- Editing the source intent from the backlog.
- Moving a Define cluster from the Future shelf into the backlog (the shelf keeps its own review).
- Notifications outside Pulse (email, chat).
- A share link for the backlog.
- Bulk actions (merge many, drop many).
- Comments on items (comments live in the source and the opened intent).
- Deleting an item.

## Open questions

1. File 05's area record is `areas.<id>.{name, kind, status, from}` in `context/profile/profile.json` and has no lead. This file needs a `lead` cell on it (a person id, set by the company admin as a provenance cell, same rule as the other cells) and a lead picker on 05 Screen A. Needs 05 to add it; until then North sends the reminder to the company admin and says no lead is named. Also: 05 spells the list route `/intents`, which ruling 1 corrects.
2. The reminder hour (07:00 is proposed), the weekly repeat and the escalation to the company admin after four weeks without action are all proposals. Need a decision.
3. The default review date is one quarter, copied from the Future shelf. Is that right for an ops problem (maybe one month)?
4. Should the raiser of an item be able to tap their own item? Proposed: no, the raise counts as the first tap.
5. Should people outside the item's area be able to tap? Proposed: no, only people tagged to the area.
6. A Company-wide item has no area lead. Proposed: the company admin and the source organiser act. Confirm.
7. Should dropped items be visible to people in the area, or only to actors? Proposed: visible, with the reason, so people know what happened to what they raised.
8. The similar-items hint in step 5 needs a way of judging "close". Proposed: North judges it in words from the titles and lines, with no numeric threshold; confirm no threshold is needed.
9. Confirmed by the ruling: the shared park form is extracted from `ui/src/modules/m1_intent/define/`. Only the extraction itself remains to schedule.
10. Should a weekly check-in item raised anonymously be allowed in the backlog at all, given that the lead cannot ask the raiser a question? Proposed: yes, as "Anonymous", with taps from the area as the signal.
11. Should moving a review date out by more than a quarter need a reason? Not stated as a rule here; proposed: no, the change is only logged.
12. How does `backlog_ref` reach the start flow? The route convention has only `type` and `from` on `/centre/intent/new`. Proposed: the dialog creates the draft first, so the draft already holds `backlog_ref`; confirm no new query parameter is wanted.
