# 40. Weekly check-in review and outcome

Part of: Intent Centre v2. Depends on: 00-BRIEF, 01 (record and lifecycle), 02 (types catalogue, Weekly check-in), 07 (time box), 09 (closure), 13 (Pulse lines), 17 (projector view), 21 (backlog), 38 (series setup, week clock), 39 (entry: the items, their severity and links), 41 (Problem start). Feeds: 04 (home counters), 12 (past intents), 19 (centre counters), 21 (backlog items), 41 (Problem intents).

On screen the type is "Weekly check-in". "Pulse" alone means the daily page. The record key stays `pulse`.

## Purpose (three sentences)

When answers close for the week, North drafts a digest of what the area said: what ran, what broke and what is on people's minds, every number traced to items. The reviewer (the person named in start question 3 of file 38; the organiser by default) goes through the digest in a 30 minute review session, gives each item one fate with a reason, and closes the week. The closed week is read-only, and every reporter sees what happened to each of their items and why.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Reviewer (for example Janet for Operations) | After answers close, then the review session | Pulse line "Read the week" (13, stage `review`); North's digest is waiting |
| Reporter (a participant, for example Aaron, Harvey) | After the week is closed | Pulse line "Your items from the week of 28 Sep have a decision" |
| Participants and observers | Any time after closure | Open the week or the trends tab; they read the digest and decisions, never anonymous authorship; observers never write |
| Affected people | Any time | See existence, title, purpose, stage, clock, people and the outcome once closed. They open the week content only if the organiser switched on "affected people may read" at creation (default off) or they are named on a share |
| Company admin | When a reviewer is away or a week is stuck | Sees the outcome; may close a stuck week for the reviewer (01 stuck-intent rule); never sees anonymous authorship |
| Owner of a Problem that came out of an item | Opens the Problem | Link "From the week of 28 Sep" |
| Super admin | Never opens content | Existence row only (00-BRIEF section 4, ruling 5) |

## Entry points (every route, link, Pulse line, button that leads here)

- Pulse line (13), reviewer, stage `review`: "Read the week" opens `/centre/intent/<id>/review?week=<week_key>` (Screen A).
- Pulse line (13), reviewer, stage `triage`: "Give each item a decision: 7 items need one" opens Screen A with `item=` set to the first item still open.
- Weekly check-in intent page `/centre/intent/<id>`: the weeks list; each row links to its week on `/centre/intent/<id>/review?week=<week_key>`; a link "Trends" opens Screen D.
- **Start review session** on Screen A opens Screen B (same route, `view=session`).
- **Close the week** on Screen A opens Screen C (a panel on the same route, `#close`).
- Pulse line (13), reporter: "Your items from the week of 28 Sep have a decision" opens `/centre/intent/<id>/week?week=<week_key>&view=mine` (Screen E).
- Backlog item (21), "Where it came from" panel: links back to the item on its week.
- Problem intent (41), "Came from" panel: links back to the item on its week.

## Screens, element by element

### Screen A. Week review

Route: `/centre/intent/<id>/review?week=<week_key>`. Query: `section`, `item=<item id>`, `mode=session`.

Layout at 1280: top bar (title "Weekly check-in, Operations, week of 28 Sep", state chip, counters strip, buttons). Left column (360 px): the digest in four sections (Broke, Ran well, On your mind, Repeats). Main column: the item list for the chosen section, one card per item, each with the decision control. Right column (320 px): North panel. Layout at 390: the left column becomes a tab row (Broke, Ran well, On your mind, Repeats) with counts; cards stack full width; the decision control opens as a bottom sheet; the North panel is a sheet behind a dot; **Start review session** and **Close the week** sit under "More" in the bottom bar.

The digest (North, drafted when answers close, before the reviewer opens it):

