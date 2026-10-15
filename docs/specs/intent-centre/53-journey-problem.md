# 53. Journey: a Problem, from a weekly check-in item to closure

Part of: Intent Centre v2. Depends on: 00-BRIEF, 02-intent-types-catalogue, 03-create-intent-chooser, 06-people-and-roles-in-an-intent, 07-time-box-and-stage-clock, 08-north-workflow-runner, 09-closure-and-signoff, 10-ratings-and-session-value, 13-pulse-lines-and-notifications, 20-linking-intents. Feeds: the test script for the Problem type.

## Purpose

This file follows one Problem through the Ardmore family office, screen by screen and person by person, from a weekly check-in item to a closed record. It is a walk-through for builders and testers: it adds no new rules, and where a rule lives it names the file. Every figure, name and date is synthetic. The journey runs in 5 working days, the Problem time box in `intent_types.yaml`.

## The people (Ardmore synthetic)

| Person | Role in this journey | Seed login (from `data/_control/seed_credentials.txt`) |
|---|---|---|
| Aaron | Participant in the Operations weekly pulse. Reports the item. Becomes the Problem's reporter. | participant.ardmore@example.test |
| Harvey | Proposed source owner of the measure "Custodian cash balance match". Passes the Problem. | owner.ardmore@example.test |
| Katie | Analyst and data owner of the measure. Accepts the Problem and owns the fix. | analyst.ardmore@example.test |
| Grace | Approver. Affected: her month-end sign-off waits on the match. Taps "Fixed for me". | approver.ardmore@example.test |
| Daniel | Sponsor. Affected: his monthly report uses the match. Taps "Fixed for me". | sponsor.ardmore@example.test |
| Janet | Organiser of the centre. Observer on this Problem. Watches; does not act. | company_admin.ardmore@example.test |
| North | Runs the workflow, keeps the clock, drafts. Never signs. | none |

Janet signs in with the company admin account, so in branch A she acts as company admin, not as observer. The seed has no separate company admin login.

Starting facts, all in the seed pack: the measure `custodian_cash_match` has a node in the governed state with source owner "not yet named", data owner Katie, and 3 alerts from Ops in the last 14 days (the Ops alert feed, existing). Aaron's pulse item reads: "The custodian cash balance did not match the ledger on Tuesday and Thursday. I fixed it by hand again."

## The path

Day 0 is Monday. "Working day" counts follow `07-time-box-and-stage-clock`. The Problem opens with state `open`, stages `describe`, `find_cause`, `fix`, `confirm`.

### Step 1. The item becomes a Problem

- **Who:** Aaron. North has already offered it.
- **Screen and route:** Weekly pulse item card on `/centre/intent/<pulse id>/week` (the week record), then `/centre/intent/new?type=problem&from=<pulse id>&item=<item id>`.
- **What he sees:** On his item, the Nira line "This looks like an ops problem. Start a Problem from this item." Then the start form with five questions, pre-filled by North from the item text: Q1 "What is wrong?" One line filled from his sentence; what you saw filled "Tuesday and Thursday no match." Q2 "Which process or measure is it about?" pre-selected "Custodian cash match" from the area. Q3 "How hard does it bite?" empty (cost, "I do not know" accepted). Q4 "Who do you think owns it?" empty. Q5 "Which areas are affected?" pre-selected "Operations" with affected people empty. Pre-filled fields carry the label "Drafted by North from your item. Edit anything."
- **What he clicks:** Confirms Q1. Confirms Q2. Confirms Q3. Types "Harvey" in Q4 (the people picker lists those in area Operations). In Q5 ticks "Grace" and "Daniel" under "Who feels it", clicks "Start this Problem".
- **What North does:** Fills the drafts, checks the required fields (Q1, Q3, Q5), and checks the people minimum: reporter, one affected person. Owner is proposed but not required on open.
- **What is written:** `intents/<id>/intent.json` with `type: problem`, `created_by: Aaron`, `people.organiser: Aaron`, `people.reporter: Aaron`, `people.participants: [Aaron]`, `people.affected: [Grace, Daniel]`, `people.observers: [Janet]` (the area rule adds her, `05-areas-and-visibility`), `links.from: <pulse id>`, `links.alert: null`, and on the pulse item `fate: problem`, `fate_ref: <id>` with reason "Started as a Problem by Aaron".
- **The clock:** Starts now. `time_box.starts` Monday 10:05, `ends` Friday end of day. Stage `describe` opens, 1 day.

