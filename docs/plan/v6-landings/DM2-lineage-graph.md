# DM2: Lineage graph on Map > Data model

Screenshot: `docs/plan/v6-landings/dm2-lineage.png` (silver.benchmark_components picked, seeded Evergreen env).

## What changed
- **Toggle** "Tables | Lineage" next to Loaded / Whole model in `ui/src/v1/k3/ModelTab.tsx`. Loaded / Whole model and Find still decide which tables are drawn.
- **Graph** `ui/src/v1/k3/Lineage.tsx` reuses `OntoGraph` (its layout, fit/zoom/pan) rather than a new library. Columns left to right: Sources, Bronze, Silver, Gold, Dashboards and reports, Projects. Silver wraps into extra sub-columns after 12 tables so the page stays readable.
- **Pick a node**: everything upstream and downstream is lit, the rest dimmed, edges on the path drawn bright. `OntoGraph` got one optional prop `path` for this; the ontology is unchanged. Picking a table also opens the existing column and "If this table changes" panels.
- **Badge**: silver nodes read "used by N projects" (projects that own a gold table downstream).
- **Endpoint** `GET /api/v1/centre-map/model` gains `lineage: {nodes, edges}` (`_lineage` in `sh_platform/v1/k3_model.py`), read-only, from records already used: source to bronze (layer registry source), bronze to silver and silver to gold (plan `depends_on` and `lineage`), gold to dashboard or report (tile SQL), gold to project (registry/plan owner). Nodes and edges are limited to what the viewer was given: non-data roles get gold, dashboards, reports and their projects only (no sources, bronze or silver).
- `model.fixtures.json` regenerated with the new key.

## Tests
- `pytest tests/v1/test_k3_model.py tests/v1/test_k3.py`: all edge kinds present, used_by count, access filtering.
- `cd ui && npx vitest run src/v1/k3 --pool=threads` (default fork pool timed out on this loaded box): toggle, upstream/downstream highlight, used-by badge. `npx tsc --noEmit` clean.

## Limits
- Bronze to silver edges exist only where an approved plan lists the bronze table in a silver table's `depends_on`; row-level load ids (source_records) are not read.
- Unloaded tables are hidden in Loaded mode, so a chain through one shows broken until Whole model is chosen.
