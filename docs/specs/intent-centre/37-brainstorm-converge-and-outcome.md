# 37. Brainstorm converge and outcome

Part of: Intent Centre v2. Depends on: 00-BRIEF, 01 (intent record and lifecycle), 02 (intent types catalogue, Brainstorm stages and outcome), 06 (people and roles), 07 (time box and stage clock), 09 (closure and sign-off), 10 (ratings), 20 (linking intents), 22 (Initiative start questions), 21 (backlog), 24 (card model), 36 (brainstorm session). Feeds: 09 (Next list and outcome block), 10 (rating opens at close), 12 (past intents), 19 (centre counters), 20 and 22 (pre-filled answers), 21 (new backlog item).

## Purpose (three sentences)

After the live session a Brainstorm has many ideas and no answer. This feature lets each seated person back up to three groups or cards, shows only how many backed each (never who), lets the organiser run one more round on the top three, and turns the result into one outcome card that North drafts and the organiser confirms. At closure the organiser says what happens to it (an Initiative, the backlog, or nothing with a reason), people get a short window to add a late thought, and then the record is frozen.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Participant (Aaron, Katie, Harvey as invited) | Stage 3 `choose` opens, after the live session | Pulse line from Nira: "Back up to three ideas in <title>" |
| Organiser (Janet) | Runs the count, breaks a tie, confirms the outcome, picks "What next", closes | North banner on the intent: "Backing is open. 5 of 7 have backed." |
| Sponsor (Daniel), when one is named | Reads the outcome; may back only if also invited as a participant | Pulse line "Outcome ready: <title>" |
| Observer | Reads what a participant reads; never backs, writes or votes (brief ruling 4) | Invitation as observer |
| Affected person and area members | Existence, title, purpose, stage, clock, people, and the outcome once closed. Content opens only if the organiser switched on "affected people may read" at creation, or they are named on a share (ruling 4) | Intent Centre home, past list |
| Company admin | Reads existence and the outcome, never who backed, never anonymous notes | Intent Centre home |
| Super admin | Existence only: title, type, state, areas, people count, dates, time box status (ruling 5). Never content | `/centre/control/intents` |
| North (agent) | Opens the count, nudges, drafts the outcome card and the closure | Stage and clock events (07, 08) |

## Entry points (every route, link, Pulse line, button that leads here)

- Brainstorm intent page (36), `/centre/intent/<id>`: when the live session ends, the organiser's button "Move to choosing" opens stage 3 `choose`. The stage view at `/centre/intent/<id>` then shows Screen A (Converge) to every seated person.
- Pulse line (Nira) to each seated person: "Back up to three ideas in <title>. 2 days left." Links to `/centre/intent/<id>`.
- Pulse line to the organiser when the count is closed: "The count is in. Check the outcome card." Links to `/centre/intent/<id>?view=outcome` (Screen B).
- Closure screen (09), `/centre/intent/<id>/close`: the first row of the Next list for a Brainstorm opens Screen C in place. Screen D (late thought) is also shown to participants on this screen.
- Closed intent page, `/centre/intent/<id>`: Screen D (late thought) continues to show while the window remains open.
- Share link (11): read-only view of the outcome card for the people it names, through the visitor entry `POST /api/modules/m1_intent/shared/view`. Shares are managed at `/centre/intent/<id>/share` (file 11).
- Backlog (21) and Initiative (20, 22): the "Came from" card links back to `/centre/intent/<id>` if the viewer may open it.
- Past list, `/centre/intent/past` (12): a closed Brainstorm opens Screen B read-only at `?view=outcome`.

## Screens, element by element

### A. Converge (route `/centre/intent/<id>`, stage view while stage 3 `choose` is open)

