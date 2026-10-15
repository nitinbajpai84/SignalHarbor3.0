# The moat: how little a person has to type

Signal Harbor's advantage is not that it has agents. It is that across the whole cycle a person mostly reads, taps and signs, while agents draft and the system counts. This file is the evidence. Every claim below cites rows in `docs/product/input_ledger.yaml` (merged from `docs/product/ledger/*.yaml` by `tools/ledger_summary.py`).

**Every minute figure in this file is a planning estimate, not a measurement.** Each row's `basis` says why the estimate was chosen. No minute figure may appear in product copy or a sales conversation as a fact; the claims may, because each one describes what the product does, and the rows say who confirms it.

Modes: **manual** (a person types, picks, uploads or decides with no draft), **confirm** (an agent drafts, a named person confirms, edits or rejects), **derived** (an agent works it out from documents, data or records), **automatic** (the system computes it by rule). Signatures and decisions are always manual; agents prepare them, people make them.

## Status of this ledger

Specs 01 to 56 and the built modules (`v1`) have their rows. Still without a ledger file (listed again in the generated block): the four return-cycle specs, 57 (opportunity radar and hypothesis), 58 (initiative outcomes and uplift), 59 (Build centre agent chain) and 60 (Consume by lens and context cards). Notice and Prove will thicken most when they land; until then Prove has no rows for the weekly uplift report or verdicts.

Build checks: specs 01 to 34 and 50 to 56 were checked against the code; 42 and 43 were checked; 35 to 41 and 44 to 49 were not, so a missing `built:` there means unchecked, not matching.

Known validation problems in the source files (left to their owners; the merge still includes the rows):
- `01.yaml`: seven rows use a stage word as the journey (`01.start_session`, `01.send_back`, `01.confirmer_sign`, `01.auto_closing`, `01.session_end`, `01.closure_signed`, `01.closed_in_box`). They are lifecycle rows common to every type and should read `journey: shared`. They appear as journeys `run`, `prove` and `decide` in the tables.

## The cycle in inputs

Notice, Think, Decide, Build, Run, Prove, then Notice again. For each stage: what a person gives, and what the product does without being asked.

**Notice.** A person gives: a line saying what they want to do, or what they saw (`03.free_text`, `41.q1.saw`); an opportunity raised by hand when they spot one first (`56.opp.raise`). The product: the Watcher notices repeated patterns in the run log, alerts, feeds and check-ins with no one asking (`56.opp.notice`); North judges whether a pattern is worth an initiative and says how sure it is (`56.opp.judge`), and Lens attaches the definition, owner and process step as evidence (`56.opp.evidence.lens`); North shows similar past intents before anyone starts (`12.similar`); a new family office is offered three starter intents from the industry pack (`18.first_intents`).

**Think.** A person gives: ideas and cards on the wall, answers to North's quarter questions, votes (`36.idea.add`, `23.b.q_answers`, `26.d.vote`). The product: North clusters, names and colours the cards before anyone arrives (`50.s05.cluster`, `26.d.clusters`); North looks up every term in the glossary and catalogue before the organiser asks (`22.q4.lookup`); Lens drafts every data source and technical area, every glossary term, the technical definition of every measure and all six governed fields, each marked stated, guessed or unknown (`28.draft`, `29.draft_terms`, `30.draft_all`, `31.draft_six`), and named owners confirm (`31.owners`); a person settles only the ambiguous terms (`29.pick_meaning`); Lens drafts every process the initiative touches, marked guessed with its source (`27.a.draft`), and assembles the processes page of the charter (`27.c.charter_page`).

**Decide.** A person gives: which shelf each cluster sits on, the decision and its reason, the charter signature, the hand to Build (`50.s06.shelf`, `13.decide_line`, `32.sign`, `33.handoff`). The product: North writes the charter draft from the ticked groups and shelves, then the whole charter from the initiative's records (`26.x.charter_draft`, `32.draft`); North recomputes the seven build-ready lines after every relevant write (`33.check`); Lens drafts process steps, technical definitions and all six governed fields for named people to confirm (`50.s07.process`, `50.s08.catalogue`, `50.s09.governed`); North drafts the option cards for a Decision, each with what it means, for, against and needs, and a source tag (`54.s04.cards`, `43.options.draft`).

