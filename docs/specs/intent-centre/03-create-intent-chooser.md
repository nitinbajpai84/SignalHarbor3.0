# 03. Create-intent chooser ("What do you want to do?")

Part of: Intent Centre v2. Depends on: 01 and 02 (the intent record and the types catalogue), 04 (the centre home that links here). Feeds: 22 (Initiative), 35 (Brainstorm), 38 (Weekly check-in), 41 (Problem), 43 (Decision), which own the start questions and the opening of each type; and 13 (Nira's draft lines).

## Purpose (three sentences)
The centre starts at what a person intends to do, not at the wall. This file is the chooser frame only: the person picks one of five intent types, or says it in a line and North proposes the type, and the chooser writes a draft and hands over to the per-type start questions. Everything after the hand-over (the questions, areas, people, time box and the "Open" button) is owned by the per-type file named in the hand-over table.

## Who uses it and when (role, moment, trigger)
- **Any signed-in person of the company** (Janet organiser, Aaron participant, Harvey owner, Katie analyst). Moment: they want to start something. Trigger: they open the centre, or press "Start an intent" anywhere.
- The person who starts an intent is its organiser (for a Problem the reporter, for a Decision the organiser; each per-type file says who else is named).
- Super admin and company admin: cannot reach this screen for a company draft. A draft is seen only by its creator (brief section 10, ruling 14).
- **Agents decide and draft; people act.** North classifies the free text and drafts a title. The person confirms the type. North never picks a type for the person and never opens an intent.

## Entry points (every route, link, Pulse line, button that leads here)
| From | What the person sees | Lands on |
|---|---|---|
| `/centre/intent` (CentrePage, spec 04) | Primary button "Start an intent" at the top of the page | `/centre/intent/new` |
| Centre side menu, Intent entry | Opens `/centre/intent/new` for a person with no open intents; otherwise the centre home | `/centre/intent/new` |
| Pulse page line from Nira ("You have 2 drafts waiting", spec 13) | Line with link "Finish your drafts" | `/centre/intent/new?type=<type>&draft=<id>` for one draft, the "Your drafts" panel for more |
| "Your drafts" row on the centre page | Row title, type chip, "Last touched", button "Carry on" | `/centre/intent/new?type=<type>&draft=<id>` |
| A closed intent's "Next" line (closure.next of kind initiative or problem, spec 20) | Button "Start the follow-on" | `/centre/intent/new?type=<type>&from=<intent id>`; tile preselected, `links.from` set |
| A weekly check-in item turned into a problem (spec 40) | Button "Open as a problem" | `/centre/intent/new?type=problem&from=<intent id>`; the item text arrives as the first answer |

URL parameters: `type` preselects a tile (still shown, still confirmable) or, with `draft`, goes straight to the per-type file; `from` sets `links.from`; `draft` resumes a draft. A route with no declaration is refused (default deny): the manifest declares `centre/intent/new` for every signed-in company role.

## Hand-over to the per-type start questions
After the person confirms a type, the chooser writes the draft (see Records) and goes to the route below. From there the named file owns the questions, the answers, the draft title and purpose, the areas, the people, the time box and the button that opens the intent.

| Type (key) | Tile text | File | Route after hand-over | Start questions | Opens with |
|---|---|---|---|---|---|
| Initiative (`initiative`) | Initiative | 22 | `/centre/intent/new?type=initiative&draft=<id>` (22 sets the step) | six | "Open this intent" (22) |
| Brainstorm (`brainstorm`) | Brainstorm | 35 | `/centre/intent/new?type=brainstorm&draft=<id>` (35 sets the step) | five | "Open this brainstorm" (35) |
| Weekly check-in (`pulse`) | Weekly check-in | 38 | `/centre/intent/new?type=pulse&draft=<id>` | four | "Start the check-in" (38) |
| Problem (`problem`) | Problem | 41 | `/centre/intent/new?type=problem&draft=<id>` (41 sets the step) | five | "Open this problem" (41) |
| Decision (`decision`) | Decision | 43 | `/centre/intent/new?type=decision&draft=<id>` | five | "Open this decision" (43) |

Who owns what, so nothing is specified twice:

| Item | Owned by | Note |
|---|---|---|
| Start questions, their wording keys and which are required | 22, 35, 38, 41, 43 (one each) | Ruling 2. Keys and field names in 02 follow these files |
| Areas picker | 22 (question 5), 35 (question 4), 38 (question 1), 41 (question 5), 43 (question 5) | Each file places it in its own question list; the picker is a chip multi-select over the profile areas |
| People picker | 22 (question 2), 35 (question 3), 38 (question 2), 41 (questions 4 and 5), 43 (questions 3 and 4) | Group rules per type are in each file; groups and roles are in 06 |
| Time box and "Extend" form | Default per type in 02; set on the question in 22 (question 6), 35 (question 5), 41 and 43 (by the date field); extend form in 07 | This file shows only the chip on the tile |
| "Open" button, validation, first stage, invitations | 22, 35, 38, 41, 43 (each its own button) | Opening writes `state: open`; see 01 for the lifecycle |
| Draft title and purpose drafted by North | the per-type file | Frame fields only appear in the summary card here |

## Screens, element by element

### Screen A. "What do you want to do?" (route `/centre/intent/new`)
**Layout at 1280.** Header region (title, one-line help). Under it, left two thirds: the free-text line, then the five type tiles in a grid of three plus two. Right third: the "Your drafts" panel and North's side line. Footer bar: "Back to the centre".
**Layout at 390.** One column. Order: header, free-text line, tiles as a vertical list of full-width cards (description under the title, 56 px minimum tap height), "Your drafts" collapsed to one line "2 drafts" that expands, North's line last. Footer bar sticks to the bottom.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Page title "What do you want to do?" | heading | The question, with the company name in the eyebrow | none | Signed-in company person | n/a |
| Help line | text | "Pick one, or tell North in your own words. You can change your mind before you open it." | none | all | n/a |
| Free-text line | field (single line, grows to 3 lines) | Placeholder "Tell North what you want to do". Counter appears past 400 characters; limit 600 | Enter or "Ask North" sends it; Shift+Enter adds a line | all | Placeholder shown; button disabled |
| "Ask North" | button | Label; spinner while North classifies | Calls `POST /api/intents/classify`; on success shows the proposal panel; on failure shows "North is not available" and leaves the tiles usable | all | Disabled when the field is empty |
| North proposal panel | agent line + panel | "This looks like a Brainstorm." One-sentence reason, the drafted title and a confidence word (Likely, Possible) | See next two rows | all | Hidden until a proposal exists |
| "Yes, a Brainstorm" (type name varies) | button | Type name | Writes the draft with that type, carries the typed line and drafted title to the per-type file, goes to the hand-over route | all | Hidden with the panel |
| "Pick another" | button | Label | Closes the panel, focuses the first tile, keeps the typed line to hand over as the first answer of the chosen type | all | Hidden with the panel |
| Tile: Initiative | button (radio-style card, one of five) | Title, line "Run a project or a new initiative with a clear goal and the people behind it.", chip with the default time box | Selects the tile, writes the draft, goes to the Initiative hand-over route (file 22) | all | n/a |
| Tile: Brainstorm | same | "Think with six or seven people about an idea or a problem." | same, to file 35 | all | n/a |
| Tile: Weekly check-in | same | "Start the weekly round for an operations area: what ran, what broke, what is on people's minds." | same, to file 38 | all | n/a |
| Tile: Problem | same | "Something is wrong in operations and needs an owner and a fix." | same, to file 41 | all | n/a |
| Tile: Decision | same | "One decision to make and record, with the options." | same, to file 43 | all | n/a |
| Tile time box chip | chip | Default time box read from the types catalogue (02), never typed into the screen | none | all | If the catalogue value is missing the chip says "Time box not set" and the tile cannot be chosen (see Open questions) |
| "Your drafts" panel | list | One row per own draft: title or "Untitled", type chip, "Last touched" as a date and time, "Carry on" and "Discard" | "Carry on" goes to the hand-over route with `draft=<id>`; the per-type file resumes at the first unanswered question. "Discard" asks "Discard this draft? It stays in your history as cancelled." then sets state to `cancelled` with reason "Discarded by the organiser" | The draft's creator only | "No drafts. Anything you start and leave is kept here." |
| North side line | agent line | One line that depends on state ("Not sure which one? Say it in a sentence and I will suggest.") | none | all | Always present |
| "Back to the centre" | button | Label | Goes to `/centre/intent`. Nothing is lost: a started intent is already a draft | all | n/a |
| Error state | panel | "We could not load the intent types. Try again." with "Try again" | Reloads the types catalogue and the drafts | all | Shown on load failure only |

### Screen B. The frame around the start questions (route `/centre/intent/new?type=<type>&draft=<id>`)
The per-type files place their questions inside this frame. The questions themselves are not listed here.
**Layout at 1280.** Left two thirds: the private-room conversation (North asks, the person answers, one question at a time). Right third: "Your intent so far" summary card. Top bar: type chip and the stepper whose steps the per-type file names.
**Layout at 390.** Conversation fills the screen; the summary becomes a bar at the top ("Question 3 of 6") and opens as a bottom sheet when tapped. Composer sticks above the keyboard.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Type chip with "Change type" | chip + link | The chosen type | Back to Screen A with the answers kept; if the new type has a question with the same key the answer is reused, otherwise it is parked in the draft, not deleted | creator | n/a |
| Stepper | list | The steps named by the per-type file, current marked, finished ticked | Click or Enter on a finished step jumps to it. Later steps are not clickable | creator | First step only on arrival |
| North question | agent line | The current question in North's voice, with "Why I ask" (one line). Wording and keys come from the per-type file | none | creator | First question shown on arrival |
| Answer composer | field (multi-line) | Placeholder depends on the question | Enter sends, Shift+Enter new line; the answer is saved to the draft on send | creator | Send disabled when empty, unless the question is optional, then "Skip" shows |
| "Skip" | button | Only on optional questions | Records the answer as unknown (`mark: unknown`), asks the next | creator | Hidden on required questions |
| Voice bar | control | Same as the room (M1-P06) | Same | creator | "Voice is off" when not enabled |
| Answer read-back | agent line | North's one-line read-back with "That is right" and "Let me correct it" | "That is right" moves on; "Let me correct it" puts the answer back in the composer (the room's correction flow) | creator | none |
| Summary card | panel | Type, title, purpose and the answers so far, each with "Change" | "Change" reopens that question | creator | "Nothing answered yet." |
| "Save and leave" | button | Label | Saves the draft, goes to `/centre/intent` with the toast "Draft kept in Your drafts" | creator | n/a |

