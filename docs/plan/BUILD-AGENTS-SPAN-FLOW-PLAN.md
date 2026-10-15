# Build agents: Span and Flow (plan, 7 Oct 2026)

Two model-backed agents come back into the Build centre: **Span**, the solution architect (rooms 0 and 1), and **Flow**, the data engineer (rooms 2 and 3). They replace the deterministic "Architect" and "Builder" on screen. The rule-based drafts that exist today stay as the fallback. This is a planning document. It changes no code. Cards are in section 4.

Sources read for this plan: CLAUDE.md; `.claude/rules/` reuse-first, egress, contracts, testing, house-style, ui-copy, modules; `docs/decisions.md` (D-003, D-036, A-005, A-009); `docs/reuse-inventory.md` module 4; `docs/reuse-audit-2026-10-06.md` BC-3; spec 59; `.sh-tmp/ic/RULINGS-BUILD.md` (R14, R16); `sh_platform/agents/*`, `sh_platform/build/*`, `sh_platform/intents/north.py`, `lens.py`, `modules/m3_connect/agent/*`, `sh_platform/egress/gateway.py`, `sh_platform/memory/*`, `sh_platform/consume/market.py`; the Build pages in `ui/src/pages`; and in EARLIER every file the brief names (line ranges are in section 2). There are two later requirements from Nitin: (A) Span learns modelling techniques and suggests changes, and (B) Span writes a full design document in the Archify style, in two steps.

---

## 0. Decisions taken (each one can be reversed)

