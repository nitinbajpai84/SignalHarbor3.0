# 00-INDEX. Intent Centre v2: map, journeys, register and build order

Date: 7 October 2026. Integrator's file for the folder `docs/specs/intent-centre/`. It indexes `00-BRIEF.md` and the 55 feature files (01 to 55, 14,966 lines in all, plus the 164-line brief). It changes no other file. Where this index proposes a ruling, the brief and the feature files still have to be corrected to match; nothing here has been applied to them.

How to read it: section 1 says what the centre is. Section 2 is the map of all 55 files. Sections 3 to 5 are the five journeys, the department view and the outputs timeline. Section 6 is the open-question register. Section 7 lists the contradictions the brief's rulings 1 to 24 do not yet settle. Section 8 lists decision requests for `docs/decisions.md`. Section 9 is the build order.

Ruling numbers ("ruling 3") are those in sections 10 and 11 of `00-BRIEF.md`. File references ("05 Q9") mean question 9 in the Open questions of file 05.

## 1. What the Intent Centre v2 is

The Intent Centre is where anyone in a small or mid-size company starts something and where everyone can see what the company is working on. It answers two questions: "I want to do something, where do I start?" (a person opens the centre with an intent, not a form, and the centre asks what they intend to do and runs the right workflow) and "what is happening in the company?" (everyone sees the intents in their area, running, finished and past, so the company has clarity). It starts at what you intend to do, not at the wall. There are five intent types, each with its own start questions, workflow, outcome record and time box: Initiative (10 working days; stages Think unfiltered, Define strategically, Build-ready), Brainstorm (3 days, one live session), Weekly check-in (record key `pulse`; one week, recurring), Problem (5 days) and Decision (2 days). Every intent is one record with one id and one state machine (`draft`, `open`, `in_session`, `closing`, `closed`, `cancelled`), kept in `intents/<id>/intent.json` in the company plane. North runs the workflow and keeps the clock, Lens drafts definitions, Nira keeps "what is waiting for you"; agents draft and people sign, confirm, decide and rate. Visibility follows areas: people tagged to an intent's areas see that it exists, participants open the content, the super admin sees existence only, and a share link is explicit, per intent and read-only. Gap analysis is room 0 of the Build centre, not part of the Intent Centre; an Initiative ends at the Build-ready check and hands over a build-ready charter.

## 2. The map

"Depends on" and "Feeds" are taken from each file's "Part of" line; where the line names a file only in prose, the number is mapped from the body. Files 50 to 54 carry no "Part of" line; their numbers come from their "Reads" lines and bodies and are marked (body). "Lines" is `wc -l` on 7 October 2026.

| No | Title | One-line purpose | Depends on | Feeds | Lines |
|---|---|---|---|---|---|
| 01 | Intent record and lifecycle | The one record, six states, who moves them, the visibility tiers, the nine core routes and the id scheme | brief | all | 275 |
| 02 | Intent types catalogue | The five types, their start questions, stages, outcomes, closers and links, held in `intent_types.yaml` | brief | 03, 12, 20, 21, 22, 33, 35, 38, 41, 43 | 315 |
| 03 | Create-intent chooser | "What do you want to do?": five tiles, free-text classify, draft, hand-over to the per-type questions | 01, 02, 04 | 13, 22, 35, 38, 41, 43 | 190 |
| 04 | Intent Centre home | Lanes of intent cards per area, Start button, Your turn strip, past list, four counters | 03, 19 (brief) | 12, 13, 33 | 243 |
| 05 | Areas and visibility | Areas as tags on intents and people, the visibility matrix, super admin existence view | brief | all | 286 |
| 06 | People and roles in an intent | People panel, invite, accept or decline with reason, join link, `people_detail` | 01, 02, 05, 22, 35, 38, 41, 43 | 07, 09, 11, 13, 16, 47, 48 | 309 |
| 07 | Time box and stage clock | Clock states, extend dialog and approval, North's time card, overdue panel, auto-freeze | 02, 03, 05, 08, 09, 13, 22 | 04, 13, 19 | 264 |
| 08 | North as workflow runner | North panel, turns, drafts marked until confirmed, nudges, proposals, what North may never do | 02, 07, 09 | every intent screen, 07, 09 | 318 |
| 09 | Closure and sign-off | One closure screen for every type: why, what came out, next list, signature, close with what we have, cancel | 10, 40, brief | 04, 13, 21, 33 | 263 |
| 10 | Ratings and session value | One to five rating at closure, ratings panel, "was the outcome used" a month later, ratings summary | 09, 13, brief | 13, 08, outcomes page | 247 |
| 11 | Share link and visitor view | Organiser shares an intent read-only with named people or areas; log, notes, withdraw | 01, 05, 13 | 09, 13 | 238 |
| 12 | Past intents and history | Past view by area and month, "where did this lead" chain, history notes, share requests | 01, 05, 09, 10, 16, 20 | 04, 13 | 293 |
| 13 | Pulse lines and notifications | The 17 intent lines on the daily Pulse page, the seven-line cap and drafted messages | 02, 26, 37, 38 | 45, 09, 10, 11, every type | 256 |
| 14 | Permissions matrix | Route and page access for six company roles plus super admin; per-intent layer on top of default deny | 02, brief | every file that adds a route | 597 |
| 15 | Search and filters | One search box, chip groups and sort for home and Past; the search index | 01, 02, 05, 10 | 04, 12, 48 | 255 |
| 16 | Transcript and audit trail | Append-only `events.jsonl`, the "What happened" tab, Markdown and print download | 01, 06, 07, 09 | 04, 10, 11, 33 | 290 |
| 17 | Phone and projector views | 390 px rules per screen family and the names-free projector view | 01, 02, 03, 04, 06 | 26 to 31, 35 to 40 | 381 |
| 18 | Empty states and first run | First-run home, no-areas panel and the words for every empty state | 01, 02, 03, 04, 06, 09, 11, 12, 15, 23, 26 to 31, 35 to 43, 49 | the same files | 248 |
| 19 | Centre counters and measures | Fifteen measures (M01 to M15) computed on read; "Not available yet" and what is missing | 01, 02, 04, 06 | 04, 09, 10 | 199 |
| 20 | Linking intents | Turn an intent or one item into the next intent, backlog item or Build hand-off; chain | 01, 02, 03, 06, 09, 16, 21, 22, 35, 38, 41, 43 | 04, 11, 12, 55 | 308 |
| 21 | Backlog | Items held between intents with source, raiser, why and review date; open, merge, park, drop | 01 to 05, 09, 38 | 04, 09, 22, 35, 41, 43 | 274 |
| 22 | Initiative start | Canonical six start questions; "here is what I understood"; open and prepare the wall | 01, 02, 03, 06, 07 | 23, 26 | 325 |
| 23 | Think unfiltered: the wall | Initiative stage 1: private rooms with North, then the wall; freeze at window end | 01, 02, 06, 07, 22 | 24, 26, 09, 32 | 233 |
| 24 | The card model | Card record, seal and anonymous taps, edit, withdraw, move; the single-quarter brainstorm card | 01, 06, 07 | 23, 26, 36, 09 | 246 |
| 25 | North's suggestion cards | At most three dashed suggestions per lane, dropped when the wall freezes | 01, 02, 07 (04, 36 body) | 04, 09 | 207 |
| 26 | Define strategically: clusters and shelves | One session turns the wall into clusters on four shelves; writes the charter draft | 01, 02, 06, 07, 08, 27 to 30 (31) | 09, 27 to 30, 33 | 306 |
| 27 | Process map | Lens drafts processes from cards and documents; the business owner confirms | 01, 06, 28 | 28, 30, 31, 32, 33 | 284 |
| 28 | Data sources and technical areas | Committee names sources and technical areas; Lens drafts; the source owner confirms | 01, 02, 06, 07, 08, 27, 30, 31 | 27, 30, 33 | 239 |
| 29 | Business glossary | Lens drafts every term; owner confirms; governance lead settles ambiguities; one definition per term | 01, 05, 06, 08, 22 | 09, 30, 32 | 261 |
| 30 | Technical glossary and data catalogue | Nine-part technical definition and one catalogue entry per measure, under one code | 05, 06, 09, 28, 29 (31) | 32, 33, Build gap analysis | 251 |
| 31 | Governed state per measure | Six provenance cells per measure and a ring per cluster; Build reads them | 01, 05, 06, 14 | 09, 13, 19, 33 | 265 |
| 32 | Charter and signature | The ten-page charter; North drafts, organiser edits, sponsor signs once | 01, 06, 09, 27, 28, 30, 33, 34 | 09, 11, 33 | 258 |
| 33 | Build-ready check and hand-off | Seven-line check; "Hand to Build" writes `links.build` and opens gap analysis | 01, 08, 09, 19, 27, 28, 34 (29 to 32) | 04, 13, 19, Build | 270 |
| 34 | Who does what | Six Build roles named at the charter; each named person accepts or declines | 01, 06, 13 | 09, 19, 32, 33 | 242 |
| 35 | Starting a Brainstorm | Five start questions, related-work check, invitation, pre-thinking | 01, 02, 03, 05, 06, 07, 12, 21, 24 | 36, 37, 09, 21, 22 | 257 |
| 36 | The Brainstorm session screen | Live session: one lane, idea cards, North groups, organiser runs the clock | 01, 02, 06, 07, 17, 24 | 37, 09, 10 | 280 |
| 37 | Brainstorm converge and outcome | Back up to three ideas, optional round 2, one outcome card, what next, late thoughts | 01, 02, 06, 07, 09, 10, 20, 21, 22, 24, 36 | 09, 10, 12, 19, 20, 21, 22 | 297 |
| 38 | Weekly check-in setup | Set up the series once; open one week file by the clock; pause or end | 01, 02, 03, 05, 06, 07, 08, 13, 21 | 09, 12, 19, 21, 39, 40, 41 | 268 |
| 39 | Weekly check-in entry | The reporter's two-minute screen: ran, broke and thought items; prefill marked guessed | 01, 02, 05, 07, 13, 16, 24, 27, 38 | 09, 19, 21, 40 | 288 |
| 40 | Weekly check-in review and outcome | Digest, one fate and reason per item, close the week, reporters see decisions, trends | 01, 02, 07, 09, 13, 17, 21, 38, 39, 41 | 04, 12, 19, 21, 41 | 275 |
| 41 | Problem start, triage and acceptance | Five start questions; North proposes an owner; accept or pass | 01, 02, 03, 05, 07, 13, 16, 38 | 42, 09, 21 | 243 |
| 42 | Problem resolution and closure | From "owner holds it" to root cause, fix, affected confirm and closure; reopen once | 01, 02, 07, 08, 09, 10, 13, 20, 22, 41 | 12, 19, 21 | 249 |
| 43 | Decision intent | Options, adviser notes, one named decider decides and records; no decision or decide later | 01, 02, 03, 06, 07, 09, 10, 20 | 04, 11, 13, 21 | 300 |
| 44 | Lens in Define | Lens drafts nine kinds of Define content unattended; at most three questions per person | 01, 06, 26 to 30 | 09, 13, 26, 29, 30, 33 | 306 |
| 45 | Nira: what is waiting for you | Each person's list across intents, computed on read; the organiser's "who has not acted" panel | 01, 02, 06, 07, 13, 14 | 04, 13, 19 | 253 |
| 46 | Agent memory in intents | At closure the agents write short filtered memory lines; North's opening line uses them | 01, 08, 09, 24, 29, 30, 32 | 03, 19, 22 | 247 |
| 47 | Affected and observer experience | What an affected person or observer sees and may do; "I feel this", notes, ask to join | 03, 04, 05, 06, 13, 21, 22, 24 | 09, 14, 19 | 316 |
| 48 | Admin views | Company admin list, overdue, unrated, counters, defaults, admin cancel; super admin existence | 01, 02, 03, 05, 07, 09, 10, 14, 19, 38 | 14, 18 | 311 |
| 49 | Pack suggestions | Industry pack gives dashed, labelled suggestions: first intents, start hints, check-in questions | 01, 02, 03, 05, 18, 25, 38 | 03, 04, 18, 22, 38 | 248 |
| 50 | Journey: an Initiative | Thirteen steps from first click to hand-off, with seven branches | 01, 03, 07, 08, 09, 22, 23, 26 to 34 (body) | test script | 280 |
| 51 | Journey: a Brainstorm | Twelve steps from "Start an intent" to ratings and late thoughts | 03, 06, 09, 10, 17, 24, 35, 36, 37 (body) | test script | 234 |
| 52 | Journey: the Weekly check-in | One week of the Operations series, nine steps | 02, 06, 07, 08, 09, 13, 17, 20, 21 | 53, 19 | 207 |
| 53 | Journey: a Problem | Twelve steps from a check-in item to a closed Problem | 02, 03, 06, 07, 08, 09, 10, 13, 20 (body) | test script | 222 |
| 54 | Journey: a Decision | Eleven steps from a closed brainstorm to a recorded choice | 03, 06, 07, 09, 10, 20, 43 (body) | test script | 192 |
| 55 | Data knowledge map | After each signed charter, gap report, release or scan the company map learns where each field lives and who owns it | 05, 13, 14, 20, 27, 28, 30, 32, 33 | 12, 13, 19, 45, 48, Build room 0 | 257 |
| 56 | Data-backed opportunities | The Watcher notices a pattern in the records, Lens adds evidence, North judges whether it merits an Initiative; a dashed suggested Initiative that only a person picks up | 05, 19, 21, 22, 25, 55, Build Ops | 04, 21, 22 | 252 |