Layout at 1280: header strip (title, chip "Choosing", line "Round <n> of up to <max_rounds>", time left from the stage clock in 07). Left, 8 of 12: the candidate list, groups first (North's groups from the live session), then single cards. Right, 4 of 12: "Your backs" panel, the organiser's "Close the count" panel (organiser only), and the North line. At 390: one column. Header, "Your backs" as a sticky strip showing "2 of 3 used", then the candidate list as cards, organiser panel last. Each candidate opens full-screen on tap.

The numbers "3", "up to 2" and "1" come from the `converge` block of the contract (`max_backs`, `max_rounds`, `round_2_max_backs`) and are stored on the record as `converge.max_backs` and `converge.max_rounds`. They are proposed values, see Open questions 1 and 2.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Round chip | chip | "Round 1" or "Round 2: top three only" from `converge.state` | None | Participants, organiser, sponsor, observers | Not shown before the count opens |
| Candidate row (group) | list row | Group name, number of cards in it (board store cluster `note_count`), three sample ideas, backed count ("4 backed", open-round tally) and a bar sized to the biggest count | Click opens the group with its cards and comments in a side panel | Participants, organiser, observers | "No ideas were added in the live session, so there is nothing to back." The organiser also sees "Close with what we have" (09) |
| Candidate row (card) | list row | The idea text (author shown only when posted by name), backed count | Click opens the card | As above | Not shown when every card sits in a group and the filter is Groups |
| Back this | button (toggle) | "Back this", or "Backed" when on | On: adds this candidate to the person's backs; refused with "You have used all three. Take one back first." when `max_backs` are on. Off: takes it back. Saves at once; can be changed until the count is closed | Participants and organiser (the organiser holds a seat). Not observers, not the sponsor unless seated | Disabled with the reason "The count is closed." or "The count has not opened." |
| Backed count | chip | Number only, for example "4 backed". Never a name, never "you and 3 others". Read from the open-round tally; after close from `outcome.ideas_kept[].backed` | None | Participants, organiser, sponsor, observers | "0 backed" |
| You backed this | chip | Shown on the viewer's own backed rows only | None | The person themselves | Not shown |
| Your backs | panel | The viewer's picked rows as a short list, each with "Take back", and "3 of 3 used" (the viewer's own seat; `converge.max_backs`) | "Take back" turns that back off | The person | "You have not backed anything yet. Pick up to three." |
| Filter chips (All, Groups, Cards) | chip group | Three chips | Filters the list. Counts do not change | Participants, organiser, observers | All shown |
| "n of m have backed" | agent line | n: seats with at least one back (open-round seat keys; after close `rounds[].people_backed`). m: seats in the Brainstorm (participants plus the organiser, from `people`). Never which people | None | Participants, organiser | "No one has backed yet." |
| Tie chip | chip | "Tied with 2 others" on candidates with equal counts across a boundary (first place or third place) | None | Organiser and participants once the count is closed | Not shown |
| Close the count | button (primary) | Label "Close the count" while a round is open | Opens a confirm dialog: "n of m have backed. Close the count? People can no longer change their backs." Confirm closes the round: seat keys are dropped, counts are written, the top three are marked | Organiser | Disabled with "Nobody has backed yet." |
| Tie dialog | dialog | "These ideas are tied for third place: A, B, C. You choose which go into round 2." Checkboxes, exactly the free places | "Use these" writes the pick and the organiser as who made it. "Cancel" closes the dialog and the count stays closed with the tie open | Organiser | Not opened when no tie sits at a boundary |
| Run a second round | button (secondary) | "Run round 2 on the top three" | Opens round 2 with those three candidates only. Each seat may back one of the three (Open question 1). Participants get a new Pulse line | Organiser | Hidden once round 2 has run, or when fewer than three candidates exist ("Only two ideas, so no second round.") |
| Skip to the outcome | button (secondary) | Label | Closes backing if open, then goes to `/centre/intent/<id>/review` | Organiser | Shown after any closed round |
| Close with what we have | button (secondary) | Label | The 09 action: closes with `closure.incomplete` and no chosen idea | Organiser | Always shown to the organiser |
| North line | agent line | Before close: "5 of 7 have backed. 2 days left." After close: "Idea 1 leads with 5 backed" or "Two ideas are tied at the top. You decide." | None; North states, never decides | Everyone who sees the page | "Waiting for the first back." |

### B. Outcome card (route `/centre/intent/<id>?view=outcome`)