### Step 2. North's triage draft, with the measure's recent alerts

- **Who:** North drafts. Aaron reads. Nobody else acts yet.
- **Screen and route:** `/centre/intent/<id>`, stage `describe`.
- **What he sees:** The Problem page with a "Triage draft from North" panel: a statement in two sentences; the measure named as `custodian_cash_match` (matched from the item and the area); a box "Recent alerts from Operations" listing the 3 alerts in the last 14 days with date and size of the mismatch (read from the Ops alert feed, never typed by North); a line "Likely source owner: Harvey (named on the upstream feed). Likely data owner: Katie (named on the measure)"; and "Not available yet: cost per occurrence. Nobody has said." The panel ends with two buttons.
- **What he clicks:** "Looks right" (agrees the statement), or "Edit statement" and then "Looks right". He clicks "Looks right".
- **What North does:** Writes the triage draft once; states in the thread that the draft is North's, not a person's. Offers the owner proposal.
- **What is written:** `outcome.what` (the one-line statement) as a draft with `drafted_by: north`; on confirm, `confirmed_by: Aaron`, `confirmed_at`. Alert references are stored as ids into the Ops feed, not copies.
- **The clock:** Day 0, 10:20. The `describe` stage has until Tuesday 10:05.

### Step 3. The owner proposal and the pass

- **Who:** North proposes. Harvey is asked. Harvey passes.
- **Screen and route:** Harvey opens his Pulse line "You are proposed as owner of a Problem" on `/centre/pulse`, which links to `/centre/intent/<id>` showing a banner "You are asked to own this. Accept or pass."
- **What he sees:** The statement, the alerts box, the people, the time box ("5 working days, ends Friday") and two buttons: "Accept ownership" and "Pass, and say why".
- **What he clicks:** "Pass, and say why". A required reason field: "The break is in the ledger load, which Katie's team owns, not the custodian feed." He clicks "Send pass".
- **What North does:** Reads the reason, drafts a suggestion "Katie owns the measure's data. Propose Katie?" and posts it to Aaron as a card with "Propose Katie" and "Choose someone else".
- **What is written:** `people.owner_proposals: [{who: Harvey, at, answer: pass, reason}]`; thread entry. Harvey leaves the Problem's people list; he remains in the audit trail.
- **The clock:** A proposal has 1 working day to be answered. North nudges Harvey at the half day if no answer. Here he answers within the hour.

### Step 4. Acceptance by the data owner

- **Who:** Aaron proposes Katie. Katie accepts.
- **Screen and route:** Aaron: card on `/centre/intent/<id>`. Katie: Pulse line then the same page.
- **What they see:** Aaron sees Harvey's reason beside the card. Katie sees the banner and the pass reason from Harvey.
- **What they click:** Aaron clicks "Propose Katie". Katie clicks "Accept ownership".
- **What North does:** Sets Katie as owner, moves the Problem to `find_cause`, tells all participants in the thread "Katie owns this Problem. Next: find the cause."
- **What is written:** `people.owner: Katie`, owner proposal answer `accept`, stage `describe` closed, stage `find_cause` opened.
- **The clock:** Monday 14:30. `find_cause` has 2 working days, to Wednesday 14:30.

### Step 5. The thread and North's running "what we know"

