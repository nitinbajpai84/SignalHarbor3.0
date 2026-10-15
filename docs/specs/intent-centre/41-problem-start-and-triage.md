# 41. Problem: start questions, triage and acceptance

Part of: Intent Centre v2. Depends on: 01 (intent record), 02 (type catalogue), 03 (chooser frame), 05 (areas and visibility), 07 (time box), 13 (Pulse lines), 16 (events), 38 (Weekly check-in). Feeds: the Problem stages `find_cause`, `fix` and `confirm` (42), 09 (closure), 21 (backlog).

## Purpose (three sentences)
A person says what is wrong in operations, how hard it bites and what it is about, and North turns that into a Problem intent with a proposed owner. North then drafts a triage note from what the company already knows: similar past problems, related open intents, and the measure's recent alerts and range breaks from Ops. The proposed owner accepts, or passes it with a reason to a named person, so that within hours of the report one named person holds the problem.

This file is canonical for the Problem's five start questions (brief section 10, ruling 2). The statement of the problem is the field `what`.

## Who uses it and when (role, moment, trigger)
| Role | Moment | Trigger |
|---|---|---|
| Reporter (any signed-in person: Aaron participant, Katie analyst, Janet organiser) | Sees something wrong and wants it owned | Chooser tile "Problem", a Weekly check-in item, or an Ops alert |
| Proposed owner (Harvey owner) | Told "A problem is waiting for you" | Pulse line from Nira after the reporter opens the intent |
| Passed-to person (named by Harvey) | Told the same, with the reason | Harvey presses "Pass it on" |
| Company admin | Receives a problem that was passed twice | Second pass |
| Affected people | See that it exists and is owned; read the content only if the organiser switched on "affected people may read" at creation (default off) | Their area or name is tagged |

Agents decide and draft: North asks the start questions, proposes the owner and writes the triage draft. People act at three named moments: the reporter presses "Open this problem", the proposed owner presses "Accept" or "Pass it on", and the owner (or the company admin on a second pass) presses "Extend" if the time box needs it. North never assigns an owner and never accepts for anyone.

## Entry points (every route, link, Pulse line, button that leads here)
| From | What the person sees | Lands on |
|---|---|---|
| Chooser (03), tile "Problem" | Tile "Problem", chip "5 working days" (from 02) | `/centre/intent/new?type=problem` |
| Chooser free text, North proposes "This looks like a Problem" | Button "Yes, a Problem" | same, the typed line is the answer to question 1 |
| Weekly check-in review (file 38, 40), button "Open as a problem" beside an item of kind `broke` | Button on the item row; on click it opens the route on the right | `/centre/intent/new?type=problem&from=<check-in intent id>&item=<item id>`; item text is the answer to question 1 |
| Ops page `/ops` (`ui/src/pages/OpsPage.tsx`, `AlertCard`) | New button "Start a problem" beside "Acknowledge" and "Close"; on click it opens the route on the right | `/centre/intent/new?type=problem&alert=<alert id>`; question 1 prefilled ("<source>: <kind>"), question 2 preselected to the alert's measure or source, question 4 preselected to the alert's source owner |
| Pulse line to the proposed owner | "A problem is waiting for you: <title>" with action "Look at it" | `/centre/intent/<id>` (stage view, which is the triage screen while the Problem is in stage `describe`; see Open questions 1) |
| Pulse line to the reporter after a pass | "Harvey passed your problem to Grace" with action "Open" | `/centre/intent/<id>` |
| Company admin Pulse line | "A problem was passed twice and needs an owner" with action "Look at it" | `/centre/intent/<id>` |

"Pulse" here is the daily Pulse page. The Weekly check-in is a separate type (ruling 3). The manifest declares `centre/intent/new` and `centre/intent/<id>` (spec 03 and 01) for every signed-in company role; the screen itself decides what each viewer sees (default deny for undeclared routes).

## Screens, element by element

### Screen A. Problem start questions (route `/centre/intent/new?type=problem`, the questions step of the chooser)
Spec 03 owns the frame (stepper, summary card, composer, read-back, "Save and leave"). This spec fixes the five questions and the extra controls under the composer. The Problem has five questions, not six (Open questions 2 covers the change to the 02 wording).

