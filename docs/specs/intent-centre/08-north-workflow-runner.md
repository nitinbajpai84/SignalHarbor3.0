# 08. North as workflow runner

Part of: Intent Centre v2. Depends on: 02 (types catalogue: stage lists and start questions), 07 (clock and time box), 09 (closure summary and next proposals). Feeds: every screen spec that shows an intent (the North panel is on all of them), the Pulse page lines, 09 (closure draft), 07 (late and extend proposals).

## Purpose (three sentences)

North is the agent responsible for every intent reaching an outcome inside its time box. For each type and each stage North knows what comes next, drafts it, asks the one missing question, says whose turn it is and nudges that person, watches the clock, and writes the closure draft and the "what next" proposals. North never signs, closes, deletes or invents a number: a named person confirms, picks, signs or rates, and every North draft is marked as a draft until that person confirms it.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | Opens an intent; every stage change; closure | Opens the intent screen; North has a draft or a question waiting for her |
| Sponsor (Daniel) | Initiative charter; any "extend or close" pick on an initiative | A Pulse line "waiting for you"; the panel names him as whose turn it is |
| Participant (Aaron) | Their turn in a stage; rating at closure | North's nudge in Pulse or in the screen line |
| Owner (Harvey), approver (Grace) | Problem owner steps; sign-off steps | Same nudge path |
| Analyst (Katie) | Prepares definitions at Define strategically; sees North's questions on the same panel | Opens an intent she is in |
| Company admin | Sees North's drafts and thread on any intent in their company, except sealed and anonymous material | Opens any intent |
| Super admin | Never sees the thread or drafts, only that the intent exists | Not applicable |

North itself runs on three triggers: a person opens an intent screen, a stage changes, and a clock check. The clock check runs when anyone opens the intent or the Pulse page, and once a day per open intent (see Open questions: no background scheduler exists today, `sh_platform/pulse` is computed on request).

## Entry points (every route, link, Pulse line, button that leads here)

- The North panel sits on every intent screen (docked right at 1280, bottom sheet at 390). Every spec that shows an intent includes it; this spec owns its behaviour.
- Pulse line for a person whose turn it is: kind `request` (answer, upload, join), `decision` (pick extend, close or cancel, pick next), or `signature` (sign the charter). `href` is `/centre/intent/<intent id>`, `source.record` is `intents/<id>/intent.json`. The `action` text is North's nudge title. A weekly check-in line uses the type name "Weekly check-in".
- "Ask North" button on the intent header (opens the panel at the answer box).
- "North has a draft for you" chip on the intent card in the centre list; opens the intent with the draft focused.
- Start of a new intent: the chooser at `/centre/intent/new` (02, 03) and the per-type start screen hand the first answers to North, which asks the missing start question in this panel.
- A share link read-only view shows North's confirmed text only, never the thread (see Rules).

## Screens, element by element

### Screen A: the North panel (component, used on every intent screen)

Route: none of its own; it renders inside `/centre/intent/<intent id>` and each stage route under it. Data: `GET /api/intents/{id}/north` (New).

