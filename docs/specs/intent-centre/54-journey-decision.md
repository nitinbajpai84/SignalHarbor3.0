# 54. Journey: a Decision, from a closed brainstorm to a recorded choice

Part of: Intent Centre v2. Read with 00-BRIEF (intent record, visibility, North), 03 (chooser), 06 (people), 07 (clock), 09 (closure), 10 (ratings), 20 (links). Synthetic Ardmore family office data only.

## Purpose

This file follows one Decision from the first question to the closed record. It shows what each person sees, clicks and leaves behind, and what North drafts in between. The worked case: a brainstorm closed with the idea "move the monthly fund return report to one agreed set of measures". Janet opens a Decision to choose how. Daniel decides. Nothing here adds a rule. Where the journey needs a figure or a rule that the brief does not give, it is listed under "Open questions" at the end.

Time box is the brief default: 2 working days, extendable once. Agents draft; Daniel, and only Daniel, decides.

## The people (Ardmore synthetic)

| Person | Role in this intent | Why |
|---|---|---|
| Janet | Organiser (`people.organiser`) | Closed the brainstorm; opens the Decision from it |
| Daniel | Decider (`people.decider`, ruling 13; he is also the sponsor of the work, `people.sponsor`) | Sponsor of the work; the only person who picks an option |
| Katie | Adviser (`participants`) | Analyst; knows the measures and the data |
| Harvey | Adviser (`participants`) | Owner of the reports; knows the run and the cost of change |
| Grace | Adviser (`participants`) | Approver; knows the control and sign-off effect |
| Aaron | Affected (`affected`) | Prepares the monthly report today; sees the outcome and its reason, never the advisers' notes |
| Company admin (the Janet account, `company_admin` role; Janet acts as organiser and as admin) | Observer of existence and outcome | May cancel, with a reason; never sees anonymous notes |

North runs the workflow. Lens is not used unless an option names a measure that has no definition (see branch 3).

## The path

Routes follow 00-BRIEF section 10, ruling 1: `/centre/intent/<id>` carries notes, options, decide and record as panels; `/centre/intent/<id>/close` is the only sub-view used. Clock lines are working days from `time_box.starts`.

1. **Start questions, pre-filled from the brainstorm.**
   - Who: Janet. Screen and route: `/centre/intent/new?type=decision&from=<brainstorm id>` (03 chooser, "Start the follow-on", type Decision).
   - Sees: three questions. "What has to be decided?" is pre-filled from `outcome.chosen` of the brainstorm. "Who decides?" has Daniel suggested from the brainstorm's sponsor. "Who advises?" has Katie, Harvey, Grace suggested from the brainstorm's participants. A line reads "Pre-filled from the brainstorm. Change anything."
   - Clicks: edits nothing, presses "Review". Then "Open this decision".
   - North: reads the closed brainstorm record and the thinking kept; drafts the title and the one-line purpose; marks Aaron as affected because his area (Fund Reporting) is on the brainstorm.
   - Written: `intents/<id>.json` with `type: decision`, `state: open`, `links.from = <brainstorm id>`, `time_box` of 2 working days, `areas`, `people`. Stage "Options" opened.
   - Clock: day 0, starts now.

2. **Advisers invited.**
   - Who: Katie, Harvey, Grace receive the invitation; Daniel receives "You decide this".
   - Screen and route: Pulse line, then `/centre/intent/<id>`, which shows the invitation panel first to an invited person who has not answered (06 Screen D).
   - Sees: the question, the decider's name, the deadline "Decision due on <date>", the brainstorm's chosen idea as read-only context.
   - Clicks: "Accept" or "Decline" (an adviser who declines gives one line of reason).
   - North: sends the invitation lines through Nira; nudges anyone who has not answered by the end of day 0.
   - Written: invitation record per person, `people.participants` updated on accept.
   - Clock: day 0.

