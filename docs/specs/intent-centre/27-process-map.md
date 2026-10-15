# 27. Process map

Part of: Intent Centre v2. Depends on: 01 (intent record), 06 (people and roles in an intent), the Define screen of the v1 spec (section 4), 28 (data sources map). Feeds: the charter ("Processes involved" page), 28 (data sources map), the catalogue and governed state (measure links), Build-ready check, Build gap analysis.

## Purpose (three sentences)

In Define, the committee maps the processes the initiative touches, so everyone sees what is possible today, which processes are involved, and where each one breaks. Lens drafts the map from the wall cards, the interviews and the documents, marks every draft as guessed with its source, and never invents a step. The named owner of each process confirms it, and the confirmed map goes into the charter as a "Processes involved" page and links each process step to the measures and data sources it touches.

## Who uses it and when (role, moment, trigger)

| Person | Moment | What they do here |
|---|---|---|
| Committee (sponsor Daniel, organiser Janet, participants such as Aaron) | The Define session, once clusters exist | Read Lens's drafted processes, add, edit, split, merge, discuss, ask for an owner. They do not confirm on the owner's behalf. |
| Process owner (for example Harvey) | After Lens names them, in or after the session | Confirms, corrects or declines ("not mine, it is X") their process; answers Lens's questions about unknown steps. |
| Analyst (Katie) | Before the session, and while the committee talks | Fixes wording, links steps to measures and systems, checks the sources. Cannot confirm a process she does not own. |
| Grace (approver) | At charter sign-off | Reads the "Processes involved" page; sees which processes are confirmed and which are still guessed. |
| Company admin | Any time | Sees that a map exists and its counts. Sees content only if named in the intent. |

Triggers: Define opens for an Initiative (the stage key `define` goes `open`); the first cluster is formed; a wall card is added or moved after the first draft (Lens offers a redraft, never overwrites).

## Entry points (every route, link, Pulse line, button that leads here)

- The **Process map** tab in Define, beside Clusters, Shelves, Glossary, Catalogue, Governed state, Data sources and Charter. Route: `/centre/intent/{intent_id}/define?tab=process-map`. In the v1 screen this is the Define route `/new/define/:sessionId` with the new tab; the intent page resolves the session through `refs.wall_session_ids`.
- A cluster header in the Clusters tab: the link "Processes (3)" opens the Process map tab filtered to that cluster.
- A wall card in the Clusters tab: the chip "Where it bites: used in 2 processes" opens the Process map at those processes.
- The Data sources tab (28): a source row's link "Used in these steps" opens the Process map with the steps highlighted.
- The catalogue entry of a measure: "Produced by / consumed by" lists steps; each opens the Process map at that step.
- Nira's "what is waiting for you" line for an owner: "Daniel's team asks you to confirm the process 'Month-end fund pricing'". It opens the process card directly (`?tab=process-map&process=<pid>`).
- A guest link to a question: `/owner-answer/{token}` (existing `OwnerAnswerPage` page route, reused as built; its spelling is outside the `/centre/intent/...` convention, Open question 9), for an owner who has no sign-in. See Agent behaviour.
- The charter page list: "Processes involved" opens the read-only view of the same data.

## Screens, element by element

### Screen A: Process map tab (list)

Route: `/centre/intent/{intent_id}/define?tab=process-map`.

Layout at 1280: three regions. Left rail (240 px): cluster filter (All, then one row per cluster with its colour, name and process count) and the status filter (All, Guessed, Confirmed, Has open question). Centre (flexible): the process list, one card per process, grouped under the cluster heading. Right panel (320 px): Lens panel (what it drafted, what it needs, the questions waiting) and the counters block. Header row above all: title "Process map", the line "Mapped today by Lens from 14 cards, 2 interviews and 3 documents" (numbers from the record), buttons "Ask Lens to draft", "Add a process".

