# 52. Journey: the Weekly check-in

Part of: Intent Centre v2. Depends on: 02 (intent types), 06 (people and roles), 07 (time box and stage clock), 08 (North workflow runner), 09 (closure), 13 (Pulse lines), 17 (phone views), 21 (backlog), 20 (linking). Feeds: 53 onwards (other journeys) and 19 (counters).

The Weekly pulse intent type is called "Weekly check-in" on screen so it is never confused with the daily Pulse page. Routes below are proposed and must be declared in the module manifest before they exist. Nothing here is built yet.

## Purpose

One ops area, one series, one short entry per person per week, one reader. This file walks a single week for the Operations area at Ardmore, from setting up the series to the second Monday, and says who sees what, how long it takes, and what is written. Use it as the script for building and testing the flow.

## The people (Ardmore, synthetic)

| Person | Role in this journey | Access note |
|---|---|---|
| Katie | Organiser and reader of the series for Operations. Sets it up, reviews each week, decides each item, closes the week | Operations analyst; sees the Operations area |
| Aaron | Reporter | Operations; sees the run log for his own jobs |
| Harvey | Reporter | Operations; owns the nightly valuation load |
| Mei Ling | Reporter | Operations; reconciliations |
| Rahul | Reporter | Operations; client reporting packs |
| Janet | Company admin. Watches counts and outcomes only | Never sees anonymous notes (brief section 4) |

Four reporters. The catalogue minimum of two participants is met. Agents: North runs the series and drafts. Nira writes the Pulse lines. Lens takes no part. Agents never decide an item's fate; Katie does.

## The path

Clock for the demo week: Monday 12 October 2026 to Friday 16 October. Series set up on Friday 9 October.

### 1. Setting up the series (Friday 9 October, 15:00)

- Who: Katie.
- Screen and route: `/centre/intent/new?type=pulse` (the chooser frame from file 03 with the Weekly check-in card; four start questions from file 38). On phone or laptop.
- What she sees: the four questions, one at a time: the area, who takes part each week, the day the week closes, who reads the week.
- What she clicks: picks "Operations"; picks Aaron, Harvey, Mei Ling, Rahul; picks "Wednesday, 17:00" for closing; picks herself as reader; then "Start the series".
- What North does: reads the answers back in one sentence ("Every Monday at 08:00, four people in Operations answer three questions by Wednesday 17:00. You read the week on Thursday."). Drafts the three weekly prompts from the catalogue ("What ran well this week?", "What broke or nearly broke?", "What is on your mind?") and shows them. Checks that the minimum of two participants is met.
- Written: `intents/<id>/intent.json` with type `pulse`, state `draft` then `open`; `people.organiser = Katie`; participants; `areas = [Operations]`; recurring flag and close day (fields in file 38); `stages` collect, review, triage. The series is not rated and neither is any week.
- Clock: about 3 minutes for Katie. Series is live; first week opens Monday 08:00.

### 2. Week one opens (Monday 12 October, 08:00)

- Who: North, then each reporter receives a nudge.
- Screen and route: Nira Pulse line on the reporter's home (`/`), and a phone notification link to `/centre/intent/<id>/week`.
- What they see: "Weekly check-in, Operations, due Wednesday 17:00. Takes two minutes." One button, "Start my check-in".
- What North does: opens the week (a new `weeks` entry for this intent, stage `collect` opened), sends the nudge, starts the clock. Nira writes the line.
- Written: stage `collect` `opened_at`; a week file `intents/<id>/weeks/2026-10-12.json` holding the shell `{week_of: 2026-10-12, area, participants_count: 4, responded_count: 0, items: []}`.
- Clock: instant. No person acts.

### 3. Each reporter's entry (Monday 08:20 to Wednesday 09:00, phone, 390 wide)

Route: `/centre/intent/<id>/week`. At 390 there is one prompt per screen, one thumb-sized button, no side panel. At 1280 the three prompts sit in one column beside a "from the run log" panel.

**Aaron (Monday 08:20, about 2 minutes)**
- What he sees: prompt 1, "What ran well this week?", already holding a North prefill from the run log: "Three nightly extracts ran on time: holdings, prices, cash. 0 retries." The figure is shown with its source line: "from the run log, 5 to 11 October". He can edit it or clear it.
- What he clicks: "Looks right", then on prompt 2 types "Cash extract waited on the custodian file twice", then on prompt 3 taps "Nothing this week". Then "Send".
- What North does: prefills prompts 1 and 2 only from facts in the run log (job names, run times, failures, retries). A prefill is a draft; the text is Aaron's only after he keeps or edits it. North turns each answer into an item with a kind (ran, broke, thought). It never invents a figure: if the log has no runs for him it writes "Not available yet: no run log entries for your jobs this week".
- Written: two items on the week record, `from = Aaron`, kind and text; `responded_count = 1`; a transcript line per item (file 16).

