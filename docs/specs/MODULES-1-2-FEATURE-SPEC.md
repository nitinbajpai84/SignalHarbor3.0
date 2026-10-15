# Signal Harbor: Modules 1 and 2, feature specification

**Version 1 · 3 October 2026 · Input for the build**

This document lists the features of module 1 (Intent Centre) and module 2 (Baseline) in a form a builder can work from. Each feature has an ID, who it is for, what goes in and out, acceptance criteria, and what exists today.

Companion files in this folder:
- `signal-harbor-data-catalogue-template.xlsx`: the data catalogue workbook that module 2 produces.
- `modules-1-2-feature-backlog.xlsx`: this feature list as a sortable backlog.

Design sources: the deck "Module 1 Intent Centre: workflow and screens" and the deck "Module 2 Baseline: process and data mapping" (private artifacts).

## 1. How to use this document

- Read section 2 first. It holds the rules that apply to every feature.
- Take features by priority, then by dependency. **P0** is needed for the first usable version of the module. **P1** completes the design. **P2** is later or optional.
- **Status** says what exists on the main branch today: Built, Partly built, or New. Verify the code before relying on a status; some are from memory of the build.
- **Size** (S, M, L) is a relative estimate for planning. The builder should confirm it.
- Anything in section 11 (open questions) is not decided. Do not fill the gap; ask.
- Sequencing: the family-office branch touches the same session, Intent Centre and shared menu files and has not merged yet. Start the build after it merges, unless the owner decides otherwise.

## 2. Rules for every builder

1. Contracts are the only source of truth: lists, states, templates, presets, thresholds and wording live in `contracts/`.
2. Never invent a business rule, a figure or a formula. If a value is missing, stop and ask.
3. Real client data never leaves the customer's environment. Only text and column names or types may go to an AI model, never values.
4. No secret in a contract, model or notebook. Use `secret_ref: env:NAME`.
5. Every model call goes through the gateway; every agent run writes to `control.run_registry`.
6. Every new route has an entry in `route_permissions.yaml`. Tokens are header-only. Mutations use the CSRF double-submit header.
7. No destructive command, and no deletion of customer content, without explicit human approval.
8. Plain words on screen; the vocabulary and leak tests must pass.
9. The empty company works on every screen.
10. One agent builds, a different agent reviews, and the package lands only through `scripts/sh_commit.py`.

## 3. Agents and how they behave

| Agent | Does | Never does |
| --- | --- | --- |
| Nira, coordinator | Welcomes, explains rules, keeps time, sends requests, chases, moves the work on, issues the outputs | Gives an opinion on a problem; writes a figure |
| North, industry expert | Listens, takes the note, reads it back, says what others in the industry usually track, groups notes | Proposes which problems to raise; states company policy; invents a figure |
| Lens, business analyst | Drafts definitions, asks the owners their questions, writes up answers, draws the process map, raises conflicts | Picks between two answers; invents a formula; treats a document as a source of a figure |

## 4. Roles (proposal; the builder maps these to the canonical roles in `contracts/access/`)

| Capability | Who |
| --- | --- |
| Prepare and run a session | Organiser (any user allowed to create intent) |
| Join a session | Anyone with the link and a free seat |
| Sign the charter | Two sponsors, or one owner on the smallest plan |
| Approve a charter from outside | A named C-level approver |
| Nominate owners | Organiser or a sponsor |
| Answer a request | The nominated person, by link or account |
| Sign a part of the baseline | The owner of that part |
| Countersign the baseline | The sponsors |

## 5. Where the code lives today (starting points)

| Area | Files |
| --- | --- |
| Sessions, notes, wall, tokens | `emitters/intent_sessions.py`, `webapp/backend/routers/intent_sessions.py`, `webapp/backend/routers/live.py` |
| Session screens | `docs/signal-harbor/prototype/js/screens/intent-session.js`, `alignment-room.js`, `charter-doc.js`, `intent-center.js` |
| Problem library | `webapp/backend/routers/problem_library.py`, `templates/<industry>/1/problems.yaml` |
| Baseline | `emitters/baseline.py`, `webapp/backend/routers/baseline.py`, `docs/signal-harbor/prototype/js/screens/baseline.js`, `estate.js` |
| Industry packs | `templates/insurance/1`, `templates/asset_management/1` (kpi_tree, glossary, feeds, industry_defaults, process_map_default) |
| Access | `contracts/access/route_permissions.yaml`, `contracts/access/` |
| Decisions | `docs/signal-harbor/history/nira-platform/decisions.md` (ND-38 to ND-53) |

## 6. Screens and navigation

Module 1 follows the stages in order. Module 2 is a work list with a wizard inside each task. A home page of six tiles opens each module.

| Module | Screen | Who | Leads to |
| --- | --- | --- | --- |
| 1 | Prepare | Organiser | Create room |
| 1 | Create room and invite | Organiser | Lobby |
| 1 | Lobby | Everyone | Briefing |
| 1 | Briefing | Everyone | My room |
| 1 | My room | Participant | Board |
| 1 | Brainstorm board | Organiser, then everyone | Together |
| 1 | Together: agree, tick, priority | Everyone | Charter |
| 1 | Charter and sign-off | Sponsors | Module 2 |
| 1 | Approver view | Approver | Back to Together, or signed |
| 2 | KPI work list | Analyst, organiser | A KPI's tasks |
| 2 | Triage | Analyst | Nominate |
| 2 | Owners and governance | Organiser | Requests |
| 2 | Requests | Organiser | Outstanding |
| 2 | My questions (answer link) | Owner | Done |
| 2 | Sensing and trace | Owners | Catalogue |
| 2 | Catalogue (five tabs) | Owners, analyst | Process map |
| 2 | Process map | Process owner | Review |
| 2 | Review and sign | Owners, sponsors | Module 3 |

## 7. Data model

Entities and the workbook tab each one comes from. All are stored as contracts in the customer's workspace; the builder proposes file names and confirms them against the existing layout under `sh_data/workspaces/<workspace>/contracts/`.

