# 33. Build-ready check and hand-off to Build

Part of: Intent Centre v2. Depends on: 01 (intent record and lifecycle), 09 (closure and sign-off), 08 (North workflow runner), 19 (centre counters), 27 (process map), 28 (data sources and technical areas), 34 (who does what), the Initiative's other Define files (charter, glossary, catalogue, governed state). Feeds: Build centre (gap analysis as room 0), 04 (home page), 13 (Pulse lines), 19 (counters).

## Purpose (three sentences)

While an Initiative is in the `closing` state (entered at charter signature per spec 32), the build-ready check says whether Build has what it needs: a signed charter, a business glossary, a data catalogue, owners, and a named team. Nitin's rule: before any build you need a proper data catalogue plus a business glossary, and gap analysis is the first step of a build, not part of the Intent Centre. When every line passes, the organiser presses "Hand to Build", which writes `links.build` and opens the Build centre at room 0, the gap analysis (the Moment of truth, as built, moved and not rebuilt); when a build is not needed, the organiser closes the Initiative with the charter and glossary as its outcome and nothing is handed over.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | Define is nearly done, or North says the time box is ending | Opens the Build-ready panel; chases the missing lines; presses "Hand to Build" |
| Sponsor (Daniel) | The charter is waiting, or the closure waits for a signature | Signs the charter (existing); answers "Build needed"; reads the panel to see why closure is held |
| Analyst (Katie) | Definitions are drafted and need confirming | Follows a "Fix it" link from a line to the record |
| Business owner, data owner, source owner (Harvey) | A measure, process or source names them | Follows "Fix it" to confirm a definition, a process or a source |
| Architect, developer, tester (named in spec 34) | After hand-off | See the Build centre with their names against their steps |
| Affected person, observer | Any time | Affected: sees the chip and the verdict. Observer: reads what a participant reads, never writes (ruling 4) |
| North (agent) | Every write to a record the check reads; at the closing state | Recomputes the check, drafts the to-do, nudges the person whose turn it is |
| Lens (agent) | A line fails because a definition is missing | Drafts the missing definition for a person to confirm |
| Company admin | Any time | Reads the verdict and counters; cannot hand over unless named organiser |

## Entry points (every route, link, Pulse line, button that leads here)

- Panel "Build-ready" on the charter screen `/centre/intent/<id>/charter` (owned by spec 32; this file adds the panel).
- Panel "Build-ready" on the closure screen `/centre/intent/<id>/close` (spec 09, Initiative only; shown above the Outcome block).
- Full check page `/centre/intent/<id>/build-ready` (opened from either panel by "See every line").
- Intent page header chip "Build-ready: 5 of 7" (spec 01 owns the header; the chip links to the check page).
- Nira "waiting for you" line for the person whose turn it is: "Janet, 2 lines stop <Title> from being build-ready. Open the check."
- Pulse page line (spec 13): "<Title> is build-ready. Hand to Build." (organiser and sponsor only).
- Button "Hand to Build" on the check page, both panels and the closure footer (organiser only).
- After hand-off: Build centre home `/centre/build`, and directly `/centre/build/gap-analysis?from=<intent id>` (room 0).
- Build centre room 0 banner "Handed over from <Title> on <date>" with a link back to the closed or closing intent.

## Screens, element by element

### A. Build-ready check page

Route `/centre/intent/<id>/build-ready`.

Layout at 1280: top bar; header strip (title, type chip "Initiative", chip "Build-ready: n of 7", primary "Hand to Build" right aligned); two columns. Left, 8 of 12: the check list, one row per line, grouped under "Agreed on paper" (lines 1, 7), "Defined" (lines 2, 3), "Owned" (lines 4, 5, 6). Right, 4 of 12: "North's to-do" panel and "What happens next" card.

Layout at 390: one column: header strip with the chip and a sticky "Hand to Build" button (disabled until green); then North's to-do (collapsed to the first three items, "Show all"); then the check list as cards, one per line, the row detail folded under "Show what is missing"; "What happens next" last.

