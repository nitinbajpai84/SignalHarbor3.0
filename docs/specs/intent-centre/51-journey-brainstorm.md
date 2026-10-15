# 51. Journey: a Brainstorm, start to rating

Part of: Intent Centre v2. Depends on: 00 (brief sections 2, 4 and 10), 03, 06, 09, 10, 17, 24, 35, 36, 37, and the wall as built (`docs/guides/TESTING-INTENT-CENTRE.md` section 6). Feeds: the end-to-end test of the Brainstorm type.

## Purpose

This file walks one Brainstorm from "Start an intent" to the ratings, as people at Ardmore would live it. It joins the pieces written in 35 (start), 36 (live session, diverge and group) and 37 (converge, outcome, late thoughts), and adds closure and ratings, so a builder or tester can follow one thread without opening ten specs. The wall is used as built, configured as a brainstorm: one lane instead of four quarters, ideas instead of problems, no votes in diverge or group. All pages follow ruling 1 of the brief: the intent screen is `/centre/intent/<id>`, with the views `/session`, `/projector`, `/close`, `/review` and `/share` under it. Where two specs disagree, this file says which one it follows and lists it under "Spec gaps found".

Synthetic data only. Topic of the walk: "Performance reviews take two weeks and nobody trusts the scores" (the Ardmore HR story). Dates use the real calendar of October 2026 (7 October is a Wednesday). Times use the company's time zone from the profile, else UTC.

## The people (Ardmore synthetic)

| Person | Role in this intent | Area | Sign-in (seed account) | What they are there for |
|---|---|---|---|---|
| Janet Shaw | Organiser | HR, Operations | `company_admin.ardmore@example.test` (provisional, see Open questions) | Opens it, runs the session, closes the count, confirms the outcome, closes it |
| Aaron | Participant | Operations | `participant.ardmore@example.test` | Adds ideas from his phone; uses a join link |
| Katie | Participant (analyst) | Finance | `analyst.ardmore@example.test` | Adds an anonymous idea; reads the data side |
| Harvey | Participant (owner) | Operations | `owner.ardmore@example.test` | Builds on others' ideas; the likely owner of any follow-on |
| Grace | Participant (approver) | Compliance | `approver.ardmore@example.test` | Thinks like anyone else here; signs nothing in a Brainstorm unless the closure asks for an approver |
| Mei Ling | Participant | Treasury | no seed account; test seed as `participant2.ardmore@example.test` | Joins the session late in branch 1; adds a late thought on the day after |
| Ravi | Participant | HR | no seed account; test seed as `participant3.ardmore@example.test` | Adds ideas before the session only; absent on the day in branch 1 |
| Daniel | Sponsor, affected person (not invited to think) | HR (tagged area) | `sponsor.ardmore@example.test` | Sees the Brainstorm exists, reads the outcome after close, may receive a share link |

Six invited: Aaron, Katie, Harvey, Grace, Mei Ling, Ravi. Four to eight is the rule (35, Q3). With Janet, who holds a seat in the count (37), that is seven people in the room. Daniel is in `people.sponsor` and `people.affected`, not `participants`. By ruling 4 he sees existence, title, purpose, stage, clock, people and the outcome once closed, and never the ideas, unless Janet switched on "affected people may read" at creation (default off, left off here) or names him on a share. He holds no vote and cannot rate unless Janet adds him as an observer.

## The path

Clock for the main path: Janet opens on Wed 7 Oct 2026, 15:00. `time_box.starts` Thu 8 Oct 09:00 (ideas open, the day before). Session Fri 9 Oct, 10:00 to 11:00 (the session day). The day after is Mon 12 Oct, the next working day. `time_box.ends` Mon 12 Oct 17:00: three working days, one live session (Thu, Fri, Mon; the weekend does not count).

