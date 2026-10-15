# 42. Problem resolution and closure

Part of: Intent Centre v2. Depends on: 01 (intent record), 02 (Problem type), 07 (time box), 08 (North runner), 09 (closure), 10 (ratings), 13 (Pulse lines), 20 (linking intents), 22 (Initiative start, pre-fill), 41 (Problem start and triage). Feeds: 19 (centre counters), 12 (past intents), 21 (backlog), the Ops page and NodePage.

## Purpose (three sentences)

This feature is the working screen of a Problem intent, from "owner holds it" to "closed with a root cause and a fix". The owner drives it, North keeps a running "what we know" summary and drafts the root cause, and the people who feel the problem say whether it is fixed for them. When it ends, the fix is written to the measure or process it concerns and to the Ops alert it came from, so the next reader of that node sees what happened.

## Who uses it and when (role, moment, trigger)

"Content readers" below means: participants, observers (read only), affected people when the organiser switched on "affected people may read" at creation (default off, brief ruling 4), and people named on a share link. Affected people without that switch see the header and their own answer row only.

| Role | Moment | Trigger |
|---|---|---|
| Owner (Harvey, `people.owner`) | Works the problem for up to 5 working days: adds notes, confirms the root cause, records the fix, closes | Pulse line "Problem P-123 is yours: 4 days left" |
| Reporter (Katie, `people.reporter`) | Adds evidence, then confirms the fix or reopens once | Pulse line "Harvey says P-123 is fixed. Is it fixed for you?" |
| Affected person (Aaron, in `people.affected`) | Taps "It is fixed for me" or "Still happening for me"; adds a note when the switch is on | Pulse line from Nira |
| Organiser (the person who opened the intent, usually the reporter) | Changes the owner; turns the problem into an Initiative when it is bigger than a fix | Owner or reporter says "this is bigger than a fix" |
| Approver (Grace) | Not in this flow. A Problem needs no signature (spec 09) | None |
| Company admin, super admin | Company admin sees existence and outcome, never anonymous notes; super admin sees existence only, never content (brief section 4, ruling 5) | Home page list |

## Entry points (every route, link, Pulse line, button that leads here)

- Route `/centre/intent/<id>` for an intent of type `problem` in state `open` or `in_session` renders this screen as the stage view that opens by default (the intent shell from spec 04 chooses the screen by type). `/centre/intent/<id>/close` (view `close`) is the closure screen of spec 09, reached by the "Close this problem" button.
- Pulse line (Nira, spec 13): "You own problem P-123", "P-123 has no cause yet and 2 days left", "Harvey says P-123 is fixed. Is it fixed for you?", "Problem P-123 was reopened".
- Weekly check-in review (specs 02 and 40): a week item with fate `problem` opens `/centre/intent/new?type=problem&from=<check-in id>&item=<item id>` (spec 20). The new Problem has `links.from` set. Spec 41 asks the start questions and takes the owner's Accept; this screen starts once the owner holds the problem.
- Ops page `/ops` (`ui/src/pages/OpsPage.tsx`, alert card): new button "Start a problem" on an open alert, as in spec 41. It goes to `/centre/intent/new?type=problem&alert=<alert id>`; the start questions are pre-filled from the alert (source, measure, source owner). The alert id is stored in `links.alert`.
- NodePage (`ui/src/pages/NodePage.tsx`) of a measure or process: link "Report a problem with this" goes to `/centre/intent/new?type=problem&node=<node id>` and sets `links.node`. The `alert` and `node` query keys are not in brief ruling 1 (open question 10).
- Home page card (spec 04, `/centre/intent`) of a running Problem.
- A reopen notice to the owner (Pulse line) points back to `/centre/intent/<id>`.

## Screens, element by element

### A. Problem screen (route `/centre/intent/<id>`, type `problem`)

Layout at 1280: top bar; header band across the full width (title, id chip "P-123", state chip, clock, owner). Below, two columns. Left, 8 of 12: "What we know" panel, then the thread, then the root cause block, then the fix block. Right, 4 of 12: "Affected people" panel with the confirm taps, the "Bigger than a fix" panel, "Linked to" panel (node, alert, source intent). Sticky footer bar with "Close this problem".