- **Who:** Katie, Aaron, Grace, Daniel post. North summarises. Janet reads.
- **Screen and route:** `/centre/intent/<id>`, tab Thread. Right-hand panel "What we know".
- **What they see:** A thread of short posts, newest last. Katie posts "Tuesday's break matches the batch that loaded late." Aaron posts the two dates. Grace posts "My sign-off was held on Tuesday for 3 hours." The panel "What we know" has three lists: Confirmed (each line cites a post or a record), Not confirmed, Missing (for example "The ledger load log for Thursday").
- **What they click:** "Add evidence" (text, or a reference to an Ops alert or a measure version), "Post". Janet sees the thread read-only: the Post button is absent for her.
- **What North does:** After each post, redrafts "What we know" and shows the change with the label "Updated by North, 11:42". It never deletes a person's post. It asks one missing question at a time, such as "Does the Thursday break line up with the late batch too?"
- **What is written:** Each post as `thread[]` with `by`, `at`, `text`, `refs`; "What we know" as a replaceable draft `outcome.working_summary` with its source post ids.
- **The clock:** Monday 14:30 to Wednesday 14:30. North nudges Katie on Tuesday 14:30 if no cause is drafted.

### Step 6. The root cause draft and confirm

- **Who:** North drafts. Katie confirms. Aaron and affected people may comment.
- **Screen and route:** `/centre/intent/<id>`, stage `find_cause`, panel "Root cause".
- **What they see:** North's draft: "The ledger load runs after the custodian file lands. When the file arrives late, the match runs on the old ledger." It cites the posts it rests on and the ledger load log line. A line "Confidence: drafted from 4 posts and 1 log. Not confirmed."
- **What they click:** Katie clicks "Confirm root cause" (or "Edit and confirm", or "Not right, keep looking").
- **What North does:** On confirm, moves the Problem to `fix` and drafts the fix steps from the confirmed cause.
- **What is written:** `outcome.root_cause` with `confirmed_by: Katie`, `confirmed_at`, source post ids. Stage `find_cause` closed.
- **The clock:** Tuesday 16:10, inside the stage. `fix` has 1 working day, to Wednesday 16:10.

### Step 7. The fix with a workaround date

- **Who:** North drafts. Katie fills in and confirms.
- **Screen and route:** `/centre/intent/<id>`, stage `fix`, panel "Fix".
- **What she sees:** A draft with fields: "What will change", "Who does it", "Workaround until then", "Workaround in place by" (a date), "Fix done by" (a date). North's draft: change the match to wait for the ledger load; Katie does it; workaround: Aaron reruns the match after 08:30, in place by Wednesday; fix done by Thursday.
- **What she clicks:** Edits the dates, clicks "Confirm the fix plan".
- **What North does:** Checks the fix date is inside the time box (Friday). If it were not, North would say so and offer "Extend" (branch D). It posts the plan to the thread and asks each affected person to watch for "Fixed for me".
- **What is written:** `outcome.fix: {what, by: Katie, workaround_by, done_at: null, planned_done_at}`. Stage `fix` stays open until the fix is marked done.
- **The clock:** Tuesday 16:40. Workaround date Wednesday. Fix date Thursday. Time box ends Friday.

### Step 8. Affected people tap "Fixed for me"

- **Who:** Grace and Daniel. Katie marks the fix done first.
- **Screen and route:** Katie: "Mark fix done" on `/centre/intent/<id>`. Grace and Daniel: Pulse line "Katie says the fix is in. Is it fixed for you?" and the same page.
- **What they see:** The fix plan and the date it was marked done. A panel "Is it fixed for you?" with a tally "0 of 2".
- **What they click:** Each clicks "Fixed for me". If it is not, "Not fixed for me" opens a required note.
- **What North does:** Updates the tally. When all affected have answered "Fixed for me", it moves the Problem to `confirm` and nudges the reporter. A "Not fixed for me" goes to Katie as a card; North does not move the stage.
- **What is written:** `outcome.fix.done_at: Thursday 11:00`; `outcome.fix_for_me: [{who, answer, at, note}]`.
- **The clock:** Thursday. Day 4 of 5. North nudges any affected person who has not answered after 4 working hours.

### Step 9. Closure

