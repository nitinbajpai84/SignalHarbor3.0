# 19. Centre counters and measures

Part of: Intent Centre v2. Depends on: 01 (intent record and lifecycle), 02 (types catalogue and outcome shapes), 04 (home), 06 (people and roles). Feeds: 04 (the four home counters), the company admin review, the closure draft (rating prompt).

## Purpose (three sentences)

The Intent Centre reports numbers about itself so the company can tell whether it is worth the time. Each measure is defined once here, computed from named fields of the intent record, and returned by one route with the ids it came from. A measure whose record does not exist yet says "Not available yet" and names what is missing; nothing is estimated and nothing is shown as zero when it means "not yet".

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Any signed-in person | Glances at the four home counters on their way to start or find an intent | Opens `/centre/intent` |
| Company admin | Weekly review: is the centre earning its time, which type is stuck, which type is liked | Opens the "How the centre is doing" panel on the home page |
| Organiser | Sees the rating prompt for their own closed intent (one line, feeds the rating measure) | Intent moves to `closed` |
| Super admin | Checks that a company is using the centre at all | Opens the company row in the control panel |
| North (agent) | Computes nothing and writes nothing. It asks the one-month question (M15) and keeps the clock that M02 to M04 read | One month after `closure.closed_at` |

## Entry points (every route, link, Pulse line, button that leads here)

- Home page `/centre/intent`: the four counter cards (04, Counters) show M01, M02, M13 and M08 in short form. Each has "Show the intents".
- Home page, below the counters: the panel "How the centre is doing" (company admin only), button "Show all measures" to expand it.
- Control panel, super admin: `/centre/control/intents`, per company, link "Centre use" (Screen 3). Counts only.
- Pulse line (the daily page), company admin only: "Measures for last month are ready" is Nira's line on the first working day of a month. It links to the panel.
- `GET /api/intents/measures` (route, section Screens).

## Screens, element by element

### Screen 1: the four counters (part of the home page, owned by 04)

Not rebuilt here. This file defines the numbers behind them. Route: `/centre/intent`. At 1280 a row of four `StatCard`s; at 390 a 2 by 2 grid. Cards: Intents opened this month (M01, all types summed), Closed inside the time box (M02), Average rating (M13), Build-ready charters (M08). Each card shows the number, a sub-label, and "Show the intents".

### Screen 2: panel "How the centre is doing"

Route: `/centre/intent`, panel below the counters, company admin only. Data from `GET /api/intents/measures?window=6m`.

**Layout at 1280.** One full-width card with a header row (title, window select, "Download as CSV" button) and four sections in two columns: Starting and finishing (M01 to M04), Effort (M05, M06), Quality of definitions and outcomes (M07, M08, M13, M15), What came out (M09 to M12, M14). Each measure is one row: name, number in words and digits, a six-month strip of counts (`StatCard` plus a strip of plain counts; no Sparkbar exists in `ui/src`), a "?" that opens the definition, and "Show the intents".

**Layout at 390.** Header collapses to title and one "Window" select. Sections become four accordions, closed by default except the first. Strips become the latest month and the month before as two numbers. "Download as CSV" moves into a menu.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Window select | field | "Last 6 months" (default), "Last 12 months", "This quarter" | Re-fetches the route with `window` | Company admin | Never empty |
| Measure row | list | Name, value, sub-label, strip | Opens the definition drawer | Company admin | A row with no record shows "Not available yet" and the missing record in grey (see the table below) |
| "?" definition | button | The exact definition from this file, the fields read, the count it was computed from | Opens a drawer | Company admin | Never empty |
| Show the intents | button | n, the intents behind the number | Sets the home filters to exactly those ids and scrolls to Past intents or the lanes | Company admin. For others the same button on the four counters, limited to intents they may see | Hidden when n is 0 |
| Download as CSV | button | One row per measure per month: measure id, group, month, numerator, denominator, value | Downloads the numbers as shown. No titles, names, notes | Company admin | Disabled with "Nothing to download yet" when no measure has a value |
| Fewer than five | chip | "Fewer than five" in place of a mean, median or rate whose group is under five records | None | Company admin | Not shown otherwise |
| Footnote | text | "Numbers come from the intent records of this company. Ratings are counted including anonymous ones; notes are never shown here." | None | Company admin | Never empty |
| Empty panel | panel | "Nothing to measure yet. Measures appear after the first intent is opened." | None | Company admin | Shown only when the company has no intent beyond `draft` |

