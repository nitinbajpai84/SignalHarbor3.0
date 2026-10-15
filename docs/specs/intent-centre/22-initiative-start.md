# 22. Initiative start: the six questions and the hand-over to the wall

Part of: Intent Centre v2. Depends on: 01 (intent record), 02 (type catalogue, Initiative stage days), 03 (chooser and the start shell), 06 (people and invitations), 07 (time box). Feeds: the Initiative's first stage "Think unfiltered" (the v1 wall), "Define strategically", and the Build-ready check.

## Purpose (three sentences)
This file is the canonical definition of the Initiative's six start questions (brief section 10, ruling 2): their order, wording, required flags and field names are fixed in the table at the top of "Screens, element by element", and specs 02 and 03 copy that table exactly and do not restate it. North asks the six questions one at a time, drafts help from the company profile, the interviews, the uploaded documents and a look-up of the existing glossary and catalogue, reads each answer back, then writes "Here is what I understood". The person confirms, the record is written with a stated or guessed mark on each answer, and the wall is prepared for Think unfiltered with its purpose line, lanes, invited people and window.

## Who uses it and when (role, moment, trigger)
- **The organiser** (Janet at Ardmore): she has picked the Initiative tile on `/centre/intent/new`, confirmed North's proposal, or pressed "Start the follow-on" on a closed intent. She answers; she confirms the summary; she presses the button that opens the wall.
- **Sponsor and invited people** (Daniel sponsor, Katie analyst, Aaron participant, Harvey data owner, Grace approver): they do not see this screen. They get a Pulse line from the invitation (spec 06) after the intent is open.
- **Company admin and super admin**: cannot reach this screen for someone else's draft. After opening they see the intent as the brief section 4 allows.
- **Agents decide and draft; people act.** North asks, drafts, looks up, reads back and drafts the summary. The person types or picks every answer, confirms the summary, and presses "Open this intent" and later "Open the wall". Lens is not used at the start (it works in Define). Nothing is signed here.

## Entry points (every route, link, Pulse line, button that leads here)
| From | What the person sees | Lands on |
|---|---|---|
| Tile "Initiative" on `/centre/intent/new` (spec 03, Screen A) | Tile with chip "10 working days" | `/centre/intent/new?type=initiative&step=goal` |
| North's proposal panel "Yes, an Initiative" (spec 03) | The typed line is already in Question 1 | same, line carried as the first draft of the goal |
| "Your drafts" row, button "Carry on" | Row with Initiative chip | `/centre/intent/new?type=initiative&draft=<id>&step=<first unanswered key>` (Open questions 10) |
| Closed Brainstorm or Problem, "What happens next", button "Start an Initiative" | Chosen idea or problem text | `/centre/intent/new?type=initiative&from=<intent id>` (ruling 1 route); the source's title and closure summary are offered as the draft goal; `links.from` is set |
| Nira Pulse line "Start an Initiative from this idea" | Line with link | same as above |
| Summary card "Change" on a question | Pencil link next to each line | the same route at that question, answers kept |

The manifest declares `/centre/intent/new` for every signed-in company role (spec 03). The new API calls in this spec (`/api/intents/<id>/definitions/check` and the wall hand-over inside `/api/intents/<id>/open`) are declared too; a route with no declaration is refused. After opening, the intent screen is `/centre/intent/<id>` and the wall is `/centre/intent/<id>/wall` (ruling 1).

## Screens, element by element

### Canonical start questions (the contract: `initiative_start.yaml` holds exactly this)
Order is fixed. `key` is the `step` value in the route and the key in `start_answers`. "Writes" is the field on the intent record (see Fields). Every question takes North's draft and a read-back.

| # | key | Exact wording (North's question line) | Required to open | Writes |
|---|---|---|---|---|
| 1 | `goal` | What are you trying to achieve? | Yes: goal line and why | `purpose`, `outcome.goal` |
| 2 | `people` | Whom do you need to involve, and who is affected? | Yes: named people, or "Just me for now". Sponsor optional | `people.sponsor`, `people.participants`, `people.affected`, `outcome.people_note`, `affected_may_read` |
| 3 | `build` | Do you think this needs a build (new data, pipelines, reports)? | Yes: yes, no or not sure | `outcome.build_needed` |
| 4 | `definitions` | Do we already have a business glossary and technical definitions for this, or will we discover them along the way? | Yes: yes, some or no | `outcome.definitions_exist`, `outcome.definitions_found` |
| 5 | `areas` | Which areas does this touch? | Yes: at least one | `areas` |
| 6 | `deadline` | When must this be decided by? | Yes: a date | `outcome.decide_by`, `time_box.ends` |

After question 6 the stepper shows "Review" (`step=review`, Screen B). Stepper labels: Goal, People, Build, Definitions, Areas, Deadline, Review.

