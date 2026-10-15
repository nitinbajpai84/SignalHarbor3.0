"""E1a routes: what was known then.

- `GET /api/v1/evidence/asof?table=&cutoff=&latest=1&<field>=<value>...` → {table, cutoff, rows}  (any other query parameter is an equality filter)
- `GET /api/v1/evidence/chain?table=&id=` → {table, rows} oldest first
Rows are filtered by E1d: a row of a portfolio the viewer cannot see is left out. Rows with no portfolio need access to at least one.
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import e1_asof as A
from sh_platform.v1.seats import viewer_of

log = logging.getLogger(__name__)
router = APIRouter()
_OWN = {"table", "cutoff", "latest", "id"}


def _plain(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _json(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v) if isinstance(v, (Decimal, UUID)) else v


def _visible(plane, viewer, rows: list[dict], table: str = "") -> list[dict]:
    try:
        from sh_platform.v1 import e1_access
        allowed = e1_access.visible_portfolios(plane, viewer)
    except ImportError:
        log.warning("E1d e1_access is not installed; evidence is withheld")
        raise
    def pf(table, r):  # a row with no portfolio takes the one on an earlier row of its chain; none found -> hidden
        if r.get("portfolio_id"):
            return str(r["portfolio_id"])
        try:
            return next((str(c["portfolio_id"]) for c in A.chain(plane, table, str(r["id"])) if c.get("portfolio_id")), None)
        except Exception:
            return None
    return [r for r in rows if ("portfolio_id" not in r) or pf(table, r) in allowed]


def _run(fn):
    try:
        return fn()
    except A.AsOfError as e:
        return _plain(400, "invalid", str(e))
    except ImportError:
        return _plain(503, "unavailable", "Access checks are not ready yet, so no evidence is shown.")


@router.get("/api/v1/evidence/asof")
def asof(request: Request, table: str = "", cutoff: str = "", latest: str = ""):
    viewer, plane = viewer_of(request), _plane(request)
    where = {k: v for k, v in request.query_params.items() if k not in _OWN}

    def go():
        rows = A.snapshot(plane, table, where, cutoff or None)
        rows = _visible(plane, viewer, rows, table)[: 1 if latest == "1" else None]
        return {"table": table, "cutoff": cutoff or None, "rows": [{k: _json(v) for k, v in r.items()} for r in rows]}
    return _run(go)


@router.get("/api/v1/evidence/chain")
def chain(request: Request, table: str = "", id: str = ""):
    viewer, plane = viewer_of(request), _plane(request)

    def go():
        rows = _visible(plane, viewer, A.chain(plane, table, id), table)
        return {"table": table, "rows": [{k: _json(v) for k, v in r.items()} for r in rows]}
    return _run(go)
