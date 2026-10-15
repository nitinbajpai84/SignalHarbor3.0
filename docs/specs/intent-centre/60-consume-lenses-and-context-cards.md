# 60. Consume by lens, and context cards

Part of: Intent Centre v2 (the return cycle, `docs/plan/CYCLE-PLAN.md` section 2). Depends on: 05 (areas), 13 (Pulse lines), 55 (data knowledge map), 56 (data-backed opportunities), 57 (opportunity radar and the hypothesis record), 58 (initiative outcomes and Proving), 59 (Build centre agent chain, the Architect). Feeds: 19 (centre measures), 56 and 57 (opportunities raised from a what-if), 58 (Proving lines per lens), Ask Lens (`modules/m2_baseline/api/lens_chat.py`).

## Purpose (three sentences)

The Consume centre today has three rooms (Market forces, What-if, Feeds) that each answer one kind of question; a person who cares about cost or risk has to visit all three and join the answers in their head. This feature regroups what Consume already shows under four lenses (new revenue, process cost, retention, risk): for each lens, what the market is doing (outside material, labelled), what our data says (feeds and range breaks), what we are building (Initiatives in Build and Proving) and what we should consider next (radar opportunities, 57), with a what-if that can be turned into an opportunity. Every gold table also carries a context card (business meaning, measures served, lineage, owner, quality rules, last change and why, the Initiative that created or changed it), drafted by the Architect and Lens, confirmed by the data owner, shown on the measure page and read by Ask Lens.

## Who uses it and when (role, moment, trigger)

| Role (Ardmore demo) | Moment | Trigger |
|---|---|---|
| Daniel, sponsor | Weekly, before the investment committee | Opens Consume, picks the Risk lens, reads what moved and what is being built |
| Harvey, owner (operations, data owner of the custody marts) | After a blueprint is signed or a mart changes | Pulse line "A context card for gold.k12 waits for you"; confirms or corrects it on the measure page |
| Katie, analyst | Any time she tests an idea | Runs a what-if under the Process cost lens, presses "Turn this into an opportunity" |
| Janet, organiser | Starting a new Initiative | Reads the Process cost lens to see what is already being built before she opens one |
| Aaron, participant | Any time | Opens Consume with "My line of work" on; sees only measures and briefs his viewer rule allows |
| Grace, approver | Before signing a release | Reads the context card of each gold table the release touches |
| Super admin | Never | Consume holds company figures; no route (05, ruling 5) |

## Entry points (every route, link, Pulse line, button that leads here)

- Consume home `/centre/consume` (existing, `ui/src/App.tsx` L144-L149): new row of four lens tiles above the three rooms.
- Lens page `/centre/consume/lens/<lens>` where `<lens>` is `new-revenue`, `process-cost`, `retention` or `risk` (New; open question 1).
- Feeds card (existing `FeedCard`, `ui/src/pages/FeedsPage.tsx` L28-L45): new lens chip under the owner line, links to the lens page.
- Measure page `/centre/consume/feeds/<code>` (existing): new side card "Context card" and lens chip in the actions.
- What-if result (existing, `ui/src/pages/WhatIfPage.tsx` L259-L285): new button "Turn this into an opportunity".
- Pulse line (Nira, kind `decision`, to the data owner only): "A context card for <table> waits for you." href `/centre/consume/feeds/<code>?card=confirm`.
- Pulse line (Nira, kind `decision`, to the data owner only): "<table> changed since you confirmed its card. Check it." Same href.
- Pulse line (Nira, kind `inform`, to people whose line of work a lens touches, open question 9): "Risk: two measures left their usual range this month." href `/centre/consume/lens/risk`.
- Radar opportunity row (57) "See its lens" to `/centre/consume/lens/<lens>`.
- API (New, open question 2): `GET /api/company/consume/lenses`, `GET /api/company/consume/lenses/{lens}`, `GET /api/company/consume/cards/{table}`, `POST /api/company/consume/cards/{table}/confirm`, `POST .../edit`, `POST .../dispute`, `POST /api/company/consume/lenses/assign`. Existing and reused: `GET /api/company/feeds`, `GET /api/company/feeds/{code}`, `GET /api/company/market`, `POST /api/company/whatif`, `POST /api/company/whatif/keep`, `POST /api/intents/opportunities` (56).