At 390: one column. The left rail becomes a dropdown "Cluster" and a dropdown "Status" under the header. The right panel collapses to a strip "Lens: 6 drafts, 2 questions" that opens as a bottom sheet. Process cards show name, owner, status and break count; the step strip scrolls sideways inside its own card.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Header line | agent line (Lens) | Counts of cards, interviews, documents read for the last draft, and the time | None | Anyone with content access | "Lens has not drafted a map yet. Ask Lens to draft it, or add a process yourself." |
| Ask Lens to draft | button | Label; disabled with the reason when no cluster exists | Calls `POST /api/intents/{id}/processes/draft`; shows "Lens is reading" until done; new drafts appear marked guessed | Organiser, sponsor, analyst | Disabled: "Form clusters first. Lens drafts processes from them." |
| Add a process | button | Label | Opens the Process card in edit mode with empty fields | Organiser, sponsor, analyst, participants | Always shown |
| Cluster filter | list | Cluster name, colour, process count | Filters the centre list | Content access | "No clusters yet" |
| Status filter | chip row | All, Guessed, Confirmed, Has open question | Filters the centre list | Content access | Chips with 0 are shown dimmed |
| Process card (collapsed) | panel | Name; owner chip (name, or a dashed "No owner yet"); status chip (Guessed, Edited, Confirmed by Harvey); frequency; trigger; step strip; systems row; "Breaks today: 2" | Click opens the Process card (Screen B) | Content access | n/a |
| Step strip | list of chips | Steps left to right as chips, numbered | None on the list; chip click opens Screen B at that step | Content access | "No steps yet. Lens does not guess steps. The owner is asked." |
| Systems row | list of chips | Systems used, as chips under the strip | Chip click shows the system's profile entry in a popover | Content access | "No systems named" |
| Open question badge | chip | "1 question to Harvey" | Opens the question inside Screen B | Content access | Hidden |
| Counters block | panel | The numbers in "Counters and measures" | None | Content access | Each number reads "0" with its reason, or "Not available yet" and what is missing |
| Lens panel list "Needs from you" | list | Up to three open questions per person, grouped by person | Click opens the process and step | Content access; each person sees their own at the top | "Nothing is waiting." |

### Screen B: Process card (open)

Route: `/centre/intent/{intent_id}/define?tab=process-map&process={pid}`. A side sheet over the list at 1280 (640 px wide), a full page at 390.

Layout at 1280: header (name, status, owner, buttons), then the step strip drawing across the full width, then two columns: left holds Trigger, Frequency, Inputs, Outputs; right holds Where it breaks today and Links (measures, data sources). A provenance line under every field. At 390 the two columns stack, the step strip scrolls sideways, and the drawing keeps its order.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Name | field | Process name (a cell) | Edit by anyone with edit rights; the cell turns Edited with name and time | Content access | "Name this process" |
| Owner | field (person picker from profile people) | Named person; mark | Pick a person; a change clears Confirmed and notifies the old and new owner | Edit rights | "No owner. Lens suggests: Harvey (from the RACI, page 2)" if it has a source, else "No owner yet" |
| Trigger | field | What starts it, in words (a cell) | Edit | Content access | "Trigger not known. Ask the owner" with button "Ask Harvey" |
| Frequency | field | Free text plus the quick chips Daily, Weekly, Monthly, Quarterly, Yearly, When needed | Chip fills the field; text can still be edited | Content access | "Not known" |
| Steps | list | The ordered steps, each with number, short name, who does it (role or person), systems used, inputs, outputs | Drag to reorder; "Add step"; the row menu has Edit, Split here, Remove (soft, kept in history) | Edit rights to edit, content access to read | "No steps. Lens does not guess steps." |
| Add step | button | Label | Adds an empty step at the end, or after the selected step | Edit rights | n/a |
| Split this process | button | Label | Asks "Split after which step?" and creates two processes sharing the earlier history, each marked Edited and unconfirmed | Edit rights | Disabled when fewer than two steps |
| Merge with... | button | Label | Pick another process; steps join in order; the owner of the first is kept; both confirmations clear | Edit rights | Disabled when the cluster has one process |
| Step strip drawing | panel | A left-to-right strip: one chip per step, an arrow between chips, a dashed chip "?" where a step is unknown; below it a row of system chips under the step that uses them | Chip click selects the step in the list | Content access | Same as Steps |
| Inputs | list of chips | What comes in (a file, a feed, an approval) | Add or remove chip | Content access | "Not known" |
| Outputs | list of chips | What leaves | Add or remove chip | Content access | "Not known" |
| Where it breaks today | list | Each break as one line with the wall card it came from ("From card: 'Prices arrive late'") or the owner's own words | "Link a card" opens a picker of cards (see sealed rule); "Add in my words" adds a line | Content access, with the sealed and anonymous rules | "No break linked. Cards that mention this process: 0" |
| Links: measures | list | Each linked measure with the role: "produced at step 3" or "used at step 5" | "Link a measure" opens the catalogue picker; remove link | Edit rights | "No measure linked. Measures in the cluster: 4" |
| Links: data sources | list | Each source from 28 used by a step | "Link a source" opens the 28 picker | Edit rights | "No data source linked. See Data sources." |
| Provenance line | agent line | "Guessed by Lens from Interview with Aaron" or "Edited by Katie, 7 Oct" or "Confirmed by Harvey, 7 Oct" | Click shows the source passage in a popover | Content access | n/a |
| Confirm this process | button | Label | Only the named owner sees it enabled; writes `confirmed`; see States | The named owner | Disabled for others with the line "Only Harvey can confirm this." |
| Not mine, it is... | button | Label | Owner picks the right person; the process moves to them, unconfirmed, with a Pulse line to them | The named owner | n/a |
| Questions | list | Lens's questions to this process's owner and their answers | Answer box with "Send answer"; "I do not know" | The asked person, and the committee read-only | "No questions." |
| History | list | Every edit with person and time | None | Content access | "No edits yet" |

