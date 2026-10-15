# 15. Search and filters (finding an intent)

Part of: Intent Centre v2. Depends on: 00-BRIEF (intent record, visibility rule, section 10 rulings), 01 (intent record and folder layout), 02 (intent types catalogue), 05 (areas and visibility), 10 (ratings). Feeds: 04 (Intent home) and 12 (Past intents); they own the page, this feature owns the search box, chips, sort, result card, the list API and the index file.

## Purpose (three sentences)

A company can run hundreds of intents a year, and a person must be able to find one by what they remember: a word in the title, the area, who organised it, or what came out. This feature gives the Intent home and the Past view one search box, seven filter chip groups, a sort and one result card, all answered by `GET /api/intents`, which returns only what the signed-in person may see. It keeps a large company fast with one small index file, `intents/_index.json`, which sits beside the `intents/<id>/` folders and is updated on every write.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Any person tagged to an area (Harvey, Grace, Aaron) | "Did we already look at this?" or "What came out of the onboarding review?" | Types in the search box on Intent home or Past |
| Organiser (Janet) | Finds her own intents, her drafts and closed ones | Chip "My role: Organiser" |
| Participant, observer, or affected person who may read | Finds an intent they were in, including its card text | Searches a phrase they wrote or read |
| Sponsor (Daniel) | Finds what is ending soon and what is past its end | Sort "Ending soonest", chip "Past its end" |
| Company admin | Checks that intents exist and what came out | Chips "Closed", "Outcome kind" |
| Super admin | Reads existence only (title unless the company keeps titles private, type, state, areas, people count, dates, time box status) | Reads through the kernel on request; page is `/centre/control/intents` (not this file) and uses this list API at tier 0 |
| North (agent) | Drafts the outcome line at closure; once a named person confirms it, that line is searchable | Closure confirmed by a named person |

People act: type, filter, sort, open. No agent searches for the person and no model is called for search.

## Entry points (every route, link, Pulse line, button that leads here)

- `/centre/intent` (Intent home): the search and results region sits under the five type cards. Shows intents that are not yet closed or cancelled.
- `/centre/intent/past`: same region, showing closed and cancelled intents. Reached from the link "Past intents" on Intent home.
- Link "See all in this area" on an area chip elsewhere in the centre: opens `/centre/intent?area=<area>`.
- Line on the daily Pulse page from Nira, "3 intents in Operations end this week": opens `/centre/intent?area=Operations&sort=ending`. (The count is read from the index at query time.)
- API: `GET /api/intents` (new). Facet counts come back in the list response; there is no separate facets route.

Filter chips and sort go in the page address (`?type=brainstorm&state=open&sort=newest`). The search text does not: it stays in page memory, because people type names into it (no personal data in a URL).

## Screens, element by element

### Screen A: Intent home and Past, search region

Routes: `/centre/intent` and `/centre/intent/past`. One component, one `view` value (`home` or `past`).