| Entity | Key attributes | Workbook tab |
| --- | --- | --- |
| Session | purpose, outcome, seats, timetable, template, approver, state | (module 1) |
| Note | text, purpose, affected, frequency and size, belief, source guess, labels, shown-as, author | (module 1) |
| Cluster | name, note IDs, agreement, in charter, priority | (module 1) |
| Charter | version, lines, signers, approver | (module 1) |
| KPI | ID, name, definition, priority, problem, three owners, tracking status, tentative date, next steps, sponsor acceptance, three signatures | 5 KPIs |
| Source | ID, name, type, structure, where it lands, owner, connection method and details, secret reference, personal data, who may see, arrival, SLA, availability | 1 Sources |
| Item | ID, source, kind, name, related KPIs, grain, arrival, update pattern, history, connection detail, cut-offs, availability | 2 Tables |
| Field | ID, item, name, meaning, type, format, allowed values, KPI, role, personal-data class, required, valid from and to, exception and handling | 3 Fields |
| Extraction | ID, item, what, why, KPI, where, format, required, personal-data class, valid from and to, exception and handling | 4 Extractions |
| Request | person, KPIs, how sent, state, reminders | (module 2) |
| Provenance | stated, guessed or unknown, who, when | every row |

Relations: Source has many Items. An Item relates to many KPIs. A Field or Extraction belongs to one Item and feeds one KPI per row. A KPI shows how many Items, Fields and Extractions are mapped to it.

## 8. Contracts to add (suggested names)

- `contracts/settings/intent_session.yaml`: seat limits, time presets, default split, warning time.
- `contracts/intent/charter_templates.yaml`: charter templates.
- `contracts/settings/baseline_requests.yaml`: reminder days (3 and 7), link expiry, request wording, email provider reference.
- `contracts/settings/tracking_status.yaml`: the four tracking statuses and the readiness rule.
- `contracts/settings/catalogue_lists.yaml`: every dropdown list in the workbook.
- `contracts/settings/modules.yaml`: which modules are enabled per customer.
- Per workspace: catalogue records (sources, items, fields, extractions) under the baseline contracts folder.

## 9. Feature list


### Module 1: Intent Centre


#### A Preparation

### M1-01 · Prepare a session
**Status:** New · **Priority:** P0 · **Size:** M

**What:** The organiser prepares the session ahead of time: what we are here to do, the outcome wanted, the charter template, the time split, whether North offers industry practice and the problem library, the briefing video, and the named approver. It is saved as a draft, editable until the session starts, and can be saved as a reusable template.

**Who:** Organiser  
**In:** Purpose, outcome, charter template, time split, North options, video, approver  
**Out:** A session draft; the room rules shown at the briefing

**Acceptance criteria:**
- A draft can be saved, closed, reopened and edited by the organiser only.
- After the session starts, the preparation values are read-only.
- Saving as a template lets a later session start from the same values.
- Every list offered (templates, time presets) is read from contracts, not code.
- Works for a company that has never run a session (empty company).

**Note:** Today the organiser gives only a title and the phases.


### M1-02 · Seats and time
**Status:** Partly built · **Priority:** P0 · **Size:** S · **Depends on:** M1-01

**What:** The organiser says how many people will join (1 to 10) and how long the session lasts (presets of 5, 10, 20, 30 minutes, or custom), and how the time is split across briefing, individual rooms and together.

**Who:** Organiser  
**In:** Seat count, length, split  
**Out:** A session with seats and a stage timetable

**Acceptance criteria:**
- 0 seats or more than 10 is refused with a plain message.
- One seat is a solo session: the organiser is the only participant and can run every stage.
- The split must add up to the length; otherwise the screen says so.
- Presets and the limit of 10 come from a contract.

**Note:** Host, phases and timer exist (V3-04a); seat count and presets are new.



#### B Room and invitations

### M1-03 · Create the room and the join link
**Status:** Partly built · **Priority:** P0 · **Size:** M · **Depends on:** M1-02

**What:** Starting a prepared session creates the common room and one private room per seat, with one join link. Each person opens the link and picks a free seat.

**Who:** Organiser, participants  
**In:** Prepared session  
**Out:** A room, seats, a join link

**Acceptance criteria:**
- People join with the link and no account.
- The link works only for this session and stops working when it closes.
- The organiser can revoke a seat.
- A seat taken by one person cannot be taken by another.
- The participant token travels only in the X-Session-Token header, never in a URL.
- Nobody without the link can see or enter the room.

**Note:** Sessions, join and tokens exist; fixed seats and the single link are new.


### M1-04 · Lobby
**Status:** Partly built · **Priority:** P1 · **Size:** S · **Depends on:** M1-03

**What:** Participants arrive and give a name and a role. Everyone sees who has arrived against the seats. Nira welcomes each person. The organiser starts when ready, with empty seats if need be.

**Who:** Everyone  
**In:** Name, role  
**Out:** A list of arrived people

**Acceptance criteria:**
- The organiser sees arrivals live.
- Nira greets each arrival by name and says how long the session will take.
- Starting with empty seats is allowed; a latecomer can still take a free seat (see M1-15).
- No notes can be added in the lobby (ND-53).

**Note:** A lobby state exists; the seat picture and greeting are new.


### M1-15 · Rejoin and late join
**Status:** New · **Priority:** P1 · **Size:** S · **Depends on:** M1-03

**What:** A person who loses their connection returns with the same link to their own seat and room. A latecomer takes a free seat and gets the time left.

**Who:** Participant  
**In:** Join link  
**Out:** A restored seat

**Acceptance criteria:**
- The same link returns the person to the same seat, notes and conversation.
- A latecomer sees the briefing first.
- An occupied seat cannot be taken.



#### C Briefing

### M1-05 · Briefing and room rules
**Status:** New · **Priority:** P0 · **Size:** M · **Depends on:** M1-01, M1-04, M1-07

**What:** Everyone sees the prepared rules (what we do, how it works, time, outcome, how notes are shown) and the briefing video. Each person confirms they are clear or asks Nira a question. The organiser sends everyone to their individual rooms.

**Who:** Everyone  
**In:** Rules from M1-01, video  
**Out:** Every person marked clear; rooms opened

**Acceptance criteria:**
- The rules text comes from the prepared session, not from code.
- The organiser sees how many people have confirmed.
- Rooms open only when the organiser sends everyone.
- A question to Nira is answered from the rules only, with no opinion on the problem.
- A person who joins late sees the briefing before going to their room.

