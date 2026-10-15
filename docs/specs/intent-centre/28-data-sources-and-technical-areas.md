# 28. Data sources and technical areas

Part of: Intent Centre v2. Depends on: 01 (intent record), 02 (stage table), 06 (people and roles), 07 (stage clock), 08 (North runner), 27 (process map), 30 (technical glossary and catalogue), 31 (governed state), the Define screen of v1 (`INTENT-CENTRE-SPEC.md` section 4). Feeds: 27 (a step links to a source), 30 (technical glossary and catalogue), 33 (build-ready check), Moment of truth in Build (`m3_connect` sources and intake).

## Purpose (three sentences)

In Define, the committee names the data sources that feed the processes today and the technical areas around them: the systems and teams, and the people who could speak for each. Lens drafts the list from the profile systems list, interviews, documents and the v1 catalogue; the source owner confirms their own source. The result is the data sources map: it is the `sources` tab of the existing catalogue plus a thin extras file, and it is what Moment of truth reads when the definitions meet the files.

Three owner kinds are kept apart everywhere on these screens, because the v1 build mixed them:

| Owner kind | Plain meaning | Question it answers | Where it is kept today | Who confirms |
|---|---|---|---|---|
| **Business owner** | Owns the process or the measure the source feeds. Cares about the result being right | "Who is hurt if this is wrong?" | governed state "Owners" (`m2_baseline/contracts/governed_state.yaml`; its "process owner" is this business owner, the owner of the process), process map step owner | that person |
| **Data owner** | Accountable for what the data means, its class and who may see it | "Who decides what this field means and who may open it?" | catalogue `sources` column F "Data owner"; governed state "Owners" | that person; the governance lead for class and who may see |
| **Source owner** (new name) | Runs the system or file the data comes out of. Knows when it lands, what breaks, how to get it | "Who do we ring when the file is late?" | Not kept apart today. `m2_baseline` questionnaire `sources[].owner` ("Who owns it") and `m3_connect/domain/intake.py` `source_plan` `owner` both use column F, so source owner and data owner were mixed | the source owner |

One person may hold two kinds. The screen never merges them into one cell.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | Before the Define session | North opens the Data sources tab once clusters exist; Pulse line "Data sources drafted, 9 to review" (the 9 is the count of drafted rows in `catalogue.json`) |
| Committee (Daniel sponsor, Katie analyst, Aaron participant) | In the Define session | Opens a cluster, then the tab, to add or correct a source and name the areas |
| Source owner (Harvey for the portfolio system) | After the draft (the wait is an Open question) | Pulse line "Confirm your source: <name>" (a `request` line) |
| Governance lead (Grace approver) | After sources are named | Confirms personal data class and who may see per source |
| Analyst (Katie) | After Define | Reads the tab as the input to 30 and 33 |

## Entry points (every route, link, Pulse line, button that leads here)

- Define view `/centre/intent/<id>/define` (reshapes the existing `ui/src/modules/m1_intent/define/DefineScreen.tsx`, which has no tab strip today and is reached by `/centre/intent/define/:sessionId` in v1; that spelling is superseded): a new tab strip **Clusters | Data sources | Glossary**; the new tab is `/centre/intent/<id>/define?tab=data-sources`.
- Intent page of an Initiative (spec 01, 04): stage chip **Define strategically** opens Define; a panel row "Data sources: 9 named, 6 confirmed" links to `/centre/intent/<id>/define?tab=data-sources`.
- Cluster panel in Define (Lens panel, `LensPanel.tsx`): link **Sources for this cluster** opens the tab filtered to that cluster.
- Pulse lines (Nira, `GET /api/pulse`): `request` "Confirm your source" to the source owner; `request` "Name who could speak for Portfolio system" to the organiser; `decision` "Two sources have no source owner" to the organiser.
- Build-ready check (33, `/centre/intent/<id>/build-ready`): a failed row "Source has no source owner" links to the source row.
- Moment of truth (Build) source map: the source panel links **Where this source was named** back to the row, read only.

## Screens, element by element

### Screen A: Data sources tab in Define

Route `/centre/intent/<id>/define?tab=data-sources`. Reads the baseline through `refs.baseline_ids[0]` of the intent.