- **Who:** North drafts the closure. Katie, as owner, closes.
- **Screen and route:** `/centre/intent/<id>`, panel "Closure" (shared with `09-closure-and-signoff`).
- **What she sees:** North's draft summary, "why it happened" (the confirmed root cause), "what came out" (the fix and the version it made), and the next list: "Start an Initiative", "Add to backlog", "Start a Problem", "Nothing, and why". Closure is blocked and says why if root cause, fix with doer, or reporter confirmation is missing; here reporter confirmation is still missing, so "Close" is disabled and reads "Waiting for Aaron to confirm".
- **What she clicks:** After step 10 she clicks "Close this Problem", with "Nothing, and why: no wider work needed".
- **What North does:** Drafts the closure, keeps the button disabled until the rule holds.
- **What is written:** `closure: {closed_by: Katie, closed_at, summary, why_it_happened, what_came_out, next: [{kind: nothing, reason}]}`, `state: closed`, stage `confirm` closed.
- **The clock:** Friday morning, inside the 5 days.

### Step 10. The reporter confirms

- **Who:** Aaron.
- **Screen and route:** `/centre/intent/<id>`, stage `confirm`.
- **What he sees:** The question "Is the problem you reported gone?" with the fix summary and the next two match results from the Ops feed (read, not typed).
- **What he clicks:** "Yes, it is gone" or "No, send it back" (branch C).
- **What North does:** Logs, tells Katie "Aaron confirms. You may close." Step 9's button enables.
- **What is written:** `outcome.confirmed_by: Aaron`, `confirmed_at`.
- **The clock:** Thursday afternoon to Friday morning.

### Step 11. The version note on the measure node

- **Who:** North writes the note. Katie sees it. Grace, Daniel and Janet may see it in the governed state.
- **Screen and route:** The governed state node for `custodian_cash_match` (existing governed state view, `31-governed-state`), tab History.
- **What they see:** A new version line: "v4, 9 October. Match now waits for the ledger load. Source: Problem 'Cash balance did not match'." It links back to the Problem. Source owner now reads "Katie" (from step 4), and Harvey's pass is shown in the Problem, not on the node.
- **What they click:** The link "Open the Problem".
- **What North does:** Drafts the version note from the closure and the fix. Katie confirms it as the data owner because a change to a node is a governed change; North never writes a version alone.
- **What is written:** A new version on the node in the governed state store (existing), with `source_intent: <id>`. `links.to` gains the node ref.
- **The clock:** Friday, right after closure. Not part of the 5 days; it follows the closure.

### Step 12. Ratings

- **Who:** Aaron, Grace, Daniel, Katie, and Janet if she wishes.
- **Screen and route:** `/centre/intent/<id>`, after closure, panel "Was this useful?" (`10-ratings-and-session-value`).
- **What they see:** Five steps, 1 to 5, an optional note, and a tick "Rate without my name".
- **What they click:** A score and "Send rating".
- **What North does:** Waits. It never rates. It shows the average only when 3 or more people have rated.
- **What is written:** `ratings[]`; anonymous ones carry no `by`.
- **The clock:** Open for 7 days after closure (open question 1 in 10).

## The branches

**A. Two passes go to the company admin.** If Harvey passes and Katie also passes, North does not propose a third name. It posts "Two people passed. The company admin names an owner." The Problem gets state `open` with `people.owner: null` and an amber banner. The company admin sees a card on Pulse "A Problem has no owner", with "Name an owner" and "Cancel the Problem, and say why". Naming an owner resumes at step 4. The clock does not run while no owner exists (the pause rule of `07`). Written: `owner_proposals` with two passes, then `owner` and `named_by: company admin`.

**B. The owner marks it bigger than a fix and turns it into an Initiative.** At step 5 or 6 Katie clicks "This is bigger than a fix". North asks one line, "What is bigger about it?", then drafts the Initiative's start answers from the thread. Katie clicks "Turn into an Initiative". The Problem closes with `next: [{kind: initiative, ref}]` and the reason; the Initiative starts at `/centre/intent/new?type=initiative&from=<id>` with Katie as organiser, Aaron, Grace and Daniel as affected, and `links.from` set. The Problem's closure does not need a fix or reporter confirmation: "closed as bigger than a fix" is a named closure kind, and Aaron is told in the thread. Rules in `20-linking-intents`.