### Screen C: Questions to an owner (guest link or in-app)

Route: `/owner-answer/{token}` (existing page route, reused as built; Open question 9) or the Questions list on Screen B.

Layout: one column at both widths. Up to three questions, each with the process name, the step it concerns, a plain question, a text box, and "Send answer" and "I do not know".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Question card | panel | Process, step, question text ("What happens after the pricing file is checked?") | None | The asked person | "You have no questions." |
| Answer box | field | Free text | Type | The asked person | Empty |
| Send answer | button | Label | Writes the answer as a stated cell by the person; Lens turns it into a step proposal (guessed from the answer, source "Answer from Harvey") | The asked person | Disabled when empty |
| I do not know | button | Label | Marks the question dropped with the reason; the step stays unknown; the process cannot be confirmed until the committee accepts the gap | The asked person | n/a |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Before the session, the wall is frozen and North has made the clusters. **Lens** reads the cards (lane, q1 to q4, cluster), the interview answers in the profile and the context documents the company has attached. It drafts processes per cluster. Each field is a cell marked guessed with its source. Where a field has no source it is left unknown; Lens writes no value.
2. Janet opens Define and the Process map tab. She sees the header "Lens drafted 7 processes from 14 cards, 2 interviews and 3 documents" and the list grouped by cluster.
3. The committee reads a draft with Aaron and Daniel. They edit the name, merge two near-duplicates, split one that is really two (Split this process), and add one nobody drafted (Add a process).
4. For each process the committee names an owner, or accepts Lens's suggestion when it has a source. Each new owner gets a Nira line "waiting for you".
5. **Lens** finds the gaps: a process with no trigger, a step whose input is unknown, a hand-off without a named person. For each it queues a question to the owner. It sends at most three per person; the rest wait in the panel, ranked by the committee's shelf order, with the line "4 more questions are waiting for Harvey's answers".
6. Katie links steps to measures (the catalogue picker) and to systems and data sources (the 28 picker). Lens proposes links from the measure's technical definition where it names a system, marked guessed.
7. Harvey opens his process in the session or from his Nira line. He reads the strip, corrects the steps, answers the questions, and presses Confirm this process. Nothing else confirms it.
8. **Lens** re-checks after every edit: it reruns the dashed "unknown" chips, updates the counters and clears Confirmed on any process whose steps changed after confirmation, with the line "Harvey needs to confirm again".
9. Daniel asks for the charter. **North** includes the "Processes involved" page (see Output) with Confirmed processes shown in full and Guessed processes shown with a "Not yet confirmed by its owner" label. Nothing is hidden.
10. Janet leaves the tab. The record keeps every edit, link and answer.

