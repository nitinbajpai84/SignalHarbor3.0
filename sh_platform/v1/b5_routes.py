"""B5 routes: GET /api/v1/ops, POST /api/v1/ops/loaded. Alert ack/close stay on the kernel routes (/api/company/build/alerts/...)."""
from fastapi import APIRouter, Body, HTTPException, Request

from sh_platform.profile.api import _plane, _viewer
from sh_platform.v1 import b5_ops, wh

router = APIRouter()


@router.get("/api/v1/ops")
def get_ops(request: Request) -> dict:
    return b5_ops.summary(plane := _plane(request), wh.today(plane))


@router.post("/api/v1/ops/loaded")
def post_loaded(request: Request, body: dict = Body(...)) -> dict:
    try:
        return b5_ops.mark(_plane(request), body, _viewer(request).name or "someone")
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
