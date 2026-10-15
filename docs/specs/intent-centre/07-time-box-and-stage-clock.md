# 07. Time box and stage clock

Part of: Intent Centre v2. Depends on: 02 (stage lists and default days per type), 03 and 22 (the start flow that creates the time box), 05 (areas and visibility), 08 (North's nudges and the closure draft), 09 (closure and sign-off), 13 (Pulse lines). Feeds: 04 (clock chip on the home lists), 13 (overdue panel and counters), 19 (centre counters).

## Purpose (three sentences)

Every intent has a time box and every stage has a clock, so nothing drifts from 10 days to 20 unnoticed. North keeps the clock, says early when an intent will not make it, and drafts three options (extend with a reason, close with what we have, cancel) for a named person to pick. Every extension is kept in the record with who and why, and the organiser's Pulse lists what is overdue.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | Opens an intent, sees the clock daily, picks when North's card appears and at the end | Stage bar and clock on every intent screen; North's line in "what is waiting for you" |
| Sponsor (Daniel) | Approves a later extension; sees the clock on intents he sponsors | Extension request waiting in his list |
| Participant, observer (Aaron, Harvey) | Sees how long the intent has left; cannot change it | Clock chip in the intent head and on the home lists |
| Affected person, area member (Katie) | Sees the clock chip and the stage; cannot change it | Clock chip on the intent card (file 05 rules) |
| Company admin | Sees overdue intents across areas, never content | Overdue panel on the Pulse (admin view) |
| Super admin | Sees time box status as part of existence, never reasons | Control view `/centre/control/intents` (file 48) |
| North (agent) | Keeps the clock, drafts nudges and the three options | A threshold is crossed, a stage ends, the box ends |

## Entry points (every route, link, Pulse line, button that leads here)

- The stage bar and clock sit on top of the intent screen `/centre/intent/<id>` and on every view under it (`wall`, `define`, `charter`, `build-ready`, `session`, `week`, `review`, `close`, `share`, `events`, `people`, `projector`).
- The clock chip appears on every card of the home lists at `/centre/intent` and on `/centre/intent/past` (final state only).
- "Extend" button on the stage bar and in North's time card.
- "What is waiting for you" lines (Nira, file 13): "Janet, the Finance data initiative is close to the end of its time."
- Pulse page, panel "Overdue intents", organiser and company admin views (file 13 owns the page).
- `/centre/intent/<id>/close`, opened from North's "Close with what we have" option (file 09).
- Cancel dialog, opened from North's "Cancel this intent" option (file 09).

## Screens, element by element

This feature adds no page of its own. It adds three components (stage bar with clock, extend dialog, North's time card) and one panel on the Pulse page.

Time zone, everywhere in this file: the company's time zone from the company profile, else UTC. Dates and times on screen are shown in that zone. Counts are exact.

### Screen A: stage bar with clock (top of every intent screen)

Route: `/centre/intent/<id>` and every `/centre/intent/<id>/<view>`. Component: `StageBar` reused from `ui/src/modules/m1_intent/wall/StageBar.tsx`, reshaped to take the stage list as a prop (see Reuse check).

Layout at 1280: one card across the content width. Left: the stage list as a row of steps (for an Initiative: Think unfiltered, Define strategically, Build-ready; for the other types, the stage names from file 02). Middle: the clock for the current stage. Right: the clock for the whole time box, then the "Extend" button. Below, one line: "Closes Fri 17:00" (reuse `closesWhen`).
Layout at 390: the stage list collapses to "Step 2 of 3: Define strategically" with a thin progress line; the two clocks stack; "Extend" moves under them full width.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Stage steps | list | Each stage in order; done stages marked, current stage lit, later stages plain. Each shows its due date on hover or focus ("due Wed 8 Oct") | Click does nothing for done or later stages; the current step opens that stage's view | Everyone who can see the intent | A draft intent shows all steps plain and "Starts when opened" |
| Stage clock | chip | Time left in the current stage ("3 days left", "6 hours left", "Overdue by 1 day"), from the clock route | None. Tooltip: "Stage due Wed 8 Oct 17:00. Working days only." | Everyone who can see the intent | "No clock yet" on a draft; "Not started" on a later stage |
| Time box clock | chip | Same wording for the whole intent, and "Day 4 of 10" | Same tooltip with the box end and the number of extensions | Same | Same as above |
| Colour | style on both chips | Neutral, amber, red and red solid with the word "Overdue" (cut-offs under Open questions 1) | None. Colour is never the only signal: the chip text carries the state | Same | Neutral |
| Extensions note | line | "Extended once: Janet, 6 Oct, waiting for the glossary from Finance" (latest only) | "See all" opens the extension list in a side panel (read-only) | Organiser, sponsor, participants, observers; affected people only when "affected people may read" is on (file 05); area members see only "Extended once" without the reason | Hidden when there are none |
| Next-step button | button | The v1 wording ("Close the wall", "Close the rooms and bring everyone to the wall") or the next stage name | Behind "Are you sure?" as v1 does | Organiser | Hidden when the stage has no next step |
| Extend | button | "Extend" | Opens Screen B | Organiser and sponsor; hidden once the intent is closed or cancelled | Disabled with the note "Nothing to extend. The intent is closed." |

### Screen B: extend dialog

Route: modal over Screen A (no route of its own). Layout at 1280: centred dialog 480 wide. At 390: full-screen sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Current end | text | "Now ends Fri 17 Oct, 17:00" | None | Organiser, sponsor | Never empty |
| Extra working days | field (choice) | A short list of day counts (the list is under Open questions 2) | Updates the new-end line | Organiser, sponsor | Nothing chosen; "Extend" disabled |
| New end | text | The end date after the chosen working days | None | Organiser, sponsor | "Choose how many days" |
| Reason | field (text, required) | Placeholder "Why more time is needed" (length limits under Open questions 2) | Typing enables "Extend" | Organiser, sponsor | Empty: "Extend" disabled; message "A reason is needed." |
| Which clock | choice | "This stage only" or "The whole intent" (default: whole intent, which also moves the stage) | Changes what is written | Organiser, sponsor | Hidden for single-stage types |
| Approval line | text | Who must approve this extension, from the approval rule (Open questions 3), for example "This extension needs Daniel (sponsor) to approve." | None | Organiser | Hidden when no approval is needed |
| Extend | button | "Extend", or "Ask Daniel to approve" when approval is needed and the viewer is the organiser | No approval needed, or the viewer is the approver: writes at once. Otherwise writes a pending request and puts a line in the approver's list | Organiser, sponsor | Disabled until choice and reason are valid |
| Not now | button | "Not now" | Closes the dialog; nothing written | Organiser, sponsor | Always shown |

### Screen C: North's time card (inside the intent, above the stage bar; also a line in "what is waiting for you")

Layout at 1280: a full-width card in North's colour, three buttons. At 390: the buttons stack.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| North line | agent line | When the time left crosses a threshold: "Half the time is gone. 2 of 4 steps are done. 3 people have not replied." Near the end: "Two days left and the process map is not started." At the end: "Time is up." Every number is read from the record | None | Organiser, sponsor | Not shown before the first threshold |
| Extend with a reason | button | "Extend" with North's drafted reason and days | Opens Screen B pre-filled; the person edits and confirms | Organiser, sponsor | Hidden when the viewer may not extend (Open questions 3) |
| Close with what we have | button | "Close with what we have" with North's closure draft | Opens `/centre/intent/<id>/close` with North's draft; a named person signs (file 09) | Organiser, sponsor | Never hidden while the intent is open |
| Cancel this intent | button | "Cancel this intent" | Opens the cancel dialog (file 09); a reason is required | Organiser, sponsor | Never hidden while the intent is open |
| Who picks | text | "Janet picks. If Janet does not pick by Mon 20 Oct, Daniel is asked." | None | Everyone who sees the card | Never empty once the card shows |
| Remind me tomorrow | link | "Remind me tomorrow" | Hides the card for the viewer until the next working day; the waiting line stays | Organiser | Hidden at the end state (snooze rule under Open questions 6) |

### Screen D: "Overdue intents" panel on the Pulse page (file 13 owns the page)

Layout at 1280: panel in the second column, a table. At 390: rows become cards.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Panel title | text | "Overdue intents" with a count of open intents past `time_box.ends` | None | Organiser (their own intents); company admin (all intents in the company, existence and clock only) | Count 0 |
| Row | list | Title, type chip, stage, days overdue, extensions used, organiser name | Opens `/centre/intent/<id>` (Screen C shows at the top) | Same as the panel | "Nothing is overdue." |
| "At risk" group | list | Open intents past the at-risk cut-off, not overdue, same row shape | Same | Same | Group hidden when empty |
| Days overdue | chip | "2 days overdue", red | None | Same | Not shown on at-risk rows |
| Ask North | button | "Ask North to draft options" | North drafts the Screen C options for that intent and puts the card on it | Organiser | Hidden if the card already shows |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet answers the start questions for an Initiative "Fund-level data definitions" (file 22) and clicks "Open this intent" (file 03). North proposes the time box from the catalogue (file 02: 10 working days) and the stage budgets (3, 6 and 1 days, file 02). Janet may shorten a stage before it opens. Nothing runs until she confirms.
2. The time box and the stage dues are written. The stage bar shows "Day 1 of 10" and the Think unfiltered clock.
3. Between steps, North recalculates the clock on each page load and every hour while the page is open. The server is the one source of time.
4. When the time left first crosses the first threshold, North adds the time card and a waiting line to Janet's list. Janet reads where the intent stands and may snooze or act.
5. At the second threshold North adds a red card and a line to Daniel (sponsor), for information only.
6. Janet clicks "Extend", chooses the days, writes "Waiting for the glossary from Finance", and clicks "Extend". The extension is written with her name, time and reason. The chips recalculate against the new end.
7. If the box ends with no pick, the clock shows Overdue. The current stage stays open, except the wall, which freezes at its window end (see Auto-freeze).
8. North asks Janet to pick. If she does not by the next working day, North adds a waiting line to Daniel.
9. Janet picks "Close with what we have". North has drafted the closure; Janet signs in `/centre/intent/<id>/close` (file 09). The intent is closed and the counters update. She leaves the screen.
10. Alternative at step 6: if the approval rule needs the sponsor, the request is pending. Daniel sees the first reason, the new reason and what is left, and approves or declines in his list. A decline sends Janet back to Screen C.

## States and transitions (table: state, who moves it, to what, what is written)

Clock states are derived from the dates and are never written as a field, so they cannot go out of step. Cut-offs are under Open questions 1.

| State | Meaning | Who moves it | To what | What is written |
|---|---|---|---|---|
| on_time | Above the first cut-off | Time passing (derived) | at_half | Nothing |
| at_half | At or below the first cut-off, above the second | Time passing (derived) | at_risk | Event `time.nudge` kind `half` in `intents/<id>/events.jsonl`; record `time_box.nudge_counts.half` plus one |
| at_risk | At or below the second cut-off, not over | Time passing (derived) | overdue | Event kind `risk`; `nudge_counts.risk` plus one |
| overdue | End passed, intent not closed or cancelled | Time passing (derived) | closing, cancelled, or back to an earlier state if extended | Event kind `over`; `nudge_counts.over` plus one; the intent `state` does not change by itself |
| extended | An extension was made | Organiser or sponsor (approval rule, Open questions 3) | Percentages recalculated from the new end | `time_box.ends` replaced; `extended_by` entry {by, at, reason, days, scope, was, status: approved} |
| extension_pending | An extension needs approval | Organiser asks | Approver approves (extended) or declines (previous clock state) | `extended_by` entry with `status: pending`, then `approved` or `declined` with `decided_by`, `decided_at` |
| closing | A named person picked "Close with what we have" | Organiser or sponsor | closed after signing (file 09) | `state: closing`, then closure per file 09 |
| cancelled | A named person picked Cancel with a reason | Organiser or sponsor | End | `state: cancelled`, reason in `closure.summary` (file 09) |
| frozen (wall only) | The wall window ended | The wall window clock (automatic) | Define strategically opens | `stages[].closed_at` for the wall; the frozen wall snapshot as v1 |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Status |
|---|---|---|
| `intents/<id>/intent.json`, `time_box` | `starts`, `ends`, `extended_by` | Existing in the brief (file 01 owns the file); extended below |
| `intents/<id>/intent.json`, `stages[]` | `key`, `state`, `opened_at`, `closed_at`, plus file 02's `default_days` and `days_used`, plus `due` | `due` New; the rest Existing in the brief or file 02 |
| `intents/<id>/events.jsonl` | One line per nudge, extension request and decision (file 16 owns the file) | New |
| `GET /api/intents/{id}/clock` | Per clock (stage and whole box): `starts`, `ends`, `working_days_total`, `working_days_left`, `hours_left`, `percent_left`, `state`, `extensions` count | New |
| `POST /api/intents/{id}/time-box/extend` | Body: `days`, `reason`, `scope` (stage or intent). Roles: organiser, sponsor | New (modelled on `POST /api/modules/m1_intent/sessions/{id}/timer/extend`) |
| `POST /api/intents/{id}/time-box/extend/{n}/decide` | Body: `decision` (approve, decline), `comment`. Role: the approver (Open questions 3) | New |
| Company profile `calendar` and `timezone` | `working_days` (list), `holidays` (list of dates), time zone name | New (none found in `sh_platform/profile/`; see Open questions 4) |
| `modules/m1_intent/contracts/intent_session.yaml` wall window | `wall_window_days`, Monday to Friday, UTC | Existing; not changed |
| `modules/m1_intent` session `timer/extend` route and `stage_extensions` store | Minute extensions for the live wall and live Brainstorm session | Existing; not changed |
| Run log | One line per nudge, extension, decision | Existing (`sh_platform` run log) |

## Fields this feature adds to the intent record

```
time_box: {
  starts, ends,
  working_days,                           # the box length in working days when it was set (from the catalogue or the organiser's change)
  calendar: "profile" | "mon-fri",        # which calendar was used, so the sum can be repeated
  extended_by: [{
    by, at, reason, days, scope: stage|intent,
    was,                                  # the end before this extension
    status: approved | pending | declined,
    decided_by, decided_at
  }],
  nudge_counts: {half, risk, over}        # counts only; the lines are in events.jsonl
}
stages[].due                              # ISO time the stage should end
```

The brief's `extended_by` has `{by, at, reason}`; the other entry fields are additions. No brief field is renamed. The stage budget fields `default_days` and `days_used` belong to file 02 and are not redefined here.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North, at open.** Drafts the time box from the catalogue default (file 02: Initiative 10, Brainstorm 3, Problem 5, Decision 2, Weekly check-in one week recurring, all working days) and the stage budgets (file 02's split, not set here). The organiser acts: confirms or changes the days. North never starts the clock by itself.
- **North, at the first threshold.** Drafts a status line from the record only: steps done out of steps, who has not replied, the next unstarted step. Offers three buttons: Extend, Close with what we have, Cancel. Also a waiting line to the organiser. The organiser may snooze.
- **North, at the second threshold.** Same card in red. Says whether the pace will finish in time only when the pace can be worked out from completed steps; otherwise "I cannot tell yet." The number of completed steps needed is under Open questions 5. Adds an information line for the sponsor.
- **North, at the end.** Writes "Time is up", drafts the closure from what exists (summary, why it happened, what came out, next steps, file 09 shape), and asks the named person to pick: the organiser first, then the sponsor after the wait set under Open questions 7.
- **North, on an extension.** Drafts a reason from what is outstanding ("The glossary from Finance is not in"); the person edits and sends. North never sends an extension.
- **North, on an extension that needs approval.** Writes a short request to the approver with the earlier reason, the new reason, and what is left.
- **Lens.** No part in the clock.
- **Nira.** Turns each nudge into a waiting line and a Pulse line (file 13). Nira does not decide thresholds.
- Agents never extend, close or cancel. A named person acts each time.

## Rules (visibility, time box, who may do what)

**Time box and clock**
- Every intent gets a time box when it opens; `time_box.ends` is never empty for an open intent.
- The clock counts working days. The calendar comes from the company profile when it has one; otherwise Monday to Friday with no holidays, as `window_minutes` in `modules/m1_intent/domain/timer.py` does today (it has no calendar input yet; the new function adds one and `window_minutes` stays as it is for the wall).
- A working day is counted from the start time of day: day 1 ends at the same time of day on the next working day. A start on a non-working day counts from the next working day at the same time.
- Percent left is working time left divided by working time in the current box, using 24 working hours per working day as `window_minutes` does. The server computes in UTC; the screen shows the company's time zone from the profile, else UTC.
- Display: "N days left", "N hours left" or "Overdue by N days or hours". The switch from days to hours is under Open questions 1. Zero or less is overdue.
- Stage clocks use the same rules against `stages[].due`. A stage clock never ends after the time box end. If a stage is behind, the later stages lose time and North says so.
- Stage budgets are file 02's: Initiative 3, 6, 1 days; Brainstorm 1, 1, 1; Weekly check-in 3, 1, 1; Problem 1, 2, 1, 1; Decision 1, 1. This file states none of its own. The Initiative's Think unfiltered budget sets the wall window for the v1 wall session (one number, not two); that the v1 default of 5 differs from file 02's 3 is file 02's open question.

**What a person may do**
- Extend: organiser or sponsor, with a reason that is kept. Who needs approval, and any cap, is under Open questions 3.
- Close with what we have and Cancel: organiser or sponsor, under file 09's rules. A cancel needs a reason.
- Nobody else (participants, affected people, observers, area members, super admin, company admin) can change the clock. An observer reads what a participant reads and never writes.

**Auto-freeze per stage**

| Type and stage | At the clock end | Why |
|---|---|---|
| Initiative, Think unfiltered (the wall) | The wall freezes automatically at its window end. No card is added or changed after the freeze. The frozen wall is page one of the charter. Untouched North suggestions are dropped (v1 A-056) | v1 rule, already built through the wall window |
| Initiative, Define strategically | Nothing freezes. The stage stays open and marked overdue; North asks for a pick | Work in Define is confirmed by people; freezing could lose unconfirmed drafts |
| Initiative, Build-ready | Nothing freezes. The check shows what is missing and North asks for a pick | A check is a read, not an edit |
| Brainstorm, live session | The existing session timers end each timed stage by themselves (`AUTO_MOVE` in `timer.py`) | Existing behaviour |
| Brainstorm (outside the session), Problem, Decision | Nothing freezes. Overdue and a pick | A person must decide |
| Weekly check-in | The week closes by the clock at its close day. Each `broke` item without a fate needs one before the week closes (file 40 owns how); `ran` and `thought` items left undecided close as `nothing` with reason "Not reviewed this week". A new week opens on the next working day after the close day, even if the review is unfinished | Ruling 3 of the brief; the check-in is recurring and cannot wait |

The auto-freeze never signs anything and never closes an intent. It stops edits to the frozen part only.

**Visibility**
- Everyone who can see an intent (area members, affected, participants, observers) sees its clock chip and the time box end. This follows file 05's corrected matrix.
- Extension reasons are seen by organiser, sponsor, participants and observers; affected people see them only when the organiser switched on "affected people may read" or named them on a share. Area members see "Extended once" with no reason.
- The overdue panel shows the viewer's own intents (organiser) or all intents' existence and clock (company admin). No content.
- The super admin sees existence only, including time box status (on time or overdue), read through the kernel on request. Never reasons. Where the company switch "titles private to the company" is on, titles are removed from that view.
- A draft intent is visible only to the person who started it. A cancelled or closed intent keeps its record, including extensions, and appears in Past.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Computed from | Shown where |
|---|---|---|
| Closed inside the time box | Closed intents where `closure.closed_at` is not later than the original end (the earliest `was`, or `ends` when never extended); shown as "7 of 10" | Pulse (organiser, own areas), company admin overview |
| Closed after an extension | Closed intents where `extended_by` has at least one `approved` entry | Same |
| Extensions per intent | Count of `approved` entries in `extended_by`, per intent | Intent record view |
| Mean extensions across closed intents | Mean of the line above | Pulse; shows "Fewer than five" below five closed intents |
| Overdue now | Open intents past `time_box.ends` | Overdue panel title |
| At risk now | Open intents past the at-risk cut-off, not overdue | Overdue panel group |
| Days overdue at close | Working days between the original end and `closure.closed_at`, where later | Intent record view |
| Cancelled for time | Needs a time tag on the cancel reason, which file 09 may not define | "Not available yet: file 09 defines no time tag on a cancel reason" |

Counts are exact. A mean, median or any per-person figure shows "Fewer than five" below five records. Where no closed intent exists, a counter says "Not available yet" and names the missing record (closed intents). The live session counters in `modules/m1_intent` (`actions`, free-text counts, `cards_*`) are not touched by this feature.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `graft ask "stage timer extend"`, `"working days window"`, `"stage bar"`; direct reads of the files below. All paths below were checked and exist, except the one marked missing.

| Exists | Where | Decision |
|---|---|---|
| Stage bar: stages in order, current lit, done marked, one next-step button behind "Are you sure?" | `ui/src/modules/m1_intent/wall/StageBar.tsx` | Reshaped. Keep the markup, class names and "Are you sure?" pattern. Change: take `stages` and `clock` as props instead of the fixed list; add the clock chips and the Extend button. The v1 wall page keeps the v1 list |
| `closesWhen` ("Fri 17:00") | `ui/src/modules/m1_intent/wall/copy.ts`, line 82 | Copied as is, used for the closing line |
| Stage timer: `ends_at`, `status`, `AUTO_MOVE`, `is_timed` | `modules/m1_intent/domain/timer.py` | Reused for the live Brainstorm session and the wall. The percent states are a new function beside it |
| Working-day sum | `window_minutes` in `modules/m1_intent/domain/timer.py` (Monday to Friday, no holidays, UTC; no calendar input) | Reshaped: a new `working_days_between` takes the calendar; `window_minutes` stays and calls it |
| Extend route with minutes and roles | `modules/m1_intent/api/briefing.py`, route `/sessions/{session_id}/timer/extend` at line 420 | Reshaped: new day-based route on the intent record; the live session route is unchanged |
| Wall window: `WALL_DAYS_DEFAULT`, `WALL_DAYS_MAX` | `modules/m1_intent/domain/preparation.py` line 31; `modules/m1_intent/contracts/intent_session.yaml` lines 25 to 30 | Reused. (Path in the first draft was `contracts/intent_session.yaml`; that path does not exist.) |
| Wall window rule, freezing at rooms end | `docs/specs/INTENT-CENTRE-SPEC.md` section 3 | Reused |
| Input counters | `modules/m1_intent/store/sessions.py` line 26; `modules/m1_intent/api/deps.py` | Not used: they count actions in a live session, not time |
| Profile calendar and time zone | `sh_platform/profile/` (searched for calendar, holiday, timezone: none) | New; the only new piece of company data here |
| Counts under five | `sh_platform/egress/aggregates.py` | Not used here; the brief's "Fewer than five" rule is applied in the counters |
| Company-plane JSON files and viewer filter | `sh_platform/jsonfile.py`; `sh_platform/profile/view.py` | Reused for `intents/<id>/intent.json` and filtering |

Genuinely new: percent-left states, the day-based extension with approval, the Overdue panel, the profile calendar and time zone.

## Not in this feature

- Closure content and the sign step (file 09).
- The Pulse page layout beyond the Overdue panel (file 13).
- Per-stage work: wall cards, Define, the build-ready check.
- Email or phone nudges. Waiting lines and Pulse lines only.
- Time tracking of hours worked by people.
- Editing the default time boxes per type (file 02's catalogue).
- Gap analysis, which is room 0 of the Build centre and has no clock here.

## Open questions

1. **Clock cut-offs.** The brief gives none. Proposed: neutral above 50 percent left, amber at 50 or less, red at 20 or less, "hours left" under two working days. These also set North's two nudge points. Owner to decide.
2. **Extension choices.** Proposed day counts in the dialog (1, 2, 3, 5) and reason length (10 to 300 characters). Not in the brief.
3. **Approval and cap.** Proposed: the organiser may extend once alone; a later extension needs the sponsor; no cap. For types with no sponsor (Brainstorm, Weekly check-in, Problem, Decision) proposed: the company admin approves a second. The brief names no approver or cap.
4. **Company calendar and time zone.** No `calendar` or time zone field exists in the profile. Who edits them (company admin on the control screen?) and whether holidays are typed or imported.
5. **Pace statement.** North says whether the pace will finish only after a number of completed steps. Proposed two; not decided.
6. **Snooze.** Proposed once per day for the organiser. Is any snooze acceptable on a red card?
7. **If neither organiser nor sponsor picks.** Proposed: the sponsor is asked after one working day, the company admin after three. Not decided.
8. **Percent base.** Percent of the current box including extensions, or of the original length. The first keeps the colour honest after an extension; the second punishes late work.
9. **Stage splits.** File 02's split (Initiative 3, 6, 1) is used. It shortens the v1 wall default of 5 to 3; file 02 owns that question.
10. **Brainstorm live session end.** Whether the single live session may run past its own timer without an extension record.
11. **Weekly check-in lateness.** Whether a week that closes late counts toward "closed inside the time box".
12. **Ruling 1 spelling in file 02.** File 02 and the brief name the check-in "Weekly pulse" in places; this file uses "Weekly check-in" on screen and `pulse` as the record key, per ruling 3.
