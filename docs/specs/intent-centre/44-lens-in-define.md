# 44. Lens in Define: the definitions agent

Part of: Intent Centre v2. Depends on: 01 (intent record, `refs`), 06 (people and roles), 26 (Define, right panel tabs, governed ring), 27 (process map), 28 (data sources), 29 (business glossary), 30 (technical glossary and catalogue). Feeds: 26, 29, 30, 13 (Pulse lines), 33 (build-ready check), 09 (closure).

## Purpose (three sentences)

Lens is the definitions agent inside an Initiative's Define stage. Before the session, unattended, it drafts nine kinds of content for every measure a cluster maps to, marks each as guessed with its source named, and raises at most three questions per person. This file specifies what Lens drafts and from what, the order, the questions, the "Send back with a note" loop, what Lens may and may not read, the "Lens is drafting" state, and how its output is marked on every screen until a named person confirms it.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Analyst (Katie) | Before the session: checks Lens's drafts, sends back what is wrong, answers questions | North's prepare list: "Check Lens's drafts" |
| Owner (Harvey, as business owner, data owner or source owner) | Before or in the session: confirms or sends back the definitions he owns, answers Lens's questions | Pulse line "Lens has 2 questions for you" |
| Governance lead / approver (Grace) | Settles ambiguities, confirms classification and who may see, decides what has been sent back twice | Pulse line "Lens needs you to decide" |
| Organiser (Janet) | Watches progress, starts a retry for a failed draft, reads what is still guessed at close | Define screen, "Lens" strip |
| Sponsor (Daniel) | Sends a measure back with a note; reads what Lens drafted | Invitation to the session |
| Participant (Aaron) | Reads Lens's drafts in the tab; may not confirm or send back unless he owns the measure | Define screen |
| Affected person, observer | Affected people read content only when the organiser switched on "affected people may read" or a share names them; an observer reads what a participant reads and never writes | Define screen, share link |
| Company admin, super admin | Company admin sees existence, counts and outcome, never anonymous notes; super admin sees existence only (title, type, state, areas, people count), read through the kernel, never this content | Intent list, `/centre/control/intents` |

## Entry points (every route, link, Pulse line, button that leads here)

- Define (26, `/centre/intent/<id>`; the stage view opens by default): the right panel tab "Definition" (default), plus the "Lens" strip at the top of the panel. Route `/centre/intent/<id>/define`, with `?cluster=<cluster_id>` and `?cell=<cell_key>` for deep links.
- Pulse (13): Nira lines "Lens has finished drafting, check the drafts" (analyst), "Lens has <n> questions for you" (a named person, never above three), "Lens needs you to decide" (governance lead, for an escalated send back).
- North's prepare list on the intent home (04): "Check Lens's drafts".
- Governed ring refusal on a cluster tile (26): "Open Lens's definition".
- Charter and build-ready check (33, `/centre/intent/<id>/charter` and `/centre/intent/<id>/build-ready`): "Open in Define" on any line that names a guessed cell.
- Share link (11, `/centre/intent/<id>/share`): read-only. Shows every draft with its mark. No send back, no answer boxes.

## Screens, element by element

All content sits inside the Define route (26). No new top-level screen. The Definition tab content for glossary (29) and catalogue (30) is specified there; this file specifies the Lens strip, the draft cell, the send-back dialog, the question list and the escalation queue.

### Screen 1. The Lens strip (top of the right panel)

