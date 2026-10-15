# 43. Decision intent

Part of: Intent Centre v2. Depends on: 01 (record and lifecycle), 02 (type catalogue), 03 (chooser), 06 (people), 07 (time box), 09 (closure and sign-off), 10 (ratings), 20 (linking intents). Feeds: 04 (home and past list), 13 (Pulse lines), 21 (backlog), the company graph versions (measures and processes), the share link view (11).

## Purpose (three sentences)

This file is canonical for the Decision's five start questions (ruling 2); specs 02 and 03 follow it.

The Decision intent is for one decision that must be made and kept with its options. The question, the options and the advisers' notes sit on one screen, North drafts the options and a recommendation from records, and one named person decides. The decision, why, who, when, the advisers and the options considered are kept as the record, and the measures or processes the decision names get a version note.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet, or anyone who opens the intent) | Something needs a decision and the options are not clear | Chooses "A decision" in the chooser (03), answers five start questions |
| Decider (one named person, default the sponsor, for example Daniel) | The options are ready, or the time box is near its end | Nira line "A decision is waiting for you"; opens the decision screen; picks |
| Adviser (up to five, for example Katie, Aaron, Harvey) | After being named | Nira line "Janet asked for your advice on <question>"; adds an option or a note, anonymous allowed |
| Affected person (area member) | Any time | Sees the intent exists and, once closed, the one-line outcome |
| Business owner of a named measure or process (Harvey) | The decision is recorded | Sees a version note on the node and a Nira line "<Decision> changed <node>" |
| North (agent) | From the first answer to the closure draft | Drafts options, the recommendation, nudges, drafts closure; never decides |
| Company admin | Any time | Sees existence and outcome, never anonymous notes (brief section 4) |
| Super admin | Any time | Sees that the intent exists, never its content |

## Entry points (every route, link, Pulse line, button that leads here)