Layout at 390: one column in this order: header band (clock and owner on two lines), what we know, root cause, fix, confirm taps, thread, bigger than a fix, linked to. The footer button stays sticky. The thread collapses to the latest notes with "Show all notes".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Problem header | panel | Title, purpose line, "Reported by Katie on 5 Oct" (from `people.reporter` and `created_at`), stage chip (Describe, Find the cause, Fix, Confirm) | Pencil on the title and statement (organiser, owner) edits `outcome.what`; an edit logs a note "Statement changed" | Everyone who may see the intent exists: title, purpose, stage, state, people. Statement text: content readers | Title is required before the intent can open (spec 01) |
| Clock | chip | "Day 3 of 5, ends Fri 10 Oct" from `time_box`, and the days left in the current stage (spec 07). Dates use the company time zone from the profile, else UTC | None. Red text when the box has ended: "Past the time box by 1 day" | Everyone who may see the intent exists | "Not started" while the intent is `draft` |
| Owner | chip | "Owner: Harvey" from `people.owner`, with a small "Change owner" link | Link opens a person picker (organiser only); the change is written to `people.owner` and as a note "Owner changed from X to Y"; the new owner gets a Pulse line | Everyone who may see the intent exists | "No owner yet. Name one to open this problem." Open is blocked |
| What we know | agent line (read-only text, 3 to 6 sentences) | North's running summary of the statement and all notes, each sentence with a source chip ("Note by Aaron, 6 Oct", "Ops alert, 5 Oct") | Chip opens the note or record in a side panel. "Refresh" button asks North to redraw it. Owner may pin a sentence ("Keep this wording"); a pinned sentence is never redrawn | Content readers | "Nothing is known yet. Add the first note." |
| Thread | list | Notes, newest last: author, role chip (owner, reporter, affected), time, text, optional attachment link to an Ops record | None per note; notes are never edited, only added to (an author may add a correction note) | Content readers | "No notes yet. The owner, the reporter and the affected people can add one." |
| Add a note | field + button "Add note" | Text up to 2000 characters (the limit of the node comment flow), checkbox "Add without my name" | Appends a note; North redraws What we know; the other people get no notification unless they are mentioned | Owner, reporter, affected people when the read switch is on, other participants. Observers read only | Button disabled until text is typed |
| Anonymous note | list item | Text with "Anonymous" and no author | Counted in "Anonymous: n" in the people panel; the company admin never sees it (brief section 4) | Content readers, not the company admin | Not shown when none |
| Root cause block | panel | Status chip (Draft by North, Confirmed by Harvey on 7 Oct), the cause in one or two sentences, a "Based on" list of the notes and Ops records it used | "Draft cause" button (owner) asks North to draft from the notes and Ops records. "Confirm cause" (owner) signs it as the owner's. "Edit" lets the owner rewrite it; an edited cause is marked "Written by Harvey" | Content readers | "No cause yet. North drafts one when the owner asks." |
| Draft cause button | button | "Draft the cause" | Runs North; shows a draft and questions "What would settle this?" (at most 3, A-045) | Owner | Disabled with "Add a note first" when the thread has none and no Ops record is linked |
| Confirm cause | button, primary | "Confirm this cause" | Writes `outcome.root_cause` with `confirmed_by` and `confirmed_at`; stage moves to `fix` | Owner only | Disabled with "Draft or write a cause first" |
| Cause not known | link | "We cannot find the cause" | Opens a dialog: reason required. Writes `outcome.root_cause = {unknown: true, reason}`; closing is then only possible as "no fix, accepted" or as a workaround (open question 3) | Owner | Shown only after the stage `find_cause` has used its days |
| Fix block | panel | Radio "Fixed" or "Workaround". Fixed: what was done, by whom, when. Workaround: what we do instead, by whom, and "real fix by" date | "Save fix" (owner). The "by" field picks from people in the company profile; "when" is a date field | Content readers | "No fix recorded yet." Locked until the root cause is confirmed or marked unknown |
| What was done | field | Text up to 2000 characters | Edit in place | Owner | "Say what was done" |
| Done by | field (person) | One named person; can be the owner | Picker | Owner | Required before save |
| Done on | field (date) | Date; not in the future for "Fixed" | Date input | Owner | Required before save |
| Workaround date | field (date) | "Real fix by" date, later than today | Date input; on save North sets a reminder Pulse line to the owner on that date | Owner | Required when "Workaround" is chosen |
| Bigger than a fix | panel with button "Turn into an Initiative" | One line: "Use this when the answer is a project, not a repair." Shows the linked Initiative once created, with its state | Opens `/centre/intent/new?type=initiative&from=<this id>` (spec 22, six questions), pre-filled as in "Initiative pre-fill" below. The owner checks each answer. When the Initiative draft is created (spec 20 writes both sides of the link), this problem gets `closure.next[]` of kind `initiative` and moves to `closing` with "Handed to an Initiative" | Owner and organiser | Always shown while the problem is open. After use: "Became Initiative <title>" with a link |
| Affected people | list | Each person in `people.affected`, one row: name, "Waiting" / "Fixed for me" / "Still happening for me", date, optional comment | None on the row itself | Content readers; an affected person without the read switch sees their own row only | "No affected people named. Add at least one before the problem can close." |
| Fix line for affected people | text | "Harvey did: <what>, on <date>" so the person can answer. Nothing else of the thread | None | Affected people (own row) | Hidden until a fix is recorded; before that: "Waiting for the fix" |
| It is fixed for me | button | Primary, on the viewer's own row | One tap writes `fixed` with the time; optional comment field opens after the tap. Active only once the fix block is saved | The affected person themselves (own row only) | Hidden until a fix is recorded |
| Still happening for me | button | Secondary, same row | Requires a comment (one sentence). Writes `still` and adds a note "Aaron says it is still happening: ..."; North flags it to the owner by Pulse line | The affected person | Hidden until a fix is recorded |
| Confirm tally | chip | "3 of 4 say it is fixed", counted from `outcome.affected_confirms` over `people.affected` | None | Content readers | "No one has answered yet" |
| Linked to | panel | The measure or process node from `links.node` (name, link to NodePage), the Ops alert from `links.alert` (state), the source intent from `links.from` | Links open the target; "Change link" (owner) picks another node | Content readers | "Not linked to a measure or a process. The fix note will stay in this problem only." |
| North banner | agent line | "2 days left and no cause yet. Options: extend, close as accepted, cancel." Person who picks named | Buttons run spec 07 extend, spec 09 "Close with what we have", or cancel. Nothing happens until a named person presses | Owner, organiser | Not shown when on time |
| Close this problem | button, primary, footer | "Close this problem" | Goes to the closure screen of spec 09 with the Problem outcome block filled | Owner only | Disabled with the first unmet check named (see Rules) |

