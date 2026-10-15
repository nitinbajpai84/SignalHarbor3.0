"""K2 routes: the Office view in Consume. All read-only; `currency` is USD or any currency with a signed fixing; `as_of` is a date.

- `GET /api/v1/office/holdings?currency=&as_of=`   entities > portfolios > holdings with value, status word and source
- `GET /api/v1/office/issued?currency=`            latest issued report, as issued beside as known now
- `GET /api/v1/office/nav-bridge?currency=&as_of=` investment total vs administrator NAV per portfolio, difference in four parts
- `GET /api/v1/office/liquidity?currency=&as_of=`  available cash and calls/distributions due in 30/60/90 days
- `GET /api/v1/office/why-moved?start=&end=&currency=&portfolio_id=&book=` why a portfolio or the liquid book moved between two dates
Logic and access: k4_office."""
import logging
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import k4_office as O
from sh_platform.v1.seats import viewer_of

log = logging.getLogger(__name__)
router = APIRouter()
BASE = "/api/v1/office"


def _json(v):
    if isinstance(v, Decimal):
        return format(v, "f")  # never "0E-8"
    if isinstance(v, UUID):
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
    except ValueError:
        return JSONResponse({"error": "bad_request", "message": "The date or currency could not be read."}, status_code=400)
    except ImportError:
        log.warning("office view: a data module is missing", exc_info=True)
        return JSONResponse({"error": "unavailable", "message": "The figures are not ready yet, so nothing is shown."}, status_code=503)


@router.get(BASE + "/holdings")
def get_holdings(request: Request, currency: str = "USD", as_of: str = ""):
    return _run(request, lambda p, v: O.holdings(p, v, currency, as_of or None))


@router.get(BASE + "/issued")
def get_issued(request: Request, currency: str = ""):
    return _run(request, lambda p, v: O.issued_vs_known(p, v, currency or None))


@router.get(BASE + "/nav-bridge")
def get_nav_bridge(request: Request, currency: str = "USD", as_of: str = ""):
    return _run(request, lambda p, v: O.nav_bridge(p, v, currency, as_of or None))


@router.get(BASE + "/liquidity")
def get_liquidity(request: Request, currency: str = "USD", as_of: str = ""):
    return _run(request, lambda p, v: O.liquidity(p, v, currency, as_of or None))


@router.get(BASE + "/why-moved")
def get_why_moved(request: Request, start: str, end: str, currency: str = "USD", portfolio_id: str = "", book: str = ""):
    return _run(request, lambda p, v: O.why_moved(p, v, start, end, currency, portfolio_id or None, book or None))