Notes on the map. File 14 owns the route register and page table; every file that adds a route must conform to it. File 02's YAML is the only list of types, questions and stage days. File 38 owns the week file shape (ruling 17). File 04 and file 19 share the four home counters (19 is the single source). Files 25 to 31 and 44 are all the Define work of an Initiative.

## 3. The five journeys

Each journey is the script in files 50 to 54. The feature file wins on screens; the journey file wins on order and timing. Routes follow ruling 1 and ruling 18. Agents draft and people act; where a step says "Out:" the owner file is in brackets.

### 3.1 Initiative (file 50; start questions 22)

Demo: "Cut the days it takes to produce the quarterly client report", 10 working days, build needed. Clock: Think unfiltered days 1 to 3, Define strategically days 4 to 9, Build-ready check day 10.

People: Janet (organiser, on a company admin account until an organiser seed exists), Daniel (sponsor, signs the charter), Katie (analyst and data owner), Aaron (participant), Harvey (source owner, business owner of the report process), Grace (governance approver). Agents: North (workflow and clock), Lens (definitions), Nira (Pulse lines).

1. `/centre/intent` then `/centre/intent/new`. Janet presses Start an intent and picks the Initiative tile. North writes the draft record, visible to Janet only. Out: draft `intents/<id>/intent.json` and an index row (01, 03).
2. `/centre/intent/new?type=initiative&step=goal` to `step=review`. Janet answers the six questions (goal, people, build, definitions, areas, decide-by) and presses "That is right, open this intent". North reads back each answer, drafts title and purpose, runs the glossary and catalogue look-up. Out: purpose, title, areas, people, `affected_may_read`, outcome start fields, `time_box`, wall reference (22).
3. `/centre/intent/<id>` then `/wall`. Janet presses "Open the wall" and copies the join link; invitees open their Pulse line. North drafts the invitations for Janet to send; Nira adds the lines. Out: `people.participants`, seats, Pulse lines (06, 13, 23).
4. `/centre/intent/<id>/wall` (private rooms). Aaron, Katie, Harvey, Grace, Daniel and Janet each answer four questions with North, choose "Put it on the wall", and may seal a card or make it anonymous. North drafts cards from the interview and at most three suggestions per lane, and fills an empty quarter only when the person presses the button. Out: cards in the profile `cards` section, lane counts (23, 24, 25).
5. `/centre/intent/<id>/wall`. Janet presses "Close the wall"; the wall also freezes by the clock at the window end. North freezes the snapshot, clusters and names; Lens proposes shelves. Out: frozen wall (charter page 1), clusters, Define opened (23, 26, 07).
6. `/centre/intent/<id>/define?tab=clusters`. The committee moves clusters to shelves (Must, Should, Good to have, Future), votes, confirms or sends back with a note. Lens drafts at most three questions per person; North keeps the clock; a cluster cannot go to Must or Should while ungoverned. Out: shelves, votes, move history, Future reason and review date (26).
7. `/centre/intent/<id>/define?tab=process-map` and `?tab=data-sources`. Katie and Harvey confirm processes and sources, edit cells, and say "Not mine, it is Aaron". Lens drafts both maps (marked guessed); North nudges Harvey within two working days. Out: process map (27), data sources map with source owner (28).
8. `/centre/intent/<id>/define?tab=glossary` and `?tab=catalogue`. Katie, Grace and the owners pick a meaning, confirm as data owner and settle ambiguities. Lens updates drafts and never overwrites a person. Out: business glossary (29), technical glossary and catalogue (30).
9. `/centre/intent/<id>/define` (governed panel). Grace, Harvey, Katie and Daniel confirm owners, classification, who may see and resolving team. Lens drafts with provenance; North nudges. Out: governed state per measure (31).
10. `/centre/intent/<id>/charter`. Janet reads the ten pages and the problem lines and presses "Use this"; Daniel presses "Sign the charter". North drafts the charter and checks completeness; Nira lists it for Daniel. Out: charter, problem statements (the "so that" lines), signature, read-only after signing (32).
11. `/centre/intent/<id>/charter?focus=roles`. Janet confirms six Build roles; each named person accepts or declines. Lens drafts the roles; North updates the build-ready line. Out: who does what (34).
12. `/centre/intent/<id>/build-ready`. Janet fixes failing lines and presses "Hand to Build" at 7 of 7. North recomputes on every write; Lens drafts missing definitions. Out: build-ready check (33).
13. `/centre/intent/<id>/close` then `/centre/build/gap-analysis?from=<id>`. Janet confirms the hand-off and closes; Daniel confirms. North writes the closure draft; ratings open. Out: hand-off to Build room 0 gap analysis (`links.build`, 33), closure (09), ratings (10), knowledge map update after the signed charter (55), memory lines (46), events (16).

Branches: build not needed (closure with charter and glossary, `next: nothing`); a participant never joins (nudge, charter lists "invited, did not contribute"); wall frozen with two cards (North offers extend, close with what we have, cancel); ungoverned cluster refused for Must (named people shown); sponsor sends the charter back; time box runs out; organiser cancels with a reason.

### 3.2 Brainstorm (file 51; start questions 35)

Demo: "Performance reviews take two weeks and nobody trusts the scores". Opens Wed 7 Oct; ideas open Thu 8; session Fri 9 at 10:00; ends Mon 12 Oct 17:00.

People: Janet (organiser), Aaron, Katie (one anonymous idea), Harvey, Grace, and two more invited seats (Mei Ling and Ravi, who need seed accounts); Daniel (sponsor and affected, not invited to think). Agents: North (groups, counts, drafts), Nira (lines).

1. `/centre/intent` then `/centre/intent/new`. Janet presses Start an intent and picks Brainstorm (or asks North). North writes the draft. Out: draft record with an `outcome` object (03).
2. `/centre/intent/new?type=brainstorm`. Janet answers five questions (idea, good outcome, four to eight people, areas, session time). North checks related past work, suggests people and areas, derives the three-day window, drafts title, purpose and invitation. Out: `start_answers`, outcome fields, areas, participants (35).
3. `/centre/intent/<id>`. Janet presses "Looks right" then "Open this brainstorm". North validates, opens the first stage, posts the first line; Nira places Pulse lines. Out: `state: open`, `time_box`, stages, invitations (35, 07, 16).
4. `/centre/intent/<id>`. Janet copies the invitation message; six people accept; Daniel gets an information line. North updates the count. Out: participant statuses (06, 35).
5. `/centre/intent/<id>` at 390. Invited people add ideas privately and may "Hide my name". North stamps `ideas_open_at`, sends one reminder, shows counts only to Janet. Out: idea cards, anonymous keys (35, 24).
6. `/centre/intent/<id>/session`. Janet presses "Open the session"; everyone adds ideas and builds on others'. North groups from the third card. Out: `state: in_session`, phase diverge, replies (36).
7. `/centre/intent/<id>/session`. Janet moves to group; everyone moves and renames; "Group again". North regroups and keeps move history. Out: phase group, moves (36).
8. `/centre/intent/<id>` (stage `choose`). Seven seats back up to three ideas; Janet closes the count. North counts, nudges privately and drafts the outcome; nobody sees who backed what. Out: converge counts (37).
9. `/centre/intent/<id>?view=outcome`. Janet edits "what it would take" and presses "Confirm this outcome". North drops unsourced sentences. Out: `outcome.chosen`, runners-up, `state: closing` (37).
10. `/centre/intent/<id>/close`. Janet edits, picks what next (Initiative, backlog or nothing, with a reason) and presses "Close intent". North writes the child draft at `/centre/intent/new?type=initiative&from=<id>`. Out: closure, `links.to`, late-thought window (09, 37, 20).
11. `/centre/intent/<id>/close` (rating panel). Participants give 1 to 5 and a note, anonymous by default. North aggregates counts only. Out: ratings, `rating.rated` (10).
12. `/centre/intent/<id>`. Late people add a thought until Monday 17:00; North freezes at the window end. Out: late thoughts, `frozen_at` (37).

Branches: only three turn up; ideas tied (tie pick, round 2); backlog; same topic last quarter; anonymous idea; session overruns; nobody backs; organiser picks a less-backed idea with a reason; late thought after freeze refused.

### 3.3 Weekly check-in (file 52; setup 38, entry 39, review 40)

Demo: one week of the Operations series, Mon 12 to Thu 15 Oct 2026. On screen "Weekly check-in"; "Pulse" alone means the daily page.

People: Katie (organiser and reviewer), Aaron, Harvey, Mei Ling and Rahul (reporters; the last two need seed accounts), Janet (company admin: counts only, no anonymous notes). Agents: North (opens weeks by the clock, drafts), Nira (lines); Lens takes no part.

1. `/centre/intent/new?type=pulse`, Fri 9 Oct. Katie answers four questions (area, who reports, close day and reviewer, optional own question) and presses "Start the check-in". North reads back, drafts the three fixed prompts, checks the minimum of two reporters. Out: series record, close day, recurring flag (38, 02).
2. Pulse line then `/centre/intent/<id>/week`, Mon 12 Oct. Each reporter presses "Start my check-in". North opens the week and Nira places the line. Out: week file `weeks/<week_key>.json`, stage `collect` (38).
3. `/centre/intent/<id>/week`. Each reporter keeps, edits or drops North's prefill from the run log and presses "Send my week". North turns answers into items of kind `ran`, `broke` and `thought`, and invents no figure. Out: items, transcript lines (39, 16).
4. Close day, Wed 14 Oct. North closes `collect`, locks edits, opens review and builds the digest. Out: collect closed, review opened, digest (38, 40).
5. `/centre/intent/<id>/review?week=<week_key>`, Thu 15 Oct. Katie reads the digest and opens items. North groups repeats and drafts a suggested fate for each `broke` item (40).
6. Same view. Katie gives each item a fate (problem, backlog, handled, nothing) with a required reason; North refuses to close the week while any `broke` item lacks one. Out: fates, Problem draft, backlog items (40, 41, 21).
7. `/centre/intent/<id>/review` (close section). Katie presses "Close this week". North drafts the week summary and next rows. Out: week closed, `links.to` the Problem (40, 09).
8. `/` and `/centre/intent/<id>/week?week=<week_key>`, Fri 16 Oct. Reporters read their own items and fates; Nira writes one line each. Out: seen marks (40).
9. By the clock, on the next working day after the close day (Thu 15 Oct). North opens week two even if the review is unfinished and shows late drafts to keep or drop. Out: new week file (38, ruling 3).

Branches: a reporter misses a week (count only; after three misses an offer to ask or remove); an item repeats three weeks running ("Add to that Problem"); reviewer away (nudges, then the closer is offered extend, close with what we have or cancel; only ending the series closes it with what we have, ruling 23); series paused; an item names a restricted measure (flag, no figure).

### 3.4 Problem (file 53; start 41, resolution 42)

Demo: a custodian cash match problem raised from a check-in item; 5 working days.

People: Aaron (reporter, starts it), Harvey (proposed source owner, passes), Katie (analyst and data owner, accepts and owns the fix), Grace and Daniel (affected, "Fixed for me"), Janet (read-only, on a company admin account). North runs and never signs.