Layout at 1280: top bar (title "Data sources", progress line "9 named, 6 confirmed by their source owner", buttons **Ask Lens to draft**, **Add a source**); left rail (cluster filter, process filter); centre: the technical areas chip strip, then the sources table; right drawer (source detail, opened on row click). At 390: filters become a select; the table becomes one card per source (name, system, three owners as three labelled lines, state pill); the drawer becomes a full screen with a Back button; the chip strip scrolls sideways.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Progress line | agent line | counts from the extras file and catalogue (section Counters) | none | all committee members, source owners (their own rows only) | "No sources named yet. Ask Lens to draft from what you have already given us." |
| **Ask Lens to draft** | button | Spinner then "Lens drafted N sources from M documents and the systems list" | `POST /api/intents/{id}/data-sources/draft`; new rows marked guessed; none replace a person's row | organiser, sponsor | Disabled with reason "Nothing to read yet. Add files in Bring what you have or the systems list." when profile `systems` is empty and no documents |
| **Add a source** | button | Opens the drawer on a blank row | creates a row on first save | committee, organiser | n/a |
| Cluster filter | list | Define clusters with card counts; "All" | filters rows to sources whose "Where it is used" touches that cluster | committee | "No clusters yet. Clusters come from the wall." |
| Technical areas strip | list of chips | one chip per system or team, see Screen B | opens the chip drawer | committee | "No systems or teams named yet. Add one, or Lens will propose them from the systems list." |
| Sources table | list | one row per source: Source name, System, Format, Arrival, Source owner, Data owner, Business owner, Personal data class, State pill (Drafted by Lens, Edited, Confirmed by source owner, Needs source owner) | row click opens drawer | per row rule below | Row-less empty state above |
| State pill | chip | Mark of the weakest cell: `guessed`, `stated`, `unknown` (provenance cells from `m2_baseline/domain/provenance.py`) | click filters to that state | committee | n/a |
| Row owner cells (three) | field | three separate cells, each with a name and a mark; blank cell reads "Not named yet" in the owner's own colour, never merged | click opens a people picker (people of the intent, then the profile people list) | committee edits; the named person confirms | "Not named yet" |
| Drawer: Source name | field | name | edit saves; the Source ID stays | committee | required, error "A source needs a name." |
| Drawer: System | field | the profile system (`systems.<id>.name`) this source sits in, from a picker of the systems list plus "Not in the list" | change sets the chip link | committee | "Not named yet" |
| Drawer: Format | field (choice) | File, Database, Screen, Person, plus Document, Email, Portal or API read from the catalogue `SourceType` list | change saves to column C and the extras `format` | committee | "Not named yet" |
| Drawer: Arrival, how often | field (choice) | `Frequency` list (catalogue column L) | saves column L | committee, source owner | "Not named yet" |
| Drawer: Arrival, how it lands | field (text plus choice) | the questionnaire `connection` words (I download it, Email forward, and so on) and free text "lands at" (column E) | saves columns E and G | committee, source owner | "Not named yet" |
| Drawer: Arrival, expected time | field | column M "Expected arrival time or SLA" | saves | source owner | "Not named yet" |
| Drawer: Fields known so far | list | fields from catalogue `fields` tab for this source (name, meaning, class); count "12 fields, 3 with no meaning" | **Add a field** opens the technical tab of 30; row opens that field | committee | "No fields known yet. Lens lists them when a file or definition names them." |
| Drawer: Personal data class | field (choice) | `PersonalClass` list; per source the answer Yes, No, Not sure (column J) | change by the governance lead; others propose, the cell shows "Proposed by Katie, waiting for Grace" | propose: committee; set: governance lead | "Not sure", shown as undecided, never as No |
| Drawer: Who may see | field (names list) | names or roles (column K) | governance lead and data owner set | those two; others read | "Everyone in the company" is never the default; empty reads "Not set. Treated as closed until set." |
| Drawer: Where it is used | list | measures (catalogue `Feeds KPI`), process steps, clusters, resolved from records; each links | click opens that measure or step | committee | "Not used by any measure yet." and North asks whether the source is needed (m3 "Not needed for any measure") |
| Drawer: Known problems | list of notes | person notes, each with author and date: "Arrives 2 days late at month end" | **Add a problem** | committee, source owner | "No problems recorded. That is not the same as none: ask the source owner." |
| **Confirm this source** | button | visible only to the named source owner; label "Confirm this is how <name> works" | writes `confirmed_by`, `date confirmed` (columns R, S), mark `stated` on the owner's cells | the source owner | hidden for others; they see "Waiting for Harvey" |
| **Not mine, it is...** | button | beside Confirm | reassigns the source owner cell to a named person, sends them a Pulse line | the named source owner | n/a |
| **Remove from map** | button | needs a reason; row moves to "Not a source" list, never deleted | `PUT` sets `left_out: {by, reason, at}` | organiser | n/a |

