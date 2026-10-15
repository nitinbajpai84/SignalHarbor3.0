"""E5a routes: the Role Pulse.

- `GET /api/v1/pulse2/items?on_date=YYYY-MM-DD&role=cio` -> {role, roles, items}  (the signed-in person's cards for that role)
- `POST /api/v1/pulse2/items/{id}/acknowledge`
- `POST /api/v1/pulse2/items/{id}/dismiss` {reason}  (a reason is required)"""
from datetime import date

from fastapi import APIRouter, Body, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import e5_pulse as P
from sh_platform.v1.seats import NO_SPACE, viewer_of

router = APIRouter()
BASE = "/api/v1/pulse2/items"


def _run(request: Request, fn):
    viewer = viewer_of(request)
    try:
        return fn(_plane(request), viewer)
    except PermissionError:
        raise HTTPException(403, {"error": "forbidden", "message": NO_SPACE}) from None
    except P.Refused as e:
        raise HTTPException(e.status, {"error": "not_allowed", "message": e.message}) from None


@router.get(BASE)
def get_items(request: Request, on_date: str = "", role: str = ""):
    try:
        day = date.fromisoformat(on_date) if on_date else None
    except ValueError:
        raise HTTPException(400, "on_date must look like 2026-10-09") from None
    return _run(request, lambda p, v: P.view(p, v, day, role or None))


@router.post(BASE + "/{item_id}/acknowledge")
def post_acknowledge(request: Request, item_id: str):
    return _run(request, lambda p, v: P.acknowledge(p, v, item_id))


@router.post(BASE + "/{item_id}/dismiss")
def post_dismiss(request: Request, item_id: str, body: dict = Body(default_factory=dict)):
    return _run(request, lambda p, v: P.dismiss(p, v, item_id, str(body.get("reason") or "")))
