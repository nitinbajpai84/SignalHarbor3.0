"""C4 routes: the context library and each conversation's ticks. Body reading, decoding and refusals come from I2's routes.

- `GET /api/v1/library?q=` → [items the viewer may see]
- `POST /api/v1/library` {name, data (base64), kind?, note?, share?, iid?, force?} → {item} | {duplicate} | {similar}
- `PUT /api/v1/library/{id}` {note?, kind?, visibility?} → item;  `DELETE /api/v1/library/{id}` → {deleted}
- `GET|PUT /api/v1/intents/{iid}/context` {library_ids} → {library_ids, items}
- `GET /api/v1/intents/{iid}/context/suggestions` → [items]
"""
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import c4_library as L
from sh_platform.v1 import l3_library as F
from sh_platform.v1.i2_routes import MAX_FILE_BODY, _answer, _decode, _json_body, _model
from sh_platform.v1.seats import viewer_of

router = APIRouter()


def _context(plane, iid: str, viewer) -> dict:
    items = [L.shown(i, viewer, plane) for i in L.selected(plane, iid, viewer)]
    return {"library_ids": [i["id"] for i in items], "items": items}


@router.get("/api/v1/library")
def list_library(request: Request, q: str = ""):
    viewer = viewer_of(request)
    F.ensure(_plane(request), _model(request, _plane(request)))  # L3: the first read after deploy sorts the library
    return _answer(lambda: L.listing(_plane(request), viewer, q))


@router.post("/api/v1/library")
async def upload(request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, MAX_FILE_BODY)
    if isinstance(body, JSONResponse):
        return body
    return await run_in_threadpool(_answer, lambda: L.upload(
        _plane(request), viewer, str(body.get("name") or ""), _decode(body.get("data")), kind=body.get("kind"),
        note=str(body.get("note") or ""), share=body.get("share") is True, iid=body.get("iid") or None, force=body.get("force") is True,
        sensitivity=body.get("sensitivity"), topic=body.get("topic"), reviewed=body.get("reviewed") is True,  # K1
        folder=body.get("folder"), folder_by=body.get("folder_by")))  # L3


@router.put("/api/v1/library/{item_id}")
async def change(item_id: str, request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, 16 * 1024)
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: L.change(_plane(request), viewer, item_id, body))


@router.delete("/api/v1/library/{item_id}")
def delete(item_id: str, request: Request):
    viewer = viewer_of(request)

    def work():
        L.delete(_plane(request), viewer, item_id)
        return {"deleted": item_id}
    return _answer(work)


@router.get("/api/v1/intents/{iid}/context")
def get_context(iid: str, request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: _context(_plane(request), iid, viewer))


@router.put("/api/v1/intents/{iid}/context")
async def put_context(iid: str, request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, 64 * 1024)
    if isinstance(body, JSONResponse):
        return body

    def work():
        ids = body.get("library_ids")
        if not isinstance(ids, list):
            raise L.Refused(400, "Send the list of ticked files.")
        plane = _plane(request)
        L.save_ids(plane, iid, viewer, ids)
        return _context(plane, iid, viewer)
    return _answer(work)


@router.get("/api/v1/intents/{iid}/context/suggestions")
def get_suggestions(iid: str, request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: L.suggestions(_plane(request), iid, viewer))