Row visibility: a source with personal "Yes" or "Restricted" shows to the people in "Who may see", the organiser, sponsor and company admin; everyone else sees a row "A restricted source" with no owner, system or fields (`m3_connect/domain/sources.py` `RESTRICTED_SOURCE`, `sh_platform/profile/view.py` `sees_source`). Counts include it as a separate line "1 restricted source".

### Screen B: Technical areas chips

Part of Screen A (strip above the table); opens a drawer. Layout at 1280: strip of chips, drawer to the right. At 390: chips wrap into two rows, drawer is full screen.

A technical area is a **system** (Portfolio system, Custodian portal, Excel workbook) or a **team** (Operations, Finance IT, the outsourced administrator). It carries the names of the people who could say how it works.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| System chip | chip | system name from profile `systems.<id>.name`, a count of sources in it ("3"), a dot for confirmed or not | opens the chip drawer | committee | strip empty state above |
| Team chip | chip | team name from profile `people.<id>.team` (distinct values) with count of people | opens the chip drawer | committee | same |
| **Add an area** | button | small field: name, kind (system or team) | creates a chip marked stated | committee | n/a |
| Drawer: Sources here | list | sources linked to the chip | row click selects it in the table | committee | "No source linked yet." |
| Drawer: People who could say | list of people with a mark | names from profile people with that team, interviews that mentioned the system, and added names | **Add a person** picker; each person gets a Pulse line "You were named as someone who could say how Portfolio system works" (an invite to confirm, never an assignment) | committee | "Nobody named yet. This area cannot be asked about." |
| Drawer: Linked areas | chips | other areas the same sources touch (a source in Portfolio system fed by Custodian portal) | click opens that chip | committee | "None named." |
| **Not an area** | button | with reason | moves the chip to a hidden list, restorable | organiser | n/a |

Restricted systems: a chip for a system the viewer may not see reads "A restricted area" (profile `SHUT_SOURCE`) with a count only.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet opens the Initiative at `/centre/intent/<id>` and closes Think unfiltered (or arrives from the Pulse line). North moves the Initiative to Define and creates the data sources map for the baseline.
2. Between steps (Lens, unattended): reads profile `systems` (name, kind, owner, lands, frequency, tables, personal_data, may_see), interview answers (Q3 "how do you track it today", source rows in `m2_baseline` answers `sources`), documents in context shelves, and the v1 catalogue `sources` rows if any. Drafts one source per distinct system or file, marked `guessed`, and one chip per system and team. It proposes the three owners separately: source owner from the profile `systems.<id>.owner` and interview "who sends it"; data owner from the RACI; business owner from the process map step owner. A cell it cannot fill stays "Not named yet".
3. North posts a Pulse line to Janet: "Lens drafted 9 sources and 7 areas. Review before the Define session."
4. Janet opens the tab, reads the table, fixes names, adds a missing source, clicks **Add an area** for the outsourced administrator.
5. Between steps (North): for each source with a named source owner who has not confirmed, writes a Pulse `request` line to that person with the one question "Is this how it works?" The wait before a reminder is an Open question.
6. In the session the committee works cluster by cluster: opens the source drawer, corrects Format and Arrival, adds Known problems, names who could say for each chip.
7. Harvey opens his Pulse line, sees only his rows, corrects Arrival ("lands by 09:00 on working day 2"), clicks **Confirm this is how Portfolio system works**. Or clicks **Not mine, it is Aaron**.
8. Grace sets Personal data class and Who may see on each source. A source with personal "Yes" and an empty Who may see blocks the build-ready check (rule below).
9. Between steps (Lens): from fields named in documents and definitions, drafts catalogue `tables` and `fields` rows for each source (names and types only, no values); the drawer's "Fields known so far" fills in.
10. Janet clicks **Done with data sources** (button in the top bar) and leaves the tab for the next Define tab or the intent page. North checks the counts, writes the closure line for the substage, and hands the map to 30 and 33. Nothing is signed here; the charter signature stays with the sponsor.

