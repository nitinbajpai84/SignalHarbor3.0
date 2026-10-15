"""RUN1: GET /api/v1/ops/runs (latest 100; ?mode=test|production, ?kind=) and GET /api/v1/ops/runs/{run_id} (with its steps). Data team only."""
from fastapi import APIRouter, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import run_log
from sh_platform.v1.seats import DATA_ENGINEER, require_seat

router = APIRouter()


@router.get("/api/v1/ops/runs")
def runs(request: Request, mode: str | None = None, kind: str | None = None) -> dict:
    require_seat(request, DATA_ENGINEER)
    return {"runs": run_log.list_runs(_plane(request), mode, kind, 100)}


@router.get("/api/v1/ops/pipelines")
def pipelines(request: Request) -> dict:
    """Operations > Live pipelines: each pipeline's own last production run and its next scheduled run."""
    require_seat(request, DATA_ENGINEER)
    return {"pipelines": run_log.pipelines(_plane(request))}


@router.get("/api/v1/ops/runs/{run_id}")
def one(run_id: str, request: Request) -> dict:
    require_seat(request, DATA_ENGINEER)
    r = run_log.get_run(_plane(request), run_id)
    if not r:
        raise HTTPException(404, {"error": "not_found", "message": "There is no such run."})
    return r