1. `/centre/intent/new?type=problem&from=<pulse id>&item=<item id>`. Aaron confirms five prefilled questions and presses "Start this Problem". North drafts from the item and checks the required questions. Out: Problem record (41, 02).
2. `/centre/intent/<id>` (stage `describe`, triage panel). Aaron reads the triage draft and Ops alerts and presses "Looks right". North drafts the statement once. Out: `outcome.what` (41).
3. `/centre/intent/<id>` banner. Harvey presses "Pass, and say why". North drafts "Propose Katie?". Out: owner proposals (41, 42).
4. Same screen. Aaron proposes Katie; Katie presses "Accept ownership". North moves the stage to `find_cause`. Out: `people.owner` (41, 06, 07).
5. `/centre/intent/<id>` thread. Katie, Aaron, Grace and Daniel add evidence. North redrafts "What we know". Out: notes, working summary (42).
6. Same screen, panel "Root cause". Katie presses "Confirm root cause". North drafts from the posts and the run log. Out: root cause (42).
7. Panel "Fix". Katie sets dates and presses "Confirm the fix plan". North drafts and checks the date is inside the box. Out: fix with a named doer (42).
8. Katie presses "Mark fix done"; Grace and Daniel press "Fixed for me". North moves to `confirm` when all have answered. Out: fix done, affected confirms (42).
9. `/centre/intent/<id>/close`. Katie (the owner) presses "Close this Problem", disabled until Aaron has confirmed. North drafts the closure. Out: closure, `state: closed` (09).
10. Stage `confirm`. Aaron presses "Yes, it is gone" or "No, send it back" (once only). Out: reporter confirmation (42).
11. Governed state node History. Katie confirms the version note; North drafts it. Out: new node version (42, 31).
12. `/centre/intent/<id>/close` (rating panel). People score 1 to 5, anonymous by default; aggregates from three. Out: ratings (10).

Branches: two passes go to the company admin with the clock paused; the owner turns it into an Initiative ("bigger than a fix"); the reporter reopens once; the owner extends with a reason; a restricted measure is hidden from the reporter.

### 3.5 Decision (file 54; screens 43)

Demo: move the monthly fund return report to one agreed set of measures; 2 working days; started from a closed brainstorm.

People: Janet (organiser, on a company admin account), Daniel (decider and sponsor), Katie, Harvey and Grace (advisers), Aaron (affected: outcome and reason only), the super admin (existence only). North runs; Lens only if a measure lacks a definition.

1. `/centre/intent/new?type=decision&from=<brainstorm id>`. Janet reviews and presses "Open this decision". North prefills the questions from the brainstorm and drafts title and purpose. Out: Decision record, `links.from`, two-day box (43, 02).
2. Pulse line then `/centre/intent/<id>`. Advisers accept or decline. Nira places lines; North nudges by the end of day 0. Out: invitation records (06).
3. `/centre/intent/<id>` panel "Notes". Advisers add a note, signed or anonymous. North counts notes and nudges on day 1 if fewer than two. Out: notes (43).
4. Panel "Options". Janet edits, merges, removes or adds her own. North drafts two to four option cards from notes and records and never invents a cost. Out: options (43).
5. Panel "Options". Harvey adds an option, optionally without his name. North tags it "Added by an adviser" and ranks nothing. Out: anonymous option (43).
6. Panel "North's suggestion". Everyone reads the recommendation and its source tags. North drafts after day 1 or on request, and says what is missing if there are under two sources. Out: recommendation, labelled "Agent's draft. Not a decision." (43).
7. Panel "Decide". Daniel chooses an option, writes the reason and presses "Record my decision". North checks the reason and never fills it. Out: decision, `state: closing` (43).
8. Panel "Record". Daniel presses "Confirm the record". North drafts the page. Out: decision record (43).
9. Panel "Record". Katie presses "Add this note to the measure". North drafts the note. Out: version note on the catalogue entry (43, 30).
10. Automatic. North writes the link both ways after the record is confirmed. Out: `links.to` on the brainstorm (20).
11. `/centre/intent/<id>/close`. Janet presses "Close this decision" (file 54; files 02 and 14 name the decider as closer, see C-1 in section 7); advisers rate. North drafts the closure; Aaron is told. Out: closure, ratings, Pulse line (09, 10, 13).

Branches: "Decide later" extends once; "No decision" with a reason; an adviser without measure access; time box runs out; company admin cancels with a reason.

## 4. The department view

How areas, swim lanes, visibility, sharing and the backlog work across intents (files 05, 04, 11, 21, 47, 48).

**Areas (05).** An area is a department or operations area, kept as a tag. Tags sit on intents (`areas`, at least one to open) and on people (`people.<pid>.areas` in the company profile, set by the company admin on "People and areas"). The pack proposes areas for a family office as labelled suggestions; Lens proposes tags from each person's team value; the admin accepts. An area is renamed or retired, never deleted, so past intents keep matching. A person with no area sees only intents they are named in, and a banner says so.

**Swim lanes (04).** The home page is one lane per area the viewer belongs to, then a "Company-wide" lane (the reserved area token `company-wide`). Each lane shows up to four intent cards at 1280 (five rows at 390) with "Show all (n)". A card shows title, type chip, stage, days left, organiser, people count and the viewer's own role tag. An intent that touches two of the viewer's areas appears in both lanes, the second marked "Also in <area>"; counters count it once. The "Your turn" strip above the lanes is Nira's list for this viewer (45). Filters (type, state, area, Mine or All) live in the URL; search (15) answers from the same per-viewer cut.

**Visibility (05, with 01 tiers and 47).** Three tiers decided on the server by one function in `sh_platform/profile/view.py`: `content`, `card`, `exists`. People tagged to the intent's areas learn it exists, with title, purpose, stage and organiser, and the outcome once closed. Affected people (by area or named) also see people and clock (ruling 4), and open content only when the organiser switched on "affected people may read" at creation (default off) or a share names them. Observers read what a participant reads and never write or vote. Participants see everything except sealed and anonymous material (D-013). A draft is seen by its starter alone. The company admin sees existence and outcome, never anonymous notes. The super admin sees existence only (title, type, state, areas, people count, dates, time box status), read through the kernel on request, with a company switch that removes titles. A viewer outside every tier gets the same 404 as a made-up id.

**Sharing (11).** Only the organiser shares, per intent, never a draft. A share row names a person, an area or a link maker; every row has an expiry and can be withdrawn at once. The visitor reads through their own `Viewer`, so a share never makes anyone a participant. Sealed cards show as a count, anonymous authors are never sent, and a visitor may leave a note but cannot change anything. The organiser sees who opened it.

**Backlog (21).** `/centre/intent/backlog` holds what is not yet an intent: items that arrive from a Brainstorm's "what next", a check-in fate of backlog, or a closure next row. Each item carries source, raiser, why it matters and a review date (default one quarter). An area lead opens an item as an intent (never a check-in), merges duplicates, parks with a reason or drops with a reason; nothing is deleted. People in the area see the list.

**Across intents.** Links (20) join intents in a chain (Brainstorm to Decision to Initiative to Build); Past (12) at `/centre/intent/past` keeps closed and cancelled intents by area and month; the admin page (48) and the measures (19) read the same records. Every list and count is cut per viewer on the server; a hidden intent never appears in a total.

## 5. The outputs timeline

Every output an intent can produce. "Agent" is who drafts; "Person" is who confirms, signs or acts (agents never sign). "Stored" names the file or route; the owner file is in brackets. Rows are grouped: every type first, then each type in its journey order.