Layout at 1280: one centred card, 8 of 12, with the numbers panel to its right, 4 of 12. At 390: card first, runners-up under it, numbers last; the Confirm button is sticky at the bottom.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Outcome card header | panel header | Chip "Draft by North" or "Confirmed by Janet, 8 Oct" (company time zone, else UTC), and the idea title | None | Participants, observers, organiser; affected people once confirmed and closed | "North has not drafted the outcome yet." with button "Draft it" (organiser) |
| Draft it | button | Label | Calls `POST /api/intents/<id>/outcome/draft`. North writes the draft; a draft never overwrites a human edit | Organiser | Hidden when a draft exists |
| The idea | field (editable text) | Chosen group name and North's one-paragraph synthesis, or the chosen card's text (`outcome.chosen.idea`) | Organiser edits in place; an edited text loses "Drafted by North" and keeps editor and time | Organiser edits; others read | "No idea is chosen yet. Pick one from the count." |
| Pick a different idea | link | The candidates of the last closed round with their counts | Selecting one swaps the card. A reason field appears when the pick is not the most backed ("Why this one when another had more backs?") | Organiser | Hidden before the count is closed |
| Why it was chosen | field (editable text) | `outcome.chosen.why`: North's draft, two to four sentences, each with a source chip ("5 of 7 backed", "3 comments", "Round 2"). Counts only, no names of who backed | Organiser edits. North drops a sentence it cannot source | Organiser edits; others read | "Add the reason." Confirm stays off |
| What it would take | list (editable) | `outcome.chosen.what_it_takes`: lines for people, data or systems named in the thinking, and time if the intent says so. Each has a source chip or the mark "North's suggestion" | "Add line" and "Remove" per line; organiser only | Organiser edits; others read | "Not known yet. Add what you know, or write 'To be found out'." |
| Proposed by | field | Names of people who posted the chosen card, or the cards in the chosen group, by name; "and 2 who chose to stay unnamed" when anonymous cards exist (`proposed_unnamed`). One anonymous card: "Proposed anonymously" | None | Participants, observers; affected after close | "Proposed anonymously" |
| Backed by | chip | "5 of 7 backed this" (`chosen.backed`, `chosen.backed_of`), and per round when two ran. Number only | None | Participants, observers, organiser; affected after close | "Not available yet: no count was run." |
| Runners-up | list | The two next candidates by count, with idea text and backed count (`ideas_kept[]` with `runner_up: true`); "Show all (n)" lists every other idea, kept | "Keep" is on by default. The organiser may remove a runner-up with a reason, which moves it to `dropped` | Participants, observers; affected see the outcome only (ruling 4) | "No other ideas." |
| Numbers panel | panel | Ideas added, groups, backs cast, people who backed, rounds run, time from count opened to confirmed. Each from the record named in "Counters" | None | Organiser, sponsor | "Not available yet: <what is missing>" |
| Confirm this outcome | button (primary) | Label | Needs the idea, a reason and at least one "what it would take" line. Writes `confirmed_by`, `confirmed_at`, moves the intent to `closing`, takes the organiser to `/centre/intent/<id>/close` (09) | Organiser | Disabled with the first unmet item named beside it |
| Back to the count | link | Label | Returns to Screen A if a round is open or round 2 may still run | Organiser | Hidden once confirmed |

### C. What next (panel inside 09 Screen A, route `/centre/intent/<id>/close`, Next list)

