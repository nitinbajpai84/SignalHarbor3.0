# 38. Weekly check-in setup (the recurring intent)

Part of: Intent Centre v2. Depends on: 01, 02, 03, 05, 06, 07, 08, 13, 21. Feeds: 09, 12, 19, 21, 39, 40, 41 (a check-in item can start a Problem).

## Purpose (three sentences)

An ops area's people say each week what ran, what broke and what is on their mind, and that becomes the organiser's weekly intent. This feature sets the series up once (area, who reports, which day the week closes and who reviews, what each person answers), opens one week record each week by the clock without anyone pressing a button, and lets the organiser pause or end the series. Each item in a closed week is settled as `problem | backlog | handled | nothing`, with the reason.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet, ops lead) | Once, to start a standing weekly round; later to change people, day, questions, pause or end | Tile "Weekly check-in" in the chooser (spec 03); the "Series settings" button on the series home |
| Reporter (Aaron, Katie; the people of the area) | Each week, a few minutes (Open question 2) | Pulse line "Your check-in is open" (row 13 of spec 13) |
| Reviewer (default the organiser; may be another named person) | The last working days of each week | Pulse line "Check-in review is waiting" |
| Harvey (owner), Daniel (sponsor) | When an item becomes a Problem or a backlog item | The line from spec 13 for that Problem or item |
| Company admin | Sees that the series exists and its outcomes | Intent Centre home (spec 04) |

North opens each week, keeps the clock, drafts items from answers and nudges. People answer, review and decide fates. Agents never sign.

## Entry points (every route, link, Pulse line, button that leads here)

- Chooser tile "Weekly check-in" (spec 03) leads to Screen A at `/centre/intent/new?type=pulse`. Tile line: "Collect what ran, what broke and what is on people's minds in one ops area, every week." The chooser hands over to the four start questions below, which are canonical here (brief section 10, ruling 2).
- Pulse line row 13 (spec 13), title "Your check-in is open", action "Answer your check-in", href `/centre/intent/<id>/week`.
- Pulse line (organiser or reviewer): "Check-in review is waiting", action "Read the week", href `/centre/intent/<id>/review`.
- Intent Centre home card for the series (spec 04), button "Open", href `/centre/intent/<id>`.
- Link in the message North drafts to the reporters ("Your check-in for <area> closes <date>"), href `/centre/intent/<id>/week`.
- A Problem or backlog item made from a check-in item links back to the week (`links.from`, spec 21 `source`), href `/centre/intent/<id>/week?week=<week_key>`.

On a Pulse line, the word "Pulse" is never in the line text. It says "check-in".

## Screens, element by element

Five screens. Two routes carry weeks: `/centre/intent/<id>/week` (the reporter's answer form, and the read-only view of any closed week) and `/centre/intent/<id>/review` (the reviewer's read and sort). Both take the query parameter `?week=<week_key>` where `<week_key>` is the week to read (default: the current week; ruling 18). Series settings and Pause, resume or end live on the series home as a panel and a dialog, with no route of their own.

### Screen A. Set up a weekly check-in

