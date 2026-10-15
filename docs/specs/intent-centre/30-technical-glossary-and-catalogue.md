# 30. Technical glossary and data catalogue

Part of: Intent Centre v2. Depends on: 00-BRIEF, 05 (areas and visibility), 06 (people and roles in an intent), 09 (closure and signoff), 28 (data sources tab), 29 (business glossary). Feeds: the charter (catalogue page), the Build-ready check, and Build step 1 (gap analysis).

## Purpose (three sentences)

For every measure an Initiative cares about, this feature records one technical definition (source, fields, calculation, period, currency) and one catalogue entry (sources, fields, personal data class, who may see it, three owners), in one place, under one code. Lens drafts both from the data sources tab, the wall and the documents and marks what it guessed; the data owner confirms. Build's gap analysis reads this and nothing else to know what each measure is made of and who to ask.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | After the data sources tab has rows, before the charter is signed | Nira line "Catalogue: 4 measures have no technical definition yet" |
| Analyst (Katie) | Working through draft entries, adding fields and calculations | Opens the Catalogue tab in Define |
| Data owner (Harvey) | Confirming the technical definition of the measures named to them | Nira line "3 definitions are waiting for you"; the emailed link (existing ask-owner mechanism) |
| Business owner of a measure | Checking that the business definition and the technical one still say the same thing | Chip "Business and technical differ" on the entry |
| Sponsor (Daniel) | Accepting a measure that stays unknown on purpose (proposal, see Open questions) | "Accept as unknown" on an entry |
| Approver (Grace) | Reading the catalogue page of the charter before signing | Charter page "Data catalogue" |
| Build (gap analysis) | First step after hand-off | Reads the confirmed catalogue by baseline reference |

## Entry points (every route, link, Pulse line, button that leads here)

- Initiative page, stage "Define strategically", tab "Catalogue" (the tab sits after "Data sources" and "Business glossary"): `/centre/intent/<id>/define?tab=catalogue`.
- Existing M2 screen for the same baseline (kept as the working surface, reached from the tab by "Open full catalogue"): `/baselines/<baseline_id>/catalogue` and `/baselines/<baseline_id>/technical`.
- Data owner link: `/baselines/<baseline_id>/my-technical` (existing M2 route, lists only the measures the signed-in person owns as data owner; inside the Initiative the same list is `/centre/intent/<id>/define?tab=catalogue&owner=me`).
- Nira line on the Initiative page and on Pulse: "4 measures have no technical definition yet" opens the tab filtered to "Not drafted".
- Build-ready check row "Catalogue complete" opens the tab filtered to what is missing.
- Charter page "Data catalogue": `/centre/intent/<id>/charter#catalogue` (read only).
- Data sources tab (28): row link "Used by 3 measures" opens the Catalogue tab filtered to that source.

## Screens, element by element

### Screen A. Catalogue tab in Define

