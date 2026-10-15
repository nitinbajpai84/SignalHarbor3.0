# EG2: every agent tool result passes the egress row check

Files: `sh_platform/v1/agent_tools.py`, `sh_platform/v1/lumen_tools.py`, `sh_platform/v1/north_tools.py`, `skills/lumen/questions.md`, `tests/v1/test_context_egress_shape.py`, and two tool tests that asserted the old shapes (`tests/v1/test_agent_tools.py`, `tests/v1/test_lumen_loop.py`). `span_tools.py` needed no edit. Backups are in `.sh-tmp/*.bak-eg2`.

1. **One helper.** `agent_tools._plain` now runs `egress_fit.flatten` on every list. A record inside a list becomes one line, for example `name: day; type: date` or `run_id: r1; status: done; steps: table: a; status: ok; row_count: 12, ...`. Inside such a line the key already labels each number, so numbers stay bare there. A top-level number is still written as "label: value" (LOOP0). The `rows`/`records` drop and all access filtering are unchanged. This one change covers `list_tables`, `describe_table`, `get_definition` (concepts and variants) and `whoami_and_access` (projects). It also covers Span's `get_plan`, `get_run_log` and `profile_table`, which already went through `_plain`.
2. **Lumen.** `list_gold_tables` goes through `_plain`, giving one line per table: `name: gold_x; purpose: ...; columns: a (DATE), b (DECIMAL)`. `query_figure` had a second problem. The registry turns a group under five rows into `{"available": false}`, so two or more such groups formed a list of objects without `group_size`, which the gateway reads as raw rows. Groups under five rows are now left out of `groups`, and a `hidden` line says that some exist. The total was already withheld in that case.
3. **North.** `list_intents`, `get_process_map` and `list_sources` were already lines. `get_intent` is wrapped in `egress_fit.flatten` in case a goal list (readers, decisions) holds records.
4. **Tally.** No change. Every Tally tool already passes the check, as the new test shows.
5. **Guard test.** It calls every registered tool of every agent through `loop._run_tool`, so the bytes it checks are the ones the model sees, and runs `json_findings` on each result. The planes are seeded with two or more of each item:
   - Lumen and shared: 2 projects, 2 gold tables, groups under five rows.
   - Span: 2+ plan tables and 2 sandbox runs.
   - North: 2 intents, 2 steps and 2 sources.
   - Tally: the cash-break case.

   A read tool must answer. Only tools with nothing seeded to find may refuse (`explain_figure_source` and, for some agents, `describe_table`/`get_valuation_chain`), and their refusal text is checked too. Adding a tool without adding it to the test fails the test. One more check: `_plain` on a definition with two concepts × two variants. The earlier agent-turn checks are kept.
6. **Lumen skill.** The `questions.md` heading is back to "# Questions worth asking", which `test_c3` looks for. The whole Lumen skill is 4,871 characters against the 6,000 cap.

Tool tests updated for the new shapes. `test_agent_tools` reads table and project lines. In `test_lumen_loop`, hidden groups now come back as `groups == []` plus `hidden`.

Run: `test_context_egress_shape` (11), `test_agent_tools`, `test_span_loop`, `test_north_loop`, `test_lumen_loop`, `test_tally_loop`, `test_c3` and `test_v3_g1` all pass (110 passed).

Not done: when a line holds nested records (run steps, definition variants), the records are joined with ", ", so where one ends is visible only from the repeated first key. If the models misread this, give those two tools their own line format.

## Review
Verdict: accept. One shared helper (`agent_tools._plain` via `egress_fit.flatten`) serves agent, Span, Lumen and North tools. The guard test covers every registered tool and fails on an unlisted one. Access filtering unchanged. Re-run: the 7 loop/shape/tool/v3_g1 files gave 107 passed, plus test_c3 passed. No defects fixed. Open: nested records in run-step and variant lines are comma-joined.
