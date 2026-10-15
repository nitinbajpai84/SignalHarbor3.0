# Signal Harbor: technical guide for maintainers

For the engineering team that takes over maintenance. Every fact here was checked against the code in this repo on 13 October 2026. Where the code and an older document disagree, this guide follows the code and says so.

Short names used below:

- **Repo** means this repository (`Repo 1.0`).
- **Plane** means one company's data folder and everything inside it.
- **Card** means one small feature with its own file pair in `sh_platform/v1/`.

Related documents:

| Document | Use it for |
|---|---|
| [Technical specification](../spec/TECHNICAL-SPECIFICATION.md) | Full system description as built (12 Oct 2026) |
| [Decisions](../decisions.md) | Why things are the way they are |
| [Architecture diagrams](../architecture/README.md) | Visual views (open the `.html` files) |
| [Demo data](../demo/DEMO-DATA.md) | What each demo screen shows and how to reset it |
| [Running locally](../RUNNING.md) and [Railway deploy](../DEPLOY-RAILWAY.md) | Earlier run and deploy notes |
| [Feature landings](../plan/v6-landings/) | What each recent feature added, file by file |
| [Rules](../../.claude/rules/) | House rules: reuse, data locality, contracts, egress, style, testing |
| [Environment template](../../.env.example) | Names of every setting (no values) |

---

## 1. What the product is

Signal Harbor takes a family office from "what do we want to know" to "what is likely next". An agent drafts at each step. A named person signs each result. Nothing is final until a person signs it.

The demo company is **Evergreen Office**, a synthetic family office. No real client data is in the code, the tests or the demo.

### The four centres

| Centre | What people do there | Main screens |
|---|---|---|
| **Intent** | Talk to North. The signed intent of work and the process map come out of one conversation. | Chat, intent, process map, wall (shared board of ideas) |
| **Action** | Work the day: cases, reconciliations, statements to chase, figures to confirm, approvals. | Today (one page), cases, tickets, Ask Tally |
| **Build** | Design and run the data pipeline. | Projects, Architecture (design pack), Pipelines, Dashboard studio, Operations, Delivery |
| **Consume** | Read published figures. | Today (Morning Note), Financial health, Markets, Reports, What if |

Two more areas sit beside the centres:

- **Map**: the company's ontology, process map, business glossary, data model and lineage.
- **Settings**: people, connectors, jobs and events, teaching the agents, cycle date, model mode.

The **pulse** is the landing page after sign-in. It shows what waits for the person.

### The four agents

| Agent | Role | Where it works |
|---|---|---|
| **North** | Drafts the intent of work (SOW), the process map and the definitions from a conversation. Asks how each named system arrives and how often. | Intent |
| **Span** | Two roles. The **architect** reads the signed intent and drafts the design pack; the head of data approves it. The **builder** connects sources, runs the pipeline on a copy from the mapping sheet, asks for a benchmark, and goes live on approval. | Build |
| **Lumen** | Proposes a starter dashboard, writes briefs and the Morning Note. A different person approves before Consume shows it. | Build, Consume |
| **Tally** | Data analyst of the Action centre. Explains one case, finds timing causes, drafts follow-ups. It never sends anything. | Action |

Agents propose. People act. The approvals are: the intent (sponsor), the design pack and build plan (head of data), go-live (project owner), dashboards (a different person from the author), and cases (the case owner).

Older notes call the builder role "Flow" and the intake helper "Lens" or "Nira". The code still accepts those old names as aliases for Span and Lumen (see `sh_platform/v1/model_modes.yaml`, the `agents:` block). The screens use the current names.

---

## 2. Architecture

### 2.1 Three planes

The diagram to open first is [sh-three-planes-security.html](../architecture/sh-three-planes-security.html). The other main diagrams are:

- [sh-final-architecture.html](../architecture/sh-final-architecture.html): one-page view of parts and two traces.
- [sh-four-centres.html](../architecture/sh-four-centres.html): as built, with each box tied to source.
- [sh-agent-egress.html](../architecture/sh-agent-egress.html): the single exit and its guards.
- [sh-data-layers.html](../architecture/sh-data-layers.html): landing, bronze, silver and gold.
- [sh-local-vs-production.html](../architecture/sh-local-vs-production.html): simple and production modes.
- [sh-deployment-railway.html](../architecture/sh-deployment-railway.html): the Railway set-up.

| Plane | Holds | Does not hold |
|---|---|---|
| **Control plane** | Super admin, module switches, industry packs, domain context | Any company data |
| **Module plane** | Modules and agents. The same code for every company. | State of its own |
| **Data plane** (one per company) | Landing files, warehouse, intents, baseline, context, graph, logs | Anything from another company |

Every path, table and graph is resolved from the signed-in company. A request that would reach another company's plane fails closed. The rule is in `sh_platform/plane.py` (`CompanyPlane.path` raises `CrossCompanyError`).

### 2.2 Request path

1. A request reaches the FastAPI app (`sh_platform/app.py`, factory `create_app`).
2. The auth middleware (`sh_platform/auth/`) checks the session, the CSRF header on writes, and the route's rule in the permission tables. A route with no rule gets 403.
3. Module routes pass the module gate (`sh_platform/modulegate.py`). A switched-off module gets the same 403 as an unknown module.
4. The handler opens the signed-in company's plane and checks the seat (`sh_platform/v1/seats.py`).
5. Agent calls run the read-only loop (`sh_platform/agents/loop.py`). Any model call goes through the router and then the egress gateway.

### 2.3 Egress gateway and its four guards

The egress gateway (`sh_platform/egress/`) is the only way out of a plane. Tools inside a plane have no network access of their own. Every model prompt, internet query and email goes through these guards, in this order.

| Guard | Where in code | What it does |
|---|---|---|
| **1. Counts only** | `sh_platform/egress/aggregates.py`, tool registry in `sh_platform/agents/registry.py` | Internal tools return counts and totals, never rows. A group smaller than five (`MIN_GROUP = 5`) is not shown. Numbers in outgoing text are checked by value, so a held-back figure cannot leave in another format. |
| **2. Minimiser** | `sh_platform/egress/minimiser.py`, `sh_platform/egress/egress_fit.py` | Keeps only what the question needs: the question, the allowed facts and an optional short summary. Records are not sent as lists. |
| **3. Name vault** | `sh_platform/egress/vault.py`, `sh_platform/egress/names.py` | Swaps names for tokens (for example `PERSON_001`) before sending, and maps replies back inside the plane. The vault file (`context/name_vault.json`) never leaves the plane and is never logged. |
| **4. Gateway checks and log** | `sh_platform/egress/gateway.py`, `policy.py`, `rows.py` | Allows only listed hosts over https, with redirects never followed. Blocks any payload with a vault name, a raw record or a held-back figure. Checks the payload shape against allowed keys. Writes a log line (host, decision, count, size, hash, never content) before sending. If the log cannot be written, nothing is sent. |