### Screen A. The six questions (route `/centre/intent/new?type=initiative&step=<goal|people|build|definitions|areas|deadline>`)
**Layout at 1280.** Top bar: type chip "Initiative" with "Change type", then the stepper "1 Goal  2 People  3 Build  4 Definitions  5 Areas  6 Deadline  Review". Left two thirds: North's question and the person's answer control, then North's help panel under it. Right third: the "So far" card (answers given, each with a mark chip and "Change"). Footer: "Back", "Next", "Save and leave".
**Layout at 390.** One question per page. "So far" collapses to a bar "Question 3 of 6" that opens as a bottom sheet. North's help panel sits under the answer control and is collapsed to its headline line, which expands on tap. Footer sticks above the keyboard; "Next" is full width.

Top bar and frame (every question):

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Type chip | chip | "Initiative" | none | creator | Always present |
| "Change type" | link | Label | Returns to `/centre/intent/new` (chooser, spec 03); answers kept in the draft | creator | Always present |
| Stepper steps | chip list | Goal, People, Build, Definitions, Areas, Deadline, Review; answered steps show a tick | Click goes to that step if it is answered or is the next one; later steps are not clickable | creator | Review is disabled until all six are answered |
| "So far" card | panel | One line per answered question with its mark chip | Each line has "Change" (goes to that question, answers kept) | creator | "Nothing answered yet." |
| "Question N of 6" bar (390 only) | button | Label | Opens the "So far" card as a bottom sheet | creator | Same as the card |

Common to every question:

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Question line | agent line | North's wording of the question, with "Why I ask" (one sentence) | none | creator | Always present |
| "North's draft" panel | agent line + panel | What North drafted, where from ("From the profile", "From the interview with Daniel", "From the document Q3 reporting notes"), and a mark chip "Guessed" | See per question | creator | "North has nothing to draft from yet. Answer in your own words." |
| "Use this draft" | button | Label | Copies the draft into the answer control, still editable. The answer keeps mark `guessed` until the person edits it | creator | Hidden when there is no draft |
| "Skip draft" | button | Label | Hides the panel; North does not draft this question again in this draft | creator | Hidden when there is no draft |
| Read-back | agent line | One line: "So the goal is to ... Is that right?" with "That is right" and "Let me correct it" | "That is right" saves and enables "Next". "Let me correct it" returns to the control | creator | Shown after an answer is sent |
| "Next" | button | Label | Saves the answer to the draft intent and goes on. Disabled while a required answer is missing, with a line naming it | creator | Disabled until valid |
| "Back" | button | Label | Previous question, nothing lost | creator | Hidden on question 1 |
| "Save and leave" | button | Label | Draft kept; goes to `/centre/intent` with the toast "Draft kept in Your drafts" | creator | n/a |
| "North is not available" line | alert | "North cannot draft right now. You can still answer every question." | Controls stay usable; draft panels are hidden; the summary step is written by the person | creator | Shown only when North is off |

**Question 1. What are you trying to achieve?**

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Goal line | field (single line, 140 characters) | Label "In one line". Placeholder "For example: cut the days it takes to produce the quarterly client report" | Saves on Next. The line becomes `intent.purpose` and `title` is drafted from it | creator | Required. Next disabled, line "Say the goal in one line." |
| Why field | field (multi-line, 600 characters) | Label "Why does it matter? Say it in as many lines as you need" | Saves on Next | creator | Required, at least 20 characters. Line "A few words on why will help the people you invite." |
| North's draft | panel | A drafted goal line and why, from: the company profile (constraints, reported figures, interviews of the organiser), the text carried from a source intent, and uploaded documents (only short passages; documents are context, never a figure) | "Use this draft" fills both fields | creator | See common panel |
| Character counters | text | "86 of 140" | none | creator | Hidden until typing starts |

**Question 2. Whom do you need to involve, and who is affected?**

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Involve group | chip multi-select with search | People from the company profile who may take part: name, role, team. Sub-heads "Sponsor" (one), "Take part" (up to the wall's seats, see Rules) | Click or Space adds or removes. A person sits in one group only; moving shows a one-line note | creator | "No people in the company profile yet. Add them in the company profile." with a link. "Just me for now" chip is offered |
| "Just me for now" | chip | Label | Sets involve group empty on purpose. Required to move on when the group is empty, so an empty group is a choice | creator | n/a |
| Affected group | chip multi-select with search | Same list, plus teams as whole-team chips | Same. Whole-team chips add the team's people to `affected` | creator | "Nobody named yet. Areas in question 5 also make people aware." Optional |
| North's draft | panel | Suggested sponsor (profile flag `is_sponsor`, or the person named in a document as owner), suggested takers (people in the interviews who named the topic, analysts of the area), suggested affected (people whose team matches the goal's terms). Each chip says why: "Named in the Q3 reporting notes" | "Use this draft" adds all suggested chips; each chip also adds on its own | creator | See common panel |
| "Affected people may read this intent" | switch | Label and one line: "Off: affected people see that it exists, its title, purpose, stage, clock, people and the outcome once closed. On: they may also read the content." | Toggle; saves on Next. Default off (ruling 4) | creator | Default off. Hidden while no affected person or area is chosen |
| Person not listed | link | "Someone is not listed" | One-line note saved in the draft as a request to the company admin. The person is not added | creator | n/a |
| Restricted people | rule shown as nothing | A person or area the organiser may not see (profile view) is never offered | none | creator | n/a |

