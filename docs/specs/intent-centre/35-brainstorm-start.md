# 35. Starting a Brainstorm

Part of: Intent Centre v2. Depends on: 01 (intent record), 02 (type catalogue), 03 (chooser frame), 05 (areas and visibility), 06 (people and invitations), 07 (time box), 12 (past intents), 21 (backlog), 24 (card model, brainstorm card). Feeds: 36 (the live session, converge happens inside it), 37 (the day after: late thoughts, confirming, closing), 09 (closure), 21 (backlog), 22 (when the outcome becomes an Initiative).

This file is canonical for the Brainstorm's five start questions (brief section 10, ruling 2). File 03 is the chooser frame only and hands over to this file. File 02's YAML for the Brainstorm questions must match the questions here, field for field.

## Purpose (three sentences)
A Brainstorm is for an idea or a problem statement that one person wants six or seven others to think about with them, in one live session, and it ends with a chosen idea or solution that may lead to an initiative. This feature is the five start questions, North's check that the topic is not already being thought about, the invitation, and the pre-thinking that happens before the session. It writes the Brainstorm intent with its three working day time box set around the session date.

## Who uses it and when (role, moment, trigger)
- **Organiser** (Janet at Ardmore). Moment: she has an idea or a problem and wants other people's thinking. Trigger: she picks the Brainstorm tile in the chooser (03), or North proposes it from her free line and she confirms.
- **Invited person** (Aaron, Katie, Harvey). Moment: a Pulse line says Janet has invited them. Trigger: they open it, accept or decline, and add idea cards before the session.
- **Sponsor** (Daniel) is optional. A Brainstorm has none by default (`people.sponsor: null`); the organiser may add one as an observer.
- **Observer.** Reads what a participant reads, never writes or votes (ruling 4). Does not count in the four to eight.
- **Agents decide and draft; people act.** North asks, checks related work, suggests people and areas, drafts the title, the invitation and the message. Janet answers, picks people, sets the date and presses "Open this brainstorm". North never opens, invites or sends. The system never sends a message: the organiser copies it (spec 06).

## Entry points (every route, link, Pulse line, button that leads here)
| From | What the person sees | Lands on |
|---|---|---|
| Chooser tile "Brainstorm" (03 Screen A) | Tile with "Think with six or seven people about an idea or a problem." and chip "3 working days" | `/centre/intent/new?type=brainstorm` (Screen A below) |
| North proposal "Yes, a Brainstorm" (03) | Panel with the drafted title | Same route, question 1 pre-filled from the typed line |
| "Your drafts" row of type Brainstorm (03) | "Carry on" | `/centre/intent/new?type=brainstorm&draft=<id>` at the first unanswered question |
| A backlog item of kind idea (21 Screen D) | Button "Open an intent from this item", type Brainstorm | `/centre/intent/new?type=brainstorm&from=<backlog item id>`; question 1 pre-filled from the item (see Open question 10) |
| A weekly check-in item or a closed intent's `next` (03, 06) | "Start the follow-on" with type Brainstorm | `/centre/intent/new?type=brainstorm&from=<intent id>` |
| Invitation Pulse line (invited person) | "Janet has invited you to think about: <statement>" | `/centre/intent/<id>`, which shows the invitation card in place of the stage view until the person accepts (06 Screen D; no separate invitation route) |
| Pre-thinking Pulse line (invited person, accepted) | "Add your ideas before Thursday's session" | `/centre/intent/<id>/session` in its "before the session" state (Screen D below; see Open question 11) |

The manifest declares `centre/intent/<id>/session` for participants and observers only (default deny). `centre/intent/new` is already declared by 03. Times and dates on every screen use the company's time zone from the profile, else UTC.

## Screens, element by element

### Screen A. The five start questions (route `/centre/intent/new?type=brainstorm`, steps `q1` to `q5`)
This replaces Screens B and C of 03 for the Brainstorm type only. The conversation components are the same (private room: transcript, North question, composer, voice bar, read-back). The stepper reads: "1 Idea  2 Outcome  3 People  4 Areas  5 Session  6 Open". Questions are asked in this order, one at a time.