Every count on this screen is read from `build_ready.lines[]` on the intent record, which the server computes from the records named in the row evidence line. "Checked at <time>" is `build_ready.checked_at`, in the company's time zone from the profile, else UTC. "Waiting since <date>" is the event line in `intents/<id>/events.jsonl` where the line first failed.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Chip "Build-ready: n of 7" | chip | Count of lines that pass, `build_ready.lines[].ok` | Scrolls to the first failing line | Everyone who may open the intent content; area members and affected people (switch off) see this chip and the verdict only | "Not checked yet. North checks when Define has a charter draft." |
| Line 1 "Charter signed" | list row | Pass or fail; signer name, date and version from the charter outcome | "Fix it" opens the charter screen at the sign panel | Participants, observers, sponsor, people named on a share; affected only when "affected people may read" is on | Fail text: "The charter has no signature yet. Daniel signs it." |
| Line 2 "Every Must and Should measure has a confirmed business definition" | list row | `n of m` measures; failing measure names as chips | Chip opens that measure in the glossary at its term | As line 1 | "No measures are on the Must or Should shelf yet." (the line fails, never passes on zero) |
| Line 3 "... a confirmed technical definition, a catalogue entry and a governed state" | list row | Three sub-counts (technical, catalogue, governed) of `m`; each failing measure chip names which part is missing | Chip opens the catalogue row; the governed-state chip opens the six-field panel | As line 1 | Same empty text as line 2 |
| Line 4 "Every process has a confirmed business owner" | list row | `n of m` processes (status not removed) with a named owner who has confirmed the process, from spec 27 | Chip opens the process card (`?tab=process-map&process=<pid>`) | As line 1 | "The process map is empty. Draw it first." (fails) |
| Line 5 "Every data source has a confirmed source owner" | list row | `n of m` sources (not left out) whose source owner is named and has confirmed, from spec 28; restricted sources show "1 restricted source, counted" | Chip opens the source row in the Data sources tab | As line 1 | "No data sources are mapped yet." (fails, unless line 7 says build not needed) |
| Line 6 "Who does what: architect, developer, tester named" | list row | Three slots with the person's name, or "Not named"; read from the roles record of spec 34 | "Name them" opens spec 34's Who does what panel (no second form here) | Organiser edits there; others read | "Nobody is named for the build yet." |
| Line 7 "Build needed is answered yes" | list row | The recorded answer: Yes, No, or Not answered, with who answered and when | "Answer it" opens the "Do we need a build?" dialog | Organiser and sponsor answer; others read | "Not answered. Janet or Daniel answers this." |
| "Fix it" link | link | One per failing row; the destination record is named in the link text ("Fix it in the glossary") | Opens the owning record in the same tab, with a "Back to the check" chip at the top of that screen | Whoever may edit that record | Hidden on a passing row; a passing row shows "Open" instead |
| "Open" link | link | On a passing row | Opens the record read-only | As the row | n/a |
| "Back to the check" chip | chip | On the destination screen, after "Fix it" | Returns to `/centre/intent/<id>/build-ready` and triggers a recheck | Whoever arrived by "Fix it" | n/a |
| "Show what is missing" | button (link style) | At 390 only: unfolds the row's missing items | Unfolds or folds the row | As the row | Hidden on a passing row |
| Row evidence line | text | Record name, id and the time it was last read (`evidence.record, id, read_at`) | Opens the record read-only | As the row | Never empty; if the record cannot be read: "Not available yet: <record name> could not be read." |
| Turn chip on a failing row | chip | Whose turn it is: a named person and role ("Harvey, business owner") | Opens the person's card (no action) | Participants, observers | "No one is named yet" and North asks the organiser |
| North's to-do panel | agent line (list) | Ordered list of what is missing, one sentence each, with the named person, the "Fix it" link and "waiting since <date>" | "Nudge" on a row sends Nira's waiting line to that person (organiser only). A row leaves when the check passes; there is no "Done" button | Organiser, sponsor; named people see their own rows | Green state: "Nothing is missing. North checked at <time>." |
| "Show all" | button (link style) | Under the first three to-do items (at 390 and on panel B) | Unfolds the full to-do list | As the panel | Hidden when three or fewer |
| "Nudge" | button | On a to-do row | Sends the person a Nira "waiting for you" line; the row shows "Nudged <date>" | Organiser | Disabled with "No one is named yet" when the row has no person |
| "Do we need a build?" dialog | dialog | Two buttons "Yes, Build is needed" and "No, close with the charter and glossary"; a required reason line for No | Yes writes `build_needed: true`. No writes `build_needed: false` with the reason, then offers "Go to closure" | Organiser, sponsor | Not shown once answered |
| "Change answer" | link | Beside the recorded answer on line 7 | Reopens the dialog; sets `build_needed` back to null on save | Organiser, sponsor, while the intent is open | Hidden when not answered |
| "Go to closure" | button | After "No" is saved; replaces "Hand to Build" while `build_needed` is false | Opens `/centre/intent/<id>/close` | Organiser | Hidden otherwise |
| "Recheck now" | button | Secondary; then "Checked at <time>" | Forces North to recompute | Organiser | Always shown |
| "Hand to Build" | button | Primary. Enabled only when all 7 lines pass and `build_needed` is true | Opens the confirm dialog (journey step 9); on confirm writes `links.build` and navigates to `/centre/build/gap-analysis?from=<id>` | Organiser only (others see it disabled with "Only the organiser hands over") | Disabled with the first failing line named beside it ("Line 4 stops this: 2 processes have no confirmed owner") |
| Confirm dialog buttons "Hand to Build" and "Not yet" | button | The dialog text names the baseline version and source count read from the baseline record and the data sources record | "Hand to Build" confirms; "Not yet" closes the dialog and writes nothing | Organiser | n/a |
| "What happens next" card | panel | Two fixed sentences: what Build opens with and what the organiser still does on this side (close the intent) | None | Participants, observers | Never empty |

