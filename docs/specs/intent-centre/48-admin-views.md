# 48. Admin views (company admin and super admin)

Part of: Intent Centre v2. Depends on: 01 (record), 02 (type catalogue), 03 (type settings, cancel), 05 (areas, existence projection), 07 (clock, overdue), 09 (closure), 10 (ratings), 14 (permissions matrix), 19 (counters), 38 (Weekly check-in questions). Feeds: 14 (adds the routes below), 18 (admin first run).

## Purpose (three sentences)

The company admin needs one place that shows every intent in the company with its outcome and closure, what is late, what nobody rated, and how many there are per area and type, plus the defaults every new intent starts from. The super admin needs one place in Control that shows each company's intent counts and the centre switch, and never a line of content. Neither role edits content, signs for anyone or deletes; the one act the company admin has is a cancel with a reason, which is logged.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Company admin | Weekly look: what is late, what is closed, what nobody rated | Opens "All intents" from the Intent Centre section links, or follows a Nira line "2 intents are overdue" |
| Company admin | Setting up or changing how the centre behaves | Opens the "Defaults" tab once at set-up, then rarely |
| Company admin | Month end: hands the register of closed intents to the sponsor or auditor | Presses "Download register (CSV)" |
| Company admin | An intent is stuck and its organiser has left or cannot act | Opens it from the Overdue tab and presses "Cancel this intent" |
| Super admin | Checking that a company's centre is on and in use | Opens Control, then "Intents" |
| Super admin | Switching the centre on or off for a company | Flips the Intent centre switch |

## Entry points (every route, link, Pulse line, button that leads here)

- Intent Centre section links (14): "All intents" (company admin only) opens `/centre/intent/admin`. "Intent defaults" opens `/centre/intent/admin?tab=defaults`. Both are one route with a `tab` query; no other admin page route exists (brief, section 10, ruling 1).
- Area and people tagging is spec 05 screens A and B at `/company/settings/areas` and `/company/settings/areas/people`. This file adds a link to each from the Counters tab ("Set up areas", "Tag people") and from the empty states below. It does not rebuild them. Those two routes are spec 05's; they sit outside the `/centre/intent/...` convention and 05 carries that as its own open question.
- Pulse line from Nira to the company admin: "N intents are overdue" opens `/centre/intent/admin?tab=overdue`. Here "Pulse" means the daily page (row to be added in 13, see Open questions).
- Spec 19 home counter "Show the intents" opens `/centre/intent/admin` with the matching filter, for the company admin only; every other role opens the board.
- Control (super admin): rail item "Intents" opens `/centre/control/intents` (spec 05 screen E, reshaped here). The centre switch sits in the existing Companies card.
- Intent page `/centre/intent/<id>` is the destination of every row. The admin sees the existence and outcome view (05, "Locked note"), plus the "Cancel this intent" button described below.

## Screens, element by element

### Screen A. All intents (company admin)

