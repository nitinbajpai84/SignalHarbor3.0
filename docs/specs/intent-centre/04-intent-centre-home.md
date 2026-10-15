# 04. Intent Centre home

Part of: Intent Centre v2. Depends on: 00-BRIEF (the intent record, visibility rule), 03 (the chooser), 19 (counters, measures M01, M02, M08, M13), the intent page spec (the screen a card opens). Feeds: the Pulse page lines, the Build hand-off list, the past intents archive.

## Purpose (three sentences)

The home answers two questions in this order: "what is happening in the company" (lanes of intent cards) and "I want to do something" (the Start an intent button, always in view). It replaces the v1 home, which showed three Initiative rooms and the wall as if they were the whole centre. Every card, line and counter on it comes from an intent record the viewer is allowed to see.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser | Starting something, or checking what they run and what is late | Opens the centre from the home tile, or follows a Pulse line |
| Sponsor | Checking that what they sponsor is on time and heading to a charter | Weekly look, or a "Your turn" line asking for a sign-off |
| Participant | Finding the session or step they were invited to | Invite link, or a "Your turn" line |
| Owner (of a Problem) | Seeing the problems they own and the days left | Nira line "a problem is waiting on you" |
| Affected person | Knowing that something touching their area exists, and what came out | Opens the centre, or reads a closed outcome |
| Company admin | Seeing all intents, their outcomes and the centre counters | Weekly review |
| Super admin | Confirming the centre is in use at a company | Support check; sees existence only |

## Entry points (every route, link, Pulse line, button that leads here)

- Route `/centre/intent` (declared in the module manifest; default deny for any role not in the table above). The super admin does not get this page: they read existence at `/centre/control/intents` (see Rules).
- Home page tile "Intent Centre" on the shell home (existing).
- Back links from every intent page, the charter page and the outcomes page.
- Pulse line from Nira: "Two intents are waiting on you" links to `/centre/intent#your-turn` (an anchor on this page, not a route).
- Share link for a closed intent opens the read-only view, not this page.
- Query parameters keep a filtered view linkable: `?type=initiative,problem&state=open&area=finance&view=mine`. The old `?start=wall` and `?start=truth` links are redirected: `?start=wall` redirects to `/centre/intent/new?type=initiative`; `?start=truth` redirects to `/centre/build/gap-analysis` (gap analysis is room 0 of the Build centre).

## Screens, element by element

### Screen 1: Intent Centre home

Route: `/centre/intent`.

**Layout at 1280.** Uses the existing `PageFrame` with the aside. Regions, top to bottom:

1. Header band: eyebrow "Intent Centre", title "What is happening in the company", one-line subline, and on the right the primary button "Start an intent" (never scrolls out; sticky at the top of the content column).
2. "Your turn" strip, full width, only when Nira has at least one item.
3. Filter row: type chips, state chips, area select, Mine / All switch.
4. Lanes: stacked horizontally-scrolling rows, one per area the viewer belongs to, then "Company-wide". Each lane shows up to four cards at 1280 (card width 280), then "Show all (n)".
5. Past intents: a card of closed and cancelled rows with outcome one-liners.
6. Counters: a `StatGrid` of four `StatCard`s at the bottom of the main column.
7. Aside (right, 320 wide): "Governed state" side card (kept from v1, for Initiatives only), "Where things are kept" links (outcomes, map), footnote.

