# Module 3 (m3_connect, "Assess and plan"): shared contract

Every package reads this first. Decisions: D-036 (Lens leads, Nira small side panel, weeks 0-3 / 3-8 / 8+, the line at zero on each axis, benchmarks from source owners). Spec memory: Nitin's flow in `docs/ledger/M3-DESIGN/`. Design deck: https://claude.ai/artifact/PRnJuiGXEDZHph7pRttB9y. Reuse check: `docs/ledger/M3-DESIGN/reuse-check.md`.

## The principle: the customer does four things, Lens does the rest
The customer only:
1. **Gives source data**: uploads files (Excel, CSV, JSON) or a connection, per source.
2. **Gives benchmark data**: figures they already report (a monthly pack, a dashboard export) for the same period.
3. **Accepts the risks**: each risk, ambiguity and unknown Lens lists, accepted (with an optional note) or sent back.
4. **Accepts the plan**: the sponsor, then the head of data, sign the phased build plan.

Everything else is automatic, drafted by Lens and shown for review, never asked as a form:
- scores every source for impact and readiness and places it on the map;
- lists what to ask each source owner for (tables, columns, period) from the signed catalogue;
- reads uploaded files, matches their columns to the catalogue's fields, profiles them (columns found, how full, date range, row count);
- turns each signed measure definition into a rule it can run on the sample, runs it, compares with the benchmark, explains each gap;
- sorts every measure into ready to build / unclear / unknown and writes the risk list;
- drafts the phased plan with effort by team.

A person may change any Lens draft with a reason; a draft never overwrites a human edit (rule 7). Lens's reasons are plain words. Nira, in a small side panel, says what is next and who it waits on.

## Inputs (read only, never imported from another module)
Read JSON from the company plane by path, like `modules/m2_baseline/store/catalogue.py` reads the charter:
- the signed module 2 outcome: `plane.path("intents", "m2_baseline", "outcomes", <outcome_id>.json)` (see `modules/m2_baseline/contracts/baseline_outcome.yaml`): `catalogue` (sources, tables, fields, extractions, kpis), `process_map`, `confirmations`, `signatures`, `gaps`, and the measure definitions and owners;
- the signed module 1 charter outcome (path in `modules/m1_intent/contracts/outcome.yaml`): `problems` (with Must/Should/Could/Not this time), `pain_points`, `future_signals`, `levers`.
Restricted measures (personal, sensitive, a `may_see` list) keep their visibility in module 3: a viewer who may not see a measure sees "A restricted measure" and nothing about its source.

