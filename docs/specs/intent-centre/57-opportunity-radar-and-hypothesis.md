# 57. Opportunity radar and the hypothesis record

Part of: Intent Centre v2. Depends on: 56 (data-backed opportunities), 55 (data knowledge map), 04 (home), 05 (areas), 19 (centre measures), 21 (backlog), 22 (Initiative start), 23 and 25 (wall and suggestion cards), 32 (charter), 35 and 37 (Brainstorm start and outcome), 38 to 40 (weekly check-in), 43 (Decision), 48 (admin defaults). Feeds: 04, 13 (Pulse lines), 19, 21, 22, 32, 35, 58 (Initiative outcomes), 60 (Consume by lens).

## Purpose (three sentences)

File 56 lets the Watcher notice a pattern in the run log, alerts, feeds and check-in weeks and lets North judge whether it merits an Initiative; this file turns that into a radar that also reads documents and voices, states each opportunity as one testable hypothesis, and checks it against counter-evidence before anyone sees it as a suggestion. The hypothesis record (belief, lens, evidence lines traced to records, measure, baseline, target, expected uplift with its basis, confidence in words, review date, state) is one shape shared by the opportunity, the Brainstorm outcome, the Initiative and its charter, so the thing that was noticed is the thing that is later proved (58). People see the radar for their own line of work, for an area and by lens on the Intent home and in Consume, and only a person turns an opportunity into a Brainstorm or an Initiative; no agent ever opens an intent (ruling 32).

### What 57 adds to 56 (56 stays in force; nothing in it is replaced)

| 56 has | 57 adds |
|---|---|
| Opportunity record `intents/opportunities/<id>.json`, states `noticed` to `dismissed` | Field `hypothesis_ref` on the record; one new state `rejected` (North, with reason); field `pattern.kind: data \| theme` |
| The Watcher reads five record kinds; "never notices from documents" | The Watcher still reads only data. Lens reads documents on the context shelves and voices (wall cards, check-in items, brainstorm ideas, backlog items) and groups repeated wishes into one theme with the voices counted |
| North judges "fits an Initiative: yes or no" | North first writes the hypothesis, then runs the counter-evidence check; a pattern the evidence breaks is rejected with the reason and the record that broke it |
| Evidence lines `supports \| disputes` with a source | Each line also carries `record_kind: data \| document \| voice` |
| Panels on the Ops page and the Intent home; drawer on the backlog | The radar view (per person, per area, per lens) on the home and in Consume; hypothesis, counter-evidence and voices regions in the 56 drawer |
| "Pick it up" opens an Initiative start | "Think it through first" opens a Brainstorm start; both pre-fill from the hypothesis, every answer marked guessed |
| The Watcher runs inside `GET /api/intents/opportunities` | A scheduled scan, with today's on-read run kept as the fallback |
| Three thresholds in the admin settings | The thresholds shown on the admin Defaults tab, plus two new keys; all empty by default |

## Who uses it and when (role, moment, trigger)

| Role (Ardmore demo) | Moment | Trigger |
|---|---|---|
| Harvey, ops manager (`owner`) | Daily | Radar on the home, scope "My line of work": sources and processes he owns |
| Katie, analyst (`analyst`) | When Lens or North writes a hypothesis in her areas | Pulse line "North wrote a hypothesis. Check its evidence"; she adds or disputes lines |
| Mei Ling, treasury (`participant`) | When she reads the radar for Treasury | Radar, scope "An area" |
| Janet, organiser | Before starting something | Radar by lens; "Think it through first" if she is allowed (open question 4) |
| Daniel, sponsor | Monthly | Consume, radar room, by lens |
| Grace, approver | When a risk-lens hypothesis touches an open Decision | Pulse line from Nira naming the Decision |
| Company admin | Setting up | Admin Defaults tab, card "Radar thresholds" |
| Super admin | Never | No route (ruling 5) |

## Entry points (every route, link, Pulse line, button that leads here)