- Broke: items grouped by process or measure (from the item's `ref`, file 39; no `ref` goes under "Not linked"). Inside a group, ordered by the number of people who reported the same item (as grouped by North), then by earlier weeks seen. Each item shows the severity its reporters marked ("Stopped us 2, Slowed us 1, Cost money 0, Not marked 1"), with the count or amount they gave. North never picks a severity.
- Ran well: grouped by process or measure; ordered by number of reporters.
- On your mind: grouped by topic (a short phrase North gives a group, for example "Month-end custody reconciliation"); ordered by number of items.
- Repeats: an item North matches to an item of an earlier week carries the chip "Seen 3 weeks" (this week plus two earlier); hover lists the weeks. The match is North's draft; the reviewer may split it ("Not the same").
- Every number in the digest carries a source chip that opens the items it counts. A sentence whose number has no items behind it is dropped.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Header: title and week chip | Heading | "Weekly check-in, <area>", "Week of 28 Sep", state chip (Collecting, Ready to review, In review session, Closing, Closed) read from `week.state` | None | Participants, observers, reviewer, company admin; affected only when allowed (Rules) | Same |
| Counters strip | Panel | "5 of 6 answered" (`responded_count` of `participants_count`), "7 items" (count of `items[]`), "3 broke" and "2 repeat" (count of `items[].kind`, `seen_weeks`), "4 decided of 7" (count of `items[].decision`) | A number opens the items it counts | Same as header | "Not available yet: the week has no answers recorded." |
| Digest section tab | Chip group | Broke, Ran well, On your mind, Repeats, each with a count of its items | Switches the list; writes `section` to the URL | Same | A section with zero is dimmed: "Nothing in this section." |
| Group heading | Heading with count | "Custody reconciliation, Breaks cleared by 10:00: 3 items" | Collapses or expands the group | Same | Not shown for an empty group |
| North digest line | Agent line | One sentence per group, for example "Three people said the 10:00 custody file was late again." with source chips | A chip opens the items it counts | Same | "North could not group this week's items. They are listed as written." |
| Item card | List item | Text, kind chip (Ran, Broke, On your mind), process or measure chip, reporter name or "Anonymous", "Seen N weeks" chip, severity chips (Broke only), decision chip | Click opens the card drawer (full text, North's note, links, decision history) | Same; the name is hidden on an anonymous item (D-013) | Not shown |
| "Not the same" link | Link button | On a repeat chip | Removes the match; the item's count drops to 1; the split is recorded in the week's events | Reviewer | Hidden when the item has no repeat chip |
| Decision control | Segmented control with fields | Four fates (below), a reason field, a link field where needed | Saved by **Save decision**; changeable until the week closes | Reviewer; company admin on a stuck week | "No decision yet". Broke items show "Needs a decision" in warn colour |
| Fate **Becomes a Problem** | Option | "Becomes a Problem" | Opens the Problem start (41) pre-filled in a side panel: question 1 one-liner from the item, "What you saw" from the item text, process or measure from `ref`, "How hard" from `severity`, `count`, `amount`, areas from the pulse, owner empty. The reviewer presses **Create Problem**. The item stores `fate = problem` and `fate_ref = <problem intent id>` | Reviewer | Disabled with "Needs an area" if the intent has no area (guard only) |
| Fate **Goes to the backlog** | Option | "Goes to the backlog" | Opens the backlog add form (21) pre-filled: title, area, kind "Ops problem" for Broke and "Idea" for the others, source = this item, North's why-it-matters line. The reviewer presses **Add to backlog**. The item stores `fate = backlog`, `fate_ref = <backlog item id>` | Reviewer | Same guard |
| Fate **Already handled** | Option | "Already handled" and a required link field "Link to what handled it" | A picker of existing Problems, backlog items, Initiatives, Brainstorms and Decisions the viewer may see (by title), or a pasted route inside the centre. Saves `fate = handled`, `fate_ref` | Reviewer | "You have no intent or backlog item to link yet. Choose another fate or open one first." |
| Fate **Nothing** | Option | "Nothing" | Needs only the reason | Reviewer | None |
| Reason field | Text field | "Why? Say it in a line." Required for every fate; North pre-fills a draft (for example for a Problem: "Third week running"), the reviewer edits | Typing enables **Save decision**; a reporter reads this text on Screen E | Reviewer | Field error "Please say why." |
| **Save decision** | Button (primary) | "Save decision" | Writes the fate, reason, link, reviewer and time; the card shows the decision chip, reason or link | Reviewer | Disabled until the fate, the reason and any required link or created record are complete |
| **Change decision** | Link button | On a decided item while the week is not closed | Reopens the control; the earlier decision stays in the item's history | Reviewer | Hidden once the week is closed |
| Decision progress | Panel | "3 of 3 broke items decided. 1 of 4 other items decided." (count of `items[].decision` by kind) | None | Reviewer | "No items this week." |
| **Start review session** | Button | "Start review session" | Switches to Screen B | Reviewer | Disabled: "Nothing to review: the week has no items." |
| **Close the week** | Button (primary) | "Close the week" | Opens Screen C | Reviewer; company admin on a stuck week | Disabled while any broke item has no decision: "2 broke items still need a decision", linking to the first |
| North panel | Agent panel | What North grouped, what it matched as repeat, a draft sentence for "what came out" | **Use this** copies the draft into Screen C; **Ask North** answers from this week's items only | Reviewer | "North has nothing to add yet." |

### Screen B. Review session mode

Route: `/centre/intent/<id>/review?week=<week_key>&view=session`. A display mode of Screen A, not a new screen (same pattern as the projector view in 17).

Layout at 1280 and 1920 by 1080: top strip with the current group on the left and the clock on the right (30:00 counting down). Middle: one item at large size (kind chip, text, process or measure, "Seen N weeks", severity chips), the four fate buttons below, and **Next item** and **Previous item**. Bottom strip: "Item 4 of 7, 3 decided". No names are shown. At 390 the Projector chip is hidden (17); if the session is opened by link it shows one column: clock, item, fate buttons.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| **Projector view** chip (the existing `t.projector` pattern, 17) | Chip | "Projector view" / "Back to the full view" | Fullscreen display; Escape leaves | Reviewer | Hidden for others |
| Session clock | Number | 30:00 counting down from `session.started_at`; time is read from the server, never the browser | None. At 5:00 left it turns to the warn colour with "5 minutes left" | Reviewer and the projector | "Not started" before **Start session** |
| **Start session** | Button | "Start session" | Writes `session.started_at` and `session.by`; state `in_session`; items ordered Broke first (digest order), then On your mind, then Ran well | Reviewer | Disabled: "Nothing to review." |
| Current item | Panel | Item text without name, kind, process or measure, repeat count, severity chips | None | Display | "All items are reviewed." with **Close the week** |
| Four fate buttons | Buttons | **Becomes a Problem**, **Goes to the backlog**, **Already handled**, **Nothing** | As on Screen A; the pre-filled panels and the reason field open on the reviewer's laptop, never on the projector | Reviewer | Disabled with the reason shown |
| **Next item**, **Previous item** | Buttons | "Next item", "Previous item" | Moves the current item. Moving past a Broke item with no fate asks "This broke item has no decision. Move on and come back?" with **Move on** and **Stay** | Reviewer | Next disabled on the last item; Previous on the first |
| **End session** | Button | "End session" | Writes `session.ended_at` and `session.minutes_used`; returns to Screen A; undecided items stay undecided | Reviewer | Enabled once started |
| Overrun line | Agent line | "The 30 minutes are up. 2 items are still open. Extend by 10 minutes, or end the session." with **Extend 10 minutes** and **End session** | **Extend 10 minutes** adds `{by, at, minutes}` to `session.extended_by[]` | Reviewer | Shown only at zero |

### Screen C. Close the week

Route: panel on `/centre/intent/<id>/review?week=<week_key>#close`. At 1280 a 480 px right-hand panel over the list; at 390 a full-screen sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Summary draft | Agent line (North draft, editable field) | "Five of six answered. Seven items: 3 broke, 2 ran well, 2 on minds. 1 became a Problem, 2 went to the backlog, 1 already handled, 3 nothing." Each number carries a source chip | The reviewer edits; North's redraft never overwrites an edit (rule 7) | Reviewer | "North could not draft this. Write one line." |
| Decisions table | List | One row per item: text (shortened), fate, reason or link | A row opens the item card | Reviewer | "No items this week. The week closes as: nothing came in." |
| Undecided items panel | Panel | "3 items have no decision. They close as Nothing with the reason 'Not reviewed this week'." with a link to each | A link opens the item | Reviewer | Hidden when all are decided |
| "The series continues" line | Text | "Next week opens by the clock on Mon 5 Oct, whether or not this week is closed." from the series schedule (38) | None | Reviewer | "The series has been stopped; no next week opens." |
| **Close the week** | Button (primary) | "Close the week" | Writes the closure (see States), sets the week read-only; it does not open the next week (the clock does, 38) and sends no message | Reviewer | Disabled while any broke item has no decision |
| **Cancel** | Link button | "Cancel" | Closes the panel | Reviewer | Always enabled |

### Screen D. Trends

Route: `/centre/intent/<id>/review?view=trends` (ruling 18). Layout at 1280: top bar (title, process filter, range chips); main: a table of closed weeks across and processes down, each cell the count of Broke items; below it the repeated items list; right: North's reading. At 390: the table scrolls sideways with the process column fixed; the repeated list stacks.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Broke items per week per process | Table | One row per process, one column per closed week, count of `items[].kind = broke` by `ref`; a column total | A cell opens that process and week's items in a side panel | Participants, observers, reviewer; affected only when allowed. Others in the area see existence only | "Not available yet: trends need four closed weeks. This series has 2." |
| Repeated items list | List | Each item North matched across weeks: text, process, the weeks, "Seen 4 weeks", fate in its latest week | A row opens the latest week's item | Same | "No item has come up in more than one week." (once four weeks exist) |
| Range chips | Chip group | Last 4 weeks, Last 8 weeks, All weeks in the series | Re-filters | Same | "Last 8 weeks" dimmed while fewer than eight weeks exist |
| Process filter | Select | The processes seen in the series | Filters table and list | Same | "No processes recorded yet." |
| North's reading | Agent line | One or two sentences, for example "Custody file lateness has been reported in 4 of the last 5 weeks." with source chips | A chip opens the items | Same | "Not available yet: trends need four closed weeks." |

### Screen E. What I raised (the reporter's view)

Route: `/centre/intent/<id>/week?week=<week_key>&show=mine`. Layout at 1280: a single 720 px column; at 390 the same, full width. Shown only for closed weeks.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Heading | Heading | "Your items, week of 28 Sep" | None | The reporter | Same |
| Item row | List item | The reporter's own item text, kind chip, fate chip (Became a Problem, Went to the backlog, Already handled, Nothing), the reason, the link title | The link opens the Problem, backlog item or intent if the reporter may open it; otherwise it shows the title with "Ask <reviewer name> for access" | The reporter, own items only. An anonymous item is shown to its author only through their anonymous token (D-013) | "You did not add an item this week." |
| Problem progress chip | Chip | State of the linked Problem (Open, Fixed, Closed), read from the Problem | None | The reporter | Hidden if no Problem |
| Pulse line | Line | "Your items from the week of 28 Sep have a decision", shown until the reporter opens this screen | Opens this screen | The reporter | No line |
| **See the whole week** | Link | "See the whole week" | Opens Screen A read-only | Participants, observers, affected when allowed | Hidden for others |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Answers close (stage `collect` ends, 38). North stops accepting answers.
2. North drafts the digest: groups items by process or measure, orders broke items by reporter count and earlier weeks, shows the severity the reporters marked, groups "on your mind" items by topic, matches repeats to earlier weeks, and puts a source chip on every number. The week moves to `ready`.
3. Nira puts "Read the week" on Janet's Pulse.
4. Janet opens Screen A (arriving from that line). She reads Broke first. North's line says "Three people said the 10:00 custody file was late again. Seen 3 weeks."
5. Janet decides alone, item by item, or presses **Start review session**.
6. In the session (Screen B) the clock starts at 30:00 and the team watches the projector. For the custody file item Janet picks **Becomes a Problem**. North pre-fills the Problem start; Janet picks Harvey as owner and presses **Create Problem**, then writes the reason. The item shows "Problem, owner Harvey".
7. North watches the clock: it says "5 minutes left", and at zero offers extend or end. Janet ends the session with one item open.
8. Janet returns to Screen A, decides the last items, presses **Close the week**. Screen C shows North's summary; she edits one sentence.
9. She presses **Close the week**. The week becomes read-only. Next week has already opened by the clock (38).
10. Nira puts a line on each reporter's Pulse. Aaron opens Screen E and reads "Nothing: already covered by the quarterly vendor review", with the reason, then leaves.
11. After four closed weeks, anyone who may open the week opens Screen D and reads the trends.

## States and transitions (table: state, who moves it, to what, what is written)

Week states live in `week.state`. The intent stays `open` while the series continues.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| `collecting` | North, when answers close | `ready` | `digest`, `digest.drafted_at`, `stages[review].opened_at` |
| `ready` | Reviewer presses **Start session** | `in_session` | `session.started_at`, `session.by` |
| `ready` | Reviewer saves the first decision | `reviewing` | `item.decision` with `by`, `at` |
| `in_session` | Reviewer presses **End session** | `reviewing` | `session.ended_at`, `minutes_used`, `extended_by[]` |
| `ready`, `reviewing`, `in_session` | North, at the end of the close day (38) if the week is not closed | `closing` | Event line; the reviewer's Pulse line stays |
| `ready`, `reviewing`, `closing` | Reviewer presses **Close the week** (every broke item has a fate) | `closed` | `closure` (summary, closed_by, closed_at); every undecided `ran` and `thought` item gets `fate = nothing`, reason "Not reviewed this week"; `read_only = true` |
| `closed` | Nobody | None | Nothing changes. A correction is a note on a later week, never an edit |
| `ready`, `reviewing`, `closing` | Company admin closes a stuck week | `closed` | As above, with `closed_by` the admin and `closed_for = reviewer id` |

A new week is opened by the clock (ruling 3, file 38), not by this table. Stopping or ending the series is file 38 Screen D.

## Records read and written (file or route, fields; mark Existing or New)

| Record or route | Fields | Mark |
|---|---|---|
| `intents/<id>/intent.json` (through `sh_platform/jsonfile.py`, filtered by `sh_platform/profile/view.py`) | Read: people, areas, series schedule. Written: `outcome.weeks[]` summary row per closed week (below) | Existing file (01), new section |
| `intents/<id>/weeks/<week_key>.json` | The week: items, digest, session, closure | New (the file per week, ruling 3) |
| `intents/<id>/events.jsonl` | One line per decision, split, session start, extension, end and close | New (16) |
| `profile/<person>/pulse_mine.json` | The reporter's pointer to their own items (anonymous ones included) | New (39) |
| `GET /api/intents/<id>/weeks/<week_key>` | The week for the viewer: digest, items, decisions, session, closure | New |
| `GET /api/intents/<id>/weeks/<week_key>/mine` | The viewer's own items and decisions | New |
| `POST /api/intents/<id>/weeks/<week_key>/digest` | North's draft digest (system call; refused for a person) | New |
| `PUT /api/intents/<id>/weeks/<week_key>/items/<item id>/decision` | `{fate, reason, fate_ref}` | New |
| `POST /api/intents/<id>/weeks/<week_key>/session` (`start`, `extend`, `end`) | `session` | New |
| `POST /api/intents/<id>/weeks/<week_key>/close` | `closure` | New |
| `GET /api/intents/<id>/trends` | Counts per week per process, repeated items | New |
| Problem start (41), backlog add (21) | Called with the pre-filled fields | Existing by those specs |
| Pulse lines (13) | Reviewer and reporter lines read from the week state | Existing reader, new rows |

Week file shape (ruling 17). Item fields: `id, by|anonymous, kind: ran|broke|thought, text, severity|null, count|null, amount|null, ref|null, topic|null, people_count|null, seen_weeks|null, fate|null, fate_reason|null, decided_by|null`. The week holds:

```
{week_key, area, state, participants_count, responded_count,
 digest: {drafted_at, drafted_by: "north", groups: [{kind, ref|topic, item_ids, line, source_item_ids}], repeats: [{item_id, seen_in: [week_key], matched_by: "north"|"reader", split: bool}], summary_line},
 items: [{id, by|anonymous, kind: ran|broke|thought, text, severity|null, count|null, amount|null, ref|null, topic|null, people_count|null, seen_weeks|null, fate|null, fate_reason|null, decided_by|null}],
 session: {started_at, ended_at, by, minutes_used, extended_by: [{by, at, minutes}]}|null,
 closure: {closed_by, closed_at, closed_for|null, summary, edited_by_person: bool}|null,
 read_only}
```

## Fields this feature adds to the intent record

- `outcome.weeks[]`: `{week_key, closed_at, items_count, broke_count, fates: {problem, backlog, handled, nothing}}`, counts only; the content stays in the week file. Matches ruling 6 (`outcome` is an object from the start).
- In the week file: `digest`, `session`, `closure`, `read_only`, and per item `fate`, `fate_reason`, `decided_by` (ruling 17).
- Fate `handled` beside `problem`, `backlog`, `nothing` (ruling 3). The catalogue (02) needs the line `fates: [problem, backlog, handled, nothing]`.
- No common field in 00-BRIEF section 3 is renamed. `closure.next[]` kind includes `handled` (ruling 19); items with fate `handled` link to the reference they name.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North drafts** the digest when answers close: grouping, ordering, repeat matches, one line per group, the summary, and a draft reason per item. North never decides a fate, never marks severity, never signs, never closes the week. Once the reviewer edits a line or a match, North does not overwrite it (rule 7).
- **North keeps the clock** in the session, says "5 minutes left", and at zero offers **Extend 10 minutes** or **End session**. The reviewer picks.
- **North pre-fills** the Problem and backlog forms from the item. The reviewer presses **Create Problem** or **Add to backlog**. North never creates either.
- **Lens** has no part.
- **Nira** puts "Read the week" on the reviewer's Pulse and "Your items have a decision" on each reporter's Pulse, stating only counts that trace to items. Nira may suggest "Start a Problem from this item" on an item seen for three weeks (a suggestion line, not a decision).
- **People act at**: **Save decision**, **Create Problem**, **Add to backlog**, **Start session**, **End session**, **Extend 10 minutes**, **Close the week**, and **Not the same**.

## Rules (visibility, time box, who may do what)

- **Who decides.** Only the reviewer decides and closes. The company admin may close a stuck week. Nobody else sees the decision control. Observers read and never write.
- **Fates.** Four: `problem`, `backlog`, `handled`, `nothing`. Each needs a reason. `handled` also needs a link; `problem` and `backlog` also need the created record.
- **Required.** Every broke item needs a fate before the week closes. `ran` and `thought` items left undecided close as `nothing` with the reason "Not reviewed this week".
- **Severity.** Shown as the reporters marked it (slowed us, stopped us, cost money, not marked) with their count or amount (file 39). The digest never turns it into one score and North never fills it in. Ordering of broke items uses people reporting and earlier weeks seen, both counts of items.
- **Session.** One working day is the review stage time box (02); the session fits inside it. Extensions are recorded each time.
- **Read-only week.** After closure nothing in the week changes. The series continues in its own next week.
- **No ratings.** Series are not rated and weeks are not rated.
- **Anonymous items.** Reporter names never show on the digest, projector or session. The author sees their item on Screen E only through their anonymous token. The company admin never sees anonymous authorship.
- **Projector.** Item text, counts and the clock, never names; reviewer only (17).
- **Visibility.** Area people see that the week exists and its counts. Participants and observers open the digest and decisions. Affected people open them only when "affected people may read" is on or they are named on a share (ruling 4). Reporters always see their own items with fate and reason. Super admin sees existence only.
- **Numbers.** Counts are exact. Any mean, median or per-person figure shows "Fewer than five" below five records. No per-person figure appears anywhere. Dates and times use the company's time zone from the profile, else UTC.
- **Trends.** "Not available yet" below four closed weeks, naming how many exist. Counts include only closed weeks.
- **Repeat matches** are North's draft and the reviewer may split them. A split is recorded; a match is never hidden.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Traced to | When not available |
|---|---|---|
| Answers per week (people who answered of people asked) | `responded_count`, `participants_count` of the week file | "Not available yet: the week is still collecting." |
| Items per week by kind (ran, broke, thought) | `items[].kind` | Same |
| Broke items by marked severity | `items[].severity` | Same |
| Items by fate (problem, backlog, handled, nothing, no decision) | `items[].decision.fate` | "Not available yet: the week has no decisions." |
| Broke items per week per process | `items[].kind = broke`, `ref` | "Not available yet: trends need four closed weeks." |
| Repeated items and the highest repeat count | `items[].seen_weeks` | Same |
| Review minutes for a week | `session.minutes_used` (ended minus started, plus extensions) | "Not available yet: no review session was run." |
| Mean review minutes across weeks | `session.minutes_used` of closed weeks | "Fewer than five weeks with a session." |
| Weeks closed, weeks with no session | `state = closed`, `session = null` | "Not available yet: no week has closed." |
| Problems and backlog items that came from items | `decision.fate_ref` | "Not available yet: no item has become one." |

These feed the centre counters (19) and the home counters (04).

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `graft ask "shelf reason review date"`, `graft ask "pulse lines"`, `graft ask "projector view timer"`; reads of the v1 spec and files 02, 13, 17, 21, 38, 39, 41. Every path below was checked to exist.

| Existing | Verdict |
|---|---|
| `modules/m1_intent/domain/together.py` L209 `move_to_shelf` (a choice plus a reason, trimmed to `reason_chars`, move recorded with person and time) and `modules/m1_intent/store/together_shelves.py` (audit `moves[]`, atomic write) | **Reshaped.** The pattern is copied in shape: one decision per item, a reason, a history of changes. The four fates replace the shelves. Not imported (shelves belong to clusters). |
| `ui/src/modules/m1_intent/define/DefineScreen.tsx` (shelf choice and reason field) | **Reshaped.** Reason field wording and length message reused; drag is not (this is a decision control). |
| `sh_platform/pulse/lines.py` L71 `line(...)`, L342 `starts`, L350 `running` (organiser lines, counts only) and `sh_platform/pulse/__init__.py` L13 `CAP = 7` | **Reused.** "Read the week" and "Your items have a decision" are new rows built with `line()`, added through the reader file of 13. |
| `sh_platform/pulse/messages.py` L30 `draft()` | **Not used.** No message is sent; Pulse lines do the telling. |
| `modules/m1_intent/domain/timer.py` L25 `ends_at` (extensions, server-held time) | **Reused** for the 30 minute clock and 10 minute extensions. No new time code. |
| `ui/src/modules/m1_intent/wall/WallScreen.tsx` L102 and L156 (projector state and chip) and `wall/Lane.tsx` | **Reshaped** per 17: session mode reuses the toggle, adds the clock and one large item. |
| `sh_platform/jsonfile.py` and `sh_platform/profile/view.py` L167-L183 (anonymous author scrub) | **Reused** as the storage and visibility path. |
| Spec 21 backlog add form and spec 41 Problem start | **Reused by call**, pre-filled; this feature builds neither. |
| Trends table, digest grouping, repeat matching | **New.** The searches above found no weekly aggregation for check-in items. |

## Not in this feature

- Collecting the weekly answers, their wording, severity and links (file 39).
- Series setup, the clock that opens weeks, pause and end (file 38).
- The Problem intent's screens (41) and the backlog's screens (21).
- Sending email or chat messages (13; send is still a 503 draft).
- Sharing a week by link (11) beyond the existing read-only visitor view.
- Ratings of weeks or series.
- Charts beyond the trends table.
- Editing a closed week.

## Open questions

1. The "Nothing" reason and every other reason: is 300 characters the limit (the Define reason limit)? This spec states no number on screen.
2. Should marked severity decide the order of broke items (and in which order: cost money, stopped us, slowed us)? This spec orders by reporters and earlier weeks and only displays severity.
3. Is 30 minutes a default the reviewer may change before the session, or fixed? Is the 10 minute extension and the "5 minutes left" warning right? None is in the brief.
4. How many matched weeks make a "repeat" worth a stronger flag? This spec flags any match with the count and sets no threshold.
5. Four closed weeks before trends show, and the ranges 4 and 8 weeks: not given by the brief.
6. Who closes a week when the reviewer is away more than a day, other than the company admin (02 open question 6)? May the admin decide broke items for the reviewer, or must the reviewer?
7. File 38 says ending the series closes the open week "with what we have", but ruling 3 requires every broke item to have a fate. Which wins?
8. File 38 Screen F ("Read and sort the week") overlaps Screen A here. Which file owns the reviewer's screen, and what is the view name for trends and for the reporter's page (ruling 1 lists no `trends`)?
9. A reporter's anonymous item on another device: this spec ties the view to the token and browser, so losing it loses the view.
10. Should an item with no `ref` be grouped under "Not linked", as here?
11. File 39 stores weeks under `pulse.weeks[]` in the intent file; ruling 3 gives one file per week. 39 should follow. Also confirm `week_key` is the Monday date used as `week_of` in 39.
12. File 02 calls the third kind `mind`; this spec uses `thought` (ruling 2) and needs 02 to follow.
