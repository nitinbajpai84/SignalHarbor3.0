"""V5W-1 routes: `GET /api/v1/action/landing` the Action page; `GET /api/v1/projects/{pid}/assignments`;
`POST /api/v1/projects/{pid}/assign` {steps, to, message, due}; `POST /api/v1/projects/{pid}/handover` {to, message, due, steps?};
`POST /api/v1/assignments/{aid}/done|withdraw`. Mount: `app.include_router(p2_router)` from sh_platform.v1.p2_routes."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import e5_pulse
from sh_platform.v1 import p2_assign as A
from sh_platform.v1 import p2_pulse
from sh_platform.v1.seats import NO_SPACE, viewer_of

router = APIRouter()


@router.get("/api/v1/pulse")  # P2 Pulse, the landing's three bands: it shares this file's name with V5W-1, so it stays here
def get_pulse(request: Request) -> dict:
    viewer = viewer_of(request)
    try:
        plane = _plane(request)
    except PermissionError:
        raise HTTPException(403, {"error": "forbidden", "message": NO_SPACE}) from None
    return p2_pulse.build(plane, viewer)


def _run(request: Request, fn):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        return JSONResponse(jsonable_encoder(fn(plane, viewer)))
    except A.Refused as e:
        return JSONResponse({"error": "not_allowed" if e.status == 403 else "refused", "message": e.message}, status_code=e.status)
    except e5_pulse.Refused as e:
        return JSONResponse({"error": "not_allowed", "message": e.message}, status_code=e.status)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": NO_SPACE}, status_code=403)


async def _body(request: Request) -> dict:
    try:
        b = await request.json()
    except ValueError:
        return {}
    return b if isinstance(b, dict) else {}


@router.get("/api/v1/action/landing")
def get_landing(request: Request):
    return _run(request, lambda p, v: A.landing(p, v))


@router.get("/api/v1/projects/{pid}/assignments")
def get_assignments(pid: str, request: Request):
    return _run(request, lambda p, v: A.history(p, v, pid))


@router.get("/api/v1/projects/{pid}/assign/candidates")
def get_candidates(pid: str, request: Request):
    return _run(request, lambda p, v: A.candidates(p, v, pid))


@router.post("/api/v1/projects/{pid}/assign")
async def post_assign(pid: str, request: Request):
    b = await _body(request)
    message = b.get("message") if b.get("message") is not None else b.get("note")  # Build's dialog says "note"
    if b.get("handover") is True:
        return _run(request, lambda p, v: A.handover(p, v, pid, str(b.get("to") or ""), message, b.get("due"), b.get("steps")))
    return _run(request, lambda p, v: A.assign(p, v, pid, b.get("steps"), str(b.get("to") or ""), message, b.get("due")))


@router.post("/api/v1/projects/{pid}/handover")
async def post_handover(pid: str, request: Request):
    b = await _body(request)
    return _run(request, lambda p, v: A.handover(p, v, pid, str(b.get("to") or ""), b.get("message"), b.get("due"), b.get("steps")))


@router.post("/api/v1/assignments/{aid}/done")
def post_done(aid: str, request: Request):
    return _run(request, lambda p, v: A.finish(p, v, aid, "done"))


@router.post("/api/v1/assignments/{aid}/withdraw")
def post_withdraw(aid: str, request: Request):
    return _run(request, lambda p, v: A.finish(p, v, aid, "withdraw"))