Layout at 1280: one row with the search box (wide) and the sort select at the right; under it one row of chip groups that wraps onto a second row if needed; under that a count line and the active-filter strip; then result cards in a two-column grid with "Show more" at the bottom. At 390: search box full width; one row with a "Filters" button (showing the number of active filters) and the sort select; the chip groups move into the filter sheet (Screen B); active filters show as removable chips in a single row that scrolls sideways; cards stack in one column.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Search box | field (`type="search"`) | Placeholder "Search by title, purpose, area, organiser or outcome" | After a short pause in typing (proposed 250 ms, minimum 2 characters, Open question 11) calls the API with `q`. Clearing (the x, or Escape) restores the list. Enter searches at once. | Everyone signed in with a seat | Empty box shows the list unfiltered |
| Search scope hint | text with button "Got it" | "You are searching titles, purposes, areas, organisers and outcomes. Card text is searched only in intents you may read." | "Got it" hides it for the session | Everyone whose highest tier is below content on every intent | Hidden once dismissed |
| Type chips | chip group (single choice with "Any") | Initiative, Brainstorm, Weekly check-in, Problem, Decision, each with its count from `facets.type` | Sets `type`; list reloads | Everyone | A type with 0 visible intents stays shown, greyed, count 0 |
| State chips | chip group (multi choice) | Home: Draft, Open, In session, Closing. Past: Closed, Cancelled. Each with its count from `facets.state` | Sets `state`; list reloads | Everyone; "Draft" only for a person who has a draft they started | Count 0 greyed |
| Area chips | chip group (multi choice) | The company's areas, each with its count from `facets.area`. First five shown (proposed) and a chip "More areas" | Sets `area` (any of the chosen). "More areas" expands the group to every area | Everyone | "No areas set up yet. Your company admin adds them in the company profile." |
| My role chips | chip group (single choice) | Organiser, Sponsor, Participant, Affected, Observer, Decider, Owner, Reporter, Named in a share link; count from `facets.role` | Sets `role`; keeps only intents where the signed-in person holds that role | Everyone | Count 0 greyed |
| Time box status chips | chip group | Home: Not started yet, Running to time, Extended, Past its end. Past: Closed within time, Closed late. Count from `facets.timebox` | Sets `timebox` | Everyone | Count 0 greyed |
| Outcome kind chips | chip group | Start an Initiative, Added to backlog, Started a Problem, Nothing, and why. From `closure.next[].kind`. Count from `facets.outcome`. Shown on Past only | Sets `outcome` | Everyone | Count 0 greyed |
| Rated chips | chip group | "Rated (3 or more ratings)", "Not rated yet". Count from `facets.rated` | Sets `rated` | Everyone | Count 0 greyed |
| Sort select | select | Home: Newest, Ending soonest, Most people, Best rated. Past: Newest closed, Most people, Best rated | Sets `sort`; list reloads | Everyone | Never empty |
| Clear all | button | "Clear all filters" (not shown when none is on) | Clears chips and search; sort stays | Everyone | Hidden |
| Active-filter strip | list of chips | One removable chip per active filter, e.g. "Area: Operations x" | x removes that filter | Everyone | Hidden when no filter is on |
| Count line | text | "14 intents", or "14 of 212 intents you can see" when filtered. Both read `total` (filtered and unfiltered) from the API | None | Everyone | See the empty copy below |
| List refreshed line | text | "List refreshed 7 Oct, 09:14" from `index.built_at`, in the company time zone | None | Everyone | "Not available yet: the list has not been built." |
| Result cards | list | See Screen C | Open the intent (or its summary) | Per Rules | Empty copy below |
| Show more | button | "Show more" | Calls the API with `cursor` and adds cards | Everyone | Hidden on the last page |

### Screen B: Filter sheet (390 only)

Opens from the "Filters" button as a native `<dialog>` that slides up and fills most of the screen height. At 1280 this screen does not exist: the chips are in the page. Layout at 390: title row, scrolling chip groups, a fixed bottom row with Clear and Show.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Sheet title | text | "Filters" and the live count "14 intents" (from `total` of a `limit=0` call) | None | Everyone | Never empty |
| Chip groups | chip groups | The same seven groups as Screen A (Type, State, Area, My role, Time box status, Outcome kind, Rated), one heading each, in that order | Changes a draft selection; the list behind does not move until Show | Everyone | Same as Screen A |
| Show button | button | "Show 14 intents" (the count updates as chips change, from one API call with `limit=0`) | Applies the draft and closes | Everyone | "Show no intents", disabled, when the count is 0 |
| Clear button | button | "Clear all" | Resets the draft selection | Everyone | Disabled when none is on |
| Close | button | x at the top right | Closes and drops the draft selection | Everyone | None |

### Screen C: Result card