### Screen 3: "Centre use" (super admin)

Route: `/centre/control/intents`, one row per company, link "Centre use". Layout at 1280: the company list on the left, the table for the chosen company on the right. At 390: the list becomes a select above the table, and the table scrolls inside its own box. The server reads the counts from the company's intent records through the kernel on request (ruling 5, request A-074); the control plane stores nothing.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Company row | list | Company name, "Centre use" link | Loads that company's table | Super admin | "No company yet." |
| Month table | list | Month (company time zone, else UTC), intents opened per type (M01), closed, cancelled; exact counts | None | Super admin | "This company has not opened an intent." |
| Window select | field | "Last 6 months" (default), "Last 12 months" | Re-fetches with `window` | Super admin | Never empty |

Counts only. No title, person, rating, minutes or content. The other existence fields (areas, dates, time box status) and the company switch "titles private to the company" (default off) belong to the existence list in file 14; this table shows none of them. "Fewer than five" never applies to counts of intents.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. A person opens `/centre/intent`. The home page calls `GET /api/centre/home`, which takes M01, M02, M13 and M08 from the same code as this route.
2. The company admin scrolls to "How the centre is doing". The panel calls `GET /api/intents/measures`.
3. The admin opens "?" on "Closed inside the time box" to read the exact definition, then presses "Show the intents" to see the late ones in Past intents.
4. The admin changes the window to "Last 12 months". The route is called again.
5. The admin downloads the CSV for the monthly review.
6. Between visits: when an organiser closes an intent, North adds a one-line rating prompt to the closure screen (10 owns the prompt; this file only reads `ratings[]`). One month after close North asks the organiser the M15 question and the organiser answers (10 owns the question and the write). The person leaves by closing the panel or going back to `/centre/intent`.

## States and transitions (table: state, who moves it, to what, what is written)

The measures hold no state of their own. They are computed on every request from `intents/<id>/intent.json` and the week files; nothing is cached or written. This file writes no field. The rows below are written by file 10 and are listed only so the reader knows which state a measure counts.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| Closed, no rating | A named person rates, once each | Closed, rated | `ratings[]` row (10) |
| Closed, one month passed, not asked | North asks | Asked | `outcome_used.asked_at` (10) |
| Asked | Organiser answers | Answered | `outcome_used.answer`, `answered_at` (10) |
| Asked, not answered | North drops the line (10 sets the days) | Unanswered | `outcome_used.dropped_at`; M15 counts it as "not answered" |

## Records read and written (file or route, fields; mark Existing or New)

| Record or route | Fields used | Mark |
|---|---|---|
| `GET /api/intents/measures` | Query `window` (`3m`, `6m`, `12m`, `quarter`, default `6m`) and optional `type`. Returns per measure: `id`, `name`, `value`, `numerator`, `denominator`, `by_type`, `by_month`, `ids`, `missing` | New |
| `intents/<id>/intent.json` via `sh_platform/jsonfile.py`, filtered by `sh_platform/profile/view.py` and the visibility function from 01 | `type`, `state`, `created_at`, `stages[].key`, `stages[].opened_at`, `stages[].closed_at`, `time_box.ends`, `time_box.extended_by`, `closure.closed_at`, `closure.next[]`, `ratings[].score`, `outcome.*`, `links.from`, `links.to`, `links.build`, `outcome_used` | New (the brief and files 01, 10 define the record) |
| `modules/m1_intent/store/sessions.py` session `inputs` (`actions`, `free_text`, `cards_confirmed`, `cards_new`, `cards_sealed`) | Counters per wall session, read by reference from an Initiative's `refs.wall_session_id`; numbers only | Existing |
| `modules/m1_intent/store/stages` `started.private_rooms` and `outcomes/<id>.json` `signed_at` | The recorded span of an Initiative's wall (M05, M06) | Existing |
| `GET /api/company/outcomes` (`sh_platform/outcomes.py`, LI-OUTCOMES) | `definitions_unchanged`, `cards_first_five`, `modules[].minutes` for the Initiative | Existing; kept as is and read by M05, M06, M07 |
| `intents/<id>/weeks/<week_key>.json` (file 38) | `items[]` (`kind`, `fate`, `fate_ref`), `closed_at` | New |
| `GET /api/centre/home` | The four home counters, taken from the same functions as this route | New (owned by 04) |
| Writes | None by the route. `outcome_used` and `ratings[]` are written by file 10's routes | None |

