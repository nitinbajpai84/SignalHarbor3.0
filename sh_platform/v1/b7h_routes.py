"""STUDIO2 card A routes (logic in b7h_history): talk, history, undo, restore, compare, withdraw, tile inspector, duplicate and delete widget.
DASH = /api/v1/build/p/{pid}/studio/{did}. Makers only; the submitted / published rules are cx_dash's (a submitted draft is edited after withdraw)."""
from fastapi import APIRouter, Body, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import b7h_history as H
from sh_platform.v1 import b7_routes as B
from sh_platform.v1.seats import viewer_of

router = APIRouter()
DASH = B.DASH


async def _go(request: Request, fn):
    """Makers only, then the same error shapes as the rest of the studio."""
    def run(p, v):
        B._maker(v)
        return fn(p, v)
    return await B._run(request, run)


@router.post(DASH + "/talk")
async def talk(request: Request, pid: str, did: str, body: dict = Body(default_factory=dict)):
    return await _go(request, lambda p, v: H.talk(p, v, pid, did, B._with_reading(body)))


@router.get(DASH + "/history")
async def history(request: Request, pid: str, did: str):
    return await _go(request, lambda p, v: H.history(p, v, pid, did))


@router.post(DASH + "/undo")
async def undo(request: Request, pid: str, did: str):
    return await _go(request, lambda p, v: H.undo(p, v, pid, did))


@router.post(DASH + "/history/{n}/restore")
async def restore(request: Request, pid: str, did: str, n: int):
    return await _go(request, lambda p, v: H.restore(p, v, pid, did, n))


@router.get(DASH + "/history/{n}/compare")
async def compare(request: Request, pid: str, did: str, n: int):
    return await _go(request, lambda p, v: H.compare(p, v, pid, did, n))


@router.post(DASH + "/withdraw")
async def withdraw(request: Request, pid: str, did: str):
    return await _go(request, lambda p, v: H.withdraw(p, v, pid, did))


@router.patch(DASH + "/tiles/{tid}")
async def patch_tile(request: Request, pid: str, did: str, tid: str, body: dict = Body(default_factory=dict)):
    return await _go(request, lambda p, v: H.patch_tile(p, v, pid, did, tid, body))


@router.post(DASH + "/widgets/{wid}/duplicate")
async def duplicate(request: Request, pid: str, did: str, wid: str):
    return await _go(request, lambda p, v: H.duplicate_widget(p, v, pid, did, wid))


@router.delete(DASH + "/widgets/{wid}")
async def delete_widget(request: Request, pid: str, did: str, wid: str):
    return await _go(request, lambda p, v: H.delete_widget(p, v, pid, did, wid))