### B. Build-ready panel on the charter screen

Route `/centre/intent/<id>/charter` (panel added; the screen is owned by spec 32).

Layout at 1280: a side card under the signature panel. At 390: a collapsed card "Build-ready: n of 7" below the signature panel.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Panel header | panel | "Build-ready" and the chip count; green only at 7 of 7, otherwise neutral with a dashed ring | None | Participants, observers, sponsor, organiser | "Not checked yet." |
| Missing list | list | The first three items of North's to-do with the person's name | Item opens its "Fix it" target | Participants, observers | Green: "Build-ready. Nothing is missing." |
| "Show all" | link | Under the list | Opens the check page | As the panel | Hidden when three or fewer |
| "See every line" | button | Label | Opens `/centre/intent/<id>/build-ready` | Participants, observers | Always shown |

### C. Build-ready panel on the closure screen

Route `/centre/intent/<id>/close` (spec 09, Initiative only; panel added).

Layout at 1280: a full-width strip above the Outcome block. At 390: a collapsed strip under the header, expanded by tap on the strip header.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Strip | panel | Green at 7 of 7 and build needed: "Build-ready. Ready to hand to Build." Neutral when build needed is no: "No build needed. This Initiative closes with its charter and glossary." Otherwise "Not build-ready: n items missing" | Opens the check page | Participants, observers, sponsor, organiser | "Not checked yet." |
| Missing list | list | All of North's to-do with whose turn it is | As panel B | Participants, observers | Hidden when green |
| "Hand to Build" | button | Same button as page A | Same | Organiser | Disabled with the first failing line named |
| "Close without hand-off" | button | Secondary; shown when `build_needed` is false, or when the organiser chooses to close an incomplete Initiative | Opens spec 09's "Close with what we have" dialog, which records `closure.incomplete` and the unmet lines as reasons | Organiser | Hidden when green and build needed |

### D. Build centre room 0, gap analysis (existing Moment of truth, reached from Build)

Route `/centre/build/gap-analysis?from=<intent id>` (ruling 10). Layout and elements are the existing Moment of truth screens (trial, scan, source map, plan, accept); this file adds one banner and one strip above them.