Layout at 1280: a right dock, a quarter of the screen, 360 to 720 px (reuse `dockedWidth`, `ui/src/components/AgentPanel.tsx`), page content reserves its width. Regions top to bottom: head (North name, role line, voice toggle), "asking now" block (the question highlighted), turn strip (whose turn), drafts list, thread, answer box, action row.
Layout at 390: the dock becomes a bottom sheet opened from a pill "North, 1 waiting" (the number is a count of open drafts and questions, see Counters). The sheet shows the same regions in one column; the thread collapses to the last three turns with "Show earlier".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Head | agent line | "North" and the type-specific role line from 02 (for example "runs this initiative with you") | None | Everyone who can open the intent content (see Rules) | Never empty |
| Voice toggle | button | Speaker icon; same behaviour as `NiraDock` | Switches spoken replies on or off for this person | People with a seat (participants, organiser, sponsor, decider, owner, reporter) | Disabled with the reason when speech is not set up |
| Asking now | agent line, highlighted (reuse `Turn now`, `NorthPanel.tsx` 29-36, 95-103) | The one question North needs answered, in plain words, and whose it is | None; the answer box below answers it | The person whose turn it is; others see it greyed with "Waiting for <name>" | "North has nothing to ask right now." |
| Turn strip | chip | "Your turn: <what>" or "Waiting for <name>: <what>, since <date>" or "Nobody is waiting" | Click on a name opens that person's card (name only, no contact details) | Anyone who can open content | "Nobody is waiting" |
| Clock line | agent line | "Day 4 of 10, 6 days left" or "2 days over the time box" (numbers from 07 only) | None | Anyone who can open content | "Not available yet: no time box set" and names 07's field |
| Draft card | panel with chip | North's draft text, the chip "Draft by North, not confirmed", "Based on:" list of record names it used | See buttons below | Who may confirm it (see table in Rules); others see text greyed, chip kept | Not shown |
| Confirm | button (primary) on a draft card | "Confirm" (or the verb of the moment: "Send to the group", "Use as summary") | Writes the draft as confirmed by this person, with time; the chip becomes "Confirmed by <name>, <date>" | The person named to confirm | Disabled with "Only <name> can confirm this" for others |
| Edit | button on a draft card | "Edit" | Opens the text in place; saving writes a person edit that North never overwrites | Same as Confirm | Same |
| Discard | button on a draft card | "Discard" | Draft marked discarded, kept in the thread; North may offer a new one only if the person answers a new question | Same as Confirm | Same |
| Pick row | button group on a proposal draft | Options named in the draft, for example "Extend by 2 days", "Close with what we have", "Cancel" | Opens a one-line reason field (required for extend and cancel), then "Record my pick"; writes through 07 or 09, not here | The named picker | Not shown |
| Thread | list | Turns, oldest first: North turns, person turns, system lines (draft confirmed, pick recorded). Reuse `ds-north__thread` markup | None | Each person sees their own turns plus North turns addressed to everyone; a turn addressed to one person is visible to that person and the organiser only | "No conversation yet. North will open one when this intent starts." |
| Answer box | field (textarea) | Label "Your answer", hint from the current question | Typing enables Answer | A person whose turn it is, or anyone with a seat when North asks the group. Not shown to an observer or to an affected reader (they see "You are reading this intent. You cannot answer.") | Disabled with "Waiting for <name>" if it is not their turn |
| Answer | button (primary) | "Answer" | Posts to `POST /api/intents/{id}/north/turns`; North replies with the next question or says it has what it needs | Same as answer box | Disabled when the box is empty |
| Ask North | field and button inside the thread footer | "Ask North something about this intent" | Posts as a question; North answers from the intent record, never from other people's content | People with a seat (not observers) | Same as answer box |
| Something is wrong | link | "Tell the organiser North got this wrong" | Writes a thread line to the organiser; no change to the record | Anyone with a seat | Not shown when the viewer is the organiser |
| Error line | agent line | North's plain failure line (reuse the `_NO_MODEL` wording, `modules/m1_intent/api/private_room.py` line 44) | Retry button | Anyone | Not shown |

### Screen B: the "Waiting for you" line on an intent screen (in-screen nudge)

Route: the top strip of `/centre/intent/<intent id>` and each stage route.
Layout at 1280: a one-line strip under the page head. At 390: the same line, wraps to two lines, with one button.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Nudge strip | agent line | "North: Aaron, your note is due Thursday. 1 day left." plus the verb button | Button opens the panel at the matching draft or question | The person whose turn it is only | Not shown |
| Dismiss for today | button | "Not now" | Hides the strip until the next day; the Pulse line stays; nothing is written to the record | Same | Not shown |

### Screen C: the Pulse line for a nudge

Route: `/pulse` (existing landing, the daily Pulse page; not the Weekly check-in). One LINE per person per open item, within the existing cap of 7 a day (`docs/plan/SHAPES.md` section 1).

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Pulse line | list item | `title`: North's nudge in one sentence; `detail`: intent title and stage; `due`: stage end date | Opens the intent with the panel focused on the item | Only the person named in `people` for that turn | Strip omitted (existing rule) |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

