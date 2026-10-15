# 12. Past intents and history

Part of: Intent Centre v2. Depends on: 00-BRIEF, 01 (record and folder), 05 (visibility, sharing and read-only opening), 09 (closure), 10 (ratings), 16 (events), 20 (links, chain, Intent nodes on the graph). Feeds: 04 (front page running and past counts), 13 (Pulse lines), the avatar menu.

## Purpose (three sentences)

The Past view is the record of everything the company has intended, by area and by month, so anyone in an area can see what was discussed before and what came of it. Nothing is deleted: closed intents keep their thinking and outcome, and cancelled intents keep their reason and appear here. A "where did this lead" chain shows, from one intent, the intents, build work and release it produced, using the chain that file 20 builds from the links already in the records.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Anyone tagged to an area (Aaron, Katie) | Before starting something: "has this been discussed already?" | Opens Past, picks their area, searches a word |
| Organiser (Janet) | Starting a new intent on a topic that may have history | North shows "Similar past intents" on the chooser; Janet opens one |
| Sponsor (Daniel) | Quarterly review of what each area intended and what was used | Opens Past, groups by area, reads the counters |
| Owner, decider, approver (Harvey, Grace) | Checking what a past decision or problem fix said | Follows a link from a Pulse line or a chain |
| Company admin | Audit: every intent's existence and outcome | Opens Past; sees cards and outcomes, never content or anonymous notes |
| Super admin | Not a user of Past | Reads intent existence at `/centre/control/intents` (file 48); there is no Past entry for the role |
| Any person | "What was I in?" | Avatar menu, "Intents I was in" |

Agents decide and draft: North suggests similar past intents and drafts the one-line outcome used on the closed card. People act: a person opens, filters, shares, and rates (rating is in files 09 and 10, shown here read-only).

## Entry points (every route, link, Pulse line, button that leads here)

- Intent Centre front page (`/centre/intent`): tab "Past" beside "Running" (route `/centre/intent/past`).
- Avatar menu: "Intents I was in" (route `/centre/intent/past?mine=1`).
- Closure screen (`/centre/intent/<id>/close`): after closing, link "See it in Past".
- Chooser (`/centre/intent/new`, North): "Similar past intents" list, each opens `/centre/intent/<id>`.
- Pulse line from Nira: "Three intents in Treasury closed this month" links to Past filtered by area and month.
- Intent screens: the "From" and "Led to" chips link to `/centre/intent/<id>` for closed ones.
- Graph node page (`/centre/intent/map/<node id>`, existing v1 route): for an Intent node the "asked" step links to `/centre/intent/<id>`.
- Share link: the visitor entry `POST /api/modules/m1_intent/shared/view` (file 14) opens the read-only view of that one intent, not the Past list.

## Screens, element by element

Every count on these screens is counted by the server from `intents/<id>/intent.json` for the intents the viewer may see (see Counters). Dates and months use the company's time zone from the profile, else UTC.

### Screen A. Past list

Route: `/centre/intent/past`. Query: `?area=`, `?type=`, `?outcome=`, `?q=`, `?from=`, `?to=`, `?mine=1`.

Layout at 1280: page title "Past intents" with a subline "Everything the company has intended. Nothing is deleted." Left rail: area list with counts and the filters. Centre (rest): timeline by month, newest first; inside each month, intents grouped by area (one band per area, area name as the band heading). Right: none. Top strip: counters (see Counters).