Reuse: the transcript list, message bubbles, composer, voice bar, "Ask Nira" button and agent chip are the private room components (`RoomView` in `ui/src/modules/m1_intent/private_room/PrivateRoomScreen.tsx`), driven through a new thin hook that talks to the intent route instead of `/sessions/{id}/room`. The room's notes panel, library panel and finish panel are not used.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)
1. The person presses "Start an intent". The screen loads the five types from the catalogue (02) and the person's drafts. North's side line greets.
2. The person picks a tile or types a line and presses "Ask North".
3. **North classifies** the line and returns a type, a reason, a confidence word and a drafted title. The panel appears. The person presses "Yes, a Brainstorm" or "Pick another" (then picks a tile). North never skips this confirmation.
4. On the first choice the screen writes a **draft** intent (state `draft`, type, created_by, company, id, an `outcome` object shaped for the type). From now on every answer is saved to it.
5. The screen goes to the hand-over route for the type. The per-type file takes over (see the hand-over table). North asks the first question there; the frame in Screen B shows the conversation, read-back and summary card.
6. Leaving: the person presses "Back to the centre" on Screen A, or "Save and leave" on Screen B. The draft stays under "Your drafts". The journey of the chosen type ends at the per-type file's "Open" button, which is not part of this file.

**Keyboard flow.** Tab order on Screen A: free-text line, "Ask North", the five tiles in reading order (a radio group: arrow keys move, Enter or Space selects), "Your drafts" rows ("Carry on", "Discard"), "Back to the centre". On Screen B: stepper, North question (focusable, read by screen readers through `aria-live="polite"`), composer, "Send", "Skip", voice bar, "Save and leave". Escape closes the bottom sheet; focus returns to the button that opened it. Focus moves to the first new element after each step change and is announced. No action needs a pointer.

