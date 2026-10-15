# 58. Initiative outcomes and the weekly uplift report

Part of: Intent Centre v2. Depends on: 01 (record and lifecycle), 09 (closure), 10 (ratings and `outcome_used`), 13 (Pulse lines), 19 (centre measures), 32 (charter), 33 (build-ready and hand-off), 45 (Nira), 46 (agent memory), 57 (radar and hypothesis record), `docs/specs/BUILD-CENTRE-SPEC.md` section 4.5 (release). Feeds: 04 (home chip), 12 (Past), 19, 57 (failed and partial hypotheses come back), 60 (Consume by lens, "upliftment").

## Purpose (three sentences)

After an Initiative's change goes live, the company needs to know whether the thing it believed (the hypothesis frozen at charter signature, 57) actually happened, in the measure it named, against the target it set. This file adds Proving: a track that follows a closed Initiative from release to its review date, with a weekly uplift report North drafts every Friday (before, now, target, the series since the start, attribution notes, a verdict with the rule that produced it, confidence in words) that the organiser confirms and the sponsor reads on Pulse. At the review date the organiser and sponsor settle the outcome; a hypothesis that did not work, or worked only in part, goes back to the radar with what was learnt, every person whose voice fed it gets a receipt, and North keeps a short, figure-free memory of it.

### Where Proving sits in file 01's state machine (decision and justification)

Proving is a **sub-state of `closed`**, kept in a side file `intents/<id>/proving.json`. It is not a seventh intent state and not a new stage.

1. Ruling 26 writes `closed` after hand-off (or after "build needed: no"). The release is signed later, in Build (`BUILD-CENTRE-SPEC.md` 4.5). So Proving always begins after `closed`. A state after `closed` would break 01's rule that `closed` is terminal, and every reader of `state` (lists, visibility, closure, Past, measures M02 to M04) would have to learn it.
2. A stage would need writes to a read-only record, and 01 closes every stage at closure.
3. A side file keeps the closed record read-only. The only record key Proving writes is `outcome_used`, already on the post-close list (00-INDEX C-28).

On screen the intent shows "Closed" and, beside it, a chip "Proving" (or "Proved", "Sent back to the radar", "Stopped").

## Who uses it and when (role, moment, trigger)

| Role (Ardmore demo) | Moment | Trigger |
|---|---|---|
| Janet, organiser | Each Friday while Proving runs | Pulse line "North drafted this week's uplift report on `<T>`. Check it." |
| Daniel, sponsor | After Janet confirms; at the review | Pulse watch line "Uplift on `<T>`: <verdict>"; review line "Review `<T>`" |
| Katie, analyst | When a report needs an attribution note | Participant of the Initiative; adds a note |
| Harvey, Mei Ling, Rahul (voices) | When Proving starts and when it ends | Receipt line "Your item became `<T>`" |
| Area members | Any time | See the chip and the confirmed verdict word on the home and Past |
| Company admin | Setting up | Admin Defaults card "Proving rules" |
| North (agent) | Every Friday; at the review date; at send-back | Drafts reports, verdicts, the review summary, the learning |
| Nira (agent) | Report drafted, report confirmed, review due, receipts | Pulse lines |
| Super admin | Never | Existence only (ruling 5); no route |

## Entry points (every route, link, Pulse line, button that leads here)

- `/centre/intent/<id>` (stage view) of a closed Initiative with a `proving.json`: the Proving panel opens by default (ruling 18: panels on the stage view). Query keys: `?focus=proving` (default), `?week=<week_key>` (one report), `?focus=review`.
- Home card and Past row chip "Proving" (`ui/src/intents/IntentHome.tsx`, `IntentPast.tsx`): opens `/centre/intent/<id>?focus=proving`.
- Pulse lines (rows below in Agent behaviour), each to `/centre/intent/<id>?week=<week_key>` or `?focus=review`.
- Build Prove page (`ui/src/pages/ProvePage.tsx`): after the sponsor signs a release, a link "Follow the outcome" per Initiative whose measure was released.
- The 57 drawer (`/centre/intent/backlog?opportunity=<id>`): on a carried hypothesis, the line "Being proved in `<T>`" links here.
- Admin Defaults `/centre/intent/admin?tab=defaults`: card "Proving rules".
- API (New, each declared in `sh_platform/route_permissions.yaml`, default deny): `GET /api/intents/{id}/proving`; `GET /api/intents/{id}/proving/reports/{week_key}`; `POST /api/intents/{id}/proving/reports/{week_key}/confirm`; `POST /api/intents/{id}/proving/reports/{week_key}/notes`; `POST /api/intents/{id}/proving/start`; `POST /api/intents/{id}/proving/review`; `POST /api/intents/{id}/proving/review/confirm`; `POST /api/intents/{id}/proving/receipts/{receipt_id}/seen`.