**Layout at 1280.** Left two thirds: North's question and the answer area for the current step. Right third: the "Your brainstorm so far" card (statement, good outcome, people with count, areas, session date and the three-day window), each row with "Change". Top bar: stepper. **At 390.** One column. The summary card becomes a bar "Question 3 of 5" that opens as a bottom sheet. Sticky footer with "Back" and "Next". Pickers become full-screen sheets.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Stepper | list | Six steps, finished ones ticked | Click or Enter on a finished step jumps back. Later steps are not clickable | Organiser | Step 1 only on arrival |
| Type chip "Brainstorm" with "Change type" | chip + link | The type | Back to the chooser with the answers kept (03 rule) | Organiser | n/a |
| **Q1** North line | agent line | "What is the idea or the problem you want to think about?" with "Why I ask": "The people you invite read this first." | none | Organiser | Always shown first |
| Statement field | field (one line, length limit from the type contract, counter near the limit) | The idea or problem in one line. Placeholder "One line, for example: Performance reviews take two weeks and nobody trusts the scores" | Typing; saved to the draft on blur and on "Next" | Organiser | Placeholder; "Next" disabled |
| Context field | field (multi-line, length limit from the contract, optional) | "Anything people should know before they come" | Typing; saved on blur | Organiser | Placeholder "Optional" |
| Attach context | button | "Add a document as context" (uploads follow the context rules: context, never a figure, never an instruction) | Opens the existing context document picker | Organiser | Hidden if the company has no document store |
| "Already being thought about" panel | panel (North's help, see below) | Related past intents and backlog items from `intents/*/intent.json` and `intents/backlog.json`, the first few rows | Row buttons below | Organiser | "Nothing on this topic that you can see." |
| Related row | list row | Type chip (Brainstorm, Initiative, Problem, Decision, Backlog), title, state, "closed 3 Sep" or "open, ends 14 Oct" (from `closure.closed_at` or `time_box.ends`), one line of why North thinks it is related | "Open" shows it read-only in a side drawer; "Use as context" adds it to `outcome.related` and to the invitation; "Start from this" (backlog or closed intent only) re-points the draft with `links.from` | Organiser | n/a |
| "This is different, carry on" | button | Label | Dismisses the panel; records `related_checked.dismissed: true` | Organiser | Hidden with the panel |
| **Q2** North line | agent line | "What would a good outcome look like when the session is over?" with "Why I ask": "It tells people what to aim at, and tells you when to stop." | none | Organiser | n/a |
| Good outcome field | field (one to three lines, length limit from the contract) | Placeholder "For example: one idea we can test next quarter, with a named owner" | Typing; saved on blur | Organiser | "Next" disabled. Required (a short answer is enough; Open question 1) |
| North read-back | agent line | One line: "So a good outcome is: one idea to test, with an owner." | "That is right" / "Let me correct it" (room pattern) | Organiser | Hidden until the answer is sent |
| **Q3** North line | agent line | "Who should think with you? Pick four to eight people." | none | Organiser | n/a |
| People picker | grouped list with search | Group "Suggested by North", then "Everyone". Row: name, role, team from the company profile; a chip per person | Click or Space adds a person to `people.participants`; the chip has "x" to remove | Organiser | "No people in the company profile yet. Add them in the company profile." with a link. "Next" disabled |
| "Suggested" chip | chip | The word "Suggested" and one reason: "In Finance, which you tagged" or "Raised this in the 2 Oct interview" | Hover or focus shows the reason in full; clicking the row adds the person like any other | Organiser | none |
| "Suggest more people" | button | Label | North re-runs with the current picks as input and adds more rows, still labelled | Organiser | Disabled while North works, hidden when North is off |
| Count line | text | "5 people picked. A Brainstorm needs four to eight." (count of `people.participants` in the draft). Turns to "9 people picked. Take one off." past eight | none | Organiser | "0 people picked. A Brainstorm needs four to eight." |
| "Someone is not listed" | link | Label | One-line note saved in the draft as a request to the company admin (03); the person is not added | Organiser | n/a |
| Seat note | agent line | "Six or seven works well. You can add observers who read but do not add ideas." (observers are not in the four to eight) | none | Organiser | Shown from the third pick |
| **Q4** North line | agent line | "Which parts of the company does this touch?" | none | Organiser | n/a |
| Areas picker | chip multi-select with search (03 pattern) | Company areas; North marks "Suggested" the areas of the people picked and the areas named in the statement | Click or Space toggles | Organiser | "No areas in the company profile yet. Add them in the company profile." "Next" disabled; one area is required |
| Area help line | text | "Everyone tagged to these areas will see that this brainstorm exists, its title, purpose, stage and clock. They open the ideas only if they are invited." | none | Organiser | Always shown |
| Toggle "Affected people may read" | toggle | Label; default off | Sets `affected_may_read` (01). Turning it on shows "People in these areas will be able to read the ideas and the outcome. Anonymous ideas stay anonymous." | Organiser | Off |
| Toggle "Let people hide their name on ideas" | toggle | Label; default off | Sets `outcome.anonymous_ideas` | Organiser | Off |
| **Q5** North line | agent line | "When is the live session?" | none | Organiser | n/a |
| Session date | field (`input type="date"` with time) | Date and start time. Earliest: the next working day (a day for pre-thinking must exist before it) | Typing or picker; invalid dates show "Pick a working day, tomorrow or later" | Organiser | Empty; "Next" disabled |
| Session length | field (two radio buttons) | "45 minutes" / "60 minutes". Default none, one is required (values are proposed, Open question 4) | Selection saved | Organiser | Neither selected; "Next" disabled |
| Three-day window | panel | Three rows, for a session on Thu 15 Oct 2026: "Before: Wed 14 Oct, you and the invited people add ideas", "Session: Thu 15 Oct, 10:00 to 11:00, including choosing the idea", "After: Fri 16 Oct, late thoughts, confirming the outcome and closing". Footer: "Ends Fri 16 Oct". Dates come from the date picked and the working-day rule | none (read-only; derived from the date) | Organiser | Hidden until a date is chosen |
| "Extend" | button | Label | Opens the extend form of 03 and 07 (reason required). Not offered before the date is set | Organiser | Hidden until a date is set |
| Review card | panel | Statement, context, good outcome, people with count, areas, session, window, related items used. Each row has "Change" | "Change" jumps to the step | Organiser | n/a |
| North draft line | agent line | Drafted title (from the statement) and purpose (one line) in editable fields; drafted invitation message under "Your invitation message" | Edit on blur. "Looks right" moves on | Organiser | If North is off the fields start empty and the title is required |
| "Open this brainstorm" | button (primary) | Label, spinner | Validates, writes, opens, creates the invitation lines (see Journey). Lands on `/centre/intent/<id>` | Organiser | Disabled until all five answers are valid, with a line naming the first missing one |
| "Save and leave" | button | Label | Saves the draft; back to `/centre/intent` with the toast "Draft kept in Your drafts" | Organiser | n/a |
| Open failure | alert | "Could not open this brainstorm. Your draft is safe. Try again." with "Try again" | Repeats the open | Organiser | Failure only |

### Screen B. Invitations (the organiser's side, after open)
Route: `/centre/intent/<id>`, panel "Invitations" on the Brainstorm's own page (the full list is also at `/centre/intent/<id>/people`, 06), built from `InvitePanel` (one line that opens), reshaped from seats to named people. **Layout at 1280:** a card in the right column. **At 390:** a one-line row that opens to a sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Invite line | button (as `InvitePanel`) | "6 invited, 2 accepted, 0 declined. Invite" (counts of `people.participants` by `status`) | Expands or collapses the panel | Organiser | "No one invited yet." never shows after open: at least four are required |
| People rows | list | Name, role "Participant", status Invited, Accepted, Declined, with the decline reason if given | "Remind" copies a reminder (06 `reminder` writer). "Take off" removes someone not yet accepted, with a one-line reason | Organiser | n/a |
| "Add someone" | button | Label | Opens the invite dialog of 06 Screen C, limited to the eight-person ceiling | Organiser | Disabled at eight participants with the line "Eight is the most. Take someone off first." |
| Pulse line preview | text | The exact line each person gets: "Janet has invited you to think about <statement>. Session Thu 15 Oct, 10:00 (60 minutes)." | none | Organiser | n/a |
| Drafted message | field (multi-line, editable) | North's draft: who is asking, the problem statement, the good outcome, the session day and time, how long, that ideas can be added from the day before, and the link. Subject line included | Editing saves a version; North never overwrites the organiser's edit | Organiser | Draft always present after open |
| "Copy message" | button | Label | Clipboard write with a status line "Copied" or "Could not copy. Select the text instead." | Organiser | n/a |
| "Copy subject" | button | Label | Copies the subject line, same status line | Organiser | n/a |
| Join link row | field + button | Link and "Copy link", reused from `InvitePanel` | Same as today. "New link" revokes the old one | Organiser | "No link. Make one." with "New link" |
| "Cancel this brainstorm" | button | Label | Asks for a reason, then moves the intent to `cancelled` (see States) | Organiser | Hidden once closed |

### Screen C. The invitation card for the invited person (06 Screen D)
Route `/centre/intent/<id>` (the card replaces the stage view until the person accepts; 06 owns the card). **Layout at 1280:** one column of 640 px, statement large at the top, buttons below. **At 390:** the same column at full width, the three buttons stacked and sticky at the bottom. This feature adds five rows to it.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Problem statement | text | `outcome.statement` and `context`, large | none | Invited person | n/a |
| Good outcome | text | "A good outcome: ..." from `outcome.good_outcome` | none | Invited person | n/a |
| Session and window | text | "Session Thu 15 Oct, 10:00 to 11:00. Ideas open from Wed 14 Oct. We choose the idea in the session and close on Fri 16 Oct." | none | Invited person | n/a |
| Accept, Decline, Ask for a different role | buttons | As in 06. A decline needs a one-line reason for a Participant | As in 06 | Invited person | n/a |
| Related work | list | Titles of the items the organiser chose "Use as context" for, each opening read-only if the person may see it | "Open" | Invited person | Hidden when none |

### Screen D. Pre-thinking: "Add your ideas" (route `/centre/intent/<id>/session`, the "before the session" state, from Pulse)
**Layout at 1280.** One column, 640 px: the statement and good outcome at the top, the add form, then "Your ideas so far". **At 390.** Same column, full width, add button sticks to the bottom.
The form is the brainstorm card of spec 24 Screen D (one text field, "Add your idea", "Hide my name" if the organiser allowed it). No lanes, no quarters. At `session_at` the same route becomes the live session (36).

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Heading | text | "Think before Thursday: <statement>" (the weekday is read from `session_at`) | none | Accepted participants | n/a |
| Window note | text | "Ideas open until the session starts. You can add as many as you like, and change them until then." | none | Accepted participants | After the window closes: "Ideas are closed. Come to the session." |
| Idea field | field (multi-line, length limit from the contract, voice button) | Placeholder "One idea, in your own words" | Typing | The author | "Add" disabled |
| "Hide my name" | toggle | Label, shown only if `outcome.anonymous_ideas` is true | Marks the idea anonymous; stored under the `anon-*` key (D-013 rules) | The author | Hidden when the organiser did not allow it |
| "Add your idea" | button | Label | Writes the card with `session_kind: brainstorm`, `on_wall: false`. Line "Kept. Others see it when the session starts." | The author | Disabled when empty |
| "Your ideas so far" | list | Each of the author's own cards: text, time, "Edit", "Take back" | "Edit" saves a new version (24). "Take back" sets `withdrawn` | The author | "No ideas yet. One is enough." |
| Others' ideas | none | Nothing: pre-thinking is private to the author so that people do not copy each other | none | n/a | n/a |
| Count line (organiser only, on the intent page) | text | "4 of 6 invited have added ideas. 9 ideas." (counts of cards with `session_kind: brainstorm`, `on_wall: false`, by author; no content) | none | Organiser | "No ideas added yet." |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)
1. Janet picks the Brainstorm tile. A draft is written (03). North asks question 1.
2. Janet types the statement and, if she likes, context. **North checks related work** (see Agent behaviour) and shows "Already being thought about". She opens one row, adds it as context, or presses "This is different, carry on".
3. North asks question 2. Janet answers; North reads it back; she confirms.
4. North asks question 3 and offers a labelled "Suggested by North" group. Janet picks the people. The count line turns green at four to eight.
5. North asks question 4 and marks suggested areas. Janet picks at least one and decides whether affected people may read and whether names may be hidden.
6. North asks question 5. Janet picks the date, time and length. The three-day window appears.
7. North drafts the title, the purpose and the invitation message. Janet edits and presses "Looks right".
8. Janet reads the review card and presses "Open this brainstorm". The route validates, sets `state: open`, stamps `time_box`, fills the `outcome` object, adds `stages[0]` "Prepare", and writes the invitation record for each person.
9. Nira places a Pulse line for each invited person (kind `invite`) and for the areas a line "For your information" (kind `invite`, detail says so). North posts the first line on the intent page: "This brainstorm is open. Ideas open on Wed 14 Oct. Session Thu 15 Oct, 10:00."
10. Janet copies the drafted message and sends it herself (email or chat). The system sends nothing.
11. Each invited person accepts or declines. On accept, Nira swaps the invite line for a pre-thinking line (kind `ops`, "Add your ideas before Thursday's session") that becomes active at `time_box.starts`.
12. In the window before the session the invited people add idea cards from Screen D. North reminds those who have not, once, on the day before the session (a line, never a message).
13. At `session_at` the state moves to `in_session` (spec 36). The private idea cards are placed on the shared board (24 `on_wall: true`) with names only where the author did not hide them. Diverge, group and converge all happen inside the live session (36 and 37).
14. The day after is for late thoughts, confirming the outcome and closing (37 and 09). This feature ends at the session start; Janet leaves to `/centre/intent/<id>`.