**Note:** Maps to the existing brief state.


### M1-06 · Briefing video
**Status:** New · **Priority:** P1 · **Size:** S · **Depends on:** M1-05

**What:** A standard briefing video ships with the module. The organiser can replace it with their own.

**Who:** Organiser  
**In:** Optional uploaded video  
**Out:** A video shown at the briefing

**Acceptance criteria:**
- The standard video plays without any outside host.
- An uploaded video is stored in the customer's own environment.
- File types and size limits come from a contract.
- A text version of the video is always shown beside it.

**Note:** The standard video itself has to be produced.



#### D Individual rooms

### M1-08 · Private room conversation
**Status:** Partly built · **Priority:** P0 · **Size:** L · **Depends on:** M1-05

**What:** Each person has a private room with their own North. They talk or type freely. North takes each note in the person's own words, reads it back, and accepts corrections.

**Who:** Participant, North  
**In:** Spoken or typed words  
**Out:** Notes and a saved transcript

**Acceptance criteria:**
- Only the person and their North can see the conversation (who else may read it: open question Q4).
- Typed or spoken input; speech becomes text the person can correct.
- North asks one question at a time and keeps replies short.
- The full transcript is saved with the notes made from it.
- North never invents a problem, a figure or a rule.
- The conversation continues if the connection drops and returns.

**Note:** Private rooms and North's room turns exist; the listen-first behaviour and read-back are new.


### M1-09 · Spoken voice
**Status:** New · **Priority:** P1 · **Size:** M · **Depends on:** M1-08

**What:** The agent's replies can be spoken aloud, in a casual conversational voice. The text is always shown. Each person can mute.

**Who:** Participant  
**In:** Agent reply text  
**Out:** Audio and text

**Acceptance criteria:**
- Voice can be switched on or off per person; text is always shown.
- The speech service, its settings and its key reference live in a contract and an env reference; never in code.
- If the speech service fails the conversation continues in text with no error shown.
- Whether audio is stored is open question Q6.

**Note:** Nitin accepted an outside speech service. Speech to text already exists.


### M1-10 · Industry practice from North
**Status:** New · **Priority:** P0 · **Size:** M · **Depends on:** M1-08

**What:** After a note, North says what others in the industry usually track for that kind of problem, drawn from the industry pack. It is labelled as a suggestion and never as the company's policy. The person adds it to the note or dismisses it.

**Who:** North, participant  
**In:** The note, the industry pack  
**Out:** An industry-practice card on the note

**Acceptance criteria:**
- The card says Industry practice (suggestion) and states that the company decides.
- It appears only when the pack has a match; with no match nothing is shown and there is no error.
- It never states a figure that is not in the pack (label guard, ND-38).
- Adding or dismissing is recorded.
- Evals check the label, the absence of invented numbers, and the no-pack case.
- Switchable by the organiser in M1-01.

**Note:** Packs are templates/<industry>/1 (kpi_tree, glossary, industry_defaults). North does not propose which problems to raise.


### M1-11 · The note form
**Status:** Partly built · **Priority:** P0 · **Size:** M · **Depends on:** M1-08

**What:** Each note carries: the problem, the business purpose, who is affected, how often and how big, what the person believes today, where the data might be, and labels. North pre-fills from the conversation and asks only for what is missing.

**Who:** Participant, North  
**In:** Conversation  
**Out:** A submitted note

**Acceptance criteria:**
- The belief number comes only from the person; North never proposes one.
- Where the data might be is stored and labelled as a guess.
- Labels are suggested by North and confirmed by the person.
- Unsubmitted notes stay private; submitting is the person's act.
- The field list comes from a contract.

**Note:** Pain and belief fields exist; purpose, source guess and labels are new.


### M1-12 · Anonymous or by name, per note
**Status:** New · **Priority:** P0 · **Size:** S · **Depends on:** M1-11

**What:** On each note the person chooses to post by name or anonymously, as in a chat. An anonymous note shows no author to the room.

**Who:** Participant  
**In:** The choice  
**Out:** A note with or without a visible author

**Acceptance criteria:**
- The choice is on every note.
- For an anonymous note no response of any route carries the author to the room.
- The author's own view shows that the note is anonymous.
- Leak tests cover the board, the wall, the charter and any export.
- Whether the organiser can see the author is open question Q1; the default choice is open question Q3.

**Note:** Author is stored apart from the note so that it can be protected.


### M1-13 · Problem library offer
**Status:** Built · **Priority:** P1 · **Size:** S

**What:** When the organiser has switched it on, the person can start a note from a common problem in their industry, reword it and set its priority.

**Who:** Participant  
**In:** Industry pack  
**Out:** A note started from a library problem

**Acceptance criteria:**
- Nothing is added until the person acts.
- With no library for the industry the screen says so.
- Reads the existing problem-library route.

**Note:** V3-15 and V3-16. Adapt it to appear inside the private room.



#### E Brainstorm board

### M1-17 · The board appears when the rooms close
**Status:** Partly built · **Priority:** P0 · **Size:** M · **Depends on:** M1-08

**What:** While individual rooms are open nobody sees the board. When they close, the organiser sees it first, then shares it with the room. Notes show as written, then grouped.

**Who:** Organiser, everyone  
**In:** Submitted notes  
**Out:** A board

**Acceptance criteria:**
- The board route refuses with a plain message while rooms are open.
- After close the organiser sees raw and grouped views.
- The organiser shares it to the room with one action.
- An empty board shows an honest empty state.

**Note:** Gather and wall exist; the not-visible-until-close rule is new.


### M1-18 · Clustering by North
**Status:** Built · **Priority:** P0 · **Size:** M · **Depends on:** M1-17

**What:** North groups the notes into named problem clusters, shows which notes it merged, and never drops a note. A note that fits nowhere stays on its own.

**Who:** North  
**In:** Submitted notes  
**Out:** Named clusters

**Acceptance criteria:**
- Every submitted note appears in exactly one cluster or on its own.
- Cluster names are in the people's words.
- If the model fails the raw notes are shown with a plain message.
- Evals cover merging, singletons and a failed model call.

**Note:** Existing gather step (V3-04a); extend to named clusters and merged-note display where missing.


