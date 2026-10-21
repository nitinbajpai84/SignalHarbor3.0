"""Build > Connections and Build > Onboarding (v3_connections). /api/v3/connections already serves the Trust page's pull sources (v3_ops), so
the connector framework lives at /api/v3/connectors."""
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from sh_platform.profile.api import _plane
from sh_platform.v1 import v3_connections as C

router = APIRouter()


async def _json(request: Request) -> dict:
    try:
        body = await request.json()
    except ValueError:
        body = None
    return body if isinstance(body, dict) else {}


@router.get("/api/v3/connectors")
def get_connectors(request: Request):
    return {"connectors": C.listing(_plane(request))}


@router.post("/api/v3/connectors/{cid}/run")
async def post_run(request: Request, cid: str):
    plane, b = _plane(request), await _json(request)
    try:
        since = date.fromisoformat(b["since"]) if b.get("since") else None
    except (ValueError, TypeError):
        raise HTTPException(400, "since must be a date like 2026-09-01.") from None
    try:
        return await run_in_threadpool(C.run, plane, cid, since)
    except KeyError:
        raise HTTPException(404, "I do not know that connector.") from None


@router.get("/api/v3/onboarding")
async def get_onboarding(request: Request):
    return await run_in_threadpool(C.onboarding, _plane(request))


@router.post("/api/v3/onboarding/{sid}/tick")
async def post_tick(request: Request, sid: str):
    plane, b = _plane(request), await _json(request)
    me = request.app.state.account_store.get(request.state.account_id) or {}
    by = me.get("display_name") or me.get("email") or "someone"
    try:
        return await run_in_threadpool(C.tick, plane, sid, by, b.get("done") is not False, str(b.get("note") or ""))
    except KeyError:
        raise HTTPException(404, "I do not know that step.") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