Route: `/centre/intent/<id>/define`. Layout at 1280: a full-width row above the tabs in the right panel: Lens name and status line on the left, progress and the "Questions" chip on the right. At 390: one line at the top of the bottom sheet; tap expands to the question list.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Lens status line | agent line (Lens) | "Lens has drafted 41 of 52 items for 6 measures." Counts are read from `define.lens.cells` by `state` (exact) | Click opens the run detail: one row per measure with its state | Everyone who may open the content | "Not available yet: Lens has not started. North starts it when Define opens." |
| Drafting progress | text with bar | "Drafting 3 of 9 for Fund returns" while a run is on (`define.lens.run.order` and `cells` for that measure) | None | Everyone who may open | Hidden when no run is on |
| Questions chip | chip | "Questions: 2 open for you, 4 waiting" (counts from `define.lens.questions` by `state` and `to`; waiting means queued over the cap) | Opens Screen 4 | Everyone named in a question; others see the totals only | Hidden at zero |
| Run detail | panel | Per measure: nine kinds, each with state (not drafted, drafting, guessed, failed, sent back, confirmed) | Click a row selects the cluster and the cell | Organiser, analyst, sponsor, governance lead | "No measures behind this group yet. Lens drafts them once a baseline exists." |
| Try again (all failed) | button | "Try again for <n> items that failed" | Starts a retry run for failed items only (see states) | Organiser, analyst | Hidden when nothing failed |
| Lens source line | text | "Read: 14 documents, 6 interviews, the profile, the family office pack as suggestions" (counts from `define.lens.reads`, exact) | None | Everyone who may open | "Lens read no documents. The pack's suggestions are shown, marked as suggestions." |

### Screen 2. The draft cell (the provenance cell used for every item below)

Route: `/centre/intent/<id>/define` (`?cluster=`, `?cell=`). One component, reused in the Definition tab, the Process map tab and the Data sources tab. Layout at 1280: label, value, mark chip, source line, actions. At 390: same stack, actions below.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Cell label | text | One of the nine kinds (see "What Lens drafts") | None | Everyone who may open | n/a |
| Cell value | text or field | Lens's draft | A person with edit rights may overwrite it; their wording is marked stated and Lens's draft is kept beside it as a proposal | Everyone who may open | "Not drafted yet." or "Lens found nothing in your documents that says what <term> means, so it will ask <name>." |
| Mark chip | chip | "Guessed" (dashed edge, amber) until confirmed; "Confirmed by Harvey, 8 Oct" (solid edge, green) after | None | Everyone | n/a |
| Source line | text | "Lens, from Fund returns policy.pdf, page 3" or "Lens, from Harvey's interview" or "Lens, from the family office pack (a suggestion)" | Click on a document title opens that document's passage if the viewer may see it | Everyone who may see that source; a source the viewer may not see reads "A restricted document" | "Lens, no source found" (never a blank) |
| Lens is drafting | agent line (Lens) | See Screen 3 | None | Everyone | n/a |
| Confirm | button | "Confirm" | Writes the person's name and date, mark becomes stated; Lens never confirms | The owner of that item, or the governance lead for classification and who may see (as in 26 and 30) | Hidden for others |
| Send back with a note | button | "Send back with a note" | Opens Screen 3a | Same people as Confirm, plus sponsor and analyst | Hidden on a confirmed cell, and on signed content |
| Redraft proposal | panel | Lens's second draft beside the first, with the note that caused it | "Use this one" replaces the value (marked guessed until confirmed); "Keep the first" dismisses it | Person who sent it back, owner, analyst | Hidden when none |
| Escalated chip | chip | "With Grace for a decision" | Click opens Screen 5 for Grace; others see the chip only | Everyone who may open | Hidden unless escalated |

### Screen 3. "Lens is drafting" state (on every cell, while a draft is made)