Route `/centre/intent/admin`. At 1280: page header (title "All intents", count line, "Download register (CSV)"), a row of five tabs (All intents, Overdue, Unrated, Counters, Defaults), a filter row, then the table full width. At 390: tabs become a select, filters open as a sheet, table rows become cards (title, type chip, state chip, clock chip, "Open"); "Download register (CSV)" moves into a menu.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Count line | text | "126 intents: 9 open, 4 overdue, 98 closed, 15 cancelled" (each number counted from the rows the filter returns, not a cache) | None | Company admin | "No intents yet. They appear here when someone starts one." plus the link "Start something" |
| Tab bar | tabs | All intents, Overdue (count), Unrated (count), Counters, Defaults | Switches the view; the tab sits in the URL (`?tab=`) | Company admin | n/a |
| Type filter | chip group | Initiative, Brainstorm, Weekly check-in, Problem, Decision; several may be on | Re-queries | Company admin | n/a |
| State filter | chip group | Draft is never offered (drafts are private to their creator, ruling 14). Open, In session, Closing, Closed, Cancelled | Re-queries | Company admin | n/a |
| Area filter | select (multi) | Active and retired areas from `GET /api/company/areas` (05); "No area" as the last option | Re-queries | Company admin | "No areas yet. Set up areas." link to 05 screen A |
| Organiser filter | select | People who organised at least one intent | Re-queries | Company admin | Hidden when there are no intents |
| Dates filter | two date fields | "Opened from", "Opened to", in the company time zone from the profile, else UTC | Re-queries | Company admin | n/a |
| Search | field | Searches title and purpose only | Re-queries when typing pauses | Company admin | "No intent matches. Clear the filters." with button "Clear filters" |
| Table | list | One row per non-draft intent, columns below. Cancelled intents stay in the list | Row click opens the intent page | Company admin | As the count line |
| Column Title | cell | Title, with purpose in small text | Link to `/centre/intent/<id>` | Company admin | n/a |
| Column Type and State | cell | Type chip and state chip; "Cancelled by admin" chip when it was | None | Company admin | n/a |
| Column Stage | cell | Current stage name from `stages[]` | None | Company admin | "Not started" for an open intent with no stage opened |
| Column Areas | cell | Area chips; "No area" in amber when empty | None | Company admin | n/a |
| Column People | cell | Organiser name, then "+N people" (count of every named person in `people` except the organiser) | None | Company admin | n/a |
| Column Opened and Ends | cell | Opening date and final `time_box.ends` (after extensions); "1 extension" when any | None | Company admin | "Not started" |
| Column Clock | chip | Spec 07 chip: "3 days left", "Overdue by 2 days", or "Done in time", "Done 2 days late" for closed | None | Company admin | "No clock yet" |
| Column Outcome | cell | For closed: first line of `closure.what_came_out` and the next steps as chips (Initiative, Backlog, Problem, Nothing). For others: "Not closed". The `outcome` object exists from opening (ruling 6) but its content is never shown before close | None | Company admin | "Not closed" |
| Column Rating | cell | "4.2 from 11" for closed intents with three or more ratings; "2 ratings" below three; "Not rated" when none. Weekly check-in series and weeks show "Not rated by design" (ruling 3) | None | Company admin | "Not rated" |
| Sort | header click | Opened, Ends, Title, Type, State | Re-orders the current result | Company admin | n/a |
| Load more | button | "Show more" | Fetches the next page (`after`) | Company admin | Hidden at the end |
| Download register (CSV) | button | "Download register (CSV)" | Fetches `GET /api/intents/admin/register` for the current filters and builds the file in the browser (see Screen C) | Company admin | Disabled with "Nothing closed yet" when no closed intent matches |

What the admin never sees in this table or on the page it opens: the name of an anonymous author, an anonymous rating's author, sealed material, drafts, or participant-only content (cards, notes, transcripts). These are removed by `sh_platform/profile/view.py` before the route answers.

### Screen A2. Overdue tab

Same route, `?tab=overdue`. Layout as Screen A at 1280 and 390. Lists open, in-session and closing intents past `time_box.ends` (spec 07 derivation), most overdue first. Beneath them, an "At risk" group (not yet overdue, as spec 07 Screen D defines it).

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| North line | agent line | "4 intents are past their end. 3 have been extended once." Plus "1 has no named sponsor." only for types that take a sponsor. Built only from record fields | None | Company admin | Hidden when none are overdue |
| Overdue row | list | Title, type chip, stage, "N days overdue", extensions used, organiser, sponsor ("No sponsor" when none) | Opens the intent page | Company admin | "Nothing is overdue." |
| At risk group | list | Same row shape without "days overdue" | Same | Company admin | Group hidden |
| Cancel this intent | button (on the intent page, not in the row) | See Screen D | Opens the cancel dialog | Company admin | n/a |

### Screen A3. Unrated tab