Route `/centre/intent/<id>/define?tab=catalogue`. At 1280: left, the measure list (one row per measure, code first); centre, the selected entry (technical definition then catalogue entry); right, a panel "Waiting for" (who must confirm what) and the Lens line. At 390: the list becomes a single column of cards; selecting one opens the entry full width with a back arrow; the right panel moves under the list; every button is full width.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Tab header counts | chip row | "Confirmed 6, Draft 3, Not drafted 2, Unknown accepted 1" | Click a chip to filter the list | Participants and observers (affected people only when the organiser switched on "affected people may read") | "No measures yet. Measures come from the wall clusters in Define. Open Clusters." |
| Measure list | list | Code, name (label), data owner, state chip (Confirmed, Draft, Not drafted, Unknown accepted, Changed since confirmed), guessed count | Row click opens the entry | Participants; each row also filtered by the profile view (a measure limited to named people is a row reading "A restricted measure" for others) | "No measures yet." as above |
| Search measures | field | Matches code, label and aliases | Filters the list | Participants | Shows "No measure matches. Add it from the wall cluster, not here." |
| Draft with Lens | button | Appears when any measure is Not drafted | Starts Lens drafting for the shown measures (existing `POST /baselines/{id}/lens/technical`); the list shows "Lens is drafting 4 measures" then refreshes | Organiser, analyst | Hidden when nothing is Not drafted |
| Redraft | button (per entry) | Present when Lens has drafted before | Existing `lens/technical/redraft`; a person's part is never overwritten, the draft waits beside it | Organiser, analyst | Hidden before the first draft |
| Entry header | panel | Code (fixed, read only), label (editable), aliases, version "v3", state chip | Edit label writes the label and an alias, never a new id (see "The one-id rule") | Participants | n/a |
| Technical definition block | panel | Nine parts in the existing order: Sources, Tables, Fields, Calculation, Filters, Grain, Period, Currency basis, Notes. Each part has a mark chip: stated, guessed, unknown, and "from" (which document or tab) | Edit a part (existing `PUT .../kpis/{kpi_id}/technical`); Sources, Tables and Fields are pickers of catalogue rows, never free text | Analyst, organiser edit; data owner edits and confirms; others read | Each empty part reads "Not drafted yet. Lens has not found it in the sources or documents." |
| Use Lens's draft | button (per part) | Shows the waiting draft beside a person's part | Existing `.../technical/use`; writes the draft over the part and marks it with the person who used it | Analyst, organiser, data owner | Hidden when no draft waits |
| Business definition line | panel | The business glossary wording for the same code, read only | "Open glossary entry" | Participants | "No business definition yet. The business glossary (29) must name this measure first." |
| Catalogue entry block | panel | Sources (with source owner), fields (name, personal data class), who may see, business owner, data owner, source owner | Edit opens the existing catalogue row editor for the linked rows | Analyst, organiser; data owner for the fields they own | "No sources linked. Pick them from the data sources tab." |
| Personal data class | chip per field | open, personal, sensitive, restricted (existing governed classes) | Change writes the field row and a version line; who may lower a class is an open question | Data owner, organiser | "Not decided yet" in amber; blocks Build-ready |
| Who may see | chip list | Named roles and people for this measure and its fields | Edit writes the existing governed `may_see` | Organiser, data owner | "Everyone in the Initiative" shown explicitly, never blank |
| Owners row | panel | Business owner (also the owner of the process the measure belongs to), data owner, source owner, each with a person or "Not named" | "Name an owner" picks from the Initiative's people and the company directory | Organiser | "Not named" in amber |
| Ask owner | button | "Ask Harvey about the calculation" | Existing `POST .../ambiguities/{amb_id}/ask`: emails the link, names the question, keeps no secret in the mail | Organiser, analyst | Hidden when nothing is open |
| Confirm as data owner | button | "I confirm this definition as it stands (v3)" | Existing `POST .../technical/confirm`; refused unless the signed-in person is the named data owner | The named data owner only | Disabled with reason "Fill Sources, Fields and Calculation first" |
| Send back | button | "Send back to Katie" with a reason field | Existing `POST .../measures/{kpi_id}/send-back`; state returns to Draft | Data owner, business owner | Hidden when Draft |
| Accept as unknown | button | "Accept as unknown for now" with a reason and a date to revisit | Existing sponsor acceptance on the kpis tab (Unknown accepted by, Date accepted) | Sponsor only | Hidden to others (proposal: sponsor only) |
| Open questions list | list | The ambiguities on this measure (kind, question, status open, settled, accepted) | Answer, Accept, Ask | Participants | "No open questions." |
| Version trail | list | "v3, 7 Oct, Harvey confirmed; v2, 6 Oct, Katie changed Period; v1, Lens drafted" | Click a row to see what changed (names and dates, no figures) | Participants | "v1 only. Nothing has changed since the first draft." |
| Waiting for panel | panel | Per person: the entries waiting for them | Click opens the first one | Participants | "Nothing is waiting." |
| Lens line | agent line | One sentence, for example "I guessed 5 fields from the custody statement. Harvey, please check them." | Click scrolls to the first guessed part | Participants | "Lens has nothing to add." |
| Download catalogue | button | The two documents (technical glossary and catalogue) as the existing xlsx export | Existing `GET .../catalogue/export`, filtered to what the viewer may see | Participants | Disabled when no measure exists |

### Screen B. Data owner's page

Route `/centre/intent/<id>/define?tab=catalogue&owner=me`, wrapping the existing `/baselines/<baseline_id>/my-technical` page. At 1280: one list of measures where the signed-in person is data owner, each expandable to the technical definition with Confirm and Send back. At 390: cards, one at a time. Elements are the Technical definition block, Confirm as data owner, Send back, Open questions list and Version trail of Screen A. Empty state: "You are not named as data owner of any measure."