**Build.** A person gives: a sample file, five environment answers, and the signatures (`v1.truth.upload`, `v1.build.environment`, `v1.build.blueprint.sign`). The product: the blueprint is drafted from the signed baseline with every row traceable (`v1.build.blueprint`); Lens profiles the sample and states quality rules in plain words (`v1.truth.rules`); the trial counts match, gap and not yet per measure (`v1.truth.trial`); the data map verifies each claim from column names and types and learns where each data point lives on every signature (`55.map.verify`, `55.map.update`); the hand-over list is read from the outcome, never assembled (`20.handoff_list`).

**Run.** A person gives: the three weekly questions, posts and evidence in a problem thread, a what-if slider (`13.week_line`, `53.s05.post`, `v1.consume.whatif.slider`). The product: the week is prefilled from the run log (`52.s03.prefill`); North groups repeated items into a digest with every original kept (`52.s05.digest`, `40.digest.groups`); North keeps a running summary of a problem, each line cited (`53.s05.know`); every released measure shows its value, status and 30-day line (`v1.consume.feeds`); the what-if impact is computed as the slider moves (`v1.consume.whatif.impact`).

**Prove.** A person gives: the closure signature, an approval or send-back, acceptance of a gap with a reason (`09.sign`, `09.approver_decision`, `v1.build.prove.accept`). The product: the transcript of a closed intent is ready to attach (`16.transcript`); the portfolio and quarterly counts come from the records (`01.counters`, `04.counters`, `12.counters`); the company learns which kinds of intent earn their time without ranking any person (`10.worth_section`); outcome use a month later is counted (`19.m14_m15`). The weekly uplift report and verdicts (spec 58) will add rows here.

## Twenty strongest claims

Each claim is something the product does. Row ids are the evidence; the minute figures behind them are planning estimates.

1. The Watcher notices repeated patterns in the records with no one asking. (`56.opp.notice`, `56.opp.judge`)
2. Before anyone starts, North shows past intents that covered the same ground. (`12.similar`)
3. A new family office opens the centre to a starting list of intents from its industry, each prefilled with one tap; no workshop. (`18.first_intents`, `49.strip.build`)
4. North clusters and names a wall of cards before anyone arrives. (`50.s05.cluster`, `26.d.clusters`)
5. North writes the whole charter from the initiative's records and the shelves people chose, and keeps the build-ready check current after every change. (`26.x.charter_draft`, `32.draft`, `33.check`)
6. Every term is looked up in the glossary and catalogue before the organiser asks. (`22.q4.lookup`)
7. Lens drafts every process an initiative touches, marking what is guessed and where it came from. (`27.a.draft`, `27.c.charter_page`)
8. Lens drafts every data source, glossary term and technical definition before anyone asks, each marked stated, guessed or unknown; people settle only what is ambiguous. (`28.draft`, `29.draft_terms`, `30.draft_all`, `44.kind.technical`, `29.pick_meaning`)
9. Lens drafts all six governed fields with a plain source for each; the named owners confirm. (`31.draft_six`, `31.owners`, `50.s09.governed`)
10. For a Decision, North drafts the option cards, each with for, against, needs and its source. (`54.s04.cards`, `43.options.draft`)
11. A reviewer reads themes, not forty messages: the week is grouped, every original kept. (`40.digest.groups`, `52.s05.digest`)
12. The weekly check-in arrives prefilled from the run log. (`52.s03.prefill`)
13. A problem keeps its own running summary, every line cited to a post or record. (`53.s05.know`)
14. The build blueprint is drafted from the signed baseline, with every row traceable. (`v1.build.blueprint`)
15. Lens profiles a sample and states the quality rules in plain words; the trial grades each measure by itself. (`v1.truth.rules`, `v1.truth.trial`)
16. The company data map is built from records and checked against the real columns, never edited by hand. (`v1.map.page`, `55.map.verify`, `55.map.update`)
17. Every released measure shows its latest value, status and 30-day line, and a what-if shows which measures move. (`v1.consume.feeds`, `v1.consume.whatif.impact`)
18. Access to every intent is worked out from who is in it and its state; nobody maintains permissions per project. (`14.access_layer`)
19. A closed intent produces its transcript and its hand-over list without anyone assembling them. (`16.transcript`, `20.handoff_list`)
20. The portfolio, the quarterly review and which kinds of intent earn their time are counted from the records, never from a status sheet, and never rank a person. (`01.counters`, `04.counters`, `12.counters`, `10.worth_section`, `19.m05_m07`)