**Layout at 1280.** Left two thirds: North's question, the composer and the control for that question. Right third: summary card "Your problem so far". **At 390.** One column; the control sits under the composer; the summary is a bar "Question 2 of 5" that opens a bottom sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Q1 North line "What is wrong?" | agent line | "What is wrong? Give it in one line, then say what you saw." | none | Reporter | Always shown first |
| Q1 field "One line" | field (single line, 140 characters, Open questions 3) | Becomes `title` and `outcome.what` | Saved to the draft on blur | Reporter | Placeholder "For example: Monthly fee file arrives late". Required |
| Q1 field "What you saw" | field (multi-line, 600 characters, Open questions 3) | Becomes `outcome.saw` | Saved on send | Reporter | Required; "Skip" is not offered |
| Q2 North line "Which process or measure is it about?" | agent line | One line, plus "Why I ask": it lets me find the owner and similar problems | none | Reporter | n/a |
| Q2 picker "Process or measure" | grouped list with search | Two groups: "Measures" (catalogue entries from the signed baseline) and "Processes" (the process list). One row each: name, group chip, business owner if known. A row North thinks fits is marked "Suggested" | Click or Enter selects one row; selected row shows above with button "Remove" (clears the pick) | Reporter | "No catalogue yet. Add a line of your own, or pick Not sure." |
| Q2 button "Not sure" | button | Label | Sets `outcome.about = {kind: "unknown"}` and moves on. North then looks for a match from the text in Q1 and offers it in triage | Reporter | Always shown |
| Q3 North line "How hard does it bite?" | agent line | "Did it slow us, stop us, or cost money? Give a count or an amount only if you know it." | none | Reporter | n/a |
| Q3 radio "How hard" | radio group of three | "Slowed us", "Stopped us", "Cost money" (one choice) | Saved to `outcome.bites.kind` | Reporter | Required |
| Q3 field "How many" | number field | Label "How many times or how many items" | Saved to `outcome.bites.count` | Reporter | Optional; empty shows "Not known" in the summary |
| Q3 field "Amount" | number field with unit label from the company profile currency | Label "Amount in <unit>" | Saved to `outcome.bites.amount` and `outcome.bites.unit` | Reporter | Optional; shown only when "Cost money" is chosen; empty shows "Not known"; no currency in the profile shows "Not available yet: the company profile has no currency" |
| Q4 North line "Who do you think owns it?" | agent line | North's proposal as a labelled chip row (see below), then "Pick someone else" | none | Reporter | n/a |
| Q4 chip "Business owner: <name>" | chip | The business owner of the process, from the baseline record for the picked process or measure; label "Suggested from the process map" | Click selects; stores `outcome.proposed_owner.source = business_owner` | Reporter | Hidden when none is on record |
| Q4 chip "Source owner: <name>" | chip | The owner on the pipeline contract of the source feeding the measure; label "Suggested from the pipeline contract" | Click selects; `outcome.proposed_owner.source = source_owner` | Reporter | Hidden when none is on record |
| Q4 chip "Data owner: <name>" | chip | The `owned_by` person of the data node in the map; label "Suggested from the map" | Click selects; `outcome.proposed_owner.source = data_owner` | Reporter | Hidden when none is on record |
| Q4 picker "Pick someone else" | list with search | People in the company profile that the viewer may see | Click selects; stores `outcome.proposed_owner.source = reporter` and `owner_picked_by: reporter` | Reporter | "No people in the company profile yet." |
| Q4 button "I do not know" | button | Label | Leaves the owner empty; North proposes the best chip in triage and the company admin is the fallback (see Rules) | Reporter | Always shown |
| Q5 North line "Which areas are affected?" | agent line | One line, plus North's suggested areas | none | Reporter | n/a |
| Q5 chip picker "Areas" | chip multi-select (the spec 03 areas picker, reused) | The areas of the company; the area of the picked process or measure is marked "Suggested" | Toggle on click or Space | Reporter | "No areas in the company profile yet." |
| Q5 people picker "Who feels it" | grouped list (spec 03 people picker, group Affected only) | Names and teams; at least one is needed | Click adds a name; the "x" on a name removes it | Reporter | "Name at least one person who feels it." |
| Q5 switch "Affected people may read" | switch | Label and one line "Off: they see that it exists, not what is in it" | Saved to `share.who_may_open` setting per spec 05 | Reporter | Off by default |
| Read-back line | agent line | One line after each answer: "So: <answer>. Right?" | Buttons "Yes" (next question) and "Change" (reopens that answer) | Reporter | n/a |
| "Next" | button | Label | Saves the answer and shows the next question; disabled on Q3 until a radio is chosen, on Q4 until an owner or "I do not know" is given, on Q5 until an area and a person are given | Reporter | Disabled until valid |
| Origin banner | panel | Only when arrived from an item or an alert: "Started from: <alert source and kind>" or "Started from a Weekly check-in item" | Button "Remove link" clears `links.from`, `from_item` and `links.alert` | Reporter | Hidden otherwise |
| Review card | panel | Title, `outcome.saw`, `outcome.about`, `outcome.bites`, `outcome.proposed_owner` with its label, areas, affected, "Ends <date>, 5 working days" (date in the company time zone from the profile, else UTC) | Each row has a link "Edit" that returns to that question | Reporter | Shown after Q5 |
| "Open this problem" | button (primary) | Label; spinner while saving | Runs the open (Journey step 4); disabled until Q1, Q3, Q5 are answered, with a line naming the first missing item | Reporter | Disabled until valid |
| "Save and leave" | button | Label | Spec 03 behaviour: draft kept, visible to the reporter only | Reporter | n/a |

