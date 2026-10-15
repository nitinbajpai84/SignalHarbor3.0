"""Harbor 3.0 role routes (logic in v3_roles). Failures answer a plain message."""
from fastapi import APIRouter, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import v3_roles as R

router = APIRouter()


def _me(request: Request) -> dict:
    return request.app.state.account_store.get(request.state.account_id) or {}


def _admin(request: Request) -> bool:
    return bool(R.ADMINISH & set(request.state.roles or []))


def _mine(request: Request) -> list[dict]:
    me = _me(request)
    rows = [a for a in request.app.state.account_store._read() if a.get("company_id") == request.state.company_id]  # emails stay inside this module
    return rows if _admin(request) else [a for a in rows if a["account_id"] == me.get("account_id")]


@router.get("/api/v3/me/role")
def get_my_role(request: Request):
    return R.my_role(_plane(request), str(_me(request).get("email") or ""))


@router.get("/api/v3/people/jobs")
def get_jobs(request: Request):
    return {"people": R.jobs_list(_plane(request), _mine(request)), "roles": R.my_role(_plane(request), "")["roles"]}


@router.post("/api/v3/people/job")
async def post_job(request: Request):
    try:
        b = await request.json()
    except ValueError:
        b = None
    b = b if isinstance(b, dict) else {}
    me = str(_me(request).get("email") or "").casefold()
    email = str(b.get("email") or me).strip().casefold()  # no email: your own
    if email != me and not _admin(request):
        raise HTTPException(403, "You can set your own job; an admin sets anyone's.")
    if email not in {a["email"] for a in _mine(request)}:
        raise HTTPException(404, "I cannot find that person.")
    try:
        R.set_job(_plane(request), email, str(b.get("role") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return R.my_role(_plane(request), me)
