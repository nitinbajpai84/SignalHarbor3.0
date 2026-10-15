# Inventory of the earlier product, mapped to the six modules (D-031: check here before you build)

Source: `<earlier repo>` (commit 3a798cc5, `main`), plus the unmerged family-office fork at `...\worktrees\practical-hawking-bd28e8` (branch `claude/quizzical-jackson-5f69d5`). Both are on this machine. Copy from them freely; there are no restrictions on moving code, prompts, tests, screens or content between the repos. Real client data never moves (rule 0).

"Confidence": **read** = I read the code; **name** = judged from the file name, folder and headers, so open it with `graft ask` before relying on it. Prefix `emitters/`, `webapp/backend/routers/` and `docs/signal-harbor/prototype/js/screens/` are shortened below to `e/`, `r/` and `s/`.

## How to check before building
1. `graft ask "<what you need>" --source` run inside the earlier repo (`cd` there). `graft grep "<literal>"` finds every occurrence.
2. Search this table for the module and the verb (draft, scan, profile, build, forecast, brief).
3. Look in the earlier repo's `tests/` (158 files) and `docs/signal-harbor/prototype/js/tests/` (52 files) for the behaviour already pinned down; port the tests first.
4. Write the result in the package brief under "Reuse check": file and lines, copied / reshaped / new, and why.

## Platform and cross-cutting (all modules)

| Capability | Where in the earlier product | Confidence | Already in this repo? |
|---|---|---|---|
| Company creation, provisioning, tenancy | `sh_platform/provision.py`, `tenancy.py`, `workspace.py`, `store.py`, `r/platform_admin.py`, `r/ws_admin.py`, `r/domains.py`, `r/admin.py` | name (workspace.py read) | company plane yes; super-admin console and provisioning no |
| Sign-in, roles, permissions | `r/auth.py`, `r/auth_me.py`, `r/access.py`, `webapp/backend/authz.py`, `contracts/access/` | read | yes (phase 1) |
| Model gateway, policy, tiers | `agents/gateway.py`, `agents/policy.py` | read | yes (egress) |
| Agent runtime, memory, sessions, tools | `e/agent_brain.py`, `agent_memory.py`, `agent_sessions.py`, `agent_context.py`, `agents/sh_tools.py`, `agents/runtime_agents.py`, `agents/run_context.py` | read (brain) | runtime yes; memory, retry, citation scrub, context assembly partly (port in M1-P04c) |
| crewAI bridge and personas | `agents/crews_bridge.py`, `sh_crews/` (crews, personas, worker, replay) | name | no (planned for the common room) |
| Background jobs, worker, telemetry | `sh_platform/jobs.py`, `worker.py`, `telemetry.py`, `r/usage.py` (allowance and cost) | name | no |
| Team rooms and room dispatch | `e/team_room.py`, `e/room_dispatch.py`, `r/room_agents.py`, `s/team-rooms.js`, `s/rooms.js`, `js/room-session.js` | read (headers) | no |
| My tasks, action loop | `js/my-tasks-api.js`, `s/my-tasks.js`, `s/action-loop.js`, `e/signals/actions.py`, `r/signals_actions.py` | name | no (Nira project board is new on top) |
| Clarity score, gamification | `js/gamify.js`, `js/torch.js` | name | no |
| Documents and uploads | `e/documents.py`, `r/uploads_routes.py`, `r/agent_docs.py`, `sh_platform/context/` | name | no |
| Live updates (SSE) | `r/live.py`, `js/live.js` | read | yes (module 1) |
| Voice | `e/voice.py`, `js/voice.js` (721 lines; mic, spoken replies, agent voices) | read | speech in yes; spoken replies in M1-P06 |
| Evals, release gate, evidence | `e/evals/`, `e/release_gate.py`, `e/release_signoff.py`, `evidence/`, `harness/` (smoke_live and others) | read (evals) | evals yes |
| Packs and domain admin | `templates/<industry>/1/`, `e/domain_packs.py`, `e/domain_admin.py`, `contracts/settings/` | read | packs yes (3 industries after M1-P04c) |
| Look and feel | `docs/signal-harbor/prototype/css/`, `assets/brand/` | read | yes (legacy styles) |
| Deploy | `deploy/`, `Dockerfile`, `railway.json` | name | no (not needed locally) |