## Fields this feature adds to the intent record

None. The one-month question is stored in `outcome_used` (file 10: `ask_at`, `asked_at`, `answer`, `note`, `answered_by`, `answered_at`, `dropped_at`). This file reads it under that one name and adds no second field. It reads `ratings[]` (file 10) and renames none of the brief's section 3 fields.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** does not compute the measures. It asks the one-month question as file 10 defines it (Yes, Partly, No and a note) and writes `outcome_used`. The organiser answers; the deferral and drop days are file 10's.
- **Lens** is not involved.
- **Nira** writes the monthly Pulse line for the company admin (see Entry points). It states the line only when at least one measure has a value, and it quotes no figure itself; the line links to the panel.
- Agents never rate, answer the use question, or change a measure.

## Rules (visibility, time box, who may do what)

**Who sees what.**

| Viewer | Four home counters | Panel and route (full set) | Notes |
|---|---|---|---|
| Any person | Yes, over the intents they may see at the tiers of 01 (existence or content) | No. The route returns M01, M02, M08, M13 only, with `scope: "visible"` | A counter never counts a hidden intent, so two people can see different numbers; the sub-label says "Intents you can see" |
| Company admin | Yes, all intents | Yes, all fifteen measures | Existence plus outcome (ruling 4). Never anonymous notes, never rating notes, never who rated what |
| Super admin | No | No. Only the table "Centre use" at `/centre/control/intents`: M01 (per type per month), closed count and cancelled count, per company | Existence only (ruling 5), read through the kernel on request; no copy in the control plane. The route refuses every other measure with 403 "Super admin sees counts only" |

**Rules for every measure.**

- Counts are of intents (records) and are shown exactly. A mean, median or any per-person figure (M03, M05, M06) whose group is under five records shows "Fewer than five". Ratings (M13) aggregate from three ratings; below three the row shows "Fewer than three ratings". No per-person average exists anywhere (ruling 15).
- Time zone: the company's from the profile, else UTC, in every measure. "Month" and "quarter" are calendar periods in that zone.
- A Weekly check-in series is not rated and has no close, so it is excluded from M02 to M04 and M13; its weeks feed M10 only. Weeks are not rated.
- A cancelled intent is excluded from every measure except M01 and the cancelled count. A `draft` is excluded everywhere.
- An intent counts once. In a measure by type it counts under its own `type`.
- A measure with no qualifying record returns `value: null` and `missing: "<what is missing>"`. Zero is returned only when at least one qualifying intent exists and none met the condition.
- A number is never shown without its denominator where it is a share: "6 of 8", not "75%". No percentages anywhere.
- The route computes on read under the shared lock reads of `sh_platform/jsonfile.py`; it never writes.
- No threshold, target or traffic light. The panel reports, it does not judge (open question 1).

**The measures.** Month of an intent = month of the date named in "When counted".

