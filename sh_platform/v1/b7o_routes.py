"""STUDIO2 card C: `POST /api/v1/build/p/{pid}/studio/{did}/tiles/{tid}/options` {text?} -> {options: [{label, why, patch, pick}]} (exactly three, one is Lumen's pick)."""
from fastapi import APIRouter, Body, Request

from sh_platform.v1 import b7o_options as O
from sh_platform.v1.b7_routes import DASH, _maker, _run

router = APIRouter()


@router.post(DASH + "/tiles/{tid}/options")
async def tile_options(request: Request, pid: str, did: str, tid: str, body: dict = Body(default_factory=dict)):
    def go(p, v):
        _maker(v)
        return O.options(p, v, pid, did, tid, str(body.get("text") or ""))
    return await _run(request, go)