## Screens, element by element

### Screen A. Proving panel (stage view)

Route: `/centre/intent/<id>?focus=proving`. Layout at 1280: the intent header (existing `IntentHeader.tsx`) with "Closed" and the Proving chip; main column: hypothesis strip, latest report card, series chart, report list; right aside: "How the verdict is decided", "Who hears about it". Layout at 390: one column in that order; the chart becomes a sparkline with the table under it; the aside becomes two collapsed rows at the end.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Proving chip | chip | "Proving since <start date>", "Waiting for release", "Proved", "Sent back to the radar", "Stopped" from `proving.state` | Scrolls to the latest report | Everyone who sees the intent exists | Hidden when no `proving.json` |
| Hypothesis strip | panel | Belief, lens chip, measure name, target with its date, review date, "Frozen at charter v<n>" from the hypothesis version in `proving.hypothesis_ref` (57) | Link "Open the hypothesis" opens the 57 drawer region | Participants, sponsor, company admin | "Not available yet: this Initiative carries no hypothesis. North drafted one from the charter's measures; confirm it below." |
| Start line | agent line (North) | "Live since <date>, from <the release signed by Daniel on <date> \| the closure on <date>>" from `proving.start` | Button "Change the start date" (organiser, until the first report is confirmed): native date input and a required reason | Participants, sponsor | "Waiting for release: the measure `<name>` is not in a signed release yet." |
| Latest report card | panel | Before, Now, Target (each with value, unit, period and a trace link to the gold table row), verdict pill, the rule line that fired, confidence in words, state "Drafted by North" or "Confirmed by Janet on <date>" | Opens Screen B for that week | Figures only to viewers who pass the measure's access list (`prove._may_see`); others see the verdict word and "You cannot see this measure's figures" | "The first report is drafted on the first Friday after the start date." |
| Series chart | chart (existing `LineChart`) | Measure value per period since `counter_periods` before the start, the start marked, the target as a line, the normal range as a band | Hover shows period and value | As the figures above | "Not available yet: no period of `<measure>` has landed since the start." |
| Report list | list | One row per week: week key, verdict word, state (drafted, confirmed, no change) | Opens Screen B | Participants, sponsor, company admin | "No reports yet." |
| "How the verdict is decided" | text | The four rules below in words, with the company's values for `proving_min_periods` and `counter_periods` | Company admin: link to Screen D | Everyone who sees the panel | "Not available yet. The company has not set <key names>, so every verdict reads Too early." |
| "Who hears about it" | list | Sponsor, participants, and the count of receipt holders (named voices counted; anonymous voices counted separately) from `proving.receipts` | None | Organiser, sponsor | "Nobody raised this from a voice; no receipts are due." |
| Button "Open the review" | button | Shown from the review date | Opens Screen C | Organiser, sponsor | Hidden before `review_date` |

### Screen B. One weekly report