### M1-19 · Manual board edits
**Status:** New · **Priority:** P1 · **Size:** M · **Depends on:** M1-18

**What:** People can move a note to another cluster, rename a cluster, split or merge clusters.

**Who:** Organiser  
**In:** Board  
**Out:** An edited board

**Acceptance criteria:**
- Every edit records who made it.
- Anonymous authors stay hidden while editing.
- North's grouping can be restored.



#### F Back in the room

### M1-20 · Agree and discuss
**Status:** Built · **Priority:** P1 · **Size:** S

**What:** Back in the common room everyone marks agree or not on each cluster and can discuss in a thread.

**Who:** Everyone  
**In:** Clusters  
**Out:** Agreement and comments

**Acceptance criteria:**
- One mark per person per cluster, changeable until the organiser closes the stage.
- Threads show who wrote each comment, or anonymous where chosen.

**Note:** Alignment room (V3-UIc). Check anonymity applies to comments.


### M1-21 · Tick a cluster into the charter
**Status:** New · **Priority:** P0 · **Size:** M · **Depends on:** M1-20

**What:** Ticking a cluster sends it to the charter draft. Unticking removes it. Clusters left unticked are saved for a later session.

**Who:** Organiser, sponsors  
**In:** Clusters  
**Out:** A charter draft

**Acceptance criteria:**
- Tick and untick update the draft immediately.
- Unticked clusters are kept and offered at the next session's preparation.
- Nothing is ever deleted.


### M1-22 · Priority per ticked cluster
**Status:** Partly built · **Priority:** P0 · **Size:** S · **Depends on:** M1-21

**What:** Each ticked cluster gets a priority: must, should, could or not this time.

**Who:** Organiser, sponsors  
**In:** Ticked clusters  
**Out:** A priority per cluster

**Acceptance criteria:**
- The four values come from a contract.
- Who may set it follows the existing alignment-room rule (ND-51, V3-04a); the builder confirms.
- A cluster in the charter always has a priority.

**Note:** MoSCoW exists on intent items.


### M1-23 · Pause and resume
**Status:** Partly built · **Priority:** P1 · **Size:** S

**What:** The organiser can pause the session. The room, notes and seats are kept, and the group returns later.

**Who:** Organiser  
**In:** A pause action  
**Out:** A held session

**Acceptance criteria:**
- Pause is explicit and reversible.
- A paused session resumes at the same stage.
- Seats and tokens stay valid for the existing seven-day rule (ND-51).

**Note:** Persistence exists; an explicit pause is new.



#### G Charter and sign-off

### M1-24 · Charter templates
**Status:** New · **Priority:** P1 · **Size:** M · **Depends on:** M1-21

**What:** The organiser chooses a charter template in preparation. Nira writes the charter from the ticked clusters into that template.

**Who:** Organiser, Nira  
**In:** Ticked clusters, template  
**Out:** A charter draft

**Acceptance criteria:**
- Templates are contracts.
- Each charter line shows the problem, the purpose, the priority and the number of notes.
- A name appears only where the note was posted by name.


### M1-25 · Sign-off in the room
**Status:** Built · **Priority:** P0 · **Size:** S

**What:** Two sponsors sign the charter in the room, or one owner alone on the smallest plan. A signed charter is read-only.

**Who:** Sponsors  
**In:** Charter draft  
**Out:** A signed charter

**Acceptance criteria:**
- A signed charter changes only through a new sign-off.
- Both sponsor parts are shown from the gates (V3-14).

**Note:** ND-40, ND-48, V3-08, V3-14.


### M1-26 · Send the charter to a C-level approver
**Status:** New · **Priority:** P0 · **Size:** L · **Depends on:** M1-24, M1-27

**What:** If no senior person is in the room, the draft goes to a named C-level approver. The approver is named by the organiser in preparation and can be changed by the room at the end. The approver approves, or returns it with a comment.

**Who:** Organiser, approver, Nira  
**In:** Charter draft, approver  
**Out:** An approval or a return

**Acceptance criteria:**
- The approver receives a link to the draft only, with no other access.
- Return reopens the together stage and keeps the earlier draft as a version.
- Approval signs the charter with the approver's name and the time.
- The link is scoped, expires, can be revoked, and travels only in the header.
- How the product knows the approver is C-level is open question Q2.


### M1-27 · Charter versions
**Status:** New · **Priority:** P1 · **Size:** S

**What:** Every draft of the charter is kept as a version with who changed it and when.

**Who:** System  
**In:** Charter drafts  
**Out:** A version history

**Acceptance criteria:**
- A returned charter keeps the earlier draft.
- Versions are read-only.


### M1-28 · Business graph from the charter
**Status:** New · **Priority:** P1 · **Size:** M · **Depends on:** M1-25

**What:** The signed charter creates a graph: each problem is a node linked to the measures it needs, the people it affects, the process it belongs to and the source someone guessed. A simple picture can be shown at sign-off.

**Who:** System  
**In:** Signed charter  
**Out:** Graph nodes and links

**Acceptance criteria:**
- Built only from a signed charter.
- Feeds the existing context graph.
- Whether the picture is shown at sign-off is open question Q10.


### M1-30 · Hand-off to module 2
**Status:** New · **Priority:** P0 · **Size:** S · **Depends on:** M1-25, M2-01

**What:** A signed charter opens module 2 and creates the KPI work list from it.

**Who:** System  
**In:** Signed charter  
**Out:** Module 2 work items

**Acceptance criteria:**
- Module 2 cannot start from an unsigned charter, except where the client types or uploads a list of measures.
- The charter is recorded as the source of every KPI it creates.



#### H Cross-cutting

### M1-07 · Nira as coordinator
**Status:** Partly built · **Priority:** P0 · **Size:** M

**What:** Nira welcomes people, explains the rules, keeps time, answers what do I do now, and moves the room on. She does not give opinions on the substance of a problem.

**Who:** Nira  
**In:** Session state, rules  
**Out:** Messages and stage changes

**Acceptance criteria:**
- Evals cover: welcome, a rules question, a time warning, what do I do now, and a request for an opinion (refused politely).
- Every run goes through the gateway and is written to control.run_registry.
- Replies use plain words and pass the vocabulary leak test.

**Note:** Nira exists as the guide; the coordinator behaviours here are new.