## States and transitions (table: state, who moves it, to what, what is written)

Per source row (one state, derived from cell marks and `confirmed_by`, not a new column):

| State | Who moves it | To what | What is written |
|---|---|---|---|
| `drafted` (all cells guessed) | Lens (draft route) | `edited` | catalogue row, marks `guessed`, `by: Lens`, `from` names the document or profile cell |
| `drafted` or `edited` | committee member edits a cell | `edited` | cell value, mark `stated`, `by`, `at` (provenance cell, `sh_platform/profile/store.py` `cell()`) |
| `edited` | the named source owner (**Confirm**) | `confirmed` | catalogue columns R `Confirmed by`, S `Date confirmed`; extras `confirmed_by` |
| `edited` | the named source owner (**Not mine, it is...**) | `edited`, source owner changed | source owner cell, Pulse line to the new person, history entry |
| any | organiser (**Remove from map**, reason) | `left_out` | extras `left_out` with by, reason, at; row kept |
| `confirmed` | any committee member edits a confirmed cell | `edited` | cell changes, `confirmed_by` cleared, history keeps who confirmed before; source owner gets a line "Your source changed" |
| `left_out` | organiser (**Restore**) | `edited` | `left_out` cleared, history entry |

Substage: `data_sources` entry inside the Initiative `stages` list (spec 01): `waiting` to `open` (North, when Define opens) to `closed` (organiser, **Done with data sources**; North writes `closed_at`). Closing is allowed with unconfirmed sources; the build-ready check (33) reports them. A confirmed source is read only except through the edit rule above.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Mark | Read or written by |
|---|---|---|---|
| `intents/m2_baseline/<baseline_id>/catalogue.json`, `sources` tab (`modules/m2_baseline/store/catalogue.py` `_raw`, `read_catalogue`, `add_row`, `edit_row`, `propose_rows`) | Source ID, Source name, Source type (format), Structured or unstructured, Where it lands or lives, Data owner, Connection method, Contains personal data?, Who may see it, How often it arrives, Expected arrival time or SLA, Availability, Next step or project, How sure are we, Confirmed by, Date confirmed, Notes | Existing | read, and written through the existing routes `POST/PUT /baselines/{id}/catalogue/sources/rows[/{row_id}]` |
| same file, `tables` and `fields` tabs | Source ID, Item ID, Field name as in the source, Business meaning, Data type, Personal data class, Feeds KPI | Existing | read for "Fields known so far"; written by 30 |
| `intents/m2_baseline/<baseline_id>/answers` (`modules/m2_baseline/store/answers.py` `read_answers`, `questionnaire.source_rows`) | `sources[]` rows: name, kind, lands, owner, connection, tables, fields, read_out, personal, structure, frequency, sla | Existing | read by Lens as drafting input only |
| profile (`sh_platform/profile/reader.py` L109-L124 `_systems`; `store.py`), read per viewer with `sh_platform/profile/view.py` `read` | `systems.<id>.name`, kind, owner, lands, frequency, tables, personal_data, may_see, restricted; `people.<id>.team`, role | Existing | read; the chips link to these cells; never written by this feature except through `profile.record(...)` when a person adds a system not yet in the list (mark `stated`) |
| `intents/m2_baseline/<baseline_id>/data_sources.json` | `{"version": 1, "sources": {"<Source ID>": {"source_owner": cell, "business_owner": cell, "format_note": cell, "arrival_how": cell, "used_in": {"clusters": [], "steps": []}, "known_problems": [{"id", "text", "by", "at"}], "system_ref": "systems.<id>"\|null, "left_out": {"by", "reason", "at"}\|null, "history": [{"by", "at", "what"}]}}, "areas": [{"id", "kind": "system"\|"team", "name", "profile_ref": str\|null, "source_ids": [], "who_can_say": [{"name", "mark"}], "linked": [area id], "hidden": null\|{"by", "reason"}}]}`. Each `cell` is a provenance value | New | read and written only by the new routes below, through `sh_platform/jsonfile.py` (`lock_for`, `read_json_strict`, `write_json_atomic`) |
| `modules/m3_connect` `sources.json` (`domain/sources.py` L222-L240 `read`, `save_scored`) | `id`, `zone`, impact, readiness, measures fed | Existing | read by this tab only for the line "Moment of truth: zone p1" after Build starts; never written here |
| `modules/m3_connect` intake plan (`domain/intake.py` L85-L122 `source_plan`) | `source_id`, `source_name`, `owner`, tables, columns | Existing | reshaped: `owner` becomes source owner first (see Reuse check) |
| `intents/<id>/intent.json` | the fields in the next section | New fields | written by North and the routes |

