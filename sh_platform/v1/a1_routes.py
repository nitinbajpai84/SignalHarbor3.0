"""A1 routes: Span's conversation with the architect, and the head of data's approval.

- `GET /api/v1/build/{iid}/blueprint/chat` → the view (turns, data model, questions, design layers, scan, mapping summary), plus
  `can_talk` (architect seat) and `can_approve` (the head of data seat).
- `POST /api/v1/build/{iid}/blueprint/chat` {text, files?: [{name, data (base64), kind?}]} → the same, after Span's reply (architect
  seat). Files are stored where I2 puts them (`i2_north.save_file`: a sample under landing/, a document under documents/).
- `POST /api/v1/build/{iid}/blueprint/approve` → "Approve design and mapping for the engineer" (the head of data seat: head_of_data or company_admin).
Refusals are `{"error", "message"}`; a switched-off Build centre is refused as b3 does."""
import json

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.build.agents.routes import _switched_on
from sh_platform.build.agents.runtime import runtime_for_request
from sh_platform.profile.api import _plane
from sh_platform.v1 import a1_chat as C
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import i2_north as N
from sh_platform.v1.i2_routes import MAX_TURN_BODY, _decode
from sh_platform.v1.seats import ARCHITECT, CONSUMER, HEAD_OF_DATA, require_seat, seat_of, viewer_of

router = APIRouter()
BASE = "/api/v1/build/{iid}/blueprint"
MAX_BODY = 16 * 1024


def _err(status: int, message: str) -> JSONResponse:
    code = {400: "invalid", 403: "not_allowed", 404: "not_found", 409: "conflict"}.get(status, "invalid")
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _answer(request: Request, viewer, fn):
    if not _switched_on(request):
        return _err(403, "The Build centre is switched off for this company.")
    try:
        out = fn(_plane(request))
    except C.Refused as e:
        return _err(e.status, e.message)
    except PermissionError:
        return _err(403, "This company space cannot be opened.")
    return {**out, "can_talk": out["state"] != "approved",
            "can_approve": HEAD_OF_DATA in seat_of(viewer) and out["state"] != "approved"}


@router.get(BASE + "/chat")
def get_chat(iid: str, request: Request):
    viewer = viewer_of(request)
    G1.http_gate(_plane(request), viewer, iid)  # G1
    return _answer(request, viewer, lambda plane: C.view(plane, iid, viewer))


@router.post(BASE + "/chat")
async def post_chat(iid: str, request: Request):
    viewer = require_seat(request, CONSUMER)  # anyone who may see the project may talk to Span; the logic leaves the design to the architect
    G1.http_gate(_plane(request), viewer, iid, "read")  # G1
    raw = await request.body()
    if len(raw) > (MAX_TURN_BODY if b'"files"' in raw else MAX_BODY):
        return _err(400, "That message is too long.")
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        body = {}
    text = str(body.get("text") or "") if isinstance(body, dict) else ""
    raw_files = body.get("files") if isinstance(body, dict) else None

    def work(plane):
        try:  # V1: files dropped into Span's conversation, saved as I2 saves them
            files = [N.save_file(plane, iid, str(f.get("name") or ""), _decode(f.get("data")), f.get("kind"))
                     for f in raw_files or [] if isinstance(f, dict)]
        except N.Refused as e:
            raise C.Refused(e.status, e.message) from None
        return C.chat(plane, runtime_for_request(request, plane, viewer), iid, viewer, text, files)
    return await run_in_threadpool(_answer, request, viewer, work)


@router.post(BASE + "/approve")
def post_approve(iid: str, request: Request):
    viewer = viewer_of(request)
    if HEAD_OF_DATA not in seat_of(viewer):
        return _err(403, "Only the head of data approves the design.")
    return _answer(request, viewer, lambda plane: C.approve(plane, iid, viewer))