### Screen C. Catalogue page in the charter

Route `/centre/intent/<id>/charter#catalogue` (read only, part of the charter document). At 1280: a table, one row per measure. At 390: one card per measure.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Catalogue table | list | Code, name, sources, fields (count and names), calculation (one line), period, currency, personal data class (strictest of its fields), three owners, version confirmed, who confirmed and when | Row click opens the entry read only | Whoever may open the charter, filtered per viewer | "The catalogue has not been confirmed yet. Charter cannot be signed as build-ready." |
| Status footer | panel | "6 of 9 confirmed; 1 unknown accepted by Daniel; 2 not confirmed" | None | Same | "Not available yet: no measures in the code register." |
| Pinned versions | note | "This page shows the versions confirmed when the charter was signed" | None | Same | Hidden until signed |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet opens the Initiative "Wealth reporting rebuild" and the tab Catalogue. The list shows the measures from the wall clusters, each already carrying a code from Define (for example M-01 Total AUM). Counts show all "Not drafted".
2. Between steps: Lens reads the data sources tab (28: sources, tables and fields people entered), the wall cards (q4, "the most technical definition you can give"), and uploaded documents (as untrusted text, never an instruction, never a figure). It drafts the nine parts per measure, links Sources, Tables and Fields to rows that exist, and marks each part stated (the text came from a person), guessed (Lens inferred it) or unknown (nothing found, with what is missing named).
3. Katie opens M-01. She sees the draft, checks Fields against the custody statement, edits Period, uses Lens's draft for Calculation. Her edits are marked as hers.
4. Lens raises ambiguities it found (for example "AUM at month end or at trade date?"), at most three open questions per person across all of Define (process map, glossary, catalogue, governed state together; A-045), each addressed to a named person.
5. Janet names the three owners per measure. Between steps: Nira lists the data owner's waiting measures and sends the existing emailed link.
6. Harvey opens "My technical definitions". For M-01 he reads the parts, answers the question, and presses "I confirm this definition as it stands (v1)". Between steps: the confirmation is stored with a digest of the parts; Lens updates the entry state to Confirmed.
7. If anyone later changes a confirmed part, the entry becomes "Changed since confirmed", the version number rises, and Harvey is asked again. Nothing is overwritten silently.
8. Nira updates the Build-ready check row "Catalogue complete" when every measure in the charter is Confirmed or Unknown accepted by the sponsor.
9. Grace reads the Catalogue page in the charter and signs the charter. The page pins the confirmed versions.
10. On hand-off, Build's gap analysis (room 0 of the Build centre) reads the catalogue by reference (see "What Build's gap analysis reads"). Janet leaves the tab for the Initiative page; Harvey leaves by closing his list.

## States and transitions (table: state, who moves it, to what, what is written)