Question 4 is deliberately not required: "I do not know" is a valid answer. The people step of spec 03 is not shown for a Problem; Q4 and Q5 fill `people.owner` (proposed) and `people.affected`; the reporter fills `people.reporter` and `people.organiser`. The reporter cannot extend the time box at open.

### Screen B. Triage and acceptance (the stage view at `/centre/intent/<id>` while the Problem is in stage `describe`)
Seen by the proposed owner, and by the reporter in read-only form.

**Layout at 1280.** Top: title, type chip "Problem", state chip "Waiting for <owner>", clock "Ends <date> (<n> working days left)", read from `time_box.ends` and the working-day calendar of spec 07. Left two thirds: the problem as reported (what, saw, bites, about, areas, affected), then North's triage draft in four labelled panels. Right third: the decision card ("Accept" and "Pass it on") and the reporter's name. **At 390.** One column. Order: header, decision card (sticky bar with the two buttons), problem, triage panels (each collapsed to one line with a count read from the matching `triage_note` list).

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Header | heading + chips | Title, "Problem", state chip, clock | none | Reporter, proposed owner, owner, company admin; affected people see this region only (existence, title, purpose, stage, clock, people) unless "affected people may read" is on | n/a |
| "As reported" panel | panel | Reporter name and time; what is wrong (`outcome.what`); what they saw (`outcome.saw`); how hard it bites (`outcome.bites.kind`, count, amount, each "Not known" if empty); about (`outcome.about`, name and group, or "Not sure"); areas; affected people | none | Reporter, proposed owner, owner, company admin (outcome), observers; affected people only when the switch is on | n/a |
| Triage banner | agent line | "North drafted this note. Check it before you decide." with the drafted-at time from `triage_note.drafted_at` | none | proposed owner, reporter | Shown always |
| Panel "Similar past problems" | list, label "Suggested by North" | Up to five closed Problem intents the viewer may open (five is a screen choice, Open questions 4), matched first on the same process or measure, then on the same area and similar wording. Each row: title, closed date, root cause line, fix line, owner. Link "Open" | "Open" goes to `/centre/intent/<id>`; a row the viewer may not open shows title, state and owner only | proposed owner, reporter | "No similar problem on record." |
| Panel "Related open intents" | list, label "Suggested by North" | Open intents (any type) in the same areas or on the same process or measure: title, type, state, organiser | "Open" as above | proposed owner, reporter | "Nothing else open on this." |
| Panel "Recent alerts and range breaks" | list, label "From Ops" | For the picked measure or its source: alerts from `build/alerts.json` (kind, state, opened date, acknowledged by and note) and today's range breaks (measure, latest value if the viewer may see it, usual range basis). Link "Open Ops" | "Open Ops" goes to `/ops` | proposed owner, reporter | "No alerts or range breaks on record for this." When about is "Not sure": "Pick a process or measure to see this." |
| Panel "Terms to define" | list, label "Suggested by North" | Terms in the report that the catalogue does not hold | none | proposed owner, reporter | Hidden when none |
| Panel "Proposed owner" | panel | `outcome.proposed_owner` name, the label of where the proposal came from ("Business owner, from the process map"), and the reporter's pick if different, with both shown | none | proposed owner, reporter | "No owner on record. The company admin was proposed." |
| Link "Why these" | link | One line each on how North matched (same measure, same area, wording) | Expands | proposed owner | n/a |
| Button "Redraw the note" | button | Label | Calls `triage/refresh`; replaces the panels and the drafted-at time | Reporter, proposed owner | Disabled while the note is newer than the last change |
| Button "Accept" | button (primary) | Label | Opens a one-line confirmation "You will own this problem. It ends <date>." with "Yes, I own it" (writes the acceptance) and "Cancel" (closes it) | Proposed owner only | Disabled for anyone else |
| Button "Pass it on" | button | Label | Opens a form: Person (picker, required, not the passer and not the reporter) and Reason (required, one line, minimum 10 characters, Open questions 4). "Send" writes the pass; "Cancel" closes the form | Proposed owner only | Form shows "Name who should own this and say why." |
| Pass history | list | "Harvey passed this to Grace on 8 Oct: This is a Finance Ops file." One row per `passes` entry | none | all who may open the content | "Not passed." |
| Escalation note | agent line | Only after two passes: "Passed twice. The company admin picks the owner." | none | all who may open the content | Hidden otherwise |
| Admin card (after two passes) | panel | Picker "Pick the owner" and button "Assign" | "Assign" writes the acceptance as owner with `assigned_by_admin`; the named person is told and then holds the problem without a further accept | Company admin only | Hidden unless two passes |
| Alert line (only if started from an Ops alert) | line with two buttons | "Also acknowledge the Ops alert?" | "Acknowledge" calls the existing alert acknowledge with the note "Problem opened: <title>"; "Not now" hides the line | Reporter | Hidden otherwise |
| Button "Extend" | button | Label | Spec 07 form: new end date and Reason (required, minimum 10 characters). Allowed once, by the owner only, from acceptance onward (Open questions 5) | Owner only (after acceptance) | Hidden before acceptance and after one extension; after one extension a line reads "Extended once on <date>: <reason>" |
| "Back to the centre" | button | Label | `/centre/intent` | all | n/a |
| Error state | panel | "We could not load this problem. Try again." with "Try again" | Reloads | all | Load failure only |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)
1. The reporter arrives from one of the entry points. If from an alert or an item, North prefilled what it can and says so ("I filled Q1 and Q2 from the alert. Change anything.").
2. North asks Q1 to Q5 one at a time, reads each answer back in one line, and the reporter confirms or corrects. After Q2 North looks up the business owner, the source owner and the data owner and offers the chips in Q4.
3. After Q5 North drafts the title and purpose (from Q1) and shows the review card.
4. The reporter edits if needed and presses "Open this problem". The route writes the intent as `open` with first stage `describe` and `outcome.triage = waiting`. `time_box.starts` is today and `ends` is five working days on (spec 07).
5. **North drafts the triage note** in the same request: it reads closed Problem intents, open intents, and the Ops alerts and range breaks for the measure, and stores the panels with a drafted-at time. If North's drafting is off, North stores the fixed lookups (same measure, same area, alerts for the source) and says "North could not write the note. These are the plain matches."
6. **Nira** places "A problem is waiting for you" on the proposed owner's Pulse (spec 13) and "Your problem is with Harvey" on the reporter's. If no owner was proposed, the line goes to the company admin.
7. The proposed owner opens the intent, reads the problem and the note.
8. The owner presses "Accept" and confirms. `people.owner` is written. North posts "Harvey owns this. Ends 14 Oct." and moves stage `describe` to its working state (42). The reporter gets a Pulse line; affected people get one that says it is owned.
9. Or the owner presses "Pass it on", names a person and gives a reason. The record shows the pass. North tells the named person and the reporter. The named person repeats steps 7 to 9.
10. If the second person also passes, North stops, writes the escalation note and the company admin gets a line. The admin picks an owner; that person is told and holds the problem. Nobody can pass it a third time.
11. If the problem came from an Ops alert, after opening the reporter sees the alert line. Nothing is acknowledged without the click.
12. The reporter or owner presses "Back to the centre" and leaves. North keeps the clock; the owner returns for the Problem stages in 42.

