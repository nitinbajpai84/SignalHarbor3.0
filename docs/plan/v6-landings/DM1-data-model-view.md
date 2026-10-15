# DM1: the Data model view on the Map

Screenshot against the approved artboard (`DataModel.dc.html`): `docs/plan/v6-landings/dm1-data-model.png` (silver.position_snapshots picked).

## What changed

- **Map switch**: Ontology, Process map, **Data model**, Business glossary (`ui/src/v1/k3/MapPage.tsx`). Opens with `?tab=model` (the Map's own parameter) or `?view=model`; either is read.
- **Screen** `ui/src/v1/k3/ModelTab.tsx`: header "The data model" with the one-line model version ("core plus N approved additions"), find a table or column, "Loaded · N" (default: tables that exist with rows) and "Whole model · N" (unloaded ones dimmed), three columns with each layer's one-line meaning, every table shown as `bronze.x`, `silver.x`, `gold.x`. Silver is grouped by the DBML TableGroup names in plain words, in the model's order; company-added tables sit in "Added for this office · model vN" with a dashed outline. Pick a table: columns with type and meaning, group, rows, owner when recorded, what it reads (upstream), and "If this table changes" (gold tables, dashboards, reports, projects). Tables it feeds and reads are lit.
- **Endpoint** `GET /api/v1/centre-map/model` (`sh_platform/v1/k3_model.py`, route in `k3_routes.py`, declared in `k3.permissions.yaml`). Everything from existing records, nothing listed by hand:
  - tables and column notes: `e0a_catalogue` (core DBML plus approved versions); bronze and gold: its layer registry; visibility: `AgentTools._catalogue` (G1);
  - row counts: `AgentTools._counts` (aggregates only, never rows);
  - what feeds what: the build plans' `depends_on` and `lineage` (plans of projects the viewer may see), then the dashboards' tile SQL (`k3_map._dashboards`); a dashboard marked company-wide is called a report (`cx_dash.company_reports`);
  - bronze source name, cadence and owner: `k3_map._systems`; gold owner: the plan's proposer.
- **Access**: same rule as the rest of the Map. The data team sees every layer. Anyone else sees only the gold tables of projects they may see (`g1_access.may_see_project`) and the dashboards they may open, plus a line saying so. Row counts only.
- **Warehouse aliases** (approved): in the company warehouse `evidence.duckdb` the schemas `bronze`, `silver`, `gold` hold VIEWS over the real tables in `main`: `silver.position_snapshots` -> `main.position_snapshots`, `gold.investment_report_holdings_monthly` -> `main.gold_investment_report_holdings_monthly`, `bronze.administrator_positions` -> `main.bronze_administrator_positions`. No real table is renamed; every pipeline keeps its names. `e0a_catalogue.alias_layers(con, silver_names)` is idempotent (views replaced, views of vanished tables dropped); `refresh_aliases(plane)` is the same through `wh.connect` (the turn-taking path).
  - Where it runs (never on a read): at the end of `e0a_catalogue._migrate` (so on warehouse build/apply and on a model approval), after a live plan run (`b6_run.run`), and after an intake load registers its bronze table (`e0c_load._after_load`).
- **What I found in the two warehouses**: `evidence.duckdb` is the v1 company warehouse (`wh.connect`, everything in `main`, 42 core tables plus plan tables). `company.duckdb` (`sh_platform/warehouse/__init__.py`, `open_company`) is the older pipeline's file and already has its own schemas `bronze`, `silver`, `gold` with real tables; I left it alone. The aliases went into `evidence.duckdb` only, so no existing schema name is touched, and the two files never collide.
- **One side fix the aliases needed**: two readers asked `information_schema.columns` by table name only, so a silver alias would have doubled a table's column list. `e1_asof._columns` and `e1_write` now filter `table_schema = 'main'` (one phrase each; a test covers it). Other readers already filter on `main`, or build sets/dicts where a duplicate is harmless.

## How to test

- Start your own server on your own port (the test environment I used: `.sh-tmp/testenv/dm1/serve.py`, port 8621, data copy in the same folder; screenshot script `shot.py`). Sign in as Anita Rao, open Map, choose "Data model" (or `/centre/map?view=model`). Try: switch Loaded / Whole model, type `market value` or `portfolio_id`, pick `silver.position_snapshots`, then a gold table (it shows what it reads).
- Sign in as someone outside the data team: only ready-made figures of their projects appear.
- DBeaver: open `evidence.duckdb` read-only with the server stopped; schemas `bronze`, `silver`, `gold` list the views.
- Tests: `pytest tests/v1/test_k3_model.py tests/v1/test_k3.py` (endpoint payload, prefixed names, row counts, lineage and impact, company-addition group, access, aliases idempotent and not doubling columns, fixture keys); `cd ui && npx vitest run src/v1/k3` (the view: switch order, layers, loaded/whole, pick and impact, find, non-team note); `npx tsc --noEmit` clean.

## Can Span propose new silver tables for a new use case today?

Partly. The path exists but Span the agent cannot walk it by itself.

- The path that exists: a plan with a new silver table needs an E0a model change first (`b6_plan.validate`: "A new table needs a model change first"). `b6_span.propose_plan(..., model_change={add_table | add_column | dbml, note})` opens the E0a proposal (`e0a_catalogue.propose`, data engineer seat) and links it to the plan (`model_changes = <version>`); the plan then validates against core plus that proposal, and the head of data's approval of the plan approves the linked model version (`b6_plan.approve` -> `e0a_catalogue.approve`, architect seat, never the proposer; the sandbox trial runs on a copy first, then the warehouse is migrated and, now, the alias views are refreshed). The route is `POST .../plan/propose {model_change}` and the Build "Model changes" panel shows the diff. Separately the data agent (E0b) has `propose_model_change(reason, dbml)` for mapping work.
- The gap: Span's chat tools (`span_tools.propose_plan_change`) draft **gold tables only** (`layer: "gold"` is fixed). Neither Span's tools nor the b10 pack (`b10_pack._silver`) can author a new silver table or a model change; the pack only writes a note ("a model change adds it"), and `b6_span.draft_plan` builds silver as inserts into existing core tables. So today a person (data engineer) must supply the `model_change` when proposing the plan. Closing the gap would mean a `propose_model_change`-style tool on Span's registry that feeds `E.propose` and links the number to the plan. Not built, as asked.
- A related gap the new screen exposes: an approved addition appears in "Added for this office" only once approved; a proposal waiting for approval is not drawn.

## Departures from the brief

- URL: the Map already uses `?tab=`; the view opens with `?tab=model` and also reads `?view=model`.
- Non-team viewers see gold only (the Map's existing rule that source, file and table detail is the data team's), not silver or bronze.
- Silver group names are the DBML TableGroup names in plain words; the one word mapped is "rag" -> "search" ("Documents and search").
- A column without a note shows "Links to <table>" (from the model's own references) or "Identifies the row" (primary key); otherwise blank. Gold and bronze columns say "From <source column>" (plan) or "As received". No meaning is invented.
- Bronze tables appear once registered by an intake load or an approved plan; until the file is a real table in the warehouse it shows no row count and is dimmed in "Whole model".