New routes, spelled under `/api/intents/{id}/...` as the brief requires (`{id}` resolves to the baseline through `refs.baseline_ids[0]`). The code sits in `modules/m2_baseline/api/data_sources.py` because the kernel cannot import a module; how the mount works is an Open question. Manifest and permissions declared as default deny. Existing catalogue routes (`modules/m2_baseline/api/catalogue.py`) stay as they are:

| Route | Does | Who |
|---|---|---|
| `GET /api/intents/{id}/data-sources` | merged view at the viewer's tier: catalogue sources rows plus extras plus areas, restricted rows masked | committee, source owner (own rows), admin (existence only) |
| `POST /api/intents/{id}/data-sources` | add a source: writes a catalogue `sources` row through `add_row`, then the extras entry | committee |
| `PUT /api/intents/{id}/data-sources/{source_id}` | edit cells; class and who-may-see refused unless governance lead or data owner | committee, governance lead |
| `POST /api/intents/{id}/data-sources/{source_id}/confirm` and `/reassign` | confirm or hand over the source owner cell; refused unless the viewer is that named person | the source owner |
| `POST /api/intents/{id}/data-sources/{source_id}/problems` | add a known problem | committee, source owner |
| `POST /api/intents/{id}/data-sources/areas`, `PUT .../areas/{area_id}` | add, edit, hide a chip; add or remove a person who could say | committee |
| `POST /api/intents/{id}/data-sources/draft` | Lens draft (rows and chips, guessed) | organiser, sponsor, North |
| `POST /api/intents/{id}/data-sources/done` | closes the substage; returns the counts | organiser |

## Fields this feature adds to the intent record

Initiative only; no existing field renamed.

```
data_sources: {
  baseline_id,                 # same as refs.baseline_ids[0], repeated only as the key the screen reads; not a copy of any content
  state: not_started|drafted|in_review|done,
  drafted_at, drafted_by: "Lens",
  done_by, done_at
}
```

Everything else (rows, owners, chips) stays in the baseline folder; the intent points at it by reference (`refs.baseline_ids`) and never copies. Counters come from records at read time.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** opens the substage when Define opens, asks the missing question ("Who runs Custodian portal?"), keeps the clock (spec 07), and writes the one-line closure draft when the organiser clicks **Done with data sources**. It never fills an owner cell itself. North flags, as a `decision` line to the organiser, any source with no source owner once the wait has passed (the wait is an Open question), and proposes: name one, leave out with reason, or carry as a known gap into 33. A named person picks.
- **Lens** drafts rows, chips, the three owners (each separately, each marked guessed), fields known, personal data class suggestions (from `m2_baseline/contracts/governance.yaml` field-name words and profile `personal_data`), and arrival from profile `frequency` and `lands`. It never sets Personal data class or Who may see as final: those wait for the governance lead. It never overwrites a person's cell (rule 7: a draft never replaces a human edit; `catalogue.py` `_source_touched` logic). It raises at most three open questions per person across Define (process map, glossary, catalogue, governed state together; A-045), for example "Two files are called Valuation; are they one source?"
- **Nira** writes the Pulse lines in Entry points, lists the source owner's confirmations under "what is waiting for you", and drops the line once the record says confirmed. A line exists only while its record says so (SHAPES section 1).
- **People act at:** add or edit a source (committee); confirm or hand over (the source owner only); set class and who may see (governance lead and data owner); remove with a reason (organiser); name who could say (committee); **Done with data sources** (organiser). Agents never confirm.