Layout at 390: rail becomes a "Filters" button opening a sheet; counters stack to one column; month headings stay sticky; cards full width, outcome line truncates to two lines; the area band heading stays.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Page title and subline | text | "Past intents" and the keeping rule | None | All signed-in company roles except super admin | Always shown |
| Search box | field | Placeholder "Search title and purpose" | Typing filters the list after a short pause (Open question 1); matches `search_text`, case-insensitive, whole words first; writes `?q=` | All | Empty box shows everything |
| Area list (rail) | list of chips | The viewer's areas, then "All areas", each with the count of past intents in view (count of `intent.json` files with that area, state closed or cancelled) | Click selects an area; second click clears; writes `?area=` | All; a person sees only areas they belong to plus areas of intents they may see (05) | "You are not tagged to an area yet. Ask your admin." with link "Open my profile" |
| Type chips | chip group | Initiative, Brainstorm, Weekly check-in, Problem, Decision, with counts (`type`) | Toggle; several may be on; writes `?type=` | All | A type with zero shows dimmed with "0" |
| Outcome chips | chip group | "Became an initiative", "Went to backlog", "Became a problem", "Nothing came of it", "Decision made", "Cancelled" | Toggle; writes `?outcome=`. The first four come from `closure.next[].kind`; "Decision made" is `type=decision` with `state=closed`; "Cancelled" is `state=cancelled` | All | Dimmed with "0" |
| Date range | field pair | "From" and "To" month pickers (native month input) | Narrows the timeline by `closed_month`; default window in Open question 1 | All | "Nothing in this range. Widen the dates." with button "Clear dates" |
| "Only mine" toggle | switch | On: only intents where the viewer is in `people` | Writes `?mine=1` | All | Off by default |
| Clear filters | button | "Clear filters" shown when any filter is on | Resets the query string | All | Hidden when no filter |
| Month heading | heading | "October 2026" and the count of intents closed or cancelled that month (`closed_month`) | Click collapses or opens the month | All | A month with no intents is not shown |
| Area band | heading | Area name and count in that month | Click collapses the band | All | Not shown if empty |
| Intent card (closed form) | card, see Screen B | One past intent | Click on the title opens Screen C | Per 05 | n/a |
| Show older months | button | "Show older months" after the default window | Loads the next window | All | Hidden when no older record |
| Empty page | panel | Title "Nothing in the past yet." Lines: "Intents appear here once they close or are cancelled." Link "Start an intent" | Link goes to `/centre/intent` | All | Shown when the company has no closed or cancelled intent |
| Filter-empty panel | panel | "No past intent matches." Lines: the active filters in words. Button "Clear filters" | Resets | All | Shown when filters match nothing but records exist |
| Similar-intents agent line | agent line | North: "Three past intents mention 'custody fees'." Shown only when `?q=` has a term and there are matches in other areas the viewer may see (count of matches) | Click opens the list filtered by that term across areas | All | Hidden when no match |

An intent's month is the month of `closure.closed_at`, or the cancellation date for cancelled intents (`closed_month`). Only intents in state `closed` or `cancelled` appear on this list. An intent in state `draft` is visible only to the person who started it and never appears in Past. A closed intent appears once, under its first area, and in every other area's band with a small "also in" mark (not duplicated in counts).

### Screen B. The intent card, closed form

A card on Screen A, in the chain and in "Intents I was in". It is a reshaped `Strip` look and the `Pill` and `Chip` parts from `ui/src/design/parts.tsx`, with no new component family.

Layout at 1280: one row: left a type chip and title; middle dates and organiser; right the outcome line and next links. At 390: stacks to four lines: title with type chip, dates, outcome line, next links; rating on the dates line.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Type chip | chip | Initiative, Brainstorm, Weekly check-in, Problem or Decision | None | All who see the card | Always |
| Title | link | `title` | Opens Screen C | All who see the card | Always |
| Area tags | chips | `areas` | Click filters Past to that area | All | Always at least one |
| Dates | text | "Opened 2 Mar, closed 6 Mar 2026" (opened = `created_at`; closed = `closure.closed_at`) | None | All | Cancelled: "Opened 2 Mar, cancelled 4 Mar" |
| Organiser | text | `people.organiser` name | None | All | "Not recorded" |
| People count | text | "6 people": count of `people.organiser` plus `people.participants` | None | All | "No participants recorded" |
| Outcome one-liner | text | `closure.what_came_out`, first sentence, shortened (Open question 1). North drafts it at closure, the organiser confirms | None | All tagged to the areas (outcome is open to them, brief section 4) | "Closed without a written outcome" |
| Cancelled mark | pill | "Cancelled" and the reason from `closure.summary`, one line | None | All | A reason is required to cancel, so never empty; an older record without one shows "No reason recorded" |
| Next links | chip list | One chip per `closure.next[]`: "Initiative: Treasury cash view", "Backlog", "Problem: late notices", "Nothing, because ..." | Click opens the target's card (Screen C) or, if still running, its live screen; backlog opens the item (file 21) | A chip for a target the viewer may not see reads "Restricted" with no name | "No next step recorded" |
| Rating average | text | "4.2 from 5 ratings" (mean of `ratings[].score`, count of `ratings`) | None | Only for types that are rated (file 10; a Weekly check-in series is never rated) and only from three ratings; never anonymous notes | Hidden when fewer than three, or not rated |
| "Also in" mark | text | Other areas the intent covers (`areas`) | None | All | Hidden when one area |