## Gaps: where a person still types what an agent could draft

Each is a candidate feature.

**The spec says an agent drafts it; the build has a person type it** (rows carry `built:`):
- What happens next at closure, with kind, title and reason: the build proposes one empty row. (`01.closure_next`, `09.next_rows`)
- Initiative start answers: goal, why it matters, who takes part, who is affected. North drafts only when a source intent or chooser line is carried. (`22.q1.goal`, `22.q1.why`, `22.q2.takers`, `22.q2.affected`)
- Brainstorm's good outcome. (`35.q2.good_outcome`)
- Who to invite and the named slots (decider, owner). (`06.pick_people`, `06.named_slot`)
- Who to share with, and the offer to share a closed outcome. (`11.share_pick`, `11.closure_offer`)
- Reasons and short texts: extending, cancelling, a chat message, the next step after a No or Partly. (`07.extend_reason`, `12.cancel_summary`, `13.chat_text`, `10.used_next`)
- The next question on the projector. (`17.next_question`)
- Not built at all: add someone or carry on when declines leave too few people. (`06.decline_gap`)

Outcome lines (`04.outcome_line`, `12.outcome_line`, `15.outcome_line`) are drafted by rule from the first sentence rather than confirmed; that is fewer inputs than the spec, not more, but the organiser never sees it to correct.

**Manual in the spec, but an agent could draft it:**
- Session time and the day the week closes, offered from calendars. (`51.s02.session`, `52.s01.day`)
- How hard a problem bites, from the size of the alert that raised it. (`53.s01.q3`)
- Cost to change in a Decision, from earlier decisions and the catalogue. (`54.s04.cost`)
- An opportunity raised by hand, with its first evidence line drafted from what the person is looking at. (`56.opp.raise`)
- The five environment answers for Build, from the company profile's systems list. (`v1.build.environment`)
- The company's areas, from an uploaded organisation chart (the person tags already are drafted). (`05.areas_list`, `05.people_tags`)
- Source details a person still types: expected arrival time and a known problem with a source, from the run log and earlier problems. (`28.arrival_time`, `28.problem`)
- Glossary and catalogue edits typed free: wording edits, technical notes and proposed changes to a company term could start from a Lens redraft. (`29.edit`, `30.notes`, `29.propose_change`)
- Governed cells are confirmed one by one: a single "confirm all drafted, unchanged" for each owner would cut the taps. (`31.owners`)

## The numbers

Generated by `tools/ledger_summary.py`; do not edit between the markers. Minutes are planning estimates.

<!-- ledger:start -->
Rows: **1527**. manual 508, confirm 227, derived 276, automatic 516.

### By journey

| journey | rows | manual | confirm | derived | automatic |
|---|---:|---:|---:|---:|---:|
| shared | 481 | 146 | 56 | 102 | 177 |
| initiative | 421 | 138 | 96 | 72 | 115 |
| brainstorm | 144 | 65 | 22 | 20 | 37 |
| checkin | 133 | 42 | 15 | 20 | 56 |
| problem | 103 | 45 | 15 | 20 | 23 |
| admin | 89 | 17 | 4 | 9 | 59 |
| decision | 67 | 24 | 13 | 10 | 20 |
| consume | 49 | 16 | 3 | 11 | 19 |
| build | 40 | 15 | 3 | 12 | 10 |