Route: `/centre/intent/<id>/define`. Layout at 1280: inside the draft cell, the value area and a one-line agent line below it. At 390: the same, full width, "Try again" below the line.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Drafting outline | visual | Dashed pulsing outline on the cell, value area shows three grey lines | None | Everyone | n/a |
| Drafting line | agent line (Lens) | 0 to 5 seconds: "Lens is drafting this." After 5 seconds: "Taking longer than usual. You can carry on, the page is not blocked." | None | Everyone | n/a |
| Another screen is drafting | agent line (Lens) | "Another person's screen started this draft." (the claim is held by another run) | None | Everyone | Hidden otherwise |
| Failure line | agent line (Lens) | "Lens could not draft this just now." If the pack has a suggestion for the item it is shown beneath, marked "Suggestion from the family office pack, not a draft of yours" | "Try again" button re-runs that cell once | Organiser, analyst, owner | n/a |
| No model line | agent line (Lens) | "Lens could not read your documents because no model is set up for your company; these are the industry pack's suggestions." | None | Organiser, analyst | Hidden when a model is set up |
| Try again | button | "Try again" | Sends a single retry for that cell; the server skips a cell already tried unless told to retry | Organiser, analyst, owner | Hidden when not failed |

### Screen 3a. Send back dialog

Route: `/centre/intent/<id>/define`, opened from the draft cell. Layout at 1280: a centred dialog over the right panel, note field above the buttons. At 390: a full-height sheet, buttons fixed at the bottom.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Dialog title | text | "Send back <kind> for <measure> to Lens" | None | The person sending back | n/a |
| Note | field (required, existing instruction length limit) | "Tell Lens what to change" | Required; "Send back" stays disabled until filled | Same | Error "Please say what to change." |
| Send back | button (primary) | "Send back" | First send back: Lens redrafts once with the note (see loop). Second send back of the same cell: no redraft, the cell goes to the governance lead (Screen 5) | Same | Disabled until the note is filled |
| Cancel | button | "Cancel" | Closes, nothing written | Same | n/a |
| Second-time warning | text | "This was already sent back once. Sending it back again passes it to Grace to decide." | None | Same, only on a second send back | Hidden on the first |

### Screen 4. Questions list ("Lens asks")

Layout at 1280: a list in the Definition tab, grouped by person; the viewer sees only their own group in full, plus counts for the others. At 390: one card at a time.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Question card | list item | Question text in plain words, the item it belongs to, why Lens is asking you ("You are named as business owner of Fund returns"), and the meanings found: "The documents say three things: <meaning 1> (policy.pdf), <meaning 2> (Harvey's interview), <meaning 3> (pack suggestion)" | Opens answer options | The person it is addressed to; the governance lead sees all escalated ones | "Lens has no questions for you." |
| Answer: pick a meaning | button per meaning | The meaning found, with its source | Records the answer, offers "Use this as the definition" | Addressed person | n/a |
| Answer: write my own | field and button | "Say it in your words" then "Save my answer" | Records the answer; the wording becomes the person's stated value | Addressed person | Disabled until filled |
| Not mine, it is ... | button | "Not mine, it is <name>" with a person picker over the intent's people and the profile people | Reassigns the question and the owner proposal; the new person's cap applies (see rules) | Addressed person | n/a |
| Accept as ambiguous | button | "Accept both meanings" | Only the governance lead; records a known risk (29) | Governance lead | Hidden for others |
| Waiting count | text | "4 more questions are waiting for Harvey's answers" | None | Organiser, analyst, the person | Hidden at zero |

### Screen 5. Escalation queue (governance lead)

Route: `/centre/intent/<id>/define?view=escalated` (a query on the Define view; see open question 9). Layout at 1280: a list in the Definition tab, the open item's two drafts side by side with the three options beneath. At 390: one item at a time, drafts stacked, options below.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Escalated item | list item | The item, the first draft, the redraft, both notes with who wrote them | Opens three options | Governance lead, organiser (read) | "Nothing waiting for your decision." |
| Choose a wording | buttons | "Use the first draft", "Use the redraft" | Records the choice; the cell stays guessed until the lead or owner confirms | Governance lead | n/a |
| Write the wording | field and button | "Write it myself" then "Save" | Wording becomes stated, by the governance lead | Governance lead | Disabled until filled |
| Mark unknown | button | "We do not know yet" | Cell value becomes "Not known yet" and a known risk is written (29) | Governance lead | n/a |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet opens Define from the intent screen (26). Between her step and the next, North asks Lens to start its run for every measure the clusters map to. Nobody clicks.
2. Lens drafts in this order, one measure at a time, so progress shows and one failure never blocks the rest:
   1. cluster to measure mapping; 2. business definition; 3. technical definition; 4. catalogue entry; 5. the three owners (business owner, data owner, source owner); 6. governed state (six fields); 7. process steps (27); 8. data sources (28); 9. ambiguities with the meanings found.