One card per intent. Same card at 1280 and 390; at 390 the lines wrap and the match line moves under the purpose.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Type chip | chip | Type name and a one-letter mark from catalogue 02 (on screen "Weekly check-in" for record key `pulse`) | None | Everyone who sees the card | Never empty |
| Title | link | `title`, with matched words marked. When the company switch "titles private to the company" is on, the super admin sees "Title private to the company" | Opens `/centre/intent/<id>` (the screen shows the content for content access, the summary for the others; file 05 owns that split) | As the card | Never empty |
| Purpose line | text | `purpose`, one line, cut at a proposed 140 characters | None | Tier 2 and above (see Rules) | Hidden for the super admin and for the company admin who is not tagged |
| State and stage | chip | State word and current stage name, e.g. "In session, Define strategically" | None | Tier 2 and above see state and stage; tier 1 sees state and stage; super admin sees state only | Never empty |
| Areas | chips | `areas`, first three then "+2" (count from `areas`) | Click adds that area filter | Everyone who sees the card | "No area named" |
| Organiser | text | "Organised by Janet" | None | Tier 2 and above | Hidden below tier 2 |
| People count | text | "6 people" (every person ref in `people`, counted once each) | None | Everyone who sees the card | Never empty |
| Time box line | text | Open: "Ends Fri 17 Oct, 3 working days left" or "Ended 2 working days ago, past its end" or "Extended once" (from `time_box.ends` and the length of `extended_by`). Closed: "Closed 9 Oct, within time". Draft: "Not started yet". Cancelled: "Cancelled 9 Oct". Weekly check-in series: "Not available yet: the series has no single end date" (Open question 10) | None | Everyone who sees the card | Never empty |
| Outcome line | text | Closed only: `closure.what_came_out`, one line | None | Tier 1 and above | Open intents: "No outcome yet" |
| Rating | text | From three ratings: "4.2 from 5 ratings". One or two: "2 ratings so far, the average shows from three". None: "Not rated yet". Average of `ratings[].score`; anonymous ratings count, never who. Not shown for Weekly check-in series | None | Tier 2 and above | "Not rated yet" |
| Match line | text | "Matched in: purpose" or "Matched in: card text" with a proposed 60-character snippet, words marked. Only a field the viewer's tier may search is named | None | Only when `q` is set | Hidden when no search |
| Access line | text | For someone below content access: "You can see that this exists. Ask Janet to add you to open it." | None | Viewers without content access | Hidden for readers |
| Open button | button | "Open" (content access) or "View summary" (below content) | Same as title | Everyone who sees the card | Never empty |

### Empty and failure copy (exact wording)

| Case | Heading | Lines | Button | On click |
|---|---|---|---|---|
| No intents exist in the company | "Nothing has been started yet." | "Pick what you want to do above. North will plan it with you." | None (the type cards are above) | None |
| Home, none open for this viewer, some past | "Nothing is running that you can see." | "Past intents are kept. Open them to see what came out." | "Past intents" | Opens `/centre/intent/past` |
| Past, none closed yet | "Nothing has finished yet." | "An intent appears here once it is closed or cancelled." | "Back to running intents" | Opens `/centre/intent` |
| Search with no match, no filters | "No intent matches ""<text>""." | "Try fewer words, or check the spelling. Card text is searched only in intents you may read." | "Clear search" | Empties the box and reloads |
| Filters with no match | "No intent matches these filters." | "Remove one, or clear them all." | "Clear all filters" | Clears chips, reloads |
| Search and filters, no match | "No intent matches ""<text>"" with these filters." | "Clear the filters to search everything you can see." | "Clear all filters" | Clears chips, keeps the text |
| Index being rebuilt | "The list is being refreshed." | "This takes a few seconds. Try again in a moment." | "Try again" | Repeats the last request |
| Request failed | "The list did not load." | "Nothing was changed. Try again in a moment." | "Try again" | Repeats the last request |
| Not signed in to a company | "The Intent Centre is not open to you." | "Ask your company admin for a seat in this company." | None | None |