**Question 3. Do you think this needs a build (new data, pipelines, reports)?**

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Three choices | radio group | "Yes", "No", "Not sure" | Select; saves on Next | creator | Required |
| "What counts as a build" line | text | "New data, a pipeline, a report or a dashboard that does not exist today" | none | creator | Always shown |
| North's draft | panel | A leaning with the reason, never decided: "Likely yes: 3 of the 4 terms you named are not in the catalogue yet" (counts from the question 4 look-up, so North asks question 4's look-up first, silently, when it has the goal), or "Not sure: nothing in the profile says where this data lives" | "Use this draft" selects the leaning; mark stays `guessed` | creator | If no look-up is possible the panel reads "North cannot say yet." |
| "Why not sure?" | optional field | One line | Saved as the answer's note | creator | Shown only after "Not sure" |

**Question 4. Do we already have a business glossary and technical definitions for this, or will we discover them along the way?**

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Terms strip | chip list | The terms North pulled from the goal and why (for example "quarterly client report", "portfolio return"), each removable, with "Add a term" | Removing or adding a term re-runs the look-up | creator | "North found no terms in your goal. Add the words you use." |
| "What already exists" panel | list grouped in three: Business glossary, Technical definitions, Catalogue | Per term: the existing entry's name, its status ("Signed", "Draft", "Provided by a document"), the owner if known (business owner, data owner or source owner, as the entry names it), and a link "Open" to the baseline glossary or catalogue screen. Counts line: "2 of 4 terms have a business definition. 1 has a technical definition. 1 is in the catalogue." | "Open" opens the baseline screen in a new tab (read only for non-owners). "That is not it" on a hit marks it rejected for this intent, and the count updates | creator, filtered to what the creator may see (restricted fields never listed) | "No baseline exists yet. No glossary or catalogue to look in." The three choices below stay available |
| Three choices | radio group | "Yes, we have them", "Some of them", "No, we will discover them along the way" | Select; saves on Next | creator | Required |
| North's draft | panel | The leaning from the counts: all terms matched and signed means "Yes"; some means "Some"; none means "No"; and the reason as a sentence. "Not checked" is shown when the look-up could not run | "Use this draft" selects it; mark `guessed` | creator | See common panel |
| "What this means" line | agent line | Yes: "Define will start from what exists and only fill gaps." Some: "Define will keep the existing entries and draft the rest." No: "Lens will draft definitions from the wall, the interviews and the documents." | none | creator | Shown after a choice |

**Question 5. Which areas does this touch?**

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Areas picker | chip multi-select with search | The company's departments and operations areas from the profile; restricted areas filtered out | Toggle; selected chips collect above | creator | "No areas in the company profile yet. Add them in the company profile." Next disabled: at least one area is required |
| Help line | text | "Everyone tagged to these areas will see that this intent exists, its title, purpose and stage. They open the content only if they take part." | none | creator | Always shown |
| North's draft | panel | Suggested chips from the teams of the people chosen in question 2 and the areas named in the goal and documents, each with its reason | "Use this draft" selects them all | creator | See common panel |

**Question 6. When must this be decided by?**

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Decide-by date | field (date, native date input) | Prefilled with the default end: 10 working days from today (`initiative_start.yaml`), Monday to Friday, holidays when the company has set them, in the company's time zone from the profile, else UTC. Under it: "That is 10 working days." | Changing the date recomputes "That is N working days" and the stage split line below | creator | Always prefilled. Cleared field disables Next |
| "Use this date" | button | Label | Fills the date field with North's drafted date; mark `guessed` until the person edits it | creator | Hidden when there is no drafted date |
| Stage split line | text | "Think unfiltered 3, Define strategically 6, Build-ready check 1 working days" for 10 days (spec 02); for another count North shows the proposed split and the person may keep it | none | creator | n/a |
| North's draft | panel | "A usual Initiative takes 10 working days. Your date leaves 6." or a warning "This leaves 1 working day for Define. Pick a later date or accept less time." North drafts a date only from a stated deadline in a document or the source intent | "Use this date" fills the field; mark `guessed` | creator | Hidden when North has nothing beyond the default |
| Default note | text | "10 working days is the default for an Initiative." | none | creator | Always shown |