## States and transitions (table: state, who moves it, to what, what is written)
| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | Organiser picks Brainstorm | draft | New `intents/<id>/intent.json` with `type: brainstorm`, `state: draft`, and `outcome` an empty object of the Brainstorm shape (03; ruling 6). A draft is visible to its organiser only |
| draft | Organiser answers a question | draft | `start_answers[]` entry; `outcome` fields as answered; `draft_updated_at` |
| draft | Organiser presses "Open this brainstorm" | open | `state`, `title`, `purpose`, `areas`, `people`, `affected_may_read`, `time_box`, `outcome`, `stages[0]`, `opened_by`, invitations |
| open | Clock, at `time_box.starts` | open (ideas open) | `outcome.ideas_open_at` stamped; pre-thinking lines become active |
| open | Clock, at `session_at` | in_session | `stages[1]` "Session" opened (spec 36) |
| open | Organiser changes the session date (before the day before it) | open | `session_at`, new `time_box`, `outcome.session_history[{from, to, by, at, reason}]`; invited people get a new Pulse line; North redrafts the message |
| open | Organiser presses "Cancel this brainstorm" | cancelled | `state: cancelled`, `closure.next[{kind: nothing, reason}]`; cards stay, marked withdrawn by cancellation. The intent is kept and shown in Past with its reason |
| invitation | Invited person accepts or declines | Accepted or Declined | `people.participants[].status`, `reason` (spec 06) |
| idea card | Author adds, edits, takes back | private card | Card in `profile.cards` with `session_kind: brainstorm`, `on_wall: false` (24) |

