"""TEACH1 routes: what each person may teach, and the teaching itself. The agent's rights are checked in `teach` (default deny), whatever the route roles say.

- `GET /api/v1/knowledge` → {agents: [{key, name}]} the agents this person may teach
- `GET /api/v1/knowledge/{agent}` → {agent, items}
- `POST /api/v1/knowledge/{agent}` {title, name+data (base64) | text} → item
- `PUT /api/v1/knowledge/{agent}/{id}` {title?, name+data | text} → item (a new version)
- `POST /api/v1/knowledge/{agent}/{id}/active` {active} → item
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import teach as T
from sh_platform.v1.i2_routes import _answer, _decode, _json_body
from sh_platform.v1.seats import viewer_of

router = APIRouter()
MAX_BOOK_BODY = T.MAX_BOOK * 4 // 3 + 64 * 1024  # base64 grows a file by a third


def _kw(body: dict) -> dict:
    return {"filename": str(body.get("name") or ""), "data": _decode(body.get("data")) if body.get("data") else None,
            "text": body.get("text") if isinstance(body.get("text"), str) else None}


@router.get("/api/v1/knowledge")
def agents(request: Request):
    return {"agents": T.agents_for(viewer_of(request))}


@router.get("/api/v1/knowledge/{agent}")
def listing(agent: str, request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: {"agent": agent, "items": T.listing(_plane(request), viewer, agent)})


@router.post("/api/v1/knowledge/{agent}")
async def add(agent: str, request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, MAX_BOOK_BODY, T.MAX_BOOK // 1_000_000)
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: T.add(_plane(request), viewer, agent, body.get("title"), always=body.get("always") is True, **_kw(body)))


@router.put("/api/v1/knowledge/{agent}/{item_id}")
async def replace(agent: str, item_id: str, request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, MAX_BOOK_BODY, T.MAX_BOOK // 1_000_000)
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: T.replace(_plane(request), viewer, agent, item_id, title=body.get("title"), **_kw(body)))


@router.post("/api/v1/knowledge/{agent}/{item_id}/active")
async def active(agent: str, item_id: str, request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, 4096)
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: T.set_active(_plane(request), viewer, agent, item_id, body.get("active") is True))