**Initiative pre-fill.** Spec 22 owns the six questions and spec 20 owns the mapping; this feature supplies the source record only. The pre-fill is a plain mapping, each answer marked "Guessed" until the owner edits it:

| Spec 22 question | Filled from this problem |
|---|---|
| 1 Goal line and why | Goal line: `outcome.fix.what` if a workaround or fix is saved, else `outcome.what`. Why: `outcome.root_cause.text`, or "Cause not known yet" |
| 2 People | `people.owner` and `people.affected` offered as suggestions, never added without the owner's click. Sponsor left empty |
| 3 Build, 4 Definitions | Not filled. North says "North could not fill this from the problem" |
| 5 Areas | The problem's `areas` |
| 6 Deadline | Not filled (default date) |

### B. Closure screen (route `/centre/intent/<id>/close`, owner view)

This is spec 09 screen A with the Problem outcome block. Layout at 1280 and 390 are spec 09's. This feature adds only the following rows.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Outcome block (Problem) | panel | Statement, root cause, fix (what, by, on) or workaround with date, owner, affected tally, "Confirmed by <reporter> on <date>" or "Waiting for <reporter>" | Read-only; "Edit outcome" returns to screen A | Content readers; people named on a share | "No outcome recorded yet." |
| Close and send for confirmation | button, primary | "Close this problem" | Writes the closure and moves the intent to `closing` until the reporter confirms. Per ruling 25, the organiser presses the final Close button. See States | Owner | Disabled until checks pass |
| No fix, accepted | button, secondary | "Close without a fix" | Dialog: reason required, and the person who accepts the risk named (may be the owner). Writes `outcome.fix = {kind: accepted_no_fix, accepted_by, reason}` | Owner | Shown after the cause is confirmed or unknown |
| Counts line | chip | "3 fixed for me, 0 still happening, 1 no answer", from `outcome.affected_confirms` | None | Content readers | "No one answered" |