**Abandoning halfway.** Closing the tab, pressing "Back", "Save and leave", signing out, or an idle timeout all leave the draft as it is (it is written after every answer). The draft appears under "Your drafts" and on the centre page. A draft untouched for 30 days is not deleted: Nira marks it "Waiting for you" (auto-cancel is an Open question). Nobody else sees a draft. "Discard" turns it to `cancelled` with a reason; it is kept and shown in Past (ruling 14).

## States and transitions (table: state, who moves it, to what, what is written)
| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | The person picks a tile or confirms North's proposal | draft | New folder `intents/<id>/` with `intent.json`: id, type, company, created_by, created_at, state `draft`, `stages: []`, `outcome` shaped for the type (02), `north_proposal` if used |
| draft | The person answers a question | draft | The answer in `start_answers` and `draft_updated_at` (the fields the per-type file adds are in that file) |
| draft | The person presses "Discard" | cancelled | `state: cancelled`, `closure.next: [{kind: nothing, reason: "Discarded by the organiser"}]` |
| draft (30 days) | Nobody | draft | Nothing; Nira's line only |
| draft | The person presses the per-type "Open" button | open | Owned by 22, 35, 38, 41, 43 and 01 |

## Records read and written (file or route, fields; mark Existing or New)
| Item | Read or write | Fields | Status |
|---|---|---|---|
| `intents/<id>/intent.json` through `sh_platform/jsonfile.py` (`read_json_strict`, `write_json_atomic`, `lock_for`) | write, read | The intent record (brief section 3); this file writes only the draft fields above | New file per intent, Existing helper |
| Intent types catalogue (02): title, chooser line, default time box per type | read | `type, title, chooser_line, time_box_days` | New (defined in 02) |
| `POST /api/intents/classify` | write-free call | In: the free text (names tokenised through the gateway). Out: `{type, reason, confidence, title}` | New; goes through the egress gateway like the room's North call |
| `POST /api/intents` (create draft), `PATCH /api/intents/<id>` (answers and fields), `POST /api/intents/<id>/cancel` (discard) | write | See the transitions table | New |
| `GET /api/intents?mine=draft` | read | The caller's drafts: id, type, title, `draft_updated_at` | New |
| `POST /api/intents/<id>/messages` | write | One start answer, North's reply and read-back, in the same turn shape as the room's `post_message` | New (shape reused from `modules/m1_intent/api/private_room.py`, `post_message` L430-L471) |
| `modules/m1_intent/manifest.yaml`: route `centre/intent/new` for every signed-in company role | write | Declaration | New entry |
| `/api/intents/<id>/open` | not used here | Owned by the per-type files and 01 | New (other files) |