## Screens, element by element

### Screen A. Consume home, re-staged by lens

Route: `/centre/consume` (existing, `ui/src/pages/ConsumeCentre.tsx`).

Layout at 1280: page frame as today; a new section "Lenses" with four `RoomTile`s in one row (the existing auto-fit grid, L42); under it the existing section "Rooms" (Market forces, What-if, Feeds), retitled "Tools", unchanged. Layout at 390: the auto-fit grid stacks the lens tiles to one column, then the tools; the chip row wraps.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Section title "Lenses" | heading | Fixed | None | Everyone the consume `RoleGate` lets in | Always shown |
| Chip "My line of work" / "Everything" | chip pair | Which measures the tiles count | Re-reads `GET /api/company/consume/lenses?mine=1` or without | As above | "My line of work" disabled with hint "No area or measure is linked to you yet" when the viewer has none |
| Lens tile "New revenue", "Process cost", "Retention", "Risk" | panel (`RoomTile`) | Name; one line of what the lens asks; counts: measures, outside their usual range, briefs, building, proving, to consider | "Open <lens>" to `/centre/consume/lens/<lens>` | As above; counts only over measures the viewer may see | Tile dim, count line "Not available yet: no measure assigned to this lens" |
| Count "n outside their usual range" | text on tile | Feeds with `may_see` and `range_break` among the lens measures (`feeds.py` L50-L69, rule `range.py` L34) | None | As above | Omitted when 0 |
| Footnote | text | "A lens groups what is already here. It adds no figure of its own." | None | As above | Always shown |
| Section "Tools" | panel | Existing three room tiles (L25-L32) | Existing | Existing | Existing |

### Screen B. Lens page

Route: `/centre/consume/lens/<lens>` (New).

Layout at 1280: page frame, crumbs "Consume centre / <Lens>"; actions: chip pair "My line of work" / "Everything"; main column with four strips in this order: "What the market is doing", "What our data says", "What we are building", "What we should consider next"; aside: "Measures in this lens" and "How this lens is drawn". Layout at 390: one column; the aside moves under the fourth strip; each strip shows three items then "Show all (n)".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Title | heading | Lens name and its question, e.g. "Risk: what could hurt the family's capital" | None | Consume roles | Always shown |
| Chip "My line of work" / "Everything" | chip pair | Filter by line of work (Rules) | Re-reads the lens route with `mine=1` | As above | As Screen A |
| Strip "What the market is doing" | list of `SideCard` (copied from `MarketPage.tsx` L137-L154) | Briefs whose `measures` or `measure_moves` meet the lens measures; pill "Outside material"; source footnote | Measure chip opens the measure page; "All briefs" opens `/centre/consume/market` | As above | "No outside material touches this lens yet." |
| Strip "What our data says" | list of `FeedCard` (reused) | Lens measures, range breaks first, latest value, sparkline, owner | Card opens the measure page | As above; restricted measures show "Restricted: ask <owner>" | "No measure in this lens has a value yet. Not available yet: no gold table holds one." |
| Line "n of m outside their usual range" | text | Count from the feeds route | None | As above | "All inside the usual range" |
| Strip "What we are building" | list | Initiatives of this lens with `links.build` set or in Proving (58): title, stage chip "In Build" or "Proving", organiser, measure it aims to move, latest verdict from 58 if any | Opens `/centre/intent/<id>` | People who may see the intent exists (05); title only for others in its areas | "Nothing is being built for this lens." |
| Verdict chip | chip | 58's verdict in words: working, partly, not, too early | None | As above | "No report yet" |
| Strip "What we should consider next" | list | Radar opportunities (57) whose hypothesis `lens` is this lens and state is noticed, under review or proposed: title, state chip, North's one line | Opens `/centre/intent/backlog?opportunity=<id>` | 56's opportunity viewers, filtered by area | "Nothing suggested for this lens yet." |
| Button "Try a what-if" | button | Fixed | `/centre/consume/what-if?lens=<lens>`; the driver list puts lens measures first | Consume roles | Always shown |
| Aside "Measures in this lens" | list | Each measure with "Lens draft" or "Confirmed by <name>" | Measure opens its page; "Move to another lens" opens a select | Business owner of the measure may move it; others read | "No measure assigned yet. Lens drafts the list once a baseline exists." |
| Aside "How this lens is drawn" | panel | "Measures come from the lens list. Briefs are outside material. Initiatives and opportunities carry their own lens." | None | Everyone | Always shown |