### M1-14 · Timer, warning and extension
**Status:** Partly built · **Priority:** P1 · **Size:** S · **Depends on:** M1-02

**What:** A visible timer runs on the briefing, individual rooms and together. One minute before the end a warning shows. The organiser can extend.

**Who:** Everyone, organiser  
**In:** Session timetable  
**Out:** Warnings, stage moves

**Acceptance criteria:**
- The timer is shown on every stage.
- A one-minute warning is shown.
- At the end the notes written so far are submitted and the stage moves on, unless extended.
- Extending needs only the organiser.

**Note:** A timer exists; warning and extension rules are new.


### M1-16 · Notes only in the rooms
**Status:** Built · **Priority:** P0 · **Size:** S

**What:** A new note is accepted only in the individual-room stages; the lobby, briefing, gathering, wall and a closed session refuse it with a plain message.

**Who:** System  
**In:** State  
**Out:** A refusal

**Acceptance criteria:**
- Refused states return 409 with a plain-words message.
- A solo run follows the same rule.

**Note:** ND-53, V3-14. Reuse the existing session states: brief, rooms_1, rooms_2, gathering, wall, closed. Decide whether the old second round stays as an optional add-detail step.


### M1-29 · Storage, privacy and retention
**Status:** Partly built · **Priority:** P0 · **Size:** M

**What:** Transcripts, notes, boards and charters are stored in the customer's own workspace. Anonymous authors are stored apart from notes.

**Who:** System  
**In:** All session data  
**Out:** Protected records

**Acceptance criteria:**
- Nothing leaves the customer's environment except as allowed in X-01.
- Retention periods come from a contract (open question Q5).
- Deleting anything needs explicit human approval.


### M1-31 · Solo and empty company
**Status:** Built · **Priority:** P0 · **Size:** S

**What:** The whole module works for one person, and for a company that has never used it.

**Who:** Everyone  
**In:** -  
**Out:** -

**Acceptance criteria:**
- A solo run goes from preparation to a signed charter.
- Every screen has an honest empty state with no invented content.

**Note:** Verify each new screen against this (rule 12).



### Module 2: Baseline


#### A Work list

### M2-01 · KPI work list from the charter
**Status:** New · **Priority:** P0 · **Size:** M · **Depends on:** M1-30

**What:** Each charter problem becomes one or more KPIs to baseline. Lens proposes KPI names from the problem and the industry pack; people confirm, add or remove. The list shows the state of each KPI.

**Who:** Lens, business analyst  
**In:** Signed charter, industry pack  
**Out:** A KPI list

**Acceptance criteria:**
- No KPI exists until a person confirms it.
- A charter problem with no KPI is shown as such.
- States: not started, drafted, questions open, signed.
- With no pack the list starts empty with an add-a-KPI action.


### M2-02 · Triage per KPI
**Status:** New · **Priority:** P0 · **Size:** S · **Depends on:** M2-01, M2-12

**What:** For each KPI the screen shows four things: the definition, the owner, the producer of the data, and how it is gathered. Each is stated, guessed or unknown.

**Who:** Business analyst  
**In:** KPI  
**Out:** A triage view

**Acceptance criteria:**
- Each of the four shows its mark and who stated it.
- Unknown is a valid state and is listed.


### M2-03 · Definition drafts
**Status:** Built · **Priority:** P0 · **Size:** S

**What:** Lens drafts each KPI's definition from the company's own industry pack and asks the questions only the business can answer. It never invents a formula.

**Who:** Lens  
**In:** Pack, KPI  
**Out:** Draft definitions with You decide questions

**Acceptance criteria:**
- Content comes from templates/<domain>/1, never from another industry.
- A KPI with no formula gets a null formula and a question for the customer.
- A signed or confirmed part is never re-drafted (409); human edits are kept.

**Note:** V3-17.



#### B Owners and governance

### M2-04 · Nominate the owners
**Status:** New · **Priority:** P0 · **Size:** M · **Depends on:** M2-02

**What:** For each KPI the organiser nominates a business owner, a data owner and a process owner, by name, with or without an account. A nominated person can decline, which returns the question to the organiser.

**Who:** Organiser, sponsors  
**In:** KPI, names  
**Out:** Three owners per KPI

**Acceptance criteria:**
- Three roles per KPI, each a named person.
- Declining returns the nomination to the organiser.
- A KPI with a missing owner shows no owner and cannot be signed.
- Every nomination records who nominated and when.

**Note:** A data owner role already exists in access contracts.


### M2-05 · Governance per source and field
**Status:** Partly built · **Priority:** P0 · **Size:** M · **Depends on:** M2-16

**What:** Each source and field is marked personal data, sensitive to the business, neither, or not sure, and the organiser names who may see it.

**Who:** Data owner, organiser  
**In:** Classification, names  
**Out:** Access limits on catalogue rows

**Acceptance criteria:**
- Not sure is treated as personal until someone confirms.
- People not named see that a row exists but not what is in it, enforced on the server.
- Leak tests cover every route that returns catalogue rows.
- Reuses the personal-data levels already in the data model contracts.


### M2-30 · Reassign an owner
**Status:** New · **Priority:** P2 · **Size:** S · **Depends on:** M2-04

**What:** The organiser can replace a nominated owner who leaves or changes role. Earlier answers stay with the name of who gave them.

**Who:** Organiser  
**In:** A new name  
**Out:** A reassigned KPI

**Acceptance criteria:**
- The earlier signatures stay in the history.
- The new owner re-confirms.



#### C Requests

### M2-06 · Requests to owners
**Status:** New · **Priority:** P0 · **Size:** L · **Depends on:** M2-04, M2-07, M2-09

**What:** Nira sends each nominated person a request listing their questions per KPI, by email with a link or to an account created for them. Owners can instead answer together in a meeting. Nira tracks sent, opened and answered, and chases.

**Who:** Nira, owners  
**In:** Nominations, questions  
**Out:** Answers, a status per person

**Acceptance criteria:**
- A request carries the KPI name and the questions only, never client data or figures.
- The answer link opens only that person's questions.
- Reminders go after three and after seven days (from a contract); then the organiser is told.
- Every send is logged in control.run_registry.
- If no email service is configured the screen says so plainly and nothing is sent.


