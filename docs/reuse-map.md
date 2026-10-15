# Reuse map: what we carry over, reshape or build new

Source: the earlier repo at `<earlier repo>` (branch main, commit 3a798cc5). It is read from, never written to.

- **Copy**: taken over almost as is; renamed and its tests carried with it.
- **Reshape**: the logic is kept, but it is split, renamed, made industry-neutral or fitted to the new flow.
- **Rebuild**: same purpose, written again (all screens, because the interface moves to React).
- **New**: did not exist before.

## Platform kernel

| Piece | Old location (size) | Treatment | Note |
|---|---|---|---|
| Company isolation, one data plane per company | `sh_platform/workspace.py` (598 lines) | Reshape | Becomes the company plane; data root from settings |
| Sign-in, sessions, CSRF | inside `webapp/backend/main.py` (1,313 lines, mixed) | Reshape | Extracted into `platform/auth`; the old file mixed many concerns |
| Permission per route, default deny | `webapp/backend/authz.py` (549), `contracts/access/` | Copy | Roles trimmed to those modules 1 and 2 use |
| Redirect to login when a session expires | none | New | Lesson from the last cycle |
| Module switches per company, module manifests | none | New | Entitlement is checked by menu, route and tool registry |
| Model gateway | `agents/gateway.py`, `agents/policy.py` | Reshape | Becomes the egress gateway's model path |
| Agent runtime: context pack, read-only tool loop | `emitters/agent_brain.py` (1,672) | Reshape | Split into smaller parts; keeps the tool loop and model settings |
| Pseudonymiser, name vault, allowlist, egress log | none | New | Decisions D-006, D-007 |
| Tool registry for MCP tools | none | New | Internal read-only tools first; outside connectors later |
| Numbers traced to facts (label guard) | `emitters/` guard code | Copy | |
| Agent evals | `emitters/evals/agent_evals.py` (482) | Copy | Adapted to North and Lens |
| Run registry | control tables | Reshape | |
| Industry packs | `templates/insurance/1`, `templates/asset_management/1` | Copy | |
| Pack loader | three separate loaders in the old repo | Reshape | One loader, industry always a parameter |
| Live updates (server-sent events) | `webapp/backend/routers/live.py` (83) | Copy | |
| Voice input | `emitters/voice.py` (123) | Copy | Spoken replies are new |
| crewAI bridge | `agents/crews_bridge.py`, `sh_crews/` | Copy, later | When the common room is built |
| Start-up check (`doctor`) | none | New | Lesson: missing key made North silent |

## Module 1: Intent Centre

| Piece | Old location (size) | Treatment | Note |
|---|---|---|---|
| Session engine: phases, seats, timer, private rooms, notes, join binding, solo run | `emitters/intent_sessions.py` (959), router (472) | Reshape | Phases change to the new flow (briefing; board only after rooms close) |
| Clustering notes, the wall, agree and discuss | same files | Reshape | |
| Problem library | `routers/problem_library.py` (51) | Copy | |
| Charter and two-sponsor sign-off | gates and charter code | Reshape | The C-level approver flow is new |
| Briefing with room rules and video | none | New | |
| Anonymous per note | none | New | |
| Charter templates and versions | none | New | |
| Business graph from the charter | none | New | |
| Screens | `intent-session.js` (366), `intent-center.js` (790), `alignment-room.js`, `charter-doc.js` | Rebuild in React | Old screens are the behaviour reference |

## Module 2: Baseline

| Piece | Old location (size) | Treatment | Note |
|---|---|---|---|
| Definitions drafted from the pack, "you decide" questions, conflicts, sign-off lock, human edits kept | `emitters/baseline.py` (906), router (242) | Reshape | This week's fixes come with it |
| Process map and data landscape generators | same | Reshape | |
| Metadata column matching | `emitters/column_matcher.py` (304) | Copy | |
| Local profiling of samples and dictionaries | `emitters/profiler.py` | Reshape | Only names and types go to the model |
| KPI work list and triage | partly in baseline | New | |
| Owners, governance, reassignment | none | New | |
| Requests to owners by email link or account | none | New | Needs an email service decision |
| Sensing (tracked today, source, timing, dependencies) | Sense peek screen (insurance-scripted) | Rebuild | |
| Upstream and downstream trace | none | New | |
| Per-owner signing and sponsor countersign | sign-off code | Reshape | |
| Excel data catalogue export | template only | New | Template: `docs/specs/signal-harbor-data-catalogue-template.xlsx` |
| Screens, including the process map | `baseline.js` (364), `estate.js` | Rebuild in React | Process map on React Flow |