## States and transitions (table: state, who moves it, to what, what is written)
The intent `state` values stay as in the brief. Triage is a sub-state kept in `outcome.triage`. Every transition also appends one line to `intents/<id>/events.jsonl` (spec 16).

| State | Who moves it | To what | What is written |
|---|---|---|---|
| none | Reporter picks the Problem tile or confirms North's proposal | draft | Spec 03 draft record; answers go to `start_answers` and the fields below; `outcome` exists as an object with `problem` empty (ruling 6) |
| draft | Reporter presses "Open this problem" | open, triage `waiting` | `state`, `title`, `purpose`, `areas`, `people.reporter`, `people.organiser`, `people.affected`, `time_box.starts/ends`, `stages[0]`, `outcome.what`, `outcome.saw`, `outcome.about`, `outcome.bites`, `outcome.proposed_owner`, `outcome.triage`, `triage_note`, `opened_by` |
| open, triage `waiting` | Proposed owner presses "Accept" | open, triage `accepted` | `people.owner`, `outcome.accepted_at`, `outcome.accepted_by`, a stage line |
| open, triage `waiting` (pass 1) | Proposed owner presses "Pass it on" | open, triage `waiting` for the named person | `passes: [{from, to, reason, at}]`, `proposed_owner` replaced |
| open, triage `waiting` (pass 2) | Second person presses "Pass it on" | open, triage `escalated` | second pass entry, `proposed_owner: null` |
| open, triage `escalated` | Company admin presses "Assign" | open, triage `accepted` | `people.owner`, `outcome.accepted_at`, `outcome.accepted_by` (admin), `outcome.assigned_by_admin: true` |
| open, triage `accepted` | Owner presses "Extend" (once) | open | `time_box.extended_by` entry `{by, at, reason}` |
| open, triage `waiting` | Reporter cancels from the intent page (spec 01) | cancelled | `closure.next [{kind: nothing, reason}]`; the reason is kept and the intent shows in Past (ruling 14) |
| open, triage `waiting` for 2 working days | Nobody | open | Nothing written; North flags it to the reporter and the admin (Open questions 6) |