## Module 1: Intent Centre
See `docs/reuse-map.md` and `docs/ledger/M1-LOOK/old-ui/README.md`. Session engine, wall, clustering, charter, problem library, interview, voice input, live updates: all located. Also in the earlier repo and not yet used: `e/intent.py`, `e/intent_change.py` (intent change control), `r/intent_items.py` (MoSCoW items), `s/intent-center.js` (Board, Sessions, MoSCoW, Pain points tabs), `js/intent-rank.js`. Used for the four kinds of note (4 Oct): the pain point fields (`pain_point.schema.yaml` text, affected, frequency, linked KPI) became the pain point kind's details; the MoSCoW item fields (name, priority, owner, phase) were not used because this module's vote already sets priority. The earlier What-if screen (`prototype/js/screens/what-if.js`) is a seeded insurance simulator, not a place levers are collected: only the idea of a lever and the KPIs it moves was used, as the lever kind's `moves` detail. Details in the package report.

## Module 2: Baseline
| Capability | Where | Confidence |
|---|---|---|
| Definitions drafted from the pack, "you decide" questions, conflicts, sign-off lock, human edits kept | `e/baseline.py` (906), `r/baseline.py` (242) | read |
| Process map, data landscape | same; `s/process-map.js`, `s/data-landscape.js`, `s/baseline.js` | read / name |
| Requests to owners, intake forms | `e/intake_compiler.py`, `e/intake_template_builder.py` | name |
| BA deliverables | `e/ba_deliverables.py` | name |
| RAID log | `e/raid_log.py` | name |
| Proposals and approvals | `e/proposals.py`, `r/proposals.py` | name |
| Sensing and benchmark | `s/sense-peek.js`, `s/sense-check.js`, `e/benchmark.py` | read (benchmark) |
| Catalogue (Excel) | template only: `docs/specs/signal-harbor-data-catalogue-template.xlsx` | read |

## Module 3: Connect, scan and gap
| Capability | Where | Confidence |
|---|---|---|
| Estate scan and findings | `e/estate.py`, `r/estate.py`, `s/estate.js` | name |
| Landing zone | `e/landing.py` | name |
| Connectors (databases, files) | `e/connectors.py`, `e/connect_adapter.py`, tests `test_connectors_ddl_upload_live.py` | read (adapter) |
| Profiling | `e/profiler.py` | name |
| Source discovery agent and review | `e/discovery_agent.py`, `r/discovery_routes.py`, `e/source_review.py` | name |
| Column matching against definitions | `e/column_matcher.py` (304) | read |
| Unstructured scan | `e/unstructured_scan.py` | read |
| Gap report by problem | `e/gap_report.py` | read |
| Maturity check | `s/maturity-check.js` | name |
| Screens | `s/scan-gaps.js`, `s/estate.js`, `s/context-uploads.js`, `s/sense-check.js` | name |
| Agent skills (Flow, Scribe) | `agents/skills/` (detective.md, engineer.md and others) | read |

## Module 4: Build and gap closure
| Capability | Where | Confidence |
|---|---|---|
| Pipeline build (bronze, silver, gold) | `e/pipeline_build.py`, `e/bronze_loader.py`, `e/silver_transform.py`, `e/gold_transform.py`, `r/pipeline_routes.py`, `dbt/` | name |
| SQL dialect translation | `e/sql_dialect.py` (sqlglot) | name |
| Model and architecture drafting (agent writes a specification) | `e/model_drafting.py`, `e/architecture_drafting.py`, `e/architecture.py`, `r/architecture_routes.py`, `e/reference_arch.py` | name |
| Test pack generation and results | `e/test_pack.py`, `r/test_pack_routes.py`, `s/build-test.js` | name |
| Release gate and two-person sign-off, Databricks push | `e/release_gate.py`, `e/release_signoff.py`, `r/release.py`, `r/gates.py` | read (gates) |
| Knowledge graph and context layer | `r/context.py`, `r/context_layer.py`, `s/knowledge-graph.js`, Neo4j and Qdrant settings in `.env` | name |
| Screens | `s/build-package.js`, `s/build-track.js`, `s/architecture.js`, `s/reconciliation.js` | name |
| Ontology from glossary | not built | - |
| Snowflake target | not built | - |
| Functional specification document for the customer to approve | partly in drafting code; document form not built | name |

