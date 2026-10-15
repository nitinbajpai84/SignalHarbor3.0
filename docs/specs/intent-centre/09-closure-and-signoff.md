# 09. Closure and sign-off

Part of: Intent Centre v2. Depends on: 10 (ratings), 40 (week review and close), the intent record and time box in 00-BRIEF, the per-type outcome files, the Pulse page and home page files. Feeds: the home page past list, Pulse lines, the backlog (21), Build (hand-off of a closed Initiative, 33).

## Purpose (three sentences)

Every intent ends the same way, whatever its type: one closure screen that says why it happened, who opened it, who took part, what came out, what happens next and who signed it. North drafts the screen from records; people confirm, sign and rate. After closure the intent is kept, read-only, and its outcome is visible to everyone tagged to its areas.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Sponsor (Daniel) | Closure of an Initiative after charter signature | Gets "waiting for you" from Nira; signs on the closure screen, or by the approver link if not signed in. Organiser cannot Close without sponsor approval. |
| Decider | Closure of a Decision | Gets "waiting for you" from Nira; decides on the closure screen. Organiser cannot Close without decider action. |
| Owner (Harvey) then Reporter | Closure of a Problem | Owner confirms the fix; reporter confirms the closure. Organiser cannot Close without both actions. |
| Organiser (Janet) | After per-type confirmer acts (or none needed) | Presses "Close this intent" on the intent page after reviewing North's draft and the confirmer's action. State moves from `closing` to `closed`. |
| North (agent) | Charter signature (Initiative), every stage complete (others), or time box ended | For Initiative: moves to `closing` at charter signature. For other types: writes the closing prompt once stages are complete or time box ends; once organiser opens `closing`, drafts the closure. Never closes by itself. |
| Participant (Aaron, Katie) | After closure | Gets the rating prompt (spec 10) except in a Weekly check-in; reads the closed view |
| Observer | After closure | Reads what a participant reads; never writes, signs or rates (brief ruling 4) |
| Affected people, area members | After closure | See the outcome in the closed view and on the past list; open content only as the visibility rule allows |
| Company admin | Any time | Sees existence and outcome of every closed intent, never anonymous notes |
| Super admin | Any time | Sees existence only at `/centre/control/intents`, never the closure content |

## Entry points (every route, link, Pulse line, button that leads here)

- Button "Close this intent" on the intent page header (organiser only, shown when state is `closing` and the per-type confirmer has acted where required; spec 01 owns the page).
- Button "Close this intent" becomes available once the per-type confirmer acts: sponsor signs (Initiative), decider decides (Decision), owner and reporter confirm (Problem), or immediately for Brainstorm and Weekly check-in.
- North's closing prompt on the intent page and in Nira's "what is waiting for you": "The time box ends <date>. North has drafted the closure. Review it." For Initiative: "Charter is signed. The intent is now closing. Review the closure."
- Nira line for the sponsor/decider/owner: "<Title> is ready for your action." Once acted: organiser can now close.
- Pulse page line for a closed intent (see Screens, section C).
- Home page past list row and `/centre/intent/past` (see Screens, section C).
- Share link `/centre/intent/<id>/share` (organiser creates it; opens the closed view read-only; the visitor entry stays `POST /api/modules/m1_intent/shared/view`).
- Approver link `/approve/<token>` when the sponsor, decider or approver (Grace) signs without signing in (reuses the existing charter approver page route).
- Routes: `/centre/intent/<id>/close` (closure screen while `closing`); `/centre/intent/<id>` (the intent screen; once `closed` or `cancelled` it opens the closed view by default).

## Screens, element by element

### A. Closure screen (route `/centre/intent/<id>/close`)