## Records read and written (file or route, fields; mark Existing or New)
| Item | Read or write | Fields | Status |
|---|---|---|---|
| `intents/<id>/intent.json` through `sh_platform/jsonfile.py` | write, read | Intent record plus the fields below | New file, Existing helper |
| `intents/<id>/events.jsonl` (spec 16) | write | One line per transition and pass; the record holds counts only | New |
| `POST /api/intents`, `PATCH /api/intents/<id>`, `POST /api/intents/<id>/open` (defined in spec 03) | write | Problem answers | New (routes defined in spec 03, reused here) |
| `POST /api/intents/<id>/triage/accept` | write | `people.owner`, `accepted_at`, `accepted_by` | New |
| `POST /api/intents/<id>/triage/pass` | write | `passes[]` entry `{from, to, reason, at}` | New |
| `POST /api/intents/<id>/triage/assign` | write | `people.owner`, `assigned_by_admin` (company admin only) | New |
| `POST /api/intents/<id>/triage/refresh` | write | Redraws `triage_note` (reporter or proposed owner, once the note is older than the last change) | New |
| `GET /api/company/build/ops` and `build/alerts.json` (`sh_platform/build/ops.py`, `alerts.py`) | read | `alerts[]` (id, kind, source, measure, owner, opened, state, by, note) and `range_breaks[]` (mart, source, owner, latest, basis) | Existing |
| `POST /api/company/build/alerts/{alert_id}/ack` | write | Acknowledge with a note, only on the person's click | Existing, called unchanged |
| Graph nodes and edges (`sh_platform/graph/read.py` `graph_for`; `build.py` Process and Measure nodes, `owned_by` edges) | read | Measures, processes, owners | Existing |
| Pipeline contracts `build/pipelines/*.json` | read | `source`, `owner`, `marts` | Existing |
| Company profile people, areas, currency and time zone (`profile/api.py`, `profile/view.py`) | read | Names, teams, areas; filtered per viewer | Existing |
| Closed and open `intents/*/intent.json` | read | `type`, `state`, `title`, `areas`, `outcome.about`, `root_cause`, `fix`, `people.owner` | New |

