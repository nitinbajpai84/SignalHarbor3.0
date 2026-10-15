"""CS1 route: GET /api/v1/consume/daily?currency=USD|SGD[&as_of=YYYY-MM-DD] -> the key numbers band. Read only. Logic and access: k9_daily."""
import logging
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import k9_daily
from sh_platform.v1.seats import viewer_of

log = logging.getLogger(__name__)
router = APIRouter()


def _json(v):
    if isinstance(v, Decimal):
        return format(v, "f")  # never "0E-8"
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _json(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_json(x) for x in v]
    return v


@router.get("/api/v1/consume/daily")
async def get_daily(request: Request, currency: str = "USD", as_of: str = ""):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        return JSONResponse(_json(await run_in_threadpool(k9_daily.daily, plane, viewer, currency, as_of or None)))
    except ValueError:
        return JSONResponse({"error": "bad_request", "message": "Choose USD or SGD, and write a date like 2026-10-09."}, status_code=400)
