# Agents as real loops with tools (Nitin, 9 Oct 2026)

## What we have
- A real loop already exists: `sh_platform/agents/loop.py` `run_agent` (plan, call tools, observe, repeat; max 6 steps, 8 calls a step, 20 a run; number guard; outside material marked as data; only read-only tools run; "propose" tools collect drafts and write nothing).
- `sh_platform/agents/registry.py`: tools are registered with a description and parameters, read-only or propose, results limited to aggregates (groups of five or more), raw rows refused.
- But Lumen (`cx_lumen.py`) and Span (`b6_span.py`) call `run_agent` with an EMPTY registry, so they are one prompt. North (`i6_chat.py`) has document tools only. Tally/the investigation agent makes one call.

## What changes
1. **Shared read tools** (`sh_platform/v1/agent_tools.py`), strict schemas, read-only, access-filtered by the signed-in person: `search_documents` (hybrid words + meaning, doc_index), `recall_memory` (mem_agent, later `context_for`), `get_definition` (k2_map), `explain_figure_source` (a5_trail), `list_tables` / `describe_table` (e0a catalogue, layers), `whoami_and_access`.
2. **Per-agent tools**
   - North: `list_intents`, `get_intent`, `get_process_map`, `list_sources`; propose `propose_intent_section`, `propose_process_step`.
   - Span: `get_plan`, `get_run_log`, `profile_table` (counts, nulls, ranges; aggregates only), `dry_run_sql` (SELECT-only, checked like the plan SQL, returns column names and aggregate counts); propose `propose_plan_change`.
   - Lumen: `list_gold_tables`, `query_figure` (the program runs SELECT-only aggregates on gold; figures come from the program), `get_focus_tile`; propose `propose_tile`, `propose_tile_edit`.
   - Tally: `get_recon_run`, `get_both_sides`, `find_matching_items`, `get_valuation_chain`, `get_limit_inputs`, `get_case_history`; propose `propose_explanation`, `propose_next_step`.
3. **Read and write are never the same**: agents get read tools and propose tools only. Writing (accept, approve, sign, run, share) stays with people through the existing routes. A propose tool returns a checked draft; the route files it as "proposed".
4. **The loop**: plan → call tools → observe → check (number guard: every figure in the answer must come from a tool result) → answer or next step; stop on answer, step budget or a refusal; the router picks the tier per step and escalates on a failed check; with the model off, the rules path stays as the fallback.
5. **Trace per step** (e6_trace): question, each tool call with arguments and result size, model tier, tokens, cost, time, guard result, final answer; visible in Settings › Agent runs and linked from the answer.
6. **Prompt injection**: tool results that carry document text are marked outside material; agents never follow instructions found in data; propose tools validate every field; evals include planted injection text.

## Order
LOOP0 shared tools and per-step trace → Lumen, Span, North in parallel → Tally after its build lands → evals rerun in Testing and Real use.