3. **Advisers add notes.**
   - Who: Katie, Harvey, Grace.
   - Screen and route: `/centre/intent/<id>`, panel "Notes".
   - Sees: the question, a note box titled "Your view, in a few lines", a list of the measures the question touches (from the brainstorm's links and the company catalogue).
   - Clicks: "Add my note" (named) or "Add anonymously" (not shown to Daniel or anyone with a name; D-013 rule applies).
   - North: counts notes; on day 1 at start, if fewer than two advisers have written, it says so to Janet and nudges.
   - Written: `outcome.notes[]` with `by` or `anonymous: true`, text, time.
   - Clock: day 0 to day 1.

4. **North drafts the option cards.**
   - Who: North drafts; Janet reviews.
   - Screen and route: `/centre/intent/<id>`, panel "Options".
   - Sees: two to four cards. Each has a name, a one-line what-it-means, "Who this helps", "Cost to change" (only from a note or record, otherwise "Not available yet: no adviser gave one"), the measures it names as chips, and the notes it came from as small source tags (name or "anonymous"). Cards are marked "Draft by North".
   - Clicks: "Edit card", "Merge two cards", "Remove card" (removed cards are kept in the record with who removed them), "Add my own option".
   - North: reads the advisers' notes, the brainstorm's kept thinking and the records the options name (catalogue entries, a prior charter if any). It never invents a cost or a figure.
   - Written: `outcome.options[]` with `id, name, summary, measures[], sources[], drafted_by: north, edited_by[]`.
   - Clock: day 1.

5. **An adviser adds an anonymous option.**
   - Who: Harvey, who is not sure he wants his name on a view that goes against the report owner team.
   - Screen and route: `/centre/intent/<id>`, panel "Options", button "Add an option".
   - Sees: a short form: name, what it means, a switch "Add without my name".
   - Clicks: switches it on, "Add option".
   - North: adds the card with the tag "Added by an adviser". It does not rank it lower or higher. It strips names from any text it quotes from the anonymous note.
   - Written: option with `anonymous: true`, `by` held only in the sealed field readable by no one in the intent (v1 seal rule).
   - Clock: day 1.

6. **North's recommendation line, with its sources.**
   - Who: North drafts; every person in the intent sees it.
   - Screen and route: `/centre/intent/<id>`, panel "North's suggestion" above the cards.
   - Sees: one line, for example "North suggests option 2, one agreed set of measures with a monthly review." Under it, "Because" with two to four source tags that open the note, record or measure (for example the catalogue entry for the measure in option 2, Katie's note, the brainstorm's chosen idea). If North has fewer than two sources it says "North has no suggestion yet: not enough notes or records." and names what is missing.
   - Clicks: a source tag to open it; "Ask North why" opens a short reply; nothing else.
   - North: drafts after day 1 notes are in or after Janet presses "Ask North for a suggestion". The suggestion is advice and never selects the option.
   - Written: `outcome.recommendation {option_id, because: [source refs], drafted_at}`.
   - Clock: day 1 to day 2.

7. **Daniel decides, with a reason.**
   - Who: Daniel (the confirmer for Decision type, ruling 25).
   - Screen and route: `/centre/intent/<id>`, panel "Decide", reached from the Pulse line "Daniel, this decision is waiting for you".
   - Sees: the option cards side by side (stacked at 390), North's line, each adviser's named notes (anonymous ones marked "anonymous"), the time left.
   - Clicks: chooses a card ("Choose this option"), types the reason (required, at least one sentence), presses "Record my decision". A confirm sheet states "This is recorded in your name." Buttons "Decide later" and "No decision" sit beside it (see branches).
   - North: checks the reason is not empty and that the chosen option is not one that failed the measure check (branch 3). It never fills the reason.
   - Written: `outcome.decided {option_id, by: Daniel, at, reason}`; `state: closing`.
   - Clock: day 2 at the latest.

8. **The decision record.**
   - Who: North drafts; Daniel confirms (the confirmer for Decision type, ruling 25).
   - Screen and route: `/centre/intent/<id>`, panel "Record".
   - Sees: one page: the decision, the options considered (with the unchosen ones and why they were not taken, as Daniel's reason and the advisers' notes), who decided, when, who advised, the brainstorm it came from.
   - Clicks: Daniel presses "Confirm the record" (or "Edit the wording" first).
   - North: drafts the page from the data above; nothing is added that is not in the record.
   - Written: `outcome.record_confirmed {by, at}`.
   - Clock: day 2.

9. **The version note on the measures the option names.**
   - Who: North drafts; Katie confirms because she keeps the measures.
   - Screen and route: `/centre/intent/<id>`, panel "Record", section "Measures this decision touches".
   - Sees: for each measure the chosen option names, the line "Decision <id> chose <option> on <date>" and the proposed version note text. The measure itself is not changed here.
   - Clicks: Katie presses "Add this note to the measure". If she cannot, "Leave it for the owner".
   - North: drafts the note text; points at the catalogue entry through the existing measures route (`/api/intents/measures`, spec 19).
   - Written: a version note on the measure's catalogue entry (a pointer to the decision, never a new definition); `links.to` gets the measure references.
   - Clock: day 2.

10. **The link back to the brainstorm.**
    - Who: automatic; Janet sees it.
    - Screen and route: `/centre/intent/<brainstorm id>` and the decision's page.
    - Sees: on the brainstorm, a line "Decided in <decision title> on <date>"; on the decision, "From the brainstorm <title>".
    - Clicks: the line opens the other record.
    - North: writes both links when the record is confirmed; never before.
    - Written: `links.to` on the brainstorm gets the decision id; the decision's `links.from` was set at step 1. The closed brainstorm's content is untouched.
    - Clock: day 2.

11. **Closure and ratings.**
    - Who: Janet closes (the organiser, ruling 25); Daniel, Katie, Harvey, Grace rate; Aaron receives the outcome.
    - Screen and route: `/centre/intent/<id>/close` (spec 09), then the rating sheet (spec 10).
    - Sees: North's closure draft: summary, why it happened, what came out, next (for this case, kind `initiative` with "Move the report to the agreed measures", reason given). Aaron's Pulse line says what was decided and the reason; not the notes.
    - Clicks: Janet "Close this decision"; each person "Rate this" with 1 to 5 and an optional note, or "Rate without my name".
    - North: drafts the closure; adds the `next` entry; offers "Start the follow-on" on it. Does not rate.
    - Written: `closure`, `state: closed`, `ratings[]`, and `next[]`. Aaron's affected record is stamped as notified.
    - Clock: closes inside day 2; the clock stops.

## The branches

1. **Daniel picks "Decide later".** Sheet asks one reason line. North offers "Extend by 1 working day" once; Daniel confirms. Written: `time_box.extended_by[{by: Daniel, at, reason}]`, `time_box.ends` moved, Pulse line to the advisers "Daniel has more time until <date>". A second "Decide later" is not offered; the sheet says "This decision was already extended once." Only "Decide now" or "No decision" remain.
2. **"No decision", with a reason.** Daniel presses "No decision", types the reason (required). North writes the closure draft with `outcome.decided = null`, `no_decision_reason`, and offers `next` of kind `backlog` or `nothing`. Janet closes as usual. The record shows plainly "No decision was made. Reason: ...".
3. **An adviser has no access to a measure an option names.** On the options page the chip for that measure shows "You cannot open this measure". The card text still shows its name, and the adviser's note on it is allowed. North writes under the card "Not all advisers could open this measure" and lists who could not, as names to Janet and the decider only. North asks Janet to "Give access" (a request to the measure's owner, never a grant). If no one reads it by Daniel's decision, the record says so. Nothing is hidden from the decider.
4. **The time box runs out.** At the end of day 2 (or the extended end) with no decision, North says in a Pulse line to Daniel and Janet: "Time is up." It proposes "Extend" (if not yet used), "Close with what we have" (a no-decision closure), or "Cancel". A named person picks: Daniel for extend or no decision, Janet for close, the company admin for cancel. North never decides on the time box ending.
5. **The company admin cancels, with a reason.** From the intent's page the admin presses "Cancel this decision" and types a reason. Written: `state: cancelled`, `closure.cancel_reason = <reason>`, `closure.closed_by`, `closure.closed_at` (ruling 27). The record stays with its notes and options; advisers and Daniel see "Cancelled by the company admin: <reason>". No ratings are asked.