Same route, `?tab=unrated`. Layout as Screen A. Lists closed intents (not cancelled, and never Weekly check-in series or weeks, which are not rated) with no entry in `ratings[]`, newest close first. A rating by someone anonymous counts as a rating; the list never reveals who.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Unrated row | list | Title, type chip, closed date, "Closed 12 days ago", organiser, number of people who could rate (count of participants) | Opens the intent page | Company admin | "Every closed intent has at least one rating." |
| Reminder note | text | "North reminded the participants once. Nobody else is asked." Read from the reminder entry in `history`; timing is spec 10's | None | Company admin | "No reminder was sent." when the history has no reminder entry |

The admin cannot rate for anyone and has no "Remind" button here. Reminders are North's (10). The list is information.

### Screen A4. Counters tab

Same route, `?tab=counters`. Layout as Screen A; at 390 each table becomes cards. Two tables from `GET /api/intents/admin/counters`.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Area by type table | list | Rows are areas (and "No area"), columns are the five types plus "All". Each cell: open, overdue, closed, cancelled as four small numbers ("3 open, 1 overdue, 8 closed, 0 cancelled") | A cell opens the All intents tab filtered to that area and type | Company admin | "No intents yet." If no areas: "No areas yet. Set up areas." |
| Totals row | list | Distinct intents per type (an intent in two areas is counted once here, in each area row above) | Same | Company admin | n/a |
| Untagged line | text | "5 people are not tagged to any area and see only what they are named in." from `people.<pid>.areas` | "Tag people" opens 05 screen B filtered to untagged | Company admin | "Everyone is tagged." When the profile holds no area data: "Not available yet. No areas have been set up." |
| No area line | text | "2 intents have no area." (only possible for intents created before areas existed) | "Show them" filters the table | Company admin | Hidden at zero |
| Link row | links | "Set up areas" to `/company/settings/areas`; "Tag people" to `/company/settings/areas/people` | Opens spec 05 screens | Company admin | n/a |

The wider measures (closed inside the time box, days to close, ratings by type, one-month use) stay in spec 19 at `/centre/intent`. This tab is counts by area and type only.

### Screen B. Defaults tab (company admin)

Route `/centre/intent/admin?tab=defaults`. At 1280: two cards stacked in one column (Time boxes, Privacy), a read-only note card (Weekly check-in questions) between them, and one Save bar fixed at the bottom. At 390: same order, Save bar full width.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Time box row (four rows: Initiative, Brainstorm, Problem, Decision) | field | Type name, number of working days, the catalogue default beside it in grey ("Catalogue default: 10") | Whole number, one or more, edited in place. Marked "Changed" when it differs from the catalogue | Company admin | Never empty; falls back to the catalogue value |
| Weekly check-in time box row | text | "One week, recurring. Set by the check-in itself." | None. Not editable here | Company admin | n/a |
| Reset time boxes | button | "Back to catalogue defaults" | Clears the company override for the four rows after Confirm | Company admin | Disabled when nothing is changed |
| Weekly check-in questions note | text | "Each organiser sets the four start questions when starting a check-in. The company does not change the wording here." | None | Company admin | n/a |
| Titles private to the company | switch | "Keep intent titles private to this company" with the note "The platform operator then sees that an intent exists, its type, state, areas and dates, but not its title." | Writes `titles_private` in `settings/intent_centre.json`. Default off | Company admin | Off |
| Affected people note | text | "Whether affected people may read an intent's content is chosen by its organiser when they start it. It is off unless they switch it on." | None | Company admin | n/a |
| Save | button | "Save defaults" | Writes the company settings files via `PUT /api/intents/admin/settings`. A toast says "Saved. New intents use these defaults. Open ones keep theirs." | Company admin | Disabled until a field changes |
| Discard | button | "Discard changes" | Reloads from the files | Company admin | Disabled until a field changes |
| North line | agent line | Shown when a changed time box is less than the sum of that type's stage defaults in the catalogue: "Your Initiative time box is 6 working days. The stages add up to 10. North will propose an extension early." Facts from the catalogue only | None | Company admin | Hidden otherwise |

A change applies only to intents opened after the save. Spec 03 copies the time box value into the record (`time_box.default_days`), so later changes never rewrite an open intent.