### Step 1. Start an intent
- Who: Janet. North helps.
- Screen and route: `/centre/intent` then `/centre/intent/new` (03 Screen A).
- She sees: the home page with the button "Start an intent", then five type tiles. The Brainstorm tile reads "Think with six or seven people about an idea or a problem." with the chip "3 working days".
- She clicks: "Start an intent", then the Brainstorm tile. (Alternative: types a line into the box and presses "Ask North"; North proposes "Yes, a Brainstorm".)
- North before the next step: writes a draft `intents/<id>/intent.json` (`type: brainstorm`, `state: draft`, `outcome` an object from the start, ruling 6) and asks question 1.
- Written: the draft record; `created_by: janet`, `created_at`. A draft is visible only to Janet (ruling 14).
- Clock: not running. A draft has no time box.

### Step 2. The five start questions
- Who: Janet. North asks one at a time; Janet answers.
- Screen and route: `/centre/intent/new?type=brainstorm`, steps `q1` to `q5` (35 Screen A). Stepper: Idea, Outcome, People, Areas, Session, Open.
- She sees: Q1 "What is the idea or the problem you want to think about?" Q2 "What would a good outcome look like when the session is over?" Q3 "Who should think with you? Pick four to eight people." Q4 "Which parts of the company does this touch?" Q5 "When is the live session?" The right-hand card "Your brainstorm so far" grows with each answer.
- She clicks or types: the statement (the Ardmore line above); "This is different, carry on" on the related-work panel (see branch 4); good outcome "one idea we can test next quarter, with a named owner", then "That is right"; the six people, accepting two from "Suggested by North"; areas HR and Operations (Daniel is tagged through HR); Fri 9 Oct, 10:00, "60 minutes". The three-day window panel appears: Before Thu 8 Oct, Session Fri 9 Oct, After Mon 12 Oct. The panel "Affected people may read the ideas" stays off.
- North before the next step: checks related work after Q1; reads back Q2; suggests people and areas, each labelled "Suggested"; derives the window; drafts the title, the purpose and the invitation message.
- Written: `start_answers[]`, `outcome {statement, good_outcome, session_at, session_minutes, related}`, `areas`, `people.participants` (status Invited).
- Clock: not running. Janet may press "Save and leave" at any step; the draft waits in "Your drafts".

### Step 3. Review and open
- Who: Janet.
- Screen and route: the review card on the same route, then `/centre/intent/<id>` (35 Screen B).
- She sees: the review card with "Change" on each row, an editable title (60 characters), a purpose line, and "Your invitation message" with a subject.
- She clicks: "Looks right", then "Open this brainstorm".
- North before the next step: validates (four to eight people, one area, a working day tomorrow or later), sets `state: open`, stamps `time_box`, opens `stages[0]` "Prepare", posts the first intent line "This brainstorm is open. Ideas open on Thu 8 Oct. Session Fri 9 Oct, 10:00." Nira places the Pulse lines.
- Written: `state: open`, `time_box {starts, ends}`, `stages[0]`, one invitation per person, `opened_by`, first line in `intents/<id>/events.jsonl` (ruling 12).
- Clock: starts now as a countdown to `time_box.starts`. The brainstorm is visible to everyone tagged to HR and Operations as "exists, title, purpose, stage, clock, people, organiser" (brief section 4, ruling 4).

### Step 4. Invitations
- Who: Janet sends; the six answer; Daniel is told for information.
- Screen and route: Janet on `/centre/intent/<id>` (panel "Invitations", 35 Screen B). Invitees open the same route, which shows their invitation first (06 Screen D, 35 Screen C), reached from Pulse. Daniel opens the same route in the read-only form for an affected person.
- Janet sees: "6 invited, 0 accepted, 0 declined. Invite", the drafted message, "Copy message", "Copy subject", the join link row. Each invitee sees the statement, the good outcome, "Session Fri 9 Oct, 10:00 to 11:00. Ideas open from Thu 8 Oct. We converge in the session and take late thoughts until Mon 12 Oct." and the buttons Accept, Decline, Ask for a different role. Daniel's Pulse line reads "For your information: Janet is running a brainstorm on <statement>" and opens the intent page with title, purpose, stage, clock and people, and no ideas.
- They click: Janet presses "Copy message" and sends it herself (the system sends nothing). Aaron, Katie, Harvey, Grace, Mei Ling and Ravi press "Accept".
- North before the next step: updates the count line ("6 invited, 6 accepted"); swaps each invite line for the pre-thinking line "Add your ideas before Friday's session" (Nira), active at `time_box.starts`.
- Written: `people.participants[].status`, invitation records, Pulse lines.
- Clock: running, 0 working days used.

