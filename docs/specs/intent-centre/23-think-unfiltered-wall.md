# 23. Think unfiltered: the wall

Part of: Intent Centre v2. Depends on: 01 (intent record), 02 (Initiative stage list), 06 (people and invitation, join link), 07 (stage clock), 22 (start questions: purpose and people). Feeds: 24 onwards (Define strategically reads the frozen wall), the charter (page one), 09 (closure draft reads the counts).

Routes follow brief section 10, ruling 1: the wall is `/centre/intent/<id>/wall`. No alias exists. Where a v1 route is kept, it is marked Existing and listed under Open questions.

## Purpose (three sentences)

The wall is the first stage of an Initiative: everyone who knows something puts it on the wall in about five minutes, in a private room with North, with no form. In v2 the wall no longer starts the centre. It opens from an intent record, takes its purpose, title and people from the start questions (22), and runs on the stage clock (07). Nothing about the wall's four lanes, four-quarter cards, seal, anonymous rule or North's suggestion cards changes; what changes is where it starts and who owns it.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | Opens the stage, watches counts while rooms are open, closes the rooms, reads the wall, freezes it | "Open the wall" on the intent, stage bar button on the wall |
| Participant (Aaron) | Writes cards in a private room, then reads the wall | Pulse line "Janet asked you to add cards to <title>" (06), or the join link |
| Observer | Reads what a participant reads. Never writes, never votes | Invitation as observer (06) |
| Sponsor (Daniel) | Reads the wall and the counts; may ask the organiser to extend | Sponsor line on Pulse, intent page |
| Affected (Katie, Harvey) | Sees that the intent exists: title, purpose, stage, clock, people, and the outcome once closed. Opens the wall only if the organiser switched on "affected people may read" at creation (default off) or a share names them | Pulse line "For your information" (06) |
| Company admin | Sees the intent exists and its outcome once closed; never sealed or anonymous material | Intent list |
| Super admin | Sees existence only (title, type, state, areas, people count, dates, time box status); never the wall | Control intents list |
| North (agent) | Interviews each person, drafts cards, suggests up to three per lane, keeps the clock | Seat taken, rooms open |
| Lens (agent) | Fills quarter 4 from files when the person says "I don't know", marked guessed | Card put on the wall with quarter 4 empty |

## Entry points (every route, link, Pulse line, button that leads here)

- Intent page `/centre/intent/<id>`, stage "Think unfiltered": button "Open the wall" (organiser) and "Go to the wall" (everyone who may read it). New.
- Wall route `/centre/intent/<id>/wall`. New, thin: it resolves the intent's wall session id and renders the existing `WallScreen`.
- Old v1 route `/centre/intent/wall/<session_id>` (existing `wall/:sessionId` in `IntentModule.tsx`): same screen without the intent header, kept for walls that exist today. Open question 1.
- Private room: existing route `sessions/:sessionId/room`. Reached from the join link `/join/<code>` (existing; a code can name an intent, 06), the Pulse line "Add your cards" (06), and the button "Your private room" on the wall for a seat holder. Open question 1.
- Pulse lines (Nira, 06): "Janet asked you to add cards to <title>", "The wall for <title> closes tomorrow", "The wall for <title> is frozen. Read it."
- North's nudge card on the intent page (07): extend, close with what we have, cancel.
- Charter page one: link "Open the frozen wall" on the charter (`/centre/intent/<id>/charter`).
- Share link (06, 11): read-only wall view for people the link names.

## Screens, element by element

Rows marked "As built" repeat v1 and are not respecified: see the named file under `ui/src/modules/m1_intent/wall/`.

### Screen A. The wall (organiser, participant, observer; one screen, role decides what shows)

Route `/centre/intent/<id>/wall`. Component `WallScreen` (existing) wrapped by a new `IntentHeader`. Phases as v1: rooms open (counts and silhouettes), wall open (words show), frozen (read-only).

Layout at 1280: intent header (full width); stage bar card (organiser sees buttons, others read-only); invite panel (organiser, one line that opens); tools row; four equal lanes; North panel as a sticky right column, 420 px, only while the viewer has a room open (lanes shrink to fit).

