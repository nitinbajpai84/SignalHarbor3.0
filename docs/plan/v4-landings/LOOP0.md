# LOOP0: shared agent tools and per-step trace (9 Oct 2026)

Code: `sh_platform/v1/agent_tools.py`. Tests: `tests/v1/test_agent_tools.py` (39). Spec: `docs/plan/AGENT-LOOPS.md`.

## The call

```python
from sh_platform.v1.agent_tools import tools_for

tools_for(plane, viewer, agent, *, gate=None, module_id=None, iid=None, registry=None) -> ToolRegistry
```

- `agent`: `"north" | "span" | "lumen" | "tally"`. `module_id` defaults to the one that agent already runs under
  (`AGENT_MODULE`: north `m1_intent`, span `m4_build`, lumen `consume`, tally `m1_intent`). Pass the same `module_id` to `run_agent`.
- `gate`: default always on (the route has already checked entitlement). `iid`: limit `search_documents` to the files ticked for that conversation.
- `registry`: add to a registry that already holds the agent's own tools. A name already there is kept (North keeps its own `search_documents`).
- Per-agent tools (LOOP1..3) register on the returned registry with the same `module_id`.

```python
reg = tools_for(plane, viewer, "lumen")
res = run_agent(model, reg, company_id, "consume", "Lumen", system, ctx, question, recorder=RunRegistry(plane))
res.trace_id   # GET /api/v1/agent-runs/trace/{trace_id}  ->  {runs, steps}
```

## The seven tools (all read-only; every argument is required each time)

| Tool | Arguments | Returns |
|---|---|---|
| `search_documents` | `query` text 1..200, `max` whole 1..8 | passages "file, lines a-b: text" the person may read (doc_index words + meaning). Registered as OUTSIDE material |
| `recall_memory` | `topic` text 1..200 | `remembered` lines and `preferences` for this agent and this person (mem_agent) |
| `get_definition` | `term` text 1..120 | concepts with variants (team, project, owner, definition, formula, unit, period) and the difference line (k2_map, G1 filtered) |
| `explain_figure_source` | `kind` one of valuation, position, cash, nav, metric, case, tile; `item_id` id 1..64 | the six-step trail (a5_trail), figures written as sentences |
| `list_tables` | `layer` all/bronze/silver/gold, `starts_with` text 0..40 | name, layer, purpose; at most 40, no rows |
| `describe_table` | `table` text 1..100 | layer, purpose, column names and types (at most 40), no rows |
| `whoami_and_access` | none | name, roles, seats, centres opened, projects the person may see with their level |

Rules held: a bad argument is refused with a plain message whose first word names the argument; the registry's aggregate rule applies (a figure
is written as "label: value" text, never a bare number, so nothing is hidden and the guard does not treat it as a computed figure); access comes
from the existing readers (library K1/G1, definitions G1, trails E1d, bronze/gold tables of a project G1); nothing writes.

## The trace

- `AgentResult` gains `trace_id` and `trace` (list). `run_agent` records, per step: `model` (n, tier, tokens_in, tokens_out, tries, ms, ok, tool_calls),
  `tool` (n, tool, arg_keys, result_chars, refused, reason code, ms), then `guard` (numbers_replaced). Argument values, prompts and answers are never kept.
- Tier and tokens come from `RoutedModel.attempts` (new, in `router.py`); a plain model shows time only.
- A recorder that has `record_trace` keeps them: `RunRegistry.record_trace` writes `context/run_steps.jsonl`. `e6_trace.steps_for(plane, trace_id)` reads it
  and `GET /api/v1/agent-runs/trace/{id}` now returns `{runs, steps}`. The trace id is `e6_trace.current_trace_id()` when the work runs inside `e6_trace.trace()`,
  else new. The Settings > Agent runs screen still needs a small UI step to list `steps` (not done: no UI build in this card).
- Total elapsed ms is on each stored row (`elapsed_ms`).

## Files changed (backups in `.sh-tmp/<name>.bak-loop`)
`sh_platform/agents/loop.py`, `sh_platform/agents/runs.py`, `sh_platform/v1/router.py`, `sh_platform/v1/e6_trace.py`, `sh_platform/v1/e6a_routes.py`.
Not touched: `n1_tally.py`, `e4_investigate.py`, `data/`.

## Checked
`tests/v1/test_agent_tools.py` 39 passed; `tests/agents` 141, `tests/egress` 263, `tests/build` (runtime tools, routes, gateway, security, prove) 73,
`tests/intents/test_b14.py` 19, and e6a/b/c, doc_read, mem_agent, mem_routes, router, a5, k1, cx, i6a, b6 all pass. Two failures in
`tests/v1/test_v3_g1.py::test_skills_load_under_cap_whole[north|lumen]` (skill folder file set differs): not related to this card.

## Open
- Nothing uses `tools_for` yet: LOOP1..3 wire Lumen, Span and North (they call `run_agent` with an empty registry today).
- `get_definition` and `recall_memory` read live files; `context_for` (mem_agent, later) can replace `recall_memory`'s body without changing the schema.