`outcome` shape for a Problem (ruling 16):
`{what, saw, about: {kind: measure|process|unknown, id|null, name|null}, bites: {kind: slowed|stopped|cost_money, count|null, amount|null, unit|null}, accepted_at|null, accepted_by|null, assigned_by_admin: bool, triage: waiting|accepted|escalated, proposed_owner: {name, source: business_owner|source_owner|data_owner|reporter|admin, label}|null}`.
The owner is held in `people.owner`, not in the outcome (ruling 13). `what` is the canonical name of the problem statement (ruling 2); 02's `statement` is renamed to `what` in 02.

## Fields this feature adds to the intent record
| Field | Meaning |
|---|---|
| `people.reporter` | Named slot: the person who reported the problem (ruling 13); also set as `people.organiser` |
| `people.owner` | Named slot: who holds the problem, set on accept or assign (ruling 13); empty until then |
| `outcome.what, saw, about, bites` | The report as the reporter gave it (ruling 16) |
| `outcome.accepted_at, accepted_by, assigned_by_admin` | When and by whom the problem was taken (ruling 16) |
| `outcome.proposed_owner` | The owner North proposed, with its source label; replaced on each pass (ruling 16) |
| `outcome.triage` | `waiting`, `accepted` or `escalated` (ruling 16) |
| `triage_note: {drafted_at, similar: [{intent, why}], related: [{intent, why}], alerts: [{alert_id, kind, state}], range_breaks: [{mart, basis}], terms: [], drafted_plainly: bool}` | North's draft, stored by reference (ids and reasons, not copies of other intents or of Ops rows) |
| `passes: [{from, to, reason, at}]` | Every pass, kept for the record |
| `owner_picked_by` | `reporter` when the reporter chose the owner, else absent |
| `links.from` | Existing field; set to the Weekly check-in intent id |
| `links.alert: alert id or null` | The Ops alert this problem came from |
| `from_item` | Check-in item id when started from a check-in item |

No field from brief section 3 is renamed.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)
- **North, asking.** Five questions, one at a time, read-back after each. Prefills from an alert or item. Person acts: confirms each answer.
- **North, proposing the owner.** From the picked process or measure it reads three records and labels each: the business owner (baseline), the source owner (pipeline contract), the data owner (map `owned_by`). It proposes one, in that order of preference (Open questions 7), and shows the others. It never writes the owner. Person acts: the reporter picks a chip, picks someone else or says "I do not know"; the proposed owner accepts or passes.
- **North, triage draft.** At open, writes the panels, each marked as suggested or as from Ops. It uses counts and names from records only; a figure it cannot trace is shown as "Not available yet". Person acts: the proposed owner reads and decides; either the reporter or the proposed owner may press "Redraw the note".
- **North, after a pass.** Tells the named person and the reporter, and stops after the second pass. It does not choose the admin's pick.
- **North, clock.** Says whether the owner has accepted (days in Open questions 6); proposes "extend", "close with what we have" or "cancel" as the end nears (spec 07). Person acts: the owner picks.
- **Lens.** Not used. When the reporter's line names a term the catalogue does not hold, North lists it under "Terms to define"; a definition draft belongs to later stages.
- **Nira.** Places the waiting, passed and escalated lines on the Pulse page (spec 13). Does not write to the intent.