| # | Decision | How to reverse |
|---|---|---|
| S1 | The names are **Span** (solution architect, rooms 0 and 1) and **Flow** (data engineer, rooms 2 and 3). On screen, Span replaces "Architect" and Flow replaces "Builder". Prover and Watcher keep their names. This answers spec 59 open question 6. | Names live in `sh_platform/build/agents/runtime.py` (`SPAN`, `FLOW`) and the copy files. Change those strings. |
| S2 | Signatures stay with today's signers. No new user roles; A-005 stands. The head of department, or a company admin when no change note is open, signs the blueprint and the design document in one act. The sponsor signs the release. The tester signs UAT. | Edit the sign hooks in `chain.py` `/approve` and `blueprint.py` sign. |
| S3 | Agents draft, people sign. No agent signs, approves, runs a pipeline, changes a contract or applies a suggestion. | Not reversible within this brief. |
| S4 | Every model call goes through the egress gateway (`run_agent`, then `EgressModelClient`, then `EgressGateway`). Names are tokenised. Only counts over groups of five or more, field names and the company's own definition text leave. Rows and sample values never leave. | Not reversible (egress.md). |
| S5 | The R14 pattern applies. When the model call fails, the existing rule-based draft stands (`blueprint_draft.draft`, `chain._draft`, the runner's rule counts), and the screen says so in one sentence. | Remove the fallback branch in each agent file. |
| S6 | A draft never overwrites a human edit. A blueprint path whose provenance mark is `stated`, a change note line, a design document line or a spec part marked `stated` is kept as it is. A draft is recorded beside it. | Rule 7 of CLAUDE.md. Not reversible. |
| S7 | Span and Flow talk to each other only through "propose a change, a person approves". There is no agent-to-agent chat. | Add an ask-teammate tool later (earlier `agent_brain.py` `ask_teammate`). |
| S8 | Build is kernel code in `sh_platform/build/`, not a module folder (the catalogue lists `m4_build` with no manifest; the Build centre has "no modules yet"). The agents follow the North and Lens split instead of `build-a-module`. The agent identity, rules yaml and context builders sit in `sh_platform/build/agents/`; the routes and stores sit in `sh_platform/build/`. `MODULE_ID = "m4_build"` is used for the entitlement gate and the run log. | Move to `modules/m4_build/` when Build gets a manifest. The files move as they are. |
| S9 | Picture-to-diagram is **out of scope**. The gateway only takes string message content (`gateway.py` `_check_structure` L117-L119), and egress.md says a picture never leaves the machine. | It needs a gateway change and a decision from Nitin (section 5, Q4). |
| S10 | The design document has two steps. Step 1 is plain standalone HTML with the diagrams inline as SVG, in waves 1 to 3. Step 2 renders the same content in the Archify look, in wave 4. The structure lives in a template file Span fills, so the look can change without touching Span. | Skip wave 4. |

Shared files a card may edit are named in that card's OWNS list. The orchestrator makes edits to permission files, manifests, `.claude/rules/*`, `catalogue.yaml`, `docs/decisions.md` and dependency files. Section 3.8 lists them.

---

## 1. Purpose and the user journey

### Purpose

Today an Initiative handed to Build meets an Architect that fills the blueprint from rules (`blueprint_draft.py` L132, "No model call") and a Builder that is just the runner. Nobody explains a failed run in plain words. Nobody suggests a better model, and the architecture is a component table, not a design. Span and Flow add judgement where rules cannot reach, behind the same gates. Span reads what the Intent Centre handed over, drafts the target architecture, the silver model, the gold contract and a design document, builds the model in a sandbox before anyone sees it, and suggests modelling changes to the data team. Flow builds bronze, silver and gold from signed contracts, explains every run and every row that failed a check, drafts the SQL for the company's own warehouse when one is named, and looks at data incidents with Watch. A named person signs every result.

### The journey (Ardmore example: "Valuation chase protocol", Janet organiser, Daniel sponsor, Aaron architect, Grace head of department, Katie developer, Mei Ling tester, Harvey ops)

**Room 0, gap analysis** (`/centre/build/gap-analysis?from=<id>`, `GapAnalysisRoom`)
1. Janet presses "Hand to Build" (33). Under R16, room 0 receives the signed charter, the catalogue, the processes and the source map, with each source's quadrant and strategic flag (`source_map.read_map`, masked per viewer).
2. Span reads the hand-off through its read tools. It sees source names as tokens, quadrants, strategic flags, measure codes and names, process names, and counts. From these it drafts the **target architecture**: which sources load, into which layer, which marts serve which measure, and where the restricted file and the read-only copy sit. The draft is an Archify spec ("target") beside today's record ("current"), plus the first sections of the design document (purpose and scope, context from the charter, current state, target architecture). Each line is marked guessed and names the record it came from.
3. The room 0 card reads "Span's suggestion: target architecture" and shows the diagram and three lines of why. If the model call failed, the card shows the rule-based projection (`architecture.project`) with "Span could not reach the model. This is the rule-based draft."
4. Katie runs the gap analysis and Daniel signs the gap report as today (module 3). The change note opens (`chain.ensure`).

**Room 1, blueprint** (`/centre/build/blueprint`)
5. Span drafts the **silver model** (facts, dimensions, grain, keys, slowly changing type per dimension) and the **gold contract** (one mart per measure, with its transform). It chooses a modelling technique from its knowledge pack and the company's own past decisions in memory, and says why.
6. **Sandbox and repair.** The server builds the draft in a scratch DuckDB file (`warehouse/sandbox/<draft>.duckdb`) from the company's bronze tables. It checks that every name exists, the keys are unique and each measure computes for at least one period. Failures go back to Span as scrubbed error lines (column names and error kinds only, no values), for at most three rounds (Q6). A draft that builds is **filed for signature**: it is merged into the blueprint draft as `guessed` by Span, and every `stated` path is kept. A draft that still fails is kept with its errors and offered to the architect as "Span could not make this build", with the errors in plain words.
7. **Decision records.** Each placement in the change note's "Decision and alternatives" section carries at least two options, the choice, why and what follows (the earlier `architecture_drafting` shape). Span writes the why. The options and their checks stay deterministic.
8. **Reference citations** (only when the company has internet switched on for Build, D-006). Span may search published guidance through `gateway.internet_query` with a public-terms query. Results come back marked as outside material. A recommendation that cites a passage is kept only when the passage exists (the earlier `reference_arch.verify`). With internet off, the tool is not listed and nothing is said about it.
9. **Design document (step 1).** Span fills the design document template section by section (3.6). The diagrams are Archify specs for current state, target state and the delta, validated before they are rendered and drawn inline as SVG. Room 1 shows the document and offers "Download the design document". Aaron edits a guessed line, which becomes stated. He presses "Send for approval" on the change note. Grace approves the design on the change note, which signs the blueprint version and the design document version together. Both are then read-only. The next change starts a new version beside them.
10. **Span's suggestions to the data team** (requirement A). In room 1, Span reviews the current silver model, the gold contracts, the catalogue grain and the source map, and files suggestions. For example: "Keep the history of fund manager changes: slowly changing type 2 on the fund dimension. 214 of 1,180 fund rows changed manager in the last 12 loads (counts from the run log). Two marts read it. Effort: small." Each suggestion goes to one named person: the measure's data owner, or else the person who signed the blueprint. They accept it, decline it with a reason, or ask a question. An accepted suggestion opens a change note through the chain, labelled "from Span's suggestion P-0003". When the change alters a contract, Flow tells the developer to rerun that pipeline. Suggestions are labelled "Span's suggestion" and are never applied by the agent.

**Room 2, pipelines** (`/centre/build/pipelines`)
11. Contracts come from the signed blueprint (`contracts.ensure`, unchanged). Katie drops a file and presses Run, as today.
12. After each run, Flow writes **the run in plain words**: what landed, how many rows loaded, which checks failed, and how many rows went to the quarantine table and why (rule and field names, counts). The quarantine table stays in the plane and nothing from it leaves. Its fallback is the deterministic lines built from the run log.
13. **Warehouse SQL.** When the company names a warehouse target in the environment check (new answer `warehouse_target`), the server transpiles the runner's DuckDB SQL with sqlglot (deterministic, no model). Flow explains the differences in plain words. The page shows "SQL for your warehouse" with a download, marked as a draft. Nothing is pushed anywhere; the cloud push is BC-8 and stays out of scope.
14. If a failure points at the model (a grain that is not unique, a type that does not fit), Flow files a `model_change` proposal addressed to the blueprint signer, naming Span as the drafter of the fix (S7).

**Room 3, ops** (`/centre/build/ops`)
15. Watch raises alerts as today (`ops.build`, `alerts.py`). For a data alert (failed checks, out of range, late file), Flow adds an **incident note**: the likely cause in plain words, from the run log and the rule counts, and a suggested next step ("Ask the custodian for the 2026-08 file again"). The ops person or the developer acknowledges the alert with the note, or edits it. Flow never closes an alert.

### What each person sees, by state (every screen covers loading, empty, error, refused and populated)

| Element | Empty | Fallback (model failed) | Refused |
|---|---|---|---|
| Span target card (room 0) | "Span drafts the target architecture once an Initiative is handed to Build." | "Span could not reach the model. This is the rule-based draft." | Hidden (route gate) |
| Span model draft (room 1) | "Span drafts the model once the baseline is signed." | Same sentence, with the blueprint's rule-based model shown | "You cannot ask Span for a draft." |
| Suggestions (room 1) | "Span has no suggestions right now." | "Span could not review the model just now. Try again later." | Read only |
| Design document (room 1) | "Span drafts the design document after the gap report is signed." | Template filled from records only, with the same sentence | Read only |
| Flow run note (room 2) | "Flow explains each run after it finishes." | Deterministic lines, with "Flow could not reach the model. These lines come from the run log." | Hidden |
| Flow incident note (room 3) | Hidden when no data alert is open | Deterministic cause line | Hidden |

---

## 2. Reuse check

Searches run on 7 Oct 2026. In CURRENT: Grep for `quarantin` over `sh_platform` (0 hits); `kimball|data vault|slowly changing` over the repo outside worktrees (only `blueprint.py` L137 "Slowly changing type is 1 or 2", `BUILD-CENTRE-SPEC.md` L41 and a ledger copy); `sqlglot` (installed 30.8.0, imported nowhere, not in `requirements.txt`); `jsonschema` (installed 4.26.0, not declared); `internet_query` (`sh_platform/consume/market.py` L91); `outside=True` (the registry flag exists, no tool sets it); `image|vision` in `sh_platform/egress` (only `vault.py` L36). In EARLIER: Grep for `data vault|slowly changing|bus matrix` (only `catalogue_chat.py` L166-L175, SCD 1 or 2 capture, and the reference topic line `reference_arch.py` L106); skeletons of every file named in the brief; `agents/gates.py` L39-L44 for the Span and Flow personas.

### 2.1 EARLIER, file by file

| Capability | EARLIER file and lines | Decision | Lands in CURRENT |
|---|---|---|---|
| Span and Flow personas | `agents/gates.py` L42-L50 (Span "Solution architect", Flow "Data engineer") | **Copy** the names and subtitles | `sh_platform/build/agents/runtime.py` constants |
| Journey and gates G0-G5 | `agents/gates.py` L101-L200 | **Not used**: CURRENT has the five-step chain (spec 59, `chain.py`) and its signatures | n/a |
| Span skill | `agents/skills/architect.md` (all 66 lines) | **Reshape**: keep "what you cannot do", "the KPIs decide the model", "say the trade-off". Drop the earlier tool names, Approvals screen and step numbers. Add the CURRENT tool names | `sh_platform/build/agents/span_rules.yaml` |
| Flow skill | `agents/skills/engineer.md` (all 54 lines) | **Reshape**: keep the "check the chain in order" rule (contract, bronze, silver, gold), "a quarantine has a reason" and "never say data is loaded unless the records say so". Drop the remote-warehouse timings | `sh_platform/build/agents/flow_rules.yaml` |
| Skill file rules | `agents/skills/README.md` L1-L16 | **Copy** the editing rules as the header comment of both rules yaml files | as above |
| Agent descriptions | `emitters/agent_brain.py` L163-L222 (`AGENT_SLUGS` architect, engineer) | **Copy** the two descriptions into the yaml `role` lines | rules yaml |
| Per-agent tool lists | `agent_brain.py` L423-L434 (`AGENT_ONLY_TOOLS`), L1227-L1247 (tool list per slug); `agents/policy.py` L115-L140 (`_BASE_POLICY`) | **Reshape**: one explicit list per agent, registered under `m4_build` with agent-scoped names (`span.*`, `flow.*`). No policy table | `sh_platform/build/agents/read_tools.py` |
| propose_change | `agent_brain.py` L964-L1018 (inside the 853-1110 range: `propose_change`, `answer_value_interrogation`) | **Reshape**: in the loop, a propose call only collects (a sink). The caller validates and files it after the run. The value interrogation is not used: our fields (what, why, evidence, impact, alternatives, effort) cover it | `sh_platform/agents/registry.py`, `loop.py`, `sh_platform/build/proposals.py` |
| Proposal kinds and checks | `emitters/proposals.py` L1-L30 (doc), L57 (`STATUSES`), L115-L133 (`_req`), L385-L414 (`validate`) | **Reshape**: a closed `KINDS` list with a schema per kind. JSON files in the plane, not a DuckDB control table | `sh_platform/build/proposals.py` |
| search_reference_architectures | `agent_brain.py` L1038-L1068 | **Reshape**: one outside tool through `gateway.internet_query` (the `consume/market.py` L91 pattern), listed only when internet is on | `read_tools.py` (`span.search_reference`) |
| start/get_model_draft | `agent_brain.py` L1082-L1110 | **Reshape** into routes: Span is asked from the screen, not from chat | `sh_platform/build/agents/routes.py` |
| Model draft loop | `emitters/model_drafting.py` L703-L808 (`run_draft`: rounds, normalise, check, sandbox, repair) | **Copy** the loop shape. **Reshape**: each round is one `run_agent` call through the gateway, not `_call_model` (L268) with a direct provider. No room posts (L694). No target confirmation (L674) | `sh_platform/build/agents/span_model.py` |
| Format guide | `model_drafting.py` L121-L242 (`FORMAT_GUIDE`) | **Reshape**: keep the silver and gold JSON shapes and the "only names that exist" rule. Drop dashboards and attribution. **Drop the profiled sample values** that `gather_inputs` L78-L120 sends (that breaks S4) | `span_rules.yaml` `model_format` |
| Normalise and check | `model_drafting.py` L295-L400 (`_free_surrogate_name`, `normalise`), L400-L525 (`_known_refs`, `check`) | **Copy**, then remove the dashboard checks | `sh_platform/build/model_build.py` |
| Sandbox build | `model_drafting.py` L525-L638 (`sandbox_build`) | **Reshape**: a scratch DuckDB file per draft with bronze attached read-only. No dashboards. Errors scrubbed of values before they reach the model | `model_build.py` |
| SCD1, SCD2, fact build | `emitters/silver_transform.py` L109-L135 (scd1), L135-L171 (scd2, merge hash on tracked attributes only), L324-L333 (fact) | **Copy** into the sandbox engine. CURRENT `transforms.build_silver` stays the production silver path until a signed model asks for SCD2 (Q7) | `model_build.py` |
| Gold mart from contract | `emitters/gold_transform.py` L214-L253 (`_aggregate_fact`), L268-L355 (`build_mart`) | **Reshape** to the one CURRENT gold shape (`period`, `value`; `transforms.build_mart` L36). Cross-fact metrics are kept as a ponytail ceiling | `model_build.py` |
| Decision with alternatives | `emitters/architecture_drafting.py` L95-L135 (format), L163-L232 (`parse_decision`, `normalise`, `check`) | **Copy** `normalise` and `check` (at least two options; every cited reference exists). The prompt is reshaped | `sh_platform/build/agents/span_design.py` |
| Architecture record capture and consistency | `emitters/architecture.py` L53-L73, L125-L176 | **Reshape**: `check_consistency` becomes the design document's "Consistency" lines. Capture is **not used**: CURRENT has the record (`build/architecture.py`) | `span_design.py` |
| Image interpretation | `architecture.py` L74-L117 (`interpret_architecture_image`, vision call) | **Not used** (S9) | n/a |
| Reference corpus | `emitters/reference_arch.py` L157-L329 (fetch, extract, chunk, embed, refresh) | **Not used**: it needs a crawler and an embedding store outside the plane. An on-demand gateway query is enough | n/a |
| Citation check | `reference_arch.py` L439-L568 (`_norm`, `_named_terms`, `_unsupported_terms`, `verify`) | **Copy** | `span_design.py` |
| Advice prompt | `reference_arch.py` L420-L437 | **Reshape**: no vendor or cloud names, outside-material marker | `span_rules.yaml` `cite` |
| Background build | `emitters/pipeline_build.py` L83-L165 | **Not used**: CURRENT runs one source at a time (`runner.run_pipeline` L113) and the page reloads the run log | n/a |
| Quarantine | `emitters/bronze_loader.py` L487-L497 (`_quarantine_batch` copies files or dumps a JSON snapshot) | **Reshape**: offending rows of a block rule go to a plane table `quarantine.<source>`. No file dumps, no snapshot, never sent anywhere | `sh_platform/build/runner.py`, `transforms.py` |
| Quality rules | `bronze_loader.py` L424-L486 | **Not used**: CURRENT `transforms.check_rule` L59 covers non-empty, unique and range | n/a |
| SQL dialect | `emitters/sql_dialect.py` L165-L235 (`SqlConnection`, sqlglot transpile) | **Reshape**: transpile only (`sqlglot.transpile(sql, read="duckdb", write=<dialect>)`). No connection | `sh_platform/build/dialect.py` |
| Remote warehouse credits and connect | `sql_dialect.py` L61-L163, L272-L333 | **Not used**: no push in this plan (BC-8) | n/a |
| Model draft routes | `webapp/backend/routers/pipeline_routes.py` L51-L98 | **Reshape** to `/api/company/build/span/model-draft` | `routes.py` |
| Build routes | `pipeline_routes.py` L99-L134 | **Not used** (CURRENT runner routes) | n/a |
| Advice routes | `routers/architecture_routes.py` L41-L82 | **Reshape**: citations come inside Span's draft, so there is no separate advice store | `span_design.py` |
| Architecture CRUD and interpret-image | `architecture_routes.py` L83-L159 | **Not used** (CURRENT `architecture.py` routes; S9) | n/a |
| Data architect charter | `.claude/agents/data-architect.md` (28 lines: Kimball star by default, SCD per attribute, say why) | **Reshape** as the seed of the modelling pack. The rest of the pack is new | `sh_platform/build/agents/modelling_pack.yaml` |
| Solution architect charter | `.claude/agents/solution-architect.md` (23 lines) | **Reshape** into `span_rules.yaml` `role` | rules yaml |
| Bronze, silver and gold engineer charters | `.claude/agents/de-bronze.md`, `de-silver.md`, `de-gold.md` | **Reshape**: one line per layer duty in `flow_rules.yaml` | rules yaml |

### 2.2 CURRENT, reused as it is or reshaped

| CURRENT | Where | Decision |
|---|---|---|
| Agent loop, guard, run log | `sh_platform/agents/loop.py` `run_agent` L44, `guard.check_numbers`, `runs.RunRegistry` | Reused. The loop gains a proposals sink (SF01) |
| Registry | `registry.py` `register` L39-L46 refuses anything not read-only | Reshaped: a `proposes=True` tool may register. It only appends to the run's sink (SF01) |
| Model client set-up | `modules/m3_connect/agent/compile.py` `get_model` L34-L44, `register_names` L47-L55; `intents/lens.py` `Runtime` L66-L97 | Copied (not imported: kernel code must not import a module) into `sh_platform/build/agents/runtime.py` |
| JSON reply and retry once | `compile.py` `_parse` L58, `ask` L67-L80, `compile_rule` L83 | Pattern copied for Span's JSON drafts: invalid once, retry with the reason, then fallback |
| Rule-based drafts (fallbacks) | `blueprint_draft.draft` L132; `chain._draft` L218-L285; `architecture.project` L78 | Reused unchanged as the R14 fallback |
| Blueprint store and provenance | `blueprint.py` PUT L160-L196 (`stated` mark, signed kept as `blueprint.v<n>.json`), sign L199-L226 | Reused. Span's file step writes `guessed` paths only. The sign hook also signs the design version (SF13) |
| Chain | `chain.py` `_open` L185, `/approve` L647-L693, `pulse_lines` L792, `install` L836 | Reshaped: `open_from_proposal` (SF02), screen words Architect to Span (SF02), design sign and router install (SF13) |
| Architecture record and spec | `architecture.py` `read` L163, `spec` L250-L265, `masked` L274, `svg` L297 ("C24: no renderer bundled") | Reused. `archify_spec.py` builds current, target and delta specs on top and adds boundaries |
| Archify spec shape | `docs/architecture/sh-m4-build.json`, `sh-agent-egress.json` and their HTML | Shape copied. `sh-agent-egress.html` and `sh-m4-build.html` are the reference look for step 2 |
| Archify schema and template | `~/.claude/skills/archify/schemas/architecture.schema.json`, `common.schema.json`, `assets/template.html` (MIT, "Copyright (c) 2026 tt-a1i (Archify)") | Copied into `sh_platform/build/archify/` with the licence notice. The node CLI stays a development tool outside the product (C24) |
| Internet query | `sh_platform/consume/market.py` L91 `gateway.internet_query` | Pattern copied for `span.search_reference` |
| Memory | `sh_platform/memory/__init__.py` `AGENTS` L13, `remember` L61, `for_prompt` L119; `api.py` `AGENTS` L19, `tomb_hash` L47 (tombstones) | Reshaped: `AGENTS` gains `span` and `flow`. A company decision is checked against tombstones before it is written |
| Events | `sh_platform/intents/events.py` `append_event` L139; agent check L150-L154 (only North or Lens may draft) | Reshaped: `span` and `flow` may write draft lines of their own kinds (SF02) |
| Pulse | `sh_platform/pulse/intent_lines.py` L406-L411 (chain block); `pulse/lines.line` L73 | One more block for proposals, design and Flow lines (SF13) |
| Knowledge map moments | `graph/knowledge_map.py` `MOMENTS` L21 (`blueprint_signed`, `release`), `try_moment` L334 | Reused; no new moment. The design document is signed in the blueprint moment |
| Environment check | `sh_platform/build_env.py` `QUESTIONS` L17 | Reshaped: new question `warehouse_target` (SF07) |

### 2.3 Genuinely new

The proposals sink and store; the modelling knowledge pack and Span's decision memory; Span's suggestion engine; the sandbox engine file (copied parts plus value scrubbing); the quarantine table; current, target and delta Archify specs with boundaries and schema validation; the design document template, store, versions and renderers (step 1 plain, step 2 Archify look); the dialect file; Flow's run and incident notes; the screens' Span and Flow panels.

---

## 3. Architecture

### 3.1 Where the agents live

```
sh_platform/build/agents/
  __init__.py
  runtime.py            SPAN="Span", FLOW="Flow", MODULE_ID="m4_build"; Runtime (model, gate, company); get_model; register_names
  read_tools.py         registry builders: span_registry(plane, rt), flow_registry(plane, rt); read tools + the propose sink
  modelling_pack.yaml   requirement A: techniques and when each fits (industry-neutral, read by Span, not code)
  modelling.py          load the pack, pick the passages for a question, company decision memory (write, read, tombstones)
  span_rules.yaml       role, rules, prompts: target, model_format, repair, suggest, design, cite
  span_model.py         silver model + gold contract draft, sandbox repair loop, file for signature
  span_suggest.py       review and suggestions (requirement A)
  span_design.py        room 0 target, decision records, citations, design document content, Archify spec draft
  flow_rules.yaml       role, rules, prompts: run, incident, dialect
  flow.py               run notes, quarantine explanation, incident notes, dialect explanation, model_change proposals
  routes.py             all Span and Flow routes (one router)
  design_template.yaml  the design document structure (sections, order, sources, which agent prompt fills each)
sh_platform/build/
  proposals.py          proposal store, closed kinds, accept/decline/ask, routes, Pulse lines
  model_build.py        sandbox engine (copied from EARLIER), error scrub
  archify_spec.py       current/target/delta specs, boundaries, validation, svg with boundaries
  archify/              architecture.schema.json, common.schema.json, template.html (step 2), LICENCE-ARCHIFY.txt
  design_doc.py         design versions, fill from records (fallback), plain HTML render (step 1)
  design_html.py        step 2: Archify-look render (wave 4)
  dialect.py            sqlglot transpile of the runner's SQL for the stated warehouse target
```

This mirrors North (`modules/m1_intent/agent/north.py` holds identity and prompts, `sh_platform/intents/north.py` holds state and routes) and Lens (`modules/m2_baseline/agent/lens.py` plus `sh_platform/intents/lens.py` `draft_for`). Every model call is `run_agent(rt.model, registry, company_id, "m4_build", agent, system, context, question, recorder=RunRegistry(plane))`. The gate is the entitlements gate from the request. A background draft uses Lens's `_OpenGate` pattern, because the route that started it already checked entitlement (lens.py L58-L63).

**Long drafts.** The model draft and the design document run in a background thread, as the earlier `start_draft` (`model_drafting.py` L895) did. The record carries `state: drafting` and `claimed_at`, and a claim older than 300 seconds counts as failed (Lens `STALE_AFTER` L46, `is_stale` L180). The page polls the GET route.

### 3.2 Tools per agent

Every tool returns a summary that passes `registry._summary_only`: counts carry `group_size` of 5 or more, lists stay at 50 items or fewer, and there are no `rows` or `records` keys.

| Tool | Agent | Kind | Returns |
|---|---|---|---|
| `span.read_handoff(intent_id)` | Span | read | charter title and question; measures `[{code, name, grain_text}]`; processes `[{name}]`; sources `[{name, quadrant, strategic}]` (R16, `source_map.read_map`, masked per viewer) |
| `span.read_model()` | Span | read | blueprint `model` (facts, dimensions: names, grain, keys, scd), `lineage` (measure, source, fields, transform), with the provenance mark per path |
| `span.read_contracts()` | Span, Flow | read | per source: `fields [{name, type}]`, `marts`, `rules`, `depends_on`, `expected`, `sla` |
| `span.read_profile(source)` | Span | read | `{group_size: rows, rows, fields: [{name, type, nulls, distinct}]}`, all over the whole table (group_size = row count). None when rows are under 5 |
| `span.read_change_rate(source, key)` | Span | read | `{group_size: keys, keys, keys_changed_last_n_loads, loads}` from `bronze` load ids. Evidence for slowly changing suggestions |
| `span.read_architecture(view)` | Span | read | record components `[{id, kind, view, state, restricted}]` (labels masked) |
| `span.read_decisions(topic)` | Span | read | company decision memory entries for this topic (text, date). Never people's names (`memory.filters.depersonalise`) |
| `span.read_pack(topic)` | Span | read | the modelling pack passages for a topic (3.5) |
| `span.read_queries()` | Span | read | query patterns: which marts each measure and dashboard reads, counted from the blueprint lineage and the map's consume nodes. Names and counts only |
| `span.search_reference(query)` | Span | read, **outside** | gateway internet query to an allowlisted destination. Listed only when internet is on for `m4_build`. Wrapped in `OUTSIDE_MARKER` by the loop |
| `flow.read_runs(source)` | Flow | read | last 10 runs: `status, on_time, schema_ok, rows (group_size rows), rules [{rule, passed, count}], not_run, notes` |
| `flow.read_quarantine(source)` | Flow | read | `{group_size: rows, by_rule: [{rule, field, count, group_size}]}`. A count under 5 reads "fewer than five" |
| `flow.read_alerts()` | Flow | read | open alerts `[{id, kind, source, since}]` |
| `flow.read_dialect(target)` | Flow | read | `{dialect, statements: [{name, changed_constructs: [str]}]}` from `dialect.py`. No SQL text with literals |
| `span.propose` / `flow.propose` | both | **propose** | appends one proposal to the run's sink. The caller validates and files it (3.3) |

### 3.3 The one new kind of tool: propose a change, a person approves

**Shape.** `ToolRegistry.register(..., read_only=False, proposes=True)` is allowed only with `proposes=True`. When the model calls it, the registry does not run arbitrary code. It checks the arguments against the kind's schema (`proposals.KINDS[kind]`), then appends `{kind, args}` to `AgentResult.proposals` and returns `{"filed": "waiting for a person"}`. Nothing is written during the loop. After `run_agent` returns, the calling engine (`span_suggest.py`, `flow.py`) calls `proposals.file(plane, agent, items, run_meta)`. That call re-validates each item, drops any whose numbers failed the guard, removes duplicates of open proposals (same kind, same target and same `what`), caps the run at three, and writes `build/proposals/P-<n>.json`.

**Closed kinds.**

| Kind | From | Addressed to | On accept |
|---|---|---|---|
| `model_change` | Span; Flow (naming Span) | the measure's data owner (catalogue governance), else the blueprint signer | `chain.open_from_proposal`: a change note marked `from: P-<n>`, Span redrafts its sections, and the normal five steps follow |
| `architecture_decision` | Span | the architect role on the change note | the decision line is added to the change note's decisions as `stated` by the accepter |
| `incident_note` | Flow | the alert's `tell` person (`chain.alert_fields`) | the alert is acknowledged with the note (`alerts.act`), by the accepter |

**Proposal record** (`build/proposals/P-0003.json`):
```
{id, kind, by_agent: "Span"|"Flow", to: person name, to_role, intent_id|null, change_id|null,
 title, what, technique|null, why, evidence: {counts: [{label, value, group_size}], fields: [str], queries: [str]},
 impact: {contracts: [path], marts: [str], dashboards: [str]}, alternatives: [{option, why_not}], effort: "small"|"medium"|"large",
 cites: [{source, passage_id}], state: "proposed"|"accepted"|"declined"|"asked"|"superseded",
 thread: [{by, text, at}], decided: {by, at, reason}|null, run_id, created_at}
```

**Security review the propose tool needs** (card SF14):
1. The agent cannot apply anything. Only `POST /api/company/build/proposals/{pid}/accept` applies, under the person's name, after it re-checks that the person is the addressee (`chain.may_act` pattern) and that the target is still in the state the proposal saw. A signed record is never touched; accepting always opens a new draft.
2. The author is never the approver. An agent has no account. A person who triggered the run may still accept, because the addressee is fixed by role, not by who asked.
3. Kinds and arguments are a closed list. Unknown keys are refused. The `what` and `why` fields are capped at 2,000 characters. Evidence must be `{label, value, group_size}` facts with group_size of 5 or more, or field names. A number that does not trace to this run's tool facts makes the item invalid.
4. Prompt injection: a run that called an outside tool marks its proposals `outside_seen: true`, and the screen says "Span read outside material for this". Outside text can never pick the addressee or the kind's target.
5. Flooding: three per run, one open proposal per (kind, target), and a daily cap per company (Q5).
6. Cross-company: the store resolves through `plane` only, and an id is matched with `^P-\d{4,6}$` before any path is built.
7. Rows: the gateway already refuses raw rows and suppressed figures. The proposal file holds the same summaries, so it can be shown to the addressee without a further mask, except a restricted measure, whose proposal follows the measure's access list (`blueprint._hidden` pattern).
8. Logging: `RunRegistry` records the run (no text). The proposal file records the run id.

### 3.4 Gateway payload shapes (counts and field names only, never rows)

Each payload is what `run_agent` puts in the user message: `{"context": ..., "question": ...}`. The gateway tokenises names and refuses rows and small groups. Examples:

**Span, target architecture (room 0)**
```
{"context": {"company": "COMPANY_01", "industry": "family office",
  "charter": {"title": "Valuation chase protocol", "question": "..."},
  "measures": [{"code": "K12", "name": "Stale private fund valuations", "grain_text": "one row per fund per month"}],
  "processes": [{"name": "Monthly valuation chase"}],
  "sources": [{"name": "ORG_03 statements", "quadrant": "high impact, low readiness", "strategic": true}],
  "current": {"components": [{"id": "gold:k07", "kind": "gold", "state": "live"}]},
  "facts": []},
 "question": "Draft the target architecture as JSON: components, interfaces, placements with two options each."}
```

**Span, model draft round**
```
{"context": {"measures": [...as above, plus "technical_definition": "<the signed text>"],
  "sources": [{"name": "ORG_03 statements", "fields": [{"name": "fund_id", "type": "bigint"}, ...]}],
  "facts": [{"label": "ORG_03 statements rows", "value": 1180, "group_size": 1180},
            {"label": "fund_id distinct", "value": 236, "group_size": 1180}],
  "pack": "<two or three passages from modelling_pack.yaml>", "decisions": ["Company chose type 2 history on the fund dimension (2026-09)"],
  "previous": {...last plan...}, "errors": ["fact_valuation: grain fund_id, period_end is not unique (duplicates exist)"]},
 "question": "Write the silver model and the gold contract as one JSON object."}
```
Errors go through `model_build.scrub`: quoted literals, numbers that are not column positions, and anything after "value" are removed. Only table, column and error kind stay.

**Span, suggestions**: the same model and profile facts, plus `queries` (names and counts) and `change_rate` facts. The question: "Suggest at most three modelling changes using span.propose. Use only figures from the facts."

**Flow, run note**
```
{"context": {"source": "ORG_03 statements", "run": {"status": "failed", "on_time": true, "schema_ok": true},
  "facts": [{"label": "rows loaded", "value": 1180, "group_size": 1180},
            {"label": "fund_id empty", "value": 12, "group_size": 1180}],
  "rules": [{"rule": "K12:fund_id must not be empty", "passed": false}], "chain": ["contract", "bronze ok", "silver ok", "gold not built"]},
 "question": "Explain this run in at most four plain sentences for the developer."}
```
A count under 5 is never a fact. The tool returns "fewer than five" as text, and the guard replaces any figure the model invents.

**Flow, dialect**: `{"context": {"dialect": "<the stated target>", "changed": ["strftime to date_format", "arg_max to max_by"]}, "question": "Say in plain words what differs."}`. No SQL text with literals leaves.

**Never sent**: rows, sample values, file names of landed files, quarantine contents, people's names (they are tokenised; owners are referred to by role in prompts), uploaded documents in full.

### 3.5 Requirement A: the modelling knowledge pack, memory and suggestions

**Pack** (`sh_platform/build/agents/modelling_pack.yaml`; industry-neutral, so it does not belong in `packs/<industry>/`). One entry per technique: `{id, name, what, fits_when: [volume, change rate, audit need, query pattern], avoid_when, keys, effort, signals: [names of read-tool facts that point to it]}`. Entries:
- Kimball dimensional: facts, conformed dimensions, grain statement, bus matrix (built from measures by entity, as `blueprint_draft._model` L59 already groups).
- Slowly changing dimension types 0, 1, 2, 3, 4, 5 and 6, each with its signal (for example type 2: `keys_changed_last_n_loads` is above zero and the catalogue says the value changes or audit is needed).
- Data Vault 2.0: hubs, links, satellites; fits many sources per entity, high audit need, frequent source change.
- Inmon / 3NF enterprise model: fits many consumers and a stable enterprise vocabulary.
- Medallion bronze, silver and gold (the CURRENT runner's layers).
- One big table and wide marts: fits few measures, one consumer, simple query patterns.
- Periodic snapshot, accumulating snapshot and transaction facts.
- Keys: surrogate, natural and hash, and when each fits.
Span reads the pack only through `span.read_pack(topic)`, which returns at most three passages. `modelling.pick(question, facts)` chooses them by signals, so the prompt stays small.

**Memory: what this company decided and why.** `sh_platform/memory` `AGENTS` gains `span` and `flow`. On accept or decline of a `model_change`, `modelling.remember_decision(plane, text)` writes a company entry, kind `decision`, with the text "Chose <technique> for <subject> because <reason>" or "Declined <technique> for <subject>: <reason>". It is checked against tombstones (`memory.api.tomb_hash`), so a line a company admin deleted is never written again. It is depersonalised (`filters.depersonalise`) and budgeted by `for_prompt`. Span reads it through `span.read_decisions`. The rule in `span_rules.yaml`: "Follow the company's earlier decisions unless the facts changed. If you suggest against one, say which fact changed." The company admin reads and corrects it on the existing Memory page (`/api/company/memory/span`).

**Suggestion engine** (`span_suggest.py`): `review(plane, rt, viewer) -> list[proposal]`.
1. Gather facts through the read tools: model, contracts, catalogue grain, source map, profile counts, change rates, query patterns.
2. Deterministic findings first (rule-based, also the fallback): grain not unique (sandbox `check`), a measure whose lineage fields have more than 20% empties, a dimension whose key changes and is typed 1 while the catalogue says the value changes, two marts with the same grain and source (a candidate for a conformed dimension). The 20% threshold is an assumption and goes to Q8.
3. One `run_agent` call with the `span.propose` sink: at most three suggestions, each with the technique from the pack, the evidence, the impact (contracts, marts and dashboards from `read_queries`), the alternatives and the effort.
4. `proposals.file`. Pulse line to the addressee: "Span suggests a change to <subject>. Decide." (kind `decision`).
5. Runs when a person presses "Ask Span to review the model" in room 1, and once after each blueprint signature. Not on a timer (cost, Q5).

### 3.6 Requirement B: the design document and Archify specs

**Template** (`sh_platform/build/agents/design_template.yaml`). The structure lives here, so the look can change without touching Span:
```
sections:
  - {id: purpose, title: "Purpose and scope", from: [charter], fill: span.design.purpose}
  - {id: context, title: "Context from the charter", from: [charter, intent], fill: records}
  - {id: current, title: "Current state", from: [architecture.record vN signed], diagram: current, fill: records}
  - {id: target, title: "Target architecture", from: [span target draft], diagram: target, fill: span.design.target}
  - {id: delta, title: "What changes", diagram: delta, from: [change note what_changes], fill: records}
  - {id: model, title: "Data model and modelling technique", from: [blueprint model, modelling pack], fill: span.design.model}
  - {id: layers, title: "Layers: bronze, silver, gold", from: [contracts, blueprint lineage], fill: records}
  - {id: sources, title: "Sources and their strategic flags", from: [source map R16], fill: records}
  - {id: flows, title: "Data flows", from: [contracts depends_on, interfaces], fill: records}
  - {id: security, title: "Security and the egress boundary", from: [blueprint access, restricted marts, egress rules], fill: records}
  - {id: quality, title: "Quality and testing", from: [blueprint rules, prove.json, change note tests], fill: records}
  - {id: operations, title: "Operations", from: [contracts expected/sla, run book lines], fill: records}
  - {id: decisions, title: "Decisions and alternatives", from: [change note decisions], fill: span.design.decisions}
  - {id: risks, title: "Risks and open questions", from: [gap report accepted risks], fill: span.design.risks}
  - {id: suggestions, title: "Suggestions for the data team", from: [proposals open], fill: records}
```
`fill: records` sections are written by code from the records (this is also the fallback). `fill: span.design.*` sections are prose from Span (`span_rules.yaml` `design.*` prompts). Every line is `{text, mark, from, by, at}`, as change note lines are.

**Store and versions.** `build/design/design.json` holds the current draft: `{version, state: draft|signed, sections: {id: [line]}, specs: {current, target, delta}, signed_by, drafted: {by, at, fallback: bool}}`. A signed version is kept as `build/design/design.v<n>.json`. A redraft after signature opens v<n+1> as a draft, and stated lines carry over (S6). The design is signed in the same act as the blueprint (S2): `chain /approve` and `blueprint/sign` call `design_doc.sign(plane, by, role)`.

**Archify specs.** `archify_spec.py`:
- `current(plane)` is `architecture.spec` over the newest signed record version (`record.v<n>.json`).
- `target(plane, draft)` is the current components, plus the change's proposed components, plus Span's target placements, each traced to a record or marked "Span's suggestion".
- `delta(plane)` is the target spec with `meta.views = [{"id": "this-change", "focus": [...]}]` (the shape `architecture.spec` L262 already writes).
- Every spec adds two fixed boundaries: "Company plane" (every component in the plane) and "Egress gateway", the only exit, drawn as a node on the boundary. Sources from the source map carry the strategic flag as `sublabel` ("strategic") and the quadrant in a card.
- **Validation before render**: `validate(spec) -> list[str]` runs `jsonschema` against the copied `architecture.schema.json` (with `common.schema.json` resolved locally, no network). It also runs a reference check: every component id is a record component, a fixed boundary node or a Span placement in the draft, and every connection's `from` and `to` exist. A spec that fails is not rendered. The screen shows "The diagram could not be drawn: <first error in plain words>", and the previous valid spec stays.
- **Render**: step 1 uses `svg_with_boundaries(spec)`, which is `architecture.svg` L297 plus a dashed rectangle per boundary.

**How a person edits a draft spec without hand-editing HTML.** HTML is always generated. A person edits:
1. component description and owner, on the existing `PUT /api/company/build/architecture/components/{id}`;
2. a design line, with `PUT /api/company/build/design/lines` (it becomes stated);
3. for an architect who wants control of layout: "Download the spec" (JSON), edit it, then "Upload the spec". `PUT /api/company/build/design/spec` validates the upload against the schema and the reference check. It refuses with the first error, or saves it as `stated` by that person. A later Span draft keeps a stated spec and records its own beside it as a proposal.

**Step 1 render** (`design_doc.render_plain(doc) -> str`): one standalone HTML page with inline CSS, the sections in template order, the three diagrams as inline SVG, a "Draft" or "Signed by <name> on <date>" banner, and "Span's suggestion" tags on guessed lines. No script and no external asset. Room 1 shows it in a sandboxed iframe; "Download the design document" serves the same HTML.

**Step 2 render** (`design_html.render_archify(doc) -> str`, wave 4): the same `doc`, rendered with the copied Archify `template.html` conventions: theme tokens with dark and light, typography, a section navigation rail, inline explorable SVG (hover a component to highlight its connections) and export to PNG and SVG from the page. `docs/architecture/sh-agent-egress.html` and `sh-m4-build.html` are the visual reference. The node CLI is not bundled (C24). If Nitin wants a byte-identical Archify output, that is Q9.

### 3.7 Memory, events, Pulse, knowledge map

- **Memory**: `span`: company decisions (3.5), plus a person's preferences from `remember_for_account` after a "revise" request (the North pattern). `flow`: company lessons on sources ("ORG_03 files arrive late on the first working day"), written when an incident note is accepted. Both appear on the Memory page.
- **Events** (`events.append_event`, R4): only when the record has an `intent_id`. New draft kinds `span_drafted` (detail `{what: target|model|design|suggestion, ref}`) and `flow_drafted` (`{what: run_note|incident_note, ref}`), with `who` "span" or "flow" and status `draft`. A new act kind `proposal_decided` (`{pid, decision}`), with `who` the person. Build records without an intent rely on their own file.
- **Pulse lines**, one reader `build.agent_lines(plane, viewer)` wired into `intent_lines.py` beside the chain block:
  - `decision`, to the addressee: "Span suggests a change to <subject>. Decide." (href room 1 `#suggestions`, record `build/proposals/<pid>.json`); "Flow suggests a model change for <source>. Decide."
  - `request`, to the architect role: "Span drafted the design document for <T>. Check it." (href room 1 `#design`).
  - `request`, to the architect role: "Span could not make the model build. See why." (href room 1).
  - `watch`, to the developer: "Flow explained why <source> failed its checks." (href room 2).
  - `request`, to the alert's tell person: "Flow wrote a note on the <source> alert. Check it." (href room 3).
  - R10: signature and decision lines are never cut by the seven-a-day cap.
- **Knowledge map**: blueprint and release moments are already wired (`blueprint.py` L218-L219, `chain._regen`). The design version is signed inside the blueprint moment. No new moment.

### 3.8 Permission lines and other orchestrator-owned edits

Add to `sh_platform/route_permissions.yaml` (the handlers check the named person, as the chain routes do):
```
GET  /api/company/build/span/target: {roles: [company_admin, analyst, sponsor, owner, approver, participant]}   # SF13, room 0
POST /api/company/build/span/target: {roles: [company_admin, analyst]}                                           # SF13, handler: architect role
GET  /api/company/build/span/model-draft: {roles: [company_admin, analyst]}                                      # SF13
POST /api/company/build/span/model-draft: {roles: [company_admin, analyst]}                                      # SF13, handler: architect role
POST /api/company/build/span/model-draft/{draft_id}/file: {roles: [company_admin, analyst]}                      # SF13, handler: architect role
POST /api/company/build/span/review: {roles: [company_admin, analyst, owner]}                                    # SF13
GET  /api/company/build/proposals: {roles: [company_admin, analyst, sponsor, owner, approver, participant]}      # SF02, filtered by viewer
GET  /api/company/build/proposals/{pid}: {roles: [company_admin, analyst, sponsor, owner, approver, participant]}
POST /api/company/build/proposals/{pid}/accept: {roles: [company_admin, analyst, sponsor, owner, approver, participant]}  # handler: addressee
POST /api/company/build/proposals/{pid}/decline: {roles: [company_admin, analyst, sponsor, owner, approver, participant]} # handler: addressee, reason
POST /api/company/build/proposals/{pid}/ask: {roles: [company_admin, analyst, sponsor, owner, approver, participant]}     # handler: addressee
GET  /api/company/build/design: {roles: [company_admin, analyst, sponsor, owner, approver, participant]}         # SF13
GET  /api/company/build/design/download: {roles: [company_admin, analyst, sponsor, owner, approver, participant]}
GET  /api/company/build/design/spec: {roles: [company_admin, analyst, sponsor, owner, approver, participant]}
PUT  /api/company/build/design/spec: {roles: [company_admin, analyst]}                                           # handler: architect role
PUT  /api/company/build/design/lines: {roles: [company_admin, analyst]}                                          # handler: architect role
POST /api/company/build/design/redraft: {roles: [company_admin, analyst]}                                        # handler: architect role
GET  /api/company/build/flow/runs/{run_id}: {roles: [company_admin, analyst, owner]}                             # SF13, room 2
POST /api/company/build/flow/runs/{run_id}/explain: {roles: [company_admin, analyst]}
GET  /api/company/build/flow/incidents: {roles: [company_admin, analyst, owner]}                                 # room 3
GET  /api/company/build/dialect: {roles: [company_admin, analyst]}                                               # room 2
GET  /api/company/build/dialect/download: {roles: [company_admin, analyst]}
GET  /api/company/memory/span, /api/company/memory/flow                                                          # existing {agent} routes cover them
```
Other edits for the orchestrator:
- `requirements.txt` and `pyproject.toml`: add `sqlglot` and `jsonschema` (both already installed).
- `.claude/rules/ui-copy.md`: "Span, the solution architect; Flow, the data engineer" added to the named agents.
- `sh_platform/catalogue.yaml`: `m4_build.agent: Span and Flow` (A-009 says names live there).
- `docs/decisions.md`: new A-numbers for S1 to S10. D-003 named Flow as the module 3 data agent, but D-036 made Lens lead module 3, so Flow is free. Record that.
- `.env` and settings: none. The repair round cap is a constant with a `ponytail:` comment (Q6).

---

## 4. Cards

Common guardrails for every card (repeated by reference as "G"):
- **G1** Do not run cards against the live backend while another session tests on 8200. A Python edit under `sh_platform/` restarts the reloader, and on this box it does not come back (`.sh-tmp/backend-watch.sh`). Work in a worktree made from HEAD by hand (not `isolation: worktree`, which starts from an old origin/main), or wait for the go-ahead.
- **G2** Reuse first: copy the EARLIER lines named in section 2, and port the EARLIER tests where they exist. The package brief starts with the "Reuse check".
- **G3** Model calls are stubbed in unit tests (a `ModelClient` stub, as `tests/agents` do). No live call outside evals. Every test writes to a tmp folder.
- **G4** No row, sample value or file name in any payload, tool result, proposal or log line. Groups under five are not shown.
- **G5** Never overwrite a `stated` line or path. Signed records are read-only.
- **G6** Screen copy: plain words, no vendor or table names, no em dashes, British spelling, "Span's suggestion" on every agent draft, one-sentence errors.
- **G7** Touch only the files in OWNS. A shared file in OWNS: back it up and dry-run any scripted edit (memory: back up before bulk edits).
- **G8** No permission, manifest, rules or dependency file edits. List what is needed in the report (section 3.8 has the list).

The definition of done for every backend card also includes: `python -c "import <module>"` for each new module; `python -m pytest tests/build -q` still green (report real counts); and a live check written down for later (route, account, expected screen), not run.

### Wave 1 (parallel; OWNS disjoint)

**SF01. Build agent runtime, read tools and the propose sink** (model: opus)
- OWNS: `sh_platform/build/agents/__init__.py`, `runtime.py`, `read_tools.py`; `sh_platform/agents/registry.py`, `sh_platform/agents/loop.py`; `tests/build/test_sf01_runtime_tools.py`, `tests/agents/test_propose_sink.py`.
- Task: copy `compile.get_model` and `register_names` and Lens's `Runtime` into `runtime.py` (constants SPAN, FLOW, MODULE_ID). Build `span_registry` and `flow_registry` with the tools in 3.2. Add `proposes=True` to the registry (only argument-check and collect) and `AgentResult.proposals` to the loop. The `span.search_reference` tool is registered `outside=True`, only when the company's internet switch for `m4_build` is on.
- Acceptance: (1) every read tool's output passes `_summary_only` with a fixture of 4 rows (unavailable) and of 1,180 rows (available); (2) `read_handoff` masks a restricted source per viewer; (3) the registry still refuses `read_only=False` without `proposes=True`; (4) a propose call with unknown keys is refused, a valid one lands in `res.proposals` and nothing is written to disk; (5) `search_reference` is absent when internet is off and wrapped as outside material when on; (6) no tool returns a key named rows or records.
- DoD: `python -m pytest tests/build/test_sf01_runtime_tools.py tests/agents/test_propose_sink.py tests/agents -q`; import check of `sh_platform.build.agents.read_tools`.
- Guardrails: G1 to G8. `loop.py` changes are additive. The existing North, Lens and module 3 tests must stay green (`python -m pytest tests/agents tests/intents -q`).
- Depends on: none. Wave 1.

**SF02. Proposals store, review routes, chain hook and agent names on the chain** (model: opus)
- OWNS: `sh_platform/build/proposals.py`; `sh_platform/build/chain.py` (add `open_from_proposal`; change the screen words "Architect" to "Span"); `sh_platform/build/blueprint_draft.py` (only `BY = "Span"`); `sh_platform/intents/events.py` (AGENTS may draft: `span`, `flow`; kinds `span_drafted`, `flow_drafted`, `proposal_decided`); `tests/build/test_sf02_proposals.py`.
- Task: implement 3.3. Closed `KINDS` with schemas; `file()` with dedupe, the cap of three and re-validation; routes list, get, accept, decline (reason required) and ask (a thread line). Accepting a `model_change` calls `chain.open_from_proposal`. A change note for a proposal with no intent takes its people from the newest signed charter (`uat._role` pattern), and its "Why" section quotes the proposal. Accepting an `incident_note` calls `alerts.act`. Also `pulse_lines(plane, viewer)` for decision lines.
- Acceptance: (1) only the addressee can accept, decline or ask (403 otherwise); (2) decline without a reason is a 422; (3) accepting a `model_change` opens exactly one change note marked `from: P-n`, and accepting twice is a 409; (4) a signed blueprint is untouched by an accept; (5) a proposal on a restricted measure is hidden from a viewer outside its list; (6) id pattern and plane resolution refuse `../` and another company's id; (7) existing chain tests pass with the renamed words updated.
- DoD: `python -m pytest tests/build/test_sf02_proposals.py tests/build/test_b59.py -q`; events tests `python -m pytest tests/intents -q -k events`.
- Guardrails: G1 to G8. `events.py` is shared: back it up and keep the current kinds unchanged.
- Depends on: none (it reads `res.proposals` items as plain dicts). Wave 1.

**SF03. Modelling knowledge pack and decision memory** (model: opus)
- OWNS: `sh_platform/build/agents/modelling_pack.yaml`, `sh_platform/build/agents/modelling.py`; `sh_platform/memory/__init__.py` and `sh_platform/memory/api.py` (only `AGENTS`); `tests/build/test_sf03_modelling.py`.
- Task: write the pack (3.5) with every technique listed by Nitin and its `fits_when`, `avoid_when` and `signals`, in plain industry-neutral words. Seed it from EARLIER `.claude/agents/data-architect.md`. Write `pick(question, facts) -> list[passage]` (at most 3). Write `remember_decision` and `decisions(topic)` on company memory with the tombstone check and depersonalising.
- Acceptance: (1) the pack loads and every entry has the required keys; (2) `pick` returns the type 2 entry when a change-rate fact is above zero and the catalogue says the value changes, and the one big table entry for one measure with one consumer; (3) a tombstoned decision is not written again; (4) a person's name in a reason is removed before it is written; (5) `/api/memory/me/span` and `/api/company/memory/span` work (existing routes); (6) no industry word appears in the pack (`tests/test_no_hardcoded_industry.py` still passes).
- DoD: `python -m pytest tests/build/test_sf03_modelling.py tests/memory tests/test_no_hardcoded_industry.py -q`.
- Guardrails: G1 to G8. The pack is suggestion material, not company policy.
- Depends on: none. Wave 1.

**SF04. Sandbox model engine** (model: opus)
- OWNS: `sh_platform/build/model_build.py`; `tests/build/test_sf04_model_build.py` (port the EARLIER `tests/test_model_drafting*` and silver SCD tests first).
- Task: copy `normalise`, `check`, the SCD1, SCD2 and fact builders and `build_mart` (section 2.1), and reshape them to one sandbox DuckDB file per draft (`warehouse/sandbox/<draft_id>.duckdb`, with the company warehouse attached read-only, deleted after the report). Add `scrub(error) -> str` (keep table, column and error kind; drop literals and values). Return `{built: {silver: [names], gold: [names]}, counts: {name: rows}, errors: [scrubbed]}`.
- Acceptance: (1) a valid draft builds the facts, dimensions and marts and reports counts; (2) a non-unique grain is an error naming the table and columns only; (3) an SCD2 dimension keeps one current row per key; (4) a DuckDB conversion error carrying a value is scrubbed to "column X: values do not fit type double"; (5) the company warehouse file is unchanged after a run (hash before and after); (6) the sandbox file is removed even when a build fails.
- DoD: `python -m pytest tests/build/test_sf04_model_build.py -q`; import check.
- Guardrails: G1 to G8. Never write to `warehouse/company.duckdb`.
- Depends on: none. Wave 1.

**SF05. Archify specs: current, target, delta, boundaries and validation** (model: opus)
- OWNS: `sh_platform/build/archify_spec.py`; `sh_platform/build/archify/architecture.schema.json`, `common.schema.json`, `template.html`, `LICENCE-ARCHIFY.txt` (copied from the skill, MIT notice kept); `tests/build/test_sf05_archify_spec.py`.
- Task: implement the spec part of 3.6: `current`, `target`, `delta`, the two fixed boundaries, the strategic flag on sources, `validate` (jsonschema with local refs, plus the reference check), `svg_with_boundaries`, and the masking through `architecture.masked`.
- Acceptance: (1) the `docs/architecture/sh-m4-build.json` fixture validates; (2) a spec with an unknown component type or a dangling connection fails with a plain first error; (3) a component that traces to no record and is not a Span placement is refused; (4) restricted components render as "Restricted" with no label for a viewer outside the list; (5) the egress gateway node sits on the plane boundary in every spec; (6) validation makes no network call (resolver patched to raise on any URL).
- DoD: `python -m pytest tests/build/test_sf05_archify_spec.py -q`; import check.
- Guardrails: G1 to G8. Do not edit `architecture.py`; wrap it.
- Depends on: none. Wave 1.

**SF06. Design document template, store and plain renderer (step 1)** (model: sonnet)
- OWNS: `sh_platform/build/agents/design_template.yaml`; `sh_platform/build/design_doc.py`; `tests/build/test_sf06_design_doc.py`.
- Task: the template (3.6), the store and versions (draft, signed, v<n>, stated lines carried over), `fill_from_records(plane)` (every `fill: records` section, and the fallback for the Span sections with "Not available yet" naming the missing record), `sign(plane, by, role)`, and `render_plain(doc, diagrams: dict[str, str])` (inline CSS, no script, no external asset).
- Acceptance: (1) the sections render in template order, and reordering the yaml reorders the page with no code change; (2) a signed version is read-only, and an edit opens v<n+1> with stated lines kept; (3) every figure in the document traces to a record (a test reads each number and finds it in the source records); (4) the rendered HTML has no `<script>` and no `http` URL; (5) the empty company gives "Span drafts the design document after the gap report is signed."; (6) two industries (family office, asset management) render with no industry word in code.
- DoD: `python -m pytest tests/build/test_sf06_design_doc.py -q`; import check.
- Guardrails: G1 to G8. Diagrams come in as strings, so there is no import of SF05 in this wave.
- Depends on: none. Wave 1.

**SF07. Warehouse target and dialect SQL** (model: sonnet)
- OWNS: `sh_platform/build/dialect.py`; `sh_platform/build_env.py` (new question `warehouse_target`, a stated answer only, no guess); `tests/build/test_sf07_dialect.py`.
- Task: collect the runner's SQL statements per source (silver typing, marts) as DuckDB text from the same builders, then `sqlglot.transpile(..., read="duckdb", write=<dialect>)`. Return statements, plus `changed_constructs` (the function names that differ). A mapping from the stated answer to a sqlglot dialect name lives in one dict. An unknown answer gives "Not available yet: Span and Flow cannot write SQL for <answer> yet."
- Acceptance: (1) with no stated target, the dialect route reports nothing to do; (2) a stated target transpiles every statement, or names the one that failed; (3) `changed_constructs` holds no literal from the SQL; (4) the environment page shows the new question with no guess; (5) the download is a text file of the statements marked as a draft.
- DoD: `python -m pytest tests/build/test_sf07_dialect.py tests/build_env -q`.
- Guardrails: G1 to G8. Nothing connects to a remote warehouse.
- Depends on: none. Wave 1.

**SF08. Tester, wave 1** (model: sonnet)
- OWNS: `tests/build/test_sf_wave1_review.py` (read-only review of the others; new tests only).
- Task: one review round over SF01 to SF07. Run each card's commands and report the real counts. Add cross-card tests: the propose sink items are accepted by `proposals.file`; the specs validate when rendered by `render_plain`; the plane isolation test (another company's proposal, design and sandbox are unreachable); a role without access is refused on the proposal routes (TestClient with the stub permissions of 3.8 applied in the test app only).
- Acceptance: every DoD command re-run with its count; at least the four cross-card tests; a findings list per card (file and line).
- DoD: `python -m pytest tests/build -q`.
- Depends on: SF01 to SF07. End of wave 1.

### Wave 2 (parallel; OWNS disjoint)

**SF09. Span: model draft, sandbox repair and file for signature** (model: opus)
- OWNS: `sh_platform/build/agents/span_rules.yaml` (sections `role`, `rules`, `model_format`, `repair`); `sh_platform/build/agents/span_model.py`; `tests/build/test_sf09_span_model.py`.
- Task: `start(plane, rt, by, changes="")` runs the background draft; `latest(plane)`; `file(plane, draft_id, by)`. Loop: gather facts through SF01 tools, `run_agent`, `_parse` JSON, `model_build.normalise`, `check`, sandbox, at most `MAX_ROUNDS = 3` (ponytail constant, Q6) and 120 seconds of wall time. File merges into `build/blueprint.json` paths `model.*` and `lineage.*` as `guessed` by Span, skipping `stated` paths and a signed blueprint (it opens the next version, as `blueprint.py` PUT L188-L190 does). Fallback: the model is missing or failing, so the existing rule-based model stands and the draft says so.
- Acceptance: (1) a stub that answers a valid model files it and the blueprint paths are guessed by Span; (2) a stated path is unchanged after filing; (3) a stub that fails twice then succeeds stops at round 3 with the success; (4) a stub that always fails leaves the draft `failed` with scrubbed errors and the blueprint untouched; (5) the payload sent (captured from the stub) has no sample value and no landed file name; (6) the number guard replacing a figure makes the round invalid; (7) a stale claim older than 300 seconds reads as failed.
- DoD: `python -m pytest tests/build/test_sf09_span_model.py -q`.
- Guardrails: G1 to G8.
- Depends on: SF01, SF03, SF04. Wave 2.

**SF10. Span: suggestions to the data team** (model: opus)
- OWNS: `sh_platform/build/agents/span_suggest.py`; `sh_platform/build/agents/span_suggest_rules.yaml`; `tests/build/test_sf10_span_suggest.py`.
- Task: implement the suggestion engine in 3.5: deterministic findings first, then one sink run, then `proposals.file`, and `remember_decision` on accept and decline (a hook `proposals.on_decided` that SF02 calls by name; agree the signature `on_decided(plane, proposal, decision, reason)` in both cards).
- Acceptance: (1) with a change-rate fact above zero, a type 1 dimension and a catalogue that says the value changes, the deterministic finding suggests type 2 even with no model; (2) the model's suggestion carries technique, evidence, impact, alternatives and effort, or it is dropped; (3) evidence numbers all trace to tool facts; (4) a suggestion against an earlier company decision names the fact that changed, or it is dropped; (5) accept writes a decision memory entry, and decline writes the reason; (6) at most three per run and no duplicate of an open one.
- DoD: `python -m pytest tests/build/test_sf10_span_suggest.py -q`.
- Guardrails: G1 to G8. Never apply a suggestion.
- Depends on: SF01, SF02, SF03, SF04. Wave 2.

**SF11. Span: target architecture, decisions, citations, design content and spec draft** (model: opus)
- OWNS: `sh_platform/build/agents/span_design.py`; `sh_platform/build/agents/span_design_rules.yaml` (sections `target`, `design.*`, `cite`); `tests/build/test_sf11_span_design.py`.
- Task: `draft_target(plane, rt, intent_id)` (room 0) and `draft_design(plane, rt)`: fill the `span.design.*` sections, the decision records (copied `normalise` and `check` from `architecture_drafting`), the citations (copied `verify`, only with internet on), and Span's placements for the target spec. Validate with SF05 before saving, then save through SF06. Fallback: `fill_from_records` and `architecture.project`, with the R14 sentence.
- Acceptance: (1) every decision has at least two options, or it is dropped; (2) a citation whose passage does not exist is removed; (3) with internet off, no outside tool is listed and no citation appears; (4) an invalid spec from the model is not saved and the previous one stays; (5) stated design lines are kept on redraft; (6) the R16 hand-off fields all appear in the target payload (captured from the stub), and nothing else from the intent does.
- DoD: `python -m pytest tests/build/test_sf11_span_design.py -q`.
- Guardrails: G1 to G8. Outside material is never a source of a company figure.
- Depends on: SF01, SF05, SF06. Wave 2.

**SF12. Flow: run notes, quarantine, incident notes and dialect explanation** (model: opus)
- OWNS: `sh_platform/build/agents/flow.py`, `sh_platform/build/agents/flow_rules.yaml`; `sh_platform/build/runner.py` and `sh_platform/build/transforms.py` (quarantine only: offending rows of a failed block rule copied to `quarantine.<source>` in the company warehouse with the run id; counts on the run record); `tests/build/test_sf12_flow.py`.
- Task: `explain_run(plane, rt, run_id)` (stored on `build/flow/runs/<run_id>.json`, with deterministic fallback lines built from the run record following engineer.md's chain order); `incident_note(plane, rt, alert_id)`, filed as an `incident_note` proposal; `explain_dialect(plane, rt)`; and a `model_change` proposal when a failure points at the model.
- Acceptance: (1) a failed run gets a note within one call, and with no model the deterministic lines name the first missing link; (2) quarantine holds exactly the offending rows of block rules, and the run record holds counts; (3) no quarantine value appears in any payload, note or proposal (captured stub payload); (4) a count under five reads "fewer than five"; (5) an incident note goes to the alert's tell person; (6) a non-unique grain failure files one `model_change` naming Span; (7) the existing runner tests still pass.
- DoD: `python -m pytest tests/build/test_sf12_flow.py tests/build/test_runner.py tests/build/test_ops.py -q`.
- Guardrails: G1 to G8. Flow never runs a pipeline or closes an alert.
- Depends on: SF01, SF02, SF07. Wave 2.

**SF13. Routes, install, sign hooks and Pulse** (model: sonnet)
- OWNS: `sh_platform/build/agents/routes.py`; `sh_platform/build/blueprint.py` (sign hook only: `design_doc.sign`); `sh_platform/build/chain.py` (`/approve` calls `design_doc.sign`; `install` includes `proposals.router` and `agents.routes.router`); `sh_platform/pulse/intent_lines.py` (one try block for `proposals.pulse_lines` and `routes.agent_lines`); `tests/build/test_sf13_routes.py`.
- Task: every route in 3.8 except the proposal routes (SF02), thin over SF06 and SF09 to SF12; the Pulse lines in 3.7; the R14 `fallback` flag and sentence in each GET.
- Acceptance: (1) each route refuses a role not in 3.8 and a viewer who is not the named person where the handler checks; (2) approving a change note signs the design version in the same act, and the signed design is then read-only; (3) the Pulse lines appear for the addressee only, and decision lines survive the daily cap (R10); (4) `GET design/download` returns the plain HTML with `Content-Disposition: attachment`; (5) `PUT design/spec` refuses an invalid spec with the first error and saves a valid one as stated; (6) a switched-off company is refused on every route.
- DoD: `python -m pytest tests/build/test_sf13_routes.py tests/build/test_b59.py tests/build/test_blueprint.py tests/pulse -q`.
- Guardrails: G1 to G8. `chain.py` and `intent_lines.py` are shared: back them up first.
- Depends on: SF02, SF06, SF09, SF10, SF11, SF12. It runs last in wave 2 (it may start once their function signatures are fixed).

**SF14. Security review: the propose tool and the agent payloads** (model: opus)
- OWNS: `tests/build/test_sf14_security.py`; findings in the card report (no code edits; fixes go back to the owning card).
- Task: review 3.3 points 1 to 8 against the code. Add attack tests: prompt injection through outside material asking for a proposal to another addressee; a proposal with a raw row in evidence; a figure from a group of 4; cross-company ids; an accept by a non-addressee; a flood of proposals; error text with a value reaching the model; a design upload with a script tag; a spec with an external `$ref`.
- Acceptance: each attack has a test that fails before and passes after the owning card's fix; every gateway payload in the wave 2 tests is captured and passes `gateway._check_structure`; a written verdict per point.
- DoD: `python -m pytest tests/build/test_sf14_security.py tests/egress -q`.
- Depends on: SF01, SF02, SF09 to SF13. Wave 2 (after its peers land).

**SF15. Tester, wave 2** (model: sonnet)
- OWNS: `tests/build/test_sf_wave2_review.py`.
- Task: one review round over SF09 to SF13. Run all commands; an end-to-end test on a seeded tmp company (family office and asset management, an empty company, one person alone): hand-off, then target, model draft, file, suggestion accepted (a change note opens), design approved (signed together), run failed (Flow note and quarantine counts), alert (incident note).
- Acceptance: the end-to-end test passes for all four company shapes; the real counts are reported; findings listed per card.
- DoD: `python -m pytest tests/build -q`.
- Depends on: SF09 to SF14. End of wave 2.

### Wave 3 (parallel; screens)

**SF16. Room 1 screens: Span's model draft, suggestions and design document** (model: sonnet)
- OWNS: `ui/src/pages/build/SpanModelPanel.tsx`, `SuggestionsPanel.tsx`, `DesignDocPanel.tsx`, `spanCopy.ts`, `span.test.tsx`; `ui/src/pages/BlueprintPage.tsx` (mount the three panels only); the API client additions in a new `ui/src/pages/build/spanApi.ts`.
- Task: the model draft panel (status, rounds, errors in plain words, "Ask Span to revise" with a note, "File for signature" for the architect role); suggestions (cards with what, technique, why, evidence, impact, alternatives and effort; Accept, Decline with a reason, Ask; "Span's suggestion" tag); the design document (sandboxed iframe of the plain HTML, Current, Target and What changes tabs, "Download the design document", "Download the spec" and "Upload the spec" for the architect role); the R14 fallback banner.
- Acceptance: five states per panel (loading, empty, error, refused, populated); copy passes G6 (a test greps for vendor names, "Archify", "DuckDB" and em dashes); the iframe has `sandbox` with no `allow-scripts`; a 390-pixel layout puts the panels in one column; the decline button is disabled until a reason is typed.
- DoD: `cd ui && npx vitest run src/pages/build/span.test.tsx src/pages/blueprintPage.test.tsx`; `cd ui && npx tsc --noEmit`; live check for later: sign in as Aaron (architect role) on the demo company, open `/centre/build/blueprint`, compare with the room 1 artboard by screenshot.
- Guardrails: G6, G7; typed props, no `any`, server data through the one typed client.
- Depends on: SF13. Wave 3.

**SF17. Rooms 0, 2 and 3 screens: Span's target card and Flow's notes** (model: sonnet)
- OWNS: `ui/src/pages/build/SpanTargetCard.tsx`, `FlowRunNote.tsx`, `FlowIncidentNote.tsx`, `DialectPanel.tsx`, `flowCopy.ts`, `flow.test.tsx`; `ui/src/intents/views/BuildReadyView.tsx` (mount `SpanTargetCard` in `GapAnalysisRoom` only); `ui/src/pages/PipelinesPage.tsx` and `ui/src/pages/OpsPage.tsx` (mount lines only); `ui/src/pages/MemoryPage.tsx` (add Span and Flow to the agent list if it is fixed).
- Task: the room 0 target card (diagram, three why lines, fallback banner); the Flow run note under each run row; the quarantine counts ("12 rows set aside: fund id empty"); "SQL for your warehouse" (shown only when a target is stated) with a download; the incident note on the alert with Acknowledge with this note and Edit.
- Acceptance: five states each; G6 copy test; no figure shown as zero when missing ("Not available yet"); a count under five reads "fewer than five"; mobile layout at 390 pixels.
- DoD: `cd ui && npx vitest run src/pages/build/flow.test.tsx src/pages/pipelinesPage.test.tsx src/pages/opsPage.test.tsx src/intents/BuildReadyView.test.tsx`; `cd ui && npx tsc --noEmit`; live check for later: Katie on `/centre/build/pipelines` after a failed run, Harvey on `/centre/build/ops`.
- Guardrails: G6, G7.
- Depends on: SF13. Wave 3.

**SF18. Tester, wave 3** (model: sonnet)
- OWNS: `ui/src/pages/build/spanFlow.review.test.tsx`.
- Task: one review round over SF16 and SF17: run vitest and tsc, check the five states and the copy rules, and write the live walk script for later (accounts, routes, screenshots against the artboards, `shot.py`).
- Acceptance: the commands re-run with counts; the walk script is written; findings listed per card.
- DoD: `cd ui && npx vitest run`; `cd ui && npx tsc --noEmit`.
- Depends on: SF16, SF17. End of wave 3.

### Wave 4 (step 2, later)

**SF19. Design document in the Archify look (step 2)** (model: sonnet)
- OWNS: `sh_platform/build/design_html.py`; `sh_platform/build/archify/template.html` (adapted copy, MIT notice kept); `tests/build/test_sf19_design_html.py`; the download route switch in `sh_platform/build/agents/routes.py` (one parameter `look=plain|archify`, default `archify` once accepted).
- Task: render the same `doc` with theme tokens (dark and light, plus the `data-theme` override), typography, a section rail, inline explorable SVG (hover highlights connections; no network) and export to PNG and SVG from the page. Use `docs/architecture/sh-agent-egress.html` and `sh-m4-build.html` as the reference.
- Acceptance: (1) the same content as step 1 (a test compares the section text); (2) both themes render; (3) no external URL (fonts inlined or system fonts); (4) the page is still valid when a diagram failed validation (that section shows the plain error line); (5) swapping `design_template.yaml` order changes both renderers with no Span change.
- DoD: `python -m pytest tests/build/test_sf19_design_html.py tests/build/test_sf06_design_doc.py -q`; import check.
- Guardrails: G1 to G8. No node at run time.
- Depends on: SF06, SF11, SF13. Wave 4.

**SF20. Tester, wave 4** (model: sonnet)
- OWNS: `tests/build/test_sf_wave4_review.py`.
- Task: one review round over SF19: run its commands, open both renders in the browser pane on a tmp file (not the live backend), compare against `docs/architecture/sh-m4-build.html` by screenshot, and report.
- Acceptance: counts reported, screenshots attached, findings listed.
- DoD: `python -m pytest tests/build -q`.
- Depends on: SF19. End of wave 4.

### Waves at a glance

| Wave | Cards (parallel) | Ends with |
|---|---|---|
| 1 | SF01, SF02, SF03, SF04, SF05, SF06 (step 1), SF07 | SF08 tester |
| 2 | SF09, SF10, SF11, SF12, then SF13, then SF14 security | SF15 tester |
| 3 | SF16 (step 1 screens), SF17 | SF18 tester |
| 4 | SF19 (step 2, Archify look) | SF20 tester |

Model suggestion summary: opus for SF01 to SF05, SF09 to SF12 and SF14; sonnet for SF06 to SF08, SF13, SF15 to SF20. The router (`tools/route_task.py`) makes the final pick.

---

## 5. Risks and open questions for Nitin

### Risks

1. **Cost and time of model calls.** A model draft is up to 3 rounds, plus one suggestion call, one design call and one call per run and per alert. On a busy day this could be dozens of calls per company. Mitigation: no timers (calls happen only on a person's press, after a signature, or after a run); a daily cap per company (Q5); the run log counts calls.
2. **Leakage through error text and evidence.** DuckDB errors and model-written evidence can carry values. Mitigation: `model_build.scrub`, the number guard, `_summary_only`, the gateway's row and figure checks, and the SF14 attack tests. This is the highest-impact risk.
3. **The live backend and shared files.** Wave 2 edits `chain.py`, `blueprint.py`, `runner.py`, `events.py` and `intent_lines.py`, which other sessions also touch, and any Python edit restarts the reloader that does not come back on this box. Mitigation: G1 (hand-made worktree from HEAD), backups and dry runs (G7), SF13 last in wave 2.
4. A suggestion engine that over-suggests erodes trust. Mitigation: deterministic findings first, three per run, no duplicates, and company decisions in memory.
5. Sandbox SCD2 versus the production runner: the production `transforms.build_silver` has no SCD2. An accepted type 2 suggestion builds in the sandbox but not in production until Q7 is settled.

### Open questions

1. **Names.** Span and Flow on screen, replacing Architect and Builder (S1). D-003 gave Flow to module 3 and A-009 calls module 4's agent "Builder". Confirm, and say whether Prover and Watcher keep their names (Watch in D-003 or Watcher in code).
2. **Signer roles.** A-005 stands (S2). Confirm that the design document is signed with the blueprint by the head of department, and that a suggestion is addressed to the measure's data owner, else the blueprint signer.
3. **Warehouse targets.** Which targets should the dialect offer first? The answer is free text in the environment check today. Should naming a target also unlock the cloud push (BC-8)? This plan says no.
4. **Image reading.** Picture-to-diagram is out of scope (S9). Do you want the gateway to carry images later (a change to egress.md and D-032), or should pictures stay on the machine for good?
5. **Cost of model calls.** Is there a daily cap per company (suggested: 40 Build calls), and who sees the count (company admin on the run log)?
6. **Sandbox repair loop.** Three rounds and 120 seconds of wall time are proposed (EARLIER used 4 rounds, `SH_DRAFT_ROUNDS`). Confirm, or give the limits.
7. **SCD2 in production.** Should the production runner gain the copied SCD2 builder when a signed model asks for type 2, or is that a later card?
8. **Thresholds** with no source yet: 20% empties as a suggestion trigger; "last 12 loads" for change rate; three suggestions per run. These are assumptions to confirm.
9. **Step 2 look.** Is an Archify-style render inside the product enough, or must the download be byte-identical to the Archify CLI output? That would need node bundled with the product, which C24 rules out today.
10. **Reference citations.** Internet stays off by default (D-006). Which destinations go on the allowlist when a company turns it on for Build?