Other rules at the gateway:

- **Internet is off by default** for each company. It is switched on per company and per module by the company admin (`sh_platform/egress/policy.py`).
- **Outside material is data.** Text from the web, documents or outside tools is labelled untrusted and is never an instruction.
- **Never sent:** raw rows, figures other than totals over groups of five or more, and uploaded documents in full. A few relevant passages can go, tokenised and marked as quoted content (decision D-032).
- **Breaker:** after a provider fails with a billing or key code, calls to it stop for a window (`gateway.py`, `_breaker_check`). Simple mode keeps this in memory; production mode uses Redis.
- **Email** uses the same exit. With `SH_SMTP_URL` set it sends; otherwise it writes an `.eml` file to the plane's outbox so a developer can read it (`sh_platform/egress/email.py`).

Known residual risk (decision A-003): row detection in free text was reduced to structural checks. Table-shaped text typed into a question is not detected. The design relies on one container per company and on tools that return counts only.

### 2.4 Permissions and roles

Roles are declared at the top of `sh_platform/route_permissions.yaml`:

| Role | Who |
|---|---|
| `super_admin` | Control area only. Has no company and never reads company data. |
| `company_admin` | Manages people and settings of one company. |
| `sponsor` | Backs the work, signs the intent. |
| `analyst` | Prepares and reviews work. |
| `head_of_data` | Approves the design pack, build plan and verified map. Held with `analyst`. |
| `approver` | Approves from outside the team (named by the organiser). |
| `participant` | Joins sessions and adds notes. |
| `owner` | A nominated data owner who answers requests and signs a part of the work. |

Seats map roles to actions (`sh_platform/v1/seats.py`). The screens use one role table in `ui/src/shell/roles.ts`, which mirrors the permission file. Change the two together.

---

## 3. Code layout

### 3.1 Top-level folders

| Folder | What is in it |
|---|---|
| `sh_platform/` | The platform: app factory, auth, egress, agents, build pipeline, consume, intents, graph, state, jobs, and the 1.0 cards in `v1/` |
| `modules/` | Three module packages (`m1_intent`, `m2_baseline`, `m3_connect`), each with `manifest.yaml`, `api/`, `agent/`, `contracts/`, `domain/`, `store/`, `tests/` and its own `CLAUDE.md`. Mounted under `/api/modules/<id>/`. |
| `packs/` | Industry knowledge: `family_office/1`, `asset_management/1`, `insurance/1`. Each has YAML files (areas, glossary, KPI tree, feeds, column synonyms). Packs are suggestions, never company policy. |
| `skills/` | Agent playbooks: one folder per agent with `playbook.md`, `questions.md`, `traps.md`, `examples.md` (see section 5.4). |
| `ui/` | React 19, TypeScript, Vite 8. Source in `ui/src/`. Built into `ui/dist` and served by the Python app. |
| `docs/` | Specs, decisions, architecture diagrams, plans, demo notes, handover pack |
| `tests/` | Backend tests grouped by area (`agents`, `auth`, `build`, `egress`, `v1`, and more) |
| `tools/` | Seeds, doctor, dev and serve scripts, worker, Postgres migration, verification, commit helper (`sh_commit.py`) |
| `.claude/` | Rules and agent definitions for the build team (not used at run time) |
| `data/`, `local/`, `graft/`, `.sh-tmp/` | Local only and git-ignored: company planes, prospect files, code index, scratch |
| `Data Model/`, `system design/` | Design material. The Docker image does not copy them, so the code does not read them. |

Top-level files that matter: `Dockerfile`, `railway.json`, `docker-compose.yml` (local Postgres and Redis for production-mode tests), `requirements.txt` (the only requirements file), `pyproject.toml` (pytest settings), `conftest.py` (test fixtures), `.env.example`.

### 3.2 Main packages in `sh_platform/`

