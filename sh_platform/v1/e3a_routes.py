"""E3a routes: the rules register.

- `GET /api/v1/rules` → [rule line];  `GET /api/v1/rules/{code}/history` → [version]
- `POST /api/v1/rules/{code}` {definition_text, parameters?, effective_from, rule_type?} → draft version
- `POST /api/v1/rules/versions/{id}/approve` → the signed version
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import e3_rules as R
from sh_platform.v1.i2_routes import _answer, _json_body
from sh_platform.v1.seats import viewer_of

router = APIRouter()


@router.get("/api/v1/rules")
def rules(request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: R.listing(_plane(request), viewer))


@router.get("/api/v1/rules/{code}/history")
def rule_history(code: str, request: Request):
    viewer = viewer_of(request)
    plane = _plane(request)

    def work():
        R.need_role(viewer)
        return R.history(plane, code)
    return _answer(work)


@router.post("/api/v1/rules/versions/{vid}/approve")
def approve(vid: str, request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: R.approve(_plane(request), viewer, vid))


@router.post("/api/v1/rules/import")
async def import_signed(request: Request):
    """{file_id, sheet?}: a signed limits workbook already uploaded to intake, read as proposed versions (UC5 G-3)."""
    viewer = viewer_of(request)
    body = await _json_body(request, 4096)
    if isinstance(body, JSONResponse):
        return body
    plane = _plane(request)

    def work():
        from sh_platform.v1 import e0c_landing as L
        from sh_platform.v1.i2_north import Refused
        try:
            rec = L.get(plane, str(body.get("file_id") or ""))
        except L.Refused as e:
            raise Refused(e.status, e.message) from None
        return R.import_signed(plane, viewer, L.original_path(plane, rec), body.get("sheet") or None)
    return _answer(work)


@router.post("/api/v1/rules/{code}")
async def propose(code: str, request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, 16384)
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: R.propose(_plane(request), viewer, code, body.get("definition_text", ""), body.get("parameters"),
                                     body.get("effective_from", ""), body.get("rule_type", "")))
