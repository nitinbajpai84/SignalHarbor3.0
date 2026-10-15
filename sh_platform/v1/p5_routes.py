"""P5 routes: the ops card's read (live projects, daily state, open tickets) and tickets. Go live and the run book are G2 (g2_routes)."""
from fastapi import APIRouter, Body, HTTPException, Request

from sh_platform.build import runner
from sh_platform.profile.api import _plane, _viewer
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import p5_handover as P

router = APIRouter()


def _act(fn, *args):
    try:
        return fn(*args)
    except LookupError:
        raise HTTPException(404, "No such project.") from None
    except P.Refusal as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@router.get("/api/v1/ops/live")
def get_board(request: Request, iid: str | None = None) -> dict:
    plane, viewer = runner._company(request)
    got = P.board(plane, iid)  # G1: only the live projects the viewer may read (the ?iid= one is gated by the router)
    return {**got, "projects": [r for r in got["projects"] if G1.may_see_project(plane, viewer, r["pid"]) in ("full", "read")]}


@router.post("/api/v1/ops/tickets")
def post_ticket(request: Request, body: dict = Body(...)) -> dict:
    plane, viewer = runner._company(request)
    pid = body.get("pid") if isinstance(body, dict) else None
    try:
        if isinstance(pid, str):
            G1.require(plane, viewer, pid, "read")  # G1: no ticket on a project the viewer cannot read
    except G1.Refused as e:
        if e.status == 403:
            raise HTTPException(403, {"error": "not_allowed", "message": e.message}) from None
    return _act(P.raise_ticket, plane, body, viewer.name or "someone")