Route: `/centre/intent/new?type=pulse`. Layout at 1280: left column "North asks" with the four questions one block at a time (answered ones collapse to one line with "Change"); right column "What happens" preview panel. At 390: one column; the preview moves under the questions as a collapsed bar "What happens" that opens on tap.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Heading | text | "Set up a weekly check-in" and "Every week the people of one area say what ran, what broke and what is on their mind." | none | creator | n/a |
| Q1 Area picker (`area`) | field (single choice from the company's areas, from the profile area list) | "Which ops area is this for?" One chip per area; a search box once the list is long (Open question 2) | Choose one; fills `areas` (one area) and the series title "Check-in: <area>" | creator | "No ops areas are set up yet. Ask your company admin to add one." "Next" stays off |
| Q2 People picker (`reporters`) | field (multi pick; people tagged to the area first, others searchable) | "Who reports each week?" Each person as a chip with name and role; a count "<n> people" (n is the chips chosen on this screen) | Add or remove; fills `people.participants` | creator | "Pick at least the minimum number of people." Next stays off (minimum in Open question 2) |
| Q2 button "Everyone in the area" | button | "Add all <n> people tagged to <area>" (n from the profile area tags) | Fills the picker with every person tagged to the area | creator | Hidden; the line says "No one is tagged to this area yet." |
| Q3 Close day (`close_day`) | field (weekday select, Monday to Friday) | "Which day does the week close?" Default shown (Open question 2) | Sets `series.close_day`; refreshes the preview | creator | Never empty (default shown) |
| Q3 Reviewer (`reviewer`) | field (single person pick, default "Me") | "Who reviews the week and decides what happens to each item?" | Sets `series.reviewer`; `people.organiser` stays the creator | creator | Never empty (default is the creator) |
| Q4 Answers panel (`prompts`) | list of three fixed lines | "What each person answers each week": "What ran well this week?" (kind `ran`), "What broke or nearly broke?" (kind `broke`), "What is on your mind?" (kind `thought`) | The three cannot be edited or removed | creator | n/a |
| Q4 button "Add one question" | button then text field | "Add one question of your own" (length limit in Open question 2) | Fills `series.extra_prompt`; shows as line 4 "(optional for the reporter)" | creator | Field closed; panel shows only the three lines |
| Preview panel | panel | "First week opens <date> and closes <date>. Answers close <date>. You review <date> and sort <date>. Then a new week opens every <weekday>." Dates computed from today, the close day and the company time zone (profile, else UTC) | Updates as Q3 changes | creator | n/a |
| North line | agent line | "North will open each week, remind people who have not answered, and draft an item from each answer for the writer to keep or change." | none | creator | n/a |
| Button "Start the check-in" | button | Enabled when Q1, Q2 and Q3 are valid | `POST /api/intents` with `type=pulse`, then `POST /api/intents/<id>/open`; opens week 1 at once; goes to `/centre/intent/<id>` | creator | Disabled, with the missing question named under it |
| Button "Save as draft" | button | none | Saves `state=draft`; no week opens. A draft is visible only to its creator (ruling 14) | creator | n/a |
| Link "Cancel" | link | none | Returns to `/centre/intent/new`; nothing is saved | creator | n/a |

### Screen B. The series home

Route: `/centre/intent/<id>`. Layout at 1280: top band (title, area, status chip, buttons), left "This week" panel, right "Earlier weeks" list, below it the "Series settings" panel (collapsed until opened). At 390: bands stack; "Earlier weeks" and "Series settings" are collapsed lists.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Title and status chip | text, chip | "Check-in: Operations: Settlement". Chip "Running", "Paused" or "Ended" from `series.status` | none | Area members and affected people see title, purpose, stage, clock, people and chip; content only to the people named below (ruling 4) | n/a |
| Button "Series settings" | button | none | Opens the settings panel below (panel S) | Organiser (edit), reviewer (read only) | Hidden for others |
| Button "Pause" or "Resume" | button | "Pause the series" / "Resume" | Opens dialog D | Organiser | Hidden when ended |
| Button "End the series" | button | none | Opens dialog D | Organiser | Hidden when ended |
| "This week" panel | panel | Week label "Week of <date>, closes <date>", stage chip (Collect, Review, Sort) from the week file `state`, and "<n> of <m> have answered" (n: distinct `answers[].account_id`; m: `people` on the week file; a count, never names, for non-reviewers) | Button "Open this week's check-in" goes to `/centre/intent/<id>/week` for reporters or `/centre/intent/<id>/review` for the reviewer and organiser | Participants, reviewer, organiser | "No week is open. The series is paused." with button "Resume" |
| "Who has not answered" list | list | Names of the reporters without an answer on the current week file | Button "Draft a reminder" asks North for the `intent_nudge` message (spec 13); the organiser sends or copies it | Organiser, reviewer | "Everyone has answered." |
| "Earlier weeks" list | list | One row per closed week: date, "<n> answered" (distinct `answers[].account_id`), "<n> items" (`items[]` length), "<n> settled as problems or backlog" (`items[].fate`) | Row opens `/centre/intent/<id>/week?week=<week_key>` read only | Participants, organiser, reviewer, share link | "No week has closed yet. The first closes <date>." |
| "Seen again" panel | panel | Items North found in the weeks before: "<text>: seen in <n> of the last <m> weeks" (n from `items[].repeat_of`; the window and threshold are Open question 5) | Row opens the first week it was seen | Reviewer, organiser | Hidden until a repeat exists |
| Counters strip | panel | Weeks run, answers this week, items settled (see Counters) | none | Organiser, reviewer | "Not available yet: no week has closed." |
| Panel S, Series settings | panel | Area (read only, text; to change area, end this series and start a new one); Reporters (the Q2 picker); Close day (select); Reviewer (person pick); Own question (text field, or "No question of your own." with link "Add one") | Reporters, close day and own question apply from the next week; the reviewer applies at once to the open week | Organiser (edit); reviewer (read only); reporters see area, close day, reviewer and the questions only | Reporters: "Pick at least the minimum number of people." and Save stays off |
| Panel S "Changes apply from" note | text | "The week of <next week start>. The week now open keeps its questions and its people." | none | organiser | n/a |
| Panel S button "Save changes" | button | none | `PUT /api/intents/<id>/series`; one history line per changed field in `events.jsonl` | organiser | Disabled until a field changes |
| Link "Share" | link | none | Goes to `/centre/intent/<id>/share` (spec 11) | Organiser | Hidden for others |

### Screen D. Pause, resume or end (dialog over Screen B)

Route: none. Layout at 1280: centred, 480 wide; at 390: full-width sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Heading | text | "Pause the check-in?", "Resume the check-in?" or "End the series?" | none | organiser | n/a |
| Consequence line | text | Pause: "The week now open finishes as normal. No new week opens until you resume." Resume: "A new week opens on <next working day>." End: "The week now open is closed with what we have. No new week opens. Every earlier week is kept." | none | organiser | n/a |
| Reason | field | "Why?" (required for End, optional for Pause) | Saved with the change | organiser | "Give a reason to end the series." The End button stays off |
| Button "Pause", "Resume" or "End the series" | button | none | `POST /api/intents/<id>/series/<pause\|resume\|end>` | organiser | n/a |
| Button "Not now" | button | none | Closes the dialog; nothing is written | organiser | n/a |

### Screen E. Answer this week (reporter), and read a closed week

Route: `/centre/intent/<id>/week` (`?week=<week_key>` for another week). Layout at 1280: one column 640 wide with the answer lines as text areas and a side note "Closes <date>". At 390: one column, the note above the first line. Phone is a first-class screen.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Week label | text | "Check-in for Operations: Settlement. Week of <date>. Answers close <date>." | none | reporter | n/a |
| Answer fields (three, and a fourth if `extra_prompt` is set) | field (text) | The prompt as the label | Typing saves a draft after a pause | reporter | Placeholder "A sentence or two is enough" |
| Checkbox "Keep my name off this" (one per line) | field | none | Sets `anonymous` on the item drawn from that line (v1 rules, D-013) | reporter | Unchecked |
| Button "Nothing this week" (one per line) | button | none | Marks the line "Nothing to report"; it counts as answered | reporter | n/a |
| Button "Send my check-in" | button | Enabled when every required line has text or "Nothing this week" | `POST /api/intents/<id>/weeks/<week_key>/answers`; North drafts items; screen shows "Check what North wrote for you" (row 4, spec 13) | reporter | Disabled, names the line still empty |
| "North wrote" list | list | One drafted item per answer line, as a card with the reporter's words kept first | Buttons "Keep", "Change", "Delete" per card; only the author acts | reporter | "Nothing to check." |
| Late state | panel | "This week's answers have closed. Your answer can no longer be added." with link "Add it to next week" | Link opens `/centre/intent/<id>/week` for the next week once it is open | reporter | n/a |
| Closed week read view | panel | Items and fates with reasons; anonymous items without names | Link on a fated item opens the Problem or backlog item it became | Participants, organiser, reviewer, share link | "Nobody answered this week." |

### Screen F. Read and sort the week (reviewer)

Owned by spec 40 (intent-review-sorting.md). File 38 holds the route only: `/centre/intent/<id>/review` with the query parameter `?week=<week_key>` (ruling 18). See spec 40 for the layout, elements, user journey and closed week view.

## User journey

1. Janet picks "Weekly check-in" from the chooser. North asks Q1 and she picks "Operations: Settlement".
2. She adds Aaron, Katie and others (Q2), chooses Friday as the close day and herself as reviewer (Q3), and keeps the three lines, adding "What did you wait on that you should not have?" (Q4).
3. She reads the preview and presses "Start the check-in". North writes the series record and opens week 1. North drafts the message `intent_week` for her to send (spec 13).
4. Monday: Aaron's Pulse shows "Your check-in is open". He answers, ticks "Keep my name off this" on one line, and sends. North turns each line into a drafted item. He keeps one, changes one.
5. Between steps, North counts answers, drafts a reminder for Katie before answers close, and groups repeats against earlier weeks.
6. Late in the week, answers are closed. Janet's Pulse shows "Check-in review is waiting". At `/centre/intent/<id>/review` she reads the items, merges two, and gives each a fate with a reason: ops problem, backlog, handled, or nothing.
7. Harvey receives the Problem as his own line. A backlog item is opened for Daniel to see.
8. On the close day she presses "Close the week". The week record is written and the series home lists it under Earlier weeks.
9. On the next working day after the close day, with no one pressing anything, North opens week 2 with the same people, day and questions, even if week 1 were still unreviewed.
10. In a later week Janet presses "Pause" for a shutdown fortnight, then "Resume". When the area no longer needs it she presses "End the series" with a reason, and leaves the screen.

## States and transitions

Two things have states: the series (the intent record) and each week (its own file).

Series (intent `state`, plus `series.status`):

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | Organiser, "Save as draft" | `draft` | Record with `type=pulse` and the `series` block; visible to the creator only |
| `draft` | Organiser, "Start the check-in" | `open`, `series.status=running` | `time_box.starts`; first week file; event line |
| `open`, running | Organiser, "Pause" | `open`, `series.status=paused` | `series.paused {by, at, reason}`; event line |
| `open`, paused | Organiser, "Resume" | `open`, `running` | `series.next_week_opens`; the pause kept as an event line |
| `open` | Organiser, "End the series" (reason required) | `closing`, `series.status=ended` | `series.ended {by, at, reason}`; the open week moves to `closing`; North drafts the closure |
| `closing` | Organiser, "Close intent" (spec 09) | `closed` | `closure` (summary, weeks run, what came out) |
| `draft`, `open` | Organiser or sponsor | `cancelled` (spec 01) | `cancel {by, at, reason}`; shown in Past with the reason (ruling 14). Whether a cancel is allowed after the first week closes is Open question 7 |

Week (file `intents/<id>/weeks/<week_key>.json`, `week_key` like `2026-W42`):

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | North, by the clock, on the next working day after the close day | `collect` | Week file with `opens_on`, `answers_close`, `closes_on`, `people` and `prompts` copied from the series |
| `collect` | North, when the answer window ends | `review` | `stage_closed_at`; the answer window locks |
| `review` | Reviewer, "Start sorting", or North at the end of the review day | `sort` | `stage_closed_at` |
| `sort` | Reviewer, "Close the week" (every `broke` item has fate and reason) | `closed` | `outcome`, `closed_by`, `closed_at` |
| `collect`, `review` or `sort` | North, at the end of the close day | `closing` | Unsettled items listed "not sorted"; the Pulse line stays for the reviewer |
| `closing` | Reviewer, "Close the week" | `closed` | As above |
| `closed` | none | final | Read only (house rule 7) |

The new week opens by the clock, not by the previous week's closing (see Rules).

## Records read and written

| Record or route | Fields | Existing or New |
|---|---|---|
| `intents/<id>/intent.json` (the series intent) | the full intent record (brief section 3) plus the `series` block | New (spec 01; ruling 12) |
| `intents/<id>/weeks/<week_key>.json` | `week_key, opens, closes, state, items: [{id, by\|anonymous, kind: ran\|broke\|thought, text, severity\|null, count\|null, amount\|null, ref\|null, fate\|null, fate_reason\|null, decided_by\|null}], review: {...}, closed_at` (ruling 17) | New |
| `intents/<id>/events.jsonl` | one line per series change, week open, pause, end (spec 16) | New |
| `intents/index.json` | one line per intent | New (spec 01) |
| `POST /api/intents`, `POST /api/intents/<id>/open`, `PUT /api/intents/<id>/series`, `POST /api/intents/<id>/series/<pause\|resume\|end>` | as the buttons above | New |
| `GET /api/intents/<id>/weeks`, `GET .../weeks/<week_key>`, `POST .../weeks/<week_key>/answers`, `POST .../weeks/<week_key>/items/<item_id>/fate`, `POST .../weeks/<week_key>/close` | as the screens | New |
| `modules/m1_intent/contracts/intent_types.yaml`, entry `pulse` | the four start questions below, prompts, stages | New (spec 02 creates it; file not present today) |
| `sh_platform/profile/view.py` | viewer, areas, roles, time zone for visibility and dates | Existing, read |
| `sh_platform/jsonfile.py` | read and write of the JSON files | Existing |
| Problem and backlog creation | `/centre/intent/new?type=problem&from=<id>` (spec 41), spec 21 | New, by their own specs |
| `pulse/messages.json` | `intent_week`, `intent_nudge` drafts | Existing file, new kinds (spec 13) |

Start-question keys (canonical, ruling 2): `area`, `reporters`, `close_day` with `reviewer`, `prompts`.

Week item shape (ruling 17): `items` array holds objects with keys `id, by|anonymous, kind: ran|broke|thought, text, severity|null, count|null, amount|null, ref|null, fate|null, fate_reason|null, decided_by|null`. The organiser's optional fourth question (Q4 "Add one question") produces items of kind `thought`.

## Fields this feature adds to the intent record

| Field | Shape | Meaning |
|---|---|---|
| `series` | `{status: running\|paused\|ended, close_day: mon..fri, reviewer: account_id, extra_prompt: string\|null, week_length_days, next_week_opens: date\|null, current_week: week_key\|null, weeks: [week_key], paused: {by, at, reason}\|null, ended: {by, at, reason}\|null}` | The recurring settings and the list of weeks. The weeks are separate files. `week_length_days` value: Open question 2 |
| `refs.weeks_dir` | `"intents/<id>/weeks"` | Where the week files live; the record points and never copies |

`time_box` for a series means the current week's box (`starts`, `ends`), moved forward each week. `outcome` is an object from the moment the series opens (ruling 6), never null; for a series it holds the derived counts `{weeks_run, fates: {problem, backlog, handled, nothing}}` read from the week files, final shape in spec 02 (ruling 16 ensures it is flat; Open question 8). `ratings` stays empty: series are not rated and weeks are not rated. `people.participants` and `areas` are the series defaults. `stages` holds one entry, `running`; each week holds its own stage.

## Agent behaviour

- **North** (the workflow, brief section 5):
  - At setup: asks the four questions, shows the preview, writes the series on "Start the check-in". It never opens a series by itself.
  - Each week: opens the week record at `next_week_opens`, copies people and prompts into it, drafts the `intent_week` message for the organiser. The organiser sends it, or copies the text (the email path does not exist yet).
  - On each answer: drafts items, one per line; the author keeps, changes or deletes.
  - Review: groups repeats within the week and against earlier weeks (a text match drafted by North; the reviewer merges or splits). Drafts a reason for each fate; the reviewer writes or accepts it.
  - At the end of the close day: moves any unfinished week to `closing`, lists unsettled items, never closes a week itself.
  - On "End": drafts the closure summary (weeks run, answer counts, fates) for the organiser to confirm.
  - If several weeks in a row close empty, North shows the streak and offers "Pause", "Change the people", or "Keep going". A person picks (number in Open question 6).
- **Lens**: not used. No definition is drafted by a check-in.
- **Nira**: feeds the Pulse lines "Your check-in is open" (row 13), "Check-in review is waiting", "Check what North wrote for you" (row 4), and the organiser line "<n> of <m> have not answered" (row 16). Nira drafts the line from the week file; the person acts.

## Rules

- **The name rule.** "Pulse" on screen means one thing only: the daily landing page and its lines. The type is called "Weekly check-in" on every screen; its record key stays `pulse` and is never shown. A line about a check-in says "check-in". Each week is "this week's check-in" or "the week of <date>". The person who sorts is "the reviewer". This follows ruling 3; specs 02, 03 and 13 are corrected in the review wave.
- **The series shape (ruling 3).** One intent record with one id for the series, and one file per week at `intents/<id>/weeks/<week_key>.json`. Visibility, people, share link and history belong to the series and are not copied each week. A closed week never changes, so it can be shared or filtered on its own.
- **A new week opens by the clock.** The next week opens on the next working day after the close day, in the company time zone (profile, else UTC), whether or not the reviewer has closed the last one. The old week stays in `closing` and its Pulse line stays for the reviewer.
- **Fates.** Every `broke` item must have a fate with a reason before the week closes (ruling 23). `ran` and `thought` items left undecided close as `nothing` with the reason "Not reviewed this week". A week never closes with an undecided `broke` item. Fates are `problem | backlog | handled | nothing`. An ops problem always starts through spec 41 so it has an owner; a backlog item always goes through spec 21.
- **Week length and phase.** The week and the answer, review and sort days follow the close day; the lengths are Open question 2.
- **Opening without a scheduler.** No clock job exists today. North opens a due week the first time the series, Pulse or the centre is read after `next_week_opens`, under the intent lock, keyed by `week_key`, so two readers never open two weeks.
- **Who sets up.** Any company person may start a check-in. The creator is the organiser. The reviewer defaults to the organiser and may be one other named person.
- **Who answers.** Only people in `people.participants` of that week. Each answers once per line and may edit until answers close. A reporter sees their own answers only until the week closes; then participants see items and fates.
- **Who sees what** (brief section 4, ruling 4): area members and affected people see existence, title, purpose, stage, clock, people and the outcome once closed. Content opens only for participants, the reviewer and organiser, observers (read only), people on a share, and affected people when the organiser switched on "affected people may read" at creation (default off). Anonymous items show "Anonymous" to everyone, including the company admin and the reviewer. A super admin sees existence only (ruling 5).
- **Areas.** One area per series. Moving to another area is a new series, because visibility and reporters follow the area.
- **Pause** is the organiser's and never cancels the open week. **End** needs a reason, keeps every week, closes the open week with what it has (ruling 23: the only "close with what we have"), and is final; a restart is a new series with `links.from` set.
- **Changes** to reporters, close day and the extra question apply from the next week. The reviewer change applies at once.
- **Numbers** follow ruling 8: counts are exact; any mean, median or per-person figure shows "Fewer than five" below five records. No per-person figures exist anywhere.

## Counters and measures of this feature (numbers only, each traced to a record)

| Number | Traced to |
|---|---|
| Weeks run | count of week files under `refs.weeks_dir` |
| Answers this week, shown as "<n> of <m>" | distinct `answers[].account_id` over `people` on the current week file |
| Answers across weeks | the same, summed over closed week files; "Not available yet: no week has closed." until one exists |
| Items this week, items settled | `items[]` length; items with `fate` set |
| Fates by kind | `items[].fate` counts over closed week files |
| Items that came back | `items[].repeat_of` non-empty |
| Weeks closed late | week files whose `closed_at` falls after `closes_on` |
| Empty weeks | week files closed with zero answers |
| Weeks paused | pause events in `intents/<id>/events.jsonl` |

Counts never name a person for non-reviewers. Whether "Nothing this week" counts as an answer is Open question 9.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searched with graft ("how a m1_intent session is created, stored, listed and stateful") and by reading `sh_platform/pulse/` and `modules/m1_intent/`. Paths checked on 7 Oct 2026.

| Existing | Verdict |
|---|---|
| `sh_platform/pulse/lines.py`: `line()` line 71, `safe` line 60, `MINUTES` line 22 | Reused for the Pulse lines only: the line shape, the safe wrapper and the minutes table. New kinds come from spec 13 |
| `sh_platform/pulse/__init__.py`: `CAP = 7` line 13, `_order` line 16, `_strips` line 31, `build` line 58 | Reused as is: check-in lines compete under the cap like any other line. The new reader is spec 13's |
| `sh_platform/pulse/messages.py`, `sh_platform/pulse/templates.py` | Reused for the `intent_week` and `intent_nudge` drafts (words and dates only) |
| `modules/m1_intent/store/sessions.py`: `SessionStore` from line 42 (file per session, `index.json`, lock, `create`, `get`, `transition`, `list_for`) | Reshaped: the pattern (file per id, index, lock, transition table) is copied into the intent store of spec 01; week files use it in a sub-folder. Not reused as is, because a session carries wall fields a check-in does not have |
| `modules/m1_intent/domain/states.py`: `ALLOWED` line 21, `can_move` line 28 (and the paused-from idea) | Reshaped: the pause and resume idea copies to `series.status`; the states differ |
| `modules/m1_intent/domain/timer.py`: `window_minutes` line 35 | Reshaped by spec 01: a date-returning working-days sibling gives `answers_close`, `closes_on`, `next_week_opens` |
| `modules/m1_intent/api/session.py`: `create_draft` line 79 | Reshaped: the same "draft then open" flow, new route `/api/intents` |
| `modules/m1_intent/contracts/interview_notes.yaml` | Idea only: draft then keep. The prompts are new wording |
| `modules/m1_intent/contracts/intent_types.yaml` | Does not exist yet; spec 02 creates it |
| `ui/src/pages/PulsePage.tsx` | Not used for any screen here; only its line cards render the check-in lines |
| `sh_platform/profile/view.py`, `sh_platform/jsonfile.py` | Reused for visibility, time zone and JSON storage; no change |

Genuinely new: the series record and its week files, the weekly clock, the series settings panel, and the reporter and reviewer screens.

## Not in this feature

- The Pulse page itself and its seven-line cap (spec 13 and today's code).
- The Problem workflow and the backlog (specs 41 and 21); this feature only starts them.
- Recurring types other than the check-in.
- Email delivery of reminders (drafts and "Copy text" only).
- Charts of week-on-week trends (spec 19 may read the counts).
- Rating a series or a week, and scoring people by their answers. Answers are not performance data.
- Per-person times or reminders by time of day.
- Several areas in one series.
- The person-facing screens for the answer window in depth (spec 39) and the review and outcome in depth (spec 40); this file holds the setup and the screens' routes.

## Open questions

1. Routes: settings and the pause dialog have no route of their own, and weeks use `?week=<week_key>` on `/week` and `/review`. Confirm a query parameter is acceptable, or add a `/centre/intent/<id>/week/<week_key>` form to ruling 1.
2. Values not given by the brief and not yet justified: default close day (proposed Friday); week length (proposed 5 working days, Monday to Friday, no holidays); answer window end, review day and sort day (proposed two working days before the close day, one, one); minimum number of reporters (proposed two, plus the reviewer); answer length (600 characters) and own-question length (240); when the area picker gets a search box (proposed above 8 areas); expected minutes per answer (spec 13 `MINUTES` has no check-in entry).
3. May a week be shorter than five working days for an area on a short week?
4. Who may end a series if the organiser leaves the company: the sponsor, or only the company admin? The brief's company admin role sees existence and outcomes; ending is an action that needs a ruling.
5. Repeats: the text match North uses, the threshold (proposed 2 or more weeks) and the look-back window (proposed the last 5 weeks).
6. How many empty weeks in a row before North offers a pause (proposed three)? Spec 07 question 11 asks whether a late week counts as closed in its time box.
7. May a series be cancelled after its first week has closed, or only ended?
8. Final shape of the series `outcome` object (counts only, derived from week files) belongs to spec 02.
9. Should "Nothing this week" count as an answer in the answers count? Proposed yes, shown as a separate count.
10. Should a reporter who joins mid-series see earlier closed weeks? Proposed yes if tagged to the area, anonymous items unchanged.
11. Backlog item kind (idea, initiative, fix) is spec 21's; confirm a check-in item sorted to the backlog may carry "initiative candidate".