A session date cannot move to fewer than one working day ahead once the window has begun; after `time_box.starts` North proposes "extend" or "cancel" instead.

## Records read and written (file or route, fields; mark Existing or New)
| Item | Read or write | Fields | Status |
|---|---|---|---|
| `intents/<id>/intent.json` through `sh_platform/jsonfile.py` | write | Intent record plus fields below | New file, Existing helper |
| `intents/<id>/events.jsonl` (16) | write | One event per organiser action and per North draft; the record holds counts only | New (from 16) |
| Company profile people, areas, time zone through `sh_platform/profile/api.py` `get_profile`, filtered by `profile/view.py` `read` and `sees_area` | read | `people.<id>.name, role, team, areas`; area names; time zone | Existing |
| Interview records (who was interviewed on which topic): `sh_platform/interview/engine.py` `people` L52 | read | person, question topic, whether the answer was anonymous or sealed (those are never used) | Existing |
| Index of the viewer's visible intents (05 rule, spec 12 history reader) | read | `id, type, title, purpose, state, areas, closure.summary` for open and closed intents the viewer may see | New (reader from 12) |
| `intents/backlog.json` (spec 21) | read | `id, title, kind, areas, status` for items the viewer may see | New (from 21) |
| `profile.cards` through `sh_platform/profile/store.py` | write | The brainstorm idea card of 24, with `intent_id`, `session_kind: brainstorm`, `on_wall: false` | Existing section, fields from 24 |
| `sh_platform/pulse/lines.py` | write | New templates: `invite` for brainstorm, `prethink`, `prethink_reminder`, `fyi` for areas | Existing module, new templates |
| `sh_platform/pulse/templates.py` `invite` | write | The drafted message (subject, body) | Existing, reshaped |
| `POST /api/intents/<id>/related` | read | `{statement}` in, `[{kind, ref, title, state, why}]` out | New |
| `POST /api/intents/<id>/suggest-people` | read | `{statement, areas, picked}` in, `[{person, reason}]` out | New |
| `POST /api/intents/<id>/open` (03) | write | The brainstorm fields validated: statement, good_outcome, people 4 to 8, one area, session in the future | Existing from 03, brainstorm rules added |
| `POST /api/intents/<id>/ideas`, `PATCH` and `DELETE` on a card | write | One idea card of the caller | New |
| Run log | write | Each North draft and each organiser action | Existing |

