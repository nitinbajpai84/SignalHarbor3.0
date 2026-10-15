"""L2 routes: the changes an agent proposed and nobody has decided yet.

- `GET /api/v1/intents/{iid}/proposals` -> {pending: [...], recent: [...]}  (whoever may read the project; the v1 intent gate checks that)
- `POST /api/v1/intents/{iid}/proposals/{id}/accept` -> the accepted proposal  (the project's team, and only a role that may write that document)
- `POST /api/v1/intents/{iid}/proposals/{id}/reject` {reason?} -> the rejected proposal
Writes go through the v1 intent gate at "full" (G1); the role that may write the document is checked again here.
"""
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import l2_proposals as L2
from sh_platform.v1.seats import viewer_of

router = APIRouter()
CODES = {400: "invalid", 403: "not_allowed", 404: "not_found", 409: "conflict"}


async def _run(fn):
    try:
        return await run_in_threadpool(fn)
    except L2.Refused as e:
        return JSONResponse({"error": CODES.get(e.status, "invalid"), "message": e.message}, status_code=e.status)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": "Your company space could not be opened. Please ask your administrator."}, status_code=403)


def _writer(plane, viewer, iid: str, pid: str) -> None:
    doc = next((p["document"] for p in L2.pending(plane, iid) if p["id"] == pid), None)
    need = L2.WRITERS.get(doc)
    if need and not need & set(getattr(viewer, "roles", ()) or ()):
        raise L2.Refused(403, "Only the people who work on this document can accept or turn down its changes.")


@router.get("/api/v1/intents/{iid}/proposals")
async def listing(request: Request, iid: str):
    viewer, plane = viewer_of(request), _plane(request)
    return await _run(lambda: L2.view(plane, iid))


@router.post("/api/v1/intents/{iid}/proposals/{pid}/accept")
async def accept(request: Request, iid: str, pid: str):
    viewer, plane = viewer_of(request), _plane(request)

    def go():
        _writer(plane, viewer, iid, pid)
        return L2.accept(plane, iid, pid, viewer.name)
    return await _run(go)


@router.post("/api/v1/intents/{iid}/proposals/{pid}/reject")
async def reject(request: Request, iid: str, pid: str):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        body = await request.json()
    except ValueError:
        body = None
    reason = str(body.get("reason") or "") if isinstance(body, dict) else ""

    def go():
        _writer(plane, viewer, iid, pid)
        return L2.reject(plane, iid, pid, viewer.name, reason)
    return await _run(go)