### M2-07 · Answer link without an account
**Status:** New · **Priority:** P0 · **Size:** M · **Depends on:** M2-04

**What:** A scoped link lets a nominated person answer their questions with no account.

**Who:** Owner  
**In:** A link  
**Out:** Answers

**Acceptance criteria:**
- The token travels only in the header, expires, and can be revoked.
- The person can save and return.
- The link grants no other access.

**Note:** Follows the pattern of the session participant token.


### M2-08 · Account for an owner
**Status:** New · **Priority:** P1 · **Size:** M · **Depends on:** M2-04

**What:** The organiser can create an account for a nominated owner instead of sending a link.

**Who:** Organiser  
**In:** Name, email  
**Out:** An account with an owner role

**Acceptance criteria:**
- Uses the existing authentication and its protections.
- The owner role sees only their own questions and rows.
- First sign-in forces a password change.


### M2-09 · Email service
**Status:** New · **Priority:** P1 · **Size:** M

**What:** A sender that works with any provider, configured in the customer's environment.

**Who:** System  
**In:** Provider settings  
**Out:** Sent emails

**Acceptance criteria:**
- The provider and the wording are in contracts; the credential is an env reference.
- A bounce is shown to the organiser.
- It can be switched off, and the module then works without it.


### M2-29 · Outstanding view and chasing
**Status:** New · **Priority:** P1 · **Size:** S · **Depends on:** M2-06

**What:** The organiser sees who has not answered and Nira nudges them.

**Who:** Organiser, Nira  
**In:** Request states  
**Out:** Reminders

**Acceptance criteria:**
- Outstanding people are listed with how long they have waited.
- Reminder timing comes from a contract.



#### D Sensing

### M2-10 · Sensing questions
**Status:** Partly built · **Priority:** P0 · **Size:** M · **Depends on:** M2-06 or meeting

**What:** Each owner says: is it tracked today, could we track it, where it comes from, whether it is structured, unstructured or both, the SLA, when it arrives, its dependencies, and offers a sample. By form or by talking to Lens.

**Who:** Owner, Lens  
**In:** Answers  
**Out:** Sensing answers per KPI

**Acceptance criteria:**
- Every answer is stated, guessed or unknown.
- The person can save and return.
- Lens writes up what the person says and the person confirms it.

**Note:** Sense peek and benchmark views exist separately.



#### E Trace

### M2-11 · Trace upstream and downstream
**Status:** New · **Priority:** P0 · **Size:** M · **Depends on:** M2-10

**What:** For each KPI: who supplies the data and who they ask (upstream), who processes it and where it is changed by hand (in between), who asks for the result and who consumes it (downstream).

**Who:** Process owner, Lens  
**In:** Answers  
**Out:** A chain per KPI

**Acceptance criteria:**
- Every hop has an owner or Unknown.
- A spreadsheet in the middle is recorded as a manual step.
- The chain feeds the lineage columns and the process map.



#### F Documents and samples

### M2-13 · Data dictionary upload
**Status:** New · **Priority:** P1 · **Size:** M · **Depends on:** M2-16

**What:** An owner can upload an existing data dictionary. Lens reads it as context and proposes rows for the catalogue.

**Who:** Owner, Lens  
**In:** A dictionary file  
**Out:** Proposed rows marked guessed

**Acceptance criteria:**
- A dictionary is context, never a source of a figure (ND-43).
- Proposed rows need a person to confirm.
- The file stays in the customer's environment.


### M2-14 · Sample data comparison
**Status:** New · **Priority:** P1 · **Size:** L · **Depends on:** M2-13

**What:** An owner can give a sample of old data. Lens profiles it on the customer's machine and compares how the fields really look with what is expected, then lists the differences for the owner to rule on.

**Who:** Owner, Lens  
**In:** A sample file  
**Out:** A difference list

**Acceptance criteria:**
- The sample is read locally; nothing is sent out.
- Only column names and types may be shown to an AI model, never values.
- Each difference needs an owner's ruling, which is recorded.
- A sample is deleted only with explicit human approval.

**Note:** Rule 0 in CLAUDE.md applies.


### M2-15 · Read metadata from a system
**Status:** New · **Priority:** P2 · **Size:** L · **Depends on:** M2-16

**What:** Lens can connect to a source with read-only access and read table and column names and types to propose rows in the catalogue.

**Who:** Lens, data owner  
**In:** A connection  
**Out:** Proposed rows marked guessed

**Acceptance criteria:**
- Read-only credentials by secret reference only.
- Metadata only, never row values.
- Failure gives a plain message.
- The line between this and module 3's connect and scan is open question Q7.



#### G Catalogue

### M2-16 · The catalogue model
**Status:** New · **Priority:** P0 · **Size:** L

**What:** Sources, items (tables, files, document types), fields, extractions and KPIs with their relations, stored as contracts in the customer's workspace.

**Who:** System  
**In:** -  
**Out:** A stored catalogue

**Acceptance criteria:**
- Source to items is one to many; items to KPIs and fields to KPIs are many to many.
- IDs are stable.
- Every record carries provenance (M2-12).
- The entities and fields match the Excel template; see the model section.


### M2-17 · Map tables and fields to KPIs
**Status:** New · **Priority:** P0 · **Size:** M · **Depends on:** M2-16

**What:** Each table lists the KPIs it relates to; each field and extraction names the KPI it feeds. Counts per KPI show what is mapped.

**Who:** Data owner  
**In:** KPI IDs  
**Out:** A mapping and coverage counts

**Acceptance criteria:**
- A table can relate to several KPIs.
- A KPI with nothing mapped is visible.
- Counts of tables, fields and extractions per KPI are shown.
- Mapping changes are attributed.

**Note:** Counts already exist as formulas in the workbook.


### M2-18 · Excel export
**Status:** New · **Priority:** P0 · **Size:** M · **Depends on:** M2-16

**What:** The catalogue exports as the Excel workbook, identical in tabs, columns, lists and formulas to the template.

**Who:** Anyone allowed  
**In:** The catalogue  
**Out:** An .xlsx file

**Acceptance criteria:**
- Opens in Excel without a repair prompt.
- Dropdown lists are filled from the contracts.
- Example rows are not included.
- Respects governance: rows a person may not see are not exported.