### Screen C. Register of closed intents (CSV, no new page)

The button on Screen A. The file is built in the browser from `GET /api/intents/admin/register`, the way spec 19 builds its CSV. One row per closed or cancelled intent that matches the filters (Weekly check-in series appear as one row each, rating columns blank). Columns, in order:

`id, type, title, state, areas, organiser, sponsor, opened, time_box_end, closed_at, closed_in_time, extensions, summary, what_came_out, next, rating_count, rating_mean, cancelled_by, cancel_reason`

- `areas` and `next` are joined with a semicolon.
- Dates are written in the company time zone from the profile, else UTC.
- `rating_mean` is blank under three ratings (the ratings rule, ruling 8), with `rating_count` always filled.
- Never in the file: anonymous authors, notes on ratings, sealed material, participant names beyond organiser and sponsor, content of the intent.
- Any cell that starts with `=`, `+`, `-`, `@` or a tab is written with a leading apostrophe so a spreadsheet cannot run it.
- File name: `intent-register-<company>-<yyyy-mm-dd>.csv`, UTF-8 with a byte order mark so a spreadsheet opens accents correctly.
- Each download writes one run-log line: who, when, filters, row count. No row text.

### Screen D. Cancel dialog (company admin, on the intent page)

Opened from "Cancel this intent" on `/centre/intent/<id>`. Shown only when `state` is open, in_session or closing. At 1280 a centred dialog; at 390 a full-screen sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Cancel this intent | button | "Cancel this intent" (secondary) | Opens the dialog | Company admin; also organiser and sponsor by 03, 07 on their own screens | Hidden for closed and cancelled |
| Warning | text | "This stops the intent. Its record is kept, shown in Past, and says you cancelled it and why. The organiser and sponsor are told." | None | Company admin | n/a |
| Reason | field (multi-line) | Required text, at least one character after trimming | Typing enables the confirm button | Company admin | Confirm stays off while empty |
| Confirm | button | "Cancel this intent" | `POST /api/intents/<id>/admin-cancel` with `{reason}` | Company admin | Disabled until a reason is typed |
| Keep it | button | "Keep it running" | Closes the dialog; nothing written | Company admin | Always shown |
| Refusal | text | "This intent has just changed. Open it again to see where it stands." (409 when the state moved while the dialog was open) | Closes the dialog | Company admin | Hidden |

### Screen E. Super admin Intents (Control)

Route `/centre/control/intents`. Rail item "Intents" in `ControlPage` (super admin rail only). At 1280: a company picker on the left (the existing `cp-pick` select), then, for the chosen company, three cards: Centre, Counts, Intents. At 390: cards stack, the table becomes cards.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Company picker | select | Companies from `GET /api/control/companies` | Loads that company's card set | Super admin | "No companies yet." (existing `t.centres.none`) |
| Intent centre switch | switch | "Intent centre" on or off, from the catalogue entry for centre `intent` | `PUT /api/control/companies/{id}/centres/intent` `{on}`; the existing `Switch` component and saved note | Super admin | n/a |
| Switch note | text | "Off hides the centre for everyone in the company. Intents and their records are kept." (the existing off rule line) | None | Super admin | n/a |
| Counts by type and state | list | Rows are the five types, columns are Open, In session, Closing, Closed, Cancelled, plus "Total" | None | Super admin | "This company has no intents yet." |
| Overdue count | stat | "4 overdue" and "2 at risk" (spec 07 derivation over open intents) | None | Super admin | "0 overdue" |
| Last activity | stat | Date of the newest `created_at` or `closure.closed_at` | None | Super admin | "No activity yet." |
| Existence table | list | Title, type, state, areas, people count, opened, ends, clock chip ("Overdue by 2 days"). No row opens | None | Super admin | "This company has no intents yet." |
| Title cell when private | cell | "Title private to the company" in grey, in place of the title | None | Super admin | n/a |
| Page note | text | "Control sees that intents exist. It never sees what is in them." | None | Super admin | n/a |