### Screen C. A past intent, opened (read-only)

Route: `/centre/intent/<id>`. This is the closed form of the intent screen: for a closed or cancelled intent the stage view is replaced by the tabs below (Open question 2). Also reached by share link (05, 14).

Layout at 1280: header strip (title, type chip, state, dates, areas); two columns. Main (two thirds): tabs "What was done", "What was said", "What came out". Side (one third): People, Time box, Links, "Where did this lead" preview, Versions. At 390: side panels fold below the main in that order; tabs scroll horizontally.

Who opens content: a participant, an observer (reads what a participant reads, never writes), a named person on the intent's share, an affected person only when the organiser switched on "affected people may read" at creation (default off), and named people on a share link. Everyone else tagged to the areas, including an affected person with the switch off and the company admin, sees the header and "What came out" (brief section 4, ruling 4).

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Read-only banner | strip | "This intent is closed. You are reading the record." (cancelled: "This intent was cancelled. Reason: ...") | None | All | Always |
| Header | text | Title, purpose, type chip, state pill, areas, organiser, sponsor | None | All who may see it exists | Always |
| Tab "What was done" | tab | The stage history from `stages` with opened and closed dates; the wall, charter, baseline and assessment as links to the existing screens, read-only | Link opens the existing screen in read-only form | Content viewers only | "No stages were recorded." |
| Tab "What was said" | tab | The thinking kept: wall notes, brainstorm ideas, check-in items, problem notes, decision options, each with author name. Anonymous shows "Anonymous"; sealed shows "Sealed" with no text (D-013, seal) | None | Content viewers only. Company admin sees no content unless also a participant, and never anonymous notes | "Nothing was said in the record." |
| Tab "What came out" | tab | `closure.summary`, `why_it_happened`, `what_came_out`, `next` with reasons, the type's `outcome` object | None | Everyone tagged to the areas | "No outcome was written." |
| Tagged-only view | panel | For a person tagged to the area without content access: header, "What came out", People, Time box, and the line "You can see that this was discussed and what came of it. The thinking is open to the people who were in it." with button "Ask the organiser to share" | Button calls `POST /api/intents/<id>/share-request`; adds a Pulse line for the organiser (13) | Tagged non-participants; company admin sees the panel without the button | Hidden for content viewers |
| People panel | list | `people`: organiser, sponsor, decider, owner, reporter, participants, affected, observers with names (anonymous raters not listed) | None | Everyone who sees the card (ruling 4 gives affected people the people list) | "No people recorded." |
| Time box panel | list | `time_box.starts`, `ends`, each extension with who, when, reason | None | Everyone who sees the card | "No extension." |
| Links panel | list | "From" intent, "Led to" intents, build reference | Each opens its card | Per target visibility | "Not linked to anything." |
| "Where did this lead" preview | strip | The chain from file 20's chain route, collapsed to one line of steps | Click opens Screen D | Per target visibility | "Nothing followed from this intent." |
| Versions panel | list | `VersionList` rows built from the intent's events (16): "Closed by Janet", "Outcome confirmed by Janet", "Note added by Janet", "Shared with Aaron" with dates | None | Content viewers | "No changes since closing." |
| Rating summary | text | Average and count as on the card; notes of ratings given by name only | None | As on the card; notes only to content viewers | Hidden |
| Share this record | button | "Share this record" | Opens `/centre/intent/<id>/share` (05) | Organiser only | Hidden for others |
| Add a note | button | "Add a note" (organiser only) | Opens a text field; Save calls `POST /api/intents/<id>/note` | Organiser only | Hidden for others |
| Back to Past | link | "Back to Past" keeping filters | Returns with the query string | All | Always |

There is no edit control. Closed content is signed and read-only (rule 7). A correction is a new note on the record by the organiser, shown as a new version row, never an overwrite.

### Screen D. "Where did this lead" chain

Route: `/centre/intent/past/<id>/chain`. Also an overlay from the preview on Screen C. The chain itself is file 20's `GET /api/intents/<id>/chain` at the viewer's tier; Past adds the release step and the map panel.

