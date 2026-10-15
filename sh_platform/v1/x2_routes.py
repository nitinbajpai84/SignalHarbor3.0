"""X2 Home: `GET /api/v1/home`, what waits for the signed-in person's seats (sh_platform/v1/x2_home.py)."""
from fastapi import APIRouter, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import x2_home
from sh_platform.v1.seats import viewer_of

router = APIRouter()


@router.get("/api/v1/home")
def get_home(request: Request) -> dict:
    viewer = viewer_of(request)
    try:
        plane = _plane(request)
    except PermissionError:
        raise HTTPException(403, {"error": "forbidden", "message": "Your company space could not be opened."}) from None
    return x2_home.build(plane, viewer)