Layout at 1280: the banner and the reads strip sit full width above the existing step list; the existing layout is unchanged below. At 390: the banner collapses to its first sentence with "Show more"; the strip wraps to two lines; the existing steps stack as they do today.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Hand-over banner | panel | "Handed over from <Title> on <date> by Janet. Charter signed by Daniel on <date>. <m> measures, <s> sources." Numbers read from `build_handoff.measure_count` and `source_count`; a line "Definition changed after hand-off" shows when the record carries that flag | "Open the intent" opens the intent read-only | People who may open the intent content | Not shown when the room is opened without `from` |
| "Show more" | link | At 390 only | Unfolds the banner | As the banner | Hidden at 1280 |
| Reads strip | chip row | "Reading: baseline version <n>, <s> sources", from `build_handoff.catalogue_version` and `source_count`, and the current baseline version beside it when they differ | Chip opens the catalogue or the data sources map | Build centre users | "Not available yet: no catalogue was handed over." |
| Step list | list | The existing steps: trial, scan, source map, plan, accept | Existing behaviour, unchanged | Build centre users | Existing empty states |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet opens the check page from the header chip "Build-ready: 2 of 7" on the intent page. Before that, North recomputed the check after every write to a record the check reads and posted the chip.
2. Daniel signs the charter (existing sign action). Line 1 passes. North drafts the to-do for the remaining lines, each with a named person, and sends Nira lines to those people.
3. Lens, seeing line 2 or 3 fail on a measure, drafts the missing business or technical definition or the governed-state fields into the m2 stores, marked "Drafted by Lens". A named owner confirms; only a confirmation counts toward the line.
4. Harvey opens "Fix it in the glossary" from his Nira line, confirms two definitions, and presses "Back to the check". North rechecks and the row moves from fail to pass. Harvey also confirms his process (line 4) and his source (line 5) through the same "Fix it" links.
5. Janet sees line 6 fail. She presses "Name them", which opens spec 34's Who does what panel; Katie is named architect, Aaron developer, Grace tester. Each person's answer is spec 34's. North rechecks.
6. Line 7 fails. Daniel presses "Answer it" and picks "Yes, Build is needed".
7. The chip turns green: 7 of 7. North writes "North checked at 14:05" and sends Nira's line "Hand to Build" to Janet.
8. Janet presses "Hand to Build".
9. A confirm dialog reads: "This opens Build with the gap analysis first. Build will read baseline version <n> and <s> sources. The charter stays signed and read-only. Hand over?" with "Hand to Build" and "Not yet".
10. On confirm, the server writes `links.build`, `build_handoff` and an event line, freezes the check result as the hand-over record, and opens `/centre/build/gap-analysis?from=<id>`.
11. In Build, the Moment of truth runs its own steps. Nothing about the gap analysis is written on the intent record except the reference.
12. Janet leaves Build and returns to the intent (in `closing` per spec 32; the hand-off is not a closure). She then closes the intent through spec 09, moving it to `closed`, with a summary and signature. She leaves when closed.

Branch, build not needed: at step 6 Daniel picks "No, close with the charter and glossary" and writes a reason. Line 7 passes as "answered no". Lines 4 and 5 stop being required (see Rules). The Hand to Build button is replaced by "Go to closure". North drafts the closure with the charter and glossary as the outcome. No `links.build` is written.

## States and transitions (table: state, who moves it, to what, what is written)

The check has its own small state, held on the intent record. It does not change the intent's `state`; specs 01 and 09 own that.

| Check state | Who moves it | To what | What is written |
|---|---|---|---|
| `not_checked` | North, on the first charter draft | `incomplete` | `build_ready.lines[]`, `build_ready.checked_at` |
| `incomplete` | North, after any write to a read record, or "Recheck now" | `incomplete` (counts change) or `ready` | Same fields; event line only when the verdict changes |
| `ready` | North, when 7 of 7 pass and `build_needed` is true | `incomplete` if any record changes so a line fails again (for example a definition is reopened) | Same fields; event line "Build-ready lost: line 3" |
| `ready` | Organiser, "Hand to Build" | `handed_over` | `links.build`, `build_handoff`, frozen `build_ready.lines[]`, event line |
| `incomplete` or `ready` | Organiser or sponsor, answers "No" on build needed | `not_needed` | `build_needed: false`, `build_needed_reason`, `build_needed_by`, `build_needed_at` |
| `handed_over` | Nobody | Terminal for this feature | Nothing further; the Build centre owns what follows |
| `not_needed` | Organiser or sponsor, "Change answer" (while the intent is open) | `incomplete` | `build_needed` back to null, event line |