The existence table lists only what ruling 5 allows: title (unless private), type, state, areas, people count, dates, time box status. No purpose, no stage content, no organiser name, no outcome, no closure text, no ratings. Drafts are not listed (ruling 14). The super admin reads this through the kernel on request, one company at a time; the control plane keeps no copy of company data. That is request A-074 for Nitin: the super admin may read intent existence through the kernel. Until it is approved the card shows only the switch.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

Company admin (Harvey is the owner role; the admin here is the company admin of Ardmore):

1. The admin opens the Intent Centre and presses "All intents". The page calls `GET /api/intents/admin/list` with the admin tier; view.py strips anonymous authors, sealed material and drafts.
2. North reads the clock of every open intent and writes the line on the Overdue tab from record fields. The admin opens the Overdue tab.
3. The admin opens one overdue Problem. The page shows existence, outcome so far and the "Cancel this intent" button. The admin cannot read the participants' content.
4. The admin sees the organiser is away. The admin presses "Cancel this intent", types "Organiser has left; the fix was done in the other Problem", and presses the confirm button.
5. The route sets state to cancelled, writes the history entry and a run-log line, and Nira adds a line to the organiser and sponsor: "Your company admin cancelled <title>: <reason>."
6. The admin opens the Unrated tab, sees two closed Decisions with no rating, opens one, and leaves it to North's reminder.
7. The admin opens Counters, sees Operations has 3 open and 1 overdue Problem, and presses "Tag people" because the untagged line says 5 people are not tagged. That opens spec 05 screen B and the admin leaves this screen.
8. At month end the admin presses "Download register (CSV)" and saves the file. The admin leaves.

Super admin:

1. The super admin opens Control and picks "Intents". The page calls `GET /api/intents/control/summary` for the first company; the kernel reads that company and returns the projection.
2. The super admin reads the counts and the existence table. Nothing opens.
3. The super admin flips the Intent centre switch for a new company to on. The existing route writes the entitlement and the saved note appears. The super admin leaves.

## States and transitions (table: state, who moves it, to what, what is written)

This feature adds one transition and one setting. Every other transition belongs to 01, 03, 07 and 09.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| open, in_session or closing | Company admin, with a reason | cancelled | `state: cancelled`; `closure.summary` holds the reason; `closure.closed_by` the admin; `closure.closed_at`; `closure.cancelled_by_role: "company_admin"`; a history entry `{kind: "cancelled_by_admin", by, at, reason}` (the entry goes to `events.jsonl`, 16; the record holds counts only); `closure.next: [{kind: nothing, reason}]`; one run-log line |
| draft | Nobody but its creator (05, 03) | n/a | The admin cannot see or cancel a draft |
| closed or cancelled | Nobody | n/a | Past intents are never changed or deleted. The cancel route answers 409 |
| centre switch off | Super admin | centre on | Entitlement file via `entitlements.set_centre` (Existing) |
| centre switch on | Super admin | centre off | Same. Records are kept; routes under the centre are refused for the company |
| defaults saved | Company admin | new settings version | `settings/intent_types.json` and `settings/intent_centre.json` in the company plane |

## Records read and written (file or route, fields; mark Existing or New)