- Chooser card "A decision" (spec 03) opens the start questions at `/centre/intent/new?type=decision`.
- `&from=<intent id>` on the same route when any intent (Initiative, Brainstorm, Weekly check-in item, Problem or another Decision) needs a decision (spec 20 owns the link; ruling 7: a Decision may link to any type, as source or target). The question is pre-filled and the source intent is shown as a chip. North's pre-fill is a draft.
- Button "Ask for a decision" on a Brainstorm's chosen-idea screen and on a Problem's closure screen (those specs own the buttons; this spec owns the route).
- Home page (`/centre/intent`) list row for a Decision (spec 04) opens `/centre/intent/<id>`; the Past list (`/centre/intent/past`) shows closed and cancelled decisions, cancelled with their reason.
- Nira "waiting for you": decider ("<Question> needs your decision by <date>"), advisers ("Your advice was asked on <question>"), organiser ("Two advisers have not replied").
- Pulse page line when a decision is recorded: "<Question> decided: <option>. By <name>."
- Share link (spec 11, view `/centre/intent/<id>/share`; visitors enter through `POST /api/modules/m1_intent/shared/view`) opens the read-only record view.
- Routes: `/centre/intent/new?type=decision` (start), `/centre/intent/<id>` (decision screen while `open`; record view when `closed` or `cancelled`), `/centre/intent/<id>/close` (closure screen from 09, used only to close incomplete or to cancel; a clean decision closes itself at the decider's pick).

## Screens, element by element

### A. Start questions (route `/centre/intent/new?type=decision`)

Fields written: Q1 `title` and `outcome.question`; Q2 `time_box.ends`; Q3 `people.decider`; Q4 `people.advisers`; Q5 `areas`.

Layout at 1280: the chooser frame from 03. Left, 7 of 12: five questions stacked, each with its helper line. Right, 5 of 12: "What North will do" panel and a live preview of the intent header (title, time box, decider). Footer bar: "Back" and "Open this decision".
Layout at 390: one column, questions first, the preview collapses to a row "Preview" that opens on tap. Footer bar sticky with "Open this decision".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Q1 "What must be decided?" | field (one line, length limit in Open question 8, counter) | Placeholder "For example: which valuation date do we use for the fund report?" | Writes `title` and `outcome.question`. North checks it ends as a question or a clear "whether" line and offers a rewrite as an agent line, never forced | Organiser | "Open this decision" disabled with "Say what must be decided" |
| Q1 helper | agent line (North) | "One decision only. If there are two, open two." Shown when the line contains "and" or "or" between two verbs | None | Organiser | Not shown |
| Q2 "By when?" | field (date, working days only) | Default is two working days from today (brief section 2), shown as "Friday 9 Oct (2 working days)" in the company time zone from the profile, else UTC | Writes `time_box.ends`. A date beyond the limit in Open question 3 shows "That is longer than a decision should take. Consider an Initiative." (a note, not a block) | Organiser | Default filled; cannot be empty |
| Q3 "Who decides?" | field (person picker, one name) | Default "The sponsor" resolved to a named person, for example "Daniel (sponsor)" | Writes `people.decider` (ruling 13) and `people.sponsor` if empty. Only people in the company; company admin and sponsor roles are marked | Organiser | Disabled "Open this decision" with "Name who decides" if no sponsor exists and none is picked |
| Q3 warning | agent line | "You chose yourself. That is allowed. Advisers will still be asked." Shown when decider equals organiser | None | Organiser | Not shown |
| Q4 "Whose advice do you want?" | field (people picker, chips up to the cap in Open question 8) | Chips with name and role; each chip has "Remove" (x) | Writes to `people.advisers`. A name over the cap is refused with "That is more advisers than this decision allows." |
| Add adviser | button (text) | "Add adviser" | Opens the people picker from spec 06; the chosen person is added to `people.advisers` | Organiser | Picker shows "Nobody found" when the search is empty | Organiser | "No advisers. North will draft the options from the records alone." Allowed |
| Q5 "Which areas does it affect?" | field (area chips, from company areas) | Chips, each with "Remove" (x) | Writes `areas`. Drives visibility (05) | Organiser | Disabled "Open this decision" with "Choose at least one area" |
| Add area | button (text) | "Add area" | Opens the company area list; the chosen area becomes a chip | Organiser | "No areas are set up for this company yet" |
| Affected people may read | switch | "Affected people may read the options and notes." Off by default (ruling 4) | Writes `share.affected_may_read` (see Fields section). On: affected people read what a participant reads, except anonymous authorship; they never write | Organiser | Off |
| What North will do | panel | Three lines: "North drafts the options from the records and the advisers' notes. North drafts a recommendation and shows what it rests on. Daniel decides." | None | Organiser | n/a |
| Open this decision | button (primary) | Label "Open this decision" | Creates `intents/<id>/intent.json` with `type: decision`, `state: open`, `stages: [{key: options}, {key: decide}]`, and `outcome` as an object holding `question` and empty `options` (ruling 6, never null); sets `time_box`; writes the first line of `events.jsonl`; sends Nira lines to the decider and advisers; starts North's first draft; goes to B | Organiser | Disabled until Q1, Q3 and Q5 are filled |
| Back | button (text) | "Back" | Returns to the chooser; nothing is saved | Organiser | n/a |

### B. Decision screen (route `/centre/intent/<id>`, state `open`)

Layout at 1280: top bar; header strip (question as title, type chip "Decision", state chip, time box line "Decide by Fri 9 Oct", decider name, "Add an option" and "More" menu). Two columns. Left, 8 of 12: "Options" (cards in a two-column grid), then "North's recommendation", then "The decider's choice". Right, 4 of 12: "Advisers" panel, "Affects" panel (areas and named measures or processes), "Linked intents".
Layout at 390: one column in this order: header strip, options (one card per row, collapsed to name and "for / against" counts, tap to expand), North's recommendation, decider's choice, advisers, affects. Header buttons go into "More". The decider's choice is a sticky bottom bar with "Choose" for the decider only.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| More menu | button (menu) | "More" in the header strip; at 390 it also holds "Add an option" | Opens: "Share" (organiser), "Change the decider" (organiser, before any choice), "Cancel this decision" | Organiser; decider sees "Cancel this decision" | Always holds "Cancel this decision" |
| Change the decider | button (in More) | "Change the decider" | Opens the person picker (spec 06); writes `people.decider` and an entry in `events.jsonl`; shows old and new names | Organiser | Hidden once an option is chosen |
| Question | panel | `title`, `purpose` line, "Asked by Janet on 7 Oct", source chip if `links.from` | Pencil ("Edit question") edits the question (organiser) until the first option exists; after that it is read-only with "Open a new decision to change the question" | Participants (decider, advisers, organiser); area members see title and state only | n/a |
| Option card | list item | Name; "What it means" (one or two sentences); "For" (list); "Against" (list); "What it costs or needs" (one line); mark "Guessed by North" or "Added by <name>" or "Added by an adviser" (anonymous); count of advisers' notes | Click expands the card and its notes. The "Edit" button on a card marked "Added by <me>" or, for the organiser, on any card | Participants | See "No options yet" below |
| Guessed mark | chip | "Guessed by North, from 4 records" with the count of records it rests on. Becomes "Confirmed by <name>" when the person who added or an adviser accepts it | Click lists the records (open in a side panel, read-only); "n" is the length of `sources` on that option | Participants | A card with no record behind it is marked "Guessed by North, nothing recorded behind it" and is shown last |
| Add an option | button | "Add an option" | Opens a form: name (required, length limit in Open question 8), what it means, for, against, cost or need. Anonymous switch (off by default). Writes an option to `outcome.options`; the form has buttons "Add option" and "Cancel" | Organiser, advisers and the decider; never an observer | Always shown while open |
| Anonymous switch | switch | Off by default; on the option form and the note field. Helper on: "Nobody will see who added this." | Stores `by: "Anonymous"` and nothing else about the writer (as graph comments do) | Same | Off |
| Add a note | field on a card (one line, length limit in Open question 8) with kind choice "Comment" or "Suggestion" and an anonymous switch | Placeholder "Your view on this option" | Appends to the option's notes. A suggestion proposes a change to the card text ("say the cost is two weeks, not one") | Advisers, organiser, decider; never an observer | Card shows "No notes yet." |
| Notes list | list (comment thread, reused) | By, time, text, state line ("Open", "Accepted by Janet", "Declined", "Answered") | The buttons "Accept", "Decline" and "Answer" (from `CommentThread`) appear on a suggestion; pressing one records the state (see Rules for who may decide a suggestion) | Participants | "No notes yet." |
| North's drafting line | agent line | "North drafted 3 options from 6 records and 2 notes at 14:05. 1 adviser has not replied." | None | Participants | "North has not drafted yet. It is waiting for the question." |
| Redraft | button (text) | "Redraft options" | North redrafts only cards it drafted and nobody edited; cards a person edited or added are kept as they are (rule 7 of the repo: a draft never overwrites a human edit) | Organiser | Hidden when every card has been edited |
| Recommendation line | agent line, labelled "North's draft recommendation" | One sentence: "North leans to Option B, because <reason in one clause>." then "Rests on:" and source chips (record name and date, for example "Measure: NAV lag, 3 Oct", "Janet's note, 7 Oct") | Chip opens the record in a side panel | Participants | "North has no recommendation. It needs the minimum options and records in Open question 8." |
| Recommendation label | chip | "Agent's draft. Not a decision." Always shown beside the line | None | Participants | n/a |
| Trace rule note | text | Every number in the line has a chip; a number without a record is dropped by North and the line says what is missing: "North could not work out the cost of Option A. Missing: a quote or an estimate." | None | Participants | n/a |
| Decider's choice panel | panel | Three choices in order: "Pick one option", "Decide later", "No decision". Shows the decider's name and the time left | Opens the matching form below. Anyone else sees the panel read-only with "Waiting for Daniel" | Decider acts; others read | Disabled with "Add at least one option first" when there are none |
| Pick one option | button (primary) | "Choose <option>" on each card, visible to the decider only | Opens the sign modal (Screen C) for that option | Decider | n/a |
| Decide later | button | "Decide later" | Opens a small form: new date (required, working day, within the cap in Open question 3) and a reason (required, one line). Extends once, see Rules | Decider | Second use shows "Already extended once on 8 Oct. Pick or say no decision." |
| No decision | button | "No decision" | Opens a small form: reason (required, one line, length limit in Open question 8). Closes with `chosen: null` | Decider | n/a |
| Advisers panel | list | Name, role, "Added 2 notes" or "Not replied yet" with the count's unit | Click filters notes to that person's (non-anonymous) | Participants see names and counts; anonymous contributions are a separate line "Anonymous notes: n" | "No advisers named. North drafted from records." |
| Nudge adviser | button | "Nudge" beside "Not replied yet" | Sends one Nira line to that adviser; the frequency limit is in Open question 8 | Organiser | Hidden when everyone has replied |
| Affects panel | list | Areas as chips; "Measures and processes named" as chips (each is a node id with its label) | Button "Name a measure or process" (organiser or decider) opens a picker over the company map nodes the viewer can see; each named chip has "Remove" (x) while open | Participants | "No measure or process is named. Nothing will be written to the map." |
| North banner | agent line | "This will not be decided inside the time box. Options: extend, close with no decision, cancel." with the named person who picks | Each option is a button; nothing happens until a named person presses one (spec 07) | Organiser, decider | Not shown when on time |
| Time box line | chip | "Decide by Fri 9 Oct, 1 working day left" with the clock state from 07 | Click opens the extend dialog from 07 (the decider's own path is "Decide later") | Organiser, decider | n/a |
| Cancel this decision | button (in More) | "Cancel this decision" | Dialog with required reason and buttons "Cancel this decision" and "Keep it open"; state becomes `cancelled`; the reason is shown in Past | Organiser; decider | Reason empty keeps confirm off |
| Linked intents | list | `links.from` and `links.to` as chips with title and type (any type, ruling 7) | Click opens that intent if the viewer may | Participants | "No linked intents." |
| Source chip | chip | Title of `links.from` | Click opens the source intent if the viewer may | Participants | Not shown |
| Source record chip | chip | Record name and date in the recommendation line | Click opens the record in a side panel | Participants | Not shown |

Numbers on screen B and where each comes from: "from n records" is the length of `outcome.options[].sources`; note counts are the length of `outcome.options[].notes`; "Added n notes" and "Anonymous notes: n" count the same `notes` by `by`; "n working days left" and the decide-by date come from `time_box.ends` against the company clock; "Not replied yet" is an adviser in `people.participants` with no entry in any `notes[].by`. A figure with no record behind it reads "Not available yet" and names what is missing.

### C. Sign modal (opens from "Choose <option>")

Layout at 1280: centred modal 520 wide over the screen. At 390: bottom sheet, full width.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Summary line | panel | "You are choosing: <option name>. This will be recorded as your decision." | None | Decider | n/a |
| Why field | field (required, length limit in Open question 8) | Placeholder "Why this option?" North offers a draft line the decider may use, marked "North's draft"; an unedited draft is stored with `why_drafted: true` | Writes `outcome.why` | Decider | "Record my decision" disabled with "Say why" |
| What this writes | list | "A version note on: NAV lag measure, Month-end close process." and "A link on: <source intent>." Each line comes from the Affects panel and `links.from` | None | Decider | "Nothing else is written. No measure or process is named." |
| Record my decision | button (primary) | Label "Record my decision" | Writes the decision (see journey step 8); closes the intent | Decider | Disabled until Why is filled |
| Cancel | button (text) | "Not yet" | Closes the modal; nothing is written | Decider | n/a |

### D. Record view (route `/centre/intent/<id>`, state `closed` or `cancelled`)

Same frame as B, rendered from the stored record. Not rendered at all (not just disabled): "Add an option", "Add a note", "Redraft options", "Nudge", the decider's choice buttons, "Cancel this decision". The rating panel (10) and "Share" (organiser) remain.

| Element | Kind | Shows | On click | Visible to | State when empty |
|---|---|---|---|---|---|
| Share | button | "Share" | Opens `/centre/intent/<id>/share` (spec 11) | Organiser | Always shown on a record |
| Rating panel | panel | Spec 10's prompt; ratings anonymous by default (ruling 15) | As spec 10 | Participants | As spec 10 |
| Decision strip | panel | "Decided: <option name>. By Daniel on 8 Oct." or "No decision. Reason: <reason>." or "Cancelled: <reason>." | None | Everyone who sees the intent (area members and affected people see this line, plus title, purpose, stage and people, unless "Affected people may read" is on) | n/a |
| Why | panel | The decider's reason, with "North's draft" mark if unedited | None | Participants, share-link people | n/a |
| Options considered | list | Every option card as it stood at the decision, the chosen one marked, with for, against, cost, and the notes count | Click expands | Participants, share-link people. Anonymous notes keep "Anonymous" | "No options were recorded." (only for a cancelled intent) |
| Advisers | list | Names and whether each gave a note; "Anonymous notes: n" | None | Participants | "No advisers were named." |
| Recommendation as it was | agent line | "North's draft recommendation was Option B" with its source chips, shown beside the chosen option so a different choice is plain | Chip opens the record | Participants | "North made no recommendation." |
| What it wrote | list | Version notes written (node label, version, link to the node) and the link on the source intent | Opens the node or intent if the viewer may | Participants | "Nothing else was written." |
| Deferral line | text | "Decide-later used once: from 9 Oct to 14 Oct. Reason: <reason>." | None | Participants | Not shown |
| Linked intents | list | `links.from` and `links.to` (spec 20) | Opens that intent if the viewer may | As the source intent | "No linked intents." |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet opens the chooser (`/centre/intent/new`), picks "A decision", and answers the five start questions (Screen A, `/centre/intent/new?type=decision`). She names Daniel as decider, Katie, Aaron and Harvey as advisers, and the areas "Finance operations" and "Investment". She leaves "Affected people may read" off.
2. She presses "Open this decision". The record is created in `intents/<id>/intent.json`; the time box is two working days; Nira sends lines to Daniel and the three advisers.
3. North reads the records it may read for the named areas (the named measures, the process map nodes, earlier decisions in those areas, Janet's linked intent) and drafts option cards (how many is Open question 8), each marked "Guessed by North, from n records". It drafts the recommendation line. Nothing is drafted from a record the viewer may not see.
4. Katie opens the screen, adds an option "Use month-end custodian price" with an anonymous note on another card. Aaron adds a suggestion on a card. Harvey adds a comment. Each addition is written at once; nothing waits for a save.
5. North updates the drafting line, redrafts only unedited cards when asked, and keeps the recommendation line current. It tells the organiser which advisers have not replied; the organiser presses "Nudge" and Nira sends one line. Any automatic nudge timing is in Open question 8.
6. Daniel opens the screen when it is his turn. He reads the cards, the notes and North's draft recommendation with its source chips.
7. Daniel chooses one of three paths. (a) Presses "Choose" on a card, then the sign modal opens. (b) "Decide later": picks a new date and a reason; the time box moves once; the screen shows the new date. (c) "No decision": writes a reason; the intent closes with no option chosen.
8. On "Record my decision" the system writes `outcome` (chosen option, why, decider, at, advisers, options considered, the recommendation as it stood), runs the closing checks from 09 (decision text, decider, why), and moves the state to `closed`. For each named measure or process it appends a version note; on the source intent it adds a link.
9. North writes the closure draft (why it happened, what came out, next list) for Janet to read. The decision is already closed; the closure text is a draft for the record, edited by Janet before it is final. If Janet does nothing, the closure keeps North's draft marked "Drafted by North".
10. Nira sends the Pulse line to the area members and a version-note line to each named node's owner. The rating prompt (10) goes to Janet, Daniel and the advisers.
11. Anyone with the share link or the right to open sees the record view (Screen D). Each person's journey ends when they leave the screen; the intent's ends at `closed` or `cancelled`.

Between steps North never decides, never picks an option, and never fills the Why on its own: the draft Why is a suggestion in a field the decider must confirm.

## States and transitions (table: state, who moves it, to what, what is written)

| State | Who moves it | To | What is written |
|---|---|---|---|
| (new) | Organiser presses "Open this decision" | `open` | New `intents/<id>/intent.json` and `events.jsonl`: type, title, purpose, areas, people, `time_box`, `stages`, `people.decider`, `outcome.question`, `outcome.options: []` |
| `open` (stage `options`) | North drafts; advisers and organiser add | `open` | `outcome.options[]`, notes on each option, `outcome.recommendation` |
| `open` | Decider presses "Decide later" (first time) | `open` | `time_box.ends` replaced; `extended_by` entry {by, at, reason, kind: decide_later, was}; `outcome.deferral` |
| `open` | Decider presses "Decide later" (second time) | No move | Refused with the message "Already extended once" |
| `open` | Decider confirms "Record my decision" | `closed` | `outcome.chosen`, `outcome.why`, `outcome.decided_by`, `outcome.decided_at`; `closure` (closed_by is the decider); `stages[*].closed_at`; version notes; links |
| `open` | Decider confirms "No decision" with reason | `closed` | `outcome.chosen: null`, `outcome.no_decision_reason`; `closure` as above |
| `open` | Organiser or decider presses "Cancel this decision" with reason | `cancelled` | `closure.cancel_reason`, `closed_by`, `closed_at`; options kept as they stood |
| `open`, time box over | Named person picks from North's banner (spec 07) | `open` (extended once by the organiser), `closed` with no decision, or `cancelled` | As the matching row above |
| `closed`, `cancelled` | No one | No move | Nothing. A follow-up is a new intent linked by `links.from` |

Note on `closing`: a Decision does not rest in `closing`. The decider's act closes it. `closing` is used only if the organiser opens `/centre/intent/<id>/close` to "Close with what we have" (a decision with no decider's act, for example when the decider has left the company); that follows 09 unchanged.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Read or written | Fields | Existing or New |
|---|---|---|---|
| `intents/<id>/intent.json` | Read and written | The intent record from the brief; `outcome` as below (an object from the moment of opening) | New (record defined in spec 01) |
| `intents/<id>/events.jsonl` | Appended | One line per open, option, note, decider change, deferral, decision, cancel; the record holds counts only (ruling 12) | New (spec 16) |
| `sh_platform/jsonfile.py` | Used for every write (`write_json_atomic`, `lock_for`) | None | Existing |
| `sh_platform/profile/view.py` | Read: per-viewer filtering of the record, anonymous notes, and area visibility | None | Existing |
| `graph/comments.json` | Not written by this feature. The note and suggestion shape is reshaped into `outcome.options[].notes` (same fields: kind, text, by or "Anonymous", at, state, decided_by, decided_at, answer) | Shape only | Existing, reshaped |
| `graph/versions.json` via `append_version(plane, node_id, what, by, ref)` | Written once per named measure or process on a recorded decision | `what`: "Decision: <option name>. <one-line why>"; `by`: decider name; `ref`: `intent:<id>` | Existing |
| `GET /api/company/graph/node/{id}` | Read: node labels, business owner, steward for the Affects picker | `owned_by`, label | Existing |
| Measures and process map nodes named in Affects | Read | Label, owner, last version | Existing |
| Earlier closed decisions in the same areas | Read (North uses them as records) | `outcome`, `closure.summary` | New (same `intents/<id>/intent.json` files) |
| `intents/<from>/intent.json` of the source intent (`links.from`) | Written: `links.to` gains this id | `links.to` | New |
| Nira "waiting for you" lines | Written | decider, advisers, owners | Existing mechanism (`sh_platform/pulse/lines.py`) |
| New routes | Declared in the module manifest, default deny | `POST /api/intents` (create), `POST /api/intents/{id}/options`, `POST /api/intents/{id}/options/{opt}/notes`, `POST /api/intents/{id}/notes/{note}/decide`, `POST /api/intents/{id}/decide` (choose, later, none), `POST /api/intents/{id}/nudge/{person}`, `POST /api/intents/{id}/decider` (change the decider), `GET /api/intents/{id}` (read, filtered per viewer) | New |

`outcome` for a Decision:

```
outcome: {
  question,                           # the decider is people.decider, advisers are people.advisers (ruling 13, 21)
  options: [{id, name, means, for: [], against: [], needs, origin: north|person|adviser|anonymous,
             by|"Anonymous", at, confirmed_by|null, sources: [record refs], notes: [{id, kind, text, by|"Anonymous", at, state, decided_by, decided_at, answer}]}],
  recommendation: {option_id|null, line, sources: [record refs], drafted_at, drafted_by: "North"} | null,
  chosen: option id | null, why, why_drafted: bool, decided_by, decided_at,
  no_decision_reason|null,
  deferral: {from, to, reason, by, at} | null,
  writes: [{node_id, version, ref}], 
  considered_snapshot: [option cards as they stood at the decision]
}
```

## Fields this feature adds to the intent record

Under `outcome` (shown above). Beyond that:

- `people.decider`: one named person, a named slot (ruling 13). `people.sponsor` stays optional.
- `people.advisers`: list of named people (ruling 21).
- `share.affected_may_read`: boolean, default false (ruling 4).
- `stages`: `[{key: "options"}, {key: "decide"}]` for a Decision.
- `time_box.extended_by[].kind`: `decide_later` (so 07 and 09 can tell it from a plain extension).
- `closure.next`: usually empty; if the decision names a follow-up, the same `{kind, ref, reason}` rows as 09.

No existing field is renamed.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

**North drafts:**
- Option cards, from the records for the named areas and the named measures or processes, and from advisers' notes. Each card says what it means, for, against, and what it costs or needs. A cost or need North cannot trace to a record is written as "Not known. Needs: an estimate from <owner>", never a guess in digits.
- Every card it drafts is marked "Guessed by North, from n records". A person's edit replaces the mark with their name and North stops touching that card.
- The recommendation line: one option, one clause of reason, the source chips. If fewer than two options or no record, no line, and a sentence saying what is missing.
- The Why draft in the sign modal, as a suggestion only.
- The closure draft after the decision is recorded.
- The time-box banner when the decision will not be made in time.

**North never:** picks an option, writes a number it cannot trace, edits a card a person edited, signs, or changes the decider.

**Lens:** only if a named measure or process has no definition in the glossary or map, Lens drafts the definition line shown on the Affects panel as "Lens draft", for a person to confirm elsewhere (spec 26 owns that flow). No other part of this feature uses Lens.

**Nira:** carries "waiting for you" lines for the decider (decision due), advisers (advice asked), the organiser (advisers silent, time running out) and the business owners of named nodes (version note written). Nira feeds the Pulse line at closure.

**The person acts at:** opening the decision (organiser), adding options and notes (organiser, advisers), accepting or declining a suggestion on a card (see Rules), choosing, deferring or declining to decide (decider), confirming the Why, closing text edits (organiser), rating (10).

## Rules (visibility, time box, who may do what)

- One decider, one named person. The default is the sponsor. The decider may be the organiser. Changing the decider is possible only by the organiser while no option has been chosen, and appends an entry to `events.jsonl` (spec 16); the old and new names are shown on the screen.
- Only the decider records the decision. The organiser, North and company admin cannot choose for the decider. If the decider is absent, the organiser may "Close with what we have" with a reason (spec 09), which records no decision.
- Advisers: the cap is Open question 8. Each adviser may add options and notes. The organiser and decider may add options. An observer reads what a participant reads and never writes or votes (ruling 4).
- Suggestion handling reuses the graph comments rule: only the owner or the steward decides a suggestion. Here the "owner" of an option card is the person who added it, and for a card drafted by North it is the organiser. The decider also may accept or decline a suggestion, because the decider owns the question. Anyone else sees the note and the state line "Open · Janet to decide" and never the Accept or Decline buttons. A refused attempt returns 403 "Only the card's owner or the decider can decide this".
- Accepting a suggestion edits the card text with a version of the card kept in its notes ("Accepted: <text>"). It does not change the decider's options.
- Anonymous: an anonymous option or note stores "Anonymous" and nothing about the writer. The organiser, decider, company admin and super admin never see who. The anonymous switch is per item.
- Time box: two working days by default. "Decide later" extends once, within the cap in Open question 3, with a reason. A second extension is not offered to the decider. If the organiser needs more, spec 07's rule for a second extension applies (sponsor approval); this is an open question below.
- The recommendation is always labelled "Agent's draft. Not a decision." It is shown beside, never above, the options. It is not shown in the cards' order (cards are ordered by creation time, newest last, never by North's lean).
- Every number on the screen traces to a record or reads "Not available yet" with the missing record named.
- A decision stays open after the decider picks only until the write finishes; then it is `closed` and read-only. A closed decision is never edited or re-opened.
- Visibility follows the brief and ruling 4: area members and affected people see existence, title, purpose, stage, clock, people and, once closed, the outcome; content opens for them only when "Affected people may read" was on at creation or they are named on a share. Participants see the cards and notes (except anonymous authorship); share-link people see the record view. The company admin sees existence and outcome, never anonymous notes. The super admin sees title, type, state, areas, people count, dates and time box status only, read through the kernel, never content (ruling 5).
- A draft intent is visible only to the person who started it. Cancelled decisions keep their reason and appear in Past (ruling 14). Dates and clocks use the company time zone from the profile, else UTC (ruling 8).
- A decision that names a measure or process the viewer may not see shows the node as "A measure you do not have access to" in the Affects list and the writes list.
- Version notes are written only to nodes the decider may see. If the decider cannot see a named node, the modal says so and that node is skipped with the line "Not written: you cannot see <label>".
- Signed content is read-only (repo rule 7): once recorded, `outcome` is never rewritten.

## Counters and measures of this feature (numbers only, each traced to a record)

| Measure | Counts | Traced to |
|---|---|---|
| Decisions open | Decision intents with `state: open` in the viewer's areas | `intents/*.json` |
| Decisions closed this month | Decision intents closed in the month, split into decided, no decision, cancelled | `outcome.chosen`, `closure.closed_at`, `state` |
| Time to decide | Working days from `created_at` to `outcome.decided_at`, median | Same files; below five closed decisions it shows "Fewer than five" (ruling 8) |
| Decide later used | Decisions with `outcome.deferral` set | `outcome.deferral` |
| Options per decision | Mean of `outcome.options` length for closed decisions | `outcome.options`; "Fewer than five" below five closed decisions |
| Share of options added by people | Options with `origin` not `north` over all options | `origin` |
| Decider followed North's draft | Closed decisions where `chosen` equals `recommendation.option_id`, count over closed decisions with a recommendation | `outcome.chosen`, `outcome.recommendation` |
| Version notes written by decisions | Count of `writes` entries | `outcome.writes` |
| Advisers who replied | Advisers with at least one note over advisers named | `outcome.options[].notes[].by`, `people.advisers` |
| Ratings average | As spec 10, aggregated from three ratings, never per person (ruling 15) | `ratings` |

Counts are exact. "Decider followed North's draft" is a count and a fraction of two counts; it is never labelled as North's accuracy.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searched `sh_platform/graph`, `modules/m1_intent`, `ui/src/design` and `ui/src/modules/m1_intent` for comment, suggestion, decide, sign and modal.

| Existing | Where | Decision |
|---|---|---|
| Graph comments with kinds comment, suggestion and ambiguity; anonymous stores only "Anonymous" | `sh_platform/graph/comments.py` lines 23 to 36 (`KINDS`, `NewComment`, `Decision`), 117 to 133 (post) | Reshaped: same fields and same anonymity rule, stored inside `outcome.options[].notes` instead of `graph/comments.json`; only the `comment` and `suggestion` kinds are used |
| Decide route, owner or steward only; 403 text; accepted, declined, answered; answer required for "answered" | `comments.py` lines 54 to 74 (`_owner`, `_steward_is`, `_may_decide`), 135 to 157 (decide route) | Reshaped: same `_may_decide` shape, the "owner" becomes the card's author (or organiser for North's cards) plus the decider |
| Accepted suggestion writes a version | `comments.py` line 81 (`_add_version`), `sh_platform/graph/versions.py` lines 40 to 50 (`append_version`) | Reused as it is for the version note on each named measure or process |
| State line "Open · <name> to decide" and the "(owner)" or "(steward)" suffix | `comments.py` lines 94 to 105 (`_line`) | Copied for the notes list state line |
| Comment thread UI with Accept, Decline, Answer | `ui/src/design/parts.tsx` lines 279 to 305 (`CommentThread`) | Reused as it is for the notes list on each card |
| Signature strip and sign action | `ui/src/design/parts.tsx` lines 307 to 317 (`Signature`) | Reused for the "Decided by" strip on the record view; the sign modal copies its copy pattern |
| Charter sign flow: role check, signer record {name, account_id}, one confirm | `modules/m1_intent/api/charter.py` lines 294 to 305; `ui/src/modules/m1_intent/charter/CharterScreen.tsx` line 177 (`SignActions`) | Reshaped: the decider's "Record my decision" modal copies the confirm step; no role table is needed because the decider is a named person; no approver link (a decision is recorded by the decider in person) |
| Dialog markup for small forms | `ui/src/modules/m1_intent/define/DefineScreen.tsx` lines 104 and 189 (`role="dialog"` card with a form) | Copied for "Decide later", "No decision" and "Cancel this decision" forms |
| Person and area pickers | Searched `ui/src` for picker; the people picker belongs to spec 06 | Reused from spec 06 |
| Closure and ratings | Specs 09 and 10 | Reused as they stand; the Decision outcome block in 09 reads this spec's `outcome` |
| Time box and extend dialog | Spec 07 | Reused; "Decide later" is a special first extension with its own reason field |
| Per-viewer filtering; JSON files | `sh_platform/profile/view.py`; `sh_platform/jsonfile.py` | Reused |
| Pulse and Nira lines | `sh_platform/pulse/lines.py` | Reused for the lines in Entry points |