An intent that reaches `closed` while `incomplete` carries `closure.incomplete = true` (spec 09) and the unmet lines in its reasons. It can still be handed over later through a follow-up Initiative (`closure.next`) whose `links.from` points here; the old intent is not reopened.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Read or written | Fields used | Existing or New |
|---|---|---|---|
| `intents/<id>/intent.json` (spec 01; ruling 12) | Read, written | `refs`, `people`, `links`, `state`, plus the fields below | Existing; fields New |
| `intents/<id>/events.jsonl` (spec 16) | Written (event lines), read (first-failed date) | verdict changes, hand-off, answers | Existing (spec 16 owns it) |
| Charter and signature, `GET /api/modules/m1_intent/sessions/{session_id}/charter`, outcome via `GET /api/modules/m1_intent/outcomes/{outcome_id}` | Read | signed flag, signer, signed_at, version, measures per problem, shelf | Existing |
| m2 glossary, `GET /api/modules/m2_baseline/baselines/{baseline_id}/glossary` (`domain/glossary.py`) | Read | term, business definition, state (drafted or confirmed), confirmed_by | Existing |
| m2 technical definitions (`domain/technical.py`) | Read | source, fields, calculation, period, currency, confirmed state | Existing |
| m2 catalogue, `GET /api/modules/m2_baseline/baselines/{baseline_id}/catalogue` (`domain/catalogue.py`) | Read | one row per measure present; baseline version | Existing |
| m2 governed state (`domain/governed.py`, `is_complete`, six fields, A-054) | Read | six provenance cells per measure, including the owners cell (business, data) | Existing |
| `intents/<id>/processes.json`, `GET /api/intents/{id}/processes` (spec 27) | Read | `processes[].status`, `owner.value`, `confirmed`, `removed` | New (spec 27) |
| `intents/m2_baseline/<baseline_id>/data_sources.json`, `GET /baselines/{id}/data-sources` under the m2_baseline module prefix (spec 28) | Read | `sources.<Source ID>.source_owner` cell, `left_out`, catalogue `Confirmed by` | New (spec 28) |
| Roles record `intents/m1_intent/roles/<session id>.json`, `GET /api/modules/m1_intent/sessions/{id}/roles` (spec 34) | Read | `roles.architect`, `roles.developer`, `roles.tester` | Existing; extended by spec 34 |
| Company profile, `sh_platform/profile/view.py` | Read | people list; systems list | Existing |
| `GET /api/intents/<id>/build-ready` | Read | the computed check result, each line with its record link | New |
| `POST /api/intents/<id>/build-ready/recheck` | Written | recomputes and stores `build_ready` | New |
| `PUT /api/intents/<id>/build-needed` | Written | `build_needed`, reason, by, at | New |
| `POST /api/intents/<id>/handoff` | Written | `links.build`, `build_handoff`, event line | New |
| Build centre, `GET /api/company/build/home` (`sh_platform/build/home.py`) | Read | room states; add room 0 and `handed_over_from` | Existing; fields New |
| m3 assessment, `POST /assessments` (`modules/m3_connect/api/assessment.py`) | Written by Build, not this file | the assessment is created in Build when gap analysis starts, seeded from `refs` | Existing |
| m3 steps (`domain/steps.py`) and routes `trial`, `sources`, `plan`, `outcome` | Read by the Build room | unchanged | Existing |

Route permissions: every new route needs a declaration in `sh_platform/route_permissions.yaml` (default deny). Roles: GET for participants, observers and the company admin; recheck and handoff for the organiser only; build-needed for the organiser and sponsor. The chip and verdict alone are served to area members and affected people (switch off) through the same GET, cut by `sh_platform/profile/view.py`.

## Fields this feature adds to the intent record

Initiative only. Unknown fields stay refused on other types. None of the brief's section 3 fields is renamed. The team is not a field here: spec 34's roles record holds it and the intent keeps a reference only.

| Field | Type | Why | Written by |
|---|---|---|---|
| `build_needed` | `true`, `false` or null | Line 7; decides hand-off or no hand-off | Organiser or sponsor, via the dialog |
| `build_needed_reason`, `build_needed_by`, `build_needed_at` | string, person object, ISO time | Reason required when false; who and when for either answer | Server |
| `build_ready` | `{state: not_checked\|incomplete\|ready\|handed_over\|not_needed, checked_at, lines: [{key, ok, count, of, missing: [{kind, ref, label, turn_of}], evidence: {record, id, read_at}}]}` | The last computed check; each line carries the record it traced to | North, through the server; never edited by hand |
| `build_handoff` | `{by, at, charter_outcome_id, catalogue_version, source_count, measure_count, lines_frozen: [...]}` or null | The frozen hand-over record; Build reads it, the intent keeps it | Server, on "Hand to Build" |
| `links.build` | ref string `build:<assessment_or_intake_ref>` | Already in the brief; this file is the only writer | Server, on "Hand to Build" |

