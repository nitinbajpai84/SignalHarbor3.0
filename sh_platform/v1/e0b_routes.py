"""E0b2 routes: sheet mapping records.

- `GET /api/v1/model/mappings?state=` -> list;  `GET /api/v1/model/mappings/{id}` -> one (columns: source, target_table, target_field, transform)
- `PUT /api/v1/model/mappings/{id}` {columns: [{source, target, date_format?, multiply?, decimal?}], fixed?: {"table.field": value}} -> the mapping, corrected
- `POST /api/v1/model/mappings/{id}/approve`;  `POST /api/v1/model/mappings/{id}/reject` {reason}
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import e0b_mappings as M
from sh_platform.v1.i2_routes import _answer, _json_body
from sh_platform.v1.seats import viewer_of

router = APIRouter()


@router.get("/api/v1/model/mappings")
def mappings(request: Request, state: str = ""):
    viewer_of(request)
    return _answer(lambda: M.listing(_plane(request), state or None))


@router.get("/api/v1/model/mappings/{mapping_id}")
def one(mapping_id: str, request: Request):
    viewer_of(request)
    return _answer(lambda: M.get(_plane(request), mapping_id))


@router.put("/api/v1/model/mappings/{mapping_id}")
async def edit(mapping_id: str, request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, 65536)
    return body if isinstance(body, JSONResponse) else _answer(lambda: M.edit(_plane(request), mapping_id, viewer, list(body.get("columns") or []), dict(body.get("fixed") or {})))


@router.post("/api/v1/model/mappings/{mapping_id}/approve")
def approve(mapping_id: str, request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: M.approve(_plane(request), mapping_id, viewer))


@router.post("/api/v1/model/mappings/{mapping_id}/reject")
async def reject(mapping_id: str, request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, 8192)
    return body if isinstance(body, JSONResponse) else _answer(lambda: M.reject(_plane(request), mapping_id, viewer, str(body.get("reason") or "")))
