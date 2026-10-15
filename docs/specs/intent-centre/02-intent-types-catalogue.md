# 02. Intent types catalogue

Part of: Intent Centre v2. Depends on: 00-BRIEF (intent record, visibility rule, section 10 rulings). Feeds: 03 (chooser frame), 22, 35, 38, 41, 43 (per-type start questions), the per-type workflow specs, 33 (Build hand-off), 12, 20, 21.

## Purpose (three sentences)

The catalogue is the single list of the five intent types: Initiative, Brainstorm, Weekly check-in (record key `pulse`), Problem and Decision. For each type it fixes the start questions North asks, the stages and their default days, who must be in it, the outcome record, what "closed" requires, and which other types it can link to. It lives in one contract file, `modules/m1_intent/contracts/intent_types.yaml`, so no screen or agent holds a list of types, questions or stage times in code. The wording, order, required flags and field names of the start questions are copied from the per-type files 22, 35, 38, 41 and 43, which are canonical (brief section 10, ruling 2).

Gap analysis is room 0 of the Build centre (`/centre/build/gap-analysis?from=<id>`, ruling 10). It is not an Intent stage of any type. An Initiative ends at the Build-ready check and hands a build-ready charter to Build.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Any signed-in person (becomes organiser) | Answers "What do you want to do?" | Clicks one of five type cards |
| North (agent) | Reads the catalogue to ask start questions, build the stage list, set the clock, check people, draft the closure | A type is chosen; each stage opens and closes; closure |
| Company admin | Sees the catalogue as the list of types the company runs; changes nothing this round | Settings, "Intent types" (read only) |
| Reviewer, builder | Reads the YAML as the contract | Package brief |

People act at named moments: choosing the type, answering the questions, naming people, opening, closing. Agents draft and keep the clock. They never sign, decide or close.

## Entry points (every route, link, Pulse line, button that leads here)

- `/centre/intent` (home): button "Start something" opens `/centre/intent/new`.
- `/centre/intent/new` (chooser, "What do you want to do?"): five cards, one per type, each with its `chooser_line`.
- `/centre/intent/new?type=<type>&from=<id>`: start questions of one type, optionally from a source intent.
- Pulse line from Nira: "Start a Problem from this item" (from a check-in item), "Start an Initiative from this idea" (from a Brainstorm or Problem closure).
- Closure screen, "What happens next": buttons "Start an Initiative", "Add to backlog", "Start a Problem", "Start a Decision", "Nothing, and why". Each reads `can_become` or `can_create` from the catalogue.
- Read only: `GET /api/intents/types` returns the catalogue (no company data; the same for every company).

## Screens, element by element

This feature owns no new screen. It supplies the content of the chooser (frame owned by 03) and of the start questions (owned by 22, 35, 38, 41, 43).

### Screen A. Chooser

Route: `/centre/intent/new`. Layout at 1280: heading `chooser_heading`, five type cards in one row, a "What you will get" panel under the focused card. At 390: cards stack one per row; the panel opens as a bottom sheet from "What you will get".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Type card | button | `title` and `chooser_line` of the type | Opens `/centre/intent/new?type=<type>` | Everyone signed in | "The list of things you can start is not available yet. Ask your company admin." |
| Time box chip | chip | `time_box_days` read from the catalogue, "10 working days" | None | Everyone | Never empty |
| Who is in it chip | chip | `people.required_slots` and counts from the catalogue, "Organiser, and four to eight people" | None | Everyone | Never empty |
| What you will get panel | panel | `outcome.kind` in plain words and the `stages` list with `default_days` | None | Everyone | Never empty |
| "Your drafts" link | link | Count of the viewer's own `draft` intents, read from `intents/*/intent.json` | Opens the drafts list on `/centre/intent` | The person themselves | "Not available yet: you have no drafts." |

### Screen B. Start questions