Example: Janet opens the Ardmore initiative "Add a client reporting data source".

1. Janet picks "Initiative" on the 02 start screen and gives a title and one line of purpose. North reads the type contract (02) and sees which of the six Initiative start questions (file 22) are still unanswered.
2. North asks the first missing one in the panel: "Who is the sponsor for this?" (wording from file 22). The question is highlighted. Janet answers in the box. North asks the next one, one at a time, never a form.
3. When the contract's start questions are all answered, North drafts the opening message of the first stage (what this stage is for, who is asked to do what, by when). The draft card appears with "Draft by North, not confirmed".
4. Janet edits one sentence and presses "Send to the group". The draft becomes confirmed and goes out as an invite (existing invite path, `sh_platform/pulse/messages.py` draft and send). North writes a thread line "Opening message confirmed by Janet".
5. Between steps: North sets the turn to the participants, writes it on the record, and creates a Pulse line for each person who must act. In-screen the strip appears for them.
6. Aaron opens the intent from Pulse. The strip says "Your turn: add your note." The panel asks him the question for his part of the stage. He answers. North reads the answer back (the existing "listen and check" behaviour, `modules/m1_intent/agent/north_rules.yaml` `listen_rules`), asks at most one question, and never rewrites what he said.
7. When nobody is late, North stays quiet. When someone is late against the stage end (07), North's next clock check writes a nudge: Pulse line first, strip in the screen second. North does not message outside the product by itself.
8. When all stage work is in, North drafts the next stage opening (back to step 3) or, at the last stage, tells Janet "This is ready to close" and drafts the closure summary (09).
9. Janet reads the closure draft, edits, and presses "Use as summary". She confirms who may rate. Participants rate when it is their turn.
10. North drafts the "next" proposals (initiative, backlog, problem, nothing) with a reason each. Janet picks one per proposal. North never picks.
11. Janet presses the close control owned by 09. North writes the thread line and the memory summary (see Agent behaviour). The intent leaves "closing".
12. If at any point the clock says the time box will not hold, North says so in the panel and drafts three options (extend, close with what we have, cancel). A named person picks and gives a reason; that pick, not North, changes the record through 07.
13. Janet leaves: she closes the panel, or follows a next-step link to the new intent or to Build at `/centre/build/gap-analysis?from=<id>`. The intent stays at `/centre/intent/<id>` read-only with the thread kept. North writes the memory entry and stops.

For a Weekly check-in the journey repeats per week: a new week opens by the clock on the next working day after the close day, even if the review is unfinished, and North opens that week's thread. Series and weeks are never rated.

## States and transitions (table: state, who moves it, to what, what is written)

Intent states are the brief's (`draft|open|in_session|closing|closed|cancelled`). This table lists what North moves itself and what it only proposes.

