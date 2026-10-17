"""Harbor 3.0 figure records (logic in v3_figstore; contract in docs/v3/STEP1-DECISION-SCHEMAS.md). Failures answer a plain message."""
from fastapi import APIRouter, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import v3_figstore as FS

router = APIRouter()


def _rec(request: Request, figure_id: str) -> dict:
    rec = FS.read(_plane(request), figure_id)
    if rec is None:
        raise HTTPException(404, "I cannot find that figure.")
    return rec


@router.get("/api/v3/figures")
def list_figures(request: Request):
    return [FS.row(r) for r in FS.every(_plane(request))]


@router.get("/api/v3/figures/{figure_id}")
def get_figure(figure_id: str, request: Request):
    return FS.detail(_plane(request), _rec(request, figure_id))


@router.post("/api/v3/figures/{figure_id}/rollback")
async def rollback(figure_id: str, request: Request):
    _rec(request, figure_id)
    try:
        body = await request.json()
    except ValueError:
        body = None
    me = request.app.state.account_store.get(request.state.account_id) or {}
    try:
        got = FS.rollback(_plane(request), figure_id, (body or {}).get("v") if isinstance(body, dict) else None, me.get("display_name"), "company_admin" in (request.state.roles or []))
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    return FS.detail(_plane(request), got)