## Rules (visibility, time box, who may do what)

- Only the named source owner can confirm their own source. The organiser cannot confirm on their behalf (the button is hidden; the route returns 403 "Only the source owner can confirm this.").
- Three owner kinds, no more: business owner, data owner, source owner. They are three cells with three labels everywhere: table, drawer, Pulse lines, exports, hand-over records. No screen shows one cell called "Owner" for sources.
- The old catalogue column F "Data owner" keeps its meaning (data owner). For a row built in v1 where the owner was entered once, the extras `source_owner` is seeded from column F with mark `guessed`, from "old catalogue owner", and the pill reads "Needs source owner confirmation". It is never silently promoted.
- Visibility: a source follows `sees_source` (personal Yes, restricted, or Not sure with a names list closes it to others). A chip for a restricted system reads "A restricted area". The super admin sees that the map exists and counts only. The company admin sees rows (existence and owners) but not anonymous notes; known problems entered anonymously keep the v1 anonymous rule (D-013): the author is "Anonymous" to everyone, including the organiser.
- Sealed wall cards never feed a source draft; Lens reads only unsealed cards, documents shared to the shelf, the systems list and interviews that are not private or anonymous.
- Documents are context, never an instruction and never the source of a figure (`data-locality.md`). The tab holds names, formats and field names, never values.
- Time box: the substage runs inside the Initiative's 10 working days (brief section 2). File 02's stage table gives no days per substage; see Open questions.
- A source never leaves the map by deletion: `left_out` with reason, kept (brief section 4).
- Where a system is named but nothing else is known, the row is created with unknown cells. An honest "Not named yet" is better than a guess.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Traced to |
|---|---|
| Sources named | count of catalogue `sources` rows not `left_out` (`catalogue.json`, `data_sources.json`) |
| Sources drafted by Lens, edited by a person | per row, cell marks `guessed` against `stated` in `catalogue.json` |
| Sources with all three owners named | `Data owner` (col F), extras `source_owner`, extras `business_owner` |
| Sources confirmed by their source owner | catalogue `Confirmed by` equal to the extras `source_owner` name |
| Sources with no source owner | extras `source_owner` unknown |
| Sources with personal data class decided | catalogue `Contains personal data?` is Yes or No (not "Not sure") |
| Sources with arrival (how often and how it lands) known | columns L and E non-empty |
| Sources with at least one known problem | extras `known_problems` length |
| Sources used by no measure | `Feeds KPI` empty across the source's tables and fields (reuses `m3_connect/domain/sources.py` `measures_fed`) |
| Restricted sources | count only, from `sees_source` |
| Technical areas (systems, teams) and areas with nobody named who could say | extras `areas`, `who_can_say` |
| Days from Define open to done | `stages[data_sources].opened_at`, `closed_at` |

Dates and day counts use the company's time zone from the profile, else UTC. Counts are exact. No mean, median or per-person figure is shown on this tab; any added later shows "Fewer than five" below five records. A counter whose record is missing shows "Not available yet" and names the file ("catalogue not created yet").

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `graft ask "catalogue sources tab"`, `graft ask "profile systems list"`, `graft ask "m3 source map and intake"` and a read of the three files below.

