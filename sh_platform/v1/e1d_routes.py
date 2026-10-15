"""E1d routes: your reach into the warehouse, and (company_admin only) access groups, members and scopes. Logic: e1_access."""
from fastapi import APIRouter, Body, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import e1_access as A
from sh_platform.v1.seats import NO_SPACE, viewer_of

router = APIRouter()
BASE = "/api/v1/access"


def _ctx(request: Request, admin: bool):
    v = viewer_of(request)
    if admin and not A.is_admin(v):
        raise HTTPException(403, {"error": "not_allowed", "message": "Only the company admin can change access."})
    try:
        return _plane(request), v
    except PermissionError:
        raise HTTPException(403, {"error": "forbidden", "message": NO_SPACE}) from None


def _do(fn, *a):
    try:
        return fn(*a)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@router.get(BASE + "/mine")
def mine(request: Request):
    p, v = _ctx(request, False)
    return {"entities": sorted(A.visible_entities(p, v)), "portfolios": sorted(A.visible_portfolios(p, v))}


@router.get(BASE + "/groups")
def groups(request: Request):
    p, _ = _ctx(request, True)
    return {"groups": A.list_groups(p)}


@router.post(BASE + "/groups")
def post_group(request: Request, body: dict = Body(default_factory=dict)):
    p, v = _ctx(request, True)
    return {"id": _do(A.add_group, p, v, body.get("group_name") or "", body.get("description") or "")}


@router.post(BASE + "/groups/{gid}/members")
def post_member(request: Request, gid: str, body: dict = Body(default_factory=dict)):
    p, v = _ctx(request, True)
    return {"id": _do(A.add_member, p, v, gid, body.get("user_id") or "", body.get("expires_at"))}


@router.delete(BASE + "/groups/{gid}/members/{uid}")
def delete_member(request: Request, gid: str, uid: str):
    p, v = _ctx(request, True)
    return {"removed": A.remove_member(p, v, gid, uid)}


@router.post(BASE + "/groups/{gid}/scopes")
def post_scope(request: Request, gid: str, body: dict = Body(default_factory=dict)):
    p, v = _ctx(request, True)
    return {"id": _do(A.add_scope, p, v, gid, body.get("scope_type") or "", body.get("scope_value") or "", body.get("access_level") or "")}