## Fields this feature adds to the intent record
`outcome` is an object from the moment the intent opens, never null (ruling 6). For a Brainstorm it is shaped as:
```
outcome: {
  statement,            # the idea or problem, one line (Q1)
  context,              # optional longer text (Q1)
  good_outcome,         # one to three lines (Q2)
  session_at,           # ISO date and time of the live session (Q5), shown in the company time zone
  session_minutes,      # 45 or 60 (Q5)
  anonymous_ideas,      # bool, organiser's choice at open
  related: [{kind: intent|backlog, ref, title, note, used_as_context: bool}],
  related_checked: {at, shown: int, dismissed: bool},
  session_history: [{from, to, by, at, reason}],
  ideas_open_at,        # stamped by the clock
  chosen: null          # the chosen idea, written at closure (09 and 37), not here
}
```
Existing fields used: `type`, `title`, `purpose`, `areas`, `affected_may_read` (01), `people.organiser`, `people.participants` (4 to 8), `people.observers`, `people.sponsor` (null by default), `time_box.starts` (start of the working day before `session_at`), `time_box.ends` (end of the working day after), `stages`, `links.from`. Each participant entry carries `status` (Invited, Accepted, Declined) from spec 06. Closure fills `chosen`. No existing field is renamed.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)
- **North, asking.** Five questions in the order above, one at a time, with a read-back after each. Person acts: confirm or correct.
- **North, the related work check.** Runs when Janet leaves question 1 (blur or "Next"), and again if she changes the statement by more than a few words. Reads the statement against the titles and purposes of the intents and backlog items she may see (names tokenised through the gateway, only titles, purposes and closure summaries leave, never content of walls or cards). It returns a short list, each item with one reason ("Closed in September: a brainstorm on slow reviews"). It says "Nothing on this topic that you can see" when there is none; it never reports items the viewer may not see. Person acts: open, use as context, start from it, or carry on.
- **North, suggesting people.** Draws from three sources: people tagged to the areas the statement names, people who raised the topic in company interviews (only if their answer was neither anonymous nor sealed), and people who took part in related past intents. Every row is labelled "Suggested" with its reason. North never fills the list for the organiser. Person acts: click to add.
- **North, suggesting areas.** From the areas of the people picked and the statement. Labelled "Suggested". Person acts: toggle.
- **North, drafting.** Title, purpose and the invitation message (statement, good outcome, session time and length, window, link). Person acts: edit, then "Looks right".
- **North, the clock.** Computes the window from the session date, skipping weekends (holidays when the profile has them). North is responsible for the Brainstorm reaching an outcome inside its time box. If fewer than four have accepted close to the session, North says so and proposes "add someone", "move the session" or "cancel" (when, Open question 6). A named person picks.
- **North, when off.** The questions use fixed wording, the related work panel says "North is not available. Check the backlog yourself" with a link, suggestions are absent, and title, purpose and message start empty.
- **Lens.** Not used here. Definitions come if the outcome becomes an Initiative.
- **Nira.** Places the invitation, area, pre-thinking and reminder lines on Pulse pages and removes them when acted on or when the window closes. Does not write to the intent. Agents never sign.

