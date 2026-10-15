"""E1c routes (read only).

- `GET /api/v1/reports` -> reports with their versions (id, period_end, cutoff_at, status, issued_at, supersedes)
- `GET /api/v1/reports/versions/{id}?view=issued|now` -> {version_id, view, lines: [{key, label, value (string), currency, status, issued_value?}]}
  Lines for portfolios the person cannot see are left out (E1d). If E1d is not available nothing is shown.
"""
import logging
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request

from sh_platform.profile.api import _plane
from sh_platform.v1 import e1_reports as R
from sh_platform.v1.seats import viewer_of

router = APIRouter()
log = logging.getLogger(__name__)


def _visible(plane, viewer, line: dict) -> bool:
    from sh_platform.v1 import e1_access  # lazy; ImportError means no access (fail closed)
    pf = line.get("portfolio_id")
    if not pf and line.get("is_total"):  # a report-wide total needs every portfolio in the warehouse
        mine = e1_access.visible_portfolios(plane, viewer)
        return bool(mine) and mine >= e1_access._all(plane)[1]
    for s in ([] if pf else line.get("sources", [])):  # a holding with no portfolio: use the one on its source row
        pf = pf or (R._row(plane, s["table"], s["row_id"]) or {}).get("portfolio_id")
    return bool(pf) and e1_access.level(plane, viewer, portfolio_id=str(pf)) != "none"  # still unknown: hide


def _plain(v):
    return str(v) if isinstance(v, Decimal) else v


@router.get("/api/v1/reports")
def reports(request: Request):
    viewer = viewer_of(request)
    plane = _plane(request)
    try:
        from sh_platform.v1 import e1_access
        if not e1_access.visible_portfolios(plane, viewer):
            return []
    except ImportError:
        log.warning("E1d not available; reports hidden")
        return []
    return R.listing(plane)


@router.get("/api/v1/reports/versions/{version_id}")
def version(version_id: str, request: Request, view: str = "issued"):
    viewer = viewer_of(request)
    plane = _plane(request)
    try:
        lines = R.as_known_now(plane, version_id) if view == "now" else R.as_issued(plane, version_id)
        out = [ln for ln in lines if _visible(plane, viewer, ln)]
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    except ImportError:
        raise HTTPException(503, "Access rules are not ready yet, so nothing is shown.") from None
    return {"version_id": version_id, "view": view, "lines": [{k: _plain(v) for k, v in ln.items()} for ln in out]}