### Screen B. "Here is what I understood" (same route, `step=review`)
**Layout at 1280.** One centred card, 720 px wide, with North's line above and the buttons below. The "So far" column is replaced by this card. **At 390.** The card fills the screen; buttons stack, primary first, 56 px tap height.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| North's lead line | agent line | "Here is what I understood. Check it, change anything that is wrong, then open it." | none | creator | Always shown |
| Summary text | panel | North's short written summary in four to six sentences: the goal and why, who is involved and affected, whether a build is likely, what definitions exist, the areas, the date. Every number in it comes from the answers or the look-up | none | creator | If North is off, the person writes it; field required |
| Answer rows | list | One row per question: question, the answer, a mark chip ("Stated by you" or "Guessed by North"), and "Change" | "Change" goes to that question, then returns here | creator | Rows are never empty: required answers block the review |
| Edit summary | link | "Edit the summary" | Opens the summary text as an editable field; saving marks the summary `stated` | creator | n/a |
| Title field | field (single line, 120 characters) | North's drafted title, editable | Saves on blur | creator | Starts filled; required |
| Handover preview | panel | "When you open this intent: the wall opens for N working days, to M people. Purpose line: ...". With the four lane names | none | creator | n/a |
| "That is right, open this intent" | button (primary) | Label; spinner while saving | Writes the intent as `open` (see States), creates the prepared wall (see Screen C and the Journey), lands on `/centre/intent/<id>`. Disabled while a required item is missing, with a line naming the first one | creator | Disabled until valid |
| "Change something" | button | Label | Focus moves to the first "Change" link | creator | n/a |
| "Save as draft and leave" | button | Label | Draft kept; goes to `/centre/intent` | creator | n/a |
| Open failure | alert | "Could not open this intent. Your draft is safe. Try again." with "Try again" | Repeats the open; a half-made wall is not left behind (see Rules) | creator | Shown on failure only |

### Screen C. The prepared wall hand-over card (on `/centre/intent/<id>`, first stage)
This is the Initiative's first-stage landing, built by spec 04 to 08 for the whole type. This spec fixes only what the hand-over puts on it.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Hand-over card | panel | "The wall is ready. Purpose: <goal line>. Open until <date> (3 working days). Lanes: Tracking today, Missing, Watch, Levers. Invited: 5 people." | none | organiser | n/a |
| "Open the wall" | button (primary) | Label | Starts the room (draft to lobby) and shows the join link through the invite panel. Until pressed the wall is a prepared draft nobody else can reach | organiser | Disabled with the line "Topic already has an open wall. Change the topic." when the wall rules refuse (see Rules) |
| "Change the wall setup" | link | Label | Opens the existing Prepare edit for this draft wall (purpose, window, seats, topic) | organiser | Hidden once the wall is open |
| Invite panel | panel | The existing `InvitePanel`: one line "N seats, M arrived", opens to the join link, "Copy link", and seats with "Take back" | As today | organiser | Hidden until the wall is open |
| Invitation drafts | list | One line per person named in question 2, "Janet has opened an Initiative and asked you to take part", with "Send" per line and "Send all" | Hands each line to the invitation flow of spec 06; North drafts, the organiser sends | organiser | "Nobody was named. You can invite people from the people panel." |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)
1. The person arrives from the tile, a draft or a follow-on. If a draft exists the screen resumes at the first unanswered question; otherwise the draft intent is written (state `draft`, type `initiative`).
2. **North reads what it can** before asking: the company profile as the person may see it, the interviews held, the uploaded documents (as short passages), and the source intent when `from` is set. It prepares drafts for each question and does not show any until its question is reached.
3. Question 1. North asks for the goal and the why. If a draft exists it offers it. The person types or uses the draft. North reads back one line. The person confirms.
4. **North runs the glossary and catalogue look-up** in the background as soon as the goal is saved (see Agent behaviour). It does not wait for question 4. Look-up results are stored as `outcome.definitions_found`.
5. Question 2. North offers sponsor, takers and affected as chips with reasons. The person picks, or presses "Just me for now". North reads back.
6. Question 3. North offers a leaning for the build with the reason from the look-up. The person picks yes, no or not sure. North reads back.
7. Question 4. North shows "What already exists" for each term. The person may remove a wrong term, mark a hit as not it, or add a term. The person picks yes, some or no. North reads back and says what Define will do.
8. Question 5. North suggests areas. The person picks at least one.
9. Question 6. North shows the default date and the split. The person keeps it or picks another date.
10. **North writes the summary** "Here is what I understood" and a drafted title. The person reads it, changes any answer or the summary, edits the title.
11. The person presses "That is right, open this intent". The route validates, writes the record, creates the wall draft through the existing Prepare route, and sets stage 1 `opened_at`. North posts the first line in the intent: "This intent is open. The wall is prepared. Decide by 24 Oct."
12. The person lands on the intent page, sees the hand-over card, and presses "Open the wall" when ready. The room starts and the join link appears in the invite panel.
13. **North drafts the invitations**, one per named person, and Nira puts "Janet has opened an Initiative and asked you to take part" under "what is waiting for you" for each only after the organiser sends it (spec 06). Nobody is invited without being named by the person.
14. Leaving halfway: every answer is saved on Next; "Save and leave" or closing the tab keeps the draft, visible to the creator only (ruling 14), as spec 03 describes.
15. The person leaves by opening the wall (`/centre/intent/<id>/wall`), by going to `/centre/intent`, or by closing the tab. The intent stays open and North keeps the clock (spec 07).