**Layout at 390.** Single column, 16px gutter. The header shows the title and a full-width "Start an intent" button (44px high) directly under it. Your turn strip becomes a stack of up to three rows. Filters collapse behind one "Filters (n)" button that opens a sheet; the Mine / All switch stays visible. Each lane becomes a vertical list of cards (one per row, full width), five per lane, then "Show all (n)". Past intents show as rows, title and one-liner only. Counters become a 2 by 2 grid. The aside cards move to the end of the page.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Title and subline | Text | "What is happening in the company" and "N intents running in your areas, M closed this month" (N = count of visible intents with `state` open, in_session or closing; M = count with `closure.closed_at` in this month, company time zone) | None | All except super admin (see rules) | Subline reads "No intents yet" |
| Start an intent | Button (primary) | Label "Start an intent" | Opens the chooser (`/centre/intent/new`), which asks "What do you intend to do?" and picks the type | Company admin, and any signed-in person the company allows to organise (see Open questions) | Always shown to those roles; hidden for others, with the line "Ask your company admin to start one" in its place |
| Bring files | Chip | "Bring files" | Goes to `/centre/intent/bring` (existing v1 route, see Open questions) | Company admin | Hidden for others |
| Your turn strip | Panel of agent lines | Heading "Your turn", sub-label "Nira, suggestions" and up to three lines, each: what is waiting, which intent, days left | A line click opens the intent at the stage that needs the person. "See all (n)" expands inline | Anyone with at least one item | The strip is not rendered. If the viewer has none, the line "Nothing is waiting on you" sits under the header in soft text |
| Type chips | Chip group (multi-select) | Initiative, Brainstorm, Weekly check-in, Problem, Decision, each with the count of cards currently visible (count of `intent.type` over the records on screen) | Toggles the filter, updates the URL, re-renders lanes | All | A type with zero cards is shown dimmed and still selectable |
| State chips | Chip group (single choice) | Open, In session, Closing, Draft (only the person who started it), All running | Filters cards by `state`. "Open" = `open`; "In session" = `in_session`; "Closing" = `closing` | All | Zero-count states dimmed |
| Area select | Select | "All my areas" and each area the viewer belongs to (company admin: every area in the company) | Shows only that lane | All | Single option "All my areas" when the viewer has one area |
| Mine / All switch | Segmented control | "Mine" (viewer is organiser, sponsor, participant, owner or affected) and "All" (everything the viewer may see exist) | Re-filters lanes and counters' sub-labels. Counters never change with filters | All. Default for non-admins: Mine. Default for company admin: All | If Mine returns nothing, the lanes show "Nothing of yours is running. Switch to All to see the company." |
| Filters (n) | Button (390 only) | "Filters (n)", n = count of filters switched on | Opens a sheet holding type chips, state chips and area select; "Apply" closes it and updates the URL | All | n is 0: label reads "Filters" |
| North notice | Agent line | "North created 3 intent records from earlier work" with a "Check" link (shown once; count = records created) | "Check" opens the first created intent at `/centre/intent/<id>`; the line is dismissed once read | Organiser who owns the earlier work, company admin | Not rendered |
| Lane | List of cards | Lane title (area name, or "Company-wide"), count of running intents, lane-level link "Show all (n)" | Show all expands the lane to a wrapped grid | See rules | See "Lane empty" below |
| Lane empty | Text | "Nothing is running in <area>." plus a "Start one for <area>" link that opens `/centre/intent/new?area=<area>` (area pre-filled) | Opens Start an intent | Organiser roles | Same text without the link for others |
| Intent card | Card (link) | Title; type chip; stage label; days left in time box; organiser name; people count; "Your role" tag when the viewer has one; state pill when not `open` | Click opens `/centre/intent/<id>` (the stage view opens by default). Keyboard: the whole card is one link with an accessible name "<title>, <type>, <stage>, <days left>" | Per visibility rule | Not applicable |
| Title | Text (max two lines) | `intent.title` | In the card link | Everyone who sees the card | A missing title shows "Untitled intent" and North asks the organiser for one |
| Type chip | Chip | Initiative, Brainstorm, Weekly check-in, Problem or Decision. One colour per type, always with the word | None | Everyone who sees the card | None |
| Stage label | Text | The current stage by type. Initiative: "Think unfiltered", "Define strategically" or "Build-ready check". Brainstorm: "Invites out", "Live session", "Choose an idea". Weekly check-in: "Collecting", "Sorting". Problem: "Owner and cause", "Fix", "Closing". Decision: "Options", "Decide". Stage keys come from `stages[]` (the open one). Exact labels are owned by each type's spec | None | Everyone who sees the card | "Not started" when no stage is open (state `draft`) |
| Days left | Text with colour | "6 days left", "Last day", "2 days over" (warn colour, with the word, never colour alone). Working days between today and `time_box.ends` (latest extension). Weekly check-in: "Ends Friday" | None | Everyone who sees the card | For a draft: "Time box starts when opened" |
| Organiser | Text | `people.organiser` display name | None | Everyone who sees the card | "No organiser" (should not occur; North flags it) |
| People count | Text | "7 people": count of unique ids across `people.organiser`, `sponsor`, `decider`, `owner`, `reporter`, `participants` and `affected`. Observers excluded. Super admin sees this count only | None | Everyone who sees the card | "0 invited yet" for a draft |
| Your role tag | Chip | One word: Organiser, Sponsor, Decider, Owner, Reporter, Participant, Affected, Observer. If more than one, the first in that order | None | The viewer, on cards they are in | Not rendered when the viewer has no role |
| Extended marker | Chip | "Extended" when `time_box.extended_by` is not empty; hover or focus shows who and why | None | Everyone who sees the card | Not rendered |
| Past intents card | Panel (list) | Title "Past intents". Rows: title, type chip, closed or cancelled date, outcome one-liner, and a link "Open outcome". Latest ten, newest first | "Open outcome" goes to the closed intent view (or the charter for an Initiative). "Show all past intents" opens `/centre/intent/past` with the same filters | All who may see the intent exists. Content link follows the rules below | "Nothing has been closed yet. Closed intents will appear here with what came out of them." |
| Outcome one-liner | Text (max 140 characters) | `closure.one_liner` for closed; for cancelled: "Cancelled: <reason>" | None | Everyone who sees the row | "Closed without a summary" and North flags the organiser |
| Counters | StatGrid, four StatCards | M01, M02, M13 and M08 as defined in file 19 (see Counters and measures below) | Each card has "Show the intents" which sets filters and scrolls to Past intents or the lanes | Per rules | Each card reads "Not available yet" with what is missing |
| Governed state card (aside) | SideCard | Kept from v1: four bars (owner, classified, who may see, sealed) over reported measures, labelled "Initiatives only" | None | Company admin, sponsor, organiser | "Not available yet. No measures have been reported." (as v1) |
| Where things are kept (aside) | Links | "Outcomes" and "Map" (existing routes) | Navigate | Company admin, organiser, sponsor | Links always shown |
| Footnote | Text | One line: figures come from intent records in your company | None | All | None |
| Loading and error | `ScreenState` | "Loading the centre" and "The centre could not load. Try again." with Retry | Retry reloads | All | None |

