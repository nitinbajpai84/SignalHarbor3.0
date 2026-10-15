# 56. Data-backed opportunities

Part of: Intent Centre v2. Depends on: 04 (home), 05 (areas and visibility), 19 (centre measures), 21 (backlog), 22 (Initiative start), 25 (suggestion cards), 38 and 40 (weekly check-in weeks and review), 55 (data knowledge map), Build centre room 3 Ops (`sh_platform/build/ops.py`). Feeds: 04, 13 (Pulse lines), 19, 21, 22.

## Purpose (three sentences)

The ops manager should not only keep today's runs going; the records the Watcher already reads also show patterns that deserve an Initiative, such as a measure that keeps drifting on one portfolio or the same reconciliation step coming up in the weekly check-in week after week. This feature lets the Watcher draft an opportunity from those records, lets Lens and the business analyst add or dispute evidence, and lets North judge whether it merits an Initiative and say why. The result is a dashed suggested Initiative on the Intent home and the backlog, which only a person may pick up; no agent ever opens an intent (ruling 32).

## Who uses it and when (role, moment, trigger)

| Role (Ardmore demo) | Moment | Trigger |
|---|---|---|
| Harvey, ops manager (role `owner`) | Daily, on the Ops page; when North has judged an opportunity | "Opportunities" panel on `/centre/build/ops`; Pulse line "North suggests an Initiative from the records" |
| Katie, business analyst (role `analyst`) | When an opportunity is noticed in her areas | Pulse line "The Watcher noticed a pattern. Add or dispute evidence"; the panel on the Intent home |
| Janet, organiser | Browsing the Intent home or backlog | Dashed card "Suggested by North from the records" in an area lane |
| Harvey or Katie | Any time they see something the Watcher has not | Button "Raise an opportunity" on either panel |
| Company admin | Checking the counters | Counters strip on the backlog's opportunity panel |
| Super admin | Never | No route (05, ruling 5) |

The Watcher notices, Lens adds evidence, North judges. Katie disputes or adds evidence; Harvey picks up, parks or dismisses.

## Entry points (every route, link, Pulse line, button that leads here)

- Build centre Ops page `/centre/build/ops` (existing `ui/src/pages/OpsPage.tsx`): new panel "Opportunities", each row links to `/centre/intent/backlog?opportunity=<id>`.
- Intent home `/centre/intent` (04): new panel "Opportunities from the records" for organiser roles and analysts; dashed suggested cards in the area lanes.
- Backlog `/centre/intent/backlog` (21): dashed suggested cards at the top of the list; status chip "Suggested"; panel at `?opportunity=<id>` (ruling 18).
- Pulse line (Nira, kind `decision`) to the analysts of the touched areas: "The Watcher noticed a pattern on <measure or process>. Add or dispute evidence." href `/centre/intent/backlog?opportunity=<id>`.
- Pulse line (Nira, kind `decision`) to the ops manager: "North suggests an Initiative from the records: <title>." Same href.
- Button "Pick it up" leads to `/centre/intent/new?type=initiative&from=<opportunity id>` (ruling 1 route, 22).
- API (New): `GET /api/intents/opportunities`, `GET /api/intents/opportunities/<id>`, `POST /api/intents/opportunities` (raise by hand), `POST /api/intents/opportunities/<id>/evidence`, `/dispute`, `/pick-up`, `/park`, `/dismiss`, `/bring-back`.

## Screens, element by element

### Screen A. "Opportunities" panel on the Ops page

Route: `/centre/build/ops` (existing, `ui/src/App.tsx` L115). One new card in the main column under the alerts list (`OpsPage.tsx` L156-L157), before the run book.