Genuinely new: the Decision start questions, the option card with its marks, the recommendation line with its source chips, the decider's three choices, the `outcome` shape, and the write to nodes and the source intent. A search for "option", "decision record" and "decider" in `modules/` and `sh_platform/` found only `pending-memories/decide` (agent memory, unrelated) and the graph comments decide route above.

## Not in this feature

- Votes, scoring matrices, weighted criteria, or any score North computes for an option.
- More than one decider, a quorum, or a committee decision (see Open questions).
- Approver links for decisions; the decider acts in the signed-in app.
- Re-opening or editing a closed decision; a new intent is opened and linked instead.
- Creating the measure or process itself; this feature only writes a version note on one that exists.
- Money approvals, spend limits and contract sign-off; no thresholds are defined here.
- Live session rooms (a Brainstorm owns those).
- The chooser, the home page, ratings and the closure screen; they are specs 03, 04, 10 and 09.

## Open questions

1. Should the decider be allowed to name someone to decide in their place (delegate), and who is recorded then?
2. Is one "decide later" enough, or does the second extension need sponsor approval as in 07? This spec offers none to the decider.
3. The "decide later" cap. This spec states no number as a rule. Proposed for review: one extension, to a date within five working days; and a note on Q2 when the date is beyond ten working days. No existing rule supports either figure.
4. Should North see earlier closed decisions in the same areas as records (this spec says yes)? A decision may contain material not meant for every area.
5. When two measures or processes are named and the decider can see only one, is a partial write acceptable (this spec says yes, with a line saying which was skipped)?
6. Should a Decision be able to close "deferred to an Initiative" as a fourth outcome, or is "No decision" with a link enough?
7. Does the company want a decision log across the whole company (all closed decisions in one list, with filter), or is the home past list (spec 12) enough?
8. Limits the brief did not give, proposed for review: advisers at most five; question line 140 characters; option name 60 characters; note 300 characters; reason 400 characters; one Nira nudge per adviser per day; North drafts two to four options; a recommendation needs at least two options and one record.
9. Should "adviser" be a role on `people.participants` (this spec) or a named slot? Ruling 13 names only `decider`, `owner` and `reporter`.