## States and transitions (table: state, who moves it, to what, what is written)

Process status (one per process, in `processes.json`):

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | Lens (draft route) or any editor (Add a process) | `guessed` (Lens) or `edited` (person) | New process with id, `cluster`, cells with marks, `created_by`, `history` row |
| `guessed` | A person edits any field | `edited` | The changed cell becomes stated or edited by that person; `history` row; other cells keep their marks |
| `guessed` or `edited` | The named owner presses Confirm this process | `confirmed` | `confirmed: {by, at, version}` with the hash of the steps at that moment; `history` row |
| `confirmed` | Anyone edits name, owner, trigger, steps, inputs or outputs | `edited` | `confirmed` cleared (kept in `history`); Nira line to the owner |
| `confirmed` | Any editor changes only links (measures, sources) | `confirmed` | Link rows only; the confirmation stands because links do not change what the owner confirmed |
| any | Owner presses "Not mine, it is X" | `edited` with the new owner | `owner` cell updated; Pulse line to the new owner |
| any | Committee removes a process | `removed` (soft) | `removed: {by, at, reason}`; process leaves counters, stays in history and in the charter's change note |

Question state: `queued` (over the cap) to `open` (sent, the person has fewer than three open) to `answered` or `dropped` (reason required). Written to `questions[]` in the record.

Map state (derived, never stored): "Not drafted" (no processes), "Drafted" (at least one, none confirmed), "In confirmation" (some confirmed), "Confirmed" (every non-removed process confirmed). The Build-ready check reads this value. Gap analysis is room 0 of the Build centre (`/centre/build/gap-analysis?from=<id>`) and reads the confirmed map from here.

## Records read and written (file or route, fields; mark Existing or New)

**New file** `intents/<id>/processes.json`, inside the intent folder beside `intents/<id>/intent.json` (ruling 12, confirmed), through `sh_platform/jsonfile.py` (strict read, atomic write, one lock), viewer-filtered like other intent content. The intent record is `intents/<id>/intent.json` and the intent's files live in the folder `intents/<id>/` (brief section 10, ruling 12). The intent record holds counts only, never a copy.

```
processes.json: {
  version: int,                       # incremented on every write; 409 on a stale version (as in 01)
  intent_id,
  drafted_at, drafted_from: {cards: n, interviews: n, documents: n},
  processes: [{
    id, cluster,                      # cluster id from the wall session
    name, owner, trigger, frequency,  # each a provenance cell (value, mark, by, at, from, ref?, agent?)
    inputs: cell(list), outputs: cell(list),
    steps: [{
      id, order, name,                # name: cell
      actor: cell,                    # role or person, free text or person id
      systems: cell(list of profile system ids),
      inputs: cell(list), outputs: cell(list),
      produces: [measure_id],         # measures this step produces
      uses: [measure_id],             # measures this step consumes
      sources: [source_id]            # data sources of 28 used here
    }],
    breaks: [{ id, card_id|null, text: cell, sealed_card: bool }],
    status: guessed|edited|confirmed|removed,
    confirmed: null | {by, at, steps_hash},
    removed: null | {by, at, reason},
    history: [{by, at, kind, field, was?}]
  }],
  questions: [{ id, process_id, step_id|null, to_person, text, state, asked_at, answered_at|null, answer: cell|null, dropped_reason|null }]
}
```

**Existing, read:**
- `profile.json` cards section (`sh_platform/profile/cards.py` and `store.py`): `lane`, `q1` to `q4`, `cluster`, `shelf`, `sealed`, `anonymous`. q2 "where it bites" is the source of the "breaks" lines; q3 "tracked today and source" names systems.
- `profile.json` `systems.<id>.<field>` and `people.<id>.<field>` cells: the system chips and the owner picker.
- `profile.json` `interviews.<person>.<qn>`: interview answers (cells with `ref.kind` "interview").
- Context documents through `sh_platform/profile/reader.py` `passages` and the group reader: pains with `what`, `who`, `how_often`; systems; people.
- `m2_baseline` catalogue and glossary: the measures for the link picker.
- `intents/<id>/intent.json`: `refs.wall_session_ids`, `people`, `areas`, `stages` (01).
- The 28 data sources record: the source picker.

