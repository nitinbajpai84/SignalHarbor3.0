# Decisions

One list. Each entry: what was decided, by whom, when. Builders treat these as settled; anything not here and not in the spec is an open question.

| # | Date | Decision | By |
|---|---|---|---|
| D-001 | 2026-10-03 | Signal Harbor is rebuilt as a fresh, separate product in this repo. It reuses code from the earlier repo but is never merged with it. The earlier repo stays untouched. | Nitin |
| D-002 | 2026-10-02 | Six modules: 1 Intent, 2 Baseline and sensing, 3 Connect, scan and gap, 4 Build, 5 Foresight and advanced modelling, 6 Ops, daily feed and market pulse. Each module is a package that can be sold and run on its own and ends in one output. | Nitin |
| D-003 | 2026-10-02 | Agents: North (industry expert, module 1), Lens (business analyst, module 2), Flow (data, module 3), a builder (module 4), a forecaster (module 5), Watch (module 6), Nira (guide and project manager, all modules). The builder and forecaster names are placeholders. | Nitin |
| D-004 | 2026-10-02 | The module 1 room holds up to ten people; one person can run it alone on the smallest plan. | Nitin |
| D-005 | 2026-10-02 | Task tracking is a list inside the product kept by the agents, like a Jira board. No outside tool first. | Nitin |
| D-006 | 2026-10-03 | Internet access is off by default for a new company, switched on per company and per module only at the customer's request. | Nitin |
| D-007 | 2026-10-03 | Tokenised before anything leaves: company names, people's names, emails and phone numbers, fund, account and portfolio names, counterparties, account and policy numbers. Never sent: raw rows; figures other than totals over groups of five or more; uploaded documents in full (a short summary only). | Nitin |
| D-008 | 2026-10-03 | Packages, as a proposal accepted for now: Discover (modules 1-3), Build (1-5), Run (all six). Names and contents may change. | Nitin |
| D-009 | 2026-10-03 | The interface is React with TypeScript. Backend logic is reused; screens are rebuilt. | Nitin |
| D-010 | 2026-10-03 | Build and test modules 1 and 2 first; the other modules follow only after Nitin has tested these. | Nitin |
| D-011 | 2026-10-03 | Modules are installed in the customer's own environment, so sample data and metadata stay there. | Nitin (spec section 12) |
| D-012 | 2026-10-02/03 | Module 1 and 2 behaviour settled in `docs/specs/MODULES-1-2-FEATURE-SPEC.md` section 12 (anonymous per note, North suggests industry practice labelled as such, spoken voice with an outside speech service, C-level approver named in preparation, board after the rooms close, owners sign their own part and sponsors countersign, requests by email link or account, uploads of dictionaries or samples, readiness rule, Excel catalogue output). | Nitin |

## Decided 2026-10-03 (answers to the spec's Q1 to Q10 and the repo questions)

These override the spec's own wording where they differ. Builders follow this table.