Layout at 1280: full-width card in the main column; rows of one line each; the "Raise an opportunity" button on the card header. Layout at 390: one stacked card per opportunity; the state chip moves above the title; the button goes full width under the card title.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Card title "Opportunities" | heading | Fixed, with sub-line "Patterns the Watcher found in the run log, alerts, feeds and check-ins" | None | `company_admin`, `analyst`, `owner` (open question 9) | Always shown |
| Opportunity row | list | Title, state chip, the measure or process it touches, periods covered ("4 Mondays", "3 month-ends"), noticed by ("The Watcher" or a person) and date | Opens `/centre/intent/backlog?opportunity=<id>` | As above, filtered by areas and restricted measures (Rules) | See empty line |
| State chip | chip | Noticed, Under review, Proposed, Picked up, Parked, Dismissed (words, never colour alone) | None | As above | None |
| Evidence count | text | "3 evidence lines" from `evidence[]` length | None | As above | "No evidence yet" |
| Button "Raise an opportunity" | button | Fixed | Opens the raise sheet (Screen C, "Raise" form) | `owner`, `analyst` | Always shown to them |
| Link "See all on the backlog" | link | Fixed | `/centre/intent/backlog?status=suggested` | As above | Hidden when there are none |
| Empty line | text | "Nothing noticed yet. The Watcher looks for patterns across run days, alerts, feeds and check-in weeks." | None | As above | This is the empty state |

### Screen B. "Opportunities from the records" panel on the Intent home

Route: `/centre/intent` (04). A panel between the "Your turn" strip and the filter row; the dashed card also sits in each area lane it touches.

Layout at 1280: panel full width, up to three rows then "Show all (n)"; dashed cards take a normal card slot (width 280) at the end of their lane. Layout at 390: panel collapses to one line "Opportunities (n)" that expands; dashed cards are full-width rows at the end of the lane list.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Panel title "Opportunities from the records" | heading | Fixed, count of open opportunities (states noticed, under review, proposed) the viewer may see | None | Organiser roles (`company_admin`, `sponsor`, `analyst`, A-025) and `owner` | Panel not drawn when n is 0 |
| Row | list | Title, state chip, North's one-line judgement once written | Opens Screen C | As above | None |
| "Show all (n)" | link | Count as above | `/centre/intent/backlog?status=suggested` | As above | Hidden under four rows |
| Suggested Initiative card | card, dashed border, no state pill | Title, type chip "Initiative", label "Suggested by North from the records", areas, North's confidence in words | Opens Screen C | Anyone tagged to an area it touches who may see every measure it names (Rules) | Not drawn unless state is `proposed` |
| Card label | chip | "Suggested by North from the records" | None | As card | Never empty |

### Screen C. Opportunity panel on the backlog

Route: `/centre/intent/backlog?opportunity=<id>` (ruling 18: a panel on the backlog view, same drawer frame as file 21 Screen B).