## What each person saw in total

| Person | Saw | Never saw |
|---|---|---|
| Janet | Everything in the intent except anonymous authors; the unmet access list; the closure draft | Who added the anonymous option |
| Daniel | Options, named notes, anonymous notes without names, North's line and sources, the record, ratings summary | Authors of anonymous notes |
| Katie | Her own and others' named notes, options, the record, the measure version prompt | Anonymous authors |
| Harvey | Same as Katie; his own anonymous option marked "yours" to him only | Other anonymous authors |
| Grace | Same as Katie | Anonymous authors |
| Aaron | That a decision exists, the outcome, the decider's reason, the next step | Notes, other options' wording, ratings |
| Company admin | Existence, outcome, state, cancellation control | Anonymous notes and their authors |
| Super admin | Title, type, state, areas, people count | All content |

## The records at the end

- `intents/<decision id>.json`: type, title, purpose, people, `time_box` with any extension, stages "Options", "Decide", "Record", `outcome` (question, notes, options, recommendation, decided or no-decision with reason, record_confirmed), `closure`, `ratings`, `links.from = <brainstorm id>`, `links.to = [follow-on initiative id, measure refs]`.
- `intents/<brainstorm id>.json`: `links.to` gains the decision id. Nothing else changes.
- The measure's catalogue entry: one version note pointing at the decision.
- Run log entries for each North draft and each human act (who, what, when).
- Nothing is deleted. A cancelled decision keeps its notes and options.