### C. Reporter confirmation (route `/centre/intent/<id>`, state `closing`)

Layout at 1280: the Problem screen with a banner across the top. At 390: the banner is the first block.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Confirm banner | panel | "Harvey closed this problem on 8 Oct. Root cause: <text>. Fix: <text>. Is it fixed for you?" | None | Reporter | Not shown to others |
| It is fixed, close it | button, primary | "Yes, it is fixed" | Writes `confirmed_by`, `confirmed_at` (per ruling 25, organiser presses Close to move to `closed`). Runs the write-back on organiser's close (see Records written) | Reporter | Hidden once answered |
| It is not fixed, reopen | button, secondary | "No, reopen" | Opens a field "What is still wrong?" (required) and a choice of stage (Find the cause, Fix). Writes the reopen and returns the intent to `open` with the reason as a note | Reporter, once only | After one reopen the button is replaced by the text "Reopened once already. Start a new Problem" with a "Start a new Problem" button that goes to `/centre/intent/new?type=problem&from=<this id>` |
| Reopen reason | field | One to three sentences | Required to submit | Reporter | "Say what is still wrong" |
| Close, reporter did not answer | button | "Close, reporter did not answer" | Dialog: reason required. Marks confirmation as waived. Organiser then presses Close per ruling 25 (see States) | Owner, after the wait in open question 5 | Hidden until the wait has passed |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. The owner (Harvey) opens the Problem from the Pulse line at `/centre/intent/<id>`. North has already drafted a problem statement and the "What we know" line from the start answers and any linked Ops alert. Harvey checks the owner, clock and affected list.
2. Harvey and the others add notes. After each note North redraws "What we know" with source chips and flags a missing item: "Nobody has said when it started."
3. Harvey presses "Draft the cause". North drafts a root cause from the notes and records, with up to three questions. Harvey edits it and presses "Confirm this cause". The stage moves to Fix. If no cause can be found Harvey records that, with a reason.
4. Harvey fills the fix block: fixed (what, by whom, when) or a workaround (what, by whom, real fix by date). If the answer is a project, Harvey presses "Turn into an Initiative" instead (step 8).
5. Saving the fix moves the stage to Confirm. North sends a Pulse line to each affected person: "Is it fixed for you?"
6. Each affected person taps "It is fixed for me" or "Still happening for me" with a reason. North updates the tally and tells Harvey about any "still happening".
7. Harvey presses "Close this problem" and lands on `/centre/intent/<id>/close`. North drafts the closure (why it happened, what came out, next) as in spec 09; Harvey edits and closes. The intent goes to `closing`. North tells the reporter.
8. Alternative at step 4 or later: "Turn into an Initiative" opens spec 22 pre-filled. Harvey checks the answers and creates the draft. The problem closes as "Handed to an Initiative" with the link, and is not subject to the reporter's confirm (the Initiative carries the work).
9. The reporter confirms (move to `closed`) or reopens once with a reason (move to `open`; the clock restarts per open question 4). On `closed` the server writes the version note to the node and acknowledges the alert (see Records read and written). North sends the rating Pulse line (spec 10).
10. The closed Problem is read-only. Everyone tagged to its areas sees the outcome. The person leaves to `/centre/intent` or `/centre/intent/past`.

## States and transitions (table: state, who moves it, to what, what is written)

Intent states are those of the brief and spec 01. This feature adds the stage of the Problem and one transition, `closing` to `open`, by reopen (open question 2).

