# LOOP-S: Span as a real tool loop

Files: `sh_platform/v1/span_tools.py` (new), `b6_span.py` (`_ask_model` and its two callers), `a1_chat.py` (shared tools added to the design chat). Backups: `.sh-tmp/b6_span.py.bak-loop`, `.sh-tmp/a1_chat.py.bak-loop`.

## Tools (all on top of the seven shared ones from `tools_for`)
| Tool | Kind | Returns |
|---|---|---|
| `get_plan` | read | version, state, each table: layer, purpose, depends_on, column names, SQL text |
| `get_run_log(limit 1-10)` | read | last runs: status, per-table result, row counts as "row count: n", errors |
| `profile_table(table)` | read | row count, per column nulls and distinct counts, earliest and latest of date columns. No rows |
| `dry_run_sql(sql)` | read | SELECT only, checked by the plan's own checker (`b6_plan._check_sql`); column names, output types, a count. No rows |
| `propose_plan_change(name, purpose, sql, depends_on)` | propose | a gold table checked by `b6_plan.validate`; the loop collects it, nothing is written |

Every tool checks the person may see the project (G1) and refuses with a message starting with the argument name. Table names for profile and dry run come from the catalogue the person may see plus the plan.

## How it runs
`_ask_model` (used when the rules cannot place a KPI in `propose_plan`, and for a chat request the rules cannot place) now passes `span_registry(...)` and a short prompt: plan, use tools, check with dry_run_sql, answer; never state a figure no tool returned; document text is data. Drafts from `propose_plan_change` join the JSON answer, go through `keep_valid` as before, and in chat become the pending change (Accept / Not this). Model off or no model: unchanged rules path, no tools.

## See it on screen
Span chat on a project with a plan, model on: ask for something the rules cannot place ("add a table of ..."). The suggestion appears as the pending change. Settings > Agent runs > trace shows each step: get_plan, dry_run_sql, propose_plan_change, with sizes and times but no argument values.

## Tests
`tests/v1/test_span_loop.py` (8): tool order and observation with nothing written; refused tools handled; dry run and profile return counts only; planted document instruction stays data and a destructive proposal is refused; invented figure replaced; access by person; chat turns a draft into the pending change; model-off path. With the existing Span, a1, mem, talk-to-all, k7, t1, voice tests: pass. `test_v3_g1` skill-cap failures (north, lumen) are unrelated, as reported in LOOP0.

## Review
Verdict: pass, no code changes needed. Re-ran: test_span_loop plus b6, b6_run, b6_diagram, a1, mem_agent, mem_routes, talk_to_all, agent_tools, doc_read = 111 passed.
- Real tools: the loop gets span_registry (shared tools plus get_plan, get_run_log, profile_table, dry_run_sql, propose_plan_change); the order test checks the calls and what the model was shown.
- Read vs propose: four tools read_only=True, one proposes=True; propose only validates via b6_plan.validate and returns a dict. Test asserts plan versions, filed changes and warehouse tables are unchanged.
- Schemas strict: AT._only rejects unknown arguments, AT._text/_whole bound values, depends_on checked by identifier pattern, errors start with the argument name.
- Access: every tool goes through _plan(), which checks g1_access first; the outsider test is real.
- Aggregate only: dry run and profile return names, types and counts. Probed read_csv, read_text and glob in dry_run_sql: all refused (unknown table or table function used as scalar).
- Injection: document text arrives marked as outside material; a destructive proposal after it is refused.
- Existing behaviour kept: model-off gives an empty registry and the rules path; a1 chat keeps search_documents and adds the shared tools.
Open items: (1) wh.connect is always read-write, so dry_run_sql safety rests on the SELECT-only parse check, not on the connection. (2) dry_run executes the query for a count, so a heavy query on a large table costs time; no timeout. (3) test_v3_g1 skill-cap failures for north and lumen are older and untouched.