Layout at 1280: top bar; header strip (title, type chip, state chip "Closing", time box line "ends <date>" in the company's time zone from the profile, else UTC; "Close with what we have" and "Cancel this intent" as secondary buttons, right aligned); two columns. Left, 8 of 12: "Why it happened", "What came out", "What happens next". Right, 4 of 12: "Who took part", "Signature", "Rate it" panel (rating panel is spec 10, shown here once the intent is closed). Footer bar with "Back to the intent" and "Close this intent".

Layout at 390: one column in this order: header strip, why, what came out, next, signature, who took part. Secondary buttons move into an overflow menu "More". The footer bar is sticky with one button "Close this intent".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Summary draft | agent line (editable text) | North's drafted summary, 3 to 6 sentences. Each sentence ends with a small source chip (for example "Wall, 14 cards", "Charter v2", "Session 3 Oct") | Click a chip opens the record it came from in a side panel. Organiser edits a sentence in place; an edited sentence loses the "Drafted by North" mark and keeps the author and time | Organiser edits; participants, observers, sponsor read; affected people read only if "affected people may read" is on | "North has not drafted the closure yet. Draft it" button; if nothing was recorded: "Nothing was recorded in this intent, so there is nothing to summarise." |
| Draft it / Draft again | button | North's drafting action | Calls `POST /api/intents/<id>/closure/draft`; "Draft again" keeps every sentence the organiser edited | Organiser | Draft it shown only when no draft exists |
| Source chip | chip | Record name and count, from the intent record or the record it points at | Opens the source in the side panel (read-only) | Whoever may open the content | A sentence with no source chip is not allowed; North drops it |
| Why it happened | panel | `purpose` plus North's one-line reason, with who opened it and when ("Opened by Janet on 1 Oct") | Edit pencil on the reason line (organiser) | Everyone tagged to the areas | "No purpose was written when this was opened." Organiser must add one before closing |
| Outcome block | panel | One block per type, see table below | "Edit outcome" (organiser) returns to the stage that owns the field; the block itself is not edited here | Participants, observers, share-link people, company admin; area members and affected people once closed | "No outcome recorded yet." Closing is allowed only through "Close with what we have" |
| Edit outcome | button | Label "Edit outcome" | Navigates to the stage view that owns the missing field | Organiser | Hidden when the outcome is complete |
| Next list | list | One row per next item: kind chip (Initiative, Backlog, Problem, Nothing), title, reason, target ref | "Add next" (organiser) opens a small form: kind, title, reason (required). Remove icon per row | Everyone who may open the content | "Nothing follows from this intent." with the choice "Nothing" needing a reason |
| Add next | button | Label "Add next" | Opens the form (kind, title, reason); Save adds a row, Cancel closes it | Organiser | Always shown while `closing` |
| Remove icon | button (icon) | Per next row | Removes that row from the draft | Organiser | Not shown when no rows |
| Next row reason | field | One sentence, required for every kind including "Nothing" | Edit in place | Organiser | Red line "Add the reason" and the Close button stays off |
| People list | list | Name, role (organiser, sponsor, decider, owner, participant, affected, observer), contribution count and the count's unit | Click a name filters the source side panel to that person's items (only non-anonymous) | Participants, observers and affected people; area members see the count of people only (open question 7) | "No one took part besides the organiser." |
| Contribution count | chip | Number of cards, replies, votes or comments by that person, from the records. Under five records it reads "Fewer than five" (a per-person figure, brief ruling 8). Anonymous items are counted in a separate line "Anonymous contributions: n" with no names | None | As above | "Not available yet: this type records no contributions" |
| Signature line | panel (reused Signature) | "Sponsor: Daniel" with state waiting or signed, date and how (in the room, by the approver link); "Decider: <name>" for Decision; "Owner: <name>, Reporter: <name>" for Problem | Sponsor/decider/owner sees "Sign/Decide/Confirm closure" and presses it. Organiser sees "Send to <name> by link" and "Withdraw link" | Signer signs; organiser sees state; participants and observers see state | Types with no signature: panel shows "This type needs no signature. Closed by <organiser>." |
| Sign closure | button | Primary, signer only | Writes the signature (see States); the button becomes the signed line. For Problem, a second "Confirm closure" appears for reporter after owner acts | Sponsor (Initiative), decider (Decision), owner then reporter (Problem); company admin where `sign_roles` allows | Disabled with "Check the outcome lines first" until the outcome block has been scrolled and every next row has a reason |
| Send to approver | button | Names the person (Grace) | Creates the link, shown once, with copy button and expiry | Organiser | Hidden when no approver is named: "Name an approver in the intent first" |
| Withdraw link | button | Label "Withdraw link" | Revokes the link; the signature line returns to waiting | Organiser | Hidden when no link is out |
| Close this intent | button | Primary, footer | Runs the closing checks, then moves state to `closed`. Enabled only after per-type confirmer acts (or none needed). | Organiser only; North only proposes | Disabled with the first unmet check named beside it, or with "waiting for <role>" until the confirmer acts |
| Back to the intent | button | Footer, secondary | Returns state to `open` or `in_session`; the draft closure is kept as draft | Organiser | Always shown while `closing` |
| Close with what we have | button | Secondary, header | Opens a dialog (see journey step 9). Writes `closure.incomplete = true` with the reasons | Organiser | Shown only when the outcome block has a missing required field |
| Cancel this intent | button | Secondary, header | Opens a dialog with required reason, then moves to `cancelled`; writes `closure.cancel_reason` with `closed_by` and `closed_at` | Organiser | Reason field empty keeps the confirm button off |
| Extend time box | link | "Extend by n working days" in the North banner | Asks for a reason, then writes `time_box.extended_by` with by, at, reason | Organiser | Shown while the banner is shown; any limit on extensions is open question 3 |
| North banner | agent line | "This will not finish inside its time box. Options: extend, close with what we have, cancel." with the person who picks named | Each option is a button; nothing happens until a named person presses one | Organiser, sponsor | Not shown when on time |
| Send-back note | panel | The approver's comment, `closure.send_back` | None | Organiser, signer | Not shown when there is no send-back |

Outcome block per type (data comes from the type's own spec; this screen only reads it):

| Type | Block shows | Required to close complete |
|---|---|---|
| Initiative | Charter version and its signature state; the artefacts as chips (business glossary, technical glossary and catalogue, process map, data sources map) each "Confirmed", "Draft" or "Not started"; build-ready flag (yes, no, reason); hand-off to Build | Signed charter; build-ready flag set |
| Brainstorm | The chosen idea, runners-up with vote counts, the thinking kept (link to the session record) | One chosen idea |
| Weekly check-in | The week record at `intents/<id>/weeks/<week_key>.json`: items by fate (problem, backlog, handled, nothing) with the reason each | None beyond the week's own rules (spec 40): a `broke` item needs a fate before the week closes; undecided `ran` and `thought` items close as nothing with reason "Not reviewed this week" |
| Problem | Root cause, fix, owner, date fixed, verified by | Root cause, fix, owner |
| Decision | The decision, options considered, who decided, why | Decision text, decider, why |

A Weekly check-in never reaches `closing` week by week. A new week opens by the clock on the next working day after the close day, even if the review is unfinished (spec 40 owns this). This screen closes the whole series only when the organiser ends it. The series is not rated and neither is any week, so no "Rate it" panel and no rating prompt appear for this type.

### B. Closed view (route `/centre/intent/<id>`, state `closed` or `cancelled`)

The same screen as A, rendered from the stored closure block. Layout at 1280 and 390 are as A.

Differences, element by element: the header chip reads "Closed <date>" (or "Cancelled <date>"); the footer bar is gone; every pencil, "Add next", remove icon, "Draft it", "Edit outcome", "Close this intent", "Close with what we have", "Cancel this intent", "Extend time box" and "Send to approver" is not rendered, not just disabled. The source chips still open the side panel. The rating panel (spec 10) and "Share" button (organiser) remain, except for a Weekly check-in, which has no rating panel. Cancelled intents show a "Why it was cancelled" panel in place of the outcome block. An incomplete close shows a "Closed with what we have" strip listing what was missing and the reason given.

| Element | Kind | Shows | On click | Visible to | State when empty |
|---|---|---|---|---|---|
| Closed strip | panel | "Closed by Janet on 7 Oct. Signed by Daniel on 7 Oct." or "Closed with what we have: root cause was not found. Reason: ..." | None | Everyone who sees the intent | Not shown for a clean close with no signature |
| Why it was cancelled | panel | `closure.cancel_reason`, who cancelled and when | None | Everyone who sees the intent (cancelled intents show in Past) | Not shown unless cancelled |
| Share | button | Creates or shows the share link, names who may open it | Organiser picks people; link opens this view read-only | Organiser | "Not shared" |
| Open in Build | link | For a closed, build-ready Initiative: link to the hand-off | Goes to `/centre/build/gap-analysis?from=<id>` (room 0 of Build) | Organiser, sponsor, participants | Hidden when the build-ready flag is no |
| Linked intents | list | `links.from` and `links.to` with title and state | Opens that intent if the viewer may; "See the chain" opens `/centre/intent/past/<id>/chain` | As the source intent | "No linked intents." |
| Rating summary | panel (spec 10) | Ratings aggregated from three; anonymous by default; no per-person averages | None | Organiser, sponsor | "Not shown until three people have rated." Not shown for a Weekly check-in |

### C. How closure appears elsewhere

| Surface | What it shows | On click | Visible to | State when empty |
|---|---|---|---|---|
| Pulse page line | "<Title> closed. <One-line outcome>. Next: <first next item>." with kind chip | Opens the closed view | Area members, affected | Pulse page says "Nothing closed this week." |
| Home page past list row (`/centre/intent` and `/centre/intent/past`) | Title, type chip, closed date, one-line outcome, signed mark (tick and signer name) where the type needs one, "incomplete" tag where applicable | Opens the closed view | Area members see the row; content opens per the visibility rule | "No past intents yet in your areas." |
| Past list filter | chips: All, Initiative, Brainstorm, Weekly check-in, Problem, Decision, Cancelled | Filters the list | As above | Filter with no rows: "Nothing of this type in your areas." |
| Nira "waiting for you" | Signer's signature request, organiser closing prompt, participant rating prompt (not for a Weekly check-in) | Opens the closure screen or rating panel | The person named | "Nothing is waiting for you." |

One-line outcome: the first sentence of the type's outcome as stored, never regenerated for the list.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. For Initiative: North watches the charter. At charter signature, the intent moves to `closing`. The sponsor is told by Nira: "Charter is signed. The closure is ready for your review."
2. For other types: North watches each open intent. When every stage of the type is complete, or the time box has ended, North writes a prompt to the organiser and Nira lists it under "waiting for you".
3. The per-type confirmer is told by Nira: "This intent is ready for your action." Sponsor signs (Initiative), decider decides (Decision), owner then reporter confirm (Problem), or no one for Brainstorm and Weekly check-in.
4. North drafts the closure from the records: summary sentences each with a source chip, the reason, the outcome block, people with contribution counts, and a proposed next list, each with kind and reason. Drafting runs once; the organiser can press "Draft again", which keeps every sentence the organiser edited.
5. The organiser reads the summary and presses source chips to check them. A sentence the organiser cannot trace is deleted, not kept.
6. The organiser reviews the next list. For each row they confirm, edit or remove it. Every row needs a reason, including "Nothing".
7. The per-type confirmer acts: signs, decides, or confirms. If not signed in, the organiser presses "Send to <name> by link" and the person opens `/approve/<token>`, reads a one-page view of the closure, and approves or sends it back with a comment. A send-back returns the intent to `closing` with the comment shown at the top. An agent never signs.
8. With the confirmer's action done (or none needed) and the checks met, the organiser presses "Close this intent". The checks, in order: purpose present, outcome required fields present (or "Close with what we have" chosen), every next row has kind and reason, confirmer has acted where required.
9. The system writes the closure (see States). North then creates the links (initiative or backlog items, problem records) from the next list. Nira sends the rating prompt to every participant, except for a Weekly check-in.
10. Close with what we have: the organiser presses the button, sees the list of missing required fields, writes one reason, and confirms. The closure is confirmed by the same rule as a complete one (the confirmer still acts where needed) and carries `incomplete: true`.
11. Cancel: the organiser presses "Cancel this intent", writes a reason, confirms. The state moves to `cancelled`; the reason is recorded in `closure.cancel_reason`; no next list is required but the organiser may add one.
12. Everyone leaves to the closed view at `/centre/intent/<id>`; participants rate (spec 10) and the organiser may share the link.

## States and transitions (table: state, who moves it, to what, what is written)

| State | Who moves it | To | What is written |
|---|---|---|---|
| `open`, `in_session` (non-Initiative) | North proposes; organiser presses "Close this intent" | `closing` | `state`, `closing_started_at` (stages stay open until the final close) |
| `in_session` (Initiative only) | North moves at charter signature | `closing` | `state`, `closing_started_at` |
| `closing` | Organiser presses "Back to the intent" | `open` (or `in_session` if it was) | `state`; the draft closure is kept as draft |
| `closing` | Signer signs (or approver approves) | `closing` (signature recorded) | `closure.signature` {name, account_id, at, how: room or approver} |
| `closing` | Approver sends back | `closing` | `closure.send_back` {by, at, comment}; signature cleared |
| `closing` | Organiser presses "Close this intent" after checks and confirmer acts | `closed` | `closure` block, `state`, `stages[*].closed_at`, `links.to`, backlog items, one line to `events.jsonl` |
| `closing` | Organiser presses "Close with what we have" and confirms | `closed` | as above plus `closure.incomplete`, `closure.missing`, `closure.incomplete_reason` |
| `draft`, `open`, `in_session`, `closing` | Organiser cancels with reason | `cancelled` | `state`, `closure.cancel_reason`, `closure.closed_by`, `closure.closed_at`; `outcome` stays as it stood |
| `closed`, `cancelled` | No one | No move | Nothing. Re-opening is not offered; a follow-up is a new intent linked by `links.from` |

A draft intent is visible only to the person who started it (brief ruling 14); only that person can cancel it. A cancelled intent keeps its reason and shows in Past.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Read or written | Fields | Existing or New |
|---|---|---|---|
| `intents/<id>/intent.json` via `sh_platform/jsonfile.py` | Read and written | state, closure, links, time_box, stages, people, outcome, ratings | New (record defined in 00-BRIEF; folder per intent, brief ruling 12) |
| `intents/<id>/events.jsonl` | Written (one line per closing action: draft, edit, sign, send-back, close, cancel); the record holds counts only | event kind, by, at | New (owned by spec 16) |
| `intents/<id>/weeks/<week_key>.json` | Read (Weekly check-in outcome block) | items, kinds `ran`, `broke`, `thought`, fates, reasons | New (owned by specs 39 and 40) |
| `sh_platform/profile/view.py` | Read | per-viewer filter of the record; company time zone | Existing |
| Charter and approver store, `modules/m1_intent/store/charter.py` | Read | charter version, signatures, approver link state for an Initiative | Existing |
| `intents/m1_intent/outcomes/<outcome id>.json` | Read (Initiative charter outcome) | signatures, problems, footer | Existing |
| Wall, board, together records of the Initiative | Read (source chips) | cards, votes, notes | Existing |
| M2 definitions, process map, data sources map | Read (artefact chips) | confirmed or draft | Existing |
| Rating records (spec 10) | Read for the closed view, written by spec 10 | `ratings` | New in spec 10 |
| Backlog | Written | item with title, reason, `from` intent id | New (the backlog spec, 21, owns the file; this feature calls it) |
| Child intents (Initiative or Problem created from next) | Written | draft intent with `links.from` set | New |
| `POST /api/intents/<id>/closure/draft` | Route | North drafts; organiser only | New |
| `PUT /api/intents/<id>/closure` | Route | organiser edits summary, next, reason | New |
| `POST /api/intents/<id>/closure/sign` | Route | signer signs | New (reshaped from `POST /sessions/<id>/charter/sign`) |
| `POST /api/intents/<id>/closure/send` and `/withdraw` | Route | approver link create and revoke | New (reshaped from charter `send` and `withdraw`) |
| `POST /api/modules/m1_intent/approver/closure` and `/approver/decision` | Route | approver reads and decides by token; guest routes may only live under `/api/modules/<module>/` | Reshaped from `/approver/charter` and `/approver/decision` |
| `POST /api/intents/<id>/close`, `/close-incomplete`, `/cancel` | Route | state moves | New |
| `GET /api/intents/<id>` | Route | closed view | New |

## Fields this feature adds to the intent record

The brief's `closure` block is kept as named. Fields added inside it, and next to it:

```
closure: {
  closed_by, closed_at, summary, why_it_happened, what_came_out, next: [{kind, ref, reason}],   # from 00-BRIEF, unchanged
  summary_sentences: [{text, sources: [record ref], by: "north"|person, edited_at|null}],
  signature: {required: bool, by_role: sponsor|decider|owner|null, name, account_id, at, how: room|approver} | null,
  send_back: {by, at, comment} | null,
  incomplete: bool, missing: [field names], incomplete_reason: text | null,
  cancel_reason: text | null,          # written only when state: cancelled; closed_by and closed_at are always present
  people_counts: [{name|null, role, count, unit}],
  anonymous_count: int
}
closing_started_at: timestamp | null
```

`next[].ref` is filled when North writes the link (the new intent id or backlog item id); it is empty for "nothing". The `outcome` object exists from the moment the intent opens and is never null (brief ruling 6); this feature only reads it.

Per-type confirmers by ruling 25: Initiative (sponsor signs), Decision (decider decides), Problem (owner confirms, then reporter confirms). Brainstorm and Weekly check-in need no confirmation: closed by the organiser.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** moves Initiative to `closing` at charter signature. For other types: drafts the closure when the organiser opens `closing`. Drafts summary sentences with source refs, the reason, the proposed next list (it chooses a kind and writes the reason from the records, for example a check-in item with no owner proposes "Backlog"). It states what is missing for a complete close. It writes the banner when the time box will not be met and proposes extend, close with what we have, or cancel; a named person picks. North creates the child intents and backlog items only after closure, from the confirmed next list. North never signs, closes, confirms or cancels.
- **Lens** is not used here, except to tell North whether an Initiative's artefacts are confirmed or draft (read only).
- **Nira** lists the closing prompt for organiser, the per-type confirmer's action request, and the participant rating prompt under "what is waiting for you"; feeds the Pulse line and the past list row.
- **People act at:** per-type confirmer signing/deciding/confirming, organiser pressing Close, editing a sentence, confirming each next row, sending back, rating, cancelling.

## Rules (visibility, time box, who may do what)

- A sentence without a source is not shown. A number in the summary must come from a record; if it cannot, the line says "Not available yet" and names what is missing. Counts are exact; means, medians and per-person figures show "Fewer than five" below five records; ratings aggregate from three (brief ruling 8).
- Ratings are anonymous by default; a person's own file keeps the link so they can see what they gave; no per-person average exists anywhere (brief ruling 15). A Weekly check-in series and its weeks are not rated (brief ruling 3).
- Only the organiser closes or cancels. Per-type confirmers must act first: sponsor signs (Initiative), decider decides (Decision), owner then reporter confirm (Problem), nobody for Brainstorm and Weekly check-in. North may only propose.
- Only a named person with a role in `sign_roles` (`company_admin`, `sponsor` in `contracts/charter.yaml`) signs an Initiative closure. Decider and owner/reporter roles are confirmed in contract. The signature of one person is enough unless the organiser asked for two when preparing the Initiative (as the charter does).
- Once signed, the signed text is read-only (CLAUDE.md rule 7). An organiser edit after signing clears the signature and asks again.
- Cancel reason is recorded only in `closure.cancel_reason` with `closure.closed_by` and `closure.closed_at` when state moves to `cancelled`. No other cancel field is allowed.
- After `closed` or `cancelled`: no stage, card, vote, comment, note, person list, time box, outcome or closure field can change. What stays writable: ratings (spec 10, until their own window ends), share link create and withdraw, the `next[].ref` link written by North within the same closing action.
- Participants and observers see everything except sealed and anonymous material (D-013). The closure summary never quotes sealed or anonymous items; they count only in "Anonymous contributions: n".
- Area members and affected people see title, purpose, stage, clock, people, organiser and the outcome once closed. They open the summary and source chips only when the organiser switched on "affected people may read" at creation (default off) or they are named on a share (brief ruling 4).
- Super admin sees existence only (title, type, state, areas, people count, dates, time box status), read through the kernel; the company switch "titles private to the company" removes titles from that view. Company admin sees existence and outcome, never anonymous notes.
- Time box: closing does not extend it. Extension is a separate act with a reason.
- Past intents are never deleted. A cancelled one says why.
- Approver link: valid for the hours set in `contracts/charter.yaml` for the charter link; shown once; only its hash is kept; one use; failed attempts are throttled as in the charter approver.
- Copy: no game words, no model or vendor names, British spelling. Dates in the company's time zone from the profile, else UTC.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Traced to |
|---|---|
| Intents closed this month, by type (exact count) | `closure.closed_at`, `type` over `intents/*/intent.json` |
| Closed with what we have, as a count and share of closed | `closure.incomplete` |
| Cancelled, with the count of each stated reason | `closure.cancel_reason` |
| Median days from open to closed against the time box; "Fewer than five" below five closed intents | `created_at`, `closure.closed_at`, `time_box` |
| Median days from `closing_started_at` to signature; "Fewer than five" below five signed | `closing_started_at`, `closure.signature.at` |
| Sentences edited by the organiser out of sentences drafted | `summary_sentences[*].edited_at` |
| Next items by kind | `closure.next[*].kind` |
| Next items with a written link still open after a set period | `next[*].ref` joined to the target record (the period is open question 5) |
| Send-backs by approver | `closure.send_back` |

When there are no closed intents the counters say "Not available yet: no intent has closed."

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searched `modules/m1_intent` for sign, approver and charter; found these. All paths below were checked and exist in this repo.

| Existing | Where | Decision |
|---|---|---|
| Sign route: `sign_charter`, role check against `settings.sign_roles`, `store.sign` | `modules/m1_intent/api/charter.py` lines 294 to 307 | Reshaped: same check, same signer record {name, account_id}, pointed at `intents/<id>/intent.json` closure |
| Send and withdraw an approver link (`new_token`, `store.send`, `store.revoke`, link shown once, hash kept) | `modules/m1_intent/api/charter.py` lines 308 to 329; `modules/m1_intent/store/charter.py` lines 197 to 275 (`new_token` at 276) | Copied: token and hash logic unchanged; only the record it writes to changes |
| Approver routes by token: `read_draft`, `decide`, throttle on failed links | `modules/m1_intent/api/approver.py` lines 40 to 175 | Reshaped: new closure read; decision reused with approve or decline and the required decline comment |
| `signers_needed`, `sign_in_room`, `approve`, `decline`, `clean_comment` | `modules/m1_intent/domain/charter.py` lines 261 to 303 | Copied |
| Settings for roles, signers required and link hours | `modules/m1_intent/contracts/charter.yaml` lines 20 to 25 | Reused as they are |
| State machine style with one allowed-moves table | `modules/m1_intent/domain/states.py` | Reshaped: a second small table for the intent states in this spec, same `IllegalMove` pattern |
| Charter screen with signature strip and sign actions | `ui/src/pages/CharterView.tsx` lines 183 to 340 (`Signature` strip, `SignActions`) | Reshaped: the `Signature` component from `ui/src/design/parts.tsx` line 307 and the copy pattern are reused for the signature line; closure has its own page |
| Approver page with one question, route `/approve/:token` | `ui/src/pages/ApproverPage.tsx`; route in `ui/src/main.tsx` line 30 | Reshaped: same page frame and decision form, new body showing the closure |
| Outcome record written once when the charter is signed | `modules/m1_intent/contracts/outcome.yaml`; `modules/m1_intent/store/charter.py` line 96 | Reused for an Initiative's charter outcome; not duplicated |
| Per-viewer filtering | `sh_platform/profile/view.py` | Reused |
| JSON file storage | `sh_platform/jsonfile.py` | Reused |

Genuinely new: the intent closure record, summary sentences with sources, the next list and its link-writing, the closing and cancelled states, the closure screen, the past list row and Pulse line. Searches for "closure", "close intent" and "rating" in `modules/` found only session `closed` state and the charter signing; nothing to reuse for the closure screen itself.

## Not in this feature

- Rating questions, scores and the anonymous option (spec 10).
- The outcome content of each type (each type's own spec).
- The backlog screen and the Build hand-off screens.
- The Weekly check-in recurrence and the weekly cycle (specs 38 to 40).
- Re-opening a closed intent (a follow-up intent is used instead).
- Email or chat sending of the approver link; the organiser copies it.
- Exporting the closure as a document (the charter download stays where it is).

## Open questions

1. How many times may a time box be extended? None is invented here.
2. How long after closure may people rate (spec 10 sets it; this spec only keeps ratings writable).
3. How long before a next item's link is judged "still open" for the follow-up measure? No period is set; confirm or drop the measure.
4. Should a company admin be able to sign for a sponsor who is absent? The charter allows it; confirm for closure.
5. Should area members see the people list names, or only the count? This spec shows only the count to area members; affected people see people (brief ruling 4).
6. Should North prompt the organiser before the time box ends, and how early? None is invented here.
7. Should participants be locked out of adding material while the intent is `closing`? This spec assumes yes; the brief does not say.
8. Should `closure.next[].kind` gain `decision` and `handled` to match brief ruling 7 (a Decision may link to any type) and the check-in fate `handled`? The brief's list is initiative, backlog, problem, nothing.
9. Should "Fewer than five" apply to the per-person contribution count on the closure screen? This spec applies it, following brief ruling 8, which makes the chip empty for small intents.