Layout at 390: header collapses to title, one clock chip and "4 / 6 people". Stage bar collapses to "Step 1 of 3: Think unfiltered" (07). Lanes become four tabs with counts, one lane at a time. North panel becomes a sheet under "Talk to North". Invite panel moves under the stage bar.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Crumb | text | "Intent Centre / <title> / Think unfiltered" | Each part links up | Everyone who may read the wall | Not applicable |
| Intent title | heading | `intent.title`. The v1 H1 becomes the sub-line | None | Same | "Untitled intent. The organiser has not named it yet." |
| Wall sentence | text | As built, see `wall/copy.ts` | None | Same | Not applicable |
| Purpose line | text | "What are we here for:" then `intent.purpose` (start question 1, file 22). v1 read `preparation.purpose` | None. "Edit" (organiser) opens the intent's purpose field (22) | Same | "No purpose yet. Add one so people know why they are writing." with "Add purpose" for the organiser |
| Topic chip | chip | `topic` if set (v1 field) | None | Same | Hidden |
| Clock chip | chip | Stage clock from 07, read from `time_box` and the stage record: "3 days left", "Overdue by 1 day". Tooltip: close time in the company time zone from the profile, else UTC | None | Everyone who may read the wall; affected people see it on the intent page, not here | "No clock yet" while the intent is draft |
| People line | chip with initials | Initials of named contributors and "4 / 6 people": joined seats of invited `people` entries (06). Anonymous authors never show, not even as an initial | Opens the people panel (06) | Participants, observers, organiser, sponsor. Hidden in projector view | "Nobody has joined yet." |
| Card count | text | "27 cards": cards put on the wall, from `/board` `counts` | None | Same | "Not available yet" until the rooms have opened |
| Live mark | chip | "Live" while rooms are open | None | Same | Hidden when rooms are closed or the wall is frozen |
| Frozen mark | chip | "Frozen on 9 Oct, 17:00" from `stages[think_unfiltered].wall.frozen_at` | None | Same | Hidden before freeze |
| Stage bar | card | The intent's stages with the current one lit, and under it the v1 wall steps (existing `STAGES`) | See next rows | Organiser sees the button; participants and observers see the bar read-only | Draft intent: all steps plain, "Starts when opened" |
| Next-step button | button | As built, see `wall/StageBar.tsx` | "Are you sure?" with "Yes" and "No"; Yes calls the existing stage route and reloads | Organiser | Hidden when the stage has no next step |
| "Close the wall" | button | As built label | Freezes the wall, closes stage Think unfiltered and opens Define strategically, after "Are you sure?" | Organiser | Hidden until the wall step is reached |
| Extend | button | "Extend" (07 Screen B) | Opens the extend dialog; moves the wall window and the stage due date together | Organiser, sponsor | Disabled: "Nothing to extend. The wall is frozen." |
| North time card | agent line | North's nudge from 07, with counts read from `/board` `counts` and `people`: "4 of 6 people have not added a card." Buttons "Extend", "Close the wall now", "Cancel the intent" | A person presses; North never does | Organiser (sponsor read-only) | Hidden until the first nudge point in 07 |
| Invite panel | panel | As built, see `wall/InvitePanel.tsx`; the link is the intent's join link (06) | As built: "Copy link", "New link" (the old link stops working), "Revoke" | Organiser | "No link yet. Make a link." |
| "Show only mine" | chip | Filters lanes to the viewer's own cards | Toggles | Everyone except observers (no cards of their own) and in projector view | Not applicable |
| "Projector view" | chip | Lane names and counts only; no cards, names, panel or people line | Opens `/centre/intent/<id>/projector` (17); there "Back to the full view" returns here | Everyone who may read the wall | Not applicable |
| Lane (four) | list | As built, see `wall/Lane.tsx` and `wall/copy.ts`. Keys unchanged: `intent` TRACKING NOW, `pain_point` MISSING, `future_signal` WATCH, `lever` LEVERS | "+ n more" expands the lane | Same | "Nothing here yet." The lanes always show |
| Card | list item | As built, see `wall/Card.tsx` | Own card opens to read and edit while rooms are open; others read | Same | Not applicable |
| Card, four quarters | detail | As built (Q1 to Q4 wording in `wall/copy.ts`). A quarter filled by North or Lens shows "guessed" and names the document | Edit by the author only | Author, plus readers once the card is on the wall | "Not answered" |
| Seal | mark | As built: striped silhouette "A sealed card about <area>". No words, author or source reach the page | None | Silhouette to everyone not on the area's `may_see` list, including organiser and company admin (D-013) | Not applicable |
| Anonymous | mark | "Anonymous"; no name, no initial | None | Everyone sees the card; nobody sees the author | Not applicable |
| Other person's card, draft card, suggestion card | list items | As built, see `wall/Card.tsx`: "Someone's card" while rooms are open; dashed "Draft, only you see it"; dashed suggestion with source and "Pick it up to make it yours" (at most three per lane) | "Pick it up" calls existing `pickUpSuggestion`; failure: "That could not be picked up. Try again." | Participants with an open room; drafts to the author only | Suggestions hidden when North has no document to draw from |
| North panel | panel | As built, see `wall/NorthPanel.tsx`: question, four quarter bars, thread, "Your answer" box, voice bar | Answer sends to North | Anyone with an open room | "Tell North what you track, miss or want to watch, and it will ask the rest." |
| "Answer", "Yes, still right" | buttons | As built, see `wall/NorthPanel.tsx` | Save the answer; keep North's drafted quarter | Same | Disabled when the box is empty or nothing is drafted |
| "Put it on the wall now" | button | As built | Submits the card (existing `submitNote`); lane count rises | Same | Disabled until two of four quarters are answered, with the v1 line (A-055) |
| "Anonymous" and "Seal it" checkboxes | fields | As built | Write `anonymous` and `restricted` on the card | Same | Unticked |
| Wall state | panel | As built, see `wall/WallState.tsx` | "Try again" retries | Everyone | Empty and refused wording as built |
| Read-only banner (observer) | text | "You can read this wall. You do not add cards." | None | Observer | Not applicable |
| "Open the frozen wall as charter page one" | link | Shown once frozen | Opens `/centre/intent/<id>/charter` | Organiser, sponsor, participants, observers | Hidden before freeze |