Route: `/centre/intent/new?type=<type>`. Layout at 1280: question column on the left two thirds, "So far" card on the right third. At 390: one question per page; "So far" is a bar "Question 3 of 5" that opens as a sheet. Frame (stepper, read-back, "Save and leave") is 03's; per-question controls are in the per-type file. The catalogue supplies:

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Question line | agent line | `lead` of the question, in `order` | None | Organiser | Never empty |
| Answer fields | field | `fields` of the question | Saves the answer to the draft; "Next" | Organiser | A required question blocks "Next" with a line naming it |
| Choice control | field | `choices` of the question, where listed | Select; saves on "Next" | Organiser | As the question's `required` |
| Unknown option | chip | `unknown_label` ("Just me for now", "Not sure", "I do not know"), on questions that list one | Records the answer as `unknown`, a valid answer | Organiser | Not shown where the question lists none |
| Open button | button | `open_button` of the type | Creates state `open`, writes `stages` and `time_box` from the catalogue (`POST /api/intents/<id>/open`) | Organiser | Disabled until every required question is valid, with a line naming the first missing one |
| "Save and leave" | button | Label | Draft kept, visible to its creator only (ruling 14) | Organiser | n/a |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. The person opens `/centre/intent/new`. The page loads `GET /api/intents/types` and shows five cards.
2. The person clicks a card. North reads that type's `start_questions`.
3. North asks each question in `order`, one at a time, with the exact wording in the YAML. The person answers; North reads back one line. Required questions cannot be skipped.
4. After the last question North drafts title, purpose, areas and time box from the answers. The person edits or confirms.
5. North checks the type's `people` rules and names any missing role. The person names someone, or fixes the count.
6. The person clicks the type's `open_button`. North writes `intents/<id>/intent.json` with `catalogue_version`, `start_answers`, `stages`, `time_box` and an `outcome` object, and drafts the invitations.
7. The type's workflow screens take over. When the last stage ends North drafts the closure; the named closer confirms (see Rules). The person leaves to the intent screen.

## States and transitions (table: state, who moves it, to what, what is written)

The states are the brief's six. The catalogue adds what "closed" requires per type.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| `draft` | Organiser clicks the type's `open_button` | `open` | `stages`, `time_box.starts` and `ends`, `people`, `areas`, `outcome` object |
| `open` | North opens stage 1; for Brainstorm the clock opens the live session | `in_session` or stays `open` | `stages[0].opened_at` |
| `open` or `in_session` | Last stage ends, or the organiser asks to close | `closing` | North writes the `closure` draft |
| `closing` | The `closure.closer` of the type confirms | `closed` | `closure.closed_by`, `closed_at`, `next` |
| any before `closed` | Organiser cancels with a reason | `cancelled` | `closure.cancel_reason`; shown in Past (ruling 14) |
| any open state | Organiser, on North's proposal, extends | same state | `time_box.extended_by` |

A Weekly check-in series stays `open` while it runs; each week has its own state in `intents/<id>/weeks/<week_key>.json` (file 38). North reads `time_box.ends`; when the clock will not hold it proposes extend, close with what we have, or cancel, and the named closer picks.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Mode | Fields | Mark |
|---|---|---|---|
| `modules/m1_intent/contracts/intent_types.yaml` | read | whole catalogue | New |
| `GET /api/intents/types` | read | catalogue as JSON | New |
| `intents/<id>/intent.json` via `sh_platform/jsonfile.py` | write | brief section 3 record plus fields below | New file, Existing helper |
| `intents/<id>/weeks/<week_key>.json` | write (file 38) | one week of a check-in series | New |
| `intents/<id>/events.jsonl` | write (file 16) | events; the record holds counts only (ruling 12) | New |
| `modules/m1_intent/contracts/intent_session.yaml` | read | `seats`, `time_presets_minutes`, `warning_seconds`, wall window | Existing |
| `modules/m1_intent/contracts/wall_questions.yaml` | read | four wall questions (Initiative stage 1) | Existing |
| `modules/m1_intent/contracts/interview_notes.yaml` | read | note drafts from an interview | Existing |
| `modules/m1_intent/contracts/outcome.yaml` | read | charter outcome shape | Existing |

### The five types

Wording and flags below equal the YAML. R means required.

**Initiative (file 22).** Chooser line and time box: 10 working days. Questions: 1 "What are you trying to achieve?" (goal line, why) R. 2 "Whom do you need to involve, and who is affected?" R (named people, or "Just me for now"; sponsor optional). 3 "Do you think this needs a build (new data, pipelines, reports)?" R (yes, no, not sure). 4 "Do we already have a business glossary and technical definitions for this, or will we discover them along the way?" R (yes, some, no). 5 "Which areas does this touch?" R. 6 "When must this be decided by?" R (prefilled). Stages: Think unfiltered 3, Define strategically 6, Build-ready 1 (a check, not a room). People: organiser; sponsor optional. Outcome: refs to charter, glossaries, catalogue, process map, data sources, `build_ready`, `build_ready_gaps`, `handoff`. Closer: organiser, with sponsor's confirmation required. Closed requires a charter signed by a named person.