Route: `/centre/intent/<id>?week=<week_key>`. Layout at 1280: report in the main column (four regions), actions bar at the foot; aside "Earlier weeks". Layout at 390: regions stack; actions bar sticks to the bottom; aside becomes a select at the top.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Before, Now, Target | stat cards (existing `StatCard`) | Before: the hypothesis baseline (value, periods). Now: the latest period in the gold table on the Friday. Target: value and date | Trace link opens the gold row or the hypothesis version | Viewers passing the access list | Each card: "Not available yet: <what is missing>" (no baseline, no period since start, no target) |
| Series since start | table plus sparkline | `series[]`: period, value, change from before | None | As above | "No period since the start." |
| Attribution notes | list | Each note: text, who (North or a person), the record it rests on, date | Record link opens it; "Add a note" opens a text field (required record link or the words "No record") | Read: participants, sponsor. Add: organiser, analyst, sponsor | "North found nothing else that moved this measure." |
| Verdict | pill plus agent line (North) | Working, Partly, Not working, Too early; the rule that fired in one sentence; confidence: Fairly sure, Not sure, Unlikely | None | Everyone who sees the panel (word only for those without figures) | Never empty: "Too early" with its reason |
| Changed verdict line | text | "North said <x>. Janet changed it to <y>: <reason>." | None | As verdict | Hidden unless changed |
| Button "Confirm this report" | button (primary) | Fixed | `POST .../confirm`; state `confirmed`; Nira's sponsor line | Organiser | Hidden once confirmed or when state is `no_change` |
| Button "Change the verdict" | button | Fixed | Sheet: select of the four verdicts, reason (required); saved with the confirm | Organiser | Hidden once confirmed |
| Button "Add a note" | button | Fixed | As attribution notes | Organiser, analyst, sponsor | Hidden after the review is settled |
| "No change" banner | agent line (North) | "No new period of `<measure>` since last week. Nothing to confirm." | None | As verdict | Hidden when a new period landed |

### Screen C. The review

Route: `/centre/intent/<id>?focus=review`. Layout at 1280: North's review summary on the left; the decision form on the right. Layout at 390: summary, then form.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Review summary | agent line (North) | Verdicts of every confirmed report in order, the latest Before, Now, Target, attribution notes, and North's proposed outcome | None | Organiser, sponsor, participants | "No report was confirmed. North cannot propose an outcome; choose one yourself." |
| Choice "It works, keep it running" | radio | Proposed when the last confirmed verdict is Working | Sets `review.action = keep` | Organiser | Always shown |
| Choice "Give it more time" | radio plus native date input | New review date, reason (required) | Sets `review.action = more_time` | Organiser | Always shown |
| Choice "Send back to the radar" | radio plus text | The learning North drafted (editable): what held, what did not, which segment or period | Sets `review.action = send_back` | Organiser | Proposed when Not working or Partly |
| Choice "Stop proving" | radio plus text | Reason (required), for example the measure was retired | Sets `review.action = stop` | Organiser | Always shown |
| Button "Send to Daniel" | button (primary) | Fixed | `POST .../review`; Nira's line to the sponsor | Organiser | Disabled until a choice and its required text exist |
| Button "Confirm the outcome" | button | Shown to the sponsor after the organiser sends | `POST .../review/confirm`; writes the outcome (Records) | Sponsor; where the Initiative has no sponsor, the organiser confirms alone | Hidden until sent |
| Button "Send back to Janet" | button | Fixed | Reason (required); review returns to the organiser | Sponsor | Hidden until sent |

### Screen D. Proving rules (admin Defaults card)

Route: `/centre/intent/admin?tab=defaults`, one card under 57's "Radar thresholds". Layout at 1280: one row per key. Layout at 390: rows stack; Save bar as file 48.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Row "Periods a verdict needs" | field (whole number) | New key `proving_min_periods` | Saved by 48's "Save defaults" | Company admin | "Not set: every verdict reads Too early" |
| Row "Periods North checks against" | field (whole number) | 57's `counter_periods`, shown here read only with a link | Link opens 57's card | Company admin | As 57 |

### Screen E. Receipt (Pulse line and the source item)

Route: Pulse `/` and the source item (wall card, check-in week item, brainstorm idea, backlog item). Layout at 1280 and 390: the existing Pulse card and, on the source item, one line under its text.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Receipt line on Pulse | Pulse line, kind `outcome` | Start: "Your item became `<T>`. It went live on <date>." End: "`<T>` was reviewed: <verdict word>. <measure> moved from <before> to <now>." Figures only if the person passes the access list, else "<measure> moved the way the Initiative hoped" or "did not move" | Opens Screen A; `POST .../receipts/{id}/seen` | The named voice | Not made |
| "What came of this" line on the source item | text | "This became `<T>` (<chip>)" | Opens Screen A if the viewer may see the intent exists | Whoever may read the item; this is how an anonymous author learns it | Hidden when the item fed nothing |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