### Screen B. The private room (participant arriving by link or from Pulse)

Route: existing `sessions/:sessionId/room` (`PrivateRoomScreen`). Layout at 1280: left, the person's own cards (`NotesPanel`) and North's suggestions (`LibraryPanel`); right, North's conversation. At 390: one column, cards first, North under a "Talk to North" tab.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Arrival band | text | "Janet asked you to add what you know to <title>. It takes about five minutes. Closes Fri 17:00." Title, organiser, purpose and clock from the intent; time in the company time zone, else UTC | None | The arriving person | "The organiser has not written a purpose yet." |
| Join step (link only) | form | Sign in, or join as a guest with name and role (existing `JoinScreen`); the code names the intent (06) | "Take my seat" writes the seat and a person entry `via: link` | A person arriving by link | "This link has ended. Ask Janet for a new one." |
| Role note | text | Participant: "You add cards." Observer: "You can read the wall. You do not add cards." | None | The person | Not applicable |
| North's first question | agent line | Q1 wording, or the question drafted from the person's interview (existing `seed_from_interview`, "Read from: <document>") | Answer in the box | Participants | North asks Q1 when nothing is drafted |
| Own cards | list | Own cards and drafts with edge and quarters (`NotesPanel`) | Open to edit; "Put it on the wall now" | The author | "You have no cards yet. Tell North what you track, miss or want to watch." |
| "Finish" panel | panel | Count of cards sent; "Your words show to others when the rooms close" | "I am done" (existing `FinishPanel`) | The author | Disabled: "Put at least one card on the wall first." |
| "Go to the wall" | button | "The rooms have closed. Go to the wall." | Opens Screen A | Anyone with a seat | Hidden while rooms are open |

An observer never sees Screen B: the link or Pulse line lands on Screen A with the read-only banner. An affected person with reading switched off sees only the intent page.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet opens the intent (22 has set title, purpose, people). She presses "Open the wall", then "Start the briefing" and "Open the private rooms", each behind "Are you sure?". North opens the stage clock (07) and writes the stage open date.
2. Between steps: Nira writes a Pulse line for each invited participant and observer. Janet copies the join link and sends it herself; the system never sends (06).
3. Aaron opens the Pulse line or pastes the join link. By link he signs in or joins as a guest and takes a seat. He lands in his private room.
4. North asks Aaron the four questions, one at a time. If an earlier interview exists, North drafts cards from it and Aaron confirms, changes or discards.
5. Aaron answers at least two of four quarters. He ticks Anonymous or "Seal it" if he wishes and presses "Put it on the wall now". The card counts.
6. Aaron may pick up a suggestion from North. It becomes his own card with the same four quarters to fill.
7. While rooms are open Janet sees counts per lane and silhouettes. North sends its nudges (07). Janet picks extend, close with what we have, or cancel.
8. Janet presses "Close the rooms and bring everyone to the wall". Words show. Lens fills quarter 4 where empty and marks it guessed with the file named.
9. Participants and observers read the wall, on phone or projector as in v1, each seeing what the rules allow.
10. Janet presses "Close the wall" (or the window ends, Open question 2). The wall freezes; untouched suggestions are dropped. The stage moves to Define strategically. Nira writes "The wall for <title> is frozen. Read it."
11. The frozen wall is page one of the charter. Janet and Daniel read it; the intent page shows the final counts from `outcome.wall`.
12. Each person leaves by the crumb link to the intent page, or "Open the frozen wall as charter page one".