**Note:** Template: signal-harbor-data-catalogue-template.xlsx.


### M2-19 · Excel import
**Status:** New · **Priority:** P1 · **Size:** M · **Depends on:** M2-18

**What:** A filled workbook can be uploaded. It is checked, shown as a difference, and applied only after a person confirms.

**Who:** Data owner, analyst  
**In:** An .xlsx file  
**Out:** Updated catalogue

**Acceptance criteria:**
- Row-level errors are listed with the cell.
- A signed row is never overwritten.
- Imported values record who imported them and when.


### M2-20 · Catalogue screens
**Status:** New · **Priority:** P0 · **Size:** L · **Depends on:** M2-16

**What:** The five tabs as screens: list, add, edit, filter by KPI and by owner, with completeness and provenance on each row.

**Who:** Owners, analyst  
**In:** Catalogue  
**Out:** Edited catalogue

**Acceptance criteria:**
- Each tab matches its template tab.
- Completeness is shown per row.
- Respects governance (M2-05).
- Empty states are honest.



#### H Process map

### M2-12 · Provenance on every value
**Status:** New · **Priority:** P0 · **Size:** M

**What:** Every value in the baseline is marked stated by a named person, guessed, or unknown, with who and when.

**Who:** System  
**In:** Any input  
**Out:** A mark on each value

**Acceptance criteria:**
- No value is shown without its mark.
- A change to a value changes its mark and its author.
- Exports carry the mark.

**Note:** Applies to modules 2 and 3.


### M2-21 · Process map drawn from the answers
**Status:** Partly built · **Priority:** P0 · **Size:** L · **Depends on:** M2-11, M2-22

**What:** Lens draws the process map from the owners' answers and the trace: lanes by team, steps in order, manual steps marked, and the tracking status on every step. People validate, edit or remove each step.

**Who:** Lens, process owner  
**In:** Answers, trace  
**Out:** A process map

**Acceptance criteria:**
- Steps nobody confirmed are shown as unconfirmed.
- Each step shows its tracking status.
- A map can be exported as an image.
- A signed map is never redrawn over.

**Note:** A list of steps drafted from the pack exists; the drawing and the answer-driven steps are new.


### M2-22 · Tracking status
**Status:** New · **Priority:** P0 · **Size:** S

**What:** Each KPI and each step has one of four statuses: tracked today, can be tracked now, will be tracked in future, cannot be tracked.

**Who:** Owners  
**In:** A choice  
**Out:** A status

**Acceptance criteria:**
- The four values come from a contract.
- The status shows on the map, the work list and the catalogue.



#### I Review and readiness

### M2-23 · Unknowns, next steps and sponsor acceptance
**Status:** New · **Priority:** P0 · **Size:** M · **Depends on:** M2-22

**What:** For anything not tracked today the owners give a tentative date if there is one and the next steps or the project that will bring it. A sponsor accepts it as unknown for now.

**Who:** Owners, sponsors  
**In:** Date, steps, acceptance  
**Out:** A future view for sponsors

**Acceptance criteria:**
- Acceptance records the sponsor and the date.
- A one-page view lists what is coming and which project brings it.
- A tentative date is optional.


### M2-24 · Conflict reports
**Status:** Built · **Priority:** P1 · **Size:** S

**What:** When two people answer differently, both versions are shown with who said each. A named person settles it.

**Who:** Lens, named person  
**In:** Two answers  
**Out:** A settled answer

**Acceptance criteria:**
- Lens never picks one.
- Both versions are kept in the history.

**Note:** V3-06.


### M2-25 · Owner sign-off and sponsor countersign
**Status:** Partly built · **Priority:** P0 · **Size:** M · **Depends on:** M2-26

**What:** The business owner signs the definition, the data owner the source and catalogue rows, the process owner the process. The sponsors then countersign the baseline. Signed content is read-only.

**Who:** Owners, sponsors  
**In:** Their part  
**Out:** A signed baseline

**Acceptance criteria:**
- Each owner signs only their own part.
- Sponsors can countersign only when every KPI is ready (M2-26).
- A change after signing needs a new sign-off.
- Who signed what and when is recorded.

**Note:** Baseline sign-off with parts exists (V3-06); the per-KPI owner signatures are new.


### M2-26 · Readiness for module 3
**Status:** New · **Priority:** P0 · **Size:** S · **Depends on:** M2-22, M2-23, M2-25

**What:** A KPI is ready when its three owners have signed and either it is tracked today or can be tracked now, or it has next steps and a sponsor's acceptance. The baseline is ready when every KPI is ready.

**Who:** System  
**In:** KPI data  
**Out:** A ready or not-ready answer with reasons

**Acceptance criteria:**
- The rule is the same as the Ready column in the workbook.
- Not ready lists exactly what is missing.
- The rule's wording and values are in a contract.


### M2-27 · Protection of human work
**Status:** Built · **Priority:** P0 · **Size:** S

**What:** A re-draft never overwrites signed or human-edited content.

**Who:** System  
**In:** -  
**Out:** -

**Acceptance criteria:**
- Re-drafting a signed baseline is refused with 409 and a plain message.
- Edited steps, acknowledged sources and answered questions are kept.

**Note:** V3-17.


### M2-28 · Hand-off to module 3
**Status:** New · **Priority:** P0 · **Size:** S · **Depends on:** M2-26

**What:** A signed baseline makes the catalogue and the process map available to module 3. Empty and unknown rows open as gaps.

**Who:** System  
**In:** Signed baseline  
**Out:** Gap candidates for module 3

**Acceptance criteria:**
- Every Unknown and every empty required cell appears as an open gap.
- Module 3 reads the catalogue, never the workbook file directly.



#### J Whole module

### M2-31 · Empty company and one-person path
**Status:** Partly built · **Priority:** P0 · **Size:** S

**What:** Module 2 works for a company with no history and for one person doing every role.

**Who:** Everyone  
**In:** -  
**Out:** -

**Acceptance criteria:**
- Every screen has an honest empty state.
- One person can nominate themselves as all three owners.

**Note:** Verify against rule 12.



### Across both modules

### X-01 · Runs in the customer's own environment
**Status:** Partly built · **Priority:** P0 · **Size:** M