Illustrative, synthetic Ardmore. No figure here is a planted value.

1. Janet closed "Treasury sweep to money market funds" (09) with "build needed: no". The hypothesis frozen at Daniel's charter signature names a cash measure, a target and a review date. The closure writes `proving.json` in state `proving`, `start` from `closure.closed_at`. Nira sends receipts "Your item became ..." to Mei Ling (her check-in item was a voice) and to Harvey (he picked up the opportunity).
2. Janet opens the panel and presses "Change the start date": the sweep began earlier than the closure. She enters the date of the first sweep transfer and the reason "first sweep ran then"; North redraws the series from it.
3. On Friday the first read of the intent after midnight in the company time zone writes this week's draft (the check-in clock pattern; no scheduler). North reads the gold table through the read-only warehouse, fills Before, Now, Target and the series, looks for attribution (another intent on the same measure, an event flagged in the run log, a corrected statement, a segment that differs), applies the verdict rules and writes "Working, fairly sure". Nira gives Janet "Check this week's uplift report".
4. Janet opens Screen B, reads it, adds nothing, and presses "Confirm this report". Nira gives Daniel the watch line "Uplift on Treasury sweep: Working".
5. Next Friday no new month has landed. North writes a `no_change` report; nothing is asked of anyone.
6. On the review date Nira gives Janet and Daniel "Review `<T>`". Janet opens Screen C. North proposes "It works, keep it running". Janet picks it and presses "Send to Daniel". Daniel presses "Confirm the outcome".
7. The server writes `review`, sets `proving.state = proved`, writes `outcome_used.answer = yes` on the intent (10), sends the end receipts, and North writes one company memory line through 46 (no figure). Janet leaves to the home; the chip reads "Proved".
8. Branch, Partly: for "One-page personal summary", North's verdict is Partly because the measure moved out of its normal range but not to target, and the breakdown shows one reader group improved while another did not. At review Janet picks "Send back to the radar" and edits North's learning to name the group that did not move. On Daniel's confirm the server creates a 57 opportunity `under_review`, `origin.kind: initiative`, with a new hypothesis version carrying `learning`; North runs its counter-evidence check as for any new opportunity. The chip reads "Sent back to the radar".
9. Branch, Too early: for "Valuation chase protocol" only one period exists after the start. At review Janet picks "Give it more time" with a new date and reason; Daniel confirms; Proving continues.

## States and transitions (table: state, who moves it, to what, what is written)

`proving.state`:

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | Server, on `closed` of an Initiative with a hypothesis measure or confirmed charter measure | `waiting` (build handed over, release not signed) or `proving` (build needed no) | `proving.json` created; `start` when `proving` |
| `waiting` | Server, on a signed release whose `released` codes include the measure (`build/prove.json` `release`) | `proving` | `start: {at: release.at, from: release}`; receipts (start) |
| `proving` | Organiser, "Change the start date" (before the first confirm) | `proving` | `start.at`, `start.changed: {by, at, reason}` |
| `proving` | Server, on the review date | `reviewing` | Nira lines |
| `reviewing` | Organiser sends, sponsor confirms `keep` | `proved` | `review`; intent `outcome_used`; receipts (end); memory |
| `reviewing` | Organiser sends, sponsor confirms `more_time` | `proving` | `review_dates[]` gains the new date with reason |
| `reviewing` | Organiser sends, sponsor confirms `send_back` | `returned` | `review`, `returned_to: <opportunity id>`; 57 opportunity and hypothesis version; receipts; memory |
| `proving` or `reviewing` | Organiser sends, sponsor confirms `stop` | `stopped` | `review` with reason; receipts; memory |
| `proved`, `returned`, `stopped` | nobody | none | Terminal; a new attempt is a new Initiative with `links.from` (ruling 31) |