## Test script

Tool: `.sh-tmp/shot.py <email> <path> <out.png> [--width 1280|390] [--full] [--click "text=..."] [--wait ms]`, signing in with the seed account for the person. Paths have no leading slash. Run each step at `--width 1280` and `--width 390`. At 390 check: no horizontal scroll, the primary button visible without scrolling past the cards, option cards stacked, source tags wrap.

Seed state needed: a closed brainstorm with an `outcome.chosen`. Accounts exist in docs/guides/TESTING-INTENT-CENTRE.md lines 13 to 25: Janet `company_admin.ardmore@example.test`, Daniel `sponsor.ardmore@example.test`, Katie `analyst.ardmore@example.test`, Aaron `participant.ardmore@example.test`, Harvey `owner.ardmore@example.test`, Grace `approver.ardmore@example.test`; super admin `platform@example.test`. Company admin steps use Janet's account.

| Step | Account | Path | Checks |
|---|---|---|---|
| 1 | Janet | `centre/intent/new?type=decision&from=<brainstorm id>` | Q1 pre-filled; Daniel and three advisers suggested; line "Pre-filled from the brainstorm"; "Open this decision" disabled until valid |
| 2 | Katie | `centre/intent/<id>` | Question, decider, due date; Accept and Decline; brainstorm idea read-only |
| 3 | Katie, Harvey | `centre/intent/<id>` | Both "Add my note" and "Add anonymously"; an anonymous note shows no name to Daniel |
| 4 | Janet | `centre/intent/<id>` | 2 to 4 cards marked "Draft by North"; empty cost reads "Not available yet"; Merge, Edit, Remove present |
| 5 | Harvey | `centre/intent/<id>` `--click "text=Add an option"` | Switch "Add without my name"; new card tagged "Added by an adviser"; no author on any other screen |
| 6 | Daniel | `centre/intent/<id>` | One line with 2 to 4 sources; with under two sources the line names what is missing; no wording of a score or ranking |
| 7 | Daniel | `centre/intent/<id>` | "Record my decision" disabled until option and reason; sheet says "recorded in your name"; "Decide later" and "No decision" present |
| 8 | Daniel | `centre/intent/<id>` | Unchosen options and reasons shown; "Confirm the record" |
| 9 | Katie | `centre/intent/<id>` | "Add this note to the measure" and "Leave it for the owner"; no definition changed |
| 10 | Janet | `centre/intent/<brainstorm id>` | Line "Decided in ..." opens the decision |
| 11 | Janet, Aaron | `centre/intent/<id>/close`; Aaron's Pulse | Closure draft has summary, why, what came out, next; Aaron sees outcome and reason, not notes; rating sheet with "Rate without my name" |
| B1 | Daniel | `centre/intent/<id>` `--click "text=Decide later"` twice | First extends once and writes `extended_by`; second is not offered |
| B2 | Daniel | `centre/intent/<id>` `--click "text=No decision"` | Reason required; closure shows "No decision was made" |
| B3 | Katie (no access), Janet | `centre/intent/<id>` | Chip "You cannot open this measure"; Janet sees names of those who could not |
| B4 | Daniel | `centre/intent/<id>` after time box | "Time is up" with Extend, Close with what we have, Cancel; North never decides |
| B5 | Janet (company admin account) | `centre/intent/<id>` `--click "text=Cancel this decision"` | Reason required; state cancelled; no ratings asked |

Also check for every screen: console errors printed by the script are empty; no em dashes, no game words, no model or vendor names in copy; every number on screen traces to a record or reads "Not available yet".

## Open questions

- Whether "Decide later" extends by one working day or by another length.
- Whether an adviser may be added after day 0.
- The minimum number of notes before North offers a suggestion (written above as two, which needs approval).
- Whether a version note on a measure needs its owner's consent before it appears.
- Ruling 1 lists no `invitation`, `notes`, `options`, `decide` or `record` view. This file shows them as panels on `/centre/intent/<id>`; spec 06 Screen D and the per-type specs must agree, or ruling 1 must add views.
- The measures route is written as `/api/intents/measures` to follow the API convention; spec 19 must confirm the path.
- Janet's account is the company admin, so one login is both organiser and cancelling admin. Confirm that is acceptable for step 11 and branch 5, or add a second admin account.