### Screen 2: Empty home (company with no intents yet)

Same route. Shown when the company has zero intent records visible to the viewer and the company has the Intent module switched on.

**Layout at 1280.** Header as above. In place of filters, lanes, past intents and counters: one centred panel "Nothing has been started yet" with the line "Start with what you intend to do. North will ask the right questions and keep the clock." Beneath it, five type rows (type chip, one-line why, "Start" button), taken from the brief's type table. The counters are not shown (they would all read zero or "Not available yet"); one footnote says "Counters appear after the first intent is opened."

**Layout at 390.** The five type rows stack, each with a full-width "Start" button.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Empty panel | Panel | "Nothing has been started yet" and the North line | None | All viewers who get a page | Is the empty state |
| Type row (five) | Row with chip and button | Type, its reason ("I want to run X", "I have an idea and want people to think with me", "Every week my ops people say what ran", "Something is wrong in operations", "One decision must be made and recorded") | "Start" opens Start an intent with that type chosen | Roles who may start | For viewers who may not start: the rows are text only and the panel says "Nothing has been started yet. Your company admin can start the first intent." |
| Existing v1 material | Link | If the company has v1 walls, baselines or charters but no intent records: "Earlier work: N walls and M charters" with a link to each | Opens the existing route | Company admin, organiser | Not rendered |