### Screen C. Measure page additions (context card and lens)

Route: `/centre/consume/feeds/<code>` (existing, `ui/src/pages/MeasurePage.tsx`); `?card=confirm` opens the card in confirm mode (ruling 18 style query key).

Layout at 1280: the aside (L189-L207) gains "Context card" as its first side card, above "Definition"; the actions gain a lens chip beside the range pill. Layout at 390: the aside already stacks below the main column; the context card moves to the top of the page, collapsed to its title and state, tap to open.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Lens chip | chip | "Risk" etc., with "Lens draft" when not confirmed | Opens the lens page | Everyone who may open the page | "No lens yet" |
| Side card "Context card" | panel | Title "gold.<table>", state pill: Draft, Confirmed, Changed since confirmed, Disputed | None | Everyone who may open the page; restricted measures show only table name and data owner (existing restricted branch L168-L177) | "No context card yet. The Architect drafts one when the blueprint that builds this table is signed." |
| Row "What it means" | text | Business meaning in plain words | None | As above | "Not available yet: no signed definition" |
| Row "Measures it serves" | list | Measure codes and names from blueprint `lineage[].mart` (SHAPES 2) | Opens each measure page | As above; measures the viewer may not see read "A restricted measure" | "Serves no governed measure yet" |
| Row "Where it comes from" | list | Lineage from the map (55): source, system, fields, pipeline | "Show lineage" to `/centre/intent/graph?view=lineage&focus=mart:<table>` | As above; restricted systems per `read.py` | "Not on the map yet" |
| Row "Owner" | text | Data owner from the governed owners cell (`modules/m2_baseline/domain/governed.py` L17-L19, role `data`) | Opens the person node | As above | "Not available yet: no data owner named" |
| Row "Quality rules" | list | Blueprint `rules[]` for the measures served: rule, severity, from (scan or trial); last run result from `warehouse/runs.json` `rules[]` | None | As above | "No quality rule set yet" |
| Row "Last change and why" | text | Newest `graph/versions.json` row for the mart node: what, by, at, and the why the card holds | "See all changes" opens the node page versions | As above | "No change recorded since it was built" |
| Row "Made or changed by" | link | The Initiative behind the newest version (`ref` to an intent through 55's `updates.json`), with "created" or "changed" | Opens `/centre/intent/<id>` | As above; an intent the viewer may not see reads "An Initiative you cannot open" | "Not available yet: built before Initiatives were recorded" |
| Line "Drafted by" | agent line | "Drafted by the Architect and Lens on <date>. Confirmed by <name> on <date>." | None | As above | None |
| Button "Confirm this card" | button | Fixed | `POST .../cards/{table}/confirm`; state Confirmed | The data owner of the table only | Hidden |
| Button "Correct a line" | button | Fixed | Opens the line as a field; save writes `POST .../edit` with the line, new text and required why; state stays Draft until confirmed | The data owner only | Hidden |
| Button "This is wrong" | button | Fixed | `POST .../dispute` with required reason; state Disputed; North asks the Architect to redraft | The data owner only | Hidden |
| Link "Suggest a change" | link | Fixed | Existing node page comment flow (SHAPES 10) on `mart:<table>` | Everyone who may open the page | Always shown |
| Side card "Ask Lens" (existing L111-L128, L206) | panel | Unchanged; answers now read the confirmed card (Agent behaviour) | Existing | Existing | Existing |

### Screen D. What-if, "Turn this into an opportunity"

Route: `/centre/consume/what-if` (existing); `?lens=<lens>` orders lens measures first in the driver list (L246).

Layout at 1280: the button sits under "Keep this scenario" in the "What moves" card (L277-L282). Layout at 390: full-width button under the keep button.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Button "Turn this into an opportunity" | button | Fixed | Keeps the scenario (existing `POST /api/company/whatif/keep`), then opens the raise sheet of 56 with a hypothesis (57) prefilled from the result | `owner`, `analyst` (56's raise roles, open question 6) | Disabled with "Pick a driver whose path reaches a measure" when `moved` is empty |
| Raise sheet prefill: belief | field | "If <driver> moves <pct>%, <measure> moves from <value> to <moved_value>" | Editable | As above | None |
| Prefill: lens | field (select) | The lens of the first moved measure | Editable | As above | "Pick a lens" |
| Prefill: evidence line | list | One line, kind `whatif`, ref the kept scenario id, basis text from the result | Read only | As above | None |
| Prefill: baseline and target | field | Baseline: `latest.value` and period (traced to the feeds route); target blank, with hint "The what-if is a straight-line estimate, not a target" | Target is typed by the person | As above | "Not available yet: the measure has no value" |
| Button "Raise it" | button | Fixed (56) | `POST /api/intents/opportunities`; the Watcher, Lens and North then act as 56 and 57 say | As above | Disabled until belief and lens are set |
| Button "Cancel" | button | Fixed | Closes the sheet; the kept scenario stays | As above | Always shown |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Daniel signs the blueprint for the K12 build (59). Between that signature and anyone's next step, the Architect drafts the technical lines of the `gold.k12` card (measures served, lineage from the map, quality rules, last change, the Initiative from the version `ref`); Lens drafts "What it means" from the signed K12 definition and assigns K12 to a lens as a draft. Nira writes the decision line to Harvey, the data owner.
2. Harvey opens Pulse, reads "A context card for gold.k12 waits for you", and lands on the K12 measure page with the card in confirm mode.
3. Harvey reads the card. He presses "Correct a line" on "Last change and why", types "Stale now means one quarter without a final statement" and saves. He presses "Confirm this card". The card is Confirmed.
4. Daniel opens `/centre/consume`. The Risk tile reads "5 measures, 1 outside its usual range, 2 briefs, 1 building, 1 to consider". He clicks "Open Risk".
5. On the Risk page he reads the private-market calls brief (outside material), sees K12 outside its usual range, the Initiative "Valuation evidence chase" in Proving with verdict "too early", and an opportunity on late custodian files. He clicks K12.
6. On the K12 page he asks Lens "why did this rise in September". Between his question and the answer, Lens reads the confirmed card, the definition and the figures he may see, and answers with the card's last change and the Initiative that made it. Daniel leaves.
7. Katie opens What-if with `?lens=process-cost`, picks the lever "Document intake and missing-evidence follow-up", sets minus 20 percent, and sees K03 and K14 move. She presses "Turn this into an opportunity".
8. The scenario is kept; the raise sheet opens prefilled. She edits the belief, leaves the target blank and presses "Raise it". The Watcher and Lens add evidence and North judges, as 56 and 57 say. Katie leaves.
9. A month later the pipeline for `gold.k12` changes and a version row is appended. The card turns "Changed since confirmed"; Nira writes the second decision line to Harvey; the journey repeats from step 2.

## States and transitions (table: state, who moves it, to what, what is written)

| State | Who moves it | To what | What is written |
|---|---|---|---|
| No card | Blueprint signature (59) for a blueprint whose lineage names the table, or the first scan of a gold table with no card | Draft | `consume/cards/<table>.json` with every line `mark: guessed`, `drafted_by`, `drafted_at` |
| Draft | Harvey, data owner, "Confirm this card" | Confirmed | `confirmed_by`, `confirmed_at`, every line `mark: stated` |
| Draft or Confirmed | Data owner, "Correct a line" | Draft (until confirmed) | Line text, `edited_by`, `why`; history row |
| Draft or Confirmed | Data owner, "This is wrong" | Disputed | `dispute: {by, at, reason}`; North line to the Architect |
| Disputed | Architect redraft | Draft | New draft lines; history row keeps the old ones |
| Confirmed | A new `graph/versions.json` row on `mart:<table>` after `confirmed_at` | Changed since confirmed | `stale_since`, `stale_ref` |
| Changed since confirmed | Data owner confirms again | Confirmed | As Draft to Confirmed |
| Measure lens: none | Lens draft | Draft lens | `consume/lenses.json` row `mark: guessed` |
| Draft lens | Business owner of the measure confirms or moves it | Confirmed lens | `lens`, `confirmed_by`, `confirmed_at` |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Read or written | Mark |
|---|---|---|---|
| `consume/cards/<table>.json` (plane, via `sh_platform/jsonfile.py`) | `{table, measures: [code], meaning: LINE, lineage: LINE, owner: LINE, rules: LINE, last_change: LINE, made_by: {intent_id, how: created\|changed}\|null, state: draft\|confirmed\|changed\|disputed, drafted_by: [architect, lens], drafted_at, confirmed_by, confirmed_at, stale_since, stale_ref, dispute, history: [{at, by, action, line, old, new, why}]}`; `LINE = {text, mark: guessed\|stated, from: record ref}` | Written by the Architect, Lens and the three owner routes; read by the measure page and Ask Lens | New |
| `consume/lenses.json` | `{measures: {code: {lens: new_revenue\|process_cost\|retention\|risk, mark: guessed\|stated, from, confirmed_by, confirmed_at}}}` | Written by Lens and the business owner | New |
| `GET /api/company/consume/lenses` and `/{lens}` | `{lenses: [{key, name, question, measures: [code], counts: {measures, outside, briefs, building, proving, consider}}]}`; one lens adds `briefs`, `feeds`, `building`, `consider` lists | Read | New |
| `GET /api/company/feeds` (`sh_platform/consume/feeds.py` L50-L69) | `measures[]` plus new key `lens` | Read | Existing route, new key |
| `GET /api/company/feeds/{code}` (`sh_platform/consume/measure.py` L89-L108) | new key `card` (the card, gated) | Read | Existing route, new key |
| `GET /api/company/market` (`sh_platform/consume/market.py` L115-L140) | `briefs[].measures`, `measure_moves`, `source`, `outside` | Read, filtered by lens measures | Existing |
| `POST /api/company/whatif`, `/keep` (`sh_platform/build/whatif.py` L69-L124) | `driver`, `moved[]`, `basis`, scenario id | Read and written | Existing |
| `build/blueprint.json` (SHAPES 2) | `lineage[]`, `rules[]`, `access[]` | Read for measures served and rules | Existing |
| `warehouse/runs.json` (SHAPES 4) | `rules[]` results | Read for the rule's last result | Existing |
| `graph/company.json`, `graph/versions.json`, `graph/updates.json` (55) | lineage view, mart node versions, update `ref` | Read | Existing; `updates.json` New (55) |
| Governed state `modules/m2_baseline/store/governed.py` (`_read`, `confirm_field` L68) | `owners.value.data`, `owners.value.business`, `affects`, `may_see` | Read | Existing |
| `intents/<id>/intent.json` (01) | `type`, `state`, `links.build`, `areas`, hypothesis `lens` (57), Proving and verdict (58) | Read | Existing; 57 and 58 fields New |
| `intents/opportunities/<id>.json` (56) | state, `touches.measures`, hypothesis `lens` (57) | Read; written only through 56's raise route | New (56) |
| Profile people `people.*.areas` (05) | viewer's areas | Read for line of work | New (05) |

## Fields this feature adds to the intent record

- None. Lenses on Initiatives come from 57's hypothesis; context cards point at intents by `made_by.intent_id` and never write into the intent record.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **The Architect** (Build chain, 59): at each blueprint signature, drafts the technical lines of every card whose table the blueprint's lineage names: measures served, lineage (55's lineage traversal, never free text), quality rules (blueprint `rules[]`), last change (newest version row) and made by (the version `ref` resolved through `updates.json`). Each line carries `from`, the record it was read from. A line with no record reads "Not available yet" and names what is missing. On a dispute it redrafts the disputed lines only.
- **Lens**: drafts "What it means" from the signed definition (`modules/m2_baseline/domain/technical.py` text) and the business glossary; drafts each measure's lens from its definition and the pack's measure tree; answers Ask Lens with the confirmed card lines added to its facts (`lens_facts`, `lens_chat.py` L208-L248, for measures found by `_mentioned` L250). A draft card is quoted as "draft, not yet confirmed by <owner>".
- **North**: on a dispute, writes the line to the Architect and keeps the card in Disputed; in the what-if raise flow, judges the opportunity as 56 and 57 say. North never confirms a card or a lens.
- **Nira**: writes the two decision lines to the data owner and the inform line for a lens (open question 9).
- People act: the data owner confirms, corrects or disputes a card; the business owner confirms or moves a measure's lens; an owner or analyst raises an opportunity from a what-if. No agent confirms, raises or opens an intent.

## Rules (visibility, time box, who may do what)

- A lens adds no figure. Every count on a tile or page is a count over records the viewer may see; every value is the Feeds value for this viewer (`feeds.py` access rule).
- Outside material stays labelled "Outside material" on every lens page and can never become a measure value (existing rule, `MarketPage.tsx` L109-L111).
- A measure sits in exactly one lens (open question 3). Unassigned measures are listed under "Not in a lens yet" on Screen A's footnote count.
- "My line of work" for a viewer is the union of: measures where they are named business, data or process owner; measures whose governed `affects` names one of their profile areas; measures touched by intents they are a participant in. No other signal.
- Only the data owner of the table confirms, corrects or disputes its card. Only the business owner (or the head of data, as `governed.py` `check_confirm` already allows) moves a lens.
- A restricted measure's card shows the table name and data owner only; restricted systems and fields follow 55's viewer rule.
- An Initiative appears under "What we are building" only to people who may see it exists (05); content opens by 05's rules.
- No time box. Cards follow the blueprints and pipelines that change them.
- Means, medians and per-person figures show "Fewer than five" below five records (ruling 8); this feature shows none.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Record | Empty |
|---|---|---|
| Measures in a lens | `consume/lenses.json`, viewer-gated | "Not available yet: no measure assigned" |
| Outside their usual range, per lens | `GET /api/company/feeds` `range_break` with `may_see` | Omitted when 0 |
| Briefs touching a lens | `GET /api/company/market` `briefs[].measures` against lens measures | "No outside material" |
| Initiatives building, proving | `intents/*/intent.json` `links.build`, 58 Proving state | "Nothing is being built" |
| Opportunities to consider | `intents/opportunities/*.json` states noticed, under review, proposed | "Nothing suggested" |
| Gold tables with a card, confirmed, waiting, changed | `consume/cards/*.json` `state` against gold tables in the warehouse (`feeds.py` L72-L89 query) | "No gold table yet" |
| What-ifs turned into opportunities | opportunity evidence lines of kind `whatif` | "None yet" |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: read of `sh_platform/consume/*.py`, `sh_platform/build/whatif.py`, `sh_platform/build/opportunity_watch.py`, the four Consume pages, `ConsumeCentre.tsx`; grep for "context card" and "context_card" (only `CYCLE-PLAN.md` and a temp audit note mention it; nothing built); grep of `packs/family_office/1/kpi_tree.yaml` for a lens tag (none); in the earlier repo (`<earlier repo>`) a grep for "context card", "table card" and lens words next to revenue or retention across py, ts, tsx, js and md found nothing. Its `sh_platform/context/store.py` `lineage(kpi)` is already reshaped by 55 and is used here only through 55's lineage view.

| File and lines | What it is | Use |
|---|---|---|
| `ui/src/pages/ConsumeCentre.tsx` L25-L47 | Three room tiles in an auto-fit grid | Reshaped: four lens tiles in the same grid, rooms kept as "Tools" |
| `ui/src/pages/FeedsPage.tsx` L28-L45, L75-L78 | `FeedCard`, Mine and All chips | Reused unchanged on the lens page; lens chip added; "Mine" logic widened to line of work |
| `ui/src/pages/MeasurePage.tsx` L111-L128, L168-L177, L189-L207 | Ask Lens, restricted branch, aside side cards | Reshaped: one new side card; restricted branch reused for the card |
| `ui/src/pages/MarketPage.tsx` L137-L154 | Brief card with outside pill and measure moves | Copied into the lens page strip |
| `ui/src/pages/WhatIfPage.tsx` L259-L285 | Result card and keep | Reshaped: one new button after keep |
| `sh_platform/consume/feeds.py` L50-L89 | Governed measures, access, marts list | Reused; new `lens` key |
| `sh_platform/consume/measure.py` L89-L108 | Measure page route | Reused; new `card` key |
| `sh_platform/consume/market.py` L115-L140 | Briefs with measure moves | Reused, filtered by lens measures |
| `sh_platform/consume/range.py` L9-L13, L34 | The one range rule | Reused unchanged |
| `sh_platform/build/whatif.py` L69-L124 | What-if run and keep | Reused; the kept scenario is the evidence ref |
| `modules/m2_baseline/domain/governed.py` L17-L19, L33-L41, L106 | Draft cell and person cell, owner roles, confirm check | Copied pattern: card lines are draft cells confirmed by the named person |
| `modules/m2_baseline/api/lens_chat.py` L208-L262 | Lens facts and ask | Reshaped: facts gain confirmed card lines |
| `sh_platform/graph/versions.py` L180-L200 | Node route with versions | Reused for last change |
| `sh_platform/build/opportunity_watch.py` L160 | Watcher detect | Not used directly; 56 owns it |
| `sh_platform/build/prove.py` | Prover and release | Not used: Proving lines come from 58 |

## Not in this feature

- The radar and hypothesis shape (57), Proving and verdicts (58), the Architect's other work (59).
- New figures, forecasts or blended lens scores.
- Editing a gold table or its pipeline from the card.
- Cards for silver or bronze tables.
- Any super admin view.

## Open questions

1. Consume routes live under `/centre/consume/...`, not `/centre/intent/...` (DoD 12, ruling 1). Confirm `/centre/consume/lens/<lens>` and the `?card=` and `?lens=` keys.
2. New API under `/api/company/consume/...` beside the existing `/api/company/feeds`, not `/api/intents/...`. Confirm.
3. May a measure sit in two lenses (K01 funding headroom reads as risk and as cost)? This file says one.
4. What "new revenue" and "retention" mean for a family office (returns and alpha, K15 and K16? retaining managers, staff or family members?). Lens drafts; the meaning is not given.
5. The lens names clash with the agent Lens in copy. Rename the four (for example "views") or keep?
6. Who may turn a what-if into an opportunity: 56's raise roles (owner, analyst) or the keep roles (sponsor, analyst, company admin)?
7. 56's evidence trace kinds have no `whatif`; add it, or record the kept scenario as `edge`?
8. The Architect is not one of the brief's three agents (section 5). Confirm it may draft a record people confirm.
9. Who receives the lens inform line, and how often; no threshold for "worth a line" is given.
10. Which owner confirms a card when a gold table serves measures with different data owners?
11. A catalogue may name a mart other than `gold.<code>` (SHAPES 2); which measure page shows its card?
12. Ask Lens needs a signed baseline today (`MeasurePage.tsx` L206); should a confirmed card let Lens answer without one?
13. Does the card's "why" come only from the person, or may the Architect draft it from the change note (59)?