| Package or file | Role |
|---|---|
| `app.py` | Builds the app. Mounts the kernel routes, the module loader, the v1 cards, the Build scheduler and the UI. |
| `auth/` | Sessions, CSRF, lockout, the default-deny permission table |
| `route_permissions.yaml` | Kernel permission table and roles |
| `settings.py`, `mode.py` | Environment settings and the simple or production mode check |
| `plane.py` | One isolated folder per company. Refuses paths that leave it. |
| `egress/` | The gateway and its guards (section 2.3) |
| `agents/` | Shared agent runtime: `loop.py` (read-only tool loop), `registry.py` (tools), `guard.py` (figure guard), `runs.py` (run registry), `context.py`, `handoff.py`, `groups.py` (the under-five rule) |
| `build/` | Build pipeline: contracts, runner, schedule, ops, prove, UAT, whatif, blueprint, Archify spec builder, design document. Newer Build cards sit in `v1/`. |
| `consume/` | Feeds, market data, measures, lenses, cards, read range |
| `intents/` | Intent Centre (North's conversation, wall, sources, glossary, catalogue, charter, closure, proving, radar and more). One file per card. |
| `graph/` | The company graph: a projection rebuilt from records. Never edited directly. |
| `profile/` | Company profile and the "bring what you have" uploads |
| `context_docs/` | Company context uploads, text reading and retrieval |
| `memory/` | Agent memory: short term, summaries, long term |
| `pulse/` | What waits for each person (the landing page) |
| `interview/` | The one interview with an invite link per person |
| `state/` | `StateStore` adapter: JSON files (simple mode) or Postgres (production) |
| `jobs/` | Job queue: inline or thread (simple), Redis plus worker (production) |
| `events.py` | Event bus (in-process or Postgres outbox) |
| `warehouse/` | Company DuckDB file helpers (sits beside `v1/wh.py`) |
| `speech/` | Speech provider (Gemini, development and demos only) |
| `mcp/` | MCP server at `POST /mcp` with a bearer token (Settings holds the token routes) |
| `control/` | Super-admin control area and provider list (`providers.yaml`) |
| `packs.py` | Pack loader. Reads `packs/<industry>/<version>/` by parameter. |
| `module_loader.py`, `modulegate.py`, `manifest.py` | Finds, mounts and gates module packages |
| `webui.py` | Serves `ui/dist` as the last route, with a fallback for deep links |
| `perf.py` | Logs any route slower than the threshold |

### 3.3 Naming in `sh_platform/v1/`

`v1/` holds the 1.0 feature cards. Each card is a pair: `<card>_routes.py` (the HTTP routes) and `<card>.permissions.yaml` (its permission lines), plus the logic in one or more `<card>_*.py` files. The file names carry the card codes from the build plans. The letter is a workstream code, not a meaning. Read the module docstring first.

| Prefix | Area | Examples |
|---|---|---|
| `a1`, `a5` | Span's conversation with the architect; the six-step "where is this from" trail | `a1_chat.py`, `a5_trail.py` |
| `b1` to `b11` | **Build** centre: design (b1), scan (b2), mapping sheet (b3), Flow loads (b4), ops (b5), build plan and run (b6), dashboard studio (b7), verify (b9), design pack (b10), builder (b11) | `b6_run.py`, `b6_schedule.py`, `b7_studio.py`, `b11_builder.py` |
| `c1` to `c5` | **Consume** and shared: KPI cards (c1), offers (c2), Lumen's chat (c3), context library (c4), connectors (c5) | `c5_connect/` (connector kinds) |
| `cx_*`, `cy` | Consume dashboards and Lumen (`cx_dash`, `cx_lumen`); cycle date (`cy`) | `cy_routes.py` sets the company's business day |
| `d1` | Delivery of published dashboards (consume page, Morning Note, webhooks) | `d1_delivery.py` |
| `doc_*` | Local document index and passage search. Embeddings run on this machine. | `doc_index.py`, `doc_embed.py` |
| `e0a`, `e0b`, `e0c` | Data model catalogue and versions; sheet mappings; landing zone and loads | `e0a_catalogue.py`, `e0c_load.py` |
| `e1*` | Evidence rules: as-of queries, the one writer of evidence rows, reports, access | `e1_write.py` (append-only), `e1_asof.py` |
| `e2*` | Document intake, field extraction and identity matching | `e2_match.py` |
| `e3*` | Calculation library, reconciliation (cash, NAV, limits, trades), rules register, impact | `e3_recon.py` |
| `e4*` | Cases (the Action Desk's records) and the refusal guard | `e4_cases.py`, `e4_guard.py` |
| `e5*` | CIO brief and the role pulse | `e5_pulse.py` |
| `e6*` | Agent run trace (one trace id per piece of work) | `e6_trace.py` |
| `f1` | Data engineer's conversation with Span | `f1_chat.py` |
| `g1` to `g4` | Project access, go live and run book, benchmark sheet, deviations | `g2_runbook.py`, `g4_deviations.py` |
| `i1` to `i6` | Company page (i1), intent of work (i2 to i4), document reading (i5), North's conversation (i6) | `i2_north.py`, `i6_chat.py` |
| `k1` to `k12` | Library and access, company map, office view, manager inbox, benchmarks, attribution, liquidity, SOP, daily numbers, pain-point demo | `k6_liquidity.py`, `k7_benchmark.py` |
| `l2`, `l3` | Proposed changes (waiting for a person), library folders | `l2_proposals.py` |
| `m1` | The company map | `m1_map.py` |
| `mem_*` | One memory for every agent, the context map, conversation summaries | `mem_context.py` |
| `n1`, `n2` | Tally (the Action analyst) and comments with history | `n1_tally.py` |
| `p1` to `p5` | Projects and artefacts (p1), assignments and the Action landing (p2), benchmarks (p4), go live and tickets (p5) | `p2_pulse.py` |
| `r1` | Run list for the data team (test and production runs) | `r1_runs.permissions.yaml` |
| `t1`, `t2` | Templates for outputs, the ticket centre | `t1_templates.py` |
| `teach*` | Teaching the agents (section 5.3) | `teach.py` |
| `v1_voice` | Speech in and out for agent screens | `v1_voice_routes.py` |
| `w3_jobs` | Jobs and events admin page, and the event stream | `w3_jobs_routes.py` |
| `x2`, `x5` | Pulse-style "what waits" list (x2); extraction specs and review queue (x5) | `x5_extract.py` |
| `agent_tools.py`, `lumen_tools.py`, `span_tools.py`, `tally_tools.py` | Each agent's read-only tools for the loop | |
| `router.py`, `model_modes.yaml` | Model router and the Testing and Real use modes (section 5.1) | |
| `wh.py` | The company warehouse: one DuckDB file per company, `connect(plane)` | |

The `sh_platform/v1/__init__.py` docstring is the rule book for this folder: every feature lives in its own pair of files, so builders never edit a shared file.

### 3.4 How routes are found

Route discovery is automatic. Nothing is registered by hand.

1. **Code routes.** `sh_platform/v1/__init__.py` (`install`) imports every `sh_platform/v1/*_routes.py`, and includes its `router`. Each router gets the intent gate dependency (`g1_access.intent_gate`). A file with no `router` is logged and skipped.
2. **Permission lines.** `sh_platform/auth/permissions.py` loads `route_permissions.yaml` and then every `sh_platform/v1/*.permissions.yaml` (`extra_permission_files()`). A card's line is added only if the kernel file does not already declare that route, so a card cannot widen a kernel route.
3. **Default deny.** Any route with no line gets 403. The server also refuses to start on a bad permission line (for example an unknown role).
4. **Modules.** `sh_platform/module_loader.py` reads `modules/<id>/manifest.yaml`. Each manifest route must match the permission table, and each router route must be in the manifest. A mismatch stops the start with a plain message. A broken module is skipped and the others still load.

Permission line format:

```yaml
routes:
  GET /api/v1/build/{iid}/design: {roles: [company_admin, analyst, sponsor, owner, approver, participant]}
  POST /api/v1/build/{iid}/design: {roles: [company_admin, analyst]}
```

Also valid: `public: true`, `authenticated: true` (account-level routes only) and `MOUNT /prefix/{path}` (static files only).

### 3.5 UI layout (`ui/src/`)

| Folder | What is in it |
|---|---|
| `ui/src/v1/` | One folder per card, 63 in all (`a5/`, `b6/`, `k3/` and so on). Each card owns `routes.tsx`, which exports `routes`. |
| `ui/src/v1/index.tsx` | Globs `./*/routes.tsx` and mounts every route inside the centre shell. A new screen needs no edit to `App.tsx`. |
| `ui/src/shell/` | The centre frame (`CentreShell.tsx`), the role table (`roles.ts`), redirects, top bar |
| `ui/src/modules/m1_intent`, `m2_baseline`, `m3_connect` | Module screens for the three module packages |
| `ui/src/intents/` | Intent screens (views and panels loaded with `import.meta.glob`) |
| `ui/src/api/` | The one typed API client |
| `ui/src/components/`, `design/`, `styles/` | Shared components, design tokens, stylesheets (legacy styles copied from the earlier product) |
| `ui/src/pages/`, `live/`, `pulse` (under `v1/`) | Other pages and the live event stream |

Client state: the screens read server data through the typed client. Browser storage is not used for records.

---

## 4. Data

### 4.1 The per-company plane

Each company lives under the data root (`SH_DATA_ROOT`, default `./data`):

```
<data root>/
  _control/                  accounts, companies, entitlements, seed_credentials.txt (never printed)
  _models/                   local embedding model cache
  <company>/
    landing/                 originals as received (never edited)
    warehouse/               evidence.duckdb (main warehouse), sandbox.duckdb, restricted marts file
    intents/                 North's threads, signed intents of work (sow.json)
    baseline/  context/      context (egress log, model cost log, run registry, name vault)
    graph/  index/  library/  projects/  build/  consume/  cases/  model/  templates/  tickets/
    ops/                     run log (runs.jsonl, run_steps.jsonl)
```

The planes are listed in `sh_platform/plane.py` (`AREAS`). Other folders appear as features need them.

Plane rules:

- Every company gets its own folder, and nothing reads another company's folder.
- Signed content is read-only. A draft never overwrites a human edit.
- The seed and demo never write outside the company folder.

### 4.2 The warehouse: bronze, silver and gold

The warehouse is one DuckDB file per company: `<company>/warehouse/evidence.duckdb`. Code opens it only through `connect(plane)` (`sh_platform/v1/wh.py`). Facts are append-only: a correction is a new row that points to the row it supersedes (`e1_write.py` is the only writer of evidence rows).

| Layer | Content | Rule |
|---|---|---|
| **Landing** (files) | Originals as received | Kept; never edited |
| **Bronze** (`bronze_*` tables) | Loaded as is | No business meaning added |
| **Silver** (core table names) | The company model: cleaned and typed | Changed only through model versions |
| **Gold** (`gold_*` tables) | Reporting tables for each project, built from the signed mapping sheet | Types and definitions come from the design pack |

Tools such as DBeaver see schemas `bronze`, `silver` and `gold`. These are **alias views** over the real tables in `main` (`silver.position_snapshots`, `gold.<x>` for `gold_<x>`, `bronze.<x>` for `bronze_<x>`). Real tables are never renamed. The aliasing is idempotent (`e0a_catalogue.py`, `alias_layers`).

Restricted marts (for example pay or HR data) live in a separate DuckDB file that only listed people can read. Query tools read a read-only copy, refreshed after each load (decision A-065).

### 4.3 The core model

- **Source of truth:** `docs/v2/evidence-to-action-mvp.dbml` (DBML). Generated SQL sits beside it: `evidence-to-action-mvp.duckdb.sql` and `evidence-to-action-mvp.postgres.sql`. A family-office-only model is in `family-office-data-model*.dbml`.
- **Size:** 42 tables in 9 groups (checked: 42 `Table` blocks in the DBML).
- **Groups:** access (5), master data (4), intake (6), documents and retrieval (3), observations (7), rules and benchmarks (4), intents and outputs (7), exceptions and pulse (5), agents (1).
- **Catalogue:** `sh_platform/v1/e0a_catalogue.py` holds the governed catalogue. Version 1 is the core file. A company adds **extensions** (new tables or new columns). It never drops or changes a core column type. A proposal waits in state `proposed` until the head of data approves it.
- **Warehouse follows the catalogue:** the warehouse gets new tables and columns only. Constraints beyond primary keys and not-null are not added.

### 4.4 Lineage

Each figure can be traced from Consume back through gold, silver and bronze to the landing file or API call. The trail uses the mapping sheet, batch and source-record keys, and `metric_evidence`. The trail screen is `sh_platform/v1/a5_trail.py`.

### 4.5 Simple mode and production mode

`sh_platform/mode.py` picks the mode at start-up:

- **Production** when both `DATABASE_URL` and `REDIS_URL` are set.
- **Simple** when neither is set.
- **Refused start** when only one is set. The server stops with a plain message rather than guess where data lives.

| Part | Simple mode | Production mode |
|---|---|---|
| Company state | JSON files, atomic write, one lock per file (`state/` `FileStore`) | Postgres (`PgStore`): one table per store kind, JSONB, compare-and-set version (`Conflict` on a clash) |
| Jobs | Run inline, or one background thread (`LocalQueue`) | Redis queue, retries with doubling wait, failed list. `tools/worker.py` runs the jobs. A lease lets another worker take a dead worker's job. |
| Events | In-process, last 500 kept | Postgres outbox written in the caller's transaction; each consumer runs once per event |
| Cache, rate limit, breaker | Process memory | Redis (shared by all replicas) |
| Warehouse (DuckDB), uploads, logs | Volume | Volume (same as simple mode) |

Behaviour is the same in both modes, and the screens do not change.

**Honest position (from the specification):**

- The `StateStore` adapter, the Postgres schema, `tools/migrate_to_postgres.py` (idempotent, `--dry-run` available) and `tools/parity_check.py` are built.
- About 350 call sites still read and write JSON files in both modes. Moving each store through the adapter is planned.
- Postgres connections open per call. No pool yet.
- Only one web replica may run. DuckDB takes one writer process at a time, so the web process and the worker share the volume and write in turn.

---

## 5. Agents and models

### 5.1 The model router and its modes

The router (`sh_platform/v1/router.py`) picks one of three tiers for each agent call, by rules only (no model call makes the choice):

| Tier | Use |
|---|---|
| **fast** | Simple reads and replies |
| **specialist** | Most agent work |
| **manager** | The hardest calls |

Each company has a mode. The mode switches without a restart:

| Mode | Where the models come from | Notes |
|---|---|---|
| **Testing** (default) | `sh_platform/v1/model_modes.yaml`: cheap tool-capable OpenRouter models (`qwen/qwen3.7-flash` for fast; `openai/gpt-oss-120b` for specialist and manager) | Used by demos and tests |
| **Real use** | Environment names `SH_MODEL_FAST`, `SH_MODEL_SPECIALIST`, `SH_MODEL_MANAGER`, and an alternate per tier `SH_MODEL_<TIER>_ALT` | Refused on a public link unless `SH_ALLOW_REAL_MODE=1` is set |

Fallbacks, each logged as a line in the company's cost log (`context/model_costs.jsonl`):

1. **Retry up, never down.** An unusable reply (empty, wrong shape, or a figure the guard would rewrite) is asked once more on the next tier.
2. **Provider failure.** The call goes to the tier's alternate model in Real use. In Testing it goes to the next tier.
3. **Tier above unreachable.** The reply in hand goes to the guard. A manager call that cannot be reached tries the specialist once. That is the only step down, and it is for availability, not quality.
4. **Same model in both tiers.** No retry is made to a tier with the same model. The step is logged as "no stronger model in this mode".

Other switches:

- `SH_ROUTER=off` pins every call to the specialist model.
- `SH_DAILY_MODEL_CAP_USD` caps spend per company per UTC day, read from the cost log. After the cap, agents answer from rules with a plain note.
- `SH_CHAT_TURNS_PER_HOUR` limits chat turns per account per hour (HTTP 429 after).
- Prices sit in `model_modes.yaml`. A model not listed is priced at its tier default and marked as an estimate. Never zero.

### 5.2 The number guard

File: `sh_platform/agents/guard.py`.

**Why it exists.** A language model can state a figure that no tool returned. A family office cannot act on an invented number. The guard checks every figure in an answer against the facts that the run's tools recorded. A figure that cannot be traced is replaced with "not available yet", and the screen says what is missing.

Rules (from the module docstring; these are the documented limits):

- A number counts if it equals a recorded fact in sign and size. A percentage and a count are not told apart.
- Facts with a group size under five are never a source. This follows the under-five rule.
- Ignored: ids such as `D-013`, full dates, quarter and half labels, years in a date context, file names, column types, and list ordinals. A known limit: a line starting "99. items" reads as a list number.
- Numbers written as words are checked only when they count something a tool talked about.
- The guard reads the tool's own sentences as facts, so a figure keeps the word it counts (a tool said "4 tables", so "4 entities" is replaced).

Tests: `tests/agents/`, and `tests/egress/`.

### 5.3 Teaching the agents

File: `sh_platform/v1/teach.py`. Routes: `sh_platform/v1/teach_routes.py`. Screen: `ui/src/v1/teach/`.

People add a file or a short note for **one** agent. Stored per company in `knowledge/`:

- `index.json`: one entry per item (title, agent, who taught it, when, on or off, always flag)
- `<agent>/<id>__<name>`: the file, or a note saved as `.txt`
- `trail.jsonl`: every add, switch-off, switch-on and replace. The Activity trail reads it.

**Rights** (`RIGHTS` in `teach.py`, default deny):

| Agent | Who may teach it |
|---|---|
| Span | head of data, analyst, company admin |
| North | company admin |
| Tally | owner, sponsor, approver, company admin |
| Lumen | owner, head of data, company admin |

**Retrieval.** At answer time the chat route opens a scope (`TeachMiddleware`, paths in `CHAT_PATHS`). `run_agent` calls `reference_block()`. It returns at most four passages, about 1,500 characters in all, from the agent's **active** items that fit the question. Search uses word matching (BM25) plus local bge-small meaning vectors. Nothing leaves the machine except those few passages, which ride in the next model call through the gateway with names tokenised. The block goes in as its own user message and is labelled as quoted reference material. The route's JSON reports which items were used.

**Always-on house rules.** A note marked "always" rides with every question for that agent, up to 4,000 characters in all. Use these for short standing rules only.

Errors never cost the person an answer. `reference_block` catches its own errors and logs a warning.

### 5.4 Playbooks

Folder: `skills/<agent>/` (repo copy). Agents: `north`, `span`, `lumen`, `tally`, plus folders `briefing`, `consumer`, `data`, `flow`, `intake`, `investigation` that map to the aliases in `model_modes.yaml`.

| File | Holds |
|---|---|
| `playbook.md` | How the agent works and the domain background (for example how a family office runs its month) |
| `questions.md` | Questions the agent should ask |
| `traps.md` | Mistakes to avoid |
| `examples.md` | Worked examples. North also has `sop.md`; Lumen has `managers.md`. |

`sh_platform/v1/skill_loader.py` (`load_skill`) joins these files into one block for the agent's static prompt. The text is trimmed to 6,000 characters. A missing folder returns an empty block, so a card never breaks without its skill.

**Always on.** The playbook is in the static prompt for every call of that agent. It is not searched. Only taught items are searched.

**Company override.** A company's own files at `<plane>/skills/<name>/*.md` replace the repo file with the same name (T1 rule). A company file saved under an old agent name still applies to the new name (`tests/test_skill_loader_retired.py`).

### 5.5 Agent loop

File: `sh_platform/agents/loop.py`.

- Only tools registered as read-only ever run. The tool registry checks the gate on every listing and every call (`registry.py`).
- A **propose** tool collects a checked item in the result. The caller validates it and files it. Nothing is written by the loop itself.
- Figures returned by the run's own tools count as recorded facts for the guard.
- Retries and timeouts of the model call belong to the gateway transport, not the loop.
- Each run is recorded in `context/run_registry.jsonl` (agent, module, status, steps, tools called, numbers replaced), and its steps in `context/run_steps.jsonl`. The trace view is `sh_platform/v1/e6_trace.py`; company admins see it at `GET /api/v1/agent-runs`.

---

## 6. Running locally

### 6.1 Prerequisites

| Tool | Version | Source |
|---|---|---|
| Python | 3.11 or later | `pyproject.toml` (`requires-python >=3.11`) and `Dockerfile` (python 3.11 slim) |
| Node.js | 22 | `Dockerfile` (node 22 slim). The UI uses Vite 8, React 19 and TypeScript 7. |
| Docker | Optional | Only for the local Postgres and Redis set-up (`docker-compose.yml`) |

### 6.2 Install

```bash
# from the repo root
python -m pip install -r requirements.txt
cd ui
npm ci            # uses package-lock.json, as the Dockerfile does
cd ..
```

Copy `.env.example` to `.env` and fill in the names you need. Never commit `.env`. The file is git-ignored. Model keys are optional for simple tests because the model provider can be set off (`SH_MODEL_PROVIDER=off`).

The embedding model downloads on first use into `data/_models`. Tests never load it. The conftest sets the embedding function to off.

### 6.3 Check the set-up

```bash
python tools/doctor.py
```

It prints PASS or FAIL per check and the action to take for each FAIL. Checks cover ports, a writable data root, pack loading, the model provider and the speech provider. It never prints a key.

### 6.4 Seed demo data

| Command | What it does |
|---|---|
| `python tools/seed.py` | Four illustrative companies (the `COMPANIES` table in `tools/seed.py` lists them, one of them a single-person company) and their people. Safe to run again. Writes passwords only to `<data root>/_control/seed_credentials.txt`. |
| `python tools/seed_demo_boot.py --data-root <root>` | The public-demo seed: seeds the Evergreen Office universe, then runs `seed_demo_ready.py`. Idempotent and never wipes. |
| `python tools/seed_10uc.py --data-root <root>` | Ten use cases of history on Evergreen Office (13 months). Used by the demo boot and the tests. |
| `python tools/seed_demo_boot.py --reset --data-root <root>` | Empties the root and seeds again. Refuses the repo's `data/` unless `--allow-repo-data` is given. |

Note: `RUNNING.md` says the seed makes three companies. The code in `tools/seed.py` makes four. Trust the code.

### 6.5 Start the app

Two ways:

- **Developer mode (backend and Vite dev server):** `python tools/dev.py`. Backend on `127.0.0.1:8200`, UI dev server on `8201`. Ctrl+C stops both. Note: `ui/vite.config.ts` sets the Vite port to 8401 and proxies `/api` to 8400, which is the port `tools/serve_v1.py` uses. Either set the proxy target to match or run the built UI. Check before you rely on either.
- **Built UI on one port:** `ui/dist` is served by the Python app. Build with `cd ui && npm run build` (runs `tsc --noEmit` then `vite build`). Then run `python tools/serve_v1.py` (port 8400), or the production command in section 7.

### 6.6 `tools/serve_test.py`: one tester, one server

Gives each tester a private port and a private copy of the data:

```bash
python tools/make_test_env.py t01 --seed                     # private copy, seeded fresh
python tools/serve_test.py --port 8501 --data-root .sh-tmp/testenv/t01/data
```

`make_test_env.py` without `--seed` copies the golden data root. `--golden` rebuilds the golden root. The scheduler is off unless `--scheduler` is given. The server log goes to `<data-root>/../server.log`, not the console. Use ports 8200 to 8299 for local work.

### 6.7 Work with real files

The company folders in `data/` may hold a live DuckDB file. A running server holds it open. On Windows a second process cannot copy a locked file. Stop the server, or use `serve_test.py` with a copy.

---

## 7. Deploying

### 7.1 Railway (the current set-up)

Files: `Dockerfile`, `railway.json`, `tools/start.sh`.

**Image (two stages):**

1. Node 22 builds the UI (`npm ci`, `npm run build`).
2. Python 3.11 slim installs `requirements.txt` (plus `libgl1`, `libglib2.0-0`, `libxcb1` for the picture reader), copies `sh_platform/`, `modules/`, `packs/`, `skills/`, the seed and worker tools, the data model SQL and the synthetic universe, and the built UI. `/app/data` links to `/data`.

Baked-in settings: `SH_MODE=prod`, `SH_DATA_ROOT=/data`, `SH_SCHEDULER=on`, `SH_ROUTER=on`, `SH_MODEL_PROVIDER=openrouter`.

**Services:** one web service (the container), one persistent volume at `/data`, and, for production mode, one Postgres service and one Redis service. The web container and the worker run **in the same container**, because the DuckDB volume attaches to one service. Run one replica only.

**Start order (`tools/start.sh`):**

1. `python tools/seed_demo_boot.py --data-root "$SH_DATA_ROOT"`: seeds an empty volume. Never wipes. Logins go to `/data/_control/seed_credentials.txt`, not to the log. Each step is idempotent.
2. If `DATABASE_URL` and `REDIS_URL` are both set: `python tools/migrate_to_postgres.py "$SH_DATA_ROOT"` (idempotent), then `python tools/worker.py &`.
3. `exec uvicorn sh_platform.app:create_app --factory --host 0.0.0.0 --port "${PORT:-8200}" --proxy-headers --forwarded-allow-ips="*"`.

Note: the start script defaults to port 8200 if `PORT` is unset. Railway sets `PORT`.

**Health check:** `GET /api/health`, timeout 300 seconds (first boot seeds the demo in about 30 seconds). `railway.json` restarts on failure, up to 5 times.

**Deploys:** Railway builds the Dockerfile and deploys automatically on every push to `main` (seen on 13 Oct 2026: each push to main produced a new deployment within minutes). Keep `main` protected and work through pull requests.

**Variables:** names only in the repo. Set values with `railway variables --set NAME="value"`. The main names are listed in section 9.3.

**Public link settings** (from `DEPLOY-RAILWAY.md`): Testing mode only; daily spend cap of 2 USD per company; 30 chat turns per account per hour; super-admin routes off; no super-admin seeded; voice off; scheduler on. Do not set `SH_ENABLE_SUPERADMIN=1` or `SH_ALLOW_REAL_MODE=1` on a link others can open.

### 7.2 Reset the demo

```bash
railway ssh -- sh -c 'python tools/seed_demo_boot.py --reset --data-root "$SH_DATA_ROOT"'
railway redeploy        # the running app keeps the old warehouse file open: restart it
```

In production mode, also empty the app records in Postgres:

```bash
railway ssh -- sh -c 'python tools/seed_demo_boot.py --reset --reset-db --data-root "$SH_DATA_ROOT"'
```

`--reset-db` needs `--reset` and `DATABASE_URL`. It truncates only the `sh_state_*` and `sh_outbox*` tables. It never drops a table.

A simpler reset that `DEPLOY-RAILWAY.md` gives: `railway ssh`, then `rm -rf /data/evergreen /data/_control`, `exit`, `railway redeploy`. The next boot seeds fresh with new passwords.

### 7.3 Another cloud, or a client's own environment

The same container runs anywhere that runs a Docker image with a persistent volume:

1. Build the image from `Dockerfile`.
2. Mount a persistent volume at `/data` and set `SH_DATA_ROOT=/data`.
3. Set `SH_SESSION_SECRET` (32 characters or more outside dev mode), `SH_MODE=prod` and the model variables you need.
4. For production mode, provide a Postgres and a Redis, and set `DATABASE_URL` and `REDIS_URL` together. Run the worker in the same container, as `start.sh` does.
5. Run one replica. Point the health check at `/api/health`.
6. Keep the data on the client's volume or database. Real client data never leaves the client's environment (rule 0).

Local production-mode rehearsal: `docker compose up -d` starts Postgres on `127.0.0.1:5433` and Redis on `127.0.0.1:6380` (set `SH_PG_PASSWORD` and `SH_REDIS_PASSWORD` in your shell first). Then set `DATABASE_URL` and `REDIS_URL` as shown in `docker-compose.yml`. The web server and `tools/worker.py` run on the host.

---

## 8. Tests

### 8.1 Backend (pytest)

Settings: `pyproject.toml` (`testpaths = tests, modules, sh_platform`; `pythonpath = .`). Fixtures: `conftest.py` (embedding model off; background embedding runs inline).

```bash
python -m pytest -p no:cacheprovider --basetemp=<a scratch folder outside the repo>
python -m pytest tests/egress -p no:cacheprovider --basetemp=<scratch>     # one area
```

Tip: give every run a `--basetemp` outside the repo, on a drive with space. On Windows, `conftest.py` sets `PYTEST_DEBUG_TEMPROOT` to `D:/Temp` if that folder exists. The team once lost 46 GB of C: space to pytest temp folders. The test rules say every test writes to a temp folder, and a guard fails any test that leaves a file in the repo.

Counts (13 Oct 2026): **6,478 tests collected** (parametrised cases counted separately). Full backend run that day: **4,310 passed, 74 skipped, 1 failed**; the failure was the warehouse lock test clashing with a running local server, and it passes on its own. Full UI run: **1,814 passed**, plus one flaky voice test that passes on its own.

### 8.2 Frontend (vitest and TypeScript)

```bash
cd ui
npx tsc --noEmit        # type check (also: npm run typecheck)
npx vitest run          # all UI tests (also: npm test)
npx vitest run src/v1/b7   # one folder
```

Counts (13 Oct 2026): **1,757 tests listed** by `vitest list`. The specification's last full run was 1,755 passed.

### 8.3 Known flaky or fragile tests

| Test | Symptom | Why | What to do |
|---|---|---|---|
| UI `ui/src/v1/voice/voice.test.tsx` (the "Speak" test) | Can fail under full-suite load, pass alone | Timing under parallel workers. Ledger notes record it as a load flake. | Rerun alone. Raise the timeout only if it keeps failing. |
| Warehouse lock test `tests/v1/test_b6_run_lock.py` | A sandbox run fails while a server holds the warehouse file open | Windows refuses to copy a file that another process has open. The test opens the shared connection on purpose. | Run it with no server on the same data root, or keep the test as is and read the message. `tests/conftest.py` skips locked `.duckdb` files when it copies data. |
| `tests/v1/test_wh_lock.py` | Not flaky. It checks that a second process is refused with a message naming the server. | Intended behaviour | None |
| `tests/egress/test_hardening.py` timing tests | Can fail under heavy load | Timing-sensitive checks (noted in the P1-02b brief) | Rerun alone |
| `tests/context_docs` deep-nesting timing test | Can fail on a slow machine | Timing check on a hostile HTML page (noted in the review of the context-docs card) | Rerun alone |
| Voice backend test (`test_voice`, listed as out of date in `docs/test/BACKEND-SUITE-10OCT.md`) | Fails on the current code, not flaky | The test expects the old failure shape and not the `note` field added later | Update the assertion to the current shape |

Also check `docs/test/BACKEND-SUITE-10OCT.md` and `docs/test/SUITE-W3.md` before you rely on any suite count.

### 8.4 Test rules (from `.claude/rules/testing.md`)

- Write the failing test first for any behaviour change or defect.
- Every module runs against two industries and an empty company (no hard-coded industry).
- Every screen is checked in five states: loading, empty, error, refused, populated.
- Security tests: another company's data is unreachable, a role without access is refused, a switched-off module is refused.
- Agent model calls are stubbed in unit tests. Live calls run only in the evals suite (`tests/evals`, `tools/run_evals.py`).
- Test accounts are separate per agent and per person. Never test on a real person's account.

---

## 9. Conventions

### 9.1 House style (from `.claude/rules/house-style.md`)

- **Python:** type hints; `logging`, not `print`; no bare `except`; small functions.
- **SQL:** lowercase keywords; CTEs over subqueries; one column per line. Platform SQL is generated, never hand-written.
- **TypeScript and React:** function components; typed props; no `any`; server data through one typed API client.
- **Shortest working change.** No abstraction with one implementation; no scaffolding for later.
- **File names say what they hold.** No `utils.py` or `helpers.ts` grab-bags.

### 9.2 Core rules

| Rule | Where to read it | In one line |
|---|---|---|
| Reuse first (D-031) | `.claude/rules/reuse-first.md`, `docs/reuse-inventory.md` | Check the earlier product and the inventory before you build anything. Copy freely. |
| Data locality (rule 0) | `.claude/rules/data-locality.md` | Real client data never leaves the client's environment. Tests and demos use synthetic data only. |
| Contracts | `.claude/rules/contracts.md` | Never invent a table, column, threshold or rule. Write it under open questions instead. |
| Default deny | `route_permissions.yaml` | A route with no permission line is refused. |
| Egress | `.claude/rules/egress.md` | One exit. Tokenised names, no raw rows, allowlist, log, under-five rule, internet off by default. |
| Industry is a parameter | `.claude/rules/industry.md` | No module names an industry. Pack content is labelled as a suggestion. |
| Signed content is read-only | `.claude/rules/modules.md` | A draft never overwrites a human edit. It records a proposal beside it. |
| No secrets in code | `docs/RUNNING.md` | Keys live in the environment. Code, docs and the repo hold names only. |
| Author is not reviewer | `CLAUDE.md` | The person or agent who writes a change never reviews it. Packages land through `tools/sh_commit.py`. |

### 9.3 Settings (names only)

Values are never in the repo. See `.env.example` for the full list.

| Name | What it does |
|---|---|
| `SH_MODE` | `dev` (default) or `prod`. `prod` turns on secure cookies and the strict checks. |
| `SH_DATA_ROOT` | Data root folder (default `./data`; `/data` on Railway) |
| `SH_SESSION_SECRET` | Session signing. 32 characters or more outside dev. Set by hand. |
| `SH_EGRESS_DEFAULT` | Default internet switch for a new company (`off`) |
| `SH_MODEL_PROVIDER` | Which model provider the gateway uses (for example `openrouter`). `off` switches model calls off. |
| `OPENROUTER_API_KEY`, `GOOGLE_API_KEY` | Provider keys (values set in the host's variables). `GOOGLE_API_KEY` also enables speech in development. |
| `SH_MODEL_FAST`, `SH_MODEL_SPECIALIST`, `SH_MODEL_MANAGER`, `SH_MODEL_<TIER>_ALT` | Real use models per tier |
| `SH_ROUTER` | `off` pins every call to the specialist model |
| `SH_DAILY_MODEL_CAP_USD`, `SH_CHAT_TURNS_PER_HOUR` | Spend cap and chat rate limit (0 turns each off) |
| `SH_ALLOW_REAL_MODE`, `SH_ENABLE_SUPERADMIN` | Keep off on any public link |
| `SH_DEMO_PASSWORD` | Optional shared password for every seeded demo account (12 characters or more) |
| `DATABASE_URL`, `REDIS_URL` | Both set turns on production mode. Only one set stops the start. |
| `SH_SCHEDULER` | `on` (default) or `off`. Runs the pipeline and delivery schedules. |
| `SH_SMTP_URL` | Email server. Unset means emails go to an outbox file. |
| `SH_PUBLIC_BASE_URL` | Base address for links in emails. Set it in production. |
| `SH_SPEECH_PROVIDER` | `gemini`, `stub` or `off`. Speech is for development and demos only. |
| `FRED_API_KEY`, `FINNHUB_API_KEY` | Market data connectors (optional) |
| `SH_EMBED_MODEL` | Embedding model name. Default is a local bge-small model. Changing it re-embeds the document index. |
| `SH_MCP_TOKEN` | Bearer token for the MCP endpoint |
| `PORT` | Set by Railway |

### 9.4 Speech, embeddings, outside sources

- **Speech** is on the Gemini free tier, for development and demos only. The free tier may use content to improve Google's products. Production should use a paid tier or a local engine. Speech runs only in dev mode (decision D-028).
- **Embeddings** run locally. A passage's text is never sent to an embedding service.
- **Outside sources** (market data, the web) come through the gateway and are labelled as outside material.

---

## 10. Maintenance

### 10.1 Add a route

1. Write the logic in a `sh_platform/v1/<card>_*.py` file. Keep it free of model calls unless the card is an agent.
2. Add the router in `sh_platform/v1/<card>_routes.py` (export `router`). Check the seat or role inside the handler too.
3. Add a permission file `sh_platform/v1/<card>.permissions.yaml` with a line per route. Use roles, not `public` or `authenticated`, for any route that reads or writes company data.
4. Add the screen in `ui/src/v1/<card>/routes.tsx` (export `routes`). The router finds it.
5. Add tests: the route is refused for a role without access; another company's plane is unreachable; a switched-off module is refused.
6. Run `python -m pytest <your test files> --basetemp=<scratch>` and `npx vitest run <your folder>`.

Module routes (`modules/<id>/`) also need a line in `manifest.yaml` that matches the permission table. The module loader checks both.

### 10.2 Add an agent tool

1. Write the tool in the agent's tools file (for example `sh_platform/v1/tally_tools.py`), or in `agent_tools.py` if every agent needs it.
2. Register it on the `ToolRegistry` with the read-only flag set. The registry refuses a tool that is not read-only unless it is a propose tool.
3. Return counts, totals and field names. Never return rows. Groups under five are hidden by the registry.
4. A tool that proposes a change returns it as a checked item. The caller validates it and files it. The loop never writes.
5. Test the tool and the guard: a figure from the tool must be quotable, and a figure not from a tool must be replaced.

### 10.3 Add a chart kind

1. Add the name to `KINDS` in `sh_platform/v1/b7_studio.py`. If it is a view kind (only shown as a view, not a stored tile), add it to `VIEW_KINDS` as well.
2. Draw it in `ui/src/v1/cxui/ChartKinds.tsx` (and `Chart.tsx` for the switch). The studio screens are in `ui/src/v1/b7/`.
3. Add a check rule to `sh_platform/v1/b7k_checks.py` if the chart can mislead (for example double counting).
4. Test the spec on the server and render it once in the UI.

### 10.4 Make an agent teachable

1. Add the agent key to `AGENTS` and a rights line to `RIGHTS` in `sh_platform/v1/teach.py`.
2. Add the agent's chat route pattern to `CHAT_PATHS` in the same file, so the scope opens for that chat.
3. Add the agent's folder in `skills/<agent>/` with a playbook, questions, traps and examples.
4. Make sure the agent's aliases are in `model_modes.yaml` if it needs old names.
5. Test: a person without rights is refused; an active item is retrieved for a matching question; an "always" note rides with a question that does not match it.

### 10.5 Where logs and run IDs are

| What | Where | Notes |
|---|---|---|
| Pipeline and build runs | `<company>/ops/runs.jsonl` and `run_steps.jsonl` | One run id per run (test or production). Start line then finish line. Never deleted. Shown on Operations and `GET /api/v1/ops/runs`. |
| Agent runs | `<company>/context/run_registry.jsonl` and `run_steps.jsonl` | One uuid per agent run. Company admin reads them at `GET /api/v1/agent-runs`. |
| Model calls and cost | `<company>/context/model_costs.jsonl` | One line per call and per fallback step. Read at `GET /api/v1/router/costs`. |
| Egress (every outside call) | `<company>/context/egress_log.jsonl` | Host, decision, masked count, size, hash. Never content. |
| Name vault | `<company>/context/name_vault.json` | Real names. Never logged or sent. |
| Jobs and events | Settings, Jobs and events page; `GET /api/v1/jobs`; `GET /api/v1/events/stream` | Failed jobs can be sent again from the page. |
| Server log (local) | `<data root>/../server.log` when started with `serve_test.py` | Otherwise standard output |
| Slow routes | Server log at WARNING | Any route over the threshold in `sh_platform/perf.py` |
| Railway | Railway log view for the service | The seed prints a failed step's reason, never a key |

Trace IDs follow one piece of work from arrival to pulse (`sh_platform/v1/e6_trace.py`).

### 10.6 Known gaps

| Gap | Position |
|---|---|
| **Single sign-on is not built.** | No SSO code in `sh_platform/` (checked). Sign-in is email and password with the server-side session table. |
| **Backups rely on cloud snapshots.** | The app has no backup job of its own. Snapshot the Railway volume and the Postgres database. Test a restore. |
| **UC8 live re-run is pending.** | The UC8 use case (trade export against the administrator's trade confirmations) still needs its live re-run. Reported by the team. |
| **Paid capital calls can still raise an Action case.** | `sh_platform/v1/k6_liquidity.py` (`alert_if_due`) opens a "Fund the capital call" case when a confirmed call is due within the alert window. The function reads the due date and the notice status, not whether the call has since been paid. Check this before you rely on the case list. |
| **Agent answers take 8 to 70 seconds.** | Measured on the hosted demo on 13 Oct 2026 in Testing mode: Tally 8–11 s (after the speed fix), Span 8–17 s, studio talk about 25 s, Lumen 18–70 s. Each answer waits on the model call and the tool loop. Watch the run registry (section 10.5) to measure it. |
| About 350 JSON stores still in production mode | Specification section 5 and 10. Moving them to Postgres is planned. |
| One web replica only | DuckDB takes one writer at a time (specification section 10) |
| SORA not offered | Needs a free registered key from the provider |
| Column-level and document-type restrictions | Planned. Fund-level access is built. |
| Postgres connections open per call | A pool is planned |
| Cloud warehouse push | Needs two named approvers. The pilot carries synthetic data only. |

### 10.7 Start-up checks

- `python tools/doctor.py` before a server starts.
- A refused start with "only one of DATABASE_URL and REDIS_URL" means one is missing.
- A module that fails to load is logged and skipped. Check the log line for its id.

---

## 11. Glossary

| Term | Meaning |
|---|---|
| **Action** | The centre where people work their day: cases, reconciliations, approvals. |
| **Agent** | A helper that drafts and checks. Four: North, Span, Lumen, Tally. Agents propose and never sign. |
| **Approver** | A role that approves a result. Named by the organiser. |
| **Bronze, silver, gold** | Raw loaded tables, the company's cleaned model, and reporting tables for one project. |
| **Card** | One feature with its own file pair in `sh_platform/v1/`. |
| **Case** | A record in the Action Desk for an exception, such as a cash break or a capital call. |
| **Cycle date** | The company's business day. Every check reads it. Pinned on the Settings screen for demos. |
| **Egress** | Anything that leaves a plane. The gateway is the only exit. |
| **Four-eyes** | A dashboard is approved by someone other than its author. |
| **Gateway** | The egress gateway (`sh_platform/egress/gateway.py`). |
| **Guard** | A check in the agent answer path (the number guard) or the egress path (the four egress guards). |
| **Head of data** | The role that approves the design pack, build plan and map. Held with analyst. |
| **Intent of work (SOW)** | The signed record of what a company wants to know and how. North drafts it. |
| **Landing** | The folder of original files as received. Never edited. |
| **Lineage** | The trail from a figure back to its source file or API call. |
| **Mapping sheet** | The record of how each source field maps to a target field. |
| **Mode (Testing, Real use)** | The model set a company uses. Testing is cheap and default. |
| **Pack** | Industry knowledge in `packs/<industry>/`. Suggestions only. |
| **Plane** | One company's data folder. |
| **Playbook** | An agent's written method, in `skills/<agent>/`. |
| **Propose tool** | An agent tool that collects a change for a person to accept. It never writes. |
| **Pulse** | The landing page: what waits for each person. |
| **Seat** | A set of actions that a role may take (for example "architect" or "decision maker"). |
| **Signed** | A person has approved the record. Signed content is read-only. |
| **Simple mode / production mode** | Files and in-process jobs, versus Postgres, Redis and a worker. |
| **Teaching** | Adding files or notes that one agent may quote. |
| **Under-five rule** | A figure about a group smaller than five never leaves the plane or appears in a shared view. |
| **Wall** | The shared board of ideas inside an intent (Intent centre). |