3. Each result is stored as a cell marked guessed with its source named. Lens then ranks the questions and sends at most three per person across Define.
4. Nira sends Pulse lines: the analyst "Lens has finished drafting", each addressed person "Lens has <n> questions for you".
5. Katie follows her Pulse line to Define, reads the strip, opens a cluster. Where a cell is wrong she clicks "Send back with a note" and types the change. Lens redrafts once and shows the redraft beside the first. Katie picks one, or sends it back again, which passes it to Grace.
6. Harvey answers his questions, then clicks "Confirm" on the definitions he owns, or "Not mine, it is <name>". Lens opens his next queued question after each answer.
7. Grace opens her escalated items and decides each. She settles the ambiguities (29) and confirms classification and who may see.
8. At the session (26) the strip still shows every cell not yet confirmed as guessed. Janet may click a failed item's "Try again".
9. At close, North counts cells still guessed and lists them in the dialog (26). Nothing guessed is hidden from the charter draft: it prints "Draft by Lens, not confirmed".
10. Each person leaves by closing the panel or going back to the intent screen. Janet leaves the intent at close (09).

## States and transitions (table: state, who moves it, to what, what is written)

| State | Who moves it | To what | What is written |
|---|---|---|---|
| Cell `not_drafted` | North starts the run | `drafting` | claim (cell, run id, time); existing claim logic with a stale time-out |
| `drafting` | Lens finishes | `guessed` | value, `mark: guessed`, `by: Lens`, source, `drafted_at` |
| `drafting` | Lens fails or the claim goes stale | `failed` | outcome `unreachable`; the pack suggestion kept beside it where one exists |
| `drafting` | Nothing found to draft from | `guessed` with value "Not known yet" and a question | outcome `nothing`; a question to the owner |
| `failed` | Organiser, analyst or owner, "Try again" | `drafting` once | retry flag, attempt counted |
| `guessed` | Owner or governance lead, "Confirm" | `confirmed` | person, time, `mark: stated`; Lens's draft stays as the proposal history |
| `guessed` | A person edits it | `confirmed` only on Confirm; edit alone | wording `stated` by the person; Lens's draft kept beside as a proposal |
| `guessed` | A person, "Send back with a note" (first time) | `redrafted` | send-back record (who, when, note); Lens's redraft beside the first |
| `redrafted` | A person picks "Use this one" or "Keep the first" | `guessed` | choice kept with name and time |
| `redrafted` | A person sends it back again | `escalated` | second note; a question to the governance lead |
| `escalated` | Governance lead decides | `guessed` (wording chosen or written) or `confirmed` (if the lead also confirms) or "Not known yet" with a known risk | decision, name, time |
| `confirmed` | Nobody | read-only; a change creates a new version (30), never an overwrite | none |
| Question `queued` | Lens, when a person has fewer than three open | `open` | `raised_at` |
| Question `open` | The person answers, reassigns, or the lead accepts | `answered` or `dropped` (reason required) | answer, by, at |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Read or write | Status |
|---|---|---|---|
| `POST /api/modules/m2_baseline/baselines/{id}/lens/draft` | kpi_ids, suggestion_ids, retry | write (drafts) | Existing |
| `GET /api/modules/m2_baseline/baselines/{id}/lens` | pending, failed, drafting, documents, refine, asks, say | read | Existing |
| `POST /api/modules/m2_baseline/baselines/{id}/lens/redraft` | kpi_id, instruction | write (redraft beside) | Existing; the send-back button calls it once per cell |
| `POST /api/modules/m2_baseline/baselines/{id}/lens/technical`, `.../lens/technical/redraft` | measure ids, instruction | write | Existing |
| `store/lens.py` `lens.json` | attempts per item, drafts, stale claim | read and write | Existing |
| `store/governed.py` governed state | six fields, `mark`, `by` | read and write | Existing |
| `store/ambiguities.py`, `store/glossary.py`, `store/catalogue.py`, `store/kpis.py` | ambiguities, glossary, catalogue rows, measures | read and write | Existing |
| `sh_platform/profile/view.py` `read(plane, viewer)` | cards, areas, sources, rules, filtered per viewer | read | Existing |
| `sh_platform/context_docs` `documents_for`, `retrieve` | passages, titles, restricted flag | read | Existing |
| Interviews of people in the intent (`m1_intent` interview store) | answers the person confirmed as shareable | read | Existing; eligibility filter is New (see Rules) |
| `GET /api/intents/{id}/define/lens` | run state, per-cell state, counts | read | New |
| `POST /api/intents/{id}/define/lens/run` | starts the unattended run (North only) | write | New |
| `POST /api/intents/{id}/define/lens/cells/{cell_key}/send-back` | note | write | New; wraps the existing redraft and counts the send backs |
| `POST /api/intents/{id}/define/lens/questions/{qid}/answer`, `.../reassign`, `.../drop` | answer, person, reason | write | New |
| `intents/<id>/intent.json` | `define.lens` (below) | read and write via `sh_platform/jsonfile.py`, filtered per viewer by `sh_platform/profile/view.py` | New (01) |
| `intents/<id>/events.jsonl` | one event per run start, finish, send back, escalation, answer; the intent record holds counts only | write | New (16) |
| `POST /api/modules/m1_intent/shared/view` | read-only share view of every draft with its mark | read | Existing (11, 14) |

