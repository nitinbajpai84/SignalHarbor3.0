"""Harbor 3.0 operations routes: people, runs, connections, setup. Logic in v3_ops; failures answer a plain message."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from sh_platform.profile.api import _plane
from sh_platform.v1 import v3_ops as O

router = APIRouter()


async def _json(request: Request) -> dict:
    try:
        body = await request.json()
    except ValueError:
        body = None
    return body if isinstance(body, dict) else {}


def _people(request: Request, plane) -> dict:
    return O.people(plane, request.app.state.account_store.in_company(request.state.company_id))


@router.get("/api/v3/people")
def get_people(request: Request):
    return _people(request, _plane(request))


@router.post("/api/v3/people/autonomy")
async def post_autonomy(request: Request):
    plane, b = _plane(request), await _json(request)
    try:
        O.set_autonomy(plane, str(b.get("thread") or ""), str(b.get("level") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    except KeyError:
        raise HTTPException(404, "I cannot find that thread.") from None
    return _people(request, plane)


@router.get("/api/v3/runs")
def get_runs(request: Request):
    return O.runs(_plane(request))


@router.get("/api/v3/connections")
async def get_connections(request: Request):
    return await run_in_threadpool(O.connections, _plane(request))


@router.get("/api/v3/setup")
def get_setup(request: Request):
    return O.setup(request.app, _plane(request), request.state.company_id)


@router.post("/api/v3/setup")
async def post_setup(request: Request):
    plane, b = _plane(request), await _json(request)
    try:
        O.choose_pack(request.app, request.state.company_id, str(b.get("pack") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    except FileExistsError as e:
        raise HTTPException(409, str(e)) from None
    return O.setup(request.app, plane, request.state.company_id)