The empty copy never says whether a hidden intent exists. A search that matches only sealed or anonymous text gets the "No intent matches" copy.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Aaron opens `/centre/intent` from the centre's menu. The page calls `GET /api/intents?view=home&sort=newest`. The server reads the index (from memory when warm), keeps only rows Aaron may see, sorts, and returns the first page of cards plus the counts for every chip.
2. Aaron types "onboarding" in the search box. After the pause the page calls the API with `q=onboarding`. Cards show the words marked and a match line naming the field.
3. Aaron clicks the chip "Area: Operations". The page adds `area=Operations` to the address and reloads the list. The counts on the other chips change to fit.
4. Aaron changes the sort to "Most people". The list reloads. The sort is kept in the address.
5. Aaron clicks "Show more". The page sends the `cursor` from the last response and adds cards below.
6. On a phone, Aaron taps "Filters", picks chips in the sheet, watches "Show 6 intents" change, taps it, and the list updates.
7. Aaron clicks a card title. If he may read it he lands on the intent at `/centre/intent/<id>`; if not, on its summary with the access line. He has left this feature.
8. Between steps no agent acts. North's only part is earlier: at closure it drafted the outcome line, a named person confirmed it, and Aaron's search can now match it.

## States and transitions (table: state, who moves it, to what, what is written)

The search region holds screen state only. Nothing is written to a company record by searching.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| `loading` | Page load or any change of search, chip or sort | `ready`, `empty`, `refused`, `error` or `rebuilding` | Nothing |
| `ready` | The person changes search, chip, sort or clicks Show more | `loading` | Chips and sort go to the address; search text stays in page memory |
| `empty` | Server returns zero items | `loading` after a change; or the person clicks Clear | Nothing |
| `rebuilding` | Server answers 503 with `index: "rebuilding"` | `loading` after the person clicks Try again, or automatically after a short wait (Open question 11) | Nothing |

Index file states (server side):

| State | Who moves it | To what | What is written |
|---|---|---|---|
| `absent` | First query, or file lost | `building` | Nothing yet |
| `building` | The first request that finds it absent or stale; other requests wait on the file lock, then return 503 "rebuilding" | `ready` | `intents/_index.json` written whole by `write_json_atomic` |
| `ready` | Every intent write calls the upsert | `ready` | The row for that intent replaced; `updated_at` of the file set |
| `stale` | A check finds the folder count or a row `rev` differs from disk | `building` | Whole file rewritten |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Read or write | Fields | Mark |
|---|---|---|---|
| `GET /api/intents` | Read | Query: `q, type, state, area, role, timebox, outcome, rated, sort, view, cursor, limit`. Response: `{items: [card], total, next_cursor or null, facets: {type, state, area, role, timebox, outcome, rated}, index: {built_at, rows}}` | New |
| `intents/_index.json` (in `data/<company>/`, beside the `intents/<id>/` folders) | Read on query; written on every intent write and on rebuild | `{schema: 1, built_at, rebuilt_reason, rows: [row]}` | New |
| Index row | Part of the file | `id, type, title, purpose, state, stage_key, stage_name, areas, created_by, organiser {name}, people {organiser, sponsor, decider, owner, reporter, participants, affected, observers, share_named} (person refs as the intent record holds them), affected_may_read (copy of the organiser's creation switch, field name per file 05), people_count, starts, ends, extended (true when `time_box.extended_by` is not empty), closed_at, cancelled_at, outcome_text (copy of `closure.what_came_out`, empty before closure), next_kinds, rating_n, rating_avg (empty when `rating_n` is below 3), rev (= intent `updated_at`), body_text (see Rules)` | New |
| `intents/<id>/intent.json` | Read on a rebuild and on a single-row repair; never read per query | The whole intent record | New (defined in 00-BRIEF section 3 and file 01) |
| `intents/<id>/events.jsonl`, `intents/<id>/weeks/<week_key>.json` | Not read | Events and week files are not indexed; the series is one row | New (files 16, 39) |
| `sh_platform/jsonfile.py` | Read and write | `read_json_strict`, `write_json_atomic`, `lock_for` | Existing |
| `sh_platform/profile/view.py` | Read | `Viewer`, `norm`, the account-bound name match of `_passes` | Existing |
| Company profile: area list and time zone | Read | Area names for the chips; the viewer's own areas; the company time zone, else UTC | Not found as built (Open question 2) |
| Company switch "titles private to the company" | Read | One boolean per company (ruling 5) | New (file 05 or 48) |
| Run log | Write | One line per query: viewer id, filter names used, result count, milliseconds. Never `q` | Existing (platform run log) |