## Rules (visibility, time box, who may do what)
- Four to eight participants, plus the organiser, plus any observers. Open is blocked outside the range with the reason on screen. The count traces to `people.participants`.
- The session date is a working day, at least one working day after the day the intent is opened, so the day before exists.
- Time box is three working days: the day before (ideas), the session day (the live session, including choosing the idea), and the day after (late thoughts, confirming and closing). An extension needs a reason and is recorded with who and when (07).
- Visibility (ruling 4): a draft is seen only by its organiser. After open, people tagged to the chosen areas, and anyone named affected, see existence, title, purpose, stage, clock, people and the organiser, and the outcome once closed. They open the ideas only if `affected_may_read` is on or a share names them. Participants and observers see the statement, context, good outcome, session details and the board, minus sealed and anonymous material. Observers never write or vote. A super admin sees existence only (ruling 5). A company admin sees existence and the outcome, never anonymous ideas.
- Pre-thinking cards are private to their author until the session starts. The organiser sees counts only. Anonymous ideas keep the D-013 rules.
- Interview material used for suggestions follows the interview rules: nothing anonymous or sealed is read, and a suggestion's reason names no quote.
- North's related-work check lists only what the viewer may already see (05 and 14).
- The organiser may add or take off participants until the day before the session, within four to eight.
- Counts are exact. Any mean or median shows "Fewer than five" below five records (ruling 8).
- Copy: no game words, no model or vendor names, British spelling, no em dashes.