### By stage

| stage | rows | manual | confirm | derived | automatic |
|---|---:|---:|---:|---:|---:|
| think | 511 | 185 | 109 | 80 | 137 |
| decide | 257 | 108 | 43 | 40 | 66 |
| notice | 237 | 65 | 30 | 44 | 98 |
| run | 200 | 70 | 23 | 44 | 63 |
| prove | 189 | 49 | 15 | 42 | 83 |
| shared | 88 | 16 | 0 | 12 | 60 |
| build | 45 | 15 | 7 | 14 | 9 |

### By role

| role | rows | manual | confirm | derived | automatic |
|---|---:|---:|---:|---:|---:|
| organiser | 574 | 184 | 123 | 100 | 167 |
| participant | 182 | 89 | 12 | 23 | 58 |
| analyst | 95 | 25 | 22 | 32 | 16 |
| owner | 83 | 30 | 17 | 17 | 19 |
| reporter | 71 | 33 | 10 | 11 | 17 |
| company admin | 59 | 17 | 0 | 7 | 35 |
| any | 46 | 8 | 0 | 12 | 26 |
| company_admin | 36 | 4 | 5 | 2 | 25 |
| sponsor | 36 | 18 | 1 | 9 | 8 |
| system | 34 | 0 | 0 | 2 | 32 |
| reviewer | 30 | 8 | 2 | 8 | 12 |
| ops manager | 26 | 9 | 3 | 9 | 5 |
| affected person | 21 | 9 | 0 | 1 | 11 |
| person | 20 | 2 | 0 | 6 | 12 |
| decider | 19 | 8 | 3 | 3 | 5 |
| data owner | 17 | 4 | 6 | 6 | 1 |
| governance lead | 16 | 9 | 4 | 2 | 1 |
| any person | 15 | 6 | 0 | 0 | 9 |
| committee | 14 | 4 | 4 | 2 | 4 |
| reader | 11 | 0 | 2 | 4 | 5 |
| source owner | 10 | 4 | 5 | 0 | 1 |
| adviser | 9 | 8 | 1 | 0 | 0 |
| approver | 9 | 3 | 2 | 1 | 3 |
| consume reader | 9 | 0 | 0 | 2 | 7 |
| architect | 8 | 1 | 1 | 5 | 1 |
| head of department | 7 | 2 | 0 | 2 | 3 |
| affected | 6 | 3 | 0 | 1 | 2 |
| named person | 6 | 4 | 0 | 0 | 2 |
| term owner | 6 | 4 | 2 | 0 | 0 |
| business owner | 5 | 1 | 1 | 1 | 2 |
| invited person | 5 | 2 | 0 | 0 | 3 |
| process owner | 5 | 4 | 0 | 1 | 0 |
| super admin | 5 | 1 | 0 | 0 | 4 |
| visitor | 5 | 0 | 0 | 3 | 2 |
| admin | 4 | 2 | 0 | 0 | 2 |
| build team | 4 | 0 | 0 | 1 | 3 |
| company_person | 4 | 0 | 0 | 0 | 4 |
| developer | 3 | 1 | 0 | 1 | 1 |
| super_admin | 3 | 0 | 0 | 0 | 3 |
| observer | 2 | 0 | 0 | 0 | 2 |
| tester | 2 | 1 | 0 | 1 | 0 |
| anyone | 1 | 0 | 0 | 0 | 1 |
| area member | 1 | 0 | 0 | 0 | 1 |
| component owner | 1 | 0 | 1 | 0 | 0 |
| everyone | 1 | 0 | 0 | 0 | 1 |
| raiser | 1 | 0 | 0 | 1 | 0 |

### Minutes per journey (planning estimates, not measurements)