## Fields this feature adds to the intent record

- `updated_at` (ISO time): set on every write of `intents/<id>/intent.json`. It is the `rev` the index compares. Every other spec's write path sets it through the one intent-save function.
- `closure.what_came_out` is already in the brief; the index copies it into `outcome_text`. `outcome` is an object from the moment the intent opens (ruling 6) and is not read here.

Nothing else is added to the record. Everything else this feature stores lives in the index file.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- North: drafts `closure.what_came_out` at closure (the closure spec owns the draft). A named person confirms it; only then is it searchable. North does not search and is not asked to rank.
- Lens: none.
- Nira: may write a daily Pulse line that links to a pre-filtered list (see Entry points). The filter values come from records (an area name, a sort), never from a guess.
- No text from the index or from a search leaves the company plane. Search does not use the egress gateway.

## Rules (visibility, time box, who may do what)

Visibility tiers. The server computes the tier per row for the signed-in person. A row the person has no tier for is not returned, not counted in `total`, and not counted in any chip. Tiers follow brief section 4 and ruling 4.

| Tier | Who | Fields searched and shown |
|---|---|---|
| 0 Existence | Super admin (read through the kernel on request, no copy in the control plane; ruling 5) | Searched: `title` (not when the company keeps titles private), `areas`. Shown: title (same exception), type, state, areas, people count, dates, time box status |
| 1 Outcome | Company admin who is not tagged to the intent | Tier 0 plus state, stage and `outcome_text` once closed. Never anonymous notes |
| 2 Area | Anyone tagged to one of the intent's areas; anyone named as affected (by area or by name) when "affected people may read" is off | Tier 1 plus `purpose`, organiser name, people, clock |
| 3 Content | Organiser, sponsor, decider, owner, reporter, participants, observers; affected people only when the organiser switched on "affected people may read" at creation; anyone named in `share.who_may_open` | Tier 2 plus card text |

- The highest tier a person qualifies for applies. A person is matched by account id where the intent record binds one, otherwise by display name, as `view.py` does (`_passes`); a name shared by two accounts matches neither.
- Drafts are returned only to the person who started them (`created_by`), to nobody else, not to admins (ruling 14). Cancelled intents are searchable in Past, with their reason in `closure.summary`, at tier 1 and above.
- Sealed and anonymous material is never written to the index. `body_text` holds only cards that are neither sealed nor anonymous. A sealed card is therefore not found even by its author. When a seal is lifted the next write of that intent re-indexes it. Nobody, including the company admin, finds anonymous notes by any route.
- Matching: lower-case, accents folded, punctuation ignored (the `norm` rule of `view.py`). Every word typed must be found in one of the searchable fields (AND). A word matches the start of a word. Words shorter than the minimum are ignored.
- Filters within one group are OR; across groups they are AND.
- Sorts. Newest: `created_at` descending (Past: `closed_at` or `cancelled_at`). Ending soonest: open intents by `time_box.ends` ascending, any extension included; drafts, closed, cancelled and check-in series last. Most people: `people_count` descending. Best rated: `rating_avg` descending, then `rating_n` descending; intents with fewer than three ratings last. Ties: newest first, then id.
- Ratings are read only. They aggregate from three (ruling 8). Ratings are anonymous by default; the index holds a count and an average only, never who gave which (ruling 15). No per-person average exists here. Weekly check-in series and weeks are not rated (ruling 3).
- Counts are exact. No mean or median is computed here other than the rating average, which follows the three-rating rule.
- Time box status is worked out from the row and the company clock. Days count Monday to Friday, using the working-day rule of `modules/m1_intent/contracts/intent_session.yaml`, in the company time zone from the profile, else UTC (ruling 8). Not started yet = state `draft`. Running to time = open, not past `ends`, `extended` false. Extended = open and `extended` true. Past its end = open and now after `ends`. Closed within time = `closed_at` not after `ends`. Closed late = after.
- Outcome kind uses `closure.next[].kind` from the row's `next_kinds`; an intent with several kinds matches each of them. "Nothing, and why" matches kind `nothing`.
- Pagination: `cursor` is opaque: it holds the sort key and id of the last item, so a write between pages cannot repeat or skip an item. `limit=0` returns counts only (for the phone sheet). Default and maximum page size: Open question 11.
- The response never includes `body_text`. A snippet is cut on the server and only from a field the viewer's tier may read.
- `q` is not written to the run log, an error message or the page address.
- Any route without a viewer, or a viewer with no seat in the company, gets 403. The index is per company plane (`data/<company>/intents/_index.json`); a request cannot name another company.

