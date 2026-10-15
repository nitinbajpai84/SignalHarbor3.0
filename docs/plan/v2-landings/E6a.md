# E6a Agent run tracing

## What changed
`e6_trace.agent_run(plane, viewer, agent_type, model_id, prompt_version, tool_policy_version, exception_id=None, decision_intent_id=None)` is a context manager. It inserts an `agent_runs` row (status running) on entry and, on exit, updates `finished_at`, `run_status` (succeeded or failed), `tool_calls`, `cost_usd`, `output_artifact_uri`. An exception is recorded and re-raised. The yielded `Run` has `.id`, `.trace_id`, `.tool_call(n=1)`, `.output`.

Trace ids: `new_trace_id()`, `current_trace_id()`, `with trace(trace_id=None)`. A run uses the current trace id (or makes one) and sets it as current inside the run, so a case, pulse item or nested run opened inside shares it. Cards that want one id from arrival to pulse wrap the chain in `with trace() as tid:` and store `current_trace_id()` on their own rows.

Admin route (company_admin only): `GET /api/v1/agent-runs?day=&agent_type=` (runs by agent and day with failures, tool calls, cost, plus the latest 200 runs) and `GET /api/v1/agent-runs/trace/{trace_id}`.

## Files
`sh_platform/v1/e6_trace.py`, `e6a_routes.py`, `e6a.permissions.yaml`, `tests/v1/test_e6a.py`.

## Test on the demo
1. `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e6a.py -q` (4 tests).
2. In a shell, open a run in a tmp plane (see the test) and read it back with `e6_trace.summary(plane)`.
3. As company admin, open `/api/v1/agent-runs` once an agent card has written runs.

## Known limits
- Cost: the router cost log holds tokens, not dollars, so `cost_usd` is filled only from rows that carry `cost_usd` for the same agent within the run window; otherwise it is empty. No price table was invented. A rate card (decision for Nitin) would let this compute cost from tokens.
- Router rows are matched by `agent` name equal to `agent_type`.
- UUID columns: `acting_for_user_id` for an account id that is not a UUID is a fixed uuid5 under the company id. `exception_id` and `decision_intent_id` must be UUIDs.
- A run left "running" after a process kill stays "running"; no sweeper yet.

## Wiring for the orchestrator
- Register `e6a_routes.router` and `e6a.permissions.yaml` (auto-install should pick them up).
- Cards E2b, E4b, E5b should wrap model work in `agent_run`; E4a/E5a can store `current_trace_id()`.
- No new packages.
