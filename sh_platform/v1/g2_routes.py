"""G2 routes: Go live (the project's owner) and the run book (drafted by Flow, edited and signed by the ops manager).

- `POST /api/v1/projects/{pid}/go-live` → the project, now live; 409 with a plain sentence when it cannot
- `POST /api/v1/projects/{pid}/run-book/draft` → Flow's draft (ops seat); `PUT …/run-book` {sections: [{lines}]} edits; `POST …/run-book/sign`
"""
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import g2_runbook as R
from sh_platform.v1 import p1_project as P1
from sh_platform.v1 import p5_handover as P5
from sh_platform.v1 import t2_tickets as T2
from sh_platform.v1.seats import CONSUMER, OPS_MANAGER, require_seat, seat_of

router = APIRouter()
BASE = "/api/v1/projects/{pid}"


def _gate(plane, viewer, pid: str, runbook: bool) -> None:
    """G1: the project's own people. The run book is also for the ops seat, once the project is live (G2), but only when someone with "full" on
    the project gave them a ticket on it; ops joins the team then. A person never adds themselves."""
    rec, lvl = G1.require(plane, viewer, pid, "read")
    if runbook and lvl != "full":
        if rec.get("stage") != "live" or OPS_MANAGER not in seat_of(viewer) or not T2.assigned_on(plane, viewer, pid):
            raise P1.Refused(403, "The run book opens to the ops seat once the project is live and the owner or builder has given you a ticket on it.")
        G1.join(plane, pid, viewer.name, "ops", viewer.account_id)


async def _run(request: Request, seat: str, fn, runbook: bool = True):
    viewer = require_seat(request, seat)
    from sh_platform.profile.api import _plane
    try:
        _gate(_plane(request), viewer, request.path_params["pid"], runbook)
        return await run_in_threadpool(fn, _plane(request), viewer.name or "someone")
    except P1.Refused as e:
        return JSONResponse({"error": {404: "not_found", 403: "not_allowed"}.get(e.status, "conflict"), "message": e.message}, status_code=e.status)
    except (P5.Refusal, R.Refusal) as e:
        return JSONResponse({"error": "conflict", "message": str(e)}, status_code=409)
    except LookupError:
        return JSONResponse({"error": "not_found", "message": "There is no such project."}, status_code=404)
    except ValueError as e:
        return JSONResponse({"error": "invalid", "message": str(e)}, status_code=400)


@router.post(BASE + "/go-live")
async def go_live(request: Request, pid: str):
    return await _run(request, CONSUMER, lambda plane, who: P5.go_live(plane, pid, who), runbook=False)


@router.post(BASE + "/run-book/draft")
async def draft(request: Request, pid: str):
    return await _run(request, OPS_MANAGER, lambda plane, who: R.draft(plane, P1.read(plane, pid), who))


@router.put(BASE + "/run-book")
async def edit(request: Request, pid: str):
    try:
        body = await request.json()
    except ValueError:
        body = None
    sections = body.get("sections") if isinstance(body, dict) else None
    return await _run(request, OPS_MANAGER, lambda plane, who: R.edit(plane, P1.read(plane, pid)["intent_id"], sections, who))


@router.post(BASE + "/run-book/sign")
async def sign(request: Request, pid: str):
    return await _run(request, OPS_MANAGER, lambda plane, who: R.sign(plane, P1.read(plane, pid), who))