**Harvey (Monday 11:40, about 3 minutes)**
- Prefill shows the nightly valuation load: "Ran 5 of 5 nights. Slowest: Wednesday, 47 minutes." He adds under "What broke": "Valuation load slow on Wednesday and the fund price file arrived late. Third time this month." Prompt 3: "We still rerun the load by hand when a price is missing."
- Three items written. `responded_count = 2`.

**Mei Ling (Tuesday 09:10, about 2 minutes)**
- Prefill: "Reconciliation ran on all 5 days. 2 breaks cleared the same day." Prompt 2: "Fund price file late again, we waited until 10:30 on Wednesday." (The same cause as Harvey's, worded differently. North will group them later.) Prompt 3 left empty. She taps "Send" and the empty prompt writes nothing.
- Two items. `responded_count = 3`.

**Rahul (Wednesday 16:30, about 2 minutes)**
- Prefill: "Client packs went out on Thursday and Friday, none late." Prompt 2: "I have no view into why the pack template loses the chart colours; it started after the last update." Prompt 3: nothing.
- Two items. `responded_count = 4`. He sent 30 minutes before the close.

Each reporter, after Send, sees one confirmation: "Sent. Katie reads the week on Thursday." and the list of his own items, still editable until Wednesday 17:00. He sees nobody else's items.

Nudges: North sends one reminder on Tuesday 16:00 to anyone who has not sent, and one on Wednesday 15:00. No more.

### 4. The week closes (Wednesday 14 October, 17:00)

- Who: North.
- Screen and route: none for reporters; Katie sees a Pulse line "Week closed: 4 of 4 sent. Digest ready."
- What North does: closes `collect`, locks reporter edits, opens `review`, builds the digest. Entries after 17:00 are refused with "This week has closed. Add it to next week's check-in." The text is kept as a draft for week two (see branches).
- Written: `collect.closed_at`, `review.opened_at`; week record `responded_count = 4`.
- Clock: 17:00 to 17:05.

### 5. North's digest (Wednesday 14 at 17:05, read by Katie Thursday 15 at 08:30)

- Who: North drafts; Katie reads.
- Screen and route: `/centre/intent/<id>/review?week=2026-10-12` (the review screen). At 1280: three lanes, "Ran", "Broke", "On people's minds", with a count strip on top; at 390 the lanes stack and each lane is collapsed to its first three cards.
- What she sees: the count strip "4 of 4 sent, 9 items" (from `responded_count` and `items`). In "Broke", cards grouped by North: "Fund price file arrives late (3 people)" with the three source sentences listed under it, "Cash extract waits on the custodian file (Aaron)", "Pack template loses chart colours (Rahul)". The "Ran" lane holds the run-log facts the reporters kept. "On people's minds" holds Harvey's manual rerun.
- What she clicks: "Open" on a card to read the original words. No other action yet.
- What North does: groups repeats (never hides an original; each item stays visible inside its group), adds a weekly count ("this item has appeared 3 weeks running" only when `weeks` records show it, otherwise nothing), and drafts a suggested fate with a reason for each broke item, marked "North suggests". Ran and thought items carry no suggestion. Anonymous items, if any, show "Anonymous" with no name.
- Written: groups as links between item ids on the week record; the draft fates under `draft_fate` (never overwriting a human choice).
- Clock: Katie's reading takes about 6 minutes.

### 6. The review: a decision per broke item (Thursday 15 October, 08:40)

- Who: Katie, with North's drafts beside each card.
- Screen and route: `/centre/intent/<id>/review?week=2026-10-12`, stage `triage`. Every broke card carries four fate buttons: "Make it a Problem", "Put it on the backlog", "Already handled", "No action needed", and a required field "Why" (one line). Ran and thought cards carry the same buttons, optional.
- Decision 1, fund price file arrives late: Katie clicks "Make it a Problem". North's draft reason: "Three reporters named it and Harvey says it is the third time this month." She edits the reason to "Hits the valuation load and reconciliation both. Needs an owner." North opens the Problem start form pre-filled (what is wrong, where, who feels it) with Harvey named as suggested owner; Katie checks it and clicks "Start Problem".
- Decision 2, pack template loses chart colours: "Put it on the backlog". Reason: "Cosmetic, not blocking. Revisit after the template update." North creates a backlog item (file 21) linked to the week record.
- Decision 3, cash extract waits on the custodian file: "Already handled" (fate `handled`). Reason: "The custodian cut-off change was agreed with Operations last Friday." North checks the claim only against records it has; where it cannot, it says "I cannot confirm this from a record" beside the reason and Katie's word stands.
- Ran and thought items are optional. Harvey's manual rerun (thought) gets "Put it on the backlog" with the reason "Candidate for the Problem on the late price file." The four ran items are left alone. At close, any ran or thought item without a fate is written as `nothing` with the reason "Not reviewed this week".
- What North does: refuses to close the week until every broke item has a fate and a reason. It never picks one.
- Written: each item `fate` (problem, backlog, handled, nothing), `fate_ref` (the new Problem id, the backlog id, or null), `reason`, `decided_by = Katie`, `decided_at`, in `intents/<id>/weeks/2026-10-12.json`.
- Clock: about 12 minutes for Katie.

### 7. The week closure (Thursday 15 October, 08:55)

- Who: Katie signs; North drafts.
- Screen and route: the closure panel from file 09, at `/centre/intent/<id>/close?week=2026-10-12`. Button "Close this week".
- What she sees: North's draft summary: "Four of four sent. Nine items. Two items became one Problem, two went to the backlog, one was already handled, four ran well and were not reviewed this week." Fields "why it happened" and "what came out" are pre-drafted.
- What she clicks: edits one word, then "Close this week".
- What North does: fills `closure.next` from the fates (one `problem`, two `backlog`, one `handled`, each with its ref and reason; the four unreviewed ran items are `nothing`, "Not reviewed this week"), sets the week to closed, closes `triage`, and writes the Pulse lines. Janet's count updates.
- Written: the closed week record; `closure` on the intent for this week; link from the series to the new Problem (`links.to`); transcript and audit lines.
- Clock: about 2 minutes. Review and closure total about 20 minutes with the reading.

### 8. What reporters see next morning (Friday 16 October, 08:00)

- Who: Aaron, Harvey, Mei Ling, Rahul.
- Screen and route: Pulse line on `/` and `/centre/intent/<id>/week?week=2026-10-12` in a read-only reporter view.
- What each sees, only their own items and the fate of each:
  - Harvey: his late-file item, "Became a Problem, you are suggested owner. Reason: Hits the valuation load and reconciliation both." His manual rerun: "On the backlog."
  - Mei Ling: her late-file item, "Joined the Problem on the fund price file." Her ran item has no fate line.
  - Aaron: "Already handled. Reason: The custodian cut-off change was agreed." He sees the reason in Katie's words. His ran item reads "Not reviewed this week".
  - Rahul: "On the backlog. Reason: Cosmetic, not blocking."
- Nobody sees another person's items or reasons for them. They see that the week was read and that something happened to their words.
- What North does: Nira writes one line per reporter. No action is asked of anyone except Harvey, who is nudged to accept or decline the Problem ownership.
- Written: a read mark per reporter (`seen_at`).
- Clock: 30 seconds each.

### 9. Week two opens (Thursday 15 October, 08:00)

- Who: North.
- What happens: a new week file opens by the clock on the next working day after the week one close day (Wednesday 14), even if week one's review were unfinished. The nudge now includes "Last week: one of your items became a Problem" where it is true, and prefill from the run log for 12 to 14 October. Any late draft kept from week one is shown to its author to keep or drop.
- Written: new week shell; the series intent stays `open`; the Problem from week one is a separate intent with its own 5 working day box.
- Clock: instant.

## The branches

**A reporter misses the week.** Rahul does not send by Wednesday 17:00. North has nudged twice. At close it writes `responded_count = 3` with the name of the missing person in the count only (the digest says "3 of 4 sent"). Katie sees "Rahul did not send" and may click "Nudge Rahul for next week". The week is not held open. No empty item is written for Rahul. If nobody sends at all, North closes with "nothing came in" and the counts, per file 02. Janet sees "3 of 4" and nothing more. A person who misses three weeks running is shown to Katie as "Rahul has not sent for 3 weeks" with two buttons: "Ask Rahul if he still takes part" and "Remove from the series". North never removes anyone.

**An item repeats three weeks running.** North compares item groups across the last three week records. On week three the card shows "Seen 3 weeks running" with links to the earlier cards. North raises the suggested fate to "Make it a Problem" and adds "It was set to backlog in week one" if true. If it already has an open Problem, the card says "Already a Problem: <title>" and the button to choose is "Add to that Problem". Katie may still choose backlog or nothing, but the reason is required to say why it keeps coming back. The three-week count is read from records only; the number three is the task's rule and appears under Open questions as a default to confirm.

**The reviewer is away.** On Thursday 08:30 North sees Katie has not opened the digest and has no away status set. It sends one nudge to Katie, then at 14:00 a line to the sponsor or, if none, to Janet: "The Operations week is waiting for its reader." North names no stand-in and the series has no stand-in field (see Open questions). If no one acts by Friday 17:00, North says the week will overrun its time box and offers three choices to Janet: extend the review by a day, close with what we have, or cancel the week with a reason. Whoever picks is recorded in `time_box.extended_by` or `closure`. Week two still opens by the clock.

**The series is paused.** Katie clicks "Pause the series" on the series page with a reason. The current week, if collecting, is closed early and keeps what came in; reviewers still read it. No new week opens on Monday and no nudges go out. The series state shows "Paused since 16 October: holiday week". "Resume" opens the next Monday. Paused weeks are recorded with no items and a note, so counts do not show a missed week as a failure. Only the organiser or Janet may pause or resume.

**An item names a measure outside the reporter's access.** Mei Ling writes "Fund NAV for the family trust looked wrong on Tuesday" and she has no access to that fund's measures. North does not check, quote or show the figure to her. The item is kept as her words only, with no North figure attached and a flag "Mentions a measure you cannot open". In the digest Katie sees the text; if Katie also lacks access North shows "Mentions a measure Katie cannot open" and offers "Ask the owner of that measure to look" which creates a Problem for the measure's owner, with the item text and no figures. Nothing from the restricted measure travels in the prefill, the digest or a Pulse line. The restriction is recorded as a note on the item, not as the data.

## What each person saw in total

Minutes are for the demo week, counted from the first open to the last close, and are estimates to be replaced by recorded times once built.

| Person | Steps | Minutes in the week | What they saw |
|---|---|---|---|
| Katie | 1, 5, 6, 7 (plus Pulse lines) | 3 (setup, once) + 6 + 12 + 2 = 20 in a normal week | All items with names, the digest, North's drafts, every fate she gave |
| Aaron | 2, 3, 8 | 2 + 0.5 = 2.5 | His own two items, his prefill, the fate and reason for his items |
| Harvey | 2, 3, 8 | 3 + 0.5 + 1 for the Problem ownership nudge = 4.5 | His three items, the fate and reason for each, the Problem he is asked to own |
| Mei Ling | 2, 3, 8 | 2 + 0.5 = 2.5 | Her two items, the fate and reason for each |
| Rahul | 2, 3, 8 | 2 + 0.5 = 2.5 | His two items, the fate and reason for each |
| Janet | counts only | 1 | "4 of 4 sent, 9 items, 1 Problem, 2 backlog, 1 handled". No item text, no names on items, no anonymous notes |

Total person-time for the week, reporters plus reader: about 32 minutes, against a one-hour status meeting for five people.

## The records at the end

| Record | Where | Holds | New or existing |
|---|---|---|---|
| Intent (the series) | `intents/<id>/intent.json` | type `pulse`, areas, people, state `open`, close day (Wednesday 14:00), pause history | New (file 01) |
| Week file, 12 October | `intents/<id>/weeks/2026-10-12.json` | `week_key: 2026-10-12`, `opens, closes`, `area`, nine items (kinds ran, broke, thought), `participants_count 4`, `responded_count 4`, every `fate`, `fate_ref`, `reason`, `decided_by` | New (shape in file 02, ruling 17) |
| Closure for the week | `closure` in the week file or `intents/<id>/weeks/2026-10-12.json` | summary, why it happened, what came out, `next`: one `problem`, two `backlog`, one `handled`; four ran items `nothing`, "Not reviewed this week" | New (ruling 19: `handled` is closure next kind) |
| Problem intent | `intents/<problem-id>/intent.json` | opened from the fund price file item; `links.from` points at the series; Harvey suggested owner | New (file 02, Problem) |
| Backlog items (2) | backlog store (file 21) | text, source week and item id, reason | New |
| Transcript lines | file 16 | each entry and each decision, with time and person | New |
| Run log reads | `sh_platform` run log | read only, source of the prefill | Existing |

Nothing is duplicated: the week record points at the run log entries by id and the backlog items point back at the week.

## Test script

Tool: `.venv/Scripts/python .sh-tmp/shot.py <email> <path> <out.png> --width 390`, then the same with `--width 1280`. Use synthetic Ardmore accounts. Run each step at 390 first, read the screenshot against the artboard, then at 1280. Where a click is needed use `--click "text=..."`. Use `--text` to check copy.

| Step | Account and route | Checks at 390 first, then 1280 |
|---|---|---|
| 1 Setup | katie, `/centre/intent/new?type=pulse` | Four questions in order; area list has Operations; close day field accepts Wednesday 17:00; read-back sentence names all four people; no horizontal scroll at 390; "Start the series" is a full-width button |
| 2 Week opens | aaron, `/` | Pulse line reads "Weekly check-in, Operations"; "Start my check-in" present; the word "Pulse" is not used to name this feature; no model or vendor name |
| 3 Entry | aaron, `/centre/intent/<id>/week` | One prompt per screen at 390; prefill text carries its source line and date range; "Looks right" and edit both work; empty prompt 3 writes no item; at 1280 the run log panel sits beside the prompts; after Send the confirmation shows only Aaron's items |
| 3b Privacy | harvey, same route | Aaron's items never appear; Harvey's own three items editable until Wednesday 17:00 and locked after |
| 3c No log | an account with no run entries | Prefill says "Not available yet: no run log entries for your jobs this week" and shows no invented number |
| 4 Close | katie, `/` | Line "4 of 4 sent" matches the week record; a send at 17:01 is refused with the "Add it to next week's check-in" text |
| 5 Digest | katie, `/centre/intent/<id>/review?week=2026-10-12` | Count strip equals items in the record; the late-file group lists three source sentences; "North suggests" label on draft fates; lanes stack at 390, three columns at 1280; originals still reachable inside groups |
| 6 Review | katie, same, click each button | Each broke card has the four fate buttons and a required "Why"; "Close this week" stays disabled until every broke item has a fate and reason; ran and thought items left alone close as `nothing`, "Not reviewed this week"; "Make it a Problem" opens a pre-filled Problem form; backlog button creates one backlog item linked to the week |
| 7 Closure | katie, closure panel | Summary numbers (1 Problem, 2 backlog, 1 handled, 4 not reviewed) match fates; `closure.next` has four entries; Janet's account (next row) shows the same counts |
| 7b Admin | janet, `/centre/intent` | Counts and outcome only; no item text, no anonymous notes; super admin account sees title and state only |
| 8 Next morning | harvey, then rahul, week route | Each sees only own items and fates; Harvey sees the Problem ownership nudge; read mark written |
| 9 Week two | aaron, `/` | New week open on Monday; line mentions last week's result where true; late draft from week one offered to keep or drop |
| Branch: miss | rahul sends nothing | Digest says "3 of 4 sent"; no empty item; Janet sees the count only |
| Branch: repeat | seed three weeks with the same group | Card says "Seen 3 weeks running"; button text switches to "Add to that Problem" if one is open |
| Branch: away | katie idle | Nudge to Katie, then line to the sponsor or Janet; extend, close or cancel offered to Janet; none auto-picked; week two still opens by the clock |
| Branch: paused | katie clicks "Pause the series" | No new week on Monday; paused note shows; counts do not show a miss |
| Branch: restricted | mei ling with a restricted measure in her text | No figure shown to her; flag text present; Pulse line carries no figure |

Pass rule: at 390 and 1280 no text clipped, no horizontal scroll, every button named as above, every number traces to a record or reads "Not available yet", and no em dash or game word appears in the copy.

## Open questions

1. Stand-in reader: should the series allow one, named at setup or by Janet on the day? Until answered there is no field and North names nobody.
2. The three-weeks rule for repeats is taken from the task, not from a contract. Confirm the number and whether it is consecutive weeks or three in four.
3. Who may stop the recurrence besides Katie (file 02 open question 5)? This journey allows Katie and Janet to pause.
4. Minutes in the table are estimates until the build records real times.
5. Ruling 23 binds every broke item to a fate before the week closes, and rules out closing "with what we have" except when ending the series. Clarify how Katie triggers series end vs weekly closure.