- Intent home `/centre/intent?view=radar` (open question 1 on the `view` value): link "Open the radar" on the 56 panel "Opportunities from the records" (`ui/src/intents/IntentHome.tsx` L331).
- Consume centre `/centre/consume`: a fourth room tile "Opportunities" in the rooms list (`ui/src/pages/ConsumeCentre.tsx` L25-L33) to `/centre/consume/radar` (New route, open question 2).
- 56 drawer `/centre/intent/backlog?opportunity=<id>` and the Ops page drawer (`ui/src/pages/OpsPage.tsx` L166-L167): new regions, see Screen C.
- Pulse lines (Nira, kind `decision`): "North wrote a hypothesis on <measure or theme>. Check its evidence." to analysts of the areas; "North rejected a pattern: <title>. See why." to the person who raised it, if a person did; "A hypothesis touches the open Decision <title>." to the decider (43).
- Buttons "Pick it up" (56) and "Think it through first" (New) lead to `/centre/intent/new?type=initiative&from=<opp id>` and `/centre/intent/new?type=brainstorm&from=<opp id>`.
- Admin Defaults `/centre/intent/admin?tab=defaults`: card "Radar thresholds".
- API (New): `GET /api/intents/radar?scope=mine|area|lens&area=<id>&lens=<lens>`, `GET /api/intents/hypotheses/<hyp id>`, `POST /api/intents/opportunities/<id>/hypothesis` (a person edits target, review date or lens), `POST /api/intents/opportunities/<id>/state` gains action `think_through`. Each is declared in `sh_platform/route_permissions.yaml` (default deny) with the roles of the 56 routes at L449-L453.

## Screens, element by element

### Screen A. The radar (Intent home)

Route: `/centre/intent?view=radar&tab=mine|areas|lenses&focus=<area id or lens>`.

Layout at 1280: page frame title "What the records suggest"; a three-tab strip (My line of work, By area, By lens); under it four lens columns (New revenue, Process cost, Retention, Risk) of opportunity cards, each column headed by its count; a right aside "Rejected by North" and "How the radar works". Layout at 390: tabs become a select; the four columns become four collapsible sections in lens order; the aside moves below as two collapsed rows.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Title "What the records suggest" | heading | Fixed, sub-line "Patterns in your data, documents and what people said. North checks each one before it reaches you." | None | Roles of `GET /api/intents/opportunities` (`owner`, `company_admin`, `sponsor`, `analyst`) plus open question 3 | Always shown |
| Tab "My line of work" | tab | Opportunities touching a measure, source or process the viewer owns (graph `owned_by` edges, 55), or where the viewer is a voice or added evidence | Sets `tab=mine` | As title | "Nothing on the radar touches your work yet." |
| Tab "By area" | tab + select | Area picker from the viewer's areas (`profile/areas`) | Sets `tab=areas&focus=<area id>` | As title | "You are not tagged to an area. Ask your company admin." |
| Tab "By lens" | tab | All four columns, whole company the viewer may see | Sets `tab=lenses` | As title | See columns |
| Lens column heading | heading + count | "New revenue (n)", "Process cost (n)", "Retention (n)", "Risk (n)": count of open opportunities with `hypothesis.lens` equal to it, from `intents/hypotheses/*.json` joined to the opportunity | Click sets `focus=<lens>` and shows only that column | As title | "(0)" and the line "Nothing here yet." |
| Opportunity card | card (dashed while `proposed`, solid otherwise) | Title; belief in one sentence; measure name; baseline and target with periods, or "Not available yet: <what is missing>"; expected uplift with its basis word; confidence in words; evidence mix "2 data, 1 document, 4 voices" counted from `evidence[].record_kind`; state chip | Opens Screen C | As 56 Rules: areas plus every touched measure visible | n/a |
| Theme chip | chip | "Theme, 7 voices" from `theme.voices` | None | As card | Not drawn on data patterns |
| "Rejected by North" list | list | Title, one-line reason, the record that broke it, date | Opens Screen C | As card | "North has rejected nothing yet." |
| "How the radar works" | text | Fixed: who scans, how often (from settings), which thresholds are set, last scan time from `intents/radar/scans.jsonl` | Link "Radar thresholds" for the company admin only | As title | "The radar has not run yet. Thresholds are not set." with the names of the unset keys |
| Thresholds notice | agent line (Nira) | "Not available yet. <n> of 6 radar thresholds are not set, so those checks stay silent." | Company admin: link to Screen D | As title | Hidden when all are set |