Report `state`: `drafted` (North) to `confirmed` (organiser, optionally with `changed_verdict`); or `no_change` (North, when no new period landed and no new note), never confirmed.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Read or written | Mark |
|---|---|---|---|
| `intents/<id>/proving.json` via `sh_platform/jsonfile.py` | `{intent_id, state, hypothesis_ref: {id, version}, measure: {code, name, unit, grain}, start: {at, from: release\|closure, ref, changed}, review_dates: [{date, by, reason}], reports: [week_key], review: {action, by, at, reason, learning, confirmed_by, confirmed_at}\|null, returned_to\|null, receipts: [{id, to, kind: started\|ended, at, seen_at}]}` | Written by the server and the routes above | New |
| `intents/<id>/proving/<week_key>.json` | `{week_key, drafted_at, state: drafted\|confirmed\|no_change, before: {value, unit, periods, trace}, now: {value, period, trace}, target: {value, by}, series: [{period, value}], normal_range: {low, high, periods}, notes: [{text, by, trace, at}], verdict: working\|partly\|not\|too_early, rule, confidence: fairly_sure\|not_sure\|unlikely, changed_verdict: {from, to, reason}\|null, confirmed_by, confirmed_at}` | Written by North (draft) and the confirm and notes routes | New |
| `intents/hypotheses/<hyp id>.json` (57) | Frozen version (target, baseline, measure, review date); on send-back a new version with `learning` | Read; written on send-back | Existing in 57 (New there), widened by `learning` |
| `intents/opportunities/<id>.json` (56, 57) | New record `origin: {kind: initiative, ref}`, `state: under_review` | Written on send-back | Existing, widened |
| `build/prove.json` `release` (`sh_platform/build/prove.py` L237-L254) | `state`, `at`, `by`, `released[]` | Read | Existing |
| `warehouse/company.duckdb` gold tables (`gold.k01` and the rest, `tools/seed_demo_cycle.py` L74-L79) through `sh_platform/warehouse` `open_readonly` | `period`, `value`, breakdown column where present | Read | Existing |
| `intents/<id>/intent.json` (01) | Read: `type`, `state`, `people`, `closure`, `links.build`, `build_handoff`, `hypothesis_ref`. Written: `outcome_used` only | Read; one key written | Existing |
| `intents/<id>/events.jsonl` (16) | `proving_started`, `report_drafted`, `report_confirmed`, `verdict_changed`, `review_sent`, `review_confirmed`, `sent_back` | Written | Existing |
| `intents/index.json` (01) | Row field `proving` (state word) for the home and Past chip | Written | Existing, widened |
| Settings opportunity block (`sh_platform/intents/admin.py` L62-L116) | New key `proving_min_periods`; reads 57's `counter_periods` | Read; written by the company admin | Existing, widened |
| Memory `context/memory/north/company.json` (46) | One entry `{kind: fact, topic: intent:initiative, text, from}` | Written at the end of Proving | Existing |
| `pulse/messages.json` (13) | Drafts `intent_uplift_report`, `intent_uplift_review` | Written | Existing, new kinds |
| Source items: wall card, week item, idea, backlog item | Read for "What came of this"; nothing written on them | Read | Existing |
| Routes listed in Entry points | as above | Read and written | New |
| `docs/product/input_ledger.yaml` rows | report draft, verdict, attribution draft, receipts: derived or automatic; confirm, changed verdict, start date, review choice: confirm; notes, learning edit: manual | Rows for the ledger owners, not this file | New rows |

## Fields this feature adds to the intent record

None. Proving lives in `intents/<id>/proving.json` and `intents/<id>/proving/`. The only intent key written after closure is `outcome_used` (10), already on the post-close list (C-28): the confirmed review writes `answer` `yes` (keep), `partly` (send back after Partly), `no` (send back after Not working, or stop), so file 10 does not ask the same question again a month after closure.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

**North** drafts every Friday for each intent in `proving`:

1. Reads the measure's gold table. Before = the frozen hypothesis baseline. Now = the latest period on or before the Friday. Series = every period from `counter_periods` before the start to now. A figure that cannot be traced is not shown: "Not available yet" names what is missing.
2. Normal range = the lowest and highest value over the `counter_periods` periods before the start.
3. Attribution notes, each traced to a record: another open or proving intent on the same measure; a run-log event, alert or corrected statement in the period; a breakdown segment that moved differently from the rest; outside market briefs only as context, never as the cause of the company's own figure (57, Not in this feature).
4. Verdict by rule, in this order; the first that fires wins and its sentence is written as `rule`:

| Verdict | Rule |
|---|---|
| Too early | Fewer than `proving_min_periods` periods after the start, or `proving_min_periods` or `counter_periods` not set, or no baseline or no target |
| Working | The last `proving_min_periods` periods are all at or past the target, in the direction from baseline to target |
| Partly | The latest period is outside the normal range in the direction of the target but not at it; or the whole measure is at target while a breakdown segment named in a note is not |
| Not working | The latest period is inside the normal range, or past it in the wrong direction |

5. Confidence in words: Fairly sure when the move began after the start and no note names another cause; Not sure when a note names another cause in the same periods or the move began before the start; Unlikely when a note's cause alone accounts for the move (the same move in a segment the Initiative did not touch).
6. If no new period landed and no note was added since the last report, writes `no_change`.
7. At the review date drafts the review summary and proposes an action; on Not working or Partly drafts the learning in two sentences, naming the period, segment or record.

**Lens** drafts nothing here.

**Nira** writes the Pulse lines (LINE shape, `sh_platform/pulse/lines.py` `line`):

| Line | To | Kind | Title | When it goes |
|---|---|---|---|---|
| Report drafted | Organiser | decision | "Check this week's uplift report on `<T>`" | On confirm |
| Report confirmed | Sponsor | outcome (watch strip) | "Uplift on `<T>`: <verdict word>" | On the next confirm, or after a period (open question 6) |
| Review due | Organiser | decision | "Review `<T>`: its review date has come" | On send |
| Review sent | Sponsor | decision | "Confirm the outcome of `<T>`" | On confirm or send back |
| Receipt | Each named voice | outcome | Screen E | On seen, or after a period (open question 6) |

**People act**: the organiser confirms or changes each verdict, changes the start date, chooses the review action; the sponsor confirms it; the analyst and sponsor add notes. North never confirms a report, never sends back to the radar and never stops Proving.

## Rules (visibility, time box, who may do what)

- Visibility follows the intent (brief section 4, rulings 4 and 5). Area members and affected people see the chip and the confirmed verdict word. Figures, series and notes show only to people who may open the content and who pass the measure's access list (`prove._may_see`); a restricted measure's figure never reaches a Pulse line, a receipt, a message or memory for anyone outside the list.
- A drafted verdict is never shown to area members or the sponsor's watch line; only confirmed ones.
- Proving has no time box. The review date is the hypothesis's `review_date`; each "Give it more time" adds a dated row with a reason.
- One report per intent per week (`week_key` from the Friday in the company time zone, ruling 22). The draft is written on the first read on or after that Friday, under the intent lock.
- Only the organiser confirms and changes a verdict; a changed verdict keeps North's word and the reason. Only the sponsor confirms the review outcome; where there is no sponsor the organiser confirms alone.
- Receipts go to named voices in the hypothesis evidence (`record_kind: voice`), the person who picked up the opportunity, and the authors of week items whose `fate` led here. Anonymous voices get no line; the "What came of this" line on their item is how they learn it, and it never names them.
- Memory (46): North's line holds the title, the outcome word and the review date, never a figure, a name other than the reader's, or anonymous material. Tombstones are respected.
- An Initiative closed as cancelled, or with no hypothesis and no confirmed charter measure, gets no Proving.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Record | Empty |
|---|---|---|
| Initiatives proving now | `proving.json` with `state` `waiting`, `proving`, `reviewing` | "Not available yet: no Initiative has gone live." |
| Outcomes by verdict and lens | `review.action` and the last confirmed report's `verdict`, joined to the hypothesis `lens` | "Not available yet: no review has been confirmed." |
| Reports confirmed in the week they were drafted | report `confirmed_at` against `week_key`, "n of m" | "No reports yet." |
| Verdicts changed by a person | reports with `changed_verdict`, "n of m" | As above |
| Sent back to the radar | `proving.state = returned`, resolving `returned_to` | "None yet." |
| Uplift realised per Initiative | last confirmed `now.value` minus `before.value`, in the measure's unit; never summed across units or Initiatives | "Not available yet" naming what is missing; read by 57's "Uplift realised" |
| Receipts seen | `receipts[].seen_at` set, "n of m" | "No receipts are due." |