`links.build` is the pointer to Build and is set only through "Hand to Build". It never holds a copy of the catalogue. The intent record holds counts only for history (ruling 12); every change is an event line.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** computes the check from records after every write to one of them. It drafts the to-do list (one sentence per missing item, with the person whose turn it is, taken from the record's owner, or the organiser when no one is named), orders it by what blocks most, and nudges on the schedule spec 07 and spec 08 set for the stage clock; this file adds no timing of its own. It writes `build_ready` and the event line. North never sets `build_needed`, never names the team, never presses "Hand to Build". At the closing state it adds the build-ready verdict to the closure draft.
- **Lens** drafts any definition a line asks for: business definition, technical definition, catalogue entry, governed-state fields. A Lens draft shows on the line as "Drafted, not yet confirmed" and does not count. Team suggestions are spec 34's.
- **Nira** turns each row of North's to-do into a "waiting for you" line for the person named, and a Pulse line "Build-ready: <Title>" to the organiser and sponsor when the check turns green. Nira writes nothing here.
- **People act at named moments:** Daniel signs the charter; the business owner confirms a process, the source owner confirms a source, owners confirm definitions; Janet names the team (spec 34) and presses "Hand to Build"; Janet or Daniel answers "Build needed".
- The questions Lens raises to people stay inside the cap of three open per person across Define (A-045); this file raises none.

## Rules (visibility, time box, who may do what)

- A line passes only when every item it covers is confirmed by a named person. A Lens draft, an empty list, or a measure with no confirmation never passes. Zero measures fail lines 2 and 3.
- "Every Must and Should measure" means every measure on the Must or Should shelf of the signed charter. Good to have and Future measures are not checked.
- A measure counts as defined for line 3 only when its governed state is complete under `modules/m2_baseline/domain/governed.py::is_complete` (all six confirmed; the review date is a default and counts as confirmed).
- Three owner kinds are kept apart (ruling 11): line 4 reads the business owner of each process (the "process owner" of the governed state is the same person), line 5 reads the source owner of each source, and the data owner is read inside line 3 through the governed state. The screen never merges them into one "Owner" label.
- When `build_needed` is false: lines 4 and 5 are shown as "Not required: no build" and the other lines still show their state but never block closure. The charter signature (line 1) is still required to close a successful Initiative; the glossary lines still show their counts as the outcome.
- Only the organiser presses "Hand to Build". The sponsor and company admin see the button disabled with "Only the organiser hands over".
- The charter stays signed and read-only after hand-off (rule 7). Reopening a definition after hand-off is allowed through the owning record, flags the hand-over record with "Definition changed after hand-off" and does not change `links.build`. Build reads the current baseline and shows the difference against `catalogue_version` in the banner.
- A hand-off cannot be withdrawn here. Build owns what follows; if Build is wrong the organiser opens a new Initiative linked from this one.
- Time box: the check adds none. If North judges the intent will not be build-ready inside its time box, it proposes extend, close with what we have, or cancel through spec 09.
- Visibility (rulings 4 and 5): participants, observers and the sponsor see the whole check. An affected person sees the chip and the final verdict, and the whole check only when the organiser switched on "affected people may read" at creation (default off) or named them on a share. Area members see the chip count and the final verdict. The super admin sees that the intent exists and nothing of the check. The company admin sees the verdict and counts, never anonymous notes. Sealed material is not named on a line: a sealed measure shows "1 sealed measure, counted".
- A draft intent is visible only to the person who started it (ruling 14); no check is shown to anyone else until the intent opens.
- Each person sees only what is for them: an owner sees their own rows in Nira's list; they open the full check only when the rules above allow it.
- Every line must name its record. A line that cannot read its record fails and says "Not available yet: <record> could not be read."
- No thresholds are invented. The check is all-or-nothing per line.

## Counters and measures of this feature (numbers only, each traced to a record)

Counts are exact. Days are calendar days in the company's time zone from the profile, else UTC. A median, a range or any mean shows "Fewer than five" below five records (ruling 8).

| Counter | Definition | Traced to | When not available |
|---|---|---|---|
| Build-ready charters | Count of Initiatives whose `build_ready.state` is `ready` or `handed_over`, as a count and as a share of Initiatives with a signed charter | `intents/*/intent.json`, `build_ready.state` | "Not available yet: no Initiative has a signed charter." |
| Days from signed charter to hand-off | Days from the charter's signed_at to `build_handoff.at`, per Initiative; the centre shows the median and the range | Charter outcome `signed_at`, `build_handoff.at` | "Not available yet: no Initiative has been handed over." Below five hand-overs: "Fewer than five" |
| Lines failing most often | For open Initiatives, how many currently fail each of the 7 lines | `build_ready.lines[].ok` | "Not available yet: nothing has been checked." |
| Initiatives closed with no build | Count where `build_needed` is false and state is `closed` | `intents/*/intent.json` | "None yet." |
| Hand-overs with later definition changes | Count of `build_handoff` records flagged "Definition changed after hand-off" | `build_handoff` flag | "None yet." |
| Days waiting on the person | For each failing line, days since the line first failed, grouped by role of the person whose turn it is; shown only for groups of five or more | `intents/<id>/events.jsonl`, `build_ready.lines[].missing[].turn_of` | "Not available yet." |

No per-person figure is shown (ruling 8). These feed spec 19 (centre counters) and the Build centre's own outcomes page (time to first matching measure starts from `build_handoff.at`).

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `graft ask "gap analysis trial scan source map plan accept" --source`, `graft ask "catalogue glossary governed state is_complete" --source`, `graft ask "build centre home rooms" --source`, `graft skeleton modules/m3_connect/api/<file>.py` for assessment, trial, sources and plan, `graft skeleton` for the m1, m2 and m3 domain files below, and a read of `route_permissions.yaml`, the m1 and m2 manifests, and specs 27, 28 and 34. All paths below were checked present.

| What exists | Where (lines from graft) | Decision | Why |
|---|---|---|---|
| The gap analysis as built: trial, scan, source map, plan, accept | `modules/m3_connect/api/assessment.py` (`create_assessment` L73-L76, `get_assessment` L81-L88); `api/trial.py` (`run_trial` L115-L134, `check_rule` L146-L166); `api/sources.py` (`get_map` L80-L82, `put_override` L109-L124); `api/plan.py` (`sign` L261-L269, `outcome` L289-L298); `domain/steps.py` (`steps_for` L27-L34); `domain/accept.py` (`is_signed` L56-L58); `domain/trial.py`, `domain/sources.py`, `domain/plan.py`; `contracts/trial.yaml`, `plan.yaml`, `scoring.yaml` | **Existing and moves**: not rebuilt, not copied, no code changed. Only its entry point changes: it is reached from Build as room 0 (ruling 10), seeded from `links.build` and `refs` | Nitin: gap analysis is the first step of a build. The Moment of truth screens stay as built |
| Build centre spec | `docs/specs/BUILD-CENTRE-SPEC.md` (inputs section) | Reused: the hand-off is the "signed inputs" step. Request A-075 amends it to place gap analysis as room 0 | Ruling 10 |
| Build centre screen and home | `ui/src/pages/BuildCentre.tsx` (`BuildState` L14, `useLoad` L27, `Room` L53, page L66-L110), `sh_platform/build/home.py` (`build` L42-L88, route L90) | Reshaped via graft: add room 0 "Moment of truth" ahead of "Architect your design" and one banner; reuse `BuildState`, `useLoad`, `Room`, `PageFrame`, `SideCard`, `Chip` as they are | Same components, one more room. No new page |
| Charter and signature | `modules/m1_intent/api/charter.py` (`charter_view` L97-L130), `domain/charter.py`, `domain/handoff.py` (`build_outcome` L33) | Reused: line 1 reads the existing signed flag and outcome | Signing is built; the check only reads it |
| m2 glossary, technical definitions, catalogue, governed state, sign-off gate | `modules/m2_baseline/domain/glossary.py`, `technical.py` (`missing` L56-L59, `present` L48-L49), `catalogue.py` (`contract` L55-L63, `with_review` L255), `governed.py` (`is_complete` L53-L56, `percentages` L57), `gate.py` (`check` L47-L60), `handoff.py` | Reused: lines 2 and 3 read these. `gate.py::check` is the nearest existing readiness gate for m2; the build-ready check has a wider scope, so it is not forced into `gate.py` | `gate.py` answers "is the baseline signable"; this answers "can Build start" |
| Process map, sources map | Specs 27 and 28 (`intents/<id>/processes.json`; `data_sources.json`); `modules/m2_baseline/domain/process_map.py` (`from_technical` L194) is the v1 per-measure map | Reused through 27 and 28: line 4 reads `processes[].owner` and `confirmed`; line 5 reads `source_owner`. The v1 `process_map.py` is not read | Field names confirmed against 27 and 28 |
| Who does what | `modules/m1_intent/domain/roles.py`, `api/roles.py` (spec 34); `sh_platform/build/uat.py` (`_tester` L44-L45, sign route L48) | Reused: line 6 reads `roles.architect`, `developer`, `tester`; Build's UAT already reads the charter tester. No second form here | Spec 34 owns the roles record |
| Signature panel, Chip, card, side card, empty state | `ui/src/design` | Reused as they are | Design system |
| Atomic JSON write and per-viewer filter | `sh_platform/jsonfile.py`, `sh_platform/profile/view.py` | Reused | Brief section 3 |
| Pulse and "waiting for you" lines | `sh_platform/pulse/` | Reused through spec 13 | North and Nira lines are drafted in the shared way |
| The check evaluator (seven rule functions over record reads) | none found | New: one module in the Intent Centre package, about seven small functions, one per line, each returning ok, count, of, missing and evidence | No existing build-readiness check across intent, baseline and sources. Searches above returned only m2's sign-off gate and m3's plan gate |
| `build_needed` | none found | New field | Nitin's flow needs the answer recorded |

## Not in this feature

- The gap analysis itself, its screens, its scoring, its plan and accept steps (Existing in m3_connect, owned by Build).
- Environment check, blueprint, pipelines, release, Ops manager (Build centre spec).
- Drafting definitions, the glossary, the catalogue, the process map and the sources map (Define files 27 to 31).
- Naming and accepting the team (spec 34).
- The closure screen, signature and ratings (specs 09 and 10); this file adds only a panel to spec 09's screen.
- Withdrawing a hand-off or reopening a build from the Intent side.
- Non-Initiative types: Brainstorm, Weekly check-in, Problem and Decision have no build-ready check.
- Any threshold such as "90 per cent defined"; the check is all-or-nothing.

## Open questions

1. Settled by ruling 10: gap analysis is room 0 of the Build centre. Pending request A-075 to amend `BUILD-CENTRE-SPEC.md`.
2. Line 4 reads a process as passing when its owner is named and has confirmed it. Spec 27 (open question 3) proposes only "every process has an owner" plus a recorded "no processes involved" for an empty map, and has no field for that record. Which applies? Here an empty map fails.
3. Line 5 passes on a named, confirmed source owner. Spec 28 (open question 3) leaves open whether all three owners are needed per source. Here only the source owner is required; the data owner is checked inside line 3.
4. What does "catalogue version" mean? The m2 catalogue carries no version number of its own; `build_handoff.catalogue_version` is read from the baseline sign-off version (m2 handoff `version`). Confirm, or name the field.
5. When `build_needed` is false, do lines 4 and 5 ("Not required") count in the chip "n of 7"? Written here as counting as passed; confirm.
6. Does line 6 pass when the three people are named, or only when each has accepted (spec 34 answer states)? Written here as named and not declined; confirm.
7. Is the tester one person or many? Build's UAT reads one `roles.tester` today. One person per role here; per-measure testers later.
8. Is a signed charter required when `build_needed` is false? Here yes, so the outcome is signed.
9. Should a hand-off be blocked when a Must measure is left out in the m2 sign-off gate? Here left-out measures leave the shelf before the check counts them.
10. May a company admin who is not the organiser hand over when the organiser has left? Here no; the company admin first reassigns the organiser through spec 06.
11. Should the Build banner update automatically when definitions change after hand-off, or only show the difference against `catalogue_version`? Here the difference only.
12. Spec 34 uses the route `/centre/intent/<id>/roles`, which is not in the ruling 1 view list. "Name them" opens the charter screen's panel here until the list is confirmed.
13. Spec 19 (M08) reads `outcome.build_ready`; this file writes `build_ready.state` and `build_handoff`. Which does 19 read?
14. The sources map route prefix is assumed to be `/api/modules/m2_baseline` (spec 28 declares `modules/m2_baseline/api/data_sources.py`). Confirm.