| # | Decision | By |
|---|---|---|
| D-013 | **Anonymous notes (spec Q1).** When a note is set to anonymous, nobody can see who wrote it: not the organiser, not an admin. The choice is real. | Nitin |
| D-014 | **Approver (spec Q2).** There is a role called **approver**. The organiser names whoever they want in it; the product does not check or record whether the person is C-level. Wherever the spec says "C-level approver", read "approver". | Nitin |
| D-015 | **Note by name or anonymous (spec Q3).** By name by default. Anonymous is chosen per note, only if the author wants it. | Nitin |
| D-016 | **Private transcripts (spec Q4).** A private transcript is readable by its author, and by an admin when the author's notes are not anonymous. If the author used anonymous notes, only the author can read the transcript. The board of notes is readable by everyone in the room, with anonymous notes shown without a name. | Nitin |
| D-017 | **Retention (spec Q5).** How long transcripts, requests and answers are kept is a contract setting per customer. | Nitin |
| D-018 | **Audio (spec Q6).** No audio is stored. The text transcript is kept (see D-017). | Nitin |
| D-019 | **Module 2 versus module 3 (spec Q7).** Module 2 reads names and types of tables and columns to propose rows; module 3 tests connections and compares samples. | Nitin |
| D-020 | **Priority of a cluster (spec Q8), changed.** People in the room **vote** on which problems to prioritise, as in a live poll such as Mentimeter. Each problem statement has a voting column: must have, should have, could have (and will not have). Voting is simple and has **no restrictions**: everyone in the room can vote, there are no voting rules, weights or special rights, and nothing overrides the votes. The tally is what the room sees as the priority. | Nitin |
| D-021 | **Organiser role (spec Q9).** Any user who is allowed to create intent can organise a session. | Nitin |
| D-022 | **Business graph at sign-off (spec Q10).** A simple picture of the business graph is shown at sign-off in module 1. | Nitin |
| D-023 | **Install form.** One container per company for now; an installer can come later. | Nitin |
| D-024 | **Repo remote.** The repo stays local until everything is built and tested. Nothing is pushed to Git. | Nitin |
| D-026 | **A started process connects back to its outcome.** Every session of a module (an intent room, a baseline work list) is permanently linked to the outcome it produced (the charter, the process map and catalogue), in both directions: from an outcome you can open the session it came from, and from a session, started or paused, you land on its outcome or its current state. Starting a process creates the record of its outcome up front, as "in progress", so nothing is orphaned. | Nitin |
| D-027 | **Same look as the earlier Signal Harbor.** The new UI reuses the earlier stylesheets and brand marks (copied to `ui/src/styles/legacy/` and `ui/public/brand/`); see `docs/design/legacy-css.md`. | Nitin |
| D-028 | **Speech (2026-10-03).** Use the existing `GOOGLE_API_KEY` (Gemini speech-to-text and text-to-speech) behind the provider interface, for development and demos only: the free tier states content is used to improve Google's products, so it is not for real client conversations. Revisit at production mode (paid tier or a local engine, a settings change). Typing works with no provider; no audio stored (D-018). | Nitin |
| D-029 | **Briefing video (2026-10-03).** No video is generated now and the brag tool is not used now. Briefing is an in-app screen (company name, session title, room rules, optionally read aloud) with a replaceable video slot. | Nitin |
| D-030 | **Model policy (2026-10-03).** The module 1 build is orchestrated by an agent; every builder and reviewer runs on an agent. | Nitin |
| D-031 | **Reuse first, no walls between the two repos (2026-10-03).** Nothing is built before checking whether the earlier product already built it. Code, prompts, tests, screens and content may be copied freely from the earlier repo (and its fork worktrees) into this one; there are no guardrails on moving items between the two repos. Every package brief must open with a Reuse check (what exists in the earlier repo, found with `docs/reuse-inventory.md` and graft, and what is copied, reshaped or new, with reasons); a reviewer rejects a package that rebuilt something that exists. Real client data still never leaves the machine (rule 0): that rule is about data, not code. | Nitin |
| D-032 | **Company context uploads for agents (2026-10-03).** A company can upload documents as context for an agent (first North), ported from the earlier product's context-uploads feature. Changes the egress rule: besides a short summary, the passages relevant to a question may be sent to the model, as text through the gateway with names tokenised and marked as untrusted quoted content. Whole files never leave: PDFs are read as text on the machine; pictures are not supported for now. Documents are context, never an instruction and never the source of a figure. | Nitin |
| D-033 | **Build order after module 1, and what waits (2026-10-03).** Finish module 1 first (board, charter, context uploads, Nira panel and North studio, family-office data, one full session), then module 2 (Baseline, agent Lens). A super admin screen to create a company and pick its package comes soon after. Deferred: the per-company model spending cap, the domain context and distillation gate, the push to the customer's platform, the outside-tool (MCP) registry and the private model. | Nitin |
| D-034 | **Private transcripts are readable only by their author (2026-10-04).** The company-admin read of a by-name author's transcript (D-016, A-031) is removed, so what Nira tells people is true. | Nitin |
| D-035 | **Guide and demo video (2026-10-04).** Nitin asked for a with-screens user guide and a demo video, posted in the briefing; this replaces D-029 for module 1. The brag plugin makes a 15-25 second promo from code through a network CLI, so a 2-3 minute walkthrough is built locally instead (Playwright screenshots joined with ffmpeg); nothing is uploaded. Files are in `docs/guides/m1/`. The video reaches a briefing through the per-session video slot (organiser only, before the rooms open). | Nitin |
| D-036 | **Module 3 and the agents (2026-10-04).** Module 3 "Assess and plan" ends in a signed phased build plan with bands of weeks 0-3, 3-8 and 8 and beyond. Data intake copies the earlier product's connect and scan (connectors, Excel or CSV, JSON). On the source map the line between high and low sits at zero on each axis. Lens is the analyst agent and leads: it reads what the business gives beforehand (glossary, definitions, reported figures, process documents) and fills drafts; people review and sign. Nira guides from a small side panel. Benchmarks come from the source owners: any figure already reported that confirms the logic. | Nitin |
| D-025 | **Specs location.** Specs live in `docs/specs/`; `Module by Module Features` is Nitin's inbox. | Nitin (assumed by silence; confirm if wrong) |