Layout at 1280: right panel 480 px over the backlog list. Regions: header (title, state chip, areas), "What was noticed", "Evidence", "North's judgement", "Proposed start answers", history, sticky footer of actions. Layout at 390: full-screen sheet with Back; regions stack; footer shows the first allowed action, the rest under "More".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Title | field (text) | Drafted by the Watcher, editable by `owner` and `analyst` while not picked up | Saves on blur; history line | As Screen A, per Rules | Required; "A title is needed." |
| State chip | chip | Current `state` | None | As above | None |
| "What was noticed" | agent line + list (Watcher) | The pattern in one sentence and one row per number, each with its trace: run log row, alert id, week item, feed value or graph edge (open question 3 for drift length) | Each trace link opens its record: alert on `/centre/build/ops`, week on `/centre/intent/<id>/week?week=<week_key>`, measure on `/centre/intent/map/<node id>` | As above; a number on a restricted measure is replaced by "A restricted measure" | "The Watcher found no numbers for this. It was raised by <name>." |
| Touches | chip group | Measures (pack `kpi_tree` id and name), processes and sources | Chip opens the node page on the map (55) | As above | "Nothing named yet" |
| Evidence list | list | One line per `evidence[]` row: text, source record link, added by (Lens, the Watcher, or a person), kind (supports or disputes), date | Link opens the source record | As above | "No evidence yet. Lens adds definitions and owners once noticed." |
| Button "Add evidence" | button | Fixed | Sheet: text (required), source record picker (alert, run day, week item, map node, document on a shelf), kind supports or disputes | `analyst`, `owner` | Always shown to them while not picked up or dismissed |
| Button "Dispute" | button | Fixed | Sheet: reason (required), optional source record; writes an evidence line of kind `disputes`; North re-judges | `analyst` | Hidden after pick up or dismiss |
| "North's judgement" | agent line (North) | Fits an Initiative: Yes or No; why, in two or three sentences; confidence in words ("Fairly sure", "Not sure", "Unlikely") | None | As above | "North has not judged this yet. It waits for Lens's evidence." |
| "Proposed start answers" | list | The six file 22 questions (`goal`, `people`, `build`, `definitions`, `areas`, `deadline`) with North's draft each, every one marked "Guessed by North" | None (edited only in the start flow) | As above | "North drafts these when it judges Yes." |
| Button "Pick it up" | button (primary) | Fixed | Writes `picked_up_by`, then opens `/centre/intent/new?type=initiative&from=<id>` with the answers pre-filled, mark `guessed` | `owner` (open question 6 for organiser roles) | Disabled until North has judged; hidden after pick up |
| Button "Park" | button | Fixed | Sheet: reason (required), review date (native date input, required) | `owner` | Hidden when parked, picked up or dismissed |
| Button "Dismiss" | button | Fixed | Sheet: reason (required) | `owner` | Hidden when picked up or dismissed |
| Button "Bring back" | button | On parked or dismissed | Sets state `under_review`; North re-judges | `owner` | Hidden otherwise |
| "Became" link | link | The Initiative opened from it, its title and state | Opens `/centre/intent/<intent id>` | As above, and only if the viewer may see that intent exists | Hidden until an Initiative carries `links.from` to this id |
| "Did the measure move" | text | From file 19's measures | None | As above | "Not available yet: file 19 has no measure of movement after an Initiative" |
| History | list | One row per state change and evidence line: who, what, when | None | As above | Never empty (the first row is "Noticed") |
| "Raise" form (sheet) | panel | Fields: title, what you noticed (text), touches (measure and process pickers from the pack and the map), areas, first evidence line with a source record | "Raise it" writes a new record, state `noticed`, `noticed_by` the person | `owner`, `analyst` | "Name at least one measure, process or source." blocks Raise it |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

Illustrative, synthetic Ardmore figures.

1. Over several Mondays the Watcher's daily read (`_build_open`, `ops.py` L77-L119) raises the alert `custodian_prices:late` for the custodian price file, and the Ops page shows it each time. Harvey acknowledges it each Monday.
2. Between runs, the Watcher reads `build/alerts.json`, `warehouse/runs.json`, feed values and range breaks, the Operations check-in week files and graph edges. It sees four late Monday arrivals for one source, three check-in items of kind `broke` saying the Monday price reconciliation was redone, and K12 Stale-valuation share rising at three month-ends on one portfolio. The graph links the source to `val_date`, which feeds K12. It writes `intents/opportunities/opp-0007.json`, state `noticed`, with every number traced.
3. Nira writes the Pulse line to Katie, analyst for Operations. Lens adds evidence lines: K12's pack definition (labelled a suggestion), the source owner from the pipeline contract, and the process step from the process map (27). State moves to `under_review`.
4. Katie opens the panel from Pulse. She clicks "Add evidence": "The reconciliation sheet shows the same manual price override each Monday", linked to the week item. She leaves.
5. North reads the record and judges: "Yes, fits an Initiative. The late file, the manual step and the drifting measure cross a source contract, a process step and a reported measure, which is more than one fix. Fairly sure." It drafts the six start answers (goal, people Harvey and Katie, build "not sure", definitions "some", area Operations, deadline the default end) and moves the state to `proposed`. A dashed card appears in the Operations lane on the home and at the top of the backlog. Nira writes the Pulse line to Harvey.
6. Janet sees the dashed card on the home and opens it. She reads it; she cannot act on it (open question 6). She leaves.
7. Harvey opens the panel and clicks "Pick it up". The start flow opens with the six answers pre-filled, each "Guessed by North". He edits the goal and confirms. File 22 writes the intent with `links.from: "opportunity:opp-0007"`; the opportunity state becomes `picked_up` with `became: <intent id>`.
8. Alternatively Harvey clicks "Park" with reason "Wait for the custodian contract renewal" and a review date, or "Dismiss" with a reason. Katie could instead have clicked "Dispute"; North then re-judges and may move the state back to `under_review` with judgement "No".
9. Harvey leaves from the start flow or the panel.