**Existing, written:** none. The profile is not written by this feature. A step answer from an owner stays in `processes.json`.

**New routes** (declared in `sh_platform/route_permissions.yaml`, default deny; roles as 01):

| Route | Does | Body | Returns |
|---|---|---|---|
| `GET /api/intents/{id}/processes` | The map at the viewer's tier | none | `processes.json` cut to what the viewer may see |
| `POST /api/intents/{id}/processes/draft` | Lens drafts or redrafts | `version` | New and changed processes; never touches `edited` or `confirmed` cells |
| `POST /api/intents/{id}/processes` | Add a process | `version`, cell values | The process |
| `PATCH /api/intents/{id}/processes/{pid}` | Edit fields, links, steps; reorder; split; merge | `version`, change | The process (or two, for a split) |
| `POST /api/intents/{id}/processes/{pid}/confirm` | Owner confirms | `version` | The process; 403 unless the caller is the named owner |
| `POST /api/intents/{id}/processes/{pid}/handover` | "Not mine, it is X" | `version`, `to_person` | The process |
| `DELETE /api/intents/{id}/processes/{pid}` | Soft remove | `version`, `reason` | The process with `removed` set |
| `POST /api/intents/{id}/process-questions/{qid}/answer` | Answer or "I do not know" | `answer` or `dropped_reason` | The question |
| `GET /api/intents/{id}/processes/charter-page` | Rendered "Processes involved" data | none | Page data for the charter |

## Fields this feature adds to the intent record

| Field | Shape | Meaning | Written by |
|---|---|---|---|
| `refs.processes_file` | string, `intents/<id>/processes.json`, or null | Pointer to the map; ids only, never a copy | The first draft or add route |
| `outcome.processes` | `{count, confirmed, state}`, an object from the moment the intent opens (`{0, 0, "Not drafted"}`, never null, ruling 6) | Counts and the derived map state at close, copied from the record at that moment so a closed intent reads without opening the file | The close route (01) calls the counter function |

No existing field is renamed.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

**Lens drafts** (agent flag `lens` on every cell it writes, mark `guessed`, `from` a plain label such as "Card: Prices arrive late" or "Interview with Aaron" or "Operations handbook, page 4", `ref` the machine pointer):
- Processes from the wall cards: cards in a cluster that name an activity ("month-end close", "fund pricing") become a candidate process, with the card's q2 as a break line and q3's system as a system chip.
- Triggers, frequencies, inputs, outputs and owners only where a document or interview states them. `how_often` from a document pain maps to the frequency cell as written, not converted.
- Steps only where a source lists them in order. A source that lists steps loosely gives the steps with the same mark and passage. A process with no source steps has an empty step list.
- Suggested links between steps and measures when the measure's technical definition names the system the step uses, marked guessed.

**Lens never invents a step.** If a step is unknown, Lens writes no step and asks. It also never fills a trigger or owner by pattern ("finance usually..."). Pack content (industry suggestions) can be shown beside a process as a suggestion labelled "What others in the industry usually do", never written into a cell.

**Lens asks** (A-045, at most 3 questions per owner): an unknown step, trigger, hand-off or system becomes a question to the process owner (or, with no owner, to the person who wrote the nearest card). At most three open per person. The cap is the shared Define cap: three open per person across process map, glossary, catalogue and governed state together. Surplus questions stay `queued`.

**North**: keeps the Define clock; adds the line "Process map: 3 of 7 confirmed" to its next-step list; nudges owners whose confirmation is the last thing blocking Build-ready; writes the "Processes involved" page into the charter draft. North does not confirm.

**Nira**: puts "Confirm the process 'Month-end fund pricing'" and "You have 2 questions about a process" in the owner's waiting list and on the Pulse page.

**Person acts at**: Add a process; Edit, Split, Merge; Link a measure or source; Confirm this process (owner only); Answer a question (the asked person only); Remove (committee, with reason).

## Rules (visibility, time box, who may do what)