**Brainstorm (file 35).** 3 working days. Questions: 1 "What is the idea or the problem you want to think about?" R. 2 "What would a good outcome look like when the session is over?" R. 3 "Who should think with you? Pick four to eight people." R. 4 "Which parts of the company does this touch?" R. 5 "When is the live session?" R (date, time, 45 or 60 minutes). Stages: Think alone 1, Live session 1, Choose 1. Outcome: `chosen`, `ideas_kept`, `dropped`. Closer: organiser.

**Weekly check-in (file 38).** One week, recurring. Questions: 1 "Which ops area is this for?" R. 2 "Who reports each week?" R (at least two). 3 "Which day does the week close?" with "Who reviews the week and decides what happens to each item?" R (defaults Friday and the organiser). 4 "What each person answers each week" (three fixed prompts, one optional own question), not required. Stages of a week: Collect 3, Review 1, Sort 1. Item kinds `ran`, `broke`, `thought`. Fates `problem`, `backlog`, `handled`, `nothing`, each with a reason. Every `broke` item needs a fate before the week closes; `ran` and `thought` items left undecided close as `nothing` with the reason "Not reviewed this week". A new week opens by the clock on the next working day after the close day, even if the review is unfinished. Series and weeks are not rated.

**Problem (file 41).** 5 working days. Questions: 1 "What is wrong?" (one line `what`, and what you saw) R. 2 "Which process or measure is it about?" not required ("Not sure"). 3 "How hard does it bite?" R (slowed, stopped, cost money; count and amount optional). 4 "Who do you think owns it?" not required ("I do not know"). 5 "Which areas are affected?" R, with at least one named person who feels it. Stages: Describe 1, Find the cause 2, Fix 1, Confirm 1. People: reporter (the organiser), owner (proposed, accepted in triage), affected. Closer: organiser, with owner's and reporter's confirmation required.

**Decision (file 43).** 2 working days. Questions: 1 "What must be decided?" R. 2 "By when?" R (default two working days). 3 "Who decides?" R. 4 "Whose advice do you want?" not required (up to five). 5 "Which areas does it affect?" R. Stages: Set out the options 1, Decide and record 1. People: decider, organiser (may be the same person), advisers. Closer: organiser, with decider's confirmation required. A Decision may link to any type as source or target (ruling 7).

### YAML contract proposal

Proposed file: `modules/m1_intent/contracts/intent_types.yaml`. Values marked "chosen" were not given by the brief or a per-type file: placeholders for Nitin to confirm.