## Rules (visibility, time box, who may do what)
- A draft is visible to its creator only (ruling 14). Once open, the title, purpose, state, areas, clock, people and organiser (the reporter) are visible to everyone tagged to the areas, including affected people.
- Content, including the triage note, opens only for the reporter, the proposed or acting owner, participants and observers (observers read, never write), and anyone a share names. Affected people read content only when the organiser switched on "affected people may read" at creation (default off) or when a share names them (ruling 4). They never see the triage note.
- The company admin sees existence and the outcome, never anonymous notes, and not the triage note unless named. On a second pass the admin reads the outcome to pick an owner (Open questions 8).
- The super admin sees existence only: title, type, state, areas, people count, dates and time box status, read through the kernel; titles are hidden when the company switch "titles private to the company" is on (ruling 5).
- The Ops panel shows a figure only to a viewer on that measure's access list (`ops.py` rule, `view.sees_rule`); otherwise "Hidden for your role".
- Only the proposed owner may Accept or Pass it on. Only the company admin may Assign, and only after two passes. The reporter cannot accept for another person.
- A person may pass to anyone in the company profile except themselves and the reporter. The reason is required.
- Two passes at most; the second moves the problem to the company admin; no third pass (Open questions 9).
- Accepting makes the person the owner of record. The pass history stays.
- Time box: 5 working days from open (default from the catalogue, 02). It does not restart on a pass. The owner may extend once, with a reason. A second extension is refused with "This problem has been extended once. Close it, or ask the company admin." (Open questions 5).
- Times and dates use the company time zone from the profile, else UTC.
- Sharing is by the reporter only, spec 11. Ratings do not apply here (spec 10).
- Copy: no game words, no model or vendor names, British spelling, no em dashes.

## Counters and measures of this feature (numbers only, each traced to a record)
Counts are exact. A median or any per-person figure shows "Fewer than five" below five records (ruling 8).

| Measure | Traced to |
|---|---|
| Problems opened, per month | count of `intents/*/intent.json` with `type: problem` and `opened_by` set, by `time_box.starts` |
| Problems waiting for an owner | count with `outcome.triage` `waiting` or `escalated` |
| Median time to acceptance | `accepted_at` minus `stages[0].opened_at`; "Fewer than five" below five accepted |
| Accepted on first offer | count with `accepted_by` equal to the first `proposed_owner` and `passes` empty, over all accepted |
| Passed once, passed twice | count of `passes` length 1 and 2 |
| Problems started from an alert | count of `links.alert` not null |
| Problems started from a check-in item | count of `from_item` not null |
| Accepted, by proposed owner source | count of accepted by `proposed_owner.source`; "Not available yet" while none is accepted |
| Reporter's own pick | count where `owner_picked_by: reporter` is set |
| Counts on the triage screen (rows per panel, passes, "n working days left") | length of the matching `triage_note` list, `passes`, and `time_box.ends` with the spec 07 calendar |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)
Searches run: `graft ask` on Ops alerts and acknowledge, graph comments and decide, the chooser start questions, and owner fields in the graph and pipeline contracts. Then read the files below; all paths were checked and exist.

