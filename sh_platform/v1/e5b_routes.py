"""E5b routes: the CIO Brief.

- `GET /api/v1/brief/{rvid}?currency=SGD` → the report as issued beside as known now, with status per line and the banner
- `POST /api/v1/brief/{rvid}/explain` {line_key, question?} → answer, evidence, sources, caveats, next action, approver (or a refusal)
Logic and access: e5_brief."""
import logging
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import e5_brief as B
from sh_platform.v1.seats import viewer_of

log = logging.getLogger(__name__)
router = APIRouter()
BASE = "/api/v1/brief"


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


def _run(request: Request, fn):
    viewer, plane = viewer_of(request), _plane(request)
    try:
        return JSONResponse(_json(fn(plane, viewer)))
    except LookupError as e:
        return JSONResponse({"error": "not_found", "message": str(e)}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "not_allowed", "message": "You do not have access to this."}, status_code=403)
    except ImportError:
        return JSONResponse({"error": "unavailable", "message": "The report data is not ready yet, so nothing is shown."}, status_code=503)


@router.get(BASE + "/{rvid}")
def get_brief(request: Request, rvid: str, currency: str = ""):
    return _run(request, lambda p, v: B.brief(p, v, rvid, currency or None))


@router.post(BASE + "/{rvid}/explain")
def post_explain(request: Request, rvid: str, body: dict = Body(default_factory=dict)):
    return _run(request, lambda p, v: B.explain(p, v, rvid, str(body.get("line_key") or ""), body.get("question") or None))