## States and transitions (table: state, who moves it, to what, what is written)
| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | The person picks the Initiative tile | draft | `intents/<id>/intent.json` with id, type `initiative`, company, created_by, created_at, state `draft` (spec 03) |
| draft, question N | The person presses Next | draft, question N+1 | The answer under `start_answers` and, once the review is confirmed, under `outcome` (see Fields). `draft_updated_at` |
| draft | North finishes the look-up | draft | `outcome.definitions_found` with counts (written to the draft, shown only to the creator) |
| draft | The person presses "That is right, open this intent" | open | `state: open`, `title`, `purpose` (= goal line), `areas`, `people`, `time_box.starts/ends`, `stages[0]` (Think unfiltered, `opened_at`, `ref`), `outcome.*` with marks, `outcome.start_summary` |
| open | The system, in the same request | open | Wall draft created by the existing create-draft route; its session id stored in `stages[0].ref` |
| wall draft | The organiser presses "Open the wall" | wall in lobby, intent `in_session` when the room is live (spec 01 rule) | Existing room start: join code, seats |
| draft | The person presses "Discard" in Your drafts | cancelled | Spec 03's rule: kept, with reason "Discarded by the organiser" |
| open, wall not started | The organiser changes the wall setup | open | Existing Prepare update of the draft wall; intent unchanged |

## Records read and written (file or route, fields; mark Existing or New)
| Item | Read or write | Fields | Status |
|---|---|---|---|
| `intents/<id>/intent.json` through `sh_platform/jsonfile.py` (`read_json_strict`, `write_json_atomic`, `lock_for`) | read, write | The intent record (brief section 3) plus the fields below | New file per intent, Existing helper |
| Company profile read: `sh_platform/profile/view.py` `read(plane, viewer)` | read | people (name, role, team, `is_sponsor`), areas, interviews, documents' short summaries, constraints, reported figures | Existing |
| `modules/m1_intent/domain/profile_draft.py` `build(profile, settings)` | read | The drafting pattern for Prepare values from the profile | Existing, reshaped (see Reuse check) |
| `GET /api/modules/m2_baseline/baselines/{id}/glossary` (`m2_baseline/api/glossary.py`, `read`) | read | Entries: term, definition status, owner, source; filtered by `ctx.sees` | Existing |
| `GET /api/modules/m2_baseline/baselines/{id}/technical` (`m2_baseline/api/technical.py`) | read | Technical definition state per measure | Existing |
| `GET /api/modules/m2_baseline/baselines/{id}/catalogue` (`m2_baseline/api/catalogue.py`, `read`) | read | Catalogue rows: measures, tables, fields, with source | Existing |
| `m2_baseline/domain/glossary.py` `code_matches`; `api/glossary.py` `_matcher` for the meaning match | read | Term to entry match by stems, then by meaning for terms code could not match | Existing |
| `POST /api/intents/<id>/definitions/check` | read, write to draft | In: terms. Out: per term `{term, kind, entry_ref, status}` and counts; stored as `definitions_found` | New |
| `POST /api/intents/<id>/messages` | write | One answer, North's draft and read-back for a start question (spec 03 shape) | New (spec 03) |
| `PATCH /api/intents/<id>` | write | Answers, areas, people, time box on the draft | New (spec 03) |
| `POST /api/intents/<id>/open` | write | Validation and the open write; calls the wall hand-over inside the same request | New (spec 03), extended here |
| `POST /api/modules/m1_intent/sessions` (`m1_intent/api/session.py` `create_draft`) | write | Preparation: `purpose`, `outcome`, `seats`, `topic`, `wall_window_days`, `drafted: true` | Existing |
| `POST /api/modules/m1_intent/sessions/{id}/start`, `GET .../join-link`, `POST .../link` (same prefix) | write, read | Room start, join code, current link | Existing |
| `modules/m1_intent/contracts/initiative_start.yaml` | read | The six question keys, wording, required flags, default 10 working days, stage split 3/6/1: exactly the canonical table above. The file does not exist yet (path checked 7 October 2026) | New contract file, small |
| `modules/m1_intent/manifest.yaml` | write | Declares the new routes (the `/api/intents/...` calls and the page route) | Existing file, new entries |

## Fields this feature adds to the intent record
Every answer cell has the shape `{value, mark, by, from, at}`. `mark` is `stated` when the person typed or chose it; `guessed` when North drafted it and the person kept it unchanged, or when the person answered "Not sure". Editing a draft changes the mark to `stated`. `by` is the person's name for stated and `North` for guessed; `from` names the source ("The profile", "Interview with Daniel", "The document Q3 reporting notes", "Look-up of the baseline glossary"). Nothing here is written to the company profile; the profile is read only.

