"""Agent memory routes (sh_platform/v1/mem_agent.py). A person lists, corrects and forgets their own items; the company's items are read by
everyone in the company and written by the company administrator and analysts. The person is always the signed-in one: no route names
another person.

- `GET /api/v1/memory/me` -> {items: [{id, agent, agent_name, kind, text, sure, at, source}]}
- `PATCH /api/v1/memory/me/{id}` {text} -> the corrected item ; `DELETE /api/v1/memory/me/{id}` -> {forgotten: id}
- `GET /api/v1/memory/company` ; `POST /api/v1/memory/company` {text} or {term, concept_id} ; `PATCH|DELETE /api/v1/memory/company/{id}`"""
import logging

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import mem_agent as M
from sh_platform.v1.p1_project import Refused
from sh_platform.v1.seats import viewer_of

log = logging.getLogger(__name__)
router = APIRouter()
CODES = {400: "invalid", 403: "not_allowed", 404: "not_found"}


def _run(request: Request, fn):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        return JSONResponse(fn(plane, viewer))
    except Refused as e:
        return JSONResponse({"error": CODES.get(e.status, "failed"), "message": e.message}, status_code=e.status)
    except (OSError, ValueError):
        log.warning("memory could not be read or written", exc_info=True)
        return JSONResponse({"error": "failed", "message": "The memory could not be opened. Please try again."}, status_code=500)


@router.get("/api/v1/memory/me")
def mine(request: Request):
    return _run(request, lambda p, v: {"items": M.mine(p, v)})


@router.patch("/api/v1/memory/me/{item_id}")
def fix_mine(request: Request, item_id: str, body: dict = Body(default_factory=dict)):
    return _run(request, lambda p, v: M._view(M.correct(p, v, item_id, body.get("text")), "person"))


@router.delete("/api/v1/memory/me/{item_id}")
def forget_mine(request: Request, item_id: str):
    def go(p, v):
        M.forget(p, v, item_id)
        return {"forgotten": item_id}
    return _run(request, go)


@router.get("/api/v1/memory/company")
def company(request: Request):
    return _run(request, lambda p, v: {"items": M.company_items(p), "may_edit": bool(set(v.roles) & M.EDITORS)})


@router.post("/api/v1/memory/company")
def add_company(request: Request, body: dict = Body(default_factory=dict)):
    return _run(request, lambda p, v: M._view(M.remember_company(p, v, body.get("text") or "", body.get("term") or "", body.get("concept_id") or ""), "company"))


@router.patch("/api/v1/memory/company/{item_id}")
def fix_company(request: Request, item_id: str, body: dict = Body(default_factory=dict)):
    return _run(request, lambda p, v: M._view(M.correct(p, v, item_id, body.get("text"), company=True), "company"))


@router.delete("/api/v1/memory/company/{item_id}")
def forget_company(request: Request, item_id: str):
    def go(p, v):
        M.forget(p, v, item_id, company=True)
        return {"forgotten": item_id}
    return _run(request, go)