## Fields this feature adds to the intent record
| Field | Meaning |
|---|---|
| `north_proposal: {text, type, confidence, accepted: bool, picked_type}` or null | What the person typed and what North proposed; kept so a wrong classification is visible and countable |
| `draft_updated_at` | Last touch of the draft; drives "Last touched" |
| `opened_by` | The person who pressed the per-type "Open" button (written by that button, named here so the counter below traces to it) |

`start_answers` is defined by 02 (`[{id, answer, mark: stated|unknown}]`); this file only writes to it through the room route. No field of the brief's section 3 is renamed.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)
- **North, classifying.** Reads the free-text line, returns one type, a one-sentence reason, a confidence word and a drafted title. It never picks for the person. If it cannot tell, it returns "Not sure", shows no proposal and asks one question ("Do you want people to think with you, or is something already broken?"). Person acts: "Yes, a ..." or "Pick another".
- **North, asking.** One question at a time, in the room's conversation style, with a read-back after each answer. The questions are the per-type file's. Person acts: confirm or correct each answer.
- **North, when off or slow.** The tiles still work and the questions use fixed wording from the per-type file. The screen says so in one line.
- **Lens.** Not used here.
- **Nira.** Shows "Your drafts" waiting lines on the Pulse page. Does not write to the intent. Invitations after open belong to the per-type files and 06.

## Rules (visibility, time box, who may do what)
- Only the creator sees or edits a draft. Admin and super admin do not see drafts (a draft has no areas yet).
- The pickers inside the per-type files list only what the viewer may see (profile `view.read` rules); that is specified there.
- The default time box shown on a tile is the catalogue's; setting and extending it is owned by the per-type files and 07.
- Every start answer is stored. Nothing typed here leaves the machine except through the egress gateway with names tokenised (egress rules, D-007).
- Routes follow brief section 10 ruling 1: page `/centre/intent/new` with `type`, `from` and `draft`; API under `/api/intents/...`.
- Copy: no game words, no model or vendor names (agents are North, Lens, Nira), British spelling, no em dashes. "Weekly check-in" on screen; "Pulse" alone means the daily page.