| Record or route | Fields or use | Existing or New |
|---|---|---|
| `intents/<id>/intent.json` (01) | Read through `sh_platform/profile/view.py` at tier `admin`: type, title, purpose, state, areas, people (counts and organiser, sponsor), stages, time_box, outcome (only once closed), closure, ratings (score only), links | Existing record shape (01, New), New tier `admin` in view.py |
| `intents/<id>/events.jsonl` (16) | One cancel entry appended; read only for the reminder entry on the Unrated tab | New (16) |
| `GET /api/intents/admin/list` | Filters `overdue=1`, `unrated=1`, `organiser`, `opened_from`, `opened_to`, `q`, `type`, `state`, `area`, `after`. Each item adds `clock`, `rating_mean`, `rating_count`, `cancelled_by_role` | New. Company admin only |
| `GET /api/intents/admin/counters` | Area by type by state counts, untagged people count, no-area intent count | New. Company admin only |
| `GET /api/intents/admin/register` | Closed and cancelled rows with the CSV columns, for the filters | New. Company admin only |
| `POST /api/intents/<id>/admin-cancel` | `{reason}`; 400 when blank, 409 when not cancellable | New. Company admin only |
| `GET /api/intents/admin/settings`, `PUT /api/intents/admin/settings` | Time boxes and `titles_private` | New. Company admin only |
| `settings/intent_types.json` (company plane) | `types.<type>.time_box_days` for the four timed types | New (the company override beside the pack default, per the 03 proposal) |
| `settings/intent_centre.json` (company plane) | `titles_private: bool`, default false | New |
| `GET /api/intents/control/summary` | Per company: counts by type and state, overdue, at risk, last activity, titles_private | New. Super admin only. Reads through the kernel (A-074) |
| `GET /api/intents/control/<company_id>/existence` (05) | Existence projection rows; title omitted by the route when `titles_private` | New (05), reshaped here. Super admin only |
| `GET /api/control/companies` | `centres_on` already lists the centre ids on | Existing |
| `PUT /api/control/companies/{company_id}/centres/{centre_id}` | The on or off switch | Existing |
| `GET /api/control/catalogue` | Centre names and descriptions for the switch label | Existing |
| `GET /api/company/areas`, `PUT /api/profile/people/{pid}/areas` (05) | Area list and tagging | New in 05, used here unchanged |
| `modules/m1_intent/contracts/intent_types.yaml` (02) | Catalogue defaults shown beside company values | New in 02 (not in the repo yet), read here |
| Run log (`sh_platform/agents/runs.py`, `record`) | Cancel, register download, defaults saved | Existing |

## Fields this feature adds to the intent record

| Field | Meaning |
|---|---|
| `closure.cancelled_by_role` | `organiser`, `sponsor` or `company_admin`. Lets the table show "Cancelled by admin" |
| Event kind `cancelled_by_admin` | `{by, at, reason}` as above, in `events.jsonl`. Kept like every other event |
| `time_box.default_days` | Already in 03. Read here only |

Company-level, not on the intent: `titles_private` and per-type `time_box_days`. `share.affected_may_read` is owned by the organiser's start questions (brief, ruling 4); this file adds no default for it.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** keeps the clock (07). It writes the one-line summary on the Overdue tab and the check on the defaults tab, from record and catalogue fields only. It never cancels, extends or closes. The company admin acts by pressing "Cancel this intent".
- **Lens** suggests areas for untagged people (05 screens A and B). It has nothing to draft on the admin views. The admin accepts or ignores.
- **Nira** adds one line to the company admin when intents are overdue, and one line to the organiser and sponsor after an admin cancel. It states counts and the reason the admin typed, nothing else. The admin does nothing further.
- No agent changes a default, a switch or the register. Agents never sign.

## Rules (visibility, time box, who may do what)

- The company admin sees every non-draft intent in the company: title, type, state, stage, areas, people counts, dates, clock, outcome and closure, rating score and count. The admin never sees an anonymous author, an anonymous note, sealed content, or the content of an intent they do not take part in (brief, section 4). All of it is filtered in `profile/view.py`, not in the screen.
- The company admin may: filter, read the list, download the register, cancel with a reason, change company defaults, tag areas and people (05). The company admin may never: edit an intent's content or people, sign or approve for someone, rate for someone, extend a time box, reopen a closed intent, or delete anything. These routes answer 403 "You can see this but not change it."
- The super admin sees that each intent exists: title (unless private), type, state, areas, people count, dates and time box status, plus counts per type and state and the overdue count. The super admin never sees purpose, organiser or participant names, outcome, closure text, ratings, notes or content, and has no cancel, edit, sign or delete.
- Titles: `titles_private` is a company decision, off by default, set by the company admin only. The super admin cannot change it. When on, the existence table and the summary route return no title for that company. The route does not send the title and let the screen hide it.
- A cancel by the company admin needs a reason (trimmed, not empty). It is written to the record and the run log with who, when and why. It is allowed only while the intent is open, in session or closing. A cancelled intent stays visible, is shown in Past, and says by whom and why.
- Nothing is deleted. Cancelled and closed intents stay in every list and in the register.
- A company switched off by the super admin: all Intent Centre routes for that company refuse with the existing centre-off answer; the admin screens say "The Intent centre is switched off for your company. Ask the platform operator." The Control view keeps working.
- A change to a time box default applies to intents opened after the save.
- A route that is not in `sh_platform/route_permissions.yaml` is refused (default deny). Each route above gets a line there, company admin only or super admin only.
- Cross-company reads fail closed. The super admin route reads each company through the kernel, one company at a time, never as a join.
- Counts are exact. Any mean or median shows "Fewer than five" below five records. Ratings aggregate from three. No per-person figure exists on any admin view.