### Screen B. The radar room in Consume

Route: `/centre/consume/radar` (open question 2). Same cards as Screen A, read only, grouped by lens, for people who read numbers rather than act on them. File 60 owns the lens grouping of the other Consume rooms; this room follows it.

Layout at 1280: page frame "Opportunities, by lens"; four columns as Screen A; no tabs. Layout at 390: four collapsible sections.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Room tile "Opportunities" on `/centre/consume` | tile | Count of open opportunities the viewer sees | Opens this room | Consume roles (`RoleGate centre="consume"`, `ui/src/App.tsx` L144) | Tile dim with "Not available yet: nothing noticed" |
| Lens columns and cards | list | As Screen A, without actions | Card opens Screen C read only | Consume roles, filtered by 56 Rules | As Screen A |
| Link "Act on these on the Intent home" | link | Fixed | `/centre/intent?view=radar` | Viewers who also have the Intent routes | Hidden otherwise |

### Screen C. Hypothesis regions in the 56 drawer

Route: `/centre/intent/backlog?opportunity=<id>` (56 Screen C), same frame (`ui/src/intents/OpportunitiesPanel.tsx`, `OpportunityDrawer` from L221). 57 adds four regions between "North's judgement" and "Proposed start answers", and one button. Layout at 1280: regions stack in the 480 px panel. Layout at 390: each region is a collapsible row, "Hypothesis" open by default.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| "Hypothesis" region | panel + agent line (North) | Belief; lens chip; measure; baseline (value, unit, periods, trace link); target (value, by date, who set it); expected uplift (value, per month or year, basis); confidence in words; review date; version "v2, 6 Oct" | Trace links open the record (56 trace kinds, plus document and voice) | As 56 drawer | "North has not written a hypothesis yet. It waits for Lens's evidence." |
| Lens select | field (select) | New revenue, Process cost, Retention, Risk | Writes a new version with `lens` and `by` the person | `owner`, `analyst` while not picked up | North's draft, marked "Guessed by North" |
| Target fields | field (number, unit fixed from the measure; native date input for "by") | Target value and date | "Save target" writes a new version; uplift recomputed only when basis is `gap_to_target` | `owner`, `analyst` | "No target yet. Set one or leave it for the start questions." |
| Review date | field (native date input) | `review_date` | Writes a new version | `owner`, `analyst` | Required before "Pick it up" or "Think it through first" |
| Expected uplift | text | Value with basis word: "Gap to target", "Stated by <name>", "What others in the industry usually see (pack)", "Measured after an earlier Initiative" | Basis link opens its record | As drawer | "Not available yet: no baseline" or "no target" or "no measure for this theme" |
| "Evidence by kind" region | list | Lines grouped Data, Documents, Voices; each line: text, stance (supports or counters), record link, added by, date | Record link opens it; a document opens on its shelf; a voice opens the wall card, week item or idea | As drawer; a document the viewer may not open shows "A document you cannot open"; an anonymous voice shows "Someone, anonymously" | "No evidence of this kind." per group |
| "Counter-evidence check" region | panel + agent line (North) | What North looked for, what it found, verdict "Holds" or "Broken", with the breaking record linked | None | As drawer | "North has not checked this yet." |
| "Voices" region (themes only) | list | Count of voices; per source (wall, check-in, brainstorm, backlog) a count and the named people who are not anonymous | Each row opens its record | As drawer; anonymous voices counted, never named | Hidden on data patterns |
| Button "Think it through first" | button | Fixed | Writes `picked_up_by` with `as: brainstorm`, opens `/centre/intent/new?type=brainstorm&from=<id>` pre-filled | `owner` (open question 4) | Disabled until a hypothesis exists and is "Holds"; hidden after pick up |
| Button "Bring back" (widened) | button | On `rejected` too | Sheet: reason (required); state `under_review`; North re-checks | `owner` | Hidden otherwise |
| "Rejected because" line | agent line (North) | Reason and the record that broke the pattern | Record link | As drawer | Hidden unless `rejected` |

