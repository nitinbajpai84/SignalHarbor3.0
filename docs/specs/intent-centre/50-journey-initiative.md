# 50. Journey: one Initiative, from first click to hand-off

Part of: Intent Centre v2. Journey file, not a feature file. Reads: 00 brief, 01, 03, 07, 08, 09, 22, 23, 26 to 34. Source order: v1 spec `docs/specs/INTENT-CENTRE-SPEC.md` sections 3 to 6 and `docs/guides/TESTING-INTENT-CENTRE.md` sections 5 to 10, re-ordered under an Initiative intent.

## Purpose

This file walks one Initiative end to end for the Ardmore family office so that one tester, one builder and one reviewer read the same story. It says who is on which screen, what they click, what North and Lens do between clicks, what is written, and how long it takes. Where a feature file and this file disagree on a screen, the feature file wins; where they disagree on order or timing, this file wins and the feature file is fixed.

The demo Initiative: **"Cut the days it takes to produce the quarterly client report"** (synthetic; family office pack; Ardmore demo company). Time box 10 working days. Build needed: yes.

Rules held throughout: agents (North, Lens, Nira) decide and draft, people act at named moments, agents never sign. No game words, no model or vendor names in copy. Every number traces to a record or the screen says "Not available yet" and names what is missing.

## The people (Ardmore synthetic)

| Person | Role in this Initiative | Seed account (Ardmore) | What only this person does |
|---|---|---|---|
| **Janet** | Organiser. Opens the intent, names areas and people, runs the wall and Define, names who does what, presses "Hand to Build". | `company_admin.ardmore@example.test` (see Open questions 1) | Answers the start questions; opens and closes the wall; moves clusters; names the team; hands to Build. |
| **Daniel** | Sponsor. Signs the charter. Answers "Is a build needed?" when Janet does not. | `sponsor.ardmore@example.test` | Signs; sends the charter back with a note; accepts or refuses an extension. |
| **Katie** | Analyst and data owner of the report measures. Confirms technical definitions and catalogue rows. | `analyst.ardmore@example.test` | Confirms technical definition, catalogue entry; confirms the data owner cell for her measures. |
| **Aaron** | Participant. Puts cards on the wall from his private room. | `participant.ardmore@example.test` | Adds, seals or anonymises his own cards. |
| **Harvey** | Source owner of the portfolio system and business owner of the report process. Confirms how the source works. | `owner.ardmore@example.test` | Confirms or corrects his source; says "Not mine, it is X". |
| **Grace** | Governance lead (approver). Settles ambiguous terms, confirms classification and who may see. | `approver.ardmore@example.test` | Picks the meaning of an ambiguous term; confirms classification and who may see. |

Agents: **North** runs the workflow and the clock. **Lens** drafts the process map, data sources, glossary, catalogue and governed state. **Nira** puts "what is waiting for you" and the Pulse lines on each person's page.

## The path

Clock key: "Day" is a working day of the Initiative's 10-day time box. The stage split is the one in file 02's YAML: Think unfiltered 3 days (Days 1 to 3), Define strategically 6 days (Days 4 to 9), Build-ready check 1 day (Day 10). "Typical" is the time a person is on the screen, not elapsed time. Routes follow ruling 1: `/centre/intent/<id>/<view>`.

**Step 1. Janet opens the centre and picks a type. (Day 1, 1 min)**
- Who: Janet.
- Screen: Intent centre home `/centre/intent` (04), then the chooser `/centre/intent/new` (03).
- Sees: the home with running, finished and past intents in her areas; five type tiles; the Initiative tile with the chip "10 working days".
- Clicks: "Start an intent", then the tile "Initiative".
- North/Lens: North creates a draft record and asks the first question.
- Written: `intents/<id>/intent.json` created, `state: draft`, `type: initiative`, `people.organiser: Janet`, `created_at`, `outcome: {}`. `intents/index.json` row added.
- Clock: not started (draft). The draft is visible to Janet only.

