# W01-step-cost: Model step cost tracking (9 Oct 2026)

## What changed

In `sh_platform/agents/loop.py`, each model step in the trace now records `cost_usd` — the sum of costs from all attempts in that step. Cost is computed from model tokens and the router's list-price table (`sh_platform/v1/model_modes.yaml`).

- **Code**: `sh_platform/agents/loop.py` `_model_step()` function (3 lines added).
- **Tests**: `tests/agents/test_agents_loop.py` — two new tests verify cost_usd in trace (both pass; all 18 loop tests pass, 143 total agent tests pass).
- **Trace format**: Each `{"kind": "model", ...}` entry in `AgentResult.trace` now includes `"cost_usd": <float or null>`.

## How to see it

Run an agent and inspect `trace`:

```python
from sh_platform.agents.loop import run_agent
result = run_agent(model, registry, company_id, module_id, agent, system_prompt, context, question)
for step in result.trace:
    if step["kind"] == "model":
        print(f"Step {step['n']}: {step['tokens_in']} in, {step['tokens_out']} out, cost ${step['cost_usd']}")
```

Via the run log (`GET /api/v1/agent-runs/trace/{trace_id}`), each step shows `cost_usd`.

## Architecture

- Router (`sh_platform/v1/router.py`) computes `cost_usd` for each model call attempt and stores it in `RoutedModel.attempts`.
- Loop (`sh_platform/agents/loop.py`) sums cost from all attempts per step and adds it to the trace.
- Null when the model has no price in `model_modes.yaml` or no reply was received.

## Open

- The mod to visualize running subagents, token spend, and costs has not been built (user request: show via /mod).
- Traces currently show 50 most-recent cost rows; aggregation and historical views await UI work.

## Review

Verdict: pass after one fix. Builder's sum treated unpriced attempts as 0.0, so an unpriced model showed cost 0 instead of null. Fixed in `_model_step` (sums only numeric costs, null if none) and added `test_model_step_cost_usd_null_when_unpriced`. Scope: only loop.py and its test changed in the repo. The "Open" note above about the mod is out of this card's scope: the mod lives outside the repo (`~/.claude/dev-mods/...`) and was not reviewed here.
