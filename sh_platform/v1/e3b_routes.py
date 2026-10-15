"""E3b routes: run a reconciliation and list the last runs.

- `POST /api/v1/recon/{code}/run` {as_of_date: "YYYY-MM-DD", cutoff?: iso} → {recon_code, checked, breaks, opened: [exception id], skipped: [words]}
- `GET /api/v1/recon/runs` → last runs, newest first
"""
from datetime import date, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import e1_access, wh
from sh_platform.v1 import e3_recon as R
from sh_platform.v1.i2_routes import _answer, _json_body
from sh_platform.v1.seats import viewer_of

router = APIRouter()
READ_ONLY = "Your access to the company's data is read-only: you can read the checks and their results, but not run them."


def _may_run(plane, viewer) -> bool:
    """analyst-uc2-02, uc8-02: a run writes cases, so it needs full access to at least one portfolio; a read-only group (the Data team) reads only."""
    if e1_access.is_admin(viewer) or {"analyst", "head_of_data"} & set(viewer.roles or ()):
        return True  # FIXE1: the data team runs the checks, as the refusal itself names them; the 403 stays for everyone else
    return any(e1_access.level(plane, viewer, portfolio_id=p) == "full" for p in e1_access.visible_portfolios(plane, viewer))


@router.post("/api/v1/recon/{code}/run")
async def run(code: str, request: Request):
    v = viewer_of(request)
    if not _may_run(_plane(request), v):
        return JSONResponse({"error": "forbidden", "message": READ_ONLY}, status_code=403)
    body = await _json_body(request, 4096)
    if isinstance(body, JSONResponse):
        return body
    try:
        on = date.fromisoformat(str(body["as_of_date"])[:10]) if body.get("as_of_date") else wh.today(_plane(request))  # FIXE2: no day = the cycle date
        cutoff = datetime.fromisoformat(body["cutoff"]) if body.get("cutoff") else None
    except ValueError:
        return JSONResponse({"error": "invalid", "message": "Give the day as YYYY-MM-DD."}, status_code=400)
    return _answer(lambda: R.run_detail(_plane(request), code, on, cutoff, who=v.name))


@router.get("/api/v1/recon/runs")
def runs(request: Request):
    viewer_of(request)
    return _answer(lambda: R.last_runs(_plane(request)))
