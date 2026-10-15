"""E6a routes (company admin only).

- `GET /api/v1/agent-runs?day=YYYY-MM-DD&agent_type=` -> {by_agent_day: [{agent_type, day, runs, failures, tool_calls, cost_usd}], runs: [...]}
- `GET /api/v1/agent-runs/loops?agent=&offset=&limit=` -> {loops: [{trace_id, agent, at, steps, tokens, cost_usd, ms, outcome, worded_by, runs}],
  more} one line per trace of chat turns, newest first; filter by agent (north, span, lumen, tally), page with offset (RC-10)
- `GET /api/v1/agent-runs/trace/{trace_id}` -> {runs, steps, total} for one piece of work (steps: each model call, tool call and number guard of its loop runs;
  total: {cost_usd, tokens}, cost_usd is the sum of the steps' W01 prices or None when no step carried one)
- `GET /api/v1/agent-runs/model-trouble` -> {trouble: {code, providers, words, at} | null}: the Settings banner when the latest call to a model
  provider ended out of credit, with its key refused or its model unknown (codes and hosts from the egress log, never content)
Logic: e6_trace."""
from fastapi import APIRouter, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import e6_trace as T
from sh_platform.v1.seats import NO_SPACE, viewer_of

router = APIRouter()
BASE = "/api/v1/agent-runs"


def _admin(request: Request):
    viewer = viewer_of(request)
    if "company_admin" not in viewer.roles:
        raise HTTPException(403, {"error": "not_allowed", "message": "Only the company administrator can see agent runs."})
    try:
        return _plane(request)
    except PermissionError:
        raise HTTPException(403, {"error": "forbidden", "message": NO_SPACE}) from None


@router.get(BASE)
def runs(request: Request, day: str = "", agent_type: str = ""):
    return T.summary(_admin(request), day or None, agent_type or None)


@router.get(BASE + "/loops")
def loops(request: Request, agent: str = "", offset: int = 0, limit: int = 100):
    limit = max(1, min(int(limit), 200))
    rows = T.loop_traces(_admin(request), limit + 1, agent or None, max(0, int(offset)))
    return {"loops": rows[:limit], "more": len(rows) > limit}


@router.get(BASE + "/model-trouble")
def model_trouble(request: Request):
    return {"trouble": T.model_trouble(_admin(request))}


@router.get(BASE + "/trace/{trace_id}")
def trace_runs(request: Request, trace_id: str):
    plane = _admin(request)
    steps = T.steps_for(plane, trace_id)
    return {"runs": T.by_trace(plane, trace_id), "steps": steps, "total": total(steps)}


def total(rows: list[dict]) -> dict:
    """W14: tokens and price of all steps of the loop runs on one trace; price None when no step recorded one."""
    st = [s for r in rows for s in r.get("steps") or [] if isinstance(s, dict)]
    prices = [float(s["cost_usd"]) for s in st if s.get("cost_usd") is not None]
    return {"cost_usd": sum(prices) if prices else None,
            "tokens": sum(int(s.get("tokens_in") or 0) + int(s.get("tokens_out") or 0) for s in st)}
