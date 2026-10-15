"""N2 routes: `GET /api/v1/comments?kind=&id=` the thread; `POST /api/v1/comments` {kind, id, text, parent_id?}; `PUT|DELETE /api/v1/comments/{cid}`;
`POST /api/v1/comments/{cid}/raise` {as: case|ticket}; `GET /api/v1/comments/people` names for @mentions."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import n2_comments as C
from sh_platform.v1.seats import viewer_of

router = APIRouter()


def _run(request: Request, fn):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        return JSONResponse(fn(plane, viewer))
    except C.Refused as e:
        return JSONResponse({"error": "not_allowed" if e.status == 403 else "refused", "message": e.message}, status_code=e.status)


async def _body(request: Request) -> dict:
    try:
        b = await request.json()
    except ValueError:
        return {}
    return b if isinstance(b, dict) else {}


@router.get("/api/v1/comments")
def get_thread(request: Request, kind: str = "", id: str = ""):
    return _run(request, lambda p, v: C.thread(p, v, kind, id))


@router.get("/api/v1/comments/people")
def get_people(request: Request):
    viewer_of(request)
    return JSONResponse([{"name": p["name"]} for p in C.people(_plane(request))])


@router.post("/api/v1/comments")
async def post_comment(request: Request):
    b = await _body(request)
    return _run(request, lambda p, v: C.add(p, v, str(b.get("kind") or ""), str(b.get("id") or ""), b.get("text"), b.get("parent_id")))


@router.put("/api/v1/comments/{cid}")
async def put_comment(cid: str, request: Request):
    b = await _body(request)
    return _run(request, lambda p, v: C.edit(p, v, cid, b.get("text")))


@router.delete("/api/v1/comments/{cid}")
def delete_comment(cid: str, request: Request):
    return _run(request, lambda p, v: C.delete(p, v, cid))


@router.post("/api/v1/comments/{cid}/raise")
async def raise_comment(cid: str, request: Request):
    b = await _body(request)
    return _run(request, lambda p, v: C.raise_as(p, v, cid, str(b.get("as") or "case")))