## States and transitions (table: state, who moves it, to what, what is written)

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | The Watcher, or Harvey or Katie by "Raise it" | `noticed` | New `intents/opportunities/<id>.json`; history row; `noticed_by` |
| `noticed` | Lens adds its first evidence line, or a person adds one | `under_review` | `evidence[]` row; history row |
| `under_review` | North judges Yes | `proposed` | `judgement` with `fits: true`, `why`, `confidence`, `start_answers` |
| `under_review` | North judges No | stays `under_review` | `judgement` with `fits: false`, `why`; Harvey may dismiss or park |
| `proposed` | Katie disputes | `under_review` | `evidence[]` row kind `disputes`; North re-judges |
| `proposed` | Harvey, "Pick it up" | `picked_up` | `picked_up_by`, `picked_up_at`; on intent creation `became: <intent id>` |
| `noticed`, `under_review` or `proposed` | Harvey, "Park" | `parked` | `parked: {by, at, reason, review_date}` |
| `noticed`, `under_review` or `proposed` | Harvey, "Dismiss" | `dismissed` | `dismissed: {by, at, reason}` |
| `parked` or `dismissed` | Harvey, "Bring back"; or the review date arrives (Nira reminds, nothing moves by itself) | `under_review` | History row |
| `picked_up` | Nobody | final | Nothing is deleted |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Read or written | Mark |
|---|---|---|---|
| `intents/opportunities/<id>.json` via `sh_platform/jsonfile.py` (`lock_for`, `write_json_atomic`) | `{id, title, state: noticed\|under_review\|proposed\|picked_up\|parked\|dismissed, noticed_by: "watcher"\|account id, noticed_at, areas: [], touches: {measures: [kpi id], processes: [id], sources: [id]}, pattern: {text, periods: [period], numbers: [{label, value, unit, trace: {kind: run\|alert\|week_item\|feed\|range_break\|edge, ref, at}}]}, evidence: [{id, text, kind: supports\|disputes, source: {kind, ref}, by: "lens"\|"watcher"\|account id, at}], judgement: {fits, why, confidence: fairly_sure\|not_sure\|unlikely, start_answers: {goal, people, build, definitions, areas, deadline}, at}\|null, picked_up_by, picked_up_at, became: intent id\|null, parked: {by, at, reason, review_date}\|null, dismissed: {by, at, reason}\|null, history: [{at, by, action, note}]}` | Written by the Watcher, Lens, North and the routes; read per viewer | New |
| `warehouse/runs.json` (SHAPES section 4) | `source`, `started`, `ended`, `status`, `on_time`, `rules[]` | Read | Existing |
| `build/alerts.json` (`sh_platform/build/alerts.py` L1-L2 shape) | `id`, `kind`, `source`, `measure`, `owner`, `opened`, `state` | Read | Existing |
| `build/pipelines/*.json` | `source`, `owner`, `marts` | Read | Existing |
| `GET /api/company/feeds` (`sh_platform/consume/feeds.py` L103-L104) and `range.trend`, `range.breaks` (`sh_platform/consume/range.py` L17-L45) | measure values by period, break verdict and basis | Read | Existing |
| `intents/<id>/weeks/<week_key>.json` (ruling 17) | `items[].kind`, `text`, `fate`, `ref` | Read, Operations series only for the touched areas | Existing shape (38) |
| `graph/company.json` via `sh_platform/graph/read.py` | edges `fed_by`, `held_in`, `produces`, `owned_by` (55) | Read | Existing, edges widened by 55 |
| `packs/family_office/1/kpi_tree.yaml` through the pack loader | `id`, `name`, `definition`, `unit` (K12 at L150-L162) | Read; labelled "what others in the industry usually track" | Existing |
| `intents/<id>/intent.json` (01, 22) | `links.from` set to `opportunity:<id>`; `start_answers` marks `guessed` | Written by the start flow, never by an agent | Existing record, new link value |
| `intents/backlog.json` (21) | none written; the backlog view lists opportunities beside items | Read only | New (21) |
| Pulse lines via `sh_platform/pulse/lines.py` `line()` L71-L73 | two new line ids | Written by Nira | Existing shape |
| Run log | events `opportunity_noticed`, `opportunity_judged`; counts only, no text | Written | Existing log, new events |
| Routes under `/api/intents/opportunities` listed in Entry points | as above | Read and written; each declared in `sh_platform/route_permissions.yaml` (default deny) | New |