### Step 5. Pre-thinking on the phone
- Who: the six invited. Alone, on their phones.
- Screen and route: `/centre/intent/<id>` at 390, stage "Prepare", panel "Your ideas" (35 Screen D).
- They see: "Think before Friday: <statement>", the window note "Ideas open until the session starts...", one field "One idea, in your own words", the voice button, "Add your idea", "Your ideas so far". They never see others' ideas.
- They click: Aaron types "Pay custodians by a morning cash sweep" and presses "Add your idea"; the line "Kept. Others see it when the session starts." shows. Ravi adds two ideas. Harvey edits one ("Edit"), then adds another. Katie taps "Hide my name" (Janet allowed it) and adds one.
- North before the next step: on Thu 8 Oct 09:00 stamps `brainstorm.ideas_open_at`. On the morning of Fri 9 Oct sends one reminder line (never a message) to anyone with no idea. Janet's page shows counts only: "4 of 6 invited have added ideas. 9 ideas."
- Written: cards in `profile.cards` with `session_kind: brainstorm`, `on_wall: false`; anonymous cards under the `anon-*` key (D-013).
- Clock: Thu 8 Oct is working day 1 of 3.

### Step 6. The live session: diverge
- Who: Janet opens; everyone adds. North groups.
- Screen and route: `/centre/intent/<id>/session` (36 Screen A), the wall as built in one-lane form. Janet may open `/centre/intent/<id>/projector` on the room screen.
- They see: the problem statement, the phase strip (Diverge lit), the clock, "Live", "5 / 7 people", North's prompt ("Everyone adds. No judging."), the idea lane. The pre-thinking cards were placed on the lane in random order, names shown only where the author did not hide them.
- They click: Janet presses "Open the session" then Yes. Aaron adds a live idea from his phone. Harvey opens Aaron's card and presses "Build on this", writing "only for balances over a set amount". Katie adds an anonymous idea.
- North before the next step: groups as cards land, from the third card (`min_notes`); the group panel shows named groups and "Not grouped yet". At the first minute Nira sends "Your brainstorm is open. Join now."
- Written: `state: in_session`, `session.opened_at`, `session.phase = diverge`, `stages[live_session].opened_at`; cards; replies under cards (replies are not cards).
- Clock: diverge counts down from 15 minutes (36 proposes 15, 10 and 15; not decided, see Open questions). Fri 9 Oct is working day 2 of 3.

### Step 7. Group
- Who: Janet moves the phase; everyone may move cards.
- Screen and route: same route, group phase (36 Screen A, group columns).
- They see: group columns with names and counts; North's prompt "These are the groups I see. Move any card that sits wrong, rename any group."
- They click: Janet presses "Move to group" then Yes. Mei Ling drags a card to another group; Harvey renames a group "Cash timing". Janet presses "Group again" once, answering Yes.
- North before the next step: regroups all current cards; moves already made stay in the move history. At zero on the clock it says "The clock is at zero. Move on, add time or close." and does nothing else.
- Written: `session.phases[] += {diverge}`, `phase = group`, moves, renames.
- Clock: group countdown, 10 minutes proposed.