A company with only v1 material is not truly empty. North creates one intent record per existing wall session on first load (see Agent behaviour) so the lanes are never blank while old work exists.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet (organiser) opens the centre from the home tile "Intent Centre". The page loads intent records through the viewer-filtered route; Nira builds her Your turn lines in the same call.
2. She reads the strip: "Confirm the closure draft for Treasury onboarding, 1 day left". North had drafted the closure and the one-liner when the last stage closed; Janet has not seen it yet.
3. She clicks the line and lands on the intent page at the closure step (other spec). Janet confirms. The home now moves that intent to Past intents.
4. Back on the home she scans her lanes: Operations, Finance, Company-wide. She switches to "Mine" and filters by Problem.
5. She presses "Start an intent". She lands on `/centre/intent/new`, which asks what she intends to do; the agent chooses the workflow after she picks a type. She leaves the home.
6. Aaron (participant) opens the same page. He sees only lanes for his areas, a Your turn line "Add your cards to the wall, 3 days left", and his "Participant" tags. He clicks the card and leaves.
7. Harvey (owner) sees his Problem card in the Operations lane with "Owner" and "2 days over". Nira has told him on the strip; North has already proposed extend, close with what we have, or cancel to Janet.

## States and transitions (table: state, who moves it, to what, what is written)

This page changes no intent state. It shows states and sends people to where they are moved. The page itself has these view states.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| Loading | The page, on open or Retry | Populated, Empty or Error | Nothing |
| Populated | The page | Filters applied (URL changes) | Nothing. Filters live in the URL; the last chosen Mine / All is kept in browser storage as a convenience only |
| Empty | The page, when no intent is visible to the viewer | Populated once an intent exists | Nothing |
| Error | The page, when the intents route fails | Loading on Retry | Nothing |
| Card shown as Draft | Organiser, on the Start an intent flow | Open (set elsewhere) | Not here |
| Card shown as Closed | Organiser confirms closure (intent page) | Appears in Past intents | Not here |

Which card goes where, by `intent.state`:

| `state` | Lane | Past intents | Notes |
|---|---|---|---|
| draft | The person who started it only, with a "Draft" pill | No | Hidden from everyone else, company admin included (ruling 14) |
| open, in_session, closing | Yes | No | "Closing" shows an amber pill and the word |
| closed | No | Yes | |
| cancelled | No | Yes, with the reason | Kept and shown in Past (ruling 14) |

## Records read and written (file or route, fields; mark Existing or New)