An entry (one measure's technical definition and catalogue entry) has one state.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| Not drafted | Lens drafts, or a person types a part | Draft | Parts with marks (`technical`), `technical_proposal` where a person's part exists, version v1 |
| Draft | Data owner presses Confirm (needs Sources, Fields, Calculation present) | Confirmed | `technical_confirmed {by, at, digest}`, version n+1 "confirmed" |
| Draft | Sponsor accepts as unknown | Unknown accepted | `accepted_by`, `accepted_at`, reason, revisit date; version n+1 |
| Confirmed | Anyone edits a confirmed part | Changed since confirmed | Part change with who and when; confirmation lapses (existing digest check); version n+1 "changed" |
| Changed since confirmed | Data owner re-confirms | Confirmed | New `technical_confirmed`; version n+1 |
| Draft or Confirmed | Data owner or business owner sends back | Draft | Reason, who, when; version n+1 |
| Unknown accepted | Lens finds the missing part, or a person adds it | Draft | The part with its mark; acceptance cleared; version n+1 |
| Any | Charter signed | Pinned | Charter records the confirmed version of every entry; later changes make a new version and raise the Build change notice, never edit the signed page |

A signed baseline refuses every write (existing `SignedGuard`). A change after signing opens a new baseline version through the existing re-open flow, not an edit.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Mark |
|---|---|---|
| Baseline catalogue (`modules/m2_baseline/store/catalogue.py`), tabs sources, tables, fields, extractions, kpis | Contract `modules/m2_baseline/contracts/catalogue.yaml`: Source ID, Data owner, Contains personal data?, Who may see it; Item ID; Field ID, Feeds KPI, Personal data class; KPI ID, KPI name, Definition, Business owner, Data owner, Process owner (the existing cell; shown as the business owner, see Open questions) | Existing |
| Technical definition on the measure (`store/technical.py`, `domain/technical.py`) | `technical = {sources, tables, fields, calculation, filters, grain, period, currency_basis, notes}` each a provenance value; `technical_proposal`; `technical_confirmed {by, at, digest}` | Existing |
| Ambiguities on the measure | `{id, kind, text, question, where, raised_by, status, resolution, by, at}` | Existing |
| Governed state (`store/governed.py`) | six cells: owners, classification, may_see, resolving, affects, review_date | Existing |
| Data sources tab (28) | Source rows with owner, personal data, who may see | Existing rows, new tab (28) |
| Wall cards | `cards.*.q4` (technical definition) per card, `cluster`, `shelf` | Existing |
| Graph versions `graph/versions.json` through `sh_platform/graph/versions.append_version` | `{node id: [{v, what, by, at, ref}]}` | Existing, new use: keyed by `measure:<code>` for this feature |
| Measure code register (`catalogue_measures` in the intent's baseline) | `{code, label, aliases[], merged_into|null, minted_by, minted_at, from: wall card id|null}` | New |
| Source owner | `source_owner` per source row, read from the Sources tab `Data owner` cell | New field name, existing cell (see Open questions) |
| Catalogue pin on the charter | `charter.catalogue_pin = [{code, version, confirmed_by, confirmed_at}]` | New |
| Intent record | `links.build` reference unchanged; see "Fields this feature adds" | Existing record, new fields |

Routes reused unchanged (M2 baseline routes as built; mount prefix as in the M2 manifest): `GET /baselines/{id}/catalogue`, `POST .../catalogue/{tab}/rows`, `PUT .../catalogue/{tab}/rows/{row_id}`, `POST .../catalogue/refresh`, `GET .../catalogue/export`, `GET .../technical`, `GET .../ambiguities`, `PUT .../kpis/{kpi_id}/technical`, `POST .../technical/use`, `POST .../technical/confirm`, `GET .../my-technical`, `POST .../measures/{kpi_id}/send-back`, `POST .../lens/technical`, `POST .../lens/technical/redraft`. New routes: `GET /api/intents/{id}/catalogue` (a view that resolves the intent to its baseline and returns the Screen A list), `POST /api/intents/{id}/catalogue/measures` (mint a code, one place only, see below), `POST /api/intents/{id}/catalogue/measures/{code}/alias`, `POST /api/intents/{id}/catalogue/measures/{code}/merge`, `GET /api/intents/{id}/charter/catalogue`. Each is declared in the manifest and `route_permissions.yaml` (default deny).

## Fields this feature adds to the intent record

```
intent.catalogue: {
  baseline: ref,                       # the m2_baseline id this Initiative works in (a pointer, not a copy)
  measures: int,                       # count of live codes
  by_state: {confirmed, draft, not_drafted, unknown_accepted, changed},
  guessed_parts: int,
  checked_at,                          # when North last evaluated the Build-ready row
  ready: true|false, ready_reason|null
}
```

Counts are derived from the baseline when read; the stored copy is a cache that North rewrites and never trusts over the baseline.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **Lens drafts** the technical definition and catalogue entry per measure when the data sources tab has at least one row or a document is attached, and again when the data sources tab changes. It reads the wall's q4 text, the data sources tab and documents. It links Sources, Tables and Fields to existing rows by id and proposes new rows only as "NEW_SOURCE", "NEW_TABLE", "NEW_FIELD" suggestions a person accepts. It marks every part stated, guessed or unknown. It never writes over a person's part: the draft waits as `technical_proposal`. It never confirms. **A person acts:** analyst edits; data owner confirms.
- **Lens raises ambiguities** (period, currency, owner, source, calculation, threshold, conflict) at most three open questions per person across all of Define (A-045). **A person acts:** answer, accept, or ask the owner.
- **Lens flags** a business and technical mismatch (the business definition names a thing the technical definition does not feed from). **A person acts:** business owner or data owner settles it.
- **Nira** keeps "waiting for you": the data owner's unconfirmed entries, the organiser's measures without owners, the sponsor's unknowns. It writes the Pulse line and the Build-ready row text. How often it asks is an open question.
- **North** evaluates the Build-ready row "Catalogue complete" at each stage clock tick and when an entry changes. If the time box will end with entries unconfirmed, North says so and proposes: extend, close with what we have (unconfirmed entries are listed as gaps in the hand-off), or cancel. **A person acts:** the organiser picks.
- Agents never sign. Confirmation is a named person's act, recorded with name and time.

## Rules (visibility, time box, who may do what)

- **Confirmation:** only the named data owner confirms a technical definition; the business owner confirms the business definition in the glossary. Who accepts an unknown is an open question (proposal: the sponsor). The organiser may name or change owners, never confirm for them (existing governed rule: "Only the person named for this part can confirm it").
- **Who reads:** participants and observers read the tab; affected people read it only when the organiser switched on "affected people may read" at creation; a draft Initiative is seen only by the person who started it. Observers never write.
- **Visibility:** every list and entry passes through `sh_platform/profile/view.py`. A measure, source or field limited to named people appears to everyone else as "A restricted measure" with no code, no label and no counts leaking. Personal data classification is shown to all participants; the content of a restricted field is not. Counts are exact. Any mean or median, and any per-person figure, shows "Fewer than five" below five records (brief ruling 8). Dates and times use the company's time zone from the profile, else UTC.
- **No figures:** the catalogue holds names, types, definitions and owners. It never holds a value from the company's data.
- **Documents** are context. Lens may quote a passage in a draft, marked with its document; the original never leaves the machine; passages that leave go through the egress gateway tokenised (D-032).
- **Time box:** the Catalogue tab is part of "Define strategically"; the Initiative's 10 working days apply. This feature adds no clock of its own. Unconfirmed entries at close are recorded as gaps in the hand-off, never hidden.
- **Charter:** the Build-ready row "Catalogue complete" reads: every measure is Confirmed or Unknown accepted. Build-ready is a check, not a room; whether an incomplete catalogue blocks signing or only shows a reason is an open question.
- **Signed content is read only.** A later change is a new version through the re-open flow (house rule 7).

### The one-id rule (a measure has exactly one node and one code)

The v1 build produced two Measure nodes for one measure. Cause, found in `sh_platform/graph/build.py`: the baseline made `measure:<code>` (line 258) while a reported figure with no case-insensitive name match to a baseline label made `measure:<slug of the name>` (lines 180 to 184), and `fed_by` read the free-text "Related KPIs" cell straight into a node id (line 284). So "Total AUM" typed on the wall and "KPI-03 Assets under management" in the baseline became two nodes, with owners and sources split between them.

The spec prevents it in six ways:

1. **One place mints a code.** `POST /api/intents/{id}/catalogue/measures` is the only writer of the code register. It is called when a wall cluster is promoted to a measure in Define, or when a person adds a measure on the Catalogue tab. The code is `M-<n>` in the Initiative, never reused, never derived from the name.
2. **The node id is `measure:<code>`, nothing else.** The graph build no longer mints a Measure node from a name. A reported figure or wall card that names a measure with no code becomes a *candidate* (a row in the Catalogue tab list, state "Candidate: not a measure yet") and creates no node until a person promotes it or links it.
3. **The name is a label and an alias on the code.** The register holds `label` and `aliases[]`. Renaming changes `label` and adds the old label to `aliases`. Searching by any alias finds the one code. A second entry that normalises (spaces and case ignored, plural ignored) to an existing label or alias is refused with "This looks like M-03 Assets under management. Link it instead?" and the person chooses Link (adds an alias) or "It is different" (names the difference in one line, kept).
4. **Every reference is a code.** "Related KPIs", "Feeds KPI" and the wall cluster link are pickers that store codes. Free text that matches no code is stored as a candidate, never as `measure:<text>`.
5. **Merge, not a second node.** If two live codes turn out to be one, `POST .../merge` retires the later code with `merged_into`, moves its sources, fields, owners and versions to the survivor, keeps the old code as an alias that redirects, and writes one version line on the survivor. Never two live nodes.
6. **A check that fails the build.** The graph build asserts that no two live Measure nodes share a normalised label or alias and that no Measure node id is a name. A failure is shown as a blocker on the Build-ready row ("Two measures share the name Total AUM: M-01 and M-07. Merge or rename.") and is a named test (see Counters).

### Versions on change

- The entry version is an integer on the code, written to `graph/versions.json` through `append_version(plane, "measure:<code>", what, by, ref)`. `what` is one plain sentence ("Period changed from month end to trade date"). No figures.
- A new version is written on: Lens first draft, any part edit, owner or class change, confirmation, send back, acceptance as unknown, merge, and rename.
- A confirmation holds only while the parts are as they were (existing `technical.digest`). A lapse is a version line "Confirmation lapsed: Calculation changed".
- Charter signing pins the version of every entry in `charter.catalogue_pin`. The pin is the reference Build reads.

### What Build's gap analysis reads

Build step 1 reads, through the hand-off record the intent points to (`links.build`) and not by copying:

| Read | From | Why |
|---|---|---|
| Measure codes and labels | Code register | The rows of the gap analysis, one per code |
| Sources per measure (id, name, type, owner) | `technical.sources` joined to the Sources tab (28); graph edge `fed_by` | Does the source exist and who owns it |
| Tables and fields per measure (name, type, personal data class, availability) | `technical.tables`, `technical.fields`; graph edge `uses` | Which fields are present, missing or unavailable |
| Calculation, filters, grain, period, currency basis | `technical.*` | What must be built |
| Marks (stated, guessed, unknown) and accepted unknowns | Provenance on each part; sponsor acceptance | Which gaps are known, which are guessed |
| Three owners per measure | Business owner, data owner, source owner | Whom to ask |
| Who may see | Governed `may_see` | What the build must restrict |
| Version pinned | `charter.catalogue_pin` | Which version the charter signed |

Build never receives personal data values or rows. It receives names and classes.

## Counters and measures of this feature (numbers only, each traced to a record)

| Number | Traced to | When not available |
|---|---|---|
| Measures | Count of live codes in the code register | "Not available yet: no measures promoted in Define" |
| Confirmed, Draft, Not drafted, Unknown accepted, Changed | State of each entry from `technical_confirmed` and the digest | Same |
| Guessed parts | Count of provenance marks equal to guessed in `technical` | "Not available yet: Lens has not drafted" |
| Measures with all three owners named | Owner cells on the kpis tab and Sources tab | "Not available yet: no measures" |
| Fields with no personal data class | Fields tab, Personal data class blank | Same |
| Open ambiguities | Ambiguity list status open | "No open questions" |
| Duplicate-name blockers | Result of the one-id check in the graph build | "Not available yet: the graph has not been built" |
| Days from first draft to last confirmation | `versions.json` first v1 and last confirmed line | "Not available yet: nothing confirmed" |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searched: `graft ask "technical definition of a measure"`, `graft ask "catalogue routes"`, `graft ask "graph node types"`, plus reading the files below.

- `modules/m2_baseline/domain/technical.py` (1 to 459): PARTS, NEEDED, `set_part`, `use_proposal`, `confirm`, `digest`, `sweep`, `view_parts`, ambiguity detection. **Reused unchanged.** The nine parts are exactly the brief's source, fields, calculation, period, currency, plus tables, filters, grain, notes.
- `modules/m2_baseline/store/technical.py` (189 lines) and `api/technical.py` (358 lines): routes at lines 93 to 345 (`/technical`, `/ambiguities`, `PUT kpis/{id}/technical`, `technical/use`, `my-technical`, `technical/confirm`, `send-back`, `lens/technical`, `lens/technical/redraft`, ambiguity answer, accept, ask). **Reused unchanged.** The new intent routes wrap them by resolving the intent to its baseline.
- `modules/m2_baseline/domain/catalogue.py` (1 to 1110), `store/catalogue.py` (209), `api/catalogue.py` (165; routes at lines 73 to 160), `contracts/catalogue.yaml` (703): five tabs, columns, row ids, the viewer filter `Viewer`, export. **Reused unchanged.** The Catalogue tab is a view; the full M2 screen stays the working surface.
- `modules/m2_baseline/domain/governed.py` and `store/governed.py`: classes open, personal, sensitive, restricted; `may_see`; owner roles business, data, process (process read as the business owner of the process, ruling 11); the refusal text. **Reused.** The "source owner" is read from the Sources tab owner cell; no new store.
- `modules/m2_baseline/domain/handoff.py` (technical import at line 10): carries technical definitions and the catalogue into the hand-off. **Reused;** the gap analysis reads this record.
- `modules/m2_baseline/agent/lens.py`, `glossary_lens.py`, `lens_rules.yaml`: Lens drafting and rules. **Reused.**
- `sh_platform/catalogue.yaml` (57 lines): **not the company's data catalogue.** It is the *platform catalogue*: the list of the six modules (`modules`), the packages that bundle them (`packages`) and the three centres (`centres`: intent, build, consume), read by the control plane for switches and entitlements. It holds no measures, sources or fields. **Not used by this feature.** It is named here so nobody writes company measures into it, and so the word "catalogue" always says which one: "platform catalogue" (modules and centres) or "data catalogue" (this feature, in the company's data plane).
- `sh_platform/graph/models.py` (`NODE_TYPES`, `EDGE_TYPES`): node types Measure, Term, Source, Field, Person; edges `defined_as` (Measure to Term), `fed_by` (Measure to Source), `uses` (Source to Field), `owned_by` (Measure, Source to Person), `governed_by`. **Reused unchanged.** The business definition is the Term node, the technical definition is the Measure's `fed_by` and `uses` edges plus the technical record. No new node type.
- `sh_platform/graph/build.py` lines 180 to 184 (`_figures`) and 258 (`_baseline`) and 284 (`fed_by` from Related KPIs): **reshaped.** Name-based Measure minting and free-text node ids are removed in favour of the code register (the one-id rule). This spec states the behaviour; a builder package makes the change.
- `sh_platform/graph/versions.py` (`append_version`, `record_versions_from_build`): **reused** for the version trail; the node id is `measure:<code>`.
- `sh_platform/profile/view.py` and `sh_platform/jsonfile.py`: viewer filtering and atomic writes. **Reused.**
- Wall card `q4` (v1 spec section on the wall): **reused** as the first input to the technical draft.

Genuinely new: the code register, the candidate state, the merge route, `charter.catalogue_pin`, the intent-level view routes, the Catalogue tab layout inside the Initiative.

## Not in this feature

- Business glossary (terms, owners, accepted ambiguities): file 29; this feature only links to it.
- The data sources tab (rows, availability, how sure): file 28; this feature reads it.
- Gap analysis, scoring, trial run, the Moment of truth screen: Build.
- The edit to `sh_platform/graph/build.py` itself (a builder package follows from the one-id rule).
- The platform catalogue (`sh_platform/catalogue.yaml`).
- Importing a company's existing catalogue file beyond the existing xlsx import in M2.
- Data values, quality scans and data quality rules (module 3 scan proposals stay in the kpis tab column "Quality rules (proposed by Lens)").

## Open questions

1. **Process owner (settled).** Three owner kinds: business, data, source. The process owner is the business owner of the process. The existing kpis tab still has a Process owner cell; proposal: show it as the business owner and read it as one. Does M2's contract change, or only the label?
2. **Code format.** `M-<n>` per Initiative, or one company-wide sequence so a measure reused by a second Initiative keeps its code? Proposal: company-wide, because the graph is company-wide.
3. **Second Initiative on the same measure.** Copy the entry, or point at the existing code and its confirmed version? Proposal: point, re-confirm only if a part changes.
4. **Personal data class.** Who may lower a class (proposal: data owner; company admin as well?). Raising immediately is also a proposal.
5. **How long a confirmation holds.** The existing rule lapses on any change. Is a time-based review wanted too? No threshold is invented here.
6. **Who may merge two codes.** Proposal: organiser with the data owner of both.
7. **Who accepts an unknown.** Proposal: the sponsor, as the existing kpis tab does. Confirm against file 06.
8. **Catalogue gate.** Does an incomplete catalogue block signing the charter, or only show on the Build-ready check? Proposal: the check shows the reason; signing as "not build-ready" stays allowed.
9. **Nira frequency.** How often may Nira repeat a waiting line to the same person?
10. **Routes.** The existing M2 pages and API (`/baselines/...`) are kept as the working surface. Is that acceptable under the `/centre/intent/...` and `/api/intents/...` convention, or are they re-mounted?
11. **Source owner.** Read from the Sources tab Data owner cell (file 28). Does 28 add a separate source owner cell?
12. **Sealed or anonymous wall cards** feeding q4: Lens must not use them in a draft; confirm.
