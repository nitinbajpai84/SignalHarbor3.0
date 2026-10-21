"""Harbor 3.0 Knowledge, the use case story (logic in v3_knowledge_story). This company only.
GET /api/v3/knowledge/usecases -> {groups:[{domain,name,count,items}], domains, total}
GET /api/v3/knowledge/usecase/{tid} -> one use case from who asked down to the files, with the edges of its path
GET /api/v3/knowledge/domain/{id} -> a domain: its use cases as columns and the rows Decisions, KPIs, Gold, Silver, Bronze
GET /api/v3/knowledge/model/logical -> the business objects in plain words, their relations, rows and the KPIs that read them
GET /api/v3/knowledge/model/physical?kpi= -> lanes Bronze, Silver, Gold, KPIs with row counts; with kpi, only that KPI's path
GET /api/v3/knowledge/decisions -> signed rules, decisions and assumptions, each with the use cases it affects
Every failure answers a plain message, never a trace."""
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from sh_platform.profile.api import _plane
from sh_platform.v1 import v3_knowledge_story as S

log = logging.getLogger(__name__)
router = APIRouter()


async def _run(request: Request, fn, *args):
    plane = _plane(request)
    try:
        return await run_in_threadpool(lambda: fn(plane, request.app.state.account_store.in_company(plane.company_id), *args))
    except Exception:  # noqa: BLE001 - a plain message, never a trace
        log.warning("v3 knowledge story failed", exc_info=True)
        raise HTTPException(502, "I could not read that just now. Please try again.") from None


@router.get("/api/v3/knowledge/usecases")
async def get_usecases(request: Request):
    return await _run(request, S.usecases)


@router.get("/api/v3/knowledge/usecase/{tid}")
async def get_usecase(tid: str, request: Request):
    got = await _run(request, S.usecase, tid)
    if got is None:
        raise HTTPException(404, "The office does not know that use case.")
    return got


@router.get("/api/v3/knowledge/domain/{did}")
async def get_domain(did: str, request: Request):
    got = await _run(request, S.domain, did)
    if got is None:
        raise HTTPException(404, "The office has no such domain.")
    return got


@router.get("/api/v3/knowledge/model/logical")
async def get_logical(request: Request):
    return await _run(request, S.logical)


@router.get("/api/v3/knowledge/model/physical")
async def get_physical(request: Request, kpi: str | None = None):
    return await _run(request, S.physical, kpi)


@router.get("/api/v3/knowledge/decisions")
async def get_decisions(request: Request):
    return await _run(request, S.decisions)