## Counters and measures of this feature (numbers only, each traced to a record)
| Measure | Traced to |
|---|---|
| Brainstorms opened | count of `intents/*/intent.json` with `type: brainstorm` and `opened_by` set |
| Participants per brainstorm | `people.participants` length |
| Invitations accepted of invited | `people.participants[].status` |
| People invited who were North suggestions | participants with `suggested_by: north` over participants; "Not available yet: no brainstorm opened" until one exists |
| Related items shown, and used as context | `outcome.related_checked.shown` and `outcome.related[].used_as_context` |
| Brainstorms where the related check was dismissed | `outcome.related_checked.dismissed` |
| Participants who added at least one idea before the session | idea cards by participant with `on_wall: false` at `session_at`; "Not available yet" before the first session |
| Ideas added before the session | count of cards with `session_kind: brainstorm` and `intent_id` |
| Session date moved | `outcome.session_history` length |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)
Searches run: `graft ask` for the invite panel, the private room conversation, the pulse invite lines and templates, the interview people list, the profile card section. All paths below were checked to exist in this repo on 7 Oct 2026; the line ranges were found with graft and are as read by the first draft of this file.
| Existing | Decision |
|---|---|
| Chooser spec `docs/specs/intent-centre/03-create-intent-chooser.md` (chooser frame, draft, classify, open, cancel, people and area pickers) | Reused for tile, draft, classify, open, cancel and the pickers. Reshaped for Brainstorm only: this file's five questions replace the generic start steps, and "a good outcome" is required here (see Open questions) |
| `ui/src/modules/m1_intent/wall/InvitePanel.tsx` (L10-L70, `getJoinLink`, `newJoinLink`, `revokeSeat` from `m1_intent/api`) | Reshaped. The one-line collapsible card, the join link row and the copy button stay; the rows change from numbered seats to named people with an invitation status. Not rewritten |
| `ui/src/modules/m1_intent/private_room/PrivateRoomScreen.tsx` (`RoomView` L111-L318) and `modules/m1_intent/api/private_room.py` (`_converse` L312-L356, `post_message` L430-L471) | Reused as in 03: conversation, read-back and correction, with the intent start route behind it. The wall's notes, library and finish panels are not used |
| `modules/m1_intent/api/room.py` (join link L205, revoke L221, join L350) | Reused for the optional join link; named invitations are new in 06 |
| `sh_platform/pulse/lines.py` (`invited` L113-L135, line shape, `MINUTES` L22) | Reshaped. A new brainstorm invite template and the new `prethink`, `prethink_reminder`, `fyi` lines follow the same shape. The `ops` minutes (10) are overridden to 5 for pre-thinking (Open question 9) |
| `sh_platform/pulse/templates.py` (`invite` L16, `KINDS` L4) | Reshaped. Subject and body gain statement, good outcome, session time. The organiser copies; nothing is sent |
| `sh_platform/interview/engine.py` (`people` L52) and profile interview data | Reused as one source of people suggestions. Anonymous and sealed material is excluded by `profile/view.py` |
| `sh_platform/profile/api.py` (`get_profile` L72), `profile/view.py` (`read` L116, `sees_area` L79) | Reused unchanged for pickers and the visibility of related items |
| `sh_platform/profile/store.py` (cards section) and spec 24 Screen D | Reused for pre-thinking idea cards; fields from 24 |
| `ui/src/modules/m1_intent/timer/StageTimer.tsx` and `extendTimer` (`ui/src/modules/m1_intent/api.ts`) | Reshaped for "Extend" (reason field), as in 03 and 07 |
| `sh_platform/jsonfile.py` | Reused for `intents/<id>/intent.json` |
| Backlog (21) and past intents (12) readers | Reused for the related-work check; no new store |
| Genuinely new | The five-question flow for Brainstorm, the related-work panel, `suggest-people`, the three-day window computation, the invitation panel rows, the pre-thinking state, the brainstorm invite and pre-think Pulse lines |