**Step 2. Janet answers the six start questions. (Day 1, 8 min)**
- Who: Janet.
- Screen: `/centre/intent/new?type=initiative&step=goal|people|build|definitions|areas|deadline`, then `step=review` (22, Screens A and B).
- Sees: one question at a time with North's draft and a "So far" card. The questions are file 22's, in its order: 1 "What are you trying to achieve?" (goal and why); 2 "Whom do you need to involve, and who is affected?" (sponsor optional, "Just me for now" allowed, switch "Affected people may read this intent", default off); 3 "Do you think this needs a build (new data, pipelines, reports)?" (Yes, No, Not sure); 4 "Do we already have a business glossary and technical definitions for this, or will we discover them along the way?" (Yes, Some, No); 5 "Which areas does this touch?"; 6 "When must this be decided by?" (date, prefilled 10 working days). North reads the profile and drafts answers marked "Guessed".
- Clicks: "Use this draft" or types her own; "That is right" on each read-back; "Next"; at Review, "That is right, open this intent".
- North/Lens: North runs the glossary and catalogue look-up (existing `m2_baseline`) once the goal is saved and says which terms are already defined. It names the sponsor and the people it found in the profile; it never invites anyone.
- Written: `purpose`, `title`, `areas`, `people` (sponsor Daniel, participants Aaron and others, affected), `affected_may_read`, `outcome.goal`, `.build_needed` (value `yes`, with mark, by and time), `.definitions_exist`, `.definitions_found`, `.decide_by`, `time_box.starts/ends`. On "That is right, open this intent": `state: open`, `stages[0]` (Think unfiltered) opened, wall draft created and referenced as `stages[0].ref` (kind `wall_session`).
- Clock: the 10-day time box starts. The stage clock for the wall starts at 3 working days (file 02).

**Step 3. People are invited and the rooms open. (Day 1, 3 min)**
- Who: Janet; then Aaron, Katie, Harvey, Grace, Daniel by invitation.
- Screen: intent page `/centre/intent/<id>`, where the hand-over card has "Open the wall" and the invitation drafts; then the invite panel on the wall `/centre/intent/<id>/wall`.
- Sees: Janet sees stage bar "Think unfiltered", invite panel with a copyable join link, seats taken. Invited people see a Pulse line "Add your cards" (13).
- Clicks: Janet "Open the wall", then "Copy link" or "Send" per invitation. Each invitee opens the Pulse line.
- North/Lens: North sends invitations as drafts for Janet to approve; Nira puts one Pulse line per person.
- Written: `people.participants`, seat records in the wall session, Pulse lines (strip `request`).
- Clock: invitees have until the wall window closes.