| Existing | Decision |
|---|---|
| `sh_platform/build/ops.py` (`build` L72, `_build_open` L77, `_act` L127, routes `get_api_company_build_ops` L122-L123, `ack` L135-L137) and `sh_platform/build/alerts.py` (`sync` L25, `act` L40; states `open`, `acknowledged`, `closed`) | Reused unchanged for the triage panel (read) and for the optional acknowledge (call). Reshaped idea: the alert's `{state, by, at, note}` is the pattern for the pass and accept entries. Limit found: `sync` drops an alert whose cause has cleared, so the panel shows current alerts only (Open questions 10) |
| `ui/src/pages/OpsPage.tsx` (`AlertCard` L50; "Acknowledge" L72) | Reshaped: one new button "Start a problem" in the same row, linking to the chooser with `alert=<id>`. No new alert screen |
| `sh_platform/graph/comments.py` (`KINDS` L23, `_may_decide` L72, `_line` L94, `decide` route L135) | Reshaped, the decide pattern. An item opens, the named owner (or the steward) decides, the state line says who and what. "Accept" is like `accepted`, "Pass it on" like `declined` with the reason as the answer and a named next person; the company admin takes the place of the steward after two passes. Not reused as a store: graph comments belong to map nodes, an intent record is not a node |
| `ui/src/pages/CentrePage.tsx` and `ui/src/modules/m1_intent/private_room/PrivateRoomScreen.tsx` (`RoomView` L111-L318), through spec 03 (areas and people pickers, composer) | Reused through spec 03. Only the question list, the owner chips and the "bites" control are new |
| `sh_platform/graph/build.py` (Process nodes L294-L301 with the Process owner column; `owned_by` edges L169, L187, L265, L280, L303), `sh_platform/graph/build_nodes.py` L106 (`owned_by` on the pipeline), `sh_platform/graph/read.py` | Reused (read only) for the catalogue, the process list and the three owner proposals. The column "Process owner" is shown as "Business owner" (ruling 11). No new owner table |
| `sh_platform/profile/api.py`, `sh_platform/profile/view.py` (`read`, `sees_area`, `sees_rule`) | Reused unchanged for people, areas, currency, time zone and the hidden-figure rule |
| `sh_platform/jsonfile.py` (`read_json_strict`, `write_json_atomic`, `lock_for`) | Reused for `intents/<id>/intent.json` |
| `sh_platform/pulse/__init__.py` and spec 13 | Reused through spec 13; this feature supplies the line kinds `problem_waiting`, `problem_passed`, `problem_escalated` |
| Genuinely new | The five Problem questions and their fields, the owner-source chips, the triage view and note, four triage routes, the pass and escalation rule |

## Not in this feature
- The stages `find_cause`, `fix` and `confirm`, and the Problem closure (42 and 09).
- Turning a problem into an Initiative.
- Setting the fate of the Weekly check-in item when a problem is opened from it (file 38 and 40 own the item and its fate).
- Editing or adding alerts, processes, measures or owners (Ops, M2 and the profile own them).
- Sending messages outside the company. Any message North drafts is text for a person to send.
- Share links (spec 11) and ratings (spec 10).

## Open questions
1. Routes. The triage screen is the stage view at `/centre/intent/<id>` while the Problem is in `describe`, so no new page route is needed. If a separate `/centre/intent/<id>/triage` view is wanted it must be added to the view list in ruling 1. The extra query parameters `item` and `alert` on the chooser route are not named in ruling 1; confirm them.
2. Spec 02 still lists six Problem questions with `statement`. Per ruling 2 it is corrected to these five and to `what`. Proposed: keep "what was tried" as an optional note in the `find_cause` stage. Confirm.
3. Character limits (140 for the line, 600 for what was seen) are screen choices, not rules.
4. "Similar" matching (same measure or process first, then same area and word overlap), five rows at most, and the 10-character minimum for a reason are proposals. No word-overlap threshold is set.
5. Extension: once, with a reason, is proposed; the brief records `extended_by` as a list and does not cap it. Does the clock stop while waiting for acceptance? Proposed: no.
6. If the proposed owner has not responded in two working days, North flags the reporter and the company admin and does not reassign. Days for North's acceptance check (proposed: day 1 and day 3) are not set. Needs a decision.
7. The order of preference for the proposed owner (business owner, source owner, data owner) is a proposal.
8. May the company admin read the open outcome (what, saw, about) to pick an owner? The brief gives the admin existence and outcome; whether an open intent's outcome counts is unclear.
9. The cap of two passes before the company admin is a proposal.
10. How far back should the Ops panel look? Today `build/alerts.json` keeps only alerts whose cause is current. Proposed: show what exists and say so; keep a history of closed alerts in a later change.
11. Which currency and unit label does the Amount field use? Proposed: the company profile's currency; "Not available yet" if none is set.
12. Can the reporter also be the proposed owner? Proposed: yes ("I own it"), then triage is `accepted` on open and no acceptance is asked for.
13. May a proposed owner pass to someone in another area? Proposed: yes, with a reason; the intent areas do not change.
