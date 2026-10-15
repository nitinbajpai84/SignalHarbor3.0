# 17. Phone and projector views

Part of: Intent Centre v2. Depends on: 01 (record and lifecycle), 02 (types catalogue), 03 (chooser), 04 (home), 06 (people and roles). Feeds: the type files for brainstorm session, define session and weekly check-in (their live screens use the projector view defined here).

## Purpose (three sentences)
Every Intent Centre screen must work with one thumb on a phone 390 pixels wide, because people join a live session from the phone in their hand. This file says, per screen family, what collapses, in what order the regions stack, which actions sit in the bottom bar, how North becomes a sheet, how lanes swipe, and how big the touch targets are. It also defines the projector view: a full-screen, names-free display at `/centre/intent/<id>/projector` that the organiser puts on a wall or a shared screen during a brainstorm session, a define session or a weekly check-in review.

## Who uses it and when (role, moment, trigger)
| Who | Moment | Trigger |
|---|---|---|
| Aaron (participant) | In a live session, in the room or remote, on a phone | Opens the invitation link; adds cards, reads lanes, answers North |
| Katie (analyst, affected) | Between meetings, checking what is waiting | Pulse line from Nira opens the home or an intent on a phone |
| Harvey (owner), Grace (approver) | Reading a problem or decision and acting | "Waiting for you" link on a phone |
| Janet (organiser) | Running a session | Presses **Projector view** on a laptop that is connected to a screen or shared in a call |
| Daniel (sponsor), an observer, a share visitor | Reading a closed or open intent | Share link or intent link opened on a phone |
| Company admin | Looking at existence and outcomes | Home on a phone |

Phone is below 700 pixels wide (the existing `PHONE = 700` in `WallScreen.tsx`). The reference width for shots and tests is 390. Between 700 and 1280 the 1280 layout reflows by the same grid rules; no third layout is specified. "Pulse" alone means the daily page (brief ruling 3); the recurring type is "Weekly check-in".

## Entry points (every route, link, Pulse line, button that leads here)
- Every route of the centre has a phone layout. Routes used in this file (brief ruling 1): `/centre/intent` (home, spec 04), `/centre/intent/new?type=<type>&from=<id>` (chooser, spec 03), `/centre/intent/<id>` (the intent screen for every type), `/centre/intent/<id>/wall`, `/define`, `/session`, `/week`, `/review`, `/close`, `/share`, `/projector`, and `/centre/intent/past`.
- Wall: `/centre/intent/<id>/wall`, served by the existing `WallScreen`; the intent screen links to it.
- Projector view: route `/centre/intent/<id>/projector`. Reached by the button **Projector view** on the wall, on `/session` (brainstorm, define) and on `/review` (weekly check-in). Organiser only (see Rules). On the projector route, **Back to the full view** returns to the view it came from.
- Projector join address: the QR code and short link on the projector open the **participant join** page for that session, never the projector itself.
- Nira Pulse lines and invitation emails link to the phone layout of the same route. There is no separate phone site.

## Screens, element by element

Common rules first, then one block per family. Every family block gives route, layouts and an element table.

### Common phone rules (apply to every family)
| Rule | Value |
|---|---|
| Width | 390 CSS pixels; no horizontal page scroll at 390 or at 360 |
| Gutter | 16 px (`--ds-s4`) each side, as `.ds-wall` already does |
| Touch target | 44 by 44 px minimum for every button, chip, tab, checkbox and link row; 48 px for bottom-bar buttons. The wall card button (36 px today) and `.ds-north__choice` (32 px today) are raised to 44 on phone |
| Type | Body 14 px minimum; no text below 12 px; counts and times 18 px or more |
| Region order | Header, then what is waiting for this person, then the main region, then side regions as collapsible rows, then the bottom bar |
| Side regions | A right-hand panel at 1280 becomes a collapsed row ("Your drafts, 2") that expands in place |
| Tables | A table at 1280 becomes a list of rows on phone; the first column is the row title, the rest wrap under it |
| Bottom bar | Fixed, 56 px high plus the safe-area inset, holds at most two actions: one primary, one secondary. Page padding at the bottom is 96 px so the last row is never hidden (as `.ds-wall` does) |
| Motion | None required; where there is any it stops under `prefers-reduced-motion` (existing rule in `wall.css`) |
| Top bar | The shell bar already collapses below 720 px: nav and company name hide, the burger shows (`barStyle.ts`). Unchanged |
| Copy | Same copy as 1280. No phone-only wording except the short bar labels named below |

All pixel values in this table are proposals; see Open questions 9.