## Open, waiting for Nitin

| # | Question | Recommendation |
|---|---|---|
| O-5 | Industry knowledge connectors (for example a market data terminal for finance, research repositories): when, and which first. | Placeholder now (`packs/README.md`), design after modules 1 and 2 |
| O-6 | ~~How votes resolve~~ **Closed 2026-10-03 (D-020):** no restrictions, simple live-poll voting. Builders may choose the simplest display of results (for example a bar per option) and record any such choice as an autonomous decision. | Closed |
| O-7 | **Admin reading transcripts (D-016).** Which admin: the company admin only? Is each admin read recorded in an access log? | Company admin only, every read logged |
| O-8 | **Spec wording.** `docs/specs/MODULES-1-2-FEATURE-SPEC.md` still says "C-level approver" and an organiser-picked priority in places. The builder reads `docs/decisions.md` first; edit the spec to match when module 1 is built. | Yes |

## Autonomous decisions (phase 1, for Nitin's review)

Chosen without asking, as the phase 1 prompt allows. Each can be reversed as stated. The working notes are in `docs/ledger/autonomous.md` and each package's `docs/ledger/<ID>/report.md`.

| # | Question | Choice | Why | How to reverse |
|---|---|---|---|---|
| A-001 | CLAUDE.md names the kernel `platform/`; a package with that name shadows Python's own `platform` module | The package is `sh_platform/` (the old repo used the same name) | Avoids a hard-to-diagnose import failure | Rename the folder and imports in one commit |
| A-002 | The project agents (`sh-builder`, `sh-reviewer`, and so on) were not registered in the session | Each ran as a general-purpose agent told to follow its definition file; reviewers could not edit | Keeps author and reviewer separate without touching tool settings | Switch the agent type once they load |
| A-003 | The security reviewer rejected the egress package three times for the same cause (raw-row detection heuristics) | **Nitin's direction:** allowlist design; row detection reduced to structural checks; review bar eased (only realistic cross-company leaks, gate bypasses and wrong refusals block a package). Table-shaped free text can pass: accepted residual risk | One container per company (D-023) | Re-add the heuristics in `sh_platform/egress/rows.py`, raise the review bar |
| A-004 | `SH_MODE` defaults to `dev` when unset, which skips the secret-strength rule and the Secure cookie flag | Keep dev as the default; doctor fails when `SH_MODE` is neither dev nor prod; RUNNING.md says production sets prod | Local running stays simple | Change the default in `sh_platform/settings.py` |
| A-005 | Which roles (the spec only proposed some; `organiser` is not a role, D-021) | `super_admin`, `company_admin`, `sponsor`, `analyst`, `approver`, `participant`, `owner` (a nominated data owner). The nine old module roles (stakeholder, data_analyst, architect, data_engineering_lead, test_manager, ops_lead, insight_manager, platform_admin, tester) were dropped | Only what modules 1 and 2 use, plus `approver` (D-014) | Edit `roles:` in `sh_platform/route_permissions.yaml` |
| A-006 | Routes that any signed-in person may use (logout, who am I) fit neither `roles:` nor `public:`; how should login be protected | Third rule form `authenticated: true` (account-level routes only, refuses an account with no company unless the rule lists `super_admin`); login accepts only `application/json` (else 415); passwords use scrypt N=2^15 | Closes cross-site login forgery; safe default cost | List explicit roles; drop the content-type check; change `_N` |
| A-007 | FastAPI's `app.frontend` cannot be declared in default deny | It is always refused; the built UI is served through one declared public `MOUNT /{path}` with a single-page-app fallback only for non-`api`, non-`docs` paths without a file extension | Default deny stays complete | Replace the mount in `sh_platform/webui.py` |
| A-008 | What a refused module looks like | Switched off, never owned, unknown id and super admin all get the same 403 `module_not_available` (identical body and headers); the gate sits outside the auth layer; a signed-out request under `/api/modules/` gets 401 `session_expired` | Nobody can probe which modules exist | Edit `sh_platform/modulegate.py` |
| A-009 | Package and agent names for modules not yet built | Package ids `discover`, `build`, `run`; agents for modules 4 and 5 are "Builder" and "Forecaster" (placeholders per D-003) | Names live only in `sh_platform/catalogue.yaml` | Edit the catalogue |
| A-010 | What an industry value may be | Free text up to 64 characters (it becomes a pack folder name); an industry with no pack gets the honest empty state | Never validate against a hardcoded list | Loosen or tighten `_clean` in `sh_platform/entitlements.py` |
| A-011 | Real model provider calls | Not built: the egress client sends role and content only (no assistant tool calls or call ids) and the gateway has its own envelope; provider adapters and model selection from settings are phase 2 | Phase 1 is the kernel | Add an adapter that carries tool names and call ids through the allowed keys |
| A-012 | Which states a session and an outcome have (D-026) | Session `in_progress`, `paused`, `completed`; outcome `in_progress`, `completed`; completed is final; modules keep their own detail in their own records | The minimum D-026 needs | Extend the two tuples in `sh_platform/process_record.py` |
| A-013 | Fonts (D-027) | Fraunces, Source Sans 3 and JetBrains Mono load from Google Fonts until vendored into `ui/public/fonts/`; offline fallbacks (Georgia, Segoe UI) were checked and look acceptable | The look doc says so; a customer environment may be offline | Vendor the fonts before any customer install |
| A-014 | Seed data | Companies `harbor-mutual` (insurance, Discover), `tidewater-capital` (asset management, Build), `solo-studio` (industry `unlisted`, no modules, one solo user) and a platform account; every name carries "Illustrative", e-mails end in `@example.test`; passwords only in `<data>/_control/seed_credentials.txt` | Synthetic only; never printed | Edit the `COMPANIES` table in `tools/seed.py` |
| A-015 | Locks and sessions | One process per company container: sessions are in memory, and the account, entitlement and process-record stores lock threads in one process only. Several workers, or a command-line tool beside the server, need file locks first | Matches D-023 | Add file locks before running more than one process per plane |
| A-016 | The number guard's ignore rules (agents) | Documented limits: numbers as words are not checked; ids are whole tokens like `D-013`; a year in a date context is ignored; figures returned by tools in the same run count as recorded facts only for groups of five or more | Keeps the guard simple and predictable | Tighten `sh_platform/agents/guard.py` |

