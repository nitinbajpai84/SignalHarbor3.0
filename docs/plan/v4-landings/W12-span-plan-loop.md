# W12-span-plan-loop

Finding: no code change. The gold-table model path is not in b6_plan.py (that file is the plan store, validator and approval, with no model call). It lives in b6_span.py `_ask_model` (line ~279), and it is already a tool loop, not one JSON prompt:

- `run_agent(...)` over `ST.span_registry(...)`, which is `agent_tools.tools_for(plane, viewer, "span", ...)` plus Span's own get_plan, get_run_log, profile_table, dry_run_sql and propose_plan_change.
- Tables drafted by `propose_plan_change` arrive as `res.proposals` (already checked by `B.validate`) and are merged with the JSON reply; every table then goes through `keep_valid` again.

Only gap: the tool loop is used when `viewer` and `pid` are given; otherwise it falls back to an empty registry (single prompt). `propose_plan` always passes both, so the plan path always loops. Nothing to change in b6_span.py; b6_plan.py needs no model code (not edited).

Tests: tests/v1/test_span_loop.py already covers the loop, refusals, no-rows dry run, injection, number guard, access and model-off. See the result in the build report.

## Review

Verdict: accept, no code change. Checked b6_span.py lines 296-297: `_ask_model` builds `ST.span_registry(...)` and calls `run_agent`, so the card premise was out of date. Re-ran tests/v1/test_span_loop.py: 8 passed. Scope clean (only this note written, no backups needed). Open items: none. The builder's remark about subagent token/cost data is outside this card and was not actionable here.