## Fields this feature adds to the intent record

These go in one new block `define.lens` inside `intents/<id>/intent.json` (ruling 12). No field of the brief's section 3 is renamed; `refs` (01) is read, not changed.

`define.lens`:

```
{ run: {id, state: idle|running|done|partial, started_at, finished_at, order: [9 kinds], model_set_up: bool},
  cells: {<cell_key>: {kind, measure_code, state, attempts, outcome, drafted_at, confirmed_by|null, confirmed_at|null}},
  send_backs: [{cell_key, by, at, note, round: 1|2, redraft_ref|null, escalated_to|null, decision|null}],
  questions: [{id, to, about_cell, state: queued|open|answered|dropped, raised_at, answered_at|null}],
  reads: {documents: n, interviews: n, profile: bool, pack: bool} }
```

`cell_key` is `<measure_code>:<kind>`. The questions list is shared with 27 and 29; each of them writes its own kinds to it, and the open count per person is derived from it, never stored. 29's `questions_asked` stays as its own tally.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

**North** starts Lens's run when Define opens (a stage trigger, 08) and again after a late card or cluster change, for the changed measures only. It lists in the prepare list what is still guessed. North decides nothing here.

**Lens** drafts the nine kinds in order, marks every draft guessed with the source named, and raises the questions. It never confirms, never overwrites a person's wording (its draft goes beside it as a proposal) and never states a figure it did not find in a record.

What Lens drafts, and from what:

| # | Kind | Drafted from | Notes |
|---|---|---|---|
| 1 | Cluster to measure mapping | the cluster's cards and the measure list (`measure_codes` in the together view) | Code first, no model. A cluster mapping to nothing shows "No measures yet" |
| 2 | Business definition | the profile, shelf documents, interviews, then the pack as a suggestion | One model call per measure |
| 3 | Technical definition | source, fields, calculation, period, currency from catalogue metadata and documents (30) | Never invents a formula: a missing formula is a question |
| 4 | Catalogue entry | rows the technical notes name, kept only where a passage says the name | Marked guessed, with the document title |
| 5 | The three owners | RACI in the profile, systems list, interviews | Business owner, data owner and source owner, each its own cell. The governed state's "process owner" is the business owner of the process |
| 6 | Governed state | classification policy, access list, deadlines file, pack dependencies (six fields, A-054) | Drafted with the definitions, nobody asks for it |
| 7 | Process steps | cards, interviews, documents (27) | One map per cluster |
| 8 | Data sources | catalogue, systems list, profile sources (28) | |
| 9 | Ambiguities with the meanings found | contradictions between sources, found by code first (`code_ambiguities`) and by one model call | Each meaning shown with its source, so the person picks, not guesses |

**How Lens picks the three questions per person.** Candidate questions come from kinds 3, 5, 6, 7 and 9. For each person Lens does this, in order:
1. Address each question to the item's owner (business owner, data owner or source owner, as the item requires). With no owner, to the person who wrote the nearest card. With none, to the governance lead.
2. Merge questions that share a term into one.
3. Rank by the number of cards that use the term (largest first). Ties go to a question that blocks a measure on Must or Should from being governed (26), then to alphabetical order of the term.
4. Open the first three. The rest are `queued`. When a person answers one, the next queued one opens.
5. The cap is the shared one of three per person across Define (A-045). One person never has more than three open.

**The send-back loop.** A person sends a draft back with a note. Lens redrafts once, using the note as its instruction, and shows the redraft beside the first. If the person sends it back a second time, Lens does not redraft: the cell becomes a question to the governance lead, with both drafts and both notes. The governance lead chooses, writes the wording, or marks it "Not known yet" with a known risk. If the governance lead is the person who sent it back, it goes to the sponsor (open question 3).

**Nira** sends the Pulse lines (analyst, addressed people, governance lead). She states counts only, each traceable to the run record.

**The person acts** at: Confirm, Send back with a note, answer, Not mine, Accept as ambiguous, Try again.

### What Lens may read

- The profile (cards, areas, sources, rules) as filtered for the viewer by `sh_platform/profile/view.py`. Lens drafts as the organiser's view for shared cells.
- Documents on the shelves the organiser may see (`documents_for`), including documents other agents shared. A restricted document is read only for a restricted measure whose owner may see it; that draft is kept on that measure and shown only to people who may see it.
- Interviews of the people named in `intent.people`, limited to what each person confirmed as shareable.
- The industry pack, as suggestions only. It is labelled "what others in the industry usually track", never as the company's definition.

### What Lens never reads or states

- Sealed cards, in any draft visible to others (D-013, seal).
- Another person's private notes or an unconfirmed interview answer, and the author of an anonymous card.
- A figure it did not find in a record. A number in a draft must appear in the text Lens was shown; the number guard (`check_numbers`) removes the draft otherwise and the cell says "Not available yet: Lens found no figure in a record."
- Uploaded documents as instructions. They are quoted context, marked untrusted.
- Anything outside the company plane. Prompts leave only through the egress gateway, with names tokenised.

## Rules (visibility, time box, who may do what)