### Screen D. Radar thresholds (admin Defaults)

Route: `/centre/intent/admin?tab=defaults` (48 Screen B), one new card under "Privacy". Layout at 1280: card with one row per key. Layout at 390: rows stack, Save bar as 48.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Row per existing key | field (whole number) | `late_same_weekday`, `drift_periods`, `checkin_items_same_step`, `window_days` (`sh_platform/intents/admin.py` L35) in words | Edited in place; saved by the 48 "Save defaults" | Company admin | Empty, with "Not set: this check stays silent" |
| Row "Voices that make a theme" | field (whole number) | New key `theme_min_voices` | As above | Company admin | As above |
| Row "Periods North checks against" | field (whole number) | New key `counter_periods` | As above | Company admin | As above |
| Row "Scan" | field (select) | New key `scan`: "When someone opens the radar" or "Every working day after the runs" | As above | Company admin | "When someone opens the radar" (today's behaviour) |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

Illustrative, synthetic Ardmore; no figure here is a planted value.

1. Overnight, on the schedule, the Watcher runs `detect` (`sh_platform/build/opportunity_watch.py` L160-L171) over runs, alerts, feeds and week files and drafts data patterns; each scan appends a row to `intents/radar/scans.jsonl`.
2. Lens reads new documents on the context shelves and new voices since the last scan. It finds the same wish, in different words, on two walls, in one check-in item and in one brainstorm idea; with `theme_min_voices` met it drafts one opportunity, `pattern.kind: theme`, with four voices counted.
3. North writes a hypothesis for each new opportunity: belief, lens, measure, baseline from the feed (traced), target left empty, uplift "Not available yet: no target", confidence, review date proposal. Then it runs the counter-evidence check. For one data pattern it finds that the measure and the suspected cause moved together in two periods but not in a later one, and that the effort log names a different cause for the same hours. It writes verdict "Broken", state `rejected`, with both records linked. The others hold and move to `proposed`.
4. Nira writes the Pulse lines. Katie opens the radar, tab "By area", Operations. She opens a card, reads the counter-evidence region, adds a document evidence line (a supplier email on a shelf) with stance supports. North re-checks once; the verdict stays "Holds".
5. Harvey opens "My line of work". He sets a target and review date on the theme's hypothesis; the uplift stays "Not available yet: no measure for this theme" because a wish has no measure.
6. Harvey presses "Think it through first". The Brainstorm start (35) opens with Q1 statement = belief, context = evidence summary, Q2 good outcome drafted from the target, Q3 suggested people = the named voices and the owners, Q4 areas = the opportunity's areas; each "Guessed by North". He edits and opens it. The Brainstorm record carries `hypothesis_ref`.
7. For another card he presses "Pick it up" (56); the Initiative start (22) pre-fills goal from the belief and target; the intent carries `hypothesis_ref`.
8. Janet reads the "Rejected by North" aside, disagrees, and asks Harvey; Harvey presses "Bring back" with a reason; North re-checks and writes a new version.
9. They leave the radar. Later the Brainstorm's chosen outcome (37) and the charter (32) carry new versions of the same hypothesis; 58 reads the version frozen at signature.

## States and transitions (table: state, who moves it, to what, what is written)

Opportunity states are 56's plus `rejected`. Hypothesis states are below.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| Opportunity `under_review` | North, check "Broken" | `rejected` | `rejected: {at, why, broke_by: [refs]}`; hypothesis `state: rejected`; history |
| Opportunity `under_review` | North, check "Holds" and fits | `proposed` | 56 judgement; hypothesis `state: checked` |
| `rejected` | Harvey, "Bring back" | `under_review` | History with reason; North re-checks |
| `proposed` | Harvey, "Think it through first" | `picked_up` | `picked_up_by`, `picked_up_as: brainstorm`; on intent creation `became` |
| Hypothesis (none) | North | `draft` | New `intents/hypotheses/<hyp id>.json`, version 1 |
| `draft` | North, counter check | `checked` or `rejected` | `counter_check` |
| `checked` | A person edits lens, target or review date | `checked` (new version) | New entry in `versions[]`, `by` the person |
| `checked` | Start flow on intent creation | `carried` | `carried_into: [{intent id, version}]` |
| `carried` | Organiser confirms the Brainstorm outcome (37) or the sponsor signs the charter (32) | `carried` (new version, frozen at signature) | Version with `frozen_by: charter:<id> v<n>` |
| `carried` | 58 | proving states owned by 58 | None here |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Read or written | Mark |
|---|---|---|---|
| `intents/hypotheses/<hyp id>.json` via `sh_platform/jsonfile.py` | `{id, origin: {kind: opportunity\|brainstorm\|initiative, ref}, state: draft\|checked\|rejected\|carried, carried_into: [], versions: [{v, at, by, belief, lens: new_revenue\|process_cost\|retention\|risk, measure: {id, name}\|null, baseline: {value, unit, periods, trace}\|null, target: {value, unit, by, set_by}\|null, expected_uplift: {value, unit, per: month\|year, basis: gap_to_target\|stated\|pack\|earlier_initiative, trace}\|null, confidence: fairly_sure\|not_sure\|unlikely, review_date, evidence: [{id, record_kind: data\|document\|voice, stance: supports\|counters, text, trace: {kind, ref, at}, voices\|null, by, line_ref\|null}], counter_check: {at, looked_for: [], found: [], verdict: holds\|broken, why}\|null, theme: {voices, by_source: {wall, checkin, brainstorm, backlog}}\|null, frozen_by\|null}]}` | Written by North and the hypothesis route; read per viewer | New |
| `intents/opportunities/<id>.json` (56) | adds `hypothesis_ref`, `pattern.kind`, `rejected`, `picked_up_as`, `evidence[].record_kind` | Read and written | Existing, widened |
| `intents/radar/scans.jsonl` | `{at, by: watcher\|lens\|north, read: {runs, alerts, feeds, weeks, documents, voices}, drafted, rejected}` counts only | Written each scan | New |
| `settings` opportunity block (`admin.py` L62-L116) | existing four keys plus `theme_min_voices`, `counter_periods`, `scan` | Read; written by the company admin | Existing, widened |
| Context shelves `context/agent_docs/<agent>/` (`sh_platform/context_docs/store.py` L142 `documents_for`, `retrieval.py` L94 `retrieve`) | documents and passages, restricted flag | Read by Lens | Existing |
| Wall cards (`modules/m1_intent/domain/board.py`, `mask_sealed` L135) | card text, author or anonymous | Read by Lens; sealed cards never | Existing |
| Week files `intents/<id>/weeks/<week_key>.json` (ruling 17) | `items[].kind`, `text`, `by` | Read | Existing |
| Brainstorm ideas and outcome (36, 37) | idea text, `outcome.chosen` | Read; `outcome.chosen.hypothesis_ref` written by the start and converge flows | Existing, widened |
| `intents/backlog.json` (21) | `title`, `why_it_matters`, `raised_by` | Read as voices | Existing |
| `intents/<id>/intent.json` | `hypothesis_ref` | Written by the start flow, never by an agent | Existing, widened |
| Charter `pages_frozen` (32) | adds `hypothesis_ref` with version | Written at signature | Existing, widened |
| Open Decisions (43) | `outcome.question`, areas, state | Read for the link check | Existing |
| Routes listed in Entry points | as above | Read and written | New |
| `docs/product/input_ledger.yaml` rows (CYCLE-PLAN section 4) | target, lens, review date: confirm; belief, evidence, counter check, theme count: derived; scan, counts: automatic | Rows to be added by the ledger owners, not by this file | New rows |

## Fields this feature adds to the intent record

- `hypothesis_ref: {id, version} | null`: set by the start flow when an intent opens from an opportunity, or by the Brainstorm converge flow (37) and the charter (32) when they write a new version.
- Brainstorm `outcome.chosen.hypothesis_ref` (inside 02's flat outcome shape, ruling 16).

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **The Watcher** (data only, as 56): on each scan runs `detect` (`opportunity_watch.py` L160-L171) with the set thresholds; an unset threshold keeps its detector silent (L30-L41). It never reads text.
- **Lens** (documents and voices): on each scan reads documents on shelves the company has marked readable for agents and voices since the last scan. It adds evidence lines with `record_kind` to open opportunities whose touches the text names, and groups wishes that say the same thing into one theme, counting distinct voices (a named person once per theme; each anonymous item once). Below `theme_min_voices` nothing is drafted. It never reads sealed cards, private interview notes or restricted documents for viewers who may not open them.
- **North** (on each new opportunity and each new evidence line, once per change, as `_rejudge` in `sh_platform/intents/opportunities.py` L166-L177):
  1. Writes the hypothesis version. Baseline only from a traced feed value; target only from a person, else empty; uplift only with a basis that traces; otherwise "Not available yet" naming what is missing. Words for confidence, never a percentage.
  2. Runs the counter-evidence check over the last `counter_periods` periods: periods where the pattern should hold and does not; a record that attributes the effect to another cause; a one-off event (holiday, failed run, corrected statement); the measure already back in range; an open intent or open Decision on the same measure, in which case it links to it and says so rather than proposing a new one.
  3. If broken: state `rejected`, with the reason in two sentences and the breaking records. If it holds: 56's judgement follows.
- **Nira** writes the three Pulse lines and reminds on review dates.
- **People act**: Katie adds or disputes evidence; Harvey or Katie edit lens, target and review date; Harvey picks up, thinks it through first, parks, dismisses or brings back. No agent opens an intent, picks up or sets a target.

Kinds of pattern the radar must handle (the acceptance cases; no answer key here):

| Kind | Lens | Read by | What the radar must do |
|---|---|---|---|
| Money sitting idle above a stated policy | New revenue | Watcher (balances), Lens (minutes, notes) | Propose, with baseline from the feed |
| A late source driving manual effort | Process cost | Watcher (runs, alerts), Lens (check-ins, emails) | Propose; one record, not one per symptom |
| Falling report use with rising questions | Retention | Watcher (feeds), Lens (feedback notes) | Propose |
| Stale inputs feeding a risk measure | Risk | Watcher, Lens (compliance notes) | Propose |
| A cost that stepped after a structural change, not yet acted on | Process cost | Watcher (drift), Lens (fee emails) | Propose |
| An exposure already the subject of an open Decision | Risk | Watcher, North link check | Link to the Decision, no duplicate |
| The same wish in many places, no measure | Any | Lens (voices) | One theme, voices counted, uplift "Not available yet" |
| A correlation that breaks in a later period or is explained by another cause | Any | North check | Reject, naming the period and the record |
| An Initiative already running on the same measure | Any | North link check | Say so; no new proposal |

## Rules (visibility, time box, who may do what)

- Visibility is 56's (areas, plus every touched measure visible through `Ctx.sees`, `opportunities.py` L181-L199). A hypothesis is visible exactly where its carrier is.
- Voices: anonymous voices are counted and never named; sealed material is never read (D-013); a document line shows its text only to viewers who may open that document.
- Thresholds are company settings only. No default value exists in code or copy; an empty key means "Not available yet".
- A hypothesis version is never edited in place; edits make a new version. A version frozen by a charter signature never changes.
- Only a person sets a target. North may draft a target in the start questions, marked guessed.
- "Think it through first" and "Pick it up" need a review date and a "Holds" check.
- No time box of its own. Rejected and dismissed records are kept.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Record | Empty |
|---|---|---|
| Open opportunities per lens | `intents/hypotheses/*.json` latest `lens`, joined to opportunity `state` in `noticed`, `under_review`, `proposed` | "(0)" per lens once any exist; "Not available yet: nothing noticed" before |
| Rejected by North | opportunities with `state = rejected` | As above |
| Rejections brought back | history rows `brought_back` after `rejected` | As above |
| Evidence mix per card | `evidence[].record_kind` of the latest version | "No evidence of this kind." |
| Voices in a theme | `theme.voices` | Hidden on data patterns |
| Became Brainstorm, became Initiative | `picked_up_as` and `became` resolving to an intent of that type with `hypothesis_ref.id` matching | "Fewer than five" below five (ruling 8) |
| Last scan, items read | `intents/radar/scans.jsonl` last row | "The radar has not run yet." |
| Uplift realised | 58 | "Not available yet: Initiative outcomes (58) are not recorded" |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: grep `opportunit` across `sh_platform`, `modules`, `ui/src`, `tests`; read of the 56 code below.

| File and lines | What it is | Use |
|---|---|---|
| `sh_platform/intents/opportunities.py` L72-L112 store and `run_watcher`, L116-L136 North prompt and parse, L166-L177 `_rejudge`, L181-L199 `Ctx`, L216-L237 `_can` and `_shape`, L254-L266 `pulse_lines`, L304-L452 routes | 56 as built | Reshaped: hypothesis written before the judgement; `rejected` state; `think_through` action; new lines |
| `sh_platform/build/opportunity_watch.py` L22-L41 keys and thresholds, L76-L157 detectors, L160-L182 `detect`, `same` | The Watcher's data step | Reused unchanged; called by the scan |
| `sh_platform/intents/admin.py` L35, L62-L116 | Opportunity settings keys | Reshaped: two new keys and `scan` |
| `ui/src/intents/OpportunitiesPanel.tsx` `SuggestedCard` L69, panel L106, `OpportunityDrawer` L221 | Card, panel, drawer | Reshaped: radar columns reuse the card; drawer gains regions |
| `ui/src/intents/IntentHome.tsx` L331, `sh_platform/intents/home.py` L370 | Home panel and its role gate | Reused; adds the radar link |
| `ui/src/pages/ConsumeCentre.tsx` L25-L33 | Consume rooms | Reshaped: fourth room |
| `sh_platform/pulse/intent_lines.py` L325-L342 | Opportunity Pulse lines | Reused for the three new lines |
| `sh_platform/context_docs/store.py` L142, `retrieval.py` L94 | Shelf documents and retrieval | Reused by Lens |
| `modules/m1_intent/domain/board.py` L135 `mask_sealed` | Seal rule on wall cards | Reused before Lens reads voices |
| `sh_platform/route_permissions.yaml` L449-L453 | 56 routes | Model for the new routes |

Genuinely new: the hypothesis store, the counter-evidence check, Lens's voice and document reading, the scan log, the radar view and Consume room.

## Not in this feature

- Proving, weekly uplift reports and verdicts (58).
- Grouping the other Consume rooms by lens (60).
- Ranking opportunities by a number or a score.
- Any agent opening, picking up, parking or dismissing.
- Reading outside material as evidence of the company's own figure (market briefs are context only, as Consume's footnote says).

## Open questions

1. `view=radar` on `/centre/intent`, and `tab` and `focus` values outside the ruling 18 list: allowed?
2. `/centre/consume/radar` is a new Consume route; does 60 own it?
3. May participants such as Mei Ling see the radar for their area, given 56's role gate (`owner`, `company_admin`, `sponsor`, `analyst`)?
4. Who besides the ops manager may press "Think it through first" or "Pick it up" (56 open question 4)?
5. Values for every threshold, including `theme_min_voices` and `counter_periods`; none is given.
6. Scan time and frequency: inside the runner after each run day, or a separate scheduled step?
7. Counting voices: is one anonymous item one voice, or is anonymity counted once per intent?
8. Should 56's `evidence[]` and the hypothesis's `evidence[]` merge into one list?
9. Which bases of expected uplift are acceptable for a family office, and may `pack` benchmarks ever be shown as a figure?
10. May North reject without a person seeing it first, or should rejection be a proposal a person confirms?
11. Which documents on the shelves may Lens read for the radar: all agent-readable ones, or only those marked for operations?
12. When a hypothesis touches an open Decision, should the Decision gain a link (20) automatically, or only after the decider confirms?