| Field | Meaning |
|---|---|
| `purpose` | The goal line (existing brief field, written from question 1) |
| `outcome.goal` | `{line, why, mark, by, from, at}`. Line up to 140 characters, why up to 600 |
| `outcome.build_needed` | `{value: yes|no|not_sure, note, mark, by, from, at}` |
| `outcome.definitions_exist` | `{value: yes|some|no|not_checked, mark, by, from, at}` |
| `outcome.definitions_found` | `[{term, kind: glossary|technical|catalogue, entry_ref, status: signed|draft|provided, rejected: bool}]` and `counts: {terms, business, technical, catalogue}`. Refs, never copies of the entries (brief section 3) |
| `outcome.start_summary` | `{text, mark, confirmed_by, confirmed_at}`: North's "Here is what I understood" as edited and confirmed |
| `outcome.people_note` | `{just_me: bool, not_listed: [text]}` |
| `outcome.decide_by` | `{date, working_days, mark, by, from, at}`; also copied into `time_box.ends` |
| `stages[0].ref` | `{kind: "wall_session", id}`: the session id of the prepared wall. The wall stays in `modules/m1_intent`; the intent only points at it |
| `start_answers` | Draft-only map keyed `goal`, `people`, `build`, `definitions`, `areas`, `deadline`: the raw answer cells while the intent is `draft` |
| `draft_updated_at` | Time of the last saved answer, in the company's time zone from the profile, else UTC |
| `affected_may_read` | Boolean, default false: affected people may read the content (ruling 4). Name proposed here (Open questions 11) |
| `outcome` | An object from the moment the draft is written, never null (ruling 6): `{}` at creation, filled as answers are saved |
| `people: {organiser, sponsor|null, decider|null, owner|null, reporter|null, participants: [], advisers: [], affected: [], observers: []}` | People slots per ruling 21. Written from question 2: `sponsor`, `participants`, `affected` (existing brief fields) |
| `areas` | Written from question 5 (existing brief field) |

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)
- **North asks.** The six questions in the order above, one at a time, wording from `initiative_start.yaml`. After each answer it reads back one line; the person confirms or corrects.
- **North drafts, per question, from what exists:**
  - Q1: a goal line and why from the source intent (when `from` is set), from interviews of the organiser, and from document passages. It names its source.
  - Q2: sponsor, takers and affected from the profile people list and teams, the interviews, and the people named in documents.
  - Q3: a leaning on the build from the Q4 look-up counts and from whether the data's system is known in the profile. A leaning, never a decision.
  - Q4: the terms (nouns and measures in the goal), then the look-up (below), then a leaning for the choice.
  - Q5: areas from the teams chosen and the areas named in documents.
  - Q6: the default date; a different date only from a stated deadline in a document or the source intent.