## Not in this feature
- The live session itself: the board, the facilitation, diverge, group, and choosing the idea in converge (36 and 37).
- The day after: late thoughts, confirming the outcome and closing (37 and 09).
- Turning the outcome into an Initiative or a backlog item (09, 21).
- Sending messages: the system never sends. Email delivery stays with the organiser.
- Recurring or multi-session brainstorms.
- Editing areas after open (spec 05).

## Open questions
1. Is "a good outcome" required? Nitin lists it as question 2; spec 03 and 02 mark it optional. Proposed: required, one line is enough. Spec 02's YAML must follow the answer.
2. Do anonymous ideas apply in pre-thinking? Proposed: the organiser chooses at open (`anonymous_ideas`), default off. Spec 24 left seal and anonymity in brainstorms open.
3. Are the ideas on the board at the session shown to all, in random order? Proposed yes, to be settled in 36.
4. Field length limits (statement, context, good outcome, idea), the two session lengths (45 and 60 minutes) and how many related rows or extra suggestions North shows: none is in the brief. Proposed values live in the type contract, not in code. Confirm them.
5. How many working days ahead may a session be set? No cap proposed; North flags a date far away (the number is not invented here).
6. When does North warn that fewer than four have accepted, and when does it send the one reminder to people who have added no ideas? Proposed: two working days before the session, and the day before. Not in the brief; confirm.
7. Is more than one session allowed on one Brainstorm? Proposed no: a second session is a new Brainstorm with `links.from`.
8. How does North weigh "related"? Proposed: a judgment on titles and purposes with a reason, never a score on the screen. A similarity threshold is not invented here.
9. Do holidays count in working days? The profile has none today (same as 03 and 07). Proposed: weekends only. Also confirm the 5 minute estimate for the pre-thinking Pulse line.
10. Ruling 1 gives `new?type=<type>&from=<id>` and 03 adds `&draft=<id>`. A backlog item as the source needs either `from=<backlog item id>` (used here, with the id telling the two apart) or its own parameter. Confirm with 03 and 21.
11. Pre-thinking has no view of its own in ruling 1. This file puts it in the `session` view in a "before the session" state. Confirm with 36, or add a view to the ruling.
12. Files 36 and 37 still use old route spellings (`/centre/intent/i/<id>/session`, `/intents/<id>/converge`) and 37 puts converge in a separate stage after the session. Under ruling 1 and this file, converge is inside the live session and the day after is for late thoughts, confirming and closing. 36 and 37 must be corrected to match; the stage list in 02 (Brainstorm 1/1/1) already fits.