| State and stage | Who moves it | To what | What is written |
|---|---|---|---|
| `draft` (visible only to the reporter, ruling 14) | Reporter presses "Open this problem" (spec 41) | `open`, stage `describe` | `stages[0].opened_at`; `time_box`; `people.owner` required |
| `open`, `describe` | Owner or organiser presses "Statement agreed" | `open`, `find_cause` | stage `closed_at`; the statement kept in `outcome.what` |
| `open`, `find_cause` | Owner presses "Confirm this cause" (or records "cause not known") | `open`, `fix` | `outcome.root_cause`, `confirmed_by`, `confirmed_at` |
| `open`, `fix` | Owner presses "Save fix" | `open`, `confirm` | `outcome.fix`; Pulse line to affected people |
| `open`, `confirm` | Each affected person taps | stays; tally changes | `outcome.affected_confirms[]` `{by, state, at, comment}` |
| `open` (any stage) | Owner presses "Turn into an Initiative" and creates the draft | `closing` | `closure.next[]` kind `initiative`; `links.to`; Initiative draft created (specs 20 and 22) |
| `open` to `closing` | Owner presses "Close this problem" | `closing`, `closure` drafted | `closure` per spec 09 with `closed_by` = owner |
| `closing` to `closed` | Organiser presses "Close this intent" (per ruling 25) after owner and reporter confirm | `closed` | `outcome.confirmed_by`, `confirmed_at`; node version note; alert acknowledged |
| `closing` to `open` | Reporter presses "No, reopen" (once) | `open`, stage `find_cause` or `fix` as the reporter picks | `outcome.reopened = [{by, at, reason}]`; owner's Pulse line; the earlier `closure` stays in `intents/<id>/events.jsonl`, not deleted |
| `closing` to `closed` | Owner marks fix accepted, organiser presses "Close this intent" per ruling 25 | `closed` directly | `outcome.fix.accepted_by`, `reason`; no node version note of "fixed"; a note "problem P-123 closed without a fix on <date>" is written instead |
| `closing` to `closed` (reporter silent) | Organiser presses "Close this intent" per ruling 25 after owner marks reporter silent | `closed` | `outcome.confirmed_by = null`, `confirm_waived_by`, `reason` |
| `open` to `cancelled` | Organiser, with reason (spec 09) | `cancelled` | `closure.cancel_reason`; shown in Past with the reason (ruling 14) |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Read or write | Fields | Status |
|---|---|---|---|
| `intents/<id>/intent.json` via `sh_platform/jsonfile.py`, filtered per viewer with `sh_platform/profile/view.py` | Read and write | Intent record of spec 01 with the `outcome` below | Existing shape (spec 01), New for the problem outcome |
| Problem outcome fields | Write | Spec 41 owns `what`, `saw`, `about`, `bites`, `triage`. This feature adds `root_cause: {text, drafted_by_north, confirmed_by, confirmed_at, based_on: [], unknown, reason}`, `fix: {kind: fixed|workaround|accepted_no_fix, what, by, done_at, real_fix_by, accepted_by, reason}`, `affected_confirms: [{by, state: fixed|still, at, comment}]`, `reopened: [{by, at, reason}]`, `confirmed_by`, `confirmed_at`, `summary_pinned: []` | New (extends spec 41 and spec 02 outcome shape) |
| `people.owner`, `people.reporter`, `people.affected` in the intent record | Read, write (owner change) | Named slots of brief ruling 13 | New slots |
| `intents/<id>/intent.json` `notes[]` | Write | `{id, by|anonymous, role, at, text, ref|null}` | New |
| `what_we_know` (inside the intent record) | Write by North | `{text, sentences: [{text, source_ref, pinned}], drafted_at}` | New |
| `intents/<id>/events.jsonl` (spec 16) | Write | One event per note, cause, fix, tap, reopen, close; the record holds counts only (ruling 12) | New |
| `GET/POST /api/intents/{id}/notes` | Read, write | Body `text`, `anonymous`; answer the note | New. Reshaped from the node comments routes |
| `POST /api/intents/{id}/problem/cause`, `/fix`, `/confirm-tap`, `/reopen`, `/to-initiative` | Write | One route per button named above; each checks role and the version of the record | New |
| `POST /api/intents/{id}/close` | Write | Spec 01 route; for a Problem adds the rule that `outcome.root_cause` and `outcome.fix` must exist | Existing (spec 01), extended |
| `graph/versions.json` through `append_version(plane, node_id, what, by, ref)` in `sh_platform/graph/versions.py` | Write on `closed` | `what` = "Problem P-123 fixed on 8 Oct"; `by` = the owner's name; `ref` = `problem:<intent id>`; North is never the `by` | Existing function, New caller |
| `graph/comments.json` | Not written | The thread of a Problem stays in the intent. A node comment is not created | Existing, not used here |
| Ops alerts through `act(plane, alert_id, "ack", by, note)` in `sh_platform/build/alerts.py` | Write when `links.alert` is set | `state` acknowledged, `by` the owner, `note` "Problem P-123: /centre/intent/<id>" | Existing function, New caller |
| `POST /api/company/build/alerts/{id}/ack` | Not called directly | The server calls `act` itself so a person need not press Acknowledge twice | Existing |
| `modules/m1_intent` Pulse feed (spec 13) | Write | Lines named in Entry points | New lines |
| Company profile `profile.store.raw(plane)["people"]` | Read | Person picker, area lookup | Existing |

