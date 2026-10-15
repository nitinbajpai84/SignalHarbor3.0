"""K10 routes: the Consume reading room. All read-only; logic and access are in k10_note (every figure is filtered by what the viewer may see).

GET /api/v1/consume/today?currency=&as_of=           Today: the headline, four key numbers, what moved and the markets in one line
GET /api/v1/consume/health?currency=&as_of=          Financial health: every portfolio and entity with value, month P&L, return and how far we trust the value
GET /api/v1/consume/note?currency=&as_of=            the Morning Note (as the email and Slack carry it)
GET /api/v1/consume/email-note?currency=&as_of=      the same note as the daily email: {subject, html, text}
GET /api/v1/consume/pnl?currency=&as_of=             Daily P&L and NAV
GET /api/v1/consume/signals?currency=&as_of=&period= market signals: month | ytd | inception
GET /api/v1/consume/league?as_of=&rank=              the fund league: alpha | value
GET /api/v1/consume/index-map                        the signed fund-to-index mapping (and the proposal for funds not signed yet)
POST /api/v1/consume/index-map {rows: {fund_id: series_key}}  the head of data signs it (head of data seat)
GET /api/v1/consume/reports                          the reports library
GET /api/v1/consume/reports/{version_id}/pdf         a signed report version as a PDF
GET /api/v1/consume/reports/{version_id}/pptx        the same as a PowerPoint
Single-segment paths on purpose: /api/v1/consume/{iid}/{code} (card C1) owns every two-segment path."""
import logging

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from sh_platform.profile.api import _plane
from sh_platform.v1 import k10_note as N, read_cache, scope_memo, wh
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.k9_routes import _json
from sh_platform.v1.seats import viewer_of

log = logging.getLogger(__name__)
router = APIRouter()
BASE = "/api/v1/consume"
BAD = {"error": "bad_request", "message": "Choose USD or SGD, a period of month, ytd or inception, a ranking of alpha or value, and write a date like 2026-10-09."}


def _compute(plane, viewer, fn, args):
    with scope_memo.scope():  # the same question inside one request is worked out once
        return _json(fn(plane, viewer, *args))


async def _run(request: Request, fn, *args, keep: bool = True):
    """Answer a read. `keep`: reuse the answer until something is written (see read_cache); a request that writes passes keep=False."""
    viewer, plane = viewer_of(request), _plane(request)
    try:
        if keep:
            out = await run_in_threadpool(read_cache.kept, wh.path(plane), (viewer, fn.__name__, args), lambda: _compute(plane, viewer, fn, args))
        else:
            out = await run_in_threadpool(_compute, plane, viewer, fn, args)
        return JSONResponse(out)
    except ValueError:
        return JSONResponse(BAD, status_code=400)
    except Refused as e:
        return JSONResponse({"error": "refused", "message": e.message}, status_code=e.status)


@router.get(BASE + "/today")
async def get_today(request: Request, currency: str = "USD", as_of: str = ""):
    return await _run(request, N.today, currency, as_of or None)


@router.get(BASE + "/health")
async def get_health(request: Request, currency: str = "USD", as_of: str = ""):
    return await _run(request, N.health, currency, as_of or None)


@router.get(BASE + "/note")
async def get_note(request: Request, currency: str = "USD", as_of: str = ""):
    return await _run(request, N.morning_note, currency, as_of or None)


@router.get(BASE + "/email-note")
async def get_email_note(request: Request, currency: str = "USD", as_of: str = ""):
    return await _run(request, lambda p, v, c, a: N.render_email(N.morning_note(p, v, c, a)), currency, as_of or None)


@router.get(BASE + "/pnl")
async def get_pnl(request: Request, currency: str = "USD", as_of: str = ""):
    return await _run(request, N.pnl, currency, as_of or None)


@router.get(BASE + "/signals")
async def get_signals(request: Request, currency: str = "USD", as_of: str = "", period: str = "month"):
    return await _run(request, N.signals, currency, as_of or None, period)


@router.get(BASE + "/league")
async def get_league(request: Request, as_of: str = "", rank: str = "alpha"):
    return await _run(request, N.league, as_of or None, rank)


@router.get(BASE + "/index-map")
async def get_index_map(request: Request):
    return await _run(request, N.index_map)


@router.post(BASE + "/index-map")
async def post_index_map(request: Request):
    try:
        body = await request.json()
    except ValueError:
        body = {}
    rows = body.get("rows") if isinstance(body, dict) and isinstance(body.get("rows"), dict) else {}
    return await _run(request, N.sign_index_map, rows, keep=False)


@router.get(BASE + "/reports")
async def get_reports(request: Request):
    return await _run(request, N.reports_library)


@router.get(BASE + "/reports/{version_id}/pdf")
async def get_report_pdf(request: Request, version_id: str, currency: str = ""):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        data, name = await run_in_threadpool(N.report_pdf, plane, viewer, version_id, currency or None)
    except Refused as e:
        return JSONResponse({"error": "refused", "message": e.message}, status_code=e.status)
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"', "X-Content-Type-Options": "nosniff"})


@router.get(BASE + "/reports/{version_id}/pptx")
async def get_report_pptx(request: Request, version_id: str, currency: str = ""):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        data, name = await run_in_threadpool(N.report_pptx, plane, viewer, version_id, currency or None)
    except Refused as e:
        return JSONResponse({"error": "refused", "message": e.message}, status_code=e.status)
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "X-Content-Type-Options": "nosniff"})