- **North's look-up (Q4).** It takes the terms and looks them up in the company's baseline glossary, technical definitions and catalogue by the existing stem matcher, and by meaning (through the egress gateway, names tokenised) for terms code cannot match. It reports counts and entry names the person may see. A result below five rows in a group is shown in full as names of entries, not figures (the entries are the company's own, and the guard on counts applies to numbers about people). It never reads a restricted or sealed entry into a draft for someone who may not see it.
- **North writes** the summary and the drafted title, and the prepared wall: purpose line from the goal line, outcome text from the why (trimmed to the Prepare limit), wall window, topic from the first area, and at most three suggestion cards per lane drawn from the goal, the matched entries and the documents, each marked "Suggested by North, from <source>". Suggestions become cards only when someone picks them up (v1 rule).
- **North drafts invitations**, one per named person. It does not send them. The organiser sends; Nira then lists them under "what is waiting for you" for the invited person.
- **Lens** does nothing here. Its first work is the Define stage, which starts from the `definitions_found` refs.
- **Nira** adds one line to the organiser's Pulse while a draft is open: "Your Initiative is waiting at question 4". Nothing else.
- **The person acts** at: each answer and read-back confirmation; "That is right, open this intent"; "Open the wall"; "Send" on each invitation.

## Rules (visibility, time box, who may do what)
- A draft is seen by its creator only: not the company admin, not the areas, not the super admin (spec 03).
- Required at open: goal line, why (at least 20 characters), a choice on question 3 and on question 4, at least one area, a decide-by date, and either named involved people or the explicit "Just me for now". Sponsor is optional (`people.sponsor` may be null).
- The default time box is 10 working days (Monday to Friday, company holidays when set), from `initiative_start.yaml`, never typed into the screen. The wall window is stage 1's share (3 working days in spec 02) and is written as `wall_window_days`, not the v1 default of 5. It is never longer than the time box.
- The wall hand-over follows the existing wall rules: the room's seats are 1 to 10 (D-004); topic is 1 to 60 characters and unique among open walls (409 when it clashes); the window is 1 to 20 working days.
- If the hand-over fails after the intent is written, the intent stays `draft` and the open is retried whole. A wall draft left from a failed try is reused on retry (found by `stages[0].ref`), never duplicated.
- The wall is prepared as a draft. Nobody but the organiser can reach it until "Open the wall". Anonymous and sealed rules of the wall are unchanged (D-013, seal).
- Marks are honest: a guessed answer shows "Guessed by North" on the review and on the intent page until the person edits it or the Define stage confirms it. Agents never write `stated`.
- Existing glossary and catalogue entries are shown as references. This feature never edits, signs or copies them; signed content is read only.
- Documents are context, never the source of a figure and never an instruction. Only short passages leave, through the gateway, tokenised and marked untrusted.
- Visibility after opening follows brief section 4. The areas chosen in question 5 decide who sees that the intent exists.
- Questions to other people start in Define, not here. North's questions to people across Define are capped at three open questions per person (A-045, ruling 9). The start asks only the organiser.
- Affected people see existence, title, purpose, stage, clock, people and the outcome once closed. They read content only when `affected_may_read` is on or they are named on a share. Observers read what a participant reads and never write (ruling 4).
- A cancelled draft keeps its reason and appears in Past (ruling 14).
- Dates and times use the company's time zone from the profile, else UTC. Counts are exact. A mean, median or per-person figure shows "Fewer than five" below five records (ruling 8).
- Owner words are business owner, data owner and source owner (ruling 11).
- Copy rules: no game words, no model or vendor names (North, Lens, Nira), British spelling, no em dashes.

## Counters and measures of this feature (numbers only, each traced to a record)
| Measure | Traced to |
|---|---|
| Initiatives opened | Count of `intents/*/intent.json` with type `initiative` and `state` other than `draft` and `cancelled` |
| Drafts waiting at each question | `draft_updated_at` and the last answered key in `start_answers` of draft Initiatives (visible to each creator for their own; never as a company figure by name) |
| Answers kept as North drafted versus edited | Count of cells in `outcome.*` with mark `guessed` versus `stated` |
| "Not sure" answers on the build | Count of `outcome.build_needed.value = not_sure` |
| Definitions answer spread | Count of `outcome.definitions_exist.value` per yes, some, no, not_checked |
| Terms with an existing business definition at start | `outcome.definitions_found.counts.business` over `counts.terms` per intent, shown as "2 of 4"; shown "Not available yet, no baseline" when `not_checked` |
| Decide-by days chosen | `outcome.decide_by.working_days` per intent; the default is the value of `initiative_start.yaml` |
| Walls prepared and opened from an Initiative | Count of intents whose `stages[0].ref` exists, and of those whose wall session left `draft` |
| Invitations drafted and sent | Count of invitation lines from the hand-over card and those the organiser sent (spec 06 records) |

Numbers shown on the screens of this feature and where each is read from:

| Number on screen | Read from |
|---|---|
| "86 of 140" characters | The text typed in the field; the limit is Open questions 12 |
| "Question N of 6" | The index in the canonical table |
| "3 of the 4 terms ... not in the catalogue", "2 of 4 terms have a business definition" | `outcome.definitions_found.counts` of this draft; "Not available yet, no baseline exists" when `not_checked` |
| "That is N working days" and the stage split | The decide-by date against the company calendar and `initiative_start.yaml`; split rule is Open questions 4 |
| "Invited: M people", "N seats, M arrived" | `people.participants` of this intent; the wall session's seats and arrivals (Existing, `InvitePanel`) |
| "A usual Initiative takes 10 working days" | The default in `initiative_start.yaml` (brief section 2) |

Counters are numbers only (A-057). No answer text is counted or shown company-wide.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)
Line ranges are as read on 7 October 2026 from the working tree.