**C. The reporter reopens once.** At step 10 Aaron clicks "No, send it back" and gives a note ("It matched on Monday, broke again today"). The Problem returns to `find_cause` with 1 working day and a banner "Reopened by Aaron". North redrafts "What we know" with the new fact. A second "No" is not offered: North says "This has been reopened once. The owner decides: Extend, Close as not fixed, or Turn into an Initiative", and Katie picks. Written: `reopened: [{by, at, note}]`, the stage re-opened with a new `opened_at`.

**D. The time box runs out and the owner extends with a reason.** On Friday end of day, if the Problem is still open, North posts "The time box has ended" and offers three buttons to Katie: "Extend", "Close with what we have", "Cancel, and say why". She clicks "Extend", picks a number of days and types "Ledger vendor needs one more day to deploy." Written: `time_box.extended_by: [{by: Katie, at, reason}]`, `time_box.ends` moved. North states the new end date to everyone. Only the owner may extend; the Problem keeps a visible "Extended" chip.

**E. The Problem names a restricted measure Aaron may not see.** If the matched measure sits in a restricted area (for example "Principal fee accrual", Finance only), North's triage draft shows Aaron "A measure in a restricted area is involved. You cannot see its name or its alerts." It names the measure to people who may see it (Katie, Grace) and shows Aaron a neutral line in the alerts box: "Alerts from a restricted measure are not shown to you." Aaron can still confirm the statement, see his own words, and confirm the fix at step 10. The version note at step 11 is shown only to those who may see the node. Janet sees the alerts box as Aaron does when she lacks access. Written: `restricted_refs: [measure id]` on the thread entry and the draft, so `view.py` filters per viewer.

## What each person saw in total

| Person | Saw | Acted | Never saw |
|---|---|---|---|
| Aaron | His item; the pre-filled start form; triage draft and alerts; Harvey's pass reason; the thread; "What we know"; the root cause and fix; his own confirmation question; the closure | Started the Problem; confirmed the statement; proposed Katie; posted evidence; confirmed it is gone; rated | Restricted measures (branch E); anonymous ratings by others |
| Harvey | The owner proposal with statement, alerts, time box | Passed with a reason | Later thread and fix, unless named (he is in the audit trail only) |
| Katie | Everything in the Problem; the node; the proposal banner | Accepted; confirmed root cause; confirmed fix; marked done; closed; confirmed version note; rated | Anonymous ratings |
| Grace | Statement, alerts if allowed, thread, fix plan, "Is it fixed for you?", closure | Posted evidence; tapped "Fixed for me"; rated | Anonymous ratings |
| Daniel | Same as Grace | Tapped "Fixed for me"; rated | Anonymous ratings |
| Janet | That the Problem exists in her area; the thread and outcome read-only | Optionally rated | The post box and any action button; restricted material |
| Company admin | Existence and outcome of the Problem; branch A card | Named an owner (branch A) | Anonymous notes and ratings |
| Super admin | That the intent exists: title, type, state, areas, people count | Nothing | Content |

## The records at the end

- `intents/<id>/intent.json`: the Problem record, `state: closed`, outcome `{what, saw, about, bites, root_cause, fix: {what, by, workaround_by, done_at}, working_summary, confirmed_by: Aaron, confirmed_at}`, `closure`, `ratings`, `people: {reporter: Aaron, organiser: Aaron, owner: Katie, affected: [Grace, Daniel]}`, `links.from: <pulse id>`, `links.to: [<node ref>]`.
- The week record of the Operations pulse: the item's `fate: problem`, `fate_ref: <id>`, reason.
- The governed state: `custodian_cash_match` version v4 with `source_intent: <id>` and the version note.
- The thread, kept in full with North's drafts labelled, and the audit trail (`16-transcript-and-audit-trail`): every pass, accept, confirm and extend with who and when.
- Nothing is deleted. A cancelled Problem keeps its record with the reason.

## Test script

Tool: `.venv/Scripts/python .sh-tmp/shot.py <email> <path> <out.png> --width 1280|390 [--click "text=..."]`. Run each step at 1280 and at 390. Output to `.sh-tmp/shots/problem-<step>-<role>-<width>.png`. Use the seed logins above. Reset the seed before the run. Fix the date by the seed clock so the day counts are stable.

