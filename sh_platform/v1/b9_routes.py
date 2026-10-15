"""V5W-3 routes: verify, send for review, business review, fix and run again, accept (the Pipelines step). Shapes: ui/src/v1/b9verify/api.ts.

GET  /api/v1/build/p/{pid}/verify            figures, verified, review, comparison, can
POST .../verify/mark                         the data engineer marks the run verified (who and when)
POST .../verify/send {portfolio, code, month, message?, table?}   assigns the review to the business owner
POST .../verify/flag {text}                  the owner sends the run back with an issue (a case + a comment)
POST .../verify/fix                          the data engineer proposes the signed mix as a rule version and runs the copy again
POST .../verify/accept                       the owner accepts the numbers"""
import logging

import duckdb
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import b9_verify as V
from sh_platform.v1 import e4_cases, n2_comments
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import p1_project as P1
from sh_platform.v1 import wh
from sh_platform.v1 import b6_run as R
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.seats import CONSUMER, require_seat

router = APIRouter()
log = logging.getLogger(__name__)
CODES = {400: "invalid", 403: "not_allowed", 404: "not_found", 409: "conflict"}
BUSY = {"error": "busy", "message": "A data file is busy. Try again in a minute."}
BASE = "/api/v1/build/p/{pid}/verify"


async def _run(request: Request, fn):
    viewer = require_seat(request, CONSUMER)
    try:
        return await run_in_threadpool(fn, _plane(request), viewer)
    except (Refused, P1.Refused, e4_cases.Refused, n2_comments.Refused) as e:  # flag opens a case and comments on it
        return JSONResponse({"error": CODES.get(e.status, "invalid"), "message": e.message}, status_code=e.status)
    except R.Refused as e:
        return JSONResponse({"error": CODES.get(e.status, "invalid"), "message": e.message}, status_code=e.status)
    except PermissionError as e:
        if e.errno is None:
            return JSONResponse({"error": "forbidden", "message": "Your company space could not be opened. Please ask your administrator."}, status_code=403)
        return JSONResponse(BUSY, status_code=503)
    except (OSError, wh.Busy, duckdb.IOException) as e:
        log.warning("verify call hit a busy file: %r", e)
        return JSONResponse(BUSY, status_code=503)


async def _body(request: Request) -> dict:
    try:
        got = await request.json()
    except ValueError:
        got = None
    return got if isinstance(got, dict) else {}


def _act(request: Request, pid: str, need: str, fn):
    def go(plane, v):
        G1.require(plane, v, pid, need)
        fn(plane, v)
        return V.view(plane, v, pid)
    return _run(request, go)


@router.get(BASE)
async def get_verify(request: Request, pid: str):
    return await _run(request, lambda plane, v: (G1.require(plane, v, pid, "read"), V.view(plane, v, pid))[1])


@router.post(BASE + "/mark")
async def mark(request: Request, pid: str):
    return await _act(request, pid, "full", lambda plane, v: V.mark_verified(plane, v, pid))


@router.post(BASE + "/send")
async def send(request: Request, pid: str):
    body = await _body(request)
    return await _act(request, pid, "full", lambda plane, v: V.send_for_review(plane, v, pid, body))


@router.post(BASE + "/flag")
async def flag(request: Request, pid: str):
    body = await _body(request)
    return await _act(request, pid, "read", lambda plane, v: V.flag(plane, v, pid, body.get("text")))  # the business owner reads the project; the module checks who they are


@router.post(BASE + "/fix")
async def fix(request: Request, pid: str):
    return await _act(request, pid, "full", lambda plane, v: V.propose_fix(plane, v, pid))


@router.post(BASE + "/accept")
async def accept(request: Request, pid: str):
    return await _act(request, pid, "read", lambda plane, v: V.accept(plane, v, pid))