```yaml
# Intent types (Intent Centre v2, spec 02). Chooser, start flow and North read every list from here.
# Start questions equal files 22, 35, 38, 41, 43 (ruling 2). Gap analysis is not a stage of any type (ruling 10).
version: 1
working_days: mon-fri        # company time zone from the profile, else UTC; holidays when the profile sets them
chooser_heading: "What do you want to do?"
types:
  initiative:
    title: "Initiative"
    chooser_line: "Run a project or a new initiative, from the first idea to a plan that Build can pick up."
    open_button: "That is right, open this intent"
    time_box_days: 10
    people: {slots: [organiser, sponsor, participants, affected], required_slots: [organiser], sponsor_optional: true}
    start_questions:
      - {id: i1, lead: "What are you trying to achieve?", required: true, fields: [goal_line, why], fills: [title, purpose, outcome.goal]}
      - {id: i2, lead: "Whom do you need to involve, and who is affected?", required: true, fields: [sponsor, involve, affected], unknown_label: "Just me for now", fills: [people.sponsor, people.participants, people.affected]}
      - {id: i3, lead: "Do you think this needs a build (new data, pipelines, reports)?", required: true, choices: [yes, no, not_sure], fills: [outcome.build_needed]}
      - {id: i4, lead: "Do we already have a business glossary and technical definitions for this, or will we discover them along the way?", required: true, choices: [yes, some, no], fills: [outcome.definitions_exist]}
      - {id: i5, lead: "Which areas does this touch?", required: true, fills: [areas]}
      - {id: i6, lead: "When must this be decided by?", required: true, default: "time_box_days from today", fills: [time_box.ends, outcome.decide_by]}
    stages:
      - {key: think_unfiltered, name: "Think unfiltered", default_days: 3, reuses: "m1_intent wall (intent_session.yaml, wall_questions.yaml)"}
      - {key: define_strategically, name: "Define strategically", default_days: 6, reuses: "m1_intent Define"}
      - {key: build_ready, name: "Build-ready", default_days: 1, kind: check}
    outcome:
      kind: initiative
      fields: [goal, why, build_needed, definitions_exist, build_ready]
    closure: {closer: organiser, closer_confirms: sponsor, requires: [signed_charter, build_ready_set, next_filled]}
    can_become: [build]
    can_create: [problem, decision]
    can_come_from: [brainstorm, problem, decision]
  brainstorm:
    title: "Brainstorm"
    chooser_line: "Think with five to nine people to find one idea or one answer."
    open_button: "Open this brainstorm"
    time_box_days: 3
    people: {slots: [organiser, participants, observers], required_slots: [organiser], participants_min: 4, participants_max: 8}
    start_questions:
      - {id: b1, lead: "What is the idea or the problem you want to think about?", required: true, fields: [statement, context], fills: [title, purpose, outcome.statement, outcome.context]}
      - {id: b2, lead: "What would a good outcome look like when the session is over?", required: true, fills: [outcome.good_outcome]}
      - {id: b3, lead: "Who should think with you? Pick four to eight people.", required: true, fills: [people.participants]}
      - {id: b4, lead: "Which parts of the company does this touch?", required: true, fills: [areas]}
      - {id: b5, lead: "When is the live session?", required: true, fields: [session_at, session_minutes], choices: [45, 60], fills: [outcome.session_at, outcome.session_minutes, time_box]}
    stages:
      - {key: think_alone, name: "Think alone", default_days: 1}
      - {key: live_session, name: "Live session", default_days: 1, live: true}
      - {key: choose, name: "Choose", default_days: 1}
    outcome: {kind: brainstorm, fields: [statement, good_outcome, session_at, chosen, backed, runners_up, ideas_kept, dropped]}
    closure: {closer: organiser, closer_confirms: null, requires: [one_chosen_with_reason, next_filled]}
    can_become: [initiative, backlog]
    can_create: [decision]
    can_come_from: [pulse, problem, decision]
  pulse:                                 # shown as "Weekly check-in"; "Pulse" alone is the daily page
    title: "Weekly check-in"
    chooser_line: "Collect what ran, what broke and what is on people's minds in one ops area, every week."
    open_button: "Start the check-in"
    time_box_days: 5                     # one week; a new week opens by the clock on the next working day after the close day
    recurring: weekly
    rated: false                         # series and weeks are not rated
    people: {slots: [organiser, participants], required_slots: [organiser], participants_min: 2}   # participants_min chosen
    start_questions:
      - {id: p1, lead: "Which ops area is this for?", required: true, fills: [areas]}
      - {id: p2, lead: "Who reports each week?", required: true, fills: [people.participants]}
      - {id: p3, lead: "Which day does the week close?", required: true, fields: [close_day, reviewer], default: {close_day: fri, reviewer: organiser}, fills: [series.close_day, series.reviewer]}
      - {id: p4, lead: "What each person answers each week", required: false, fields: [extra_prompt], fills: [series.extra_prompt]}
    weekly_prompts:
      - {id: w1, kind: ran, lead: "What ran well this week?"}
      - {id: w2, kind: broke, lead: "What broke or nearly broke?"}
      - {id: w3, kind: thought, lead: "What is on your mind?"}
    stages:
      - {key: collect, name: "Collect", default_days: 3}
      - {key: review, name: "Review", default_days: 1}
      - {key: sort, name: "Sort", default_days: 1}
    outcome:                             # an object from open (ruling 6); the series holds the week list, each week holds its items
      kind: pulse
      fields: [weeks]
      week_fields: [week_key, opens, closes, state, items, review, closed_at]
      item_fields: [id, by_or_anonymous, kind, text, severity, count, amount, ref, fate, fate_reason, decided_by]
      item_kinds: [ran, broke, thought]
      fates: [problem, backlog, handled, nothing]
      week_close: {closer: reviewer, requires: [every_broke_item_has_fate_and_reason], undecided_ran_thought: {fate: nothing, reason: "Not reviewed this week"}}
    closure: {closer: organiser, closer_confirms: null, requires: [series_ended_with_reason]}
    can_become: []
    can_create: [problem, backlog]
    can_come_from: [decision]
  problem:
    title: "Problem"
    chooser_line: "Something is wrong in operations. Give it an owner and a fix."
    open_button: "Open this problem"
    time_box_days: 5
    people: {slots: [organiser, reporter, owner, affected], required_slots: [reporter], affected_min: 1}   # reporter is the organiser; owner accepted in triage
    start_questions:
      - {id: r1, lead: "What is wrong?", required: true, fields: [what, saw], fills: [title, purpose, outcome.what, outcome.saw]}
      - {id: r2, lead: "Which process or measure is it about?", required: false, unknown_label: "Not sure", fills: [outcome.about]}
      - {id: r3, lead: "How hard does it bite?", required: true, choices: [slowed, stopped, cost_money], fields: [count, amount], fills: [outcome.bites]}
      - {id: r4, lead: "Who do you think owns it?", required: false, unknown_label: "I do not know", fills: [people.owner]}
      - {id: r5, lead: "Which areas are affected?", required: true, fields: [areas, who_feels_it], fills: [areas, people.affected]}
    stages:
      - {key: describe, name: "Describe", default_days: 1}
      - {key: find_cause, name: "Find the cause", default_days: 2}
      - {key: fix, name: "Fix", default_days: 1}
      - {key: confirm, name: "Confirm", default_days: 1}
    outcome: {kind: problem, fields: [what, saw, bites, count, amount, owner_accepted_at, root_cause, fix]}
    closure: {closer: organiser, closer_confirms: [owner, reporter], requires: [root_cause, fix_with_named_doer, reporter_confirmed_or_accepted_by_name]}
    can_become: [initiative]
    can_create: [decision]
    can_come_from: [pulse, decision]
  decision:
    title: "Decision"
    chooser_line: "Make one decision and keep the options and the reasons."
    open_button: "Open this decision"
    time_box_days: 2
    people: {slots: [organiser, decider, advisers], required_slots: [organiser, decider], advisers_max: 5}   # decider may be the organiser; zero advisers allowed
    start_questions:
      - {id: d1, lead: "What must be decided?", required: true, fills: [title, purpose, outcome.question]}
      - {id: d2, lead: "By when?", required: true, default: "time_box_days from today", fills: [time_box.ends]}
      - {id: d3, lead: "Who decides?", required: true, default: "sponsor", fills: [people.decider]}
      - {id: d4, lead: "Whose advice do you want?", required: false, fills: [people.advisers]}
      - {id: d5, lead: "Which areas does it affect?", required: true, fills: [areas]}
    stages:
      - {key: options, name: "Set out the options", default_days: 1}
      - {key: decide, name: "Decide and record", default_days: 1}
    outcome: {kind: decision, fields: [question, options, chosen, why]}
    closure: {closer: organiser, closer_confirms: decider, requires: [chosen_or_no_decision_reason, decider_named, reason]}
    can_become: [initiative, brainstorm, pulse, problem, decision]   # ruling 7: any type, as source or target
    can_create: [initiative, brainstorm, pulse, problem, decision]
    can_come_from: [initiative, brainstorm, pulse, problem, decision]
closure_common:
  requires: [why_it_happened, what_came_out, next_one_or_more]
  next_kinds: [initiative, problem, decision, backlog, handled, nothing]    # nothing needs a reason
```