## States and transitions (table: state, who moves it, to what, what is written)

The intent's own states are in file 01. This table is the wall's, inside stage `think_unfiltered`. The wall session is the existing m1_intent session.

| State (v1 session stage) | Who moves it | To what | What is written |
|---|---|---|---|
| draft | Organiser ("Open the wall" on an open intent) | lobby | Session exists from 22; stage `think_unfiltered` open with `opened_at`; session id on the intent |
| lobby | Organiser ("Start the briefing") | briefing | Session stage |
| briefing | Organiser ("Open the private rooms") | private_rooms | Session stage; rooms last the wall window |
| private_rooms | Organiser ("Close the rooms and bring everyone to the wall"), or the window ending | board | Session stage; `wall.rooms_closed_at`; cards readable; Lens fills quarter 4 |
| board | Organiser ("Close the wall"), or the window ending | together | `wall_snapshot.freeze`; untouched suggestions dropped; `wall.frozen_at`; stage closed with `closed_at`; `define_strategically` opened; `outcome.wall` written |
| together, signing | Organiser, as v1 | closed | Existing; unchanged |
| paused | Organiser (existing pause and resume) | back to the stage it left | Existing |
| any, intent cancelled | Organiser (cancel, 01) | closed | Wall stays readable to those who could read it; cancel reason on the intent |

## Records read and written (file or route, fields; mark Existing or New)

| Record or route | Fields | Existing or New |
|---|---|---|
| `intents/<id>/intent.json` | read: title, purpose, people, time_box, stages, session id, share, outcome. Write: stage open and close, `stages[think_unfiltered].wall`, `outcome.wall` | Existing (file 01); the wall touches only the fields named |
| `GET /sessions/{id}/board` and `/board/counts` | notes by cluster, `counts`, `by_kind`, `stage`, `organiser`, `can_edit` | Existing |
| `GET /sessions/{id}/room`, `POST /room/messages`, `/room/notes`, `/room/notes/{note}`, `/prefill`, `/submit`, `/practice` | room view, turns, notes with `quarters`, `anonymous`, `restricted`, `kind` | Existing |
| `GET /sessions/{id}/room/library` | North's suggestion cards with source document | Existing |
| `POST /sessions/{id}/start`, `/briefing`, `/rooms/close`, `/together`, `/pause`, `/resume` | stage movers | Existing |
| `GET /sessions/{id}/join-link`, `POST /sessions/{id}/link`, `POST /sessions/{id}/seats/{n}/revoke`, `POST /join` | join link, seats | Existing; a `/join` code may name an intent (06) |
| `GET /sessions/{id}/lobby`, `/live` | seat count, arrivals, live stream | Existing |
| `GET /sessions/{id}/charter`, `wall_snapshot` | frozen cards, sealed ones as silhouettes | Existing |
| `GET /api/intents/<id>/wall` | session id for the intent and the viewer's role (organiser, participant, observer, affected, none) | New (one small read) |
| Profile `cards` (A-053) and counters `cards_confirmed`, `cards_new`, `cards_sealed` (A-057) | lane, q1 to q4, sealed, anonymous, author; numbers only per person | Existing (v1 spec) |

## Fields this feature adds to the intent record

| Field | Type | Written by | Purpose |
|---|---|---|---|
| `refs.wall_session_ids` | list of session ids | Initiative start (01, 22) | Points at the wall; never copies it. Open question 5 |
| `stages[think_unfiltered].wall` | `{window_days, rooms_closed_at, frozen_at}` | Wall stage routes, once each | The window and freeze times; `window_days` equals the stage budget in 07 |
| `outcome.wall` (Initiative) | `{cards_total, per_lane: {intent, pain_point, future_signal, lever}, sealed, anonymous, people_contributed, snapshot_ref}` | Freeze, counts only | Feeds closure and the intent list; `snapshot_ref` points at the charter snapshot |