Illustrative record (synthetic Ardmore data; every value and id is invented for the demo):

```json
{
  "id": "opp-0007",
  "title": "Monday price file and the stale-valuation drift",
  "state": "proposed",
  "noticed_by": "watcher",
  "noticed_at": "2026-10-05T07:10:00+08:00",
  "areas": ["operations"],
  "touches": {"measures": ["K12"], "processes": ["month_end_valuation"], "sources": ["custodian_prices"]},
  "pattern": {
    "text": "The custodian price file arrived late on four Mondays; K12 rose at three month-ends on one portfolio.",
    "periods": ["2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28"],
    "numbers": [
      {"label": "Late Monday arrivals", "value": 4, "unit": "runs", "trace": {"kind": "run", "ref": "warehouse/runs.json#custodian_prices", "at": "2026-09-28"}},
      {"label": "Open alert", "value": 1, "unit": "alert", "trace": {"kind": "alert", "ref": "custodian_prices:late", "at": "2026-09-28"}},
      {"label": "Check-in items on the Monday reconciliation", "value": 3, "unit": "items", "trace": {"kind": "week_item", "ref": "ops-checkin/weeks/2026-W39#i4", "at": "2026-09-25"}}
    ]
  },
  "evidence": [
    {"id": "e1", "text": "K12 definition, pack suggestion", "kind": "supports", "source": {"kind": "pack", "ref": "kpi_tree#K12"}, "by": "lens", "at": "2026-10-05T07:12:00+08:00"},
    {"id": "e2", "text": "Same manual price override each Monday", "kind": "supports", "source": {"kind": "week_item", "ref": "ops-checkin/weeks/2026-W40#i2"}, "by": "katie", "at": "2026-10-05T10:02:00+08:00"}
  ],
  "judgement": {"fits": true, "why": "Crosses a source contract, a process step and a reported measure.", "confidence": "fairly_sure", "start_answers": {"goal": {"value": "Stop Monday price lateness driving stale valuations", "mark": "guessed", "by": "North", "from": "opp-0007"}}, "at": "2026-10-05T10:05:00+08:00"},
  "picked_up_by": null, "picked_up_at": null, "became": null, "parked": null, "dismissed": null,
  "history": [{"at": "2026-10-05T07:10:00+08:00", "by": "watcher", "action": "noticed", "note": null}]
}
```

Other Ardmore patterns the same record shape carries (illustrative):

| Pattern | Records it traces to | Likely judgement |
|---|---|---|
| Late price files from one source every Monday | `warehouse/runs.json` rows, alert `<source>:late` reopened each Monday | Yes when it also moves a measure; else "reads as a Problem" |
| A fee or cost measure drifting on one portfolio over several month-ends | feed values by period (`range.trend`); no fee measure exists in the pack yet (open question 2) | Depends on evidence |
| Repeated check-in items about the same reconciliation step | week files, items of kind `broke` with the same step, fates `handled` each week | Yes: handled every week means no lasting fix |