## One assessment = one folder in the plane
`plane.path("intents", "m3_connect", "assessments", <assessment_id>)`, each package owning its own files (never write another package's file):

| File | Owner | Holds |
|---|---|---|
| `assessment.json` | SCAFFOLD | id, baseline outcome id, charter outcome id, state (`draft`, `signed`), created by and at |
| `sources.json` | P01 | per source: id, name, kind (spreadsheet, email, outside feed, system), measures fed, impact {score -1..1, reasons[]}, readiness {score -1..1, reasons[]}, zone, extra marks (restricted, blocked_upstream, effort small/medium/large, licence, owners_disagree), person override {impact, readiness, reason, by, at} |
| `requests.json` | P02 | per source: tables and columns asked for (from the catalogue), period, benchmark asked for, link token hash, state |
| `intake/<source_id>/` | P02 | uploaded files (kept on the machine), `profile.json`: columns found vs expected, fill rate per column, date range, row count, matches to catalogue fields, gap list |
| `benchmarks.json` | P02 | per measure: the customer's figure, period, where it came from (file, page or cell), given by |
| `rules.json` | P03 | per measure: the runnable rule Lens compiled from the signed definition (see below), state (draft, checked), checked by |
| `trial.json` | P03 | per measure: our figure, their figure, result (matches, gap, cannot be worked out), difference, likely reason, what is missing |
| `findings.json` | P03 | per measure: group (ready, unclear, unknown), reasons, affected pain points; the risk list: id, kind (risk, ambiguity, unknown), text, measures, pain points, decision {accepted or sent_back, note, by, at} |
| `plan.json` | P04 | three bands (now 0-3 weeks, next 3-8, later 8+), items with measures delivered, pain points resolved, effort, team, blocked by, who unblocks, date, why de-scoped, covered by a running programme; signatures |
| `outcome` | P04 | on signing: a read-only record `plane.path("intents", "m3_connect", "outcomes", <id>.json)` for module 4 |

## Zones (D-036: the line sits at zero)
Scores run from -1 to 1. Zone: impact >= 0 and readiness >= 0 -> `p1` "Ready to scan, priority 1"; impact < 0 and readiness >= 0 -> `p2` "Ready to scan, priority 2"; impact < 0 and readiness < 0 -> `identify` "To be identified"; impact >= 0 and readiness < 0 -> `unknown` "Unknown zone: resolve first".

## Rules Lens compiles (P03)
A rule is data, never code: `{"measure": ..., "source": ..., "table": ..., "op": "sum|avg|count|min|max|ratio|difference|latest", "column": ..., "numerator": {...}, "denominator": {...}, "filters": [{"column", "op": "eq|ne|in|between|not_null", "value"}], "period": {"column", "from", "to"}, "group_by": optional}`. The engine (pure Python, stdlib) runs it on the uploaded rows locally. The model sees only the definition text, the column names and types; never rows, never figures (egress rules).

## Privacy and egress
Files stay in the plane. Only column names, types, counts and the definition text may go to the model, through the egress gateway, names tokenised. Groups under five are not shown. Never real client data: demos use `packs/family_office/1/demo_module3/`, marked illustrative.

## Routes and screens
Base `/api/modules/m3_connect/assessments/{assessment_id}/...`. Each package adds its routes under its own heading in `manifest.yaml` and `sh_platform/route_permissions.yaml` (default deny; the two must agree). **A signed assessment is read-only (M3-P04).** Once both people have signed the plan, every write (anything but GET) on `/assessments/{assessment_id}/...` answers 409 in plain words, whichever package owns the route, except `POST .../plan/sign`. A package does nothing to get this: `api/__init__.py` puts the router-level dependency `refuse_when_signed` (`api/signed_guard.py`) on the module's router, so a new route is covered. Its body is FastAPI's `{"detail": {"error": "signed", "message": ...}}`. A package that wants the screens' own shape `{"error", "message"}` (what `ui/src/api/client.ts` reads, so the message shows in plain words) builds its router as `from modules.m3_connect.api.signed_guard import GuardedRouter; router = GuardedRouter()`: same rule, answered before the route runs. Signed is read from `plan.json` `signed_at` (P04's file) or `assessment.json` state `signed`. The first signature already locks the plan, its edits and the risk decisions (module 2's rule), but not the other packages' routes.
Roles: company_admin, sponsor, analyst; the upload link for a source owner is a guest `entry` route like module 2's answer link. Screens under `ui/src/modules/m3_connect/<area>/`, one route each in `ConnectModule.tsx`.

## Scope and wording rules (M3-FIX-A, from the live run's defects D3, D5, D7 to D10)
- **Left out in module 2**: a measure in the baseline's `left_out` is not scored, tried, requested or planned. It is listed once, with its reason (masked for a viewer who may not see it): `left_out` on the plan answer, the map answer and the findings answer. A source that feeds no measure that is left in is off the map and the requests and is listed as "Not needed for any measure" (`not_needed` on the map and request-list answers, `sources.json`).
- **Data request and Scan** wait only on sources in zone p1 or p2 that feed at least one measure not left out, and not on a request the organiser withdrew (`revoked_at`) or marked "will not send" (`state: will_not_send`, set by `POST .../intake/requests/{id}/revoke` with body `{"will_not_send": true}`; asking again reopens it).
- **Trial** is done only when it was run and every rule Lens wrote was checked; until then Nira says the analyst has rules to check.
- **Findings**: a measure that matches is `ready` even with notes module 2 accepted (known risks); an ambiguity still open makes it `unclear`; a measure with no rule is `unknown`, "No rule yet", never ready. The plan words nothing outside Now as ready.
- **Risks**: a risk about a restricted measure has `restricted: true` and is decided by the head of data (or the organiser). `GET .../risks` adds `notes` (one line per person who accepted module 2 ambiguities) and `restricted_note` (for viewers who cannot see them). "Accept all remaining" answers `accepted`, `left_hidden`, `left` and `message` (how many, how many left, why).
- **Nira** (`GET .../next`): the signed plan ends it ("The plan is signed. Module 4 starts from it."); otherwise the first step in progress, else the first not started. The plan step names who decides: the sponsor, the head of data for restricted risks, who signs next.
- **Text**: module 2's text is plain (no backticks or asterisks), a catalogue row id becomes the row's name or is dropped. No date is `date: null` and `date_text: null`; the screen says "No date yet".

## Packages
- SCAFFOLD: module folder, manifest, catalogue entry renamed "Assess and plan" with agent Lens, assessment create/read from a signed baseline, status, UI module shell with the step list and Nira's side panel slot.
- DATA: demo inputs in `packs/family_office/1/demo_module3/`.
- P01 source map: scoring, zones, map screen (SVG scatter), source panel, override with reason.
- P02 intake: requests by link, upload, read rows (stdlib Excel reader, CSV, JSON), match and profile, benchmarks.
- P03 trial: compile rules, run, compare, explain, findings and the risk list.
- P04 plan: draft the plan, accept risks, accept and sign the plan, outcome for module 4, Nira's next-step panel.