## Open questions waiting for Nitin (from phase 1)

- Spec section 4 says "one owner on the smallest plan" signs the charter. Does "owner" mean the plan's business owner rather than the data-owner role `owner`?
- Brand: the legacy look is applied (D-027); a dark-theme Sign in button blends into the dark card because of an earlier-stylesheet token (1.15:1). Accept, or change the token?
- Should production deployments be required to set `SH_MODE=prod` (A-004)?
- Add a public `AccountStore.set_password` (the seed uses private methods for `--reset-credentials`) and a public disable-account method (the smoke tests use a helper)?

## Decided 2026-10-06 (Intent centre re-staging; proposed by the build session, for Nitin's review)

Spec: `docs/specs/INTENT-CENTRE-SPEC.md`. Plan: `docs/specs/INTENT-CENTRE-BUILD-PLAN.md`. Diagram: `docs/architecture/sh-three-centres.json`.

| # | Decision | Why | How to reverse |
|---|---|---|---|
| A-052 | The product is presented as three centres (Intent, Build, Consume), each with three rooms, with no game vocabulary on screen: lanes, cards, shelves, seals, the wall. The mechanics (everyone contributes in parallel, anonymous is real, the group decides by moving things, it ends in a signed record) stay. | Enterprise buyers adopted facilitation tools (Miro, Mural, Slido) and rejected gamified ones (Gartner 2012, Fortune 2014); the mechanics are what worked. | Rename the labels; nothing in the engines changes. |
| A-053 | A `cards` section in the company profile, one entry per card on the wall, written only by the wall routes, with lane, four provenance quarters, sealed, anonymous, author, from_interview, cluster, shelf. | One spine for every room; per-viewer filtering comes free from `profile.read`. | Keep cards in the module 1 notes store only. |
| A-054 | A governed state per measure: owners, classification, who may see, resolving team and week, affected downstream, review date. A cluster sits on Must or Should only when every measure it maps to is fully governed. | Governance set once in Define and enforced downstream (module 3 masking, module 4 access rules, feeds). | Drop the rule; keep the fields as information. |
| A-055 | A card may be put on the wall with two of four quarters answered. Empty quarters show empty; a quarter an agent fills from a document is marked guessed with the document named. | A half-formed thought should not be lost because the person lacks the technical definition. | Require four of four. |
| A-056 | North may add at most three suggestion cards per lane, from the pack and the company's own documents, labelled as suggestions; a suggestion counts only when a person picks it up and is dropped when the wall closes. | Suggestions help a quiet room without letting the pack write the charter. | Set the limit to zero. |
| A-057 | Counters record numbers only (cards confirmed, new, sealed; actions; free-text boxes). | Outcomes page needs them; content never belongs in a counter. | Remove the counters. |
| A-058 | Shelves are Must, Should, Good to have, Future. Future keeps the reason and a review date (default one quarter). Nothing is deleted from the wall. | "Could" reads as a dismissal; parked thoughts are the next quarter's input. | Return to Must, Should, Could. |
| A-059 | A builder-model router (`tools/route_task.py`): code rules decide the sensitive cases; a typed judgment picks the builder tier (Haiku, Sonnet, or back to the orchestrator) and the review level for the rest. A reasoning model orchestrates and reviews gate packages. Agreement with the orchestrator is logged; below 80% over twenty routings the router is switched off. | Spend the larger models where a mistake would show one person another's data, not on renames. | Delete the tool; route by the table in the plan. |
| A-060 | The company graph (`docs/specs/COMPANY-GRAPH-SPEC.md`) is a projection rebuilt from the records (profile, cards, catalogue, process map, trial, plan); nothing is edited on it directly. | Keeps the signed-record rule; no second store can drift from the ones we guard. | Make it a store of its own. |
| A-061 | Decisions and Rules are node types on the graph, each with provenance to a person and a date. | Signatures, shelf moves, owner confirmations and settled ambiguities become traceable; undocumented rules are the usual cause of wrong numbers. | Keep them in the records only. |
| A-062 | No screen draws more than one topic's relationships (the earlier product's V2-Q rule); the Map view is counts and holes. Views: shelf, topic, trace, impact, map. | The earlier force-directed graph was unreadable; the four-view layer replaced it and is copied. | Add a whole-graph canvas. |
| A-063 | The graph never leaves the plane; agents receive traversal results as tokenised counts and labels through the gateway. | Same egress rule as everything else. | None. |
| A-064 | The Build centre warehouse is one DuckDB file per company inside the plane; a customer's cloud warehouse is a choice in the environment check, not the default. | Zero infrastructure, data locality, a file a person can back up and inspect. | Make the cloud warehouse the default. |
| A-065 | Restricted marts live in a separate DuckDB file readable only by the people on the list; query tools read a read-only copy refreshed after each load, never the live file. | DuckDB has no row-level security; separation by file is auditable. | Single file with views. |
| A-066 | Pipelines are contracts (arrival, SLA, schema, rules, dependencies, owner) compiled to code; the built-in runner is the default and an Airflow DAG is generated for customers who have Airflow. | One contract for every client, two runners; Airflow per company is heavy to run. | Require Airflow always. |
| A-067 | Webhooks (Slack, Teams) are egress destinations allowlisted per company; posts carry status, counts and labels only, through the gateway. | Same one-exit rule as everything else. | None. |
| A-068 | A measure is release-ready only when it matches the reported figure for every period in the band, or its gap has an owner-signed reason; the sponsor signs the band. | Nothing is marked done that is not proven. | Release on the sponsor's word alone. |
| A-069 | The company admin passes a restricted area only while nobody is named on it (so the lists can be set up); once the policy or a person names a may_see list, the admin is treated like anyone else and sees a silhouette unless named. | A sealed card or file must be sealed from the admin too, or the promise on the wall is empty; the set-up path still needs someone who can see an unnamed area. | Restore the unconditional admin pass in profile view. |