Index maintenance and rebuild.

- One function `upsert(plane, intent)` replaces a row. Every code path that writes `intents/<id>/intent.json` calls it straight after the write, inside `lock_for(index path)`, and writes the index with `write_json_atomic`. Events: create, open, stage change, people or area change, share change, "affected people may read" change, extend, close, cancel, rating added, seal lifted, card added or edited.
- A failed upsert does not fail the intent write. It logs a plain-words error and marks the index stale, so the next query rebuilds.
- Rebuild reads every `intents/*/intent.json` (never `_index.json`, `events.jsonl` or week files) with `read_json_strict`, builds rows, writes the whole file. A file that will not parse is skipped, named in the run log, and left alone; it is not in the list until fixed.
- A rebuild runs when: the file is absent; the file will not parse or `schema` is not the current number; on the first query after the server starts, the count of `intents/*/intent.json` files differs from `rows`; or a single-row check finds a `rev` that differs from the file (the row is repaired alone, not a full rebuild).
- Opening an intent compares its `updated_at` to the row's `rev` and repairs the row if they differ.
- Nothing is ever deleted from `intents/`. A row is never removed, only replaced.
- The server keeps the parsed index in memory and re-reads it when the file's modified time changes.
- The cap on `body_text` and the performance targets are proposals, listed in Open questions 7, 8 and 11. If the whole-file rewrite on every write proves too slow, `body_text` moves to a second file or the index to a table; the API does not change.

## Counters and measures of this feature (numbers only, each traced to a record)

- Rows in the index: `rows` in `intents/_index.json`. Cross-checked against the count of `intents/*/intent.json`; a difference is shown to the company admin as "The list needs a refresh".
- Intents you can see: `total` of the unfiltered API response for the signed-in person.
- Count on each chip: `facets` in the response, computed over the rows the person may see with every other active filter applied.
- Index built at: `built_at`, shown as "List refreshed 7 Oct, 09:14". "Not available yet" when the file is absent.
- Searches that found nothing: "Not available yet". The run log does not hold search text, and counting zero results needs a new log field; not added.
- Query time: milliseconds on the run log line of each query.
- Card figures: people count from `people`; working days left from `time_box.ends`; rating from `ratings[].score` (shown from three).

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: read `ui/src/pages/RegisterPage.tsx`, `ui/src/pages/MemoryPage.tsx`, `sh_platform/jsonfile.py`, `sh_platform/profile/view.py`; grep of `ui/src/design` for sheet and drawer components (no hit); grep of `sh_platform/profile` for time zone (no hit) and for area lists (only `governance.restricted_areas`). Graft was not run; the files were read directly and every path below was checked to exist on 7 Oct 2026.