Checks the build must hold: stage `default_days` sum to `time_box_days` (10, 3, 5, 5, 2); every `fills` target is a field of the intent record, `outcome`, `series` or `time_box`; question wording, order, `required` and field names equal files 22, 35, 38, 41, 43; no stage is called gap analysis; every type's `outcome` is an object from open, never null.

## Fields this feature adds to the intent record

- `catalogue_version`: the version of `intent_types.yaml` the intent opened under, so a later change does not alter a running intent.
- `start_answers`: `[{id, answer, mark: stated|guessed|unknown}]`, the answers in order.
- `stages[].default_days` and `stages[].days_used`: copied at opening; `days_used` filled at stage close.
- `outcome.kind`: equal to the type.
- `people.decider` (Decision), `people.owner` and `people.reporter` (Problem): named slots (ruling 13). `people.sponsor` stays optional.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** drafts the intent title, purpose and areas from the start answers; the stage list; the invitation text; the closure. It asks the missing question, keeps the clock and nudges the person whose turn it is. The person acts: answers, names people, opens, closes.
- **Lens** drafts definitions inside the Initiative's Define strategically stage. In the other types it acts only when a Problem or Decision names an undefined term; a person confirms.
- **Nira** reads `closure.next` and check-in item fates and shows the Pulse lines under Entry points. It drafts the line; the person decides to start the linked intent.
- No agent signs, confirms a decision or closes an intent.

## Rules (visibility, time box, who may do what)

