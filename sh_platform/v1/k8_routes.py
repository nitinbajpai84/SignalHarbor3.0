"""K7 routes: the SOP of a signed intent of work, as a preview and as a download (Word by default, Markdown on request).
GET /api/v1/intents/{iid}/sop            the SOP as data
GET /api/v1/intents/{iid}/sop/download   ?format=docx|md
Reading is for every seat that may read the intent of work (I4's rule). A draft has no SOP: the process is not agreed yet."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from sh_platform.profile.api import _plane
from sh_platform.v1 import i4_sow as S
from sh_platform.v1 import k8_sop as K
from sh_platform.v1.seats import CONSUMER, require_seat

router = APIRouter()
BASE = "/api/v1/intents/{iid}/sop"


async def _signed_sop(request: Request, iid: str) -> dict:
    require_seat(request, CONSUMER)
    try:
        plane = _plane(request)
    except PermissionError:
        raise HTTPException(403, {"error": "forbidden", "message": "Your company space could not be opened."}) from None
    try:
        sow = await run_in_threadpool(S.read, plane, iid)
    except S.SowError as e:
        raise HTTPException(e.status, {"error": e.code, "message": e.message}) from None
    if sow.get("state") != "signed":
        raise HTTPException(409, {"error": "not_signed", "message": "The procedure can be written once the intent of work is signed."})
    return K.build(sow)


@router.get(BASE)
async def preview(request: Request, iid: str):
    return await _signed_sop(request, iid)


@router.get(BASE + "/download")
async def download(request: Request, iid: str, format: str = "docx"):
    sop = await _signed_sop(request, iid)
    if format == "docx":  # PF2: always Word; k8_sop writes it without python-docx when that is not installed
        data, mime, ext = await run_in_threadpool(K.to_docx, sop), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
    elif format == "md":
        data, mime, ext = K.to_markdown(sop).encode("utf-8"), "text/markdown; charset=utf-8", "md"
    else:
        raise HTTPException(400, {"error": "bad_request", "message": "Choose Word or Markdown."})
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{K.filename(sop, ext)}"'})