- **Who confirms:** only the named owner of the process. The process owner is the business owner of that process (ruling 11); the data owner and source owner are different roles, named in 28 and the catalogue. The organiser, sponsor and analyst can edit but cannot confirm for another person. If the owner has left or cannot be reached, the organiser may name another owner (a history row), who then confirms. This is not a bypass of the owner.
- **No invented step.** A server check refuses an agent write to `steps` unless every step cell carries a `from` and a `ref`. A person's own step needs only their name.
- **Marks:** guessed, stated, unknown, as `sh_platform/profile/store.py`. An agent write never overwrites a cell a person wrote (rule 7 in `CLAUDE.md`). A redraft adds or updates only guessed cells and offers the rest as a suggestion.
- **Three questions per person** (A-045, ruling 9): three open questions per person across Define (process map, glossary, catalogue and governed state together). Surplus questions stay `queued`.
- **Sealed and anonymous cards** keep the v1 rules (D-013). A break line from an anonymous card shows its words and never the author. A break from a sealed card shows only to those who may see that card; to everyone else the line reads "1 sealed card" and no words. Lens does not draft a process from a sealed card for a viewer who may not see it, and the draft never quotes sealed words. A guest link never carries sealed or anonymous text.
- **Visibility:** the three tiers of 01 apply. Participants and observers see the map (observers read, never write or confirm). An affected person (by area or named) sees the map only when the organiser switched on "affected people may read" at creation (default off) or when named on a share; otherwise they see "Process map: 7 processes, 4 confirmed" and nothing else. Super admin sees existence only, never content. Company admin sees the counts and the charter page once closed. A draft intent is visible only to the person who started it.
- **Numbers and time:** times show in the company's time zone from the profile, else UTC. Counts are exact. This feature shows no mean, median or per-person figure.
- **Time box:** the map has no clock of its own. It lives inside the Define stage; at close, unconfirmed processes stay in the charter marked "Not yet confirmed by its owner". Nothing is hidden or deleted at close.
- **Build-ready:** a map in state "Not drafted" is not a blocker by itself, because an initiative may touch no process. The check reads: every confirmed or guessed process has an owner, and the committee has recorded "no processes involved" if the map is empty. Open question 3.
- **Industry:** no process, step or system name is hardcoded. Examples in copy come from the company's own record or are labelled illustrative.
- **Copy:** no game words; no vendor or model names; agents are North, Lens, Nira.

## Counters and measures of this feature (numbers only, each traced to a record)

| Number | Traced to |
|---|---|
| Processes mapped (excluding removed) | `processes[]` where `status != removed` |
| Confirmed by owner | `processes[].confirmed != null` |
| Still guessed | `status == guessed` |
| Edited since draft | `status == edited` |
| Steps in total; steps unknown | `steps[]`; count of questions on steps with `state` queued or open |
| Open questions; queued questions | `questions[]` by `state` |
| Processes without an owner | `owner.value` empty |
| Breaks linked to a wall card; breaks in the owner's words | `breaks[].card_id` set or null |
| Measures linked to at least one step; measures in the catalogue with no process | `steps[].produces` and `uses` against the catalogue |
| Data sources linked | `steps[].sources` |
| Processes per cluster | `processes[].cluster` |

If the catalogue does not yet exist, the measure numbers read "Not available yet. The catalogue has no measures." If the wall has no cards the drafted-from line reads the same way.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: whole-file reads of `sh_platform/process_record.py`, `profile/store.py` (first 60 lines), `profile/cards.py` and `interview/engine.py` headers; function listings of `profile/reader.py`, `profile/view.py` and `m1_intent/domain/charter*.py`; grep of `docs/specs/INTENT-CENTRE-SPEC.md` for "process"; a file listing of `ui/src/pages`. Line ranges below come from those reads.

