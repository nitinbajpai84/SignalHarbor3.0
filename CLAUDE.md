# Signal Harbor

Signal Harbor takes a business from "what do we want to know" to "what is likely next", one module at a time. An agent drafts at every step; a named person signs every result. This repo is a fresh product. It reuses ideas and code from the earlier Signal Harbor repo but is never merged with it.

## Architecture in one paragraph

Three planes. The **control plane** (super admin, module switches, industry packs, domain context) holds no company data. The **module plane** holds the six modules and their agents, the same code for every company, with no state of its own. Each company has its own **data plane** (landing zone, warehouse, intents, baseline, context, graph); company data sits there and nowhere else. An agent has exactly one way out: the egress gateway. Diagrams: `docs/architecture/`.

## Layout

| Path | What lives there |
|---|---|
| `sh_platform/` | Shared kernel: company space, sign-in, entitlements, egress gateway, agent runtime, tool registry, guards, run log, pack loader, company profile |
| `modules/m1_intent/`, `modules/m2_baseline/`, `modules/m3_connect/` | One folder per module: manifest, api, agent, tools, ui, tests. Each has its own `CLAUDE.md` |
| `packs/<industry>/` | Industry knowledge: problems, glossary, measures, feeds. Suggestions, never company policy |
| `ui/` | React + TypeScript shell: login, home page of module tiles, wizard frame |
| `docs/` | `decisions.md`, `specs/`, `architecture/`, `ledger/` |
| `tools/` | `sh_commit.py`, `doctor.py`, seeds |
| `.claude/` | `agents/` (builder and reviewers), `agent-memory/` (their notebooks, committed), `rules/`, `skills/`, `commands/`, `hooks/guard.cjs`, `settings.json` |

## Hard rules

1. Real client data never leaves the machine. Only synthetic data in tests and demos. See `.claude/rules/data-locality.md`.
2. Contracts and specs are the only source of truth. Never invent a table, column, threshold or business rule; put it in Open questions.
3. No secret in code, contracts or docs. Use environment variable names.
4. Author is never the reviewer. Packages land only through `tools/sh_commit.py`.
5. No destructive command without Nitin's approval in the session.
6. The industry is always a parameter. No module may hardcode one industry.
7. Signed content is read-only; a draft never overwrites a human edit.
8. Jev picks the model for every subagent: route a card per task with `~/.claude/helpers/jev_route.py` (see `~/.claude/CLAUDE.md`); the jev-guard hook refuses unrouted launches.

## Chapters

`.claude/rules/`: reuse-first, data-locality, contracts, egress, modules, industry, testing, ui-copy, house-style. Read the chapter that matches your task, not all of them. **Always read reuse-first** (D-031): check `docs/reuse-inventory.md` and the earlier repo before building anything, and copy freely between the repos.

## Working method

- Get code context from graft first (`graft ask "<q>" --source`, `graft skeleton <file>`, `graft callers <sym>`).
- Run `python tools/doctor.py` before starting servers; it fails loudly on a missing key or setting.
- Architecture diagrams: an Archify JSON spec plus its HTML, side by side in `docs/architecture/`. Edit the JSON and re-render; never hand-edit the HTML.
- Simplest working change (Ponytail ladder, see `house-style`). A whole-repo audit for over-building: `/ponytail-audit`.
- Agent notebooks: each agent in `.claude/agents/` with `memory: project` keeps lessons in `.claude/agent-memory/<agent>/MEMORY.md`. Lessons only; never client data.
- Specs: `docs/specs/`. Decisions: `docs/decisions.md`. Reuse map: `docs/reuse-map.md`.