## Counters and measures of this feature (numbers only, each traced to a record)
Counts are exact. Any average, if added later, follows ruling 8 ("Fewer than five" below five records).
| Measure | Traced to |
|---|---|
| Drafts waiting (per person, shown only to that person) | count of `intents/*/intent.json` with `state: draft` and `created_by` the person |
| Intents opened from free text, and from a tile | count of intents with `north_proposal` not null and `opened_by` set, and with `north_proposal` null and `opened_by` set |
| North proposal accepted | `north_proposal.accepted` over `north_proposal` present; "Not available yet: no proposals recorded" until one exists |
| Time from first tile to open (per intent) | `stages[0].opened_at` minus `created_at`; "Not available yet" until one intent is opened |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)
Searches run: `graft ask` for the centre page, wall and room components, North conversation routes, company profile people list. All paths below were checked to exist in this repo on 7 Oct 2026.
| Existing | Decision |
|---|---|
| `ui/src/pages/CentrePage.tsx` (`CentrePage` L121, `buildRooms` L77, `startWall` L138, `get` L67, `Fetched` L32) | Reshaped. The page keeps its place at `/centre/intent`; the chooser is a new route beside it (`ui/src/App.tsx` L106 pattern, a new `Route path="intent/new"`). `get` and `Fetched` are reused for loading. Copy goes in a new `intentNewCopy.ts` in the style of `ui/src/pages/centreCopy.ts` |
| `ui/src/modules/m1_intent/private_room/PrivateRoomScreen.tsx` (`RoomView` L111: transcript, message bubble, composer, `VoiceBar`, `AgentChip`, correction flow, `askNira`) | Copied and reshaped: layout and the read-back and correction pattern are reused as components. The data hook changes (`useRoom.ts`, `roomApi.ts` `sendMessage` L120 become a start-answer hook). Notes, library and finish panels are not used: they belong to the wall |
| `modules/m1_intent/api/private_room.py` (`_converse` L312, `post_message` L430, `_check` L396, `_model_available` L288) | Reshaped. Same turn shape and same "North off" fallback; a new route file for intents. The model call stays through the gateway |
| `ui/src/modules/m1_intent/PrepareWizard.tsx` and `form.ts` | Reshaped: its save-as-you-go behaviour is the model for draft saving. Not copied whole because it prepares an M1 session, not an intent record |
| `sh_platform/jsonfile.py` (`lock_for` L19, `read_json_strict` L25, `write_json_atomic` L41) | Reused unchanged for the one-folder-per-intent store |
| `sh_platform/profile/api.py` (`get_profile` L72) and `profile/view.py` | Not used on this screen (it needs only the company name and the drafts). Used unchanged by the pickers in 22, 35, 38, 41, 43 |
| `ui/src/modules/m1_intent/timer/StageTimer.tsx` and `ui/src/modules/m1_intent/api.ts` | Not used here: the extend form moved to 07 |
| `sh_platform/interview/engine.py`, `modules/m3_connect/domain/from_profile.py` | Not used here: people sources belong to the per-type pickers |
| `ui/src/pages/PeopleLinks.tsx` | Not used: links accounts to profile people, not a chooser |
| `tools/route_task.py` (the Jev router) | Not used: it routes build tasks. The classify call is its own small route |
| Genuinely new | Five type tiles, the classify route, the intent create, patch and cancel routes, the "Your drafts" list |

## Not in this feature
- The start questions, areas, people, time box and the "Open" step of each type (22, 35, 38, 41, 43).
- The extend form and the clock (07). People and roles (06).
- The centre home and the wall of intents (04).
- Sharing links and closing (11 and 09).
- Adding people or areas to the company profile.
- Gap analysis and Moment of truth (Build).

## Open questions
1. Query parameters `draft` and `step` are used by this file and the per-type files but are not in the ruling 1 spelling (`type`, `from`). Proposed: add them to the routes list. Needs the orchestrator.
2. Files 02, 13, 41 and 43 still use other spellings for the same route (`/intent/new/<type>`, `/centre/intent/new/<type>?draft=`, `/intents/new?type=decision`, and 41 omits `type`). They need the ruling 1 fix in the review wave.
3. Does a draft auto-cancel after some days? Proposed: never, Nira reminds.
4. If the catalogue has no default time box for a type, should the tile be blocked ("Time box not set")? Proposed: yes.
5. Where does the types catalogue live (pack default, company override)? Owned by 02; this file reads whatever 02 decides.
6. `start_answers` shape: this file follows 02 (`{id, answer, mark}`); 20 adds `prefilled_from`. Confirm there is one shape.
7. Can a person start an intent on behalf of someone else (Janet opens a Problem with Harvey as owner)? Proposed: yes, the per-type file names the owner and invites; the opener stays organiser.
