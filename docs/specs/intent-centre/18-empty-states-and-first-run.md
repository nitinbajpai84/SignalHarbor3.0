# 18. Empty states and first run

Part of: Intent Centre v2. Depends on: 01 (intent record), 02 (types catalogue), 03 (chooser), 04 (home), 06 (people and roles), 49 (pack suggestions), and the per-type specs for Brainstorm (35 to 37), Weekly check-in (38 to 40), Problem (41, 42) and Decision (43), the wall (23), Define (26 to 31), closure (09), past intents (12), search (15) and share (11), referred to below by screen name. Feeds: every one of those specs, which must use the copy in this file for their empty cases.

## Purpose (three sentences)
This file says what a brand new company and a brand new person see in the Intent Centre, and fixes the words and the one action for every empty state on every screen. An empty screen is never blank and never shows a zero that looks like a fact; it says what is missing and what the person can do about it. Industry suggestions on first run come from the pack, are labelled as suggestions, and are never the company's own policy.

## Who uses it and when (role, moment, trigger)
| Role | Moment | Trigger |
|---|---|---|
| Company admin (Grace, first person in a new company) | First sign-in to a company with the Intent module on and no intent records | Opens `/centre/intent` |
| Any signed-in person with no areas tagged (Aaron on his first day) | First sign-in, before Grace has tagged him to a department or ops area | Opens `/centre/intent` |
| Organiser (Janet) | Has intents, but one screen has nothing to show (no past intents, no search hits, no check-in week yet) | Opens that screen |
| Participant, affected person, owner (Aaron, Harvey) | Opens an intent whose section is empty (no ideas on the wall yet, no decision recorded yet) | Opens the section |
| Super admin | Never sees content; sees only the existence list, which has its own empty line (below) | Opens the company overview |

Agents decide and draft; people act. North writes the first-run opening line and picks which pack suggestions to show first. Nobody is enrolled, tagged or started by an agent. The admin tags areas; the person presses "Start" or "Start your first intent".

## Entry points (every route, link, Pulse line, button that leads here)
| From | What the person sees | Lands on |
|---|---|---|
| Sign-in, first time, company with the Intent module on | The centre menu entry "Intent Centre" | `/centre/intent` (spec 04 Screen 2, extended here as the first-run home; route as fixed by brief section 10, ruling 1) |
| Daily Pulse page line from Nira, person with no areas | "You are not tagged to an area yet, so you see no intents. Ask your company admin." | `/centre/intent` (the no-areas panel) |
| Daily Pulse page line from Nira, company with no intents | "Nothing has been started yet. Start the first intent." | `/centre/intent` |
| Any screen listed in the empty-state table | The empty panel itself | The screen's own route; the action button lands as named in the table |
| Company admin people page (existing `ui/src/pages/PeopleLinks.tsx`, `/centre/control`) | "Tag areas" next to a person with no areas | The existing people and roles screen (spec 06 owns the tag editor) |

No new route is added by this file. The first-run home is spec 04's `/centre/intent` in an empty or no-areas state. The manifest already declares that route; the other screens keep their own declarations (default deny).

## Screens, element by element

### Screen 1. First run for a company with no intents (route `/centre/intent`)
Shown when the company has the Intent module on and the intents route returns zero records visible to the viewer, and the viewer is tagged to at least one area (or is the company admin). This replaces the copy of spec 04 Screen 2 where the two differ; the structure (five type rows, no counters, earlier-work link) is kept.

