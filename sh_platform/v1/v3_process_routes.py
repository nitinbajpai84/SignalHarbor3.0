"""Harbor 3.0 process-only builds: GET /api/v3/threads/{tid}/sop?format=json|docx|md, the procedure of a thread (logic in v3_process, writing in k8_sop)."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from sh_platform.profile.api import _plane
from sh_platform.v1 import k8_sop as K
from sh_platform.v1 import v3_harbor as H

router = APIRouter()
MIME = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "md": "text/markdown; charset=utf-8"}


@router.get("/api/v3/threads/{tid}/sop")
async def get_sop(tid: str, request: Request, format: str = "json"):
    try:
        th = H.load(_plane(request), tid)
    except KeyError:
        raise HTTPException(404, "I cannot find that thread.") from None
    sop = th.get("sop")
    if not sop:
        raise HTTPException(409, "The procedure is not written yet.")
    if format == "json":
        return sop
    if format not in MIME:
        raise HTTPException(400, "Choose Word or Markdown.")
    data = await run_in_threadpool(K.to_docx, sop) if format == "docx" else K.to_markdown(sop).encode("utf-8")
    return Response(data, media_type=MIME[format], headers={"Content-Disposition": f'attachment; filename="{K.filename(sop, format)}"'})