| Output | When it appears | Agent drafts | Person confirms or signs | Stored |
|---|---|---|---|---|
| **Every type** | | | | |
| Intent record (draft) | First tile pick | North: title, purpose, areas | Organiser, by pressing Open | `intents/<id>/intent.json` (01) |
| Start answers | During the start questions | North asks and reads back | Organiser | `start_answers` (02, 03) |
| Index row and search row | Every write | none | none | `intents/index.json` (01), search fields (15) |
| Time box and stage list | On Open | North proposes from the catalogue | Organiser opens or shortens a stage | `time_box`, `stages` (01, 02, 07) |
| People, invitations, statuses | On Open, then through the stage | North, Nira lines | Each person accepts, declines or confirms; organiser invites | `people`, `people_detail` (06) |
| North drafts, nudges, proposals | Each stage and each clock check | North | The named person: confirm, edit, discard or pick | `north` block, `intents/<id>/north.json` (08) |
| Pulse lines and message drafts | When a record makes a line true | Nira (lines), North (messages) | The person acts; organiser sends any message | Computed on read; `pulse/messages.json` (13) |
| Events | Every act and every draft | North, Lens (logged as drafts) | none | `intents/<id>/events.jsonl` (16) |
| Extension | Any time before closed | North drafts the reason | Organiser, with approval by the closer or company admin after the first (proposal) | `time_box.extended_by` (07) |
| Closure draft and summary sentences | At `closing` | North | The closer edits and confirms | `closure` (09) |
| Next rows, child intents, backlog items | At close | North proposes kind and reason | The closer picks each, with a reason | `closure.next`, `links.to`, `intents/backlog.json` (09, 20, 21) |
| Signature on closure | At `closing` (Initiative, Decision, Problem; proposal) | none | Sponsor, decider or owner | `closure.signature` (09) |
| Ratings | After `closed`, not for series or weeks | none | Each participant, anonymous by default | `ratings`, `rating`, a person's own receipt (10) |
| Outcome used | One month after closure | North asks, drafts one next move | Organiser answers | `outcome_used` (10) |
| Share | Any time except draft | North suggests at closure | Organiser | `share` (11) |
| Past entry, one-liner, history notes | After close or cancel | North: one-line outcome | Organiser confirms; later notes by organiser | `closure`, `history_notes`, `closed_month` (12) |
| Memory lines | After close | North (people), Lens (company facts, Initiative only) | Closer confirmed the closure; each person may edit or delete | `context/memory/<agent>/...` (46) |
| Transcript file | On request, closed or cancelled | none | The person who downloads | Built on request (16) |
| **Initiative** | | | | |
| Wall cards | While rooms are open | North drafts from the interview; Lens fills no quarter unprompted | Author puts it on the wall; may seal or make anonymous | Profile `cards` section (23, 24) |
| Suggestion cards | At wall open and when a document lands | North (at most three per lane) | The person picks one up or hides it | `wall_suggestions/<session>.json` (25) |
| Frozen wall snapshot | Close the wall or window end | none | Organiser | `wall_snapshot.py`, charter page 1 (23) |
| Clusters and shelves | Define session | North clusters; Lens proposes a shelf | Committee votes; organiser breaks ties | `together_shelves` (26) |
| Process map | Define, before and during the session | Lens (marked guessed) | The named business owner | `intents/<id>/processes.json` (27) |
| Data sources map | Define | Lens | The source owner; governance lead sets class and who may see | Catalogue sources tab, `data_sources.json` (28) |
| Business glossary | When the wall closes, redrafted on new input | Lens | Each term owner; governance lead settles ambiguities | `intents/m2_baseline/<id>/glossary.json`, `glossary/company-terms.json` (29) |
| Technical glossary and catalogue | After sources have rows | Lens | The named data owner | Baseline `technical`, `catalogue_measures` (30) |
| Governed state | First Define look, then per measure | Lens | Named owners, governance lead, sponsor, by field | `governed_state.json` (31) |
| Lens drafts (nine kinds) | Define opens, unattended | Lens | Owner of each cell; Grace decides escalations | `define.lens.*` and m2 stores (44) |
| Charter and problem statements | Define closes | North | Organiser edits; sponsor signs once | `CharterStore`, `intents/m1_intent/outcomes/<id>.json` (32) |
| Who does what | At the charter | Lens drafts six roles | Organiser confirms; each named person accepts or declines | `intents/m1_intent/roles/<session>.json` (34) |
| Build-ready check | From the first charter draft, recomputed on every write | North | Organiser or sponsor answers "Is a build needed?" | `build_ready`, `build_needed*` (33) |
| Hand-off to Build room 0 (gap analysis) | Check at 7 of 7 | none | Organiser presses "Hand to Build" | `links.build`, `build_handoff` (33) |
| Knowledge map update | After each signed charter | Nira writes the line; the map is rebuilt from records | none | `graph/company.json`, `graph/updates.json` (55) |
| **Brainstorm** | | | | |
| Related-work list and invitation | Start questions and Open | North | Organiser | `outcome.related`, invitation text (35) |
| Idea cards and replies | Think alone, live session | none | Each participant | Profile `cards` (24, 36) |
| Groups and moves | Live session | North groups | Participants and organiser move and rename | `store/board.py`, keyed by intent (36) |
| Backs and counts | Stage `choose` | North counts only | Each seat backs up to three; organiser closes the count | `outcome.ideas_kept[].backed` (37) |
| Outcome card (chosen idea, why, runners-up) | After the count | North | Organiser | `outcome.chosen` (37) |
| Late thoughts | After closing until the window ends | none | Each participant | `late_thoughts[]` (37) |
| **Weekly check-in** | | | | |
| Series record | Start the check-in | North | Organiser | `intents/<id>/intent.json`, `series` (38) |
| Week file | Opened by the clock | North | Reviewer closes it | `intents/<id>/weeks/<week_key>.json` (38) |
| Items (`ran`, `broke`, `thought`) | Collect stage | North prefills, marked guessed | The reporter sends | Week file `items[]` (39) |
| Digest | When answers close | North | Reviewer reads | Week file `digest` (40) |
| Fates and reasons | Review and sort | North suggests a reason | Reviewer, per item | Week file item fields (40) |
| Problem or backlog item from an item | On a fate | North prefills | Reviewer presses | A Problem intent (41) or `intents/backlog.json` (21) |
| Week summary | Close day | North | Reviewer | Week file, `outcome.weeks[]` (40) |
| **Problem** | | | | |
| Statement (`what`, `saw`, `bites`) | Open | North asks, drafts | Reporter | `outcome` (41) |
| Triage note and proposed owner | On open | North | Proposed owner accepts, passes or is assigned | `triage_note`, `people.owner` (41) |
| What we know | After each note | North | Owner may pin sentences | `what_we_know` (42) |
| Root cause | Stage `find_cause` | North drafts | Owner confirms | `outcome.root_cause` (42) |
| Fix with a named doer | Stage `fix` | North checks the date | Owner saves | `outcome.fix` (42) |
| Affected confirms; reporter confirms | Stage `confirm` | none | Each affected person; the reporter | `outcome.affected_confirms[]`, `confirmed_by` (42) |
| Fix note on the map node | On close | none | Owner (reporter's confirm triggers it) | `graph/versions.json` (42, 31) |
| **Decision** | | | | |
| Options and notes | After Open | North drafts options, marked guessed | Advisers and organiser add; each adder confirms | `outcome.options[]` (43) |
| Recommendation | After day 1 or on request | North, labelled "Agent's draft. Not a decision." | none | `outcome.recommendation` (43) |
| Decision and reason | Stage `decide` | North may offer a draft Why only | The decider | `outcome.chosen`, `why`, `decided_by` (43) |
| No decision or decide later | Stage `decide` | none | The decider | `outcome.no_decision_reason`, `deferral` (43) |
| Version notes on measures | On the decision | North drafts the note | The decider | `graph/versions.json` (43, 30) |
| **Admin and measures** | | | | |
| Centre measures (M01 to M15) | On read | none | none | Route only (19) |
| Admin cancel, register CSV, company defaults | On press | none | Company admin | `closure`, browser download, `settings/intent_types.json` (48) |

## 6. The open-question register

Method. All 55 feature files carry an "Open questions" section, and the journey files 50 to 54 carry them as bullets or lists. They hold 626 questions in total (files 01 to 49: 575; files 50 to 55: 51). They were collected, grouped by theme and deduplicated across files into the rows below. A question that a ruling already decides stays in the register, marked "Ruled", so the owning files can be corrected. Display-only constants (widths, pauses, row counts) are grouped into one row each.

How to read a row. "Raised by" lists file and question number. "Proposed answer" follows the brief's rulings 1 to 24 wherever they decide the matter; where they do not, it is the answer most files already lean towards. "Who" is **Nitin** where the answer is a product choice that changes what a person sees or may do, and **builder** where a builder can settle it from the proposal (rulings, existing code, a display constant). Rows marked Nitin feed section 8.

### 6.1 Routes

| ID | Question | Raised by | Proposed answer | Who |
|---|---|---|---|---|
| RT-1 | Query keys used by the files but not listed in ruling 18: `step`, `item`, `alert`, `node`, `edit`, `cluster`, `cell`, `role`, `owner`, `sort`, `area`, `type`, `state`, `q`, `kind`, `status`, `due`, `open`, `suggestion`, `show`, `section`, `mode` | 03 Q1; 18 Q11; 20 Q11; 22; 24 Q9; 34 Q11; 40 Q8; 41 Q1; 42 Q10; 44; 49 Q7; 50 Q3 | Add a ruling 25 that lists the allowed keys (the first nineteen above) on the twelve views and on `/centre/intent/new`. Replace `mode=session` with `view=session` and `show=mine` with `view=mine`. A hash such as `#rate` or `#your-turn` is an anchor, not a route, and is allowed | builder |
| RT-2 | Existing v1 pages outside ruling 1 (`/centre/intent/bring`, `/centre/intent/outcomes`, `/centre/intent/graph`, `/centre/intent/map/<node id>`, `/outcomes`, `/graph`, `/ops`, `/pulse`, `/centre/memory`, `/register/terms/{id}`, the M2 baseline pages): keep, move or drop | 04 Q9; 10 Q5; 12 Q8; 14 Q8; 18 Q7; 20 Q12; 29 Q4; 30 Q10; 31 Q10; 46 Q10; 50 Q3; 55 Q1 | Keep every existing route as built, list each once in file 14's page table marked "existing", and redirect later. New pages only follow ruling 1 | builder |
| RT-3 | Company pages and APIs for areas and people pickers (`/company/settings/areas`, `/company/settings/areas/people`, `GET /api/company/areas`, `/api/profile/areas...`, `GET /api/intents/areas`, `GET /api/intents/people`) | 05 Q1; 11 Q9; 21 Q1 | Keep the three company settings pages and `/api/profile/areas...` (they are company settings, not intent pages). The organiser's pickers read `GET /api/company/areas` and `GET /api/intents/people`, both cut by `view.py` | builder |
| RT-4 | Share visitor pages, token carriage, guest note and events routes, short link host | 05 Q3; 11 Q11; 14 Q8, Q9; 16 Q10; 17 Q1, Q2 | One page, `/centre/intent/<id>/share`. A link token rides in the URL fragment and is sent only in `X-Session-Token`. Guest APIs stay under `/api/modules/m1_intent/shared/*` (ruling 24), including `note` and `events`. No short-link host this round: show the full link and a QR code from a library | builder |
| RT-5 | Route names and verbs differ between files (PUT or PATCH, `close` or `closure/confirm`, `north/ask` or `north/turns`, `nudge`, people PUT or POST, `pulse/*` or `weeks/*`, three spellings of `notes`); literal segments beside `{intent_id}` | 14 Q7; 18; 45; 48 | File 14 is the route register. Each owner conforms in the build. Literal segments (`types`, `home`, `admin`, `waiting`, `measures`, `backlog`, `suggestions`, `hints`, `past`, `mine`, `control`, `people`, `areas`, `settings`, `classify`) are registered before `/{intent_id}`. Add `suggestions`, `hints` and `classify` to 14's reserved list | builder |
| RT-6 | Super admin API spelling | 01 Q14; 05 Q1; 14 Q3; 48 Q2 | Use 14's `GET /api/control/companies/{company_id}/intents` and `GET /api/control/intents/summary`. `GET /api/intents` refuses the super admin. Ruling 5 names the existence keys; `id` is added as an opaque value | builder |
| RT-7 | A kernel router cannot import a module: how `/api/intents/...` reaches M1, M2 and M3 stores | 25 Q8; 28 Q8; 30 Q10; 32 Q8; 33 Q14; 55 Q2 | The intent router lives in the kernel (`sh_platform/intents/`). Module data stays at `/api/modules/<module>/...`; the router calls module stores through the module registry. Thin wrappers only where the intent record is read or written | builder |
| RT-8 | Retire the v1 wall, define and charter routes | 23 Q1; 26 Q9; 28 Q9; 32 | Keep them working for sessions with no intent record. Redirect to `/centre/intent/<id>/...` when a record refers to the session | builder |
| RT-9 | Views the files still name that ruling 18 refuses (`rate`, `used`, `invitation`, `roles`, `triage`, `decide`, `notes`, `options`, `record`) | 06 Q12; 10 Q6; 13 Q1; 33 Q12; 34 Q11; 35 Q11; 45 Q5; 54 Q5 | Ruled: ruling 18. They are panels on the stage view, or `?focus=`, `?view=` and `?draft=` keys on the twelve views | builder |
| RT-10 | The projector view for Define, Brainstorm and check-in review; who may open it | 17 Q4; 26 Q10 | The `projector` view serves all three; organiser only (company admin for a stuck intent is dropped, see C-25) | builder |
| RT-11 | A backlog item reaching the chooser (`from=<backlog id>`) | 21 Q12; 35 Q10 | `from` takes an intent id only. "Open it" calls `POST /api/intents/backlog/{id}/open`, which creates the draft first and continues at `/centre/intent/new?type=<type>&draft=<id>` | builder |

### 6.2 Record shape

| ID | Question | Raised by | Proposed answer | Who |
|---|---|---|---|---|
| RS-1 | Flat or nested `outcome`; the series `outcome`; `outcome.chosen`, `question`, `what` and the rest | 02 Q3, Q4; 22 Q13; 37 Q6; 38 Q8; 41 Q2; 53 Q9 | Ruled: rulings 6, 16 and 17. Flat per type, an object from open, 02 owns it. The sweep of files still nesting is C-18 | builder |
| RS-2 | Shape of `outcome.weeks[]` on the series | 02 Q4; 38 Q8; 39 Q3; 40 Q11 | One row per closed week: `{week_key, closed_at, items_count, broke_count, fates}` (file 40). Week key is the date of the Monday the answers cover | builder |
| RS-3 | `start_answers`: list or map, marks `stated`, `guessed`, `unknown`, `prefilled_from` | 02 Q5; 03 Q6; 20; 22 Q7 | A list on the record after open: `{id, answer, mark: stated|guessed|unknown, prefilled_from|null}`. A kept North draft stays `guessed` until the person edits or says "That is right" | builder |
| RS-4 | `people` entries: person object or id; `people_detail`; advisers; which types take a sponsor | 05 Q11, Q12; 06 Q4, Q13; 13 Q2; 34 Q12; 45 Q2; 48 Q13 | `people.*` entries are `{account_id, name}` (01). `people_detail` joins 01 as a list keyed by person. Advisers are a list (ruling 21). The sponsor slot is offered on Initiative only. Decider, owner and reporter read content as participants | builder |
| RS-5 | Name and place of the "affected people may read" switch | 15 Q6; 22 Q11; 35; 43; 47 | A boolean `affected_may_read` directly on the record (01). Changes are events (16); there is no second structure | builder |
| RS-6 | Where ratings are tied to people | 05 Q6; 10 Q7 | Ruled in behaviour: ruling 15. Use file 10: `rating.rated` (presence only) and a person's own receipt `people/<account_id>/ratings.json`. Drop file 05's `rated_by` (C-7) | builder |
| RS-7 | Wall reference key | 19; 22; 23 Q5 | `refs.wall_session_ids` (01, 23). `stages[0].ref` and `refs.wall_session_id` are dropped | builder |
| RS-8 | References and counts for Define artefacts (`refs.processes_file`, `outcome.processes`, `data_sources`, `outcome.glossary`, `catalogue`, `refs.baseline_ids`); location of the roles file | 27; 28; 29; 30; 31 Q13; 34 Q13 | References in `refs` (ids and file names only). Counts are derived on read. No nested blocks under `outcome` (C-18). Move the roles file to `intents/<id>/roles.json` to follow ruling 12 | builder |
| RS-9 | Source owner and business owner: separate cells or the Data owner cell | 28 Q1; 30 Q1, Q11; 31 Q11 | Ruling 11 fixes the three kinds. Keep 28's extras file as the source until the M2 contract change is accepted; 30 reads it (C-15) | builder |
| RS-10 | Measure codes and a second Initiative on the same measure | 30 Q2, Q3 | One company-wide counter `M-<n>`. A later Initiative refers to the existing entry and proposes a version | builder |
| RS-11 | Problem short reference and Problem fields (`owner_proposals`, `fix_for_me`, `reopened`, `restricted_refs`, `links.alert`, `links.node`) | 42 Q1, Q11; 53 Q4 to Q7 | Reference `P-<n>`, a company counter held beside the index. Adopt the four fields as flat keys registered by 41 and 42. `links.alert` and `links.node` are lists | builder |
| RS-12 | Decision deferred to an Initiative; partial version note; fourth outcome | 43 Q5, Q6 | A deferral is "no decision" with a reason plus `links.to` a new Initiative (ruling 7). A version note writes only to nodes the decider may see | builder |
| RS-13 | Backlog item shape, owner and the area lead | 02 Q8; 20 Q3; 21 Q1 | File 21 owns `intents/backlog.json`. Add a `lead` cell to `areas.<id>` in file 05 | builder |
| RS-14 | Votes and backing: who writes `votes[]` | 13 Q3; 45 Q9 | `votes` is derived on read from the owning store (together store for Define, converge counts for Brainstorm); the record keeps no second copy (C-10) | builder |
| RS-15 | Currency and units for amounts and counts | 39 Q8, Q9; 41 Q11 | Amount is `{value, currency}`, currency defaulting from the company profile. Count unit is hours or times | builder |
| RS-16 | Id scheme and field limits | 01 Q12; 22 Q12 | Id `<prefix>-<32 hex>` (01). Title 120, purpose 140 characters | builder |
| RS-17 | Memory counts block and the `topic` field | 46 Q3, Q11 | Add `memory {written_at, by_agent, filtered, state}` (counts only) and an optional `topic` on the memory shape in SHAPES section 9 | builder |
| RS-18 | Process record mirror; good outcome required on Brainstorm | 01 Q5; 35 Q1 | No mirror; the intent index replaces it. A good outcome is required (file 02 marks it required) | builder |

### 6.3 Visibility

| ID | Question | Raised by | Proposed answer | Who |
|---|---|---|---|---|
| VS-1 | Who may start each type of intent | 01 Q2; 03 Q7; 04 Q1; 05 Q9; 14 Q2; 18 Q1 | Brief section 1 says anyone. Any signed-in company person starts Brainstorm, Problem, Decision and Weekly check-in; an Initiative needs the organiser capability (company admin, sponsor, analyst, as 14 has it). A person may start a draft for someone else; the starter stays organiser | Nitin |
| VS-2 | May participant, owner and approver roles open the centre | 05 Q2; 14 Q1 | Yes, all six company roles (file 14's table); the QUALITY-PASS line that says otherwise is superseded | Nitin |
| VS-3 | Is at least one area required to open; a person with no area | 05 Q13; 18 Q1 | Yes, one area is needed to open. A person with no area can save a draft; North asks the company admin to tag them | builder |
| VS-4 | What the company admin reads: closure summary, North thread, events, Define cells, outcome when assigning an owner, who has not acted | 05 Q4; 08 Q7; 15 Q3; 16 Q1, Q12; 31 Q9; 41 Q8; 45 Q8 | Existence, outcome, `what_came_out` and `next`, milestone events and counts. Not the thread, drafts, anonymous notes or Define cell content unless the admin is named. Sweep C-25 | Nitin |
| VS-5 | Area-tagged people who are not affected: do they see people names and the clock | 01; 05 Q5; 09 Q7; 15 | Organiser and a people count; clock yes; names only for affected people (ruling 4). Closure `summary` and `why_it_happened` only in the content tier (C-9) | Nitin |
| VS-6 | May the organiser change "affected people may read" after creation; affected tap on a Problem without it | 05 Q14; 14 Q10; 47 Q6, Q11 | Yes, on or off until `closing`, each change an event; an "I feel this" tap adds no content read and needs no switch | Nitin |
| VS-7 | Sharing audience: people outside the company, a link for any signed-in person, sponsor sharing, anonymous visitor notes | 05 Q8; 11 Q1, Q3, Q5, Q13; 14 Q9 | Company accounts only (A-051 puts cross-company later). A link works only for the signed-in people or areas it names. Organiser only shares. Visitor notes are named | Nitin |
| VS-8 | Anonymity in small rooms: anonymous cards, unsigned taps, per-area splits, visitor ratings, "opened by X of N" | 11 Q4, Q7, Q14; 16 Q3, Q4; 47 Q2, Q3, Q4; 36 Q7 | One rule: anonymous means no author id in any intent file. Fewer than five participants: anonymous cards reach a link visitor as a count only. Per-area splits of unsigned taps hide below five. Visitors see no ratings. Share counts are exact (ruling 8) | Nitin |
| VS-9 | Editing your own anonymous item without a name-to-item link | 39 Q1; 40 Q9; 24 Q1 | The person's own reference file lives under `people/<id>/` and the intent never reads it; the author cannot un-hide a name after posting anonymously | builder |
| VS-10 | Who is asked to rate; organiser rating own intent; cancelled intents; notes below three | 10 Q3, Q8; 51 Q5, Q7, Q8 | Asked: organiser, sponsor, participants, decider, owner, reporter, advisers, and affected only if they opened or contributed. Not observers, drafts, cancelled intents, series or weeks. The organiser may rate. Signed notes are shown; anonymous notes never | builder |
| VS-11 | A person who moves area; sensitive options on a Decision in Past | 05 Q10; 12 Q5 | Visibility follows the tag at once. No sealed flag on options this round | builder |
| VS-12 | Observers in practice: viewer resolution, stage buttons, observer to participant | 06 Q6; 08 Q4; 23 Q3, Q8; 47 Q9 | Ruled: ruling 4. Observers never write or vote; buttons hidden. Observer to participant is allowed with a reason. Nudge status shows names to the organiser and counts to others | builder |
| VS-13 | Backlog and search visibility | 15 Q3, Q4; 21 Q4 to Q7, Q10 | As file 21 proposes: people in the area see items; a raiser cannot tap their own; dropped items stay visible with the reason. The organiser's search never reads her anonymous cards | builder |
| VS-14 | Define reading rules: sponsor vote, lowering a data class, sealed measures in the strip, withdrawn words, edit counts, sealing a brainstorm idea | 24 Q2, Q3, Q6; 26 Q7; 30 Q4; 31 Q7 | The sponsor does not vote; only the governance lead lowers a class; the strip shows the percentage the viewer can see; withdrawn words are for the author only; no public edit count; brainstorm ideas are not sealable | builder |
| VS-15 | What North and Lens may read: earlier closed Decisions, interview answers; an adviser without measure access | 43 Q4; 44 Q4; 54 | Closed Decisions the viewer may see; only interview answers marked shareable (add the flag); an adviser without access sees a chip and the organiser may request access | builder |
| VS-16 | Mute lines; a pass to someone in another area | 41 Q13; 47 Q7 | No mute this round. A pass may name anyone; they become affected by name | builder |

### 6.4 Time and clocks

| ID | Question | Raised by | Proposed answer | Who |
|---|---|---|---|---|
| TC-1 | Clock cut-offs, nudge moments, "hours left" switch | 07 Q1; 08 Q2; 13 Q5; 01 Q3; 09 Q9; 28 Q4; 34 Q7; 06 Q2 | Neutral above 50 percent left, amber at 50 or less, red at 20 or less (file 13 gives 20 as Nitin's figure); "hours left" under two working days. North's two nudge moments are the same two | Nitin |
| TC-2 | Extension: who, how many, how long, approval | 01 Q4; 07 Q2, Q3; 09 Q3; 41 Q5; 43 Q2, Q3; 48 Q5 | The organiser may extend once alone; later ones need the closer, or the company admin where no sponsor exists. No cap. Day choices 1, 2, 3, 5; reason 10 to 300 characters; every extension is kept | Nitin |
| TC-3 | If nobody picks extend, close or cancel | 07 Q7; 08 Q3 | The closer is asked after one working day, the company admin after three | Nitin |
| TC-4 | Stage splits and what scales when the date is not default | 02 Q1; 07 Q9; 22 Q4, Q7; 28 Q3 | File 02's splits (Initiative 3, 6, 1; Brainstorm 1, 1, 1; check-in 3, 1, 1; Problem 1, 2, 1, 1; Decision 1, 1); the wall window default of 5 days becomes 3; other lengths scale pro rata, whole days, minimum one | Nitin |
| TC-5 | Working days and holidays; time zone field | 01 Q9, Q13; 04 Q3; 07 Q4; 15 Q2; 24 Q12; 35 Q9 | Ruled: ruling 22. Monday to Friday until the profile has a calendar; `profile.company.time_zone`, else UTC. Holidays later | builder |
| TC-6 | Percent base after an extension | 07 Q8 | The current box including extensions, so colour stays honest | builder |
| TC-7 | Weekly check-in clocks: close day, stage days, week length, late week, no series time line | 07 Q11; 13 Q12; 15 Q10; 38 Q2, Q3; 39 Q10; 48 Q14, Q15 | Ruled in part: ruling 3. Close day Friday by default; collect 3, review 1, sort 1; week length fixed at five working days and not editable; the series has no time-box line (C-29); a late week is not counted against a time box | builder |
| TC-8 | Rating window, reminder day, outcome-used follow-up | 09 Q4; 10 Q1; 13 Q4; 19 Q4; 45 Q3; 48 Q8 | Rating prompt at closure; one reminder after two working days; window ends after the fifth working day. Outcome-used asked one calendar month after closure, deferrable seven days twice, answer period 28 days. Asked for Initiative, Brainstorm, Problem, Decision; not series | Nitin |
| TC-9 | Brainstorm clocks: phase lengths, session overrun, late-thought window, how far ahead | 07 Q10; 35 Q5; 36 Q1; 37 Q3; 51 Q3 | Phases 15, 10 and 15 minutes inside a 45 or 60 minute session (scaled); overrun needs an extension record; late-thought window one working day; a session may be set up to ten working days ahead | Nitin |
| TC-10 | Problem and Decision clocks: owner response, reopened Problem, silent reporter, decide later | 41 Q5, Q6; 42 Q4, Q5; 43 Q2, Q3; 53 Q1; 54 Q1 | Owner answers within two working days; reopened Problem gets two days; silent reporter three days; clock pauses while the company admin assigns an owner; "decide later" once, up to one working day | Nitin |
| TC-11 | Review dates and expiries: Future shelf, ambiguity, governed review, backlog reminder | 21 Q2, Q3, Q11; 26 Q6, Q12; 29 Q8; 30 Q5; 31 Q3 | One quarter by default (A-058), 91 days for governed state, an accepted ambiguity returns after one quarter, backlog reminder weekly at the item's review date | builder |
| TC-12 | Drafts that stand still | 03 Q3 | Never auto-cancelled; Nira marks a draft "Waiting for you" after 30 days | builder |
| TC-13 | Life of Pulse lines (shared, A1, A2) | 11 Q8; 47 Q8 | A line goes when the person opens it, or when the intent closes plus seven days | builder |
| TC-14 | Define clock constants | 26 Q1, Q2, Q3, Q11 | Keep the v1 constants: 90 minutes recorded per intent, amber at 15 and red at 5 minutes, "Add 15 minutes" | builder |
| TC-15 | Reminder cadence for people | 06 Q3; 13 Q9; 35 Q6; 45 Q4 | One reminder at half the stage and one the day before it ends; at most one nudge per person per working day; affected people are not reminded after the first telling. North drafts, nothing leaves the product | Nitin |

### 6.5 Agents

| ID | Question | Raised by | Proposed answer | Who |
|---|---|---|---|---|
| AG-1 | North's clock check without a scheduler | 08 Q1 | Run on open and once a day on the first request per intent; no background scheduler this round | Nitin |
| AG-2 | Limits on proposals, nudges, pace statement and snooze | 07 Q5, Q6; 08 Q5, Q9; 13 Q6 | One open proposal per intent; one open nudge per person per stage; North states pace only after two completed steps, otherwise "I cannot tell yet"; snooze once a day | builder |
| AG-3 | Who authors and sends nudges and messages | 13 Q8; 43; 45 | North decides and drafts the text and signs messages "North"; Nira places the line; the organiser's "Nudge" button creates a message draft only; nothing is sent from the product (C-23) | builder |
| AG-4 | Lens defaults: redraft count, retry, draft order, pack fallback text, mark target | 44 Q1, Q6, Q7, Q8; 27 Q7 | One redraft, one retry, drafts in file 44's order of nine kinds, pack fallback counts as not drafted, five-second mark target (not a hard limit) | builder |
| AG-5 | The three-question cap across Define | 27 Q5; 29 Q2, Q3; 31 Q15; 44 Q3 | Ruled: ruling 9 and A-045. Three open questions per person across all Define work and all their open Initiatives; ranking by cards that use the term; escalations count | builder |
| AG-6 | Similarity and relatedness without a number | 21 Q8; 35 Q8; 41 Q4; 42 Q6, Q12 | Judged in words; no numeric threshold; no auto-draft of a cause after N notes; no "bigger than a fix" nudge this round | builder |
| AG-7 | Memory: filters and what is written | 46 Q4, Q5, Q6, Q7, Q8, Q12, Q13 | Follow file 46: cancelled intents write one decision line, Nira writes nothing by default, lines shown before closing with "Do not remember this", series and weeks write nothing | builder |
| AG-8 | A "Stop remembering" switch | 46 Q1 | Yes: a per-person switch beside read, correct and delete (A-049), on top of what is never remembered at all (A-050) | Nitin |
| AG-9 | North's memory budget and drafting for observers; quiet-seat nudge | 08 Q8; 25 Q9; 36 Q3 | 1200 characters for a turn, up to 4000 for a draft; nothing drafted for observers; no quiet-seat nudge in a live session | builder |
| AG-10 | Organiser strips for a non-admin organiser | 13 Q7 | Every organiser gets the organiser strips | builder |

### 6.6 Numbers and limits

| ID | Question | Raised by | Proposed answer | Who |
|---|---|---|---|---|
| NL-1 | Small groups and "Fewer than five" | 04 Q4; 09 Q12; 10 Q2; 11 Q14; 16 Q3; 19 Q1; 31 Q16; 36 Q14; 47 Q4; 55 | Ruled: ruling 8. Counts are exact; means, medians and per-person figures show "Fewer than five" below five records; ratings aggregate from three. The wording in files 04 (three or five), 53 and 55 is corrected | builder |
| NL-2 | Text limits (title, goal, why, note, reason, one-liner, chat) | 12 Q1; 13 Q11; 22 Q12; 35 Q4; 40 Q1; 41 Q3; 43 Q8; 47 Q1; 10 Q1 | One `limits` block in `intent_types.yaml` with each file's default: title 120, goal 140, why 600, rating note 140, outcome line 200, one-liner 140, reason 300, chat 240 | builder |
| NL-3 | Display constants (card counts, widths, polls, pauses, performance targets) | 04 Q2; 15 Q7, Q8, Q11; 17 Q3, Q9; 25 Q7; 12 Q1 | Use each file's proposal; they hold no business rule | builder |
| NL-4 | Ranges and seats: Brainstorm four to eight, wall seats, check-in minimum, adviser maximum | 02 Q2; 06 Q10; 22 Q6; 36 Q9; 38 Q2 | Brainstorm 4 to 8 invited plus the organiser, a guide not a cap; wall 10 seats (D-004); check-in minimum two reporters; Decision up to five advisers; no other cap | builder |
| NL-5 | Brainstorm backing: backs per seat, rounds, runners-up, organiser override | 37 Q1, Q2, Q4, Q7 | Three backs in round 1, one in round 2, at most two rounds, two runners-up shown; the organiser may pick a less-backed idea with a written reason | Nitin |
| NL-6 | Session lengths, regroup and group names, `min_notes` | 02 Q7; 35 Q4; 36 Q2, Q9 | Session 45 or 60 minutes; the organiser's idea counts as one of the group; regroup by organiser only | builder |
| NL-7 | Weekly check-in thresholds: repeat flag, empty weeks, "Nothing this week", trends, review session length | 38 Q5, Q6, Q9; 39 Q2, Q12; 40 Q3, Q4, Q5; 52 Q2 | A repeat is flagged after two matching weeks, looking back five; a pause is offered after three empty weeks; "Nothing this week" counts as an answer; trends after four closed weeks; review session 30 minutes with a 10-minute extension | Nitin |
| NL-8 | Problem limits: passes, similar rows, reason length | 41 Q4, Q9 | At most two passes, then the company admin assigns; five similar rows; reason at least 10 characters | Nitin |
| NL-9 | Define and governed constants | 26 Q1; 31 Q8, Q14 | Keep the v1 values: 90 minutes, 91-day review, target week 1 to 520 | builder |
| NL-10 | Extraction and suggestion caps; pack counts | 22 Q9; 25 Q2; 49 Q1 | Eight terms; no per-person suggestion total beyond three per lane; three first intents, one hint per question, five check-in questions | builder |
| NL-11 | Targets from v1 ("one card in five minutes", "about 20 decisions") | 19 Q9; 24 Q10; 36 Q14 | No targets on any screen; measures only | Nitin |
| NL-12 | Share numbers: expiry default and maximum, log window, note length, body size | 05 Q8; 11 Q2, Q6, Q12 | Expiry default 14 days, maximum 90; log de-duplication ten minutes; note 1000 characters; body 16384 bytes | Nitin |

### 6.7 Signatures

| ID | Question | Raised by | Proposed answer | Who |
|---|---|---|---|---|
| SG-1 | Who closes and who signs, by type | 02; 08 Q3; 09 Q1; 13 row 10; 14; 16; 17; 50 Q5 | The closer in file 02 presses Close intent: sponsor (Initiative; organiser when none), organiser (Brainstorm, check-in series), owner (Problem), decider (Decision). The organiser prepares the draft and moves to `closing`. Signature required for Initiative, Decision and Problem (C-1) | Nitin |
| SG-2 | Is the charter signature also the closure signature | 09 Q2; 50 Q5 | One signature at the charter. Closure of an Initiative asks for a second only if the closure text changes the outcome | Nitin |
| SG-3 | The company admin when a named person is away or has gone: sign for a sponsor, hand to Build, reassign organiser, reviewer or series owner | 09 Q6; 10 Q4; 14 Q5; 32 Q1; 33 Q10; 38 Q4; 40 Q6 | The company admin may sign the charter as in v1 and hand to Build with a reason; may reassign organiser, reviewer or series owner with a reason; never decides or signs for a decider or owner | Nitin |
| SG-4 | Who may cancel and who may extend | 01 Q10; 07 Q3; 09 Q8; 48 Q5 | Cancel: organiser; Initiative sponsor; Decision decider; company admin as a last resort with a reason. Extend: as TC-2 | Nitin |
| SG-5 | Can the decider delegate | 43 Q1 | No delegation. The organiser may change the decider with a reason before the decision; `decided_by` is always the person who decided | Nitin |
| SG-6 | Versioning authority over company terms and measures; accepting an unknown; confirmer left | 27 Q8; 29 Q5, Q6; 30 Q6, Q7; 31 Q4, Q5, Q12 | The term owner confirms a version; the governance lead settles ambiguities and merges or retires terms; the sponsor accepts an unknown; if a confirmer has left the governance lead may confirm a change | Nitin |
| SG-7 | Who decides after a send-back twice to the governance lead | 44 Q2 | The sponsor | Nitin |
| SG-8 | Dissent on a signed charter; reopen Define before signing; measure version note consent; join requests | 32 Q6; 26 Q4; 54 Q4; 47 Q10 | No dissent field (send back with a note only); the organiser may reopen Define before signing and ticks stay; the note needs the owner informed, not consent; the organiser answers join requests | builder |
| SG-9 | `sign_roles` for decider and owner; a business owner who is not a participant | 09 Q1; 14 Q13 | Add decider and owner to the contract; a named business owner reads and writes only their own rows | builder |

### 6.8 Pack

| ID | Question | Raised by | Proposed answer | Who |
|---|---|---|---|---|
| PK-1 | Where the types catalogue lives | 03 Q5 | `modules/m1_intent/contracts/intent_types.yaml`; a company changes only the time boxes, through admin defaults | builder |
| PK-2 | Who reviews pack text and what other industries get | 18 Q5, Q6; 49 Q1, Q4 | Only the family office pack is written this round, after practitioner review by Nitin before status "adopted". Any other industry gets an honest empty state, never another industry's text | Nitin |
| PK-3 | Label wording, strip life, dismissals, hint keys | 18 Q9, Q10; 49 Q2, Q3, Q5, Q6, Q8 | Use the existing `SUGGESTION_LABEL`; the strip shows on an empty home and for admins and organisers under "Suggestions" until dismissed; dismissals per person; after a pack upgrade only new suggestions return; hints keyed by question key | builder |
| PK-4 | Pack kinds feeding the Brainstorm lane; `from_pack` as a counter | 25 Q3; 18 Q4 | Brainstorm uses the pack's idea kinds only; the first-run counter reads `from_pack` | builder |

### 6.9 Build hand-off

| ID | Question | Raised by | Proposed answer | Who |
|---|---|---|---|---|
| BH-1 | Gap analysis is room 0 of the Build centre; amend the Build centre spec | 14 Q14; 33 Q1 | Ruled: ruling 10. Decision request A-075 (the brief's A-060, renamed) | builder |
| BH-2 | Shape of `links.build`; the release record the chain ends on | 12 Q3; 20 Q6 | `links.build` is `{assessment_id, handed_by, handed_at}`. Until Build names a release record the chain shows "Release: not available yet" | builder |
| BH-3 | What each build-ready line needs: unconfirmed drafts, an empty process map, Must against Should, build not needed | 27 Q3; 28 Q2; 30 Q8; 31 Q1, Q2; 32 Q10 to Q12; 33 Q2 to Q5, Q8, Q9 | Follow file 33's seven lines. A draft never counts. An empty map fails. Must clusters need all six governed fields, Should are reported but never block (C-14). When no build is needed, only the charter and glossary lines count | Nitin |
| BH-4 | "Hand over anyway" or all-or-nothing; which roles are required before hand-over | 33 Q6, Q7; 34 Q4, Q9, Q14 | All-or-nothing (file 33). Required: architect, developer and tester accepted; sponsor and ops before release, not before hand-over. A role change after hand-over goes to the organiser and the person named | Nitin |
| BH-5 | After hand-over: banner on later definition changes; signed charter v1 while v2 is a draft | 32 Q4, Q5; 33 Q11 | Signed v1 stays live; Build shows a banner "Definitions changed since hand-off" with the difference | builder |
| BH-6 | Define needs a baseline; who creates it | 22 Q2; 26 Q5; 44 Q5 | North creates a draft baseline when Define opens, through the kernel; the look-up reads the latest signed, else draft, else none | builder |
| BH-7 | Roles for people with no account; skills; one person in several roles | 34 Q2, Q3, Q5 | A named person must have an account to accept; no skills column; one person may hold several roles with a visible note | builder |
| BH-8 | Testing guide corrections outside this folder | 34 Q1; 46 Q9 | Record them for the testing guide owner; not edited here | builder |

### 6.10 Knowledge map

| ID | Question | Raised by | Proposed answer | Who |
|---|---|---|---|---|
| KM-1 | A Backlog node and next kinds on the chain | 12 Q9, Q10; 20 Q4 | Yes, a Backlog node; the chain reads source, backlog item, then intent | builder |
| KM-2 | Edge and node naming: `built_by`, `produces`, landing area, Charter node, owner kinds, File nodes, version `ref`, retention of verify rows | 20 Q5; 55 Q4 to Q7, Q10, Q11, Q13 | Follow file 55's drafted answers; rename the widened edge `handed_to` | builder |
| KM-3 | Restricted steps and fields in the chain and the map; audience of Nira's map line | 12 Q7; 55 Q3, Q12 | Keep silhouettes ("A restricted step"); the line goes to people in the intent's areas and the named owners | builder |
| KM-4 | Scan match confidence and "found elsewhere" waiting for the source owner | 55 Q8, Q9 | A match is a candidate until the source owner confirms; confidence thresholds come from the existing module 3 scan | builder |
| KM-5 | Where teams and systems come from | 28 Q6; 31 Q11 | `people.<id>.team` plus the systems owner column; Lens drafts the source owner | builder |

### 6.11 Data-backed opportunities (file 56)

| Question | Raised by | Proposed answer | Who |
|---|---|---|---|
| What counts as a pattern: how many periods of drift, late weekdays or repeated check-in items? | 56 | Three periods, three Mondays, three weeks; one setting per company | Nitin |
| How is drift defined when `range.breaks` only judges the latest period? | 56 | A new `drift` read over the last n periods in sh_platform/consume/range.py | builder |
| May North draft a Problem start when it judges "reads as a Problem"? | 56 | Yes, as a dashed Problem suggestion, picked up only by a person | Nitin |
| Restricted measures: hide the opportunity or show a silhouette? | 56 | Silhouette with count, as the wall does for sealed cards | builder |
| Should the Ops route widen to the owner role for the ops manager? | 56 | Yes, read only | builder |
| Does the Watcher run inside the cached daily read or as a scheduled step? | 56 | Inside the daily read, like alerts; no scheduler this round (A-079) | builder |

### 6.12 Other

| ID | Question | Raised by | Proposed answer | Who |
|---|---|---|---|---|
| OT-1 | Earlier walls with no intent record: backfill and when | 01 Q7; 04 Q10; 12 Q6; 23 Q7 | Backfill only when the company admin or organiser presses "Create records from earlier work"; never on read. Until then Past says "Earlier walls are not shown here yet" | Nitin |
| OT-2 | Reopen, workaround close and "bigger than a fix" | 42 Q2, Q3; 53 Q2, Q3 | The reporter may reopen once from `closing`; a second reopen goes to the owner (extend, close as not fixed, or Initiative); a workaround closes only with a real-fix date; "bigger than a fix" is `next: initiative` with a reason and needs no fix | Nitin |
| OT-3 | Abandoned drafts; locking people out during `closing` | 01 Q11; 09 Q10 | An abandoned draft is cancelled with a reason, shown to its starter; participants cannot add material while `closing` | builder |
| OT-4 | One backend process; email path; PDF method; QR library; retention at offboarding | 01 Q6; 16 Q5, Q9; 17 Q1; 32 Q2 | One process for the demo; drafts only, no email; browser print for PDF; a small QR library; keep everything after offboarding | builder |
| OT-5 | Past, Outcomes page and a decision log | 12 Q4; 43 Q7 | Keep the Outcomes page beside Past; a decision log is Past filtered by type | builder |
| OT-6 | Chains that loop; the backlog's reminders | 02 Q9; 21 Q2, Q3 | No limit; North flags a third hop in one chain. Backlog reminder 07:00 weekly, escalation after four weeks | builder |
| OT-7 | Seed accounts and names for the demo | 50 Q1; 51 Q1, Q2; 52 Q1; 53 Q8; 54 Q7 | Add to the local synthetic seed: an organiser account for Janet, seats for Mei Ling, Ravi and Rahul, a second company admin; a reader may name a stand-in at setup | builder |
| OT-8 | Withdrawal of a wall card; ending a series | 23 Q6; 38 Q7; 52 Q3, Q5 | The author may withdraw until the freeze (file 24); a series is ended, never cancelled, once a week has closed (ruling 23) | builder |

## 7. Residual contradictions the rulings do not yet cover

Each row names the files, quotes the clash and proposes a ruling. Where the brief's rulings 1 to 24 already decide the matter, the sweep needed is listed in section 6 (marked Ruled) and not repeated here. These rows would become rulings 25 onward in the brief; the product ones are also in section 8.

| ID | Files | The contradiction | Proposed ruling |
|---|---|---|---|
| C-1 | 01, 09 against 02, 13, 14, 16, 17 | 01 and 09 say the organiser presses "Close intent" and the sponsor, decider or owner only signs; 02, 13 (row 10), 14 and 16 name a closer per type (sponsor, organiser, owner, decider); 17 says "Approver only" for confirming a Problem closure | The closer named in 02 presses "Close intent" and signs where a signature is needed (one press). The organiser prepares the draft and presses "Move to closing". The organiser sees "Close intent" only where they are the closer. File 01's transition table and 09's buttons follow |
| C-2 | 01, 02, 03, 04, 07, 09, 12, 43, 48, 50, 54 | Where a cancel reason lives: `cancel {by, at, reason}` (01); `closure.cancel_reason` (04, 09, 43); `closure.summary` (02, 07, 12, 48, 50); `closure.why_it_happened` (54); `closure.next` with "nothing" (03). Who may cancel: organiser (01), organiser or sponsor (09, 48), organiser or decider (43) | `cancel` (01) is the one place; screens read `cancel.reason`; `closure.summary` stays empty on a cancel. Who cancels: SG-4. `closure.cancelled_by_role` (48) is kept |
| C-3 | 01, 02, 03, 22, 35, 38, 41, 07 | Open is `PATCH /state to=open` (01) but `POST /api/intents/{id}/open` elsewhere; extend is `POST /extend` (01) but `POST /time-box/extend` with `.../extend/{n}/decide` (07) | `POST /api/intents/{id}/open` is a named route and `PATCH .../state` refuses `open`, `closed` and `cancelled`. Extension is `POST /api/intents/{id}/extend` with `days`, `reason`, `scope`; approval is `POST .../extend/{n}/decide` |
| C-4 | 01, 04, 05, 12, 15 | List route: an array (01) or `{items, total}` (05, 15); `view=running|finished|past` (01) or `view=<mine|all>` (04); `GET /api/intents/past` and `/mine` (12) | One list route owned by 15: `{items, total, facets}`; `scope=mine|all`, `view=running|finished|past|shared`; 12's `past` and `mine` become queries. Counters stay at `GET /api/intents/measures` and `/home` |
| C-5 | 01, 05 | Areas change by `PATCH /api/intents/{id}` (01) or `PUT .../areas` with a confirm step (05) | `PUT .../areas` carries `areas`, `affected` and `affected_may_read` with the "N more people will see this" confirm; `PATCH` carries title, purpose and people and refuses `areas` |
| C-6 | 01, 05, 11, 14, 17 | `share` is `{link, who_may_open}` (brief), a token hash with `expires_at` (05), `{entries, log, notes}` (11), per-person tokens (14), `share.short` (17); pages `/centre/intent/<id>/share` (05) against `/centre/shared/...` (11) and `/centre/intent/shared/:token` (14) | `share` is 11's structure; `share.link` holds the id of the live link row, `who_may_open` is rebuilt from live rows, hashes live only in `entries`; `expires_at` per entry. One page (RT-4). "Shared with me" is `/centre/intent?view=shared` |
| C-7 | 05, 10, 13, 17, 51, 53 | Rating: `rated_by` (05) against `rating.rated` (10); reminder after two working days and drop after the fifth (10) against a seven-day window with a day-5 reminder (13); Pulse kinds `rate` and `used` (10) against `rating` and `outcome` (13) with no row for "was the outcome used"; rating visible to everyone (17); ratings never close (51) against closing after 7 days (53) | File 10's storage and timing (TC-8); 13 gets a row 18 "outcome used" of kind `outcome`; kind names are 13's (`rating`, `outcome`); rating is shown to participants only; copy is 10's switch "Put my name on it", off by default (ruling 15) |
| C-8 | 01, 06, 13, 14, 15, 43, 54 | 01 `people.*` entries are `{account_id, name}`; 06 stores person ids and adds `people_detail`; 13, 14, 15, 43 (L95) and 54 treat advisers as participants, but ruling 21 makes `advisers` its own list | RS-4. Pulse row 1, the permission table, the filters and the role chips list advisers separately |
| C-9 | 01, 04, 05, 09, 15 | People list and clock for area-tagged people: names to the card tier (01), "organiser only" (05), a count (04, 09), people and clock to "anyone tagged" (15); closure text for the same people | Area-tagged non-affected: organiser, people count, clock, outcome once closed (with `what_came_out` and `next`). Affected: also names (ruling 4). `summary` and `why_it_happened` only in the content tier. Files 01 and 15 are corrected |
| C-10 | 08, 13, 26, 37, 45 | North's state is `north.turn` and `north.drafts` (08) but Pulse reads `waiting_on`, `votes`, `drafts_to_confirm`, `definitions_waiting`, `process_waiting` (13, 45) | `north.turn` is the one source of whose turn it is; `waiting_on` is derived from it; the other four lists are derived on read from the owning stores, never stored on the record |
| C-11 | 02, 08, 13, 38, 40, 52 | Check-in stage keys: `collect, review, sort` (02, 13), `collect, review, triage` (08, 40 L26); week states `collect|review|sort|closing|closed` (38) against `collecting|ready|in_session|reviewing|closing|closed` (40); week opens "every Monday 08:00" and close "Wednesday 14:00" (52) against the next working day after the close day (ruling 3) and 17:00 | Stage keys `collect`, `review`, `sort`; week states are 38's; 52's times are examples that follow the close-day rule, and its steps 8 and 9 are put in time order |
| C-12 | 38, 39, 40, 52 | Item and route names: `decision`, `fate_ref`, `reason`, `answers[]`, `submissions[]`, `from` (39, 40, 52) against ruling 17 (`fate`, `fate_reason`, `decided_by`, `ref`, `by|anonymous`); routes `/pulse/entry` (39) against `/weeks/<week_key>/answers` (38) and `/digest`, `/items/<id>/decision` (40) | Ruling 17's names only; extras `mark` and `unit` are registered by 38. Routes are 38's: `.../weeks/<week_key>/answers`, `.../items/<id>/fate`, `.../digest`, `.../close` |
| C-13 | 26, 32, 33, 50 | When an Initiative reaches `closing`: when Define closes (26), at the first signature (32), after hand-over through 09 (33, 50). Charter signing is blocked until "Is a build needed?" is answered (32 L194) but 33 and 50 have Daniel sign first | `closing` begins when the Build-ready decision is made (hand-over pressed, or "no build needed" recorded). The sponsor may sign before the build question is answered; line 1 counts as passing at signing. Files 26, 32 and the L194 rule are corrected |
| C-14 | 26, 31, 33 | Governed state: Must needs all six fields stated and Should never blocks (31); the build-ready check covers "every Must and Should measure" and counts the default review date as confirmed (33); A-054 says Must or Should needs a governed cluster (26) | The "governed" line of the check covers Must clusters; Should clusters are counted and shown, not blocking. A review date left at the default never blocks. 31's text and A-054's wording are aligned |
| C-15 | 28, 30, 31 | Source owner is a separate extras cell (28) or the Data owner cell (30); 28 expects 30 to own the catalogue columns; 30 changes no contract | RS-9: 28's extras file is the source; 30 reads it; the M2 contract change is a later request |
| C-16 | 02, 04, 19, 33, 34 | `build_ready` is `outcome.build_ready` (02, 04, 19) or a block `build_ready {state, lines}` directly on the record and `build_handoff` (33, with per-line `missing` stored, against ruling 12's counts only); required roles are three (33) or six with "Hand over anyway" (34) | Flat on `outcome`: `build_ready` (boolean), `build_ready_gaps` (line keys), `handoff` (02). The seven-line detail is computed on read. Roles: BH-4 |
| C-17 | 26, 27, 28, 29, 44, 50 | Define tabs and keys: 26 lists three panels, 28 three tabs, 29 six tabs, 27 adds Shelves and Charter, 44 uses `?cluster=` and `?cell=`, 50 uses `?tab=governed`; stage key `define_strategically` (26) against `define` (27) and a `data_sources` entry in `stages` (28); layout 68/32 (26) against 60/40 (29) | Tabs: `clusters`, `process-map`, `data-sources`, `glossary`, `catalogue` plus `governed` (added to ruling 18). Stage keys are 02's; sub-stages are checks inside `define_strategically`, not `stages[]` entries. Layout 60/40 on every tab |
| C-18 | 22, 27, 29, 36, 41, 42, 50, 51, 53, 54 | Ruling 16 (flat) is not yet applied: `outcome.initiative.*`, `outcome.problem.*`, `outcome.brainstorm.*`, `outcome.decision.*`, `outcome.processes`, `outcome.glossary` are still written | Sweep all ten files to flat keys. Define artefacts use `refs` plus derived counts (RS-8). The `chosen`, `question` and `what` keys are 02's |
| C-19 | 01 against every file | 01 refuses unknown fields (strict key set, as `SessionStore._read`), while the files add roughly ninety keys directly on the record (`north`, `define`, `session`, `converge`, `rating`, `outcome_used`, `series`, `people_detail`, `refs`, `memory`, `from_pack`, `link_log`, `late_thoughts`, `share_requests` and others) | 01 owns one `ALLOWED_KEYS` built from every "Fields this feature adds" section at the Wave 0 merge. A key not in it is refused; adding one is an orchestrator edit to SHAPES |
| C-20 | 01, 15, 21, 49, 50 | Index file `intents/index.json` (01, 50) against `intents/_index.json` with search text (15); flat files `intents/backlog.json` (21) and `intents/_suggestion_marks/` (49) beside folders | One `intents/index.json`: 01's row fields plus 15's search fields (`body_text` is never returned). `backlog.json` and `_suggestion_marks/` stay; folder names start with a type prefix and a hyphen so none collides |
| C-21 | 20, 21 | Backlog item made at once on "Add to backlog" (20) or only after the source intent or week closes (21); `area` against `areas`; `source.pulse_item_id` against `source.week_key` and `week_item_id` | File 21 owns the shape and the timing. "Add to backlog" in 20 records the fate or next row on the source; 21 makes the item when the source closes or the week closes |
| C-22 | 12, 13, 15, 18, 43, 47 | Pulse lines that file 13 says do not exist: "a line is an act or a share, never a notice of existence" (13) against Nira lines for area digests (15), no area and first intent (18), affected people A1 to A5 (47), decision advisers (43) | File 13 gains rows 19 onward for these, kind `inform`, lowest priority in the cap; its rule is amended to "an act, a share or a notice to a named person". The monthly area digest (12) is one `inform` line |
| C-23 | 08, 43, 45 and the brief, section 5 | "Nudge" sends a Nira line (43), drafts a message and sends nothing (45), North nudges the person whose turn it is (brief) | AG-3: North decides and drafts, Nira places the line, the organiser's button makes a draft; nothing leaves the product |
| C-24 | 14, 16, 17 | Events: the projector display-on event is in `events.jsonl` (17 L297) and the run log (17 L275) but 16's kind list is closed; `intent_refused` in the run log (14) | Projector opening goes to the run log only; 16's closed list of event kinds stands |
| C-25 | 08, 23, 24, 28, 40, 41, 45, 48 against the brief, section 4 | The company admin reads the North thread (08), sees cards "by the same rules as a participant" (23, 24), sees source rows with owners (28), closes a stuck week (40), assigns an owner (41), sees who owes what by name (45) | The company admin is existence, outcome, counts. Admin actions are only: last-resort cancel, hand-over of organiser, reviewer or series owner, and signing for an absent sponsor (SG-3). Each listed screen is swept (VS-4) |
| C-26 | 41, 42, 53 | Owner required to open (42) or optional (41); acceptance moves `describe` to working (41) or a separate "Statement agreed" press (42); "Ratings do not apply here" (41) against a rating Pulse line (42) | The owner may be empty at open (41); acceptance assigns the owner; "Statement agreed" (42) closes `describe`; Problems are rated (10, ruling 15); the stage view shows triage while `describe` and the working screen after |
| C-27 | 02, 08, 35, 36, 37 | Brainstorm stages: `think_alone`, `live_session`, `choose` (02, 08) against Prepare and Session (35); the clock moves to `in_session` at `session_at` (35) against the organiser's "Open the session" (36); converge "the day after" (35) against in the session (36, 37); no private room first (36) against private pre-thinking cards (35) | Stage keys are 02's. "Open the session" (01's Start session) moves to `in_session`; the clock only nudges. Converge sits in stage `choose`. Pre-thinking is private until the session opens (35) |
| C-28 | 01, 09, 12, 37, 43, 46 | Decision closes at the decider's act without resting in `closing` (43, 46); post-close writes (late thoughts 37, history notes 12, ratings 10, shares 11, `outcome_used`, `next[].ref`) are not all in 09's allowed list | A Decision passes through `closing` inside one write. After `closed` only these stay writable: `ratings`, `rating`, `outcome_used`, `share`, `history_notes`, `share_requests`, `late_thoughts` until `frozen_at`, and the `next[].ref` link. 09 lists them |
| C-29 | 01, 02, 13, 15, 38 | A Weekly check-in series gets `time_box_days: 5` (02) and a computed `time_box.ends` at Open (01), but rows 8 and 9 of 13 and the overdue list skip it | The series has `time_box.ends` null and no clock line; each week has its own clock; 02's `time_box_days: 5` is the week length |
| C-30 | 40, 52, 53 and rulings 3, 17 | The reviewer writes fates (ruling 3, 40, 52) but file 53 has the reporter start a Problem and write `fate: problem` with a reason | The reporter's "Open as a Problem" carries `from_item`; only the reviewer writes the item's fate. File 53 step 1 is changed |
| C-31 | 23, 24, 25, 26 | Lens fills quarter 4 when rooms close (23) against North fills only on button press and Lens only reads (24); the lane names differ (25 names an Intent, Pain, Future and Lever set; 26 names Think, Fix, Fear and Dream); window default 5 against 3 | File 24 wins (A-055: a filled quarter is marked guessed and a person presses). Lane names come from `wall_questions.yaml`, not restated in 25 or 26. Window: TC-4 |
| C-32 | 24, 26, 34 and ruling 21 | "Committee" (24, 26) and "governance lead" (29, 34) are named as people but have no slot | "Committee" means the intent's organiser, sponsor, participants and named owners; no slot. The governance lead is a profile role, stored in profile governance, default company admin (A-087) |
| C-33 | 50 to 54 and rulings 2, 15, 16, 17 | Journey text still carries older wording: Decision "three questions" (54), "Rate without my name" tick (53, 54), nested outcomes (50, 51, 54), `intents/<id>.json` (54), `fate_ref` (52), extra people names beyond the six Ardmore names (Mei Ling, Ravi, Rahul, a surname for Janet) | Journey files are swept to the rulings after the feature files. The extra names are kept as synthetic seeds (OT-7), listed once in the seed file |
| C-34 | 06, 19, 39, 55 and ruling 8 | Per-person figures: 06 and 39 hold counts and minutes per person, 55 applies "Fewer than five" to exact counts of fields and people | A person's own figures in their own view are allowed. Any figure about another person, any mean or median, shows "Fewer than five" below five. Exact counts stay exact (ruling 8) |
| C-35 | 14, 29, 31 | Citations to verify: 31 cites A-069 for "company admin confirms nothing", but A-069 in `docs/decisions.md` is about restricted areas; 14 cites A-025 (who may organise a session) and 29 cites A-043 and A-044b, which exist in `docs/ledger/autonomous.md`; the brief's ruling 9 once said A-043 | Replace the A-069 citation by the intended decision or request a new one (A-080 covers the company admin); other citations stay |

## 8. Decision requests for `docs/decisions.md`

Check made on 7 October 2026: the highest number in `docs/decisions.md` is A-073 (`docs/ledger/autonomous.md` stops at A-051). The brief's provisional A-059 (super admin existence through the kernel) and A-060 (amend the Build centre spec) are already taken in `docs/decisions.md` (A-059 is the builder-model router, A-060 the company graph projection), so they are renamed A-074 and A-075. The requests below start at the next free number. They are for Nitin; nothing here is applied to `docs/decisions.md`.

| No | Request (one line) | Files that need it |
|---|---|---|
| A-074 | The super admin may read intent existence (title, type, state, areas, people count, dates, time box status) through the kernel on request; the control plane still stores no company data; a company switch removes titles. (Was A-059.) | 01, 04, 05, 12, 14, 15, 19, 48 |
| A-075 | Gap analysis is room 0 of the Build centre at `/centre/build/gap-analysis?from=<id>`, `modules/m3_connect` moved, not rebuilt; `BUILD-CENTRE-SPEC.md` is amended. (Was A-060.) | 01, 02, 04, 09, 14, 20, 32, 33, 50, 55 |
| A-076 | Who may start an intent: anyone starts Brainstorm, Problem, Decision and Weekly check-in; an Initiative needs the organiser capability; all six company roles reach the centre | 01, 03, 04, 05, 14, 18 |
| A-077 | Closing (ruling 25): the organiser presses Close for every type after the per-type confirmer has acted (sponsor, decider, owner then reporter, nobody); an Initiative enters `closing` at charter signature (ruling 26); the organiser or the company admin may cancel, reason in `closure.cancel_reason` (ruling 27) | 01, 02, 08, 09, 13, 14, 16, 17, 50 |
| A-078 | Clock rules: cut-offs at 50 and 20 percent, extension by the organiser once and then the closer or company admin, no cap, who is asked if nobody picks, stage splits, reminder cadence | 02, 06, 07, 08, 09, 13, 22, 28, 43, 48 |
| A-079 | North's clock check runs on read and once a day per intent; no background scheduler this round | 07, 08, 13 |
| A-080 | What sits below the content tier: area-tagged people see organiser and a people count; the company admin sees existence, outcome and counts, and acts only as last-resort cancel, hand-over of a named role and signing for an absent sponsor | 05, 08, 09, 14, 15, 16, 28, 31, 32, 33, 38, 40, 41, 45, 48 |
| A-081 | Sharing and anonymity: company accounts only; links open only for named people or areas; expiry 14 days default and 90 maximum; the affected switch may change until closing; anonymous cards reach a link visitor as a count below five participants | 05, 11, 14, 16, 36, 39, 40, 47 |
| A-082 | Ratings and measures: reminder after two working days, window to the fifth, outcome-used one month after closure, aggregates from three, no targets on screen | 09, 10, 13, 19, 45, 48 |
| A-083 | Brainstorm rules: three backs in round 1 and one in round 2, at most two rounds, organiser may pick a less-backed idea with a reason, phases 15, 10 and 15 minutes, late-thought window one working day | 02, 35, 36, 37, 51 |
| A-084 | Weekly check-in thresholds: minimum two reporters, repeat flag after two matching weeks, pause offer after three empty weeks, trends after four weeks, 30-minute review | 38, 39, 40, 52 |
| A-085 | Problem and Decision rules: owner answers in two working days, at most two passes, reporter reopens once, no delegation of the decider, "decide later" once | 41, 42, 43, 53, 54 |
| A-086 | Build hand-off rules: the seven-line check is all-or-nothing, a draft never counts, architect, developer and tester accepted before hand-over | 27, 28, 30, 31, 32, 33, 34 |
| A-087 | A governance lead role (default company admin) settles ambiguities and merges or retires company terms; the sponsor accepts an unknown and decides after a second send-back | 26, 29, 30, 31, 34, 44 |
| A-088 | Pack content: only the family office pack is written this round; Nitin reviews first-intent and hint text before "adopted"; other industries get an honest empty state | 18, 49 |
| A-089 | A per-person "Stop remembering" switch for agent memory, beside read, correct and delete | 46 |
| A-091 | Data-backed opportunities (file 56, ruling 32): the Watcher may draft opportunities from the records; the analyst adds evidence; North judges; only a person opens the Initiative; the pattern thresholds are company settings. Enhancements to a running project are Initiatives, never Problems (ruling 31) | 02, 04, 20, 21, 22, 41, 56 |
| A-090 | Earlier walls become intent records only when the company admin or organiser presses "Create records from earlier work" | 01, 04, 12, 23 |

## 9. Suggested build order

Shared files have one writer, the orchestrator: `ui/src/App.tsx` (routes), `sh_platform/route_permissions.yaml` (every new route, default deny), `sh_platform/app.py` (router mounts and `app.state`), and the SHAPES document `docs/plan/SHAPES.md` (record keys, LINE kinds, memory shape, `more`). Also single-writer: `ui/src/shell/roles.ts`, the module `manifest.yaml` route declarations, and the contract `modules/m1_intent/contracts/intent_types.yaml` (owned by 02). Two files are shared but owned: `sh_platform/pulse/lines.py` (13 owns; each type registers its row functions in its own file) and `sh_platform/profile/view.py` and `store.py` (05 owns). A builder writes new code in new files and hands the orchestrator one "wiring block" per file: route lines, route permissions, SHAPES keys. The orchestrator merges the blocks wave by wave.

| Wave | Files (parallel within a wave) | Why here | Waits for |
|---|---|---|---|
| 0, orchestrator alone | Apply section 7 rulings and ruling 25 to the brief and files; SHAPES keys and `ALLOWED_KEYS`; one route block from 14; router mounts in `app.py`; route stubs for the twelve views in `App.tsx`; `profile.company.time_zone` and the `areas` section | Everything later imports these | A-074, A-075 |
| 1a | 01 (store, states, id, nine routes), 02 (catalogue and `GET /api/intents/types`) | The record and the types are the base of all files | Wave 0 |
| 1b | 05 (areas, `read_intent`, matrix tests), 14 (guard layer and role test), 16 (events writer), 15 (index inside 01's store), 07 (clock functions, no screens) | Pure services over 01; each has its own tests | 1a |
| 2 | 06 people, 08 North panel and runner, 09 closure and sign-off, 10 ratings, 11 share, 13 Pulse reader and messages, 03 chooser, 04 home | Shared screens and services every type uses; 09 reads 10 and 40 through stubs | 1b; A-076 to A-082 |
| 3, one builder per type | Initiative stage 1: 22, 23, 24, 25. Brainstorm: 35, 36, 37. Weekly check-in: 38, 39, 40. Problem: 41, 42. Decision: 43 | Types are independent once waves 1 and 2 land; each registers its Pulse rows and wiring block | Wave 2; A-083 to A-085 |
| 4, Initiative Define and hand-off | First 27, 28, 29, 30 together; then 31 and 44; then 26; then 32 and 34; last 33 | 26 needs the four artefact contracts, 32 needs them signed, 33 reads all | Wave 3 (22 to 25); A-086, A-087 |
| 5, readers and views | 12 past, 19 measures, 20 links, 21 backlog, 45 waiting, 46 memory, 47 affected and observer, 48 admin, 49 pack, 18 empty states, 17 phone and projector pass, 55 knowledge map | They read finished records; 20 and 21 need the types' next kinds; 55 needs 32 and 33 | Waves 3 and 4; A-088 to A-090 |
| 6, verification | 50 to 54 run as end-to-end scripts (one tester each; the author is never the reviewer), then the full suite and the security review, then screenshots against the artboards | The journeys are the acceptance tests; the brief says own-feature tests first, full suite after the MVP | Waves 1 to 5 |

Two cautions for the orchestrator. First, resolve C-1, C-13 and C-19 before Wave 1: they change the transition table and the key set that every file builds on. Second, Wave 3 files must not be built from the unswept text of 22, 36, 41, 42 and 54 (nested outcomes, C-18); sweep those five first.