## Fields this feature adds to the intent record

None of the brief's section 3 fields is renamed. This feature adds:

- `links.node`: node id (measure or process) the Problem concerns, or null.
- `links.alert`: Ops alert id the Problem came from, or null.
- Outcome fields (flat per type): `what`, `root_cause`, `fix`, `affected_confirms`, `reopened`, `confirmed_by`, `confirmed_at`, `summary_pinned` (list; server allows at most one reopen entry, open question 2).
- `notes[]`, `what_we_know`.
- `short_ref`: "P-123", a display number per company (open question 1).

The reporter and owner are held in `people.reporter` and `people.owner` (brief ruling 13), so this feature adds no `reporter` or `owner` field. The `created_by` of spec 01 is the person who opened the record, who may differ from the reporter.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North drafts** the problem statement from the start answers (once), and after every note redraws "What we know" with source chips. It drafts the root cause from the notes and the linked Ops records when the owner presses "Draft the cause". It asks at most three questions (A-045). It drafts the closure (spec 09) and the Initiative pre-fill (spec 20). It keeps the clock, says when the cause or fix is late, and proposes extend, close as accepted, or cancel. A person acts: the owner confirms the cause, saves the fix, closes; each affected person taps; the reporter confirms or reopens.
- North never confirms a cause, never signs a fix, never writes the node version note itself; the server writes it on the reporter's confirmation and records the owner as the author.
- North's figures (days, counts of notes) trace to the record. It does not state a cost or a likelihood it cannot work out; it says "Not available yet".
- **Lens** drafts a definition only when a note names a measure or term that has no glossary entry: "Aaron wrote 'settled value'. No definition exists. Draft one?" A person confirms in the glossary flow, not here.
- **Nira** writes the Pulse lines in Entry points and the owner's reminder on a workaround date. She adds a "bigger than a fix" nudge only under open question 6.
- No agent edits a human edit: a pinned sentence or an owner's edited cause is never redrawn (hard rule 7 in `CLAUDE.md`).

## Rules (visibility, time box, who may do what)

- Time box: 5 working days (brief section 2, spec 07). Stage budgets are spec 02's split; this file states none of its own. A reopen restarts the clock only as set in open question 4. Dates and "today" use the company time zone from the profile, else UTC.
- Who may do what: only the owner confirms the cause and saves the fix. Only the reporter confirms or reopens. Only an affected person taps their own row. Participants may add notes; observers read and never write. The organiser changes the owner and turns the problem into an Initiative together with the owner; either may press it, the other is told. Per ruling 25, the organiser presses the final "Close this intent" button after the owner and reporter have confirmed.
- Owner and reporter are two different people unless the owner reported it (spec 02). The reporter may not tap for an affected person.
- Close checks, each named beside the disabled button: a confirmed cause (or "unknown" with a reason), a saved fix or an accepted no-fix, at least one affected person, a one-line summary, a reason on every `next` row (the affected-person check is open question 8).
- A workaround can close the problem only if it carries a "real fix by" date; North then offers "Start a Problem for the real fix" in the closure's next list.
- Reopen: once, reason required. The second time is a new Problem linked by `links.from` (open question 2).
- Visibility follows brief section 4 and rulings 4, 5 and 14. Area members and affected people see existence, title, purpose, stage, clock, people and, once closed, the outcome. Content readers open the thread. Anonymous notes are never shown to the company admin. A super admin sees existence only. A share link (spec 11) shows the thread, the cause, the fix and the confirm tally, read-only, to the people it names. A draft is visible only to the reporter.
- Notes are a thread. Nothing is edited or deleted; a correction is a new note.
- Write-back on `closed` is idempotent: a repeat of the close call never appends a second version row (check `ref` before append).
- The version note is written only when `links.node` is set. If the node is gone, the closure says "Node not found, fix note not written". Who writes it when the owner cannot see the node is open question 7.
- The Ops alert is acknowledged only when `links.alert` is set. The ack is attributed to the owner, never to North.
- Ratings follow spec 10 and ruling 15: anonymous by default, no per-person averages.

