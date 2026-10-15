# Harbor skills catalogue: one agent, many small skills

Harbor is the only agent a person talks to. Everything North, Span, Lumen and Tally do today is broken into **small skills**. Each skill
does one piece of work toward a milestone, proves it worked, and can be reused by any use case. Over time the library grows with every
office (industry skills) and inside each office (office skills). **The library is the moat**: it is the accumulated, tested know-how of
how family offices (and later other businesses) actually turn files into decisions, and it gets better with every client.

## 1. Four levels

| Level | What it is | Example | Who sees it |
|---|---|---|---|
| **Outcome** | What a person signs or uses | A signed intent of work; a live use case; a board | Everyone |
| **Milestone** | An ordered set of skills ending in a gate (a person's decision or an automatic check) | "Brief ready" = restate the ask, draft the goal, define each figure, draw the process, set the rules, check it can be signed | The person sees one card per milestone |
| **Skill** | One piece of work with one goal, a typed output and a check | "Define one figure" | Engineers and Trust › Skills |
| **Tool** | Plain code, no model: reads, writes, runs, checks | `t1_templates.sign_block`, `b6_run`, `e0c_load` | Nobody; skills call them |

Harbor plans with milestones, runs skills, and skills call tools. A skill never calls another skill; Harbor does the joining.

## 2. How small is a skill? (the granularity test)

A piece of work is **one skill** when all of these hold:

1. **One goal, one output.** It produces one thing with a fixed shape (one figure's definition, one table's SQL, one file's mapping). Two
   outputs of different kinds means two skills.
2. **One kind of judgement.** Understanding words, designing a structure, writing code, and explaining a difference are different
   judgements. A skill uses one.
3. **Checkable on its own.** There is a check that says right or wrong without a person (a schema, a rule, a known answer, a number that
   must add up). If it cannot be checked, it is too vague; if a person must always check it, it ends at a gate.
4. **Small enough to be fast.** It fits one focused prompt (under about 4,000 words of instructions and context) and finishes in under
   a minute on the cheapest model tier that passes its tests.
5. **Reused or repeated.** It runs for more than one use case, or many times inside one (once per figure, per file, per table). Work that
   always runs together and is never reused is merged.
6. **Parallel where it can be.** If the same work is done for N items (figures, files, tables), the skill is written for ONE item and
   Harbor runs N helpers at once.

Rule of thumb: a skill is roughly what a good analyst would do in 10 to 30 minutes and hand over on one page.

## 3. What a skill file holds

A skill is a folder `skills/<id>/` (the existing `skill_loader.py` layout, extended):

```
SKILL.md        name, goal (one line), when to use (one line Harbor reads to choose), inputs, output shape, steps,
                tools it may call, checks, never-does, model tier, version, source (core | industry | office), signed by
examples.md     two or three worked examples
traps.md        what went wrong before
tests.jsonl     known inputs with expected outputs (the answer key it must pass before it is used)
```

Harbor sees only `name + when to use` of every skill (about 60 one-liners) and loads the full folder only for the skills it runs.

## 4. How Harbor runs a use case

1. **Route** (fast model): which outcome is asked for, which milestones it needs.
2. **Plan**: the milestone's skills in dependency order; independent ones run in parallel as helpers, each holding only its own skill.
3. **Run and check**: every output passes the skill's checks and the number guard; a failed check retries once on the next model tier,
   then becomes a question to a person (never a silent failure).
4. **Gate**: the milestone ends at one of the three decisions, or an automatic check.
5. **Learn**: when a person had to step in twice for the same kind of work, Harbor drafts a new skill (`harbor.write-skill`), tests it
   on the cases it saw, and asks a person to admit it (Action centre). Admitted skills are versioned and signed.

## 5. The catalogue (63 skills: 22 are tools only and need no model, 5 are mostly tools, 24 use the fast model, 12 the strong model)

Tier: **F** fast model, **S** strong model, **T** tools only. "From" names the code it wraps today.

### 5.1 Intent (what North does today) — outcome: a signed intent of work

| Milestone | Skill id | Goal | Output | Check | Tier | From |
|---|---|---|---|---|---|---|
| Understand the ask | `intent.restate-ask` | Say back what the person wants in one line | question, readers, decisions, frequency | every part comes from the person's words or is marked "suggested" | F | i6_chat |
| | `intent.match-use-case` | Match the ask to a known use case of the pack or the office | use-case id or "new" | id exists | F | c2_offers, intent_examples |
| | `intent.read-company-doc` | Take facts from a document the person dropped | definitions, owners, systems, rules with quotes | every fact has a quote | F | i5_docs |
| Draft the brief | `intent.draft-goal` | Why it matters, who reads, what they decide, when | goal section | all five fields filled or asked | S | i6_chat |
| | `intent.list-figures` | Name the figures the answer needs | list of figure names | at least one; no duplicates | F | i6_chat (KPIs) |
| | `intent.define-figure` | Define ONE figure: meaning, formula, unit, period, owner | one figure card | formula uses only named inputs | S | i6_chat; runs once per figure |
| | `intent.name-sources` | Which systems and files hold the inputs | sources with owner and what they hold | every figure input has a source | F | catalogue_scan |
| | `intent.capture-benchmark` | What was reported last period, or "none" | per-figure benchmark | copied by code from words or a report | T+F | p4_benchmarks, g3_sheet |
| Process and decisions | `intent.draw-process-lanes` | Who takes part today | lanes | each lane is a person or system named | F | i6_chat (process map) |
| | `intent.draw-process-steps` | The steps today, in order, with hand-overs | steps and hand-overs | every step has a lane and an output | S | i6_chat |
| | `intent.map-decision-path` | Who decides what, on which threshold, and who is told | decision path | each decision has an owner and a trigger | S | new |
| Rules | `intent.set-access` | Who may see the result | access rule | names real roles | F | i4_sow governance |
| | `intent.set-retention-and-change` | How long to keep it; who approves a change | rules | both present | F | i4_sow governance |
| Ready to sign | `intent.find-gaps` | Which required parts are still empty | list | from the template, no judgement | T | t1_templates.sign_block |
| | `intent.ask-one-question` | Pick the ONE most useful question to ask next | one question | answerable in one sentence | F | new |
| | `intent.fill-with-practice` | Fill an empty part with the usual practice, marked suggested | suggested lines | every line tagged suggested | F | v3_harbor FILL |
| | `intent.sign` | Sign in the confirming person's name, keep the record | signature, version | signer = person who clicked | T | i4_sow.sign |
| | `intent.write-sop` | Standard operating procedure from the signed brief | SOP document | follows the process steps | F | k8_sop |

### 5.2 Build (what Span and Flow do today) — outcome: a live use case

| Milestone | Skill id | Goal | Output | Check | Tier | From |
|---|---|---|---|---|---|---|
| Files in | `data.recognise-file` | Which source a file is | source or question | tie asks, never guesses | T+F | v3_harbor.recognise |
| | `data.profile-file` | Columns, types, examples, row count | file profile | row count equals file | T | catalogue_scan, e0b_tools |
| | `data.read-pdf-fields` | Read the marked fields of a PDF (notice, statement) | fields with page and quote | each value quoted from the page | F | x5_extract, e2_extract |
| | `data.match-identity` | Which entity, fund or instrument a name means | id or question | one match or ask | F | e2_match |
| | `data.detect-duplicate` | Same file as before? | yes or no | hash | T | e0c_landing |
| Model | `model.find-reusable` | Which of the office's clean tables already hold this | reused tables | table exists, columns match | T+F | e0a_catalogue |
| | `model.design-ready-table` | ONE ready table for ONE figure | table spec (grain, columns, source tables) | every figure input traced | S | b10_design; once per figure |
| | `model.propose-clean-table` | A new shared clean table when none fits | proposal for a person | does not break a shared table | S | e0b_tools, b10_pack |
| | `model.propose-ontology-addition` | A new object or property this office uses | proposal | not already in the model | F | v3_model |
| Mapping | `map.map-file` | Map ONE file's columns onto the model | mapping with confidence | every target column exists | S | e0b_tools propose mapping; once per file |
| | `map.explain-doubt` | Say in plain words why a mapping is unsure | one question | answerable by a person in one click | F | v3_harbor d2 |
| Code | `build.write-ready-sql` | SQL for ONE ready table | SQL | runs on a copy; passes sqlglot guard | S | b6_span, b4_formula |
| | `build.write-formula-table` | Formula figures (returns, fee ratios) | SQL or Decimal code | matches the formula's test cases | S | b4_formula, e3_calc |
| | `build.order-and-schedule` | Order the tables and set the refresh | build plan | no cycles; schedule valid | T | b6_plan, b6_schedule |
| Run and prove | `run.load-file` | Load one file only when it adds up | loaded rows | rows in = rows out | T | e0c_load |
| | `run.on-copy` | Run the plan on a copy | run id | every step ok | T | b6_run sandbox |
| | `check.against-source` | Compare with an independent source (administrator, custodian) | per-figure checks | copied numbers only | T | b9_verify, b11 variance |
| | `check.adds-up` | Parts add up; no figure untraced; reload unchanged | checks | rules only | T | e3_recon |
| | `check.explain-difference` | Why a figure differs (timing, late notice, sweep) | one sentence with the rows | cites rows | S | b9_verify, n1_tally |
| Live | `build.write-run-book` | How it runs, who is called when it breaks | run book | names owners | F | g2_runbook |
| | `build.go-live` | Switch on the schedule, record who and when | live record | schedule set | T | p5_handover |

### 5.3 Action (what Tally does today) — outcome: an exception closed with a reason

| Milestone | Skill id | Goal | Output | Check | Tier | From |
|---|---|---|---|---|---|---|
| Notice | `action.detect-exception` | A break, shortfall, late file or limit breach | exception record | rule-based | T | e3_recon, e3_rules |
| | `action.size-impact` | How much is at stake, which reports it touches | amount, reports | numbers from rows | T | e3_impact |
| Investigate | `action.investigate` | Why it happened, from the rows and documents | finding with evidence | every claim cites a row | S | n1_tally |
| | `action.suggest-next-step` | What a person could do (ask, mark timing, correct) | 2 or 3 options | none moves money | F | n1_tally |
| | `action.draft-message` | Draft the email to the administrator or manager | draft, never sent | needs a person's OK | F | n1_tally |
| Route | `action.route-owner` | Who should act, by when | owner and due | owner has the role | T | p2_assign, e4_cases |
| | `action.close-with-reason` | Close with the reason recorded | closed case | reason present | T | e4_cases |

### 5.4 Consume (what Lumen does today) — outcome: an answer, a board, a note

| Milestone | Skill id | Goal | Output | Check | Tier | From |
|---|---|---|---|---|---|---|
| Answer | `consume.understand-words` | Turn the office's words into model terms ("dry powder" = uncalled) | terms | from the language list | T+F | v3_model language |
| | `consume.answer-from-cache` | Same question on the same data: return the cached answer | answer or miss | data version unchanged | T | read_cache |
| | `consume.answer-question` | Answer from the ready tables | figure, chart, sentence | number guard; every figure traced | F | talk, cx_lumen |
| | `consume.explain-number` | Where a number is from | file → run → table → definition | from records only | T | a5_trail |
| | `consume.precompute-golden` | After each run, answer the most-asked questions ahead | cached answers | same as answer-question | T+F | read_cache |
| Boards | `consume.choose-chart` | Three ways to show one figure | options | from the table's columns | T | b7o_options |
| | `consume.check-chart` | Is the chart honest (no double counting, right scale) | checks | rules only | T | b7k_checks |
| | `consume.build-board` | A board from the brief's figures | tiles | every tile has data | F | b7_studio, v3_harbor c_lumen |
| | `consume.read-sketch` | A paper sketch into a board | tiles | each box matched to a table | F | b7s_sketch |
| Reports | `consume.write-morning-note` | The note: headline, 3 points, who must decide | note | figures from the run | F | k10_note |
| | `consume.make-monthly-pack` | The month-end pack, PDF and Excel | files | matches the issued report | T | e1_reports, exports |
| | `consume.attribution` | Why returns moved (allocation, selection) | attribution table | adds up to the active return | T | k11_attrib |

### 5.5 Knowledge and Harbor itself

| Skill id | Goal | Output | Check | Tier | From |
|---|---|---|---|---|---|
| `knowledge.update-company-map` | Add what was just built to the company's graph | nodes and links | from records only | T | m1_map, k3_onto |
| `knowledge.learn-word` | A new word the office uses, proposed for the language list | proposal | not already listed | F | v3_model |
| `harbor.route` | Which outcome and milestones a request needs | plan | known milestones only | F | v3_harbor |
| `harbor.write-skill` | Draft a new skill from repeated human steps | SKILL.md + tests | passes its own tests | S | new |
| `harbor.test-skill` | Run a skill on its known answers | pass / fail per case | all cases run | T | new |

### 5.6 Office skills (written by Harbor, admitted by a person) — examples
`office.read-cedarpoint-notice`, `office.eg-b-sweep-is-transfer`, `office.fee-check-side-letter`. These are the ones nobody else has.

## 6. Why this is the moat
- Every client adds tested skills; the industry library improves for the next family office without moving any client data
  (skills hold method, never figures).
- Every skill has an answer key, so quality is measurable and can only go up.
- The office's own skills capture how that office works; switching away means losing them.

## 7. What it takes to build (after approval)
1. Skill store: `skills/<id>/` with SKILL.md fields above; Trust › Skills reads it; office skills in the company plane (loader exists).
2. Harbor runtime: route → plan → run helpers in parallel → check → gate; one run log row per skill call (run_log exists).
3. Convert North, Span, Lumen, Tally prompts and tools into the skills above (most tools exist; about 15 skills are new code).
4. Answer cache and golden pre-compute for Consume.
5. `harbor.write-skill` and the admit flow in the Action centre.
