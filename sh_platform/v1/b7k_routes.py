"""STUDIO2 card B: `GET /api/v1/build/p/{pid}/studio/{did}/checks` -> {checks:[{id, widget, tile, kind, message, fix?:{label, patch, tile}}]} (b7k_checks)."""
from fastapi import APIRouter, Request

from sh_platform.v1 import b7_routes as R
from sh_platform.v1 import b7k_checks as K

router = APIRouter()


@router.get(R.DASH + "/checks")
async def studio_checks(request: Request, pid: str, did: str):
    return await R._run(request, lambda p, v: K.checks(p, v, pid, did))