| # | Measure | Exact definition | Record and fields | When counted | Not available when (and what is named) |
|---|---|---|---|---|---|
| M01 | Intents opened per type per month | Count of intents with `state` not `draft` and `stages[0].opened_at` in the month, grouped by `type` | `type`, `state`, `stages[0].opened_at` | Month of `stages[0].opened_at` | No intent has left `draft`: "Not available yet. No intent has been opened." |
| M02 | Closed inside the time box | Of intents with `state = closed`, the number with `closure.closed_at` on or before the final `time_box.ends` (the end after every extension), shown "n of m" per type | `closure.closed_at`, `time_box.ends`, `time_box.extended_by` | Month of `closure.closed_at` | None closed: "Not available yet. Nothing has closed." |
| M03 | Days from open to close by type | Median working days (Monday to Friday, no holidays, as 01) from `stages[0].opened_at` to `closure.closed_at`, per type, with the count of intents; the mean is not shown | `stages[0].opened_at`, `closure.closed_at` | Month of `closure.closed_at` | Fewer than five closed in the type: "Fewer than five". None: "Not available yet. Nothing has closed." |
| M04 | Extensions per intent | Per type: the number of intents with at least one extension, and the total extensions, over closed intents of that type. Shown "3 of 8 extended, 4 extensions" | `time_box.extended_by` (length), `state` | Month of `closure.closed_at` | None closed: as M02 |
| M05 | People minutes per intent | For an Initiative with a wall: the span in minutes from `started.private_rooms` to the outcome's `signed_at` (the recorded span, as `modules[].minutes` in LI-OUTCOMES), and beside it the session counters `actions` and `free_text`. Shown as "n minutes, a actions, f free-text entries". These are elapsed minutes of the work and counters of what people did; they are not a timesheet and no person is named | m1 `inputs.actions`, `inputs.free_text`, `started.private_rooms`, `signed_at`, reached through `refs.wall_session_id` | Month of `signed_at` | No Initiative has a signed outcome: "Not available yet. No wall has been signed." Every other type: "Not available yet. This type records no minutes." |
| M06 | Cards per person in the first five minutes (v1) | Initiatives with a wall only. Cards written by named (not anonymous) authors within five minutes of `started.private_rooms`, divided by the number of distinct named authors, to one decimal. This is `cards_first_five` of LI-OUTCOMES unchanged | m1 cards `lane.at`, `author`, `anonymous` (through `profile/view.py`) | The wall's start | No named card yet: "Not available yet. No card has been written." Marked "v1, Initiatives only" |
| M07 | Definitions confirmed unchanged | Of the technical parts a data owner confirmed in the newest baseline, the number left exactly as Lens drafted them: "k of n". This is `definitions_unchanged` of LI-OUTCOMES unchanged | m2 `kpis.json` `technical_confirmed`, `technical.<part>.from` | Current, not monthly | No definition confirmed: "Not available yet. No data owner has confirmed a definition." Sealed measures are never counted (LI-OUTCOMES rule) |
| M08 | Build-ready charters per quarter | Initiatives whose `build_ready` stage closed with `outcome.build_ready = true`, in the quarter. Beside it, how many of them have `links.build` set (handed to Build) and how many do not (waiting) | `stages[key=build_ready].closed_at`, `outcome.build_ready`, `links.build` | Quarter of the `build_ready` stage `closed_at` | No Initiative reached the check: "Not available yet. No Initiative has reached the check." |
| M09 | Brainstorms that became initiatives | Of closed Brainstorms, the number whose `closure.next[]` has a row `kind = initiative` whose `ref` resolves to an intent of type `initiative` with `links.from` equal to the brainstorm id: "n of m" | `closure.next[]`, `links.to`, the target's `type` and `links.from` | Month of the brainstorm's `closure.closed_at` | No Brainstorm closed: "Not available yet. No Brainstorm has closed." A row with an `initiative` kind and an unresolved `ref` is counted in m but not in n |
| M10 | Weekly check-in items that became problems or backlog | Over closed week files: items with `fate = problem` and a `fate_ref` that resolves to a Problem intent, `fate = backlog`, `fate = handled`, `fate = nothing`, out of all items "p problems, b backlog, h handled, z nothing, of t items". A `problem` fate with no resolving ref is counted as `nothing` and listed in `missing` | week file `items[].fate`, `fate_ref`, `reason`, `closed_at` | Month of the week file's `closed_at` | No week closed: "Not available yet. No weekly check-in week has closed." Counts only; no item text |
| M11 | Problems closed with a root cause | Of closed Problems, the number with `outcome.root_cause` present (not `unknown: true`) and `outcome.fix.by` named: "n of m". A Problem closed as "no fix, accepted" counts in m, and in n when it names a root cause | `outcome.root_cause`, `outcome.fix.by`, `state` | Month of `closure.closed_at` | None closed: "Not available yet. No Problem has closed." |
| M12 | Decisions recorded | Closed Decisions with `outcome.chosen`, `outcome.decided_by` and `outcome.why` all present: "n of m". A Decision closed with `outcome.no_decision_reason` counts in m only | `outcome.chosen`, `decided_by`, `why`, `no_decision_reason` | Month of `closure.closed_at` | None closed: "Not available yet. No Decision has closed." |
| M13 | Average rating by type | Per type: mean of `ratings[].score` over intents closed in the period, to one decimal, with the count of ratings: "4.2 from 11 ratings". Anonymous scores included; notes never | `ratings[].score` | Month of `closure.closed_at` | Under three ratings in the type: "Fewer than three ratings". None: "Not available yet. No ratings have been given." The mean is never shown without its count |
| M14 | Intents that led to another intent | Count of closed intents with at least one `closure.next[]` row `kind` of `initiative` or `problem` with a resolving `ref`, by type. Supports M09 and M10; shown in the strip, no separate card | `closure.next[]`, `links.to` | Month of `closure.closed_at` | None closed: as M02 |
| M15 | Outcomes used after one month | Of closed intents with `outcome_used.asked_at` set, the number with `outcome_used.answer` `yes`, `partly`, `no`, and the number with `answer` null: "y used, p partly, n not used, u not answered, of m" | `outcome_used.answer`, `asked_at`, `answered_at`, `closure.closed_at` | Month of `closure.closed_at` | No closed intent has `outcome_used.asked_at`: "Not available yet. Nobody has been asked whether the outcome is used." |

