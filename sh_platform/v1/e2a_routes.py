"""E2a routes: manager statement intake.

- `POST /api/v1/evidence/documents` {filename, data (base64), source_code?, received_at?} → {id, document}   (upload; files travel as base64 JSON like I2)
- `GET /api/v1/evidence/documents?instrument_id=` → {documents}, newest received first, each with `current`, `instrument_name`, `label` Current|Superseded
- `GET /api/v1/evidence/documents/{id}` → the screen detail {id, instrument_name, valuation_date, versions[], fields[], match, can_review} (e2_screen)
- `GET /api/v1/evidence/documents/{id}/original` → the original file
Logic: e2_intake; the screen shapes: e2_screen. Only documents the viewer may see (Operations all; others through E1d).
"""
import base64
import binascii
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import e2_intake as E
from sh_platform.v1 import e2_screen as S
from sh_platform.v1.i2_routes import _answer, _json_body, _plain
from sh_platform.v1.seats import viewer_of

router = APIRouter()
BASE = "/api/v1/evidence/documents"
LIMIT = 25_000_000


@router.post(BASE)
async def upload(request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, LIMIT * 4 // 3 + 10_000)
    if not isinstance(body, dict):
        return body
    try:
        data = base64.b64decode(str(body.get("data") or ""), validate=True)
        received = datetime.fromisoformat(body["received_at"]) if body.get("received_at") else None
    except (binascii.Error, ValueError):
        return _plain(400, "bad_request", "That file could not be read. Please try again.")
    name = str(body.get("filename") or "").strip()
    if not name or not data:
        return _plain(400, "bad_request", "Please choose a statement to upload.")
    plane = _plane(request)

    def go():
        did = E.register(plane, None, viewer, str(body.get("source_code") or "manager_email"), received_at=received, data=data, filename=name,
                     names=[str(n)[:200] for n in (body.get("fund_names") or [])[:3]] if isinstance(body.get("fund_names"), list) else None)
        return {"id": did, "document": S.detail(plane, did, viewer)}
    return _answer(go)


@router.get(BASE)
def documents(request: Request, instrument_id: str = ""):
    viewer = viewer_of(request)
    plane = _plane(request)
    return _answer(lambda: {"documents": S.rows(plane, viewer, instrument_id or None)})


@router.get(BASE + "/{document_id}")
def document(request: Request, document_id: str):
    viewer = viewer_of(request)
    plane = _plane(request)
    return _answer(lambda: S.detail(plane, document_id, viewer))


@router.get(BASE + "/{document_id}/original")
def original(request: Request, document_id: str):
    viewer = viewer_of(request)
    plane = _plane(request)

    def go():
        doc = E.detail(plane, document_id)  # Refused(404) on an unknown id: answered, not a 500
        if not S.can_see(plane, viewer, doc["instrument_id"]):
            return _plain(403, "not_allowed", "You do not have access to this statement.")
        return FileResponse(plane.path(*doc["original_uri"].split("/")), filename=doc["original_filename"])
    return _answer(go)