`outcome` is an object from the moment the intent opens (ruling 6); `outcome.wall` is absent until freeze. No brief section 3 field is renamed.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** drafts cards from each person's interview; asks the four questions one at a time; suggests up to three cards per lane from the pack and the company's documents (dashed, labelled); keeps the clock and drafts the options at the nudge points in 07. A person confirms, changes or discards each draft and picks up each suggestion. North never puts a card on the wall alone. The organiser presses extend, close or cancel.
- **Lens** fills quarter 4 from the company's files after the person says "I don't know", marked guessed with the file named. It never reads a sealed card into a draft others can see. The author confirms or edits.
- **Nira** writes the Pulse lines: invitation, closing reminder, frozen notice, and "what is waiting for you" for the organiser. Nira drafts the join-link email; the organiser copies and sends it.
- Agents never sign. Nothing on the wall needs a signature; the charter that carries it does (existing).

## Rules (visibility, time box, who may do what)

- Participants and observers see every card on the wall except sealed and anonymous material (D-013, seal). Anonymous means no name, no initial, and not even the organiser sees the author. An observer reads what a participant reads and never writes or votes.
- Sealed cards are silhouettes for everyone off the area's `may_see` list, including organiser, company admin and super admin.
- An affected person (by area or named) sees existence, title, purpose, stage, clock, people, and the outcome once closed (ruling 4). Content opens only when the organiser switched on "affected people may read" at creation (default off) or the person is named on a share.
- The super admin sees existence only (ruling 5), never the wall. The company admin sees the intent and its outcome once closed, never anonymous notes or sealed content.
- A draft intent, and so its wall, is visible only to the person who started it (ruling 14).
- A share link opens a read-only wall to the people it names, with the same masks.
- Only the organiser moves the wall's stages, makes or ends the join link and takes back a seat. A sponsor may ask; it is recorded as a note.
- The window is the stage clock (07): one number. `wall_window_days` (v1, 1 to 20, default 5, Monday to Friday) is set by the stage budget; North proposes it.
- A late joiner may take a seat until the rooms close; after that the link says "The rooms have closed."
- Frozen means no card is added or changed. The author may withdraw an own card until freeze (Open question 6); withdrawn cards are not counted.
- A card needs two of four quarters answered (A-055, as built).
- Times show in the company time zone from the profile, else UTC.
- No game words, no model or vendor names in copy. Demo content carries "Illustrative".

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Source record |
|---|---|
| Cards on the wall, total and per lane (exact) | `/board` `counts` and `by_kind`; after freeze `outcome.wall` |
| Cards sealed, cards anonymous (exact) | profile `cards` (`sealed`, `anonymous`) |
| People invited, joined, contributed at least one card (exact) | intent `people`, session seats, notes |
| Suggestions offered, suggestions picked up (exact) | `room/library` and notes with `suggestion` set |
| Cards confirmed from interview, cards new (exact) | counters `cards_confirmed`, `cards_new` (A-057) |
| Quarters answered per card, mean out of 4 | profile `cards` q1 to q4. "Fewer than five" below five cards; "Not available yet" with no cards |
| Days from open to freeze, against window | `stages[think_unfiltered]` times and `time_box` |
| Extensions of this stage | `time_box.extended_by` |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `graft skeleton` on `WallScreen.tsx`, `board.py`, `private_room.py`; `grep` for `wall_window`, `closes_at`, `wall_snapshot`. Every path below was checked to exist in this repo on 7 Oct 2026.

UI, as built, see `ui/src/modules/m1_intent/wall/`: `WallScreen.tsx`, `Card.tsx`, `Lane.tsx`, `NorthPanel.tsx`, `StageBar.tsx`, `InvitePanel.tsx`, `WallState.tsx`, `copy.ts`, `wall.css`, `wall.test.tsx`, `invite.test.tsx`, `stagebar.test.tsx`.