## Tooling

| Piece | Treatment |
|---|---|
| Graft code index and MCP | Copy configuration |
| Archify diagrams | Global skill; diagrams copied to `docs/architecture/` |
| Ponytail rules | Global plugin, unchanged |
| Commit gate (`sh_commit.py`) | Copy, paths adapted |
| Guard hook | Copy, adapted |
| Builder and reviewer agents | Copy, adapted; security and UI reviewers added |

## Development cycle for every package

1. Brief: the spec features, OWNS paths, acceptance criteria, tests to run.
2. Builder in its own worktree writes failing tests, then the code.
3. Tests for two industries, an empty company and a solo user.
4. Independent review; security and UI review where they apply.
5. Fix rounds until PASS.
6. `/ship`: the commit gate checks reviewer ≠ builder, scope and secrets, then commits and tags.
7. Nitin checks locally at the end of each slice.

## Why phases take days when code exists

Most of the time is not writing code. Each package goes through reshaping to the new structure, tests against two industries and an empty company, independent review, and usually one fix round. Last week the average package took two review rounds. Reuse roughly halves the backend work; the screens are new because they move to React.

## What phase 1 actually did (updated 2026-10-03)

Planned treatment above; this table records what was really copied, reshaped, rebuilt or created. Source is the earlier repo unless noted.

| Piece | Planned | What happened |
|---|---|---|
| Company plane | Reshape `sh_platform/workspace.py` | **Rebuilt** as `sh_platform/plane.py`. Kept the idea of resolving every path and refusing anything outside the company folder; dropped the ambient "current company" binding and the audit-hook tripwire (nothing replaces them yet); added junction, symlink and Windows device-name refusal and error messages that never contain the data root |
| Sign-in, sessions, CSRF | Reshape the sign-in code in `main.py` | **Rebuilt** under `sh_platform/auth/` (signed cookie plus server-side session, scrypt passwords, CSRF double-submit, lockout, WebSocket rules). Nothing copied |
| Permission per route, default deny | Copy `authz.py` | **Rebuilt** as `sh_platform/route_permissions.yaml` plus one ASGI layer; only the roles idea was carried over (seven roles, nine old module roles dropped) |
| Redirect to login on expiry | New | **New** (401 `session_expired` plus the login page sentence) |
| Module switches, manifests, package catalogue | New | **New** (`entitlements.py`, `manifest.py`, `modulegate.py`, `catalogue.yaml`) |
| Model gateway | Reshape `agents/gateway.py`, `policy.py` | **Nothing reshaped**: the old files only chose a model tier and checked tool paths. The egress gateway is new (`sh_platform/egress/`); real provider adapters are phase 2 |
| Pseudonymiser, name vault, allowlist, egress log | New | **New** |
| Agent runtime | Reshape `emitters/agent_brain.py` | **Rebuilt** (`sh_platform/agents/`): tool registry, read-only loop, context pack, run registry; the old brain was only read for ideas (tool loop shape) |
| Number-to-fact guard | Copy | **Rebuilt** as `agents/guard.py` (the idea of replacing untraceable numbers was kept); documented limits |
| Agent evals | Copy | **Reshaped**: `agents/evals/` (stub model by default, `--live` refused without a real client, six neutral cases) |
| Run registry | Reshape | **New** in the company plane (`agents/runs.py`), content-free |
| Industry packs | Copy `templates/insurance/1`, `templates/asset_management/1` | **Copied** byte for byte (hash-compared) to `packs/<industry>/1/`, plus a small `pack.yaml` each |
| Pack loader | Reshape three loaders | **Rebuilt** as one loader, `sh_platform/packs.py` (industry is always a parameter; unknown industry gives an honest empty state) |
| Live updates, voice, crewAI bridge | Copy later | Not touched in phase 1 |
| Doctor | New | **Extended** `tools/doctor.py`; seeds are new (`tools/seed.py`) |
| Process record (D-026) | not planned | **New** `sh_platform/process_record.py`: a session is linked to its outcome both ways |
| UI shell | Rebuild | **Rebuilt** in React (login, home tiles, wizard frame, five screen states, session-ended flow) |
| Look and feel (D-027) | not planned | **Copied** read-only: the earlier stylesheets to `ui/src/styles/legacy/` and the lighthouse marks to `ui/public/brand/`; the shell uses them (`ui/src/styles/shell.css` adds only what they lack, with legacy tokens) |
| Tooling | Copy | Phase 0: commit gate, guard hook, builder and reviewer agents |