| Existing | Where | Decision |
|---|---|---|
| Prepare: create a wall draft from `purpose`, `outcome`, `seats`, `topic`, `wall_window_days`, `drafted` | `modules/m1_intent/api/session.py` L77-L102 (`create_draft`), L32-L47 (`_prepare`, `_profile_draft`); `domain/preparation.py` L25-L62 (defaults), L81-L139 (`clean`), TOPIC_MAX and WALL_DAYS_MAX near L28-L31 | **Reused as is.** The hand-over calls the existing route; no second Prepare is built |
| Prepare drafted from the profile, as the viewer may see it | `modules/m1_intent/domain/profile_draft.py` L43 (`build`) | **Reshaped:** the same idea (draft from the viewer's profile, restricted items already out) for the six questions; the profile read is `sh_platform/profile/view.py` `read` L116, `sees_area` L79 |
| Room start, join code, join link | `modules/m1_intent/api/room.py` L185-L192 (`start_room`), L195-L202 (`new_link`), L205-L218 (`current_link`) | **Reused as is** behind "Open the wall" |
| The briefing (purpose and outcome as the wall shows them to people who join) | `modules/m1_intent/api/briefing.py` L193-L238 (`_briefing_view`, `get_briefing`, `confirm`); timer L410-L430 | **Reused as is.** It shows `preparation.purpose` and `outcome`, so the goal and why must populate them. Not rebuilt |
| Invite panel (join link, copy, seats, take back) | `ui/src/modules/m1_intent/wall/InvitePanel.tsx` L1-L70 | **Reused as is** on the intent's first stage. Named invitations come from spec 06; this panel only holds the link and seats |
| Wall questions, lanes and the three-suggestions rule | `modules/m1_intent/contracts/wall_questions.yaml`; `docs/specs/INTENT-CENTRE-SPEC.md` section 3 | **Not changed.** Referenced for the lanes and for North's suggestion cards |
| Private room conversation components (transcript, bubbles, composer, voice bar) | `ui/src/modules/m1_intent/private_room/` (named by spec 03) | **Reused** through spec 03's thin hook; Screen A is that conversation with the help panel added |
| Glossary read and lookup | `modules/m2_baseline/api/glossary.py` L80-L96 (`_screen`, `read`), `_matcher` L53-L70; `domain/glossary.py` L161-L181 (`code_matches`) | **Reused:** the check calls the same functions in process, with the same `ctx.sees` filter. A thin new route wraps them |
| Technical definitions read | `modules/m2_baseline/api/technical.py` L73-L97 (`screen`, `get_technical`) | **Reused** read only |
| Catalogue read | `modules/m2_baseline/api/catalogue.py` L73-L80 (`read`); store `modules/m2_baseline/store/kpis.py` L14 (`read_kpis`) | **Reused** read only |
| Provenance marks `stated`, `guessed` with `by`, `from` | `sh_platform/profile/cards.py` L36-L50; `profile/links.py` | **Reshaped:** the same mark vocabulary on the intent's answer cells. The intent does not write to the profile |
| Intent file helper | `sh_platform/jsonfile.py` L19-L41 | **Reused** |

Genuinely new: `initiative_start.yaml`; the definitions check route and its screen panel; the summary card text; the wall hand-over route inside `POST /api/intents/<id>/open`; the `outcome.initiative` fields. Searches run: "prepare", "preparation", "rooms/open", "briefing", "InvitePanel", "glossary", "catalogue", "code_matches" across `modules/`, `ui/src` and `sh_platform`. There is no route named `rooms/open`; the Prepare step and room opening are `POST /api/modules/m1_intent/sessions` and `.../sessions/{id}/start`.

## Not in this feature
- The chooser and the other types' start questions (spec 03 and 04 to 08).
- Inviting people by name, invitation emails and Pulse lines (spec 06). This spec supplies the names and the wall link.
- The wall screens, Define, the charter and the Build-ready check; the stage clock and the extend dialog (spec 07).
- Editing or signing glossary or catalogue entries (m2_baseline). The start only looks and links.
- Gap analysis: room 0 of the Build centre at `/centre/build/gap-analysis?from=<id>`, the built `modules/m3_connect` moved, not rebuilt (ruling 10; request A-075). Also any build decision. Question 3 records an opinion, not a plan.
- Writing the start answers to the company profile.

## Open questions
1. Spec 03 lists different Initiative start questions (sponsor, build, definitions, affected) and separate areas, people and time steps. This spec replaces them with Nitin's six questions and folds people, areas and the date into them. Spec 03's stepper for Initiative should read "Goal, People, Build, Definitions, Areas, Deadline, Review". Confirm and align.
2. Which baseline does the check read: the latest signed one, or the latest in progress? A company may have none. Proposal: latest signed, else latest draft, else "No baseline exists yet".
3. Is a sponsor required to open? Brief section 3 allows `sponsor: null`; spec 03 made it required. This spec makes it optional and asks North to nudge.
4. A decide-by date other than 10 working days: how do the three stage shares scale? This spec shows a proposed split and lets the person keep it; the rule (whole days, minimum one per stage) needs Nitin's word.
5. A minimum date: is "decide by" allowed tomorrow? No minimum is invented here.
6. The wall's seat limit is 10 (D-004). If Question 2 names more than nine takers, North should say so and ask who joins the wall and who is only informed. Confirm this wording.
7. Mark rule: a North draft kept unedited stays `guessed` even though a person read it. Is that the intended reading, or should confirmation by the person turn it to `stated`?
8. Topic for the wall: first area name, or a separate field? Proposal: first area, editable in "Change the wall setup".
9. Terms extraction: North proposes terms from the goal; is a cap needed (proposal: eight terms) to keep the look-up and the screen short?
10. The draft resume route `?draft=<id>` is not in ruling 1's list. Proposal: a query parameter on `/centre/intent/new`, no new path. Confirm.
11. Which spec owns `affected_may_read` and its field name (05 or this file)? Proposal: this file writes it from question 2; 05 owns the meaning.
12. Limits not given by the brief and chosen here: goal line 140 characters, why up to 600 and at least 20, title 120, at most three suggestion cards per lane (v1 rule, kept), a wall window of 3 working days. Confirm or replace.
13. Spec 02 still lists eight Initiative start questions and spec 03 another set. Ruling 2 makes the canonical table above the source; `intent_types.yaml` should reference `initiative_start.yaml`. "What will tell us it worked" is dropped and sponsor and helpers fold into question 2. Nitin to confirm.
