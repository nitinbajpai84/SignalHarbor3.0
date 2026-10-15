"""STUDIO2 card D: sketch to dashboard. DASH = /api/v1/build/p/{pid}/studio/{did}
- `POST DASH/sketch` {name, data (base64 picture or pdf) | labels: [text or {label,x,y,w,h}]} -> {boxes:[{id,label,row,col,headline,status,maps_to?,why,question?,needs?}]}
- `POST DASH/sketch/build` {boxes} -> {placed, left_out, step} ; `POST DASH/sketch/request` {boxes} -> {request_id} (a data-team ticket, t2_tickets)
The picture is read on this machine and goes nowhere else."""
from fastapi import APIRouter, Body, Request

from sh_platform.v1 import b7_routes as B
from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import b7s_sketch as K

router = APIRouter()
DASH = B.DASH


@router.post(DASH + "/sketch")
async def sketch(request: Request, pid: str, did: str, body: dict = Body(default_factory=dict)):
    def go(p, v):
        B._maker(v)
        S._editor(p, v, pid, did)
        return K.read_sketch(p, pid, body)
    return await B._run(request, go)


@router.post(DASH + "/sketch/build")
async def sketch_build(request: Request, pid: str, did: str, body: dict = Body(default_factory=dict)):
    def go(p, v):
        B._maker(v)
        return K.build(p, v, pid, did, body) | {"dashboard": S.view(p, v, pid, did)}
    return await B._run(request, go)


@router.post(DASH + "/sketch/request")
async def sketch_request(request: Request, pid: str, did: str, body: dict = Body(default_factory=dict)):
    def go(p, v):
        B._maker(v)
        S._editor(p, v, pid, did)
        return K.request(p, v, pid, body)
    return await B._run(request, go)