No per-person figure (ruling 8). These feed 19 as new rows after M15.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: grep `proving|uplift` in `sh_platform`, `modules`, `ui/src` (two unrelated hits: `modules/m1_intent/api/approver.py`, `ui/src/modules/m1_intent/charter/charter.test.tsx`); outlines of the files below.

| File and lines | What it is | Use |
|---|---|---|
| `sh_platform/build/prove.py` L237-L254 `post_api_company_build_release_sign`; L179 `_may_see` | Release signature; per-measure access | Reused: release starts Proving; `_may_see` gates every figure |
| `sh_platform/warehouse` `open_readonly`; `tools/seed_demo_cycle.py` L74-L79 | Read-only gold tables `gold.k01` onward | Reused for every figure |
| `sh_platform/intents/checkin.py` L165-L209 `_open_week`, `tick` | Week opened by the clock on first read, under the lock | Reshaped: the Friday draft uses the same pattern |
| `sh_platform/intents/clock.py` L35 `working_days`, L86 `_tz` | Working days and company time zone | Reused |
| `sh_platform/intents/memory_close.py` L111 `write_closure_memory`, `sh_platform/memory/__init__.py` L61 `remember` | Closure memory, filtered | Reshaped: one more entry builder for the end of Proving |
| `sh_platform/intents/opportunities.py` L72 `_create`, L89 `_add_evidence`, L166 `_rejudge`, L254 `pulse_lines` | 56 records and North's judgement | Reused for send-back; `pulse_lines` as the model for Nira's lines |
| `sh_platform/pulse/lines.py` `line`; `sh_platform/pulse/intent_lines.py` L104 `_row`; `ui/src/pages/PulsePage.tsx` L16 kind `outcome` | Pulse line shape and kinds | Reused; no new kind |
| `sh_platform/intents/admin.py` L62-L116 | Settings block | Reshaped: one key |
| `sh_platform/intents/home.py` L134 `_stage`; `ui/src/intents/IntentHome.tsx`, `IntentPast.tsx` | Home and Past chips | Reshaped: Proving chip |
| `ui/src/intents/IntentScreen.tsx` L148 `StageView` | Stage view | Reshaped: Proving panel for closed Initiatives |
| `ui/src/design/parts.tsx` L104 `StatCard`, L120 `Pill`, L142 `Sparkline`, L155 `LineChart`, L244 `VersionList` | Design parts | Reused |
| `sh_platform/intents/measures.py` M15 (L331) | `outcome_used` counter | Reused: the review writes `outcome_used` |
| `ui/src/pages/ProvePage.tsx` | Build's release proof per measure | Not used as the screen (it proves the figure matches; this proves the change worked); gains one link |

Genuinely new: the proving side file, weekly reports, verdict rules, review, receipts.

## Not in this feature

- Proving Brainstorm, Problem or Decision outcomes.
- Writing the hypothesis, the radar, the counter-evidence check (57).
- Build's own proof that a figure matches the reported figure (`BUILD-CENTRE-SPEC.md` 4.4).
- A score or a money total across Initiatives.
- Any agent confirming, sending back, stopping or picking up.

## Open questions

1. Values for `proving_min_periods` and `counter_periods`; none is given, so every verdict reads Too early until set.
2. Friday is the report day for every company, or a company setting?
3. May the sponsor change the start date or the verdict, or only the organiser?
4. A release covers measures, not Initiatives: is matching the released codes to the hypothesis measure enough, or should `release` name the Initiatives it serves?
5. Should a weekly report be skipped altogether when the measure is monthly and no period landed, rather than writing `no_change`?
6. How long the sponsor's watch line and a receipt line last on Pulse when not opened; no period is given.
7. Partly by segment needs a breakdown column in the gold table; which measures carry one, and who names the segments?
8. Should the end-of-Proving memory line also go to the organiser's own memory, not only the company's?
9. Does the index row field `proving` belong to 01, and does 19 own the new counter rows?
10. A hypothesis whose target is set after the start: does the verdict use the frozen target only, or the latest version?
11. Should a "keep" outcome ask again after a year (a second review), or is Proving over?