## Counters and measures of this feature (numbers only, each traced to a record)

| Id | Measure | Definition | Fields | Empty |
|---|---|---|---|---|
| A1 | Intents per area, type and state | Count of non-draft intents with that area tag, `type`, and derived state (open, overdue, closed, cancelled). An intent with two areas counts in both rows; the totals row counts it once | `areas`, `type`, `state`, `time_box.ends`, `time_box.extended_by` | "No intents yet." |
| A2 | Overdue now | Open, in-session and closing intents past final `time_box.ends` (07) | `state`, `time_box` | "Nothing is overdue." |
| A3 | Unrated closed intents | Closed (not cancelled, not a Weekly check-in) with `ratings` empty | `state`, `type`, `ratings` | "Every closed intent has at least one rating." |
| A4 | People not tagged to an area | Accounts in the profile with no `people.<pid>.areas` | `people.<pid>.areas` | "Everyone is tagged." |
| A5 | Intents with no area | Non-draft intents with `areas` empty | `areas` | Hidden at zero |
| A6 | Cancelled by the company admin | Count of cancelled with `closure.cancelled_by_role = company_admin` | `closure.cancelled_by_role` | "None." |
| S1 | Per company, per type and state | Same as A1 without the area split, for the super admin | `type`, `state` | "This company has no intents yet." |
| S2 | Per company overdue and at risk | A2, and the at-risk rule of 07 | `time_box` | "0 overdue" |

A number whose record is missing says "Not available yet" and names it (for example "Not available yet. No areas have been set up.").

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Paths below were checked to exist by reading the files and grep in the repo (graft was not run by this agent).

