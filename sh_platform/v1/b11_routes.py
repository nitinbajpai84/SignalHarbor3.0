"""V6-builder routes: Span the builder in the Pipelines step (designs H7 to H9). Shapes: ui/src/v1/b11/api.ts.

GET  /api/v1/build/p/{pid}/builder                 pack, connections, run, benchmark, variance, thread, needs, can
POST .../builder/start                             connect and run the newest approved pack (once per version; the screen calls it on open)
POST .../builder/recheck                           connect again after a person fixed what failed
POST .../builder/settle {source, field, value}     settle a mismatch: the system map and the pack change together
POST .../builder/not-needed {source, reason?, needed?}   take a source with no sample out of the build (or put it back)
POST .../builder/benchmark {name, text|b64} or {report_version_id}   the report to check against
POST .../builder/go-live {accept_variance?, no_benchmark?}
POST .../builder/send-back {note?}                 hand the variance to the architect (a hand-off with the evidence)
POST .../builder/pack {changes: [{table, sql, why}], note?, handoff_id?}   the architect issues the next pack version"""
import logging

import duckdb
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.agents import handoff as H
from sh_platform.profile.api import _plane
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import b6_run as R
from sh_platform.v1 import b11_builder as BU
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import p1_project as P1
from sh_platform.v1 import wh
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.seats import CONSUMER, require_seat

router = APIRouter()
log = logging.getLogger(__name__)
CODES = {400: "invalid", 403: "not_allowed", 404: "not_found", 409: "conflict", 422: "invalid"}
BUSY = {"error": "busy", "message": "A data file is busy. Try again in a minute."}
BASE = "/api/v1/build/p/{pid}/builder"


async def _run(request: Request, pid: str, need: str, fn):
    viewer = require_seat(request, CONSUMER)

    def go(plane, v):
        G1.require(plane, v, pid, need)
        return fn(plane, v)
    try:
        return await run_in_threadpool(go, _plane(request), viewer)
    except (Refused, P1.Refused, R.Refused, B.Refused, H.Refused) as e:
        return JSONResponse({"error": CODES.get(e.status, "invalid"), "message": e.message}, status_code=e.status)
    except PermissionError as e:
        if e.errno is None:
            return JSONResponse({"error": "forbidden", "message": "Your company space could not be opened. Please ask your administrator."}, status_code=403)
        return JSONResponse(BUSY, status_code=503)
    except (OSError, wh.Busy, duckdb.IOException) as e:
        log.warning("builder call hit a busy file: %r", e)
        return JSONResponse(BUSY, status_code=503)


async def _body(request: Request) -> dict:
    try:
        got = await request.json()
    except ValueError:
        got = None
    return got if isinstance(got, dict) else {}


@router.get(BASE)
async def get_builder(request: Request, pid: str):
    return await _run(request, pid, "read", lambda plane, v: BU.view(plane, v, pid))


@router.post(BASE + "/start")
async def start(request: Request, pid: str):
    return await _run(request, pid, "full", lambda plane, v: (BU.start(plane, v, pid), BU.view(plane, v, pid))[1])


@router.post(BASE + "/recheck")
async def recheck(request: Request, pid: str):
    return await _run(request, pid, "full", lambda plane, v: (BU.recheck(plane, v, pid), BU.view(plane, v, pid))[1])


@router.post(BASE + "/settle")
async def settle(request: Request, pid: str):
    body = await _body(request)
    return await _run(request, pid, "full", lambda plane, v: (BU.resolve(plane, v, pid, body), BU.view(plane, v, pid))[1])


@router.post(BASE + "/benchmark")
async def benchmark(request: Request, pid: str):
    body = await _body(request)
    return await _run(request, pid, "full", lambda plane, v: BU.set_benchmark(plane, v, pid, body))


@router.post(BASE + "/go-live")
async def go_live(request: Request, pid: str):
    body = await _body(request)
    return await _run(request, pid, "full", lambda plane, v: BU.go_live(plane, v, pid, body))


@router.post(BASE + "/send-back")
async def send_back(request: Request, pid: str):
    body = await _body(request)
    return await _run(request, pid, "full", lambda plane, v: BU.send_back(plane, v, pid, str(body.get("note") or "")))


@router.post(BASE + "/pack")
async def issue_pack(request: Request, pid: str):
    body = await _body(request)
    return await _run(request, pid, "full", lambda plane, v: (BU.issue_version(plane, v, pid, body), BU.view(plane, v, pid))[1])


@router.post(BASE + "/not-needed")
async def not_needed(request: Request, pid: str):
    body = await _body(request)
    return await _run(request, pid, "full", lambda plane, v: (BU.set_not_needed(plane, v, pid, body), BU.view(plane, v, pid))[1])
