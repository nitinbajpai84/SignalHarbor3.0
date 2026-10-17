# Step 1: decision schemas and the live figure view (16 Oct)

Plan: https://claude.ai/artifact/XnUEvbsi8nJMwUh7cPUZDB (Step 1). The office never sees the word "ontology" or "schema". It sees
"Built from", "Where this number comes from", "What I assumed" and "Also used by".

## What a decision schema is
One record per figure the office has defined. It holds:
- what the figure means: name, definition, grain;
- how it is built: a recipe id, an office skill id, or a model design;
- its receipts.

It is versioned. It is built when a brief is confirmed, kept with its receipts, and reused when another brief names the same figure. The existing `th["bindings"]`
(figure → recipe, from v3_recipes) is its seed.

Store: `<company>/v3/figures/<figure_id>.json` (simple mode, files) — one file per figure, all versions inside.

```json
{"id": "fig-cash-break", "name": "Cash break", "definition": "...", "grain": ["entity", "day"],
 "versions": [{"v": 1, "built_from": {"kind": "recipe|skill|design", "id": "cash_break"},
   "reads": ["position_snapshots", "cash_movements"], "sql_hash": "…", "model": "…|null", "prompt_hash": "…|null",
   "assumptions": [{"text": "Money in is positive", "source": "ASSUMPTIONS A5|loader|person", "at": "…"}],
   "tie_out": {"rule": "…", "ok": true, "at": "…"}, "approved_by": "Daniel Foo", "approved_at": "…",
   "runs": [{"run_id": "…", "at": "…", "ok": true, "rows": 3}], "status": "verified|held|draft"}],
 "used_by": [{"thread": "…", "brief": "…", "person": "Grace Ong"}]}
```

## API (both agents build to this contract)
- `GET /api/v3/figures` → `[{id, name, current_v, status, built_from, used_by_count, last_run_at}]`
- `GET /api/v3/figures/{id}` → the full record above, plus `lineage`: `{files: [{name, rows}], tables: [...], figure: {...}}`
- `POST /api/v3/figures/{id}/rollback` `{v}` → makes an earlier verified version current again (company admin or the figure's approver only)
- On a thread: `GET /api/v3/threads/{tid}` adds `reuse: [{figure_id, name, built_from, verified_runs, first_used_by, suggest: true}]`
  while at Decision 1, when a brief figure matches an existing verified figure.
- `POST /api/v3/threads/{tid}/decide {n:1, answer:"confirm", reuse:{"<brief figure id>": "<figure_id>"|null}}` accepts or declines each reuse.
- Consume answer (`POST /api/v3/ask`) adds `figure: {id, name, v}` when the answer came from a figure, so the UI can link "Where this number comes from".

## Behaviour
1. **Confirm at Decision 1.** Each brief figure becomes a figure version (status `draft`), bound per v3_recipes. If a verified figure with the same
   binding or meaning exists, Decision 1 offers it: "Use Daniel's Cash by entity (verified, run 3 times)?" The person decides.
2. **Trial run at Decision 3.** The version gets its `reads`, `sql_hash`, its tie-out and its first run. The status becomes `verified`, or `held` when the tie-out fails.
3. **Each live run** appends to `runs`.
4. **A new version that fails its tie-out.** The figure stays on the last verified version: that is the rollback. Every thread using it shows the hold.
5. **Assumptions.** Each assumption is collected from the loaders' normalisations (sign, date format, side, label spelling) and from ASSUMPTIONS.md. Decision 2 shows them as
   "What I assumed".

## UI
- **Decision 1:** a "Built from" line per figure (exists), plus the reuse offer card.
- **Knowledge > Figures:** the list, then the figure page. It has these sections:
  - Lineage: files → tables → figure, drawn simply.
  - What I assumed.
  - Runs: date, ok, rows.
  - Versions, with Roll back.
  - Also used by.
- **Consume:** each answer that came from a figure gets a small "Where this number comes from" link to the figure page.
- **Colours** follow docs/v3/COLOURS.md:
  - verified = done green;
  - held = problem red;
  - draft = needs amber;
  - actions = act navy.

## Contract changes (backend, 16 Oct)
All additive; no shape above was removed.
- The ask answer's existing `figure: {label, value, change}` is kept; `id`, `name`, `v` are merged into the same object (v = the figure's current version).
- Each `reuse` offer on the thread view also carries `brief_figure` (the brief figure's own id, `fig-<slug of its name>`). The decide `reuse` map is keyed by the offer's `figure_id`: the same id to use it, `null` (or absent) to keep one's own, which makes a new version.
- The figure record has `current_v` and, per version, `reason` (why it is held) and `reads`. The list row and the detail add `hold: {v, reason} | null`: set when a newer version failed its tie-out and an earlier verified one stays current.
- Every thread view (any stage) adds `figures: [{figure_id, name, v, status, hold}]`, the figures the thread uses, so each thread shows the hold.
- Decision 2 adds `assumptions: [{figure, text, source}]` ("What I assumed").
- Rollback returns the full updated record (with `lineage`). Only `company_admin` or a person who approved a version of that figure may roll back (403 otherwise); an unverified version is 409.
- Chains C and M gain a last step "Recorded the run on each figure".
