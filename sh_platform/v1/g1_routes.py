"""G1 routes: who may see a project, asking for access, the project folder.

- `GET /api/v1/projects/{pid}/access` → {level, sensitivity, team, grants, can_manage, requests (to answer)}; a lock row when locked
- `PUT /api/v1/projects/{pid}/access` {sensitivity?, team?: [{name | account_id, role}]}  the owner or a company admin
- `POST …/access/request` {reason?}  a K1 request to the owner;  `POST …/access/answer/{request_id}` {approve, days?, note?}
- `POST …/access/grants` {account_id, days?, why?};  `DELETE …/access/grants/{account_id}`
- `GET …/files` the project folder;  `POST …/files` {name, data (base64)}  upload into projects/<pid>/files/
"""
import base64
import binascii

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import k1_access as K
from sh_platform.v1 import p1_project as P
from sh_platform.v1.i2_north import Refused as UploadRefused
from sh_platform.v1.seats import NO_SPACE, viewer_of

router = APIRouter()
BASE = "/api/v1/projects/{pid}"
CODES = {400: "invalid", 403: "not_allowed", 404: "not_found", 409: "conflict", 413: "invalid", 422: "invalid"}


async def _run(request: Request, fn):
    viewer = viewer_of(request)
    try:
        return await run_in_threadpool(fn, _plane(request), viewer)
    except (P.Refused, UploadRefused) as e:
        return JSONResponse({"error": CODES.get(e.status, "invalid"), "message": e.message}, status_code=e.status)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": NO_SPACE}, status_code=403)


async def _body(request: Request) -> dict:
    try:
        got = await request.json()
    except ValueError:
        got = None
    return got if isinstance(got, dict) else {}


def _days(b: dict, default=None):
    d = b.get("days", default)
    return d if isinstance(d, int) and not isinstance(d, bool) else default


@router.get(BASE + "/access")
async def get_access(request: Request, pid: str):
    def go(plane, v):
        rec = P.read(plane, pid)
        lvl = G1.level(plane, v, rec)
        if lvl not in ("full", "read"):
            return G1.lock_row(rec, lvl, plane, v)
        mine = [r for r in G1.incoming(plane, v) if r.get("project") == pid]
        return {"id": pid, "level": lvl, "sensitivity": G1.sensitivity(rec), "team": G1.team_of(rec), "can_manage": G1.can_manage(rec, v),
                "grants": G1.shown(plane, v, rec)["grants"], "requests": [{k: r.get(k) for k in ("id", "requester", "reason", "at")} for r in mine]}
    return await _run(request, go)


@router.put(BASE + "/access")
async def put_access(request: Request, pid: str):
    b = await _body(request)
    return await _run(request, lambda plane, v: G1.set_access(plane, v, pid, b.get("sensitivity"), b.get("team")))


@router.post(BASE + "/access/request")
async def post_request(request: Request, pid: str):
    b = await _body(request)
    return await _run(request, lambda plane, v: G1.request_access(plane, v, pid, b.get("reason") or ""))


@router.post(BASE + "/access/answer/{request_id}")
async def post_answer(request: Request, pid: str, request_id: str):
    b = await _body(request)
    return await _run(request, lambda plane, v: G1.answer(plane, v, pid, request_id, b.get("approve") is True, _days(b, K.DEFAULT_DAYS), b.get("note") or ""))


@router.post(BASE + "/access/grants")
async def post_grant(request: Request, pid: str):
    b = await _body(request)
    return await _run(request, lambda plane, v: G1.grant(plane, v, pid, str(b.get("account_id") or ""), _days(b), b.get("why") or ""))


@router.delete(BASE + "/access/grants/{account_id}")
async def delete_grant(request: Request, pid: str, account_id: str):
    return await _run(request, lambda plane, v: G1.revoke(plane, v, pid, account_id))


@router.get(BASE + "/files")
async def get_files(request: Request, pid: str):
    return await _run(request, lambda plane, v: {"files": G1.files(plane, v, pid)})


@router.post(BASE + "/files")
async def post_file(request: Request, pid: str):
    b = await _body(request)
    try:
        data = base64.b64decode(str(b.get("data") or ""), validate=True)
    except (binascii.Error, ValueError):
        return JSONResponse({"error": "invalid", "message": "That file could not be read. Please try again."}, status_code=400)
    return await _run(request, lambda plane, v: G1.add_file(plane, v, pid, str(b.get("name") or ""), data))