| Record or route | Fields used | Mark |
|---|---|---|
| `GET /api/intents?view=<mine\|all>&type=&state=&area=` | Per intent, after `sh_platform/profile/view.py` has filtered it for the viewer: id, type, title, state, areas, people (counts and the viewer's own role), organiser display name, the open stage key and label, time_box (ends, extended_by), closure.one_liner, closure.closed_at, ratings (scores only, no anonymous notes), outcome.build_ready | New |
| `GET /api/intents/home` | The four counters (M01, M02, M13, M08, from the same functions as file 19's `GET /api/intents/measures`), each with the list of intent ids it was computed from, and the Your turn lines | New |
| `intents/<id>/intent.json` in the company plane via `sh_platform/jsonfile.py` | The intent record in the brief | New (the brief defines it) |
| `GET /api/profile` (`reported_figures`, `governance`) | Used by `governedBars` for the aside card | Existing |
| `GET /api/profile/readiness` (`groups`, `asks`) | Source of Your turn lines for Define asks on Initiatives | Existing |
| `GET /api/modules/m1_intent/walls`, `/sessions`, `m2_baseline/baselines`, `m3_connect/assessments` | Only to create the first intent records from earlier work and to link an Initiative card to its wall, baseline or charter | Existing |
| Writes | None from this page. Browser storage holds only the Mine / All choice | None |

## Fields this feature adds to the intent record

| Field | Meaning | Written by |
|---|---|---|
| `closure.one_liner` | Up to 140 characters: what came out, for the past intents list | North drafts, the organiser confirms at closure |
| `closure.cancel_reason` | One sentence, shown on the cancelled row | Organiser at cancel |
| `areas` token `"company-wide"` | A reserved area value that places the intent in the Company-wide lane and makes its existence visible to everyone in the company | The person who opens the intent, when asked "Is this for the whole company?" |

`people.decider`, `people.owner` and `people.reporter` are read here for the Your role tag; file 02 adds them (ruling 13), not this file. No other field. Days left, stage label, people count and Your role tag are computed on read, not stored.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **Nira** builds the Your turn strip on every load. She reads intents where the viewer is named in an open step (confirm, sign, add, rate, decide) and the existing readiness asks. She drafts one line each: what, which intent, days left. She orders by days left, then by type order in the brief. Nira never acts; the person clicks the line and acts on the intent page. Lines are labelled as suggestions.
- **North** keeps the clock that produces "days left" and the amber and over states. When an intent is over its time box North has already proposed extend, close with what we have, or cancel to the organiser; the card shows "2 days over" until a named person picks. North drafts `closure.one_liner` when closure is drafted; the organiser confirms it. North also writes the first intent records from earlier v1 walls so the lanes are not blank (the organiser sees "North created 3 intent records from earlier work" once, with a Check link).
- **Lens** does nothing on this page. Its drafts are reached from the Initiative's Define stage.
- Agents decide and draft; people act at the named moments: Start an intent (organiser), confirm closure (organiser), pick extend or close (organiser or sponsor), rate (participant). None of these happen on this page.

## Rules (visibility, time box, who may do what)

What each role sees. Existence means title, type, state, areas, people count.

| Role | Lanes | Cards | Your turn | Past intents | Counters | Start an intent |
|---|---|---|---|---|---|---|
| Organiser | Own areas plus Company-wide; drafts they started | Full card, "Organiser" tag, link to content | Yes | Own and area intents; content link for own | All four | Yes |
| Sponsor | Own areas plus Company-wide | Full card, "Sponsor" tag; content link on intents they sponsor | Yes (sign-offs) | Same | All four | Only if the company lets sponsors organise (Open questions) |
| Participant, Observer | Own areas plus Company-wide | Full card. Content opens only for intents they are in (an observer reads what a participant reads and never writes); others show existence, stage, organiser | Yes (their steps) | Existence and outcome one-liner; content only for ones they were in | All four | Only if the company allows (Open questions) |
| Owner (Problem) | Own areas plus Company-wide | Full card, "Owner" tag; content link on problems they own | Yes (fix, close) | Same | All four | Same as participant |
| Affected person | Own areas plus Company-wide | Existence, title, purpose, stage, days left, people, organiser; content link only when the organiser switched on "affected people may read" at creation (default off) or they are named on a share; outcome once closed | Only items for them (for example "Rate this outcome") | Existence and outcome | All four | Same as participant |
| Company admin | Every area in the company plus Company-wide | Every card, existence and outcome; never anonymous notes; ratings shown as scores only | Items addressed to them | All | All four, plus the Governed state card | Yes |
| Super admin | Not this page. `/centre/control/intents` lists existence per company, read through the kernel on request (no copy in the control plane) | Title, type, state, areas, people count, dates, time box status. When the company switch "titles private to the company" (default off) is on, no title. No organiser name, no stage detail, no rating, no one-liner, no links into content | None | State and count only | Counts of opened and closed only (file 19, Centre use); ratings and build-ready read "Hidden at this level" | No |

Further rules:

- A card appears in the lane of each of its areas that the viewer belongs to. When an intent spans more than one of the viewer's areas, the second and later cards carry "Also in <area>" so the viewer does not read it as a new intent. Counters count an intent once.
- Visibility is decided on the server by `view.py`. The page never fetches a record and hides it in the browser.
- Anonymous and sealed material never reaches this page. Ratings arrive as scores; anonymous ratings count in the average and are never shown as a list here, and no per-person average exists (ruling 15).
- Days left counts working days in the company calendar. Working-day source: Open questions.
- Cancelled intents are kept and shown with the reason. Nothing is deleted from this page.
- No game words. Lanes, cards, stages. No model or vendor names; agents appear as North, Lens, Nira.
- Dates and "this month" use the company's time zone from the profile, else UTC. Counts are exact; means show "Fewer than five" below five records and ratings aggregate from three (ruling 8).

## Counters and measures of this feature (numbers only, each traced to a record)

The four counters are not defined here. File 19 is the single source; this page calls the same functions and shows the short form. "This month" = the calendar month in the company's time zone from the profile, else UTC. Every counter returns the ids it was computed from, and "Show the intents" opens that exact list, limited to intents the viewer may see.

| Counter on the home | File 19 measure | Short form shown | Traces to | Not available when |
|---|---|---|---|---|
| Intents opened this month | M01 (all types summed) | Count of intents opened this month | `stages[0].opened_at`, `state` not `draft` | As file 19: "Not available yet. No intent has been opened." The Empty screen shows when no intent is visible |
| Closed inside the time box | M02 | "6 of 8" this month, all types; cancelled excluded | `closure.closed_at`, `time_box.ends`, `time_box.extended_by` | "Not available yet. Nothing has closed." |
| Average rating | M13 | Mean with count: "4.2 from 11 ratings". Shown from three ratings (ruling 8); below three: "Fewer than three ratings" | `ratings[].score` | "Not available yet. No ratings have been given." |
| Build-ready charters | M08 (this quarter) | Count waiting for Build and, beside it, count handed over | `outcome.build_ready`, `links.build`, `stages[key=build_ready].closed_at` | "Not available yet. No Initiative has reached the check." |

For anyone but the company admin the sub-label reads "Intents you can see" and file 19's `scope: "visible"` applies (two people can see different numbers).

Other measures on the page: lane counts (cards in the lane after filters), type chip counts, the Your turn count (Nira lines for this viewer), and the people count on each card. Each is a count of records the viewer may see, never of hidden ones; a super admin's people counts are totals only.

v1 counters (files read, interviews done, Lens read of the baseline, time) are no longer on this page. They belong to the Initiative's Define stage; the "time" counter was always "Not available yet" and is dropped.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Source read in full: `ui/src/pages/CentrePage.tsx` (345 lines), the page at `/centre/intent`. Graft was not run for this spec; the file was read directly because only this one file is in scope. Components come from `ui/src/design` (`Button`, `Chip`, `Footnote`, `PageFrame`, `Pill`, `RoomTile`, `SideCard`, `StatCard`, `StatGrid`) and `ui/src/components/ScreenState`.

| Existing (lines) | What it is | Decision |
|---|---|---|
| 1-12 imports, 17-18 constants | Imports, `NA` text, route base | Kept. `NEW` stays `/centre/intent` |
| 20-36 types `Profile`, `Group`, `Readiness`, `Session`, `Baselines`, `Closed`, `Room` | v1 data shapes | `Profile`, `Readiness` kept (aside card, Your turn). `Room` dropped. New `IntentCard` type added |
| 38-41 helpers `val`, `has`, `norm`, `live` | Small helpers | Kept. `live` reused to find running v1 walls when creating first intent records |
| 43-64 `governedBars` (exported) | Four governed-state bars | Kept as is, but moved to the aside and labelled "Initiatives only". Not copied; the same function is imported |
| 66-75 `get`, `ok` | Fetch that treats 403 as "module off" | Kept. Used for the new intent routes; a refused route hides that part of the page |
| 77-111 `buildRooms`, `lit` | Three Initiative rooms as doors, lit in order | Moved. The rooms become stage labels on the Initiative card and the stage links on the intent page. No tiles on the home. Dropped as a home element |
| 113-119 `DOORS_GRID`, `DOOR`, `FIELD`, `INPUT`, `ROW` styles | Layout styles | `ROW` kept; `DOORS_GRID` reshaped into the lane card grid (`repeat(auto-fit, minmax(min(100%, 280px), 1fr))`). `FIELD`, `INPUT` move with the start panel |
| 121-161 `startWall`, `startTruth`, start panels (264-296) | Inline "start a wall" and "start gap check" panels | Moved. `startWall` becomes the Initiative branch of Start an intent (same `getLists`, `toPreparation`, `createDraft`, `startRoom`, `saveLink` calls). `startTruth` is dropped from the home; gap analysis is Build's first step and Moment of truth is reached from Build |
| 163-200 load effect with `Promise.all` | Fetch of profile, readiness, interviews, sessions, baselines, assessments, walls, charters | Reshaped. Replaced by two calls (`/api/intents`, `/api/intents/home`); the profile and readiness calls stay for the aside and the Define asks. Interview and assessment calls leave the home |
| 203-208 `waiting` (Nira list) | First three asks or missing groups | Moved into Your turn. Kept as one source; intent-based lines are added in front |
| 213-254 aside: governed card, waiting card, "So far" links, footnote | Right column | Governed card kept (aside). Waiting card becomes the full-width Your turn strip. "So far" links (`/outcomes`, `/graph`) kept as "Where things are kept". Footnote kept with new text |
| 257-263 `PageFrame` with crumbs, title, subline, actions | Page shell | Kept. Title and subline change; the "Bring files" `Chip` kept for the company admin; "Start an intent" `Button` added as the main action |
| 297-308 rooms list with `RoomTile`, `Pill` | Three room tiles | Dropped from the home. `RoomTile` stays in the design kit for other screens |
| 309-323 running walls card | List of running walls | Moved into lanes: each wall is an Initiative card in "Think unfiltered" |
| 324-335 closed walls with signed charters | "Signed" list with charter links | Moved and generalised into Past intents; the charter link stays for Initiatives |
| 336-341 four `StatCard`s | files, interviews, Lens read, time | Replaced by the four centre counters. `StatGrid` and `StatCard` reused |

Genuinely new: the `IntentCard` component, `Lane`, the filter row, the Your turn strip, the Empty screen, the two `/api/intents` routes, and the intent record. Checked and not found in `ui/src`: any card, lane or filter component for records (the design kit has `RoomTile`, `StatCard`, `SideCard`, `Chip`, `Pill`, none of which fits a card with seven fields). The earlier repo (`earlier-repo`) was not searched for this spec; the builder runs the reuse check there before writing `IntentCard` (D-031).

## Not in this feature

- The Start an intent flow itself, and each type's own start questions.
- The intent page a card opens, the closure step, rating and extend or cancel actions.
- The share link view.
- The past intents archive page `/centre/intent/past` beyond its link and filters.
- Pulse page lines on the shell home, and notifications by email.
- Gap analysis and the Moment of truth screen (Build).
- Any edit of an intent from the home.

## Open questions

1. Who may press "Start an intent": company admin only (as v1), or any signed-in person? The vision says "anyone in a company starts something". Default drawn here: company admin and organiser roles; sponsor, participant, owner and affected get the "ask your admin" line until Nitin decides.
2. Display choices, not business rules: four cards per lane at 1280 and five at 390, ten past intents, three Your turn lines, card width 280, aside width 320, one-liner limit of 140 characters. Confirm or change.
3. Working days: which calendar (country, public holidays) does the company use for "days left"? Until set, Monday to Friday.
4. Ratings show from three, means from five (ruling 8), but file 19 says "Fewer than five" for M13. This file follows the ruling; 19 needs correcting.
5. File 19 still names `GET /api/centre/home` and a UTC month. This file uses `GET /api/intents/home` (brief section 8, item 12) and the company time zone else UTC (ruling 8). 19 needs correcting.
6. "Closed inside the time box": does an extended time box count as inside? Counted against the final end after extensions (as file 19, M02); the card shows the "Extended" marker. Confirm.
7. The `company-wide` area token: should the company admin define named groups (for example "All branches") beyond departments? Not needed for the first build.
8. The key for the build-ready flag. This file reads `outcome.build_ready` (as file 19, M08); the Initiative spec owns the final name.
9. Routes outside the convention: `/centre/intent/bring` (existing v1 "Bring files"), `/outcomes` and `/graph` (existing "Where things are kept" links), the `#your-turn` anchor. Keep, move under `/centre/intent/...`, or drop?
10. North writing one intent record per v1 wall on first load is a write caused by a read. Should the organiser press "Create records from earlier work" instead?