Layout at 1280: a left-to-right chain of step cards (file 20's `Chain` component), each the closed card in compact form, joined by arrows; the opened intent is highlighted; steps before it are on the left ("Came from"), after it on the right ("Led to"). Under the chain, a panel "On the map". At 390: the chain turns vertical, earliest at top, with the opened intent marked "You are here".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Chain step | card | Type chip, title, closed date, state: "Brainstorm: Treasury ideas, closed 6 Mar" then "Initiative: Cash view, closed 20 Mar" then "Build: Cash view pipeline" then "Release: 2 Apr" | Intent steps open Screen C; build and release steps open the Build screen they name | Per target; an unseen step shows as "A restricted step" with its type and date, no title | n/a |
| Direction label | text | "Came from" and "Led to" | None | All | Hidden when that side is empty |
| Branch marker | pill | "3 branches" when one intent has several `links.to` | Click expands the branches below, one lane each | All | Hidden for a single chain |
| Not yet step | card | For a running target: "Running, due 12 Oct" (its `time_box.ends`) with its live link | Opens the live intent | Per target | n/a |
| Open step | card | A target named in `closure.next` with no record yet: "Backlog item, not started" | Opens the backlog item (21) | Per target | n/a |
| "On the map" panel | panel | The sentence built the way `trail()` in `GraphPage.tsx` builds it (asked, defined, supplied, owned) for each measure or term this chain touched | Opens the node page | Per the graph's own gating (`_sees`, node `restricted_to`) | "This chain did not touch the map." |
| Back | link | "Back to the intent" | Returns to Screen C | All | Always |
| Empty chain | panel | "Nothing came before or after this intent." | None | All | Shown when `links.from` is null, `links.to` empty and `links.build` null |

How the chain is built (no new store): Past does not walk links itself. It reads file 20's chain route, which walks `links.from` up and `links.to` down with a visited set. Where the intent has `links.build`, the release step comes from the release record Build keeps for that reference (Open question 3). Where an intent's records point at a wall, charter or baseline, the graph (`graph/company.json` through `sh_platform/graph/read.py`) supplies the measures and terms that came from it, so the screen can say what reached the map. File 20 adds the Intent node (`intent:<id>`) and the `led_to`, `came_from` and `built_by` edges to that same graph; Past reads the chain from the route and the measures from the graph, and never edits either.

### Screen E. "Intents I was in" (avatar menu)

Route: `/centre/intent/past?mine=1`. The avatar menu entry shows the count read from the viewer's `people` entries.

Layout at 1280: the Past list with the "Only mine" toggle on and fixed, grouped by year, then month, then role. At 390: single list, role as a small label.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Avatar menu item | link | "Intents I was in (14)", count of intents with the viewer in `people` | Opens Screen E | The signed-in person | Count hidden when 0 |
| Role label | chip on each card | The slot the person holds: "Organiser", "Sponsor", "Decider", "Owner", "Reporter", "Participant", "Affected" or "Observer" | None | The person | n/a |
| Still running | section | Running intents the person is in, with live links (never drafts started by someone else) | Opens the live intent | The person | Hidden when none |
| Year group | heading | "2026" with count | Collapses | The person | n/a |
| Empty state | panel | "You have not been in an intent yet." Lines: "When you take part, it is listed here." Link "See what is running" | Goes to `/centre/intent` | The person | Shown when none |

A person sees intents where their own account is in `people`. Anonymous contributions are never listed against the person's account (05). A person's own ratings are listed in their own file (10), not here.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Aaron opens Past from the front page. The screen loads his areas (Treasury, Operations) and the default window.
2. Between steps: the server filters the intent files by his profile through `sh_platform/profile/view.py`, so he sees only intents whose areas he may see, and no drafts.
3. Aaron types "custody" in the search box. North shows an agent line: "Two past intents in Operations mention custody."
4. He selects the area chip "Operations" and the outcome chip "Became an initiative". The list narrows to one card.
5. He reads the card: title, dates, organiser Janet, outcome line, next link "Initiative: Custody fee review".
6. He opens the card (Screen C at `/centre/intent/<id>`). He is tagged for this one but did not take part, so he sees the tagged-only view. He presses "Ask the organiser to share". North adds a line to Janet's Pulse.
7. He opens "Where did this lead". The chain shows brainstorm, initiative, build, release. One step shows as "A restricted step".
8. He presses a link on the initiative step and reads its closed record, which he took part in.
9. He opens the avatar menu, "Intents I was in (3)", and finds his own record.
10. He leaves with "Back to Past"; filters are kept in the address.

## States and transitions (table: state, who moves it, to what, what is written)

Past is a view; it moves nothing except the records below.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| closed | Organiser closes (09) | Appears in Past under its closing month | Nothing here; Past reads `intents/<id>/intent.json` |
| cancelled | Organiser or sponsor cancels, reason required | Appears in Past with the "Cancelled" pill | `closure.summary` holds the reason; Past reads it |
| closed, outcome line empty | North drafts the line at closure; organiser confirms | Card shows the line | `closure.what_came_out` (09 writes it) |
| closed, read-only | Nobody edits | Stays read-only | Corrections are an appended note in `history_notes[]` and an event row (16) |
| shared | Organiser, in the share dialog | View opens for named people | `share` (05) |
| share-request | A tagged person without content access presses "Ask the organiser to share" | A Pulse line for the organiser | `share_requests[]` (see below) |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Kind | Fields used | Read or written |
|---|---|---|---|
| `intents/<id>/intent.json` (company plane, through `sh_platform/jsonfile.py`) | New (brief section 3, folder per ruling 12) | id, type, title, purpose, areas, people, state, time_box, stages, outcome, closure, ratings, links, share | Read; written only for `history_notes` and `share_requests` |
| `intents/<id>/events.jsonl` | New (file 16) | Close, note and share events | Read for the Versions panel; the note and share-request routes append events through 16's writer |
| `sh_platform/profile/view.py` `sees_area`, `allows` | Existing | Viewer and area gating | Read |
| `graph/company.json` (through `sh_platform/graph/read.py`) | Existing; Intent nodes and edges New (file 20) | Nodes, edges, `restricted_to` | Read |
| `GET /api/company/graph/node/{id}` (`sh_platform/graph/versions.py`) | Existing | Trail, owner, versions for a node | Read, for the "On the map" panel |
| `GET /api/intents/past` | New | Query: area, type, outcome, q, from, to, mine, page. Returns cards, counters, month groups | Read |
| `GET /api/intents/{id}` | New (shared with 01 and 05) | The record filtered for the viewer's tier | Read |
| `GET /api/intents/{id}/chain` | New (file 20) | Chain steps at the viewer's tier | Read |
| `GET /api/intents/mine` | New | The viewer's intents with role | Read |
| `POST /api/intents/{id}/note` | New | `{text}`, organiser only | Written to `history_notes` and an event row |
| `POST /api/intents/{id}/share-request` | New | `{}`, tagged person without content access | Written to `share_requests` and a Pulse line |
| `POST /api/modules/m1_intent/shared/view` | New (file 14) | Share visitor entry | Not called by Past; named so the share link path is clear |
| `modules/m1_intent` sessions, `m2_baseline`, `m3_connect` records | Existing | Referenced by the intent record, opened read-only | Read |
| Build release records | Existing or to be named by Build | Reference id, release date | Read (Open question 3) |

Every list is filtered per viewer on the server. The client never receives a title it may not show.

## Fields this feature adds to the intent record

```
history_notes: [{by, at, text}]          # corrections or later facts added after closing; never replaces closure
share_requests: [{by, at, state: open|answered}]
search_text: string                      # derived on write: title plus purpose, lower case, for the search box
closed_month: "YYYY-MM"                  # derived on close or cancel, in the company's time zone; the timeline key
```

`search_text` and `closed_month` are derived from other fields and rebuilt if missing. No other field is added. None of the brief's section 3 fields is renamed.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** drafts the one-line outcome at closure (first sentence of `what_came_out`, plain words), drafts "Similar past intents" on the chooser and the search agent line, and drafts the cancel summary when the organiser gives a reason. The organiser confirms the outcome line; nobody else edits it. North never states a rating or a count it cannot trace to a record.
- **Lens** is not used here. Past does not define anything.
- **Nira** adds Pulse lines: "Aaron asked you to share the Treasury ideas record" and the monthly line "Four intents closed in your area" (count of `closed_month` in the person's areas).
- A person acts at: opening a record, pressing "Ask the organiser to share", the organiser sharing or adding a note. Agents never sign and never edit a closed record.

## Rules (visibility, time box, who may do what)

- Everyone tagged to an intent's areas sees the card: title, purpose, stage, organiser, people, clock and outcome once closed. They open the content only as a participant, an observer, a person named on a share, an affected person when the organiser switched on "affected people may read" (default off), or a person named on the share link (brief section 4, ruling 4; 05 defines opening).
- Participants see all, except sealed and anonymous material, which keep the v1 rules (D-013, seal).
- The company admin sees every card and outcome, never content or anonymous notes. The super admin has no Past; existence only is read at `/centre/control/intents` (ruling 5, request A-074).
- A restricted target in a chain or a next link shows "Restricted" with type and date, never a title.
- Draft intents never appear in Past. Cancelled intents appear with their reason.
- Nothing is deleted. There is no delete or hide button on Past. A mistaken intent is closed with the reason or cancelled with the reason.
- A closed record is read-only. The organiser may add a note; it appears as a new version with name and date.
- Time box: none applies to history. Past shows a closed intent's `time_box` and extensions as recorded.
- Rating average shows only for rated types and from three ratings (ruling 8). Ratings are anonymous by default; no per-person average exists (ruling 15). A Weekly check-in series and its weeks are not rated (ruling 3).
- Search covers only titles and purposes of intents the viewer may see. It never searches content the viewer cannot open.
- Share links never appear in Past lists for people not named.
- British spelling, no game words, no vendor names in any string.

## Counters and measures of this feature (numbers only, each traced to a record)

Shown in the strip on Screen A for the chosen area and range. Each is computed from `intents/<id>/intent.json` and says "Not available yet" with what is missing when the records cannot give it. Counts are exact. Any mean, median or per-person figure shows "Fewer than five" below five records, except the rating average, which follows the ratings rule of three (ruling 8).

| Counter | Definition | Traces to |
|---|---|---|
| Intents per quarter | Count of intents by `closed_month` quarter, by area, split by type | `closed_month`, `areas`, `type` |
| Outcomes used | Count of closed intents with at least one `closure.next` of kind initiative, backlog or problem, with the count of closed intents beside it | `closure.next[].kind`, `state` |
| Of those, still running or done | Count of next targets whose own record is open, closed or has a `links.build` | `links.to`, target `state`, `links.build` |
| Cancelled | Count with `state=cancelled` | `state` |
| Closed with nothing | Count where every `next.kind` is "nothing" | `closure.next` |
| Average rating | Mean score of rated intents in view; only intents meeting the rating rule | `ratings` |
| Intents I was in | Count of intents where the viewer is in `people` | `people` |

"Outcomes used" is shown as two counts, for example "9 of 14 closed intents led to something." A quarter with no closed intent shows "No intent closed this quarter." Counters include only intents the viewer may see; the strip says "Counted from the intents you can see" when that differs from the company total (the company admin sees the total). No figure is shown per person.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Paths below were checked to exist in this repo.

| Existing | Where | Decision |
|---|---|---|
| Trail sentence builder `trail()` | `ui/src/pages/GraphPage.tsx` lines 93 to 105 | Reshaped: same asked, defined, supplied, owned logic feeds "On the map". File 20 reshapes the same function into `chainSentence(chain)` for the chain; Past uses that for the chain line and `trail()` only for measures. Not rebuilt |
| `Trail`, `TrailStep` | `ui/src/design/parts.tsx` line 212 onwards | Not used for the chain: file 20 adds a `Chain` component for chain cards and Past reuses it. `Trail` stays for the node page |
| `VersionList` | `ui/src/design/parts.tsx` line 244 onwards; used in `ui/src/pages/NodePage.tsx` | Reused as is for the Versions panel, fed from events (16) |
| `NodePage` layout (header, `SideCard`, `CommentThread`) | `ui/src/pages/NodePage.tsx` (192 lines) | Reshaped: Screen C copies its header and side-card layout; comments are not used on closed records |
| `append_version`, `plain_versions` | `sh_platform/graph/versions.py` lines 40 and 110 | Not used for intent versions: file 16 keeps one `events.jsonl` per intent and owns the trail. `plain_versions` is the pattern for folding same-day rows |
| `GET /api/company/graph/node/{id}` | `sh_platform/graph/versions.py` | Reused, read-only, for the "On the map" panel |
| Register page | `sh_platform/graph/register.py` (`register`, `_stages`, `_lineage`) and `ui/src/pages/RegisterPage.tsx` | Reshaped, not copied: the register's `origin` link `/centre/intent/map/{id}` shows where "asked, defined" came from. Past does not list definitions, so it links to the register and does not duplicate it |
| Intent nodes on the graph (`add_intent_nodes`, edges `led_to`, `came_from`, `built_by`) | Specified in `docs/specs/intent-centre/20-linking-intents.md` (section "The graph"); builder `sh_platform/graph/intent_nodes.py` does not exist yet | Reused as specified: Past reads, never writes. Replaces this file's earlier assumption that intents are not graph nodes |
| Viewer gating | `sh_platform/profile/view.py` (`sees_area` line 79, `allows` line 38) | Reused for every list and chain step |
| Atomic JSON read and write | `sh_platform/jsonfile.py` (`read_json_strict`, `lock_for`) | Reused for `intents/<id>/intent.json` |
| `EmptyState`, `StatCard`, `StatGrid`, `Pill`, `Chip`, `Strip`, `PageFrame`, `Footnote` | `ui/src/design/parts.tsx` lines 30 to 189 | Reused for every empty state, counter and chip |
| Avatar menu | `ui/src/App.tsx` (comment at line 90) and `ui/src/components/AgentChip.tsx` | Reshaped: add one item "Intents I was in" to the existing menu; no new menu |
| Outcomes page | `ui/src/pages/OutcomesPage.tsx`, route `intent/outcomes` (`ui/src/App.tsx` line 108) | Not used. It lists v1 outcomes; Past replaces nothing there. Open question 4 |
| Route structure | `ui/src/App.tsx` lines 104 to 109 under `RoleGate centre="intent"` | Reused: add `intent/past` and `intent/past/:id/chain` beside `intent/outcomes`; `intent/:id` belongs to the intent screen (01, 04) |
| Earlier repo | `<earlier repo>` | Searched for history, timeline and archive screens before writing; none found to copy beyond the above |

Genuinely new: the month and area timeline, the filters, the "mine" list, the counters strip, the closed form of the intent screen, and the read routes under `/api/intents/`.

## Not in this feature

- Editing or reopening a closed intent (09; reopening is not allowed in this round).
- Deleting, archiving or hiding an intent.
- Starting, running or closing an intent.
- Building the chain and the Intent graph nodes (20); Past reads them.
- Sharing rules and link creation (05, 11); Past only calls the dialog.
- Giving a rating (10); Past only shows the average.
- Tracking who viewed a record. Past shows no view counts and no read receipts.
- The Moment of truth screen and gap analysis (Build, `/centre/build/gap-analysis?from=<id>`).
- Export of the timeline to a file.
- Notifications beyond the one share-request Pulse line.

## Open questions

1. Values this file needs and the brief does not give: the search pause before filtering, the default date window (12 months proposed), the step for "Show older months", the one-liner length limit (140 characters proposed). None has a business rule behind it.
2. Is Screen C the same page as `/centre/intent/<id>` shown in its closed form (assumed), or does file 01 or 04 want a separate closed view under `/centre/intent/<id>/<view>`?
3. Which Build record names a release and its date, so the chain's release step can be traced? Until named, the chain stops at the build reference and shows "Release: not available yet".
4. Does `OutcomesPage` (v1) fold into Past, or stay as the list of outcomes awaiting use?
5. May a tagged non-participant see the "What came out" tab for a Decision whose options were sensitive? The outcome is visible per the brief; the options inside it may need a sealed flag from 05.
6. Where do pre-v2 intents (v1 walls with no intent record) appear? Proposed: not at all until migrated, with a line "Earlier walls are not shown here yet."
7. Should the chain stop with "A restricted step" where it would cross areas the viewer cannot see? Assumed yes; file 20 owns the final rule.
8. The map node page is `/centre/intent/map/<node id>` in existing code (`register.py`) but is not in the brief's route list. Does it stay, and is Intent node `intent:<id>` opened there?
9. Outcome chips cover next kinds initiative, backlog, problem and nothing. File 20 adds Decision and Brainstorm as next kinds; do they get chips?
10. Backlog target: without a Backlog node (file 20, open question 3) an "Open step" for a backlog item has no graph end; it is read from file 21 instead.
