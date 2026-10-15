# 13. Pulse lines and notifications

Part of: Intent Centre v2. Depends on: 00-BRIEF, 02 (intent types catalogue: stages, closers, time boxes), the intent record (brief section 3), 26 (Define vote), 37 (Brainstorm backing), 38 (Weekly check-in). Feeds: 45 (Nira's whole list reads these rows), every per-type workflow spec (each stage must set the fields read here), the closure and rating specs, the share spec.

## Purpose (three sentences)

An intent only works if the right person finds out it is their turn. This feature fixes every line an intent can put on the Pulse page (`GET /api/pulse`, SHAPES section 1) and every message North drafts for the organiser to send. It adds one reader file for intents beside the readers that exist, keeps the seven-line cap, and says how intent lines compete with the lines that exist today.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Any person | Opens Pulse (the landing page) | A record names them: invited, their turn, a vote, a rating, a share |
| Organiser | Opens Pulse; reads and sends drafted messages | The clock, the people who have not answered, the closure |
| Owner, decider, closer (named in the intent) | Opens Pulse | The intent waits on them |
| Company admin | Opens Pulse (organiser layout) | Sees the organiser strips for the intents they organise, and for existing walls |
| North (agent) | Writes the fields the readers use (`waiting_on`, `votes`, drafts) and drafts messages | Each stage opens, closes or goes quiet |
| Nira (agent) | Reads the intent records and returns lines; stores message drafts | Each `GET /api/pulse` and each draft request |

Agents decide and draft. A person acts at every line: answers, confirms, votes, signs, rates, picks extend, close or cancel.

## Entry points (every route, link, Pulse line, button that leads here)

- `GET /api/pulse`: the new reader `sh_platform/pulse/intent_lines.py` is called from `_strips` in `sh_platform/pulse/__init__.py` (see Reuse check).
- `GET /api/pulse/messages` (drafts the person may send) and `POST /api/pulse/messages/{id}/send`: unchanged routes, new message kinds.
- Pulse page `/` (the landing page, called Pulse and nothing else): the cards. Each card is a link to `href` in the tables below.
- Intent screen `/centre/intent/<id>` (the stage view opens by default) and its views `/centre/intent/<id>/<view>` (brief section 10, ruling 1). Every `href` below is one of these. The only hash used is `#rate`, on the close view (Open question 1).
- Intent home `/centre/intent`: the "And N more" link, and the whole list in file 45.

## Screens, element by element

This feature owns no new screen. It supplies lines to the existing Pulse page and drafts to the existing drafts list.

Route: `/` (Pulse). Layout at 1280: the strips of the viewer's artboard (`layout()` in `__init__.py`: participant, sponsor, data, organiser). At 390: strips stack, the phone tab bar stays. Both are existing; nothing changes except the new line kinds.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Intent card | list (existing `Card`) | `title`, `detail`, "Due <weekday day month>" from `due`, in the company's time zone from the profile, else UTC, the `action` label | Opens `href` | The person the line is for | Strip omitted; if no strip has lines: "Nothing needs you today." (existing) |
| Rating card | list | As above; kind `rating` shows a small "1 minute" note (`MINUTES`) | Opens `/centre/intent/<id>/close#rate` | A participant of a closed Initiative, Brainstorm, Problem or Decision (a weekly check-in is not rated) | Omitted |
| Clock card | list | Working days left of the time box (from `time_box`) and North's proposal in the detail | Opens `/centre/intent/<id>/close` | Organiser and closer | Omitted |
| Outcome card | list (Watch strip, existing `WatchCard`) | The title as the sentence; the label "Shared with you" | Opens the read-only share view `/centre/intent/<id>/share` | A person named on a share | Omitted |
| "and N more" note | panel | "And 3 more in the Intent Centre." The number is `more` from `GET /api/pulse`, the lines cut by the cap. Link to `/centre/intent` | Opens the intent home | Everyone | Not shown when `more` is 0 |
| Drafts list (organiser) | list (existing drafts counter, `panels.drafts`) | Count by message kind, from `pulse/messages.json` (`state: draft`); each draft opens its text | Opens the draft; button "Send" | Organiser who owns the intent, company admin | "No drafts waiting." |
| Send button | button | "Send" | `POST .../send`; today answers 503 and the card says "No email path is set up yet; the message stays a draft." | Same as above | Disabled when no recipient has an address (`accounts.email`): "None of the people named has an address yet." |
| Copy button | button | "Copy text" | Copies `chat` or `body` to the clipboard so the organiser can paste it into any chat | Same as above | Always present on a draft |

## Pulse lines, one row per trigger

LINE shape is SHAPES section 1 and unchanged: `id, kind, title, detail, href, action, due, minutes, source{record, at}`. New: `id` is `intent:<intent id>:<trigger>`, `source.record` is `intents/<intent id>` (the folder; the record is `intents/<id>/intent.json`, ruling 12), `source.at` is the time the record changed to make the line true. `<T>` is the intent title. `<type>` is the type title as shown on screen (Initiative, Brainstorm, Weekly check-in, Problem, Decision). "Pulse" alone is only the daily page; the record key for a check-in stays `pulse` and is never shown. Counts are exact and the page shows counts only, never a mean, so "Fewer than five" does not arise (ruling 8). A date, title or count is read from the record named in Source; when the record lacks it, the line is not made and nothing is estimated. `<stage>` is the stage name. All hrefs are `/centre/intent/<id>` or `/centre/intent/<id>/<view>` as shown. The line lasts only while its record says so, and goes the moment the record changes.

Row 7 reuses the existing signature line; every other row is new. Kinds: existing kinds are reused where one fits (`invite`, `decision`, `request`, `signature`). Three are new: `rating` (1 minute), `clock` (2 minutes), `outcome` (2 minutes). Each needs an entry in `MINUTES` and an icon in `PulsePage.tsx`.

| # | Trigger (record says) | For | Strip | Kind | Title | Detail | href | Action | Due | Source |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Invited: state `open` or `in_session`; the person is in `people.participants` (an adviser is a participant of a Decision) and has not yet acted in the open stage | Participant, adviser. Never an affected person or an observer (ruling 4) | invited | invite | `<T>` | "Janet invited you to a <type>: <purpose>." | Initiative `/centre/intent/<id>/wall`; Weekly check-in, row 13 takes over; others `/centre/intent/<id>` | Brainstorm "Add your ideas"; Decision "Give your view"; Problem "Add what you know"; Weekly check-in "Answer three questions" (row 13 takes over); Initiative "Open the wall" | End of the open stage | `intents/<id>`, `stages[].opened_at` |
| 2 | Your turn: `waiting_on.person` is the viewer and the stage is open | Whoever North named: reader, owner, reporter, adviser, organiser | decide | decision | "Your turn on `<T>`" | North's one-line ask from `waiting_on.what`, e.g. "The ideas are in. Pick the one to take forward." | `/centre/intent/<id>` | Wording per type and stage in the table below | End of the open stage | `intents/<id>`, `waiting_on.since` |
| 3 | A start question unanswered: state `draft`, `created_by` is the viewer, a required start question has no answer | Person who began it | decide | decision | "Finish starting `<T or 'your <type>'>`" | "<n> questions are left. North cannot plan the work until they are answered." (n is counted from `start_answers` against the type's required questions in file 02) | `/centre/intent/new?type=<type>&draft=<id>` | "Answer them" | None | `intents/<id>`, `start_answers` |
| 4 | A card to confirm: a North draft of the viewer's own words (a Weekly check-in item from their answer; a Problem statement for the reporter) has `confirmed_by` empty | The author of the words | decide | decision | "Check what North wrote for you" | "North turned your answer into a short card. Keep it, change it, or delete it." | `/centre/intent/<id>` | "Check the card" | End of the open stage | `intents/<id>`, `drafts_to_confirm[]` |
| 5 | A vote or backing open: a `votes[]` entry has `state: open` and the viewer is in its `voters` and not in `cast_by`. Two uses exist: the Define vote on a cluster (file 26: Must, Should, and the rest) and the Brainstorm backing of up to three ideas (file 37, stage `choose`) | Voters | decide | decision | Define: "Vote: `<question>`"; Brainstorm: "Back up to three ideas in `<T>`" | "<n> of <m> have voted. The vote closes <date>." (counts only, never who) | Define `/centre/intent/<id>/define`; Brainstorm `/centre/intent/<id>` | Define "Vote"; Brainstorm "Back your ideas" | `votes[].closes` | `intents/<id>`, `votes[]` |
| 6 | A definition to confirm: a Lens draft term in `definitions_waiting[]` names the viewer as the one who confirms (the business owner, data owner or source owner named for the term) | That owner | decide | decision | "A term needs your confirmation: `<term>`" | "Lens drafted the meaning from the intent. Confirm it, or write your own." | `/centre/intent/<id>/define` | "Confirm" | End of the open stage | `intents/<id>`, `definitions_waiting[]` |
| 7 | A signature wanted: an Initiative charter is `awaiting_approver` and the viewer is the approver | Sponsor | decide | signature | "A charter waits for your signature" | The approver's name (existing wording) | `/centre/intent/<id>/charter` | "Review and sign" | None | `charters/<sid>` (the intent record points to the wall session id) |
| 8 | Time box at 20 percent (Nitin's figure, Open question 5): state `open` or `in_session`; the type is not a Weekly check-in (its week has its own clock, file 38); working days left are 20 percent or less of the working days in the time box (`starts` to `ends`, extensions included), and the intent is not yet overdue | Organiser and closer. A closer who is also the organiser sees one line | watch; moves to decide when North says the clock will not hold (the sum of `default_days` of the stages not yet closed is more than the working days left) | clock | "`<T>`: 2 working days left of 10" | On track: "North expects to finish in time." Will not hold: "North does not expect to finish in time. Pick one: extend, close with what we have, or cancel." | `/centre/intent/<id>/close` | On track "Open it"; will not hold "Choose" | `time_box.ends` | `intents/<id>`, `time_box` |
| 9 | Overdue: `now` is after `time_box.ends`, the type is not a Weekly check-in, and state is not `closing`, `closed` or `cancelled` | Organiser and closer (the person whose turn it is also keeps row 2) | decide | decision | "`<T>` is overdue" | "It ended on <date>. Pick one: extend, close with what we have, or cancel." | `/centre/intent/<id>/close` | "Choose" | `time_box.ends` (past, so it sorts first) | `intents/<id>`, `time_box` |
| 10 | Closure to sign (per-type confirmer): state `closing` and `closure.signed_by` empty; the viewer is the per-type confirmer: sponsor (Initiative), decider (Decision), owner then reporter (Problem), or nobody (Brainstorm, Weekly check-in week). For a Weekly check-in the state is that of the week (`intents/<id>/weeks/<week_key>.json`) and the closer is the reviewer | Confirmer | decide | signature | "`<T>` is ready to close" | "North drafted why it happened and what came out. Read it, then close it." | `/centre/intent/<id>/close` (a week: `/centre/intent/<id>/review`) | "Review and close" | None | `intents/<id>`, `closure` draft, `closure.signed_by` |
| 10a | Close this intent: state `closing` and per-type confirmer has acted (or no confirmer exists for the type); the viewer is the organiser | Organiser | decide | decision | "Close `<T>`" | "All confirmers have acted. Close the intent." | `/centre/intent/<id>/close` | "Close it" | None | `intents/<id>`, `closure` |
| 11 | Rating wanted: state `closed`, the type is not a Weekly check-in (series and weeks are not rated, ruling 3), the viewer was a participant and has no entry in `ratings`, and the intent closed within 7 days (placeholder, Open question 4) | Participants | give | rating | "How did `<T>` go?" | "Give a score from 1 to 5 and a line if you wish. You may rate without your name." | `/centre/intent/<id>/close#rate` | "Rate it" | Seven days after `closure.closed_at` | `intents/<id>`, `closure.closed_at`, `ratings` |
| 12 | Outcome shared with you: `share.who_may_open` names the viewer, or the viewer is affected and the organiser switched on "affected people may read" at creation (default off, ruling 4); the intent is closed; the viewer is not a participant | People named on a share, or affected people where that switch is on | watch | outcome | "Shared with you: `<T>`" | `closure.summary`, first 140 characters (placeholder, Open question 11) | `/centre/intent/<id>/share` (read-only view) | "Read what came out" | None | `intents/<id>`, `share` |
| 13 | A check-in week open: a Weekly check-in intent, this week's stage `collect` open, the viewer is a participant and has no answers this week | Participants of the area | give | request | "Your week for `<area>`" | "Three questions: what ran well, what broke or nearly broke, what is on your mind. About 5 minutes." (the `request` entry in `MINUTES`) | `/centre/intent/<id>/week` | "Answer three questions" | `collect` end | `intents/<id>/weeks/<week_key>.json`, stage `collect` |
| 14 | A problem assigned to you: Problem intent, state `open`, `describe` stage, the viewer is `people.owner` and has not accepted | Owner | decide | decision | "A problem needs an owner: `<T>`" | "Janet reported it: <purpose>. Take it, or hand it back with a reason." | `/centre/intent/<id>` | "Take it" | `time_box.ends` | `intents/<id>`, `owner_accepted_at` |
| 15 | A decision wanted from you: Decision intent, stage `decide` open, the viewer is `people.decider` | Decider | decide | decision | "A decision waits for you: `<T>`" | "<n> advisers have given views and <m> options are set out (counted from the stage records). Choose one and give the reason." | `/centre/intent/<id>` | "Decide" | `time_box.ends` | `intents/<id>`, `stages`, `people` |
| 16 | People who have not answered: state `open` or `in_session` and some of the people have not acted in the open stage | Organiser | waiting (organiser layout) or watch (others) | request | "`<T>`: 3 of 6 have not added ideas" | "Draft a reminder, extend the stage, or move on." Counts only, never who (same rule as `running()` today) | `/centre/intent/<id>/people` | "See who to remind" | End of the open stage | `intents/<id>`, `stages`, `people` |
| 17 | A process step to confirm: a Lens draft step or lane in `process_waiting[]` names the viewer as the business owner of the process and `confirmed_by` is empty (file 45 reads this row; file 27 owns the content) | That business owner | decide | decision | "A process step needs your check: `<step>`" | "Lens drafted the step from the intent. Confirm it, or write your own." | `/centre/intent/<id>/define` | "Check the step" | End of the open stage | `intents/<id>`, `process_waiting[]` |

A new check-in week opens by the clock on the next working day after the close day, even if the last week's review is unfinished. The reviewer may then hold row 2 for the old week and row 13 for the new one; the old week's line is kept (one line per person per intent) and the other waits. Item kinds are `ran`, `broke`, `thought`.

Wording for row 2 by type and stage (the action label is the button; `waiting_on.what` is North's sentence for the detail):

| Type, stage | Who | Action | Example detail |
|---|---|---|---|
| Brainstorm, `choose` | Organiser | "Choose the idea" | "Six people added 14 ideas. Pick the one to take forward." |
| Weekly check-in, `review` | Reviewer | "Read the week" (`/centre/intent/<id>/review`) | "Five people answered. North grouped the repeats." |
| Weekly check-in, `sort` | Reviewer | "Give each item a fate" (`/centre/intent/<id>/review`) | "7 items need a fate: ops problem, backlog item, handled, or nothing, with a reason. Each one that broke needs one before the week closes." |
| Problem, `find_cause` | Owner (`people.owner`) | "Add the cause" | "North drafted a cause from the evidence. Confirm it or write your own." |
| Problem, `fix` | Owner | "Name the fix" | "Say what fixes it and who does it." |
| Problem, `confirm` | Reporter (`people.reporter`) | "Confirm it is gone" | "Harvey says the fix is done. Is the problem gone?" |
| Decision, `options` | Adviser (a participant) | "Give your view" | "Daniel asked for your view on each option." |
| Initiative, `define_strategically` | Organiser | Existing `define:<sid>` line, not repeated | none |
| Initiative, `build_ready` | Sponsor (`people.sponsor`) | "Check the build-ready list" | "North found 2 gaps. Say whether to hand over now." |

### One line per person per intent

A person gets at most one line from one intent at a time. If several triggers are true, the highest in this order wins and the others wait for their turn: closure to sign (10), close this intent (10a), decision wanted (15), overdue (9), your turn (2), problem assigned (14), vote open (5), card to confirm (4), definition to confirm (6), signature (7, which is also an existing line and keeps its own id), process step to confirm (17), start question (3), time box 20 percent (8), check-in week (13), invited (1), rating (11), outcome shared (12). Row 16 is the organiser's and is separate from the person's own line. This stops one busy intent from filling the page.

### What is not a line

- Area members who are not participants or affected get no line. They see the intent in the Intent Centre list (brief section 4). A line is an act or a share, never a notice of existence.
- An intent a person may only see exists (super admin, company admin) gives no line.
- A cancelled intent gives no line to anyone. Participants see the reason on the intent.
- An affected person or an observer gets no act line (ruling 4); an affected person gets row 12 only where the organiser switched on "affected people may read" or a share names them. A draft intent gives a line to its creator only (row 3, ruling 14). An anonymous author is never named in a line. A line that says how many have answered gives a count, never a name.

## Competing for seven lines

Today `build()` in `sh_platform/pulse/__init__.py` fills strips in order, orders each strip by due date (none last), then newest record first, and cuts at `CAP = 7`, so the last strip (Watch) loses first. Intents join that same contest. They do not get reserved places and they are not cut first.

1. Intent lines are added to the same four strip lists (and to `start`, `running`, `waiting` for the organiser layout), so the cap, the order and the "a record shown in an earlier strip is not repeated" rule apply to them as they do to every line.
2. Within a strip the earliest `due` wins. An overdue line has a past `due` and so comes first. A line with no `due` comes after one with a due date.
3. Intent lines and existing lines (walls, baselines, data requests, signatures, ops) sit in the same order. A person who is a sponsor in two worlds sees the earliest due date first, whatever its source.
4. Duplicates: when an Initiative's stage already has an existing line, the intent reader does not make a second one. It uses the existing id, so the existing de-duplication catches it: wall invite is `invite:<session id>`, the organiser's wall is `running:<id>`, closed wall without a charter is `define:<id>`, the charter signature is `sign:charter:<id>`, the baseline measure confirmation is `confirm:<baseline>:<kpi>`.
5. The cap hides lines silently today. This feature adds one field to the response: `more` (integer, the lines cut). It is the number counted in `build()`, never estimated. The page shows "And N more in the Intent Centre." when `more` is above 0.
6. Minutes: `minutes` on the response is the sum over lines shown, as today. `MINUTES` gains `rating: 1`, `clock: 2`, `outcome: 2`. The new rows reuse `invite: 5`, `decision: 3`, `request: 5`, `signature: 5`.

## Drafted messages (email and chat)

Messages stay at `/api/pulse/messages`. A draft is created by `draft(plane, kind, record)` in `sh_platform/pulse/messages.py`. It is written by a function in `sh_platform/pulse/templates.py` (no model call, words and dates only, no figure, no row). It waits in `pulse/messages.json`. Only the organiser of that intent or a company admin may send (`_may`). Send answers 503 "No email path is set up yet; the message stays a draft." until `app.state.email_sender` exists; nothing else changes when it does.

Two fields are new on each message: `chat` (the same ask in 240 characters or fewer, plain text, for pasting into a chat tool; the Copy button copies it) and `link` (the `href` of the matching Pulse line, so the message opens the right screen, not "the sign-in page"). Intent messages are signed "North", because North drafts them; the existing five stay signed "Nira".

A repeated nudge needs its own id. `draft()` makes the id from `kind` and `from_record` and returns the old draft if asked again, so `from_record` for a nudge is `intents/<id>#<trigger>:<stage>:<date>`; a one-off message uses `intents/<id>#<trigger>`.

| Trigger (row) | Kind | To | When North drafts it | Subject | Body (plain text) | Chat |
|---|---|---|---|---|---|---|
| Invited (1) | `intent_invite` (reshapes `invite`) | The people named | The intent opens | "You are invited: `<T>`" | "Hello, Janet is running a `<type>` on `<purpose>` and would like you to take part. It runs until `<ends>`. Open it here: `<link>`" | "Janet invited you to `<T>`. It runs until `<ends>`. `<link>`" |
| Your turn (2), card to confirm (4), definition to confirm (6), vote (5), process step (17) | `intent_nudge` (reshapes `reminder`) | The one person whose turn it is | The stage has waited a working day on them, then once each day while it waits | "A reminder: `<T>` is waiting for you" | "Hello Aaron, `<what>`. The stage closes `<due>`. Open it here: `<link>`" | "`<T>` is waiting for you: `<what>`. `<link>`" |
| People not answered (16) | `intent_nudge` | Those who have not acted (the organiser sees the draft with the names; the Pulse line shows a count only) | The organiser clicks "See who to remind" | As above | As above | As above |
| Problem assigned (14) | `intent_owner` (reshapes `owner_ask`) | Owner | The Problem opens | "A problem needs an owner: `<T>`" | "Hello Harvey, Janet reported: `<purpose>`. Could you take it, or tell us who should? Open it here: `<link>`" | "Janet asks you to own `<T>`. `<link>`" |
| Decision wanted (15) | `intent_decide` | Decider | The `decide` stage opens | "A decision waits for you: `<T>`" | "Hello Daniel, the options are set out and `<n>` views are in. Please choose one and give the reason. Open it here: `<link>`" | "Decision wanted on `<T>`. `<link>`" |
| Check-in week (13) | `intent_week` | Participants of the area | `collect` opens, and once more the day before it ends | "Your week for `<area>`" | "Hello, three short questions: what ran well, what broke or nearly broke, what is on your mind. It closes `<date>`. Answer here: `<link>`" | "Three questions for your week: `<link>`" |
| Process step to confirm (17) | `intent_nudge` | The one business owner | As the other nudges | As above | As above | As above |
| Time box 20 percent (8) and overdue (9) | None | none | The line is for the organiser and closer, who decide. North drafts nothing to others until a person picks | none | none | none |
| After "Extend" is picked (8, 9) | `intent_extended` | All participants | The organiser or closer picks extend and gives the reason | "`<T>` now ends `<new date>`" | "Hello, `<T>` has been extended to `<new date>`. Reason: `<reason>`. Open it here: `<link>`" | "`<T>` now ends `<new date>`. `<link>`" |
| Closure to sign (10) | `intent_close_ask` | Closer | State becomes `closing` | "`<T>` is ready to close" | "Hello Daniel, North drafted why it happened and what came out. Please read it and close it. Open it here: `<link>`" | "`<T>` is ready for you to close. `<link>`" |
| Rating wanted (11) | `intent_rating` | Participants | The intent closes; again once on day 5 for those who have not rated | "How did `<T>` go?" | "Hello, `<T>` is closed. Please give a score from 1 to 5 and a line if you wish. You may rate without your name. Rate it here: `<link>`" | "How did `<T>` go? `<link>`" |
| Outcome shared (12) | `intent_share` | People the share names | The organiser clicks "Share" | "Shared with you: `<T>`" | "Hello, Janet shared what came out of `<T>`. It is read only. Read it here: `<link>`" | "Janet shared `<T>` with you. `<link>`" |
| Start question (3), signature (7) | None | none | The person is told on Pulse; the existing sponsor ask and charter lines need no message | none | none | none |

British spelling, no em dashes, short sentences, no model or vendor name in any message. `sponsor_ask`, `ops_report` and `owner_ask` are untouched.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

Example: Janet (organiser) opens a Brainstorm with Aaron, Katie and three others.

1. Janet clicks "Open this intent". North writes the record and drafts `intent_invite` once. The drafts list shows "1 draft".
2. Janet reads the draft, clicks "Send". Today the answer is 503 and she clicks "Copy text" and pastes the chat line. She tells nobody to wait; the Pulse lines do the rest.
3. Aaron opens Pulse. Nira reads the record and returns row 1: "Brainstorm: faster month-end close", action "Add your ideas", due the end of the first stage.
4. Aaron adds his ideas. The next `GET /api/pulse` no longer returns row 1 (his name is in the stage's authors).
5. A working day passes. Katie has not acted. North drafts `intent_nudge` for Katie. Her Pulse line stays row 1; the organiser's layout shows row 16 as "2 of 5 have not added ideas".
6. The live session ends. North writes `waiting_on` to Janet. Her Pulse shows row 2, "Choose the idea".
7. Two working days of three are left of the time box and North does not expect to finish. Row 8 moves to Janet's decide strip. She clicks "Choose", then "Extend by one day" and writes a reason. North drafts `intent_extended` for all.
8. Janet picks the idea. The state becomes `closing`. Brainstorm has no per-type confirmer, so row 10a shows to Janet (organiser); she reads North's draft and clicks "Close it".
9. Closure writes `closed_at`. Each participant gets row 11 for seven days. Daniel, named in the share, gets row 12 in Watch.
10. A line the person has dealt with is gone on the next read. Nothing needs "Done".

## States and transitions (table: state, who moves it, to what, what is written)

Lines hold no state of their own. They are derived on each read. The only states are the draft states of a message and the fields North writes.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| Line true | The record changes (a person acts, a stage opens, the clock passes) | Line present | Nothing; the line is computed |
| Line false | A person acts, or the record changes again | Line gone | Nothing |
| Message `draft` | North drafts it | `draft` (waits) | `pulse/messages.json`: `id, kind, to, subject, body, chat, link, drafted_at, state, from_record, organiser_account_id` |
| Message `draft` | Organiser or company admin clicks "Send", an email path exists | `sent` | `sent_by`, `sent_at` (existing) |
| Message `draft` | Same click, no email path | stays `draft` | Nothing; answer 503 (existing) |
| Message `draft` | Intent closes or is cancelled | stays `draft`, hidden from the organiser's list | A new field is not needed: the list filters by the intent state |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Mode | Fields | Mark |
|---|---|---|---|
| `GET /api/pulse` | read | strips, lines, `minutes`, `map`, `panels` | Existing |
| `GET /api/pulse` response field `more` | write | integer, lines cut by the cap | New |
| `intents/<id>/intent.json` | read | `type, title, purpose, state, people (incl. decider, owner, reporter), areas, stages, time_box, closure (incl. closed_by, closed_at, cancel_reason), ratings, share, start_answers, waiting_on, votes, drafts_to_confirm, definitions_waiting, process_waiting, owner_accepted_at, nudges` | New |
| `intents/<id>/weeks/<week_key>.json` | read | the open week's stage, answers and state (Weekly check-in only, file 38) | New |
| `intents/m1_intent/sessions/*`, `rooms/*`, `stages/*`, `note_authors/*`, `charters/*` | read | as the existing readers | Existing |
| `intents/m2_baseline/*/governed_state.json` | read | as `measures` | Existing |
| `pulse/messages.json` | read, write | message fields above | Existing, two fields New (`chat`, `link`) |
| `GET /api/pulse/messages`, `POST /api/pulse/messages/{id}/send` | read, write | as today | Existing |
| `accounts` (`app.state.account_store`) | read | `email` | Existing |

## Fields this feature adds to the intent record

- `waiting_on`: `{person: {account_id, name}, what: text, since: iso} | null`. North writes it when a stage opens or the turn passes; a person's action clears it. Row 2 reads it.
- `votes`: `[{id, question, options: [text], voters: [account_id], cast_by: [account_id], opens, closes, state: open|closed}]`. Row 5 reads it. Votes are anonymous in count only, so `cast_by` is kept for who has voted, never what.
- `drafts_to_confirm`: `[{id, author: account_id, text, confirmed_by|null}]`. Row 4 reads it.
- `definitions_waiting`: `[{term, owner: account_id, drafted_by: "Lens", state: open|confirmed}]`. Row 6 reads it.
- `process_waiting`: `[{id, step, owner: account_id, drafted_by: "Lens", confirmed_by: account_id|null, state: open|confirmed}]`. Row 17 reads it. File 27 owns the content; file 45 names the same field.
- `owner_accepted_at`: iso or null, for Problem. Row 14 reads it.
- `nudges`: `[{kind, at, message_id}]`, so North does not draft more than one nudge a day for one person.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** writes `waiting_on`, `drafts_to_confirm`, the stage clock and the message drafts. It drafts a nudge after a working day of waiting, then at most once a day. It drafts nothing for time box and overdue; it writes its proposal into the line detail and the organiser or closer picks. Person acts: the person named on the line.
- **Lens** writes `process_waiting` and `definitions_waiting` (a drafted meaning from the intent text and the pack, marked as a suggestion). Person acts: the named owner confirms or rewrites.
- **Nira** reads the records and returns the lines on each request, and stores the drafts. Nira writes no field and sends nothing. Person acts: every line has an action; every send is a person's click.
- No agent signs, votes, rates, closes or decides.

## Rules (visibility, time box, who may do what)

- A line is for the viewer only, matched by `account_id` (as `_mine` and `invited` do today). A person with no account never gets a line from an intent; their name appears in the organiser's drafts only if an address exists.
- Restricted and sealed items never appear to anyone outside their list (SHAPES 1). An anonymous author is never named in a line or message. Counts are of distinct people, never who.
- The company admin and super admin see existence on the Intent Centre list, never a line for an intent they are not part of.
- Time box: the clock counts working days, Monday to Friday, as the wall window does (`modules/m1_intent/contracts/intent_session.yaml` (checked: exists)). Extensions add to `ends`, so the 20 percent is measured on the extended time box.
- Messages: only the organiser of that intent and a company admin may send. Nothing is sent without a click. A message needs the person to have an address on their account.
- At most three open questions to one person across Define (process map, glossary, catalogue, governed state together, A-045): rows 6 and 17 together make at most three lines for one person; the next waits until one is answered (ruling 9).
- A Pulse line always names its action. No line says "FYI".

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Where | Traced to |
|---|---|---|
| Lines shown, lines cut (`more`) | Pulse response | the same list the cap acted on |
| Intent drafts waiting by kind | Organiser panel `drafts` | `pulse/messages.json`, `state: draft` |
| Messages sent this week | Organiser panel (new stat, "Not available yet" until an email path exists) | `pulse/messages.json`, `sent_at` |
| Lines by trigger for one person today | Not shown to anyone; used in tests | the readers |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Read directly from the files named; every path below was checked to exist on 7 October 2026 (`sh_platform/pulse/__init__.py`, `lines.py`, `messages.py`, `templates.py`, `sh_platform/jsonfile.py`, `ui/src/pages/PulsePage.tsx`, `ui/src/pages/pulseCopy.ts`, `modules/m1_intent/contracts/intent_session.yaml`, `docs/plan/SHAPES.md`).

Exists today and is reused as it is:
- `sh_platform/pulse/__init__.py` lines 13 (`CAP = 7`), 16-19 (`_order`), 31-44 (`_strips`), 58-69 (`build`, includes the repeat rule at 63): reused. One edit: count lines cut into `more`, and add the intent readers into `_strips`.
- `sh_platform/pulse/lines.py`: `line()` (71-74), `safe` (60-68), `MINUTES` (23), `invited` (113-127: wall invite, `invite:<sid>`), `interview` (129-142), `measures` (144-160: confirm measure, `confirm:<b>:<kpi>`), `signatures` (175-195: charter, baseline, plan), `purpose_asks` (244-252: sponsor gives the purpose line), `starts` (342-346: sponsor ask), `running` (350-372: organiser's wall and the closed wall with no charter), `waiting` (386-391), `requests` (266-279). These stay. They are the lines for Initiative's wall and Define stage, so rows 1 and 7 for an Initiative are these lines, not new ones.
- `sh_platform/pulse/messages.py`: `draft` (30-47), `_may` (50-52), list route (62-65), send route (68-95; the 503 is at 86-87): reused. Edits: `draft` stores `chat` and `link` when given.
- `sh_platform/pulse/templates.py`: `KINDS` (4), `WRITERS` (last lines), the writers `invite`, `reminder`, `owner_ask`: reshaped into `intent_invite`, `intent_nudge`, `intent_owner`; same helpers `_who`, `_link`.
- `ui/src/pages/PulsePage.tsx` (via graft): `Kind` (16), `ICON` (30-32), `STRIP_ICON` (34), `Card` (42-46), `WatchCard` (56-60), `summarise` (128). Reused. Edits: add three kinds and icons, render `more`.
- `ui/src/pages/pulseCopy.ts`: `strips` (5-8), `amber` (9), `watchLabel` (40), `kinds` (class names for the data and sponsor day): add `clock`, `rating`, `outcome` words there.

New:
- `sh_platform/pulse/intent_lines.py`: one small reader per trigger (rows 1-6, 8-16), each `(plane, viewer, now) -> [LINE]` with `@safe`, same style as `lines.py`. Reads `intents/<id>/intent.json` by path through `sh_platform/jsonfile.py`.
- Ten message writers (`intent_invite` ... `intent_share`) in `templates.py`.
- The `more` field; the fields above on the intent record.

Not copied from the earlier repo: nothing was found there that makes a day's lines from intent records. Not used: a notification centre, a bell, a push or an email digest. The Pulse page is the one place.

## Not in this feature

- Sending email or chat itself (no mail server; Send answers 503 until `app.state.email_sender` exists).
- A bell, push, digest, or read receipt.
- The intent screen, the chooser, the votes screen, the rating screen, the share screen (other specs; this feature only links to them).
- Existing lines for ops, data requests, gaps, market brief, release and blueprint signature: unchanged.
- Reminders to people without an account.

## Open questions

1. The rating panel has no view in the ruling 1 list. This spec uses `/centre/intent/<id>/close#rate`; file 10 still writes `/centre/intents/<id>/rate`, which is a wrong spelling. The ruling must name the view. Also `draft=<id>` on `/centre/intent/new` is not in ruling 1.
2. `people` entries need `account_id` as well as the name, so `_mine`-style matching works. The brief shows names only. Proposed: `{account_id, name}`.
3. Votes: the brief does not define a vote, but two exist in the specs: the Define vote (file 26, Must and Should against the rest) and the Brainstorm backing (file 37, up to three ideas). Row 5 keeps one line for both through a `votes` field. Who writes `votes[]` for each (the Define board and `TogetherStore` hold their own counts today), and whether a decision's advisers vote at all, is open.
4. Rating window of 7 days and the "day 5" second message are placeholders. Is there a rule? They are held in one constant.
5. Time box at 20 percent is Nitin's number. Whether it is measured on working days (assumed) or calendar days needs confirming.
6. "North expects to finish" is derived here from the stages not yet closed against the working days left. A better measure may exist.
7. Should an organiser who is not a company admin get the organiser strips (`start`, `running`, `waiting`)? Today `layout()` gives them only to the company admin; this spec puts their lines in the four common strips.
8. Intent messages signed "North" and the 240-character chat text are proposals; the existing five are signed "Nira".
9. When an email path arrives, should one nudge per person per day be enforced in code (the `nudges` field) or only by North's behaviour?
10. Does the `more` field belong in SHAPES section 1? It changes the response shape; the SHAPES owner decides.
11. The 140 characters of an outcome line, the 240 characters of a chat text, "one nudge after one working day, then once a day", and the "one line per person per intent" order of priority are proposals, not brief rules. File 45 sorts its own list by group (signature, decision, others), then due date; confirm the two orders may differ.
12. Rows 8 and 9 are switched off for a Weekly check-in, because its week has its own clock (file 38). Confirm no time box line is wanted for the series.
13. Section 4 of the brief says affected people see existence only; row 1 now excludes them, so an affected person with "affected people may read" on gets only row 12 after closure. Confirm no earlier line is wanted.