### Step 8. Converge: back up to three
- Who: Janet runs it; the seven seats take part. North states progress, never decides.
- Screen and route: same session route, converge phase (36 hands over; 37 Screen A owns the controls, shown inside the session view).
- They see: the candidate list, groups first (North's groups from the live session), then single cards; "Round 1"; "Your backs: 0 of 3 used"; "n of 7 have backed" and, per candidate, a backed count as a number only. North's line: "Back up to three ideas you want to carry forward."
- They click: Janet presses "Move to converge" then Yes. Aaron presses "Back this" on one group and two cards; a fourth press shows "You have used all three. Take one back first." He takes one back and backs another. Janet presses "Close the count" and confirms ("6 of 7 have backed. Close the count? People can no longer change their backs.").
- North before the next step: counts progress ("5 of 7 have backed") and nudges each person who has not backed, privately, once; the organiser never sees who is missing. On close it drops the seat keys, writes the counts and marks the top three. Nobody sees who backed what, Janet included. North drafts the outcome card from counts, cards and comments (37 step 8).
- Written: `session.phase = converge`, `converge.rounds[0] {opened_at, closed_at, closed_by, counts, top_three}`; seat keys removed at close; `stages[choose]` opened.
- Clock: converge counts down from 15 minutes (proposed). Round 2 is optional (branch 2). On the main path Janet presses "Skip to the outcome".

### Step 9. The outcome card, confirmed
- Who: Janet decides and confirms. North drafts.
- Screen and route: the session view, panel "Outcome" (37 Screen B, shown inside `/centre/intent/<id>/session` after the count closes). Janet presses "Close the session" first (36), then edits the card.
- She sees: the chip "Draft by North" and the idea "Morning cash sweep for custodian payments", "Backed by 5 of 7", "Why it was chosen" with a source chip on each sentence, "What it would take" lines (each marked from the thinking or "North's suggestion"), "Proposed by Aaron, Harvey and 1 who chose to stay unnamed", runners-up with counts, and the numbers panel (ideas added, groups, backs cast, people who backed, rounds run; each from the record).
- She clicks: edits one "what it would take" line, adds "Owner: Harvey to confirm", then "Confirm this outcome". It needs the idea, a reason and at least one "what it would take" line.
- North before the next step: drops any sentence it cannot source; marks the edited line as Janet's; writes nothing over her edits.
- Written: `outcome.chosen {idea_ref, wording, confirmed_by, confirmed_at, reason}`, `runners_up`, `session.closed_at`, `session.closed_by`; `intent.state = closing`; `stages[live_session].closed_at`.
- Clock: Fri 9 Oct, about 11:00, working day 2 of 3.

### Step 10. Closure, "What next", and the Initiative
- Who: Janet. A named person signs; agents never do.
- Screen and route: `/centre/intent/<id>/close` (09 Screen A, with 37 panel C "What next" as the first Next row).
- She sees: North's drafted `summary`, `why_it_happened`, `what_came_out`, and the choices "Turn into an Initiative", "Put on the backlog", "Nothing", each needing a reason. Under "Turn into an Initiative" the start questions of the Initiative with answers marked "From the brainstorm", editable.
- She clicks: edits one sentence, chooses "Turn into an Initiative", then "Close this intent". If the closure asks for sign-off, the sponsor or approver (Grace) signs by the approver link (09, reused charter approver route).
- North before the next step: writes the child draft at `/centre/intent/new?type=initiative&from=<id>` with the chosen idea as the first statement and answers pre-filled (goal and purpose from the idea and why chosen; people from named proposers and participants offered as suggestions, never from who backed); sets `links.to`; opens the late-thought window and the rating ask.
- Written: `closure {closed_by, closed_at, summary, why_it_happened, what_came_out, next: [{kind: initiative, ref, reason}]}`, `state: closed`, `late_window {opens_at, closes_at}`, `links.to`; the new Initiative draft with `links.from`.
- Clock: the intent is closed, the record stays editable only through late thoughts until `frozen_at`.

### Step 11. Ratings
- Who: each participant. Janet sees the totals.
- Screen and route: `/centre/intent/<id>/review` from Pulse (10 Screen A; results in 10 Screen B on the same view).
- They see: "How worth your time was this?" with 1 to 5 and a note, and "Anonymous" ticked by default (ruling 15).
- They click: Aaron gives 4; Katie gives 5; Grace gives 3 with a note; Harvey and Mei Ling give 4. Each presses "Send rating".
- North before the next step: aggregates counts only. Janet sees "5 of 6 rated" (an exact count, ruling 8). With five records the mean and the spread show; below three no score aggregate shows, and below five a mean shows "Fewer than five". No author is shown on an anonymous rating, no per-person figure exists, and a rating never ranks a person. Each person's own file keeps the link to what they gave.
- Written: `ratings[]` (anonymous, score, note); `rating.rated` holds presence only.
- Clock: ratings stay open after closure and after freeze; there is no deadline.

### Step 12. The day after: late thoughts and the freeze
- Who: any participant adds a late thought. Janet reads. North tells her each time one arrives.
- Screen and route: `/centre/intent/<id>` (closed view, 37 panel D "Late thought"), Mon 12 Oct.
- They see: "You can add a late thought until Mon 12 Oct, 17:00. After that the record is frozen." One field, 300 characters, "By name" or "Anonymous", "About" (the chosen idea or a runner-up), "Add thought". The "Came from here" link on the new Initiative opens the same thoughts.
- They click: Mei Ling writes "Check the banks' cut-off times first" about the chosen idea and presses "Add thought". Harvey adds "I can own this" by name.
- North before the next step: on Mon morning posts "The window closes today at 17:00." to Janet's Pulse. A late thought never changes the confirmed outcome. At `closes_at` North freezes the record; the share link (11) still opens it read-only.
- Written: `late_thoughts[] {by|anonymous, text, about, at}`; at 17:00 `frozen_at`; the last line in `events.jsonl`.
- Clock: Mon 12 Oct is working day 3 of 3, and the time box ends 17:00. Janet may not move the freeze; an extension of the time box needs a reason (07).

## The branches

| Branch | Where it starts | What the people see | What North does | What is written |
|---|---|---|---|---|
| 1. Only three turn up | Step 6, 10:00 | Janet sees "3 / 7 people". Pre-thinking cards from the absent people are on the lane (names kept where chosen) | At 10:05 North says "Three of seven are here. Wait, carry on, or move the session." Janet picks; no automatic action. The threshold for "too few" is not in the specs (Open questions) | `session.attendance_flag`, a line in the transcript, Janet's choice and reason. If she carries on, `closure.why_it_happened` names who was present |
| 2. Ideas are level | Step 8, count closed | A chip "Level with 2 others" at first place or at the third-place boundary | At first place: "Two ideas are level at the top. You decide." At the boundary the tie dialog asks Janet which go into round 2 (checkboxes for the free places). North never breaks a tie. Janet may press "Run round 2 on the top three", where each person backs once among the three (proposed, 37 open question 1), or "Skip to the outcome" | `converge.tie_broken_by`, `tie_picks`, `rounds[1]` if run. If she keeps both, `chosen` holds the first and `next` carries the second as a backlog item |
| 3. Janet picks "Put on the backlog" | Step 10 | Closure Next shows the backlog preview: title, why, raised by, "Also considered", review date, and a required reason | North files the idea into the backlog (21) with the runners-up as "Also considered" | `closure.next [{kind: backlog, ref, reason}]`, a backlog item with `links.from` |
| 4. Same topic last quarter | Step 2, after Q1 | Panel "Already being thought about" lists "Performance review pain points, closed 12 Jun, Brainstorm" with "Open", "Use as context", "Start from this" | North names why it matches (same area, similar words). Janet reads it in a side drawer, adds it as context, or presses "This is different, carry on" | `brainstorm.related`, `related_checked {dismissed: true}`; the invitation lists the related item as titles only |
| 5. A participant adds an anonymous idea | Steps 5 and 6 | The card shows "Anonymous". Janet cannot see the author, and no control reveals it. In the outcome card the proposer line counts it and never names it | North treats it as any other card (groups it, includes it in counts) | The card is stored under `anon-*`; no name in any file, export or admin view (D-013). The company admin never sees anonymous notes |
| 6. The session overruns | Steps 6 to 9 | The clock reaches zero and shows over time in amber | North says "The clock is at zero. Move on, add time or close." Nothing moves by itself. Janet picks "Add time" (minutes, reason), "Move on", or "Close the session" | `session.extended_by[] {by, at, minutes, reason}`. If the session runs past 11:00 the closure summary notes it. The three-day box is untouched unless Janet extends it (07) |
| 7. Nobody backs anything | Step 8 | "No one has backed yet." and "Close the count" disabled | North proposes "Close with what we have" (09) and says the outcome would have no chosen idea | If Janet closes: `outcome.chosen: null`, `closure.incomplete` with her reason |
| 8. Janet picks an idea with fewer backs | Step 9 | "Pick a different idea" shows the three candidates with counts; a field asks "Why this one when another had more backs?" | North records it and drops no wording of Janet's | `chosen.reason` carries the explanation; the card shows it |
| 9. A late thought after the freeze | Step 12, after 17:00 | "This record is frozen." The field is read-only | None | Nothing is written; the request is refused |

## What each person saw in total

"No" means nothing was shown. Counts are exact; anything without five or more records shows "Fewer than five" (ruling 8).

| Person | Saw that it exists | Saw the statement | Saw others' ideas | Saw who wrote | Saw the chosen idea | Saw ratings | Was asked to act |
|---|---|---|---|---|---|---|---|
| Janet | Yes, from step 1 (her draft only she sees until step 3) | Yes | Yes, all, from session open | Named ideas only; never anonymous | Yes, she confirmed it | Totals and notes, no author on an anonymous rating | Start, open, send message, move phases, close the count, confirm, close |
| Aaron | Yes, from his invitation | Yes | No before the session; yes once it opens | Named ideas only | Yes, from step 9 | Totals only when Janet shares them | Accept, add ideas, back, rate, optionally a late thought |
| Katie | Yes | Yes | After the session opens | Named only; her own anonymous idea stays hers alone | Yes | Totals only | Accept, add anonymous idea, back, rate |
| Harvey | Yes | Yes | After the session opens | Named only | Yes | Totals only | Accept, build on ideas, back, rate, late thought |
| Grace | Yes | Yes | After the session opens | Named only | Yes | Totals only | Accept, add ideas, back, rate; sign only if closure asks |
| Mei Ling | Yes | Yes | After the session opens | Named only | Yes | Totals only | Accept, move cards, back, rate, late thought |
| Ravi | Yes | Yes | After the session opens (even in branch 1, only if he rejoins) | Named only | Yes | Totals only | Accept, add ideas before; rate |
| Daniel | Yes, from step 4 | Yes | No (the switch "affected people may read" is off) | No | Yes, from closure | Only if Janet names him on the share | None (information only) |

Nobody sees sealed or anonymous material beyond their rights, and nobody sees who backed what. The super admin sees that the intent exists (title, type, state, areas, people count, dates, time box status) and never its content, and the titles go too if the company switch "titles private to the company" is on (ruling 5). The company admin sees existence and outcome, never anonymous notes.

## The records at the end

All under the Ardmore company data plane, one folder per intent through `sh_platform/jsonfile.py`, read through `sh_platform/profile/view.py`.

| Record | Where | What it holds | Written at step |
|---|---|---|---|
| Brainstorm intent | `intents/<id>/intent.json` | Intent record per brief section 3: type brainstorm, areas HR and Operations, people, time_box, stages Prepare, Live session, Choose, Closure, outcome, closure, ratings, links | 1 to 12 |
| `outcome` | inside the intent file | statement, good outcome, session time, related, chosen idea, runners-up, tie if any | 2, 8, 9, branch 2 |
| `converge` | inside the intent file | rounds, counts, top three, tie picks; no seat keys after a round closes | 8 |
| Idea cards | `profile.cards` (existing store), `session_kind: brainstorm` | text, author or anonymous key, `on_wall`, withdrawn | 5, 6 |
| Replies | under their card | text, author or anonymous | 6 |
| Groups and moves | the board store (existing `m1_intent` board) | group names, moves, renames, North regroups | 6, 7 |
| Session block | `session` in the intent file | phases, pauses, extensions, attendance flag, opened and closed | 6 to 9 |
| Invitations | in the intent file, and Pulse lines | status, reasons | 3, 4 |
| Closure | `closure` in the intent file | summary, why it happened, what came out, next, signer if any | 10 |
| Late thoughts | `late_thoughts[]`, `late_window`, `frozen_at` | text, author or anonymous, about, time | 12 |
| The Initiative draft | its own intent folder | `links.from` this Brainstorm; first statement is the chosen idea | 10 |
| Ratings | `ratings[]` and `rating.rated` | score, note, anonymous flag; presence kept apart from score | 11 |
| Events | `intents/<id>/events.jsonl` (16) | every phase move, count close, confirm, close, late thought, freeze, with who and when; the intent file holds counts only | all |

## Test script

Tool: `.sh-tmp/shot.py <email> <path> <out.png> [--width 1280|390] [--click "text=..."] [--wait ms]`. Paths have no leading slash. Run from the repo root in Git Bash with `.venv/Scripts/python`. Sign-in is by seed account, so the two accounts without a seed (Mei Ling, Ravi) need a test seed step first (see Open questions). Use the built app on 8200 or Vite on 8201 as `shot.py` is set to (it uses 8201). Reseed the Ardmore journey first (`TESTING-INTENT-CENTRE.md`, reseeding section).

Each step is shot at 1280 and at 390 (output names `bs-<step>-1280.png` and `bs-<step>-390.png`). Checks per step (look at the shot, then at the record):

| Step | Account | Path | Checks at 1280 | Checks at 390 |
|---|---|---|---|---|
| 1 | Janet | `centre/intent/new` | Five tiles; Brainstorm tile has "3 working days"; "Ask North" present | Tiles stacked, no sideways scroll |
| 2 | Janet | `centre/intent/new?type=brainstorm` | Stepper has six steps; summary card on the right; related-work panel appears after Q1; window shows Thu 8, Fri 9, Mon 12 Oct | Summary becomes a bar "Question 3 of 5"; sticky footer Back and Next |
| 3 | Janet | `centre/intent/<id>` | "Open this brainstorm" disabled until valid; record has `state: open` and `time_box` after click | Invitations panel is one line that opens |
| 4 | Aaron, Daniel | `centre/intent/<id>` | Aaron: statement, good outcome, session line, Accept, Decline. Daniel: title, purpose, stage, clock, people; no idea content | One column |
| 5 | Aaron | `centre/intent/<id>` | Field, "Add your idea", "Your ideas so far"; others' ideas not shown; counts-only line on Janet's page | Add button sticky at the bottom |
| 6 | Janet and Aaron | `centre/intent/<id>/session` | Phase strip, clock, "Live", "n / 7 people", one lane, group panel after three cards; anonymous card shows "Anonymous" | Sticky top bar with clock; bottom bar "Add an idea"; North panel is a sheet |
| 7 | Janet | same | Group columns; "Group again" asks Yes or No | Cards stacked by group |
| 8 | Janet and Aaron | same | Candidate list, "Your backs: n of 3 used", backed counts as numbers only, no names; a fourth back is refused; "Close the count" asks to confirm; a tie shows "Level with 2 others" if forced | Backs strip sticky "2 of 3 used" |
| 9 | Janet | same, panel "Outcome" | Chosen idea recorded; every sentence has a source chip; "Confirm this outcome" disabled until idea, reason and one line exist | Confirm sticky at the bottom |
| 10 | Janet, then Grace by approver link | `centre/intent/<id>/close` | Next choices with reasons; "Turn into an Initiative" opens a prefilled Initiative draft with `links.from` | Buttons full width |
| 11 | Aaron, Katie | `centre/intent/<id>/review` | Scores 1 to 5, Anonymous ticked by default; results show "5 of 6 rated" and no author on an anonymous rating; below three, no aggregate | Same |
| 12 | Mei Ling, Harvey | `centre/intent/<id>` | Window line "until Mon 12 Oct, 17:00", 300-character field, "About" select; after 17:00 "This record is frozen." and the field is read-only | Panel under the outcome card |

Projector view: shoot `centre/intent/<id>/projector` as Janet at 1920 by 1080 and again at 1280. It must show only the problem statement, clock, idea count (diverge) or group names with counts (group), join box with QR, and Live and people count. Fail the shot if it shows any idea text, reply, author, initials, North panel, session bar or admin control (36 Screen C, 17). In converge 36 does not say what the projector shows; until it does, fail any shot that shows a name of who backed or an idea's text. Also fail on any game word, model or vendor name, em dash, or American spelling in the shot (copy audit in the testing guide).

Record checks after the run: open `intents/<id>/intent.json` for Ardmore and confirm `type`, `state: closed`, `outcome` not null, `outcome.chosen.confirmed_by`, `closure.next[0].kind`, `ratings` length, `late_thoughts` length, `frozen_at` of Mon 12 Oct 17:00 (equal to `time_box.ends`), no author on any `anon-*` card, and no seat key left in `converge.rounds[]`. Open `events.jsonl` and confirm one line per step 3, 6, 7, 8, 9, 10 and 12.

## Spec gaps found

1. Converge timing. 35 puts "converge on one idea" on the day after the session, with "After: Fri 10 Oct, North and you converge on one idea" in its window panel and "We converge on <day after>" in the invitation. 36 and 37 converge inside the session. This walk follows 36 and 37, so the day after is for late thoughts and the freeze; 35's panel and invitation copy need correcting.
2. Calendar in 35 examples ("Wed 8 Oct", "Thu 9 Oct", "Fri 10 Oct") does not match the real October 2026 calendar (7 Oct is a Wednesday). This walk uses the real dates: Thu 8, Fri 9, Mon 12.
3. Day count: three working days (Thu, Fri, Mon) includes a weekend; 07 should say working days skip weekends.
4. Routes outside ruling 1. 37 uses `/intents/<id>/converge` and `/intents/<id>/outcome`; 35 and 06 use `/invitation` and `/ideas`; 10 uses `/rate`. None is in the ruling-1 view list. This walk shows converge and the outcome card inside `/centre/intent/<id>/session`, the invitation and the idea box on `/centre/intent/<id>`, and ratings on `/review`; those files need to say the same.
5. Where the outcome card lives once the session is closed (37 gives it its own route; this walk keeps it in the session view) and whether the `choose` stage opens when the converge phase starts or when the count closes (37 says when the live session ends).
6. Late-thought window length (37: one working day after close) is not in the brief or 07; here it ends at `time_box.ends`, Mon 12 Oct 17:00. 37's own example shows 15:00.
7. 36 defines the projector for diverge and group only; the converge view is not defined.

## Open questions

- Which seed account is Janet? The brief gives Katie as analyst, so `company_admin.ardmore@example.test` is provisional; a company admin never sees anonymous notes, which this walk relies on.
- Phase lengths for diverge, group and converge (36 proposes 15, 10 and 15 minutes for a 60-minute session; not a rule). Round 2 length is not proposed anywhere.
- What counts as too few people in the room in branch 1. The specs give four to eight invited, not a minimum present.
- Whether Daniel as an affected person gets a rating prompt (10 says participants; he is not one).
- Whether pre-thinking cards are shown to all at session start with names, or all anonymous, when the author did not tick "Hide my name" (35 says names where not hidden).
- Whether Janet may rate her own Brainstorm (37 counts her as a seat in the count; this walk counts "of 6" for ratings).
- Whether score notes show when fewer than three ratings exist (ruling 8 sets aggregates from three; notes can identify an anonymous author in a small group).
- The 37 open questions this walk assumes the proposed answers to: one back per person in round 2, a back on a card counts for the card only, and the organiser may pick an idea with fewer backs if she gives a reason.