**Step 4. The wall: each person adds cards in a private room. (Days 1 to 3, 5 min each)**
- Who: Aaron, Katie, Harvey, Grace, Daniel, Janet (each for themselves).
- Screen: the join link from the invite panel to the private room, then the wall `/centre/intent/<id>/wall` (23). The private room has no view name in ruling 1 (Open questions 3).
- Sees: North asks the four questions one at a time (what it is in business words; where it bites and how hard; how it is tracked today; the most technical definition, "I don't know" accepted). North's draft cards from the person's interview. Four lanes: tracking, missing, watch, levers.
- Clicks: "Use this draft" or types; ticks "Anonymous" or "Seal it"; "Put it on the wall now" (enabled after two of four quarters); "Pick it up" on a dashed suggestion card; "I am done".
- North/Lens: North drafts cards and adds at most three suggestion cards per lane (from the pack and the company's documents). Lens fills Q4 from files when the person says "I don't know" and marks it `guessed` with the document named. Lens never reads a sealed card into a draft others see.
- Written: `cards` in the company profile (lane, q1 to q4, `sealed`, `anonymous`, `author`, `from_interview`); per-lane counts; lean counters (`cards_confirmed`, `cards_new`, `cards_sealed`).
- Clock: wall window (3 working days, file 02). North nudges at 50 and 20 percent (07).

**Step 5. Janet closes the wall; it freezes. (Day 3, 2 min)**
- Who: Janet.
- Screen: `/centre/intent/<id>/wall`, stage bar.
- Sees: counts per lane, silhouettes for sealed cards, who has and has not contributed, North's line "5 of 6 people added cards".
- Clicks: "Next step" then "Close the wall" (confirm).
- North/Lens: North freezes a snapshot. Untouched suggestion cards are dropped and not counted. North clusters the cards, names and colours each cluster; Lens proposes a shelf per cluster, labelled as a suggestion.
- Written: frozen wall snapshot (page one of the charter); clusters with card counts and lanes; stage "Think unfiltered" `closed_at`; stage "Define strategically" opened.
- Clock: Define stage clock starts (spec 07; six working days, Days 4 to 9, then one day for the Build-ready check).

**Step 6. Define: the committee sorts clusters onto shelves. (Day 4, 30 min in one session)**
- Who: Janet, Daniel, Katie, Harvey, Grace.
- Screen: `/centre/intent/<id>/define` (26), tab "Clusters".
- Sees: shelves Must, Should, Good to have, Future; each cluster with colour, card count, votes, measure codes and a governed ring (dashed until every measure is governed). Right panel: Lens's definition for the selected cluster.
- Clicks: drag a cluster to a shelf, or "Move to" menu (390); vote Must/Should/other; "Confirm the definition"; "Send back with a note" (Daniel); "Future" asks a reason and a review date.
- North/Lens: Lens raises at most three ambiguous terms per person. North keeps the clock. Every move is kept with person and time. The vote rule: ticked when Must plus Should votes beat the rest and reach the minimum; Janet breaks ties.
- Written: `cluster.shelf`, vote rows, move history, Future reason and `review_date`.
- Clock: Day 4. Steps 6 to 9 spread over Define, Days 4 to 9; Lens's questions are capped at three open questions per person across Define (A-045, ruling 9).

**Step 7. Process map and data sources. (Days 4 to 5, 10 min each for Katie, 5 min for Harvey)**
- Who: Katie (process map and data sources), Harvey (his source).
- Screen: Define tabs "Process map" (27) and "Data sources" (28): `/centre/intent/<id>/define?tab=process-map` and `?tab=data-sources` (tabs are a query on the `define` view, Open questions 3); Harvey via his Pulse line "Confirm your source: Portfolio system".
- Sees: Lens's drafted processes per cluster (steps, who does them, systems) and a source map with technical areas; guessed cells marked.
- Clicks: Katie "Confirm this process", "Add a process", edits a cell (mark becomes `edited`); Harvey "Confirm this is how Portfolio system works" or "Not mine, it is Aaron".
- North/Lens: Lens drafts both from cards, documents and profile. North nudges Harvey within two working days of the draft.
- Written: process map entries (`guessed` or `edited`); data sources rows with arrival, source owner, technical area; source owner confirmations with time.
- Clock: Days 4 to 5.

**Step 8. Glossary and catalogue. (Days 5 to 7, 15 min Katie, 5 min Grace)**
- Who: Katie (technical definitions, catalogue), Grace (ambiguous terms), the business owner, data owner and source owner of each measure.
- Screen: Define tabs "Glossary" (29), "Catalogue" (30): `/centre/intent/<id>/define?tab=glossary` and `?tab=catalogue`; Katie's own list is the existing baseline "my technical" page (Open questions 3).
- Sees: business terms with their business owner; the "return" case showing three meanings with where each was found; per measure source, fields, calculation, period, currency, personal data class, who may see.
- Clicks: Grace "Pick this meaning" (the choice is recorded as a known risk if the ambiguity is accepted); Katie "Confirm as data owner"; "Send back" with a note.
- North/Lens: Lens updates drafts when new cards or documents arrive; a person's wording is never overwritten, a later draft shows as a proposal.
- Written: `m2_baseline` glossary and catalogue records (existing, referenced); decisions on ambiguous terms; business owner, data owner and source owner confirmations.
- Clock: Days 5 to 7.

**Step 9. Governed state. (Days 7 to 8, 10 min Grace and the owners)**
- Who: Grace, Harvey (business owner and source owner) and Katie (data owner), Janet (reads), Daniel (resolving team at shelving).
- Screen: Define tab "Governed state" (31) at `/centre/intent/<id>/define?tab=governed`; the ring on each cluster; the baseline page of `m2_baseline` shows the same panel (Open questions 3).
- Sees: six fields per measure: owners (business owner, data owner, source owner; the process owner is the business owner of the process), classification, who may see, resolving team and target week, affected downstream, review date; percentages rising (owners, classified, who-may-see confirmed, sealed).
- Clicks: each named owner "Confirm owners"; Grace "Confirm classification" and "Confirm who may see"; Daniel confirms the resolving team at shelving.
- North/Lens: Lens drafts each field with provenance; North nudges the named person. Review date defaults to one quarter and needs nobody.
- Written: governed cells (`confirmed_by`, time) per measure; ring turns solid when all six are confirmed.
- Clock: Days 7 to 8. A cluster may sit on Must or Should only when governed (rule A-054).

**Step 10. Charter, signed by the sponsor. (Day 9, 10 min Janet, 3 min Daniel)**
- Who: Janet drafts and edits; Daniel signs.
- Screen: `/centre/intent/<id>/charter` (32).
- Sees: Page 1 the intent; page 2 the frozen wall; problems with priority and "so that" lines; measures per problem; glossary and catalogue summaries; "Build needed: Yes" with the reason; "Parked for later" (Future shelf); status Draft, then Signed.
- Clicks: Janet "Use this" on each North "so that" draft or edits it; Daniel "Sign the charter", then the modal "Are you the sponsor?" and "Yes, sign".
- North/Lens: North checks no unchecked draft line, at least one problem, build needed answered, then says "Ask Daniel to sign." Nira puts the item on Daniel's list. Agents never sign.
- Written: charter outcome (`m1_intent/outcomes`), signature (name, role, time), `status: signed`; charter read-only from here (house rule 7); `state: closing`.
- Clock: Day 9. North warns two working days before the end if the charter is unsigned.

**Step 11. Who does what. (Day 9, 5 min Janet, 1 min each named person)**
- Who: Janet names; each named person accepts or declines.
- Screen: the "Who does what" panel on the charter, `/centre/intent/<id>/charter?focus=roles` (34).
- Sees: six roles (architect, developer, tester, sponsor, operations, informed, per 34), drafted by North from the people on the wall and in the catalogue; only named people, no blank rows.
- Clicks: Janet edits a name (saves at once); each person on their Pulse line "Accept" or "Decline".
- North/Lens: North drafts the roles and nudges anyone who has not replied.
- Written: `roles` rows with `accepted_by`, time; declines return the line to Janet.
- Clock: Day 9.

**Step 12. Build-ready check. (Day 10, 3 min)**
- Who: Janet.
- Screen: `/centre/intent/<id>/build-ready` (33). Header chip "Build-ready: 7 of 7".
- Sees: the seven lines of file 33: charter signed; every Must and Should measure has a business definition; each has a technical definition, catalogue entry and governed state; every process has a business owner; every data source has a source owner; who does what named; "Build needed is answered yes". Each failing line has a "Fix it" link to the record and a named person.
- Clicks: "See every line"; "Fix it" on any failing line; when 7 of 7, "Hand to Build".
- North/Lens: North recomputes the check on every write and drafts the to-do. Lens drafts any missing definition for a person to confirm.
- Written: `build_ready: {ready, checked_at, lines}`.
- Clock: Day 10 is the last day of the time box.

**Step 13. Hand to Build, and the Initiative closes. (Day 10, 3 min)**
- Who: Janet.
- Screen: confirm dialog on the check page, then closure `/centre/intent/<id>/close` (09), then `/centre/build/gap-analysis?from=<id>`.
- Sees: closure draft by North (what was done, why it happened, what came out), with the next step "Hand to Build". After the hand-off the Build centre opens at gap analysis, the first room, with the charter's measures and the named roles.
- Clicks: "Hand to Build"; "Close the Initiative".
- North/Lens: North writes the closure draft. Agents do not close.
- Written: `links.build: <ref>`, `closure` (closed_by, summary, why_it_happened, what_came_out, `next: [{kind: initiative, ref}]` or Build reference), `state: closed`. Ratings open (10).
- Clock: stops. Time box closed with remaining days recorded.

## The branches

Each branch names where it leaves the path, what each person sees, what is written and where it rejoins.

**B1. Build needed = no (leaves at step 2 or step 12)**
- Janet answers "No" at question 3 (22), or Janet or Daniel answers "No" with a reason in line 7 (33).
- Lines 4 and 5 of the build-ready check stop being required; the other lines show state but never block closure. The charter signature stays required.
- Step 13 changes: no "Hand to Build" button. Janet presses "Go to closure" (33); the closure records the build answer with its reason, who answered and when, as file 33 fixes.
- Written: `build_ready.state: not_needed`; `closure.next: [{kind: nothing, reason}]`. Rejoins at step 13 (closure).
- Page 8 of the charter reads "Build needed: No" with the reason. Build centre is not opened.

**B2. A participant never joins (leaves at step 4)**
- Aaron has not opened the join link by 50 percent of the wall window. North's nudge card (07) to Janet reads "Aaron has not added a card." Nira repeats the line on Aaron's Pulse.
- Janet may resend the invitation, remove Aaron from participants, or proceed. North never removes a person.
- If the wall closes without Aaron, the charter page 2 lists him as "invited, did not contribute" (a count from seat records, not a judgement). His areas still see the intent exists.
- Written: a nudge entry in the intent's `events.jsonl` (ruling 12); seat record unchanged; `people.participants` changed only if Janet removes him. Rejoins at step 5.

**B3. The wall freezes with two cards (leaves at step 5)**
- The wall closes with two cards in total. The system accepts it; no minimum wall size is invented (Open questions 2).
- North says in its closure line "Only 2 cards. Clusters will be thin." and proposes three options: extend the wall window with a reason, close with what we have, or cancel. Janet picks and gives a reason for extend or cancel.
- If Janet proceeds, North clusters the two cards and Define opens with one or two clusters. The charter still needs at least one problem (32), so two cards can pass.
- Written: `time_box.extended_by` (if extended), or a note on `stages[0]`. Rejoins at step 6.

**B4. An ungoverned cluster is pushed to Must (leaves at step 6 or 9)**
- Janet drags a cluster with an ungoverned measure to Must. The drop is refused with a message naming the missing fields and the person who must confirm each, for example "Owners and who may see are not confirmed yet. Harvey and Grace."
- The cluster stays where it was. Nothing moves. The dashed ring stays.
- Janet clicks the message link to the Governed state tab (31) and nudges the named person. Once all six fields are confirmed the ring turns solid and the drop is allowed.
- Written: a refusal entry in the move history (person, time, reason). Rejoins at step 6 or step 9.
- Closing Define with a Must measure not governed is also refused at the build-ready check (31, line 85).

**B5. The sponsor sends the charter back (leaves at step 10)**
- Daniel opens the charter and presses "Send back with a note" instead of "Sign the charter". The note is required.
- Janet gets a Pulse line "Daniel sent the charter back: <note>". North drafts what to change; Janet edits; she presses "Ask Daniel again".
- The charter stays Draft. Nothing signed is overwritten (house rule 7). The note is kept with Daniel's name and time.
- Written: `charter.returns: [{by, at, note}]`, status unchanged. Rejoins at step 10.
- If the return lands inside the last two working days, North proposes extend, close with what we have, or cancel (B6, B7).

**B6. The time box runs out (leaves at any step)**
- At 50 percent North drafts a status from the record only: steps done out of 13, who has not replied, the next unstarted step. At the end, the clock shows overdue (derived; state does not change by itself).
- North drafts three options: Extend by N days with a reason (Janet or Daniel picks), Close with what we have, Cancel.
- Extend: written to `time_box.extended_by: [{by, at, reason}]`; clock returns to on-time or at-half. Close with what we have: closure summary names what is missing; build-ready stays incomplete, no hand-off. Rejoins at the step it left, or at step 13 for close.
- Agents never extend, close or cancel. A named person acts each time.

**B7. The organiser cancels (leaves at any step)**
- Janet opens "Cancel this intent" from the intent page, the wall time card or North's options. A reason is required (03, 07).
- The wall stays readable to participants. The charter, if signed, stays signed and read-only. Nothing is deleted.
- Written: `state: cancelled`; `closure.summary` holds the reason; `closed_by`, `closed_at`. Stage clocks stop. Pulse lines for pending work are withdrawn by Nira.
- The journey ends here; there is no hand-off. The intent appears under past intents with "Cancelled: <reason>".

## What each person saw in total

Counts are for the main path with no branch. Minutes are time on screen, not elapsed. Screens count distinct routes opened.

| Person | Screens | Minutes | Acts (what they did with their own hands) |
|---|---|---|---|
| **Janet** | 10 (home, chooser, start questions, intent page, wall, Define, charter, roles, build-ready, closure) | about 75 | Answered 6 questions; invited people; closed the wall; moved clusters; edited "so that" lines; named roles; pressed "Hand to Build"; closed the Initiative |
| **Daniel** | 5 (Pulse line, Define read-only, charter, build-ready read, closure) | about 15 | Gave a vote; signed the charter; confirmed the resolving team; confirmed the closure |
| **Katie** | 5 (Pulse line, process map, data sources, glossary and catalogue, my-technical) | about 40 | Confirmed process map; confirmed technical definitions and catalogue; confirmed the data owner cell |
| **Aaron** | 3 (Pulse line, private room, wall) | about 8 | Added cards; set one anonymous; picked up one suggestion; accepted a role |
| **Harvey** | 3 (Pulse line, data sources, governed state) | about 10 | Confirmed his source; confirmed owners for his measures |
| **Grace** | 4 (Pulse line, glossary, governed state, baseline) | about 15 | Picked a meaning for an ambiguous term; confirmed classification and who may see |

The figures above are planning targets for the test, not records. The live numbers come from the counters (19): actions and free-text boxes per person, which the lean counters store as numbers only. Until those exist the screen says "Not available yet".

## The records at the end

All under the company data plane (`data/<company>/`). The intent record points at the others by reference; it never copies them (brief section 3).

| File | What it holds |
|---|---|
| `intents/<id>/intent.json` | The intent record: type, title, purpose, people, areas, state, stages, time box and extensions, outcome (outcome.goal, outcome.build_needed, outcome.definitions_exist, outcome.definitions_found, outcome.decide_by), closure, ratings, links (`from`, `to`, `build`), `build_ready`, share, event counts. New |
| `intents/<id>/events.jsonl` | The events of this intent, one file per intent (ruling 12). New |
| `intents/index.json` | One row per intent for the home and lists; rebuilt from the files if damaged. New |
| `intents/m1_intent/sessions/<session_id>.json` | The wall session: seats, invitations, stage, frozen snapshot. Existing |
| `intents/m1_intent/outcomes/<outcome_id>.json` | The charter: problems, "so that", measures, frozen wall as page one, signature, returns, roles. Existing |
| `intents/m2_baseline/outcomes/<outcome_id>.json` | Business glossary, technical glossary, catalogue entries with owner confirmations, known risks for accepted ambiguities. Existing |
| Company profile (`sh_platform.profile`) | `cards` (lane, q1 to q4, sealed, anonymous, author, cluster, shelf) and the `governed` six fields per measure, each with provenance. Existing, extended |
| Process map (spec 27) | Processes per cluster with steps, owners, systems, marks. New |
| Data sources map (spec 28) | Sources with arrival, owner, technical area, confirmations. Reads the baseline through `refs.baseline_ids[0]`. New |
| Pulse messages (`/api/pulse/messages`) | Lines sent to each person and their state (open, done, withdrawn). Existing |
| Run log and egress log | Each North and Lens call, with the minimised payload shown as counts; no names leave. Existing |

Not written by this journey: the gap analysis (first step of Build), the Moment of truth assessment (`m3_connect`), signed baseline for Build. Those start after hand-off.

## Test script

Tool: `.sh-tmp/shot.py` (headless Chromium; signs in as one seed account; saves a PNG).
Usage: `.venv/Scripts/python .sh-tmp/shot.py <email> <path> <out.png> --width 1280|390 [--full] [--click "text=..."] [--wait ms] [--text]`.
Paths have no leading slash (Git Bash mangles it). Run `python tools/doctor.py` first; the production build serves on 8201 (`APP` in the script). Accounts are in `data/_control/seed_credentials.txt`. Output goes to `.sh-tmp/out/journey-initiative/<step>-<who>-<width>.png`.

Method for every step: run each command at `--width 1280` and `--width 390`, one account per command. Use `--click` to press the buttons in order; each click waits 600 ms. `--text` prints the first 6000 characters of the page for checks. Open both PNGs and compare with the canvas artboard for the screen. Console errors print as `CONSOLE ERROR` and fail the step. The tool signs in once per run, so a step that depends on an earlier write needs the earlier steps run first, in order.

| Step | Command (replace `<id>` with the new intent id; run for 1280 and 390) | Checks |
|---|---|---|
| 1 | `shot.py company_admin.ardmore@example.test centre/intent 01-janet-1280.png --click "text=Start an intent"` (the chooser is `centre/intent/new`) | Home lists running, finished and past intents in Janet's areas; five tiles; Initiative tile chip "10 working days". No game words. At 390 the tiles stack, no horizontal scroll. |
| 2 | `shot.py company_admin.ardmore@example.test "centre/intent/new?type=initiative&step=goal" 02-goal.png --text`; repeat with `step=people`, `build`, `definitions`, `areas`, `deadline`, `review` | One question per page at 390; "So far" card at 1280; "Next" disabled while the required answer is missing and names it; North's draft shows a "Guessed" chip; sources named ("From the profile"). Question wording equals file 22. Check all six read-back lines; the review button reads "That is right, open this intent". |
| 3 | `shot.py company_admin.ardmore@example.test centre/intent/<id>/wall 03-invite.png --text` (the wall opens after "Open the wall" on `centre/intent/<id>`) and `shot.py participant.ardmore@example.test centre/pulse 03-aaron-pulse.png --text` | Invite panel has a copyable join link and seats taken. Aaron's Pulse shows only his own line "Add your cards". No other person's line. |
| 4 | `shot.py participant.ardmore@example.test centre/intent/<id>/wall 04-aaron-room.png --text` (the private room opens first for a person with no cards); then the same path as Katie, Harvey, Grace | Four numbered questions; "Put it on the wall now" disabled until two quarters are answered; a sealed card shows as a silhouette to anyone outside the area, including Janet; an anonymous card shows no name; dashed suggestions have "Pick it up". At 390 one lane at a time. |
| 5 | `shot.py company_admin.ardmore@example.test centre/intent/<id>/wall 05-close.png --click "text=Next step" --click "text=Close the wall"` | Run on Day 3. Counts per lane equal the cards put on; dropped suggestions are not counted; stage bar shows Define lit; frozen wall is read-only; North names clusters. |
| 6 | `shot.py company_admin.ardmore@example.test centre/intent/<id>/define 06-define.png --text`; as `sponsor.ardmore@example.test` for the read-only view | Four shelves; each cluster has colour, count, ring; sponsor sees "Send back with a note" and no drag handles. Try a move of an ungoverned cluster to Must: refusal names missing fields (this is branch B4). Future asks for reason and date; the modal does not close until both are set. At 390 the "Move to" menu replaces drag. |
| 7 | `shot.py analyst.ardmore@example.test "centre/intent/<id>/define?tab=process-map" 07-process.png`; `.../define?tab=data-sources`; as `owner.ardmore@example.test` on his Pulse line | Lens cells marked guessed; an edit changes the mark to `edited`; Harvey sees only his source rows, as source owner; "Not mine, it is Aaron" is present. |
| 8 | `shot.py approver.ardmore@example.test "centre/intent/<id>/define?tab=glossary" 08-glossary.png --text`; `shot.py analyst.ardmore@example.test "centre/intent/<id>/define?tab=catalogue" 08-catalogue.png` | The "return" term lists three meanings with where each was found; "Pick this meaning" shows only for Grace and the business owner; a wording a person typed is never overwritten. Catalogue shows source, fields, calculation, period, currency, data class, who may see. |
| 9 | `shot.py approver.ardmore@example.test centre/intent/<id>/define 09-governed.png --click "text=Governed state"` | Six fields per measure, owners shown as business owner, data owner and source owner; percentages rise after each confirm and show "Not available yet" on an empty profile; ring turns solid only with all six confirmed. The baseline page shows the same panel. |
| 10 | `shot.py company_admin.ardmore@example.test centre/intent/<id>/charter 10-charter-janet.png --full`; `shot.py sponsor.ardmore@example.test centre/intent/<id>/charter 10-charter-daniel.png --click "text=Sign the charter"` | Janet cannot sign; "Sign the charter" is disabled while a "so that" draft is unchecked, Page 3 is empty or build needed is unanswered; Daniel sees the confirm modal "Are you the sponsor?"; signature shows name and date and survives reload. Download prints the PDF; at 390 text is not cut off. |
| 11 | `shot.py company_admin.ardmore@example.test "centre/intent/<id>/charter?focus=roles" 11-roles.png`; as `analyst.ardmore@example.test` on his Pulse line | Only named people, no blank rows; edit saves at once; a declined role returns to Janet's Pulse. |
| 12 | `shot.py company_admin.ardmore@example.test centre/intent/<id>/build-ready 12-ready.png --text` | Chip "Build-ready: n of 7"; each failing line has "Fix it" and a name; "Hand to Build" is disabled until 7 of 7. |
| 13 | `shot.py company_admin.ardmore@example.test centre/intent/<id>/build-ready 13-hand.png --click "text=Hand to Build"`; then `centre/build/gap-analysis?from=<id>` and `centre/intent/<id>/close` | The hand-off dialog names who receives it; Build opens at gap analysis, the first room, showing the charter's measures and roles; closure has North's draft and a "Close the Initiative" button; the intent shows closed in the home list. |

Branch checks, each starting from the step where it leaves:

| Branch | How a tester forces it | Check |
|---|---|---|
| B1 build needed = no | Answer "No" at question 3, or at line 7 of step 12 | Lines 4 and 5 stop being required; "Go to closure" replaces "Hand to Build"; charter page 8 says "Build needed: No". |
| B2 participant never joins | Do not open Aaron's join link; advance the clock to 50 percent in the seed | North card names Aaron; Aaron's Pulse repeats the line; the charter lists him as "invited, did not contribute". |
| B3 wall with two cards | Put exactly two cards on the wall, then close it | North says only 2 cards and offers three options; Define still opens. |
| B4 ungoverned to Must | Drag an ungoverned cluster to Must | The refusal names the missing fields and the people; the cluster does not move. |
| B5 charter sent back | As Daniel, "Send back with a note" with and without a note | The button is disabled with no text; with text the charter stays Draft, Janet gets the line, the note is kept with his name. |
| B6 time box runs out | Move `time_box.ends` into the past in the seed | North shows three options; Extend needs a reason and writes `extended_by`; nothing changes without a person. |
| B7 cancel | Janet cancels with and without a reason | A reason is required; the wall stays readable; the intent appears under past intents "Cancelled: <reason>". |

Per-role view checks at the end (run once at 1280 and 390): Aaron sees no other person's sealed or anonymous content, only his own and the shared wall; the super admin (`platform@example.test`) sees that the intent exists (title, type, state, areas, people count) and no content; the company admin sees the outcome and never anonymous notes. Read every `--text` output for game words, vendor names, em dashes and American spelling (the copy audit named in the testing guide, Automated checks).

## Open questions

Minutes and "typical" figures anywhere in this file are planning figures, not measured; a timing run belongs to the first full test pass.

1. The seed has six Ardmore accounts and no separate "organiser" account. This journey uses `company_admin.ardmore@example.test` for Janet. If the seed adds an organiser account, update the table and the commands.
2. No minimum number of cards is set for freezing a wall (B3). The brief says do not invent thresholds. A minimum would need a decision.
3. Screens that ruling 1's view list does not name: the private room (`room`), the Define tabs (`define?tab=process-map|data-sources|glossary|catalogue|governed`), the roles focus (`charter?focus=roles`), the baseline page and the "my technical" list of `m2_baseline`, and the hand-over card's "Open the wall" on `/centre/intent/<id>`. This file treats tabs and focus as query parameters on a named view and the private room as part of `wall`. The rest of the routing is for the owner of file 01 to confirm.
4. The "saw in total" table (screens, minutes, acts) has no source record. Counters (19) must define where per-person action counts come from; until then the screen says "Not available yet".
5. Seven build-ready lines are taken from file 33, and six roles from file 34. The earlier testing guide lists different roles (owner, architect, builder, tester, releaser, analyst liaison). Nitin to confirm which list holds.
6. The vote rule in step 6 ("Must plus Should votes beat the rest and reach the minimum") and the three-day wall window both rely on values no feature spec fixes for other date choices (22, Open questions 4 and 12). The stage split for a decide-by date other than 10 working days is open.
7. `intents/index.json` is named in this file; its owner and rebuild rule are not given by a feature spec read here.