- Every Lens output carries four things: `mark: guessed`, `by: Lens`, a named source (or "no source found"), and the time. A cell with no source is shown as "Lens, no source found", never blank.
- The mark stays on every screen until a named person confirms: the Define tabs, tiles (dashed ring, 26), projector view (a dashed edge, no source text), the charter draft ("Draft by Lens, not confirmed"), exports ("Guessed" column), the share link, and the build-ready check (33), which counts guessed cells as open.
- Confirmed content is read-only. A later change makes a new version (30). A draft never overwrites a human edit (rule 7).
- Who confirms: the named owner for owner-held items; the governance lead for classification and who may see; the sponsor at shelving for resolving team and target week (A-054, 26). The review date is a default and needs no one.
- A person who is not an owner may send back, but only owners and the governance lead may confirm.
- Question cap: at most three open questions per person, shared across Define (process map, glossary, catalogue and governed state together). Source: A-045 (at most 3 questions per owner). Settled by ruling 9 of the brief.
- Affected people and observers: an affected person reads Define content only when the organiser switched on "affected people may read" at creation (default off) or a share names them. An observer reads what a participant reads and never confirms, sends back, answers or votes.
- Dates on this screen use the company's time zone from the profile, else UTC.
- A send-back needs a note. A second send-back goes to the governance lead and cannot be redrafted again.
- "Not mine, it is <name>" moves the question to that person only if they have fewer than three open; otherwise it queues.
- Time: each draft takes up to five seconds. The run has no overall limit, is not part of the stage clock (07), and never blocks the screen.
- Visibility: restricted measures are drafted and shown only to people who may see them; others see "Something restricted is still open". Super admin sees nothing of this. Company admin sees counts, never anonymous authors.
- Copy: no game words, no model or vendor names. Agents are North, Lens, Nira. British spelling, no em dashes.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Traces to |
|---|---|
| Items drafted of items total, per kind | `define.lens.cells` by `state` |
| Items failed; items retried | `cells.outcome` and `attempts` |
| Time to draft one item (seconds, mean) | `cells.drafted_at` less claim time in the run record |
| Cells still guessed; cells confirmed | `cells.state` |
| Send backs; redrafted; escalated | `send_backs` by `round` and `escalated_to` |
| Questions open per person; queued | `questions` by `state` and `to` |
| Questions answered; dropped | `questions` by `state` |
| Documents, interviews read | `reads` |

Time to draft one item is a mean and shows "Fewer than five" below five items. Counts are exact. Where the run has not started the strip says "Not available yet: Lens has not started." Where there are no measures it says "Not available yet: no measures to draft."

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `graft ask` on "Lens agent definitions draft routes prompts" (indexed `m2_baseline` and `ui`); direct reads of the files below; grep for "A-045", "three per person", "send-back"; every path below checked to exist on 7 Oct 2026. `sh_platform/` is not under the graft index here, so its entries come from direct reads.

| Existing | Where | Status and use |
|---|---|---|
| Lens agent: prompt builder, pre-read, conversation, field drafting, technical drafting, one-at-a-time runner, name registration | `modules/m2_baseline/agent/lens.py` (1 to 259: `system_prompt` 43, `preread` 74, `converse` 105, `draft_fields` 142, `draft_technical` 174, `run_in_order` 210, `register_names` 250) | Existing, reused as is |
| Lens prompts and rules | `modules/m2_baseline/agent/lens_rules.yaml` | Existing, reused as is; the draft rules already forbid inventing a formula |
| Ambiguity matching by meaning | `modules/m2_baseline/agent/glossary_lens.py` (`match_by_meaning` 22) | Existing, reused for kind 9 |
| Draft route: pack first, then documents, marks guessed, never overwrites a stated value, drafts governed state too | `modules/m2_baseline/api/worklist.py` (413 to 430 `lens_draft`) | Existing, reused for kinds 2 and 6 |
| Lens state, redraft, conversation | `modules/m2_baseline/api/lens_chat.py` (77 to 175: `lens_state`, `redraft_one` 124, `lens_redraft` 166) | Existing; the redraft is the send-back's one redraft |
| Technical drafting and redraft | `modules/m2_baseline/api/technical.py` (264 to 290) | Existing, reused for kind 3 |
| Draft claim, attempts, stale claim | `modules/m2_baseline/store/lens.py` (`claim` 46, `is_stale` 26, `record` 37) | Existing, reused for the "drafting" and failure states |
| Questions Lens asks | `modules/m2_baseline/domain/lens_view.py` (`asks` 18), `domain/ambiguities.py`, `store/ambiguities.py` | Existing, reshaped: add the shared cap of three open per person and ranking |
| Kernel agent runtime, tool registry, number guard, context pack | `sh_platform/agents/loop.py` (`run_agent` 45), `registry.py` (`ToolRegistry` 35), `guard.py` (`check_numbers` 90), `context.py` (`build_context_pack` 15) | Existing, reused through graft of the Lens agent |
| Per-viewer profile | `sh_platform/profile/view.py` (`read` 116, `sees_area`, `sees_source`, `sees_rule`) | Existing, reused as is |
| Documents and passages | `sh_platform/context_docs/` (`documents_for`, `retrieve`, `wrap_untrusted`) | Existing, reused as is |
| Drafting block in the browser: first-move drafting one at a time, progress, "Try again", failure text | `ui/src/modules/m2_baseline/agents/BaselineDock.tsx` (71 to 236), `LensCards.tsx`, `ui/src/modules/m2_baseline/api.ts` (162, `lensDraft`) | Existing, reshaped: the loop is driven by the browser today; here it is a server run started by North so it is unattended |
| Lens's panel with six governed cells | `ui/src/modules/m1_intent/define/LensPanel.tsx` (1 to 159) | Existing, reshaped into the draft cell and the Definition tab (26) |
| Failure and no-model notes | `agent/lens.py` (91 to 93: `LENS_NOTE`, `NO_MODEL_NOTE`) | Existing, reused for Screen 3 wording |
| Send back for technical definitions | `POST .../measures/{kpi_id}/send-back` (cited in 30) | Existing, reused; Define's button wraps it for all nine kinds |
| Unattended server run, escalation on a second send back, shared cap of three, `define.lens` record | none (searched `send-back`, `escalat`, `questions_asked`) | New |

