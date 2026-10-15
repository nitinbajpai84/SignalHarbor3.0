"""L3 routes: the library by folder.

- `GET /api/v1/library/folders?q=` -> {folders: [{folder, icon, count, items}], sorting, all}  (counts and items are the viewer's own view)
- `PUT /api/v1/library/{id}/folder` {folder} -> item  (the owner moves it; recorded)
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import l3_library as F
from sh_platform.v1.i2_routes import _answer, _json_body, _model
from sh_platform.v1.seats import viewer_of

router = APIRouter()


@router.get("/api/v1/library/folders")
def folders(request: Request, q: str = ""):
    viewer = viewer_of(request)
    plane = _plane(request)

    def work():
        F.ensure(plane, _model(request, plane))
        return F.folders(plane, viewer, q)
    return _answer(work)


@router.put("/api/v1/library/{item_id}/folder")
async def move(item_id: str, request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, 4 * 1024)
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: F.move(_plane(request), viewer, item_id, str(body.get("folder") or "")))