Layout: the Next list of 09 holds this panel as its first row for a Brainstorm. At 1280 it sits in the left column; at 390 it expands inline.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| What next | radio group | Six choices: "Turn into an Initiative", "Turn into a Problem", "Turn into a Decision", "Put on the backlog", "Mark as handled", "Nothing" (ruling 19 kinds) | Selecting shows that choice's preview below | Organiser edits; others read after close | None selected: Close stays off with "Say what happens next." |
| Initiative preview | panel | The six start questions of file 22, with the answers pre-filled from this outcome (table in User journey step 12). Each pre-filled answer carries the chip "From the brainstorm" (file 20's `prefilled_from`) and is editable here | Organiser edits an answer. Nothing is written to the new intent until Close | Organiser | Questions with no source stay empty and are listed as "You will be asked these" |
| Backlog preview | panel | The item as 21 will hold it: title (the idea), why, raised by (the proposer unless anonymous), "Also considered" (runners-up), and the review date field from 21 | Organiser may change the review date | Organiser | "Raised by: unnamed" when anonymous |
| Nothing reason | field | Required text | Organiser types the reason | Organiser | "Add the reason" |
| Reason line | field | One sentence, required for all three choices (09 rule) | Edit in place | Organiser | "Add the reason" and Close stays off |
| Close this intent | button | The 09 button | Runs the 09 closing checks plus: outcome confirmed, a choice made, a reason written | Organiser | Disabled with the first unmet check named |

### D. Late thought (panel during closing, route `/centre/intent/<id>/close`; continues on closed intent page, route `/centre/intent/<id>`)

Layout at 1280: during closing (09 Screen A), panel in the right column; on closed intent, panel under the outcome block in the left column. At 390: during closing, panel inline; on closed intent, panel under the outcome card. The window line shows the closing time; after that time the record is frozen and no new thoughts can be added.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Window line | agent line | "You can add a late thought until 9 Oct, 15:00. After that the record is frozen." Time is `late_window.closes_at` in the company time zone, else UTC | None | Participants, observers see it but cannot write | After freeze: "This record is frozen." |
| Late thought field | field | Text up to 300 characters, with count (`limits.comment_chars` in `board.yaml`) | Typing enables Add thought | Participants of the intent (not observers, not the sponsor unless seated) | Hint "Something you thought of after the session" |
| By name or Anonymous | toggle | Per the intent's names rule (as comments on the wall): a choice, or fixed with the reason | Sets `anonymous` | Author | Default "By name" |
| About | select | "About: <chosen>, <runner-up 1>, ..." | Sets `about` | Author | Defaults to the chosen idea |
| Add thought | button (primary) | Label | Writes the thought and sends North's note to the organiser | Participants | Disabled until text is typed |
| Late thoughts list | list | Each thought with author (unless anonymous), about which idea, time | None | Participants, observers, organiser, share-link people. Company admin sees by-name thoughts only | "No late thoughts." |
| Frozen chip | chip | "Frozen on 9 Oct" (`frozen_at`) | None | Everyone who opens the record | Not shown while the window is open |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet ends the live session (36) and presses "Move to choosing". North opens stage 3 `choose`, loads the groups and cards from the session record as candidates, and Nira sends each seated person a Pulse line.
2. Aaron opens the intent page. He sees groups and cards with counts at 0. He taps "Back this" on a group, then on two cards. "Your backs" reads "3 of 3 used". A fourth tap shows "You have used all three. Take one back first."
3. Aaron takes one back and backs another. Counts update for everyone; no name moves. (Person.)
4. Between steps, North keeps the clock and tells the organiser "5 of 7 have backed." It nudges each person who has not backed, through that person's own Pulse, once a day until the count is closed. The organiser never sees who is missing.
5. Janet presses "Close the count" and confirms. The server drops the seat keys, writes the counts, and marks the top three.
6. If candidates are tied across a boundary, North says so and the tie dialog asks Janet which go forward. Ties go to the organiser.
7. Janet presses "Run round 2 on the top three". Seated people back again among the three (steps 2 to 5 repeat, once). Or she presses "Skip to the outcome".
8. North drafts the outcome card from the closed counts, the cards and the comments: idea, why it was chosen, what it would take, who proposed it unless anonymous, and the runners-up. Every sentence carries its source.
9. Janet opens `/centre/intent/<id>?view=outcome`, edits the lines, may pick a different idea (with a reason when it was not the most backed), and presses "Confirm this outcome". The intent moves to `closing`.
10. On `/centre/intent/<id>/close` the intent is in the `closing` state. North drafts the summary and shows Screen C. Screen D (late thought window) opens to participants. Janet chooses a "What next" and writes the reason.
11. If she chose an Initiative, North shows the pre-filled start questions. Janet edits and presses "Close this intent" (the intent moves to `closed`).
12. Pre-fill rules, aligned to the six questions of file 22 (every answer marked "From the brainstorm" and editable; marks follow 22: `guessed` until edited):

    | 22 question | Filled from | Left empty |
    |---|---|---|
    | 1 Goal line and why | Goal line: `outcome.chosen.idea` trimmed to 140 characters. Why: `outcome.chosen.why`, then the "what it would take" lines when they fit in 600 characters | Nothing |
    | 2 Whom to involve, who is affected | "Take part": named proposers in `chosen.proposed_by` and the Brainstorm participants, offered as suggested chips only. Never from who backed (nobody can know) | Sponsor and affected |
    | 3 Build needed | Not filled | Yes |
    | 4 Definitions exist | Not filled; 22's own look-up runs once Q1 is saved | Yes |
    | 5 Areas | The Brainstorm's `areas`, offered as chips | No |
    | 6 Decide-by | Not filled; 22's default date applies | Yes |

13. If she chose the backlog, North writes the item (21): idea, why, raised by, runners-up as "Also considered". If "Nothing" or "Handled", Janet writes the reason.
14. Janet presses "Close this intent". State becomes `closed`. North writes the child intent draft or backlog item, sets `links.to`, starts the rating ask (10). Participants may still add late thoughts until `late_window.closes_at`. Janet leaves the screen.
15. Participants add late thoughts while the window is open (during `closing` and briefly after closing, until `late_window.closes_at`). North tells Janet each time one arrives.
16. At `late_window.closes_at` North freezes the record (`frozen_at`). Nothing more can be added; the share link (11) still opens it read-only.

## States and transitions (table: state, who moves it, to what, what is written)

| State | Who moves it | To what | What is written |
|---|---|---|---|
| `converge.state: not_open` | Organiser ("Move to choosing") | `round_1_open` | `outcome.rounds[0].opened_at`, candidate refs, `converge.max_backs`, `converge.max_rounds` |
| `round_1_open` | Participant (back, take back) | same | Seat's backs (seat key kept in the together store only while the round is open) |
| `round_1_open` | Organiser ("Close the count"), or North proposes when stage 3 ends and the organiser presses | `round_1_closed` | Counts per candidate on `outcome.ideas_kept[].backed`, `closed_at`, `closed_by`, `people_backed`, seat keys removed, top three |
| `round_1_closed` | Organiser (tie dialog) | same | `tie_picks`, `tie_broken_by` |
| `round_1_closed` | Organiser ("Run round 2") | `round_2_open` | `outcome.rounds[1]` with the three candidates |
| `round_2_open` | Organiser ("Close the count") | `round_2_closed` | Counts, seat keys removed |
| `round_1_closed` or `round_2_closed` | North (draft); organiser (edits) | outcome draft ready | `outcome.chosen` draft with sources |
| Outcome draft | Organiser ("Confirm this outcome") | `converge.state: done`; intent `in_session` or `open` to `closing` | `chosen.confirmed_by`, `chosen.confirmed_at`, late window opens, `late_window.opens_at`, `closes_at` |
| `closing` | Organiser ("Close this intent") | intent `closed` | `closure.next`, child ref, `closure.closed_at` (09), `outcome.next` (copy of closure.next[0]) |
| Late window open (during `closing` and after) | Participant (add) | same | Entry in `late_thoughts[]` |
| Late window open | North at `closes_at` | frozen | `frozen_at` |
| Any before close | Organiser ("Close with what we have", 09) | `closed` with `closure.incomplete` | `outcome.chosen: null`, reason in `closure` |
| Any before close | Organiser (cancel, 09) | `cancelled` | Cancel reason (09) |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Read or written | Fields | Mark |
|---|---|---|---|
| `intents/<id>/intent.json` via `sh_platform/jsonfile.py` | Read and written | `outcome`, `converge`, `late_window`, `late_thoughts`, `frozen_at`, `closure.next` | New (record defined in 00-BRIEF and 01) |
| `intents/<id>/events.jsonl` (file 16) | Written | One line per back-count close, tie pick, confirm, close, late thought. Never a seat or who backed | New |
| `sh_platform/profile/view.py` | Read | Per-viewer filter | Existing |
| Together store, `modules/m1_intent/store/board.py` `TogetherStore` | Read and written | `votes: {candidate: {seat: "back"}}` for a round in progress; deleted at round close | Existing store, reshaped use |
| Board store, `BoardStore` | Read | Groups and cards of the live session | Existing |
| Cards, `profile.json` section `cards` (24) | Read | `cluster`, `author`, `anonymous`, `session_kind: brainstorm`, text | Existing, extended by 24 |
| `GET /api/intents/<id>/converge` | Route | Candidates, counts, the viewer's own backs, `have_backed` over `seated` | New (reshaped from `GET /sessions/<id>/together`) |
| `POST /api/intents/<id>/converge/open` | Route | Organiser opens round 1 | New |
| `POST /api/intents/<id>/converge/back` | Route | Body `{candidate, on: bool}`; refused over `max_backs` or when closed | New (reshaped from `.../clusters/<cid>/vote`) |
| `POST /api/intents/<id>/converge/close` | Route | Organiser closes the round; body may carry `tie_picks` | New |
| `POST /api/intents/<id>/converge/round2` | Route | Organiser opens round 2 on the top three | New |
| `POST /api/intents/<id>/outcome/draft` | Route | North drafts; organiser only | New |
| `PUT /api/intents/<id>/outcome` | Route | Organiser edits idea, reason, takes, runner-up removals | New |
| `POST /api/intents/<id>/outcome/confirm` | Route | Organiser confirms | New |
| `POST /api/intents/<id>/late-thoughts` | Route | Body `{text, about, anonymous}`; refused when frozen | New |
| `PUT /api/intents/<id>/closure` and `POST /api/intents/<id>/close` (09) | Route | Next choice, close | Defined in 09 (New overall) |
| `POST /api/modules/m1_intent/shared/view` (11, 14) | Route | Visitor read of the closed outcome | Defined in 11 (New) |
| Backlog item (21) | Written | Idea, why, raised by, also considered, `from` | New (owned by 21; this feature calls it) |
| Child Initiative draft (20, 22) | Written | Start answers with `prefilled_from`, `links.from` | New |
| `sh_platform/route_permissions.yaml` | Read | One line per route above (default deny) | Existing file, new lines |
| `modules/m1_intent/contracts/board.yaml` `converge` block | Read | `max_backs`, `max_rounds`, `round_2_max_backs`, `late_window_working_days` | Existing file, new block |

## Fields this feature adds to the intent record

The brief's `outcome`, `closure` and `links` keep their names. `outcome` is an object from the moment the intent opens (ruling 6), never null. For `type: brainstorm`, 02 fixes `outcome = {chosen, ideas_kept, dropped}`. This feature adds keys inside that one shape and renames nothing. It is the single `outcome` shape for Brainstorm; 02 is asked to adopt it (Open question 6). File 20 already reads `outcome.chosen.idea` and `outcome.chosen.why`.

```
outcome: {                                   # at open: {chosen: null, ideas_kept: [], dropped: [], rounds: [], next: null}
  chosen: {
    idea, why,                               # 02 names
    kind: group|card, ref,
    what_it_takes: [{text, source | "north_suggestion"}],
    proposed_by: [{name, account_id}], proposed_unnamed: int,    # anonymous authors counted, never named
    backed: int, backed_of: int,             # seats that backed it, seats in the Brainstorm
    overridden_reason: text | null,          # set when not the most backed
    confirmed_by, confirmed_at
  } | null,
  ideas_kept: [{ref, kind: card|group, text, from | anonymous, group: ref | null,   # 02 names text and from|anonymous
                backed: {round1: int, round2: int | null}, runner_up: bool}],       # ref gives file 20 a stable item id
  dropped: [{ref, text, reason}],            # 02 shape, ref added
  rounds: [{n, candidates: [ref], opened_at, closed_at, closed_by,
            people_backed: int, tie_picks: [ref] | null, tie_broken_by: account_id | null}],
  next: {kind: initiative|backlog|nothing, ref, reason} | null    # copy of closure.next[0], so the outcome reads alone
}
converge: {state: not_open|round_1_open|round_1_closed|round_2_open|round_2_closed|done, max_backs, max_rounds}
late_window: {opens_at, closes_at} | null
late_thoughts: [{by: account_id | null, anonymous: bool, text, about: ref, at}]   # text up to 300 characters
frozen_at: timestamp | null
```

Seat keys during an open round live in the together store only and are deleted at round close. No file keeps who backed what after close, so no person, organiser or admin can read it. Late thoughts marked anonymous carry `by: null`.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** opens the count when stage 3 starts (the person acts: Janet pressed "Move to choosing"). It states progress as "n of m have backed", nudges individuals privately, and proposes closing the count when the stage clock ends; the organiser presses. It proposes round 2 only when places at the top are tied, and says so; the organiser decides. It drafts the outcome card from the counts, cards and comments with a source on every sentence and drops a sentence it cannot source. It drafts "what it would take" only from lines in the thinking and marks the rest "North's suggestion". It drafts the pre-filled Initiative answers and the backlog item. It never chooses the idea, never picks a tie, never confirms, never closes. A draft never overwrites a human edit (hard rule 7).
- **Lens** is not used in this feature. Groups come from the live session (36).
- **Nira** puts the Pulse lines: "Back up to three ideas", "Round 2 is open", "Outcome ready", "You can still add a late thought until <time>". Nira never says who has not backed to anyone but that person.
- People act at: backing, taking back, closing the count, tie pick, round 2, editing the card, confirming, What next, closing, late thought.

## Rules (visibility, time box, who may do what)

- Proposed values, each under Open questions: up to three backs per seat in round 1; up to one in round 2; at most two rounds; top three go to round 2; two runners-up shown; one working day for late thoughts. None is fixed by the brief. They live in the contract, not in code.
- A seat may back groups and cards. A back on a card inside a group counts for the card only (Open question 2).
- Counts are numbers. Nobody sees who backed what, including the organiser, sponsor, company admin and super admin. "n of m have backed" shows who is done only as a count.
- Backs can be changed until the organiser closes the round. A closed round cannot be reopened.
- Ties go to the organiser, at first place and at the third-place boundary. A tie is on equal counts only; no margin is applied. North never breaks a tie.
- Only the organiser confirms the outcome, picks "What next", and closes. Observers never back (ruling 4). The sponsor backs only if seated.
- A reason is required for: choosing an idea that was not the most backed, removing a runner-up, "Nothing", and every "What next" row (09).
- Anonymous cards stay anonymous: the proposer line counts them and never names them (D-013). Late thoughts follow the intent's names rule. The company admin never reads anonymous late thoughts.
- Late thoughts: the record becomes read-only after the intent closes, so the late-thought window runs inside the `closing` state before close, and stays open briefly after close until `late_window.closes_at`. Late thoughts never change the confirmed outcome. At the end of the window the record is frozen; the share link still reads it.
- Time box: the whole Brainstorm stays inside 3 working days (02); converge and confirm sit in the `choose` stage of 1 working day. If the stage will overrun, North offers extend, close with what we have, or cancel (09), and the organiser picks.
- Visibility follows 00-BRIEF section 4 and rulings 4 and 5. Dates and times use the company time zone from the profile, else UTC.
- Cancelled Brainstorms keep their reason and show in Past (ruling 14); a cancelled intent has no outcome card shown beyond its counts.

## Counters and measures of this feature (numbers only, each traced to a record)

All counts are exact. This feature defines no mean, median or per-person figure; any one added later shows "Fewer than five" below five records (ruling 8). No person's backs are counted anywhere.

| Number | Where it shows | Traced to |
|---|---|---|
| Ideas added (cards) | Numbers panel (B) | `cards` filtered by `intent_id`, `on_wall` |
| Groups | Numbers panel | Board store clusters for the session |
| People who backed, over seats | Converge line, outcome card | `outcome.rounds[].people_backed`; seats from `people.participants` plus the organiser |
| Backs cast | Numbers panel | Sum of `outcome.ideas_kept[].backed.round1` and `round2`, plus `chosen` counts |
| Backed count of one candidate | Candidate row | Open round: the existing `tally` of the together store. Closed: `outcome.ideas_kept[].backed` |
| Rounds run | Numbers panel | `len(outcome.rounds)` |
| Time from count opened to confirmed (one intent) | Numbers panel | `rounds[0].opened_at` to `chosen.confirmed_at` |
| Ties broken by the organiser | Centre counters (19) | Count of `rounds[].tie_broken_by` not null |
| Choice at closure, by kind | Centre counters (19) | `outcome.next.kind` across closed Brainstorms |
| Late thoughts per Brainstorm | Closed page, 19 | `len(late_thoughts)` |
| Most backed idea chosen, yes or no | Centre counters (19) | `chosen.overridden_reason` null or set |

Any number whose record is missing shows "Not available yet: <what is missing>".

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Paths checked as present in this repo.

| Existing | Where | Decision |
|---|---|---|
| Together vote, `vote()` | `modules/m1_intent/domain/together.py` 40-47 (one option per seat per cluster, `None` takes it back) | Reshaped: the option is the single value "back"; a new check limits one seat to `max_backs` across candidates. The take-back path (`None`) is kept |
| `tally()` | `domain/together.py` 89-94 | Copied as is, with option ids `["back"]` |
| `check_voting`, stage gate | `domain/together.py` 30-32 | Reshaped: gate on `converge.state` instead of session state |
| `tick()` | `domain/together.py` 82-86 (organiser ticks groups into the charter, many) | Reshaped: the organiser's confirm picks exactly one chosen candidate. Same rule that the organiser decides |
| `auto_decision`, `apply_auto_ticks`, `priority` | `domain/together.py` 97-117 (Must plus Should beats the rest) | Not used: the Brainstorm rule is "back up to three, top three, organiser breaks ties". The tie flag (line 128 of `cluster_view`) is the model for the Tie chip |
| `cluster_view` | `domain/together.py` 120-132 (counts, own vote, tally) | Reshaped: same shape without priority, shelf and comments |
| Seat keys in `votes` | `domain/together.py` docstring lines 1 to 4 (kept by seat; screens get counts and own choice only) | Reused: the same "counts and own choice only" rule. New: seat keys are deleted at round close |
| `TogetherStore`, `BoardStore` | `modules/m1_intent/store/board.py` (class lines 88 and 61) | Reused for the open round; reshaped as stated above |
| Routes vote and tick | `modules/m1_intent/api/together.py` 97-114 (`_change`, vote route), 163-172 (tick route) | Reshaped to `/api/intents/<id>/converge/back` and `/outcome/confirm`; `_change` plumbing (open session, stage check, update store) reused |
| Vote options contract | `modules/m1_intent/contracts/board.yaml` 3-11 (`vote_options`, `auto_tick`) | Not used for the rule. A new `converge` block holds the proposed numbers so none lives in code |
| Comment limit | `board.yaml` `limits.comment_chars: 300`, `comments_per_cluster: 100` | Reused for late thoughts |
| Vote UI | `ui/src/modules/m1_intent/together/ClusterCard.tsx` 22-147 (bar per option, own vote toggle, tick checkbox 43-57), `TogetherScreen.tsx` | Reshaped via graft: one "Back this" toggle per row, "n of 3 used" strip; the tick checkbox becomes "Confirm this outcome" on the outcome card. Bars and Panel components copied |
| API client | `ui/src/modules/m1_intent/api.ts` 528-541 (`voteOn`, `tickCluster`, `pSend`) | Reshaped into `backCandidate` and `confirmOutcome` |
| Card model, comments, names rule | 24, `modules/m1_intent/store/notes.py`, `domain/together.py` 65-79 (`comment()`) | Reused for late thought text and By name or Anonymous |
| Closure, signature, rating panels | 09, 10 | Reused. No signature for a Brainstorm (09) |
| Record store and per-viewer filter | `sh_platform/jsonfile.py`, `sh_platform/profile/view.py`, `sh_platform/route_permissions.yaml` | Reused as they are |
| Genuinely new | Converge route set, outcome card, What next panel, late-thought window and freeze | Searched `converge`, `runner_up`, `late_thought`, `freeze` in `modules/m1_intent` and `sh_platform`: no converge, runner-up or late-thought code. A freeze exists: `modules/m1_intent/store/wall_snapshot.py` `freeze` (line 41, written once, a second freeze changes nothing), called at session close (`store/sessions.py` 230-231). Reused as the model for `frozen_at`: written once |

## Not in this feature

- The live session, private room and grouping (36) and the wall card form (24, 23).
- The closure screen, summary draft and signature (09) and ratings (10). This file adds only the Brainstorm panel and fields.
- Creating an Initiative or its start questions (22), the link mechanics and chain (20), and the backlog and its review (21).
- Named votes, weighted votes, or more than two rounds.
- Editing a confirmed outcome after close. A new intent is the way to revisit it.
- A Decision created from a close vote. File 20 maps Brainstorm to Decision and ruling 7 allows it, but "What next" here offers only 09's three kinds (Open question 8).

## Open questions

1. Backs per seat: three in round 1 and one in round 2 are proposed. The brief gives neither. Confirm, or allow up to three again in round 2.
2. Rounds and candidates: at most two rounds, round 2 on the top three, and a back on a card inside a group counting for the card only (alternative: roll card backs up into the group). None is in the brief.
3. Late-thought window of one working day: not in the brief or 07. Confirm the length. The window now runs during `closing` and briefly after close; organiser may close the intent before the window closes (09).
4. The organiser may pick an idea that was not the most backed, with a written reason (proposed). Confirm, or restrict to ties only.
5. Seat keys are deleted at round close so nobody can ever see who backed what. This differs from the existing vote store, which keeps seats. Confirm that losing the ability to audit a vote is acceptable.
6. File 02 still shows `outcome = {chosen: {idea, why}, ideas_kept: [{text, from|anonymous}], dropped}` and `outcome.fields: [chosen, ideas_kept, dropped]`. This file adds `rounds`, `next`, `ref`, `backed`, `runner_up` and more `chosen` keys. 02 must adopt the shape above; until then the two files differ.
7. Runners-up shown by default: two is proposed; the rest sit under "Show all". No rule in the brief.
8. The six kinds in "What next" (Initiative, Problem, Decision, Backlog, Handled, Nothing) follow ruling 19. Confirm that all six are valid for a Brainstorm closure; the file currently offers only four. Decision is new (ruling 7, file 20 allows Brainstorm to Decision mapping).
9. File 20's pre-fill table for Brainstorm to Initiative uses 02's old question numbers (1 achieve, 2 why now, 3 areas, 5 helpers). File 22 now has six different questions. This file follows 22; 20 should be corrected to the table in User journey step 12.
10. Where the "what it would take" lines go in a new Initiative: 22 has no field for them, so they are appended to the why (600 characters) or kept on the "Came from" card. Confirm.
11. "m" in "n of m have backed" counts the participants plus the organiser (the organiser may back). Confirm that the organiser and the sponsor, if not invited, hold seats as stated.
12. Brainstorm length of live session and who may back (does the sponsor, if not invited, ever back?). See 02 open question 4.