Everything else a person might want (cost saved, hours saved, return on effort, money, cross-company comparison, trend against a target, who is slowest) says "Not available yet. The centre does not record this." and is not computed.

**Response shape (for the builder).** `{company, window, generated_at, scope: "all"|"visible"|"counts", measures: [{id, name, value, numerator, denominator, by_type: {type: {...}}, by_month: [{month, ...}], ids: [intent id], missing: text|null, small_group: bool}]}`. `ids` is returned only for the viewer's tier and only for the four home counters when `scope` is `visible`. The CSV is built in the browser from this JSON.

## Counters and measures of this feature (numbers only, each traced to a record)

Meta-measures of this panel itself, counted from the events log (`intents/<id>/events.jsonl`, file 16) only if it records panel opens; otherwise "Not available yet. Panel use is not recorded."

| Measure | Traced to |
|---|---|
| Times the panel was opened per month | None today. Not available yet; no panel-use record exists |
| Measures with a value / measures in the set | Count of `measures[].value` not null over fifteen, taken from the route response |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

| What | Found | Verdict |
|---|---|---|
| m1_intent lean counters: `NO_INPUTS` and `SessionStore.count` | `modules/m1_intent/store/sessions.py` lines 26 and 128-140; callers in `api/deps.py` (lines 43-56) and `store/notes.py` (lines 153-177) | Used as is for M05. Counters stay numbers only; no new counter added |
| LI-OUTCOMES | `sh_platform/outcomes.py`: `_m1` (lines 72-95), `_m2` (96-125), `_m3` (126-147), `build` (148-183), `outcomes` route (185-187) | M05, M06, M07 are read from it, unchanged. Its helpers `_load`, `_files`, `_time`, `_days` are reshaped into the new route's module: copy the four small functions rather than import across, since `outcomes.py` reads module folders by path and the new route reads `intents/*.json`. The route `GET /api/company/outcomes` stays for the Initiative's Define stage |
| INTENT-CENTRE-SPEC.md section 9 (graft) | Lines 127-141: the targets table and the "Measures of the centre itself (LI-OUTCOMES)" line | Reshaped. Its five measures become M07, M06, M05, M03 (Initiative only) and the match rate, which stays at the Moment of truth in Build and is not in this file. The "about 20 decisions" and "one card in the first five minutes" targets are not carried over as thresholds (open question 1) |
| Home counters | `docs/specs/intent-centre/04-intent-centre-home.md` lines 179-192: four counters | Kept. This file defines M01, M02, M13 and M08 as the single source; 04 must call the same functions |
| Per-viewer filter | `sh_platform/profile/view.py` (`Viewer`, `norm`, `allows`) and the visibility function in 01 | Used. The route counts only what the filter lets the viewer see, except for company admin and super admin tiers |
| JSON reading | `sh_platform/jsonfile.py` | Used |
| `StatGrid`, `StatCard` (`ui/src/design/parts.tsx` lines 99 and 104; used in `ui/src/pages/CentrePage.tsx`) | Used by the home page today | Reused for the four counters; the panel rows reuse `StatCard` and a plain count strip. `Sparkbar` was searched in `ui/src` and does not exist, so it is not used |
| Ratings and outcome used (file 10) | `docs/specs/intent-centre/10-ratings-and-session-value.md` lines 118-160, and its `GET /api/company/ratings` | Read, not rebuilt; this file uses `outcome_used` exactly as 10 names it |
| Search run | "outcomes", "counter", "inputs", "StatCard" across `sh_platform`, `modules/m1_intent`, `ui/src` | Nothing else computes centre measures. No rating, extension or per-type store exists in code, so those are new and read only the intent record |