| Found | Decision |
|---|---|
| `sh_platform/process_record.py` (lines 1 to 208): `ProcessRecords`, a two-way link between a module session and its outcome (D-026): ids, states, timestamps, label. It is not a business process record. | **Not used for the map, name clash.** It holds no steps, owners or systems, and its file is `context/process_records.json`. The new file is `processes.json` and the spec says "process map" and "business process" in copy to avoid confusion. Its pattern is reused: strict read, atomic write, lock, no overwrite of an unreadable file (via `sh_platform/jsonfile.py`, lines 1 to 12). |
| `sh_platform/profile/store.py` lines 1 to 66: `cell()`, `is_agent()`, marks, `agent` flag, `ref` kinds | **Reused as is** for every cell in `processes.json`. One reshape: `KINDS` gains `card` so a break can point at a wall card. Open question 4. |
| `sh_platform/profile/store.py` lines 94 to 118: `set_cell`, `record`, `drop_drafts`, "a draft never overwrites a person's cell" | **Copied in rule** into the map writer (the same function cannot be called because it is bound to `profile.json`). |
| `sh_platform/profile/cards.py` (lines 1 to 36): card shape with `q1` to `q4`, `cluster`, `sealed`, `anonymous` | **Read only.** q2 is "where it bites". |
| `sh_platform/profile/reader.py` lines 243 to 340 and `contract.yaml` lines 28 to 45: document reading that already extracts `pains` (what, who, how_often), systems, people with the passage | **Reused**: Lens's document source for frequency, owner and systems. No new reader. |
| `sh_platform/interview/engine.py` and `interviews.<person>.<qn>` cells | **Reused** as the interview source. The map reads, never writes. |
| `sh_platform/profile/view.py` (`Viewer`, `norm`, `allows`, `sees_area`) | **Reused** for the visibility cut, through the intent view function of 01. |
| `modules/m1_intent/domain/charter.py` and `charter_export.py` (`to_markdown`, `to_html`, `_wall`) | **Reshaped**: a "Processes involved" page is added to the export as one more section; the charter's one signature rule is unchanged. |
| `ui/src/pages/OwnerAnswerPage.tsx` and the guest link in `sh_platform/public_link.py` | **Reused** for Screen C and the token link. |
| `ui/src/pages/CentrePage.tsx` Define links (lines 95 to 99) | **Reshaped**: the new tab sits in the Define screen. No new page. |
| A step strip or process drawing component | **Searched, none found in `ui/src`.** New and small: chips and arrows in CSS, no diagramming library. |
| A business process model in the earlier repo (`earlier-repo`) | **Not checked in this session**; the builder runs `graft ask "process map"` in that repo first (reuse-first rule, D-031) and ports anything it finds. |

## Not in this feature

- Any diagramming tool, swimlanes, BPMN or free drawing. The drawing is a strip of chips only.
- Process mining, measuring cycle times or costs from system logs.
- Automating or redesigning a process. This maps what happens today.
- Data source records and their checks (28). Here a step only points at them.
- The glossary, catalogue and governed state definitions. Here a step only links to a measure.
- Process maps outside an Initiative (a Problem may link to a process through `links`, nothing more).
- Signing. The owner confirms a process; the sponsor signs the charter, as in v1.

## Open questions

1. Settled, not open: `intents/<id>/processes.json` lives in the intent folder (ruling 12). Number kept so later references hold.
2. Frequency: free text with quick chips, or a fixed list with a count? The spec keeps free text because no rule is given.
3. Build-ready rule: what counts as enough? Proposed above: every process has an owner and a recorded "no processes involved" for an empty map. Needs Nitin's call. No threshold is invented (for example, "at least one process per Must cluster").
4. `KINDS` in `sh_platform/profile/store.py` has no `card`. Add it there, or keep a map-local list?
5. The shared cap of three (A-045): ruling 9 says per person across Define; confirm whether it counts per intent or across all open intents. Written here as per intent.
6. How a step names a system: by profile system id only, or also by free text when the system is not in the profile? Written here as id only, with "Add system to the profile" as a button; confirm.
7. Who is the owner of a process Lens drafts from an anonymous card, when the card names no one? Written here as no owner and a question to the organiser; confirm.
8. Whether a link change (measure or source) should clear confirmation. Written here as no, because the owner confirms steps, not links.
9. `/owner-answer/{token}` is an existing guest page outside the `/centre/intent/...` convention. Keep it as built, or move it under the intent routes? The guest API stays under `/api/modules/<module>/` (ruling 1).
10. The query parameters `?tab=process-map` and `&process=<pid>` sit on `/centre/intent/<id>/define`; the brief names no query convention for Define tabs. Confirm.