## Counters and measures of this feature (numbers only, each traced to a record)

| Measure | Source |
|---|---|
| Problems per process (or measure) per month | `intents/*/intent.json` of type `problem`, grouped by `links.node` and the month of `created_at` |
| Problems with no linked node | count where `links.node` is null; shown as "Not linked" |
| Days to close (median, longest) | working days from the `open` event to the `closed` event in `intents/<id>/events.jsonl`, per month. Median shows "Fewer than five" below five closed problems |
| Closed inside the time box | `closure.closed_at <= time_box.ends` |
| Reopened | count where `outcome.reopened` is not empty |
| Became Initiatives | count where `closure.next` has kind `initiative` |
| Closed without a fix, accepted | count where `outcome.fix.kind = accepted_no_fix` |
| Affected people who say fixed | `outcome.affected_confirms` where `state = fixed`, over all affected on closed problems |
| Workarounds past their date | `outcome.fix.real_fix_by` earlier than today and no later fix on a linked Problem |

Counts are exact (ruling 8). Means, medians and any per-person figure show "Fewer than five" below five records. With no closed Problem the screen says "Not available yet: no problem has closed." These numbers feed spec 19.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Paths below were checked as present in this repo.

| Existing | Where | Decision |
|---|---|---|
| Node comment thread: `NewComment`, add comment route, `_line` plain-sentence builder | `sh_platform/graph/comments.py` lines 28 to 38, 94 to 132 | Reshaped. Same shape (`id`, `text`, `by` or "Anonymous", `at`, 2000 character limit, lock and atomic write) but scoped to an intent id, with a role chip. The kinds `comment, suggestion, ambiguity` are not used |
| Decide flow: `_may_decide` (owner or steward), `Decision`, the "accepted" outcome becoming a version | `sh_platform/graph/comments.py` lines 72 to 75, 135 to 160 | Reshaped. The rule "only the named owner decides" is copied into the cause confirm and the fix save; the "accepted becomes a version" idea is reused on closure through `append_version`. A node comment is not created for a problem |
| Version writer `append_version(plane, node_id, what, by, ref)` | `sh_platform/graph/versions.py` lines 40 to 49 | Reused as is. New caller only. `comments.py` has a private `_add_version` copy at lines 81 to 87; this feature calls the public one |
| Plain-language version rows `plain_versions` and the NodePage version list | `sh_platform/graph/versions.py` lines 110 to 125; `ui/src/pages/NodePage.tsx` lines 172 to 178 | Reused. A "Problem P-123 fixed on <date>" row appears in the VersionList with no UI change |
| Ops alerts: `act(plane, alert_id, action, by, note)` and states open, acknowledged, closed | `sh_platform/build/alerts.py` lines 40 to 49; route `ack` at `sh_platform/build/ops.py` line 135 | Reused. Server-side call on close and the ack note carries the problem link. The "Start a problem" button on the alert card in `ui/src/pages/OpsPage.tsx` (alert card from line 59) is spec 41's; this feature only names it |
| Alerts are rebuilt from live checks by `sync` | `sh_platform/build/alerts.py` lines 25 to 38 | Not changed. See open question 9 |
| Closure screen, signature panel, closing checks, next list | spec 09; `modules/m1_intent/api/charter.py` 294 to 305 (`sign_charter`) | Reused through spec 09; a Problem has no signature panel |
| Ratings | spec 10 | Reused |
| Intent store and filter: `sh_platform/jsonfile.py`, `sh_platform/profile/view.py` | spec 01 | Reused |
| Initiative start and pre-fill | specs 20 and 22 (both exist in this folder) | Reused. This feature supplies the source record and the mapping table above |
| Problem start, owner Accept, outcome fields | spec 41 | Reused. This feature starts where 41 ends |
| Stage clock, extend | spec 07; `modules/m1_intent/domain/timer.py` | Reused |
| Design parts `CommentThread`, `VersionList`, `EmptyState`, `Button`, `SideCard`, `Trail`, `Footnote` | `ui/src/design`, imported by `ui/src/pages/NodePage.tsx` line 5 | Reused for the thread, the linked panel and the empty states |
| Problem screen, root cause block, fix block, confirm taps, counters | none found | New. Searched `sh_platform`, `modules`, `ui/src` for "root cause", "fixed for me", "counters.json" and problem workflows; only the Ops alert and node comment code above is near |