## Fields this feature adds to the intent record

- `links.from` accepts the value `opportunity:<id>` (no new key; open question 8 for the prefix).
- `refs.opportunity_id: <id> | null`: set by the start flow when opened from an opportunity, so file 19 can count "became Initiatives".

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **The Watcher** (Build centre ops agent, `sh_platform/build/ops.py`): after each daily read that syncs alerts (`alerts.sync`, ops.py L110), it looks across the stored records for a pattern: one alert id reopened or kept open across several run days; one source late on the same weekday; a measure drifting the same way over several periods (beyond `range.breaks`, which judges only the latest period); check-in items on the same step or source over several weeks; alerts on sources that the graph ties to one process. It drafts the record with every number traced. It never states a number it cannot trace, and never notices from documents, chats or anything outside the five record kinds. How many periods make a pattern is open question 1. It never opens a second record for a pattern already open (match on touches and source).
- **Lens**: on `noticed`, adds evidence lines: the measure's definition (pack, or the signed glossary if one exists), its owners by kind (ruling 11), the process step and system from the map (55). Lens drafts; it never disputes.
- **North**: on each new evidence line after Lens's first, judges once per change. Writes fits yes or no, why, confidence in words, and when yes the six start answers drafted from the record (marked guessed, as 22). A pattern that is something wrong in operations today and fixable by one owner gets "No: this reads as a Problem, not an Initiative" (ruling 31); North does not open the Problem (open question 5). An enhancement to a built project gets "Yes" with the earlier Initiative named for `links.from` (ruling 31).
- **Nira**: writes the two Pulse lines; reminds Harvey on a parked review date.
- **People act**: Katie adds evidence or disputes; Harvey picks up, parks, dismisses or brings back; either raises by hand. No agent opens an intent, signs, picks up, parks or dismisses.

## Rules (visibility, time box, who may do what)

- Visibility follows 05: a viewer sees an opportunity only when tagged to one of its `areas` and only when they may see every measure and field it touches (`view.sees_rule`, `sh_platform/profile/view.py` L99; the same gate `ops.py` L64 uses for range breaks). Otherwise the opportunity is absent, not a silhouette (open question 7).
- Numbers in `pattern.numbers` are shown only to viewers on the measure's access list, as on the Ops page; others see the trace kind and date without the value.
- Super admin: no route. Company admin: existence and state of every opportunity and the counters.
- Only a person picks up. "Pick it up" never creates the intent; the start flow does, after the person confirms its review (22).
- Every Park and Dismiss carries a reason; Park carries a review date. Nothing is deleted.
- No time box of its own; the Initiative it becomes gets file 22's default.
- Agent drafts never overwrite a person's edit of the title or an evidence line.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Record | Empty |
|---|---|---|
| Opportunities noticed (by the Watcher, by a person) | `intents/opportunities/*.json` `noticed_by`, `noticed_at` in the window | "Not available yet: nothing noticed" |
| Picked up | records with `state = picked_up` | "0" only when some exist |
| Dismissed, parked | `state` and `dismissed`, `parked` | As above |
| Became Initiatives | records with `became` resolving to an intent of type `initiative` whose `refs.opportunity_id` matches | As above |
| North judged Yes, then picked up | `judgement.fits = true` against `state = picked_up` | "Fewer than five" below five (ruling 8) |
| Did the Initiative's measure move | file 19 | "Not available yet: file 19 has no measure of movement after an Initiative" |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `graft ask "Watcher ops alerts drafted ask" --source`; grep for `Watcher`, `kpi_tree`, `opportunit` across `sh_platform`, `modules`, `ui/src` and this folder (no opportunity code or spec exists).