| File | Status and reason |
|---|---|
| `WallScreen.tsx` (92 to 184; `loadWall` 46 to 67; `useSessionLine` 80 to 88) | Reshaped in two places: `useSessionLine` reads title and purpose from the intent when an intent id is given; the header gets the intent clock. Observer viewing reshapes the read-only check |
| `StageBar.tsx` (22 to 66) | Reshaped by file 07 (stage list as a prop, clock). This file adds nothing else |
| `copy.ts` | Reshaped: gains the intent crumb and "Frozen on" strings only |
| `Card.tsx`, `Lane.tsx`, `NorthPanel.tsx`, `InvitePanel.tsx`, `WallState.tsx`, `wall.css` | Copied as is (existing, unchanged); no reason to rebuild |
| the three v1 tests | Existing; must keep passing |
| `IntentHeader` (title, purpose, clock, people) | New, small; reuses `Chip`, `closesWhen` and 07's clock chip |
| Intent route `/centre/intent/<id>/wall` and "Open the wall" button | New; resolves intent to session |

Private room, `ui/src/modules/m1_intent/private_room/`: `PrivateRoomScreen.tsx`, `NotesPanel.tsx`, `NoteForm.tsx`, `LibraryPanel.tsx`, `FinishPanel.tsx`, `roomApi.ts`, `useRoom.ts`. Existing, unchanged (copied as is). `ui/src/modules/m1_intent/IntentModule.tsx` lines 29 to 42 carry `wall/:sessionId` and `sessions/:sessionId/room`; reshaped to add the intent wall route.

API, `modules/m1_intent/api/` (all Existing, used as is): `board.py` (board, counts, close rooms), `private_room.py` (room, conversation, suggestions, pick up, seed from interview), `notes.py` (save, prefill, submit), `room.py` (start, link, join-link, revoke, briefing, lobby, live, join), `together.py` (close the wall, together, pause, resume), `charter.py` (wall snapshot as page one), `session.py` (session read and create, `wall_window_days`), `walls.py` (walls the viewer may open). Support, unchanged: `deps.py` (reshaped for observer viewer resolution, Open question 3), `roles.py`, `summary.py`, `approver.py`, `briefing.py`, `voice.py`, `__init__.py`.

Also Existing: `modules/m1_intent/domain/preparation.py` (`WALL_DAYS_DEFAULT`, window check), `store/sessions.py` (rooms last the wall window), `store/wall_snapshot.py`, `contracts/wall_questions.yaml`, `contracts/interview_notes.yaml`.

New: the intent header, the intent route and button, the session id write, the `outcome.wall` counts at freeze, and `GET /api/intents/<id>/wall`.

Not used: the v1 testing guide's lane names North, East, South, West (`docs/guides/TESTING-INTENT-CENTRE.md` section 6). The built lanes (`copy.ts`) win.

## Not in this feature

- Define strategically (clusters, shelves, glossary, catalogue, process map, governed state, charter writing). This file only freezes the wall and hands over.
- Build-ready check, Moment of truth, gap analysis (Build, not Intent).
- The Brainstorm "Think alone" stage, which reuses the private room: its own spec.
- The start questions (22), people panel and invitation (06), clock and extend dialog (07), ratings (10), closure (09), projector view (17).
- Grouping the wall by topic across several walls (not built in v1).
- New lanes, new quarters, new seal or anonymous behaviour.

## Open questions

1. Route spellings outside ruling 1's view list: the v1 wall route `/centre/intent/wall/<session_id>` and the private room `sessions/:sessionId/room` are kept as built. Should the room become an intent view, and should the old wall route redirect?
2. Should the window end freeze the wall automatically, or only move to "closing" and wait for the organiser? v1 closes the board by a person. Proposed: automatic at the window end, a person may close earlier. Not decided; file 07 says "freezes automatically".
3. Observer reading needs a viewer-resolution change in `deps.py` (read the board through the intent's people list without a seat). Owner to confirm. Affected-may-read needs the same change.
4. May the organiser add cards on their own wall without a seat? v1 gives the organiser counts, not cards, while rooms are open. Proposed: unchanged.
5. File 22 stores the wall session id in `stages[0].ref`; this file names `refs.wall_session_ids`. File 01 owner to pick one.
6. Withdraw an own card already on the wall before freeze: v1 note routes allow edit and discard of drafts; confirm withdrawal of a submitted card is allowed.
7. A wall run before this spec exists as a v1 session with no intent. Whether to wrap each in a synthetic Initiative record is for file 01.
8. Should observers see the stage bar's buttons greyed or hidden? Proposed: hidden, bar read-only.
