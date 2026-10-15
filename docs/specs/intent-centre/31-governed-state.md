# 31. Governed state per measure

Part of: Intent Centre v2. Depends on: 01 (intent record, `refs.baseline_ids`), 05 (areas and visibility), 06 (people and roles in an intent), 14 (permissions matrix). Feeds: 09 (closure and sign-off: the build-ready flag), 13 (Pulse lines), 19 (counters), and Build (access rules, Feeds, Moment of truth).

## Purpose (three sentences)

Every measure an Initiative defines carries one governed state: six fields (owners as business, data and source owner, classification, who may see, resolving team and target week, affected downstream, review date), each a provenance cell that Lens drafts and a named person confirms. The Define stage shows it as a ring on each cluster and a panel on the selected cluster, with four percentages that each trace to the stored cells. The state belongs to the measure, not to the Initiative: it is set once, applies company-wide, and Build reads it without asking anyone again.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger | What they do |
|---|---|---|---|
| Katie (analyst) | Define strategically, after clusters are shelved | Opens the Define screen | Reads Lens's six drafts, chases the named people; confirms nothing she is not named for |
| Harvey (owner) | Define, or from his Pulse line | "N part(s) wait for your confirmation" | Confirms owners and affected downstream for measures he owns |
| Grace (approver, governance lead) | Define | Pulse line, or Define ring | Confirms classification and who may see |
| Daniel (sponsor) | At shelving | Cluster moved to a shelf | Confirms resolving team and target week |
| Janet (organiser) | Build-ready check | Closing Define | Sees which Must measures are not fully governed; cannot confirm for others |
| Company admin | Anytime | Opens the Initiative | Sees that the Initiative exists and its outcome; confirms nothing for others (A-069). Whether the admin reads measure cells is Open question 9 |
| Observer | Any time in Define | Invited by the organiser | Reads what a participant reads; never confirms or proposes |
| Later initiative's people | A new Initiative uses a measure already governed | Measure added to Define | See the existing state as confirmed; may propose a change |

## Entry points (every route, link, Pulse line, button that leads here)

