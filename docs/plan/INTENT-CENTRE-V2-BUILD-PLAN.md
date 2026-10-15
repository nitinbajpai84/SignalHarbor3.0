# Intent Centre v2: build plan (7 October 2026)

Source of truth: `docs/specs/intent-centre/` (00-BRIEF.md rulings 1 to 32, 00-INDEX.md, files 01 to 56). Orchestrator: this session (the AI product manager). Team: up to 60 agents in waves. Model per card from `tools/route_task.py` (Jev); the orchestrator may only make a pick stricter.

## 0. Rules that hold for every card

- Shared files belong to the orchestrator alone: `ui/src/App.tsx`, `ui/src/design/*`, `ui/src/shell/*`, `ui/src/styles/*`, `sh_platform/app.py`, `sh_platform/route_permissions.yaml`, `docs/plan/SHAPES.md`. The orchestrator scaffolds every route, page stub and permission line before a wave starts; builders replace stub bodies and never touch the shared files.
- One agent owns the data plane (`tools/seed_demo_intents.py`, card D1). No `--reset` once testers mutate.
- Every builder writes one small test file for its behaviour and takes shots at 1280 and 390 with `.sh-tmp/shot.py`; every builder is followed by a tester on the live plane. READY is accepted only when verified on the live plane, never on mocks.
- Backend runs through `.sh-tmp/backend-watch.sh`; after every Python edit `import sh_platform.app` must pass; after every TS edit `npx tsc --noEmit` must be clean.
- Standing rules: never push, never commit (orchestrator commits through the private index recipe), synthetic data only, never edit `.claude/`, no model or vendor names in copy, every number traces to a record or says "Not available yet", agents decide and people act, no game words, British spelling, no em dashes, Ponytail (shortest working change, reuse before writing, no new dependencies).

## 1. Scaffold (orchestrator, before wave 1)

- Backend package `sh_platform/intents/` with one router module per card (`records.py`, `types.py`, `visibility.py`, `access.py`, `home.py`, `people.py`, `clock.py`, `north.py`, `closure.py`, `events.py`, `search.py`, `initiative.py`, `define.py`, `processes.py`, `sources.py`, `glossary.py`, `catalogue.py`, `charter.py`, `build_ready.py`, `brainstorm.py`, `checkin.py`, `problem.py`, `decision.py`, `lens.py`, `nira.py`, `share.py`, `past.py`, `links.py`, `backlog.py`, `affected.py`, `admin.py`, `pack.py`, `memory.py`, `measures.py`, `knowledge_map.py`, `opportunities.py`), each `router = APIRouter()` with its routes returning 501 `{"detail": "Not available yet"}`, all registered in `app.py`.
- `route_permissions.yaml`: the full block from file 14 (141 routes) plus the guest exceptions of ruling 24.
- UI: `ui/src/intents/` with one page stub per view (`IntentHome.tsx`, `IntentNew.tsx`, `IntentScreen.tsx` with the twelve views as children, `IntentPast.tsx`, `IntentBacklog.tsx`, `IntentAdmin.tsx`, `ControlIntents.tsx`), routes in `App.tsx` per ruling 1, each stub rendering `ScreenState` "Not available yet" with the file number it waits for.
- `docs/plan/SHAPES.md` section 15: the intent record (01 after rulings 16, 21, 28), the week file (17), the events line (16), the opportunity record (56).

## 2. Waves and cards

Each card: id, spec files, OWNS, acceptance (its definition of done), tester. Cards are JSON under `.sh-tmp/ic/cards/`; the router log is `docs/ledger/routing.jsonl`.

### Wave 1: foundation (10 builders, 10 testers)
B01 record and lifecycle (01) · B02 types catalogue and chooser (02, 03) · B03 areas and visibility (05) · B04 per-intent access check and module gate prefix (14) · B05 home and empty states (04, 18) · B06 people, roles, invitations (06) · B07 time box and clock (07) · B08 North workflow runner and panel (08) · B09 closure and ratings (09, 10) · B10 events log and search index (16, 15)

### Wave 2: Initiative (9 builders, 9 testers)
B11 initiative start (22) · B12 wall inside an intent, cards, suggestions (23, 24, 25) · B13 Define shell, tabs, clusters, shelves, session mode (26) · B14 process map (27) · B15 data sources and technical areas (28) · B16 business glossary (29) · B17 technical glossary, catalogue, governed state (30, 31) · B18 charter, signature, who does what (32, 34) · B19 build-ready check, hand-off, Build room 0 (33)

### Wave 3: other types and agents (8 builders, 8 testers)
B20 brainstorm start and session (35, 36) · B21 converge and outcome (37) · B22 weekly check-in setup and entry (38, 39) · B23 weekly check-in review and trends (40) · B24 problem (41, 42) · B25 decision (43) · B26 Lens in Define (44) · B27 Pulse lines and Nira strip (13, 45)

### Wave 4: periphery (7 builders, 7 testers)
B28 share link and visitor (11) · B29 past, chain, links, backlog (12, 20, 21) · B30 affected and observer (47) · B31 admin and super admin views (48) · B32 pack suggestions and memory (49, 46) · B33 centre measures (19) · B34 phone and projector pass over every intent screen (17)

### Wave 5: knowledge and data (3 builders, 3 testers)
B35 knowledge map (55) · B36 data-backed opportunities (56) · D1 demo seed for intents: five areas, two Initiatives (one closed, one in Define), one Brainstorm closed, one Weekly check-in series with three weeks, two Problems, one Decision, a backlog, opportunities; synthetic, Ardmore names plus Mei Ling, Ravi, Rahul

### Wave 6: departments test (18 testers, then fixers as needed)
Personas by department, each walking the product as a real person with a real goal, on the live plane, phone and desktop, reporting every problem with a screenshot and a repro: Finance (Janet organiser, Daniel sponsor, Mei Ling reporter), Investments (Katie analyst, Ravi participant), Operations (Harvey source owner and ops manager, Aaron reporter, Rahul reporter), Compliance (Grace governance lead), company admin, super admin, a customer critic, a security prober (leaks across roles), a numbers auditor (every number traces), a copy auditor, a phone-only user, an accessibility pass, a speed pass. Problems go to `.sh-tmp/ic/reports/T*-report.md`; the orchestrator triages into fix cards (F*) routed through Jev; the loop repeats until every persona reaches their goal without a blocker and the critic's verdict is "would use it".

## 3. Definition of done for the whole programme

1. Every route in file 14's block answers for the roles it names and refuses the rest (role matrix test extended and green).
2. The five journeys (files 50 to 54) run end to end on the live plane as their test scripts say, at 1280 and 390, screenshots on disk.
3. Every persona in wave 6 reaches their goal; no open blocker; critic says "would use it".
4. `import sh_platform.app`, `npx tsc --noEmit`, the copy rules test, the role matrix test and each card's test file are green; the full suites run once at the end.
5. No number on any intent screen without a record behind it.
6. Committed through the private index with a plain message, local only.