**What:** Both modules install in the customer's environment. Everything is stored there. Outbound calls are limited to: an AI model (text, column names and types, never client values), an optional email service, an optional speech service. Each is a setting that can be switched off.

**Who:** System  
**In:** Settings  
**Out:** A contained install

**Acceptance criteria:**
- No client data leaves the environment (rule 0).
- Each outbound service has a contract setting and an env reference for its key.
- With every optional service off, the module still works.


### X-02 · Each module is a package
**Status:** New · **Priority:** P1 · **Size:** M

**What:** A module can be switched on or off for a customer. The navigation shows only the enabled modules, and a module reads another's output only when both are enabled.

**Who:** Platform admin  
**In:** A per-customer setting  
**Out:** A module set

**Acceptance criteria:**
- The enabled set comes from a contract.
- A disabled module's routes refuse.
- A client can start at module 2 with a list of measures instead of a charter.


### X-03 · Contracts first
**Status:** Built · **Priority:** P0 · **Size:** S

**What:** Every list, state, template, time preset, threshold and piece of wording lives in contracts/, never in code.

**Who:** Builders  
**In:** -  
**Out:** -

**Acceptance criteria:**
- New contracts are schema-valid and committed.
- A missing contract value stops the build and asks, never fills a gap (rules 1 and 4).

**Note:** CLAUDE.md rules.


### X-04 · Access
**Status:** Built · **Priority:** P0 · **Size:** S

**What:** Every new route has an entry in contracts/access/route_permissions.yaml, so anything unlisted is refused. Tokens travel only in headers. Mutating calls use the double-submit CSRF header. Workspaces never see each other.

**Who:** Builders  
**In:** -  
**Out:** -

**Acceptance criteria:**
- Route-permission coverage tests pass.
- A viewer cannot write.
- Cross-workspace tests pass in strict isolation mode.


### X-05 · Agents
**Status:** Built · **Priority:** P0 · **Size:** S

**What:** All model calls go through the gateway. Agents use read-only tools. The label guard stops a figure that is not grounded. Each new behaviour has evals. Every run is written to control.run_registry.

**Who:** Builders  
**In:** -  
**Out:** -

**Acceptance criteria:**
- Stub evals run on every commit.
- No agent writes a number it cannot trace to a recorded fact.


### X-06 · Plain words and look
**Status:** Built · **Priority:** P0 · **Size:** S

**What:** Screens use the plain-words vocabulary, the Charter look, and keep the Hindsight, Insight, Foresight and Action headings.

**Who:** Builders  
**In:** -  
**Out:** -

**Acceptance criteria:**
- The vocabulary and copy-leak tests pass.
- No technical word appears on screen.

**Note:** ND-52.


### X-07 · Tests and review
**Status:** Built · **Priority:** P0 · **Size:** S

**What:** Every acceptance criterion in this document becomes a test. Each package is built by one agent and reviewed by a different one.

**Who:** Builders  
**In:** -  
**Out:** -

**Acceptance criteria:**
- The isolation gate and the node suite pass.
- Packages land only through scripts/sh_commit.py.


### X-08 · Audit trail
**Status:** Partly built · **Priority:** P0 · **Size:** M

**What:** Nominations, requests, answers, edits and signatures record who and when, append-only.

**Who:** System  
**In:** -  
**Out:** -

**Acceptance criteria:**
- History cannot be edited.
- It can be read by the people allowed to read the item.



## 10. Suggested build order

Start after the family-office branch has merged (see section 1). Group into packages of about one reviewable change each; the orchestrator assigns package IDs in the ledger.

1. **Module 1 core flow (P0):** M1-01, M1-02, M1-03, M1-05, M1-07, M1-08, M1-10, M1-11, M1-12, M1-17, M1-18, M1-21, M1-22, M1-26, M1-30, with X-03 to X-08.
2. **Module 2 foundation (P0):** M2-01, M2-02, M2-04, M2-05, M2-12, M2-16, M2-17, M2-20, M2-22, M2-26. Owners answer in a meeting at this stage; no email yet.
3. **Module 2 exchange (P0):** M2-06, M2-07, M2-10, M2-11, M2-18, M2-21, M2-23, M2-25, M2-28.
4. **Completing the design (P1):** voice, video, charter templates and versions, manual board edits, graph, account creation, import, document and sample comparison, per-module enablement.
5. **Later (P2):** reading metadata from systems, reassigning owners.

## 11. Open questions (not decided; do not fill the gap)

| # | Question | Recommendation |
| --- | --- | --- |
| Q1 | Can the organiser see who wrote an anonymous note? | No. Nobody can, so the choice is real. |
| Q2 | How does the product know the approver is C-level? | The organiser marks the title when naming them. |
| Q3 | Is a note by name or anonymous by default? | By name, unless the organiser sets otherwise in preparation. |
| Q4 | Who may read a person's private transcript? | Only the author. |
| Q5 | How long are transcripts, requests and answers kept? | A contract setting decided per customer. |
| Q6 | Is the audio of spoken replies stored? | No. |
| Q7 | Where is the line between reading metadata in module 2 and connect and scan in module 3? | Module 2 reads names and types to propose rows; module 3 tests connections and compares samples. |
| Q8 | Who may set the priority of a cluster? | Follow the existing alignment-room rule. |
| Q9 | Which role is the organiser? | Any user allowed to create intent, matching today's facilitator. |
| Q10 | Is a picture of the business graph shown at sign-off in module 1? | Yes, a simple one. |

## 12. Settled by Nitin on 2 and 3 October 2026

Six modules; builder and forecaster agent names are placeholders; room of up to ten and one person can run it alone; in-product task list instead of an outside tool; anonymous is a per-note choice; North offers industry practice, labelled as a suggestion; the spoken voice stays and an outside speech service is accepted; the approver is any C-level person named in preparation and changeable at the end; the board appears when the individual rooms close; a standard briefing video that can be replaced; each owner signs their own part and the sponsors countersign; requests by email link or an account created for the owner; owners may upload a data dictionary or a sample of old data; the baseline is ready when KPIs are signed or unknowns are recognised and accepted with next steps; the output is a process map and an Excel catalogue; modules are installed in the customer's own environment; Lens may read metadata from their systems.