| journey | rows | minutes without | minutes with | saved |
|---|---:|---:|---:|---:|
| initiative | 420 | 7288 | 557.5 | 6730.5 |
| shared | 439 | 5067 | 223 | 4844 |
| admin | 87 | 2611 | 53 | 2558 |
| build | 17 | 973 | 40 | 933 |
| checkin | 133 | 945 | 108 | 837 |
| brainstorm | 144 | 819 | 143.5 | 675.5 |
| problem | 103 | 784 | 110 | 674 |
| decision | 67 | 690 | 87 | 603 |
| consume | 25 | 488 | 8.7 | 479.3 |
| all | 1435 | 19665 | 1330.7 | 18334.3 |

### Missing in the build (92 rows: feature gaps, not counted as savings)

- `06.decline_gap` (confirm in spec): Add someone, or carry on, when declines leave too few people
- `44.kind.governed` (derived in spec): Governed state, six fields
- `47.close.notes` (derived in spec): Summary of affected people's notes and counts in the closure draft
- `49.hint.line` (derived in spec): Others often say: a wording hint under a start question
- `49.hint.use` (confirm in spec): Copy the hint into the field as a draft
- `49.hint.hide` (manual in spec): Hide hints for this session
- `49.checkin.panel` (derived in spec): Suggested weekly questions for the chosen area
- `49.checkin.add` (confirm in spec): Add a suggested question as my own
- `49.checkin.dismiss` (manual in spec): Hide a suggested question
- `49.wall.cards` (derived in spec): Problem and measure cards on a blank lane
- `57.tabs` (automatic in spec): Which cards touch my work, my area or my lens
- `57.lenscount` (automatic in spec): Open opportunities per lens
- `57.card` (derived in spec): Belief, measure, baseline, target, uplift, confidence and evidence mix on a card
- `57.theme` (derived in spec): A theme and the count of voices behind it
- `57.reject` (derived in spec): A pattern rejected with the record that broke it
- `57.scan` (automatic in spec): Last scan time and items read
- `57.hypo` (confirm in spec): The hypothesis: belief, baseline, target, uplift, confidence
- `57.lens` (confirm in spec): Which lens the opportunity sits in
- `57.target` (manual in spec): Target value and date
- `57.review` (manual in spec): Review date
- `57.uplift` (derived in spec): Expected uplift with its basis word
- `57.evidence` (derived in spec): Evidence lines grouped data, documents, voices
- `57.evadd` (manual in spec): Added or disputed evidence line
- `57.counter` (derived in spec): Counter-evidence check verdict, Holds or Broken
- `57.voices` (automatic in spec): Voices behind a theme by source
- `57.think` (manual in spec): Think it through first, opening a Brainstorm
- `57.bringback` (manual in spec): Bring back a rejected opportunity with a reason
- `57.thresholds` (manual in spec): Radar thresholds: late weekday, drift periods, check-in items, window, theme voices, counter periods, scan
- `57.tile` (automatic in spec): Count of open opportunities the viewer sees
- `58.chip` (automatic in spec): Proving state from release to review date
- `58.hypo` (derived in spec): Hypothesis frozen at charter signature
- `58.start` (derived in spec): Live since date
- `58.startchg` (manual in spec): Changed start date with a reason
- `58.weekly` (derived in spec): Before, Now and Target figures each with trace
- `58.series` (automatic in spec): Measure series since start, target line and normal range
- `58.notes` (derived in spec): What else moved the measure
- `58.noteadd` (manual in spec): An attribution note with its record or No record
- `58.verdict` (derived in spec): Verdict, rule and confidence in words
- `58.confirm` (manual in spec): Confirm or change the weekly verdict
- `58.nochange` (automatic in spec): No new period landed, nothing to confirm
- `58.summary` (derived in spec): Review summary and proposed outcome
- `58.choice` (manual in spec): Review action: keep, more time, send back, stop
- `58.learning` (confirm in spec): What held and what did not, naming the period or segment
- `58.sponsor` (manual in spec): Sponsor confirms or sends back the outcome
- `58.rules` (manual in spec): Periods a verdict needs
- `58.receipt` (derived in spec): Receipt to each person whose voice fed the Initiative
- `59.chain` (automatic in spec): Change rows with the five steps and who holds each
- `59.step` (derived in spec): Person for each step from the charter
- `59.days` (automatic in spec): Working days at the current step
- `59.archview` (derived in spec): Data, infrastructure and enterprise diagrams
- `59.components` (derived in spec): Components with owner, version and state
- `59.owner` (manual in spec): Owner of a component
- `59.desc` (confirm in spec): Plain-words description of an enterprise component
- `59.version` (automatic in spec): Version, what produced it, counts added, changed, retired
- `59.ownersmissing` (derived in spec): Components with no owner
- `59.note` (confirm in spec): The change note, seven sections
- `59.why` (derived in spec): Why the change is made, from the frozen hypothesis
- `59.steps` (derived in spec): Pipeline contracts, marts and rules to build, done or not done
- `59.totest` (derived in spec): Catalogue check and hypothesis check per measure
- `59.runbook` (derived in spec): Run book entries for new pipelines
- `59.risks` (derived in spec): Accepted risks that touch this change
- `59.approve` (manual in spec): Approve the design, signing change note and blueprint together
- `59.built` (manual in spec): Built, ready to test
- `59.uat` (manual in spec): UAT signature per measure
- `59.takeover` (manual in spec): Ops takeover
- `59.stop` (manual in spec): Stop the change with a reason
- `59.sigs` (automatic in spec): Signatures and send-backs listed
- `59.strip` (automatic in spec): Step and change note shown on each Build page
- `59.itsigner` (manual in spec): Who signs the infrastructure part
- `60.lenstile` (automatic in spec): Counts per lens: measures, outside range, briefs, building, proving, to consider
- `60.mine` (automatic in spec): Filter to my line of work
- `60.range` (automatic in spec): Measures outside their usual range
- `60.market` (derived in spec): Outside briefs that touch the lens measures
- `60.data` (automatic in spec): Lens measures with latest value, sparkline and owner
- `60.building` (automatic in spec): Initiatives of this lens in Build or Proving with their verdict
- `60.next` (derived in spec): Radar opportunities of this lens
- `60.lensmeasures` (confirm in spec): Lens assigned to each measure
- `60.movelens` (manual in spec): Move a measure to another lens
- `60.whatif` (automatic in spec): Lens measures ordered first in the drivers
- `60.cardstate` (automatic in spec): Context card state: draft, confirmed, changed, disputed
- `60.means` (confirm in spec): Business meaning in plain words
- `60.serves` (derived in spec): Measures a table serves
- `60.from` (derived in spec): Source, system, fields and pipeline
- `60.owner` (derived in spec): Data owner of the table
- `60.rules` (derived in spec): Quality rules and the last result
- `60.lastchange` (derived in spec): Newest change, who and why
- `60.madeby` (derived in spec): The Initiative behind the latest change
- `60.confirmcard` (manual in spec): Confirm the context card
- `60.correct` (manual in spec): Correct a card line with a reason
- `60.dispute` (manual in spec): Dispute the card with a reason
- `60.raise` (confirm in spec): Opportunity raised from a what-if, with belief, lens, evidence and baseline prefilled
- `60.raisetarget` (manual in spec): Target for the raised opportunity

### Specs with no ledger file yet (0)

none: every spec has its rows
<!-- ledger:end -->

## How to keep this current

- Every new or changed spec adds or edits its rows in `docs/product/ledger/<NN>.yaml`, in the same change, following `.sh-tmp/ic/ledger/LEDGER-BRIEF.md`.
- When a build lands that turns a typed field into a drafted one (or the reverse), update that row's `built:`; remove `built:` once the build matches the spec.
- Run `.venv/Scripts/python tools/ledger_summary.py`. It validates every row, rewrites `input_ledger.yaml`, refreshes the block above and lists specs still without a ledger file. A non-zero exit means a row is wrong; fix it in its own file.
- Claims and gaps in the prose above cite row ids. When a row id changes or a gap is closed, edit the prose in the same change.
- Never quote a minute figure as a fact. Quote the claim and cite the rows.
