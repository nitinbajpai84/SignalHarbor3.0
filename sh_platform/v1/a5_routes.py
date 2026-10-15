"""A2 routes: `GET /api/v1/trail?kind=valuation|position|cash|nav|metric|case|tile&id=` -> the six-step trail (a5_trail)."""
import logging
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import a5_trail as T
from sh_platform.v1.seats import viewer_of

log = logging.getLogger(__name__)
router = APIRouter()


def _json(v):
    if isinstance(v, (Decimal, UUID)):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _json(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_json(x) for x in v]
    return v


@router.get("/api/v1/trail")
def get_trail(request: Request, kind: str = "", id: str = ""):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        return JSONResponse(_json(T.trail(plane, viewer, kind, id)))
    except ValueError as e:
        return JSONResponse({"error": "bad_request", "message": str(e)}, status_code=400)
    except LookupError as e:
        return JSONResponse({"error": "not_found", "message": str(e)}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "not_allowed", "message": "You do not have access to this."}, status_code=403)