Rejected: a second Lens, a second prompt set, or a new drafting store. The only builds are the server run trigger, the send-back round counter, the shared question cap and the intent record block.

## Not in this feature

- The content and layout of the business glossary (29), the technical glossary and catalogue (30), the process map (27) and the data sources (28). This file covers only how Lens drafts and marks them.
- The clusters, shelves, vote and governed ring (26).
- Lens's free conversation ("Ask Lens"), which stays as built in `lens_chat.py`.
- Gap analysis (room 0 of the Build centre at `/centre/build/gap-analysis?from=<id>`, `modules/m3_connect` moved, not rebuilt) and the Moment of truth screen.
- Lens in the other four intent types.

## Open questions

1. Is the five-second mark ("Taking longer than usual") a target or a hard limit with the cell then marked failed? This spec treats it as the point where the line appears and marks failure only on an error or a stale claim. The brief gave no number.
2. If the governance lead is the person who sends a draft back twice, who decides? Proposed: the sponsor.
3. Does a send-back that escalates to Grace count towards her three? Proposed: yes, queued when she is at three.
4. Which people's interviews may Lens read: all answers, or only those the person confirmed as shareable? Proposed: confirmed only; the interview store may need a "shareable" flag, which is not found today.
5. Define needs a baseline (`baseline_id`) for the existing Lens routes. Does North create a draft baseline when Define opens, and does the module boundary rule allow the Intent module to call baseline routes? Proposed: North creates it and the UI calls the routes; the backend does not import across modules.
6. Before shelves exist, questions are ranked by card count (29). 27 ranks by shelf order. Which wins once shelves are set? Proposed: shelf order from then on.
7. The pack is a suggestion and also a fallback on failure. Should a pack fallback text count as drafted (state guessed) or as not drafted? Proposed: not drafted, shown beside the failure.
8. The brief gives no rule for these, so they are proposals and not settled: one redraft per cell, escalation on the second send back, one retry per failed cell, the question ranking order (card count, then Must or Should block, then alphabetical), and the draft order of the nine kinds.
9. The escalation queue uses `/centre/intent/<id>/define?view=escalated`, a query on the Define view and not a new page. Confirm that no separate route is wanted.