| State or item | Who moves it | To what | What is written |
|---|---|---|---|
| Intent `draft` to `open` | Organiser presses "Open this intent" (02). A `draft` intent is visible and nudged only to the person who started it | `open` | `state`, `stages[0].opened_at`; North writes `north.turn` |
| Stage `pending` to `open` | Organiser confirms the stage opening draft | Stage `open` | `stages[i].state`, `opened_at`; `north.drafts[]` marked confirmed |
| `north.turn` set or changed | North alone | Names the holder and what is asked, with `since` | `north.turn = {holder, what, since, due}` |
| Nudge raised | North alone (clock check) | `north.nudges[]` gets an entry | `{to, at, kind: pulse|strip, stage, text}`; Pulse line appears |
| Draft created | North alone | `draft` | `north.drafts[]` entry (see fields) |
| Draft confirmed, edited, discarded | The named person | `confirmed`, `edited`, `discarded` | `status`, `by`, `at`, text kept |
| Time box at risk | North alone proposes; named person picks | Proposal `open` to `picked` | Proposal and the pick in `north.drafts[]`; extend written by 07 as `time_box.extended_by` |
| Stage closes | Organiser (the stage's own close control) | Stage `closed` | `stages[i].closed_at` |
| Intent `open` or `in_session` to `closing` | Organiser (09) | `closing` | `state`; North generates the closure draft |
| `closing` to `closed` | Organiser (09) | `closed` | 09 writes `closure`; North writes only the memory entry |
| Any state to `cancelled` | A named person with a reason (07) | `cancelled` | 07 writes the reason |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Read or write | Fields | Status |
|---|---|---|---|
| `intents/<id>/intent.json` (intent record) | Read; North writes only the `north` block | All brief fields; `north.*` below | New file (brief section 3, ruling 12); `north` block New |
| `intents/<id>/north.json` (the North thread, its own file in the intent's folder) | Read and write | `turns: [{id, role: north|person|system, to: all|<person id>, text, at, answered, kind: answer|question|draft|nudge|pick}]` | New (file 16 owns `intents/<id>/events.jsonl`; the record keeps counts only) |
| Type contract from 02 | Read | stage list, start questions, per-stage turn holder, per-stage ending condition, opening-message hints | New (02 owns) |
| Clock from 07 | Read | `starts`, `ends`, stage ends, `extended_by`, days elapsed and left | New (07 owns) |
| Closure and next from 09 | Read, and North's draft is stored in `north.drafts[]` until 09 copies the confirmed text into `closure` | `closure.*` | New (09 owns) |
| Company profile | Read through `sh_platform/profile/view.py` `read(plane, viewer)` | Company name, industry, areas, roles (names only for people), field-level rules | Existing |
| Memory | Read `memory.for_prompt(plane, "north", pid, budget)`; write `summarise_and_remember` at closure | `{"person": [...], "company": [...]}` | Existing |
| Pulse | Write LINE records on request when `GET /api/pulse` builds | LINE shape of SHAPES section 1 | Existing shape, new builder `intents` in `sh_platform/pulse/lines.py` |
| Run log | Write, existing runtime | Agent, module, status; no prompt, answer, name or figure | Existing (`sh_platform/agents/runs.py`) |
| Sessions, walls, charters, baselines | Read by reference only | Whatever the stage screen already shows | Existing |

New routes (all declared in `modules/m1_intent/manifest.yaml` and `sh_platform/route_permissions.yaml`, default deny):

| Route | Purpose | Roles |
|---|---|---|
| `GET /api/intents/{id}/north` | Panel state: asking now, turn, clock line, open drafts, last turns (view-filtered) | Any person who may open the intent content |
| `POST /api/intents/{id}/north/turns` | A person answers or asks; North replies in the same response | Person whose turn it is, or any seat for a group question or "ask" |
| `POST /api/intents/{id}/north/drafts/{draft_id}/confirm` | Confirm; body may carry an edit | The person named on the draft |
| `POST /api/intents/{id}/north/drafts/{draft_id}/discard` | Discard | Same |
| `POST /api/intents/{id}/north/proposals/{draft_id}/pick` | Pick an option with a reason; calls 07 or 09 to apply it | The person named on the proposal |
| `POST /api/intents/{id}/north/clock-check` | Runs the clock check and writes nudges; also called on open | Any viewer; idempotent per day |

## Fields this feature adds to the intent record

```
north: {
  turn: {holder: person id|"group"|null, what, since, due} | null,
  asked: [{key, question, answered_at|null}],        # start questions from 02 and their state
  drafts: [{id, kind: opening|question|nudge|closure|next|extend_close_cancel,
            stage|null, text, status: draft|confirmed|edited|discarded,
            addressed_to: [person ids], may_confirm: [person ids],
            based_on: [record names], made_at, decided_by|null, decided_at|null,
            options: [{key, label}] | null, picked: key|null, reason|null}],
  nudges: [{to, at, kind: pulse|strip, stage, text}],
  last_check: iso|null,
  thread_ref: "intents/<id>/north.json"
}
```

A person's edit sets `by: person` on the draft text; North never overwrites it (CLAUDE.md rule 7).

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

### North's duties per stage

North reads the stage list from the type contract (02) at run time. Nothing about stages is hardcoded in North. Per stage, North does the same six things:

| Duty | North does alone | A person acts |
|---|---|---|
| Know the stage | Reads the stage key, its turn holder and its ending condition from 02 | None |
| Open the stage | Drafts the opening message (purpose of the stage, who does what, due date from 07) | Organiser confirms or edits ("Send to the group") |
| Ask the missing start question | Compares the type's start questions with `north.asked`; asks one at a time | The asked person answers |
| Name the turn | Writes `north.turn`, shows the turn strip | None |
| Nudge | Pulse line and strip when the turn holder is within the nudge window or late (window is an Open question) | The holder acts |
| Watch the clock | Reads 07; when the time box will not hold, drafts extend, close with what we have, or cancel | A named person picks, with a reason |
| Close | Drafts the closure summary (09) and the next proposals | Organiser confirms, picks, closes; participants rate |

### What North does per type (stage keys are file 02's; start questions are the per-type files', ruling 2)

| Type (stage keys from 02) | Opening message drafts | Start questions North asks if missing | Turn holders North names | Closure and next North drafts |
|---|---|---|---|---|
| Initiative: `think_unfiltered`, `define_strategically`, `build_ready` | At each stage: what it is for, who is asked, the date | The six in file 22 | Participants (wall notes), Katie (definitions), Daniel (charter signature), Janet (Build-ready check) | Summary of the charter and what was agreed; next: hand-off to Build, backlog, problem, nothing |
| Brainstorm: `think_alone`, `live_session`, `choose` | The invite with the idea or problem statement | The five in file 35 | Invited people for ideas; Janet for choosing one idea | The chosen idea with the thinking kept; next: initiative, backlog, decision, nothing |
| Weekly check-in (record key `pulse`): `collect`, `review`, `triage` | Each week's prompt to the ops area | The four in file 38 | Each ops person for items of kind `ran`, `broke`, `thought`; Janet to review and decide fates | The week record; North drafts a fate per item (`problem`, `backlog`, `handled`, `nothing`) with a reason, Janet decides. Every `broke` item needs a fate before the week closes. Undecided `ran` and `thought` items close as `nothing`, reason "Not reviewed this week" (written by file 40, not North) |
| Problem: `describe`, `find_cause`, `fix`, `confirm` | Report read-back and the owner request | The five in file 41 | Reporter (`people.reporter`), owner Harvey (`people.owner`), approver Grace when a fix needs sign-off | Root cause, fix, owner, closure; next: initiative if bigger than a fix, backlog, decision, nothing |
| Decision: `options`, `decide` | The decision statement and options request to advisers | The five in file 43 | Advisers for options; the decider (`people.decider`) for the decision | The decision, options considered, who decided, why; next: any type, backlog, nothing |

Questions North puts to people during Define strategically (process map, glossary, catalogue, governed state) share one cap: three open questions per person (A-045, ruling 9). North asks Katie or an owner only while that person has fewer than three open.

### The exact moments a person acts, and what North does alone

| Moment | Person | Kind of act |
|---|---|---|
| Answers a start question or a stage question | The asked person | Answer (their own words, kept as said) |
| Confirms an opening message, a nudge sent outside the product, a closure summary | Organiser | Confirm |
| Picks extend, close with what we have, or cancel | The named person (organiser by default; sponsor on an initiative is an Open question) | Pick, with a reason |
| Picks the "next" for each proposal | Organiser | Pick |
| Signs the charter or any sign-off step | The named signer (Daniel, Grace) | Sign |
| Rates and adds a note | Each participant; anonymous by default, the person's own file keeps the link (ruling 15). Not for check-in series or weeks | Rate |
| Seals a note, ticks anonymous | The author | Choose (existing v1 rules, D-013) |

North alone: reads, decides what is missing, drafts, asks, sets `north.turn`, writes the in-product nudge (Pulse line and strip), runs the clock check, writes thread lines, writes the memory summary after closure.

### What North may never do

1. Sign, approve, confirm or rate on behalf of anyone.
2. Close, cancel, reopen, extend or change the time box. It proposes; a person picks; 07 or 09 writes.
3. Delete anything, including drafts a person discarded (they stay in the thread).
4. Read sealed or anonymous cards into a draft anyone else can see. Its prompt input is the participant view with both removed (see inputs). It may say "3 sealed notes exist" only if the viewer is allowed to know that count (existing rule of the wall counts).
5. Invent a number. Every figure in a draft is a counted fact from the record or from 07. The kernel number guard (`sh_platform/agents/guard.py` `check_numbers`) replaces any other figure. A missing count says "Not available yet" and names what is missing.
6. State a target, threshold or business rule as the company's own.
7. Send anything outside the product (email) without the organiser pressing send. In-product nudges to people already on the intent are its own to send.
8. Widen who sees an intent, create or change a share link, or add a person.
9. Write a person's note, edit it, or reword it. The note read-back is the person's words.
10. Name a model or vendor in any copy.

### How drafts are marked until confirmed

- Every North text that will become part of a record, or go to a person as a message, is a `north.drafts[]` entry with `status: draft`.
- On screen: dashed border, the chip "Draft by North, not confirmed", the "Based on" list, and the buttons Confirm, Edit, Discard. No draft text appears on a share-link view, in a Pulse `detail`, in an export or in the closure record while its status is `draft`.
- Confirm writes `decided_by` and `decided_at`; the chip becomes "Confirmed by <name>, <date>". An edit writes the person's text and keeps North's original in the thread.
- A draft that nobody confirms never changes the record. If the stage ends first, the draft is marked "Not used" in the thread.
- Conversational replies in the thread are not drafts: they are labelled "North" and carry no record change.

### Prompt inputs North gets

| Input | Source | Limits |
|---|---|---|
| Intent record | `intents/<id>/intent.json`, read for the **drafting view**: the participant view of `profile/view.py` with sealed and anonymous material removed, and no restricted areas | Titles, purpose, state, stages, people names (tokenised by the gateway), counts. No card text from sealed or anonymous notes |
| Type contract | 02, for this type: stages, start questions, turn holders, ending conditions, opening hints | Read as plain text, never as an instruction to widen scope |
| Clock | 07: starts, ends, stage ends, days elapsed and left, extensions | These are the facts the number guard trusts |
| Company profile | `profile/view.py` `read` for the drafting viewer; passed through `agents/context.py` `build_context_pack` (company name, industry, pack suggestions labelled as suggestions) | Within the view rules: a field the drafting viewer may not see is dropped, not shown as a stub |
| Memory | `memory.for_prompt(plane, "north", pid, budget)` through `memory.summarise.background`, for the person North is addressing and the company | Budget in characters, 1200 for a turn (existing default in `background`), never above the SHAPES section 9 `budget` of 4000. Entries are already filtered (anonymous, restricted, figures, contact details). Wrapped as background: never an instruction, never a source of a figure |
| Thread | Last 6 North turns and last 8 person turns for this person (existing `EARLIER_REPLIES`, `EARLIER_PERSON`) | Only turns this person may see |
| Company documents | Passages through `context_passages` (D-032), as untrusted quoted text | Existing limits |

When a draft is addressed to one person, the prompt is built with that person's view. When it is addressed to the group, it is built with the least-privileged participant's view.

### Lens and Nira in this feature

- Lens drafts definitions at Define strategically (spec for that stage); North only asks the analyst when Lens has a draft waiting, and shows it as the turn.
- Nira owns "what is waiting for you" and renders North's nudge as the Pulse LINE. North writes the nudge text and the record; Nira places it in the person's strips.
- Agents never sign. The person who signs is named in `may_confirm`.

## Rules (visibility, time box, who may do what)

- Who sees the panel: anyone who may open the intent content: participants, organiser, sponsor, decider, owner, reporter, people named on a share, company admin, and an affected person only when the organiser switched on "affected people may read" (default off). Observers and affected readers see the thread read-only: no answer box, no confirm, no pick, no vote. People who only see that the intent exists see no panel and no thread.
- A draft intent and its thread are visible only to the person who started it.
- Super admin: sees that the intent exists. Never the thread, drafts, nudges or `north` block.
- Company admin: sees the thread and drafts of every intent in the company, never anonymous notes, never sealed text unless a seal rule already gives them access.
- Participant: sees North turns addressed to everyone and turns addressed to them; never another participant's private answers.
- A turn addressed to one person (a nudge, a private question) is visible to that person and the organiser.
- Share link view: confirmed text only; no thread, no drafts, no nudges.
- Who confirms what: the opening message and closure summary by the organiser; a stage question by the asked person; a pick by the person named on the proposal; a signature by the named signer. `may_confirm` is written when the draft is made and checked by the route.
- Time box: North reads 07 and never extends by itself. How many proposals may be open at once is an Open question.
- A draft addressed to a person who has left the intent is moved to the organiser.
- Nudges: the Pulse cap of 7 lines a day still holds. Any limit per person per stage is an Open question.
- Dates and clock lines use the company's time zone from the profile, else UTC.
- Numbers: only counts and dates from records. Counts are exact. Means, medians and any per-person figure show "Fewer than five" below five records (`agents/groups.py` `group_ok`). No per-person averages exist.
- No game words, no model names. Copy follows the UI copy chapter (`.claude/rules/ui-copy.md`).
- Cancelled and closed intents keep the whole thread, read-only.
- Memory: North writes memory only after a conversation ends or an intent closes, through the existing filters. A person can read and edit their own memory on the Memory page (existing).

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Source | Where shown |
|---|---|---|
| Open drafts waiting for this person | `north.drafts` where `status = draft` and the viewer is in `may_confirm` | Panel pill; Pulse |
| Open questions for this person | `north.turn.holder` equals the viewer, plus unanswered `north.asked` | Panel pill; strip |
| Days since the turn holder was last asked | `north.turn.since` and today | Turn strip ("since 3 Oct") |
| Nudges sent for this intent | `north.nudges` count | Organiser's panel footer |
| Drafts confirmed, edited, discarded (three exact counts) | `north.drafts[].status` | Organiser's panel footer; "Not available yet: no drafts made" when `north.drafts` is empty |
| Days over the time box | 07 | Clock line |

Each counter shows "Not available yet" and names the missing record if its source is absent. No figure is computed by North.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

| Existing | Where | Decision |
|---|---|---|
| North's agent module and rules: `next_question`, tool registry build, "listen and check", never invent a figure, "Industry practice (suggestion)" label | `modules/m1_intent/agent/north.py` 53-145, `north_rules.yaml` | Reuse the module and its rules file. Reshape: add a workflow prompt (stage, turn, draft kinds) beside the private-room prompt in a new rules file `north_workflow_rules.yaml`; do not edit the private-room rules |
| North drafting structured output from the person's own words (`propose_cards`, `draft_card`: JSON, "never invent", kept as drafts) | `north.py` 168-227 | Copy the pattern for opening, closure and next drafts (JSON object, parsed, a draft the person confirms) |
| Kernel agent loop, number guard, tool registry, run log | `sh_platform/agents/loop.py` 45-100, `guard.py` 90, `registry.py`, `runs.py` | Reuse unchanged. Facts for the guard are the 07 clock values and record counts |
| Context pack with labelled suggestions and the small-group rule | `sh_platform/agents/context.py` 15-40, `groups.py` | Reuse unchanged |
| North conversation panel: asking now highlighted (`Turn now`), thread, answer box, voice, anonymous and seal boxes | `ui/src/modules/m1_intent/wall/NorthPanel.tsx` 29-143 | Reshape. Copy the structure (asking-now block, thread, answer box, Answer button, voice bar) into a generic `IntentNorthPanel`. Not used here: the four quarter bars and "Put on the wall" (wall-only; they stay on the wall screen) |
| Docked panel shell, bottom sheet at small width, pill | `ui/src/components/AgentPanel.tsx`, `AskBox.tsx`, `ChatSection.tsx` | Reuse unchanged |
| Companion dock with sections and actions | `ui/src/modules/m1_intent/NiraDock.tsx` 40-195 | Not used for North (it is Nira's dock for sessions). Its `askNira`, warning line and `NiraAction` buttons inform the strip and the "actions" row only |
| Conversation turn handling: save person turn, call North, save North turn, draft beside the reply | `modules/m1_intent/api/private_room.py` 312-357 (`_converse`; `_NO_MODEL` at line 44) | Reshape as `north/turns` route; same pattern (model unavailable gives the plain failure line, a failed turn is retried once without documents) |
| Memory store, prompt read, summary at end of conversation, background wrapper | `sh_platform/memory/__init__.py` (`for_prompt` at the end), `memory/summarise.py` 26-65, `memory/filters.py` | Reuse unchanged |
| Drafting a message that sits as a draft until a person sends | `sh_platform/pulse/messages.py` (`draft`, send route), `pulse/templates.py` `WRITERS` | Reuse for opening messages and outside nudges; add kinds only through a new template entry owned by this spec's build package |
| Pulse LINE shape and builders | `sh_platform/pulse/lines.py` `line()` at 71, `invited` 113, `signatures` 175; `docs/plan/SHAPES.md` section 1 | Reuse the shape; add one builder `intents` that reads `north.turn` and `north.nudges` |
| Profile view rules | `sh_platform/profile/view.py` | Reuse unchanged |
| JSON store | `sh_platform/jsonfile.py` (`lock_for`, `read_json_strict`, `write_json_atomic`) | Reuse unchanged |
| Time box and extension for sessions | `modules/m1_intent/api/briefing.py` timer routes (`timer`, `timer/extend`) | Not used: stage-timer for a live session, not an intent time box; 07 decides whether to reshape it |

Genuinely new: the `north` block on the intent record, the thread file, the draft status model, the six routes, the `intents` Pulse builder, the workflow rules file, `IntentNorthPanel`. Searches run: graft ask for "North agent", "conversation panel", "agent memory prompt", "pulse line builder", "draft message send".

## Not in this feature

- The stage screens themselves (wall, define, charter): they own their own forms; North only adds the panel to them.
- The type catalogue, stage lists and start questions (02).
- Clock arithmetic, extension rules and the late state (07).
- The closure form, ratings and the close control (09).
- Lens definitions and the catalogue (their own specs).
- Email delivery (no email path exists yet; messages stay drafts until one does, as in `pulse/messages.py`).
- A background scheduler.
- Voice recording rules beyond reusing the existing voice bar.

## Open questions

1. Clock check without a scheduler: run on open and daily on request, or add a scheduled task? Needs Nitin's call.
2. The nudge window: how many days before a stage end does North start nudging, and how often after the date has passed? No number is justified yet; the build must read it from 07 or a company setting, not hardcode it.
3. Who picks extend, close or cancel on an initiative: the organiser (Janet) or the sponsor (Daniel)? Default in this spec is the organiser; confirm.
4. Should a participant see the other participants' nudge status ("Aaron has not answered") or only "2 people are still to answer"? This spec shows names to the organiser and counts to others; confirm.
5. Proposal limit: may more than one extend, close or cancel proposal be open at once? A build default of one is proposed, not decided.
6. File 35 adds a Brainstorm stage "Prepare"; file 02 has `think_alone`, `live_session`, `choose`. This spec follows 02, so 35 needs correcting. File 02's YAML still lists older start questions (eight for Initiative, six for Problem, a `mind` item kind, no `handled` fate); this spec follows ruling 2 and the per-type files.
7. Do company admins read the thread of every intent, or only the outcome? The brief lets them see existence and outcome; this spec gives them the thread except sealed and anonymous material. Confirm.
8. Memory budget for a workflow turn: 1200 characters is the existing figure for private-room turns; does a workflow draft need more (up to 4000)?
9. Nudge limit: is one open nudge per person per stage right? Proposed, not justified.