| File and lines | What it is | Use |
|---|---|---|
| `sh_platform/build/ops.py` L77-L119 `_build_open`, L106-L108 range alerts, L110 `alerts.sync` | The Watcher's daily read and alert derivation | Reshaped: the noticing step runs after the sync and reads the same inputs |
| `sh_platform/build/ops.py` L44-L69 `_breaks` | Range breaks with the restricted-field gate | Reused for the feed and range evidence and the visibility gate |
| `sh_platform/build/alerts.py` L1-L49 | Alert store, stable ids, states | Reused as a read source; its lock and atomic write pattern copied for the opportunity store |
| `sh_platform/consume/range.py` L17-L45 | `trend` (nine periods), `breaks` (latest period only) | Reused for values; drift across periods is new (open question 1) |
| `ui/src/pages/OpsPage.tsx` L50-L78 `AlertCard`, L80-L190 page | Ops page and alert card | Reshaped: the Opportunities card reuses the `ActionCard`/`EmptyState` pattern in the main column |
| `packs/family_office/1/kpi_tree.yaml` L150-L162 (K12) | Measure names and definitions | Reused by Lens as labelled suggestion evidence |
| `docs/specs/intent-centre/25-north-suggestion-cards.md` | Dashed card, "Suggested by North" label, pick up | Reshaped: dashed card and label wording; state lives in its own record, not the wall |
| `docs/specs/intent-centre/21-backlog.md` Screen B drawer, `intents/backlog.json` | Backlog drawer, park with review date, drop with reason | Reshaped: same drawer frame and Park and Dismiss shape |
| `docs/specs/intent-centre/22-initiative-start.md` L20, L31-L38, L204 | `from=` entry, six questions, `guessed` marks | Reused unchanged for pre-fill |
| `docs/specs/intent-centre/55-data-knowledge-map.md` | Lineage edges source to field to measure | Reused for "touches" and Lens's evidence |
| `sh_platform/pulse/lines.py` L71-L73 | Pulse line shape | Reused for both lines |
| `sh_platform/route_permissions.yaml` L313, L328-L329 | Ops and alert route roles | Reused as the model for the new routes |

Genuinely new: the opportunity record and its routes, the noticing step, the two panels and the backlog `opportunity` panel.

## Not in this feature

- Opening a Problem or any intent from an opportunity automatically.
- Noticing from documents, chats, emails or anything outside the five record kinds.
- Scoring, ranking or weighting opportunities with numbers.
- Notifications outside Pulse.
- Any super admin view.

## Open questions

1. What counts as "a pattern": how many periods of drift, how many late arrivals on the same weekday, how many check-in items on the same step, over what window? None is given; the Watcher must not invent one.
2. Which family office measure stands for "custodian fees"? The pack `kpi_tree.yaml` has no fee measure, so the example uses K12 Stale-valuation share.
3. How is "drift" defined when `range.breaks` judges only the latest period: same direction each period, or outside range in more than one?
4. Who may pick up besides the ops manager: may Janet or another organiser pick up a proposed opportunity?
5. When North judges "this is a Problem", may it draft a Problem start (file 41) for a person to open, or only say so?
6. Can the organiser who sees the dashed card act on it, or only read it?
7. Restricted measures: hide the opportunity entirely (this file) or show a silhouette as the map does (55, open question 3)?
8. `links.from` today names an intent id; is the `opportunity:<id>` prefix acceptable, or should `refs.opportunity_id` alone carry it?
9. `GET /api/company/build/ops` allows only `company_admin` and `analyst` (`route_permissions.yaml` L313), yet the ops manager is role `owner`. Widen it to `owner`?
10. Does the Watcher run on the daily read (inside a cached GET, as `alerts.sync` does today) or as a scheduled step after the runner?
11. How long do parked review dates default to: the backlog's quarter (21) or something else?
12. Does a dismissed pattern block the Watcher from noticing the same pattern again, and for how long?
13. File 19 needs a new measure for "did the Initiative's measure move"; who defines the before and after periods?