| Existing | Found | Decision |
|---|---|---|
| `ui/src/pages/RegisterPage.tsx` lines 14-17 (`Filter` type, `FILTERS`), 41-42 (`filter`, `q` state), 54-56 (browser filter and substring search), 65-68 (chip row, `type="search"` input), 70 (empty state "No measure matches") | A chip row plus search box with a clear empty state | Reshaped. Chip row, search input and empty-state pattern are copied. The filtering in the browser is not: it suits tens of rows, not hundreds with per-viewer rules, so it moves to the server. |
| `ui/src/pages/MemoryPage.tsx` lines 16-18 (`Tab`: `ds-chip`, `ds-chip--active`, `aria-selected`) | Chip markup and active style | Copied for the look. Chips here are filters, so `aria-pressed` replaces `role="tab"`. |
| `ui/src/pages/RegisterPage.tsx` `DataTable` use | A table | Not used: intents are cards, and a card carries a match line and an access line. |
| `ui/src/design/parts.tsx` (`PageFrame` line 30, `Chip` line 125, `Button` line 132, `EmptyState` line 189) | Shared parts used by both pages above | Reused as they are. |
| Filter sheet | No sheet or drawer component in `ui/src/design` | New and small: a native `<dialog>` styled as a bottom sheet. No library. |
| `sh_platform/jsonfile.py` lines 19 (`lock_for`), 25 (`read_json_strict`), 41 (`write_json_atomic`) | The one way to read and write JSON in a company plane | Reused as they are for `_index.json` and for rebuild reads. The lock is per process, which holds for one server process; a second writer process needs a file lock (note in the file header). |
| `sh_platform/profile/view.py` lines 27-31 (`Viewer`), 34-35 (`norm`), 60-71 (`_passes`) | Per-viewer filtering by account id or name, with the shared-name rule | Reused for the tier check. `_passes` is private and its company-admin rule is for lists, so the intent code wraps the account and name match in one public function rather than editing `view.py`. |
| `modules/m1_intent/contracts/intent_session.yaml` line 26 (working-day rule) | Monday to Friday, no holidays, stated in UTC | Reused for "working days left" and time box status; the zone is the company's from the profile, else UTC (ruling 8). |

Genuinely new: the list endpoint, the index file and its upsert and rebuild, the tier rules for search, the result card, the phone filter sheet.

## Not in this feature

- The Intent home page frame, the five type cards, the Past page frame, and the intent and summary pages themselves.
- Saved searches, recent searches, "More like this", search suggestions, typo tolerance, ranking by relevance.
- Searching inside the Moment of truth, Build, or the walls, charters and baselines that stay in `modules/m1_intent`, `m2_baseline`, `m3_connect`. Only the intent record and its cards are searched.
- Exporting the list, and bulk actions on results.
- Rating an intent (file 10 owns it); here ratings are only read.
- Any model call, and any search across companies.
- The super admin page `/centre/control/intents` (file 48).

## Open questions

1. Summary for existence-only viewers: ruling 1 lists no summary route, so this file opens `/centre/intent/<id>` for everyone and leaves the content or summary split to file 05. Confirm.
2. Where do the company area list, the viewer's own areas and the company time zone come from? Only `governance.restricted_areas` exists in the profile today; no time zone was found. If people are not tagged, tier 2 is empty.
3. Company admin: the brief gives existence and outcome. This file adds state and stage at tier 1 and no purpose or organiser unless tagged. Confirm.
4. Does the organiser search her own anonymous cards? This file says no one does, to keep the rule simple.
5. A "Best match" sort while a search is on is not among the four sorts asked for. Add it, or keep Newest?
6. The name of the "affected people may read" field in the intent record (file 05 owns it); the index copies it as `affected_may_read`.
7. The `body_text` cap (proposed 4000 characters of the newest non-sealed, non-anonymous cards). Is it acceptable, or should every card be searchable?
8. Performance targets (proposed, to be checked by a timing test on 2000 synthetic intents): warm query under 300 ms at the server and 700 ms to show cards; first query after start under 1.5 s; rebuild of 2000 files under 20 s; upsert adds under 150 ms; index about 10 MB at most. Who confirms them?
9. May the company admin see a "Rebuild the list" button, or is the automatic rebuild enough?
10. A Weekly check-in series is one card (ruling 3). What time box line does a series show: the open week's end, which would need the week file in the index, or nothing? This file shows "Not available yet" until decided.
11. Interface constants proposed here, none given by the brief: search pause 250 ms and minimum 2 characters; page size 20 by default, 50 at most; five areas shown before "More areas"; purpose cut at 140 characters; snippet of 60 characters; automatic retry after 3 seconds, at most 3 times; wait on the index lock of 2 seconds before answering "rebuilding". Confirm or change each.
12. The record path in brief section 3 reads `intents/<id>.json`; ruling 12 moves it to `intents/<id>/intent.json`. This file follows the ruling; the brief text should be corrected.