| What | Where | Decision |
|---|---|---|
| Super admin company switches (centre and module) | `ui/src/pages/ControlPage.tsx` `SuperCentres` lines 109 to 165, `Switch` line 46, rail and tab map lines 305 to 332 | Existing, used as is. The Intent centre switch is the entry for centre `intent` in the existing list. Only new: the rail item "Intents" and the counts card beside it |
| Company-side centre list (read only) | `ControlPage.tsx` `CompanyCentres` lines 240 to 252 | Existing, unchanged |
| Control routes | `sh_platform/control/api.py` `companies` lines 96 to 109, `_switch` and `put_centre` lines 128 to 146, `catalogue` line 80 | Existing, unchanged. The new intent summary route is under `/api/intents/control/` per the route convention, not added here |
| Entitlement switches | `sh_platform/entitlements.py` `Centre` line 48, `switches` line 202, `set_centre` line 259, `list_companies` line 193 | Existing, unchanged. No second flag is created |
| Control client | `ui/src/api/control.ts` (`setCentre`, `listCompanies`) | Existing; two functions added |
| Register page and route | `ui/src/pages/RegisterPage.tsx` lines 37 to 108 (search chip, `DataTable`, loading, refused and error states); `sh_platform/graph/register.py` `get_api_company_register` lines 145 to 152 | Reshaped: the table frame, search chip and four states are copied for Screen A. The register page has no CSV export today (searched `ui/src` for `text/csv`: only upload tests), so the CSV is New and built in the browser as spec 19 does |
| Viewer filtering | `sh_platform/profile/view.py` (`Viewer` line 27, `allows` line 38, `sees_area` line 79) | Reshaped: the new `admin` tier is added here |
| Company plane JSON read and write | `sh_platform/jsonfile.py` | Existing, used for `settings/*.json` |
| Run log | `sh_platform/agents/runs.py` `record` line 15 | Existing, used for cancel, download and save lines |
| Route permissions | `sh_platform/route_permissions.yaml` | Existing; new routes get lines |
| Top bar and `RoleGate` | `ui/src/App.tsx` 77 to 143, `ui/src/shell/roles.ts` | Existing; spec 14 owns the matrix |
| Areas and tagging | Spec 05 screens A, B and E | Reused, not rebuilt. This file links to them |
| Clock and overdue | Spec 07 screen D and its clock route | Reused. The admin list is the same data without the organiser filter |
| Counters and CSV approach | Spec 19 | Reused for the measure rules and the in-browser CSV |
| Type defaults | Spec 02 catalogue and spec 03 type settings | Reused; `modules/m1_intent/contracts/intent_types.yaml` does not exist yet (searched `modules/m1_intent/contracts`); the company override file is the one new thing |
| Check-in questions | Spec 38 | Owned there; not repeated here |
| Genuinely new | The admin tier in view.py, the four admin routes, the settings routes, the cancel route, the Control summary route, the Screens A to E layouts |  |

## Not in this feature

- Area and people tagging screens (05), the wider measures panel (19), the clock rules (07), the closure and ratings screens (09, 10), the permissions matrix itself (14).
- The Weekly check-in start questions and their wording (38).
- Editing, signing, rating, extending, reopening or deleting by either admin.
- Any content search across companies, or any cross-company ranking.
- Exports other than the register of closed intents.
- Per-area or per-organiser defaults.
- A company default for "affected people may read" (the organiser chooses at creation, ruling 4).
- Control's own audit view of what company admins did.

## Open questions

1. A-074 (for Nitin): the super admin may read intent existence through the kernel, one company at a time, with no copy in the control plane. Until it is approved Screen E shows only the centre switch.
2. Route names: this file puts all new API under `/api/intents/admin/...` and `/api/intents/control/...`, including the Control summary. Confirm with 14 and 05, which may name the existence route differently.
3. Defaults sit on the tab `?tab=defaults` of `/centre/intent/admin` because the brief lists no separate defaults route. Confirm, or add a route to the brief.
4. Should a company be allowed to set the default for "affected people may read" (organiser's switch default is off, ruling 4)? Not offered here.
5. Should the company admin be able to extend a time box or ask North to nudge an organiser? Not specified; this file allows neither.
6. Time box upper bound and whether a company may remove a stage default: no limit invented here; the field takes any whole number of one or more.
7. May a company change the Weekly check-in questions? Ruling 3 gives them to 38 and each organiser; this file shows a note only.
8. Does the unrated list wait for the rating window of 10 before an intent counts as unrated? Proposed: no wait, it lists any closed intent with no rating and shows the reminder state beside it.
9. Which Nira row (13) carries "N intents are overdue" to the company admin? A row must be added in 13.
10. Should the register CSV include the organiser's and sponsor's names? Proposed yes (they are named in the record the admin may read); drop them if Nitin prefers roles only.
11. Does a cancel by the admin notify participants too, or only organiser and sponsor? Proposed: organiser and sponsor only.
12. The rating mean shows from three ratings (ruling 8) while other means show "Fewer than five" below five records. Confirm the two thresholds are meant to differ.
13. Which intent types take a sponsor, so that "no named sponsor" is only counted for them (ruling 13)? Not given in the brief.
14. The overdue and at-risk reading of a recurring Weekly check-in series (a week is one week, the series has no end) is spec 07's open question; the admin lists follow whatever 07 decides.
15. The Weekly check-in row in the time box card is read-only; whether a company may change the week length is not decided.
