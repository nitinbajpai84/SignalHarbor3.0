"""Harbor skills routes (docs/v3/HARBOR-SPEC.md, "Added 15 Oct"). Logic in v3_skills; every failure answers a plain message."""
from fastapi import APIRouter, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import v3_skills as S

router = APIRouter()


async def _json(request: Request) -> dict:
    try:
        body = await request.json()
    except ValueError:
        body = None
    return body if isinstance(body, dict) else {}


def _who(request: Request) -> str:
    acct = request.app.state.account_store.get(request.state.account_id) or {}
    return (acct.get("display_name") if isinstance(acct, dict) else getattr(acct, "display_name", None)) or "A colleague"


def _call(fn, *args):
    try:
        return fn(*args)
    except KeyError:
        raise HTTPException(404, "I cannot find that skill.") from None
    except ValueError as e:
        raise HTTPException(409, str(e)) from None


@router.get("/api/v3/skills")
def list_skills(request: Request, status: str | None = None):
    return {"skills": S.listing(_plane(request), status)}


@router.get("/api/v3/skills/usage")  # before /{sid}, so "usage" is not read as a skill id
def usage(request: Request, thread: str | None = None):
    plane = _plane(request)
    return {"runs": [{**{k: r.get(k) for k in ("at", "skill", "ms", "ok", "detail")}, "name": S.name_of(plane, r["skill"])} for r in S.runs(plane, thread)]}


@router.get("/api/v3/skills/{sid}")
def get_skill(sid: str, request: Request):
    return _call(S.read, _plane(request), sid)


@router.post("/api/v3/skills/{sid}/edit")
async def edit_skill(sid: str, request: Request):
    b = await _json(request)
    return _call(S.edit, _plane(request), sid, str(b.get("field") or ""), b.get("value"), _who(request))


@router.post("/api/v3/skills/{sid}/try")
def try_skill(sid: str, request: Request):
    plane = _plane(request)
    _call(S.read, plane, sid)
    return S.try_(plane, sid)


@router.post("/api/v3/skills/{sid}/admit")
def admit_skill(sid: str, request: Request):
    return _call(S.admit, _plane(request), sid, _who(request))


@router.post("/api/v3/skills/{sid}/reject")
async def reject_skill(sid: str, request: Request):
    b = await _json(request)
    return _call(S.reject, _plane(request), sid, str(b.get("reason") or ""), _who(request))
