"""Harbor 3.0 Knowledge: GET /api/v3/knowledge -> {nodes, edges, processes, things, empty} and GET /api/v3/knowledge/thing/{id}?up=N&down=M -> one thing's neighbourhood, this company only (logic in v3_knowledge)."""
import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from sh_platform.profile.api import _plane
from sh_platform.v1 import v3_knowledge as K

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/v3/knowledge")
async def get_knowledge(request: Request):
    plane = _plane(request)
    try:
        return await run_in_threadpool(lambda: K.build(plane, request.app.state.account_store.in_company(plane.company_id)))
    except Exception:  # noqa: BLE001 - a plain message, never a trace
        log.warning("v3 knowledge failed", exc_info=True)
        raise HTTPException(502, "I could not read what the office knows just now. Please try again.") from None


@router.get("/api/v3/knowledge/thing/{thing_id}")
async def get_thing(thing_id: str, request: Request, up: int = Query(1, ge=0, le=20), down: int = Query(1, ge=0, le=20)):
    plane = _plane(request)
    try:
        got = await run_in_threadpool(lambda: K.thing(plane, request.app.state.account_store.in_company(plane.company_id), thing_id, up, down))
    except Exception:  # noqa: BLE001 - a plain message, never a trace
        log.warning("v3 knowledge thing failed", exc_info=True)
        raise HTTPException(502, "I could not read that just now. Please try again.") from None
    if got is None:
        raise HTTPException(404, "The office does not know that thing.")
    return got