- Define screen `/centre/intent/<id>/define` (reshaped: v1 routes it by wall session id as `/centre/intent/define/:sessionId`; the session is reached from the intent record by reference): the ring on each cluster card; "Governed state" panel on the selected cluster (`LensPanel`).
- Baseline page `/centre/intent/baseline/:baselineId` (Existing route; the brief's route convention has no baseline view, so its new home is Open question 10): "Governed state" side card per measure, with the confirm buttons. This is the same panel, not a second one.
- Pulse "Decide" line `confirm:<baseline>:<measure>` (Existing, `sh_platform/pulse/lines.py` 144-159): button "Confirm", opens the baseline page. Fixed in this spec to count only the parts the viewer may confirm.
- Build-ready check at `/centre/intent/<id>/build-ready` (spec 09): link "Open governed state" to `/centre/intent/<id>/define`.
- Centre home `/centre/intent`, "How well governed" side card (Existing, `CentrePage.tsx`): link to Define of the viewer's latest open Initiative.
- Sign-off panel on the baseline page (Existing, `BaselineSignoff.tsx`): "Is every Must measure governed?"; each listed measure links to its panel.

## Screens, element by element

### Screen A: Define, cluster ring and Governed state panel

Route: `/centre/intent/<id>/define`. Layout at 1280: shelves in columns (left, wide), Lens panel on the right (about 360 wide), with the percentage strip across the top of the shelves. At 390: one column; shelves stack; the Lens panel opens as a bottom sheet when a cluster is tapped; the percentage strip becomes four rows.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Percentage strip | panel of four bars | Owned, Classified, Who may see confirmed, Team assigned, each as `n of m measures` and a rounded percentage | Click a bar: filters clusters to those still missing that field | Participants, observers, organiser; affected only when the organiser has switched on "affected people may read" (measures they may see only) | "Governed: Not available yet. No measures have been named in this Initiative." |
| Ring on a cluster card | chip | Solid ring and "Governed" when every measure behind the cluster has all six fields stated; dashed ring and "Needs: owner, classification" otherwise | Click: selects the cluster, opens its panel | Anyone who may see the cluster | "Governed: Not available yet" (cluster has no measure codes yet) |
| Pill "Owner not confirmed: Harvey" | chip | Owners (business, data or source) whose cell is still guessed, each name once | Click: filters the shelves to measures waiting on that person | Anyone who may see the measure | Hidden |
| "Governed state" card per measure | panel | Title "Governed state: <measure>", count "n of 6", six rows | See rows | Those who may see the measure; a sealed measure shows no card to others | "Governed state: Not available yet" |
| Row "Owner" | provenance cell | `Business owner: Harvey · Data owner: Katie · Source owner: Not set`; mark (Guessed by Lens, from the work list's owners / Confirmed by Harvey) | Button "Confirm owners" (only the named owner of that kind or head of data sees it enabled) | As card | "Not set" with source "Not drafted yet" |
| Row "Classification" | provenance cell | open, personal, sensitive or restricted with mark and source | "Confirm classification" with a four-way choice; enabled for governance lead only | As card | As above |
| Row "Who may see" | provenance cell | Names; "Everyone with access" when the list is empty and classification is open | "Confirm who may see" with a name picker over the Initiative's people and company accounts; governance lead only | As card | As above |
| Row "Who resolves it" | provenance cell | `Team, by week N` | "Confirm team and week" with a team field and a whole week number (range: Open question 8); sponsor only | As card | As above |
| Row "What it affects" | provenance cell | List of measure names | "Confirm what it affects"; named owner only; list may be edited before confirming | As card | As above |
| Row "Review date" | provenance cell | A date; default date marked Guessed, from "default" (rule: Open question 3); shown in the company's time zone, else UTC | "Confirm review date"; any of the four named confirmers | As card | As above |
| Button "Ask Lens to draft again" | button | Re-runs the draft; a stated cell is kept | Calls the draft; shows "Drafted n of 6 again. Confirmed parts were kept." | Organiser, analyst | Hidden when all six are stated |
| Line "Only the person named for this part can confirm it. Ask them, or ask the sponsor to name them." | agent line (refusal) | Shown beside a disabled button on hover or tap | None | Anyone not named | Hidden |
| Row "Proposal waiting" | agent line | `<name> proposed <value> for <field>: <reason>`, with proposer and date | Buttons "Apply proposal" (writes the proposed value as stated by the clicker), "Decline proposal" (asks for a reason, then writes it) and, for the proposer only, "Withdraw" (removes it) | The person named for that field and the proposer; others read the line without buttons | Hidden when no proposal waits |
| Link "Propose a change" | button | Appears on a measure whose six fields are stated in an earlier Initiative | Opens the change form (Screen B) | Organiser, analyst, named owner (not observers) | Hidden when the state is not yet confirmed |

Numbers on Screen A: each percentage and each "n of 6" is counted from the stored cells in `governed_state.json` (Counters section); otherwise the screen says "Not available yet" and names the missing record.

### Screen B: Propose a change (modal over Define)

Route: none; a modal on Screen A. At 1280, centred 480 wide. At 390, full-screen sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Header | text | "Change the governed state of <measure>" and "Confirmed by <name> on <date> in <Initiative title>" | None | As Screen A | Not shown without a confirmed state |
| Field picker | field | The six fields | Choose one field | As above | None |
| Current cell | text | The stored value, mark and who confirmed | None | As above | None |
| Proposed value | field | Input matching the field's shape (same checks as `domain/governed.clean`) | Typing validates; plain error "That answer is not in a form this part accepts." | As above | Button disabled |
| Reason | field | One line, required | Typing | As above | Button disabled |
| Button "Send proposal" | button | None | Writes a proposal beside the stored cell (see Records); the stored cell stays as it is until the person named for that field confirms | As above | Disabled until value and reason are set |
| Button "Cancel" | button | None | Closes | As above | None |

### Screen C: Build-ready check row for governance

Route: `/centre/intent/<id>/build-ready`. Layout at 1280: one row in the check list; at 390 the row stacks title above reasons.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Row "Is every Must measure governed?" | panel | `n of m Must measures governed`; Should count as a separate grey line "n of m Should measures governed" | Click opens Screen A at the first gap | Participants, observers, organiser; affected only when "affected people may read" is on | "No Must measure is in this Initiative yet." |
| List "Not governed yet" | list | `<Measure>: owners, who may see not stated yet` per Must measure | Click: opens that measure's panel | As above | Hidden when none |
| Refusal line | agent line | The refusal copy under Rules | None | As above | Hidden when the check passes |

Numbers on Screen C: counted from `kpis.json` priority and the six cells in `governed_state.json` (Counters section).

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet opens Define from the Initiative page (`/centre/intent/<id>/define`) and shelves clusters. Lens runs `draft_all` over every measure the viewer may see, once, on first look (Existing, `api/governed.py` `read`). No model call; it uses the work list, the profile (RACI, field rules, restricted areas, deadlines) and the pack.
2. Lens first checks whether the measure already has a stated governed state from an earlier Initiative. If so it copies those stated cells into this baseline as stated, keeping the original confirmer and date (New). Otherwise it drafts the six cells as Guessed with a plain source.
3. The strip and rings show the first percentages. Katie reads the panel for each cluster.
4. Harvey gets a Pulse "Decide" line for the parts he may confirm. He opens the panel, edits the owner list if needed, and clicks "Confirm owners". The route checks he is a named owner. The cell becomes stated by Harvey, with the time.
5. Grace confirms classification and who may see. Daniel confirms resolving team and target week when the cluster is moved to a shelf. Harvey confirms what it affects. Review date stays at the default until one of the four confirms it.
6. A person who is not named clicks a confirm button. Nothing is written. The refusal line shows.
7. The rings go solid as the last field on each cluster is stated. Percentages rise; Lens does not change them, only stated cells count.
8. Janet closes Define. The build-ready check reads the stored cells. If a Must measure is missing a field, the refusal copy lists it and the Initiative cannot be marked build-ready.
9. A month later a second Initiative adds the same measure. Its Define screen shows the state as confirmed. Katie clicks "Propose a change", picks "Who may see", gives a reason, and sends. The stored cell is unchanged; Grace sees a Pulse line and confirms or declines.
10. On confirm, the stored cell becomes the new value and the old one is kept as a version (Records). Build reads the new value from then on.
11. Each confirm or proposal appends one line to the intent's events file (Records). Katie leaves Define by closing the panel or opening the build-ready check; the confirmer leaves the screen. North then reports counts only on the Initiative.

## States and transitions (table: state, who moves it, to what, what is written)

Per cell (Existing, `domain/governed.py`):

| State | Who moves it | To what | What is written |
|---|---|---|---|
| unknown | Lens (draft with no value) | guessed | cell `{value, mark: "guessed", by: "Lens", from, agent: "lens"}` |
| guessed | Lens (a fresh draft) | guessed (new value) | cell replaced; allowed |
| guessed | Named person (confirm) | stated | cell `{value, mark: "stated", by: <name>, from: "confirmed in Define", at}` |
| stated | Lens (draft) | stated (kept) | nothing; `keep_old` refuses |
| stated | Named person (confirm, same field) | stated (new value) | cell replaced on the working baseline before it is signed |
| stated | Anyone, once the baseline is signed | refused | nothing; "This baseline is signed and read-only. Changes need a new version." |

Per proposal (New):

| State | Who moves it | To what | What is written |
|---|---|---|---|
| none | Organiser, analyst, named owner (Send proposal) | proposed | `proposals[field]` beside the cell: `{value, reason, by, at, initiative_id}` |
| proposed | The person named for that field (Confirm) | applied | cell becomes the proposed value, stated by that person; the old cell is appended to `history[field]`; `proposals[field]` is removed |
| proposed | The person named for that field (Decline, with a reason) | declined | `proposals[field]` gets `declined: {by, at, reason}`; the stored cell is unchanged |
| proposed | Proposer (Withdraw) | removed | `proposals[field]` removed |

Per measure: `complete` is true only when all six cells are stated. It is never a score.

## Records read and written (file or route, fields; mark Existing or New)

**Where the governed block lives today.** One file per baseline: `intents/m2_baseline/<baseline id>/governed_state.json` in the company plane, shape `{measure id: {owners, classification, may_see, resolving, affects, review_date}}`, each a provenance cell `{value, mark, by, at, from, agent?}` (Existing; `modules/m2_baseline/store/governed.py` `FILE`, contract `modules/m2_baseline/contracts/governed_state.yaml`). The inputs Lens drafts from stay where they are: the profile's `governance.field_rules`, `governance.restricted_areas`, `people`, `constraints` (via `sh_platform/profile/store.py`), the work list's `owners` and `governance` per measure (`kpis.json`), and the pack's `kpi_tree` drives. This spec creates no second place for the state itself.

| Record | Fields | Mark |
|---|---|---|
| `GET /api/modules/m2_baseline/baselines/{id}/governed` | `{measures: [{id, name, state, complete, governed, missing}], percentages: {owned, classified, may_see_confirmed, sealed}}`; first look drafts | Existing |
| `POST .../baselines/{id}/governed/{measure}/confirm` | body `{field, value}`; 403 with the refusal sentence when not the named person | Existing |
| `governed_state.json` entry | the six cells | Existing |
| `governed_state.json` entry, key `proposals` | `{field: {value, reason, by, at, initiative_id, declined?}}` | New |
| `governed_state.json` entry, key `history` | `{field: [{cell, replaced_at, replaced_by, initiative_id}]}` | New |
| `governed_state.json` entry, key `carried_from` | `{baseline_id, at}` when stated cells were copied forward | New |
| `POST /api/intents/{id}/governed/{measure}/propose` | body `{field, value, reason}`; the intent id resolves the baseline | New |
| `POST /api/intents/{id}/governed/{measure}/withdraw` | body `{field}`; proposer only | New |
| `POST /api/intents/{id}/governed/{measure}/proposal/{field}/decide` | body `{decision: "apply"|"decline", reason?}`; same who-may-confirm check as `confirm` | New |
| `intents/<id>/intent.json` | read for the baseline pointer (`refs.baseline_ids` as named in spec 01; the brief's section 3 shows `links` only, Open question 13); nothing is copied into the intent | New (spec 01) |
| `intents/<id>/events.jsonl` | one line appended per confirm, propose, apply, decline, withdraw: `{kind, measure, field, by, at}`; kind names are spec 16's | New (spec 16) |
| Profile `governance` block | read by Lens; never written by this feature | Existing |
| Contract change: owners cell keys | `business`, `data`, `source` (replaces `process`) | New |
| `sh_platform/pulse/lines.py` `measures` | reads the entry; adds the who-may-confirm filter | Existing, reshaped |

The company-wide read is one helper over the same files: for a measure id, the stated entry from the newest signed baseline, else the working baseline's entry. `sh_platform/consume/feeds.py` `_build` and `sh_platform/graph/register.py` `_business_owners` already pick "signed baseline, else first"; they move to this one helper (reshaped), so the two cannot disagree.

## Fields this feature adds to the intent record

None. The intent record points at the baseline by `refs.baseline_ids`. Counts on the Initiative page are worked out at read time from `governed_state.json`; nothing is stored on the intent.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

| Field | Lens drafts from | Confirmed by (person acts) |
|---|---|---|
| Owners (business owner, data owner, source owner) | the work list's owners, RACI and interviews in the profile; the source owner from the data sources map (Open question 11) | each named owner of that kind, or the head of data |
| Classification | the measure's personal and sensitive answers; the profile's field rules and restricted areas (the strictest wins; not sure counts as personal) | governance lead (approver role or head of data) |
| Who may see | the measure's may_see, restricted areas and field rules | governance lead |
| Resolving team and target week | the business owner's team in the profile; the nearest profile deadline that names the measure or team ("week N") | sponsor, at shelving |
| Affected downstream | the pack's dependencies (`drives`) and "who feels this" taps | named owner |
| Review date | a default date, marked Guessed, from "default" (Open question 3) | any of named owner, head of data, governance lead, sponsor |

**How the six fields map to owner kinds.** Three owner kinds are used everywhere: business owner, data owner, source owner. The governed state's process owner is the business owner of the process (31 and 28 agree), so it has no cell of its own.

| Field | Who confirms | Note |
|---|---|---|
| Owners | business owner confirms the business slot, data owner the data slot, source owner the source slot; head of data may confirm any | v1 stores `business`, `data`, `process` (`domain/governed.py` line 19); `process` folds into `business` and `source` is new (Open question 11) |
| Classification | governance lead (approver role or head of data) | not an owner kind |
| Who may see | governance lead | not an owner kind |
| Resolving team and target week | sponsor, at shelving | the business owner's team drafts it |
| Affected downstream | business owner | v1 says "named owner"; this reading is Open question 12 |
| Review date | any of business owner, data owner, governance lead, sponsor | v1 allows four confirmers |

- **Lens** drafts all six on first look and on "Ask Lens to draft again". It never replaces a stated cell and never replaces a person's cell with an agent's. It writes the source in plain words next to each guess. It calls no model for this feature. It copies forward stated cells from an earlier Initiative (marked "Carried from <Initiative title>") before drafting the rest.
- **Nira** adds one "Decide" line per measure with parts the viewer may confirm, and one "Decide" line to the confirmer when a proposal waits. She does not list parts the person is not named for. A person has at most three open questions across all of Define (process map, glossary, catalogue and governed state together; A-045). Further lines wait until one is answered, and North tells the organiser who is holding more than three.
- **North** holds the build-ready check: if Must measures are not governed, it says which, names the person for each missing part, and nudges them. North never confirms. If the time box will end first, North proposes: extend, close with Should measures unconfirmed, or cancel; a named person picks.
- Agents never sign. A named person confirms each field.

## Rules (visibility, time box, who may do what)

- **Who confirms.** Only the person named for the field (table above). The company admin role confirms nothing for others unless also named. Refusal copy (Existing): "Only the person named for this part can confirm it. Ask them, or ask the sponsor to name them."
- **Must and Should.** Must measures (priority `must` in the signed charter) need all six fields stated before the Initiative can be marked build-ready. Should measures never block; they show as a grey count and as unconfirmed on the panel. The v1 sign-off panel already behaves this way (`BaselineSignoff.tsx` 41-44).
- **Refusal copy for Must.** "Not ready for Build. {n} Must measures are not fully governed. {Measure}: {fields} not stated yet. Ask the person named for each part to confirm it." One measure per line, fields in plain words from the existing list (owners, classification, who may see, resolving team, affected downstream, review date). Never a role code or id.
- **One measure, one governed state.** A governed state is keyed by the measure, not the Initiative. A stated cell in one Initiative is shown as confirmed (with the confirmer and date) in every later Initiative. Lens copies it forward; nobody confirms it again. A later Initiative may propose a change as a version (Screen B); the stored cell changes only when the person named for that field confirms.
- **A change is a version.** The old cell is kept in `history`. Nothing is deleted. A signed baseline stays read-only; the new value applies from the next baseline and from the company-wide read.
- **Percentage definitions** (Existing, `domain/governed.percentages`): owned = owners stated; classified = classification stated; who may see confirmed = may_see stated; team assigned = resolving stated (New, replaces "sealed" on the strip; "sealed" stays as the fourth number on the sign-off panel, defined as classification stated and not open, and may_see stated). Each is `round(100 × count / measures the viewer may see)` as v1 computes it (Open question 16); "Not available yet" is shown instead of 0% when there are no measures.
- **Visibility.** A measure the viewer may not see does not exist for them: not in the list, not in the percentages, not confirmable (`_seen`, `W.may_see`). Sealed and anonymous wall material keeps the v1 rules. The super admin sees none of it.
- **Time box.** The panel stays editable while the Initiative's Define stage is open and the baseline is not signed. The clock is the Initiative's own (spec 01); this feature adds none.
- **Who reads.** Participants and observers read the cells; affected people read them only when the organiser switched on "affected people may read"; the super admin reads none. A draft Initiative is visible only to the person who started it. A cancelled Initiative keeps its cells and reason and appears in Past.
- **Dates and zone.** Every date shown uses the company's time zone from the profile, else UTC.
- **Counts.** Counts are exact. Percentages are shown beside "n of m"; whether a percentage under five measures needs "Fewer than five" is Open question 16.

**What reads the state downstream.**

- **Build access rules** (`sh_platform/build/blueprint_draft.py` "access" line): classification and who may see are turned into access rules at Build, with no new question asked.
- **Feeds** (`sh_platform/consume/feeds.py`): a card shows its value only to the people in `may_see` (the one helper above); a measure with no stated state shows "Not governed yet".
- **Moment of truth masking** (`modules/m3_connect`, reached from Build; gap analysis is room 0 of the Build centre at `/centre/build/gap-analysis?from=<id>`): restricted measures are scored only for those who may see them. It keeps reading the measure's `governance.may_see`; after the write-through in item 2 it agrees with the governed cell.
- **Graph and map**: `governed_by` edges and the node's "named people" count read the same cells.
- **Pulse and Centre home**: counters read the same file.
- **Affected downstream** names measures; Build uses it to warn the owners of those measures when a change is proposed.

## Counters and measures of this feature (numbers only, each traced to a record)

| Number | Where shown | Traced to |
|---|---|---|
| Owned (n of m, %) | Strip, Centre home bar | count of entries in `governed_state.json` where `owners.mark = "stated"`, over measures the viewer may see in `kpis.json` |
| Classified | Strip, Centre home bar | `classification.mark = "stated"` |
| Who may see confirmed | Strip, Centre home bar | `may_see.mark = "stated"` |
| Team assigned | Strip | `resolving.mark = "stated"` |
| Sealed | Sign-off panel | `classification.mark = "stated"`, value not `open`, and `may_see.mark = "stated"` |
| Must measures governed (n of m) | Build-ready row, sign-off panel | measures with `priority = "must"` in `kpis.json`, all six cells stated |
| Fields still missing per measure | Panel, ring | `missing` from `governed_for` (cells not stated) |
| Proposals waiting | Pulse line, panel | entries with `proposals[field]` and no `declined` |
| Measures governed (Pulse stat) | Pulse "Measures governed n of m" | `sh_platform/pulse/lines.py` `_governed` |

Not available yet cases: no baseline (strip reads "Not available yet. No baseline has been started for this Initiative."); no measures; the file missing before the first look.

## Defects in the v1 build this spec closes

Seen in the code:

1. **Owners differ by screen.** The Define ring and panel read `governed_state.json`; the Centre home "Owned" bar counts `reported_figures[].owner` in the profile (`CentrePage.tsx` 58); the Pulse line reads owners from `governed_state.json` of unsigned baselines only; Feeds and the graph read the signed baseline, else the first. One measure can show four owner answers. The owner cell also keeps a `process` kind, which ruling 11 folds into business owner, leaving three kinds (business, data, source). Fix: all read the one helper over `governed_state.json`.
2. **Two places hold who may see.** The draft copies `may_see` from the work list's `governance`, but a later confirmation writes only `governed_state.json`. Feeds reads the governed file; the work list, the glossary and Moment of truth read `kpis.json` governance (`worklist.py` `may_see`, 147-157). A confirmed list changes Feeds but not Moment of truth. Fix: confirming `may_see` or `classification` writes through to the measure's `governance` in `kpis.json` (one writer, inside the store), so both readers agree. Marked as an open question on the exact write-through.
3. **The Pulse "Confirm" line over-counts.** It counts every open field for any owner (`lines.py` 154-155), although an owner cannot confirm classification. Fix in this spec: count only fields the viewer may confirm.
4. **Centre home bars use a different rule** from the record (name matching against profile rules), so their percentages can disagree with the strip. Fix as above.
5. **The sign-off gate is partly on the client.** The Must check is in `BaselineSignoff.tsx`; the server gate (`domain/gate.py`) checks governance decided from the catalogue, not the six cells. Fix: the server's build-ready check also reads Must measures' cells.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

| Item | File and lines | Verdict |
|---|---|---|
| Six-field rules, drafts, who-may-confirm, percentages | `modules/m2_baseline/domain/governed.py` 17-194 | Existing, used as is. Percentages gain "team assigned" (reshaped, 57-68) |
| Store: `draft_governed`, `confirm_field`, `draft_all`, `governed_for` | `modules/m2_baseline/store/governed.py` 52-110 | Existing. Reshaped: carry-forward of stated cells; `proposals` and `history` keys |
| Contract | `modules/m2_baseline/contracts/governed_state.yaml` | Existing; add `proposals`, `history`, `carried_from`, and "team assigned" |
| Routes GET governed, POST confirm | `modules/m2_baseline/api/governed.py` 33-54; `sh_platform/route_permissions.yaml` 192-194 | Existing; two routes added (propose, decide) |
| Define ring and cluster card | `ui/src/modules/m1_intent/define/DefineScreen.tsx` 132-143, 271-308 | Existing, used |
| Define Governed state card | `ui/src/modules/m1_intent/define/LensPanel.tsx` 141-150; copy in `define/copy.ts` 89-92 | Existing; reshaped to add the confirm buttons and mark text per row (the buttons exist today only on the baseline page) |
| Baseline page panel with confirm | `ui/src/pages/BaselinePage.tsx` 61-125 | Existing; the Define panel reuses this component |
| Sign-off Must gate and four bars | `ui/src/pages/BaselineSignoff.tsx` 8-84 | Existing; the Initiative build-ready row reuses its Must rule |
| Centre home bars | `ui/src/pages/CentrePage.tsx` 43-64 | Reshaped: reads the record, not the profile (see below) |
| Pulse confirm line | `sh_platform/pulse/lines.py` 143-159, 403-419 | Reshaped: filter by who may confirm |
| Feeds and graph owner lookup | `sh_platform/consume/feeds.py` 50-66; `sh_platform/graph/register.py` 90-100 | Reshaped: the one company-wide helper |
| Version trail for graph nodes | `sh_platform/graph/versions.py` 40-50 | Not used for cells; `history` stays in the governed file so there is no second place |

## Not in this feature

- The business glossary, technical glossary and catalogue entries (other files in 30 to 39).
- The Build access rules, Feeds screen and Moment of truth screen themselves; this feature only supplies the cells they read.
- A score or ranking of governance; `complete` is a hard rule.
- Role definitions and sign-in; spec 06 owns who holds sponsor, approver and head of data.
- Retention clocks, SSO and SCIM.

## Open questions

1. What exactly makes a measure Must? v1 uses the charter problem's `priority`; Should is "everything else". Is that the rule for an Initiative started without a charter?
2. Should a Should measure with unconfirmed fields be an accepted risk with a reason, as the baseline sign-off does for left-out measures? Not decided; this spec only shows it as a grey count.
3. Review date: v1 defaults to today plus 91 days; the brief gives no figure. The v1 brief says "nobody; a default", the code lets four roles confirm. Which person, and what happens on the date (a Pulse line to the owner?)
4. Proposal flow: does a proposal need the original confirmer, or any person named for the field (spec uses the latter)? Does the proposer's Initiative have to be open?
5. Carry-forward: when an earlier state is stated but its confirmer has left the company, who may confirm a change? No rule exists; proposed: the company admin names a replacement.
6. Exact write-through of `may_see` and `classification` into `kpis.json` governance (item 2 above), including the account binding in `may_see_accounts`.
7. Sealed measures in the strip: should the percentage include a measure the viewer cannot see? Current rule: no; viewers may therefore see different percentages for the same Initiative. Confirm this is acceptable.
8. Whether the resolving team's target week is a week number from the Initiative start or an absolute week; v1 stores a bare number 1 to 520 and the brief gives no range.
9. May the company admin read measure cells, or only the Initiative's existence and outcome (brief section 4)? The first draft let the admin see every measure's state.
10. Where does the baseline page live under the route convention? `/centre/intent/baseline/:baselineId` is outside it.
11. Source owner: who drafts it and from what (proposed: the data sources map)? What happens to stored `process` values (proposed: read as business owner)?
12. Affected downstream: confirmed by the business owner only (proposed), or any named owner as in v1?
13. The brief's intent record has `links.build` and no `refs`. Is `refs.baseline_ids` from spec 01 the agreed pointer, and does the intent screen read governance through `/api/intents/{id}/...` or the existing module route?
14. Values the brief does not give but v1 uses: the 91-day review default and the 1 to 520 week range. Keep, or set from the company profile?
15. Which three questions reach a person first when more than three wait (A-045 cap): oldest, or Must before Should?
16. Under five measures, do the percentages need "Fewer than five" (ruling 8 names means, medians and per-person figures), and is the v1 rounding kept?