## Not in this feature

- Starting a Problem, its start questions, triage and the owner's Accept (specs 03, 41).
- The closure screen itself, signing, share link and ratings (09, 10, 11).
- Creating the Initiative (20, 22); only the button, the entry and the pre-fill source are here.
- Raising Ops alerts or fixing data in Build. The Problem records a fix; it does not run it.
- Any cost estimate or severity score (no rule exists for either).
- Editing a measure's definition. A definition change goes through the node's own accept flow.
- Notifications beyond the Pulse lines named.

## Open questions

1. **Short reference.** "P-123" needs a per-company counter. Where is it kept, and does it reset? Drafted: a `counters.json` in the company plane, never reused.
2. **Reopen.** Spec 01 makes `closed` final, so reopen here happens from `closing`, before the reporter confirms. The limit of one reopen is not in the brief. Do we also need reopen after `closed`? Drafted: no, a new Problem linked by `links.from`.
3. **Cause not known.** May a problem close with an unknown cause and a workaround only? Drafted: yes, with a reason and a workaround date.
4. **Time after reopen (drafted figure, needs approval).** Does the reopened problem get a fresh 5 days, or a shorter box? Drafted: 2 working days, owner can extend with a reason. This figure is invented.
5. **Silent reporter (drafted figure, needs approval).** How long may the reporter stay silent before the owner may close? Drafted: 3 working days, then the "reporter did not answer" button appears. Not a rule.
6. **Bigger than a fix nudge (drafted figure, needs approval).** What should make North suggest an Initiative: a count of affected people, repeat problems on the same node, or the owner's word only? Drafted: owner's word only, plus North may mention it when the same node has three Problems in a month. The threshold of three is invented. A second drafted trigger, a cause naming three or more people or processes, is dropped until this is settled.
7. **Node access.** If the owner cannot see the node, who writes the version note? Drafted: the server writes it under the owner's name regardless, since closure is the owner's act.
8. **Affected and read access.** Ruling 4 keeps content closed to affected people unless the organiser switches on "affected people may read". This file lets an affected person see a one-line fix summary on their own row so they can answer. Is that allowed with the switch off? Also, is "at least one affected person before close" a rule? Neither is in the brief.
9. **Alert reappears.** Alerts are rebuilt from live checks. If the check still fails after the fix, the alert returns. Should a Problem's fix hold the alert acknowledged, or must the check pass first? Drafted: the alert follows its check; the Problem does not close the alert.
10. **Query keys.** Ruling 1 lists `type` and `from` on `/centre/intent/new`. Specs 20 and 41 add `item` and `alert`; this file adds `node`. Spec 41 also uses a `/centre/intent/<id>/triage` view that ruling 1 does not list. Spec 20 reads `outcome.statement` while spec 41 holds the statement as `outcome.what` (flat per ruling 16); this file follows 41.
11. **Several nodes.** A Problem may touch more than one measure or process. Drafted: one `links.node` for now, others as text in the notes.
12. **Auto-draft of the cause.** Drafted: North drafts only when the owner asks. Should it also draft by itself once a number of notes exist? The brief gives no number.