Checks at both widths, every step: no horizontal scroll; every button named in the step is present and reachable; no game words; no model or vendor names; the clock chip matches the stage; empty states say what is missing. At 390: the "What we know" panel collapses under the thread into a closed section, the people list becomes chips, buttons stack and are at least 44 px high.

| Step | Run as | Path | Check |
|---|---|---|---|
| 1 | Aaron | `/centre/intent/new?type=problem&from=<pulse id>&item=<item id>` | Q1 (what), Q2 (measure) pre-filled with the North label; Q3 (how hard) empty; Q4 (owner) empty; Q5 (areas) pre-filled; "Start this Problem" disabled until Q1, Q3, Q5 are filled and an affected person named; after click the record has `type: problem`, `links.from` and `links.alert` set, `people.reporter` filled |
| 2 | Aaron | `/centre/intent/<id>` | Alerts box lists exactly 3 alerts matching the Ops feed; "Looks right" writes `confirmed_by: Aaron`; the cost line says "Not available yet" |
| 3 | Harvey | `/centre/pulse` then `/centre/intent/<id>` | Banner with "Accept ownership" and "Pass, and say why"; "Send pass" refuses an empty reason |
| 4 | Aaron, Katie | same | Aaron sees the pass reason and "Propose Katie"; Katie's accept moves the stage to `find_cause` and shows the 2-day clock |
| 5 | Katie, Grace, Janet | same | Every post shows by and at; "What we know" cites post ids; Janet has no Post button |
| 6 | Katie | same | Draft shows source lines; "Confirm root cause" writes `confirmed_by`; stage moves to `fix` |
| 7 | Katie | same | Both dates present; a fix date after Friday shows the Extend offer |
| 8 | Katie, Grace, Daniel | same | Tally goes 0 of 2, 1 of 2, 2 of 2; "Not fixed for me" refuses an empty note and holds the stage |
| 9 | Katie | same | "Close" disabled with "Waiting for Aaron to confirm" until step 10, then enabled |
| 10 | Aaron | same | Question shown with the next two match results from the feed; "Yes, it is gone" writes `confirmed_by: Aaron` |
| 11 | Katie, Grace | governed state node, tab History | v4 line links back; Katie's confirm precedes publication; Aaron sees no line if the node is restricted |
| 12 | Aaron, Grace, Janet | `/centre/intent/<id>` | Score and "Rate without my name"; average hidden below 3 ratings; Janet may rate |

Branch checks (each one at 1280 and 390): A) both passes lead to a company admin card and the clock shows paused; B) "This is bigger than a fix" opens an Initiative with the answers carried and closes the Problem as bigger than a fix; C) "No, send it back" works once and the second time the owner's three buttons appear; D) at the seed clock past Friday, "Extend" requires a reason and the chip "Extended" shows; E) as Aaron, the restricted measure's name and alerts are absent from the page text and from the network response of the route.

Record checks at the end: open `intents/<id>/intent.json`, assert state `closed`, one `outcome.root_cause` with `confirmed_by`, one `outcome.fix.done_at`, two `fix_for_me` entries, the closure `next`, the node version, and the pulse item `fate_ref`.

## Open questions

Rules this journey added that the brief and files 41 and 42 do not give. Owners of 41 and 42: adopt or reject each.

1. **One working day to answer an owner proposal** (step 3). North nudges at the half day. The figure is not justified by any source.
2. **Closing as bigger than a fix needs no fix and no reporter confirmation** (branch B). This relaxes the closure rule of 09.
3. **A second reopen is blocked** (branch C). The reporter may send it back once; then only the owner decides: Extend, Close as not fixed, or Turn into an Initiative.

Problem fields introduced here, to be added to the intent record by file 41 or dropped:

4. `people.owner_proposals: [{who, at, answer, reason}]` (steps 3 and 4, branch A).
5. `outcome.fix_for_me: [{who, answer, at, note}]` (step 8).
6. `reopened: [{by, at, note}]` (branch C).
7. `restricted_refs: [measure id]` on thread entries and drafts (branch E).

Also unsettled: Branch A needs a company admin who is not Janet, or Janet acts in both roles. The `outcome.problem` nesting in 41 is corrected to flat `outcome.*` per ruling 16.
