"""V5 D1 routes: Delivery, step 5 of a project. Logic: d1_delivery.

- `GET /api/v1/build/p/{pid}/delivery` -> channels (status, preview, what the person can do), kinds, approved dashboards, settings state, outbox
- `POST .../delivery/channels` {kind, dashboard_id, title?, when?, at?, addresses?, alert?} ; `POST .../channels/{cid}/submit|approve|stop` ; `.../send-back` {reason}
- `POST .../delivery/go-live` (nothing is sent now) ; `POST .../delivery/outbox/{oid}/retry` ; `GET .../delivery/summary` (project complete)
- `GET|PUT /api/v1/settings/delivery` (admin): {kind, secret, host}, the secret by name
- `GET /api/v1/consume/delivery-lines` -> the lines of live Morning Note channels"""
from fastapi import APIRouter, Body, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import d1_delivery as X
from sh_platform.v1.p1_project import Refused
from sh_platform.v1.seats import viewer_of

router = APIRouter()
BASE = "/api/v1/build/p/{pid}/delivery"
CH = BASE + "/channels/{cid}"
CODES = {400: "invalid", 403: "not_allowed", 404: "not_found", 409: "conflict"}


async def _run(request: Request, fn):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        return JSONResponse(D.jsonable(await run_in_threadpool(fn, plane, viewer)))
    except Refused as e:
        return JSONResponse({"error": CODES.get(e.status, "failed"), "message": e.message}, status_code=e.status)
    except PermissionError:
        return JSONResponse({"error": "not_allowed", "message": "You do not have access to this."}, status_code=403)


@router.get(BASE)
async def delivery_view(request: Request, pid: str):
    return await _run(request, lambda p, v: X.view(p, v, pid))


@router.post(BASE + "/channels")
async def channel_create(request: Request, pid: str, body: dict = Body(default_factory=dict)):
    return await _run(request, lambda p, v: X.create_channel(p, v, pid, body))


@router.post(CH + "/submit")
async def channel_submit(request: Request, pid: str, cid: str):
    return await _run(request, lambda p, v: X.submit_channel(p, v, pid, cid))


@router.post(CH + "/approve")
async def channel_approve(request: Request, pid: str, cid: str):
    return await _run(request, lambda p, v: X.decide_channel(p, v, pid, cid, True))


@router.post(CH + "/send-back")
async def channel_send_back(request: Request, pid: str, cid: str, body: dict = Body(default_factory=dict)):
    return await _run(request, lambda p, v: X.decide_channel(p, v, pid, cid, False, body.get("reason", "")))


@router.post(CH + "/stop")
async def channel_stop(request: Request, pid: str, cid: str):
    return await _run(request, lambda p, v: X.stop_channel(p, v, pid, cid))


@router.post(BASE + "/go-live")
async def delivery_go_live(request: Request, pid: str):
    return await _run(request, lambda p, v: X.go_live(p, v, pid))


@router.post(BASE + "/outbox/{oid}/retry")
async def outbox_retry(request: Request, pid: str, oid: str):
    return await _run(request, lambda p, v: X.retry(p, v, pid, oid))


@router.get(BASE + "/summary")
async def delivery_summary(request: Request, pid: str):
    return await _run(request, lambda p, v: X.summary(p, v, pid))


@router.get("/api/v1/settings/delivery")
async def settings_get(request: Request):
    def go(p, v):
        if not X.is_admin(v):
            raise Refused(403, "Only an administrator can see this.")
        return X.config_view(p)
    return await _run(request, go)


@router.put("/api/v1/settings/delivery")
async def settings_put(request: Request, body: dict = Body(default_factory=dict)):
    return await _run(request, lambda p, v: X.set_config(p, v, body.get("kind"), body.get("secret"), body.get("host")))


@router.get("/api/v1/consume/delivery-lines")
async def morning_lines(request: Request):
    return await _run(request, lambda p, v: {"lines": X.morning_note_lines(p, v)})
