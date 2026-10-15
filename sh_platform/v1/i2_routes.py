"""I2 routes: start an intent with one line, read the thread, add a turn (with files), upload a file.

Files travel as base64 in JSON (the 2.0 context_docs upload shape: no multipart library). The body reader is copied from
`sh_platform/context_docs/api.py` `_json_body`. The decision maker writes; the architect seat may read.
"""
import base64
import binascii
import json

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.build.agents.runtime import get_model
from sh_platform.context_docs import reader
from sh_platform.intents.store import Unreadable, VersionConflict
from sh_platform.profile.api import _plane
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import i2_north as N
from sh_platform.v1.seats import CONSUMER, require_seat, viewer_of

router = APIRouter()
MAX_FILE_BODY = reader.MAX_UPLOAD_BYTES * 4 // 3 + 64 * 1024
MAX_TURN_BODY = 4 * MAX_FILE_BODY  # a turn may carry a few files inline


def _plain(status: int, error: str, message: str) -> JSONResponse:
    return JSONResponse({"error": error, "message": message}, status_code=status)


async def _json_body(request: Request, limit: int, mb: int = reader.MAX_UPLOAD_BYTES // 1_000_000) -> dict | JSONResponse:
    too_big = _plain(413, "too_big", f"That is too large. The limit is {mb} MB a file.")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        return too_big
    raw = bytearray()
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > limit:
            return too_big
    try:
        body = json.loads(bytes(raw))
    except ValueError:
        body = None
    return body if isinstance(body, dict) else _plain(400, "bad_request", "That could not be read. Please try again.")


def _decode(data) -> bytes:
    try:
        return base64.b64decode(str(data or ""), validate=True)
    except (binascii.Error, ValueError):
        raise N.Refused(400, "That file could not be read. Please try again.") from None


def _answer(fn):
    try:
        return fn()
    except N.Refused as e:
        code = {403: "not_allowed", 404: "not_found", 409: "conflict", 413: "too_big"}.get(e.status, "invalid")
        return _plain(e.status, code, e.message)
    except (Unreadable, VersionConflict):
        return _plain(409, "conflict", "This intent could not be saved. Please reload.")
    except PermissionError:
        return _plain(403, "forbidden", "Your company space could not be opened. Please ask your administrator.")


def _model(request: Request, plane):
    return get_model(request.app.state, plane)


def _pack(request: Request):
    st = request.app.state
    industry = str((st.entitlements.company(request.state.company_id) or {}).get("industry") or "")
    try:
        return st.packs.load(industry) if industry else None
    except ValueError:
        return None


@router.post("/api/v1/intents")
async def start(request: Request):
    viewer = require_seat(request, CONSUMER)
    body = await _json_body(request, 16 * 1024)
    if isinstance(body, JSONResponse):
        return body

    def work():
        plane = _plane(request)
        return N.create(plane, viewer, str(body.get("line") or ""), model=_model(request, plane))
    return await run_in_threadpool(_answer, work)


@router.get("/api/v1/intents/{iid}/thread")
def get_thread(iid: str, request: Request):
    G1.http_gate(_plane(request), viewer_of(request), iid)  # G1

    def work():
        plane = _plane(request)
        return {**N.read_thread(plane, iid), "sow": N.read_sow(plane, iid)}
    return _answer(work)


@router.post("/api/v1/intents/{iid}/thread/files")
async def upload(iid: str, request: Request):
    G1.http_gate(_plane(request), require_seat(request, CONSUMER), iid, "full")  # G1
    body = await _json_body(request, MAX_FILE_BODY)
    if isinstance(body, JSONResponse):
        return body
    return await run_in_threadpool(_answer, lambda: N.save_file(_plane(request), iid, str(body.get("name") or ""),
                                                                _decode(body.get("data")), body.get("kind")))


@router.post("/api/v1/intents/{iid}/thread")
async def add_turn(iid: str, request: Request):
    viewer = require_seat(request, CONSUMER)
    G1.http_gate(_plane(request), viewer, iid, "full")  # G1
    body = await _json_body(request, MAX_TURN_BODY)
    if isinstance(body, JSONResponse):
        return body

    def work():
        plane = _plane(request)
        files = []
        for f in body.get("files") or []:
            if not isinstance(f, dict):
                raise N.Refused(400, "That file could not be read. Please try again.")
            files.append(N.save_file(plane, iid, str(f.get("name") or ""), _decode(f["data"]), f.get("kind")) if f.get("data")
                         else N.stored_file(plane, f))
        return N.turn(plane, iid, viewer, str(body.get("text") or ""), files, model=_model(request, plane), pack=_pack(request))
    return await run_in_threadpool(_answer, work)