New: the route `GET /api/intents/measures`, the panel, M01 to M04 and M08 to M15 computations. Nothing of M05 to M07 is rebuilt.

## Not in this feature

- Targets, thresholds, traffic lights, scores for people or areas, league tables.
- Per-person minutes and any timesheet. M05 is elapsed minutes and counters only.
- Money, hours saved, return on effort, adoption of Build outputs.
- Cross-company comparison or a super admin view of content, ratings or minutes.
- The rating screen itself (owned by 01 and 06) and the closure screen.
- Match rate at the Moment of truth (Build owns it).
- Exports other than the CSV of the numbers on screen.

## Open questions

1. **Small groups.** Ruling 8 sets "Fewer than five" for means, medians and per-person figures and "from three" for ratings. This file shows intent counts exactly. For a company that opens under five intents a quarter, M03 is mostly "Fewer than five". Confirm.
2. **Home route names.** `GET /api/centre/home` (04) is outside `/api/intents/...`. Should it move to `/api/intents/home`? Needs a decision from 04's owner.
3. **People minutes for other types.** Only the Initiative wall records a span. Brainstorm has one live session whose length no spec stores. Add `stages[].active_minutes` for Brainstorm, or leave M05 as Initiative only?
4. **Which types are asked "was it used".** A Decision may have no use to ask about, and a check-in series has no close. File 10 does not say. Which types are asked?
5. **Ratings for Decision and Problem.** A Decision has a decider and one adviser, so a rating can nearly identify a person even at three. Show them only over the whole window?
6. **Home counters for people who see less.** Counts follow what each person may see, so numbers differ between viewers. Acceptable, or company-wide M01 only?
7. **Overlap with file 10.** File 10 defines `GET /api/company/ratings` (by type, by area, outcome-used counts). M13 and M15 duplicate it. Keep one route; which?
8. **Decision dissent.** The earlier draft counted dissent entries. File 43 stores no such field, so it is dropped. Add one, or leave it out?
9. **Targets.** The v1 spec had targets (one card in five minutes, about 20 decisions). No rule justifies one, so the panel reports without judging. Does Nitin want targets, set by whom?