## A-070 The company map ("How my organisation connects") is open to everyone in the company (7 Oct 2026)
Nitin: the map is business processes and definitions, no data, so it is open internally and sits on everyone's pulse page. It shows names and links only: walls, problems, measures, systems, owners, teams, rules. It never shows a figure, a row or a document. Anonymous cards are never linked to a person. Restricted areas (pay, HR) still appear as silhouettes to anyone outside their list, A-069 unchanged. The map grows from the intent sessions people were invited to; "new this week" is listed per person.

## A-071 The pulse is the landing page (7 Oct 2026)
Sign-in lands on the pulse, not the Intent centre. Four strips in a fixed order: Invited, Decide, Give, Watch, then the map. Each line is read from a record and opens the one screen where the action is taken. At most seven lines a day; an empty strip is hidden; a line leaves when the record changes. Roles: participant, sponsor, organiser (AI product manager), measure or data owner, data team (sees Build and Ops; others do not), company admin (Control). The same pulse goes out by email through the gateway.

## A-072 The map is a stewarded ontology with comments, versions and sign-off trails (7 Oct 2026)
Every signed outcome adds to the map; nothing is drawn by hand. Each node shows its source of truth (which wall asked, which session defined, who signed, when), a version per change with person and time, and for a pipeline its code commits and the design, UAT and release signatures. Anyone in the company can comment, suggest a change or flag an ambiguity on a process or definition; the item goes to the node owner's pulse as a Decide item. One map steward (head of data by default) accepts or declines suggested changes and resolves conflicting versions; Lens drafts, the steward decides. A signed register page lists every signed KPI and definition with owner, pipeline, signers and version. Build roles (architect, developer, tester or UAT sponsor, sponsor, ops, informed) are named at the charter and enforced as pulse tasks.

## A-073 One role table drives the top bar, the routes and the permissions (7 Oct 2026)
| Role | Top bar | Lands on | Never sees |
|---|---|---|---|
| Participant | Pulse, Map | Pulse | Build, Control, other people's walls |
| Owner, approver | Pulse, Consume, Map | Pulse | Build, Control, Intent (except by invite link) |
| Sponsor | Pulse, Intent, Consume, Map | Pulse | Build, Control |
| Analyst (data team) | Pulse, Build, Consume, Map | Pulse | Control |
| Company admin (organiser) | Pulse, Intent, Build, Consume, Map, Control | Pulse | nothing |
| Super admin | Control | Control | company data |

One table (`ui/src/shell/roles.ts` mirrored in `sh_platform/route_permissions.yaml`) drives the bar, the routes and the permissions. An invite link opens the one wall for anyone with a seat, whatever their bar shows.