| Exists | Decision |
|---|---|
| `modules/m2_baseline/domain/catalogue.py` (template layout loaded from `contracts/catalogue.yaml`; sources columns A to U; `TABS`, `required`, `options`) | **Reused as the record.** The Data sources tab is a view and an editor over its `sources` tab; no new table. Columns not changed here: a Source owner and Business owner column would belong in `catalogue.yaml`, owned by 30 (see Open questions); until then they sit in the extras file |
| `modules/m2_baseline/store/catalogue.py` L107-L202 (`read_catalogue`, `view`, `add_row`, `propose_rows`, `edit_row`, `_may_open`) | **Reused as is** for all row writes and for the viewer guard |
| `modules/m2_baseline/domain/questionnaire.py` L212-L226 `source_rows`; `contracts/questionnaire.yaml` L77-L126 (`sources` rows: name, kind, lands, owner, connection, tables, fields, read_out, personal, structure, frequency, sla) | **Reused as Lens input.** Its `owner` ("Who owns it") is the mixed field; it seeds the source owner cell as guessed |
| `modules/m2_baseline/domain/provenance.py` (`prov`, `unknown`) and `sh_platform/profile/store.py` `cell`, `record` | **Reused** for every cell and the mark rule |
| `modules/m2_baseline/domain/handoff.py` L13-L100 (`build_outcome`, `for_viewer`, `WITHHELD`) | **Reused**: the hand-over to 30 and 33 reads sources through it; withheld names stay withheld |
| `sh_platform/profile/reader.py` L109-L124 `_systems`, L313-L320 (systems extraction from documents); `view.py` L86-L147 (`sees_source`, `read`, `SHUT_SOURCE`) | **Reused** for the chips: systems and teams come from the profile; restricted systems stay shut per viewer |
| `modules/m3_connect/domain/sources.py` L1-L30, L57-L75 (`measures_fed`), L222-L240 (`sources.json`, `RESTRICTED_SOURCE`) | **Reused** for "Where it is used" and the masked label; not written here |
| `modules/m3_connect/domain/intake.py` L85-L122 `source_plan` (its `owner` is column F "Data owner") and `api/intake.py` L238-L276 (requests addressed to that owner) | **Reshaped**: the person asked to upload a file is the source owner, falling back to the data owner marked "data owner, no source owner named". This is the v1 mix fixed |
| `ui/src/modules/m2_baseline/catalogue/CatalogueTab.tsx`, `CatalogueScreen.tsx` | **Reused**: the table component, provenance pills and drawer pattern are copied into the Data sources tab; the tab shows the sources tab with an owners-first column set |
| `ui/src/modules/m1_intent/define/DefineScreen.tsx`, `LensPanel.tsx`, `define.css` | **Reshaped**: the tab strip is added; the Data sources tab is a new child component beside the Lens panel |
| `ui/src/modules/m2_baseline/process_map/*` and `domain/process_map.py` `from_technical` | **Not used here**; the process map is file 27 and links to a source by Source ID |
| Interview engine (`sh_platform/interview`), context shelves (`sh_platform/context_docs`) | **Reused** as Lens input only |

New: the extras file `data_sources.json`, the three-owner labelling, the technical-area chips, the confirm and hand-over routes, the substage `data_sources`, the Pulse lines.

## Not in this feature

- Connecting to a system, reading rows or testing a file: that is Moment of truth and Build (`m3_connect` intake, scan, trial).
- Field-level definitions, calculations and the catalogue `fields` and `tables` editing: spec 30.
- The process map and swimlanes: separate spec; this feature only links a source to a step.
- Sign-off of the whole map: no signature here; the sponsor signs the charter, and 33 reports readiness.
- Access rules and feeds enforcement: module 4 reads Who may see; this feature only records it.
- Changing the catalogue template contract file.

## Open questions

1. Add "Source owner" and "Business owner" columns to `modules/m2_baseline/contracts/catalogue.yaml` `sources` tab (owned by spec 30), or keep them in the extras file? This spec keeps them in the extras file to avoid a contract change it does not own.
2. Which numbers does the build-ready check (33) require per source before it passes: all three owners, or only source owner and arrival? This spec lists the inputs and names no threshold.
3. Day split inside the 10-working-day Initiative: this spec suggests data sources open on day 3 and done by day 6. File 02's stage table gives no days per substage. Not decided.
4. How many working days before North reminds a source owner who has not confirmed, and before it flags a source with no source owner? Neither wait is set.
5. Where the source owner has no account, does confirm go by a one-time link (like `m3_connect` intake links) or must they be a user? Not decided.
6. Do teams in the chip strip come only from profile `people.<id>.team` or also from the systems list `owner` column when that holds a team name?
7. Should a source feeding a Future-shelf cluster stay on the map? This spec keeps it, marked "Parked cluster".
8. Routes: the new routes are spelled `/api/intents/{id}/data-sources/...` per the brief, but the code lives in a module and the kernel cannot import it. Mount through a kernel route that calls a module hook, or declare them under `/api/modules/m2_baseline/`? Not decided.
9. The v1 route `/centre/intent/define/:sessionId` needs a redirect or alias plan to the new spelling. Not decided.