## Module 5: Foresight
| Capability | Where | Confidence |
|---|---|---|
| Signals: classify, enrich, evaluate, hidden gems, risk scoring | `e/signals/` (classify.py, enrich.py, evaluate.py, gems.py, risk_scoring.py, actions.py, poc_source.py), `r/signals.py` | name |
| Customer profiles, clusters | `e/customers.py`, `r/customers.py`, `contracts/context/clusters.yaml` | read (V3-09) |
| Benchmark (belief, range, company figure) | `e/benchmark.py` | read |
| Forces (pull, friction, retention, gems), forecast, market signals, what-if | `s/foresight.js`, `s/forces.js`, `s/what-if.js`, `s/signals.js`, `s/cmo-dashboard.js` | name (insurance content) |
| Family-office five dimensions (attractiveness, mandate fit, funding feasibility, implementation friction, evidence strength) and its routes | the fork's `/api/family-office/foresight`, `emitters/family_office*.py`, classifier and signals files in `templates/family_office/1/` | name (unmerged; Nitin gave this to the fork) |
| Monthly feed | `e/monthly_feed.py`, `r/feed_monthly.py` | name |

## Module 6: Day two (ops, daily feed, market pulse)
| Capability | Where | Confidence |
|---|---|---|
| Daily feed, Today page | `e/daily_feed.py`, `e/today.py`, `r/today.py` | read (today) |
| Ops schedule and tickets | `e/ops_schedule.py`, `e/ops_tickets.py`, `r/ops.py` | name |
| Market data | `r/market_routes.py`, market briefs in the packs | name |
| Anomalies, action outcomes | `e/signals/actions.py`, `r/signals_actions.py` | read (today feed) |
| Screens | `s/today.js`, `s/ops-manager.js`, `s/ops-watch.js`, `s/command-center.js`, `s/action-loop.js` | name |
| Agent skills (Watch, Niru) | `agents/skills/nightwatch.md`, `delivery.md`, `program.md` | read |

## Reused inside this repo: Lens's block and Nira in module 2 (M2-AGENTS)
| Capability | Where | What was done |
|---|---|---|
| Docked, expandable agent panel | `ui/src/components/AgentPanel.tsx` (was `NiraPanel.tsx`), `AskBox.tsx` (out of `NiraDock.tsx`) | generalised to any agent (name, role); module 1's Nira dock uses the same |
| Nira's shared turn (cut, plain, quiet context, model turn) | `sh_platform/agents/guide.py` (from `modules/m1_intent/agent/nira.py`) | moved to the kernel for the second module; each module keeps its rules, messages and session facts |
| Company context uploads | `sh_platform/context_docs` | the pre-read checklist is a view over them, tagged by kind in `store/lens.py`; no second store |
| Lens drafts, proposals, provenance, owners and triage routes | `agent/lens.py`, `api/worklist.py`, `domain/provenance.py` | extended (`draft_fields`, `draft_items`, redraft); a person's value is never overwritten |
| `useLoad` | `ui/src/components/useLoad.ts` (was in module 1) | moved; module 1 re-exports it |

## Unmerged work in the fork (family office)
Templates `templates/family_office/1/`, routes under `/api/family-office/` (insights, levers, portfolios, evidence, foresight, what-if, ops, sensing, maturity, architecture, build-test, reconciliation), screens for the same, a guard `isOtherIndustryLive` that stops non-insurance companies seeing insurance illustrations, and `north.yaml`-style pack wording read by the catalogue chat. Status unknown to me (not checked for commits). Treat as a source to copy from, as with the main repo.

## Known gaps in the earlier product (so you do not search for what is not there)
Nira as project manager (board, follow-ups); Mentimeter-style voting; briefing and video; anonymous notes; charter versions and templates; business graph from the charter; approver role; owner requests by email link; catalogue Excel export; ontology; Snowflake; the balance ring; module switches per company; package catalogue; egress pseudonymiser. These are new.

## Agent memory (9 Oct)

- The earlier repo's agent memory (`agent_memory.py`, ported as `sh_platform/memory/`, file-per-agent entries merged by similarity) was found and its filters and lock/atomic-write helpers are reused (`sh_platform/memory/filters.py`, `jsonfile`). Its shape (one entries list per agent, replaced wholesale) could not carry per-item source, agent, certainty, supersedes, or a shared memory across agents, so `sh_platform/v1/mem_agent.py` is a new store beside it; the old `/api/memory/*` lists stay and the Settings page shows both.