**Layout at 1280.** Header (centre title, no filters, no lanes, no counters). One centred column. Top: the North opening line. Below it the heading "Start your first intent". Then a block "Suggested first, for a family office" with two or three suggestion cards. Then a block "The five kinds of intent" with five rows. Footnote at the bottom.
**Layout at 390.** One column. North line, heading, suggestion cards as a vertical list (full width), five rows stacked, each with a full-width "Start" button. Footnote last.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| North opening line | Agent line | "Welcome. Nothing has been started at Ardmore yet. Tell me what you intend to do and I will ask the right questions and keep the clock." (company name from the company record; "your company" if no name) | None | Every viewer of this screen | Never empty; if North cannot be reached the fixed line "Nothing has been started yet." is shown with no agent mark |
| Heading "Start your first intent" | Heading | The words, plus the eyebrow "Intent Centre" | None | Every viewer | n/a |
| Help line | Text | "An intent is one thing the company wants to do, with a clear end date and a named person who owns it." | None | Every viewer | n/a |
| Suggestion block heading | Text + label | "Suggested first, for a family office" ("family office" is the pack `label`) and the strip label fixed by file 49: "Suggested from what others in the industry usually do" with the source chip "Pack: Family office, version 1" (existing `SUGGESTION_LABEL` in `sh_platform/packs.py` stays for other screens; see Open questions) | None | Every viewer | Block hidden when the pack has no suggestions (see "No pack" below) |
| Suggestion card (dashed, as file 49) | Card with type chip, title, purpose line, button | Chip (Initiative, Weekly check-in or Decision), title and purpose from `first_intents.yaml`, tag "Suggestion" | "Start this" opens the chooser at `/centre/intent/new?type=<type>` (spec 03) with title, purpose and areas prefilled as a draft. The person can change all of it. Nothing is written until the person presses "Open this intent" in the chooser | Roles who may start an intent | For viewers who may not start: the card is text only, no button |
| "Not for us" on a card | Button | Label | Hides the card for this person only. Owned by file 49 (its `suggestion_marks` write); this file adds no write | Roles who may start | Not drawn for viewers who may not start |
| Five type rows | Row: type chip, one line, button | The five lines in the next table; chip with the default time box | "Start" opens `/centre/intent/new?type=<type>` with that type selected | Roles who may start | For viewers who may not start: text only, and the line "Your company admin can start the first intent." |
| "Not sure which one?" link | Link | "Tell North in your own words" | Opens `/centre/intent/new` with the free-text line focused | Roles who may start | Hidden for others |
| Earlier-work link | Link | "Earlier work: N walls and M charters" | Opens the existing walls and charters screens (existing routes; their v2 spellings are file 04's) | Company admin, organiser | Not rendered when N and M are both zero. If a count cannot be read: "Earlier work: Not available yet (the sessions list did not load)" |
| Footnote | Footnote | "Counters and lanes appear after the first intent is opened." | None | Every viewer | n/a |

The five type lines (one line each, from the brief's type table, with the on-screen name "Weekly check-in" (ruling 3; the record key stays `pulse`); the time box chip is read from the type settings, never typed on the screen):

| Type | Line on the row | Chip |
|---|---|---|
| Initiative | "Run a project or a new initiative, with a clear goal and the people behind it." | "10 working days" |
| Brainstorm | "Think with four to eight people about an idea or a problem." | "3 working days" |
| Weekly check-in | "Every week, an operations area says what ran, what broke and what is on its mind." | "One week, repeats" |
| Problem | "Something is wrong in operations and needs an owner and a fix." | "5 working days" |
| Decision | "One decision to make and record, with the options considered." | "2 working days" |

**Which suggestions show first.** North reads the pack file `intents/first_intents.yaml` through the loader (see "Records read and written") and shows the cards in the pack's order, dropping any this person has dismissed or picked up (file 49). The family office pack gives three: an Initiative ("Report to the family on one page every quarter"), a Weekly check-in ("Weekly check-in for operations") and a Decision ("Decide whether to consolidate custodians"). North may reorder them using the company's context documents, never add one that is not in the pack. If the company has uploaded context that already names a pain point, the matching card moves first and the tag still says "Suggestion". The cap of three is file 49's, not set here.

**No pack for the industry.** The pack loader returns `EmptyPack` (never another industry's content, per `industry.md`). The suggestion block is not drawn, and one line replaces it: "No industry knowledge is available yet for this industry. You can still start from the five kinds below." (the opening of the existing `EmptyPack.message`, as file 49 reuses it) The five rows are unaffected.

### Screen 2. First run for a person with no areas tagged (route `/centre/intent`)
Shown when the signed-in person is a company person (not admin, not super admin) and `areas` for them is empty in the company profile. The company may have intents; this person sees none of them because visibility follows areas (brief section 4).

**Layout at 1280.** Header. One centred panel with the North line, the explanation, and one button. No lanes, no counters, no past intents.
**Layout at 390.** The same panel at full width; the button is full width.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| North line | Agent line | "Hello Aaron. I cannot show you any intents yet because you are not tagged to a department or operations area." | None | The person | Fixed text without the name if the display name is missing |
| Explanation | Text | "Intents are shown to the people in the areas they affect. Your company admin tags you to your areas. Until then you will only see an intent if someone names you in it or sends you a share link." | None | The person | n/a |
| Line to the company admin | Text with copy button | "Please tag me to my department or operations area in the Intent Centre. My name is Aaron and I sign in as aaron@ardmore.example." (synthetic; the real sign-in name is inserted at run time) | "Copy request" copies the text; confirmation "Copied". Nothing is sent. Sending a message on the person's behalf is not done by this screen | The person | Never empty |
| "Who is my company admin?" line | Text | "Company admin: Grace" if the company record names an admin; otherwise "Not available yet (the company record names no admin)" | None | The person | As stated |
| "Start an intent" button | Button | Label | Opens `/centre/intent/new`. A person with no areas may start an intent if the company allows it; the areas step then makes them choose areas (spec 03). Hidden if the company does not allow it, with the line "Your company admin starts intents for now." | Roles who may start | Hidden or replaced as stated |
| Intents they were named in | List | Any intent where the person is participant, affected, observer or named on a share link, shown as ordinary cards (spec 04) above this panel | Opens the intent | The person | When none, the panel stands alone |

A person with no areas who is named in an intent does not see Screen 2 alone; they see their cards with a one-line note under them: "You are not tagged to an area yet. You only see intents you are named in."

## Every empty state (the table)
Wording rules: British spelling, short sentences, no em dashes, no agent vendor names, no game words. Each empty state names what is missing and offers at most one action. The "Offers" column is the action; "None" means the screen explains and offers nothing because the person has nothing to do.

| Screen | Element | Copy | Offers |
|---|---|---|---|
| Home (`/centre/intent`) | Whole page, company with no intents | See Screen 1 | "Start" on five rows, suggestion cards |
| Home | Whole page, person with no areas | See Screen 2 | "Copy request", "Start an intent" if allowed |
| Home | "Your turn" lane (spec 04) | "Nothing is waiting for you." | None |
| Home | Running lane | "No intents are running in your areas." | "Start an intent" |
| Home | Past intents card | "Nothing has been closed yet. Closed intents will appear here with what came out of them." | None |
| Home | Counter tile with no source | "Not available yet" and under it the missing source (see the rule below) | None |
| Chooser (`/centre/intent/new`) | "Your drafts" panel | "No drafts. Anything you start and leave is kept here." | None |
| Chooser | Free-text line | Placeholder "Tell North what you want to do" | "Ask North" (disabled until text) |
| Chooser | Areas step, company has no areas defined | "No areas are set up for your company yet. Ask your company admin to add departments or operations areas." | "Copy request" (same as Screen 2) |
| Chooser | People step, no one in the chosen areas | "Nobody is tagged to these areas yet. You can still open the intent with yourself as organiser and add people later." | "Open this intent" stays enabled; "Choose other areas" |
| Wall (`/centre/intent/<id>/wall`) | Empty wall | "No ideas on the wall yet. Add the first one, or wait for others to add theirs." | "Add an idea" for participants; none for observers |
| Wall | Cluster list | "Nothing to group yet. North groups ideas once there are at least five." (the five is the guard in `egress.md`; see Open questions) | None |
| Wall | Sealed or anonymous note count | "Not available yet (no notes have been added)" | None |
| Define (`/centre/intent/<id>/define`: clusters, shelves, glossary, catalogue, process map, data sources) | Each panel with no draft | "Lens has not drafted this yet. It starts when the wall has ideas to work from." plus the single missing item named, for example "Missing: ideas on the wall" | "Ask Lens to draft" when the prerequisite exists; otherwise none |
| Define | Business glossary, no terms | "No terms yet. Lens drafts them from the wall and your documents. You confirm each one." | "Add a term" |
| Define | Data sources map, no sources | "No data sources are listed yet. Missing: files or feeds brought in." | "Bring files" (existing `/centre/intent/bring` route in `ui/src/App.tsx`; not in the ruling 1 list, see Open questions) |
| Define | Charter | "No charter yet. It is drafted when the definitions are confirmed." | None |
| Brainstorm | Before invitation | "Nobody has been invited yet. Add four to eight people." | "Invite people" for the organiser |
| Brainstorm | Idea list, session not started | "The live session has not started. Ideas appear here as people add them." | "Start the session" for the organiser |
| Brainstorm | Chosen idea | "No idea chosen yet. The organiser chooses one when the session ends." | "Choose an idea" for the organiser |
| Weekly check-in (`/centre/intent/<id>/week`) | Page before the first week | "No week has been recorded yet. The first round opens on the date you set." plus the date, or "Not available yet (no start date is set)" | "Set the first round" for the organiser |
| Weekly check-in | Week with no items | "Nobody has added anything for this week." | "Add an item" for people in the area |
| Weekly check-in | Items awaiting a fate | "Every item from this week has a fate." | None |
| Problem | Before an owner | "No owner yet. A problem needs one named person." | "Name an owner" for the organiser |
| Problem | Root cause and fix | "Not recorded yet. The owner adds the root cause and the fix before closing." | "Record root cause" for the owner |
| Problem | Affected people | "Nobody is named as affected. Add the people or areas this touches." | "Add affected people" |
| Decision | Options | "No options yet. Add the options so the record shows what was weighed." | "Add an option" for the decider and advisers |
| Decision | Decision record | "Not decided yet. The decider records the decision and the reason." | "Record the decision" for the decider |
| Closure (`/centre/intent/<id>/close`) | Closure draft | "North has not drafted a closure yet. It drafts one when the last stage is closed or the time box ends." | None |
| Closure | "Next" list | "Nothing follows from this intent." Offered kinds: initiative, backlog, problem, nothing, each needing a reason | "Add what comes next" for the closer |
| Closure | Ratings | "No ratings yet." The exact count shows once there is one rating; an aggregate shows only from three ratings, below that "Fewer than three ratings" (ruling 8). A Weekly check-in series and its weeks are not rated (ruling 3) | "Rate this intent" for participants of rateable intents |
| Past intents (`/centre/intent/past`) | List, no closed or cancelled intents | "Nothing has been closed yet. Closed and cancelled intents are kept here, never deleted." | None |
| Past intents | List, filters match nothing | "No past intents match these filters." | "Clear filters" |
| Search | Before typing | "Search your intents by title, purpose, person or area. You only see what you may see." | None |
| Search | No hits | "Nothing found for this search. Intents you may not open show only their title, so try the title." | "Clear search" |
| Search | No intents to search | "There is nothing to search yet." | "Start an intent" |
| Share (organiser view, `/centre/intent/<id>/share`) | No link yet | "This intent is not shared. Sharing is by named people and is read only." | "Share with named people" |
| Share (recipient view, link expired or removed; entry `POST /api/modules/m1_intent/shared/view`, ruling 1) | Whole page | "This link no longer opens an intent. Ask the organiser to share it again." | None |
| Share | Named people list | "Nobody is named yet." | "Add a person" |
| Super admin existence list (`/centre/control/intents`) | Whole list | "No intents exist for this company." (existence only, never content; with the company switch "titles private to the company" on, titles are not shown either, ruling 5) | None |
| Every screen | Load failure | "Not available yet. This did not load." with "Try again" (existing `ScreenState` error state) | "Try again" |

## The rule: never show 0 when there is no data
1. A number is shown only when a record it traces to has been read. A count of "0" is a fact: it is allowed only when the source was read successfully and held nothing, and only on a screen that is not itself an empty state.
2. When the source is missing, unread, failed to load, or has not started, the number is replaced by "Not available yet", and a second line names what is missing: "Missing: no intents have been opened", "Missing: no ratings have been given", "Missing: the check-in has no recorded week", "Missing: the intents list did not load".
3. A rate, average or percentage needs a denominator of at least one. With none, it reads "Not available yet" and names the missing base: "Missing: no closed intents to measure". A mean, median or per-person figure, and any anonymous or sealed note count, shows "Fewer than five" below five records; a ratings aggregate shows "Fewer than three ratings" below three (ruling 8, with the guard in `egress.md`). Exact counts stay exact. No per-person average exists anywhere (ruling 15).
4. "Days left" (in the company's time zone from the profile, else UTC) for an intent with no time box reads "Not available yet (no end date is set)". It is never shown as 0 days.
5. A time since an event that did not happen is never "0". "Last closed" with no closed intent reads "Not available yet (nothing has been closed)".
6. The words come from one constant, the existing `shellText.notYet` ("Not available yet") in `ui/src/shell/copy.ts` and `NA` in `CentrePage.tsx`; no screen types its own variant. The "Missing:" line is a second string per tile, supplied by the tile.
7. Screens under the first-run home show no counters at all (they would all be "Not available yet"); the footnote says when they appear.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)
First run, company (Grace is the first admin of Ardmore; Janet is an organiser):
1. Grace signs in. The shell opens her start page; the centre menu shows "Intent Centre".
2. She opens `/centre/intent`. `GET /api/intents` returns nothing. The page shows Screen 1. Between steps, North reads `packs/family_office/1/intents/first_intents.yaml` and picks the suggestions (it reads, it does not write).
3. North's opening line appears at the top. Grace reads the three suggestion cards and the five rows.
4. She presses "Start this" on the Initiative card. The chooser opens at `/centre/intent/new?type=initiative` with the pack title, purpose and areas as her draft.
5. She edits the draft, answers the Initiative start questions (file 22 is canonical, ruling 2), picks areas and people, and presses "Open this intent". The intent is written; North starts the clock.
6. She returns to `/centre/intent`. The page now has one running intent, so Screen 1 is gone and the counters appear (Not available yet where no record exists).

First run, person (Aaron has no areas):
1. Aaron signs in and opens `/centre/intent`. The route returns nothing for him and his profile has no areas. He sees Screen 2.
2. He presses "Copy request" and pastes it into his own message to Grace. Nothing is sent by the screen.
3. Grace tags him to Finance Operations in the people screen (spec 06).
4. Aaron reloads. Intents in Finance Operations now show as cards he can see the existence of; he opens only those he is named in.

## States and transitions (table: state, who moves it, to what, what is written)
| State | Who moves it | To what | What is written |
|---|---|---|---|
| Company has no intents (first-run home) | The organiser presses "Open this intent" in the chooser | Home shows lanes and counters | The first intent record `intents/<id>/intent.json` (ruling 12). Nothing else is written by this feature |
| Person has no areas (Screen 2) | The company admin tags the person | Home shows the intents of those areas | Company profile areas (written by spec 06, not here) |
| Suggestion card shown | The person presses "Start this" | Chooser with type, title, purpose and areas prefilled | Nothing until "Open this intent". An abandoned chooser becomes a draft by the chooser's own rule |
| Suggestion card dismissed | The person, by "Not for us" (file 49) | Hidden for that person | A mark in file 49's `suggestion_marks`, written by 49. Whether the cards also go once the company has any intent is an Open question |
| Empty section (any screen) | The person acts on the single offered action | The section holds its first item | Whatever the owning spec writes for that item |
| "Not available yet" counter | The source record is written or read successfully | The counter shows its figure | None (display only) |

## Records read and written (file or route, fields; mark Existing or New)
| Record or route | Fields used | Mark |
|---|---|---|
| `GET /api/intents` (spec 04; API convention `/api/intents/...`, ruling 1) | Count of visible records, the viewer's areas | New (spec 04) |
| Company profile through `sh_platform/profile/view.py` | Viewer's `areas`, role, display name | Existing |
| Company record | Company name, company admin display name | Existing |
| `packs/<industry>/<v>/intents/first_intents.yaml` through `Pack.intents_section("first_intents")` (file 49) | Per suggestion: `id, type, title, purpose, areas, why, start_answers` | New pack file and a small loader addition, both defined and owned by file 49. This file adds no pack file |
| `GET /api/intents/suggestions?kind=first` (file 49 spells it `/api/company/intents/suggestions`; see Open questions) | `label, pack, items, dismissed_count, empty_message` | New (file 49) |
| `PackLoader.load(industry).suggestion_label` | The label text | Existing |
| `EmptyPack.message` | "No industry knowledge is available yet for this industry..." | Existing (not shown verbatim; this file's own line is used so the wording fits the screen) |
| Type settings (spec 02) | Default time box per type | New (spec 02) |
| Writes | None by this feature. "Not for us" writes through file 49 | n/a |

## Fields this feature adds to the intent record
None. First run and empty states are display only. The suggestion content lives in file 49's `intents/first_intents.yaml` (family office, synthetic, a suggestion file, never policy); `from_pack` on the intent record is file 49's field, set at "Open this intent", not here. The three starters, as file 49 fixes them:

```
# packs/family_office/1/intents/first_intents.yaml (owned by file 49)
suggestions:
  - {id: fo-initiative-family-reporting, type: initiative, title: "Report to the family on one page every quarter"}
  - {id: fo-checkin-operations,          type: pulse,      title: "Weekly check-in for operations"}
  - {id: fo-decision-custodian,          type: decision,   title: "Decide whether to consolidate custodians"}
```

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)
- **North** drafts the opening line on first run (company name and the fixed sentence), and orders the pack's first intents (file 49). It reads the pack and the company's context documents; it never invents a starter, never opens an intent and never tags a person. If North is not available the screen shows the fixed line and the same cards, so first run never depends on an agent. The moment a person acts: pressing "Start" or "Start this".
- **Lens** does nothing on first run. In Define, an empty panel says Lens has not drafted yet and names what it is waiting for. The moment a person acts: "Ask Lens to draft" once the prerequisite exists.
- **Nira** writes the line on the daily Pulse page for a company with no intents and for a person with no areas (see Entry points). It feeds nothing else here. The moment a person acts: following the link.
- Agents never sign. Nobody is tagged to an area by an agent.

## Rules (visibility, time box, who may do what)
- An empty state shows only what the viewer is allowed to know. A person who cannot open an intent never sees an empty-state line that reveals its content ("no ideas yet" is a content fact; they see only title, purpose, stage, organiser and outcome).
- Pack suggestions are labelled "Suggestion" on each card and carry the pack label. They are never stored as company policy, never copied into the intent without the person pressing "Open this intent" (then recorded as provenance by file 49), and never shown when the pack is empty.
- A company with no pack for its industry gets the honest line above, never another industry's content (`industry.md`). No industry word is hardcoded in the screen; "family office" in the example comes from the pack's `label` (`Family office`).
- The first-run home and Screen 2 are shown to a viewer only; the company admin's first-run home also shows the "Tag areas" link in the explanation line for a company with no areas defined.
- The super admin sees the existence list or its empty line, never content.
- Affected people see an empty section only as far as they may open it: existence, title, purpose, stage, clock, people and outcome, and content only where the organiser allowed it or a share names them. Observers read as a participant does and never write (ruling 4).
- Empty screens have no time box. Time boxes begin when an intent is opened (spec 01).
- Anonymous and sealed material keeps the v1 rules (D-013, seal): empty states never disclose that sealed material exists unless the viewer may see it.
- Every empty state carries at most one action, and that action is available only to the roles in the table.

## Counters and measures of this feature (numbers only, each traced to a record)
| Counter | Rule | Source | When it reads "Not available yet" |
|---|---|---|---|
| Companies with no intents (control plane, super admin) | Count of companies where the intents route returns zero records | Company intent index | The index was not readable: "Missing: the company index did not load" |
| People with no areas (company admin view) | Count of company people whose profile areas list is empty | Company profile | "Missing: the people list did not load" |
| First-run starts from a suggestion | Count of intents opened from "Start with this" | `intent.links` carries no such flag; not tracked in v2 | "Not available yet (no record of where an intent started)". See Open questions |

No other counter is added. Home counters belong to spec 04.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)
Searches run: grep over `ui/src` for `ScreenState`, `EmptyState`, `Not available yet`, `notYet`; reads of `ui/src/components/ScreenState.tsx`, `ui/src/design/parts.tsx` (lines 185 to 197), `ui/src/shell/copy.ts` (lines 1 to 25), `sh_platform/packs.py` (lines 1 to 110) and the family office pack folder. Graft was not run for this spec; the files were small and named in the task.
| Existing | What it does | Decision |
|---|---|---|
| `ui/src/components/ScreenState.tsx` (states loading, empty, error, refused, populated; `message` replaces the default) | One-line empty, error and refused states used by every module screen | Reused for each empty table row that is a single line, and for the load-failure row. Not enough for Screens 1 and 2, which need cards and buttons |
| `ui/src/design/parts.tsx` `EmptyState` (lines 189 to 197: title, lines, links) | Card with a title, lines and links; used in `ui/src/design/Gallery.tsx` (line 56) and `ui/src/pages/PulsePage.tsx` (lines 158, 250) | Reused for Screen 2 and for every table row that needs one action as a link. Reshaped only by passing a button as a link; no change to the component |
| `ui/src/shell/copy.ts` `shellText.notYet` (line 17), `NA` in `ui/src/pages/CentrePage.tsx` (line 17) and `NOT_YET` in `ui/src/pages/BaselinePage.tsx` (line 23) | The one phrase for missing data | Reused as the single source for the rule; the "Missing:" second line is new per tile |
| `ui/src/pages/baselinePage.test.tsx` line 98 (asserts "Not available yet") | Test of the phrase on the baseline page | Pattern copied for the new tests of the first-run home |
| `sh_platform/packs.py` `PackLoader`, `Pack.section`, `EmptyPack`, `SUGGESTION_LABEL` (lines 9 to 13, 49 to 110) | Loads a pack version; returns `EmptyPack` for an unknown industry; carries the suggestion label | Reused. File 49 adds `intents_section(name)` for the `intents/` subfolder (the loader lists only files directly in the version folder today), so this file does not rely on a flat section |
| `packs/family_office/1/intent_examples.yaml`, `north.yaml` | Existing example lines (`examples`, `pain_point_examples`, `example_data_line`) | Not used for the cards. The cards come from file 49's `intents/first_intents.yaml`; these files stay as North's wall and note-form examples |
| Spec 04 Screen 2 (empty home) | Empty home with five rows | Kept and extended: suggestions block, North opening line, no-areas panel are new here |
| Private room `RoomView` | Not touched | Not used |
New: the suggestion cards, the no-areas panel, the "Missing:" second line, Nothing else is rebuilt. The pack files are file 49's.

## Not in this feature
- The content of any non-empty screen (specs 03 to 17).
- The tag editor for areas (spec 06 and the existing people screen).
- Sending the request to the admin. The screen copies text; it does not message anyone.
- A guided tour, tooltips or a checklist after the first intent.
- Creating a pack for an industry that has none.
- Analytics on first-run use.

## Open questions
1. Should a person with no areas be allowed to start an intent at all? The chooser has an areas step, so it works either way; the default here is "if the company allows it". Nitin to decide the company setting.
2. The guard "North groups ideas once there are at least five" borrows the five-person group guard in `egress.md`. The brief gives no threshold for clustering. Confirm or replace.
3. Who is "the company admin" in the company record when there are several? Screen 2 names one; the record shape is not specified.
4. First-run starts from a suggestion: file 49's `from_pack` records provenance, so the counter could read it. Confirm, then replace the "not tracked" row.
5. `intents/first_intents.yaml` for asset management and other industries is not written here. Until it exists those companies see the "No industry knowledge" line, honest but plain. Who writes them, and is a practitioner review needed first?
6. No other industry's suggestions are ever shown to a family office. Noted so no one adds a fallback.
7. Ruling 1's route list has no `/centre/intent/bring`, yet it exists in `ui/src/App.tsx` and this file links to it. Keep, or give it a ruling 1 spelling?
8. File 49 spells its API `/api/company/intents/...` and some pages `/intent/new/<type>`, against ruling 1. 49 should be corrected in the review wave; this file uses the ruling 1 spellings.
9. Strip label: this file uses file 49's "Suggested from what others in the industry usually do"; the existing `SUGGESTION_LABEL` reads differently (49 open question 3).
10. File 49 keeps its strip after first run, with "Not for us"; the earlier text here said cards go once an intent exists. Which wins?
11. A card needs to pass its suggestion id to the chooser (to set `from_pack`). Ruling 1 gives only `?type=` and `?from=<id>`. Page state, or a new query parameter?
12. Numbers the brief does not set and this file avoids: how many options a Decision needs, how long "Copied" shows, and the cap of three cards (file 49's).
13. The empty rows for Problem, Decision and Weekly check-in use the copy of files 38, 41 and 43 by screen name; confirm their field names match.