### The North sheet (every screen that has a North panel)
Route: the host screen's own route. Layout 1280: the North panel is a column on the right. Layout 390: a bottom sheet behind a button.
| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Talk to North | Button (primary or secondary in the bottom bar) | "Talk to North"; a dot when North has a question waiting for this person | Opens the sheet; `aria-expanded` true | Anyone with a North panel at 1280 | Hidden when North has nothing to say and the session is not live (same condition as today: only while `live`) |
| Sheet | Panel (bottom sheet, `aside`, label "North, your conversation") | The same `NorthPanel` as 1280: North's question, answer box, choices, drafts | Scrolls inside; max height 80 vh; page behind does not scroll | Same as 1280 | "North has no question for you right now." |
| Close North | Button (the same button, relabelled) | "Close North" | Closes the sheet; focus returns to the Talk to North button | Same | Not applicable |
| Drag handle | Handle (visual only) | A short bar at the top of the sheet | Swipe down closes; the close button remains the accessible way | Same | Not applicable |

The sheet never opens by itself. North raises the dot; the person opens it.

### Lane swiper (wall, brainstorm session, define clusters)
Route: the host screen's own route. Layout 1280: all lanes side by side. Layout 390: one lane at a time.
| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Lane tabs | Tablist of chips (existing `ds-wall__tabs`) | Lane name and its card count (read from the wall route's `submitted`), all in view, wrapped on two rows if needed; the open lane is marked | Tap shows that lane | Anyone who sees the wall | Counts read 0; the lane says "Nothing here yet." |
| Lane body | List | One lane at a time, cards stacked; "+ n more" after the first ten (existing `SHOWN` rule) | Tap a card to open it; horizontal swipe on the body moves to the next or previous lane | Per card rules (anonymous, sealed) | "Nothing here yet." |
| Swipe | Gesture (new) | Horizontal drag across the body | Changes the lane and the selected tab; announces the lane name to screen readers; does not wrap at either end | Same | Not applicable |
| Dots under the tabs | Indicator | One dot per lane, the open one filled | None | Same | Not applicable |

Swipe is an addition to tabs, never a replacement: every action stays reachable by tap. Today only tabs exist (`WallScreen.tsx` L158-L166); swipe is new. The swipe distance is an open question (9).

### Family 1. Home
Route: `/centre/intent`.
- **At 1280.** Header with "Start an intent"; "Your turn" lines; intents in your areas as cards in a grid; Past intents card; "Where things are kept" aside.
- **At 390.** Order: header (title only), "Your turn" lines (full width, each one a row), then a segmented switch **Running / Finished / Past** that replaces the three-column grid with one list at a time, intent cards one per row, Past intents last as a collapsed row, "Where things are kept" as a collapsed row.
- **Collapses.** The aside; the filters (into one **Filter** button that opens a sheet with area and type chips); the people count on cards (kept as "6 people" text only).
| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Your turn line | List row (link) | One line from Nira per waiting item (read from the person's waiting list, spec 04) | Opens that intent's screen at `/centre/intent/<id>` | The person it waits for | "Nothing is waiting for you." |
| Running / Finished / Past | Segmented switch | The three lists, each with its count of intents from `GET /api/intents` | Shows one list | Everyone | Count 0 and "No intents here yet." |
| Intent card | Link row | Title, type chip, stage, "6 people" (length of `people`), days left (from `time_box.ends`) | Opens `/centre/intent/<id>` | Per spec 04 visibility (draft only to its author) | Not applicable |
| Past intents row | Collapsed row | "Past intents" | Expands in place; **Open all** goes to `/centre/intent/past` | Everyone | "Nothing has been closed yet." |
| Where things are kept | Collapsed row | Spec 04 text | Expands in place | Everyone | Not applicable |
| Start an intent | Button (bottom bar, primary) | "Start an intent" | Goes to `/centre/intent/new` | Roles that may organise | Not rendered; the body says "Ask your company admin to start one" (spec 04) |
| Filter | Button (bottom bar, secondary) | "Filter" | Opens a sheet with area and type chips; **Apply** closes it | Everyone | Sheet lists "No areas set up yet." |
- **North.** Not a panel on this screen; the North line sits under the "Your turn" lines.

### Family 2. Chooser
Route: `/centre/intent/new?type=<type>&from=<id>`. Specified in spec 03 (one column, tiles as vertical full-width cards, drafts collapsed to "2 drafts", North's line last). This file adds the bar only.
- **At 1280.** Tiles in a grid; start questions on the right once a tile is chosen (the per-type files own the questions, brief ruling 2).
- **At 390.** One column; the free-text line stays above the tiles and its keyboard never hides **Continue**.
| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Type tile | Card button | Type name and one line (spec 02) | Selects the type; **Continue** enables | Roles that may organise | Not applicable |
| Back to the centre | Button (bar, secondary, left) | "Back to the centre" | Goes to `/centre/intent` | Everyone on this screen | Not applicable |
| Continue | Button (bar, primary, right) | "Continue" | Opens the start questions of the chosen type (specs 22, 35, 38, 41, 43) | Roles that may organise | Disabled until a tile is chosen |

### Family 3. Wall (existing, Think unfiltered)
Route: `/centre/intent/<id>/wall`.
- **At 1280.** Header strip (cards, people, closes, Live); title; purpose; stage bar; invite panel; tools (Show only mine, Projector view); four lanes side by side; North panel in the right 420 px column.
- **At 390 (exists today, kept).** Title 22 px; one lane at a time with the lane tabs; North as a sheet behind a fixed Talk to North button; stage bar and invite panel stack above the lanes.
- **Order at 390.** Header strip (cards, "6 / 8 people", closes, Live), title, purpose chip, stage bar (collapsed to the current stage name and "closes in 2 days"; tap to expand all stages), tools row, lane tabs, lane body, bottom bar.
| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Header strip | Text | Card total (`submitted`), "6 / 8 people" (`people`), closes (`closes`), Live (`live`) from the wall route | None | Everyone who may open the wall | "Not available yet: the wall has no people count" for a missing count |
| Stage bar | Collapsed row | Current stage name and days left (`closes`) | Tap expands all stages | Everyone | "No close date set." |
| Invite people | Collapsed row (existing `InvitePanel`) | Invite link and names | Expands in place | Organiser only | Hidden for others |
| Show only mine | Chip (existing) | "Show only mine" | Filters lanes to the person's own cards | Everyone except on projector | Not applicable |
| Lane tabs and body | See Lane swiper | | | | |
| Pick it up | Button on a card (existing, 44 px on phone) | "Pick it up" | Existing handler: opens that card for North | Participants | Hidden on cards the person may not use |
| Add a card | Button (bar, primary) | "Add a card" | Opens the private room (existing route) | Participants and organiser | Hidden when the rooms are closed |
| Talk to North | Button (bar, secondary) | See North sheet | Opens the sheet | Per North sheet | Per North sheet |
| Close the rooms | Button (bar, secondary, replaces Talk to North for the organiser while rooms are open) | "Close the rooms" | Existing close action with its confirmation | Organiser only | Hidden once closed |
- **Changes.** Participant avatars collapse to the count text. **Projector view** is hidden on phone (see Rules).

### Family 4. Define (clusters, shelves, process map, data sources, glossary, catalogue)
Route: `/centre/intent/<id>/define`.
- **At 1280.** Board with clusters in columns (`MapColumns`), a detail panel on the right, North on the far right.
- **At 390.** One cluster or shelf at a time, using the lane swiper. The detail panel opens as a full-screen sheet over the list when a card is tapped. The process map is an ordered list of steps (not a canvas).
- **Collapses.** The right detail panel (to the sheet), the cluster rename field (inside the card sheet), the grouping controls (into a **More** menu).
| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Cluster tabs and body | See Lane swiper | Cluster names and card counts from the define record | Tap or swipe | Participants, observers; affected only if switched on (brief ruling 4) | "Nothing here yet." |
| Card sheet | Full-screen sheet | The detail panel of the card, Lens draft if any | Opens on tap of a card | Same | Not applicable |
| Back arrow | Button (44 px) | Arrow, "Back" | Closes the card sheet | Same | Not applicable |
| Open the map on a larger screen | Link (process map only) | That text | Copies the page link and shows "Link copied" | Same | Not applicable |
| Move to... | Button (replaces drag) | "Move to..." | Opens a list of clusters; choosing one moves the card | Participants | Disabled with one cluster |
| More | Menu button | Grouping controls | Opens the menu | Participants | Not applicable |
| Confirm | Button (bar, primary, when a Lens draft is open) | "Confirm" | A named person confirms the draft; reads **Read to the end to confirm** and stays disabled until the text has been scrolled to its end | The person who may confirm | Not rendered when no draft is open |
| Add to this shelf | Button (bar, primary, no draft open) | "Add to this shelf" | Opens a one-field sheet; **Send** adds the card | Participants | Not applicable |
| Talk to North | Button (bar, secondary) | See North sheet | Opens the sheet | Per North sheet | Per North sheet |
- **Touch.** Every drag handle is hidden on phone; every move is a button. Signing the charter and governed-state confirmation need the full detail text; on phone they stay possible.

### Family 5. Brainstorm session (live, organiser plus four to eight people)
Route: `/centre/intent/<id>/session`.
- **At 1280.** Question strip at the top (the current question, set by the organiser or North); lanes (the types catalogue's brainstorm lanes, spec 02); North panel; people strip; clock.
- **At 390.** Order: clock and question strip (sticky at the top), lane tabs, lane body, bottom bar. The people strip is one line "5 / 7 here".
- **Collapses.** North panel to the sheet; the people strip to a count; lane descriptions to a one-line hint.
| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Question strip | Text (sticky) | `session.current_question.text` | None | Everyone in the session | "No question is set yet." |
| Clock | Text | Time left from `time_box.ends` or the stage clock (`StageTimer`) | None | Everyone in the session | "Not available yet. The session has no end set." |
| People strip | Text | "5 / 7 here" (people present over `people` length) | None | Everyone in the session | Hidden when presence is not recorded |
| Lane tabs and body | See Lane swiper | Brainstorm lanes and counts | Tap or swipe | Participants, observers read only | "Nothing here yet." |
| Add an idea | Button (bar, primary) | "Add an idea" | Opens a sheet with a 3-line text box; **Send** on the right adds the card | Participants and organiser; not observers | Not rendered for observers |
| Talk to North | Button (bar, secondary) | See North sheet | Opens the sheet | Per North sheet | Per North sheet |
| More | Menu button (organiser) | "More" | Opens **Next question**, **Close the session**, **Projector view link** | Organiser only | Not rendered for others |
| Next question | Menu item | "Next question" | Puts up North's drafted question; writes `session.current_question` | Organiser only | Disabled with "North has no question drafted." |
| Close the session | Menu item | "Close the session" | Moves the intent to closing (spec 01) after a confirmation | Organiser only | Hidden once closing |
| Projector view link | Menu item | "Projector view link" | Copies `/centre/intent/<id>/projector`; shows "Link copied" | Organiser only | Not applicable |
| Mark or vote on a card | Button, 44 px (only if the type file defines it) | Per type file | Per type file; never swipe-only | Participants | Per type file |

### Family 6. Weekly check-in (type file 38)
Route: `/centre/intent/<id>/week` for contributors, `/centre/intent/<id>/review` for the organiser's review.
- **At 1280.** Week header; three columns by item kind (ran, broke, thought); items list; North's draft lines; review table for the organiser.
- **At 390.** The three kinds become three stacked sections, each a collapsed row with an item count, the first one open. Items are rows of text with a status chip. The organiser's review table becomes rows with one **Decide** button per row.
| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Kind section (Ran, Broke, Thought) | Collapsed row | Kind name and item count from the week file `intents/<id>/weeks/<week_key>.json` | Expands in place | Contributors and observers | "Nothing added yet." |
| Item row | Row | Item text, status chip (fate or "Not decided") | Opens the item sheet | Contributors; names only where type file 38 allows | Not applicable |
| Add to this week | Button (bar, primary, contributor) | "Add to this week" | Opens a sheet: pick the kind, write the item; **Send** adds it | Contributors | Hidden after the week closes |
| Next item | Button (bar, primary, organiser in review) | "Next item" | Moves to the next undecided item | Organiser only | Disabled: "Every item has a fate." |
| Decide | Button (bar, secondary, organiser in review; also on each row) | "Decide" | Opens a sheet with **Problem**, **Backlog**, **Handled**, **Nothing** and a required reason; **Save** writes the fate | Organiser only | Not applicable |
| Talk to North | Button (bar, secondary, contributor) | See North sheet | Opens the sheet | Per North sheet | Per North sheet |
- **Touch.** The four fate buttons are 48 px, stacked. Every `broke` item needs a fate before the week closes; `ran` and `thought` items left open close as `nothing` with reason "Not reviewed this week" (brief ruling 3).

### Family 7. Problem (type problem)
Route: `/centre/intent/<id>`.
- **At 1280.** Header with state and 5-day time box; root cause, fix, owner, affected people in a two-column body; closure draft; North.
- **At 390.** Order: header (title, state pill, days left), "Waiting for you" line, owner and affected as one line each, root cause, fix, closure draft last. Each section is a collapsed row; the one that needs this person is open.
| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Header | Text | Title, state (`state`), days left (`time_box.ends`) | None | Everyone who sees the intent | "Not available yet. No time box set." |
| Waiting for you | Agent line (Nira) | What this person must do next | Scrolls to and opens that section | The person it waits for | Hidden |
| Owner, affected | Text rows | `people.owner`, `people.affected` | None | Everyone who sees the intent | "No owner named yet." |
| Root cause, Fix, Closure draft | Collapsed rows (44 px) | The record's text | Expands in place | Participants; affected only if switched on | "Not written yet." |
| Mark fixed | Button (bar, primary, owner) | "Mark fixed" | Owner records the fix | Owner only | Not rendered for others |
| Move to closing | Button (bar, primary, organiser) | "Move to closing" | Moves the state to closing (spec 01) | Organiser only | Disabled until a fix is written |
| Confirm closure | Button (bar, primary, approver) | "Confirm closure" | Approver confirms the closure draft | Approver only | Disabled until the draft exists |
| Talk to North | Button (bar, secondary) | See North sheet | Opens the sheet | Per North sheet | Per North sheet |

### Family 8. Decision (type decision)
Route: `/centre/intent/<id>`.
- **At 1280.** Decision statement; options side by side as columns with pros and cons; advisers' notes; the decider's panel; North.
- **At 390.** Options become one card each, stacked, collapsed to title and one line; the chosen option (once chosen) is pinned first. Advisers' notes sit under each option. No horizontal comparison table.
| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Option card | Collapsed card (56 px) | Title and one line; expands to pros, cons, notes | Expands in place | Participants; affected only if switched on | "No options added yet." |
| Compare | Button | "Compare" | Opens a full-screen sheet with two options at a time; swipe moves between pairs | Participants | Disabled with fewer than two options |
| Decide | Button (bar, primary, decider) | "Decide" | Opens a sheet: pick the option, write why, **Confirm** records the decision | `people.decider` only | Disabled until an option exists |
| Add a note | Button (bar, primary, adviser) | "Add a note" | Opens a one-field sheet; **Send** adds the note | Advisers | Not rendered for others |
| Talk to North | Button (bar, secondary) | See North sheet | Opens the sheet | Per North sheet | Per North sheet |

### Family 9. Closure (the closing state for every type)
Route: `/centre/intent/<id>/close`.
- **At 1280.** Summary, why it happened, what came out, next steps (initiative, backlog, problem, nothing, each with reason), rating, close button.
- **At 390.** One section per row in that order; North's draft text is shown in a field the closer edits. Next steps are a list of cards.
| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Summary, Why it happened, What came out | Fields | North's draft in an editable field (`closure`) | Closer edits | Closer; read-only to others | "North has not drafted this yet." |
| Next step card | Card | `next` entry: kind and reason | **Change** opens a sheet to pick the kind and write the reason | Closer | "No next step yet. Choose one, or Nothing with a reason." |
| Rating | Five 48 px buttons, 8 px apart | Scores 1 to 5, anonymous by default (brief ruling 15) | Tap records the score; an optional note | Everyone except where the type is not rated | Hidden for weekly check-in series and weeks (not rated, brief ruling 3) |
| Close intent | Button (bar, primary, closer) | "Close intent" | Closes the intent (spec 01) | Closer only | Disabled until summary, why and next are filled |
| Send back to open | Button (bar, secondary, closer) | "Send back to open" | Returns the state to open, while spec 01 allows | Closer only | Hidden when not allowed |
| Rate this | Button (bar, primary, everyone else) | "Rate this" | Scrolls to the rating | Everyone except where not rated | Not rendered where not rated |

### Family 10. Past
Route: `/centre/intent/past`.
- **At 1280.** Filter bar (type, area, date, outcome) over a table.
- **At 390.** Filter bar becomes one **Filter** button that opens a sheet. Table becomes rows.
| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Past row | Row | Title, type chip, closed date, outcome one-liner; cancelled rows read "Cancelled: " and the reason | Row has **Open outcome** | Per visibility rule (brief section 4) | "Nothing has been closed yet. Closed intents will appear here with what came out of them." |
| Open outcome | Button (44 px) | "Open outcome" | Opens `/centre/intent/<id>` read-only at the outcome | Same | Not applicable |
| Filter | Button (bar, primary) | "Filter" | Opens a sheet with type, area, date and outcome chips; **Apply** closes it | Everyone | Chips say "None set." |
No secondary bar action.

### Family 11. Share visitor (read-only)
Route: `/centre/intent/<id>/share`; the visitor entry stays at `POST /api/modules/m1_intent/shared/view` (brief ruling 1).
- **At 1280.** Read-only header ("Shared with you by Janet"), what was done, what was said and who said it (unless anonymous), what came out.
- **At 390.** Same order as the closure screen, all sections collapsed except "What came out". If the visitor has no account, no top-bar menu is shown, only the company name.
| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Section row | Collapsed row | Section title | Expands in place | Named visitor | "Nothing was recorded here." |
| Back to top | Button (bar, only action) | "Back to top" | Scrolls to the top | Named visitor | Not applicable |
| Expired message | Panel | "This link is not valid any more. Ask the person who shared it for a new one." | None | Anyone with a wrong or expired link | Not applicable |
No North, no sheet, no projector, no edit control anywhere.

### Projector view
Route: `/centre/intent/<id>/projector`. It is a page of its own (brief ruling 1), full screen, with no shell bar. The button **Projector view** goes there and asks the browser for fullscreen. On the wall today the same effect is a local toggle (`projector` state in `WallScreen.tsx` L102, chip at L156); that toggle is reshaped into a link to the route, and the wall's existing projector styling is reused on the route.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Projector view | Chip (existing `t.projector`) | "Projector view" | Goes to `/centre/intent/<id>/projector` and requests fullscreen | Organiser only | Not rendered for anyone else |
| Back to the full view | Chip (existing `t.exitProjector`) | "Back to the full view" | Returns to the previous view; Escape also leaves | Organiser only | Not applicable |
| Lane headings | Heading per lane | Lane name (existing copy) | None | Display | Lane still shown with count 0 |
| Lane counts | Number, large (existing `.ds-wall--projector .ds-wall-lane__count`) | Count of submitted cards per lane, from `getBoardCounts` | None | Display | "0" is a real count; where the count cannot be read, the lane says "Not available yet" |
| Current question | Text, large, up to three lines | `session.current_question.text`; for a weekly check-in review, the item under review (text only, no author) | None | Display | "No question is set yet." |
| Clock | Large time | Time left in the session or stage: `mm:ss` under one hour, `h:mm` over; "Over time" in the amber token when past | None | Display | "Not available yet" with "The session has no end set." |
| Join box | Panel with a QR code and a short link | "Join: " and `share.short`; the QR encodes the same link | None | Display | If the intent is not shared, "Turn on sharing to show the join code." with the button **Turn on sharing** (organiser only; writes `share.link` and `share.short`) |
| People count | Text | "5 / 7 people" (existing count only) | None | Display | Hidden when not available |
| Live dot | Chip (existing `t.live`) | "Live" | None | Display | Hidden when the session is not live |
| Reconnecting | Text, bottom strip | "Reconnecting" | None | Display | Shown only after repeated failed polls |

What the projector never shows: card text on wall lanes (existing rule in `Lane.tsx`: heading and count only), authors, initials, avatars, the North panel, the invite panel, the stage bar, "Show only mine", sealed or anonymous material, any "waiting for you" line, any admin control. The exception is the weekly check-in review, where the item under review shows as text without the name of who wrote it; anonymous items stay anonymous and sealed items show as "A sealed card about a restricted area" (existing copy).

**Layout at 1280 and above, and on a projector (1920 by 1080).** Top strip: current question left, clock right. Middle: lanes in one row, equal width, counts large. Bottom strip: join box left, people count and Live right. Colours from the dark tokens already in use; a high contrast between count and ground is required (value in Open questions 9).
**Layout at 390.** The route renders one column: question, clock, lanes as rows of name and count, join box. The **Projector view** chip is hidden on phone; the route is reachable by the link for a quick check, not for presenting.

**Refresh.**
| What | Today | In this spec |
|---|---|---|
| Wall counts | `WallScreen` loads the wall once through `useLoad` and again only after North's panel changes something. `useLoad` does not poll (`ui/src/components/useLoad.ts`) | The projector route polls lane counts through the existing counts route (`getBoardCounts`), not the full card list, using `usePolled` (`board/usePolled.ts`, `POLL_MS = 3000`) |
| Clock | `StageTimer.tsx` re-reads the server every 15 seconds and ticks every second | Reuse as is |
| Question | Not shown on the wall today | Read with the same poll from `GET /api/intents/{intent_id}` (field added in this feature) |
| Dropout | `usePolled` keeps the last view on a short failure | Keep the last numbers; after repeated failed polls show "Reconnecting" in the bottom strip; never blank the screen. The count of failures is an open question (9) |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)
**Phone participant in a brainstorm session.**
1. Aaron opens the invitation link on his phone, which lands on `/centre/intent/<id>/session`. North has already set the first question.
2. He sees the question strip, the clock and the lane tabs. He taps **Add an idea**, types, taps **Send**.
3. North reads the card (agent draft only) and may raise the dot on **Talk to North** with a clarifying question.
4. Aaron opens the sheet, answers, closes it.
5. He swipes across lanes to read the others' cards; counts update at the next poll.
6. When the session closes, the bottom bar becomes **Rate this**; he rates, then closes the page or taps the shell's back to leave the intent.

**Organiser with the projector.**
1. Janet opens the live session on her laptop, which is on the room screen. She sees the session at `/centre/intent/<id>/session`.
2. She presses **Projector view**. The browser opens `/centre/intent/<id>/projector` full screen. The QR code and short link show; the clock starts from the server time. North has drafted the next question; nothing is on the display until Janet puts it up.
3. People scan the code and join on their phones. The people count moves at the next poll.
4. Janet presses **Next question**; the projector shows it within one poll.
5. Janet presses Escape or **Back to the full view**, which returns her to the session, and later leaves the intent from the home link.

## States and transitions (table: state, who moves it, to what, what is written)
| State | Who moves it | To what | What is written |
|---|---|---|---|
| Projector route not open | Organiser (Projector view) | Projector route open | Nothing on the record; a display-on event in the run log |
| Projector route open | Organiser (Back to the full view, Escape) | Previous view | Nothing |
| Projector route requested by a non-organiser | Server | Refused; the person is returned to the intent screen | Nothing |
| Sheet closed | Anyone (Talk to North) | Sheet open | Nothing |
| Lane n | Anyone (tap or swipe) | Lane n plus or minus 1 | Nothing |
| Sharing off | Organiser (Turn on sharing) | Sharing on, short link exists | `share.link` and `share.short` through the sharing file's route |
| Session not live | North or organiser per spec 01 | Projector shows "Session closed" and the closing counts, no poll | Nothing |

The intent record states (spec 01) are unchanged by this feature.

## Records read and written (file or route, fields; mark Existing or New)
| Record | Use | Status |
|---|---|---|
| Wall route behind `loadWall` (cards, `submitted`, `people`, `closes`, `live`) | First load of the wall | Existing |
| `GET .../board/counts` (`getBoardCounts` in `ui/src/modules/m1_intent/api.ts`) | Projector poll for lane counts | Existing |
| Stage timer route read by `StageTimer.tsx` | Clock | Existing |
| Session purpose and topic (`useSessionLine`) | Purpose line | Existing |
| `GET /api/intents/{intent_id}` (spec 01) | Every family's data, the current question, `share` | New (spec 01) |
| `intents/<id>/weeks/<week_key>.json` | Weekly check-in items and fates, read only here | New (spec 38) |
| `session.current_question` on `intents/<id>/intent.json` | Question strip and projector | New field (see below) |
| `share.link`, `share.short` | Join box | New (spec 01 and below) |
| Short link resolver | Turns the short code into the join page | New |
| `intents/<id>/events.jsonl` display-on event | Counter of projector openings | New (spec 16) |
Nothing is written by a layout change.

## Fields this feature adds to the intent record
| Field | Shape | Written by |
|---|---|---|
| `session.current_question` | `{text, set_by, set_at}` or null, with `history` of earlier values | Organiser (**Next question**) or North when it proposes and the organiser accepts |
| `share.short` | string, a short unambiguous code; length in Open questions | Server on **Turn on sharing**; resolves only to the join page for that intent |

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)
- **North** drafts the current question text. The organiser presses **Next question** to put it up. North raises the dot on **Talk to North**; it never opens the sheet. North keeps the clock; it does not draw on the projector.
- **Lens** has no part in the projector. In define sessions on phone, Lens drafts show in the card sheet; a person presses **Confirm**.
- **Nira** puts the "Your turn" lines at the top of the phone home. No Nira text appears on the projector.
- No agent turns the projector on or off, and none signs anything on a phone.

## Rules (visibility, time box, who may do what)
- Only the organiser of that intent (and the company admin for a stuck intent, per spec 01) may open `/centre/intent/<id>/projector`. The chip is not rendered for anyone else, and the server refuses any other caller, because the route carries the join box and the question.
- The projector shows no names, ever. It shows counts and, for the weekly check-in review only, the item text. Anonymous and sealed rules (D-013, seal) hold.
- A super admin never sees content, so never gets the projector. A share visitor, an observer and a person who is only affected never get it.
- The join address on the projector opens the join page for the session. It lets a named invitee join; an unnamed person who scans it is asked for the name the organiser invited. The link follows `share.who_may_open`.
- Observers read what a participant reads and never write or vote (brief ruling 4), so **Add an idea** and **Add to this week** are not rendered for them.
- Any action on a phone has the same permission as at 1280. A bottom bar button the person may not press is not rendered.
- Time box: the clock shows the stage clock or the intent time box that the type defines; this feature sets no duration.
- Phone and projector show the same numbers as the 1280 view from the same records. Counts are exact (brief ruling 8).

## Counters and measures of this feature (numbers only, each traced to a record)
| Number | Traced to |
|---|---|
| Times the projector view was opened | Count of display-on events in `intents/<id>/events.jsonl` |
| People who joined by short link | Count of `share.short` joins in the session's participant record |
| Participants on a phone at 390 | Not available yet: the app does not record the viewport; needs a viewport field in the join event (Open questions 7) |
| Seconds from **Next question** to the projector showing it | Not available yet: the poll receipt time is not recorded |

**Shots a tester takes.** Run with `.venv/Scripts/python .sh-tmp/shot.py <email> <path> <out.png> --width 1280|390 [--click "text=..."]`. Emails come from `data/_control/seed_credentials.txt`; Janet for organiser views, Aaron for participant views. A 1920 shot uses `--width 1920 --height 1080`.
| Shot | Account | Path | Options |
|---|---|---|---|
| home-1280, home-390 | Janet | `centre/intent` | `--width 1280` / `--width 390` |
| chooser-1280, chooser-390 | Janet | `centre/intent/new` | same |
| wall-1280, wall-390 | Aaron | `centre/intent/<id>/wall` | same |
| wall-390-north-sheet | Aaron | same | `--width 390 --click "text=Talk to North"` |
| define-390, brainstorm-390, weekly-check-in-390 | Janet | `centre/intent/<id>/define`, `/session`, `/review` | `--width 390` |
| problem-390 (Harvey), decision-390 (Grace), closure-390, past-390 | each named account | `centre/intent/<id>`, `/close`, `centre/intent/past` | `--width 390` |
| share-390 | none (link) | `centre/intent/<id>/share` | `--width 390` |
| projector-1920 | Janet | `centre/intent/<id>/projector` | `--width 1920 --height 1080` |
| projector-as-Aaron | Aaron | same | `--width 1280`; passes when he is returned to the intent screen |
A shot passes when there is no horizontal scroll (`document.documentElement.scrollWidth <= 390`), every button is at least 44 px, and the projector shots show no name, initial or card text.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)
All paths below were checked and exist in this repo.
| Existing | Verdict |
|---|---|
| `ui/src/modules/m1_intent/wall/WallScreen.tsx` L19 (`PHONE`), L102-L106, L122, L148-L180: `projector` toggle, `phone` below 700, wide layout, North sheet, Talk to North button | **Reshaped.** Phone switch and sheet reused as they are. The projector toggle becomes a link to `/centre/intent/<id>/projector`. Added: organiser-only gate, fullscreen request, question, clock, join box, poll. Bottom bar and swipe are new |
| `ui/src/modules/m1_intent/wall/Lane.tsx` L6-L24: projector shows heading and count only | **Used as is** |
| `ui/src/modules/m1_intent/wall/wall.css` L35-L38 (projector sizes), L110-L120 (phone rules), L81 (sheet), L56, L79, L127 (touch heights 36, 32, 44) | **Reshaped.** Projector sizes raised for the clock and question; 36 and 32 raised to 44 on phone |
| `ui/src/modules/m1_intent/wall/copy.ts` (projector, exitProjector, laneSwitcher, talkToNorth, closeNorth) | **Used as is**; new strings added for question, clock and join box |
| `ui/src/modules/m1_intent/wall/NorthPanel.tsx`, `InvitePanel.tsx`, `StageBar.tsx` | **Used as is** inside the sheet or collapsed row |
| `ui/src/shell/CentreShell.tsx`, `ui/src/shell/barStyle.ts` L19-L22 (burger below 720) | **Used as is**; the shell is not changed |
| `ui/src/modules/m1_intent/board/usePolled.ts` (`POLL_MS = 3000`, keeps last view on dropout) | **Used as is** for the projector poll |
| `ui/src/modules/m1_intent/timer/StageTimer.tsx` (15 s poll, 1 s tick) | **Used as is** for the clock |
| `ui/src/modules/m1_intent/api.ts` (`getBoardCounts`) | **Used as is** for counts |
| `ui/src/components/useLoad.ts` | **Not used** on the projector: it does not poll |
| `ui/src/design/parts.tsx`, `MapColumns.tsx`, `icons.tsx`, tokens `--ds-*` | **Used as is.** No new component library. A shared bottom bar and a sheet are small new parts added to `parts.tsx` when the first screen needs them; the existing wall sheet is the pattern |
| `ui/src/modules/m1_intent/wall/wall.test.tsx` (projector and phone tests) | **Reused** and extended |
| QR code | Not found in `ui/src` (searched for a QR library and encoder). Genuinely new; open question 1 |

## Not in this feature
- A second display for the audience; a presenter mode with notes.
- Casting, remote control from the phone, or a clicker.
- A native app; push notifications.
- Offline use or adding cards without a connection.
- Changing card, lane, North panel or stage bar content (their own features).
- Landscape-specific phone layouts.
- The content of the per-type screens (specs 22, 35, 38, 41, 43); this file sets only their phone layout and bar.

## Open questions
1. Which QR library, or is a short link alone enough for the first build? Neither a library nor an encoder was found in `ui/src`.
2. Short link host and format: a short code under the app's own host, or a company short domain? The brief names none.
3. Should the poll interval be 3 seconds (as the board) or 5 for a projector that runs for an hour? The wall carries ten to twenty people, so 3 is assumed.
4. May the sponsor open the projector view, or the organiser only? The brief says organiser; this file follows it.
5. Specs 03 and 04 must both use `/centre/intent/new`; spec 04's `/centre/intent/start` is wrong under ruling 1 and is corrected in the review wave.
6. Projector on weekly check-in review shows item text: is that acceptable for items an ops person wrote in confidence? The default here is text without author; the organiser may need a per-item **Hide** control.
7. Should the viewport width be recorded on join to count phone use? Needs a decision before the counter is available.
8. Should swipe between lanes wrap at the ends? Assumed not.
9. Values this file proposes that the brief does not give, all to be confirmed: touch targets 44 and 48 px; bottom bar 56 px; page padding 96 px; sheet height 80 vh; swipe threshold 60 px with 30 px drift; the 390 and 360 widths; text sizes; the number of failed polls before "Reconnecting" (3 proposed); the contrast ratio on the projector (7 to 1 proposed); the short code length (six proposed).
10. Closure for a weekly check-in week: rating is hidden because ruling 3 says weeks and series are not rated. Confirm that **Rate this** should simply not render there.