- Visibility follows brief section 4 and rulings 4 and 5: areas see that the intent exists; participants and, where the organiser switched it on, affected people open content; observers read what participants read; super admin sees existence only; company admin sees existence and outcome, never anonymous notes; a share link is explicit and per intent. A draft is visible only to its creator.
- Time box is the sum of the stage defaults. The organiser may shorten a stage before it opens; extending goes through `time_box.extended_by` with a reason.
- Each type's `people` rules and required questions must hold before its `open_button` is enabled.
- A closed intent is read only. Past intents are kept; cancelled intents carry the reason.
- Closure names `why_it_happened`, `what_came_out` and at least one `next` entry (which may be `nothing` with a reason). Weekly check-in weeks close under `week_close`.
- Ratings are collected at closure from participants, anonymous by default, aggregated from three, never per person (rulings 8 and 15). Weekly check-in series and weeks are not rated.

## Counters and measures of this feature (numbers only, each traced to a record)

- Intents opened per type: count of `intents/*/intent.json` by `type`. "Not available yet: no intent has been opened" when none.
- Intents closed within the time box per type: count where `closure.closed_at` is not later than `time_box.ends`, over closed intents of that type.
- Mean days used per stage: from `stages[].days_used` against `default_days`; "Fewer than five" below five closed records.
- Intents extended: count of records with a non-empty `time_box.extended_by`.
- Start questions answered `unknown`: count of `start_answers` with mark `unknown`, per question id.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `ls modules/m1_intent/contracts`, `ls sh_platform/jsonfile.py sh_platform/profile/view.py`, and a read of the files below. graft does not index YAML here.

| Existing | Found | Decision |
|---|---|---|
| `modules/m1_intent/contracts/intent_session.yaml` (43 lines): seats, presets, 20/40/40 split, wall window | Stage and time rules for the wall | Reused as is for Initiative stage 1; the working-day rule reshaped into `working_days` (company time zone, else UTC). The type-level time box is new. |
| `modules/m1_intent/contracts/wall_questions.yaml` (14 lines): four wall questions | Card questions | Not copied: they belong to Initiative stage 1. Referenced by the stage. |
| `modules/m1_intent/contracts/interview_notes.yaml` (17 lines) | Draft-then-keep pattern | Reshaped idea only; the weekly prompts are new wording. |
| `modules/m1_intent/contracts/outcome.yaml` (18 lines): charter outcome | Initiative outcome points at it | Reused by reference. |
| `modules/m1_intent/contracts/charter.yaml`, `board.yaml`, `note_fields.yaml` | Charter, board lanes, note kinds | Not changed. Referenced by Initiative stages. |
| `sh_platform/jsonfile.py`, `sh_platform/profile/view.py` | Storage and per-viewer filtering | Reused for the intent record. |

Genuinely new: the type catalogue, per-type outcomes and closure rules. No existing contract lists intent types.

## Not in this feature

- The chooser frame, start-question screens, workflow screens, closure, intents list and share links (03, 22, 35, 38, 41, 43 and others).
- Gap analysis and the Moment of truth screen (Build centre).
- Changing the catalogue from the UI. This round it is edited as a file.
- Recurrence mechanics beyond what 38 and ruling 3 fix.

## Open questions

1. Stage splits (Initiative 3/6/1, Brainstorm 1/1/1, Check-in 3/1/1, Problem 1/2/1/1, Decision 1/1) are not in the brief, which fixes only the totals. The v1 wall window default of 5 days is shortened to 3.
2. Minimum counts marked "chosen": Weekly check-in two reporters (from 38). Initiative has no minimum because file 22 allows "Just me for now"; the brief's earlier "committee" size is unanswered.
3. Settled: ruling 16 makes the outcome flat per type; files 22, 35, 41 and 43 now follow this file.
4. File 38 says the series `outcome` stays `null`; ruling 6 says an object. This file gives the series `{weeks}`. File 38's third stage is Sort, earlier catalogue key was `triage`; `sort` is used here. 38's own fourth question creates item kind `extra`, which ruling 3 does not list.
5. `start_answers` mark: file 22 marks "Not sure" as `guessed`; this file adds `unknown`. Reconcile.
6. Settled: ruling 13 puts the decider in `people.decider` and the owner in `people.owner`; 41 and 43 now follow.
7. Live session length: 35 offers 45 or 60 minutes; the existing presets (5 to 30) are shorter. Confirm 45 and 60.
8. Where do backlog items live? File 21 owns it; this file only names `backlog` as a target.
9. Is a limit on Problem to Decision to Problem chains wanted now that a Decision may link to any type?
